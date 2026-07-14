"""PetApp: owns the Tk root, both pets, a persistent control panel, the single
main loop, and an optional interaction director that makes the pets talk to
each other.
"""

import math
import random
import time
import json

import tkinter as tk

import config
import platform_utils
import scheduler as sched_mod
from asset_loader import AssetLoader
from dialogue import DialogueStore
from pet import Pet
from state import CodependencyState
from altar import Altar
from backpack import Backpack, BackpackItem
from vision import VisionWindow


class InteractionDirector:
    """Occasionally makes the two pets act out a small scene:

    - "cling": Ashley sidles up next to Andrew and the two exchange a line.
    - "chase": Andrew chases Ashley; she sidesteps away; he catches up and
      the two exchange a line.
    In both, the pets end up one body-width apart, facing each other, then
    speak (which also freezes them — see Pet.freeze_until).
    """

    SCENE_WEIGHTS = {"cling": 2.0, "chase": 1.0, "scripted": 1.5, "scene": 0.8, "choice": 0.4}

    def __init__(self, pets, dialogue_store, rng=None, enabled=True,
                 root=None, codep=None):
        self.pets = pets
        self.dialogue_store = dialogue_store
        self.rng = rng or random
        self.enabled = enabled
        # root (for scheduling .after) + codep (for choice-scene deltas) are
        # needed by _approach_choice; passed in by PetApp.
        self.root = root
        self.codep = codep
        self.next_at = time.monotonic() + self.rng.uniform(*config.INTERACTION_RANGE)
        self.active = False
        self.global_cooldown = 0.0  # last trigger time

    def maybe_trigger(self, now):
        if not self.enabled or len(self.pets) < 2 or self.active:
            return False
        if now - self.global_cooldown < config.INTERACTION_COOLDOWN:
            return False
        if now < self.next_at:
            return False
        self._start(now)
        return True

    def _pet(self, character):
        for p in self.pets:
            if p.character == character:
                return p
        return None

    def _start(self, now):
        self.active = True
        self.global_cooldown = now
        self.next_at = now + self.rng.uniform(*config.INTERACTION_RANGE)
        andrew = self._pet("andrew")
        ashley = self._pet("ashley")
        if not andrew or not ashley or not andrew.win or not ashley.win:
            self.active = False
            return
        scene = self.rng.choices(list(self.SCENE_WEIGHTS.keys()),
                                 weights=list(self.SCENE_WEIGHTS.values()), k=1)[0]
        if scene == "scene" and self.dialogue_store:
            seq = self.dialogue_store.random_scene(self.rng)
            if seq:
                self._approach_scripted(seq)  # walk together, then play beats
                return
            scene = "cling"  # no scenes configured -> fall through
        if scene == "scripted" and self.dialogue_store:
            seq = self.dialogue_store.random_dialogue(self.rng)
            if seq:
                self._approach_scripted(seq)
                return
            # no dialogues configured -> fall through to a cling scene
            scene = "cling"
        if scene == "choice" and self.dialogue_store:
            choice = self.dialogue_store.random_choice(self.rng)
            if choice:
                self._approach_choice(choice)
                return
            scene = "cling"  # no choices configured -> fall through
        if scene == "chase":
            self._approach_chase(andrew, ashley)
        else:
            self._approach_cling(ashley, andrew)

    def _beside(self, mover, target):
        """Target a point one body-width to the side of `target` nearer to
        `mover`. Returns (target_x, target_y)."""
        size = config.PLACEHOLDER_SIZE
        offset = size + 10
        tx = target.x - offset if mover.x < target.x else target.x + offset
        return tx, target.y

    def _approach_cling(self, ashley, andrew):
        # Ashley walks up beside Andrew, faces him; then they exchange lines.
        tx, ty = self._beside(ashley, andrew)
        ashley.target_x, ashley.target_y = tx, ty
        ashley.facing = "right" if andrew.x >= ashley.x else "left"
        ashley.state = Pet.STATE_WANDERING
        andrew.facing = "left" if andrew.x >= ashley.x else "right"
        ashley.win.after(2500, lambda: self._exchange(ashley, andrew))

    def _approach_chase(self, andrew, ashley):
        # Andrew chases Ashley. After he's been walking a moment, Ashley
        # sidesteps away (evade); Andrew re-targets her new position. When he
        # closes in, they exchange lines. Freeze is handled by speak().
        andrew.target_x, andrew.target_y = self._beside(andrew, ashley)
        andrew.facing = "right" if ashley.x >= andrew.x else "left"
        andrew.state = Pet.STATE_WANDERING

        def evade():
            # Ashley hops sideways a short distance (still on screen), away
            # from Andrew, to keep the chase going a little longer.
            sign = 1 if ashley.x >= andrew.x else -1
            nx = ashley.x + sign * config.CHASE_EVADE_PX
            x0, _, x1, _ = ashley.bounds
            nx = max(x0 + config.SCREEN_MARGIN,
                     min(nx, x1 - config.PLACEHOLDER_SIZE - config.SCREEN_MARGIN))
            ashley.target_x, ashley.target_y = nx, ashley.y
            ashley.facing = "right" if nx >= ashley.x else "left"
            ashley.state = Pet.STATE_WANDERING
            andrew.target_x, andrew.target_y = self._beside(andrew, ashley)
            andrew.facing = "right" if ashley.x >= andrew.x else "left"

        andrew.win.after(1100, evade)
        andrew.win.after(2600, lambda: self._exchange(andrew, ashley))

    def _approach_scripted(self, beats):
        """Play a fixed dialogue sequence. The first speaker walks up to the
        other, then each beat is spoken in order (speak() handles multi-bubble
        beats and freezes both pets)."""
        if not beats or not beats[0].character:
            self.active = False
            return
        first = self._pet(beats[0].character)
        other = self._pet(beats[1].character) if len(beats) > 1 else None
        if not first or not first.win:
            self.active = False
            return
        if other:
            tx, ty = self._beside(first, other)
            first.target_x, first.target_y = tx, ty
            first.facing = "right" if other.x >= first.x else "left"
            other.facing = "left" if other.x >= first.x else "right"
            first.state = Pet.STATE_WANDERING
        # Let the approach walk a moment before the first line.
        self._play_beats(beats, first, start_delay=2200)

    def _play_beats(self, beats, first, start_delay=0):
        """Speak each beat in order (used by both scripted scenes and
        drag-onto scenes). `first` is any pet whose win we schedule on."""
        def play(i=0):
            if i >= len(beats):
                first.win.after(int(config.BUBBLE_HOLD * 1000) + 800,
                                lambda: self._finish())
                return
            beat = beats[i]
            speaker = self._pet(beat.character)
            if speaker and speaker.win:
                from dialogue import DialogueLine as DL
                line = DL(beat.character, beat.mood, beat.text)
                speaker.speak(line)
                n = len(beat.text) if isinstance(beat.text, list) else 1
                gap_ms = int(n * config.BUBBLE_HOLD * 1000) + 400
            else:
                gap_ms = 300
            first.win.after(gap_ms, lambda: play(i + 1))
        if start_delay:
            first.win.after(start_delay, lambda: play(0))
        else:
            play(0)

    def _exchange(self, a, b):
        try:
            line_a = a.dialogue.random_line(a.character, rng=a.rng)
            if line_a:
                a.speak(line_a)
            # b responds after a short pause.
            a.win.after(1500, lambda: self._respond(b))
        finally:
            a.win.after(int(config.BUBBLE_HOLD * 1000) + 1800,
                        lambda: self._finish())

    def _respond(self, b):
        line_b = b.dialogue.random_line(b.character, rng=b.rng)
        if line_b:
            b.speak(line_b)

    def _finish(self):
        self.active = False

    def _approach_choice(self, choice):
        """A player-choice scene: the speaker walks up to the other, asks a
        question (as a speech bubble), then a choice popup appears. The user's
        pick adjusts codependency and triggers a response line."""
        speaker_name = choice["speaker"]
        question = choice["question"]
        options = choice["options"]
        speaker = self._pet(speaker_name)
        if not speaker or not speaker.win:
            self._finish()
            return
        other_name = "ashley" if speaker_name == "andrew" else "andrew"
        other = self._pet(other_name)
        if other:
            tx, ty = self._beside(speaker, other)
            speaker.target_x, speaker.target_y = tx, ty
            speaker.facing = "right" if other.x >= speaker.x else "left"
            other.facing = "left" if other.x >= speaker.x else "right"
            speaker.state = Pet.STATE_WANDERING
        # After the approach walk, speaker asks the question, then popup opens.
        def ask():
            from dialogue import DialogueLine as DL
            # Pick a mood that fits asking — neutral is safe for both.
            ask_mood = "neutral" if speaker_name == "andrew" else "chuckle"
            speaker.speak(DL(speaker_name, ask_mood, question))
            # Freeze both during the popup (speak already froze them; extend
            # the freeze until the user picks + response plays).
            hold = time.monotonic() + config.BUBBLE_HOLD + 30.0  # generous
            speaker.freeze_until(hold)
            if other:
                other.freeze_until(hold, face_toward=(speaker.x, speaker.y))
            # Open the popup after the question bubble shows.
            speaker.win.after(int(config.BUBBLE_HOLD * 1000), _open_popup)

        def _open_popup():
            import choice_dialog
            # Determine the speaker's mood for the popup sprite.
            mood = speaker.current_mood
            choice_dialog.open_choice_dialog(
                self.root, speaker_name, mood, question, options,
                on_choice=lambda idx: _on_choice(idx))

        def _on_choice(idx):
            opt = options[idx] if idx < len(options) else options[0]
            # Apply codep deltas.
            if self.codep:
                for char_name, delta in opt.get("codep", {}).items():
                    self.codep.adjust(char_name, delta)
            # Speak the response line (if the option has one).
            resp = opt.get("response")
            if resp and isinstance(resp, dict):
                from dialogue import DialogueLine as DL
                rc = resp.get("character", other_name)
                rm = resp.get("mood", "neutral")
                rt = resp.get("text", "...")
                responder = self._pet(rc) or speaker
                if responder and responder.win:
                    responder.speak(DL(rc, rm, rt))
            # Finish after the response bubble.
            speaker.win.after(int(config.BUBBLE_HOLD * 1000) + 800,
                              lambda: self._finish())

        # Schedule the ask after the approach walk.
        speaker.win.after(2200, ask)


class PetApp:
    def __init__(self, root, no_interaction=False):
        self.root = root
        self.rng = random.Random()
        self.bounds = platform_utils.screen_bounds(root)

        self.loader = AssetLoader()
        self.dialogue = DialogueStore.load()

        self.pets = []
        for char in config.CHARACTERS:
            s = sched_mod.PetScheduler(rng=self.rng)
            pet = Pet(char, self.loader, self.dialogue, s, self.root,
                      self.bounds, rng=self.rng,
                      on_quit=self.quit,
                      on_partner_freeze=self._on_partner_freeze,
                      on_drag_onto_partner=self._on_drag_onto_partner,
                      on_poked=self._on_poked,
                      on_check_state=self.check_state,
                      on_summon_altar=self._on_summon_altar,
                      on_open_backpack=self._on_open_backpack,
                      on_set_city=self._on_set_city,
                      on_ai_chat=self._on_ai_chat,
                      on_toggle_music=self._on_toggle_music)
            pet.start()
            self.pets.append(pet)

        # Shared codependency state; each pet gets a reference.
        self.codep = CodependencyState()
        for pet in self.pets:
            pet.codep = self.codep

        # Wire each pet to know its partner (used by distance-band + drag-onto).
        if len(self.pets) == 2:
            self.pets[0].partner_ref = self.pets[1]
            self.pets[1].partner_ref = self.pets[0]

        # The altar window (summoned on demand, dismissed when done).
        self.altar = None
        # Backpack & talisman charges (sacrifice +1, use -1). Persisted across
        # restarts in the env-state file so a sacrifice isn't lost on quit.
        self.backpack = None
        self.talisman_charges = self._load_talisman_charges()

        # Preload all moods so dropping art in mid-run still works (lazy cache).
        for char in config.CHARACTERS:
            self.loader.load_character(char)

        self.director = InteractionDirector(self.pets, self.dialogue, rng=self.rng,
                                            enabled=not no_interaction,
                                            root=self.root, codep=self.codep)

        # Environment context: morning/evening + holiday greetings at first
        # launch of the day, and weather/todo reactivity on condition change.
        # Held here so _tick can poll it; never raises (silent on failure).
        from env_context import EnvContext
        self.env = EnvContext(self.root, self.pets, self.rng, self.dialogue,
                             director=self.director)
        self.root.after(1500, self.env.startup_greeting)  # let the GUI settle

        # Background music: pygame.mixer looped playback. Best-effort — if
        # pygame isn't installed or no music files, the app runs silently.
        from music_player import MusicPlayer
        self.music = MusicPlayer()
        self.music.start()

        self._build_control_panel(no_interaction)

        self.last_time = time.monotonic()
        # Red bond line: a separate transparent window that draws a faint line
        # between the two pets when codependency is high. Updated each tick.
        self._bond_win = None
        self._bond_line = None
        self._init_bond_window()
        # Throttled topmost refresh: re-lift both pets every LIFT_INTERVAL_S so
        # other topmost windows don't bury them. Skips a pet mid-drag.
        self._last_lift = 0.0
        self._tick()

    def _build_control_panel(self, no_interaction):
        self.panel = tk.Toplevel(self.root)
        self.panel.title("Andy & Leyley")
        self.panel.geometry("190x96")
        self.panel.attributes("-topmost", True)
        self.panel.resizable(False, False)
        # Keep it a normal opaque window so it's always grabbable (even when a
        # pet is in click-through mode on macOS).

        tk.Label(self.panel, text="Andy & Leyley", font=(config.UI_FONT, 10, "bold")) \
            .pack(pady=(6, 2))

        btns = tk.Frame(self.panel)
        btns.pack()

        tk.Button(btns, text="Quit", width=7, command=self.quit).pack(side="left", padx=3)

        self.interaction_on = not no_interaction
        self.inter_btn = tk.Button(btns, text="Interact: ON" if self.interaction_on else "Interact: OFF",
                                   width=11, command=self._toggle_interaction)
        self.inter_btn.pack(side="left", padx=3)

        if platform_utils.is_macos():
            self.click_through_on = False
            self.ct_btn = tk.Button(self.panel,
                                    text="Click-through: OFF", width=18,
                                    command=self._toggle_click_through)
            self.ct_btn.pack(pady=4)
        else:
            # Position hint label instead.
            tk.Label(self.panel, text="Right-click a pet for more",
                     font=(config.UI_FONT, 8), fg="#666").pack(pady=(2, 0))

        # Place panel near bottom-right of the primary screen.
        try:
            w = self.root.winfo_screenwidth()
            h = self.root.winfo_screenheight()
            self.panel.geometry(f"+{w - 220}+{h - 160}")
        except Exception:
            pass

        self.panel.protocol("WM_DELETE_WINDOW", self.quit)
        self.panel.bind("<Escape>", lambda e: self.quit())
        self.panel.bind("<Control-q>", lambda e: self.quit())
        self.panel.bind("<Command-q>", lambda e: self.quit())

    def _toggle_interaction(self):
        self.interaction_on = not self.interaction_on
        self.director.enabled = self.interaction_on
        self.inter_btn.config(text="Interact: ON" if self.interaction_on else "Interact: OFF")

    def _toggle_click_through(self):
        self.click_through_on = not self.click_through_on
        for pet in self.pets:
            platform_utils.set_click_through(pet.win, self.click_through_on)
        self.ct_btn.config(text="Click-through: ON" if self.click_through_on
                           else "Click-through: OFF")

    def _init_bond_window(self):
        """A full-screen, transparent, click-through overlay that draws a faint
        red line between the two pets when their mutual codependency is high.

        Created once at startup (covering the whole primary screen) and never
        resized — we only update the line's coordinates each tick. This avoids
        the flicker and teardown cost of recreating an overlay window on every
        geometry change. The window is magenta-transparent like the pets, so its
        only visible pixel is the line itself.
        """
        try:
            win = tk.Toplevel(self.root)
            transparent_ok = platform_utils.setup_window(win, config.TRANSPARENT_COLOR)
            if not transparent_ok:
                # No real transparency on this platform/Tk build — a full-screen
                # overlay would cover the desktop in solid magenta. Bail: the
                # bond line is cosmetic and not worth that. (Pets still work;
                # they manage their own tighter windows.)
                win.destroy()
                self._bond_win = None
                self._bond_canvas = None
                self._bond_line = None
                return
            x0, y0, x1, y1 = self.bounds
            win.geometry(f"{int(x1 - x0)}x{int(y1 - y0)}+{int(x0)}+{int(y0)}")
            canvas = tk.Canvas(win, width=int(x1 - x0), height=int(y1 - y0),
                               bd=0, highlightthickness=0,
                               bg=config.TRANSPARENT_COLOR)
            canvas.pack()
            # The line lives under the sprites (its window is topmost too, but
            # we keep it just-less-than-topmost so pets render above it).
            try:
                win.attributes("-topmost", False)
            except tk.TclError:
                pass
            self._bond_win = win
            self._bond_canvas = canvas
            self._bond_line = None          # canvas item id, created lazily
            self._bond_visible = False      # whether the line is currently shown
        except Exception:
            # Bond visualization is purely cosmetic — never let it block startup.
            self._bond_win = None
            self._bond_canvas = None
            self._bond_line = None

    def _update_bond(self):
        """Refresh the bond line each tick. It appears ONLY when both pets'
        codependency reaches BOND_THRESHOLD (99.5 — see config) — a single,
        fixed-faintness red line between them. No gradient: the bond is
        either formed or not."""
        if not self._bond_win or len(self.pets) < 2:
            return
        a, b = self.pets[0], self.pets[1]
        if not a.win or not b.win:
            return
        ca = self.codep.get(a.character)
        cb = self.codep.get(b.character)
        # The bond needs BOTH pulled to the peak — the weaker one gates it.
        if min(ca, cb) < config.BOND_THRESHOLD:
            if self._bond_visible and self._bond_line is not None:
                self._bond_canvas.itemconfig(self._bond_line, state="hidden")
                self._bond_visible = False
            return
        # Create the line once (lazy), then just move it each tick.
        # Soft, faint red: a thin (width=1) solid line in a light pink-red.
        # No stipple — stipple dithers red against transparent (magenta) pixels
        # which -transparentcolor punches out, leaving a sparse red speckle that
        # reads grey/dusty rather than red. Thinness + a desaturated tint gives
        # the "soft thread" feel without needing true alpha (Windows
        # -transparentcolor can't do partial alpha without fringe).
        if self._bond_line is None:
            self._bond_line = self._bond_canvas.create_line(
                0, 0, 0, 0, fill="#e8909a", width=1)
        elif not self._bond_visible:
            self._bond_canvas.itemconfig(self._bond_line, state="normal")
        self._bond_visible = True
        # Bond line endpoints: each pet's sprite center, in overlay coords.
        # Pet sprite center in screen coords = (self.x + size/2, self.y + size/2);
        # the overlay sits at (x0,y0) so subtract that origin.
        ox, oy = self.bounds[0], self.bounds[1]
        size = config.PLACEHOLDER_SIZE
        ax = a.x + size / 2 - ox
        ay = a.y + size / 2 - oy
        bx = b.x + size / 2 - ox
        by = b.y + size / 2 - oy
        try:
            self._bond_canvas.coords(self._bond_line, ax, ay, bx, by)
        except tk.TclError:
            pass


    def _tick(self):
        now = time.monotonic()
        dt = min(now - self.last_time, 0.1)  # clamp big gaps
        self.last_time = now

        for pet in self.pets:
            pet.update(dt)
            event = pet.scheduler.tick(dt)
            if event:
                # While a scene (drag-onto / altar prophecy / scripted exchange)
                # is mid-flight, don't let a pet's scheduler fire a random
                # dialogue line that would talk over the scripted beats. Wander
                # is harmless (movement), expression just changes the face, so
                # only dialogue is muted — the pet still acts, just stays quiet.
                if event == "dialogue" and self.director.active:
                    event = "wander"
                pet.handle_event(event)

        self._update_distance_bands()
        self.director.maybe_trigger(now)

        # Environment: weather + todo reactivity (throttled inside poll()).
        self.env.poll()

        # Bond line: faint red connection when mutual codependency is high.
        self._update_bond()

        # Periodically re-assert topmost on both pets so other always-on-top
        # windows (taskbar, our own panel/popups, other apps) can't bury them.
        # Toggle off-then-on rather than a bare lift(): lift() only reorders
        # within the topmost group, while toggling re-asserts the topmost flag
        # and reliably pushes the window back above other topmost windows.
        # Skip a pet that's being dragged right now (would yank it under the
        # cursor).
        if now - self._last_lift >= config.LIFT_INTERVAL_S:
            self._last_lift = now
            for pet in self.pets:
                if pet._drag_data or not pet.win:
                    continue
                try:
                    pet.win.attributes("-topmost", False)
                    pet.win.attributes("-topmost", True)
                except tk.TclError:
                    pass

        self.root.after(config.FRAME_MS, self._tick)

    def _partner_of(self, pet):
        for other in self.pets:
            if other is not pet:
                return other
        return None

    def _on_partner_freeze(self, speaker):
        """Freeze the OTHER pet while `speaker` is talking, and turn it to
        face the speaker so the two look at each other during the exchange."""
        partner = self._partner_of(speaker)
        if partner is None:
            return
        hold = time.monotonic() + config.BUBBLE_HOLD + 0.2
        partner.freeze_until(hold, face_toward=(speaker.x, speaker.y))

    def _on_drag_onto_partner(self, dragged, partner):
        """A pet was dragged on top of the other -> play a drag-onto scene.
        The two are already overlapping, so skip the approach walk and play
        the scripted beats directly."""
        if self.director.active:
            return  # don't interrupt a running scene
        # Dragging onto each other bonds them.
        self.codep.adjust(dragged.character, config.CODEP_DRAG_ONTO_DELTA)
        self.codep.adjust(partner.character, config.CODEP_DRAG_ONTO_DELTA)
        seq = self.dialogue.random_drag_dialogue(dragged.character, self.rng)
        if not seq:
            return
        # Face each other where they landed.
        dragged.facing = "right" if partner.x >= dragged.x else "left"
        partner.facing = "left" if partner.x >= dragged.x else "right"
        self.director.active = True
        self.director.global_cooldown = time.monotonic()
        self.director._play_beats(seq, dragged)

    def _on_poked(self, pet):
        """A pet was clicked. Andrew poked rapidly -> Ashley angers."""
        if pet.character != "andrew" or not pet.partner_ref:
            return
        pet._click_count += 1
        # Reset the counter after the click window.
        if pet._click_reset_after_id:
            try:
                pet.win.after_cancel(pet._click_reset_after_id)
            except Exception:
                pass
        pet._click_reset_after_id = pet.win.after(
            int(config.CLICK_WINDOW_S * 1000), lambda: setattr(pet, "_click_count", 0))
        # Andrew gets a little attention bump.
        self.codep.adjust("andrew", config.CODEP_CLICK_ANDREW_DELTA)
        if pet._click_count >= config.CLICK_RAGE_THRESHOLD:
            pet._click_count = 0
            self._ashley_angers(pet)

    def _ashley_angers(self, andrew):
        """Ashley reacts angrily to Andrew being poked repeatedly."""
        ash = andrew.partner_ref
        if not ash or not ash.win:
            return
        self.codep.adjust("ashley", config.CODEP_CLICK_ASHLEY_DELTA)
        # Ashley walks over to Andrew and snaps.
        ash.target_x, ash.target_y = self.director._beside(ash, andrew)
        ash.facing = "right" if andrew.x >= ash.x else "left"
        ash.state = Pet.STATE_WANDERING
        def snap():
            # Use the ashley_angers trigger pool: these lines ("Stop poking
            # him!" etc.) only make sense in this event, so they're excluded
            # from random idle dialogue and only surface here.
            line = ash.dialogue.random_triggered("ashley", "ashley_angers",
                                                  rng=ash.rng)
            if line:
                ash.speak(line)
        ash.win.after(1500, snap)

    def check_state(self, pet):
        """Pop a small window showing ONE pet's codependency / mental state
        (right-clicked pet only)."""
        v = self.codep.get(pet.character)
        lvl = self.codep.level(pet.character)
        label, emoji = self.codep.mental_state(pet.character)
        disp = config.CHARACTER_META.get(pet.character, {}).get("display", pet.character)
        win = tk.Toplevel(self.root)
        win.title(f"{disp} — State")
        win.geometry("240x130")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        text = (f"{emoji}  {disp}\n\n"
                f"  codependency: {v:.0f}  ({lvl})\n"
                f"  mental state: {label}")
        tk.Label(win, text=text, font=(config.UI_FONT, 10),
                 justify="left", padx=14, pady=14).pack()
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def _on_open_backpack(self):
        """Open the backpack window (reuse if already open)."""
        if self.backpack is not None and self.backpack.win is not None:
            try:
                self.backpack.win.lift()
                self.backpack.win.attributes("-topmost", True)
            except Exception:
                pass
            return
        items = [BackpackItem(it["name"], it["path"], it["usable"])
                 for it in config.BACKPACK_ITEMS]
        self.backpack = Backpack(self.root, items,
                                 talisman_charges=self.talisman_charges,
                                 on_use_talisman=self._on_use_talisman)
        self.backpack.start()

    def _on_set_city(self):
        """Open the city-picker so the user can set their weather city."""
        import city_dialog
        def chosen(name, lat, lon):
            # Reset weather baseline so the next poll can fire a line for the
            # new location's current conditions (rather than being treated as
            # "no change" against the old location's last category).
            self.env._last_weather_cat = None
        city_dialog.open_city_dialog(self.root, on_chosen=chosen)

    def _on_toggle_music(self):
        """Toggle background music on/off."""
        playing = self.music.toggle()
        # Could show a status bubble, but keep it simple — silent toggle.

    def _on_ai_chat(self, pet):
        """Open the AI-chat dialog for the right-clicked pet."""
        import ai_dialog
        ai_dialog.open_ai_dialog(self.root, pet, director=self.director)

    def _on_use_talisman(self):
        """Consume one talisman charge and show a random vision image.
        Also nudges codependency: Andy random ±, Ashley +0.1."""
        if self.talisman_charges <= 0:
            return
        self.talisman_charges -= 1
        self._save_talisman_charges()
        if self.backpack:
            self.backpack.update_talisman_count(self.talisman_charges)
        # Codependency: Andy gets a random +0.2 or -0.1, Ashley +0.1.
        if self.codep:
            self.codep.adjust("andrew", self.rng.choice([0.2, -0.1]))
            self.codep.adjust("ashley", 0.1)
        # Pick a random vision image.
        import os
        visions = sorted(f for f in os.listdir(config.VISION_DIR)
                         if f.lower().endswith(".png"))
        if not visions:
            return
        pick = self.rng.choice(visions)
        path = os.path.join(config.VISION_DIR, pick)
        vw = VisionWindow(self.root, path)
        vw.show()

    def _on_summon_altar(self, pet):
        """Summon a temporary altar window next to the right-clicked pet."""
        # Place the altar beside the pet, offset to the right.
        ax = pet.x + config.PLACEHOLDER_SIZE + 20
        ay = pet.y - (config.ALTAR_SIZE - config.PLACEHOLDER_SIZE) // 2
        # Keep it on screen.
        x0, y0, x1, y1 = self.bounds
        ax = max(x0 + config.SCREEN_MARGIN,
                 min(ax, x1 - config.ALTAR_SIZE - config.SCREEN_MARGIN))
        ay = max(y0 + config.SCREEN_MARGIN,
                 min(ay, y1 - config.ALTAR_SIZE - config.SCREEN_MARGIN))
        # Reuse an existing altar if one is already open.
        if self.altar is not None and self.altar.win is not None:
            self.altar.x, self.altar.y = ax, ay
            self.altar._move_window()
        else:
            self.altar = Altar(self.root, ax, ay,
                               on_sacrifice_done=self._on_sacrifice_done,
                               on_sacrifice_start=self._on_sacrifice_start,
                               rng=self.rng)
            self.altar.start()

    def _on_sacrifice_start(self):
        """Ashley says her offering line immediately when the sacrifice begins
        (plays over the soul's flight animation). Also nudges codependency."""
        ashley = next((p for p in self.pets if p.character == "ashley"), None)
        if ashley and ashley.win and not self.director.active:
            from dialogue import DialogueLine
            line = DialogueLine("ashley", "chuckle",
                                "I offer this soul for one trinket charge and thank youuu.")
            ashley.speak(line)
        # Sacrifice costs codependency: Andy -0.5, Ashley -0.2.
        if self.codep:
            self.codep.adjust("andrew", -0.5)
            self.codep.adjust("ashley", -0.2)

    def _on_sacrifice_done(self):
        """The sacrifice animation finished — grant one talisman charge."""
        self.talisman_charges += 1
        self._save_talisman_charges()
        if self.backpack:
            self.backpack.update_talisman_count(self.talisman_charges)

    def _load_talisman_charges(self):
        """Read the persisted talisman count from the env-state file so a
        sacrifice survives a quit/restart. Defaults to 0 on any failure."""
        try:
            from env_context import EnvContext
            n = EnvContext._load_state().get("talisman_charges", 0)
            return int(n) if n else 0
        except Exception:
            return 0

    def _save_talisman_charges(self):
        """Merge the current talisman count into the env-state file (preserves
        the other keys like last_greet_date / last_active_timestamp). Silent
        on failure — the count is cosmetic, not worth crashing over."""
        try:
            from env_context import EnvContext
            data = EnvContext._load_state()
            data["talisman_charges"] = int(self.talisman_charges)
            with open(config.ENV_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _distance_band(dist):
        """Map a pixel distance to a band name (see config.DIST_*)."""
        u = dist / config.DIST_BAND_SIZE
        if u <= config.DIST_VERY_NEAR:
            return "very_near"
        if u <= config.DIST_CLOSE:
            return "close"
        if u <= config.DIST_FAR:
            return "far"
        return "very_far"

    def _update_distance_bands(self):
        """Every tick, recompute the inter-pet distance and tell each pet its
        band so idle moods + dialogue cooldown track proximity. Also drives
        codependency drift from proximity."""
        if len(self.pets) < 2:
            return
        a, b = self.pets[0], self.pets[1]
        dist = math.hypot(a.x - b.x, a.y - b.y)
        band = self._distance_band(dist)
        a.set_distance_band(band)
        b.set_distance_band(band)
        # Codependency drift from proximity — runs in every band now
        # (close/far/very_far all drain it; very_near raises it). Per-second
        # rates live in CodependencyState.tick; dt clamped by FRAME_MS so
        # it's small per tick.
        if self.codep:
            self.codep.tick(config.FRAME_MS / 1000.0, band)

    def quit(self):
        # Stop background music cleanly.
        try:
            self.music.shutdown()
        except Exception:
            pass
        # Record when the app closed so the next launch can detect a long
        # absence and trigger a reunion greeting.
        try:
            from env_context import EnvContext
            EnvContext.save_last_active_timestamp()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
