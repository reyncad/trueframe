"""
TrueFrame v2 — CLIP + FFT tabanlı AI görsel dedektörü.

Mimari:
  - CLIP ViT-B/32 görsel encoder (512-dim) → geniş jeneralizasyon
  - FFT branch (frekans domain özellikleri, 128-dim) → artifact tespiti
  - Birleşik classifier → real/fake

Hedef: <100ms inference, modern AI generatorlarına karşı güçlü genelleme.
"""
import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
from torchvision import transforms
from transformers import CLIPVisionModel, CLIPProcessor
from PIL import Image
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix
import json

# --- Config ---
REAL_DIR = Path("data/v2/real")
FAKE_DIR = Path("data/v2/fake")
MODEL_OUT = Path("models/trueframe_v2")
CLIP_MODEL = "openai/clip-vit-base-patch32"

BATCH_SIZE = 32
EPOCHS = 6
LR = 1e-4
VAL_SPLIT = 0.15
DEVICE = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"


class FFTEncoder(nn.Module):
    """Görsel frekans domaininden artifact özelliklerini çıkarır."""
    def __init__(self, out_dim=128):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.fc = nn.Linear(64 * 4 * 4, out_dim)

    def forward(self, x):
        # x: (B, C, H, W) normalize edilmiş görsel
        gray = x.mean(dim=1, keepdim=True)
        fft = torch.fft.fft2(gray)
        fft_shift = torch.fft.fftshift(fft)
        magnitude = torch.log1p(torch.abs(fft_shift))
        # [0,1] normalize
        mag_min = magnitude.amin(dim=(-2, -1), keepdim=True)
        mag_max = magnitude.amax(dim=(-2, -1), keepdim=True)
        magnitude = (magnitude - mag_min) / (mag_max - mag_min + 1e-8)
        features = self.cnn(magnitude)
        return self.fc(features.flatten(1))


class TrueFrameV2(nn.Module):
    def __init__(self, clip_model_name=CLIP_MODEL):
        super().__init__()
        self.clip = CLIPVisionModel.from_pretrained(clip_model_name)
        self.fft = FFTEncoder(out_dim=128)
        clip_dim = self.clip.config.hidden_size  # 768 for ViT-B/32

        self.classifier = nn.Sequential(
            nn.Linear(clip_dim + 128, 512),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(512, 128),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(128, 2),
        )

    def forward(self, pixel_values, raw_tensor=None):
        clip_out = self.clip(pixel_values=pixel_values)
        clip_feat = clip_out.pooler_output  # (B, clip_dim)

        if raw_tensor is not None:
            fft_feat = self.fft(raw_tensor)
        else:
            fft_feat = torch.zeros(clip_feat.shape[0], 128, device=clip_feat.device)

        combined = torch.cat([clip_feat, fft_feat], dim=1)
        return self.classifier(combined)


class ImageDataset(Dataset):
    def __init__(self, real_dir, fake_dir, clip_processor, img_size=224):
        self.processor = clip_processor
        self.raw_transform = transforms.Compose([
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
        ])

        exts = {".jpg", ".jpeg", ".png", ".webp"}
        real_files = [f for f in Path(real_dir).glob("*") if f.suffix.lower() in exts]
        fake_files = [f for f in Path(fake_dir).glob("*") if f.suffix.lower() in exts]

        # Her iki sınıfı eşitle (az olana göre cap)
        min_count = min(len(real_files), len(fake_files))
        np.random.seed(42)
        real_files = list(np.random.choice(real_files, min_count, replace=False))
        fake_files = list(np.random.choice(fake_files, min_count, replace=False))

        self.samples = [(f, 0) for f in real_files] + [(f, 1) for f in fake_files]
        np.random.shuffle(self.samples)
        print(f"Dataset: {len(real_files)} real, {len(fake_files)} fake")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        img = Image.open(path).convert("RGB")

        clip_inputs = self.processor(images=img, return_tensors="pt")
        pixel_values = clip_inputs["pixel_values"].squeeze(0)
        raw = self.raw_transform(img)

        return pixel_values, raw, label


def train():
    print(f"Cihaz: {DEVICE}")
    print(f"CLIP modeli yükleniyor: {CLIP_MODEL}")

    processor = CLIPProcessor.from_pretrained(CLIP_MODEL)
    dataset = ImageDataset(REAL_DIR, FAKE_DIR, processor)

    val_size = int(len(dataset) * VAL_SPLIT)
    train_size = len(dataset) - val_size
    train_ds, val_ds = random_split(dataset, [train_size, val_size],
                                     generator=torch.Generator().manual_seed(42))

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    model = TrueFrameV2().to(DEVICE)

    # CLIP encoder'ı ilk 2 epoch dondur, sonra aç
    for param in model.clip.parameters():
        param.requires_grad = False

    optimizer = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()), lr=LR
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    criterion = nn.CrossEntropyLoss()

    best_val_acc = 0
    history = []

    for epoch in range(EPOCHS):
        # Epoch 3'ten itibaren CLIP encoder'ı da fine-tune et (düşük lr ile)
        if epoch == 2:
            for param in model.clip.parameters():
                param.requires_grad = True
            optimizer = torch.optim.AdamW([
                {"params": model.clip.parameters(), "lr": LR * 0.1},
                {"params": model.fft.parameters(), "lr": LR},
                {"params": model.classifier.parameters(), "lr": LR},
            ])
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=EPOCHS - 2
            )
            print("  [Epoch 3] CLIP fine-tuning açıldı.")

        # Train
        model.train()
        train_loss, train_correct = 0, 0
        for pixel_values, raw, labels in train_loader:
            pixel_values = pixel_values.to(DEVICE)
            raw = raw.to(DEVICE)
            labels = labels.to(DEVICE)

            optimizer.zero_grad()
            logits = model(pixel_values, raw)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_loss += loss.item()
            train_correct += (logits.argmax(1) == labels).sum().item()

        scheduler.step()

        # Validation
        model.eval()
        val_loss, val_correct = 0, 0
        all_preds, all_labels = [], []
        with torch.no_grad():
            for pixel_values, raw, labels in val_loader:
                pixel_values = pixel_values.to(DEVICE)
                raw = raw.to(DEVICE)
                labels = labels.to(DEVICE)
                logits = model(pixel_values, raw)
                val_loss += criterion(logits, labels).item()
                preds = logits.argmax(1)
                val_correct += (preds == labels).sum().item()
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())

        train_acc = train_correct / train_size
        val_acc = val_correct / val_size
        print(f"Epoch {epoch+1}/{EPOCHS} | "
              f"Train loss: {train_loss/len(train_loader):.4f} acc: {train_acc:.4f} | "
              f"Val loss: {val_loss/len(val_loader):.4f} acc: {val_acc:.4f}")

        history.append({"epoch": epoch+1, "train_acc": train_acc, "val_acc": val_acc})

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            MODEL_OUT.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), MODEL_OUT / "model.pt")
            print(f"  -> Model kaydedildi (val_acc: {val_acc:.4f})")

    # Classification report
    print("\n=== Validation Sonuçları ===")
    print(classification_report(all_labels, all_preds, target_names=["Real", "Fake"]))

    # Config kaydet
    config = {
        "clip_model": CLIP_MODEL,
        "architecture": "TrueFrameV2_CLIP_FFT",
        "best_val_acc": best_val_acc,
        "classes": ["real", "fake"],
        "input_size": 224,
    }
    with open(MODEL_OUT / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    with open(MODEL_OUT / "history.json", "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nEn iyi val accuracy: {best_val_acc:.4f}")
    print(f"Model kaydedildi: {MODEL_OUT}")
    print("\nSıradaki adım: python3 export_onnx.py")


if __name__ == "__main__":
    train()
