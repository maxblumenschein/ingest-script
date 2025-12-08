import os

# Get the directory of the script
script_dir = os.path.dirname(__file__)

# Define variables
SRC = os.path.join(script_dir, "test_source") # define source directory
DST = os.path.join(script_dir, "test_destination") # define destination directory
SKIPPED = "skipped_files"  # define directory name for skipped files

# How to organize subdirectories:
#  - "id"     = group by ID segment
#  - "prefix" = group by characters 2–4 of first segment
#  - "auto"   = current behavior (id if present, otherwise prefix)
SUBDIR_MODE = "prefix"

# Define file-check-lists
valid_first_segment_first_char = open(os.path.join(
    # Replace with actual valid first characters
    script_dir, 'resources', 'ms-zustaendigkeit.txt')).read().splitlines()
# Replace with actual valid strings for the next three characters
valid_first_segment_other_chars = open(os.path.join(
    script_dir, 'resources', 'ms-kategorien.txt')).read().splitlines()
# Replace with actual valid initial characters for IDs
valid_id_initial_chars = open(os.path.join(
    script_dir, 'resources', 'ms-id.txt')).read().splitlines()
valid_suffixes = open(os.path.join(script_dir, 'resources', 'ms-suffix.txt')
                      # Replace with actual valid suffixes
                      ).read().splitlines()
required_metadata_tags = open(os.path.join(
    script_dir, 'resources', 'ms-metadata-tags.txt')).read().splitlines()
