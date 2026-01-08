"""Data models for the Consensys code review system."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime
import uuid


class VoteDecision(Enum):
    """Possible vote outcomes for code review."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


class AgreementLevel(Enum):
    """Agreement levels for response to reviews."""
    AGREE = "AGREE"
    PARTIAL = "PARTIAL"
    DISAGREE = "DISAGREE"


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Issue:
    """A specific issue found during code review."""
    description: str
    severity: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    line: Optional[int] = None


@dataclass
class Review:
    """Structured result from a code review.

    Attributes:
        agent_name: Name of the reviewing agent
        issues: List of issues found in the code
        suggestions: List of improvement suggestions
        severity: Overall severity assessment
        confidence: Agent's confidence in their review (0.0-1.0)
        summary: Brief overall assessment
        session_id: UUID of the review session
        timestamp: When the review was created
    """
    agent_name: str
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "LOW"
    confidence: float = 0.8
    summary: str = ""
    session_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Response:
    """Structured response to another agent's review.

    Attributes:
        agent_name: Name of the responding agent
        responding_to: Name of the agent being responded to
        agreement_level: Level of agreement (AGREE, PARTIAL, DISAGREE)
        points: List of response points/arguments
        summary: Brief summary of the response
        session_id: UUID of the review session
        timestamp: When the response was created
    """
    agent_name: str
    responding_to: str
    agreement_level: str = "PARTIAL"  # AGREE, PARTIAL, DISAGREE
    points: List[str] = field(default_factory=list)
    summary: str = ""
    session_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Vote:
    """Structured vote on code quality.

    Attributes:
        agent_name: Name of the voting agent
        decision: Vote decision (APPROVE, REJECT, ABSTAIN)
        reasoning: Explanation for the vote
        session_id: UUID of the review session
        timestamp: When the vote was cast
    """
    agent_name: str
    decision: VoteDecision = VoteDecision.ABSTAIN
    reasoning: str = ""
    session_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Consensus:
    """Final consensus from the multi-agent review.

    Attributes:
        final_decision: The overall decision (APPROVE, REJECT, ABSTAIN)
        vote_counts: Dict with counts for each vote type
        key_issues: List of the most important issues identified
        accepted_suggestions: List of suggestions agreed upon by multiple agents
        session_id: UUID of the review session
        code_snippet: The code that was reviewed
        context: Optional context provided for the review
        timestamp: When consensus was reached
    """
    final_decision: VoteDecision
    vote_counts: Dict[str, int] = field(default_factory=lambda: {
        "APPROVE": 0,
        "REJECT": 0,
        "ABSTAIN": 0
    })
    key_issues: List[Dict[str, Any]] = field(default_factory=list)
    accepted_suggestions: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    code_snippet: str = ""
    context: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.session_id is None:
            self.session_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def total_votes(self) -> int:
        """Get total number of votes cast."""
        return sum(self.vote_counts.values())

    @property
    def is_approved(self) -> bool:
        """Check if the code was approved."""
        return self.final_decision == VoteDecision.APPROVE

    @property
    def is_rejected(self) -> bool:
        """Check if the code was rejected."""
        return self.final_decision == VoteDecision.REJECT


def create_session_id() -> str:
    """Generate a new unique session ID."""
    return str(uuid.uuid4())
