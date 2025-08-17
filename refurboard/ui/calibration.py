"""
Calibration module for Refurboard - handles screen boundary calibration
"""

import time
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.core.window import Window
from kivy.clock import Clock
import time


class CalibrationTarget(Widget):
    """A target widget shown at screen corners during calibration"""
    
    def __init__(self, position='center', **kwargs):
        super().__init__(**kwargs)
        self.position = position
        self.target_size = 50
        self.is_active = False
        
        # Bind to window size changes
        Window.bind(size=self.update_position)
        Clock.schedule_once(self.update_position, 0)
    
    def update_position(self, *args):
        """Update target position based on screen location"""
        margin = 20  # Small margin from actual edge for visibility
        
        # Use the full window size (which should now be maximized to screen size)
        try:
            screen_width, screen_height = Window.size
            print(f"Target positioning using full window size: {Window.size}")
        except Exception as e:
            print(f"Warning: Could not get window size: {e}")
            screen_width, screen_height = (1200, 800)  # Fallback size
        
        if self.position == 'top_left':
            self.pos = (margin, screen_height - margin - self.target_size)
        elif self.position == 'top_right':
            self.pos = (screen_width - margin - self.target_size, screen_height - margin - self.target_size)
        elif self.position == 'bottom_left':
            self.pos = (margin, margin)
        elif self.position == 'bottom_right':
            self.pos = (screen_width - margin - self.target_size, margin)
        else:  # center
            self.pos = ((screen_width - self.target_size) / 2, (screen_height - self.target_size) / 2)
        
        self.size = (self.target_size, self.target_size)
        self.draw_target()
    
    def draw_target(self):
        """Draw the calibration target"""
        self.canvas.clear()
        with self.canvas:
            if self.is_active:
                Color(1, 0, 0, 1)  # Red when active
            else:
                Color(0, 1, 0, 1)  # Green when inactive
            
            # Draw circle
            Ellipse(pos=self.pos, size=self.size)
            
            # Draw crosshairs
            Color(1, 1, 1, 1)  # White crosshairs
            center_x = self.pos[0] + self.size[0] / 2
            center_y = self.pos[1] + self.size[1] / 2
            
            # Horizontal line
            Line(points=[center_x - 15, center_y, center_x + 15, center_y], width=2)
            # Vertical line
            Line(points=[center_x, center_y - 15, center_x, center_y + 15], width=2)
    
    def activate(self):
        """Activate this target (turn red)"""
        self.is_active = True
        self.draw_target()
    
    def deactivate(self):
        """Deactivate this target (turn green)"""
        self.is_active = False
        self.draw_target()


class CalibrationScreen(Widget):
    """Full screen calibration interface"""
    
    def __init__(self, server, callback, **kwargs):
        super().__init__(**kwargs)
        print("Initializing CalibrationScreen...")
        self.server = server
        self.callback = callback
        
        # Make this widget fill the entire window
        try:
            self.size = Window.size
            print(f"Using full window size: {Window.size}")
        except Exception as e:
            print(f"Error getting window size: {e}")
            self.size = (1200, 800)  # Fallback size
        self.pos = (0, 0)
        
        # Calibration state
        self.current_step = 0
        self.calibration_points = {}
        self.targets = []
        self.steps = ['top_left', 'top_right', 'bottom_left', 'bottom_right']
        self.step_names = {
            'top_left': 'Top Left Corner',
            'top_right': 'Top Right Corner', 
            'bottom_left': 'Bottom Left Corner',
            'bottom_right': 'Bottom Right Corner'
        }
        
        # Set up UI
        self.setup_ui()
        
        # Bind to window size changes to keep calibration screen full size
        Window.bind(size=self.on_window_size_change)
        
        self.start_calibration()
    
    def on_window_size_change(self, instance, size):
        """Handle window size change during calibration"""
        try:
            width, height = size
            print(f"CalibrationScreen: Window size changed to: {width}x{height}")
            self.size = (width, height)
            
            # Reposition targets for new window size
            for target in self.targets:
                target.calculate_position()
                print(f"Target {target.position} repositioned to: {target.pos}")
        except Exception as e:
            print(f"Error handling window size change: {e}")
    
    def setup_ui(self):
        """Set up the calibration UI"""
        # Main layout positioned at the center with fixed positioning
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20,
                          size_hint=(None, None), size=(600, 300),
                          pos_hint={'center_x': 0.5, 'center_y': 0.5})
        
        # Instructions with dark background for visibility
        self.instruction_label = Label(
            text='Screen Corner Calibration: Connect your phone, then point LED at each corner target. This maps the phone camera view to screen coordinates.',
            size_hint=(1, None), height=120,
            color=(0, 0, 0, 1),  # Black text
            font_size=22,
            bold=True,
            halign='center',
            valign='middle',
            text_size=(560, None)  # Enable text wrapping
        )
        self.instruction_label.bind(texture_size=self.instruction_label.setter('text_size'))
        layout.add_widget(self.instruction_label)
        
        # Progress label
        self.progress_label = Label(
            text='',
            size_hint=(1, None), height=60,
            color=(0, 0, 0, 1),  # Black text
            font_size=20,
            halign='center',
            valign='middle',
            text_size=(560, None)  # Enable text wrapping
        )
        self.progress_label.bind(texture_size=self.progress_label.setter('text_size'))
        layout.add_widget(self.progress_label)
        
        # Cancel button - smaller and less prominent
        cancel_button = Button(
            text='Cancel',
            size_hint=(None, None), size=(120, 40),
            pos_hint={'center_x': 0.5},
            background_color=(0.6, 0.6, 0.6, 1),  # Gray background  
            font_size=14
        )
        cancel_button.bind(on_press=self.cancel_calibration)
        layout.add_widget(cancel_button)
        
        # Add a semi-transparent background for the UI elements with rounded corners
        with layout.canvas.before:
            Color(1, 1, 1, 0.95)  # More opaque white background
            self.ui_bg = Rectangle(pos=layout.pos, size=layout.size)
            Color(0, 0, 0, 0.3)  # Dark border
            Line(rectangle=(layout.x, layout.y, layout.width, layout.height), width=2)
        
        layout.bind(pos=self.update_ui_bg, size=self.update_ui_bg)
        
        self.add_widget(layout)
        
        # Create targets
        for position in self.steps:
            target = CalibrationTarget(position=position)
            self.targets.append(target)
            self.add_widget(target)
        
        # Set fullscreen white background
        with self.canvas.before:
            Color(1, 1, 1, 1)  # Pure white background
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        
        self.bind(size=self.update_bg, pos=self.update_bg)
    
    def update_bg(self, *args):
        """Update background rectangle"""
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = self.pos
            self.bg_rect.size = self.size
    
    def update_ui_bg(self, instance, *args):
        """Update UI background rectangle"""
        if hasattr(self, 'ui_bg'):
            self.ui_bg.pos = instance.pos
            self.ui_bg.size = instance.size
            
            # Update border if it exists
            if hasattr(instance, 'canvas') and len(instance.canvas.before.children) > 3:
                # Find and update the border line
                for instruction in instance.canvas.before.children:
                    if hasattr(instruction, 'rectangle'):
                        instruction.rectangle = (instance.x, instance.y, instance.width, instance.height)
    
    def start_calibration(self):
        """Start the calibration process"""
        self.current_step = 0
        self.calibration_points = {}
        self.update_instruction()
        Clock.schedule_interval(self.check_led_position, 0.1)
    
    def update_instruction(self):
        """Update instruction text"""
        if self.current_step < len(self.steps):
            step_name = self.step_names[self.steps[self.current_step]]
            
            # Check if client is connected
            if hasattr(self.server, 'is_client_connected') and not self.server.is_client_connected():
                self.instruction_label.text = f'Step {self.current_step + 1}: Please connect your phone first, then point LED at: {step_name}'
                self.progress_label.text = 'Waiting for phone connection...'
            else:
                self.instruction_label.text = f'Step {self.current_step + 1}: Point LED at: {step_name}'
                self.progress_label.text = f'Step {self.current_step + 1} of {len(self.steps)} - Hold LED steady for 3 seconds'
            
            # Activate current target
            for i, target in enumerate(self.targets):
                if i == self.current_step:
                    target.activate()
                else:
                    target.deactivate()
        else:
            self.finish_calibration()
    
    def check_led_position(self, dt):
        """Check if LED is positioned at current target"""
        if self.current_step >= len(self.steps):
            return False
        
        try:
            # Get current LED position from server
            position = self.server.get_current_position()
            if position['x'] == 0 and position['y'] == 0:
                return True  # No LED detected yet
            
            # Check if LED has been stable at target for enough time
            current_target = self.targets[self.current_step]
            target_center_x = current_target.pos[0] + current_target.size[0] / 2
            target_center_y = current_target.pos[1] + current_target.size[1] / 2
            
            # For now, we'll use a simple timeout - in a real implementation,
            # you'd check if the LED position corresponds to the target location
            if not hasattr(self, 'step_start_time'):
                self.step_start_time = time.time()
            
            elapsed_time = time.time() - self.step_start_time
            
            if elapsed_time > 3:  # Wait 3 seconds per target
                # Record the calibration point
                step_name = self.steps[self.current_step]
                self.calibration_points[step_name] = {
                    'led_x': position['x'],
                    'led_y': position['y'],
                    'screen_x': target_center_x,
                    'screen_y': target_center_y
                }
                
                # Move to next step
                self.current_step += 1
                self.step_start_time = time.time()
                self.update_instruction()
        except Exception as e:
            print(f"Error in calibration LED check: {e}")
            # Continue anyway, don't crash calibration
        
        return True
    
    def finish_calibration(self):
        """Complete the calibration process"""
        # Clean up scheduled events
        Clock.unschedule(self.check_led_position)
        
        # Clean up window bindings
        try:
            Window.unbind(size=self.on_window_size_change)
            Window.unbind(size=self.update_bg, pos=self.update_bg)
        except:
            pass
        
        # Calculate calibration parameters
        if len(self.calibration_points) == 4:
            calibration_data = {
                'upperLeftX': self.calibration_points['top_left']['led_x'],
                'upperLeftY': self.calibration_points['top_left']['led_y'],
                'upperRightX': self.calibration_points['top_right']['led_x'],
                'upperRightY': self.calibration_points['top_right']['led_y'],
                'lowerLeftX': self.calibration_points['bottom_left']['led_x'],
                'lowerLeftY': self.calibration_points['bottom_left']['led_y'],
                'lowerRightX': self.calibration_points['bottom_right']['led_x'],
                'lowerRightY': self.calibration_points['bottom_right']['led_y'],
                'calibrated': True
            }
            
            self.instruction_label.text = 'Calibration Complete!'
            self.progress_label.text = 'Returning to main screen...'
            
            # Return calibration data
            Clock.schedule_once(lambda dt: self.callback(calibration_data), 2)
        else:
            self.instruction_label.text = 'Calibration Failed!'
            self.progress_label.text = 'Not enough points captured'
            Clock.schedule_once(lambda dt: self.callback(None), 3)
    
    def cancel_calibration(self, instance):
        """Cancel the calibration process"""
        # Clean up scheduled events
        Clock.unschedule(self.check_led_position)
        
        # Clean up window bindings
        try:
            Window.unbind(size=self.on_window_size_change)
            Window.unbind(size=self.update_bg, pos=self.update_bg)
        except:
            pass
            
        self.callback(None)


class CalibrationManager:
    """Manages the calibration process"""
    
    @staticmethod
    def start_calibration(server, parent_widget, callback):
        """Start calibration process"""
        print("Starting calibration with maximized window...")
        
        def calibration_callback(calibration_data):
            # Restore window to normal size after calibration
            try:
                print("Restoring window to normal size...")
                Window.size = (800, 600)
                Window.left = 100
                Window.top = 100
            except Exception as e:
                print(f"Error restoring window size: {e}")
            
            callback(calibration_data)
        
        try:
            # Maximize window to fill screen (safer than fullscreen mode)
            print("Maximizing window for calibration...")
            try:
                # Get actual screen size - try multiple methods
                screen_width, screen_height = Window.system_size
                print(f"System size reported: {screen_width}x{screen_height}")
                
                # If system_size doesn't give us full screen, try alternative approaches
                if screen_width <= 800 or screen_height <= 600:
                    print("System size seems too small, trying alternative methods...")
                    
                    # Try to get screen size from environment or use common resolutions
                    import os
                    if 'DISPLAY' in os.environ:
                        try:
                            # Try to get screen resolution using xrandr if available
                            import subprocess
                            result = subprocess.run(['xrandr'], capture_output=True, text=True, timeout=2)
                            if result.returncode == 0:
                                for line in result.stdout.split('\n'):
                                    if ' connected primary' in line or ' connected' in line:
                                        parts = line.split()
                                        for part in parts:
                                            if 'x' in part and part.replace('x', '').replace('+', '').replace('-', '').isdigit():
                                                w, h = part.split('x')[0], part.split('x')[1].split('+')[0].split('-')[0]
                                                if w.isdigit() and h.isdigit():
                                                    screen_width, screen_height = int(w), int(h)
                                                    print(f"Got screen size from xrandr: {screen_width}x{screen_height}")
                                                    break
                                        break
                        except:
                            pass
                    
                    # Fallback to common resolutions if still too small
                    if screen_width <= 800 or screen_height <= 600:
                        screen_width, screen_height = 1920, 1080  # Common default
                        print(f"Using fallback resolution: {screen_width}x{screen_height}")
                
                # Set window to full screen size
                print(f"Setting window size to: {screen_width}x{screen_height}")
                Window.size = (screen_width, screen_height)
                Window.left = 0
                Window.top = 0
                
                # Force window update
                Window.dispatch('on_resize', screen_width, screen_height)
                
                print(f"Window maximized to: {Window.size}")
                
                # Give window time to resize
                import time
                time.sleep(0.1)
            except Exception as e:
                print(f"Error maximizing window: {e}")
                # Fallback to large window
                Window.size = (1920, 1080)
                Window.left = 0
                Window.top = 0
            
            print("Creating calibration screen...")
            calibration_screen = CalibrationScreen(server, calibration_callback)
            
            # Make sure calibration screen matches the new window size
            calibration_screen.size = Window.size
            calibration_screen.pos = (0, 0)
            
            print("Adding calibration screen to parent widget...")
            parent_widget.add_widget(calibration_screen)
            print("Calibration screen setup complete")
            return calibration_screen
        except Exception as e:
            print(f"Error in start_calibration: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    @staticmethod
    def apply_calibration(app_instance, calibration_data):
        """Apply calibration data to app instance"""
        if calibration_data and calibration_data.get('calibrated'):
            app_instance.upperLeftX = calibration_data['upperLeftX']
            app_instance.upperLeftY = calibration_data['upperLeftY'] 
            app_instance.upperRightX = calibration_data['upperRightX']
            app_instance.upperRightY = calibration_data['upperRightY']
            app_instance.lowerLeftX = calibration_data['lowerLeftX']
            app_instance.lowerLeftY = calibration_data['lowerLeftY']
            app_instance.lowerRightX = calibration_data['lowerRightX']
            app_instance.lowerRightY = calibration_data['lowerRightY']
            app_instance.calibrated = True
            return True
        return False
