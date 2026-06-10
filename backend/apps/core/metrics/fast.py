"""
Hızlı, ML gerektirmeyen görüntü kalitesi göstergeleri.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter, ImageStat
from scipy.signal import convolve2d

_LAP_KERNEL = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)


def compute_fast_metrics(pil_img: Image.Image) -> dict:
    """
    Returns:
        sharpness_lap   — Laplacian varyansı (yüksek = keskin)
        noise_est       — Gauss farkı std (yüksek = gürültülü)
        colour_richness — RGB std ortalaması
        brightness      — normalize ortalama parlaklık [0-1]
        contrast_rms    — RMS kontrast
    """
    gray = np.array(pil_img.convert("L"), dtype=np.float32)

    # Keskinlik: Laplacian varyansı
    lap = convolve2d(gray, _LAP_KERNEL, mode="valid")
    sharpness = float(lap.var())

    # Gürültü: blurred-original farkının std
    blurred = np.array(
        pil_img.convert("L").filter(ImageFilter.GaussianBlur(2)),
        dtype=np.float32,
    )
    noise = float(np.abs(gray - blurred).std())

    # Renk zenginliği
    stat = ImageStat.Stat(pil_img.convert("RGB"))
    colour_richness = float(np.mean(stat.stddev))

    # Parlaklık
    brightness = float(gray.mean() / 255.0)

    # Kontrast (RMS)
    contrast_rms = float(np.sqrt(np.mean((gray - gray.mean()) ** 2)))

    return {
        "sharpness_lap":   round(sharpness, 2),
        "noise_est":       round(noise, 2),
        "colour_richness": round(colour_richness, 2),
        "brightness":      round(brightness, 4),
        "contrast_rms":    round(contrast_rms, 2),
    }
