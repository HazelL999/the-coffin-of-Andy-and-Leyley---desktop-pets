# Ashley "Leyley" Graves — sprite assets

Ashley has 39 expression moods (27 unique + 12 shared with Andrew). One
folder each under `assets/ashley/`. Drop sprite art in and the app picks it
up automatically — no restart needed, just trigger that mood (e.g.
right-click → "Say something").

Note: Ashley has no separate "evil grin" mood — her evil-grin sprite **is**
her `neutral` expression (mapped by `_place_ashley.py`), stored under
`assets/ashley/neutral/`. Andrew's `neutral` is a -1/-2 transition; Ashley's
is single-frame. They share the slug but have independent art/animations.

## How art is laid out
- **Static (single frame)**: one PNG in a mood folder → shown as-is.
  Most of Ashley's moods are single-frame.
- **Transition (-1/-2)**: a mood with two keyframes, `01.png` (-1) and
  `02.png` (-2). On `speak()` the pet shows -1, then ~400 ms later switches
  once to -2 and **holds** there (no looping). Which moods are transitions
  is declared in `expressions.TRANSITION_MOODS`. Ashley's pairs:
  `embarrased`, `happy`, `inlove` (`inlove` is shared with Andrew).
- **Looping animation** (legacy): multiple PNGs in a folder that is NOT a
  transition mood play in filename order, looping.

## Adding a new -1/-2 pair
1. Put `01.png` and `02.png` in `assets/ashley/<mood>/`.
2. Add `"<mood>"` to `TRANSITION_MOODS` in `expressions.py`.
That's it — `speak()` will now play the -1 → -2 transition for that mood.

## Art rules
- Recommended size ~128×128px; keep consistent across this character. The
  placement script (`_place_ashley.py`) scales the long edge to 128 and
  pads the short side with transparency, centered.
- On Windows, do **not** use pure magenta `#ff00ff` anywhere in the art
  (it is the transparent color and would become see-through).
- Do **not** pre-mirror left-facing art — the app flips automatically.
- Empty/missing folder → a colored placeholder is drawn instead. The app
  always runs, even with zero assets.

## Ashley's 39 moods
`admitting`, `angry`, `are_u_serious`, `confident`, `content`,
`crying`, `cute`, `doomed`, `embarrased`(+), `emm`, `emotionally_hurt`,
`endure`, `furious`, `giggles`, `happy`(+), `hmm`,
`indifferent`, `mad`, `madly_thinking`, `inlove`(+), `no_way`, `neutral`,
`pout`, `provoking`, `regreful`, `regrefully_thinking`, `sad`, `satisfied`,
`scolding`, `shouting`, `sigh`, `sinister`, `smug`, `snort`, `sorry`,
`speechless`, `surprised`, `unsatisfied`, `worried`.

(+) = transition mood (-1/-2 pair). `neutral` here is Ashley's evil-grin
sprite (single frame); `smug` is her chuckle sprite — both via filename
aliases in `_place_ashley.py`. Shared slugs with Andrew (each has its own
art): `neutral`/`inlove`/`happy`/`sinister`/`mad`/`worried`/`cute`/
`indifferent`/`content`/`furious`/`scolding`/`snort`. `annoyed` has no art
yet (placeholder drawn) but stays available because dialogue references it.
