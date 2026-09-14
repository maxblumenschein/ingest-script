#!/usr/bin/env python3
"""
First-time setup for the ingest pipeline.

Run once before using INGEST / INGEST.ps1:
    python3 onboard.py        (macOS / Linux)
    python  onboard.py        (Windows)

No third-party packages required — uses Python stdlib only.
"""

import os
import platform
import shutil
import subprocess
import sys
import textwrap

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PRESETS_DIR  = os.path.join(SCRIPT_DIR, "presets")
VENV_DIR     = os.path.join(SCRIPT_DIR, "venv")
BIN_DIR      = os.path.join(SCRIPT_DIR, "bin")
REQUIREMENTS = os.path.join(SCRIPT_DIR, "_internal", "requirements.txt")
USER_CONFIG  = os.path.join(SCRIPT_DIR, "user_config.py")

IS_WINDOWS = platform.system() == "Windows"


# ── display helpers ──────────────────────────────────────────────────────────

def _hr(char="─", width=58):
    print(char * width)

def _ok(msg):   print(f"  ✓  {msg}")
def _warn(msg): print(f"  !  {msg}")
def _err(msg):  print(f"  ✗  {msg}")


def _ask(prompt, default=None, required=False):
    """Prompt for text input. Returns stripped value or default."""
    hint = f"  (default: {default})" if default else ""
    while True:
        try:
            val = input(f"\n  {prompt}{hint}\n  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nAborted.")
            sys.exit(0)
        if val:
            return val
        if default is not None:
            return default
        if not required:
            return ""
        _warn("This field is required — please enter a value.")


def _ask_path(prompt, required=False):
    """Prompt for a filesystem path, expanding ~ and env vars."""
    raw = _ask(prompt, required=required)
    return os.path.normpath(os.path.expandvars(os.path.expanduser(raw))) if raw else ""


def _confirm(prompt, default="N"):
    val = _ask(f"{prompt} [y/N]", default=default)
    return val.lower() in ("y", "yes")


# ── step 1: python version ───────────────────────────────────────────────────

def _check_python():
    v = sys.version_info
    if v < (3, 9):
        _err(f"Python 3.9 or newer is required (you have {v.major}.{v.minor})")
        sys.exit(1)
    _ok(f"Python {v.major}.{v.minor}.{v.micro}")


# ── step 2: virtual environment + pip packages ───────────────────────────────

def _venv_python():
    if IS_WINDOWS:
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def _setup_venv():
    if not os.path.isdir(VENV_DIR):
        print("  Creating virtual environment…")
        import venv as _venv
        _venv.create(VENV_DIR, with_pip=True)
    else:
        _ok("Virtual environment exists")

    py = _venv_python()
    if not os.path.isfile(py):
        _err(f"Virtual environment Python not found: {py}")
        sys.exit(1)

    print("  Installing Python packages…")
    r = subprocess.run(
        [py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        capture_output=True, text=True,
    )
    r = subprocess.run(
        [py, "-m", "pip", "install", "--quiet", "-r", REQUIREMENTS],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _err("pip install failed:")
        print(r.stderr)
        sys.exit(1)
    _ok("Python packages installed")


# ── step 3: exiftool ─────────────────────────────────────────────────────────

def _check_exiftool():
    if shutil.which("exiftool"):
        _ok("ExifTool found in PATH")
        return

    local_name = "exiftool.exe" if IS_WINDOWS else "exiftool"
    if os.path.isfile(os.path.join(BIN_DIR, local_name)):
        _ok(f"ExifTool found in bin/  (used automatically by ingest.py)")
        return

    _err("ExifTool not found")
    print()
    if IS_WINDOWS:
        print(textwrap.indent(textwrap.dedent("""\
            To install ExifTool without admin rights on Windows:
              1. Download the "Windows Executable" (.zip) from:
                     https://exiftool.org
              2. Unzip it and rename the .exe to  exiftool.exe
              3. Create a  bin\\  folder inside this project and put
                 exiftool.exe there:
                     bin\\exiftool.exe
              ingest.py will find it automatically.
        """), "  "))
    elif shutil.which("brew"):
        print("  Install with:  brew install exiftool")
    else:
        print(textwrap.indent(textwrap.dedent("""\
            Install ExifTool:
              macOS (Homebrew):  brew install exiftool
                 → Install Homebrew first (no admin on Apple Silicon):
                   https://brew.sh
              Linux:             sudo apt install libimage-exiftool-perl
        """), "  "))
    print()
    print("  Re-run  python3 onboard.py  after installing to verify.")
    print()


# ── step 4: metadata preset ───────────────────────────────────────────────────

_REQUIRED_FIELDS = [
    ("Creator",  "Your full name as it should appear in image metadata"),
    ("Rights",   "Institution or copyright holder"),
    ("Relation", "Standards reference, e.g. 'Project Standards v1.1.0'"),
]

_RECOMMENDED_FIELDS = [
    ("Authors Position", "Job title"),
    ("Address",          "Street address"),
    ("City",             "City"),
    ("Postal Code",      "Postal / ZIP code"),
    ("Country",          "Country"),
    ("Email Work",       "Work email address"),
    ("Telephone Work",   "Work phone number"),
    ("Website",          "Website URL"),
]


def _ask_code():
    while True:
        code = _ask("Author code  (2–4 lowercase letters, e.g. 'blm')", required=True)
        code = code.lower()
        if code.isalpha() and 2 <= len(code) <= 4:
            return code
        _warn("Code must be 2–4 letters (a–z only). Try again.")


def _build_preset_content(values):
    def q(key):
        return f'"{values.get(key, "")}"'

    lines = ["# ===== REQUIRED ====="]
    for key, _ in _REQUIRED_FIELDS:
        lines.append(f'{key}={q(key)}')
    lines.append("")
    lines.append("# ===== RECOMMENDED =====")
    for key, _ in _RECOMMENDED_FIELDS:
        lines.append(f'{key}={q(key)}')
    lines.append("")
    lines.append("# ===== OPTIONAL =====")
    lines.append('Title=""')
    lines.append('Description=""')
    lines.append('Instructions=""')
    lines.append("")
    return "\n".join(lines)


def _create_user_preset():
    print()
    _hr()
    print("  Step 2 — Metadata preset")
    _hr()
    print(textwrap.dedent("""\

      Each user needs a personal preset file so that your name, institution,
      and contact details are written into every image you ingest.

      The author code becomes your CLI identifier, e.g.  ./INGEST blm
    """))

    code = _ask_code()
    preset_path = os.path.join(PRESETS_DIR, f"{code}-metadata.txt")

    if os.path.isfile(preset_path):
        print(f"\n  Found existing preset:  presets/{code}-metadata.txt")
        if not _confirm("Overwrite it with new values?"):
            _ok(f"Keeping existing preset — code: {code}")
            return code

    print(textwrap.dedent("""\

      Fill in each field. Required fields cannot be blank.
      Press Enter to leave recommended fields blank for now
      (you can edit presets/{code}-metadata.txt later).
    """).format(code=code))

    values = {}

    print("  ── REQUIRED ──────────────────────────────────")
    for key, hint in _REQUIRED_FIELDS:
        values[key] = _ask(f"{key}  ({hint})", required=True)

    print("\n  ── RECOMMENDED  (Enter to skip) ──────────────")
    for key, hint in _RECOMMENDED_FIELDS:
        values[key] = _ask(f"{key}  ({hint})")

    os.makedirs(PRESETS_DIR, exist_ok=True)
    with open(preset_path, "w", encoding="utf-8") as fh:
        fh.write(_build_preset_content(values))

    print()
    _ok(f"Saved  presets/{code}-metadata.txt")
    return code


# ── step 5: user_config.py ───────────────────────────────────────────────────

_USER_CONFIG_TEMPLATE = """\
# Personal config — generated by onboard.py.
# Not tracked by git. Edit this file to change your paths.

AUTHOR_CODE  = {author_code!r}

SRC          = {src!r}
DST          = {dst!r}
STAGING_DIR  = {staging!r}
SUBDIR_MODE  = {subdir_mode!r}

# Color accuracy check (optional). Set to None to disable.
COLORCHECK_REFERENCE = {colorcheck_reference!r}
"""


def _create_user_config(author_code):
    print()
    _hr()
    print("  Step 3 — Paths")
    _hr()

    if os.path.isfile(USER_CONFIG):
        print("\n  Found existing user_config.py")
        if not _confirm("Overwrite it with new values?"):
            _ok("Keeping existing user_config.py")
            return

    print(textwrap.dedent("""\

      Source      — folder containing photos to ingest
                    (you can use a different folder each time; this is the default)
      Destination — where processed files and derivatives are written
      Staging     — optional fast local drive for intermediate processing;
                    speeds things up when the destination is a slow external disk.
                    Leave blank to write directly to the destination.
    """))

    src     = _ask_path("Source directory", required=True)
    dst     = _ask_path("Destination directory", required=True)
    staging = _ask_path("Staging directory  (optional — leave blank to skip)")
    staging = staging if staging else None

    print(textwrap.dedent("""\

      Subdirectory mode — how files are grouped inside the destination:
        prefix  →  by category code (e.g. w11, d21)   ← recommended default
        id      →  by ID segment
        auto    →  id if present, otherwise prefix
    """))
    subdir_mode = _ask("Mode", default="prefix")
    if subdir_mode not in ("prefix", "id", "auto"):
        _warn(f"Unknown mode '{subdir_mode}', using 'prefix'")
        subdir_mode = "prefix"

    print(textwrap.dedent("""\

      Color accuracy check (optional) — compares a ColorChecker Mini
      target photographed in your images against reference measurements,
      flags files whose color, white balance, or exposure drift out of
      spec, and records the result in each file's metadata. It only runs
      on the naming convention's 'wNa' view (the one that includes the
      target), and does nothing unless enabled here.
    """))
    colorcheck_reference = None
    if _confirm("Enable the color accuracy check?"):
        colorcheck_reference = _ask_path(
            "Path to the CGATS.17 reference measurement file (.txt)", required=True)

    content = _USER_CONFIG_TEMPLATE.format(
        author_code=author_code,
        src=src,
        dst=dst,
        staging=staging,
        subdir_mode=subdir_mode,
        colorcheck_reference=colorcheck_reference,
    )

    with open(USER_CONFIG, "w", encoding="utf-8") as fh:
        fh.write(content)

    print()
    _ok("Saved  user_config.py")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    _hr("═")
    print("  Ingest pipeline — first-time setup")
    _hr("═")
    print()
    _hr()
    print("  Step 1 — Dependencies")
    _hr()

    _check_python()
    _setup_venv()
    _check_exiftool()

    author_code = _create_user_preset()
    _create_user_config(author_code)

    print()
    _hr("═")
    print("  Setup complete")
    _hr("═")
    print()
    if IS_WINDOWS:
        print("  To run ingest:   .\\INGEST.ps1")
        print("  To re-run setup: python onboard.py")
    else:
        print("  To run ingest:   ./INGEST")
        print("  To re-run setup: python3 onboard.py")
    print()


if __name__ == "__main__":
    main()
