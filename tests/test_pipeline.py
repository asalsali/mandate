"""Tests for pipeline execution and cross-mandate type checking."""

from pathlib import Path

import pytest
from mandate.lexer import tokenize
from mandate.parser import parse
from mandate.type_checker import check
from mandate.runner import run_pipeline, PipelineResult


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestPipelineExecution:
    def test_pipeline_runs_all_stages(self):
        result = run_pipeline(EXAMPLES / "pipeline.mdt", {"source": "test", "question": "what?"})
        assert isinstance(result, PipelineResult)
        assert len(result.stages) == 2
        assert result.stages[0].mandate_name == "fetch_data"
        assert result.stages[1].mandate_name == "analyze_data"

    def test_pipeline_chains_output(self):
        result = run_pipeline(EXAMPLES / "pipeline.mdt", {"source": "test", "question": "what?"})
        # Stage 1 produces {data, rows}, stage 2 needs {data, question}
        # data flows from stage 1 output, question from initial input
        assert "answer" in result.final_output
        assert "confidence" in result.final_output

    def test_pipeline_all_passed(self):
        result = run_pipeline(EXAMPLES / "pipeline.mdt", {"source": "test", "question": "what?"})
        assert result.all_passed

    def test_pipeline_single_mandate(self):
        result = run_pipeline(EXAMPLES / "hello.mdt", {"name": "Alice"})
        assert len(result.stages) == 1
        assert result.stages[0].mandate_name == "hello"

    def test_pipeline_stops_on_error(self):
        """A mandate with a runtime error stops the pipeline."""
        from mandate.runner import run_pipeline as rp
        from mandate.lexer import tokenize as lex
        from mandate.parser import parse as par

        src = '''mandate fail_first {
  intent: "Fail"
  output: { x: int }
  flow {
    y = nonexistent_var
    return { x: y }
  }
}
mandate never_reached {
  intent: "Should not run"
  output: { z: int }
  flow { return { z: 1 } }
}'''
        # Write to temp file
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".mdt", mode="w", delete=False, encoding="utf-8") as f:
            f.write(src)
            tmp = f.name
        try:
            result = rp(tmp, {})
            assert len(result.stages) == 1  # stopped at first
            assert result.stages[0].runtime_error is not None
        finally:
            os.unlink(tmp)

    def test_pipeline_result_final_output_empty_on_no_stages(self):
        result = PipelineResult()
        assert result.final_output == {}
        assert result.all_passed is True


class TestPipelineTypeChecking:
    def test_compatible_pipeline_passes(self):
        src = '''mandate producer {
  intent: "Produce"
  output: { data: string, count: int }
  flow { return { data: "x", count: 1 } }
}
mandate consumer {
  intent: "Consume"
  input: { data: string }
  output: { result: string }
  flow { return { result: input.data } }
}'''
        result = check(parse(tokenize(src)))
        assert result.ok

    def test_missing_field_detected(self):
        src = '''mandate producer {
  intent: "Produce"
  output: { data: string }
  flow { return { data: "x" } }
}
mandate consumer {
  intent: "Consume"
  input: { data: string, missing_field: int }
  output: { result: string }
  flow { return { result: input.data } }
}'''
        result = check(parse(tokenize(src)))
        errors = [str(e) for e in result.errors]
        assert any("missing_field" in e for e in errors)

    def test_type_mismatch_detected(self):
        src = '''mandate producer {
  intent: "Produce"
  output: { value: string }
  flow { return { value: "hello" } }
}
mandate consumer {
  intent: "Consume"
  input: { value: int }
  output: { result: int }
  flow { return { result: input.value } }
}'''
        result = check(parse(tokenize(src)))
        errors = [str(e) for e in result.errors]
        assert any("mismatch" in e.lower() or "Type" in e for e in errors)

    def test_no_output_type_warns(self):
        src = '''mandate producer {
  intent: "Produce"
  flow { return { x: 1 } }
}
mandate consumer {
  intent: "Consume"
  input: { x: int }
  output: { y: int }
  flow { return { y: input.x } }
}'''
        result = check(parse(tokenize(src)))
        errors = [str(e) for e in result.errors]
        assert any("no output type" in e.lower() for e in errors)

    def test_single_mandate_no_pipeline_check(self):
        """Single mandate should not trigger pipeline checks."""
        src = '''mandate solo {
  intent: "Solo"
  output: { x: int }
  flow { return { x: 1 } }
}'''
        result = check(parse(tokenize(src)))
        assert result.ok
