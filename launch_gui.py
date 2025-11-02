#!/usr/bin/env python3
"""
MuseVision GUI Launcher
Simple script to launch the MuseVision GUI interface
"""

import os
import sys
import subprocess

def main():
    """Launch the MuseVision GUI"""
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gui_script = os.path.join(script_dir, 'gui', 'musevision_gui.py')
    
    if not os.path.exists(gui_script):
        print(f"❌ GUI script not found: {gui_script}")
        print("Please ensure the MuseVision GUI is properly installed.")
        return 1
    
    try:
        # Check for Pillow (optional but recommended for image previews)
        try:
            import PIL
            print("✅ Pillow detected - image previews will be available")
        except ImportError:
            print("💡 Note: Install Pillow for image previews: pip install Pillow")
        
        # Launch the GUI
        print("🚀 Launching MuseVision GUI...")
        subprocess.run([sys.executable, gui_script], check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to launch GUI: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n👋 GUI closed by user")
        return 0

if __name__ == "__main__":
    sys.exit(main())