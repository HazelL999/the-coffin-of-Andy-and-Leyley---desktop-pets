"""Group chat: a social-app-style IM window (like IG/WhatsApp) where the
player, Andrew, and Ashley all talk together. Pure message stream (no
sprites), dark bubbles, bottom input bar. The player sends one line and BOTH
pets reply (each its own AI conversation history, so they stay in character
and remember context). Closing the window drops all history -- no
persistence, starts fresh each session.

Reuses ai_chat.fetch_ai_line (already multi-turn via history=), ai_dialog's
_open_settings for the key/model config, and theme for the dark styling.
"""

import random
import threading
import tkinter as tk

import ai_chat
import ai_dialog  # for _open_settings (key/model config)
import config
import theme


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def open_group_chat(root, pets, director=None):
    """Build and show the group-chat IM window. `pets` is the PetApp's pet
    list (used to fetch each pet's dialogue store for local fallback + rng)."""
    win = tk.Toplevel(root)
    win.title("Group chat")
    win.geometry(f"{config.GROUP_CHAT_W}x{config.GROUP_CHAT_H}")
    win.attributes("-topmost", True)
    win.config(bg=theme.BG)

    # Per-character conversation history (for multi-turn AI). Reset on close.
    history = {"andrew": [], "ashley": []}
    pet_map = {p.character: p for p in pets}
    busy = {"on": False}

    # --- message stream: a scrollable Text widget (the IM pattern) ---
    # Text is the most reliable Tk widget for a scrolling message log with
    # colored text and word-wrap -- no Canvas+inner-Frame width-tracking bugs.
    msg = tk.Text(win, bd=0, highlightthickness=0, bg=theme.BG,
                 fg=theme.FG, font=(config.UI_FONT, 10),
                 wrap="word", spacing1=2, spacing2=4, spacing3=2,
                 padx=12, pady=10, state="disabled",  # read-only until we insert
                 cursor="arrow")
    scroll = tk.Scrollbar(win, orient="vertical", command=msg.yview,
                          bg=theme.BG, troughcolor=theme.BG,
                          activebackground=theme.BG_ELEVATED)
    msg.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    msg.pack(side="top", fill="both", expand=True)

    # Text tags for bubble-like styling: colored name prefix per character.
    for char in ("andrew", "ashley"):
        color = _rgb_to_hex(config.CHARACTER_META.get(char, {}).get("color", (200, 200, 200)))
        disp = config.CHARACTER_META.get(char, {}).get("display", char)
        msg.tag_configure(f"name_{char}", foreground=color,
                          font=(config.UI_FONT, 9, "bold"))
        msg.tag_configure(f"text_{char}", foreground=theme.FG,
                          font=(config.UI_FONT, 10))
    msg.tag_configure("player", foreground=theme.FG,
                      font=(config.UI_FONT, 10))
    msg.tag_configure("sys", foreground=theme.FG_DIM,
                      font=(config.UI_FONT, 8))
    msg.tag_configure("you_label", foreground=theme.ACCENT,
                      font=(config.UI_FONT, 9, "bold"))

    def _insert_text(text, tag=None):
        """Append a line to the message stream and scroll to the bottom."""
        msg.configure(state="normal")
        if msg.index("end-1c") != "1.0":
            msg.insert("end", "\n")
        msg.insert("end", text, tag)
        msg.see("end")
        msg.configure(state="disabled")

    def _add_message(text, who):
        """Add one message. Player messages are prefixed 'You:'. Pet messages
        are prefixed with their colored display name."""
        if who == "player":
            _insert_text("You: ", "you_label")
            _insert_text(text, "player")
        else:
            disp = config.CHARACTER_META.get(who, {}).get("display", who)
            _insert_text(f"{disp}: ", f"name_{who}")
            _insert_text(text, f"text_{who}")

    def _add_system(text):
        _insert_text(text, "sys")

    _add_system("You're in a group chat with Andrew and Ashley. "
                "Say anything -- they'll both reply.")

    # --- input bar (bottom) ---
    bar = tk.Frame(win, bg=theme.BG)
    bar.pack(fill="x", padx=10, pady=(4, 8))
    entry = tk.Entry(bar, font=(config.UI_FONT, 10),
                    bg=theme.BG_ELEVATED, fg=theme.FG,
                    insertbackground=theme.FG, relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=theme.BORDER)
    entry.pack(side="left", fill="x", expand=True)
    send_btn = theme.style_button(
        tk.Button(bar, text="Send", width=8, command=lambda: _send()))
    send_btn.pack(side="left", padx=(4, 2))
    theme.style_button(
        tk.Button(bar, text="⚙", width=2,
                  command=lambda: ai_dialog._open_settings(win, None))
    ).pack(side="left", padx=2)
    entry.bind("<Return>", lambda e: _send())
    entry.focus_set()

    def _send():
        if busy["on"]:
            return
        user_msg = entry.get().strip()
        if not user_msg:
            return
        entry.delete(0, tk.END)
        _add_message(user_msg, "player")
        if not ai_chat.is_configured():
            for char in ("andrew", "ashley"):
                pet = pet_map.get(char)
                if pet:
                    loc = pet.dialogue.random_line(char, rng=pet.rng)
                    if loc:
                        _add_message(loc.text, char)
            return
        busy["on"] = True
        send_btn.config(state="disabled")

        def worker():
            # Both pets reply to the same player line, sequentially (free
            # models throttle harder under concurrent calls). Each uses its
            # OWN conversation history.
            replies = []
            for char in ("andrew", "ashley"):
                line, mood, cached = ai_chat.fetch_ai_line(
                    char, user_msg, history=history[char])
                if line:
                    history[char].append({"role": "user", "content": user_msg})
                    history[char].append({"role": "assistant", "content": f"{mood}|{line}"})
                    replies.append((char, line))
                else:
                    pet = pet_map.get(char)
                    if pet:
                        loc = pet.dialogue.random_line(char, rng=pet.rng)
                        if loc:
                            replies.append((char, loc.text))

            def done():
                busy["on"] = False
                send_btn.config(state="normal")
                for char, line in replies:
                    _add_message(line, char)
                entry.focus_set()
            root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    win.protocol("WM_DELETE_WINDOW", win.destroy)
