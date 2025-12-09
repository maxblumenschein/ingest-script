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


def create_jpg_derivative(src_image_path, dst_directory, file_name, logger=None):
    if logger is None:
        logger = logging.getLogger('ingest')
    try:
        original = Image.open(src_image_path)
        original = original.convert('RGB' if original.mode != 'L' else 'L')
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
        original = original.convert('RGB' if original.mode != 'L' else 'L')
        _ = convert_to_target_profile(original.copy(), file_name)
        return True
    except Exception:
        return False