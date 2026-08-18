"""Shared fixtures for Mandate tests."""

import os
from pathlib import Path

import pytest


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def examples_dir():
    return EXAMPLES_DIR


@pytest.fixture
def hello_source():
    return (EXAMPLES_DIR / "hello.mdt").read_text(encoding="utf-8")


@pytest.fixture
def sort_source():
    return (EXAMPLES_DIR / "sort_array.mdt").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch):
    """Ensure stub mode for all tests."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
