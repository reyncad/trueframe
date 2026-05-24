"""
TrueFrame Detection Service — v2 (CLIP + FFT) ve v1 (fallback) destekler.
v2 modeli varsa ONNX Runtime ile hızlı inference yapar, yoksa v1'e düşer.
"""
import json
import numpy as np
from pathlib import Path
from PIL import Image

import torch
from torchvision import transforms

MODEL_V2_DIR = Path(__file__).resolve().parents[2] / "models" / "trueframe_v2"
MODEL_V1_DIR = Path(__file__).resolve().parents[2] / "models" / "true_frame_model"
FALLBACK_MODEL = "dima806/ai_vs_real_image_detection"

IMG_SIZE = 224
TEMPERATURE = 1.8  # Skor kalibrasyonu: yüksek → daha ihtiyatlı tahminler
RAW_TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
])


class DetectionService:
    def __init__(self):
        self._mode = None          # "v2_onnx" | "v2_torch" | "v1"
        self._ort_session = None
        self._clip_processor = None
        self._v1_extractor = None
        self._v1_model = None
        self._v2_model = None

    def _load(self):
        if self._mode is not None:
            return

        # --- v2 ONNX ---
        onnx_path = MODEL_V2_DIR / "model.onnx"
        if onnx_path.exists():
            try:
                import onnxruntime as ort
                from transformers import CLIPProcessor
                config = json.loads((MODEL_V2_DIR / "config.json").read_text())
                self._clip_processor = CLIPProcessor.from_pretrained(config["clip_model"])
                self._ort_session = ort.InferenceSession(
                    str(onnx_path), providers=["CPUExecutionProvider"]
                )
                self._mode = "v2_onnx"
                print("[TrueFrame] v2 ONNX modeli yüklendi")
                return
            except Exception as e:
                print(f"[TrueFrame] ONNX yüklenemedi ({e}), PyTorch'a düşülüyor")

        # --- v2 PyTorch ---
        pt_path = MODEL_V2_DIR / "model.pt"
        if pt_path.exists():
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
                from train_v2 import TrueFrameV2
                from transformers import CLIPProcessor
                config = json.loads((MODEL_V2_DIR / "config.json").read_text())
                self._clip_processor = CLIPProcessor.from_pretrained(config["clip_model"])
                model = TrueFrameV2(config["clip_model"])
                model.load_state_dict(torch.load(pt_path, map_location="cpu"))
                model.eval()
                self._v2_model = model
                self._mode = "v2_torch"
                print("[TrueFrame] v2 PyTorch modeli yüklendi")
                return
            except Exception as e:
                print(f"[TrueFrame] v2 PyTorch yüklenemedi ({e}), v1'e düşülüyor")

        # --- v1 fallback ---
        from transformers import AutoFeatureExtractor, AutoModelForImageClassification
        src = str(MODEL_V1_DIR) if MODEL_V1_DIR.exists() else FALLBACK_MODEL
        self._v1_extractor = AutoFeatureExtractor.from_pretrained(src)
        self._v1_model = AutoModelForImageClassification.from_pretrained(src)
        self._v1_model.eval()
        self._mode = "v1"
        print(f"[TrueFrame] v1 modeli yüklendi: {src}")

    def _predict_pil_v2_onnx(self, img: Image.Image) -> dict:
        clip_inputs = self._clip_processor(images=img, return_tensors="pt")
        raw = RAW_TRANSFORM(img).unsqueeze(0)
        # FFT dışarıda hesaplanır (ONNX fft_fft2 desteklemiyor)
        gray = raw.mean(dim=1, keepdim=True)
        import torch
        fft_shift = torch.fft.fftshift(torch.fft.fft2(gray))
        magnitude = torch.log1p(torch.abs(fft_shift))
        mag_min = magnitude.amin(dim=(-2, -1), keepdim=True)
        mag_max = magnitude.amax(dim=(-2, -1), keepdim=True)
        fft_magnitude = ((magnitude - mag_min) / (mag_max - mag_min + 1e-8)).numpy()
        logits = self._ort_session.run(None, {
            "pixel_values": clip_inputs["pixel_values"].numpy().astype(np.float32),
            "fft_magnitude": fft_magnitude.astype(np.float32),
        })[0]
        return self._logits_to_result(logits[0])

    def _predict_pil_v2_torch(self, img: Image.Image) -> dict:
        clip_inputs = self._clip_processor(images=img, return_tensors="pt")
        raw = RAW_TRANSFORM(img).unsqueeze(0)
        with torch.no_grad():
            logits = self._v2_model(clip_inputs["pixel_values"], raw)
        return self._logits_to_result(logits[0].numpy())

    def _predict_pil_v1(self, img: Image.Image) -> dict:
        inputs = self._v1_extractor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = self._v1_model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
        return self._probs_to_result(probs)

    @staticmethod
    def _logits_to_result(logits: np.ndarray) -> dict:
        scaled = logits / TEMPERATURE
        exp = np.exp(scaled - scaled.max())
        probs = exp / exp.sum()
        return DetectionService._probs_to_result(probs.tolist())

    @staticmethod
    def _probs_to_result(probs: list) -> dict:
        pred_id = int(np.argmax(probs))
        confidence = probs[pred_id] * 100

        if pred_id == 1:  # AI
            if confidence >= 88:
                label = "KESİNLİKLE YAPAY"
            elif confidence >= 70:
                label = "MUHTEMELEN YAPAY"
            else:
                label = "BELİRSİZ"
        else:  # Gerçek
            if confidence >= 88:
                label = "KESİNLİKLE GERÇEK"
            elif confidence >= 70:
                label = "MUHTEMELEN GERÇEK"
            else:
                label = "BELİRSİZ"

        return {
            "is_ai_generated": pred_id == 1,
            "label": label,
            "confidence": round(confidence, 2),
            "real_prob": round(probs[0] * 100, 2),
            "fake_prob": round(probs[1] * 100, 2),
        }

    def predict_pil(self, image: Image.Image) -> dict:
        self._load()
        img = image.convert("RGB")
        if self._mode == "v2_onnx":
            return self._predict_pil_v2_onnx(img)
        elif self._mode == "v2_torch":
            return self._predict_pil_v2_torch(img)
        else:
            return self._predict_pil_v1(img)

    def predict(self, image_path: str) -> dict:
        return self.predict_pil(Image.open(image_path))


# Geriye dönük uyumluluk (eski views.py CNNDetectionService'i import ediyorsa)
CNNDetectionService = DetectionService
