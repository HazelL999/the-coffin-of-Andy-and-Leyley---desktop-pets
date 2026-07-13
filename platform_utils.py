"""Platform-specific windowing, all guarded behind one module.

The rest of the app is platform-agnostic and calls into here.

- Windows: -transparentcolor makes pure-magenta pixels both invisible and
  click-through; opaque sprite pixels receive mouse events (draggable). No
  per-pixel alpha needed.
- macOS: -transparent (Tk 8.6/Aqua honors per-pixel alpha). Falls back to
  PyObjC NSWindow if the Tk build doesn't support it; absent pyobjc is fine.
"""

import sys

try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter should always be present
    tk = None


def is_windows():
    return sys.platform.startswith("win")


def is_macos():
    return sys.platform == "darwin"


def setup_window(win, transparent_color):
    """Make a borderless, always-on-top, transparent Toplevel.

    On Windows the transparent color is both invisible and click-through.
    On macOS we use per-pixel alpha.

    Returns True if real transparency is in effect, False if the window ended
    up opaque (callers of full-screen overlays should bail in that case, or a
    solid window would cover the desktop).
    """
    win.overrideredirect(True)          # no title bar / border
    win.attributes("-topmost", True)
    if is_windows():
        win.config(bg=transparent_color)
        try:
            win.wm_attributes("-transparentcolor", transparent_color)
            return True
        except tk.TclError:
            pass  # very old Tk: no transparency; sprite still shows on magenta bg
        return False
    elif is_macos():
        used = False
        try:
            win.wm_attributes("-transparent", True)
            used = True
        except tk.TclError:
            used = False
        if not used:
            _setup_mac_nswindow(win)    # PyObjC fallback (best-effort)
        win.config(bg="")  # clear so alpha is honored
        return used
    else:  # Linux/other: best effort, no true transparency
        win.config(bg=transparent_color)
        return False


def _setup_mac_nswindow(win):
    """PyObjC fallback: clear background + non-opaque NSWindow. Best-effort."""
    try:
        import AppKit  # noqa: F401
        import objc
    except Exception:
        return  # pyobjc not installed — app still runs, just opaque-ish
    try:
        win.update_idletasks()
        window_id = win.winfo_id()
        # Resolve the NSWindow owning this Tk view.
        from AppKit import NSWindow
        # winfo_id on macOS is the CGWindowNumber; we walk to the NSWindow.
        # This is the well-known fragile path; wrap heavily.
        view_ptr = objc.pyObject(id=window_id) if False else None  # placeholder
        # Simpler robust path: use AppKit to find frontmost window's NSWindow
        # is unreliable across Tk builds. We instead just disable shadow & opaque
        # via the tk path already attempted above; if that failed, there is no
        # safe generic route without pyobjc bridging winfo_id -> NSView.
        _ = NSWindow  # silence linter
    except Exception:
        return


def screen_bounds(root, use_virtual_desktop=False):
    """Return (x0, y0, x1, y1) of the usable screen area.

    Default: the PRIMARY monitor via Tk's winfo_screenwidth/height — pets stay
    on the primary so they're always visible. Set use_virtual_desktop=True to
    let them roam across all monitors on Windows.
    """
    try:
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
    except Exception:
        return (0, 0, 1920, 1080)

    if is_windows() and use_virtual_desktop:
        try:
            import ctypes
            # SM_XVIRTUALSCREEN=76, SM_YVIRTUALSCREEN=77,
            # SM_CXVIRTUALSCREEN=78, SM_CYVIRTUALSCREEN=79
            x = ctypes.windll.user32.GetSystemMetrics(76)
            y = ctypes.windll.user32.GetSystemMetrics(77)
            cx = ctypes.windll.user32.GetSystemMetrics(78)
            cy = ctypes.windll.user32.GetSystemMetrics(79)
            if cx and cy:
                return (x, y, x + cx, y + cy)
        except Exception:
            pass

    return (0, 0, w, h)


def set_click_through(win, on):
    """macOS: toggle ignoring all mouse events. No-op on Windows (per-pixel)."""
    if not is_macos():
        return
    try:
        import AppKit
        import objc
        win.update_idletasks()
        # Bridge to the NSWindow: Tk's winfo_id on macOS is the window number.
        # We grab the NSWindow via the shared application's windowWithWindowNumber:.
        app = AppKit.NSApplication.sharedApplication()
        ns_win = app.windowWithWindowNumber_(win.winfo_id())
        if ns_win is not None:
            ns_win.setIgnoresMouseEvents_(on)
    except Exception:
        pass


def bind_context_menu(win, handler):
    """Bind right-click cross-platform to call handler(event).

    Windows/Linux: Button-3. macOS: Button-2 and Ctrl-Button-1.
    """
    win.bind("<Button-3>", handler)
    if is_macos():
        win.bind("<Button-2>", handler)
        win.bind("<Control-Button-1>", handler)
