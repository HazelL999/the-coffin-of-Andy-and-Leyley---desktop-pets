"""User settings: city selection, persisted across restarts.

Layered with a clear precedence so the app works out-of-the-box AND lets
users override without editing code:

    environment variables  >  data/user_settings.json  >  config.py defaults

- Out of the box: no file, no env vars -> the config.py defaults apply
  (Beijing). Nothing to set up for a first-time `git clone && python run.py`.
- Power users: set PET_WEATHER_LAT / PET_WEATHER_LON env vars to override.
- Everyone else: the right-click "Set city" dialog writes lat/lon + the
  resolved city name here, so future launches just work.

The settings file is gitignored (it's per-user runtime state, not source).
Never raises: a missing/unreadable/empty file yields the defaults.
"""

import json
import os
import sys

import config

# Per-user settings file (gitignored). Lives next to dialogue.json.
_SETTINGS_PATH = config.ROOT_DIR / "data" / "user_settings.json"


def get_weather_coords():
    """Return (lat, lon) for the Open-Meteo query, honoring the precedence.

    Lat/lon may be ints or floats. Falls back to config defaults on any miss.
    """
    # 1. Environment variables (highest precedence).
    lat = _parse_coord(os.environ.get("PET_WEATHER_LAT"))
    lon = _parse_coord(os.environ.get("PET_WEATHER_LON"))
    if lat is not None and lon is not None:
        return lat, lon
    # 2. Per-user settings file.
    s = _load()
    lat = _parse_coord(s.get("lat"))
    lon = _parse_coord(s.get("lon"))
    if lat is not None and lon is not None:
        return lat, lon
    # 3. Config defaults.
    return config.WEATHER_LAT, config.WEATHER_LON


def get_city_name():
    """The human-readable city last chosen (for display), or None."""
    return _load().get("city")


def save_city(city_name, lat, lon):
    """Persist the chosen city + coords so future launches use them."""
    s = _load()
    s["city"] = city_name
    s["lat"] = lat
    s["lon"] = lon
    _save(s)


# ---------- AI chat (OpenRouter key + model) ----------
# Same precedence as the city: env var PET_AI_KEY > settings file > none.
# No key configured => AI chat is disabled (falls back to local dialogue).

def get_ai_key():
    """The OpenRouter API key, or None if unset. Env var wins over the file."""
    key = os.environ.get("PET_AI_KEY")
    if key:
        return key
    return _load().get("ai_key")


def save_ai_key(key):
    s = _load()
    s["ai_key"] = key or ""
    _save(s)


def get_ai_model():
    """The model id (default config.AI_MODEL_DEFAULT if unset)."""
    m = _load().get("ai_model")
    return m or config.AI_MODEL_DEFAULT


def save_ai_model(model):
    s = _load()
    s["ai_model"] = model or ""
    _save(s)


# ---------- internals ----------

def _load():
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _save(data):
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        sys.stderr.write(f"[settings] could not save: {exc}\n")


def _parse_coord(v):
    """Parse a lat/lon from env-var string or JSON number. None if invalid."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
