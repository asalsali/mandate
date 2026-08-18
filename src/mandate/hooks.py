"""Git hook management for Mandate pipelines.

Installs a pre-commit hook that runs a Mandate pipeline on staged diffs.
"""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path


HOOK_TEMPLATE = '''\
#!/bin/sh
# Mandate code review hook — installed by `mandate hook install`
# Runs the code review pipeline on staged changes.

# Get staged diff
DIFF=$(git diff --cached)

if [ -z "$DIFF" ]; then
    exit 0
fi

# Extract first changed file path
FILE_PATH=$(git diff --cached --name-only | head -1)

# Run mandate pipeline
mandate run {pipeline_path} --pipeline -i "$(python3 -c "
import json, sys
diff = sys.stdin.read()
print(json.dumps({{\\"diff\\": diff[:8000], \\"file_path\\": \\"$FILE_PATH\\"}}))" <<< "$DIFF")" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "Mandate review found issues. Commit blocked."
    echo "To skip: git commit --no-verify"
    exit 1
fi
'''

HOOK_MARKER = "# Mandate code review hook"


def find_git_root() -> Path | None:
    """Find the git repository root from the current directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except FileNotFoundError:
        pass
    return None


def get_hook_path(git_root: Path) -> Path:
    """Get the pre-commit hook file path."""
    return git_root / ".git" / "hooks" / "pre-commit"


def install_hook(pipeline_path: str | None = None) -> tuple[bool, str]:
    """Install the Mandate pre-commit hook.

    Returns (success, message).
    """
    git_root = find_git_root()
    if not git_root:
        return False, "Not in a git repository."

    hook_path = get_hook_path(git_root)

    # Check for existing hook
    if hook_path.exists():
        content = hook_path.read_text(encoding="utf-8")
        if HOOK_MARKER in content:
            return False, "Mandate hook already installed."
        # Append to existing hook
        hook_content = "\n\n" + _build_hook(pipeline_path, git_root)
        hook_path.write_text(content + hook_content, encoding="utf-8")
    else:
        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text(_build_hook(pipeline_path, git_root), encoding="utf-8")

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)

    return True, f"Installed Mandate pre-commit hook at {hook_path}"


def uninstall_hook() -> tuple[bool, str]:
    """Remove the Mandate pre-commit hook.

    Returns (success, message).
    """
    git_root = find_git_root()
    if not git_root:
        return False, "Not in a git repository."

    hook_path = get_hook_path(git_root)
    if not hook_path.exists():
        return False, "No pre-commit hook found."

    content = hook_path.read_text(encoding="utf-8")
    if HOOK_MARKER not in content:
        return False, "No Mandate hook found in pre-commit."

    # Remove the mandate hook section
    lines = content.splitlines()
    new_lines: list[str] = []
    skip = False
    for line in lines:
        if HOOK_MARKER in line:
            skip = True
            continue
        if skip and line.strip() == "":
            continue
        if skip and not line.startswith("#") and not line.startswith("mandate") and not line.startswith("EXIT") and not line.startswith("if") and not line.startswith("echo") and not line.startswith("exit") and not line.startswith("DIFF") and not line.startswith("FILE"):
            skip = False
        if not skip:
            new_lines.append(line)

    remaining = "\n".join(new_lines).strip()
    if remaining and remaining != "#!/bin/sh":
        hook_path.write_text(remaining + "\n", encoding="utf-8")
    else:
        hook_path.unlink()

    return True, "Mandate hook removed."


def _build_hook(pipeline_path: str | None, git_root: Path) -> str:
    """Build the hook script content."""
    if pipeline_path:
        resolved = Path(pipeline_path).resolve()
    else:
        # Look for pipelines/code-review/review.mdt relative to git root
        default = git_root / "pipelines" / "code-review" / "review.mdt"
        if default.exists():
            resolved = default
        else:
            resolved = Path("review.mdt")

    return HOOK_TEMPLATE.replace("{pipeline_path}", str(resolved))
