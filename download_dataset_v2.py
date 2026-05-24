"""
Dataset indirme ve hazırlama scripti.
Unbiased Tiny GenImage (2.5GB) + GRAVEX-200K (1.9GB) indirir,
mevcut datayla birleştirerek data/v2/ altında düzenler.
"""
import os
import shutil
import subprocess
import random
from pathlib import Path
from PIL import Image

DOWNLOAD_DIR = Path("data/_download/v2")
OUT_REAL = Path("data/v2/real")
OUT_FAKE = Path("data/v2/fake")
KAGGLE = os.path.expanduser("~/Library/Python/3.9/bin/kaggle")

# Her klasörden max kaç görsel alacağız (dengesizliği önlemek için)
MAX_PER_SOURCE = 3000


def run(cmd):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False)
    return result.returncode


def copy_images(src_dir, dst_dir, label, max_count=MAX_PER_SOURCE):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = [f for f in src_dir.rglob("*") if f.suffix.lower() in exts]
    random.shuffle(files)
    files = files[:max_count]

    copied = 0
    skipped = 0
    for f in files:
        try:
            img = Image.open(f).convert("RGB")
            if img.size[0] < 64 or img.size[1] < 64:
                skipped += 1
                continue
            out_path = dst_dir / f"{label}_{copied:06d}{f.suffix.lower()}"
            img.save(out_path)
            copied += 1
        except Exception:
            skipped += 1

    print(f"  [{label}] {copied} kopyalandı, {skipped} atlandı")
    return copied


def main():
    random.seed(42)

    # --- 1. Mevcut veriyi v2'ye kopyala ---
    print("\n=== Mevcut veri kopyalanıyor ===")
    copy_images("data/real", OUT_REAL, "existing_real", max_count=2202)
    copy_images("data/fake", OUT_FAKE, "existing_fake", max_count=1001)

    # --- 2. Unbiased Tiny GenImage indir ---
    print("\n=== Unbiased Tiny GenImage indiriliyor (2.5GB) ===")
    dl_genimage = DOWNLOAD_DIR / "unbiased-tiny-genimage"
    dl_genimage.mkdir(parents=True, exist_ok=True)

    ret = run(
        f"{KAGGLE} datasets download cartografia/unbiased-tiny-genimage "
        f"--path {dl_genimage} --unzip"
    )
    if ret != 0:
        print("  HATA: Unbiased GenImage indirilemedi, atlanıyor.")
    else:
        # Klasör yapısı genellikle: imagenet_ai_0424_wukong/train/ai/ ve /nature/
        for subset_dir in dl_genimage.rglob("ai"):
            if subset_dir.is_dir():
                gen_name = subset_dir.parent.parent.name
                copied = copy_images(subset_dir, OUT_FAKE, f"genimage_{gen_name}")
                if copied > 0:
                    print(f"    Fake kaynak: {gen_name} → {copied} görsel")

        for subset_dir in dl_genimage.rglob("nature"):
            if subset_dir.is_dir():
                gen_name = subset_dir.parent.parent.name
                copied = copy_images(subset_dir, OUT_REAL, f"genimage_real_{gen_name}")
                if copied > 0:
                    print(f"    Real kaynak: {gen_name} → {copied} görsel")

    # --- 3. GRAVEX-200K indir ---
    print("\n=== GRAVEX-200K indiriliyor (1.9GB) ===")
    dl_gravex = DOWNLOAD_DIR / "gravex"
    dl_gravex.mkdir(parents=True, exist_ok=True)

    ret = run(
        f"{KAGGLE} datasets download muhammadbilal6305/200k-real-vs-ai-visuals-by-mbilal "
        f"--path {dl_gravex} --unzip"
    )
    if ret != 0:
        print("  HATA: GRAVEX indirilemedi, atlanıyor.")
    else:
        for real_dir in ["real", "Real", "REAL", "natural", "Natural"]:
            candidate = dl_gravex / real_dir
            if candidate.exists():
                copy_images(candidate, OUT_REAL, "gravex_real")
                break

        for fake_dir in ["ai", "AI", "fake", "Fake", "FAKE", "generated", "Generated"]:
            candidate = dl_gravex / fake_dir
            if candidate.exists():
                copy_images(candidate, OUT_FAKE, "gravex_fake")
                break

        # Alt dizinleri de tara
        for sub in dl_gravex.iterdir():
            if sub.is_dir():
                for real_dir in ["real", "Real", "REAL"]:
                    candidate = sub / real_dir
                    if candidate.exists():
                        copy_images(candidate, OUT_REAL, f"gravex_{sub.name}_real")
                for fake_dir in ["ai", "AI", "fake", "Fake", "generated"]:
                    candidate = sub / fake_dir
                    if candidate.exists():
                        copy_images(candidate, OUT_FAKE, f"gravex_{sub.name}_fake")

    # --- Özet ---
    real_count = len(list(OUT_REAL.glob("*")))
    fake_count = len(list(OUT_FAKE.glob("*")))
    print(f"\n=== Dataset hazır ===")
    print(f"  Real: {real_count} görsel")
    print(f"  Fake: {fake_count} görsel")
    print(f"  Toplam: {real_count + fake_count} görsel")


if __name__ == "__main__":
    main()
