"""Catch a Soul -- a flower-field soul-catching minigame.

Summoned from a pet's right-click menu. Hides the desktop pets and shows a
fullscreen game window: a red flower field with 15 floating souls (12 white
teardrops + 1 pink Ashley + 1 green Andrew + 1 grime + 1 tar). The player
wields a beer-bottle container to catch white souls; pink/green dodge fast
and touching them shakes the screen red. 30-second countdown. Caught white
souls feed the altar's sacrifice count; picked flowers feed a persistent
backpack count.

Clean rewrite of a reference impl -- keeps the essence (ghost outline,
tapered petals, layered bottle, dodge multipliers), drops the dross
(per-pixel gradients, python flood-fill, hardcoded sizes, global key binds,
empty end-game). Cross-platform: the game window is an opaque Toplevel over
a transparent fullscreen overlay (same pattern as the TV mode), so macOS
create_image works without the NSImage bridge.
"""

import math
import random
import tkinter as tk
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image, ImageDraw, ImageTk

import config
import platform_utils

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

WIN_W, WIN_H = 900, 650
BG_COLOR = "#2a3a28"            # field ground (dark grey-green)

FLOWER_COUNT = 12               # clusters of red flowers along the bottom
FLOWER_COLOR = "#cc2222"        # red petals
STEM_COLOR = "#524940"
STEM_WIDTH = 3
FLOWER_OFFSETS = [(-9, -18, -11), (0, 10, 0), (11, -8, 13)]  # (dx, stem_adj, slant)
# Petals-image geometry (anchor="sw"; stems attach at fy - FLOWER_CY_OFF).
FLOWER_STEM_LEN_BASE = 50
FLOWER_CX = 52
FLOWER_CY_OFF = 36

# Souls: 1 ashley + 1 andrew + 1 tar + 1 grime + rest teardrops (=12)
SOUL_COUNT = 15
SOUL_SPEED = 70.0               # drift speed px/s (all kinds, at rest)
TEARDROP_H = 38              # teardrop (white soul) sprite height; uses Altar/soul.png
GHOST_W, GHOST_H = 34, 57       # ashley/andrew/tar
TAR_W, TAR_H = 38, 46
ESCAPE_RADIUS = 80.0            # jar within this distance triggers dodge
# Multiplier on escape speed when the jar is close. None = never dodges.
DODGE_MULT = {
    "teardrop": 1.2,
    "ashley":   2.6,
    "andrew":   2.6,
    "tar":    None,
    "grime":      None,
}

BOTTLE_R = 20                   # collision radius for the bottle
PICK_RADIUS = 28

GAME_DURATION = 30              # seconds

# Shake / red flash when the player tries to grab a pink/green soul.
SHAKE_AMPLITUDE = 14
SHAKE_DECAY = 0.88
RED_OVERLAY = "#ff2222"
RED_STIPPLE = "gray50"

AA_SCALE = 4                    # PIL supersample for smooth edges

# Colors per soul kind.
GHOST_FILL_ASHLEY = (208, 117, 178)
GHOST_EYE_ASHLEY = (74, 50, 82)
GHOST_FILL_ANDREW = (100, 195, 100)
GHOST_EYE_ANDREW = (40, 100, 40)
GHOST_OUTLINE = (18, 14, 18)

GRIME_TOP = (0, 0, 0)
GRIME_BOT = (195, 40, 35)
GRIME_EYE = (220, 30, 30)


# ---------------------------------------------------------------------------
# PIL pre-rendered sprites (module-level cache)
# ---------------------------------------------------------------------------

def _supersample(img: Image.Image, s: int) -> Image.Image:
    """Draw at s× then LANCZOS-down to 1× for smooth edges."""
    return img.resize((img.width // s, img.height // s), Image.LANCZOS)


def _tapered_petal(draw, cx, cy, angle_deg, length, r_base, r_tip, s, color):
    """One petal: narrow at base, round at tip, pointing out at angle_deg."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    ux, uy = ca, sa
    px, py = -sa, ca
    bx, by = cx, cy
    tx, ty = cx + length * ux, cy + length * uy
    poly = [
        (bx - px * r_base, by - py * r_base),
        (tx - px * r_tip, ty - py * r_tip),
        (tx + px * r_tip, ty + py * r_tip),
        (bx + px * r_base, by + py * r_base),
    ]
    draw.polygon(poly, fill=color)
    draw.ellipse([tx - r_tip, ty - r_tip, tx + r_tip, ty + r_tip], fill=color)


_petals_photo: Optional[ImageTk.PhotoImage] = None
_petals_anchor = (0.0, 0.0)


def _petals_image():
    """Pre-render a cluster of three red flowers (petals only; stems drawn on
    canvas). Returns (PhotoImage, anchor_x, anchor_y) where anchor is the
    bottom-center of the cluster (where the stems meet the ground)."""
    global _petals_photo, _petals_anchor
    if _petals_photo is not None:
        return _petals_photo, _petals_anchor
    s = AA_SCALE
    cluster_w, cluster_h = 80, FLOWER_STEM_LEN_BASE + 40
    pad = 12
    img_w = int((cluster_w + pad * 2) * s)
    img_h = int((cluster_h + pad * 2) * s)
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    base_cx = (cluster_w / 2 + pad) * s
    base_cy = (cluster_h - pad) * s
    petal_len = 10.0 * s
    r_tip, r_base = 3.3 * s, 2.2 * s
    for dx, stem_adj, slant in FLOWER_OFFSETS:
        fx = base_cx + dx * s
        stem_px = (50 + stem_adj) * s
        flower_x = fx + slant * s
        flower_y = base_cy - stem_px
        for i in range(6):
            angle = i * 60 + random.uniform(-8, 8)
            plen = petal_len * random.uniform(0.65, 1.0)
            rt = r_tip * random.uniform(0.8, 1.2)
            rb = r_base * random.uniform(0.7, 1.3)
            _tapered_petal(draw, flower_x, flower_y, angle, plen, rb, rt, s,
                           FLOWER_COLOR)
    img = _supersample(img, s)
    _petals_photo = ImageTk.PhotoImage(img)
    _petals_anchor = (base_cx / s, base_cy / s)
    return _petals_photo, _petals_anchor


def _ghost_points(cx, cy, w, h, steps=64):
    """Halloween-ghost outline: round head + flared body + three scallop feet.
    Returns a flat [x0,y0, ...] list. Symmetric and parameterised."""
    r = w / 2
    top = cy - h / 2
    half = steps // 2
    body_w = r * 1.16
    foot_r = body_w / 3
    body_bot = cy + h / 2 - r * 0.40
    foot_cy = body_bot - foot_r
    pts = []
    # top semicircle left-shoulder -> top -> right-shoulder
    for i in range(half + 1):
        a = math.pi + math.pi * i / half
        pts.append((cx + r * math.cos(a), top + r + r * math.sin(a)))
    # right body flare down
    n_body = int(half * 0.8)
    for i in range(1, n_body + 1):
        t = i / n_body
        y = (top + r) + (foot_cy - (top + r)) * t
        x = cx + r * (1.0 + 0.16 * (1 - math.cos(math.pi * t)) / 2)
        pts.append((x, y))
    # three feet (right -> left), each a downward half-ellipse
    f0 = cx - body_w + foot_r
    f1 = cx - body_w + 2 * foot_r + foot_r
    f2 = cx + body_w - foot_r
    n_foot = int(half * 0.5)
    for fcx in (f2, f1, f0):
        for i in range(n_foot + 1):
            a = math.pi * i / n_foot
            pts.append((fcx + foot_r * math.cos(a),
                        foot_cy + foot_r * math.sin(a)))
    # left body back up
    for i in range(n_body, 0, -1):
        t = i / n_body
        y = (top + r) + (foot_cy - (top + r)) * t
        x = cx - r * (1.0 + 0.16 * (1 - math.cos(math.pi * t)) / 2)
        pts.append((x, y))
    return pts


_ghost_photos = {}  # (kind, w, h) -> (PhotoImage, pad)


def _ghost_image(kind, w, h, pad_ratio=0.18):
    """Pre-render a ghost PNG (ashley/andrew share shape, differ color)."""
    key = (kind, w, h)
    if key in _ghost_photos:
        return _ghost_photos[key]
    s = AA_SCALE
    pw, ph = int(w * (1 + pad_ratio * 2)), int(h * (1 + pad_ratio * 2))
    W, H = int(pw * s), int(ph * s)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    pts = _ghost_points(cx, cy, w * s, h * s)
    flat = [v for p in pts for v in p]
    # black outline (slightly larger)
    outer = [(cx + (x - cx) * 1.025, cy + (y - cy) * 1.025) for x, y in pts]
    d.polygon([v for p in outer for v in p], fill=GHOST_OUTLINE)
    if kind == "ashley":
        fill, eye = GHOST_FILL_ASHLEY, GHOST_EYE_ASHLEY
    else:
        fill, eye = GHOST_FILL_ANDREW, GHOST_EYE_ANDREW
    d.polygon(flat, fill=fill + (255,))
    eye_r = w * s * 0.085
    eye_y = cy - h * s * 0.20
    for ex in (cx - w * s * 0.19, cx + w * s * 0.19):
        d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                  fill=eye + (255,))
    img = _supersample(img, s)
    photo = ImageTk.PhotoImage(img)
    _ghost_photos[key] = (photo, pad_ratio)
    return photo, pad_ratio


# ---------------------------------------------------------------------------
# Grime / Tar body outlines (ported verbatim from the reference impl -- these
# are the shape-correct generators; only the slow flood-fill helpers from the
# reference were dropped in favour of the existing _fill_inside above).
# ---------------------------------------------------------------------------

def _tar_body_points(cx, cy, w, h, ear_w=0.18, ear_h=0.30):
    """Tar body outline: Ashley-like curved body but irregular, two cat ears
    (pointed top, wide base). Returns (body_pts, [foot_pts, ...]):
      body_pts is the body+ears outline (no feet);
      the four feet are independent polygons (vertical olive shape) so they
      keep transparent gaps between them when rendered.
    """
    r = w / 2               # head half-width
    top = cy - h / 2        # head top y
    bot = cy + h / 2        # foot bottom y

    body_bot = bot - h * 0.08  # torso bottom (feet extend below this)
    body_w = r * 1.20          # body bottom half-width (flared, wider than head)

    # ear params (cat ear: pointed top, wide base, outer edge bulges out)
    ear_w_px = w * ear_w          # ear base half-width reference
    ear_h_px = h * ear_h          # ear height reference
    ear_inset = w * 0.22          # ear horizontal inset on the head top

    steps = 64
    half = steps // 2

    body_pts = []

    # 1) left ear: cat ear (outer bulge + pointed cap)
    ear_left_cx = cx - ear_inset - ear_w_px * 0.35
    ear_left_top = top - ear_h_px * 0.65
    r_tip = ear_w_px * 0.04
    # left ear outer edge (left side): base -> tip, bulging arc
    for i in range(5):
        t = i / 4                     # 0=base, 1=tip
        base = (1 - r_tip / ear_w_px) * (1 - t**3) + r_tip / ear_w_px
        bulge = 0.02 * t * (1 - t)    # mid outward bulge
        offset = base + bulge
        x = ear_left_cx - ear_w_px * offset
        y = top + (ear_left_top - top) * t
        body_pts.append((x, y))
    # pointed cap: half circle from a=pi(left) to a=0(right) through the top
    for i in range(5):
        a = math.pi - math.pi * i / 4
        x = ear_left_cx + r_tip * math.cos(a)
        y = ear_left_top + r_tip * math.sin(a)
        body_pts.append((x, y))
    # left ear inner edge (right side): tip -> base
    for i in range(5):
        t = i / 4                     # 0=tip, 1=base
        curve = 1 - 0.25 * math.sin(math.pi * t)  # outward push to the left
        offset = (r_tip / ear_w_px) * (1 - t) + 0.45 * t
        x = ear_left_cx + ear_w_px * offset * curve
        y = ear_left_top + (top - ear_left_top) * t
        body_pts.append((x, y))

    # 2) top arc (between the ears): left ear inner base -> right ear inner base
    ear_right_cx = cx + ear_inset + ear_w_px * 0.35
    ear_right_top = top - ear_h_px * 0.65
    x_arc0 = ear_left_cx + ear_w_px * 0.45      # left ear inner base x
    x_arc1 = ear_right_cx - ear_w_px * 0.45     # right ear inner base x
    for i in range(7):
        t = i / 6
        x = x_arc0 + (x_arc1 - x_arc0) * t
        y = top - r * 0.15 * math.sin(math.pi * t)
        body_pts.append((x, y))

    # 3) right ear: cat ear (mirror of left, outer bulge + pointed cap)
    # right ear inner edge (left side): base -> tip
    for i in range(5):
        t = i / 4                     # 0=base, 1=tip
        curve = 1 - 0.25 * math.sin(math.pi * t)  # outward push to the right
        offset = 0.45 * (1 - t) + (r_tip / ear_w_px) * t
        x = ear_right_cx - ear_w_px * offset * curve
        y = top + (ear_right_top - top) * t
        body_pts.append((x, y))
    # right ear pointed cap (mirror, same half-circle direction)
    for i in range(5):
        a = math.pi - math.pi * i / 4
        x = ear_right_cx + r_tip * math.cos(a)
        y = ear_right_top + r_tip * math.sin(a)
        body_pts.append((x, y))
    # right ear outer edge (right side): tip -> base (must go tip->base or the
    # polygon path crosses itself and the ear "folds")
    for i in range(5):
        t = i / 4                     # 0=tip, 1=base
        u = 1 - t                     # 0=base, 1=tip (same param as left outer)
        base = (1 - r_tip / ear_w_px) * (1 - u**3) + r_tip / ear_w_px
        bulge = 0.02 * u * (1 - u)
        offset = base + bulge
        x = ear_right_cx + ear_w_px * offset
        y = ear_right_top + (top - ear_right_top) * t
        body_pts.append((x, y))

    # 4) right body: right ear inner -> bottom-right (flare + slight waist dip)
    waist = 0.08
    n_body = int(half * 0.5)
    for i in range(1, n_body + 1):
        t = i / n_body
        y = top + (body_bot - top) * t
        bulge_out = 0.20 * (1 - math.cos(math.pi * t)) / 2
        waist_in = waist * math.sin(math.pi * t) ** 4
        x = cx + r * (1.0 + bulge_out - waist_in)
        body_pts.append((x, y))

    # 5) left body: bottom-left -> left ear inner (mirror of right)
    for i in range(n_body, 0, -1):
        t = i / n_body
        y = top + (body_bot - top) * t
        bulge_out = 0.20 * (1 - math.cos(math.pi * t)) / 2
        waist_in = waist * math.sin(math.pi * t) ** 4
        x = cx - r * (1.0 + bulge_out - waist_in)
        body_pts.append((x, y))

    # 6) four feet (independent polygons, vertical olive/pointed-ellipse,
    #    each a different size for irregularity). Deterministic RNG so the
    #    shape is stable across calls.
    foot_h = h * 0.22
    foot_top = body_bot - h * 0.03  # feet tops overlap the body (no seam)
    foot_rng = random.Random(42)
    foot_width_scales = [1.15, 0.92, 1.10, 0.98]
    foot_height_scales = [0.95, 1.05, 0.97, 1.02]
    width_scales = [s * foot_rng.uniform(0.96, 1.04) for s in foot_width_scales]
    height_scales = [s * foot_rng.uniform(0.96, 1.04) for s in foot_height_scales]
    w_sum = sum(width_scales)
    total_hw = body_w * 0.94
    half_widths = [total_hw * s / w_sum for s in width_scales]
    heights = [foot_h * s for s in height_scales]
    gap = (2 * body_w - 2 * total_hw) / 3
    x = cx - body_w
    foot_centers = []
    for hw in half_widths:
        foot_centers.append(x + hw)
        x += hw * 2 + gap

    n_foot = 10
    feet = []
    for idx, fcx in enumerate(foot_centers):
        lw = half_widths[idx]
        lh = heights[idx]
        foot = []
        # right side: top(wide) -> bottom(rounded, 0.20 width)
        for i in range(n_foot + 1):
            t = i / n_foot          # 0 -> 1, top to bottom
            ww = 0.20 + 0.80 * (1.0 - t * t)
            x = fcx + lw * ww
            y = foot_top + lh * t
            foot.append((x, y))
        # left side: bottom -> top
        for i in range(n_foot, -1, -1):
            t = i / n_foot
            ww = 0.20 + 0.80 * (1.0 - t * t)
            x = fcx - lw * ww
            y = foot_top + lh * t
            foot.append((x, y))
        feet.append(foot)

    return body_pts, feet


def _grime_body_points(cx, cy, w, h):
    """Grime body outline: rounded head (no ears) + straight body + 6 flame
    tentacles (2 vertical on the head, 2 x 45deg + 2 x 10deg on the sides).
    Returns (body_pts, []) -- the three short feet are emitted into body_pts
    (not separate polygons) so the body+feet are one closed outline.
    """
    r = w / 2               # body half-width
    top = cy - h / 2
    bot = cy + h / 2
    body_bot = bot - h * 0.25   # torso bottom (feet extend below this)
    head_h = r * 0.55           # head height
    head_scale = 2.0 / 3.0      # head widest = 2/3 body width
    HEAD_POWER = 1.0            # head arc power (1.0 = pure half-ellipse)

    # tentacle params
    # row 1: two vertical tentacles riding the head arc (grow upward)
    tent_v = (head_h * 0.99, head_h * 0.25, w * 0.18)
    V_TENT_THICK = 2.4
    # rows 2,3: horizontal capsule tentacles on the straight body sides
    tent_params = [
        (0.38, w * 0.24, w * 0.60),  # row 2 (45deg flame)
        (0.38 + (w * 0.24 + w * 0.12) / h, w * 0.12, w * 0.5),  # row 3 (10deg)
    ]

    y_shoulder = top + head_h
    y_full = y_shoulder + h * 0.12

    def _right_edge(y):
        if y <= y_shoulder and head_h > 0:
            u = (y - top) / head_h
            if 0.0 <= u <= 1.0:
                arc = math.sqrt(max(0.0, 2.0 * u - u * u))
                cos_a = arc ** HEAD_POWER
                return cx + r * head_scale * cos_a
        if y <= y_full:
            v = (y - y_shoulder) / (y_full - y_shoulder)
            expand = head_scale + (1.0 - head_scale) * (1.0 - math.cos(math.pi * v)) / 2.0
            return cx + r * expand
        return cx + r * 1.0

    def _left_edge(y):
        return 2 * cx - _right_edge(y)

    def _tentacle(by, base_hw, reach, sign, thick=1.0):
        """Horizontal capsule tentacle: straight edges (constant width) ->
        half-circle cap -> straight edges. Continuous outline."""
        edge = _right_edge if sign > 0 else _left_edge
        base_hw = base_hw * thick
        reach = reach * thick
        r_bot = by + base_hw
        r_top = by - base_hw
        ex_bot = edge(r_bot)
        ex_top = edge(r_top)
        cap_cx = ex_bot + sign * reach
        cap_cy = by
        n = 10
        pts = []
        bot_p = (cap_cx, r_bot)
        for i in range(n + 1):
            t = i / n
            x = ex_bot + (bot_p[0] - ex_bot) * t
            y = r_bot + (bot_p[1] - r_bot) * t
            pts.append((x, y))
        for i in range(n + 1):
            t = i / n
            a = math.pi / 2 + math.pi * t
            x = cap_cx + base_hw * math.cos(a)
            y = cap_cy + base_hw * math.sin(a)
            pts.append((x, y))
        top_p = (cap_cx, r_top)
        for i in range(1, n + 1):
            t = i / n
            x = top_p[0] + (ex_top - top_p[0]) * t
            y = top_p[1] + (r_top - top_p[1]) * t
            pts.append((x, y))
        if sign < 0:
            pts.reverse()
        return pts

    def _tentacle_v(y_bot_rel, y_top_rel, reach, sign, thick=1.0):
        """Vertical flame tentacle riding the head arc, growing straight up.
        Per-point sampling along a vertical centerline, half-width tapering
        from root to tip, half-circle cap at the tip."""
        reach = reach * thick
        y_bot = top + y_bot_rel
        y_top = top + y_top_rel
        edge = _right_edge if sign > 0 else _left_edge
        ex_bot = edge(y_bot)
        ex_top = edge(y_top)
        mid_x = (ex_bot + ex_top) / 2.0
        base_hw = (y_bot_rel - y_top_rel) / 2.0 * thick
        y_tip = y_top - reach
        n = 24
        side = 1 if sign > 0 else -1
        root_hw = base_hw * 0.70
        cap_r = base_hw * 0.18
        ramp_t = 0.30

        def _centerline(t):
            return mid_x, y_bot + (y_tip - y_bot) * t

        def _hw(t):
            return root_hw * (1.0 - t ** 1.5) + cap_r

        def _inner_pt(t):
            ccx, ccy = _centerline(t)
            return ccx - side * _hw(t), ccy

        def _outer_pt(t):
            ccx, ccy = _centerline(t)
            return ccx + side * _hw(t), ccy

        def _inner_ramp(t):
            px, py = _inner_pt(t)
            if t <= ramp_t:
                uu = (1.0 - t / ramp_t) ** 2
                sx = mid_x - side * root_hw
                return sx * uu + px * (1.0 - uu), y_top * uu + py * (1.0 - uu)
            return px, py

        def _outer_ramp(t):
            px, py = _outer_pt(t)
            if t <= ramp_t:
                uu = (1.0 - t / ramp_t) ** 2
                return ex_bot * uu + px * (1.0 - uu), y_bot * uu + py * (1.0 - uu)
            return px, py

        pts = []
        for i in range(n + 1):
            pts.append(_inner_ramp(i / n))
        tips_n = n // 2
        for i in range(1, tips_n + 1):
            t = i / tips_n
            a = math.pi * t if sign < 0 else math.pi * (1 - t)
            pts.append((mid_x + cap_r * math.cos(a),
                        y_tip - cap_r * math.sin(a)))
        for i in range(n, -1, -1):
            pts.append(_outer_ramp(i / n))
        if sign < 0:
            pts.reverse()
        return pts

    def _tentacle_flame_45(by, base_hw, reach, sign, thick=1.0):
        """45-degree upward flame tentacle: per-point sampling along a center
        line that starts at 45deg and curves upward."""
        edge = _right_edge if sign > 0 else _left_edge
        base_hw = base_hw * thick
        reach = reach * thick
        r_bot = by + base_hw
        r_top = by - base_hw
        ex_bot = edge(r_bot)
        ex_top = edge(r_top)
        mid_x = (ex_bot + ex_top) / 2.0
        cos45 = 0.7071067811865476
        bend_x = 0.25
        bend_y = 0.40
        n = 24
        root_hw = base_hw * 0.70
        cap_r = base_hw * 0.18

        def _centerline(t):
            x = mid_x + sign * reach * (cos45 * t - bend_x * t * t)
            y = by - reach * (cos45 * t + bend_y * t * t)
            return x, y

        def _tangent(t):
            dx = sign * reach * (cos45 - 2 * bend_x * t)
            dy = -reach * (cos45 + 2 * bend_y * t)
            return dx, dy

        def _width(t):
            return root_hw * (1.0 - t ** 1.5) + cap_r

        def _normal(t, outer=True):
            tx, ty = _tangent(t)
            if outer:
                nx = -ty if sign > 0 else ty
                ny = tx if sign > 0 else -tx
            else:
                nx = ty if sign > 0 else -ty
                ny = -tx if sign > 0 else tx
            length = math.hypot(nx, ny)
            if length > 0:
                nx, ny = nx / length, ny / length
            return nx, ny

        pts = []
        ramp_t = 0.30
        for i in range(n + 1):
            t = i / n
            ccx, ccy = _centerline(t)
            nx, ny = _normal(t, outer=True)
            w = _width(t)
            if t <= ramp_t:
                u = t / ramp_t
                uu = (1 - u) ** 2
                px = ex_bot * uu + (ccx + nx * w) * (1 - uu)
                py = r_bot * uu + (ccy + ny * w) * (1 - uu)
                pts.append((px, py))
            else:
                pts.append((ccx + nx * w, ccy + ny * w))
        tips_n = n // 2
        c_tip_x, c_tip_y = _centerline(1.0)
        tip_tx, tip_ty = _tangent(1.0)
        tip_len = math.hypot(tip_tx, tip_ty)
        if tip_len > 0:
            tip_dx, tip_dy = tip_tx / tip_len, tip_ty / tip_len
        else:
            tip_dx, tip_dy = sign * cos45, -cos45
        tip_nx, tip_ny = _normal(1.0, outer=True)
        for i in range(1, tips_n + 1):
            t = i / tips_n
            a = math.pi * (1 - t)
            x = c_tip_x + cap_r * (math.cos(a) * tip_nx + math.sin(a) * tip_dx)
            y = c_tip_y + cap_r * (math.cos(a) * tip_ny + math.sin(a) * tip_dy)
            pts.append((x, y))
        for i in range(n, -1, -1):
            t = i / n
            ccx, ccy = _centerline(t)
            nx, ny = _normal(t, outer=False)
            w = _width(t)
            if t <= ramp_t:
                u = t / ramp_t
                uu = (1 - u) ** 2
                px = ex_top * uu + (ccx + nx * w) * (1 - uu)
                py = r_top * uu + (ccy + ny * w) * (1 - uu)
                pts.append((px, py))
            else:
                pts.append((ccx + nx * w, ccy + ny * w))
        if sign < 0:
            pts.reverse()
        return pts

    def _tentacle_horizontal(by, base_hw, reach, sign, thick=1.0):
        """10-degree upward flame tentacle: same sampling as _tentacle_flame_45
        but the initial angle is 10deg instead of 45deg."""
        edge = _right_edge if sign > 0 else _left_edge
        base_hw = base_hw * thick
        reach = reach * thick
        r_bot = by + base_hw
        r_top = by - base_hw
        ex_bot = edge(r_bot)
        ex_top = edge(r_top)
        mid_x = (ex_bot + ex_top) / 2.0
        cos10 = 0.984807753012208
        sin10 = 0.17364817766693033
        bend_x = 0.25
        bend_y = 0.40
        n = 24
        root_hw = base_hw * 0.70
        cap_r = base_hw * 0.18

        def _centerline(t):
            x = mid_x + sign * reach * (cos10 * t - bend_x * t * t)
            y = by - reach * (sin10 * t + bend_y * t * t)
            return x, y

        def _tangent(t):
            dx = sign * reach * (cos10 - 2 * bend_x * t)
            dy = -reach * (sin10 + 2 * bend_y * t)
            return dx, dy

        def _width(t):
            return root_hw * (1.0 - t ** 1.5) + cap_r

        def _normal(t, outer=True):
            tx, ty = _tangent(t)
            if outer:
                nx = -ty if sign > 0 else ty
                ny = tx if sign > 0 else -tx
            else:
                nx = ty if sign > 0 else -ty
                ny = -tx if sign > 0 else tx
            length = math.hypot(nx, ny)
            if length > 0:
                nx, ny = nx / length, ny / length
            return nx, ny

        pts = []
        ramp_t = 0.30
        for i in range(n + 1):
            t = i / n
            ccx, ccy = _centerline(t)
            nx, ny = _normal(t, outer=True)
            w = _width(t)
            if t <= ramp_t:
                u = t / ramp_t
                uu = (1 - u) ** 2
                px = ex_bot * uu + (ccx + nx * w) * (1 - uu)
                py = r_bot * uu + (ccy + ny * w) * (1 - uu)
                pts.append((px, py))
            else:
                pts.append((ccx + nx * w, ccy + ny * w))
        tips_n = n // 2
        c_tip_x, c_tip_y = _centerline(1.0)
        tip_tx, tip_ty = _tangent(1.0)
        tip_len = math.hypot(tip_tx, tip_ty)
        if tip_len > 0:
            tip_dx, tip_dy = tip_tx / tip_len, tip_ty / tip_len
        else:
            tip_dx, tip_dy = sign * cos10, -sin10
        tip_nx, tip_ny = _normal(1.0, outer=True)
        for i in range(1, tips_n + 1):
            t = i / tips_n
            a = math.pi * (1 - t)
            x = c_tip_x + cap_r * (math.cos(a) * tip_nx + math.sin(a) * tip_dx)
            y = c_tip_y + cap_r * (math.cos(a) * tip_ny + math.sin(a) * tip_dy)
            pts.append((x, y))
        for i in range(n, -1, -1):
            t = i / n
            ccx, ccy = _centerline(t)
            nx, ny = _normal(t, outer=False)
            w = _width(t)
            if t <= ramp_t:
                u = t / ramp_t
                uu = (1 - u) ** 2
                px = ex_top * uu + (ccx + nx * w) * (1 - uu)
                py = r_top * uu + (ccy + ny * w) * (1 - uu)
                pts.append((px, py))
            else:
                pts.append((ccx + nx * w, ccy + ny * w))
        if sign < 0:
            pts.reverse()
        return pts

    body_pts = []

    y_bot_rel, y_top_rel, reach = tent_v
    y_bot_arc = top + y_bot_rel
    y_top_arc = top + y_top_rel

    # 2) right body: top -> right shoulder -> tentacle1 -> tentacle2 -> body_bot
    #    (includes the vertical tentacle riding the head arc)
    y_a = top
    # 2a) head arc right half: top -> vertical tentacle top edge
    n_seg = max(3, int((y_top_arc - y_a) / (h / 18)))
    for i in range(n_seg + 1):
        t = i / n_seg
        y = y_a + (y_top_arc - y_a) * t
        body_pts.append((_right_edge(y), y))

    # 2b) vertical tentacle (right side)
    tent_pts = _tentacle_v(y_bot_rel, y_top_rel, reach, +1, V_TENT_THICK)
    body_pts.extend(tent_pts)

    # 2c) vertical tentacle bottom edge -> right shoulder
    y_a = y_bot_arc
    y_b = y_shoulder
    n_seg = max(3, int((y_b - y_a) / (h / 18)))
    for i in range(n_seg + 1):
        t = i / n_seg
        y = y_a + (y_b - y_a) * t
        body_pts.append((_right_edge(y), y))
    y_a = y_shoulder

    # 2d) right shoulder -> horizontal tentacle1 -> tentacle2 -> body_bot
    for idx in range(2):
        ty, base_hw, reach_h = tent_params[idx]
        by = top + h * ty
        y_b = by + base_hw
        n_seg = max(3, int((y_b - y_a) / (h / 18)))
        for i in range(n_seg + 1):
            t = i / n_seg
            y = y_a + (y_b - y_a) * t
            body_pts.append((_right_edge(y), y))
        if idx == 0:
            tent_pts = _tentacle_flame_45(by, base_hw, reach_h, +1)
        else:
            tent_pts = _tentacle_horizontal(by, base_hw, reach_h, +1)
        body_pts.extend(tent_pts)
        y_a = by - base_hw
    n_seg = max(3, int((body_bot - y_a) / (h / 18)))
    for i in range(n_seg + 1):
        t = i / n_seg
        y = y_a + (body_bot - y_a) * t
        body_pts.append((_right_edge(y), y))

    # 3) three feet (emitted into the body outline, widths aligned to body edge)
    foot_w = r / 3.0
    foot_h = h * 0.22
    foot_centers = [
        cx - r * 2 / 3,  # left
        cx,               # middle (shortest)
        cx + r * 2 / 3,  # right
    ]
    foot_heights = [1.0, 0.72, 1.0]
    n_foot = 16

    def _emit_foot(fcx, lh):
        lw = foot_w
        side_h = 0.45 * lh
        body_pts.append((fcx + lw, body_bot))
        body_pts.append((fcx + lw, body_bot + side_h))
        for i in range(n_foot + 1):
            a = math.pi * i / n_foot
            x = fcx + lw * math.cos(a)
            y = body_bot + side_h + (lh - side_h) * math.sin(a)
            body_pts.append((x, y))
        body_pts.append((fcx - lw, body_bot + side_h))
        body_pts.append((fcx - lw, body_bot))

    _emit_foot(foot_centers[2], foot_h * foot_heights[2])
    _emit_foot(foot_centers[1], foot_h * foot_heights[1])
    _emit_foot(foot_centers[0], foot_h * foot_heights[0])

    # 4) left body (counter-clockwise): body_bot -> tentacle2 -> tentacle1 ->
    #    left shoulder -> vertical tentacle bottom -> vertical tentacle -> top
    y_a = body_bot
    for idx in range(1, -1, -1):
        ty, base_hw, reach_h = tent_params[idx]
        by = top + h * ty
        y_b = by - base_hw
        n_seg = max(3, int((y_a - y_b) / (h / 18)))
        for i in range(n_seg + 1):
            t = i / n_seg
            y = y_a + (y_b - y_a) * t
            body_pts.append((_left_edge(y), y))
        if idx == 0:
            tent_pts = _tentacle_flame_45(by, base_hw, reach_h, -1)
        else:
            tent_pts = _tentacle_horizontal(by, base_hw, reach_h, -1)
        body_pts.extend(tent_pts)
        y_a = by + base_hw
    n_seg = max(3, int((y_a - y_shoulder) / (h / 18)))
    for i in range(n_seg + 1):
        t = i / n_seg
        y = y_a + (y_shoulder - y_a) * t
        body_pts.append((_left_edge(y), y))
    y_a = y_shoulder
    n_seg = max(3, int((y_a - y_bot_arc) / (h / 18)))
    for i in range(n_seg + 1):
        t = i / n_seg
        y = y_a + (y_bot_arc - y_a) * t
        body_pts.append((_left_edge(y), y))
    tent_pts = _tentacle_v(y_bot_rel, y_top_rel, reach, -1, V_TENT_THICK)
    body_pts.extend(tent_pts)
    y_a = y_top_arc
    n_seg = max(3, int((y_a - top) / (h / 18)))
    for i in range(n_seg + 1):
        t = i / n_seg
        y = y_a + (top - y_a) * t
        body_pts.append((_left_edge(y), y))

    return body_pts, []


def _fill_inside(img, fill_rgba):
    """Fill any fully-transparent pixels that are *inside* the drawn shape
    with the given colour (fixes self-intersecting polygon holes). Flood-fill
    the outside from each corner as 'background', then anything still alpha=0
    is interior -> recolour. Cheaper than a python per-pixel scan."""
    bg = (0, 0, 0, 0)
    # mark outside by flood-filling from the four corners
    w, h = img.size
    for corner in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        if img.getpixel(corner)[3] == 0:
            ImageDraw.floodfill(img, corner, (1, 1, 1, 1), thresh=0)
    # now: outside = (1,1,1,1), drawn = its colour, interior holes = (0,0,0,0)
    px = img.load()
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if p[3] == 0:
                px[x, y] = fill_rgba
            elif p == (1, 1, 1, 1):
                px[x, y] = bg
    return img


_tar_photo: Optional[ImageTk.PhotoImage] = None


def _tar_image():
    """Pre-render the tar soul: black->red vertical gradient body with two
    cat ears and four independent feet, red eyes. Shape from
    _tar_body_points (ported from the reference impl)."""
    global _tar_photo
    if _tar_photo is not None:
        return _tar_photo
    s = AA_SCALE
    w, h = GHOST_W, GHOST_H
    pad = 0.30          # ears + feet need more margin than the ghost
    pw, ph = int(w * (1 + pad * 2)), int(h * (1 + pad * 2))
    W, H = int(pw * s), int(ph * s)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    gw, gh = w * s, h * s

    body_pts, feet = _tar_body_points(cx, cy, gw, gh)
    # outline each shape (body + 4 feet) separately so feet keep transparent
    # gaps between them.
    all_shapes = [body_pts] + feet
    for shape in all_shapes:
        outer = [(cx + (x - cx) * 1.025, cy + (y - cy) * 1.025) for x, y in shape]
        d.polygon([v for p in outer for v in p], fill=GHOST_OUTLINE + (255,))

    # vertical black->red gradient, masked by the union of body + feet.
    # Build a 1px-wide gradient strip and resize it up (cheap, no per-pixel
    # putpixel over the full image).
    grad = Image.new("RGBA", (1, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(H):
        t = yy / H if H > 0 else 0
        r = int(GRIME_TOP[0] + (GRIME_BOT[0] - GRIME_TOP[0]) * t)
        g = int(GRIME_TOP[1] + (GRIME_BOT[1] - GRIME_TOP[1]) * t)
        b = int(GRIME_TOP[2] + (GRIME_BOT[2] - GRIME_TOP[2]) * t)
        gd.point((0, yy), fill=(r, g, b, 255))
    grad = grad.resize((W, H))
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for shape in all_shapes:
        md.polygon([v for p in shape for v in p], fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # red eyes (vertical ellipses)
    eye_w = gw * 0.06
    eye_h = gw * 0.12
    eye_y = cy - gh * 0.18
    for ex in (cx - gw * 0.16, cx + gw * 0.16):
        d.ellipse([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
                  fill=GRIME_EYE + (255,))

    # fill interior holes from self-intersecting tentacle/ear polygons with the
    # gradient's mid colour (not the bright bottom red) so the seams blend with
    # the surrounding gradient instead of showing as flat red streaks.
    mid = (int((GRIME_TOP[0] + GRIME_BOT[0]) / 2),
           int((GRIME_TOP[1] + GRIME_BOT[1]) / 2),
           int((GRIME_TOP[2] + GRIME_BOT[2]) / 2), 255)
    img = _fill_inside(img, mid)
    img = _supersample(img, s)
    _tar_photo = ImageTk.PhotoImage(img)
    return _tar_photo


_grime_photo: Optional[ImageTk.PhotoImage] = None


def _grime_image():
    """Pre-render the grime soul: rounded head + straight body with six flame
    tentacles and three short feet, black->red gradient, three red eyes.
    Shape from _grime_body_points (ported from the reference impl)."""
    global _grime_photo
    if _grime_photo is not None:
        return _grime_photo
    s = AA_SCALE
    w, h = TAR_W, TAR_H
    pad = 0.90          # the six flame tentacles stick far out -- wide margin
    pw, ph = int(w * (1 + pad * 2)), int(h * (1 + pad * 2))
    W, H = int(pw * s), int(ph * s)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    gw, gh = w * s, h * s

    body_pts, feet = _grime_body_points(cx, cy, gw, gh)
    all_shapes = [body_pts] + feet
    for shape in all_shapes:
        outer = [(cx + (x - cx) * 1.025, cy + (y - cy) * 1.025) for x, y in shape]
        d.polygon([v for p in outer for v in p], fill=GHOST_OUTLINE + (255,))

    # vertical black->red gradient masked by the body outline.
    grad = Image.new("RGBA", (1, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for yy in range(H):
        t = yy / H if H > 0 else 0
        r = int(GRIME_TOP[0] + (GRIME_BOT[0] - GRIME_TOP[0]) * t)
        g = int(GRIME_TOP[1] + (GRIME_BOT[1] - GRIME_TOP[1]) * t)
        b = int(GRIME_TOP[2] + (GRIME_BOT[2] - GRIME_TOP[2]) * t)
        gd.point((0, yy), fill=(r, g, b, 255))
    grad = grad.resize((W, H))
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    for shape in all_shapes:
        md.polygon([v for p in shape for v in p], fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # three red eyes in a tight triangle (one upper-center, two lower sides)
    eye_w = gw * 0.05
    eye_h = gw * 0.09
    d.ellipse([cx - eye_w, (cy - gh * 0.24) - eye_h,
               cx + eye_w, (cy - gh * 0.24) + eye_h], fill=GRIME_EYE + (255,))
    for ex in (cx - gw * 0.16, cx + gw * 0.16):
        d.ellipse([ex - eye_w, (cy - gh * 0.16) - eye_h,
                   ex + eye_w, (cy - gh * 0.16) + eye_h],
                  fill=GRIME_EYE + (255,))

    mid = (int((GRIME_TOP[0] + GRIME_BOT[0]) / 2),
           int((GRIME_TOP[1] + GRIME_BOT[1]) / 2),
           int((GRIME_TOP[2] + GRIME_BOT[2]) / 2), 255)
    img = _fill_inside(img, mid)
    img = _supersample(img, s)
    _grime_photo = ImageTk.PhotoImage(img)
    return _grime_photo


_teardrop_photo: Optional[ImageTk.PhotoImage] = None


def _teardrop_image():
    """The white soul sprite -- reuses the altar's soul.png (the same soul the
    player sees fly into the demon) so the minigame and the altar share one
    canonical look. Scaled down to ~38px tall. Cached at module level."""
    global _teardrop_photo
    if _teardrop_photo is not None:
        return _teardrop_photo
    soul_path = str(config.ROOT_DIR / "Altar" / "soul.png")
    try:
        im = Image.open(soul_path).convert("RGBA")
        w, h = im.size
        scale = TEARDROP_H / h
        im = im.resize((max(1, round(w * scale)), TEARDROP_H), Image.LANCZOS)
        _teardrop_photo = ImageTk.PhotoImage(im)
    except Exception:
        # Fallback: a simple white oval if the art file is missing.
        s = AA_SCALE
        W, H = int(56 * s), int(76 * s)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([W * 0.2, 0, W * 0.8, H * 0.7], fill=(255, 255, 255, 255))
        d.polygon([(W * 0.3, H * 0.6), (W * 0.5, H), (W * 0.7, H * 0.6)],
                  fill=(255, 255, 255, 255))
        img = _supersample(img, s)
        _teardrop_photo = ImageTk.PhotoImage(img)
    return _teardrop_photo


_bottle_photos = {}  # scale -> (PhotoImage, anchor_cx, anchor_cy)


def _bottle_image(scale=1.0):
    """Pre-render a green beer bottle tilted 45° (down-right). Faithful port
    of the reference impl's layered bottle: body + shoulder polygons + neck +
    crown cap with ridges + glass highlights + bottom reflection. Returns
    (PhotoImage, anchor_cx, anchor_cy)."""
    key = round(scale, 2)
    if key in _bottle_photos:
        return _bottle_photos[key]
    s = AA_SCALE * scale
    body_w = 16 * s
    body_h = 36 * s
    body_x = 0
    body_y = 38 * s
    shoulder_h = 8 * s
    neck_w = 8 * s
    neck_h = 12 * s
    neck_x = (body_w - neck_w) // 2
    neck_y = body_y - shoulder_h - neck_h
    cap_w = 9 * s
    cap_h = 7 * s
    cap_x = (body_w - cap_w) // 2
    cap_y = neck_y - cap_h
    pad = 10 * s
    img_w = int(body_w + pad * 2)
    img_h = int(body_y + body_h + pad * 2)
    ox = pad
    oy = pad
    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    def rx(x): return ox + x
    def ry(y): return oy + y
    BODY = (100, 130, 100, 200)
    BODY_DARK = (82, 110, 82, 215)
    NECK = BODY
    CAP = (80, 112, 90, 235)
    CAP_DARK = (46, 74, 56, 250)
    CAP_HIGHLIGHT = (185, 218, 192, 200)
    OUTLINE = (78, 110, 78, 255)
    HL = (230, 245, 230, 100)
    HL_BRIGHT = (250, 255, 250, 140)
    REFLECT = (200, 220, 200, 60)
    body_r = int(4 * s)
    outline_w = max(1, int(1.5 * s))
    # 1. body (rounded rect with outline)
    draw.rounded_rectangle(
        [rx(body_x), ry(body_y), rx(body_x + body_w), ry(body_y + body_h)],
        radius=body_r, fill=BODY, outline=OUTLINE, width=outline_w)
    # 2. neck + shoulders (seamless polygon joins, 1px overlap)
    poly_y = body_y + body_r
    neck_bottom_y = neck_y + neck_h
    draw.rectangle(
        [rx(neck_x - 1 * s), ry(neck_y), rx(neck_x + neck_w + 1 * s), ry(poly_y)],
        fill=NECK, outline=None)
    draw.polygon([(rx(0), ry(body_y)), (rx(neck_x + 1 * s), ry(neck_bottom_y)),
                  (rx(neck_x + 1 * s), ry(body_y))], fill=NECK, outline=None)
    draw.polygon([(rx(0), ry(poly_y)), (rx(0), ry(body_y)),
                  (rx(neck_x), ry(body_y)), (rx(neck_x), ry(poly_y))],
                 fill=NECK, outline=None)
    draw.polygon([(rx(body_w), ry(body_y)),
                  (rx(neck_x + neck_w - 1 * s), ry(neck_bottom_y)),
                  (rx(neck_x + neck_w - 1 * s), ry(body_y))],
                 fill=NECK, outline=None)
    draw.polygon([(rx(body_w), ry(poly_y)), (rx(body_w), ry(body_y)),
                  (rx(neck_x + neck_w), ry(body_y)),
                  (rx(neck_x + neck_w), ry(poly_y))],
                 fill=NECK, outline=None)
    # outline lines for shoulders/neck
    draw.line([(rx(0), ry(body_y)), (rx(neck_x), ry(neck_bottom_y)),
               (rx(neck_x), ry(neck_y))], fill=OUTLINE, width=outline_w)
    draw.line([(rx(body_w), ry(body_y)),
               (rx(neck_x + neck_w), ry(neck_bottom_y)),
               (rx(neck_x + neck_w), ry(neck_y))], fill=OUTLINE, width=outline_w)
    draw.line([(rx(neck_x), ry(neck_y)), (rx(neck_x + neck_w), ry(neck_y))],
              fill=OUTLINE, width=outline_w)
    # 3. crown cap
    cap_r = int(2 * s)
    draw.rounded_rectangle(
        [rx(cap_x), ry(cap_y), rx(cap_x + cap_w), ry(cap_y + cap_h)],
        radius=cap_r, fill=CAP, outline=CAP_DARK, width=2)
    draw.line([rx(cap_x + 1 * s), ry(cap_y + cap_h - 1 * s),
               rx(cap_x + cap_w - 1 * s), ry(cap_y + cap_h - 1 * s)],
              fill=(120, 150, 125, 200), width=max(1, int(1 * s)))
    draw.rectangle([rx(cap_x + cap_w * 0.18), ry(cap_y + 1 * s),
                    rx(cap_x + cap_w * 0.82), ry(cap_y + 2.2 * s)],
                   fill=CAP_HIGHLIGHT, outline=None)
    # 4. glass highlights (left side, neck + body)
    hl_w = int(2 * s)
    draw.rectangle([rx(neck_x + 2 * s), ry(neck_y + 2 * s),
                    rx(neck_x + 2 * s + hl_w), ry(neck_y + neck_h - 2 * s)],
                   fill=HL, outline=None)
    draw.rectangle([rx(body_x + 2 * s), ry(body_y + 2 * s),
                    rx(body_x + 2 * s + hl_w), ry(body_y + body_h - 4 * s)],
                   fill=HL, outline=None)
    draw.rectangle([rx(body_x + 1 * s), ry(body_y + 4 * s),
                    rx(body_x + 2 * s), ry(body_y + body_h - 6 * s)],
                   fill=HL_BRIGHT, outline=None)
    # 5. bottom arc reflection
    body_cx = body_x + body_w / 2
    body_cy = body_y + body_h
    arc_w = body_w * 0.55
    draw.arc([rx(body_cx - arc_w / 2), ry(body_cy - 8 * s),
              rx(body_cx + arc_w / 2), ry(body_cy)],
             start=0, end=180, fill=REFLECT, width=2)
    # 6. right-side inner shadow
    shadow_w = int(3 * s)
    draw.rectangle([rx(body_x + body_w - shadow_w - 1 * s), ry(body_y + 4 * s),
                    rx(body_x + body_w - 1 * s), ry(body_y + body_h - 4 * s)],
                   fill=BODY_DARK, outline=None)
    # 7. rotate 45° clockwise (NEAREST preserves hard alpha edges, then LANCZOS down)
    img = img.rotate(-45, resample=Image.NEAREST, expand=True)
    final_w = max(1, int(round(img.width / AA_SCALE)))
    final_h = max(1, int(round(img.height / AA_SCALE)))
    img = img.resize((final_w, final_h), Image.LANCZOS)
    photo = ImageTk.PhotoImage(img)
    _bottle_photos[key] = (photo, img.width // 2, img.height // 2)
    return _bottle_photos[key]


@dataclass
class Soul:
    kind: str
    cx: float
    cy: float
    vx: float
    vy: float
    body_id: int
    eyes: List[int] = field(default_factory=list)
    caught: bool = False


@dataclass
class Flower:
    cx: float
    cy: float
    stem_ids: List[int] = field(default_factory=list)
    petal_id: int = 0
    picked: bool = False


class SoulGame:
    """A fullscreen soul-catching minigame window."""

    def __init__(self, root, on_done=None, rng=None):
        self.root = root
        self.on_done = on_done        # on_done(caught, picked)
        self.rng = rng or random.Random()
        self.win = None
        self.canvas = None
        self.souls: List[Soul] = []
        self.flowers: List[Flower] = []
        self.mx = WIN_W / 2
        self.my = WIN_H / 2
        self.jar_x = self.mx
        self.jar_y = self.my
        self.jar_placed = False      # False = held (catches), True = down (picks)
        self.jar_id = None
        self.caught = 0
        self.picked = 0
        self.time_left = GAME_DURATION
        self.game_over = False
        self._timer_id = None
        self._loop_id = None
        self._shake_amp = 0.0
        self._shake_time = 0.0
        self._red_rect = None
        self._score_text = None
        self._timer_text = None

    # ---------- lifecycle ----------
    def start(self):
        self.win = tk.Toplevel(self.root)
        platform_utils.setup_window(self.win, config.TRANSPARENT_COLOR)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # opaque inner canvas sized to the game; window is fullscreen+transparent
        self.win.geometry(f"{sw}x{sh}+0+0")
        self.win.attributes("-topmost", True)
        # shake needs a frame so the canvas can shift inside the window
        self._frame = tk.Frame(self.win, bg=BG_COLOR, bd=0,
                               highlightthickness=0)
        self._frame.place(x=0, y=0, relwidth=1, relheight=1)
        # center the game canvas; leave SHAKE_AMPLITUDE margin so shifts don't
        # expose the desktop.
        self._ox = (sw - WIN_W) / 2
        self._oy = (sh - WIN_H) / 2
        self.canvas = tk.Canvas(self._frame, width=WIN_W, height=WIN_H,
                                bd=0, highlightthickness=0, bg=BG_COLOR)
        self.canvas.place(x=self._ox, y=self._oy)
        self._draw_field()
        self._spawn_souls()
        self._draw_jar()
        self._score_text = self.canvas.create_text(
            10, 10, anchor="nw", text="✨0 🌸0", fill="white",
            font=(config.UI_FONT, 12, "bold"))
        self._timer_text = self.canvas.create_text(
            WIN_W / 2, 14, anchor="n", text=f"{self.time_left}s",
            fill="white", font=(config.UI_FONT, 14, "bold"))
        # bindings (canvas-level, not bind_all)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_click)
        self.win.bind("<KeyPress-d>", self._toggle_jar)
        self.win.bind("<KeyPress-D>", self._toggle_jar)
        self.win.bind("<KeyPress-space>", self._toggle_jar)
        self.win.bind("<Escape>", self._close)
        self.win.focus_force()
        self._loop()
        self._tick_timer()

    def _draw_field(self):
        """Red flower clusters along the bottom; stems on canvas, petals as image
        (anchor="sw", stems attach at fy - FLOWER_CY_OFF)."""
        photo, anchor = _petals_image()
        for _ in range(FLOWER_COUNT):
            fx = self.rng.uniform(80, WIN_W - 80)
            fy = self.rng.uniform(WIN_H // 2, WIN_H - 40)
            stem_ids = []
            for dx, adj, slant in FLOWER_OFFSETS:
                bx = fx + FLOWER_CX + dx
                by = fy - FLOWER_CY_OFF
                tx = bx + slant
                ty = by - (FLOWER_STEM_LEN_BASE + adj)
                sid = self.canvas.create_line(bx, by, tx, ty, fill=STEM_COLOR,
                                              width=STEM_WIDTH)
                stem_ids.append(sid)
            # petals image bottom-left pinned at (fx, fy) -- sits above the stems
            pid = self.canvas.create_image(fx, fy, anchor="sw", image=photo)
            # cluster center = the middle stem's top (dx=0, adj=10)
            mid_cx = fx + FLOWER_CX
            mid_cy = (fy - FLOWER_CY_OFF) - (FLOWER_STEM_LEN_BASE + 10)
            self.flowers.append(Flower(cx=mid_cx, cy=mid_cy,
                                       stem_ids=stem_ids, petal_id=pid))

    def _spawn_souls(self):
        kinds = (["ashley", "andrew", "tar", "grime"]
                 + ["teardrop"] * (SOUL_COUNT - 4))
        self.rng.shuffle(kinds)
        for kind in kinds:
            cx = self.rng.uniform(60, WIN_W - 60)
            cy = self.rng.uniform(60, WIN_H - 200)
            ang = self.rng.uniform(0, 2 * math.pi)
            bid = self._create_soul_image(kind, cx, cy)
            self.souls.append(Soul(kind=kind, cx=cx, cy=cy,
                                   vx=math.cos(ang) * SOUL_SPEED,
                                   vy=math.sin(ang) * SOUL_SPEED,
                                   body_id=bid))

    def _create_soul_image(self, kind, cx, cy):
        if kind == "teardrop":
            photo = _teardrop_image()
            return self.canvas.create_image(cx, cy, image=photo)
        if kind in ("ashley", "andrew"):
            photo, _ = _ghost_image(kind, GHOST_W, GHOST_H)
            return self.canvas.create_image(cx, cy, image=photo)
        if kind == "grime":
            return self.canvas.create_image(cx, cy, image=_grime_image())
        if kind == "tar":
            return self.canvas.create_image(cx, cy, image=_tar_image())
        return 0

    def _draw_jar(self):
        photo, acx, acy = _bottle_image(1.0)
        self._jar_photo = photo
        self.jar_id = self.canvas.create_image(self.jar_x, self.jar_y, image=photo)
        self.canvas.tag_raise(self.jar_id)

    # ---------- main loop ----------
    def _loop(self):
        if self.game_over:
            return
        dt = 1.0 / 30
        for s in self.souls:
            if s.caught:
                continue
            self._update_soul(s, dt)
        self._update_shake(dt)
        self._update_jar()
        self._loop_id = self.win.after(33, self._loop)

    def _update_soul(self, s, dt):
        # drift: occasional random turn
        if self.rng.random() < 0.02:
            ang = self.rng.uniform(-0.5, 0.5)
            self._rotate_velocity(s, ang)
        # dodge if jar is close and this kind dodges
        mult = DODGE_MULT.get(s.kind)
        if mult is not None and not self.jar_placed:
            dx = s.cx - self.jar_x
            dy = s.cy - self.jar_y
            dist = math.hypot(dx, dy)
            if 0 < dist < ESCAPE_RADIUS:
                fear = 1.0 - dist / ESCAPE_RADIUS
                escape = SOUL_SPEED * (1.2 + fear * 3.0) * mult
                s.vx = (dx / dist) * escape
                s.vy = (dy / dist) * escape
            else:
                # coast back to drift speed
                spd = math.hypot(s.vx, s.vy)
                if spd > SOUL_SPEED * 1.05:
                    s.vx *= 0.95
                    s.vy *= 0.95
        s.cx += s.vx * dt
        s.cy += s.vy * dt
        # bounds bounce
        m = 30
        if s.cx < m: s.cx = m; s.vx = abs(s.vx)
        if s.cx > WIN_W - m: s.cx = WIN_W - m; s.vx = -abs(s.vx)
        if s.cy < m: s.cy = m; s.vy = abs(s.vy)
        if s.cy > WIN_H - m - 10: s.cy = WIN_H - m - 10; s.vy = -abs(s.vy)
        self.canvas.coords(s.body_id, s.cx, s.cy)

    @staticmethod
    def _rotate_velocity(s, ang):
        ca, sa = math.cos(ang), math.sin(ang)
        nvx = s.vx * ca - s.vy * sa
        nvy = s.vx * sa + s.vy * ca
        # renormalise to SOUL_SPEED (unless currently dodging faster)
        spd = math.hypot(nvx, nvy) or 1.0
        if spd < SOUL_SPEED * 1.05:
            nvx = nvx / spd * SOUL_SPEED
            nvy = nvy / spd * SOUL_SPEED
        s.vx, s.vy = nvx, nvy

    def _update_jar(self):
        if self.jar_placed:
            return
        # ease toward mouse
        self.jar_x += (self.mx - self.jar_x) * 0.4
        self.jar_y += (self.my - self.jar_y) * 0.4
        if self.jar_id:
            self.canvas.coords(self.jar_id, self.jar_x, self.jar_y)
            self.canvas.tag_raise(self.jar_id)

    # ---------- input ----------
    def _on_motion(self, e):
        # canvas coords (already relative to the placed canvas)
        self.mx = e.x
        self.my = e.y

    def _toggle_jar(self, e=None):
        # Toggle between held (catches souls) and placed (picks flowers).
        self.jar_placed = not self.jar_placed

    def _on_click(self, e):
        if self.game_over:
            return
        if self.jar_placed:
            self._try_pick_flower(e.x, e.y)
        else:
            self._try_catch(e.x, e.y)

    def _try_catch(self, x, y):
        # any pink/green inside the bottle radius -> shake (no catch)
        shook = False
        for s in self.souls:
            if s.caught or s.kind in ("tar", "grime", "teardrop"):
                continue
            if math.hypot(s.cx - x, s.cy - y) < BOTTLE_R:
                shook = True
        if shook:
            self._trigger_shake()
        # catch white teardrops inside the radius
        for s in self.souls:
            if s.caught or s.kind != "teardrop":
                continue
            if math.hypot(s.cx - x, s.cy - y) < BOTTLE_R:
                s.caught = True
                self.caught += 1
                self.canvas.delete(s.body_id)
                self._update_score()
                # no respawn: the field just gets emptier

    def _try_pick_flower(self, x, y):
        for f in self.flowers:
            if f.picked:
                continue
            if math.hypot(f.cx - x, f.cy - y) < PICK_RADIUS:
                f.picked = True
                self.picked += 1
                self.canvas.delete(f.petal_id)
                self._update_score()
                return

    def _update_score(self):
        if self._score_text:
            self.canvas.itemconfig(self._score_text,
                                   text=f"✨{self.caught} 🌸{self.picked}")

    # ---------- shake / red flash ----------
    def _trigger_shake(self):
        self._shake_amp = SHAKE_AMPLITUDE
        self._shake_time = 0.35
        if self._red_rect is None:
            self._red_rect = self.canvas.create_rectangle(
                0, 0, WIN_W, WIN_H, fill=RED_OVERLAY, stipple=RED_STIPPLE,
                outline="")
            self.canvas.tag_raise(self._red_rect)

    def _update_shake(self, dt):
        if self._shake_time > 0:
            self._shake_time -= dt
            if self._shake_time <= 0 and self._red_rect is not None:
                self.canvas.delete(self._red_rect)
                self._red_rect = None
        if self._shake_amp > 0.01:
            ox = self.rng.uniform(-self._shake_amp, self._shake_amp)
            oy = self.rng.uniform(-self._shake_amp, self._shake_amp)
            self.canvas.place_configure(x=self._ox + ox, y=self._oy + oy)
            self._shake_amp *= SHAKE_DECAY
        else:
            self.canvas.place_configure(x=self._ox, y=self._oy)
            self._shake_amp = 0.0

    # ---------- timer ----------
    def _tick_timer(self):
        if self.game_over:
            return
        self.time_left -= 1
        if self._timer_text:
            self.canvas.itemconfig(self._timer_text, text=f"{max(0,self.time_left)}s")
        if self.time_left <= 0:
            self._end_game()
        else:
            self._timer_id = self.win.after(1000, self._tick_timer)

    def _end_game(self):
        self.game_over = True
        if self._timer_text:
            self.canvas.itemconfig(self._timer_text, text="0s")
        # result overlay
        self.canvas.create_text(
            WIN_W / 2, WIN_H / 2,
            text=f"Caught {self.caught} soul(s)\nPicked {self.picked} flower(s)",
            fill="white", font=(config.UI_FONT, 18, "bold"), justify="center")
        # hand off after a short beat so the player sees the result
        self.win.after(1500, self._close)

    def _close(self, e=None):
        # Guard against double-close: _end_game schedules a delayed _close, but
        # the player may also press Esc first -- only fire on_done once.
        if self._loop_id is None and self._timer_id is None and self.win is None:
            return
        if self._loop_id is not None:
            try: self.win.after_cancel(self._loop_id)
            except Exception: pass
            self._loop_id = None
        if self._timer_id is not None:
            try: self.win.after_cancel(self._timer_id)
            except Exception: pass
            self._timer_id = None
        try:
            self.win.destroy()
        except Exception:
            pass
        self.win = None
        if self.on_done is not None:
            cb = self.on_done
            self.on_done = None
            try:
                cb(self.caught, self.picked)
            except Exception:
                pass
