"""Dialogue loading and weighted random selection.

Each line is tagged with a character and a mood, so when a pet speaks it can
set the matching expression. Unknown moods are warned and skipped (never crash).
The store reads from an external JSON so users can swap in verbatim game quotes.

A line's `text` may be a string (single bubble) or a list of strings (a
multi-bubble monologue: each bubble shows in turn, mood/expression set only
once — see Pet.speak). The optional top-level `dialogues` array holds fixed
multi-line exchange sequences the InteractionDirector can play out.
"""

import json
import random
import sys
from dataclasses import dataclass, field
from typing import Optional, Union, List

import config
import expressions


@dataclass
class DialogueLine:
    character: str
    mood: str
    text: Union[str, List[str]]
    weight: float = 1.0

    @property
    def is_multi(self) -> bool:
        return isinstance(self.text, list)


@dataclass
class DialogueBeat:
    """One beat of a fixed dialogue sequence: who says it, in what mood, and
    what text (str or list of str for a multi-bubble beat)."""
    character: str
    mood: str
    text: Union[str, List[str]]


class DialogueStore:
    def __init__(self):
        # (character, mood) -> list[DialogueLine]
        self._by_key = {}
        # character -> list[DialogueLine] (all moods)
        self._by_char = {c: [] for c in config.CHARACTERS}
        # list[list[DialogueBeat]] — fixed exchange sequences
        self._dialogues: List[List[DialogueBeat]] = []
        # dragged-character -> list[list[DialogueBeat]] — drag-onto scenes
        self._drag_dialogues: dict = {}
        # list[list[DialogueBeat]] — longer "skit" scenes auto-played on a timer
        self._scenes: List[List[DialogueBeat]] = []
        # list[list[DialogueBeat]] — prophecy lines spoken after a sacrifice
        self._prophecies: List[List[DialogueBeat]] = []
        # Environment-triggered lines:
        # period ("morning"/"evening") -> list[DialogueBeat] (single-beat)
        self._greetings: dict = {"morning": [], "evening": [], "late_night": []}
        # "MM-DD" -> list[DialogueBeat] (fixed-date holiday lines)
        self._holidays: dict = {}
        # weather category ("rain"/"overcast"/"clear") -> list[DialogueBeat]
        self._weather: dict = {}
        # list[list[DialogueBeat]] — Ashley reminds / Andrew deflects (todo grew)
        self._todo_reminders: List[List[DialogueBeat]] = []
        # list[list[DialogueBeat]] — reunion sequences on long-absence relaunch
        self._reunions: List[List[DialogueBeat]] = []
        # list[dict] — player-choice scenes (raw dicts: speaker/question/options)
        self._choices: list = []

    @classmethod
    def load(cls, path=None):
        path = path or config.DIALOGUE_PATH
        store = cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            sys.stderr.write(
                f"[dialogue] no dialogue file at {path}; pets will be silent.\n")
            return store
        except (json.JSONDecodeError, OSError) as exc:
            sys.stderr.write(f"[dialogue] failed to read {path}: {exc}\n")
            return store

        valid_moods = set(expressions.MOODS)
        valid_chars = set(config.CHARACTERS)

        lines = data.get("lines", []) if isinstance(data, dict) else []
        for entry in lines:
            if not isinstance(entry, dict):
                continue
            char = entry.get("character")
            mood = entry.get("mood")
            text = entry.get("text")
            if not char or not mood or text is None or text == "":
                continue
            if not _validate_entry(char, mood, valid_chars, valid_moods):
                continue
            try:
                weight = float(entry.get("weight", 1.0))
            except (TypeError, ValueError):
                weight = 1.0
            if weight <= 0:
                weight = 1.0
            line = DialogueLine(char, mood, text, weight)
            store._by_key.setdefault((char, mood), []).append(line)
            store._by_char.setdefault(char, []).append(line)

        # Fixed multi-line exchange sequences.
        dialogues = data.get("dialogues", []) if isinstance(data, dict) else []
        for entry in dialogues:
            if not isinstance(entry, dict):
                continue
            seq = entry.get("sequence")
            if not isinstance(seq, list) or not seq:
                continue
            beats = []
            for beat in seq:
                if not isinstance(beat, dict):
                    continue
                c = beat.get("character")
                m = beat.get("mood")
                t = beat.get("text")
                if not c or not m or t is None or t == "":
                    continue
                if not _validate_entry(c, m, valid_chars, valid_moods):
                    continue
                beats.append(DialogueBeat(c, m, t))
            if len(beats) == len(seq):  # all beats valid
                store._dialogues.append(beats)

        # Drag-onto sequences: fired when a pet is dragged onto the other.
        # Each entry has a `dragged` field (who was dragged) + a `sequence`.
        drag = data.get("drag_onto", []) if isinstance(data, dict) else []
        for entry in drag:
            if not isinstance(entry, dict):
                continue
            dragged = entry.get("dragged")
            seq = entry.get("sequence")
            if not isinstance(seq, list) or not seq or dragged not in valid_chars:
                continue
            beats = []
            for beat in seq:
                if not isinstance(beat, dict):
                    continue
                c = beat.get("character")
                m = beat.get("mood")
                t = beat.get("text")
                if not c or not m or t is None or t == "":
                    continue
                if not _validate_entry(c, m, valid_chars, valid_moods):
                    continue
                beats.append(DialogueBeat(c, m, t))
            if len(beats) == len(seq):
                store._drag_dialogues.setdefault(dragged, []).append(beats)

        # Skit scenes: longer multi-beat sequences auto-played on a timer.
        scenes = data.get("scenes", []) if isinstance(data, dict) else []
        for entry in scenes:
            if not isinstance(entry, dict):
                continue
            seq = entry.get("sequence")
            if not isinstance(seq, list) or not seq:
                continue
            beats = _parse_beats(seq, valid_chars, valid_moods)
            if len(beats) == len(seq):
                store._scenes.append(beats)

        # Prophecy lines: spoken after a soul is sacrificed at the altar.
        prophecies = data.get("prophecy", []) if isinstance(data, dict) else []
        for entry in prophecies:
            if not isinstance(entry, dict):
                continue
            seq = entry.get("sequence")
            if not isinstance(seq, list) or not seq:
                continue
            beats = _parse_beats(seq, valid_chars, valid_moods)
            if len(beats) == len(seq):
                store._prophecies.append(beats)

        # --- Environment-triggered lines ---
        # Morning/evening greetings: single-beat arrays, played at first launch
        # of the day. Weather: category-keyed single beats. Both reuse the
        # per-line DialogueBeat shape; todo_reminders are multi-beat sequences.
        for period, key in (("morning", "greetings_morning"),
                            ("evening", "greetings_evening"),
                            ("late_night", "late_night")):
            arr = data.get(key, []) if isinstance(data, dict) else []
            for entry in arr:
                if not isinstance(entry, dict):
                    continue
                c = entry.get("character")
                m = entry.get("mood")
                t = entry.get("text")
                if not c or not m or t is None or t == "":
                    continue
                if not _validate_entry(c, m, valid_chars, valid_moods):
                    continue
                store._greetings[period].append(DialogueBeat(c, m, t))

        holidays = data.get("holidays", []) if isinstance(data, dict) else []
        for entry in holidays:
            if not isinstance(entry, dict):
                continue
            date = entry.get("date")
            seq = entry.get("lines")
            if not isinstance(date, str) or not isinstance(seq, list) or not seq:
                continue
            beats = _parse_beats(seq, valid_chars, valid_moods)
            if len(beats) == len(seq):
                store._holidays[date] = beats

        weather = data.get("weather", []) if isinstance(data, dict) else []
        for entry in weather:
            if not isinstance(entry, dict):
                continue
            category = entry.get("category")
            c = entry.get("character")
            m = entry.get("mood")
            t = entry.get("text")
            if not category or not c or not m or t is None or t == "":
                continue
            if not _validate_entry(c, m, valid_chars, valid_moods):
                continue
            store._weather.setdefault(category, []).append(DialogueBeat(c, m, t))

        todo = data.get("todo_reminders", []) if isinstance(data, dict) else []
        for entry in todo:
            if not isinstance(entry, dict):
                continue
            seq = entry.get("sequence")
            if not isinstance(seq, list) or not seq:
                continue
            beats = _parse_beats(seq, valid_chars, valid_moods)
            if len(beats) == len(seq):
                store._todo_reminders.append(beats)

        # Reunion sequences: played on re-launch after a long absence.
        reunions = data.get("reunion", []) if isinstance(data, dict) else []
        for entry in reunions:
            if not isinstance(entry, dict):
                continue
            seq = entry.get("sequence")
            if not isinstance(seq, list) or not seq:
                continue
            beats = _parse_beats(seq, valid_chars, valid_moods)
            if len(beats) == len(seq):
                store._reunions.append(beats)

        # Player-choice scenes: stored as raw dicts (non-standard structure).
        # Each has speaker/question/options[{text,codep,response}].
        choices = data.get("choices", []) if isinstance(data, dict) else []
        for entry in choices:
            if not isinstance(entry, dict):
                continue
            speaker = entry.get("speaker")
            question = entry.get("question")
            options = entry.get("options")
            if speaker not in valid_chars or not question or not isinstance(options, list) \
                    or len(options) < 2:
                continue
            valid_opts = []
            for opt in options:
                if not isinstance(opt, dict) or not opt.get("text"):
                    continue
                resp = opt.get("response")
                if isinstance(resp, dict):
                    rc = resp.get("character")
                    rm = resp.get("mood")
                    rt = resp.get("text")
                    if rc not in valid_chars or not rm or not rt:
                        resp = None  # invalid response — caller skips it
                codep = opt.get("codep")
                if not isinstance(codep, dict):
                    codep = {}
                valid_opts.append({"text": opt["text"], "codep": codep, "response": resp})
            if len(valid_opts) >= 2:
                store._choices.append({
                    "speaker": speaker, "question": question, "options": valid_opts
                })
        return store

    def random_line(self, character: str, mood: Optional[str] = None,
                    rng: Optional[random.Random] = None) -> Optional[DialogueLine]:
        rng = rng or random
        if mood is not None:
            pool = self._by_key.get((character, mood))
            if not pool:
                # fall back to any mood for this character
                pool = self._by_char.get(character)
        else:
            pool = self._by_char.get(character)
        if not pool:
            return None
        weights = [l.weight for l in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    def random_dialogue(self, rng: Optional[random.Random] = None
                        ) -> Optional[List[DialogueBeat]]:
        """Pick a random fixed dialogue sequence, or None if none configured."""
        if not self._dialogues:
            return None
        rng = rng or random
        return rng.choices(self._dialogues, k=1)[0]

    def random_drag_dialogue(self, dragged: str,
                             rng: Optional[random.Random] = None
                             ) -> Optional[List[DialogueBeat]]:
        """Pick a random drag-onto sequence for the given dragged character,
        or None if none configured for them."""
        pool = self._drag_dialogues.get(dragged)
        if not pool:
            return None
        rng = rng or random
        return rng.choices(pool, k=1)[0]

    def random_scene(self, rng: Optional[random.Random] = None
                     ) -> Optional[List[DialogueBeat]]:
        """Pick a random skit scene, or None if none configured."""
        if not self._scenes:
            return None
        rng = rng or random
        return rng.choices(self._scenes, k=1)[0]

    def random_prophecy(self, rng: Optional[random.Random] = None
                        ) -> Optional[List[DialogueBeat]]:
        """Pick a random prophecy sequence (spoken after a sacrifice)."""
        if not self._prophecies:
            return None
        rng = rng or random
        return rng.choices(self._prophecies, k=1)[0]

    # --- Environment-triggered lines ---

    def random_greeting(self, period: str,
                        rng: Optional[random.Random] = None
                        ) -> Optional[DialogueBeat]:
        """Pick a random morning/evening greeting, or None if none configured.
        Returns a single DialogueBeat (not a sequence)."""
        pool = self._greetings.get(period)
        if not pool:
            return None
        rng = rng or random
        return rng.choices(pool, k=1)[0]

    def greeting_for_holiday(self, date_mmdd: str
                             ) -> Optional[List[DialogueBeat]]:
        """Return the fixed lines for a holiday (MM-DD), or None."""
        return self._holidays.get(date_mmdd)

    def random_weather(self, category: str,
                       rng: Optional[random.Random] = None
                       ) -> Optional[DialogueBeat]:
        """Pick a random line for a weather category (rain/overcast/clear)."""
        pool = self._weather.get(category)
        if not pool:
            return None
        rng = rng or random
        return rng.choices(pool, k=1)[0]

    def random_todo_reminder(self, rng: Optional[random.Random] = None
                             ) -> Optional[List[DialogueBeat]]:
        """Pick a random Ashley-reminds / Andrew-deflects sequence."""
        if not self._todo_reminders:
            return None
        rng = rng or random
        return rng.choices(self._todo_reminders, k=1)[0]

    def has_lines(self, character: str) -> bool:
        return bool(self._by_char.get(character))

    def random_reunion(self, rng: Optional[random.Random] = None
                       ) -> Optional[List[DialogueBeat]]:
        """Pick a random reunion sequence (played on long-absence re-launch)."""
        if not self._reunions:
            return None
        rng = rng or random
        return rng.choices(self._reunions, k=1)[0]

    def random_choice(self, rng: Optional[random.Random] = None) -> Optional[dict]:
        """Pick a random player-choice scene dict, or None if none configured.
        The dict has keys: speaker, question, options (list of {text,codep,response})."""
        if not self._choices:
            return None
        rng = rng or random
        return rng.choices(self._choices, k=1)[0]


def _validate_entry(character, mood, valid_chars, valid_moods):
    if character not in valid_chars:
        sys.stderr.write(
            f"[dialogue] skipping line with unknown character: {character}\n")
        return False
    if mood not in valid_moods:
        sys.stderr.write(
            f"[dialogue] skipping line with unknown mood '{mood}'"
            f" (character {character}). Valid moods: {', '.join(expressions.MOODS)}\n")
        return False
    return True


def _parse_beats(seq, valid_chars, valid_moods):
    """Parse a list of beat dicts into DialogueBeat objects, skipping invalid
    ones. Returns the beats (caller checks len == len(seq) for all-valid)."""
    beats = []
    for beat in seq:
        if not isinstance(beat, dict):
            continue
        c = beat.get("character")
        m = beat.get("mood")
        t = beat.get("text")
        if not c or not m or t is None or t == "":
            continue
        if not _validate_entry(c, m, valid_chars, valid_moods):
            continue
        beats.append(DialogueBeat(c, m, t))
    return beats
