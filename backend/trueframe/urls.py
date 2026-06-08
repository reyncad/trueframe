from django.urls import path, include
from detector.api_views import analyze, history_list, history_detail
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
    """
    try:
        from core.db import get_analysis
        from core.report import render_html_report
        record = get_analysis(analysis_id)
        if record is None:
            return JsonResponse({"error": "Kayıt bulunamadı."}, status=404)
        # api_response → tam analiz verisi; quality alt-bloğunu kök seviyeye taşı
        data = record
        if "quality" in data and isinstance(data["quality"], dict):
            data = {**data, **data["quality"]}
        html = render_html_report(data)
        return HttpResponse(html, content_type="text/html; charset=utf-8")
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


urlpatterns = [
    path("", health, name="root"),
    path("api/analyze", analyze, name="api_analyze"),
    path("api/history", history_list, name="api_history_list"),
    path("api/history/<int:analysis_id>", history_detail, name="api_history_detail"),
    path("api/report/<int:analysis_id>", html_report, name="api_report"),  # FIX: dead code kurtarıldı
    path("health/", health, name="health"),
]
