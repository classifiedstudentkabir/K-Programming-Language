"""
ast_nodes.py — Abstract Syntax Tree node definitions for K++.
Every node stores the source line for error reporting.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Node:
    line: int


# ─────────────────────────────────────────────────────────────────────────────
# Program
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProgramNode(Node):
    statements: List[Node] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Literals and identifiers
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LiteralNode(Node):
    value: Any  # int | float | str | bool | None


@dataclass
class IdentifierNode(Node):
    name: str


# ─────────────────────────────────────────────────────────────────────────────
# Expressions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BinaryOpNode(Node):
    left: Node
    operator: str   # 'plus' | 'minus' | 'times' | 'divided by' | 'modulo'
    right: Node


@dataclass
class UnaryOpNode(Node):
    operator: str   # 'not'
    operand: Node


@dataclass
class ConditionNode(Node):
    """
    Wraps a comparison or logical combination.
    op is one of: 'is', 'is not', 'is greater than', 'is less than',
                  'is greater than or equal to', 'is less than or equal to',
                  'and', 'or', 'not'
    For binary comparisons: left, op, right.
    For logical 'and'/'or': left, op, right.
    For 'not': op='not', left=operand, right=None.
    """
    left: Node
    op: str
    right: Optional[Node]


@dataclass
class CallExprNode(Node):
    name: str
    args: List[Node] = field(default_factory=list)


@dataclass
class ListNode(Node):
    elements: List[Node] = field(default_factory=list)


@dataclass
class ListAccessNode(Node):
    index_expr: Node
    list_name: str


@dataclass
class ListSizeNode(Node):
    list_name: str


# ─────────────────────────────────────────────────────────────────────────────
# Statements
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeclarationNode(Node):
    name: str
    value_expr: Node


@dataclass
class AssignmentNode(Node):
    name: str
    value_expr: Node


@dataclass
class PrintNode(Node):
    expr: Node


@dataclass
class InputNode(Node):
    prompt: str
    target: str


@dataclass
class IfNode(Node):
    condition: Node
    then_body: List[Node]
    else_body: Optional[List[Node]]


@dataclass
class WhileNode(Node):
    condition: Node
    body: List[Node]


@dataclass
class RepeatNode(Node):
    count_expr: Node
    body: List[Node]


@dataclass
class ForEachNode(Node):
    loop_var: str
    list_name: str
    body: List[Node]


@dataclass
class FunctionDefNode(Node):
    name: str
    params: List[str]
    body: List[Node]


@dataclass
class CallStmtNode(Node):
    name: str
    args: List[Node] = field(default_factory=list)


@dataclass
class ReturnNode(Node):
    expr: Node


@dataclass
class AddToListNode(Node):
    value_expr: Node
    list_name: str


@dataclass
class RemoveFromListNode(Node):
    index_expr: Node
    list_name: str


# ─────────────────────────────────────────────────────────────────────────────
# For range loop  (v1.1 extension)
#
# Syntax:
#   for VAR from EXPR to EXPR [step EXPR] then STMTS end.
#
# step_expr is None when omitted; direction is auto-inferred (+1 or -1).
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ForRangeNode(Node):
    loop_var:   str
    start_expr: Node
    end_expr:   Node
    step_expr:  Optional[Node]         # None → auto (+1 or -1)
    body:       List[Node] = field(default_factory=list)
