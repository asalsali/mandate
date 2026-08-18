"""AST node definitions for the Mandate language."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Type nodes
# ---------------------------------------------------------------------------

@dataclass
class PrimitiveType:
    """string, int, float, bool."""
    name: str  # "string" | "int" | "float" | "bool"

    def __repr__(self) -> str:
        return self.name


@dataclass
class ArrayType:
    """T[]."""
    element_type: Any  # PrimitiveType or nested

    def __repr__(self) -> str:
        return f"{self.element_type}[]"


@dataclass
class OptionalType:
    """T?."""
    inner_type: Any

    def __repr__(self) -> str:
        return f"{self.inner_type}?"


@dataclass
class RecordType:
    """{name: string, age: int}."""
    fields: dict[str, Any]  # field_name -> type node

    def __repr__(self) -> str:
        parts = ", ".join(f"{k}: {v}" for k, v in self.fields.items())
        return "{" + parts + "}"


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------

@dataclass
class Literal:
    """A literal value: string, int, float, bool."""
    value: Any
    type: str  # "string" | "int" | "float" | "bool"


@dataclass
class Identifier:
    """A bare name reference."""
    name: str


@dataclass
class FieldAccess:
    """object.field."""
    object: Any  # expression node
    field: str


@dataclass
class BinaryOp:
    """left op right."""
    left: Any
    op: str  # "+", "-", "*", "/", "==", "!=", ">", "<", ">=", "<=", "and", "or", "contains", "in"
    right: Any


@dataclass
class UnaryOp:
    """not expr."""
    op: str  # "not"
    operand: Any


@dataclass
class FunctionCall:
    """name(args...)."""
    name: str
    args: list[Any] = field(default_factory=list)


@dataclass
class SynthesizeExpr:
    """synthesize { given: ..., produce: ..., instruction: ... }."""
    given: list[Any]  # list of expression nodes
    produce_type: Any  # type node
    instruction: str


@dataclass
class RangeExpr:
    """low..high -- used inside 'in' checks in verify."""
    low: Any
    high: Any


@dataclass
class InterpolatedString:
    """String with {expr} interpolations."""
    parts: list[Any]  # mix of str literals and expression nodes


# ---------------------------------------------------------------------------
# Statement nodes
# ---------------------------------------------------------------------------

@dataclass
class Assignment:
    """target = expression."""
    target: str
    expression: Any


@dataclass
class ReturnStmt:
    """return { field: value, ... }."""
    fields: dict[str, Any]  # field_name -> expression node


@dataclass
class IfStmt:
    """if cond { body } else { else_body }."""
    condition: Any
    body: list[Any]  # list of statements
    else_body: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Verify / Handoff
# ---------------------------------------------------------------------------

@dataclass
class VerifyExpr:
    """A single boolean assertion in a verify block."""
    expression: Any  # expression node
    source: str = ""  # original source text for reporting


@dataclass
class HandoffBlock:
    """handoff { worked: ..., failed: ..., next: ... }."""
    worked: str
    failed: str
    next_recommendation: str


# ---------------------------------------------------------------------------
# Requires
# ---------------------------------------------------------------------------

@dataclass
class RequiresDecl:
    """requires: fetch_data(params) -> return_type."""
    name: str
    params: dict[str, Any]  # param_name -> type node
    return_type: Any  # type node


# ---------------------------------------------------------------------------
# Top-level block
# ---------------------------------------------------------------------------

@dataclass
class MandateBlock:
    """The top-level mandate { ... } block."""
    name: str
    intent: str
    input_type: RecordType | None = None
    output_type: RecordType | None = None
    requires: list[RequiresDecl] = field(default_factory=list)
    flow: list[Any] = field(default_factory=list)  # list of statements
    verify: list[VerifyExpr] = field(default_factory=list)
    handoff: HandoffBlock | None = None


@dataclass
class Program:
    """A .mdt file can contain one or more mandate blocks."""
    mandates: list[MandateBlock] = field(default_factory=list)
