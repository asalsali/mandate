# Mandate

AI code review on every commit. One command.

```bash
pip install mandate-lang
cd your-project
mandate hook install
```

Every commit now gets an AI code review that catches security issues, code quality problems, and missing validations -- before the code reaches your repo.

## What it does

Mandate runs a 3-stage pipeline on your staged changes:

```
Diff Analysis  -->  Security Scan  -->  Code Review
(classify change)   (find vulns)       (verdict + suggestions)
```

Each stage is type-checked against the next. If the security scanner finds a hardcoded API key or command injection, the review stage knows about it. If any stage's assertions fail, the commit is blocked.

```
$ git commit -m "add admin endpoint"

============================================================
  analyze_diff
============================================================
  change_type: feature
  complexity: simple
  summary: Added an admin route to execute shell commands.
  verify: 4/4 passed

============================================================
  scan_security
============================================================
  issues_found: 3
  severity: critical
  findings:
    - Hardcoded secret: API key found.
    - Command injection vulnerability via unsanitized input.
    - Missing input validation for command execution.
  verify: 2/2 passed

============================================================
  generate_review
============================================================
  verdict: request_changes
  risk_level: high
  review: The admin route poses significant security risks...
  suggestions:
    - Remove hardcoded API key, use environment variables.
    - Sanitize input to prevent command injection.
    - Use subprocess with proper arguments.
  verify: 4/4 passed

Pipeline complete: 3 stages, all passed.
```

## How it works

Mandate is a programming language for AI workflows. Each stage in the pipeline is a `.mdt` file with typed inputs, typed outputs, LLM synthesis blocks, and verification assertions.

The language catches errors at compile time -- before any LLM tokens are spent:

```bash
# Type-check the pipeline (are outputs compatible with downstream inputs?)
mandate check review.mdt

# Static analysis (token cost, verify coverage, dead stages)
mandate analyze review.mdt

# Test with mock LLM (no API key needed, runs in CI)
mandate test review.mdt --pipeline
```

### Example mandate

```
mandate scan_security {
  intent: "Scan a diff for security issues"

  input: { diff: string, file_path: string }
  output: { issues_found: int, severity: string, findings: string }

  budget { max_calls: 1 }

  flow {
    scan = synthesize {
      given: input.diff, input.file_path
      produce: { issues_found: int, severity: string, findings: string }
      instruction: "Scan for hardcoded secrets, injection, XSS, path traversal..."
    }
    return { issues_found: scan.issues_found, severity: scan.severity, findings: scan.findings }
  }

  verify {
    output.issues_found >= 0
    output.findings.length > 0
  }
}
```

## Install

```bash
pip install mandate-lang
```

Requires Python 3.10+. For LLM features, set `OPENAI_API_KEY`. For testing and static analysis, no API key needed.

### Local LLM (Ollama)

```bash
mandate run review.mdt --pipeline --model codellama:34b
```

## CLI

```
mandate check <file>              Type-check (including cross-stage pipeline types)
mandate analyze <file>            Static analysis: dependency graph, token cost, coverage
mandate test <file> [--pipeline]  Run verify blocks with mock LLM (CI-friendly)
mandate run <file> [--pipeline]   Execute with real LLM
mandate fmt <file> [--write]      Auto-format to canonical style
mandate hook install              Install pre-commit git hook
mandate hook uninstall            Remove hook
mandate parse <file>              Display AST
mandate transpile <file>          Generate Python
mandate air <file>                Output AIR JSON
```

## Language features

- **Types**: `string`, `int`, `float`, `bool`, `T[]`, `T?`, `{ field: type }`, `enum`, `A | B`
- **Imports**: `import scan from "./scanner.mdt"`
- **Pipeline chaining**: output of stage N flows into input of stage N+1
- **Budgets**: `budget { max_calls: 3 }` -- enforced at analysis time
- **Verify assertions**: `output.score in 0.0..1.0`, `output.data contains "expected"`
- **Handoff metadata**: structured agent-to-agent coordination
- **Multi-error parser**: reports all errors, not just the first
- **Snapshot testing**: record LLM outputs, replay without API calls

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v   # 168 tests
```

## License

MIT. Copyright (c) 2026 Alex Salsali.
