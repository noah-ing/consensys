"""CLI interface for Consensys multi-agent code review."""
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from src import __version__
from src.orchestrator.debate import DebateOrchestrator
from src.db.storage import Storage
from src.models.review import VoteDecision, Severity
from src.git.helpers import (
    is_git_repo,
    get_repo_root,
    get_uncommitted_changes,
    get_staged_changes,
    get_pr_info,
    post_pr_comment,
    get_current_branch,
    extract_diff_context,
    DiffContext,
)
from src.export.exporter import DebateExporter
from src.personas.custom import (
    load_custom_personas,
    save_custom_persona,
    get_all_personas,
    get_persona_by_name,
    delete_custom_persona,
    list_all_persona_names,
)
from src.personas.teams import (
    TEAM_PRESETS,
    get_active_team,
    set_active_team,
    get_team_personas,
)
from src.agents.personas import Persona
from src.languages import detect_language, get_syntax_highlight_language


console = Console()


# Severity ordering for comparison (higher number = more severe)
SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def severity_meets_threshold(issue_severity: str, threshold: str) -> bool:
    """Check if an issue's severity meets or exceeds a threshold.

    Args:
        issue_severity: The severity of the issue (LOW, MEDIUM, HIGH, CRITICAL)
        threshold: The minimum severity threshold

    Returns:
        True if issue_severity >= threshold
    """
    issue_level = SEVERITY_ORDER.get(issue_severity.upper(), 0)
    threshold_level = SEVERITY_ORDER.get(threshold.upper(), 0)
    return issue_level >= threshold_level


def filter_issues_by_severity(issues: list, min_severity: str) -> list:
    """Filter a list of issues to only include those at or above min_severity.

    Args:
        issues: List of issue dicts with 'severity' key
        min_severity: Minimum severity to include

    Returns:
        Filtered list of issues
    """
    return [
        issue for issue in issues
        if severity_meets_threshold(issue.get("severity", "LOW"), min_severity)
    ]


def check_fail_threshold(reviews: list, consensus, fail_on: str) -> bool:
    """Check if any issues meet the fail-on threshold.

    Args:
        reviews: List of Review objects
        consensus: Consensus object with key_issues
        fail_on: Severity threshold that triggers failure

    Returns:
        True if any issues at or above threshold are found
    """
    # Check all issues from all reviews
    for review in reviews:
        for issue in review.issues:
            issue_sev = issue.get("severity", "LOW")
            if severity_meets_threshold(issue_sev, fail_on):
                return True

    # Check key issues from consensus
    if consensus and consensus.key_issues:
        for issue in consensus.key_issues:
            issue_sev = issue.get("severity", "LOW")
            if severity_meets_threshold(issue_sev, fail_on):
                return True

    return False


@click.group()
@click.version_option(version=__version__, prog_name="consensys")
def cli():
    """Consensys - Multi-agent AI code review with debate and voting.

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
@click.option("--fix", "-f", is_flag=True, help="Auto-fix code based on consensus feedback")
@click.option("--output", "-o", type=click.Path(), help="Write fixed code to file (with --fix)")
@click.option("--stream", "-s", is_flag=True, help="Stream agent thinking in real-time")
@click.option("--debate", "-d", is_flag=True, help="Use confrontational debate mode (agents argue more)")
@click.option("--quick", "-q", is_flag=True, help="Quick mode: Round 1 only (no debate/voting), fast for hooks")
@click.option("--no-cache", is_flag=True, help="Force fresh review, skip cache")
@click.option("--min-severity", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
              default=None, help="Only display issues at or above this severity")
@click.option("--fail-on", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
              default=None, help="Exit with code 1 if issues at or above this severity are found (for CI)")
@click.option("--diff-only", is_flag=True, help="Only review changed lines vs HEAD (requires git repo)")
def review(file: Optional[str], code: Optional[str], context: Optional[str], fix: bool, output: Optional[str], stream: bool, debate: bool, quick: bool, no_cache: bool, min_severity: Optional[str], fail_on: Optional[str], diff_only: bool):
    """Run a full debate review on code.

    Review a file:
        consensys review path/to/file.py

    Review inline code:
        consensys review --code 'def foo(): pass'

    Add context:
        consensys review file.py --context 'This is a critical auth function'

    Auto-fix code based on review:
        consensys review file.py --fix
        consensys review file.py --fix --output fixed.py

    Quick mode (for git hooks):
        consensys review file.py --quick

    Force fresh review (skip cache):
        consensys review file.py --no-cache

    Filter issues by severity:
        consensys review file.py --min-severity HIGH

    CI mode (exit 1 if issues found):
        consensys review file.py --fail-on CRITICAL
        consensys review file.py --fail-on HIGH

    Review only changed lines (smart diff mode):
        consensys review file.py --diff-only
    """
    # Get code from file or --code option
    diff_context_info: Optional[DiffContext] = None

    if file:
        file_path = Path(file)
        try:
            code_content = file_path.read_text()
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            sys.exit(1)
        context = context or f"File: {file_path.name}"

        # Handle --diff-only mode
        if diff_only:
            if not is_git_repo():
                console.print("[red]Error: --diff-only requires a git repository[/red]")
                console.print("[dim]Initialize with: git init[/dim]")
                sys.exit(1)

            # Get the diff context for this file
            repo_root = get_repo_root()
            if repo_root:
                # Convert to relative path from repo root
                try:
                    rel_path = file_path.resolve().relative_to(Path(repo_root).resolve())
                except ValueError:
                    rel_path = file_path

                diff_context_info = extract_diff_context(str(rel_path), context_lines=5, path=repo_root)

                if not diff_context_info:
                    console.print(f"[yellow]No changes detected in {file_path.name} vs HEAD[/yellow]")
                    console.print("[dim]The file has no uncommitted changes to review.[/dim]")
                    console.print("[dim]Use without --diff-only to review the entire file.[/dim]")
                    return

                # Use the focused diff content instead of full file
                code_content = diff_context_info.context_code
                context = context or f"File: {file_path.name} (diff-only mode: reviewing changed lines)"

                if diff_context_info.is_new_file:
                    context += " [NEW FILE]"
                elif diff_context_info.changed_line_ranges:
                    ranges_str = ", ".join(
                        f"L{start}-{end}" for start, end in diff_context_info.changed_line_ranges
                    )
                    context += f" [Changed: {ranges_str}]"
            else:
                console.print("[red]Error: Could not determine git repository root[/red]")
                sys.exit(1)

    elif code:
        code_content = code
        if diff_only:
            console.print("[yellow]Warning: --diff-only is ignored for inline code snippets[/yellow]")
    else:
        console.print("[red]Error: Provide either a file path or --code option[/red]")
        console.print("Run 'consensys review --help' for usage.")
        sys.exit(1)

    # Detect language from file or code content
    file_path_str = str(file_path) if file else None
    detected_language = detect_language(file_path=file_path_str, code=code_content)
    syntax_lang = get_syntax_highlight_language(language=detected_language)

    # Display what we're reviewing
    console.print()

    # Show language detection result
    if detected_language.name != "text":
        console.print(f"[dim]Detected language: {detected_language.display_name}[/dim]")
        console.print()

    # Show diff first if in diff-only mode
    if diff_context_info:
        console.print(Panel(
            Syntax(diff_context_info.diff_text, "diff", theme="monokai"),
            title="[bold magenta]Git Diff vs HEAD[/bold magenta]",
            border_style="magenta",
        ))
        console.print()
        console.print("[dim]Reviewing only the changed sections (token-efficient mode):[/dim]")
        console.print()

    console.print(Panel(
        Syntax(code_content, syntax_lang, theme="monokai", line_numbers=True),
        title=f"[bold cyan]Code Under Review[/bold cyan]" + (f" [{detected_language.display_name}]" if detected_language.name != "text" else "") + (" [diff-only]" if diff_context_info else ""),
        border_style="cyan",
    ))

    if context:
        console.print(f"[dim]Context: {context}[/dim]")

    console.print()

    # Run the full debate (use team-configured personas)
    try:
        if debate:
            # Use confrontational debate personas
            from src.agents.personas import DEBATE_PERSONAS
            team_personas = DEBATE_PERSONAS
            console.print("[bold yellow]⚔️  Debate Mode: Agents will argue more aggressively[/bold yellow]")
            console.print()
        else:
            team_personas = get_team_personas()

        # Determine cache setting
        use_cache = not no_cache

        if stream:
            # Parallel streaming mode: all 4 agents stream simultaneously in Live panels
            console.print()
            console.print("[bold cyan]━━━ Parallel Streaming Mode ━━━[/bold cyan]")
            console.print("[dim]Watch all 4 AI reviewers think simultaneously![/dim]")
            console.print()

            orchestrator = DebateOrchestrator(personas=team_personas, use_cache=use_cache, language=detected_language)
            consensus_result = orchestrator.run_streaming_review(code_content, context)

        elif quick:
            # Quick mode: Round 1 only, no debate/voting (fast for hooks)
            console.print("[bold cyan]⚡ Quick Mode: Running Round 1 only[/bold cyan]")
            console.print()
            orchestrator = DebateOrchestrator(personas=team_personas, use_cache=use_cache, language=detected_language)
            consensus_result = orchestrator.run_quick_review(code_content, context)

        else:
            # Standard parallel mode (full debate)
            orchestrator = DebateOrchestrator(personas=team_personas, use_cache=use_cache, language=detected_language)
            consensus_result = orchestrator.run_full_debate(code_content, context)

        # Print session ID for replay
        console.print()
        console.print(
            f"[dim]Session ID: {orchestrator.session_id}[/dim]"
        )
        console.print(
            f"[dim]Replay with: consensys replay {orchestrator.session_id}[/dim]"
        )

        # Auto-fix if requested
        if fix and consensus_result:
            console.print()
            console.print("[bold cyan]━━━ Auto-Fix Mode ━━━[/bold cyan]")
            console.print()

            from src.agents.agent import CodeFixer

            # Collect all issues and suggestions from reviews
            all_issues = []
            all_suggestions = set()
            for review in orchestrator.reviews:
                all_issues.extend(review.issues)
                all_suggestions.update(review.suggestions)

            # Add consensus suggestions
            all_suggestions.update(consensus_result.accepted_suggestions)

            if not all_issues and not all_suggestions:
                console.print("[green]No issues found - code looks good![/green]")
            else:
                with console.status("[bold cyan]Generating fixed code...[/bold cyan]"):
                    fixer = CodeFixer()
                    fix_result = fixer.fix_code(
                        code=code_content,
                        issues=all_issues,
                        suggestions=list(all_suggestions),
                        context=context
                    )

                # Display the fixed code
                console.print(Panel(
                    Syntax(fix_result.fixed_code, syntax_lang, theme="monokai", line_numbers=True),
                    title="[bold green]Fixed Code[/bold green]",
                    border_style="green",
                ))

                # Display changes made
                if fix_result.changes_made:
                    console.print()
                    console.print("[bold]Changes Made:[/bold]")
                    for change in fix_result.changes_made:
                        console.print(f"  [green]✓[/green] {change}")

                # Display explanation
                if fix_result.explanation:
                    console.print()
                    console.print(f"[dim]{fix_result.explanation}[/dim]")

                # Write to file if output specified
                if output:
                    output_path = Path(output)
                    output_path.write_text(fix_result.fixed_code)
                    console.print()
                    console.print(f"[green]Fixed code written to: {output_path}[/green]")
                elif file:
                    console.print()
                    console.print(f"[dim]To overwrite original: consensys review {file} --fix --output {file}[/dim]")

        # Display severity filtering summary if enabled
        if min_severity:
            console.print()
            console.print(f"[dim]Severity filter: showing only {min_severity}+ issues[/dim]")

            # Count filtered issues
            total_issues = sum(len(r.issues) for r in orchestrator.reviews)
            filtered_issues = sum(
                len(filter_issues_by_severity(r.issues, min_severity))
                for r in orchestrator.reviews
            )
            if total_issues > filtered_issues:
                console.print(f"[dim]({filtered_issues}/{total_issues} issues shown at {min_severity}+ level)[/dim]")

        # Check fail-on threshold for CI integration
        if fail_on:
            should_fail = check_fail_threshold(
                orchestrator.reviews,
                consensus_result,
                fail_on
            )
            if should_fail:
                console.print()
                console.print(f"[bold red]CI Check Failed: Issues at {fail_on} severity or above found[/bold red]")
                sys.exit(1)
            else:
                console.print()
                console.print(f"[bold green]CI Check Passed: No issues at {fail_on} severity or above[/bold green]")

    except Exception as e:
        console.print(f"[red]Error during review: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-n", default=20, help="Number of sessions to show")
def history(limit: int):
    """Show past review sessions.

    Lists recent review sessions with their IDs, dates, and final decisions.
    Use 'consensys replay <session_id>' to view a past debate.
    """
    storage = Storage()
    sessions = storage.list_sessions(limit=limit)

    if not sessions:
        console.print("[yellow]No review sessions found.[/yellow]")
        console.print("Run 'consensys review <file>' to start a review.")
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
    console.print("[dim]Use 'consensys replay <session_id>' to view a session[/dim]")


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
        console.print("Run 'consensys history' to see available sessions.")
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


def _detect_language_for_highlight(filepath: str) -> str:
    """Detect programming language from file extension for syntax highlighting.

    Uses the languages module but returns just the highlight string for simpler cases.
    """
    detected = detect_language(file_path=filepath)
    return detected.syntax_highlight


def _review_file_changes(files, context_prefix: str = "") -> Optional[str]:
    """Review a list of changed files and return the session ID."""
    if not files:
        console.print("[yellow]No changes found to review.[/yellow]")
        return None

    team_personas = get_team_personas()
    orchestrator = DebateOrchestrator(personas=team_personas)
    session_id = None

    for i, file in enumerate(files, 1):
        console.print()
        console.print(f"[bold cyan]Reviewing file {i}/{len(files)}: {file.path}[/bold cyan]")

        # Display the diff
        lang = _detect_language_for_highlight(file.path)
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
        consensys pr 123
        consensys pr 123 --post  # Post summary to PR

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
        console.print(f"[dim]Replay with: consensys replay {session_id}[/dim]")

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

                comment += f"\n---\n*Generated by [Consensys](https://github.com/noah-ing/consensys) - Multi-agent AI code review*"

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
        consensys diff
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
        console.print(f"[dim]Replay with: consensys replay {session_id}[/dim]")


@cli.command("commit")
def commit_review():
    """Review staged changes before committing.

    Reviews only the staged changes (what would be included in the
    next commit). Use as a pre-commit check.

    \b
    Example:
        git add myfile.py
        consensys commit
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
        console.print(f"[dim]Replay with: consensys replay {session_id}[/dim]")


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
        consensys export abc123 --format md
        consensys export abc123 --format html -o review.html
    """
    exporter = DebateExporter()

    # Handle partial session ID matching
    sessions = Storage().list_sessions(limit=100)
    matching = [s for s in sessions if s["session_id"].startswith(session_id)]

    if not matching:
        console.print(f"[red]Session not found: {session_id}[/red]")
        console.print("Run 'consensys history' to see available sessions.")
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
        console.print("Run 'consensys review <file>' to start reviewing code.")
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
    console.print("[dim]Run 'consensys history' to see individual sessions.[/dim]")
    console.print("[dim]Run 'consensys export <session_id> --format html' for detailed reports.[/dim]")


@cli.command()
@click.option("--period", "-p", type=click.Choice(["daily", "weekly", "monthly"]),
              default="daily", help="Time period for cost breakdown")
@click.option("--days", "-d", default=30, type=int,
              help="Number of days to look back (default: 30)")
@click.option("--budget", "-b", type=float, default=None,
              help="Monthly budget in USD for threshold alerts")
def metrics(period: str, days: int, budget: Optional[float]):
    """Show API usage metrics and cost tracking.

    Displays token usage, API call costs, and performance metrics.
    Useful for monitoring spending and identifying optimization opportunities.

    \b
    Examples:
        consensys metrics                      # Show summary
        consensys metrics --period weekly      # Weekly breakdown
        consensys metrics --days 7             # Last 7 days only
        consensys metrics --budget 10.00       # Set $10 budget alert
    """
    from src.metrics import get_metrics_tracker, PRICING

    tracker = get_metrics_tracker()
    summary = tracker.get_summary()

    if summary.total_calls == 0:
        console.print("[yellow]No API metrics recorded yet.[/yellow]")
        console.print("Run 'consensys review <file>' to start generating metrics.")
        return

    console.print()
    console.print(Panel(
        "[bold cyan]API Usage Metrics & Cost Tracking[/bold cyan]",
        border_style="cyan",
    ))
    console.print()

    # Overall summary table
    summary_table = Table(title="Overall Summary", show_header=True, header_style="bold blue")
    summary_table.add_column("Metric", style="dim")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total API Calls", f"{summary.total_calls:,}")
    summary_table.add_row("Input Tokens", f"{summary.total_tokens_in:,}")
    summary_table.add_row("Output Tokens", f"{summary.total_tokens_out:,}")
    summary_table.add_row("Total Tokens", f"{summary.total_tokens:,}")
    summary_table.add_row("Total Cost", f"${summary.total_cost_usd:.4f}")
    summary_table.add_row("Avg Cost/Call", f"${summary.avg_cost_per_call:.6f}")
    summary_table.add_row("Avg Duration", f"{summary.avg_duration_ms:.0f}ms")

    console.print(summary_table)
    console.print()

    # Cost by agent
    if summary.by_agent:
        agent_table = Table(title="Cost by Agent", show_header=True, header_style="bold blue")
        agent_table.add_column("Agent", style="cyan")
        agent_table.add_column("Calls", justify="right")
        agent_table.add_column("Tokens", justify="right")
        agent_table.add_column("Cost", justify="right")
        agent_table.add_column("Avg Duration", justify="right")

        for agent_name, data in sorted(summary.by_agent.items()):
            total_tokens = data["tokens_in"] + data["tokens_out"]
            agent_table.add_row(
                agent_name,
                str(data["calls"]),
                f"{total_tokens:,}",
                f"${data['cost_usd']:.4f}",
                f"{data['avg_duration_ms']:.0f}ms",
            )

        console.print(agent_table)
        console.print()

    # Cost by operation
    if summary.by_operation:
        op_table = Table(title="Cost by Operation", show_header=True, header_style="bold blue")
        op_table.add_column("Operation", style="cyan")
        op_table.add_column("Calls", justify="right")
        op_table.add_column("Tokens", justify="right")
        op_table.add_column("Cost", justify="right")

        op_colors = {"review": "green", "respond": "yellow", "vote": "blue", "fix": "magenta"}
        for op_name, data in sorted(summary.by_operation.items()):
            total_tokens = data["tokens_in"] + data["tokens_out"]
            color = op_colors.get(op_name, "white")
            op_table.add_row(
                f"[{color}]{op_name}[/{color}]",
                str(data["calls"]),
                f"{total_tokens:,}",
                f"${data['cost_usd']:.4f}",
            )

        console.print(op_table)
        console.print()

    # Time-based cost breakdown
    breakdown = tracker.get_cost_breakdown(period=period, days=days)

    if breakdown.daily_breakdown:
        period_title = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[period]
        time_table = Table(
            title=f"{period_title} Cost Breakdown ({breakdown.start_date} to {breakdown.end_date})",
            show_header=True,
            header_style="bold blue"
        )
        time_table.add_column("Period", style="dim")
        time_table.add_column("Calls", justify="right")
        time_table.add_column("Tokens", justify="right")
        time_table.add_column("Cost", justify="right")

        for entry in breakdown.daily_breakdown[:14]:  # Show last 14 entries max
            time_table.add_row(
                entry["period"],
                str(entry["calls"]),
                f"{entry['tokens']:,}",
                f"${entry['cost_usd']:.4f}",
            )

        console.print(time_table)
        console.print()

    # Budget alert
    if budget:
        is_over, current_spend, percentage = tracker.check_budget(budget, period_days=30)

        if is_over:
            console.print(Panel(
                f"[bold red]Budget Alert![/bold red]\n\n"
                f"Current 30-day spending: [red]${current_spend:.4f}[/red]\n"
                f"Budget: ${budget:.2f}\n"
                f"Usage: [red]{percentage:.1f}%[/red] of budget",
                title="[bold red]Over Budget Threshold (80%)[/bold red]",
                border_style="red",
            ))
        else:
            console.print(Panel(
                f"[bold green]Budget Status: OK[/bold green]\n\n"
                f"Current 30-day spending: ${current_spend:.4f}\n"
                f"Budget: ${budget:.2f}\n"
                f"Usage: [green]{percentage:.1f}%[/green] of budget",
                title="[bold green]Within Budget[/bold green]",
                border_style="green",
            ))
        console.print()

    # Model pricing reference
    console.print("[dim]Pricing Reference (Claude 3.5 Haiku):[/dim]")
    console.print(f"[dim]  Input: ${PRICING['claude-3-5-haiku-20241022']['input_per_million']:.2f}/M tokens[/dim]")
    console.print(f"[dim]  Output: ${PRICING['claude-3-5-haiku-20241022']['output_per_million']:.2f}/M tokens[/dim]")
    console.print()
    console.print("[dim]Run 'consensys metrics --budget 10.00' to set budget alerts.[/dim]")


def load_consensusignore(directory: Path) -> list:
    """Load ignore patterns from .consensusignore file.

    Args:
        directory: The directory to search for .consensusignore

    Returns:
        List of ignore patterns (glob patterns)
    """
    ignore_patterns = []
    ignore_file = directory / ".consensusignore"

    if ignore_file.exists():
        try:
            content = ignore_file.read_text()
            for line in content.splitlines():
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    ignore_patterns.append(line)
        except Exception:
            pass

    return ignore_patterns


def should_ignore(file_path: Path, ignore_patterns: list, base_dir: Path) -> bool:
    """Check if a file should be ignored based on patterns.

    Args:
        file_path: The file path to check
        ignore_patterns: List of glob patterns to match against
        base_dir: Base directory for relative path comparison

    Returns:
        True if the file should be ignored
    """
    import fnmatch

    # Get relative path from base directory
    try:
        rel_path = file_path.relative_to(base_dir)
    except ValueError:
        rel_path = file_path

    rel_str = str(rel_path)
    name = file_path.name

    for pattern in ignore_patterns:
        # Match against filename
        if fnmatch.fnmatch(name, pattern):
            return True
        # Match against relative path
        if fnmatch.fnmatch(rel_str, pattern):
            return True
        # Match against path with ** prefix for nested patterns
        if fnmatch.fnmatch(rel_str, f"**/{pattern}"):
            return True

    return False


def collect_python_files(directory: Path, ignore_patterns: list) -> list:
    """Collect all Python files in a directory, respecting ignore patterns.

    Args:
        directory: The directory to search
        ignore_patterns: Patterns from .consensusignore

    Returns:
        List of Path objects for Python files
    """
    files = []

    # Add default ignore patterns
    default_ignores = [
        "__pycache__",
        "*.pyc",
        ".git",
        ".venv",
        "venv",
        "env",
        ".env",
        "node_modules",
        "*.egg-info",
        "dist",
        "build",
    ]
    all_patterns = default_ignores + ignore_patterns

    for file_path in directory.rglob("*.py"):
        if not should_ignore(file_path, all_patterns, directory):
            files.append(file_path)

    # Sort for consistent ordering
    files.sort()
    return files


@cli.command("review-batch")
@click.argument("path", type=click.Path(exists=True))
@click.option("--parallel", "-p", default=4, help="Number of parallel workers (default: 4)")
@click.option("--quick", "-q", is_flag=True, help="Use quick mode (Round 1 only) for each file")
@click.option("--no-cache", is_flag=True, help="Force fresh reviews, skip cache")
@click.option("--min-severity", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
              default=None, help="Only display issues at or above this severity")
@click.option("--fail-on", type=click.Choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
              default=None, help="Exit with code 1 if issues at or above this severity are found")
@click.option("--report", "-r", type=click.Path(), default=None,
              help="Generate combined markdown report at this path")
def review_batch(path: str, parallel: int, quick: bool, no_cache: bool,
                 min_severity: Optional[str], fail_on: Optional[str], report: Optional[str]):
    """Review all Python files in a directory.

    Runs code reviews on all Python files in the specified directory,
    processing multiple files in parallel for efficiency.

    \b
    Examples:
        consensys review-batch src/
        consensys review-batch . --parallel 8
        consensys review-batch src/ --quick --no-cache
        consensys review-batch src/ --fail-on HIGH
        consensys review-batch src/ --report batch_report.md

    Respects .consensusignore file for exclusions. Create a .consensusignore
    file in your project root with glob patterns to exclude:

    \b
        # .consensusignore example
        tests/
        *_test.py
        conftest.py
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from dataclasses import dataclass
    from typing import Tuple
    import time

    @dataclass
    class BatchResult:
        """Result of reviewing a single file."""
        file_path: Path
        session_id: Optional[str]
        decision: Optional[str]
        issues_count: int
        suggestions_count: int
        severity: str
        duration_seconds: float
        error: Optional[str] = None

    dir_path = Path(path)

    # Handle file vs directory
    if dir_path.is_file():
        if not dir_path.suffix == ".py":
            console.print("[red]Error: Single file must be a Python file (.py)[/red]")
            console.print("[dim]Use 'consensys review <file>' for single file review.[/dim]")
            sys.exit(1)
        files = [dir_path]
        ignore_patterns = []
    else:
        # Load ignore patterns
        ignore_patterns = load_consensusignore(dir_path)

        # Collect Python files
        files = collect_python_files(dir_path, ignore_patterns)

    if not files:
        console.print("[yellow]No Python files found to review.[/yellow]")
        if ignore_patterns:
            console.print(f"[dim]Note: {len(ignore_patterns)} ignore patterns loaded from .consensusignore[/dim]")
        return

    console.print()
    console.print(Panel(
        f"[bold]Directory:[/bold] {dir_path.absolute()}\n"
        f"[bold]Files:[/bold] {len(files)} Python files\n"
        f"[bold]Workers:[/bold] {parallel} parallel\n"
        f"[bold]Mode:[/bold] {'Quick (Round 1)' if quick else 'Full Debate'}",
        title="[bold cyan]Batch Review[/bold cyan]",
        border_style="cyan",
    ))

    if ignore_patterns:
        console.print(f"[dim]Ignore patterns: {len(ignore_patterns)} loaded from .consensusignore[/dim]")

    console.print()

    # Function to review a single file
    def review_single_file(file_path: Path) -> BatchResult:
        """Review a single file and return the result."""
        start_time = time.time()

        try:
            code_content = file_path.read_text()
        except Exception as e:
            return BatchResult(
                file_path=file_path,
                session_id=None,
                decision=None,
                issues_count=0,
                suggestions_count=0,
                severity="ERROR",
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

        try:
            # Create orchestrator with a fresh console (suppress output for batch)
            team_personas = get_team_personas()
            # Use a dummy console to suppress individual review output
            from io import StringIO
            quiet_console = Console(file=StringIO(), quiet=True)
            orchestrator = DebateOrchestrator(
                personas=team_personas,
                console=quiet_console,
                use_cache=not no_cache,
            )

            context = f"File: {file_path.name}"

            if quick:
                consensus_result = orchestrator.run_quick_review(code_content, context)
            else:
                consensus_result = orchestrator.run_full_debate(code_content, context)

            # Aggregate issues and suggestions
            total_issues = sum(len(r.issues) for r in orchestrator.reviews)
            total_suggestions = sum(len(r.suggestions) for r in orchestrator.reviews)

            # Get max severity across all reviews
            severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            max_severity = "LOW"
            for review in orchestrator.reviews:
                if severity_order.index(review.severity) > severity_order.index(max_severity):
                    max_severity = review.severity

            decision = consensus_result.final_decision.value if consensus_result else None

            return BatchResult(
                file_path=file_path,
                session_id=orchestrator.session_id,
                decision=decision,
                issues_count=total_issues,
                suggestions_count=total_suggestions,
                severity=max_severity,
                duration_seconds=time.time() - start_time,
            )

        except Exception as e:
            return BatchResult(
                file_path=file_path,
                session_id=None,
                decision=None,
                issues_count=0,
                suggestions_count=0,
                severity="ERROR",
                duration_seconds=time.time() - start_time,
                error=str(e),
            )

    # Run reviews in parallel with progress
    results: list = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        overall_task = progress.add_task(
            f"[cyan]Reviewing {len(files)} files...[/cyan]",
            total=len(files)
        )

        with ThreadPoolExecutor(max_workers=parallel) as executor:
            future_to_file = {
                executor.submit(review_single_file, f): f
                for f in files
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Update progress
                    if result.error:
                        status = f"[red]✗ {file_path.name}[/red]"
                    elif result.decision == "APPROVE":
                        status = f"[green]✓ {file_path.name}[/green]"
                    elif result.decision == "REJECT":
                        status = f"[red]✗ {file_path.name}[/red]"
                    else:
                        status = f"[yellow]~ {file_path.name}[/yellow]"

                    progress.console.print(f"  {status}")
                    progress.advance(overall_task)

                except Exception as e:
                    console.print(f"[red]Error processing {file_path}: {e}[/red]")
                    progress.advance(overall_task)

    # Sort results by file path for consistent display
    results.sort(key=lambda r: str(r.file_path))

    # Display summary table
    console.print()
    console.print()

    table = Table(title="Batch Review Results", show_header=True, header_style="bold cyan")
    table.add_column("File", style="dim", max_width=40)
    table.add_column("Decision", justify="center")
    table.add_column("Severity", justify="center")
    table.add_column("Issues", justify="center")
    table.add_column("Time", justify="right")

    decision_colors = {"APPROVE": "green", "REJECT": "red", "ABSTAIN": "yellow"}
    severity_colors = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "green", "ERROR": "red"}

    total_issues = 0
    total_approve = 0
    total_reject = 0
    total_abstain = 0
    total_errors = 0
    has_fail_threshold_issue = False

    for result in results:
        # Get relative path for display
        try:
            rel_path = result.file_path.relative_to(dir_path)
        except ValueError:
            rel_path = result.file_path

        if result.error:
            table.add_row(
                str(rel_path),
                "[red]ERROR[/red]",
                "-",
                "-",
                f"{result.duration_seconds:.1f}s",
            )
            total_errors += 1
        else:
            dec_color = decision_colors.get(result.decision, "dim")
            sev_color = severity_colors.get(result.severity, "blue")

            # Apply min-severity filter to issue count display
            displayed_issues = result.issues_count
            if min_severity:
                # We show all issues but note that filtering is available in individual reviews
                pass

            table.add_row(
                str(rel_path),
                f"[{dec_color}]{result.decision}[/{dec_color}]",
                f"[{sev_color}]{result.severity}[/{sev_color}]",
                str(displayed_issues),
                f"{result.duration_seconds:.1f}s",
            )

            total_issues += result.issues_count

            if result.decision == "APPROVE":
                total_approve += 1
            elif result.decision == "REJECT":
                total_reject += 1
            else:
                total_abstain += 1

            # Check fail-on threshold
            if fail_on and result.severity:
                if severity_meets_threshold(result.severity, fail_on):
                    has_fail_threshold_issue = True

    console.print(table)
    console.print()

    # Summary stats
    total_files = len(results)
    total_duration = sum(r.duration_seconds for r in results)

    summary_table = Table(title="Summary", show_header=True, header_style="bold blue")
    summary_table.add_column("Metric", style="dim")
    summary_table.add_column("Value", justify="right")

    summary_table.add_row("Total Files", str(total_files))
    summary_table.add_row("[green]Approved[/green]", str(total_approve))
    summary_table.add_row("[red]Rejected[/red]", str(total_reject))
    summary_table.add_row("[yellow]Abstained[/yellow]", str(total_abstain))
    if total_errors > 0:
        summary_table.add_row("[red]Errors[/red]", str(total_errors))
    summary_table.add_row("Total Issues", str(total_issues))
    summary_table.add_row("Total Duration", f"{total_duration:.1f}s")

    console.print(summary_table)
    console.print()

    # Generate combined report if requested
    if report:
        report_path = Path(report)
        report_lines = [
            "# Consensus Batch Review Report",
            "",
            f"**Directory:** `{dir_path.absolute()}`",
            f"**Files Reviewed:** {total_files}",
            f"**Total Duration:** {total_duration:.1f}s",
            "",
            "## Summary",
            "",
            f"- **Approved:** {total_approve}",
            f"- **Rejected:** {total_reject}",
            f"- **Abstained:** {total_abstain}",
            f"- **Errors:** {total_errors}",
            f"- **Total Issues:** {total_issues}",
            "",
            "## Results by File",
            "",
            "| File | Decision | Severity | Issues | Session |",
            "|------|----------|----------|--------|---------|",
        ]

        for result in results:
            try:
                rel_path = result.file_path.relative_to(dir_path)
            except ValueError:
                rel_path = result.file_path

            if result.error:
                report_lines.append(f"| `{rel_path}` | ERROR | - | - | - |")
            else:
                session_link = result.session_id[:12] if result.session_id else "-"
                report_lines.append(
                    f"| `{rel_path}` | {result.decision} | {result.severity} | "
                    f"{result.issues_count} | {session_link} |"
                )

        report_lines.extend([
            "",
            "---",
            "*Generated by [Consensys](https://github.com/noah-ing/consensys) - Multi-agent AI code review*",
        ])

        report_path.write_text("\n".join(report_lines))
        console.print(f"[green]Report saved to: {report_path}[/green]")
        console.print()

    # Print replay hint
    session_ids = [r.session_id for r in results if r.session_id]
    if session_ids:
        console.print("[dim]Replay individual reviews with:[/dim]")
        console.print(f"[dim]  consensys replay <session_id>[/dim]")
        console.print()

    # Check fail-on threshold
    if fail_on and has_fail_threshold_issue:
        console.print(f"[bold red]CI Check Failed: Files with {fail_on}+ severity found[/bold red]")
        sys.exit(1)
    elif fail_on:
        console.print(f"[bold green]CI Check Passed: No files with {fail_on}+ severity[/bold green]")


@cli.command("add-persona")
@click.option("--name", "-n", prompt="Persona name", help="Unique name for the persona (e.g., DatabaseExpert)")
@click.option("--role", "-r", prompt="Role", help="Role title (e.g., Database Administrator)")
@click.option("--style", "-s", prompt="Review style", help="How this persona communicates (e.g., 'methodical and data-driven')")
def add_persona(name: str, role: str, style: str):
    """Create a new custom reviewer persona interactively.

    Custom personas are stored in ~/.consensus/personas.json and can
    participate in code reviews alongside built-in experts.

    \b
    Example:
        consensys add-persona
        # Follow the interactive prompts

        consensys add-persona --name DatabaseExpert --role "DBA" --style "data-driven"
        # Still prompts for system_prompt and priorities
    """
    # Check if name already exists
    existing = get_persona_by_name(name)
    if existing:
        console.print(f"[yellow]Warning: A persona named '{name}' already exists.[/yellow]")
        if not click.confirm("Do you want to overwrite it?"):
            console.print("[dim]Cancelled.[/dim]")
            return

    console.print()
    console.print(Panel(
        f"[bold]Creating new persona: {name}[/bold]\n\n"
        f"[dim]Fill in the following details to create your custom reviewer.[/dim]",
        title="[bold cyan]New Persona[/bold cyan]",
        border_style="cyan",
    ))
    console.print()

    # Get system prompt (multi-line)
    console.print("[bold]System Prompt[/bold]")
    console.print("[dim]Describe this persona's expertise, focus areas, and review approach.")
    console.print("This will be used as the AI's system prompt. Enter a blank line to finish.[/dim]")
    console.print()

    system_lines = []
    while True:
        line = click.prompt("", default="", show_default=False)
        if line == "":
            if system_lines:
                break
            console.print("[yellow]Please enter at least one line.[/yellow]")
            continue
        system_lines.append(line)

    system_prompt = "\n".join(system_lines)

    # Get priorities
    console.print()
    console.print("[bold]Priorities[/bold]")
    console.print("[dim]Enter 3-5 focus areas, one per line. Enter a blank line to finish.[/dim]")
    console.print()

    priorities = []
    while True:
        priority = click.prompt(f"Priority {len(priorities) + 1}", default="", show_default=False)
        if priority == "":
            if len(priorities) >= 1:
                break
            console.print("[yellow]Please enter at least one priority.[/yellow]")
            continue
        priorities.append(priority)
        if len(priorities) >= 5:
            console.print("[dim]Maximum 5 priorities reached.[/dim]")
            break

    # Create and save the persona
    persona = Persona(
        name=name,
        role=role,
        system_prompt=system_prompt,
        priorities=priorities,
        review_style=style,
    )

    save_custom_persona(persona)

    console.print()
    console.print(Panel(
        f"[bold]Name:[/bold] {persona.name}\n"
        f"[bold]Role:[/bold] {persona.role}\n"
        f"[bold]Style:[/bold] {persona.review_style}\n"
        f"[bold]Priorities:[/bold] {', '.join(persona.priorities)}",
        title=f"[bold green]Persona Created: {name}[/bold green]",
        border_style="green",
    ))
    console.print()
    console.print("[dim]Use 'consensys set-team' to add this persona to your review team.[/dim]")


@cli.command("set-team")
@click.argument("personas", nargs=-1)
@click.option("--preset", "-p", type=click.Choice(list(TEAM_PRESETS.keys())), help="Use a preset team")
def set_team(personas: tuple, preset: Optional[str]):
    """Set the active review team.

    Select which personas participate in code reviews. You can use
    a preset team or specify individual personas.

    \b
    Examples:
        consensys set-team --preset security-focused
        consensys set-team SecurityExpert PragmaticDev
        consensys set-team Security Performance  # Partial name matching
    """
    if preset:
        # Use preset team
        set_active_team(team_name=preset)
        preset_info = TEAM_PRESETS[preset]

        console.print()
        console.print(Panel(
            f"[bold]Preset:[/bold] {preset}\n"
            f"[bold]Description:[/bold] {preset_info['description']}\n"
            f"[bold]Personas:[/bold] {', '.join(preset_info['personas'])}",
            title="[bold green]Team Set[/bold green]",
            border_style="green",
        ))
        return

    if not personas:
        console.print("[yellow]Specify personas or use --preset.[/yellow]")
        console.print()
        console.print("Available personas:")
        for name in list_all_persona_names():
            console.print(f"  - {name}")
        console.print()
        console.print("Presets:")
        for name, info in TEAM_PRESETS.items():
            console.print(f"  - {name}: {info['description']}")
        return

    # Match persona names (partial matching)
    all_names = list_all_persona_names()
    matched_personas = []
    not_found = []

    for search in personas:
        search_lower = search.lower()
        # Try exact match first
        found = None
        for name in all_names:
            if name.lower() == search_lower:
                found = name
                break
        # Try partial match
        if not found:
            for name in all_names:
                if search_lower in name.lower():
                    found = name
                    break
        if found:
            if found not in matched_personas:
                matched_personas.append(found)
        else:
            not_found.append(search)

    if not_found:
        console.print(f"[yellow]Personas not found: {', '.join(not_found)}[/yellow]")
        console.print("[dim]Available: " + ", ".join(all_names) + "[/dim]")
        if not matched_personas:
            return

    if matched_personas:
        set_active_team(custom_personas=matched_personas)

        console.print()
        console.print(Panel(
            f"[bold]Active Team:[/bold] {', '.join(matched_personas)}",
            title="[bold green]Team Set[/bold green]",
            border_style="green",
        ))


@cli.command("teams")
def teams():
    """List available team presets and current team.

    Shows all preset teams and custom personas available for
    code reviews.
    """
    console.print()
    console.print(Panel(
        "[bold cyan]Team Configuration[/bold cyan]",
        border_style="cyan",
    ))
    console.print()

    # Current team
    current_team = get_active_team()
    current_personas = get_team_personas()
    current_names = [p.name for p in current_personas]

    console.print("[bold]Current Team:[/bold]")
    if current_team:
        console.print(f"  Preset: [green]{current_team}[/green]")
    console.print(f"  Personas: [cyan]{', '.join(current_names)}[/cyan]")
    console.print()

    # Preset teams
    preset_table = Table(title="Team Presets", show_header=True, header_style="bold blue")
    preset_table.add_column("Name", style="cyan")
    preset_table.add_column("Description")
    preset_table.add_column("Personas", max_width=40)

    for name, info in TEAM_PRESETS.items():
        marker = " [green](active)[/green]" if name == current_team else ""
        preset_table.add_row(
            name + marker,
            info["description"],
            ", ".join(info["personas"]),
        )

    console.print(preset_table)
    console.print()

    # Built-in personas
    from src.agents.personas import PERSONAS
    builtin_table = Table(title="Built-in Personas", show_header=True, header_style="bold blue")
    builtin_table.add_column("Name", style="cyan")
    builtin_table.add_column("Role")
    builtin_table.add_column("Style", max_width=40)

    for persona in PERSONAS:
        builtin_table.add_row(
            persona.name,
            persona.role,
            persona.review_style,
        )

    console.print(builtin_table)
    console.print()

    # Custom personas
    custom_personas = load_custom_personas()
    if custom_personas:
        custom_table = Table(title="Custom Personas", show_header=True, header_style="bold blue")
        custom_table.add_column("Name", style="green")
        custom_table.add_column("Role")
        custom_table.add_column("Style", max_width=40)

        for persona in custom_personas:
            custom_table.add_row(
                persona.name,
                persona.role,
                persona.review_style,
            )

        console.print(custom_table)
        console.print()

    console.print("[dim]Use 'consensys set-team --preset <name>' to select a preset.[/dim]")
    console.print("[dim]Use 'consensys set-team <persona1> <persona2>' for custom selection.[/dim]")
    console.print("[dim]Use 'consensys add-persona' to create a new persona.[/dim]")


@cli.command("install-hooks")
@click.option("--git/--no-git", default=True, help="Install git pre-commit hook")
@click.option("--claude/--no-claude", default=True, help="Install Claude Code hooks")
def install_hooks(git: bool, claude: bool):
    """Install consensus hooks for automatic code review.

    Installs hooks that automatically run consensys review:

    \b
    Git pre-commit: Reviews staged Python files before commit
    Claude Code: Reviews files after Write/Edit tool calls
    """
    from src.hooks.installer import install_hooks as do_install, get_hook_status

    console.print("[bold cyan]Installing Consensus Hooks[/bold cyan]")
    console.print()

    results = do_install(git_hooks=git, claude_code_hooks=claude)

    for hook_name, success in results.items():
        if success:
            console.print(f"  [green]✓[/green] {hook_name} installed")
        else:
            console.print(f"  [red]✗[/red] {hook_name} failed")

    console.print()

    # Show status
    status = get_hook_status()
    for hook_name, info in status.items():
        if info["installed"]:
            console.print(f"[dim]{hook_name}: {info['path']}[/dim]")


@cli.command("uninstall-hooks")
@click.option("--git/--no-git", default=True, help="Uninstall git pre-commit hook")
@click.option("--claude/--no-claude", default=True, help="Uninstall Claude Code hooks")
def uninstall_hooks(git: bool, claude: bool):
    """Uninstall consensus hooks."""
    from src.hooks.installer import uninstall_hooks as do_uninstall

    console.print("[bold cyan]Uninstalling Consensus Hooks[/bold cyan]")
    console.print()

    results = do_uninstall(git_hooks=git, claude_code_hooks=claude)

    for hook_name, success in results.items():
        if success:
            console.print(f"  [green]✓[/green] {hook_name} uninstalled")
        else:
            console.print(f"  [yellow]![/yellow] {hook_name} not found or failed")


@cli.command("hook-status")
def hook_status():
    """Show status of installed hooks."""
    from src.hooks.installer import get_hook_status

    status = get_hook_status()

    table = Table(title="Hook Status", show_header=True, header_style="bold cyan")
    table.add_column("Hook", style="cyan")
    table.add_column("Status")
    table.add_column("Path", style="dim")

    for hook_name, info in status.items():
        status_str = "[green]Installed[/green]" if info["installed"] else "[dim]Not installed[/dim]"
        table.add_row(
            hook_name,
            status_str,
            info["path"] or "-"
        )

    console.print(table)


@cli.group()
def config():
    """Manage Consensus configuration.

    View and manage configuration settings from:
    - Project-level: .consensus.yaml or .consensus.json in repo root
    - User-level: ~/.consensus/config.yaml

    CLI flags always override config file settings.
    """
    pass


@config.command("show")
def config_show():
    """Display current configuration.

    Shows the effective configuration with source files
    and which values come from which config file.

    \b
    Examples:
        consensys config show
    """
    from src.settings import (
        load_config,
        get_user_config_file,
        find_project_config,
        YAML_AVAILABLE,
        DEFAULT_MODEL,
        DEFAULT_CACHE_TTL,
        DEFAULT_TEAM,
    )

    config = load_config()

    console.print()
    console.print(Panel(
        "[bold cyan]Consensus Configuration[/bold cyan]",
        border_style="cyan",
    ))
    console.print()

    # Configuration sources
    console.print("[bold]Configuration Sources:[/bold]")
    if config.source_files:
        for source in config.source_files:
            console.print(f"  [green]✓[/green] {source}")
    else:
        console.print("  [dim]No config files found (using defaults)[/dim]")

    # Check for potential config locations
    user_config = get_user_config_file()
    project_config = find_project_config()

    if not user_config.exists():
        console.print(f"  [dim]User config: {user_config} (not found)[/dim]")
    if not project_config:
        console.print("  [dim]Project config: .consensus.yaml (not found)[/dim]")

    console.print()

    # Current settings table
    table = Table(title="Current Settings", show_header=True, header_style="bold blue")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    def get_source(value, default):
        """Determine if value is from config or default."""
        if value is None or value == default:
            return "default"
        if config.source_files:
            return "config file"
        return "default"

    # default_team
    team_value = config.default_team if config.default_team else DEFAULT_TEAM
    if isinstance(team_value, list):
        team_display = ", ".join(team_value)
    else:
        team_display = str(team_value)
    table.add_row(
        "default_team",
        team_display,
        get_source(config.default_team, None),
    )

    # min_severity
    table.add_row(
        "min_severity",
        config.min_severity or "[dim]not set[/dim]",
        get_source(config.min_severity, None),
    )

    # cache_ttl
    cache_display = f"{config.cache_ttl}s ({config.cache_ttl // 60}m)"
    table.add_row(
        "cache_ttl",
        cache_display,
        get_source(config.cache_ttl, DEFAULT_CACHE_TTL),
    )

    # model
    table.add_row(
        "model",
        config.model,
        get_source(config.model, DEFAULT_MODEL),
    )

    # fail_on
    table.add_row(
        "fail_on",
        config.fail_on or "[dim]not set[/dim]",
        get_source(config.fail_on, None),
    )

    # quick_mode
    quick_display = "[green]enabled[/green]" if config.quick_mode else "[dim]disabled[/dim]"
    table.add_row(
        "quick_mode",
        quick_display,
        get_source(config.quick_mode, False),
    )

    console.print(table)
    console.print()

    # YAML availability
    if YAML_AVAILABLE:
        console.print("[dim]YAML support: [green]available[/green][/dim]")
    else:
        console.print("[dim]YAML support: [yellow]not available[/yellow] (install pyyaml)[/dim]")

    console.print()
    console.print("[dim]Create a config file with: consensys config init[/dim]")
    console.print("[dim]Config files are YAML or JSON format.[/dim]")


@config.command("init")
@click.option("--project", "-p", is_flag=True, help="Create project-level config (.consensus.yaml)")
@click.option("--user", "-u", is_flag=True, help="Create user-level config (~/.consensus/config.yaml)")
def config_init(project: bool, user: bool):
    """Initialize a configuration file with example values.

    Creates an example configuration file that you can customize.

    \b
    Examples:
        consensys config init --project   # Create .consensus.yaml
        consensys config init --user      # Create ~/.consensus/config.yaml
        consensys config init             # Interactive selection
    """
    from src.settings import create_example_config, get_user_config_file

    if not project and not user:
        # Interactive selection
        console.print()
        console.print("[bold]Where would you like to create the config file?[/bold]")
        console.print()
        console.print("  [cyan]1.[/cyan] Project-level (.consensus.yaml in current directory)")
        console.print("  [cyan]2.[/cyan] User-level (~/.consensus/config.yaml)")
        console.print()

        choice = click.prompt("Choose option", type=click.Choice(["1", "2"]), default="1")
        project = choice == "1"
        user = choice == "2"

    if project:
        config_path = Path.cwd() / ".consensus.yaml"
        if config_path.exists():
            if not click.confirm(f"{config_path} already exists. Overwrite?"):
                console.print("[dim]Cancelled.[/dim]")
                return
        create_example_config(config_path)
        console.print(f"[green]Created project config: {config_path}[/green]")

    if user:
        config_path = get_user_config_file()
        if config_path.exists():
            if not click.confirm(f"{config_path} already exists. Overwrite?"):
                console.print("[dim]Cancelled.[/dim]")
                return
        create_example_config(config_path)
        console.print(f"[green]Created user config: {config_path}[/green]")

    console.print()
    console.print("[dim]Edit the config file to customize settings.[/dim]")
    console.print("[dim]Run 'consensys config show' to verify.[/dim]")


@config.command("path")
def config_path():
    """Show paths to configuration files.

    Displays the paths where Consensus looks for configuration.
    """
    from src.settings import get_user_config_file, find_project_config

    console.print()
    console.print("[bold]Configuration File Paths:[/bold]")
    console.print()

    # User config
    user_config = get_user_config_file()
    user_exists = "[green]exists[/green]" if user_config.exists() else "[dim]not found[/dim]"
    console.print(f"  [bold]User-level:[/bold]")
    console.print(f"    {user_config} ({user_exists})")
    console.print()

    # Project config
    project_config = find_project_config()
    console.print(f"  [bold]Project-level:[/bold]")
    if project_config:
        console.print(f"    {project_config} [green]exists[/green]")
    else:
        console.print(f"    .consensus.yaml or .consensus.json in repo root ([dim]not found[/dim])")

    console.print()
    console.print("[dim]Precedence: CLI flags > project config > user config > defaults[/dim]")


@cli.command("web")
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
@click.option("--port", "-p", default=8000, type=int, help="Port to listen on (default: 8000)")
def web_server(host: str, port: int):
    """Start the web UI server.

    Launches a FastAPI server with a web interface for code reviews.
    Open http://localhost:8000 in your browser to access the UI.

    \b
    API Endpoints:
    - GET  /api/health          Health check
    - POST /api/review          Submit code for review
    - GET  /api/sessions        List past sessions
    - GET  /api/sessions/{id}   Get session details
    - WS   /ws/review           Streaming reviews
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error: uvicorn not installed.[/red]")
        console.print("Install web dependencies with: pip install consensys[web]")
        console.print("Or: pip install uvicorn fastapi websockets")
        sys.exit(1)

    console.print()
    console.print(Panel.fit(
        f"[bold green]Starting Consensus Web Server[/bold green]\n\n"
        f"Server: http://{host if host != '0.0.0.0' else 'localhost'}:{port}\n"
        f"API Docs: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs\n\n"
        "[dim]Press Ctrl+C to stop[/dim]",
        title="Consensus Web UI",
        border_style="green"
    ))
    console.print()

    from src.web.app import app
    uvicorn.run(app, host=host, port=port)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
