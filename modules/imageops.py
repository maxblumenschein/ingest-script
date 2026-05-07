import os
import io
import logging
from PIL import Image, ImageCms

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SRGB_ICC = os.path.join(BASE_DIR, 'resources', 'sRGB_IEC61966-2-1.icc')
GRAY_ICC = os.path.join(BASE_DIR, 'resources', 'Gray-Gamma-2-2.icc')


def convert_to_target_profile(img, file_name):
    icc = img.info.get('icc_profile')
    mode = img.mode
    try:
        if mode == 'L':
            target = ImageCms.ImageCmsProfile(GRAY_ICC)
        else:
            target = ImageCms.ImageCmsProfile(SRGB_ICC)
        target_bytes = target.tobytes()
        if icc:
            input_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            converted = ImageCms.profileToProfile(img, input_profile, target, outputMode=mode, renderingIntent=0)
            converted.info['icc_profile'] = target_bytes
        else:
            img.info['icc_profile'] = target_bytes
            converted = img
        return converted
    except Exception as e:
        logging.error('%s: ICC conversion failed: %s', file_name, e)
        raise


def _is_grayscale(mode):
    return mode.split(';')[0] in ('L', 'LA', 'I', 'F')


def _to_8bit(img):
    """Convert any image to 8-bit mode (L for grayscale, RGB for colour).
    For high-bit-depth grayscale (I;16, I, F) scales values to 0-255 rather than clipping."""
    icc = img.info.get('icc_profile')
    if _is_grayscale(img.mode):
        base = img.mode.split(';')[0]
        if base == 'I':
            # 16-bit unsigned (0-65535) → scale to 8-bit; point() uses linear transform
            out = img.point(lambda x: x / 256, 'L').convert('L')
        elif base == 'F':
            # Float (0.0-1.0) → scale to 8-bit
            out = img.point(lambda x: x * 255, 'L').convert('L')
        else:
            out = img.convert('L')
    else:
        out = img.convert('RGB')
    if icc and not out.info.get('icc_profile'):
        out.info['icc_profile'] = icc
    return out


def create_jpg_derivative(src_image_path, dst_directory, file_name, logger=None):
    if logger is None:
        logger = logging.getLogger('ingest')
    try:
        original = Image.open(src_image_path)
        original = _to_8bit(original)
        converted = convert_to_target_profile(original.copy(), file_name)
        os.makedirs(dst_directory, exist_ok=True)
        dst_jpg = os.path.join(dst_directory, os.path.splitext(file_name)[0] + '.jpg')
        converted.save(dst_jpg, 'JPEG', quality=100, icc_profile=converted.info.get('icc_profile', b''))
        logger.info('Saved derivative: %s', dst_jpg)
        # copy metadata from primary to derivative
        from modules.fileops import copy_metadata_with_exiftool
        copy_metadata_with_exiftool(src_image_path, dst_jpg, logger=logger)
    except Exception as e:
        logger.error('Failed to create derivative for %s: %s', file_name, e)


def can_create_jpg_derivative(src_image_path, file_name):
    try:
        original = Image.open(src_image_path)
        original = _to_8bit(original)
        _ = convert_to_target_profile(original.copy(), file_name)
        return True
    except Exception:
        return False