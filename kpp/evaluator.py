"""
evaluator.py — Tree-walk evaluator for K++.

Walks the AST produced by parser.py, evaluates every node, and manages
runtime state through the Environment scope chain.
"""

from __future__ import annotations
import sys
import os
from typing import Any, List

try:
    from .ast_nodes import (
        ProgramNode, LiteralNode, IdentifierNode,
        BinaryOpNode, ConditionNode,
        CallExprNode, ListNode, ListAccessNode, ListSizeNode, NewInstanceNode, AttrAccessNode,
        DeclarationNode, AssignmentNode, PrintNode, InputNode,
        IfNode, WhileNode, RepeatNode, ForEachNode, ForRangeNode,
        FunctionDefNode, ClassNode, ImportNode, SetAttrNode, CallStmtNode, ReturnNode,
        AddToListNode, RemoveFromListNode,
    )
    from .environment import Environment, KppNameError, KppRedeclarationError
    from .stdlib import KppBuiltin, load_into, _kpp_value_to_str
    from .errors import ErrorCodes
except ImportError:
    from ast_nodes import (
        ProgramNode, LiteralNode, IdentifierNode,
        BinaryOpNode, ConditionNode,
        CallExprNode, ListNode, ListAccessNode, ListSizeNode, NewInstanceNode, AttrAccessNode,
        DeclarationNode, AssignmentNode, PrintNode, InputNode,
        IfNode, WhileNode, RepeatNode, ForEachNode, ForRangeNode,
        FunctionDefNode, ClassNode, ImportNode, SetAttrNode, CallStmtNode, ReturnNode,
        AddToListNode, RemoveFromListNode,
    )
    from environment import Environment, KppNameError, KppRedeclarationError
    from stdlib import KppBuiltin, load_into, _kpp_value_to_str
    from errors import ErrorCodes


# ─────────────────────────────────────────────────────────────────────────────
# Runtime errors
# ─────────────────────────────────────────────────────────────────────────────

class KppRuntimeError(Exception):
    code = ErrorCodes.RUNTIME
    kind = "Runtime Error"

    def __init__(self, message: str, line: int, hint: str = "") -> None:
        self.message = message
        self.line = line
        self.hint = hint
        super().__init__(self._format())

    def _format(self) -> str:
        msg = f"at line {self.line}: {self.message}"
        if self.hint:
            msg += f"\n  Hint: {self.hint}"
        return msg


class KppTypeError(KppRuntimeError):
    code = ErrorCodes.TYPE
    kind = "Type Error"

class KppNameRuntimeError(KppRuntimeError):
    code = ErrorCodes.NAME
    kind = "Name Error"

class KppImportError(KppRuntimeError):
    code = ErrorCodes.IMPORT
    kind = "Import Error"

class KppNullError(KppRuntimeError):
    pass

class KppIndexError(KppRuntimeError):
    pass

class KppMathError(KppRuntimeError):
    pass

class KppValueError(KppRuntimeError):
    pass

class KppRecursionError(KppRuntimeError):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Internal signals (not errors — used for control flow)
# ─────────────────────────────────────────────────────────────────────────────

class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


# ─────────────────────────────────────────────────────────────────────────────
# User-defined function object
# ─────────────────────────────────────────────────────────────────────────────

class KppFunction:
    def __init__(self, name: str, params: List[str], body: list, closure: Environment) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure  # captured scope at definition time

    def __repr__(self) -> str:
        return f"<function {self.name}>"


class KppClass:
    def __init__(self, name: str, methods: dict[str, KppFunction]) -> None:
        self.name = name
        self.methods = methods

    def __repr__(self) -> str:
        return f"<class {self.name}>"


class KppInstance:
    def __init__(self, klass: KppClass) -> None:
        self.klass = klass
        self.fields: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"<{self.klass.name} instance>"


# ─────────────────────────────────────────────────────────────────────────────
# Evaluator
# ─────────────────────────────────────────────────────────────────────────────

MAX_CALL_DEPTH = 1000

class Evaluator:
    def __init__(self, output=None) -> None:
        """
        output: file-like object for print/show.  Defaults to sys.stdout.
                Useful for tests.
        """
        self._output = output or sys.stdout
        self._call_depth = 0
        self._module_cache: set[str] = set()
        self._module_dir_stack: list[str] = [os.getcwd()]

        # Build the global environment with stdlib
        self.global_env = Environment()
        load_into(self.global_env)

    # ── public API ────────────────────────────────────────────────────────────

    def execute(self, node: ProgramNode, source_dir: str | None = None) -> None:
        """Execute a full program in the global environment."""
        if source_dir:
            self._module_dir_stack.append(source_dir)
        try:
            self._exec_stmts(node.statements, self.global_env)
        finally:
            if source_dir:
                self._module_dir_stack.pop()

    def execute_one(self, node) -> Any:
        """Execute a single statement node, returning any display value."""
        return self._exec(node, self.global_env)

    # ── statement dispatch ───────────────────────────────────────────────────

    def _exec_stmts(self, stmts: list, env: Environment) -> None:
        for stmt in stmts:
            self._exec(stmt, env)

    def _exec(self, node, env: Environment) -> Any:
        kind = type(node).__name__

        if kind == "DeclarationNode":   return self._exec_declaration(node, env)
        if kind == "AssignmentNode":    return self._exec_assignment(node, env)
        if kind == "PrintNode":         return self._exec_print(node, env)
        if kind == "InputNode":         return self._exec_input(node, env)
        if kind == "IfNode":            return self._exec_if(node, env)
        if kind == "WhileNode":         return self._exec_while(node, env)
        if kind == "RepeatNode":        return self._exec_repeat(node, env)
        if kind == "ForEachNode":       return self._exec_for_each(node, env)
        if kind == "ForRangeNode":      return self._exec_for_range(node, env)
        if kind == "FunctionDefNode":   return self._exec_function_def(node, env)
        if kind == "ClassNode":         return self._exec_class_def(node, env)
        if kind == "ImportNode":        return self._exec_import(node, env)
        if kind == "SetAttrNode":       return self._exec_set_attr(node, env)
        if kind == "CallStmtNode":      return self._exec_call_stmt(node, env)
        if kind == "ReturnNode":        return self._exec_return(node, env)
        if kind == "AddToListNode":     return self._exec_add_to_list(node, env)
        if kind == "RemoveFromListNode": return self._exec_remove_from_list(node, env)

        raise KppRuntimeError(f"Unknown statement node: {kind}", getattr(node, "line", 0))

    # ── declaration ──────────────────────────────────────────────────────────

    def _exec_declaration(self, node: DeclarationNode, env: Environment) -> None:
        value = self._eval(node.value_expr, env)
        try:
            env.declare(node.name, value)
        except KppRedeclarationError as e:
            raise KppRuntimeError(str(e), node.line,
                hint=f"Use 'set {node.name} to ...' to reassign an existing variable.")

    # ── assignment ───────────────────────────────────────────────────────────

    def _exec_assignment(self, node: AssignmentNode, env: Environment) -> None:
        value = self._eval(node.value_expr, env)
        try:
            env.set(node.name, value)
        except KppNameError:
            raise KppNameRuntimeError(
                f"Variable '{node.name}' is not defined. Cannot assign to it.",
                node.line,
                hint=f"Use 'let {node.name} be ...' to declare it first.",
            )

    # ── print / show ─────────────────────────────────────────────────────────

    def _exec_print(self, node: PrintNode, env: Environment) -> None:
        value = self._eval(node.expr, env)
        print(_kpp_value_to_str(value), file=self._output)

    # ── input ────────────────────────────────────────────────────────────────

    def _exec_input(self, node: InputNode, env: Environment) -> None:
        try:
            raw = input(node.prompt + " ")
        except EOFError:
            raw = ""
        try:
            env.set(node.target, raw)
        except KppNameError:
            raise KppNameRuntimeError(
                f"Variable '{node.target}' is not defined. Declare it before using 'ask'.",
                node.line,
                hint=f"Add 'let {node.target} be nothing.' before this ask statement.",
            )

    # ── if ───────────────────────────────────────────────────────────────────

    def _exec_if(self, node: IfNode, env: Environment) -> None:
        cond = self._eval_condition(node.condition, env)
        block_env = env.child()
        if cond:
            self._exec_stmts(node.then_body, block_env)
        elif node.else_body is not None:
            else_env = env.child()
            self._exec_stmts(node.else_body, else_env)

    # ── while ────────────────────────────────────────────────────────────────

    def _exec_while(self, node: WhileNode, env: Environment) -> None:
        while self._eval_condition(node.condition, env):
            loop_env = env.child()
            self._exec_stmts(node.body, loop_env)

    # ── repeat ───────────────────────────────────────────────────────────────

    def _exec_repeat(self, node: RepeatNode, env: Environment) -> None:
        count_val = self._eval(node.count_expr, env)
        if not isinstance(count_val, (int, float)):
            raise KppTypeError(
                f"'repeat' count must be a number, got {type(count_val).__name__}.",
                node.line,
            )
        count = int(count_val)
        for _ in range(count):
            loop_env = env.child()
            self._exec_stmts(node.body, loop_env)

    # ── for each ─────────────────────────────────────────────────────────────

    def _exec_for_each(self, node: ForEachNode, env: Environment) -> None:
        try:
            collection = env.get(node.list_name)
        except KppNameError:
            raise KppNameRuntimeError(
                f"List '{node.list_name}' is not defined.", node.line
            )
        if not isinstance(collection, list):
            raise KppTypeError(
                f"'{node.list_name}' is not a list, cannot iterate over it.",
                node.line,
            )
        for element in collection:
            loop_env = env.child()
            loop_env.declare(node.loop_var, element)
            self._exec_stmts(node.body, loop_env)


    # ── for range (v1.1) ─────────────────────────────────────────────────────

    def _exec_for_range(self, node: ForRangeNode, env) -> None:
        """
        Execute:  for VAR from START to END [step STEP] then … end.

        Rules
        ─────
        • START, END, STEP must all evaluate to numbers.
        • If STEP is omitted it defaults to +1 when START <= END,
          and to -1 when START > END.
        • If STEP is provided it must be non-zero; its sign determines
          direction regardless of START/END ordering.
        • VAR is scoped to the loop body (block scope per spec).
        • Inclusive range: the loop runs while the counter has not yet
          passed END in the direction of STEP.
        """
        start = self._eval(node.start_expr, env)
        end   = self._eval(node.end_expr,   env)

        if not isinstance(start, (int, float)) or isinstance(start, bool):
            raise KppTypeError(
                f"for-range 'from' value must be a number, got {_type_name(start)}.",
                node.line,
            )
        if not isinstance(end, (int, float)) or isinstance(end, bool):
            raise KppTypeError(
                f"for-range 'to' value must be a number, got {_type_name(end)}.",
                node.line,
            )

        if node.step_expr is not None:
            step = self._eval(node.step_expr, env)
            if not isinstance(step, (int, float)) or isinstance(step, bool):
                raise KppTypeError(
                    f"for-range 'step' value must be a number, got {_type_name(step)}.",
                    node.line,
                )
            if step == 0:
                raise KppMathError(
                    "for-range 'step' must not be zero (infinite loop).",
                    node.line,
                )
        else:
            step = 1 if start <= end else -1

        # normalise to float/int for clean iteration
        counter = start
        ascending = step > 0

        while (ascending and counter <= end) or (not ascending and counter >= end):
            loop_env = env.child()
            # Preserve integer type when all values are integral
            display = int(counter) if isinstance(counter, float) and counter == int(counter) else counter
            loop_env.declare(node.loop_var, display)
            try:
                self._exec_stmts(node.body, loop_env)
            except _ReturnSignal:
                raise   # propagate returns out of functions
            counter += step

    # ── function definition ──────────────────────────────────────────────────

    def _exec_function_def(self, node: FunctionDefNode, env: Environment) -> None:
        fn = KppFunction(
            name=node.name,
            params=node.params,
            body=node.body,
            closure=env,
        )
        try:
            env.declare(node.name, fn)
        except KppRedeclarationError:
            raise KppRuntimeError(
                f"Function '{node.name}' is already defined.", node.line
            )

    def _exec_class_def(self, node: ClassNode, env: Environment) -> None:
        methods: dict[str, KppFunction] = {}
        for m in node.methods:
            methods[m.name] = KppFunction(
                name=m.name,
                params=m.params,
                body=m.body,
                closure=env,
            )
        klass = KppClass(name=node.name, methods=methods)
        try:
            env.declare(node.name, klass)
        except KppRedeclarationError:
            raise KppRuntimeError(f"Class '{node.name}' is already defined.", node.line)

    def _exec_import(self, node: ImportNode, env: Environment) -> None:
        try:
            from .lexer import tokenize, KppLexError
            from .parser import parse, KppSyntaxError
        except ImportError:
            from lexer import tokenize, KppLexError
            from parser import parse, KppSyntaxError

        if not node.module_path:
            raise KppImportError("Module path must not be empty.", node.line)

        base_dir = self._module_dir_stack[-1] if self._module_dir_stack else os.getcwd()
        module_path = node.module_path
        if not os.path.isabs(module_path):
            module_path = os.path.join(base_dir, module_path)
        module_path = os.path.abspath(module_path)

        if module_path in self._module_cache:
            return
        if not os.path.isfile(module_path):
            raise KppImportError(f"Module not found: {node.module_path}", node.line)

        try:
            with open(module_path, "r", encoding="utf-8") as fh:
                source = fh.read()
        except OSError as e:
            raise KppImportError(f"Could not read module '{node.module_path}': {e}", node.line)

        try:
            tokens = tokenize(source)
            ast = parse(tokens)
        except (KppLexError, KppSyntaxError) as e:
            raise KppImportError(
                f"Failed to import '{node.module_path}': {e}",
                node.line,
            )

        self._module_cache.add(module_path)
        self._module_dir_stack.append(os.path.dirname(module_path))
        try:
            self._exec_stmts(ast.statements, self.global_env)
        finally:
            self._module_dir_stack.pop()

    def _exec_set_attr(self, node: SetAttrNode, env: Environment) -> None:
        value = self._eval(node.value_expr, env)
        target = self._eval_identifier(IdentifierNode(line=node.line, name=node.object_name), env)
        if not isinstance(target, KppInstance):
            raise KppTypeError(
                f"'{node.object_name}' is not an object instance.",
                node.line,
            )
        target.fields[node.attr_name] = value

    # ── call statement ───────────────────────────────────────────────────────

    def _exec_call_stmt(self, node: CallStmtNode, env: Environment) -> None:
        args = [self._eval(a, env) for a in node.args]
        self._call_function(node.name, args, env, node.line, target_name=node.target_name)

    # ── return ───────────────────────────────────────────────────────────────

    def _exec_return(self, node: ReturnNode, env: Environment) -> None:
        value = self._eval(node.expr, env)
        raise _ReturnSignal(value)

    # ── add to list ──────────────────────────────────────────────────────────

    def _exec_add_to_list(self, node: AddToListNode, env: Environment) -> None:
        value = self._eval(node.value_expr, env)
        try:
            lst = env.get(node.list_name)
        except KppNameError:
            raise KppNameRuntimeError(f"List '{node.list_name}' is not defined.", node.line)
        if not isinstance(lst, list):
            raise KppTypeError(f"'{node.list_name}' is not a list.", node.line)
        lst.append(value)

    # ── remove from list ─────────────────────────────────────────────────────

    def _exec_remove_from_list(self, node: RemoveFromListNode, env: Environment) -> None:
        index = self._eval(node.index_expr, env)
        if not isinstance(index, (int, float)):
            raise KppTypeError("List index must be a number.", node.line)
        idx = int(index)
        try:
            lst = env.get(node.list_name)
        except KppNameError:
            raise KppNameRuntimeError(f"List '{node.list_name}' is not defined.", node.line)
        if not isinstance(lst, list):
            raise KppTypeError(f"'{node.list_name}' is not a list.", node.line)
        if idx < 0 or idx >= len(lst):
            raise KppIndexError(
                f"Index {idx} is out of bounds for list '{node.list_name}' of size {len(lst)}.",
                node.line,
            )
        lst.pop(idx)

    # ─────────────────────────────────────────────────────────────────────────
    # Expression evaluation
    # ─────────────────────────────────────────────────────────────────────────

    def _eval(self, node, env: Environment) -> Any:
        kind = type(node).__name__

        if kind == "LiteralNode":       return node.value
        if kind == "IdentifierNode":    return self._eval_identifier(node, env)
        if kind == "BinaryOpNode":      return self._eval_binary(node, env)
        if kind == "ConditionNode":     return self._eval_condition(node, env)
        if kind == "CallExprNode":      return self._eval_call_expr(node, env)
        if kind == "ListNode":          return self._eval_list(node, env)
        if kind == "ListAccessNode":    return self._eval_list_access(node, env)
        if kind == "ListSizeNode":      return self._eval_list_size(node, env)
        if kind == "NewInstanceNode":   return self._eval_new_instance(node, env)
        if kind == "AttrAccessNode":    return self._eval_attr_access(node, env)

        raise KppRuntimeError(f"Unknown expression node: {kind}", getattr(node, "line", 0))

    def _eval_identifier(self, node: IdentifierNode, env: Environment) -> Any:
        try:
            return env.get(node.name)
        except KppNameError:
            raise KppNameRuntimeError(
                f"Variable '{node.name}' is not defined.",
                node.line,
                hint=f"Use 'let {node.name} be ...' to declare it.",
            )

    # ── arithmetic ───────────────────────────────────────────────────────────

    def _eval_binary(self, node: BinaryOpNode, env: Environment) -> Any:
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        op = node.operator
        line = node.line

        # Guard null
        if left is None or right is None:
            raise KppNullError(
                f"Cannot apply '{op}' to 'nothing'.", line,
                hint="Check that variables are initialised before arithmetic."
            )
        # Guard booleans
        if isinstance(left, bool) or isinstance(right, bool):
            raise KppTypeError(
                f"Cannot apply '{op}' to boolean values.", line,
                hint="Booleans cannot be used in arithmetic."
            )

        if op == "plus":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                result = left + right
                # preserve int when both operands are int
                return int(result) if isinstance(left, int) and isinstance(right, int) else result
            raise KppTypeError(
                f"Cannot apply 'plus' to {_type_name(left)} and {_type_name(right)}.", line,
                hint="Both sides of 'plus' must be the same type (both numbers or both text).",
            )

        # Numeric-only ops
        _assert_numeric(left, op, line)
        _assert_numeric(right, op, line)

        if op == "minus":
            result = left - right
            return int(result) if isinstance(left, int) and isinstance(right, int) else result
        if op == "times":
            result = left * right
            return int(result) if isinstance(left, int) and isinstance(right, int) else result
        if op == "divided by":
            if right == 0:
                raise KppMathError("Division by zero.", line)
            return left / right
        if op == "modulo":
            if right == 0:
                raise KppMathError("Modulo by zero.", line)
            result = left % right
            return int(result) if isinstance(left, int) and isinstance(right, int) else result

        raise KppRuntimeError(f"Unknown arithmetic operator '{op}'.", line)

    # ── conditions ───────────────────────────────────────────────────────────

    def _eval_condition(self, node, env: Environment) -> bool:
        kind = type(node).__name__

        # A bare boolean literal / identifier that holds bool is valid
        if kind == "LiteralNode":
            v = node.value
            if isinstance(v, bool):
                return v
            raise KppTypeError("Condition must be a boolean expression.", node.line)

        if kind == "IdentifierNode":
            v = self._eval(node, env)
            if isinstance(v, bool):
                return v
            raise KppTypeError(
                f"Variable '{node.name}' is not boolean, cannot use as condition.", node.line
            )

        if kind != "ConditionNode":
            raise KppTypeError("Expected a condition.", getattr(node, "line", 0))

        op = node.op
        line = node.line

        if op == "not":
            return not self._eval_condition(node.left, env)

        if op == "and":
            return self._eval_condition(node.left, env) and self._eval_condition(node.right, env)

        if op == "or":
            return self._eval_condition(node.left, env) or self._eval_condition(node.right, env)

        # comparison operators
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)

        if op == "is":
            return _kpp_equal(left, right)
        if op == "is not":
            return not _kpp_equal(left, right)

        # Ordered comparisons require numbers
        if op in ("is greater than", "is less than",
                  "is greater than or equal to", "is less than or equal to"):
            if left is None or right is None:
                raise KppNullError("Cannot compare 'nothing' with an ordered comparison.", line)
            _assert_numeric(left, op, line)
            _assert_numeric(right, op, line)
            if op == "is greater than":              return left > right
            if op == "is less than":                 return left < right
            if op == "is greater than or equal to":  return left >= right
            if op == "is less than or equal to":     return left <= right

        raise KppRuntimeError(f"Unknown comparison operator '{op}'.", line)

    # ── call expression ──────────────────────────────────────────────────────

    def _eval_call_expr(self, node: CallExprNode, env: Environment) -> Any:
        args = [self._eval(a, env) for a in node.args]
        return self._call_function(
            node.name,
            args,
            env,
            node.line,
            target_name=node.target_name,
        )

    def _call_function(
        self,
        name: str,
        args: List[Any],
        env: Environment,
        line: int,
        target_name: str | None = None,
    ) -> Any:
        if target_name:
            try:
                target = env.get(target_name)
            except KppNameError:
                raise KppNameRuntimeError(f"Object '{target_name}' is not defined.", line)
            if not isinstance(target, KppInstance):
                raise KppTypeError(f"'{target_name}' is not an object instance.", line)
            return self._call_method(target, name, args, line)

        # Look up in the entire scope chain
        try:
            fn = env.get(name)
        except KppNameError:
            raise KppNameRuntimeError(
                f"Function '{name}' is not defined.", line,
                hint="Check the function name and make sure it was defined with 'define function'.",
            )

        # Built-in
        if isinstance(fn, KppBuiltin):
            try:
                return fn.call(args, line)
            except TypeError as e:
                raise KppTypeError(str(e), line)
            except ValueError as e:
                raise KppValueError(str(e), line)

        # User-defined
        if isinstance(fn, KppFunction):
            if len(args) != len(fn.params):
                raise KppRuntimeError(
                    f"Function '{name}' expects {len(fn.params)} argument(s), got {len(args)}.",
                    line,
                )
            self._call_depth += 1
            if self._call_depth > MAX_CALL_DEPTH:
                self._call_depth -= 1
                raise KppRecursionError(
                    f"Maximum recursion depth ({MAX_CALL_DEPTH}) exceeded in '{name}'.", line,
                    hint="Consider rewriting the function iteratively."
                )
            fn_env = fn.closure.child()
            for param, arg in zip(fn.params, args):
                fn_env.declare(param, arg)
            try:
                self._exec_stmts(fn.body, fn_env)
                return None  # implicit return nothing
            except _ReturnSignal as ret:
                return ret.value
            finally:
                self._call_depth -= 1

        raise KppTypeError(f"'{name}' is not callable.", line)

    def _call_method(self, instance: KppInstance, name: str, args: List[Any], line: int) -> Any:
        method = instance.klass.methods.get(name)
        if method is None:
            raise KppNameRuntimeError(
                f"Method '{name}' is not defined on class '{instance.klass.name}'.",
                line,
            )
        if len(args) != len(method.params):
            raise KppRuntimeError(
                f"Method '{name}' expects {len(method.params)} argument(s), got {len(args)}.",
                line,
            )
        self._call_depth += 1
        if self._call_depth > MAX_CALL_DEPTH:
            self._call_depth -= 1
            raise KppRecursionError(
                f"Maximum recursion depth ({MAX_CALL_DEPTH}) exceeded in method '{name}'.",
                line,
            )
        fn_env = method.closure.child()
        fn_env.declare("self", instance)
        for param, arg in zip(method.params, args):
            fn_env.declare(param, arg)
        try:
            self._exec_stmts(method.body, fn_env)
            return None
        except _ReturnSignal as ret:
            return ret.value
        finally:
            self._call_depth -= 1

    def _eval_new_instance(self, node: NewInstanceNode, env: Environment) -> Any:
        try:
            klass = env.get(node.class_name)
        except KppNameError:
            raise KppNameRuntimeError(f"Class '{node.class_name}' is not defined.", node.line)
        if not isinstance(klass, KppClass):
            raise KppTypeError(f"'{node.class_name}' is not a class.", node.line)
        instance = KppInstance(klass)
        args = [self._eval(a, env) for a in node.args]
        init_method = klass.methods.get("init")
        if init_method is not None:
            self._call_method(instance, "init", args, node.line)
        elif args:
            raise KppRuntimeError(
                f"Class '{node.class_name}' has no init method but arguments were provided.",
                node.line,
            )
        return instance

    def _eval_attr_access(self, node: AttrAccessNode, env: Environment) -> Any:
        target = self._eval_identifier(IdentifierNode(line=node.line, name=node.object_name), env)
        if not isinstance(target, KppInstance):
            raise KppTypeError(f"'{node.object_name}' is not an object instance.", node.line)
        if node.attr_name not in target.fields:
            raise KppNameRuntimeError(
                f"Attribute '{node.attr_name}' is not defined on '{target.klass.name}'.",
                node.line,
            )
        return target.fields[node.attr_name]

    # ── list literal ─────────────────────────────────────────────────────────

    def _eval_list(self, node: ListNode, env: Environment) -> list:
        return [self._eval(e, env) for e in node.elements]

    # ── list access ──────────────────────────────────────────────────────────

    def _eval_list_access(self, node: ListAccessNode, env: Environment) -> Any:
        idx_val = self._eval(node.index_expr, env)
        if not isinstance(idx_val, (int, float)):
            raise KppTypeError("List index must be a number.", node.line)
        idx = int(idx_val)
        try:
            lst = env.get(node.list_name)
        except KppNameError:
            raise KppNameRuntimeError(f"List '{node.list_name}' is not defined.", node.line)
        if not isinstance(lst, list):
            raise KppTypeError(f"'{node.list_name}' is not a list.", node.line)
        if idx < 0 or idx >= len(lst):
            raise KppIndexError(
                f"Index {idx} is out of bounds for list '{node.list_name}' of size {len(lst)}.",
                node.line,
            )
        return lst[idx]

    # ── list size ─────────────────────────────────────────────────────────────

    def _eval_list_size(self, node: ListSizeNode, env: Environment) -> int:
        try:
            lst = env.get(node.list_name)
        except KppNameError:
            raise KppNameRuntimeError(f"List '{node.list_name}' is not defined.", node.line)
        if not isinstance(lst, list):
            raise KppTypeError(f"'{node.list_name}' is not a list.", node.line)
        return len(lst)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _type_name(val: Any) -> str:
    if val is None:         return "nothing"
    if isinstance(val, bool): return "boolean"
    if isinstance(val, int):  return "number"
    if isinstance(val, float): return "number"
    if isinstance(val, str):  return "text"
    if isinstance(val, list): return "list"
    if isinstance(val, KppClass): return "class"
    if isinstance(val, KppInstance): return "object"
    return type(val).__name__


def _assert_numeric(val: Any, op: str, line: int) -> None:
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise KppTypeError(
            f"Cannot apply '{op}' to {_type_name(val)}. Numbers required.", line
        )


def _kpp_equal(a: Any, b: Any) -> bool:
    """K++ equality: nothing == nothing, type-strict otherwise."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # bool vs non-bool: never equal
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b
