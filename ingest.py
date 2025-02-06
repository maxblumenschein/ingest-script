import sys
import os
import shutil
import re
from datetime import datetime, timezone
from PIL import Image
import logging

from variables import SRC, DST, SKIPPED, valid_id_initial_chars, valid_suffixes, valid_first_segment_first_char, valid_first_segment_other_chars

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff')

now = datetime.now(timezone.utc).astimezone()
date_suffix = now.strftime("%Y-%m-%dT%H%M%S")

date_isoformat = now.replace(microsecond=0).isoformat()

log_directory = os.path.join(DST, "log")
os.makedirs(log_directory, exist_ok=True)
log_file_name = f"script_{date_suffix}.log"
log_path = os.path.join(log_directory, log_file_name)
logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

logging.info("Start ingest process")
logging.info(f"Source directory = {SRC}")
logging.info(f"Destination directory = {DST}")

def move_file(src, dst, reason):
    try:
        shutil.move(src, dst)
        logging.info(f"Moved: {src} -> {dst} ({reason})")
    except shutil.Error as e:
        logging.error(f"Error moving {src} to {dst}: {e}")

def is_image_file(file_name):
    return file_name.lower().endswith(IMAGE_EXTENSIONS)

def is_valid_id(id_segment):
    valid_initials = ''.join(valid_id_initial_chars)
    id_pattern = rf"^\d{{7}}$|^[{valid_initials}]\d{{6}}$"
    return re.fullmatch(id_pattern, id_segment) is not None

def is_valid_filename(file_name):
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')

    if len(segments) < 2:
        logging.warning(f"{file_name}: Invalid filename structure")
        return False

    return all([
        is_valid_first_segment(segments[0]),
        is_valid_second_segment(segments[1]),
        (len(segments) <= 2 or is_valid_third_segment(segments[2])),
        (len(segments) <= 3 or is_valid_freetext_segment(segments[3])),
        (len(segments) <= 4 or is_valid_suffix_segment(segments[4]))
    ])

def is_valid_first_segment(first_segment):
    return len(first_segment) == 4 and first_segment[0] in valid_first_segment_first_char and first_segment[1:] in valid_first_segment_other_chars

def is_valid_second_segment(second_segment):
    ids_or_date = second_segment.split('-')
    return all(is_valid_id(part) for part in ids_or_date)

def is_valid_third_segment(third_segment):
    return re.fullmatch(r"^(xxxx|\d{2}x{2}|\d{3}x{1}|\d{4})-(\d{2}|x{2})-(\d{2}|x{2})$", third_segment) is not None

def is_valid_freetext_segment(freetext_segment):
    return re.fullmatch(r"^[a-z][a-z0-9-]*$", freetext_segment) is not None

def is_valid_suffix_segment(suffix_segment):
    return suffix_segment.startswith("s-") and all(sub in valid_suffixes for sub in suffix_segment[2:].split("-"))

def file_check(file_name):
    if not is_image_file(file_name):
        logging.warning(f"{file_name}: Invalid file type")
        return False
    if not is_valid_filename(file_name):
        logging.warning(f"{file_name}: Invalid filename")
        return False
    return True

def process_files():
    skipped_directory = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
    skipped_files = []
    valid_files = []

    for dirpath, _, filenames in os.walk(SRC):
        if dirpath.startswith(os.path.join(SRC, SKIPPED)):
            continue
        for file_name in filenames:
            if file_name == ".DS_Store":
                continue
            file_path = os.path.join(dirpath, file_name)

            if file_check(file_name):
                valid_files.append((file_name, file_path))
            else:
                skipped_files.append(file_path)

    if skipped_files:
        os.makedirs(skipped_directory, exist_ok=True)
        for file_path in skipped_files:
            move_file(file_path, skipped_directory, "Moved to skipped")

    for file_name, file_path in valid_files:
        dst_directory_name = file_name[1:4] if len(file_name) > 3 else file_name[1:]
        dst_directory = os.path.join(DST, dst_directory_name)
        os.makedirs(dst_directory, exist_ok=True)
        dst_file_path = os.path.join(dst_directory, file_name)

        if os.path.exists(dst_file_path):
            logging.warning(f"{file_name} already exists at destination, moving to skipped folder.")
            if not skipped_files:
                os.makedirs(skipped_directory, exist_ok=True)
            move_file(file_path, skipped_directory, "Moved to skipped (file already exists)")
        else:
            move_file(file_path, dst_directory, "Moved to destination")

    if os.path.exists(skipped_directory) and not os.listdir(skipped_directory):
        os.rmdir(skipped_directory)

def main():
    process_files()
    logging.info("Done")

if __name__ == "__main__":
    main()
