"""
DetectorConfig — Django AppConfig.

Model önyükleme (warmup):
  - Sunucu başladığında modelleri arka plan thread'inde sırayla yükler.
  - Sağlık kontrolü modeller yüklenmeden geçer; ilk analiz isteği
    model yükleme tamamlanana kadar bekler (_service._load() idempotent).

  Çalışma ortamı uyumluluğu:
  - runserver (geliştirme): RUN_MAIN=true olan child process'te çalışır,
    parent reloader'da tekrar çalışmaz.
  - Gunicorn (production): RUN_MAIN set edilmez. --preload kullanıldığında
    warmup master process'te bir kez çalışır; worker'lar fork ile devralır.
    --preload kullanılmazsa warmup atlanır, lazy load devreye girer.

  ⚠ BİLİNEN SINIRLILIK — Gunicorn --preload + çok worker:
    ready() master process'te warmup thread'ini başlatır; _warmup_done = True
    set edilir ANCAK thread henüz warmup_done.set() çağırmamış olabilir.
    Worker'lar fork ile bu state'i kopyalar → her worker'ın warmup_done Event'i
    hiçbir zaman set olmaz → analyze ilk istekte 60 s timeout'a düşer (lazy load).
    Pratik etki: ilk N istek ~60 s bekler, sonrası normal.
    Gerçek düzeltme: --preload modunda warmup'ı senkron yap veya
    worker post-fork hook'unda (gunicorn post_fork) warmup_done.set() çağır.
"""
import gc
import os
import threading
import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

# Gunicorn --preload: modeller master'da yüklenmiş olabilir;
# bu flag tekrar çalışmayı engeller.
_warmup_done = False


def _is_worker_process() -> bool:
    """
    runserver child process (RUN_MAIN=true) veya
    Gunicorn worker/master (SERVER_SOFTWARE ayarlı ya da gunicorn process) için True döner.
    """
    # Django runserver child
    if os.environ.get("RUN_MAIN") == "true":
        return True
    # Gunicorn: parent reloader yok, tüm process'ler worker sayılır
    # (gunicorn --preload ile master'da da çalışması istenir)
    if "gunicorn" in os.environ.get("SERVER_SOFTWARE", "").lower():
        return True
    # Gunicorn argümanı tespit et (sys.argv[0] veya GUNICORN_CMD_ARGS)
    import sys
    if any("gunicorn" in arg.lower() for arg in sys.argv[:2]):
        return True
    # runserver --noreload: tek process, reloader yok, worker sayılır
    if "--noreload" in sys.argv:
        return True
    return False


class DetectorConfig(AppConfig):
    name = "detector"

    def ready(self):
        global _warmup_done
        if _warmup_done:
            return
        if not _is_worker_process():
            return   # runserver parent watcher'ı — atla
        _warmup_done = True

        def _warmup():
            try:
                # 1) Tespit modeli
                from detector.api_views import _service, _quality_available, warmup_done
                logger.info("[TrueFrame] Model ön yükleme başladı (tespit)...")
                _service._load()
                logger.info("[TrueFrame] Tespit modeli hazır.")

                # 2) IQA metrikleri — sırayla yükle, aralarında GC ile bellek baskısını azalt
                if _quality_available:
                    from core.metrics.iqa import get_model
                    from core.config import IQA_METRICS
                    for name in IQA_METRICS:
                        try:
                            get_model(name)
                            logger.info("[TrueFrame] IQA metrik hazır: %s", name)
                            gc.collect()   # her model sonrası artık belleği temizle
                        except Exception as exc:
                            logger.warning("[TrueFrame] IQA metrik yüklenemedi (%s): %s", name, exc)

                logger.info("[TrueFrame] Tüm modeller hazır.")
            except Exception as exc:
                logger.error("[TrueFrame] Model ön yükleme hatası: %s", exc)
            finally:
                # Warmup tamamlandı (hata olsa da) — analyze endpoint'i serbest bırak
                from detector.api_views import warmup_done
                warmup_done.set()

        t = threading.Thread(target=_warmup, name="trueframe-warmup", daemon=True)
        t.start()
