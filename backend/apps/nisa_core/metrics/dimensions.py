"""
6 boyutlu kalite radar skoru.

Tek sayılı "overall" yerine her boyut ayrı değerlendirilerek
daha bilgilendirici bir profil ortaya çıkar.

Boyutlar:
  keskinlik — Laplacian varyansı + blur tipi cezası
  gurultu   — noise_est (luma) + kroma gürültüsü cezası  [yüksek = az gürültü = iyi]
  pozlama   — dinamik aralık + kırpılma cezası
  renk      — cast gücü + doygunluk uyumu
  estetik   — MUSIQ + PAQ2PIQ + CLIP-IQA ML metrikleri
  teknik    — BRISQUE / NIQE / HyperIQA / DBCNN / TOPIQ / Laplacian
"""

from __future__ import annotations

import math

from core.config import IQA_METRICS
from core.metrics.iqa import quality_label


def compute_dimensions(
    fast:         dict,
    histogram:    dict,
    color:        dict,
    blur_type:    dict,
    color_noise:  dict,
    iqa_metrics:  dict,
) -> dict:
    """Her boyut 0-100 (yüksek = iyi)."""
    return {
        "keskinlik": _sharpness_dim(fast, blur_type),
        "gurultu":   _noise_dim(fast, color_noise),
        "pozlama":   _exposure_dim(histogram),
        "renk":      _color_dim(color),
        "estetik":   _aesthetic_dim(iqa_metrics),
        "teknik":    _technical_dim(iqa_metrics),
    }


# ── Keskinlik ────────────────────────────────────────────────
def _sharpness_dim(fast: dict, blur_type: dict) -> float:
    lap = max(fast.get("sharpness_lap", 0), 0)
    # Log ölçeği: 0→0, 100→40, 500→65, 2000→85, 5000→95, 10000→100
    raw = min(100.0, math.log1p(lap) / math.log1p(12000) * 100)

    btype = blur_type.get("type", "sharp")
    if btype == "motion":
        raw *= 0.55   # hareket bulanıklığı ciddi ceza
    elif btype == "defocus":
        raw *= 0.70   # odak kayması orta ceza

    return round(max(0.0, min(100.0, raw)), 1)


# ── Gürültü (yüksek = az gürültü = iyi) ─────────────────────
def _noise_dim(fast: dict, color_noise: dict) -> float:
    noise = fast.get("noise_est", 10)
    # noise_est: 0→100, 5→90, 15→70, 25→45, 40→10
    raw = max(0.0, 100 - noise * 2.8)

    # Kroma gürültüsü ek ceza
    cn_ratio = color_noise.get("chroma_noise_ratio", 0)
    sev = color_noise.get("severity", "yok")
    if sev == "ciddi":
        raw *= 0.60
    elif sev == "orta":
        raw *= 0.78
    elif sev == "hafif":
        raw *= 0.90

    return round(max(0.0, min(100.0, raw)), 1)


# ── Pozlama ──────────────────────────────────────────────────
def _exposure_dim(histogram: dict) -> float:
    dr  = histogram.get("dynamic_range_score", 50)   # 0-100
    hl  = histogram.get("highlight_clip_pct",  0)    # % blown highlights
    sh  = histogram.get("shadow_clip_pct",     0)    # % blown shadows

    raw = dr - hl * 4 - sh * 3
    return round(max(0.0, min(100.0, raw)), 1)


# ── Renk ─────────────────────────────────────────────────────
def _color_dim(color: dict) -> float:
    cast = color.get("cast_strength", 0)    # 0 = nötr, yüksek = sorunlu
    sat  = color.get("saturation",    50)   # 0-100

    # Cast cezası: 0→100, 0.15→78, 0.30→50, 0.50→15
    cast_penalty = min(100, cast * 200)
    raw = max(0.0, 100 - cast_penalty)

    # Doygunluk cezası
    if sat < 10:
        raw *= 0.60
    elif sat < 20:
        raw *= 0.80
    elif sat > 92:
        raw *= 0.85

    return round(max(0.0, min(100.0, raw)), 1)


# ── Estetik — ML metrikleri ───────────────────────────────────
_AESTHETIC_METRICS = {
    "musiq":    {"lo": 30.0, "hi": 90.0, "w": 2.0},
    "paq2piq":  {"lo": 30.0, "hi": 90.0, "w": 1.2},
    "clip_iqa": {"lo":  0.0, "hi":  1.0, "w": 1.3},
}

def _aesthetic_dim(iqa_metrics: dict) -> float:
    scores, weights = [], []
    for name, cfg in _AESTHETIC_METRICS.items():
        r = iqa_metrics.get(name, {})
        if r.get("status") != "ok":
            continue
        s = (r["score"] - cfg["lo"]) / max(cfg["hi"] - cfg["lo"], 1e-6) * 100
        scores.append(max(0.0, min(100.0, s)))
        weights.append(cfg["w"])

    if not scores:
        return 50.0
    return round(sum(s*w for s,w in zip(scores,weights)) / sum(weights), 1)


# ── Teknik IQA — ML metrikleri ────────────────────────────────
_TECHNICAL_METRICS = [
    "brisque", "niqe", "hyperiqa", "dbcnn", "topiq_nr"
]

def _technical_dim(iqa_metrics: dict) -> float:
    scores = []
    for name in _TECHNICAL_METRICS:
        r = iqa_metrics.get(name, {})
        if r.get("status") != "ok":
            continue
        meta = IQA_METRICS.get(name)
        if not meta:
            continue
        lbl = quality_label(r["score"], meta)
        scores.append({"iyi": 90, "orta": 55, "zayıf": 15}[lbl])

    if not scores:
        return 50.0
    return round(sum(scores) / len(scores), 1)
