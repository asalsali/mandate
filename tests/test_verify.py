"""Tests for the Mandate verify engine."""

import pytest
from mandate.ast_nodes import (
    BinaryOp, Literal, Identifier, FieldAccess, UnaryOp,
    FunctionCall, RangeExpr, VerifyExpr,
)
from mandate.verify import evaluate_expr, run_verify, VerifyResult


def test_equality():
    expr = BinaryOp(Literal(1, "int"), "==", Literal(1, "int"))
    assert evaluate_expr(expr, {}) is True


def test_inequality():
    expr = BinaryOp(Literal(1, "int"), "!=", Literal(2, "int"))
    assert evaluate_expr(expr, {}) is True


def test_greater_than():
    expr = BinaryOp(Literal(5, "int"), ">", Literal(3, "int"))
    assert evaluate_expr(expr, {}) is True


def test_less_than():
    expr = BinaryOp(Literal(2, "int"), "<", Literal(10, "int"))
    assert evaluate_expr(expr, {}) is True


def test_gte_lte():
    gte = BinaryOp(Literal(5, "int"), ">=", Literal(5, "int"))
    assert evaluate_expr(gte, {}) is True
    lte = BinaryOp(Literal(3, "int"), "<=", Literal(5, "int"))
    assert evaluate_expr(lte, {}) is True


def test_and_or():
    and_expr = BinaryOp(Literal(True, "bool"), "and", Literal(False, "bool"))
    assert evaluate_expr(and_expr, {}) is False
    or_expr = BinaryOp(Literal(True, "bool"), "or", Literal(False, "bool"))
    assert evaluate_expr(or_expr, {}) is True


def test_not():
    expr = UnaryOp("not", Literal(False, "bool"))
    assert evaluate_expr(expr, {}) is True


def test_contains():
    # "hello world" contains "hello"
    expr = BinaryOp(Literal("hello world", "string"), "contains", Literal("hello", "string"))
    assert evaluate_expr(expr, {}) is True


def test_contains_false():
    expr = BinaryOp(Literal("abc", "string"), "contains", Literal("xyz", "string"))
    assert evaluate_expr(expr, {}) is False


def test_field_access_output():
    expr = FieldAccess(object=Identifier("output"), field="score")
    result = evaluate_expr(expr, {"score": 0.95})
    assert result == 0.95


def test_field_access_input():
    expr = FieldAccess(object=Identifier("input"), field="name")
    result = evaluate_expr(expr, {}, input_data={"name": "Alice"})
    assert result == "Alice"


def test_range_in():
    # 0.5 in 0.0..1.0
    expr = BinaryOp(
        Literal(0.5, "float"),
        "in",
        RangeExpr(Literal(0.0, "float"), Literal(1.0, "float")),
    )
    assert evaluate_expr(expr, {}) is True


def test_range_out():
    expr = BinaryOp(
        Literal(1.5, "float"),
        "in",
        RangeExpr(Literal(0.0, "float"), Literal(1.0, "float")),
    )
    assert evaluate_expr(expr, {}) is False


def test_arithmetic():
    expr = BinaryOp(Literal(3, "int"), "+", Literal(4, "int"))
    assert evaluate_expr(expr, {}) == 7


def test_nested_field_access():
    # output.greeting.length > 0
    expr = BinaryOp(
        FieldAccess(object=FieldAccess(object=Identifier("output"), field="greeting"), field="length"),
        ">",
        Literal(0, "int"),
    )
    result = evaluate_expr(expr, {"greeting": "Hello!"})
    assert result is True


def test_builtin_len():
    expr = FunctionCall(name="len", args=[FieldAccess(object=Identifier("output"), field="items")])
    result = evaluate_expr(expr, {"items": [1, 2, 3]})
    assert result == 3


def test_run_verify_all_pass():
    vexprs = [
        VerifyExpr(
            expression=BinaryOp(
                FieldAccess(object=Identifier("output"), field="x"),
                ">",
                Literal(0, "int"),
            ),
            source="output.x > 0",
        ),
    ]
    results = run_verify(vexprs, {"x": 5})
    assert len(results) == 1
    assert results[0].passed is True


def test_run_verify_failure():
    vexprs = [
        VerifyExpr(
            expression=BinaryOp(
                FieldAccess(object=Identifier("output"), field="x"),
                ">",
                Literal(100, "int"),
            ),
            source="output.x > 100",
        ),
    ]
    results = run_verify(vexprs, {"x": 5})
    assert len(results) == 1
    assert results[0].passed is False


def test_run_verify_error_captured():
    vexprs = [
        VerifyExpr(
            expression=FieldAccess(object=Identifier("output"), field="missing"),
            source="output.missing",
        ),
    ]
    results = run_verify(vexprs, {})
    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].error is not None


def test_unary_minus():
    expr = UnaryOp("-", Literal(5, "int"))
    assert evaluate_expr(expr, {}) == -5
