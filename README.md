# Ingest

This Python Script moves data from an input directoy to an output directory based on filename and filetype.

## Steps

1. Check filenames for valid
  1. extensions
  2. segment lengths between delimeters
  3. prefix

2. Move valid files into prefix-named folders in output directory

3. Move invalid files into skipped-files folder
