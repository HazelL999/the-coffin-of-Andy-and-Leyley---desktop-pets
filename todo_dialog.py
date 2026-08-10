"""Todo editor: a small dark window showing the player's todo list with
checkboxes and optional deadlines (DDL).

Right-click a pet -> "Todo..." opens this. The todo.txt format is:
    [ ] buy milk @2026-08-10       -- unchecked, due Aug 10
    [x] reply to email             -- checked (done, doesn't count as open)
Lines without @DDL have no deadline. Comment (#) and blank lines are skipped
on load. On save the file is rewritten with the same header.

The env_context poll detects open-count changes and triggers pet reactions;
overdue items (DDL < today) are surfaced in the list with a red DDL label.
"""

from datetime import datetime as _datetime
import tkinter as tk

import config
import theme


def _today_str():
    return _datetime.now().strftime("%Y-%m-%d")


def _parse_line(raw):
    """Parse a todo.txt line into (checked, text, ddl). Returns None for
    comment/blank lines. Format: '[ ] text @ddl' / '[x] text @ddl'."""
    s = raw.strip()
    if not s or s.startswith("#"):
        return None
    checked = s.lower().startswith("[x]")
    if s.lower().startswith("[ ]") or s.lower().startswith("[x]"):
        s = s[3:].strip()
    ddl = ""
    if " @" in s:
        parts = s.rsplit(" @", 1)
        text = parts[0].strip()
        ddl = parts[1].strip()
    else:
        text = s
    return (checked, text, ddl)


def _format_line(checked, text, ddl):
    box = "[x]" if checked else "[ ]"
    return f"{box} {text}" + (f" @{ddl}" if ddl else "")


def open_todo_dialog(root):
    """Build and show the todo editor Toplevel."""
    win = tk.Toplevel(root)
    win.title("Todo")
    win.geometry("440x460")
    win.attributes("-topmost", True)
    win.resizable(False, False)
    win.config(bg=theme.BG_ELEVATED)

    tk.Label(win, text="Things to do", font=(config.UI_FONT, 11, "bold"),
             fg=theme.FG, bg=theme.BG_ELEVATED).pack(pady=(10, 6))

    # Scrollable list of items (each row: checkbox + text + ddl).
    list_outer = tk.Frame(win, bg=theme.BG_ELEVATED)
    list_outer.pack(fill="both", expand=True, padx=12)
    canvas = tk.Canvas(list_outer, bg=theme.BG, bd=0, highlightthickness=0,
                       height=280)
    scroll = tk.Scrollbar(list_outer, orient="vertical", command=canvas.yview,
                          bg=theme.BG_ELEVATED, troughcolor=theme.BG_ELEVATED)
    scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(canvas, bg=theme.BG)
    canvas.create_window((0, 0), window=inner, anchor="nw")
    def _on_inner(e=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_inner)

    rows = []  # list of dicts: {frame, check_var, text_var, ddl_var}

    def _load():
        try:
            with open(config.TODO_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            return
        for ln in lines:
            parsed = _parse_line(ln)
            if parsed is None:
                continue
            _add_row(*parsed)

    def _add_row(checked=False, text="", ddl=""):
        row = tk.Frame(inner, bg=theme.BG)
        row.pack(fill="x", pady=1)
        cv = tk.IntVar(value=1 if checked else 0)
        cb = tk.Checkbutton(row, variable=cv, bg=theme.BG,
                            activebackground=theme.BG,
                            selectcolor="#ffffff",
                            bd=0, highlightthickness=0)
        cb.pack(side="left")
        te = tk.Entry(row, font=(config.UI_FONT, 10), bg=theme.BG, fg=theme.FG,
                      insertbackground=theme.FG, relief="flat", bd=0,
                      highlightthickness=1, highlightbackground=theme.BORDER)
        te.insert(0, text)
        te.pack(side="left", fill="x", expand=True, padx=2)
        # DDL entry -- red text if overdue.
        de = tk.Entry(row, font=(config.UI_FONT, 9), width=11, bg=theme.BG,
                      fg=theme.FG_DIM, insertbackground=theme.FG, relief="flat",
                      bd=0, highlightthickness=1, highlightbackground=theme.BORDER)
        de.insert(0, ddl)
        def _check_ddl(_ev=None):
            d = de.get().strip()
            if d and d < _today_str():
                de.config(fg="#ff5555")
            else:
                de.config(fg=theme.FG_DIM)
        de.bind("<FocusOut>", _check_ddl)
        de.bind("<KeyRelease>", _check_ddl)
        _check_ddl()
        de.pack(side="left", padx=(2, 0))
        # Remove button for this row.
        theme.style_button(
            tk.Button(row, text="×", width=2, font=(config.UI_FONT, 8),
                      command=lambda: (row.destroy(), rows.remove(r)))
        ).pack(side="left", padx=(2, 0))
        r = {"frame": row, "check_var": cv, "text_var": te, "ddl_var": de}
        rows.append(r)

    # Input bar: text + DDL + Add.
    bar = tk.Frame(win, bg=theme.BG_ELEVATED)
    bar.pack(fill="x", padx=12, pady=(4, 6))
    new_entry = tk.Entry(bar, font=(config.UI_FONT, 10), bg=theme.BG,
                        fg=theme.FG, insertbackground=theme.FG, relief="flat",
                        bd=0, highlightthickness=1,
                        highlightbackground=theme.BORDER)
    new_entry.pack(side="left", fill="x", expand=True)
    new_ddl = tk.Entry(bar, font=(config.UI_FONT, 9), width=11, bg=theme.BG,
                      fg=theme.FG_DIM, insertbackground=theme.FG, relief="flat",
                      bd=0, highlightthickness=1, highlightbackground=theme.BORDER)
    new_ddl.pack(side="left", padx=(4, 0))

    def add_item(_ev=None):
        text = new_entry.get().strip()
        if text:
            _add_row(False, text, new_ddl.get().strip())
            new_entry.delete(0, tk.END)
            new_ddl.delete(0, tk.END)
            # scroll to bottom
            win.update_idletasks()
            canvas.yview_moveto(1.0)

    new_entry.bind("<Return>", add_item)
    theme.style_button(
        tk.Button(bar, text="Add", width=6, command=add_item)
    ).pack(side="left", padx=(4, 0))

    # Save / Cancel.
    btns = tk.Frame(win, bg=theme.BG_ELEVATED)
    btns.pack(pady=(0, 8))

    def save():
        header = ("# Andy & Leyley TODO list -- one open item per line.\n"
                  "# Format: '[ ] item @ddl' (unchecked) / '[x] item @ddl' (done).\n"
                  "# DDL is optional (YYYY-MM-DD). When the open count INCREASES,\n"
                  "# Ashley will scold you and Andrew will shrug.\n\n")
        try:
            with open(config.TODO_PATH, "w", encoding="utf-8") as f:
                f.write(header)
                for r in rows:
                    if not r["frame"].winfo_exists():
                        continue
                    checked = bool(r["check_var"].get())
                    text = r["text_var"].get().strip()
                    ddl = r["ddl_var"].get().strip()
                    if text:
                        f.write(_format_line(checked, text, ddl) + "\n")
        except Exception:
            pass
        win.destroy()

    theme.style_button(
        tk.Button(btns, text="Save", width=10, command=save)
    ).pack(side="left", padx=3)
    theme.style_button(
        tk.Button(btns, text="Cancel", width=10, command=win.destroy)
    ).pack(side="left", padx=3)

    _load()
    new_entry.focus_set()
    win.protocol("WM_DELETE_WINDOW", win.destroy)
