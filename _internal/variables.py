import os

script_dir = os.path.dirname(os.path.abspath(__file__))

SRC = os.path.join(script_dir, "test_source")
DST = os.path.join(script_dir, "test_destination")
SKIPPED = "skipped_files"

# Optional: put primary (original) and derivative (JPG) files in separate
# locations, e.g. originals on a slow archive drive and derivatives on a
# fast local drive for quick browsing. Leave both as None to use the
# default DST/primary and DST/derivative layout. Override in user_config.py.
PRIMARY_DST = None
DERIVATIVE_DST = None

# Optional staging directory on a fast local drive.
# When set, all processing happens here first; at the end the result is
# bulk-copied to DST in one pass (much faster when DST is an external drive).
# Set to None to write directly to DST.
STAGING_DIR = "/tmp/process-staging"

# Color accuracy check via ColorChecker Mini.
# Set COLORCHECK_REFERENCE to an absolute path of a CGATS.17 measurement file to enable.
# Override in user_config.py.
COLORCHECK_REFERENCE = None
COLORCHECK_MEAN_DE_THRESHOLD = 4.0     # Colour accuracy: mean ΔE2000
COLORCHECK_MAX_DE_THRESHOLD = 10.0     # Colour accuracy: max ΔE2000
COLORCHECK_WB_THRESHOLD = 2.0          # White balance: ΔE(a*b*), grey patches
COLORCHECK_EXPOSURE_THRESHOLD = 2.0    # Exposure: ΔL*2000, grey patches (mean)
# Test phase: the color check runs ONLY with --colorcheck-only (read-only,
# nothing is moved or written). Set True to also run it — and write its
# result into the metadata — during a normal processing run.
COLORCHECK_IN_PIPELINE = False

# How to organize subdirectories:
#  - "id"     = group by ID segment
#  - "prefix" = group by characters 2–4 of first segment
#  - "auto"   = current behavior (id if present, otherwise prefix)
SUBDIR_MODE = "prefix"

# Legacy personal overrides (user_config.py) — still honoured if present.
try:
    from user_config import *  # noqa: F401, F403
except ImportError:
    pass

# Shared installation config (config.json at the repo root, created by
# onboard.py, not tracked by git). Overrides user_config.py.
from modules.presets import load_config as _load_config
_config = _load_config(os.path.dirname(script_dir))
if _config:
    globals().update(_config)

# Resolve primary/derivative defaults after overrides are applied.
if not PRIMARY_DST:
    PRIMARY_DST = os.path.join(DST, "primary")
if not DERIVATIVE_DST:
    DERIVATIVE_DST = os.path.join(DST, "derivative")

# load resources
with open(
    os.path.join(script_dir, "resources", "ms-zustaendigkeit.txt"), encoding="utf-8"
) as f:
    valid_first_segment_first_char = [line.strip() for line in f if line.strip()]
with open(
    os.path.join(script_dir, "resources", "ms-kategorien.txt"), encoding="utf-8"
) as f:
    valid_first_segment_other_chars = [line.strip() for line in f if line.strip()]
with open(os.path.join(script_dir, "resources", "ms-id.txt"), encoding="utf-8") as f:
    valid_id_initial_chars = [line.strip() for line in f if line.strip()]
with open(
    os.path.join(script_dir, "resources", "ms-suffix.txt"), encoding="utf-8"
) as f:
    valid_suffixes = [line.strip() for line in f if line.strip()]
with open(
    os.path.join(script_dir, "resources", "ms-metadata-tags.txt"), encoding="utf-8"
) as f:
    required_metadata_tags = [
        line.strip() for line in f if line.strip() and not line.strip().startswith("#")
    ]
