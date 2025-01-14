import sys
import os
import shutil
import re

from variables import *
from datetime import datetime, timezone
from PIL import Image

# Get the directory of the main script
script_dir = os.path.dirname(__file__)

# create DST path
if not os.path.isdir(DST):
    os.makedirs(DST, exist_ok=True)

# Get the current date and time
now = datetime.now(timezone.utc).astimezone()
date_suffix = now.strftime("%Y-%m-%dT%H%M%S")
date_isoformat = datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()

# Specify the log destination directory and log file name
log_directory = os.path.join(DST, "log")
log_file_name = "script_" + date_suffix + ".log"

# Ensure the log directory exists
os.makedirs(log_directory, exist_ok=True)

# Create the full path to the log file
log_path = os.path.join(log_directory, log_file_name)

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()  # Ensure it's written immediately

    def flush(self):
        pass

# Redirect stdout and stderr to the log file
sys.stdout = Logger(log_path)
sys.stderr = Logger(log_path)

# Generate the skipped files subdirectory name with the current date and time as suffix
skipped_directory_name = SKIPPED + '_' + date_suffix
skipped_directory = os.path.join(SRC, skipped_directory_name)

# annotate log-file
print(f"{date_isoformat} [info         ] Start ingest process \n"
      f"{date_isoformat} [info         ] Source directory = {SRC} \n"
      f"{date_isoformat} [info         ] Destination directory = {DST}"
    )

# File check
def is_image_file(file_name):
    # List of image file extensions
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff')
    return file_name.lower().endswith(image_extensions)

def is_valid_id(id_segment):
    """ Validate individual ID according to the patterns. """
    valid_initials = ''.join(valid_id_initial_chars)
    id_pattern = rf"^\d{{7}}$|^[{valid_initials}]\d{{6}}$"  # ID can be 7 digits or 6 digits preceded by valid initial character
    return re.fullmatch(id_pattern, id_segment) is not None

def is_valid_sub_suffix(sub_suffix):
    """ Validate each sub-suffix to allow either valid suffixes or a 3-digit serial number. """
    return sub_suffix in valid_suffixes or re.fullmatch(r"^\d{3}$", sub_suffix) is not None

# check filename for segment syntax
def is_valid_filename(file_name):
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')
    valid_segments = []

    # Check first segment
    if len(segments) < 2:
        return False

    first_segment = segments[0]
    if (len(first_segment) != 4 or
        first_segment[0] not in valid_first_segment_first_char or
        first_segment[1:] not in valid_first_segment_other_chars):
        return False

    # Check second segment (IDs or date)
    second_segment = segments[1]
    date_pattern = r"^(xxxx|\d{2}x{2}|\d{3}x{1}|\d{4})-(\d{2}|x{2})-(\d{2}|x{2})$"  # Date format with optional 'x'

    ids_or_date = second_segment.split('-')
    if len(ids_or_date) > 1:
        # If multiple IDs are provided, each should be valid
        if not all(is_valid_id(id_part) for id_part in ids_or_date):
            return False
        is_id = True
    else:
        is_id = is_valid_id(second_segment)
        is_date = re.fullmatch(date_pattern, second_segment)
        if not is_id and not is_date:
            return False

    # Check third segment if second segment is ID(s)
    if is_id and len(segments) > 2:
        third_segment = segments[2]
        if not re.fullmatch(date_pattern, third_segment):
            return False

    # Check freetext segment
    freetext_index = 3 if is_id else 2
    if len(segments) > freetext_index:
        freetext_segment = segments[freetext_index]
        if not re.fullmatch(r"^[a-z][a-z0-9-]*$", freetext_segment):
            return False

    # Check suffix segment
    suffix_index = freetext_index + 1 if len(segments) > freetext_index else freetext_index
    if len(segments) > suffix_index:
        suffix_segment = segments[suffix_index]

        # Ensure the suffix segment starts with "s-"
        if not suffix_segment.startswith("s-"):
            return False

        # Split the suffix segment into sub-suffixes based on the "-" delimiter
        sub_suffixes = suffix_segment[2:].split("-")

        # Validate each sub-suffix
        if any(not is_valid_sub_suffix(sub_suffix) for sub_suffix in sub_suffixes):
            return False

    return True

def has_icc_profile(filepath):
    try:
        with Image.open(filepath) as img:
            if img.info.get('icc_profile'):
                return True
            else:
                return False
    except IOError:
        return False

def file_check(file_name):
    if not is_image_file(file_name):
        print(f"{date_isoformat} [warning      ] {file_name} = invalid filetype")
        return False

    if not is_valid_filename(file_name):
        print(f"{date_isoformat} [warning      ] {file_name} = invalid filename")
        return False

    if not has_icc_profile(file_path):
        print(f"{date_isoformat} [warning      ] {file_name} = missing ICC profile")
        return False

    return True

# loop on all files and get the folder name that each file is supposed to move to
for dirpath, dirnames, filenames in os.walk(SRC):
    # skip directories that start with SKIPPED
    if dirpath.startswith(os.path.join(SRC, SKIPPED)):
        continue
    # skip ".DS_Store" files
    for file_name in filenames:
        file_path = os.path.join(dirpath, file_name)
        if file_name == ".DS_Store":
            continue
        # check if it is one of the files we are looking for
        if file_check(file_name):
            # extract folder name
            dst_directory_name = file_name[1:4] if len(file_name) > 3 else file_name[1:]
            # create folder if it doesn't exist
            dst_directory = os.path.join(DST, dst_directory_name)
            if not os.path.isdir(dst_directory):
                os.mkdir(dst_directory)
            # if file doesn't already exist move the file
            if not os.path.isfile(os.path.join(dst_directory, file_name)):
                shutil.move(file_path, dst_directory)
                print(f"{date_isoformat} [info         ] {file_name} = [conform      ] ––> MOVED to {dst_directory}")
            # if file does already exist move file into SKIPPED path
            else:
                if not os.path.isdir(skipped_directory):
                    os.makedirs(skipped_directory, exist_ok=True)
                shutil.move(file_path, skipped_directory)
                print(f"{date_isoformat} [warning      ] {file_name} = [conform      ] ––> SKIPPED already exists in destination directory ––> MOVED to {skipped_directory}")
        # if file does not conform move file into SKIPPED path
        else:
            if not os.path.isdir(skipped_directory):
                os.makedirs(skipped_directory, exist_ok=True)
            shutil.move(file_path, skipped_directory)
            print(f"{date_isoformat} [warning      ] {file_name} = [not conform  ] ––> MOVED to {skipped_directory}")

# clean-up SRC except "skipped_files"-folder
for dirpath, dirnames, filenames in os.walk(SRC, topdown=False):
    # Skip the excluded folder and its subdirectories
    if dirpath.startswith(os.path.join(SRC, SKIPPED)):
        continue

    # Process files
    for file_name in filenames:
        file_path = os.path.join(dirpath, file_name)
        if file_name == ".DS_Store":
            os.remove(file_path)
        else:
            raise Exception(f"{date_isoformat} [warning      ] Unexpected file {file_path}")

    # Process directories
    for dirname in dirnames:
        dir_path = os.path.join(dirpath, dirname)
        try:
            os.rmdir(dir_path)
            print(f"{date_isoformat} [info         ] REMOVED empty directory {dir_path}")
        except OSError:
            # The directory is not empty
            print(f"{date_isoformat} [info         ] SKIPPED directory not empty {dir_path}")
print(f"{date_isoformat} [info         ] Done")
