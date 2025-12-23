"""
Dialog classes for dsclock application
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

import os
import shutil


class CustomizeDialog(Gtk.Dialog):
    """Unified customization dialog with GNOME-style sidebar"""
    
    def __init__(self, parent):
        # Set title with theme name
        title = f"Clock Settings - {parent.theme.name}"
        super().__init__(title=title, parent=parent, flags=0)
        
        # Add custom buttons
        self.save_button = self.add_button("Save", Gtk.ResponseType.APPLY)
        self.close_button = self.add_button("Close", Gtk.ResponseType.CLOSE)
        
        # Initially disable Save button (no changes yet)
        self.save_button.set_sensitive(False)
        
        # Connect response handler
        self.connect('response', self.on_response)
        
        # Connect delete-event (X button) to handle close properly
        self.connect('delete-event', self.on_delete_event)
        
        # Connect Escape key to discard
        self.connect('key-press-event', self.on_key_press)
        
        self.set_border_width(0)
        
        self.parent_clock = parent
        
        # Add CSS for subtle FlowBox selection color
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            flowboxchild:selected {
                background-color: rgba(100, 150, 200, 0.15);
                border: 2px solid rgba(100, 150, 200, 0.3);
            }
        """)
        screen = self.get_screen()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        # Store single in-memory preview for current theme
        self.in_memory_preview_pixbuf = None
        
        # LEFT SIDEBAR
        sidebar = Gtk.ListBox()
        sidebar.set_size_request(180, -1)
        sidebar.get_style_context().add_class('sidebar')
        
        # Add sidebar items
        self.sidebar_items = []
        items = [
            ("Themes", "themes"),
            ("Clock Face", "clock-face"),
            ("Ticks", "ticks"),
            ("Hands", "hands"),
            ("Date Box", "date-box"),
            ("Options", "options")
        ]
        
        for label_text, page_id in items:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=label_text)
            label.set_halign(Gtk.Align.START)
            label.set_margin_start(12)
            label.set_margin_end(12)
            label.set_margin_top(8)
            label.set_margin_bottom(8)
            row.add(label)
            row.page_id = page_id
            sidebar.add(row)
            self.sidebar_items.append(row)
        
        sidebar.connect('row-selected', self.on_sidebar_changed)
        
        # Create main horizontal box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        
        # RIGHT CONTENT AREA with stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(150)
        
        # Add pages to stack
        themes_page = self._create_themes_page()
        clock_face_page = self._create_clock_face_page()
        ticks_page = self._create_ticks_page()
        hands_page = self._create_hands_page()
        date_box_page = self._create_date_box_page()
        options_page = self._create_options_page()
        
        self.stack.add_named(themes_page, "themes")
        self.stack.add_named(clock_face_page, "clock-face")
        self.stack.add_named(ticks_page, "ticks")
        self.stack.add_named(hands_page, "hands")
        self.stack.add_named(date_box_page, "date-box")
        self.stack.add_named(options_page, "options")
        
        # Pack sidebar and content (no scrolled window)
        main_box.pack_start(sidebar, False, False, 0)
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        main_box.pack_start(separator, False, False, 0)
        main_box.pack_start(self.stack, True, True, 0)
        
        # Add to dialog
        box = self.get_content_area()
        box.pack_start(main_box, True, True, 0)
        
        # Select first item
        sidebar.select_row(self.sidebar_items[0])
        
        # Show all widgets to get proper size requests
        self.show_all()
        
        # Immediately update control visibility after show_all
        # show_all() makes everything visible, so we need to hide the appropriate controls
        self._update_color_controls_visibility()
        self._update_texture_controls_visibility()
        self._update_number_controls_visibility()
        self._update_hour_tick_controls_visibility()
        self._update_minute_tick_controls_visibility()
        self._update_hand_controls_visibility()
        # Force the widgets to actually hide by processing pending events
        while Gtk.events_pending():
            Gtk.main_iteration()
        
        # Calculate required height based on tallest page
        pages = [themes_page, clock_face_page, ticks_page, hands_page, date_box_page, options_page]
        max_height = 0
        for page in pages:
            nat_height = page.get_preferred_height()[1]  # Get natural height
            if nat_height > max_height:
                max_height = nat_height
        
        # Add extra space for dialog chrome (title bar, buttons, padding)
        dialog_chrome = 100
        total_height = max_height + dialog_chrome
        
        # Set dialog size
        dialog_width = 950
        self.set_default_size(dialog_width, total_height)
        
        # Position dialog to the left and up to keep clock visible
        parent_x, parent_y = parent.get_position()
        self.move(max(0, parent_x - dialog_width - 20), max(0, parent_y - 50))
    
    def on_sidebar_changed(self, listbox, row):
        if row:
            # If switching to Themes tab and there are unsaved changes, regenerate preview
            if row.page_id == 'themes' and self.parent_clock.theme.is_dirty:
                self._regenerate_current_theme_preview()
            self.stack.set_visible_child_name(row.page_id)
    
    def on_key_press(self, widget, event):
        """Handle Escape key to close dialog"""
        if event.keyval == Gdk.KEY_Escape:
            self.response(Gtk.ResponseType.CLOSE)
            return True
        return False
    
    def on_delete_event(self, widget, event):
        """Handle window close (X button) - check for unsaved changes"""
        self._handle_close()
        return True  # Prevent default close behavior
    
    def on_response(self, dialog, response_id):
        """Handle dialog response"""
        if response_id == Gtk.ResponseType.APPLY:
            # Save button - save without closing
            self._save_theme()
        elif response_id == Gtk.ResponseType.CLOSE:
            # Close button - check for unsaved changes
            self._handle_close()
    
    def _save_theme(self):
        """Save theme without closing dialog"""
        # Update preview before saving if theme is dirty
        if self.parent_clock.theme.is_dirty:
            self._regenerate_current_theme_preview()
            self._save_in_memory_preview_to_disk()
        
        # Save theme and settings
        if self.parent_clock.theme.name == 'default':
            # Can't save to default, show save as dialog
            self.on_save_theme_as_clicked()
        else:
            self.parent_clock.theme.save()
            self.parent_clock.settings.save()
            
            # Disable save button since changes are now saved
            self.save_button.set_sensitive(False)
    
    def _handle_close(self):
        """Handle close button - check for unsaved changes"""
        if self.parent_clock.theme.is_dirty:
            # Show dialog asking what to do with unsaved changes
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text="Save changes before closing?"
            )
            dialog.format_secondary_text("You have unsaved changes to the current theme.")
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Discard", Gtk.ResponseType.NO)
            dialog.add_button("Save", Gtk.ResponseType.YES)
            
            response = dialog.run()
            dialog.destroy()
            
            if response == Gtk.ResponseType.CANCEL:
                # Don't close
                return
            elif response == Gtk.ResponseType.NO:
                # Discard changes by reloading theme from disk
                self.parent_clock.theme.load()
                self.parent_clock.queue_draw()
                self.destroy()
            elif response == Gtk.ResponseType.YES:
                # Save and close
                self._save_theme()
                self.destroy()
        else:
            # No unsaved changes, just close
            self.destroy()
    
    def on_duplicate_theme_clicked(self):
        """Handle duplicate theme button"""
        # Prompt for new theme name
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Duplicate Theme"
        )
        dialog.format_secondary_text("Enter a name for the new theme:")
        
        # Add entry field
        entry = Gtk.Entry()
        entry.set_text(f"{self.parent_clock.theme.name}_copy")
        entry.set_activates_default(True)
        dialog.get_content_area().pack_start(entry, False, False, 0)
        dialog.get_content_area().show_all()
        
        # Set OK button as default
        dialog.set_default_response(Gtk.ResponseType.OK)
        
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK and new_name:
            # Create duplicate theme
            from theme import Theme
            new_theme = self.parent_clock.theme.duplicate(new_name)
            new_theme.save()
            
            # Switch to new theme
            self.parent_clock.theme = new_theme
            self.parent_clock.settings.set('active_theme_name', new_name)
            self.parent_clock.settings.save()
            
            # Update dialog title
            self.set_title(f"Clock Settings - {new_name}")
            
            # Refresh themes list
            self._populate_themes()
            
            # Disable save button since we now have a clean theme
            self.save_button.set_sensitive(False)
    
    def _update_controls_from_clock(self):
        """Update all dialog controls to reflect current theme/settings state"""
        theme = self.parent_clock.theme
        settings = self.parent_clock.settings
        
        # Clock Face controls
        if hasattr(self, 'enable_color_check'):
            self.enable_color_check.set_active(theme.get('enable_face_color'))
        if hasattr(self, 'enable_texture_check'):
            self.enable_texture_check.set_active(theme.get('enable_face_texture'))
        if hasattr(self, 'background_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('background_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.background_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.background_color_button, 'hex_label'):
                self.background_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'rim_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('rim_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.rim_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.rim_color_button, 'hex_label'):
                self.rim_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'face_texture_label'):
            self.face_texture_label.set_text(self._format_texture_label(theme.get('face_texture_name')))
        
        # Ticks controls
        if hasattr(self, 'hour_tick_style_combo'):
            self.hour_tick_style_combo.set_active_id(theme.get('hour_tick_style'))
        if hasattr(self, 'minute_tick_style_combo'):
            self.minute_tick_style_combo.set_active_id(theme.get('minute_tick_style'))
        if hasattr(self, 'ticks_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('ticks_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.ticks_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.ticks_color_button, 'hex_label'):
                self.ticks_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'minute_ticks_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('minute_ticks_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.minute_ticks_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.minute_ticks_color_button, 'hex_label'):
                self.minute_ticks_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'numbers_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('numbers_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.numbers_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.numbers_color_button, 'hex_label'):
                self.numbers_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'number_font_button'):
            self.number_font_button.set_font(theme.get('number_font'))
        if hasattr(self, 'number_bold_switch'):
            self.number_bold_switch.set_active(theme.get('number_bold'))
        if hasattr(self, 'roman_numerals_switch'):
            self.roman_numerals_switch.set_active(theme.get('use_roman_numerals'))
        if hasattr(self, 'cardinal_numbers_switch'):
            self.cardinal_numbers_switch.set_active(theme.get('show_cardinal_numbers_only'))
        if hasattr(self, 'show_numbers_switch'):
            self.show_numbers_switch.set_active(theme.get('show_numbers'))
        if hasattr(self, 'show_hour_ticks_switch'):
            self.show_hour_ticks_switch.set_active(theme.get('show_hour_ticks'))
        if hasattr(self, 'show_minute_ticks_switch'):
            self.show_minute_ticks_switch.set_active(theme.get('show_minute_ticks'))
        
        # Hands controls
        if hasattr(self, 'hands_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('hands_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.hands_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.hands_color_button, 'hex_label'):
                self.hands_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'second_hand_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('second_hand_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.second_hand_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.second_hand_color_button, 'hex_label'):
                self.second_hand_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'minute_hand_snap_switch'):
            self.minute_hand_snap_switch.set_active(settings.get('minute_hand_snap'))
        
        # Update hand theme label
        if hasattr(self, 'hand_theme_label'):
            self.hand_theme_label.set_text(self._format_hand_theme_label())
        
        # Update hand controls visibility based on new theme's hand image settings
        if hasattr(self, 'hour_width_scale'):
            self._update_hand_controls_visibility()
        
        # Date box controls
        if hasattr(self, 'date_text_color_button'):
            rgba = Gdk.RGBA()
            color = theme.get('date_text_color')
            rgba.red, rgba.green, rgba.blue = color
            rgba.alpha = 1.0
            self.date_text_color_button.set_rgba(rgba)
            # Update hex label if it exists
            if hasattr(self.date_text_color_button, 'hex_label'):
                self.date_text_color_button.hex_label.set_text(self._color_to_hex(color))
        if hasattr(self, 'date_font_button'):
            self.date_font_button.set_font(theme.get('date_font'))
        if hasattr(self, 'date_bold_switch'):
            self.date_bold_switch.set_active(theme.get('date_bold'))
    
    def _mark_dirty(self):
        """Update save button based on theme dirty state"""
        is_dirty = self.parent_clock.theme.is_dirty
        self.save_button.set_sensitive(is_dirty)
    
    def _on_theme_property_changed(self, property_name, value):
        """Generic handler for theme property changes"""
        self.parent_clock.theme.set(property_name, value)
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()
    
    def _on_settings_property_changed(self, property_name, value):
        """Generic handler for settings property changes"""
        self.parent_clock.settings.set(property_name, value)
        self.parent_clock.settings.save()
        self.parent_clock.queue_draw()
    
    
    def _create_themes_page(self):
        """Create Themes management page"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(24)
        box.set_margin_end(24)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        
        # Header with Save Theme As button
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        
        label = Gtk.Label(label="<b>Available Themes</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        header_box.pack_start(label, False, False, 0)
        
        save_as_themes_button = Gtk.Button(label="Save theme as...")
        save_as_themes_button.connect('clicked', lambda btn: self.on_save_theme_as_clicked())
        header_box.pack_end(save_as_themes_button, False, False, 0)
        
        self.delete_theme_button = Gtk.Button(label="Delete selected theme")
        self.delete_theme_button.connect('clicked', self.on_delete_theme_clicked)
        self.delete_theme_button.set_sensitive(False)
        header_box.pack_end(self.delete_theme_button, False, False, 0)
        
        box.pack_start(header_box, False, False, 0)
        
        # Scrolled window for theme grid
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(400)
        
        self.themes_flow = Gtk.FlowBox()
        self.themes_flow.set_max_children_per_line(4)
        self.themes_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.themes_flow.set_row_spacing(12)
        self.themes_flow.set_column_spacing(12)
        self.themes_flow.set_homogeneous(True)
        self.themes_flow.connect('child-activated', self.on_theme_activated)
        self.themes_flow.connect('selected-children-changed', self.on_theme_selection_changed)
        
        scrolled.add(self.themes_flow)
        box.pack_start(scrolled, True, True, 0)
        
        # Populate themes
        self._populate_themes()
        
        return box
    
    def _create_clock_face_page(self):
        """Create Clock Face customization page"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_margin_start(24)
        grid.set_margin_end(24)
        grid.set_margin_top(24)
        grid.set_margin_bottom(24)
        
        row = 0
        
        # Overall Size Section
        label = Gtk.Label(label="<b>Overall Size</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        self._add_slider(grid, row, "Clock Size (px):", self.parent_clock.settings.get('clock_size'), 200, 800, 
                        self.on_size_changed, discrete=True, step=10)
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Color Section
        label = Gtk.Label(label="<b>Color</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        # Enable Color checkbox
        self.enable_color_check = Gtk.CheckButton(label="Enable")
        self.enable_color_check.set_active(self.parent_clock.theme.get('enable_face_color'))
        self.enable_color_check.set_halign(Gtk.Align.END)
        self.enable_color_check.connect('toggled', self.on_enable_color_toggled)
        grid.attach(self.enable_color_check, 1, row, 1, 1)
        row += 1

        self.face_color_controls = []
        
        # Background color
        bg_label = Gtk.Label(label="Background:")
        bg_label.set_halign(Gtk.Align.START)
        grid.attach(bg_label, 0, row, 1, 1)
        
        # Create horizontal box for button, hex label, and copy button
        bg_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.background_color_button = Gtk.ColorButton()
        self.background_color_button.set_use_alpha(False)
        bg_color = self.parent_clock.theme.get('background_color')
        self.background_color_button.set_rgba(self._tuple_to_rgba(bg_color))
        self.background_color_button.set_halign(Gtk.Align.START)
        bg_hbox.pack_start(self.background_color_button, False, False, 0)
        
        # Add hex value label
        bg_hex_label = Gtk.Label()
        bg_hex_label.set_text(self._color_to_hex(bg_color))
        bg_hex_label.set_selectable(True)
        bg_hex_label.set_halign(Gtk.Align.START)
        bg_hex_label.get_style_context().add_class("monospace")
        bg_hbox.pack_start(bg_hex_label, False, False, 0)
        self.background_color_button.hex_label = bg_hex_label
        
        # Add copy button
        bg_copy_button = Gtk.Button()
        bg_copy_button.set_label("📋")
        bg_copy_button.set_tooltip_text("Copy to clipboard")
        bg_copy_button.set_relief(Gtk.ReliefStyle.NONE)
        bg_copy_button.connect("clicked", lambda btn: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(bg_hex_label.get_text(), -1))
        bg_hbox.pack_start(bg_copy_button, False, False, 0)
        
        def bg_color_callback(button):
            rgba = button.get_rgba()
            color = (rgba.red, rgba.green, rgba.blue)
            button.hex_label.set_text(self._color_to_hex(color))
            self.on_background_color_changed(button)
        
        self.background_color_button.connect("color-set", bg_color_callback)
        grid.attach(bg_hbox, 1, row, 1, 1)
        self.face_color_controls.extend([bg_label, bg_hbox])
        row += 1

        # Color Opacity slider
        color_opacity_label = Gtk.Label(label="Opacity:")
        color_opacity_label.set_halign(Gtk.Align.START)
        grid.attach(color_opacity_label, 0, row, 1, 1)
        color_opacity_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.01)
        color_opacity_scale.set_value(self.parent_clock.theme.get('face_color_opacity'))
        color_opacity_scale.set_hexpand(True)
        color_opacity_scale.set_size_request(400, -1)
        color_opacity_scale.set_value_pos(Gtk.PositionType.RIGHT)
        color_opacity_scale.set_digits(2)
        color_opacity_scale.connect("value-changed", self.on_face_color_opacity_changed)
        grid.attach(color_opacity_scale, 1, row, 1, 1)
        self.face_color_controls.extend([color_opacity_label, color_opacity_scale])
        row += 1

        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Texture Section
        label = Gtk.Label(label="<b>Texture</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        # Enable Texture checkbox
        self.enable_texture_check = Gtk.CheckButton(label="Enable")
        self.enable_texture_check.set_active(self.parent_clock.theme.get('enable_face_texture'))
        self.enable_texture_check.set_halign(Gtk.Align.END)
        self.enable_texture_check.connect('toggled', self.on_enable_texture_toggled)
        grid.attach(self.enable_texture_check, 1, row, 1, 1)
        row += 1

        self.face_texture_controls = []
        
        # Texture selection
        texture_label = Gtk.Label(label="Texture:")
        texture_label.set_halign(Gtk.Align.START)
        grid.attach(texture_label, 0, row, 1, 1)
        self.face_texture_label = Gtk.Label(label=self._format_texture_label(self.parent_clock.theme.get('face_texture_name')))
        self.face_texture_label.set_halign(Gtk.Align.START)
        grid.attach(self.face_texture_label, 1, row, 1, 1)
        self.face_texture_controls.extend([texture_label, self.face_texture_label])
        row += 1

        self.face_choose_texture_button = Gtk.Button(label="Choose Texture…")
        self.face_choose_texture_button.set_halign(Gtk.Align.START)
        self.face_choose_texture_button.connect('clicked', self.on_choose_face_texture_clicked)
        grid.attach(self.face_choose_texture_button, 1, row, 1, 1)
        self.face_texture_controls.append(self.face_choose_texture_button)
        row += 1
        
        # Texture Opacity slider
        texture_opacity_label = Gtk.Label(label="Opacity:")
        texture_opacity_label.set_halign(Gtk.Align.START)
        grid.attach(texture_opacity_label, 0, row, 1, 1)
        texture_opacity_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.01)
        texture_opacity_scale.set_value(self.parent_clock.theme.get('face_texture_opacity'))
        texture_opacity_scale.set_hexpand(True)
        texture_opacity_scale.set_size_request(400, -1)
        texture_opacity_scale.set_value_pos(Gtk.PositionType.RIGHT)
        texture_opacity_scale.set_digits(2)
        texture_opacity_scale.connect("value-changed", self.on_face_texture_opacity_changed)
        grid.attach(texture_opacity_scale, 1, row, 1, 1)
        self.face_texture_controls.extend([texture_opacity_label, texture_opacity_scale])
        row += 1

        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Rim Section
        label = Gtk.Label(label="<b>Rim</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        self._add_slider(grid, row, "Thickness:", self.parent_clock.theme.get('rim_width'), 0.0, 0.05, self.on_rim_width_changed)
        row += 1
        
        self._add_slider(grid, row, "Opacity:", self.parent_clock.theme.get('rim_opacity'), 0.0, 1.0, self.on_rim_opacity_changed)
        row += 1
        
        rim_color_widgets = self._add_color_button(grid, row, "Color:", self.parent_clock.theme.get('rim_color'), self.on_rim_color_changed)
        self.rim_color_button = rim_color_widgets[1]
        row += 1

        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Numbers Section
        label = Gtk.Label(label="<b>Numbers</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Show numbers checkbox
        label = Gtk.Label(label="Show numbers:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        self.show_numbers_switch = Gtk.Switch()
        self.show_numbers_switch.set_active(self.parent_clock.theme.get('show_numbers'))
        self.show_numbers_switch.set_halign(Gtk.Align.START)
        self.show_numbers_switch.connect("notify::active", self.on_show_numbers_toggled)
        grid.attach(self.show_numbers_switch, 1, row, 1, 1)
        row += 1
        
        # Track number controls for visibility management
        self.number_controls = []
        
        # Determine initial visibility
        numbers_visible = self.parent_clock.theme.get('show_numbers')
        
        # Position slider
        position_widgets = self._add_slider(grid, row, "Position:", self.parent_clock.theme.get('number_position'), 0.65, 0.95,
                        self.on_number_position_changed)
        for widget in position_widgets:
            widget.set_visible(numbers_visible)
        self.number_controls.extend(position_widgets)
        row += 1
        
        # Size slider
        size_widgets = self._add_slider(grid, row, "Size:", self.parent_clock.theme.get('number_size'), 0.05, 0.25,
                        self.on_number_size_changed)
        for widget in size_widgets:
            widget.set_visible(numbers_visible)
        self.number_controls.extend(size_widgets)
        row += 1
        
        # Color button
        color_label = Gtk.Label(label="Color:")
        color_label.set_halign(Gtk.Align.START)
        color_label.set_visible(numbers_visible)
        self.number_controls.append(color_label)
        grid.attach(color_label, 0, row, 1, 1)
        
        # Create horizontal box for button, hex label, and copy button
        numbers_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        numbers_hbox.set_visible(numbers_visible)
        
        numbers_color_button = Gtk.ColorButton()
        numbers_color_button.set_use_alpha(False)
        numbers_color = self.parent_clock.theme.get('numbers_color')
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue = numbers_color
        rgba.alpha = 1.0
        numbers_color_button.set_rgba(rgba)
        numbers_color_button.set_halign(Gtk.Align.START)
        numbers_color_button.set_hexpand(False)
        numbers_hbox.pack_start(numbers_color_button, False, False, 0)
        
        # Add hex value label
        numbers_hex_label = Gtk.Label()
        numbers_hex_label.set_text(self._color_to_hex(numbers_color))
        numbers_hex_label.set_selectable(True)
        numbers_hex_label.set_halign(Gtk.Align.START)
        numbers_hex_label.get_style_context().add_class("monospace")
        numbers_hbox.pack_start(numbers_hex_label, False, False, 0)
        numbers_color_button.hex_label = numbers_hex_label
        
        # Add copy button
        numbers_copy_button = Gtk.Button()
        numbers_copy_button.set_label("📋")
        numbers_copy_button.set_tooltip_text("Copy to clipboard")
        numbers_copy_button.set_relief(Gtk.ReliefStyle.NONE)
        numbers_copy_button.connect("clicked", lambda btn: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(numbers_hex_label.get_text(), -1))
        numbers_hbox.pack_start(numbers_copy_button, False, False, 0)
        
        def numbers_color_callback(button):
            rgba = button.get_rgba()
            color = (rgba.red, rgba.green, rgba.blue)
            button.hex_label.set_text(self._color_to_hex(color))
            self.on_numbers_color_changed(button)
        
        numbers_color_button.connect("color-set", numbers_color_callback)
        self.number_controls.append(numbers_hbox)
        self.numbers_color_button = numbers_color_button
        grid.attach(numbers_hbox, 1, row, 1, 1)
        row += 1
        
        # Font selection
        font_label = Gtk.Label(label="Font:")
        font_label.set_halign(Gtk.Align.START)
        font_label.set_visible(numbers_visible)
        self.number_controls.append(font_label)
        grid.attach(font_label, 0, row, 1, 1)
        
        font_button = Gtk.FontButton()
        font_button.set_font(self.parent_clock.theme.get('number_font'))
        font_button.set_use_font(False)
        font_button.set_show_size(False)
        font_button.set_halign(Gtk.Align.START)
        font_button.set_visible(numbers_visible)
        font_button.connect("font-set", self.on_number_font_changed)
        self.number_controls.append(font_button)
        self.number_font_button = font_button
        grid.attach(font_button, 1, row, 1, 1)
        row += 1
        
        # Bold switch
        bold_label = Gtk.Label(label="Bold:")
        bold_label.set_halign(Gtk.Align.START)
        bold_label.set_visible(numbers_visible)
        self.number_controls.append(bold_label)
        grid.attach(bold_label, 0, row, 1, 1)
        
        bold_switch = Gtk.Switch()
        bold_switch.set_active(self.parent_clock.theme.get('number_bold'))
        bold_switch.set_halign(Gtk.Align.START)
        bold_switch.set_visible(numbers_visible)
        bold_switch.connect("notify::active", self.on_number_bold_toggled)
        self.number_controls.append(bold_switch)
        self.number_bold_switch = bold_switch
        grid.attach(bold_switch, 1, row, 1, 1)
        row += 1
        
        # Roman numerals switch
        roman_label = Gtk.Label(label="Roman numerals:")
        roman_label.set_halign(Gtk.Align.START)
        roman_label.set_visible(numbers_visible)
        self.number_controls.append(roman_label)
        grid.attach(roman_label, 0, row, 1, 1)
        
        roman_switch = Gtk.Switch()
        roman_switch.set_active(self.parent_clock.theme.get('use_roman_numerals'))
        roman_switch.set_halign(Gtk.Align.START)
        roman_switch.set_visible(numbers_visible)
        roman_switch.connect("notify::active", self.on_roman_numerals_toggled)
        self.number_controls.append(roman_switch)
        self.roman_numerals_switch = roman_switch
        grid.attach(roman_switch, 1, row, 1, 1)
        row += 1
        
        # Cardinal numbers only switch
        cardinal_label = Gtk.Label(label="Cardinal numbers only:")
        cardinal_label.set_halign(Gtk.Align.START)
        cardinal_label.set_visible(numbers_visible)
        self.number_controls.append(cardinal_label)
        grid.attach(cardinal_label, 0, row, 1, 1)
        
        cardinal_switch = Gtk.Switch()
        cardinal_switch.set_active(self.parent_clock.theme.get('show_cardinal_numbers_only'))
        cardinal_switch.set_halign(Gtk.Align.START)
        cardinal_switch.set_visible(numbers_visible)
        cardinal_switch.connect("notify::active", self.on_cardinal_numbers_toggled)
        self.number_controls.append(cardinal_switch)
        self.cardinal_numbers_switch = cardinal_switch
        grid.attach(cardinal_switch, 1, row, 1, 1)
        row += 1
        
        return grid

    
    def _create_ticks_page(self):
        """Create Ticks customization page"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_margin_start(24)
        grid.set_margin_end(24)
        grid.set_margin_top(24)
        grid.set_margin_bottom(24)
        
        row = 0
        
        # Tick Position (shared)
        label = Gtk.Label(label="<b>Tick Position</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        self._add_slider(grid, row, "Position:", self.parent_clock.theme.get('hour_tick_position'), 0.85, 0.99,
                        self.on_tick_position_changed)
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Hour Ticks Section
        label = Gtk.Label(label="<b>Hour Ticks</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Show hour ticks checkbox
        label = Gtk.Label(label="Show hour ticks:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        self.show_hour_ticks_switch = Gtk.Switch()
        self.show_hour_ticks_switch.set_active(self.parent_clock.theme.get('show_hour_ticks'))
        self.show_hour_ticks_switch.set_halign(Gtk.Align.START)
        self.show_hour_ticks_switch.connect("notify::active", self.on_show_hour_ticks_toggled)
        grid.attach(self.show_hour_ticks_switch, 1, row, 1, 1)
        row += 1
        
        # Track hour tick controls for visibility management
        self.hour_tick_controls = []
        
        # Determine initial visibility
        hour_ticks_visible = self.parent_clock.theme.get('show_hour_ticks')
        
        # Hour tick style dropdown
        label = Gtk.Label(label="Style:")
        label.set_visible(hour_ticks_visible)
        self.hour_tick_controls.append(label)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        self.style_combo = Gtk.ComboBoxText()
        self.style_combo.append("square", "Square")
        self.style_combo.append("round", "Round")
        self.style_combo.append("rectangular", "Rectangular")
        self.style_combo.set_active_id(self.parent_clock.theme.get('hour_tick_style'))
        self.style_combo.set_halign(Gtk.Align.START)
        self.style_combo.set_visible(hour_ticks_visible)
        self.style_combo.connect("changed", self.on_hour_tick_style_changed)
        self.hour_tick_controls.append(self.style_combo)
        grid.attach(self.style_combo, 1, row, 1, 1)
        row += 1
        
        # Size slider - track its widgets
        size_label = Gtk.Label(label="Size:")
        size_label.set_halign(Gtk.Align.START)
        size_label.set_visible(hour_ticks_visible)
        self.hour_tick_controls.append(size_label)
        grid.attach(size_label, 0, row, 1, 1)
        
        size_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.01, 0.05, 0.001)
        size_scale.set_value(self.parent_clock.theme.get('hour_tick_size'))
        size_scale.set_hexpand(True)
        size_scale.set_value_pos(Gtk.PositionType.RIGHT)
        size_scale.set_digits(3)
        size_scale.set_visible(hour_ticks_visible)
        size_scale.connect("value-changed", self.on_hour_tick_size_changed)
        self.hour_tick_controls.append(size_scale)
        grid.attach(size_scale, 1, row, 1, 1)
        row += 1
        
        # Shape slider (only visible for rectangular style)
        # Uses logarithmic scale: -2 to +2, where 0 = square (1.0)
        # Negative = taller, Positive = wider
        # Determine if shape should be visible (rectangular style AND hour ticks enabled)
        is_rectangular = self.parent_clock.theme.get('hour_tick_style') == "rectangular"
        shape_visible = hour_ticks_visible and is_rectangular
        
        self.shape_label = Gtk.Label(label="Shape:")
        self.shape_label.set_halign(Gtk.Align.START)
        self.shape_label.set_visible(shape_visible)
        grid.attach(self.shape_label, 0, row, 1, 1)
        
        # Convert aspect ratio to log scale for slider
        import math as m
        current_ratio = self.parent_clock.theme.get('hour_tick_aspect_ratio')
        slider_value = m.log2(current_ratio) if current_ratio > 0 else 0
        
        self.shape_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.5, 1.5, 0.1)
        self.shape_scale.set_value(slider_value)
        self.shape_scale.set_hexpand(True)
        self.shape_scale.set_size_request(400, -1)
        self.shape_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.shape_scale.set_digits(1)
        
        # Add marks for reference
        self.shape_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Square")
        self.shape_scale.add_mark(-1.5, Gtk.PositionType.BOTTOM, "Tall")
        self.shape_scale.add_mark(1.5, Gtk.PositionType.BOTTOM, "Wide")
        
        self.shape_scale.set_visible(shape_visible)
        self.shape_scale.connect("value-changed", self.on_hour_tick_shape_changed)
        grid.attach(self.shape_scale, 1, row, 1, 1)
        row += 1
        
        # Track shape widgets for visibility toggling
        self.hour_tick_shape_widgets = [self.shape_label, self.shape_scale]
        
        # Color button - track its widgets
        color_label = Gtk.Label(label="Color:")
        color_label.set_halign(Gtk.Align.START)
        color_label.set_visible(hour_ticks_visible)
        self.hour_tick_controls.append(color_label)
        grid.attach(color_label, 0, row, 1, 1)
        
        # Create horizontal box for button, hex label, and copy button
        ticks_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ticks_hbox.set_visible(hour_ticks_visible)
        
        ticks_color_button = Gtk.ColorButton()
        ticks_color_button.set_use_alpha(False)
        ticks_color = self.parent_clock.theme.get('ticks_color')
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue = ticks_color
        rgba.alpha = 1.0
        ticks_color_button.set_rgba(rgba)
        ticks_color_button.set_halign(Gtk.Align.START)
        ticks_color_button.set_hexpand(False)
        ticks_hbox.pack_start(ticks_color_button, False, False, 0)
        
        # Add hex value label
        ticks_hex_label = Gtk.Label()
        ticks_hex_label.set_text(self._color_to_hex(ticks_color))
        ticks_hex_label.set_selectable(True)
        ticks_hex_label.set_halign(Gtk.Align.START)
        ticks_hex_label.get_style_context().add_class("monospace")
        ticks_hbox.pack_start(ticks_hex_label, False, False, 0)
        ticks_color_button.hex_label = ticks_hex_label
        
        # Add copy button
        ticks_copy_button = Gtk.Button()
        ticks_copy_button.set_label("📋")
        ticks_copy_button.set_tooltip_text("Copy to clipboard")
        ticks_copy_button.set_relief(Gtk.ReliefStyle.NONE)
        ticks_copy_button.connect("clicked", lambda btn: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(ticks_hex_label.get_text(), -1))
        ticks_hbox.pack_start(ticks_copy_button, False, False, 0)
        
        def ticks_color_callback(button):
            rgba = button.get_rgba()
            color = (rgba.red, rgba.green, rgba.blue)
            button.hex_label.set_text(self._color_to_hex(color))
            self.on_ticks_color_changed(button)
        
        ticks_color_button.connect("color-set", ticks_color_callback)
        self.hour_tick_controls.append(ticks_hbox)
        self.ticks_color_button = ticks_color_button
        grid.attach(ticks_hbox, 1, row, 1, 1)
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Minute Ticks Section
        label = Gtk.Label(label="<b>Minute Ticks</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Show minute ticks checkbox
        label = Gtk.Label(label="Show minute ticks:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        self.show_minute_ticks_switch = Gtk.Switch()
        self.show_minute_ticks_switch.set_active(self.parent_clock.theme.get('show_minute_ticks'))
        self.show_minute_ticks_switch.set_halign(Gtk.Align.START)
        self.show_minute_ticks_switch.connect("notify::active", self.on_show_minute_ticks_toggled)
        grid.attach(self.show_minute_ticks_switch, 1, row, 1, 1)
        row += 1
        
        # Track minute tick controls for visibility management
        self.minute_tick_controls = []
        
        # Determine initial visibility
        minute_ticks_visible = self.parent_clock.theme.get('show_minute_ticks')
        
        # Minute tick style dropdown
        label = Gtk.Label(label="Style:")
        label.set_halign(Gtk.Align.START)
        label.set_visible(minute_ticks_visible)
        self.minute_tick_controls.append(label)
        grid.attach(label, 0, row, 1, 1)
        
        self.minute_style_combo = Gtk.ComboBoxText()
        self.minute_style_combo.set_visible(minute_ticks_visible)
        self.minute_tick_controls.append(self.minute_style_combo)
        self.minute_style_combo.append("square", "Square")
        self.minute_style_combo.append("round", "Round")
        self.minute_style_combo.append("rectangular", "Rectangular")
        self.minute_style_combo.set_active_id(self.parent_clock.theme.get('minute_tick_style'))
        self.minute_style_combo.set_halign(Gtk.Align.START)
        self.minute_style_combo.connect("changed", self.on_minute_tick_style_changed)
        grid.attach(self.minute_style_combo, 1, row, 1, 1)
        row += 1
        
        # Track size slider widgets
        size_widgets = self._add_slider(grid, row, "Size:", self.parent_clock.theme.get('minute_tick_size'), 0.01, 0.05,
                        self.on_minute_tick_size_changed)
        for widget in size_widgets:
            widget.set_visible(minute_ticks_visible)
        self.minute_tick_controls.extend(size_widgets)
        row += 1
        
        # Minute shape slider (only visible for rectangular style)
        # Determine if shape should be visible (rectangular style AND minute ticks enabled)
        is_minute_rectangular = self.parent_clock.theme.get('minute_tick_style') == "rectangular"
        minute_shape_visible = minute_ticks_visible and is_minute_rectangular
        
        self.minute_shape_label = Gtk.Label(label="Shape:")
        self.minute_shape_label.set_halign(Gtk.Align.START)
        self.minute_shape_label.set_visible(minute_shape_visible)
        grid.attach(self.minute_shape_label, 0, row, 1, 1)
        
        # Convert aspect ratio to log scale for slider
        import math as m
        current_ratio = self.parent_clock.theme.get('minute_tick_aspect_ratio')
        slider_value = m.log2(current_ratio) if current_ratio > 0 else 0
        
        self.minute_shape_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -3.3, 1.5, 0.1)
        self.minute_shape_scale.set_value(slider_value)
        self.minute_shape_scale.set_hexpand(True)
        self.minute_shape_scale.set_size_request(400, -1)
        self.minute_shape_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self.minute_shape_scale.set_digits(1)
        
        # Add marks for reference
        self.minute_shape_scale.add_mark(0, Gtk.PositionType.BOTTOM, "Square")
        self.minute_shape_scale.add_mark(-3.3, Gtk.PositionType.BOTTOM, "Skinny")
        self.minute_shape_scale.add_mark(1.5, Gtk.PositionType.BOTTOM, "Wide")
        
        self.minute_shape_scale.set_visible(minute_shape_visible)
        self.minute_shape_scale.connect("value-changed", self.on_minute_tick_shape_changed)
        grid.attach(self.minute_shape_scale, 1, row, 1, 1)
        row += 1
        
        # Track shape widgets for visibility toggling
        self.minute_tick_shape_widgets = [self.minute_shape_label, self.minute_shape_scale]
        
        # Color button
        color_label = Gtk.Label(label="Color:")
        color_label.set_halign(Gtk.Align.START)
        color_label.set_visible(minute_ticks_visible)
        self.minute_tick_controls.append(color_label)
        grid.attach(color_label, 0, row, 1, 1)
        
        # Create horizontal box for button, hex label, and copy button
        minute_ticks_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        minute_ticks_hbox.set_visible(minute_ticks_visible)
        
        minute_ticks_color_button = Gtk.ColorButton()
        minute_ticks_color_button.set_use_alpha(False)
        minute_ticks_color = self.parent_clock.theme.get('minute_ticks_color')
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue = minute_ticks_color
        rgba.alpha = 1.0
        minute_ticks_color_button.set_rgba(rgba)
        minute_ticks_color_button.set_halign(Gtk.Align.START)
        minute_ticks_color_button.set_hexpand(False)
        minute_ticks_hbox.pack_start(minute_ticks_color_button, False, False, 0)
        
        # Add hex value label
        minute_ticks_hex_label = Gtk.Label()
        minute_ticks_hex_label.set_text(self._color_to_hex(minute_ticks_color))
        minute_ticks_hex_label.set_selectable(True)
        minute_ticks_hex_label.set_halign(Gtk.Align.START)
        minute_ticks_hex_label.get_style_context().add_class("monospace")
        minute_ticks_hbox.pack_start(minute_ticks_hex_label, False, False, 0)
        minute_ticks_color_button.hex_label = minute_ticks_hex_label
        
        # Add copy button
        minute_ticks_copy_button = Gtk.Button()
        minute_ticks_copy_button.set_label("📋")
        minute_ticks_copy_button.set_tooltip_text("Copy to clipboard")
        minute_ticks_copy_button.set_relief(Gtk.ReliefStyle.NONE)
        minute_ticks_copy_button.connect("clicked", lambda btn: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(minute_ticks_hex_label.get_text(), -1))
        minute_ticks_hbox.pack_start(minute_ticks_copy_button, False, False, 0)
        
        def minute_ticks_color_callback(button):
            rgba = button.get_rgba()
            color = (rgba.red, rgba.green, rgba.blue)
            button.hex_label.set_text(self._color_to_hex(color))
            self.on_minute_ticks_color_changed(button)
        
        minute_ticks_color_button.connect("color-set", minute_ticks_color_callback)
        self.minute_tick_controls.append(minute_ticks_hbox)
        self.minute_ticks_color_button = minute_ticks_color_button
        grid.attach(minute_ticks_hbox, 1, row, 1, 1)
        row += 1
        
        return grid
    
    def _create_hands_page(self):
        """Create Hands customization page"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_margin_start(24)
        grid.set_margin_end(24)
        grid.set_margin_top(24)
        grid.set_margin_bottom(24)
        
        # Store grid reference for dynamic slider updates
        self.hands_page_grid = grid
        
        row = 0
        
        # Hand Theme Section (applies to all hands)
        label = Gtk.Label(label="<b>Hand Theme</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Hand theme picker
        label = Gtk.Label(label="Hand Images:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        hand_theme_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.hand_theme_label = Gtk.Label(label=self._format_hand_theme_label())
        self.hand_theme_label.set_halign(Gtk.Align.START)
        hand_theme_box.pack_start(self.hand_theme_label, False, False, 0)
        
        choose_hand_theme_button = Gtk.Button(label="Choose…")
        choose_hand_theme_button.connect('clicked', self.on_choose_hand_theme_clicked)
        hand_theme_box.pack_start(choose_hand_theme_button, False, False, 0)
        
        clear_hand_theme_button = Gtk.Button(label="Clear")
        clear_hand_theme_button.connect('clicked', self.on_clear_hand_theme_clicked)
        hand_theme_box.pack_start(clear_hand_theme_button, False, False, 0)
        
        grid.attach(hand_theme_box, 1, row, 1, 1)
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Hour Hand Section
        label = Gtk.Label(label="<b>Hour Hand</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        hour_length_widgets = self._add_slider(grid, row, "Length:", self.parent_clock.theme.get('hour_hand_length'), 0.3, 0.7,
                        self.on_hour_hand_length_changed)
        self.hour_length_widgets = hour_length_widgets
        row += 1
        
        hour_tail_widgets = self._add_slider(grid, row, "Tail:", self.parent_clock.theme.get('hour_hand_tail'), 0.0, 0.3,
                        self.on_hour_hand_tail_changed)
        self.hour_tail_widgets = hour_tail_widgets
        row += 1
        
        # Width slider - will be dynamically configured based on mode (geometric vs image)
        # Start with image mode defaults (logarithmic, 0.33-3.0)
        hour_width_widgets = self._add_slider(grid, row, "Width:", 1.0, 0.33, 3.0,
                        self.on_hour_hand_width_changed, logarithmic=True)
        self.hour_width_widgets = hour_width_widgets
        self.hour_width_scale = hour_width_widgets[1]
        self.hour_width_row = row  # Store row for potential slider replacement
        row += 1
        
        hands_color_widgets = self._add_color_button(grid, row, "Color:", self.parent_clock.theme.get('hands_color'),
                              self.on_hands_color_changed)
        self.hands_color_button = hands_color_widgets[1]
        self.hands_color_widgets = hands_color_widgets
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Minute Hand Section
        label = Gtk.Label(label="<b>Minute Hand</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        minute_length_widgets = self._add_slider(grid, row, "Length:", self.parent_clock.theme.get('minute_hand_length'), 0.5, 0.9,
                        self.on_minute_hand_length_changed)
        self.minute_length_widgets = minute_length_widgets
        row += 1
        
        minute_tail_widgets = self._add_slider(grid, row, "Tail:", self.parent_clock.theme.get('minute_hand_tail'), 0.0, 0.3,
                        self.on_minute_hand_tail_changed)
        self.minute_tail_widgets = minute_tail_widgets
        row += 1
        
        # Width slider - will be dynamically configured based on mode (geometric vs image)
        # Start with image mode defaults (logarithmic, 0.33-3.0)
        minute_width_widgets = self._add_slider(grid, row, "Width:", 1.0, 0.33, 3.0,
                        self.on_minute_hand_width_changed, logarithmic=True)
        self.minute_width_widgets = minute_width_widgets
        self.minute_width_scale = minute_width_widgets[1]
        self.minute_width_row = row  # Store row for potential slider replacement
        row += 1
        
        # Note: Minute hand uses same color as hour hand
        label = Gtk.Label(label="(Uses same color as Hour Hand)")
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class('dim-label')
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Second Hand Section
        label = Gtk.Label(label="<b>Second Hand</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        second_length_widgets = self._add_slider(grid, row, "Length:", self.parent_clock.theme.get('second_hand_length'), 0.5, 1.0,
                        self.on_second_hand_length_changed)
        self.second_length_widgets = second_length_widgets
        row += 1
        
        second_tail_widgets = self._add_slider(grid, row, "Tail:", self.parent_clock.theme.get('second_hand_tail'), 0.0, 0.4,
                        self.on_second_hand_tail_changed)
        self.second_tail_widgets = second_tail_widgets
        row += 1
        
        # Width slider - will be dynamically configured based on mode (geometric vs image)
        # Start with image mode defaults (logarithmic, 0.33-3.0)
        second_width_widgets = self._add_slider(grid, row, "Width:", 1.0, 0.33, 3.0,
                        self.on_second_hand_width_changed, logarithmic=True)
        self.second_width_widgets = second_width_widgets
        self.second_width_scale = second_width_widgets[1]
        self.second_width_row = row  # Store row for potential slider replacement
        row += 1
        
        second_hand_color_widgets = self._add_color_button(grid, row, "Color:", self.parent_clock.theme.get('second_hand_color'),
                              self.on_second_hand_color_changed)
        self.second_hand_color_button = second_hand_color_widgets[1]
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Center Dot Section
        label = Gtk.Label(label="<b>Center Dot</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        self._add_slider(grid, row, "Size:", self.parent_clock.theme.get('center_dot_radius'), 0.01, 0.1,
                        self.on_center_dot_size_changed)
        row += 1
        
        # Note: Center dot uses same color as hands
        label = Gtk.Label(label="(Uses same color as Hands)")
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class('dim-label')
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        return grid
    
    def _create_date_box_page(self):
        """Create Date Box customization page"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_margin_start(24)
        grid.set_margin_end(24)
        grid.set_margin_top(24)
        grid.set_margin_bottom(24)
        
        row = 0
        
        # Date Box Section
        label = Gtk.Label(label="<b>Date Box</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        self._add_slider(grid, row, "Width:", self.parent_clock.theme.get('date_box_width'), 0.4, 2.0,
                        self.on_date_box_width_changed)
        row += 1
        
        self._add_slider(grid, row, "Height:", self.parent_clock.theme.get('date_box_height'), 0.1, 0.5,
                        self.on_date_box_height_changed)
        row += 1
        
        self._add_slider(grid, row, "Margin:", self.parent_clock.theme.get('date_box_margin'), 0.0, 0.5,
                        self.on_date_box_margin_changed)
        row += 1
        
        self._add_slider(grid, row, "Font Size:", self.parent_clock.theme.get('date_font_size'), 0.05, 0.2,
                        self.on_date_font_size_changed)
        row += 1
        
        # Date format selection
        label = Gtk.Label(label="Format:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        # Generate examples using today's date
        import datetime
        today = datetime.datetime.now()
        
        self.date_format_combo = Gtk.ComboBoxText()
        self.date_format_combo.append("%Y-%m-%d", today.strftime("%Y-%m-%d"))
        self.date_format_combo.append("%d/%m/%Y", today.strftime("%d/%m/%Y"))
        self.date_format_combo.append("%m/%d/%Y", today.strftime("%m/%d/%Y"))
        self.date_format_combo.append("%B %d, %Y", today.strftime("%B %d, %Y"))
        self.date_format_combo.append("%d %b %Y", today.strftime("%d %b %Y"))
        self.date_format_combo.append("%A, %B %d", today.strftime("%A, %B %d"))
        self.date_format_combo.append("%a %d %b", today.strftime("%a %d %b"))
        self.date_format_combo.append("custom", "Custom...")
        
        current_format = self.parent_clock.theme.get('date_format')
        self.date_format_combo.set_active_id(current_format)
        if self.date_format_combo.get_active_id() is None:
            # Current format is custom
            self.date_format_combo.set_active_id("custom")
            self.custom_date_format = current_format
        else:
            self.custom_date_format = None
        
        self.date_format_combo.set_halign(Gtk.Align.START)
        self.date_format_combo.connect("changed", self.on_date_format_changed)
        
        # Create horizontal box for combo and edit button
        format_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        format_box.pack_start(self.date_format_combo, False, False, 0)
        
        # Add edit button for custom format (only visible when custom is selected)
        self.edit_custom_format_button = Gtk.Button(label="Edit...")
        self.edit_custom_format_button.connect("clicked", self.on_edit_custom_format_clicked)
        self.edit_custom_format_button.set_visible(self.date_format_combo.get_active_id() == "custom")
        format_box.pack_start(self.edit_custom_format_button, False, False, 0)
        
        grid.attach(format_box, 1, row, 1, 1)
        row += 1
        
        # Font selection
        label = Gtk.Label(label="Font:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        date_font_button = Gtk.FontButton()
        date_font_button.set_font(self.parent_clock.theme.get('date_font'))
        date_font_button.set_use_font(False)
        date_font_button.set_show_size(False)
        date_font_button.set_halign(Gtk.Align.START)
        date_font_button.connect("font-set", self.on_date_font_changed)
        grid.attach(date_font_button, 1, row, 1, 1)
        row += 1
        
        # Bold checkbox
        label = Gtk.Label(label="Bold:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        date_bold_switch = Gtk.Switch()
        date_bold_switch.set_active(self.parent_clock.theme.get('date_bold'))
        date_bold_switch.set_halign(Gtk.Align.START)
        date_bold_switch.connect("notify::active", self.on_date_bold_toggled)
        grid.attach(date_bold_switch, 1, row, 1, 1)
        row += 1
        
        # Text color
        date_text_color_widgets = self._add_color_button(grid, row, "Text Color:", self.parent_clock.theme.get('date_text_color'),
                              self.on_date_text_color_changed)
        self.date_text_color_button = date_text_color_widgets[1]
        row += 1
        
        return grid
    
    def _create_options_page(self):
        """Create Options page"""
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_margin_start(24)
        grid.set_margin_end(24)
        grid.set_margin_top(24)
        grid.set_margin_bottom(24)
        
        row = 0
        
        # System Options Section
        label = Gtk.Label(label="<b>System Options</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Auto Start checkbox
        label = Gtk.Label(label="Auto Start on Logon:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        autostart_switch = Gtk.Switch()
        autostart_switch.set_active(self.parent_clock.is_autostart_enabled())
        autostart_switch.set_halign(Gtk.Align.START)
        autostart_switch.connect("notify::active", self.on_autostart_toggled)
        grid.attach(autostart_switch, 1, row, 1, 1)
        row += 1
        
        # Separator
        grid.attach(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), 0, row, 2, 1)
        row += 1
        
        # Display Options Section
        label = Gtk.Label(label="<b>Display Options</b>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1
        
        # Show Date checkbox
        label = Gtk.Label(label="Show Date:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        show_date_switch = Gtk.Switch()
        show_date_switch.set_active(self.parent_clock.settings.get('show_date_box'))
        show_date_switch.set_halign(Gtk.Align.START)
        show_date_switch.connect("notify::active", self.on_show_date_toggled)
        grid.attach(show_date_switch, 1, row, 1, 1)
        row += 1
        
        # Show Seconds checkbox
        label = Gtk.Label(label="Show Seconds:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        show_seconds_switch = Gtk.Switch()
        show_seconds_switch.set_active(self.parent_clock.settings.get('show_second_hand'))
        show_seconds_switch.set_halign(Gtk.Align.START)
        show_seconds_switch.connect("notify::active", self.on_show_seconds_toggled)
        grid.attach(show_seconds_switch, 1, row, 1, 1)
        row += 1
        
        # Snap Minute Hand checkbox
        label = Gtk.Label(label="Snap Minute Hand:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        snap_minute_switch = Gtk.Switch()
        snap_minute_switch.set_active(self.parent_clock.settings.get('minute_hand_snap'))
        snap_minute_switch.set_halign(Gtk.Align.START)
        snap_minute_switch.connect("notify::active", self.on_minute_hand_snap_toggled)
        grid.attach(snap_minute_switch, 1, row, 1, 1)
        row += 1
        
        # Always on Top checkbox
        label = Gtk.Label(label="Always on Top:")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        always_on_top_switch = Gtk.Switch()
        always_on_top_switch.set_active(self.parent_clock.settings.get('always_on_top'))
        always_on_top_switch.set_halign(Gtk.Align.START)
        always_on_top_switch.connect("notify::active", self.on_always_on_top_toggled_dialog)
        grid.attach(always_on_top_switch, 1, row, 1, 1)
        row += 1
        
        return grid
    
    def _populate_themes(self):
        """Populate the themes grid with available themes"""
        # Save current selection
        selected_theme_name = None
        selected = self.themes_flow.get_selected_children()
        if selected:
            selected_theme_name = selected[0].theme_name
        
        # Clear existing items
        for child in self.themes_flow.get_children():
            self.themes_flow.remove(child)
        
        # Get all available themes using Theme class
        from theme import Theme
        available_themes = Theme.list_available_themes(self.parent_clock.themes_dir)
        
        # Add each theme
        for theme_name in available_themes:
            self._add_theme_item(theme_name)
        
        self.themes_flow.show_all()
        
        # Restore selection if the theme still exists
        if selected_theme_name and selected_theme_name in available_themes:
            for child in self.themes_flow.get_children():
                if hasattr(child, 'theme_name') and child.theme_name == selected_theme_name:
                    self.themes_flow.select_child(child)
                    break
    
    def _add_theme_item(self, theme_name):
        """Add a single theme item to the grid"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        
        # Preview image
        img = Gtk.Image()
        preview_path = self._get_theme_preview_path(theme_name)
        if os.path.exists(preview_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(preview_path, 200, 200, True)
                img.set_from_pixbuf(pixbuf)
            except Exception:
                # Use placeholder if preview fails to load
                img.set_from_icon_name('image-missing', Gtk.IconSize.DIALOG)
        else:
            # Generate preview if it doesn't exist
            self._generate_theme_preview(theme_name)
            if os.path.exists(preview_path):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(preview_path, 200, 200, True)
                    img.set_from_pixbuf(pixbuf)
                except Exception:
                    img.set_from_icon_name('image-missing', Gtk.IconSize.DIALOG)
            else:
                img.set_from_icon_name('image-missing', Gtk.IconSize.DIALOG)
        
        # Theme name label
        label = Gtk.Label(label=theme_name)
        label.set_max_width_chars(20)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_halign(Gtk.Align.CENTER)
        
        # Highlight current theme with bold text only
        if theme_name == self.parent_clock.theme.name:
            label.set_markup(f"<b>{theme_name}</b>")
        
        box.pack_start(img, False, False, 0)
        box.pack_start(label, False, False, 0)
        
        child = Gtk.FlowBoxChild()
        child.add(box)
        child.theme_name = theme_name
        self.themes_flow.add(child)
    
    def _get_theme_preview_path(self, theme_name):
        """Get the path to a theme's preview image"""
        if theme_name == 'default':
            # Store default preview in config dir
            return os.path.join(self.parent_clock.config_dir, 'default_preview.png')
        return os.path.join(self.parent_clock.themes_dir, f"{theme_name}.png")
    
    def _generate_theme_preview(self, theme_name):
        """Generate a 200x200 preview image for a theme and save to disk"""
        import cairo
        from theme import Theme
        
        # Save current theme
        saved_theme = self.parent_clock.theme
        
        # Load the theme temporarily
        temp_theme = Theme(theme_name, self.parent_clock.themes_dir)
        temp_theme.load()
        self.parent_clock.theme = temp_theme
        
        # Create a 200x200 surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)
        
        # Clear background
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        
        # Draw clock using the same rendering method as main clock
        # Center at 100,100 with radius 80
        # Use settings for second hand visibility
        show_seconds = self.parent_clock.settings.get('show_second_hand')
        self.parent_clock._draw_clock_face(cr, 100, 100, 80, show_date=False, show_seconds=show_seconds)
        
        # Restore original theme
        self.parent_clock.theme = saved_theme
        self.parent_clock.queue_draw()
        
        # Save to file
        preview_path = self._get_theme_preview_path(theme_name)
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        surface.write_to_png(preview_path)
    
    def _generate_preview_surface_from_current_state(self):
        """Generate a preview surface from current theme state without saving to disk"""
        import cairo
        
        # Create a 200x200 surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)
        
        # Clear background
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        
        # Draw clock using the same rendering method as main clock
        # Center at 100,100 with radius 80
        # Use settings for second hand visibility
        show_seconds = self.parent_clock.settings.get('show_second_hand')
        self.parent_clock._draw_clock_face(cr, 100, 100, 80, show_date=False, show_seconds=show_seconds)
        
        return surface
    
    def _regenerate_current_theme_preview(self):
        """Regenerate preview for current theme from in-memory state and store in memory"""
        # Generate preview surface from current state
        surface = self._generate_preview_surface_from_current_state()
        
        # Convert surface to pixbuf for display
        import io
        buffer = io.BytesIO()
        surface.write_to_png(buffer)
        buffer.seek(0)
        
        from gi.repository import GdkPixbuf
        loader = GdkPixbuf.PixbufLoader.new_with_type('png')
        loader.write(buffer.read())
        loader.close()
        pixbuf = loader.get_pixbuf()
        
        # Store in memory (only one theme can be dirty at a time)
        self.in_memory_preview_pixbuf = pixbuf
        
        # Update the theme item display
        self._update_theme_item_preview(self.parent_clock.theme.name, pixbuf)
    
    def _update_theme_item_preview(self, theme_name, pixbuf):
        """Update the preview image for a specific theme item in the grid"""
        # Find the theme item in the flowbox
        for child in self.themes_flow.get_children():
            if hasattr(child, 'theme_name') and child.theme_name == theme_name:
                # Get the box inside the child
                box = child.get_child()
                if box:
                    # Get the image widget (first child of the box)
                    children = box.get_children()
                    if children and isinstance(children[0], Gtk.Image):
                        children[0].set_from_pixbuf(pixbuf)
                break
    
    def _save_in_memory_preview_to_disk(self):
        """Save the in-memory preview to disk for the current theme"""
        if self.in_memory_preview_pixbuf:
            preview_path = self._get_theme_preview_path(self.parent_clock.theme.name)
            os.makedirs(os.path.dirname(preview_path), exist_ok=True)
            self.in_memory_preview_pixbuf.savev(preview_path, 'png', [], [])
            # Clear in-memory preview after saving
            self.in_memory_preview_pixbuf = None
    
    def on_theme_selection_changed(self, flowbox):
        """Handle theme selection change"""
        selected = flowbox.get_selected_children()
        if selected:
            theme_name = selected[0].theme_name
            # Enable delete button only for non-default themes
            self.delete_theme_button.set_sensitive(theme_name != 'default')
        else:
            self.delete_theme_button.set_sensitive(False)
    
    def on_theme_activated(self, flowbox, child):
        """Handle theme double-click/activation"""
        theme_name = child.theme_name
        
        # Check if there are unsaved changes
        if self.parent_clock.theme.is_dirty:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text=f"Apply theme '{theme_name}'?"
            )
            dialog.format_secondary_text("You have unsaved changes to the current theme.")
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
            dialog.add_button("Discard changes and switch", Gtk.ResponseType.NO)
            dialog.add_button("Save changes and switch", Gtk.ResponseType.YES)
            
            response = dialog.run()
            dialog.destroy()
            
            if response == Gtk.ResponseType.CANCEL:
                return
            elif response == Gtk.ResponseType.YES:
                # Save current theme before switching
                if self.parent_clock.theme.name == 'default':
                    # Can't save to default, show save as dialog
                    self.on_save_theme_as_clicked()
                    # After save as, user may have canceled, check if still dirty
                    if self.parent_clock.theme.is_dirty:
                        return  # User canceled save as
                else:
                    # Save to current theme
                    self.parent_clock.theme.save()
                    self.parent_clock.settings.save()
                    # Save in-memory preview to disk
                    self._save_in_memory_preview_to_disk()
            # If response == NO, just discard and continue
        
        # Apply the theme
        self._apply_theme(theme_name)
    
    def _apply_theme(self, theme_name):
        """Apply a theme using atomic reference swap"""
        # Create new theme object
        from theme import Theme
        new_theme = Theme(theme_name, self.parent_clock.themes_dir)
        new_theme.load()
        
        # Atomic reference swap - this is the key to avoiding contamination
        self.parent_clock.theme = new_theme
        
        # Update dialog controls to reflect new theme
        self._update_controls_from_clock()
        
        # Clear dirty flag since we just loaded a clean theme
        self.save_button.set_sensitive(False)
        
        # Update dialog title
        self.set_title(f"Clock Settings - {theme_name}")
        
        # Refresh themes grid to highlight new active theme
        self._populate_themes()
        
        # Clear any in-memory preview since we're now on a clean theme
        self.in_memory_preview_pixbuf = None
        
        # Save settings with new active theme
        self.parent_clock.settings.set('active_theme_name', theme_name)
        self.parent_clock.settings.save()
        
        # Redraw clock to show new theme
        self.parent_clock.queue_draw()
    
    def on_delete_theme_clicked(self, button):
        """Handle delete theme button click"""
        selected = self.themes_flow.get_selected_children()
        if not selected:
            return
        
        theme_name = selected[0].theme_name
        if theme_name == 'default':
            return  # Should not happen due to button sensitivity
        
        # Confirm deletion
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete theme '{theme_name}'?"
        )
        dialog.format_secondary_text("This action cannot be undone.")
        
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            # Delete theme file and preview
            theme_file = os.path.join(self.parent_clock.themes_dir, f"{theme_name}.json")
            preview_file = self._get_theme_preview_path(theme_name)
            
            try:
                if os.path.exists(theme_file):
                    os.remove(theme_file)
                if os.path.exists(preview_file):
                    os.remove(preview_file)
                
                # If deleted theme was active, switch to default
                if self.parent_clock.theme.name == theme_name:
                    self._apply_theme('default')
                else:
                    # Just refresh the grid
                    self._populate_themes()
            except Exception as e:
                error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Failed to delete theme"
                )
                error_dialog.format_secondary_text(str(e))
                error_dialog.run()
                error_dialog.destroy()
    
    def on_save_theme_as_clicked(self):
        """Handle Save Theme As button click"""
        dialog = Gtk.Dialog(title="Save Theme As", parent=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        
        label = Gtk.Label(label="Theme name:")
        label.set_halign(Gtk.Align.START)
        content.pack_start(label, False, False, 0)
        
        entry = Gtk.Entry()
        entry.set_text(self.parent_clock.theme.name if self.parent_clock.theme.name != 'default' else '')
        entry.set_activates_default(True)
        content.pack_start(entry, False, False, 0)
        
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        
        response = dialog.run()
        theme_name = entry.get_text().strip()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK and theme_name:
            if theme_name == 'default':
                error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="Invalid theme name"
                )
                error_dialog.format_secondary_text("Cannot use 'default' as a theme name.")
                error_dialog.run()
                error_dialog.destroy()
                return
            
            # Save current theme with new name
            new_theme = self.parent_clock.theme.duplicate(theme_name)
            new_theme.save()
            
            # Save in-memory preview to disk
            self._save_in_memory_preview_to_disk()
            
            # Switch to the new theme by creating new Theme object
            from theme import Theme
            self.parent_clock.theme = Theme(theme_name, self.parent_clock.themes_dir)
            self.parent_clock.theme.load()
            
            # Update settings
            self.parent_clock.settings.set('active_theme_name', theme_name)
            self.parent_clock.settings.save()
            
            # Update dialog
            self.save_button.set_sensitive(False)
            
            # Update UI
            self.set_title(f"Clock Settings - {theme_name}")
            self._populate_themes()
            
            # Settings already saved above
    
    def _add_slider(self, grid, row, label_text, value, min_val, max_val, callback, discrete=False, step=None, logarithmic=False):
        """Helper to add a labeled slider. Returns (label, scale) tuple for tracking."""
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        if logarithmic:
            # For logarithmic scale: map value range to log space
            # min_val to max_val -> log(min_val) to log(max_val)
            import math
            log_min = math.log(min_val)
            log_max = math.log(max_val)
            log_value = math.log(value)
            
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, log_min, log_max, (log_max - log_min) / 100)
            scale.set_value(log_value)
            scale.set_digits(2)
            
            # Store original callback and wrap it to convert from log space
            def log_callback(widget):
                log_val = widget.get_value()
                actual_val = math.exp(log_val)
                # Temporarily disconnect to avoid recursion
                widget.handler_block_by_func(log_callback)
                # Update display value
                widget.set_value(log_val)
                widget.handler_unblock_by_func(log_callback)
                # Create a fake widget with the actual value for the callback
                class FakeWidget:
                    def get_value(self):
                        return actual_val
                callback(FakeWidget())
            
            scale.connect("value-changed", log_callback)
            
            # Custom format function to display actual value
            def format_value(scale, log_val):
                actual_val = math.exp(log_val)
                return f"{actual_val:.2f}"
            scale.connect("format-value", format_value)
            
        else:
            # Calculate step based on range and discrete mode
            if step:
                actual_step = step
                digits = 0
            elif discrete:
                actual_step = 1
                digits = 0
            else:
                range_size = max_val - min_val
                actual_step = range_size / 100 if range_size < 10 else 1
                digits = 3 if range_size < 10 else 0
            
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_val, max_val, actual_step)
            scale.set_value(value)
            scale.set_digits(digits)
            
            if discrete:
                scale.set_round_digits(0)
            
            scale.connect("value-changed", callback)
        
        scale.set_hexpand(True)
        scale.set_size_request(400, -1)  # Set minimum width for sliders
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        
        grid.attach(scale, 1, row, 1, 1)
        
        return (label, scale)
    
    def _add_color_button(self, grid, row, label_text, color_tuple, callback):
        """Helper to add a labeled color button with hex value display and copy button"""
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 1, 1)
        
        # Create horizontal box for button, hex label, and copy button
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        color_button = Gtk.ColorButton()
        color_button.set_use_alpha(False)  # Disable alpha channel for clearer color selection
        color_button.set_rgba(self._tuple_to_rgba(color_tuple))
        color_button.set_halign(Gtk.Align.START)
        color_button.set_hexpand(False)
        hbox.pack_start(color_button, False, False, 0)
        
        # Add hex value label
        hex_label = Gtk.Label()
        hex_label.set_text(self._color_to_hex(color_tuple))
        hex_label.set_selectable(True)  # Allow copying
        hex_label.set_halign(Gtk.Align.START)
        hex_label.get_style_context().add_class("monospace")
        hbox.pack_start(hex_label, False, False, 0)
        
        # Add copy button
        copy_button = Gtk.Button()
        copy_button.set_label("📋")
        copy_button.set_tooltip_text("Copy to clipboard")
        copy_button.set_relief(Gtk.ReliefStyle.NONE)
        
        def copy_to_clipboard(btn):
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(hex_label.get_text(), -1)
        
        copy_button.connect("clicked", copy_to_clipboard)
        hbox.pack_start(copy_button, False, False, 0)
        
        # Store hex label reference for updates
        color_button.hex_label = hex_label
        
        # Wrap callback to update hex label
        def wrapped_callback(button):
            rgba = button.get_rgba()
            color = (rgba.red, rgba.green, rgba.blue)
            button.hex_label.set_text(self._color_to_hex(color))
            callback(button)
        
        color_button.connect("color-set", wrapped_callback)
        grid.attach(hbox, 1, row, 1, 1)
        
        return (label, color_button)
    
    def _tuple_to_rgba(self, color_tuple):
        """Convert (R, G, B) tuple to Gdk.RGBA"""
        rgba = Gdk.RGBA()
        rgba.red = color_tuple[0]
        rgba.green = color_tuple[1]
        rgba.blue = color_tuple[2]
        rgba.alpha = 1.0
        return rgba
    
    def _rgba_to_tuple(self, rgba):
        """Convert Gdk.RGBA to (R, G, B) tuple"""
        return (rgba.red, rgba.green, rgba.blue)
    
    def _color_to_hex(self, color_tuple):
        """Convert (R, G, B) tuple (0.0-1.0) to hex string #RRGGBB"""
        r = int(color_tuple[0] * 255)
        g = int(color_tuple[1] * 255)
        b = int(color_tuple[2] * 255)
        return f"#{r:02X}{g:02X}{b:02X}"
    
    # Callback methods
    def on_size_changed(self, scale):
        size = int(scale.get_value())
        self._on_settings_property_changed('clock_size', size)
        self.parent_clock.update_window_size()
    
    def on_background_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('background_color', color)


    def on_rim_width_changed(self, scale):
        value = max(0.0, min(0.05, float(scale.get_value())))
        self._on_theme_property_changed('rim_width', value)

    def on_rim_opacity_changed(self, scale):
        value = max(0.0, min(1.0, float(scale.get_value())))
        self._on_theme_property_changed('rim_opacity', value)
    
    def on_rim_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('rim_color', color)
    
    def on_background_opacity_changed(self, scale):
        value = max(0.0, min(1.0, float(scale.get_value())))
        self._on_theme_property_changed('background_opacity', value)
    
    def on_face_color_opacity_changed(self, scale):
        value = max(0.0, min(1.0, float(scale.get_value())))
        self._on_theme_property_changed('face_color_opacity', value)
    
    def on_face_texture_opacity_changed(self, scale):
        value = max(0.0, min(1.0, float(scale.get_value())))
        self._on_theme_property_changed('face_texture_opacity', value)
    
    def on_border_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('border_color', color)

    def _format_texture_label(self, texture_name):
        if not texture_name:
            return '(none)'
        # Remove file extension from display name
        return os.path.splitext(texture_name)[0]
    
    def _format_hand_image_label(self, hand_type):
        """Format label for hand image display (hour, minute, or second)"""
        source = self.parent_clock.theme.get(f'{hand_type}_hand_image_source')
        name = self.parent_clock.theme.get(f'{hand_type}_hand_image_name')
        
        if source == 'none' or not name:
            return '(none)'
        
        # Display just the hand set name (folder name)
        return name
    
    def _format_hand_theme_label(self):
        """Format label for unified hand theme display"""
        # Check if all hands use the same theme
        hour_source = self.parent_clock.theme.get('hour_hand_image_source')
        hour_name = self.parent_clock.theme.get('hour_hand_image_name')
        minute_source = self.parent_clock.theme.get('minute_hand_image_source')
        minute_name = self.parent_clock.theme.get('minute_hand_image_name')
        second_source = self.parent_clock.theme.get('second_hand_image_source')
        second_name = self.parent_clock.theme.get('second_hand_image_name')
        
        # If all are none
        if hour_source == 'none' and minute_source == 'none' and second_source == 'none':
            return '(none)'
        
        # If all use the same theme
        if (hour_source == minute_source == second_source and 
            hour_name == minute_name == second_name and 
            hour_name is not None):
            return hour_name
        
        # Mixed themes
        return '(mixed)'
    
    def on_enable_color_toggled(self, checkbox):
        value = checkbox.get_active()
        self._on_theme_property_changed('enable_face_color', value)
        self._update_color_controls_visibility()
    
    def on_enable_texture_toggled(self, checkbox):
        value = checkbox.get_active()
        self._on_theme_property_changed('enable_face_texture', value)
        self._update_texture_controls_visibility()
    
    def _update_color_controls_visibility(self):
        visible = self.enable_color_check.get_active()
        for w in self.face_color_controls:
            w.set_visible(visible)
    
    def _update_texture_controls_visibility(self):
        visible = self.enable_texture_check.get_active()
        for w in self.face_texture_controls:
            w.set_visible(visible)
    
    def _update_hand_controls_visibility(self):
        """Update visibility of hand controls based on whether hand images are used"""
        import math
        
        # Check if any hand has an image
        has_hand_images = False
        for hand_type in ['hour', 'minute', 'second']:
            source = self.parent_clock.theme.get(f'{hand_type}_hand_image_source')
            if source != 'none':
                has_hand_images = True
                break
        
        # When using hand images:
        # - Hide tail sliders (not applicable to images)
        # - Show width sliders (for scaling image width) - use image_width property
        # - Show color controls (for recoloring images in memory)
        # - Show length sliders (for scaling image length)
        
        # When not using hand images (geometric hands):
        # - Show tail sliders
        # - Show width sliders (for line width) - use width property
        # - Show color controls
        # - Show length sliders
        
        if has_hand_images:
            # Hide tail sliders
            for widget in self.hour_tail_widgets:
                widget.set_visible(False)
            for widget in self.minute_tail_widgets:
                widget.set_visible(False)
            for widget in self.second_tail_widgets:
                widget.set_visible(False)
            
            # Show color controls (for recoloring hand images)
            for widget in self.hands_color_widgets:
                widget.set_visible(True)
            
            # Recreate width sliders for image mode (logarithmic, 0.33-3.0)
            self._recreate_width_slider('hour', 'image')
            self._recreate_width_slider('minute', 'image')
            self._recreate_width_slider('second', 'image')
            
        else:
            # Show tail sliders
            for widget in self.hour_tail_widgets:
                widget.set_visible(True)
            for widget in self.minute_tail_widgets:
                widget.set_visible(True)
            for widget in self.second_tail_widgets:
                widget.set_visible(True)
            
            # Show color controls
            for widget in self.hands_color_widgets:
                widget.set_visible(True)
            
            # Recreate width sliders for geometric mode (linear, 0.01-0.08 for hour, etc.)
            self._recreate_width_slider('hour', 'geometric')
            self._recreate_width_slider('minute', 'geometric')
            self._recreate_width_slider('second', 'geometric')
    
    def _recreate_width_slider(self, hand_type, mode):
        """Recreate a width slider with appropriate range for the mode"""
        import math
        
        # Get current widgets and row
        if hand_type == 'hour':
            old_widgets = self.hour_width_widgets
            row = self.hour_width_row
            callback = self.on_hour_hand_width_changed
        elif hand_type == 'minute':
            old_widgets = self.minute_width_widgets
            row = self.minute_width_row
            callback = self.on_minute_hand_width_changed
        else:  # second
            old_widgets = self.second_width_widgets
            row = self.second_width_row
            callback = self.on_second_hand_width_changed
        
        # Remove old widgets from grid
        for widget in old_widgets:
            self.hands_page_grid.remove(widget)
        
        # Create new slider with appropriate range and scale
        if mode == 'image':
            # Image mode: logarithmic scale, 0.33-3.0, default 1.0
            value = self.parent_clock.theme.get(f'{hand_type}_hand_image_width')
            new_widgets = self._add_slider(self.hands_page_grid, row, "Width:", value, 0.33, 3.0,
                                          callback, logarithmic=True)
        else:  # geometric
            # Geometric mode: linear scale with appropriate ranges
            value = self.parent_clock.theme.get(f'{hand_type}_hand_width')
            if hand_type == 'hour':
                new_widgets = self._add_slider(self.hands_page_grid, row, "Width:", value, 0.01, 0.08,
                                              callback, logarithmic=False)
            elif hand_type == 'minute':
                new_widgets = self._add_slider(self.hands_page_grid, row, "Width:", value, 0.005, 0.05,
                                              callback, logarithmic=False)
            else:  # second
                new_widgets = self._add_slider(self.hands_page_grid, row, "Width:", value, 0.002, 0.02,
                                              callback, logarithmic=False)
        
        # Update stored references
        if hand_type == 'hour':
            self.hour_width_widgets = new_widgets
            self.hour_width_scale = new_widgets[1]
        elif hand_type == 'minute':
            self.minute_width_widgets = new_widgets
            self.minute_width_scale = new_widgets[1]
        else:  # second
            self.second_width_widgets = new_widgets
            self.second_width_scale = new_widgets[1]
        
        # Show the new widgets
        for widget in new_widgets:
            widget.show()


    def _iter_texture_files(self):
        textures = []

        builtin_dir = self.parent_clock.get_builtin_textures_dir()
        if os.path.isdir(builtin_dir):
            for name in sorted(os.listdir(builtin_dir)):
                if name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    textures.append(('builtin', name, os.path.join(builtin_dir, name)))

        user_dir = self.parent_clock.get_user_textures_dir()
        if os.path.isdir(user_dir):
            for name in sorted(os.listdir(user_dir)):
                if name.lower().endswith(('.png', '.jpg', '.jpeg')):
                    textures.append(('user', name, os.path.join(user_dir, name)))

        return textures

    def _open_texture_picker(self, title):
        dialog = Gtk.Dialog(title=title, parent=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(700, 500)

        content = dialog.get_content_area()
        
        # Add CSS for subtle selection color
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            flowboxchild:selected {
                background-color: rgba(100, 100, 100, 0.2);
            }
        """)
        screen = dialog.get_screen()
        style_context = dialog.get_style_context()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content.pack_start(scrolled, True, True, 0)
        
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(6)
        flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flow.set_row_spacing(10)
        flow.set_column_spacing(10)
        flow.set_activate_on_single_click(False)  # Only activate on double-click
        scrolled.add(flow)
        
        # Add double-click handler (child-activated only fires on double-click when activate_on_single_click is False)
        flow.connect('child-activated', lambda f, child: dialog.response(Gtk.ResponseType.OK))

        textures = self._iter_texture_files()
        for source, name, path in textures:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(6)
            box.set_margin_end(6)

            img = Gtk.Image()
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 96, 96, True)
                img.set_from_pixbuf(pixbuf)
            except Exception:
                pass

            # Remove file extension from display name
            display_name = os.path.splitext(name)[0]
            label = Gtk.Label(label=display_name)
            label.set_max_width_chars(18)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_halign(Gtk.Align.CENTER)

            box.pack_start(img, False, False, 0)
            box.pack_start(label, False, False, 0)

            row = Gtk.FlowBoxChild()
            row.add(box)
            row.texture_source = source
            row.texture_name = name
            flow.add(row)
        
        # Add Import button at the bottom
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_margin_start(12)
        button_box.set_margin_end(12)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(12)
        
        import_button = Gtk.Button(label="Import Texture…")
        import_button.connect('clicked', lambda btn: self._on_import_texture_from_picker(dialog, flow))
        button_box.pack_start(import_button, False, False, 0)
        content.pack_start(button_box, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        selected = None
        if response == Gtk.ResponseType.OK:
            sel = flow.get_selected_children()
            if sel:
                child = sel[0]
                selected = (child.texture_source, child.texture_name)
        dialog.destroy()
        return selected

    def on_choose_face_texture_clicked(self, button):
        selected = self._open_texture_picker('Choose Face Texture')
        if not selected:
            return
        source, name = selected
        self.parent_clock.theme.set('face_texture_source', source)
        self.parent_clock.theme.set('face_texture_name', name)
        self.face_texture_label.set_text(self._format_texture_label(name))
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()


    def _on_import_texture_from_picker(self, picker_dialog, flow):
        """Import texture from within the texture picker dialog and refresh the list"""
        imported_name = self._import_texture_file(picker_dialog)
        if imported_name:
            # Refresh the texture list in the picker
            self._refresh_texture_flow(flow)
    
    def _import_texture_file(self, parent_dialog):
        """Import a texture file and return the imported filename, or None if cancelled/failed"""
        chooser = Gtk.FileChooserDialog(
            title='Import Texture',
            parent=parent_dialog,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

        filter_img = Gtk.FileFilter()
        filter_img.set_name('Images')
        filter_img.add_pattern('*.png')
        filter_img.add_pattern('*.jpg')
        filter_img.add_pattern('*.jpeg')
        chooser.add_filter(filter_img)

        resp = chooser.run()
        path = chooser.get_filename() if resp == Gtk.ResponseType.OK else None
        chooser.destroy()
        if not path:
            return None

        dest_dir = self.parent_clock.get_user_textures_dir()
        os.makedirs(dest_dir, exist_ok=True)

        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        dest = os.path.join(dest_dir, base)
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(dest_dir, f"{name}_{i}{ext}")
            base = f"{name}_{i}{ext}"
            i += 1

        try:
            shutil.copy2(path, dest)
        except Exception:
            return None

        # Invalidate cached surface if any
        if hasattr(self.parent_clock, '_texture_surface_cache'):
            self.parent_clock._texture_surface_cache.pop(dest, None)
        
        return base
    
    def _refresh_texture_flow(self, flow):
        """Refresh the texture list in a FlowBox"""
        # Remove all existing children
        for child in flow.get_children():
            flow.remove(child)
        
        # Re-populate with updated texture list
        textures = self._iter_texture_files()
        for source, name, path in textures:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(6)
            box.set_margin_end(6)

            img = Gtk.Image()
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 96, 96, True)
                img.set_from_pixbuf(pixbuf)
            except Exception:
                pass

            # Remove file extension from display name
            display_name = os.path.splitext(name)[0]
            label = Gtk.Label(label=display_name)
            label.set_max_width_chars(18)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_halign(Gtk.Align.CENTER)

            box.pack_start(img, False, False, 0)
            box.pack_start(label, False, False, 0)

            row = Gtk.FlowBoxChild()
            row.add(box)
            row.texture_source = source
            row.texture_name = name
            flow.add(row)
        
        flow.show_all()
    
    def on_import_texture_clicked(self, button):
        """Legacy method - no longer used since import is now in texture picker"""
        pass
    
    def _iter_hand_sets(self):
        """
        Iterate over available hand image sets.
        Yields tuples of (source, name, paths_dict) where paths_dict contains
        'hour', 'minute', 'second' keys with paths to each hand image.
        """
        # Builtin hands
        builtin_dir = os.path.join(os.path.dirname(__file__), 'assets', 'hands')
        if os.path.exists(builtin_dir):
            for entry in os.listdir(builtin_dir):
                hand_dir = os.path.join(builtin_dir, entry)
                if os.path.isdir(hand_dir):
                    paths = self._get_hand_set_paths(hand_dir)
                    if paths:
                        yield ('builtin', entry, paths)
        
        # User hands
        user_dir = self.parent_clock.get_user_hands_dir()
        if os.path.exists(user_dir):
            for entry in os.listdir(user_dir):
                hand_dir = os.path.join(user_dir, entry)
                if os.path.isdir(hand_dir):
                    paths = self._get_hand_set_paths(hand_dir)
                    if paths:
                        yield ('user', entry, paths)
    
    def _get_hand_set_paths(self, hand_dir):
        """
        Get paths to hand images in a hand set directory.
        Prefers processed images, falls back to original.
        Returns dict with 'hour', 'minute', 'second' keys, or None if incomplete.
        """
        paths = {}
        
        for hand_type in ['hour', 'minute', 'second']:
            # Try processed image first
            processed_path = os.path.join(hand_dir, 'processed', f'{hand_type}.png')
            if os.path.exists(processed_path):
                paths[hand_type] = processed_path
                continue
            
            # Fall back to original image
            original_path = os.path.join(hand_dir, 'original', f'{hand_type}.png')
            if os.path.exists(original_path):
                paths[hand_type] = original_path
                continue
            
            # Legacy: try direct path
            legacy_path = os.path.join(hand_dir, f'{hand_type}.png')
            if os.path.exists(legacy_path):
                paths[hand_type] = legacy_path
                continue
            
            # Hand image not found
            return None
        
        # All three hand images must exist
        if len(paths) == 3:
            return paths
        return None
    
    def _open_hand_picker(self, title):
        """Open hand image set picker dialog"""
        dialog = Gtk.Dialog(title=title, parent=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(700, 500)

        content = dialog.get_content_area()
        
        # Add CSS for subtle selection color
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            flowboxchild:selected {
                background-color: rgba(100, 100, 100, 0.2);
            }
        """)
        screen = dialog.get_screen()
        style_context = dialog.get_style_context()
        style_context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content.pack_start(scrolled, True, True, 0)
        
        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(4)
        flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        flow.set_row_spacing(10)
        flow.set_column_spacing(10)
        flow.set_activate_on_single_click(False)
        scrolled.add(flow)
        
        # Add double-click handler
        flow.connect('child-activated', lambda f, child: dialog.response(Gtk.ResponseType.OK))

        hand_sets = self._iter_hand_sets()
        for source, name, paths in hand_sets:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(6)
            box.set_margin_end(6)

            # Create a composite preview showing all three hands
            preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            
            for hand_type in ['hour', 'minute', 'second']:
                img = Gtk.Image()
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(paths[hand_type], 30, 80, True)
                    img.set_from_pixbuf(pixbuf)
                except Exception:
                    pass
                preview_box.pack_start(img, False, False, 0)

            label = Gtk.Label(label=name)
            label.set_max_width_chars(18)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_halign(Gtk.Align.CENTER)

            box.pack_start(preview_box, False, False, 0)
            box.pack_start(label, False, False, 0)

            row = Gtk.FlowBoxChild()
            row.add(box)
            row.hand_source = source
            row.hand_name = name
            flow.add(row)
        
        # Add Import button at the bottom
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_margin_start(12)
        button_box.set_margin_end(12)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(12)
        
        import_button = Gtk.Button(label="Import Hand Set…")
        import_button.connect('clicked', lambda btn: self._on_import_hand_set_from_picker(dialog, flow))
        button_box.pack_start(import_button, False, False, 0)
        content.pack_start(button_box, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        selected = None
        if response == Gtk.ResponseType.OK:
            sel = flow.get_selected_children()
            if sel:
                child = sel[0]
                selected = (child.hand_source, child.hand_name)
        dialog.destroy()
        return selected
    
    def _on_import_hand_set_from_picker(self, picker_dialog, flow):
        """Import hand set from within the hand picker dialog and refresh the list"""
        imported_name = self._import_hand_set(picker_dialog)
        if imported_name:
            # Refresh the hand set list in the picker
            self._refresh_hand_flow(flow)
    
    def _import_hand_set(self, parent_dialog):
        """Import a hand set folder and return the folder name, or None if cancelled/failed"""
        chooser = Gtk.FileChooserDialog(
            title='Import Hand Set Folder',
            parent=parent_dialog,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

        resp = chooser.run()
        path = chooser.get_filename() if resp == Gtk.ResponseType.OK else None
        chooser.destroy()
        if not path:
            return None

        # Verify the folder contains the required hand images
        paths = self._get_hand_set_paths(path)
        if not paths:
            # Show error dialog
            error_dialog = Gtk.MessageDialog(
                parent=parent_dialog,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Invalid Hand Set"
            )
            error_dialog.format_secondary_text(
                "The selected folder must contain three PNG files:\n"
                "hour.png, minute.png, and second.png"
            )
            error_dialog.run()
            error_dialog.destroy()
            return None

        dest_dir = self.parent_clock.get_user_hands_dir()
        os.makedirs(dest_dir, exist_ok=True)

        folder_name = os.path.basename(path)
        dest = os.path.join(dest_dir, folder_name)
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(dest_dir, f"{folder_name}_{i}")
            folder_name = f"{folder_name}_{i}"
            i += 1

        try:
            shutil.copytree(path, dest)
        except Exception:
            return None

        return folder_name
    
    def _refresh_hand_flow(self, flow):
        """Refresh the hand set list in a FlowBox"""
        # Remove all existing children
        for child in flow.get_children():
            flow.remove(child)
        
        # Re-populate with updated hand set list
        hand_sets = self._iter_hand_sets()
        for source, name, paths in hand_sets:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_margin_top(6)
            box.set_margin_bottom(6)
            box.set_margin_start(6)
            box.set_margin_end(6)

            # Create a composite preview showing all three hands
            preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            
            for hand_type in ['hour', 'minute', 'second']:
                img = Gtk.Image()
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(paths[hand_type], 30, 80, True)
                    img.set_from_pixbuf(pixbuf)
                except Exception:
                    pass
                preview_box.pack_start(img, False, False, 0)

            label = Gtk.Label(label=name)
            label.set_max_width_chars(18)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_halign(Gtk.Align.CENTER)

            box.pack_start(preview_box, False, False, 0)
            box.pack_start(label, False, False, 0)

            row = Gtk.FlowBoxChild()
            row.add(box)
            row.hand_source = source
            row.hand_name = name
            flow.add(row)
        
        flow.show_all()

    
    def on_hour_tick_style_changed(self, combo):
        style = combo.get_active_id()
        self._on_theme_property_changed('hour_tick_style', style)
        
        # Update visibility of shape control based on style
        is_rectangular = (style == 'rectangular')
        for widget in self.hour_tick_shape_widgets:
            widget.set_visible(is_rectangular)
    
    def on_hour_tick_size_changed(self, scale):
        value = scale.get_value()
        self.parent_clock.theme.set('hour_tick_size', value)
    
    def on_hour_tick_shape_changed(self, scale):
        # Convert logarithmic slider value to aspect ratio
        import math
        slider_value = scale.get_value()
        aspect_ratio = math.pow(2, slider_value)
        self.parent_clock.theme.set('hour_tick_aspect_ratio', aspect_ratio)
    
    def on_tick_position_changed(self, scale):
        # Set both hour and minute tick positions to the same value
        position = scale.get_value()
        self.parent_clock.theme.set('hour_tick_position', position)
        self.parent_clock.theme.set('minute_tick_position', position)
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()
    
    def on_ticks_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self.parent_clock.theme.set('ticks_color', color)
    
    def on_minute_tick_style_changed(self, combo):
        style = combo.get_active_id()
        self._on_theme_property_changed('minute_tick_style', style)
        
        # Update visibility of shape control based on style
        is_rectangular = (style == 'rectangular')
        for widget in self.minute_tick_shape_widgets:
            widget.set_visible(is_rectangular)
    
    def on_minute_tick_size_changed(self, scale):
        value = scale.get_value()
        self.parent_clock.theme.set('minute_tick_size', value)
        self._on_theme_property_changed('minute_tick_size', value)
    
    def on_minute_tick_shape_changed(self, scale):
        # Convert logarithmic slider value to aspect ratio
        import math
        slider_value = scale.get_value()
        aspect_ratio = math.pow(2, slider_value)
        self._on_theme_property_changed('minute_tick_aspect_ratio', aspect_ratio)
    
    def on_minute_ticks_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('minute_ticks_color', color)
    
    def on_show_numbers_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('show_numbers', value)
        self._update_number_controls_visibility()
    
    def on_show_hour_ticks_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('show_hour_ticks', value)
        self._update_hour_tick_controls_visibility()
    
    def on_show_minute_ticks_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('show_minute_ticks', value)
        self._update_minute_tick_controls_visibility()
    
    def on_number_position_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('number_position', value)
    
    def on_number_size_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('number_size', value)
    
    def on_numbers_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('numbers_color', color)
    
    def on_number_font_changed(self, font_button):
        # Extract just the font family name from the font description
        font_desc = font_button.get_font()
        font_family = font_desc.split()[0] if font_desc else "Sans"
        self._on_theme_property_changed('number_font', font_family)
    
    def on_number_bold_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('number_bold', value)
    
    def on_roman_numerals_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('use_roman_numerals', value)
    
    def on_cardinal_numbers_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('show_cardinal_numbers_only', value)
    
    def on_hour_hand_length_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('hour_hand_length', value)
    
    def on_hour_hand_tail_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('hour_hand_tail', value)
    
    def on_hour_hand_width_changed(self, scale):
        value = scale.get_value()
        # Check if we're in image mode or geometric mode
        source = self.parent_clock.theme.get('hour_hand_image_source')
        if source != 'none':
            # Image mode - save to image_width
            self._on_theme_property_changed('hour_hand_image_width', value)
        else:
            # Geometric mode - save to width
            self._on_theme_property_changed('hour_hand_width', value)
    
    def on_hands_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('hands_color', color)
        
        # Clear hand image cache so colors are regenerated
        self.parent_clock.clear_hand_image_cache()
    
    def on_minute_hand_length_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('minute_hand_length', value)
    
    def on_minute_hand_tail_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('minute_hand_tail', value)
    
    def on_minute_hand_width_changed(self, scale):
        value = scale.get_value()
        # Check if we're in image mode or geometric mode
        source = self.parent_clock.theme.get('minute_hand_image_source')
        if source != 'none':
            # Image mode - save to image_width
            self._on_theme_property_changed('minute_hand_image_width', value)
        else:
            # Geometric mode - save to width
            self._on_theme_property_changed('minute_hand_width', value)
    
    def on_minute_hand_snap_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_settings_property_changed('minute_hand_snap', value)
    
    def on_always_on_top_toggled_dialog(self, switch, gparam):
        value = switch.get_active()
        self._on_settings_property_changed('always_on_top', value)
        self.parent_clock.set_keep_above(value)
    
    def on_second_hand_length_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('second_hand_length', value)
    
    def on_second_hand_tail_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('second_hand_tail', value)
    
    def on_second_hand_width_changed(self, scale):
        value = scale.get_value()
        # Check if we're in image mode or geometric mode
        source = self.parent_clock.theme.get('second_hand_image_source')
        if source != 'none':
            # Image mode - save to image_width
            self._on_theme_property_changed('second_hand_image_width', value)
        else:
            # Geometric mode - save to width
            self._on_theme_property_changed('second_hand_width', value)
    
    def on_second_hand_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('second_hand_color', color)
        
        # Clear hand image cache so colors are regenerated
        self.parent_clock.clear_hand_image_cache()
    
    def on_center_dot_size_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('center_dot_radius', value)
    
    def on_date_box_width_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('date_box_width', value)
    
    def on_date_box_height_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('date_box_height', value)
    
    def on_date_box_margin_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('date_box_margin', value)
        self.parent_clock.update_window_size()
    
    def on_date_font_size_changed(self, scale):
        value = scale.get_value()
        self._on_theme_property_changed('date_font_size', value)
    
    def on_date_format_changed(self, combo):
        format_id = combo.get_active_id()
        if format_id == "custom":
            # Show custom format dialog
            self._show_custom_date_format_dialog()
            # Show edit button
            self.edit_custom_format_button.set_visible(True)
        else:
            # Use predefined format
            self._on_theme_property_changed('date_format', format_id)
            self.custom_date_format = None
            self.parent_clock.queue_draw()
            # Hide edit button
            self.edit_custom_format_button.set_visible(False)
    
    def on_edit_custom_format_clicked(self, button):
        """Handle edit button click for custom format"""
        self._show_custom_date_format_dialog()
    
    def _show_custom_date_format_dialog(self):
        """Show dialog for entering custom date format"""
        import datetime
        
        dialog = Gtk.Dialog(
            title="Custom Date Format",
            parent=self,
            flags=0,
            buttons=(
                Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                Gtk.STOCK_OK, Gtk.ResponseType.OK
            )
        )
        
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        
        # Instructions
        instructions = Gtk.Label()
        instructions.set_markup("<b>Enter a custom date format string</b>\n\nCommon format codes:\n"
                               "%Y = 4-digit year    %y = 2-digit year\n"
                               "%m = month (01-12)   %B = month name    %b = short month\n"
                               "%d = day (01-31)     %A = weekday name  %a = short weekday")
        instructions.set_halign(Gtk.Align.START)
        content.pack_start(instructions, False, False, 0)
        
        # Entry for format string
        entry = Gtk.Entry()
        if self.custom_date_format:
            entry.set_text(self.custom_date_format)
        else:
            entry.set_text(self.parent_clock.theme.get('date_format'))
        entry.set_width_chars(30)
        content.pack_start(entry, False, False, 0)
        
        # Preview label
        preview_label = Gtk.Label()
        preview_label.set_halign(Gtk.Align.START)
        content.pack_start(preview_label, False, False, 0)
        
        def update_preview(*args):
            try:
                now = datetime.datetime.now()
                preview_text = now.strftime(entry.get_text())
                preview_label.set_markup(f"<b>Preview:</b> {preview_text}")
            except Exception as e:
                preview_label.set_markup(f"<b>Preview:</b> <span color='red'>Invalid format</span>")
        
        entry.connect("changed", update_preview)
        update_preview()
        
        dialog.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            custom_format = entry.get_text()
            try:
                # Validate format
                datetime.datetime.now().strftime(custom_format)
                self.custom_date_format = custom_format
                self._on_theme_property_changed('date_format', custom_format)
                self.parent_clock.queue_draw()
            except Exception:
                # Invalid format, revert combo
                if self.custom_date_format:
                    self.date_format_combo.set_active_id("custom")
                else:
                    current_format = self.parent_clock.theme.get('date_format')
                    self.date_format_combo.set_active_id(current_format)
        else:
            # User cancelled, revert combo
            if self.custom_date_format:
                self.date_format_combo.set_active_id("custom")
            else:
                current_format = self.parent_clock.theme.get('date_format')
                self.date_format_combo.set_active_id(current_format)
        
        dialog.destroy()
    
    def on_date_font_changed(self, font_button):
        # Extract just the font family name from the font description
        font_desc = font_button.get_font()
        font_family = font_desc.split()[0] if font_desc else "Sans"
        self._on_theme_property_changed('date_font', font_family)
    
    def on_date_bold_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_theme_property_changed('date_bold', value)
    
    def on_date_text_color_changed(self, button):
        color = self._rgba_to_tuple(button.get_rgba())
        self._on_theme_property_changed('date_text_color', color)
    
    def on_choose_hand_theme_clicked(self, button):
        """Open hand image picker dialog and apply to all hands"""
        selected = self._open_hand_picker('Choose Hand Theme')
        if not selected:
            return
        
        source, name = selected
        
        # Apply to all three hands
        for hand_type in ['hour', 'minute', 'second']:
            self.parent_clock.theme.set(f'{hand_type}_hand_image_source', source)
            self.parent_clock.theme.set(f'{hand_type}_hand_image_name', name)
        
        # Update label
        self.hand_theme_label.set_text(self._format_hand_theme_label())
        
        # Update visibility of controls
        self._update_hand_controls_visibility()
        
        # Clear hand image cache so new hand images are loaded
        self.parent_clock.clear_hand_image_cache()
        
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()
    
    def on_clear_hand_theme_clicked(self, button):
        """Clear hand images for all hands"""
        # Clear all three hands
        for hand_type in ['hour', 'minute', 'second']:
            self.parent_clock.theme.set(f'{hand_type}_hand_image_source', 'none')
            self.parent_clock.theme.set(f'{hand_type}_hand_image_name', None)
        
        # Update label
        self.hand_theme_label.set_text('(none)')
        
        # Update visibility of controls
        self._update_hand_controls_visibility()
        
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()
    
    def on_choose_hand_image_clicked(self, hand_type):
        """Open hand image picker dialog for specified hand type (hour, minute, second)"""
        selected = self._open_hand_picker(f'Choose {hand_type.capitalize()} Hand Image')
        if not selected:
            return
        
        source, name = selected
        self.parent_clock.theme.set(f'{hand_type}_hand_image_source', source)
        self.parent_clock.theme.set(f'{hand_type}_hand_image_name', name)
        
        # Update label
        label_attr = f'{hand_type}_hand_image_label'
        if hasattr(self, label_attr):
            getattr(self, label_attr).set_text(self._format_hand_image_label(hand_type))
        
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()
    
    def on_clear_hand_image_clicked(self, hand_type):
        """Clear hand image for specified hand type"""
        self.parent_clock.theme.set(f'{hand_type}_hand_image_source', 'none')
        self.parent_clock.theme.set(f'{hand_type}_hand_image_name', None)
        
        # Update label
        label_attr = f'{hand_type}_hand_image_label'
        if hasattr(self, label_attr):
            getattr(self, label_attr).set_text('(none)')
        
        self._mark_dirty()
        self._regenerate_current_theme_preview()
        self.parent_clock.queue_draw()
    
    def on_autostart_toggled(self, switch, gparam):
        if switch.get_active():
            self.parent_clock.enable_autostart()
        else:
            self.parent_clock.disable_autostart()
    
    def on_show_date_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_settings_property_changed('show_date_box', value)
        self.parent_clock.update_window_size()
        self.parent_clock.save_geometry()
        self.parent_clock.queue_draw()
    
    def on_show_seconds_toggled(self, switch, gparam):
        value = switch.get_active()
        self._on_settings_property_changed('show_second_hand', value)
        self.parent_clock.save_geometry()
        self.parent_clock.queue_draw()
    
    def _update_hour_tick_controls_visibility(self):
        """Show/hide hour tick controls based on show_hour_ticks_switch"""
        visible = self.show_hour_ticks_switch.get_active()
        for control in self.hour_tick_controls:
            control.set_visible(visible)
        
        # Shape widgets have additional visibility condition (only for rectangular style)
        is_rectangular = self.style_combo.get_active_id() == 'rectangular'
        shape_visible = visible and is_rectangular
        for widget in self.hour_tick_shape_widgets:
            widget.set_visible(shape_visible)
    
    def _update_minute_tick_controls_visibility(self):
        """Show/hide minute tick controls based on show_minute_ticks_switch"""
        visible = self.show_minute_ticks_switch.get_active()
        for control in self.minute_tick_controls:
            control.set_visible(visible)
    
    def _has_hand_images(self):
        """Check if any hand has an image"""
        for hand_type in ['hour', 'minute', 'second']:
            source = self.parent_clock.theme.get(f'{hand_type}_hand_image_source')
            if source != 'none':
                return True
        return False
    
    def _recolor_hand_images(self):
        """Recolor hand images in memory based on selected colors"""
        from PIL import Image
        import io
        
        # Get colors
        hands_color = self.parent_clock.theme.get('hands_color')
        second_hand_color = self.parent_clock.theme.get('second_hand_color')
        
        # Initialize recolored images dict if not exists
        if not hasattr(self.parent_clock, 'recolored_hand_images'):
            self.parent_clock.recolored_hand_images = {}
        
        # Recolor each hand
        for hand_type in ['hour', 'minute', 'second']:
            source = self.parent_clock.theme.get(f'{hand_type}_hand_image_source')
            name = self.parent_clock.theme.get(f'{hand_type}_hand_image_name')
            
            if source == 'none' or not name:
                # Clear recolored image if hand image is not set
                if hand_type in self.parent_clock.recolored_hand_images:
                    del self.parent_clock.recolored_hand_images[hand_type]
                continue
            
            # Get original image path
            if source == 'builtin':
                base_dir = os.path.join(os.path.dirname(__file__), 'assets', 'hands', name)
            else:  # user
                base_dir = os.path.join(self.parent_clock.get_user_hands_dir(), name)
            
            # Try processed first, fall back to original
            processed_path = os.path.join(base_dir, 'processed', f'{hand_type}.png')
            original_path = os.path.join(base_dir, 'original', f'{hand_type}.png')
            
            if os.path.exists(processed_path):
                image_path = processed_path
            elif os.path.exists(original_path):
                image_path = original_path
            else:
                # No image found
                if hand_type in self.parent_clock.recolored_hand_images:
                    del self.parent_clock.recolored_hand_images[hand_type]
                continue
            
            # Load image
            try:
                img = Image.open(image_path).convert('RGBA')
                pixels = img.load()
                
                # Find and remember the red pixel (rotation center) position
                red_pixel_pos = None
                for y in range(img.height):
                    for x in range(img.width):
                        r, g, b, a = pixels[x, y]
                        if r == 255 and g == 0 and b == 0:
                            red_pixel_pos = (x, y)
                            break
                    if red_pixel_pos:
                        break
                
                # Determine which color to use
                if hand_type == 'second':
                    target_color = second_hand_color
                else:  # hour or minute
                    target_color = hands_color
                
                # Convert color from 0-1 range to 0-255 range
                target_r = int(target_color[0] * 255)
                target_g = int(target_color[1] * 255)
                target_b = int(target_color[2] * 255)
                
                # Recolor: replace black pixels with target color, preserve transparency
                # Also preserve the red pixel by skipping it
                for y in range(img.height):
                    for x in range(img.width):
                        # Skip the red pixel - don't recolor it
                        if red_pixel_pos and (x, y) == red_pixel_pos:
                            continue
                        
                        r, g, b, a = pixels[x, y]
                        
                        # Only recolor fully opaque pure black pixels
                        # This avoids recoloring anti-aliased edges which would make the hand appear thicker
                        if a == 255 and r == 0 and g == 0 and b == 0:
                            pixels[x, y] = (target_r, target_g, target_b, a)
                
                # Store recolored image as pixbuf
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                buffer.seek(0)
                
                loader = GdkPixbuf.PixbufLoader.new_with_type('png')
                loader.write(buffer.read())
                loader.close()
                pixbuf = loader.get_pixbuf()
                
                self.parent_clock.recolored_hand_images[hand_type] = pixbuf
                
                # Store red pixel position for rendering to use
                if not hasattr(self.parent_clock, 'hand_red_pixel_positions'):
                    self.parent_clock.hand_red_pixel_positions = {}
                if red_pixel_pos:
                    self.parent_clock.hand_red_pixel_positions[hand_type] = red_pixel_pos
                
            except Exception as e:
                print(f"Error recoloring {hand_type} hand image: {e}")
                if hand_type in self.parent_clock.recolored_hand_images:
                    del self.parent_clock.recolored_hand_images[hand_type]
    
    def _update_number_controls_visibility(self):
        """Show/hide number controls based on show_numbers_switch"""
        visible = self.show_numbers_switch.get_active()
        for control in self.number_controls:
            control.set_visible(visible)
