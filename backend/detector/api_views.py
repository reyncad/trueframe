"""
TrueFrame API görünümleri.

Endpointler:
  POST /api/analyze            — görsel analizi (tespit + kalite)
  GET  /api/history            — geçmiş analiz listesi
  GET  /api/history/<id>       — tekil analiz detayı

Güvenlik önlemleri:
  - MIME sniffing: python-magic ile gerçek tip doğrulaması
  - API key header: X-TrueFrame-Key (iç ağ servisi doğrulaması)
  - Boyut limiti: 5 MB
  - csrf_exempt: yalnızca iç ağ (backend container) üzerinden erişildiğinden güvenli
"""

import logging
import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from PIL import Image

logger = logging.getLogger(__name__)

# ── Yol ayarları ─────────────────────────────────────────────
_nisa_path = str(Path(__file__).resolve().parents[1] / "apps")
if _nisa_path not in sys.path:
    sys.path.insert(0, _nisa_path)

import importlib.util
_nc_path = Path(__file__).resolve().parents[1] / "apps" / "nisa_core"
if "core" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "core", _nc_path / "__init__.py",
        submodule_search_locations=[str(_nc_path)]
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["core"] = _mod
    _spec.loader.exec_module(_mod)

# ── Singleton servisler ───────────────────────────────────────
from apps.detection.services import DetectionService
_service = DetectionService()

# ── Warmup senkronizasyonu ────────────────────────────────────
# apps.py'deki background thread warmup tamamlandığında bu event'i set eder.
# analyze endpoint ilk istekte 60s'ye kadar bekler; bu sürede warmup bitmezse
# lazy load devreye girer (normal davranış).
import threading as _threading
warmup_done = _threading.Event()

try:
    from core.analyzer import compute_fast_bundle, finalize_analysis
    from core.metrics.iqa import run_iqa_metrics
    from core.config import IQA_METRICS
    _quality_available = True
except Exception as _qe:
    logger.warning("Kalite modülleri yüklenemedi: %s", _qe)
    _quality_available = False

try:
    from core.db import init_db, save_analysis, get_history, get_analysis
    init_db()
    _db_available = True
except Exception as _de:
    logger.warning("Veritabanı modülü yüklenemedi: %s", _de)
    _db_available = False

# ── MIME doğrulama ────────────────────────────────────────────
try:
    import magic
    _magic_available = True
except ImportError:
    logger.warning("python-magic kurulu değil; MIME doğrulaması header tabanlı çalışacak.")
    _magic_available = False

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/bmp",
}
# clip_iqa pyiqa'nın mevcut sürümünde desteklenmiyor; config'den dinamik oku
ALL_METRICS = ["musiq", "topiq_nr", "hyperiqa", "dbcnn", "paq2piq", "brisque", "niqe"]


# ── Yardımcılar ───────────────────────────────────────────────

def _safe(val, default=None):
    """None veya NaN değerleri temizler."""
    try:
        if val is None or (isinstance(val, float) and (val != val)):
            return default
        return val
    except Exception:
        return default


def _verify_api_key(request) -> bool:
    """
    İç ağ API key doğrulaması.
    TRUEFRAME_API_KEY boşsa doğrulama atlanır (geliştirme modu).
    """
    expected = getattr(settings, "TRUEFRAME_API_KEY", "")
    if not expected:
        return True   # Geliştirme: key tanımlanmamışsa atla
    provided = request.headers.get("X-TrueFrame-Key", "")
    return provided == expected


def _verify_mime(raw: bytes, content_type: str) -> bool:
    """
    Gerçek MIME tipini ilk 2048 byte inceleyerek doğrular.
    python-magic kurulu değilse header'a güvenir.
    """
    if _magic_available:
        real_type = magic.from_buffer(raw[:2048], mime=True)
        return real_type in ALLOWED_CONTENT_TYPES
    return content_type in ALLOWED_CONTENT_TYPES


VALID_PROFILES = {"none", "web", "social", "print", "news"}

def _run_quality(img: Image.Image, image_path: str, name: str, profile: str = "none") -> dict:
    if not _quality_available:
        return {}
    if profile not in VALID_PROFILES:
        profile = "none"
    try:
        bundle = compute_fast_bundle(img)
        iqa    = run_iqa_metrics(image_path, ALL_METRICS)
        result = finalize_analysis(bundle, iqa, name, profile)

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

        checks = []
        for c in profile_r.get("checks", []):
            checks.append({
                "name":   c.get("name"),
                "passed": c.get("passed"),
                "value":  c.get("display") or c.get("value"),
                "needed": c.get("threshold_display") or c.get("threshold"),
            })

        tilt = geometry.get("tilt", {})

        return {
            "quality_score": _safe(result.get("overall"), 0),
            "verdict":       result.get("verdict", ""),
            "profile_label": profile_r.get("profile_label", ""),  # FIX: was "label"
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
                "label":          histogram.get("exposure_label", ""),          # FIX: fast→histogram
                "highlight_clip": _safe(histogram.get("highlight_clip_pct"), 0),
                "shadow_clip":    _safe(histogram.get("shadow_clip_pct"), 0),
                "dynamic_range":  _safe(histogram.get("dynamic_range_score"), 0), # FIX: fast→histogram
                "avg_brightness": _safe(fast.get("brightness"), 0),             # FIX: avg_brightness→brightness
            },
            "color": {
                "cast":        color.get("cast", ""),
                "temperature": _safe(color.get("temperature_k")),
                "tint":        _safe(color.get("tint")),
                "saturation":  _safe(color.get("saturation")),
                "noise":       color.get("noise_label", ""),
            },
            "geometry": {
                "blur_type":        blur_type.get("type", ""),
                "blur_label":       blur_type.get("description", ""),
                "tilt_angle":       _safe(tilt.get("angle")),
                "tilt_label":       tilt.get("label", ""),
                "tilt_confidence":  _safe(tilt.get("confidence")),
                "moire_score":      _safe(geometry.get("moire", {}).get("score"), 0),
                "moire_label":      geometry.get("moire", {}).get("label", "Yok"),
            },
            "iqa_metrics": iqa_table,
            "checks":      checks,
        }
    except Exception as e:
        logger.exception("Kalite analizi hatası")
        return {"error": str(e)}


# ── Endpointler ───────────────────────────────────────────────

@csrf_exempt
@require_POST
def analyze(request):
    """
    POST /api/analyze
    Kabul: multipart/form-data, 'image' alanı
    Yanıt: JSON (tespit + kalite)
    """
    # Warmup bitmeden istek işleme — modeller yüklenirken gelen ilk istek OOM'a yol açabilir.
    # 60 saniye bekle; süre aşılırsa lazy load devreye girer (normal davranış).
    if not warmup_done.is_set():
        warmup_done.wait(timeout=60)

    if not _verify_api_key(request):
        return JsonResponse({"error": "Yetkisiz istek."}, status=401)

    image_file = request.FILES.get("image")
    if not image_file:
        return JsonResponse({"error": "Görsel bulunamadı."}, status=400)

    if image_file.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Dosya 5 MB'dan büyük olamaz."}, status=400)

    raw = image_file.read()

    # MIME sniffing — gerçek tip doğrulaması (header manipülasyonuna karşı)
    if not _verify_mime(raw, image_file.content_type):
        return JsonResponse(
            {"error": "Desteklenmeyen veya geçersiz dosya formatı. JPG, PNG veya WEBP gönderin."},
            status=400
        )

    try:
        img = Image.open(BytesIO(raw))
        detection = _service.predict_pil(img)
    except Exception as e:
        logger.exception("AI tespit hatası")
        return JsonResponse({"error": f"Analiz sırasında hata oluştu: {e}"}, status=500)

    quality = {}
    ext = os.path.splitext(image_file.name)[1] or ".jpg"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        profile = request.POST.get("profile", "none")
        quality = _run_quality(img, tmp_path, image_file.name, profile)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    response_data = {**detection, "quality": quality}

    # Geçmişe kaydet (hata olsa da yanıt dönmeye devam et)
    if _db_available:
        try:
            _save_to_history(response_data, img, image_file.name, profile)
        except Exception as e:
            logger.warning("Geçmiş kaydedilemedi: %s", e)

    return JsonResponse(response_data)


def _save_to_history(api_response: dict, img: Image.Image, name: str, profile: str = "none"):
    """API yanıtını thumbnail ile birlikte veritabanına kaydeder."""
    import json
    quality = api_response.get("quality", {})
    result = {
        "name":        name,
        "profile":     profile,  # FIX: hardcoded "social" yerine gerçek profil
        "overall":     quality.get("quality_score"),
        "verdict":     quality.get("verdict", ""),
        # Tüm API yanıtı — Details sayfası için
        "api_response": json.dumps(api_response, ensure_ascii=False),
        # Detection fields
        "label":       api_response.get("label", ""),
        "fake_prob":   api_response.get("fake_prob", 0),
        "real_prob":   api_response.get("real_prob", 0),
    }
    save_analysis(result, img)


@csrf_exempt
@require_GET
def history_list(request):
    """
    GET /api/history
    Yanıt: Son 30 analiz kaydının özet listesi
    """
    if not _verify_api_key(request):
        return JsonResponse({"error": "Yetkisiz istek."}, status=401)

    if not _db_available:
        return JsonResponse({"items": [], "warning": "Veritabanı kullanılamıyor."})

    try:
        items = get_history(limit=30)
        return JsonResponse({"items": items})
    except Exception as e:
        logger.exception("Geçmiş listesi hatası")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_GET
def history_detail(request, analysis_id: int):
    """
    GET /api/history/<id>
    Yanıt: Tekil analiz kaydının tam detayı
    """
    if not _verify_api_key(request):
        return JsonResponse({"error": "Yetkisiz istek."}, status=401)

    if not _db_available:
        return JsonResponse({"error": "Veritabanı kullanılamıyor."}, status=503)

    try:
        record = get_analysis(analysis_id)
        if record is None:
            return JsonResponse({"error": "Kayıt bulunamadı."}, status=404)
        return JsonResponse(record)
    except Exception as e:
        logger.exception("Analiz detay hatası")
        return JsonResponse({"error": str(e)}, status=500)
