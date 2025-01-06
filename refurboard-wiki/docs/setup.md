
## Setup Instructions

### Installing Python
Before setting up Refurboard, ensure you have Python installed on your system.

1. Download the latest version of Python from the [official Python website](https://www.python.org/downloads/).
2. Follow the installation instructions for your operating system.
3. Verify the installation by running:
    ```sh
    python --version
    ```

### Setting up Poetry
To set up Refurboard, you need to install Poetry, a Python dependency manager.

1. Install Poetry by following the instructions at [Poetry's official website](https://python-poetry.org/docs/#installation).
2. Clone the repository and navigate to the project directory:
    ```sh
    cd /Refurboard
    ```
3. Install the project dependencies:
    ```sh
    poetry install
    ```

### Starting the Client
Once you've set up Poetry and installed the necessary dependencies, you can start the client.

1. Start the Poetry shell:
    ```sh
    poetry shell
    ```
2. Run the client:
    ```sh
    python main.py
    ```

### Scanning the QR Code
To connect your smartphone or tablet to the Refurboard system, follow these steps:

1. Open your camera or QR code scanning app on your mobile device.
2. Scan the QR code displayed on your screen to connect your phone to the system.

### Accepting the Self-Signed Certificate
When you scan the QR code, you may be prompted to accept a self-signed certificate. This is necessary for establishing a secure connection. Click "Advanced" or "Continue" when you see the warning and proceed to the next steps.

### Using Refurboard with Your Projector

1. **Position Your Phone**: Point your old smartphone or tablet at the projector screen where you will be displaying content. The camera on your phone will track the LED pen movements on the screen.
   
2. **Start Calibration**: Open Refurboard on your device, then begin the calibration process. The app will prompt you to draw or move the LED pen around the boundaries of the screen. This helps the app recognize the edges of your projected display and adjust accordingly.
   
3. **Track the LED Pen**: Once the calibration is complete, the app will track the LED pen's movements on the screen. The pen will act as a pointer, controlling the mouse cursor on your connected computer, enabling you to interact with the content displayed on the projector.