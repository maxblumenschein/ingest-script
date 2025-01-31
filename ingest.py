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
        logging.info(f"Directory created: {path}")
    except OSError as e:
        logging.error(f"Error creating directory {path}: {e}")

def move_file(src, dst, reason):
    """Move a file and log the reason."""
    try:
        shutil.move(src, dst)
        logging.info(f"Moved: {src} -> {dst} ({reason})")
    except shutil.Error as e:
        logging.error(f"Error moving {src} to {dst}: {e}")

def is_image_file(file_name):
    """Check if the file is an image."""
    return file_name.lower().endswith(IMAGE_EXTENSIONS)

def has_icc_profile(filepath):
    """Check if the image has an ICC profile."""
    try:
        with Image.open(filepath) as img:
            return 'icc_profile' in img.info
    except IOError:
        return False

def is_valid_id(id_segment):
    """Validate individual ID according to the patterns."""
    valid_initials = ''.join(valid_id_initial_chars)
    id_pattern = rf"^\d{{7}}$|^[{valid_initials}]\d{{6}}$"
    return re.fullmatch(id_pattern, id_segment) is not None

def is_valid_filename(file_name):
    """Check if the filename matches the required pattern."""
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')

    if len(segments) < 2:
        logging.warning(f"{file_name}: Invalid filename structure")
        return False

    if not is_valid_first_segment(segments[0]):
        return False

    if not is_valid_second_segment(segments[1]):
        return False

    if len(segments) > 2 and not is_valid_third_segment(segments[2]):
        return False

    if len(segments) > 3 and not is_valid_freetext_segment(segments[3]):
        return False

    if len(segments) > 4 and not is_valid_suffix_segment(segments[4]):
        return False

    return True

def is_valid_first_segment(first_segment):
    """Validate the first segment of the filename."""
    return len(first_segment) == 4 and \
           first_segment[0] in valid_first_segment_first_char and \
           first_segment[1:] in valid_first_segment_other_chars

def is_valid_second_segment(second_segment):
    """Validate the second segment of the filename."""
    ids_or_date = second_segment.split('-')
    return all(is_valid_id(part) for part in ids_or_date)

def is_valid_third_segment(third_segment):
    """Validate the third segment (date) of the filename."""
    date_pattern = r"^(xxxx|\d{2}x{2}|\d{3}x{1}|\d{4})-(\d{2}|x{2})-(\d{2}|x{2})$"
    return re.fullmatch(date_pattern, third_segment) is not None

def is_valid_freetext_segment(freetext_segment):
    """Validate the freetext segment."""
    return re.fullmatch(r"^[a-z][a-z0-9-]*$", freetext_segment) is not None

def is_valid_suffix_segment(suffix_segment):
    """Validate the suffix segment."""
    return suffix_segment.startswith("s-") and \
           all(is_valid_sub_suffix(sub_suffix) for sub_suffix in suffix_segment[2:].split("-"))

def is_valid_sub_suffix(sub_suffix):
    """Validate a sub-suffix in the suffix segment."""
    return sub_suffix in valid_suffixes

def file_check(file_name):
    """Check if the file is a valid image and filename."""
    if not is_image_file(file_name):
        logging.warning(f"{file_name}: Invalid file type")
        return False
    if not is_valid_filename(file_name):
        logging.warning(f"{file_name}: Invalid filename")
        return False
    return True

def process_files():
    """Process files from the source directory."""
    skipped_directory = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
    create_directory_if_not_exists(skipped_directory)

    for dirpath, dirnames, filenames in os.walk(SRC):
        if dirpath.startswith(os.path.join(SRC, SKIPPED)):
            continue
        for file_name in filenames:
            if file_name == ".DS_Store":
                continue
            file_path = os.path.join(dirpath, file_name)

            # Check if file already exists in destination
            dst_directory_name = file_name[1:4] if len(file_name) > 3 else file_name[1:]
            dst_directory = os.path.join(DST, dst_directory_name)
            create_directory_if_not_exists(dst_directory)
            dst_file_path = os.path.join(dst_directory, file_name)

            if os.path.exists(dst_file_path):
                logging.warning(f"{file_name} already exists at destination, moving to skipped folder.")
                move_file(file_path, skipped_directory, "Moved to skipped (file already exists)")
            elif file_check(file_name):
                move_file(file_path, dst_directory, "Moved to destination")
            else:
                move_file(file_path, skipped_directory, "Moved to skipped")

    cleanup_empty_directories()

def cleanup_empty_directories():
    """Remove empty directories after file processing."""
    for dirpath, dirnames, filenames in os.walk(SRC, topdown=False):
        if dirpath.startswith(os.path.join(SRC, SKIPPED)):
            continue
        for file_name in filenames:
            file_path = os.path.join(dirpath, file_name)
            if file_name == ".DS_Store":
                os.remove(file_path)
                logging.info(f"Removed .DS_Store file: {file_path}")
            else:
                logging.warning(f"Unexpected file {file_path}")
        for dirname in dirnames:
            dir_path = os.path.join(dirpath, dirname)
            try:
                os.rmdir(dir_path)
                logging.info(f"Removed empty directory: {dir_path}")
            except OSError:
                logging.info(f"Skipped non-empty directory: {dir_path}")

def main():
    """Main function to start the file processing."""
    process_files()
    logging.info("Done")

if __name__ == "__main__":
    main()
