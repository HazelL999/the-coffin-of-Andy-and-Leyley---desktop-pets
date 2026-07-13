"""Per-pet weighted-random event scheduler. Pure logic, no Tk.

Each pet has a scheduler. Every random interval (EVENT_INTERVAL_RANGE) it rolls
a weighted event: wander / expression / dialogue / interaction. The Pet reacts
to the returned event name. Animation frame advance is separate (in Pet.update).
"""

import random
import time

import config


class PetScheduler:
    def __init__(self, rng: random.Random = None):
        self.rng = rng or random
        self._timer = self._next_interval()
        self._last_event = time.monotonic()

    def _next_interval(self):
        lo, hi = config.EVENT_INTERVAL_RANGE
        return self.rng.uniform(lo, hi)

    def tick(self, dt: float):
        """Advance the countdown by dt seconds. Returns an event name or None."""
        self._timer -= dt
        if self._timer > 0:
            return None
        self._timer = self._next_interval()
        return self._roll_event()

    def _roll_event(self):
        weights = config.EVENT_WEIGHTS
        events = list(weights.keys())
        ws = list(weights.values())
        return self.rng.choices(events, weights=ws, k=1)[0]

    def reset(self):
        self._timer = self._next_interval()
