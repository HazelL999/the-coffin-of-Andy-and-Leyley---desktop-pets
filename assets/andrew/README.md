# Andrew "Andy" Graves — sprite assets

Andrew has 40 expression moods, one folder each under `assets/andrew/`.
Drop sprite art in and the app picks it up automatically — no restart
needed, just trigger that mood (e.g. right-click → "Say something").

## How art is laid out
- **Static (single frame)**: one PNG in a mood folder → shown as-is.
  Most of Andrew's moods are single-frame.
- **Transition (-1/-2)**: a mood with two keyframes, `01.png` (-1) and
  `02.png` (-2). On `speak()` the pet shows -1, then ~400 ms later switches
  once to -2 and **holds** there (no looping). Which moods are transitions is
  declared in `expressions.TRANSITION_MOODS`. Current pairs:
  `neutral`, `inlove`, `shy`, `explaining`.
- **Looping animation** (legacy/other characters): multiple PNGs in a folder
  that is NOT a transition mood play in filename order, looping.

## Adding a new -1/-2 pair
1. Put `01.png` and `02.png` in `assets/andrew/<mood>/`.
2. Add `"<mood>"` to `TRANSITION_MOODS` in `expressions.py`.
That's it — `speak()` will now play the -1 → -2 transition for that mood.

## Art rules
- Recommended size ~128×128px; keep consistent across this character. The
  placement script (`_place_andrew.py`) scales the long edge to 128 and
  pads the short side with transparency, centered.
- On Windows, do **not** use pure magenta `#ff00ff` anywhere in the art
  (it is the transparent color and would become see-through).
- Do **not** pre-mirror left-facing art — the app flips automatically.
- Empty/missing folder → a colored placeholder is drawn instead.

## Andrew's 40 moods
`neutral`(+), `cute`, `indifferent`, `disdain`, `demanding`, `speechless`,
`stop`, `sinister`, `mad`, `unhappy`, `snort`, `content`, `scared`, `blue`,
`furious`, `whatever`, `inlove`(+), `come_on`, `give_up`, `concealing`,
`awkward`, `explaining`(+), `ingratiate`, `nervous`, `scolding`, `fake_calm`,
`proud`, `fuck`, `snigger`, `anxious`, `worried`, `happy`, `pissed_off`,
`you_know_me_well`, `shy`(+), `desperate`, `frown`, `evil_grin`, `rapture`,
`thinking`.

(+) = transition mood (-1/-2 pair).
