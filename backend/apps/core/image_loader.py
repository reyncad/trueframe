"""
Görsel yükleme — base64 data-URI, URL veya dosya yolu.
Daima (PIL.Image, tmp_path: str | None) döndürür.
Caller, tmp_path'i silmekten sorumludur.
"""

from __future__ import annotations

import base64
import io
import os
import tempfile

import requests
from PIL import Image

def _prepare_for_iqa(pil_img: Image.Image, max_edge: int = 1080) -> Image.Image:
    """
    IQA modellerinin belleği (RAM) tüketmesini önler ve 
    modelin eğitim dağılımına uygun boyutlara çeker.
    """
    width, height = pil_img.size
    
    # Sadece fotoğraf belirlediğimiz maksimum sınırın üzerindeyse küçült
    if max(width, height) > max_edge:
        # En uzun kenarı max_edge (örn: 1080) yapacak şekilde en-boy oranını hesapla
        ratio = max_edge / float(max(width, height))
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        # LANCZOS, piksel bozulmasını (aliasing) en aza indiren, 
        # IQA için en güvenli yeniden boyutlandırma algoritmasıdır.
        pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
    return pil_img

def load_image(source: str) -> tuple[Image.Image, str | None]:
    """
    Returns (pil_image, tmp_file_path).
    """
    # 1. Görseli kaynaktan çek ve PIL nesnesine dönüştür
    if source.startswith("data:image"):
        _, b64 = source.split(",", 1)
        raw = base64.b64decode(b64)
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
    elif source.startswith(("http://", "https://")):
        resp = requests.get(source, timeout=15)
        resp.raise_for_status()
        pil = Image.open(io.BytesIO(resp.content)).convert("RGB")
    else:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Dosya bulunamadı: {source}")
        pil = Image.open(source).convert("RGB")

    # 2. ORTAK İŞLEM: Bellek patlamasını önlemek için yeniden boyutlandır
    pil = _prepare_for_iqa(pil, max_edge=1080)

    # 3. Sonuçları döndür
    if source.startswith(("data:image", "http")):
        tmp = _save_tmp(pil)
        return pil, tmp
    
    return pil, None


def _save_tmp(pil: Image.Image) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    pil.save(tmp.name, quality=95)
    tmp.close()
    return tmp.name


def cleanup_tmp(tmp_path: str | None) -> None:
    if tmp_path and os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass

