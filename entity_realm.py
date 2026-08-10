"""Entity's realm -- opens Claw's Realm HTML in the default browser.

Summoned when the demon says "You owe me one soul now, tar soul." 10x.
Passes flower_total and mental_state (andrew/ashley) as URL query params
so chase.js can read them and pick the ending.
"""

import urllib.parse
import webbrowser
from pathlib import Path

import config

_REALM_HTML = Path(config.ROOT_DIR) / "entity_realm" / "index.html"


class EntityRealm:
    """Opens the Realm scene in the system browser."""

    def __init__(self, root, on_close=None):
        self.root = root
        self.on_close = on_close
        self.win = None  # no Tkinter window -- it's a browser tab

    def start(self, flower_total=0, mental_andrew=60, mental_ashley=60):
        """Open the Realm page with game params as URL query.
        flower_total: backpack flower count (each click uses 3).
        mental_andrew/ashley: mental_state values 0-100 (determines ending)."""
        try:
            url = _REALM_HTML.as_uri()
            params = urllib.parse.urlencode({
                "flowers": int(flower_total),
                "m_andrew": int(mental_andrew),
                "m_ashley": int(mental_ashley),
            })
            webbrowser.open(f"{url}?{params}")
        except Exception:
            pass
