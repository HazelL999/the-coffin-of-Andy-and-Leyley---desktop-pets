"""Centralized tunable constants for the desktop pets.

Single source of truth — tweak behavior here, no logic. All times in seconds
unless the name says otherwise (ms).
"""

import sys
from pathlib import Path

# --- Cross-platform UI font (used by all Tk widgets across the app) ---
# "Segoe UI" is the native sans on Windows; macOS has none of that name (Tk
# silently falls back to a default that sizes differently), so use Helvetica
# there. Linux: DejaVu Sans is near-universal.
if sys.platform.startswith("win"):
    UI_FONT = "Segoe UI"
elif sys.platform == "darwin":
    UI_FONT = "Helvetica"
else:
    UI_FONT = "DejaVu Sans"

# Color-emoji font for the hover mental-state icon (each platform ships its own).
if sys.platform.startswith("win"):
    EMOJI_FONT = "Segoe UI Emoji"
elif sys.platform == "darwin":
    EMOJI_FONT = "Apple Color Emoji"
else:
    EMOJI_FONT = "Noto Color Emoji"

# --- Paths (resolved relative to the project root, i.e. this file's parent) ---
ROOT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ROOT_DIR / "assets"
DIALOGUE_PATH = ROOT_DIR / "data" / "dialogue.json"

# --- Characters ---
CHARACTERS = ["andrew", "ashley"]

# Character display metadata: label shown on placeholder + speech bubbles.
CHARACTER_META = {
    "andrew": {"display": "Andrew", "initial": "A", "color": (90, 130, 180)},
    "ashley": {"display": "Ashley", "initial": "L", "color": (170, 70, 90)},
}

# --- Transparency ---
# Windows uses this exact color for -transparentcolor. Magenta is chosen because
# it is unlikely to appear in character art. Documented in README: do not use
# pure magenta (#ff00ff) anywhere in sprite art.
TRANSPARENT_COLOR = "#ff00ff"
TRANSPARENT_RGB = (255, 0, 255)


def hex_to_rgb(hexc):
    """Parse a #rrggbb (or rrggbb) hex color string to an (r, g, b) tuple.
    Shared by asset_loader + backpack so the helper isn't duplicated."""
    h = hexc.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

# --- Timing ---
FPS = 30
FRAME_MS = 1000 // FPS          # ~33ms per render frame
ANIM_FRAME_DEFAULT_MS = 100     # fallback per-frame duration for PNG sequences
TRANSITION_DELAY_MS = 400        # -1 shows this long before switching to -2 on speak()

# --- Movement ---
WALK_SPEED_PX_S = 30           # pixels per second (slowed: less frantic wandering)
IDLE_PAUSE_RANGE = (2.0, 6.0)  # seconds the pet idles between wanders (longer = calmer)
SCREEN_MARGIN = 20              # keep pets this far from screen edges

# --- Scheduler ---
EVENT_INTERVAL_RANGE = (2.0, 6.0)   # seconds between random events per pet
EVENT_WEIGHTS = {
    "wander": 0.45,
    "expression": 0.20,
    "dialogue": 0.30,
    # "interaction" is not here on purpose: inter-pet scenes are driven by
    # InteractionDirector.maybe_trigger in PetApp._tick (its own timing via
    # INTERACTION_RANGE / INTERACTION_COOLDOWN), not by the per-pet scheduler.
}
DIALOGUE_COOLDOWN = 24.0       # min seconds between two lines from one pet (was 8.0)
INTERACTION_COOLDOWN = 60.0    # min seconds between interaction sequences
INTERACTION_RANGE = (90.0, 270.0)  # when to schedule the next interaction (was 30-90)
CHASE_EVADE_PX = 40            # how far Ashley sidesteps when Andrew chases her

# --- Distance emotion spectrum (Andy & Leyley: close=clingy/smothering,
# far=longing/hostile — matches the game's Burial/Decay duality) ---
# Bands are in multiples of PLACEHOLDER_SIZE (a "body length"). Thresholds are
# the upper bound of each band (dist <= T1 -> very_near, etc.).
DIST_BAND_SIZE = 128            # one body length unit (= PLACEHOLDER_SIZE)
DIST_VERY_NEAR = 1.5          # touching / smothering
DIST_CLOSE = 5.0              # comfortable together
DIST_FAR = 10.0               # longing / hostile (beyond this = very_far)
DISTANCE_BAND_COOLDOWN_SCALE = {  # multiply DIALOGUE_COOLDOWN by band
    "very_near": 0.5,         # close -> talk a lot
    "close": 1.0,
    "far": 1.3,
    "very_far": 1.8,          # far -> rarely speak (but occasional blowup)
}
DRAG_ONTO_DIST = 128 * 0.6      # overlap threshold for drag-onto-partner

# --- Codependency / sleep / click-reaction ---
SLEEP_IDLE_THRESHOLD = 15.0    # seconds idle (and pressed to Ashley) before Andy sleeps
SLEEP_DIST_BAND = "very_near"  # Andy only sleeps when this close to Ashley
CLICK_WINDOW_S = 3.0           # multi-click window for "Andrew poked N times"
CLICK_RAGE_THRESHOLD = 3       # clicks within window that angers Ashley
CLICK_DRAG_PX = 5              # move less than this = a click, not a drag
CODEP_CLICK_ASHLEY_DELTA = -8.0   # Ashley codependency drop when Andrew is poked
CODEP_CLICK_ANDREW_DELTA = 2.0    # Andrew nudged up (attention)
CODEP_DRAG_ONTO_DELTA = 10.0      # both rise when one is dragged onto the other
ANDY_SLEEP_MOOD = "content"    # mood shown while Andy sleeps (no dedicated art)

# --- Bond line (visualizes peak mutual codependency) ---
# The faint red line appears ONLY when BOTH pets' codependency is maxed at
# 100 — the fully-formed, mutual bond. It's a peak state, meant to be rare
# and earned (the two have to drift all the way to the top together), not a
# gradient you watch fill in. Faint by design: a thin, stippled, soft-red
# line so it reads as an ambient connection, not a bright cable.
BOND_THRESHOLD = 100.0

# --- Altar (sacrifice to the demon for prophecy) ---
ALTAR_SIZE = 200               # px — square altar window
ALTAR_STAR_RADIUS = 80         # outer radius of the pentagram

# --- Backpack & talisman ---
BACKPACK_DIR = str(ROOT_DIR / "backpack")
VISION_DIR = str(ROOT_DIR / "vision")
BACKPACK_ITEMS = [
    {"name": "Andy's doll", "path": str(ROOT_DIR / "backpack" / "Andy's rabbit doll.png"), "usable": False},
    {"name": "Leyley's doll", "path": str(ROOT_DIR / "backpack" / "Leyley's rabbit doll.png"), "usable": False},
    {"name": "Talisman", "path": str(ROOT_DIR / "backpack" / "Talisman.png"), "usable": True},
]

# --- Environment context (time/weather/todo) ---
# Pets react to the world outside: morning/evening + holiday greetings at first
# launch of the day, weather changes via Open-Meteo (no API key), and a local
# TODO file. Network/file failures degrade silently (never crash).
ENV_POLL_INTERVAL_S = 600    # how often poll() actually checks weather+todo
WEATHER_LAT = 39.9          # city latitude (default: Beijing). Change to relocate.
WEATHER_LON = 116.4         # city longitude
WEATHER_TIMEOUT_S = 6.0     # Open-Meteo HTTP timeout (sync request; polled rarely)
TODO_PATH = ROOT_DIR / "data" / "todo.txt"
ENV_STATE_PATH = ROOT_DIR / "data" / ".env_state.json"

# --- Daily rhythm events ---
# Late-night monologue: between these hours, the first poll after crossing into
# night triggers a one-off insomnia line (Andrew tired, Ashley possessive).
LATE_NIGHT_START = 23   # hour (inclusive) — 23:00 onwards is "late night"
LATE_NIGHT_END = 5      # hour (exclusive) — before 5:00 still counts
# Reunion greeting: if the app was closed longer than this, re-launch triggers
# a multi-beat reunion sequence instead of the normal time-period greeting.
REUNION_THRESHOLD_HOURS = 12

# --- AI chat (OpenRouter, optional enhancement) ---
# Right-click "AI chat…" lets the pet speak an AI-generated, in-character line.
# Requires the user's own OpenRouter API key (free :models have a daily cap).
# With no key / on failure, falls back to local random dialogue — the app runs
# identically with or without this configured. Pure stdlib (urllib), no deps.
AI_MODEL_DEFAULT = "google/gemma-4-26b-a4b-it:free"  # probed working 2026-07-13
# Tried in order on 429/rate-limit/404 (free models get throttled upstream, and
# a given :free variant can 404 if its provider route is broken even when the
# model is listed as "alive"). Order = models we've actually seen succeed first,
# then the rest as rotation. Note: free OpenRouter keys also hit a 402
# "spend limit exceeded" on some models once the key's free quota is tapped —
# those count as failures too and trigger the next fallback.
AI_MODEL_FALLBACKS = [
    "google/gemma-4-31b-it:free",      # alive but provider route sometimes 404s
    "openai/gpt-oss-120b:free",        # often 429 (shared pool throttled)
    "meta-llama/llama-3.3-70b-instruct:free",  # can 402 once key quota tapped
]
AI_TIMEOUT_S = 12.0          # LLM inference is slower than weather; give it room
AI_MAX_TOKENS = 80           # keep lines short (saves free-tier quota)
AI_CACHE_PATH = ROOT_DIR / "data" / ".ai_cache.json"

# --- AI chat UI images (the character-selection background + portraits) ---
# These live in the project's AICHAT/ folder. Users can swap them for their
# own art. The "original" image is the full-size scene background shown before
# a character is picked; the two "talk to <char>" images flash briefly on
# selection. All paths are joined with the OS separator (pathlib) so they work
# on macOS/Linux too — the old backslash-joins broke non-Windows.
AICHAT_DIR = ROOT_DIR / "AICHAT"
AICHAT_ORIGINAL = str(AICHAT_DIR / "original.png")
AICHAT_TALK_ANDREW = str(AICHAT_DIR / "talk to Andrew.png")
AICHAT_TALK_ASHLEY = str(AICHAT_DIR / "talk to Ashley.png")

# --- Speech bubble ---
BUBBLE_HOLD = 4.0             # seconds a bubble stays visible
BUBBLE_FADE = 0.3            # (reserved) fade duration — kept simple for now
BUBBLE_MAX_WIDTH = 220       # px — wrap text past this

# --- Sprite sizing ---
PLACEHOLDER_SIZE = 128        # px — placeholder + assumed sprite size for clamping

# --- Background music (pygame.mixer, cross-platform) ---
# Drop .mp3 / .ogg / .wav files into assets/music/ — the first found file
# is played on loop at startup. Right-click a pet → "🎵 Music on/off" toggles.
MUSIC_DIR = ASSETS_DIR / "music"
MUSIC_VOLUME = 0.25          # 0.0–1.0; low default so it's ambient, not intrusive
MUSIC_ENABLED = True          # start playing on launch (user can toggle off)
