# 🎭 Narrative Guidance with `explore_narrative`

## ✅ **Good News:** The `--guidance` argument already exists!

The `explore_narrative` command already has a `--guidance` parameter that adds additional instructions directly to the LLM prompt. This is **exactly** what you want for controlling prompt expansion!

## 🧠 How It Works

When you provide `--guidance`, it gets inserted into the LLM prompt as:
```
Additional guidance: [your guidance text]
```

This gives the LLM specific instructions on how to expand and modify the prompts.

## 🎯 Expansion Control Examples

### 🏗️ **Setting/Environment Expansion**
```bash
python agent.py explore_narrative --project Architecture \
    --prompt "a mysterious castle" \
    --guidance "Explore different rooms inside the castle - the throne room, library, dungeons, tower chambers, kitchen, and secret passages. Focus on architectural details and atmosphere of each space." \
    --dream-count 6
```

### 🌍 **Different Settings for Same Character**
```bash
python agent.py explore_narrative --project Character \
    --prompt "a wise wizard" \
    --guidance "Show this wizard in completely different environments - their tower laboratory, a forest clearing, a bustling marketplace, an ancient ruin, by a mountain lake. Keep the character consistent but vary the setting dramatically." \
    --dream-count 5
```

### 👥 **Character Expansion** 
```bash
python agent.py explore_narrative --project Fantasy \
    --prompt "a brave knight" \
    --guidance "Introduce new characters that would interact with this knight - a wise mentor, a loyal squire, a mysterious stranger, a village elder, a magical creature. Show the knight in scenes with these different characters." \
    --dream-count 8
```

### 🎬 **Cinematic Story Progression**
```bash
python agent.py explore_narrative --project Story \
    --prompt "a detective investigating a case" \
    --guidance "Create a narrative progression - examining evidence at the crime scene, interviewing witnesses, chasing suspects through dark alleys, making the crucial discovery, confronting the culprit. Build tension and story beats." \
    --dream-count 7
```

### 🌟 **Mood and Atmosphere Variations**
```bash
python agent.py explore_narrative --project Mood \
    --prompt "a forest path" \
    --guidance "Vary the mood and time of day dramatically - peaceful morning mist, ominous storm approaching, magical twilight with fireflies, spooky midnight shadows, bright cheerful sunlight, mysterious fog. Same path, completely different feelings." \
    --dream-count 6
```

### 🔍 **Detail Zoom Levels**
```bash
python agent.py explore_narrative --project Details \
    --prompt "a medieval marketplace" \
    --guidance "Show different scales and focuses - wide establishing shot of the busy marketplace, close-up of a merchant's goods, intimate conversation between buyers, details of coins changing hands, food being prepared, children playing between the stalls." \
    --dream-count 8
```

## 🎨 Creative Direction Examples

### 📚 **Genre Shifts**
```bash
python agent.py explore_narrative --project Genre \
    --prompt "a spaceship landing" \
    --guidance "Reimagine this scene in different genres - horror (alien invasion), comedy (bumbling tourists), romance (reunion scene), thriller (escape pod), documentary (scientific discovery), fantasy (magical vessel)." \
    --dream-count 6
```

### ⏰ **Time Period Variations**
```bash
python agent.py explore_narrative --project Time \
    --prompt "a messenger delivering important news" \
    --guidance "Show this across different time periods - medieval herald with scroll, Victorian telegram delivery, 1940s wartime dispatch, modern email notification, futuristic hologram message, ancient smoke signals." \
    --dream-count 6
```

### 🎭 **Emotional Journey**
```bash
python agent.py explore_narrative --project Emotion \
    --prompt "a person reading a letter" \
    --guidance "Show the emotional progression - curiosity upon receiving it, surprise at first reading, joy or sadness from the contents, contemplation afterwards, sharing the news with others, life changes from the letter." \
    --dream-count 7
```

## 🎯 Practical Usage Patterns

### **Source Image + Expansion**
```bash
# Use existing images as seeds and expand them
python agent.py explore_narrative --project MyProject \
    --selected-dir "selected_images" \
    --guidance "Take each scene and explore what happened before and after this moment. Show the build-up, the climax, and the aftermath." \
    --dream-count 5
```

### **Per-Image Focused Expansion**
```bash
# Different expansion for each source image
python agent.py explore_narrative --project Expansion \
    --per-image \
    --guidance "For each image, zoom out to show more of the environment, then zoom in to show intimate character details, then show the same scene from a different perspective." \
    --dream-count 3
```

### **Override + Custom Direction**
```bash
# Override seed prompts with your own base + expansion guidance
python agent.py explore_narrative --project Custom \
    --prompt "a mysterious artifact" \
    --guidance "Show the artifact's discovery, its powers being revealed, different people trying to use it, the conflicts it causes, and its ultimate fate. Make each scene dramatically different." \
    --dream-count 8 \
    --creativity 0.8
```

## 📋 Complete Command Template

```bash
python agent.py explore_narrative \
    --project [ProjectName] \
    --selected-dir [source_images_folder] \
    --guidance "[specific expansion instructions]" \
    --dream-count [number_of_variations] \
    --creativity [0.1-1.0] \
    --tokens-per-prompt [prompt_length] \
    --wildcards "all:2" \
    --seed-count [variations_per_prompt]
```

## 💡 Pro Tips

### **Be Specific**
```bash
# ✅ Good: Specific direction
--guidance "Show this character in their childhood, teenage years, as an adult, and as an elder. Focus on how their clothing, posture, and environment change with age."

# ❌ Vague: Generic instruction  
--guidance "Show different versions"
```

### **Combine with Wildcards**
```bash
# Use wildcards for technical enhancement + guidance for creative direction
python agent.py explore_narrative --project Combined \
    --prompt "a warrior" \
    --guidance "Show this warrior in training, in battle, celebrating victory, mourning defeat, and finally at peace. Each scene should feel cinematic." \
    --wildcards "Camera_Shots:1" "Lighting_and_Mood:1" \
    --dream-count 5
```

### **Adjust Creativity**
```bash
# Higher creativity for more dramatic variations
--creativity 0.8 --guidance "Go wild with creative interpretations"

# Lower creativity for more controlled expansion  
--creativity 0.5 --guidance "Stay close to the original concept but explore different angles"
```

## 🚀 **Ready to Use Right Now!**

The `--guidance` feature is **fully functional** in your current system. You can start using it immediately to control how the LLM expands your prompts for narrative generation.

**🎉 No code changes needed - this powerful feature was already there waiting for you!**
