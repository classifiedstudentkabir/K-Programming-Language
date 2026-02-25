"""
parser.py — Recursive descent parser for K++.

Consumes a token stream produced by lexer.py and builds an AST using
the node classes in ast_nodes.py.  Implements the EBNF grammar from the
K++ specification exactly.
"""

from __future__ import annotations
from typing import List, Optional

from lexer import Token, TK
from ast_nodes import (
    ProgramNode, LiteralNode, IdentifierNode,
    BinaryOpNode, ConditionNode,
    CallExprNode, ListNode, ListAccessNode, ListSizeNode,
    DeclarationNode, AssignmentNode, PrintNode, InputNode,
    IfNode, WhileNode, RepeatNode, ForEachNode, ForRangeNode,
    FunctionDefNode, CallStmtNode, ReturnNode,
    AddToListNode, RemoveFromListNode,
)


# ─────────────────────────────────────────────────────────────────────────────
# Error
# ─────────────────────────────────────────────────────────────────────────────

class KppSyntaxError(Exception):
    def __init__(self, message: str, token: Token) -> None:
        super().__init__(
            f"[K++ SyntaxError] at line {token.line}, token {token.lexeme!r}: {message}"
        )
        self.token = token


# ─────────────────────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────────────────────

class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # ── token stream helpers ─────────────────────────────────────────────────

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]   # EOF

    def _advance(self) -> Token:
        t = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return t

    def _check_keyword(self, *words: str) -> bool:
        t = self._current()
        return t.kind == TK.KEYWORD and t.lexeme in words

    def _check_kind(self, kind: TK) -> bool:
        return self._current().kind == kind

    def _expect_keyword(self, *words: str) -> Token:
        t = self._current()
        if t.kind == TK.KEYWORD and t.lexeme in words:
            return self._advance()
        raise KppSyntaxError(
            f"Expected keyword {words!r} but got {t.lexeme!r}", t
        )

    def _expect_kind(self, kind: TK, msg: str = "") -> Token:
        t = self._current()
        if t.kind == kind:
            return self._advance()
        raise KppSyntaxError(
            msg or f"Expected {kind.name} but got {t.lexeme!r}", t
        )

    def _expect_identifier(self, allow_kw_as_name: bool = False) -> str:
        t = self._current()
        if t.kind == TK.IDENTIFIER:
            self._advance()
            return t.lexeme
        if allow_kw_as_name and t.kind == TK.KEYWORD:
            self._advance()
            return t.lexeme
        raise KppSyntaxError(f"Expected identifier but got {t.lexeme!r}", t)

    def _expect_period(self) -> None:
        self._expect_kind(TK.PERIOD, "Expected '.' to end statement")

    # ── lookahead helpers ────────────────────────────────────────────────────

    def _next_is_keyword(self, *words: str) -> bool:
        t = self._peek(1)
        return t.kind == TK.KEYWORD and t.lexeme in words

    def _is_block_terminator(self) -> bool:
        """True when current token starts an 'else' or 'end' block closer."""
        return self._check_keyword("else", "end")

    # ── public entry point ───────────────────────────────────────────────────

    def parse(self) -> ProgramNode:
        line = self._current().line
        stmts: List = []
        while not self._check_kind(TK.EOF):
            stmts.append(self._parse_statement())
        return ProgramNode(line=line, statements=stmts)

    # ─────────────────────────────────────────────────────────────────────────
    # Statement dispatch
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_statement(self):
        t = self._current()

        if t.kind == TK.KEYWORD:
            kw = t.lexeme

            if kw == "let":
                return self._parse_declaration()
            if kw == "set":
                return self._parse_assignment()
            if kw in ("print", "show"):
                return self._parse_print()
            if kw == "ask":
                return self._parse_input()
            if kw == "if":
                return self._parse_if()
            if kw == "while":
                return self._parse_while()
            if kw == "repeat":
                return self._parse_repeat()
            if kw == "for":
                return self._parse_for()
            if kw == "define":
                return self._parse_function_def()
            if kw == "call":
                return self._parse_call_stmt()
            if kw == "return":
                return self._parse_return()
            if kw == "add":
                return self._parse_add_to_list()
            if kw == "remove":
                return self._parse_remove_from_list()

        raise KppSyntaxError(f"Unexpected token {t.lexeme!r} at start of statement", t)

    # ─────────────────────────────────────────────────────────────────────────
    # Declaration: let IDENTIFIER be EXPRESSION .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_declaration(self):
        line = self._current().line
        self._expect_keyword("let")
        name = self._expect_identifier()
        self._expect_keyword("be")
        expr = self._parse_expression()
        self._expect_period()
        return DeclarationNode(line=line, name=name, value_expr=expr)

    # ─────────────────────────────────────────────────────────────────────────
    # Assignment: set IDENTIFIER to EXPRESSION .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_assignment(self):
        line = self._current().line
        self._expect_keyword("set")
        name = self._expect_identifier()
        self._expect_keyword("to")
        expr = self._parse_expression()
        self._expect_period()
        return AssignmentNode(line=line, name=name, value_expr=expr)

    # ─────────────────────────────────────────────────────────────────────────
    # Print: (print | show) EXPRESSION .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_print(self):
        line = self._current().line
        self._advance()  # consume 'print' or 'show'
        expr = self._parse_expression()
        self._expect_period()
        return PrintNode(line=line, expr=expr)

    # ─────────────────────────────────────────────────────────────────────────
    # Input: ask STRING and save to IDENTIFIER .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_input(self):
        line = self._current().line
        self._expect_keyword("ask")
        t = self._expect_kind(TK.STRING, "Expected string prompt after 'ask'")
        prompt = t.value
        self._expect_keyword("and")
        self._expect_keyword("save")
        self._expect_keyword("to")
        target = self._expect_identifier()
        self._expect_period()
        return InputNode(line=line, prompt=prompt, target=target)

    # ─────────────────────────────────────────────────────────────────────────
    # If: if CONDITION then STMT+ [else STMT+] end .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_if(self):
        line = self._current().line
        self._expect_keyword("if")
        cond = self._parse_condition()
        self._expect_keyword("then")
        then_body = self._parse_body()
        else_body = None
        if self._check_keyword("else"):
            self._advance()  # consume 'else'
            else_body = self._parse_body()
        self._expect_keyword("end")
        self._expect_period()
        return IfNode(line=line, condition=cond, then_body=then_body, else_body=else_body)

    # ─────────────────────────────────────────────────────────────────────────
    # While: while CONDITION then STMT+ end .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_while(self):
        line = self._current().line
        self._expect_keyword("while")
        cond = self._parse_condition()
        self._expect_keyword("then")
        body = self._parse_body()
        self._expect_keyword("end")
        self._expect_period()
        return WhileNode(line=line, condition=cond, body=body)

    # ─────────────────────────────────────────────────────────────────────────
    # Repeat: repeat EXPRESSION times STMT+ end .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_repeat(self):
        line = self._current().line
        self._expect_keyword("repeat")
        # Use _parse_primary here: "times" is both an arith op and the repeat
        # terminator keyword, so a full expression parse would greedily consume
        # "times" as a multiplication operator.  The spec intends a simple
        # count value (literal or variable) before the "times" keyword.
        count = self._parse_primary()
        self._expect_keyword("times")
        body = self._parse_body()
        self._expect_keyword("end")
        self._expect_period()
        return RepeatNode(line=line, count_expr=count, body=body)

    # ─────────────────────────────────────────────────────────────────────────
    # For each: for each IDENTIFIER in IDENTIFIER then STMT+ end .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_for_each(self):
        line = self._current().line
        self._expect_keyword("for")
        self._expect_keyword("each")
        loop_var = self._expect_identifier(allow_kw_as_name=True)
        self._expect_keyword("in")
        list_name = self._expect_identifier()
        self._expect_keyword("then")
        body = self._parse_body()
        self._expect_keyword("end")
        self._expect_period()
        return ForEachNode(line=line, loop_var=loop_var, list_name=list_name, body=body)


    # ─────────────────────────────────────────────────────────────────────────
    # For dispatch: 'for each …' vs 'for VAR from …'
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_for(self):
        """
        Peek at the token after 'for':
          - 'each'  → for-each loop  (existing)
          - anything else → for-range loop  (v1.1)
        """
        # _current() is 'for'; _peek(1) is the next token
        next_tok = self._peek(1)
        if next_tok.kind == TK.KEYWORD and next_tok.lexeme == "each":
            return self._parse_for_each()
        return self._parse_for_range()

    # ─────────────────────────────────────────────────────────────────────────
    # For range: for IDENTIFIER from EXPR to EXPR [step EXPR] then STMT+ end .
    #
    # EBNF (v1.1 extension):
    #   for_range_stmt ::= "for" IDENTIFIER "from" expression
    #                      "to"   expression
    #                      ("step" expression)?
    #                      "then" statement+ "end" "."
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_for_range(self):
        line = self._current().line
        self._expect_keyword("for")
        loop_var = self._expect_identifier()
        self._expect_keyword("from")
        start_expr = self._parse_primary()   # simple primary avoids 'to' ambiguity
        self._expect_keyword("to")
        end_expr = self._parse_primary()     # same reason – 'step' would be consumed
        step_expr = None
        if self._check_keyword("step"):
            self._advance()
            step_expr = self._parse_primary()
        self._expect_keyword("then")
        body = self._parse_body()
        self._expect_keyword("end")
        self._expect_period()
        return ForRangeNode(
            line=line,
            loop_var=loop_var,
            start_expr=start_expr,
            end_expr=end_expr,
            step_expr=step_expr,
            body=body,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Function def: define function NAME [takes PARAM, ...] then STMT+ end .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_function_def(self):
        line = self._current().line
        self._expect_keyword("define")
        self._expect_keyword("function")
        name = self._expect_identifier()
        params: List[str] = []
        if self._check_keyword("takes"):
            self._advance()
            params.append(self._expect_identifier())
            while self._check_kind(TK.COMMA):
                self._advance()
                params.append(self._expect_identifier())
        self._expect_keyword("then")
        body = self._parse_body()
        self._expect_keyword("end")
        self._expect_period()
        return FunctionDefNode(line=line, name=name, params=params, body=body)

    # ─────────────────────────────────────────────────────────────────────────
    # Call statement: call NAME [with EXPR, ...] .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_call_stmt(self):
        line = self._current().line
        self._expect_keyword("call")
        name = self._expect_identifier()
        args: List = []
        if self._check_keyword("with"):
            self._advance()
            args.append(self._parse_expression())
            while self._check_kind(TK.COMMA):
                self._advance()
                args.append(self._parse_expression())
        self._expect_period()
        return CallStmtNode(line=line, name=name, args=args)

    # ─────────────────────────────────────────────────────────────────────────
    # Return: return EXPRESSION .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_return(self):
        line = self._current().line
        self._expect_keyword("return")
        expr = self._parse_expression()
        self._expect_period()
        return ReturnNode(line=line, expr=expr)

    # ─────────────────────────────────────────────────────────────────────────
    # add VALUE to LIST .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_add_to_list(self):
        line = self._current().line
        self._expect_keyword("add")
        value_expr = self._parse_expression()
        self._expect_keyword("to")
        list_name = self._expect_identifier()
        self._expect_period()
        return AddToListNode(line=line, value_expr=value_expr, list_name=list_name)

    # ─────────────────────────────────────────────────────────────────────────
    # remove item N from LIST .
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_remove_from_list(self):
        line = self._current().line
        self._expect_keyword("remove")
        self._expect_keyword("item")
        index_expr = self._parse_primary()
        # 'from' is not in the keyword set so it lexes as IDENTIFIER
        t = self._current()
        if (t.kind in (TK.IDENTIFIER, TK.KEYWORD)) and t.lexeme == "from":
            self._advance()
        else:
            raise KppSyntaxError("Expected 'from' after index in 'remove item'", t)
        list_name = self._expect_identifier()
        self._expect_period()
        return RemoveFromListNode(line=line, index_expr=index_expr, list_name=list_name)

    # ─────────────────────────────────────────────────────────────────────────
    # Body: statement list until else/end
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_body(self) -> List:
        stmts = []
        while not self._is_block_terminator() and not self._check_kind(TK.EOF):
            stmts.append(self._parse_statement())
        if not stmts:
            raise KppSyntaxError("Empty block body", self._current())
        return stmts

    # ─────────────────────────────────────────────────────────────────────────
    # Expression parsing
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_expression(self):
        """
        expression ::= call_expr | list_expr | list_access | list_size | arith_expr | primary

        Strategy: parse a primary (or special form), then check for arithmetic
        operator to form a BinaryOpNode.
        """
        line = self._current().line

        # ── call expr ────────────────────────────────────────────────────────
        if self._check_keyword("call"):
            left = self._parse_call_expr()
        # ── list of ... ──────────────────────────────────────────────────────
        elif self._check_keyword("list"):
            left = self._parse_list_expr()
        # ── item N of LIST ───────────────────────────────────────────────────
        elif self._check_keyword("item"):
            left = self._parse_list_access()
        # ── size of LIST ─────────────────────────────────────────────────────
        elif self._check_keyword("size"):
            left = self._parse_list_size()
        else:
            left = self._parse_primary()

        # ── optional arithmetic operator ─────────────────────────────────────
        op = self._try_arith_op()
        if op is not None:
            right = self._parse_expression()
            return BinaryOpNode(line=line, left=left, operator=op, right=right)

        return left

    def _try_arith_op(self) -> Optional[str]:
        t = self._current()
        if t.kind != TK.KEYWORD:
            return None
        if t.lexeme == "plus":
            self._advance(); return "plus"
        if t.lexeme == "minus":
            self._advance(); return "minus"
        if t.lexeme == "times":
            self._advance(); return "times"
        if t.lexeme == "modulo":
            self._advance(); return "modulo"
        if t.lexeme == "divided":
            # expect 'by' next
            n = self._peek(1)
            if n.kind == TK.KEYWORD and n.lexeme == "by":
                self._advance(); self._advance()
                return "divided by"
        return None

    def _parse_call_expr(self) -> CallExprNode:
        line = self._current().line
        self._expect_keyword("call")
        name = self._expect_identifier()
        args: List = []
        if self._check_keyword("with"):
            self._advance()
            args.append(self._parse_expression())
            while self._check_kind(TK.COMMA):
                self._advance()
                args.append(self._parse_expression())
        return CallExprNode(line=line, name=name, args=args)

    def _parse_list_expr(self) -> ListNode:
        line = self._current().line
        self._expect_keyword("list")
        self._expect_keyword("of")
        # list of nothing → empty list
        if self._current().kind == TK.NULL:
            self._advance()
            # optionally consume trailing period that may appear in declaration
            # (the period is consumed by the parent declaration rule, not here)
            return ListNode(line=line, elements=[])
        elements = [self._parse_expression()]
        while self._check_kind(TK.COMMA):
            self._advance()
            elements.append(self._parse_expression())
        return ListNode(line=line, elements=elements)

    def _parse_list_access(self) -> ListAccessNode:
        line = self._current().line
        self._expect_keyword("item")
        index_expr = self._parse_primary()
        self._expect_keyword("of")
        list_name = self._expect_identifier()
        return ListAccessNode(line=line, index_expr=index_expr, list_name=list_name)

    def _parse_list_size(self) -> ListSizeNode:
        line = self._current().line
        self._expect_keyword("size")
        self._expect_keyword("of")
        list_name = self._expect_identifier()
        return ListSizeNode(line=line, list_name=list_name)

    def _parse_primary(self):
        t = self._current()
        line = t.line

        if t.kind == TK.NUMBER:
            self._advance()
            return LiteralNode(line=line, value=t.value)
        if t.kind == TK.STRING:
            self._advance()
            return LiteralNode(line=line, value=t.value)
        if t.kind == TK.BOOLEAN:
            self._advance()
            return LiteralNode(line=line, value=t.value)
        if t.kind == TK.NULL:
            self._advance()
            return LiteralNode(line=line, value=None)
        if t.kind == TK.IDENTIFIER:
            self._advance()
            return IdentifierNode(line=line, name=t.lexeme)

        raise KppSyntaxError(f"Expected a value but got {t.lexeme!r}", t)

    # ─────────────────────────────────────────────────────────────────────────
    # Condition parsing  (handles AND / OR / NOT / comparisons)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_condition(self):
        """
        condition ::= not condition
                    | expression cmp_op expression
                    | condition and condition
                    | condition or condition

        We parse left-to-right with 'and' > 'or' precedence:
        or_expr = and_expr (or and_expr)*
        and_expr = not_expr (and not_expr)*
        not_expr = 'not' not_expr | comparison
        comparison = expression cmp_op expression
        """
        return self._parse_or_condition()

    def _parse_or_condition(self):
        left = self._parse_and_condition()
        while self._check_keyword("or"):
            line = self._current().line
            self._advance()
            right = self._parse_and_condition()
            left = ConditionNode(line=line, left=left, op="or", right=right)
        return left

    def _parse_and_condition(self):
        left = self._parse_not_condition()
        while self._check_keyword("and"):
            line = self._current().line
            self._advance()
            right = self._parse_not_condition()
            left = ConditionNode(line=line, left=left, op="and", right=right)
        return left

    def _parse_not_condition(self):
        if self._check_keyword("not"):
            line = self._current().line
            self._advance()
            operand = self._parse_not_condition()
            return ConditionNode(line=line, left=operand, op="not", right=None)
        return self._parse_comparison()

    def _parse_comparison(self):
        line = self._current().line
        left = self._parse_expression()
        op = self._parse_cmp_op()
        right = self._parse_expression()
        return ConditionNode(line=line, left=left, op=op, right=right)

    def _parse_cmp_op(self) -> str:
        """
        cmp_op ::= 'is' | 'is not' | 'is greater than' | 'is less than'
                 | 'is greater than or equal to' | 'is less than or equal to'
        """
        t = self._current()
        if not (t.kind == TK.KEYWORD and t.lexeme == "is"):
            raise KppSyntaxError(f"Expected comparison operator ('is ...') but got {t.lexeme!r}", t)
        self._advance()  # consume 'is'

        if self._check_keyword("not"):
            self._advance()
            return "is not"
        if self._check_keyword("greater"):
            self._advance()
            self._expect_keyword("than")
            if self._check_keyword("or"):
                self._advance()
                self._expect_keyword("equal")
                self._expect_keyword("to")
                return "is greater than or equal to"
            return "is greater than"
        if self._check_keyword("less"):
            self._advance()
            self._expect_keyword("than")
            if self._check_keyword("or"):
                self._advance()
                self._expect_keyword("equal")
                self._expect_keyword("to")
                return "is less than or equal to"
            return "is less than"
        if self._check_keyword("equal"):
            # allow bare 'is equal to'
            self._advance()
            self._expect_keyword("to")
            return "is"

        return "is"


# ─────────────────────────────────────────────────────────────────────────────
# Public helper
# ─────────────────────────────────────────────────────────────────────────────

def parse(tokens) -> ProgramNode:
    return Parser(tokens).parse()
