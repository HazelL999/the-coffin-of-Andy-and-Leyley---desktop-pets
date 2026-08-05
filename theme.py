"""Centralized dark theme for every opaque UI surface (dialogs, menus, the
control panel, buttons). Single source of truth so the look is consistent
across Win + macOS.

The strict black bg + near-white text exists specifically because macOS Aqua
renders native tk.Button/tk.Menu bevels that IGNORE bg/fg unless overridden
— left to the theme default, buttons come out a washed grey that makes text
barely readable. style_button forces relief=flat/bd=0/highlightthickness=0
to suppress that bevel; style_menu sets bg/fg/activebackground (Mac menus
are native but honor those). Transparent sprite windows and the speech
bubble (white bg, dark text) are NOT UI surfaces and stay untouched.

Also hosts the shared rounded-rectangle geometry helper used by both the
desktop pet speech bubble (pet.py) and the AI-chat dialog bubble
(ai_dialog.py) — previously duplicated in both.
"""

import math

from PIL import Image, ImageTk

BG = "#141414"            # near-black panel/dialog background
BG_ELEVATED = "#1f1f24"   # buttons / listbox / cell frames (slightly lifted)
FG = "#f0f0f0"            # near-white primary text
FG_DIM = "#9aa0a6"        # secondary text / hints
ACCENT = "#ffd24a"        # talisman count / status accents (kept from before)
SELECT = "#2f3338"        # listbox selection / button active bg
BORDER = "#3a3f4a"        # outlines

# Dialog background as an RGB tuple, for alpha-compositing sprites over it.
# Equals BG above; opaque dialogs (AI chat, choice popup) composite transparent
# sprite art over this color (NOT magenta-baked — that's only for transparent
# pet windows). Shared by ai_dialog and choice_dialog.
BG_RGB = (0x14, 0x14, 0x14)

# Per-character default mood when the requested mood has no art folder.
_DEFAULT_MOOD = {"andrew": "neutral", "ashley": "chuckle"}


def sprite_over_bg(character, mood, bg_rgb=BG_RGB):
    """Load a sprite PhotoImage for (character, mood), alpha-composited over an
    opaque dialog bg color (not magenta-baked — this is for normal opaque
    windows like the AI-chat / choice dialogs).

    Reads the first PNG in assets/<character>/<mood>/. Falls back to the
    character's default mood (neutral/chuckle) if the requested mood has no
    art; returns None if even the default is missing. Caching is the caller's
    job — this always builds a fresh PhotoImage."""
    import config  # local import: config imports nothing from theme (no cycle)
    folder = config.ASSETS_DIR / character / mood
    im = None
    try:
        pngs = sorted(p for p in folder.glob("*.png"))
        if pngs:
            im = Image.open(pngs[0]).convert("RGBA")
    except Exception:
        im = None
    if im is None:
        default = _DEFAULT_MOOD.get(character, "neutral")
        if mood != default:
            return sprite_over_bg(character, default, bg_rgb)
        return None
    bg_img = Image.new("RGBA", im.size, bg_rgb + (255,))
    composed = Image.alpha_composite(bg_img, im).convert("RGB")
    return ImageTk.PhotoImage(composed)


def round_rect_points(x0, y0, x1, y1, r, n=8):
    """Flat point list [x0,y0, x1,y1, ...] for a rounded-rectangle polygon,
    sampling n+1 arc points per corner. Suitable for canvas.create_polygon
    with smooth=False. Shared by pet.py and ai_dialog.py speech bubbles."""
    pts = []
    # top-right corner: center (x1-r, y0+r), 0->90deg
    cx, cy = x1 - r, y0 + r
    for i in range(n + 1):
        a = math.pi / 2 * (i / n)
        pts.append(cx + r * math.sin(a))
        pts.append(cy - r * math.cos(a))
    # bottom-right corner: center (x1-r, y1-r), 90->180
    cx, cy = x1 - r, y1 - r
    for i in range(n + 1):
        a = math.pi / 2 * (i / n)
        pts.append(cx + r * math.cos(a))
        pts.append(cy + r * math.sin(a))
    # bottom-left corner: center (x0+r, y1-r), 180->270
    cx, cy = x0 + r, y1 - r
    for i in range(n + 1):
        a = math.pi / 2 * (i / n)
        pts.append(cx - r * math.sin(a))
        pts.append(cy + r * math.cos(a))
    # top-left corner: center (x0+r, y0+r), 270->360
    cx, cy = x0 + r, y0 + r
    for i in range(n + 1):
        a = math.pi / 2 * (i / n)
        pts.append(cx - r * math.cos(a))
        pts.append(cy - r * math.sin(a))
    return pts


def style_button(btn):
    """Force a tk.Button to a flat dark look (suppresses the Mac Aqua native
    bevel that ignores bg/fg). Call right after constructing the button:
        style_button(tk.Button(parent, text=..., command=...)).pack(...)
    Returns the button so it can be chained."""
    try:
        btn.config(bg=BG_ELEVATED, fg=FG, activebackground=SELECT,
                   activeforeground=FG, relief="flat", bd=0,
                   highlightthickness=0, borderwidth=0)
    except Exception:
        pass
    return btn


def style_menu(menu):
    """Force a tk.Menu (right-click menu / cascade submenu) to dark bg +
    white text. macOS menus are native but honor bg/fg/activebackground;
    Windows menus honor them fully."""
    try:
        menu.config(bg=BG, fg=FG, activebackground=BG_ELEVATED,
                    activeforeground=FG, borderwidth=0)
    except Exception:
        pass
    return menu
