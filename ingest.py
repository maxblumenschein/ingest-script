import sys
import os
import shutil
import re
from datetime import datetime, timezone
from PIL import Image
import logging

# Assuming these are specific imports required from 'variables'
from variables import SRC, DST, SKIPPED, valid_id_initial_chars, valid_suffixes, valid_first_segment_first_char, valid_first_segment_other_chars

# Configuration
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff')

# Get the current date and time
now = datetime.now(timezone.utc).astimezone()
date_suffix = now.strftime("%Y-%m-%dT%H%M%S")
date_isoformat = now.replace(microsecond=0).isoformat()

# Set up logging
log_directory = os.path.join(DST, "log")
os.makedirs(log_directory, exist_ok=True)
log_file_name = f"script_{date_suffix}.log"
log_path = os.path.join(log_directory, log_file_name)
logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

logging.info("Start ingest process")
logging.info(f"Source directory = {SRC}")
logging.info(f"Destination directory = {DST}")

def create_directory_if_not_exists(path):
    """Create a directory if it does not exist."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        logging.error(f"Error creating directory {path}: {e}")

def move_file(src, dst, reason):
    """Move a file and log the reason."""
    try:
        shutil.move(src, dst)
        logging.info(f"{src} -> {dst} ({reason})")
    except shutil.Error as e:
        logging.error(f"Error moving {src} to {dst}: {e}")

def is_image_file(file_name):
    return file_name.lower().endswith(IMAGE_EXTENSIONS)

def has_icc_profile(filepath):
    try:
        with Image.open(filepath) as img:
            return 'icc_profile' in img.info
    except IOError:
        return False

def is_valid_id(id_segment):
    """ Validate individual ID according to the patterns. """
    valid_initials = ''.join(valid_id_initial_chars)
    id_pattern = rf"^\d{{7}}$|^[{valid_initials}]\d{{6}}$"  # ID can be 7 digits or 6 digits preceded by valid initial character
    return re.fullmatch(id_pattern, id_segment) is not None

def is_valid_filename(file_name):
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')

    if len(segments) < 2:
        return False

    # First segment validation
    first_segment = segments[0]
    if len(first_segment) != 4 or first_segment[0] not in valid_first_segment_first_char or first_segment[1:] not in valid_first_segment_other_chars:
        return False

    # Second segment validation (IDs or date)
    second_segment = segments[1]
    ids_or_date = second_segment.split('-')

    # Check if each part is a valid ID
    if not all(is_valid_id(part) for part in ids_or_date):
        return False

    # Third segment validation (date)
    if len(segments) > 2:
        third_segment = segments[2]
        date_pattern = r"^(xxxx|\d{2}x{2}|\d{3}x{1}|\d{4})-(\d{2}|x{2})-(\d{2}|x{2})$"
        if not re.fullmatch(date_pattern, third_segment):
            return False

    # Freetext segment validation (optional)
    freetext_index = 3 if len(segments) > 3 else None
    if freetext_index and len(segments) > freetext_index:
        freetext_segment = segments[freetext_index]
        if not re.fullmatch(r"^[a-z][a-z0-9-]*$", freetext_segment):
            return False

    # Suffix segment validation (optional)
    suffix_index = freetext_index + 1 if freetext_index else 3
    if len(segments) > suffix_index:
        suffix_segment = segments[suffix_index]
        if not suffix_segment.startswith("s-"):
            return False
        sub_suffixes = suffix_segment[2:].split("-")
        if any(not is_valid_sub_suffix(sub_suffix) for sub_suffix in sub_suffixes):
            return False

    return True

def file_check(file_name):
    if not is_image_file(file_name):
        logging.warning(f"{file_name} = invalid filetype")
        return False

    if not is_valid_filename(file_name):
        logging.warning(f"{file_name} = invalid filename")
        return False

    return True

def process_files():
    skipped_directory = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
    for dirpath, dirnames, filenames in os.walk(SRC):
        if dirpath.startswith(os.path.join(SRC, SKIPPED)):
            continue
        for file_name in filenames:
            if file_name == ".DS_Store":
                continue
            file_path = os.path.join(dirpath, file_name)
            if file_check(file_name):
                dst_directory_name = file_name[1:4] if len(file_name) > 3 else file_name[1:]
                dst_directory = os.path.join(DST, dst_directory_name)
                create_directory_if_not_exists(dst_directory)
                move_file(file_path, dst_directory, "MOVED to destination")
            else:
                create_directory_if_not_exists(skipped_directory)
                move_file(file_path, skipped_directory, "MOVED to skipped")

    for dirpath, dirnames, filenames in os.walk(SRC, topdown=False):
        if dirpath.startswith(os.path.join(SRC, SKIPPED)):
            continue
        for file_name in filenames:
            file_path = os.path.join(dirpath, file_name)
            if file_name == ".DS_Store":
                os.remove(file_path)
            else:
                logging.warning(f"Unexpected file {file_path}")
        for dirname in dirnames:
            dir_path = os.path.join(dirpath, dirname)
            try:
                os.rmdir(dir_path)
                logging.info(f"REMOVED empty directory {dir_path}")
            except OSError:
                logging.info(f"SKIPPED directory not empty {dir_path}")

def main():
    process_files()
    logging.info("Done")

if __name__ == "__main__":
    main()
