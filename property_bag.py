#!/usr/bin/env python3
"""
Base PropertyBag class for unified property storage with save/load capabilities.
"""

import json
import os


class PropertyBag:
    """
    Base class for property bag storage with JSON persistence.
    Provides unified storage, dirty tracking, and save/load functionality.
    """
    
    # Subclasses must define DEFAULTS dict
    DEFAULTS = {}
    
    def __init__(self, file_path=None):
        """
        Initialize property bag.
        
        Args:
            file_path: Path to JSON file for persistence (None for in-memory only)
        """
        self.file_path = file_path
        self._properties = self.DEFAULTS.copy()
        self._dirty = False
    
    def set(self, key, value):
        """
        Set a single property and mark as dirty.
        
        Args:
            key: Property name
            value: Property value
            
        Raises:
            AssertionError: If key is not in DEFAULTS
        """
        assert key in self.DEFAULTS, f"Unknown property '{key}' in {self.__class__.__name__}"
        
        if self._properties.get(key) != value:
            self._properties[key] = value
            self._dirty = True
    
    def get(self, key, default=None):
        """
        Get a property value.
        
        Args:
            key: Property name
            default: Default value if not set (uses DEFAULTS if None)
            
        Returns:
            Property value
            
        Raises:
            AssertionError: If key is not in DEFAULTS
        """
        assert key in self.DEFAULTS, f"Unknown property '{key}' in {self.__class__.__name__}"
        
        if default is not None:
            return self._properties.get(key, default)
        return self._properties.get(key, self.DEFAULTS[key])
    
    @property
    def is_dirty(self):
        """Check if properties have unsaved changes."""
        return self._dirty
    
    def load(self):
        """
        Load properties from JSON file.
        Sets _dirty to False after successful load.
        Missing properties are filled from DEFAULTS.
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        if not self.file_path or not os.path.exists(self.file_path):
            # Use defaults
            self._properties = self.DEFAULTS.copy()
            self._dirty = False
            return False
        
        try:
            with open(self.file_path, 'r') as f:
                loaded = json.load(f)
            
            # Start with defaults, then overlay loaded values
            self._properties = self.DEFAULTS.copy()
            self._properties.update(loaded)
            
            self._dirty = False
            return True
            
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading {self.file_path}: {e}")
            # Keep defaults on error
            self._properties = self.DEFAULTS.copy()
            self._dirty = False
            return False
    
    def save(self):
        """
        Save properties to JSON file.
        Sets _dirty to False after successful save.
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self.file_path:
            return False
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            
            with open(self.file_path, 'w') as f:
                json.dump(self._properties, f, indent=2)
            
            self._dirty = False
            return True
            
        except IOError as e:
            print(f"Error saving {self.file_path}: {e}")
            return False
    
    def get_all(self):
        """
        Get all properties as a dictionary.
        
        Returns:
            dict: Copy of all properties
        """
        return self._properties.copy()
    
    def duplicate(self):
        """
        Create a duplicate of this property bag with same properties.
        The duplicate will be marked as dirty.
        
        Returns:
            PropertyBag: New instance with copied properties
        """
        duplicate = self.__class__(file_path=None)
        duplicate._properties = self._properties.copy()
        duplicate._dirty = True
        return duplicate
