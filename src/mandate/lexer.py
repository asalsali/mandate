"""Tokenizer for .mdt files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator


class TokenType(Enum):
    # Keywords
    MANDATE = auto()
    INTENT = auto()
    INPUT = auto()
    OUTPUT = auto()
    REQUIRES = auto()
    FLOW = auto()
    SYNTHESIZE = auto()
    VERIFY = auto()
    HANDOFF = auto()
    GIVEN = auto()
    PRODUCE = auto()
    INSTRUCTION = auto()
    RETURN = auto()
    IF = auto()
    ELSE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IN = auto()
    IS = auto()
    CONTAINS = auto()
    WORKED = auto()
    FAILED = auto()
    NEXT = auto()

    # Delimiters
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COLON = auto()
    COMMA = auto()
    DOT = auto()
    DOTDOT = auto()
    ARROW = auto()

    # Operators
    ASSIGN = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    EQ = auto()
    NEQ = auto()
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    QUESTION = auto()

    # Literals
    STRING = auto()
    NUMBER = auto()
    FLOAT_LIT = auto()
    IDENT = auto()

    # Structural
    NEWLINE = auto()
    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "mandate": TokenType.MANDATE,
    "intent": TokenType.INTENT,
    "input": TokenType.INPUT,
    "output": TokenType.OUTPUT,
    "requires": TokenType.REQUIRES,
    "flow": TokenType.FLOW,
    "synthesize": TokenType.SYNTHESIZE,
    "verify": TokenType.VERIFY,
    "handoff": TokenType.HANDOFF,
    "given": TokenType.GIVEN,
    "produce": TokenType.PRODUCE,
    "instruction": TokenType.INSTRUCTION,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "in": TokenType.IN,
    "is": TokenType.IS,
    "contains": TokenType.CONTAINS,
    "worked": TokenType.WORKED,
    "failed": TokenType.FAILED,
    "next": TokenType.NEXT,
}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        if self.type in (TokenType.STRING, TokenType.NUMBER, TokenType.FLOAT_LIT, TokenType.IDENT):
            return f"Token({self.type.name}, {self.value!r}, L{self.line})"
        return f"Token({self.type.name}, L{self.line})"


class LexError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.line = line
        self.col = col
        super().__init__(f"Lex error at line {line}, col {col}: {message}")


def tokenize(source: str) -> list[Token]:
    """Tokenize Mandate source code into a list of tokens."""
    tokens: list[Token] = []
    i = 0
    line = 1
    col = 1
    length = len(source)

    def advance(n: int = 1) -> None:
        nonlocal i, col
        i += n
        col += n

    def peek(offset: int = 0) -> str:
        pos = i + offset
        return source[pos] if pos < length else ""

    def current() -> str:
        return source[i] if i < length else ""

    while i < length:
        ch = current()

        # Skip whitespace (not newlines)
        if ch in (" ", "\t", "\r"):
            advance()
            continue

        # Newlines
        if ch == "\n":
            tokens.append(Token(TokenType.NEWLINE, "\\n", line, col))
            i += 1
            line += 1
            col = 1
            continue

        # Comments: -- to end of line
        if ch == "-" and peek(1) == "-":
            while i < length and source[i] != "\n":
                i += 1
            continue

        # String literals
        if ch == '"':
            start_line, start_col = line, col
            advance()  # skip opening quote
            string_val = ""
            while i < length and current() != '"':
                if current() == "\\":
                    advance()
                    esc = current()
                    if esc == "n":
                        string_val += "\n"
                    elif esc == "t":
                        string_val += "\t"
                    elif esc == '"':
                        string_val += '"'
                    elif esc == "\\":
                        string_val += "\\"
                    elif esc == "{":
                        string_val += "{"
                    else:
                        string_val += esc
                    advance()
                elif current() == "\n":
                    raise LexError("Unterminated string literal", start_line, start_col)
                else:
                    string_val += current()
                    advance()
            if i >= length:
                raise LexError("Unterminated string literal", start_line, start_col)
            advance()  # skip closing quote
            tokens.append(Token(TokenType.STRING, string_val, start_line, start_col))
            continue

        # Numbers
        if ch.isdigit():
            start_col_num = col
            num_str = ""
            is_float = False
            while i < length and (current().isdigit() or current() == "."):
                if current() == ".":
                    if peek(1) == ".":
                        # This is a range operator .., stop here
                        break
                    is_float = True
                num_str += current()
                advance()
            tok_type = TokenType.FLOAT_LIT if is_float else TokenType.NUMBER
            tokens.append(Token(tok_type, num_str, line, start_col_num))
            continue

        # Identifiers and keywords
        if ch.isalpha() or ch == "_":
            start_col_id = col
            ident = ""
            while i < length and (current().isalnum() or current() == "_"):
                ident += current()
                advance()
            tok_type = KEYWORDS.get(ident, TokenType.IDENT)
            tokens.append(Token(tok_type, ident, line, start_col_id))
            continue

        # Two-character operators
        two = source[i : i + 2] if i + 1 < length else ""
        if two == "->":
            tokens.append(Token(TokenType.ARROW, "->", line, col))
            advance(2)
            continue
        if two == "==":
            tokens.append(Token(TokenType.EQ, "==", line, col))
            advance(2)
            continue
        if two == "!=":
            tokens.append(Token(TokenType.NEQ, "!=", line, col))
            advance(2)
            continue
        if two == ">=":
            tokens.append(Token(TokenType.GTE, ">=", line, col))
            advance(2)
            continue
        if two == "<=":
            tokens.append(Token(TokenType.LTE, "<=", line, col))
            advance(2)
            continue
        if two == "..":
            tokens.append(Token(TokenType.DOTDOT, "..", line, col))
            advance(2)
            continue

        # Single-character tokens
        singles: dict[str, TokenType] = {
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            ":": TokenType.COLON,
            ",": TokenType.COMMA,
            ".": TokenType.DOT,
            "=": TokenType.ASSIGN,
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            ">": TokenType.GT,
            "<": TokenType.LT,
            "?": TokenType.QUESTION,
        }
        if ch in singles:
            tokens.append(Token(singles[ch], ch, line, col))
            advance()
            continue

        raise LexError(f"Unexpected character: {ch!r}", line, col)

    tokens.append(Token(TokenType.EOF, "", line, col))
    return tokens
