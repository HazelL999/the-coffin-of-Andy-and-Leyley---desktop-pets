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

        Tuned as a slow upward integrator: closeness accumulates the bond,
        separation barely bleeds it, so the value creeps up over hours/days
        toward 100 (the red bond line) rather than plateauing mid-scale.
        The pets are only pressed together briefly each interaction (the real-
        time push-apart keeps them ~1 body length apart at rest, so very_near
        is a small slice of wall-clock time), so the raise rate has to outpace
        the drain from the much larger time spent wandering apart. Per-second
        rates (multiplied by dt):
          very_near: both +0.3   (pressed close → bond builds fast)
          close:     both -0.01  (apart → barely cools)
          far:       both -0.02  (apart → slow cool)
          very_far:  both -0.04  (abandoned → slow bleed)
        Net is slightly positive over a day given the interaction cadence,
        so the red line surfaces every few days. Discrete events (drag-onto
        +5, sacrifice -0.7, poke) layer on top.
        """
        rates = {
            "very_near": (+0.3, +0.3),
            "close":     (-0.01, -0.01),
            "far":       (-0.02, -0.02),
            "very_far":  (-0.04, -0.04),
        }
        da, ds = rates.get(distance_band, (0.0, 0.0))
        if da:
            self.adjust("andrew", da * dt)
        if ds:
            self.adjust("ashley", ds * dt)
