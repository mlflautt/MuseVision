#!/usr/bin/env python3
"""
Debug script to examine workflow generation issues with multi-LoRA combinations.

This script will:
1. Test the dynamic workflow generation
2. Examine the generated JSON structure
3. Try to identify what's causing the 400 error
4. Test with different LoRA combinations
"""

import sys
import os
import json
import tempfile
import glob
import requests

# Add the script directory to the path
script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, script_dir)

from dynamic_lora_workflow import DynamicLoRAWorkflow, LoRAConfig, parse_lora_args


def test_lora_directory():
    """Check what LoRAs are available"""
    loras_dir = os.path.expanduser("~/MuseVision/ComfyUI/models/loras")
    
    print(f"🔍 Checking LoRA directory: {loras_dir}")
    
    if not os.path.exists(loras_dir):
        print(f"❌ LoRA directory does not exist: {loras_dir}")
        return []
    
    lora_files = glob.glob(os.path.join(loras_dir, "*Flux*.safetensors"))
    print(f"📁 Found {len(lora_files)} Flux LoRA files:")
    
    for i, lora_file in enumerate(lora_files[:10]):  # Show first 10
        basename = os.path.basename(lora_file)
        size = os.path.getsize(lora_file) / (1024*1024)  # MB
        print(f"   {i+1:2d}. {basename} ({size:.1f}MB)")
    
    if len(lora_files) > 10:
        print(f"   ... and {len(lora_files) - 10} more")
    
    return lora_files


def test_workflow_generation(lora_count=5):
    """Test generating workflow with specified number of LoRAs"""
    print(f"\n🔧 Testing workflow generation with {lora_count} LoRAs...")
    
    # Get available LoRAs
    lora_files = test_lora_directory()
    if len(lora_files) < lora_count:
        print(f"❌ Not enough LoRAs available. Need {lora_count}, found {len(lora_files)}")
        return None
    
    # Create test LoRA configs
    import random
    selected_files = random.sample(lora_files, lora_count)
    lora_configs = []
    
    for lora_file in selected_files:
        name = os.path.basename(lora_file)
        strength = round(random.uniform(0.5, 1.0), 2)
        lora_configs.append(LoRAConfig(name, strength, 1.0))
    
    print(f"🎯 Testing with LoRAs:")
    for i, config in enumerate(lora_configs):
        print(f"   {i+1}. {config.name} (strength: {config.strength_model})")
    
    # Test workflow generation
    try:
        workflow_path = os.path.join(script_dir, '..', 'ComfyUI', 'user', 'default', 'workflows', 'flux_dev_multi-LoRA.api.json')
        
        if not os.path.exists(workflow_path):
            print(f"❌ Base workflow not found: {workflow_path}")
            return None
        
        generator = DynamicLoRAWorkflow(workflow_path)
        workflow = generator.create_multi_lora_workflow(lora_configs)
        
        print(f"✅ Workflow generated successfully")
        
        # Analyze the generated workflow
        analyze_workflow(workflow, lora_configs)
        
        return workflow, lora_configs
        
    except Exception as e:
        print(f"❌ Error generating workflow: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_workflow(workflow, lora_configs):
    """Analyze the generated workflow for potential issues"""
    print(f"\n🔍 Analyzing generated workflow...")
    
    # Count nodes by type
    node_types = {}
    lora_nodes = {}
    
    for node_id, node_data in workflow.items():
        class_type = node_data.get('class_type', 'Unknown')
        node_types[class_type] = node_types.get(class_type, 0) + 1
        
        if class_type == 'LoraLoader':
            inputs = node_data.get('inputs', {})
            lora_name = inputs.get('lora_name', 'Unknown')
            strength_model = inputs.get('strength_model', 'Unknown')
            lora_nodes[node_id] = {
                'name': lora_name,
                'strength_model': strength_model,
                'strength_clip': inputs.get('strength_clip', 1.0)
            }
    
    print(f"📊 Node type counts:")
    for node_type, count in sorted(node_types.items()):
        print(f"   {node_type}: {count}")
    
    print(f"\n🎛️ LoRA nodes:")
    for node_id, lora_info in lora_nodes.items():
        print(f"   Node {node_id}: {lora_info['name']} (model: {lora_info['strength_model']}, clip: {lora_info['strength_clip']})")
    
    # Check for potential issues
    issues = []
    
    # Check if we have the expected number of LoRA nodes
    expected_loras = len(lora_configs)
    actual_loras = len(lora_nodes)
    if actual_loras != expected_loras:
        issues.append(f"LoRA count mismatch: expected {expected_loras}, got {actual_loras}")
    
    # Check for broken connections
    for node_id, node_data in workflow.items():
        inputs = node_data.get('inputs', {})
        for input_name, input_value in inputs.items():
            if isinstance(input_value, list) and len(input_value) == 2:
                referenced_node = input_value[0]
                if referenced_node not in workflow:
                    issues.append(f"Node {node_id} references missing node {referenced_node}")
    
    # Check for missing required nodes
    required_nodes = ['CheckpointLoaderSimple', 'CLIPTextEncode', 'KSampler', 'SaveImage']
    for required in required_nodes:
        if required not in node_types:
            issues.append(f"Missing required node type: {required}")
    
    if issues:
        print(f"\n⚠️ Potential issues found:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"\n✅ No obvious issues detected")
    
    return issues


def test_comfyui_submission(workflow, test_prompt="a mystical forest guardian"):
    """Test submitting the workflow to ComfyUI"""
    print(f"\n🚀 Testing ComfyUI submission...")
    
    # Update the prompt in the workflow
    for node_id, node_data in workflow.items():
        if node_data.get('class_type') == 'CLIPTextEncode' and 'text' in node_data.get('inputs', {}):
            # Look for positive prompt (usually has more text or specific markers)
            current_text = node_data['inputs']['text'].strip()
            if current_text or 'Positive' in node_data.get('_meta', {}).get('title', ''):
                workflow[node_id]['inputs']['text'] = test_prompt + "\n"
                print(f"   Updated prompt in node {node_id}")
                break
    
    # Generate a random seed
    import random
    seed = random.getrandbits(64)
    
    # Update seed in KSampler
    for node_id, node_data in workflow.items():
        if node_data.get('class_type') == 'KSampler':
            workflow[node_id]['inputs']['seed'] = seed
            print(f"   Updated seed in node {node_id}: {seed}")
            break
    
    # Update filename prefix
    for node_id, node_data in workflow.items():
        if node_data.get('class_type') == 'SaveImage':
            workflow[node_id]['inputs']['filename_prefix'] = "debug_test"
            print(f"   Updated filename prefix in node {node_id}")
            break
    
    # Save the workflow to file for inspection
    debug_file = "/tmp/debug_workflow.json"
    with open(debug_file, 'w') as f:
        json.dump(workflow, f, indent=2)
    print(f"   Saved debug workflow to: {debug_file}")
    
    # Submit to ComfyUI
    try:
        import uuid
        client_id = str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": client_id}
        
        print(f"   Submitting to ComfyUI...")
        response = requests.post("http://127.0.0.1:8188/prompt", json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get("prompt_id")
            print(f"   ✅ Success! Prompt ID: {prompt_id}")
            return True
        else:
            print(f"   ❌ Error {response.status_code}: {response.text}")
            print(f"   Response headers: {dict(response.headers)}")
            
            # Try to parse the error
            try:
                error_data = response.json()
                print(f"   Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"   Raw response: {response.text}")
            
            return False
            
    except Exception as e:
        print(f"   ❌ Exception during submission: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the debug tests"""
    print("🐛 MuseVision Multi-LoRA Workflow Debug\n")
    
    # Test with different LoRA counts
    test_counts = [1, 2, 3, 5]
    
    for count in test_counts:
        print(f"\n" + "="*60)
        print(f"Testing with {count} LoRAs")
        print("="*60)
        
        result = test_workflow_generation(count)
        if result:
            workflow, lora_configs = result
            
            # Test submission
            success = test_comfyui_submission(workflow)
            
            if success:
                print(f"✅ {count} LoRAs: SUCCESS")
                break
            else:
                print(f"❌ {count} LoRAs: FAILED")
        else:
            print(f"❌ {count} LoRAs: GENERATION FAILED")
    
    print(f"\n" + "="*60)
    print("Debug complete!")
    print("="*60)


if __name__ == "__main__":
    main()
