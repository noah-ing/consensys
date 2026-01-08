"""Hook installer for Claude Code and git integration."""
import os
import stat
from pathlib import Path
from typing import Dict, Optional, List

# Claude Code hooks directory
CLAUDE_CODE_HOOKS_DIR = Path.home() / ".claude" / "hooks"

# Pre-commit hook that runs consensys review
PRE_COMMIT_HOOK = '''#!/bin/bash
# Consensys Review - Pre-commit Hook
# Runs multi-agent code review on staged changes

set -e

# Get staged Python files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.py$' || true)

if [ -z "$STAGED_FILES" ]; then
    echo "No Python files staged, skipping consensys review"
    exit 0
fi

echo "🔍 Running Consensys review on staged changes..."
echo ""

# Run consensys on staged changes
python -m src.cli commit --quick

# Check the exit code
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Consensys review found issues. Fix them or commit with --no-verify"
    exit 1
fi

echo ""
echo "✅ Consensys review passed"
'''

# Claude Code hook that triggers on tool calls
CLAUDE_CODE_HOOK = '''#!/bin/bash
# Consensys Review - Claude Code Hook
# Auto-reviews code written by Claude

EVENT_TYPE="$1"
TOOL_NAME="$2"
FILE_PATH="$3"

# Only run on Write/Edit tool calls to Python files
if [[ "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "Edit" ]]; then
    exit 0
fi

if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    exit 0
fi

# Quick review (no debate, just round 1)
echo "🔍 Quick consensys review of $FILE_PATH..."
python -m src.cli review "$FILE_PATH" --quick 2>/dev/null || true
'''

# Quick review command for hooks (fast, single-round)
QUICK_REVIEW_SCRIPT = '''
# Add --quick option to cli.py for fast reviews
'''


def install_hooks(
    git_hooks: bool = True,
    claude_code_hooks: bool = True,
    repo_path: Optional[Path] = None
) -> Dict[str, bool]:
    """Install consensys hooks.

    Args:
        git_hooks: Install git pre-commit hook
        claude_code_hooks: Install Claude Code hooks
        repo_path: Git repo path (defaults to current directory)

    Returns:
        Dict of hook_name -> success status
    """
    results = {}

    if git_hooks:
        results["git_pre_commit"] = _install_git_hook(repo_path)

    if claude_code_hooks:
        results["claude_code"] = _install_claude_code_hook()

    return results


def uninstall_hooks(
    git_hooks: bool = True,
    claude_code_hooks: bool = True,
    repo_path: Optional[Path] = None
) -> Dict[str, bool]:
    """Uninstall consensys hooks.

    Args:
        git_hooks: Uninstall git pre-commit hook
        claude_code_hooks: Uninstall Claude Code hooks
        repo_path: Git repo path (defaults to current directory)

    Returns:
        Dict of hook_name -> success status
    """
    results = {}

    if git_hooks:
        results["git_pre_commit"] = _uninstall_git_hook(repo_path)

    if claude_code_hooks:
        results["claude_code"] = _uninstall_claude_code_hook()

    return results


def get_hook_status() -> Dict[str, Dict]:
    """Get status of all hooks.

    Returns:
        Dict with hook status information
    """
    status = {}

    # Check git hook
    git_hook_path = _get_git_hooks_dir() / "pre-commit"
    status["git_pre_commit"] = {
        "installed": git_hook_path.exists() if git_hook_path else False,
        "path": str(git_hook_path) if git_hook_path else None
    }

    # Check Claude Code hook
    claude_hook_path = CLAUDE_CODE_HOOKS_DIR / "consensys-review.sh"
    status["claude_code"] = {
        "installed": claude_hook_path.exists(),
        "path": str(claude_hook_path)
    }

    return status


def _get_git_hooks_dir(repo_path: Optional[Path] = None) -> Optional[Path]:
    """Get the git hooks directory for a repo."""
    if repo_path:
        git_dir = repo_path / ".git"
    else:
        # Find git root from current directory
        current = Path.cwd()
        while current != current.parent:
            if (current / ".git").exists():
                git_dir = current / ".git"
                break
            current = current.parent
        else:
            return None

    if not git_dir.exists():
        return None

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    return hooks_dir


def _install_git_hook(repo_path: Optional[Path] = None) -> bool:
    """Install git pre-commit hook."""
    hooks_dir = _get_git_hooks_dir(repo_path)
    if not hooks_dir:
        return False

    hook_path = hooks_dir / "pre-commit"

    # Backup existing hook if present
    if hook_path.exists():
        backup_path = hooks_dir / "pre-commit.backup"
        hook_path.rename(backup_path)

    # Write new hook
    hook_path.write_text(PRE_COMMIT_HOOK)

    # Make executable
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return True


def _uninstall_git_hook(repo_path: Optional[Path] = None) -> bool:
    """Uninstall git pre-commit hook."""
    hooks_dir = _get_git_hooks_dir(repo_path)
    if not hooks_dir:
        return False

    hook_path = hooks_dir / "pre-commit"
    backup_path = hooks_dir / "pre-commit.backup"

    if hook_path.exists():
        hook_path.unlink()

    # Restore backup if exists
    if backup_path.exists():
        backup_path.rename(hook_path)

    return True


def _install_claude_code_hook() -> bool:
    """Install Claude Code hook."""
    try:
        CLAUDE_CODE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)

        hook_path = CLAUDE_CODE_HOOKS_DIR / "consensys-review.sh"
        hook_path.write_text(CLAUDE_CODE_HOOK)

        # Make executable
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Also create a config entry
        config_path = CLAUDE_CODE_HOOKS_DIR / "consensys-config.json"
        config_path.write_text('''{
    "name": "consensys-review",
    "description": "Multi-agent AI code review",
    "trigger": "post_tool",
    "tools": ["Write", "Edit"],
    "file_patterns": ["*.py"],
    "script": "consensys-review.sh"
}''')

        return True
    except Exception:
        return False


def _uninstall_claude_code_hook() -> bool:
    """Uninstall Claude Code hook."""
    try:
        hook_path = CLAUDE_CODE_HOOKS_DIR / "consensys-review.sh"
        config_path = CLAUDE_CODE_HOOKS_DIR / "consensys-config.json"

        if hook_path.exists():
            hook_path.unlink()
        if config_path.exists():
            config_path.unlink()

        return True
    except Exception:
        return False
