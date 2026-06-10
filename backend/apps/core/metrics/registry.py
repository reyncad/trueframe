"""
Metric Registry — genişletilebilir metrik sistemi.

Yeni bir ML metriği eklemek için:
  1. core/metrics/ altında yeni dosya yarat
  2. MetricBase'den miras al
  3. compute() ve validate() metodlarını implement et
  4. Modül sonunda register_metric() çağır

Sistem, METRIC_REGISTRY'e kayıtlı metrikleri otomatik olarak
core/config.py IQA_METRICS tanımlarıyla eşleştirir.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Type


class MetricResult:
    """Standart metrik sonucu wrapper."""

    __slots__ = ("score", "status", "elapsed_ms", "error")

    def __init__(
        self,
        score: float | None = None,
        status: str = "ok",
        elapsed_ms: int = 0,
        error: str | None = None,
    ) -> None:
        self.score      = score
        self.status     = status
        self.elapsed_ms = elapsed_ms
        self.error      = error

    def to_dict(self) -> dict:
        if self.status != "ok":
            return {"status": self.status, "error": self.error or ""}
        return {
            "status":     self.status,
            "score":      self.score,
            "elapsed_ms": self.elapsed_ms,
        }


class MetricBase(ABC):
    """
    Tüm IQA metriklerinin temel sınıfı.

    Alt sınıflar:
      - name       : str  — config.py IQA_METRICS anahtarıyla eşleşmeli
      - direction  : str  — "higher" veya "lower"
    """

    name:      str = ""
    direction: str = "higher"

    @abstractmethod
    def compute(self, image_path: str) -> MetricResult:
        """
        Görsel dosyasından metrik hesapla.

        Args:
            image_path: Disk üzerindeki geçici görsel yolu.

        Returns:
            MetricResult with score and timing.
        """

    def validate(self, score: float) -> bool:
        """
        Hesaplanan skor geçerli aralıkta mı?
        Alt sınıflar metrik-spesifik aralıklarla override edebilir.
        """
        return isinstance(score, (int, float)) and not (score != score)  # NaN check

    def get_info(self) -> dict:
        """Registry metadata."""
        return {"name": self.name, "direction": self.direction}


# ── Global registry ──────────────────────────────────────────────────────────

METRIC_REGISTRY: Dict[str, Type[MetricBase]] = {}


def register_metric(name: str, cls: Type[MetricBase]) -> None:
    """
    Metriği global registry'ye ekle.

    Args:
        name: IQA_METRICS'teki anahtar (ör. "brisque")
        cls:  MetricBase'den türeyen sınıf
    """
    if not issubclass(cls, MetricBase):
        raise TypeError(f"{cls.__name__} MetricBase'den türemeli")
    METRIC_REGISTRY[name] = cls


def get_metric(name: str) -> MetricBase:
    """
    Registry'den metrik instance'ı al.

    Raises:
        KeyError: Metrik kayıtlı değilse
    """
    if name not in METRIC_REGISTRY:
        raise KeyError(f"Metrik '{name}' registry'de bulunamadı. Kayıtlılar: {list(METRIC_REGISTRY)}")
    return METRIC_REGISTRY[name]()


def list_metrics() -> list[str]:
    """Kayıtlı tüm metrik isimlerini döndür."""
    return sorted(METRIC_REGISTRY.keys())
