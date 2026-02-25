from __future__ import annotations

import os
import sys


class ErrorCodes:
    SYNTAX = "E001"
    RUNTIME = "E002"
    NAME = "E003"
    TYPE = "E004"
    IMPORT = "E005"


class _Ansi:
    RED = "\033[31m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    RESET = "\033[0m"


def _color_enabled(stream=None) -> bool:
    target = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(target, "isatty") and target.isatty()


def _paint(text: str, color: str, stream=None) -> str:
    if not _color_enabled(stream):
        return text
    return f"{color}{text}{_Ansi.RESET}"


def format_success(message: str, stream=None) -> str:
    return _paint(message, _Ansi.GREEN, stream=stream)


def format_warning(message: str, stream=None) -> str:
    return _paint(message, _Ansi.YELLOW, stream=stream)


def format_error_message(message: str, code: str, kind: str, stream=None) -> str:
    return _paint(f"[{code}] {kind}: {message}", _Ansi.RED, stream=stream)


def format_exception(exc: Exception, stream=None) -> str:
    code = getattr(exc, "code", ErrorCodes.RUNTIME)
    kind = getattr(exc, "kind", exc.__class__.__name__)
    if hasattr(exc, "message"):
        message = str(getattr(exc, "message"))
    else:
        message = str(exc)
    return format_error_message(message, code=code, kind=kind, stream=stream)
