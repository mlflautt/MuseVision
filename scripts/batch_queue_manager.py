#!/usr/bin/env python3
"""
MuseVision Batch Queue Manager

Manages persistent batch queue for sequential GPU resource coordination.
Handles queue persistence, file locking, and batch lifecycle management.
"""

import json
import os
import time
import fcntl
import tempfile
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Optional at runtime; used to query ComfyUI queue for live counts
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None


@dataclass
class BatchInfo:
    """Information about a queued batch"""
    id: str
    command: str
    project: str
    status: str
    created: str
    estimated_duration: float
    parameters: Dict[str, Any]
    full_command: str
    started: Optional[str] = None
    completed: Optional[str] = None
    error_message: Optional[str] = None


class BatchQueueManager:
    """Manages persistent batch queue with file locking"""
    
    def __init__(self, queue_path: Optional[str] = None):
        """Initialize queue manager with optional custom path"""
        self.queue_path = queue_path or self._get_default_queue_path()
        self.lock_path = self.queue_path + ".lock"
        self._ensure_queue_file_exists()
    
    def _get_default_queue_path(self) -> str:
        """Get default queue file path from environment or home directory"""
        default_path = os.path.expanduser("~/.musevision_batch_queue.json")
        return os.environ.get("MUSEVISION_QUEUE_PATH", default_path)
    
    def _ensure_queue_file_exists(self):
        """Create queue file if it doesn't exist"""
        if not os.path.exists(self.queue_path):
            empty_queue = {
                "queue_version": "1.0",
                "created": datetime.now(timezone.utc).isoformat(),
                "batches": []
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.queue_path), exist_ok=True)
            
            # Write empty queue atomically
            self._write_queue_atomic(empty_queue)
    
    def _write_queue_atomic(self, queue_data: Dict[str, Any]):
        """Write queue data atomically using temporary file"""
        temp_path = self.queue_path + ".tmp"
        try:
            with open(temp_path, 'w') as f:
                json.dump(queue_data, f, indent=2)
            shutil.move(temp_path, self.queue_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    
    def _acquire_lock(self, timeout: float = 300.0) -> bool:
        """Acquire exclusive file lock with timeout"""
        try:
            self.lock_file = open(self.lock_path, 'w')
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    # Write PID for debugging
                    self.lock_file.write(f"{os.getpid()}\n{datetime.now(timezone.utc).isoformat()}\n")
                    self.lock_file.flush()
                    return True
                except BlockingIOError:
                    time.sleep(0.1)
            
            return False
        except Exception as e:
            print(f"⚠️  Failed to acquire lock: {e}")
            return False
    
    def _release_lock(self):
        """Release file lock"""
        try:
            if hasattr(self, 'lock_file') and self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                if os.path.exists(self.lock_path):
                    os.unlink(self.lock_path)
        except Exception as e:
            print(f"⚠️  Warning: Failed to release lock cleanly: {e}")
    
    def _load_queue(self) -> Dict[str, Any]:
        """Load queue from file"""
        try:
            with open(self.queue_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️  Queue file corrupted, creating new: {e}")
            empty_queue = {
                "queue_version": "1.0", 
                "created": datetime.now(timezone.utc).isoformat(),
                "batches": []
            }
            self._write_queue_atomic(empty_queue)
            return empty_queue
    
    def _generate_batch_id(self, command: str, project: str) -> str:
        """Generate unique batch ID based on timestamp, command, and project"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize project name for filename safety
        safe_project = "".join(c for c in project if c.isalnum() or c in "_-")[:20]
        return f"{timestamp}_{command}_{safe_project}"
    
    def _estimate_total_images(self, command: str, parameters: Dict[str, Any], project: Optional[str] = None) -> int:
        """Estimate total number of images/jobs for a batch based on parameters"""
        if command == "explore_styles":
            dream_count = parameters.get("dream_count", 5)
            n_variations = parameters.get("n", 10)
            return dream_count * n_variations
        elif command == "explore_narrative":
            dream_count = parameters.get("dream_count", 5)
            seed_count = parameters.get("seed_count", 1)
            img_mult = 1
            if parameters.get("per_image"):
                sel = parameters.get("selected_images") or []
                if sel:
                    img_mult = len(sel)
                else:
                    # Try to auto-discover from projects/<project>/selected_images
                    try:
                        projects_root = "/home/mitchellflautt/MuseVision/projects"
                        if project:
                            import os
                            from glob import glob
                            sel_dir = os.path.join(projects_root, project, 'selected_images')
                            if os.path.isdir(sel_dir):
                                cnt = len([p for p in glob(os.path.join(sel_dir, '*')) if p.lower().endswith(('.png','.jpg','.jpeg'))])
                                if cnt > 0:
                                    img_mult = cnt
                    except Exception:
                        pass
            return dream_count * seed_count * img_mult
        elif command == "refine_styles":
            dream_count = parameters.get("dream_count", 5)
            test_count = parameters.get("test_count", 10)
            return dream_count * test_count
        else:
            return 10  # fallback
    
    def _estimate_batch_duration(self, command: str, parameters: Dict[str, Any], project: Optional[str] = None) -> float:
        """Estimate batch duration in seconds based on parameters"""
        base_times = {
            "explore_styles": 40.0,    # seconds per image
            "explore_narrative": 35.0,
            "refine_styles": 45.0
        }
        
        base_time = base_times.get(command, 40.0)
        total_images = self._estimate_total_images(command, parameters, project)
        
        # Add LLM processing time (~5-10 seconds per prompt)
        llm_time = parameters.get("dream_count", 5) * 7.5
        
        return (total_images * base_time) + llm_time
    
    def add_batch(self, command: str, project: str, parameters: Dict[str, Any], 
                  full_command: str, force: bool = False) -> str:
        """Add a new batch to the queue"""
        if not self._acquire_lock():
            raise RuntimeError("Could not acquire queue lock - another process may be running")
        
        try:
            queue_data = self._load_queue()
            
            batch_id = self._generate_batch_id(command, project)
            estimated_duration = self._estimate_batch_duration(command, parameters, project)
            
            batch = BatchInfo(
                id=batch_id,
                command=command,
                project=project,
                status="pending",
                created=datetime.now(timezone.utc).isoformat(),
                estimated_duration=estimated_duration,
                parameters=parameters,
                full_command=full_command
            )
            
            queue_data["batches"].append(asdict(batch))
            self._write_queue_atomic(queue_data)
            
            print(f"📋 Added batch to queue: {batch_id}")
            print(f"   🎯 Command: {command}")
            print(f"   📁 Project: {project}")
            print(f"   ⏱️ Estimated duration: {self._format_time(estimated_duration)}")
            
            return batch_id
            
        finally:
            self._release_lock()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        if not self._acquire_lock():
            return {"error": "Could not acquire lock", "batches": [], "total_estimated_time": 0}
        
        try:
            queue_data = self._load_queue()
            batches = queue_data.get("batches", [])
            
            # Calculate totals
            pending_batches = [b for b in batches if b["status"] == "pending"]
            processing_batches = [b for b in batches if b["status"].startswith("processing")]
            total_estimated_time = sum(b["estimated_duration"] for b in pending_batches)
            
            return {
                "total_batches": len(batches),
                "pending": len(pending_batches),
                "processing": len(processing_batches),
                "completed": len([b for b in batches if b["status"] == "completed"]),
                "failed": len([b for b in batches if b["status"] == "failed"]),
                "batches": batches,
                "total_estimated_time": total_estimated_time,
                "queue_file": self.queue_path
            }
        finally:
            self._release_lock()
    
    def remove_batch(self, batch_id: str) -> bool:
        """Remove a batch from the queue"""
        if not self._acquire_lock():
            print("⚠️  Could not acquire queue lock")
            return False
        
        try:
            queue_data = self._load_queue()
            batches = queue_data["batches"]
            
            # Find and remove batch
            original_length = len(batches)
            queue_data["batches"] = [b for b in batches if b["id"] != batch_id]
            
            if len(queue_data["batches"]) < original_length:
                self._write_queue_atomic(queue_data)
                print(f"✅ Removed batch: {batch_id}")
                return True
            else:
                print(f"⚠️  Batch not found: {batch_id}")
                return False
        finally:
            self._release_lock()
    
    def clear_queue(self, status_filter: Optional[str] = None) -> int:
        """Clear queue (optionally filter by status)"""
        if not self._acquire_lock():
            print("⚠️  Could not acquire queue lock")
            return 0
        
        try:
            queue_data = self._load_queue()
            original_count = len(queue_data["batches"])
            
            if status_filter:
                # Remove only batches with specific status
                queue_data["batches"] = [
                    b for b in queue_data["batches"] 
                    if b["status"] != status_filter
                ]
                removed_count = original_count - len(queue_data["batches"])
                print(f"✅ Removed {removed_count} batches with status '{status_filter}'")
            else:
                # Clear entire queue
                queue_data["batches"] = []
                removed_count = original_count
                print(f"✅ Cleared entire queue ({removed_count} batches)")
            
            self._write_queue_atomic(queue_data)
            return removed_count
        finally:
            self._release_lock()
    
    def update_batch_status(self, batch_id: str, status: str, 
                          error_message: Optional[str] = None) -> bool:
        """Update batch status"""
        if not self._acquire_lock():
            return False
        
        try:
            queue_data = self._load_queue()
            
            for batch in queue_data["batches"]:
                if batch["id"] == batch_id:
                    batch["status"] = status
                    if status.startswith("processing") and not batch.get("started"):
                        batch["started"] = datetime.now(timezone.utc).isoformat()
                    elif status in ["completed", "failed"]:
                        batch["completed"] = datetime.now(timezone.utc).isoformat()
                    
                    if error_message:
                        batch["error_message"] = error_message
                    
                    self._write_queue_atomic(queue_data)
                    return True
            
            return False
        finally:
            self._release_lock()
    
    def get_next_pending_batch(self) -> Optional[Dict[str, Any]]:
        """Get the next pending batch for processing"""
        if not self._acquire_lock():
            return None
        
        try:
            queue_data = self._load_queue()
            
            for batch in queue_data["batches"]:
                if batch["status"] == "pending":
                    return batch
            
            return None
        finally:
            self._release_lock()
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}h:{minutes:02d}m:{secs:02d}s"
    
    def print_queue_status(self):
        """Print formatted queue status"""
        status = self.get_queue_status()
        
        if "error" in status:
            print(f"❌ {status['error']}")
            return
        
        total = status["total_batches"]
        pending = status["pending"]
        processing = status["processing"]
        completed = status["completed"]
        failed = status["failed"]
        
        print(f"\n📋 BATCH QUEUE STATUS")
        print(f"{'=' * 40}")
        print(f"📊 Total batches: {total}")
        print(f"⏳ Pending: {pending}")
        print(f"🔄 Processing: {processing}")
        print(f"✅ Completed: {completed}")
        print(f"❌ Failed: {failed}")
        
        if pending > 0:
            estimated_time = status["total_estimated_time"]
            print(f"⏰ Estimated completion time: {self._format_time(estimated_time)}")
        
        print(f"📁 Queue file: {status['queue_file']}")
        
        # Show detailed batch list if there are active batches
        if pending > 0 or processing > 0:
            print(f"\n📝 ACTIVE BATCHES:")

            # Try to fetch ComfyUI queue once for live counts
            comfy_queue = None
            if requests is not None:
                try:
                    r = requests.get("http://127.0.0.1:8188/queue", timeout=2)
                    if r.status_code == 200:
                        comfy_queue = r.json()
                except Exception:
                    comfy_queue = None

            for batch in status["batches"]:
                if batch["status"] in ["pending", "processing_llm", "processing_images"]:
                    status_icon = {
                        "pending": "⏳",
                        "processing_llm": "🧠", 
                        "processing_images": "🎨"
                    }.get(batch["status"], "❓")
                    
                    duration_str = self._format_time(batch["estimated_duration"])
                    try:
                        jobs_est = self._estimate_total_images(batch["command"], batch["parameters"], batch.get("project"))
                    except Exception:
                        jobs_est = None

                    # Live remaining (running+pending) for this batch from ComfyUI
                    live_suffix = ""
                    if comfy_queue and jobs_est:
                        try:
                            prefixes = []
                            project = batch.get("project")
                            params = batch.get("parameters", {})
                            # Decide subdir
                            if batch["command"] == "explore_styles":
                                subdir = "style_explore"
                            elif batch["command"] == "explore_narrative":
                                subdir = params.get("out_subdir", "narrative_explore")
                            elif batch["command"] == "refine_styles":
                                subdir = "style_refine"
                            else:
                                subdir = "outputs"
                            # Absolute and relative prefixes to match against SaveImage.filename_prefix
                            abs_root = f"/home/mitchellflautt/MuseVision/projects/{project}/{subdir}/"
                            rel_root = f"{project}/{subdir}/"
                            prefixes = [abs_root, rel_root]

                            def belongs_to_batch(item):
                                try:
                                    graph = item[2]
                                    for node_id, node in graph.items():
                                        if node.get('class_type') == 'SaveImage':
                                            fp = node.get('inputs', {}).get('filename_prefix', '')
                                            if any(str(fp).startswith(p) for p in prefixes):
                                                return True
                                except Exception:
                                    return False
                                return False

                            qrun = [it for it in comfy_queue.get('queue_running', []) if belongs_to_batch(it)]
                            qpend = [it for it in comfy_queue.get('queue_pending', []) if belongs_to_batch(it)]
                            remaining = len(qrun) + len(qpend)

                            # Rough ETA based on completed count and elapsed
                            started = batch.get("started")
                            if started:
                                try:
                                    dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                                    elapsed = (datetime.now(timezone.utc) - dt).total_seconds()
                                except Exception:
                                    elapsed = None
                            else:
                                elapsed = None

                            completed = jobs_est - remaining if jobs_est is not None else None
                            if elapsed is not None and completed and completed > 0:
                                avg = elapsed / completed
                            else:
                                # Fallback to a base image time
                                base_times = {"explore_styles": 40.0, "explore_narrative": 35.0, "refine_styles": 45.0}
                                avg = base_times.get(batch["command"], 40.0)
                            eta_secs = int(max(0, remaining) * avg)
                            live_suffix = f" | 🔁 {remaining} left | ⏳ ~{self._format_time(eta_secs)}"
                        except Exception:
                            live_suffix = ""

                    print(f"  {status_icon} {batch['id']}")
                    if jobs_est is not None:
                        print(f"     📁 {batch['project']} | 🎯 {batch['command']} | ⏱️ {duration_str} | 🧮 ≈{jobs_est} jobs{live_suffix}")
                    else:
                        print(f"     📁 {batch['project']} | 🎯 {batch['command']} | ⏱️ {duration_str}{live_suffix}")


def main():
    """Test the batch queue manager"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MuseVision Batch Queue Manager")
    subparsers = parser.add_subparsers(dest='action', help='Queue management actions')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show queue status')
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear queue')
    clear_parser.add_argument('--status-filter', help='Clear only batches with specific status')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove specific batch')
    remove_parser.add_argument('batch_id', help='Batch ID to remove')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Add test batch')
    test_parser.add_argument('--command', default='explore_styles', help='Command to test')
    test_parser.add_argument('--project', default='test_project', help='Project name')
    
    args = parser.parse_args()
    
    if not args.action:
        parser.print_help()
        return
    
    manager = BatchQueueManager()
    
    if args.action == 'status':
        manager.print_queue_status()
    
    elif args.action == 'clear':
        count = manager.clear_queue(args.status_filter)
        print(f"Cleared {count} batches from queue")
    
    elif args.action == 'remove':
        success = manager.remove_batch(args.batch_id)
        if not success:
            exit(1)
    
    elif args.action == 'test':
        # Add a test batch
        test_params = {
            "prompt": "test prompt",
            "dream_count": 3,
            "n": 5,
            "timeout": 86400
        }
        test_command = f"./scripts/gpu_optimized_agent.py {args.command} --project {args.project}"
        
        batch_id = manager.add_batch(
            command=args.command,
            project=args.project,
            parameters=test_params,
            full_command=test_command
        )
        print(f"Added test batch: {batch_id}")


if __name__ == "__main__":
    main()
