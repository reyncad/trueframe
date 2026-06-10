"""
HTML rapor üretici.

/api/report/{id} endpoint'i tarayıcıda açılınca yazdırılabilir,
Ctrl+P → PDF olarak kaydedilebilir profesyonel rapor üretir.
"""

from __future__ import annotations

import html as _html
import math
import re as _re
from typing import Any

from core.config import IQA_METRICS


def _esc(val: Any) -> str:
    """Kullanıcı kontrollü değerleri HTML'e gömmeden önce escape et (XSS önlemi)."""
    return _html.escape(str(val)) if val is not None else ""


def _safe_filename(name: str) -> str:
    """JS string'ine gömülen dosya adından tehlikeli karakterleri ayıkla."""
    base = _re.sub(r"[^\w.\- ]", "", str(name)).strip().replace(" ", "_")
    return base or "rapor"


def _score_color(score: float) -> str:
    if score >= 75: return "#40f088"
    if score >= 55: return "#c8f040"
    if score >= 40: return "#f0c040"
    return "#f04060"


def _qual_label(score: float, meta: dict) -> str:
    glo, ghi = meta["good_range"]
    wlo, whi = meta.get("warn_range", [glo, ghi])
    if meta["direction"] == "higher":
        if score >= glo: return "İyi"
        if score >= wlo: return "Orta"
        return "Zayıf"
    else:
        if score <= ghi: return "İyi"
        if score <= whi: return "Orta"
        return "Zayıf"


def _radar_svg(dims: dict, size: int = 220) -> str:
    """6 boyutlu radar chart SVG."""
    labels = ["Keskinlik", "Gürültü", "Pozlama", "Renk", "Estetik", "Teknik"]
    keys   = ["keskinlik", "gurultu", "pozlama", "renk", "estetik", "teknik"]
    values = [dims.get(k, 50) / 100 for k in keys]
    n      = len(labels)
    cx, cy = size / 2, size / 2
    r_max  = size * 0.38
    r_mid  = r_max * 0.5

    def point(i: int, radius: float) -> tuple[float, float]:
        angle = math.pi / 2 - 2 * math.pi * i / n
        return cx + radius * math.cos(angle), cy - radius * math.sin(angle)

    # Background rings
    rings = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{point(i, r_max*frac)[0]:.1f},{point(i, r_max*frac)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#2a2a3a" stroke-width="1"/>'

    # Axis lines
    axes = ""
    for i in range(n):
        px, py = point(i, r_max)
        axes += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{px:.1f}" y2="{py:.1f}" stroke="#2a2a3a" stroke-width="1"/>'

    # Data polygon
    data_pts = " ".join(f"{point(i, r_max * values[i])[0]:.1f},{point(i, r_max * values[i])[1]:.1f}" for i in range(n))
    data = (
        f'<polygon points="{data_pts}" fill="rgba(200,240,64,0.15)" stroke="#c8f040" stroke-width="2"/>'
    )

    # Dots
    dots = ""
    for i, v in enumerate(values):
        px, py = point(i, r_max * v)
        col = _score_color(v * 100)
        dots += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{col}"/>'

    # Labels
    lbls = ""
    for i, lbl in enumerate(labels):
        px, py = point(i, r_max * 1.22)
        val = int(values[i] * 100)
        lbls += (
            f'<text x="{px:.1f}" y="{py:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="Space Mono,monospace" font-size="9" fill="#8080b0">{lbl}</text>'
            f'<text x="{px:.1f}" y="{py+13:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="Space Mono,monospace" font-size="10" font-weight="bold" fill="{_score_color(val)}">{val}</text>'
        )

    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">'
        f'{rings}{axes}{data}{dots}{lbls}</svg>'
    )


def _histogram_svg(hist: dict) -> str:
    r   = hist.get("hist_r", [])
    g   = hist.get("hist_g", [])
    b   = hist.get("hist_b", [])
    if not r:
        return "<p style='color:#666;font-size:11px'>Histogram verisi yok</p>"

    W, H   = 400, 80
    n      = len(r)
    max_v  = max(max(r, default=1), max(g, default=1), max(b, default=1), 1)
    step_w = W / n

    def polyline(data: list, color: str) -> str:
        pts = " ".join(f"{i*step_w:.1f},{H-(d/max_v*H):.1f}" for i, d in enumerate(data))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.85"/>'

    return (
        f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{W}" height="{H}" fill="#0e0e18" rx="4"/>'
        f'{polyline(r,"#f07070")}{polyline(g,"#70f070")}{polyline(b,"#7090f0")}'
        f'</svg>'
    )


def _check_icon(passed: bool | None) -> str:
    if passed is True:  return '<span style="color:#40f088">✓</span>'
    if passed is False: return '<span style="color:#f04060">✗</span>'
    return '<span style="color:#5a5a88">—</span>'


def render_html_report(data: dict[str, Any]) -> str:
    name     = _esc(data.get("name", "Görsel"))
    overall  = data.get("overall") or 0
    verdict  = _esc(data.get("verdict", "—"))
    profile  = data.get("profile_result", {})
    dims     = data.get("dimensions", {})
    exif     = data.get("exif", {})
    hist     = data.get("histogram", {})
    tech     = data.get("technical", {})
    iqa      = data.get("iqa_metrics", {})
    fast     = data.get("fast", {})
    geo      = data.get("geometry", {})
    blur_t   = data.get("blur_type", {})
    col      = data.get("color", {})
    cn       = data.get("color_noise", {})
    thumb    = data.get("thumbnail", "")

    # AI tespit alanları — api_response'un üst düzey alanları
    ai_label      = _esc(data.get("label", ""))
    ai_fake_prob  = data.get("fake_prob", 0) or 0
    ai_real_prob  = data.get("real_prob", 0) or 0
    ai_confidence = data.get("confidence", 0) or 0
    ai_manip      = data.get("is_manipulated", False)
    ai_manip_sc   = data.get("manip_score", 0) or 0
    ai_generated  = data.get("is_ai_generated", False)
    analysis_flags = data.get("analysis", {}) or {}
    has_ai_analysis = analysis_flags.get("ai", bool(ai_label))
    # Format edilmiş değerler (iç içe f-string'de :.1f kullanılamaz)
    _ai_fake_pct   = f"{ai_fake_prob  * 100:.1f}"
    _ai_real_pct   = f"{ai_real_prob  * 100:.1f}"
    _ai_conf_pct   = f"{ai_confidence * 100:.1f}"
    _ai_manip_pct  = f"{ai_manip_sc   * 100:.1f}"
    _ai_label_col  = "#f04060" if ai_generated else "#40f088"

    score_color = _score_color(overall)

    # Profile checks table
    # api_views.py "value" ve "needed" anahtarlarıyla gönderir;
    # profiles.py iç yapısı "display" ve "threshold_display" kullanır —
    # her iki kaynağı da tolere et.
    checks_html = ""
    for c in profile.get("checks", []):
        passed = c.get("passed")
        icon = _check_icon(passed)
        bg   = "#0f1a0f" if passed is True else "#1a0f0f" if passed is False else "transparent"
        val    = c.get("value") or c.get("display") or "—"
        needed = c.get("needed") or c.get("threshold_display") or c.get("threshold") or "—"
        checks_html += (
            f'<tr style="background:{bg}">'
            f'<td>{icon}</td>'
            f'<td>{_esc(c.get("name", ""))}</td>'
            f'<td style="color:#40efc8">{_esc(val)}</td>'
            f'<td style="color:#5a5a88">{_esc(needed)}</td>'
            f'</tr>'
        )

    # IQA metrics table — iki format desteklenir:
    # 1) API response / DB formatı: list[{label, score, direction, good_min, good_max, error}]
    # 2) Bundle formatı (legacy): dict[key, {score, status}]
    iqa_html = ""
    if isinstance(iqa, list):
        for item in iqa:
            score     = item.get("score")
            lbl       = _esc(item.get("label", "?"))
            direction = item.get("direction", "higher")
            good_min  = item.get("good_min", 0)
            good_max  = item.get("good_max", 1)
            err       = item.get("error")
            if err or score is None:
                iqa_html += f'<tr><td></td><td>{lbl}</td><td colspan="3" style="color:#f04060">Hata</td></tr>'
                continue
            if direction == "lower":
                ql = "İyi" if score <= good_max else "Orta" if score <= good_max * 1.25 else "Zayıf"
            else:
                ql = "İyi" if score >= good_min else "Orta" if score >= good_min * 0.75 else "Zayıf"
            qc = "#40f088" if ql == "İyi" else "#f0c040" if ql == "Orta" else "#f04060"
            dir_lbl = "▼ düşük iyi" if direction == "lower" else "▲ yüksek iyi"
            iqa_html += (
                f'<tr>'
                f'<td></td>'
                f'<td style="font-weight:700">{lbl}</td>'
                f'<td style="color:#40efc8;font-family:monospace">{score:.4f}</td>'
                f'<td style="color:{qc}">{ql}</td>'
                f'<td style="color:#5a5a88;font-size:10px">{dir_lbl}</td>'
                f'</tr>'
            )
    elif isinstance(iqa, dict):
        for k, r in iqa.items():
            meta = IQA_METRICS.get(k, {})
            if r.get("status") != "ok" or not meta:
                iqa_html += f'<tr><td>{meta.get("icon","")}</td><td>{meta.get("label",k)}</td><td colspan="3" style="color:#f04060">Hata</td></tr>'
                continue
            ql    = _qual_label(r["score"], meta)
            qc    = "#40f088" if ql=="İyi" else "#f0c040" if ql=="Orta" else "#f04060"
            iqa_html += (
                f'<tr>'
                f'<td>{meta.get("icon","")}</td>'
                f'<td style="font-weight:700">{meta.get("label",k)}</td>'
                f'<td style="color:#40efc8;font-family:monospace">{r["score"]:.4f}</td>'
                f'<td style="color:{qc}">{ql}</td>'
                f'<td style="color:#5a5a88;font-size:10px">{"▼ düşük iyi" if meta.get("direction")=="lower" else "▲ yüksek iyi"}</td>'
                f'</tr>'
            )

    # EXIF rows
    exif_pairs = [
        ("Kamera",         exif.get("camera")),
        ("Lens",           exif.get("lens")),
        ("ISO",            exif.get("iso")),
        ("Diyafram",       exif.get("aperture")),
        ("Enstantane",     exif.get("shutter")),
        ("Odak Uzunluğu",  exif.get("focal_length")),
        ("Tarih / Saat",   exif.get("datetime")),
    ]
    exif_html = "".join(
        f'<tr><td style="color:#5a5a88">{k}</td><td style="color:#40efc8">{_esc(v)}</td></tr>'
        for k, v in exif_pairs if v is not None and v != ""
    ) or '<tr><td colspan="2" style="color:#5a5a88">EXIF verisi bulunamadı</td></tr>'

    # Thumbnail
    thumb_html = (
        f'<img src="{thumb}" style="max-width:220px;max-height:160px;object-fit:contain;border-radius:6px;border:1px solid #2a2a3a"/>'
        if thumb else
        '<div style="width:220px;height:160px;background:#0e0e18;border-radius:6px;border:1px solid #2a2a3a;display:flex;align-items:center;justify-content:center;color:#3a3a5a">Önizleme yok</div>'
    )

    tilt  = geo.get("tilt", {})
    moire = geo.get("moire", {})

    created_at = data.get("created_at", "")

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8"/>
<title>IQA Rapor — {name}</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<style>
  .pdf-btn{{position:fixed;top:16px;right:16px;z-index:999;background:#c8f040;color:#08080f;border:none;padding:10px 20px;font-family:'Space Mono',monospace;font-size:12px;font-weight:700;border-radius:6px;cursor:pointer;letter-spacing:1px;box-shadow:0 2px 12px rgba(200,240,64,.3)}}
  .pdf-btn:hover{{background:#d8ff50}}
  .pdf-btn:disabled{{opacity:.5;cursor:wait}}
  @media print{{.pdf-btn{{display:none}}}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#08080f;color:#e4e4f0;font-family:'Syne',sans-serif;padding:32px;line-height:1.5}}
  .mono{{font-family:'Space Mono',monospace}}
  h1{{font-size:1.6rem;font-weight:800;letter-spacing:-0.5px}}
  h2{{font-size:1rem;font-weight:700;margin:24px 0 10px;padding-bottom:4px;border-bottom:1px solid #2a2a3a;color:#8080b0}}
  .header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px;padding-bottom:20px;border-bottom:2px solid #c8f040}}
  .score-big{{font-size:3.5rem;font-weight:800;line-height:1;color:{score_color};font-family:'Space Mono',monospace}}
  .verdict-box{{background:#0e0e18;border:1px solid #2a2a3a;border-left:3px solid #c8f040;padding:14px 18px;border-radius:6px;margin-bottom:20px;font-size:.88rem;line-height:1.7}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
  .grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  td{{padding:7px 10px;border-bottom:1px solid #1a1a28}}
  .dim-card{{background:#0e0e18;border:1px solid #2a2a3a;border-radius:6px;padding:12px;text-align:center}}
  .dim-val{{font-size:1.8rem;font-weight:800;font-family:'Space Mono',monospace}}
  .dim-label{{font-size:.7rem;color:#5a5a88;font-family:'Space Mono',monospace;letter-spacing:1px;text-transform:uppercase;margin-top:2px}}
  .section{{margin-bottom:24px}}
  .pill{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.75rem;font-family:'Space Mono',monospace;border:1px solid;margin:2px}}
  .footer{{margin-top:32px;padding-top:12px;border-top:1px solid #2a2a3a;font-size:.72rem;color:#3a3a5a;font-family:'Space Mono',monospace;display:flex;justify-content:space-between}}
  @media print{{body{{background:white;color:black}}}}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="mono" style="font-size:9px;letter-spacing:4px;color:#c8f040;text-transform:uppercase;margin-bottom:6px"> True Frame · Analiz Raporu</div>
    <h1>{name}</h1>
    <div class="mono" style="font-size:10px;color:#5a5a88;margin-top:4px">{created_at} · {tech.get("width","??")}×{tech.get("height","??")}px · {tech.get("megapixels","?")} MP</div>
  </div>
  <div style="text-align:right">
    {thumb_html}
  </div>
</div>

<div class="section" style="display:flex;gap:28px;align-items:center;margin-bottom:24px">
  <div>
    <div class="mono" style="font-size:9px;letter-spacing:2px;color:#5a5a88;text-transform:uppercase">Genel Kalite Skoru</div>
    <div class="score-big">{overall:.0f}<span style="font-size:1.4rem;color:#5a5a88">/100</span></div>
    <div class="mono" style="font-size:10px;color:#5a5a88;margin-top:4px">Profil: {profile.get("profile_label","Genel")} · {profile.get("passed","?")}/{profile.get("total","?")} kontrol geçildi</div>
  </div>
  {_radar_svg(dims, 220)}
</div>

{"" if not has_ai_analysis or not ai_label else f'''
<div class="section" style="margin-bottom:20px">
  <h2>AI / Sahte Tespit</h2>
  <div style="background:#0e0e18;border:1px solid #2a2a3a;border-radius:8px;padding:14px 18px;display:flex;flex-wrap:wrap;gap:24px;align-items:center">
    <div>
      <div class="mono" style="font-size:9px;letter-spacing:2px;color:#5a5a88;text-transform:uppercase">Tespit Sonucu</div>
      <div style="font-size:1.4rem;font-weight:800;color:{_ai_label_col};font-family:Space Mono,monospace">{ai_label}</div>
      <div class="mono" style="font-size:10px;color:#5a5a88;margin-top:2px">Güven: {_ai_conf_pct}%</div>
    </div>
    <div style="display:flex;gap:20px">
      <div style="text-align:center">
        <div class="mono" style="font-size:9px;color:#5a5a88;text-transform:uppercase">AI Olasılığı</div>
        <div style="font-size:1.5rem;font-weight:800;color:#f04060;font-family:Space Mono,monospace">{_ai_fake_pct}<span style="font-size:.8rem">%</span></div>
      </div>
      <div style="text-align:center">
        <div class="mono" style="font-size:9px;color:#5a5a88;text-transform:uppercase">Gerçek Olasılığı</div>
        <div style="font-size:1.5rem;font-weight:800;color:#40f088;font-family:Space Mono,monospace">{_ai_real_pct}<span style="font-size:.8rem">%</span></div>
      </div>
      {"" if not ai_manip else f"<div style='text-align:center'><div class='mono' style='font-size:9px;color:#5a5a88;text-transform:uppercase'>Manipülasyon</div><div style='font-size:1.5rem;font-weight:800;color:#f07040;font-family:Space Mono,monospace'>{_ai_manip_pct}<span style='font-size:.8rem'>%</span></div></div>"}
    </div>
    {"<div style='background:#1a0f0f;border:1px solid #f04060;border-radius:6px;padding:8px 14px;color:#f04060;font-size:.82rem'><strong>⚠ Manipülasyon Tespit Edildi</strong></div>" if ai_manip else ""}
  </div>
</div>
'''}

<div class="verdict-box">{verdict}</div>

<h2>6 Boyutlu Kalite Profili</h2>
<div class="grid3 section">
  {"".join(
    f'<div class="dim-card"><div class="dim-val" style="color:{_score_color(dims.get(k,50))}">{dims.get(k,50):.0f}</div><div class="dim-label">{lbl}</div></div>'
    for k, lbl in [("keskinlik","Keskinlik"),("gurultu","Gürültü"),("pozlama","Pozlama"),("renk","Renk"),("estetik","Estetik"),("teknik","Teknik")]
  )}
</div>

{"" if not profile.get("checks") else f'''
<h2>{profile.get("profile_label","Profil")} Kontrol Listesi</h2>
<div class="section">
  <table>
    <thead><tr><td></td><td><b>Kontrol</b></td><td><b>Değer</b></td><td><b>Gerekli</b></td></tr></thead>
    <tbody>{checks_html}</tbody>
  </table>
</div>
'''}

<div class="grid2">
  <div>
    <h2>Görsel Bilgisi</h2>
    <table>
      <tr><td style="color:#5a5a88">Çözünürlük</td><td style="color:#40efc8">{tech.get("width","?")}×{tech.get("height","?")} px</td></tr>
      <tr><td style="color:#5a5a88">Megapiksel</td><td style="color:#40efc8">{tech.get("megapixels","?")} MP</td></tr>
      <tr><td style="color:#5a5a88">Format</td><td style="color:#40efc8">{tech.get("format","?")}</td></tr>
      <tr><td style="color:#5a5a88">Renk Modu</td><td style="color:#40efc8">{tech.get("color_mode","?")}</td></tr>
      <tr><td style="color:#5a5a88">DPI (EXIF)</td><td style="color:#40efc8">{tech.get("dpi_x","—")}</td></tr>
    </table>

    <h2>EXIF Verisi</h2>
    <table><tbody>{exif_html}</tbody></table>
  </div>

  <div>
    <h2>Histogram</h2>
    <div class="section">{_histogram_svg(hist)}</div>
    <table>
      <tr><td style="color:#5a5a88">Pozlama</td><td style="color:#40efc8">{hist.get("exposure_label","—")}</td></tr>
      <tr><td style="color:#5a5a88">Highlight Kırpılması</td><td style="color:#f07070">{hist.get("highlight_clip_pct",0):.1f}%</td></tr>
      <tr><td style="color:#5a5a88">Shadow Kırpılması</td><td style="color:#7090f0">{hist.get("shadow_clip_pct",0):.1f}%</td></tr>
      <tr><td style="color:#5a5a88">Dinamik Aralık</td><td style="color:#40efc8">{hist.get("dynamic_range_score",0):.1f}/100</td></tr>
      <tr><td style="color:#5a5a88">Ort. Parlaklık</td><td style="color:#40efc8">{hist.get("mean_brightness",0):.0f}/255</td></tr>
    </table>

    <h2>Renk &amp; Gürültü</h2>
    <table>
      <tr><td style="color:#5a5a88">Renk Sıcaklığı</td><td style="color:#40efc8">{col.get("temperature_label","—")}</td></tr>
      <tr><td style="color:#5a5a88">Renk Tonu</td><td style="color:#40efc8">{col.get("cast","nötr")} ({col.get("cast_strength",0):.2f})</td></tr>
      <tr><td style="color:#5a5a88">Doygunluk</td><td style="color:#40efc8">{col.get("saturation",0):.1f}%</td></tr>
      <tr><td style="color:#5a5a88">Renk Gürültüsü</td><td style="color:#40efc8">{cn.get("severity","—")}</td></tr>
    </table>
  </div>
</div>

<h2>Geometri &amp; Blur Analizi</h2>
<div class="grid3 section">
  <div class="dim-card">
    <div class="dim-label">Blur Tipi</div>
    <div style="font-size:1.1rem;font-weight:700;margin:6px 0;color:{'#40f088' if blur_t.get('type')=='sharp' else '#f0c040'}">{blur_t.get("label","—")}</div>
    <div style="font-size:.72rem;color:#5a5a88">{blur_t.get("description","")}</div>
  </div>
  <div class="dim-card">
    <div class="dim-label">Horizon Eğikliği</div>
    <div style="font-size:1.1rem;font-weight:700;margin:6px 0;color:{'#f04060' if tilt.get('is_tilted') else '#40f088'}">{tilt.get("label","0°")}</div>
    <div style="font-size:.72rem;color:#5a5a88">{tilt.get("severity", tilt.get("label","Yok"))} · Güven: {(tilt.get("confidence") or 0):.0%}</div>
  </div>
  <div class="dim-card">
    <div class="dim-label">Moire Pattern</div>
    <div style="font-size:1.1rem;font-weight:700;margin:6px 0;color:{'#f04060' if moire.get('detected') else '#40f088'}">{moire.get("label", moire.get("severity","Yok"))}</div>
    <div style="font-size:.72rem;color:#5a5a88">Skor: {moire.get("score",0):.0f}/100</div>
  </div>
</div>

<h2>IQA Metrik Skorları</h2>
<div class="section">
  <table>
    <thead><tr><td></td><td><b>Metrik</b></td><td><b>Skor</b></td><td><b>Kalite</b></td><td><b>Yön</b></td></tr></thead>
    <tbody>{iqa_html}</tbody>
  </table>
</div>

<div class="footer">
  <span>NR-IQA Vision Lab · Lokal Analiz</span>
  <span>{created_at}</span>
</div>

<button class="pdf-btn" id="pdfBtn" onclick="downloadPdf()">⬇ PDF İndir</button>

<script>
function downloadPdf() {{
  const btn = document.getElementById('pdfBtn');
  btn.disabled = true;
  btn.textContent = 'Hazırlanıyor...';
  const opt = {{
    margin:      [8, 8, 8, 8],
    filename:    '{_safe_filename(data.get("name", "rapor"))}_iqa_rapor.pdf',
    image:       {{ type: 'jpeg', quality: 0.95 }},
    html2canvas: {{ scale: 2, useCORS: true, backgroundColor: '#08080f' }},
    jsPDF:       {{ unit: 'mm', format: 'a4', orientation: 'portrait' }},
    pagebreak:   {{ mode: ['avoid-all', 'css'] }},
  }};
  html2pdf().set(opt).from(document.body).save().then(() => {{
    btn.disabled = false;
    btn.textContent = '⬇ PDF İndir';
  }});
}}
</script>

</body>
</html>"""
