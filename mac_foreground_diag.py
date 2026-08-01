"""Diagnostic: print exactly what companion.foreground_app_name() returns
and which step fails on THIS machine. Run from the project dir:

    python mac_foreground_diag.py

(macOS: `python3 mac_foreground_diag.py`). It prints each step so we can see
whether PyObjC loads, NSWorkspace resolves, and localizedName comes back.
Safe to delete after the issue is resolved.
"""
import sys
sys.path.insert(0, ".")

print("platform:", sys.platform)
print("1) is pyobjc importable?")
try:
    import AppKit
    print("   AppKit OK")
except Exception as e:
    print("   AppKit FAILED:", repr(e))
    sys.exit(0)

print("2) NSWorkspace sharedWorkspace?")
try:
    ws = AppKit.NSWorkspace.sharedWorkspace()
    print("   ws =", ws)
except Exception as e:
    print("   FAILED:", repr(e))
    sys.exit(0)

print("3) frontmostApplication?")
try:
    app = ws.frontmostApplication()
    print("   app =", app)
    if app is None:
        print("   frontmostApplication returned None — nothing is frontmost?")
except Exception as e:
    print("   FAILED:", repr(e))
    sys.exit(0)

print("4) localizedName / bundleIdentifier / isActive?")
for attr in ("localizedName", "bundleIdentifier", "isActive", "processIdentifier"):
    try:
        val = getattr(app, attr)
        # some are methods
        if callable(val):
            val = val()
        print(f"   {attr} = {val!r}")
    except Exception as e:
        print(f"   {attr} FAILED: {e!r}")

print("5) full runningApplications (active, with activation policy):")
try:
    apps = ws.runningApplications()
    print("   count:", len(apps))
    shown = 0
    for a in apps:
        try:
            if a.activationPolicy() == 0:  # NSApplicationActivationPolicyRegular
                name = a.localizedName()
                print(f"     active app: {name!r} (pid {a.processIdentifier()})")
                shown += 1
                if shown >= 8:
                    break
        except Exception as e:
            print("     one app failed:", repr(e))
except Exception as e:
    print("   FAILED:", repr(e))

print("6) companion.foreground_app_name() result:")
import companion
print("   ", repr(companion.foreground_app_name()))
print("   category:", companion._categorize(companion.foreground_app_name()))
