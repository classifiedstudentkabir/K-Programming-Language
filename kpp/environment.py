"""
environment.py — Scope chain (Environment) for K++.

Each Environment holds a dict of name → value bindings and an optional
reference to a parent (enclosing) scope.  This implements the scope rules
from the K++ specification:

  - Global scope: accessible everywhere.
  - Function scope: destroyed on return.
  - Block scope (if/while/repeat/for each): local; can read and set outer vars
    but cannot re-declare them.
"""

from __future__ import annotations
from typing import Any, Optional


class KppNameError(Exception):
    pass


class KppRedeclarationError(Exception):
    pass


class Environment:
    def __init__(self, parent: Optional["Environment"] = None) -> None:
        self._bindings: dict[str, Any] = {}
        self._parent = parent

    # ── declaration ──────────────────────────────────────────────────────────

    def declare(self, name: str, value: Any) -> None:
        """
        Create a new binding in THIS scope.
        Raises KppRedeclarationError if the name is already declared here.
        (It is fine to shadow a name from an outer scope.)
        """
        if name in self._bindings:
            raise KppRedeclarationError(
                f"Variable '{name}' has already been declared in this scope."
            )
        self._bindings[name] = value

    # ── lookup ───────────────────────────────────────────────────────────────

    def get(self, name: str) -> Any:
        """Walk up the scope chain; raise KppNameError if not found."""
        if name in self._bindings:
            return self._bindings[name]
        if self._parent is not None:
            return self._parent.get(name)
        raise KppNameError(f"Variable '{name}' is not defined.")

    # ── assignment ───────────────────────────────────────────────────────────

    def set(self, name: str, value: Any) -> None:
        """
        Assign to an existing binding anywhere in the scope chain.
        Raises KppNameError if the name cannot be found.
        """
        if name in self._bindings:
            self._bindings[name] = value
            return
        if self._parent is not None:
            self._parent.set(name, value)
            return
        raise KppNameError(
            f"Variable '{name}' is not defined. Use 'let {name} be ...' to declare it."
        )

    # ── function binding check ───────────────────────────────────────────────

    def has_local(self, name: str) -> bool:
        """True if the name is declared in THIS scope (not parent)."""
        return name in self._bindings

    def has(self, name: str) -> bool:
        """True if the name is visible anywhere in the chain."""
        if name in self._bindings:
            return True
        if self._parent is not None:
            return self._parent.has(name)
        return False

    # ── child scope factory ──────────────────────────────────────────────────

    def child(self) -> "Environment":
        """Return a new child scope whose parent is this environment."""
        return Environment(parent=self)

    def __repr__(self) -> str:
        names = list(self._bindings.keys())
        return f"<Environment locals={names}>"
