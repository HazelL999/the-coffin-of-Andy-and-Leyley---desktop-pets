"""Backpack window: a small grid showing the items the player carries.

Items are loaded from the backpack folder (PNG sprites). The Talisman shows
a charge count (×N) and can be clicked to use -- consuming one charge and
popping a vision image. Dolls can be right-clicked for a "Use it" menu that
triggers character-specific effects; the Pistol, Mop, and Flower show lore
captions on click.
"""

import math

from PIL import Image, ImageDraw, ImageTk

import config
import theme

# Cell background the sprite sits on. Items are alpha-composited over this
# color (NOT baked over the magenta transparent color): the backpack is an
# opaque UI window with no -transparentcolor, so baking to magenta would
# leave visible purple fringe around semi-transparent sprite edges -- the
# same class of bug as the pet sprite fringe, but here magenta can't be
# matched away because the window isn't transparent.
CELL_BG = theme.BG  # near-black cell, matches the dialog/panel theme


class BackpackItem:
    """One item in the backpack: name, sprite path, whether it's usable, an
    optional persistent count key ('talisman' / 'soul' / 'flower' / 'coin'),
    and an optional max_px to cap the sprite's largest dimension (for items
    that are too large or too wide at the default 95px scale)."""
    def __init__(self, name, path, usable=False, count=None, max_px=None):
        self.name = name
        self.path = path
        self.usable = usable  # only talisman is usable for now
        self.count = count    # None = display-only; else a persistent count key
        self.max_px = max_px   # None = default 95px cap; else this px cap


class Backpack:
    """A Toplevel window with a grid of item sprites."""

    def __init__(self, root, items, talisman_charges=0, soul_count=0,
                 flower_count=0, coin_count=0, on_use_talisman=None,
                 on_use_doll=None):
        self.root = root
        self.items = items
        self.talisman_charges = talisman_charges
        self.soul_count = soul_count
        self.flower_count = flower_count
        self.coin_count = coin_count
        self.on_use_talisman = on_use_talisman
        self.on_use_doll = on_use_doll  # callback(doll_name) -> trigger effect
        self.win = None
        self._photos = []          # keep PhotoImage refs alive
        self._count_labels = {}    # count-key -> Label ("talisman"/"soul"/"flower"/"coin")
        self._cell_frames = {}     # item name -> cell Frame
        self._photos_by_name = {}  # item name -> PhotoImage
        self._status_var = None    # StringVar for the bottom status bar
        self._status_bar = None    # bottom status Label
        self._caption_after = None  # after id to cancel a pending caption clear

    def start(self):
        import tkinter as tk

        cell = 120  # cell size (sprite ~100px + padding)
        cols = len(self.items)
        win_w = cell * cols + 20
        win_h = cell + 60  # cell + bottom status bar
        self.win = tk.Toplevel(self.root)
        self.win.title("Backpack")
        self.win.geometry(f"{win_w}x{win_h}")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        # Use a normal opaque window (like the control panel) so it's
        # clearly a UI surface, not a transparent sprite.
        self.win.config(bg=theme.BG_ELEVATED)

        frame = tk.Frame(self.win, bg=theme.BG_ELEVATED)
        frame.pack()

        # Bottom status bar -- shows item captions (click notes) here so they're
        # always visible, not fighting with sprite z-order inside the cells.
        self._status_var = tk.StringVar(value="")
        self._status_bar = tk.Label(self.win, textvariable=self._status_var,
                                    font=(config.UI_FONT, 9), fg=theme.FG,
                                    bg=theme.BG_ELEVATED, anchor="center",
                                    wraplength=win_w - 20, height=2)
        self._status_bar.pack(side="bottom", fill="x", padx=4)

        for i, item in enumerate(self.items):
            cell_frame = tk.Frame(frame, bg=CELL_BG, width=cell, height=cell)
            cell_frame.pack(side="left", padx=4, pady=4)
            cell_frame.pack_propagate(False)
            self._cell_frames[item.name] = cell_frame

            count_key = item.count  # None | "talisman" | "soul" | "flower"
            # Load, scale, and alpha-composite over the cell background so
            # semi-transparent sprite edges blend smoothly into CELL_BG
            # (no purple magenta fringe, no jaggy alpha binarization).
            photo = None
            if item.path:
                try:
                    im = Image.open(item.path).convert("RGBA")
                    w, h = im.size
                    # Contain-mode scale: fit within the larger of (max_px or
                    # 95)px on BOTH axes, so wide sprites (pistol) or tall
                    # sprites (soul) never overflow the 120px cell. Items with
                    # a max_px (coin/pistol) are capped even smaller.
                    cap = item.max_px or 95
                    scale = min(cap / w, cap / h)
                    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
                    im = im.resize((nw, nh), Image.LANCZOS)
                    bg = Image.new("RGBA", im.size, config.hex_to_rgb(CELL_BG) + (255,))
                    im = Image.alpha_composite(bg, im).convert("RGB")
                    photo = ImageTk.PhotoImage(im)
                except Exception:
                    photo = None
            else:
                # No external sprite -- draw a built-in placeholder (soul/flower).
                photo = self._placeholder_photo(item.name, count_key)

            if photo is not None:
                self._photos.append(photo)
                self._photos_by_name[item.name] = photo
                lbl = tk.Label(cell_frame, image=photo, bg=CELL_BG)
                lbl.place(relx=0.5, rely=0.40, anchor="center")
                if item.usable:
                    lbl.bind("<Button-1>",
                             lambda e, it=item: self._on_item_click(it))
                # Dolls: right-click -> "Use it" menu -> triggers the doll's
                # character-specific effect (dialogue / codependency).
                if item.name in ("Andy's doll", "Leyley's doll"):
                    lbl.bind("<Button-3>",
                             lambda e, it=item: self._on_doll_rightclick(e, it))
            else:
                tk.Label(cell_frame, text="?", font=(config.UI_FONT, 20),
                         fg=theme.FG_DIM, bg=CELL_BG
                         ).place(relx=0.5, rely=0.45, anchor="center")

            name_lbl = tk.Label(cell_frame, text=item.name,
                                font=(config.UI_FONT, 7), fg=theme.FG_DIM,
                                bg=CELL_BG)
            name_lbl.place(relx=0.5, rely=0.96, anchor="s")
            if item.usable:
                name_lbl.bind("<Button-1>",
                              lambda e, it=item: self._on_item_click(it))
            if item.name in ("Andy's doll", "Leyley's doll"):
                name_lbl.bind("<Button-3>",
                              lambda e, it=item: self._on_doll_rightclick(e, it))

            # Charge/count label for items that carry a persistent count
            # (talisman / soul / flower / coin), placed at the cell's top-right.
            if count_key:
                n = (self.talisman_charges if count_key == "talisman"
                     else self.soul_count if count_key == "soul"
                     else self.flower_count if count_key == "flower"
                     else self.coin_count)
                lbl2 = tk.Label(
                    cell_frame, text=f"×{n}",
                    font=(config.UI_FONT, 9, "bold"), fg=theme.ACCENT, bg=CELL_BG)
                lbl2.place(relx=1.0, rely=0.0, x=-4, y=2, anchor="ne")
                self._count_labels[count_key] = lbl2

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

    def update_talisman_count(self, n):
        self.talisman_charges = n
        self._set_count("talisman", n)

    def update_soul_count(self, n):
        self.soul_count = n
        self._set_count("soul", n)

    def update_flower_count(self, n):
        self.flower_count = n
        self._set_count("flower", n)

    def update_coin_count(self, n):
        self.coin_count = n
        self._set_count("coin", n)

    def _set_count(self, key, n):
        lbl = self._count_labels.get(key)
        if lbl and self.win:
            try:
                lbl.config(text=f"×{n}")
            except Exception:
                pass

    def _placeholder_photo(self, name, count_key):
        """A built-in PIL placeholder sprite for count items with no external
        PNG (soul = white teardrop, flower = red petals). Composited over
        CELL_BG so edges blend. Replace with real art later by setting path
        in config.BACKPACK_ITEMS."""
        import math
        size = 95
        bg_rgb = config.hex_to_rgb(CELL_BG)
        img = Image.new("RGBA", (size, size), bg_rgb + (255,))
        d = ImageDraw.Draw(img)
        cx = cy = size / 2
        if count_key == "soul":
            # white teardrop
            w, h = 22, 60
            head_cy = cy - h * 0.18
            pts = [
                cx + 8, cy + h * 0.5,
                cx + w * 0.85, head_cy + h * 0.95 * 0.3 + (h * 0.5 - head_cy - h * 0.95 * 0.3) * 0.45,
                cx + w, head_cy + h * 0.95 * 0.3,
                cx + w * 0.55, head_cy - h * 0.55,
                cx - w * 0.55, head_cy - h * 0.55,
                cx - w, head_cy + h * 0.95 * 0.3,
                cx - w * 0.85, head_cy + h * 0.95 * 0.3 + (h * 0.5 - head_cy - h * 0.95 * 0.3) * 0.45,
                cx + 8 - w * 0.85 * 0.3, cy + h * 0.5,
            ]
            d.polygon(pts, fill=(200, 216, 224))
            d.polygon(pts, fill=(255, 255, 255))
            er = w * 0.12
            for ex in (cx - w * 0.22, cx + w * 0.22):
                d.ellipse([ex - er, cy - er, ex + er, cy + er],
                          fill=(168, 216, 240))
        elif count_key == "flower":
            # red flower: 6 tapered petals around a center
            r = 18
            for i in range(6):
                a = math.radians(i * 60)
                ux, uy = math.cos(a), math.sin(a)
                px, py = -math.sin(a), math.cos(a)
                bx, by = cx, cy
                tx, ty = cx + r * ux, cy + r * uy
                d.polygon([(bx - px * 5, by - py * 5),
                           (tx - px * 7, ty - py * 7),
                           (tx + px * 7, ty + py * 7),
                           (bx + px * 5, by + py * 5)],
                          fill="#cc2222")
                d.ellipse([tx - 7, ty - 7, tx + 7, ty + 7], fill="#cc2222")
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill="#5a1a1a")
        return ImageTk.PhotoImage(img)

    # ---------- doll right-click "Use it" ----------

    def _on_doll_rightclick(self, e, item):
        """Right-click a doll -> popup menu with 'Use it'. Clicking it triggers
        the doll's effect via on_use_doll (handled in main.py)."""
        import tkinter as tk
        if not self.win or not self.on_use_doll:
            return
        menu = theme.style_menu(tk.Menu(self.win, tearoff=0))
        menu.add_command(label="Use it",
                         command=lambda it=item: self._use_doll(it))
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    def _use_doll(self, item):
        """Called from the right-click 'Use it' menu -- delegate to main."""
        if self.on_use_doll:
            try:
                self.on_use_doll(item.name)
            except Exception:
                pass

    def _show_item_caption(self, item, text, ms=3000):
        """Show a caption text in the bottom status bar, auto-clear after ms."""
        if not self.win:
            return
        # Cancel a pending clear from a previous caption.
        if self._caption_after is not None:
            try:
                self.win.after_cancel(self._caption_after)
            except Exception:
                pass
            self._caption_after = None
        self._status_var.set(text)
        self._caption_after = self.win.after(ms, self._clear_caption)

    def _clear_caption(self):
        try:
            self._status_var.set("")
        except Exception:
            pass
        self._caption_after = None

    def _on_item_click(self, item):
        """Handle a usable item click. Routes by item name. Wrapped in
        try/except so a stray exception (e.g. a dead window ref) never bubbles
        up to Tk's event loop and freezes the backpack -- that was the cause of
        the intermittent 'can't reopen' bug."""
        if not item.usable or not self.win:
            return
        name = item.name
        try:
            if name == "Talisman":
                if self.talisman_charges <= 0:
                    # Flash the talisman charge label red briefly to signal
                    # "no charges" (the click was received, not dead).
                    lbl = self._count_labels.get("talisman")
                    if lbl and self.win:
                        try:
                            orig = theme.ACCENT
                            lbl.config(fg="#e05050")
                            self.win.after(250, lambda: lbl.config(fg=orig))
                        except Exception:
                            pass
                    return
                if self.on_use_talisman:
                    self.on_use_talisman()
                return
            if name in ("Andy's doll", "Leyley's doll"):
                self._show_item_caption(item, "Leyley's birthday present")
                return
            if name == "Flower":
                # Interaction design is TBD; this placeholder keeps the click
                # path wired so the real interaction drops in here later.
                self._show_item_caption(item, "Something is waiting to bloom here...")
                return
            if name == "Pistol":
                self._show_item_caption(item, "Can be used for self-defense -- or for killing.")
                return
            if name == "Mop":
                self._show_item_caption(item, "The best thing in the whole world.")
                return
        except Exception:
            pass

    def _on_close(self):
        """Destroy the backpack window and reset all internal state so a fresh
        open can recreate everything cleanly. Called via WM_DELETE_WINDOW."""
        # Cancel any pending callbacks.
        if self._caption_after is not None:
            try:
                if self.win:
                    self.win.after_cancel(self._caption_after)
            except Exception:
                pass
            self._caption_after = None
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        self._status_var = None
        self._status_bar = None
        self._photos = []
        self._photos_by_name = {}
        self._cell_frames = {}
        self._count_labels = {}
