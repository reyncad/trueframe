"""
Analiz orkestratörü.

Her modül tek sorumluluğa sahiptir; bu dosya sıralamayı ve birleştirmeyi yapar.
"""

from __future__ import annotations

from PIL import Image

from core.config import IQA_METRICS
from core.image_loader import cleanup_tmp, load_image
from core.metrics.blur_type import detect_blur_type
from core.metrics.color import analyze_color
from core.metrics.color_noise import analyze_color_noise
from core.metrics.dimensions import compute_dimensions
from core.metrics.exif import read_exif
from core.metrics.fast import compute_fast_metrics
from core.metrics.geometry import analyze_geometry
from core.metrics.highlight_map import compute_highlight_map
from core.metrics.histogram import analyze_histogram
from core.metrics.iqa import compute_overall, device_str, run_iqa_metrics
from core.metrics.sharpness_map import compute_sharpness_map
from core.profiles import evaluate
from core.verdict import generate_verdict


def compute_fast_bundle(pil: Image.Image) -> dict:
    """
    ML olmayan tüm analizleri hesaplar.
    SSE akışında ilk paket olarak gönderilir — model beklenmeden görünür.
    """
    exif         = read_exif(pil)
    fast         = compute_fast_metrics(pil)
    histogram    = analyze_histogram(pil)
    color        = analyze_color(pil)
    sharp_map    = compute_sharpness_map(pil)
    highlight_m  = compute_highlight_map(pil)
    blur_t       = detect_blur_type(pil)
    color_noise  = analyze_color_noise(pil)
    geometry     = analyze_geometry(pil)

    technical = {
        "width":      pil.width,
        "height":     pil.height,
        "megapixels": round(pil.width * pil.height / 1_000_000, 2),
        "format":     getattr(pil, "format", "JPEG") or "JPEG",
        "color_mode": pil.mode,
        "dpi_x":      exif.get("dpi_x"),
        "dpi_y":      exif.get("dpi_y"),
    }

    return {
        "technical":     technical,
        "exif":          exif,
        "fast":          fast,
        "histogram":     histogram,
        "color":         color,
        "sharpness_map": sharp_map,
        "highlight_map": highlight_m,
        "blur_type":     blur_t,
        "color_noise":   color_noise,
        "geometry":      geometry,
    }


def finalize_analysis(
    bundle:        dict,
    iqa_metrics:   dict,
    name:          str,
    profile_id:    str,
) -> dict:
    """Hızlı bundle + ML metrikleri → tam analiz sonucu."""
    overall = compute_overall(iqa_metrics)

    # Profil değerlendirmesi — geometry bilgisini de kullan
    profile_data   = {**bundle}
    profile_result = evaluate(profile_id, profile_data)

    # 6D radar skoru
    dimensions = compute_dimensions(
        fast        = bundle["fast"],
        histogram   = bundle["histogram"],
        color       = bundle["color"],
        blur_type   = bundle["blur_type"],
        color_noise = bundle["color_noise"],
        iqa_metrics = iqa_metrics,
    )

    verdict = generate_verdict(
        overall        = overall,
        profile_result = profile_result,
        fast           = bundle["fast"],
        histogram      = bundle["histogram"],
        color          = bundle["color"],
        exif           = bundle["exif"],
        iqa_metrics    = iqa_metrics,
        geometry       = bundle["geometry"],
        sharpness_map  = bundle["sharpness_map"],
        blur_type      = bundle["blur_type"],
        color_noise    = bundle["color_noise"],
    )

    return {
        "status":         "ok",
        "name":           name,
        "profile":        profile_id,
        "overall":        overall,
        "verdict":        verdict,
        "profile_result": profile_result,
        "dimensions":     dimensions,
        **bundle,
        "iqa_metrics":    iqa_metrics,
        "metric_meta":    IQA_METRICS,
        "device":         device_str(),
    }


def analyze_image(
    source:           str,
    name:             str = "image",
    selected_metrics: list[str] | None = None,
    profile_id:       str = "none",
) -> dict:
    """Tam analiz — tek seferde tüm sonuçları döndürür (batch için)."""
    if selected_metrics is None:
        selected_metrics = list(IQA_METRICS.keys())

    try:
        pil, tmp_path = load_image(source)
    except Exception as e:
        return {"status": "error", "error": str(e), "name": name}

    try:
        bundle      = compute_fast_bundle(pil)
        eff_tmp     = tmp_path or source
        iqa_metrics = run_iqa_metrics(eff_tmp, selected_metrics)
        return finalize_analysis(bundle, iqa_metrics, name, profile_id)
    finally:
        cleanup_tmp(tmp_path)
