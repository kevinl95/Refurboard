"""
Test cases for network utilities
"""

import unittest
from refurboard.utils.network import get_ip_address, generate_qr_code_image


class TestNetworkUtils(unittest.TestCase):
    """Test cases for network utilities"""
    
    def test_get_ip_address(self):
        """Test IP address detection"""
        ip = get_ip_address()
        self.assertIsInstance(ip, str)
        # Should be a valid IP format (basic check)
        parts = ip.split('.')
        self.assertEqual(len(parts), 4)
        for part in parts:
            self.assertTrue(0 <= int(part) <= 255)
    
    def test_generate_qr_code(self):
        """Test QR code generation"""
        test_data = "https://example.com"
        qr_image = generate_qr_code_image(test_data)
        self.assertIsNotNone(qr_image)
        # Basic check that we got a PIL image object
        self.assertTrue(hasattr(qr_image, 'width'))
        self.assertTrue(hasattr(qr_image, 'height'))
        # QR codes should be square (or very close to it due to borders)
        width_height_ratio = qr_image.width / qr_image.height
        self.assertAlmostEqual(width_height_ratio, 1.0, delta=0.1)
        # Should have reasonable dimensions (bigger than before)
        self.assertGreater(qr_image.width, 200)  # Should be much bigger now
        self.assertGreater(qr_image.height, 200)


if __name__ == '__main__':
    unittest.main()
