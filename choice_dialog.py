"""Player-choice popup: a small Toplevel showing the speaker's sprite,
the question, and 2-3 option buttons. The user picks for the character,
and the chosen option's codep deltas + response line are applied by the
caller via the on_choice callback.

Mirrors city_dialog.py / ai_dialog.py's Toplevel pattern (topmost, dark bg).
Uses the shared theme (theme.py) for strict black bg + white text so macOS
Aqua's native button bevel can't wash it out.
"""

import tkinter as tk

import config
import theme

_SPRITE_SIZE = config.PLACEHOLDER_SIZE


def open_choice_dialog(root, character, mood, question, options, on_choice):
    """Build and show a choice popup.

    Args:
        root: the Tk root.
        character: which character is asking (for the sprite).
        mood: the speaker's current mood (for the sprite).
        question: the question text shown above the buttons.
        options: list of dicts, each with a "text" key (button label).
        on_choice: callback(index) called with the chosen option's index.
    """
    win = tk.Toplevel(root)
    win.title("...")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.config(bg=theme.BG)

    # Sprite at top.
    photo = theme.sprite_over_bg(character, mood)
    if photo:
        sprite_lbl = tk.Label(win, image=photo, bg=theme.BG, bd=0)
        sprite_lbl.image = photo  # keep ref
        sprite_lbl.pack(padx=20, pady=(12, 4))
    else:
        # Fallback: show the character's display name as text.
        disp = config.CHARACTER_META.get(character, {}).get("display", character)
        tk.Label(win, text=disp, font=(config.UI_FONT, 14, "bold"),
                 fg=theme.FG, bg=theme.BG).pack(pady=(16, 4))

    # Question text.
    tk.Label(win, text=question, font=(config.UI_FONT, 11),
             fg=theme.FG, bg=theme.BG, wraplength=320, justify="center",
             height=3).pack(padx=20, pady=(4, 8))

    # Option buttons.
    def pick(idx):
        win.destroy()
        on_choice(idx)

    for i, opt in enumerate(options):
        theme.style_button(
            tk.Button(win, text=opt["text"], width=28,
                      font=(config.UI_FONT, 10),
                      command=lambda i=i: pick(i),
                      padx=12, pady=6)
        ).pack(padx=20, pady=3)

    win.protocol("WM_DELETE_WINDOW", lambda: pick(0))  # closing = first option
