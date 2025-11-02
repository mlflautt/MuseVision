#!/usr/bin/env python3
"""Test LoRA metadata detection from PNG files"""

import sys
import os
sys.path.append('/home/mitchellflautt/MuseVision/scripts')

from agent import extract_metadata_from_png

def test_lora_detection(image_path):
    """Test LoRA detection from a PNG file"""
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    try:
        prompt_text, loras, seed = extract_metadata_from_png(image_path)
        print(f"📄 Testing: {os.path.basename(image_path)}")
        print(f"🔤 Prompt: {prompt_text[:100]}...")
        print(f"🧬 Seed: {seed}")
        print(f"🎛️  LoRAs detected: {len(loras)}")
        
        for i, (name, model_str, clip_str) in enumerate(loras, 1):
            print(f"  {i}. {name} - model:{model_str}, clip:{clip_str}")
            
        if not loras:
            print("⚠️  No LoRAs detected in this image")
        
        return prompt_text, loras, seed
        
    except Exception as e:
        print(f"❌ Error processing {image_path}: {e}")
        return None, [], None

if __name__ == "__main__":
    # Test with available images
    test_images = [
        "/home/mitchellflautt/MuseVision/ComfyUI/output/ComfyUI_00001_.png",
        "/home/mitchellflautt/MuseVision/ComfyUI/output/ComfyUI_00002_.png",
        "/home/mitchellflautt/MuseVision/ComfyUI/output/ComfyUI_00003_.png"
    ]
    
    for img in test_images:
        test_lora_detection(img)
        print("-" * 60)
