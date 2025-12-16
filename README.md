# Ingest

This Python script moves image data from an input directory to an output directory. Files are validated before movement based on filename, filetype and color profile conformity. Validated files are moved and personal metadata is written to them. The script generates derivative files in `.jpg` format for valid primary images. Invalid files are skipped.

---

## Functionality

- Validates filenames according to _Mediastandard_[^1] conventions.
- Moves valid files into **prefix-named folders**[^2] inside the output directory.
- Writes personal metadata to validated files.
- Generates a `.jpg` derivative for valid primary file.
- Moves invalid or non-conforming files into a `skipped-files` folder inside the input directory.
- Logs all actions into a **log file** in the output and input directory.
- Options via arguments for only writing metadata (`--only-metadata`), only validating and moving files (`--skip-metadata`) or dryrunning (`--dry-run`).

The filecheck is made to check basic conformity of image files with _Mediastandard_ [^1] at [Kunstmuseum Basel](https://medienstandard.kumu.swiss/) and [_Wissenschaftliche Fotografie am Kunstmuseum Basel – Standards_](https://fotografie.kumu.swiss/).

---

## Steps

1. **Check files for validity**
    1. Extension: is supported file type
    2. Filename
        * FIRST: 4 characters, validated against allowed character sets
        * ID (optional): numeric or alphanumeric IDs, possibly hyphen-separated
        * DATE: must be `YYYY-MM-DD`
        * FREETEXT (optional): lowercase alphanumerics and hyphens
        * SUFFIX (optional): must start with `s-` and match allowed suffix tokens
    3. ICC-profile
    4. Required metadata

2. **Move valid files** into prefix-named folders inside the output directory.
3. **Write personal metadata** to validated primary files. 
4. **Create derivative** files from valid primary files.
5. **Move invalid files** into `skipped-files` folder inside input directory.

---

## Usage

1. Define input and output directories inside `variables.py`:

```python
SRC = "path/to/source/directory"  # define source directory
DST = "path/to/destination/directory"  # define destination directory
```

2. Define personal metadata inside `resources/abc-metadata.txt`, where `abc` becomes the argument for this specific personal metadata file.

3. run `python3 "./ingest.py" ABC`

### General dependencies

1. Install Pillow: `pip install pillow`

2. Install exiftool:
    * **macOS**: `brew install exiftool`
    * **Ubuntu/Debian**: `sudo apt install libimage-exiftool-perl`
    * **Windows**:
        1. Download and extract https://exiftool.org/
        2. Add to `PATH` manually

[^1]: KMB-Mediastandard Version 3.0.1, 2025.

[^2]: ID-named option available via `variables.py`.
