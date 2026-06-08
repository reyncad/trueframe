"""
v2 datasına ek gerçek fotoğraf ekler.

Kaynaklar:
  - data/test/real/      (CelebA-HQ — stüdyo/ünlü fotoğrafları)
  - data/real/           (AI Detection Dataset real klasörü)
  - data/_download/ai_faces/AI-face-detection-Dataset/real/

Tüm dosyalar data/v2/real/'e kopyalanır, duplikasyon korunur.
"""
import shutil
from pathlib import Path

DEST = Path("data/v2/real")
DEST.mkdir(parents=True, exist_ok=True)

SOURCES = [
    (Path("data/test/real"), "celebahq"),
    (Path("data/real"), "aidet"),
    (Path("data/_download/ai_faces/AI-face-detection-Dataset/real"), "aifaces"),
]

EXTS = {".jpg", ".jpeg", ".png", ".webp"}

total = 0
for src_dir, prefix in SOURCES:
    if not src_dir.exists():
        print(f"[ATLANDI] {src_dir} bulunamadı")
        continue

    files = [f for f in src_dir.glob("*") if f.suffix.lower() in EXTS]
    copied = 0
    for i, f in enumerate(files):
        dest_name = f"{prefix}_{i:06d}{f.suffix.lower()}"
        dest_path = DEST / dest_name
        if not dest_path.exists():
            shutil.copy2(f, dest_path)
            copied += 1
    print(f"[{prefix}] {copied} yeni fotoğraf kopyalandı ({len(files)} toplam)")
    total += copied

print(f"\nTamamlandı: {total} yeni fotoğraf eklendi → {DEST}")
print(f"v2/real toplam: {len(list(DEST.glob('*')))}")
