"""Companion mode: the two pets sit quietly in the screen's bottom-right
corner, gently float, and watch what the user is doing -- speaking a line
when the frontmost app's *category* changes (coding, browsing, video...).

Two halves:

1. ``foreground_app_name()`` -- read the OS frontmost app/window name.
   Windows: ctypes GetForegroundWindow + GetWindowTextW. macOS: PyObjC
   NSWorkspace.frontmostApplication().localizedName(). All failures degrade
   silently to None (locked screen, no permission, no pyobjc) -- never crash,
   matching the env_context "silent on failure" pattern.

2. ``CompanionObserver`` -- throttled poll that reads the frontmost app,
   buckets it via ``_categorize``, and speaks a category-matched line only
   on a change (steady browsing doesn't repeat). Skips if a scene/dialogue is
   mid-flight (reuses the director.active guard).
"""

import sys
import time

import config


# --- frontmost app detection (cross-platform, silent on failure) ---

def foreground_app_name():
    """Return the frontmost app/window name, or None if it can't be read.

    Windows: the foreground window's title (often "<doc> - <app>"). macOS:
    the frontmost application's localized name. Both are case-folded to lower
    for keyword matching. Returns None on any error so the observer treats
    it as "idle/unknown" rather than crashing."""
    try:
        if sys.platform.startswith("win"):
            return _foreground_win()
        if sys.platform == "darwin":
            return _foreground_mac()
    except Exception:
        return None
    return None


def _foreground_win():
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    buf = ctypes.create_unicode_buffer(512)
    n = user32.GetWindowTextW(hwnd, buf, 512)
    if not n:
        return None
    return buf.value.lower().strip() or None


def _foreground_mac():
    """Frontmost app name on macOS. Tries NSWorkspace.frontmostApplication
    first; falls back to scanning runningApplications for the first regular
    (GUI) app if frontmostApplication returns None (it can, e.g. right after
    focus changes). No-op (returns None) if PyObjC isn't available."""
    try:
        import AppKit
    except Exception:
        return None
    try:
        ws = AppKit.NSWorkspace.sharedWorkspace()
        app = ws.frontmostApplication()
        if app is not None:
            name = app.localizedName()
            if name:
                return str(name).lower().strip() or None
        # Fallback: first regular-activation-policy running app. The list is
        # ordered by recency on recent macOS, so the head is usually the
        # frontmost GUI app even when frontmostApplication() returns nil.
        NSRegular = 0  # NSApplicationActivationPolicyRegular
        for a in ws.runningApplications() or []:
            try:
                if a.activationPolicy() == NSRegular:
                    name = a.localizedName()
                    if name:
                        return str(name).lower().strip() or None
            except Exception:
                continue
    except Exception:
        return None
    return None


# --- categorization ---

# Keyword -> category. Order matters: checked in order, first hit wins, so
# put specific terms (e.g. 'steam' gaming) before generic ('edge' browsing).
# Lowercased; the frontmost name is also lowercased before matching.
_CATEGORY_KEYWORDS = [
    ("coding", ["code", "vscode", "visual studio", "pycharm", "idea",
                "sublime", "neovim", "vim", "neovide", "terminal",
                "powershell", "cmd", "git", "devenv", "xcode", "cursor",
                "python", "idle", "jupyter", "spyder", "thonny"]),
    ("gaming", ["steam", "epic games", "battle.net", "riot", "minecraft",
               "genshin", "league of legends", "dota", "overwatch",
               "skyrim", "gog", "ubisoft", "ea desktop", "origin"]),
    ("video", ["bilibili", "youtube", "netflix", "twitch", "iqiyi",
              "youku", "qq video", "potplayer",
              "vlc", "mpv"]),
    ("music", ["spotify", "foobar", "aimp", "netease", "qqmusic",
               "itunes", "music"]),
    ("chat", ["wechat", "qq", "telegram", "discord", "slack",
              "teams"]),
    ("writing", ["word", "wps", "notion", "obsidian", "typora", "onenote",
                 "pages", "memo", "notes"]),
    ("browsing", ["chrome", "firefox", "edge", "safari", "opera", "brave",
                  "browser", "msedge"]),
]


def _categorize(name):
    """Map a frontmost-app name to a category, or 'idle' if none match / the
    name is None / empty. Categories drive which companion line is picked."""
    if not name:
        return "idle"
    for cat, kws in _CATEGORY_KEYWORDS:
        for kw in kws:
            if kw in name:
                return cat
    return "idle"  # unknown app -- treat as generic idle/other


# --- observer ---

class CompanionObserver:
    """Throttled poll: read the frontmost app, and speak a line when its
    category changes. Held by PetApp; only polled while companion mode is on.

    Reuses the director's ``active`` flag to avoid speaking over a running
    scene (same guard env_context uses). Lines come from the dialogue store's
    companion pool (see dialogue.random_companion)."""

    def __init__(self, root, pets, rng, store, director=None):
        self.root = root
        self.pets = pets
        self.rng = rng
        self.store = store
        self.director = director
        self._last_poll = 0.0
        # Last category seen -- first poll sets the baseline without speaking
        # (so turning companion mode on doesn't immediately narrate whatever
        # was already open).
        self._last_cat = None
        self._first = True

    def _any_active(self):
        d = self.director
        return bool(d and getattr(d, "active", False))

    def _pet(self, character):
        for p in self.pets:
            if p.character == character:
                return p
        return None

    def poll(self):
        """Called every tick by PetApp while companion mode is on. Throttled
        to COMPANION_POLL_INTERVAL_S."""
        now = time.monotonic()
        if now - self._last_poll < config.COMPANION_POLL_INTERVAL_S:
            return
        self._last_poll = now
        if self._any_active():
            return  # a scene/exchange is mid-flight -- don't talk over it
        name = foreground_app_name()
        cat = _categorize(name)
        if self._first:
            # Baseline: don't fire on the very first read after enabling.
            self._first = False
            self._last_cat = cat
            return
        if cat == self._last_cat:
            return  # same category as last poll -- no line (no spam)
        self._last_cat = cat
        self._speak(cat)

    def _speak(self, cat):
        """Pick a companion sequence for the category and play its beats."""
        if not self.store:
            return
        from dialogue import DialogueLine
        beats = self.store.random_companion(cat, self.rng)
        if not beats:
            return  # no lines configured for this category -- silent
        # Mirror env_context._play_sequence: root.after chain, independent of
        # the director's scheduling, skips if a scene starts mid-sequence.
        seq = list(beats)

        def play(i=0):
            if i >= len(seq) or self._any_active():
                return
            beat = seq[i]
            speaker = self._pet(beat.character)
            if speaker and speaker.win:
                line = DialogueLine(beat.character, beat.mood, beat.text)
                speaker.speak(line)
                n = len(beat.text) if isinstance(beat.text, list) else 1
                gap_ms = int(n * config.BUBBLE_HOLD * 1000) + 400
            else:
                gap_ms = 300
            self.root.after(gap_ms, lambda: play(i + 1))

        play(0)
