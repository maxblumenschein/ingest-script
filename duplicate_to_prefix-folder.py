import os
import shutil
import re

from datetime import datetime
from variables import match

SRC = "path/to/source/directory"
DST = "path/to/destination/directory"
SKIPPED = "skipped_files"

# create DST path
if not os.path.isdir(DST):
    os.makedirs(DST, exist_ok=True)

# Generate the skipped files subdirectory name with the current date and time as suffix
# Get the current date and time
now = datetime.now()
date_suffix = now.isoformat(timespec='seconds')
skipped_subfolder_name = SKIPPED + '_' + date_suffix
skipped_subfolder = os.path.join(SRC, skipped_subfolder_name)

# create SKIPPED path
if not os.path.isdir(skipped_subfolder):
    os.makedirs(skipped_subfolder, exist_ok=True)

# loop on all files and get the folder name that each file is supposed to move to
for dirpath, dirnames, filenames in os.walk(SRC):
    if dirpath.startswith(os.path.join(SRC, SKIPPED)):
        continue
    for file_name in filenames:
        file_path = os.path.join(dirpath, file_name)
        if file_name == ".DS_Store":
            continue

        # check with 'medienstandard-kategorien.txt' if it is one of the files we are looking for
        if any(re.findall('|'.join(match), file_name)):
            # extract folder name
            folder_name = file_name.split("_")[0][1:4]
            # create folder if it doesn't exist
            if not os.path.isdir(os.path.join(DST, folder_name)):
                os.mkdir(os.path.join(DST, folder_name))
            # if file doesn't exist copy the file
            if not os.path.isfile(os.path.join(DST, folder_name, file_name)):
                # copy the file with metadata
                shutil.copy2(file_path, os.path.join(DST, folder_name))
                print(f"Copied {file_path} (conform) to {DST, folder_name}")
                os.remove(file_path)
            else:
                shutil.move(file_path, skipped_subfolder)
                print(f"Skipped {file_path} (conform); moved to {skipped_subfolder}")
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
