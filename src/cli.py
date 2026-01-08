"""CLI interface for Consensus multi-agent code review."""
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text

from src.orchestrator.debate import DebateOrchestrator
from src.db.storage import Storage
from src.models.review import VoteDecision
from src.git.helpers import (
    is_git_repo,
    get_repo_root,
    get_uncommitted_changes,
    get_staged_changes,
    get_pr_info,
    post_pr_comment,
    get_current_branch,
)
from src.export.exporter import DebateExporter


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="consensus")
def cli():
    """Consensus - Multi-agent AI code review with debate and voting.

    Run code reviews with multiple AI experts who discuss, debate, and
    vote on code quality. Each expert has a unique perspective:

    \b
    - SecurityExpert: Focuses on vulnerabilities and security issues
    - PerformanceEngineer: Analyzes efficiency and optimization
    - ArchitectureCritic: Evaluates design patterns and structure
    - PragmaticDev: Balances practicality with best practices
    """
    pass


@cli.command()
@click.argument("file", required=False, type=click.Path(exists=True))
@click.option("--code", "-c", help="Review inline code snippet instead of a file")
@click.option("--context", "-x", help="Additional context about the code")
def review(file: Optional[str], code: Optional[str], context: Optional[str]):
    """Run a full debate review on code.

    Review a file:
        consensus review path/to/file.py

    Review inline code:
        consensus review --code 'def foo(): pass'

    Add context:
        consensus review file.py --context 'This is a critical auth function'
    """
    # Get code from file or --code option
    if file:
        file_path = Path(file)
        try:
            code_content = file_path.read_text()
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            sys.exit(1)
        context = context or f"File: {file_path.name}"
    elif code:
        code_content = code
    else:
        console.print("[red]Error: Provide either a file path or --code option[/red]")
        console.print("Run 'consensus review --help' for usage.")
        sys.exit(1)

    # Display what we're reviewing
    console.print()
    console.print(Panel(
        Syntax(code_content, "python", theme="monokai", line_numbers=True),
        title="[bold cyan]Code Under Review[/bold cyan]",
        border_style="cyan",
    ))

    if context:
        console.print(f"[dim]Context: {context}[/dim]")

    console.print()

    # Run the full debate
    try:
        orchestrator = DebateOrchestrator()
        consensus = orchestrator.run_full_debate(code_content, context)

        # Print session ID for replay
        console.print()
        console.print(
            f"[dim]Session ID: {orchestrator.session_id}[/dim]"
        )
        console.print(
            f"[dim]Replay with: consensus replay {orchestrator.session_id}[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error during review: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of sessions to show")
def history(limit: int):
    """Show past review sessions.

    Lists recent review sessions with their IDs, dates, and final decisions.
    Use 'consensus replay <session_id>' to view a past debate.
    """
    storage = Storage()
    sessions = storage.list_sessions(limit=limit)

    if not sessions:
        console.print("[yellow]No review sessions found.[/yellow]")
        console.print("Run 'consensus review <file>' to start a review.")
        return

    table = Table(
        title=f"Recent Review Sessions (last {limit})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Session ID", style="dim")
    table.add_column("Date", style="blue")
    table.add_column("Decision", justify="center")
    table.add_column("Code Preview", max_width=40)

    decision_colors = {
        "APPROVE": "green",
        "REJECT": "red",
        "ABSTAIN": "yellow",
    }

    for session in sessions:
        session_id = session["session_id"]
        created_at = session["created_at"][:16].replace("T", " ")
        decision = session.get("final_decision") or "In Progress"
        color = decision_colors.get(decision, "dim")
        decision_styled = f"[{color}]{decision}[/{color}]"

        # Truncate code preview
        code_preview = session["code_snippet"][:37] + "..." if len(
            session["code_snippet"]
        ) > 40 else session["code_snippet"]
        code_preview = code_preview.replace("\n", " ")

        table.add_row(
            session_id[:12] + "...",
            created_at,
            decision_styled,
            code_preview,
        )

    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Use 'consensus replay <session_id>' to view a session[/dim]")


@cli.command()
@click.argument("session_id")
def replay(session_id: str):
    """Replay a past debate session.

    Shows the complete debate history: code, reviews, responses,
    votes, and final consensus.
    """
    storage = Storage()

    # Handle partial session ID matching
    sessions = storage.list_sessions(limit=100)
    matching = [s for s in sessions if s["session_id"].startswith(session_id)]

    if not matching:
        console.print(f"[red]Session not found: {session_id}[/red]")
        console.print("Run 'consensus history' to see available sessions.")
        return

    if len(matching) > 1:
        console.print(f"[yellow]Multiple sessions match '{session_id}':[/yellow]")
        for s in matching[:5]:
            console.print(f"  {s['session_id']}")
        console.print("Please provide a more specific session ID.")
        return

    full_session_id = matching[0]["session_id"]
    session = storage.get_session(full_session_id)

    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        return

    console.print()
    console.print(Panel(
        f"[bold]Session:[/bold] {full_session_id}\n"
        f"[bold]Date:[/bold] {session['created_at'][:19].replace('T', ' ')}\n"
        f"[bold]Status:[/bold] {session.get('final_decision') or 'In Progress'}",
        title="[bold cyan]Debate Replay[/bold cyan]",
        border_style="cyan",
    ))

    # Show the code
    console.print()
    console.print(Panel(
        Syntax(session["code_snippet"], "python", theme="monokai", line_numbers=True),
        title="[bold]Code Under Review[/bold]",
        border_style="dim",
    ))

    if session.get("context"):
        console.print(f"[dim]Context: {session['context']}[/dim]")

    # Load and display reviews
    reviews = storage.get_reviews(full_session_id)
    if reviews:
        console.print()
        console.rule("[bold blue]Round 1: Initial Reviews[/bold blue]")
        console.print()

        severity_colors = {
            "CRITICAL": "red",
            "HIGH": "red",
            "MEDIUM": "yellow",
            "LOW": "green",
        }

        for review in reviews:
            color = severity_colors.get(review.severity, "blue")

            content_lines = []
            content_lines.append(f"[bold]Severity:[/bold] [{color}]{review.severity}[/{color}]")
            content_lines.append(f"[bold]Confidence:[/bold] {review.confidence:.0%}")

            if review.issues:
                content_lines.append(f"\n[bold]Issues ({len(review.issues)}):[/bold]")
                for issue in review.issues:
                    desc = issue.get("description", str(issue))
                    sev = issue.get("severity", "LOW")
                    sev_color = severity_colors.get(sev, "blue")
                    content_lines.append(f"  [{sev_color}]\u2022[/{sev_color}] {desc}")

            if review.suggestions:
                content_lines.append(f"\n[bold]Suggestions:[/bold]")
                for suggestion in review.suggestions:
                    content_lines.append(f"  [cyan]\u2022[/cyan] {suggestion}")

            if review.summary:
                content_lines.append(f"\n[bold]Summary:[/bold]\n{review.summary}")

            panel = Panel(
                "\n".join(content_lines),
                title=f"[bold]{review.agent_name}[/bold]",
                border_style=color,
                padding=(1, 2),
            )
            console.print(panel)
            console.print()

    # Load and display responses
    responses = storage.get_responses(full_session_id)
    if responses:
        console.print()
        console.rule("[bold blue]Round 2: Debate Responses[/bold blue]")
        console.print()

        agreement_colors = {
            "AGREE": "green",
            "PARTIAL": "yellow",
            "DISAGREE": "red",
        }

        for response in responses:
            color = agreement_colors.get(response.agreement_level, "blue")

            content_lines = []
            content_lines.append(
                f"[bold]{response.agent_name}[/bold] responds to "
                f"[bold]{response.responding_to}[/bold]"
            )
            content_lines.append(
                f"[bold]Agreement:[/bold] [{color}]{response.agreement_level}[/{color}]"
            )

            if response.points:
                content_lines.append(f"\n[bold]Points:[/bold]")
                for point in response.points:
                    content_lines.append(f"  [cyan]\u2022[/cyan] {point}")

            panel = Panel(
                "\n".join(content_lines),
                title=f"[bold]{response.agent_name} \u2192 {response.responding_to}[/bold]",
                border_style=color,
                padding=(1, 2),
            )
            console.print(panel)
            console.print()

    # Load and display votes
    votes = storage.get_votes(full_session_id)
    if votes:
        console.print()
        console.rule("[bold blue]Round 3: Final Voting[/bold blue]")
        console.print()

        decision_colors = {
            "APPROVE": "green",
            "REJECT": "red",
            "ABSTAIN": "yellow",
        }

        for vote in votes:
            decision_str = vote.decision.value if isinstance(
                vote.decision, VoteDecision
            ) else str(vote.decision)
            color = decision_colors.get(decision_str, "blue")

            content_lines = []
            content_lines.append(f"[bold]Vote:[/bold] [{color}]{decision_str}[/{color}]")
            content_lines.append(f"\n[bold]Reasoning:[/bold]\n{vote.reasoning}")

            panel = Panel(
                "\n".join(content_lines),
                title=f"[bold]{vote.agent_name}[/bold]",
                border_style=color,
                padding=(1, 2),
            )
            console.print(panel)
            console.print()

    # Load and display consensus
    consensus = storage.get_consensus(full_session_id)
    if consensus:
        console.print()
        console.rule("[bold blue]Final Consensus[/bold blue]")
        console.print()

        decision_colors = {
            VoteDecision.APPROVE: "green",
            VoteDecision.REJECT: "red",
            VoteDecision.ABSTAIN: "yellow",
        }
        color = decision_colors.get(consensus.final_decision, "blue")
        decision_str = consensus.final_decision.value

        content_lines = []
        content_lines.append("[bold]Vote Breakdown:[/bold]")
        content_lines.append(
            f"  [green]APPROVE[/green]: {consensus.vote_counts.get('APPROVE', 0)}"
        )
        content_lines.append(
            f"  [red]REJECT[/red]: {consensus.vote_counts.get('REJECT', 0)}"
        )
        content_lines.append(
            f"  [yellow]ABSTAIN[/yellow]: {consensus.vote_counts.get('ABSTAIN', 0)}"
        )

        if consensus.key_issues:
            content_lines.append(f"\n[bold]Key Issues ({len(consensus.key_issues)}):[/bold]")
            for issue in consensus.key_issues:
                desc = issue.get("description", str(issue))
                content_lines.append(f"  [red]\u2022[/red] {desc}")

        if consensus.accepted_suggestions:
            content_lines.append(
                f"\n[bold]Agreed Suggestions ({len(consensus.accepted_suggestions)}):[/bold]"
            )
            for suggestion in consensus.accepted_suggestions:
                content_lines.append(f"  [cyan]\u2022[/cyan] {suggestion}")

        panel = Panel(
            "\n".join(content_lines),
            title=f"[bold {color}]Final Decision: {decision_str}[/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
        console.print(panel)
        console.print()


def _detect_language(filepath: str) -> str:
    """Detect programming language from file extension."""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "bash",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".md": "markdown",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
    }
    for ext, lang in ext_map.items():
        if filepath.endswith(ext):
            return lang
    return "text"


def _review_file_changes(files, context_prefix: str = "") -> Optional[str]:
    """Review a list of changed files and return the session ID."""
    if not files:
        console.print("[yellow]No changes found to review.[/yellow]")
        return None

    orchestrator = DebateOrchestrator()
    session_id = None

    for i, file in enumerate(files, 1):
        console.print()
        console.print(f"[bold cyan]Reviewing file {i}/{len(files)}: {file.path}[/bold cyan]")

        # Display the diff
        lang = _detect_language(file.path)
        console.print(Panel(
            Syntax(file.diff or "(no diff)", "diff", theme="monokai", line_numbers=True),
            title=f"[bold]Diff: {file.path}[/bold]",
            border_style="cyan",
        ))

        # Prepare code for review (prefer diff, fall back to content)
        code_to_review = file.diff if file.diff else (file.content or "")
        if not code_to_review.strip():
            console.print(f"[dim]Skipping {file.path} - no content to review[/dim]")
            continue

        context = f"{context_prefix}File: {file.path} (Status: {file.status})"

        try:
            consensus = orchestrator.run_full_debate(code_to_review, context)
            session_id = orchestrator.session_id
        except Exception as e:
            console.print(f"[red]Error reviewing {file.path}: {e}[/red]")
            continue

    return session_id


@cli.command()
@click.argument("pr_number", type=int)
@click.option("--post", is_flag=True, help="Post summary comment to the PR")
def pr(pr_number: int, post: bool):
    """Review a GitHub Pull Request.

    Fetches the PR diff and runs a full debate on the changed files.

    \b
    Examples:
        consensus pr 123
        consensus pr 123 --post  # Post summary to PR

    Requires: gh CLI (https://cli.github.com) authenticated
    """
    console.print()
    console.print(f"[bold cyan]Fetching PR #{pr_number}...[/bold cyan]")

    pr_info = get_pr_info(pr_number)
    if not pr_info:
        console.print("[red]Error: Could not fetch PR. Is gh CLI installed and authenticated?[/red]")
        console.print("[dim]Install from: https://cli.github.com[/dim]")
        sys.exit(1)

    console.print(Panel(
        f"[bold]PR #{pr_info.number}:[/bold] {pr_info.title}\n"
        f"[bold]Author:[/bold] {pr_info.author}\n"
        f"[bold]Branch:[/bold] {pr_info.head_branch} -> {pr_info.base_branch}\n"
        f"[bold]Files:[/bold] {len(pr_info.files)} changed\n"
        f"[bold]URL:[/bold] {pr_info.url}",
        title="[bold cyan]Pull Request[/bold cyan]",
        border_style="cyan",
    ))

    if not pr_info.files:
        console.print("[yellow]No files changed in this PR.[/yellow]")
        return

    session_id = _review_file_changes(pr_info.files, context_prefix=f"PR #{pr_number}: ")

    if session_id:
        console.print()
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        console.print(f"[dim]Replay with: consensus replay {session_id}[/dim]")

        if post:
            # Build summary comment
            storage = Storage()
            consensus_result = storage.get_consensus(session_id)
            if consensus_result:
                decision_str = consensus_result.final_decision.value
                comment = f"""## Consensus Code Review

**Decision:** {decision_str}

**Vote Breakdown:**
- APPROVE: {consensus_result.vote_counts.get('APPROVE', 0)}
- REJECT: {consensus_result.vote_counts.get('REJECT', 0)}
- ABSTAIN: {consensus_result.vote_counts.get('ABSTAIN', 0)}

"""
                if consensus_result.key_issues:
                    comment += "**Key Issues:**\n"
                    for issue in consensus_result.key_issues[:5]:
                        desc = issue.get("description", str(issue))
                        comment += f"- {desc}\n"
                    comment += "\n"

                if consensus_result.accepted_suggestions:
                    comment += "**Agreed Suggestions:**\n"
                    for suggestion in consensus_result.accepted_suggestions[:5]:
                        comment += f"- {suggestion}\n"

                comment += f"\n---\n*Generated by [Consensus](https://github.com/consensus) - Multi-agent AI code review*"

                console.print()
                console.print("[dim]Posting comment to PR...[/dim]")
                success, msg = post_pr_comment(pr_number, comment)
                if success:
                    console.print("[green]Comment posted successfully![/green]")
                else:
                    console.print(f"[red]Failed to post comment: {msg}[/red]")


@cli.command()
def diff():
    """Review all uncommitted changes in the current repo.

    Reviews both staged and unstaged changes. Use before committing
    to catch issues early.

    \b
    Example:
        cd my-project
        consensus diff
    """
    if not is_git_repo():
        console.print("[red]Error: Not in a git repository.[/red]")
        console.print("[dim]Run this command from within a git repository.[/dim]")
        sys.exit(1)

    repo_root = get_repo_root()
    branch = get_current_branch()

    console.print()
    console.print(Panel(
        f"[bold]Repository:[/bold] {repo_root}\n"
        f"[bold]Branch:[/bold] {branch}",
        title="[bold cyan]Reviewing Uncommitted Changes[/bold cyan]",
        border_style="cyan",
    ))

    files = get_uncommitted_changes()
    if not files:
        console.print("[green]No uncommitted changes found. Working tree is clean.[/green]")
        return

    console.print(f"[dim]Found {len(files)} file(s) with changes[/dim]")

    session_id = _review_file_changes(files, context_prefix="Uncommitted: ")

    if session_id:
        console.print()
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        console.print(f"[dim]Replay with: consensus replay {session_id}[/dim]")


@cli.command("commit")
def commit_review():
    """Review staged changes before committing.

    Reviews only the staged changes (what would be included in the
    next commit). Use as a pre-commit check.

    \b
    Example:
        git add myfile.py
        consensus commit
        git commit -m "My changes"
    """
    if not is_git_repo():
        console.print("[red]Error: Not in a git repository.[/red]")
        console.print("[dim]Run this command from within a git repository.[/dim]")
        sys.exit(1)

    repo_root = get_repo_root()
    branch = get_current_branch()

    console.print()
    console.print(Panel(
        f"[bold]Repository:[/bold] {repo_root}\n"
        f"[bold]Branch:[/bold] {branch}",
        title="[bold cyan]Reviewing Staged Changes[/bold cyan]",
        border_style="cyan",
    ))

    files = get_staged_changes()
    if not files:
        console.print("[yellow]No staged changes found.[/yellow]")
        console.print("[dim]Stage changes with: git add <file>[/dim]")
        return

    console.print(f"[dim]Found {len(files)} staged file(s)[/dim]")

    session_id = _review_file_changes(files, context_prefix="Staged: ")

    if session_id:
        console.print()
        console.print(f"[dim]Session ID: {session_id}[/dim]")
        console.print(f"[dim]Replay with: consensus replay {session_id}[/dim]")


@cli.command()
@click.argument("session_id")
@click.option("--format", "-f", "output_format", type=click.Choice(["md", "html"]), default="md",
              help="Export format: md (markdown) or html")
@click.option("--output", "-o", "output_path", type=click.Path(), default=None,
              help="Output file path (defaults to session_id.md or session_id.html)")
def export(session_id: str, output_format: str, output_path: Optional[str]):
    """Export a debate session to markdown or HTML.

    \b
    Examples:
        consensus export abc123 --format md
        consensus export abc123 --format html -o review.html
    """
    exporter = DebateExporter()

    # Handle partial session ID matching
    sessions = Storage().list_sessions(limit=100)
    matching = [s for s in sessions if s["session_id"].startswith(session_id)]

    if not matching:
        console.print(f"[red]Session not found: {session_id}[/red]")
        console.print("Run 'consensus history' to see available sessions.")
        return

    if len(matching) > 1:
        console.print(f"[yellow]Multiple sessions match '{session_id}':[/yellow]")
        for s in matching[:5]:
            console.print(f"  {s['session_id']}")
        console.print("Please provide a more specific session ID.")
        return

    full_session_id = matching[0]["session_id"]

    # Determine output path
    if output_path is None:
        ext = "md" if output_format == "md" else "html"
        output_path = f"consensus_review_{full_session_id[:12]}.{ext}"

    output_file = Path(output_path)

    console.print(f"[dim]Exporting session {full_session_id[:12]}...[/dim]")

    if output_format == "md":
        success = exporter.save_markdown(full_session_id, output_file)
    else:
        success = exporter.save_html(full_session_id, output_file)

    if success:
        console.print(f"[green]Exported to: {output_file}[/green]")
    else:
        console.print("[red]Failed to export session.[/red]")


@cli.command()
def stats():
    """Show aggregate statistics across all review sessions.

    Displays:
    - Total sessions and completion rate
    - Vote breakdown (APPROVE/REJECT/ABSTAIN)
    - Agent agreement rates
    - Most common issue types
    """
    storage = Storage()
    stats_data = storage.get_stats()

    if stats_data["total_sessions"] == 0:
        console.print("[yellow]No review sessions found.[/yellow]")
        console.print("Run 'consensus review <file>' to start reviewing code.")
        return

    console.print()
    console.print(Panel(
        "[bold cyan]Consensus Review Statistics[/bold cyan]",
        border_style="cyan",
    ))
    console.print()

    # Sessions table
    sessions_table = Table(title="Session Statistics", show_header=True, header_style="bold blue")
    sessions_table.add_column("Metric", style="dim")
    sessions_table.add_column("Value", justify="right")

    sessions_table.add_row("Total Sessions", str(stats_data["total_sessions"]))
    sessions_table.add_row("Completed Sessions", str(stats_data["completed_sessions"]))

    if stats_data["total_sessions"] > 0:
        completion_rate = stats_data["completed_sessions"] / stats_data["total_sessions"] * 100
        sessions_table.add_row("Completion Rate", f"{completion_rate:.1f}%")

    console.print(sessions_table)
    console.print()

    # Vote breakdown table
    if stats_data["vote_breakdown"]:
        vote_table = Table(title="Vote Breakdown", show_header=True, header_style="bold blue")
        vote_table.add_column("Decision", style="dim")
        vote_table.add_column("Count", justify="right")
        vote_table.add_column("Percentage", justify="right")

        total_votes = sum(stats_data["vote_breakdown"].values())
        vote_colors = {"APPROVE": "green", "REJECT": "red", "ABSTAIN": "yellow"}

        for decision, count in sorted(stats_data["vote_breakdown"].items()):
            color = vote_colors.get(decision, "white")
            pct = count / total_votes * 100 if total_votes > 0 else 0
            vote_table.add_row(
                f"[{color}]{decision}[/{color}]",
                str(count),
                f"{pct:.1f}%"
            )

        console.print(vote_table)
        console.print()

    # Agreement breakdown table
    if stats_data["agreement_breakdown"]:
        agreement_table = Table(title="Agent Agreement Rates", show_header=True, header_style="bold blue")
        agreement_table.add_column("Agreement Level", style="dim")
        agreement_table.add_column("Count", justify="right")
        agreement_table.add_column("Percentage", justify="right")

        total_responses = sum(stats_data["agreement_breakdown"].values())
        agreement_colors = {"AGREE": "green", "PARTIAL": "yellow", "DISAGREE": "red"}

        for level, count in sorted(stats_data["agreement_breakdown"].items()):
            color = agreement_colors.get(level, "white")
            pct = count / total_responses * 100 if total_responses > 0 else 0
            agreement_table.add_row(
                f"[{color}]{level}[/{color}]",
                str(count),
                f"{pct:.1f}%"
            )

        console.print(agreement_table)
        console.print()

    # Summary insights
    console.print("[dim]Run 'consensus history' to see individual sessions.[/dim]")
    console.print("[dim]Run 'consensus export <session_id> --format html' for detailed reports.[/dim]")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
