# Bundled Themes

This directory contains themes that ship with the application.

## Adding Bundled Themes

1. Create themes using the app's Customize dialog
2. Run `./copy_themes.py` to copy themes from your config to this directory
3. Review the copied themes
4. Rebuild the snap to include the new bundled themes

## How It Works

- Bundled themes are packaged with the snap in `/snap/dsclock/current/lib/dsclock/bundled_themes/`
- On first run, the app copies bundled themes to the user's themes directory (`~/.config/dsclock/themes/`)
- Existing user themes are never overwritten
- Users can customize or delete bundled themes after installation

## Theme Files

Theme files are JSON files with the `.json` extension. Each file contains theme properties like colors, sizes, and visibility settings.
