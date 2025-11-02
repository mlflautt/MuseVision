#!/usr/bin/env python3
"""
MuseVision Batch Coordinator

Coordinates sequential execution of batched operations with proper GPU resource management.
Manages ComfyUI lifecycle and LLM/ComfyUI resource coordination.
"""

import os
import sys
import time
import subprocess
import signal
import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from batch_queue_manager import BatchQueueManager
from comfyui_manager import ComfyUIManager
from gpu_optimized_agent import GPUOptimizedAgent
from agent import ModelPreset, resolve_project_dir


class BatchCoordinator:
    """Coordinates batch execution with ComfyUI resource management"""
    
    def __init__(self, queue_path: Optional[str] = None):
        """Initialize the batch coordinator"""
        self.queue_manager = BatchQueueManager(queue_path)
        self.comfyui_manager = ComfyUIManager()
        self.agent = GPUOptimizedAgent()
        self.current_batch_id: Optional[str] = None
        self.coordinator_lock_path = os.path.expanduser("~/.musevision_coordinator.lock")
        
    def is_coordinator_running(self) -> bool:
        """Check if another coordinator is already running"""
        if not os.path.exists(self.coordinator_lock_path):
            return False
            
        try:
            with open(self.coordinator_lock_path, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    pid = int(lines[0].strip())
                    # Check if process is still running
                    try:
                        os.kill(pid, 0)  # Signal 0 just checks if process exists
                        return True
                    except OSError:
                        # Process doesn't exist, remove stale lock
                        os.unlink(self.coordinator_lock_path)
                        return False
        except (ValueError, FileNotFoundError):
            return False
            
        return False
    
    def acquire_coordinator_lock(self) -> bool:
        """Acquire coordinator lock to ensure single instance"""
        if self.is_coordinator_running():
            return False
            
        try:
            with open(self.coordinator_lock_path, 'w') as f:
                f.write(f"{os.getpid()}\n{datetime.now(timezone.utc).isoformat()}\n")
            return True
        except Exception as e:
            print(f"⚠️  Failed to acquire coordinator lock: {e}")
            return False
    
    def release_coordinator_lock(self):
        """Release coordinator lock"""
        try:
            if os.path.exists(self.coordinator_lock_path):
                os.unlink(self.coordinator_lock_path)
        except Exception as e:
            print(f"⚠️  Warning: Failed to release coordinator lock: {e}")
    
    def wait_for_comfyui_queue_completion(self, timeout: int = 3600) -> bool:
        """Wait for current ComfyUI queue to complete, with stall recovery"""
        print("⏳ Waiting for existing ComfyUI queue to complete...")
        
        import requests
        start_time = time.time()
        last_change = start_time
        last_counts = None
        interrupt_sent = False
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://127.0.0.1:8188/queue", timeout=10)
                if response.status_code == 200:
                    queue_info = response.json()
                    
                    executing_items = queue_info.get('queue_running', [])
                    pending_items = queue_info.get('queue_pending', [])
                    
                    if not executing_items and not pending_items:
                        print("✅ ComfyUI queue is now empty")
                        return True
                    
                    # Progress / stall detection
                    counts = (len(executing_items), len(pending_items))
                    if counts != last_counts:
                        last_counts = counts
                        last_change = time.time()
                    else:
                        stalled_for = time.time() - last_change
                        if stalled_for > 600 and not interrupt_sent:  # 10 minutes
                            print("🛎️ Queue appears stalled. Sending /interrupt to nudge the worker...")
                            try:
                                requests.post("http://127.0.0.1:8188/interrupt", timeout=5)
                                interrupt_sent = True
                            except Exception as e:
                                print(f"⚠️  Interrupt failed: {e}")
                        elif stalled_for > 900:  # 15 minutes
                            print("🔄 Queue still stalled after interrupt. Restarting ComfyUI...")
                            self.comfyui_manager.restart()
                            print("✅ After restart, assuming queue cleared.")
                            return True
                    
                    total_jobs = counts[0] + counts[1]
                    if total_jobs <= 5:  # Show details for small queues
                        print(f"🔄 ComfyUI queue: {counts[0]} running, {counts[1]} pending")
                    
                    time.sleep(30)  # Check every 30 seconds
                    
            except requests.RequestException:
                # ComfyUI might be down, which is fine for us
                print("✅ ComfyUI appears to be stopped")
                return True
        
        print(f"⚠️  Timeout waiting for ComfyUI queue completion")
        return False
    
    def execute_batch(self, batch: Dict[str, Any]) -> bool:
        """Execute a single batch with proper resource management"""
        batch_id = batch['id']
        command = batch['command']
        project = batch['project']
        parameters = batch['parameters']
        
        print(f"\n🚀 EXECUTING BATCH: {batch_id}")
        print(f"{'='*60}")
        print(f"📁 Project: {project}")
        print(f"🎯 Command: {command}")
        print(f"⏱️ Estimated duration: {self._format_time(batch['estimated_duration'])}")
        
        self.current_batch_id = batch_id
        
        try:
            # Update batch status to processing
            self.queue_manager.update_batch_status(batch_id, "processing_llm")
            
            # Step 1: ComfyUI Resource Coordination - ALWAYS try to coordinate
            print(f"\n🔄 STEP 1: ComfyUI Resource Coordination")
            print("="*50)
            
            # Check if ComfyUI API is accessible (more reliable than process detection)
            comfyui_accessible = False
            try:
                import requests
                response = requests.get("http://127.0.0.1:8188/system_stats", timeout=2)
                if response.status_code == 200:
                    comfyui_accessible = True
                    print("🎮 ComfyUI is running and accessible via API")
            except:
                print("✅ ComfyUI appears to be stopped")
            
            if comfyui_accessible:
                if not self.wait_for_comfyui_queue_completion():
                    print("⚠️  ComfyUI queue didn't complete in time, stopping anyway...")
                
                # Stop ComfyUI to free GPU memory for LLM
                print("🛑 Stopping ComfyUI to free GPU memory for LLM...")
                if not self.comfyui_manager.stop():
                    print("⚠️  Warning: Failed to stop ComfyUI cleanly")
                
                # More aggressive cleanup - kill any remaining ComfyUI processes
                print("🧽 Ensuring all ComfyUI processes are terminated...")
                self._aggressive_comfyui_cleanup()
                    
                # Wait a moment for GPU memory to be released
                print("⏳ Waiting for GPU memory to be released...")
                time.sleep(8)
            
            # Step 2: Execute LLM phase
            print(f"\n🧠 STEP 2: LLM Prompt Generation")
            print("="*40)
            
            # Create agent jobs for this batch
            self._setup_agent_for_batch(batch)
            
            # Execute LLM phase only
            print("🔮 Generating prompts with LLM...")
            llm_jobs = [job for job in self.agent.job_batch if job.job_type == 'llm_generation']
            for i, job in enumerate(llm_jobs, 1):
                print(f"🔮 LLM Job {i}/{len(llm_jobs)}: {job.command}")
                self.agent._execute_llm_job(job)
            
            # Step 3: Start ComfyUI for image generation
            print(f"\n🎨 STEP 3: ComfyUI Image Generation")
            print("="*40)
            
            self.queue_manager.update_batch_status(batch_id, "processing_images")
            
            print("🚀 Starting ComfyUI for image generation...")
            if not self.comfyui_manager.start():
                raise RuntimeError("Failed to start ComfyUI")
            
            # Execute image generation phase
            img_jobs = [job for job in self.agent.job_batch if job.job_type == 'image_generation']
            for i, job in enumerate(img_jobs, 1):
                print(f"🖼️  Image Job {i}/{len(img_jobs)}: {job.command}")
                timeout = parameters.get('timeout', 86400)
                self.agent._execute_image_job(job, timeout)
            
            # Success!
            self.queue_manager.update_batch_status(batch_id, "completed")
            print(f"\n✅ BATCH COMPLETED: {batch_id}")
            return True
            
        except Exception as e:
            # Error handling
            error_msg = str(e)
            print(f"\n❌ BATCH FAILED: {batch_id}")
            print(f"🔴 Error: {error_msg}")
            
            # Provide GPU memory guidance for LLM failures
            if "memory" in error_msg.lower() or "cuda" in error_msg.lower():
                print(f"\n💡 GPU Memory Guidance:")
                print(f"   • ComfyUI typically uses 7-10GB VRAM")
                print(f"   • LLM typically uses 6-8GB VRAM")
                print(f"   • Your RTX 4070 Ti SUPER has 16GB total")
                print(f"   • Try: --force-now --no-queue to bypass coordination")
            
            self.queue_manager.update_batch_status(batch_id, "failed", error_msg)
            return False
            
        finally:
            self.current_batch_id = None
            self.agent._cleanup()
    
    def _setup_agent_for_batch(self, batch: Dict[str, Any]):
        """Setup GPU agent for batch execution"""
        import os
        import glob
        
        command = batch['command']
        parameters = batch['parameters'].copy()  # Make a copy to avoid modifying original
        
        # Convert preset dict back to ModelPreset object
        if 'preset' in parameters and isinstance(parameters['preset'], dict):
            preset_dict = parameters['preset']
            preset = ModelPreset(
                name=preset_dict['name'],
                llama_cli=preset_dict['llama_cli'],
                model_path=preset_dict['model_path'],
                ctx=preset_dict['ctx'],
                ngl=preset_dict['ngl'],
                top_p=preset_dict['top_p']
            )
            parameters['preset'] = preset
        
        # Ensure output directory is computed and exists
        try:
            proj_dir = resolve_project_dir(batch['project'])
        except Exception:
            proj_dir = None
        
        if proj_dir:
            # Determine default subdir per command
            default_subdir = (
                parameters.get('out_subdir')
                if command == 'explore_narrative' else
                ('style_explore' if command == 'explore_styles' else 'style_refine')
            )
            out_subdir = parameters.get('out_subdir', default_subdir)
            output_dir_abs = os.path.join(proj_dir, out_subdir)
            os.makedirs(output_dir_abs, exist_ok=True)
            # ComfyUI is started with output-directory set to /home/mitchellflautt/MuseVision/projects
            comfy_root = '/home/mitchellflautt/MuseVision/projects'
            try:
                rel_output = os.path.relpath(output_dir_abs, comfy_root)
            except Exception:
                rel_output = out_subdir
            # Only set if missing or empty
            if not parameters.get('output_dir'):
                parameters['output_dir'] = rel_output
        
        # Auto-discover selected_images for narrative if not provided
        if command == 'explore_narrative' and not parameters.get('selected_images') and proj_dir:
            selected_images_dir = os.path.join(proj_dir, 'selected_images')
            os.makedirs(selected_images_dir, exist_ok=True)
            image_patterns = ['*.png', '*.jpg', '*.jpeg']
            selected_images = []
            for pattern in image_patterns:
                selected_images.extend(glob.glob(os.path.join(selected_images_dir, pattern)))
            if selected_images:
                parameters['selected_images'] = selected_images
        
        # Clear any existing jobs
        self.agent.job_batch.clear()
        
        # Add LLM generation job
        self.agent.add_job('llm_generation', command, **parameters)
        
        # Add image generation job  
        self.agent.add_job('image_generation', command, **parameters)
    
    def process_queue(self, max_batches: Optional[int] = None) -> int:
        """Process batches in the queue sequentially"""
        if not self.acquire_coordinator_lock():
            print("⚠️  Another coordinator is already running")
            return 0
        
        try:
            print("🎯 BATCH COORDINATOR STARTED")
            print("="*50)
            
            processed_count = 0
            
            while max_batches is None or processed_count < max_batches:
                # Get next batch
                next_batch = self.queue_manager.get_next_pending_batch()
                
                if next_batch is None:
                    print("📭 No more pending batches in queue")
                    break
                
                # Execute the batch
                success = self.execute_batch(next_batch)
                processed_count += 1
                
                if not success:
                    print(f"⚠️  Batch failed, continuing with next batch...")
                
                # Small delay between batches
                time.sleep(2)
            
            print(f"\n🎉 COORDINATOR FINISHED")
            print(f"   📊 Processed: {processed_count} batches")
            
            return processed_count
            
        except KeyboardInterrupt:
            print(f"\n⚠️  Coordinator interrupted by user")
            if self.current_batch_id:
                self.queue_manager.update_batch_status(
                    self.current_batch_id, "failed", "Interrupted by user"
                )
            return processed_count
            
        except Exception as e:
            print(f"\n❌ Coordinator error: {e}")
            if self.current_batch_id:
                self.queue_manager.update_batch_status(
                    self.current_batch_id, "failed", f"Coordinator error: {e}"
                )
            raise
            
        finally:
            self.release_coordinator_lock()
    
    def _aggressive_comfyui_cleanup(self):
        """Aggressively clean up ComfyUI processes to free GPU memory"""
        import subprocess
        import psutil
        
        # Find all Python processes that might be ComfyUI
        comfyui_pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                if cmdline:
                    cmdline_str = ' '.join(cmdline).lower()
                    # Look for ComfyUI-related processes
                    if ('main.py' in cmdline_str and 
                        ('comfyui' in cmdline_str or '--listen' in cmdline_str or '--port' in cmdline_str)):
                        comfyui_pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        if comfyui_pids:
            print(f"   🔍 Found {len(comfyui_pids)} ComfyUI process(es): {comfyui_pids}")
            for pid in comfyui_pids:
                try:
                    print(f"   💀 Terminating ComfyUI process {pid}...")
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)  # Give it a moment to terminate gracefully
                    
                    # Check if still running, then force kill
                    try:
                        os.kill(pid, 0)  # Check if process exists
                        print(f"   🔨 Force killing stubborn process {pid}...")
                        os.kill(pid, signal.SIGKILL)
                    except OSError:
                        print(f"   ✅ Process {pid} terminated")
                        
                except OSError as e:
                    print(f"   ⚠️  Failed to kill process {pid}: {e}")
        else:
            print("   ✅ No ComfyUI processes found")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}h:{minutes:02d}m:{secs:02d}s"


def main():
    """Main entry point for batch coordinator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MuseVision Batch Coordinator")
    parser.add_argument('--max-batches', type=int, help='Maximum number of batches to process')
    parser.add_argument('--queue-path', help='Custom queue file path')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (restart when queue has items)')
    parser.add_argument('--check-interval', type=int, default=60, help='Check interval for daemon mode (seconds)')
    
    args = parser.parse_args()
    
    coordinator = BatchCoordinator(args.queue_path)
    
    if args.daemon:
        print("🔄 Starting coordinator in daemon mode...")
        print(f"   🕐 Check interval: {args.check_interval} seconds")
        print("   💡 Use Ctrl+C to stop")
        
        try:
            while True:
                # Check if there are pending batches
                status = coordinator.queue_manager.get_queue_status()
                
                if status.get('pending', 0) > 0:
                    print(f"\n📋 Found {status['pending']} pending batch(es), starting processing...")
                    processed = coordinator.process_queue(args.max_batches)
                    print(f"✅ Processed {processed} batches")
                
                time.sleep(args.check_interval)
                
        except KeyboardInterrupt:
            print("\n👋 Daemon stopped by user")
    
    else:
        # One-time processing
        processed = coordinator.process_queue(args.max_batches)
        print(f"✅ Processed {processed} batches")


if __name__ == "__main__":
    main()
