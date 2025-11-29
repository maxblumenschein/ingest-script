# Ingest

This Python script moves data from an input directoy to an output directory based on filename and filetype.

## Steps

1. Check filenames for validity
    1. prefix
    2. segment length and syntax between delimeters
    3. id
    4. date
    5. free-text
    6. suffix
    7. extension
    8. required Metadata
2. Move valid files into id-named folders inside output directory
3. Create specified derivative (`.jpg`, `sRGB`) from valid primary files
3. Move invalid files into skipped-files folder inside input directory

## Logging

Actions are recorded in a log-file inside the output directory

## Use

Define input and output directory inside `variables.py`:

```python
SRC = "path/to/source/directory" # define source directory
DST = "path/to/destination/directory" # define destination directory
```

The filecheck is made to check basic conformity of image files with _Mediastandard_ [^1] at [Kunstmuseum Basel](https://medienstandard.kumu.swiss/) and [_Wissenschaftliche Fotografie am Kunstmuseum Basel – Standards_](https://fotografie.kumu.swiss/). To adapt the filecheck configure the function `is_valid_filename(file_name)` inside `ìngest.py` accordingly.

### General dependencies

1. Install Pillow: `pip install pillow`

2. Install exiftool:
    * **macOS**: `brew install exiftool`
    * **Ubuntu/Debian**: `sudo apt install libimage-exiftool-perl`
    * **Windows**:
        1. Download and extract https://exiftool.org/
        2. Add to `PATH` manually

[^1]: KMB-Mediastandard Version 3.0, 2024.
