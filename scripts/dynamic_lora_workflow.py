#!/usr/bin/env python3
"""
dynamic_lora_workflow.py

A class for dynamically modifying ComfyUI workflow JSON files to support 
any number of LoRA combinations. This replaces the hardcoded 2-LoRA limit.

Usage:
    generator = DynamicLoRAWorkflow(base_workflow_path)
    modified_workflow = generator.create_multi_lora_workflow(loras_config)
"""

import json
import copy
from typing import List, Dict, Any, Optional, Tuple


class LoRAConfig:
    """Configuration for a single LoRA"""
    def __init__(self, name: str, strength_model: float = 1.0, strength_clip: float = 1.0):
        self.name = name
        self.strength_model = strength_model
        self.strength_clip = strength_clip

    def __repr__(self):
        return f"LoRAConfig(name='{self.name}', model={self.strength_model}, clip={self.strength_clip})"


class DynamicLoRAWorkflow:
    """Dynamically modifies ComfyUI workflows to support multiple LoRAs"""
    
    def __init__(self, base_workflow_path: str):
        """Initialize with a base workflow file"""
        self.base_workflow_path = base_workflow_path
        self.base_workflow = self._load_workflow()
        self._analyze_base_workflow()
    
    def _load_workflow(self) -> Dict[str, Any]:
        """Load the base workflow JSON"""
        with open(self.base_workflow_path, 'r') as f:
            return json.load(f)
    
    def _analyze_base_workflow(self):
        """Analyze the base workflow to identify key nodes and connections"""
        self.checkpoint_node = None
        self.existing_lora_nodes = []
        self.final_model_connection = None
        self.final_clip_connection = None
        
        # Find checkpoint loader and existing LoRA nodes
        for node_id, node_data in self.base_workflow.items():
            class_type = node_data.get('class_type', '')
            
            if class_type == 'CheckpointLoaderSimple':
                self.checkpoint_node = node_id
            elif class_type == 'LoraLoader':
                self.existing_lora_nodes.append(node_id)
        
        # Find the final model/clip connections (usually from the last LoRA)
        if self.existing_lora_nodes:
            last_lora_id = max(self.existing_lora_nodes, key=int)
            self.final_model_connection = [last_lora_id, 0]
            self.final_clip_connection = [last_lora_id, 1]
        elif self.checkpoint_node:
            self.final_model_connection = [self.checkpoint_node, 0]
            self.final_clip_connection = [self.checkpoint_node, 1]
        
        print(f"📋 Workflow Analysis:")
        print(f"  Checkpoint node: {self.checkpoint_node}")
        print(f"  Existing LoRA nodes: {self.existing_lora_nodes}")
        print(f"  Final connections: model={self.final_model_connection}, clip={self.final_clip_connection}")
    
    def create_multi_lora_workflow(self, loras: List[LoRAConfig]) -> Dict[str, Any]:
        """
        Create a new workflow with the specified LoRAs chained together
        
        Args:
            loras: List of LoRAConfig objects specifying each LoRA to include
            
        Returns:
            Modified workflow dictionary
        """
        if not loras:
            # Return workflow with existing LoRAs removed
            return self._remove_all_loras()
        
        # Start with a copy of the base workflow
        workflow = copy.deepcopy(self.base_workflow)
        
        # Remove existing LoRA nodes
        for lora_id in self.existing_lora_nodes:
            if lora_id in workflow:
                del workflow[lora_id]
        
        # Find the highest existing node ID to avoid conflicts
        max_node_id = max(int(node_id) for node_id in workflow.keys())
        
        # Chain the new LoRAs
        current_model_input = [self.checkpoint_node, 0]
        current_clip_input = [self.checkpoint_node, 1]
        
        new_lora_nodes = []
        for i, lora in enumerate(loras):
            node_id = str(max_node_id + 1 + i)
            new_lora_nodes.append(node_id)
            
            # Create LoRA node
            workflow[node_id] = {
                "inputs": {
                    "lora_name": lora.name,
                    "strength_model": lora.strength_model,
                    "strength_clip": lora.strength_clip,
                    "model": current_model_input,
                    "clip": current_clip_input
                },
                "class_type": "LoraLoader",
                "_meta": {
                    "title": f"Load LoRA {i+1}: {lora.name}"
                }
            }
            
            # Update inputs for next LoRA in chain
            current_model_input = [node_id, 0]
            current_clip_input = [node_id, 1]
        
        # Update all nodes that reference the old final connections
        # (but exclude the new LoRA nodes we just created)
        last_lora_id = new_lora_nodes[-1] if new_lora_nodes else self.checkpoint_node
        self._update_references(workflow, 
                               old_model_ref=self.final_model_connection,
                               old_clip_ref=self.final_clip_connection,
                               new_model_ref=[last_lora_id, 0],
                               new_clip_ref=[last_lora_id, 1],
                               exclude_nodes=set(new_lora_nodes))
        
        print(f"✅ Created workflow with {len(loras)} LoRAs chained together")
        return workflow
    
    def _remove_all_loras(self) -> Dict[str, Any]:
        """Remove all LoRAs and connect directly to checkpoint"""
        workflow = copy.deepcopy(self.base_workflow)
        
        # Remove existing LoRA nodes
        for lora_id in self.existing_lora_nodes:
            if lora_id in workflow:
                del workflow[lora_id]
        
        # Update references to point directly to checkpoint
        self._update_references(workflow,
                               old_model_ref=self.final_model_connection,
                               old_clip_ref=self.final_clip_connection,
                               new_model_ref=[self.checkpoint_node, 0],
                               new_clip_ref=[self.checkpoint_node, 1])
        
        return workflow
    
    def _update_references(self, workflow: Dict[str, Any], 
                          old_model_ref: List, old_clip_ref: List,
                          new_model_ref: List, new_clip_ref: List,
                          exclude_nodes: set = None):
        """Update all references to old LoRA connections"""
        if exclude_nodes is None:
            exclude_nodes = set()
            
        for node_id, node_data in workflow.items():
            # Skip nodes that we want to exclude (e.g., newly created LoRA nodes)
            if node_id in exclude_nodes:
                continue
                
            inputs = node_data.get('inputs', {})
            
            # Check all input connections
            for input_name, input_value in inputs.items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    # This is a node connection reference
                    if input_value == old_model_ref:
                        inputs[input_name] = new_model_ref
                        print(f"  Updated {node_id}.{input_name}: {old_model_ref} -> {new_model_ref}")
                    elif input_value == old_clip_ref:
                        inputs[input_name] = new_clip_ref
                        print(f"  Updated {node_id}.{input_name}: {old_clip_ref} -> {new_clip_ref}")
    
    def save_workflow(self, workflow: Dict[str, Any], output_path: str):
        """Save the modified workflow to a file"""
        with open(output_path, 'w') as f:
            json.dump(workflow, f, indent=2)
        print(f"💾 Saved workflow to: {output_path}")


def parse_lora_args(lora_specs: List[str]) -> List[LoRAConfig]:
    """
    Parse LoRA specifications from command line arguments
    
    Args:
        lora_specs: List of strings in format "name:model_strength:clip_strength" or "name:strength" or "name"
        
    Returns:
        List of LoRAConfig objects
    """
    configs = []
    for spec in lora_specs:
        parts = spec.split(':')
        name = parts[0]
        
        if len(parts) == 1:
            # Just name, use defaults
            configs.append(LoRAConfig(name))
        elif len(parts) == 2:
            # name:strength (use for both model and clip)
            strength = float(parts[1])
            configs.append(LoRAConfig(name, strength, strength))
        elif len(parts) == 3:
            # name:model_strength:clip_strength
            model_strength = float(parts[1])
            clip_strength = float(parts[2])
            configs.append(LoRAConfig(name, model_strength, clip_strength))
        else:
            raise ValueError(f"Invalid LoRA specification: {spec}")
    
    return configs


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test dynamic LoRA workflow generation")
    parser.add_argument("--base-workflow", default="../ComfyUI/user/default/workflows/flux_dev_multi-LoRA.api.json")
    parser.add_argument("--loras", nargs='+', help="LoRA specs: name[:model_strength[:clip_strength]]")
    parser.add_argument("--output", default="modified_workflow.json")
    
    args = parser.parse_args()
    
    # Test the workflow generator
    generator = DynamicLoRAWorkflow(args.base_workflow)
    
    if args.loras:
        lora_configs = parse_lora_args(args.loras)
        print(f"\n🔧 Creating workflow with LoRAs: {lora_configs}")
        workflow = generator.create_multi_lora_workflow(lora_configs)
    else:
        print(f"\n🔧 Creating workflow with no LoRAs")
        workflow = generator.create_multi_lora_workflow([])
    
    generator.save_workflow(workflow, args.output)
