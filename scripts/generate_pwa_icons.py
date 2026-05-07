"""Regenerate pwa-icon-192.png and pwa-icon-512.png from logo.png (for manifest / Android install)."""
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("Install Pillow: pip install Pillow", file=sys.stderr)
    sys.exit(1)

# Allow large source logos without DecompressionBombError
Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "logo.png")
OUT192 = os.path.join(ROOT, "pwa-icon-192.png")
OUT512 = os.path.join(ROOT, "pwa-icon-512.png")


def main():
    if not os.path.isfile(SRC):
        print(f"Missing {SRC}", file=sys.stderr)
        sys.exit(1)
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    L = (w - side) // 2
    T = (h - side) // 2
    sq = img.crop((L, T, L + side, T + side))
    sq.resize((192, 192), Image.Resampling.LANCZOS).save(OUT192, optimize=True)
    sq.resize((512, 512), Image.Resampling.LANCZOS).save(OUT512, optimize=True)
    print(f"Wrote {OUT192} and {OUT512}")


if __name__ == "__main__":
    main()
