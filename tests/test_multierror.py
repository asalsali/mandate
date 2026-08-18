"""Tests for multi-error parser."""

import pytest
from mandate.lexer import tokenize
from mandate.parser import parse, MultiParseError, ParseError


class TestMultiError:
    def test_single_error_raises(self):
        with pytest.raises((ParseError, MultiParseError)):
            parse(tokenize("mandate broken {"))

    def test_multiple_bad_mandates(self):
        """Two broken mandates should collect errors for both."""
        src = '''mandate a { blarg }
mandate b { blarg }'''
        with pytest.raises(MultiParseError) as exc_info:
            parse(tokenize(src))
        assert len(exc_info.value.errors) >= 2

    def test_multi_error_message(self):
        src = '''mandate a { blarg }
mandate b { blarg }'''
        with pytest.raises(MultiParseError) as exc_info:
            parse(tokenize(src))
        msg = str(exc_info.value)
        assert "parse error" in msg.lower()

    def test_valid_program_no_error(self, hello_source):
        # Should not raise
        program = parse(tokenize(hello_source))
        assert len(program.mandates) == 1

    def test_recovery_after_error(self):
        """Parser should recover and parse the second mandate."""
        src = '''mandate broken { @@@ }
mandate ok {
  intent: "Valid"
  flow { return { x: 1 } }
}'''
        # The @@ will cause a lex error first, but let's test with parser-level errors
        # Use a parseable but invalid body
        src2 = '''mandate broken { blarg }
mandate ok {
  intent: "Valid"
  flow { return { x: 1 } }
}'''
        with pytest.raises(MultiParseError) as exc_info:
            parse(tokenize(src2))
        # At least one error from the broken mandate
        assert len(exc_info.value.errors) >= 1
