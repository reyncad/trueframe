"""
TrueFrame — Kritik Bug Testleri
Tespit edilen hataları doğrular; düzeltmelerden sonra tüm testler GREEN olmalıdır.
"""
import sys
import os
import json
import sqlite3
import tempfile
import threading
from pathlib import Path
from io import BytesIO
from unittest.mock import patch, MagicMock

# ── Path ayarı ───────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
APPS = BACKEND / "apps"
sys.path.insert(0, str(APPS))

# nisa_core → core alias
import importlib.util
_nc = APPS / "nisa_core"
_spec = importlib.util.spec_from_file_location(
    "core", _nc / "__init__.py",
    submodule_search_locations=[str(_nc)]
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["core"] = _mod
_spec.loader.exec_module(_mod)

from PIL import Image
import numpy as np

# ─────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────

def make_test_image(w=200, h=200, mode="RGB") -> Image.Image:
    arr = np.random.randint(50, 200, (h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr, mode)


# ═════════════════════════════════════════════════════════════
# BÖLÜM 1: fast.py alan adı hataları
# ═════════════════════════════════════════════════════════════

def test_fast_metrics_field_names():
    """
    BUG #1: api_views.py fast.get('avg_brightness') ama fast.py'de alan adı 'brightness'.
    BUG #2: api_views.py fast.get('dynamic_range') ama bu alan histogram'da.
    BUG #3: api_views.py fast.get('exposure_label') ama bu alan histogram'da.
    """
    from core.metrics.fast import compute_fast_metrics
    img = make_test_image()
    result = compute_fast_metrics(img)

    # Doğru alan adları
    assert "brightness" in result,         "FAIL: 'brightness' alanı yok (api_views avg_brightness kullanıyor → her zaman 0)"
    assert "sharpness_lap" in result,      "FAIL: sharpness_lap yok"
    assert "noise_est" in result,          "FAIL: noise_est yok"

    # Yanlış alan adları — bunlar OLMAMALI (karışıklığa işaret eder)
    assert "avg_brightness" not in result, "WARN: avg_brightness yok — api_views bunu arıyor, yanlış isim"
    assert "dynamic_range" not in result,  "INFO: dynamic_range fast'ta yok, histogram'da olmalı"
    assert "exposure_label" not in result, "INFO: exposure_label fast'ta yok, histogram'da olmalı"

    print(f"  ✓ fast fields: {list(result.keys())}")


def test_histogram_has_correct_fields():
    """histogram.py doğru alanları döndürüyor mu?"""
    from core.metrics.histogram import analyze_histogram
    img = make_test_image()
    h = analyze_histogram(img)

    assert "exposure_label" in h,        "FAIL: exposure_label histogram'da yok"
    assert "dynamic_range_score" in h,   "FAIL: dynamic_range_score histogram'da yok"
    assert "mean_brightness" in h,       "FAIL: mean_brightness histogram'da yok"
    assert "highlight_clip_pct" in h,    "FAIL: highlight_clip_pct yok"
    assert "shadow_clip_pct" in h,       "FAIL: shadow_clip_pct yok"
    print(f"  ✓ histogram fields OK, label={h['exposure_label']}, dr={h['dynamic_range_score']}")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 2: profiles.py → api_views.py alan adı uyumsuzluğu
# ═════════════════════════════════════════════════════════════

def test_profiles_evaluate_field_names():
    """
    BUG #4: api_views.py profile_r.get('label') ama evaluate() 'profile_label' döndürüyor.
    Sonuç: Profile adı frontend'de hiç gösterilmiyor.
    """
    from core.profiles import evaluate

    # Dummy veri
    data = {
        "technical": {"width": 1920, "height": 1080, "megapixels": 2.07},
        "fast":      {"sharpness_lap": 300, "noise_est": 10},
        "histogram": {"highlight_clip_pct": 1.0, "shadow_clip_pct": 0.5},
        "geometry":  {},
    }
    result = evaluate("web", data)

    assert "profile_label" in result, "FAIL: evaluate() 'profile_label' döndürmüyor"
    assert result["profile_label"] == "Web / Blog", f"FAIL: yanlış label: {result['profile_label']}"

    # api_views.py'deki yanlış anahtar
    wrong = result.get("label", "NOT_FOUND")
    assert wrong == "NOT_FOUND", f"BUG CONFIRMED: 'label' anahtarı var mı? Değeri: {wrong}"
    print(f"  ✓ profile_label='{result['profile_label']}', passed={result['passed']}/{result['total']}")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 3: db.py — get_history SELECT eksik kolonlar
# ═════════════════════════════════════════════════════════════

def test_db_get_history_columns():
    """
    BUG #5: get_history() SQL'i label, fake_prob, real_prob kolonlarını SELECT etmiyor
    ama return dict'i bu kolonlara erişiyor → KeyError.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Ortam değişkenini geçici olarak ayarla
        db_path = os.path.join(tmpdir, "test.db")

        # Geçici patch
        import core.db as db_mod
        orig_path = db_mod.DB_PATH
        db_mod.DB_PATH = Path(db_path)

        try:
            db_mod.init_db()

            # Test kaydı ekle
            img = make_test_image()
            rid = db_mod.save_analysis({
                "name":      "test.jpg",
                "profile":   "web",
                "overall":   75.5,
                "verdict":   "Test verdict",
                "label":     "MUHTEMELEN GERÇEK",
                "fake_prob": 15.2,
                "real_prob": 84.8,
            }, img)
            assert rid > 0

            # get_history çağrısı KeyError üretmemeli
            items = db_mod.get_history(limit=10)
            assert len(items) == 1

            item = items[0]
            assert item["label"] == "MUHTEMELEN GERÇEK", f"FAIL: label={item.get('label')}"
            assert item["fake_prob"] == 15.2,            f"FAIL: fake_prob={item.get('fake_prob')}"
            assert item["real_prob"] == 84.8,            f"FAIL: real_prob={item.get('real_prob')}"
            print(f"  ✓ get_history kolonları OK: label='{item['label']}', fake_prob={item['fake_prob']}")

        finally:
            db_mod.DB_PATH = orig_path


# ═════════════════════════════════════════════════════════════
# BÖLÜM 4: _save_to_history hardcoded "social" profili
# ═════════════════════════════════════════════════════════════

def test_save_to_history_profile_hardcoded():
    """
    BUG #6 (DÜZELTİLDİ): api_views._save_to_history() artık gerçek profil değerini kullanıyor.
    Kullanıcının seçtiği profil doğru şekilde kaydediliyor.
    """
    src = (BACKEND / "detector" / "api_views.py").read_text()
    # Hardcode "social" artık olmamalı
    assert '"profile":     "social"' not in src and "'profile':     'social'" not in src and \
           '"profile": "social"' not in src and "'profile': 'social'" not in src, \
        "REGRESSION: _save_to_history hâlâ 'social' hardcode içeriyor"

    # Dinamik profil kullanıldığını doğrula
    assert '"profile":     profile' in src or '"profile": profile' in src or \
           'result.get("profile"' in src or 'profile,' in src, \
        "Dinamik profil ataması bulunamadı"

    print("  ✓ _save_to_history gerçek profil değerini kullanıyor")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 5: report.py dead code — URL endpoint yok
# ═════════════════════════════════════════════════════════════

def test_report_endpoint_exists():
    """
    BUG #7 (DÜZELTİLDİ): /api/report/<id> endpoint'i urls.py'e eklendi.
    render_html_report() artık erişilebilir.
    """
    urls_src   = (BACKEND / "trueframe" / "urls.py").read_text()
    report_src = (BACKEND / "apps" / "nisa_core" / "report.py").read_text()

    assert "render_html_report" in report_src, "render_html_report fonksiyonu bulunamadı"
    assert "api/report" in urls_src, \
        "REGRESSION: /api/report/<id> endpoint urls.py'de yok"

    print("  ✓ /api/report/<id> endpoint urls.py'de kayıtlı")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 6: Frontend fake heatmap zones
# ═════════════════════════════════════════════════════════════

def test_fake_heatmap_zones_removed():
    """
    BUG #8 (DÜZELTİLDİ): Statik 'texture/lighting/edge' zone'lar Result.cshtml'den kaldırıldı.
    Rozetler artık gerçek analiz verisine (blur tipi, eğiklik, highlight kırpılması) dayalı.
    """
    result_view = (ROOT / "frontend" / "Views" / "Analysis" / "Result.cshtml").read_text()

    assert "heatmap-zone" not in result_view, \
        "REGRESSION: Statik heatmap-zone'lar hâlâ Result.cshtml'de"

    # Gerçek veri bazlı rozetlerin varlığını doğrula
    assert "BlurType" in result_view or "BlurLabel" in result_view, \
        "Blur rozeti bulunamadı — gerçek veri bağlantısı eksik olabilir"

    print("  ✓ Statik heatmap zone'ları kaldırıldı; rozetler gerçek veriye dayalı")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 7: AnalysisController CheckItem null→false dönüşümü
# ═════════════════════════════════════════════════════════════

def test_check_passed_null_handling():
    """
    BUG #9 (DÜZELTİLDİ): AnalysisController.cs artık Passed null değerini koruyarak geçiriyor.
    'N/A — güven düşük' durumları artık kırmızı ✗ yerine gri — gösteriyor.
    """
    controller_src = (ROOT / "frontend" / "Controllers" / "AnalysisController.cs").read_text()
    assert "Passed = c.Passed ?? false" not in controller_src, \
        "REGRESSION: Passed ?? false null-coalescing geri geldi — N/A durumları yanlış gösterilir"
    assert "Passed = c.Passed" in controller_src, \
        "Passed ataması bulunamadı — AnalysisController kontrolü yapılmalı"
    print("  ✓ CheckItem.Passed null korunuyor — N/A durumları gri — olarak görünür")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 8: Security — users.json şifre hash'i repoda
# ═════════════════════════════════════════════════════════════

def test_users_json_sha256_hash():
    """
    SECURITY:
    1. users.json .gitignore'da olmalı (repoya commit edilmemeli).
    2. UserStore.Login() legacy SHA-256 hash'leri PBKDF2'ye otomatik yükseltmeli.
    """
    gitignore = (ROOT / ".gitignore").read_text()
    assert "users.json" in gitignore or "Data/users.json" in gitignore, \
        "REGRESSION: users.json .gitignore'dan çıkarılmış — şifre hash'leri repoya girdi"

    # UserStore.cs'de otomatik migration mekanizması mevcut olmalı
    userstore_src = (ROOT / "frontend" / "Services" / "UserStore.cs").read_text()
    assert "PasswordHash = PasswordHasher.Hash(password)" in userstore_src, \
        "REGRESSION: UserStore login'de hash migration yapmıyor"

    # Eğer users.json mevcutsa, içindeki SHA-256 hash'leri belgele (hata değil, uyarı)
    users_file = ROOT / "frontend" / "Data" / "users.json"
    if users_file.exists():
        users = json.loads(users_file.read_text())
        for username, data in users.items():
            h = data.get("PasswordHash", "")
            if len(h) == 64 and all(c in "0123456789ABCDEFabcdef" for c in h):
                print(f"  ⚠ NOTICE: '{username}' legacy SHA-256 hash — ilk login'de PBKDF2'ye otomatik yükseltilecek")

    print("  ✓ users.json .gitignore'da; UserStore login'de otomatik hash migration yapıyor")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 9: Dimensions hesaplama doğruluğu
# ═════════════════════════════════════════════════════════════

def test_dimensions_range():
    """6D boyutlarının 0-100 aralığında olduğunu doğrular."""
    from core.metrics.dimensions import compute_dimensions

    fast = {"sharpness_lap": 500, "noise_est": 10}
    histogram = {
        "highlight_clip_pct": 2.0,
        "shadow_clip_pct": 1.0,
        "dynamic_range_score": 65.0,
    }
    color = {"cast_strength": 0.05, "saturation": 55}
    blur_type = {"type": "sharp"}
    color_noise = {"chroma_noise_ratio": 0.1, "severity": "hafif"}
    iqa_metrics = {
        "musiq":   {"status": "ok", "score": 75.0},
        "paq2piq": {"status": "ok", "score": 65.0},
        "clip_iqa":{"status": "ok", "score": 0.75},
        "brisque": {"status": "ok", "score": 20.0},
        "niqe":    {"status": "ok", "score": 4.0},
    }

    dims = compute_dimensions(fast, histogram, color, blur_type, color_noise, iqa_metrics)

    for k, v in dims.items():
        assert 0.0 <= v <= 100.0, f"FAIL: {k}={v} aralık dışı [0-100]"

    print(f"  ✓ 6D dims: {dims}")


# ═════════════════════════════════════════════════════════════
# BÖLÜM 10: verdict.py boş girdi dayanıklılığı
# ═════════════════════════════════════════════════════════════

def test_verdict_with_empty_inputs():
    """Boş/None girdilerle verdict çökmemeli."""
    from core.verdict import generate_verdict

    verdict = generate_verdict(
        overall=None,
        profile_result={"profile_id": "none", "profile_label": ""},
        fast={},
        histogram={},
        color={},
        exif={},
        iqa_metrics={},
        geometry=None,
        sharpness_map=None,
        blur_type=None,
        color_noise=None,
    )
    assert "yeterli veri" in verdict.lower() or verdict != "", \
        "Boş girdi için verdict boş döndü"
    print(f"  ✓ verdict(None overall): '{verdict[:60]}...'")


def test_verdict_with_valid_data():
    """Normal veriyle verdict mantıklı çıktı üretmeli."""
    from core.verdict import generate_verdict

    verdict = generate_verdict(
        overall=82.5,
        profile_result={"profile_id": "web", "profile_label": "Web / Blog",
                        "passed": 5, "total": 6},
        fast={"sharpness_lap": 400, "noise_est": 8},
        histogram={"highlight_clip_pct": 1.2, "shadow_clip_pct": 0.3},
        color={"cast": "nötr", "cast_strength": 0.02, "saturation": 60,
               "temperature_k": 5600},
        exif={"iso": 200},
        iqa_metrics={
            "musiq":   {"status": "ok", "score": 80.0, "label": "iyi"},
            "brisque": {"status": "ok", "score": 22.0, "label": "iyi"},
        },
        geometry={"tilt": {"is_tilted": False, "confidence": 0.8}},
        sharpness_map={"grid": [[60]*10]*8},
        blur_type={"type": "sharp"},
        color_noise={"severity": "yok"},
    )
    assert len(verdict) > 20, "verdict çok kısa"
    assert "82.5" in verdict or "82" in verdict, f"skor verdict'te yok: {verdict}"
    print(f"  ✓ verdict OK: '{verdict[:80]}...'")


# ═════════════════════════════════════════════════════════════
# TEST RUNNER
# ═════════════════════════════════════════════════════════════

TESTS = [
    ("fast_metrics_field_names",     test_fast_metrics_field_names),
    ("histogram_has_correct_fields", test_histogram_has_correct_fields),
    ("profiles_evaluate_field_names",test_profiles_evaluate_field_names),
    ("db_get_history_columns",       test_db_get_history_columns),
    ("save_to_history_profile",       test_save_to_history_profile_hardcoded),
    ("report_endpoint_exists",       test_report_endpoint_exists),
    ("fake_heatmap_zones_removed",   test_fake_heatmap_zones_removed),
    ("check_passed_null_handling",   test_check_passed_null_handling),
    ("users_json_security",          test_users_json_sha256_hash),
    ("dimensions_range",             test_dimensions_range),
    ("verdict_empty_inputs",         test_verdict_with_empty_inputs),
    ("verdict_valid_data",           test_verdict_with_valid_data),
]


if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = 0

    print("\n" + "═" * 60)
    print("  TrueFrame Bug Test Suite")
    print("═" * 60)

    for name, fn in TESTS:
        print(f"\n▶ {name}")
        try:
            fn()
            print(f"  → PASS")
            passed += 1
        except AssertionError as e:
            print(f"  → FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  → ERROR: {type(e).__name__}: {e}")
            errors += 1

    print("\n" + "─" * 60)
    print(f"  Sonuç: {passed} PASS  |  {failed} FAIL  |  {errors} ERROR")
    print("─" * 60 + "\n")

    if failed > 0 or errors > 0:
        sys.exit(1)
