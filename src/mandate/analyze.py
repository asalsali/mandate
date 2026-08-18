"""Static analysis for Mandate programs.

Provides whole-program analysis that justifies Mandate as a language:
- Dependency graph: which mandates feed into which
- Token cost estimation: count synthesize blocks before execution
- Verify coverage: which output fields lack assertions
- Dead mandate detection: mandates whose output is never consumed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ast_nodes import (
    Assignment,
    FieldAccess,
    Identifier,
    MandateBlock,
    Program,
    SynthesizeExpr,
)


@dataclass
class MandateAnalysis:
    """Analysis of a single mandate."""
    name: str
    intent: str
    input_fields: list[str]
    output_fields: list[str]
    synthesize_count: int
    verify_count: int
    unverified_fields: list[str]
    estimated_llm_calls: int
    budget_max_calls: int | None = None
    budget_exceeded: bool = False


@dataclass
class PipelineEdge:
    """A data dependency between two mandates."""
    producer: str
    consumer: str
    fields: list[str]  # fields that flow from producer to consumer


@dataclass
class AnalysisReport:
    """Complete static analysis report."""
    mandates: list[MandateAnalysis] = field(default_factory=list)
    edges: list[PipelineEdge] = field(default_factory=list)
    dead_mandates: list[str] = field(default_factory=list)
    total_synthesize_calls: int = 0
    total_verify_assertions: int = 0
    estimated_total_llm_calls: int = 0
    warnings: list[str] = field(default_factory=list)


def _count_synthesize_blocks(flow: list[Any]) -> int:
    """Count synthesize expressions in a flow block (including nested)."""
    count = 0
    for stmt in flow:
        if isinstance(stmt, Assignment) and isinstance(stmt.expression, SynthesizeExpr):
            count += 1
        elif isinstance(stmt, Assignment):
            count += _count_expr_synthesize(stmt.expression)
    return count


def _count_expr_synthesize(expr: Any) -> int:
    """Count synthesize expressions nested in an expression."""
    if isinstance(expr, SynthesizeExpr):
        return 1
    return 0


def _get_verified_fields(mandate: MandateBlock) -> set[str]:
    """Extract output field names referenced in verify blocks."""
    fields: set[str] = set()
    for vexpr in mandate.verify:
        _walk_for_output_fields(vexpr.expression, fields)
    return fields


def _walk_for_output_fields(expr: Any, fields: set[str]) -> None:
    """Walk an expression tree collecting output.field references."""
    if isinstance(expr, FieldAccess):
        if isinstance(expr.object, Identifier) and expr.object.name == "output":
            fields.add(expr.field)
        _walk_for_output_fields(expr.object, fields)
    elif hasattr(expr, "left") and hasattr(expr, "right"):
        _walk_for_output_fields(expr.left, fields)
        _walk_for_output_fields(expr.right, fields)
    elif hasattr(expr, "operand"):
        _walk_for_output_fields(expr.operand, fields)


def analyze(program: Program) -> AnalysisReport:
    """Run static analysis on a Mandate program."""
    report = AnalysisReport()

    for mandate in program.mandates:
        input_fields = list(mandate.input_type.fields.keys()) if mandate.input_type else []
        output_fields = list(mandate.output_type.fields.keys()) if mandate.output_type else []
        synth_count = _count_synthesize_blocks(mandate.flow)
        verify_count = len(mandate.verify)

        verified = _get_verified_fields(mandate)
        unverified = [f for f in output_fields if f not in verified]

        # Budget checking
        budget_max = None
        budget_exceeded = False
        if mandate.budget and mandate.budget.max_calls is not None:
            budget_max = mandate.budget.max_calls
            if synth_count > budget_max:
                budget_exceeded = True

        analysis = MandateAnalysis(
            name=mandate.name,
            intent=mandate.intent,
            input_fields=input_fields,
            output_fields=output_fields,
            synthesize_count=synth_count,
            verify_count=verify_count,
            unverified_fields=unverified,
            estimated_llm_calls=synth_count,
            budget_max_calls=budget_max,
            budget_exceeded=budget_exceeded,
        )
        report.mandates.append(analysis)
        report.total_synthesize_calls += synth_count
        report.total_verify_assertions += verify_count
        report.estimated_total_llm_calls += synth_count

        if unverified:
            report.warnings.append(
                f"'{mandate.name}': output fields {unverified} have no verify assertions"
            )

        if budget_exceeded:
            report.warnings.append(
                f"'{mandate.name}': budget exceeded — {synth_count} synthesize calls "
                f"but max_calls is {budget_max}"
            )

    # Pipeline dependency analysis
    if len(program.mandates) > 1:
        consumed_outputs: set[str] = set()

        for i in range(len(program.mandates) - 1):
            producer = program.mandates[i]
            consumer = program.mandates[i + 1]

            if not producer.output_type or not consumer.input_type:
                continue

            produced = set(producer.output_type.fields.keys())
            needed = set(consumer.input_type.fields.keys())
            shared = produced & needed

            if shared:
                report.edges.append(PipelineEdge(
                    producer=producer.name,
                    consumer=consumer.name,
                    fields=sorted(shared),
                ))
                consumed_outputs.update(shared)

        # Dead mandate detection: mandates whose output is never consumed
        # (last mandate is always "live" — it produces the final output)
        for i, mandate in enumerate(program.mandates[:-1]):
            if not mandate.output_type:
                continue
            produced = set(mandate.output_type.fields.keys())
            if not produced & consumed_outputs and len(program.mandates) > 1:
                report.dead_mandates.append(mandate.name)
                report.warnings.append(
                    f"'{mandate.name}': output fields are never consumed by downstream mandates"
                )

    return report
