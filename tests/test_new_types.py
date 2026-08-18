"""Tests for enum and union types."""

from pathlib import Path

import pytest
from mandate.lexer import tokenize, TokenType
from mandate.parser import parse
from mandate.ast_nodes import EnumType, UnionType, PrimitiveType
from mandate.transpiler import transpile
from mandate.air import _type_to_dict


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestEnumLexer:
    def test_enum_keyword(self):
        tokens = tokenize("enum")
        assert tokens[0].type == TokenType.ENUM


class TestEnumParser:
    def test_parse_enum(self):
        src = '''enum Status { active, pending, closed }
mandate m { intent: "T" flow { return { x: 1 } } }'''
        program = parse(tokenize(src))
        enums = getattr(program, "enums", [])
        assert len(enums) == 1
        assert enums[0].name == "Status"
        assert enums[0].variants == ["active", "pending", "closed"]

    def test_parse_enum_example(self):
        source = (EXAMPLES / "with_enum.mdt").read_text(encoding="utf-8")
        program = parse(tokenize(source))
        enums = getattr(program, "enums", [])
        assert len(enums) == 1
        assert enums[0].name == "Priority"
        assert "critical" in enums[0].variants

    def test_enum_as_type(self):
        src = '''enum Color { red, green, blue }
mandate m {
  intent: "T"
  input: { color: Color }
  output: { label: string }
  flow { return { label: "ok" } }
}'''
        program = parse(tokenize(src))
        assert program.mandates[0].input_type.fields["color"].name == "Color"


class TestUnionType:
    def test_pipe_token(self):
        tokens = tokenize("string | int")
        types = [t.type for t in tokens if t.type not in (TokenType.EOF, TokenType.NEWLINE)]
        assert TokenType.PIPE in types

    def test_parse_union_type(self):
        src = '''mandate m {
  intent: "T"
  input: { value: string | int }
  output: { result: string }
  flow { return { result: "ok" } }
}'''
        program = parse(tokenize(src))
        value_type = program.mandates[0].input_type.fields["value"]
        assert isinstance(value_type, UnionType)
        assert len(value_type.types) == 2

    def test_parse_triple_union(self):
        src = '''mandate m {
  intent: "T"
  input: { x: string | int | float }
  output: { y: string }
  flow { return { y: "ok" } }
}'''
        program = parse(tokenize(src))
        x_type = program.mandates[0].input_type.fields["x"]
        assert isinstance(x_type, UnionType)
        assert len(x_type.types) == 3

    def test_union_repr(self):
        u = UnionType([PrimitiveType("string"), PrimitiveType("int")])
        assert str(u) == "string | int"


class TestTypesSerialization:
    def test_enum_to_air(self):
        e = EnumType(name="Status", variants=["active", "pending"])
        result = _type_to_dict(e)
        assert result == {"enum": {"name": "Status", "variants": ["active", "pending"]}}

    def test_union_to_air(self):
        u = UnionType([PrimitiveType("string"), PrimitiveType("int")])
        result = _type_to_dict(u)
        assert result == {"union": ["string", "int"]}


class TestTypesTranspile:
    def test_enum_example_transpiles(self):
        source = (EXAMPLES / "with_enum.mdt").read_text(encoding="utf-8")
        code = transpile(parse(tokenize(source)))
        import ast
        ast.parse(code)  # valid Python
