"""
TrueFrame v2 modelini ONNX formatına export eder.

FFT operasyonu ONNX'te desteklenmediği için iki aşamalı yaklaşım:
  - FFT hesaplaması Python/torch ile yapılır (hızlı, CPU)
  - ONNX wrapper: (pixel_values, fft_magnitude) → logits
"""
import torch
import torch.nn as nn
import json
import numpy as np
from pathlib import Path
from PIL import Image
from transformers import CLIPProcessor
from train_v2 import TrueFrameV2, CLIP_MODEL

MODEL_DIR = Path("models/trueframe_v2")
ONNX_PATH = MODEL_DIR / "model.onnx"


class TrueFrameONNXWrapper(nn.Module):
    """FFT zaten hesaplanmış olarak alır — ONNX uyumlu."""
    def __init__(self, model: TrueFrameV2):
        super().__init__()
        self.clip = model.clip
        self.fft_cnn = model.fft.cnn
        self.fft_fc = model.fft.fc
        self.classifier = model.classifier

    def forward(self, pixel_values, fft_magnitude):
        # fft_magnitude: (B, 1, H, W) dışarıda hesaplanmış
        clip_feat = self.clip(pixel_values=pixel_values).pooler_output
        fft_feat = self.fft_fc(self.fft_cnn(fft_magnitude).flatten(1))
        return self.classifier(torch.cat([clip_feat, fft_feat], dim=1))


def compute_fft_magnitude(raw_tensor: torch.Tensor) -> torch.Tensor:
    """Servis katmanında FFT hesaplamak için kullanılır."""
    gray = raw_tensor.mean(dim=1, keepdim=True)
    fft_shift = torch.fft.fftshift(torch.fft.fft2(gray))
    magnitude = torch.log1p(torch.abs(fft_shift))
    mag_min = magnitude.amin(dim=(-2, -1), keepdim=True)
    mag_max = magnitude.amax(dim=(-2, -1), keepdim=True)
    return (magnitude - mag_min) / (mag_max - mag_min + 1e-8)


def export():
    print("Model yükleniyor...")
    with open(MODEL_DIR / "config.json") as f:
        config = json.load(f)

    base_model = TrueFrameV2(config["clip_model"])
    base_model.load_state_dict(torch.load(MODEL_DIR / "model.pt", map_location="cpu"))
    base_model.eval()

    wrapper = TrueFrameONNXWrapper(base_model)
    wrapper.eval()

    processor = CLIPProcessor.from_pretrained(config["clip_model"])
    dummy_pil = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
    pixel_values = processor(images=dummy_pil, return_tensors="pt")["pixel_values"]
    raw_tensor = torch.rand(1, 3, 224, 224)
    fft_magnitude = compute_fft_magnitude(raw_tensor)  # (1, 1, 224, 224)

    print("ONNX export başlıyor...")
    torch.onnx.export(
        wrapper,
        (pixel_values, fft_magnitude),
        ONNX_PATH,
        input_names=["pixel_values", "fft_magnitude"],
        output_names=["logits"],
        dynamic_axes={
            "pixel_values": {0: "batch"},
            "fft_magnitude": {0: "batch"},
            "logits": {0: "batch"},
        },
        opset_version=17,
        do_constant_folding=True,
    )
    print(f"ONNX modeli kaydedildi: {ONNX_PATH}")

    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
        out = sess.run(None, {
            "pixel_values": pixel_values.numpy(),
            "fft_magnitude": fft_magnitude.numpy(),
        })
        print(f"ONNX doğrulama OK — output shape: {out[0].shape}")
    except ImportError:
        print("onnxruntime kurulu değil: pip3 install onnxruntime")


if __name__ == "__main__":
    export()
