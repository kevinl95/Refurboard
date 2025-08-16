"""
Calibration module for Refurboard - handles screen boundary calibration
"""

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
        margin = 50  # Distance from edge
        
        # Use the full system screen size, not the window size
        screen_width, screen_height = Window.system_size
        
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
        self.server = server
        self.callback = callback
        
        # Make this widget fullscreen
        self.size = Window.system_size
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
        self.start_calibration()
    
    def setup_ui(self):
        """Set up the calibration UI"""
        # Main layout positioned at the center with fixed positioning
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20,
                          size_hint=(None, None), size=(600, 300),
                          pos_hint={'center_x': 0.5, 'center_y': 0.5})
        
        # Instructions with dark background for visibility
        self.instruction_label = Label(
            text='Calibration: Point LED at the target and wait',
            size_hint=(1, None), height=80,
            color=(0, 0, 0, 1),  # Black text
            font_size=28,
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
        
        # Cancel button
        cancel_button = Button(
            text='Cancel Calibration',
            size_hint=(None, None), size=(200, 60),
            pos_hint={'center_x': 0.5},
            background_color=(0.8, 0.2, 0.2, 1),  # Red background
            font_size=16
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
            self.instruction_label.text = f'Point LED at: {step_name}'
            self.progress_label.text = f'Step {self.current_step + 1} of {len(self.steps)}'
            
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
        
        if time.time() - self.step_start_time > 3:  # Wait 3 seconds per target
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
        
        return True
    
    def finish_calibration(self):
        """Complete the calibration process"""
        Clock.unschedule(self.check_led_position)
        
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
        Clock.unschedule(self.check_led_position)
        self.callback(None)


class CalibrationManager:
    """Manages the calibration process"""
    
    @staticmethod
    def start_calibration(server, parent_widget, callback):
        """Start calibration process"""
        # Store the original window state
        original_window = Window.fullscreen
        
        # Make window fullscreen for calibration
        Window.fullscreen = 'auto'
        
        def calibration_callback(calibration_data):
            # Restore original window state
            Window.fullscreen = original_window
            callback(calibration_data)
        
        calibration_screen = CalibrationScreen(server, calibration_callback)
        parent_widget.add_widget(calibration_screen)
        return calibration_screen
    
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
