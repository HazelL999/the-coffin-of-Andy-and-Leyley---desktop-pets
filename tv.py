"""The TV: a summoned opaque window that plays ads on its screen while the
two pets sit on the couch watching (drawn to the window's right side).

Lifecycle mirrors altar.py: summoned on demand (reused if already open),
draggable, right-click -> Close to dismiss. But unlike the altar this is an
opaque black UI surface (not a transparent sprite), so it uses a plain
Toplevel + theme.BG and canvas.create_image for both Windows and macOS -- no
NSImage bridge is needed (that bridge only exists to work around Tk's
SourceAtop bug on *transparent* windows).

Ads live in subfolders of ads/. Each subfolder is one ad:
  - single .png/.jpg  -> shown TV_AD_HOLD_S seconds
  - single .gif       -> PIL-seeked frame-by-frame at the gif's own durations
  - multiple .png      -> played as a looping frame sequence (default ms/frame)
If no ads are found, the screen shows a "static/no signal" placeholder so the
TV never breaks.
"""

import math
import random
import time

import tkinter as tk
from PIL import Image, ImageTk

import config
import platform_utils
import theme


class Ad:
    """One playable ad: a list of (PIL frame, duration_ms) pairs.

    kind is 'single' (one frame, held TV_AD_HOLD_S), 'gif' (frames at the
    gif's own durations), or 'seq' (multiple PNGs at ANIM_FRAME_DEFAULT_MS)."""

    def __init__(self, kind, frames, name=""):
        self.kind = kind
        self.frames = frames   # list of (PIL.Image, duration_ms)
        self.name = name


def _fit_letterbox(im, w, h):
    """Resize an RGBA/RGB image to fit inside (w,h) keeping aspect, padded
    with black to the target size (letterbox). Never crops content."""
    im = im.convert("RGBA")
    iw, ih = im.size
    if iw == 0 or ih == 0:
        return Image.new("RGBA", (w, h), (0, 0, 0, 255))
    scale = min(w / iw, h / ih)
    nw = max(1, round(iw * scale))
    nh = max(1, round(ih * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    canvas.alpha_composite(im, ((w - nw) // 2, (h - nh) // 2))
    return canvas.convert("RGB")


class TV:
    """A draggable opaque window: code-drawn TV shell (left) with an ad
    screen, plus the couch image (right). Summoned by PetApp; dismissing it
    calls on_close so PetApp can un-hide the desktop sprites."""

    def __init__(self, root, on_close=None, rng=None):
        self.root = root
        self.on_close = on_close
        self.rng = rng or random
        self.win = None
        self.canvas = None
        self.x = 0.0
        self.y = 0.0
        self._drag_data = None
        self._ads = []
        self._ad_idx = 0
        self._frame_idx = 0
        self._screen_item = None     # canvas image item for the ad
        self._photo = None           # keep current PhotoImage ref alive
        self._after_id = None

    # ---------- ad loading ----------

    def _load_ads(self):
        """Scan ads/ subfolders; build Ad objects. Silently returns [] if the
        folder is missing/empty so the TV falls back to the static screen."""
        ads = []
        base = config.ADS_DIR
        if not base.is_dir():
            return ads
        try:
            subdirs = sorted(p for p in base.iterdir() if p.is_dir())
        except Exception:
            return ads
        for d in subdirs:
            try:
                ad = self._load_one_ad(d)
            except Exception:
                ad = None
            if ad:
                ads.append(ad)
        return ads

    def _load_one_ad(self, folder):
        files = sorted(p for p in folder.iterdir()
                       if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif"))
        if not files:
            return None
        # A single .gif: peel its frames.
        if len(files) == 1 and files[0].suffix.lower() == ".gif":
            frames = []
            try:
                im = Image.open(files[0])
                i = 0
                while True:
                    try:
                        im.seek(i)
                    except EOFError:
                        break
                    dur = im.info.get("duration") or 100
                    frames.append((im.copy().convert("RGBA"), int(dur)))
                    i += 1
            except Exception:
                return None
            if not frames:
                return None
            return Ad("gif", frames, folder.name)
        # Multiple PNGs: a looping frame sequence.
        if len(files) > 1:
            frames = []
            for f in files:
                try:
                    im = Image.open(f).convert("RGBA")
                except Exception:
                    continue
                frames.append((im, config.ANIM_FRAME_DEFAULT_MS))
            if not frames:
                return None
            return Ad("seq", frames, folder.name)
        # Single static image.
        try:
            im = Image.open(files[0]).convert("RGBA")
        except Exception:
            return None
        return Ad("single", [(im, int(config.TV_AD_HOLD_S * 1000))], folder.name)

    # ---------- lifecycle ----------

    def start(self):
        self._ads = self._load_ads()
        self.rng.shuffle(self._ads) if self._ads else None
        self._ad_idx = 0
        self._frame_idx = 0

        w = config.TV_WIDTH
        h = config.TV_HEIGHT
        self.win = tk.Toplevel(self.root)
        self.win.title("TV")
        self.win.geometry(f"{w}x{h}")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.config(bg=theme.BG)
        # Center on the primary screen.
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.x = (sw - w) / 2
        self.y = (sh - h) / 2
        self.canvas = tk.Canvas(self.win, width=w, height=h, bd=0,
                                highlightthickness=0, bg=theme.BG)
        self.canvas.pack()
        self._draw_tv_shell()
        self._draw_couch()
        # The screen image item, created lazily and reused.
        self._screen_item = self.canvas.create_image(
            config.TV_SHELL_PAD + config.TV_SCREEN_W // 2,
            config.TV_SCREEN_TOP + config.TV_SCREEN_H // 2,
            anchor="center")
        self._move_window()
        # Drag + context menu.
        self.canvas.bind("<Button-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        platform_utils.bind_context_menu(self.win, self._on_context,
                                        canvas=self.canvas)
        try:
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass
        # Begin playback.
        self._play_current_frame()
        self.win.protocol("WM_DELETE_WINDOW", self.dismiss)

    def _move_window(self):
        if not self.win:
            return
        try:
            self.win.geometry(f"+{int(self.x)}+{int(self.y)}")
        except tk.TclError:
            pass

    # ---------- drawing ----------

    def _round_rect(self, x0, y0, x1, y1, r, **kw):
        """A rounded-rectangle polygon (8 samples per corner). Used for the
        retro TV body's corners so it doesn't read as a flat modern slab."""
        import math as _m
        pts = []
        n = 8
        # top-right
        cx, cy = x1 - r, y0 + r
        for i in range(n + 1):
            a = _m.pi / 2 * (i / n)
            pts += [cx + r * _m.sin(a), cy - r * _m.cos(a)]
        # bottom-right
        cx, cy = x1 - r, y1 - r
        for i in range(n + 1):
            a = _m.pi / 2 * (i / n)
            pts += [cx + r * _m.cos(a), cy + r * _m.sin(a)]
        # bottom-left
        cx, cy = x0 + r, y1 - r
        for i in range(n + 1):
            a = _m.pi / 2 * (i / n)
            pts += [cx - r * _m.sin(a), cy + r * _m.cos(a)]
        # top-left
        cx, cy = x0 + r, y0 + r
        for i in range(n + 1):
            a = _m.pi / 2 * (i / n)
            pts += [cx - r * _m.cos(a), cy - r * _m.sin(a)]
        return self.canvas.create_polygon(*pts, **kw)

    def _draw_tv_shell(self):
        """Code-draw a retro CRT TV: a thick black rounded body around the
        screen, with a knob strip below the screen holding a channel knob
        (click to change channel -> next ad) + a volume knob (decorative) +
        a speaker grille. No antenna."""
        c = self.canvas
        sx = config.TV_SHELL_PAD
        sy = config.TV_SCREEN_TOP
        sw = config.TV_SCREEN_W
        sh = config.TV_SCREEN_H
        # Side bezel thickness; the body extends an extra TV_KNOB_BAND below
        # the screen so the knob strip is part of the body (not floating).
        side = 16
        top = 12
        body_x0 = sx - side
        body_y0 = sy - top
        body_x1 = sx + sw + side
        body_y1 = sy + sh + side + config.TV_KNOB_BAND
        # Body: solid black with a subtle dark-grey rim (a CRT's plastic).
        self._round_rect(body_x0, body_y0, body_x1, body_y1, 12,
                         fill="#0e0e0e", outline="#2a2a2a", width=2,
                         smooth=False)
        # Inner bezel ring (lighter) just around the screen, plus the screen
        # black backdrop. The ring sells the "recessed CRT face" look.
        ring = 5
        self._round_rect(sx - ring, sy - ring, sx + sw + ring, sy + sh + ring, 4,
                         fill="#1c1c1c", outline="#000000", width=1,
                         smooth=False)
        c.create_rectangle(sx, sy, sx + sw, sy + sh, fill="#000000", outline="")
        # Subtle screen glass sheen -- a faint diagonal highlight, so the black
        # area looks like glass, not just empty. (Thin, low-contrast.)
        c.create_polygon(sx + 6, sy + 4, sx + sw * 0.5, sy + 4,
                         sx + sw * 0.5, sy + 24, sx + 6, sy + 24,
                         fill="#1a1a22", outline="", stipple="gray25")

        # Knob strip: centered vertically in the band below the screen.
        strip_top = sy + sh + side
        strip_h = config.TV_KNOB_BAND
        knob_y = strip_top + strip_h // 2
        knob_r = 11
        # Two knobs: the left one is the channel knob (click -> next ad),
        # the right one is a decorative volume knob. They turn (pointer
        # rotates) when the channel changes for visual feedback.
        self._knob_pos = []
        for kx in (sx + 34, sx + 74):
            self._knob_pos.append((kx, knob_y, knob_r))
        self._draw_knob(0, 0)   # channel knob, initial angle 0
        self._draw_knob(1, 0)   # volume knob, fixed angle 0
        # A small speaker grille to the right of the knobs (rows of dots).
        gx0 = sx + 100
        gy0 = knob_y - 9
        for row in range(3):
            for col in range(6):
                c.create_oval(gx0 + col * 7, gy0 + row * 7,
                              gx0 + col * 7 + 2, gy0 + row * 7 + 2,
                              fill="#3a3a3a", outline="")

    def _draw_knob(self, idx, angle_deg):
        """(Re)draw knob `idx` at rotation `angle_deg` (pointer points that
        many degrees clockwise from up). Knob = dark disc + a pointer tick."""
        c = self.canvas
        # Recreate each time: cheap and avoids stale item tracking.
        if not hasattr(self, "_knob_items"):
            self._knob_items = {}
        # Clear old items for this knob.
        for it in self._knob_items.get(idx, []):
            try:
                c.delete(it)
            except tk.TclError:
                pass
        kx, ky, kr = self._knob_pos[idx]
        disc = c.create_oval(kx - kr, ky - kr, kx + kr, ky + kr,
                             fill="#3a3a3a", outline="#0e0e0e", width=1)
        # Pointer tick: rotated by angle_deg, length ~kr.
        import math as _m
        a = _m.radians(angle_deg)
        # start at center, point outward; "up" is angle 0 -> (sin a, -cos a).
        px = kx + _m.sin(a) * (kr - 3)
        py = ky - _m.cos(a) * (kr - 3)
        tick = c.create_line(kx, ky, px, py, fill="#0e0e0e", width=2)
        # Center cap.
        cap = c.create_oval(kx - 2, ky - 2, kx + 2, ky + 2,
                            fill="#1a1a1a", outline="")
        self._knob_items[idx] = [disc, tick, cap]

    def _knob_at(self, x, y):
        """Return knob index (0=channel, 1=volume) if (x,y) is inside a knob,
        else None."""
        if not getattr(self, "_knob_pos", None):
            return None
        for idx, (kx, ky, kr) in enumerate(self._knob_pos):
            if (x - kx) ** 2 + (y - ky) ** 2 <= (kr + 2) ** 2:
                return idx
        return None

    def _draw_couch(self):
        """The 'pets on the couch watching' image to the right of the screen.
        Composited over the window bg (not magenta-baked -- this is opaque).
        Falls back to a placeholder label if the image is missing."""
        couch_x = config.TV_SHELL_PAD + config.TV_SCREEN_W + 2 * config.TV_SHELL_PAD
        region_w = config.TV_WIDTH - couch_x - config.TV_SHELL_PAD
        region_h = config.TV_HEIGHT - 2 * config.TV_SHELL_PAD
        try:
            im = Image.open(config.TV_COUCH_IMG).convert("RGBA")
        except Exception:
            # Placeholder: tell the user where the couch image goes.
            self.canvas.create_text(
                couch_x + region_w // 2,
                config.TV_HEIGHT // 2,
                text="couch image\ngoes here",
                font=(config.UI_FONT, 9), fill=theme.FG_DIM,
                justify="center")
            return
        im = _fit_letterbox(im, region_w, region_h)
        photo = ImageTk.PhotoImage(im)
        self._couch_photo = photo  # keep ref
        self.canvas.create_image(couch_x + region_w // 2,
                                  config.TV_HEIGHT // 2,
                                  image=photo, anchor="center")

    # ---------- playback ----------

    def _show_frame(self, pil_frame):
        """Composite a PIL frame onto black and put it on the screen item."""
        im = _fit_letterbox(pil_frame, config.TV_SCREEN_W, config.TV_SCREEN_H)
        self._photo = ImageTk.PhotoImage(im)
        try:
            self.canvas.itemconfig(self._screen_item, image=self._photo)
        except tk.TclError:
            pass

    def _play_current_frame(self):
        """Show the current ad's current frame and schedule the next step."""
        if not self.win:
            return
        if not self._ads:
            self._show_static()
            self._after_id = self.win.after(int(config.TV_AD_HOLD_S * 1000),
                                            self._next_ad)
            return
        ad = self._ads[self._ad_idx % len(self._ads)]
        frame, dur = ad.frames[self._frame_idx % len(ad.frames)]
        self._show_frame(frame)
        # Decide the next step based on ad kind.
        if ad.kind == "single":
            self._after_id = self.win.after(dur, self._next_ad)
        else:
            # gif / seq: advance frame; wrap to next ad when the last frame shows.
            if self._frame_idx + 1 < len(ad.frames):
                self._frame_idx += 1
                self._after_id = self.win.after(max(40, dur),
                                                self._play_current_frame)
            else:
                self._after_id = self.win.after(max(40, dur), self._next_ad)

    def _next_ad(self):
        if not self.win:
            return
        self._frame_idx = 0
        if self._ads:
            self._ad_idx = (self._ad_idx + 1) % len(self._ads)
        self._play_current_frame()

    def _show_static(self):
        """No-signal placeholder: a few grey noise rectangles so the screen
        isn't a dead black box when ads/ is empty."""
        import random as _r
        rng = _r.Random(0)  # deterministic, no Math.random/date issues
        sx = config.TV_SHELL_PAD
        sy = config.TV_SCREEN_TOP
        sw, sh = config.TV_SCREEN_W, config.TV_SCREEN_H
        # Draw a handful of grey flecks (cheap, not per-pixel).
        for _ in range(80):
            x = sx + rng.randint(0, sw - 1)
            y = sy + rng.randint(0, sh - 1)
            g = rng.randint(60, 130)
            try:
                self.canvas.create_rectangle(x, y, x + 2, y + 2,
                                             fill=f"#{g:02x}{g:02x}{g:02x}",
                                             outline="")
            except tk.TclError:
                pass

    # ---------- context menu ----------

    def _on_context(self, event):
        menu = theme.style_menu(tk.Menu(self.win, tearoff=0))
        menu.add_command(label="Close", command=self.dismiss)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ---------- dragging / channel knob ----------

    def _on_drag_start(self, event):
        # If the press landed on the channel knob (knob 0), treat it as a
        # "turn the knob" click: change channel + rotate the pointer. The
        # volume knob (knob 1) wobbles decoratively. Otherwise start a drag.
        knob = self._knob_at(event.x, event.y)
        if knob is not None:
            self._turn_knob(knob)
            self._drag_data = None  # don't drag when clicking a knob
            return
        self._drag_data = (event.x_root - self.x, event.y_root - self.y)

    def _turn_knob(self, idx):
        """Click a knob: channel knob (0) advances to the next ad and the
        pointer rotates a quarter turn; volume knob (1) just nudges."""
        import math as _m
        if idx == 0:
            self._next_ad()
            ang = (getattr(self, "_channel_angle", 0) + 90) % 360
            self._channel_angle = ang
            self._draw_knob(0, ang)
        else:
            ang = (getattr(self, "_volume_angle", 0) + 25) % 360
            self._volume_angle = ang
            self._draw_knob(1, ang)

    def _on_drag_motion(self, event):
        if not self._drag_data:
            return
        ox, oy = self._drag_data
        self.x = event.x_root - ox
        self.y = event.y_root - oy
        self._move_window()

    def _on_drag_end(self, event):
        self._drag_data = None

    # ---------- dismiss ----------

    def dismiss(self):
        """Stop playback, destroy the window, and tell PetApp to un-hide pets."""
        if self._after_id is not None and self.win:
            try:
                self.win.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = None
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        self.canvas = None
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass
