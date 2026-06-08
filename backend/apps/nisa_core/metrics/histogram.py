"""
RGB histogram analizi — kırpılma, pozlama, dinamik aralık.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def analyze_histogram(pil_img: Image.Image) -> dict:
    """
    Returns:
        hist_r/g/b          — 256 bin histogram listeleri
        highlight_clip_pct  — herhangi kanalda ≥250 piksel oranı (%)
        shadow_clip_pct     — tüm kanallarda ≤5 piksel oranı (%)
        mean_brightness     — Rec.709 luminans ortalaması
        dynamic_range_score — [0-100] normalize edilmiş dinamik aralık
        exposure_label      — Türkçe pozlama etiketi
    """
    arr = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    total_px = arr.shape[0] * arr.shape[1]

    hist_r = np.bincount(r.flatten(), minlength=256).tolist()
    hist_g = np.bincount(g.flatten(), minlength=256).tolist()
    hist_b = np.bincount(b.flatten(), minlength=256).tolist()

    # Highlight clipping: herhangi bir kanalda ≥ 250
    hl_mask = (r >= 250) | (g >= 250) | (b >= 250)
    highlight_clip_pct = round(float(hl_mask.sum() / total_px * 100), 2)

    # Shadow clipping: tüm kanallarda ≤ 5
    sh_mask = (r <= 5) & (g <= 5) & (b <= 5)
    shadow_clip_pct = round(float(sh_mask.sum() / total_px * 100), 2)

    # Rec.709 luminans
    lum = (
        0.2126 * r.astype(np.float32)
        + 0.7152 * g.astype(np.float32)
        + 0.0722 * b.astype(np.float32)
    )
    mean_brightness = round(float(lum.mean()), 1)

    # Dinamik aralık — kırpılmayan piksel yüzde dilimleri
    valid_lum = lum[~(hl_mask | sh_mask)]
    if valid_lum.size > 100:
        p5, p95 = np.percentile(valid_lum, [5, 95])
        dynamic_range_score = round(float((p95 - p5) / 255 * 100), 1)
    else:
        dynamic_range_score = 0.0

    # Pozlama etiketi
    if mean_brightness > 210:
        label = "Aşırı pozlanmış"
    elif mean_brightness > 165:
        label = "Açık pozlama"
    elif mean_brightness > 85:
        label = "Dengeli"
    elif mean_brightness > 45:
        label = "Koyu pozlama"
    else:
        label = "Yetersiz pozlanmış"

    return {
        "hist_r":               hist_r,
        "hist_g":               hist_g,
        "hist_b":               hist_b,
        "highlight_clip_pct":   highlight_clip_pct,
        "shadow_clip_pct":      shadow_clip_pct,
        "mean_brightness":      mean_brightness,
        "dynamic_range_score":  dynamic_range_score,
        "exposure_label":       label,
    }
