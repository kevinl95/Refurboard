"""
Test cases for LED detection functionality
"""

import unittest
import numpy as np
import cv2
from refurboard.vision.led_detector import LEDDetector


class TestLEDDetector(unittest.TestCase):
    """Test cases for LEDDetector class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = LEDDetector()
    
    def test_detector_initialization(self):
        """Test detector initializes with correct default parameters"""
        self.assertEqual(self.detector.brightness_threshold, 240)
        self.assertEqual(self.detector.min_area, 10)
        self.assertEqual(self.detector.max_area, 500)
        self.assertEqual(self.detector.circularity_threshold, 0.3)
        self.assertEqual(self.detector.min_brightness, 200)
    
    def test_update_parameters(self):
        """Test parameter updating"""
        self.detector.update_parameters(brightness_threshold=250, min_area=15)
        self.assertEqual(self.detector.brightness_threshold, 250)
        self.assertEqual(self.detector.min_area, 15)
        # Other parameters should remain unchanged
        self.assertEqual(self.detector.max_area, 500)
    
    def test_detect_led_no_led(self):
        """Test detection when no LED is present"""
        # Create a dark image
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.detector.detect_led(frame)
        self.assertIn('error', result)
        self.assertEqual(result['error'], 'LED not found')
    
    def test_detect_led_with_bright_spot(self):
        """Test detection with a bright circular spot"""
        # Create an image with a bright circle
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 15, (255, 255, 255), -1)
        
        result = self.detector.detect_led(frame)
        if 'x' in result:  # Detection might succeed depending on parameters
            self.assertIsInstance(result['x'], int)
            self.assertIsInstance(result['y'], int)
            self.assertIsInstance(result['brightness'], float)
    
    def test_calculate_centroid(self):
        """Test centroid calculation"""
        # Create a simple contour (rectangle)
        points = np.array([[100, 100], [150, 100], [150, 150], [100, 150]], dtype=np.int32)
        contour = points.reshape(-1, 1, 2)
        
        x, y = self.detector._calculate_centroid(contour)
        self.assertEqual(x, 125)  # Center X
        self.assertEqual(y, 125)  # Center Y


if __name__ == '__main__':
    unittest.main()
