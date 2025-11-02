#!/usr/bin/env python3
import os
import json
import sys

# Add the scripts directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from agent import dream_prompts, resolve_preset

# Define the 7 batches
batches = [
    {
        "name": "lizard_land_1",
        "project": "Lizard Land",
        "prompt": "Psychedelic space, astral assimilation, neon fractal lizards",
        "guidance": "",
        "dream_count": 4,
    },
    {
        "name": "lizard_land_2",
        "project": "Lizard Land",
        "prompt": "Cosmic dunes and iridescent vapor, traversed by astral beings",
        "guidance": "",
        "dream_count": 4,
    },
    {
        "name": "sufism",
        "project": "Esoteric Sacred Visuals",
        "prompt": "Sufi mysticism, whirling dervishes in a state of ecstatic trance, divine light, intricate geometric patterns, Rumi's poetry visualized",
        "guidance": "Focus on the spiritual ecstasy and the interplay of light and shadow. Use a palette of gold, white, and deep blues.",
        "dream_count": 4,
    },
    {
        "name": "gnosticism",
        "project": "Esoteric Sacred Visuals",
        "prompt": "Gnostic visions of the Demiurge, Sophia, and the Pleroma; esoteric Christian and Hellenistic mystery school aesthetics, archons as fractal entities",
        "guidance": "Emphasize the contrast between the material and the spiritual, the darkness of the Demiurge and the light of the Pleroma.",
        "dream_count": 4,
    },
    {
        "name": "tibetan_buddhism",
        "project": "Esoteric Sacred Visuals",
        "prompt": "Vajrayana Buddhist mandalas, deities like Vajrabhairava and Kalachakra in dynamic, wrathful poses, rainbow body, thangka art style",
        "guidance": "Vibrant, intricate, and respectful of the iconography. Emphasize dynamic energy and complex details.",
        "dream_count": 4,
    },
    {
        "name": "hermeticism",
        "project": "Esoteric Sacred Visuals",
        "prompt": "Hermetic and alchemical diagrams, 'As above, so below', the Emerald Tablet, symbolic representations of the seven planets, caduceus and ouroboros",
        "guidance": "A sense of ancient wisdom and cosmic interconnectedness. Use a style reminiscent of old manuscripts and engravings.",
        "dream_count": 4,
    },
    {
        "name": "alchemy",
        "project": "Esoteric Sacred Visuals",
        "prompt": "Alchemical laboratory, the Green Lion devouring the sun, the Rebis,solve et coagula, magnum opus, philosopher's stone",
        "guidance": "Symbolic, mystical, and slightly cryptic. A blend of scientific and spiritual imagery.",
        "dream_count": 4,
    },
]

def main():
    # Use a dummy args object for resolve_preset
    class DummyArgs:
        llm_preset = 'qwen7b'
        model_path = None
        llama_cli = None
        ctx = None
        ngl = None
        top_p = None

    preset = resolve_preset(DummyArgs())

    for batch in batches:
        print(f"\n--- Dreaming prompts for: {batch['name']} ---")
        prompts = dream_prompts(
            seed_prompts=[batch['prompt']],
            guidance=batch['guidance'],
            creativity=0.7,
            count=batch['dream_count'],
            tokens_per_prompt=66,
            buffer_factor=0.7,
            preset=preset,
            enforce_numbering=True
        )

        if prompts:
            output_file = f"{batch['name']}_prompts.json"
            with open(output_file, 'w') as f:
                json.dump(prompts, f, indent=2)
            print(f"✅ Saved {len(prompts)} prompts to {output_file}")
        else:
            print(f"❌ Failed to generate prompts for {batch['name']}")

if __name__ == "__main__":
    main()
