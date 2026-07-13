"""Player-choice popup: a small Toplevel showing the speaker's sprite,
the question, and 2-3 option buttons. The user picks for the character,
and the chosen option's codep deltas + response line are applied by the
caller via the on_choice callback.

Mirrors city_dialog.py / ai_dialog.py's Toplevel pattern (topmost, dark bg).
"""

import tkinter as tk

from PIL import Image, ImageTk

import config

_BG = (0x1a, 0x1a, 0x1e)
_SPRITE_SIZE = config.PLACEHOLDER_SIZE


def _load_sprite(character, mood):
    """Load a sprite PhotoImage composited over the dialog bg (not magenta-
    baked — this is a normal opaque window). Falls back to neutral."""
    folder = config.ASSETS_DIR / character / mood
    from PIL import Image as _Img
    im = None
    try:
        pngs = sorted(p for p in folder.glob("*.png"))
        if pngs:
            im = _Img.open(pngs[0]).convert("RGBA")
    except Exception:
        im = None
    if im is None:
        default = "neutral" if character == "andrew" else "chuckle"
        if mood != default:
            return _load_sprite(character, default)
        return None
    bg_img = _Img.new("RGBA", im.size, _BG + (255,))
    composed = Image.alpha_composite(bg_img, im).convert("RGB")
    return ImageTk.PhotoImage(composed)


def open_choice_dialog(root, character, mood, question, options, on_choice):
    """Build and show a choice popup.

    Args:
        root: the Tk root.
        character: which character is asking (for the sprite).
        mood: the speaker's current mood (for the sprite).
        question: the question text shown above the buttons.
        options: list of dicts, each with a "text" key (button label).
        on_choice: callback(index) called with the chosen option's index.
    """
    win = tk.Toplevel(root)
    win.title("...")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.config(bg="#1a1a1e")

    # Sprite at top.
    photo = _load_sprite(character, mood)
    if photo:
        sprite_lbl = tk.Label(win, image=photo, bg="#1a1a1e", bd=0)
        sprite_lbl.image = photo  # keep ref
        sprite_lbl.pack(padx=20, pady=(12, 4))
    else:
        # Fallback: show the character's display name as text.
        disp = config.CHARACTER_META.get(character, {}).get("display", character)
        tk.Label(win, text=disp, font=(config.UI_FONT, 14, "bold"),
                 fg="#e0e0e0", bg="#1a1a1e").pack(pady=(16, 4))

    # Question text.
    tk.Label(win, text=question, font=(config.UI_FONT, 11),
             fg="#e0e0e0", bg="#1a1a1e", wraplength=320, justify="center",
             height=3).pack(padx=20, pady=(4, 8))

    # Option buttons.
    def pick(idx):
        win.destroy()
        on_choice(idx)

    for i, opt in enumerate(options):
        tk.Button(win, text=opt["text"], width=28,
                  font=(config.UI_FONT, 10),
                  command=lambda i=i: pick(i),
                  bg="#2b2d33", fg="#e0e0e0",
                  activebackground="#3a3f4a",
                  relief="flat", bd=0, padx=12, pady=6).pack(padx=20, pady=3)

    win.protocol("WM_DELETE_WINDOW", lambda: pick(0))  # closing = first option
