"""Backpack window: a small grid showing the items the player carries.

Items are loaded from the backpack folder (PNG sprites). The Talisman shows
a charge count (×N) and can be clicked to use — consuming one charge and
popping a vision image. Other items (rabbit dolls) are display-only for now.
"""

from PIL import Image, ImageTk

import config

# Cell background the sprite sits on. Items are alpha-composited over this
# color (NOT baked over the magenta transparent color): the backpack is an
# opaque UI window with no -transparentcolor, so baking to magenta would
# leave visible purple fringe around semi-transparent sprite edges — the
# same class of bug as the pet sprite fringe, but here magenta can't be
# matched away because the window isn't transparent.
CELL_BG = "#1e2026"


class BackpackItem:
    """One item in the backpack: name, sprite path, and whether it's usable."""
    def __init__(self, name, path, usable=False):
        self.name = name
        self.path = path
        self.usable = usable  # only talisman is usable for now


class Backpack:
    """A Toplevel window with a grid of item sprites."""

    def __init__(self, root, items, talisman_charges=0, on_use_talisman=None):
        self.root = root
        self.items = items
        self.talisman_charges = talisman_charges
        self.on_use_talisman = on_use_talisman
        self.win = None
        self._photos = []          # keep PhotoImage refs alive
        self._charge_label = None  # the "×N" label for talisman

    def start(self):
        import tkinter as tk

        cell = 120  # cell size (sprite ~100px + padding)
        cols = len(self.items)
        win_w = cell * cols + 20
        win_h = cell + 40
        self.win = tk.Toplevel(self.root)
        self.win.title("Backpack")
        self.win.geometry(f"{win_w}x{win_h}")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        # Use a normal opaque window (like the control panel) so it's
        # clearly a UI surface, not a transparent sprite.
        self.win.config(bg="#2b2d33")

        tk.Label(self.win, text="Backpack", font=(config.UI_FONT, 10, "bold"),
                 fg="#e0e0e0", bg="#2b2d33").pack(pady=(4, 2))

        frame = tk.Frame(self.win, bg="#2b2d33")
        frame.pack()

        for i, item in enumerate(self.items):
            cell_frame = tk.Frame(frame, bg=CELL_BG, width=cell, height=cell)
            cell_frame.pack(side="left", padx=4, pady=4)
            cell_frame.pack_propagate(False)

            # Load, scale, and alpha-composite over the cell background so
            # semi-transparent sprite edges blend smoothly into CELL_BG
            # (no purple magenta fringe, no jaggy alpha binarization).
            photo = None
            try:
                im = Image.open(item.path).convert("RGBA")
                w, h = im.size
                scale = 95 / h
                im = im.resize((max(1, round(w * scale)), 95), Image.LANCZOS)
                bg = Image.new("RGBA", im.size, config.hex_to_rgb(CELL_BG) + (255,))
                im = Image.alpha_composite(bg, im).convert("RGB")
                photo = ImageTk.PhotoImage(im)
            except Exception:
                pass

            if photo is not None:
                self._photos.append(photo)
                lbl = tk.Label(cell_frame, image=photo, bg=CELL_BG)
                lbl.pack(pady=(8, 0))
                if item.usable:
                    lbl.bind("<Button-1>", lambda e: self._on_item_click(item))
            else:
                tk.Label(cell_frame, text="?", font=(config.UI_FONT, 20),
                         fg="#888", bg=CELL_BG).pack(pady=(20, 0))

            name_lbl = tk.Label(cell_frame, text=item.name,
                                font=(config.UI_FONT, 7), fg="#bbb",
                                bg=CELL_BG)
            name_lbl.pack()
            if item.usable:
                name_lbl.bind("<Button-1>", lambda e: self._on_item_click(item))

            # Charge count for talisman — placed at the cell's top-right corner.
            if item.usable:
                self._charge_label = tk.Label(
                    cell_frame, text=f"×{self.talisman_charges}",
                    font=(config.UI_FONT, 9, "bold"), fg="#ffd24a", bg=CELL_BG)
                self._charge_label.place(relx=1.0, rely=0.0, x=-4, y=2,
                                         anchor="ne")

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

    def update_talisman_count(self, n):
        self.talisman_charges = n
        if self._charge_label and self.win:
            try:
                self._charge_label.config(text=f"×{n}")
            except Exception:
                pass

    def _on_item_click(self, item):
        if item.usable and self.on_use_talisman:
            self.on_use_talisman()

    def _on_close(self):
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
