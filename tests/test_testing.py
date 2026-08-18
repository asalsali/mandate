"""Tests for the Mandate testing framework."""

from pathlib import Path

import pytest
from mandate.testing import (
    run_test_suite,
    mock_synthesize,
    MockConfig,
    TestSuiteResult,
    TestResult,
    record_snapshots,
)
from mandate.ast_nodes import PrimitiveType, ArrayType, RecordType


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestMockSynthesize:
    def test_string(self):
        result = mock_synthesize(PrimitiveType("string"), {}, "")
        assert isinstance(result, str)

    def test_int(self):
        result = mock_synthesize(PrimitiveType("int"), {}, "")
        assert isinstance(result, int)

    def test_float(self):
        result = mock_synthesize(PrimitiveType("float"), {}, "")
        assert isinstance(result, float)

    def test_bool(self):
        result = mock_synthesize(PrimitiveType("bool"), {}, "")
        assert isinstance(result, bool)

    def test_array(self):
        result = mock_synthesize(ArrayType(PrimitiveType("int")), {}, "")
        assert isinstance(result, list)
        assert len(result) == 3  # default array_length

    def test_record(self):
        rt = RecordType({"name": PrimitiveType("string"), "age": PrimitiveType("int")})
        result = mock_synthesize(rt, {}, "")
        assert isinstance(result, dict)
        assert "name" in result
        assert "age" in result

    def test_custom_config(self):
        cfg = MockConfig(string_value="custom", int_value=99)
        result = mock_synthesize(PrimitiveType("string"), {}, "", cfg)
        assert result == "custom"

    def test_snapshot_override(self):
        result = mock_synthesize(
            PrimitiveType("string"), {}, "",
            snapshots={"key": "snapshot_value"},
            snapshot_key="key",
        )
        assert result == "snapshot_value"


class TestRunTestSuite:
    def test_hello(self):
        suite = run_test_suite(EXAMPLES / "hello.mdt")
        assert len(suite.results) == 1
        assert suite.results[0].mandate_name == "hello"
        assert suite.results[0].passed >= 1
        assert suite.all_passed

    def test_sort_array(self):
        suite = run_test_suite(EXAMPLES / "sort_array.mdt", {"numbers": [3, 1, 2]})
        assert suite.all_passed
        assert suite.total_passed == 2

    def test_pipeline(self):
        suite = run_test_suite(EXAMPLES / "pipeline.mdt")
        assert len(suite.results) == 2

    def test_auto_generates_input(self):
        """If no input provided, mock generates type-appropriate defaults."""
        suite = run_test_suite(EXAMPLES / "hello.mdt")
        assert suite.results[0].ok

    def test_parse_error_captured(self, tmp_path):
        bad = tmp_path / "bad.mdt"
        bad.write_text("not valid mandate code @@@", encoding="utf-8")
        suite = run_test_suite(bad)
        assert len(suite.parse_errors) > 0

    def test_with_budget_example(self):
        suite = run_test_suite(EXAMPLES / "with_budget.mdt")
        assert suite.all_passed


class TestTestResult:
    def test_ok_when_all_pass(self):
        r = TestResult(mandate_name="test", passed=3, failed=0, errors=0)
        assert r.ok

    def test_not_ok_on_failure(self):
        r = TestResult(mandate_name="test", passed=2, failed=1, errors=0)
        assert not r.ok

    def test_not_ok_on_error(self):
        r = TestResult(mandate_name="test", passed=2, failed=0, errors=1)
        assert not r.ok

    def test_total(self):
        r = TestResult(mandate_name="test", passed=2, failed=1, errors=1)
        assert r.total == 4


class TestSuiteResultProps:
    def test_totals(self):
        suite = TestSuiteResult(file="test.mdt", results=[
            TestResult(mandate_name="a", passed=3, failed=1, errors=0),
            TestResult(mandate_name="b", passed=2, failed=0, errors=1),
        ])
        assert suite.total_passed == 5
        assert suite.total_failed == 1
        assert suite.total_errors == 1
        assert not suite.all_passed
