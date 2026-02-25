"""
stdlib.py — K++ standard library.

All functions are registered into an Environment at interpreter startup.
They are plain Python callables wrapped in KppBuiltin objects so the
evaluator can treat them uniformly with user-defined functions.
"""

from __future__ import annotations
import math
from typing import Any, Callable, List


# ─────────────────────────────────────────────────────────────────────────────
# Sentinel wrapper so the evaluator can distinguish builtins from user funcs
# ─────────────────────────────────────────────────────────────────────────────

class KppBuiltin:
    def __init__(self, name: str, fn: Callable, arity: int | None = None) -> None:
        """
        name  — display name
        fn    — Python callable that accepts (args: list) -> Any
        arity — exact expected argument count, or None for variadic
        """
        self.name = name
        self.fn = fn
        self.arity = arity

    def call(self, args: List[Any], line: int) -> Any:
        if self.arity is not None and len(args) != self.arity:
            try:
                from .evaluator import KppRuntimeError
            except ImportError:
                from evaluator import KppRuntimeError
            raise KppRuntimeError(
                f"Built-in '{self.name}' expects {self.arity} argument(s), "
                f"got {len(args)}.",
                line,
            )
        return self.fn(args)

    def __repr__(self) -> str:
        return f"<builtin {self.name}>"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _assert_number(val: Any, name: str, func: str) -> None:
    if not isinstance(val, (int, float)):
        raise TypeError(f"'{func}': argument '{name}' must be a number, got {type(val).__name__}.")

def _assert_string(val: Any, name: str, func: str) -> None:
    if not isinstance(val, str):
        raise TypeError(f"'{func}': argument '{name}' must be text, got {type(val).__name__}.")

def _assert_list(val: Any, name: str, func: str) -> None:
    if not isinstance(val, list):
        raise TypeError(f"'{func}': argument '{name}' must be a list, got {type(val).__name__}.")


# ─────────────────────────────────────────────────────────────────────────────
# Type conversion
# ─────────────────────────────────────────────────────────────────────────────

def _to_number(args):
    val = args[0]
    if isinstance(val, bool):
        raise ValueError("to_number: booleans cannot be converted to numbers.")
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            raise ValueError(f"to_number: cannot convert text '{val}' to a number.")
    raise ValueError(f"to_number: cannot convert {type(val).__name__} to a number.")


def _kpp_value_to_str(val: Any) -> str:
    if val is None:
        return "nothing"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, list):
        return "[" + ", ".join(_kpp_value_to_str(e) for e in val) + "]"
    return str(val)


def _to_text(args):
    return _kpp_value_to_str(args[0])


def _to_boolean(args):
    val = args[0]
    if val is None or val is False:
        return False
    return True


def _is_number(args):
    return isinstance(args[0], (int, float)) and not isinstance(args[0], bool)


def _is_text(args):
    return isinstance(args[0], str)


def _is_list(args):
    return isinstance(args[0], list)


def _is_nothing(args):
    return args[0] is None


# ─────────────────────────────────────────────────────────────────────────────
# String operations
# ─────────────────────────────────────────────────────────────────────────────

def _length_of(args):
    _assert_string(args[0], "text", "length of")
    return len(args[0])


def _join(args):
    _assert_string(args[0], "text1", "join")
    _assert_string(args[1], "text2", "join")
    return args[0] + args[1]


def _uppercase_of(args):
    _assert_string(args[0], "text", "uppercase of")
    return args[0].upper()


def _lowercase_of(args):
    _assert_string(args[0], "text", "lowercase of")
    return args[0].lower()


def _starts_with(args):
    _assert_string(args[0], "text", "starts with")
    _assert_string(args[1], "prefix", "starts with")
    return args[0].startswith(args[1])


def _ends_with(args):
    _assert_string(args[0], "text", "ends with")
    _assert_string(args[1], "suffix", "ends with")
    return args[0].endswith(args[1])


def _contains_text(args):
    _assert_string(args[0], "text", "contains text")
    _assert_string(args[1], "fragment", "contains text")
    return args[1] in args[0]


def _split(args):
    _assert_string(args[0], "text", "split")
    _assert_string(args[1], "separator", "split")
    return args[0].split(args[1])


def _trim(args):
    _assert_string(args[0], "text", "trim")
    return args[0].strip()


# ─────────────────────────────────────────────────────────────────────────────
# Math operations
# ─────────────────────────────────────────────────────────────────────────────

def _floor_of(args):
    _assert_number(args[0], "number", "floor of")
    return int(math.floor(args[0]))


def _ceiling_of(args):
    _assert_number(args[0], "number", "ceiling of")
    return int(math.ceil(args[0]))


def _round_of(args):
    _assert_number(args[0], "number", "round of")
    return int(round(args[0]))


def _absolute_of(args):
    _assert_number(args[0], "number", "absolute of")
    return abs(args[0])


def _power(args):
    _assert_number(args[0], "base", "power")
    _assert_number(args[1], "exp", "power")
    return args[0] ** args[1]


def _square_root_of(args):
    _assert_number(args[0], "number", "square root of")
    if args[0] < 0:
        raise ValueError("square root of: cannot take square root of a negative number.")
    return math.sqrt(args[0])


def _max_of(args):
    _assert_number(args[0], "a", "max of")
    _assert_number(args[1], "b", "max of")
    return max(args[0], args[1])


def _min_of(args):
    _assert_number(args[0], "a", "min of")
    _assert_number(args[1], "b", "min of")
    return min(args[0], args[1])


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

STDLIB: dict[str, KppBuiltin] = {
    # Type conversion
    "to_number":       KppBuiltin("to_number",       _to_number,        1),
    "to_text":         KppBuiltin("to_text",          _to_text,          1),
    "to_boolean":      KppBuiltin("to_boolean",       _to_boolean,       1),
    "is_number":       KppBuiltin("is_number",        _is_number,        1),
    "is_text":         KppBuiltin("is_text",          _is_text,          1),
    "is_list":         KppBuiltin("is_list",          _is_list,          1),
    "is_nothing":      KppBuiltin("is_nothing",       _is_nothing,       1),
    # String
    "length_of":       KppBuiltin("length of",        _length_of,        1),
    "join":            KppBuiltin("join",              _join,             2),
    "uppercase_of":    KppBuiltin("uppercase of",     _uppercase_of,     1),
    "lowercase_of":    KppBuiltin("lowercase of",     _lowercase_of,     1),
    "starts_with":     KppBuiltin("starts with",      _starts_with,      2),
    "ends_with":       KppBuiltin("ends with",        _ends_with,        2),
    "contains_text":   KppBuiltin("contains text",    _contains_text,    2),
    "split":           KppBuiltin("split",             _split,            2),
    "trim":            KppBuiltin("trim",              _trim,             1),
    # Math
    "floor_of":        KppBuiltin("floor of",         _floor_of,         1),
    "ceiling_of":      KppBuiltin("ceiling of",       _ceiling_of,       1),
    "round_of":        KppBuiltin("round of",         _round_of,         1),
    "absolute_of":     KppBuiltin("absolute of",      _absolute_of,      1),
    "power":           KppBuiltin("power",             _power,            2),
    "square_root_of":  KppBuiltin("square root of",   _square_root_of,   1),
    "max_of":          KppBuiltin("max of",            _max_of,           2),
    "min_of":          KppBuiltin("min of",            _min_of,           2),
}


def load_into(env) -> None:
    """Declare all standard library functions into the given Environment."""
    for name, builtin in STDLIB.items():
        env.declare(name, builtin)
