"""
Network utilities for Refurboard
"""

import socket
import urllib.parse
import qrcode
from io import BytesIO


def get_ip_address():
    """Get the local IP address of the machine"""
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


def generate_qr_code_image(data):
    """Generate a QR code PIL image from data"""
    import qrcode
    from qrcode.image.pil import PilImage
    
    # Create QR code with explicit settings
    qr = qrcode.QRCode(
        version=1,  # Start with version 1, let it auto-expand
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=15,
        border=4,
        image_factory=PilImage
    )
    
    qr.add_data(data)
    qr.make(fit=True)
    
    # Generate the image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Ensure it's converted to the right format
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    return img


def generate_qr_code(data):
    """Generate a QR code texture from data for Kivy"""
    try:
        from kivy.core.image import Image as CoreImage
    except ImportError:
        # Kivy not available or not properly initialized
        return None
    
    img = generate_qr_code_image(data)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return CoreImage(buffer, ext='png').texture
