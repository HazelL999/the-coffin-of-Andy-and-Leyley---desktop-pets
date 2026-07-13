"""The altar: a temporary summoned window where a soul is sacrificed to the
demon in exchange for prophecy.

Geometry is all code-drawn (no sprite art): a red pentagram inside a dark
ring, five candles on the outer points with flickering flames, a many-eyed
demon blob at the center, and a floating soul orb at the lower-left. Right-
click → Sacrifice animates the soul flying into the demon, the demon's eyes
flaring, a flash, then a prophecy line is spoken by the nearest pet.
"""

import math
import random

import tkinter as tk
from PIL import Image, ImageTk

import config
import platform_utils
from asset_loader import _bake_for_windows

# Where the user's cut sprites live (now relative to the project root).
SOUL_SPRITE = str(config.ROOT_DIR / "Altar" / "soul.png")
ENTITY_SPRITE = str(config.ROOT_DIR / "Altar" / "entity.png")


def _star_points(cx, cy, R, r):
    """10 polygon points for a pentagram: outer point at top (-90deg), then
    alternating inner/outer every 36deg. R = outer radius, r = inner."""
    pts = []
    for i in range(10):
        radius = R if i % 2 == 0 else r
        # -90deg + i*36deg, screen y flipped
        a = math.radians(-90 + i * 36)
        pts.append(cx + radius * math.cos(a))
        pts.append(cy + radius * math.sin(a))
    return pts


class Altar:
    """A standalone transparent window holding the altar drawing."""

    def __init__(self, root, x, y, on_sacrifice_done=None, rng=None,
                 on_sacrifice_start=None):
        self.root = root
        self.x = x
        self.y = y
        self.on_sacrifice_done = on_sacrifice_done
        self.on_sacrifice_start = on_sacrifice_start
        self.rng = rng or random
        self.win = None
        self.canvas = None
        self._drag_data = None
        # canvas item ids, for animation
        self._soul_item = None
        self._soul_pos = None          # (x, y) current soul center
        self._soul_target = None      # (x, y) demon center
        self._eye_items = []          # demon eyes (pupil items)
        self._candle_flames = []      # flame items to flicker
        self._flash_item = None
        self._anim_after_id = None
        self._flicker_after_id = None
        self._busy = False            # sacrifice animation in progress
        self._soul_float_after_id = None  # soul idle bob timer
        self._sprites = {}            # "soul"/"entity" -> ImageTk.PhotoImage (keep refs)

    def _load_sprite(self, path, target_h):
        """Load a transparent PNG, scale to target_h px tall (keep aspect),
        and bake over the transparent color so it composites cleanly on
        Windows (no AA fringe). Returns ImageTk.PhotoImage or None."""
        try:
            im = Image.open(path).convert("RGBA")
            w, h = im.size
            scale = target_h / h
            im = im.resize((max(1, round(w * scale)), target_h), Image.LANCZOS)
            if platform_utils.is_windows():
                im = _bake_for_windows(im, config.hex_to_rgb(config.TRANSPARENT_COLOR))
            else:
                im = im.convert("RGBA")
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    # ---------- lifecycle ----------
    def start(self):
        self.win = tk.Toplevel(self.root)
        platform_utils.setup_window(self.win, config.TRANSPARENT_COLOR)
        size = config.ALTAR_SIZE
        self.win.geometry(f"{size}x{size}")
        self.win_w = size
        self.win_h = size
        self.canvas = tk.Canvas(self.win, width=size, height=size,
                                bd=0, highlightthickness=0,
                                bg=config.TRANSPARENT_COLOR)
        self.canvas.pack()
        self._draw_altar()
        self._move_window()
        # drag + context menu
        self.canvas.bind("<Button-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        platform_utils.bind_context_menu(self.win, self._on_context)
        # idle flicker for candle flames
        self._schedule_flicker()

    def _move_window(self):
        if not self.win:
            return
        try:
            self.win.geometry(f"+{int(self.x)}+{int(self.y)}")
        except tk.TclError:
            pass

    # ---------- drawing ----------
    def _draw_altar(self):
        size = config.ALTAR_SIZE
        cx = size // 2
        cy = size // 2
        R = config.ALTAR_STAR_RADIUS
        r = R * 0.382  # golden-ratio inner for a true pentagram

        # Outer ring (dark red).
        self.canvas.create_oval(cx - R - 14, cy - R - 14, cx + R + 14, cy + R + 14,
                                outline="#5a0e0e", width=3)

        # Pentagram star — OUTLINE ONLY (no fill). The polygon connects outer
        # points skipping one each time (the classic 5-point star). Empty fill
        # matches the transparent color so the interior shows through.
        outer = []
        for k in range(5):
            a = math.radians(-90 + k * 72)
            outer.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        star_poly = []
        for i in range(5):
            p = outer[(i * 2) % 5]
            star_poly.extend(p)
        self.canvas.create_polygon(*star_poly,
                                    outline="#5a0e0e", fill=config.TRANSPARENT_COLOR,
                                    width=3, smooth=False)

        # Demon (entity sprite) at center.
        self._draw_demon(cx, cy)

        # Five candles on the outer star points.
        self._candle_flames = []
        for k in range(5):
            a = math.radians(-90 + k * 72)
            px = cx + (R + 2) * math.cos(a)
            py = cy + (R + 2) * math.sin(a)
            self._draw_candle(px, py, a)

        # Soul: a white teardrop ghost with a curved tail, two pale-blue eyes.
        # Drawn as code (no sprite). Rests at lower-left until sacrificed.
        sx = cx - R * 0.9
        sy = cy + R * 0.9
        self._soul_target = (cx, cy)
        self._soul_pos = [sx, sy]
        self._soul_w = 14   # teardrop width (narrow, for a tall slim ghost)
        self._soul_h = 38   # teardrop height (head + tail, taller)
        self._soul_tail_dx = 8  # tail curves off to one side
        # no glow ring (removed per user)
        self._soul_glow = None
        self._soul_item = self.canvas.create_polygon(
            *self._soul_outline(sx, sy),
            fill="#ffffff", outline="#c8d8e0", width=1, smooth=True)
        # two pale-blue eyes on the flat head (head center ~ sy - h*0.18)
        head_cy0 = sy - self._soul_h * 0.18
        self._soul_eyes = [
            self.canvas.create_oval(sx - 5, head_cy0 - 1,
                                    sx - 1, head_cy0 + 2,
                                    fill="#a8d8f0", outline=""),
            self.canvas.create_oval(sx + 1, head_cy0 - 1,
                                    sx + 5, head_cy0 + 2,
                                    fill="#a8d8f0", outline=""),
        ]
        self._soul_half = self._soul_w  # used by movement coords
        # Start the gentle float (only while resting, not during sacrifice).
        self._soul_float_t = 0.0
        self._soul_float_dy = 0.0
        self._schedule_soul_float()

    def _soul_outline(self, cx, cy):
        """Teardrop via 8 control points + Canvas smooth. Each dimension is
        independently tunable. Head is tall (width < height), upper half is
        shorter than lower half, tail is thick and curves to one side.
        Returns a flat point list [x0,y0, x1,y1, ...]."""
        w = self._soul_w
        h = self._soul_h
        tail_dx = self._soul_tail_dx
        head_cy = cy - h * 0.18          # head vertical center
        r_upper = w * 0.55             # head top half (SHORTER) — upper radius
        r_lower = w * 0.95             # head bottom half (flows to tail) — lower radius
        tail_w = w * 0.85              # tail start half-width (THICK)
        tail_tip_y = cy + h * 0.5
        # 8 control points, clockwise from tail-tip-right:
        pts = [
            cx + tail_dx,        tail_tip_y,            # P1: tail tip (curved to side)
            cx + tail_w,         head_cy + r_lower + (tail_tip_y - head_cy - r_lower)*0.45,  # P2: tail mid-right (thick)
            cx + w,              head_cy + r_lower*0.3,  # P3: head bottom-right
            cx + w*0.55,         head_cy - r_upper,      # P4: head top-right (narrow, upper shorter)
            cx - w*0.55,         head_cy - r_upper,      # P5: head top-left
            cx - w,              head_cy + r_lower*0.3,  # P6: head bottom-left
            cx - tail_w,         head_cy + r_lower + (tail_tip_y - head_cy - r_lower)*0.45,  # P7: tail mid-left (thick)
            cx + tail_dx - tail_w*0.3, tail_tip_y,       # P8: near tail tip (left side)
        ]
        # pts is already a flat [x0,y0, x1,y1, ...] list
        return pts

    def _draw_demon(self, cx, cy):
        """Draw the demon at center: a dark solid hexagon with three eyes
        (top / lower-left / lower-right). Each eye = body-colored fill + red
        outline + red pupil. No horns. The demon gently floats up and down.
        A hidden red overlay flashes the whole body during sacrifice."""
        R = 22  # hexagon radius (smaller)
        self._demon_cx = cx
        self._demon_cy = cy
        self._demon_items = []   # items that move together when floating
        # pointy-top hexagon
        hex_pts = []
        for k in range(6):
            a = math.radians(-90 + k * 60)
            hex_pts.append(cx + R * math.cos(a))
            hex_pts.append(cy + R * math.sin(a))
        body = self.canvas.create_polygon(*hex_pts, fill="#2a2233",
                                          outline="#120c18", width=2, smooth=False)
        self._demon_items.append(body)
        # Three eyes, triangular: top, lower-left, lower-right. Each eye is a
        # body-colored oval with a red outline and a red pupil inside.
        eye_positions = [(0, -7), (-8, 6), (8, 6)]
        EYE_RED = "#c01818"  # slightly more red than the pentagram
        self._eye_items = []
        for (dx, dy) in eye_positions:
            ex, ey = cx + dx, cy + dy
            # eye outline: body fill + red outline
            eye = self.canvas.create_oval(ex - 5, ey - 2, ex + 5, ey + 2,
                                          fill="#2a2233", outline=EYE_RED, width=1)
            # red pupil
            pupil = self.canvas.create_oval(ex - 2, ey - 1, ex + 2, ey + 1,
                                            fill=EYE_RED, outline="")
            self._eye_items.append(pupil)
            self._demon_items.append(eye)
            self._demon_items.append(pupil)
        # hidden red overlay for sacrifice flash (whole-body, not eyes)
        self._demon_flash = self.canvas.create_oval(
            cx - R, cy - R, cx + R, cy + R,
            fill="#e23b3b", outline="", state="hidden")
        # Start the gentle float.
        self._demon_float_t = 0.0
        self._demon_float_dy = 0.0   # last applied offset (to compute delta)
        self._schedule_demon_float()

    def _schedule_demon_float(self):
        """Gently bob the demon up and down (a few px sine motion)."""
        if not self.canvas or not self.win:
            return
        import math as _m
        self._demon_float_t += 0.18
        new_dy = _m.sin(self._demon_float_t) * 3.5   # +/-3.5px
        delta = new_dy - self._demon_float_dy
        self._demon_float_dy = new_dy
        try:
            for it in self._demon_items:
                self.canvas.move(it, 0, delta)
            # move the flash overlay too so it stays on the body
            if getattr(self, "_demon_flash", None) is not None:
                self.canvas.move(self._demon_flash, 0, delta)
        except tk.TclError:
            pass
        self._float_after_id = self.win.after(60, self._schedule_demon_float)

    def _schedule_soul_float(self):
        """Gently bob the soul up and down while it rests (stops once
        sacrifice animation begins — _animate_soul_to_demon takes over)."""
        if not self.canvas or not self.win:
            return
        if getattr(self, "_soul_sacrificed", False) or getattr(self, "_busy", False):
            self._soul_float_after_id = None
            return
        self._soul_float_t += 0.15
        new_dy = math.sin(self._soul_float_t) * 3.0   # +/-3px, gentler than demon
        delta = new_dy - self._soul_float_dy
        self._soul_float_dy = new_dy
        try:
            self.canvas.move(self._soul_item, 0, delta)
            for eye in getattr(self, "_soul_eyes", []):
                self.canvas.move(eye, 0, delta)
        except tk.TclError:
            pass
        self._soul_float_after_id = self.win.after(70, self._schedule_soul_float)

    def _draw_candle(self, x, y, angle):
        # Candle body: small rectangle oriented roughly outward.
        # Keep it simple: a short stub at the point.
        self.canvas.create_rectangle(x - 3, y - 3, x + 3, y + 9,
                                     fill="#e8dcb0", outline="#9a8c5c", width=1)
        # Flame: yellow triangle above the candle, base width matches the body.
        flame = self.canvas.create_polygon(
            x - 3, y - 3, x + 3, y - 3, x, y - 12,
            fill="#ffd24a", outline="#e0a020", width=1)
        self._candle_flames.append(flame)

    # ---------- candle flicker ----------
    def _schedule_flicker(self):
        if not self.canvas or not self._candle_flames:
            return
        for fl in self._candle_flames:
            # jitter flame color between yellow and orange
            shade = self.rng.choice(["#ffd24a", "#ffb13a", "#ff9a2a"])
            try:
                self.canvas.itemconfig(fl, fill=shade)
            except tk.TclError:
                pass
        self._flicker_after_id = self.win.after(180, self._schedule_flicker)

    # ---------- sacrifice animation ----------
    def sacrifice(self):
        if self._busy or not self.canvas:
            return
        if getattr(self, "_soul_sacrificed", False):
            # The soul is already gone — nothing left to sacrifice.
            return
        self._busy = True
        # Ashley reacts immediately when the sacrifice begins (not after the
        # animation finishes) — the offering line plays over the soul's flight.
        if self.on_sacrifice_start:
            self.on_sacrifice_start()
        # Start the soul from its resting spot and fly it to the demon center.
        cx = self.win_w // 2
        cy = self.win_h // 2
        self._soul_pos = [cx - config.ALTAR_STAR_RADIUS * 0.9,
                          cy + config.ALTAR_STAR_RADIUS * 0.9]
        self._soul_target = (cx, cy)
        # Make sure the soul is visible before the flight.
        try:
            self.canvas.itemconfig(self._soul_item, state="normal")
            if self._soul_glow is not None:
                self.canvas.itemconfig(self._soul_glow, state="normal")
            for eye in getattr(self, "_soul_eyes", []):
                self.canvas.itemconfig(eye, state="normal")
        except tk.TclError:
            pass
        self._animate_soul_to_demon()

    def _animate_soul_to_demon(self, step=0):
        if not self.canvas or self._soul_pos is None:
            self._busy = False
            return
        tx, ty = self._soul_target
        # Move ~8% of remaining distance per frame (ease-out feel).
        self._soul_pos[0] += (tx - self._soul_pos[0]) * 0.08
        self._soul_pos[1] += (ty - self._soul_pos[1]) * 0.08
        sx, sy = self._soul_pos
        w = self._soul_w
        h = self._soul_h
        try:
            # teardrop polygon: re-emit full outline at new center
            self.canvas.coords(self._soul_item, *self._soul_outline(sx, sy))
            # glow ring removed — nothing to move
            # eyes follow the flat head (head center ~ sy - h*0.18)
            eye_cy = sy - h * 0.18
            self.canvas.coords(self._soul_eyes[0], sx - 5, eye_cy - 1, sx - 1, eye_cy + 2)
            self.canvas.coords(self._soul_eyes[1], sx + 1, eye_cy - 1, sx + 5, eye_cy + 2)
        except tk.TclError:
            pass
        if abs(tx - sx) < 2 and abs(ty - sy) < 2:
            self._on_soul_reaches_demon()
            return
        self._anim_after_id = self.win.after(20, lambda: self._animate_soul_to_demon(step + 1))

    def _on_soul_reaches_demon(self):
        # Soul disappears (and stays gone — it was sacrificed).
        self._soul_sacrificed = True
        try:
            self.canvas.itemconfig(self._soul_item, state="hidden")
            if self._soul_glow is not None:
                self.canvas.itemconfig(self._soul_glow, state="hidden")
            for eye in getattr(self, "_soul_eyes", []):
                self.canvas.itemconfig(eye, state="hidden")
        except tk.TclError:
            pass
        # Demon flare: flash the red whole-body overlay (eyes stay red always).
        if getattr(self, "_demon_flash", None) is not None:
            try:
                self.canvas.itemconfig(self._demon_flash, state="normal")
            except tk.TclError:
                pass
        # Flash at demon center.
        cx, cy = self.win_w // 2, self.win_h // 2
        self._flash_item = self.canvas.create_oval(
            cx - 4, cy - 4, cx + 4, cy + 4,
            fill="#fff7d6", outline="", state="normal")
        self._expand_flash(0)
        # Hide the demon-body flash after a beat (eyes already red, no recolor).
        self.win.after(500, self._reset_demon_eyes)
        # Trigger prophecy.
        if self.on_sacrifice_done:
            self.win.after(700, self.on_sacrifice_done)
        # End busy + reset soul after the prophecy window.
        self.win.after(2200, self._reset_after_sacrifice)

    def _expand_flash(self, step):
        if not self.canvas or self._flash_item is None:
            return
        cx, cy = self.win_w // 2, self.win_h // 2
        r = 4 + step * 6
        try:
            self.canvas.coords(self._flash_item, cx - r, cy - r, cx + r, cy + r)
            # Fade by shrinking outline alpha-ish (Tk has no alpha; lower fill
            # saturation as it grows by switching to a paler color).
            if step > 3:
                self.canvas.itemconfig(self._flash_item, fill="#fff7d6")
            if step > 6:
                self.canvas.itemconfig(self._flash_item, fill="#fdf3c4")
        except tk.TclError:
            pass
        if step < 10:
            self._anim_after_id = self.win.after(30, lambda: self._expand_flash(step + 1))
        else:
            try:
                self.canvas.itemconfig(self._flash_item, state="hidden")
            except tk.TclError:
                pass

    def _reset_demon_eyes(self):
        # Hide the red demon-body flash overlay. Eyes stay red always — no
        # recolor needed.
        if getattr(self, "_demon_flash", None) is not None:
            try:
                self.canvas.itemconfig(self._demon_flash, state="hidden")
            except tk.TclError:
                pass

    def _reset_after_sacrifice(self):
        # The soul was sacrificed — it stays gone. Just free the altar for the
        # next sacrifice (a fresh soul will need a new summon, or the user
        # dismisses + re-summons). We do NOT bring the soul back here.
        self._busy = False

    # ---------- context menu ----------
    def _on_context(self, event):
        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label="Sacrifice", command=self.sacrifice)
        menu.add_separator()
        menu.add_command(label="Dismiss", command=self._dismiss)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _dismiss(self):
        self._cancel_timers()
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self.win = None
        self.canvas = None

    def _cancel_timers(self):
        for attr in ("_anim_after_id", "_flicker_after_id", "_float_after_id", "_soul_float_after_id"):
            tid = getattr(self, attr, None)
            if tid is not None and self.win:
                try:
                    self.win.after_cancel(tid)
                except Exception:
                    pass
            setattr(self, attr, None)

    # ---------- dragging ----------
    def _on_drag_start(self, event):
        self._drag_data = (event.x_root - self.x, event.y_root - self.y)

    def _on_drag_motion(self, event):
        if not self._drag_data:
            return
        ox, oy = self._drag_data
        self.x = event.x_root - ox
        self.y = event.y_root - oy
        self._move_window()

    def _on_drag_end(self, event):
        self._drag_data = None
