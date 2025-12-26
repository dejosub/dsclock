#!/usr/bin/env python3
"""
Analog Clock - A beautiful analog clock with Arabic numerals
Features:
- White transparent background
- Red seconds hand
- Slim, straight minute and hour hands
- Hour ticks
- Round shape (not square)
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
import cairo
import math
import os
import sys
import json
import subprocess
import traceback
from datetime import datetime
from dialogs import CustomizeDialog
from theme import Theme
from settings import Settings


def show_exception_dialog(exc_type, exc_value, exc_traceback):
    """Show a dialog with exception details that can be copied"""
    # Format the exception
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    error_text = ''.join(tb_lines)
    
    # Create dialog
    dialog = Gtk.MessageDialog(
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.CLOSE,
        text="An error occurred"
    )
    dialog.format_secondary_text("The application encountered an unexpected error.")
    
    # Create scrolled window with error text
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.set_min_content_height(300)
    scrolled.set_min_content_width(600)
    
    # Create text view with error details
    text_view = Gtk.TextView()
    text_view.set_editable(False)
    text_view.set_monospace(True)
    text_view.get_buffer().set_text(error_text)
    scrolled.add(text_view)
    
    # Add to dialog content area
    content = dialog.get_content_area()
    content.pack_start(scrolled, True, True, 0)
    
    # Add copy button
    copy_button = Gtk.Button(label="Copy to Clipboard")
    def on_copy_clicked(button):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(error_text, -1)
    copy_button.connect('clicked', on_copy_clicked)
    content.pack_start(copy_button, False, False, 0)
    
    dialog.show_all()
    dialog.run()
    dialog.destroy()
    
    # Also print to console
    print(error_text, file=sys.stderr)


def exception_hook(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    # Don't catch KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    # Show dialog with exception
    show_exception_dialog(exc_type, exc_value, exc_traceback)


# Install global exception handler
sys.excepthook = exception_hook


# ============================================================================
# VISUAL CONFIGURATION
# ============================================================================

CLOCK_MARGIN = 20  # Space between clock edge and window edge
INPUT_SHAPE_MARGIN = 10  # Input shape (clickable area) margin
DATE_BOX_CORNER_RADIUS = 0.05  # Corner radius (as fraction of radius)

# ============================================================================



class AnalogClock(Gtk.Window):
    def __init__(self):
        super().__init__()
        
        # Config file paths
        snap_user_data = os.environ.get('SNAP_USER_DATA')
        if snap_user_data:
            self.config_dir = snap_user_data
            self.autostart_dir = os.path.join(snap_user_data, '.config', 'autostart')
        else:
            self.config_dir = os.path.expanduser('~/.config/dsclock')
            self.autostart_dir = os.path.expanduser('~/.config/autostart')
        
        self.settings_file = os.path.join(self.config_dir, 'settings.json')
        self.themes_dir = os.path.join(self.config_dir, 'themes')
        self.autostart_file = os.path.join(self.autostart_dir, 'dsclock.desktop')
        
        # Install bundled themes on first run
        self._install_bundled_themes()
        
        # Initialize Settings and Theme objects
        self.settings = Settings(self.settings_file)
        self.settings.load()
        
        # Load active theme
        active_theme_name = self.settings.get('active_theme_name')
        self.theme = Theme(active_theme_name, self.themes_dir)
        self.theme.load()
        
        # Initialize hand image cache
        self._hand_image_cache = {}
        
        # Window setup
        self.set_title("Analog Clock")
        self.set_decorated(False)  # Remove window decorations
        self.set_resizable(True)  # Always allow resizing (just hide borders when not in resize mode)
        
        # Set window type hint for proper behavior
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        
        # Set window size and position from settings
        width = self.settings.get('width')
        height = self.settings.get('height')
        self.set_default_size(width, height)
        
        window_x = self.settings.get('window_x')
        window_y = self.settings.get('window_y')
        if window_x is not None and window_y is not None:
            self.move(window_x, window_y)
        
        # Enable transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        
        self.set_app_paintable(True)
        
        # Set always on top if enabled
        if self.settings.get('always_on_top'):
            self.set_keep_above(True)
        
        # Use EventBox to capture mouse events
        self.event_box = Gtk.EventBox()
        # Note: EventBox needs a visible window to receive events
        # We'll handle transparency through the drawing
        
        # Drawing area
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.connect('draw', self.on_draw)
        
        # Add drawing area to event box
        self.event_box.add(self.drawing_area)
        
        # Enable events on event box
        self.event_box.set_events(Gdk.EventMask.BUTTON_PRESS_MASK | 
                                  Gdk.EventMask.BUTTON_RELEASE_MASK | 
                                  Gdk.EventMask.POINTER_MOTION_MASK)
        self.event_box.connect('button-press-event', self.on_button_press)
        self.event_box.connect('button-release-event', self.on_button_release)
        self.event_box.connect('motion-notify-event', self.on_motion_notify)
        
        self.add(self.event_box)
        
        # Update every second
        GLib.timeout_add(1000, self.update_clock)
        
        # Window events
        self.connect('destroy', self.on_destroy)
        self.connect('key-press-event', self.on_key_press)
        self.connect('realize', self.on_realize)
        self.connect('size-allocate', self.on_size_allocate)
        self.connect('configure-event', self.on_configure)

        self._texture_surface_cache = {}

    def get_builtin_textures_dir(self):
        snap_dir = os.environ.get('SNAP')
        if snap_dir:
            return os.path.join(snap_dir, 'lib', 'dsclock', 'assets', 'textures')
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'textures')

    def get_user_textures_dir(self):
        snap_user_data = os.environ.get('SNAP_USER_DATA')
        if snap_user_data:
            return os.path.join(snap_user_data, 'textures')
        return os.path.expanduser('~/.config/dsclock/textures')
    
    def get_user_hands_dir(self):
        snap_user_data = os.environ.get('SNAP_USER_DATA')
        if snap_user_data:
            return os.path.join(snap_user_data, 'hands')
        return os.path.expanduser('~/.config/dsclock/hands')
    
    def resolve_hand_image_path(self, hand_type):
        """
        Resolve path to hand image for specified hand type (hour, minute, second).
        Uses processed images if available, falls back to original if not.
        Returns None if no hand image is configured.
        """
        source = self.theme.get(f'{hand_type}_hand_image_source')
        name = self.theme.get(f'{hand_type}_hand_image_name')
        
        if source == 'none' or not name:
            return None
        
        if source == 'user':
            hand_dir = os.path.join(self.get_user_hands_dir(), name)
        else:  # builtin
            hand_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'hands', name)
        
        # Try processed image first
        processed_path = os.path.join(hand_dir, 'processed', f'{hand_type}.png')
        if os.path.exists(processed_path):
            return processed_path
        
        # Fall back to original image
        original_path = os.path.join(hand_dir, 'original', f'{hand_type}.png')
        if os.path.exists(original_path):
            return original_path
        
        # Legacy: try direct path (for backwards compatibility)
        legacy_path = os.path.join(hand_dir, f'{hand_type}.png')
        return legacy_path if os.path.exists(legacy_path) else None

    def resolve_texture_path(self, source, name):
        if not name:
            return None
        if source == 'user':
            return os.path.join(self.get_user_textures_dir(), name)
        return os.path.join(self.get_builtin_textures_dir(), name)

    def _get_texture_surface(self, path):
        if not path:
            return None
        if path in self._texture_surface_cache:
            return self._texture_surface_cache[path]
        if not os.path.exists(path):
            self._texture_surface_cache[path] = None
            return None
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            w = pixbuf.get_width()
            h = pixbuf.get_height()
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            ctx = cairo.Context(surface)
            Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
            ctx.paint()
            self._texture_surface_cache[path] = surface
            return surface
        except Exception:
            self._texture_surface_cache[path] = None
            return None

    def _create_cover_pattern(self, surface, center_x, center_y, target_radius):
        if surface is None:
            return None
        w = surface.get_width()
        h = surface.get_height()
        if w <= 0 or h <= 0:
            return None

        target_size = max(1.0, float(target_radius) * 2.0)
        scale = max(target_size / float(w), target_size / float(h))
        draw_w = float(w) * scale
        draw_h = float(h) * scale
        tx = float(center_x) - draw_w / 2.0
        ty = float(center_y) - draw_h / 2.0

        pattern = cairo.SurfacePattern(surface)
        pattern.set_extend(cairo.Extend.PAD)
        pattern.set_matrix(cairo.Matrix(xx=1.0 / scale, yy=1.0 / scale, x0=-tx / scale, y0=-ty / scale))
        return pattern
    
    def is_wayland(self):
        """Check if running on Wayland"""
        gdk_window = self.get_window()
        if gdk_window:
            return 'Wayland' in str(type(gdk_window))
        return 'WAYLAND_DISPLAY' in os.environ or os.environ.get('XDG_SESSION_TYPE') == 'wayland'
    
    def get_window_position_wayland(self):
        """Get window position on Wayland using window title matching"""
        try:
            # On Wayland, use gdbus to query window list
            result = subprocess.run(
                ['gdbus', 'call', '--session',
                 '--dest', 'org.gnome.Shell',
                 '--object-path', '/org/gnome/Shell',
                 '--method', 'org.gnome.Shell.Eval',
                 'global.get_window_actors().map(a => ({title: a.meta_window.title, x: a.x, y: a.y}))'],
                capture_output=True, text=True, timeout=2
            )
            
            if result.returncode == 0 and 'Analog Clock' in result.stdout:
                # Parse the output to find our window
                import re
                # This is a simplified parser - may need adjustment
                match = re.search(r"title: 'Analog Clock'.*?x: (\d+).*?y: (\d+)", result.stdout)
                if match:
                    return int(match.group(1)), int(match.group(2))
        except Exception:
            pass
        
        return None, None
    
    def get_window_position_x11(self):
        """Get window position using xwininfo (X11)"""
        try:
            # Get the X11 window ID
            gdk_window = self.get_window()
            if gdk_window and hasattr(gdk_window, 'get_xid'):
                xid = gdk_window.get_xid()
                
                # Use xwininfo to get actual position
                result = subprocess.run(['xwininfo', '-id', str(xid)], 
                                      capture_output=True, text=True, timeout=1)
                
                if result.returncode == 0:
                    x, y = None, None
                    for line in result.stdout.split('\n'):
                        if 'Absolute upper-left X:' in line:
                            x = int(line.split(':')[1].strip())
                        elif 'Absolute upper-left Y:' in line:
                            y = int(line.split(':')[1].strip())
                    
                    if x is not None and y is not None:
                        return x, y
        except Exception:
            pass
        
        return None, None
    
    def get_window_position(self):
        """Get window position (auto-detect Wayland/X11)"""
        if self.is_wayland():
            return self.get_window_position_wayland()
        else:
            return self.get_window_position_x11()
    
    def save_geometry(self):
        """Save current window geometry (position only - settings and theme are saved separately)"""
        try:
            # Try to get actual position
            x, y = self.get_window_position()
            
            if x is not None and y is not None:
                # Update settings with new position
                self.settings.set('window_x', x)
                self.settings.set('window_y', y)
            
            # Get current window size from allocation
            allocation = self.get_allocation()
            if allocation:
                width = allocation.width
                height = allocation.height
                # Update settings with current size
                self.settings.set('width', width)
                self.settings.set('height', height)
            
            # Save settings (which includes position and size)
            self.settings.save()
            
        except Exception as e:
            print(f"ERROR in save_geometry: {e}")
            traceback.print_exc()
    
    def on_configure(self, widget, event):
        """Called when window is moved or resized"""
        # Use allocation to get client area size (excluding decorations)
        allocation = self.get_allocation()
        width = allocation.width
        height = allocation.height
        
        # Update settings
        self.settings.set('width', width)
        self.settings.set('height', height)
        
        return False
    
    def _install_bundled_themes(self):
        """Install bundled themes to user's themes directory on first run."""
        import shutil
        
        # Determine bundled themes directory
        snap_dir = os.environ.get('SNAP')
        if snap_dir:
            bundled_dir = os.path.join(snap_dir, 'lib', 'dsclock', 'bundled_themes')
        else:
            # Running from source
            bundled_dir = os.path.join(os.path.dirname(__file__), 'bundled_themes')
        
        # Check if bundled themes exist
        if not os.path.exists(bundled_dir):
            return
        
        # Create user themes directory if it doesn't exist
        os.makedirs(self.themes_dir, exist_ok=True)
        
        # Copy each bundled theme if it doesn't already exist
        try:
            for filename in os.listdir(bundled_dir):
                if filename.endswith('.json'):
                    src = os.path.join(bundled_dir, filename)
                    dst = os.path.join(self.themes_dir, filename)
                    
                    # Only copy if destination doesn't exist (don't overwrite user themes)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
        except Exception as e:
            print(f"Warning: Could not install bundled themes: {e}")
    
    def on_destroy(self, widget):
        """Called when window is closed"""
        # Get window position and save
        x, y = self.get_window_position()
        if x is not None and y is not None:
            self.settings.set('window_x', x)
            self.settings.set('window_y', y)
        
        # Save settings and theme
        self.settings.save()
        self.theme.save()
        
        Gtk.main_quit()
    
    def on_realize(self, widget):
        """Called when window is realized"""
        # On X11, use wmctrl to ensure exact position (GTK's move() may not be precise)
        window_x = self.settings.get('window_x')
        window_y = self.settings.get('window_y')
        if not self.is_wayland() and window_x is not None and window_y is not None:
            GLib.timeout_add(50, self.restore_position_x11)
        
        # Set input shape after window is realized
        self.update_input_shape()
    
    def restore_position_x11(self):
        """Fine-tune window position using wmctrl (X11 only)"""
        try:
            gdk_window = self.get_window()
            window_x = self.settings.get('window_x')
            window_y = self.settings.get('window_y')
            if gdk_window and window_x is not None and window_y is not None:
                # On X11, use wmctrl for precise positioning
                xid = gdk_window.get_xid()
                subprocess.run(['wmctrl', '-i', '-r', str(xid), '-e', 
                              f'0,{window_x},{window_y},-1,-1'],
                             timeout=1)
        except Exception:
            pass
        
        return False  # Don't repeat
    
    def on_key_press(self, widget, event):
        """Handle keyboard events"""
        if event.keyval == Gdk.KEY_Escape or event.keyval == Gdk.KEY_q:
            self.save_geometry()
            Gtk.main_quit()
    
    def on_button_press(self, widget, event):
        """Handle mouse button press for dragging and context menu"""
        if event.button == 1:  # Left mouse button
            # Start dragging
            gdk_window = self.get_window()
            if gdk_window:
                gdk_window.begin_move_drag(
                    event.button,
                    int(event.x_root),
                    int(event.y_root),
                    event.time
                )
        elif event.button == 3:  # Right mouse button - context menu
            self.show_context_menu(event)
        return True
    
    def on_button_release(self, widget, event):
        """Handle mouse button release"""
        # Save position after drag completes
        if event.button == 1:
            GLib.timeout_add(100, self.save_after_drag)
        return True
    
    def save_after_drag(self):
        """Save position after a drag operation completes"""
        self.save_geometry()
        return False  # Don't repeat
    
    def show_context_menu(self, event):
        """Show right-click context menu"""
        menu = Gtk.Menu()
        
        # Auto Start checkbox
        autostart_item = Gtk.CheckMenuItem(label="Auto Start on Logon")
        autostart_item.set_active(self.is_autostart_enabled())
        autostart_item.connect("toggled", self.on_autostart_toggled)
        menu.append(autostart_item)
        
        # Show Date checkbox
        show_date_item = Gtk.CheckMenuItem(label="Show Date")
        show_date_item.set_active(self.settings.get('show_date_box'))
        show_date_item.connect("toggled", self.on_show_date_toggled)
        menu.append(show_date_item)
        
        # Show Seconds checkbox
        show_seconds_item = Gtk.CheckMenuItem(label="Show Seconds")
        show_seconds_item.set_active(self.settings.get('show_second_hand'))
        show_seconds_item.connect("toggled", self.on_show_seconds_toggled)
        menu.append(show_seconds_item)
        
        # Always on Top checkbox
        always_on_top_item = Gtk.CheckMenuItem(label="Always on Top")
        always_on_top_item.set_active(self.settings.get('always_on_top'))
        always_on_top_item.connect("toggled", self.on_always_on_top_toggled)
        menu.append(always_on_top_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Customize menu item (unified dialog)
        customize_item = Gtk.MenuItem(label="Customize...")
        customize_item.connect("activate", self.on_customize_clicked)
        menu.append(customize_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Exit menu item
        exit_item = Gtk.MenuItem(label="Exit")
        exit_item.connect("activate", self.on_exit_clicked)
        menu.append(exit_item)
        
        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)
    
    def on_autostart_toggled(self, widget):
        """Handle auto start toggle"""
        if widget.get_active():
            self.enable_autostart()
        else:
            self.disable_autostart()
    
    def on_show_date_toggled(self, widget):
        """Handle show date toggle"""
        show_date = widget.get_active()
        self.settings.set('show_date_box', show_date)
        
        # Adjust window height
        width = self.settings.get('width')
        if show_date:
            height = width + 60
        else:
            height = width
        
        self.settings.set('height', height)
        self.resize(width, height)
        self.settings.save()
        self.queue_draw()
    
    def on_show_seconds_toggled(self, widget):
        """Handle show seconds toggle"""
        self.settings.set('show_second_hand', widget.get_active())
        self.settings.save()
        self.queue_draw()
    
    def on_always_on_top_toggled(self, widget):
        """Handle always on top toggle"""
        always_on_top = widget.get_active()
        self.settings.set('always_on_top', always_on_top)
        self.settings.save()
        self.set_keep_above(always_on_top)
    
    def on_customize_clicked(self, widget):
        """Handle customize menu item - open unified customization dialog"""
        dialog = CustomizeDialog(self)
        dialog.show()
    
    def update_window_size(self):
        """Update window size based on clock_size"""
        clock_size = self.settings.get('clock_size')
        show_date = self.settings.get('show_date_box')
        date_box_height = self.theme.get('date_box_height')
        date_box_margin = self.theme.get('date_box_margin')
        
        # Calculate height to include date box if shown
        radius = (clock_size - 2 * CLOCK_MARGIN) / 2
        date_box_extra = 0
        if show_date:
            date_box_extra = int(radius * (date_box_height + date_box_margin)) + 20
        
        new_height = clock_size + date_box_extra
        self.resize(clock_size, new_height)
        self.settings.set('width', clock_size)
        self.settings.set('height', new_height)
    
    def on_exit_clicked(self, widget):
        """Handle exit menu item"""
        # Get window position and save
        x, y = self.get_window_position()
        if x is not None and y is not None:
            self.settings.set('window_x', x)
            self.settings.set('window_y', y)
        
        # Save settings and theme
        self.settings.save()
        self.theme.save()
        
        Gtk.main_quit()
    
    def is_autostart_enabled(self):
        """Check if autostart is enabled"""
        return os.path.exists(self.autostart_file)
    
    def enable_autostart(self):
        """Enable auto start on logon"""
        os.makedirs(self.autostart_dir, exist_ok=True)
        
        # Determine the executable path
        if os.path.exists('/snap/dsclock/current'):
            # Running as snap
            exec_path = 'dsclock'
        else:
            # Running from source
            exec_path = os.path.abspath(__file__)
        
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=Analog Clock
Exec={exec_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
        
        with open(self.autostart_file, 'w') as f:
            f.write(desktop_content)
    
    def disable_autostart(self):
        """Disable auto start on logon"""
        if os.path.exists(self.autostart_file):
            os.remove(self.autostart_file)
    
    def on_motion_notify(self, widget, event):
        """Handle mouse motion"""
        return True
    
    def on_size_allocate(self, widget, allocation):
        """Update input shape when window is resized"""
        self.update_input_shape()
    
    def update_input_shape(self):
        """Create circular input shape mask"""
        # Make sure window is realized
        gdk_window = self.get_window()
        if not gdk_window:
            return
            
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        
        if width <= 0 or height <= 0:
            return
        
        # Create a surface for the mask
        surface = cairo.ImageSurface(cairo.FORMAT_A1, width, height)
        cr = cairo.Context(surface)
        
        # Clear the surface
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        
        # Draw a circle for the input region
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgba(1, 1, 1, 1)
        
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - INPUT_SHAPE_MARGIN
        
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.fill()
        
        # Create region from surface
        region = Gdk.cairo_region_create_from_surface(surface)
        gdk_window.input_shape_combine_region(region, 0, 0)
    
    def update_clock(self):
        """Trigger redraw every second"""
        self.drawing_area.queue_draw()
        return True
    
    def on_draw(self, widget, cr):
        """Draw the clock face and hands"""
        # Get dimensions
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        
        # Get settings
        show_date = self.settings.get('show_date_box')
        show_seconds = self.settings.get('show_second_hand')
        date_box_margin = self.theme.get('date_box_margin')
        date_box_height = self.theme.get('date_box_height')
        date_box_width = self.theme.get('date_box_width')
        
        # Calculate radius accounting for date box if shown
        if show_date:
            max_radius_width = width / 2 - CLOCK_MARGIN
            max_radius_height = (height - 2 * CLOCK_MARGIN) / (2 + date_box_margin + date_box_height)
            radius = min(max_radius_width, max_radius_height)
            center_y = CLOCK_MARGIN + radius
        else:
            radius = min(width, height) / 2 - CLOCK_MARGIN
            center_y = height / 2
        
        center_x = width / 2
        
        # Clear background with full transparency
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        
        # Draw the clock using shared rendering method
        self._draw_clock_face(cr, center_x, center_y, radius, show_date, show_seconds, date_box_margin, date_box_height, date_box_width)
    
    def _draw_clock_face(self, cr, center_x, center_y, radius, show_date=False, show_seconds=True, date_box_margin=0.08, date_box_height=0.2, date_box_width=1.2):
        """Shared method to draw clock face - used by both main rendering and preview generation"""
        
        # Get theme properties
        rim_width = self.theme.get('rim_width')
        rim_color = self.theme.get('rim_color')
        rim_opacity = self.theme.get('rim_opacity')
        enable_face_color = self.theme.get('enable_face_color')
        background_color = self.theme.get('background_color')
        face_color_opacity = self.theme.get('face_color_opacity')
        enable_face_texture = self.theme.get('enable_face_texture')
        face_texture_name = self.theme.get('face_texture_name')
        face_texture_source = self.theme.get('face_texture_source')
        face_texture_opacity = self.theme.get('face_texture_opacity')
        hands_color = self.theme.get('hands_color')
        center_dot_radius = self.theme.get('center_dot_radius')
        
        outer_radius = radius
        rim_thickness = outer_radius * rim_width
        face_radius = max(1.0, outer_radius - rim_thickness)

        # Draw background color if enabled
        if enable_face_color:
            cr.set_source_rgba(background_color[0], background_color[1], background_color[2], face_color_opacity)
            cr.arc(center_x, center_y, face_radius, 0, 2 * math.pi)
            cr.fill()
        
        # Draw texture on top if enabled
        if enable_face_texture and face_texture_name:
            face_path = self.resolve_texture_path(face_texture_source, face_texture_name)
            face_surface = self._get_texture_surface(face_path)
            if face_surface is not None:
                pattern = self._create_cover_pattern(face_surface, center_x, center_y, face_radius)
                cr.save()
                cr.arc(center_x, center_y, face_radius, 0, 2 * math.pi)
                cr.clip()
                cr.set_source(pattern)
                cr.paint_with_alpha(face_texture_opacity)
                cr.restore()

        # Draw rim with solid color
        cr.set_source_rgba(rim_color[0], rim_color[1], rim_color[2], rim_opacity)
        cr.arc(center_x, center_y, outer_radius, 0, 2 * math.pi)
        cr.arc(center_x, center_y, face_radius, 0, 2 * math.pi)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.fill()
        
        # Draw hour ticks and Arabic numerals
        self.draw_ticks_and_numbers(cr, center_x, center_y, face_radius)
        
        # Get current time
        now = datetime.now()
        hours = now.hour % 12
        minutes = now.minute
        seconds = now.second
        
        # Draw hands
        self.draw_hour_hand(cr, center_x, center_y, face_radius, hours, minutes)
        self.draw_minute_hand(cr, center_x, center_y, face_radius, minutes, seconds)
        if show_seconds:
            self.draw_second_hand(cr, center_x, center_y, face_radius, seconds)
        
        # Draw center dot
        cr.set_source_rgba(hands_color[0], hands_color[1], hands_color[2], 0.9)
        cr.arc(center_x, center_y, face_radius * center_dot_radius, 0, 2 * math.pi)
        cr.fill()
        
        # Draw date box below clock face (if enabled)
        if show_date:
            date_box_y = center_y + outer_radius + outer_radius * date_box_margin
            date_box_outer_width = outer_radius * date_box_width
            date_box_outer_height = outer_radius * date_box_height
            date_box_x = center_x - date_box_outer_width / 2
            
            # Calculate rim thickness for date box
            date_box_rim_thickness = outer_radius * rim_width
            
            # Inner dimensions (face area)
            date_box_inner_width = max(1.0, date_box_outer_width - 2 * date_box_rim_thickness)
            date_box_inner_height = max(1.0, date_box_outer_height - 2 * date_box_rim_thickness)
            date_box_inner_x = date_box_x + date_box_rim_thickness
            date_box_inner_y = date_box_y + date_box_rim_thickness
            
            outer_corner_radius = outer_radius * DATE_BOX_CORNER_RADIUS
            inner_corner_radius = max(0.0, outer_corner_radius - date_box_rim_thickness)
            
            # Get theme properties for date box
            date_text_color = self.theme.get('date_text_color')
            date_font = self.theme.get('date_font')
            date_bold = self.theme.get('date_bold')
            date_font_size = self.theme.get('date_font_size')
            
            # Draw rim first (outer rectangle minus inner rectangle using even-odd fill rule)
            cr.set_source_rgba(rim_color[0], rim_color[1], rim_color[2], rim_opacity)
            self.draw_rounded_rectangle(cr, date_box_x, date_box_y, date_box_outer_width, date_box_outer_height, outer_corner_radius)
            self.draw_rounded_rectangle(cr, date_box_inner_x, date_box_inner_y, date_box_inner_width, date_box_inner_height, inner_corner_radius)
            cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            cr.fill()
            
            # Draw inner face - color first if enabled
            if enable_face_color:
                cr.set_source_rgba(background_color[0], background_color[1], background_color[2], face_color_opacity)
                self.draw_rounded_rectangle(cr, date_box_inner_x, date_box_inner_y, date_box_inner_width, date_box_inner_height, inner_corner_radius)
                cr.fill()
            
            # Draw texture on top if enabled
            if enable_face_texture and face_texture_name:
                date_box_path = self.resolve_texture_path(face_texture_source, face_texture_name)
                date_box_surface = self._get_texture_surface(date_box_path)
                if date_box_surface is not None:
                    # Create pattern centered on date box inner area
                    date_box_center_x = date_box_inner_x + date_box_inner_width / 2
                    date_box_center_y = date_box_inner_y + date_box_inner_height / 2
                    date_box_radius = max(date_box_inner_width, date_box_inner_height) / 2
                    pattern = self._create_cover_pattern(date_box_surface, date_box_center_x, date_box_center_y, date_box_radius)
                    cr.save()
                    self.draw_rounded_rectangle(cr, date_box_inner_x, date_box_inner_y, date_box_inner_width, date_box_inner_height, inner_corner_radius)
                    cr.clip()
                    cr.set_source(pattern)
                    cr.paint_with_alpha(face_texture_opacity)
                    cr.restore()
            
            # Draw date text (centered in inner area)
            date_format = self.theme.get('date_format')
            date_text = now.strftime(date_format)
            cr.set_source_rgba(date_text_color[0], date_text_color[1], date_text_color[2], 0.9)
            date_font_weight = cairo.FONT_WEIGHT_BOLD if date_bold else cairo.FONT_WEIGHT_NORMAL
            cr.select_font_face(date_font, cairo.FONT_SLANT_NORMAL, date_font_weight)
            cr.set_font_size(radius * date_font_size)
            extents = cr.text_extents(date_text)
            text_x = center_x - extents.width / 2
            text_y = date_box_inner_y + date_box_inner_height / 2 + extents.height / 2
            cr.move_to(text_x, text_y)
            cr.show_text(date_text)
        
    def draw_rounded_rectangle(self, cr, x, y, width, height, radius):
        """Draw a rounded rectangle path"""
        cr.new_sub_path()
        cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
        cr.arc(x + width - radius, y + radius, radius, 3 * math.pi / 2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        cr.close_path()
    
    def _to_roman_numeral(self, num):
        """Convert number (1-12) to Roman numeral"""
        roman_map = {
            1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI',
            7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X', 11: 'XI', 12: 'XII'
        }
        return roman_map.get(num, str(num))
    
    def draw_ticks_and_numbers(self, cr, cx, cy, radius):
        """Draw hour ticks and numerals (Arabic or Roman)"""
        
        # Get theme properties
        show_hour_ticks = self.theme.get('show_hour_ticks')
        show_numbers = self.theme.get('show_numbers')
        show_minute_ticks = self.theme.get('show_minute_ticks')
        ticks_color = self.theme.get('ticks_color')
        numbers_color = self.theme.get('numbers_color')
        minute_ticks_color = self.theme.get('minute_ticks_color')
        hour_tick_size = self.theme.get('hour_tick_size')
        hour_tick_position = self.theme.get('hour_tick_position')
        hour_tick_style = self.theme.get('hour_tick_style')
        hour_tick_aspect_ratio = self.theme.get('hour_tick_aspect_ratio')
        minute_tick_size = self.theme.get('minute_tick_size')
        minute_tick_position = self.theme.get('minute_tick_position')
        minute_tick_style = self.theme.get('minute_tick_style')
        minute_tick_aspect_ratio = self.theme.get('minute_tick_aspect_ratio')
        number_position = self.theme.get('number_position')
        number_size = self.theme.get('number_size')
        number_font = self.theme.get('number_font')
        number_bold = self.theme.get('number_bold')
        use_roman_numerals = self.theme.get('use_roman_numerals')
        show_cardinal_numbers_only = self.theme.get('show_cardinal_numbers_only')
        
        for i in range(12):
            angle = math.radians(i * 30 - 90)  # -90 to start at 12 o'clock
            
            # Hour tick - draw based on style (if enabled)
            if show_hour_ticks:
                cr.set_source_rgba(ticks_color[0], ticks_color[1], ticks_color[2], 0.8)
                tick_size = radius * hour_tick_size
                
                if hour_tick_style == "round":
                    # Draw round tick (circle)
                    tick_radius = radius * hour_tick_position - tick_size
                    tick_x = cx + tick_radius * math.cos(angle)
                    tick_y = cy + tick_radius * math.sin(angle)
                    cr.arc(tick_x, tick_y, tick_size, 0, 2 * math.pi)
                    cr.fill()
                elif hour_tick_style == "rectangular":
                    # Draw rectangular tick (rotated with aspect ratio)
                    tick_center_radius = radius * hour_tick_position - tick_size
                    tick_x = cx + tick_center_radius * math.cos(angle)
                    tick_y = cy + tick_center_radius * math.sin(angle)
                    
                    # Calculate width and height based on aspect ratio
                    height = tick_size * 2
                    width = height * hour_tick_aspect_ratio
                    
                    cr.save()
                    cr.translate(tick_x, tick_y)
                    cr.rotate(angle + math.pi / 2)  # Rotate so one side faces center
                    cr.rectangle(-width / 2, -height / 2, width, height)
                    cr.fill()
                    cr.restore()
                else:
                    # Draw square tick (rotated)
                    tick_center_radius = radius * hour_tick_position - tick_size
                    tick_x = cx + tick_center_radius * math.cos(angle)
                    tick_y = cy + tick_center_radius * math.sin(angle)
                    
                    cr.save()
                    cr.translate(tick_x, tick_y)
                    cr.rotate(angle + math.pi / 2)  # Rotate so one side faces center
                    cr.rectangle(-tick_size, -tick_size, tick_size * 2, tick_size * 2)
                    cr.fill()
                    cr.restore()
            
            # Numerals (if enabled)
            if show_numbers:
                number = 12 if i == 0 else i
                
                # Skip non-cardinal numbers if cardinal-only mode is enabled
                if show_cardinal_numbers_only and number not in [12, 3, 6, 9]:
                    continue
                
                text = self._to_roman_numeral(number) if use_roman_numerals else str(number)
                
                # Position for numbers
                text_radius = radius * number_position
                text_x = cx + text_radius * math.cos(angle)
                text_y = cy + text_radius * math.sin(angle)
                
                # Draw number
                cr.set_source_rgba(numbers_color[0], numbers_color[1], numbers_color[2], 0.9)
                font_weight = cairo.FONT_WEIGHT_BOLD if number_bold else cairo.FONT_WEIGHT_NORMAL
                cr.select_font_face(number_font, cairo.FONT_SLANT_NORMAL, font_weight)
                cr.set_font_size(radius * number_size)
                
                extents = cr.text_extents(text)
                cr.move_to(text_x - extents.width / 2, text_y + extents.height / 2)
                cr.show_text(text)
        
        # Draw minute ticks (if enabled)
        if show_minute_ticks:
            cr.set_source_rgba(minute_ticks_color[0], minute_ticks_color[1], minute_ticks_color[2], 0.8)
            for i in range(60):
                if i % 5 != 0:  # Skip hour positions
                    angle = math.radians(i * 6 - 90)
                    tick_size = radius * minute_tick_size
                    
                    if minute_tick_style == "round":
                        # Draw round tick (circle)
                        tick_radius = radius * minute_tick_position - tick_size
                        tick_x = cx + tick_radius * math.cos(angle)
                        tick_y = cy + tick_radius * math.sin(angle)
                        cr.arc(tick_x, tick_y, tick_size, 0, 2 * math.pi)
                        cr.fill()
                    elif minute_tick_style == "rectangular":
                        # Draw rectangular tick (rotated with aspect ratio)
                        tick_center_radius = radius * minute_tick_position - tick_size
                        tick_x = cx + tick_center_radius * math.cos(angle)
                        tick_y = cy + tick_center_radius * math.sin(angle)
                        
                        # Calculate width and height based on aspect ratio
                        height = tick_size * 2
                        width = height * minute_tick_aspect_ratio
                        
                        cr.save()
                        cr.translate(tick_x, tick_y)
                        cr.rotate(angle + math.pi / 2)  # Rotate so one side faces center
                        cr.rectangle(-width / 2, -height / 2, width, height)
                        cr.fill()
                        cr.restore()
                    else:
                        # Draw square tick (rotated)
                        tick_center_radius = radius * minute_tick_position - tick_size
                        tick_x = cx + tick_center_radius * math.cos(angle)
                        tick_y = cy + tick_center_radius * math.sin(angle)
                        
                        cr.save()
                        cr.translate(tick_x, tick_y)
                        cr.rotate(angle + math.pi / 2)  # Rotate so one side faces center
                        cr.rectangle(-tick_size, -tick_size, tick_size * 2, tick_size * 2)
                        cr.fill()
                        cr.restore()
    
    def draw_hour_hand(self, cr, cx, cy, radius, hours, minutes):
        """Draw hour hand - either as image or geometric shape"""
        # Check if hand image is configured
        hand_image_path = self.resolve_hand_image_path('hour')
        if hand_image_path:
            self._draw_hand_image(cr, cx, cy, radius, hand_image_path, hours, minutes, 'hour')
        else:
            # Draw geometric hand
            hands_color = self.theme.get('hands_color')
            hour_hand_length = self.theme.get('hour_hand_length')
            hour_hand_tail = self.theme.get('hour_hand_tail')
            hour_hand_width = self.theme.get('hour_hand_width')
            
            angle = math.radians((hours + minutes / 60) * 30 - 90)
            length = radius * hour_hand_length
            tail_length = radius * hour_hand_tail
            
            # Tip of the hand
            x_tip = cx + length * math.cos(angle)
            y_tip = cy + length * math.sin(angle)
            
            # Tail of the hand (opposite direction)
            x_tail = cx - tail_length * math.cos(angle)
            y_tail = cy - tail_length * math.sin(angle)
            
            cr.set_source_rgba(hands_color[0], hands_color[1], hands_color[2], 0.9)
            cr.set_line_width(radius * hour_hand_width)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(x_tail, y_tail)
            cr.line_to(x_tip, y_tip)
            cr.stroke()
    
    def draw_minute_hand(self, cr, cx, cy, radius, minutes, seconds=0):
        """Draw minute hand - either as image or geometric shape"""
        # Check if hand image is configured
        hand_image_path = self.resolve_hand_image_path('minute')
        if hand_image_path:
            self._draw_hand_image(cr, cx, cy, radius, hand_image_path, 0, minutes, 'minute', seconds)
        else:
            # Draw geometric hand
            hands_color = self.theme.get('hands_color')
            minute_hand_length = self.theme.get('minute_hand_length')
            minute_hand_tail = self.theme.get('minute_hand_tail')
            minute_hand_width = self.theme.get('minute_hand_width')
            minute_hand_snap = self.settings.get('minute_hand_snap')
        
            # Optionally snap to minute marks
            if minute_hand_snap:
                angle = math.radians(minutes * 6 - 90)
            else:
                angle = math.radians((minutes + seconds / 60) * 6 - 90)
            
            length = radius * minute_hand_length
            tail_length = radius * minute_hand_tail
            
            # Tip of the hand
            x_tip = cx + length * math.cos(angle)
            y_tip = cy + length * math.sin(angle)
            
            # Tail of the hand (opposite direction)
            x_tail = cx - tail_length * math.cos(angle)
            y_tail = cy - tail_length * math.sin(angle)
            
            cr.set_source_rgba(hands_color[0], hands_color[1], hands_color[2], 0.9)
            cr.set_line_width(radius * minute_hand_width)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(x_tail, y_tail)
            cr.line_to(x_tip, y_tip)
            cr.stroke()
    
    def draw_second_hand(self, cr, cx, cy, radius, seconds):
        """Draw second hand - either as image or geometric shape"""
        # Check if hand image is configured
        hand_image_path = self.resolve_hand_image_path('second')
        if hand_image_path:
            self._draw_hand_image(cr, cx, cy, radius, hand_image_path, 0, 0, 'second', seconds)
        else:
            # Draw geometric hand
            second_hand_color = self.theme.get('second_hand_color')
            second_hand_length = self.theme.get('second_hand_length')
            second_hand_tail = self.theme.get('second_hand_tail')
            second_hand_width = self.theme.get('second_hand_width')
        
            angle = math.radians(seconds * 6 - 90)
            length = radius * second_hand_length
            tail_length = radius * second_hand_tail
            
            # Tip of the hand
            x_tip = cx + length * math.cos(angle)
            y_tip = cy + length * math.sin(angle)
            
            # Tail of the hand (opposite direction)
            x_tail = cx - tail_length * math.cos(angle)
            y_tail = cy - tail_length * math.sin(angle)
            
            cr.set_source_rgba(second_hand_color[0], second_hand_color[1], second_hand_color[2], 0.9)
            cr.set_line_width(radius * second_hand_width)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.move_to(x_tail, y_tail)
            cr.line_to(x_tip, y_tip)
            cr.stroke()
    
    def clear_hand_image_cache(self):
        """Clear the hand image cache when colors or hand images change"""
        self._hand_image_cache.clear()
    
    def _find_red_pixel(self, pixbuf):
        """
        Find the red pixel (rotation center) in the image.
        Returns (x, y) coordinates or None if not found.
        Red pixel is defined as RGB(255, 0, 0) with full opacity.
        """
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        rowstride = pixbuf.get_rowstride()
        pixels = pixbuf.get_pixels()
        n_channels = pixbuf.get_n_channels()
        has_alpha = pixbuf.get_has_alpha()
        
        for y in range(height):
            for x in range(width):
                pos = y * rowstride + x * n_channels
                r = pixels[pos]
                g = pixels[pos + 1]
                b = pixels[pos + 2]
                
                # Check if this is a red pixel (255, 0, 0)
                if r == 255 and g == 0 and b == 0:
                    # If has alpha, check it's fully opaque
                    if has_alpha:
                        a = pixels[pos + 3]
                        if a == 255:
                            return (x, y)
                    else:
                        return (x, y)
        
        return None
    
    def _draw_hand_image(self, cr, cx, cy, radius, image_path, hours, minutes, hand_type, seconds=0):
        """
        Draw a hand using an image file.
        The image should be in 12 o'clock position (pointing up).
        A single red pixel (255, 0, 0) marks the rotation center.
        """
        try:
            from gi.repository import GdkPixbuf
            
            # Get hand color from theme
            if hand_type == 'second':
                hand_color = self.theme.get('second_hand_color')
            else:  # hour or minute
                hand_color = self.theme.get('hands_color')
            
            # Create cache key based on image path and color (convert color to tuple for hashing)
            cache_key = (image_path, tuple(hand_color))
            
            # Check if we have a cached colored surface
            if cache_key in self._hand_image_cache:
                colored_surface, pivot = self._hand_image_cache[cache_key]
            else:
                # Load the image from disk
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(image_path)
                
                # Find the red pixel (rotation center)
                pivot = self._find_red_pixel(pixbuf)
                if not pivot:
                    print(f"Warning: No red pixel found in {image_path}, using image center")
                    pivot = (pixbuf.get_width() / 2, pixbuf.get_height() / 2)
                
                # Create a surface with the hand image colored
                img_width = pixbuf.get_width()
                img_height = pixbuf.get_height()
                colored_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_width, img_height)
                ctx = cairo.Context(colored_surface)
                
                # Draw the original image to get the alpha mask
                Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
                ctx.paint()
                
                # Now paint over it with the desired color, using the alpha from the image
                # OPERATOR_IN keeps the alpha from destination (the image) and color from source
                ctx.set_source_rgba(hand_color[0], hand_color[1], hand_color[2], 1.0)
                ctx.set_operator(cairo.OPERATOR_IN)
                ctx.paint()
                
                # Cache the colored surface and pivot
                self._hand_image_cache[cache_key] = (colored_surface, pivot)
            
            pivot_x, pivot_y = pivot
            
            # Calculate angle based on hand type
            if hand_type == 'hour':
                angle = math.radians((hours + minutes / 60) * 30 - 90)
            elif hand_type == 'minute':
                minute_hand_snap = self.settings.get('minute_hand_snap')
                if minute_hand_snap:
                    angle = math.radians(minutes * 6 - 90)
                else:
                    angle = math.radians((minutes + seconds / 60) * 6 - 90)
            else:  # second
                angle = math.radians(seconds * 6 - 90)
            
            # Get hand length and width from theme
            # Use image_width for hand images (scale factor)
            if hand_type == 'hour':
                hand_length = self.theme.get('hour_hand_length')
                hand_width = self.theme.get('hour_hand_image_width')
            elif hand_type == 'minute':
                hand_length = self.theme.get('minute_hand_length')
                hand_width = self.theme.get('minute_hand_image_width')
            else:  # second
                hand_length = self.theme.get('second_hand_length')
                hand_width = self.theme.get('second_hand_image_width')
            
            # Calculate scale factors
            # Length: distance from red pixel to top of image should match desired hand length
            img_height = colored_surface.get_height()
            img_width = colored_surface.get_width()
            
            # Distance from red pixel to top edge (0)
            distance_to_top = pivot_y
            target_length = radius * hand_length
            scale_y = target_length / distance_to_top if distance_to_top > 0 else 1.0
            
            # Width: hand_width is a scale factor (1.0 = original width)
            # Calculate the base width scale to maintain aspect ratio, then apply width scale factor
            # Base scale: how much to scale width to maintain original proportions at the new length
            base_width_scale = scale_y
            # Apply width multiplier (1.0 = original width at this length)
            scale_x = base_width_scale * hand_width
            
            # Save context
            cr.save()
            
            # Move to center and rotate
            cr.translate(cx, cy)
            cr.rotate(angle + math.pi / 2)  # +90 degrees to align with 12 o'clock
            
            # Scale and position the image using the red pixel as pivot
            cr.scale(scale_x, scale_y)
            cr.translate(-pivot_x, -pivot_y)
            
            # Draw the cached colored surface
            cr.set_source_surface(colored_surface, 0, 0)
            cr.paint()
            
            # Restore context
            cr.restore()
            
        except Exception as e:
            print(f"Error drawing hand image: {e}")
            # Fall back to drawing geometric hand if image fails
            pass


def main():
    clock = AnalogClock()
    clock.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
