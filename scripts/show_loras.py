#!/usr/bin/env python3
"""
show_loras.py — Print LoRA names + strengths from ComfyUI-generated PNGs.

- Scans common PNG metadata fields written by ComfyUI (Prompt/Description/Comment/Parameters/UserComment)
- Handles HTML-escaped JSON (ComfyUI often stores JSON as HTML entities)
- Recursively finds LoRA nodes with many possible key names
- Prints model/clip strengths when available; falls back to a single "strength" or "weight"
- If JSON not found, tries a light regex fallback to pair nearby ".safetensors" with strength-looking numbers

Usage:
  python show_loras.py file1.png [file2.png ...]
  python show_loras.py /path/to/dir/*.png
"""
import sys, os, json, html, re, subprocess
from collections import defaultdict

EXIFTOOL = "exiftool"
TAGS = ["-b", "-Prompt", "-Description", "-Comment", "-Parameters", "-UserComment"]

# Keys we’ll consider as potential LoRA-name fields
NAME_KEYS = {"lora_name", "lora", "LoRA", "name", "model_name", "filename"}
# Keys we’ll consider as strength fields
STRENGTH_KEYS_SINGLE = {"strength", "weight", "alpha", "lora_strength"}
STRENGTH_KEYS_MODEL  = {"strength_model", "model_strength", "strengthModel", "model_weight"}
STRENGTH_KEYS_CLIP   = {"strength_clip", "clip_strength", "strengthClip", "clip_weight"}

SAFE_NAME_RE = re.compile(r"[A-Za-z0-9._/\-]+\.safetensors")
NUM_RE = r"([0-9]+(?:\.[0-9]+)?)"

def run_exiftool(path: str) -> str:
    try:
        out = subprocess.check_output([EXIFTOOL, *TAGS, path], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except Exception:
        return ""

def json_candidates(blob: str):
    """Yield best-effort JSON chunks (some files contain multiple)."""
    text = html.unescape(blob).strip()
    # Try whole text first
    yield text
    # Fallback: pull out the largest {...} block if mixed with other text
    # (simple heuristic to catch embedded JSON)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        yield m.group(0)

def walk(obj):
    """Yield all dict objects in nested JSON."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def norm_name(val):
    if not isinstance(val, str):
        return None
    # Prefer safetensors filename if present inside the string
    m = SAFE_NAME_RE.search(val)
    return m.group(0) if m else val.strip()

def collect_from_json(text: str):
    """Return dict: name -> {'model': x or None, 'clip': y or None, 'single': z or None}"""
    results = defaultdict(lambda: {"model": None, "clip": None, "single": None})
    for candidate in json_candidates(text):
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        for node in walk(data):
            # Is this a LoRA-like node? (either has a name key or mentions lora in class/type)
            node_str = " ".join(str(node.get(k, "")) for k in ("class_type", "type", "_meta", "title"))
            looks_lora = "lora" in node_str.lower()
            name_val = None
            for k in NAME_KEYS:
                if k in node:
                    name_val = norm_name(node[k])
                    break
            if not name_val and looks_lora:
                # try common nested spots (e.g., 'inputs': {'lora_name': ...})
                if "inputs" in node and isinstance(node["inputs"], dict):
                    for k in NAME_KEYS:
                        if k in node["inputs"]:
                            name_val = norm_name(node["inputs"][k])
                            break
            if not name_val:
                continue

            # Strength fields can be on node or node['inputs']
            fields = []
            fields.append(node)
            if isinstance(node.get("inputs"), dict):
                fields.append(node["inputs"])

            model = clip = single = None
            for d in fields:
                for k in STRENGTH_KEYS_MODEL:
                    if k in d and isinstance(d[k], (int, float, str)):
                        try: model = float(d[k])
                        except: pass
                for k in STRENGTH_KEYS_CLIP:
                    if k in d and isinstance(d[k], (int, float, str)):
                        try: clip = float(d[k])
                        except: pass
                for k in STRENGTH_KEYS_SINGLE:
                    if k in d and isinstance(d[k], (int, float, str)):
                        try: single = float(d[k])
                        except: pass

            # Update / prefer explicit model/clip; keep single if that’s all we have
            r = results[name_val]
            r["model"]  = r["model"]  if r["model"]  is not None else model
            r["clip"]   = r["clip"]   if r["clip"]   is not None else clip
            r["single"] = r["single"] if r["single"] is not None else single
    return results

def regex_fallback(blob: str):
    """
    If JSON parse fails or strengths aren't explicit, try to pair safetensors with a nearby 'strength' number.
    This is heuristic; it won’t be perfect but often works.
    """
    text = html.unescape(blob)
    lines = text.splitlines()
    pairs = defaultdict(lambda: {"model": None, "clip": None, "single": None})
    last_name = None
    for ln in lines:
        for nm in SAFE_NAME_RE.findall(ln):
            last_name = nm
        # capture strength-like tokens
        # e.g., strength=0.7, strength_model: 0.6, clip_strength 0.4
        for lab, keys in (("model", STRENGTH_KEYS_MODEL), ("clip", STRENGTH_KEYS_CLIP), ("single", STRENGTH_KEYS_SINGLE)):
            for k in keys:
                m = re.search(rf"{re.escape(k)}\s*[:=]\s*{NUM_RE}", ln, flags=re.I)
                if m and last_name:
                    try:
                        val = float(m.group(1))
                        if pairs[last_name][lab] is None:
                            pairs[last_name][lab] = val
                    except:
                        pass
        # generic: "... .safetensors ... 0.XX" on same line
        if last_name:
            m = re.search(rf"{SAFE_NAME_RE.pattern}.*?{NUM_RE}", ln)
            if m and pairs[last_name]["single"] is None:
                try: pairs[last_name]["single"] = float(m.group(1))
                except: pass
    return pairs

def format_rows(mapping):
    rows = []
    for name, vals in sorted(mapping.items()):
        ms = f"{vals['model']:.3f}" if vals["model"] is not None else "N/A"
        cs = f"{vals['clip']:.3f}"  if vals["clip"]  is not None else "N/A"
        ss = f"{vals['single']:.3f}"if vals["single"] is not None else "N/A"
        # Prefer showing model/clip; if both N/A but single exists, show single
        if ms=="N/A" and cs=="N/A" and ss!="N/A":
            rows.append(f"{name}\tstrength={ss}")
        else:
            rows.append(f"{name}\tmodel={ms}\tclip={cs}")
    return rows

def process(path: str):
    blob = run_exiftool(path)
    found = collect_from_json(blob)
    # If nothing found or all strengths missing, try regex fallback to fill gaps
    need_fallback = (not found) or all(v["model"] is None and v["clip"] is None and v["single"] is None for v in found.values())
    if need_fallback:
        fb = regex_fallback(blob)
        # merge fallback into found (or replace if found empty)
        for k, v in fb.items():
            if k not in found:
                found[k] = v
            else:
                for fld in ("model","clip","single"):
                    if found[k][fld] is None and v[fld] is not None:
                        found[k][fld] = v[fld]
    return found

def main():
    if len(sys.argv) < 2:
        print("Usage: show_loras.py file1.png [file2.png ...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        print(f"File: {p}")
        if not os.path.exists(p):
            print("  (not found)\n"); continue
        data = process(p)
        if not data:
            print("  (no LoRAs found)\n"); continue
        for line in format_rows(data):
            print(line)
        print()

if __name__ == "__main__":
    main()

