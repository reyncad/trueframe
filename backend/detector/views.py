import sys
from pathlib import Path
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.detection.services import CNNDetectionService

_service = CNNDetectionService()

# ── MIME doğrulama (api_views.py ile tutarlı) ────────────────
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

try:
    import magic as _magic
    _magic_available = True
except ImportError:
    _magic_available = False


def _is_allowed_mime(raw: bytes, content_type: str) -> bool:
    """
    Gerçek MIME tipini ilk 2048 byte ile doğrular.
    python-magic kurulu değilse browser header'ına güvenir.
    Bu kontrol olmadan saldırgan .php/.html dosyasını image/jpeg header'ıyla gönderebilir.
    """
    if _magic_available:
        real = _magic.from_buffer(raw[:2048], mime=True)
        return real in _ALLOWED_TYPES
    return content_type in _ALLOWED_TYPES


@require_http_methods(["GET", "POST"])
def index(request):
    if request.method == "GET":
        return render(request, "detector/index.html")

    uploaded = request.FILES.get("image")
    if not uploaded:
        return render(request, "detector/index.html", {"error": "Lütfen bir fotoğraf seçin."})

    raw = uploaded.read()

    if not _is_allowed_mime(raw, uploaded.content_type):
        return render(request, "detector/index.html", {"error": "Sadece JPG, PNG veya WebP yükleyebilirsiniz."})

    try:
        from io import BytesIO
        image = Image.open(BytesIO(raw)).convert("RGB")
        result = _service.predict_pil(image)
    except Exception as exc:
        return render(request, "detector/index.html", {"error": f"Fotoğraf işlenemedi: {exc}"})

    import base64, io
    buf = io.BytesIO()
    image.thumbnail((600, 600))
    image.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    return render(request, "detector/index.html", {
        "result": result,
        "img_b64": img_b64,
        "filename": uploaded.name,
    })
