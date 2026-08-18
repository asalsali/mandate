#!/usr/bin/env python3
"""Run the code review pipeline on a git diff.

Usage:
    # Review staged changes
    python run_review.py

    # Review a specific commit
    python run_review.py HEAD~1

    # Review a diff file
    python run_review.py --file changes.diff

    # Test mode (no API key needed)
    python run_review.py --test
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Add mandate to path if running from source
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from mandate.runner import run_pipeline
from mandate.testing import run_test_suite


PIPELINE_DIR = Path(__file__).resolve().parent
REVIEW_MDT = PIPELINE_DIR / "review.mdt"


def get_diff(ref: str | None = None) -> str:
    """Get git diff from the current repo."""
    if ref:
        cmd = ["git", "diff", ref]
    else:
        # Staged changes, or if none, last commit
        result = subprocess.run(
            ["git", "diff", "--cached"], capture_output=True, text=True
        )
        if result.stdout.strip():
            return result.stdout
        cmd = ["git", "diff", "HEAD~1"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting diff: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Code review via Mandate pipeline")
    parser.add_argument("ref", nargs="?", help="Git ref to diff against (e.g. HEAD~1)")
    parser.add_argument("--file", "-f", help="Read diff from a file instead of git")
    parser.add_argument("--test", "-t", action="store_true", help="Run in test mode (mock LLM)")
    parser.add_argument("--model", "-m", default="gpt-4o-mini", help="LLM model")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if args.test:
        print("Running test suite (mock mode)...\n")
        suite = run_test_suite(REVIEW_MDT)
        for r in suite.results:
            status = "PASS" if r.ok else "FAIL"
            print(f"  {status}  {r.mandate_name} ({r.passed} passed, {r.failed} failed)")
            if r.runtime_error:
                print(f"         Error: {r.runtime_error}")
            for v in r.details:
                if not v.passed:
                    print(f"         x {v.expression}: {v.error or v.actual_value}")
        total = sum(r.total for r in suite.results)
        passed = sum(r.passed for r in suite.results)
        print(f"\n{passed}/{total} assertions passed across {len(suite.results)} mandates")
        sys.exit(0 if suite.all_passed else 1)

    # Get the diff
    if args.file:
        diff = Path(args.file).read_text(encoding="utf-8")
    else:
        diff = get_diff(args.ref)

    if not diff.strip():
        print("No changes to review.")
        sys.exit(0)

    # Extract file path from diff (first file mentioned)
    file_path = "unknown"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            file_path = line[6:]
            break
        elif line.startswith("diff --git"):
            parts = line.split()
            if len(parts) >= 4:
                file_path = parts[3].lstrip("b/")
                break

    # Run the pipeline
    input_data = {
        "diff": diff[:8000],  # Truncate very large diffs
        "file_path": file_path,
    }

    try:
        result = run_pipeline(
            REVIEW_MDT,
            input_data,
            model=args.model,
        )
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        output = {
            "stages": [
                {"mandate": s.mandate_name, "output": s.output, "passed": s.all_passed}
                for s in result.stages
            ],
            "all_passed": result.all_passed,
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        # Human-readable output
        for stage in result.stages:
            print(f"\n{'='*60}")
            print(f"  {stage.mandate_name}")
            print(f"{'='*60}")
            for key, value in stage.output.items():
                if isinstance(value, str) and len(value) > 80:
                    print(f"  {key}:")
                    for line in value.split("\n"):
                        print(f"    {line}")
                else:
                    print(f"  {key}: {value}")

            if stage.verify_results:
                passed = sum(1 for v in stage.verify_results if v.passed)
                total = len(stage.verify_results)
                print(f"  verify: {passed}/{total} passed")

        if not result.all_passed:
            print("\nSome verifications failed.")
            sys.exit(1)


if __name__ == "__main__":
    main()
