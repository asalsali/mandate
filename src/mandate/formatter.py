"""Auto-formatter for Mandate .mdt files.

Produces canonical formatting from an AST — one true format,
like gofmt. Reads a .mdt file, parses it, and emits formatted source.
"""

from __future__ import annotations

from typing import Any

from .ast_nodes import (
    ArrayType,
    Assignment,
    BinaryOp,
    EnumType,
    FieldAccess,
    FunctionCall,
    HandoffBlock,
    Identifier,
    IfStmt,
    ImportDecl,
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
    UnionType,
    VerifyExpr,
)


def format_program(program: Program) -> str:
    """Format a complete Mandate program to canonical source."""
    parts: list[str] = []

    for imp in program.imports:
        parts.append(f'import {imp.name} from "{imp.path}"')

    if program.imports:
        parts.append("")

    for enum in getattr(program, "enums", []):
        parts.append(_format_enum(enum))
        parts.append("")

    for i, mandate in enumerate(program.mandates):
        if i > 0:
            parts.append("")
        parts.append(_format_mandate(mandate))

    return "\n".join(parts) + "\n"


def _format_enum(enum: EnumType) -> str:
    variants = ", ".join(enum.variants)
    return f"enum {enum.name} {{ {variants} }}"


def _format_mandate(m: MandateBlock) -> str:
    lines: list[str] = []
    lines.append(f"mandate {m.name} {{")

    lines.append(f'  intent: "{m.intent}"')

    if m.input_type:
        lines.append(f"  input: {_format_record_type(m.input_type)}")

    if m.output_type:
        lines.append(f"  output: {_format_record_type(m.output_type)}")

    for req in m.requires:
        params = ", ".join(f"{k}: {_format_type(v)}" for k, v in req.params.items())
        lines.append(f"  requires: {req.name}({params}) -> {_format_type(req.return_type)}")

    if m.flow:
        lines.append("")
        lines.append("  flow {")
        for stmt in m.flow:
            for line in _format_stmt(stmt):
                lines.append(f"    {line}")
        lines.append("  }")

    if m.verify:
        lines.append("")
        lines.append("  verify {")
        for vexpr in m.verify:
            lines.append(f"    {_format_expr(vexpr.expression)}")
        lines.append("  }")

    if m.handoff:
        lines.append("")
        lines.append("  handoff {")
        lines.append(f'    worked: "{m.handoff.worked}"')
        lines.append(f'    failed: "{m.handoff.failed}"')
        lines.append(f'    next: "{m.handoff.next_recommendation}"')
        lines.append("  }")

    lines.append("}")
    return "\n".join(lines)


def _format_type(t: Any) -> str:
    if isinstance(t, PrimitiveType):
        return t.name
    if isinstance(t, ArrayType):
        return f"{_format_type(t.element_type)}[]"
    if isinstance(t, OptionalType):
        return f"{_format_type(t.inner_type)}?"
    if isinstance(t, RecordType):
        return _format_record_type(t)
    if isinstance(t, EnumType):
        return t.name
    if isinstance(t, UnionType):
        return " | ".join(_format_type(sub) for sub in t.types)
    return str(t)


def _format_record_type(r: RecordType) -> str:
    fields = ", ".join(f"{k}: {_format_type(v)}" for k, v in r.fields.items())
    return "{ " + fields + " }"


def _format_expr(expr: Any) -> str:
    if isinstance(expr, Literal):
        if expr.type == "string":
            return f'"{expr.value}"'
        if expr.type == "bool":
            return "true" if expr.value else "false"
        return str(expr.value)
    if isinstance(expr, Identifier):
        return expr.name
    if isinstance(expr, FieldAccess):
        return f"{_format_expr(expr.object)}.{expr.field}"
    if isinstance(expr, FunctionCall):
        args = ", ".join(_format_expr(a) for a in expr.args)
        return f"{expr.name}({args})"
    if isinstance(expr, BinaryOp):
        left = _format_expr(expr.left)
        if expr.op == "in" and isinstance(expr.right, RangeExpr):
            low = _format_expr(expr.right.low)
            high = _format_expr(expr.right.high)
            return f"{left} in {low}..{high}"
        right = _format_expr(expr.right)
        return f"{left} {expr.op} {right}"
    if isinstance(expr, UnaryOp):
        operand = _format_expr(expr.operand)
        if expr.op == "not":
            return f"not {operand}"
        return f"-{operand}"
    if isinstance(expr, SynthesizeExpr):
        lines = ["synthesize {"]
        if expr.given:
            given_str = ", ".join(_format_expr(g) for g in expr.given)
            lines.append(f"      given: {given_str}")
        lines.append(f"      produce: {_format_type(expr.produce_type)}")
        lines.append(f'      instruction: "{expr.instruction}"')
        lines.append("    }")
        return "\n".join(lines)
    if isinstance(expr, RangeExpr):
        return f"{_format_expr(expr.low)}..{_format_expr(expr.high)}"
    return str(expr)


def _format_stmt(stmt: Any) -> list[str]:
    if isinstance(stmt, Assignment):
        expr_str = _format_expr(stmt.expression)
        if "\n" in expr_str:
            # Multi-line (synthesize blocks)
            return [f"{stmt.target} = {expr_str}"]
        return [f"{stmt.target} = {expr_str}"]
    if isinstance(stmt, ReturnStmt):
        fields = ", ".join(f"{k}: {_format_expr(v)}" for k, v in stmt.fields.items())
        return [f"return {{ {fields} }}"]
    if isinstance(stmt, IfStmt):
        lines = [f"if {_format_expr(stmt.condition)} {{"]
        for s in stmt.body:
            for line in _format_stmt(s):
                lines.append(f"  {line}")
        if stmt.else_body:
            lines.append("} else {")
            for s in stmt.else_body:
                for line in _format_stmt(s):
                    lines.append(f"  {line}")
        lines.append("}")
        return lines
    return [str(stmt)]
