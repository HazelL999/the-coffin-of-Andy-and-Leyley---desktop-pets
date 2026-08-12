"""AI chat dialog: character-selection image UI + chat.

Two canvas modes in one window:
  - Scene mode (initial): shows original.png with a "Talk to Andrew/Ashley"
    button under each portrait.
  - Sprite mode (after selecting): the scene image disappears, the character's
    sprite (neutral) is shown centered, and AI replies render as a rounded
    speech bubble *below* the sprite -- full vertical room, no clipping. The
    sprite swaps to the mood matching each reply.

Art is user-supplied (config.AICHAT_DIR + assets/<character>/<mood>/).
"""

import threading
import tkinter as tk

import ai_chat
import config
import theme
import user_settings
from PIL import Image, ImageTk

_SPRITE_SIZE = config.PLACEHOLDER_SIZE  # 128 -- matches the desktop pet sprite


class _ImageCache:
    """Loads + caches PIL images and their PhotoImage wrappers."""

    def __init__(self, pet):
        self._pet = pet
        self._pil = {}
        self._photo = {}
        self._sprite = {}  # (character, mood) -> PhotoImage composited over _BG

    def pil(self, path):
        if path not in self._pil:
            self._pil[path] = Image.open(path).convert("RGBA")
        return self._pil[path]

    def photo(self, path, size):
        key = (path, size)
        if key not in self._photo:
            im = self.pil(path).resize(size, Image.LANCZOS)
            self._photo[key] = ImageTk.PhotoImage(im)
        return self._photo[key]

    def sprite(self, character, mood):
        """A sprite PhotoImage for (character, mood), alpha-composited over the
        dialog's dark background (NOT magenta-baked -- this is a normal opaque
        window, so we composite to the real bg color per the project rule).

        If the character has no art folder for this mood, falls back to the
        character's default mood (neutral/chuckle) so we never show a placeholder.
        Cached by (character, mood)."""
        key = (character, mood)
        if key in self._sprite:
            return self._sprite[key]
        # Delegate the load+composite to the shared theme helper, then cache.
        photo = theme.sprite_over_bg(character, mood)
        if photo is not None:
            self._sprite[key] = photo
        return photo


def open_ai_dialog(root, pet, director=None):
    """Build and show the AI-chat image dialog for `pet` (a Pet instance)."""
    win = tk.Toplevel(root)
    win.title("AI chat")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.config(bg=theme.BG)

    cache = _ImageCache(pet)
    busy = {"on": False}
    selected = {"char": None}   # None = scene mode; else sprite view for char
    # Running conversation history for multi-turn chat. Each entry is a
    # {"role": "user"/"assistant", "content": str} OpenRouter message. The
    # assistant content keeps the `mood|line` prefix so the persona stays
    # consistent across turns. Reset when the user switches character or
    # relaunches the dialog. Capped in ai_chat.build_messages.
    conversation = []

    # Window sizing: canvas on top, then buttons, then chat input bar.
    img_w = 600
    img_h = int(img_w * cache.pil(config.AICHAT_ORIGINAL).size[1]
                / cache.pil(config.AICHAT_ORIGINAL).size[0])
    btn_h = 36
    input_h = 56
    total_h = img_h + btn_h + input_h + 16
    win.geometry(f"{img_w + 20}x{total_h}")
    scene_size = (img_w, img_h)

    # Sprite geometry inside the canvas: centered horizontally, upper third
    # vertically; the bottom 2/3 is reserved for the reply bubble.
    sprite_cx = img_w // 2
    sprite_cy = img_h // 3

    # --- canvas (top): scene image OR sprite+bubble share this surface ---
    canvas = tk.Canvas(win, width=img_w, height=img_h, bd=0,
                       highlightthickness=0, bg=theme.BG)
    canvas.pack(padx=10, pady=(8, 4))
    # One scene-image item (shown in scene mode, hidden in sprite mode) + one
    # sprite-image item (shown in sprite mode). Bubble items are created/cleared
    # per reply and tracked in _bubble_items.
    canvas.image_id = canvas.create_image(0, 0, anchor="nw")
    canvas.sprite_id = canvas.create_image(sprite_cx, sprite_cy, anchor="center")
    canvas.itemconfig(canvas.sprite_id, state="hidden")
    _bubble_items = []
    _sprite_photo = {"id": None}  # keep PhotoImage ref alive

    def _show_scene_mode():
        canvas.itemconfig(canvas.image_id, state="normal")
        canvas.itemconfig(canvas.sprite_id, state="hidden")
        _hide_bubble()

    def _show_sprite_mode(character, mood="neutral"):
        canvas.itemconfig(canvas.image_id, state="hidden")
        photo = _sprite_photo_for(character, mood)
        canvas.itemconfig(canvas.sprite_id, image=photo)
        canvas.itemconfig(canvas.sprite_id, state="normal")
        _sprite_photo["id"] = photo
        _hide_bubble()

    def _sprite_photo_for(character, mood):
        """A sprite PhotoImage for (character, mood), composited over the
        dialog's dark bg (not magenta-baked -- this is a normal opaque window).
        Falls back to neutral if the mood has no art."""
        photo = cache.sprite(character, mood)
        if photo is None:
            photo = cache.sprite(character, "neutral")
        return photo

    def _set_sprite_mood(character, mood):
        """Swap the displayed sprite to a new mood (keeps the same centered
        position). Called after each reply lands."""
        photo = _sprite_photo_for(character, mood)
        if photo:
            canvas.itemconfig(canvas.sprite_id, image=photo)
            _sprite_photo["id"] = photo

    def show_scene(path):
        canvas.itemconfig(canvas.image_id, image=cache.photo(path, scene_size))

    # --- speech bubble (drawn below the sprite on the same canvas) ---

    def _hide_bubble():
        for it in _bubble_items:
            try:
                canvas.delete(it)
            except Exception:
                pass
        _bubble_items.clear()

    def _show_bubble(text):
        """Draw a rounded speech bubble below the sprite with the reply text.
        Mirrors pet.py:_show_bubble's rounded-rect+tail geometry, but the
        bubble opens downward (tail points up toward the sprite)."""
        _hide_bubble()
        if not text:
            return
        # Measure text via a hidden Label (wrap at canvas width minus padding).
        wrap = img_w - 48
        meas = tk.Label(win, text=text, font=(config.UI_FONT, 10), justify="left",
                        wraplength=wrap - 24, bg=theme.BG, fg=theme.FG)
        meas.update_idletasks()
        tw, th = meas.winfo_reqwidth(), meas.winfo_reqheight()
        pad_x, pad_y, radius = 12, 8, 14
        bw = min(img_w - 24, tw + 2 * pad_x)
        bh = th + 2 * pad_y
        # Bubble top sits just below the sprite; clamp to canvas bottom.
        sprite_bottom = sprite_cy + _SPRITE_SIZE // 2
        by0 = sprite_bottom + 6
        max_bh = img_h - by0 - 10
        if bh > max_bh:
            bh = max_bh
        by1 = by0 + bh
        # Center horizontally.
        bx0 = (img_w - bw) // 2
        bx1 = bx0 + bw
        # Tail points up to the sprite, centered on the bubble.
        tail_x = bx0 + bw // 2
        pts = theme.round_rect_points(bx0, by0, bx1, by1, radius)
        bg = canvas.create_polygon(*pts, fill="white", outline="#9aa0a6",
                                   width=1, smooth=False)
        tail = canvas.create_polygon(
            tail_x - 6, by0 + 1, tail_x + 6, by0 + 1, tail_x, by0 - 8,
            fill="white", outline="#9aa0a6", width=1)
        seam = canvas.create_line(tail_x - 5, by0, tail_x + 5, by0,
                                  fill="white", width=2)
        text_item = canvas.create_text(
            bx0 + bw / 2, by0 + bh / 2, text=text, font=(config.UI_FONT, 10),
            fill="#1a1a1a", justify="left", width=bw - 2 * pad_x,
            anchor="center")
        _bubble_items.extend([bg, tail, seam, text_item])

    # --- selection: show talk-to image briefly, then switch to sprite ---

    def select(character):
        if busy["on"]:
            return
        selected["char"] = character
        # Switching character starts a fresh conversation -- the old history
        # was with a different persona, so it would confuse the new one.
        conversation.clear()
        # Hide the "Talk to ..." buttons once a character is chosen -- they're
        # only for the initial pick and would clutter the sprite view.
        btns.pack_forget()
        # 1. Flash the talk-to scene image for 1.5s.
        scene = {
            "andrew": config.AICHAT_TALK_ANDREW,
            "ashley": config.AICHAT_TALK_ASHLEY,
        }[character]
        canvas.itemconfig(canvas.image_id, image=cache.photo(scene, scene_size))
        canvas.itemconfig(canvas.image_id, state="normal")
        canvas.itemconfig(canvas.sprite_id, state="hidden")
        _hide_bubble()
        _set_status(f"{character.capitalize()} selected. Type below to talk.")
        # 2. After 1.5s, fade to the sprite view.
        def _switch_to_sprite():
            _show_sprite_mode(character, "neutral")
        win.after(1500, _switch_to_sprite)

    # --- character buttons (placed under each portrait's center) ---
    btns = tk.Frame(win, bg=theme.BG, height=btn_h)
    btns.pack(fill="x", padx=10, pady=(0, 4))
    btn_andrew = theme.make_button(
        btns, text="Talk to Andrew", width=16,
        command=lambda: select("andrew"))
    btn_ashley = theme.make_button(
        btns, text="Talk to Ashley", width=16,
        command=lambda: select("ashley"))
    btn_andrew.place(anchor="center", relx=0.70, rely=0.5)
    btn_ashley.place(anchor="center", relx=0.30, rely=0.5)

    # --- chat input bar (bottom) ---
    # disp is the name shown in the status bar. It must reflect the character
    # actually being talked to (selected), not pet.character (the pet the dialog
    # was opened from) -- opening AI chat from Ashley then selecting "Talk to
    # Andrew" should show "Andrew said: ...", not "Ashley said: ...".
    def _disp_for(c):
        return config.CHARACTER_META.get(c, {}).get("display", c)

    def _set_status(text):
        status.config(text=text)

    def do_request(_ev=None):
        if busy["on"]:
            return
        char = selected["char"] or pet.character
        user_msg = entry.get().strip()
        if not user_msg:
            return  # nothing to say
        # Clear the input so the user can type the next line right away
        # (multi-turn chat). The message is already captured in user_msg.
        entry.delete(0, tk.END)
        # If no character selected yet, drop into sprite view for the pet.
        if not selected["char"]:
            select(pet.character)
        if not ai_chat.is_configured():
            loc = pet.dialogue.random_line(pet.character, rng=pet.rng)
            if loc:
                _set_sprite_mood(char, loc.mood)
                _show_bubble(loc.text)
            _set_status("No key -- used a local line. Click ⚙ to enable AI.")
            return
        busy["on"] = True
        btn.config(state="disabled")
        _set_status("Generating...")

        def worker():
            # Pass the running conversation so the model can reply in context
            # (multi-turn). ai_chat bypasses the cache when history is present.
            line, mood, cached = ai_chat.fetch_ai_line(char, user_msg,
                                                       history=conversation)

            def done():
                busy["on"] = False
                btn.config(state="normal")
                if line:
                    _set_sprite_mood(char, mood)
                    _show_bubble(line)
                    _set_status(f"{_disp_for(char)} said:{(' (cached)' if cached else '')}  {line}")
                    # Append this turn to the running conversation so the next
                    # request sees it. The assistant turn keeps the mood|line
                    # prefix the model was instructed to emit, keeping the
                    # persona consistent. user turn wraps the raw input.
                    conversation.append({"role": "user", "content": user_msg})
                    conversation.append({"role": "assistant", "content": f"{mood}|{line}"})
                else:
                    loc = pet.dialogue.random_line(char, rng=pet.rng)
                    if loc:
                        _set_sprite_mood(char, loc.mood)
                        _show_bubble(loc.text)
                    _set_status("AI unavailable -- used a local line instead.")
            root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    bar = tk.Frame(win, bg=theme.BG)
    bar.pack(fill="x", padx=10, pady=(4, 8))
    entry = tk.Entry(bar, font=(config.UI_FONT, 10),
                     bg=theme.BG_ELEVATED, fg=theme.FG,
                     insertbackground=theme.FG, relief="flat", bd=0,
                     highlightthickness=1, highlightbackground=theme.BORDER)
    entry.pack(side="left", fill="x", expand=True)
    btn = theme.make_button(bar, text="Say it", width=10, command=do_request)
    btn.pack(side="left", padx=(4, 2))
    theme.make_button(
        bar, text="⚙", width=2,
        command=lambda: _open_settings(root, status)
    ).pack(side="left", padx=2)
    status = tk.Label(bar,
                      text="Pick a character above, then type below.",
                      font=(config.UI_FONT, 8), fg=theme.FG_DIM, bg=theme.BG)
    status.pack(side="left", padx=6)

    entry.bind("<Return>", do_request)

    # --- initial paint: scene mode ---
    show_scene(config.AICHAT_ORIGINAL)
    _show_scene_mode()
    win.protocol("WM_DELETE_WINDOW", win.destroy)


def _open_settings(root, status_label):
    """A tiny key/model config window. Persists via user_settings."""
    w = tk.Toplevel(root)
    w.title("AI settings")
    w.geometry("420x200")
    w.attributes("-topmost", True)
    w.resizable(False, False)
    w.config(bg=theme.BG_ELEVATED)

    tk.Label(w, text="OpenRouter API key", font=(config.UI_FONT, 9, "bold"),
             fg=theme.FG, bg=theme.BG_ELEVATED).pack(pady=(10, 2), anchor="w", padx=14)
    key_entry = tk.Entry(w, width=52, font=(config.UI_FONT, 9), show="*",
                         bg=theme.BG, fg=theme.FG, insertbackground=theme.FG,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=theme.BORDER)
    key_entry.pack(padx=14)
    cur = user_settings.get_ai_key()
    if cur:
        key_entry.insert(0, cur)

    tk.Label(w, text="Model (free models end in :free)",
             font=(config.UI_FONT, 9, "bold"), fg=theme.FG, bg=theme.BG_ELEVATED) \
        .pack(pady=(8, 2), anchor="w", padx=14)
    model_entry = tk.Entry(w, width=52, font=(config.UI_FONT, 9),
                           bg=theme.BG, fg=theme.FG, insertbackground=theme.FG,
                           relief="flat", bd=0, highlightthickness=1,
                           highlightbackground=theme.BORDER)
    model_entry.pack(padx=14)
    model_entry.insert(0, user_settings.get_ai_model())

    info = tk.Label(w, text="", font=(config.UI_FONT, 8), fg=theme.ACCENT, bg=theme.BG_ELEVATED,
                    wraplength=380, justify="left")
    info.pack(pady=(6, 4), padx=14)

    def save():
        user_settings.save_ai_key(key_entry.get().strip())
        user_settings.save_ai_model(model_entry.get().strip())
        info.config(text="Saved. Get a free key at openrouter.ai/keys")
        status_label.config(text=status_label.cget("text"))

    theme.make_button(w, text="Save", width=10, command=save).pack(pady=6)
