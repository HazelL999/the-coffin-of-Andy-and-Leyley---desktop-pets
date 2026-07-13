"""Vision window: a popup showing a randomly selected vision image, full-screen
width. Shown when the talisman is used from the backpack.

The vision images live in the project's `vision/` directory (see
config.VISION_DIR). They are wide (1000-2160px) transparent PNGs. The window
scales to ~80% screen width, shows the image centered, and auto-closes after 5
seconds (or on click).
"""

import os

from PIL import Image, ImageTk


class VisionWindow:
    """A transient popup showing one vision image."""

    def __init__(self, root, image_path, auto_close_ms=5000):
        self.root = root
        self.image_path = image_path
        self.auto_close_ms = auto_close_ms
        self.win = None
        self._photo = None  # keep ref
        self._close_after_id = None

    def show(self):
        import tkinter as tk
        import platform_utils
        import config
        from asset_loader import _bake_for_windows

        try:
            im = Image.open(self.image_path).convert("RGBA")
        except Exception:
            return

        # Scale to ~80% of screen width, keep aspect.
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = int(sw * 0.8)
        w, h = im.size
        scale = target_w / w
        new_w = max(1, round(w * scale))
        new_h = max(1, round(h * scale))
        # Don't exceed 85% screen height.
        if new_h > sh * 0.85:
            scale2 = (sh * 0.85) / new_h
            new_w = max(1, round(new_w * scale2))
            new_h = max(1, round(new_h * scale2))
        im = im.resize((new_w, new_h), Image.LANCZOS)

        # Bake over transparent color for Windows (no fringe).
        if platform_utils.is_windows():
            im = _bake_for_windows(im, config.hex_to_rgb(config.TRANSPARENT_COLOR))
        self._photo = ImageTk.PhotoImage(im)

        self.win = tk.Toplevel(self.root)
        platform_utils.setup_window(self.win, config.TRANSPARENT_COLOR)
        self.win.geometry(f"{new_w}x{new_h}+{(sw - new_w) // 2}+{(sh - new_h) // 2}")
        self.win.attributes("-topmost", True)
        canvas = tk.Canvas(self.win, width=new_w, height=new_h,
                           bd=0, highlightthickness=0,
                           bg=config.TRANSPARENT_COLOR)
        canvas.pack()
        canvas.create_image(new_w // 2, new_h // 2, image=self._photo,
                            anchor="center")
        # Click anywhere to close.
        canvas.bind("<Button-1>", lambda e: self._close())
        # Auto-close after a few seconds.
        self._close_after_id = self.win.after(self.auto_close_ms, self._close)

    def _close(self):
        if self._close_after_id is not None and self.win:
            try:
                self.win.after_cancel(self._close_after_id)
            except Exception:
                pass
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
