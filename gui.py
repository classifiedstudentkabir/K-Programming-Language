"""
gui.py — K++ Desktop IDE
========================
A Tkinter-based code editor and runner for the K++ Natural English
Programming Language.

Features
────────
  • Syntax-highlighted code editor (using the existing lexer)
  • Run button — executes code through the real interpreter pipeline
  • Output console — captures stdout cleanly
  • Error panel — formatted, colour-coded error messages
  • File open / save / new support for .kpp files
  • Clear output button
  • Line / column status bar
  • Real-time syntax highlighting (on every keypress, debounced)

Usage
─────
  python gui.py                  # open blank editor
  python gui.py program.kpp      # open a file directly

Architecture
────────────
  All interpreter logic lives in lexer.py / parser.py / evaluator.py.
  This file ONLY handles the UI layer.  It executes the interpreter by
  calling the same functions main.py uses, redirecting stdout to a
  StringIO buffer that is then written to the output panel.
"""

from __future__ import annotations

import sys
import os
import io
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from typing import Optional

# ── Make sure the kpp/ package is importable when gui.py sits next to
#    it (normal dev layout) or inside it.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from kpp.lexer import tokenize, KppLexError, TK
from kpp.parser import parse, KppSyntaxError
from kpp.evaluator import Evaluator, KppRuntimeError
from kpp.version import VERSION


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────────────────────────────────────

PALETTE = {
    "bg_dark":     "#1E1E2E",
    "bg_mid":      "#252535",
    "bg_editor":   "#1A1A2A",
    "bg_console":  "#13131F",
    "bg_toolbar":  "#2A2A3D",
    "fg_text":     "#CDD6F4",
    "fg_dim":      "#6C7086",
    "fg_line":     "#45475A",
    "accent":      "#89B4FA",   # blue — keywords
    "green":       "#A6E3A1",   # strings
    "yellow":      "#F9E2AF",   # numbers
    "red":         "#F38BA8",   # errors
    "orange":      "#FAB387",   # booleans / null
    "purple":      "#CBA6F7",   # identifiers in call
    "teal":        "#94E2D5",   # comments
    "btn_run":     "#A6E3A1",
    "btn_fg":      "#1E1E2E",
    "border":      "#313244",
    "selection":   "#45475A",
    "cursor":      "#CDD6F4",
    "error_bg":    "#2A1520",
    "error_fg":    "#F38BA8",
    "error_border":"#F38BA8",
}

# ─────────────────────────────────────────────────────────────────────────────
# Syntax highlighting token → colour mapping
# ─────────────────────────────────────────────────────────────────────────────

TOKEN_TAG_MAP = {
    TK.KEYWORD:    "tok_keyword",
    TK.STRING:     "tok_string",
    TK.NUMBER:     "tok_number",
    TK.BOOLEAN:    "tok_boolean",
    TK.NULL:       "tok_null",
    TK.IDENTIFIER: "tok_ident",
    TK.COMMA:      "tok_punct",
    TK.PERIOD:     "tok_punct",
}

TAG_COLORS = {
    "tok_keyword": PALETTE["accent"],
    "tok_string":  PALETTE["green"],
    "tok_number":  PALETTE["yellow"],
    "tok_boolean": PALETTE["orange"],
    "tok_null":    PALETTE["orange"],
    "tok_ident":   PALETTE["fg_text"],
    "tok_punct":   PALETTE["fg_dim"],
    "tok_comment": PALETTE["teal"],
    "tok_error":   PALETTE["red"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Scrolled text helper (Text + vertical scrollbar in one frame)
# ─────────────────────────────────────────────────────────────────────────────

class ScrolledText(tk.Frame):
    def __init__(self, master, **text_kwargs):
        super().__init__(master, bg=PALETTE["bg_dark"])
        self.text = tk.Text(self, **text_kwargs)
        self._vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self._vsb.set)
        self._vsb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

    # Proxy common Text methods
    def __getattr__(self, name):
        return getattr(self.text, name)


# ─────────────────────────────────────────────────────────────────────────────
# Line-number gutter
# ─────────────────────────────────────────────────────────────────────────────

class LineNumbers(tk.Canvas):
    def __init__(self, master, editor: tk.Text, **kwargs):
        # Extract font before passing to Canvas (Canvas doesn't support font option)
        self._font = kwargs.pop("font", None)
        super().__init__(master, **kwargs)
        self._editor = editor
        self.configure(width=48)
        editor.bind("<KeyRelease>", self._redraw, add="+")
        editor.bind("<ButtonRelease>", self._redraw, add="+")
        editor.bind("<<Modified>>", self._redraw, add="+")
        editor.bind("<Configure>", self._redraw, add="+")

    def _redraw(self, _event=None):
        self.delete("all")
        i = self._editor.index("@0,0")
        while True:
            dline = self._editor.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(
                44, y, anchor="ne",
                text=linenum,
                fill=PALETTE["fg_line"],
                font=self._font,
            )
            i = self._editor.index(f"{i}+1line")
            if i == self._editor.index(f"end-1line"):
                break


# ─────────────────────────────────────────────────────────────────────────────
# Main application window
# ─────────────────────────────────────────────────────────────────────────────

class KppIDE(tk.Tk):
    def __init__(self, initial_file: Optional[str] = None):
        super().__init__()

        self._app_title = f"K++ Programming Language v{VERSION}"
        self.title(self._app_title)
        try:
            self.iconbitmap("kpp.ico")
        except tk.TclError:
            # Keep UI working even if icon is missing or unsupported.
            pass
        self.geometry("1200x800")
        self.minsize(800, 560)
        self.configure(bg=PALETTE["bg_dark"])

        self._filepath: Optional[str] = None
        self._modified = False
        self._highlight_after: Optional[str] = None  # debounce id
        self._running = False

        self._setup_fonts()
        self._setup_styles()
        self._build_ui()
        self._setup_editor_tags()
        self._bind_keys()

        if initial_file and os.path.isfile(initial_file):
            self._open_file(initial_file)
        else:
            self._set_default_content()

        self._update_title()

    # ── fonts ─────────────────────────────────────────────────────────────────

    def _setup_fonts(self):
        families = tkfont.families()
        for candidate in ("JetBrains Mono", "Cascadia Code", "Fira Code",
                          "Consolas", "Courier New"):
            if candidate in families:
                self._code_font = tkfont.Font(family=candidate, size=13)
                break
        else:
            self._code_font = tkfont.Font(family="Courier New", size=13)

        self._ui_font    = tkfont.Font(family="Segoe UI", size=11)
        self._label_font = tkfont.Font(family="Segoe UI", size=10)
        self._bold_font  = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self._gutter_font = tkfont.Font(
            family=self._code_font.cget("family"), size=11
        )

    # ── ttk styles ─────────────────────────────────────────────────────────────

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TScrollbar",
            gripcount=0,
            background=PALETTE["bg_mid"],
            troughcolor=PALETTE["bg_dark"],
            bordercolor=PALETTE["bg_dark"],
            arrowcolor=PALETTE["fg_dim"],
            relief="flat",
        )
        style.configure(
            "TPanedwindow",
            background=PALETTE["bg_dark"],
            sashwidth=5,
            sashrelief="flat",
        )

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Menu bar ──────────────────────────────────────────────────────────
        menubar = tk.Menu(self, bg=PALETTE["bg_toolbar"], fg=PALETTE["fg_text"],
                          activebackground=PALETTE["accent"],
                          activeforeground=PALETTE["btn_fg"],
                          relief="flat", bd=0)
        self.configure(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0,
                            bg=PALETTE["bg_toolbar"], fg=PALETTE["fg_text"],
                            activebackground=PALETTE["accent"],
                            activeforeground=PALETTE["btn_fg"])
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New          Ctrl+N", command=self._new_file)
        file_menu.add_command(label="Open…        Ctrl+O", command=self._open_file_dialog)
        file_menu.add_command(label="Save         Ctrl+S", command=self._save_file)
        file_menu.add_command(label="Save As…     Ctrl+Shift+S", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        run_menu = tk.Menu(menubar, tearoff=0,
                           bg=PALETTE["bg_toolbar"], fg=PALETTE["fg_text"],
                           activebackground=PALETTE["accent"],
                           activeforeground=PALETTE["btn_fg"])
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Run Program   F5", command=self._run_code)
        run_menu.add_command(label="Syntax Check  F6", command=self._check_syntax)
        run_menu.add_separator()
        run_menu.add_command(label="Clear Output", command=self._clear_output)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = tk.Frame(self, bg=PALETTE["bg_toolbar"], height=44)
        toolbar.pack(side="top", fill="x")
        toolbar.pack_propagate(False)

        def _tb_btn(text, cmd, color=None, icon=""):
            bg = color or PALETTE["bg_mid"]
            btn = tk.Button(
                toolbar, text=f"{icon}  {text}" if icon else text,
                command=cmd, font=self._bold_font,
                bg=bg, fg=PALETTE["btn_fg"] if color else PALETTE["fg_text"],
                activebackground=PALETTE["accent"],
                activeforeground=PALETTE["btn_fg"],
                relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
            )
            btn.pack(side="left", padx=(8, 2), pady=6)
            return btn

        _tb_btn("New",    self._new_file,          icon="📄")
        _tb_btn("Open",   self._open_file_dialog,  icon="📂")
        _tb_btn("Save",   self._save_file,          icon="💾")

        tk.Frame(toolbar, bg=PALETTE["border"], width=1).pack(
            side="left", fill="y", padx=8, pady=6
        )

        self._run_btn = _tb_btn(
            "▶  Run", self._run_code,
            color=PALETTE["btn_run"], icon=""
        )
        self._run_btn.configure(text="▶  Run")

        _tb_btn("⟳  Check", self._check_syntax)
        _tb_btn("✕  Clear", self._clear_output)

        # File path label on right
        self._path_label = tk.Label(
            toolbar, text="  Untitled.kpp", font=self._label_font,
            bg=PALETTE["bg_toolbar"], fg=PALETTE["fg_dim"], anchor="e",
        )
        self._path_label.pack(side="right", padx=12)

        # ── Main pane (editor | output) ───────────────────────────────────────
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Left: editor ──────────────────────────────────────────────────────
        editor_frame = tk.Frame(pane, bg=PALETTE["bg_editor"])
        pane.add(editor_frame, weight=3)

        # header
        ed_header = tk.Frame(editor_frame, bg=PALETTE["bg_toolbar"], height=28)
        ed_header.pack(fill="x")
        ed_header.pack_propagate(False)
        tk.Label(ed_header, text="  Code Editor",
                 font=self._label_font, bg=PALETTE["bg_toolbar"],
                 fg=PALETTE["fg_dim"]).pack(side="left", padx=6)
        self._lang_badge = tk.Label(
            ed_header, text="K++",
            font=self._label_font, bg=PALETTE["accent"],
            fg=PALETTE["btn_fg"], padx=6, pady=1,
        )
        self._lang_badge.pack(side="right", padx=8, pady=4)

        # editor row (gutter + text)
        ed_row = tk.Frame(editor_frame, bg=PALETTE["bg_editor"])
        ed_row.pack(fill="both", expand=True)

        self._editor = tk.Text(
            ed_row,
            bg=PALETTE["bg_editor"], fg=PALETTE["fg_text"],
            insertbackground=PALETTE["cursor"],
            selectbackground=PALETTE["selection"],
            selectforeground=PALETTE["fg_text"],
            font=self._code_font,
            relief="flat", bd=0,
            padx=12, pady=8,
            undo=True,
            tabs=("28",),
            wrap="none",
        )

        self._gutter = LineNumbers(
            ed_row, self._editor,
            bg=PALETTE["bg_mid"], highlightthickness=0,
            font=self._gutter_font,
        )
        self._gutter.pack(side="left", fill="y")

        ed_vsb = ttk.Scrollbar(ed_row, orient="vertical",
                                command=self._editor.yview)
        ed_hsb = ttk.Scrollbar(editor_frame, orient="horizontal",
                                command=self._editor.xview)
        self._editor.configure(yscrollcommand=ed_vsb.set,
                                xscrollcommand=ed_hsb.set)
        ed_vsb.pack(side="right", fill="y")
        self._editor.pack(side="left", fill="both", expand=True)
        ed_hsb.pack(fill="x")

        # ── Right: output + error ─────────────────────────────────────────────
        right_frame = tk.Frame(pane, bg=PALETTE["bg_dark"])
        pane.add(right_frame, weight=2)

        # Output panel
        out_header = tk.Frame(right_frame, bg=PALETTE["bg_toolbar"], height=28)
        out_header.pack(fill="x")
        out_header.pack_propagate(False)
        tk.Label(out_header, text="  Output Console",
                 font=self._label_font, bg=PALETTE["bg_toolbar"],
                 fg=PALETTE["fg_dim"]).pack(side="left", padx=6)

        self._output_text = tk.Text(
            right_frame,
            bg=PALETTE["bg_console"], fg=PALETTE["green"],
            insertbackground=PALETTE["cursor"],
            font=self._code_font,
            relief="flat", bd=0,
            padx=10, pady=8,
            state="disabled",
            wrap="word",
            height=14,
        )
        out_vsb = ttk.Scrollbar(right_frame, orient="vertical",
                                 command=self._output_text.yview)
        self._output_text.configure(yscrollcommand=out_vsb.set)

        out_vsb.pack(side="right", fill="y")
        self._output_text.pack(fill="both", expand=True)

        # Error panel
        err_header = tk.Frame(right_frame, bg=PALETTE["bg_toolbar"], height=28)
        err_header.pack(fill="x")
        err_header.pack_propagate(False)
        self._err_badge = tk.Label(
            err_header, text="  No errors",
            font=self._label_font, bg=PALETTE["bg_toolbar"],
            fg=PALETTE["fg_dim"],
        )
        self._err_badge.pack(side="left", padx=6)

        self._error_frame = tk.Frame(right_frame, bg=PALETTE["bg_dark"])
        self._error_frame.pack(fill="x")

        self._error_text = tk.Text(
            self._error_frame,
            bg=PALETTE["error_bg"], fg=PALETTE["error_fg"],
            font=self._code_font,
            relief="flat", bd=0,
            padx=10, pady=6,
            state="disabled",
            wrap="word",
            height=6,
            highlightthickness=1,
            highlightbackground=PALETTE["error_border"],
            highlightcolor=PALETTE["error_border"],
        )
        self._error_text.pack(fill="x")

        # ── Status bar ────────────────────────────────────────────────────────
        status = tk.Frame(self, bg=PALETTE["bg_toolbar"], height=22)
        status.pack(side="bottom", fill="x")
        status.pack_propagate(False)

        self._status_label = tk.Label(
            status, text="Ready", font=self._label_font,
            bg=PALETTE["bg_toolbar"], fg=PALETTE["fg_dim"], anchor="w",
        )
        self._status_label.pack(side="left", padx=8)

        self._cursor_label = tk.Label(
            status, text="Ln 1, Col 1", font=self._label_font,
            bg=PALETTE["bg_toolbar"], fg=PALETTE["fg_dim"], anchor="e",
        )
        self._cursor_label.pack(side="right", padx=12)

    # ── Editor syntax-highlight tag setup ─────────────────────────────────────

    def _setup_editor_tags(self):
        for tag, color in TAG_COLORS.items():
            self._editor.tag_configure(tag, foreground=color)
        self._editor.tag_configure(
            "tok_keyword",
            foreground=PALETTE["accent"],
            font=tkfont.Font(
                family=self._code_font.cget("family"),
                size=self._code_font.cget("size"),
                weight="bold",
            ),
        )
        # Error squiggle underline
        self._editor.tag_configure(
            "tok_error",
            foreground=PALETTE["red"],
            underline=True,
        )
        # Current line highlight
        self._editor.tag_configure(
            "current_line",
            background="#252540",
        )

    # ── Key bindings ──────────────────────────────────────────────────────────

    def _bind_keys(self):
        self._editor.bind("<KeyRelease>", self._on_key_release)
        self._editor.bind("<ButtonRelease>", self._update_cursor_pos)
        self.bind("<Control-n>", lambda _: self._new_file())
        self.bind("<Control-o>", lambda _: self._open_file_dialog())
        self.bind("<Control-s>", lambda _: self._save_file())
        self.bind("<Control-S>", lambda _: self._save_as())
        self.bind("<F5>",        lambda _: self._run_code())
        self.bind("<F6>",        lambda _: self._check_syntax())
        self.bind("<Control-Return>", lambda _: self._run_code())
        # Tab → 4 spaces
        self._editor.bind("<Tab>", self._insert_tab)

    def _insert_tab(self, event):
        self._editor.insert("insert", "    ")
        return "break"

    # ── Default starter code ──────────────────────────────────────────────────

    def _set_default_content(self):
        starter = (
            'note: Welcome to K++ — Natural English Programming Language.\n'
            'note: Press F5 or click ▶ Run to execute.\n'
            '\n'
            'let name be "World".\n'
            'let greeting be call join with "Hello, ", name.\n'
            'print greeting.\n'
            '\n'
            'note: for-range loop example.\n'
            'for i from 1 to 5 then\n'
            '    print i.\n'
            'end.\n'
        )
        self._editor.delete("1.0", "end")
        self._editor.insert("1.0", starter)
        self._schedule_highlight()

    # ─────────────────────────────────────────────────────────────────────────
    # Event handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_key_release(self, event=None):
        self._modified = True
        self._update_title()
        self._update_cursor_pos()
        self._schedule_highlight()

    def _update_cursor_pos(self, event=None):
        pos = self._editor.index("insert")
        line, col = pos.split(".")
        self._cursor_label.configure(text=f"Ln {line}, Col {int(col)+1}")
        # Highlight current line
        self._editor.tag_remove("current_line", "1.0", "end")
        self._editor.tag_add("current_line", f"{line}.0", f"{line}.end+1c")

    def _schedule_highlight(self):
        """Debounce highlight calls — fire 120 ms after last keypress."""
        if self._highlight_after:
            self.after_cancel(self._highlight_after)
        self._highlight_after = self.after(120, self._apply_syntax_highlight)

    # ─────────────────────────────────────────────────────────────────────────
    # Syntax highlighting
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_syntax_highlight(self):
        """Re-tokenize the entire editor content and apply colour tags."""
        source = self._editor.get("1.0", "end-1c")

        # Remove all existing tags
        for tag in TAG_COLORS:
            self._editor.tag_remove(tag, "1.0", "end")

        # Re-apply comment colouring first (the lexer strips them, so we
        # must detect them with a simple scan before tokenising).
        self._highlight_comments(source)

        # Tokenise and colour
        try:
            tokens = tokenize(source)
        except KppLexError:
            # Partial / invalid source — do nothing
            return

        for tok in tokens:
            if tok.kind == TK.EOF:
                break
            tag = TOKEN_TAG_MAP.get(tok.kind)
            if not tag:
                continue
            # Convert 1-based line + scan column to Tk index.
            # We track character offsets ourselves for accuracy.
            start_idx = f"{tok.line}.0"
            line_start = self._editor.index(start_idx)
            # Build Tk text index: "line.char"
            tstart = f"{tok.line}.{tok.column - 1}"
            tend   = f"{tok.line}.{tok.column - 1 + len(tok.lexeme)}"
            self._editor.tag_add(tag, tstart, tend)

    def _highlight_comments(self, source: str):
        """Highlight note: ... as comments (teal) before main tokenising."""
        lines = source.split("\n")
        for lineno, line in enumerate(lines, start=1):
            idx = line.find("note:")
            if idx == -1:
                # Also handle bare 'note' at start of word
                import re
                m = re.search(r'\bnote\b', line)
                if m:
                    idx = m.start()
                    # check next non-space is ':'
                    rest = line[idx + 4:].lstrip()
                    if not rest.startswith(":"):
                        continue
            if idx != -1:
                tstart = f"{lineno}.{idx}"
                tend   = f"{lineno}.end"
                self._editor.tag_add("tok_comment", tstart, tend)

    # ─────────────────────────────────────────────────────────────────────────
    # Run / check
    # ─────────────────────────────────────────────────────────────────────────

    def _run_code(self):
        if self._running:
            return
        self._clear_output()
        self._clear_error()
        source = self._editor.get("1.0", "end-1c").strip()
        if not source:
            return
        self._set_status("Running…", PALETTE["yellow"])
        self._run_btn.configure(state="disabled", text="⏳  Running…")
        self._running = True
        # Run in background thread so UI stays responsive
        thread = threading.Thread(target=self._run_in_thread,
                                   args=(source,), daemon=True)
        thread.start()

    def _run_in_thread(self, source: str):
        """Execute interpreter in background; update UI on main thread."""
        stdout_buf = io.StringIO()
        error_msg  = None

        try:
            tokens = tokenize(source)
        except KppLexError as e:
            error_msg = str(e)
            self.after(0, self._finish_run, "", error_msg)
            return

        try:
            ast = parse(tokens)
        except KppSyntaxError as e:
            error_msg = str(e)
            self.after(0, self._finish_run, "", error_msg)
            return

        # Redirect input through a GUI-friendly stub:
        # if the program calls 'ask', show a simple dialog.
        evaluator = Evaluator(output=stdout_buf)
        _original_input = evaluator.__class__._exec_input

        def _gui_input(self_ev, node, env):
            # Must schedule dialog on main thread and block until answered.
            result_holder = [None]
            event = threading.Event()

            def ask_dialog():
                import tkinter.simpledialog as sd
                val = sd.askstring(
                    "K++ Program Input",
                    node.prompt,
                    parent=self,
                )
                result_holder[0] = val if val is not None else ""
                event.set()

            self.after(0, ask_dialog)
            event.wait()
            try:
                env.set(node.target, result_holder[0])
            except Exception:
                from environment import KppNameError
                raise KppNameError(f"Variable '{node.target}' is not defined.")

        evaluator.__class__._exec_input = _gui_input

        try:
            evaluator.execute(ast)
        except KppRuntimeError as e:
            error_msg = str(e)
        finally:
            evaluator.__class__._exec_input = _original_input

        self.after(0, self._finish_run, stdout_buf.getvalue(), error_msg)

    def _finish_run(self, output: str, error: Optional[str]):
        self._running = False
        self._run_btn.configure(state="normal", text="▶  Run")

        if output:
            self._append_output(output)

        if error:
            self._show_error(error)
            self._set_status("Error", PALETTE["red"])
        else:
            self._set_status("Finished", PALETTE["green"])

    def _check_syntax(self):
        self._clear_error()
        source = self._editor.get("1.0", "end-1c").strip()
        if not source:
            return
        try:
            tokens = tokenize(source)
            parse(tokens)
            self._err_badge.configure(
                text="  ✓ Syntax OK", fg=PALETTE["green"]
            )
            self._set_status("Syntax OK", PALETTE["green"])
        except (KppLexError, KppSyntaxError) as e:
            self._show_error(str(e))
            self._set_status("Syntax Error", PALETTE["red"])

    # ─────────────────────────────────────────────────────────────────────────
    # Output / Error helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _append_output(self, text: str):
        self._output_text.configure(state="normal")
        self._output_text.insert("end", text)
        self._output_text.see("end")
        self._output_text.configure(state="disabled")

    def _clear_output(self):
        self._output_text.configure(state="normal")
        self._output_text.delete("1.0", "end")
        self._output_text.configure(state="disabled")
        self._set_status("Ready", PALETTE["fg_dim"])

    def _show_error(self, msg: str):
        self._error_text.configure(state="normal")
        self._error_text.delete("1.0", "end")
        self._error_text.insert("1.0", msg)
        self._error_text.configure(state="disabled")
        self._err_badge.configure(
            text="  ✗ Error", fg=PALETTE["red"]
        )
        # Also write to output console in red for visibility
        self._output_text.configure(state="normal")
        self._output_text.tag_configure("err", foreground=PALETTE["red"])
        self._output_text.insert("end", msg + "\n", "err")
        self._output_text.see("end")
        self._output_text.configure(state="disabled")

    def _clear_error(self):
        self._error_text.configure(state="normal")
        self._error_text.delete("1.0", "end")
        self._error_text.configure(state="disabled")
        self._err_badge.configure(text="  No errors", fg=PALETTE["fg_dim"])

    def _set_status(self, text: str, color: str = PALETTE["fg_dim"]):
        self._status_label.configure(text=f"  {text}", fg=color)

    # ─────────────────────────────────────────────────────────────────────────
    # File operations
    # ─────────────────────────────────────────────────────────────────────────

    def _new_file(self):
        if self._modified:
            if not messagebox.askyesno(
                "Unsaved changes",
                "You have unsaved changes. Discard and create new file?",
            ):
                return
        self._editor.delete("1.0", "end")
        self._filepath = None
        self._modified = False
        self._clear_output()
        self._clear_error()
        self._update_title()
        self._set_status("New file")

    def _open_file_dialog(self):
        path = filedialog.askopenfilename(
            title="Open K++ File",
            filetypes=[("K++ files", "*.kpp"), ("All files", "*.*")],
        )
        if path:
            self._open_file(path)

    def _open_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as e:
            messagebox.showerror("Open Error", str(e))
            return
        self._editor.delete("1.0", "end")
        self._editor.insert("1.0", content)
        self._filepath = path
        self._modified = False
        self._update_title()
        self._schedule_highlight()
        self._set_status(f"Opened: {os.path.basename(path)}", PALETTE["accent"])

    def _save_file(self):
        if self._filepath:
            self._write_file(self._filepath)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save K++ File",
            defaultextension=".kpp",
            filetypes=[("K++ files", "*.kpp"), ("All files", "*.*")],
        )
        if path:
            self._filepath = path
            self._write_file(path)

    def _write_file(self, path: str):
        content = self._editor.get("1.0", "end-1c")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        except OSError as e:
            messagebox.showerror("Save Error", str(e))
            return
        self._modified = False
        self._update_title()
        self._set_status(f"Saved: {os.path.basename(path)}", PALETTE["green"])

    def _update_title(self):
        name = os.path.basename(self._filepath) if self._filepath else "Untitled.kpp"
        dirty = " •" if self._modified else ""
        self.title(f"{self._app_title} — {name}{dirty}")
        self._path_label.configure(
            text=f"  {self._filepath or 'Untitled.kpp'}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Window close
    # ─────────────────────────────────────────────────────────────────────────

    def on_close(self):
        if self._modified:
            if not messagebox.askyesno(
                "Unsaved changes",
                "You have unsaved changes. Exit anyway?",
            ):
                return
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    app = KppIDE(initial_file=initial)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
