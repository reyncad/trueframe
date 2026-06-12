"""
TrueFrame Detection Service — v2 (CLIP + FFT) + manipülasyon dedektörü.

İki model birlikte çalışır:
  1. TrueFrame v2: genel AI vs gerçek tespiti
  2. Manipülasyon dedektörü: yüz değiştirme, arka plan swap, AI retouche tespiti

Sonuç kategorileri:
  KESİNLİKLE GERÇEK   — temiz, dokunulmamış görsel
  MUHTEMELEN GERÇEK   — büyük ihtimalle gerçek
  MANİPÜLE EDİLMİŞ   — gerçek base + AI değişikliği (Gemini, retouche, vb.)
  MUHTEMELEN YAPAY    — büyük ihtimalle AI üretimi
  KESİNLİKLE YAPAY   — sıfırdan AI üretilmiş
  BELİRSİZ            — model emin değil
"""
import json
import os
import numpy as np
from pathlib import Path
from PIL import Image

import torch
from torchvision import transforms

# Geliştirme ortamında manipülasyon dedektörünü devre dışı bırakmak için:
# docker-compose.override.yml → DISABLE_MANIP_DETECTOR: "true"
# Bu, yükleme sırasında ~500 MB RAM tasarrufu sağlar.
_DISABLE_MANIP = os.environ.get("DISABLE_MANIP_DETECTOR", "").lower() in ("1", "true", "yes")

MODEL_V2_DIR = Path(__file__).resolve().parents[2] / "models" / "trueframe_v2"
MODEL_V1_DIR = Path(__file__).resolve().parents[2] / "models" / "true_frame_model"
FALLBACK_MODEL = "dima806/ai_vs_real_image_detection"
MANIP_MODEL = "dima806/deepfake_vs_real_image_detection"

IMG_SIZE = 224
TEMPERATURE = 2.0
REAL_BIAS = 1.2
RAW_TRANSFORM = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
])


class DetectionService:
    def __init__(self):
        self._mode = None
        self._ort_session = None
        self._clip_processor = None
        self._v1_extractor = None
        self._v1_model = None
        self._v2_model = None
        # Manipülasyon dedektörü
        self._manip_extractor = None
        self._manip_model = None

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
            except Exception as e:
                print(f"[TrueFrame] ONNX yüklenemedi ({e}), PyTorch'a düşülüyor")

        # --- v2 PyTorch ---
        if self._mode is None:
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
                except Exception as e:
                    print(f"[TrueFrame] v2 yüklenemedi ({e}), v1'e düşülüyor")

        # --- v1 fallback ---
        if self._mode is None:
            from transformers import AutoImageProcessor, AutoModelForImageClassification
            src = str(MODEL_V1_DIR) if MODEL_V1_DIR.exists() else FALLBACK_MODEL
            self._v1_extractor = AutoImageProcessor.from_pretrained(src)
            self._v1_model = AutoModelForImageClassification.from_pretrained(src)
            self._v1_model.eval()
            self._mode = "v1"
            print(f"[TrueFrame] v1 modeli yüklendi: {src}")

        # --- Manipülasyon dedektörü (her modda çalışır) ---
        # DISABLE_MANIP_DETECTOR=true olursa yüklenmez (geliştirme/düşük RAM)
        if _DISABLE_MANIP:
            print("[TrueFrame] Manipülasyon dedektörü devre dışı (DISABLE_MANIP_DETECTOR=true)")
        else:
            try:
                from transformers import AutoImageProcessor, AutoModelForImageClassification
                self._manip_extractor = AutoImageProcessor.from_pretrained(MANIP_MODEL)
                self._manip_model = AutoModelForImageClassification.from_pretrained(MANIP_MODEL)
                self._manip_model.eval()
                print("[TrueFrame] Manipülasyon dedektörü yüklendi")
            except Exception as e:
                print(f"[TrueFrame] Manipülasyon dedektörü yüklenemedi ({e})")

    def _run_manip_detector(self, img: Image.Image) -> float:
        """Manipülasyon skoru döner: 0=temiz, 1=manipüle. Yüklenemezse -1."""
        if self._manip_model is None:
            return -1.0
        try:
            inputs = self._manip_extractor(images=img, return_tensors="pt")
            with torch.no_grad():
                outputs = self._manip_model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
            # Modelin label sıralamasını kontrol et
            labels = self._manip_model.config.id2label
            fake_idx = next((i for i, l in labels.items() if "fake" in l.lower() or "deep" in l.lower()), 1)
            return float(probs[fake_idx])
        except Exception:
            return -1.0

    def _predict_pil_v2_onnx(self, img: Image.Image) -> dict:
        clip_inputs = self._clip_processor(images=img, return_tensors="pt")
        raw = RAW_TRANSFORM(img).unsqueeze(0)
        gray = raw.mean(dim=1, keepdim=True)
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
        adjusted = logits.copy().astype(float)
        adjusted[1] -= REAL_BIAS   # sahte logit'i hafif düşür
        scaled = adjusted / TEMPERATURE
        exp = np.exp(scaled - scaled.max())
        probs = exp / exp.sum()
        return DetectionService._probs_to_result(probs.tolist())

    @staticmethod
    def _probs_to_result(probs: list) -> dict:
        pred_id = int(np.argmax(probs))
        confidence = probs[pred_id] * 100
        is_ai = probs[1] > 0.62   # %50 değil, %62+ gerektir

        if is_ai:
            if confidence >= 93:
                label = "KESİNLİKLE YAPAY"
            elif confidence >= 75:
                label = "MUHTEMELEN YAPAY"
            else:
                label = "BELİRSİZ"
        else:
            if confidence >= 85:
                label = "KESİNLİKLE GERÇEK"
            elif confidence >= 68:
                label = "MUHTEMELEN GERÇEK"
            else:
                label = "BELİRSİZ"

        return {
            "is_ai_generated": is_ai,
            "label": label,
            "confidence": round(confidence, 2),
            "real_prob": round(probs[0] * 100, 2),
            "fake_prob": round(probs[1] * 100, 2),
        }

    def _combine_results(self, base: dict, manip_score: float) -> dict:
        """
        İki dedektörün sonucunu birleştirir.
        manip_score: 0-1 arası, 1 = manipüle edilmiş
        """
        if manip_score < 0:
            return base  # Manipülasyon dedektörü çalışmadı

        is_ai = base["is_ai_generated"]
        ai_conf = base["fake_prob"] / 100

        # Tamamen AI üretilmiş → manipülasyon dedektörünü geçersiz kıl
        if is_ai and ai_conf >= 0.80:
            return base

        # Gerçek görünüyor ama manipülasyon şüphesi var
        if not is_ai and manip_score >= 0.78:
            confidence = round(manip_score * 100, 2)
            return {
                "is_ai_generated": False,
                "is_manipulated": True,
                "label": "MANİPÜLE EDİLMİŞ",
                "confidence": confidence,
                "real_prob": base["real_prob"],
                "fake_prob": base["fake_prob"],
                "manip_score": round(manip_score * 100, 2),
            }

        result = base.copy()
        result["is_manipulated"] = False
        result["manip_score"] = round(manip_score * 100, 2)
        return result

    def predict_pil(self, image: Image.Image) -> dict:
        self._load()
        img = image.convert("RGB")

        if self._mode == "v2_onnx":
            base = self._predict_pil_v2_onnx(img)
        elif self._mode == "v2_torch":
            base = self._predict_pil_v2_torch(img)
        else:
            base = self._predict_pil_v1(img)

        manip_score = self._run_manip_detector(img)
        return self._combine_results(base, manip_score)

    def predict(self, image_path: str) -> dict:
        return self.predict_pil(Image.open(image_path))


CNNDetectionService = DetectionService
