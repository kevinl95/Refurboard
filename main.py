#!/usr/bin/env python3
"""
Refurboard - Turn any old smartphone into an interactive whiteboard

Refactored main entry point using modular architecture.
"""

import time
import random
import ssl
import numpy as np
from threading import Thread

from kivy.app import App
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.core.window import Window

from refurboard.utils.network import get_ip_address, generate_qr_code
from refurboard.utils.mouse_control import move_mouse, is_mouse_control_available
from refurboard.server.flask_app import RefurboardServer
from refurboard.server.ssl_utils import generate_self_signed_cert
from refurboard.ui.calibration import CalibrationManager


class RefurboardApp(App):
    """Main Kivy application for Refurboard"""
    
    def build(self):
        self.icon = 'assets/logo.png'
        self.layout = BoxLayout(orientation='vertical')
        self.layout.canvas.before.clear()

        # Parameters
        self.ip_address = ''
        self.calibrated = False
        
        # Calibration coordinates (will be set during calibration)
        self.upperLeftX = 0
        self.upperLeftY = 0
        self.upperRightX = 0
        self.upperRightY = 0
        self.lowerLeftX = 0
        self.lowerLeftY = 0
        self.lowerRightX = 0
        self.lowerRightY = 0
        
        # LED detection parameters (configurable)
        self.brightness_threshold = 240
        self.min_area = 10
        self.max_area = 500
        self.circularity_threshold = 0.3
        self.min_brightness = 200
        
        # Initialize server
        self.server = RefurboardServer()
        
        # Start mouse position thread
        self.mouse_position_thread = Thread(target=self.update_mouse_position)
        self.mouse_position_thread.daemon = True
        self.mouse_position_thread.start()

        # Build UI
        self._build_ui()
        
        # Bind the window close event
        Window.bind(on_request_close=self.on_request_close)
        
        return self.layout
    
    def _build_ui(self):
        """Build the main user interface"""
        # Add the logo image
        self.logo = Image(source='assets/logo.png', size_hint=(None, None), 
                         size=(200, 200), pos_hint={'center_x': 0.5, 'top': 1})
        self.layout.add_widget(self.logo)
        
        # Add the status label
        self.status_label = Label(text='Client disconnected', color=(1, 0, 0, 1))
        self.layout.add_widget(self.status_label)
        
        # Add LED tracking status label
        self.led_status_label = Label(text='LED tracking: Waiting for calibration', color=(0.5, 0.5, 0.5, 1))
        self.layout.add_widget(self.led_status_label)

        self.label = Label(text='Starting Refurboard server...', color=(0, 0, 0, 1))
        self.layout.add_widget(self.label)
        
        self.qr_image = Image()
        self.layout.add_widget(self.qr_image)
        
        # Add buttons
        self.calibrate_button = Button(text='Calibrate', size_hint=(None, None), 
                                     size=(200, 50), pos_hint={'center_x': 0.5})
        self.calibrate_button.bind(on_press=self.show_calibration_screen)
        self.layout.add_widget(self.calibrate_button)
        
        self.settings_button = Button(text='Settings', size_hint=(None, None), 
                                    size=(200, 50), pos_hint={'center_x': 0.5})
        self.settings_button.bind(on_press=self.show_settings_menu)
        self.layout.add_widget(self.settings_button)
        
        # Schedule server start and status updates
        Clock.schedule_once(self.start_server, 1)
        Clock.schedule_interval(self.update_status, 1)
        
        # Set background color
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
    
    def on_request_close(self, *args):
        """Handle window close request"""
        self.stop()
        return False
    
    def on_stop(self):
        """Called when the app is closing"""
        print("Refurboard application closing...")
        return True
    
    def update_mouse_position(self):
        """Update mouse position based on LED tracking"""
        while True:
            if self.calibrated:
                position = self.server.get_current_position()
                cX, cY = position['x'], position['y']
                
                # Update LED status on UI thread
                Clock.schedule_once(lambda dt: self.update_led_status(cX, cY), 0)
                
                # Check if LED is within calibrated bounds
                if self.is_led_in_bounds(cX, cY):
                    screen_width, screen_height = Window.system_size
                    screen_x = np.interp(cX, [self.upperLeftX, self.upperRightX], [0, screen_width])
                    screen_y = np.interp(cY, [self.upperLeftY, self.lowerLeftY], [0, screen_height])
                    move_mouse(screen_x, screen_y)
                # If LED is out of bounds, don't move the mouse
            time.sleep(0.1)
    
    def update_led_status(self, x, y):
        """Update LED status label on UI thread"""
        if not self.calibrated:
            self.led_status_label.text = 'LED tracking: Waiting for calibration'
            self.led_status_label.color = (0.5, 0.5, 0.5, 1)
        elif x == 0 and y == 0:
            self.led_status_label.text = 'LED tracking: No LED detected'
            self.led_status_label.color = (1, 0.5, 0, 1)  # Orange
        elif self.is_led_in_bounds(x, y):
            self.led_status_label.text = f'LED tracking: Active (x={x:.0f}, y={y:.0f})'
            self.led_status_label.color = (0, 1, 0, 1)  # Green
        else:
            self.led_status_label.text = f'LED tracking: Out of bounds (x={x:.0f}, y={y:.0f})'
            self.led_status_label.color = (1, 0, 0, 1)  # Red
    
    def is_led_in_bounds(self, x, y):
        """Check if LED position is within the calibrated rectangle"""
        if not self.calibrated:
            return False
        
        # Define the calibrated rectangle bounds
        min_x = min(self.upperLeftX, self.lowerLeftX)
        max_x = max(self.upperRightX, self.lowerRightX)
        min_y = min(self.upperLeftY, self.upperRightY)
        max_y = max(self.lowerLeftY, self.lowerRightY)
        
        # Add a small tolerance margin to avoid edge issues
        tolerance = 10
        return (min_x - tolerance <= x <= max_x + tolerance and 
                min_y - tolerance <= y <= max_y + tolerance)

    def _update_rect(self, instance, _):
        """Update background rectangle size"""
        self.rect.size = instance.size

    def start_server(self, _):
        """Start the Flask server"""
        self.ip_address = get_ip_address()
        port = random.randint(1024, 65535)
        self.base_url = f"https://{self.ip_address}:{port}"
        self.label.text = f"HTTPS server running at {self.base_url}"
        
        # Generate QR code
        qr_url = f"{self.base_url}/index.html?server={self.base_url}"
        self.qr_image.texture = generate_qr_code(qr_url)

        # Generate SSL certificate
        cert_file = "server.crt"
        key_file = "server.key"
        generate_self_signed_cert(self.ip_address, cert_file, key_file)

        # Setup SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)

        # Start server in background thread
        thread = Thread(
            target=lambda: self.server.run(
                host=self.ip_address, 
                port=port, 
                ssl_context=context, 
                use_reloader=False
            )
        )
        thread.daemon = True
        thread.start()

    def update_status(self, _dt):
        """Update connection status"""
        if self.server.is_client_connected():
            self.status_label.text = 'Client connected'
            self.status_label.color = (0, 1, 0, 1)
        else:
            self.status_label.text = 'Client disconnected'
            self.status_label.color = (1, 0, 0, 1)

    def show_calibration_screen(self, _instance):
        """Show calibration screen"""
        def on_calibration_complete(calibration_data):
            # Remove calibration screen
            for child in self.layout.children[:]:
                if hasattr(child, '__class__') and 'Calibration' in child.__class__.__name__:
                    self.layout.remove_widget(child)
            
            # Apply calibration if successful
            if CalibrationManager.apply_calibration(self, calibration_data):
                print("Calibration successful!")
            else:
                print("Calibration failed or cancelled")
            
            # Rebuild main screen
            self.rebuild_main_screen()
        
        # Start calibration
        CalibrationManager.start_calibration(self.server, self.layout, on_calibration_complete)

    def show_settings_menu(self, _instance):
        """Show settings menu (simplified for now)"""
        # TODO: Move settings logic to separate module
        print("Settings feature - to be implemented in separate module")

    def rebuild_main_screen(self):
        """Rebuild the main screen after calibration/settings"""
        qr_url = f"{self.base_url}/index.html?server={self.ip_address}"
        self.qr_image.texture = generate_qr_code(qr_url)
        
        self.layout.clear_widgets()
        self.layout.add_widget(self.logo)
        self.layout.add_widget(self.status_label)
        self.layout.add_widget(self.led_status_label)
        self.layout.add_widget(self.label)
        self.layout.add_widget(self.qr_image)
        self.layout.add_widget(self.calibrate_button)
        self.layout.add_widget(self.settings_button)


if __name__ == '__main__':
    RefurboardApp().run()
