import sys
from pathlib import Path
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.detection.services import CNNDetectionService

_service = CNNDetectionService()


@require_http_methods(["GET", "POST"])
def index(request):
    if request.method == "GET":
        return render(request, "detector/index.html")

    uploaded = request.FILES.get("image")
    if not uploaded:
        return render(request, "detector/index.html", {"error": "Lütfen bir fotoğraf seçin."})

    allowed = {"image/jpeg", "image/png", "image/webp"}
    if uploaded.content_type not in allowed:
        return render(request, "detector/index.html", {"error": "Sadece JPG, PNG veya WebP yükleyebilirsiniz."})

    try:
        image = Image.open(uploaded).convert("RGB")
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
