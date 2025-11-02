#!/usr/bin/env python3
"""
Runs run_flux.py for a given prompt across either:
  • One fixed set of LoRAs (if --loras supplied)
  • N random Flux LoRA variations (otherwise),
    combining K LoRAs each time with random strengths.
    
Now supports ANY number of LoRAs per combination!
Saves directly into the folder given by --output-dir (relative to ComfyUI's base).
Filename prefixes default to the project name (derived from output-dir), but can be overridden.
"""
import os
import glob
import random
import subprocess
import argparse
import sys

# ─── Locate this script’s directory and default run_flux helper ───────────────
SCRIPT_DIR          = os.path.dirname(os.path.realpath(__file__))
DEFAULT_FLUX_SCRIPT = os.path.join(SCRIPT_DIR, 'run_flux.py')

# ─── CLI Arguments ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Run the ComfyUI workflow with Flux LoRA combinations"
)
parser.add_argument("--prompt", "-p", required=True,
                    help="The positive prompt text to use for all variations")
parser.add_argument("--n", "-n", type=int, default=10,
                    help="Number of random variations to run (ignored if --lora1/2 used)")
parser.add_argument("--k", "-k", type=int, default=2,
                    help="Number of LoRAs to combine per variation")
parser.add_argument("--strength-min", type=float, default=0.5,
                    help="Minimum random LoRA strength (ignored if --lora1-strength used)")
parser.add_argument("--strength-max", type=float, default=1.0,
                    help="Maximum random LoRA strength (ignored if --lora2-strength used)")
parser.add_argument("--loras-dir", default=os.path.expanduser("~/MuseVision/ComfyUI/models/loras"),
                    help="Directory containing Flux LoRA files to sample from")

# Legacy single pair arguments (for backward compatibility)
parser.add_argument("--lora1", help="[LEGACY] Use this LoRA instead of random sampling")
parser.add_argument("--lora1-strength", type=float,
                    help="[LEGACY] Strength for the fixed first LoRA")
parser.add_argument("--lora2", help="[LEGACY] Use this LoRA instead of random sampling")
parser.add_argument("--lora2-strength", type=float,
                    help="[LEGACY] Strength for the fixed second LoRA")
                    
# Multi-LoRA support - fixed combinations or random sampling
parser.add_argument("--loras", nargs='+', metavar="LORA_SPEC",
                    help="Fixed LoRA specs: 'name:model_strength:clip_strength' or 'name:strength' or 'name'. If not provided, will randomly sample from --loras-dir")
parser.add_argument("--fixed-loras", nargs='+', metavar="FIXED_LORA",
                    help="LoRA names that must always be included (e.g., 'Flux1D-Faceless_Gods.safetensors'). Remaining slots filled with random LoRAs")
parser.add_argument("--name-prefix",
                    help="Explicit filename prefix for saved images (overrides default project name)")
parser.add_argument("--script", default=DEFAULT_FLUX_SCRIPT,
                    help="Path to the run_flux.py helper script")
parser.add_argument("--output-dir", default=None,
                    help="Relative sub-path under the ComfyUI projects/ directory where images should be written")

# Wildcard support
parser.add_argument("--wildcards", nargs='*', metavar="WILDCARD_SPEC",
                    help="Wildcard specifications: 'file_name:count:position' or 'all:total_count'")
parser.add_argument("--wildcards-dir", default="/home/mitchellflautt/MuseVision/wildcards",
                    help="Directory containing wildcard .txt files")

# Resolution control
parser.add_argument("--width", type=int, default=720,
                    help="Image width in pixels (default: 720)")
parser.add_argument("--height", type=int, default=1280,
                    help="Image height in pixels (default: 1280)")
args = parser.parse_args()

# ─── Validation ───────────────────────────────────────────────────────────────
if args.k < 1:
    print(f"Error: k must be at least 1 (got k={args.k})", file=sys.stderr)
    sys.exit(1)

# Import the LoRA parsing utilities
try:
    from dynamic_lora_workflow import parse_lora_args
except ImportError:
    print("Error: dynamic_lora_workflow.py not found. Make sure it's in the same directory.", file=sys.stderr)
    sys.exit(1)

# Import wildcard utilities
try:
    from wildcard_prompts import WildcardSystem, WildcardConfig, parse_wildcard_args
except ImportError:
    print("Warning: wildcard_prompts.py not found. Wildcard support disabled.", file=sys.stderr)
    WildcardSystem = None

# Determine if using fixed LoRAs
use_fixed_legacy = bool(args.lora1 and args.lora2)
use_fixed_new = bool(args.loras)
use_mixed_fixed_random = bool(args.fixed_loras)  # New: mixed fixed + random mode
use_fixed = use_fixed_legacy or use_fixed_new

# Validate legacy arguments
if use_fixed_legacy:
    if args.loras:
        print("Warning: Both legacy (--lora1/2) and new (--loras) arguments provided. Using --loras.", file=sys.stderr)
        use_fixed_legacy = False
    elif args.lora1_strength is None or args.lora2_strength is None:
        print("Error: when using --lora1/2 you must also supply --lora1-strength and --lora2-strength",
              file=sys.stderr)
        sys.exit(1)
if not use_fixed:
    # Collect pool of LoRAs for random sampling
    all_loras = glob.glob(os.path.join(args.loras_dir, "*Flux*.safetensors"))
    if not all_loras:
        print(f"No Flux LoRA files found in {args.loras_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Handle mixed fixed + random mode
    if use_mixed_fixed_random:
        # Validate fixed LoRAs exist
        fixed_lora_paths = []
        for fixed_name in args.fixed_loras:
            # Find the full path for this LoRA
            matching_paths = [path for path in all_loras if os.path.basename(path) == fixed_name]
            if not matching_paths:
                print(f"Error: Fixed LoRA '{fixed_name}' not found in {args.loras_dir}", file=sys.stderr)
                sys.exit(1)
            fixed_lora_paths.append(matching_paths[0])
        
        # Check total LoRA requirements
        num_fixed = len(args.fixed_loras)
        if args.k <= num_fixed:
            print(f"Error: k ({args.k}) must be greater than number of fixed LoRAs ({num_fixed})", file=sys.stderr)
            sys.exit(1)
            
        print(f"🔒 Using {num_fixed} fixed LoRA(s): {args.fixed_loras}")
        print(f"🎲 Will randomly select {args.k - num_fixed} additional LoRAs from pool")
    else:
        # Pure random mode
        if args.k > len(all_loras):
            print(f"Error: Requested {args.k} LoRAs but only {len(all_loras)} available", file=sys.stderr)
            sys.exit(1)

# ─── Prepare output folder under ComfyUI base ─────────────────────────────────
user_output_dir = args.output_dir
if user_output_dir:
    comfy_base = os.path.expanduser("~/MuseVision/projects")
    project_folder = os.path.join(comfy_base, user_output_dir)
    os.makedirs(project_folder, exist_ok=True)

# ─── Determine default filename prefix (project name) ─────────────────────────
def default_prefix():
    if user_output_dir and os.sep in user_output_dir:
        return user_output_dir.split(os.sep, 1)[0]
    elif user_output_dir:
        return user_output_dir
    else:
        return 'variation'

# ─── Build list of LoRA combinations to run ───────────────────────────────────
jobs = []

if use_fixed_new:
    # Parse fixed LoRA specifications
    try:
        lora_configs = parse_lora_args(args.loras)
        jobs.append(lora_configs)
        print(f"🔧 Using fixed LoRA combination: {[lora.name for lora in lora_configs]}")
    except ValueError as e:
        print(f"Error parsing LoRA specifications: {e}", file=sys.stderr)
        sys.exit(1)
elif use_fixed_legacy:
    # Convert legacy arguments to new format
    from dynamic_lora_workflow import LoRAConfig
    legacy_configs = [
        LoRAConfig(args.lora1, args.lora1_strength, 1.0),
        LoRAConfig(args.lora2, args.lora2_strength, 1.0)
    ]
    jobs.append(legacy_configs)
    print(f"🔄 Using legacy LoRA pair: {args.lora1}, {args.lora2}")
else:
    from dynamic_lora_workflow import LoRAConfig
    
    if use_mixed_fixed_random:
        # Generate combinations with fixed + random LoRAs
        num_fixed = len(args.fixed_loras)
        num_random = args.k - num_fixed
        
        # Create pool of random LoRAs (excluding fixed ones)
        random_pool = [path for path in all_loras 
                      if os.path.basename(path) not in args.fixed_loras]
        
        if num_random > len(random_pool):
            print(f"Error: Need {num_random} random LoRAs but only {len(random_pool)} available after excluding fixed ones", file=sys.stderr)
            sys.exit(1)
            
        print(f"🎲 Generating {args.n} combinations: {num_fixed} fixed + {num_random} random LoRAs each")
        
        for _ in range(args.n):
            lora_configs = []
            
            # Add fixed LoRAs first
            for fixed_name in args.fixed_loras:
                strength = round(random.uniform(args.strength_min, args.strength_max), 3)
                lora_configs.append(LoRAConfig(fixed_name, strength, 1.0))
            
            # Add random LoRAs
            random_loras = random.sample(random_pool, num_random)
            for lora_path in random_loras:
                name = os.path.basename(lora_path)
                strength = round(random.uniform(args.strength_min, args.strength_max), 3)
                lora_configs.append(LoRAConfig(name, strength, 1.0))
                
            jobs.append(lora_configs)
    else:
        # Generate pure random combinations
        print(f"🎲 Generating {args.n} random combinations of {args.k} LoRAs each")
        
        for _ in range(args.n):
            selected_loras = random.sample(all_loras, args.k)
            lora_configs = []
            for lora_path in selected_loras:
                name = os.path.basename(lora_path)
                strength = round(random.uniform(args.strength_min, args.strength_max), 3)
                lora_configs.append(LoRAConfig(name, strength, 1.0))
            jobs.append(lora_configs)

# ─── Run Variations ───────────────────────────────────────────────────────────
# Choose filename prefix: explicit (--name-prefix) or default (project name)
prefix = args.name_prefix or default_prefix()

for idx, lora_configs in enumerate(jobs, start=1):
    lora_summary = ", ".join([f"{lora.name}({lora.strength_model})" for lora in lora_configs])
    print(f"[{idx}/{len(jobs)}] Running with LoRAs: {lora_summary}")
    
    # Process wildcards for this variation
    enhanced_prompt = args.prompt
    # Check if wildcards argument was provided (not None) rather than if it's truthy
    if args.wildcards is not None and WildcardSystem:
        try:
            files, wildcard_config = parse_wildcard_args(args.wildcards)
            wildcard_config.wildcards_dir = args.wildcards_dir
            
            wildcard_system = WildcardSystem(wildcard_config)
            enhanced_prompt, wildcard_summary = wildcard_system.enhance_prompt(args.prompt, files)
            
            if wildcard_summary:
                wildcard_terms = []
                for file_key, terms in wildcard_summary.items():
                    wildcard_terms.extend(terms)
                print(f"   🎯 Wildcards: {', '.join(wildcard_terms)}")
        except Exception as e:
            print(f"   ⚠️  Wildcard warning: {e}")

    # Resolve run_flux.py path
    script_path = args.script
    if not os.path.isabs(script_path):
        script_path = os.path.join(SCRIPT_DIR, script_path)

    # Assemble run_flux command using new --loras argument
    cmd = [
        sys.executable,
        script_path,
        "--prompt", enhanced_prompt,  # Use wildcard-enhanced prompt
        "--name-prefix", prefix,
    ]
    
    # Add LoRA specifications
    if lora_configs:
        lora_specs = []
        for lora in lora_configs:
            if lora.strength_clip != 1.0:
                spec = f"{lora.name}:{lora.strength_model}:{lora.strength_clip}"
            else:
                spec = f"{lora.name}:{lora.strength_model}"
            lora_specs.append(spec)
        cmd.extend(["--loras"] + lora_specs)
    
    # Add resolution settings
    cmd.extend(["--width", str(args.width), "--height", str(args.height)])
    
    if user_output_dir:
        cmd += ["--output-dir", user_output_dir]

    # Execute the command and pass through prompt_id output
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️  Error in variation {idx}: {result.stderr.strip()}", file=sys.stderr)
    else:
        # Print the full stdout to pass through prompt_id information
        print(result.stdout.strip())
        print(f"✅ Variation {idx} completed")

print("✅ All variations submitted.")

