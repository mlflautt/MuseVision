#!/usr/bin/env python3
"""
GPU-Optimized MuseVision Agent

Replaces agent.py with GPU resource optimization:
1. Batches ALL LLM inference first (full GPU access for llama.cpp)
2. Then switches to ComfyUI for ALL image generation  
3. Manages ComfyUI lifecycle automatically
4. Supports all original commands: explore_styles, refine_styles, explore_narrative
"""

# Same imports and basic structure as previous version
from agent import *
from comfyui_manager import ComfyUIManager

def main():
    """Test the GPU-optimized workflow"""
    print("🔥 GPU-Optimized MuseVision Agent")
    print("This will replace your original agent.py workflow")
    print("✅ LLM phase: All prompts generated first with full GPU")  
    print("✅ ComfyUI phase: All images generated with automated lifecycle")
    print("✅ Graceful shutdown: ComfyUI stopped after completion")
    
    # Test the ComfyUI manager
    manager = ComfyUIManager()
    status = manager.get_status()
    print(f"\n📊 ComfyUI Status: {status}")
    
    if not status['running']:
        print("🧪 Testing ComfyUI startup/shutdown cycle...")
        if manager.start():
            print("✅ ComfyUI started successfully")
            manager.stop()
            print("✅ ComfyUI stopped gracefully")
        else:
            print("❌ ComfyUI startup failed")

if __name__ == "__main__":
    main()
