import os
from modules.filechecks import (
    get_destination_subdir,
    is_image_file,
    is_valid_filename,
    get_metadata_tags,
    has_required_metadata,
    is_valid_icc_profile
)
from modules.imageops import can_create_jpg_derivative


def build_plan(src_root, dst_root, subdir_mode, logger):
    """
    Walk the source directory and build an ingest plan.
    Files are validated for:
      - image type
      - filename structure
      - required metadata
      - ICC profile
      - derivative creation possibility
    Returns a tuple: (planned_files_list, skipped_files_list)
    """
    planned = []
    skipped = []

    from variables import (
        valid_first_segment_first_char,
        valid_first_segment_other_chars,
        valid_id_initial_chars,
        valid_suffixes,
        required_metadata_tags
    )

    for dirpath, dirnames, filenames in os.walk(src_root):

        # ---------------------------------------------------------
        # Skip skipped directories and log folder
        # ---------------------------------------------------------
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith("skipped") and d != "__log__"
        ]

        # ---------------------------------------------------------
        # Ignore log files and system files
        # ---------------------------------------------------------
        filenames = [
            f for f in filenames
            if not f.lower().endswith(".log") and f != ".DS_Store"
        ]

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)

            # ---------------------------------------------------------
            # Only image files are valid ingest targets
            # ---------------------------------------------------------
            if not is_image_file(fname):
                skipped.append((fpath, 'invalid file type'))
                continue

            # ---------------------------------------------------------
            # Filename validation
            # ---------------------------------------------------------
            valid, _ = is_valid_filename(
                fname,
                valid_first_segment_first_char,
                valid_first_segment_other_chars,
                valid_id_initial_chars,
                valid_suffixes
            )
            if not valid:
                skipped.append((fpath, 'invalid filename'))
                continue

            # ---------------------------------------------------------
            # Metadata validation
            # ---------------------------------------------------------
            try:
                metadata = get_metadata_tags(fpath)
            except Exception:
                skipped.append((fpath, 'metadata read error'))
                continue

            if not has_required_metadata(metadata, fname, required_metadata_tags):
                skipped.append((fpath, 'missing required metadata'))
                continue

            # ---------------------------------------------------------
            # ICC profile check
            # ---------------------------------------------------------
            icc_ok, icc_reason = is_valid_icc_profile(metadata)
            if not icc_ok:
                skipped.append((fpath, icc_reason))
                continue

            # ---------------------------------------------------------
            # Determine destination path
            # ---------------------------------------------------------
            category_dir, subdir_name = get_destination_subdir(fname, subdir_mode)
            primary_directory = os.path.join(dst_root, 'primary', category_dir, subdir_name)
            derivative_directory = os.path.join(dst_root, 'derivative', category_dir, subdir_name)
            dst_file = os.path.join(primary_directory, fname)

            if os.path.exists(dst_file):
                skipped.append((fpath, 'exists at destination'))
                continue

            # ---------------------------------------------------------
            # Can we generate a JPG derivative?
            # ---------------------------------------------------------
            if not can_create_jpg_derivative(fpath, fname):
                skipped.append((fpath, 'cannot create derivative'))
                continue

            # ---------------------------------------------------------
            # Add to ingest plan
            # ---------------------------------------------------------
            planned.append({
                'src': fpath,
                'dst': dst_file,
                'fname': fname,
                'derivative_dir': derivative_directory
            })

    return planned, skipped
