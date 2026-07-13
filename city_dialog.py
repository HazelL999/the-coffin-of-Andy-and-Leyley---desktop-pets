"""City picker dialog: lets the user set their city by name.

Right-click a pet -> "Set city…" opens this dialog. Type a city name, hit
Search; the Open-Meteo geocoding API (no key) returns candidate matches
(same name can exist in different countries — Shanghai CN vs Shanghai US),
the user picks one, and the choice (name + lat/lon) is persisted via
user_settings so future launches use it.

All network/file operations degrade silently: a failed search shows a
message instead of a traceback. The dialog runs on the Tk root's main loop.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import config
import user_settings


def open_city_dialog(root, on_chosen=None):
    """Build and show the city-picker Toplevel. `on_chosen(name, lat, lon)`
    is called (on the main thread) after a successful save, if given."""
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(root)
    win.title("Set city")
    win.geometry("360x300")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.config(bg="#2b2d33")

    tk.Label(win, text="Weather city", font=(config.UI_FONT, 11, "bold"),
             fg="#e0e0e0", bg="#2b2d33").pack(pady=(10, 4))

    row = tk.Frame(win, bg="#2b2d33")
    row.pack(pady=(0, 6))
    entry = tk.Entry(row, width=22, font=(config.UI_FONT, 10))
    entry.pack(side="left", padx=(10, 4))
    entry.focus_set()

    # Pre-fill with the current city name, if any.
    cur = user_settings.get_city_name()
    if cur:
        entry.insert(0, cur)

    listbox = tk.Listbox(win, height=8, font=(config.UI_FONT, 9),
                        bg="#1e2026", fg="#e0e0e0", selectbackground="#3a3f4a")
    listbox.pack(fill="both", expand=True, padx=10)
    status = tk.Label(win, text="", font=(config.UI_FONT, 8),
                     fg="#888", bg="#2b2d33")
    status.pack(pady=(4, 8))

    _candidates = []  # parallel to listbox rows

    def do_search(_ev=None):
        name = entry.get().strip()
        if not name:
            status.config(text="Type a city name first.")
            return
        listbox.delete(0, "end")
        _candidates.clear()
        status.config(text="Searching…")
        win.update_idletasks()
        results = _geocode(name)
        if results is None:
            status.config(text="Search failed (network?). Try again.")
            return
        if not results:
            status.config(text="No matches. Try another spelling.")
            return
        for c in results:
            label = _format(c)
            _candidates.append(c)
            listbox.insert("end", label)
        listbox.selection_set(0)
        status.config(text=f"{len(results)} match(es). Pick one, then Save.")

    def do_save(_ev=None):
        sel = listbox.curselection()
        if not sel or not _candidates:
            status.config(text="Search and pick a city first.")
            return
        c = _candidates[sel[0]]
        lat, lon = c.get("latitude"), c.get("longitude")
        if lat is None or lon is None:
            status.config(text="That match has no coordinates.")
            return
        city = c.get("name", entry.get().strip())
        # Persist so future launches use it.
        user_settings.save_city(city, lat, lon)
        win.destroy()
        if on_chosen:
            on_chosen(city, lat, lon)

    btn = tk.Button(win, text="Search", width=9, command=do_search)
    btn.pack(side="left", padx=(12, 4), pady=4)
    tk.Button(win, text="Save", width=9, command=do_save).pack(side="left", padx=4)
    tk.Button(win, text="Close", width=9, command=win.destroy).pack(side="left", padx=4)

    win.bind("<Return>", lambda e: (do_search() if not listbox.curselection()
                                    and listbox.size() == 0 else do_save()))
    entry.bind("<Return>", do_search)
    listbox.bind("<Double-Button-1>", do_save)


def _format(c):
    """One-line label for a geocoding candidate."""
    parts = [c.get("name") or "?"]
    if c.get("admin1"):
        parts.append(c["admin1"])
    if c.get("country"):
        parts.append(c["country"])
    return ", ".join(parts) + f"  ({c.get('latitude')}, {c.get('longitude')})"


def _geocode(name):
    """Query Open-Meteo geocoding API; return a list of candidate dicts, or
    None on network/parse failure (silent)."""
    url = (f"https://geocoding-api.open-meteo.com/v1/search"
           f"?name={urllib.parse.quote(name)}&count=8&language=en&format=json")
    try:
        with urllib.request.urlopen(url, timeout=config.WEATHER_TIMEOUT_S) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return data.get("results") or []
