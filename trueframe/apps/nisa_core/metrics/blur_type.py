"""
Blur tipi tespiti — yapısal tensör analizi.

Hareket bulanıklığı (motion blur) vs odak kayması (defocus blur) ayrımı.

Motivasyon: Her ikisi de düşük Laplacian varyansı verir ama çok farklı sorunlardır.
  - Motion blur: yüksek coherence (gradyanlar tek yöne hizalı), yönlü PSF
  - Defocus:     düşük coherence (izotropik), düşük edge strength
  - Sharp:       edge strength yüksek, coherence değişken

Yöntem: Structure tensor J = [ Jxx Jxy; Jxy Jyy ]
  Jxx = E[Ix²],  Jxy = E[IxIy],  Jyy = E[Iy²]
  Özdeğerler λ₁ ≥ λ₂
  Coherence C = (λ₁-λ₂)² / (λ₁+λ₂+ε)²

  C yüksek → directional edges → motion blur
  C düşük + edge_strength düşük → defocus
  C düşük + edge_strength yüksek → sharp (multi-directional content)
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

_PROCESS_SIZE   = (512, 512)   # işlem boyutu
_SMOOTH_SIGMA   = 2.5          # yapısal tensör yumuşatma
_EDGE_SHARP_THR = 8.0          # bu üzerinde edge_strength "keskin" sayılır
_COHERENCE_THR  = 0.35         # bu üzerinde "yönlü" = motion blur
_DEFOCUS_EDGE   = 3.0          # bu altında edge_strength + düşük coherence = defocus


def detect_blur_type(pil_img: Image.Image) -> dict:
    """
    Returns:
        type            — 'sharp' | 'motion' | 'defocus' | 'unknown'
        coherence       — yapısal tutarlılık skoru [0-1]
        edge_strength   — ortalama kenar gücü
        motion_angle    — tahmini hareket yönü (sadece motion için, derece)
        label           — Türkçe etiket
        description     — Türkçe açıklama
    """
    gray = np.array(
        pil_img.convert("L").resize(_PROCESS_SIZE, Image.LANCZOS),
        dtype=np.float32,
    )

    Ix = ndimage.sobel(gray, axis=1).astype(np.float32)
    Iy = ndimage.sobel(gray, axis=0).astype(np.float32)

    # Yapısal tensör elemanları — Gaussian ile yumuşat
    Jxx = ndimage.gaussian_filter(Ix * Ix, _SMOOTH_SIGMA)
    Jxy = ndimage.gaussian_filter(Ix * Iy, _SMOOTH_SIGMA)
    Jyy = ndimage.gaussian_filter(Iy * Iy, _SMOOTH_SIGMA)

    # Özdeğerler
    trace        = Jxx + Jyy
    discriminant = np.clip((Jxx - Jyy) ** 2 + 4 * Jxy ** 2, 0, None)
    sqrt_d       = np.sqrt(discriminant)
    lam1 = (trace + sqrt_d) / 2
    lam2 = (trace - sqrt_d) / 2

    # Coherence: yüksek → tek yönlü kenarlar (motion blur)
    denom     = (lam1 + lam2 + 1e-6) ** 2
    coherence = float(np.mean((lam1 - lam2) ** 2 / denom))

    # Edge strength: kenar gücünün ortalaması
    edge_strength = float(np.sqrt(Jxx + Jyy).mean())

    # Hareket yönü (sadece motion için anlamlı)
    motion_angle: float | None = None
    if coherence > _COHERENCE_THR:
        # Baskın kenar yönü: Jxy/Jxx'ten açı hesapla
        avg_jxx = float(Jxx.mean())
        avg_jxy = float(Jxy.mean())
        if abs(avg_jxx) > 1e-6:
            motion_angle = round(float(np.degrees(np.arctan2(avg_jxy, avg_jxx))), 1)

    # Sınıflandırma
    blur_type, label, description = _classify(coherence, edge_strength, motion_angle)

    return {
        "type":          blur_type,
        "coherence":     round(coherence, 3),
        "edge_strength": round(edge_strength, 2),
        "motion_angle":  motion_angle,
        "label":         label,
        "description":   description,
    }


def _classify(
    coherence: float,
    edge_strength: float,
    motion_angle: float | None,
) -> tuple[str, str, str]:
    if edge_strength >= _EDGE_SHARP_THR:
        return ("sharp", "Keskin", "Görsel genel olarak keskin.")

    if coherence >= _COHERENCE_THR and edge_strength >= _DEFOCUS_EDGE:
        angle_str = f" ({motion_angle:+.0f}°)" if motion_angle is not None else ""
        return (
            "motion",
            "Hareket Bulanıklığı",
            f"Yönlü hareket bulanıklığı saptandı{angle_str} — "
            "tripod kullanın veya enstantane hızını artırın.",
        )

    if edge_strength < _DEFOCUS_EDGE:
        return (
            "defocus",
            "Odak Kayması",
            "Genel, izotropik bulanıklık — odak kayması veya çok düşük enstantane. "
            "AF kilidi kontrol edin veya diyaframı kısın.",
        )

    return ("unknown", "Belirsiz", "Bulanıklık tipi belirlenemedi.")
