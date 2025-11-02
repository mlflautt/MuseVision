# Multi-LoRA Support - Implementation Guide

## 🚀 Overview

The MuseVision pipeline now supports **unlimited LoRA combinations** instead of being limited to just 2 LoRAs. This enhancement allows for more complex style mixing and creative possibilities.

## 📁 Files Modified

### Core Implementation
- **`dynamic_lora_workflow.py`** - NEW: Dynamic workflow generator that modifies ComfyUI JSON workflows to support any number of LoRAs
- **`run_flux.py`** - Updated to use the dynamic workflow generator and accept unlimited LoRAs
- **`run_variations.py`** - Enhanced to generate variations with K LoRAs (not limited to 2)
- **`recreate_from_meta.py`** - Modified to extract and recreate all LoRAs from PNG metadata 
- **`agent.py`** - Updated to handle multi-LoRA workflows in style exploration and refinement

### Testing
- **`test_multi_lora.py`** - NEW: Test script to verify the implementation works correctly

## 🎛️ New Usage Patterns

### 1. Basic Multi-LoRA Usage

```bash
# Single LoRA with strength
python run_flux.py --prompt "a fantasy castle" --name-prefix "test" \
    --loras "fantasy-style:0.8"

# Multiple LoRAs with different strengths
python run_flux.py --prompt "a fantasy castle" --name-prefix "test" \
    --loras "fantasy-style:0.8" "medieval-arch:0.6" "magical-fx:0.9"

# LoRAs with custom clip strengths
python run_flux.py --prompt "a fantasy castle" --name-prefix "test" \
    --loras "style:0.8:1.0" "character:0.9:1.1" "lighting:0.7:0.9"
```

### 2. LoRA Specification Format

The `--loras` argument accepts specifications in these formats:

- **`name`** - Use default strength (1.0) for both model and clip
- **`name:strength`** - Use same strength for both model and clip  
- **`name:model_strength:clip_strength`** - Specify different strengths

### 3. Backward Compatibility

Legacy arguments still work for compatibility:

```bash
# This still works (converted internally to new format)
python run_flux.py --prompt "test" --name-prefix "test" \
    --lora1 "style.safetensors" --lora1-strength 0.8 \
    --lora2 "char.safetensors" --lora2-strength 0.6
```

### 4. Variations with Multiple LoRAs

```bash
# Generate 10 variations using 3 random LoRAs each
python run_variations.py --prompt "a mystical forest" \
    --n 10 --k 3 --strength-min 0.4 --strength-max 1.0 \
    --output-dir "MyProject/forest_variations"

# Use specific LoRA combination for all variations
python run_variations.py --prompt "a mystical forest" \
    --loras "nature:0.8" "fantasy:0.7" "mystical:0.6" \
    --output-dir "MyProject/forest_fixed"
```

### 5. Agent Style Exploration

```bash
# Random LoRA sampling (NEW: Fixed functionality!)
python agent.py explore_styles \
    --project MyProject \
    --prompt "a magical creature" \
    --dream-count 5 --n 8 --k 4

# Explore styles with specific LoRA combinations
python agent.py explore_styles \
    --project MyProject \
    --prompt "a magical creature" \
    --dream-count 5 --n 8 \
    --loras "creature1.safetensors:0.8" "magic1.safetensors:0.9" "fantasy1.safetensors:0.6"

# Use custom LoRA directory for random sampling
python agent.py explore_styles \
    --project MyProject \
    --prompt "a magical creature" \
    --loras-dir "/path/to/custom/loras" \
    --k 3 --n 10
```

### 6. Recreation from Metadata

```bash
# Now extracts ALL LoRAs from the source image
python recreate_from_meta.py source_image.png \
    --prompt "new prompt with same style combination" \
    --output-dir "recreations"
```

## 🔧 Technical Implementation

### Dynamic Workflow Generation

The `DynamicLoRAWorkflow` class:

1. **Analyzes** the base ComfyUI workflow to identify existing nodes
2. **Removes** old LoRA nodes to avoid conflicts
3. **Chains** new LoRA nodes in sequence: `Checkpoint → LoRA1 → LoRA2 → ... → LoRAn`
4. **Updates** all references to point to the final LoRA in the chain

### LoRA Chaining Logic

```
Checkpoint ──model──┐
            ──clip───┼─→ LoRA1 ──model──┐
                               ──clip───┼─→ LoRA2 ──model──┐
                                              ──clip───┼─→ ... ──→ Final Model/CLIP
```

### Metadata Storage

PNG metadata now stores all LoRAs with their individual model and clip strengths:
```json
{
  "38": {"class_type": "LoraLoader", "inputs": {"lora_name": "style1.safetensors", "strength_model": 0.8, "strength_clip": 1.0}},
  "39": {"class_type": "LoraLoader", "inputs": {"lora_name": "style2.safetensors", "strength_model": 0.6, "strength_clip": 0.9}},
  "40": {"class_type": "LoraLoader", "inputs": {"lora_name": "char1.safetensors", "strength_model": 0.9, "strength_clip": 1.1}}
}
```

## 🧪 Testing

Run the test suite to verify everything works:

```bash
cd /home/mitchellflautt/MuseVision/scripts
python test_multi_lora.py
```

Test the `explore_styles` fixes:

```bash
cd /home/mitchellflautt/MuseVision/scripts
python test_explore_styles.py
```

Expected output:
```
🚀 Testing Multi-LoRA Implementation

🧪 Testing LoRA specification parsing:
   ✅ Parsed 4 LoRA specifications

🧪 Testing: No LoRAs
   ✅ Generated workflow with 0 LoRA nodes

🧪 Testing: Single LoRA  
   ✅ Generated workflow with 1 LoRA nodes

🧪 Testing: Two LoRAs (legacy equivalent)
   ✅ Generated workflow with 2 LoRA nodes

🧪 Testing: Three LoRAs
   ✅ Generated workflow with 3 LoRA nodes

🧪 Testing: Five LoRAs with different clip strengths
   ✅ Generated workflow with 5 LoRA nodes

🎉 All tests passed!
```

## 🎨 Creative Possibilities

The unlimited LoRA support enables new creative workflows:

### Style Layering
- **Base Style** (0.8) + **Lighting** (0.6) + **Texture** (0.7) + **Color Palette** (0.5)

### Character + Environment
- **Character LoRA** (0.9) + **Fantasy Setting** (0.8) + **Magic Effects** (0.6) + **Art Style** (0.7)

### Progressive Refinement  
- **Broad Style** (1.0) → **Specific Genre** (0.8) → **Technical Details** (0.6) → **Mood** (0.4)

### Complex Combinations
- Mix architectural styles, character designs, lighting setups, and artistic techniques all in one generation

## 🔗 Integration Points

All existing MuseVision pipeline components seamlessly work with the multi-LoRA system:

- **Music Analysis** → **Narrative Planning** → **Multi-LoRA Image Generation** → **Video Synthesis**
- **Interactive Selection** retains all LoRA metadata for future refinement
- **Project Organization** handles complex LoRA combinations in folder structures
- **Metadata Tracking** preserves complete generation parameters for reproducibility

## 📈 Performance Considerations

- **Memory Usage**: Each LoRA adds ~100-500MB VRAM depending on size
- **Generation Time**: Additional LoRAs slightly increase processing time
- **Recommended Limits**: 2-6 LoRAs per generation for optimal performance
- **GPU Requirements**: Same as before (≥16GB VRAM recommended)

---

🎉 **The MuseVision pipeline now supports unlimited creative LoRA combinations!** Experiment with complex style mixing and push your AI-generated art to new levels of sophistication.
