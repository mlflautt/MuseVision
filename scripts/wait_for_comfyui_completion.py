#!/usr/bin/env python3
"""
Utility to wait for ComfyUI jobs to complete.
This script monitors the ComfyUI API queue and history to detect when jobs are finished.
"""

import os
import sys
import time
import json
import argparse
import requests
from typing import Dict, List, Set, Optional, Any, Tuple

class ComfyUIMonitor:
    """Monitors ComfyUI job queue and waits for jobs to complete"""
    
    def __init__(self, api_url: str = "http://127.0.0.1:8188"):
        self.api_url = api_url
        self.job_ids: List[str] = []
        self.job_lookup: Dict[str, Dict] = {}
        self.completed_jobs: Dict[str, Dict] = {}
    
    def add_job(self, job_id: str, prompt_idx: int, prompt_preview: str):
        """Add a job to be monitored"""
        self.job_ids.append(job_id)
        self.job_lookup[job_id] = {
            'submit_time': time.time(),
            'prompt_idx': prompt_idx,
            'prompt_preview': prompt_preview[:30] + "..." if len(prompt_preview) > 30 else prompt_preview
        }
    
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to a human-readable string"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)}m {int(seconds % 60)}s"
        hours = minutes / 60
        return f"{int(hours)}h {int(minutes % 60)}m"
    
    def _get_job_index_info(self, job_info: Dict) -> Tuple[str, Any]:
        """Get the job index information for display"""
        index_name = "prompt"
        index_value = job_info.get('prompt_idx', '?')
        return index_name, index_value
    
    def wait_for_completion(self, timeout: int = 7200, max_consecutive_errors: int = 5) -> bool:
        """
        Wait for all monitored jobs to complete
        
        Args:
            timeout: Maximum time to wait in seconds (default: 2 hours)
            max_consecutive_errors: Maximum number of consecutive API errors before aborting
            
        Returns:
            True if all jobs completed successfully, False otherwise
        """
        if not self.job_ids:
            print("No jobs to monitor")
            return True
        
        print(f"⏳ Monitoring {len(self.job_ids)} ComfyUI jobs")
        
        start_time = time.time()
        consecutive_errors = 0
        last_active_time = start_time
        
        while time.time() - start_time < timeout and len(self.completed_jobs) < len(self.job_ids):
            try:
                # Check queue status
                response = requests.get(f"{self.api_url}/queue", timeout=10)
                if response.status_code == 200:
                    consecutive_errors = 0
                    queue_info = response.json()
                    
                    # Get currently executing and pending job IDs
                    executing_items = queue_info.get('queue_running', [])
                    pending_items = queue_info.get('queue_pending', [])
                    
                    executing_ids = {item[1] for item in executing_items}
                    pending_ids = {item[1] for item in pending_items}
                    active_ids = executing_ids | pending_ids
                    
                    # Queue status debug output removed - was too verbose
                    
                    # Check history API for completed jobs
                    try:
                        history_response = requests.get(f"{self.api_url}/history", timeout=5)
                        history_data = history_response.json() if history_response.status_code == 200 else {}
                    except:
                        history_data = {}
                    
                    # Check for newly completed jobs (in history or disappeared from queue)
                    newly_completed = []
                    for job_id in self.job_ids:
                        if job_id not in self.completed_jobs:
                            # Check if job is in history (definitively completed)
                            if job_id in history_data:
                                completion_time = time.time()
                                job_duration = completion_time - self.job_lookup[job_id]['submit_time']
                                self.completed_jobs[job_id] = {
                                    'completion_time': completion_time,
                                    'duration': job_duration,
                                    'status': 'completed_in_history'
                                }
                                newly_completed.append((job_id, job_duration))
                            # Also check if it disappeared from queue (legacy detection)
                            elif job_id not in active_ids:
                                completion_time = time.time()
                                job_duration = completion_time - self.job_lookup[job_id]['submit_time']
                                self.completed_jobs[job_id] = {
                                    'completion_time': completion_time,
                                    'duration': job_duration,
                                    'status': 'disappeared_from_queue'
                                }
                                newly_completed.append((job_id, job_duration))
                    
                    # Report newly completed jobs with timing
                    for job_id, duration in newly_completed:
                        job_info = self.job_lookup[job_id]
                        index_name, index_value = self._get_job_index_info(job_info)
                        print(f"✅ Job {job_id[:8]} completed in {duration:.1f}s - Prompt {job_info['prompt_idx']}: {job_info['prompt_preview']} ({len(self.completed_jobs)}/{len(self.job_ids)})")
                        last_active_time = time.time()
                    
                    # Check for stuck jobs (no progress for too long)
                    if time.time() - last_active_time > 600:  # 10 minutes with no completed jobs
                        print(f"⚠️  No jobs completed in 10+ minutes. Checking queue health...")
                        
                        # Get current history to check for missing jobs
                        try:
                            history_response = requests.get(f"{self.api_url}/history", timeout=5)
                            current_history = history_response.json() if history_response.status_code == 200 else {}
                        except:
                            current_history = {}
                        
                        # Check if any of our jobs are still in the queue
                        our_active_jobs = [jid for jid in self.job_ids if jid in active_ids]
                        jobs_in_history = [jid for jid in self.job_ids if jid in current_history]
                        missing_jobs = [jid for jid in self.job_ids if jid not in active_ids and jid not in self.completed_jobs and jid not in current_history]
                        
                        print(f"📋 Status breakdown:")
                        print(f"   ✅ Completed: {len(self.completed_jobs)}/{len(self.job_ids)}")
                        print(f"   💹 Still active: {len(our_active_jobs)} ({[j[:8] + '...' for j in our_active_jobs[:3]]})")
                        print(f"   📋 In history: {len(jobs_in_history)} jobs")
                        print(f"   ❌ Missing: {len(missing_jobs)} jobs")
                        
                        if not executing_ids and not pending_ids:
                            print("❌ ComfyUI queue appears completely empty")
                            if missing_jobs:
                                print(f"🔴 {len(missing_jobs)} jobs disappeared without completing - likely ComfyUI issue")
                                print(f"Missing job IDs: {[j[:8] + '...' for j in missing_jobs[:5]]}")
                            break
                        else:
                            # Try gently interrupting the current job once to unstick the worker
                            try:
                                print("🛎️ Attempting to interrupt current ComfyUI job (POST /interrupt)...")
                                requests.post(f"{self.api_url}/interrupt", timeout=5)
                            except Exception as _e:
                                print(f"⚠️  Interrupt request failed: {_e}")
                            
                            last_active_time = time.time()  # Reset timer if queue is active
                    
                    # Only show periodic status if we have pending jobs (not every loop)
                    remaining = len(self.job_ids) - len(self.completed_jobs)
                    if remaining > 0 and newly_completed:  # Only show when jobs complete
                        elapsed = time.time() - start_time
                        avg_time = elapsed / len(self.completed_jobs) if self.completed_jobs else 0
                        est_remaining = avg_time * remaining if avg_time > 0 else 0
                        print(f"📈 Status: {remaining} remaining, {self._format_time(elapsed)} elapsed, ~{self._format_time(est_remaining)} estimated")
                    
                    time.sleep(10)  # Check every 10 seconds
                    
                else:
                    consecutive_errors += 1
                    print(f"⚠️  Queue status HTTP {response.status_code} (error {consecutive_errors}/{max_consecutive_errors})")
                    if consecutive_errors >= max_consecutive_errors:
                        print("❌ Too many consecutive API errors - ComfyUI may have crashed")
                        break
                    time.sleep(15)
                    
            except requests.RequestException as e:
                consecutive_errors += 1
                print(f"⚠️  Queue check error (#{consecutive_errors}): {e}")
                if consecutive_errors >= max_consecutive_errors:
                    print("❌ Too many consecutive connection errors - ComfyUI may be down")
                    break
                time.sleep(15)
        
        # Final summary
        total_time = time.time() - start_time
        if len(self.completed_jobs) == len(self.job_ids):
            avg_job_time = total_time / len(self.job_ids)  # Fixed: total time divided by job count
            print(f"\n🎉 All {len(self.job_ids)} jobs completed successfully!")
            print(f"   ⏱️ Total time: {self._format_time(total_time)}")
            print(f"   📊 Average per job: {self._format_time(avg_job_time)}")
            return True
        else:
            print(f"\n⚠️  Incomplete: {len(self.completed_jobs)}/{len(self.job_ids)} jobs finished in {self._format_time(total_time)}")
            if consecutive_errors >= max_consecutive_errors:
                print("🔴 Stopped due to ComfyUI connection issues")
            else:
                print("⏰ Stopped due to timeout")
            return False

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Wait for ComfyUI jobs to complete")
    parser.add_argument("--job-ids", nargs="+", required=True, help="Job IDs to monitor")
    parser.add_argument("--api-url", default="http://127.0.0.1:8188", help="ComfyUI API URL")
    parser.add_argument("--timeout", type=int, default=7200, help="Maximum time to wait in seconds (default: 2 hours)")
    args = parser.parse_args()
    
    monitor = ComfyUIMonitor(args.api_url)
    for i, job_id in enumerate(args.job_ids):
        monitor.add_job(job_id, i+1, f"Job {i+1}")
    
    success = monitor.wait_for_completion(args.timeout)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
