# MuseVision

A desktop GUI application for batch processing creative AI image generation using ComfyUI and various models.

## Features

- **Explore Styles**: Generate style variations using LoRA combinations
- **Explore Narrative**: Create narrative variations from source images
- **Refine Styles**: Test and refine styles against reference images
- **Project Management**: Organize work with automatic directory creation
- **Image Selection**: Browse and select reference images with previews
- **Batch Processing**: Queue and monitor multiple generation jobs
- **Progress Tracking**: Real-time progress bars and console output

## Installation

### Prerequisites

- Python 3.8+
- ComfyUI installation
- GPU with sufficient VRAM (recommended: 16GB+)

### Desktop App Installation

1. Clone the repository:
```bash
git clone https://github.com/mlflautt/MuseVision.git
cd MuseVision
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Run the desktop installer:
```bash
./install_desktop_app.sh
```

4. Launch the application:
```bash
python launch_gui.py
```

## Usage

1. **Create a Project**: Use the "New" button to create a new project folder
2. **Select Mode**: Choose from Explore Styles, Explore Narrative, or Refine Styles
3. **Configure Parameters**: Set prompts, dimensions, LoRA combinations, and other settings
4. **Add Images** (if needed): For narrative exploration or style refinement, add reference images
5. **Run Process**: Click "Run Process" to start batch generation
6. **Monitor Progress**: Watch the progress bars and console output
7. **View Results**: Use "Open Output" to view generated images

## Project Structure

```
MuseVision/
├── gui/                    # Desktop application
│   ├── musevision_gui.py   # Main GUI application
│   ├── launch_gui.py       # Launcher script
│   ├── MuseVision.desktop  # Linux desktop integration
│   └── assets/             # Icons and resources
├── models/                 # AI models and LoRAs
├── config/                 # Configuration files
├── scripts/                # Backend processing scripts
├── projects/               # User project folders (auto-created)
└── prompts/                # Prompt templates
```

## Configuration

- **Models**: Configure available models in `config/models.yaml`
- **Filters**: Set quality thresholds in `config/filters.yaml`
- **Wildcards**: Add custom wildcard files in `wildcards/` directory

## Requirements

- Python 3.8+
- tkinter (usually included with Python)
- PIL/Pillow (for image previews)
- ComfyUI
- Various AI models (Flux, SDXL, etc.)

## Development

The application is built with tkinter for cross-platform compatibility. The GUI follows Apple's design principles with a dark theme and clean interface.

### Adding New Features

1. Edit `gui/musevision_gui.py` to add new tabs or controls
2. Update backend scripts in `scripts/` for new processing modes
3. Test with sample projects before committing

## License

[Add license information here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request</content>
<parameter name="filePath">/home/mitchellflautt/MuseVision/README.md