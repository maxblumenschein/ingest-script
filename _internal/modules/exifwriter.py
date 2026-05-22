import json
import logging
import os
import re
import shutil
import subprocess

def normalize_date_to_iso8601(date_str):
    """Convert EXIF-style date (YYYY:MM:DD HH:MM:SS[±HH:MM]) to ISO 8601."""
    m = re.match(r'(\d{4})[:\-](\d{2})[:\-](\d{2})[T ](\d{2}):(\d{2}):(\d{2})([\+\-]\d{2}:\d{2}|Z)?', date_str.strip())
    if not m:
        return None
    y, mo, d, h, mi, s = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
    tz = m.group(7) or ''
    return f"{y}-{mo}-{d}T{h}:{mi}:{s}{tz}"


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
    logger.debug('exiftool: %s', ' '.join(cmd))

    if dry_run:
        logger.debug('[DRY-RUN] exiftool call skipped')
        return True

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', check=True)
        if proc.stderr:
            logger.warning('exiftool stderr: %s', proc.stderr.strip())
        return True
    except subprocess.CalledProcessError as e:
        logger.error('exiftool failed: %s', e.stderr.strip() if e.stderr else str(e))
        return False


def ensure_xmp_create_date(file_path, dry_run=False, logger=None):
    """
    Ensure XMP-xmp:CreateDate is set on the file in ISO 8601 format.
    If already present: no-op. If absent: copy from best available image date.
    Returns True on success, False if no plausible date exists.
    """
    if logger is None:
        logger = logging.getLogger('ingest')

    fname = os.path.basename(file_path)

    # Check specifically whether XMP-xmp:CreateDate is already set
    try:
        proc = subprocess.run(
            ['exiftool', '-j', '-XMP-xmp:CreateDate', file_path],
            capture_output=True, text=True, encoding='utf-8', check=True
        )
        data = json.loads(proc.stdout)
        if data and data[0].get('CreateDate'):
            return True
    except Exception as e:
        logger.error('%s: cannot check XMP:CreateDate: %s', fname, e)
        return False

    # Find best fallback date from full metadata
    from modules.filechecks import get_metadata_tags, find_plausible_date
    try:
        metadata = get_metadata_tags(file_path)
    except Exception as e:
        logger.error('%s: cannot read metadata for date fallback: %s', fname, e)
        return False

    src_tag, raw_val = find_plausible_date(metadata)
    if not raw_val:
        logger.error('%s: no plausible creation date found', fname)
        return False

    iso_val = normalize_date_to_iso8601(raw_val)
    if not iso_val:
        logger.error('%s: could not parse date %r from %s', fname, raw_val, src_tag)
        return False

    logger.info('%s: setting XMP-xmp:CreateDate from %s: %s', fname, src_tag, iso_val)

    if dry_run:
        logger.info('[DRY-RUN] would write XMP-xmp:CreateDate=%s', iso_val)
        return True

    try:
        proc = subprocess.run(
            ['exiftool', '-overwrite_original', f'-XMP-xmp:CreateDate={iso_val}', file_path],
            capture_output=True, text=True, encoding='utf-8', check=True
        )
        if proc.stderr:
            logger.warning('%s: exiftool: %s', fname, proc.stderr.strip())
        return True
    except subprocess.CalledProcessError as e:
        logger.error('%s: failed to write XMP-xmp:CreateDate: %s', fname, e.stderr.strip() if e.stderr else str(e))
        return False
