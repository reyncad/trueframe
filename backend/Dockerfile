# ─────────────────────────────────────────────────────────────
# TrueFrame Backend — Django API
# Python 3.11-slim baz alınır; GPU için nvidia/cuda tabanlı imaja geçilebilir.
# ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Sistem bağımlılıkları
# libmagic1  : MIME sniffing güvenlik kontrolü için
# libgl1     : OpenCV/IQA görüntü işleme
# libglib2.0 : PIL / scipy destek kütüphaneleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bağımlılıkları önce kopyala (layer cache için)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

# Model cache dizinleri (volume olarak mount edilir)
ENV HOME=/app
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_HOME=/app/.cache/huggingface
ENV TORCH_HOME=/app/.cache/torch
ENV PYIQA_CACHE=/app/.cache/pyiqa

RUN mkdir -p /app/.cache/huggingface /app/.cache/torch /app/.cache/pyiqa /app/data

# Güvenlik: root olmayan kullanıcı
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Gunicorn:
#   --preload       : Uygulamayı master process'te bir kez yükle; worker'lar fork ile devralır.
#                     ML modelleri (PyTorch, ONNX, pyiqa) tek seferde belleğe alınır —
#                     2 worker ile 2× değil, 1× bellek kullanımı.
#   --workers 1     : Varsayılan 1 worker; bellek kısıtlı ortamlar için güvenli başlangıç.
#                     Yüksek yük varsa GUNICORN_WORKERS env ile artır (örn: 2).
#   --timeout 300   : Model indirme + ilk yükleme süresine tolerans.
CMD ["sh", "-c", \
     "gunicorn trueframe.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers ${GUNICORN_WORKERS:-1} \
      --timeout 300 \
      --preload \
      --log-level info \
      --access-logfile - \
      --error-logfile -"]
