"""Tests for the Mandate runner (stub mode — no API key)."""

from pathlib import Path

from mandate.runner import run, MandateRunner, RunResult
from mandate.lexer import tokenize
from mandate.parser import parse


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_run_hello():
    result = run(EXAMPLES / "hello.mdt", {"name": "Alice"})
    assert isinstance(result, RunResult)
    assert result.mandate_name == "hello"
    assert "greeting" in result.output
    assert isinstance(result.output["greeting"], str)
    assert len(result.output["greeting"]) > 0


def test_run_sort_array():
    result = run(EXAMPLES / "sort_array.mdt", {"numbers": [3, 1, 2]})
    assert result.mandate_name == "sort_array"
    assert result.output["sorted"] == [1, 2, 3]
    assert result.output["count"] == 3


def test_run_sort_verify_passes():
    result = run(EXAMPLES / "sort_array.mdt", {"numbers": [5, 2, 8]})
    assert result.all_passed
    assert len(result.verify_results) == 2
    assert all(v.passed for v in result.verify_results)


def test_run_with_external_function():
    src = '''mandate ext {
  intent: "Test external"
  requires: double(x: int) -> int
  output: { result: int }
  flow {
    r = double(21)
    return { result: r }
  }
}'''
    program = parse(tokenize(src))
    m = program.mandates[0]
    runner = MandateRunner(external_functions={"double": lambda x: x * 2})
    result = runner.run_mandate(m, {})
    assert result.output["result"] == 42


def test_run_type_errors_included():
    src = '''mandate bad {
  flow { return { x: undefined_var } }
}'''
    result_obj = run.__wrapped__ if hasattr(run, '__wrapped__') else run
    # Type errors are non-blocking — they're collected and included
    from mandate.lexer import tokenize as lex
    from mandate.parser import parse as par
    from mandate.type_checker import check
    program = par(lex(src))
    tc = check(program)
    assert not tc.ok  # should have errors


def test_run_if_branch():
    src = '''mandate branch {
  intent: "Test branching"
  input: { x: int }
  output: { label: string }
  flow {
    if input.x > 10 {
      return { label: "big" }
    } else {
      return { label: "small" }
    }
  }
}'''
    program = parse(tokenize(src))
    m = program.mandates[0]
    runner = MandateRunner()
    result = runner.run_mandate(m, {"x": 20})
    assert result.output["label"] == "big"
    result2 = runner.run_mandate(m, {"x": 5})
    assert result2.output["label"] == "small"


def test_run_stub_synthesize():
    """Synthesize in stub mode returns plausible defaults."""
    result = run(EXAMPLES / "hello.mdt", {"name": "Bob"})
    # Stub mode returns "Hello, {name}! (stub response)" or similar
    assert result.output["greeting"] is not None
    assert isinstance(result.output["greeting"], str)
