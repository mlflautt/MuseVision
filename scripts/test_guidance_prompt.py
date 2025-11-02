#!/usr/bin/env python3
"""Test to show how --guidance integrates into the LLM prompt"""

import sys
import os
sys.path.append('/home/mitchellflautt/MuseVision/scripts')

from agent import dream_prompts, ModelPreset, PRESETS

def test_guidance_integration():
    """Show exactly how guidance text gets integrated into LLM prompts"""
    
    # Test parameters
    seed_prompts = ["a mysterious castle on a hill"]
    base_guidance = ""  # No guidance
    expand_guidance = "Explore different rooms inside the castle - the throne room, library, dungeons, tower chambers. Focus on architectural details and atmosphere of each space."
    
    preset = PRESETS["qwen7b"]  # Use default preset
    
    print("🧪 Testing Guidance Integration into LLM Prompts")
    print("=" * 60)
    
    print("\n📋 Test 1: NO GUIDANCE")
    print("-" * 30)
    
    # Mock the prompt construction (without actually calling LLM)
    count = 3
    tokens_per_prompt = 66
    
    # This is the exact logic from dream_prompts function
    instr_no_guidance = [
        "You are a creative storyteller, designing text-to-image prompts.",
        f"Below are {len(seed_prompts)} inspiration prompts (inspiration for content, not length)— creatively expand on the idea(s) to create a new set of vivid narrative prompts, (each one unique and nearly {int(tokens_per_prompt*0.75)} words long).",
        "Inspiration prompt(s)/Direction:",
        *[f"- {p}" for p in seed_prompts],
    ]
    # No guidance added here
    instr_no_guidance += [
        "",
        f"Produce exactly {count} prompts, numbered using ONLY '1.', '2.', … '{count}.' (no headings like 'Prompt 1:' or '1)' ).",
        "Each item must be a single self-contained, vivid, aesthetic prompt; if a character appears, fully describe them each time.",
        f"Please make the prompts a length of nearly {tokens_per_prompt} tokens (nearly {int(tokens_per_prompt*0.75)} words, nearly {int(tokens_per_prompt*4)} chars) each, and each vividly unique.",
        "Output only the numbered items.",
    ]
    
    prompt_no_guidance = "\\n".join(instr_no_guidance)
    print("LLM Prompt (excerpt):")
    lines = prompt_no_guidance.split("\\n")
    for line in lines:
        print(f"  {line}")
    
    print("\\n📋 Test 2: WITH GUIDANCE")
    print("-" * 30)
    
    # This is the exact logic from dream_prompts function WITH guidance
    instr_with_guidance = [
        "You are a creative storyteller, designing text-to-image prompts.",
        f"Below are {len(seed_prompts)} inspiration prompts (inspiration for content, not length)— creatively expand on the idea(s) to create a new set of vivid narrative prompts, (each one unique and nearly {int(tokens_per_prompt*0.75)} words long).",
        "Inspiration prompt(s)/Direction:",
        *[f"- {p}" for p in seed_prompts],
    ]
    # Guidance gets inserted here (line 160-161 in agent.py)
    if expand_guidance:
        instr_with_guidance.append(f"Additional guidance: {expand_guidance}")
    
    instr_with_guidance += [
        "",
        f"Produce exactly {count} prompts, numbered using ONLY '1.', '2.', … '{count}.' (no headings like 'Prompt 1:' or '1)' ).",
        "Each item must be a single self-contained, vivid, aesthetic prompt; if a character appears, fully describe them each time.",
        f"Please make the prompts a length of nearly {tokens_per_prompt} tokens (nearly {int(tokens_per_prompt*0.75)} words, nearly {int(tokens_per_prompt*4)} chars) each, and each vividly unique.",
        "Output only the numbered items.",
    ]
    
    prompt_with_guidance = "\\n".join(instr_with_guidance)
    print("LLM Prompt (excerpt):")
    lines = prompt_with_guidance.split("\\n")
    for line in lines:
        print(f"  {line}")
    
    print("\\n✨ Key Difference:")
    print("   Without guidance: Goes directly to production instructions")
    print("   With guidance: Includes 'Additional guidance: [your text]' line")
    
    print("\\n🎯 Example Commands:")
    print("\\n   # Basic narrative expansion:")
    print("   python agent.py explore_narrative --project Test --prompt 'a castle' --dream-count 3")
    print("\\n   # Guided expansion:")  
    print("   python agent.py explore_narrative --project Test --prompt 'a castle' \\")
    print("       --guidance 'Explore different rooms - throne room, library, dungeons' \\")
    print("       --dream-count 3")

if __name__ == "__main__":
    test_guidance_integration()
