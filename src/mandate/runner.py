"""End-to-end execution of .mdt files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ast_nodes import (
    Assignment,
    BinaryOp,
    FieldAccess,
    FunctionCall,
    Identifier,
    IfStmt,
    Literal,
    MandateBlock,
    RangeExpr,
    ReturnStmt,
    SynthesizeExpr,
    UnaryOp,
)
from .lexer import tokenize
from .parser import parse
from .synthesize import synthesize_call
from .type_checker import check
from .verify import run_verify, VerifyResult


@dataclass
class RunResult:
    """Result of executing a mandate."""
    mandate_name: str
    output: dict[str, Any]
    verify_results: list[VerifyResult] = field(default_factory=list)
    all_passed: bool = True
    type_errors: list[str] = field(default_factory=list)
    runtime_error: str | None = None


class MandateRunner:
    """Execute a parsed MandateBlock."""

    def __init__(self, model: str = "gpt-4o-mini", external_functions: dict | None = None):
        self.model = model
        self.scope: dict[str, Any] = {}
        self.external_functions = external_functions or {}

    def run_mandate(self, mandate: MandateBlock, input_data: dict) -> RunResult:
        """Execute a single mandate block with the given input."""
        self.scope = {"input": input_data}
        output: dict[str, Any] = {}

        try:
            for stmt in mandate.flow:
                result = self.exec_statement(stmt)
                if isinstance(result, dict) and "__return__" in result:
                    output = result["__return__"]
                    break
        except Exception as e:
            return RunResult(
                mandate_name=mandate.name,
                output=output,
                all_passed=False,
                runtime_error=str(e),
            )

        # Run verification
        verify_results: list[VerifyResult] = []
        if mandate.verify:
            verify_results = run_verify(mandate.verify, output, input_data)

        all_passed = all(v.passed for v in verify_results)

        return RunResult(
            mandate_name=mandate.name,
            output=output,
            verify_results=verify_results,
            all_passed=all_passed,
        )

    def exec_statement(self, stmt: Any) -> Any:
        """Execute a flow statement."""
        if isinstance(stmt, Assignment):
            value = self.eval_expr(stmt.expression)
            self.scope[stmt.target] = value
            return value

        if isinstance(stmt, ReturnStmt):
            fields = {}
            for k, v in stmt.fields.items():
                fields[k] = self.eval_expr(v)
            return {"__return__": fields}

        if isinstance(stmt, IfStmt):
            cond = self.eval_expr(stmt.condition)
            body = stmt.body if cond else stmt.else_body
            for s in body:
                result = self.exec_statement(s)
                if isinstance(result, dict) and "__return__" in result:
                    return result
            return None

        return None

    def eval_expr(self, expr: Any) -> Any:
        """Evaluate an expression in the current scope."""
        if isinstance(expr, Literal):
            return expr.value

        if isinstance(expr, Identifier):
            if expr.name in self.scope:
                return self.scope[expr.name]
            raise RuntimeError(f"Undefined variable: {expr.name}")

        if isinstance(expr, FieldAccess):
            obj = self.eval_expr(expr.object)
            if isinstance(obj, dict):
                if expr.field in obj:
                    return obj[expr.field]
                raise RuntimeError(f"Field {expr.field!r} not found")
            if expr.field == "length":
                return len(obj)
            return getattr(obj, expr.field)

        if isinstance(expr, FunctionCall):
            args = [self.eval_expr(a) for a in expr.args]
            # Check external functions first
            if expr.name in self.external_functions:
                return self.external_functions[expr.name](*args)
            # Builtins
            builtins_map: dict[str, Any] = {
                "len": len,
                "sort": sorted,
                "str": str,
                "int": int,
                "float": float,
                "abs": abs,
                "print": print,
            }
            if expr.name in builtins_map:
                return builtins_map[expr.name](*args)
            raise RuntimeError(f"Unknown function: {expr.name}")

        if isinstance(expr, SynthesizeExpr):
            given_data = {}
            for g in expr.given:
                key = self._expr_key(g)
                given_data[key] = self.eval_expr(g)
            return synthesize_call(
                given=given_data,
                produce_type=expr.produce_type,
                instruction=expr.instruction,
                model=self.model,
            )

        if isinstance(expr, BinaryOp):
            left = self.eval_expr(expr.left)
            if expr.op == "in" and isinstance(expr.right, RangeExpr):
                low = self.eval_expr(expr.right.low)
                high = self.eval_expr(expr.right.high)
                return low <= left <= high
            right = self.eval_expr(expr.right)
            return self._apply_op(expr.op, left, right)

        if isinstance(expr, UnaryOp):
            operand = self.eval_expr(expr.operand)
            if expr.op == "not":
                return not operand
            if expr.op == "-":
                return -operand

        raise RuntimeError(f"Cannot evaluate: {type(expr).__name__}")

    def _apply_op(self, op: str, left: Any, right: Any) -> Any:
        ops = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "and": lambda a, b: a and b,
            "or": lambda a, b: a or b,
            "contains": lambda a, b: b in a,
            "is": lambda a, b: type(a).__name__ == b,
        }
        if op in ops:
            return ops[op](left, right)
        raise RuntimeError(f"Unknown operator: {op}")

    def _expr_key(self, expr: Any) -> str:
        if isinstance(expr, Identifier):
            return expr.name
        if isinstance(expr, FieldAccess):
            return expr.field
        return "value"


def run(
    mdt_file: str | Path,
    input_data: dict,
    model: str = "gpt-4o-mini",
    external_functions: dict | None = None,
) -> RunResult:
    """Execute a .mdt file end-to-end.

    1. Lex the file
    2. Parse to AST
    3. Type-check
    4. Execute flow, calling synthesize bridge as needed
    5. Run verify assertions
    6. Return result
    """
    path = Path(mdt_file)
    source = path.read_text(encoding="utf-8")

    # Lex
    tokens = tokenize(source)

    # Parse
    program = parse(tokens)
    if not program.mandates:
        raise RuntimeError(f"No mandate blocks found in {path}")

    mandate = program.mandates[0]  # Run the first mandate

    # Type check
    tc_result = check(program)
    type_errors = [str(e) for e in tc_result.errors]

    # Execute
    runner = MandateRunner(model=model, external_functions=external_functions)
    result = runner.run_mandate(mandate, input_data)
    result.type_errors = type_errors

    return result
