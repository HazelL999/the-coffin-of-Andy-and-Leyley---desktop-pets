"""Standalone CRT Television — the cheap grey plastic TV from
The Coffin of Andy and Leyley's apartment.

Run directly:
    python tv.py

Features:
- Cheap grey plastic CRT body (NOT retro wood, NOT shiny)
- 3D bezel depth + CRT glass glare + warm phosphor glow
- Snow static noise on the screen
- Power on/off with green LED indicator
- Volume knob (0-5, click to cycle)
- Channel knob (1-12, click to cycle)
- Green digital channel display
- Red AD indicator LED
- Full-screen ad breaks (random commercial interruption)
- Draggable window (click & drag anywhere on body)
- Right-click context menu

Platform: cross-platform (Windows / macOS via Tkinter, zero deps).
"""

import math
import random
import tkinter as tk

import tv_config as C
import tv_builder as B


class CRT_TV:
    """A standalone CRT TV window. Drag to move, left-click controls,
    right-click for context menu."""

    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.standalone = root is None

        # ── State ──
        self.power_on = True
        self.volume = 3
        self.channel = 1
        self.ad_playing = False
        self.ad_cycle = 0

        # Canvas item tags
        self._power_led = None
        self._ch_display = None
        self._ad_led = None
        self._vol_ptr = None
        self._ch_ptr = None
        self._vol_pos = None
        self._ch_pos = None

        # Screen sub-canvas
        self._screen_canvas = None
        self._screen_rect = None

        # Timers
        self._static_after = None
        self._ad_after = None
        self._ad_schedule = None
        self._drag_data = None

        self._build()
        self._start()

    # ══════════════════════════════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════════════════════════════

    def _build(self):
        if self.standalone:
            self.root.withdraw()

        self.win = tk.Toplevel(self.root)
        total_w = C.BODY_W
        total_h = C.TOTAL_H

        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=C.BODY)
        self.win.geometry(f"{total_w}x{total_h}")
        self.win.resizable(False, False)

        # Main canvas
        self._c = tk.Canvas(self.win, width=total_w, height=total_h,
                            bd=0, highlightthickness=0, bg=C.BODY)
        self._c.pack()

        # ── Draw layers ──
        B.draw_body(self._c)
        sx0, sy0, sx1, sy1 = B.draw_bezel(self._c)
        self._screen_rect = B.draw_screen(self._c, sx0, sy0, sx1, sy1)
        self._create_screen_canvas(sx0, sy0, sx1, sy1)
        self._draw_controls()

        # ── Bind events ──
        self._c.bind("<Button-1>", self._drag_start)
        self._c.bind("<B1-Motion>", self._drag_move)
        self._c.bind("<ButtonRelease-1>", self._drag_end)
        self.win.bind("<Button-3>", self._context_menu)

    def _create_screen_canvas(self, sx0, sy0, sx1, sy1):
        sw = sx1 - sx0
        sh = sy1 - sy0
        self._screen_canvas = tk.Canvas(
            self.win, width=sw, height=sh,
            bd=0, highlightthickness=0, bg=C.SCR_BG)
        self._screen_canvas.place(x=sx0, y=sy0)

    # ══════════════════════════════════════════════════════════════════
    # CONTROLS
    # ══════════════════════════════════════════════════════════════════

    def _draw_controls(self):
        c = self._c
        py = C.BODY_H
        pw = C.BODY_W
        mid_y = py + C.PANEL_H // 2

        # Panel background
        B.draw_panel_bg(c)
        B.draw_panel_grid(c, py)

        # ── Power button ──
        px = int(pw * C.PANEL_PWR_X)
        self._power_led = B.draw_power_btn(c, px, mid_y)

        # Power hit area
        pw_hit = c.create_rectangle(px - 16, mid_y - 14,
                                     px + 16, mid_y + 32,
                                     fill="", outline="")
        c.tag_bind(pw_hit, "<Button-1>", lambda e: self.toggle_power())

        # ── Volume knob ──
        vx = int(pw * C.PANEL_VOL_X)
        vy = mid_y
        self._vol_pos = (vx, vy)
        self._vol_ptr = B.draw_knob(c, vx, vy, "VOL", self.volume, 5)

        vol_hit = c.create_rectangle(vx - 22, vy - 18,
                                      vx + 22, vy + 38,
                                      fill="", outline="")
        c.tag_bind(vol_hit, "<Button-1>", lambda e: self.cycle_volume())

        # ── Channel knob ──
        cx = int(pw * C.PANEL_CH_X)
        cy = mid_y
        self._ch_pos = (cx, cy)
        self._ch_ptr = B.draw_knob(c, cx, cy, "CH", self.channel, 12)

        ch_hit = c.create_rectangle(cx - 22, cy - 18,
                                     cx + 22, cy + 38,
                                     fill="", outline="")
        c.tag_bind(ch_hit, "<Button-1>", lambda e: self.cycle_channel())

        # ── Channel display ──
        dx = int(pw * C.PANEL_DISP)
        self._ch_display = B.draw_ch_display(c, dx, py + 18, self.channel)

        # ── AD LED ──
        ax = int(pw * C.PANEL_ADLED)
        self._ad_led = B.draw_ad_led(c, ax, mid_y)

        # ── Stand ──
        B.draw_stand(c)

    # ══════════════════════════════════════════════════════════════════
    # START / STOP LOOPS
    # ══════════════════════════════════════════════════════════════════

    def _start(self):
        self._start_static()
        self._schedule_ad()
        self._keep_topmost()

    def _start_static(self):
        self._draw_static()
        self._static_after = self.win.after(C.ST_MS, self._start_static)

    def _stop_static(self):
        if self._static_after:
            try:
                self.win.after_cancel(self._static_after)
            except Exception:
                pass
            self._static_after = None
        if self._screen_canvas:
            self._screen_canvas.delete("all")

    # ══════════════════════════════════════════════════════════════════
    # STATIC / SNOW
    # ══════════════════════════════════════════════════════════════════

    def _draw_static(self):
        if not self.power_on or self.ad_playing:
            return
        sc = self._screen_canvas
        if not sc:
            return
        sc.delete("all")
        sw = sc.winfo_reqwidth()
        sh = sc.winfo_reqheight()

        ps = C.ST_PX

        for y in range(0, sh, ps):
            for x in range(0, sw, ps):
                if random.random() < C.ST_DENS:
                    v = random.randint(16, 160)
                    col = f"#{v:02x}{v:02x}{v:02x}"
                    sc.create_rectangle(x, y, x + ps, y + ps,
                                        fill=col, outline="")

        # Horizontal interference lines
        if random.random() < 0.08:
            for _ in range(random.randint(1, 3)):
                ly = random.randint(0, sh - 2)
                lw = random.randint(2, 6)
                sc.create_rectangle(0, ly, sw, ly + lw,
                                    fill="#c0c0d0", outline="")

        # Occasional bright flash band
        if random.random() < 0.02:
            fy = random.randint(0, sh - 8)
            sc.create_rectangle(0, fy, sw, fy + 8,
                                fill="#d8d8e8", outline="")

    # ══════════════════════════════════════════════════════════════════
    # POWER
    # ══════════════════════════════════════════════════════════════════

    def toggle_power(self):
        self.power_on = not self.power_on
        if self.power_on:
            self._c.itemconfig(self._power_led, fill=C.LED_G)
            self._start_static()
            self._schedule_ad()
        else:
            self._c.itemconfig(self._power_led, fill=C.LED_G_DIM)
            self._stop_static()
            self._clear_ad()
            if self._screen_canvas:
                sc = self._screen_canvas
                scw = sc.winfo_reqwidth()
                sch = sc.winfo_reqheight()
                sc.create_rectangle(0, 0, scw, sch,
                                    fill=C.SCR_BG, outline="")

    # ══════════════════════════════════════════════════════════════════
    # VOLUME
    # ══════════════════════════════════════════════════════════════════

    def cycle_volume(self):
        if not self.power_on:
            return
        self.volume = (self.volume + 1) % 6
        x, y = self._vol_pos
        self._vol_ptr = B.redraw_knob_ptr(self._c, x, y,
                                          self.volume, 5, self._vol_ptr)

    # ══════════════════════════════════════════════════════════════════
    # CHANNEL
    # ══════════════════════════════════════════════════════════════════

    def cycle_channel(self):
        if not self.power_on:
            return
        self.channel = (self.channel % 12) + 1
        x, y = self._ch_pos
        self._ch_ptr = B.redraw_knob_ptr(self._c, x, y,
                                         self.channel, 12, self._ch_ptr)
        self._c.itemconfig(self._ch_display, text=f"CH {self.channel:02d}")

    # ══════════════════════════════════════════════════════════════════
    # AD BREAK
    # ══════════════════════════════════════════════════════════════════

    def _schedule_ad(self):
        if not self.power_on or self.ad_playing:
            return
        delay = random.randint(C.AD_DMIN, C.AD_DMAX)
        self._ad_schedule = self.win.after(delay, self.trigger_ad)

    def trigger_ad(self):
        if not self.power_on or self.ad_playing:
            return
        self.ad_playing = True
        self.ad_cycle += 1
        self._stop_static()
        self._c.itemconfig(self._ad_led, fill=C.LED_R)
        self._render_ad()

    def _render_ad(self):
        sc = self._screen_canvas
        w = sc.winfo_reqwidth()
        h = sc.winfo_reqheight()

        ad_type = random.choice([
            "flashy_product", "creepy", "text_only", "glitch", "infomercial"
        ])

        sc.delete("all")

        if ad_type == "flashy_product":
            bg = random.choice(["#080000", "#00000a", "#080800"])
            sc.create_rectangle(0, 0, w, h, fill=bg, outline="")
            fg = random.choice(["#ff3322", "#ffaa00", "#33ff33"])
            sc.create_text(w // 2, h // 3,
                           text="⚠ AMAZING OFFER ⚠",
                           font=("Courier New", 18, "bold"), fill=fg)
            sc.create_text(w // 2, h // 2 + 4,
                           text="★  ONLY 3 EASY PAYMENTS  ★",
                           font=("Courier New", 10), fill="#ffcc00")
            sc.create_text(w // 2, 2 * h // 3 + 4,
                           text="Call 1-800-SOULS",
                           font=("Courier New", 9), fill="#ffffff")
            sc.create_text(w // 2, 2 * h // 3 + 22,
                           text="*Shipping & handling not included",
                           font=("Courier New", 6), fill="#606060")

        elif ad_type == "creepy":
            sc.create_rectangle(0, 0, w, h, fill="#040410", outline="")
            sc.create_rectangle(1, 1, w - 1, h - 1,
                                outline="#202050", width=1)
            r = random.randint(25, 65)
            sc.create_oval(w // 2 - r, h // 2 - r,
                           w // 2 + r, h // 2 + r,
                           outline="#4040aa", width=2)
            sc.create_text(w // 2, h // 2,
                           text="?", font=("Courier New", 36, "bold"),
                           fill="#5050bb")
            sc.create_text(w // 2, h - 20,
                           text="YOU ARE BEING WATCHED",
                           font=("Courier New", 8), fill="#383868")

        elif ad_type == "text_only":
            sc.create_rectangle(0, 0, w, h, fill="#080808", outline="")
            sc.create_rectangle(4, 4, w - 4, h - 4,
                                outline="#2a2a2a", width=2)
            sc.create_text(w // 2, h // 2 - 14,
                           text="THIS SPACE FOR RENT",
                           font=("Courier New", 16, "bold"), fill="#5a5a5a")
            sc.create_text(w // 2, h // 2 + 14,
                           text="Contact: Mr. Owl",
                           font=("Courier New", 9), fill="#3a3a3a")

        elif ad_type == "glitch":
            bg = random.choice(["#0a0010", "#10000a", "#001010"])
            sc.create_rectangle(0, 0, w, h, fill=bg, outline="")
            for _ in range(80):
                gx = random.randint(0, w)
                gy = random.randint(0, h)
                v = random.randint(0, 255)
                sc.create_text(gx, gy,
                               text=chr(random.randint(33, 126)),
                               font=("Courier New", random.randint(6, 14)),
                               fill=f"#{v:02x}{v:02x}{v:02x}")
            sc.create_text(w // 2, h // 2 - 20,
                           text="█  BUY  █  CONSUME  █  OBEY  █",
                           font=("Courier New", 12, "bold"),
                           fill="#ff0000")

        else:  # infomercial
            sc.create_rectangle(0, 0, w, h, fill="#08080a", outline="")
            sc.create_line(w // 2, 10, w // 2, h - 10,
                           fill="#282828", width=1)
            sc.create_text(w // 4, h // 3,
                           text="BEFORE",
                           font=("Courier New", 10, "bold"), fill="#555")
            sc.create_text(3 * w // 4, h // 3,
                           text="AFTER",
                           font=("Courier New", 10, "bold"), fill="#555")
            sc.create_text(w // 2, h - 16,
                           text="Results may vary. Void where prohibited.",
                           font=("Courier New", 6), fill="#333")

        duration = random.randint(C.AD_DURMIN, C.AD_DURMAX)
        self._ad_after = self.win.after(duration, self._end_ad)

    def _end_ad(self):
        self.ad_playing = False
        if self._screen_canvas:
            self._screen_canvas.delete("all")
        try:
            self._c.itemconfig(self._ad_led, fill=C.LED_R_DIM)
        except Exception:
            pass
        if self.power_on:
            self._start_static()
            self._schedule_ad()

    def _clear_ad(self):
        if self._ad_after:
            try:
                self.win.after_cancel(self._ad_after)
            except Exception:
                pass
            self._ad_after = None
        if self._ad_schedule:
            try:
                self.win.after_cancel(self._ad_schedule)
            except Exception:
                pass
            self._ad_schedule = None
        self.ad_playing = False
        try:
            self._c.itemconfig(self._ad_led, fill=C.LED_R_DIM)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    # DRAG
    # ══════════════════════════════════════════════════════════════════

    def _drag_start(self, event):
        self._drag_data = (event.x_root - self.win.winfo_x(),
                           event.y_root - self.win.winfo_y())

    def _drag_move(self, event):
        if not self._drag_data:
            return
        ox, oy = self._drag_data
        self.win.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def _drag_end(self, event):
        self._drag_data = None

    # ══════════════════════════════════════════════════════════════════
    # CONTEXT MENU
    # ══════════════════════════════════════════════════════════════════

    def _context_menu(self, event):
        menu = tk.Menu(self.win, tearoff=0, bg="#1a1a20", fg="#8a8a9a",
                       activebackground="#2e2e38", activeforeground="#d0d0e0")
        status = "ON" if self.power_on else "OFF"
        menu.add_command(label=f"Power ({status})", command=self.toggle_power)
        menu.add_command(label="📺 Trigger Ad Break",
                         command=self.trigger_ad)
        menu.add_separator()
        menu.add_command(label="✕ Close", command=self.quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ══════════════════════════════════════════════════════════════════
    # TOPMOST KEEPER
    # ══════════════════════════════════════════════════════════════════

    def _keep_topmost(self):
        if self.win is None:
            return
        try:
            self.win.attributes("-topmost", False)
            self.win.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            self.win.after(4000, self._keep_topmost)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════
    # QUIT
    # ══════════════════════════════════════════════════════════════════

    def quit(self):
        self._clear_ad()
        self._stop_static()
        try:
            if self.win:
                self.win.destroy()
        except tk.TclError:
            pass
        self.win = None
        if self.standalone:
            try:
                self.root.quit()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════
# ENTRY
# ══════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    root.withdraw()
    tv = CRT_TV(root)
    root._tv = tv
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


if __name__ == "__main__":
    main()
