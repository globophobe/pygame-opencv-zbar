# -*- coding: utf-8 -*-
import os
import datetime
import logging
import requests
import numpy
import cv2
import zbar
from Queue import Queue
from threading import Thread
from PIL import Image

logger = logging.getLogger(__name__)
TEMP_DIR = os.path.join(os.getcwd(), 'temp')


def get_temp_dir():
    """Create TEMP_DIR if it doesn't exist"""
    if not os.path.exists(TEMP_DIR):
        os.mkdir(TEMP_DIR)
    return TEMP_DIR


def thumbnail(picture, size=0.50):
    """Thumbnail the picture"""
    width, height = picture.size
    w, h = int(width * size), int(height * size)
    picture.thumbnail((w, h), Image.ANTIALIAS)
    return picture


def save_picture(picture, path, filename):
    """Save picture to filesystem, return the path"""
    # Unfortunately, StringIO was unsatisfactory
    # StringIO size exceeds size of filesystem save. Why??
    storage = os.path.join(path, filename)
    picture.save(storage, optimize=True, format='JPEG')
    return storage


def delete_picture(path):
    """Delete the file, with a try except clause"""
    try:
        os.remove(path)
    # Gee! Thanks Windows
    except:
        pass


def prepare_msg(qrcode, picture, timestamp):
    """Prepare message to send to server"""
    timestamp = datetime.datetime.strftime(timestamp, '%Y%m%d%H%M%S%f')
    filename = '{}.jpeg'.format(timestamp)
    temp_storage = save_picture(picture, get_temp_dir(), filename)
    data = dict(qrcode=qrcode, timestamp=timestamp)
    files = {'picture': temp_storage}
    return filename, data, files


def server_auth(queue, url, qrcode, picture, timestamp, timeout=5):
    """Send message to server for auth"""
    filename, data, files = prepare_msg(qrcode, picture, timestamp)
    try:
        if logger.getEffectiveLevel() >= logging.INFO:
            # Profile the request
            start = datetime.datetime.now()
        r = requests.post(url, data=data, files=files, timeout=timeout)
        if logger.getEffectiveLevel >= logging.INFO:
            # Profile the request
            end = datetime.datetime.now()
            elapsed_time = (end - start).total_seconds()
            logger.info('Elapsed time was {} seconds'.format(elapsed_time))
    except Exception as e:
        response = None
        # Did the request timeout?
        if isinstance(e, requests.exceptions.Timeout):
            response = dict(network_timeout=True)
    else:
        response = r.json()
    finally:
        delete_picture(os.path.join(get_temp_dir(), filename))
    queue.put(response)


class QRCodeScanner(object):
    def __init__(
        self,
        url=None,
        max_responses=2,
        timeout=5,
        ok_color=(0, 0, 255),
        not_ok_color=(255, 0, 0),
        box_width=1,
        debug=False
    ):
        self.url = url
        self.timeout = timeout
        self.max_responses
        self.thread = None
        self.queue = Queue()
        # Init zbar.
        self.scanner = zbar.ImageScanner()
        # Disable all zbar symbols.
        self.scanner.set_config(0, zbar.Config.ENABLE, 0)
        # Enable QRCodes.
        self.scanner.set_config(zbar.Symbol.QRCODE, zbar.Config.ENABLE, 1)
        # Highlight scanned QR Codes.
        self.ok_color = ok_color
        self.not_ok_color = not_ok_color
        self.box_width = box_width
        self.successes = 0
        self.debug = debug

    def main(self, frame, timestamp):
        """Main function"""
        self.before_zbar(timestamp)
        frame, qrcodes = self.zbar(frame)
        if len(qrcodes) > 0:
            self.auth(frame, qrcodes, timestamp)
        frame = self.after_zbar(frame, qrcodes, timestamp)
        self.process_results_from_queue(timestamp)
        return frame

    def auth(self, frame, qrcodes, timestamp):
        """Auth with server"""
        if self.url is not None:
            qrcode = self.get_next_qrcode(frame, qrcodes)
            if qrcode is not None:
                if len(self.responses) > self.max_responses:
                    frame = Image.fromarray(frame)
                    self.launch_thread(self.url, qrcode, frame, timestamp)

    def get_next_qrcode(self, frame, qrcodes):
        """Returns the largest valid QR code, which is neither the
        active QR code nor throttled"""
        height, width = frame.shape[:2]
        frame_size = width * height

        target = None
        targets = [
            dict(
                qrcode=qrcode,
                size=self.qrcode_size(qrcodes[qrcode])
            )
            for qrcode in qrcodes
        ]
        targets = sorted(targets, key=lambda k: k['size'])
        for target in targets:
            qrcode = target['qrcode']
            qrcode_size = target['size'] / frame_size
            qrcode_size = round(qrcode_size, 4)
            if self.debug:
                logger.info('QRcode percent of frame: {}%'.format(
                    qrcode_size
                ))
            # Throttle requests for the same QR code.
            if self.active_qrcode != qrcode:
                # Throttle requests for cached QR codes.
                if not self.is_qrcode_throttled(qrcode):
                    # Ensure the QR code is valid.
                    is_valid = self.is_valid_qrcode(qrcode)
                    if self.debug:
                        logger.info('QRcode is valid: {}'.format(is_valid))
                    if is_valid:
                        if self.max_qrcode_size > 0:
                            if qrcode_size > self.max_qrcode_size:
                                self.max_size_exceeded = True
                                break
                        if not self.max_size_exceeded:
                            return qrcode

    def is_valid_qrcode(self, qrcode):
        """Intended to be overriden by subclass."""
        return True if qrcode is not None else False

    def is_qrcode_throttled(self, qrcode):
        for throttle in (self.ok_throttle_dict, self.not_ok_throttle_dict):
            if qrcode in throttle:
                return True

    def get_qrcode_size(self, qrcode):
        contour = numpy.array(qrcode, dtype=numpy.int32)
        return cv2.contourArea(contour)

    def before_zbar(self, timestamp):
        """Remove expired QR codes from throttle dict"""
        for throttle in (self.ok_throttle_dict, self.not_ok_throttle_dict):
            delete = []
            for qrcode in throttle:
                expired = (throttle[qrcode] <= datetime.datetime.now())
                if expired:
                    delete.append(qrcode)
            for qrcode in delete:
                del throttle[qrcode]

    def zbar(self, frame):
        """Scan frame using ZBar"""
        qrcodes = {}
        # Convert to grayscale, as binarization requires
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        # Apply Otsu Binarization
        _, threshold = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        try:
            # Convert to string, as ZBar requires
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

    def after_zbar(self, frame, qrcodes, timestamp):
        """Intended to be overridden by subclass. Currently, draws boxes
        around QR codes"""
        frame = self.draw_boxes(qrcodes, frame)
        return frame

    def draw_box(self, frame, location, color, width):
        """Draw a box around around QR code"""
        for index in range(len(location)):
            if (index + 1) == len(location):
                next_index = 0
            else:
                next_index = index + 1
            # From OpenCV 3.0.0, cv2.LINE_AA was renamed cv2.CV_AA
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

    def is_thread_running(self):
        """Check if the thread is running"""
        # Is a thread active?
        if self.thread is not None:
            if self.thread.is_alive():
                return True

    def launch_thread(self, url, qrcode, frame, timestamp):
        """Launch a thread to auth against server with requests library"""
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
        """Runs after thread is started. Throttles not OK results"""
        # Throttle requests
        self.not_ok_throttle_dict[qrcode] = (
            timestamp + datetime.timedelta(seconds=self.not_ok_throttle)
        )
        self.active_qrcode = qrcode
        logger.info('Sent QRcode to server {}'.format(self.active_qrcode))

    def process_results_from_queue(self, timestamp):
        """Throttles OK results. Prepares response for GUI"""
        if not self.queue.empty():
            # Clear active qrcode
            self.active_qrcode = None
            response = self.queue.get()
            if response is not None:
                # Response is OK. Flag the QR code as OK, and throttle it
                if 'qrcode' in response:
                    qrcode = response['qrcode']
                    ok_throttle = datetime.timedelta(seconds=self.ok_throttle)
                    self.ok_throttle_dict[qrcode] = timestamp + ok_throttle
                    self.responses.append(response)
