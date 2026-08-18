"""Type validation for Mandate AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ast_nodes import (
    ArrayType,
    Assignment,
    BinaryOp,
    FieldAccess,
    FunctionCall,
    Identifier,
    IfStmt,
    Literal,
    MandateBlock,
    OptionalType,
    PrimitiveType,
    Program,
    RangeExpr,
    RecordType,
    ReturnStmt,
    SynthesizeExpr,
    UnaryOp,
    VerifyExpr,
)


@dataclass
class TypeError_:
    """A type error in a Mandate program."""
    message: str
    context: str = ""  # where in the program

    def __str__(self) -> str:
        prefix = f"[{self.context}] " if self.context else ""
        return f"{prefix}{self.message}"


@dataclass
class TypeCheckResult:
    """Result of type checking a program."""
    errors: list[TypeError_] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add(self, msg: str, ctx: str = "") -> None:
        self.errors.append(TypeError_(msg, ctx))


class TypeChecker:
    """Validate types across a MandateBlock."""

    def __init__(self):
        self.result = TypeCheckResult()
        self.scope: dict[str, Any] = {}  # variable name -> type
        self.input_type: RecordType | None = None
        self.output_type: RecordType | None = None
        self.requires: dict[str, Any] = {}  # function name -> (params, return_type)

    def check_program(self, program: Program) -> TypeCheckResult:
        for mandate in program.mandates:
            self.check_mandate(mandate)
        return self.result

    def check_mandate(self, m: MandateBlock) -> None:
        """Check a single mandate block."""
        ctx = f"mandate {m.name}"

        # Validate intent exists
        if not m.intent:
            self.result.add("Missing intent declaration", ctx)

        # Set up scope with input fields
        self.input_type = m.input_type
        self.output_type = m.output_type
        self.scope = {}

        if m.input_type:
            self.scope["input"] = m.input_type

        # Register requires functions
        self.requires = {}
        for req in m.requires:
            self.requires[req.name] = (req.params, req.return_type)

        # Check flow statements
        has_return = False
        for stmt in m.flow:
            self.check_flow_statement(stmt, ctx)
            if isinstance(stmt, ReturnStmt):
                has_return = True

        # Check that flow has a return
        if m.flow and not has_return:
            self.result.add("Flow block has no return statement", ctx)

        # Check return matches output type
        for stmt in m.flow:
            if isinstance(stmt, ReturnStmt) and m.output_type:
                self.check_return_matches_output(stmt, m.output_type, ctx)

        # Check verify expressions reference valid output fields
        for vexpr in m.verify:
            self.check_verify_expr(vexpr, ctx)

    def check_flow_statement(self, stmt: Any, ctx: str) -> None:
        """Check a flow statement."""
        if isinstance(stmt, Assignment):
            inferred = self.infer_type(stmt.expression, ctx)
            self.scope[stmt.target] = inferred
        elif isinstance(stmt, ReturnStmt):
            for fname, fexpr in stmt.fields.items():
                self.infer_type(fexpr, ctx)
        elif isinstance(stmt, IfStmt):
            self.infer_type(stmt.condition, ctx)
            for s in stmt.body:
                self.check_flow_statement(s, ctx)
            for s in stmt.else_body:
                self.check_flow_statement(s, ctx)

    def infer_type(self, expr: Any, ctx: str) -> Any:
        """Infer the type of an expression and validate references."""
        if isinstance(expr, Literal):
            return PrimitiveType(expr.type)

        if isinstance(expr, Identifier):
            if expr.name in self.scope:
                return self.scope[expr.name]
            # Builtins
            if expr.name in ("len", "sort", "print"):
                return PrimitiveType("int")  # approximate
            self.result.add(f"Undefined variable: {expr.name!r}", ctx)
            return None

        if isinstance(expr, FieldAccess):
            obj_type = self.infer_type(expr.object, ctx)
            if isinstance(obj_type, RecordType):
                if expr.field not in obj_type.fields:
                    self.result.add(
                        f"Field {expr.field!r} not found in record type {obj_type}",
                        ctx,
                    )
                    return None
                return obj_type.fields[expr.field]
            # Allow .length on any type (runtime check)
            if expr.field == "length":
                return PrimitiveType("int")
            return None

        if isinstance(expr, FunctionCall):
            if expr.name in self.requires:
                params, ret_type = self.requires[expr.name]
                if len(expr.args) != len(params):
                    self.result.add(
                        f"Function {expr.name!r} expects {len(params)} args, "
                        f"got {len(expr.args)}",
                        ctx,
                    )
                return ret_type
            # Built-in functions
            if expr.name in ("len", "sort", "print", "str", "int", "float"):
                for arg in expr.args:
                    self.infer_type(arg, ctx)
                return PrimitiveType("int")  # approximate
            self.result.add(f"Unknown function: {expr.name!r}", ctx)
            return None

        if isinstance(expr, SynthesizeExpr):
            for g in expr.given:
                self.infer_type(g, ctx)
            return expr.produce_type

        if isinstance(expr, BinaryOp):
            self.infer_type(expr.left, ctx)
            if isinstance(expr.right, RangeExpr):
                self.infer_type(expr.right.low, ctx)
                self.infer_type(expr.right.high, ctx)
            else:
                self.infer_type(expr.right, ctx)
            # Approximate return types
            if expr.op in ("==", "!=", ">", "<", ">=", "<=", "and", "or", "contains", "in", "is"):
                return PrimitiveType("bool")
            return PrimitiveType("float")  # arithmetic

        if isinstance(expr, UnaryOp):
            self.infer_type(expr.operand, ctx)
            if expr.op == "not":
                return PrimitiveType("bool")
            return PrimitiveType("float")

        return None

    def check_return_matches_output(
        self, ret: ReturnStmt, output: RecordType, ctx: str
    ) -> None:
        """Check that return fields match output type declaration."""
        for field_name in output.fields:
            if field_name not in ret.fields:
                self.result.add(
                    f"Output field {field_name!r} not returned in flow", ctx
                )
        for field_name in ret.fields:
            if field_name not in output.fields:
                self.result.add(
                    f"Return field {field_name!r} not declared in output type", ctx
                )

    def check_verify_expr(self, vexpr: VerifyExpr, ctx: str) -> None:
        """Check that verify expressions reference valid fields."""
        self._walk_expr_for_output_refs(vexpr.expression, ctx)

    def _walk_expr_for_output_refs(self, expr: Any, ctx: str) -> None:
        """Walk an expression tree looking for output.field references."""
        if isinstance(expr, FieldAccess):
            self._walk_expr_for_output_refs(expr.object, ctx)
            # Check output.field references
            if isinstance(expr.object, Identifier) and expr.object.name == "output":
                if self.output_type and expr.field not in self.output_type.fields:
                    # Allow .length and other property accesses
                    if expr.field != "length":
                        self.result.add(
                            f"Verify references output.{expr.field} but "
                            f"{expr.field!r} is not in output type",
                            ctx,
                        )
        elif isinstance(expr, BinaryOp):
            self._walk_expr_for_output_refs(expr.left, ctx)
            if isinstance(expr.right, RangeExpr):
                self._walk_expr_for_output_refs(expr.right.low, ctx)
                self._walk_expr_for_output_refs(expr.right.high, ctx)
            else:
                self._walk_expr_for_output_refs(expr.right, ctx)
        elif isinstance(expr, UnaryOp):
            self._walk_expr_for_output_refs(expr.operand, ctx)
        elif isinstance(expr, FunctionCall):
            for arg in expr.args:
                self._walk_expr_for_output_refs(arg, ctx)


def check(program: Program) -> TypeCheckResult:
    """Type-check a Mandate program."""
    checker = TypeChecker()
    result = checker.check_program(program)

    # Pipeline type checking: verify output→input compatibility
    if len(program.mandates) > 1:
        _check_pipeline_types(program, result)

    return result


def _check_pipeline_types(program: Program, result: TypeCheckResult) -> None:
    """Check cross-mandate type compatibility in a pipeline.

    For each consecutive pair of mandates, verify that the output fields
    of mandate N cover the input fields required by mandate N+1.
    """
    for i in range(len(program.mandates) - 1):
        producer = program.mandates[i]
        consumer = program.mandates[i + 1]
        ctx = f"pipeline {producer.name} -> {consumer.name}"

        if not consumer.input_type:
            continue  # Consumer takes no input — always compatible

        if not producer.output_type:
            result.add(
                f"'{producer.name}' has no output type but "
                f"'{consumer.name}' expects input fields: "
                f"{list(consumer.input_type.fields.keys())}",
                ctx,
            )
            continue

        # Check that every field consumer needs is produced by producer
        # (or was in the original input — we can't know that statically,
        # so we only warn on fields the producer doesn't provide)
        produced = set(producer.output_type.fields.keys())
        for field_name, field_type in consumer.input_type.fields.items():
            if field_name not in produced:
                result.add(
                    f"'{consumer.name}' expects input field '{field_name}' "
                    f"but '{producer.name}' does not output it "
                    f"(must be provided in initial input or by an earlier stage)",
                    ctx,
                )

            # Type compatibility check
            elif field_name in producer.output_type.fields:
                out_type = producer.output_type.fields[field_name]
                if repr(out_type) != repr(field_type):
                    result.add(
                        f"Type mismatch: '{producer.name}' outputs "
                        f"'{field_name}' as {out_type} but '{consumer.name}' "
                        f"expects {field_type}",
                        ctx,
                    )
