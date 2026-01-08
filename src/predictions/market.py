"""Prediction market betting system for agent code quality predictions."""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from src.predictions.models import (
    Prediction,
    Bet,
    Outcome,
    AgentScore,
    PredictionType,
    OutcomeResult,
)
from src.predictions.storage import PredictionStorage


# Default starting tokens for new agents
DEFAULT_STARTING_TOKENS = 1000


@dataclass
class ScoreUpdate:
    """Result of a score update after resolving a prediction.

    Attributes:
        agent_name: Name of the agent
        tokens_before: Token balance before resolution
        tokens_after: Token balance after resolution
        tokens_change: Net change in tokens (positive for wins, negative for losses)
        won: Whether the agent won their bet
    """
    agent_name: str
    tokens_before: int
    tokens_after: int
    tokens_change: int
    won: bool


class PredictionMarket:
    """Manages the prediction market betting system.

    Agents place bets on code quality predictions and earn/lose tokens
    based on whether their predictions are correct.
    """

    def __init__(self, storage: Optional[PredictionStorage] = None):
        """Initialize the prediction market.

        Args:
            storage: Storage backend. Creates new one if not provided.
        """
        self.storage = storage or PredictionStorage()

    def create_prediction(
        self,
        code: str,
        file_path: str,
        prediction_type: PredictionType,
        confidence: float = 0.5
    ) -> Prediction:
        """Create a new prediction about code quality.

        Args:
            code: The code being predicted on
            file_path: Path to the file
            prediction_type: Type of prediction
            confidence: Base confidence level (0.0-1.0)

        Returns:
            The created Prediction
        """
        code_hash = Prediction.compute_code_hash(code)
        prediction = Prediction(
            code_hash=code_hash,
            file_path=file_path,
            prediction_type=prediction_type,
            confidence=confidence
        )
        self.storage.save_prediction(prediction)
        return prediction

    def place_bet(
        self,
        agent: str,
        code: str,
        prediction: Prediction,
        tokens: int
    ) -> Bet:
        """Place a bet on a prediction.

        Args:
            agent: Name of the agent placing the bet
            code: The code being bet on (for verification)
            prediction: The prediction to bet on
            tokens: Number of tokens to wager

        Returns:
            The placed Bet

        Raises:
            ValueError: If agent has insufficient tokens or invalid wager
        """
        # Validate tokens
        if tokens <= 0:
            raise ValueError("Tokens wagered must be positive")

        # Get or create agent score
        score = self.storage.get_agent_score(agent)

        # Check sufficient balance
        if score.tokens < tokens:
            raise ValueError(
                f"Insufficient tokens: {agent} has {score.tokens}, "
                f"tried to wager {tokens}"
            )

        # Determine predicted outcome based on prediction type
        # Predictions about issues expect INCIDENT, CODE_IS_SAFE expects SAFE
        if prediction.prediction_type == PredictionType.CODE_IS_SAFE:
            predicted_outcome = OutcomeResult.SAFE
        else:
            predicted_outcome = OutcomeResult.INCIDENT

        # Create and save the bet
        bet = Bet(
            agent_name=agent,
            prediction_id=prediction.prediction_id,
            tokens_wagered=tokens,
            predicted_outcome=predicted_outcome
        )
        self.storage.save_bet(bet)

        # Deduct tokens from agent balance immediately (escrow)
        score.tokens -= tokens
        score.total_bets += 1
        self.storage.update_agent_score(score)

        return bet

    def resolve(
        self,
        prediction_id: str,
        outcome: OutcomeResult,
        incident_link: Optional[str] = None
    ) -> List[ScoreUpdate]:
        """Resolve a prediction and update agent scores.

        Args:
            prediction_id: ID of the prediction to resolve
            outcome: The actual outcome (INCIDENT or SAFE)
            incident_link: Optional link to incident report

        Returns:
            List of ScoreUpdate objects showing changes to each agent

        Raises:
            ValueError: If prediction not found or already resolved
        """
        # Validate outcome is not UNRESOLVED
        if outcome == OutcomeResult.UNRESOLVED:
            raise ValueError("Cannot resolve with UNRESOLVED outcome")

        # Check prediction exists
        prediction = self.storage.get_prediction(prediction_id)
        if not prediction:
            raise ValueError(f"Prediction not found: {prediction_id}")

        # Check not already resolved
        existing_outcome = self.storage.get_outcome(prediction_id)
        if existing_outcome:
            raise ValueError(f"Prediction already resolved: {prediction_id}")

        # Save the outcome
        outcome_record = Outcome(
            prediction_id=prediction_id,
            actual_result=outcome,
            incident_link=incident_link
        )
        self.storage.save_outcome(outcome_record)

        # Get all bets for this prediction
        bets = self.storage.get_bets_for_prediction(prediction_id)
        score_updates = []

        for bet in bets:
            # Get agent's current score
            score = self.storage.get_agent_score(bet.agent_name)
            tokens_before = score.tokens

            # Calculate winnings/losses
            won = bet.predicted_outcome == outcome

            if won:
                # Winner gets their stake back plus winnings proportional to confidence
                # Winnings = stake * (1 + confidence)
                winnings = int(bet.tokens_wagered * (1 + prediction.confidence))
                score.tokens += winnings
                score.wins += 1
                tokens_change = winnings - bet.tokens_wagered  # Net gain
            else:
                # Loser already had tokens deducted at bet time (escrow)
                # No additional deduction needed
                score.losses += 1
                tokens_change = -bet.tokens_wagered  # Net loss

            # Update score in storage
            self.storage.update_agent_score(score)

            score_updates.append(ScoreUpdate(
                agent_name=bet.agent_name,
                tokens_before=tokens_before,
                tokens_after=score.tokens,
                tokens_change=tokens_change,
                won=won
            ))

        return score_updates

    def get_agent_balance(self, agent: str) -> int:
        """Get an agent's current token balance.

        Args:
            agent: Name of the agent

        Returns:
            Current token balance
        """
        score = self.storage.get_agent_score(agent)
        return score.tokens

    def get_agent_stats(self, agent: str) -> AgentScore:
        """Get full stats for an agent.

        Args:
            agent: Name of the agent

        Returns:
            AgentScore with all statistics
        """
        return self.storage.get_agent_score(agent)

    def get_leaderboard(self, limit: int = 10) -> List[AgentScore]:
        """Get the agent leaderboard ranked by accuracy.

        Args:
            limit: Maximum number of agents to return

        Returns:
            List of AgentScore objects sorted by accuracy
        """
        return self.storage.get_leaderboard(limit)

    def get_open_predictions(self, limit: int = 50) -> List[Prediction]:
        """Get unresolved predictions.

        Args:
            limit: Maximum number of predictions to return

        Returns:
            List of unresolved Prediction objects
        """
        return self.storage.list_predictions(resolved=False, limit=limit)

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """Get a prediction by ID.

        Args:
            prediction_id: The prediction ID

        Returns:
            Prediction or None if not found
        """
        return self.storage.get_prediction(prediction_id)

    def get_bets_for_prediction(self, prediction_id: str) -> List[Bet]:
        """Get all bets placed on a prediction.

        Args:
            prediction_id: The prediction ID

        Returns:
            List of Bet objects
        """
        return self.storage.get_bets_for_prediction(prediction_id)

    def get_voting_weight(self, agent: str) -> float:
        """Calculate voting weight based on historical accuracy.

        Agents with higher accuracy get more weight in voting.
        Base weight is 1.0, modified by accuracy.

        Args:
            agent: Name of the agent

        Returns:
            Voting weight multiplier (0.5-2.0)
        """
        score = self.storage.get_agent_score(agent)

        # New agents get base weight
        if score.total_bets < 5:
            return 1.0

        # Weight is 0.5 + accuracy (ranges 0.5 to 1.5)
        # Plus bonus for high token count
        accuracy_weight = 0.5 + score.accuracy

        # Token bonus: up to 0.5 extra for agents with 2x starting tokens
        token_ratio = min(score.tokens / DEFAULT_STARTING_TOKENS, 2.0)
        token_bonus = (token_ratio - 1.0) * 0.5 if token_ratio > 1.0 else 0

        return min(accuracy_weight + token_bonus, 2.0)
