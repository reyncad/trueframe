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
_quality_path = str(Path(__file__).resolve().parents[1] / "apps")
if _quality_path not in sys.path:
    sys.path.insert(0, _quality_path)

import importlib.util
_nc_path = Path(__file__).resolve().parents[1] / "apps" / "core"
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


import hmac as _hmac

if not getattr(settings, "TRUEFRAME_API_KEY", ""):
    logger.warning(
        "TRUEFRAME_API_KEY tanımlı değil — API key doğrulaması ATLANIYOR. "
        "Bu yalnızca geliştirme ortamında kabul edilebilir."
    )


def _verify_api_key(request) -> bool:
    """
    İç ağ API key doğrulaması.
    TRUEFRAME_API_KEY boşsa doğrulama atlanır (geliştirme modu — startup'ta uyarı loglanır).
    Karşılaştırma timing-safe (hmac.compare_digest).
    """
    expected = getattr(settings, "TRUEFRAME_API_KEY", "")
    if not expected:
        return True   # Geliştirme: key tanımlanmamışsa atla
    provided = request.headers.get("X-TrueFrame-Key", "")
    return _hmac.compare_digest(provided.encode(), expected.encode())


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

        technical     = result.get("technical", {})
        exif          = result.get("exif", {})
        fast          = result.get("fast", {})
        histogram     = result.get("histogram", {})
        color         = result.get("color", {})
        geometry      = result.get("geometry", {})
        blur_type     = result.get("blur_type", {})
        color_noise   = result.get("color_noise", {})
        profile_r     = result.get("profile_result", {})
        dims          = result.get("dimensions", {})
        iqa_out       = result.get("iqa_metrics", {})
        # Bölgesel haritalar: finalize_analysis **bundle ile yayar, her zaman mevcuttur.
        sharpness_map = result.get("sharpness_map", {})
        highlight_map = result.get("highlight_map", {})

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
                "datetime":     exif.get("datetime_str", exif.get("datetime")),
                # FIX: EXIF detayları hesaplanıyordu ama API yanıtına hiç konmuyordu
                "camera":       exif.get("camera"),
                "lens":         exif.get("lens"),
                "iso":          _safe(exif.get("iso")),
                "aperture":     exif.get("aperture"),
                "shutter":      exif.get("shutter"),
                "focal_length": exif.get("focal_length"),
                "flash":        exif.get("flash"),
                "has_gps":      exif.get("has_gps"),
            },
            "exposure": {
                "label":          histogram.get("exposure_label", ""),          # FIX: fast→histogram
                "highlight_clip": _safe(histogram.get("highlight_clip_pct"), 0),
                "shadow_clip":    _safe(histogram.get("shadow_clip_pct"), 0),
                "dynamic_range":  _safe(histogram.get("dynamic_range_score"), 0), # FIX: fast→histogram
                # [0-1] → [0-255]: frontend ve report.py aynı birimi kullanır
                "avg_brightness": round(_safe(fast.get("brightness"), 0) * 255, 1),
                "contrast_rms":   _safe(fast.get("contrast_rms"), 0),           # FIX: hesaplanıyordu, dönmüyordu
            },
            "color": {
                "cast":              color.get("cast", ""),
                "cast_strength":     _safe(color.get("cast_strength")),
                "temperature":       _safe(color.get("temperature_k")),
                "temperature_label": color.get("temperature_label", ""),
                "tint":              _safe(color.get("tint")),
                "saturation":        _safe(color.get("saturation")),
                "noise":             color.get("noise_label", ""),
            },
            # FIX: color_noise modülü hesaplanıyordu ama yanıtta yoktu
            "color_noise": {
                "luma_noise":   _safe(color_noise.get("luma_noise")),
                "chroma_noise": _safe(color_noise.get("chroma_noise")),
                "severity":     color_noise.get("severity", ""),
                "description":  color_noise.get("description", ""),
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
            # Bölgesel haritalar — grid: List[List[float]], değerler 0-100
            "sharpness_map": sharpness_map,
            "highlight_map": highlight_map,
        }
    except Exception as e:
        logger.exception("Kalite analizi hatası")
        return {"error": str(e)}


# ── Endpointler ───────────────────────────────────────────────

# Piksel bombası koruması: 5 MB'lık sıkıştırılmış dosya devasa bitmap'e açılabilir.
MAX_PIXELS = 50_000_000  # 50 MP


def _parse_bool(val: str, default: bool = True) -> bool:
    if val is None or val == "":
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


@csrf_exempt
@require_POST
def analyze(request):
    """
    POST /api/analyze
    Kabul: multipart/form-data
      image           : dosya (zorunlu)
      profile         : none|web|social|print|news
      analyze_ai      : true/false — AI/sahte tespiti çalıştırılsın mı (varsayılan true)
      analyze_quality : true/false — kalite analizi çalıştırılsın mı (varsayılan true)
    Yanıt: JSON (tespit ve/veya kalite)
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

    # ── Analiz türü dallandırması ─────────────────────────────
    # Kullanıcı yalnızca "kalite" seçtiyse AI/sahte tespit modeli HİÇ çağrılmaz.
    analyze_ai      = _parse_bool(request.POST.get("analyze_ai"), True)
    analyze_quality = _parse_bool(request.POST.get("analyze_quality"), True)
    if not analyze_ai and not analyze_quality:
        analyze_ai = analyze_quality = True   # ikisi de kapalıysa varsayılan: ikisi de

    try:
        img = Image.open(BytesIO(raw))
        # Piksel bombası koruması — model/IQA'ya girmeden boyutu doğrula
        if img.width * img.height > MAX_PIXELS:
            return JsonResponse(
                {"error": f"Görsel çözünürlüğü çok yüksek (maks {MAX_PIXELS // 1_000_000} MP)."},
                status=400
            )
    except Exception:
        return JsonResponse({"error": "Görsel dosyası açılamadı veya bozuk."}, status=400)

    detection = {}
    if analyze_ai:
        try:
            detection = _service.predict_pil(img)
        except Exception as e:
            logger.exception("AI tespit hatası")
            return JsonResponse({"error": f"Analiz sırasında hata oluştu: {e}"}, status=500)

    quality = {}
    profile = request.POST.get("profile", "none")
    if analyze_quality:
        ext = os.path.splitext(image_file.name)[1] or ".jpg"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            quality = _run_quality(img, tmp_path, image_file.name, profile)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    response_data = {
        **detection,
        "quality": quality,
        # Hangi analizlerin çalıştığı — geçmiş/Details görünümleri buna göre dallanır
        "analysis": {"ai": analyze_ai, "quality": analyze_quality},
    }

    # Kayıt sahibi — kullanıcı izolasyonu (kayıtlı e-posta veya 'guest')
    owner = request.POST.get("user", "").strip()[:120]

    # Geçmişe kaydet (hata olsa da yanıt dönmeye devam et)
    saved_id = None
    if _db_available:
        try:
            saved_id = _save_to_history(response_data, img, image_file.name, profile, owner)
        except Exception as e:
            logger.warning("Geçmiş kaydedilemedi: %s", e)

    if saved_id:
        response_data["saved_id"] = saved_id

    return JsonResponse(response_data)


def _save_to_history(api_response: dict, img: Image.Image, name: str,
                     profile: str = "none", owner: str = "") -> int:
    """API yanıtını thumbnail ile birlikte veritabanına kaydeder. Kayıt ID'sini döndürür."""
    import json
    quality = api_response.get("quality", {})
    result = {
        "name":        name,
        "user":        owner,    # kullanıcı izolasyonu
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
    return save_analysis(result, img)


import re as _re
_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
VALID_RESULT_FILTERS = {"ai", "real", "manip", "uncertain"}
VALID_FILE_TYPES     = {"jpg", "png", "webp", "tiff", "bmp"}


def _parse_float(val):
    try:
        return float(val) if val not in (None, "") else None
    except (TypeError, ValueError):
        return None


@csrf_exempt
@require_GET
def history_list(request):
    """
    GET /api/history
    Sorgu parametreleri (hepsi isteğe bağlı):
      result    : ai | real | manip | uncertain  — tespit sonucu filtresi
      min_score : kalite skoru alt sınırı (0-100)
      max_score : kalite skoru üst sınırı (0-100)
      date_from : YYYY-MM-DD
      date_to   : YYYY-MM-DD
      file_type : jpg | png | webp | tiff | bmp
      profile   : none | web | social | print | news
      q         : dosya adında arama
      limit     : maks kayıt (varsayılan 30, maks 200)
    """
    if not _verify_api_key(request):
        return JsonResponse({"error": "Yetkisiz istek."}, status=401)

    if not _db_available:
        return JsonResponse({"items": [], "warning": "Veritabanı kullanılamıyor."})

    g = request.GET
    result_f  = g.get("result", "").strip().lower()
    file_type = g.get("file_type", "").strip().lower()
    profile_f = g.get("profile", "").strip().lower()
    date_from = g.get("date_from", "").strip()
    date_to   = g.get("date_to", "").strip()

    try:
        limit = min(max(int(g.get("limit", 30)), 1), 200)
    except (TypeError, ValueError):
        limit = 30

    try:
        items = get_history(
            limit       = limit,
            result_filter = result_f if result_f in VALID_RESULT_FILTERS else None,
            min_score   = _parse_float(g.get("min_score")),
            max_score   = _parse_float(g.get("max_score")),
            date_from   = date_from if _DATE_RE.match(date_from) else None,
            date_to     = date_to if _DATE_RE.match(date_to) else None,
            file_type   = file_type if file_type in VALID_FILE_TYPES else None,
            profile     = profile_f if profile_f in VALID_PROFILES else None,
            search      = g.get("q", "").strip()[:100] or None,
            user        = (g.get("user", "").strip()[:120] or None),
        )
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
        user = request.GET.get("user", "").strip()[:120] or None
        record = get_analysis(analysis_id, user=user)
        if record is None:
            return JsonResponse({"error": "Kayıt bulunamadı."}, status=404)
        return JsonResponse(record)
    except Exception as e:
        logger.exception("Analiz detay hatası")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def history_delete(request, analysis_id: int):
    """
    DELETE/POST /api/history/<id>/delete
    Tekil analiz kaydını siler. (FIX: db.delete_analysis hiç bağlanmamıştı)
    """
    if request.method not in ("DELETE", "POST"):
        return JsonResponse({"error": "Yalnızca DELETE/POST."}, status=405)

    if not _verify_api_key(request):
        return JsonResponse({"error": "Yetkisiz istek."}, status=401)

    if not _db_available:
        return JsonResponse({"error": "Veritabanı kullanılamıyor."}, status=503)

    try:
        from core.db import delete_analysis
        user = (request.POST.get("user") or request.GET.get("user") or "").strip()[:120] or None
        if delete_analysis(analysis_id, user=user):
            return JsonResponse({"deleted": True, "id": analysis_id})
        return JsonResponse({"error": "Kayıt bulunamadı."}, status=404)
    except Exception as e:
        logger.exception("Analiz silme hatası")
        return JsonResponse({"error": str(e)}, status=500)
