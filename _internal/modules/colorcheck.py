"""Color accuracy checking using a ColorChecker Mini reference chart embedded in the image."""

import logging
import math
from io import BytesIO

import numpy as np
from PIL import Image, ImageCms

logger = logging.getLogger('ingest')

_N_ROWS = 4
_N_COLS = 6

# Patch IDs in row-major order: row 1 (neutral gray scale) first, cols A–F
_PATCH_IDS = [f"{c}{r}" for r in range(1, _N_ROWS + 1) for c in 'ABCDEF']

# Neutral gray-scale row used for the grey-patch-only metrics below.
_GREY_IDS = [f"{c}1" for c in 'ABCDEF']


# ---------------------------------------------------------------------------
# CGATS parser
# ---------------------------------------------------------------------------

def parse_cgats(path):
    """Parse CGATS.17 file. Returns {patch_id: (L*, a*, b*)} under D50/2°."""
    result = {}
    fields = []
    in_fmt = in_data = False
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line == 'BEGIN_DATA_FORMAT':
                in_fmt = True
            elif line == 'END_DATA_FORMAT':
                in_fmt = False
            elif in_fmt:
                fields = line.split()
            elif line == 'BEGIN_DATA':
                in_data = True
            elif line == 'END_DATA':
                in_data = False
            elif in_data and line:
                parts = line.split()
                if not parts:
                    continue
                pid = parts[0].strip('"')
                try:
                    L = float(parts[fields.index('LAB_L')])
                    a = float(parts[fields.index('LAB_A')])
                    b = float(parts[fields.index('LAB_B')])
                    result[pid] = (L, a, b)
                except (ValueError, IndexError):
                    pass
    if not result:
        raise ValueError(f"No Lab data found in {path}")
    return result


# ---------------------------------------------------------------------------
# CIEDE2000
# ---------------------------------------------------------------------------

def _delta_e_2000(lab1, lab2):
    """CIEDE2000 color difference between two CIE Lab tuples."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    C1 = math.sqrt(a1 ** 2 + b1 ** 2)
    C2 = math.sqrt(a2 ** 2 + b2 ** 2)
    C_avg = (C1 + C2) / 2.0
    C_avg7 = C_avg ** 7
    G = 0.5 * (1.0 - math.sqrt(C_avg7 / (C_avg7 + 25.0 ** 7)))
    a1p = a1 * (1.0 + G)
    a2p = a2 * (1.0 + G)
    C1p = math.sqrt(a1p ** 2 + b1 ** 2)
    C2p = math.sqrt(a2p ** 2 + b2 ** 2)

    def _hprime(ap, b):
        if ap == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, ap))
        return h + 360.0 if h < 0 else h

    h1p = _hprime(a1p, b1)
    h2p = _hprime(a2p, b2)
    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0.0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180.0:
        dhp = h2p - h1p
    elif h2p - h1p > 180.0:
        dhp = h2p - h1p - 360.0
    else:
        dhp = h2p - h1p + 360.0

    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))
    Lp_avg = (L1 + L2) / 2.0
    Cp_avg = (C1p + C2p) / 2.0

    if C1p * C2p == 0.0:
        hp_avg = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hp_avg = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hp_avg = (h1p + h2p + 360.0) / 2.0
    else:
        hp_avg = (h1p + h2p - 360.0) / 2.0

    T = (1.0
         - 0.17 * math.cos(math.radians(hp_avg - 30.0))
         + 0.24 * math.cos(math.radians(2.0 * hp_avg))
         + 0.32 * math.cos(math.radians(3.0 * hp_avg + 6.0))
         - 0.20 * math.cos(math.radians(4.0 * hp_avg - 63.0)))

    SL = 1.0 + 0.015 * (Lp_avg - 50.0) ** 2 / math.sqrt(20.0 + (Lp_avg - 50.0) ** 2)
    SC = 1.0 + 0.045 * Cp_avg
    SH = 1.0 + 0.015 * Cp_avg * T
    Cp7 = Cp_avg ** 7
    RC = 2.0 * math.sqrt(Cp7 / (Cp7 + 25.0 ** 7))
    d_theta = 30.0 * math.exp(-((hp_avg - 275.0) / 25.0) ** 2)
    RT = -math.sin(math.radians(2.0 * d_theta)) * RC

    return math.sqrt(
        (dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2
        + RT * (dCp / SC) * (dHp / SH)
    )


def _delta_e_ab(lab1, lab2):
    """Plain Euclidean color difference in the a*b* plane only (lightness ignored)."""
    _, a1, b1 = lab1
    _, a2, b2 = lab2
    return math.sqrt((a2 - a1) ** 2 + (b2 - b1) ** 2)


def _delta_l_2000(lab1, lab2):
    """CIEDE2000 lightness term (SL-weighted ΔL*), independent of chroma/hue."""
    L1, _, _ = lab1
    L2, _, _ = lab2
    dLp = L2 - L1
    Lp_avg = (L1 + L2) / 2.0
    SL = 1.0 + 0.015 * (Lp_avg - 50.0) ** 2 / math.sqrt(20.0 + (Lp_avg - 50.0) ** 2)
    return dLp / SL


# ---------------------------------------------------------------------------
# Color conversion: sRGB → CIELab D50
# ---------------------------------------------------------------------------

def _srgb_to_lab_d50(rgb):
    """
    Convert sRGB float array (shape …×3, values 0–1) to CIELab D50/2°.
    Applies sRGB linearisation → XYZ D65 → Bradford D65→D50 → Lab.
    """
    c = np.clip(rgb, 0.0, 1.0)
    lin = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)

    # sRGB → XYZ D65  (IEC 61966-2-1)
    M = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz65 = lin @ M.T

    # Bradford chromatic adaptation D65 → D50  (brucelindbloom.com)
    B = np.array([[ 1.0478112,  0.0228866, -0.0501270],
                  [ 0.0295424,  0.9904844, -0.0170491],
                  [-0.0092345,  0.0150436,  0.7521316]])
    xyz50 = xyz65 @ B.T

    Xn, Yn, Zn = 0.9642, 1.0000, 0.8251
    delta = 6.0 / 29.0

    def _f(t):
        return np.where(t > delta ** 3, np.cbrt(t), t / (3.0 * delta ** 2) + 4.0 / 29.0)

    fx = _f(xyz50[..., 0] / Xn)
    fy = _f(xyz50[..., 1] / Yn)
    fz = _f(xyz50[..., 2] / Zn)

    return np.stack([116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)], axis=-1)


# ---------------------------------------------------------------------------
# ColorChecker Mini detection
# ---------------------------------------------------------------------------

def _find_corner_patch_center(img_rgb, coarse_cx, coarse_cy, pw, ph,
                              target_L, target_a, target_b, search_frac=1.3):
    """
    Precisely relocate one *specific, known* reference patch (by its L*a*b*)
    near (coarse_cx, coarse_cy), within ±search_frac*size. Used only for the
    four corner patches, each of which has a distinct, known target color —
    unlike a generic "flattest region" search, matching a specific color is
    safe from collapsing onto a neighboring patch even with a wide search
    window, since neighbors have different target colors.

    Returns (cx, cy, cost) — the refined patch center in original-image
    coordinates, and the matching cost achieved there (lower is a more
    confident match; callers can compare costs across candidate hypotheses,
    e.g. which direction a row lies in).
    """
    search_x = max(2, int(round(pw * search_frac)))
    search_y = max(2, int(round(ph * search_frac)))
    x, y = coarse_cx - pw // 2, coarse_cy - ph // 2
    cx0 = max(0, x - search_x)
    cy0 = max(0, y - search_y)
    cx1 = min(img_rgb.width, x + pw + search_x)
    cy1 = min(img_rgb.height, y + ph + search_y)
    if cx1 - cx0 < pw or cy1 - cy0 < ph:
        return coarse_cx, coarse_cy, float('inf')

    mx, my = max(1, int(pw * 0.25)), max(1, int(ph * 0.25))
    iw, ih = pw - 2 * mx, ph - 2 * my
    if iw < 2 or ih < 2:
        return coarse_cx, coarse_cy, float('inf')

    arr = np.asarray(img_rgb.crop((cx0, cy0, cx1, cy1)), dtype=np.float64) / 255.0
    ch_h, ch_w = arr.shape[0], arr.shape[1]
    if ch_h < ph or ch_w < pw:
        return coarse_cx, coarse_cy, float('inf')

    def box_mean(plane):
        s = np.pad(np.cumsum(np.cumsum(plane, axis=0), axis=1), ((1, 0), (1, 0)))
        total = s[ih:, iw:] - s[:-ih, iw:] - s[ih:, :-iw] + s[:-ih, :-iw]
        return total / (ih * iw)

    def box_var(plane):
        s1 = np.pad(np.cumsum(np.cumsum(plane, axis=0), axis=1), ((1, 0), (1, 0)))
        s2 = np.pad(np.cumsum(np.cumsum(plane * plane, axis=0), axis=1), ((1, 0), (1, 0)))
        sum1 = s1[ih:, iw:] - s1[:-ih, iw:] - s1[ih:, :-iw] + s1[:-ih, :-iw]
        sum2 = s2[ih:, iw:] - s2[:-ih, iw:] - s2[ih:, :-iw] + s2[:-ih, :-iw]
        n = ih * iw
        return sum2 / n - (sum1 / n) ** 2

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    lum_mean = box_mean(lum)
    u_mean = box_mean(r - g)
    v_mean = box_mean(g - b)
    # A window straddling the dark gutter and a neighboring patch can average
    # out to *look* closer to the target than the true (uniform) patch —
    # especially under a strong color/exposure cast, where absolute targets
    # don't line up well with raw pixel values. Penalizing internal variance
    # (summed over all three channels) keeps the match on a single flat
    # patch rather than a gutter/patch blend that coincidentally scores well.
    variance = box_var(lum) + box_var(r - g) + box_var(g - b)

    # Target luminance, converted the same way the neutral-row search
    # converts reference L* to display-referred (gamma) 0..1 space.
    target_Y = ((target_L + 16.0) / 116.0) ** 3
    target_lum = (1.055 * (target_Y ** (1 / 2.4)) - 0.055
                  if target_Y > 0.0031308 else 12.92 * target_Y)
    AB_SCALE = 60.0  # brings typical a*/b* magnitudes onto a comparable 0..1-ish scale
    VARIANCE_WEIGHT = 8.0

    dist = ((lum_mean - target_lum) ** 2
            + (u_mean - target_a / AB_SCALE) ** 2
            + (v_mean - target_b / AB_SCALE) ** 2
            + VARIANCE_WEIGHT * variance)

    valid = dist[my:dist.shape[0] - my, mx:dist.shape[1] - mx]
    if valid.size == 0:
        return coarse_cx, coarse_cy, float('inf')
    idx = int(np.argmin(valid))
    dy, dx = np.unravel_index(idx, valid.shape)
    new_x, new_y = cx0 + int(dx), cy0 + int(dy)
    return new_x + pw // 2, new_y + ph // 2, float(valid.flat[idx])


def _solve_homography(src_pts, dst_pts):
    """
    Solve the 3x3 homography H mapping each src (x, y) to the corresponding
    dst (x, y) (up to scale), via direct linear transform on exactly 4 point
    correspondences.
    """
    a = []
    for (sx, sy), (dx, dy) in zip(src_pts, dst_pts):
        a.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy, -dx])
        a.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy, -dy])
    a = np.array(a, dtype=np.float64)
    _, _, vt = np.linalg.svd(a)
    h = vt[-1].reshape(3, 3)
    return h / h[2, 2]


def _apply_homography(h, x, y):
    v = h @ np.array([x, y, 1.0])
    return v[0] / v[2], v[1] / v[2]


def _detect_colorchecker_mini(img_rgb, reference, n_rows=_N_ROWS, n_cols=_N_COLS):
    """
    Detect a ColorChecker Mini grid in *img_rgb* (PIL Image, RGB mode).

    Strategy: downsample to ≤2800 px, build block-mean matrices at multiple
    scales, slide a n_rows×n_cols window and look for a row with the neutral
    gray-ramp signature (low saturation, monotonically increasing luminance
    correlating with the known L* ladder).  Both horizontal and vertical chart
    orientations are tried; the higher-scoring match wins.

    That thumbnail-block search only needs to be trustworthy for the neutral
    row (and its two endpoint patches, A1/F1) — its known L* ladder is a
    strong, well-separated signal. The far corners (A{n_rows}/F{n_rows}) are
    then found independently: both possible directions away from the neutral
    row are tried with a wide, specific-known-color search (matching each
    corner's own distinct L*a*b* target plus an internal-uniformity penalty,
    so it can't collapse onto a neighboring patch or a gutter even with a
    generous search window), and whichever direction's two corners actually
    match best is kept. This avoids ever trusting the thumbnail's coarse
    patch-pitch estimate across the whole grid — that estimate can be
    imprecise enough, especially for a chart that's small relative to a
    large/busy scan, that walking a fixed number of blocks away from the
    neutral row misses the true row entirely. A homography fit from the four
    corners then places all 24 patches, correcting perspective/registration
    drift and rejecting lookalike charts (e.g. SMPTE color bars) whose actual
    corner colors don't match this specific reference target.

    Returns a list of 24 (x, y, pw, ph) patch bounding boxes in original-image
    coordinates, ordered as _PATCH_IDS (A1…F1, A2…F4), or None if not found.
    """
    # 1200px was too coarse for a chart that's small relative to a large scan
    # (e.g. a full-frame artwork digitization with a small target strip along
    # one edge) — its patches could shrink below the block-size search floor.
    MAX_DIM = 2800
    orig_w, orig_h = img_rgb.size
    scale = min(MAX_DIM / orig_w, MAX_DIM / orig_h, 1.0)
    tw = max(1, int(round(orig_w * scale)))
    th = max(1, int(round(orig_h * scale)))
    thumb = img_rgb.resize((tw, th), Image.LANCZOS) if scale < 1.0 else img_rgb

    arr = np.asarray(thumb, dtype=np.float32) / 255.0
    r_ch, g_ch, b_ch = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    lum = 0.2126 * r_ch + 0.7152 * g_ch + 0.0722 * b_ch
    cmax = np.maximum(np.maximum(r_ch, g_ch), b_ch)
    cmin = np.minimum(np.minimum(r_ch, g_ch), b_ch)
    # np.where(cond, a/b, 0.0) still evaluates a/b for every element — including
    # where b=0 (pure black pixels) — triggering a spurious "invalid value in
    # divide" warning even though that 0/0 result is immediately discarded.
    # np.divide's `where=` skips the division there entirely instead.
    sat = np.zeros_like(cmax)
    np.divide(cmax - cmin, cmax, out=sat, where=cmax > 1e-6)

    # Expected neutral-row display values converted from reference L* values
    ref_L = np.array([21.17, 36.28, 50.80, 66.88, 81.56, 97.18])
    ref_Y = ((ref_L + 16.0) / 116.0) ** 3
    ref_disp = np.where(ref_Y > 0.0031308,
                        1.055 * np.power(np.clip(ref_Y, 0.0, 1.0), 1.0 / 2.4) - 0.055,
                        12.92 * ref_Y)
    ref_norm = (ref_disp - ref_disp.min()) / (ref_disp.max() - ref_disp.min())
    ref_rev  = ref_norm[::-1].copy()
    ref_c    = ref_norm - ref_norm.mean()
    ref_c_r  = ref_rev  - ref_rev.mean()
    ref_std  = float(ref_norm.std())

    MIN_CORR = 0.82
    MIN_FULL_GRID_CORR = 0.5
    # Collect every locally-good neutral-row candidate rather than only the
    # single highest-scoring one: a busy image can contain a lookalike (e.g.
    # a printed documentation sheet reproducing the same reference values as
    # a small table) that scores *better* than the real target under this
    # coarse, thumbnail-only metric. The corner-matching stage below is far
    # more discriminating (it checks each corner against its own specific
    # known color), so it gets the final say among the top candidates here.
    candidates = []  # (score, bs, r0, c0, nr, rev, orient)

    # Try horizontal orientation, then vertical (transposed image).
    # In the transposed case lum_o rows = original columns, so a "horizontal"
    # neutral row in transposed space is a vertical neutral column in the image.
    for orient in ('h', 'v'):
        if orient == 'v':
            lum_o, sat_o = lum.T, sat.T   # shape (tw, th)
            h_o, w_o = tw, th
        else:
            lum_o, sat_o = lum, sat
            h_o, w_o = th, tw

        max_bs = min(w_o // n_cols, h_o // n_rows, 200)

        for bs in range(20, max_bs + 1, 4):
            rows_fit = h_o // bs
            cols_fit = w_o // bs
            if rows_fit < n_rows or cols_fit < n_cols:
                continue

            ch_px, cw_px = rows_fit * bs, cols_fit * bs
            lum_b = lum_o[:ch_px, :cw_px].reshape(rows_fit, bs, cols_fit, bs).mean(axis=(1, 3))
            sat_b = sat_o[:ch_px, :cw_px].reshape(rows_fit, bs, cols_fit, bs).mean(axis=(1, 3))

            for r0 in range(rows_fit - n_rows + 1):
                lum_strip = lum_b[r0:r0 + n_rows, :]  # (n_rows, cols_fit)
                sat_strip = sat_b[r0:r0 + n_rows, :]

                # Sliding windows along columns → (n_rows, n_c0, n_cols)
                lum_wins = np.lib.stride_tricks.sliding_window_view(lum_strip, n_cols, axis=1)
                sat_wins = np.lib.stride_tricks.sliding_window_view(sat_strip, n_cols, axis=1)

                for nr in range(n_rows):
                    row_lum = lum_wins[nr]  # (n_c0, n_cols)
                    row_sat = sat_wins[nr]

                    sat_mean  = row_sat.mean(axis=1)          # (n_c0,)
                    lum_min   = row_lum.min(axis=1)
                    lum_rng   = row_lum.max(axis=1) - lum_min

                    # Neutral row must span a wide dark-to-light range; the
                    # darkest patch must be clearly below mid-gray. Some
                    # capture techniques (e.g. cross-polarized photography,
                    # which suppresses specular highlights) compress this
                    # range well below what a normally-lit chart shows —
                    # 0.30 still safely excludes flat/no-signal regions
                    # while admitting a genuine but lower-contrast ramp.
                    valid = (sat_mean < 0.14) & (lum_rng > 0.30) & (lum_min < 0.40)
                    if not valid.any():
                        continue

                    denom = np.where(lum_rng > 0, lum_rng, 1.0)
                    norm  = (row_lum - lum_min[:, None]) / denom[:, None]  # (n_c0, n_cols)

                    n_c   = norm - norm.mean(axis=1, keepdims=True)
                    n_std = n_c.std(axis=1)
                    safe  = np.where(n_std > 0, n_std, 1.0)

                    corr_fwd = (n_c * ref_c).mean(axis=1)   / (safe * ref_std)
                    corr_rev = (n_c * ref_c_r).mean(axis=1) / (safe * ref_std)
                    use_rev  = corr_rev > corr_fwd
                    best_corr = np.where(use_rev, corr_rev, corr_fwd)

                    other_ids = [i for i in range(n_rows) if i != nr]
                    other_sat = np.stack([sat_wins[i].mean(axis=1) for i in other_ids]).mean(axis=0)
                    sat_ratio = other_sat / np.maximum(sat_mean, 0.01)

                    score = best_corr * np.clip(sat_ratio / 2.0, 0.0, 1.0)
                    score = np.where(valid & (best_corr > MIN_CORR), score, -1.0)

                    if score.max() > MIN_CORR:
                        c0_local = int(np.argmax(score))
                        candidates.append((float(score[c0_local]), bs, r0, c0_local,
                                          nr, bool(use_rev[c0_local]), orient))

    if not candidates:
        return None

    # --- De-duplicate: many (bs, r0, nr) combinations can all be scoring the
    # same physical region at slightly different scales/offsets. Keep only
    # the top-scoring candidate per distinct location (greedy non-max
    # suppression by approximate pixel position), up to a handful of the
    # best-scoring, well-separated candidates.
    def _approx_pixel(bs_c, r0_c, c0_c, nr_c, orient_c):
        block_row = r0_c + nr_c
        if orient_c == 'h':
            return c0_c * bs_c * orig_w / tw, block_row * bs_c * orig_h / th
        return block_row * bs_c * orig_w / tw, c0_c * bs_c * orig_h / th

    candidates.sort(key=lambda c: -c[0])
    min_separation = 0.03 * max(orig_w, orig_h)
    selected = []
    selected_pixels = []
    for cand in candidates:
        px, py = _approx_pixel(cand[1], cand[2], cand[3], cand[4], cand[6])
        if any(abs(px - spx) < min_separation and abs(py - spy) < min_separation
              for spx, spy in selected_pixels):
            continue
        selected.append(cand)
        selected_pixels.append((px, py))
        if len(selected) >= 10:
            break

    def _evaluate_candidate(bs, r0, c0, nr, rev, orient):
        """
        Precisely locate all four corners for one coarse candidate and, if
        they check out, build the full 24-patch grid via homography.
        Returns (patches_or_None, total_cost) — total_cost lets the caller
        rank multiple candidates and keep the best-matching one.
        """
        neutral_block_row = r0 + nr
        pw = max(1, int(round(bs * orig_w / tw)))
        ph = max(1, int(round(bs * orig_h / th)))

        def _block_pixel(block_row, grid_col):
            actual = (n_cols - 1 - grid_col) if rev else grid_col
            block_col = c0 + actual
            if orient == 'h':
                x = max(0, int(round(block_col * bs * orig_w / tw)))
                y = max(0, int(round(block_row * bs * orig_h / th)))
            else:
                x = max(0, int(round(block_row * bs * orig_w / tw)))
                y = max(0, int(round(block_col * bs * orig_h / th)))
            return x, y

        # Neutral row's own two endpoint patches (A1, F1) come straight out
        # of the L*-ladder correlation search that already found the winning
        # window, so they're trustworthy as-is; a modest refinement window
        # just cleans up residual block-quantization jitter.
        def _corner_center(block_row, grid_col, row_num, search_frac):
            x, y = _block_pixel(block_row, grid_col)
            patch_id = f"{'ABCDEF'[grid_col]}{row_num}"
            target_L, target_a, target_b = reference.get(patch_id, (50.0, 0.0, 0.0))
            return _find_corner_patch_center(img_rgb, x + pw // 2, y + ph // 2, pw, ph,
                                             target_L, target_a, target_b, search_frac=search_frac)

        near_cx0, near_cy0, near_cost0 = _corner_center(neutral_block_row, 0, 1, 1.3)
        near_cx1, near_cy1, near_cost1 = _corner_center(neutral_block_row, n_cols - 1, 1, 1.3)
        if not (np.isfinite(near_cost0) and np.isfinite(near_cost1)):
            return None, float('inf')

        # `bs` is a coarse, block-quantized guess at the patch pitch and can
        # be substantially off (we've seen both over- and under-estimates).
        # The distance actually found between A1 and F1 is a much more
        # reliable size estimate — if it disagrees with the box size used
        # above by more than a bit, redo the near-corner search with the
        # corrected size before it feeds into everything downstream.
        measured_pitch = math.hypot(near_cx1 - near_cx0, near_cy1 - near_cy0) / (n_cols - 1)
        if measured_pitch > 0 and abs(measured_pitch - pw) > 0.15 * pw:
            pw = ph = max(1, int(round(measured_pitch)))
            near_cx0, near_cy0, near_cost0 = _corner_center(neutral_block_row, 0, 1, 1.3)
            near_cx1, near_cy1, near_cost1 = _corner_center(neutral_block_row, n_cols - 1, 1, 1.3)
            if not (np.isfinite(near_cost0) and np.isfinite(near_cost1)):
                return None, float('inf')

        def _build_and_validate(fcx0, fcy0, fcx1, fcy1):
            """
            Build the 24-patch grid from these four corners and score it by
            how well its whole hue pattern (not just the 4 corners) matches
            the reference — the real arbiter between competing hypotheses,
            since two different corner colors' raw match costs aren't
            comparable to each other (a color that's inherently easier to
            match isn't evidence of being the *correct* location).
            """
            src_pts = [(0.5, 0.5), (n_cols - 0.5, 0.5),
                      (0.5, n_rows - 0.5), (n_cols - 0.5, n_rows - 0.5)]
            dst_pts = [(near_cx0, near_cy0), (near_cx1, near_cy1),
                      (fcx0, fcy0), (fcx1, fcy1)]
            try:
                homography = _solve_homography(src_pts, dst_pts)
                if not np.all(np.isfinite(homography)):
                    return None, -2.0
            except np.linalg.LinAlgError:
                return None, -2.0

            patches = []
            for grid_row in range(n_rows):
                for grid_col in range(n_cols):
                    cx, cy = _apply_homography(homography, grid_col + 0.5, grid_row + 0.5)
                    x = int(round(cx - pw / 2))
                    y = int(round(cy - ph / 2))
                    x = max(0, min(x, orig_w - pw))
                    y = max(0, min(y, orig_h - ph))
                    patches.append((x, y, pw, ph))

            u_vals, v_vals, a_refs, b_refs = [], [], [], []
            for pid, (x, y, ppw, pph) in zip(_PATCH_IDS, patches):
                smx, smy = max(1, int(ppw * 0.25)), max(1, int(pph * 0.25))
                crop = img_rgb.crop((x + smx, y + smy, x + ppw - smx, y + pph - smy))
                samp = np.asarray(crop, dtype=np.float64) / 255.0
                if samp.size == 0:
                    continue
                mr, mg, mb = samp.reshape(-1, 3).mean(axis=0)
                u_vals.append(mr - mg)
                v_vals.append(mg - mb)
                L_ref, a_ref, b_ref = reference.get(pid, (50.0, 0.0, 0.0))
                a_refs.append(a_ref)
                b_refs.append(b_ref)
            u = np.array(u_vals) - np.mean(u_vals)
            v = np.array(v_vals) - np.mean(v_vals)
            a_c = np.array(a_refs) - np.mean(a_refs)
            b_c = np.array(b_refs) - np.mean(b_refs)
            denom = np.sqrt((u ** 2 + v ** 2).sum()) * np.sqrt((a_c ** 2 + b_c ** 2).sum())
            corr = float((u @ a_c + v @ b_c) / denom) if denom >= 1e-9 else -2.0
            return patches, corr

        # The far row (grid_row = n_rows-1) has no reliable coarse position:
        # the thumbnail's block-quantized `bs` can underestimate the chart's
        # true patch pitch by a large margin (we've seen ~35%), so walking
        # (n_rows-1) blocks away from the neutral row can land far short of
        # the real row — even a generously wide search around that wrong
        # estimate then converges on the wrong (nearer) row instead.
        # Instead, derive the row pitch geometrically from the near row's
        # own two corners (A1→F1), which are already precisely located:
        # per-column step = (F1 - A1) / (n_cols-1); the row step is that
        # vector rotated 90° (ColorChecker patches are ~square), so walking
        # (n_rows-1) row-steps from A1/F1 gives a pixel-accurate estimate of
        # where A{n_rows}/F{n_rows} actually are, regardless of how far off
        # `bs` was.
        col_dx = (near_cx1 - near_cx0) / (n_cols - 1)
        col_dy = (near_cy1 - near_cy0) / (n_cols - 1)
        row_dx, row_dy = -col_dy, col_dx
        far_pw = far_ph = max(1, int(round(math.hypot(col_dx, col_dy))))
        id0 = "A" + str(n_rows)
        id1 = 'ABCDEF'[n_cols - 1] + str(n_rows)
        L0, a0, b0 = reference.get(id0, (50.0, 0.0, 0.0))
        L1, a1, b1 = reference.get(id1, (50.0, 0.0, 0.0))

        # Search both far corners independently. Each one, on its own, is a
        # candidate anchor for the whole far row (the other corner can be
        # derived from it via the near row's own column vector — same rigid
        # chart ⇒ same column spacing on every row). Two independently
        # *searched* positions can each land on a different, wrong row (a
        # coincidentally-plausible nearer row beating the true, farther
        # one), and their raw match costs aren't comparable to each other
        # (different target colors are inherently easier or harder to
        # match) — so instead of trusting whichever searched corner scored
        # lower, build the full grid from *each* hypothesis and let the
        # whole-grid correlation below (comparing all 24 patches against
        # reference, not just one corner's color) decide which is right.
        FAR_SEARCH_FRAC = 1.5
        best_patches, best_corr = None, -2.0
        for direction in (1, -1):
            est_x0 = near_cx0 + direction * row_dx * (n_rows - 1)
            est_y0 = near_cy0 + direction * row_dy * (n_rows - 1)
            est_x1 = near_cx1 + direction * row_dx * (n_rows - 1)
            est_y1 = near_cy1 + direction * row_dy * (n_rows - 1)
            far_cx0, far_cy0, far_cost0 = _find_corner_patch_center(
                img_rgb, int(round(est_x0)), int(round(est_y0)), far_pw, far_ph,
                L0, a0, b0, search_frac=FAR_SEARCH_FRAC)
            far_cx1, far_cy1, far_cost1 = _find_corner_patch_center(
                img_rgb, int(round(est_x1)), int(round(est_y1)), far_pw, far_ph,
                L1, a1, b1, search_frac=FAR_SEARCH_FRAC)
            if not (np.isfinite(far_cost0) and np.isfinite(far_cost1)):
                continue

            hypotheses = [
                (far_cx0, far_cy0, far_cx0 + (n_cols - 1) * col_dx, far_cy0 + (n_cols - 1) * col_dy),
                (far_cx1 - (n_cols - 1) * col_dx, far_cy1 - (n_cols - 1) * col_dy, far_cx1, far_cy1),
            ]
            for hx0, hy0, hx1, hy1 in hypotheses:
                patches, corr = _build_and_validate(hx0, hy0, hx1, hy1)
                if patches is not None and corr > best_corr:
                    best_patches, best_corr = patches, corr

        if best_patches is None or best_corr < MIN_FULL_GRID_CORR:
            return None, -2.0

        return best_patches, best_corr

    # Rank candidates by full-grid correlation, not raw corner-match cost:
    # cost isn't comparable across candidates at different scales (a
    # smaller search box inherently yields lower variance/cost regardless
    # of correctness) or between different target colors, but the full-grid
    # correlation always measures the same thing — how well all 24 sampled
    # patches' hues match the reference's — so it's the one score that's
    # meaningfully comparable between competing bs/orientation hypotheses.
    best_patches, best_corr = None, -2.0
    for _, bs, r0, c0, nr, rev, orient in selected:
        patches, corr = _evaluate_candidate(bs, r0, c0, nr, rev, orient)
        if patches is not None and corr > best_corr:
            best_patches, best_corr = patches, corr

    return best_patches


# ---------------------------------------------------------------------------
# Patch sampling
# ---------------------------------------------------------------------------

def _sample_patch_lab(img, bbox, icc_bytes=None):
    """
    Sample the inner 50% (linear) of *bbox* from *img* — i.e. 25% of its
    area — and return mean CIELab D50. Uses the embedded ICC profile for
    source→sRGB conversion when available.
    """
    x, y, pw, ph = bbox
    mx = max(1, int(pw * 0.25))
    my = max(1, int(ph * 0.25))
    x1, y1 = x + mx, y + my
    x2, y2 = x + pw - mx, y + ph - my
    if x2 <= x1 or y2 <= y1:
        x1, y1, x2, y2 = x, y, x + pw, y + ph

    crop = img.crop((x1, y1, x2, y2))

    if icc_bytes:
        try:
            src  = ImageCms.ImageCmsProfile(BytesIO(icc_bytes))
            srgb = ImageCms.createProfile('sRGB')
            t    = ImageCms.buildTransform(src, srgb, 'RGB', 'RGB',
                                           renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
            crop = ImageCms.applyTransform(crop, t)
        except Exception:
            pass  # fall through to raw pixel values

    arr = np.asarray(crop, dtype=np.float32) / 255.0
    mean_rgb = arr.reshape(-1, 3).mean(axis=0)
    lab = _srgb_to_lab_d50(mean_rgb)
    return (float(lab[0]), float(lab[1]), float(lab[2]))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_color_accuracy_check(image_path, reference_path, logger,
                             mean_de_threshold=4.0, max_de_threshold=10.0,
                             wb_threshold=2.0, exposure_threshold=2.0):
    """
    Detect a ColorChecker Mini in *image_path*, measure each patch, and
    compare against *reference_path* (CGATS.17).  Results are written to
    the ingest log as a formatted table.

    Three independent criteria are evaluated:
      - Colour accuracy: mean ΔE2000 ≤ mean_de_threshold, max ΔE2000 ≤ max_de_threshold
      - White balance:   ΔE(a*b*)  (grey patches) ≤ wb_threshold
      - Exposure:        ΔL*2000   (grey patches, mean |·|) ≤ exposure_threshold

    Returns a report dict, or None on hard failure.
    """
    import os
    fname = os.path.basename(image_path)

    try:
        reference = parse_cgats(reference_path)
    except Exception as e:
        logger.warning("Color check: cannot read reference %s: %s", reference_path, e)
        return None

    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        icc_bytes = img.info.get('icc_profile')
    except Exception as e:
        logger.warning("Color check: cannot open %s: %s", fname, e)
        return None

    patches = _detect_colorchecker_mini(img, reference)
    if patches is None:
        logger.info("Color check: ColorChecker Mini not detected in %s — skipped", fname)
        return {'found': False, 'file': fname}

    logger.info("Color check: ColorChecker Mini detected in %s", fname)

    results = {}
    for pid, bbox in zip(_PATCH_IDS, patches):
        if pid not in reference:
            continue
        try:
            meas = _sample_patch_lab(img, bbox, icc_bytes)
            de   = _delta_e_2000(reference[pid], meas)
            results[pid] = {'reference': reference[pid], 'measured': meas, 'delta_e': de}
        except Exception as e:
            logger.debug("Color check: patch %s failed: %s", pid, e)

    if not results:
        logger.warning("Color check: no patches sampled in %s", fname)
        return {'found': True, 'file': fname, 'patches': {}}

    de_vals    = [r['delta_e'] for r in results.values()]
    mean_de    = sum(de_vals) / len(de_vals)
    max_de     = max(de_vals)
    max_patch  = max(results, key=lambda k: results[k]['delta_e'])
    pass_color = mean_de <= mean_de_threshold and max_de <= max_de_threshold

    # --- grey-patch-only metrics (neutral row A1–F1) ---
    grey_ab_vals = []
    grey_l_vals  = []
    for pid in _GREY_IDS:
        if pid not in results:
            continue
        r = results[pid]
        grey_ab_vals.append(_delta_e_ab(r['reference'], r['measured']))
        grey_l_vals.append(abs(_delta_l_2000(r['reference'], r['measured'])))

    mean_de_ab_grey  = sum(grey_ab_vals) / len(grey_ab_vals) if grey_ab_vals else None
    mean_dl2000_grey = sum(grey_l_vals) / len(grey_l_vals) if grey_l_vals else None

    pass_wb       = mean_de_ab_grey is None or mean_de_ab_grey <= wb_threshold
    pass_exposure = mean_dl2000_grey is None or mean_dl2000_grey <= exposure_threshold
    passed        = pass_color and pass_wb and pass_exposure

    # --- log table ---
    logger.info("Color check  %s  —  %d patches  ΔE2000 thresholds: avg≤%.1f max≤%.1f",
                fname, len(results), mean_de_threshold, max_de_threshold)
    logger.info("  %-4s  %6s %6s %6s    %6s %6s %6s    %s",
                "ID", "L*ref", "a*ref", "b*ref", "L*meas", "a*meas", "b*meas", "ΔE2000")
    logger.info("  " + "-" * 66)
    for pid in _PATCH_IDS:
        if pid not in results:
            continue
        r = results[pid]
        Lr, ar, br = r['reference']
        Lm, am, bm = r['measured']
        de = r['delta_e']
        flag = "  !" if de > max_de_threshold else ""
        logger.info("  %-4s  %6.2f %6.2f %6.2f    %6.2f %6.2f %6.2f    %5.2f%s",
                    pid, Lr, ar, br, Lm, am, bm, de, flag)

    logger.info("  Colour accuracy:          mean ΔE2000=%.2f (≤%.1f)  max ΔE2000=%.2f (%s, ≤%.1f)  → %s",
                mean_de, mean_de_threshold, max_de, max_patch, max_de_threshold,
                "PASS" if pass_color else "FAIL")
    if mean_de_ab_grey is not None:
        logger.info("  White balance (grey):     ΔE(a*b*)=%.2f (≤%.1f)  → %s",
                    mean_de_ab_grey, wb_threshold, "PASS" if pass_wb else "FAIL")
        logger.info("  Exposure (grey):          ΔL*2000=%.2f (≤%.1f)  → %s",
                    mean_dl2000_grey, exposure_threshold, "PASS" if pass_exposure else "FAIL")

    status = "PASS" if passed else "FAIL"
    logger.info("  Color check SUMMARY: %s", status)
    if not passed:
        logger.warning("Color accuracy out of spec: %s  → %s", fname, status)

    report = {
        'found':              True,
        'file':               fname,
        'patches':            results,
        'mean_de':            mean_de,
        'max_de':             max_de,
        'max_patch':          max_patch,
        'mean_de_threshold':  mean_de_threshold,
        'max_de_threshold':   max_de_threshold,
        'mean_de_ab_grey':    mean_de_ab_grey,
        'mean_dl2000_grey':   mean_dl2000_grey,
        'wb_threshold':       wb_threshold,
        'exposure_threshold': exposure_threshold,
        'pass_color':         pass_color,
        'pass_wb':            pass_wb,
        'pass_exposure':      pass_exposure,
        'pass':               passed,
    }

    _write_colorcheck_metadata(image_path, report, logger)

    return report


# ---------------------------------------------------------------------------
# Write extended test results into the file's own metadata
# ---------------------------------------------------------------------------

def _write_colorcheck_metadata(image_path, report, logger):
    """
    Append the color-check summary onto the file's XMP-photoshop:Instructions
    field — the same field the metadata presets can populate — rather than a
    separate custom tag. If Instructions already holds something (e.g. from
    an author preset), the summary is appended after a '; ' separator
    instead of overwriting it.
    """
    import json
    import shutil
    import subprocess

    from modules.exifwriter import write_metadata_to_file

    parts = [f"mean ΔE2000={report['mean_de']:.2f}",
            f"max ΔE2000={report['max_de']:.2f}"]
    if report['mean_de_ab_grey'] is not None:
        parts.append(f"WB ΔE(a*b*)={report['mean_de_ab_grey']:.2f}")
    if report['mean_dl2000_grey'] is not None:
        parts.append(f"Exposure ΔL*2000={report['mean_dl2000_grey']:.2f}")
    status = 'PASS' if report['pass'] else 'FAIL'
    summary = f"Color accuracy: {status} ({'; '.join(parts)})"

    existing = ''
    if shutil.which('exiftool'):
        try:
            proc = subprocess.run(
                ['exiftool', '-j', '-XMP-photoshop:Instructions', image_path],
                capture_output=True, text=True, encoding='utf-8', check=True)
            data = json.loads(proc.stdout)
            if data:
                existing = (data[0].get('Instructions') or '').strip()
        except Exception as e:
            logger.debug("Color check: could not read existing Instructions: %s", e)

    new_value = f"{existing}; {summary}" if existing else summary
    write_metadata_to_file(image_path,
                           ['-overwrite_original', f'-XMP-photoshop:Instructions={new_value}'],
                           dry_run=False, logger=logger)
