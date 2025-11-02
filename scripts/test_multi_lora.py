#!/usr/bin/env python3
"""
Test script for the new multi-LoRA functionality

This script tests the dynamic LoRA workflow generation without actually
submitting to ComfyUI - just shows what would be generated.
"""

import sys
import os
import json

# Add the script directory to the path so we can import our modules
script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, script_dir)

from dynamic_lora_workflow import DynamicLoRAWorkflow, LoRAConfig, parse_lora_args


def test_workflow_generation():
    """Test the dynamic workflow generation with various LoRA combinations"""
    
    workflow_path = os.path.join(script_dir, '..', 'ComfyUI', 'user', 'default', 'workflows', 'flux_dev_multi-LoRA.api.json')
    
    if not os.path.exists(workflow_path):
        print(f"❌ Base workflow not found at: {workflow_path}")
        print("Please ensure the ComfyUI workflow file exists.")
        return False
    
    try:
        generator = DynamicLoRAWorkflow(workflow_path)
        print("✅ Successfully loaded base workflow\n")
    except Exception as e:
        print(f"❌ Error loading workflow: {e}")
        return False
    
    # Test cases
    test_cases = [
        {
            "name": "No LoRAs",
            "specs": []
        },
        {
            "name": "Single LoRA",
            "specs": ["test-lora1.safetensors:0.8"]
        },
        {
            "name": "Two LoRAs (legacy equivalent)", 
            "specs": ["test-lora1.safetensors:0.8", "test-lora2.safetensors:0.6"]
        },
        {
            "name": "Three LoRAs",
            "specs": ["lora1.safetensors:0.7", "lora2.safetensors:0.9", "lora3.safetensors:0.5"]
        },
        {
            "name": "Five LoRAs with different clip strengths",
            "specs": [
                "style1.safetensors:0.8:1.0",
                "style2.safetensors:0.6:0.9", 
                "char1.safetensors:0.9:1.1",
                "lighting.safetensors:0.4:0.8",
                "texture.safetensors:0.7:1.0"
            ]
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        print(f"🧪 Testing: {test_case['name']}")
        print(f"   LoRA specs: {test_case['specs']}")
        
        try:
            if test_case['specs']:
                lora_configs = parse_lora_args(test_case['specs'])
            else:
                lora_configs = []
                
            workflow = generator.create_multi_lora_workflow(lora_configs)
            
            # Count LoRA nodes in the generated workflow
            lora_count = sum(1 for node in workflow.values() if node.get('class_type') == 'LoraLoader')
            expected_count = len(lora_configs)
            
            if lora_count == expected_count:
                print(f"   ✅ Generated workflow with {lora_count} LoRA nodes\n")
            else:
                print(f"   ❌ Expected {expected_count} LoRA nodes, got {lora_count}\n")
                all_passed = False
                
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
            all_passed = False
    
    return all_passed


def test_lora_parsing():
    """Test the LoRA specification parsing"""
    print("🧪 Testing LoRA specification parsing:")
    
    test_specs = [
        "simple.safetensors",
        "with-strength.safetensors:0.8",
        "full-spec.safetensors:0.7:0.9",
        "complex-name_v2.safetensors:1.2:0.8"
    ]
    
    try:
        configs = parse_lora_args(test_specs)
        print(f"   ✅ Parsed {len(configs)} LoRA specifications:")
        for config in configs:
            print(f"      {config}")
        print()
        return True
    except Exception as e:
        print(f"   ❌ Error parsing LoRA specs: {e}\n")
        return False


def test_agent_integration():
    """Test that agent.py properly extracts and processes multi-LoRA metadata"""
    print("🧪 Testing agent.py multi-LoRA metadata extraction:")
    
    # Import the extract function
    from agent import extract_metadata_from_png
    
    # Create mock metadata for testing
    import tempfile
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    import json
    
    # Mock workflow data with 3 LoRAs
    workflow_data = {
        "1": {
            "inputs": {"text": "test prompt with multiple LoRAs"},
            "class_type": "CLIPTextEncode"
        },
        "2": {
            "inputs": {
                "lora_name": "Flux-Test-LoRA1.safetensors",
                "strength_model": 0.8,
                "strength_clip": 1.0
            },
            "class_type": "LoraLoader"
        },
        "3": {
            "inputs": {
                "lora_name": "Flux-Test-LoRA2.safetensors", 
                "strength_model": 0.6,
                "strength_clip": 0.9
            },
            "class_type": "LoraLoader"
        },
        "4": {
            "inputs": {
                "lora_name": "Flux-Test-LoRA3.safetensors",
                "strength_model": 0.7,
                "strength_clip": 1.0
            },
            "class_type": "LoraLoader"
        },
        "5": {
            "inputs": {"seed": 12345},
            "class_type": "KSampler"
        }
    }
    
    try:
        # Create a temporary PNG with metadata
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            img = Image.new('RGB', (100, 100), color='red')
            metadata = PngInfo()
            metadata.add_text("prompt", json.dumps(workflow_data))
            img.save(tmp_file.name, "PNG", pnginfo=metadata)
            
            # Test extraction
            prompt_text, loras, seed = extract_metadata_from_png(tmp_file.name)
            
            print(f"   📤 Extracted prompt: {prompt_text[:50]}...")
            print(f"   🧬 Extracted seed: {seed}")
            print(f"   🎛️  Extracted {len(loras)} LoRAs:")
            
            for i, (name, model_str, clip_str) in enumerate(loras, 1):
                print(f"      {i}. {name} - model:{model_str}, clip:{clip_str}")
            
            # Clean up
            os.unlink(tmp_file.name)
            
            if len(loras) == 3:
                print("   ✅ Successfully extracted all 3 LoRAs\n")
                return True
            else:
                print(f"   ❌ Expected 3 LoRAs, got {len(loras)}\n")
                return False
                
    except Exception as e:
        print(f"   ❌ Error testing metadata extraction: {e}\n")
        return False


def main():
    """Run all tests"""
    print("🚀 Testing Multi-LoRA Implementation\n")
    
    parsing_ok = test_lora_parsing()
    workflow_ok = test_workflow_generation()
    agent_ok = test_agent_integration()
    
    if parsing_ok and workflow_ok and agent_ok:
        print("🎉 All tests passed! The multi-LoRA implementation is working correctly.")
        print("\n📋 Usage Examples:")
        print("   # Single LoRA:")
        print("   python run_flux.py --prompt 'test' --name-prefix 'test' --loras 'my-lora.safetensors:0.8'")
        print("\n   # Multiple LoRAs:")
        print("   python run_flux.py --prompt 'test' --name-prefix 'test' --loras 'lora1:0.8' 'lora2:0.6' 'lora3:0.9'")
        print("\n   # With custom clip strengths:")
        print("   python run_flux.py --prompt 'test' --name-prefix 'test' --loras 'style:0.8:1.0' 'char:0.9:1.1'")
        print("\n   # Agent commands now support unlimited LoRAs:")
        print("   python agent.py refine_styles --project MyProject --prompt 'test'")
        print("   python agent.py explore_narrative --project MyProject --prompt 'test'")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
