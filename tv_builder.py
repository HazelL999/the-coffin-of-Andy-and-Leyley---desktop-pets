"""TV visual rendering — all Canvas drawing primitives.

Each function takes a canvas and draws one part of the TV.
Pure: no state, no side effects beyond Canvas items.
"""

import math
import tv_config as C


# ══════════════════════════════════════════════════════════════════
# BODY SHELL
# ══════════════════════════════════════════════════════════════════

def draw_body(c):
    """Main body silhouette with 3D beveled edges (chamfer effect)."""
    w, h = C.BODY_W, C.BODY_H + C.PANEL_H

    # Main fill
    c.create_rectangle(0, 0, w, h, fill=C.BODY, outline="")

    # Top-edge highlight (light catches the top ridge)
    c.create_line(3, 1, w - 3, 1, fill=C.BODY_T, width=1)
    c.create_line(2, 2, w - 2, 2, fill=C.BODY_T, width=1)

    # Left bevel highlight (steeper angle catches ambient light)
    c.create_line(1, 2, 1, h - 2, fill=C.BODY_T, width=1)
    c.create_line(2, 2, 2, h - 2, fill="#40404c", width=1)

    # Right bevel shadow
    c.create_line(w - 1, 2, w - 1, h - 2, fill=C.BODY_S, width=1)
    c.create_line(w - 2, 2, w - 2, h - 2, fill="#22222a", width=1)

    # Bottom shadow
    c.create_line(3, h - 1, w - 3, h - 1, fill=C.BODY_B, width=1)
    c.create_line(3, h - 2, w - 3, h - 2, fill=C.BODY_B, width=1)

    # Subtle plastic texture: very faint vertical lines (mold lines)
    for i, x in enumerate(range(4, w - 4, 52)):
        if i % 2 == 0:
            c.create_line(x, 8, x, h - 8, fill="#383842", width=1)


# ══════════════════════════════════════════════════════════════════
# BEZEL (multi-step depth)
# ══════════════════════════════════════════════════════════════════

def draw_bezel(c):
    """Four-step bezel creating depth around the screen."""
    sx0 = C.BEZ_MARGIN
    sy0 = C.BEZ_MARGIN + 4
    sx1 = C.BODY_W - C.BEZ_MARGIN
    sy1 = C.BODY_H - C.BEZ_MARGIN

    for name, width, color in C.BEZ_STEPS:
        c.create_rectangle(sx0, sy0, sx1, sy1, fill=color, outline="")

        # Top/left edge highlight for each step
        bw1 = width // 2
        c.create_line(sx0, sy0, sx1, sy0, fill=C.BV_HI, width=1)
        c.create_line(sx0, sy0, sx0, sy1, fill=C.BV_HI, width=1)

        # Bottom/right shadow for each step
        c.create_line(sx0, sy1 - 1, sx1, sy1 - 1, fill=C.BV_SH, width=1)
        c.create_line(sx1 - 1, sy0, sx1 - 1, sy1, fill=C.BV_SH, width=1)

        # Inner corner radius illusion — small triangle fill
        c.create_rectangle(sx0 + 1, sy0 + 1, sx0 + 3, sy0 + 3,
                           fill=C.BV_HI, outline="")

        sx0 += width
        sy0 += width
        sx1 -= width
        sy1 -= width

    return sx0, sy0, sx1, sy1  # innermost bounds


# ══════════════════════════════════════════════════════════════════
# SCREEN + CRT GLASS
# ══════════════════════════════════════════════════════════════════

def draw_screen(c, sx0, sy0, sx1, sy1):
    """Draw screen background and CRT glass reflection."""
    sw = sx1 - sx0
    sh = sy1 - sy0

    # Screen dark background
    c.create_rectangle(sx0, sy0, sx1, sy1, fill=C.SCR_BG, outline="")
    screen_rect = (sx0, sy0, sx1, sy1)

    # ── CRT glass reflection layer ──

    # 1. Faint warm center glow (CRT phosphor warmth)
    glow_r = min(sw, sh) * 0.35
    cx, cy = sx0 + sw * 0.5, sy0 + sh * 0.48
    steps = 24
    # Stipple names Tk supports: "gray12", "gray25", "gray50", "gray75"
    _GRAY_STIPPLES = ["gray12", "gray25", "gray50", "gray75"]
    for i in range(steps, -1, -1):
        t = i / steps
        r = glow_r * t
        alpha = 6 * (1 - t)
        if alpha < 0.3:
            continue
        # Map alpha (0-6) to nearest valid stipple
        si = min(int(alpha / 2), 3)
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=C.GLR_WARM,
                      stipple=_GRAY_STIPPLES[si],
                      outline="")

    # 2. Curved top arc glare (curved surface catching overhead light)
    glare_h = sh * 0.28
    pts = []
    n = 20
    for i in range(n + 1):
        t = i / n
        x = sx0 + sw * t
        curve = math.sin(math.pi * t * 0.95)  # arc shape
        y = sy0 + glare_h * (1 - curve * 0.85)
        pts.extend([x, y])
    # Close polygon
    pts.extend([sx0 + sw, sy0])
    pts.extend([sx0, sy0])

    c.create_polygon(*pts, fill="", outline=C.GLR_TOP, width=1,
                     stipple="gray12")

    # 3. Secondary glare band (internal reflection)
    band_y = sy0 + sh * 0.12
    band_h = sh * 0.04
    c.create_rectangle(sx0 + sw * 0.1, band_y,
                       sx0 + sw * 0.85, band_y + band_h,
                       fill=C.GLR_TOP, outline="", stipple="gray25")

    # 4. Diagonal streak (tube reflection — one clean line)
    diag_start_x = sx0 + sw * 0.72
    diag_start_y = sy0 + sh * 0.02
    diag_end_x = sx0 + sw * 0.45
    diag_end_y = sy0 + sh * 0.35
    c.create_line(diag_start_x, diag_start_y,
                  diag_end_x, diag_end_y,
                  fill=C.GLR_LINE, width=2, stipple="gray12")

    # Second faint parallel streak
    offset = 6
    c.create_line(diag_start_x + offset, diag_start_y + offset * 0.6,
                  diag_end_x + offset, diag_end_y + offset * 0.6,
                  fill=C.GLR_LINE, width=1, stipple="gray25")

    # 5. Bottom deep shadow (tube curves away from light)
    bot_sh_h = sh * 0.06
    c.create_rectangle(sx0, sy1 - bot_sh_h, sx1, sy1,
                       fill=C.GLR_BOT, outline="")

    # 6. Screen edge glow (faint greenish light from CRT phosphors)
    for i in range(3):
        inset = 2 + i * 2
        c.create_rectangle(sx0 + inset, sy0 + inset,
                           sx1 - inset, sy1 - inset,
                           outline="#040608", width=1)

    return screen_rect


# ══════════════════════════════════════════════════════════════════
# CONTROL PANEL
# ══════════════════════════════════════════════════════════════════

def draw_panel_bg(c):
    """Control panel background with groove and brand text."""
    py = C.BODY_H
    pw = C.BODY_W

    # Panel background
    c.create_rectangle(0, py, pw, py + C.PANEL_H,
                       fill=C.PAN_BG, outline="")

    # Seam line at top (panel meets body)
    c.create_line(3, py, pw - 3, py, fill=C.PAN_SEAM, width=2)

    # Surface highlight
    c.create_line(3, py + 1, pw - 3, py + 1, fill=C.PAN_HI, width=1)

    # Bottom shadow
    c.create_line(0, py + C.PANEL_H - 1, pw, py + C.PANEL_H - 1,
                  fill=C.BODY_B, width=1)

    # Brand text
    c.create_text(pw // 2, py + 12,
                  text="TELETRON", font=("Courier New", 9, "bold"),
                  fill=C.TX_DIM, anchor="center")

    return py


def draw_panel_grid(c, py):
    """Subtle decorative grooves on the panel."""
    pw = C.BODY_W
    mid_y = py + C.PANEL_H // 2

    # Horizontal decorative groove left side (between knobs)
    for dx in [20, C.PANEL_VOL_X * pw + 22]:
        gx = int(dx)
        c.create_line(gx, mid_y - 10, gx + 6, mid_y - 10,
                      fill=C.PAN_GRV, width=1)
        c.create_line(gx, mid_y - 9, gx + 6, mid_y - 9,
                      fill=C.PAN_HI, width=1)

    # Arrow indicators for volume
    c.create_text(int(pw * C.PANEL_VOL_X), mid_y + 24,
                  text="▼", font=("Courier New", 6), fill=C.TX_DIM)

    # Arrow indicators for channel
    c.create_text(int(pw * C.PANEL_CH_X), mid_y + 24,
                  text="▲", font=("Courier New", 6), fill=C.TX_DIM)

    # Speaker grille (subtle slots)
    grille_y = py + C.PANEL_H - 6
    for i in range(7):
        gx = pw // 2 - 42 + i * 13
        c.create_rectangle(gx, grille_y - 1, gx + 7, grille_y + 1,
                           fill=C.PAN_GRV, outline="")

    # Ventilation slits at panel bottom corners
    for side in [12, pw - 24]:
        c.create_rectangle(side, py + C.PANEL_H - 4,
                           side + 10, py + C.PANEL_H - 3,
                           fill=C.BODY_B, outline="")


# ══════════════════════════════════════════════════════════════════
# POWER BUTTON
# ══════════════════════════════════════════════════════════════════

def draw_power_btn(c, x, y):
    """Draw power push-button with LED. Returns (body_tag, led_tag)."""
    # Recessed oval (outer depression)
    c.create_oval(x - 9, y - 9, x + 9, y + 9,
                  fill=C.PAN_GRV, outline=C.BODY_S, width=1)

    # Button body
    c.create_oval(x - 7, y - 7, x + 7, y + 7,
                  fill=C.PW_C, outline=C.KN_OUT, width=1)

    # Button top highlight (3D convex)
    c.create_arc(x - 6, y - 6, x + 6, y + 6,
                 start=0, extent=180, fill=C.PW_HI, outline="")

    # Icon — circle with vertical line (standard power symbol)
    c.create_oval(x - 3, y - 4, x + 3, y + 2,
                  outline=C.TX_DIM, width=1)
    c.create_line(x, y - 6, x, y - 3, fill=C.TX_DIM, width=1)

    # LED indicator (green when on, off when off)
    led_tag = c.create_oval(x - 3, y + 10, x + 3, y + 16,
                            fill=C.LED_G, outline="")

    # Label
    c.create_text(x, y + 24, text="POWER",
                  font=("Courier New", 6), fill=C.TX_DIM, anchor="center")

    return led_tag


# ══════════════════════════════════════════════════════════════════
# KNOB
# ══════════════════════════════════════════════════════════════════

def draw_knob(c, x, y, label, value, max_val):
    """Draw a rotary knob with position pointer. Returns pointer_tag."""
    # Outer shadow ring
    c.create_oval(x - C.KNOB_R - 2, y - C.KNOB_R - 2,
                  x + C.KNOB_R + 2, y + C.KNOB_R + 2,
                  fill=C.PAN_GRV, outline="")

    # Knob body (recessed)
    c.create_oval(x - C.KNOB_R, y - C.KNOB_R,
                  x + C.KNOB_R, y + C.KNOB_R,
                  fill=C.KN_C, outline=C.KN_OUT, width=1)

    # Inner ring
    c.create_oval(x - C.KNOB_R + 3, y - C.KNOB_R + 3,
                  x + C.KNOB_R - 3, y + C.KNOB_R - 3,
                  fill=C.KN_IN, outline="#2a2a36", width=1)

    # Top-left highlight arc (3D convex)
    c.create_arc(x - C.KNOB_R + 1, y - C.KNOB_R + 1,
                 x + C.KNOB_R - 1, y + C.KNOB_R - 1,
                 start=225, extent=135, fill=C.KN_HI, outline="",
                 stipple="gray25")

    # Grip ridges (tiny lines around rim)
    for i in range(8):
        ang = math.radians(i * 45)
        ri = C.KNOB_R - 2
        ro = C.KNOB_R
        c.create_line(
            x + ri * math.cos(ang), y + ri * math.sin(ang),
            x + ro * math.cos(ang), y + ro * math.sin(ang),
            fill=C.KN_OUT, width=1)

    # Pointer indicator
    angle = -135 + (value / max_val) * 270
    rad = math.radians(angle)
    ix = x + C.KNOB_R * 0.2 * math.cos(rad)
    iy = y + C.KNOB_R * 0.2 * math.sin(rad)
    ox = x + C.KNOB_R * 0.75 * math.cos(rad)
    oy = y + C.KNOB_R * 0.75 * math.sin(rad)
    ptr = c.create_line(ix, iy, ox, oy, fill=C.KN_PTR, width=2,
                        capstyle="round")

    # Label
    c.create_text(x, y + C.KNOB_R + 18, text=label,
                  font=("Courier New", 7, "bold"),
                  fill=C.TX_DIM, anchor="center")

    return ptr


# ══════════════════════════════════════════════════════════════════
# DIGITAL CHANNEL DISPLAY
# ══════════════════════════════════════════════════════════════════

def draw_ch_display(c, x, y, ch):
    """Green digital channel number display. Returns text_tag."""
    # Housing
    c.create_rectangle(x - 22, y - 10, x + 22, y + 10,
                       fill=C.DP_BG, outline=C.DP_BRD, width=1)

    # Inner glow line
    c.create_rectangle(x - 21, y - 9, x + 21, y + 9,
                       outline="#121220", width=1)

    # Text
    tag = c.create_text(x, y, text=f"CH {ch:02d}",
                        font=("Courier New", 12, "bold"),
                        fill=C.TX_GREEN, anchor="center")
    return tag


# ══════════════════════════════════════════════════════════════════
# AD INDICATOR LED
# ══════════════════════════════════════════════════════════════════

def draw_ad_led(c, x, y):
    """Red AD indicator LED. Returns oval_tag."""
    # Housing
    c.create_oval(x - 5, y - 5, x + 5, y + 5,
                  fill=C.DP_BG, outline=C.DP_BRD, width=1)

    # LED
    tag = c.create_oval(x - 3, y - 3, x + 3, y + 3,
                        fill=C.LED_R_DIM, outline="")

    # Label
    c.create_text(x, y + 16, text="AD",
                  font=("Courier New", 7, "bold"),
                  fill=C.TX_DIM, anchor="center")
    return tag


# ══════════════════════════════════════════════════════════════════
# STAND / BASE
# ══════════════════════════════════════════════════════════════════

def draw_stand(c):
    """Draw the base stand with feet."""
    base_y = C.BODY_H + C.PANEL_H
    tw = C.BODY_W

    # Base block — narrower than body
    base_w = tw - 80
    base_x = (tw - base_w) // 2

    c.create_rectangle(base_x, base_y, base_x + base_w, base_y + C.STAND_H,
                       fill=C.ST_C, outline="")

    # Top edge highlight
    c.create_line(base_x + 4, base_y, base_x + base_w - 4, base_y,
                  fill=C.PAN_HI, width=1)

    # Bottom shadow
    c.create_line(base_x + 4, base_y + C.STAND_H - 1,
                  base_x + base_w - 4, base_y + C.STAND_H - 1,
                  fill=C.ST_B, width=1)

    # Sides shadow
    c.create_line(base_x, base_y, base_x, base_y + C.STAND_H,
                  fill=C.ST_S, width=1)
    c.create_line(base_x + base_w, base_y, base_x + base_w, base_y + C.STAND_H,
                  fill=C.ST_S, width=1)

    # Vertical groove on stand
    center_groove = tw // 2
    c.create_line(center_groove, base_y + 2,
                  center_groove, base_y + C.STAND_H - 2,
                  fill=C.PAN_GRV, width=1)

    # Two rubber feet
    foot_w = 36
    foot_h = 4
    for f_x in [base_x + 12, base_x + base_w - 12 - foot_w]:
        c.create_rectangle(f_x, base_y + C.STAND_H,
                           f_x + foot_w, base_y + C.STAND_H + foot_h,
                           fill=C.FOOT_C, outline="")


# ══════════════════════════════════════════════════════════════════
# UPDATE HELPERS (pointer redraw)
# ══════════════════════════════════════════════════════════════════

def redraw_knob_ptr(c, x, y, value, max_val, old_ptr):
    """Delete old pointer, draw new one, return new tag."""
    c.delete(old_ptr)
    angle = -135 + (value / max_val) * 270
    rad = math.radians(angle)
    ix = x + C.KNOB_R * 0.2 * math.cos(rad)
    iy = y + C.KNOB_R * 0.2 * math.sin(rad)
    ox = x + C.KNOB_R * 0.75 * math.cos(rad)
    oy = y + C.KNOB_R * 0.75 * math.sin(rad)
    return c.create_line(ix, iy, ox, oy, fill=C.KN_PTR, width=2,
                         capstyle="round")
