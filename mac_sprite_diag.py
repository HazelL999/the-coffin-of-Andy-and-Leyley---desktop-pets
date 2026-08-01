"""macOS-only diagnostic: figure out why the pet sprite doesn't show on a
-transparent + systemTransparent Canvas, even though the purple screen is gone.

Run on the Mac:  python3 mac_sprite_diag.py
It pops a small transparent window, draws a test sprite (a solid red square
RGBA PNG built in-memory, no external file needed), and prints what it finds.
Close the window or Ctrl-C to exit.
"""
import sys
if sys.platform != "darwin":
    print("This diagnostic is macOS-only. Run it on the Mac.")
    sys.exit(0)

import tkinter as tk
from PIL import Image, ImageTk

root = tk.Tk()
root.withdraw()

print("Tcl/Tk version:", tk.Tcl().eval("info patchlevel"))
# 'tk windowingsystem' needs a real Tk main window; root is one now.
try:
    print("Tk windowingsystem:", root.tk.call("tk", "windowingsystem"))
except tk.TclError as e:
    print("Tk windowingsystem: FAILED", e)

win = tk.Toplevel(root)
win.overrideredirect(True)
win.geometry("200x200+100+100")
try:
    win.wm_attributes("-transparent", True)
    print("-transparent True: OK")
except tk.TclError as e:
    print("-transparent True: FAILED", e)

try:
    win.config(bg="systemTransparent")
    print("bg=systemTransparent: OK")
except tk.TclError as e:
    print("bg=systemTransparent: FAILED", e)

try:
    win.attributes("-topmost", True)
except tk.TclError:
    pass

canvas = tk.Canvas(win, width=200, height=200, bd=0, highlightthickness=0,
                   bg="systemTransparent")
canvas.pack()

# A solid opaque red square with a transparent surround — if it shows, the
# Canvas displays opaque image pixels over a transparent bg.
img = Image.new("RGBA", (100, 100), (220, 40, 40, 255))
photo = ImageTk.PhotoImage(img)
canvas.create_image(100, 100, image=photo, anchor="center")

# Also a Canvas-drawn shape (not a photo) to compare.
canvas.create_oval(20, 20, 60, 60, fill="blue", outline="")

win.update_idletasks()
print("window geometry:", win.winfo_geometry())
print("canvas w/h:", canvas.winfo_width(), canvas.winfo_height())
print("canvas bg:", canvas.cget("bg"))
print()
print(">>> If you see a RED square and a BLUE oval floating on the desktop,")
print("    create_image works on a transparent Canvas — the sprite bug is")
print("    elsewhere (geometry / image ref / asset path).")
print(">>> If the window is transparent but you see NOTHING (no red, no blue),")
print("    the transparent Canvas swallows image+shape draws — need a")
print("    different approach (e.g. composite sprite onto an opaque bg, or")
print("    use a non-transparent Canvas region).")
print(">>> If you see a solid grey/white block, systemTransparent isn't")
print("    honored by this Tk build.")

root.after(15000, root.destroy)  # auto-close after 15s
root.mainloop()
