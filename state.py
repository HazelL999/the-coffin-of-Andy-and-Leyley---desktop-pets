"""Codependency + mental state -- the core drivers for Andy & Leyley.

Each character has TWO independent 0..100 values:

1. **Codependency** (existing): how glued they are to each other. Drives
   proximity behavior, the red bond line, sleep posture. Starts at 50.

2. **Mental state** (new): each character's individual psychological
   stability, INDEPENDENT of codependency. Starts at 60. Drives the Realm's
   third-eye outcome (who kills whom when the road breaks). Has its own
   sources of change -- NOT tied to codependency deltas.

Mental state bands differ per character (they break differently):

  Andrew:   0-15 breaking | 15-50 frayed | 50-80 stable | 80-100 numb
  Ashley:   0-10 pleading | 10-40 furious | 40-80 stable | 80-100 negligent
"""

CLAMP_MIN = 0.0
CLAMP_MAX = 100.0

# --- Codependency bands ---
INDEPENDENT = 20.0   # Andy: below this = independent
DEPENDENT = 70.0     # Andy: above this = dependent
UNHINGED = 20.0      # Ashley: below this = unhinged
SERENE = 70.0        # Ashley: above this = serene

# --- Mental state bands (per character) ---
# Andrew
ANDREW_BREAKING = 15.0
ANDREW_FRAYED = 50.0
ANDREW_STABLE = 80.0
# Ashley
ASHLEY_PLEADING = 10.0
ASHLEY_FURIOUS = 40.0
ASHLEY_STABLE = 80.0


def _clamp(v):
    return max(CLAMP_MIN, min(CLAMP_MAX, v))


class CodependencyState:
    def __init__(self):
        self.values = {"andrew": 50.0, "ashley": 50.0}
        # Mental state (independent of codependency). Starts slightly below
        # the stable midline so there's room to grow or erode.
        self.mental = {"andrew": 60.0, "ashley": 60.0}

    # --- codependency ---
    def get(self, character):
        return self.values.get(character, 50.0)

    def adjust(self, character, delta):
        """Change a character's codependency by delta (clamped). Returns the
        new value. Positive = more codependent."""
        old = self.values.get(character, 50.0)
        new = _clamp(old + delta)
        self.values[character] = new
        return new

    def level(self, character):
        """Band label for the character's codependency."""
        v = self.get(character)
        if character == "andrew":
            if v < INDEPENDENT:
                return "independent"
            if v > DEPENDENT:
                return "dependent"
            return "passive"
        # ashley
        if v < UNHINGED:
            return "unhinged"
        if v > SERENE:
            return "serene"
        return "following"

    def codep_state(self, character):
        """Return (label, emoji) describing current codependency band.
        This is the codependency axis (not the independent mental_state axis)."""
        v = self.get(character)
        lvl = self.level(character)
        if character == "andrew":
            if lvl == "dependent":
                return ("clinging", "💗")
            if lvl == "independent":
                return ("withdrawing", "🚪")
            return ("stable", "❤")
        # ashley
        if lvl == "unhinged":
            return ("unhinged", "💔")
        if lvl == "serene":
            return ("serene", "😊")
        return ("stable", "❤")

    # --- mental state (independent axis) ---
    def get_mental(self, character):
        """Current mental state value 0..100."""
        return self.mental.get(character, 60.0)

    def adjust_mental(self, character, delta):
        """Change a character's mental state by delta (clamped 0..100).
        Independent of codependency. Returns the new value."""
        old = self.mental.get(character, 60.0)
        new = _clamp(old + delta)
        self.mental[character] = new
        return new

    def mental_label(self, character):
        """Band label for the character's mental state (per-character bands)."""
        v = self.get_mental(character)
        if character == "andrew":
            if v < ANDREW_BREAKING:
                return "breaking"
            if v < ANDREW_FRAYED:
                return "frayed"
            if v < ANDREW_STABLE:
                return "stable"
            return "numb"
        # ashley
        if v < ASHLEY_PLEADING:
            return "pleading"
        if v < ASHLEY_FURIOUS:
            return "furious"
        if v < ASHLEY_STABLE:
            return "stable"
        return "negligent"

    def mental_emoji(self, character):
        """Emoji for the mental state label."""
        label = self.mental_label(character)
        return {
            "breaking": "🔪", "frayed": "💔", "stable": "❤", "numb": "🧊",
            "pleading": "🔫", "furious": "💢", "negligent": "😏",
        }.get(label, "❤")

    def tick(self, dt, distance_band):
        """Apply proximity drift to both characters. Called every tick by
        PetApp with the current inter-pet distance band.

        Tuned (2026-08-01 mid-trim) so the red bond line surfaces ~once a
        day, not within a few hours. The prior round (+0.2/-0.05/-0.15/-0.3)
        plus the old discrete bonuses (+1 per scene, +5 per choice/drag)
        drove the value to 99.5 in hours. The pets spend most of their time
        at 'close' (kept ~one body-length apart by MIN_PARTNER_DISTANCE), so
        'close' is now neutral -- the bond only RISES when genuinely pressed
        together (very_near) and only COOLS when genuinely separated (far/
        very_far). That makes the rate depend on how much time they actually
        spend smothering vs. wandering apart, with the trimmed discrete
        bonuses (see config.CODEP_*) layered on top. Per-second rates (x dt):
          very_near: both +0.03  (pressed close -> bond builds, slowly)
          close:     both  0.0  (resting one body apart -> holds)
          far:       both -0.01 (wandering apart -> gentle cooling)
          very_far:  both -0.03 (well apart -> bleeds)
        With the trimmed discrete bonuses (choice +1.5 capped 2/day,
        scripted +0.15, drag-onto +2) the net is meant to reach 99.5 roughly
        once a day. This is sensitive to actual band occupancy (unknown until
        played); tune very_near up or far/very_far down if it's too rare/too
        frequent after a real session.
        """
        rates = {
            "very_near": (+0.03, +0.03),
            "close":     (0.0, 0.0),
            "far":       (-0.01, -0.01),
            "very_far":  (-0.03, -0.03),
        }
        da, ds = rates.get(distance_band, (0.0, 0.0))
        if da:
            self.adjust("andrew", da * dt)
        if ds:
            self.adjust("ashley", ds * dt)
