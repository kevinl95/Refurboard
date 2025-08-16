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


class RefurboardServer:
    """Flask server for Refurboard"""
    
    def __init__(self, static_folder=None):
        if static_folder is None:
            # Get the absolute path to the client directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            static_folder = os.path.join(project_root, 'client')
        
        self.app = Flask(__name__, static_folder=static_folder)
        self.led_detector = LEDDetector()
        self.last_stream_time = 0
        self.current_position = {'x': 0, 'y': 0}
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/ip')
        def get_ip():
            return jsonify('127.0.0.1')
        
        @self.app.route('/stream', methods=['POST'])
        def stream():
            self.last_stream_time = time.time()
            
            # Use default LED detection parameters for now
            # TODO: Make these configurable through a proper settings interface
            self.led_detector.update_parameters(
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
            
            result = self.led_detector.detect_led(frame)
            
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
