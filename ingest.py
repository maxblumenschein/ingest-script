#!/usr/bin/env python3
"""CLI entrypoint for ingest pipeline."""

import argparse
import os
import shutil
import sys
import warnings
from collections import Counter
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(__file__)
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

from PIL import Image

warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = 405_000_000

from modules.exifwriter import ensure_xmp_create_date, has_exiftool, write_metadata_to_file
from modules.filechecks import delete_empty_dirs, get_metadata_tags, has_required_metadata, is_image_file
from modules.fileops import move_file
from modules.imageops import create_jpg_derivative
from modules.logging_utils import setup_logging
from modules.metadata import MetadataPresetError, load_preset_for_code
from modules.planner import build_plan
from variables import DST, SKIPPED, SRC, SUBDIR_MODE, required_metadata_tags

# === Logging ===
now = datetime.now(timezone.utc).astimezone()
date_suffix = now.strftime("%Y-%m-%dT%H%M%S")
log_dir = os.path.join(DST, "__log__")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"ingest_{date_suffix}.log")
logger = setup_logging(log_file)
logger.info("Starting ingest  SRC=%s  DST=%s", SRC, DST)


# === Terminal UI helpers ===

def _progress(current, total, fname):
    width = 28
    filled = int(width * current / total) if total > 0 else width
    bar = '█' * filled + '░' * (width - filled)
    label = fname if len(fname) <= 42 else fname[:39] + '…'
    print(f'\r  [{bar}] {current}/{total}  {label:<43}', end='', flush=True)


def _finish():
    try:
        inlog = os.path.join(SRC, "__log__")
        os.makedirs(inlog, exist_ok=True)
        shutil.copy2(log_file, os.path.join(inlog, os.path.basename(log_file)))
    except Exception:
        logger.exception("Failed to copy log")
    delete_empty_dirs(SRC, logger)
    logger.info("Ingest done")


# === Metadata-only mode ===

def run_metadata_only(exif_args, dry_run):
    logger.info("Running in metadata-only mode")
    if not has_exiftool():
        print('  error: exiftool not available')
        sys.exit(2)

    files = []
    for dirpath, _, filenames in os.walk(SRC):
        if os.path.basename(dirpath).startswith("skipped") or "__log__" in dirpath:
            continue
        files += [os.path.join(dirpath, f) for f in filenames if is_image_file(f)]

    print(f'\nWriting metadata  [{len(files)} file(s)]')
    for i, fullpath in enumerate(files, 1):
        _progress(i, len(files), os.path.basename(fullpath))
        write_metadata_to_file(fullpath, exif_args, dry_run=dry_run, logger=logger)
    print(f'\n\nDone  —  {len(files)} file(s) updated')
    logger.info("metadata-only completed")


# === Main ===

def main():
    parser = argparse.ArgumentParser(description="Ingest pipeline")
    parser.add_argument("author_code", nargs="?", default=None)
    parser.add_argument("--skip-metadata", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    resources_dir = os.path.join(PROJECT_ROOT, "resources")
    exif_args = None

    if args.metadata_only and args.skip_metadata:
        print('  error: --metadata-only and --skip-metadata cannot be used together')
        sys.exit(2)

    if args.author_code and not args.skip_metadata:
        try:
            preset_required = [t for t in required_metadata_tags if t != 'CreateDate']
            exif_args = load_preset_for_code(args.author_code, resources_dir, preset_required)
            logger.info("Loaded preset for %s", args.author_code)
        except MetadataPresetError as e:
            print(f'  error: {e}')
            logger.error("Preset load failed: %s", e)
            sys.exit(2)

    if args.metadata_only:
        if not exif_args:
            print('  error: --metadata-only requires an author code')
            sys.exit(2)
        run_metadata_only(exif_args, dry_run=args.dry_run)
        _finish()
        return

    # === Normal ingest ===
    preset_tag = f'[{args.author_code}]' if args.author_code else '[no preset]'
    dry_tag = '  dry-run' if args.dry_run else ''
    src_name = os.path.basename(SRC.rstrip('/'))

    # --- Scan ---
    print(f'\nScanning {src_name} …')
    skipped_dir = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
    os.makedirs(skipped_dir, exist_ok=True)

    plan, skipped = build_plan(SRC, DST, SUBDIR_MODE, logger)
    logger.info("Plan: %d files, %d skipped", len(plan), len(skipped))

    for path, reason in skipped:
        move_file(path, skipped_dir, reason, dry_run=args.dry_run, logger=logger)

    skip_counts = Counter(r for _, r in skipped)
    skip_detail = '  ·  '.join(f'{n} {r}' for r, n in skip_counts.most_common())
    skip_str = f'  ({skip_detail})' if skipped else ''
    print(f'  {len(plan)} ready  ·  {len(skipped)} skipped{skip_str}')

    if not plan:
        print('\nDone  —  nothing to ingest')
        _finish()
        return

    # --- Process ---
    print(f'\nIngesting  {preset_tag}{dry_tag}')
    total = len(plan)
    ok = 0
    err_list = []

    for i, item in enumerate(plan, 1):
        _progress(i, total, item['fname'])
        _ok = True

        # 1. Pre-validate for --skip-metadata
        if args.skip_metadata:
            try:
                meta = get_metadata_tags(item['src'])
            except Exception as e:
                logger.error("Cannot read metadata for %s: %s", item['fname'], e)
                err_list.append((item['fname'], 'metadata read error'))
                continue
            if not has_required_metadata(meta, item['fname'], required_metadata_tags):
                logger.error("Missing required metadata: %s", item['fname'])
                err_list.append((item['fname'], 'missing required metadata'))
                if not args.dry_run:
                    move_file(item['src'], skipped_dir, 'missing required metadata',
                              dry_run=False, logger=logger)
                continue

        os.makedirs(os.path.dirname(item['dst']), exist_ok=True)
        os.makedirs(item['derivative_dir'], exist_ok=True)

        try:
            # 3. Move
            move_file(item['src'], item['dst'], 'validated move',
                      dry_run=args.dry_run, logger=logger)
            target_path = item['dst']

            # 4. Write metadata
            if exif_args and not args.skip_metadata:
                if has_exiftool():
                    write_metadata_to_file(target_path, exif_args,
                                           dry_run=args.dry_run, logger=logger)
                else:
                    logger.error("exiftool missing — cannot write metadata")

            # 4b. Ensure XMP-xmp:CreateDate
            # In dry-run the file hasn't moved yet, so check the source path
            date_check_path = item['src'] if args.dry_run else target_path
            ensure_xmp_create_date(date_check_path, dry_run=args.dry_run, logger=logger)

            # 5. Post-metadata validation (skip in dry-run — file not actually at destination)
            if not args.skip_metadata and not args.dry_run:
                final_meta = get_metadata_tags(target_path)
                if not has_required_metadata(final_meta, item['fname'], required_metadata_tags):
                    logger.error("Missing required metadata after write: %s", item['fname'])
                    _ok = False
                    err_list.append((item['fname'], 'missing required metadata after write'))
                    if not args.dry_run:
                        move_file(target_path, skipped_dir, 'missing required metadata',
                                  dry_run=False, logger=logger)

            # 6. Derivative
            if _ok and not args.dry_run:
                create_jpg_derivative(target_path, item['derivative_dir'],
                                      item['fname'], logger=logger)

        except Exception as e:
            _ok = False
            err_list.append((item['fname'], str(e)))
            logger.error("Operation failed for %s: %s", item['fname'], e)

        if _ok:
            ok += 1

    print()  # end progress line

    if err_list:
        print()
        for fname, reason in err_list:
            print(f'  ! {fname}  —  {reason[:80]}')

    print(f'\nDone  —  {ok} ingested · {len(err_list)} error(s) · {len(skipped)} skipped')

    # Cleanup empty skipped dir
    if os.path.exists(skipped_dir) and not os.listdir(skipped_dir):
        try:
            os.rmdir(skipped_dir)
        except OSError:
            pass

    _finish()


if __name__ == "__main__":
    main()
