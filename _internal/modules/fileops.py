import os
import shutil
import logging
import subprocess


def move_file(src, dst, reason, dry_run=False, logger=None):
    if logger is None:
        logger = logging.getLogger('ingest')
    if dry_run:
        logger.info('[DRY-RUN] Move: %s -> %s (%s)', src, dst, reason)
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        shutil.move(src, dst)
        logger.info('Moved: %s -> %s (%s)', src, dst, reason)
    except Exception as e:
        logger.error('Failed to move %s -> %s: %s', src, dst, e)
        raise


def copy_metadata_with_exiftool(src_path, dst_path, logger=None):
    if logger is None:
        logger = logging.getLogger('ingest')
    if shutil.which('exiftool') is None:
        logger.warning('exiftool not found; cannot copy metadata')
        return
    cmd = ['exiftool', '-overwrite_original', '-TagsFromFile', src_path, '-All:All', dst_path]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if proc.stdout:
            logger.debug('exiftool: %s', proc.stdout)
    except subprocess.CalledProcessError as e:
        logger.error('Exiftool failed copying metadata: %s', e.stderr)