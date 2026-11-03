# Process

*Loupe*

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
3. Create `config.json` with the source and destination paths (once per installation, shared by all users)
4. Create your personal metadata preset `presets/<code>-metadata.txt`

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
./PROCESS          # macOS / Linux
./PROCESS.ps1      # Windows (PowerShell)
```

At start the launcher shows the last user — press **Enter** to continue, or type another author code to switch:

```
  User: blm  (Max Blumenschein)
  Enter = continue  ·  switch: type abc
  >
```

Paths come from `config.json`; the user's metadata from `presets/<code>-metadata.txt`. An old `user_config.py` still works as a fallback.

### Color accuracy check (test phase)

```
./PROCESS_colorcheck_only         # macOS / Linux
./PROCESS_colorcheck_only.ps1     # Windows (PowerShell)
```

This only reads the images in the source folder; nothing is moved, renamed, or written into the files. The only output is a log in `SRC/__log__/colorcheck_<timestamp>.log` (patch table, ΔE2000, white balance, exposure). It only checks the `wNa` view (e.g. `gw1a`).

Reference file, first match wins: `--colorcheck-reference PATH` → `COLORCHECK_REFERENCE` in `config.json` → the newest `_internal/resources/ccmi_*.txt`.

A normal `./PROCESS` run does **not** run the color check while `COLORCHECK_IN_PIPELINE = False` (in `_internal/variables.py`).

### Options

Pass flags after the launcher:

| Flag | Effect |
|------|--------|
| `--dry-run` | Preview all actions without modifying any files |
| `--skip-metadata` | Validate and move files only; skip metadata writing |
| `--metadata-only` | Write metadata to already-processed files (requires author code) |
| `--colorcheck-only` | Check color accuracy against the calibration target only; no move, metadata write, or derivative |
| `--colorcheck-reference PATH` | Reference file for `--colorcheck-only` |
| `--user CODE` | Run as this user without asking |
| `-y`, `--yes` | Continue with the last user without asking |

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

Run `python3 onboard.py` and follow the prompts. Two kinds of file, for two questions:

| File | Answers | Contents | How many |
|---|---|---|---|
| `config.json` | *Where* does the script read and write? | SRC, DST, staging, colorcheck reference | one per installation, shared |
| `presets/abc-metadata.txt` | *Who* photographed this? | Creator, Rights, Relation, contact details — written into every image | one per user; the file name is the author code |

If `config.json` already exists, onboarding keeps it and only asks for the new user's metadata. An old `user_config.py` can be converted into `config.json` during onboarding.

To edit your metadata later, open `presets/abc-metadata.txt` directly; to change paths, edit `config.json`.

Neither is **tracked by git** — they stay on each machine. The repo only holds templates: `config.example.json` and `presets/example-metadata.txt` (never offered as a user).

---

## Staging

For faster processing when the destination is a slow external drive, set a staging directory in `config.json`:

```json
"STAGING_DIR": "/path/to/fast/local/drive"
```

All processing happens on the fast drive first; files are bulk-copied to the destination at the end.

---

[^1]: KMB-Mediastandard Version 3.0.1, 2025. [medienstandard.kumu.swiss](https://medienstandard.kumu.swiss/) · [fotografie.kumu.swiss](https://fotografie.kumu.swiss/)
