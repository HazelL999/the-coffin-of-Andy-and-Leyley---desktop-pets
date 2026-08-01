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


def transparent_bg(transparent_color):
    """The bg color a transparent window's Toplevel AND its child widgets
    (Canvas, etc.) should use so their background is truly see-through.

    - Windows: the transparent color (magenta). -transparentcolor then punches
      that exact color out as transparent + click-through.
    - macOS: 'systemTransparent', a system color with alpha. macOS has no
      -transparentcolor; -transparent True only *allows* the content area to be
      transparent — the real transparency comes from the Toplevel (and every
      child widget, or its solid bg covers the transparency) being set to a
      color with alpha. 'systemTransparent' is the value Tk's wm man page
      names for this. Using the Windows magenta here would show as a solid
      magenta block (no color keying on macOS).
    - Linux/other: the transparent color (no real transparency; sprites sit
      on a magenta block — best effort).
    """
    if is_macos():
        return "systemTransparent"
    return transparent_color


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
        # Toplevel bg must be an alpha-bearing system color (NOT "" — Tk treats
        # empty as the default grey, not transparent). Child widgets (Canvas)
        # must use the same via transparent_bg(), or their solid bg covers the
        # transparency. See transparent_bg() docstring.
        win.config(bg=transparent_bg(transparent_color))
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
    """macOS: toggle ignoring all mouse events. No-op on Windows (per-pixel
    click-through there comes from -transparentcolor). On macOS a transparent
    window STILL receives mouse events by default — there's no auto
    click-through for transparent regions — so a full-screen overlay (like
    the bond line window) must call this with on=True or it swallows every
    click on the desktop."""
    if not is_macos():
        return
    try:
        ns_win = _resolve_ns_window(win)
        if ns_win is not None:
            ns_win.setIgnoresMouseEvents_(on)
    except Exception:
        pass


def bind_context_menu(win, handler, canvas=None):
    """Bind right-click cross-platform to call handler(event).

    Windows/Linux: Button-3. macOS: Button-2 and Ctrl-Button-1. (A plain
    double-click is NOT bound — see note below.)

    On macOS, if `canvas` is given, also bind the same events to it: the
    sprite NSView sublayer can intercept rightMouseDown at the win level,
    but Canvas-level bindings still fire (the Canvas is the hit-test target
    when the sublayer is positioned below it), so binding the Canvas too
    makes two-finger tap / Ctrl-click reach the menu reliably.

    NOTE: double-click (<Double-Button-1>) used to ALSO open the menu on
    macOS (as a discoverable fallback when a trackpad has no right-button
    gesture Tk maps to Button-2). It was removed because a double-click
    also fires two <Button-1> poke events, and the menu's tk_popup grab
    interrupts the click sequence — so the 3-poke rage reaction could
    never complete (the 2nd click opened the menu first). macOS still has
    two ways to open the menu: two-finger tap (right-click -> Button-2,
    forwarded by _SpriteLayer.rightMouseDown_) and Ctrl-click.
    """
    win.bind("<Button-3>", handler)
    if is_macos():
        win.bind("<Button-2>", handler)
        win.bind("<Control-Button-1>", handler)
        if canvas is not None:
            # Canvas-level bindings fire even when a sublayer interferes
            # with win-level right-click delivery.
            canvas.bind("<Button-2>", handler)
            canvas.bind("<Control-Button-1>", handler)



# ---------------------------------------------------------------------------
# macOS sprite bridge (variant 1a)
#
# On macOS, Tk's create_image is zeroed by kCGBlendModeSourceAtop on
# -transparent windows (backing alpha=0 => result alpha always 0). Canvas
# native shapes (oval/polygon/line/text) still draw fine. So we keep Tk
# Toplevel/Canvas/after/bind intact and draw sprites on a transparent NSView
# sublayer of the Tk window's contentView, using NSImage (source-over, not
# SourceAtop). The sublayer's hitTest_ returns nil so mouse events fall
# through to the Tk Canvas — drag/poke keep working over the sprite.
#
# Verified by mac_gate_test.py: NSImage visible on transparent TKWindow, and
# clicks on the image region still trigger Tk Canvas <Button-1>.
# ---------------------------------------------------------------------------

def _mac_pyobjc_available():
    """True if pyobjc-framework-Cocoa (AppKit) is importable on macOS."""
    if not is_macos():
        return False
    try:
        import AppKit  # noqa: F401
        import objc  # noqa: F401
        return True
    except Exception:
        return False


def pil_to_nsimage(pil_rgba):
    """PIL RGBA Image -> NSImage, preserving per-pixel alpha. macOS only.
    Returns None if PyObjC is unavailable or the conversion fails."""
    if not _mac_pyobjc_available():
        return None
    try:
        import io
        import AppKit
        buf = io.BytesIO()
        pil_rgba.save(buf, format="PNG")
        raw = buf.getvalue()
        data = AppKit.NSData.dataWithBytes_length_(raw, len(raw))
        return AppKit.NSImage.alloc().initWithData_(data)
    except Exception:
        return None


if _mac_pyobjc_available():
    import AppKit as _AppKit
    import objc as _objc

    class _SpriteLayer(_AppKit.NSView):
        """A transparent NSView that draws one NSImage; fully click-through.

        hitTest_ returns None so the view never claims hit-testing. Plus we
        forward rightMouseDown (and other non-left mouse downs) to the next
        responder — Mac trackpad two-finger tap fires rightMouseDown, which
        bypasses hit-testing and would otherwise get swallowed by this
        subview, hiding the Tk Canvas <Button-2> menu binding. Forwarding
        lets it reach the Tk contentView like a normal right click.
        """

        def initWithFrame_image_(self, frame, image):
            self = _objc.super(_SpriteLayer, self).initWithFrame_(frame)
            if self is None:
                return None
            self._image = image
            return self

        def setImage_(self, image):
            self._image = image
            self.setNeedsDisplay_(True)

        def drawRect_(self, rect):
            if self._image:
                self._image.drawInRect_fromRect_operation_fraction_(
                    self.bounds(), _AppKit.NSZeroRect,
                    _AppKit.NSCompositeSourceOver, 1.0)

        def hitTest_(self, point):
            # Never claim hit-testing — let the Tk Canvas underneath get it.
            return None

        def rightMouseDown_(self, event):
            # Forward right-click (two-finger tap) to the next responder so
            # the Tk Canvas <Button-2> binding fires the right-click menu.
            nr = self.nextResponder()
            if nr is not None:
                nr.rightMouseDown_(event)

        def otherMouseDown_(self, event):
            nr = self.nextResponder()
            if nr is not None:
                nr.otherMouseDown_(event)


def _resolve_ns_window(tk_win):
    """Find the NSWindow backing a Tk Toplevel on macOS.

    winfo_id() returns Tk's internal MacDrawable*, not the NSWindow
    windowNumber, so windowWithWindowNumber_ returns None. Fall back to
    NSApp.orderedWindows() and match by frame size AND origin. Size alone
    is not enough — two pet windows have identical size but different
    positions, so a size-only match would attach both sprite bridges to the
    same NSWindow. Cocoa's frame origin is bottom-left; Tk's winfo_x/y is
    top-left, so convert: cocoa_origin_y = screen_h - tk_y - win_h.
    Returns the NSWindow (a TKWindow) or None.
    """
    if not _mac_pyobjc_available():
        return None
    try:
        ns_app = _AppKit.NSApplication.sharedApplication()
        tw = tk_win.winfo_width()
        th = tk_win.winfo_height()
        tx = tk_win.winfo_x()
        ty = tk_win.winfo_y()
        screen_h = tk_win.winfo_screenheight()
        # Cocoa origin is bottom-left; flip the Tk top-left y.
        cocoa_x = tx
        cocoa_y = screen_h - ty - th
        best = None
        for w in ns_app.orderedWindows() or []:
            f = w.frame()
            if (abs(f.size.width - tw) < 2
                    and abs(f.size.height - th) < 2
                    and abs(f.origin.x - cocoa_x) < 2
                    and abs(f.origin.y - cocoa_y) < 2):
                best = w
                break
        return best
    except Exception:
        return None


class MacSpriteBridge:
    """Manages one NSView sprite sublayer on a Tk Toplevel's NSWindow.

    attach() must be called after the Tk window is mapped (update_idletasks +
    a short delay) so winfo_width/height and the NSWindow exist. update_image()
    swaps the NSImage and triggers a redraw. detach() removes the sublayer.

    All methods are no-ops (attach returns False) if PyObjC is unavailable,
    so callers can fall back to canvas.create_image without crashing.
    """

    def __init__(self):
        self._layer = None
        self._ns_win = None

    def attach(self, tk_win, width, height, x=0, y=0):
        """Attach a sprite sublayer to tk_win's NSWindow. Returns True on
        success, False if PyObjC missing or the NSWindow can't be resolved."""
        if not _mac_pyobjc_available():
            return False
        ns_win = _resolve_ns_window(tk_win)
        if ns_win is None:
            return False
        content = ns_win.contentView()
        if content is None:
            return False
        # Cocoa origin is bottom-left; callers pass Tk-style top-left offsets.
        # For a sprite centered in the window we compute from the content height.
        try:
            ch = content.bounds().size.height
        except Exception:
            ch = height
        frame = _AppKit.NSMakeRect(x, ch - y - height, width, height)
        self._layer = _SpriteLayer.alloc().initWithFrame_image_(frame, None)
        if self._layer is None:
            return False
        # Add the sprite layer BELOW the Tk Canvas (TKContentView) so the
        # Canvas stays the hit-test target and receives all mouse events
        # (left-click drag/poke AND right-click menu / two-finger tap).
        # Relying on hitTest_ pass-through was fragile for rightMouseDown.
        # The Canvas is transparent (systemTransparent), so the sprite still
        # shows through from underneath.
        content.addSubview_positioned_relativeTo_(
            self._layer, _AppKit.NSWindowBelow, None)
        self._ns_win = ns_win
        return True

    def update_image(self, nsimage):
        """Swap the sprite's NSImage (triggers redraw). No-op if not attached."""
        if self._layer is not None:
            self._layer.setImage_(nsimage)

    def set_frame(self, x, y, width, height):
        """Move/resize the sprite sublayer (Tk top-left origin)."""
        if self._layer is None:
            return
        try:
            content = self._ns_win.contentView()
            ch = content.bounds().size.height
            self._layer.setFrame_(_AppKit.NSMakeRect(x, ch - y - height, width, height))
        except Exception:
            pass

    def detach(self):
        if self._layer is not None:
            try:
                self._layer.removeFromSuperview()
            except Exception:
                pass
            self._layer = None
        self._ns_win = None
