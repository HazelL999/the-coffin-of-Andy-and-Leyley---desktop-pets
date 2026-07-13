"""Environment context: pets react to the world outside themselves.

Three reactive layers, all failing silently so the app never crashes on a
missing file or unreachable network:

1. **Startup greeting** — at first launch of the day, pick a morning/evening
   line (or a fixed holiday line if today's MM-DD matches). "First launch of
   the day" is persisted across restarts via a tiny state file: the last
   greeted date is written after greeting, and a launch whose date differs
   greets again.
2. **Weather** — Open-Meteo (no API key) polled every ENV_POLL_INTERVAL_S.
   The WMO weather_code is bucketed into rain/overcast/clear. A line is
   spoken only when the *category* changes (steady rain doesn't repeat).
3. **TODO** — the local todo.txt (one open item per non-comment line) is
   read on the same poll cadence. A reminder sequence fires only when the
   open-item count *increases* (finishing items is celebrated with silence).

All speech goes through pet.speak(DialogueLine(...)) — the same entry point
the interaction director and altar use — so bubbles, moods, and freeze
behavior are inherited for free.
"""

import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

import config
from dialogue import DialogueLine


def _wmo_category(code):
    """Map an Open-Meteo WMO weather_code to a coarse bucket.

    Returns one of 'rain' / 'overcast' / 'clear', or None if unknown.
    Rain covers drizzle (51-57), rain (61-67), and rain showers (80-82).
    Overcast covers partly/foggy (2,3,45,48). Clear covers clear/mainly clear
    (0,1). Snow/thunder codes are ignored (no lines for them -> None).
    """
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (2, 3, 45, 48):
        return "overcast"
    if code in (0, 1):
        return "clear"
    return None


class EnvContext:
    """Owns the time/weather/todo reactivity. Held by PetApp; never crashes."""

    def __init__(self, root, pets, rng, dialogue_store, director=None):
        self.root = root
        self.pets = pets
        self.rng = rng or random
        self.store = dialogue_store
        self.director = director  # to avoid speaking over a running scene

        # Throttle: poll() returns early unless this many seconds elapsed.
        self._last_poll = 0.0
        # Weather state for change detection. None = not yet checked.
        self._last_weather_cat = None
        # TODO state. -1 = uninitialized: first read sets the baseline without
        # firing a "grew" reminder.
        self._last_todo_count = -1
        # Startup greeting state, persisted across restarts.
        self._greeted_today = False
        # Late-night state for change detection (fire once on entering night).
        self._is_late_night = False

    # ---------- helpers ----------

    def _pet(self, character):
        for p in self.pets:
            if p.character == character:
                return p
        return None

    def _any_active(self):
        """True if an interaction scene is mid-flight — don't collide with it."""
        d = self.director
        return bool(d and getattr(d, "active", False))

    def _speak_single(self, beat):
        """Make the beat's speaker say it (single bubble). Skip if busy."""
        if self._any_active():
            return
        speaker = self._pet(beat.character)
        if not speaker or not speaker.win:
            return
        line = DialogueLine(beat.character, beat.mood, beat.text)
        speaker.speak(line)

    def _play_sequence(self, beats):
        """Speak each beat in order (multi-beat holiday/todo sequences). Uses
        root.after so it survives independent of the director's scheduling."""
        if not beats:
            return
        if self._any_active():
            return  # don't interrupt a running scene

        def play(i=0):
            if i >= len(beats):
                return
            beat = beats[i]
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

    # ---------- startup greeting (time + holiday) ----------

    def startup_greeting(self):
        """Called once ~1.5s after launch. Priority: holiday > reunion
        (if app was closed > REUNION_THRESHOLD_HOURS) > morning/evening
        greeting. Only fires on the first launch of the day (persisted)."""
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if self._load_last_greet_date() == today:
                self._greeted_today = True
                return  # already greeted today (e.g. earlier launch)
            date_mmdd = now.strftime("%m-%d")
            holiday = self.store.greeting_for_holiday(date_mmdd)
            if holiday:
                self._play_sequence(holiday)
            elif self._check_reunion(now):
                seq = self.store.random_reunion(self.rng)
                if seq:
                    self._play_sequence(seq)
            else:
                period = "morning" if now.hour < 12 else (
                    "afternoon" if now.hour < 18 else "evening")
                beat = None
                if period in ("morning", "evening"):
                    beat = self.store.random_greeting(period, self.rng)
                if beat:
                    self._speak_single(beat)
            self._save_last_greet_date(today)
            self._greeted_today = True
        except Exception as exc:
            # Greeting is best-effort; never block the app on it.
            sys.stderr.write(f"[env] greeting failed: {exc}\n")

    def _check_reunion(self, now):
        """True if the app was closed longer than REUNION_THRESHOLD_HOURS.
        Reads last_active_timestamp from the state file. First-ever run
        (no timestamp) returns False."""
        try:
            with open(config.ENV_STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, OSError, ValueError):
            return False
        ts_str = data.get("last_active_timestamp")
        if not ts_str:
            return False
        try:
            last = datetime.fromisoformat(ts_str)
        except ValueError:
            return False
        hours = (now - last).total_seconds() / 3600
        return hours >= config.REUNION_THRESHOLD_HOURS

    # ---------- periodic poll (weather + todo) ----------

    def poll(self):
        """Called every tick by PetApp._tick. Throttled to
        ENV_POLL_INTERVAL_S; on each real check, refreshes weather + todo
        and fires lines on condition change."""
        now = time.monotonic()
        if now - self._last_poll < config.ENV_POLL_INTERVAL_S:
            return
        self._last_poll = now
        try:
            self._check_late_night()
        except Exception as exc:
            sys.stderr.write(f"[env] late-night check failed: {exc}\n")
        try:
            self._check_weather()
        except Exception as exc:
            sys.stderr.write(f"[env] weather check failed: {exc}\n")
        try:
            self._check_todo()
        except Exception as exc:
            sys.stderr.write(f"[env] todo check failed: {exc}\n")

    def _check_late_night(self):
        """Fire a one-off insomnia line when the app crosses into late night
        (23:00-5:00). Only triggers on the *transition* into night, not every
        poll — _is_late_night tracks whether we've already fired for this
        night session."""
        hour = datetime.now().hour
        is_night = hour >= config.LATE_NIGHT_START or hour < config.LATE_NIGHT_END
        if is_night and not self._is_late_night:
            self._is_late_night = True
            if not self._any_active():
                beat = self.store.random_greeting("late_night", self.rng)
                if beat:
                    self._speak_single(beat)
        elif not is_night:
            self._is_late_night = False  # reset so next night fires again

    def _check_weather(self):
        cat = self._fetch_weather_category()
        if cat is None:
            return  # network failed OR unmapped code — silent
        prev = self._last_weather_cat
        self._last_weather_cat = cat
        if cat == prev:
            return  # no change -> no line
        if prev is None:
            return  # baseline read — don't fire on the very first sighting
        # Category genuinely changed (e.g. clear -> rain). Say a line for it.
        beat = self.store.random_weather(cat, self.rng)
        if beat:
            self._speak_single(beat)

    def _fetch_weather_category(self):
        """GET Open-Meteo current weather_code; return its category or None.

        Coords come from user_settings (env vars > user_settings.json >
        config defaults), re-read each fetch so a mid-session city change
        takes effect on the next poll."""
        import user_settings
        lat, lon = user_settings.get_weather_coords()
        url = (f"https://api.open-meteo.com/v1/forecast"
               f"?latitude={lat}&longitude={lon}"
               f"&current=weather_code&timezone=auto")
        try:
            with urllib.request.urlopen(url,
                                        timeout=config.WEATHER_TIMEOUT_S) as r:
                data = json.load(r)
        except (urllib.error.URLError, OSError, ValueError):
            return None
        code = (data.get("current") or {}).get("weather_code")
        return _wmo_category(code)

    def _check_todo(self):
        count = self._count_open_todos()
        if count is None:
            return  # file missing/unreadable — silent
        prev = self._last_todo_count
        self._last_todo_count = count
        if prev < 0:
            return  # baseline read — don't fire on first sight
        if count > prev:
            seq = self.store.random_todo_reminder(self.rng)
            if seq:
                self._play_sequence(seq)

    @staticmethod
    def _count_open_todos():
        """Count non-comment, non-blank lines in todo.txt. None if unreadable."""
        try:
            with open(config.TODO_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (FileNotFoundError, OSError):
            return None
        n = 0
        for ln in lines:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            n += 1
        return n

    # ---------- state persistence ----------

    @staticmethod
    def _load_state():
        """Load the full state dict, or {} on any failure."""
        try:
            with open(config.ENV_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, OSError, ValueError):
            return {}

    @classmethod
    def _load_last_greet_date(cls):
        return cls._load_state().get("last_greet_date")

    @classmethod
    def _save_last_greet_date(cls, today):
        """Merge last_greet_date into the state file (preserves other keys
        like last_active_timestamp)."""
        data = cls._load_state()
        data["last_greet_date"] = today
        try:
            with open(config.ENV_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as exc:
            sys.stderr.write(f"[env] could not save state: {exc}\n")

    @classmethod
    def save_last_active_timestamp(cls):
        """Write the current time as last_active_timestamp. Called on app
        quit so the next launch can detect a long absence (reunion)."""
        data = cls._load_state()
        data["last_active_timestamp"] = datetime.now().isoformat()
        try:
            with open(config.ENV_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as exc:
            sys.stderr.write(f"[env] could not save active timestamp: {exc}\n")
