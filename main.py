import socket
import random
import qrcode
import base64
import cv2
import numpy as np
import urllib.parse
import ssl
import time
import pyautogui
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
from OpenSSL import crypto

app = Flask(__name__, static_folder='client')
pyautogui.FAILSAFE = False

# Add this line to track the last time the stream function was called
last_stream_time = 0
cX = 0
cY = 0

class RefurboardApp(App):
    def build(self):
        self.icon = 'assets/logo.png'  # Set the application icon
        self.layout = BoxLayout(orientation='vertical')
        self.layout.canvas.before.clear()

        # Parameters
        self.ip_address = ''
        self.calibrated = False
        
        # LED detection parameters (configurable)
        self.brightness_threshold = 240
        self.min_area = 10
        self.max_area = 500
        self.circularity_threshold = 0.3
        self.min_brightness = 200
        
        self.mouse_position_thread = Thread(target=self.update_mouse_position)
        self.mouse_position_thread.daemon = True
        self.mouse_position_thread.start()

        # Add the logo image
        self.logo = Image(source='assets/logo.png', size_hint=(None, None), size=(200, 200), pos_hint={'center_x': 0.5, 'top': 1})
        self.layout.add_widget(self.logo)
        
        # Add the status label
        self.status_label = Label(text='Client disconnected', color=(1, 0, 0, 1))  # Set label text color to red
        self.layout.add_widget(self.status_label)
        
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
        Clock.schedule_interval(self.update_status, 1)  # Check the status every second
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)  # Set the background color to white
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
        
        return self.layout
    
    def update_mouse_position(self):
        global cX
        global cY
        while True:
            if self.calibrated:
                screen_width, screen_height = Window.system_size
                # Map cX and cY to the screen coordinates
                screen_x = np.interp(cX, [self.upperLeftX, self.upperRightX], [0, screen_width])
                screen_y = np.interp(cY, [self.upperLeftY, self.lowerLeftY], [0, screen_height])
                # Set the mouse position
                pyautogui.moveTo(screen_x, screen_y)
            time.sleep(0.1)

    def _update_rect(self, instance, _):
        self.rect.size = instance.size

    def rebuild_main_screen(self):
        self.generate_qr_code(urllib.parse.urljoin(self.base_url, 'index.html?server=' + self.ip_address))
        self.layout.clear_widgets()  # Clear the existing widgets
        self.layout.add_widget(self.logo)
        self.layout.add_widget(self.status_label)
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

    def generate_self_signed_cert(self, hostname, cert_file, key_file):
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)

        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "California"
        cert.get_subject().L = "San Francisco"
        cert.get_subject().O = "Refurboard"
        cert.get_subject().OU = "Refurboard"
        cert.get_subject().CN = hostname
        cert.set_serial_number(random.randint(0, 1000000000))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10*365*24*60*60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha256')

        with open(cert_file, "wt") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
        with open(key_file, "wt") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))

    def start_server(self, _):
        self.ip_address = self.get_ip_address()
        port = random.randint(1024, 65535)  # Choose a random port between 1024 and 65535
        self.base_url = f"https://{self.ip_address}:{port}"
        self.label.text = f"HTTPS server running at {self.base_url}"
        self.generate_qr_code(f"{self.base_url}/index.html?server={self.base_url}")

        cert_file = "server.crt"
        key_file = "server.key"
        self.generate_self_signed_cert(self.ip_address, cert_file, key_file)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)

        thread = Thread(target=lambda: app.run(host=self.ip_address, port=port, ssl_context=context, use_reloader=False))
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

    def _update_lines(self, _instance, _value):
        self.line1.points = [50, Window.height - 50, 100, Window.height - 100]
        self.line2.points = [50, Window.height - 100, 100, Window.height - 50]

    def show_calibration_screen(self, _instance):
        # Create values for the bounding box
        self.upperLeftX = 0
        self.upperLeftY = 0
        self.upperRightX = 0
        self.upperRightY = 0
        self.lowerLeftX = 0
        self.lowerLeftY = 0
        self.lowerRightX = 0
        self.lowerRightY = 0
        self.calibrated = False
        self.layout.clear_widgets()  # Clear the existing widgets
        # Make the window full screen
        Window.fullscreen = 'auto'
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)  # Set the color to white
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
        
        # Add the calibration instruction label
        self.calibration_label = Label(text='Activate your LED pen on each target as it appears.', color=(0, 0, 0, 1), font_size='20sp', halign='center', valign='middle')
        self.layout.add_widget(self.calibration_label)
        # Function to draw X and wait for tap
        def draw_and_wait(x1, y1, x2, y2, callback):
            oldX, oldY = cX, cY
            with self.layout.canvas:
                Color(1, 0, 0, 1)  # Set the color to red
                self.line1 = Line(points=[x1, y1, x2, y2], width=2)
                self.line2 = Line(points=[x1, y2, x2, y1], width=2)
                self.layout.bind(size=self._update_lines, pos=self._update_lines)
            self._update_rect(self.layout, None)
            def check_position(dt):
                if oldX != cX or oldY != cY:
                    self.layout.canvas.remove(self.line1)
                    self.layout.canvas.remove(self.line2)
                    callback(cX, cY)
                else:
                    Clock.schedule_once(check_position, 0.5)
            Clock.schedule_once(check_position, 0.5)

        def upper_left_callback(x, y):
            self.upperLeftX, self.upperLeftY = x, y
            time.sleep(3)
            self.layout.clear_widgets()  # Clear the existing widgets
            draw_and_wait(Window.width - 50, Window.height - 50, Window.width - 100, Window.height - 100, upper_right_callback)

        def upper_right_callback(x, y):
            self.upperRightX, self.upperRightY = x, y
            self.layout.clear_widgets()  # Clear the existing widgets
            time.sleep(1)
            draw_and_wait(Window.width - 50, 50, Window.width - 100, 100, lower_right_callback)

        def lower_right_callback(x, y):
            self.lowerRightX, self.lowerRightY = x, y
            self.layout.clear_widgets()  # Clear the existing widgets
            time.sleep(1)
            draw_and_wait(50, 50, 100, 100, lower_left_callback)

        def lower_left_callback(x, y):
            self.lowerLeftX, self.lowerLeftY = x, y
            time.sleep(1)
            self.layout.clear_widgets()  # Clear the existing widgets
            print("Calibration complete")
            self.calibrated = True
            Window.fullscreen = False  # Return to regular window size
            self.rebuild_main_screen()

        # Start the calibration process
        draw_and_wait(50, Window.height - 50, 100, Window.height - 100, upper_left_callback)

    def show_settings_menu(self, _instance):
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

    def save_settings(self, _instance):
        self.base_url = self.url_input.text
        self.rebuild_main_screen()

    def update_status(self, _dt):
        global last_stream_time
        if time.time() - last_stream_time < 5:
            self.status_label.text = 'Client connected'
            self.status_label.color = (0, 1, 0, 1)  # Set label text color to green
        else:
            self.status_label.text = 'Client disconnected'
            self.status_label.color = (1, 0, 0, 1)  # Set label text color to red

@app.route('/ip')
def get_ip():
    return jsonify('127.0.0.1')

@app.route('/stream', methods=['POST'])
def stream():
    global last_stream_time
    global cX
    global cY
    last_stream_time = time.time()  # Update the last stream time

    # Get the app instance to access parameters
    app_instance = RefurboardApp.get_running_app()
    if not app_instance:
        return jsonify({'error': 'App instance not found'})

    data = request.json
    image_data = base64.b64decode(data['image'])  # Decode the image from base64
    nparr = np.frombuffer(image_data, np.uint8)  # Convert to numpy array
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # Decode the image to BGR format

    # Convert to HSV for better color-based detection
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Convert to grayscale for brightness analysis
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Create a mask for very bright areas (potential LEDs)
    # This creates a binary mask where only very bright pixels are white
    _, bright_mask = cv2.threshold(gray, app_instance.brightness_threshold, 255, cv2.THRESH_BINARY)
    
    # Apply morphological operations to clean up the mask
    kernel = np.ones((3, 3), np.uint8)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)
    
    # Find contours of bright areas
    contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # Filter contours by area (LEDs should be small but not tiny)
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if app_instance.min_area < area < app_instance.max_area:
                # Additional filtering: check if contour is roughly circular
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > app_instance.circularity_threshold:
                        valid_contours.append(contour)
        
        if valid_contours:
            # Find the brightest contour
            brightest_contour = None
            max_brightness = 0
            
            for contour in valid_contours:
                # Create a mask for this contour
                mask = np.zeros(gray.shape, np.uint8)
                cv2.fillPoly(mask, [contour], 255)
                
                # Calculate mean brightness in this contour
                mean_brightness = cv2.mean(gray, mask=mask)[0]
                
                if mean_brightness > max_brightness:
                    max_brightness = mean_brightness
                    brightest_contour = contour
            
            if brightest_contour is not None and max_brightness > app_instance.min_brightness:
                # Calculate the centroid of the brightest contour
                M = cv2.moments(brightest_contour)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    return jsonify({'x': cX, 'y': cY, 'brightness': max_brightness})
    
    return jsonify({'error': 'LED not found'})

@app.route('/')
@app.route('/<path:path>')
def serve_static(path='index.html'):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    RefurboardApp().run()
