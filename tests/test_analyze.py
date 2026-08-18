"""Tests for the Mandate static analyzer."""

from pathlib import Path

import pytest
from mandate.lexer import tokenize
from mandate.parser import parse
from mandate.analyze import analyze, AnalysisReport, MandateAnalysis


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _analyze_source(src: str) -> AnalysisReport:
    return analyze(parse(tokenize(src)))


class TestSingleMandate:
    def test_basic_analysis(self, hello_source):
        report = _analyze_source(hello_source)
        assert len(report.mandates) == 1
        m = report.mandates[0]
        assert m.name == "hello"
        assert m.input_fields == ["name"]
        assert m.output_fields == ["greeting"]
        assert m.synthesize_count == 1
        assert m.verify_count == 1

    def test_sort_no_synth(self, sort_source):
        report = _analyze_source(sort_source)
        m = report.mandates[0]
        assert m.synthesize_count == 0
        assert m.verify_count == 2

    def test_total_counts(self, hello_source):
        report = _analyze_source(hello_source)
        assert report.total_synthesize_calls == 1
        assert report.estimated_total_llm_calls == 1


class TestVerifyCoverage:
    def test_full_coverage(self, sort_source):
        """sort_array verifies count and sorted.length — both output fields covered."""
        report = _analyze_source(sort_source)
        m = report.mandates[0]
        # sorted and count are output fields
        # verify checks output.count and output.sorted.length
        assert "count" not in m.unverified_fields

    def test_unverified_field_detected(self):
        src = '''mandate partial {
  intent: "Test"
  output: { a: int, b: int, c: int }
  flow { return { a: 1, b: 2, c: 3 } }
  verify {
    output.a > 0
  }
}'''
        report = _analyze_source(src)
        m = report.mandates[0]
        assert "b" in m.unverified_fields
        assert "c" in m.unverified_fields
        assert "a" not in m.unverified_fields
        assert any("unverified" in w.lower() or "no verify" in w.lower() for w in report.warnings)

    def test_no_output_no_warning(self):
        src = '''mandate minimal {
  intent: "Test"
  flow { return { x: 1 } }
}'''
        report = _analyze_source(src)
        m = report.mandates[0]
        assert m.unverified_fields == []


class TestPipelineDependencies:
    def test_edge_detected(self):
        src = '''mandate a {
  intent: "Produce"
  output: { data: string }
  flow { return { data: "x" } }
}
mandate b {
  intent: "Consume"
  input: { data: string }
  output: { result: string }
  flow { return { result: input.data } }
}'''
        report = _analyze_source(src)
        assert len(report.edges) == 1
        assert report.edges[0].producer == "a"
        assert report.edges[0].consumer == "b"
        assert "data" in report.edges[0].fields

    def test_no_edges_single_mandate(self, hello_source):
        report = _analyze_source(hello_source)
        assert report.edges == []

    def test_pipeline_example(self):
        source = (EXAMPLES / "pipeline.mdt").read_text(encoding="utf-8")
        report = _analyze_source(source)
        assert len(report.mandates) == 2
        assert len(report.edges) == 1
        assert report.edges[0].fields == ["data"]


class TestDeadMandates:
    def test_dead_mandate_detected(self):
        src = '''mandate isolated {
  intent: "Produces stuff nobody wants"
  output: { x: int }
  flow { return { x: 1 } }
}
mandate consumer {
  intent: "Takes different input"
  input: { y: string }
  output: { z: string }
  flow { return { z: input.y } }
}'''
        report = _analyze_source(src)
        assert "isolated" in report.dead_mandates

    def test_connected_not_dead(self):
        src = '''mandate a {
  intent: "Produce"
  output: { data: string }
  flow { return { data: "x" } }
}
mandate b {
  intent: "Consume"
  input: { data: string }
  output: { result: string }
  flow { return { result: input.data } }
}'''
        report = _analyze_source(src)
        assert report.dead_mandates == []

    def test_last_mandate_never_dead(self):
        """The last mandate is always 'live' — it produces final output."""
        src = '''mandate only {
  intent: "Only one"
  output: { x: int }
  flow { return { x: 1 } }
}'''
        report = _analyze_source(src)
        assert report.dead_mandates == []
