# 📐 Resolution Control in MuseVision

## 🎯 **New Feature Added: Custom Resolution Support**

You can now control the output resolution (width and height) of generated images across **all MuseVision scripts**!

## 🔧 **How It Works**

The resolution control modifies the `EmptySD3LatentImage` node in your ComfyUI workflow, setting custom width and height values before image generation.

**Default Resolution:** 720x1280 (portrait orientation)
**Supported Range:** Any valid positive integers (recommend multiples of 8 for best results)

## 📋 **Usage Across All Scripts**

### 🎨 **Direct Image Generation** (`run_flux.py`)
```bash
# Custom resolution
python run_flux.py --prompt "a dragon" --name-prefix "test" \
    --width 1024 --height 1024

# Landscape format  
python run_flux.py --prompt "a landscape" --name-prefix "scenic" \
    --width 1920 --height 1080
    
# Portrait format
python run_flux.py --prompt "a portrait" --name-prefix "character" \
    --width 512 --height 896
```

### 🎲 **Batch Variations** (`run_variations.py`)
```bash
# Square format variations
python run_variations.py --prompt "fantasy art" --n 10 \
    --width 1024 --height 1024

# Ultra-wide format  
python run_variations.py --prompt "panoramic view" --n 5 \
    --width 1536 --height 640

# Standard portrait
python run_variations.py --prompt "character study" --n 8 \
    --width 768 --height 1344
```

### 🤖 **Agent Commands** (`agent.py`)

#### Style Exploration
```bash
python agent.py explore_styles --project MyProject \
    --prompt "character design concepts" \
    --width 512 --height 896 \
    --k 3 --n 10
```

#### Style Refinement
```bash
python agent.py refine_styles --project MyProject \
    --prompt "refined character art" \
    --width 1024 --height 768 \
    --tests-per-combo 3
```

#### Narrative Exploration  
```bash
python agent.py explore_narrative --project StoryProject \
    --prompt "epic story scenes" \
    --width 896 --height 1152 \
    --dream-count 8 \
    --guidance "Show different environments and moods"
```

## 🎨 **Recommended Resolutions**

### **Square Formats** (1:1 ratio)
- **1024x1024** - High quality square
- **768x768** - Medium quality square  
- **512x512** - Fast generation square

### **Portrait Formats** (vertical)
- **720x1280** - Default MuseVision portrait
- **768x1344** - Tall portrait
- **896x1152** - Medium portrait
- **512x896** - Narrow portrait

### **Landscape Formats** (horizontal)
- **1280x720** - Standard landscape
- **1344x768** - Wide landscape
- **1152x896** - Medium landscape
- **1920x1080** - Full HD landscape

### **Special Formats**
- **1536x640** - Ultra-wide cinematic
- **640x1536** - Ultra-tall banner
- **1024x512** - Wide panoramic
- **512x1024** - Tall banner

## ⚡ **Performance Considerations**

### **Generation Speed vs Quality**
- **Smaller resolutions** (512x512) = Faster generation
- **Larger resolutions** (1920x1080) = Slower but higher quality  
- **Default resolution** (720x1280) = Good balance

### **Memory Usage**
- Higher resolutions use more VRAM
- If you get out-of-memory errors, reduce resolution
- Multiples of 64 often work better than arbitrary numbers

## 🚀 **Advanced Usage Examples**

### **Aspect Ratio Matching**
```bash
# 16:9 widescreen (like video)
python run_flux.py --prompt "cinematic scene" --name-prefix "movie" \
    --width 1920 --height 1080

# 4:3 classic (like old TV)  
python run_flux.py --prompt "vintage scene" --name-prefix "retro" \
    --width 1024 --height 768

# 21:9 ultra-wide (like movies)
python run_flux.py --prompt "epic landscape" --name-prefix "ultra" \
    --width 1344 --height 576
```

### **Social Media Formats**
```bash
# Instagram square
python run_flux.py --prompt "social media post" --name-prefix "insta" \
    --width 1080 --height 1080

# Instagram story  
python run_flux.py --prompt "story content" --name-prefix "story" \
    --width 1080 --height 1920

# Twitter header
python run_flux.py --prompt "profile header" --name-prefix "twitter" \
    --width 1500 --height 500
```

### **Print Formats**
```bash
# A4 portrait (300 DPI equivalent)
python run_flux.py --prompt "print artwork" --name-prefix "print" \
    --width 2480 --height 3508

# US Letter landscape
python run_flux.py --prompt "landscape print" --name-prefix "letter" \
    --width 3300 --height 2550
```

### **Multi-Resolution Workflow**
```bash
# 1. Generate concept at low resolution for speed
python agent.py explore_styles --project Concepts \
    --prompt "character concepts" --width 512 --height 512 \
    --n 20 --k 2

# 2. Refine chosen concepts at medium resolution  
python agent.py refine_styles --project Concepts \
    --prompt "refined concepts" --width 768 --height 768 \
    --tests-per-combo 2

# 3. Final high-resolution versions
python run_flux.py --prompt "final character art" --name-prefix "final" \
    --width 1024 --height 1024 --loras "chosen-style:0.8"
```

## 🔄 **Resolution with Other Features**

### **Combined with Wildcards**
```bash
python agent.py explore_narrative --project Enhanced \
    --prompt "fantasy scenes" \
    --width 1152 --height 896 \
    --wildcards "Camera_Shots:1" "Lighting_and_Mood:1" \
    --guidance "Show different camera angles and lighting setups"
```

### **Combined with Multi-LoRA**
```bash
python run_flux.py --prompt "complex character" --name-prefix "multi" \
    --width 768 --height 1024 \
    --loras "Style:0.8" "Character:0.6" "Lighting:0.4"
```

### **Combined with Variations**
```bash
python run_variations.py --prompt "varied compositions" \
    --width 1344 --height 768 \
    --n 15 --k 3 \
    --wildcards "Composition_and_Technique:1"
```

## 📊 **Resolution Quick Reference**

| Format | Width | Height | Aspect | Use Case |
|--------|-------|--------|--------|----------|
| Square | 1024 | 1024 | 1:1 | Social media, icons |
| Portrait | 768 | 1344 | 4:7 | Characters, portraits |
| Landscape | 1344 | 768 | 7:4 | Scenes, environments |
| Widescreen | 1920 | 1080 | 16:9 | Cinematic, video |
| Mobile | 1080 | 1920 | 9:16 | Mobile screens, stories |
| Ultra-wide | 1536 | 640 | 12:5 | Panoramic, banners |

## ⚠️ **Tips for Best Results**

### **Resolution Guidelines**
1. **Start small** - test concepts at 512x512 first
2. **Use multiples of 64** - 512, 640, 768, 896, 1024, 1152, etc.
3. **Match your output purpose** - web = smaller, print = larger
4. **Consider your hardware** - larger = more VRAM needed

### **Common Issues**
- **Out of memory?** → Reduce resolution
- **Generation too slow?** → Use smaller dimensions  
- **Images look stretched?** → Check aspect ratio makes sense
- **Poor quality?** → Try multiples of 64 or 128

## 🎉 **Ready to Use!**

The resolution control feature is **fully integrated** and ready to use across all MuseVision components:

✅ **`run_flux.py`** - Direct image generation with custom resolution  
✅ **`run_variations.py`** - Batch variations at any resolution  
✅ **`agent.py`** - All agent commands support resolution control  
✅ **Workflow Integration** - Automatically modifies ComfyUI workflow  
✅ **Full Testing** - Comprehensive test coverage and validation  

**Now you have complete control over your image dimensions!** 📐✨
