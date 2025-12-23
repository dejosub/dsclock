#!/usr/bin/env python3
"""
Theme class for managing clock appearance properties.
"""

import os
import json
from property_bag import PropertyBag


class Theme(PropertyBag):
    """
    Property bag for theme (appearance) settings.
    Handles loading/saving theme files and provides 'default' theme fallback.
    """
    
    # Default values for all theme properties
    DEFAULTS = {
        # Visibility toggles
        'show_numbers': True,
        'show_hour_ticks': True,
        'show_minute_ticks': True,
        
        # Background
        'background_color': (1.0, 1.0, 1.0),  # White background
        'background_opacity': 0.7,
        'face_texture_source': 'builtin',
        'face_texture_name': None,
        'enable_face_color': True,
        'enable_face_texture': False,
        'face_color_opacity': 0.85,
        'face_texture_opacity': 1.0,
        
        # Rim
        'rim_width': 0.01,
        'rim_opacity': 1.0,
        'rim_color': (0.0, 0.0, 0.0),  # Black rim
        
        # Hour ticks
        'hour_tick_size': 0.022,
        'hour_tick_position': 0.975,
        'hour_tick_style': 'square',
        'hour_tick_aspect_ratio': 1.0,
        
        # Minute ticks
        'minute_tick_size': 0.018,
        'minute_tick_position': 0.975,
        'minute_tick_style': 'rectangular',
        'minute_tick_aspect_ratio': 0.2871745887492587,
        
        # Numbers
        'number_position': 0.823,
        'number_size': 0.155,
        'number_font': 'Sans',
        'number_bold': True,
        'use_roman_numerals': False,
        'show_cardinal_numbers_only': False,
        
        # Hour hand
        'hour_hand_length': 0.509,
        'hour_hand_tail': 0.099,
        'hour_hand_width': 0.041,  # Line width for geometric hands
        'hour_hand_image_width': 1.0,  # Width scale factor for hand images
        'hour_hand_image_source': 'none',  # 'none', 'builtin', or 'user'
        'hour_hand_image_name': None,
        
        # Minute hand
        'minute_hand_length': 0.74,
        'minute_hand_tail': 0.16,
        'minute_hand_width': 0.025,  # Line width for geometric hands
        'minute_hand_image_width': 1.0,  # Width scale factor for hand images
        'minute_hand_image_source': 'none',
        'minute_hand_image_name': None,
        
        # Second hand
        'second_hand_length': 0.88,
        'second_hand_tail': 0.2,
        'second_hand_width': 0.01,  # Line width for geometric hands
        'second_hand_image_width': 1.0,  # Width scale factor for hand images
        'second_hand_image_source': 'none',
        'second_hand_image_name': None,
        
        # Center dot
        'center_dot_radius': 0.04,
        
        # Date box
        'date_box_width': 1.18,
        'date_box_height': 0.24,
        'date_box_margin': 0.12,
        'date_format': '%a, %d %b',
        'date_font_size': 0.1,  # Relative to radius
        'date_font': 'Sans',
        'date_bold': False,
        
        # Colors
        'hands_color': (0.0, 0.0, 0.0),  # Black hands
        'numbers_color': (0.0, 0.0, 0.0),  # Black numbers
        'ticks_color': (0.0, 0.0, 0.0),  # Black hour ticks
        'minute_ticks_color': (0.0, 0.0, 0.0),  # Black minute ticks
        'border_color': (0.0, 0.0, 0.0),  # Black border
        'second_hand_color': (1.0, 0.0, 0.0),  # Red second hand
        'date_text_color': (0.0, 0.0, 0.0),  # Black date text
    }
    
    def __init__(self, name='default', themes_dir=None):
        """
        Initialize theme.
        
        Args:
            name: Theme name
            themes_dir: Directory containing theme files
        """
        self.name = name
        self.themes_dir = themes_dir
        
        # Determine file path
        if name == 'default' or not themes_dir:
            file_path = None  # Default theme never saved to disk
        else:
            file_path = os.path.join(themes_dir, f"{name}.json")
        
        super().__init__(file_path)
        
        # Initialize with defaults
        self._properties = self.DEFAULTS.copy()
        self._dirty = False
    
    def load(self):
        """
        Load theme from disk.
        'default' theme always uses hardcoded DEFAULTS.
        Corrupted theme files fall back to defaults with user notification.
        
        Returns:
            bool: True if loaded successfully, False if using defaults
        """
        if self.name == 'default':
            # Default theme never loads from disk
            self._properties = self.DEFAULTS.copy()
            self._dirty = False
            return True
        
        if not self.file_path or not os.path.exists(self.file_path):
            print(f"Theme '{self.name}' not found, using defaults")
            self._properties = self.DEFAULTS.copy()
            self._dirty = False
            return False
        
        try:
            with open(self.file_path, 'r') as f:
                loaded = json.load(f)
            
            # Start with defaults, overlay loaded values
            self._properties = self.DEFAULTS.copy()
            self._properties.update(loaded)
            
            # Backward compatibility: migrate old hand width schema to new schema
            # Old schema: hand_width was used for both geometric and image modes
            # New schema: hand_width for geometric, hand_image_width for images
            # Only add image_width if it doesn't exist (additive only)
            for hand_type in ['hour', 'minute', 'second']:
                image_width_key = f'{hand_type}_hand_image_width'
                width_key = f'{hand_type}_hand_width'
                
                # If the loaded theme doesn't have image_width, it's an old theme
                # Keep the loaded width value for geometric mode (already loaded)
                # Add default image_width (1.0) for image mode
                if image_width_key not in loaded:
                    # Old theme - preserve loaded width, add default image_width
                    self._properties[image_width_key] = 1.0
                # If it does have image_width, both values are already loaded correctly
            
            self._dirty = False
            return True
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"ERROR: Theme file '{self.file_path}' is corrupted: {e}")
            print(f"Falling back to default theme. Corrupted file left as-is.")
            
            # Fall back to defaults
            self._properties = self.DEFAULTS.copy()
            self._dirty = False
            return False
    
    def save(self):
        """
        Save theme to disk.
        'default' theme is never saved.
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if self.name == 'default':
            # Never save default theme
            return False
        
        return super().save()
    
    def duplicate(self, new_name):
        """
        Create a duplicate theme with a different name.
        Used for "Duplicate Theme" action.
        
        Args:
            new_name: Name for the new theme
            
        Returns:
            Theme: New theme instance with copied properties
        """
        new_theme = Theme(new_name, self.themes_dir)
        new_theme._properties = self._properties.copy()
        new_theme._dirty = True
        return new_theme
    
    @staticmethod
    def list_available_themes(themes_dir):
        """
        Discover available themes by scanning themes directory.
        
        Args:
            themes_dir: Directory to scan for theme files
            
        Returns:
            list: List of theme names (without .json extension), always includes 'default'
        """
        themes = ['default']  # Always include default
        
        if not themes_dir or not os.path.exists(themes_dir):
            return themes
        
        try:
            for filename in os.listdir(themes_dir):
                if filename.endswith('.json'):
                    theme_name = filename[:-5]  # Remove .json extension
                    if theme_name != 'default':  # Don't add default twice
                        themes.append(theme_name)
        except OSError:
            pass
        
        return sorted(themes)
