"""
Shared config and user selection.

- config.json (repo root, not tracked by git): paths and settings shared by
  all users of this installation — set once per machine.
- presets/<code>-metadata.txt (not tracked by git): one per user — the
  metadata written into every image. The author code is the file name.
- presets/.last-user: the user who ran last; Enter at the start prompt
  continues with them.

Stdlib only — also used by onboard.py before the venv exists.
"""

import json
import os
import re
import sys

CONFIG_FILE = "config.json"
METADATA_SUFFIX = "-metadata.txt"
LAST_USER_FILE = ".last-user"
EXAMPLE_NAME = "example"   # presets/example-metadata.txt is a template, never offered

# Keys config.json may set (same names as in variables.py).
CONFIG_KEYS = (
    "SRC",
    "DST",
    "PRIMARY_DST",
    "DERIVATIVE_DST",
    "STAGING_DIR",
    "SUBDIR_MODE",
    "COLORCHECK_REFERENCE",
    "COLORCHECK_MEAN_DE_THRESHOLD",
    "COLORCHECK_MAX_DE_THRESHOLD",
    "COLORCHECK_WB_THRESHOLD",
    "COLORCHECK_EXPOSURE_THRESHOLD",
)
_PATH_KEYS = ("SRC", "DST", "PRIMARY_DST", "DERIVATIVE_DST", "STAGING_DIR",
              "COLORCHECK_REFERENCE")


class PresetError(Exception):
    pass


# ── shared config ────────────────────────────────────────────────────────────

def config_path(repo_root):
    return os.path.join(repo_root, CONFIG_FILE)


def load_config(repo_root):
    """Return config.json as a dict (paths expanded), or None if it doesn't exist."""
    path = config_path(repo_root)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as e:
        raise PresetError(f"invalid JSON in {CONFIG_FILE}: {e}")
    if not isinstance(data, dict):
        raise PresetError(f"{CONFIG_FILE} must contain a JSON object")
    unknown = sorted(set(data) - set(CONFIG_KEYS))
    if unknown:
        raise PresetError(f"unknown key(s) in {CONFIG_FILE}: {', '.join(unknown)}")
    for key in _PATH_KEYS:
        if data.get(key):
            data[key] = os.path.normpath(os.path.expandvars(os.path.expanduser(data[key])))
    return data


def save_config(repo_root, data):
    with open(config_path(repo_root), "w", encoding="utf-8") as fh:
        json.dump({k: data.get(k) for k in CONFIG_KEYS if k in data},
                  fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ── users (= metadata presets) ───────────────────────────────────────────────

def list_users(presets_dir):
    if not os.path.isdir(presets_dir):
        return []
    codes = (f[:-len(METADATA_SUFFIX)] for f in os.listdir(presets_dir)
             if f.endswith(METADATA_SUFFIX))
    return sorted(c for c in codes if c != EXAMPLE_NAME)


def creator_name(presets_dir, code):
    """The Creator= value of a user's metadata preset (for display only)."""
    try:
        with open(os.path.join(presets_dir, code + METADATA_SUFFIX), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r'\s*Creator\s*=\s*"?(.*?)"?\s*$', line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return ""


def read_last(presets_dir):
    try:
        with open(os.path.join(presets_dir, LAST_USER_FILE), encoding="utf-8") as fh:
            code = fh.read().strip()
    except OSError:
        return None
    return code if code in list_users(presets_dir) else None


def write_last(presets_dir, code):
    try:
        with open(os.path.join(presets_dir, LAST_USER_FILE), "w", encoding="utf-8") as fh:
            fh.write(code + "\n")
    except OSError:
        pass


def _input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\nAborted.")
        sys.exit(0)


def _label(presets_dir, code):
    name = creator_name(presets_dir, code)
    return f"{code}  ({name})" if name else code


def _pick_from_list(presets_dir, codes):
    print()
    for i, c in enumerate(codes, 1):
        print(f"    {i}) {_label(presets_dir, c)}")
    while True:
        val = _input("\n  Number or code: ").lower()
        if val.isdigit() and 1 <= int(val) <= len(codes):
            return codes[int(val) - 1]
        if val in codes:
            return val
        print("  ! Invalid choice.")


def choose_user(presets_dir, requested=None, assume_yes=False):
    """
    Decide who is working. Returns an author code, or None when no metadata
    presets exist.

    - requested:   code given on the command line (used as-is, no prompt)
    - assume_yes:  take the last user without asking (also the behaviour
                   when stdin is not a terminal)
    Interactive: Enter continues with the last user; typing another code
    switches; anything else shows the list.
    """
    codes = list_users(presets_dir)
    if requested:
        requested = requested.lower()
        if requested not in codes:
            raise PresetError(f"no metadata preset for '{requested}' "
                              f"(presets/{requested}{METADATA_SUFFIX})"
                              + (f" — available: {', '.join(codes)}" if codes else ""))
        write_last(presets_dir, requested)
        return requested
    if not codes:
        return None

    last = read_last(presets_dir)
    if not last and len(codes) == 1:
        last = codes[0]
    interactive = sys.stdin.isatty() and not assume_yes

    if not interactive:
        if last:
            return last
        raise PresetError("several users exist and none ran before — "
                          "pass --user CODE")

    if last:
        others = [c for c in codes if c != last]
        print(f"\n  User: {_label(presets_dir, last)}")
        hint = f"switch: type {', '.join(others)}" if others else "Ctrl-C = cancel"
        val = _input(f"  Enter = continue  ·  {hint}\n  > ").lower()
        if val == "":
            chosen = last
        elif val in codes:
            chosen = val
        else:
            chosen = _pick_from_list(presets_dir, codes)
    else:
        print("\n  Who is working?")
        chosen = _pick_from_list(presets_dir, codes)

    print(f"  → {_label(presets_dir, chosen)}")
    write_last(presets_dir, chosen)
    return chosen
