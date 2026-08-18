"""Verification runner -- evaluates verify expressions against output data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast_nodes import (
    BinaryOp,
    FieldAccess,
    FunctionCall,
    Identifier,
    Literal,
    RangeExpr,
    UnaryOp,
    VerifyExpr,
)


@dataclass
class VerifyResult:
    """Result of a single verify assertion."""
    expression: str
    passed: bool
    actual_value: Any
    error: str | None = None


def evaluate_expr(expr: Any, output: dict, input_data: dict | None = None) -> Any:
    """Evaluate an expression against output (and optional input) data."""
    scope = {"output": output}
    if input_data:
        scope["input"] = input_data

    return _eval(expr, scope)


def _eval(expr: Any, scope: dict) -> Any:
    """Recursively evaluate an expression node."""
    if isinstance(expr, Literal):
        return expr.value

    if isinstance(expr, Identifier):
        if expr.name in scope:
            return scope[expr.name]
        # Builtins
        if expr.name == "true":
            return True
        if expr.name == "false":
            return False
        raise ValueError(f"Undefined variable: {expr.name}")

    if isinstance(expr, FieldAccess):
        obj = _eval(expr.object, scope)
        if isinstance(obj, dict):
            if expr.field in obj:
                return obj[expr.field]
            raise ValueError(f"Field {expr.field!r} not found in dict")
        if expr.field == "length":
            return len(obj)
        return getattr(obj, expr.field)

    if isinstance(expr, FunctionCall):
        args = [_eval(a, scope) for a in expr.args]
        builtins_map = {
            "len": len,
            "sort": sorted,
            "str": str,
            "int": int,
            "float": float,
            "abs": abs,
        }
        if expr.name in builtins_map:
            return builtins_map[expr.name](*args)
        raise ValueError(f"Unknown function: {expr.name}")

    if isinstance(expr, BinaryOp):
        left = _eval(expr.left, scope)

        # Special case for 'in' with range
        if expr.op == "in" and isinstance(expr.right, RangeExpr):
            low = _eval(expr.right.low, scope)
            high = _eval(expr.right.high, scope)
            return low <= left <= high

        right = _eval(expr.right, scope)

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

        if expr.op in ops:
            return ops[expr.op](left, right)
        raise ValueError(f"Unknown operator: {expr.op}")

    if isinstance(expr, UnaryOp):
        operand = _eval(expr.operand, scope)
        if expr.op == "not":
            return not operand
        if expr.op == "-":
            return -operand
        raise ValueError(f"Unknown unary operator: {expr.op}")

    raise ValueError(f"Cannot evaluate expression: {type(expr).__name__}")


def run_verify(
    verify_exprs: list[VerifyExpr],
    output: dict,
    input_data: dict | None = None,
) -> list[VerifyResult]:
    """Run all verify assertions against output data.

    Returns a list of VerifyResult for each assertion.
    """
    results: list[VerifyResult] = []

    for vexpr in verify_exprs:
        try:
            value = evaluate_expr(vexpr.expression, output, input_data)
            results.append(VerifyResult(
                expression=vexpr.source,
                passed=bool(value),
                actual_value=value,
            ))
        except Exception as e:
            results.append(VerifyResult(
                expression=vexpr.source,
                passed=False,
                actual_value=None,
                error=str(e),
            ))

    return results
