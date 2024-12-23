import socket
import qrcode
from io import BytesIO
from flask import Flask, jsonify
from threading import Thread
from kivy.app import App
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock

app = Flask(__name__)

class RefurboardApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical')
        self.label = Label(text='Starting HTTP server...')
        self.layout.add_widget(self.label)
        self.qr_image = Image()
        self.layout.add_widget(self.qr_image)
        Clock.schedule_once(self.start_server, 1)
        return self.layout

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

    def start_server(self, dt):
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

if __name__ == '__main__':
    RefurboardApp().run()