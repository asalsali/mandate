"""Tests for the Mandate AIR serializer."""

import json

from mandate.lexer import tokenize
from mandate.parser import parse
from mandate.ast_nodes import PrimitiveType, RecordType, ArrayType
from mandate.air import mandate_to_air, to_air_json, _type_to_dict, _expr_to_dict
from mandate.verify import VerifyResult


def _parse_first(src: str):
    return parse(tokenize(src)).mandates[0]


def test_air_version():
    m = _parse_first('mandate a { intent: "Test" flow { return { x: 1 } } }')
    air = mandate_to_air(m)
    assert air["version"] == "air-1.0"


def test_air_mandate_name():
    m = _parse_first('mandate hello { intent: "Greet" flow { return { x: 1 } } }')
    air = mandate_to_air(m)
    assert air["mandate"] == "hello"
    assert air["intent"] == "Greet"


def test_air_default_lineage():
    m = _parse_first('mandate a { intent: "T" flow { return { x: 1 } } }')
    air = mandate_to_air(m)
    assert air["lineage"]["author"] == "unknown"
    assert air["lineage"]["generation"] == 0


def test_air_custom_lineage():
    m = _parse_first('mandate a { intent: "T" flow { return { x: 1 } } }')
    lineage = {"author": "alex", "generation": 2, "parents": ["parent-1"]}
    air = mandate_to_air(m, lineage=lineage)
    assert air["lineage"]["author"] == "alex"
    assert air["lineage"]["generation"] == 2


def test_air_ast_has_flow():
    m = _parse_first('mandate a { intent: "T" flow { return { x: 1 } } }')
    air = mandate_to_air(m)
    assert "flow" in air["ast"]
    assert len(air["ast"]["flow"]) == 1


def test_air_with_verification():
    m = _parse_first('mandate a { intent: "T" flow { return { x: 1 } } }')
    results = [
        VerifyResult(expression="x > 0", passed=True, actual_value=True),
        VerifyResult(expression="x < 100", passed=False, actual_value=False, error="failed"),
    ]
    air = mandate_to_air(m, verification=results)
    assert air["verification"]["passed"] == 1
    assert air["verification"]["failed"] == 1
    assert air["confidence"] == 0.5


def test_air_json_roundtrip():
    m = _parse_first('mandate a { intent: "T" flow { return { x: 1 } } }')
    json_str = to_air_json(m)
    data = json.loads(json_str)
    assert data["mandate"] == "a"
    assert data["version"] == "air-1.0"


def test_air_handoff():
    src = '''mandate h { intent: "T" flow { return { x: 1 } }
  handoff { worked: "ok" failed: "no" next: "go" }
}'''
    m = _parse_first(src)
    air = mandate_to_air(m)
    assert air["handoff"]["worked"] == "ok"
    assert air["handoff"]["failed"] == "no"
    assert air["handoff"]["next"] == "go"


def test_type_to_dict_primitive():
    assert _type_to_dict(PrimitiveType("string")) == "string"


def test_type_to_dict_array():
    result = _type_to_dict(ArrayType(PrimitiveType("int")))
    assert result == {"array": "int"}


def test_type_to_dict_record():
    result = _type_to_dict(RecordType({"name": PrimitiveType("string")}))
    assert result == {"record": {"name": "string"}}


def test_air_input_output_types(hello_source):
    m = _parse_first(hello_source)
    air = mandate_to_air(m)
    assert "input" in air["ast"]
    assert "output" in air["ast"]
