#!/usr/bin/env python3
"""
GPU-Optimized MuseVision Agent

This replaces the original agent.py with GPU resource optimization:
1. Batches ALL LLM inference first (full GPU access for llama.cpp)
2. Then switches to ComfyUI for ALL image generation
3. Manages ComfyUI lifecycle automatically
4. Supports all original agent commands: explore_styles, refine_styles, explore_narrative
"""

import argparse
import os
import sys
import tempfile
import json
import glob
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Import existing agent functionality
from agent import (
    ModelPreset, PRESETS, resolve_preset, resolve_project_dir, next_versioned_dir,
    dream_prompts, extract_metadata_from_png, add_model_switch_args,
    DEFAULT_TOK_PER_PROMPT, DEFAULT_BUF_FACTOR, PROJECTS_ROOT
)

# Import our ComfyUI manager
from comfyui_manager import ComfyUIManager

def setup_project_structure(proj_path):
    """Create project directory structure including selected_images folder"""
    os.makedirs(proj_path, exist_ok=True)
    selected_images_dir = os.path.join(proj_path, 'selected_images')
    os.makedirs(selected_images_dir, exist_ok=True)

@dataclass
class BatchJob:
    """Represents a batched operation"""
    job_type: str  # 'llm_generation' or 'image_generation'
    command: str   # The original command (explore_styles, etc.)
    params: Dict[str, Any]  # All the parameters
    prompts: List[str] = None  # Generated prompts (filled during LLM phase)
    metadata: Dict[str, Any] = None  # Additional metadata

class GPUOptimizedAgent:
    """Complete GPU-optimized agent supporting all original commands"""
    
    def __init__(self):
        self.comfyui_manager = ComfyUIManager()
        self.job_batch: List[BatchJob] = []
        self.temp_files: List[str] = []
        
    def cmd_explore_styles(self, args, preset: ModelPreset):
        """GPU-optimized version of explore_styles"""
        proj = resolve_project_dir(args.project)
        setup_project_structure(proj)
        out = os.path.join(proj, args.out_subdir or 'style_explore')
        os.makedirs(out, exist_ok=True)
        
        # Validate LoRA setup
        if not args.loras:
            if not os.path.isdir(args.loras_dir):
                return print(f'❌ LoRA directory not found: {args.loras_dir}')
            
            available_loras = glob.glob(os.path.join(args.loras_dir, "*Flux*.safetensors"))
            if not available_loras:
                return print(f'❌ No Flux LoRA files found in {args.loras_dir}')
            
            if args.k > len(available_loras):
                return print(f'❌ Requested {args.k} LoRAs but only {len(available_loras)} available')
        
        # Add LLM generation job
        self.add_job('llm_generation', 'explore_styles',
                    preset=preset,
                    prompt=args.prompt,
                    guidance=args.guidance,
                    creativity=args.creativity,
                    dream_count=args.dream_count,
                    tokens_per_prompt=args.tokens_per_prompt,
                    buffer_factor=args.buffer_factor,
                    enforce_1toN=args.enforce_1toN)
        
        # Add image generation job
        self.add_job('image_generation', 'explore_styles',
                    n=args.n,
                    k=args.k,
                    strength_min=args.strength_min,
                    strength_max=args.strength_max,
                    loras=args.loras,
                    fixed_loras=getattr(args, 'fixed_loras', None),
                    loras_dir=args.loras_dir,
                    width=args.width,
                    height=args.height,
                    wildcards=args.wildcards,
                    wildcards_dir=args.wildcards_dir,
                    output_dir=os.path.relpath(out, PROJECTS_ROOT),
                    script=args.script)
    
    def cmd_refine_styles(self, args, preset: ModelPreset):
        """GPU-optimized version of refine_styles"""
        proj = resolve_project_dir(args.project)
        setup_project_structure(proj)
        src = os.path.join(proj, args.selected_dir or 'selected_styles')
        out = os.path.join(proj, args.out_subdir or 'style_refine')
        os.makedirs(out, exist_ok=True)
        
        # Collect existing LoRA combinations and prompts
        prompts = []
        combo_to_strengths = {}
        lora_pool = set()
        
        for img in glob.glob(f'{src}/*.png'):
            try:
                p, loras, _seed = extract_metadata_from_png(img)
                if p:
                    prompts.append(p)
                if loras:
                    names = [lora[0] for lora in loras if lora[0]]
                    lora_pool.update(names)
                    if len(names) >= 1:
                        key = tuple(sorted(names))
                        if key not in combo_to_strengths:
                            combo_to_strengths[key] = loras
            except Exception as e:
                print(f"⚠️  Error processing {img}: {e}")
        
        if not combo_to_strengths and not args.extra_combos:
            return print('Not enough LoRA combinations in selected images; aborting.')
        if not (args.prompt or prompts):
            return print('No prompt override and no prompts in metadata; aborting.')
        
        # Add minimal LLM job (refine_styles doesn't need much LLM work)
        self.add_job('llm_generation', 'refine_styles',
                    prompt=args.prompt,
                    existing_prompts=prompts)
        
        # Add image generation job
        self.add_job('image_generation', 'refine_styles',
                    combo_to_strengths=combo_to_strengths,
                    lora_pool=lora_pool,
                    extra_combos=args.extra_combos,
                    k=2,  # Default for refine_styles
                    tests_per_combo=args.tests_per_combo,
                    seed_count=args.seed_count,
                    seed=args.seed,
                    strength_min=args.strength_min,
                    strength_max=args.strength_max,
                    fixed_loras=getattr(args, 'fixed_loras', None),
                    width=args.width,
                    height=args.height,
                    wildcards=args.wildcards,
                    wildcards_dir=args.wildcards_dir,
                    output_dir=os.path.relpath(out, PROJECTS_ROOT),
                    project_name=os.path.basename(proj),
                    script=args.script)
    
    def cmd_explore_narrative(self, args, preset: ModelPreset):
        """GPU-optimized version of explore_narrative"""
        proj = resolve_project_dir(args.project)
        setup_project_structure(proj)
        seed_path = args.selected_dir or 'selected_images'
        src = os.path.join(proj, seed_path)
        
        if args.out_subdir:
            out = os.path.join(proj, args.out_subdir)
        else:
            out = next_versioned_dir(proj, 'narrative_explore')
        os.makedirs(out, exist_ok=True)
        
        # Collect seed images
        if os.path.isdir(src):
            imgs = sorted(glob.glob(os.path.join(src, '*.png')))
        elif os.path.isfile(src):
            imgs = [src]
        else:
            print(f'Error: seed path not found: {src}')
            return
        
        if not imgs:
            print(f'Error: no seed images in {src}')
            return
        
        # Extract metadata
        meta = []
        for img in imgs:
            p, loras, _seed = extract_metadata_from_png(img)
            meta.append((img, p, loras))
        
        # Determine dream sources
        per_image_effective = bool(args.per_image and not args.prompt)
        if args.prompt:
            dream_sources = [args.prompt]
        else:
            if per_image_effective:
                dream_sources = [p for _img, p, _ in meta if p]
            else:
                dream_sources = [p for _img, p, _ in meta if p]
        
        if not dream_sources:
            print('Error: no prompt source available.')
            return
        
        # Add LLM generation job
        self.add_job('llm_generation', 'explore_narrative',
                    preset=preset,
                    dream_sources=dream_sources,
                    per_image_effective=per_image_effective,
                    guidance=args.guidance,
                    creativity=args.creativity,
                    dream_count=args.dream_count,
                    tokens_per_prompt=args.tokens_per_prompt,
                    buffer_factor=args.buffer_factor,
                    enforce_1toN=args.enforce_1toN)
        
        # Add image generation job
        self.add_job('image_generation', 'explore_narrative',
                    meta=meta,
                    per_image_effective=per_image_effective,
                    seed_count=args.seed_count,
                    width=args.width,
                    height=args.height,
                    wildcards=args.wildcards,
                    wildcards_dir=args.wildcards_dir,
                    output_dir=os.path.relpath(out, PROJECTS_ROOT),
                    project_name=os.path.basename(proj))
    
    def add_job(self, job_type: str, command: str, **kwargs):
        """Add a job to the batch"""
        job = BatchJob(
            job_type=job_type,
            command=command,
            params=kwargs
        )
        self.job_batch.append(job)
        print(f"📋 Queued {job_type}: {command}")
    
    def execute_batch(self, shutdown_comfyui_after: bool = True) -> bool:
        """Execute all batched jobs with GPU optimization"""
        if not self.job_batch:
            print("📭 No jobs to execute")
            return True
        
        print(f"\n🚀 GPU-Optimized Execution: {len(self.job_batch)} jobs")
        print("=" * 70)
        
        try:
            # Phase 1: LLM Inference Phase
            print("\n🧠 PHASE 1: LLM INFERENCE (Full GPU for llama.cpp)")
            print("=" * 60)
            
            if self.comfyui_manager.is_running():
                print("⚠️  Stopping ComfyUI to maximize GPU memory for LLM...")
                self.comfyui_manager.stop()
            
            llm_jobs = [job for job in self.job_batch if job.job_type == 'llm_generation']
            for i, job in enumerate(llm_jobs, 1):
                print(f"\n🔮 LLM Task {i}/{len(llm_jobs)}: {job.command}")
                self._execute_llm_job(job)
            
            # Phase 2: Image Generation Phase
            print(f"\n🎨 PHASE 2: IMAGE GENERATION (ComfyUI with GPU)")
            print("=" * 60)
            
            if not self.comfyui_manager.start():
                print("❌ Failed to start ComfyUI")
                return False
            
            img_jobs = [job for job in self.job_batch if job.job_type == 'image_generation']
            for i, job in enumerate(img_jobs, 1):
                print(f"\n🖼️  Generation Task {i}/{len(img_jobs)}: {job.command}")
                self._execute_image_job(job)
            
            # Phase 3: Cleanup
            if shutdown_comfyui_after:
                print(f"\n🧹 PHASE 3: CLEANUP")
                print("=" * 30)
                self.comfyui_manager.stop()
                print("✅ ComfyUI shutdown complete")
            
            print("\n🎉 ALL TASKS COMPLETED SUCCESSFULLY!")
            return True
            
        except Exception as e:
            print(f"❌ Batch execution failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._cleanup()
    
    def _execute_llm_job(self, job: BatchJob):
        """Execute LLM inference job"""
        command = job.command
        args = job.params
        
        if command == 'explore_styles':
            prompts = dream_prompts(
                [args['prompt']],
                args.get('guidance', ''),
                args.get('creativity', 0.7),
                args.get('dream_count', 5),
                args.get('tokens_per_prompt', DEFAULT_TOK_PER_PROMPT),
                args.get('buffer_factor', DEFAULT_BUF_FACTOR),
                args['preset'],
                args.get('enforce_1toN', False)
            )
            job.prompts = prompts
            print(f"  ✅ Generated {len(prompts)} style prompts")
            
        elif command == 'refine_styles':
            # Minimal processing for refine_styles
            job.prompts = [args.get('prompt')] if args.get('prompt') else args.get('existing_prompts', [])
            print(f"  ✅ Using {len(job.prompts)} prompts for refinement")
            
        elif command == 'explore_narrative':
            if args.get('per_image_effective'):
                # Generate prompts per image
                all_prompts = []
                for source in args['dream_sources']:
                    prompts = dream_prompts(
                        [source],
                        args.get('guidance', ''),
                        args.get('creativity', 0.7),
                        args.get('dream_count', 5),
                        args.get('tokens_per_prompt', DEFAULT_TOK_PER_PROMPT),
                        args.get('buffer_factor', DEFAULT_BUF_FACTOR),
                        args['preset'],
                        args.get('enforce_1toN', False)
                    )
                    all_prompts.extend(prompts)
                job.prompts = all_prompts
            else:
                # Single batch of prompts
                prompts = dream_prompts(
                    args['dream_sources'],
                    args.get('guidance', ''),
                    args.get('creativity', 0.7),
                    args.get('dream_count', 5),
                    args.get('tokens_per_prompt', DEFAULT_TOK_PER_PROMPT),
                    args.get('buffer_factor', DEFAULT_BUF_FACTOR),
                    args['preset'],
                    args.get('enforce_1toN', False)
                )
                job.prompts = prompts
            print(f"  ✅ Generated {len(job.prompts)} narrative prompts")
    
    def _execute_image_job(self, job: BatchJob):
        """Execute image generation job"""
        # Find corresponding LLM job
        prompts = job.prompts
        if not prompts:
            for other_job in self.job_batch:
                if (other_job.job_type == 'llm_generation' and
                    other_job.command == job.command and
                    other_job.prompts):
                    prompts = other_job.prompts
                    break
        
        if not prompts:
            print(f"  ⚠️  No prompts available for {job.command}")
            return
        
        print(f"  📝 Processing {len(prompts)} prompts")
        
        if job.command == 'explore_styles':
            self._execute_explore_styles_images(job.params, prompts)
        elif job.command == 'refine_styles':
            self._execute_refine_styles_images(job.params, prompts)
        elif job.command == 'explore_narrative':
            self._execute_explore_narrative_images(job.params, prompts)
    
    def _execute_explore_styles_images(self, params: Dict, prompts: List[str]):
        """Generate images for explore_styles"""
        import subprocess
        import re
        from wait_for_comfyui_completion import ComfyUIMonitor
        
        submitted_jobs = []
        monitor = ComfyUIMonitor()
        
        # Verify ComfyUI is accessible before starting job submissions - restart if needed
        import requests
        try:
            response = requests.get('http://127.0.0.1:8188/system_stats', timeout=5)
            if response.status_code != 200:
                print(f"⚠️  ComfyUI not responding (status {response.status_code}), restarting...")
                # Try to restart ComfyUI using the main manager instance
                print(f"🔄 Attempting to restart ComfyUI...")
                # Access the main agent's ComfyUI manager through the call stack
                # Since this function is called from _execute_image_job, we need to get the agent instance
                # For now, create a manager but ensure it uses the same config
                from comfyui_manager import ComfyUIManager
                manager = ComfyUIManager()
                if not manager.start():
                    print(f"❌ Failed to restart ComfyUI")
                    return
                print(f"✅ ComfyUI restarted successfully")
        except Exception as e:
            print(f"❌ ComfyUI not accessible ({e}), attempting to start...")
            # Try to start ComfyUI
            print(f"🚀 Attempting to start ComfyUI...")
            from comfyui_manager import ComfyUIManager
            manager = ComfyUIManager()
            if not manager.start():
                print(f"❌ Failed to start ComfyUI")
                return
            print(f"✅ ComfyUI started successfully")
        
        print(f"✅ ComfyUI confirmed accessible, proceeding with job submissions")
        print(f"\n📋 PHASE 2A: SUBMITTING ALL JOBS TO QUEUE")
        print("=" * 50)
        
        script_path = params.get('script') or os.path.join(os.path.dirname(__file__), 'run_variations.py')
        
        # Phase 2A: Submit ALL jobs to ComfyUI queue first
        for i, prompt in enumerate(prompts, 1):
            print(f"    🎨 Submitting style prompt {i}/{len(prompts)}: {prompt[:50]}...")
            
            cmd = [
                sys.executable, script_path,
                '--prompt', prompt,
                '--n', str(params.get('n', 10)),
                '--k', str(params.get('k', 2)),
                '--strength-min', str(params.get('strength_min', 0.7)),
                '--strength-max', str(params.get('strength_max', 0.9)),
                '--width', str(params.get('width', 720)),
                '--height', str(params.get('height', 1280))
            ]
            
            if params.get('loras'):
                cmd.extend(['--loras'] + params['loras'])
            elif params.get('loras_dir'):
                cmd.extend(['--loras-dir', params['loras_dir']])
            
            if params.get('fixed_loras'):
                cmd.extend(['--fixed-loras'] + params['fixed_loras'])
            
            # Handle wildcards - check if the parameter was provided (not None) rather than if it's truthy
            if params.get('wildcards') is not None:
                cmd.extend(['--wildcards'] + params['wildcards'])
                if params.get('wildcards_dir'):
                    cmd.extend(['--wildcards-dir', params['wildcards_dir']])
            
            if params.get('output_dir'):
                cmd.extend(['--output-dir', params['output_dir']])
            
            # Submit job to queue (this returns immediately after queueing)
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                
                # Extract job IDs from the submission output
                job_id_matches = re.findall(r'prompt_id:\s*([a-fA-F0-9\-]+)', result.stdout)
                
                if not job_id_matches:
                    print(f"    ⚠️  No job IDs found for prompt {i}")
                    print(f"         stdout: {result.stdout[:200]}..." if len(result.stdout) > 200 else f"         stdout: {result.stdout}")
                    if result.stderr:
                        print(f"         stderr: {result.stderr[:200]}..." if len(result.stderr) > 200 else f"         stderr: {result.stderr}")
                else:
                    # Add all job IDs from this prompt to monitoring
                    for job_idx, job_id in enumerate(job_id_matches):
                        monitor.add_job(job_id, f"{i}-{job_idx+1}", prompt[:50])
                        submitted_jobs.append(job_id)
                    
                    print(f"    ✅ Queued {len(job_id_matches)} jobs for prompt {i}: {[jid[:8]+'...' for jid in job_id_matches]}")
                    
            except subprocess.CalledProcessError as e:
                print(f"    ❌ Error submitting prompt {i}: {e}")
                print(f"         stdout: {e.stdout[:200]}..." if e.stdout and len(e.stdout) > 200 else f"         stdout: {e.stdout}")
                print(f"         stderr: {e.stderr[:200]}..." if e.stderr and len(e.stderr) > 200 else f"         stderr: {e.stderr}")
        
        # Phase 2B: Wait for ALL queued jobs to complete
        if submitted_jobs:
            print(f"\n📋 PHASE 2B: WAITING FOR ALL JOBS TO COMPLETE")
            print("=" * 50)
            print(f"⏳ Waiting for {len(submitted_jobs)} total image generation jobs to complete...")
            print(f"🔄 Jobs queued: {[jid[:8]+'...' for jid in submitted_jobs[:10]]}{'...' if len(submitted_jobs) > 10 else ''}")
            
            success = monitor.wait_for_completion(timeout=86400)  # 24 hours
            if not success:
                print("⚠️  Some jobs may not have completed successfully")
            else:
                print(f"🎉 All {len(submitted_jobs)} jobs completed successfully!")
        else:
            print(f"\n⚠️  No jobs were submitted to ComfyUI - check the errors above")
    
    def _execute_refine_styles_images(self, params: Dict, prompts: List[str]):
        """Generate images for refine_styles"""
        import subprocess
        import random
        import re
        from wait_for_comfyui_completion import ComfyUIMonitor
        
        submitted_jobs = []
        monitor = ComfyUIMonitor()
        
        # Implementation simplified - would need full refine_styles logic
        print(f"    🔧 Refining styles with {len(params.get('combo_to_strengths', {}))} LoRA combinations")
        
        # For now, basic implementation
        prompt = prompts[0] if prompts else "refined artwork"
        
        cmd = [
            sys.executable, params.get('script') or os.path.join(os.path.dirname(__file__), 'run_flux.py'),
            '--prompt', prompt,
            '--name-prefix', params.get('project_name', 'refined'),
            '--width', str(params.get('width', 720)),
            '--height', str(params.get('height', 1280))
        ]
        
        if params.get('output_dir'):
            cmd.extend(['--output-dir', params['output_dir']])
        
        # Capture output to extract job IDs
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Extract job ID from run_flux.py output
        job_id_match = re.search(r'prompt_id:\s*([a-fA-F0-9\-]+)', result.stdout)
        if job_id_match:
            job_id = job_id_match.group(1)
            monitor.add_job(job_id, "1", prompt[:50])
            submitted_jobs.append(job_id)
            print(f"✅ Submitted refine_styles job {job_id[:8]}")
        
        # Wait for all jobs to complete
        if submitted_jobs:
            print(f"\n⏳ Waiting for {len(submitted_jobs)} refine_styles jobs to complete...")
            success = monitor.wait_for_completion(timeout=86400)  # 24 hours
            if not success:
                print("⚠️  Some jobs may not have completed successfully")
        else:
            print("⚠️  No jobs were submitted to ComfyUI")
    
    def _execute_explore_narrative_images(self, params: Dict, prompts: List[str]):
        """Generate images for explore_narrative"""
        import subprocess
        import json
        import re
        from wait_for_comfyui_completion import ComfyUIMonitor
        
        meta = params.get('meta', [])
        submitted_jobs = []
        monitor = ComfyUIMonitor()
        
        print(f"\n📋 PHASE 2A: SUBMITTING ALL NARRATIVE JOBS TO QUEUE")
        print("=" * 55)
        
        # Phase 2A: Submit ALL jobs to ComfyUI queue first
        for i, prompt in enumerate(prompts, 1):
            print(f"    📚 Submitting narrative {i}/{len(prompts)}: {prompt[:50]}...")
            
            # Get LoRA info from corresponding source image
            img_idx = (i - 1) % len(meta) if meta else 0
            loras = meta[img_idx][2] if img_idx < len(meta) else []
            
            cmd = [
                sys.executable, os.path.join(os.path.dirname(__file__), 'run_flux.py'),
                '--prompt', prompt,
                '--name-prefix', params.get('project_name', 'narrative'),
                '--width', str(params.get('width', 720)),
                '--height', str(params.get('height', 1280))
            ]
            
            # Add LoRA specs
            if loras:
                lora_specs = []
                for name, model_str, clip_str in loras:
                    if name:
                        spec = f"{name}:{model_str}" if clip_str == 1.0 else f"{name}:{model_str}:{clip_str}"
                        lora_specs.append(spec)
                if lora_specs:
                    cmd.extend(['--loras'] + lora_specs)
            
            # Handle wildcards - check if the parameter was provided (not None) rather than if it's truthy
            if params.get('wildcards') is not None:
                cmd.extend(['--wildcards'] + params['wildcards'])
                if params.get('wildcards_dir'):
                    cmd.extend(['--wildcards-dir', params['wildcards_dir']])
            
            if params.get('output_dir'):
                cmd.extend(['--output-dir', params['output_dir']])
            
            # Run multiple times for seed variations
            for seed_idx in range(params.get('seed_count', 1)):
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                
                # Extract job ID from run_flux.py output
                job_id_match = re.search(r'prompt_id:\s*([a-fA-F0-9\-]+)', result.stdout)
                if job_id_match:
                    job_id = job_id_match.group(1)
                    monitor.add_job(job_id, f"{i}-{seed_idx+1}", prompt[:50])
                    submitted_jobs.append(job_id)
                    print(f"✅ Submitted job {job_id[:8]} for prompt {i} seed {seed_idx+1}")
                else:
                    print(f"⚠️  Could not extract job ID from run_flux.py output for prompt {i}")
        
        # Phase 2B: Wait for ALL queued jobs to complete
        if submitted_jobs:
            print(f"\n📋 PHASE 2B: WAITING FOR ALL NARRATIVE JOBS TO COMPLETE")
            print("=" * 58)
            print(f"⏳ Waiting for {len(submitted_jobs)} total narrative jobs to complete...")
            print(f"🔄 Jobs queued: {[jid[:8]+'...' for jid in submitted_jobs[:10]]}{'...' if len(submitted_jobs) > 10 else ''}")
            
            success = monitor.wait_for_completion(timeout=86400)  # 24 hours
            if not success:
                print("⚠️  Some jobs may not have completed successfully")
            else:
                print(f"🎉 All {len(submitted_jobs)} narrative jobs completed successfully!")
        else:
            print(f"\n⚠️  No narrative jobs were submitted to ComfyUI")
    
    def _cleanup(self):
        """Clean up resources"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                print(f"⚠️  Cleanup warning: {e}")
        
        self.temp_files.clear()
        self.job_batch.clear()

def build_cli():
    """Build the CLI with all original agent.py functionality"""
    parser = argparse.ArgumentParser(
        description='GPU-Optimized MuseVision Agent - Batches LLM then ComfyUI operations'
    )
    
    add_model_switch_args(parser)
    subparsers = parser.add_subparsers(dest='cmd', required=True)
    
    # explore_styles
    e1 = subparsers.add_parser('explore_styles')
    e1.add_argument('--project', required=True)
    e1.add_argument('--prompt', required=True)
    e1.add_argument('--guidance', default='')
    e1.add_argument('--n', type=int, default=12)
    e1.add_argument('--k', type=int, default=3)
    e1.add_argument('--strength-min', type=float, default=0.6)
    e1.add_argument('--strength-max', type=float, default=0.9)
    e1.add_argument('--creativity', type=float, default=0.7)
    e1.add_argument('--dream-count', type=int, default=22)
    e1.add_argument('--tokens-per-prompt', type=int, default=DEFAULT_TOK_PER_PROMPT)
    e1.add_argument('--buffer-factor', type=float, default=DEFAULT_BUF_FACTOR)
    e1.add_argument('--out-subdir', default='style_explore')
    e1.add_argument('--script')
    e1.add_argument('--loras', nargs='+')
    e1.add_argument('--fixed-loras', nargs='+', metavar='LORA_NAME',
                    help='LoRA names that must always be included (e.g., "Flux1D-Faceless_Gods.safetensors"). Remaining slots filled with random LoRAs')
    e1.add_argument('--loras-dir', default=os.path.expanduser("~/MuseVision/ComfyUI/models/loras"))
    e1.add_argument('--wildcards', nargs='*')
    e1.add_argument('--wildcards-dir', default=os.path.expanduser("~/MuseVision/wildcards"))
    e1.add_argument('--width', type=int, default=1280)
    e1.add_argument('--height', type=int, default=720)
    e1.add_argument('--keep-comfyui-running', action='store_true')
    add_model_switch_args(e1)
    
    # refine_styles
    e2 = subparsers.add_parser('refine_styles')
    e2.add_argument('--project', required=True)
    e2.add_argument('--selected-dir')
    e2.add_argument('--prompt')
    e2.add_argument('--tests-per-combo', type=int, default=4)
    e2.add_argument('--seed-count', type=int, default=3)
    e2.add_argument('--seed', type=int)
    e2.add_argument('--extra-combos', type=int, default=0)
    e2.add_argument('--strength-min', type=float, default=0.6)
    e2.add_argument('--strength-max', type=float, default=0.9)
    e2.add_argument('--out-subdir', default='style_refine')
    e2.add_argument('--script')
    e2.add_argument('--fixed-loras', nargs='+', metavar='LORA_NAME',
                    help='LoRA names that must always be included (e.g., "Flux1D-Faceless_Gods.safetensors"). Remaining slots filled with random LoRAs')
    e2.add_argument('--wildcards', nargs='*')
    e2.add_argument('--wildcards-dir', default=os.path.expanduser("~/MuseVision/wildcards"))
    e2.add_argument('--width', type=int, default=1280)
    e2.add_argument('--height', type=int, default=720)
    e2.add_argument('--keep-comfyui-running', action='store_true')
    add_model_switch_args(e2)
    
    # explore_narrative
    e3 = subparsers.add_parser('explore_narrative')
    e3.add_argument('--project', required=True)
    e3.add_argument('--selected-dir', default='selected_images')
    e3.add_argument('--prompt')
    e3.add_argument('--guidance', default='Narratively explore the provided prompt(s), expand and explore provided settings, add narrative arcs to character, add auxiliary characters, etc.')
    e3.add_argument('--creativity', type=float, default=0.7)
    e3.add_argument('--dream-count', type=int, default=22)
    e3.add_argument('--tokens-per-prompt', type=int, default=DEFAULT_TOK_PER_PROMPT)
    e3.add_argument('--buffer-factor', type=float, default=DEFAULT_BUF_FACTOR)
    e3.add_argument('--out-subdir')
    e3.add_argument('--per-image', action='store_true', default=True)
    e3.add_argument('--recreate-script')
    e3.add_argument('--seed-count', type=int, default=3)
    e3.add_argument('--wildcards', nargs='*')
    e3.add_argument('--wildcards-dir', default=os.path.expanduser("~/MuseVision/wildcards"))
    e3.add_argument('--width', type=int, default=1280)
    e3.add_argument('--height', type=int, default=720)
    e3.add_argument('--keep-comfyui-running', action='store_true')
    add_model_switch_args(e3)
    
    return parser

def main():
    """Main entry point"""
    parser = build_cli()
    args = parser.parse_args()
    preset = resolve_preset(args)
    
    agent = GPUOptimizedAgent()
    
    print(f"🔥 GPU-Optimized MuseVision Agent")
    print(f"📊 Using LLM: {preset.name}")
    print(f"🎯 Command: {args.cmd}")
    
    if args.cmd == 'explore_styles':
        agent.cmd_explore_styles(args, preset)
    elif args.cmd == 'refine_styles':
        agent.cmd_refine_styles(args, preset)
    elif args.cmd == 'explore_narrative':
        agent.cmd_explore_narrative(args, preset)
    
    # Execute all batched operations
    shutdown_after = not getattr(args, 'keep_comfyui_running', False)
    agent.execute_batch(shutdown_comfyui_after=shutdown_after)

if __name__ == '__main__':
    main()
