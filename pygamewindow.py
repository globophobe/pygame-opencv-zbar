# -*- coding: utf-8 -*-
import datetime
import platform
import logging
import pygame
import cv2
import numpy
from pygame.locals import K_ESCAPE
from camera import (
    SIXTEEN_BY_TEN, SIXTEEN_BY_NINE, FOUR_BY_THREE, cv2_capture
)
from qrcodescanner import QRCodeScanner

logger = logging.getLogger(__name__)


class PygameWindow(object):
    def __init__(
            self,
            name=u'QR Code Scanner',
            font=None,
            url=None,
            resolution=(1280, 720),
            fps=30.0,
            mirror_frame=True,
            fullscreen=True,
            debug=False):
        self.url = url
        self.resolution = resolution
        self.fps = fps
        self.mirror_frame = mirror_frame
        self.font = font
        self.timestamp = datetime.datetime.now()
        self.clock = pygame.time.Clock()
        self.debug = debug
        pygame.init()
        pygame.display.init()
        pygame.mixer.init()
        # First, initialize camera.
        self.init_camera(resolution)
        # Then, initialize the pygame window with the same resolution as the
        # camera.
        self.init_window(name, self.camera.resolution, fullscreen=fullscreen)
        # Finally, initialize the scanner.
        self.init_scanner()
        self.is_window_active = True

    def get_current_resolution(self):
        display = pygame.display.Info()
        # display.current_w and display.current_h may return -1
        return (display.current_w, display.current_h)

    def get_current_aspect_ratio(self):
        resolution = self.get_current_resolution()
        return round(resolution[0] / float(resolution[1]), 2)

    def get_resolutions_for_current_aspect_ratio(self):
        aspect_ratio = self.get_current_aspect_ratio()
        return self.get_resolutions(aspect_ratio)

    def get_resolutions(self, target_aspect_ratio=None):
        aspect_ratios = {
            SIXTEEN_BY_TEN: [],
            SIXTEEN_BY_NINE: [],
            FOUR_BY_THREE: []
        }
        resolutions = pygame.display.list_modes()
        for mode in resolutions:
            aspect_ratio = round(mode[0] / float(mode[1]), 2)
            if SIXTEEN_BY_TEN == aspect_ratio:
                aspect_ratios[SIXTEEN_BY_TEN].append(mode)
            elif SIXTEEN_BY_NINE == aspect_ratio:
                aspect_ratios[SIXTEEN_BY_NINE].append(mode)
            elif FOUR_BY_THREE == aspect_ratio:
                aspect_ratios[FOUR_BY_THREE].append(mode)
        if target_aspect_ratio:
            resolutions = aspect_ratios[target_aspect_ratio]
        return resolutions

    def init_camera(self, resolution):
        def set_camera(resolutions):
            for resolution in resolutions:
                if not hasattr(self, 'camera'):
                    self.set_camera(resolution)
                else:
                    break
        if resolution == (0, 0):
            resolutions = self.get_resolutions_for_current_aspect_ratio()
            set_camera(resolutions)
        else:
            set_camera([resolution])

    def set_camera(self, resolution):
        camera = cv2_capture(resolution)
        if camera.resolution != resolution:
            # Setting resolution may fail, without an error, try 3 times.
            # Could this be because the camera is not fully initialized...
            for i in range(3):
                camera = cv2_capture(resolution)
                if camera.resolution == resolution:
                    break
        self.camera = camera

    def fit_camera_to_display(self):
        resolutions = self.get_resolutions_for_current_aspect_ratio()
        cam = self.camera.resolution
        logger.info('Supported resolutions {}'.format(resolutions))
        fit_to_camera = min(
            resolutions,
            # The best result seems to be the absolute value of the difference
            # of areas.
            key=lambda r: abs((cam[0] * cam[1]) - (r[0] * r[1]))
        )
        logger.info('Best resolution {}'.format(fit_to_camera))
        return fit_to_camera

    def init_window(self, name, resolution, fullscreen=False):
        pygame.display.set_caption(name)
        if fullscreen:
            self.display_surface = pygame.display.set_mode(
                self.fit_camera_to_display(),
                pygame.DOUBLEBUF | pygame.HWSURFACE | pygame.FULLSCREEN
            )
        else:
            self.display_surface = pygame.display.set_mode(
                self.fit_camera_to_display(), pygame.RESIZABLE
            )

        if self.debug:
            self.debug_font = self.get_font_size(32)

        self.load_user_interface()

    def get_font_size(self, size):
        if self.font:
            font = pygame.font.Font(self.font, size)
        else:
            font = pygame.font.SysFont(None, size)
        return font

    def load_user_interface(self):
        self.system_message(startup=True)

    def system_message(self, msg='Loading...', startup=False):
        BLACK = (0, 0, 0)
        ALICE_BLUE = (240, 248, 255)
        msg = self.get_font_size(48).render(
            msg, True, ALICE_BLUE
        )
        w, h = self.display_surface.get_size()
        w = w - msg.get_width()
        h = h - msg.get_height()
        self.display_surface.fill(BLACK)
        self.display_surface.blit(msg, (int(w / 2.0), int(h / 2)))
        if startup:
            pygame.display.flip()

    def init_scanner(self):
        # Show a loading message while QR code scanner initializes.
        # Init QR code scanner
        width_gt_1000 = self.display_surface.get_size()[0] >= 1000
        box_width = 2 if width_gt_1000 else 1
        self.scanner = QRCodeScanner(
            url=self.url, box_width=box_width, debug=self.debug
        )

    def main(self):
        # Prefered interface to OpenCV, with cv2.VideoCapture.grab()
        self.camera.enter_frame()
        if self.camera.frame is not None:
            if not self.camera.frame.size:
                self.system_message(msg='Invalid frame from camera.')
            else:
                frame = self.scanner.main(self.camera.frame, self.timestamp)
                frame = self.resize_frame(frame)
                # Find the frame's dimensions in (w, h) format.
                frame_size = frame.shape[1::-1]
                # Mirror preview after processing, or ZBar can't find QR codes.
                if self.mirror_frame:
                    frame = numpy.fliplr(frame)
                # Convert the frame to Pygame's Surface type.
                pygame_frame = pygame.image.frombuffer(
                    frame.tostring(), frame_size, 'RGB'
                )
                self.display_surface.blit(pygame_frame, (0, 0))
        # Exit frame.
        self.camera.exit_frame()

    def update_user_interface(self):
        """Subclass to customize this method."""
        pass

    def update_timestamp(self):
        self.timestamp = datetime.datetime.now()

    def display_debug_msg(self, msg, color, y_pos):
        w, h = self.display_surface.get_size()
        msg = self.debug_font.render(
            msg, True, color
        )
        w = w - (msg.get_width() + 20)
        self.display_surface.blit(msg, (w, y_pos))

    def display_resolution(self):
        BLUE = (0, 0, 255)
        msg = u'{} SCREEN {} CAMERA'.format(
            self.display_surface.get_size(),
            self.camera.resolution
        )
        self.display_debug_msg(msg, BLUE, 10)

    def display_fps(self, fps):
        GREEN = (0, 255, 0)
        msg = u'{} FPS'.format(int(round(fps)))
        self.display_debug_msg(msg, GREEN, 45)

    def display_successes(self):
        RED = (255, 0, 0)
        msg = u'{} OK'.format(self.scanner.successes)
        self.display_debug_msg(msg, RED, 80)

    def resize_frame(self, frame):
        w, h = self.display_surface.get_size()
        return cv2.resize(frame, (w, h))

    def update_fps(self):
        self.clock.tick()
        fps = self.clock.get_fps()
        if self.fps:
            if fps > self.fps:
                delay = int(1000.0 / (fps - self.fps))
                pygame.time.delay(delay)
        return self.clock.get_fps()

    def process_events(self):
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == K_ESCAPE:
                    self.destroy_window()
            elif event.type == pygame.QUIT:
                self.destroy_window()

    def destroy_window(self):
        self.is_window_active = False

    def event_loop(self):
        """Run the main loop."""
        self.main()
        self.update_user_interface()
        self.update_timestamp()
        fps = self.update_fps()
        if self.debug:
            self.display_resolution()
            self.display_fps(fps)
            self.display_successes()
        pygame.display.flip()
        self.process_events()

    def run(self):
        while self.is_window_active:
            self.event_loop()
