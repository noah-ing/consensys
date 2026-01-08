"""Git helper functions for Consensys code review."""
import subprocess
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple, TYPE_CHECKING


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


def get_file_diff_vs_head(filepath: str, context_lines: int = 3, path: Optional[str] = None) -> Optional[str]:
    """Get the diff of a specific file against HEAD.

    Args:
        filepath: Path to the file relative to repo root
        context_lines: Number of context lines around changes (default 3)
        path: Working directory for git command

    Returns:
        The diff output, or None if file is not modified or not in git
    """
    # First check if the file has any changes vs HEAD
    success, output = run_git_command(
        ["diff", f"--unified={context_lines}", "HEAD", "--", filepath],
        cwd=path
    )

    if success and output.strip():
        return output

    # Also check if file is untracked but exists
    success_status, status = run_git_command(["status", "--porcelain", "--", filepath], cwd=path)
    if success_status and status.strip():
        # File has some status (untracked, staged, etc.)
        # For untracked files, return the entire file as "added"
        if status.strip().startswith("??"):
            try:
                repo_root = get_repo_root(path)
                full_path = f"{repo_root}/{filepath}" if repo_root else filepath
                with open(full_path) as f:
                    content = f.read()
                # Format as diff-like output
                lines = content.split("\n")
                diff_lines = [f"diff --git a/{filepath} b/{filepath}"]
                diff_lines.append("new file mode 100644")
                diff_lines.append(f"--- /dev/null")
                diff_lines.append(f"+++ b/{filepath}")
                diff_lines.append(f"@@ -0,0 +1,{len(lines)} @@")
                for line in lines:
                    diff_lines.append(f"+{line}")
                return "\n".join(diff_lines)
            except Exception:
                pass

        # Try staged diff
        success_staged, staged_diff = run_git_command(
            ["diff", f"--unified={context_lines}", "--cached", "--", filepath],
            cwd=path
        )
        if success_staged and staged_diff.strip():
            return staged_diff

    return None


@dataclass
class DiffContext:
    """Context information for a file diff review."""
    original_file: str       # Path to original file
    diff_text: str           # The actual diff
    changed_line_ranges: List[Tuple[int, int]]  # List of (start, end) line ranges that changed
    context_code: str        # Code around the changes with context
    is_new_file: bool        # True if this is a new untracked file


def extract_diff_context(filepath: str, context_lines: int = 5, path: Optional[str] = None) -> Optional[DiffContext]:
    """Extract diff and surrounding context for a file.

    This function gets the diff for a file and extracts the changed regions
    with additional context lines, creating a focused view for code review.

    Args:
        filepath: Path to the file
        context_lines: Number of extra context lines around changes
        path: Working directory for git command

    Returns:
        DiffContext with the diff and focused code, or None if no changes
    """
    import re

    diff_text = get_file_diff_vs_head(filepath, context_lines=context_lines, path=path)
    if not diff_text:
        return None

    # Parse the diff to find changed line ranges
    changed_ranges: List[Tuple[int, int]] = []
    is_new_file = "new file" in diff_text

    # Parse @@ -old,count +new,count @@ lines to find changed regions
    hunk_pattern = r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@"
    for match in re.finditer(hunk_pattern, diff_text):
        start_line = int(match.group(1))
        count = int(match.group(2)) if match.group(2) else 1
        # Extend range with context
        range_start = max(1, start_line - context_lines)
        range_end = start_line + count + context_lines
        changed_ranges.append((range_start, range_end))

    # Merge overlapping ranges
    if changed_ranges:
        changed_ranges.sort()
        merged = [changed_ranges[0]]
        for start, end in changed_ranges[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        changed_ranges = merged

    # Read the full file and extract relevant sections
    context_code = ""
    try:
        repo_root = get_repo_root(path)
        full_path = f"{repo_root}/{filepath}" if repo_root else filepath
        with open(full_path) as f:
            lines = f.readlines()

        if is_new_file:
            # For new files, include everything
            context_code = "".join(lines)
        elif changed_ranges:
            # Extract sections around changes
            sections = []
            for start, end in changed_ranges:
                start_idx = max(0, start - 1)  # Convert to 0-indexed
                end_idx = min(len(lines), end)
                section_lines = lines[start_idx:end_idx]

                # Add line numbers as comments for context
                numbered_lines = []
                for i, line in enumerate(section_lines, start=start_idx + 1):
                    numbered_lines.append(f"{i:4d}: {line.rstrip()}")

                sections.append("\n".join(numbered_lines))

            context_code = "\n\n# ... (unchanged code) ...\n\n".join(sections)
        else:
            context_code = "".join(lines)

    except Exception:
        # Fall back to just using the diff
        context_code = diff_text

    return DiffContext(
        original_file=filepath,
        diff_text=diff_text,
        changed_line_ranges=changed_ranges,
        context_code=context_code,
        is_new_file=is_new_file,
    )
