#!/usr/bin/env python3
"""
Headless ComfyUI runner with dynamic prompt, unlimited LoRA support, filename prefix,
explicit seed management, and optional output directory.

Now supports any number of LoRAs using dynamic workflow generation!
"""
import os
import sys
import json
import uuid
import random
import requests
import argparse
import tempfile
from pathlib import Path

# Import our dynamic LoRA workflow generator
from dynamic_lora_workflow import DynamicLoRAWorkflow, LoRAConfig, parse_lora_args
# Import wildcard system
from wildcard_prompts import WildcardSystem, WildcardConfig, parse_wildcard_args
# Import checkpoint management system
from checkpoint_manager import CheckpointManager, ModelArchitecture

# ─── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_WORKFLOW = os.path.normpath(
    os.path.join(SCRIPT_DIR, '..', 'ComfyUI', 'user', 'default', 'workflows', 'flux_dev_multi-LoRA.api.json')
)

# ─── CLI Argument Parsing ─────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Submit a ComfyUI workflow with custom prompt, unlimited LoRA support, "
                "filename prefix, seed control, and optional output directory"
)
parser.add_argument("-p", "--prompt", required=True, help="Positive prompt text")

# Legacy LoRA arguments (for backward compatibility)
parser.add_argument("--lora1", metavar="LORA1", help="[LEGACY] First LoRA file name")
parser.add_argument("--lora1-strength", type=float, metavar="STR1", help="[LEGACY] Strength of first LoRA")
parser.add_argument("--lora2", metavar="LORA2", help="[LEGACY] Second LoRA file name")
parser.add_argument("--lora2-strength", type=float, metavar="STR2", help="[LEGACY] Strength of second LoRA")

# New multi-LoRA support
parser.add_argument("--loras", nargs='*', metavar="LORA_SPEC",
                    help="LoRA specifications: 'name:model_strength:clip_strength' or 'name:strength' or 'name'")

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

parser.add_argument("-n", "--name-prefix", required=True,
                    help="Filename prefix for saved images (e.g. 'dungeonsynth')")
parser.add_argument("--output-dir", help="Sub-path under ComfyUI global output dir (e.g. 'projects/myproj/stage1')")
parser.add_argument("--seed", type=int,
                    help="If provided, use this fixed seed; otherwise a fresh random seed is generated")
# Checkpoint management
parser.add_argument("--checkpoint", metavar="CHECKPOINT",
                    help="Specific checkpoint to use (filename). If not provided, auto-detects based on LoRA architecture")
parser.add_argument("--auto-checkpoint", action="store_true", default=True,
                    help="Automatically select compatible checkpoint for LoRA architecture (default: enabled)")
parser.add_argument("--no-auto-checkpoint", action="store_true",
                    help="Disable automatic checkpoint selection (requires --checkpoint)")

parser.add_argument("-w", "--workflow", default=DEFAULT_WORKFLOW,
                    help="Path to the ComfyUI workflow JSON")
parser.add_argument("--api-url", default="http://127.0.0.1:8188/prompt",
                    help="ComfyUI prompt endpoint URL")
args = parser.parse_args()

# Handle checkpoint auto-selection flag logic
if args.no_auto_checkpoint:
    args.auto_checkpoint = False

# Initialize checkpoint manager
workflow_path = args.workflow if os.path.isabs(args.workflow) else os.path.join(SCRIPT_DIR, args.workflow)
# Find ComfyUI directory by looking for 'ComfyUI' in the path
path_parts = workflow_path.split(os.sep)
if 'ComfyUI' in path_parts:
    comfyui_index = path_parts.index('ComfyUI') + 1
    comfyui_path = os.sep.join(path_parts[:comfyui_index])
else:
    # Fallback: assume ComfyUI is one level up from scripts
    comfyui_path = os.path.join(SCRIPT_DIR, '..', 'ComfyUI')
    comfyui_path = os.path.normpath(comfyui_path)

checkpoint_manager = CheckpointManager(comfyui_path)

# ─── Prepare LoRA Configuration ───────────────────────────────────────────────
lora_configs = []

# Handle legacy LoRA arguments for backward compatibility
if args.lora1 or args.lora2:
    if args.loras:
        print("⚠️  Warning: Both legacy (--lora1/2) and new (--loras) arguments provided. Using --loras.")
    else:
        print("🔄 Converting legacy LoRA arguments to new format")
        if args.lora1:
            strength = args.lora1_strength if args.lora1_strength is not None else 1.0
            lora_configs.append(LoRAConfig(args.lora1, strength, 1.0))
        if args.lora2:
            strength = args.lora2_strength if args.lora2_strength is not None else 1.0
            lora_configs.append(LoRAConfig(args.lora2, strength, 1.0))

# Handle new multi-LoRA arguments
if args.loras:
    try:
        lora_configs = parse_lora_args(args.loras)
    except ValueError as e:
        print(f"❌ Error parsing LoRA specifications: {e}", file=sys.stderr)
        sys.exit(1)

print(f"🎛️  Using {len(lora_configs)} LoRAs: {[lora.name for lora in lora_configs]}")

# ─── Checkpoint Selection and Validation ─────────────────────────────────────────
selected_checkpoint = None
selected_workflow = args.workflow

if lora_configs and args.auto_checkpoint:
    # Auto-detect architecture based on first LoRA
    first_lora = lora_configs[0]
    lora_path = None
    
    # Find the LoRA file
    lora_dirs = [
        Path(comfyui_path) / "models" / "loras",
        Path(comfyui_path) / "models" / "loras" / "flux",
        Path(comfyui_path) / "models" / "loras" / "sdxl"
    ]
    
    for lora_dir in lora_dirs:
        candidate_path = lora_dir / first_lora.name
        if candidate_path.exists():
            lora_path = candidate_path
            break
    
    if lora_path:
        lora_info = checkpoint_manager.analyze_lora_architecture(lora_path)
        print(f"🔍 LoRA Architecture: {lora_info.architecture.value.upper()} ({lora_info.confidence:.1%} confidence)")
        
        if lora_info.architecture != ModelArchitecture.UNKNOWN:
            compatible_checkpoint = checkpoint_manager.find_compatible_checkpoint(lora_info.architecture)
            
            if compatible_checkpoint:
                selected_checkpoint = compatible_checkpoint.name
                print(f"🎯 Auto-selected checkpoint: {selected_checkpoint} ({compatible_checkpoint.architecture.value.upper()})")
                
                # Try to get appropriate workflow
                workflow_path = checkpoint_manager.get_workflow_path(lora_info.architecture)
                if workflow_path:
                    selected_workflow = str(workflow_path)
                    print(f"📋 Using {lora_info.architecture.value.upper()} workflow: {workflow_path.name}")
            else:
                print(f"⚠️  No compatible {lora_info.architecture.value.upper()} checkpoints found, using default")
        else:
            print(f"⚠️  Could not determine LoRA architecture: {lora_info.details}")
    else:
        print(f"⚠️  LoRA file not found: {first_lora.name}")

elif args.checkpoint:
    selected_checkpoint = args.checkpoint
    print(f"📌 Using manually specified checkpoint: {selected_checkpoint}")
    
    # Validate the checkpoint exists and get its architecture
    checkpoint_path = Path(comfyui_path) / "models" / "checkpoints" / selected_checkpoint
    if checkpoint_path.exists():
        checkpoint_info = checkpoint_manager.detect_checkpoint_architecture(checkpoint_path)
        print(f"🔍 Checkpoint Architecture: {checkpoint_info.architecture.value.upper()} ({checkpoint_info.confidence:.1%} confidence)")
        
        # Try to get appropriate workflow
        if checkpoint_info.architecture != ModelArchitecture.UNKNOWN:
            workflow_path = checkpoint_manager.get_workflow_path(checkpoint_info.architecture)
            if workflow_path:
                selected_workflow = str(workflow_path)
                print(f"📋 Using {checkpoint_info.architecture.value.upper()} workflow: {workflow_path.name}")
        
        # Validate LoRA compatibility if we have LoRAs
        if lora_configs:
            first_lora = lora_configs[0]
            lora_path = None
            
            for lora_dir in lora_dirs:
                candidate_path = lora_dir / first_lora.name
                if candidate_path.exists():
                    lora_path = candidate_path
                    break
            
            if lora_path:
                lora_info = checkpoint_manager.analyze_lora_architecture(lora_path)
                is_compatible, compatibility_msg = checkpoint_manager.validate_compatibility(checkpoint_info, lora_info)
                
                if not is_compatible:
                    print(f"⚠️  Warning: {compatibility_msg}")
                    print(f"🤔 You may want to select a different checkpoint or LoRA for better results")
                else:
                    print(f"✅ Compatibility: {compatibility_msg}")
    else:
        print(f"❌ Error: Checkpoint file not found: {checkpoint_path}")
        sys.exit(1)

# Update workflow path for the rest of the script
args.workflow = selected_workflow

# ─── Process Wildcards ──────────────────────────────────────────────────────────
enhanced_prompt = args.prompt.strip()
wildcard_summary = {}

if args.wildcards is not None:
    try:
        files, wildcard_config = parse_wildcard_args(args.wildcards)
        wildcard_config.wildcards_dir = args.wildcards_dir
        
        wildcard_system = WildcardSystem(wildcard_config)
        enhanced_prompt, wildcard_summary = wildcard_system.enhance_prompt(enhanced_prompt, files)
        
        if wildcard_summary:
            print(f"🎯 Enhanced prompt with wildcards:")
            wildcard_system.print_summary(wildcard_summary)
        else:
            print(f"🎯 No wildcards applied (all terms may have been duplicates)")
            
    except Exception as e:
        print(f"⚠️  Warning: Wildcard processing failed: {e}")
        enhanced_prompt = args.prompt.strip()

# ─── Generate Dynamic Workflow ─────────────────────────────────────────────────
wf_path = args.workflow if os.path.isabs(args.workflow) else os.path.join(SCRIPT_DIR, args.workflow)
if not os.path.isfile(wf_path):
    print(f"Workflow file not found: {wf_path}", file=sys.stderr)
    sys.exit(1)

try:
    generator = DynamicLoRAWorkflow(wf_path)
    wf = generator.create_multi_lora_workflow(lora_configs)
except Exception as e:
    print(f"❌ Error generating dynamic workflow: {e}", file=sys.stderr)
    sys.exit(1)

# ─── Update Workflow Settings ─────────────────────────────────────────────────
# The LoRAs are already configured by the dynamic workflow generator
# Now we just need to update other settings

# 1) Update checkpoint if selected
if selected_checkpoint:
    for node_id, node_data in wf.items():
        if node_data.get('class_type') == 'CheckpointLoaderSimple':
            wf[node_id]["inputs"]["ckpt_name"] = selected_checkpoint
            print(f"📦 Updated workflow checkpoint: {selected_checkpoint}")
            break

# 2) Update prompt in the CLIPTextEncode node
for node_id, node_data in wf.items():
    if node_data.get('class_type') == 'CLIPTextEncode' and 'text' in node_data.get('inputs', {}):
        if node_data['inputs']['text'].strip() or node_data.get('_meta', {}).get('title', '').find('Positive') != -1:
            wf[node_id]["inputs"]["text"] = enhanced_prompt + "\n"
            break

# 3) Filename prefix + optional output-dir
prefix = args.name_prefix
if args.output_dir:
    # SaveImage will place images under this folder
    prefix = f"{args.output_dir}/{args.name_prefix}"

# Find SaveImage node and update filename prefix
for node_id, node_data in wf.items():
    if node_data.get('class_type') == 'SaveImage':
        wf[node_id]["inputs"]["filename_prefix"] = prefix
        break

# 4) Seed management
if args.seed is not None:
    seed = args.seed
    print(f"🔢 Using fixed seed: {seed}")
else:
    seed = random.getrandbits(64)

# Find KSampler node and update seed
for node_id, node_data in wf.items():
    if node_data.get('class_type') == 'KSampler':
        wf[node_id]["inputs"]["seed"] = seed
        break

# 5) Resolution control
print(f"📐 Setting resolution: {args.width}x{args.height}")

# Find EmptySD3LatentImage node and update resolution
for node_id, node_data in wf.items():
    if node_data.get('class_type') == 'EmptySD3LatentImage':
        wf[node_id]["inputs"]["width"] = args.width
        wf[node_id]["inputs"]["height"] = args.height
        break

# ─── Submit to ComfyUI ────────────────────────────────────────────────────────
client_id = str(uuid.uuid4())
payload = {"prompt": wf, "client_id": client_id}

try:
    resp = requests.post(args.api_url, json=payload)
    resp.raise_for_status()
except requests.RequestException as e:
    print(f"❌ Failed to submit workflow: {e}", file=sys.stderr)
    sys.exit(1)

prompt_id = resp.json().get("prompt_id")
if lora_configs:
    lora_summary = ", ".join([f"{lora.name}({lora.strength_model})" for lora in lora_configs])
    print(f"✅ Successfully submitted to ComfyUI (prompt_id: {prompt_id}) with {len(lora_configs)} LoRAs: {lora_summary}")
else:
    print(f"✅ Successfully submitted to ComfyUI (prompt_id: {prompt_id}) with no LoRAs")

