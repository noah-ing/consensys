"""Data models for the prediction market system."""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid
import hashlib


class PredictionType(Enum):
    """Types of predictions agents can make about code."""
    BUG_WILL_OCCUR = "BUG_WILL_OCCUR"
    SECURITY_INCIDENT = "SECURITY_INCIDENT"
    PERFORMANCE_ISSUE = "PERFORMANCE_ISSUE"
    MAINTENANCE_PROBLEM = "MAINTENANCE_PROBLEM"
    CODE_IS_SAFE = "CODE_IS_SAFE"


class OutcomeResult(Enum):
    """Possible outcomes for a prediction."""
    INCIDENT = "INCIDENT"  # The predicted issue occurred
    SAFE = "SAFE"  # No issue occurred
    UNRESOLVED = "UNRESOLVED"  # Not yet determined


@dataclass
class Prediction:
    """A prediction about code quality or potential issues.

    Attributes:
        prediction_id: Unique identifier for this prediction
        code_hash: SHA256 hash of the code being predicted on
        file_path: Path to the file being predicted on
        prediction_type: Type of prediction being made
        confidence: Agent's confidence in prediction (0.0-1.0)
        timestamp: When the prediction was created
    """
    code_hash: str
    file_path: str
    prediction_type: PredictionType
    confidence: float = 0.5
    prediction_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.prediction_id is None:
            self.prediction_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @staticmethod
    def compute_code_hash(code: str) -> str:
        """Compute SHA256 hash of code for identification."""
        return hashlib.sha256(code.encode()).hexdigest()


@dataclass
class Bet:
    """A bet placed by an agent on a prediction.

    Attributes:
        bet_id: Unique identifier for this bet
        agent_name: Name of the agent placing the bet
        prediction_id: ID of the prediction being bet on
        tokens_wagered: Number of tokens wagered
        predicted_outcome: What the agent predicts will happen
        timestamp: When the bet was placed
    """
    agent_name: str
    prediction_id: str
    tokens_wagered: int
    predicted_outcome: OutcomeResult
    bet_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.bet_id is None:
            self.bet_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class Outcome:
    """The resolved outcome of a prediction.

    Attributes:
        outcome_id: Unique identifier for this outcome
        prediction_id: ID of the prediction being resolved
        actual_result: What actually happened
        resolved_at: When the outcome was determined
        incident_link: Optional link to incident report/bug tracker
    """
    prediction_id: str
    actual_result: OutcomeResult
    outcome_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    incident_link: Optional[str] = None

    def __post_init__(self):
        if self.outcome_id is None:
            self.outcome_id = str(uuid.uuid4())
        if self.resolved_at is None:
            self.resolved_at = datetime.now()


@dataclass
class AgentScore:
    """Tracks an agent's prediction market performance.

    Attributes:
        agent_name: Name of the agent
        tokens: Current token balance
        total_bets: Total number of bets placed
        wins: Number of winning bets
        losses: Number of losing bets
        accuracy: Win rate (wins / total_bets)
        last_updated: When the score was last updated
    """
    agent_name: str
    tokens: int = 1000  # Starting balance
    total_bets: int = 0
    wins: int = 0
    losses: int = 0
    last_updated: Optional[datetime] = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()

    @property
    def accuracy(self) -> float:
        """Calculate win rate."""
        if self.total_bets == 0:
            return 0.0
        return self.wins / self.total_bets
