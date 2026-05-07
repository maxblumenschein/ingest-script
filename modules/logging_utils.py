import logging
import sys


def setup_logging(log_path):
    logger = logging.getLogger('ingest')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # don't bubble up to root logger

    file_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)
    logger.addHandler(fh)

    # Route root-logger calls (from modules using logging.xyz directly) to file only
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)

    return logger
