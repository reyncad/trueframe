"""
CNN Detection Service — fine-tuned TrueFrame modeli ile AI vs Real tespiti.
"""

from pathlib import Path
from PIL import Image
import torch
from transformers import AutoFeatureExtractor, AutoModelForImageClassification
import numpy as np

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "true_frame_model"
FALLBACK_MODEL = "dima806/ai_vs_real_image_detection"


class CNNDetectionService:
    def __init__(self):
        self._model = None
        self._feature_extractor = None

    def _load(self):
        if self._model is not None:
            return

        model_source = str(MODEL_PATH) if MODEL_PATH.exists() else FALLBACK_MODEL
        if not MODEL_PATH.exists():
            print(f"[CNNDetectionService] Fine-tuned model bulunamadı, base model kullanılıyor: {FALLBACK_MODEL}")

        self._feature_extractor = AutoFeatureExtractor.from_pretrained(model_source)
        self._model = AutoModelForImageClassification.from_pretrained(model_source)
        self._model.eval()

    def predict(self, image_path: str) -> dict:
        """
        Fotoğrafın gerçek mi yapay mı olduğunu tahmin eder.

        Döner:
            {
                "is_ai_generated": bool,
                "label": "GERÇEK" | "YAPAY",
                "confidence": float,   # 0-100 arası yüzde
                "real_prob": float,
                "fake_prob": float,
            }
        """
        self._load()

        image = Image.open(image_path).convert("RGB")
        inputs = self._feature_extractor(images=image, return_tensors="pt")

        with torch.no_grad():
            outputs = self._model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
        pred_id = int(np.argmax(probs))

        label_map = {0: "GERÇEK", 1: "YAPAY"}
        return {
            "is_ai_generated": pred_id == 1,
            "label": label_map[pred_id],
            "confidence": round(probs[pred_id] * 100, 2),
            "real_prob": round(probs[0] * 100, 2),
            "fake_prob": round(probs[1] * 100, 2),
        }

    def predict_pil(self, image: Image.Image) -> dict:
        """PIL Image nesnesiyle doğrudan çalışır (dosya yolu gerekmez)."""
        self._load()

        inputs = self._feature_extractor(images=image.convert("RGB"), return_tensors="pt")
        with torch.no_grad():
            outputs = self._model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
        pred_id = int(np.argmax(probs))

        label_map = {0: "GERÇEK", 1: "YAPAY"}
        return {
            "is_ai_generated": pred_id == 1,
            "label": label_map[pred_id],
            "confidence": round(probs[pred_id] * 100, 2),
            "real_prob": round(probs[0] * 100, 2),
            "fake_prob": round(probs[1] * 100, 2),
        }
