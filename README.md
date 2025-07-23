# Ingest

This Python script moves data from an input directoy to an output directory based on filename and filetype.

## Steps

1. Check filenames for valid
    1. prefix
    2. segment length and syntax between delimeters
    3. id
    4. date
    5. extension
2. Move valid files into prefix-named folders inside output directory
3. Move invalid files into skipped-files folder inside input directory

## Logging

Actions are recorded in a log-file inside the output directory

## Use

Define input and output directory inside `variables.py`:

```python
SRC = "path/to/source/directory" # define source directory
DST = "path/to/destination/directory" # define destination directory
```

The filecheck is made to check basic conformity with _Mediastandard_ [^1] at [Kunstmuseum Basel](https://medienstandard.kumu.swiss/). To adapt the filecheck configure the function `python is_valid_filename(file_name)` inside `ìngest.py` accordingly.

[^1]: KMB-Mediastandard Version 3.0, 2024.
