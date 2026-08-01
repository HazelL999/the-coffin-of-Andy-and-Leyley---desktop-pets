"""macOS-only gate test for variant 1a (bridge NSView to draw sprite via NSImage,
keeping Tk Toplevel/Canvas/after/bind intact).

Verifies the two make-or-break assumptions BEFORE touching the app:
  1. An NSView sublayer drawing an NSImage (RGBA) IS visible on a transparent
     Tk Toplevel (whereas canvas.create_image is zeroed by Tk's SourceAtop bug).
  2. Mouse clicks on the NSImage region STILL reach the Tk Canvas's <Button-1>
     binding — i.e. the NSView sublayer can be made click-through so drag/poke
     keep working. (hitTest returns nil -> events pass through to Tk.)

Run on the Mac:  python3 mac_gate_test.py
A 200x200 transparent window appears with:
  - a RED square drawn via NSImage on an NSView sublayer (should be VISIBLE)
  - a BLUE oval drawn via Tk Canvas create_oval (visible already)
  - a Tk <Button-1> binding that prints "CLICK" and flips the oval color
Click around (on the red square too). If "CLICK" prints when you click the
red square, the click-through works and variant 1a is viable.
Close with Ctrl-C or the window auto-closes after 25s.
"""
import sys
if sys.platform != "darwin":
    print("macOS-only. Run on the Mac.")
    sys.exit(0)

import tkinter as tk
from PIL import Image

# PyObjC (needs pyobjc-framework-Cocoa for AppKit; pyobjc-core alone won't import AppKit)
try:
    import AppKit
    from AppKit import NSView, NSImage, NSColor, NSBezierPath
    import objc
except ImportError as e:
    print("PyObjC / AppKit not available:", e)
    print("Install:  pip3 install pyobjc-framework-Cocoa")
    sys.exit(0)


class SpriteLayer(NSView):
    """A transparent NSView that draws one NSImage, click-through.

    hitTest_ returns None so the view never claims mouse events — they fall
    through to the Tk Canvas underneath, keeping Tk's <Button-1> drag/poke
    bindings working over the sprite area.
    """
    def initWithFrame_image_(self, frame, image):
        self = objc.super(SpriteLayer, self).initWithFrame_(frame)
        if self is None:
            return None
        self._image = image
        return self

    def drawRect_(self, rect):
        # Clear to transparent (the window backing is already alpha=0 via
        # -transparent; this view just paints the image with source-over).
        if self._image:
            self._image.drawInRect_fromRect_operation_fraction_(
                self.bounds(), AppKit.NSZeroRect, AppKit.NSCompositeSourceOver, 1.0)

    def hitTest_(self, point):
        # Click-through: never claim the event. Lets Tk Canvas receive it.
        return None


def pil_to_nsimage(pil_rgba):
    """PIL RGBA Image -> NSImage (preserves per-pixel alpha)."""
    from PIL import Image as PILImage
    # Encode to PNG bytes, build NSBitmapImageRep, wrap in NSImage.
    import io
    buf = io.BytesIO()
    pil_rgba.save(buf, format="PNG")
    data = AppKit.NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    return AppKit.NSImage.alloc().initWithData_(data)


def main():
    root = tk.Tk()
    root.withdraw()
    print("Tcl/Tk:", root.tk.call("info", "patchlevel"))

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.geometry("200x200+100+100")
    win.wm_attributes("-transparent", True)
    win.config(bg="systemTransparent")
    win.attributes("-topmost", True)

    canvas = tk.Canvas(win, width=200, height=200, bd=0, highlightthickness=0,
                       bg="systemTransparent")
    canvas.pack()

    # Blue oval via Tk Canvas (already visible — proves Canvas native shapes work)
    oval = canvas.create_oval(20, 20, 60, 60, fill="blue", outline="")
    clicks = {"n": 0}

    def on_click(event):
        clicks["n"] += 1
        # flip oval color to give visual feedback the click registered
        canvas.itemconfig(oval, fill="red" if clicks["n"] % 2 else "blue")
        print(f"CLICK #{clicks['n']} at canvas ({event.x},{event.y}) — Tk Button-1 works")

    canvas.bind("<Button-1>", on_click)

    win.update_idletasks()
    # Force the NSWindow to exist before we grab it.
    root.update()

    # Bridge to the Tk Toplevel's NSWindow -> contentView, add the sprite sublayer.
    ns_win = AppKit.NSApplication.sharedApplication().windowWithWindowNumber_(
        win.winfo_id())
    if ns_win is None:
        print("ERROR: could not resolve NSWindow from winfo_id — bridge failed.")
        root.destroy()
        return
    content = ns_win.contentView()
    if content is None:
        print("ERROR: NSWindow has no contentView.")
        root.destroy()
        return

    # Build a red RGBA image and attach as a SpriteLayer subview.
    red = Image.new("RGBA", (100, 100), (220, 40, 40, 255))
    ns_img = pil_to_nsimage(red)
    layer = SpriteLayer.alloc().initWithFrame_image_(
        AppKit.NSMakeRect(50, 50, 100, 100), ns_img)
    content.addSubview_(layer)

    print(">>> Window up for 25s. You should see a RED square (NSImage) + a BLUE")
    print(">>> oval (Tk Canvas). Click the RED square — if 'CLICK' prints, the")
    print(">>> NSView sublayer is click-through and variant 1a is viable.")
    print(">>> If you see RED but clicks on it print NOTHING, click-through failed")
    print(">>> (would need a different event-passing approach).")
    print(">>> If you see NO red (only blue), NSImage drawRect isn't showing —")
    print(">>> variant 1a's rendering assumption is wrong.")

    root.after(25000, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
