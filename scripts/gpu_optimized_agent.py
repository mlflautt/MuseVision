#!/usr/bin/env python3
"""
GPU-Optimized Agent - Batch LLM then ComfyUI operations

This is a GPU-optimized version of agent.py that:
1. Batches all LLM inference first (full GPU access)
2. Then switches to ComfyUI for image generation
3. Manages ComfyUI lifecycle automatically
4. Minimizes GPU switching overhead
"""

import argparse
import os
import sys
import tempfile
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Import existing agent functionality
from agent import (
    ModelPreset, PRESETS, resolve_preset, resolve_project_dir,
    dream_prompts, extract_metadata_from_png, add_model_switch_args,
    DEFAULT_TOK_PER_PROMPT, DEFAULT_BUF_FACTOR
)

# Import batch queue management
from batch_queue_manager import BatchQueueManager

# Import our ComfyUI manager
from comfyui_manager import ComfyUIManager, GPUOptimizedWorkflow

@dataclass
class BatchJob:
    """Represents a batched operation"""
    job_type: str  # 'llm_generation' or 'image_generation'
    command: str   # The original command (explore_styles, etc.)
    params: Dict[str, Any]  # All the parameters
    prompts: List[str] = None  # Generated prompts (filled during LLM phase)
    
class GPUOptimizedAgent:
    """GPU-optimized agent that batches operations"""
    
    def __init__(self):
        self.comfyui_manager = ComfyUIManager()
        self.job_batch: List[BatchJob] = []
        self.temp_files: List[str] = []  # Track temp files for cleanup
        
    def add_job(self, job_type: str, command: str, **kwargs):
        """Add a job to the batch"""
        job = BatchJob(
            job_type=job_type,
            command=command,
            params=kwargs
        )
        self.job_batch.append(job)
        print(f"📋 Batched job: {command} ({job_type})")
        
    def execute_batch(self, shutdown_comfyui_after: bool = True, timeout: int = 86400) -> bool:
        """Execute all batched jobs with GPU optimization"""
        if not self.job_batch:
            print("📭 No jobs to execute")
            return True
            
        print(f"🚀 Starting GPU-optimized batch execution ({len(self.job_batch)} jobs)")
        
        try:
            # Phase 1: LLM Inference Phase
            print("\n" + "="*60)
            print("🧠 PHASE 1: LLM INFERENCE (Full GPU Access)")
            print("="*60)
            
            # Ensure ComfyUI is stopped for maximum GPU memory
            if self.comfyui_manager.is_running():
                print("⚠️  Stopping ComfyUI to free GPU memory for LLM...")
                self.comfyui_manager.stop()
            
            # Execute all LLM jobs
            llm_jobs = [job for job in self.job_batch if job.job_type == 'llm_generation']
            for i, job in enumerate(llm_jobs, 1):
                print(f"\n🔮 LLM Job {i}/{len(llm_jobs)}: {job.command}")
                self._execute_llm_job(job)
            
            # Phase 2: Image Generation Phase  
            print("\n" + "="*60)
            print("🎨 PHASE 2: IMAGE GENERATION (ComfyUI)")
            print("="*60)
            
            # Start ComfyUI for image generation
            print("🚀 Starting ComfyUI for image generation...")
            if not self.comfyui_manager.start():
                print("❌ Failed to start ComfyUI")
                return False
            
            # Execute all image generation jobs
            img_jobs = [job for job in self.job_batch if job.job_type == 'image_generation']  
            for i, job in enumerate(img_jobs, 1):
                print(f"\n🖼️  Image Job {i}/{len(img_jobs)}: {job.command}")
                self._execute_image_job(job, timeout)
            
            # Phase 3: Cleanup
            if shutdown_comfyui_after:
                print("\n" + "="*30)
                print("🧹 PHASE 3: CLEANUP") 
                print("="*30)
                print("🛑 Shutting down ComfyUI...")
                self.comfyui_manager.stop()
            
            print("✅ All batch jobs completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Batch execution failed: {e}")
            return False
        finally:
            self._cleanup()
    
    def _execute_llm_job(self, job: BatchJob):
        """Execute a single LLM job"""
        command = job.command
        args = job.params
        
        if command == 'explore_styles':
            # Generate dreamed prompts
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
            
        elif command == 'explore_narrative':
            # Extract prompts from source images or use provided prompt
            per_image_mode = bool(args.get('per_image')) and bool(args.get('selected_images'))
            if args.get('selected_images'):
                seed_prompts = []
                for img_path in args['selected_images']:
                    prompt, _, _ = extract_metadata_from_png(img_path)
                    seed_prompts.append(prompt or "A lone figure wanders through an ancient, moonlit forest where the air hums with old magic.")
            else:
                # Use default narrative seed prompts if no images provided
                seed_prompts = [
                    "The creatures' vibrant colors dazzle the travelers, a kaleidoscope of hues against the alien landscape.",
                    "In the shadows of the twilight, a masked figure with a serene expression and glowing eyes stands guard as a group of rebels, their faces hidden by iron and ash masks, gather to discuss their next move against the corrupt sorcerer who wields the power of the elements.",
                    "A figure with a face of swirling, ever-changing patterns roams a landscape of memories, where the air crackles with the energy of synesthetic visions, and every step they take stirs a new tapestry of sensations."
                ]
            
            if seed_prompts:
                if per_image_mode:
                    # Dream prompts per image independently
                    prompts_by_src = {}
                    for idx, seed in enumerate(seed_prompts, 1):
                        prompts_for_img = dream_prompts(
                            [seed],
                            args.get('guidance', ''),
                            args.get('creativity', 0.7), 
                            args.get('dream_count', 5),
                            args.get('tokens_per_prompt', DEFAULT_TOK_PER_PROMPT),
                            args.get('buffer_factor', DEFAULT_BUF_FACTOR),
                            args['preset'],
                            args.get('enforce_1toN', False)
                        )
                        prompts_by_src[str(idx)] = prompts_for_img
                    # Save structured mapping for image phase
                    data = {"per_image": True, "prompts_by_src_idx": prompts_by_src}
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                    json.dump(data, temp_file)
                    temp_file.close()
                    job.params['prompts_file'] = temp_file.name
                    self.temp_files.append(temp_file.name)
                    print(f"  💾 Saved per-image prompts: {len(prompts_by_src)} sources × {len(next(iter(prompts_by_src.values())) if prompts_by_src else [])} prompts")
                else:
                    prompts = dream_prompts(
                        seed_prompts,
                        args.get('guidance', ''),
                        args.get('creativity', 0.7), 
                        args.get('dream_count', 5),
                        args.get('tokens_per_prompt', DEFAULT_TOK_PER_PROMPT),
                        args.get('buffer_factor', DEFAULT_BUF_FACTOR),
                        args['preset'],
                        args.get('enforce_1toN', False)
                    )
                    job.prompts = prompts
            else:
                print("⚠️  No seed prompts available for narrative exploration")
                
        elif command == 'refine_styles':
            # refine_styles doesn't need LLM generation
            job.prompts = [args.get('prompt', 'refined style')]
            
        # Save prompts to temp file for image generation phase
        if job.prompts:
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            json.dump(job.prompts, temp_file)
            temp_file.close()
            job.params['prompts_file'] = temp_file.name
            self.temp_files.append(temp_file.name)
            print(f"  💾 Saved {len(job.prompts)} prompts to temp file")
    
    def _execute_image_job(self, job: BatchJob, timeout: int = 86400):
        """Execute a single image generation job"""
        import subprocess
        
        # Load prompts from temp file or job data
        prompts = job.prompts
        if job.params.get('prompts_file') and os.path.exists(job.params['prompts_file']):
            with open(job.params['prompts_file'], 'r') as f:
                prompts = json.load(f)
        
        # Find corresponding LLM job to get prompts or prompts_file
        if not prompts:
            for other_job in self.job_batch:
                if other_job.job_type == 'llm_generation' and other_job.command == job.command:
                    # Prefer in-memory prompts
                    if other_job.prompts:
                        prompts = other_job.prompts
                        break
                    # Or load from its prompts_file if present
                    pf = other_job.params.get('prompts_file') if hasattr(other_job, 'params') else None
                    if pf and os.path.exists(pf):
                        with open(pf, 'r') as f:
                            prompts = json.load(f)
                        # Also attach to the image job for downstream use
                        job.params['prompts_file'] = pf
                        break
        
        if not prompts:
            print(f"⚠️  No prompts available for {job.command}")
            return
        
        # Friendly summary
        if isinstance(prompts, dict) and prompts.get('per_image') and 'prompts_by_src_idx' in prompts:
            pmap = prompts['prompts_by_src_idx']
            total = sum(len(v) for v in pmap.values())
            per_img = next((len(v) for v in pmap.values()), 0)
            print(f"  📝 Using per-image prompts: {len(pmap)} sources × {per_img} each = {total}")
        else:
            print(f"  📝 Using {len(prompts)} generated prompts")
            
        # Execute image generation based on command type
        if job.command == 'explore_styles':
            self._execute_explore_styles_images(job.params, prompts, timeout)
            
        elif job.command == 'explore_narrative':
            self._execute_explore_narrative_images(job.params, prompts, timeout)
            
        elif job.command == 'refine_styles':
            self._execute_refine_styles_images(job.params, prompts, timeout)
    
    def _execute_explore_styles_images(self, params: Dict, prompts: List[str], timeout: int = 86400):
        """Execute explore_styles image generation with GPU-optimized batch submission"""
        import subprocess
        import requests
        import time
        import random
        import glob
        
        print(f"  🎨 Processing {len(prompts)} prompts with random LoRA combinations")
        
        # Generate LoRA combinations for all jobs
        n_variations = params.get('n', 10)
        k = params.get('k', 2)
        min_strength = params.get('strength_min', 0.7)
        max_strength = params.get('strength_max', 0.9)
        loras_dir = params.get('loras_dir', '/home/mitchellflautt/MuseVision/ComfyUI/models/loras')
        
        # Find available LoRAs
        all_loras = glob.glob(os.path.join(loras_dir, "*Flux*.safetensors"))
        if not all_loras:
            print(f"⚠️  No Flux LoRA files found in {loras_dir}, using plain Flux")
            return
        
        if k > len(all_loras):
            print(f"⚠️  Requested {k} LoRAs but only {len(all_loras)} available, using all available")
            k = len(all_loras)
        
        print(f"\n📤 BATCH SUBMISSION PHASE - STYLE EXPLORATION")
        print("=" * 50)
        print(f"  🎲 Generating {n_variations} combinations using {k} LoRAs each from {len(all_loras)} available")
        
        submitted_jobs = []
        failed_submissions = 0
        total_jobs = len(prompts) * n_variations
        current_job = 0
        
        for prompt_idx, prompt in enumerate(prompts, 1):
            print(f"    📝 Prompt {prompt_idx}/{len(prompts)}: {prompt[:50]}...")
            
            for variation_idx in range(n_variations):
                current_job += 1
                
                # Generate random LoRA combination
                selected_loras = random.sample(all_loras, k)
                lora_combo = []
                
                for lora_path in selected_loras:
                    name = os.path.basename(lora_path)
                    model_strength = round(random.uniform(min_strength, max_strength), 3)
                    clip_strength = 1.0  # Standard clip strength
                    lora_combo.append((name, model_strength, clip_strength))
                
                # Build run_flux command  
                run_flux_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'run_flux.py')
                cmd = [
                    sys.executable, run_flux_path,
                    '--prompt', prompt,
                    '--name-prefix', f'style_{prompt_idx}_{variation_idx}'
                ]
                
                # Add LoRA specifications
                lora_specs = []
                for name, model_str, clip_str in lora_combo:
                    spec = f"{name}:{model_str}" if clip_str == 1.0 else f"{name}:{model_str}:{clip_str}"
                    lora_specs.append(spec)
                if lora_specs:
                    cmd.extend(['--loras'] + lora_specs)
                
                # Add resolution
                if params.get('width'):
                    cmd.extend(['--width', str(params['width'])])
                if params.get('height'):
                    cmd.extend(['--height', str(params['height'])])
                    
                # Add wildcards
                if params.get('wildcards'):
                    cmd.extend(['--wildcards'] + params['wildcards'])
                    if params.get('wildcards_dir'):
                        cmd.extend(['--wildcards-dir', params['wildcards_dir']])
                
                # Add output directory
                if params.get('output_dir'):
                    cmd.extend(['--output-dir', params['output_dir']])
                
                # Submit job immediately
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    # Extract prompt_id from output
                    job_id = None
                    for line in result.stdout.split('\n'):
                        if 'prompt_id:' in line:
                            import re
                            match = re.search(r'prompt_id: ([a-f0-9-]+)', line)
                            if match:
                                job_id = match.group(1)
                                submitted_jobs.append({
                                    'id': job_id,
                                    'prompt_idx': prompt_idx,
                                    'variation_idx': variation_idx,
                                    'submit_time': time.time(),
                                    'prompt_preview': prompt[:50] + "...",
                                    'loras': [lora[0] for lora in lora_combo]
                                })
                                break
                    
                    if not job_id:
                        print(f"⚠️  No prompt_id found for job {prompt_idx}-{variation_idx}")
                        failed_submissions += 1
                        
                    # Show progress for first few combinations
                    if variation_idx < 3:
                        lora_names = [lora[0].replace('Flux-', '').replace('.safetensors', '') for lora in lora_combo]
                        print(f"      🎯 Variation {variation_idx+1}: {', '.join(lora_names)}")
                        
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to submit job {prompt_idx}-{variation_idx}: {e.stderr.strip() if e.stderr else str(e)}")
                    failed_submissions += 1
                    continue
        
        print(f"\n📊 Submission Summary:")
        print(f"   ✅ Successfully submitted: {len(submitted_jobs)} jobs")
        print(f"   ❌ Failed submissions: {failed_submissions} jobs")
        print(f"   📊 Total expected: {total_jobs} jobs")
        
        # Phase 2: Monitor completion with better reporting
        if submitted_jobs:
            print(f"\n🔍 JOB MONITORING PHASE")
            print("=" * 40)
            self._wait_for_comfyui_jobs_enhanced(submitted_jobs, timeout)
        else:
            print("❌ No jobs were successfully submitted to track")
    
    def _execute_explore_narrative_images(self, params: Dict, prompts: List[str], timeout: int = 86400):
        """Execute explore_narrative image generation with improved job tracking
        
        Fixes:
        - Respect --per-image by multiplying jobs across selected_images
        - Structured filename prefix: <src_idx>_<prompt_idx>_<seed_idx> (zero-padded for A–Z sorting)
        """
        import subprocess
        import requests
        import time
        
        # Determine if prompts are per-image mapping
        prompts_by_src = None
        if isinstance(prompts, dict) and prompts.get('per_image') and 'prompts_by_src_idx' in prompts:
            prompts_by_src = prompts['prompts_by_src_idx']
            sample_len = next((len(v) for v in prompts_by_src.values()), 0)
            print(f"  📝 Processing per-image prompts: {len(prompts_by_src)} sources × {sample_len} prompts")
        else:
            print(f"  📝 Processing {len(prompts)} prompts")
        
        # Phase 1: Submit ALL jobs first (fast batch submission)
        print(f"\n📤 BATCH SUBMISSION PHASE")
        print("=" * 40)
        
        submitted_jobs = []
        failed_submissions = 0
        
        # Get LoRA info aligned to each source image (empty list if none)
        selected_images = params.get('selected_images') or []
        loras_by_image = []
        if selected_images:
            for img_path in selected_images:
                _, loras, _ = extract_metadata_from_png(img_path)
                loras_by_image.append(loras or [])
        if selected_images and not any(loras_by_image):
            print(f"⚠️  No LoRA metadata found in selected images - proceeding without LoRAs per image")
        
        seed_count = params.get('seed_count', 1)
        per_image = bool(params.get('per_image')) and len(selected_images) > 0
        src_count = len(selected_images) if per_image else 1
        if prompts_by_src is not None:
            total_jobs = sum(len(v) for v in prompts_by_src.values()) * seed_count
        else:
            total_jobs = len(prompts) * seed_count * src_count
        current_job = 0
        
        def build_and_submit(prefix: str, prompt: str, lora_combo, i: int, seed_idx: int, extra_job_info: dict):
            nonlocal current_job, failed_submissions
            current_job += 1
            run_flux_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'run_flux.py')
            cmd = [
                sys.executable, run_flux_path,
                '--prompt', prompt,
                '--name-prefix', prefix
            ]
            # Add LoRAs
            if lora_combo:
                lora_specs = []
                for name, model_str, clip_str in lora_combo:
                    if name:
                        spec = f"{name}:{model_str}" if clip_str == 1.0 else f"{name}:{model_str}:{clip_str}"
                        lora_specs.append(spec)
                if lora_specs:
                    cmd.extend(['--loras'] + lora_specs)
            # Resolution
            if params.get('width'):
                cmd.extend(['--width', str(params['width'])])
            if params.get('height'):
                cmd.extend(['--height', str(params['height'])])
            # Wildcards
            if params.get('wildcards'):
                cmd.extend(['--wildcards'] + params['wildcards'])
                if params.get('wildcards_dir'):
                    cmd.extend(['--wildcards-dir', params['wildcards_dir']])
            # Output directory
            if params.get('output_dir'):
                cmd.extend(['--output-dir', params['output_dir']])
            # Submit
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                job_id = None
                for line in result.stdout.split('\n'):
                    if 'prompt_id:' in line:
                        import re
                        match = re.search(r'prompt_id: ([a-f0-9-]+)', line)
                        if match:
                            job_id = match.group(1)
                            j = {
                                'id': job_id,
                                'prompt_idx': i,
                                'seed_idx': seed_idx,
                                'submit_time': time.time(),
                                'prompt_preview': prompt[:50] + "..."
                            }
                            j.update(extra_job_info or {})
                            submitted_jobs.append(j)
                            break
                if not job_id:
                    print(f"⚠️  No prompt_id found for job {extra_job_info.get('src_idx','-')}-{i}-{seed_idx}")
                    failed_submissions += 1
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to submit job {extra_job_info.get('src_idx','-')}-{i}-{seed_idx}: {e.stderr.strip() if e.stderr else str(e)}")
                failed_submissions += 1
                return
        
        if per_image:
            # Loop across each source image
            for src_idx in range(1, src_count + 1):
                lora_combo = loras_by_image[src_idx - 1] if loras_by_image else []
                print(f"    🖼️  Source {src_idx}/{src_count}")
                # Choose prompt set: per-image mapping or shared prompts
                img_prompts = None
                if prompts_by_src is not None:
                    img_prompts = prompts_by_src.get(str(src_idx), [])
                if not img_prompts:
                    img_prompts = prompts
                for i, prompt in enumerate(img_prompts, 1):
                    print(f"      📖 Narrative {i}/{len(img_prompts)}: {prompt[:50]}...")
                    for seed_idx in range(seed_count):
                        # Structured prefix for A–Z sorting
                        prefix = f"{src_idx:03d}_{i:03d}_{seed_idx:03d}"
                        build_and_submit(prefix, prompt, lora_combo, i, seed_idx, {'src_idx': src_idx})
        else:
            # Legacy behavior: rotate lora combo by prompt index if present
            for i, prompt in enumerate(prompts if not isinstance(prompts, dict) else [], 1):
                print(f"    📖 Narrative {i}/{len(prompts)}: {prompt[:50]}...")
                lora_combo = []
                if loras_by_image:
                    lora_combo = loras_by_image[(i - 1) % len(loras_by_image)]
                for seed_idx in range(seed_count):
                    prefix = f"{i:03d}_{seed_idx:03d}"
                    build_and_submit(prefix, prompt, lora_combo, i, seed_idx, {})
        
        print(f"\n📊 Submission Summary:")
        print(f"   ✅ Successfully submitted: {len(submitted_jobs)} jobs")
        print(f"   ❌ Failed submissions: {failed_submissions} jobs")
        print(f"   📊 Total expected: {total_jobs} jobs")
        
        # Phase 2: Monitor completion with better reporting
        if submitted_jobs:
            print(f"\n🔍 JOB MONITORING PHASE")
            print("=" * 40)
            self._wait_for_comfyui_jobs_enhanced(submitted_jobs, timeout)
        else:
            print("❌ No jobs were successfully submitted to track")
    
    def _execute_refine_styles_images(self, params: Dict, prompts: List[str], timeout: int = 86400):
        """Execute refine_styles image generation with LoRA pool testing methodology"""
        import subprocess
        import requests
        import time
        
        print(f"  🎨 Processing {len(prompts)} prompts with LoRA pool refinement")
        
        # Extract LoRA pool from selected style images
        lora_pool = set()  # Use set to avoid duplicates
        if params.get('selected_styles'):
            print(f"  🖼️  Extracting LoRA pool from {len(params['selected_styles'])} style images")
            for img_path in params['selected_styles']:
                _, loras, _ = extract_metadata_from_png(img_path)
                if loras:
                    for name, model_str, clip_str in loras:
                        if name:
                            lora_pool.add(name)
            
            lora_pool = list(lora_pool)  # Convert back to list
            print(f"  🎲 Extracted LoRA pool: {len(lora_pool)} unique LoRAs")
            if lora_pool:
                print(f"    LoRAs: {', '.join([lora.replace('Flux-', '').replace('.safetensors', '') for lora in lora_pool[:5]])}{'...' if len(lora_pool) > 5 else ''}")
        
        if not lora_pool:
            print(f"⚠️  No LoRA pool found in style images - falling back to random selection")
            return
        
        # Generate test combinations from LoRA pool
        test_count = params.get('test_count', 10)
        k = params.get('k', 2)
        min_strength = params.get('strength_min', 0.5)
        max_strength = params.get('strength_max', 1.0)
        
        if k > len(lora_pool):
            print(f"⚠️  Requested {k} LoRAs but only {len(lora_pool)} in pool, using all available")
            k = len(lora_pool)
        
        print(f"\n📤 BATCH SUBMISSION PHASE - STYLE REFINEMENT")
        print("=" * 50)
        print(f"  🎯 Testing {test_count} combinations using {k} LoRAs each from pool of {len(lora_pool)}")
        
        submitted_jobs = []
        failed_submissions = 0
        
        import random
        total_jobs = len(prompts) * test_count
        current_job = 0
        
        for prompt_idx, prompt in enumerate(prompts, 1):
            print(f"    📝 Prompt {prompt_idx}/{len(prompts)}: {prompt[:50]}...")
            
            for test_idx in range(test_count):
                current_job += 1
                
                # Select k LoRAs from the pool
                selected_loras = random.sample(lora_pool, k)
                lora_combo = []
                
                for lora_name in selected_loras:
                    model_strength = round(random.uniform(min_strength, max_strength), 3)
                    clip_strength = 1.0  # Standard clip strength
                    lora_combo.append((lora_name, model_strength, clip_strength))
                
                # Build run_flux command
                run_flux_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'run_flux.py')
                cmd = [
                    sys.executable, run_flux_path,
                    '--prompt', prompt,
                    '--name-prefix', f'refine_{prompt_idx}_{test_idx}'
                ]
                
                # Add LoRA specifications
                lora_specs = []
                for name, model_str, clip_str in lora_combo:
                    spec = f"{name}:{model_str}" if clip_str == 1.0 else f"{name}:{model_str}:{clip_str}"
                    lora_specs.append(spec)
                if lora_specs:
                    cmd.extend(['--loras'] + lora_specs)
                
                # Add resolution
                if params.get('width'):
                    cmd.extend(['--width', str(params['width'])])
                if params.get('height'):
                    cmd.extend(['--height', str(params['height'])])
                    
                # Add wildcards
                if params.get('wildcards'):
                    cmd.extend(['--wildcards'] + params['wildcards'])
                    if params.get('wildcards_dir'):
                        cmd.extend(['--wildcards-dir', params['wildcards_dir']])
                
                # Add output directory
                if params.get('output_dir'):
                    cmd.extend(['--output-dir', params['output_dir']])
                
                # Submit job immediately
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    # Extract prompt_id from output
                    job_id = None
                    for line in result.stdout.split('\n'):
                        if 'prompt_id:' in line:
                            import re
                            match = re.search(r'prompt_id: ([a-f0-9-]+)', line)
                            if match:
                                job_id = match.group(1)
                                submitted_jobs.append({
                                    'id': job_id,
                                    'prompt_idx': prompt_idx,
                                    'test_idx': test_idx,
                                    'submit_time': time.time(),
                                    'prompt_preview': prompt[:50] + "...",
                                    'loras': [lora[0] for lora in lora_combo]
                                })
                                break
                    
                    if not job_id:
                        print(f"⚠️  No prompt_id found for job {prompt_idx}-{test_idx}")
                        failed_submissions += 1
                        
                    # Show progress for first few combinations
                    if test_idx < 3:
                        lora_names = [lora[0].replace('Flux-', '').replace('.safetensors', '') for lora in lora_combo]
                        print(f"      🎯 Test {test_idx+1}: {', '.join(lora_names)}")
                        
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to submit job {prompt_idx}-{test_idx}: {e.stderr.strip() if e.stderr else str(e)}")
                    failed_submissions += 1
                    continue
        
        print(f"\n📊 Submission Summary:")
        print(f"   ✅ Successfully submitted: {len(submitted_jobs)} jobs")
        print(f"   ❌ Failed submissions: {failed_submissions} jobs")
        print(f"   📊 Total expected: {total_jobs} jobs")
        
        # Phase 2: Monitor completion with better reporting
        if submitted_jobs:
            print(f"\n🔍 JOB MONITORING PHASE")
            print("=" * 40)
            self._wait_for_comfyui_jobs_enhanced(submitted_jobs, timeout)
        else:
            print("❌ No jobs were successfully submitted to track")
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}h:{minutes:02d}m:{secs:02d}s"
    
    def _get_job_index_info(self, job_info: Dict) -> Tuple[str, str]:
        """Get the appropriate index key and value for a job based on what's available
        
        Returns:
            Tuple[str, str]: (index_name, index_value) pair to use for display
        """
        # Check for different job type indices in priority order
        if 'src_idx' in job_info:
            return 'src_idx', str(job_info['src_idx'])
        elif 'seed_idx' in job_info:
            return 'seed_idx', str(job_info['seed_idx'])
        elif 'variation_idx' in job_info:
            return 'variation_idx', str(job_info['variation_idx'])
        elif 'test_idx' in job_info:
            return 'test_idx', str(job_info['test_idx'])
        else:
            # Fallback if no specific index is found
            return 'job', '#'
    
    def _wait_for_comfyui_jobs_enhanced(self, submitted_jobs: List[Dict], timeout: int = 86400):
        """Enhanced job monitoring with better reporting and timeout handling"""
        import requests
        import time
        
        api_url = "http://127.0.0.1:8188"
        start_time = time.time()
        completed_jobs = {}
        last_active_time = start_time
        
        job_lookup = {job['id']: job for job in submitted_jobs}
        job_ids = [job['id'] for job in submitted_jobs]
        
        print(f"🔍 Monitoring {len(job_ids)} jobs (timeout: {self._format_time(timeout)})")
        print(f"🎯 Tracking job IDs: {[jid[:8] + '...' for jid in job_ids[:5]]}{'...' if len(job_ids) > 5 else ''}")
        
        # Initial status check
        consecutive_errors = 0
        max_consecutive_errors = 6  # Allow up to 1 minute of errors before giving up
        
        while len(completed_jobs) < len(job_ids) and (time.time() - start_time) < timeout:
            try:
                # Check queue status
                response = requests.get(f"{api_url}/queue", timeout=10)
                if response.status_code == 200:
                    consecutive_errors = 0
                    queue_info = response.json()
                    
                    # Get currently executing and pending job IDs
                    executing_items = queue_info.get('queue_running', [])
                    pending_items = queue_info.get('queue_pending', [])
                    
                    executing_ids = {item[1] for item in executing_items}
                    pending_ids = {item[1] for item in pending_items}
                    active_ids = executing_ids | pending_ids
                    
                    # Debug: Show queue status periodically
                    if len(completed_jobs) % 10 == 0 and len(completed_jobs) > 0:  # Every 10 completions
                        print(f"🗺️ Queue status: {len(executing_ids)} running, {len(pending_ids)} pending, {len(active_ids)} total active")
                    
                    # Check history API for completed jobs
                    try:
                        history_response = requests.get(f"{api_url}/history", timeout=5)
                        history_data = history_response.json() if history_response.status_code == 200 else {}
                    except:
                        history_data = {}
                    
                    # Check for newly completed jobs (in history or disappeared from queue)
                    newly_completed = []
                    for job_id in job_ids:
                        if job_id not in completed_jobs:
                            # Check if job is in history (definitively completed)
                            if job_id in history_data:
                                completion_time = time.time()
                                job_duration = completion_time - job_lookup[job_id]['submit_time']
                                completed_jobs[job_id] = {
                                    'completion_time': completion_time,
                                    'duration': job_duration,
                                    'status': 'completed_in_history'
                                }
                                newly_completed.append((job_id, job_duration))
                            # Also check if it disappeared from queue (legacy detection)
                            elif job_id not in active_ids:
                                completion_time = time.time()
                                job_duration = completion_time - job_lookup[job_id]['submit_time']
                                completed_jobs[job_id] = {
                                    'completion_time': completion_time,
                                    'duration': job_duration,
                                    'status': 'disappeared_from_queue'
                                }
                                newly_completed.append((job_id, job_duration))
                    
                    # Report newly completed jobs with timing
                    for job_id, duration in newly_completed:
                        job_info = job_lookup[job_id]
                        index_name, index_value = self._get_job_index_info(job_info)
                        print(f"✅ Job {job_id[:8]} completed in {duration:.1f}s - Prompt {job_info['prompt_idx']}-{index_value}: {job_info['prompt_preview']} ({len(completed_jobs)}/{len(job_ids)})")
                        last_active_time = time.time()
                    
                    # Check for stuck jobs (no progress for too long)
                    if time.time() - last_active_time > 600:  # 10 minutes with no completed jobs
                        print(f"⚠️  No jobs completed in 10+ minutes. Checking queue health...")
                        
                        # Get current history to check for missing jobs
                        try:
                            history_response = requests.get(f"{api_url}/history", timeout=5)
                            current_history = history_response.json() if history_response.status_code == 200 else {}
                        except:
                            current_history = {}
                        
                        # Check if any of our jobs are still in the queue
                        our_active_jobs = [jid for jid in job_ids if jid in active_ids]
                        jobs_in_history = [jid for jid in job_ids if jid in current_history]
                        missing_jobs = [jid for jid in job_ids if jid not in active_ids and jid not in completed_jobs and jid not in current_history]
                        
                        print(f"📋 Status breakdown:")
                        print(f"   ✅ Completed: {len(completed_jobs)}/{len(job_ids)}")
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
                                requests.post(f"{api_url}/interrupt", timeout=5)
                            except Exception as _e:
                                print(f"⚠️  Interrupt request failed: {_e}")
                            
                            last_active_time = time.time()  # Reset timer if queue is active
                    
                    # Only show periodic status if we have pending jobs (not every loop)
                    remaining = len(job_ids) - len(completed_jobs)
                    if remaining > 0 and newly_completed:  # Only show when jobs complete
                        elapsed = time.time() - start_time
                        avg_time = elapsed / len(completed_jobs) if completed_jobs else 0
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
        if len(completed_jobs) == len(job_ids):
            avg_job_time = sum(job['duration'] for job in completed_jobs.values()) / len(completed_jobs)
            print(f"\n🎉 All {len(job_ids)} jobs completed successfully!")
            print(f"   ⏱️ Total time: {self._format_time(total_time)}")
            print(f"   📊 Average per job: {self._format_time(avg_job_time)}")
        else:
            print(f"\n⚠️  Incomplete: {len(completed_jobs)}/{len(job_ids)} jobs finished in {self._format_time(total_time)}")
            if consecutive_errors >= max_consecutive_errors:
                print("🔴 Stopped due to ComfyUI connection issues")
            else:
                print("⏰ Stopped due to timeout")
    
    def _generate_random_lora_combinations(self, num_combinations: int, loras_dir: str, k: int = 2, min_strength: float = 0.5, max_strength: float = 1.0):
        """Generate random LoRA combinations for narrative generation"""
        import glob
        import random
        
        # Find all Flux LoRA files
        all_loras = glob.glob(os.path.join(loras_dir, "*Flux*.safetensors"))
        if not all_loras:
            print(f"⚠️  No Flux LoRA files found in {loras_dir}, using plain Flux")
            return []
        
        if k > len(all_loras):
            print(f"⚠️  Requested {k} LoRAs but only {len(all_loras)} available, using all available")
            k = len(all_loras)
        
        lora_combinations = []
        print(f"  🎲 Generating {num_combinations} combinations using {k} LoRAs each from {len(all_loras)} available")
        
        for i in range(num_combinations):
            # Select k random LoRAs
            selected_loras = random.sample(all_loras, k)
            lora_combo = []
            
            for lora_path in selected_loras:
                name = os.path.basename(lora_path)
                model_strength = round(random.uniform(min_strength, max_strength), 3)
                clip_strength = 1.0  # Standard clip strength
                lora_combo.append((name, model_strength, clip_strength))
            
            lora_combinations.append(lora_combo)
            
            # Show the first few combinations for debugging
            if i < 3:
                lora_names = [lora[0] for lora in lora_combo]
                print(f"    🎯 Combo {i+1}: {', '.join(lora_names)}")
        
        return lora_combinations
    
    def _cleanup(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                print(f"⚠️  Failed to clean up {temp_file}: {e}")
        self.temp_files.clear()
        self.job_batch.clear()

def main():
    """Main entry point for GPU-optimized agent"""
    parser = argparse.ArgumentParser(description='GPU-Optimized MuseVision Agent')
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # explore_styles command
    explore_parser = subparsers.add_parser('explore_styles', help='Explore style variations')
    explore_parser.add_argument('--project', required=True, help='Project name')
    explore_parser.add_argument('--prompt', required=True, help='Base prompt')
    explore_parser.add_argument('--guidance', default='', help='Additional guidance for LLM')
    explore_parser.add_argument('--n', type=int, default=10, help='Images per prompt')
    explore_parser.add_argument('--k', type=int, default=2, help='LoRAs per combination')
    explore_parser.add_argument('--creativity', type=float, default=0.7, help='LLM creativity')
    explore_parser.add_argument('--dream-count', type=int, default=5, help='Number of prompts to generate')
    explore_parser.add_argument('--width', type=int, default=720, help='Image width')
    explore_parser.add_argument('--height', type=int, default=1280, help='Image height')
    explore_parser.add_argument('--wildcards', nargs='*', help='Wildcard specifications')
    explore_parser.add_argument('--wildcards-dir', default='/home/mitchellflautt/MuseVision/wildcards')
    explore_parser.add_argument('--strength-min', type=float, default=0.7, help='Minimum LoRA strength')
    explore_parser.add_argument('--strength-max', type=float, default=0.9, help='Maximum LoRA strength')
    explore_parser.add_argument('--loras-dir', default='/home/mitchellflautt/MuseVision/ComfyUI/models/loras')
    explore_parser.add_argument('--keep-comfyui-running', action='store_true', 
                               help='Keep ComfyUI running after completion')
    explore_parser.add_argument('--timeout', type=int, default=86400, 
                               help='Timeout in seconds for job completion (default: 24 hours)')
    add_model_switch_args(explore_parser)
    
    # explore_narrative command
    narrative_parser = subparsers.add_parser('explore_narrative', help='Explore narrative variations using LoRAs from source images')
    narrative_parser.add_argument('--project', required=True, help='Project name')
    narrative_parser.add_argument('--selected-images', nargs='*', help='Source images to extract LoRA configurations from')
    narrative_parser.add_argument('--per-image', action='store_true', help='Process per image')
    narrative_parser.add_argument('--guidance', default='', help='Additional guidance for LLM')
    narrative_parser.add_argument('--creativity', type=float, default=0.7, help='LLM creativity')
    narrative_parser.add_argument('--dream-count', type=int, default=5, help='Number of prompts to generate')
    narrative_parser.add_argument('--out-subdir', default='narrative_explore', help='Output subdirectory')
    narrative_parser.add_argument('--seed-count', type=int, default=1, help='Images per prompt')
    narrative_parser.add_argument('--tokens-per-prompt', type=int, default=DEFAULT_TOK_PER_PROMPT, help='Tokens per prompt')
    narrative_parser.add_argument('--width', type=int, default=720, help='Image width')
    narrative_parser.add_argument('--height', type=int, default=1280, help='Image height')
    narrative_parser.add_argument('--wildcards', nargs='*', help='Wildcard specifications')
    narrative_parser.add_argument('--wildcards-dir', default='/home/mitchellflautt/MuseVision/wildcards')
    narrative_parser.add_argument('--keep-comfyui-running', action='store_true', 
                                 help='Keep ComfyUI running after completion')
    narrative_parser.add_argument('--timeout', type=int, default=86400, 
                                 help='Timeout in seconds for job completion (default: 24 hours)')
    add_model_switch_args(narrative_parser)
    
    # refine_styles command
    refine_parser = subparsers.add_parser('refine_styles', help='Refine and test LoRA combinations from selected styles')
    refine_parser.add_argument('--project', required=True, help='Project name')
    refine_parser.add_argument('--prompt', required=True, help='Base prompt for testing styles')
    refine_parser.add_argument('--selected-styles', nargs='*', help='Selected style images to extract LoRA pools from')
    refine_parser.add_argument('--guidance', default='', help='Additional guidance for LLM')
    refine_parser.add_argument('--creativity', type=float, default=0.7, help='LLM creativity')
    refine_parser.add_argument('--dream-count', type=int, default=5, help='Number of prompts to generate')
    refine_parser.add_argument('--test-count', type=int, default=10, help='Number of LoRA combinations to test')
    refine_parser.add_argument('--width', type=int, default=720, help='Image width')
    refine_parser.add_argument('--height', type=int, default=1280, help='Image height')
    refine_parser.add_argument('--wildcards', nargs='*', help='Wildcard specifications')
    refine_parser.add_argument('--wildcards-dir', default='/home/mitchellflautt/MuseVision/wildcards')
    refine_parser.add_argument('--k', type=int, default=2, help='LoRAs per combination')
    refine_parser.add_argument('--strength-min', type=float, default=0.5, help='Minimum LoRA strength')
    refine_parser.add_argument('--strength-max', type=float, default=1.0, help='Maximum LoRA strength')
    refine_parser.add_argument('--keep-comfyui-running', action='store_true', 
                             help='Keep ComfyUI running after completion')
    refine_parser.add_argument('--timeout', type=int, default=86400, 
                             help='Timeout in seconds for job completion (default: 24 hours)')
    add_model_switch_args(refine_parser)
    
    # Queue management command
    queue_parser = subparsers.add_parser('queue', help='Manage batch queue')
    queue_subparsers = queue_parser.add_subparsers(dest='queue_action', help='Queue actions')
    
    # Queue status
    status_parser = queue_subparsers.add_parser('status', help='Show queue status')
    
    # Queue clear
    clear_parser = queue_subparsers.add_parser('clear', help='Clear queue')
    clear_parser.add_argument('--status-filter', help='Clear only batches with specific status')
    
    # Queue remove
    remove_parser = queue_subparsers.add_parser('remove', help='Remove specific batch')
    remove_parser.add_argument('batch_id', help='Batch ID to remove')
    
    # Queue watch (live runtime summary)
    watch_parser = queue_subparsers.add_parser('watch', help='Live watch of queue and runtime status')
    watch_parser.add_argument('--interval', type=int, default=10, help='Refresh interval in seconds')
    
    # Add queue options to all main commands
    for cmd_parser in [explore_parser, narrative_parser, refine_parser]:
        cmd_parser.add_argument('--queue', action='store_true', default=True,
                               help='Add to batch queue (default: true)')
        cmd_parser.add_argument('--no-queue', dest='queue', action='store_false',
                               help='Execute immediately without queueing')
        cmd_parser.add_argument('--force-now', action='store_true',
                               help='Force immediate execution, bypass queue')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Handle queue management commands first
    if args.command == 'queue':
        queue_manager = BatchQueueManager()
        
        if args.queue_action == 'status':
            queue_manager.print_queue_status()
            return
        
        elif args.queue_action == 'clear':
            count = queue_manager.clear_queue(args.status_filter)
            print(f"Cleared {count} batches from queue")
            return
        
        elif args.queue_action == 'remove':
            success = queue_manager.remove_batch(args.batch_id)
            if not success:
                exit(1)
            return
        
        elif args.queue_action == 'watch':
            import time, requests, subprocess, json
            try:
                while True:
                    status = queue_manager.get_queue_status()
                    total = status.get('total_batches', 0)
                    pending = status.get('pending', 0)
                    processing = status.get('processing', 0)
                    completed = status.get('completed', 0)
                    failed = status.get('failed', 0)
                    print("\n=== Queue Runtime ===")
                    print(f"Total:{total} Pending:{pending} Processing:{processing} Completed:{completed} Failed:{failed}")
                    # LLM activity
                    try:
                        out = subprocess.run(['pgrep','-af','llama-cli'], capture_output=True, text=True)
                        llm_active = bool(out.stdout.strip())
                    except Exception:
                        llm_active = False
                    # ComfyUI
                    comfy_up = False
                    q_run = q_pend = -1
                    try:
                        r = requests.get('http://127.0.0.1:8188/queue', timeout=5)
                        if r.status_code == 200:
                            comfy_up = True
                            q = r.json()
                            q_run = len(q.get('queue_running', []))
                            q_pend = len(q.get('queue_pending', []))
                    except Exception:
                        comfy_up = False
                    print(f"LLM(dreaming): {'yes' if llm_active else 'no'} | ComfyUI: {'up' if comfy_up else 'down'}", end='')
                    if comfy_up:
                        print(f" | queue running:{q_run} pending:{q_pend}")
                    else:
                        print()
                    time.sleep(getattr(args,'interval',10))
            except KeyboardInterrupt:
                print("\nStopped watch.")
            return
        
        else:
            queue_manager.print_queue_status()
            return
    
    # Resolve model preset for batch commands
    preset = resolve_preset(args)
    
    # Check if this should be queued or executed immediately
    should_queue = getattr(args, 'queue', True) and not getattr(args, 'force_now', False)
    
    if should_queue:
        # Add to queue and exit
        queue_manager = BatchQueueManager()
        
        # Build parameter dictionary
        parameters = {
            key: value for key, value in vars(args).items()
            if key not in ['command', 'queue', 'no_queue', 'force_now', 'llm_preset', 'model_path', 'llama_cli']
        }
        
        # Add preset info
        parameters['preset'] = preset
        
        # Reconstruct full command line
        import sys
        full_command = ' '.join(sys.argv)
        
        try:
            batch_id = queue_manager.add_batch(
                command=args.command,
                project=args.project,
                parameters=parameters,
                full_command=full_command
            )
            
            # Show current queue status
            print("\n" + "="*50)
            queue_manager.print_queue_status()
            
        except RuntimeError as e:
            print(f"❌ Failed to add batch to queue: {e}")
            exit(1)
        
        return
    
    # Create GPU-optimized agent for immediate execution
    agent = GPUOptimizedAgent()
    
    if args.command == 'explore_styles':
        # Prepare project paths
        proj_dir = resolve_project_dir(args.project)
        output_dir = os.path.join(proj_dir, 'style_explore')
        selected_images_dir = os.path.join(proj_dir, 'selected_images')
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(selected_images_dir, exist_ok=True)
        print(f"📁 Created selected_images folder for saving favorites: {selected_images_dir}")
        
        # Add LLM job
        agent.add_job('llm_generation', 'explore_styles',
                     preset=preset,
                     prompt=args.prompt,
                     guidance=args.guidance,
                     creativity=args.creativity,
                     dream_count=args.dream_count)
        
        # Add image generation job
        agent.add_job('image_generation', 'explore_styles',
                     n=args.n,
                     k=args.k,
                     strength_min=args.strength_min,
                     strength_max=args.strength_max,
                     width=args.width,
                     height=args.height,
                     wildcards=args.wildcards,
                     wildcards_dir=args.wildcards_dir,
                     loras_dir=args.loras_dir,
                     output_dir=os.path.relpath(output_dir, '/home/mitchellflautt/MuseVision/projects'))
        
        # Execute batch
        shutdown_after = not args.keep_comfyui_running
        agent.execute_batch(shutdown_comfyui_after=shutdown_after, timeout=args.timeout)
    
    elif args.command == 'explore_narrative':
        # Prepare project paths
        proj_dir = resolve_project_dir(args.project)
        output_dir = os.path.join(proj_dir, args.out_subdir)
        selected_images_dir = os.path.join(proj_dir, 'selected_images')
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(selected_images_dir, exist_ok=True)
        
        # Handle selected images logic
        if args.selected_images:
            # Use explicitly provided images
            selected_images = args.selected_images
        else:
            # Auto-discover images in selected_images folder
            import glob
            image_patterns = ['*.png', '*.jpg', '*.jpeg']
            selected_images = []
            for pattern in image_patterns:
                selected_images.extend(glob.glob(os.path.join(selected_images_dir, pattern)))
            
            if not selected_images:
                print(f"\n🖼️  EXPLORE NARRATIVE REQUIRES SOURCE IMAGES")
                print(f"➡️  Please add images to: {selected_images_dir}")
                print(f"📝 Instructions:")
                print(f"   1. Place 2-5 images with interesting LoRA styles in the folder")
                print(f"   2. Run the command again")
                print(f"   3. The system will extract LoRA configurations and create narrative variations")
                print(f"\n📁 Folder created: {selected_images_dir}")
                return
            else:
                print(f"🖼️  Auto-discovered {len(selected_images)} images in selected_images folder")
        
        # Add LLM job
        agent.add_job('llm_generation', 'explore_narrative',
                     preset=preset,
                     selected_images=selected_images,
                     per_image=args.per_image,
                     guidance=args.guidance,
                     creativity=args.creativity,
                     dream_count=args.dream_count,
                     tokens_per_prompt=args.tokens_per_prompt)
        
        # Add image generation job
        agent.add_job('image_generation', 'explore_narrative',
                     selected_images=selected_images,
                     seed_count=args.seed_count,
                     width=args.width,
                     height=args.height,
                     wildcards=args.wildcards,
                     wildcards_dir=args.wildcards_dir,
                     output_dir=output_dir)
        
        # Execute batch
        shutdown_after = not args.keep_comfyui_running
        agent.execute_batch(shutdown_comfyui_after=shutdown_after, timeout=args.timeout)
    
    elif args.command == 'refine_styles':
        # Prepare project paths
        proj_dir = resolve_project_dir(args.project)
        output_dir = os.path.join(proj_dir, 'style_refine')
        selected_styles_dir = os.path.join(proj_dir, 'selected_styles')
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(selected_styles_dir, exist_ok=True)
        
        # Handle selected styles logic
        if args.selected_styles:
            # Use explicitly provided style images
            selected_styles = args.selected_styles
        else:
            # Auto-discover images in selected_styles folder
            import glob
            image_patterns = ['*.png', '*.jpg', '*.jpeg']
            selected_styles = []
            for pattern in image_patterns:
                selected_styles.extend(glob.glob(os.path.join(selected_styles_dir, pattern)))
            
            if not selected_styles:
                print(f"\n🎨 REFINE STYLES REQUIRES STYLE IMAGES")
                print(f"➡️  Please add style images to: {selected_styles_dir}")
                print(f"📝 Instructions:")
                print(f"   1. Place 3-10 images with diverse LoRA styles in the folder")
                print(f"   2. Run the command again")
                print(f"   3. The system will extract LoRA pools and test combinations")
                print(f"\n📁 Folder created: {selected_styles_dir}")
                return
            else:
                print(f"🎨 Auto-discovered {len(selected_styles)} style images in selected_styles folder")
        
        # Add LLM job
        agent.add_job('llm_generation', 'refine_styles',
                     preset=preset,
                     prompt=args.prompt,
                     guidance=args.guidance,
                     creativity=args.creativity,
                     dream_count=args.dream_count)
        
        # Add image generation job
        agent.add_job('image_generation', 'refine_styles',
                     selected_styles=selected_styles,
                     test_count=args.test_count,
                     width=args.width,
                     height=args.height,
                     wildcards=args.wildcards,
                     wildcards_dir=args.wildcards_dir,
                     k=args.k,
                     strength_min=args.strength_min,
                     strength_max=args.strength_max,
                     output_dir=output_dir)
        
        # Execute batch
        shutdown_after = not args.keep_comfyui_running
        agent.execute_batch(shutdown_comfyui_after=shutdown_after, timeout=args.timeout)
    
    # Add more commands as needed...

if __name__ == "__main__":
    main()
