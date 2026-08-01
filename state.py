"""Codependency state — the core driver for Andy & Leyley's behavior.

Each character has a codependency value 0..100 (starts at 50, "passive/
following"). It moves with interaction: closeness raises it, distance
changes it oppositely (Andy grows needier, Ashley spirals), clicking
Andrew angers Ashley, dragging one onto the other bonds them.

The value drives:
- Andy: <20 independent (pulls away), 20-70 passive, >70 dependent (seeks
  Ashley out — and can only sleep pressed against her).
- Ashley: <20 unhinged (meltdown moods), 20-70 following, >70 serene
  (quiet smile).

`mental_state` derives a short label + emoji icon for the Check-state UI.
"""

CLAMP_MIN = 0.0
CLAMP_MAX = 100.0

# Level thresholds (upper bound of each band).
INDEPENDENT = 20.0   # Andy: below this = independent
DEPENDENT = 70.0     # Andy: above this = dependent
UNHINGED = 20.0      # Ashley: below this = unhinged
SERENE = 70.0        # Ashley: above this = serene


def _clamp(v):
    return max(CLAMP_MIN, min(CLAMP_MAX, v))


class CodependencyState:
    def __init__(self):
        self.values = {"andrew": 50.0, "ashley": 50.0}
        # recent delta direction, for mental_state nuance
        self._drift = {"andrew": 0.0, "ashley": 0.0}

    def get(self, character):
        return self.values.get(character, 50.0)

    def adjust(self, character, delta):
        """Change a character's codependency by delta (clamped). Returns the
        new value. Positive = more codependent."""
        old = self.values.get(character, 50.0)
        new = _clamp(old + delta)
        self.values[character] = new
        self._drift[character] = new - old
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

    def mental_state(self, character):
        """Return (label, emoji) describing current mental state, derived
        from codependency level + recent drift."""
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

    def tick(self, dt, distance_band):
        """Apply proximity drift to both characters. Called every tick by
        PetApp with the current inter-pet distance band.

        Tuned (2026-08-01 mid-trim) so the red bond line surfaces ~once a
        day, not within a few hours. The prior round (+0.2/-0.05/-0.15/-0.3)
        plus the old discrete bonuses (+1 per scene, +5 per choice/drag)
        drove the value to 99.5 in hours. The pets spend most of their time
        at 'close' (kept ~one body-length apart by MIN_PARTNER_DISTANCE), so
        'close' is now neutral — the bond only RISES when genuinely pressed
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
