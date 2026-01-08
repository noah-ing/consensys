"""Tests for DebateOrchestrator - multi-agent debate coordination."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from io import StringIO

import pytest

from src.orchestrator.debate import DebateOrchestrator
from src.agents.personas import PERSONAS, SecurityExpert, PragmaticDev
from src.agents.agent import Agent, ReviewResult, ResponseResult, VoteResult
from src.models.review import Review, Response, Vote, Consensus, VoteDecision
from src.db.storage import Storage
from rich.console import Console


@pytest.fixture
def quiet_console():
    """Create a quiet console that doesn't output to terminal."""
    return Console(file=StringIO(), quiet=True)


@pytest.fixture
def mock_agent_review():
    """Create a mock review result."""
    return ReviewResult(
        agent_name="SecurityExpert",
        issues=[{"description": "Test issue", "severity": "MEDIUM", "line": 1}],
        suggestions=["Add validation"],
        severity="MEDIUM",
        confidence=0.85,
        summary="Test summary",
    )


@pytest.fixture
def mock_agent_response():
    """Create a mock response result."""
    return ResponseResult(
        agent_name="PragmaticDev",
        responding_to="SecurityExpert",
        agreement_level="AGREE",
        points=["Valid concern"],
        summary="I agree",
    )


@pytest.fixture
def mock_agent_vote():
    """Create a mock vote result."""
    return VoteResult(
        agent_name="SecurityExpert",
        decision=VoteDecision.APPROVE,
        reasoning="Code looks good overall",
    )


class TestDebateOrchestratorInit:
    """Tests for DebateOrchestrator initialization."""

    def test_init_default_personas(self, storage, quiet_console):
        """Should use default PERSONAS if none provided."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert len(orchestrator.personas) == 4
        assert len(orchestrator.agents) == 4

    def test_init_custom_personas(self, storage, quiet_console):
        """Should accept custom personas list."""
        custom_personas = [SecurityExpert, PragmaticDev]
        orchestrator = DebateOrchestrator(
            personas=custom_personas,
            storage=storage,
            console=quiet_console,
        )
        assert len(orchestrator.personas) == 2
        assert len(orchestrator.agents) == 2

    def test_init_creates_agents(self, storage, quiet_console):
        """Should create Agent instances for each persona."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        for agent in orchestrator.agents:
            assert isinstance(agent, Agent)

    def test_init_session_state(self, storage, quiet_console):
        """Should initialize session state to empty."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert orchestrator.session_id is None
        assert orchestrator.code is None
        assert orchestrator.context is None
        assert orchestrator.reviews == []
        assert orchestrator.responses == []
        assert orchestrator.votes == []
        assert orchestrator.consensus is None

    def test_init_cache_settings(self, storage, quiet_console):
        """Should respect cache settings."""
        orchestrator = DebateOrchestrator(
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )
        assert orchestrator.use_cache is False
        assert orchestrator._cache is None


class TestDebateOrchestratorGetters:
    """Tests for getter methods."""

    def test_get_session_id_none(self, storage, quiet_console):
        """get_session_id should return None before review."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert orchestrator.get_session_id() is None

    def test_get_reviews_empty(self, storage, quiet_console):
        """get_reviews should return empty list before review."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert orchestrator.get_reviews() == []

    def test_get_responses_empty(self, storage, quiet_console):
        """get_responses should return empty list before responses."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert orchestrator.get_responses() == []

    def test_get_votes_empty(self, storage, quiet_console):
        """get_votes should return empty list before voting."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert orchestrator.get_votes() == []

    def test_get_consensus_none(self, storage, quiet_console):
        """get_consensus should return None before consensus."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        assert orchestrator.get_consensus() is None


class TestDebateOrchestratorReview:
    """Tests for the review flow."""

    @patch.object(Agent, 'review')
    def test_start_review_creates_session(self, mock_review, storage, quiet_console, mock_agent_review):
        """start_review should create a new session."""
        mock_review.return_value = mock_agent_review

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )
        orchestrator.start_review("x = 1")

        assert orchestrator.session_id is not None
        assert orchestrator.code == "x = 1"

    @patch.object(Agent, 'review')
    def test_start_review_stores_reviews(self, mock_review, storage, quiet_console, mock_agent_review):
        """start_review should store reviews in database."""
        mock_review.return_value = mock_agent_review

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )
        reviews = orchestrator.start_review("x = 1")

        assert len(reviews) == 1
        assert len(orchestrator.reviews) == 1

        # Verify stored in database
        stored = storage.get_reviews(orchestrator.session_id)
        assert len(stored) == 1

    @patch.object(Agent, 'review')
    def test_start_review_with_context(self, mock_review, storage, quiet_console, mock_agent_review):
        """start_review should accept context."""
        mock_review.return_value = mock_agent_review

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )
        orchestrator.start_review("x = 1", context="Test context")

        assert orchestrator.context == "Test context"


class TestDebateOrchestratorResponses:
    """Tests for the response round."""

    def test_run_responses_requires_reviews(self, storage, quiet_console):
        """run_responses should raise if no reviews exist."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)

        with pytest.raises(ValueError, match="No reviews"):
            orchestrator.run_responses()

    @patch.object(Agent, 'review')
    @patch.object(Agent, 'respond_to')
    def test_run_responses_stores_responses(
        self,
        mock_respond,
        mock_review,
        storage,
        quiet_console,
        mock_agent_review,
        mock_agent_response,
    ):
        """run_responses should store responses in database."""
        mock_review.return_value = mock_agent_review
        mock_respond.return_value = mock_agent_response

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert, PragmaticDev],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        orchestrator.start_review("x = 1")
        responses = orchestrator.run_responses()

        # Each agent responds to each other agent (2 agents = 2 responses each direction)
        assert len(responses) >= 1
        assert len(orchestrator.responses) >= 1


class TestDebateOrchestratorVoting:
    """Tests for the voting round."""

    def test_run_voting_requires_reviews(self, storage, quiet_console):
        """run_voting should raise if no reviews exist."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)

        with pytest.raises(ValueError, match="No reviews"):
            orchestrator.run_voting()

    @patch.object(Agent, 'review')
    @patch.object(Agent, 'vote')
    def test_run_voting_stores_votes(
        self,
        mock_vote,
        mock_review,
        storage,
        quiet_console,
        mock_agent_review,
        mock_agent_vote,
    ):
        """run_voting should store votes in database."""
        mock_review.return_value = mock_agent_review
        mock_vote.return_value = mock_agent_vote

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        orchestrator.start_review("x = 1")
        votes = orchestrator.run_voting()

        assert len(votes) == 1
        assert len(orchestrator.votes) == 1

        # Verify stored in database
        stored = storage.get_votes(orchestrator.session_id)
        assert len(stored) == 1


class TestDebateOrchestratorConsensus:
    """Tests for consensus building."""

    def test_build_consensus_requires_votes(self, storage, quiet_console):
        """build_consensus should raise if no votes exist."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)

        with pytest.raises(ValueError, match="No votes"):
            orchestrator.build_consensus()

    @patch.object(Agent, 'review')
    @patch.object(Agent, 'vote')
    def test_build_consensus_approve_majority(
        self,
        mock_vote,
        mock_review,
        storage,
        quiet_console,
        mock_agent_review,
    ):
        """build_consensus should APPROVE with majority approve votes."""
        mock_review.return_value = mock_agent_review
        mock_vote.return_value = VoteResult(
            agent_name="Test",
            decision=VoteDecision.APPROVE,
            reasoning="Looks good",
        )

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert, PragmaticDev],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        orchestrator.start_review("x = 1")
        orchestrator.run_voting()
        consensus = orchestrator.build_consensus()

        assert consensus.final_decision == VoteDecision.APPROVE
        assert consensus.vote_counts["APPROVE"] == 2

    @patch.object(Agent, 'review')
    @patch.object(Agent, 'vote')
    def test_build_consensus_reject_majority(
        self,
        mock_vote,
        mock_review,
        storage,
        quiet_console,
        mock_agent_review,
    ):
        """build_consensus should REJECT with majority reject votes."""
        mock_review.return_value = mock_agent_review
        mock_vote.return_value = VoteResult(
            agent_name="Test",
            decision=VoteDecision.REJECT,
            reasoning="Issues found",
        )

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        orchestrator.start_review("x = 1")
        orchestrator.run_voting()
        consensus = orchestrator.build_consensus()

        assert consensus.final_decision == VoteDecision.REJECT

    @patch.object(Agent, 'review')
    @patch.object(Agent, 'vote')
    def test_build_consensus_tie_rejects(
        self,
        mock_vote,
        mock_review,
        storage,
        quiet_console,
        mock_agent_review,
    ):
        """build_consensus should REJECT on tie (conservative)."""
        mock_review.return_value = mock_agent_review

        # Return alternating votes to create a tie
        mock_vote.side_effect = [
            VoteResult("Agent1", VoteDecision.APPROVE, "Good"),
            VoteResult("Agent2", VoteDecision.REJECT, "Bad"),
        ]

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert, PragmaticDev],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        orchestrator.start_review("x = 1")
        orchestrator.run_voting()
        consensus = orchestrator.build_consensus()

        # Tie-breaker: REJECT wins
        assert consensus.final_decision == VoteDecision.REJECT


class TestDebateOrchestratorQuickReview:
    """Tests for quick review mode."""

    @patch.object(Agent, 'review')
    def test_quick_review_skips_voting(self, mock_review, storage, quiet_console):
        """run_quick_review should skip voting round."""
        mock_review.return_value = ReviewResult(
            agent_name="Test",
            issues=[],
            suggestions=[],
            severity="LOW",
            confidence=0.9,
            summary="OK",
        )

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        consensus = orchestrator.run_quick_review("x = 1")

        # Quick review should produce consensus
        assert consensus is not None
        assert orchestrator.votes == []  # No voting round

    @patch.object(Agent, 'review')
    def test_quick_review_approve_for_low_severity(self, mock_review, storage, quiet_console):
        """quick_review should APPROVE for LOW severity."""
        mock_review.return_value = ReviewResult(
            agent_name="Test",
            issues=[],
            suggestions=[],
            severity="LOW",
            confidence=0.9,
            summary="OK",
        )

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        consensus = orchestrator.run_quick_review("x = 1")
        assert consensus.final_decision == VoteDecision.APPROVE

    @patch.object(Agent, 'review')
    def test_quick_review_abstain_for_high_severity(self, mock_review, storage, quiet_console):
        """quick_review should ABSTAIN for HIGH severity."""
        mock_review.return_value = ReviewResult(
            agent_name="Test",
            issues=[{"description": "Issue", "severity": "HIGH"}],
            suggestions=[],
            severity="HIGH",
            confidence=0.9,
            summary="Issues found",
        )

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        consensus = orchestrator.run_quick_review("x = 1")
        assert consensus.final_decision == VoteDecision.ABSTAIN

    @patch.object(Agent, 'review')
    def test_quick_review_reject_for_critical_severity(self, mock_review, storage, quiet_console):
        """quick_review should REJECT for CRITICAL severity."""
        mock_review.return_value = ReviewResult(
            agent_name="Test",
            issues=[{"description": "Critical bug", "severity": "CRITICAL"}],
            suggestions=[],
            severity="CRITICAL",
            confidence=0.95,
            summary="Critical issues",
        )

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        consensus = orchestrator.run_quick_review("x = 1")
        assert consensus.final_decision == VoteDecision.REJECT


class TestDebateOrchestratorFullDebate:
    """Tests for full debate flow."""

    @patch.object(Agent, 'review')
    @patch.object(Agent, 'respond_to')
    @patch.object(Agent, 'vote')
    def test_run_full_debate(
        self,
        mock_vote,
        mock_respond,
        mock_review,
        storage,
        quiet_console,
        mock_agent_review,
        mock_agent_response,
        mock_agent_vote,
    ):
        """run_full_debate should complete all rounds."""
        mock_review.return_value = mock_agent_review
        mock_respond.return_value = mock_agent_response
        mock_vote.return_value = mock_agent_vote

        orchestrator = DebateOrchestrator(
            personas=[SecurityExpert],
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        consensus = orchestrator.run_full_debate("x = 1")

        assert consensus is not None
        assert len(orchestrator.reviews) == 1
        assert len(orchestrator.votes) == 1


class TestDebateOrchestratorDisplay:
    """Tests for display methods."""

    def test_display_review(self, storage, quiet_console, sample_review):
        """_display_review should not raise for valid review."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        # Should not raise
        orchestrator._display_review(sample_review)

    def test_display_response(self, storage, quiet_console, sample_response):
        """_display_response should not raise for valid response."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        # Should not raise
        orchestrator._display_response(sample_response)

    def test_display_vote(self, storage, quiet_console, sample_vote):
        """_display_vote should not raise for valid vote."""
        orchestrator = DebateOrchestrator(storage=storage, console=quiet_console)
        # Should not raise
        orchestrator._display_vote(sample_vote)


class TestAgentReviewTask:
    """Tests for _agent_review_task with caching."""

    @patch.object(Agent, 'review')
    def test_agent_review_task_calls_api(self, mock_review, storage, quiet_console, mock_agent_review):
        """_agent_review_task should call API when cache miss."""
        mock_review.return_value = mock_agent_review

        orchestrator = DebateOrchestrator(
            storage=storage,
            console=quiet_console,
            use_cache=False,
        )

        agent = orchestrator.agents[0]
        result, was_cached = orchestrator._agent_review_task(agent, "x = 1", None)

        assert isinstance(result, ReviewResult)
        assert was_cached is False
        mock_review.assert_called_once()
