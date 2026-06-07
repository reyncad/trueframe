import json
from io import BytesIO

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from PIL import Image

from apps.detection.services import DetectionService

_service = DetectionService()


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

    try:
        img = Image.open(BytesIO(image_file.read()))
        result = _service.predict_pil(img)
    except Exception as e:
        return JsonResponse({"error": f"Analiz sırasında hata oluştu: {e}"}, status=500)

    return JsonResponse(result)
