import socket
import qrcode
import base64
import cv2
import numpy as np
from io import BytesIO
from flask import Flask, jsonify, request
from threading import Thread
from kivy.app import App
from kivy.graphics import Color, Rectangle
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window

app = Flask(__name__)
UPLOAD_FOLDER = '/path/to/upload/folder'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class RefurboardApp(App):
    def build(self):
        self.icon = 'assets/logo.png'  # Set the application icon
        self.layout = BoxLayout(orientation='vertical')
        self.layout.canvas.before.clear()
        
        # Add the logo image
        self.logo = Image(source='assets/logo.png', size_hint=(None, None), size=(200, 200), pos_hint={'center_x': 0.5, 'top': 1})
        self.layout.add_widget(self.logo)
        
        self.label = Label(text='Starting HTTP server...', color=(0, 0, 0, 1))  # Set label text color to black
        self.layout.add_widget(self.label)
        self.qr_image = Image()
        self.layout.add_widget(self.qr_image)
        Clock.schedule_once(self.start_server, 1)
        with self.layout.canvas.before:
            Color(1, 1, 1, 1)  # Set the background color to white
            self.rect = Rectangle(size=Window.size, pos=self.layout.pos)
            self.layout.bind(size=self._update_rect, pos=self._update_rect)
        return self.layout

    def _update_rect(self, instance, _):
        self.rect.size = instance.size

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
        ip_address = self.get_ip_address()
        self.label.text = f"HTTP server running at http://{ip_address}:5000"
        self.generate_qr_code(f"http://{ip_address}:5000")
        thread = Thread(target=app.run, kwargs={'host': ip_address, 'port': 5000})
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

@app.route('/ip')
def get_ip():
    ip_address = socket.gethostbyname(socket.gethostname())
    return jsonify(ip_address)

@app.route('/stream', methods=['POST'])
def stream():
    try:
        # Get the JSON data from the request
        data = request.get_json()

        if 'image' not in data:
            return jsonify({'error': 'No image data provided'}), 400

        # Decode the base64 image data
        image_data = base64.b64decode(data['image'])

        # Convert the image data to a NumPy array
        nparr = np.frombuffer(image_data, np.uint8)

        # Decode the NumPy array into an OpenCV image
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Convert the image to HSV color space for color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Define the color range for the LED (example for red color)
        lower_bound = np.array([0, 100, 100])  # Adjust based on the LED color
        upper_bound = np.array([10, 255, 255])  # Adjust based on the LED color

        # Create a mask to identify the color in the specified range
        mask = cv2.inRange(hsv, lower_bound, upper_bound)

        # Find contours of the detected areas
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Find the largest contour (assumes LED is the largest bright spot of this color)
            largest_contour = max(contours, key=cv2.contourArea)
            (x, y), radius = cv2.minEnclosingCircle(largest_contour)

            if radius > 5:  # Minimum size to filter noise
                return jsonify({
                    'detected': True,
                    'position': {'x': int(x), 'y': int(y)},
                    'radius': int(radius)
                }), 200

        return jsonify({'detected': False}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'An error occurred'}), 500

if __name__ == '__main__':
    RefurboardApp().run()
    def process_frame(frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) > 100:
                (x, y, w, h) = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        return frame