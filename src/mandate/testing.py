"""Testing framework for Mandate programs.

Runs all verify blocks as a test suite with mock synthesize providers.
No LLM calls needed — deterministic, reproducible, CI-friendly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .ast_nodes import (
    ArrayType,
    MandateBlock,
    PrimitiveType,
    RecordType,
    SynthesizeExpr,
)
from .lexer import tokenize
from .parser import parse
from .runner import MandateRunner, RunResult
from .type_checker import check
from .verify import VerifyResult


@dataclass
class MockConfig:
    """Configuration for mock synthesize responses."""
    seed: int = 42
    string_value: str = "mock_string"
    int_value: int = 42
    float_value: float = 0.75
    bool_value: bool = True
    array_length: int = 3


@dataclass
class TestResult:
    """Result of testing a single mandate."""
    mandate_name: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    details: list[VerifyResult] = field(default_factory=list)
    type_errors: list[str] = field(default_factory=list)
    runtime_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.runtime_error is None

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors


@dataclass
class TestSuiteResult:
    """Result of testing all mandates in a file."""
    file: str
    results: list[TestResult] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)

    @property
    def total_passed(self) -> int:
        return sum(r.passed for r in self.results)

    @property
    def total_failed(self) -> int:
        return sum(r.failed for r in self.results)

    @property
    def total_errors(self) -> int:
        return sum(r.errors for r in self.results)

    @property
    def all_passed(self) -> bool:
        return all(r.ok for r in self.results) and not self.parse_errors


def mock_synthesize(produce_type: Any, given: dict, instruction: str,
                    config: MockConfig | None = None,
                    snapshots: dict | None = None,
                    snapshot_key: str = "") -> Any:
    """Generate a deterministic mock response based on the produce type.

    If snapshots are provided and contain the key, return the snapshot value.
    """
    if snapshots and snapshot_key in snapshots:
        return snapshots[snapshot_key]

    cfg = config or MockConfig()

    if isinstance(produce_type, PrimitiveType):
        if produce_type.name == "string":
            return cfg.string_value
        if produce_type.name == "int":
            return cfg.int_value
        if produce_type.name == "float":
            return cfg.float_value
        if produce_type.name == "bool":
            return cfg.bool_value

    if isinstance(produce_type, ArrayType):
        elem = mock_synthesize(produce_type.element_type, given, instruction, cfg)
        return [elem] * cfg.array_length

    if isinstance(produce_type, RecordType):
        result = {}
        for fname, ftype in produce_type.fields.items():
            result[fname] = mock_synthesize(ftype, given, instruction, cfg)
        return result

    return cfg.string_value


def _make_snapshot_key(mandate_name: str, synth_index: int) -> str:
    """Create a deterministic key for snapshot lookup."""
    return f"{mandate_name}:synth:{synth_index}"


def run_test_suite(
    mdt_file: str | Path,
    input_data: dict | None = None,
    mock_config: MockConfig | None = None,
    snapshot_file: Path | None = None,
) -> TestSuiteResult:
    """Run all mandates in a file as a test suite.

    Each mandate is tested independently with mock synthesize.
    Verify blocks are the assertions.
    """
    path = Path(mdt_file)
    source = path.read_text(encoding="utf-8")
    suite = TestSuiteResult(file=str(path))

    try:
        tokens = tokenize(source)
        program = parse(tokens)
    except Exception as e:
        suite.parse_errors.append(str(e))
        return suite

    # Load snapshots if available
    snapshots: dict | None = None
    if snapshot_file and snapshot_file.exists():
        snapshots = json.loads(snapshot_file.read_text(encoding="utf-8"))

    tc_result = check(program)

    cfg = mock_config or MockConfig()
    input_base = input_data or {}

    for mandate in program.mandates:
        test_result = _test_mandate(mandate, input_base, cfg, tc_result, snapshots)
        suite.results.append(test_result)

    return suite


def _test_mandate(
    mandate: MandateBlock,
    input_data: dict,
    config: MockConfig,
    tc_result: Any,
    snapshots: dict | None,
) -> TestResult:
    """Test a single mandate with mock synthesize."""
    result = TestResult(mandate_name=mandate.name)

    # Include type errors as warnings
    result.type_errors = [
        str(e) for e in tc_result.errors
        if mandate.name in str(e)
    ]

    # Build input with mock defaults for missing fields
    test_input = dict(input_data)
    if mandate.input_type:
        for fname, ftype in mandate.input_type.fields.items():
            if fname not in test_input:
                test_input[fname] = mock_synthesize(ftype, {}, "", config)

    # Patch synthesize_call to use mocks
    import mandate.synthesize as synth_module
    original = synth_module.synthesize_call
    synth_counter = [0]

    def mock_call(given, produce_type, instruction, model="mock"):
        key = _make_snapshot_key(mandate.name, synth_counter[0])
        synth_counter[0] += 1
        return mock_synthesize(produce_type, given, instruction, config, snapshots, key)

    try:
        synth_module.synthesize_call = mock_call
        runner = MandateRunner(model="mock")
        run_result = runner.run_mandate(mandate, test_input)
    except Exception as e:
        result.runtime_error = str(e)
        return result
    finally:
        synth_module.synthesize_call = original

    if run_result.runtime_error:
        result.runtime_error = run_result.runtime_error
        return result

    for v in run_result.verify_results:
        result.details.append(v)
        if v.error:
            result.errors += 1
        elif v.passed:
            result.passed += 1
        else:
            result.failed += 1

    return result


def record_snapshots(
    mdt_file: str | Path,
    input_data: dict | None = None,
    model: str = "gpt-4o-mini",
) -> dict:
    """Run mandates with real LLM and record synthesize outputs.

    Returns a dict of snapshot_key -> value that can be saved to a .snap file.
    """
    path = Path(mdt_file)
    source = path.read_text(encoding="utf-8")
    tokens = tokenize(source)
    program = parse(tokens)

    snapshots: dict = {}
    input_base = input_data or {}

    import mandate.synthesize as synth_module
    original = synth_module.synthesize_call

    for mandate in program.mandates:
        test_input = dict(input_base)
        synth_counter = [0]

        def recording_call(given, produce_type, instruction, model=model,
                          _mandate=mandate, _counter=synth_counter):
            result = original(given, produce_type, instruction, model)
            key = _make_snapshot_key(_mandate.name, _counter[0])
            _counter[0] += 1
            snapshots[key] = result
            return result

        try:
            synth_module.synthesize_call = recording_call
            runner = MandateRunner(model=model)
            if mandate.input_type:
                for fname, ftype in mandate.input_type.fields.items():
                    if fname not in test_input:
                        test_input[fname] = mock_synthesize(ftype, {}, "")
            runner.run_mandate(mandate, test_input)
        finally:
            synth_module.synthesize_call = original

    return snapshots
