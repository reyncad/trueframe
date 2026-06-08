"""
Evaluation script for the fine-tuned TrueFrame model.
Usage:
  python evaluate.py                          → test/ klasörünü değerlendir
  python evaluate.py --image foto.jpg         → tek fotoğraf test et
"""

import argparse
from pathlib import Path
from PIL import Image
import torch
import numpy as np
from transformers import AutoFeatureExtractor, AutoModelForImageClassification
from sklearn.metrics import accuracy_score, precision_score, recall_score, classification_report

MODEL_PATH = Path("models/true_frame_model")
TEST_DIR = Path("data/test")
ID2LABEL = {0: "GERÇEK", 1: "YAPAY"}


def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model bulunamadı: {MODEL_PATH}\n"
            "Önce fine_tune.py çalıştırın."
        )
    feature_extractor = AutoFeatureExtractor.from_pretrained(str(MODEL_PATH))
    model = AutoModelForImageClassification.from_pretrained(str(MODEL_PATH))
    model.eval()
    return model, feature_extractor


def predict_single(image_path: str, model=None, feature_extractor=None) -> dict:
    """
    Tek bir fotoğrafı test et.
    Döner: {"label": "GERÇEK"/"YAPAY", "confidence": float, "real_prob": float, "fake_prob": float}
    """
    if model is None:
        model, feature_extractor = load_model()

    image = Image.open(image_path).convert("RGB")
    inputs = feature_extractor(images=image, return_tensors="pt")

    with torch.no_grad():
        outputs = model(**inputs)

    probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
    pred_id = int(np.argmax(probs))

    result = {
        "label": ID2LABEL[pred_id],
        "confidence": round(probs[pred_id] * 100, 2),
        "real_prob": round(probs[0] * 100, 2),
        "fake_prob": round(probs[1] * 100, 2),
    }

    print(f"\nFotoğraf : {image_path}")
    print(f"Tahmin   : {result['label']}  (güven: %{result['confidence']:.1f})")
    print(f"  Gerçek : %{result['real_prob']:.1f}")
    print(f"  Yapay  : %{result['fake_prob']:.1f}")

    return result


def evaluate_folder():
    model, feature_extractor = load_model()

    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    all_paths, all_labels = [], []

    for label_id, folder_name in [(0, "real"), (1, "fake")]:
        folder = TEST_DIR / folder_name
        if not folder.exists():
            print(f"Uyarı: {folder} bulunamadı, atlanıyor.")
            continue
        for p in folder.iterdir():
            if p.suffix.lower() in image_exts:
                all_paths.append(str(p))
                all_labels.append(label_id)

    if not all_paths:
        print(f"Test klasöründe fotoğraf bulunamadı: {TEST_DIR}")
        return

    print(f"\n{len(all_paths)} fotoğraf test ediliyor...")
    predictions = []
    for path in all_paths:
        image = Image.open(path).convert("RGB")
        inputs = feature_extractor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)
        pred = int(torch.argmax(outputs.logits, dim=-1).item())
        predictions.append(pred)

    acc = accuracy_score(all_labels, predictions)
    prec = precision_score(all_labels, predictions, average="binary")
    rec = recall_score(all_labels, predictions, average="binary")

    print("\n=== Sonuçlar ===")
    print(f"Accuracy  : %{acc * 100:.2f}")
    print(f"Precision : %{prec * 100:.2f}")
    print(f"Recall    : %{rec * 100:.2f}")
    print("\nDetaylı Rapor:")
    print(classification_report(all_labels, predictions, target_names=["Gerçek", "Yapay"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, help="Tek fotoğraf test et (yol)")
    args = parser.parse_args()

    if args.image:
        predict_single(args.image)
    else:
        evaluate_folder()
