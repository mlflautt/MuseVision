#!/usr/bin/env python3
"""Debug resolution argument passing in run_variations.py"""

import subprocess
import sys
import tempfile
import os

# Create temporary LoRA files
with tempfile.TemporaryDirectory() as temp_dir:
    # Create mock LoRA files
    for i in range(2):
        mock_lora = os.path.join(temp_dir, f"Flux-Test-{i}.safetensors")
        with open(mock_lora, 'w') as f:
            f.write("mock")
    
    # Test run_variations with resolution arguments
    cmd = [
        sys.executable, "run_variations.py",
        "--prompt", "debug test",
        "--n", "1",
        "--k", "1",
        "--loras-dir", temp_dir,
        "--width", "1024", 
        "--height", "768"
    ]
    
    print("🔍 Running command:")
    print(" ".join(cmd))
    print()
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/mitchellflautt/MuseVision/scripts")
    
    print("📤 STDOUT:")
    print(result.stdout)
    print("📥 STDERR:")  
    print(result.stderr)
    print(f"Return code: {result.returncode}")
    
    # Check if resolution arguments appear in the output
    full_output = result.stdout + result.stderr
    if "--width 1024" in full_output and "--height 768" in full_output:
        print("\n✅ Resolution arguments found in output!")
    else:
        print("\n❌ Resolution arguments not found")
        print("Looking for: --width 1024 and --height 768")
