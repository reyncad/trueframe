"""
Yayın profilleri — tanımlar ve pass/fail değerlendirmesi.

Değişiklikler:
  - Baskı profilinden EXIF DPI kontrolü kaldırıldı (anlamsız).
  - Haber profiline eğiklik (tilt) kontrolü eklendi.
  - Megapiksel eşikleri A4@300dpi gerçeği yansıtacak şekilde düzeltildi.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


# ── Check tanımı ─────────────────────────────────────────────

@dataclass
class Check:
    name:        str
    key:         str
    get_value:   Callable[[dict], tuple]  # data → (raw_value, display_str)
    threshold:   float
    compare:     str                       # "gte" | "lte"
    unit:        str  = ""
    description: str  = ""


@dataclass
class Profile:
    id:          str
    label:       str
    icon:        str
    description: str
    checks:      list[Check] = field(default_factory=list)


# ── Value getters ─────────────────────────────────────────────

def _width(d):     v = d["technical"]["width"];        return v, f"{v}px"
def _height(d):    v = d["technical"]["height"];       return v, f"{v}px"
def _mp(d):        v = d["technical"]["megapixels"];   return v, f"{v:.1f} MP"
def _sharp(d):     v = d["fast"]["sharpness_lap"];     return v, f"{v:.0f}"
def _noise(d):     v = d["fast"]["noise_est"];         return v, f"{v:.1f}"
def _hl(d):        v = d["histogram"]["highlight_clip_pct"]; return v, f"{v:.1f}%"
def _sh(d):        v = d["histogram"]["shadow_clip_pct"];    return v, f"{v:.1f}%"

def _long(d):
    t = d["technical"]
    v = max(t["width"], t["height"])
    return v, f"{v}px"

def _tilt(d):
    """Eğiklik açısı (mutlak değer). Güven düşükse N/A döner."""
    geo        = d.get("geometry", {}).get("tilt", {})
    v          = geo.get("abs_angle")
    confidence = geo.get("confidence", 1.0)
    if v is None or confidence < 0.20:
        return (None, "N/A — güven düşük")
    return (v, f"{geo.get('label','—')}")

def _moire(d):
    """Moire skoru (düşük = iyi)."""
    geo = d.get("geometry", {}).get("moire", {})
    v   = geo.get("score")
    return (v, f"{v:.0f}" if v is not None else "—") if v is not None else (None, "N/A")


# ── Profil tanımları ──────────────────────────────────────────

PROFILES: dict[str, Profile] = {
    "none": Profile(
        id="none", label="Genel Analiz", icon="🔬",
        description="Profil bağımsız genel kalite değerlendirmesi",
        checks=[
            Check("Keskinlik",            "sharpness",      _sharp,  200, "gte"),
            Check("Gürültü",              "noise",          _noise,   20, "lte"),
            Check("Highlight Kırpılması", "highlight_clip", _hl,     5.0, "lte", "%"),
            Check("Shadow Kırpılması",    "shadow_clip",    _sh,     5.0, "lte", "%"),
        ],
    ),

    "web": Profile(
        id="web", label="Web / Blog", icon="🌐",
        description="Web sitesi, blog, haber portali",
        checks=[
            Check("Min Genişlik",         "min_width",      _width, 1000, "gte", "px"),
            Check("Min Yükseklik",        "min_height",     _height, 700, "gte", "px"),
            Check("Keskinlik",            "sharpness",      _sharp,  200, "gte"),
            Check("Gürültü",              "noise",          _noise,   22, "lte"),
            Check("Highlight Kırpılması", "highlight_clip", _hl,     5.0, "lte", "%"),
            Check("Shadow Kırpılması",    "shadow_clip",    _sh,     5.0, "lte", "%"),
        ],
    ),

    "social": Profile(
        id="social", label="Sosyal Medya", icon="📱",
        description="Instagram, Twitter/X, Facebook",
        checks=[
            Check("Min Boyut (uzun kenar)", "long_side",      _long, 1080, "gte", "px"),
            Check("Keskinlik",              "sharpness",      _sharp,  150, "gte"),
            Check("Gürültü",               "noise",          _noise,   28, "lte"),
            Check("Highlight Kırpılması",  "highlight_clip", _hl,     8.0, "lte", "%"),
        ],
    ),

    "print": Profile(
        id="print", label="Baskı A4 (300 DPI)", icon="🖨️",
        description="Dergi, broşür — A4@300dpi = min 8.7 MP",
        checks=[
            # A4@300dpi: 2480×3508 px = 8.7 MP.
            # EXIF DPI kontrolü KALDIRILDI — editörde değiştirilebilir anlamsız değer.
            # Piksel boyutu gerçek ölçüt.
            Check("Min Genişlik (A4@300)",  "min_width",      _width,  2480, "gte", "px",
                  "A4 dikey baskıda minimum piksel genişliği"),
            Check("Min Yükseklik (A4@300)", "min_height",     _height, 3508, "gte", "px",
                  "A4 dikey baskıda minimum piksel yüksekliği"),
            Check("Megapiksel",             "megapixels",     _mp,      8.7, "gte", " MP",
                  "A4@300dpi için minimum"),
            Check("Keskinlik",              "sharpness",      _sharp,   500, "gte"),
            Check("Gürültü",               "noise",          _noise,    10, "lte"),
            Check("Highlight Kırpılması",  "highlight_clip", _hl,      2.0, "lte", "%",
                  "Baskıda kırpılma çok belirgin görünür"),
            Check("Shadow Kırpılması",     "shadow_clip",    _sh,      2.0, "lte", "%"),
            Check("Moire Riski",           "moire",          _moire,  25.0, "lte",
                  description="Baskıda moire örüntüsü belirginleşir"),
        ],
    ),

    "news": Profile(
        id="news", label="Haber Ajansı", icon="📰",
        description="AP, Reuters, AA — yüksek çözünürlük & doğru geometri",
        checks=[
            Check("Min Boyut (uzun kenar)", "long_side",      _long, 1920, "gte", "px"),
            Check("Megapiksel",             "megapixels",     _mp,    8.0, "gte", " MP"),
            Check("Keskinlik",              "sharpness",      _sharp,  400, "gte"),
            Check("Gürültü",               "noise",          _noise,   12, "lte"),
            Check("Highlight Kırpılması",  "highlight_clip", _hl,     3.0, "lte", "%"),
            Check("Shadow Kırpılması",     "shadow_clip",    _sh,     3.0, "lte", "%"),
            Check("Horizon Eğikliği",      "tilt",           _tilt,   2.0, "lte", "°",
                  "Ajans standartları: < 2° eğiklik"),
        ],
    ),
}


# ── Değerlendirme ─────────────────────────────────────────────

def evaluate(profile_id: str, data: dict) -> dict:
    profile = PROFILES.get(profile_id, PROFILES["none"])
    results = []

    for c in profile.checks:
        raw, display = c.get_value(data)

        if raw is None:
            results.append({
                "name": c.name, "key": c.key, "passed": None,
                "value": display,
                "threshold": f"{'≥' if c.compare == 'gte' else '≤'} {c.threshold}{c.unit}",
                "description": c.description,
            })
        else:
            passed = (raw >= c.threshold) if c.compare == "gte" else (raw <= c.threshold)
            results.append({
                "name": c.name, "key": c.key, "passed": bool(passed),
                "value": display,
                "threshold": f"{'≥' if c.compare == 'gte' else '≤'} {c.threshold}{c.unit}",
                "description": c.description,
            })

    total  = len(results)
    passed = sum(1 for r in results if r["passed"] is True)
    failed = sum(1 for r in results if r["passed"] is False)

    return {
        "profile_id":     profile.id,
        "profile_label":  profile.label,
        "checks":         results,
        "total":          total,
        "passed":         passed,
        "failed":         failed,
        "overall_passed": failed == 0,
        "score_pct":      round(passed / total * 100) if total else 0,
    }
