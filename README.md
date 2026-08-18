# Mandate

An agent-native programming language for composable, verifiable AI workflows.

Mandate lets you define structured AI tasks with built-in type checking, LLM synthesis, verification assertions, and handoff metadata -- all in a single `.mdt` file.

## Install

```bash
pip install mandate-lang
```

From source:

```bash
git clone https://github.com/asalsali/mandate.git
cd mandate
pip install -e ".[dev]"
```

## Quick Start

Create `hello.mdt`:

```
mandate hello {
  intent: "Greet a user by name"

  input: { name: string }
  output: { greeting: string }

  flow {
    greeting = synthesize {
      given: input.name
      produce: string
      instruction: "Write a warm, friendly greeting for this person by name"
    }
    return { greeting: greeting }
  }

  verify {
    output.greeting.length > 0
  }
}
```

Run it:

```bash
mandate run hello.mdt --input '{"name": "Alice"}'
```

## Language Reference

### Mandate Block

Every `.mdt` file contains one or more `mandate` blocks:

```
mandate <name> {
  intent: "<human-readable description>"
  input: { <field>: <type>, ... }
  output: { <field>: <type>, ... }
  requires: <function>(<param>: <type>, ...) -> <return_type>
  flow { ... }
  verify { ... }
  handoff { ... }
}
```

### Types

| Type | Syntax | Example |
|------|--------|---------|
| Primitives | `string`, `int`, `float`, `bool` | `name: string` |
| Arrays | `T[]` | `numbers: int[]` |
| Optionals | `T?` | `note: string?` |
| Records | `{ field: type, ... }` | `{ x: int, y: int }` |

### Flow Blocks

Flow blocks contain the mandate's executable logic:

```
flow {
  x = 42
  y = sort(input.numbers)
  if input.x > 10 {
    return { label: "big" }
  } else {
    return { label: "small" }
  }
}
```

Supported statements: assignments, `return { ... }`, `if`/`else`.

Built-in functions: `len`, `sort`, `str`, `int`, `float`, `abs`.

### Synthesize Blocks

Synthesize blocks call an LLM to generate output:

```
result = synthesize {
  given: input.name, input.context
  produce: string
  instruction: "Generate a summary based on the given data"
}
```

- `given` -- expressions passed as context to the LLM
- `produce` -- the expected output type
- `instruction` -- the prompt sent to the LLM

When no `OPENAI_API_KEY` is set, synthesize runs in **stub mode** and returns plausible defaults for testing.

### Requires

Declare external function dependencies:

```
requires: fetch_price(symbol: string) -> float
```

External functions are injected at runtime via the `external_functions` parameter.

### Verify Blocks

Boolean assertions checked against the mandate's output:

```
verify {
  output.score > 0.5
  output.score in 0.0..1.0
  output.summary.length > 0
  output.tags contains "important"
}
```

Supported operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `not`, `contains`, `in` (with range `low..high`).

### Handoff Blocks

Structured metadata for agent coordination:

```
handoff {
  worked: "Found relevant data in 3 sources"
  failed: "API rate limit hit on source 4"
  next: "Deep dive into source 2 findings"
}
```

## CLI Commands

### `mandate parse <file>`

Display the AST structure of a `.mdt` file.

### `mandate check <file>`

Type-check and validate a `.mdt` file. Reports missing intents, undefined variables, output field mismatches, and unknown functions. For multi-mandate files, also verifies cross-mandate type compatibility (output fields of mandate N must cover input fields of mandate N+1).

### `mandate transpile <file>`

Generate equivalent Python code from a `.mdt` file.

### `mandate run <file> [--input JSON] [--model NAME] [--pipeline]`

Execute a `.mdt` file end-to-end: lex, parse, type-check, run flow, call LLM for synthesize blocks, and evaluate verify assertions.

```bash
mandate run sort_array.mdt --input '{"numbers": [3, 1, 2]}'
```

With `--pipeline`, run all mandates in the file as a chained pipeline -- output of mandate N is merged into the input of mandate N+1:

```bash
mandate run pipeline.mdt --input '{"source": "sales", "question": "trend?"}' --pipeline
```

### `mandate analyze <file>`

Static analysis: dependency graph, token cost estimate, verify coverage, dead mandate detection. This is whole-program analysis that catches issues before any LLM tokens are spent.

```bash
mandate analyze pipeline.mdt
```

Reports:
- Per-mandate synthesize count and verify coverage
- Pipeline data dependencies (which fields flow between mandates)
- Estimated LLM calls
- Dead mandates (output never consumed downstream)
- Unverified output fields

### `mandate air <file> [--lineage JSON]`

Output the Agent Intermediate Representation (AIR) -- a JSON serialization of the mandate's AST, verification results, and lineage metadata.

```bash
mandate air hello.mdt --lineage '{"author": "alex", "generation": 1}'
```

## AIR (Agent Intermediate Representation)

AIR is a JSON format that serializes mandates for agent consumption:

- **version** -- schema version (`air-1.0`)
- **mandate** -- name and intent
- **lineage** -- author, generation, parent chain
- **ast** -- full AST (input/output types, flow statements, verify expressions)
- **verification** -- pass/fail counts and per-assertion results
- **confidence** -- ratio of passed assertions
- **handoff** -- structured coordination metadata

AIR enables agents to consume, transform, and chain mandates programmatically.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

106 tests covering lexer, parser, type checker, transpiler, AIR serializer, runner, verify engine, pipeline execution, and static analyzer.

## License

MIT License. Copyright (c) 2026 Alex Salsali.
