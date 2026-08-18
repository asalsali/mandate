"""Agent Intermediate Representation (AIR) serialization."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .ast_nodes import (
    ArrayType,
    Assignment,
    BinaryOp,
    FieldAccess,
    FunctionCall,
    HandoffBlock,
    Identifier,
    IfStmt,
    Literal,
    MandateBlock,
    OptionalType,
    PrimitiveType,
    Program,
    RangeExpr,
    RecordType,
    RequiresDecl,
    ReturnStmt,
    SynthesizeExpr,
    UnaryOp,
    VerifyExpr,
)
from .verify import VerifyResult


def _type_to_dict(t: Any) -> dict | str:
    """Serialize a type node."""
    if isinstance(t, PrimitiveType):
        return t.name
    if isinstance(t, ArrayType):
        return {"array": _type_to_dict(t.element_type)}
    if isinstance(t, OptionalType):
        return {"optional": _type_to_dict(t.inner_type)}
    if isinstance(t, RecordType):
        return {"record": {k: _type_to_dict(v) for k, v in t.fields.items()}}
    return str(t)


def _expr_to_dict(expr: Any) -> dict:
    """Serialize an expression node."""
    if isinstance(expr, Literal):
        return {"literal": expr.value, "type": expr.type}
    if isinstance(expr, Identifier):
        return {"identifier": expr.name}
    if isinstance(expr, FieldAccess):
        return {"fieldAccess": {"object": _expr_to_dict(expr.object), "field": expr.field}}
    if isinstance(expr, FunctionCall):
        return {"call": expr.name, "args": [_expr_to_dict(a) for a in expr.args]}
    if isinstance(expr, SynthesizeExpr):
        return {
            "synthesize": {
                "given": [_expr_to_dict(g) for g in expr.given],
                "produce": _type_to_dict(expr.produce_type),
                "instruction": expr.instruction,
            }
        }
    if isinstance(expr, BinaryOp):
        right = _expr_to_dict(expr.right) if not isinstance(expr.right, RangeExpr) else {
            "range": {"low": _expr_to_dict(expr.right.low), "high": _expr_to_dict(expr.right.high)}
        }
        return {"binaryOp": {"left": _expr_to_dict(expr.left), "op": expr.op, "right": right}}
    if isinstance(expr, UnaryOp):
        return {"unaryOp": {"op": expr.op, "operand": _expr_to_dict(expr.operand)}}
    if isinstance(expr, RangeExpr):
        return {"range": {"low": _expr_to_dict(expr.low), "high": _expr_to_dict(expr.high)}}
    return {"unknown": str(type(expr).__name__)}


def _stmt_to_dict(stmt: Any) -> dict:
    """Serialize a flow statement."""
    if isinstance(stmt, Assignment):
        return {"assign": {"target": stmt.target, "expression": _expr_to_dict(stmt.expression)}}
    if isinstance(stmt, ReturnStmt):
        return {"return": {k: _expr_to_dict(v) for k, v in stmt.fields.items()}}
    if isinstance(stmt, IfStmt):
        return {
            "if": {
                "condition": _expr_to_dict(stmt.condition),
                "body": [_stmt_to_dict(s) for s in stmt.body],
                "else": [_stmt_to_dict(s) for s in stmt.else_body],
            }
        }
    return {"unknown": str(type(stmt).__name__)}


def mandate_to_air(
    mandate: MandateBlock,
    verification: list[VerifyResult] | None = None,
    lineage: dict | None = None,
) -> dict:
    """Serialize a MandateBlock + execution results to AIR format."""
    air: dict[str, Any] = {
        "version": "air-1.0",
        "mandate": mandate.name,
        "intent": mandate.intent,
    }

    # Lineage
    air["lineage"] = lineage or {
        "author": "unknown",
        "generation": 0,
        "parents": [],
    }

    # AST
    ast_dict: dict[str, Any] = {}
    if mandate.input_type:
        ast_dict["input"] = _type_to_dict(mandate.input_type)
    if mandate.output_type:
        ast_dict["output"] = _type_to_dict(mandate.output_type)
    if mandate.requires:
        ast_dict["requires"] = [
            {
                "name": r.name,
                "params": {k: _type_to_dict(v) for k, v in r.params.items()},
                "returnType": _type_to_dict(r.return_type),
            }
            for r in mandate.requires
        ]
    ast_dict["flow"] = [_stmt_to_dict(s) for s in mandate.flow]
    if mandate.verify:
        ast_dict["verify"] = [
            {"expression": _expr_to_dict(v.expression), "source": v.source}
            for v in mandate.verify
        ]
    air["ast"] = ast_dict

    # Verification results
    if verification is not None:
        passed = sum(1 for v in verification if v.passed)
        failed = sum(1 for v in verification if not v.passed)
        air["verification"] = {
            "passed": passed,
            "failed": failed,
            "results": [
                {
                    "expression": v.expression,
                    "passed": v.passed,
                    "actualValue": v.actual_value,
                    "error": v.error,
                }
                for v in verification
            ],
        }

        total = passed + failed
        air["confidence"] = passed / total if total > 0 else 0.0

    # Handoff
    if mandate.handoff:
        air["handoff"] = {
            "worked": mandate.handoff.worked,
            "failed": mandate.handoff.failed,
            "next": mandate.handoff.next_recommendation,
        }

    return air


def to_air_json(
    mandate: MandateBlock,
    verification: list[VerifyResult] | None = None,
    lineage: dict | None = None,
    indent: int = 2,
) -> str:
    """Serialize to AIR JSON string."""
    air = mandate_to_air(mandate, verification, lineage)
    return json.dumps(air, indent=indent, default=str)
