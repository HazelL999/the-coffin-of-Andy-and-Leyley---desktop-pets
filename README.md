# Andy & Leyley — Desktop Pets

Two desktop pets inspired by the indie game *The Coffin of Andy and Leyley*.
**Andrew (Andy)** and **Ashley (Leyley)** roam your screen, change expressions,
and speak in-character dialogue — and occasionally talk to each other.

> **Fan project, non-commercial.** The characters and setting belong to
> **Nemlei**, creator of *The Coffin of Andy and Leyley*. This is an unofficial
> tribute with no affiliation or endorsement implied. See the
> [License](#license) section — this project is **CC BY-NC-ND 4.0**: share it
> unmodified with credit, but no modified/derivative builds or commercial use.

Cross-platform: **macOS** and **Windows**. Pure Python + Tkinter, no build step.

---

## Quick start

Requires **Python 3.10+** (tested on 3.12). Tkinter ships with Python's
official installers; Pillow you may need to add.

```bash
pip install -r requirements.txt
python run.py
```

- **Windows**: works out of the box — true transparency + click-through, no
  extra deps.
- **macOS**: works out of the box for transparency and draggable pets. For the
  optional "click-through" toggle, also `pip install pyobjc-core` (without it,
  that one toggle is hidden — everything else still works).

> On Windows if `python` isn't on PATH, use the full path to your interpreter.

A small control panel appears (bottom-right). Two pets appear and start
wandering, changing expression, and talking.

### Quit
Any of:
- Click **Quit** in the control panel (works even if pets are in click-through mode).
- **Right-click a pet → Quit** (Windows: right-click; macOS: two-finger/Ctrl-click).
- Focus the control panel, press **Esc** / **Ctrl+Q** (macOS: **⌘Q**).

### Optional flags
```bash
python run.py --no-interaction   # disable pet-to-pet interaction sequences
```

---

## How it works

- Each pet is a borderless, always-on-top, **transparent** window that moves
  around the screen.
  - **Windows**: pure magenta pixels are made both invisible *and* click-through
    (`-transparentcolor`); opaque sprite pixels are draggable. Sprite edges are
    alpha-baked at load time so anti-aliased edges don't leave a magenta halo.
  - **macOS**: per-pixel alpha (`-transparent`); PyObjC fallback if unsupported.
- A per-pet scheduler fires weighted random events every few seconds:
  **wander** (move), **expression** (change mood), **dialogue** (speak a line),
  or **interaction** (walk to the other pet and talk).
- When a pet speaks a line, it sets the **mood** tagged on that line, so the
  expression shown always matches the dialogue.

---

## Adding your own art

Sprites live in `assets/<character>/<mood>/`, e.g. `assets/ashley/sinister/`.

- **Static**: one PNG (with transparency) in a mood folder.
- **Frame animation**: multiple PNGs, played in filename order
  (`01.png`, `02.png`, ...).
- **Animated GIF**: one `.gif`; per-frame duration is honored.
- PNGs win if both PNGs and a GIF are present.
- Don't pre-mirror left-facing art — the app flips automatically.
- **Windows gotcha**: don't use pure magenta `#ff00ff` in your art (it's the
  transparent key color). Recommended size ~128×128px.

**No art yet? No problem** — colored placeholders are drawn automatically, so
the app runs immediately. Drop art in anytime; it's picked up on the next mood
change (e.g. right-click → "Say something").

Expressions: `neutral happy annoyed sad scared thinking angry sinister smug surprised`.

---

## Changing the dialogue

Edit [`data/dialogue.json`](data/dialogue.json). Each line tags a `character`
and a `mood`; the pet's expression automatically matches the line it speaks.

```json
{ "character": "ashley", "mood": "sinister", "text": "I'll always keep you close. Always." }
```

- `character` ∈ `andrew`, `ashley`
- `mood` ∈ the expression list above (unknown moods are skipped with a warning)
- optional `weight` (default 1.0) makes a line rarer

The default lines are original placeholders written in the characters' voices.
Swap in verbatim game quotes any time — no code changes needed.

---

## Configuration

All tunables (speeds, event weights, cooldowns, colors, paths) live in
[`config.py`](config.py). Edit there to adjust behavior.

---

## Project layout

```
desktop-pets/
├── run.py              # entry point (argparse, launches PetApp)
├── config.py           # tunable constants
├── expressions.py      # mood vocabulary
├── platform_utils.py   # cross-platform transparency / screen / click-through
├── asset_loader.py     # PNG/GIF loading, alpha-bake, facing flip, placeholders
├── dialogue.py         # dialogue JSON loading + weighted pick
├── scheduler.py        # per-pet weighted-random event timer
├── pet.py              # one pet: state machine, movement, animation, bubble, menu
├── main.py             # PetApp: root, both pets, control panel, interaction dir
├── data/dialogue.json  # editable dialogue
└── assets/<character>/<mood>/   # your sprites go here
```

---

## Notes & limitations

- Pets roam the **primary monitor** by default. On Windows, the full virtual
  desktop (all monitors) is used when the OS reports it.
- Always-on-top isn't absolute — a fullscreen app or another topmost window can
  cover them.
- The default dialogue is placeholder text in the characters' style, not
  verbatim game quotes. Replace via `data/dialogue.json`.

---

## License

This project's original source code, configuration, dialogue text, and
documentation are licensed under **Creative Commons
Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)**.

[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-nd/4.0/)

**You may:**
- ✅ Read, study, and run this project privately
- ✅ Share the **unmodified** repository, with credit, non-commercially
- ✅ Reference the code for learning
- ✅ Report bugs or suggest fixes via issues (incorporation is at the author's discretion)

**You may not:**
- ❌ Redistribute modified or re-skinned versions of this project
- ❌ Rebrand it as a different mod or ship alternate characterizations/pairings
- ❌ Use this project or any derivative for commercial purposes

The **ND (NoDerivatives)** term is a deliberate choice: this project reflects
the author's preferred vision of the characters and their relationship, and is
not intended as a base for community mods that alter that vision.

**What this license does NOT cover:**
- **Characters & IP** — Andrew, Ashley, and the setting are the creation of
  **Nemlei** (*The Coffin of Andy and Leyley*). All character/trademark rights
  belong to their respective owners. This is an unofficial, non-commercial fan
  project with no affiliation or endorsement implied.
- **Art assets** — Sprites, portraits, altar/vision imagery, and music are
  **not included** in this repository and are not licensed here. Each asset
  retains its creator's rights; users supply their own (see *Adding your own
  art* above).

See [`LICENSE`](LICENSE) for the full legal text and a project-specific
notice. Where this summary and the full text differ, the CC BY-NC-ND 4.0 legal
text governs.
