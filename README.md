# TrueFrame

AI destekli görsel doğrulama ve kalite analizi platformu.

Bir görsel yükleyin — TrueFrame görselin **gerçek mi, yapay zeka üretimi mi, yoksa manipüle mi edildiğini** tespit eder; aynı anda 7 bağımsız IQA metriği ile profesyonel kalite analizi yapar.

---

## Özellikler

- **AI Tespiti** — CLIP + FFT çift-dal mimarisi (TrueFrameV2), %96.8 doğrulama hassasiyeti
- **Manipülasyon Tespiti** — Yüz değiştirme, arka plan swap, AI retouche ayrımı
- **5 Tespit Kategorisi** — KESİNLİKLE GERÇEK / MUHTEMELEN GERÇEK / MANİPÜLE / MUHTEMELEN YAPAY / KESİNLİKLE YAPAY
- **7 IQA Metriği** — MUSIQ, TOPIQ, HyperIQA, DBCNN, PAQ2PIQ, BRISQUE, NIQE
- **6D Kalite Radar** — Keskinlik, Gürültü, Pozlama, Renk, Estetik, Teknik
- **Kalite Profilleri** — Web, Sosyal Medya, Baskı, Haber iş akışları için özelleşmiş eşikler
- **HTML Rapor** — Yazdırılabilir, PDF'e dönüştürülebilir detaylı analiz raporu
- **Analiz Geçmişi** — Kayıtlı kullanıcılar için tüm analizlerin arşivi
- **Misafir Modu** — Kayıt gerektirmeden 5 analiz hakkı

---

## Mimari

```
┌───────────────────────────────────────────┐
│  Tarayıcı                                 │
│  ASP.NET Core MVC  :8080                  │
└──────────────┬────────────────────────────┘
               │  HTTP · X-TrueFrame-Key
               ▼
┌───────────────────────────────────────────┐
│  Django REST API  :8000  (iç ağ)          │
│  /api/analyze  /api/history  /api/report  │
└────────┬──────────────────┬───────────────┘
         │                  │
   ┌─────▼──────┐    ┌──────▼──────────────┐
   │ TrueFrame  │    │  IQA Motoru         │
   │ V2 (ONNX)  │    │  pyiqa · 7 metrik   │
   │ + Manip.   │    │  6D radar skoru     │
   └────────────┘    └─────────────────────┘
```

### Model Yükleme Sırası (Fallback Zinciri)

```
TrueFrameV2 ONNX  →  TrueFrameV2 PyTorch  →  HuggingFace v1 (dima806)
```

---

## Klasör Yapısı

```
TrueFrame/
├── backend/
│   ├── apps/
│   │   ├── detection/         # AI tespit servisi (ONNX + PyTorch + manipülasyon)
│   │   └── nisa_core/         # IQA metrikleri, analiz orkestratörü, DB, raporlama
│   │       └── metrics/       # blur, renk, geometri, histogram, sharpness_map, …
│   ├── detector/              # Django views, URL routing
│   ├── models/                # Model ağırlıkları (git'e dahil değil)
│   │   └── trueframe_v2/      # model.onnx · model.pt · config.json
│   ├── trueframe/             # Django ayarları
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── Controllers/           # Auth, Analysis, Home
│   ├── Services/              # PasswordHasher (PBKDF2), UserStore
│   ├── Views/
│   │   ├── Auth/              # Login, Register
│   │   └── Analysis/          # Upload, Result, History, Details
│   ├── Dockerfile
│   └── Program.cs
├── training/                  # Eğitim betikleri (Docker imajına dahil değildir)
│   ├── train_v2.py            # CLIP + FFT mimarisi, 6 epoch
│   ├── fine_tune.py
│   ├── evaluate.py
│   ├── export_onnx.py
│   ├── prepare_v2_data.py
│   └── download_dataset_v2.py
├── tests/
│   └── test_bugs.py           # Kritik regression testleri
├── docs/
│   └── ARCHITECTURE.md
├── docker-compose.yml
├── docker-compose.override.yml  # Geliştirme ortamı
└── .env.example
```

---

## Kurulum

### Gereksinimler

| Gereksinim | Notlar |
|---|---|
| Docker Desktop | Sürüm 24+ |
| Docker Belleği | **En az 4 GB** (Docker → Settings → Resources → Memory) |
| Model dosyaları | `backend/models/trueframe_v2/` altında `model.onnx` veya `model.pt` |

> **Düşük RAM (< 4 GB):** `docker-compose.override.yml` dosyasında `DISABLE_MANIP_DETECTOR: "true"` zaten açık. Bu ~500 MB tasarruf sağlar. 2 GB ile çalıştırmak için yeterli değilse pyiqa metrik sayısını `config.py`'den azaltın.

### 1. Ortam değişkenlerini ayarlayın

```bash
cp .env.example .env
```

`.env` dosyasını açıp doldurun:

```env
DJANGO_SECRET_KEY=<en az 50 karakter rastgele string>
TRUEFRAME_API_KEY=<frontend-backend arası iç API anahtarı>
SESSION_KEY=<en az 32 karakter>
```

Üretmek için:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Model ağırlıklarını yerleştirin

```
backend/models/trueframe_v2/
├── model.onnx      ← tercih edilen (daha hızlı)
├── model.pt        ← ONNX yoksa kullanılır
└── config.json     ← mimari ve eğitim meta verisi
```

ONNX veya PyTorch dosyalarından biri yeterlidir. İkisi de yoksa sistem HuggingFace'ten `dima806/ai_vs_real_image_detection` modelini otomatik indirir (internet bağlantısı gerekir, ~1 GB).

### 3. Docker ile başlatın

**Geliştirme** (hot reload, backend portu açık):
```bash
docker compose up --build
```

**Production** (Gunicorn, `--preload` ile tek model yükleme):
```bash
docker compose -f docker-compose.yml up --build
```

Uygulama `http://localhost:8080` adresinde hazır olur.

İlk çalıştırmada modeller HuggingFace'ten indirilir — başlangıç **3–10 dakika** sürebilir. Sonraki başlangıçlar cache sayesinde ~30 saniyedir.

---

## Ortam Değişkenleri

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `DJANGO_SECRET_KEY` | ✅ | Django secret key |
| `TRUEFRAME_API_KEY` | ✅ | Frontend → Backend iç API anahtarı |
| `SESSION_KEY` | ✅ | ASP.NET session şifreleme anahtarı (min 32 karakter) |
| `EXTRA_ALLOWED_HOSTS` | — | Ek Django allowed hosts (virgülle ayrılmış) |
| `DJANGO_DEBUG` | — | `true` yalnızca geliştirme ortamında |
| `DISABLE_MANIP_DETECTOR` | — | `true` → manipülasyon dedektörü devre dışı (~500 MB tasarruf) |
| `GUNICORN_WORKERS` | — | Production worker sayısı (varsayılan `1`, yüksek yük için `2`) |
| `HF_TOKEN` | — | HuggingFace token; rate limit uyarısını giderir, indirmeyi hızlandırır |

---

## API

Tüm endpoint'ler `X-TrueFrame-Key` başlığı gerektirir.

### `POST /api/analyze`

Görsel analizi — AI tespiti + kalite metrikleri.

```
Content-Type: multipart/form-data
X-TrueFrame-Key: <TRUEFRAME_API_KEY>

image   : dosya  (JPEG · PNG · WebP · TIFF · BMP, maks 5 MB)
profile : string (none · web · social · print · news)
```

**Yanıt:**

```json
{
  "label": "MUHTEMELEN GERÇEK",
  "is_ai_generated": false,
  "confidence": 78.4,
  "real_prob": 78.4,
  "fake_prob": 21.6,
  "is_manipulated": false,
  "manip_score": 12.3,
  "quality": {
    "quality_score": 81.5,
    "verdict": "...",
    "dimensions": { "keskinlik": 88, "gurultu": 74, ... },
    "iqa_metrics": [ { "label": "MUSIQ", "score": 76.2, ... } ],
    "checks": [ { "name": "Çözünürlük", "passed": true, ... } ]
  }
}
```

### `GET /api/history`

Son 30 analiz kaydı (thumbnail dahil).

### `GET /api/history/<id>`

Tekil analiz kaydının tam JSON yanıtı.

### `GET /api/report/<id>`

Tarayıcıda açılan, yazdırılabilir HTML rapor. Ctrl+P → PDF olarak kaydedilebilir.

### `GET /health/`

`{"status": "ok"}` — Docker healthcheck endpoint.

---

## Kalite Profilleri

| Profil | `profile` değeri | Kontrol Kriterleri |
|---|---|---|
| Genel (varsayılan) | `none` | Profil kontrolü yapılmaz |
| Web / Blog | `web` | Çözünürlük, keskinlik, highlight kırpılması |
| Sosyal Medya | `social` | Kare oran, keskinlik, pozlama |
| Baskı | `print` | Megapiksel (min 8 MP), keskinlik, gürültü |
| Haber | `news` | Çözünürlük, horizon eğikliği, keskinlik |

---

## IQA Metrikleri

| Metrik | Tür | Yön | Açıklama |
|---|---|---|---|
| MUSIQ | Algısal | ↑ yüksek iyi | Multi-scale transformer, en yüksek MOS korelasyonu |
| TOPIQ | Algısal | ↑ | Üst-aşağı dikkat mekanizmalı modern IQA |
| HyperIQA | Algısal | ↑ | İçerik bağımlı hiper-ağ |
| DBCNN | Algısal | ↑ | Sentetik + gerçek dünya bozulmaları |
| PAQ2PIQ | Algısal | ↑ | Yama düzeyinden global kalite |
| BRISQUE | Bozulma | ↓ düşük iyi | Uzamsal bozulma ölçümü |
| NIQE | Doğallık | ↓ | Doğal görüntü istatistiklerinden sapma |

---

## Güvenlik

- **Şifre** — PBKDF2-SHA256, 100.000 iterasyon, 16-byte salt; eski SHA-256 hash'ler ilk girişte otomatik yükseltilir
- **CSRF** — Tüm POST endpoint'lerinde `AutoValidateAntiforgeryToken`
- **Session Fixation** — Login öncesi `Session.Clear()`
- **MIME Sniffing** — `python-magic` ile gerçek dosya tipi doğrulaması (header manipülasyonuna karşı)
- **DataProtection** — Key'ler `dp_keys` volume'unda kalıcı; container rebuild sonrası session geçerliliği korunur
- **İç API** — `X-TrueFrame-Key` header doğrulaması; backend portu dışarıya açılmaz
- **Docker** — Her iki container non-root (`appuser:appgroup`) çalışır
- **Session Cookie** — `HttpOnly`, `Strict SameSite`, production'da `Secure`
- **Güvenlik Header'ları** — `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`

---

## Geliştirme

```bash
# Sadece backend yeniden build:
docker compose up --build backend

# Log takibi:
docker compose logs -f backend
docker compose logs -f frontend

# Backend kabuğu:
docker compose exec backend bash

# Regression testleri:
cd tests && python test_bugs.py
```

### Geliştirme Notu: Model Yükleme

Backend başlarken modeller arka planda sırayla yüklenir (`apps.py` warmup thread). `POST /api/analyze` ilk isteği bu süreç tamamlanana kadar bekler (maks 60 saniye). Bu tasarım, eşzamanlı model yüklemesinden kaynaklanan bellek spike'larını (OOM) önler.

---

## Eğitim

`training/` klasörü Docker imajına dahil edilmez.

```
training/
├── train_v2.py          # TrueFrameV2 (CLIP + FFT), 6 epoch, val_acc: %96.8
├── fine_tune.py         # Mevcut modeli yeni veriyle ince ayar
├── evaluate.py          # Test seti değerlendirme
├── export_onnx.py       # PyTorch → ONNX dönüşümü
├── prepare_v2_data.py   # Veri hazırlama
└── download_dataset_v2.py
```

Eğitim sonrası üretilen `.onnx` dosyasını `backend/models/trueframe_v2/` altına kopyalayın ve konteynerleri yeniden başlatın:

```bash
docker compose restart backend
```

---

## Bilinen Sınırlamalar

- Dosya boyutu limiti 5 MB — prodüksiyon RAW export'ları bu sınırı aşabilir
- Model doğrulama accuracy'si (%96.8) training validation setinden; bağımsız gerçek dünya benchmark'ı henüz yok
- `clip_iqa` metriği yüklü pyiqa sürümünde desteklenmiyor; mevcut sürümde devre dışı
- SQLite kullanımı — yüksek eşzamanlı yük için PostgreSQL önerilir
- Misafir analiz limiti session tabanlı; sunucu taraflı doğrulama yok
