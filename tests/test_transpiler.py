"""Tests for the Mandate transpiler."""

import ast

from mandate.lexer import tokenize
from mandate.parser import parse
from mandate.transpiler import transpile


def _transpile_source(src: str) -> str:
    return transpile(parse(tokenize(src)))


def test_transpile_produces_valid_python(hello_source):
    code = _transpile_source(hello_source)
    ast.parse(code)  # raises SyntaxError if invalid


def test_transpile_sort_valid_python(sort_source):
    code = _transpile_source(sort_source)
    ast.parse(code)


def test_transpile_function_name(hello_source):
    code = _transpile_source(hello_source)
    assert "def hello(input_data: dict)" in code


def test_transpile_docstring(hello_source):
    code = _transpile_source(hello_source)
    assert "Greet a user by name" in code


def test_transpile_return_produces_output(sort_source):
    code = _transpile_source(sort_source)
    assert "return output" in code


def test_transpile_if_else():
    src = '''mandate cond {
  intent: "Conditional"
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
    code = _transpile_source(src)
    ast.parse(code)
    assert "if " in code
    assert "else:" in code


def test_transpile_handoff_as_comments():
    src = '''mandate hoff {
  intent: "Test"
  flow { return { x: 1 } }
  handoff {
    worked: "Everything"
    failed: "Nothing"
    next: "Continue"
  }
}'''
    code = _transpile_source(src)
    assert "# worked:" in code
    assert "# failed:" in code


def test_transpile_requires_as_comments():
    src = '''mandate with_req {
  intent: "Test"
  requires: fetch(url: string) -> string
  flow {
    d = fetch("x")
    return { d: d }
  }
}'''
    code = _transpile_source(src)
    assert "# requires: fetch" in code
