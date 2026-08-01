"""Build the app icon: composite Andrew + Ashley neutral poses side by side
into a square transparent canvas, then emit a multi-size Windows .ico + a
high-res PNG for the Mac .icns source.

Layout: a SQUARE canvas (1024x1024). Left half = Andrew, right half = Ashley.
Each sprite is a portrait (~0.7:1), so two side-by-side naturally fill a near-
square frame without distortion — no vertical squash. Figures are scaled to the
canvas height with a small margin, bottom-anchored, each centered in its half.

Output:
  build/icon_1024.png   — 1024x1024 square, the master source (Mac .icns + re-render)
  build/app_icon.ico    — multi-size 16/32/48/64/128/256 Windows icon
"""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDREW = os.path.join(ROOT, "Andrew-sprites", "neutral-1.png")
ASHLEY = os.path.join(ROOT, "Ashley-sprites", "neutral-1.png")
OUT = os.path.join(ROOT, "build")
os.makedirs(OUT, exist_ok=True)

CANVAS = 1024               # square master
MARGIN = 40                 # top/bottom inset so figures don't touch edges
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def fit_half(src_path, half_w, full_h):
    """Scale a portrait sprite to height (full_h - 2*MARGIN), keep aspect,
    center it horizontally within a half-width canvas, bottom-anchored."""
    im = Image.open(src_path).convert("RGBA")
    w, h = im.size
    target_h = full_h - 2 * MARGIN
    scale = target_h / max(h, w)
    im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                   Image.LANCZOS)
    canvas = Image.new("RGBA", (half_w, full_h), (0, 0, 0, 0))
    x = (half_w - im.width) // 2
    y = full_h - MARGIN - im.height   # bottom-anchored
    canvas.alpha_composite(im, (x, y))
    return canvas


def main():
    half = CANVAS // 2
    andy = fit_half(ANDREW, half, CANVAS)
    ash = fit_half(ASHLEY, half, CANVAS)

    master = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    master.alpha_composite(andy, (0, 0))
    master.alpha_composite(ash, (half, 0))

    master.save(os.path.join(OUT, "icon_1024.png"))
    master.save(os.path.join(OUT, "app_icon.ico"), format="ICO",
                sizes=[(s, s) for s in ICO_SIZES])

    print("Wrote:")
    for f in ("icon_1024.png", "app_icon.ico"):
        p = os.path.join(OUT, f)
        print(f"  {p}  ({os.path.getsize(p)} bytes)")


if __name__ == "__main__":
    main()
