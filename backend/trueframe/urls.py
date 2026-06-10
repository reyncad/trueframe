from django.urls import path, include
from detector.api_views import analyze, history_list, history_detail, history_delete
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
import sys
from pathlib import Path

_apps = str(Path(__file__).resolve().parents[1] / "apps")
if _apps not in sys.path:
    sys.path.insert(0, _apps)


def health(request):
    """Docker healthcheck endpoint."""
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_GET
def html_report(request, analysis_id: int):
    """
    GET /api/report/<id>
    Tarayıcıda açılabilen, yazdırılabilir HTML rapor.
    report.py render_html_report() kullanır.

    render_html_report() raw bundle formatı bekler (histogram, fast, blur_type dict,
    profile_result dict) ama DB'de API response formatı saklanır (exposure, geometry
    flat dict, profile_label/pass/total). Bu fonksiyon aralarında köprü kurar.
    """
    try:
        from core.db import get_analysis
        from core.report import render_html_report
        user = request.GET.get("user", "").strip()[:120] or None
        record = get_analysis(analysis_id, user=user)
        if record is None:
            return JsonResponse({"error": "Kayıt bulunamadı."}, status=404)

        # record = api_response formatı: {label, fake_prob, ..., quality: {...}, ...}
        quality    = record.get("quality") or {}
        exposure   = quality.get("exposure") or {}
        geo_flat   = quality.get("geometry") or {}
        color_api  = quality.get("color") or {}
        cn_api     = quality.get("color_noise") or {}

        data = {
            # Üst düzey alanlar (AI tespit)
            "name":          record.get("name", ""),
            "thumbnail":     record.get("thumbnail", ""),
            "created_at":    record.get("created_at", ""),
            "label":         record.get("label", ""),
            "fake_prob":     record.get("fake_prob", 0),
            "real_prob":     record.get("real_prob", 0),
            "confidence":    record.get("confidence", 0),
            "is_ai_generated": record.get("is_ai_generated", False),
            "is_manipulated":  record.get("is_manipulated", False),
            "manip_score":   record.get("manip_score", 0),
            "analysis":      record.get("analysis") or {},

            # Kalite — doğrudan geçen alanlar
            "overall":    quality.get("quality_score", 0),
            "verdict":    quality.get("verdict", ""),
            "dimensions": quality.get("dimensions") or {},
            "technical":  quality.get("technical") or {},
            "exif":       quality.get("exif") or {},
            "iqa_metrics": quality.get("iqa_metrics") or [],
            "sharpness_map": quality.get("sharpness_map") or {},
            "highlight_map": quality.get("highlight_map") or {},

            # profile_result — render_html_report bu dict yapısını bekler
            "profile_result": {
                "profile_label": quality.get("profile_label", ""),
                "passed":        quality.get("profile_pass", 0),
                "total":         quality.get("profile_total", 0),
                "checks":        quality.get("checks") or [],
            },

            # histogram — render_html_report bu anahtarları bekler (exposure'dan yeniden türet)
            "histogram": {
                "exposure_label":      exposure.get("label", ""),
                "highlight_clip_pct":  exposure.get("highlight_clip", 0),
                "shadow_clip_pct":     exposure.get("shadow_clip", 0),
                "dynamic_range_score": exposure.get("dynamic_range", 0),
                "mean_brightness":     exposure.get("avg_brightness", 0),  # zaten [0-255]
            },

            # fast — sadece contrast_rms render_html_report'ta kullanılıyor
            "fast": {
                "contrast_rms": exposure.get("contrast_rms", 0),
            },

            # geometry — render_html_report tilt{} ve moire{} alt-dict'leri bekler
            "geometry": {
                "tilt": {
                    "angle":      geo_flat.get("tilt_angle"),
                    "label":      geo_flat.get("tilt_label", ""),
                    "confidence": geo_flat.get("tilt_confidence"),
                    "is_tilted":  abs(geo_flat.get("tilt_angle") or 0) >= 1.5,
                    "severity":   geo_flat.get("tilt_label", ""),
                },
                "moire": {
                    "score":    geo_flat.get("moire_score", 0),
                    "label":    geo_flat.get("moire_label", "Yok"),
                    "detected": (geo_flat.get("moire_score") or 0) > 35,
                },
            },

            # blur_type — render_html_report type/label/description dict bekler
            "blur_type": {
                "type":        geo_flat.get("blur_type", ""),
                "label":       geo_flat.get("blur_label", ""),
                "description": geo_flat.get("blur_label", ""),
            },

            # color — render_html_report cast/temperature_label/saturation/noise_label bekler
            "color": {
                "cast":              color_api.get("cast", ""),
                "cast_strength":     color_api.get("cast_strength", 0),
                "temperature_k":     color_api.get("temperature", 0),
                "temperature_label": color_api.get("temperature_label", ""),
                "tint":              color_api.get("tint", 0),
                "saturation":        color_api.get("saturation", 0),
                "noise_label":       color_api.get("noise", ""),
            },

            # color_noise
            "color_noise": {
                "luma_noise":   cn_api.get("luma_noise", 0),
                "chroma_noise": cn_api.get("chroma_noise", 0),
                "severity":     cn_api.get("severity", ""),
                "description":  cn_api.get("description", ""),
            },
        }

        html = render_html_report(data)
        return HttpResponse(html, content_type="text/html; charset=utf-8")
    except Exception as e:
        import traceback
        return HttpResponse(
            f"<pre style='font-family:monospace;padding:20px'>HTML Rapor Hatası:\n{traceback.format_exc()}</pre>",
            status=500, content_type="text/html; charset=utf-8"
        )


urlpatterns = [
    path("", health, name="root"),
    path("api/analyze", analyze, name="api_analyze"),
    path("api/history", history_list, name="api_history_list"),
    path("api/history/<int:analysis_id>", history_detail, name="api_history_detail"),
    path("api/history/<int:analysis_id>/delete", history_delete, name="api_history_delete"),
    path("api/report/<int:analysis_id>", html_report, name="api_report"),  # FIX: dead code kurtarıldı
    path("health/", health, name="health"),
]
