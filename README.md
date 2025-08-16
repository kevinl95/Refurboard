# Refurboard

![A smart phone with two blue and orange people leaping out of the screen. Below is the text Refurboard.](assets/logo.png)

[![Homepage Azure Deployment](https://github.com/kevinl95/Refurboard/actions/workflows/azure-static-web-apps-ashy-pebble-0a0fa1710.yml/badge.svg)](https://github.com/kevinl95/Refurboard/actions/workflows/azure-static-web-apps-ashy-pebble-0a0fa1710.yml)[![Automated Tests](https://github.com/kevinl95/Refurboard/actions/workflows/test.yml/badge.svg)](https://github.com/kevinl95/Refurboard/actions/workflows/test.yml)

## Overview

Refurboard is an innovative, low-cost solution that turns your old smartphone into an interactive whiteboard for classrooms, businesses, and artists. By leveraging the camera on your device and utilizing computer vision to track LED pens (such as those purchasable at discount retailers, such as FiveBelow), Refurboard enables users to interact with projected displays in real time. Teachers, in particular, can greatly benefit from this tool, as it provides an affordable way to enhance classroom interactivity without requiring expensive equipment.

Client devices can be running any operating system as long as they can connect to the same network as your computer and have a camera. This means your old Android. iOS device, Windows Phone, and more can have a second life!

Refurboard's design focuses on simplicity and affordability, making it accessible to anyone. You can easily set it up by pointing your phone's camera at your projector screen, calibrating the boundaries, and using an LED pen to control the cursor. Once calibrated, the app tracks the pen's movements and moves the mouse cursor accordingly, creating an interactive whiteboard experience.

### Key Benefits:
- **Impact for Teachers**: Teachers can turn any old smartphone into an interactive tool for their classroom, enabling students to interact with lessons in real-time. This helps make learning more engaging and interactive without a big investment in hardware.
- **Low-Cost Setup**: You don't need expensive smartboards or interactive projectors. Refurboard uses affordable LED pens (available at discount stores like FiveBelow) and old smartphones, minimizing costs while still offering powerful functionality.
- **Simple Calibration**: Setting up Refurboard is easy. Point your phone at your projector screen, run the calibration process, and the app will learn the boundaries of the screen. The LED pen then becomes a pointer, and the app will track its movement, controlling the mouse cursor on your connected computer.
- **Cross-Platform Compatibility**: Refurboard works on a variety of devices, including Android, iOS, and Windows, so you can use it with devices you already own.

Visit our [Azure-hosted homepage and Wiki](https://refurboard.com) for more details, installation instructions, and support.

## Features

- **Interactive Whiteboard**: Transform any old smartphone into an interactive whiteboard that tracks LED pen movements and controls the mouse cursor.
- **Cross-Platform**: Refurboard works across multiple platforms, including Android, iOS, Windows, and more.
- **Computer Vision**: Utilizes the camera of your smartphone or tablet to track LED pens in real-time, enabling accurate cursor control.
- **Affordable Setup**: Use inexpensive LED pens from discount stores and your old smartphone, providing an interactive whiteboard solution at a fraction of the cost of traditional smartboards.
- **Azure-Hosted**: Access comprehensive setup instructions, troubleshooting, and additional resources on our [homepage and Wiki](https://refurboard.com).

## Setup Instructions

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

### Running Tests
Refurboard includes a comprehensive test suite to ensure code quality and reliability:

1. Run all tests:
    ```sh
    poetry run pytest
    ```

2. Run tests with coverage report:
    ```sh
    poetry run pytest --cov=refurboard
    ```

3. Run specific test modules:
    ```sh
    poetry run pytest tests/test_led_detector.py  # Test computer vision
    poetry run pytest tests/test_network.py      # Test networking utilities
    poetry run pytest tests/test_mouse_control.py # Test mouse control
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
   
3. **Track the LED Pen**: Once the calibration is complete, the app will track the LED pen's movements on the screen using computer vision algorithms. The pen will act as a pointer, controlling the mouse cursor on your connected computer, enabling you to interact with the content displayed on the projector.

## Architecture

```
refurboard/
├── __init__.py          # Package initialization
├── server/              # Flask server and SSL utilities
│   ├── flask_app.py     # RefurboardServer class with organized routes
│   └── ssl_utils.py     # SSL certificate generation
├── vision/              # Computer vision processing
│   └── led_detector.py  # LEDDetector class with advanced algorithms
├── utils/               # Utility modules
│   ├── network.py       # IP detection and QR code generation
│   └── mouse_control.py # Cross-platform mouse control with pynput
└── ui/                  # User interface components (future expansion)
```

### Key Components
- **LEDDetector**: Computer vision with contour analysis, brightness filtering, and circularity detection
- **RefurboardServer**: Flask server with route management and LED detector integration
- **Network Utilities**: IP detection and QR code generation
- **Mouse Control**: Cross-platform mouse movement using pynput

## Getting Help
If you run into any issues or need more information on setting up Refurboard, visit our [Azure-hosted homepage](https://refurboard.com). There, you'll find detailed instructions, troubleshooting tips, and an FAQ section.

### Building Executables
You can build Refurboard into a distributable format for easier deployment.

1. Ensure you are in the Poetry shell:
    ```sh
    poetry shell
    ```
2. Install the development dependencies:
    ```sh
    poetry install --with dev
    ```
3. Run the build script to create the executable:
    ```sh
    ./build_executable.sh
    ```

### Development and Contributing
For developers interested in contributing to Refurboard:

1. **Python Compatibility**: Supports Python 3.11, 3.12, and 3.13
2. **Testing**: Always run the test suite before submitting changes:
    ```sh
    poetry run pytest --cov=refurboard
    ```
3. **Modular Design**: New features should follow the existing package structure
4. **Cross-Platform**: Refurboard supports Windows, Linux, and macOS.

## License
This project is licensed under the terms of the Apache-2.0 license. See the [LICENSE](LICENSE) file for details.