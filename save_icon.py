#!/usr/bin/env python3
"""
Helper script to save the MuseVision icon from screenshot or image file
"""

import os
import sys
import shutil
from pathlib import Path

def save_icon():
    musevision_dir = Path("/home/mitchellflautt/MuseVision")
    assets_dir = musevision_dir / "gui" / "assets"
    target_path = assets_dir / "musevision_icon.png"
    
    # Create assets directory if it doesn't exist
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    print("🎨 MuseVision Icon Saver")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        # Icon path provided as argument
        source_path = Path(sys.argv[1])
        if source_path.exists():
            try:
                shutil.copy2(source_path, target_path)
                print(f"✅ Icon saved successfully!")
                print(f"   From: {source_path}")
                print(f"   To: {target_path}")
                return True
            except Exception as e:
                print(f"❌ Error copying icon: {e}")
                return False
        else:
            print(f"❌ Source file not found: {source_path}")
            return False
    
    # Interactive mode
    print("Please provide the path to your MuseVision icon image:")
    print("(PNG format, 256x256 recommended)")
    print()
    
    # Common screenshot locations
    screenshot_dirs = [
        Path.home() / "Desktop",
        Path.home() / "Downloads", 
        Path.home() / "Pictures",
        Path("/tmp"),
        Path("/var/folders")  # macOS temp screenshots
    ]
    
    print("🔍 Looking for recent image files...")
    recent_images = []
    
    for directory in screenshot_dirs:
        if directory.exists():
            try:
                for pattern in ["*.png", "*.jpg", "*.jpeg"]:
                    for file_path in directory.glob(pattern):
                        if file_path.is_file():
                            # Check if modified in last hour
                            import time
                            if time.time() - file_path.stat().st_mtime < 3600:
                                recent_images.append(file_path)
            except PermissionError:
                continue
    
    if recent_images:
        print(f"Found {len(recent_images)} recent image(s):")
        for i, img_path in enumerate(recent_images[:10], 1):
            print(f"  {i}: {img_path}")
        
        print()
        choice = input("Enter number to use one of these, or full path to another file: ").strip()
        
        if choice.isdigit() and 1 <= int(choice) <= len(recent_images):
            source_path = recent_images[int(choice) - 1]
        else:
            source_path = Path(choice)
    else:
        path_input = input("Enter full path to your icon file: ").strip()
        source_path = Path(path_input)
    
    if source_path.exists():
        try:
            shutil.copy2(source_path, target_path)
            print(f"✅ Icon saved successfully!")
            print(f"   From: {source_path}")
            print(f"   To: {target_path}")
            
            # Check file size
            size_mb = target_path.stat().st_size / (1024 * 1024)
            if size_mb > 1:
                print(f"⚠️  Icon is quite large ({size_mb:.1f}MB). Consider resizing to 256x256 for better performance.")
            
            return True
        except Exception as e:
            print(f"❌ Error copying icon: {e}")
            return False
    else:
        print(f"❌ File not found: {source_path}")
        return False

if __name__ == "__main__":
    success = save_icon()
    if success:
        print()
        print("🚀 Next steps:")
        print("   1. Run: bash install_desktop_app.sh")
        print("   2. Look for MuseVision in your application menu!")
    sys.exit(0 if success else 1)