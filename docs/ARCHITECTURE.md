# TrueFrame — Mimari Belge

## İçindekiler

1. [Genel Bakış](#genel-bakış)
2. [Katman Diyagramı](#katman-diyagramı)
3. [Servisler](#servisler)
4. [Veri Akışı — Görsel Analizi](#veri-akışı--görsel-analizi)
5. [Veri Akışı — Kimlik Doğrulama](#veri-akışı--kimlik-doğrulama)
6. [Güvenlik Mimarisi](#güvenlik-mimarisi)
7. [Veritabanı Şeması](#veritabanı-şeması)
8. [Dosya Kalıcılığı ve Volumes](#dosya-kalıcılığı-ve-volumes)
9. [Risk Analizi](#risk-analizi)
10. [Karar Notları](#karar-notları)

---

## Genel Bakış

TrueFrame iki katmanlı bir web uygulamasıdır:

| Katman | Teknoloji | Sorumluluk |
|---|---|---|
| Frontend | ASP.NET Core MVC (.NET 10) | Kullanıcı arayüzü, oturum yönetimi, backend proxy |
| Backend | Django 4.2 + Gunicorn | ML model inference, görsel analizi, veri persistansı |

İki servis **Docker Compose** ile yönetilir. Backend dışarıya kapalıdır (port expose yok); sadece frontend iç ağ üzerinden erişir.

---

## Katman Diyagramı

```
┌───────────────────────────────────────────────────────────────────┐
│  Kullanıcı Tarayıcısı                                             │
└──────────────────────────────┬────────────────────────────────────┘
                               │  HTTPS  :8080
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  FRONTEND — ASP.NET Core MVC                                      │
│                                                                   │
│  Controllers/                                                     │
│    AuthController   → Kayıt, Giriş, Misafir                      │
│    AnalysisController → Upload, Result, History, Details          │
│    HomeController   → Ana sayfa                                   │
│                                                                   │
│  Services/                                                        │
│    PasswordHasher   → PBKDF2-SHA256 (100k iter)                   │
│    UserStore        → JSON tabanlı kullanıcı deposu               │
│                                                                   │
│  Models/                                                          │
│    AnalysisApiResponse  (DTO — backend JSON eşlemesi)             │
│    AnalysisViewModel    (View modeli)                             │
│    HistoryViewModel     (Geçmiş listesi)                          │
└──────────────────────────────┬────────────────────────────────────┘
                               │  HTTP  X-TrueFrame-Key
                               │  trueframe-net (Docker internal)
                               ▼
┌───────────────────────────────────────────────────────────────────┐
│  BACKEND — Django + Gunicorn                                      │
│                                                                   │
│  detector/api_views.py                                            │
│    POST /api/analyze   → görsel analiz                            │
│    GET  /api/history   → kayıt listesi                            │
│    GET  /api/history/<id> → tekil kayıt                           │
│    GET  /health/       → Docker healthcheck                       │
│                                                                   │
│  apps/detection/       → Real/Fake ONNX model inference           │
│  apps/nisa_core/db.py  → SQLite (WAL modu) CRUD                   │
│                                                                   │
│  ┌──────────────────┐    ┌──────────────────────────────┐         │
│  │  Real/Fake Model │    │  IQA Models (pyiqa)          │         │
│  │  ONNX Runtime    │    │  NIQE, BRISQUE, MUSIQ, ...   │         │
│  └──────────────────┘    └──────────────────────────────┘         │
└───────────────────────────────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  SQLite             │
                    │  /app/data/         │
                    │  iqa_history.db     │
                    └─────────────────────┘
```

---

## Servisler

### Backend (`backend/`)

- **Framework:** Django 4.2, Gunicorn (2 worker, 180s timeout)
- **Port:** 8000 (yalnızca iç ağda)
- **Model Yüklemesi:** Gunicorn worker başlatıldığında once yüklenir, request başına yeniden yüklenmez
- **Görsel Doğrulama:** MIME type → `python-magic` (gerçek dosya imzası), boyut limiti, format whitelist
- **API Kimlik Doğrulama:** `X-TrueFrame-Key` header (shared secret)
- **Healthcheck:** `GET /health/` → `{"status": "ok"}`
- **Cache:** Model ağırlıkları Docker volume'da (`model_cache:/app/.cache`)

### Frontend (`frontend/`)

- **Framework:** ASP.NET Core MVC (.NET 10)
- **Port:** 8080 (dışarıya açık)
- **Oturum:** Cookie tabanlı session, `HttpOnly + Strict SameSite`
- **CSRF:** Global `AutoValidateAntiforgeryTokenAttribute`
- **Kullanıcı Deposu:** `users.json` (atomic write: tmp → rename)
- **Backend İletişimi:** `HttpClient`, `IConfiguration` üzerinden `ApiUrl`/`HistoryApiUrl`

---

## Veri Akışı — Görsel Analizi

```
1. Kullanıcı görsel yükler
        │
        ▼
2. AnalysisController.Analyze()
   ├── Oturum kontrolü (kayıtlı/misafir)
   ├── Dosya validasyonu (uzantı, boyut)
   └── multipart/form-data → HttpClient → POST /api/analyze
            X-TrueFrame-Key header eklenir
        │
        ▼
3. Backend: detector/api_views.py → analyze()
   ├── _verify_api_key()     → 403 Forbidden
   ├── _verify_mime()        → python-magic MIME kontrolü
   ├── apps/detection → Real/Fake inference (ONNX)
   ├── pyiqa metrik hesaplama
   └── save_analysis() → SQLite (WAL)
        │  JSON yanıt
        ▼
4. Frontend: JsonSerializer.Deserialize<AnalysisApiResponse>
   MapToViewModel() → AnalysisViewModel
        │
        ▼
5. Result.cshtml
   ├── Real/Fake kartı + progress bar
   ├── Manipülasyon banner (IsManipulated)
   ├── Kalite metrikleri grid
   ├── IQA tablo (NIQE, BRISQUE, MUSIQ, ...)
   └── Doughnut grafik (Chart.js)
```

---

## Veri Akışı — Kimlik Doğrulama

```
Kayıt:
  1. Register POST → AuthController
  2. PasswordHasher.Hash() → PBKDF2 (16B salt + SHA-256 + 100k iter)
  3. UserStore.Add() → atomic JSON write (tmp → rename)

Giriş:
  1. Login POST → AuthController
  2. UserStore.FindByUsername()
  3. PasswordHasher.Verify()
     ├── PBKDF2 path (yeni format, Base64 48B)
     └── Legacy SHA-256 path (hex 64 karakter)
         └── başarılıysa: otomatik PBKDF2'ye yükselt
  4. Session.Clear() → session fixation önleme
  5. HttpContext.Session.SetString("username", ...)
```

---

## Güvenlik Mimarisi

### Şifre Hashing (PBKDF2)

```
salt = RandomNumberGenerator.GetBytes(16)
hash = PBKDF2(password, salt, iterations=100_000, alg=SHA-256, keyLen=32)
stored = Base64(salt || hash)   # 48 byte → 64 karakter Base64
```

Doğrulama `CryptographicOperations.FixedTimeEquals` ile timing-safe yapılır.

Eski SHA-256 hash'ler (64 karakter hex) başarılı girişte otomatik PBKDF2'ye upgrade edilir.

### İç API Güvenliği

Frontend, backend'e her istekte `X-TrueFrame-Key: <TRUEFRAME_API_KEY>` header'ı ekler. Backend boş key konfigürasyonunda doğrulamayı atlar (geliştirme kolaylığı); production'da mutlaka dolu olmalı.

### MIME Sniffing

Dosya uzantısı **yeterli değil**. Backend, dosyanın ilk 2048 baytını `python-magic` ile okur ve gerçek MIME tipini doğrular (`image/jpeg`, `image/png`, `image/webp`, `image/tiff`, `image/bmp`). Eşleşmezse 400 döner.

### Güvenlik Header'ları (Frontend)

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Veritabanı Şeması

`/app/data/iqa_history.db` (SQLite, WAL modu):

```sql
CREATE TABLE analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    profile     TEXT NOT NULL,
    result_json TEXT,          -- ham API yanıtı (JSON)
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    -- Migration ile eklenen alanlar:
    api_response TEXT,         -- Details sayfası için tam JSON
    label        TEXT,         -- "GERÇEK" / "YAPAY" / "MANİPÜLE"
    fake_prob    REAL,          -- AI olasılığı [0-100]
    real_prob    REAL           -- Gerçek olasılığı [0-100]
);
```

Şema migrasyonu `ALTER TABLE ... ADD COLUMN` + `try/except` ile çalışır; mevcut veritabanı varlığında hata vermez.

---

## Dosya Kalıcılığı ve Volumes

```yaml
volumes:
  model_cache:    # /app/.cache — pyiqa/huggingface model ağırlıkları
  backend_data:   # /app/data  — SQLite veritabanı
  frontend_data:  # /app/Data  — users.json
  uploads:        # /app/wwwroot/uploads — geçici görsel depolama
```

Model ağırlıkları (`backend/models/`) bind mount ile sağlanır:

```yaml
volumes:
  - ./backend/models:/app/models:ro
```

`:ro` ile salt-okunur bağlanır; konteyner model dosyalarını değiştiremez.

---

## Risk Analizi

Bu bölüm, yapılan değişikliklerin potansiyel sorunlarını belgeler.

### 1. Docker Volume Veri Kaybı

**Değişiklik:** SQLite ve kullanıcı dosyaları Docker named volume'lara taşındı.

**Risk:** `docker compose down -v` ile volume'lar silinirse tüm geçmiş analizler ve kullanıcı kayıtları kalıcı olarak kaybolur.

**Öneri:** Production'da `backend_data` ve `frontend_data` volume'larını periyodik olarak yedekleyin veya host bind mount kullanın:
```yaml
- ./data/backend:/app/data
- ./data/frontend:/app/Data
```

---

### 2. Gunicorn Worker Sayısı ve Model Belleği

**Değişiklik:** Gunicorn `--workers 2` ile başlatılır.

**Risk:** Her worker kendi model kopyasını RAM'e yükler. İki büyük model (Real/Fake + birden fazla IQA modeli) varsa toplam bellek kullanımı 2x olur. Düşük RAM'li sunucularda OOM riski.

**Öneri:** Bellek kısıtlı ortamlarda `--workers 1` veya `--preload-app` ile fork-before-load kullanın:
```
gunicorn ... --preload --workers 2
```
`--preload` modeli bir kez yükler, worker'lar fork ile paylaşır.

---

### 3. users.json Concurrent Write

**Değişiklik:** `UserStore` atomic write (tmp → rename) kullanır.

**Risk:** Birden fazla ASP.NET thread eş zamanlı kayıt yaparsa `File.Move` atomik olsa da okuma→değiştirme→yazma arası race condition oluşabilir. Mevcut implementasyonda `lock` yok.

**Öneri:** `UserStore` sınıfına `static readonly object _lock = new();` + `lock(_lock) { ... }` ekleyin, ya da kullanıcıları SQLite'a taşıyın.

---

### 4. TRUEFRAME_API_KEY Boş Kalırsa

**Değişiklik:** `_verify_api_key()` boş key'de doğrulamayı atlar (geliştirme kolaylığı).

**Risk:** `.env` dosyası eksik bırakılırsa production'da backend herhangi bir kaynaktan gelen isteği kabul eder.

**Öneri:** Backend başlangıcında key kontrolü ekleyin:
```python
if not settings.TRUEFRAME_API_KEY and not settings.DEBUG:
    raise ImproperlyConfigured("TRUEFRAME_API_KEY must be set in production")
```

---

### 5. SQLite Ölçeklenebilirlik

**Değişiklik:** Tüm analizler SQLite'a kaydedilir.

**Risk:** SQLite write lock tek yazıcıya izin verir. Yoğun eş zamanlı kullanımda write queue oluşabilir.

**Etki:** WAL modu (mevcut) çoğu senaryoda yeterlidir. Saniyede 10+ eş zamanlı yazma olursa performans düşer.

**Öneri:** Yüksek trafik senaryosunda PostgreSQL'e geçin. Django ORM zaten hazır; `settings.py`'daki `DATABASES` değiştirilmesi yeterli olur.

---

### 6. Base64 Thumbnail Boyutu

**Değişiklik:** History API'si thumbnail'ı base64 olarak döner ve `api_response` JSON'ında saklar.

**Risk:** Büyük görseller için thumbnail bile MB boyutunda olabilir. Çok sayıda kayıt için History sayfası yavaşlayabilir.

**Öneri:** Backend'de thumbnail'ı max 200x200'e küçültün veya ayrı bir `GET /api/history/<id>/thumbnail` endpoint'i açıp lazy load yapın.

---

### 7. Legacy SHA-256 Hash Upgrade

**Değişiklik:** Eski SHA-256 hash'ler girişte PBKDF2'ye upgrade edilir.

**Risk:** Upgrade sırasında `UserStore` yazılır. Yazma başarısız olursa kullanıcı her girişte legacy path'ten geçmeye devam eder — güvenlik açığı değil, performans etkisi.

**Etki:** Düşük. Upgrade başarısız olsa da kullanıcı giriş yapabilir.

---

## Karar Notları

### Neden iki ayrı servis (Django + ASP.NET)?

- Django/Python ekosistemi ML model yüklemesi için hakimdir (PyTorch, ONNX Runtime, pyiqa).
- ASP.NET MVC frontend için güçlü Razor view engine ve oturum yönetimi sunar.
- Ayrı servisler bağımsız ölçeklendirme ve teknoloji yükseltme imkânı tanır.

### Neden SQLite (PostgreSQL değil)?

- Single-node deployment için yeterli.
- Sıfır kurulum — Docker volume'da çalışır.
- Django ORM soyutlaması ile PostgreSQL'e geçiş config değişikliğiyle yapılabilir.

### Neden DTO + JsonSerializer (manuel parse yerine)?

- Önceki 150+ satır manuel parse'ın bakımı zordu.
- DTO yaklaşımı derleme zamanı tip güvenliği sağlar.
- Backend JSON şeması değiştiğinde DTO güncellenmesi yeterli olur.

### Neden users.json (veritabanı yerine)?

- Mevcut mimari ile uyumluluk.
- Bağımlılık minimizasyonu (tek SQLite bağlantısı backend'de).
- Kullanıcı sayısı küçük kaldığı sürece yeterli performans.
- Riskler: bkz. [Risk #3](#3-usersjson-concurrent-write).
