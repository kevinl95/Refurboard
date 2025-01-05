import socket
import random
import qrcode
import base64
import cv2
import numpy as np
import urllib.parse
from io import BytesIO
from flask import Flask, jsonify, request, send_from_directory
from threading import Thread
from kivy.app import App
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock
from kivy.core.window import Window

app = Flask(__name__, static_folder='client')

class RefurboardApp(App):
    def build(self):
        self.icon = 'assets/logo.png'  # Set the application icon
        self.layout = BoxLayout(orientation='vertical')
        self.layout.canvas.before.clear()

        # Parameters
        self.ip_address = ''
        
        # Add the logo image
        self.logo = Image(source='assets/logo.png', size_hint=(None, None), size=(200, 200), pos_hint={'center_x': 0.5, 'top': 1})
        self.layout.add_widget(self.logo)
        
        self.label = Label(text='Starting Refurboard server...', color=(0, 0, 0, 1))  # Set label text color to black
        self.layout.add_widget(self.label)
        self.qr_image = Image()
        self.layout.add_widget(self.qr_image)
        
        # Add the Calibrate button
        self.calibrate_button = Button(text='Calibrate', size_hint=(None, None), size=(200, 50), pos_hint={'center_x': 0.5})
        self.calibrate_button.bind(on_press=self.show_calibration_screen)
        self.layout.add_widget(self.calibrate_button)
        
        # Add the Settings button
        self.settings_button = Button(text='Settings', size_hint=(None, None), size=(200, 50), pos_hint={'center_x': 0.5})
        self.settings_button.bind(on_press=self.show_settings_menu)
        self.layout.add_widget(self.settings_button)
        
        Clock.schedule_once(self.start_server, 1)
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)  # Set the background color to white
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
        
        return self.layout

    def _update_rect(self, instance, _):
        self.rect.size = instance.size

    def rebuild_main_screen(self):
        self.generate_qr_code(urllib.parse.urljoin(self.base_url, 'index.html?server=' + self.ip_address))
        self.layout.clear_widgets()  # Clear the existing widgets
        self.layout.add_widget(self.logo)
        self.layout.add_widget(self.label)
        self.layout.add_widget(self.qr_image)
        self.layout.add_widget(self.calibrate_button)
        self.layout.add_widget(self.settings_button)

    def get_ip_address(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            s.connect(('10.254.254.254', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def start_server(self, _):
        self.ip_address = self.get_ip_address()
        port = random.randint(1024, 65535)  # Choose a random port between 1024 and 65535
        self.base_url = f"http://{self.ip_address}:{port}"
        self.label.text = f"HTTP server running at {self.base_url}"
        self.generate_qr_code(f"{self.base_url}/index.html?server={self.base_url}")
        thread = Thread(target=app.run, kwargs={'host': self.ip_address, 'port': port})
        thread.start()

    def generate_qr_code(self, data):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        self.qr_image.texture = CoreImage(buffer, ext='png').texture

    def _update_lines(self, instance, value):
        self.line1.points = [50, Window.height - 50, 100, Window.height - 100]
        self.line2.points = [50, Window.height - 100, 100, Window.height - 50]

    def show_calibration_screen(self, instance):
        self.layout.clear_widgets()  # Clear the existing widgets
        # Make the window full screen
        Window.fullscreen = 'auto'
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)  # Set the color to white
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Add the calibration instruction label
        self.calibration_label = Label(text='Use your LED pen on each target as it appears.', color=(0, 0, 0, 1), font_size='20sp', halign='center', valign='middle')
        self.layout.add_widget(self.calibration_label)
        
        with self.layout.canvas:
            Color(1, 0, 0, 1)  # Set the color to red
            # Draw a red X target in the top left corner
            self.line1 = Line(points=[50, Window.height - 50, 100, Window.height - 100], width=2)
            self.line2 = Line(points=[50, Window.height - 100, 100, Window.height - 50], width=2)
            self.layout.bind(size=self._update_lines, pos=self._update_lines)
    
        self._update_rect(self.layout, None)

    def show_settings_menu(self, instance):
        self.layout.clear_widgets()  # Clear the existing widgets
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)  # Set the color to white
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Add the settings instruction label
        self.settings_label = Label(text='Enter the base URL for the QR code:', color=(0, 0, 0, 1), font_size='20sp', halign='center', valign='middle')
        self.layout.add_widget(self.settings_label)
        
        # Add the TextInput for the base URL
        self.url_input = TextInput(text=self.base_url, multiline=False, size_hint=(None, None), size=(400, 50), pos_hint={'center_x': 0.5})
        self.layout.add_widget(self.url_input)
        
        # Add the Save button
        self.save_button = Button(text='Save', size_hint=(None, None), size=(200, 50), pos_hint={'center_x': 0.5})
        self.save_button.bind(on_press=self.save_settings)
        self.layout.add_widget(self.save_button)

    def save_settings(self, instance):
        self.base_url = self.url_input.text
        self.rebuild_main_screen()

@app.route('/ip')
def get_ip():
    return jsonify('127.0.0.1')

@app.route('/stream', methods=['POST'])
def stream():
    data = request.json
    image_data = base64.b64decode(data['image'])
    nparr = np.frombuffer(image_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Convert the frame to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Threshold the image to get the LED
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        # Get the largest contour
        c = max(contours, key=cv2.contourArea)
        # Get the center of the contour
        M = cv2.moments(c)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            # Send the coordinates back to the client or use them as needed
            return jsonify({'x': cX, 'y': cY})

    return jsonify({'error': 'LED not found'})

@app.route('/')
@app.route('/<path:path>')
def serve_static(path='index.html'):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    RefurboardApp().run()