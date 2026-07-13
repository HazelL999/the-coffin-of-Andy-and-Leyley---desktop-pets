"""Entry point for the Andy & Leyley desktop pets.

Usage:
    python run.py [--no-interaction] [--no-assets-check]
"""

import argparse
import sys
import tkinter as tk


def main():
    parser = argparse.ArgumentParser(description="Andy & Leyley desktop pets.")
    parser.add_argument("--no-interaction", action="store_true",
                        help="Disable the interaction sequences between pets.")
    parser.add_argument("--no-assets-check", action="store_true",
                        help="Skip startup checks; just run.")
    args = parser.parse_args()

    # Friendly warning if no assets present (placeholder will still show).
    if not args.no_assets_check:
        try:
            import config
            has_any = any((config.ASSETS_DIR / c / m).is_dir() and
                          any((config.ASSETS_DIR / c / m).glob("*"))
                          for c in config.CHARACTERS
                          for m in __import__("expressions").MOODS)
            if not has_any:
                sys.stderr.write(
                    "[pets] No sprite art found in assets/. Running with "
                    "placeholders. Drop PNG/GIF into assets/<character>/<mood>/ "
                    "to add art.\n")
        except Exception:
            pass

    root = tk.Tk()
    root.withdraw()  # main window hidden; pets use Toplevels

    import main as main_mod  # noqa: E402
    app = main_mod.PetApp(root, no_interaction=args.no_interaction)  # noqa: F841

    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()


if __name__ == "__main__":
    main()
