import os
import logging

class MetadataPresetError(Exception):
    pass


def parse_preset_file(path):
    """Read a metadata preset file and return a dictionary of friendly-name keys to values."""
    if not os.path.isfile(path):
        raise MetadataPresetError(f"Preset not found: {path}")
    result = {}
    with open(path, 'r', encoding='utf-8') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                logging.warning('Malformed preset line: %s', line)
                continue
            key, rhs = line.split('=', 1)
            key = key.strip()
            rhs = rhs.strip()
            # Remove quotes if present
            if (rhs.startswith('"') and rhs.endswith('"')) or (rhs.startswith("'") and rhs.endswith("'")):
                value = rhs[1:-1]
            else:
                logging.warning('Unquoted preset value; accepting raw: %s', line)
                value = rhs
            result[key] = value
    return result


def validate_required_fields(preset, required_keys):
    """Check that all required friendly-name metadata fields are present and not empty."""
    missing = [k for k in required_keys if not preset.get(k)]
    if missing:
        raise MetadataPresetError(f"Missing required metadata keys: {', '.join(missing)}")


def build_exiftool_args_from_preset(preset):
    """
    Convert friendly-name metadata keys to exiftool arguments.
    Example: Creator -> -XMP-dc:Creator
    """
    args = ['-overwrite_original', '-charset', 'filename=UTF8']

    # Friendly name -> ExifTool tag mapping
    mapping = {
        "Creator": "XMP-dc:Creator",
        "Rights": "XMP-dc:Rights",
        "Relation": "XMP-dc:Relation",
        "Date Created": "XMP-xmp:CreateDate",
        "Authors Position": "XMP-photoshop:AuthorsPosition",
        "Address": "XMP-iptcCore:CreatorAddress",
        "City": "XMP-iptcCore:CreatorCity",
        "Postal Code": "XMP-iptcCore:CreatorPostalCode",
        "Country": "XMP-iptcCore:CreatorCountry",
        "Email Work": "XMP-iptcCore:CreatorWorkEmail",
        "Telephone Work": "XMP-iptcCore:CreatorWorkTelephone",
        "Website": "XMP-iptcCore:CreatorWorkURL",
        "Title": "XMP-dc:Title",
        "Description": "XMP-dc:Description",
        "Instructions": "XMP-photoshop:Instructions"
    }

    for friendly, exiftag in mapping.items():
        if friendly in preset and preset[friendly]:
            args.append(f"-{exiftag}={preset[friendly]}")

    return args


def load_preset_for_code(code, resources_dir, required_keys):
    """
    Load preset for a given author/code from resources, validate required fields,
    and return exiftool argument list.
    """
    if not code:
        return None
    code_lc = code.lower()
    filename = f"{code_lc}-metadata.txt"
    preset_path = os.path.join(resources_dir, filename)
    preset = parse_preset_file(preset_path)
    validate_required_fields(preset, required_keys)
    return build_exiftool_args_from_preset(preset)
