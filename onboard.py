#!/usr/bin/env python3
"""
First-time setup for the processing pipeline.

Run once before using PROCESS / PROCESS.ps1:
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

sys.path.insert(0, os.path.join(SCRIPT_DIR, "_internal", "modules"))
from presets import (CONFIG_FILE, CONFIG_KEYS, config_path,  # noqa: E402
                     list_users, save_config, write_last)


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
        _ok(f"ExifTool found in bin/  (used automatically by process.py)")
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
              process.py will find it automatically.
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
    print("  Step 3 — User  (presets/<code>-metadata.txt)")
    _hr()
    existing = list_users(PRESETS_DIR)
    print(textwrap.dedent("""\

      Each person who photographs gets one metadata preset: name,
      institution and contact details written into every image they
      process. The author code is the file name and identifies you at the
      start of every run (Enter = continue as the last user).
    """))
    if existing:
        print(f"  Existing users: {', '.join(existing)}")

    code = _ask_code()
    preset_path = os.path.join(PRESETS_DIR, f"{code}-metadata.txt")

    if os.path.isfile(preset_path):
        print(f"\n  Found existing preset:  presets/{code}-metadata.txt")
        if not _confirm("Overwrite it with new values?"):
            write_last(PRESETS_DIR, code)
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

    write_last(PRESETS_DIR, code)
    print()
    _ok(f"Saved  presets/{code}-metadata.txt")
    return code


# ── step 2: shared paths (config.json) ───────────────────────────────────────

def _migrate_user_config():
    """Offer to turn an existing user_config.py into config.json. Returns True if done."""
    if not os.path.isfile(USER_CONFIG):
        return False
    print("\n  Found an old user_config.py")
    if not _confirm("Take its paths over into config.json (user_config.py is left as is)?"):
        return False
    import runpy
    cfg = runpy.run_path(USER_CONFIG)
    save_config(SCRIPT_DIR, {k: cfg[k] for k in CONFIG_KEYS if k in cfg})
    _ok(f"Saved  {CONFIG_FILE}")
    return True


def _create_shared_config():
    print()
    _hr()
    print(f"  Step 2 — Paths  ({CONFIG_FILE}, shared by all users)")
    _hr()

    if os.path.isfile(config_path(SCRIPT_DIR)):
        print(f"\n  {CONFIG_FILE} already exists — paths are set up for this installation.")
        if not _confirm("Change them?"):
            _ok(f"Keeping {CONFIG_FILE}")
            return
    elif _migrate_user_config():
        return

    print(textwrap.dedent("""\

      Source      — folder containing photos to process
                    (you can use a different folder each time; this is the default)
      Destination — where processed files and derivatives are written
      Staging     — optional fast local drive for intermediate processing;
                    speeds things up when the destination is a slow external disk.
                    Leave blank to write directly to the destination.
    """))

    src     = _ask_path("Source directory", required=True)
    dst     = _ask_path("Destination directory", required=True)

    primary_dst = None
    derivative_dst = None
    print(textwrap.dedent("""\

      By default, both original files and JPG derivatives are written under
      the destination directory (as destination/primary and
      destination/derivative). You can instead send them to two separate
      locations — e.g. originals to a slow archive drive, derivatives to a
      fast local drive for quick browsing.
    """))
    if _confirm("Use separate directories for primary and derivative files?"):
        primary_dst = _ask_path("Primary (original) files directory", required=True)
        derivative_dst = _ask_path("Derivative (JPG) files directory", required=True)

    def _overlaps(a, b):
        a = os.path.realpath(os.path.expanduser(a))
        b = os.path.realpath(os.path.expanduser(b))
        return os.path.commonpath([a, b]) in (a, b)

    # The staging dir is deleted after every run, so it must not overlap
    # with source or any destination.
    others = [src, primary_dst or os.path.join(dst, "primary"),
              derivative_dst or os.path.join(dst, "derivative")]
    while True:
        staging = _ask_path("Staging directory  (optional — leave blank to skip)")
        staging = staging if staging else None
        if not staging or not any(_overlaps(staging, o) for o in others):
            break
        _warn("Staging must be a separate folder — not the same as, inside, or "
              "containing the source or a destination (it is emptied after each run).")

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
      spec. It only runs on the naming convention's 'wNa' view (the one
      that includes the target). During the test phase it runs only via
      PROCESS_colorcheck_only and never modifies files. Leave blank to use
      the newest bundled reference (_internal/resources/ccmi_*.txt).
    """))
    colorcheck_reference = _ask_path(
        "Path to a CGATS.17 reference measurement file (.txt)  (optional)") or None

    save_config(SCRIPT_DIR, {
        "SRC": src,
        "DST": dst,
        "PRIMARY_DST": primary_dst,
        "DERIVATIVE_DST": derivative_dst,
        "STAGING_DIR": staging,
        "SUBDIR_MODE": subdir_mode,
        "COLORCHECK_REFERENCE": colorcheck_reference,
    })

    print()
    _ok(f"Saved  {CONFIG_FILE}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print()
    _hr("═")
    print("  Processing pipeline — first-time setup")
    _hr("═")
    print()
    _hr()
    print("  Step 1 — Dependencies")
    _hr()

    _check_python()
    _setup_venv()
    _check_exiftool()

    _create_shared_config()
    _create_user_preset()

    print()
    _hr("═")
    print("  Setup complete")
    _hr("═")
    print()
    if IS_WINDOWS:
        print("  To run process:   .\\PROCESS.ps1")
        print("  Color check only: .\\PROCESS_colorcheck_only.ps1")
        print("  To re-run setup: python onboard.py")
    else:
        print("  To run process:   ./PROCESS")
        print("  Color check only: ./PROCESS_colorcheck_only")
        print("  To re-run setup: python3 onboard.py")
    print()


if __name__ == "__main__":
    main()
