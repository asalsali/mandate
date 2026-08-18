"""Tests for the Mandate parser."""

import pytest
from mandate.lexer import tokenize
from mandate.parser import parse, ParseError
from mandate.ast_nodes import (
    Program, MandateBlock, RecordType, PrimitiveType, ArrayType,
    SynthesizeExpr, ReturnStmt, Assignment, HandoffBlock, Literal,
    BinaryOp, FieldAccess, FunctionCall, Identifier,
)


def _parse_source(src: str) -> Program:
    return parse(tokenize(src))


def test_parse_hello(hello_source):
    program = _parse_source(hello_source)
    assert len(program.mandates) == 1
    m = program.mandates[0]
    assert m.name == "hello"
    assert m.intent == "Greet a user by name"


def test_parse_input_output_types(hello_source):
    m = _parse_source(hello_source).mandates[0]
    assert isinstance(m.input_type, RecordType)
    assert "name" in m.input_type.fields
    assert isinstance(m.input_type.fields["name"], PrimitiveType)
    assert isinstance(m.output_type, RecordType)
    assert "greeting" in m.output_type.fields


def test_parse_array_type(sort_source):
    m = _parse_source(sort_source).mandates[0]
    assert isinstance(m.input_type.fields["numbers"], ArrayType)
    inner = m.input_type.fields["numbers"].element_type
    assert isinstance(inner, PrimitiveType)
    assert inner.name == "int"


def test_parse_flow_assignment(sort_source):
    m = _parse_source(sort_source).mandates[0]
    assignments = [s for s in m.flow if isinstance(s, Assignment)]
    assert len(assignments) == 2
    assert assignments[0].target == "sorted"
    assert assignments[1].target == "count"


def test_parse_return_stmt(sort_source):
    m = _parse_source(sort_source).mandates[0]
    returns = [s for s in m.flow if isinstance(s, ReturnStmt)]
    assert len(returns) == 1
    assert "sorted" in returns[0].fields
    assert "count" in returns[0].fields


def test_parse_synthesize_block(hello_source):
    m = _parse_source(hello_source).mandates[0]
    assignments = [s for s in m.flow if isinstance(s, Assignment)]
    synth = assignments[0].expression
    assert isinstance(synth, SynthesizeExpr)
    assert synth.instruction == "Write a warm, friendly greeting for this person by name"
    assert isinstance(synth.produce_type, PrimitiveType)
    assert synth.produce_type.name == "string"


def test_parse_verify_block(hello_source):
    m = _parse_source(hello_source).mandates[0]
    assert len(m.verify) >= 1
    # output.greeting.length > 0
    expr = m.verify[0].expression
    assert isinstance(expr, BinaryOp)
    assert expr.op == ">"


def test_parse_handoff():
    src = '''mandate research {
  intent: "Research a topic"
  output: { summary: string, confidence: float }
  flow {
    return { summary: "test", confidence: 0.8 }
  }
  handoff {
    worked: "Found data"
    failed: "API was slow"
    next: "Deep dive into subtopic"
  }
}'''
    m = _parse_source(src).mandates[0]
    assert isinstance(m.handoff, HandoffBlock)
    assert m.handoff.worked == "Found data"
    assert m.handoff.failed == "API was slow"
    assert m.handoff.next_recommendation == "Deep dive into subtopic"


def test_parse_multiple_mandates():
    src = '''mandate a {
  intent: "First"
  flow { return { x: 1 } }
}
mandate b {
  intent: "Second"
  flow { return { y: 2 } }
}'''
    program = _parse_source(src)
    assert len(program.mandates) == 2
    assert program.mandates[0].name == "a"
    assert program.mandates[1].name == "b"


def test_parse_error_missing_brace():
    with pytest.raises(ParseError):
        _parse_source("mandate broken {")


def test_parse_requires():
    src = '''mandate fetch_data {
  intent: "Fetch external data"
  requires: get_price(symbol: string) -> float
  output: { price: float }
  flow {
    p = get_price("BTC")
    return { price: p }
  }
}'''
    m = _parse_source(src).mandates[0]
    assert len(m.requires) == 1
    req = m.requires[0]
    assert req.name == "get_price"
    assert "symbol" in req.params
    assert isinstance(req.return_type, PrimitiveType)
    assert req.return_type.name == "float"


def test_parse_if_else():
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
    m = _parse_source(src).mandates[0]
    from mandate.ast_nodes import IfStmt
    ifs = [s for s in m.flow if isinstance(s, IfStmt)]
    assert len(ifs) == 1
    assert len(ifs[0].body) == 1
    assert len(ifs[0].else_body) == 1
