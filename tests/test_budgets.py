"""Tests for cost budget blocks."""

from pathlib import Path

import pytest
from mandate.lexer import tokenize, TokenType
from mandate.parser import parse
from mandate.ast_nodes import BudgetBlock
from mandate.analyze import analyze


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestBudgetLexer:
    def test_budget_keyword(self):
        tokens = tokenize("budget")
        assert tokens[0].type == TokenType.BUDGET

    def test_max_calls_keyword(self):
        tokens = tokenize("max_calls")
        assert tokens[0].type == TokenType.MAX_CALLS

    def test_max_tokens_keyword(self):
        tokens = tokenize("max_tokens")
        assert tokens[0].type == TokenType.MAX_TOKENS


class TestBudgetParser:
    def test_parse_budget(self):
        src = '''mandate m {
  intent: "T"
  budget { max_calls: 3 }
  flow { return { x: 1 } }
}'''
        program = parse(tokenize(src))
        m = program.mandates[0]
        assert m.budget is not None
        assert m.budget.max_calls == 3
        assert m.budget.max_tokens is None

    def test_parse_budget_both_fields(self):
        src = '''mandate m {
  intent: "T"
  budget {
    max_calls: 5
    max_tokens: 10000
  }
  flow { return { x: 1 } }
}'''
        program = parse(tokenize(src))
        m = program.mandates[0]
        assert m.budget.max_calls == 5
        assert m.budget.max_tokens == 10000

    def test_no_budget(self):
        src = 'mandate m { intent: "T" flow { return { x: 1 } } }'
        program = parse(tokenize(src))
        assert program.mandates[0].budget is None

    def test_parse_budget_example(self):
        source = (EXAMPLES / "with_budget.mdt").read_text(encoding="utf-8")
        program = parse(tokenize(source))
        m = program.mandates[0]
        assert m.budget is not None
        assert m.budget.max_calls == 1


class TestBudgetAnalyzer:
    def test_within_budget(self):
        src = '''mandate m {
  intent: "T"
  budget { max_calls: 2 }
  output: { x: string }
  flow {
    x = synthesize {
      given: "data"
      produce: string
      instruction: "do something"
    }
    return { x: x }
  }
}'''
        report = analyze(parse(tokenize(src)))
        m = report.mandates[0]
        assert m.budget_max_calls == 2
        assert not m.budget_exceeded

    def test_budget_exceeded(self):
        src = '''mandate m {
  intent: "T"
  budget { max_calls: 1 }
  output: { a: string, b: string }
  flow {
    a = synthesize {
      given: "data"
      produce: string
      instruction: "first"
    }
    b = synthesize {
      given: "data"
      produce: string
      instruction: "second"
    }
    return { a: a, b: b }
  }
}'''
        report = analyze(parse(tokenize(src)))
        m = report.mandates[0]
        assert m.budget_exceeded
        assert any("budget exceeded" in w.lower() for w in report.warnings)

    def test_no_budget_no_check(self):
        src = '''mandate m {
  intent: "T"
  output: { x: string }
  flow {
    x = synthesize { given: "d" produce: string instruction: "t" }
    return { x: x }
  }
}'''
        report = analyze(parse(tokenize(src)))
        m = report.mandates[0]
        assert m.budget_max_calls is None
        assert not m.budget_exceeded
