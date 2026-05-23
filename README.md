# TrueFrame

A deep learning tool that detects whether an image is real or AI-generated.

Fine-tuned from [dima806/ai_vs_real_image_detection](https://huggingface.co/dima806/ai_vs_real_image_detection) on a curated dataset of real faces (CelebA-HQ) and AI-generated faces.

## Features

- **Web interface** — upload a photo and get an instant verdict
- **Fine-tuned ViT model** — trained on 3,200+ real/fake face pairs
- **Confidence scores** — shows probability breakdown for both classes
- **CLI evaluation** — batch test entire folders or single images

## Project Structure

```
TrueFrame/
├── apps/
│   └── detection/
│       └── services.py      # Model inference service
├── detector/                # Django web app
│   ├── views.py
│   ├── urls.py
│   └── templates/
├── trueframe/               # Django project config
├── data/                    # Training data (not tracked)
│   ├── real/
│   └── fake/
├── models/                  # Saved model weights (not tracked)
├── fine_tune.py             # Fine-tuning script
├── evaluate.py              # Evaluation & single-image inference
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

## Training

Place images in `data/real/` and `data/fake/`, then run:

```bash
python fine_tune.py
```

Training uses HuggingFace `Trainer` with early stopping. Base model: ViT fine-tuned for AI vs real detection.

## Web Interface

```bash
python manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000) — upload any face photo to analyze it.

## Evaluation

```bash
# Test entire folder
python evaluate.py

# Test a single image
python evaluate.py --image path/to/photo.jpg
```

## Dataset

- **Real:** CelebA-HQ (256×256) — high-quality celebrity faces
- **Fake:** AI-generated faces dataset — Stable Diffusion / DALL-E generated faces

## Results

| Metric   | Score  |
|----------|--------|
| Accuracy | 100%   |
| Val Loss | 0.0006 |

Evaluated on held-out validation split (20% of training data).

## Requirements

- Python 3.9+
- PyTorch 2.0+
- Transformers 4.35+
- Django 4.2+
