"""AI chat: generate in-character lines via OpenRouter's free models.

Optional enhancement — the app runs identically with or without this. The
user supplies their own OpenRouter API key (free :models carry a daily cap);
with no key, on network failure, or on rate-limit, callers fall back to
local dialogue and the user notices nothing broken.

Design:
- Personas are baked in (提炼自 dialogue.json), so users on GitHub need no setup.
- A local JSON cache keys on (character, prompt) so repeated triggers don't
  burn the daily free quota. Delete data/.ai_cache.json to clear it.
- Pure stdlib urllib (no requests/openai SDK), matching the weather/geocoding
  pattern. Same silent-degrade try/except.
"""

import json
import sys
import urllib.error
import urllib.request

import config
import expressions
import user_settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Personas distilled from the existing dialogue.json corpus. Andy = exhausted,
# passive, co-dependent resentment; short clipped lines with ellipses. Ashley =
# possessive, manipulative, honey-edged menace; calls him Andy, chuckle/sinister.
# Both instructed to stay in-character, terse, never break the fourth wall.
# Each reply must be prefixed `mood|line` so the caller can swap the sprite's
# expression to match the line's emotion (mood validated against MOODS below).
_PERSONA_SYSTEM = {
    "andrew": (
        "You are Andrew Graves from The Coffin of Andy and Leyley. "
        "You are exhausted, passive, and co-dependently bound to your sister Ashley. "
        "You resent her but can't leave her. Your speech is terse, flat, laced with "
        "tired resignation and quiet bitterness; you often trail off with '...'. "
        "Examples of your voice: '...Another day.' / 'You don't love me. Not one bit.' "
        "/ 'I've been yours my whole life...' / 'Leave me alone.' "
        "Rules: reply with 1-2 short sentences only. Stay in character. Never say "
        "you are an AI or explain yourself. No stage directions, no quotes around "
        "the line. PREFIX your reply with one mood keyword from this list, then a "
        "pipe '|', then the line. Pick the mood that best fits the line's emotion. "
        "Mood list: neutral, unhappy, indifferent, worried, sad, scared, angry, "
        "mad, furious, shy, content, thinking."
    ),
    "ashley": (
        "You are Ashley Graves from The Coffin of Andy and Leyley. "
        "You are possessive, manipulative, and dangerously devoted to your brother "
        "Andy. You are honey-sweet on the surface, menacing underneath. You call him "
        "Andy. You are chuckle, confident, and treat his dependence as proof of love. "
        "Examples of your voice: 'Andrew, you need me.' / 'Stay up with me a little "
        "longer, Andy.' / 'You came back. ...You always come back.' / 'I'm never "
        "letting you go. You know that.' "
        "Rules: reply with 1-2 short sentences only. Stay in character. Never say "
        "you are an AI or explain yourself. No stage directions, no quotes around "
        "the line. PREFIX your reply with one mood keyword from this list, then a "
        "pipe '|', then the line. Pick the mood that best fits the line's emotion. "
        "Mood list: neutral, chuckle, sinister, sad, angry, mad, furious, shouting, "
        "crying, happy, content, worried."
    ),
}

# Default mood when the model omits or gives an invalid mood keyword.
_DEFAULT_MOOD = {"andrew": "neutral", "ashley": "chuckle"}


def is_configured():
    """True if an OpenRouter key is set (env or settings file)."""
    return bool(user_settings.get_ai_key())


def build_messages(character, user_msg=None):
    """Assemble OpenRouter chat messages: system=persona, user=trigger or input."""
    persona = _PERSONA_SYSTEM.get(character, _PERSONA_SYSTEM["andrew"])
    if user_msg and user_msg.strip():
        # Make it unambiguous who is speaking and who is being addressed: the
        # USER (a player, NOT the other sibling) is talking to this character,
        # and this character replies to the user. Without this, Ashley's persona
        # (which revolves around Andy) can misread the user as Andy, and the
        # pair-confusion bug (asking Andy, getting Ashley) is worse.
        content = (f"A player (NOT your sibling) says to you: {user_msg.strip()}\n"
                   f"Reply to the player in character. If you reference your "
                   f"sibling, use their name — do not mistake the player for them.")
    else:
        # No input: just say something on your mind right now.
        content = "Say one line that's on your mind right now, in character."
    return [
        {"role": "system", "content": persona},
        {"role": "user", "content": content},
    ]


def fetch_ai_line(character, user_msg=None):
    """Return an in-character AI line for `character`, or (None, None, False)
    on any failure (no key, network error, rate limit, parse error). The
    caller falls back to local dialogue. Caches hits to spare the daily quota.

    Returns (line, mood, cached) where:
      - line: the spoken text (no mood prefix)
      - mood: a validated mood from expressions.MOODS, or the character's
        default (neutral/chuckle) if the model omitted/garbled the tag
      - cached: True if it came from the cache
    On any error returns (None, None, False).
    """
    if not is_configured():
        return None, None, False

    user_msg = (user_msg or "").strip()
    cache_key = f"{character}::{user_msg}"  # "" for idle triggers

    # 1. Cache hit — don't burn quota on a repeat prompt.
    cached = _cache_get(cache_key)
    if cached is not None:
        mood, line = _split_mood_line(cached, character)
        return line, mood, True

    # 2. Call OpenRouter, trying the configured model then fallbacks on failure
    #    (free models get rate-limited upstream and rotate — never rely on one).
    key = user_settings.get_ai_key()
    messages = build_messages(character, user_msg)
    models_to_try = [user_settings.get_ai_model()]
    for m in config.AI_MODEL_FALLBACKS:
        if m not in models_to_try:
            models_to_try.append(m)

    line, mood = None, None
    for model in models_to_try:
        data = _call_openrouter(key, model, messages)
        if data is None:
            continue  # network/parse/429 on this model -> try next
        mood, line = _extract_line(data, character)
        if line:
            break
    if not line:
        return None, None, False

    _cache_put(cache_key, f"{mood}|{line}")
    return line, mood, False


def _split_mood_line(stored, character):
    """Re-split a cached 'mood|line' string. Falls back to the character's
    default mood if the stored value is malformed."""
    if "|" in stored:
        mood, line = stored.split("|", 1)
        mood = mood.strip().lower()
        if mood not in expressions.MOODS:
            mood = _DEFAULT_MOOD.get(character, "neutral")
    else:
        mood, line = _DEFAULT_MOOD.get(character, "neutral"), stored
    return mood, line.strip()


def _call_openrouter(key, model, messages):
    """POST one OpenRouter chat completion. Returns parsed JSON dict or None
    on any failure (network error, rate-limit 429, parse error). None signals
    the caller to try the next fallback model."""
    body = json.dumps({
        "model": model,
        "max_tokens": config.AI_MAX_TOKENS,
        "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            # OpenRouter recommends these for attribution on the free tier.
            "HTTP-Referer": "https://github.com/andy-leyley-desktop-pet",
            "X-Title": "Andy & Leyley Desktop Pet",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.AI_TIMEOUT_S) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # 429 = this free model is rate-limited upstream; log and try fallback.
        if e.code == 429:
            sys.stderr.write(f"[ai] {model} rate-limited; trying next model\n")
        else:
            sys.stderr.write(f"[ai] {model} HTTP {e.code}\n")
        return None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        sys.stderr.write(f"[ai] {model} failed: {exc}\n")
        return None


def _extract_line(data, character):
    """Pull choices[0].message.content out of an OpenRouter response, parse the
    `mood|line` prefix, strip surrounding quotes/whitespace, clamp length.

    Returns (mood, line) where mood is a validated MOODS entry or the
    character's default (neutral/chuckle). Returns (None, None) if malformed —
    the caller tries the next fallback model."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None, None
    if not isinstance(content, str):
        return None, None
    raw = content.strip().strip('"').strip("'").strip()
    # Take the first non-empty line (bubbles are single-line).
    line = raw
    for part in raw.splitlines():
        part = part.strip()
        if part:
            line = part
            break
    if not line:
        return None, None
    # Parse the mood|line prefix the model was instructed to emit.
    mood = _DEFAULT_MOOD.get(character, "neutral")
    if "|" in line:
        cand, rest = line.split("|", 1)
        cand = cand.strip().lower()
        if cand in expressions.MOODS:
            mood = cand
            line = rest.strip().strip('"').strip("'").strip()
    # Hard clamp so a verbose model can't overflow the bubble.
    if len(line) > 200:
        line = line[:197] + "..."
    if not line:
        return None, None
    return mood, line


# ---------- cache ----------

def _cache_load():
    try:
        with open(config.AI_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _cache_get(key):
    return _cache_load().get(key)


def _cache_put(key, value):
    data = _cache_load()
    data[key] = value
    try:
        with open(config.AI_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        sys.stderr.write(f"[ai] could not write cache: {exc}\n")
