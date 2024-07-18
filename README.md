# Ingest

This Python script moves data from an input directoy to an output directory based on filename and filetype.

## Steps

1. Check filenames for valid
    1. extension
    2. segment length between delimeters
    3. prefix
2. Move valid files into prefix-named folders in output directory
3. Move invalid files into skipped-files folder

## Logging

Actions are recorded in a log-file inside the output directory

## Use

Define input and output directory inside `ìngest.py`:

```python
SRC = "path/to/source/directory" # define SRC directory
DST = "path/to/destination/directory" # define SRC directory
```

The filecheck is made to check basic conformity with Mediastandard [^1] at [Kunstmuseum Basel](https://kunstmuseumbasel.ch/). To adapt the filecheck configure `python file_check(file_name)` accordingly.

[^1]: KMB-Mediastandard 2017 – Version 2.0; extended with a few additional prefixes
