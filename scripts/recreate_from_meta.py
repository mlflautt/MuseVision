#!/usr/bin/env python3
"""
recreate_from_meta.py

Parses a ComfyUI-generated PNG for embedded Flux LoRA names, strengths, and optionally seed,
then invokes run_flux.py with a new prompt to recreate the same LoRA combination.
Allows specifying an output subfolder directly and seed behavior.
"""
import argparse
import subprocess
import sys
import os
import json
from PIL import Image

# Determine directory of this script
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
# Default run_flux helper in same folder
default_script = os.path.join(SCRIPT_DIR, 'run_flux.py')

# ─── Argument Parsing ──────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Recreate a ComfyUI rendering by extracting LoRA metadata (and optional seed) from an image and re-running the workflow with a new prompt."
)
parser.add_argument(
    "image", help="Path to the ComfyUI-generated PNG image"
)
parser.add_argument(
    "--prompt", "-p", required=True,
    help="New prompt text to use for recreation"
)
parser.add_argument(
    "--script", default=default_script,
    help="Path to the helper script that submits to ComfyUI"
)
parser.add_argument(
    "--output-dir", help="Sub-path under the ComfyUI global output directory for the new images"
)
parser.add_argument(
    "--seed", type=int,
    help="Explicit seed to use (overrides metadata)"
)
parser.add_argument(
    "--use-seed", action='store_true',
    help="Extract and use the seed from the image metadata"
)
args = parser.parse_args()

# ─── Read and parse metadata via embedded JSON ─────────────────────────────────
try:
    img = Image.open(args.image)
    raw_json = img.info.get('prompt')
except Exception as e:
    print(f"Error opening image: {e}", file=sys.stderr)
    sys.exit(1)

if not raw_json:
    print("No prompt-chunk found in PNG metadata.", file=sys.stderr)
    sys.exit(1)

try:
    data = json.loads(raw_json)
except json.JSONDecodeError as e:
    print(f"Error parsing embedded JSON: {e}", file=sys.stderr)
    sys.exit(1)

# ─── Extract LoRA entries and optional seed ────────────────────────────────────
lora_list = []
seed_meta = None

# Collect ALL LoRA loaders (not just first 2)
for node_id, node in data.items():
    ntype = node.get('class_type') or node.get('type')
    if ntype == 'LoraLoader':
        inp = node.get('inputs', {})
        name = inp.get('lora_name')
        strength_model = inp.get('strength_model')
        strength_clip = inp.get('strength_clip', 1.0)  # Default clip strength
        if name:
            lora_list.append((name, strength_model, strength_clip))
    if seed_meta is None and ntype == 'KSampler':
        inp = node.get('inputs', {})
        seed_meta = inp.get('seed')

print(f"🔍 Found {len(lora_list)} LoRA(s) in metadata")

if not lora_list:
    print("No LoraLoader entries found in embedded JSON!", file=sys.stderr)
    sys.exit(1)

# ─── Determine seed behavior ───────────────────────────────────────────────────
final_seed = None
if args.seed is not None:
    final_seed = args.seed
elif args.use_seed:
    if seed_meta is None:
        print("No seed metadata found in image; cannot use metadata seed.", file=sys.stderr)
        sys.exit(1)
    final_seed = seed_meta

# ─── Prepare command args ───────────────────────────────────────────────────────
# Resolve script path
script_path = args.script
if not os.path.isabs(script_path):
    script_path = os.path.join(SCRIPT_DIR, script_path)

cmd = [sys.executable, script_path, "--prompt", args.prompt]

# Add ALL LoRAs using the new --loras argument
if lora_list:
    lora_specs = []
    for name, strength_model, strength_clip in lora_list:
        if strength_model is None:
            strength_model = 1.0
        if strength_clip is None:
            strength_clip = 1.0
            
        # Format LoRA spec based on whether clip strength differs from 1.0
        if strength_clip != 1.0:
            spec = f"{name}:{strength_model}:{strength_clip}"
        else:
            spec = f"{name}:{strength_model}"
        lora_specs.append(spec)
    
    cmd.extend(["--loras"] + lora_specs)
    print(f"🎛️  Recreating with LoRAs: {', '.join([name for name, _, _ in lora_list])}")

# Add seed flag if requested
if final_seed is not None:
    cmd += ["--seed", str(final_seed)]
    print(f"🎯 Using seed: {final_seed}")

# Add optional output directory
if args.output_dir:
    cmd += ["--output-dir", args.output_dir]

# ─── Invoke the helper ────────────────────────────────────────────────────────
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"Error: {os.path.basename(script_path)} exited with code {result.returncode}\n{result.stderr.strip()}", file=sys.stderr)
    sys.exit(result.returncode)
else:
    print(result.stdout.strip())

