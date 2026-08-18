"""Mandate CLI -- parse, check, transpile, run, and air commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme

# Gold accent theme matching Synthex
THEME = Theme({
    "mandate.gold": "#c9a227",
    "mandate.dim": "#666666",
    "mandate.ok": "#00cc66",
    "mandate.fail": "#ff4444",
})

console = Console(theme=THEME)


def _read_source(file: str) -> str:
    path = Path(file)
    if not path.exists():
        console.print(f"[mandate.fail]File not found: {file}[/]")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


@click.group()
@click.version_option(version="0.1.0", prog_name="mandate")
def main():
    """Mandate -- an agent-native programming language."""
    pass


@main.command()
@click.argument("file")
def parse(file: str):
    """Parse a .mdt file and display the AST."""
    from .lexer import tokenize
    from .parser import parse as parse_tokens

    source = _read_source(file)

    try:
        tokens = tokenize(source)
        program = parse_tokens(tokens)
    except Exception as e:
        console.print(f"[mandate.fail]Parse error:[/] {e}")
        sys.exit(1)

    for mandate in program.mandates:
        console.print(Panel(
            _format_ast(mandate),
            title=f"[mandate.gold]mandate {mandate.name}[/]",
            border_style="mandate.gold",
        ))


@main.command()
@click.argument("file")
def check(file: str):
    """Parse and type-check a .mdt file."""
    from .lexer import tokenize
    from .parser import parse as parse_tokens
    from .type_checker import check as type_check

    source = _read_source(file)

    try:
        tokens = tokenize(source)
        program = parse_tokens(tokens)
    except Exception as e:
        console.print(f"[mandate.fail]Parse error:[/] {e}")
        sys.exit(1)

    result = type_check(program)

    if result.ok:
        console.print(f"[mandate.ok]All checks passed[/] for [mandate.gold]{file}[/]")
        for m in program.mandates:
            in_fields = len(m.input_type.fields) if m.input_type else 0
            out_fields = len(m.output_type.fields) if m.output_type else 0
            console.print(f"  [mandate.dim]mandate[/] [mandate.gold]{m.name}[/] "
                          f"[mandate.dim]| input: {in_fields} fields | output: {out_fields} fields | "
                          f"flow: {len(m.flow)} stmts | verify: {len(m.verify)} checks[/]")
    else:
        console.print(f"[mandate.fail]Type errors in {file}:[/]")
        for err in result.errors:
            console.print(f"  [mandate.fail]x[/] {err}")
        sys.exit(1)


@main.command()
@click.argument("file")
def transpile(file: str):
    """Transpile a .mdt file to Python."""
    from .lexer import tokenize
    from .parser import parse as parse_tokens
    from .transpiler import transpile as do_transpile

    source = _read_source(file)

    try:
        tokens = tokenize(source)
        program = parse_tokens(tokens)
        python_code = do_transpile(program)
    except Exception as e:
        console.print(f"[mandate.fail]Error:[/] {e}")
        sys.exit(1)

    syntax = Syntax(python_code, "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="[mandate.gold]Transpiled Python[/]", border_style="mandate.gold"))


@main.command()
@click.argument("file")
@click.option("--input", "-i", "input_json", default="{}", help="Input data as JSON string")
@click.option("--model", "-m", default="gpt-4o-mini", help="LLM model for synthesize blocks")
def run(file: str, input_json: str, model: str):
    """Run a .mdt file end-to-end."""
    from .runner import run as run_mandate

    try:
        input_data = json.loads(input_json)
    except json.JSONDecodeError as e:
        console.print(f"[mandate.fail]Invalid input JSON:[/] {e}")
        sys.exit(1)

    try:
        result = run_mandate(file, input_data, model=model)
    except Exception as e:
        console.print(f"[mandate.fail]Runtime error:[/] {e}")
        sys.exit(1)

    # Display type warnings
    if result.type_errors:
        console.print("[mandate.gold]Type warnings:[/]")
        for err in result.type_errors:
            console.print(f"  [mandate.dim]![/] {err}")
        console.print()

    # Display runtime error
    if result.runtime_error:
        console.print(f"[mandate.fail]Runtime error:[/] {result.runtime_error}")
        sys.exit(1)

    # Display output
    console.print(Panel(
        json.dumps(result.output, indent=2, default=str),
        title=f"[mandate.gold]{result.mandate_name} output[/]",
        border_style="mandate.gold",
    ))

    # Display verification
    if result.verify_results:
        table = Table(title="Verification", border_style="mandate.gold")
        table.add_column("Check", style="mandate.dim")
        table.add_column("Status", justify="center")
        table.add_column("Value", style="mandate.dim")

        for v in result.verify_results:
            status = "[mandate.ok]PASS[/]" if v.passed else "[mandate.fail]FAIL[/]"
            value = str(v.error) if v.error else str(v.actual_value)
            table.add_row(v.expression, status, value)

        console.print(table)

    # Summary
    if result.all_passed:
        console.print(f"\n[mandate.ok]All {len(result.verify_results)} verifications passed.[/]")
    else:
        failed = sum(1 for v in result.verify_results if not v.passed)
        console.print(f"\n[mandate.fail]{failed} verification(s) failed.[/]")
        sys.exit(1)


@main.command()
@click.argument("file")
@click.option("--lineage", "-l", default=None, help="Lineage JSON string")
def air(file: str, lineage: str | None):
    """Output AIR (Agent Intermediate Representation) JSON."""
    from .air import to_air_json
    from .lexer import tokenize
    from .parser import parse as parse_tokens

    source = _read_source(file)

    try:
        tokens = tokenize(source)
        program = parse_tokens(tokens)
    except Exception as e:
        console.print(f"[mandate.fail]Error:[/] {e}")
        sys.exit(1)

    if not program.mandates:
        console.print("[mandate.fail]No mandate blocks found.[/]")
        sys.exit(1)

    lineage_dict = json.loads(lineage) if lineage else None
    air_json = to_air_json(program.mandates[0], lineage=lineage_dict)
    console.print(Syntax(air_json, "json", theme="monokai"))


def _format_ast(mandate) -> str:
    """Format an AST node for display."""
    lines = []
    lines.append(f"[mandate.gold]name:[/] {mandate.name}")
    lines.append(f"[mandate.gold]intent:[/] {mandate.intent}")

    if mandate.input_type:
        fields = ", ".join(f"{k}: {v}" for k, v in mandate.input_type.fields.items())
        lines.append(f"[mandate.gold]input:[/]  {{ {fields} }}")

    if mandate.output_type:
        fields = ", ".join(f"{k}: {v}" for k, v in mandate.output_type.fields.items())
        lines.append(f"[mandate.gold]output:[/] {{ {fields} }}")

    for req in mandate.requires:
        params = ", ".join(f"{k}: {v}" for k, v in req.params.items())
        lines.append(f"[mandate.gold]requires:[/] {req.name}({params}) -> {req.return_type}")

    lines.append(f"[mandate.gold]flow:[/]   {len(mandate.flow)} statement(s)")
    lines.append(f"[mandate.gold]verify:[/] {len(mandate.verify)} assertion(s)")

    if mandate.handoff:
        lines.append(f"[mandate.gold]handoff:[/] worked={mandate.handoff.worked!r}")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
