import os
script_dir = os.path.dirname(__file__)
SRC = os.path.join(script_dir, 'test_source')
DST = os.path.join(script_dir, 'test_destination')
SKIPPED = 'skipped_files'

# How to organize subdirectories:
#  - "id"     = group by ID segment
#  - "prefix" = group by characters 2–4 of first segment
#  - "auto"   = current behavior (id if present, otherwise prefix)
SUBDIR_MODE = 'prefix'

# load resources
with open(os.path.join(script_dir, 'resources', 'ms-zustaendigkeit.txt'), encoding='utf-8') as f:
    valid_first_segment_first_char = [line.strip() for line in f if line.strip()]
with open(os.path.join(script_dir, 'resources', 'ms-kategorien.txt'), encoding='utf-8') as f:
    valid_first_segment_other_chars = [line.strip() for line in f if line.strip()]
with open(os.path.join(script_dir, 'resources', 'ms-id.txt'), encoding='utf-8') as f:
    valid_id_initial_chars = [line.strip() for line in f if line.strip()]
with open(os.path.join(script_dir, 'resources', 'ms-suffix.txt'), encoding='utf-8') as f:
    valid_suffixes = [line.strip() for line in f if line.strip()]
with open(os.path.join(script_dir, 'resources', 'ms-metadata-tags.txt'), encoding='utf-8') as f:
    required_metadata_tags = [
        line.strip()
        for line in f
        if line.strip() and not line.strip().startswith('#')
    ]
