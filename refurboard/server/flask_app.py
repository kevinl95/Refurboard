"""
Flask server for handling camera streams and serving the web client
"""

import time
import base64
import cv2
import numpy as np
import os
from flask import Flask, jsonify, request, send_from_directory

from ..vision.led_detector import LEDDetector
from ..utils.network import get_ip_address


class RefurboardServer:
    """Flask server for Refurboard"""
    
    def __init__(self, host='0.0.0.0', port=5000):
        self.app = Flask(__name__, static_folder='../../client', static_url_path='')
        self.host = host
        self.port = port
        self.detector = LEDDetector(led_color='green')  # Default to green
        self.latest_position = None
        self.current_position = {'x': 0, 'y': 0}  # Initialize current position
        self.last_stream_time = 0  # Initialize stream time tracking
        self._setup_routes()
        
    def update_led_color(self, color):
        """Update the LED color for detection"""
        self.detector = LEDDetector(led_color=color)
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/ip')
        def get_ip():
            return jsonify({'ip': get_ip_address()})
            
        @self.app.route('/led-color', methods=['GET', 'POST'])
        def led_color():
            if request.method == 'POST':
                data = request.get_json()
                color = data.get('color', 'green')
                if color in ['red', 'green', 'blue', 'white', 'any']:
                    self.update_led_color(color)
                    return jsonify({'status': 'success', 'color': color})
                else:
                    return jsonify({'status': 'error', 'message': 'Invalid color'}), 400
            else:
                return jsonify({'color': self.detector.led_color})
        
        @self.app.route('/stream', methods=['POST'])
        def stream():
            self.last_stream_time = time.time()
            
            # Use default LED detection parameters for now
            # TODO: Make these configurable through a proper settings interface
            self.detector.update_parameters(
                brightness_threshold=240,
                min_area=10,
                max_area=500,
                circularity_threshold=0.3,
                min_brightness=200
            )
            
            data = request.json
            image_data = base64.b64decode(data['image'])
            nparr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            result = self.detector.detect_led(frame)
            
            if 'x' in result and 'y' in result:
                self.current_position = {'x': result['x'], 'y': result['y']}
            
            return jsonify(result)
        
        @self.app.route('/')
        @self.app.route('/<path:path>')
        def serve_static(path='index.html'):
            return send_from_directory(self.app.static_folder, path)
    
    def get_current_position(self):
        """Get the current LED position"""
        return self.current_position
    
    def is_client_connected(self):
        """Check if a client has streamed recently"""
        return time.time() - self.last_stream_time < 5
    
    def run(self, host, port, ssl_context=None, **kwargs):
        """Run the Flask server"""
        self.app.run(host=host, port=port, ssl_context=ssl_context, **kwargs)
