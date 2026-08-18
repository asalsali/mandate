"""Tests for the import system."""

from pathlib import Path

import pytest
from mandate.lexer import tokenize, TokenType
from mandate.parser import parse
from mandate.runner import run_pipeline


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestImportLexer:
    def test_import_keyword(self):
        tokens = tokenize("import")
        assert tokens[0].type == TokenType.IMPORT

    def test_from_keyword(self):
        tokens = tokenize("from")
        assert tokens[0].type == TokenType.FROM


class TestImportParser:
    def test_parse_import(self):
        src = 'import helper from "./helper.mdt"\nmandate m { intent: "T" flow { return { x: 1 } } }'
        program = parse(tokenize(src))
        assert len(program.imports) == 1
        assert program.imports[0].name == "helper"
        assert program.imports[0].path == "./helper.mdt"
        assert len(program.mandates) == 1

    def test_parse_multiple_imports(self):
        src = '''import a from "./a.mdt"
import b from "./b.mdt"
mandate m { intent: "T" flow { return { x: 1 } } }'''
        program = parse(tokenize(src))
        assert len(program.imports) == 2

    def test_parse_with_import_example(self):
        source = (EXAMPLES / "with_import.mdt").read_text(encoding="utf-8")
        program = parse(tokenize(source))
        assert len(program.imports) == 1
        assert program.imports[0].name == "fetch_data"
        assert len(program.mandates) == 1


class TestImportResolution:
    def test_pipeline_with_import(self):
        result = run_pipeline(
            EXAMPLES / "with_import.mdt",
            {"source": "test", "question": "what?"},
        )
        # Import resolves fetch_data, then runs analyze_imported
        assert len(result.stages) == 2
        assert result.stages[0].mandate_name == "fetch_data"
        assert result.stages[1].mandate_name == "analyze_imported"

    def test_import_not_found(self):
        import tempfile, os
        src = 'import nonexistent from "./does_not_exist.mdt"\nmandate m { intent: "T" flow { return { x: 1 } } }'
        with tempfile.NamedTemporaryFile(suffix=".mdt", mode="w", delete=False, encoding="utf-8") as f:
            f.write(src)
            tmp = f.name
        try:
            with pytest.raises(RuntimeError, match="Import not found"):
                run_pipeline(tmp, {})
        finally:
            os.unlink(tmp)
