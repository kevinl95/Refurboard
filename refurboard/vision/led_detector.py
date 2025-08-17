"""
LED detection algorithms using OpenCV
"""

import cv2
import numpy as np


class LEDDetector:
    """Advanced LED detection using computer vision"""
    
    def __init__(self, brightness_threshold=240, min_area=10, max_area=500, 
                 circularity_threshold=0.3, min_brightness=200, led_color='green'):
        self.brightness_threshold = brightness_threshold
        self.min_area = min_area
        self.max_area = max_area
        self.circularity_threshold = circularity_threshold
        self.min_brightness = min_brightness
        self.led_color = led_color
        
        # Define HSV color ranges for different LED colors
        self.color_ranges = {
            'red': [(0, 100, 100), (10, 255, 255)],  # Red - will handle wraparound separately
            'green': [(40, 100, 100), (80, 255, 255)],
            'blue': [(100, 100, 100), (130, 255, 255)],
            'white': [(0, 0, 200), (180, 30, 255)],  # Low saturation, high value
            'any': None  # Brightness-only detection
        }
    
    def detect_led(self, frame):
        """
        Detect LED position in the given frame
        
        Args:
            frame: BGR image from camera
            
        Returns:
            dict: {'x': x, 'y': y, 'brightness': brightness, 'color': color} or {'error': message}
        """
        try:
            # Convert to HSV for better color-based detection
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Convert to grayscale for brightness analysis
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Create color mask based on selected LED color
            color_mask = self._create_color_mask(hsv)
            
            # Create brightness mask
            _, bright_mask = cv2.threshold(gray, self.brightness_threshold, 255, cv2.THRESH_BINARY)
            
            # Combine color and brightness masks
            if color_mask is not None:
                combined_mask = cv2.bitwise_and(color_mask, bright_mask)
            else:
                combined_mask = bright_mask
            
            # Apply morphological operations to clean up the mask
            kernel = np.ones((3, 3), np.uint8)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
            
            # Find contours of bright colored areas
            contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Filter contours by area and shape
                valid_contours = self._filter_contours(contours)
                
                if valid_contours:
                    # Find the brightest contour
                    brightest_contour, max_brightness = self._find_brightest_contour(valid_contours, gray)
                    
                    if brightest_contour is not None and max_brightness > self.min_brightness:
                        # Calculate the centroid
                        x, y = self._calculate_centroid(brightest_contour)
                        if x is not None and y is not None:
                            return {
                                'x': x, 
                                'y': y, 
                                'brightness': max_brightness,
                                'color': self.led_color
                            }
            
            return {'error': 'LED not found'}
        except Exception as e:
            print(f"Error in LED detection: {e}")
            return {'error': f'Detection failed: {str(e)}'}
    
    def _create_color_mask(self, hsv_frame):
        """
        Create a color mask based on the selected LED color
        
        Args:
            hsv_frame: HSV image
            
        Returns:
            Binary mask or None if using brightness-only detection
        """
        try:
            if self.led_color not in self.color_ranges:
                return None
                
            color_range = self.color_ranges[self.led_color]
            if color_range is None:  # 'any' color option
                return None
                
            # Handle red color wraparound in HSV space
            if self.led_color == 'red':
                # Red spans 0-10 and 160-180 in HSV hue
                mask1 = cv2.inRange(hsv_frame, np.array([0, 100, 100]), np.array([10, 255, 255]))
                mask2 = cv2.inRange(hsv_frame, np.array([160, 100, 100]), np.array([180, 255, 255]))
                return cv2.bitwise_or(mask1, mask2)
            else:
                # Standard color range
                lower_bound = np.array(color_range[0])
                upper_bound = np.array(color_range[1])
                return cv2.inRange(hsv_frame, lower_bound, upper_bound)
        except Exception as e:
            print(f"Error creating color mask: {e}")
            return None  # Fall back to brightness-only detection

    def _filter_contours(self, contours):
        """Filter contours by area and circularity"""
        valid_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_area < area < self.max_area:
                # Check if contour is roughly circular
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > self.circularity_threshold:
                        valid_contours.append(contour)
        return valid_contours
    
    def _find_brightest_contour(self, contours, gray):
        """Find the brightest contour from the list"""
        brightest_contour = None
        max_brightness = 0
        
        for contour in contours:
            # Create a mask for this contour
            mask = np.zeros(gray.shape, np.uint8)
            cv2.fillPoly(mask, [contour], 255)
            
            # Calculate mean brightness in this contour
            mean_brightness = cv2.mean(gray, mask=mask)[0]
            
            if mean_brightness > max_brightness:
                max_brightness = mean_brightness
                brightest_contour = contour
                
        return brightest_contour, max_brightness
    
    def _calculate_centroid(self, contour):
        """Calculate the centroid of a contour"""
        M = cv2.moments(contour)
        if M["m00"] != 0:
            x = int(M["m10"] / M["m00"])
            y = int(M["m01"] / M["m00"])
            return x, y
        return None, None
    
    def update_parameters(self, **kwargs):
        """Update detection parameters"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
