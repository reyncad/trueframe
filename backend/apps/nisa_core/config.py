"""
Tüm sabitler tek yerde — Optimize edilmiş, gerçek dünya uyumlu IQA metrik tanımları ve sistem ayarları.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────
#  IQA Metric definitions - Modern & Yalın Sürüm
# ─────────────────────────────────────────────────────────────
IQA_METRICS: dict[str, dict] = {
    # --- 1. Algısal (Derin Öğrenme & SOTA) ---
    "musiq": {
        "label": "MUSIQ", "full": "Multi-Scale Image Quality Transformer",
        "direction": "higher", "good_range": [70, 100], "warn_range": [40, 70],
        "category": "Algısal", "icon": "👁",
        "description": "Sistemin omurgası. Google'ın çok-ölçekli transformer'ı — MOS korelasyonu en yüksek.",
    },
    "topiq_nr": {
        "label": "TOPIQ", "full": "Top-down Perceptual IQA",
        "direction": "higher", "good_range": [0.65, 1.0], "warn_range": [0.40, 0.65],
        "category": "Algısal", "icon": "🏆",
        "description": "Üst-aşağı algısal dikkat mekanizmalı modern IQA modeli.",
    },
    "hyperiqa": {
        "label": "HyperIQA", "full": "Hypernetwork-based IQA",
        "direction": "higher", "good_range": [0.65, 1.0], "warn_range": [0.40, 0.65],
        "category": "Algısal", "icon": "⚡",
        "description": "İçerik bağımlı kalite ağırlıkları üreten hiper-ağ.",
    },
    "dbcnn": {
        "label": "DBCNN", "full": "Deep Bilinear CNN",
        "direction": "higher", "good_range": [0.65, 1.0], "warn_range": [0.40, 0.65],
        "category": "Algısal", "icon": "🔀",
        "description": "Sentetik ve otantik (gerçek dünya) bozulmaları birleştiren çift-lineer CNN.",
    },
    "paq2piq": {
        "label": "PAQ2PIQ", "full": "Patch Quality to Image Quality",
        "direction": "higher", "good_range": [60, 100], "warn_range": [40, 60],
        "category": "Algısal", "icon": "🔭",
        "description": "Yama düzeyinden globale algısal kalite. (Keskinlik değil, genel kalitedir).",
    },

    # clip_iqa: pyiqa>=0.1.13 gerektirir; mevcut sürümde desteklenmiyor.
    # Yüklü pyiqa sürümü bu metriği sağlamıyorsa startup'ta uyarı verilir ve atlanır.
    # Destek eklendiğinde aşağıdaki bloğun yorumunu kaldırın:
    # "clip_iqa": {
    #     "label": "CLIP-IQA", "full": "CLIP-based Image Quality Assessment",
    #     "direction": "higher", "good_range": [0.7, 1.0], "warn_range": [0.4, 0.7],
    #     "category": "Estetik", "icon": "🎨",
    #     "description": "CLIP modeliyle semantik estetik ve kalite değerlendirmesi.",
    # },

    # --- 2. Bozulma ve Doğallık (Geleneksel / İstatistiksel) ---
    "brisque": {
        "label": "BRISQUE", "full": "Blind/Referenceless Image Spatial Quality Evaluator",
        "direction": "lower", "good_range": [0, 30], "warn_range": [30, 50],
        "category": "Bozulma", "icon": "📐",
        "description": "Uzamsal bozulmalar. Gerçek dünya (mobil) için eşikler esnetildi.",
    },
    "niqe": {
        "label": "NIQE", "full": "Natural Image Quality Evaluator",
        "direction": "lower", "good_range": [0, 5], "warn_range": [5, 8],
        "category": "Doğallık", "icon": "🌿",
        "description": "Doğal sahne istatistiklerinden sapma.",
    },

}

# Kategori → renk (frontend ile senkron)
CATEGORY_COLORS: dict[str, str] = {
    "Algısal":  "#b040f0",
    "Estetik":  "#f040b0",
    "Bozulma":  "#f07040",
    "Doğallık": "#40c8f0",
    "Keskinlik": "#40f0c8",
}

# Sharpness map grid boyutu
SHARP_GRID_ROWS = 8
SHARP_GRID_COLS = 10

# ─────────────────────────────────────────────────────────────
#  Metrik ağırlıkları — Gerçek dünya ve algısal tutarlılık öncelikli.
# ─────────────────────────────────────────────────────────────
METRIC_WEIGHTS: dict[str, float] = {
    # Ağır Toplar (Modern mimariler, yüksek MOS korelasyonu)
    "musiq":    2.0,   
    "topiq_nr": 1.8,   
    
    # Güçlü Destekçiler
    "hyperiqa": 1.5,   
    "dbcnn":    1.5,   
    
    # Pratik ve Semantik Değerlendiriciler
    # "clip_iqa": 1.3,   # Devre dışı — pyiqa sürüm uyumsuzluğu
    "paq2piq":  1.2,
    
    # İstatistiksel / Legacy (Eski nesil, ağırlıkları düşürüldü)
    "brisque":  0.8,   
    "niqe":     0.5,   
}

# ─────────────────────────────────────────────────────────────
#  Hard-Reject Kuralları (Model skorlarını ezen mutlak doğrular)
# ─────────────────────────────────────────────────────────────
# Eğiklik toleransları (derece)
TILT_WARN_DEG  = 1.5   # Bu üzerinde uyarı
TILT_FAIL_DEG  = 3.0   # Bu üzerinde "eğik" sayılır (Skor ne olursa olsun estetik fail)

# Moire tespit eşiği
MOIRE_WARN_SCORE = 18
MOIRE_FAIL_SCORE = 35