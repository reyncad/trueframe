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


def load_image(source: str) -> tuple[Image.Image, str | None]:
    """
    Returns (pil_image, tmp_file_path).
    tmp_file_path is None only if source is a direct file path that
    already exists on disk (we don't copy it).
    """
    if source.startswith("data:image"):
        _, b64 = source.split(",", 1)
        raw = base64.b64decode(b64)
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
        tmp = _save_tmp(pil)
        return pil, tmp

    if source.startswith(("http://", "https://")):
        resp = requests.get(source, timeout=15)
        resp.raise_for_status()
        pil = Image.open(io.BytesIO(resp.content)).convert("RGB")
        tmp = _save_tmp(pil)
        return pil, tmp

    # Local file path
    if not os.path.exists(source):
        raise FileNotFoundError(f"Dosya bulunamadı: {source}")
    pil = Image.open(source).convert("RGB")
    return pil, None  # no tmp copy needed


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
