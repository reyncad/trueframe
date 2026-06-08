import sys
import tempfile
import os
from io import BytesIO
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from PIL import Image

from apps.detection.services import DetectionService

_nisa_path = str(Path(__file__).resolve().parents[1] / "apps")
if _nisa_path not in sys.path:
    sys.path.insert(0, _nisa_path)

import importlib.util, types
_nc_path = Path(__file__).resolve().parents[1] / "apps" / "nisa_core"
if "core" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "core", _nc_path / "__init__.py",
        submodule_search_locations=[str(_nc_path)]
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["core"] = _mod
    _spec.loader.exec_module(_mod)

_service = DetectionService()

try:
    from core.analyzer import compute_fast_bundle, finalize_analysis
    from core.metrics.iqa import run_iqa_metrics
    from core.config import IQA_METRICS
    _quality_available = True
except Exception as _qe:
    _quality_available = False

ALL_METRICS = ["musiq", "topiq_nr", "hyperiqa", "dbcnn", "paq2piq", "clip_iqa", "brisque", "niqe"]


def _safe(val, default=None):
    try:
        if val is None or (isinstance(val, float) and (val != val)):
            return default
        return val
    except Exception:
        return default


def _run_quality(img: Image.Image, image_path: str, name: str) -> dict:
    if not _quality_available:
        return {}
    try:
        bundle = compute_fast_bundle(img)
        iqa    = run_iqa_metrics(image_path, ALL_METRICS)
        result = finalize_analysis(bundle, iqa, name, "social")

        technical = result.get("technical", {})
        exif      = result.get("exif", {})
        fast      = result.get("fast", {})
        histogram = result.get("histogram", {})
        color     = result.get("color", {})
        geometry  = result.get("geometry", {})
        blur_type = result.get("blur_type", {})
        profile_r = result.get("profile_result", {})
        dims      = result.get("dimensions", {})
        iqa_out   = result.get("iqa_metrics", {})

        # IQA metrik tablosu
        iqa_table = []
        for key, meta in IQA_METRICS.items():
            entry = iqa_out.get(key, {})
            if not isinstance(entry, dict):
                continue
            score = entry.get("score")
            iqa_table.append({
                "label":     meta["label"],
                "score":     _safe(score),
                "direction": meta["direction"],
                "good_min":  meta["good_range"][0],
                "good_max":  meta["good_range"][1],
                "error":     entry.get("error"),
            })

        # Profil kontrol listesi
        checks = []
        for c in profile_r.get("checks", []):
            checks.append({
                "name":    c.get("name"),
                "passed":  c.get("passed"),
                "value":   c.get("display"),
                "needed":  c.get("threshold_display"),
            })

        tilt = geometry.get("tilt", {})

        return {
            "quality_score": _safe(result.get("overall"), 0),
            "verdict":       result.get("verdict", ""),
            "profile_label": profile_r.get("label", ""),
            "profile_pass":  profile_r.get("passed", 0),
            "profile_total": profile_r.get("total", 0),
            "dimensions": {
                "keskinlik": _safe(dims.get("keskinlik"), 0),
                "gurultu":   _safe(dims.get("gurultu"), 0),
                "pozlama":   _safe(dims.get("pozlama"), 0),
                "renk":      _safe(dims.get("renk"), 0),
                "estetik":   _safe(dims.get("estetik"), 0),
                "teknik":    _safe(dims.get("teknik"), 0),
            },
            "technical": {
                "width":      _safe(technical.get("width")),
                "height":     _safe(technical.get("height")),
                "megapixels": _safe(technical.get("megapixels")),
                "format":     technical.get("format", ""),
                "color_mode": technical.get("color_mode", ""),
                "dpi":        _safe(technical.get("dpi_x")),
            },
            "exif": {
                "datetime": exif.get("datetime_str", exif.get("datetime")),
            },
            "exposure": {
                "label":          fast.get("exposure_label", ""),
                "highlight_clip": _safe(histogram.get("highlight_clip_pct"), 0),
                "shadow_clip":    _safe(histogram.get("shadow_clip_pct"), 0),
                "dynamic_range":  _safe(fast.get("dynamic_range"), 0),
                "avg_brightness": _safe(fast.get("avg_brightness"), 0),
            },
            "color": {
                "cast":        color.get("cast", ""),
                "temperature": _safe(color.get("temperature_k")),
                "tint":        _safe(color.get("tint")),
                "saturation":  _safe(color.get("saturation")),
                "noise":       color.get("noise_label", ""),
            },
            "geometry": {
                "blur_type":   blur_type.get("type", ""),
                "blur_label":  blur_type.get("description", ""),
                "tilt_angle":  _safe(tilt.get("angle")),
                "tilt_label":  tilt.get("label", ""),
                "tilt_confidence": _safe(tilt.get("confidence")),
                "moire_score": _safe(geometry.get("moire", {}).get("score"), 0),
                "moire_label": geometry.get("moire", {}).get("label", "Yok"),
            },
            "iqa_metrics": iqa_table,
            "checks":      checks,
        }
    except Exception as e:
        return {"error": str(e)}


@csrf_exempt
@require_POST
def analyze(request):
    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"error": "Görsel bulunamadı."}, status=400)

    allowed = {"image/jpeg", "image/png", "image/webp"}
    if image_file.content_type not in allowed:
        return JsonResponse({"error": "Desteklenmeyen format. JPG, PNG veya WEBP gönderin."}, status=400)

    if image_file.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Dosya 5 MB'dan büyük olamaz."}, status=400)

    raw = image_file.read()
    try:
        img = Image.open(BytesIO(raw))
        detection = _service.predict_pil(img)
    except Exception as e:
        return JsonResponse({"error": f"Analiz sırasında hata oluştu: {e}"}, status=500)

    quality = {}
    ext = os.path.splitext(image_file.name)[1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(raw)
        tmp_path = tmp.name
    try:
        quality = _run_quality(img, tmp_path, image_file.name)
    finally:
        os.unlink(tmp_path)

    return JsonResponse({**detection, "quality": quality})
