"""Tests for the Mandate auto-formatter."""

from pathlib import Path

import pytest
from mandate.lexer import tokenize
from mandate.parser import parse
from mandate.formatter import format_program


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestFormatterRoundtrip:
    def test_hello_roundtrip(self, hello_source):
        """Format should produce parseable output."""
        program = parse(tokenize(hello_source))
        formatted = format_program(program)
        # Should parse without error
        program2 = parse(tokenize(formatted))
        assert len(program2.mandates) == 1
        assert program2.mandates[0].name == "hello"

    def test_sort_roundtrip(self, sort_source):
        program = parse(tokenize(sort_source))
        formatted = format_program(program)
        program2 = parse(tokenize(formatted))
        assert program2.mandates[0].name == "sort_array"

    def test_pipeline_roundtrip(self):
        source = (EXAMPLES / "pipeline.mdt").read_text(encoding="utf-8")
        program = parse(tokenize(source))
        formatted = format_program(program)
        program2 = parse(tokenize(formatted))
        assert len(program2.mandates) == 2


class TestFormatterOutput:
    def test_includes_intent(self, hello_source):
        program = parse(tokenize(hello_source))
        formatted = format_program(program)
        assert 'intent: "Greet a user by name"' in formatted

    def test_includes_input_output(self, hello_source):
        program = parse(tokenize(hello_source))
        formatted = format_program(program)
        assert "input:" in formatted
        assert "output:" in formatted

    def test_includes_verify(self, sort_source):
        program = parse(tokenize(sort_source))
        formatted = format_program(program)
        assert "verify {" in formatted

    def test_includes_handoff(self):
        src = '''mandate h {
  intent: "Test"
  flow { return { x: 1 } }
  handoff {
    worked: "ok"
    failed: "no"
    next: "go"
  }
}'''
        program = parse(tokenize(src))
        formatted = format_program(program)
        assert 'worked: "ok"' in formatted
        assert 'failed: "no"' in formatted
        assert 'next: "go"' in formatted

    def test_idempotent(self, hello_source):
        """Formatting twice should produce the same output."""
        program = parse(tokenize(hello_source))
        once = format_program(program)
        program2 = parse(tokenize(once))
        twice = format_program(program2)
        assert once == twice


class TestFormatterImports:
    def test_format_with_import(self):
        source = (EXAMPLES / "with_import.mdt").read_text(encoding="utf-8")
        program = parse(tokenize(source))
        formatted = format_program(program)
        assert 'import fetch_data from "./imported_helper.mdt"' in formatted


class TestFormatterEnum:
    def test_format_with_enum(self):
        source = (EXAMPLES / "with_enum.mdt").read_text(encoding="utf-8")
        program = parse(tokenize(source))
        formatted = format_program(program)
        assert "enum Priority" in formatted
        assert "low" in formatted
