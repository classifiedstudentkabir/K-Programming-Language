# Repository Guidelines

## Project Structure & Module Organization
- Core runtime lives in `kpp/`:
  - `kpp/main.py` (CLI entry), `kpp/lexer.py`, `kpp/parser.py`, `kpp/evaluator.py`
  - `kpp/ast_nodes.py`, `kpp/environment.py`, `kpp/stdlib.py`
  - `kpp/errors.py` (centralized colored/error-code formatting), `kpp/version.py`
- Desktop IDE is `gui.py` (imports from `kpp.*`).
- Windows launch/build scripts: `kpp.bat`, `build_exe.bat`, `kpp_launcher.py`.
- Example programs are in `programs/`.
- Root-level `lexer.py/parser.py/evaluator.py/ast_nodes.py` are legacy copies; prefer `kpp/` for active runtime changes.

## Build, Test, and Development Commands
- `python kpp/main.py --help` — show CLI usage.
- `python kpp/main.py --version` — print current language version.
- `python kpp/main.py <file.kpp>` — run a K++ program.
- `python kpp/main.py --check <file.kpp>` — syntax-check only.
- `python gui.py` — launch GUI IDE.
- `build_exe.bat` — package Windows executable with PyInstaller.

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints where practical, small focused methods.
- Keep parser/evaluator architecture stable; add features via AST + parser + evaluator in parallel.
- Naming:
  - Classes: `PascalCase` (`KppRuntimeError`, `ClassNode`)
  - Functions/variables/files: `snake_case`
  - Error codes: `E001`-style constants in `kpp/errors.py`.

## Testing Guidelines
- No formal test framework is configured yet.
- Validate changes with smoke tests using `programs/*.kpp` plus targeted temporary scripts.
- Minimum checks for grammar/runtime changes:
  - existing `for-range` examples still run
  - `--check` and `--version` still work
  - new syntax parses and executes end-to-end.

## Commit & Pull Request Guidelines
- Commit style in history is release-oriented and imperative, e.g.:
  - `Release v1.1.0 — Professionalized runtime, modules, basic OOP support`
- PRs should include:
  - concise summary of behavior changes
  - affected files (`kpp/parser.py`, `kpp/evaluator.py`, etc.)
  - example K++ snippets for new grammar/features
  - GUI screenshots when UI-visible behavior changes.

## Current v1.1.0 Feature Baseline
- Central version module (`kpp/version.py`), CLI `--help`/`--version`.
- Centralized ANSI error formatter with structured codes (`E001`-`E005`).
- Module import support: `import "file.kpp".` (same-dir, cached, execute once).
- Basic OOP: class definitions, `new`, instance attributes, instance methods, `init`.
