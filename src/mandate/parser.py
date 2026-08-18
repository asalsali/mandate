"""Recursive descent parser for Mandate .mdt files."""

from __future__ import annotations

from typing import Any

from .ast_nodes import (
    ArrayType,
    Assignment,
    BinaryOp,
    FieldAccess,
    FunctionCall,
    HandoffBlock,
    Identifier,
    IfStmt,
    Literal,
    MandateBlock,
    OptionalType,
    PrimitiveType,
    Program,
    RangeExpr,
    RecordType,
    RequiresDecl,
    ReturnStmt,
    SynthesizeExpr,
    UnaryOp,
    VerifyExpr,
)
from .lexer import Token, TokenType, LexError


class ParseError(Exception):
    def __init__(self, message: str, token: Token | None = None):
        self.token = token
        loc = f" at line {token.line}, col {token.col}" if token else ""
        super().__init__(f"Parse error{loc}: {message}")


class Parser:
    """Recursive descent parser for Mandate language."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ----- helpers -----

    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # EOF

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]

    def advance(self) -> Token:
        tok = self.current()
        self.pos += 1
        return tok

    def expect(self, tt: TokenType, value: str | None = None) -> Token:
        tok = self.current()
        if tok.type != tt:
            raise ParseError(
                f"Expected {tt.name}" + (f" ({value!r})" if value else "")
                + f", got {tok.type.name} ({tok.value!r})",
                tok,
            )
        if value is not None and tok.value != value:
            raise ParseError(f"Expected {value!r}, got {tok.value!r}", tok)
        return self.advance()

    def skip_newlines(self) -> None:
        while self.current().type == TokenType.NEWLINE:
            self.advance()

    def at(self, tt: TokenType, value: str | None = None) -> bool:
        tok = self.current()
        if tok.type != tt:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def match(self, tt: TokenType, value: str | None = None) -> Token | None:
        if self.at(tt, value):
            return self.advance()
        return None

    # ----- type parsing -----

    def parse_type(self) -> Any:
        """Parse a type expression: primitive, array, optional, or record."""
        if self.at(TokenType.LBRACE):
            return self.parse_record_type()

        tok = self.expect(TokenType.IDENT)
        name = tok.value
        if name not in ("string", "int", "float", "bool"):
            raise ParseError(f"Unknown type: {name!r}", tok)

        base: Any = PrimitiveType(name)

        # Check for array brackets
        if self.at(TokenType.LBRACKET):
            self.advance()
            self.expect(TokenType.RBRACKET)
            base = ArrayType(base)

        # Check for optional
        if self.at(TokenType.QUESTION):
            self.advance()
            base = OptionalType(base)

        return base

    def parse_record_type(self) -> RecordType:
        """Parse { name: type, ... }."""
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        fields: dict[str, Any] = {}
        while not self.at(TokenType.RBRACE):
            name_tok = self.expect(TokenType.IDENT)
            self.expect(TokenType.COLON)
            ftype = self.parse_type()
            fields[name_tok.value] = ftype
            self.skip_newlines()
            self.match(TokenType.COMMA)
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return RecordType(fields)

    # ----- top-level parsing -----

    def parse_program(self) -> Program:
        """Parse a complete .mdt file."""
        self.skip_newlines()
        mandates: list[MandateBlock] = []
        while not self.at(TokenType.EOF):
            mandates.append(self.parse_mandate())
            self.skip_newlines()
        return Program(mandates)

    def parse_mandate(self) -> MandateBlock:
        """Parse: mandate <name> { ... }."""
        self.skip_newlines()
        self.expect(TokenType.MANDATE)
        name_tok = self.expect(TokenType.IDENT)
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        intent = ""
        input_type: RecordType | None = None
        output_type: RecordType | None = None
        requires: list[RequiresDecl] = []
        flow: list[Any] = []
        verify: list[VerifyExpr] = []
        handoff: HandoffBlock | None = None

        while not self.at(TokenType.RBRACE):
            if self.at(TokenType.INTENT):
                self.advance()
                self.expect(TokenType.COLON)
                intent = self.expect(TokenType.STRING).value
            elif self.at(TokenType.INPUT):
                self.advance()
                self.expect(TokenType.COLON)
                input_type = self.parse_record_type()
            elif self.at(TokenType.OUTPUT):
                self.advance()
                self.expect(TokenType.COLON)
                output_type = self.parse_record_type()
            elif self.at(TokenType.REQUIRES):
                self.advance()
                self.expect(TokenType.COLON)
                requires.append(self.parse_requires_decl())
            elif self.at(TokenType.FLOW):
                self.advance()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                flow = self.parse_flow_body()
                self.expect(TokenType.RBRACE)
            elif self.at(TokenType.VERIFY):
                self.advance()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                verify = self.parse_verify_body()
                self.expect(TokenType.RBRACE)
            elif self.at(TokenType.HANDOFF):
                self.advance()
                self.expect(TokenType.LBRACE)
                self.skip_newlines()
                handoff = self.parse_handoff_body()
                self.expect(TokenType.RBRACE)
            else:
                raise ParseError(
                    f"Unexpected token in mandate body: {self.current().value!r}",
                    self.current(),
                )
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        return MandateBlock(
            name=name_tok.value,
            intent=intent,
            input_type=input_type,
            output_type=output_type,
            requires=requires,
            flow=flow,
            verify=verify,
            handoff=handoff,
        )

    def parse_requires_decl(self) -> RequiresDecl:
        """Parse: name(param: type, ...) -> return_type."""
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params: dict[str, Any] = {}
        while not self.at(TokenType.RPAREN):
            pname = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            ptype = self.parse_type()
            params[pname] = ptype
            self.match(TokenType.COMMA)
        self.expect(TokenType.RPAREN)
        self.expect(TokenType.ARROW)
        ret_type = self.parse_type()
        return RequiresDecl(name=name, params=params, return_type=ret_type)

    # ----- flow parsing -----

    def parse_flow_body(self) -> list[Any]:
        """Parse the contents of a flow { ... } block."""
        stmts: list[Any] = []
        while not self.at(TokenType.RBRACE):
            stmts.append(self.parse_flow_statement())
            self.skip_newlines()
        return stmts

    def parse_flow_statement(self) -> Any:
        """Parse a single flow statement."""
        self.skip_newlines()

        # return { ... }
        if self.at(TokenType.RETURN):
            return self.parse_return()

        # if ... { ... } else { ... }
        if self.at(TokenType.IF):
            return self.parse_if()

        # assignment: ident = expr
        if self.at(TokenType.IDENT) and self.peek(1).type == TokenType.ASSIGN:
            name = self.advance().value
            self.advance()  # skip '='
            expr = self.parse_expression()
            return Assignment(target=name, expression=expr)

        raise ParseError(
            f"Expected flow statement, got {self.current().value!r}",
            self.current(),
        )

    def parse_return(self) -> ReturnStmt:
        """Parse: return { field: value, ... }."""
        self.expect(TokenType.RETURN)
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        fields: dict[str, Any] = {}
        while not self.at(TokenType.RBRACE):
            fname = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            fval = self.parse_expression()
            fields[fname] = fval
            self.skip_newlines()
            self.match(TokenType.COMMA)
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return ReturnStmt(fields=fields)

    def parse_if(self) -> IfStmt:
        """Parse: if <cond> { ... } else { ... }."""
        self.expect(TokenType.IF)
        cond = self.parse_expression()
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        body = self.parse_flow_body()
        self.expect(TokenType.RBRACE)
        self.skip_newlines()
        else_body: list[Any] = []
        if self.match(TokenType.ELSE):
            self.expect(TokenType.LBRACE)
            self.skip_newlines()
            else_body = self.parse_flow_body()
            self.expect(TokenType.RBRACE)
        return IfStmt(condition=cond, body=body, else_body=else_body)

    # ----- expression parsing (precedence climbing) -----

    def parse_expression(self) -> Any:
        """Parse an expression with full precedence."""
        return self.parse_or()

    def parse_or(self) -> Any:
        left = self.parse_and()
        while self.at(TokenType.OR):
            self.advance()
            right = self.parse_and()
            left = BinaryOp(left, "or", right)
        return left

    def parse_and(self) -> Any:
        left = self.parse_not()
        while self.at(TokenType.AND):
            self.advance()
            right = self.parse_not()
            left = BinaryOp(left, "and", right)
        return left

    def parse_not(self) -> Any:
        if self.at(TokenType.NOT):
            self.advance()
            operand = self.parse_not()
            return UnaryOp("not", operand)
        return self.parse_comparison()

    def parse_comparison(self) -> Any:
        left = self.parse_contains()
        ops = {
            TokenType.EQ: "==",
            TokenType.NEQ: "!=",
            TokenType.GT: ">",
            TokenType.LT: "<",
            TokenType.GTE: ">=",
            TokenType.LTE: "<=",
        }
        while self.current().type in ops:
            op_str = ops[self.current().type]
            self.advance()
            right = self.parse_contains()
            left = BinaryOp(left, op_str, right)
        return left

    def parse_contains(self) -> Any:
        left = self.parse_in()
        while self.at(TokenType.CONTAINS):
            self.advance()
            right = self.parse_in()
            left = BinaryOp(left, "contains", right)
        return left

    def parse_in(self) -> Any:
        left = self.parse_is()
        while self.at(TokenType.IN):
            self.advance()
            right = self.parse_addition()
            # Check for range: low..high
            if self.at(TokenType.DOTDOT):
                self.advance()
                high = self.parse_addition()
                right = RangeExpr(right, high)
            left = BinaryOp(left, "in", right)
        return left

    def parse_is(self) -> Any:
        left = self.parse_addition()
        while self.at(TokenType.IS):
            self.advance()
            type_name = self.expect(TokenType.IDENT).value
            left = BinaryOp(left, "is", Literal(type_name, "string"))
        return left

    def parse_addition(self) -> Any:
        left = self.parse_multiplication()
        while self.current().type in (TokenType.PLUS, TokenType.MINUS):
            op = "+" if self.current().type == TokenType.PLUS else "-"
            self.advance()
            right = self.parse_multiplication()
            left = BinaryOp(left, op, right)
        return left

    def parse_multiplication(self) -> Any:
        left = self.parse_unary_minus()
        while self.current().type in (TokenType.STAR, TokenType.SLASH):
            op = "*" if self.current().type == TokenType.STAR else "/"
            self.advance()
            right = self.parse_unary_minus()
            left = BinaryOp(left, op, right)
        return left

    def parse_unary_minus(self) -> Any:
        if self.at(TokenType.MINUS):
            self.advance()
            operand = self.parse_primary()
            return UnaryOp("-", operand)
        return self.parse_primary()

    def parse_primary(self) -> Any:
        """Parse a primary expression: literal, identifier, function call, field access, synthesize, paren."""
        tok = self.current()

        # Synthesize block
        if tok.type == TokenType.SYNTHESIZE:
            return self.parse_synthesize()

        # String literal
        if tok.type == TokenType.STRING:
            self.advance()
            return Literal(tok.value, "string")

        # Number literal
        if tok.type == TokenType.NUMBER:
            self.advance()
            return Literal(int(tok.value), "int")

        # Float literal
        if tok.type == TokenType.FLOAT_LIT:
            self.advance()
            return Literal(float(tok.value), "float")

        # Parenthesized expression
        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr

        # Keywords that can also be identifiers in expression context
        if tok.type in (TokenType.INPUT, TokenType.OUTPUT):
            self.advance()
            node: Any = Identifier(tok.value)
            while True:
                if self.at(TokenType.DOT):
                    self.advance()
                    field_name = self.expect(TokenType.IDENT).value
                    node = FieldAccess(object=node, field=field_name)
                else:
                    break
            return node

        # Identifier (possibly function call or field access)
        if tok.type == TokenType.IDENT:
            # Check for boolean literals
            if tok.value == "true":
                self.advance()
                return Literal(True, "bool")
            if tok.value == "false":
                self.advance()
                return Literal(False, "bool")

            self.advance()
            node: Any = Identifier(tok.value)

            # Function call or field access chain
            while True:
                if self.at(TokenType.LPAREN):
                    # Function call
                    self.advance()
                    args: list[Any] = []
                    while not self.at(TokenType.RPAREN):
                        args.append(self.parse_expression())
                        self.match(TokenType.COMMA)
                    self.expect(TokenType.RPAREN)
                    name = node.name if isinstance(node, Identifier) else str(node)
                    node = FunctionCall(name=name, args=args)
                elif self.at(TokenType.DOT):
                    self.advance()
                    field_name = self.expect(TokenType.IDENT).value
                    node = FieldAccess(object=node, field=field_name)
                else:
                    break
            return node

        raise ParseError(f"Unexpected token in expression: {tok.value!r}", tok)

    def parse_synthesize(self) -> SynthesizeExpr:
        """Parse: synthesize { given: ..., produce: ..., instruction: ... }."""
        self.expect(TokenType.SYNTHESIZE)
        self.expect(TokenType.LBRACE)
        self.skip_newlines()

        given: list[Any] = []
        produce_type: Any = PrimitiveType("string")
        instruction = ""

        while not self.at(TokenType.RBRACE):
            if self.at(TokenType.GIVEN):
                self.advance()
                self.expect(TokenType.COLON)
                # Parse a comma-separated list of expressions
                given.append(self.parse_expression())
                while self.match(TokenType.COMMA):
                    given.append(self.parse_expression())
            elif self.at(TokenType.PRODUCE):
                self.advance()
                self.expect(TokenType.COLON)
                produce_type = self.parse_type()
            elif self.at(TokenType.INSTRUCTION):
                self.advance()
                self.expect(TokenType.COLON)
                instruction = self.expect(TokenType.STRING).value
            else:
                raise ParseError(
                    f"Unexpected token in synthesize block: {self.current().value!r}",
                    self.current(),
                )
            self.skip_newlines()

        self.expect(TokenType.RBRACE)
        return SynthesizeExpr(given=given, produce_type=produce_type, instruction=instruction)

    # ----- verify parsing -----

    def parse_verify_body(self) -> list[VerifyExpr]:
        """Parse the contents of a verify { ... } block."""
        exprs: list[VerifyExpr] = []
        while not self.at(TokenType.RBRACE):
            # Capture the source text span for the expression
            start = self.pos
            expr = self.parse_expression()
            end = self.pos
            source_tokens = self.tokens[start:end]
            source_text = " ".join(t.value for t in source_tokens if t.type != TokenType.NEWLINE)
            exprs.append(VerifyExpr(expression=expr, source=source_text))
            self.skip_newlines()
        return exprs

    # ----- handoff parsing -----

    def parse_handoff_body(self) -> HandoffBlock:
        """Parse the contents of a handoff { ... } block."""
        worked = ""
        failed = ""
        next_rec = ""

        while not self.at(TokenType.RBRACE):
            if self.at(TokenType.WORKED):
                self.advance()
                self.expect(TokenType.COLON)
                worked = self.expect(TokenType.STRING).value
            elif self.at(TokenType.FAILED):
                self.advance()
                self.expect(TokenType.COLON)
                failed = self.expect(TokenType.STRING).value
            elif self.at(TokenType.NEXT):
                self.advance()
                self.expect(TokenType.COLON)
                next_rec = self.expect(TokenType.STRING).value
            else:
                raise ParseError(
                    f"Unexpected token in handoff: {self.current().value!r}",
                    self.current(),
                )
            self.skip_newlines()

        return HandoffBlock(worked=worked, failed=failed, next_recommendation=next_rec)


def parse(tokens: list[Token]) -> Program:
    """Parse a token stream into an AST Program."""
    parser = Parser(tokens)
    return parser.parse_program()
