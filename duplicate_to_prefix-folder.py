import sys
import os
import shutil
import re

from datetime import datetime
from variables import match

# Get the directory of the main script
script_dir = os.path.dirname(__file__)

SRC = os.path.join(script_dir, "test_source") # define SRC directory
DST = os.path.join(script_dir, "test_destination") # define SRC directory
SKIPPED = "skipped_files" # define directory name for skipped files

# create DST path
if not os.path.isdir(DST):
    os.makedirs(DST, exist_ok=True)

# Get the current date and time
now = datetime.now()
date_suffix = now.isoformat(timespec='seconds')

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
skipped_subfolder_name = SKIPPED + '_' + date_suffix
skipped_subfolder = os.path.join(SRC, skipped_subfolder_name)

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

        # check with list "match" if it is one of the files we are looking for
        if any(re.findall('|'.join(match), file_name)):
            # extract folder name
            folder_name = file_name.split("_")[0][1:4]
            # create folder if it doesn't exist
            if not os.path.isdir(os.path.join(DST, folder_name)):
                os.mkdir(os.path.join(DST, folder_name))
            # if file doesn't already exist copy the file
            if not os.path.isfile(os.path.join(DST, folder_name, file_name)):
                # copy the file with metadata
                shutil.copy2(file_path, os.path.join(DST, folder_name))
                print(f"Copied {file_path} (conform) to {DST, folder_name}")
                os.remove(file_path)
            # if file does already exist move file into SKIPPED path
            else:
                if not os.path.isdir(skipped_subfolder):
                    os.makedirs(skipped_subfolder, exist_ok=True)
                shutil.move(file_path, skipped_subfolder)
                print(f"Skipped {file_path} (conform); moved to {skipped_subfolder}")
        # if file does conform with list "match" move file into SKIPPED path
        else:
            if not os.path.isdir(skipped_subfolder):
                os.makedirs(skipped_subfolder, exist_ok=True)
            shutil.move(file_path, skipped_subfolder)
            print(f"Skipped {file_path} (not conform); moved to {skipped_subfolder}")

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
            raise Exception(f"Unexpected file {file_path}")

    # Process directories
    for dirname in dirnames:
        dir_path = os.path.join(dirpath, dirname)
        try:
            os.rmdir(dir_path)
            print(f"Removed empty directory: {dir_path}")
        except OSError:
            # The directory is not empty
            print(f"Directory not empty, skipping: {dir_path}")
