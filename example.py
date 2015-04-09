# -*- coding: utf-8 -*-
import sys
import argparse
import traceback
import logging
from pygamewindow import PygameWindow

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='QR Code Scanner')
    parser.add_argument(
        '--fps',
        dest='fps',
        action='store',
        type=int,
        default=30.0
    )
    parser.add_argument(
        '--width',
        dest='width',
        action='store',
        type=int,
        default=640
    )
    parser.add_argument(
        '--height',
        dest='height',
        action='store',
        type=int,
        default=480
    )
    parser.add_argument('--fullscreen', dest='fullscreen', action='store_true')
    parser.add_argument(
        '--without-dshow', dest='dshow', action='store_false', default=True
    )
    parser.add_argument('--debug', dest='debug', action='store_true')
    args = parser.parse_args()

    qrcode_scanner = PygameWindow(
        name='QR Code Scanner',
        dshow=args.dshow,
        fps=args.fps,
        resolution=(args.width, args.height),
        fullscreen=args.fullscreen,
        debug=args.debug,
    )

    if not args.debug:
        logging.basicConfig(filename='error.log', level=logging.ERROR)
        try:
            qrcode_scanner.run()
        except:
            type, value, tb = sys.exc_info()
            with open(error_log, 'a') as f:
                traceback.print_exc(file=f)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        qrcode_scanner.run()
