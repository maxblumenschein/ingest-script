import os

# Get the directory of the script
script_dir = os.path.dirname(__file__)

# Define variables
SRC = os.path.join(script_dir, "test_source") # define source directory
DST = os.path.join(script_dir, "test_destination") # define destination directory
SKIPPED = "skipped_files" # define directory name for skipped files

# Define file-check-lists
first_characters = open(os.path.join(script_dir, 'medienstandard-zustaendigkeit.txt')).read().splitlines()
second_forth_characters = open(os.path.join(script_dir, 'medienstandard-kategorien.txt')).read().splitlines()
