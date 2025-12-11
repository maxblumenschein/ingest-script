import os
from modules.filechecks import (
    get_destination_subdir,
    is_image_file,
    is_valid_filename,
    get_metadata_tags,
    is_valid_icc_profile
)
from modules.imageops import can_create_jpg_derivative


def build_plan(src_root, dst_root, subdir_mode, logger):
    """
    Planner validates:
      - file type
      - filename
      - ICC profile
      - derivative creation
    It does NOT validate metadata anymore (validation happens post-write).
    """

    planned = []
    skipped = []

    from variables import (
        valid_first_segment_first_char,
        valid_first_segment_other_chars,
        valid_id_initial_chars,
        valid_suffixes,
    )

    for dirpath, dirnames, filenames in os.walk(src_root):

        # Skip skipped dirs and log dirs
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith("skipped") and d != "__log__"
        ]

        # Filter out useless files
        filenames = [
            f for f in filenames
            if not f.lower().endswith(".log") and f != ".DS_Store"
        ]

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)

            # Must be an image
            if not is_image_file(fname):
                skipped.append((fpath, "invalid file type"))
                continue

            # Filename validation
            valid, _ = is_valid_filename(
                fname,
                valid_first_segment_first_char,
                valid_first_segment_other_chars,
                valid_id_initial_chars,
                valid_suffixes,
            )
            if not valid:
                skipped.append((fpath, "invalid filename"))
                continue

            # Metadata NOT validated here anymore

            # ICC profile check
            try:
                metadata = get_metadata_tags(fpath)
            except Exception:
                skipped.append((fpath, "metadata read error"))
                continue

            icc_ok, icc_reason = is_valid_icc_profile(metadata)
            if not icc_ok:
                skipped.append((fpath, icc_reason))
                continue

            # Destination path
            category_dir, subdir_name = get_destination_subdir(fname, subdir_mode)
            primary_directory = os.path.join(dst_root, "primary", category_dir, subdir_name)
            derivative_directory = os.path.join(dst_root, "derivative", category_dir, subdir_name)
            dst_file = os.path.join(primary_directory, fname)

            if os.path.exists(dst_file):
                skipped.append((fpath, "exists at destination"))
                continue

            # Derivative check
            if not can_create_jpg_derivative(fpath, fname):
                skipped.append((fpath, "cannot create derivative"))
                continue

            # Add to plan
            planned.append(
                {
                    "src": fpath,
                    "dst": dst_file,
                    "fname": fname,
                    "derivative_dir": derivative_directory,
                }
            )

    return planned, skipped
