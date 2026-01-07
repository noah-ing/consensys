"""Debate orchestrator for multi-agent code review discussions."""
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from src.agents.agent import Agent, ReviewResult
from src.agents.personas import PERSONAS, Persona
from src.models.review import Review
from src.db.storage import Storage


class DebateOrchestrator:
    """Manages multi-agent code review debates.

    Coordinates multiple AI agents to review code, discuss findings,
    and reach consensus through structured debate.
    """

    def __init__(
        self,
        personas: Optional[List[Persona]] = None,
        storage: Optional[Storage] = None,
        console: Optional[Console] = None,
    ):
        """Initialize the debate orchestrator.

        Args:
            personas: List of personas to use. Defaults to all PERSONAS.
            storage: Storage instance for persistence. Created if not provided.
            console: Rich console for output. Created if not provided.
        """
        self.personas = personas or PERSONAS
        self.agents = [Agent(persona) for persona in self.personas]
        self.storage = storage or Storage()
        self.console = console or Console()

        # Current session state
        self.session_id: Optional[str] = None
        self.code: Optional[str] = None
        self.context: Optional[str] = None
        self.reviews: List[Review] = []

    def _agent_review_task(
        self,
        agent: Agent,
        code: str,
        context: Optional[str]
    ) -> ReviewResult:
        """Execute a single agent's review.

        Args:
            agent: The agent to perform the review
            code: The code to review
            context: Optional context for the review

        Returns:
            ReviewResult from the agent
        """
        return agent.review(code, context)

    def _display_review(self, review: Review) -> None:
        """Display a review in a formatted panel.

        Args:
            review: The review to display
        """
        # Determine panel color based on severity
        severity_colors = {
            "CRITICAL": "red",
            "HIGH": "red",
            "MEDIUM": "yellow",
            "LOW": "green",
        }
        color = severity_colors.get(review.severity, "blue")

        # Build review content
        content_lines = []

        # Severity and confidence
        content_lines.append(f"[bold]Severity:[/bold] [{color}]{review.severity}[/{color}]")
        content_lines.append(f"[bold]Confidence:[/bold] {review.confidence:.0%}")

        # Issues
        if review.issues:
            content_lines.append(f"\n[bold]Issues ({len(review.issues)}):[/bold]")
            for issue in review.issues:
                desc = issue.get("description", str(issue))
                sev = issue.get("severity", "LOW")
                sev_color = severity_colors.get(sev, "blue")
                line_info = f" (line {issue['line']})" if issue.get("line") else ""
                content_lines.append(f"  [{sev_color}]\u2022[/{sev_color}] {desc}{line_info}")
        else:
            content_lines.append("\n[green]\u2713 No issues found[/green]")

        # Suggestions
        if review.suggestions:
            content_lines.append(f"\n[bold]Suggestions:[/bold]")
            for suggestion in review.suggestions:
                content_lines.append(f"  [cyan]\u2022[/cyan] {suggestion}")

        # Summary
        if review.summary:
            content_lines.append(f"\n[bold]Summary:[/bold]\n{review.summary}")

        content = "\n".join(content_lines)

        # Create and display panel
        panel = Panel(
            content,
            title=f"[bold]{review.agent_name}[/bold]",
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()

    def start_review(
        self,
        code: str,
        context: Optional[str] = None
    ) -> List[Review]:
        """Start a new review session with Round 1 reviews.

        All agents review the code in parallel, then their reviews
        are displayed and stored.

        Args:
            code: The code to review
            context: Optional context about the code

        Returns:
            List of Review objects from all agents
        """
        # Create a new session
        self.session_id = self.storage.create_session(code, context)
        self.code = code
        self.context = context
        self.reviews = []

        self.console.print()
        self.console.rule("[bold blue]Round 1: Initial Reviews[/bold blue]")
        self.console.print()

        # Track completed reviews for display
        completed_reviews: Dict[str, ReviewResult] = {}

        # Run all agent reviews in parallel with progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            # Create tasks for each agent
            agent_tasks = {}
            for agent in self.agents:
                task_id = progress.add_task(
                    f"[cyan]{agent.persona.name}[/cyan] is reviewing...",
                    total=None
                )
                agent_tasks[agent.persona.name] = task_id

            # Submit all reviews to thread pool
            with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
                future_to_agent = {
                    executor.submit(
                        self._agent_review_task,
                        agent,
                        code,
                        context
                    ): agent
                    for agent in self.agents
                }

                # Collect results as they complete
                for future in as_completed(future_to_agent):
                    agent = future_to_agent[future]
                    agent_name = agent.persona.name

                    try:
                        result = future.result()
                        completed_reviews[agent_name] = result

                        # Update progress
                        task_id = agent_tasks[agent_name]
                        progress.update(
                            task_id,
                            description=f"[green]\u2713 {agent_name}[/green] completed"
                        )
                        progress.remove_task(task_id)

                    except Exception as e:
                        self.console.print(
                            f"[red]Error from {agent_name}: {e}[/red]"
                        )
                        task_id = agent_tasks[agent_name]
                        progress.remove_task(task_id)

        # Convert to Review models, display, and store
        for agent in self.agents:
            agent_name = agent.persona.name
            if agent_name in completed_reviews:
                result = completed_reviews[agent_name]

                # Convert ReviewResult to Review model
                review = Review(
                    agent_name=result.agent_name,
                    issues=result.issues,
                    suggestions=result.suggestions,
                    severity=result.severity,
                    confidence=result.confidence,
                    summary=result.summary,
                    session_id=self.session_id,
                )

                # Display the review
                self._display_review(review)

                # Store in database
                self.storage.save_review(review, self.session_id)

                # Keep track for later rounds
                self.reviews.append(review)

        # Display summary table
        self._display_review_summary()

        return self.reviews

    def _display_review_summary(self) -> None:
        """Display a summary table of all reviews."""
        table = Table(title="Review Summary", show_header=True, header_style="bold")
        table.add_column("Reviewer", style="cyan")
        table.add_column("Severity", justify="center")
        table.add_column("Issues", justify="center")
        table.add_column("Confidence", justify="center")

        severity_colors = {
            "CRITICAL": "red",
            "HIGH": "red",
            "MEDIUM": "yellow",
            "LOW": "green",
        }

        for review in self.reviews:
            color = severity_colors.get(review.severity, "blue")
            table.add_row(
                review.agent_name,
                f"[{color}]{review.severity}[/{color}]",
                str(len(review.issues)),
                f"{review.confidence:.0%}",
            )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID.

        Returns:
            The current session ID or None if no session is active
        """
        return self.session_id

    def get_reviews(self) -> List[Review]:
        """Get the reviews from the current session.

        Returns:
            List of Review objects from the current session
        """
        return self.reviews

    def __repr__(self) -> str:
        agent_names = [a.persona.name for a in self.agents]
        return f"DebateOrchestrator(agents={agent_names})"
