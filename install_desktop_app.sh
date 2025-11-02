#!/bin/bash

# MuseVision Desktop App Installation Script
# This script installs MuseVision as a desktop application

echo "🎨 Installing MuseVision Desktop App..."

# Define paths
MUSEVISION_DIR="/home/mitchellflautt/MuseVision"
DESKTOP_FILE="$MUSEVISION_DIR/gui/MuseVision.desktop"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_SOURCE="$MUSEVISION_DIR/gui/assets/musevision_icon.png"

# Create applications directory if it doesn't exist
mkdir -p "$DESKTOP_DIR"

# Make the launcher executable
chmod +x "$MUSEVISION_DIR/launch_gui.py"

# Check if icon exists, create a placeholder if not
if [ ! -f "$ICON_SOURCE" ]; then
    echo "⚠️  Icon not found at $ICON_SOURCE"
    echo "📝 Creating placeholder icon..."
    
    # Create a simple SVG placeholder and convert to PNG if possible
    if command -v convert >/dev/null 2>&1; then
        # Create SVG placeholder
        cat > "$MUSEVISION_DIR/gui/assets/musevision_icon.svg" << 'EOF'
<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4A5568;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#2D3748;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="256" height="256" rx="48" fill="url(#grad1)"/>
  <circle cx="128" cy="100" r="40" fill="none" stroke="#A0AEC0" stroke-width="6"/>
  <path d="M90 100 Q128 140 166 100" fill="none" stroke="#A0AEC0" stroke-width="4"/>
  <circle cx="128" cy="100" r="8" fill="#0A84FF"/>
  <text x="128" y="190" font-family="Arial,sans-serif" font-size="24" font-weight="bold" 
        text-anchor="middle" fill="#A0AEC0">MuseVision</text>
</svg>
EOF
        
        # Convert SVG to PNG if ImageMagick is available
        convert "$MUSEVISION_DIR/gui/assets/musevision_icon.svg" "$ICON_SOURCE" 2>/dev/null || {
            echo "💡 ImageMagick not found. Please manually save your icon as:"
            echo "   $ICON_SOURCE"
            echo "   (256x256 PNG format recommended)"
        }
    else
        echo "💡 Please manually save your MuseVision icon as:"
        echo "   $ICON_SOURCE"
        echo "   (256x256 PNG format recommended)"
    fi
fi

# Copy desktop file to applications directory
cp "$DESKTOP_FILE" "$DESKTOP_DIR/"

# Make desktop file executable
chmod +x "$DESKTOP_DIR/MuseVision.desktop"

# Update desktop database
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR"
    echo "✅ Desktop database updated"
fi

# Try to install to system applications as well (optional)
if [ -w "/usr/share/applications" ]; then
    echo "🔧 Installing system-wide..."
    sudo cp "$DESKTOP_FILE" "/usr/share/applications/"
    sudo chmod +x "/usr/share/applications/MuseVision.desktop"
    sudo update-desktop-database "/usr/share/applications" 2>/dev/null || true
    echo "✅ System-wide installation completed"
else
    echo "ℹ️  User-only installation (no sudo access to /usr/share/applications)"
fi

echo ""
echo "🎉 MuseVision Desktop App installed successfully!"
echo ""
echo "📱 You can now:"
echo "   • Find 'MuseVision' in your application menu"
echo "   • Pin it to your taskbar/dock"
echo "   • Right-click for quick actions (Open Projects, Show Queue)"
echo ""
echo "🚀 Launch MuseVision from:"
echo "   • Application menu → Graphics → MuseVision"
echo "   • Or search for 'MuseVision' in your app launcher"
echo ""

# Try to add to favorites/dock if GNOME
if [ "$XDG_CURRENT_DESKTOP" = "GNOME" ] && command -v gsettings >/dev/null 2>&1; then
    echo "🔖 Adding to GNOME favorites..."
    CURRENT_FAVORITES=$(gsettings get org.gnome.shell favorite-apps)
    if [[ "$CURRENT_FAVORITES" != *"MuseVision.desktop"* ]]; then
        # Remove the closing bracket, add our app, add closing bracket back
        NEW_FAVORITES=$(echo "$CURRENT_FAVORITES" | sed "s/\]$/, 'MuseVision.desktop']/")
        gsettings set org.gnome.shell favorite-apps "$NEW_FAVORITES"
        echo "✅ Added to GNOME dock favorites"
    fi
fi

echo "✨ Installation complete! Enjoy using MuseVision!"