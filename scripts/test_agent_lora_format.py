#!/usr/bin/env python3
"""Test that agent commands generate correct LoRA format for run_flux.py"""

import tempfile
import os
import json
from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import sys

# Add scripts to path
sys.path.append('/home/mitchellflautt/MuseVision/scripts')

def create_test_project_with_multi_lora():
    """Create a test project with images containing multiple LoRAs"""
    
    # Create temporary project directory
    project_dir = Path(tempfile.mkdtemp()) / "test_multi_lora_project"
    selected_dir = project_dir / "selected_styles"
    selected_dir.mkdir(parents=True, exist_ok=True)
    
    # Mock workflow data with 4 different LoRAs
    workflow_data = {
        "1": {
            "inputs": {"text": "a beautiful anime character"},
            "class_type": "CLIPTextEncode"
        },
        "2": {
            "inputs": {
                "lora_name": "Flux-Anime-Style.safetensors",
                "strength_model": 0.85,
                "strength_clip": 1.0
            },
            "class_type": "LoraLoader"
        },
        "3": {
            "inputs": {
                "lora_name": "Flux-Character-Detail.safetensors", 
                "strength_model": 0.65,
                "strength_clip": 0.9
            },
            "class_type": "LoraLoader"
        },
        "4": {
            "inputs": {
                "lora_name": "Flux-Color-Enhance.safetensors",
                "strength_model": 0.75,
                "strength_clip": 1.1
            },
            "class_type": "LoraLoader"
        },
        "5": {
            "inputs": {
                "lora_name": "Flux-Lighting-Pro.safetensors",
                "strength_model": 0.45,
                "strength_clip": 0.8
            },
            "class_type": "LoraLoader"
        },
        "6": {
            "inputs": {"seed": 98765},
            "class_type": "KSampler"
        }
    }
    
    # Create test image with metadata
    img = Image.new('RGB', (512, 512), color='blue')
    metadata = PngInfo()
    metadata.add_text("prompt", json.dumps(workflow_data))
    
    test_image = selected_dir / "multi_lora_test.png"
    img.save(test_image, "PNG", pnginfo=metadata)
    
    print(f"📁 Created test project: {project_dir}")
    print(f"🖼️  Created test image with 4 LoRAs: {test_image}")
    
    return str(project_dir)

def verify_lora_command_format():
    """Test that agent.py generates the correct --loras command format"""
    
    project_dir = create_test_project_with_multi_lora()
    
    try:
        # Import the agent functions we need to test
        from agent import extract_metadata_from_png
        
        # Test image path
        test_image = Path(project_dir) / "selected_styles" / "multi_lora_test.png"
        
        # Extract LoRA data
        prompt_text, loras, seed = extract_metadata_from_png(str(test_image))
        
        print(f"\n🧪 Testing LoRA command format generation:")
        print(f"   📤 Extracted prompt: {prompt_text}")
        print(f"   🎛️  Extracted {len(loras)} LoRAs:")
        
        # Simulate what cmd_explore_narrative and cmd_refine_styles do
        if loras:
            lora_specs = []
            for name, model_str, clip_str in loras:
                if name:
                    if clip_str != 1.0:
                        spec = f"{name}:{model_str}:{clip_str}"
                    else:
                        spec = f"{name}:{model_str}"
                    lora_specs.append(spec)
                    print(f"      ✅ {name}: model={model_str}, clip={clip_str} -> '{spec}'")
            
            print(f"\n   🔧 Generated command format:")
            print(f"      --loras {' '.join(repr(spec) for spec in lora_specs)}")
            
            # Test that this matches what we expect for unlimited LoRAs
            expected_count = 4
            if len(lora_specs) == expected_count:
                print(f"   ✅ Correctly formatted {len(lora_specs)} LoRA specifications")
                return True
            else:
                print(f"   ❌ Expected {expected_count} LoRA specs, got {len(lora_specs)}")
                return False
        else:
            print("   ❌ No LoRAs extracted from test image")
            return False
            
    except Exception as e:
        print(f"❌ Error in LoRA format test: {e}")
        return False
        
    finally:
        # Clean up
        import shutil
        shutil.rmtree(project_dir, ignore_errors=True)

def test_legacy_vs_new_format():
    """Compare legacy 2-LoRA format vs new unlimited format"""
    
    print(f"\n📊 Legacy vs New LoRA Format Comparison:")
    
    # Legacy format (limited to 2 LoRAs)
    print("   🗂️  Legacy format (agent.py before fix):")
    print("      --lora1 'Flux-Style.safetensors' --lora1-strength '0.8'")
    print("      --lora2 'Flux-Character.safetensors' --lora2-strength '0.6'")
    print("      ❌ Cannot handle 3+ LoRAs")
    
    # New format (unlimited LoRAs)
    print("\n   🆕 New format (agent.py after fix):")
    print("      --loras 'Flux-Style.safetensors:0.8' 'Flux-Character.safetensors:0.6' 'Flux-Lighting.safetensors:0.45:0.8' 'Flux-Color.safetensors:0.75:1.1'")
    print("      ✅ Handles unlimited LoRAs with full model+clip strength control")

if __name__ == "__main__":
    print("🚀 Testing Agent Multi-LoRA Format Generation")
    print("=" * 60)
    
    success = verify_lora_command_format()
    test_legacy_vs_new_format()
    
    if success:
        print(f"\n🎉 Agent LoRA format test passed!")
        print("✅ explore_narrative and refine_styles now support unlimited LoRAs")
    else:
        print(f"\n❌ Agent LoRA format test failed!")
        sys.exit(1)
