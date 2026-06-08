"""
TrueFrame Django Ayarları

Tüm hassas değerler ortam değişkenlerinden okunur.
Geliştirme için: .env dosyası oluşturun (bakınız: ../.env.example)
Production için: docker-compose.yml environment bölümünü doldurun.
"""

import os
import sys
from pathlib import Path

# python-dotenv: geliştirmede .env dosyasını yükler (production'da etki etmez)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# nisa_core modüllerinin import edilebilmesi için
if str(BASE_DIR / "apps") not in sys.path:
    sys.path.insert(0, str(BASE_DIR / "apps"))

# ─────────────────────────────────────────────────────────────
# Güvenlik
# ─────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    # Sadece geliştirme ortamı için fallback — production'da .env zorunludur
    "INSECURE-dev-only-key-set-DJANGO_SECRET_KEY-in-production"
)

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("true", "1", "yes")

_allowed = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]

# Backend-to-backend API key (frontend ile paylaşılan)
TRUEFRAME_API_KEY = os.environ.get("TRUEFRAME_API_KEY", "")

# ─────────────────────────────────────────────────────────────
# Uygulamalar
# ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "detector",
]

# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "trueframe.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "trueframe.wsgi.application"

# ─────────────────────────────────────────────────────────────
# Lokalizasyon
# ─────────────────────────────────────────────────────────────
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

# ─────────────────────────────────────────────────────────────
# Dosya Yükleme Limitleri
# ─────────────────────────────────────────────────────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ─────────────────────────────────────────────────────────────
# Veritabanı (geçmiş kayıt için SQLite)
# ─────────────────────────────────────────────────────────────
_db_path = os.environ.get("DATABASE_URL", str(BASE_DIR / "data" / "iqa_history.db"))
DATABASE_URL = _db_path

# ─────────────────────────────────────────────────────────────
# Model Cache Dizinleri (Docker volume'larıyla örtüşür)
# ─────────────────────────────────────────────────────────────
_cache_root = Path(os.environ.get("TRUEFRAME_CACHE_ROOT", str(BASE_DIR / ".cache")))
os.environ.setdefault("TRANSFORMERS_CACHE", str(_cache_root / "huggingface"))
os.environ.setdefault("TORCH_HOME", str(_cache_root / "torch"))
os.environ.setdefault("PYIQA_CACHE", str(_cache_root / "pyiqa"))

# ─────────────────────────────────────────────────────────────
# Production güvenlik ayarları (DEBUG=False olduğunda etkinleşir)
# ─────────────────────────────────────────────────────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"
