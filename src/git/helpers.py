"""Git helper functions for Consensus code review."""
import subprocess
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ChangedFile:
    """Represents a file with changes."""
    path: str
    status: str  # A=added, M=modified, D=deleted, R=renamed
    diff: str
    content: Optional[str] = None


@dataclass
class PRInfo:
    """Information about a GitHub PR."""
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    url: str
    files: List[ChangedFile]


def run_git_command(args: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "git command not found"
    except Exception as e:
        return False, str(e)


def run_gh_command(args: List[str], cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Run a gh CLI command and return (success, output)."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "gh CLI not found. Install from https://cli.github.com"
    except Exception as e:
        return False, str(e)


def is_git_repo(path: Optional[str] = None) -> bool:
    """Check if the current directory is a git repository."""
    success, _ = run_git_command(["rev-parse", "--git-dir"], cwd=path)
    return success


def get_repo_root(path: Optional[str] = None) -> Optional[str]:
    """Get the root directory of the git repository."""
    success, output = run_git_command(["rev-parse", "--show-toplevel"], cwd=path)
    return output if success else None


def get_uncommitted_changes(path: Optional[str] = None) -> List[ChangedFile]:
    """Get all uncommitted changes (both staged and unstaged)."""
    files = []

    # Get list of modified/added/deleted files
    success, output = run_git_command(["status", "--porcelain"], cwd=path)
    if not success or not output:
        return files

    for line in output.split("\n"):
        if not line.strip():
            continue

        # Parse status codes (first two chars)
        status_chars = line[:2]
        filepath = line[3:].strip()

        # Handle renamed files (they have "old -> new" format)
        if " -> " in filepath:
            filepath = filepath.split(" -> ")[1]

        # Determine status
        if "D" in status_chars:
            status = "D"
        elif "A" in status_chars or status_chars[1] == "?":
            status = "A"
        elif "R" in status_chars:
            status = "R"
        else:
            status = "M"

        # Get diff for this file
        if status == "D":
            # For deleted files, show what was removed
            success_diff, diff = run_git_command(["diff", "HEAD", "--", filepath], cwd=path)
            if not success_diff:
                success_diff, diff = run_git_command(["diff", "--cached", "--", filepath], cwd=path)
        elif status == "A" and status_chars[1] == "?":
            # Untracked file - read content directly
            try:
                repo_root = get_repo_root(path)
                if repo_root:
                    with open(f"{repo_root}/{filepath}") as f:
                        content = f.read()
                    diff = f"+++ {filepath}\n" + "\n".join(f"+{line}" for line in content.split("\n"))
                else:
                    diff = ""
            except Exception:
                diff = ""
        else:
            success_diff, diff = run_git_command(["diff", "HEAD", "--", filepath], cwd=path)
            if not success_diff or not diff:
                # Try unstaged diff
                success_diff, diff = run_git_command(["diff", "--", filepath], cwd=path)

        # Try to get current content (for non-deleted files)
        content = None
        if status != "D":
            try:
                repo_root = get_repo_root(path)
                if repo_root:
                    with open(f"{repo_root}/{filepath}") as f:
                        content = f.read()
            except Exception:
                pass

        files.append(ChangedFile(
            path=filepath,
            status=status,
            diff=diff,
            content=content,
        ))

    return files


def get_staged_changes(path: Optional[str] = None) -> List[ChangedFile]:
    """Get staged changes (what would be committed)."""
    files = []

    # Get list of staged files
    success, output = run_git_command(["diff", "--cached", "--name-status"], cwd=path)
    if not success or not output:
        return files

    for line in output.split("\n"):
        if not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status = parts[0][0]  # First char of status
        filepath = parts[-1]  # Last part is the filename

        # Get diff for this file
        success_diff, diff = run_git_command(["diff", "--cached", "--", filepath], cwd=path)

        # Try to get current content (for non-deleted files)
        content = None
        if status != "D":
            try:
                repo_root = get_repo_root(path)
                if repo_root:
                    with open(f"{repo_root}/{filepath}") as f:
                        content = f.read()
            except Exception:
                pass

        files.append(ChangedFile(
            path=filepath,
            status=status,
            diff=diff if success_diff else "",
            content=content,
        ))

    return files


def get_pr_info(pr_number: int, path: Optional[str] = None) -> Optional[PRInfo]:
    """Get information about a GitHub PR using gh CLI."""
    # Get PR metadata
    success, output = run_gh_command([
        "pr", "view", str(pr_number),
        "--json", "number,title,author,baseRefName,headRefName,url"
    ], cwd=path)

    if not success:
        return None

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None

    # Get PR diff/files
    success_diff, diff_output = run_gh_command([
        "pr", "diff", str(pr_number)
    ], cwd=path)

    # Parse diff to get changed files
    files = parse_diff(diff_output if success_diff else "")

    return PRInfo(
        number=data["number"],
        title=data["title"],
        author=data["author"]["login"],
        base_branch=data["baseRefName"],
        head_branch=data["headRefName"],
        url=data["url"],
        files=files,
    )


def parse_diff(diff_text: str) -> List[ChangedFile]:
    """Parse a unified diff into ChangedFile objects."""
    files = []
    current_file = None
    current_diff_lines = []

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Save previous file if exists
            if current_file:
                files.append(ChangedFile(
                    path=current_file,
                    status="M",  # Default to modified
                    diff="\n".join(current_diff_lines),
                ))

            # Extract filename (format: diff --git a/path b/path)
            parts = line.split(" b/")
            if len(parts) >= 2:
                current_file = parts[-1]
            else:
                current_file = line.split()[-1]
            current_diff_lines = [line]

        elif line.startswith("new file"):
            if current_diff_lines:
                current_diff_lines.append(line)
            # Mark as added in next file creation

        elif line.startswith("deleted file"):
            if current_diff_lines:
                current_diff_lines.append(line)
            # Mark as deleted in next file creation

        elif current_file:
            current_diff_lines.append(line)

    # Don't forget the last file
    if current_file:
        # Determine status from diff content
        status = "M"
        diff_content = "\n".join(current_diff_lines)
        if "new file" in diff_content:
            status = "A"
        elif "deleted file" in diff_content:
            status = "D"

        files.append(ChangedFile(
            path=current_file,
            status=status,
            diff=diff_content,
        ))

    return files


def post_pr_comment(pr_number: int, comment: str, path: Optional[str] = None) -> Tuple[bool, str]:
    """Post a comment to a GitHub PR."""
    return run_gh_command([
        "pr", "comment", str(pr_number),
        "--body", comment
    ], cwd=path)


def get_current_branch(path: Optional[str] = None) -> Optional[str]:
    """Get the current git branch name."""
    success, output = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    return output if success else None
