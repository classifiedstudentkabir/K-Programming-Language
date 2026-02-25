"""
main.py — K++ interpreter entry point.

Usage:
    python main.py                   # start REPL
    python main.py program.kpp       # run a .kpp file
    python main.py --version         # print version
    python main.py --check prog.kpp  # syntax check only (parse, no eval)
"""

from __future__ import annotations
import sys
import os

try:
    from .lexer import tokenize, KppLexError
    from .parser import parse, KppSyntaxError
    from .evaluator import Evaluator, KppRuntimeError
    from .version import VERSION
    from .errors import format_exception, format_success, format_warning
except ImportError:
    from lexer import tokenize, KppLexError
    from parser import parse, KppSyntaxError
    from evaluator import Evaluator, KppRuntimeError
    from version import VERSION
    from errors import format_exception, format_success, format_warning


PROMPT  = ">> "
BANNER  = f"""\
+------------------------------------------------------+
|   K++  Interactive Shell  v{VERSION:<5}                     |
|   Natural English Programming Language               |
|   Type a statement ending with a period.             |
|   Type  quit.  to exit.                              |
+------------------------------------------------------+
"""


# ─────────────────────────────────────────────────────────────────────────────
# File runner
# ─────────────────────────────────────────────────────────────────────────────

def run_file(path: str, check_only: bool = False) -> int:
    """Run (or check) a .kpp source file.  Returns exit code 0 or 1."""
    if not os.path.isfile(path):
        print(format_warning(f"File not found: {path}", stream=sys.stderr), file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()

    # ── Lex ──────────────────────────────────────────────────────────────────
    try:
        tokens = tokenize(source)
    except KppLexError as e:
        print(format_exception(e, stream=sys.stderr), file=sys.stderr)
        return 1

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        ast = parse(tokens)
    except KppSyntaxError as e:
        print(format_exception(e, stream=sys.stderr), file=sys.stderr)
        return 1

    if check_only:
        print(format_success(f"[K++ OK] '{path}' — syntax is valid."))
        return 0

    # ── Evaluate ──────────────────────────────────────────────────────────────
    evaluator = Evaluator()
    try:
        evaluator.execute(ast, source_dir=os.path.dirname(os.path.abspath(path)))
    except KppRuntimeError as e:
        print(format_exception(e, stream=sys.stderr), file=sys.stderr)
        return 1

    return 0


# ─────────────────────────────────────────────────────────────────────────────
# REPL
# ─────────────────────────────────────────────────────────────────────────────

def run_repl() -> None:
    """Start an interactive K++ REPL with a persistent global environment."""
    print(BANNER)

    evaluator = Evaluator()
    buf = []          # accumulate multi-line input until a '.' ends a statement

    while True:
        try:
            prompt = PROMPT if not buf else ".. "
            try:
                line = input(prompt)
            except EOFError:
                print("\nGoodbye.")
                break

            # ── quit command ─────────────────────────────────────────────────
            stripped = line.strip()
            if stripped in ("quit.", "quit"):
                print("Goodbye.")
                break

            buf.append(line)
            source = " ".join(buf)

            # Only attempt to parse when the input ends with a period
            # (ignoring trailing whitespace).  This allows multi-line entry.
            if not source.rstrip().endswith("."):
                continue

            # ── Lex ──────────────────────────────────────────────────────────
            try:
                tokens = tokenize(source)
            except KppLexError as e:
                print(format_exception(e))
                buf = []
                continue

            # ── Parse ─────────────────────────────────────────────────────────
            try:
                ast = parse(tokens)
            except KppSyntaxError as e:
                print(format_exception(e))
                buf = []
                continue

            # ── Evaluate each statement individually ─────────────────────────
            had_error = False
            for stmt in ast.statements:
                try:
                    evaluator.execute_one(stmt)
                except KppRuntimeError as e:
                    print(format_exception(e))
                    had_error = True
                    break

            buf = []

        except KeyboardInterrupt:
            print("\n[Interrupted — type quit. to exit]")
            buf = []


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args:
        run_repl()
        return

    if args[0] == "--help":
        print(f"K++ Programming Language v{VERSION}")
        print("")
        print("Usage:")
        print("python main.py program.kpp")
        print("python main.py --check program.kpp")
        print("python main.py --version")
        print("python main.py --help")
        return

    if args[0] == "--version":
        print(f"K++ Programming Language v{VERSION}")
        return

    if args[0] == "--check":
        if len(args) < 2:
            print("Usage: python main.py --check <file.kpp>", file=sys.stderr)
            sys.exit(1)
        sys.exit(run_file(args[1], check_only=True))

    # Default: run a file
    path = args[0]
    sys.exit(run_file(path))


if __name__ == "__main__":
    main()
