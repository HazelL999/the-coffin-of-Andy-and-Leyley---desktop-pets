"""Centralized dark theme for every opaque UI surface (dialogs, menus, the
control panel, buttons). Single source of truth so the look is consistent
across Win + macOS.

The strict black bg + near-white text exists specifically because macOS Aqua
renders native tk.Button/tk.Menu bevels that IGNORE bg/fg unless overridden
— left to the theme default, buttons come out a washed grey that makes text
barely readable. style_button forces relief=flat/bd=0/highlightthickness=0
to suppress that bevel; style_menu sets bg/fg/activebackground (Mac menus
are native but honor those). Transparent sprite windows and the speech
bubble (white bg, dark text) are NOT UI surfaces and stay untouched.
"""

BG = "#141414"            # near-black panel/dialog background
BG_ELEVATED = "#1f1f24"   # buttons / listbox / cell frames (slightly lifted)
FG = "#f0f0f0"            # near-white primary text
FG_DIM = "#9aa0a6"        # secondary text / hints
ACCENT = "#ffd24a"        # talisman count / status accents (kept from before)
SELECT = "#2f3338"        # listbox selection / button active bg
BORDER = "#3a3f4a"        # outlines


def style_button(btn):
    """Force a tk.Button to a flat dark look (suppresses the Mac Aqua native
    bevel that ignores bg/fg). Call right after constructing the button:
        style_button(tk.Button(parent, text=..., command=...)).pack(...)
    Returns the button so it can be chained."""
    try:
        btn.config(bg=BG_ELEVATED, fg=FG, activebackground=SELECT,
                   activeforeground=FG, relief="flat", bd=0,
                   highlightthickness=0, borderwidth=0)
    except Exception:
        pass
    return btn


def style_menu(menu):
    """Force a tk.Menu (right-click menu / cascade submenu) to dark bg +
    white text. macOS menus are native but honor bg/fg/activebackground;
    Windows menus honor them fully."""
    try:
        menu.config(bg=BG, fg=FG, activebackground=BG_ELEVATED,
                    activeforeground=FG, borderwidth=0)
    except Exception:
        pass
    return menu
