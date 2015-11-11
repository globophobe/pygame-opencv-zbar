# -*- coding: utf-8 -*-
import os
import cv2
import zbar
import requests
import datetime
import logging
from Queue import Queue
from threading import Thread
from PIL import Image

logger = logging.getLogger(__name__)
TEMP_DIR = 'temp'


def get_temp_dir():
    if not os.path.exists(TEMP_DIR):
        os.mkdir(TEMP_DIR)
    return TEMP_DIR


def thumbnail(picture, size=0.50):
    width, height = picture.size
    w, h = int(width * size), int(height * size)
    picture.thumbnail((w, h), Image.ANTIALIAS)
    return picture


def save_picture(picture, path, filename):
    '''Experiments with StringIO were unsatisfactory. Images were never
    well compressed. Let's save to temporary storage instead.'''
    storage = os.path.join(path, filename)
    picture.save(storage, optimize=True, format='JPEG')
    return storage


def delete_picture(path):
    try:
        os.remove(path)
    except:
        pass


def server_auth(queue, url, qrcode, picture, timestamp):
    timestamp = datetime.datetime.strftime(timestamp, '%Y%m%d%H%M%S%f')
    filename = '{}.jpeg'.format(timestamp)
    temp_storage = save_picture(picture, get_temp_dir(), filename)
    data = dict(qrcode=qrcode, timestamp=timestamp)
    files = {'picture': temp_storage}
    try:
        start = datetime.datetime.now()
        r = requests.post(url, data=data, files=files)
        end = datetime.datetime.now()
        elapsed_time = (end - start).total_seconds()
        logger.info('Elapsed time was {} seconds'.format(elapsed_time))
    except:
        response = None
    else:
        response = r.json()
    delete_picture(os.path.join(get_temp_dir(), filename))
    queue.put(response)


class QRCodeScanner(object):
    def __init__(
        self,
        url=None,
        box_color=(255, 0, 0),
        box_width=1,
        debug=False
    ):
        self.url = url
        self.thread = None
        self.queue = Queue()
        # Init zbar.
        self.scanner = zbar.ImageScanner()
        # Disable all zbar symbols.
        self.scanner.set_config(0, zbar.Config.ENABLE, 0)
        # Enable QRCodes.
        self.scanner.set_config(zbar.Symbol.QRCODE, zbar.Config.ENABLE, 1)
        # Highlight scanned QR Codes.
        self.box_color = box_color
        self.box_width = box_width
        self.successes = 0
        self.debug = debug

    def main(self, frame, timestamp):
        self.before_zbar(timestamp)
        frame, qrcodes = self.zbar(frame)
        if self.url:
            if qrcodes:
                for qrcode in qrcodes:
                    self.launch_thread(self.url, qrcode, frame, timestamp)
        frame = self.after_zbar(frame, qrcodes, timestamp)
        return frame

    def before_zbar(self, timestamp):
        pass

    def after_zbar(self, frame, qrcodes, timestamp):
        for qrcode in qrcodes:
            frame = self.draw_box(
                frame,
                qrcodes[qrcode],
                self.box_color,
                self.box_width
            )
        return frame

    def is_thread_running(self):
        # Initial state is None.
        if self.thread is not None:
            # Subsequent checks are for whether the thread is alive.
            if self.thread.is_alive():
                return True

    def launch_thread(self, url, qrcode, frame, timestamp):
        try:
            self.thread = Thread(
                target=server_auth,
                args=(
                    self.queue,
                    url,
                    qrcode,
                    Image.fromarray(frame),
                    timestamp
                )
            ).start()
        except:
            logger.error('Thread failed to start')
        else:
            self.after_thread_started(qrcode, timestamp)

    def after_thread_started(self, qrcode, timestamp):
        pass

    def zbar(self, frame):
        qrcodes = {}
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, threshold = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        try:
            pil_image = Image.fromarray(threshold)
            width, height = pil_image.size
            raw = pil_image.tostring()
        except:
            logger.error('Error converting to PIL image')
        else:
            try:
                image = zbar.Image(width, height, 'Y800', raw)
            except:
                logger.error('Error converting to ZBar image')
            else:
                self.scanner.scan(image)
                for qrcode in image:
                    location = []
                    for point in qrcode.location:
                        location.append(point)
                    qrcodes[qrcode.data] = location

                    if self.debug:
                        self.successes += 1
        if self.debug:
            frame = cv2.cvtColor(threshold, cv2.COLOR_GRAY2RGB)
        return frame, qrcodes

    def draw_box(self, frame, location, color, width):
        for index in range(len(location)):
            if (index + 1) == len(location):
                next_index = 0
            else:
                next_index = index + 1
            if cv2.__version__ >= '3.0.0':
                cv2.line(
                    frame,
                    location[index], location[next_index],
                    color,
                    width,
                    lineType=cv2.LINE_AA
                )
            else:
                cv2.line(
                    frame,
                    location[index], location[next_index],
                    color,
                    width,
                    cv2.CV_AA
                )
        return frame
