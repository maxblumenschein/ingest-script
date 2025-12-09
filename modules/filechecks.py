import os
import re
import logging
from PIL import Image
import io

# NOTE: This module expects variables.* lists to be passed into functions or imported by caller if needed.

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff')


class FilenameValidationError(Exception):
    pass


def is_image_file(file_name):
    return file_name.lower().endswith(IMAGE_EXTENSIONS)

# The following validators mirror your previous logic. They assume callers provide the valid_* sets.

def is_valid_first_segment(first_segment, valid_first_chars, valid_other_strings):
    return len(first_segment) == 4 and first_segment[0] in valid_first_chars and first_segment[1:] in valid_other_strings


def is_valid_date_segment(date_segment):
    from datetime import datetime
    try:
        datetime.strptime(date_segment, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def is_valid_id_segment(id_segment, valid_id_initial_chars):
    valid_initials = ''.join(valid_id_initial_chars)
    id_pattern = rf"^\d{{7}}$|^[{valid_initials}]\d{{6}}$"
    parts = id_segment.split('-')
    return all(re.fullmatch(id_pattern, part) for part in parts)


def is_valid_freetext_segment(freetext_segment):
    if freetext_segment.startswith('s-'):
        return False
    return re.fullmatch(r'^[a-z0-9][a-z0-9-]*$', freetext_segment) is not None


def is_valid_suffix_segment(suffix_segment, valid_suffixes):
    if not suffix_segment.startswith('s-'):
        return False
    parts = suffix_segment[2:].split('-')
    for sub in parts:
        if sub in valid_suffixes:
            continue
        elif re.fullmatch(r'\d{3}', sub):
            continue
        else:
            return False
    return True


def pad_array(arr, size, fill=None):
    padded = arr[:size] + [fill] * (size - len(arr))
    return padded + arr[size:]


def is_valid_filename(file_name, valid_first_segment_first_char, valid_first_segment_other_chars, valid_id_initial_chars, valid_suffixes):
    base, _ = os.path.splitext(file_name)
    segments = base.split('_')
    if len(segments) < 2:
        logging.warning('%s: Too few segments', file_name)
        return False, True
    first_segment = segments[0]
    if not is_valid_first_segment(first_segment, valid_first_segment_first_char, valid_first_segment_other_chars):
        logging.warning('%s: Invalid first segment', file_name)
        return False, True
    remaining = segments[1:]
    if not remaining:
        logging.warning('%s: Missing segments after first', file_name)
        return False, True
    if is_valid_id_segment(remaining[0], valid_id_initial_chars):
        if len(remaining) < 2:
            logging.warning('%s: Missing date after ID segment', file_name)
            return False, True
        id_segment, date_segment, *optional = remaining
    else:
        date_segment, *optional = remaining
    if not is_valid_date_segment(date_segment):
        logging.warning('%s: Missing or invalid date segment', file_name)
        return False, True
    if optional:
        if is_valid_suffix_segment(optional[0], valid_suffixes):
            if len(optional) != 1:
                logging.warning('%s: No segment allowed after suffix segment', file_name)
                return False, True
            return True, False
    freetext, suffix, *tail = pad_array(optional, 2, None)
    if freetext and not is_valid_freetext_segment(freetext):
        logging.warning('%s: Invalid freetext segment', file_name)
        return False, True
    if suffix and not is_valid_suffix_segment(suffix, valid_suffixes):
        logging.warning('%s: Invalid suffix segment', file_name)
        return False, True
    if tail:
        logging.warning('%s: Too many segments', file_name)
        return False, True
    return True, False

def is_valid_icc_profile(metadata):
    """
    Valid RGB:  eciRGB v2 ICCv4, eciRGB v2
    Valid Gray: Gray Gamma 2.2
    """
    # try multiple possible tag names
    candidates = [
        metadata.get("ProfileDescription"),
        metadata.get("Profile Description"),
        metadata.get("ICCProfileName"),
        metadata.get("ICC Profile Name"),
    ]

    # pick the first non-empty
    desc = next((c for c in candidates if c), None)
    if not desc:
        return False, "missing ICC profile"

    desc_l = desc.strip().lower()

    # gray
    if "gray gamma 2.2" in desc_l:
        return True, None

    # rgb
    if "ecirgb v2" in desc_l:
        return True, None

    return False, f"invalid ICC profile: {desc}"


def get_metadata_tags(file_path):
    import subprocess, json
    try:
        res = subprocess.run(['exiftool', '-j', file_path], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        return data[0] if data else {}
    except Exception as e:
        logging.error('Failed to read metadata for %s: %s', file_path, e)
        raise


def missing_required_metadata(metadata, required_metadata_tags):
    missing = []
    for tag in required_metadata_tags:
        if tag not in metadata or not metadata[tag]:
            missing.append(tag)
    return missing


def has_required_metadata(metadata, file_name, required_metadata_tags):
    missing = missing_required_metadata(metadata, required_metadata_tags)
    if missing:
        logging.warning('%s: Missing metadata tags: %s', file_name, ', '.join(missing))
        return False
    return True


def delete_empty_dirs(root_dir, logger=None):
    if logger is None:
        logger = logging.getLogger('ingest')
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if not dirnames and not filenames:
            name = os.path.basename(dirpath)
            if not name.startswith(('skipped', 'ingest_skipped', 'log', '__log__')):
                try:
                    os.rmdir(dirpath)
                    logger.info('Deleted empty directory: %s', dirpath)
                except OSError as e:
                    logger.debug('Failed to delete %s: %s', dirpath, e)

def get_destination_subdir(file_name, mode="auto"):
    """
    Determine the subdirectory for a file based on filename and mode.
    Returns a tuple: (category_dir, subdir_name)
    """
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')
    first_segment = segments[0]

    # Default prefix: characters 2-4 (index 1 to 3)
    prefix = first_segment[1:4] if len(first_segment) >= 4 else first_segment[1:]

    # Check if there’s an ID segment
    has_id = len(segments) > 1 and segments[1]  # ID detection can be improved if needed

    if mode == "id":
        if has_id:
            first_id = segments[1].split('-')[0]
            return "IDs", first_id
        else:
            return "noIDs", prefix

    if mode == "prefix":
        return "prefix", prefix

    # auto mode (default behavior)
    if has_id:
        first_id = segments[1].split('-')[0]
        return "IDs", first_id

    return "noIDs", prefix
