#!/usr/bin/env python3
"""
Settings class for managing behavioral settings.
"""

from property_bag import PropertyBag


class Settings(PropertyBag):
    """
    Property bag for behavioral settings (non-appearance).
    Handles window geometry, behavioral toggles, and active theme name.
    """
    
    # Default values for all settings
    DEFAULTS = {
        # Window geometry (nullable)
        'window_x': None,
        'window_y': None,
        'width': 400,
        'height': 460,
        
        # Clock behavior
        'clock_size': 400,
        'show_date_box': True,
        'show_second_hand': True,
        'minute_hand_snap': True,
        'always_on_top': False,
        
        # Active theme
        'active_theme_name': 'default',
    }
    
    def __init__(self, settings_file):
        """
        Initialize settings.
        
        Args:
            settings_file: Path to settings.json file
        """
        super().__init__(settings_file)
