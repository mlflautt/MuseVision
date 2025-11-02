# MuseVision GUI

An intuitive, Apple-inspired GUI for the MuseVision creative AI batch processing system.

## Features

### 🎨 **Dark macOS Theme**
- Beautiful dark theme inspired by macOS design principles
- Clean, modern interface with Apple-style typography and colors
- Professional look optimized for extended creative sessions

### 🎯 **Three Main Functions**
1. **Explore Styles** - Generate style variations with random LoRA combinations
2. **Explore Narrative** - Create narrative variations using source images
3. **Refine Styles** - Test and refine LoRA combinations from selected styles

### 📁 **Enhanced Project Management**
- **Create New Projects**: Click ➕ to create new projects with standard folder structure
- **Select Existing Projects**: Dropdown menu shows all available projects
- **Quick Access**: 📁 button opens project directory in file manager
- **Auto-Refresh**: 🔄 button refreshes project list
- **Auto Output Directories**: Automatically sets appropriate output folder based on current tab

### 🖼️ **Intuitive Image Selection**
- Drag-and-drop support for image selection (planned)
- File browser integration for selecting source/style images
- Image list management with add/remove/clear functions

### ⚙️ **Comprehensive Parameter Controls**
- **Text Fields**: For prompts, guidance, and wildcards
- **Numeric Inputs**: For counts, dimensions, and strength values  
- **Checkboxes**: For boolean options like "Per Image" processing
- **Advanced Options**: Timeout settings, ComfyUI management

### 📊 **Real-time Process Monitoring**
- **Live Console Output**: See exactly what's happening during processing
- **Progress Indicators**: Visual progress bars and status updates
- **Process Control**: Start, stop, and monitor batch processes
- **Queue Management**: View and manage batch queue status

## Getting Started

### Quick Launch
```bash
cd /home/mitchellflautt/MuseVision
python3 launch_gui.py
```

### Manual Launch
```bash
cd /home/mitchellflautt/MuseVision
python3 gui/musevision_gui.py
```

## Usage Guide

### 1. **Project Setup**
- Create a new project using the ➕ button, or select an existing one from the dropdown
- The output directory will automatically update based on your current tab
- Use the "Auto" button to reset output directory to the standard location

### 2. **Configure Parameters**
- Switch between tabs: 🎨 Explore Styles, 📖 Explore Narrative, 🎯 Refine Styles
- Fill in the required parameters (prompts, counts, dimensions, etc.)
- Adjust advanced options like wildcards and timeout settings

### 3. **Select Images** (for Narrative/Refine functions)
- Click "Add Images" to browse and select source or style images
- Use "Remove Selected" to remove individual images
- Use "Clear All" to start over

### 4. **Run Processing**
- Click ▶ **Run Process** to start the batch processing
- Monitor progress in the console output area
- Use ⏹ **Stop** if you need to cancel the process
- Click 📊 **Queue Status** to view batch queue information

### 5. **Access Results**
- Use 📁 **Open Output** to view generated images in your file manager
- Results are organized in project subdirectories (style_explore, narrative_explore, style_refine)

## Design Philosophy

This GUI follows Apple's design principles:
- **Clarity**: Clear labels, logical organization, intuitive workflows
- **Deference**: Content-focused design that doesn't distract from the task
- **Depth**: Visual layers and transitions that provide clear navigation

The dark theme is optimized for creative work, reducing eye strain during long sessions while maintaining the premium feel of Apple's professional applications.

## Technical Details

- **Built with**: Python Tkinter with custom ttk styling
- **Compatible with**: Linux (tested on Fedora), should work on macOS and Windows
- **Requirements**: Python 3.6+, tkinter (usually included), Pillow (for future image features)
- **Backend Integration**: Seamlessly integrates with the existing gpu_optimized_agent.py

## Keyboard Shortcuts

- **Tab**: Navigate between input fields
- **Enter**: In most fields, focuses next field or triggers default action
- **Ctrl+C**: Copy text from console output
- **Alt+Tab**: Switch between application tabs (standard OS behavior)

## Future Enhancements

- **Drag & Drop**: Native drag-and-drop support for image files
- **Live Thumbnails**: Preview images directly in the interface
- **Batch Templates**: Save and load parameter presets
- **Progress Details**: More granular progress information
- **Results Gallery**: Built-in image viewer and gallery

---

*Created with ❤️ for creative AI workflows*