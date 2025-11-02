#!/usr/bin/env python3
"""
ComfyUI Process Manager - GPU Resource Optimization

Manages ComfyUI lifecycle to optimize GPU usage:
1. Detects running ComfyUI instances
2. Starts/stops ComfyUI with proper configuration
3. Handles graceful shutdown
4. Batches operations to minimize GPU switching
"""

import os
import sys
import time
import subprocess
import psutil
import signal
import requests
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class ComfyUIConfig:
    """Configuration for ComfyUI startup"""
    main_py_path: str = "/home/mitchellflautt/MuseVision/ComfyUI/main.py"
    output_directory: str = "../projects"
    host: str = "127.0.0.1"
    port: int = 8188
    api_url: str = "http://127.0.0.1:8188"
    
    # GPU optimization settings
    lowvram: bool = False  # Use if GPU memory conflicts occur
    cpu_only: bool = False  # Fallback option
    
    # Logging
    log_file: str = os.path.expanduser("~/.musevision_comfyui.log")
    
class ComfyUIManager:
    """Manages ComfyUI process lifecycle for GPU optimization"""
    
    def __init__(self, config: Optional[ComfyUIConfig] = None):
        self.config = config or ComfyUIConfig()
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self._log_handle = None
        
    def is_running(self) -> bool:
        """Check if ComfyUI is already running"""
        # First try to find ComfyUI processes
        comfyui_pids = self._find_comfyui_processes()
        if comfyui_pids:
            self.pid = comfyui_pids[0]  # Use the first one found
            # Also check API availability
            try:
                response = requests.get(f"{self.config.api_url}/system_stats", timeout=2)
                return response.status_code == 200
            except:
                # Process exists but API not responding - still considered running
                return True
        
        return False
    
    def _find_comfyui_processes(self) -> List[int]:
        """Find all ComfyUI process PIDs"""
        pids = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                # Look for ComfyUI main.py processes - improved detection
                cmdline_str = ' '.join(str(arg) for arg in cmdline)
                if ('main.py' in cmdline_str and 
                    ('ComfyUI' in cmdline_str or 'comfyui' in cmdline_str.lower() or
                     '--listen' in cmdline_str)):
                    pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return pids
    
    def start(self, wait_for_ready: bool = True, timeout: int = 300) -> bool:
        """Start ComfyUI if not already running"""
        if self.is_running():
            print("🎨 ComfyUI already running")
            return True
        
        print("🚀 Starting ComfyUI...")
        
        # Build command
        cmd = [
            sys.executable, self.config.main_py_path,
            "--output-directory", self.config.output_directory,
            "--listen", self.config.host,
            "--port", str(self.config.port)
        ]
        
        # Add GPU optimization flags if needed
        if self.config.lowvram:
            cmd.append("--lowvram")
        if self.config.cpu_only:
            cmd.append("--cpu")
        
        try:
            # Prepare logging: append to log file to avoid PIPE deadlocks
            os.makedirs(os.path.dirname(self.config.log_file), exist_ok=True)
            self._log_handle = open(self.config.log_file, 'a', buffering=1)
            self._log_handle.write("\n===== ComfyUI start =====\n")
            self._log_handle.flush()

            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=self._log_handle,
                stderr=self._log_handle,
                text=True,
                cwd=os.path.dirname(self.config.main_py_path)
            )
            self.pid = self.process.pid
            print(f"📋 ComfyUI started (PID: {self.pid}) - logging to {self.config.log_file}")
            
            if wait_for_ready:
                if self._wait_for_ready(timeout):
                    print("✅ ComfyUI ready for connections")
                    return True
                else:
                    print("❌ ComfyUI failed to start within timeout")
                    self.stop()
                    return False
            return True
            
        except Exception as e:
            print(f"❌ Failed to start ComfyUI: {e}")
            return False
    
    def stop(self, force: bool = False, timeout: int = 30) -> bool:
        """Stop ComfyUI gracefully - finds and stops all ComfyUI processes"""
        # Find all ComfyUI processes first
        comfyui_pids = self._find_comfyui_processes()
        
        if not comfyui_pids:
            print("🛑 ComfyUI not running")
            return True
        
        print(f"🛑 Stopping ComfyUI (found {len(comfyui_pids)} process(es): {comfyui_pids})...")
        
        stopped_pids = []
        failed_pids = []
        
        for pid in comfyui_pids:
            try:
                # Try graceful shutdown first
                if not force:
                    print(f"   📤 Sending SIGTERM to PID {pid} (graceful shutdown)...")
                    os.kill(pid, signal.SIGTERM)
                    
                    # Wait a bit for graceful shutdown
                    for _ in range(timeout):
                        if not self._pid_exists(pid):
                            print(f"✅ ComfyUI PID {pid} stopped gracefully")
                            stopped_pids.append(pid)
                            break
                        time.sleep(1)
                    else:
                        print(f"⚠️  PID {pid} graceful shutdown timed out, forcing...")
                        force = True
                
                # Force stop if graceful didn't work
                if force and self._pid_exists(pid):
                    print(f"   💀 Sending SIGKILL to PID {pid} (force stop)...")
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(1)
                    
                    if not self._pid_exists(pid):
                        print(f"✅ ComfyUI PID {pid} force stopped")
                        stopped_pids.append(pid)
                    else:
                        print(f"❌ Failed to stop PID {pid}")
                        failed_pids.append(pid)
                        
            except ProcessLookupError:
                print(f"✅ ComfyUI PID {pid} already stopped")
                stopped_pids.append(pid)
            except Exception as e:
                print(f"❌ Error stopping ComfyUI PID {pid}: {e}")
                failed_pids.append(pid)
        
        # Final cleanup
        self.process = None
        self.pid = None
        
        # Close log handle if open
        try:
            if self._log_handle:
                self._log_handle.write("\n===== ComfyUI stop =====\n")
                self._log_handle.flush()
                self._log_handle.close()
        except Exception:
            pass
        finally:
            self._log_handle = None
        
        success = len(failed_pids) == 0
        if success:
            print(f"✅ All ComfyUI processes stopped successfully ({len(stopped_pids)} total)")
        else:
            print(f"⚠️  Stopped {len(stopped_pids)}/{len(comfyui_pids)} ComfyUI processes. Failed: {failed_pids}")
        
        return success
    
    def restart(self, timeout: int = 300) -> bool:
        """Restart ComfyUI"""
        print("🔄 Restarting ComfyUI...")
        if not self.stop():
            return False
        time.sleep(2)
        return self.start(wait_for_ready=True, timeout=timeout)
    
    def _wait_for_ready(self, timeout: int) -> bool:
        """Wait for ComfyUI API to be ready"""
        start_time = time.time()
        last_status_time = start_time
        
        print(f"   ⏳ Waiting up to {timeout} seconds for ComfyUI to start...")
        
        while time.time() - start_time < timeout:
            try:
                # Check both system_stats and queue endpoints to ensure full API readiness
                system_response = requests.get(f"{self.config.api_url}/system_stats", timeout=5)
                queue_response = requests.get(f"{self.config.api_url}/queue", timeout=5)
                
                if system_response.status_code == 200 and queue_response.status_code == 200:
                    # Extra verification: wait 2 more seconds to ensure stability
                    print("   🔍 ComfyUI API responding, verifying stability...")
                    time.sleep(2)
                    
                    # Final verification
                    final_check = requests.get(f"{self.config.api_url}/system_stats", timeout=5)
                    if final_check.status_code == 200:
                        return True
                    
            except:
                pass
            
            # Show progress every 15 seconds
            current_time = time.time()
            if current_time - last_status_time >= 15:
                elapsed = int(current_time - start_time)
                remaining = int(timeout - elapsed)
                print(f"   ⏳ Still waiting for ComfyUI... ({elapsed}s elapsed, {remaining}s remaining)")
                last_status_time = current_time
            
            time.sleep(2)
        
        return False
    
    def _pid_exists(self, pid: int) -> bool:
        """Check if PID exists"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed status information"""
        status = {
            'running': self.is_running(),
            'pid': self.pid,
            'api_accessible': False,
            'gpu_usage': None
        }
        
        if status['running']:
            try:
                response = requests.get(f"{self.config.api_url}/system_stats", timeout=2)
                if response.status_code == 200:
                    status['api_accessible'] = True
                    # Could extend to parse GPU info from response
            except:
                pass
        
        return status

class GPUOptimizedWorkflow:
    """Manages GPU-optimized workflow between LLM and ComfyUI"""
    
    def __init__(self, comfyui_manager: Optional[ComfyUIManager] = None):
        self.comfyui_manager = comfyui_manager or ComfyUIManager()
        self.job_queue: List[Dict[str, Any]] = []
        
    def add_job(self, job_type: str, **kwargs):
        """Add a job to the queue"""
        job = {
            'type': job_type,
            'params': kwargs,
            'id': len(self.job_queue)
        }
        self.job_queue.append(job)
        print(f"📋 Queued job {job['id']}: {job_type}")
    
    def execute_workflow(self, shutdown_comfyui_after: bool = True) -> bool:
        """Execute the full workflow with GPU optimization"""
        if not self.job_queue:
            print("📭 No jobs queued")
            return True
            
        print(f"🎯 Starting GPU-optimized workflow with {len(self.job_queue)} jobs")
        
        # Phase 1: LLM inference phase (ComfyUI minimal/stopped)
        print("\n🧠 Phase 1: LLM Inference")
        print("=" * 50)
        
        # Ensure ComfyUI is stopped for maximum GPU availability
        if self.comfyui_manager.is_running():
            print("⚠️  ComfyUI running - stopping for LLM inference...")
            if not self.comfyui_manager.stop():
                print("❌ Failed to stop ComfyUI")
                return False
        
        # Execute LLM jobs
        llm_jobs = [job for job in self.job_queue if job['type'] in ['llm_generation', 'dream_prompts']]
        for job in llm_jobs:
            print(f"🔮 Executing LLM job {job['id']}...")
            # LLM execution will be handled by the calling code
            
        # Phase 2: Image generation phase
        print(f"\n🎨 Phase 2: Image Generation")
        print("=" * 50)
        
        # Start ComfyUI for image generation
        if not self.comfyui_manager.start():
            print("❌ Failed to start ComfyUI")
            return False
        
        # Execute ComfyUI jobs
        comfyui_jobs = [job for job in self.job_queue if job['type'] in ['image_generation', 'comfyui_job']]
        for job in comfyui_jobs:
            print(f"🖼️  Executing ComfyUI job {job['id']}...")
            # ComfyUI execution will be handled by the calling code
        
        # Phase 3: Cleanup
        if shutdown_comfyui_after:
            print(f"\n🧹 Phase 3: Cleanup")
            print("=" * 30)
            print("🛑 Shutting down ComfyUI...")
            self.comfyui_manager.stop()
        
        # Clear completed jobs
        self.job_queue.clear()
        print("✅ Workflow completed successfully")
        return True

def main():
    """Test the ComfyUI manager"""
    print("🧪 Testing ComfyUI Manager")
    print("=" * 40)
    
    manager = ComfyUIManager()
    
    # Show current status
    status = manager.get_status()
    print(f"📊 Current status: {status}")
    
    # Test start/stop cycle
    if not status['running']:
        print("\n🚀 Testing ComfyUI startup...")
        if manager.start():
            print("✅ Startup successful")
            time.sleep(3)
            
            print("\n🛑 Testing ComfyUI shutdown...")
            if manager.stop():
                print("✅ Shutdown successful")
            else:
                print("❌ Shutdown failed")
        else:
            print("❌ Startup failed")
    else:
        print("ComfyUI already running - stopping to test")
        manager.stop()

if __name__ == "__main__":
    main()
