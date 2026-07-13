"""Mood vocabulary, folder mapping, and per-character idle weights.

Each mood is also the name of the subfolder under assets/<character>/.
When a pet speaks a line, it sets the mood tagged on that line, so the
expression shown always matches the dialogue.

A mood may be "transition" (two keyframes -1/-2, placed as 01.png/02.png):
on speak() the pet shows frame 0 (-1) then switches once to frame 1 (-2)
and stays there (see TRANSITION_MOODS + Pet.speak). Non-transition moods
are single-frame; multi-PNG folders that are NOT transition moods still
play as looping animation (legacy behavior).
"""

# Canonical mood list. Andrew's 40 moods + Ashley's 28 unique moods (the two
# also share 12 moods: neutral/content/cute/furious/happy/indifferent/inlove/
# mad/scolding/sinister/snort/worried — each has its own art under
# assets/<character>/<mood>/. For Ashley, `neutral` is her "evil grin" sprite
# and `chuckle` is her "smug" sprite — both via filename aliases in
# _place_ashley.py). `annoyed` has no art yet but is kept because dialogue
# references it (placeholder is drawn).
MOODS = [
    # --- Andrew (40) ---
    "neutral", "cute", "indifferent", "disdain", "demanding", "speechless",
    "stop", "sinister", "mad", "unhappy", "snort", "content", "scared",
    "blue", "furious", "whatever", "inlove", "come_on", "give_up",
    "concealing", "awkward", "explaining", "ingratiate", "nervous",
    "scolding", "fake_calm", "proud", "fuck", "snigger", "anxious",
    "worried", "happy", "pissed_off", "you_know_me_well", "shy",
    "desperate", "frown", "evil_grin", "rapture", "thinking",
    # --- Ashley-only (28) ---
    "admitting", "angry", "are_u_serious", "confident", "crying",
    "doomed", "embarrased", "emm", "emotionally_hurt", "endure",
    "giggles", "hmm", "madly_thinking", "no_way",
    "pout", "provoking", "regreful", "regrefully_thinking", "sad",
    "satisfied", "shouting", "sigh", "chuckle", "sorry", "speechless",
    "surprised", "unsatisfied",
    # --- No art yet, but dialogue references them (placeholder drawn) ---
    "annoyed",
]

MOOD_FOLDER = {mood: mood for mood in MOODS}

# Moods that are a -1/-2 two-keyframe transition, played once on speak()
# (frame 0 -> frame 1, then hold). Their 01.png/02.png must exist paired.
# Add a pair here when you add new -1/-2 art for a mood.
TRANSITION_MOODS = {
    # Andrew
    "neutral", "inlove", "shy", "explaining",
    # Ashley
    "embarrased", "happy",
    # "inlove" is shared — both characters have a -1/-2 pair for it.
}

# Per-character idle expression weights, split by distance band. Andy & Leyley
# are codependent/toxic: very_near = clingy/smothering (or irritable from
# being too close); far = longing that curdles into hostility. Only moods the
# character has art for are listed (otherwise a placeholder would show).
# Bands: very_near / close / far / very_far (see config.DIST_*).
_IDLE_MOOD_WEIGHTS_BY_BAND = {
    "andrew": {
        "very_near": {  # smothering closeness
            "inlove": 3.0, "neutral": 2.0, "content": 2.0, "mad": 1.5,
            "unhappy": 1.0,  # the friction of being too close
        },
        "close": {  # comfortable default resting set
            "neutral": 4.0, "thinking": 2.0, "indifferent": 2.0,
            "content": 1.5, "unhappy": 1.0, "worried": 1.0,
        },
        "far": {  # anxious, probing
            "worried": 3.0, "thinking": 2.0, "anxious": 2.0,
            "unhappy": 1.5, "neutral": 1.0, "frown": 1.0,
        },
        "very_far": {  # longing curdling into resentment
            "unhappy": 3.0, "frown": 2.0, "desperate": 2.0,
            "worried": 1.5, "fake_calm": 1.0,  # feigning he's fine
        },
    },
    "ashley": {
        "very_near": {  # possessive bliss
            "neutral": 3.0,  # her evil grin
            "inlove": 2.5, "content": 2.0, "sinister": 1.5,
            "pout": 1.0,  # even pressed close, finds something to sulk about
        },
        "close": {  # comfortable default
            "neutral": 3.0, "indifferent": 2.0, "content": 2.0,
            "hmm": 2.0, "regreful": 1.5, "emm": 1.5, "speechless": 1.0,
            "sad": 1.0, "worried": 1.0,
        },
        "far": {  # testing/probing
            "provoking": 3.0, "hmm": 2.0, "worried": 2.0,
            "are_u_serious": 1.5, "regreful": 1.0, "pout": 1.0,
        },
        "very_far": {  # longing + hostility
            "sad": 3.0, "regreful": 2.0, "emotionally_hurt": 2.0,
            "crying": 1.5, "worried": 1.5, "sinister": 1.0,
        },
    },
}

# Fallback band if a character lacks a band's table entry.
_DEFAULT_BAND = "close"

# Extra idle-mood bias by codependency level (added on top of the band
# weights). Andy: dependent=clingy, independent=withdrawn. Ashley:
# unhinged=meltdown, serene=quiet bliss. Only moods with art are used.
_CODEP_MOOD_BIAS = {
    "andrew": {
        "dependent": {"inlove": 2.0, "neutral": 1.5},
        "independent": {"indifferent": 2.0, "whatever": 1.5},
        "passive": {},
    },
    "ashley": {
        "unhinged": {"furious": 2.0, "shouting": 1.5, "crying": 1.5},
        "serene": {"neutral": 2.0, "content": 1.5, "happy": 1.0},
        "following": {},
    },
}

# Weekend/weekday mood bias (layered on top of band + codep biases).
# Weekday = exhausted/restless, weekend = relaxed.
_WEEKEND_MOOD_BIAS = {
    "andrew": {
        True:  {"content": 2.0, "neutral": 1.5},           # weekend — relaxed
        False: {"unhappy": 2.0, "worried": 1.5, "indifferent": 1.5},  # weekday — tired
    },
    "ashley": {
        True:  {"neutral": 2.0, "happy": 1.5},            # weekend — content
        False: {"provoking": 2.0, "hmm": 1.5},            # weekday — restless
    },
}

# Codependency delta applied each time a pet's idle mood changes. Positive =
# more codependent, negative = more independent/unhinged. Small values because
# idle moods can change every few seconds. Moods not listed = 0 delta.
#
# NOTE: this is a flat dict keyed by mood, so shared moods (inlove/content/happy/
# neutral/sinister/scared/worried/furious/mad — both characters have art for them)
# get ONE value, listed once in the "Shared moods" block below. Do not also list
# them in the per-character blocks: a duplicate key would silently overwrite the
# earlier entry (Python keeps the last assignment), which is how `worried` once
# flipped sign -0.2 -> +0.3 by accident. If you need per-character deltas, the
# structure must become nested (e.g. {mood: {andrew: x, ashley: y}}).
MOOD_CODEP_DELTA = {
    # --- Andrew (moods unique to Andrew) ---
    "come_on":      0.0,
    "proud":      +0.5,
    "whatever":   -0.2,
    "desperate":  -1.0,
    "concealing": +0.1,
    "evil_grin":  +0.1,
    "shy":        +0.3,
    "cute":       +0.2,
    "rapture":    +0.8,
    "indifferent": -0.3,
    "unhappy":    -0.4,
    "anxious":    -0.3,
    "frown":      -0.3,
    "fake_calm":  -0.4,
    "give_up":    -0.5,
    "pissed_off": -0.5,
    "disdain":    -0.4,
    "nervous":    -0.2,
    "awkward":    -0.1,
    "thinking":  -0.1,
    "blue":       -0.3,
    # --- Ashley (moods unique to Ashley) ---
    "chuckle":    +0.4,
    "hmm":        +0.1,
    "pout":       -0.1,
    "regreful":   +0.2,
    "regrefully_thinking": +0.2,
    "sorry":      +0.2,
    "giggles":     +0.2,
    "satisfied":  +0.3,
    "confident":  +0.2,
    "provoking":  -0.2,
    "shouting":   -0.6,
    "crying":     -0.6,
    "sad":        -0.4,
    "emotionally_hurt": -0.7,
    "doomed":     -0.5,
    "unsatisfied": -0.3,
    "endure":     -0.2,
    "angry":      -0.4,
    "are_u_serious": -0.2,
    "no_way":     -0.3,
    # --- Shared moods (both characters have art; one delta each) ---
    "inlove":     +1.0,   # strong bond
    "content":    +0.4,
    "happy":      +0.3,
    "sinister":   +0.2,
    "neutral":     0.0,
    "scared":     +0.3,
    "worried":    +0.3,   # worry reads as clingy, not withdrawal
    "furious":    -0.8,   # meltdown
    "mad":        -0.5,
}


def weighted_idle_mood(character, band, rng, codep_level="passive", is_weekend=None):
    """Pick a mood for a random idle expression change for `character`,
    biased by the distance `band` (see config.DIST_*) AND the codependency
    level (state.level): high codependency pulls moods clingy/serene, low
    pulls withdrawn/unhinged. If `is_weekend` is given (True/False), layers
    a weekend/weekday mood bias on top (weekday = tired, weekend = relaxed).

    Only low-intensity moods appear so strong expressions stay reserved for
    dialogue triggers.
    """
    from datetime import datetime as _dt
    by_band = _IDLE_MOOD_WEIGHTS_BY_BAND.get(character) or \
        _IDLE_MOOD_WEIGHTS_BY_BAND["ashley"]
    weights = dict(by_band.get(band) or by_band[_DEFAULT_BAND])
    # Layer the codependency bias on top (moods not in the band table get
    # added; existing ones get boosted).
    bias = (_CODEP_MOOD_BIAS.get(character, {})
            .get(codep_level, {}))
    for m, w in bias.items():
        weights[m] = weights.get(m, 0.0) + w
    # Layer weekend/weekday bias (only moods the character has art for).
    if is_weekend is None:
        is_weekend = _dt.now().weekday() >= 5
    wk_bias = (_WEEKEND_MOOD_BIAS.get(character, {})
               .get(bool(is_weekend), {}))
    for m, w in wk_bias.items():
        weights[m] = weights.get(m, 0.0) + w
    moods = list(weights.keys())
    ws = list(weights.values())
    return rng.choices(moods, weights=ws, k=1)[0]
