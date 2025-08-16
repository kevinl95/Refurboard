"""
Test cases for mouse control functionality
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os


class TestMouseControl(unittest.TestCase):
    """Test cases for mouse control utilities"""
    
    def test_is_mouse_control_available(self):
        """Test mouse control availability check"""
        from refurboard.utils.mouse_control import is_mouse_control_available
        available = is_mouse_control_available()
        self.assertIsInstance(available, bool)
    
    @unittest.skipIf(os.environ.get('CI') or not os.environ.get('DISPLAY'), 
                     "Skipping mouse tests in headless environment")
    def test_move_mouse_with_display(self):
        """Test mouse movement when display is available"""
        with patch('refurboard.utils.mouse_control.mouse') as mock_mouse:
            mock_controller = MagicMock()
            mock_mouse.Controller.return_value = mock_controller
            
            from refurboard.utils.mouse_control import move_mouse
            move_mouse(100, 100)
            
            mock_mouse.Controller.assert_called_once()
            self.assertEqual(mock_controller.position, (100, 100))
    
    def test_move_mouse_headless_environment(self):
        """Test mouse movement in headless environment"""
        # Mock the entire pynput import to simulate headless environment
        with patch.dict('sys.modules', {'pynput': None, 'pynput.mouse': None}):
            # Force reimport to trigger the ImportError path
            if 'refurboard.utils.mouse_control' in sys.modules:
                del sys.modules['refurboard.utils.mouse_control']
            
            with patch('builtins.print') as mock_print:
                from refurboard.utils.mouse_control import move_mouse, is_mouse_control_available
                
                # Should indicate mouse control is not available
                self.assertFalse(is_mouse_control_available())
                
                # Should print message instead of moving mouse
                move_mouse(100, 100)
                mock_print.assert_called_with("Mouse would move to: (100, 100)")


if __name__ == '__main__':
    unittest.main()
