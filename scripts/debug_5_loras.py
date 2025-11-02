#!/usr/bin/env python3
"""
Focused debug for the 5 LoRA case that's causing the 400 error
"""

import sys
import os
import json
import glob
import requests
import random
import uuid

# Add the script directory to the path
script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, script_dir)

from dynamic_lora_workflow import DynamicLoRAWorkflow, LoRAConfig


def test_5_lora_workflow():
    """Test the specific case of 5 LoRAs"""
    print("🔧 Testing 5 LoRA workflow generation...")
    
    # Get available LoRAs
    loras_dir = os.path.expanduser("~/MuseVision/ComfyUI/models/loras")
    lora_files = glob.glob(os.path.join(loras_dir, "*Flux*.safetensors"))
    
    if len(lora_files) < 5:
        print(f"❌ Not enough LoRAs available. Need 5, found {len(lora_files)}")
        return
    
    # Create 5 test LoRA configs with reasonable strengths
    selected_files = random.sample(lora_files, 5)
    lora_configs = []
    
    for i, lora_file in enumerate(selected_files):
        name = os.path.basename(lora_file)
        strength = round(random.uniform(0.6, 0.9), 2)  # More conservative range
        lora_configs.append(LoRAConfig(name, strength, 1.0))
    
    print(f"🎯 Testing with 5 LoRAs:")
    for i, config in enumerate(lora_configs):
        print(f"   {i+1}. {config.name} (strength: {config.strength_model})")
    
    # Generate workflow
    try:
        workflow_path = os.path.join(script_dir, '..', 'ComfyUI', 'user', 'default', 'workflows', 'flux_dev_multi-LoRA.api.json')
        generator = DynamicLoRAWorkflow(workflow_path)
        workflow = generator.create_multi_lora_workflow(lora_configs)
        
        print("✅ Workflow generated successfully")
        
        # Update workflow for testing
        test_prompt = "a mystical forest guardian"
        
        # Update prompt
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'CLIPTextEncode' and 'text' in node_data.get('inputs', {}):
                current_text = node_data['inputs']['text'].strip()
                if current_text or 'Positive' in node_data.get('_meta', {}).get('title', ''):
                    workflow[node_id]['inputs']['text'] = test_prompt + "\n"
                    break
        
        # Update seed
        seed = random.getrandbits(64)
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'KSampler':
                workflow[node_id]['inputs']['seed'] = seed
                break
        
        # Update filename prefix
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'SaveImage':
                workflow[node_id]['inputs']['filename_prefix'] = "debug_5_loras"
                break
        
        # Save workflow for inspection
        debug_file = "/tmp/debug_5_loras_workflow.json"
        with open(debug_file, 'w') as f:
            json.dump(workflow, f, indent=2)
        print(f"💾 Saved debug workflow to: {debug_file}")
        
        # Analyze the workflow structure
        print(f"\n🔍 Workflow analysis:")
        lora_nodes = []
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'LoraLoader':
                inputs = node_data.get('inputs', {})
                lora_nodes.append({
                    'id': node_id,
                    'name': inputs.get('lora_name'),
                    'model_input': inputs.get('model'),
                    'clip_input': inputs.get('clip')
                })
        
        print(f"   Found {len(lora_nodes)} LoRA nodes:")
        for lora_node in lora_nodes:
            print(f"   Node {lora_node['id']}: {lora_node['name']}")
            print(f"     Model input: {lora_node['model_input']}")
            print(f"     Clip input: {lora_node['clip_input']}")
        
        # Check the chaining
        print(f"\n🔗 Checking LoRA chaining:")
        sorted_nodes = sorted(lora_nodes, key=lambda x: int(x['id']))
        for i, lora_node in enumerate(sorted_nodes):
            if i == 0:
                # First LoRA should connect to checkpoint (node 30)
                expected_model = ['30', 0]
                expected_clip = ['30', 1]
            else:
                # Subsequent LoRAs should connect to previous LoRA
                prev_node_id = sorted_nodes[i-1]['id']
                expected_model = [prev_node_id, 0]
                expected_clip = [prev_node_id, 1]
            
            actual_model = lora_node['model_input']
            actual_clip = lora_node['clip_input']
            
            model_ok = actual_model == expected_model
            clip_ok = actual_clip == expected_clip
            
            print(f"   Node {lora_node['id']}:")
            print(f"     Model: {actual_model} {'✅' if model_ok else '❌ (expected ' + str(expected_model) + ')'}")
            print(f"     Clip:  {actual_clip} {'✅' if clip_ok else '❌ (expected ' + str(expected_clip) + ')'}")
        
        # Test submission
        print(f"\n🚀 Testing ComfyUI submission...")
        client_id = str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": client_id}
        
        response = requests.post("http://127.0.0.1:8188/prompt", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            prompt_id = result.get("prompt_id")
            print(f"✅ Success! Prompt ID: {prompt_id}")
            print(f"   5 LoRA workflow submitted successfully!")
        else:
            print(f"❌ Error {response.status_code}")
            print(f"Response: {response.text}")
            
            # Try to get more detailed error info
            try:
                error_data = response.json()
                print(f"Error details:")
                print(json.dumps(error_data, indent=2))
            except:
                pass
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_5_lora_workflow()
