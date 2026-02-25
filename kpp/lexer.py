"""
lexer.py — Lexical analyser for K++.

Produces a flat list of Token objects from UTF-8 source text.
Strips whitespace and comments (note: ...).
Raises KppLexError on unterminated string literals.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import List


# ─────────────────────────────────────────────────────────────────────────────
# Token kinds
# ─────────────────────────────────────────────────────────────────────────────

class TK(Enum):
    # Literals
    NUMBER      = auto()
    STRING      = auto()
    BOOLEAN     = auto()
    NULL        = auto()
    # Structure
    COMMA       = auto()
    PERIOD      = auto()
    # All keywords + identifiers share one pass; identifiers are anything
    # not matched as a keyword.
    KEYWORD     = auto()
    IDENTIFIER  = auto()
    EOF         = auto()


# ─────────────────────────────────────────────────────────────────────────────
# Reserved keywords  (order matters for the lexer — longer first where needed)
# ─────────────────────────────────────────────────────────────────────────────

KEYWORDS = {
    "let", "be", "set", "to", "ask", "and", "save", "print", "show",
    "if", "then", "else", "end", "repeat", "times", "while", "is",
    "not", "greater", "less", "than", "equal", "or", "plus", "minus",
    "times", "divided", "by", "modulo", "define", "function", "takes",
    "return", "returns", "call", "with", "nothing", "true", "false",
    "list", "add", "remove", "get", "item", "at", "size", "of",
    "contains", "each", "in", "for", "note",
    # v1.1 — for-range loop
    "from", "step",
    # v1.1.0 — modules and classes
    "import", "class", "new",
}


# ─────────────────────────────────────────────────────────────────────────────
# Token dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Token:
    kind: TK
    lexeme: str
    value: object       # parsed Python value for NUMBER / STRING / BOOLEAN / NULL
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.kind.name}, {self.lexeme!r}, line={self.line})"


# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────

class KppLexError(Exception):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"[K++ LexError] at line {line}, col {column}: {message}")
        self.line = line
        self.column = column


# ─────────────────────────────────────────────────────────────────────────────
# Lexer
# ─────────────────────────────────────────────────────────────────────────────

class Lexer:
    def __init__(self, source: str) -> None:
        self._src = source
        self._pos = 0
        self._line = 1
        self._col = 1
        self._tokens: List[Token] = []

    # ── helpers ──────────────────────────────────────────────────────────────

    def _peek(self, offset: int = 0) -> str:
        idx = self._pos + offset
        return self._src[idx] if idx < len(self._src) else "\0"

    def _advance(self) -> str:
        ch = self._src[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _skip_whitespace(self) -> None:
        while self._pos < len(self._src) and self._peek() in " \t\r\n":
            self._advance()

    def _make_token(self, kind: TK, lexeme: str, value: object) -> Token:
        return Token(kind, lexeme, value, self._line, self._col)

    # ── scanning ─────────────────────────────────────────────────────────────

    def tokenize(self) -> List[Token]:
        while self._pos < len(self._src):
            self._skip_whitespace()
            if self._pos >= len(self._src):
                break

            ch = self._peek()
            start_line = self._line
            start_col = self._col

            # ── period ───────────────────────────────────────────────────────
            if ch == ".":
                self._advance()
                self._tokens.append(Token(TK.PERIOD, ".", None, start_line, start_col))

            # ── comma ────────────────────────────────────────────────────────
            elif ch == ",":
                self._advance()
                self._tokens.append(Token(TK.COMMA, ",", None, start_line, start_col))

            # ── string literal ───────────────────────────────────────────────
            elif ch == '"':
                self._scan_string(start_line, start_col)

            # ── number ───────────────────────────────────────────────────────
            elif ch.isdigit():
                self._scan_number(start_line, start_col)

            # ── word (keyword / identifier / boolean / null) ─────────────────
            elif ch.isalpha() or ch == "_":
                self._scan_word(start_line, start_col)

            else:
                raise KppLexError(f"Unexpected character {ch!r}", start_line, start_col)

        self._tokens.append(Token(TK.EOF, "", None, self._line, self._col))
        return self._tokens

    def _scan_string(self, start_line: int, start_col: int) -> None:
        self._advance()  # consume opening "
        buf: List[str] = []
        while self._pos < len(self._src):
            ch = self._peek()
            if ch == "\n":
                raise KppLexError("Unterminated string literal", start_line, start_col)
            if ch == '"':
                self._advance()  # consume closing "
                value = "".join(buf)
                self._tokens.append(Token(TK.STRING, f'"{value}"', value, start_line, start_col))
                return
            if ch == "\\" and self._peek(1) == '"':
                self._advance()
                self._advance()
                buf.append('"')
            else:
                buf.append(self._advance())
        raise KppLexError("Unterminated string literal (EOF)", start_line, start_col)

    def _scan_number(self, start_line: int, start_col: int) -> None:
        buf: List[str] = []
        while self._peek().isdigit():
            buf.append(self._advance())
        if self._peek() == "." and self._peek(1).isdigit():
            buf.append(self._advance())  # consume '.'
            while self._peek().isdigit():
                buf.append(self._advance())
            lexeme = "".join(buf)
            self._tokens.append(Token(TK.NUMBER, lexeme, float(lexeme), start_line, start_col))
        else:
            lexeme = "".join(buf)
            self._tokens.append(Token(TK.NUMBER, lexeme, int(lexeme), start_line, start_col))

    def _scan_word(self, start_line: int, start_col: int) -> None:
        buf: List[str] = []
        while self._peek().isalnum() or self._peek() == "_":
            buf.append(self._advance())
        word = "".join(buf)

        # ── comment: note: rest of line ──────────────────────────────────────
        if word == "note":
            # consume optional colon and rest of line
            self._skip_whitespace_inline()
            if self._peek() == ":":
                self._advance()
            while self._pos < len(self._src) and self._peek() != "\n":
                self._advance()
            return  # discard comment entirely

        # ── boolean ──────────────────────────────────────────────────────────
        if word == "true":
            self._tokens.append(Token(TK.BOOLEAN, word, True, start_line, start_col))
            return
        if word == "false":
            self._tokens.append(Token(TK.BOOLEAN, word, False, start_line, start_col))
            return

        # ── null ─────────────────────────────────────────────────────────────
        if word == "nothing":
            self._tokens.append(Token(TK.NULL, word, None, start_line, start_col))
            return

        # ── keyword or identifier ────────────────────────────────────────────
        if word in KEYWORDS:
            self._tokens.append(Token(TK.KEYWORD, word, word, start_line, start_col))
        else:
            self._tokens.append(Token(TK.IDENTIFIER, word, word, start_line, start_col))

    def _skip_whitespace_inline(self) -> None:
        while self._peek() in " \t":
            self._advance()


# ─────────────────────────────────────────────────────────────────────────────
# Public helper
# ─────────────────────────────────────────────────────────────────────────────

def tokenize(source: str) -> List[Token]:
    return Lexer(source).tokenize()
