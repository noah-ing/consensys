"""Export debate sessions to markdown and HTML formats."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import html

from src.db.storage import Storage
from src.models.review import Review, Response, Vote, Consensus, VoteDecision


@dataclass
class DebateData:
    """Complete debate data for export."""
    session_id: str
    code: str
    context: Optional[str]
    created_at: str
    final_decision: Optional[str]
    reviews: List[Review]
    responses: List[Response]
    votes: List[Vote]
    consensus: Optional[Consensus]


class DebateExporter:
    """Export debate sessions to various formats."""

    def __init__(self, storage: Optional[Storage] = None):
        """Initialize exporter with storage backend."""
        self.storage = storage or Storage()

    def load_debate(self, session_id: str) -> Optional[DebateData]:
        """Load complete debate data for a session.

        Args:
            session_id: The session ID (or prefix)

        Returns:
            DebateData or None if not found
        """
        # Handle partial session ID matching
        sessions = self.storage.list_sessions(limit=100)
        matching = [s for s in sessions if s["session_id"].startswith(session_id)]

        if not matching:
            return None

        if len(matching) > 1:
            # Return None for ambiguous matches
            return None

        full_session_id = matching[0]["session_id"]
        session = self.storage.get_session(full_session_id)

        if not session:
            return None

        return DebateData(
            session_id=full_session_id,
            code=session["code_snippet"],
            context=session.get("context"),
            created_at=session["created_at"],
            final_decision=session.get("final_decision"),
            reviews=self.storage.get_reviews(full_session_id),
            responses=self.storage.get_responses(full_session_id),
            votes=self.storage.get_votes(full_session_id),
            consensus=self.storage.get_consensus(full_session_id),
        )

    def to_markdown(self, session_id: str) -> Optional[str]:
        """Export debate to markdown format.

        Args:
            session_id: The session ID (or prefix)

        Returns:
            Markdown string or None if session not found
        """
        debate = self.load_debate(session_id)
        if not debate:
            return None

        return _generate_markdown(debate)

    def to_html(self, session_id: str) -> Optional[str]:
        """Export debate to styled HTML format.

        Args:
            session_id: The session ID (or prefix)

        Returns:
            HTML string or None if session not found
        """
        debate = self.load_debate(session_id)
        if not debate:
            return None

        return _generate_html(debate)

    def save_markdown(self, session_id: str, output_path: Path) -> bool:
        """Export debate to markdown file.

        Args:
            session_id: The session ID
            output_path: Path to save the file

        Returns:
            True if successful
        """
        content = self.to_markdown(session_id)
        if not content:
            return False
        output_path.write_text(content)
        return True

    def save_html(self, session_id: str, output_path: Path) -> bool:
        """Export debate to HTML file.

        Args:
            session_id: The session ID
            output_path: Path to save the file

        Returns:
            True if successful
        """
        content = self.to_html(session_id)
        if not content:
            return False
        output_path.write_text(content)
        return True


def _generate_markdown(debate: DebateData) -> str:
    """Generate markdown representation of a debate."""
    lines = []

    # Header
    lines.append("# Consensus Code Review")
    lines.append("")
    lines.append(f"**Session ID:** `{debate.session_id}`")
    lines.append(f"**Date:** {debate.created_at[:19].replace('T', ' ')}")
    if debate.final_decision:
        lines.append(f"**Final Decision:** {debate.final_decision}")
    lines.append("")

    # Code
    lines.append("## Code Under Review")
    lines.append("")
    lines.append("```python")
    lines.append(debate.code)
    lines.append("```")
    lines.append("")

    if debate.context:
        lines.append(f"**Context:** {debate.context}")
        lines.append("")

    # Reviews
    if debate.reviews:
        lines.append("## Round 1: Initial Reviews")
        lines.append("")

        for review in debate.reviews:
            lines.append(f"### {review.agent_name}")
            lines.append("")
            lines.append(f"**Severity:** {review.severity} | **Confidence:** {review.confidence:.0%}")
            lines.append("")

            if review.issues:
                lines.append("**Issues:**")
                for issue in review.issues:
                    desc = issue.get("description", str(issue))
                    sev = issue.get("severity", "LOW")
                    lines.append(f"- [{sev}] {desc}")
                lines.append("")

            if review.suggestions:
                lines.append("**Suggestions:**")
                for suggestion in review.suggestions:
                    lines.append(f"- {suggestion}")
                lines.append("")

            if review.summary:
                lines.append(f"**Summary:** {review.summary}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Responses
    if debate.responses:
        lines.append("## Round 2: Debate Responses")
        lines.append("")

        for response in debate.responses:
            lines.append(f"### {response.agent_name} responds to {response.responding_to}")
            lines.append("")
            lines.append(f"**Agreement:** {response.agreement_level}")
            lines.append("")

            if response.points:
                lines.append("**Points:**")
                for point in response.points:
                    lines.append(f"- {point}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Votes
    if debate.votes:
        lines.append("## Round 3: Final Voting")
        lines.append("")

        for vote in debate.votes:
            decision_str = vote.decision.value if isinstance(
                vote.decision, VoteDecision
            ) else str(vote.decision)
            lines.append(f"### {vote.agent_name}: {decision_str}")
            lines.append("")
            if vote.reasoning:
                lines.append(f"**Reasoning:** {vote.reasoning}")
                lines.append("")
            lines.append("---")
            lines.append("")

    # Consensus
    if debate.consensus:
        lines.append("## Final Consensus")
        lines.append("")

        decision_str = debate.consensus.final_decision.value if isinstance(
            debate.consensus.final_decision, VoteDecision
        ) else str(debate.consensus.final_decision)
        lines.append(f"**Decision:** {decision_str}")
        lines.append("")

        lines.append("**Vote Breakdown:**")
        lines.append(f"- APPROVE: {debate.consensus.vote_counts.get('APPROVE', 0)}")
        lines.append(f"- REJECT: {debate.consensus.vote_counts.get('REJECT', 0)}")
        lines.append(f"- ABSTAIN: {debate.consensus.vote_counts.get('ABSTAIN', 0)}")
        lines.append("")

        if debate.consensus.key_issues:
            lines.append("**Key Issues:**")
            for issue in debate.consensus.key_issues:
                desc = issue.get("description", str(issue))
                lines.append(f"- {desc}")
            lines.append("")

        if debate.consensus.accepted_suggestions:
            lines.append("**Agreed Suggestions:**")
            for suggestion in debate.consensus.accepted_suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by [Consensus](https://github.com/consensus) - Multi-agent AI code review*")

    return "\n".join(lines)


def _generate_html(debate: DebateData) -> str:
    """Generate styled HTML representation of a debate."""
    # Agent avatar colors
    avatar_colors = {
        "SecurityExpert": "#e74c3c",
        "PerformanceEngineer": "#3498db",
        "ArchitectureCritic": "#9b59b6",
        "PragmaticDev": "#27ae60",
    }

    # Severity colors
    severity_colors = {
        "CRITICAL": "#e74c3c",
        "HIGH": "#e67e22",
        "MEDIUM": "#f1c40f",
        "LOW": "#27ae60",
    }

    # Decision colors
    decision_colors = {
        "APPROVE": "#27ae60",
        "REJECT": "#e74c3c",
        "ABSTAIN": "#f1c40f",
    }

    # Agreement colors
    agreement_colors = {
        "AGREE": "#27ae60",
        "PARTIAL": "#f1c40f",
        "DISAGREE": "#e74c3c",
    }

    def get_avatar(name: str) -> str:
        """Generate avatar HTML for an agent."""
        color = avatar_colors.get(name, "#7f8c8d")
        initials = "".join(c for c in name if c.isupper())[:2] or name[:2].upper()
        return f'<span class="avatar" style="background-color: {color};">{initials}</span>'

    def escape(text: str) -> str:
        """HTML escape text."""
        return html.escape(str(text))

    html_parts = []

    # HTML head with styles
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Consensus Review - {escape(debate.session_id[:12])}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            color: white;
        }}
        .header-meta {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        .decision-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
            margin-top: 10px;
        }}
        .code-section {{
            background: #1e1e1e;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            overflow-x: auto;
        }}
        .code-section h2 {{
            color: #fff;
            margin-top: 0;
        }}
        .code-section pre {{
            color: #d4d4d4;
            margin: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .context {{
            background: #e8f4f8;
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 30px;
            border-left: 4px solid #3498db;
        }}
        .section {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .avatar {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            color: white;
            font-weight: bold;
            font-size: 14px;
            margin-right: 10px;
        }}
        .review-card, .response-card, .vote-card {{
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background: #fafafa;
        }}
        .review-card.collapsed .review-content,
        .response-card.collapsed .response-content,
        .vote-card.collapsed .vote-content {{
            display: none;
        }}
        .card-header {{
            display: flex;
            align-items: center;
            cursor: pointer;
        }}
        .card-header:hover {{
            opacity: 0.8;
        }}
        .agent-name {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        .meta {{
            margin-left: auto;
            font-size: 0.9em;
            color: #666;
        }}
        .expand-icon {{
            margin-left: 10px;
            transition: transform 0.2s;
        }}
        .collapsed .expand-icon {{
            transform: rotate(-90deg);
        }}
        .severity-badge, .agreement-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
            color: white;
            margin-left: 10px;
        }}
        .issues-list, .suggestions-list, .points-list {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .issue-item {{
            margin-bottom: 5px;
        }}
        .issue-severity {{
            display: inline-block;
            padding: 1px 5px;
            border-radius: 3px;
            font-size: 0.75em;
            color: white;
            margin-right: 5px;
        }}
        .summary {{
            background: #f0f0f0;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            font-style: italic;
        }}
        .consensus-section {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 10px;
            padding: 25px;
            margin-top: 30px;
        }}
        .vote-breakdown {{
            display: flex;
            gap: 20px;
            margin: 15px 0;
        }}
        .vote-count {{
            padding: 10px 20px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        }}
        .key-issues, .agreed-suggestions {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
        .arrow {{
            color: #888;
            margin: 0 5px;
        }}
    </style>
</head>
<body>
""")

    # Header
    decision_str = debate.final_decision or "In Progress"
    decision_color = decision_colors.get(decision_str, "#7f8c8d")
    html_parts.append(f"""
    <div class="header">
        <h1>Consensus Code Review</h1>
        <div class="header-meta">
            <strong>Session:</strong> {escape(debate.session_id)}<br>
            <strong>Date:</strong> {escape(debate.created_at[:19].replace('T', ' '))}
        </div>
        <div class="decision-badge" style="background-color: {decision_color};">
            {escape(decision_str)}
        </div>
    </div>
""")

    # Code section
    html_parts.append(f"""
    <div class="code-section">
        <h2>Code Under Review</h2>
        <pre>{escape(debate.code)}</pre>
    </div>
""")

    if debate.context:
        html_parts.append(f"""
    <div class="context">
        <strong>Context:</strong> {escape(debate.context)}
    </div>
""")

    # Reviews section
    if debate.reviews:
        html_parts.append("""
    <div class="section">
        <h2>Round 1: Initial Reviews</h2>
""")
        for review in debate.reviews:
            sev_color = severity_colors.get(review.severity, "#7f8c8d")
            html_parts.append(f"""
        <div class="review-card">
            <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
                {get_avatar(review.agent_name)}
                <span class="agent-name">{escape(review.agent_name)}</span>
                <span class="severity-badge" style="background-color: {sev_color};">{escape(review.severity)}</span>
                <span class="meta">Confidence: {review.confidence:.0%}</span>
                <span class="expand-icon">▼</span>
            </div>
            <div class="review-content">
""")
            if review.issues:
                html_parts.append("                <h4>Issues:</h4>\n                <ul class=\"issues-list\">\n")
                for issue in review.issues:
                    desc = issue.get("description", str(issue))
                    sev = issue.get("severity", "LOW")
                    issue_color = severity_colors.get(sev, "#7f8c8d")
                    html_parts.append(f'                    <li class="issue-item"><span class="issue-severity" style="background-color: {issue_color};">{escape(sev)}</span> {escape(desc)}</li>\n')
                html_parts.append("                </ul>\n")

            if review.suggestions:
                html_parts.append("                <h4>Suggestions:</h4>\n                <ul class=\"suggestions-list\">\n")
                for suggestion in review.suggestions:
                    html_parts.append(f"                    <li>{escape(suggestion)}</li>\n")
                html_parts.append("                </ul>\n")

            if review.summary:
                html_parts.append(f"                <div class=\"summary\">{escape(review.summary)}</div>\n")

            html_parts.append("            </div>\n        </div>\n")

        html_parts.append("    </div>\n")

    # Responses section
    if debate.responses:
        html_parts.append("""
    <div class="section">
        <h2>Round 2: Debate Responses</h2>
""")
        for response in debate.responses:
            agree_color = agreement_colors.get(response.agreement_level, "#7f8c8d")
            html_parts.append(f"""
        <div class="response-card">
            <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
                {get_avatar(response.agent_name)}
                <span class="agent-name">{escape(response.agent_name)}</span>
                <span class="arrow">→</span>
                <span>{escape(response.responding_to)}</span>
                <span class="agreement-badge" style="background-color: {agree_color};">{escape(response.agreement_level)}</span>
                <span class="expand-icon">▼</span>
            </div>
            <div class="response-content">
""")
            if response.points:
                html_parts.append("                <ul class=\"points-list\">\n")
                for point in response.points:
                    html_parts.append(f"                    <li>{escape(point)}</li>\n")
                html_parts.append("                </ul>\n")

            html_parts.append("            </div>\n        </div>\n")

        html_parts.append("    </div>\n")

    # Votes section
    if debate.votes:
        html_parts.append("""
    <div class="section">
        <h2>Round 3: Final Voting</h2>
""")
        for vote in debate.votes:
            decision_val = vote.decision.value if isinstance(vote.decision, VoteDecision) else str(vote.decision)
            vote_color = decision_colors.get(decision_val, "#7f8c8d")
            html_parts.append(f"""
        <div class="vote-card">
            <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
                {get_avatar(vote.agent_name)}
                <span class="agent-name">{escape(vote.agent_name)}</span>
                <span class="severity-badge" style="background-color: {vote_color};">{escape(decision_val)}</span>
                <span class="expand-icon">▼</span>
            </div>
            <div class="vote-content">
                <div class="summary">{escape(vote.reasoning)}</div>
            </div>
        </div>
""")
        html_parts.append("    </div>\n")

    # Consensus section
    if debate.consensus:
        cons_decision = debate.consensus.final_decision.value if isinstance(
            debate.consensus.final_decision, VoteDecision
        ) else str(debate.consensus.final_decision)
        cons_color = decision_colors.get(cons_decision, "#7f8c8d")

        html_parts.append(f"""
    <div class="consensus-section">
        <h2>Final Consensus</h2>
        <div class="decision-badge" style="background-color: {cons_color}; font-size: 1.2em;">
            {escape(cons_decision)}
        </div>
        <div class="vote-breakdown">
            <div class="vote-count" style="background-color: {decision_colors['APPROVE']};">
                APPROVE: {debate.consensus.vote_counts.get('APPROVE', 0)}
            </div>
            <div class="vote-count" style="background-color: {decision_colors['REJECT']};">
                REJECT: {debate.consensus.vote_counts.get('REJECT', 0)}
            </div>
            <div class="vote-count" style="background-color: {decision_colors['ABSTAIN']};">
                ABSTAIN: {debate.consensus.vote_counts.get('ABSTAIN', 0)}
            </div>
        </div>
""")
        if debate.consensus.key_issues:
            html_parts.append("        <div class=\"key-issues\">\n            <h4>Key Issues:</h4>\n            <ul>\n")
            for issue in debate.consensus.key_issues:
                desc = issue.get("description", str(issue))
                html_parts.append(f"                <li>{escape(desc)}</li>\n")
            html_parts.append("            </ul>\n        </div>\n")

        if debate.consensus.accepted_suggestions:
            html_parts.append("        <div class=\"agreed-suggestions\">\n            <h4>Agreed Suggestions:</h4>\n            <ul>\n")
            for suggestion in debate.consensus.accepted_suggestions:
                html_parts.append(f"                <li>{escape(suggestion)}</li>\n")
            html_parts.append("            </ul>\n        </div>\n")

        html_parts.append("    </div>\n")

    # Footer
    html_parts.append("""
    <div class="footer">
        <p>Generated by <a href="https://github.com/consensus">Consensus</a> - Multi-agent AI code review</p>
    </div>
</body>
</html>
""")

    return "".join(html_parts)


def export_to_markdown(session_id: str, output_path: Optional[Path] = None) -> Optional[str]:
    """Convenience function to export a session to markdown.

    Args:
        session_id: The session ID (or prefix)
        output_path: Optional path to save the file

    Returns:
        Markdown content or None if session not found
    """
    exporter = DebateExporter()
    if output_path:
        success = exporter.save_markdown(session_id, output_path)
        return exporter.to_markdown(session_id) if success else None
    return exporter.to_markdown(session_id)


def export_to_html(session_id: str, output_path: Optional[Path] = None) -> Optional[str]:
    """Convenience function to export a session to HTML.

    Args:
        session_id: The session ID (or prefix)
        output_path: Optional path to save the file

    Returns:
        HTML content or None if session not found
    """
    exporter = DebateExporter()
    if output_path:
        success = exporter.save_html(session_id, output_path)
        return exporter.to_html(session_id) if success else None
    return exporter.to_html(session_id)
