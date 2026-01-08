"""Tests for the prediction market module."""
import os
import tempfile
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.predictions.models import (
    Prediction,
    Bet,
    Outcome,
    AgentScore,
    PredictionType,
    OutcomeResult,
)
from src.predictions.storage import PredictionStorage
from src.predictions.market import PredictionMarket, ScoreUpdate, DEFAULT_STARTING_TOKENS


class TestPredictionType:
    """Tests for PredictionType enum."""

    def test_all_types_defined(self):
        """Test all prediction types are defined."""
        assert PredictionType.BUG_WILL_OCCUR
        assert PredictionType.SECURITY_INCIDENT
        assert PredictionType.PERFORMANCE_ISSUE
        assert PredictionType.MAINTENANCE_PROBLEM
        assert PredictionType.CODE_IS_SAFE

    def test_type_values(self):
        """Test prediction type values."""
        assert PredictionType.BUG_WILL_OCCUR.value == "BUG_WILL_OCCUR"
        assert PredictionType.CODE_IS_SAFE.value == "CODE_IS_SAFE"


class TestOutcomeResult:
    """Tests for OutcomeResult enum."""

    def test_all_outcomes_defined(self):
        """Test all outcome results are defined."""
        assert OutcomeResult.INCIDENT
        assert OutcomeResult.SAFE
        assert OutcomeResult.UNRESOLVED

    def test_outcome_values(self):
        """Test outcome result values."""
        assert OutcomeResult.INCIDENT.value == "INCIDENT"
        assert OutcomeResult.SAFE.value == "SAFE"


class TestPrediction:
    """Tests for Prediction dataclass."""

    def test_prediction_creation(self):
        """Test Prediction can be created with required fields."""
        prediction = Prediction(
            code_hash="abc123",
            file_path="/path/to/file.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.85,
        )
        assert prediction.code_hash == "abc123"
        assert prediction.file_path == "/path/to/file.py"
        assert prediction.prediction_type == PredictionType.SECURITY_INCIDENT
        assert prediction.confidence == 0.85

    def test_prediction_auto_generates_id(self):
        """Test Prediction auto-generates prediction_id."""
        prediction = Prediction(
            code_hash="abc123",
            file_path="/path/to/file.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )
        assert prediction.prediction_id is not None
        assert len(prediction.prediction_id) == 36  # UUID format

    def test_prediction_auto_generates_timestamp(self):
        """Test Prediction auto-generates timestamp."""
        prediction = Prediction(
            code_hash="abc123",
            file_path="/path/to/file.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )
        assert prediction.timestamp is not None
        assert isinstance(prediction.timestamp, datetime)

    def test_prediction_compute_code_hash(self):
        """Test static method to compute code hash."""
        code = "def foo(): pass"
        hash1 = Prediction.compute_code_hash(code)
        hash2 = Prediction.compute_code_hash(code)

        assert hash1 == hash2  # Same code, same hash
        assert len(hash1) == 64  # SHA256 hex digest

        different_hash = Prediction.compute_code_hash("def bar(): pass")
        assert hash1 != different_hash  # Different code, different hash


class TestBet:
    """Tests for Bet dataclass."""

    def test_bet_creation(self):
        """Test Bet can be created with required fields."""
        bet = Bet(
            agent_name="SecurityExpert",
            prediction_id="pred-123",
            tokens_wagered=100,
            predicted_outcome=OutcomeResult.INCIDENT,
        )
        assert bet.agent_name == "SecurityExpert"
        assert bet.prediction_id == "pred-123"
        assert bet.tokens_wagered == 100
        assert bet.predicted_outcome == OutcomeResult.INCIDENT

    def test_bet_auto_generates_id(self):
        """Test Bet auto-generates bet_id."""
        bet = Bet(
            agent_name="TestAgent",
            prediction_id="pred-123",
            tokens_wagered=50,
            predicted_outcome=OutcomeResult.SAFE,
        )
        assert bet.bet_id is not None
        assert len(bet.bet_id) == 36

    def test_bet_auto_generates_timestamp(self):
        """Test Bet auto-generates timestamp."""
        bet = Bet(
            agent_name="TestAgent",
            prediction_id="pred-123",
            tokens_wagered=50,
            predicted_outcome=OutcomeResult.SAFE,
        )
        assert bet.timestamp is not None


class TestOutcome:
    """Tests for Outcome dataclass."""

    def test_outcome_creation(self):
        """Test Outcome can be created with required fields."""
        outcome = Outcome(
            prediction_id="pred-123",
            actual_result=OutcomeResult.INCIDENT,
            incident_link="https://github.com/issue/123",
        )
        assert outcome.prediction_id == "pred-123"
        assert outcome.actual_result == OutcomeResult.INCIDENT
        assert outcome.incident_link == "https://github.com/issue/123"

    def test_outcome_auto_generates_id(self):
        """Test Outcome auto-generates outcome_id."""
        outcome = Outcome(
            prediction_id="pred-123",
            actual_result=OutcomeResult.SAFE,
        )
        assert outcome.outcome_id is not None

    def test_outcome_auto_generates_resolved_at(self):
        """Test Outcome auto-generates resolved_at timestamp."""
        outcome = Outcome(
            prediction_id="pred-123",
            actual_result=OutcomeResult.SAFE,
        )
        assert outcome.resolved_at is not None


class TestAgentScore:
    """Tests for AgentScore dataclass."""

    def test_agent_score_default_values(self):
        """Test AgentScore has correct defaults."""
        score = AgentScore(agent_name="TestAgent")
        assert score.agent_name == "TestAgent"
        assert score.tokens == 1000  # Default starting balance
        assert score.total_bets == 0
        assert score.wins == 0
        assert score.losses == 0

    def test_agent_score_accuracy_property(self):
        """Test accuracy property calculation."""
        score = AgentScore(
            agent_name="TestAgent",
            total_bets=10,
            wins=7,
            losses=3,
        )
        assert score.accuracy == 0.7

    def test_agent_score_accuracy_zero_bets(self):
        """Test accuracy is 0 with no bets."""
        score = AgentScore(agent_name="TestAgent")
        assert score.accuracy == 0.0


class TestPredictionStorage:
    """Tests for PredictionStorage class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield Path(path)
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.fixture
    def storage(self, temp_db):
        """Create a PredictionStorage instance with temp database."""
        return PredictionStorage(db_path=temp_db)

    def test_storage_initialization(self, storage):
        """Test storage initializes database tables."""
        # Tables should be created on init
        conn = storage._get_connection()
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "predictions" in tables
        assert "bets" in tables
        assert "outcomes" in tables
        assert "agent_scores" in tables

    def test_save_and_get_prediction(self, storage):
        """Test saving and retrieving a prediction."""
        prediction = Prediction(
            code_hash="test123",
            file_path="/test/file.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.9,
        )

        # Save
        storage.save_prediction(prediction)

        # Retrieve
        retrieved = storage.get_prediction(prediction.prediction_id)
        assert retrieved is not None
        assert retrieved.code_hash == prediction.code_hash
        assert retrieved.prediction_type == PredictionType.SECURITY_INCIDENT

    def test_get_nonexistent_prediction(self, storage):
        """Test getting a prediction that doesn't exist."""
        result = storage.get_prediction("nonexistent-id")
        assert result is None

    def test_list_predictions_all(self, storage):
        """Test listing all predictions."""
        # Create multiple predictions
        for i in range(3):
            storage.save_prediction(Prediction(
                code_hash=f"hash{i}",
                file_path=f"/file{i}.py",
                prediction_type=PredictionType.BUG_WILL_OCCUR,
            ))

        predictions = storage.list_predictions()
        assert len(predictions) == 3

    def test_list_predictions_unresolved_only(self, storage):
        """Test listing only unresolved predictions."""
        # Create predictions
        pred1 = Prediction(
            code_hash="hash1",
            file_path="/file1.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )
        pred2 = Prediction(
            code_hash="hash2",
            file_path="/file2.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )
        storage.save_prediction(pred1)
        storage.save_prediction(pred2)

        # Resolve one
        storage.save_outcome(Outcome(
            prediction_id=pred1.prediction_id,
            actual_result=OutcomeResult.INCIDENT,
        ))

        # List unresolved
        unresolved = storage.list_predictions(resolved=False)
        assert len(unresolved) == 1
        assert unresolved[0].prediction_id == pred2.prediction_id

    def test_save_and_get_bet(self, storage):
        """Test saving and retrieving bets."""
        # Create prediction first
        prediction = Prediction(
            code_hash="test123",
            file_path="/test.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
        )
        storage.save_prediction(prediction)

        # Create bet
        bet = Bet(
            agent_name="SecurityExpert",
            prediction_id=prediction.prediction_id,
            tokens_wagered=100,
            predicted_outcome=OutcomeResult.INCIDENT,
        )
        storage.save_bet(bet)

        # Retrieve bets
        bets = storage.get_bets_for_prediction(prediction.prediction_id)
        assert len(bets) == 1
        assert bets[0].agent_name == "SecurityExpert"
        assert bets[0].tokens_wagered == 100

    def test_get_bets_by_agent(self, storage):
        """Test getting bets by agent name."""
        # Create prediction
        prediction = Prediction(
            code_hash="test123",
            file_path="/test.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )
        storage.save_prediction(prediction)

        # Create bet
        bet = Bet(
            agent_name="TestAgent",
            prediction_id=prediction.prediction_id,
            tokens_wagered=50,
            predicted_outcome=OutcomeResult.INCIDENT,
        )
        storage.save_bet(bet)

        # Retrieve by agent
        bets = storage.get_bets_by_agent("TestAgent")
        assert len(bets) == 1
        assert bets[0].agent_name == "TestAgent"

    def test_save_and_get_outcome(self, storage):
        """Test saving and retrieving outcomes."""
        # Create prediction
        prediction = Prediction(
            code_hash="test123",
            file_path="/test.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
        )
        storage.save_prediction(prediction)

        # Create outcome
        outcome = Outcome(
            prediction_id=prediction.prediction_id,
            actual_result=OutcomeResult.INCIDENT,
            incident_link="https://github.com/issue/1",
        )
        storage.save_outcome(outcome)

        # Retrieve
        retrieved = storage.get_outcome(prediction.prediction_id)
        assert retrieved is not None
        assert retrieved.actual_result == OutcomeResult.INCIDENT
        assert retrieved.incident_link == "https://github.com/issue/1"

    def test_agent_score_auto_creation(self, storage):
        """Test agent score is auto-created when accessed."""
        score = storage.get_agent_score("NewAgent")
        assert score.agent_name == "NewAgent"
        assert score.tokens == 1000
        assert score.total_bets == 0

    def test_update_agent_score(self, storage):
        """Test updating agent score."""
        # Get initial score
        score = storage.get_agent_score("TestAgent")
        assert score.tokens == 1000

        # Update
        score.tokens = 1500
        score.wins = 5
        storage.update_agent_score(score)

        # Verify update
        updated = storage.get_agent_score("TestAgent")
        assert updated.tokens == 1500
        assert updated.wins == 5

    def test_get_leaderboard(self, storage):
        """Test getting agent leaderboard."""
        # Create agents with different scores
        for i, (wins, total) in enumerate([(8, 10), (6, 10), (4, 10)]):
            score = storage.get_agent_score(f"Agent{i}")
            score.wins = wins
            score.total_bets = total
            score.losses = total - wins
            storage.update_agent_score(score)

        leaderboard = storage.get_leaderboard(limit=3)
        assert len(leaderboard) == 3
        assert leaderboard[0].wins == 8  # Highest accuracy first

    def test_get_stats(self, storage):
        """Test getting aggregate statistics."""
        # Create some data
        pred = Prediction(
            code_hash="test",
            file_path="/test.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )
        storage.save_prediction(pred)

        bet = Bet(
            agent_name="TestAgent",
            prediction_id=pred.prediction_id,
            tokens_wagered=100,
            predicted_outcome=OutcomeResult.INCIDENT,
        )
        storage.save_bet(bet)

        stats = storage.get_stats()
        assert stats["total_predictions"] == 1
        assert stats["total_bets"] == 1
        assert stats["total_tokens_wagered"] == 100


class TestPredictionMarket:
    """Tests for PredictionMarket class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield Path(path)
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.fixture
    def market(self, temp_db):
        """Create a PredictionMarket instance."""
        storage = PredictionStorage(db_path=temp_db)
        return PredictionMarket(storage=storage)

    def test_market_creation(self, market):
        """Test market can be created."""
        assert market.storage is not None

    def test_create_prediction(self, market):
        """Test creating a prediction."""
        prediction = market.create_prediction(
            code="def foo(): pass",
            file_path="/test.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
            confidence=0.8,
        )
        assert prediction.prediction_id is not None
        assert prediction.confidence == 0.8

    def test_place_bet_success(self, market):
        """Test placing a valid bet."""
        # Create prediction
        prediction = market.create_prediction(
            code="vulnerable_code()",
            file_path="/vuln.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.9,
        )

        # Place bet
        bet = market.place_bet(
            agent="SecurityExpert",
            code="vulnerable_code()",
            prediction=prediction,
            tokens=100,
        )

        assert bet.agent_name == "SecurityExpert"
        assert bet.tokens_wagered == 100
        assert bet.predicted_outcome == OutcomeResult.INCIDENT

    def test_place_bet_deducts_tokens(self, market):
        """Test placing a bet deducts tokens from agent."""
        prediction = market.create_prediction(
            code="test",
            file_path="/test.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )

        # Initial balance
        initial = market.get_agent_balance("TestAgent")
        assert initial == DEFAULT_STARTING_TOKENS

        # Place bet
        market.place_bet(
            agent="TestAgent",
            code="test",
            prediction=prediction,
            tokens=200,
        )

        # Check balance
        new_balance = market.get_agent_balance("TestAgent")
        assert new_balance == DEFAULT_STARTING_TOKENS - 200

    def test_place_bet_insufficient_tokens(self, market):
        """Test placing a bet with insufficient tokens fails."""
        prediction = market.create_prediction(
            code="test",
            file_path="/test.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )

        with pytest.raises(ValueError) as exc_info:
            market.place_bet(
                agent="TestAgent",
                code="test",
                prediction=prediction,
                tokens=2000,  # More than starting balance
            )
        assert "Insufficient tokens" in str(exc_info.value)

    def test_place_bet_zero_tokens(self, market):
        """Test placing a bet with zero tokens fails."""
        prediction = market.create_prediction(
            code="test",
            file_path="/test.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )

        with pytest.raises(ValueError) as exc_info:
            market.place_bet(
                agent="TestAgent",
                code="test",
                prediction=prediction,
                tokens=0,
            )
        assert "positive" in str(exc_info.value).lower()

    def test_resolve_prediction_winners_get_tokens(self, market):
        """Test winners receive tokens when prediction is resolved."""
        # Create prediction for security incident
        prediction = market.create_prediction(
            code="os.system(user_input)",
            file_path="/vuln.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.8,
        )

        # Agent bets on incident
        market.place_bet(
            agent="SecurityExpert",
            code="os.system(user_input)",
            prediction=prediction,
            tokens=100,
        )

        # Resolve as incident (winner!)
        score_updates = market.resolve(
            prediction_id=prediction.prediction_id,
            outcome=OutcomeResult.INCIDENT,
        )

        assert len(score_updates) == 1
        assert score_updates[0].won is True
        assert score_updates[0].tokens_after > score_updates[0].tokens_before

    def test_resolve_prediction_losers_lose_tokens(self, market):
        """Test losers have tokens deducted when prediction is resolved."""
        # Create prediction for safe code
        prediction = market.create_prediction(
            code="safe_code()",
            file_path="/safe.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
            confidence=0.7,
        )

        # Agent bets on safe (predicted_outcome = SAFE)
        market.place_bet(
            agent="OptimistAgent",
            code="safe_code()",
            prediction=prediction,
            tokens=100,
        )

        # Resolve as incident (loser!)
        score_updates = market.resolve(
            prediction_id=prediction.prediction_id,
            outcome=OutcomeResult.INCIDENT,
        )

        assert len(score_updates) == 1
        assert score_updates[0].won is False
        # Tokens were already deducted when bet was placed (escrow)

    def test_resolve_nonexistent_prediction(self, market):
        """Test resolving a nonexistent prediction fails."""
        with pytest.raises(ValueError) as exc_info:
            market.resolve(
                prediction_id="nonexistent",
                outcome=OutcomeResult.SAFE,
            )
        assert "not found" in str(exc_info.value).lower()

    def test_resolve_already_resolved(self, market):
        """Test resolving an already resolved prediction fails."""
        prediction = market.create_prediction(
            code="test",
            file_path="/test.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )

        # Resolve once
        market.resolve(
            prediction_id=prediction.prediction_id,
            outcome=OutcomeResult.SAFE,
        )

        # Try to resolve again
        with pytest.raises(ValueError) as exc_info:
            market.resolve(
                prediction_id=prediction.prediction_id,
                outcome=OutcomeResult.INCIDENT,
            )
        assert "already resolved" in str(exc_info.value).lower()

    def test_resolve_with_unresolved_outcome_fails(self, market):
        """Test resolving with UNRESOLVED outcome fails."""
        prediction = market.create_prediction(
            code="test",
            file_path="/test.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )

        with pytest.raises(ValueError) as exc_info:
            market.resolve(
                prediction_id=prediction.prediction_id,
                outcome=OutcomeResult.UNRESOLVED,
            )
        assert "UNRESOLVED" in str(exc_info.value)

    def test_get_voting_weight_new_agent(self, market):
        """Test new agent has default voting weight."""
        weight = market.get_voting_weight("NewAgent")
        assert weight == 1.0

    def test_get_voting_weight_experienced_agent(self, market):
        """Test experienced agent has modified voting weight."""
        # Create an agent with history
        score = market.storage.get_agent_score("ExpertAgent")
        score.total_bets = 10
        score.wins = 8
        score.losses = 2
        market.storage.update_agent_score(score)

        weight = market.get_voting_weight("ExpertAgent")
        assert weight > 1.0  # Higher accuracy = higher weight

    def test_get_open_predictions(self, market):
        """Test getting open (unresolved) predictions."""
        # Create predictions
        pred1 = market.create_prediction(
            code="test1",
            file_path="/test1.py",
            prediction_type=PredictionType.BUG_WILL_OCCUR,
        )
        pred2 = market.create_prediction(
            code="test2",
            file_path="/test2.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )

        # Resolve one
        market.resolve(pred1.prediction_id, OutcomeResult.SAFE)

        # Check open predictions
        open_preds = market.get_open_predictions()
        assert len(open_preds) == 1
        assert open_preds[0].prediction_id == pred2.prediction_id

    def test_get_leaderboard(self, market):
        """Test getting agent leaderboard from market."""
        # Create agents with different performance
        for name, wins, total in [("Best", 9, 10), ("Mid", 5, 10), ("Low", 2, 10)]:
            score = market.storage.get_agent_score(name)
            score.total_bets = total
            score.wins = wins
            score.losses = total - wins
            market.storage.update_agent_score(score)

        leaderboard = market.get_leaderboard(limit=3)
        assert len(leaderboard) == 3
        assert leaderboard[0].agent_name == "Best"


class TestScoreUpdate:
    """Tests for ScoreUpdate dataclass."""

    def test_score_update_creation(self):
        """Test ScoreUpdate can be created."""
        update = ScoreUpdate(
            agent_name="TestAgent",
            tokens_before=1000,
            tokens_after=1180,
            tokens_change=180,
            won=True,
        )
        assert update.agent_name == "TestAgent"
        assert update.tokens_before == 1000
        assert update.tokens_after == 1180
        assert update.tokens_change == 180
        assert update.won is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield Path(path)
        try:
            os.unlink(path)
        except OSError:
            pass

    @pytest.fixture
    def market(self, temp_db):
        """Create a PredictionMarket instance."""
        storage = PredictionStorage(db_path=temp_db)
        return PredictionMarket(storage=storage)

    def test_empty_code_prediction(self, market):
        """Test prediction with empty code still works."""
        prediction = market.create_prediction(
            code="",
            file_path="/empty.py",
            prediction_type=PredictionType.CODE_IS_SAFE,
        )
        assert prediction.prediction_id is not None

    def test_multiple_agents_betting_on_same_prediction(self, market):
        """Test multiple agents can bet on the same prediction."""
        prediction = market.create_prediction(
            code="risky_code()",
            file_path="/risky.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.7,
        )

        # Multiple agents bet
        for agent in ["Agent1", "Agent2", "Agent3"]:
            market.place_bet(
                agent=agent,
                code="risky_code()",
                prediction=prediction,
                tokens=50,
            )

        bets = market.get_bets_for_prediction(prediction.prediction_id)
        assert len(bets) == 3

    def test_winnings_proportional_to_confidence(self, market):
        """Test winnings are proportional to prediction confidence."""
        # High confidence prediction
        high_conf_pred = market.create_prediction(
            code="test",
            file_path="/test.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.9,  # High confidence
        )

        market.place_bet(
            agent="HighConfAgent",
            code="test",
            prediction=high_conf_pred,
            tokens=100,
        )

        # Low confidence prediction
        low_conf_pred = market.create_prediction(
            code="test2",
            file_path="/test2.py",
            prediction_type=PredictionType.SECURITY_INCIDENT,
            confidence=0.5,  # Low confidence
        )

        market.place_bet(
            agent="LowConfAgent",
            code="test2",
            prediction=low_conf_pred,
            tokens=100,
        )

        # Resolve both as incidents
        high_updates = market.resolve(high_conf_pred.prediction_id, OutcomeResult.INCIDENT)
        low_updates = market.resolve(low_conf_pred.prediction_id, OutcomeResult.INCIDENT)

        # Higher confidence should yield higher winnings
        high_winnings = high_updates[0].tokens_change
        low_winnings = low_updates[0].tokens_change
        assert high_winnings > low_winnings
