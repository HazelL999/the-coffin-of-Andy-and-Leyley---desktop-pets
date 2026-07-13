"""Asset loading: folders -> renderable frames, never failing.

For each (character, mood) we look in assets/<character>/<mood>/ and produce a
FrameSet with both facing directions. Missing/empty folders yield a drawn
placeholder so the app runs with zero assets. PhotoImage references are retained
to defeat Pillow's garbage collection.

Windows-specific: each frame is alpha-baked over the transparent color so
transparent regions become EXACTLY magenta (matches -transparentcolor, no fringe).
"""

import sys

from PIL import Image, ImageTk, ImageDraw, ImageFont

import config
import expressions
import platform_utils


class FrameSet:
    """Frames for one (character, mood). Animated if len > 1."""

    def __init__(self, face_right, face_left, frame_durations, is_placeholder):
        # Lists of ImageTk.PhotoImage; keep strong refs alive.
        self.face_right = face_right
        self.face_left = face_left
        self.frame_durations = frame_durations  # ms per frame
        self.is_placeholder = is_placeholder

    def frames(self, facing):
        return self.face_right if facing == "right" else self.face_left

    def __len__(self):
        return len(self.face_right)


# Candidate TrueType fonts for placeholder rendering, tried in order. arial is
# Windows-native; Helvetica is macOS-native; DejaVuSans is near-universal on
# Linux. Pillow's truetype() raises on a missing font, so the first hit wins
# and we fall back to the bitmap default if none are present.
_PLACEHOLDER_FONT_CANDIDATES = (
    "arial.ttf", "Arial.ttf", "Helvetica.ttf", "HelveticaNeue.ttf",
    "DejaVuSans.ttf", "Arial Unicode.ttf",
)


def _load_placeholder_font(size):
    """Try known system fonts for placeholder text; fall back to Tk default."""
    for name in _PLACEHOLDER_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, int(size))
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _bake_for_windows(img, transparent_rgb, alpha_threshold=128):
    """Composite over the transparent color and crush alpha to 1-bit so the
    transparent region becomes EXACTLY the transparent color (no AA fringe).

    Anti-aliased sprite edges have semi-transparent pixels (0<alpha<255). A
    plain alpha_composite blends those with the magenta background, producing
    non-magenta tinted pixels that -transparentcolor won't match -> visible
    purple fringe. We binarize alpha first: pixels >= threshold become fully
    opaque (keep true sprite color), below become fully transparent (exact
    magenta). Edges are then either pure-magenta or pure-sprite-color, so
    -transparentcolor matches cleanly.
    """
    img = img.convert("RGBA")
    # Binarize alpha: separate the mask so we keep the original RGB where opaque.
    r, g, b, a = img.split()
    mask = a.point(lambda v: 255 if v >= alpha_threshold else 0)
    # Where opaque: original sprite RGB. Where transparent: transparent color.
    bg = Image.new("RGB", img.size, transparent_rgb)
    sprite_rgb = img.convert("RGB")
    composed = Image.composite(sprite_rgb, bg, mask)
    return composed


def _flip(img):
    return img.transpose(Image.FLIP_LEFT_RIGHT)


def _load_frames_from_folder(folder):
    """Return list of (PIL.Image, duration_ms) for a mood folder, or None.

    Rules: PNG frames (lexical order) win; else one GIF (seek frames).
    """
    pngs = sorted([p for p in folder.glob("*.png")])
    gifs = sorted([p for p in folder.glob("*.gif")])

    images = []  # list of (PIL.Image RGBA, duration_ms)

    if pngs:
        for p in pngs:
            try:
                im = Image.open(p)
                images.append((im.convert("RGBA"), config.ANIM_FRAME_DEFAULT_MS))
            except Exception:
                continue
        if images:
            return images

    if gifs:
        try:
            with Image.open(gifs[0]) as im:
                idx = 0
                while True:
                    try:
                        im.seek(idx)
                    except EOFError:
                        break
                    duration = im.info.get("duration") or config.ANIM_FRAME_DEFAULT_MS
                    images.append((im.convert("RGBA").copy(), duration))
                    idx += 1
        except Exception:
            pass
        if images:
            return images

    return None


def _make_placeholder(character, mood, size, transparent_rgb, bake_windows):
    """Draw a rounded-rect placeholder with the character's initial + mood."""
    meta = config.CHARACTER_META.get(character, {})
    color = meta.get("color", (120, 120, 120))
    initial = meta.get("initial", character[0].upper() if character else "?")
    display = meta.get("display", character.title())

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # rounded rectangle body
    pad = 6
    rect = [pad, pad, size - pad, size - pad]
    d.rounded_rectangle(rect, radius=22, fill=color + (255,))

    # mood-colored stripe to hint at expression
    mood_colors = {
        "happy": (255, 215, 0), "angry": (220, 60, 60), "sad": (90, 140, 220),
        "scared": (180, 180, 255), "annoyed": (200, 120, 40), "sinister": (80, 0, 80),
        "chuckle": (255, 180, 220), "thinking": (120, 200, 200), "surprised": (255, 255, 255),
        "neutral": (220, 220, 220),
    }
    accent = mood_colors.get(mood, (255, 255, 255))
    d.rounded_rectangle([pad, pad, size - pad, pad + 10], radius=5, fill=accent + (255,))

    # initial centered
    font = _load_placeholder_font(int(size * 0.42))
    text = initial
    bbox = d.textbbox((0, 0), text, font=font) if font else (0, 0, 10, 10)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] + 4
    d.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)

    # mood label at bottom
    small = _load_placeholder_font(14)
    if small:
        mb = d.textbbox((0, 0), mood, font=small)
        mw = mb[2] - mb[0]
        d.text(((size - mw) // 2 - mb[0], size - 22), mood,
               fill=(255, 255, 255, 255), font=small)
    return img


def _to_photoimages(pil_imgs, transparent_rgb, bake_windows):
    """Convert a list of (PIL RGBA, duration_ms) to a FrameSet's lists.

    Produces face_right (as-is) and face_left (flipped). On Windows, alpha-bake.
    Holds all PhotoImage refs in the returned lists.
    """
    right = []
    left = []
    durations = []
    for im, dur in pil_imgs:
        if bake_windows:
            # Bake once, then flip the baked result: alpha binarization +
            # composite-to-magenta is left/right symmetric, so flipping
            # before vs after baking yields identical pixels. Saves one
            # bake per frame (half the load-time cost on Windows).
            im_r = _bake_for_windows(im, transparent_rgb)
            im_l = _flip(im_r)
        else:
            im_r = im.convert("RGBA")
            im_l = _flip(im_r)
        right.append(ImageTk.PhotoImage(im_r))
        left.append(ImageTk.PhotoImage(im_l))
        durations.append(dur)
    return right, left, durations


class AssetLoader:
    """Loads and caches FrameSets per (character, mood). Never raises."""

    def __init__(self, assets_dir=None, transparent_color=None, platform=None):
        self.assets_dir = assets_dir or config.ASSETS_DIR
        tc = transparent_color or config.TRANSPARENT_COLOR
        self.transparent_rgb = config.hex_to_rgb(tc)
        self.bake_windows = platform_utils.is_windows() if platform is None else (platform == "windows")
        self._cache = {}   # (character, mood) -> FrameSet

    def load(self, character, mood):
        key = (character, mood)
        if key in self._cache:
            return self._cache[key]

        folder = self.assets_dir / character / mood
        frames = None
        try:
            if folder.is_dir():
                frames = _load_frames_from_folder(folder)
        except Exception:
            frames = None

        if not frames:
            # placeholder — one frame, still gets facing flip (symmetric, no-op)
            ph = _make_placeholder(character, mood, config.PLACEHOLDER_SIZE,
                                   self.transparent_rgb, self.bake_windows)
            right, left, durations = _to_photoimages(
                [(ph, config.ANIM_FRAME_DEFAULT_MS)],
                self.transparent_rgb, self.bake_windows)
            fs = FrameSet(right, left, durations, is_placeholder=True)
        else:
            right, left, durations = _to_photoimages(
                frames, self.transparent_rgb, self.bake_windows)
            fs = FrameSet(right, left, durations, is_placeholder=False)

        self._cache[key] = fs
        return fs

    def load_character(self, character):
        """Preload all moods for a character (best-effort)."""
        for mood in expressions.MOODS:
            try:
                self.load(character, mood)
            except Exception:
                pass
