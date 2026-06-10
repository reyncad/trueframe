"""
Kapsamlı değerlendirme paragrafı.

Tüm metrik katmanlarını bağlam duyarlı biçimde birleştirerek
tutarlı, çelişkisiz ve organik bir Türkçe değerlendirme üretir.
"""

from __future__ import annotations

from core.config import IQA_METRICS, TILT_FAIL_DEG, TILT_WARN_DEG

# Geometry modülü zaten confidence gate'ini geçirmiştir;
# verdict'te sadece çok düşük güven vakalarını eleyecek kadar düşük eşik yeterli.
_MIN_VERDICT_CONFIDENCE = 0.22

def _is_likely_natural_warmth(color: dict) -> bool:
    """Sıcak cast'ın kasıtlı/doğal (golden hour, gün batımı) olup olmadığını tahmin eder."""
    cast = color.get("cast", "nötr")
    if "kırmızı" not in cast and "sıcak" not in cast:
        return False
    
    temp_k = color.get("temperature_k", 5600)
    sat    = color.get("saturation", 50)
    
    # 3500K altı ve doygunluğu yüksek görseller büyük ihtimalle gün batımı/doğumu karesidir.
    if temp_k <= 3500 and sat > 50:
        return True
        
    return False

def _sharpness_pattern(sharpness_map: dict, blur_type: dict) -> str:
    """Sharpness grid + blur_type'tan anlamlı ve fotoğrafçı dilinde yorum üretir."""
    btype = blur_type.get("type", "sharp")

    if btype in ("motion", "defocus"):
        return blur_type.get("description", "")

    grid = sharpness_map.get("grid", [])
    if not grid:
        return ""
        
    flat = [v for row in grid for v in row]
    if not flat:
        return ""
        
    mean = sum(flat) / len(flat)
    std  = (sum((x - mean) ** 2 for x in flat) / len(flat)) ** 0.5
    max_v = max(flat)

    if mean < 15 and std < 10:
        return "Görsel genelinde ciddi bir keskinlik kaybı ve yumuşama (softness) hakim."
    if std > 28 and max_v > 65:
        return "Görselde yüksek kontrastlı bir keskinlik dağılımı var (Kasıtlı bokeh veya sığ alan derinliği etkisi)."
        
    return ""

def generate_verdict(
    overall:        float | None,
    profile_result: dict,
    fast:           dict,
    histogram:      dict,
    color:          dict,
    exif:           dict,
    iqa_metrics:    dict,
    geometry:       dict | None = None,
    sharpness_map:  dict | None = None,
    blur_type:      dict | None = None,
    color_noise:    dict | None = None,
) -> str:
    if overall is None:
        return "Yeterli veri bulunmadığından genel bir kalite değerlendirmesi yapılamadı."

    parts: list[str] = []

    # ── 1. Profil ve Giriş (Overall Skoru girişte verip konuyu kapatıyoruz) ──
    pid = profile_result.get("profile_id", "none")
    profile_text = f" ({profile_result.get('profile_label', '')} profili)" if pid != "none" else ""
    
    if overall >= 80:
        parts.append(f"Görsel {overall:.1f}/100 kalite skoruyla{profile_text} yüksek standartları karşılıyor.")
    elif overall >= 60:
        parts.append(f"Görsel {overall:.1f}/100 kalite skoruyla{profile_text} genel olarak kabul edilebilir seviyede, ancak bazı pürüzler barındırıyor.")
    else:
        parts.append(f"Görsel {overall:.1f}/100 skoruyla{profile_text} teknik veya estetik açıdan yayın standartlarının altında kalıyor.")

    # ── 2. Geometri (En net ve acil düzeltme gerektiren sorunlar) ──
    if geometry:
        tilt = geometry.get("tilt", {})
        if tilt.get("is_tilted") and tilt.get("confidence", 0) >= 0.65:
            ang = tilt.get("label", "bir miktar")
            sev = tilt.get("severity", "")
            action = "kırpma/döndürme elzem" if sev == "Ciddi" else "ufuk çizgisi düzeltmesi önerilir"
            parts.append(f"Geometrik olarak ufuk çizgisinde {ang} eğiklik tespit edildi ({action}).")

    # ── 3. Işık ve Pozlama ──
    hl = histogram.get("highlight_clip_pct", 0)
    sh = histogram.get("shadow_clip_pct", 0)

    if hl > 5:
        parts.append(f"Aşırı parlak bölgelerde (highlight) %{hl:.1f} oranında kırpılma/detay kaybı var.")
    elif sh > 5:
        parts.append(f"Karanlık bölgelerde (shadow) %{sh:.1f} oranında tamamen kararma mevcut, fill-light gerekebilir.")

    # ── 4. Renk Bilimi ──
    cast = color.get("cast", "nötr")
    cs   = color.get("cast_strength", 0)
    sat  = color.get("saturation", 50)

    if cast != "nötr" and cs > 0.15:
        if _is_likely_natural_warmth(color):
            parts.append("Çekim koşullarıyla uyumlu, doğal ve estetik bir sıcak renk tonlaması seziliyor.")
        else:
            parts.append(f"Görselde belirgin bir {cast} renk sapması var, beyaz dengesi (WB) düzeltmesi önerilir.")
            
    if sat < 18:
        parts.append("Renk doygunluğu zayıf, genel yapı soluk hissettiriyor.")
    elif sat > 88:
        parts.append("Aşırı doygun renkler (oversaturation) görseli yapaylaştırmış.")

    # ── 5. Odak, Netlik ve EXIF Dinamikleri ──
    sp = _sharpness_pattern(sharpness_map or {}, blur_type or {})
    if sp:
        parts.append(sp)

    iso = exif.get("iso")
    if iso and iso > 1600:
        noise_risk = "kaçınılmaz" if iso > 6400 else "belirgin" if iso > 3200 else "olası"
        parts.append(f"Kullanılan yüksek ISO ({iso}) değeri nedeniyle {noise_risk} gren (noise) gözlemleniyor.")

    sv  = exif.get("shutter_value")
    flv = exif.get("focal_length_value")
    if sv and flv and sv > (1.0 / flv * 2.5):
        parts.append(f"Enstantane hızı ({exif.get('shutter','')}), elde çekim için kritik sınırda; mikro-titreşim (motion blur) riski yaratmış olabilir.")

    # ── 6. Yapay Zeka IQA Özeti (Dinamik Aralık Tespiti) ──
    good_m, bad_m = [], []
    for m, r in iqa_metrics.items():
        if r.get("status") != "ok" or m not in IQA_METRICS:
            continue
            
        meta = IQA_METRICS[m]
        s = r["score"]
        glo, ghi = meta["good_range"]
        wlo, whi = meta["warn_range"]
        
        # Basit tier sınıflandırması
        if meta["direction"] == "higher":
            if s >= glo: good_m.append(meta["label"])
            elif s < wlo: bad_m.append(meta["label"])
        else:
            if s <= ghi: good_m.append(meta["label"])
            elif s > whi: bad_m.append(meta["label"])

    if good_m and len(good_m) >= len(iqa_metrics) * 0.6:
        parts.append("Yapay zeka modellerinin genel algısal ve estetik kalite değerlendirmesi pozitif yönde.")
    elif bad_m:
        lbls = ", ".join(bad_m[:3])
        parts.append(f"Bazı yapay zeka metrikleri ({lbls}) teknik bozulma veya estetik yetersizlik konusunda uyarı veriyor.")

    return " ".join(parts)