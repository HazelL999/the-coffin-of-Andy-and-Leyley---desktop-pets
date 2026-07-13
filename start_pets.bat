@echo off
REM Launch the Andy & Leyley desktop pets on Windows without a console window.
REM
REM Uses pythonw (the no-console Python interpreter) so no black cmd box shows.
REM Assumes a working Python is on PATH (see README — `pip install -r
REM requirements.txt` first). If pythonw isn't on PATH, falls back to plain
REM python (which shows a console; it pauses only on crash so the error stays
REM readable and no window lingers on a normal launch).
REM
REM NOTE for the author's own machine: the desktop shortcut
REM "Andy & Leyley.lnk" points DIRECTLY at the bundled pythonw.exe and does
REM NOT go through this bat (a bat-launched GUI process can be reaped when the
REM temporary cmd session that `start`+`exit /b` spawns it under closes). This
REM bat is kept for contributors running from a terminal where Python is on PATH.
cd /d "%~dp0"

where pythonw >nul 2>nul && (
    start "" pythonw run.py
    exit /b
)

REM Last resort: console python. This shows a window; pause only on crash.
python run.py
if errorlevel 1 pause
