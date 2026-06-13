"""
TrueFrame Model Warmup — Tüm IQA model ağırlıklarını önceden indir.

Kullanım (tek seferlik, ilk kurulumda):
    docker-compose run --rm backend python warmup.py

Bu script:
  - 7 pyiqa metriğini (MUSIQ, TOPIQ, HyperIQA, DBCNN, PAQ2PIQ, BRISQUE, NIQE) indirir
  - Modelleri /app/.cache/ altına kaydeder (docker-compose.yml'deki model_cache volume)
  - Sonraki docker-compose up çalıştırmalarında modeller hazır gelir, bekleme olmaz

Not: İlk indirme ~2–4 GB veri gerektirir. İnternet bağlantısı zorunlu.
"""

import os, sys, time

# Cache dizinlerini zorla — Dockerfile ENV ile aynı olmalı
os.environ.setdefault("HOME",               "/app")
os.environ.setdefault("HF_HOME",            "/app/.cache/huggingface")
os.environ.setdefault("TRANSFORMERS_CACHE", "/app/.cache/huggingface")
os.environ.setdefault("TORCH_HOME",         "/app/.cache/torch")
os.environ.setdefault("PYIQA_CACHE",        "/app/.cache/pyiqa")

# ── PyIQA Metrikleri ──────────────────────────────────────────
METRICS = [
    "musiq",
    "topiq_nr",
    "hyperiqa",
    "dbcnn",
    "paq2piq",
    "brisque",
    "niqe",
]

def bar(pct, width=30):
    filled = int(width * pct)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {int(pct*100)}%"

def main():
    print("=" * 60)
    print("  TrueFrame Model Warmup")
    print("=" * 60)
    print()

    try:
        import torch
        import pyiqa
        device = torch.device("cpu")
        print(f"  PyTorch  : {torch.__version__}")
        print(f"  Device   : {device}")
        print(f"  Cache    : {os.environ['TORCH_HOME']}")
        print()
    except ImportError as e:
        print(f"HATA: Gerekli paket eksik — {e}")
        print("  'pip install -r requirements.txt' ile bağımlılıkları kur.")
        sys.exit(1)

    ok, fail = [], []
    total = len(METRICS)

    for i, name in enumerate(METRICS, 1):
        pct = (i - 1) / total
        print(f"  {bar(pct)}  [{i}/{total}] {name} indiriliyor...", end="", flush=True)
        t0 = time.time()
        try:
            pyiqa.create_metric(name, device=device)
            elapsed = time.time() - t0
            print(f"\r  {bar(i/total)}  [{i}/{total}] {name:<12} ✓  ({elapsed:.1f}s)")
            ok.append(name)
        except Exception as e:
            elapsed = time.time() - t0
            print(f"\r  {bar(i/total)}  [{i}/{total}] {name:<12} ✗  {e}")
            fail.append((name, str(e)))

    print()
    print("=" * 60)
    print(f"  Tamamlandı: {len(ok)}/{total} model hazır")
    if fail:
        print(f"  Başarısız : {len(fail)} model")
        for n, err in fail:
            print(f"    - {n}: {err}")
        print()
        print("  İpucu: İnternet bağlantısını kontrol et ve tekrar çalıştır.")
        sys.exit(1)
    else:
        print()
        print("  Tüm modeller hazır. Artık docker-compose up çalıştırabilirsin.")
        print("=" * 60)

if __name__ == "__main__":
    main()
