# -*- coding: utf-8 -*-
import numpy as np
import cv2

SIXTEEN_BY_TEN = round(16 / 10.0, 2)
SIXTEEN_BY_NINE = round(16 / 9.0, 2)
FOUR_BY_THREE = round(4 / 3.0, 2)


def video_capture(resolution):
    try:
        import VideoCapture
    except ImportError:
        pass
    else:
        capture = VideoCapture.Device()
        capture.setResolution(int(resolution[0]), int(resolution[1]))
        return VideoCaptureManager(capture, resolution)


def cv2_capture(resolution):
    capture = cv2.VideoCapture(0)
    capture.set(3, resolution[0])  # CV_CAP_PROP_FRAME_WIDTH
    capture.set(4, resolution[1])  # CV_CAP_PROP_FRAME_HEIGHT
    # OpenCV doesn't considers the previously set resolution as only a
    # suggestion.
    current_resolution = int(capture.get(3)), int(capture.get(4))
    return CV2CaptureManager(capture, current_resolution)


class CaptureManager(object):
    def __init__(self, capture, resolution):
        self.capture = capture
        self.resolution = resolution
        self.entered_frame = False
        self._frame = None
        self._channel = 0

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, value):
        if self._channel != value:
            self._channel = value
            self._frame = None

    def enter_frame(self):
        pass

    def exit_frame(self):
        pass


class CV2CaptureManager(CaptureManager):
    @property
    def frame(self):
        if self.entered_frame and self._frame is None:
            _, frame = self.capture.retrieve(channel=self.channel)
            self._frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self._frame

    def enter_frame(self):
        """Capture the next frame, if any."""
        # But first, check that any previous frame was exited.
        assert not self.entered_frame, \
            'previous enter_frame() had no matching exit_frame()'

        if self.capture is not None:
            self.entered_frame = self.capture.grab()

    def exit_frame(self):
        """Release the frame."""
        # Check whether any grabbed frame is retrievable.
        # The getter may retrieve and cache the frame.
        if self.frame is None:
            self.entered_frame = False
            return

        # Release the frame.
        self._frame = None
        self.entered_frame = False
