"""Tests for the Mandate type checker."""

import pytest
from mandate.lexer import tokenize
from mandate.parser import parse
from mandate.type_checker import check, TypeCheckResult


def _check_source(src: str) -> TypeCheckResult:
    return check(parse(tokenize(src)))


def test_valid_hello(hello_source):
    result = _check_source(hello_source)
    assert result.ok


def test_valid_sort(sort_source):
    result = _check_source(sort_source)
    assert result.ok


def test_missing_intent():
    src = '''mandate no_intent {
  output: { x: int }
  flow { return { x: 1 } }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("intent" in m.lower() for m in msgs)


def test_undefined_variable():
    src = '''mandate bad_var {
  intent: "Test"
  output: { x: int }
  flow {
    return { x: nonexistent }
  }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("nonexistent" in m for m in msgs)


def test_missing_return_field():
    src = '''mandate missing_field {
  intent: "Test"
  output: { x: int, y: int }
  flow {
    return { x: 1 }
  }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("y" in m for m in msgs)


def test_extra_return_field():
    src = '''mandate extra_field {
  intent: "Test"
  output: { x: int }
  flow {
    return { x: 1, z: 2 }
  }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("z" in m for m in msgs)


def test_unknown_function():
    src = '''mandate bad_func {
  intent: "Test"
  output: { x: int }
  flow {
    return { x: nonexistent_func(1) }
  }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("nonexistent_func" in m for m in msgs)


def test_requires_function_known():
    src = '''mandate with_req {
  intent: "Test"
  requires: fetch(url: string) -> string
  output: { data: string }
  flow {
    d = fetch("http://example.com")
    return { data: d }
  }
}'''
    result = _check_source(src)
    assert result.ok


def test_requires_wrong_arity():
    src = '''mandate bad_arity {
  intent: "Test"
  requires: fetch(url: string) -> string
  output: { data: string }
  flow {
    d = fetch("a", "b", "c")
    return { data: d }
  }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("fetch" in m for m in msgs)


def test_no_return_in_flow():
    src = '''mandate no_return {
  intent: "Test"
  output: { x: int }
  flow {
    y = 1
  }
}'''
    result = _check_source(src)
    assert not result.ok
    msgs = [str(e) for e in result.errors]
    assert any("return" in m.lower() for m in msgs)
