# MuseVision Desktop App Installation

Transform your MuseVision GUI into a native desktop application with a beautiful icon!

## 🎨 Quick Installation

### Step 1: Save Your Icon
First, save your MuseVision icon image to the project:

**Option A - Automatic Helper:**
```bash
cd /home/mitchellflautt/MuseVision
python3 save_icon.py
```
The script will help you find and save your icon image.

**Option B - Manual:**
Save your icon image as:
```
/home/mitchellflautt/MuseVision/gui/assets/musevision_icon.png
```
(256x256 PNG format recommended)

### Step 2: Install Desktop App
Run the installation script:
```bash
cd /home/mitchellflautt/MuseVision
bash install_desktop_app.sh
```

## 🚀 What You Get

### **Desktop Integration:**
- **Application Menu Entry** - Find MuseVision in Graphics category
- **Search Integration** - Search for "MuseVision" in your app launcher
- **Beautiful Icon** - Your custom MuseVision icon in the dock/taskbar
- **Right-Click Actions** - Quick access to projects and queue status

### **GNOME Features (if detected):**
- **Automatically added to dock favorites**
- **Native GNOME integration**
- **System notifications support**

### **File Associations:**
- **Associated with PNG/JPEG files** for easy project imports
- **Context menu integration** (where supported)

## 📱 Usage

### Launch MuseVision:
- **Application Menu:** Graphics → MuseVision
- **Search:** Type "MuseVision" in your app launcher
- **Command Line:** Still works with `python3 launch_gui.py`

### Right-Click Menu Actions:
- **Open Project Folder** - Quick access to your projects directory
- **Show Queue Status** - Check batch processing status

### Keywords for Search:
The app responds to: `AI`, `Image`, `Generation`, `Creative`, `Batch`, `Processing`, `LoRA`, `ComfyUI`

## 🔧 Technical Details

### Files Created:
- **Desktop Entry:** `~/.local/share/applications/MuseVision.desktop`
- **System Entry:** `/usr/share/applications/MuseVision.desktop` (if sudo access)
- **Icon:** `/home/mitchellflautt/MuseVision/gui/assets/musevision_icon.png`

### Requirements:
- **Linux Desktop Environment** (GNOME, KDE, XFCE, etc.)
- **XDG Desktop Entry support** (standard on modern Linux)
- **Optional:** ImageMagick for automatic icon conversion

## 🔄 Uninstalling

To remove the desktop app (keeps your MuseVision installation):
```bash
rm ~/.local/share/applications/MuseVision.desktop
sudo rm /usr/share/applications/MuseVision.desktop 2>/dev/null || true
update-desktop-database ~/.local/share/applications
```

## 🛠️ Troubleshooting

### Icon Not Showing:
1. Ensure icon exists: `ls -la /home/mitchellflautt/MuseVision/gui/assets/musevision_icon.png`
2. Clear icon cache: `gtk-update-icon-cache -f ~/.local/share/icons` (if applicable)
3. Restart your desktop environment

### App Not Appearing in Menu:
1. Check desktop file: `desktop-file-validate ~/.local/share/applications/MuseVision.desktop`
2. Update database: `update-desktop-database ~/.local/share/applications`
3. Log out and back in

### Launch Issues:
1. Verify launcher is executable: `ls -la /home/mitchellflautt/MuseVision/launch_gui.py`
2. Test manual launch: `cd /home/mitchellflautt/MuseVision && python3 launch_gui.py`
3. Check desktop file paths match your installation

## 🎉 Enjoy!

Your MuseVision GUI is now a first-class desktop application! Pin it to your dock, add it to favorites, and launch your creative AI projects with style.

---

*Created for MuseVision - Creative AI Batch Processing*