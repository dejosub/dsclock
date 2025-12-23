#!/usr/bin/env python3
"""
Script to copy theme files from user config to project bundled_themes directory.
Run this to update the bundled themes that ship with the app.
"""

import os
import shutil
import json

# Paths
config_dir = os.path.expanduser('~/.config/dsclock')
themes_dir = os.path.join(config_dir, 'themes')
project_dir = os.path.dirname(os.path.abspath(__file__))
bundled_themes_dir = os.path.join(project_dir, 'bundled_themes')

def main():
    """Copy theme files from config to project bundled_themes directory."""
    
    if not os.path.exists(themes_dir):
        print(f"Error: Themes directory not found: {themes_dir}")
        print("Please create some themes first using the app.")
        return 1
    
    # Create bundled_themes directory if it doesn't exist
    os.makedirs(bundled_themes_dir, exist_ok=True)
    
    # Get list of theme files
    theme_files = [f for f in os.listdir(themes_dir) if f.endswith('.json')]
    
    if not theme_files:
        print(f"No theme files found in {themes_dir}")
        return 1
    
    print(f"Found {len(theme_files)} theme(s) in {themes_dir}")
    print()
    
    # Copy each theme file
    copied = 0
    for theme_file in theme_files:
        src = os.path.join(themes_dir, theme_file)
        dst = os.path.join(bundled_themes_dir, theme_file)
        
        # Validate it's a valid JSON file
        try:
            with open(src, 'r') as f:
                theme_data = json.load(f)
            
            # Copy the file
            shutil.copy2(src, dst)
            print(f"✓ Copied: {theme_file}")
            copied += 1
            
        except json.JSONDecodeError as e:
            print(f"✗ Skipped {theme_file}: Invalid JSON - {e}")
        except Exception as e:
            print(f"✗ Error copying {theme_file}: {e}")
    
    print()
    print(f"Successfully copied {copied} theme(s) to {bundled_themes_dir}")
    print()
    print("Next steps:")
    print("1. Review the copied themes in bundled_themes/")
    print("2. Rebuild the snap to include the bundled themes")
    print("3. The app will automatically install bundled themes on first run")
    
    return 0

if __name__ == '__main__':
    exit(main())
