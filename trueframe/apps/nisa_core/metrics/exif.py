"""
EXIF verisi çıkarımı — yalnızca Pillow kullanır, ek bağımlılık yok.
"""

from __future__ import annotations
from PIL import Image
from PIL.ExifTags import TAGS


def _to_float(value) -> float | None:
    """IFDRational veya tuple → float."""
    try:
        if hasattr(value, "numerator"):          # IFDRational
            return float(value)
        if isinstance(value, tuple) and len(value) == 2:
            return value[0] / value[1] if value[1] else None
        return float(value)
    except Exception:
        return None


def read_exif(pil_img: Image.Image) -> dict:
    """
    Faydalı EXIF alanlarını çıkar. Yoksa boş dict döner.
    Alanlar: camera, lens, software, datetime, iso, aperture,
             shutter, focal_length, flash, dpi_x, dpi_y, has_gps
    """
    result: dict = {}

    try:
        raw = pil_img.getexif()
    except Exception:
        return result

    # Flatten tag ID → name
    flat = {TAGS.get(k, str(k)): v for k, v in raw.items()}

    # Exif IFD sub-directory (exposure settings)
    try:
        from PIL.ExifTags import IFD
        sub = raw.get_ifd(IFD.Exif)
        flat.update({TAGS.get(k, str(k)): v for k, v in sub.items()})
    except Exception:
        pass

    # ── Camera & Software ────────────────────────────────────
    make  = str(flat.get("Make",  "")).strip()
    model = str(flat.get("Model", "")).strip()
    if make or model:
        result["camera"] = f"{make} {model}".strip()

    sw = flat.get("Software")
    if sw:
        result["software"] = str(sw).strip()

    lens = flat.get("LensModel") or flat.get("Lens")
    if lens:
        result["lens"] = str(lens).strip()

    # ── DateTime ────────────────────────────────────────────
    dt = flat.get("DateTimeOriginal") or flat.get("DateTime")
    if dt:
        result["datetime"] = str(dt)

    # ── ISO ─────────────────────────────────────────────────
    iso = flat.get("ISOSpeedRatings") or flat.get("PhotographicSensitivity")
    if iso is not None:
        try:
            result["iso"] = int(iso)
        except Exception:
            pass

    # ── Aperture ────────────────────────────────────────────
    fnumber = flat.get("FNumber")
    if fnumber is not None:
        v = _to_float(fnumber)
        if v:
            result["aperture"]       = f"f/{v:.1f}"
            result["aperture_value"] = v

    # ── Shutter speed ────────────────────────────────────────
    exp = flat.get("ExposureTime")
    if exp is not None:
        v = _to_float(exp)
        if v:
            result["shutter"]       = f"1/{round(1/v)}s" if v < 1 else f"{v:.1f}s"
            result["shutter_value"] = v

    # ── Focal length ─────────────────────────────────────────
    fl = flat.get("FocalLength")
    if fl is not None:
        v = _to_float(fl)
        if v:
            result["focal_length"]       = f"{v:.0f}mm"
            result["focal_length_value"] = v

    # ── Flash ────────────────────────────────────────────────
    flash = flat.get("Flash")
    if flash is not None:
        try:
            result["flash"] = bool(int(flash) & 0x1)
        except Exception:
            pass

    # ── DPI ─────────────────────────────────────────────────
    # 1) From image .info dict (JFIF / PNG)
    info = getattr(pil_img, "info", {})
    dpi  = info.get("dpi") or info.get("jfif_density")
    if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
        result["dpi_x"] = round(dpi[0])
        result["dpi_y"] = round(dpi[1])
    # 2) From EXIF XResolution / YResolution
    xres = flat.get("XResolution")
    yres = flat.get("YResolution")
    if xres and "dpi_x" not in result:
        v = _to_float(xres)
        if v:
            result["dpi_x"] = round(v)
    if yres and "dpi_y" not in result:
        v = _to_float(yres)
        if v:
            result["dpi_y"] = round(v)

    # ── GPS ──────────────────────────────────────────────────
    try:
        from PIL.ExifTags import IFD
        gps_ifd = raw.get_ifd(IFD.GPSInfo)
        result["has_gps"] = len(gps_ifd) > 0
    except Exception:
        result["has_gps"] = False

    return result
