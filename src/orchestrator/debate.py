"""Debate orchestrator for multi-agent code review discussions."""
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from src.agents.agent import Agent, ReviewResult, ResponseResult, VoteResult
from src.agents.personas import PERSONAS, Persona
from src.models.review import Review, Response, Vote, Consensus, VoteDecision
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
        self.responses: List[Response] = []
        self.votes: List[Vote] = []
        self.consensus: Optional[Consensus] = None

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

    def _agent_response_task(
        self,
        agent: Agent,
        review: ReviewResult,
        code: str
    ) -> ResponseResult:
        """Execute a single agent's response to another review.

        Args:
            agent: The agent providing the response
            review: The review to respond to
            code: The original code being reviewed

        Returns:
            ResponseResult from the agent
        """
        return agent.respond_to(review, code)

    def _display_response(self, response: Response) -> None:
        """Display a response in a formatted panel.

        Args:
            response: The response to display
        """
        agreement_colors = {
            "AGREE": "green",
            "PARTIAL": "yellow",
            "DISAGREE": "red",
        }
        color = agreement_colors.get(response.agreement_level, "blue")

        content_lines = []

        # Header showing who is responding to whom
        content_lines.append(
            f"[bold]{response.agent_name}[/bold] responds to [bold]{response.responding_to}[/bold]"
        )
        content_lines.append(
            f"[bold]Agreement:[/bold] [{color}]{response.agreement_level}[/{color}]"
        )

        # Points made
        if response.points:
            content_lines.append(f"\n[bold]Points:[/bold]")
            for point in response.points:
                content_lines.append(f"  [cyan]\u2022[/cyan] {point}")

        # Summary
        if response.summary:
            content_lines.append(f"\n[bold]Summary:[/bold]\n{response.summary}")

        content = "\n".join(content_lines)

        # Create and display panel
        panel = Panel(
            content,
            title=f"[bold]{response.agent_name} \u2192 {response.responding_to}[/bold]",
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()

    def _display_response_summary(self) -> None:
        """Display a summary table of all responses and debate flow."""
        # Create debate flow visualization
        self.console.print()
        self.console.rule("[bold cyan]Debate Flow[/bold cyan]")
        self.console.print()

        agreement_colors = {
            "AGREE": "green",
            "PARTIAL": "yellow",
            "DISAGREE": "red",
        }

        # Group responses by responder
        responses_by_agent: Dict[str, List[Response]] = {}
        for response in self.responses:
            if response.agent_name not in responses_by_agent:
                responses_by_agent[response.agent_name] = []
            responses_by_agent[response.agent_name].append(response)

        # Display flow for each agent
        for agent_name, agent_responses in responses_by_agent.items():
            flow_parts = []
            for resp in agent_responses:
                color = agreement_colors.get(resp.agreement_level, "blue")
                flow_parts.append(f"[{color}]{resp.responding_to}[/{color}]")
            flow_str = ", ".join(flow_parts)
            self.console.print(f"[bold cyan]{agent_name}[/bold cyan] responded to: {flow_str}")

        # Summary table
        self.console.print()
        table = Table(title="Response Summary", show_header=True, header_style="bold")
        table.add_column("Responder", style="cyan")
        table.add_column("Responding To", style="blue")
        table.add_column("Agreement", justify="center")
        table.add_column("Points", justify="center")

        for response in self.responses:
            color = agreement_colors.get(response.agreement_level, "blue")
            table.add_row(
                response.agent_name,
                response.responding_to,
                f"[{color}]{response.agreement_level}[/{color}]",
                str(len(response.points)),
            )

        self.console.print(table)
        self.console.print()

    def run_responses(self) -> List[Response]:
        """Run Round 2: Response round where agents respond to each other.

        Each agent reviews all other agents' reviews and provides responses.
        Responses are collected in parallel and stored.

        Returns:
            List of Response objects from all agents

        Raises:
            ValueError: If no reviews exist (start_review not called)
        """
        if not self.reviews:
            raise ValueError(
                "No reviews to respond to. Call start_review() first."
            )

        if not self.session_id or not self.code:
            raise ValueError("No active session. Call start_review() first.")

        self.responses = []

        self.console.print()
        self.console.rule("[bold blue]Round 2: Debate Responses[/bold blue]")
        self.console.print()

        # Convert Review models to ReviewResult for agent.respond_to()
        review_results: Dict[str, ReviewResult] = {}
        for review in self.reviews:
            review_results[review.agent_name] = ReviewResult(
                agent_name=review.agent_name,
                issues=review.issues,
                suggestions=review.suggestions,
                severity=review.severity,
                confidence=review.confidence,
                summary=review.summary,
            )

        # Track all response tasks: (agent, target_review)
        response_tasks = []
        for agent in self.agents:
            for other_agent_name, review_result in review_results.items():
                # Skip self-responses
                if agent.persona.name != other_agent_name:
                    response_tasks.append((agent, review_result))

        # Track completed responses for ordered display
        completed_responses: List[ResponseResult] = []

        # Run all response tasks in parallel with progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            # Create a single progress task for overall progress
            overall_task = progress.add_task(
                f"[cyan]Agents debating ({len(response_tasks)} responses)...[/cyan]",
                total=len(response_tasks)
            )

            # Submit all responses to thread pool
            with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
                future_to_task = {
                    executor.submit(
                        self._agent_response_task,
                        agent,
                        review_result,
                        self.code
                    ): (agent, review_result)
                    for agent, review_result in response_tasks
                }

                # Collect results as they complete
                for future in as_completed(future_to_task):
                    agent, review_result = future_to_task[future]

                    try:
                        result = future.result()
                        completed_responses.append(result)
                        progress.advance(overall_task)

                    except Exception as e:
                        self.console.print(
                            f"[red]Error from {agent.persona.name} responding to "
                            f"{review_result.agent_name}: {e}[/red]"
                        )
                        progress.advance(overall_task)

        # Sort responses by agent name for consistent display
        completed_responses.sort(key=lambda r: (r.agent_name, r.responding_to))

        # Convert to Response models, display, and store
        for result in completed_responses:
            response = Response(
                agent_name=result.agent_name,
                responding_to=result.responding_to,
                agreement_level=result.agreement_level,
                points=result.points,
                summary=result.summary,
                session_id=self.session_id,
            )

            # Display the response
            self._display_response(response)

            # Store in database
            self.storage.save_response(response, self.session_id)

            # Keep track for later rounds
            self.responses.append(response)

        # Display summary
        self._display_response_summary()

        return self.responses

    def get_responses(self) -> List[Response]:
        """Get the responses from the current session.

        Returns:
            List of Response objects from the current session
        """
        return self.responses

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

    def get_votes(self) -> List[Vote]:
        """Get the votes from the current session.

        Returns:
            List of Vote objects from the current session
        """
        return self.votes

    def get_consensus(self) -> Optional[Consensus]:
        """Get the consensus from the current session.

        Returns:
            Consensus object or None if not yet built
        """
        return self.consensus

    def _agent_vote_task(
        self,
        agent: Agent,
        code: str,
        reviews: List[ReviewResult],
        responses: Optional[List[ResponseResult]]
    ) -> VoteResult:
        """Execute a single agent's vote.

        Args:
            agent: The agent casting the vote
            code: The code being voted on
            reviews: All reviews from Round 1
            responses: All responses from Round 2

        Returns:
            VoteResult from the agent
        """
        return agent.vote(code, reviews, responses)

    def _display_vote(self, vote: Vote) -> None:
        """Display a vote in a formatted panel.

        Args:
            vote: The vote to display
        """
        decision_colors = {
            "APPROVE": "green",
            "REJECT": "red",
            "ABSTAIN": "yellow",
        }
        decision_str = vote.decision.value if isinstance(vote.decision, VoteDecision) else str(vote.decision)
        color = decision_colors.get(decision_str, "blue")

        content_lines = []
        content_lines.append(f"[bold]Vote:[/bold] [{color}]{decision_str}[/{color}]")
        content_lines.append(f"\n[bold]Reasoning:[/bold]\n{vote.reasoning}")

        content = "\n".join(content_lines)

        panel = Panel(
            content,
            title=f"[bold]{vote.agent_name}[/bold]",
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()

    def _display_vote_summary(self) -> None:
        """Display a summary table of all votes."""
        decision_colors = {
            "APPROVE": "green",
            "REJECT": "red",
            "ABSTAIN": "yellow",
        }

        table = Table(title="Vote Summary", show_header=True, header_style="bold")
        table.add_column("Voter", style="cyan")
        table.add_column("Decision", justify="center")

        for vote in self.votes:
            decision_str = vote.decision.value if isinstance(vote.decision, VoteDecision) else str(vote.decision)
            color = decision_colors.get(decision_str, "blue")
            table.add_row(
                vote.agent_name,
                f"[{color}]{decision_str}[/{color}]",
            )

        self.console.print()
        self.console.print(table)
        self.console.print()

    def run_voting(self) -> List[Vote]:
        """Run Round 3: Voting round where agents cast their final votes.

        Each agent considers all reviews and responses before voting
        APPROVE, REJECT, or ABSTAIN on the code.

        Returns:
            List of Vote objects from all agents

        Raises:
            ValueError: If no reviews exist (start_review not called)
        """
        if not self.reviews:
            raise ValueError(
                "No reviews to base votes on. Call start_review() first."
            )

        if not self.session_id or not self.code:
            raise ValueError("No active session. Call start_review() first.")

        self.votes = []

        self.console.print()
        self.console.rule("[bold blue]Round 3: Final Voting[/bold blue]")
        self.console.print()

        # Convert Review models to ReviewResult for agent.vote()
        review_results: List[ReviewResult] = []
        for review in self.reviews:
            review_results.append(ReviewResult(
                agent_name=review.agent_name,
                issues=review.issues,
                suggestions=review.suggestions,
                severity=review.severity,
                confidence=review.confidence,
                summary=review.summary,
            ))

        # Convert Response models to ResponseResult for agent.vote()
        response_results: Optional[List[ResponseResult]] = None
        if self.responses:
            response_results = []
            for resp in self.responses:
                response_results.append(ResponseResult(
                    agent_name=resp.agent_name,
                    responding_to=resp.responding_to,
                    agreement_level=resp.agreement_level,
                    points=resp.points,
                    summary=resp.summary,
                ))

        # Track completed votes
        completed_votes: List[VoteResult] = []

        # Run all votes in parallel with progress display
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
                    f"[cyan]{agent.persona.name}[/cyan] is deliberating...",
                    total=None
                )
                agent_tasks[agent.persona.name] = task_id

            # Submit all votes to thread pool
            with ThreadPoolExecutor(max_workers=len(self.agents)) as executor:
                future_to_agent = {
                    executor.submit(
                        self._agent_vote_task,
                        agent,
                        self.code,
                        review_results,
                        response_results
                    ): agent
                    for agent in self.agents
                }

                # Collect results as they complete
                for future in as_completed(future_to_agent):
                    agent = future_to_agent[future]
                    agent_name = agent.persona.name

                    try:
                        result = future.result()
                        completed_votes.append(result)

                        # Update progress
                        task_id = agent_tasks[agent_name]
                        progress.update(
                            task_id,
                            description=f"[green]✓ {agent_name}[/green] voted"
                        )
                        progress.remove_task(task_id)

                    except Exception as e:
                        self.console.print(
                            f"[red]Error from {agent_name}: {e}[/red]"
                        )
                        task_id = agent_tasks[agent_name]
                        progress.remove_task(task_id)

        # Sort votes by agent name for consistent display
        completed_votes.sort(key=lambda v: v.agent_name)

        # Convert to Vote models, display, and store
        for result in completed_votes:
            vote = Vote(
                agent_name=result.agent_name,
                decision=result.decision,
                reasoning=result.reasoning,
                session_id=self.session_id,
            )

            # Display the vote
            self._display_vote(vote)

            # Store in database
            self.storage.save_vote(vote, self.session_id)

            # Keep track
            self.votes.append(vote)

        # Display summary
        self._display_vote_summary()

        return self.votes

    def build_consensus(self) -> Consensus:
        """Build consensus from the debate.

        Aggregates votes, identifies key issues agreed upon by multiple agents,
        and determines the final decision. Uses conservative tie-breaking:
        REJECT wins ties.

        Returns:
            Consensus object with final decision and aggregated insights

        Raises:
            ValueError: If no votes exist (run_voting not called)
        """
        if not self.votes:
            raise ValueError(
                "No votes to build consensus from. Call run_voting() first."
            )

        if not self.session_id or not self.code:
            raise ValueError("No active session. Call start_review() first.")

        self.console.print()
        self.console.rule("[bold blue]Building Consensus[/bold blue]")
        self.console.print()

        # Count votes
        vote_counts = {"APPROVE": 0, "REJECT": 0, "ABSTAIN": 0}
        for vote in self.votes:
            decision_str = vote.decision.value if isinstance(vote.decision, VoteDecision) else str(vote.decision)
            if decision_str in vote_counts:
                vote_counts[decision_str] += 1

        # Determine final decision with tie-breaking (REJECT wins ties)
        approve_count = vote_counts["APPROVE"]
        reject_count = vote_counts["REJECT"]

        if approve_count > reject_count:
            final_decision = VoteDecision.APPROVE
        elif reject_count > approve_count:
            final_decision = VoteDecision.REJECT
        else:
            # Tie: REJECT wins (conservative approach)
            final_decision = VoteDecision.REJECT

        # Aggregate key issues - collect issues mentioned by multiple agents
        issue_mentions: Dict[str, int] = {}  # description -> count
        all_issues: List[Dict[str, Any]] = []

        for review in self.reviews:
            for issue in review.issues:
                desc = issue.get("description", str(issue))
                # Normalize for comparison
                desc_lower = desc.lower().strip()
                issue_mentions[desc_lower] = issue_mentions.get(desc_lower, 0) + 1
                if desc_lower not in [i.get("description", "").lower().strip() for i in all_issues]:
                    all_issues.append(issue)

        # Key issues are those mentioned by 2+ agents or have HIGH/CRITICAL severity
        key_issues = []
        for issue in all_issues:
            desc = issue.get("description", str(issue))
            desc_lower = desc.lower().strip()
            severity = issue.get("severity", "LOW")
            if issue_mentions.get(desc_lower, 0) >= 2 or severity in ("CRITICAL", "HIGH"):
                key_issues.append(issue)

        # Aggregate suggestions - collect suggestions mentioned by multiple agents
        suggestion_mentions: Dict[str, int] = {}
        all_suggestions: List[str] = []

        for review in self.reviews:
            for suggestion in review.suggestions:
                sug_lower = suggestion.lower().strip()
                suggestion_mentions[sug_lower] = suggestion_mentions.get(sug_lower, 0) + 1
                if sug_lower not in [s.lower().strip() for s in all_suggestions]:
                    all_suggestions.append(suggestion)

        # Accepted suggestions are those mentioned by 2+ agents
        accepted_suggestions = [
            s for s in all_suggestions
            if suggestion_mentions.get(s.lower().strip(), 0) >= 2
        ]

        # Create consensus
        self.consensus = Consensus(
            final_decision=final_decision,
            vote_counts=vote_counts,
            key_issues=key_issues,
            accepted_suggestions=accepted_suggestions,
            session_id=self.session_id,
            code_snippet=self.code,
            context=self.context,
        )

        # Save to database
        self.storage.save_consensus(self.consensus)

        # Display consensus
        self._display_consensus()

        return self.consensus

    def _display_consensus(self) -> None:
        """Display the final consensus in a formatted panel."""
        if not self.consensus:
            return

        decision_colors = {
            VoteDecision.APPROVE: "green",
            VoteDecision.REJECT: "red",
            VoteDecision.ABSTAIN: "yellow",
        }
        color = decision_colors.get(self.consensus.final_decision, "blue")
        decision_str = self.consensus.final_decision.value

        content_lines = []

        # Vote breakdown
        content_lines.append("[bold]Vote Breakdown:[/bold]")
        content_lines.append(
            f"  [green]APPROVE[/green]: {self.consensus.vote_counts.get('APPROVE', 0)}"
        )
        content_lines.append(
            f"  [red]REJECT[/red]: {self.consensus.vote_counts.get('REJECT', 0)}"
        )
        content_lines.append(
            f"  [yellow]ABSTAIN[/yellow]: {self.consensus.vote_counts.get('ABSTAIN', 0)}"
        )

        # Key issues
        if self.consensus.key_issues:
            content_lines.append(f"\n[bold]Key Issues ({len(self.consensus.key_issues)}):[/bold]")
            for issue in self.consensus.key_issues:
                desc = issue.get("description", str(issue))
                sev = issue.get("severity", "LOW")
                sev_colors = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
                sev_color = sev_colors.get(sev, "blue")
                content_lines.append(f"  [{sev_color}]•[/{sev_color}] {desc}")
        else:
            content_lines.append("\n[green]✓ No major issues identified[/green]")

        # Accepted suggestions
        if self.consensus.accepted_suggestions:
            content_lines.append(
                f"\n[bold]Agreed Suggestions ({len(self.consensus.accepted_suggestions)}):[/bold]"
            )
            for suggestion in self.consensus.accepted_suggestions:
                content_lines.append(f"  [cyan]•[/cyan] {suggestion}")

        content = "\n".join(content_lines)

        # Create panel with decision as title
        panel = Panel(
            content,
            title=f"[bold {color}]Final Decision: {decision_str}[/bold {color}]",
            border_style=color,
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()

    def run_full_debate(
        self,
        code: str,
        context: Optional[str] = None
    ) -> Consensus:
        """Run a complete debate: review -> respond -> vote -> consensus.

        This is the main entry point for running a full multi-agent code review.

        Args:
            code: The code to review
            context: Optional context about the code

        Returns:
            Consensus object with final decision and insights
        """
        # Round 1: Initial reviews
        self.start_review(code, context)

        # Round 2: Responses/Rebuttals
        self.run_responses()

        # Round 3: Final voting
        self.run_voting()

        # Build and return consensus
        return self.build_consensus()

    def __repr__(self) -> str:
        agent_names = [a.persona.name for a in self.agents]
        return f"DebateOrchestrator(agents={agent_names})"
