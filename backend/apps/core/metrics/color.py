"""
Renk analizi — beyaz dengesi, renk sıcaklığı, cast, dominant renkler, doygunluk.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


# ── Renk sıcaklığı tahmini ───────────────────────────────────

def _estimate_temperature(r: float, g: float, b: float) -> tuple[int, str]:
    """Grey-world'den kabaca Kelvin tahmini (R/B oranı tabanlı)."""
    b = max(b, 1.0)
    r = max(r, 1.0)
    rb = r / b

    if rb > 1.6:  return 2700,  "Tungsten / Gün batımı (~2700K)"
    if rb > 1.3:  return 3500,  "Sıcak beyaz / İç mekan (~3500K)"
    if rb > 1.1:  return 4500,  "Sabah / Akşam ışığı (~4500K)"
    if rb > 0.9:  return 5600,  "Gün ışığı, nötr (~5600K)"
    if rb > 0.75: return 7000,  "Bulutlu hava (~7000K)"
    return 9000, "Gölge / Mavi saati (~9000K+)"


def _detect_cast(r: float, g: float, b: float) -> tuple[str, float]:
    """Renk tonu sapması yönü ve gücü."""
    mean = (r + g + b) / 3
    if mean < 1:
        return "nötr", 0.0
    rn, gn, bn = r / mean, g / mean, b / mean
    max_dev = max(abs(rn - 1), abs(gn - 1), abs(bn - 1))
    strength = round(float(max_dev), 3)

    if max_dev < 0.07:
        return "nötr", strength
    if rn > gn and rn > bn:
        return "kırmızı / sıcak", strength
    if bn > rn and bn > gn:
        return "mavi / soğuk", strength
    if gn > rn and gn > bn:
        return "yeşil (magenta karşıtı)", strength
    return "karma", strength


def _dominant_colors(pil_img: Image.Image, n: int = 6) -> list[str]:
    """PIL quantize ile n baskın renk."""
    try:
        small = pil_img.convert("RGB").resize((150, 150), Image.LANCZOS)
        q = small.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()
        return [
            f"#{pal[i*3]:02x}{pal[i*3+1]:02x}{pal[i*3+2]:02x}"
            for i in range(n)
        ]
    except Exception:
        return []


def _saturation(pil_img: Image.Image) -> float:
    """HSV S kanalının ortalaması → 0-100."""
    try:
        hsv = np.array(pil_img.convert("HSV"), dtype=np.float32)
        return round(float(hsv[:, :, 1].mean() / 255 * 100), 1)
    except Exception:
        arr = np.array(pil_img.convert("RGB"), dtype=np.float32)
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        return round(float(np.std([r.mean(), g.mean(), b.mean()]) / 128 * 100), 1)


# ── Public API ───────────────────────────────────────────────

def analyze_color(pil_img: Image.Image) -> dict:
    """
    Returns:
        temperature_k / temperature_label
        cast / cast_strength
        dominant_colors     — list of hex strings
        saturation          — 0-100
        grey_world_deviation
        channel_means       — {r, g, b}
    """
    arr = np.array(pil_img.convert("RGB"), dtype=np.float32)
    r_m = float(arr[:, :, 0].mean())
    g_m = float(arr[:, :, 1].mean())
    b_m = float(arr[:, :, 2].mean())

    temp_k, temp_label = _estimate_temperature(r_m, g_m, b_m)
    cast, cast_strength = _detect_cast(r_m, g_m, b_m)
    sat = _saturation(pil_img)
    dom = _dominant_colors(pil_img)
    grey_dev = round(float(np.std([r_m, g_m, b_m])), 1)

    return {
        "temperature_k":       temp_k,
        "temperature_label":   temp_label,
        "cast":                cast,
        "cast_strength":       cast_strength,
        "dominant_colors":     dom,
        "saturation":          sat,
        "grey_world_deviation": grey_dev,
        "channel_means":       {
            "r": round(r_m, 1),
            "g": round(g_m, 1),
            "b": round(b_m, 1),
        },
    }
