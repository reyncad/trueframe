"""
Luma vs kroma gürültü ayrımı.

Motivasyon: Standart gürültü tahmini (Gauss farkı std) tüm gürültüyü toplar.
  - Luma gürültüsü (luminans): İnce taneler, göze hoş, kabul edilebilir
  - Kroma gürültüsü (renk): Çirkin mor/yeşil blotch'lar, her zaman sorun

Yöntem:
  1. LAB renk uzayına çevir (HSV ile yaklaşık)
  2. Koyu bölgelerde (düşük L) A ve B kanallarının varyansını ölç
  3. Kroma gürültüsü / toplam gürültü oranı = chroma_noise_ratio
  4. Yüksek kroma oranı + düşük luminans = color noise (ISO gürültüsü işareti)
"""

from __future__ import annotations

import numpy as np
from PIL import Image

_DARK_THRESH = 80    # V < bu değer → "koyu bölge"
_SAMPLE_SIZE = 512   # işlem boyutu


def analyze_color_noise(pil_img: Image.Image) -> dict:
    """
    Returns:
        luma_noise        — luminans gürültüsü tahmini (0-∞, düşük=iyi)
        chroma_noise      — renk gürültüsü tahmini (0-∞, düşük=iyi)
        chroma_noise_ratio — kroma/toplam oranı [0-1], yüksek = problem
        severity          — 'yok' | 'hafif' | 'orta' | 'ciddi'
        description       — Türkçe açıklama
    """
    small = pil_img.convert("RGB").resize((_SAMPLE_SIZE, _SAMPLE_SIZE), Image.LANCZOS)
    arr   = np.array(small, dtype=np.float32)

    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Luma (Rec.709 ağırlıklı)
    Y = 0.2126 * R + 0.7152 * G + 0.0722 * B

    # Cb, Cr (basit YCbCr dönüşümü)
    Cb =  -0.1687 * R - 0.3313 * G + 0.5000 * B + 128
    Cr =   0.5000 * R - 0.4187 * G - 0.0813 * B + 128

    # Koyu piksel maskesi (gürültü koyu alanda daha belirgin)
    dark_mask = Y < _DARK_THRESH

    if dark_mask.sum() < 200:
        # Yeterli koyu piksel yok
        return _result(0.0, 0.0, "yok")

    # Lokal varyans hesabı (3×3 pencere farkı)
    from scipy.ndimage import uniform_filter
    Y_mean  = uniform_filter(Y,  3)
    Cb_mean = uniform_filter(Cb, 3)
    Cr_mean = uniform_filter(Cr, 3)

    y_noise  = float(np.abs(Y  - Y_mean )[dark_mask].std())
    cb_noise = float(np.abs(Cb - Cb_mean)[dark_mask].std())
    cr_noise = float(np.abs(Cr - Cr_mean)[dark_mask].std())

    chroma_noise = (cb_noise + cr_noise) / 2
    total_noise  = max(y_noise + chroma_noise, 1e-6)
    ratio        = chroma_noise / total_noise

    return _result(y_noise, chroma_noise, _severity(chroma_noise, ratio))


def _severity(chroma: float, ratio: float) -> str:
    if chroma < 2 and ratio < 0.35:  return "yok"
    if chroma < 5 and ratio < 0.55:  return "hafif"
    if chroma < 10 and ratio < 0.70: return "orta"
    return "ciddi"


def _result(luma: float, chroma: float, sev: str) -> dict:
    total = luma + chroma
    ratio = chroma / max(total, 1e-6)
    desc_map = {
        "yok":   "Renk gürültüsü yok veya ihmal edilebilir düzeyde.",
        "hafif": "Hafif kroma gürültüsü — düşük ışık çekimlerinde beklenen.",
        "orta":  "Belirgin renk gürültüsü — noise reduction önerilir.",
        "ciddi": "Ciddi kroma gürültüsü (ISO çok yüksek veya sensör sınırı) — yeniden çekim veya güçlü NR.",
    }
    return {
        "luma_noise":          round(luma, 2),
        "chroma_noise":        round(chroma, 2),
        "chroma_noise_ratio":  round(ratio, 3),
        "severity":            sev,
        "description":         desc_map[sev],
    }
