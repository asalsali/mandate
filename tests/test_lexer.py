"""Tests for the Mandate lexer."""

import pytest
from mandate.lexer import tokenize, TokenType, LexError


def test_keyword_tokens():
    tokens = tokenize("mandate flow verify")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.MANDATE in types
    assert TokenType.FLOW in types
    assert TokenType.VERIFY in types


def test_all_keywords():
    kw = "mandate intent input output requires flow synthesize verify handoff"
    tokens = tokenize(kw)
    non_eof = [t for t in tokens if t.type not in (TokenType.EOF, TokenType.NEWLINE)]
    assert len(non_eof) == 9
    assert all(t.type != TokenType.IDENT for t in non_eof)


def test_string_literal():
    tokens = tokenize('"hello world"')
    strings = [t for t in tokens if t.type == TokenType.STRING]
    assert len(strings) == 1
    assert strings[0].value == "hello world"


def test_string_escape():
    tokens = tokenize(r'"line1\nline2"')
    strings = [t for t in tokens if t.type == TokenType.STRING]
    assert strings[0].value == "line1\nline2"


def test_unterminated_string():
    with pytest.raises(LexError):
        tokenize('"no closing quote')


def test_number_literal():
    tokens = tokenize("42")
    nums = [t for t in tokens if t.type == TokenType.NUMBER]
    assert len(nums) == 1
    assert nums[0].value == "42"


def test_float_literal():
    tokens = tokenize("3.14")
    floats = [t for t in tokens if t.type == TokenType.FLOAT_LIT]
    assert len(floats) == 1
    assert floats[0].value == "3.14"


def test_operators():
    tokens = tokenize("== != >= <= -> ..")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.EQ in types
    assert TokenType.NEQ in types
    assert TokenType.GTE in types
    assert TokenType.LTE in types
    assert TokenType.ARROW in types
    assert TokenType.DOTDOT in types


def test_single_char_delimiters():
    tokens = tokenize("{ } ( ) [ ] : , . = + - * /")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.LBRACE in types
    assert TokenType.RBRACE in types
    assert TokenType.LPAREN in types
    assert TokenType.RPAREN in types
    assert TokenType.COLON in types


def test_comment_skipped():
    tokens = tokenize("mandate -- this is a comment\nflow")
    types = [t.type for t in tokens if t.type not in (TokenType.EOF, TokenType.NEWLINE)]
    assert types == [TokenType.MANDATE, TokenType.FLOW]


def test_line_and_col_tracking():
    tokens = tokenize("a\nb")
    idents = [t for t in tokens if t.type == TokenType.IDENT]
    assert idents[0].line == 1
    assert idents[1].line == 2


def test_unexpected_character():
    with pytest.raises(LexError):
        tokenize("@")


def test_identifier():
    tokens = tokenize("my_var")
    idents = [t for t in tokens if t.type == TokenType.IDENT]
    assert len(idents) == 1
    assert idents[0].value == "my_var"


def test_range_vs_float():
    """0.0..1.0 should produce FLOAT_LIT DOTDOT FLOAT_LIT, not a single float."""
    tokens = tokenize("0.0..1.0")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.FLOAT_LIT, TokenType.DOTDOT, TokenType.FLOAT_LIT]
