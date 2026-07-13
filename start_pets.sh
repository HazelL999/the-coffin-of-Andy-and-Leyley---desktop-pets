#!/bin/bash
# Launch the Andy & Leyley desktop pets (macOS/Linux).
# Usage: ./start_pets.sh
cd "$(dirname "$0")"
python3 run.py
# If the app exits immediately, the error is printed above.
