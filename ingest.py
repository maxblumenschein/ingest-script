#!/usr/bin/env python3
"""CLI entrypoint for ingest pipeline."""
import argparse
import logging
import os
import shutil
import sys
from datetime import datetime, timezone

# Setup project root and module import path
PROJECT_ROOT = os.path.dirname(__file__)
MODULES_DIR = os.path.join(PROJECT_ROOT, 'modules')
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

from variables import SRC, DST, SKIPPED, SUBDIR_MODE, required_metadata_tags
from modules.logging_utils import setup_logging
from modules.metadata import load_preset_for_code, MetadataPresetError
from modules.planner import build_plan
from modules.fileops import move_file
from modules.exifwriter import has_exiftool, write_metadata_to_file
from modules.filechecks import delete_empty_dirs
from modules.imageops import create_jpg_derivative, can_create_jpg_derivative

# CLI & logging
now = datetime.now(timezone.utc).astimezone()
date_suffix = now.strftime("%Y-%m-%dT%H%M%S")
log_dir = os.path.join(DST, "__log__")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"ingest_{date_suffix}.log")

logger = setup_logging(log_file)
logger.info("Starting ingest")
logger.info(f"SRC={SRC} DST={DST}")


def main():
    parser = argparse.ArgumentParser(description="Modular ingest pipeline")
    parser.add_argument('author_code', nargs='?', default=None,
                        help='Three-letter author code (e.g. AZT)')
    parser.add_argument('--skip-metadata', action='store_true')
    parser.add_argument('--metadata-only', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    resources_dir = os.path.join(PROJECT_ROOT, 'resources')
    exif_args = None

    # Load metadata preset if not skipped
    if args.author_code and not args.skip_metadata:
        try:
            exif_args = load_preset_for_code(args.author_code, resources_dir, required_metadata_tags)
            logger.info("Loaded preset for %s", args.author_code)
        except MetadataPresetError as e:
            logger.error("Preset load/validation failed: %s", e)
            sys.exit(2)

    if args.metadata_only and args.skip_metadata:
        logger.error("--metadata-only and --skip-metadata are incompatible")
        sys.exit(2)

    # Build ingest plan
    metadata_required = args.skip_metadata  # Only enforce metadata when skipping metadata write
    plan, skipped = build_plan(SRC, DST, SUBDIR_MODE, logger, metadata_required=metadata_required)

    # Move skipped files
    if skipped:
        skipped_dir = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
        os.makedirs(skipped_dir, exist_ok=True)
        for path, reason in skipped:
            move_file(path, skipped_dir, reason, dry_run=args.dry_run, logger=logger)

    logger.info("Planned operations: %d", len(plan))

    # Metadata-only mode
    if args.metadata_only:
        if not exif_args:
            logger.error("metadata-only requested but no preset loaded")
            sys.exit(2)
        if not has_exiftool():
            logger.error("exiftool not available")
            sys.exit(2)
        for item in plan:
            target = item['src']
            write_metadata_to_file(target, exif_args, dry_run=args.dry_run, logger=logger)
        logger.info("metadata-only completed")
        return

    # Normal ingest loop
    for item in plan:
        os.makedirs(os.path.dirname(item['dst']), exist_ok=True)
        os.makedirs(item['derivative_dir'], exist_ok=True)
        try:
            # Move file to destination
            move_file(item['src'], item['dst'], 'validated move', dry_run=args.dry_run, logger=logger)

            # Write metadata if available
            if exif_args and not args.skip_metadata:
                if not has_exiftool():
                    logger.error("exiftool not found; skipping metadata write")
                else:
                    write_metadata_to_file(item['dst'], exif_args, dry_run=args.dry_run, logger=logger)

            # Create derivative image
            if not args.dry_run:
                create_jpg_derivative(item['dst'], item['derivative_dir'], item['fname'], logger=logger)

        except Exception as e:
            logger.error("Operation failed for %s: %s", item['fname'], e)

    # Cleanup skipped directory if empty
    skipped_dir = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
    if os.path.exists(skipped_dir) and not os.listdir(skipped_dir):
        try:
            os.rmdir(skipped_dir)
        except OSError:
            pass

    # Copy log to SRC/__log__
    try:
        inlog = os.path.join(SRC, '__log__')
        os.makedirs(inlog, exist_ok=True)
        shutil.copy2(log_file, os.path.join(inlog, os.path.basename(log_file)))
        logger.info("Copied log to %s", inlog)
    except Exception:
        logger.exception("Failed to copy log")

    # Delete empty directories
    delete_empty_dirs(SRC, logger)
    logger.info("Ingest done")


if __name__ == '__main__':
    main()
