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


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
