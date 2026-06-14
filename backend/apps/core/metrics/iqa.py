"""
pyiqa ML metrik motoru.

Özellikler:
  - Thread-safe model cache (bir kez yükle, hep kullan)
  - MD5 tabanlı sonuç cache (aynı görsel → cache hit, model çalışmaz)
  - Ağırlıklı overall skor (MUSIQ/HyperIQA/DBCNN > NIQE/PI)
  - run_single_metric() → SSE streaming için
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from typing import Any
import time
import torch
import pyiqa
import gc
from core.config import IQA_METRICS, METRIC_WEIGHTS

# ── Cihaz ────────────────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Model cache ───────────────────────────────────────────────
_model_cache: dict[str, Any] = {}
_model_lock   = threading.Lock()

# ── Sonuç cache (MD5 → metrik sonuçları) ─────────────────────
_RESULT_CACHE_MAX = 64
_result_cache: OrderedDict[str, dict] = OrderedDict()
_cache_lock = threading.Lock()


def get_model(name: str):
    with _model_lock:
        if name not in _model_cache:
            _model_cache[name] = pyiqa.create_metric(name, device=DEVICE)
        return _model_cache[name]


# ── Yardımcılar ───────────────────────────────────────────────

def quality_label(score: float, meta: dict) -> str:
    """'iyi' | 'orta' | 'zayıf'"""
    glo, ghi = meta["good_range"]
    wlo, whi = meta["warn_range"]
    if meta["direction"] == "higher":
        if score >= glo: return "iyi"
        if score >= wlo: return "orta"
        return "zayıf"
    else:
        if score <= ghi: return "iyi"
        if score <= whi: return "orta"
        return "zayıf"


def _image_hash(tmp_path: str) -> str:
    """MD5 of first 512 KB — hızlı ama yeterince özgün."""
    h = hashlib.md5()
    with open(tmp_path, "rb") as f:
        h.update(f.read(524_288))
    return h.hexdigest()


def _cache_key(img_hash: str, selected: list[str]) -> str:
    return f"{img_hash}:{','.join(sorted(selected))}"


def _cache_get(key: str) -> dict | None:
    with _cache_lock:
        if key in _result_cache:
            _result_cache.move_to_end(key)   # LRU
            return _result_cache[key]
    return None


def _cache_put(key: str, value: dict) -> None:
    with _cache_lock:
        if len(_result_cache) >= _RESULT_CACHE_MAX:
            _result_cache.popitem(last=False)  # drop oldest
        _result_cache[key] = value


# ── Tek metrik çalıştır ───────────────────────────────────────

def run_single_metric(name: str, tmp_path: str) -> dict:
    """RAM'i korumak için modeli anlık yükler, çalıştırır ve tamamen siler."""
    t0 = time.time()
    try:
        # 1. Modeli sadece bu işlem için geçici olarak yükle
        device = torch.device("cpu")
        model = pyiqa.create_metric(name, device=device)
        model.eval()

        # 2. Sadece çıkarım yap (Hafıza ağacı oluşturma)
        with torch.inference_mode(), torch.no_grad():
            score_tensor = model(tmp_path)
            score = score_tensor.item()

        # 3. NÜKLEER TEMİZLİK: Tensörü ve Modeli RAM'den tamamen sil
        del score_tensor
        del model
        
        # 4. PyTorch'un işletim sistemine RAM'i iade etmesini zorla
        gc.collect()

        return {
            "score":      round(score, 4),
            "elapsed_ms": round((time.time() - t0) * 1000),
            "status":     "ok",
            # "label":      quality_label(score, IQA_METRICS[name]), # Eğer tanımlıysa açın
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── Toplu metrik çalıştır ─────────────────────────────────────

def run_iqa_metrics(tmp_path: str, selected: list[str]) -> dict:
    """
    Seçili metrikleri sırayla çalıştır.
    Aynı görsel daha önce analiz edildiyse cache'den döner.
    """
    try:
        img_hash = _image_hash(tmp_path)
        key      = _cache_key(img_hash, selected)
        cached   = _cache_get(key)
        if cached is not None:
            return cached
    except Exception:
        key = None

    results: dict = {}
    for name in selected:
        results[name] = run_single_metric(name, tmp_path)

    if key:
        _cache_put(key, results)
    return results


# ── Ağırlıklı genel skor ─────────────────────────────────────

def compute_overall(iqa_results: dict) -> float | None:
    """
    Tier tabanlı, sürekli ve ağırlıklı normalize skor hesaplayıcı:
      'iyi'   -> [0.75, 1.00]
      'orta'  -> [0.40, 0.75]
      'zayıf' -> [0.00, 0.40] (Sabit 0.15 yerine dinamik düşüş)
    """
    weighted_sum = 0.0
    weight_total = 0.0

    for name, res in iqa_results.items():
        if res.get("status") != "ok":
            continue
            
        meta = IQA_METRICS.get(name)
        if not meta:
            continue

        s = res["score"]
        # Range açılımları: good_range [lo, hi] | warn_range [wlo, whi]
        # Higher is better için: warn_range = [40, 70], good_range = [70, 100]
        # Lower is better için: good_range = [0, 30], warn_range = [30, 50]
        glo, ghi = meta["good_range"]
        wlo, whi = meta["warn_range"]
        direction = meta["direction"]
        w = METRIC_WEIGHTS.get(name, 1.0)
        
        n = 0.0 # Normalize edilmiş alt skor

        if direction == "higher":
            if s >= glo: # İyi
                frac = (s - glo) / max(ghi - glo, 1e-6)
                n = 0.75 + 0.25 * min(1.0, max(0.0, frac))
            elif s >= wlo: # Orta
                frac = (s - wlo) / max(glo - wlo, 1e-6)
                n = 0.40 + 0.35 * frac
            else: # Zayıf (0'a doğru lineer düşüş)
                frac = s / max(wlo, 1e-6)
                n = 0.40 * max(0.0, frac)

        elif direction == "lower":
            if s <= ghi: # İyi
                frac = (ghi - s) / max(ghi - glo, 1e-6)
                n = 0.75 + 0.25 * min(1.0, max(0.0, frac))
            elif s <= whi: # Orta
                frac = (whi - s) / max(whi - ghi, 1e-6)
                n = 0.40 + 0.35 * frac
            else: # Zayıf (Sonsuza veya max tahmini kötüye doğru düşüş)
                # Kötü skor warn_hi'ı ne kadar geçtiyse puan o kadar düşer (örn: 1.5x tolerans)
                max_bad = whi * 1.5 
                frac = max(0.0, max_bad - s) / max(max_bad - whi, 1e-6)
                n = 0.40 * frac

        weighted_sum += n * w
        weight_total += w

    if weight_total < 1e-6:
        return None
        
    return round((weighted_sum / weight_total) * 100, 1)


def device_str() -> str:
    return str(DEVICE)
