"""
Test cases for mouse control functionality
"""

import unittest
from unittest.mock import patch, MagicMock
from refurboard.utils.mouse_control import move_mouse, is_mouse_control_available


class TestMouseControl(unittest.TestCase):
    """Test cases for mouse control utilities"""
    
    def test_is_mouse_control_available(self):
        """Test mouse control availability check"""
        available = is_mouse_control_available()
        self.assertIsInstance(available, bool)
    
    @patch('refurboard.utils.mouse_control.mouse')
    def test_move_mouse_with_pynput_available(self, mock_mouse):
        """Test mouse movement when pynput is available"""
        # Mock the mouse controller
        mock_controller = MagicMock()
        mock_mouse.Controller.return_value = mock_controller
        
        # Test the function
        move_mouse(100, 100)
        
        # Verify the controller was called correctly
        mock_mouse.Controller.assert_called_once()
        self.assertEqual(mock_controller.position, (100, 100))
    
    @patch('refurboard.utils.mouse_control.MOUSE_CONTROL_AVAILABLE', False)
    @patch('builtins.print')
    def test_move_mouse_without_pynput(self, mock_print):
        """Test mouse movement when pynput is not available"""
        move_mouse(100, 100)
        
        # Should print a message instead of moving mouse
        mock_print.assert_called_with("Mouse would move to: (100, 100)")


if __name__ == '__main__':
    unittest.main()
