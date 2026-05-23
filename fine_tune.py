"""
Fine-tuning script for AI vs Real image detection.
Base model: dima806/ai_vs_real_image_detection
"""

import os
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from datasets import Dataset, DatasetDict
from transformers import (
    AutoFeatureExtractor,
    AutoModelForImageClassification,
    TrainingArguments,
    Trainer,
    EarlyStoppingCallback,
)
from PIL import Image
import torch
# Paths
DATA_DIR = Path("data")
MODEL_OUTPUT = Path("models/true_frame_model")
BASE_MODEL = "dima806/ai_vs_real_image_detection"

# Label mapping: model uses REAL=0, FAKE=1
LABEL2ID = {"real": 0, "fake": 1}
ID2LABEL = {0: "real", 1: "fake"}


def load_image_paths():
    real_paths = list((DATA_DIR / "real").glob("*.jpg")) + \
                 list((DATA_DIR / "real").glob("*.jpeg")) + \
                 list((DATA_DIR / "real").glob("*.png"))

    fake_paths = list((DATA_DIR / "fake").glob("*.jpg")) + \
                 list((DATA_DIR / "fake").glob("*.jpeg")) + \
                 list((DATA_DIR / "fake").glob("*.png"))

    if not real_paths or not fake_paths:
        raise ValueError(
            f"Fotoğraf bulunamadı.\n"
            f"  data/real/ içinde: {len(real_paths)} fotoğraf\n"
            f"  data/fake/ içinde: {len(fake_paths)} fotoğraf\n"
            "Her klasöre en az 50 fotoğraf ekleyin."
        )

    paths = [str(p) for p in real_paths + fake_paths]
    labels = [0] * len(real_paths) + [1] * len(fake_paths)

    print(f"Yüklendi: {len(real_paths)} gerçek, {len(fake_paths)} yapay fotoğraf")
    return paths, labels


def build_dataset(paths, labels, feature_extractor):
    def preprocess(batch):
        images = [Image.open(p).convert("RGB") for p in batch["path"]]
        inputs = feature_extractor(images=images, return_tensors="pt")
        inputs["labels"] = batch["label"]
        return inputs

    train_paths, val_paths, train_labels, val_labels = train_test_split(
        paths, labels, test_size=0.2, stratify=labels, random_state=42
    )

    train_ds = Dataset.from_dict({"path": train_paths, "label": train_labels})
    val_ds = Dataset.from_dict({"path": val_paths, "label": val_labels})

    dataset = DatasetDict({"train": train_ds, "validation": val_ds})
    dataset = dataset.map(preprocess, batched=True, batch_size=16, remove_columns=["path"])
    dataset.set_format("torch")
    return dataset


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    accuracy = float((predictions == labels).mean())
    return {"accuracy": accuracy}


def main():
    print("Model yükleniyor:", BASE_MODEL)
    feature_extractor = AutoFeatureExtractor.from_pretrained(BASE_MODEL)
    model = AutoModelForImageClassification.from_pretrained(
        BASE_MODEL,
        num_labels=2,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )

    paths, labels = load_image_paths()
    dataset = build_dataset(paths, labels, feature_extractor)

    training_args = TrainingArguments(
        output_dir=str(MODEL_OUTPUT),
        num_train_epochs=20,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        greater_is_better=True,
        logging_dir=str(MODEL_OUTPUT / "logs"),
        logging_steps=10,
        save_total_limit=2,
        seed=42,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    print("Fine-tuning başlıyor...")
    trainer.train()

    print(f"Model kaydediliyor: {MODEL_OUTPUT}")
    trainer.save_model(str(MODEL_OUTPUT))
    feature_extractor.save_pretrained(str(MODEL_OUTPUT))
    print("Tamamlandı.")


if __name__ == "__main__":
    main()
