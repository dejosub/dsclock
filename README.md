# Analog Clock

A beautiful, customizable analog clock for Linux with various backgrounds, multiple themes, and extensive customization options.

## Installation

### Option 1: Install via Snap (Recommended)

```bash
sudo snap install dsclock
```

**Requirements:** Ubuntu 24.04 (Noble) or later

All dependencies are included. Just run:
```bash
dsclock
```

### Option 2: Run from Source

**Requirements:**
- Python 3.12+
- GTK 3
- Python Pillow (PIL)
- wmctrl (for position saving on X11)

**Install dependencies:**
```bash
sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-pil wmctrl
```

**Run:**
```bash
python3 dsclock.py
```

## Features

- **Transparent background** - Semi-transparent clock face that blends with your desktop
- **Multiple themes** - Built-in themes with full customization support
- **Hand image themes** - Use custom hand images (breguet, grandfather, modern, spear styles included)
- **Geometric or image-based hands** - Choose between drawn hands or image-based hands
- **Face textures** - Apply textures to the clock face background
- **Customizable appearance** - Extensive customization of colors, sizes, fonts, and visibility
- **Date display** - Optional date box below the clock
- **Position memory** - Automatically remembers and restores window position
- **Auto-start** - Optionally start automatically on login
- **Theme management** - Save, load, duplicate, and delete custom themes

## Controls

- **Left-click and drag** - Move the clock anywhere on screen
- **Right-click** - Open context menu with options
- **Esc** or **Q** - Quit the application

## Customization

Right-click on the clock and select **Appearance...** to access the customization dialog with the following pages:

### Face
- Background color and transparency
- Face texture (optional)
- Border color, width, and visibility
- Clock size

### Numbers
- Number visibility, color, font, and size
- Number position (distance from center)

### Ticks
- Hour and minute tick visibility, colors, and sizes
- Tick styles and positioning

### Hands
- Hand theme selection (default geometric or image-based themes)
- Hand colors (hour/minute and second hand)
- Hand lengths, widths, and tail lengths
- Image-based hand width scaling

### Date
- Date box visibility, position, and size
- Date format, font, and colors
- Background and border customization

### Themes
- Load existing themes
- Save current settings as new theme
- Delete custom themes
- Built-in themes included

## Notes

- Position and all settings are automatically saved and restored between sessions
- Works best on X11 (for Wayland, select "Ubuntu on Xorg" at login)

### Configuration Locations

**When running from snap:**
- Configuration: `~/snap/dsclock/current/`
- Themes: `~/snap/dsclock/current/themes/`
- Custom textures: `~/snap/dsclock/current/textures/`
- Custom hand images: `~/snap/dsclock/current/hands/`

**When running from source:**
- Configuration: `~/.config/dsclock/`
- Themes: `~/.config/dsclock/themes/`
- Custom textures: `~/.config/dsclock/textures/`
- Custom hand images: `~/.config/dsclock/hands/`

## License

MIT License - Copyright (c) 2025 dejosub
