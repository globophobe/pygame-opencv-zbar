# QRCodeScannerBase

Implementation of a QR Code scanner using Pygame 1.9.1, VideoCapture 0.9-5, OpenCV, and ZBar. Targets Python 2.7, for Twisted integration, and to support building an EXE with Pyinstaller.

First tries to use VideoCapture, then falls back on OpenCV. On Windows,
VideoCapture performance seems better than OpenCV. However, on Mac and Linux, the better performance of GStreamer isn't worth the extra
dependencies.

Thanks to the source code of the Kivy project for information about VideoCapture.

Also, thanks to the OpenCV docs on Otsu’s Binarization.

Finally, thanks to the book "OpenCV Computer Vision with Python" for kickstarting this project, after SimpleCV failed to work with the camera.

MIT License
