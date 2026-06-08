"""
Geometrik analiz — horizon eğikliği ve moire pattern tespiti.

Eğiklik: Sobel gradyan açı histogramı. Yalnızca yeterli güvenle raporlanır
         (düşük confidence → 'bilinmiyor' döner, yanlış alarm yerine).

Moire:   FFT magnitude spectrum'da orta frekanslardaki periyodik pikler.
         Daha muhafazakâr eşikler: doğal doku false positive azaltıldı.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

from core.config import MOIRE_FAIL_SCORE, MOIRE_WARN_SCORE, TILT_FAIL_DEG, TILT_WARN_DEG

_ANALYSIS_SIZE   = (512, 512)
_EDGE_PERCENTILE = 90    # güçlü kenar eşiği (üst %10 → daha az gürültü)
_HORIZ_BAND_DEG  = 15    # yatay band ±15°
_MIN_HORIZ_PX    = 100   # güvenilir tahmin için minimum yatay kenar sayısı
_MIN_CONFIDENCE  = 0.22  # bu altında tilt raporlanmaz
_MIN_HORIZ_RATIO = 0.18  # yatay kenar / toplam güçlü kenar — bu altında organik/dağınık sahne
_MIN_PEAK_RATIO  = 1.5   # histogram tepe bini, komşu ortalamadan bu kat daha yüksek olmalı


class _TiltResult:
    __slots__ = ("angle", "abs_angle", "is_tilted", "severity", "label", "confidence")

    def __init__(self, angle, abs_angle, is_tilted, severity, label, confidence):
        self.angle      = angle
        self.abs_angle  = abs_angle
        self.is_tilted  = is_tilted
        self.severity   = severity
        self.label      = label
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


# ── Eğiklik tespiti ──────────────────────────────────────────

def detect_tilt(pil_img: Image.Image) -> dict:
    """
    Baskın yatay kenar açısından horizon tilt tahmini.
    Confidence düşükse (diagonal ağırlıklı sahne) 'unknown' döner.
    """
    small = pil_img.convert("L").resize(_ANALYSIS_SIZE, Image.LANCZOS)
    gray  = np.array(small, dtype=np.float32)

    sx = ndimage.sobel(gray, axis=1).astype(np.float32)
    sy = ndimage.sobel(gray, axis=0).astype(np.float32)
    mag = np.sqrt(sx ** 2 + sy ** 2)

    thresh = np.percentile(mag, _EDGE_PERCENTILE)
    strong = mag > thresh

    if strong.sum() < 50:
        return _tilt_result(0.0, 0.0)

    # Açılar [-90, 90) bandına
    angles  = np.degrees(np.arctan2(sy[strong], sx[strong]))
    angles  = ((angles + 90) % 180) - 90

    # Yatay band: baskın ufuk/yatay kenar açıları
    horiz_mask  = np.abs(angles) < _HORIZ_BAND_DEG
    horiz_count = int(horiz_mask.sum())
    total_count = int(strong.sum())

    # Yatay baskınlık oranı: organik/doğal sahnelerde düşük olur (ağaç dalları vb.)
    horiz_ratio = horiz_count / max(total_count, 1)

    # Temel confidence: yatay kenar sayısına göre
    confidence = min(1.0, horiz_count / 800)

    # Yatay baskınlık düşükse confidence'ı orantılı olarak cezalandır
    if horiz_ratio < _MIN_HORIZ_RATIO:
        confidence *= horiz_ratio / _MIN_HORIZ_RATIO

    if horiz_count < _MIN_HORIZ_PX or confidence < _MIN_CONFIDENCE:
        return _tilt_result(0.0, confidence)   # yetersiz bilgi, tahmin yok

    horiz_angles = angles[horiz_mask]
    hist, bins   = np.histogram(horiz_angles, bins=30, range=(-_HORIZ_BAND_DEG, _HORIZ_BAND_DEG))
    peak_bin     = int(np.argmax(hist))

    # Peak keskinliği: tepe bini komşu ortalamasından belirgin şekilde yüksek olmalı
    neighbors = []
    if peak_bin > 0:       neighbors.append(hist[peak_bin - 1])
    if peak_bin < len(hist) - 1: neighbors.append(hist[peak_bin + 1])
    neighbor_mean = float(np.mean(neighbors)) if neighbors else 0.0
    peak_ratio = hist[peak_bin] / max(neighbor_mean, 1.0)

    if peak_ratio < _MIN_PEAK_RATIO:
        # Histogram düz → açı dağınık → güven yarıya düşür
        confidence *= 0.5

    if confidence < _MIN_CONFIDENCE:
        return _tilt_result(0.0, confidence)

    tilt_angle = float((bins[peak_bin] + bins[peak_bin + 1]) / 2)
    return _tilt_result(tilt_angle, confidence)


def _tilt_result(angle: float, confidence: float) -> dict:
    abs_a = abs(angle)

    if confidence < _MIN_CONFIDENCE:
        return {
            "angle": 0.0, "abs_angle": 0.0, "is_tilted": False,
            "severity": "Bilinmiyor", "label": "—",
            "confidence": round(confidence, 2),
        }

    if abs_a >= TILT_FAIL_DEG:
        severity, is_tilted = "Ciddi", True
    elif abs_a >= TILT_WARN_DEG:
        severity, is_tilted = "Hafif", True
    else:
        severity, is_tilted = "Yok", False

    return {
        "angle":      round(angle, 1),
        "abs_angle":  round(abs_a, 1),
        "is_tilted":  is_tilted,
        "severity":   severity,
        "label":      f"{angle:+.1f}°" if abs_a > 0.3 else "0°",
        "confidence": round(confidence, 2),
    }


# ── Moire tespiti ────────────────────────────────────────────
#
# Daha muhafazakâr yaklaşım:
#   - Merkez + çok yüksek frekans maskesi (doğal doku bu frekanslarda güçlü)
#   - Yalnızca ORTA frekans bandında güçlü pik aranır
#   - Normalize: görsel piksel sayısına göre düzeltilmiş

_FFT_SIZE    = 512
_CENTER_R    = 30    # merkez eksklüzyon yarıçapı (px)
_OUTER_R     = 200   # dış frekans maskesi (doğal doku = yüksek frekans, dışarıda)
_PEAK_THR    = 0.78  # normalize magnitude eşiği (0.72'den → 0.78, daha muhafazakâr)


def detect_moire(pil_img: Image.Image) -> dict:
    """
    FFT magnitude spectrum'un orta frekans bandında periyodik pik yoğunluğu.

    Returns:
        score       — 0-100 (yüksek = moire riski)
        detected    — MOIRE_WARN_SCORE üzerinde True
        severity    — 'Yüksek' | 'Orta' | 'Yok'
        peak_count  — güçlü pik sayısı (orta frekans bandı)
    """
    gray = np.array(
        pil_img.convert("L").resize((_FFT_SIZE, _FFT_SIZE), Image.LANCZOS),
        dtype=np.float32,
    )

    fft_sh  = np.fft.fftshift(np.fft.fft2(gray))
    mag     = np.log1p(np.abs(fft_sh))
    mag_max = mag.max()

    if mag_max < 1e-6:
        return _moire_result(0, 0)

    mag_norm = mag / mag_max

    # Yalnızca orta frekans halkası: [CENTER_R, OUTER_R]
    h, w   = mag_norm.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    dist   = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    band   = (dist > _CENTER_R) & (dist < _OUTER_R)

    outer_band = mag_norm * band
    peak_count = int((outer_band > _PEAK_THR).sum())

    # Normalize: daha büyük orta frekans bandı → daha fazla beklenen pik
    band_area = max(float(band.sum()), 1.0)
    score     = min(100.0, float(peak_count / band_area * 10_000 * 2.5))

    return _moire_result(score, peak_count)


def _moire_result(score: float, peak_count: int) -> dict:
    if score >= MOIRE_FAIL_SCORE:
        severity, detected = "Yüksek", True
    elif score >= MOIRE_WARN_SCORE:
        severity, detected = "Orta",   True
    else:
        severity, detected = "Yok",    False

    return {
        "score":      round(score, 1),
        "detected":   detected,
        "severity":   severity,
        "peak_count": peak_count,
    }


# ── Birleşik API ─────────────────────────────────────────────

def analyze_geometry(pil_img: Image.Image) -> dict:
    return {
        "tilt":  detect_tilt(pil_img),
        "moire": detect_moire(pil_img),
    }
