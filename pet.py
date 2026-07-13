"""A single pet: its own borderless transparent window, state machine,
movement/wander, animation, speech bubble, and right-click menu.

The window itself is moved (geometry) rather than a canvas item, so the
bounding box stays tight to the sprite.
"""

import math
import random
import time

import tkinter as tk

import config
import expressions
import platform_utils

# UI + emoji fonts are chosen per-platform in config (shared across the app).
_UI_FONT = config.UI_FONT
_EMOJI_FONT = config.EMOJI_FONT


class Pet:
    STATE_IDLE = "idle"
    STATE_WANDERING = "wandering"
    STATE_SPEAKING = "speaking"
    STATE_SLEEPING = "sleeping"

    def __init__(self, character, loader, dialogue_store, scheduler, root,
                 bounds, rng=None, on_quit=None,
                 on_partner_freeze=None, on_drag_onto_partner=None,
                 on_poked=None, on_check_state=None, on_summon_altar=None,
                 on_open_backpack=None, on_set_city=None, on_ai_chat=None,
                 on_toggle_music=None):
        self.character = character
        self.loader = loader
        self.dialogue = dialogue_store
        self.scheduler = scheduler
        self.root = root
        self.bounds = bounds  # (x0,y0,x1,y1)
        self.rng = rng or random
        self.on_quit = on_quit
        self.on_partner_freeze = on_partner_freeze  # see PetApp._on_partner_freeze
        self.on_drag_onto_partner = on_drag_onto_partner  # drag-onto scene trigger
        self.on_poked = on_poked          # fired when this pet is poked (clicked) repeatedly
        self.on_check_state = on_check_state  # right-click "Check state" handler
        self.on_summon_altar = on_summon_altar  # right-click "Summon altar" handler
        self.on_open_backpack = on_open_backpack  # right-click "Backpack" handler
        self.on_set_city = on_set_city  # right-click "Set city" (weather) handler
        self.on_ai_chat = on_ai_chat  # right-click "AI chat…" handler
        self.on_toggle_music = on_toggle_music  # right-click "Music on/off" handler
        self.partner_ref = None   # the other pet (set by PetApp after both start)
        self.codep = None         # CodependencyState (set by PetApp)

        # State
        self.x = 0.0
        self.y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.facing = "right"
        self.state = self.STATE_IDLE
        self.current_mood = "neutral"
        self.movement_enabled = True   # toggled by Settings menu
        self.speaking_enabled = True   # toggled by Settings menu

        # Animation
        self.current_frameset = None
        self.frame_index = 0
        self.frame_accum_ms = 0.0

        # Dialogue cooldown
        self.last_spoke = -math.inf
        self.bubble_after_id = None
        self._transition_after_id = None  # pending -1->-2 switch on speak()
        self._speaking_after_id = None   # pending return-to-idle after a bubble
        self._bubble_seq_after_id = None  # pending next-bubble in a monologue
        self._frozen_until = -math.inf   # freeze movement while someone speaks
        self.distance_band = "close"     # set by PetApp from inter-pet distance

        # Click-vs-drag detection + multi-click rage (Andrew poked -> Ashley mad)
        self._press_pos = None           # (x_root, y_root, t) on Button-1 down
        self._click_count = 0
        self._click_reset_after_id = None

        # Andy sleep: idle-seconds-while-pressed-to-Ashley accumulator
        self._sleep_idle = 0.0
        self._sleep_z_items = []         # canvas "Zzz" items

        # Hover state icon (mental state emoji after 2s hover)
        self._hover_after_id = None
        self._state_icon_items = []

        # Idle pause timer
        self.idle_timer = self.rng.uniform(*config.IDLE_PAUSE_RANGE)

        # Shadow band cache: _update_shadow only re-applies itemconfig when the
        # band changes, so calling it every frame is cheap (no flicker, no
        # redundant Tk calls). -1 = "not yet drawn" sentinel.
        self._shadow_band = -1

        # Dragging
        self._drag_data = None

        # Window + canvas built lazily
        self.win = None
        self.canvas = None
        self.image_item = None
        self.bubble_items = []  # Canvas item ids for the rounded speech bubble

    # ---------- lifecycle ----------
    def start(self):
        self.win = tk.Toplevel(self.root)
        platform_utils.setup_window(self.win, config.TRANSPARENT_COLOR)
        size = config.PLACEHOLDER_SIZE
        # The window must be wide enough to hold the speech bubble (which can be
        # wider than the sprite) and tall enough for the bubble band above the
        # sprite. The sprite sits centered horizontally at the bottom; the bubble
        # is drawn in the top band on the same Canvas so nothing is clipped.
        self.win_w = max(size, config.BUBBLE_MAX_WIDTH + 16)
        self.bubble_band = 60  # tight band: bubble hugs the sprite's head
        win_h = size + self.bubble_band
        self.win_h = win_h
        self.win.geometry(f"{self.win_w}x{win_h}")
        self.canvas = tk.Canvas(self.win, width=self.win_w, height=win_h,
                                bd=0, highlightthickness=0,
                                bg=config.TRANSPARENT_COLOR)
        self.canvas.pack()

        self.current_mood = "neutral"
        self.current_frameset = self.loader.load(self.character, self.current_mood)
        self.frame_index = 0

        # Sprite anchored at the bottom-center of the window. Its screen position
        # is (win_x + win_w/2 - size/2, win_y + bubble_band). We keep self.x /
        # self.y as the SPRITE's top-left for movement/clamp math, and offset the
        # window in _move_window so the sprite lands at (self.x, self.y).
        self.sprite_cx = self.win_w // 2
        self.sprite_cy = win_h - size // 2
        self.image_item = self.canvas.create_image(
            self.sprite_cx, self.sprite_cy, image=self._current_image(),
            anchor="center")
        # Shadow under the sprite — a darkened ellipse whose opacity reflects
        # mental state (good = faint, bad = dark). Drawn BEFORE the sprite
        # so it sits underneath.
        sh_y = self.sprite_cy + config.PLACEHOLDER_SIZE // 2 - 4
        self.shadow_item = self.canvas.create_oval(
            self.sprite_cx - 40, sh_y - 6,
            self.sprite_cx + 40, sh_y + 6,
            fill="#000000", outline="", state="hidden")
        self.canvas.tag_lower(self.shadow_item)  # behind sprite

        # Place the SPRITE at a random on-screen position. self.x/self.y are the
        # sprite's top-left; the window itself is offset upward to leave room
        # for the speech bubble band (see _move_window).
        x0, y0, x1, y1 = self.bounds
        m = config.SCREEN_MARGIN
        self.x = self.rng.uniform(x0 + m,
                                  max(x0 + m + 1, x1 - size - m))
        self.y = self.rng.uniform(y0 + m,
                                  max(y0 + m + 1, y1 - size - m))
        self._move_window()

        # Speech bubble (hidden initially)
        self._build_bubble()

        # Bindings
        platform_utils.bind_context_menu(self.win, self._on_context)
        self.canvas.bind("<Button-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        # Hover: after 2s over the pet, show its mental-state icon.
        self.canvas.bind("<Enter>", self._on_hover_enter)
        self.canvas.bind("<Leave>", self._on_hover_leave)

    def _current_image(self):
        frames = self.current_frameset.frames(self.facing)
        if not frames:
            return None
        return frames[self.frame_index % len(frames)]

    def _build_bubble(self):
        # Rounded speech bubble drawn on the pet's own canvas. We create the
        # items lazily in _show_bubble because their geometry depends on the
        # text; here we just reset state.
        self.bubble_items = []
        # Persistent hidden Label reused to measure bubble text across speaks
        # (avoids building/destroying a widget per line).
        self._meas_label = tk.Label(self.win, font=(_UI_FONT, 10), justify="left")

    def _round_rect_pts_arc(self, x0, y0, x1, y1, r):
        """Build a rounded-rectangle polygon by sampling arc points at each
        corner. 8 samples per corner is smooth enough at small sizes."""
        pts = []
        n = 8
        # top-right corner: center (x1-r, y0+r), from 0deg to 90deg (in screen coords)
        cx, cy = x1 - r, y0 + r
        for i in range(n + 1):
            a = math.pi / 2 * (i / n)
            pts.append(cx + r * math.sin(a))
            pts.append(cy - r * math.cos(a))
        # bottom-right corner: center (x1-r, y1-r), 90 to 180
        cx, cy = x1 - r, y1 - r
        for i in range(n + 1):
            a = math.pi / 2 * (i / n)
            pts.append(cx + r * math.cos(a))
            pts.append(cy + r * math.sin(a))
        # bottom-left corner: center (x0+r, y1-r), 180 to 270
        cx, cy = x0 + r, y1 - r
        for i in range(n + 1):
            a = math.pi / 2 * (i / n)
            pts.append(cx - r * math.sin(a))
            pts.append(cy + r * math.cos(a))
        # top-left corner: center (x0+r, y0+r), 270 to 360
        cx, cy = x0 + r, y0 + r
        for i in range(n + 1):
            a = math.pi / 2 * (i / n)
            pts.append(cx - r * math.cos(a))
            pts.append(cy - r * math.sin(a))
        return pts

    def _show_bubble(self, text):
        if not self.canvas:
            return
        self._hide_bubble()
        # Measure text to size the bubble. Reuse the persistent hidden Label
        # with wraplength to get required width/height, capping at BUBBLE_MAX_WIDTH.
        self._meas_label.config(text=text,
                                wraplength=config.BUBBLE_MAX_WIDTH - 24)
        self._meas_label.update_idletasks()
        tw = self._meas_label.winfo_reqwidth()
        th = self._meas_label.winfo_reqheight()
        # Bubble inner padding + corner radius.
        pad_x, pad_y = 12, 8
        radius = 14
        bw = min(config.BUBBLE_MAX_WIDTH, tw + 2 * pad_x)
        bh = th + 2 * pad_y
        # Clamp to fit the bubble band above the sprite.
        max_bh = self.bubble_band - 6
        if bh > max_bh:
            bh = max_bh
        # Bubble sits tight against the sprite's head (by1 = sprite top - 2),
        # drawn upward. Horizontally offset toward the facing side so two
        # facing pets' bubbles splay outward and don't overlap each other.
        sprite_top = self.sprite_cy - config.PLACEHOLDER_SIZE // 2
        by1 = max(bh + 2, sprite_top - 2)  # bubble bottom; leave room above
        by0 = by1 - bh
        # Center the bubble on the sprite, then nudge toward facing side.
        center_x = self.sprite_cx
        nudge = config.PLACEHOLDER_SIZE // 4  # ~32px outward
        if self.facing == "right":
            center_x += nudge
        else:
            center_x -= nudge
        bx0 = center_x - bw // 2
        # Keep the bubble fully inside the window (clamp, keep the nudge dir).
        bx0 = max(0, min(bx0, self.win_w - bw))
        bx1 = bx0 + bw
        # Tail points down toward the sprite head, on the facing side.
        tail_x = bx0 + bw // 2
        # Draw rounded bubble: white fill, thin gray outline.
        pts = self._round_rect_pts_arc(bx0, by0, bx1, by1, radius)
        bg_item = self.canvas.create_polygon(
            *pts, fill="white", outline="#9aa0a6", width=1, smooth=False)
        tail = self.canvas.create_polygon(
            tail_x - 6, by1 - 1, tail_x + 6, by1 - 1, tail_x, by1 + 8,
            fill="white", outline="#9aa0a6", width=1)
        # Cover the seam where the tail meets the bubble bottom.
        seam = self.canvas.create_line(
            tail_x - 5, by1, tail_x + 5, by1, fill="white", width=2)
        # Text, centered in the bubble with wrap.
        tx = bx0 + bw / 2
        ty = by0 + bh / 2
        text_item = self.canvas.create_text(
            tx, ty, text=text, font=(_UI_FONT, 10), fill="#1a1a1a",
            justify="left", width=bw - 2 * pad_x, anchor="center")
        # Keep order: tail behind text.
        self.bubble_items = [bg_item, tail, seam, text_item]
        # Cancel any pending hide and schedule a new one.
        if self.bubble_after_id:
            try:
                self.win.after_cancel(self.bubble_after_id)
            except Exception:
                pass
        self.bubble_after_id = self.win.after(
            int(config.BUBBLE_HOLD * 1000), self._hide_bubble)

    def _hide_bubble(self):
        if self.bubble_items and self.canvas:
            for item in self.bubble_items:
                try:
                    self.canvas.delete(item)
                except Exception:
                    pass
        self.bubble_items = []
        self.bubble_after_id = None

    # ---------- per-frame update ----------
    def update(self, dt):
        if not self.win:
            return
        self._update_movement(dt)
        self._update_animation(dt)
        # Mental-state shadow tracks codep drift, not just mood changes — so it
        # must refresh every frame. _update_shadow caches by band, making this
        # a no-op until the value crosses a band boundary.
        self._update_shadow()

    def _update_movement(self, dt):
        # While frozen (someone is speaking), hold position — no wander, no
        # walking toward a target. Window still repositioned so drag/external
        # moves stay visible. Expires automatically when _frozen_until passes.
        now = time.monotonic()
        if now < self._frozen_until:
            self._move_window()
            return
        # Sleeping: hold still (Andy sleeps pressed to Ashley). Wake checks
        # are in _update_sleep; here we just don't move.
        if self.state == self.STATE_SLEEPING:
            self._update_sleep(dt)
            self._move_window()
            return
        size = config.PLACEHOLDER_SIZE
        if self.state == self.STATE_WANDERING:
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = math.hypot(dx, dy)
            if dist < 1.5:
                self.x, self.y = self.target_x, self.target_y
                self.state = self.STATE_IDLE
                self.idle_timer = self.rng.uniform(*config.IDLE_PAUSE_RANGE)
            else:
                step = config.WALK_SPEED_PX_S * dt
                self.x += (dx / dist) * step
                self.y += (dy / dist) * step
                if abs(dx) > 1:
                    self.facing = "right" if dx > 0 else "left"
        else:  # IDLE
            # Andy pressed to Ashley won't wander off — he settles to sleep.
            settling = (self.character == "andrew" and self._pressed_to_partner())
            if not settling:
                self.idle_timer -= dt
            self._update_sleep(dt)  # accumulate idle-toward-sleep (Andy only)
            if self.idle_timer <= 0 and not settling:
                self.wander()
        self._clamp_position(size)
        self._move_window()

    def _update_sleep(self, dt):
        """Andy-only: accumulate idle time while pressed to Ashley; fall asleep
        past the threshold. Other characters never sleep."""
        if self.character != "andrew":
            return
        if self.state == self.STATE_SLEEPING:
            # Wake if Ashley moved away.
            if not self._pressed_to_partner():
                self._wake_up()
            return
        if self.state != self.STATE_IDLE:
            self._sleep_idle = 0.0
            return
        if self._pressed_to_partner():
            self._sleep_idle += dt
            if self._sleep_idle >= config.SLEEP_IDLE_THRESHOLD:
                self._fall_asleep()
        else:
            self._sleep_idle = 0.0

    def _pressed_to_partner(self):
        if not self.partner_ref:
            return False
        return self.distance_band == config.SLEEP_DIST_BAND

    def _fall_asleep(self):
        self.state = self.STATE_SLEEPING
        self.set_mood(config.ANDY_SLEEP_MOOD)
        self._draw_zzz()

    def _wake_up(self):
        if self.state != self.STATE_SLEEPING:
            return
        self.state = self.STATE_IDLE
        self.idle_timer = self.rng.uniform(*config.IDLE_PAUSE_RANGE)
        self._sleep_idle = 0.0
        self._clear_zzz()

    def _draw_zzz(self):
        if not self.canvas:
            return
        self._clear_zzz()
        # Draw a small "Zzz" above the sprite's head.
        zx = self.sprite_cx + 30
        zy = self.sprite_cy - config.PLACEHOLDER_SIZE // 2 - 6
        z = self.canvas.create_text(zx, zy, text="Zzz", font=(_UI_FONT, 12, "bold"),
                                    fill="#5b6cc4", anchor="center")
        self._sleep_z_items = [z]

    def _clear_zzz(self):
        if self._sleep_z_items and self.canvas:
            for it in self._sleep_z_items:
                try:
                    self.canvas.delete(it)
                except Exception:
                    pass
        self._sleep_z_items = []

    # ---------- hover state icon ----------
    def _on_hover_enter(self, event):
        if self._hover_after_id:
            try:
                self.win.after_cancel(self._hover_after_id)
            except Exception:
                pass
        self._hover_after_id = self.win.after(2000, self._show_state_icon)

    def _on_hover_leave(self, event):
        if self._hover_after_id:
            try:
                self.win.after_cancel(self._hover_after_id)
            except Exception:
                pass
            self._hover_after_id = None
        self._hide_state_icon()

    def _show_state_icon(self):
        self._hover_after_id = None
        if not self.canvas or not self.codep:
            return
        self._hide_state_icon()
        label, emoji = self.codep.mental_state(self.character)
        ix = self.sprite_cx
        iy = self.sprite_cy - config.PLACEHOLDER_SIZE // 2 - 16
        item = self.canvas.create_text(ix, iy, text=emoji,
                                       font=(_EMOJI_FONT, 16),
                                       anchor="center")
        self._state_icon_items = [item]

    def _hide_state_icon(self):
        if self._state_icon_items and self.canvas:
            for it in self._state_icon_items:
                try:
                    self.canvas.delete(it)
                except Exception:
                    pass
        self._state_icon_items = []

    def _update_animation(self, dt):
        # Transition moods (-1/-2) are driven ONLY by speak(): never auto-loop,
        # otherwise the two keyframes would flicker back and forth.
        if self.current_mood in expressions.TRANSITION_MOODS:
            return
        frames = self.current_frameset.frames(self.facing)
        if len(frames) <= 1:
            self.frame_index = 0
            return
        dur = self.current_frameset.frame_durations[
            self.frame_index % len(self.current_frameset.frame_durations)]
        dur = dur or config.ANIM_FRAME_DEFAULT_MS
        self.frame_accum_ms += dt * 1000.0
        if self.frame_accum_ms >= dur:
            self.frame_accum_ms = 0.0
            self.frame_index = (self.frame_index + 1) % len(frames)
            if self.image_item is not None:
                self.canvas.itemconfig(self.image_item, image=self._current_image())

    def _clamp_position(self, size):
        x0, y0, x1, y1 = self.bounds
        m = config.SCREEN_MARGIN
        # self.x/self.y are the sprite's top-left; clamp the sprite to the screen.
        self.x = max(x0 + m, min(self.x, x1 - size - m))
        self.y = max(y0 + m, min(self.y, y1 - size - m))

    def _move_window(self):
        if not self.win:
            return
        size = config.PLACEHOLDER_SIZE
        # Window top-left so the SPRITE (which is centered horizontally at the
        # bottom of the window) lands at (self.x, self.y). The bubble band sits
        # above the sprite and may extend slightly above the screen top, which is
        # fine (the bubble is a transient overlay).
        wx = int(self.x - (self.win_w - size) / 2)
        wy = int(self.y - self.bubble_band)
        try:
            self.win.geometry(f"+{wx}+{wy}")
        except tk.TclError:
            pass

    # ---------- actions ----------
    def wander(self):
        size = config.PLACEHOLDER_SIZE
        x0, y0, x1, y1 = self.bounds
        m = config.SCREEN_MARGIN
        self.target_x = self.rng.uniform(x0 + m, x1 - size - m)
        self.target_y = self.rng.uniform(y0 + m, y1 - size - m)
        # Codependency steers Andrew's wander target: dependent -> toward
        # Ashley, independent -> away. Other characters wander freely.
        if self.character == "andrew" and self.codep and self.partner_ref:
            lvl = self.codep.level("andrew")
            px, py = self.partner_ref.x, self.partner_ref.y
            if lvl == "dependent":
                self.target_x = (self.target_x + px) / 2
                self.target_y = (self.target_y + py) / 2
            elif lvl == "independent" and self.rng.random() < 0.6:
                # bias away from Ashley
                self.target_x = self.x + (self.x - px) * 0.5
                self.target_y = self.y + (self.y - py) * 0.5
        self.state = self.STATE_WANDERING

    def _cancel_transition(self):
        """Cancel any pending -1 -> -2 switch scheduled by a previous speak()."""
        if self._transition_after_id is not None and self.win:
            try:
                self.win.after_cancel(self._transition_after_id)
            except Exception:
                pass
        self._transition_after_id = None

    def freeze_until(self, t, face_toward=None):
        """Freeze movement until monotonic time `t`. If face_toward is an
        (x, y) point, turn to face it. Takes the max so a later freeze can't
        shorten an earlier one."""
        self._frozen_until = max(self._frozen_until, t)
        if face_toward is not None:
            self.facing = "right" if face_toward[0] >= self.x else "left"

    def unfreeze(self):
        """Clear any active movement freeze (e.g. when the user drags)."""
        self._frozen_until = -math.inf

    def set_distance_band(self, band):
        """Set the inter-pet distance band; biases idle moods and dialogue
        cooldown (see expressions + config.DISTANCE_BAND_COOLDOWN_SCALE)."""
        if band != self.distance_band:
            self.distance_band = band

    def set_mood(self, mood):
        if mood not in expressions.MOODS:
            mood = "neutral"
        # Same-mood early return must NOT cancel a pending -1->-2 transition:
        # during the 400ms window an idle "expression" event may re-select the
        # same transition mood, and cancelling here would swallow the switch.
        # Only a real mood change (below) cancels the old transition.
        if mood == self.current_mood and self.current_frameset is not None:
            return
        self._cancel_transition()
        self.current_mood = mood
        self.current_frameset = self.loader.load(self.character, mood)
        self.frame_index = 0
        self.frame_accum_ms = 0.0
        if self.image_item is not None:
            self.canvas.itemconfig(self.image_item, image=self._current_image())
        # Apply codependency delta for the new mood (small per-mood drift).
        if self.codep:
            delta = expressions.MOOD_CODEP_DELTA.get(mood, 0.0)
            if delta != 0.0:
                self.codep.adjust(self.character, delta)
        self._update_shadow()

    def _update_shadow(self):
        """Reflect mental state as a shadow under the sprite. Good codep =
        no shadow (hidden); middling = faint; bad = dark. Three bands.

        Called every frame (via update()), so it tracks slow codep drift, not
        just mood changes. Cached by band index so the per-frame call is a
        no-op until the value crosses a boundary — no redundant itemconfig, no
        flicker."""
        if not self.shadow_item or not self.canvas or not self.codep:
            return
        v = self.codep.get(self.character)
        if v >= 50:
            band = 0
        elif v >= 20:
            band = 1
        else:
            band = 2
        if band == self._shadow_band:
            return
        self._shadow_band = band
        try:
            if band == 0:
                # Stable/good — no shadow.
                self.canvas.itemconfig(self.shadow_item, state="hidden")
            elif band == 1:
                # Wobbling — faint shadow.
                self.canvas.itemconfig(self.shadow_item, state="normal",
                                     fill="#1a0a0a", stipple="gray50")
            else:
                # Bad — dark shadow.
                self.canvas.itemconfig(self.shadow_item, state="normal",
                                     fill="#000000", stipple="")
        except tk.TclError:
            pass

    def _show_frame(self, index):
        """Force the current mood to display a specific frame index."""
        frames = self.current_frameset.frames(self.facing) if self.current_frameset else []
        if not frames:
            return
        self.frame_index = index % len(frames)
        if self.image_item is not None:
            self.canvas.itemconfig(self.image_item, image=self._current_image())

    def _do_transition_to_frame1(self):
        """Fire once: switch a transition mood from frame 0 (-1) to 1 (-2)."""
        self._transition_after_id = None
        if self.current_mood not in expressions.TRANSITION_MOODS:
            return
        self._show_frame(1)

    def speak(self, line):
        # Speaking wakes a sleeping pet.
        if self.state == self.STATE_SLEEPING:
            self._wake_up()
        # Mood is set ONCE here, even for a multi-bubble monologue — the
        # expression stays while every bubble of the line shows in turn.
        self.set_mood(line.mood)
        self.last_spoke = time.monotonic()
        self.state = self.STATE_SPEAKING
        # For a -1/-2 transition mood, force back to frame 0 (-1) so re-triggering
        # the same mood replays the transition (set_mood's same-mood early return
        # would otherwise leave us holding -2). Then schedule a one-shot switch
        # to frame 1 (-2) which stays after the bubble closes.
        if line.mood in expressions.TRANSITION_MOODS and self.current_frameset \
                and len(self.current_frameset.frames(self.facing)) == 2:
            self._show_frame(0)
            self._cancel_transition()
            self._transition_after_id = self.win.after(
                config.TRANSITION_DELAY_MS, self._do_transition_to_frame1)
        # Bubbles to show: a single string, or a list for a monologue.
        bubbles = list(line.text) if line.is_multi else [line.text]
        # Freeze self (and partner) for the whole run of bubbles.
        hold = time.monotonic() + len(bubbles) * config.BUBBLE_HOLD + 0.2
        self.freeze_until(hold)
        if self.on_partner_freeze:
            self.on_partner_freeze(self)
        # Show bubbles sequentially, each held BUBBLE_HOLD seconds. The i-th
        # after callback shows bubble i; a fresh speak() cancels any pending
        # ones via the _speaking_after_id / _bubble_after_id chains below.
        self._cancel_speaking_timers()
        self._speak_bubble_sequence(bubbles, 0)
        # Return to idle one BUBBLE_HOLD after the last bubble appears.
        total_ms = int(len(bubbles) * config.BUBBLE_HOLD * 1000)
        self._speaking_after_id = self.win.after(
            total_ms, self._after_speaking) if self.win else None

    def _cancel_speaking_timers(self):
        """Cancel pending bubble-sequence and return-to-idle timers from a
        previous speak() so a quick re-speak can't leak stale callbacks."""
        for attr in ("_bubble_seq_after_id",):
            tid = getattr(self, attr, None)
            if tid is not None and self.win:
                try:
                    self.win.after_cancel(tid)
                except Exception:
                    pass
            setattr(self, attr, None)
        if self._speaking_after_id is not None and self.win:
            try:
                self.win.after_cancel(self._speaking_after_id)
            except Exception:
                pass
        self._speaking_after_id = None

    def _speak_bubble_sequence(self, bubbles, index):
        """Show bubbles[index]; schedule the next one BUBBLE_HOLD later."""
        if index >= len(bubbles) or not self.win:
            self._bubble_seq_after_id = None
            return
        self._show_bubble(bubbles[index])
        if index + 1 < len(bubbles):
            delay = int(config.BUBBLE_HOLD * 1000)
            self._bubble_seq_after_id = self.win.after(
                delay, lambda: self._speak_bubble_sequence(bubbles, index + 1))
        else:
            self._bubble_seq_after_id = None

    def _after_speaking(self):
        self._speaking_after_id = None
        if self.state == self.STATE_SPEAKING:
            self.state = self.STATE_IDLE
            self.idle_timer = self.rng.uniform(*config.IDLE_PAUSE_RANGE)

    def can_speak(self):
        scale = config.DISTANCE_BAND_COOLDOWN_SCALE.get(self.distance_band, 1.0)
        return (time.monotonic() - self.last_spoke) >= config.DIALOGUE_COOLDOWN * scale

    # ---------- event dispatch (called by PetApp when scheduler fires) ----------
    def handle_event(self, event):
        # Sleeping pets stay asleep: no wandering, no idle mood drift, no
        # random dialogue. They wake only on click/drag/speak-from-outside
        # (e.g. AI chat) or when a partner moves away (see _update_sleep).
        if self.state == self.STATE_SLEEPING:
            return
        if event == "wander":
            if self.movement_enabled:
                self.wander()
        elif event == "expression":
            codep = self.codep.level(self.character) if self.codep else "passive"
            mood = expressions.weighted_idle_mood(self.character, self.distance_band, self.rng, codep)
            self.set_mood(mood)
        elif event == "dialogue":
            if self.speaking_enabled and self.can_speak():
                line = self.dialogue.random_line(self.character, rng=self.rng)
                if line:
                    self.speak(line)
                elif self.movement_enabled:
                    self.wander()
            elif self.movement_enabled:
                self.wander()
        # "interaction" events are driven by InteractionDirector.maybe_trigger
        # in PetApp._tick, not by the per-pet scheduler, so they need no branch
        # here.

    # ---------- dragging ----------
    def _on_drag_start(self, event):
        self.unfreeze()  # user drag takes priority over a speech freeze
        self._drag_data = (event.x_root - self.x, event.y_root - self.y)
        # Record press to distinguish a click from a drag on release.
        self._press_pos = (event.x_root, event.y_root, time.monotonic())

    def _on_drag_motion(self, event):
        if not self._drag_data:
            return
        ox, oy = self._drag_data
        self.x = event.x_root - ox
        self.y = event.y_root - oy
        self.state = self.STATE_IDLE
        self.target_x, self.target_y = self.x, self.y
        size = config.PLACEHOLDER_SIZE
        self._clamp_position(size)
        self._move_window()

    def _on_drag_end(self, event):
        self._drag_data = None
        # Click-vs-drag: if the press barely moved, it's a click (poke).
        if self._press_pos is not None:
            px, py, pt = self._press_pos
            moved = math.hypot((event.x_root if event else px) - px,
                               (event.y_root if event else py) - py)
            self._press_pos = None
            if moved <= config.CLICK_DRAG_PX:
                self._on_poked()
                return
        # Drag-onto-partner: if we just dropped on top of the other pet, fire a
        # special scene (direction-aware: who was dragged onto whom).
        if self.on_drag_onto_partner and self.partner_ref:
            partner = self.partner_ref
            dist = math.hypot(self.x - partner.x, self.y - partner.y)
            if dist <= config.DRAG_ONTO_DIST:
                self.on_drag_onto_partner(self, partner)

    def _on_poked(self):
        """Called when the pet is clicked (not dragged). Wakes a sleeper, and
        for Andrew, rapid repeated pokes anger Ashley."""
        if self.state == self.STATE_SLEEPING:
            self._wake_up()
        if self.on_poked:
            self.on_poked(self)

    # ---------- context menu ----------
    def _on_context(self, event):
        menu = tk.Menu(self.win, tearoff=0)
        if self.on_check_state:
            menu.add_command(label="Check state",
                             command=lambda: self.on_check_state(self))
        if self.on_summon_altar:
            menu.add_command(label="Summon altar",
                             command=lambda: self.on_summon_altar(self))
        if self.on_open_backpack:
            menu.add_command(label="Backpack",
                             command=self.on_open_backpack)
        if self.on_ai_chat:
            menu.add_command(label="AI chat…",
                             command=lambda: self.on_ai_chat(self))

        # --- Settings submenu ---
        settings = tk.Menu(menu, tearoff=0)
        if self.on_set_city:
            settings.add_command(label="Set city…",
                                command=self.on_set_city)
        if self.on_toggle_music:
            settings.add_command(label="Music: On/Off",
                                command=self.on_toggle_music)
        settings.add_separator()
        settings.add_command(label="Movement: On/Off",
                             command=self._toggle_movement)
        settings.add_command(label="Speaking: On/Off",
                             command=self._toggle_speaking)
        menu.add_cascade(label="⚙ Settings", menu=settings)

        menu.add_separator()
        menu.add_command(label="Quit", command=self._quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _toggle_movement(self):
        self.movement_enabled = not self.movement_enabled
        if not self.movement_enabled:
            # Stop any current movement immediately.
            self.target_x = self.x
            self.target_y = self.y
            if self.state == self.STATE_WANDERING:
                self.state = self.STATE_IDLE
                self.idle_timer = self.rng.uniform(*config.IDLE_PAUSE_RANGE)

    def _toggle_speaking(self):
        self.speaking_enabled = not self.speaking_enabled

    def _quit(self):
        if self.on_quit:
            self.on_quit()
