import sys
import os
import shutil
import re
from datetime import datetime, timezone
from PIL import Image, ImageCms
import io
import logging
import subprocess
import json

from variables import SRC, DST, SKIPPED, valid_id_initial_chars, valid_suffixes, valid_first_segment_first_char, valid_first_segment_other_chars, required_metadata_tags

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tif', '.tiff')

now = datetime.now(timezone.utc).astimezone()
date_suffix = now.strftime("%Y-%m-%dT%H%M%S")
date_isoformat = now.replace(microsecond=0).isoformat()

log_directory = os.path.join(DST, "__log__")
os.makedirs(log_directory, exist_ok=True)
log_file_name = f"script_{date_suffix}.log"
log_path = os.path.join(log_directory, log_file_name)
logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

logging.info("Start ingest process")
logging.info(f"Source directory = {SRC}")
logging.info(f"Destination directory = {DST}")

def move_file(src, dst, reason):
    try:
        shutil.move(src, dst)
        logging.info(f"Moved: {src} -> {dst} ({reason})")
    except shutil.Error as e:
        logging.error(f"Error moving {src} to {dst}: {e}")
        raise  # re-raise to let the caller handle it

def is_image_file(file_name):
    """
    Is valid image file name

    >>> is_image_file("a.jpg")
    True
    >>> is_image_file("a.txt")
    False
    """
    return file_name.lower().endswith(IMAGE_EXTENSIONS)

def is_valid_first_segment(first_segment):
    """
    Validate the first segment of the filename.

    A valid first segment:
    - Is exactly 4 characters long
    - Starts with a character from `valid_first_segment_first_char`
    - Followed by 3 characters from `valid_first_segment_other_chars`

    Parameters:
        first_segment (str): The first segment of the filename.

    Returns:
        bool: True if the segment is valid, False otherwise.

    Example:
    >>> valid_first_segment_first_char = {'g'}
    >>> valid_first_segment_other_chars = {'w1r'}
    >>> is_valid_first_segment("gw1r")
    True
    >>> is_valid_first_segment("xx12")
    False
    """
    return len(first_segment) == 4 and first_segment[0] in valid_first_segment_first_char and first_segment[1:] in valid_first_segment_other_chars

def is_valid_date_segment(date_segment):
    """
    Validate a date segment in the format YYYY-MM-DD.

    Parameters:
        date_segment (str): The date string to validate.

    Returns:
        bool: True if the date is valid and correctly formatted, False otherwise.

    Example:
    >>> is_valid_date_segment("2024-12-31")
    True
    >>> is_valid_date_segment("2024-13-01")
    False
    >>> is_valid_date_segment("2024-02-30")
    False
    """
    try:
        datetime.strptime(date_segment, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_id_segment(id_segment):
    """
    Validate the ID segment of the filename.

    A valid ID segment:
    - May consist of one or more parts separated by dashes
    - Each part must be either:
        - 7 digits (e.g., '0098163')
        - 1 character from `valid_id_initial_chars` followed by 6 digits (e.g., 'a001285')

    Parameters:
        id_segment (str): The ID string to validate.

    Returns:
        bool: True if the ID segment is valid, False otherwise.

    Example:
    >>> valid_id_initial_chars = {'a', 'b'}
    >>> is_valid_id_segment("0098163")
    True
    >>> is_valid_id_segment("a001285")
    True
    >>> is_valid_id_segment("x001285")
    False
    >>> is_valid_id_segment("a001285-0098163")
    True
    """
    valid_initials = ''.join(valid_id_initial_chars)
    id_pattern = rf"^\d{{7}}$|^[{valid_initials}]\d{{6}}$"
    parts = id_segment.split('-')
    return all(re.fullmatch(id_pattern, part) for part in parts)

def is_valid_freetext_segment(freetext_segment):
    """
    Validate a freetext segment of the filename.

    A valid freetext segment:
    - Must not start with 's-'
    - Must consist of lowercase letters, digits, and dashes
    - Must start with a letter or digit

    Parameters:
        freetext_segment (str): The freetext segment to validate.

    Returns:
        bool: True if the freetext segment is valid, False otherwise.

    Example:
    >>> is_valid_freetext_segment("freetext")
    True
    >>> is_valid_freetext_segment("text-123")
    True
    >>> is_valid_freetext_segment("s-dt")
    False
    >>> is_valid_freetext_segment("-bad")
    False
    """
    if freetext_segment.startswith("s-"):
        return False
    return re.fullmatch(r"^[a-z0-9][a-z0-9-]*$", freetext_segment) is not None

def is_valid_suffix_segment(suffix_segment):
    """
    Validate whether a suffix segment is correctly formatted.

    A valid suffix segment:
    - Starts with 's-'
    - Is followed by one or more parts separated by dashes
    - Each part must be either:
        - A known valid suffix (from `valid_suffixes`)
        - A 3-digit number (e.g., '001')

    Parameters:
        suffix_segment (str): The suffix segment string to validate.

    Returns:
        bool: True if the suffix segment is valid, False otherwise.

    Example:
    >>> valid_suffixes = {'dt', 'note'}
    >>> is_valid_suffix_segment('s-dt')
    True
    >>> is_valid_suffix_segment('s-123-note')
    True
    >>> is_valid_suffix_segment('s-xyz')
    False
    >>> is_valid_suffix_segment('dt')
    False
    """
    if not suffix_segment.startswith("s-"):
        return False
    parts = suffix_segment[2:].split("-")
    for sub in parts:
        if sub in valid_suffixes:
            continue
        elif re.fullmatch(r"\d{3}", sub):
            continue
        else:
            return False
    return True

def pad_array(arr, size, fill=None):
    """Pads arr to at least `size` elements and keeps the rest in tail."""
    padded = arr[:size] + [fill] * (size - len(arr))
    return padded + arr[size:]

def is_valid_filename(file_name):
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')

    if len(segments) < 2:
        logging.warning(f"{file_name}: Too few segments")
        return False, True

    first_segment = segments[0]
    if not is_valid_first_segment(first_segment):
        logging.warning(f"{file_name}: Invalid first segment")
        return False, True

    remaining_segments = segments[1:]

    if not remaining_segments:
        logging.warning(f"{file_name}: Missing segments after first")
        return False, True

    if is_valid_id_segment(remaining_segments[0]):
        if len(remaining_segments) < 2:
            logging.warning(f"{file_name}: Missing date after ID segment")
            return False, True
        id_segment, date_segment, *optional_segments = remaining_segments
    else:
        date_segment, *optional_segments = remaining_segments

    if not is_valid_date_segment(date_segment):
        logging.warning(f"{file_name}: Missing or invalid date segment")
        return False, True

    if optional_segments:
        if is_valid_suffix_segment(optional_segments[0]):
            if len(optional_segments) != 1:
                logging.warning(f"{file_name}: No segment allowed after suffix segment.")
                return False, True
            if not is_valid_suffix_segment(optional_segments[0]):
                logging.warning(f"{file_name}: Invalid suffix segment")
                return False, True
            return True, False

    freetext_segment, suffix_segment, *tail = pad_array(optional_segments, 2, None)

    if freetext_segment and not is_valid_freetext_segment(freetext_segment):
        logging.warning(f"{file_name}: Invalid freetext segment")
        return False, True

    if suffix_segment and not is_valid_suffix_segment(suffix_segment):
        logging.warning(f"{file_name}: Invalid suffix segment")
        return False, True

    if tail:
        logging.warning(f"{file_name}: Too many segments")
        return False, True

    return True, False

def get_metadata_tags(file_path):
    try:
        # Run exiftool to get JSON output
        result = subprocess.run(
            ['exiftool', '-j', file_path],
            capture_output=True,
            text=True,
            check=True
        )
        metadata_list = json.loads(result.stdout)
        if metadata_list:
            return metadata_list[0]  # first dict in list contains metadata
        return {}
    except Exception as e:
        logging.error(f"Failed to get metadata for {file_path}: {e}")
        raise MetadataReadError(f"Could not read metadata from {file_path}") from e

def missing_required_metadata(metadata):
    """
    Check which required metadata tags are missing or empty.

    This function compares the input metadata dictionary against the
    globally defined `required_metadata_tags` list. It returns a list
    of tags that are either missing or have empty values (e.g., None, '', etc.).

    Parameters:
        metadata (dict): Dictionary of metadata key-value pairs.

    Returns:
        list[str]: List of missing or empty required metadata tags.

    Example:
    >>> required_metadata_tags = ['DateTimeOriginal', 'CameraModel', 'Artist']
    >>> metadata = {
    ...     'DateTimeOriginal': '2023:05:01 12:00:00',
    ...     'CameraModel': '',
    ...     'SomeOtherTag': 'Value'
    ... }
    >>> missing_required_metadata(metadata)
    ['CameraModel', 'Artist']
    """
    missing = []
    for tag in required_metadata_tags:
        if tag not in metadata or not metadata[tag]:
            missing.append(tag)
    return missing

def has_required_metadata(metadata):
    missing = missing_required_metadata(metadata)
    if missing:
        logging.warning(f"Missing required metadata tags: {', '.join(missing)}")
        return False
    return True

def file_check(file_name):
    if not is_image_file(file_name):
        logging.warning(f"{file_name}: Invalid file type")
        return False
    valid, already_logged = is_valid_filename(file_name)
    if not valid and not already_logged:
        logging.warning(f"{file_name}: Invalid filename")
    return valid

def delete_empty_dirs(root_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        if not dirnames and not filenames:
            dir_name = os.path.basename(dirpath)
            if not dir_name.startswith(("skipped", "log")):
                try:
                    os.rmdir(dirpath)
                    logging.info(f"Deleted empty directory: {dirpath}")
                except OSError as e:
                    logging.error(f"Failed to delete {dirpath}: {e}")

def copy_metadata_with_exiftool(src_path, dst_path):
    try:
        subprocess.run([
            "exiftool",
            "-overwrite_original",
            "-TagsFromFile", src_path,
            "-All:All",
            dst_path
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"Copied metadata from {src_path} to {dst_path} using exiftool.")
    except subprocess.CalledProcessError as e:
        logging.error(f"ExifTool failed for {src_path}: {e.stderr.decode().strip()}")
    except FileNotFoundError:
        logging.error("ExifTool not found. Please install it and ensure it's in the system PATH.")

def convert_to_srgb(img):
    icc_bytes = img.info.get('icc_profile')
    srgb_icc_path = os.path.join(os.path.dirname(__file__), 'resources', 'sRGB_IEC61966-2-1.icc')

    try:
        srgb_profile = ImageCms.ImageCmsProfile(srgb_icc_path)
        srgb_icc_bytes = srgb_profile.tobytes()

        if icc_bytes:
            input_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
            profile_name = ImageCms.getProfileName(input_profile)
            logging.info(f"Source ICC profile: {profile_name}")

            img = ImageCms.profileToProfile(img, input_profile, srgb_profile, outputMode='RGB')
            img.info['icc_profile'] = srgb_icc_bytes
        else:
            logging.info("No ICC profile embedded; assuming source is sRGB and embedding sRGB profile.")
            img.info['icc_profile'] = srgb_icc_bytes

    except Exception as e:
        logging.error(f"ICC conversion failed: {e}")
        raise

    return img

def create_jpg_derivative(src_image_path, dst_directory, file_name):
    try:
        original = Image.open(src_image_path)
        original = original.convert("RGB")

        original_icc = original.info.get('icc_profile', b'')

        try:
            converted = convert_to_srgb(original.copy())
            converted_icc = converted.info.get('icc_profile', b'')

            if original_icc != converted_icc:
                logging.info(f"{file_name}: ICC profile was converted to sRGB.")
            else:
                logging.info(f"{file_name}: ICC profile unchanged; already sRGB or assumed sRGB.")
        except Exception as e:
            logging.error(f"{file_name}: Failed to convert ICC profile to sRGB: {e}")
            return  # Skip saving if conversion fails

        os.makedirs(dst_directory, exist_ok=True)
        dst_jpg_path = os.path.join(dst_directory, os.path.splitext(file_name)[0] + ".jpg")

        converted.save(dst_jpg_path, "JPEG", quality=98,
                       icc_profile=converted.info.get('icc_profile', b''))
        logging.info(f"{file_name}: Saved JPG derivative with embedded sRGB: {dst_jpg_path}")

        copy_metadata_with_exiftool(src_image_path, dst_jpg_path)

    except Exception as e:
        logging.error(f"{file_name}: Failed to create JPG derivative: {e}")

def get_destination_subdir(file_name):
    base_file_name, _ = os.path.splitext(file_name)
    segments = base_file_name.split('_')

    # Default category and subdir
    category_dir = "noIDs"
    subdir_name = segments[0][1:4] if len(segments[0]) >= 4 else segments[0][1:]

    if len(segments) > 1 and is_valid_id_segment(segments[1]):
        category_dir = "IDs"
        first_id = segments[1].split('-')[0]  # Use only the first ID
        subdir_name = first_id

    return category_dir, subdir_name

def process_files():
    skipped_directory = os.path.join(SRC, f"{SKIPPED}_{date_suffix}")
    os.makedirs(skipped_directory, exist_ok=True)  # Create skipped directory once here
    skipped_files = []
    valid_files = []

    for dirpath, _, filenames in os.walk(SRC):
        if dirpath.startswith(os.path.join(SRC, SKIPPED)):
            continue
        for file_name in filenames:
            if file_name == ".DS_Store":
                continue
            file_path = os.path.join(dirpath, file_name)

            if file_check(file_name):
                valid_files.append((file_name, file_path))
            else:
                skipped_files.append(file_path)

    if skipped_files:
        for file_path in skipped_files:
            move_file(file_path, skipped_directory, "Moved to skipped")

    for file_name, file_path in valid_files:
        # Check for required metadata before proceeding
        metadata = get_metadata_tags(file_path)
        if not has_required_metadata(metadata):
            if not os.path.exists(skipped_directory):
                os.makedirs(skipped_directory, exist_ok=True)
            move_file(file_path, skipped_directory, "Missing required metadata")
            continue

        category_dir, subdir_name = get_destination_subdir(file_name)

        primary_directory = os.path.join(DST, "primary", category_dir, subdir_name)
        derivative_directory = os.path.join(DST, "derivative", category_dir, subdir_name)

        dst_file_path = os.path.join(primary_directory, file_name)
        os.makedirs(primary_directory, exist_ok=True)
        os.makedirs(derivative_directory, exist_ok=True)

        if os.path.exists(dst_file_path):
            logging.warning(f"{file_name} already exists at destination, moving to skipped folder.")
            if not skipped_files:
                os.makedirs(skipped_directory, exist_ok=True)
            move_file(file_path, skipped_directory, "Moved to skipped (file already exists at destination)")
        else:
            move_file(file_path, primary_directory, "Moved to primary destination")
            full_dst_path = os.path.join(primary_directory, file_name)
            create_jpg_derivative(full_dst_path, derivative_directory, file_name)

    if os.path.exists(skipped_directory) and not os.listdir(skipped_directory):
        os.rmdir(skipped_directory)

    delete_empty_dirs(SRC)

def main():
    process_files()
    logging.info("Done")

if __name__ == "__main__":
    main()
