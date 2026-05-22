# Ingest

Moves image files from a source directory to a destination directory. Files are validated against _Mediastandard_[^1] conventions before processing. Valid files are moved, tagged with personal metadata, and a `.jpg` derivative is generated. Invalid files are collected in a `skipped_files` folder.

---

## First-time setup

Run once on a new machine:

```
python3 onboard.py        # macOS / Linux
python  onboard.py        # Windows
```

The wizard will:

1. Create a virtual environment and install Python dependencies
2. Check for ExifTool and provide install instructions if missing
3. Create your personal metadata preset in `presets/`
4. Create `user_config.py` with your source and destination paths

After setup, everything is ready to use via the launcher scripts.

### ExifTool

ExifTool is required and must be installed separately.

- **macOS**: `brew install exiftool`
- **Ubuntu / Debian**: `sudo apt install libimage-exiftool-perl`
- **Windows (no admin)**: download the standalone `exiftool.exe` from [exiftool.org](https://exiftool.org), rename it to `exiftool.exe`, and place it in a `bin/` folder inside this project. The script will find it automatically.

### Python

Python 3.9 or newer is required.

- **macOS**: pre-installed, or via [Homebrew](https://brew.sh)
- **Windows**: available from the Microsoft Store (no admin rights needed)

---

## Daily use

```
./INGEST          # macOS / Linux
./INGEST.ps1      # Windows (PowerShell)
```

The launcher reads your author code and paths from `user_config.py` and starts the pipeline.

### Options

Pass flags after the launcher:

| Flag | Effect |
|------|--------|
| `--dry-run` | Preview all actions without modifying any files |
| `--skip-metadata` | Validate and move files only; skip metadata writing |
| `--metadata-only` | Write metadata to already-ingested files (requires author code) |

---

## What the pipeline does

1. **Validate** each file in the source directory
    - File type: must be a supported image format
    - Filename structure: `FIRST_[ID_]DATE[_FREETEXT][_SUFFIX]`
        - `FIRST` — 4 characters validated against _Mediastandard_ character sets
        - `ID` — optional; numeric or alphanumeric, hyphen-separated
        - `DATE` — `YYYY-MM-DD`
        - `FREETEXT` — optional; lowercase alphanumerics and hyphens
        - `SUFFIX` — optional; `s-` prefix followed by allowed tokens
    - ICC profile: must be eciRGB v2 or Gray Gamma 2.2
    - Required metadata tags must be present (or will be written)

2. **Move** valid files into the destination, organised into subdirectories by category prefix

3. **Write metadata** from your personal preset (`presets/abc-metadata.txt`)

4. **Create a `.jpg` derivative** for each valid primary file

5. **Move invalid files** into a timestamped `skipped_files` folder in the source directory

6. **Log** all actions to `__log__/` in both source and destination

---

## Adding a new user

Run `python3 onboard.py` and follow the prompts. This creates:

- `presets/abc-metadata.txt` — personal metadata (Creator, Rights, Relation, contact details)
- `user_config.py` — local paths and author code (not committed to git)

To edit your metadata after setup, open `presets/abc-metadata.txt` directly.

---

## Staging

For faster processing when the destination is a slow external drive, set a staging directory in `user_config.py`:

```python
STAGING_DIR = "/path/to/fast/local/drive"
```

All processing happens on the fast drive first; files are bulk-copied to the destination at the end.

---

[^1]: KMB-Mediastandard Version 3.0.1, 2025. [medienstandard.kumu.swiss](https://medienstandard.kumu.swiss/) · [fotografie.kumu.swiss](https://fotografie.kumu.swiss/)
