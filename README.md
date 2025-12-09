# Ingest

This Python script moves image data from an input directory to an output directory based on filename, filetype, and metadata conformity. It also generates derivative files in `.jpg` formatfor valid primary images.

---

## Functionality

- Validates filenames according to _Mediastandard_ conventions.
- Moves valid files into **ID-named folders** inside the output directory.
- Generates a `.jpg` derivative for each valid primary file.
- Moves invalid or non-conforming files into a `skipped-files` folder inside the input directory.
- Logs all actions and decisions into a **log file** in the output and input directory.

---

## Steps

1. **Check files for validity**
    1. Prefix
    2. Segment length and syntax between delimiters
    3. ID
    4. Date
    5. Free-text
    6. Suffix
    7. Extension
    8. Required metadata
    9. ICC-profile

2. **Move valid files** into ID-named folders inside the output directory.
3. **Create derivative** files from valid primary images.
4. **Move invalid files** into `skipped-files` folder inside input directory.

---

## Logging

- All actions, including file validation results and derivative creation, are recorded in a **log file** inside the output directory.

---

## Usage

Define input and output directories inside `variables.py`:

```python
SRC = "path/to/source/directory"  # define source directory
DST = "path/to/destination/directory"  # define destination directory
```

The filecheck is made to check basic conformity of image files with _Mediastandard_ [^1] at [Kunstmuseum Basel](https://medienstandard.kumu.swiss/) and [_Wissenschaftliche Fotografie am Kunstmuseum Basel – Standards_](https://fotografie.kumu.swiss/).

### General dependencies

1. Install Pillow: `pip install pillow`

2. Install exiftool:
    * **macOS**: `brew install exiftool`
    * **Ubuntu/Debian**: `sudo apt install libimage-exiftool-perl`
    * **Windows**:
        1. Download and extract https://exiftool.org/
        2. Add to `PATH` manually

[^1]: KMB-Mediastandard Version 3.0.1, 2025.
