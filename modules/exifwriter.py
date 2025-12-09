import shutil
import subprocess
import logging

def has_exiftool():
    """Check if exiftool is available in PATH."""
    return shutil.which('exiftool') is not None


def write_metadata_to_file(target_path, metadata_args, dry_run=False, logger=None):
    """
    Write metadata using ExifTool.

    metadata_args: list of strings like ['-Creator=Max Mustermann', ...]
    """
    if logger is None:
        logger = logging.getLogger('ingest')

    if not has_exiftool():
        logger.error('exiftool not found')
        return False

    cmd = ['exiftool'] + metadata_args + [target_path]
    logger.info('Running exiftool: %s', ' '.join(cmd))

    if dry_run:
        logger.info('[DRY-RUN] exiftool call skipped')
        return True

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if proc.stdout:
            logger.info('exiftool stdout: %s', proc.stdout.strip())
        if proc.stderr:
            logger.warning('exiftool stderr: %s', proc.stderr.strip())
        return True
    except subprocess.CalledProcessError as e:
        logger.error('exiftool failed: %s', e.stderr.strip() if e.stderr else str(e))
        return False
