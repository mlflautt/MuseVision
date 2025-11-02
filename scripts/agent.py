#!/usr/bin/env python3
"""
agent.py — Orchestrator for style exploration and narrative generation using ComfyUI & a local LLM (llama.cpp/GGUF)

Commands:
  explore_styles     Generate LoRA‐style variation batches from dreamed prompts.
  refine_styles      Recombine selected LoRAs for new style variations.
  explore_narrative  Generate new narrative-driven image batches based on selected styled images.

Model switch:
  --llm-preset {qwen7b,qwen32b,mistral7b,custom}
  For 'custom', pass --model-path and optionally --llama-cli, --ctx, --ngl.

Formatting aid:
  --enforce-1toN  → generates a small grammar on the fly to force numbering 1..N (exactly N items).
"""

import argparse
import os
import glob
import subprocess
import sys
import math
import random
import re
import json
import tempfile
from dataclasses import dataclass
from typing import Optional, List, Tuple
from PIL import Image

# ─── Paths & project config ───────────────────────────────────────────────────
SCRIPT_DIR             = os.path.dirname(os.path.realpath(__file__))
PROJECTS_ROOT          = os.path.expanduser('~/MuseVision/projects')
DEFAULT_VARIATIONS     = os.path.join(SCRIPT_DIR, 'run_variations.py')
DEFAULT_RECREATE       = os.path.join(SCRIPT_DIR, 'recreate_from_meta.py')

# ─── LLM defaults (can be overridden via CLI) ─────────────────────────────────
DEFAULT_LLAMA_CLI      = os.path.expanduser('~/MuseVision/llama.cpp/build/bin/llama-cli')
DEFAULT_LIB_PATH       = os.path.expanduser('~/MuseVision/llama.cpp/build/bin')

# Preset model files on your machine
QWEN7B_GGUF            = os.path.expanduser('~/MuseVision/models/LLM/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q5_k_m.gguf')
QWEN32B_GGUF           = os.path.expanduser('~/MuseVision/models/LLM/Qwen2.5-32B-Instruct-GGUF/qwen2.5-32b-instruct-q4_k_m.gguf')
MISTRAL7B_GGUF         = os.path.expanduser('~/MuseVision/models/LLM/Mistral/mistral-7b-instruct-v0.1.Q5_K_M.gguf')

DEFAULT_TOP_P          = 0.9
DEFAULT_TOK_PER_PROMPT = 66
DEFAULT_BUF_FACTOR     = 1.5
DEFAULT_CTX            = int(os.environ.get('LLM_CTX', '8192'))
DEFAULT_NGL            = int(os.environ.get('LLM_NGL', '999'))

# ─── Preset definitions ───────────────────────────────────────────────────────
@dataclass
class ModelPreset:
    name: str
    llama_cli: str
    model_path: str
    ctx: int = DEFAULT_CTX
    ngl: int = DEFAULT_NGL
    top_p: float = DEFAULT_TOP_P

PRESETS = {
    "qwen7b":   ModelPreset("qwen7b",   DEFAULT_LLAMA_CLI, QWEN7B_GGUF,  DEFAULT_CTX, DEFAULT_NGL, DEFAULT_TOP_P),
    "qwen32b":  ModelPreset("qwen32b",  DEFAULT_LLAMA_CLI, QWEN32B_GGUF, 4096,        DEFAULT_NGL, DEFAULT_TOP_P),  # 24GB GPU; modest ctx
    "mistral7b":ModelPreset("mistral7b",DEFAULT_LLAMA_CLI, MISTRAL7B_GGUF,DEFAULT_CTX,DEFAULT_NGL, DEFAULT_TOP_P),
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def next_versioned_dir(base_path, stem='narrative_explore'):
    # returns absolute path like .../narrative_explore_01
    nums = []
    if os.path.isdir(base_path):
        for name in os.listdir(base_path):
            if name.startswith(stem):
                parts = name.split('_')
                try:
                    nums.append(int(parts[-1]))
                except (ValueError, IndexError):
                    pass
    n = max(nums) + 1 if nums else 1
    return os.path.join(base_path, f"{stem}_{n:02d}")

def resolve_project_dir(proj_name):
    if os.path.isabs(proj_name):
        return proj_name
    return os.path.join(PROJECTS_ROOT, proj_name)

def make_numbering_grammar(count: int) -> str:
    """
    Force exactly N items:
      1. <line>\n
      ...
      N. <line>
    """
    lines = ["root  ::= " + " ".join([f"item{i}" for i in range(1, count + 1)])]
    for i in range(1, count + 1):
        if i < count:
            lines.append(f'item{i} ::= "{i}. " line "\\n"')
        else:
            lines.append(f'item{i} ::= "{i}. " line')
    lines += [
        'line ::= [^\\n]+',
    ]
    return "\n".join(lines)

def write_temp_grammar(count: int) -> str:
    gbnf = make_numbering_grammar(count)
    fd, path = tempfile.mkstemp(prefix=f"mv_g_{count}_", suffix=".gbnf")
    with os.fdopen(fd, "w") as f:
        f.write(gbnf)
    return path

def run_llama_cli(prompt: str, total_tokens: int, temp: float, top_p: float,
                  preset: ModelPreset, grammar_path: Optional[str] = None,
                  no_conversation: bool = True) -> Tuple[int, str, str]:
    """
    Launch llama.cpp with chosen preset and return (returncode, stdout, stderr).
    """
    env = {**os.environ, 'LD_LIBRARY_PATH': DEFAULT_LIB_PATH}
    cmd = [
        preset.llama_cli,
        "-m", preset.model_path,
        "--temp", str(temp),
        "--top_p", str(top_p),
        "-c", str(preset.ctx),
        "-n", str(total_tokens),
        "-p", prompt,
        "-ngl", str(preset.ngl),
        "-t", str(os.cpu_count() or 8),
    ]
    if no_conversation:
        cmd.append("--no-conversation")
    cmd.append("--no-display-prompt")
    if grammar_path:
        cmd += ["--grammar-file", grammar_path]

    print("── llama.cpp command ─────────────────────────────────────────────")
    print(" ".join([repr(x) if ' ' in x else x for x in cmd]))
    print("───────────────────────────────────────────────────────────────────")

    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return res.returncode, res.stdout, res.stderr

# ─── LLM-driven prompt generator ──────────────────────────────────────────────
def dream_prompts(seed_prompts: List[str], guidance: str, creativity: float,
                  count: int, tokens_per_prompt: int, buffer_factor: float,
                  preset: ModelPreset, enforce_numbering: bool) -> List[str]:
    """
    Generate `count` text-to-image prompts using the configured LLM (llama.cpp).
    Robust to headings like "Prompt 1:" / "1)" / "1 -".
    """
    instr = [
        "You are a creative storyteller, designing text-to-image prompts.",
        f"Below are {len(seed_prompts)} inspiration prompts (inspiration for content, not length)— creatively expand on the idea(s) to create a new set of vivid narrative prompts, (each one unique and nearly {int(tokens_per_prompt*0.75)} words long).",
        "Inspiration prompt(s)/Direction:",
        *[f"- {p}" for p in seed_prompts],
    ]
    if guidance:
        instr.append(f"Additional guidance: {guidance}")
    instr += [
        "",
        f"Produce exactly {count} prompts, numbered using ONLY '1.', '2.', … '{count}.' (no headings like 'Prompt 1:' or '1)' ).",
        "Each item must be a single self-contained, vivid, aesthetic prompt; if a character appears, fully describe them each time.",
        f"Please make the prompts a length of nearly {tokens_per_prompt} tokens (nearly {int(tokens_per_prompt*0.75)} words, nearly {int(tokens_per_prompt*4)} chars) each, and each vividly unique.",
        "Output only the numbered items.",
    ]
    full_prompt = "\n".join(instr)

    print("----- FULL LLM INPUT -----")
    print(full_prompt)
    print("----- END INPUT -----\n")

    total_tokens = math.ceil(tokens_per_prompt * count * (1 + buffer_factor))

    grammar_path = None
    try:
        if enforce_numbering:
            grammar_path = write_temp_grammar(count)
        print(f"🌀 Dreaming {count} prompts with {preset.name} ({total_tokens} tokens)…")
        rc, out, err = run_llama_cli(
            full_prompt, total_tokens, creativity, preset.top_p, preset, grammar_path, no_conversation=True
        )
    finally:
        if grammar_path and os.path.exists(grammar_path):
            try:
                os.remove(grammar_path)
            except OSError:
                pass

    if rc != 0:
        print("Error invoking LLM:", err, file=sys.stderr)
        return []

    raw = out.strip()
    raw = re.sub(r"\[end of text\]\s*$", "", raw, flags=re.IGNORECASE)

    print("----- RAW LLM OUTPUT -----")
    print(raw)
    print("----- END OUTPUT -----\n")

    # ── Normalization: map "Prompt 1:", "Prompt #1:", "1)", "1 -" → "1. "
    norm = raw
    norm = re.sub(r'(?mi)^\s*Prompt\s*#?\s*(\d+)\s*[:\-–—]\s*', r'\1. ', norm)
    norm = re.sub(r'(?mi)^\s*(\d+)\s*[\)\:\-–—]\s*', r'\1. ', norm)

    # Primary parse: numbered blocks "1. ...", "2. ..." (multiline each)
    pattern = re.compile(r'(?ms)^\s*(\d+)\.\s*(.*?)\s*(?=^\s*\d+\.\s*|\Z)')
    matches = pattern.findall(norm)

    prompts: List[Tuple[int, str]] = []
    for num, text in matches:
        idx = int(num)
        if 1 <= idx <= count:
            clean = re.sub(r'(?mi)^Prompt\s*#?\s*\d+\s*[:\-–—]\s*', '', text).strip()
            clean = " ".join(line.strip() for line in clean.splitlines() if line.strip())
            if clean:
                prompts.append((idx, clean))

    if len(prompts) >= count:
        prompts.sort(key=lambda x: x[0])
        return [t for _, t in prompts[:count]]

    # Fallback: take the first non-empty paragraphs after normalization
    paras = [p.strip() for p in re.split(r'\n\s*\n', norm) if p.strip()]
    return paras[:count]

# ─── PNG metadata parsing ─────────────────────────────────────────────────────
def extract_metadata_from_png(path):
    """Extract metadata from PNG - now supports unlimited LoRAs"""
    raw = Image.open(path).info.get('prompt','')
    data = json.loads(raw) if raw else {}
    prompt_text = ''
    for node in data.values():
        if node.get('class_type') == 'CLIPTextEncode' or node.get('type') == 'CLIPTextEncode':
            txt = node.get('inputs',{}).get('text','')
            if txt.strip():
                prompt_text = txt.strip(); break
    
    # Collect ALL LoRAs (not just first 2)
    loras = []
    for node in data.values():
        if node.get('class_type')=='LoraLoader' or node.get('type')=='LoraLoader':
            inp = node['inputs']
            name = inp.get('lora_name')
            strength_model = inp.get('strength_model')
            strength_clip = inp.get('strength_clip', 1.0)
            if name: 
                loras.append((name, strength_model, strength_clip))
    
    seed_val = None
    for node in data.values():
        if node.get('class_type')=='KSampler' or node.get('type')=='KSampler':
            seed_val = node.get('inputs',{}).get('seed'); break
    return prompt_text, loras, seed_val

# ─── Commands ─────────────────────────────────────────────────────────────────
def cmd_explore_styles(args, preset: ModelPreset):
    proj = resolve_project_dir(args.project)
    out = os.path.join(proj, args.out_subdir or 'style_explore')
    os.makedirs(out, exist_ok=True)
    refine_dir = os.path.join(proj, 'selected_styles')
    os.makedirs(refine_dir, exist_ok=True)

    # Validate LoRA setup
    if not args.loras:
        # Check if LoRA directory exists and has files for random sampling
        if not os.path.isdir(args.loras_dir):
            return print(f'❌ LoRA directory not found: {args.loras_dir}')
        
        import glob
        available_loras = glob.glob(os.path.join(args.loras_dir, "*Flux*.safetensors"))
        if not available_loras:
            return print(f'❌ No Flux LoRA files found in {args.loras_dir}')
        
        if args.k > len(available_loras):
            return print(f'❌ Requested {args.k} LoRAs but only {len(available_loras)} available in {args.loras_dir}')
        
        print(f'🎲 Random LoRA sampling: {len(available_loras)} LoRAs available, using {args.k} per combination')
    else:
        print(f'🎯 Using specific LoRAs: {args.loras}')

    dreamed = dream_prompts(
        [args.prompt], args.guidance, args.creativity,
        args.dream_count, args.tokens_per_prompt, args.buffer_factor,
        preset, args.enforce_1toN
    )
    if not dreamed:
        return print('No dreamed prompts; aborting.')

    for i, p in enumerate(dreamed, 1):
        print(f'🔹 Prompt #{i}: {p}')
        cmd = [sys.executable, args.script or DEFAULT_VARIATIONS,
               '--prompt', p,
               '--n', str(args.n), '--k', str(args.k),
               '--strength-min', str(args.strength_min),
               '--strength-max', str(args.strength_max)]
        
        # Add LoRA configuration
        if args.loras:
            # Use specific LoRAs
            cmd += ['--loras', *args.loras]
        else:
            # Enable random sampling by providing LoRA directory
            cmd += ['--loras-dir', args.loras_dir]
        
        # Add wildcard configuration
        if args.wildcards:
            cmd += ['--wildcards', *args.wildcards]
            if args.wildcards_dir:
                cmd += ['--wildcards-dir', args.wildcards_dir]
        
        # Add resolution settings
        cmd += ['--width', str(args.width), '--height', str(args.height)]
        
        cmd += ['--output-dir', os.path.relpath(out, PROJECTS_ROOT)]
        subprocess.run(cmd, check=True)

def cmd_refine_styles(args, preset: ModelPreset):
    proj = resolve_project_dir(args.project)
    src  = os.path.join(proj, args.selected_dir or 'selected_styles')
    out  = os.path.join(proj, args.out_subdir or 'style_refine')
    os.makedirs(out, exist_ok=True)

    # Collect prompts + existing LoRA combinations (with strengths)
    prompts = []
    combo_to_strengths = {}   # key = tuple(sorted(names)) -> list of (name, model_str, clip_str)
    lora_pool = set()

    for img in glob.glob(f'{src}/*.png'):
        try:
            p, loras, _seed = extract_metadata_from_png(img)
        except ValueError:
            p, loras = extract_metadata_from_png(img); _seed = None
        if p:
            prompts.append(p)
        
        # Extract LoRA names and add to pool
        if loras:
            names = [lora[0] for lora in loras if lora[0]]  # Just names
            lora_pool.update(names)
            
            # Store complete LoRA combination
            if len(names) >= 1:  # Store any combination with at least 1 LoRA
                key = tuple(sorted(names))
                if key not in combo_to_strengths:
                    combo_to_strengths[key] = loras  # Store full (name, model_str, clip_str) tuples

    existing_combos = list(combo_to_strengths.keys())
    if not existing_combos and not args.extra_combos:
        return print('Not enough LoRA combinations in selected images; aborting.')
    if not (args.prompt or prompts):
        return print('No prompt override and no prompts in metadata; aborting.')

    # Build list of combinations to run: all existing + optional extra new combinations
    combos_to_run = list(existing_combos)
    if args.extra_combos:
        pool = sorted(lora_pool)
        if len(pool) < args.k:  # Use args.k instead of hardcoded 2
            return print(f'Not enough distinct LoRAs ({len(pool)}) to create {args.k}-LoRA combinations; aborting.')
        seen = set(existing_combos)
        tries = 0
        import random as _r
        while len(combos_to_run) < len(existing_combos) + args.extra_combos and tries < 10000:
            selected = _r.sample(pool, args.k)
            key = tuple(sorted(selected))
            if key not in seen:
                combos_to_run.append(key); seen.add(key)
            tries += 1
        if len(combos_to_run) < len(existing_combos) + args.extra_combos:
            print(f'Note: only {len(combos_to_run)-len(existing_combos)} new unseen combinations could be formed.')

    # Helpers
    def prompt_for_index(i):
        return args.prompt if args.prompt else prompts[i % len(prompts)]

    def seeds_for_test():
        if args.seed is not None:
            return [args.seed + i for i in range(args.seed_count)]
        if args.seed_count <= 1:
            return [None]
        return [random.getrandbits(64) for _ in range(args.seed_count)]

    def strengths_for_combo(key):
        """Get strengths for a LoRA combination - supports any number of LoRAs"""
        stored_loras = combo_to_strengths.get(key)
        if stored_loras:
            # Use stored strengths, clamped to min/max range
            result = []
            for name, model_str, clip_str in stored_loras:
                if name in key:  # Make sure this LoRA is in our current combination
                    model_str = model_str if model_str is not None else 1.0
                    model_str = min(max(model_str, args.strength_min), args.strength_max)
                    clip_str = clip_str if clip_str is not None else 1.0
                    result.append((name, round(model_str, 3), round(clip_str, 3)))
            if result:
                return result
        
        # Fallback: random strengths for all LoRAs in the combination
        result = []
        for name in key:
            model_str = round(random.uniform(args.strength_min, args.strength_max), 3)
            clip_str = 1.0  # Default clip strength
            result.append((name, model_str, clip_str))
        return result

    # Run - now supports any number of LoRAs
    rel_out = os.path.relpath(out, PROJECTS_ROOT)
    flux_script = args.script or os.path.join(SCRIPT_DIR, 'run_flux.py')
    project_name = os.path.basename(proj)

    total = len(combos_to_run) * args.tests_per_combo * max(1, args.seed_count)
    count = 0
    for combo_idx, key in enumerate(combos_to_run, 1):
        lora_names = list(key)
        combo_prefix = f"{project_name}_style{combo_idx:02d}"

        for ti in range(args.tests_per_combo):
            prom = prompt_for_index(ti)
            lora_configs = strengths_for_combo(key)
            
            for sj, seed_val in enumerate(seeds_for_test(), 1):
                count += 1
                
                # Format display string
                lora_display = "+".join([f"{name}({model_str})" for name, model_str, _ in lora_configs])
                if args.seed_count > 1 or args.tests_per_combo > 1:
                    print(f"[{count}/{total}] {lora_display} • t{ti+1}/{args.tests_per_combo} • s{sj}/{args.seed_count}")
                else:
                    print(f"[{count}/{total}] {lora_display}")

                # Build command using new --loras argument
                cmd = [
                    sys.executable, flux_script,
                    "--prompt", prom,
                    "--name-prefix", combo_prefix,
                    "--output-dir", rel_out
                ]
                
                # Add LoRA specifications
                if lora_configs:
                    lora_specs = []
                    for name, model_str, clip_str in lora_configs:
                        if clip_str != 1.0:
                            spec = f"{name}:{model_str}:{clip_str}"
                        else:
                            spec = f"{name}:{model_str}"
                        lora_specs.append(spec)
                    cmd.extend(["--loras"] + lora_specs)
                
                # Add wildcard specifications
                if args.wildcards:
                    cmd.extend(["--wildcards"] + args.wildcards)
                    if args.wildcards_dir:
                        cmd.extend(["--wildcards-dir", args.wildcards_dir])
                
                # Add resolution settings
                cmd.extend(["--width", str(args.width), "--height", str(args.height)])
                
                if seed_val is not None:
                    cmd += ["--seed", str(seed_val)]
                
                subprocess.run(cmd, check=True)

    print(f"All jobs enqueued to ComfyUI for {out}")

def cmd_explore_narrative(args, preset: ModelPreset):
    proj = resolve_project_dir(args.project)
    seed_path = args.selected_dir or 'selected_images'
    src = os.path.join(proj, seed_path)

    # Decide output folder
    if args.out_subdir:
        out = os.path.join(proj, args.out_subdir)
    else:
        out = next_versioned_dir(proj, 'narrative_explore')
    os.makedirs(out, exist_ok=True)

    # Collect seed images (dir or single file)
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

    # Extract (prompt, loras, seed) for each image
    meta = []
    for img in imgs:
        p, loras, _seed = extract_metadata_from_png(img)
        meta.append((img, p, loras))

    # Determine dreaming sources
    per_image_effective = bool(args.per_image and not args.prompt)
    if args.prompt:
        dream_sources = [args.prompt]          # single override prompt
    else:
        if per_image_effective:
            dream_sources = [p for _img, p, _ in meta if p]
        else:
            dream_sources = [p for _img, p, _ in meta if p]

    if not dream_sources:
        print('Error: no prompt source available (no --prompt and seeds lack prompts).')
        return

    # Generate dreamed prompts
    dreamed_sets = []
    if per_image_effective:
        for psrc in dream_sources:
            dreamed = dream_prompts(
                [psrc], args.guidance, args.creativity,
                args.dream_count, args.tokens_per_prompt, args.buffer_factor,
                preset, args.enforce_1toN
            )
            dreamed_sets.append(dreamed or [])
    else:
        dreamed = dream_prompts(
            dream_sources, args.guidance, args.creativity,
            args.dream_count, args.tokens_per_prompt, args.buffer_factor,
            preset, args.enforce_1toN
        )
        dreamed_sets = [dreamed or []]

    # Render loop
    rel_out   = os.path.relpath(out, PROJECTS_ROOT)
    flux_path = os.path.join(SCRIPT_DIR, 'run_flux.py')
    proj_name = os.path.basename(proj)

    if per_image_effective:
        for (img, _p, loras), dreamed in zip(meta, dreamed_sets):
            if not dreamed:
                print(f'Warning: no prompts dreamed for {os.path.basename(img)}')
                continue

            for idx, new_prompt in enumerate(dreamed, 1):
                print(f'🔄 {os.path.basename(img)} – prompt #{idx}: {new_prompt}')
                for rep in range(args.seed_count):
                    cmd = [sys.executable, flux_path,
                           '--prompt', new_prompt,
                           '--name-prefix', proj_name,
                           '--output-dir', rel_out]
                    
                    # Add LoRA specifications using new --loras format
                    if loras:
                        lora_specs = []
                        for name, model_str, clip_str in loras:
                            if name:
                                if clip_str != 1.0:
                                    spec = f"{name}:{model_str}:{clip_str}"
                                else:
                                    spec = f"{name}:{model_str}"
                                lora_specs.append(spec)
                        if lora_specs:
                            cmd.extend(['--loras'] + lora_specs)
                    
                    # Add wildcard specifications
                    if args.wildcards:
                        cmd.extend(['--wildcards'] + args.wildcards)
                        if args.wildcards_dir:
                            cmd.extend(['--wildcards-dir', args.wildcards_dir])
                    
                    # Add resolution settings
                    cmd.extend(['--width', str(args.width), '--height', str(args.height)])
                    
                    subprocess.run(cmd, check=True)
    else:
        dreamed = dreamed_sets[0]
        if not dreamed:
            print('Error: no prompts generated; aborting.')
            return
        for idx, new_prompt in enumerate(dreamed, 1):
            img_idx = (idx - 1) % len(meta)
            _img, _p, loras = meta[img_idx]
            print(f'🔄 #{idx}: {new_prompt}')

            for rep in range(args.seed_count):
                cmd = [sys.executable, flux_path,
                       '--prompt', new_prompt,
                       '--name-prefix', proj_name,
                       '--output-dir', rel_out]
                
                # Add LoRA specifications using new --loras format
                if loras:
                    lora_specs = []
                    for name, model_str, clip_str in loras:
                        if name:
                            if clip_str != 1.0:
                                spec = f"{name}:{model_str}:{clip_str}"
                            else:
                                spec = f"{name}:{model_str}"
                            lora_specs.append(spec)
                    if lora_specs:
                        cmd.extend(['--loras'] + lora_specs)
                
                # Add wildcard specifications
                if args.wildcards:
                    cmd.extend(['--wildcards'] + args.wildcards)
                    if args.wildcards_dir:
                        cmd.extend(['--wildcards-dir', args.wildcards_dir])
                
                # Add resolution settings
                cmd.extend(['--width', str(args.width), '--height', str(args.height)])
                
                subprocess.run(cmd, check=True)

    print(f'✅ All jobs enqueued to ComfyUI for {out}')

# ─── CLI ──────────────────────────────────────────────────────────────────────
def add_model_switch_args(parser: argparse.ArgumentParser):
    parser.add_argument('--llm-preset', choices=['qwen7b', 'qwen32b', 'mistral7b', 'custom'],
                        default='qwen7b', help='Choose model preset (default: qwen7b)')
    parser.add_argument('--model-path', help='Custom GGUF path (required if --llm-preset=custom)')
    parser.add_argument('--llama-cli', default=DEFAULT_LLAMA_CLI, help='Path to llama.cpp binary (llama-cli or main)')
    parser.add_argument('--ctx', type=int, default=None, help='Context tokens (-c). Defaults to preset or env LLM_CTX')
    parser.add_argument('--ngl', type=int, default=None, help='GPU offload layers (-ngl). Defaults to preset or env LLM_NGL')
    parser.add_argument('--top-p', type=float, default=None, help='top_p (defaults to preset)')
    # accept both hyphen and underscore spellings
    parser.add_argument('--enforce-1toN', dest='enforce_1toN', action='store_true',
                        help='Force exactly 1..N numbered items via tiny grammar')
    parser.add_argument('--enforce_1toN', dest='enforce_1toN', action='store_true',
                        help=argparse.SUPPRESS)

def build_cli():
    p = argparse.ArgumentParser('ComfyUI/LLM agent (Qwen/Mistral via llama.cpp)')
    subs = p.add_subparsers(dest='cmd', required=True)

    # Make these flags valid BEFORE subcommand
    add_model_switch_args(p)

    # explore_styles
    e1 = subs.add_parser('explore_styles')
    e1.add_argument('--project', required=True)
    e1.add_argument('--prompt', required=True)
    e1.add_argument('--guidance', default='')
    e1.add_argument('--n', type=int, default=10)
    e1.add_argument('--k', type=int, default=2)
    e1.add_argument('--strength-min', type=float, default=0.7)
    e1.add_argument('--strength-max', type=float, default=0.9)
    e1.add_argument('--creativity', type=float, default=0.7)
    e1.add_argument('--dream-count', type=int, default=5)
    e1.add_argument('--tokens-per-prompt', type=int, default=DEFAULT_TOK_PER_PROMPT)
    e1.add_argument('--buffer-factor', type=float, default=DEFAULT_BUF_FACTOR)
    e1.add_argument('--out-subdir', default='style_explore', help='Output subfolder (default: style_explore)')
    e1.add_argument('--script')
    e1.add_argument('--loras', nargs='+', help='List of specific LoRA specs to use (name:strength format). If not provided, will randomly sample from --loras-dir')
    e1.add_argument('--loras-dir', default=os.path.expanduser("~/MuseVision/ComfyUI/models/loras"),
                    help='Directory containing LoRA files for random sampling (default: ~/MuseVision/ComfyUI/models/loras)')
    # Wildcard support
    e1.add_argument('--wildcards', nargs='*', metavar='WILDCARD_SPEC',
                    help='Wildcard specifications: "file_name:count:position" or "all:total_count"')
    e1.add_argument('--wildcards-dir', default=os.path.expanduser("~/MuseVision/wildcards"),
                    help='Directory containing wildcard .txt files (default: ~/MuseVision/wildcards)')
    # Resolution control
    e1.add_argument('--width', type=int, default=720,
                    help='Image width in pixels (default: 720)')
    e1.add_argument('--height', type=int, default=1280,
                    help='Image height in pixels (default: 1280)')
    # Also valid AFTER subcommand
    add_model_switch_args(e1)
    e1.set_defaults(func='explore_styles')

    # refine_styles
    e2 = subs.add_parser('refine_styles')
    e2.add_argument('--project', required=True)
    e2.add_argument('--selected-dir')
    e2.add_argument('--prompt')
    e2.add_argument('--tests-per-combo', type=int, default=3)
    e2.add_argument('--seed-count', type=int, default=1)
    e2.add_argument('--seed', type=int)
    e2.add_argument('--extra-combos', type=int, default=0, help='Add this many unseen pairs sampled from the LoRA pool')
    e2.add_argument('--strength-min', type=float, default=0.7)
    e2.add_argument('--strength-max', type=float, default=0.9)
    e2.add_argument('--out-subdir', default='style_refine')
    e2.add_argument('--script')  # optional override for run_flux.py
    # Wildcard support
    e2.add_argument('--wildcards', nargs='*', metavar='WILDCARD_SPEC',
                    help='Wildcard specifications: "file_name:count:position" or "all:total_count"')
    e2.add_argument('--wildcards-dir', default=os.path.expanduser("~/MuseVision/wildcards"),
                    help='Directory containing wildcard .txt files (default: ~/MuseVision/wildcards)')
    # Resolution control
    e2.add_argument('--width', type=int, default=720,
                    help='Image width in pixels (default: 720)')
    e2.add_argument('--height', type=int, default=1280,
                    help='Image height in pixels (default: 1280)')
    add_model_switch_args(e2)
    e2.set_defaults(func='refine_styles')

    # explore_narrative
    e3 = subs.add_parser('explore_narrative')
    e3.add_argument('--project',      required=True)
    e3.add_argument('--selected-dir', default='selected_images', help='Directory or single PNG seed')
    e3.add_argument('--prompt',       help='Override seed prompts; disables --per-image')
    e3.add_argument('--guidance',     default='')
    e3.add_argument('--creativity',   type=float, default=0.7)
    e3.add_argument('--dream-count',  type=int,   default=5)
    e3.add_argument('--tokens-per-prompt', type=int, default=DEFAULT_TOK_PER_PROMPT)
    e3.add_argument('--buffer-factor',     type=float, default=DEFAULT_BUF_FACTOR)
    e3.add_argument('--out-subdir',   help='If omitted, will auto-version as narrative_explore_XX')
    e3.add_argument('--per-image', action='store_true', help='Dream prompts per image (ignored if --prompt is set)')
    e3.add_argument('--recreate-script')
    e3.add_argument('--seed-count', type=int, default=1, help='Number of seed variations per dreamed prompt')
    # Wildcard support
    e3.add_argument('--wildcards', nargs='*', metavar='WILDCARD_SPEC',
                    help='Wildcard specifications: "file_name:count:position" or "all:total_count"')
    e3.add_argument('--wildcards-dir', default=os.path.expanduser("~/MuseVision/wildcards"),
                    help='Directory containing wildcard .txt files (default: ~/MuseVision/wildcards)')
    # Resolution control
    e3.add_argument('--width', type=int, default=720,
                    help='Image width in pixels (default: 720)')
    e3.add_argument('--height', type=int, default=1280,
                    help='Image height in pixels (default: 1280)')
    add_model_switch_args(e3)
    e3.set_defaults(func='explore_narrative')

    return p

def resolve_preset(args) -> ModelPreset:
    if args.llm_preset == 'custom':
        if not args.model_path:
            raise SystemExit("--model-path is required when --llm-preset=custom")
        preset = ModelPreset("custom", args.llama_cli, args.model_path,
                             args.ctx or DEFAULT_CTX,
                             args.ngl if args.ngl is not None else DEFAULT_NGL,
                             args.top_p if args.top_p is not None else DEFAULT_TOP_P)
    else:
        preset = PRESETS[args.llm_preset]
        # overrides if provided
        llama_cli = args.llama_cli or preset.llama_cli
        model_path = args.model_path or preset.model_path
        ctx = args.ctx or preset.ctx
        ngl = args.ngl if args.ngl is not None else preset.ngl
        top_p = args.top_p if args.top_p is not None else preset.top_p
        preset = ModelPreset(args.llm_preset, llama_cli, model_path, ctx, ngl, top_p)

    # sanity checks
    if not os.path.exists(preset.llama_cli):
        # try common alternate name 'main'
        alt = preset.llama_cli.replace('llama-cli', 'main')
        if os.path.exists(alt):
            preset.llama_cli = alt
        else:
            raise SystemExit(f"llama.cpp binary not found: {preset.llama_cli}")
    if not os.path.exists(preset.model_path):
        raise SystemExit(f"Model file not found: {preset.model_path}")
    return preset

def main():
    p = build_cli()
    args = p.parse_args()
    preset = resolve_preset(args)

    # Route subcommand
    if args.func == 'explore_styles':
        cmd_explore_styles(args, preset)
    elif args.func == 'refine_styles':
        cmd_refine_styles(args, preset)
    elif args.func == 'explore_narrative':
        cmd_explore_narrative(args, preset)
    else:
        raise SystemExit("Unknown command")

if __name__=='__main__':
    main()

