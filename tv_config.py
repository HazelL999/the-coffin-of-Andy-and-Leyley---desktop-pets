"""TV configuration — dimensions, colors, display constants.

Style: cheap grey plastic CRT, The Coffin of Andy and Leyley —
not woodgrain, not retro-fancy. Cheap 2000s apartment television.
"""

# ══════════════════════════════════════════════════════
# DIMENSIONS
# ══════════════════════════════════════════════════════

BODY_W = 520                     # total width
BODY_H = 350                     # upper body (screen + bezel area)
PANEL_H = 65                     # control panel below screen
STAND_H = 30                     # base/stand
TOTAL_H = BODY_H + PANEL_H + STAND_H  # 445

# Bezel — outer margin from body edge
BEZ_MARGIN = 10

# Inner bezel steps (each step goes one layer deeper)
BEZ_STEPS = (
    ("outer",  5, "#2e2e36"),
    ("mid",    4, "#24242c"),
    ("inner",  4, "#1a1a20"),
    ("frame",  3, "#0e0e12"),
)

# Knobs
KNOB_R = 12                      # radius

# Panel layout (fraction of body width)
PANEL_PWR_X = 0.09               # power button
PANEL_VOL_X = 0.28               # volume knob
PANEL_CH_X  = 0.44               # channel knob
PANEL_DISP  = 0.78               # channel display
PANEL_ADLED = 0.92               # AD indicator LED

# ══════════════════════════════════════════════════════
# COLORS — cheap grey plastic palette
# ══════════════════════════════════════════════════════

# Body shell
BODY   = "#3a3a42"   # gunmetal grey — visible against dark desktop
BODY_T = "#464650"   # top edge highlight
BODY_S = "#2a2a32"   # side shadow
BODY_B = "#1c1c22"   # bottom edge shadow

# Bezel (outer → inner)
BEZ1 = "#2e2e36"
BEZ2 = "#24242c"
BEZ3 = "#1a1a20"
BEZ4 = "#0e0e12"

# Bevel edge colors (for 3D chamfer effect)
BV_HI = "#50505c"    # top/left face catch light
BV_SH = "#121216"    # bottom/right face in shadow

# Screen background
SCR_BG = "#030306"

# CRT glass reflections
GLR_TOP  = "#a8a8b8"   # arc glare
GLR_LINE = "#d0d0e0"   # diagonal reflection line
GLR_BOT  = "#000002"   # deep shadow at screen bottom
GLR_WARM = "#d4c8b0"   # faint warm CRT glow center

# Control panel
PAN_BG  = "#282830"
PAN_GRV = "#12121a"    # divider groove
PAN_HI  = "#363640"    # surface highlight
PAN_SEAM= "#202028"    # seam line

# Knobs
KN_C    = "#363640"    # knob body
KN_OUT  = "#1c1c26"    # outer ring shadow
KN_IN   = "#262632"    # inner ring
KN_HI   = "#464652"    # top-left highlight
KN_PTR  = "#9a9aaa"    # pointer line

# Power button
PW_C    = "#282834"
PW_HI   = "#3c3c48"

# LEDs
LED_G     = "#30b020"
LED_G_DIM = "#061805"
LED_R     = "#dd2828"
LED_R_DIM = "#180606"

# Text
TX_DIM   = "#585866"
TX_BRIGHT = "#8a8a9a"
TX_GREEN  = "#26b018"
TX_RED    = "#dd2828"

# Digital display
DP_BG   = "#020208"
DP_BRD  = "#161622"

# Stand
ST_C   = "#222228"
ST_S   = "#14141c"
ST_B   = "#0c0c12"
FOOT_C = "#08080c"

# ══════════════════════════════════════════════════════
# STATIC / SNOW
# ══════════════════════════════════════════════════════

ST_MS   = 50         # refresh interval (ms)
ST_PX   = 3          # pixel size
ST_DENS = 0.28       # fill density

# ══════════════════════════════════════════════════════
# AD BREAK
# ══════════════════════════════════════════════════════

AD_DMIN   = 8000
AD_DMAX   = 25000
AD_DURMIN = 3000
AD_DURMAX = 6500

# ══════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════

def total_bez():
    """Total horizontal bezel thickness (left + right)."""
    return BEZ_MARGIN + sum(w for _, w, _ in BEZ_STEPS)
