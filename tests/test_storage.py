"""Tests for SQLite storage layer."""
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.db.storage import Storage
from src.models.review import Review, Response, Vote, Consensus, VoteDecision


class TestStorageInit:
    """Tests for Storage initialization."""

    def test_storage_creates_database(self, temp_db_path):
        """Storage should create database file on init."""
        storage = Storage(db_path=temp_db_path)
        assert temp_db_path.exists()

    def test_storage_creates_tables(self, temp_db_path):
        """Storage should create all required tables."""
        storage = Storage(db_path=temp_db_path)

        conn = storage._get_connection()
        cursor = conn.cursor()

        # Check all tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "sessions" in tables
        assert "reviews" in tables
        assert "responses" in tables
        assert "votes" in tables
        assert "consensus" in tables

    def test_storage_idempotent_init(self, temp_db_path):
        """Multiple Storage inits should not fail (IF NOT EXISTS)."""
        storage1 = Storage(db_path=temp_db_path)
        storage2 = Storage(db_path=temp_db_path)
        # Should not raise


class TestStorageSessions:
    """Tests for session operations."""

    def test_create_session(self, storage):
        """create_session should return a session ID."""
        session_id = storage.create_session("x = 1")
        assert session_id is not None
        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_create_session_with_context(self, storage):
        """create_session should store context."""
        session_id = storage.create_session("x = 1", context="Test context")
        session = storage.get_session(session_id)
        assert session["context"] == "Test context"

    def test_get_session(self, storage, sample_code):
        """get_session should return session details."""
        session_id = storage.create_session(sample_code)
        session = storage.get_session(session_id)

        assert session is not None
        assert session["session_id"] == session_id
        assert session["code_snippet"] == sample_code
        assert session["created_at"] is not None

    def test_get_session_not_found(self, storage):
        """get_session should return None for unknown ID."""
        result = storage.get_session("nonexistent-id")
        assert result is None

    def test_list_sessions(self, storage):
        """list_sessions should return recent sessions."""
        # Create multiple sessions
        storage.create_session("code1")
        storage.create_session("code2")
        storage.create_session("code3")

        sessions = storage.list_sessions()
        assert len(sessions) == 3

    def test_list_sessions_limit(self, storage):
        """list_sessions should respect limit parameter."""
        for i in range(10):
            storage.create_session(f"code{i}")

        sessions = storage.list_sessions(limit=5)
        assert len(sessions) == 5

    def test_list_sessions_order(self, storage):
        """list_sessions should order by created_at DESC."""
        storage.create_session("first")
        storage.create_session("second")

        sessions = storage.list_sessions()
        # Most recent should be first
        assert sessions[0]["code_snippet"] == "second"


class TestStorageReviews:
    """Tests for review operations."""

    def test_save_review(self, storage, sample_review):
        """save_review should store review in database."""
        session_id = storage.create_session("test code")
        review_id = storage.save_review(sample_review, session_id)

        assert review_id is not None
        assert isinstance(review_id, int)

    def test_get_reviews(self, storage, sample_review):
        """get_reviews should return all reviews for session."""
        session_id = storage.create_session("test code")
        storage.save_review(sample_review, session_id)

        reviews = storage.get_reviews(session_id)
        assert len(reviews) == 1
        assert reviews[0].agent_name == sample_review.agent_name
        assert reviews[0].severity == sample_review.severity

    def test_get_reviews_preserves_issues(self, storage, sample_review):
        """get_reviews should preserve issue list."""
        session_id = storage.create_session("test code")
        storage.save_review(sample_review, session_id)

        reviews = storage.get_reviews(session_id)
        assert len(reviews[0].issues) == len(sample_review.issues)
        assert reviews[0].issues[0]["severity"] == "CRITICAL"

    def test_get_reviews_preserves_suggestions(self, storage, sample_review):
        """get_reviews should preserve suggestions list."""
        session_id = storage.create_session("test code")
        storage.save_review(sample_review, session_id)

        reviews = storage.get_reviews(session_id)
        assert len(reviews[0].suggestions) == len(sample_review.suggestions)

    def test_get_reviews_empty(self, storage):
        """get_reviews should return empty list if no reviews."""
        session_id = storage.create_session("test code")
        reviews = storage.get_reviews(session_id)
        assert reviews == []


class TestStorageResponses:
    """Tests for response operations."""

    def test_save_response(self, storage, sample_response):
        """save_response should store response in database."""
        session_id = storage.create_session("test code")
        response_id = storage.save_response(sample_response, session_id)

        assert response_id is not None
        assert isinstance(response_id, int)

    def test_get_responses(self, storage, sample_response):
        """get_responses should return all responses for session."""
        session_id = storage.create_session("test code")
        storage.save_response(sample_response, session_id)

        responses = storage.get_responses(session_id)
        assert len(responses) == 1
        assert responses[0].agent_name == sample_response.agent_name
        assert responses[0].responding_to == sample_response.responding_to

    def test_get_responses_preserves_agreement(self, storage, sample_response):
        """get_responses should preserve agreement level."""
        session_id = storage.create_session("test code")
        storage.save_response(sample_response, session_id)

        responses = storage.get_responses(session_id)
        assert responses[0].agreement_level == sample_response.agreement_level

    def test_get_responses_preserves_points(self, storage, sample_response):
        """get_responses should preserve points list."""
        session_id = storage.create_session("test code")
        storage.save_response(sample_response, session_id)

        responses = storage.get_responses(session_id)
        assert len(responses[0].points) == len(sample_response.points)

    def test_get_responses_empty(self, storage):
        """get_responses should return empty list if no responses."""
        session_id = storage.create_session("test code")
        responses = storage.get_responses(session_id)
        assert responses == []


class TestStorageVotes:
    """Tests for vote operations."""

    def test_save_vote(self, storage, sample_vote):
        """save_vote should store vote in database."""
        session_id = storage.create_session("test code")
        vote_id = storage.save_vote(sample_vote, session_id)

        assert vote_id is not None
        assert isinstance(vote_id, int)

    def test_get_votes(self, storage, sample_vote):
        """get_votes should return all votes for session."""
        session_id = storage.create_session("test code")
        storage.save_vote(sample_vote, session_id)

        votes = storage.get_votes(session_id)
        assert len(votes) == 1
        assert votes[0].agent_name == sample_vote.agent_name
        assert votes[0].decision == sample_vote.decision

    def test_get_votes_preserves_decision(self, storage):
        """get_votes should preserve VoteDecision enum."""
        session_id = storage.create_session("test code")
        vote = Vote(
            agent_name="Test",
            decision=VoteDecision.APPROVE,
            reasoning="Good code",
        )
        storage.save_vote(vote, session_id)

        votes = storage.get_votes(session_id)
        assert votes[0].decision == VoteDecision.APPROVE

    def test_get_votes_all_decisions(self, storage):
        """get_votes should handle all VoteDecision values."""
        session_id = storage.create_session("test code")

        for decision in [VoteDecision.APPROVE, VoteDecision.REJECT, VoteDecision.ABSTAIN]:
            vote = Vote(agent_name="Test", decision=decision, reasoning="test")
            storage.save_vote(vote, session_id)

        votes = storage.get_votes(session_id)
        decisions = [v.decision for v in votes]
        assert VoteDecision.APPROVE in decisions
        assert VoteDecision.REJECT in decisions
        assert VoteDecision.ABSTAIN in decisions

    def test_get_votes_empty(self, storage):
        """get_votes should return empty list if no votes."""
        session_id = storage.create_session("test code")
        votes = storage.get_votes(session_id)
        assert votes == []


class TestStorageConsensus:
    """Tests for consensus operations."""

    def test_save_consensus(self, storage, sample_consensus):
        """save_consensus should store consensus in database."""
        session_id = storage.create_session("test code")
        sample_consensus.session_id = session_id
        consensus_id = storage.save_consensus(sample_consensus)

        assert consensus_id is not None
        assert isinstance(consensus_id, int)

    def test_get_consensus(self, storage, sample_consensus):
        """get_consensus should return consensus for session."""
        session_id = storage.create_session("test code")
        sample_consensus.session_id = session_id
        storage.save_consensus(sample_consensus)

        consensus = storage.get_consensus(session_id)
        assert consensus is not None
        assert consensus.final_decision == sample_consensus.final_decision

    def test_get_consensus_preserves_vote_counts(self, storage, sample_consensus):
        """get_consensus should preserve vote counts."""
        session_id = storage.create_session("test code")
        sample_consensus.session_id = session_id
        storage.save_consensus(sample_consensus)

        consensus = storage.get_consensus(session_id)
        assert consensus.vote_counts == sample_consensus.vote_counts

    def test_get_consensus_preserves_key_issues(self, storage, sample_consensus):
        """get_consensus should preserve key issues."""
        session_id = storage.create_session("test code")
        sample_consensus.session_id = session_id
        storage.save_consensus(sample_consensus)

        consensus = storage.get_consensus(session_id)
        assert len(consensus.key_issues) == len(sample_consensus.key_issues)

    def test_get_consensus_not_found(self, storage):
        """get_consensus should return None if not found."""
        session_id = storage.create_session("test code")
        consensus = storage.get_consensus(session_id)
        assert consensus is None

    def test_save_consensus_updates_session(self, storage, sample_consensus):
        """save_consensus should update session final_decision."""
        session_id = storage.create_session("test code")
        sample_consensus.session_id = session_id
        storage.save_consensus(sample_consensus)

        session = storage.get_session(session_id)
        assert session["final_decision"] == "REJECT"
        assert session["completed_at"] is not None


class TestStorageStats:
    """Tests for aggregate statistics."""

    def test_get_stats_empty(self, storage):
        """get_stats should return zeros for empty database."""
        stats = storage.get_stats()
        assert stats["total_sessions"] == 0
        assert stats["completed_sessions"] == 0

    def test_get_stats_total_sessions(self, storage):
        """get_stats should count total sessions."""
        storage.create_session("code1")
        storage.create_session("code2")

        stats = storage.get_stats()
        assert stats["total_sessions"] == 2

    def test_get_stats_completed_sessions(self, storage, sample_consensus):
        """get_stats should count completed sessions."""
        session_id = storage.create_session("test code")
        sample_consensus.session_id = session_id
        storage.save_consensus(sample_consensus)

        stats = storage.get_stats()
        assert stats["completed_sessions"] == 1

    def test_get_stats_vote_breakdown(self, storage):
        """get_stats should provide vote breakdown."""
        session_id = storage.create_session("test code")

        # Add various votes
        storage.save_vote(
            Vote("Agent1", VoteDecision.APPROVE, "good"), session_id
        )
        storage.save_vote(
            Vote("Agent2", VoteDecision.APPROVE, "fine"), session_id
        )
        storage.save_vote(
            Vote("Agent3", VoteDecision.REJECT, "issues"), session_id
        )

        stats = storage.get_stats()
        assert stats["vote_breakdown"]["APPROVE"] == 2
        assert stats["vote_breakdown"]["REJECT"] == 1

    def test_get_stats_agreement_breakdown(self, storage):
        """get_stats should provide agreement level breakdown."""
        session_id = storage.create_session("test code")

        # Add various responses
        storage.save_response(
            Response("A1", "A2", "AGREE", [], "agree"), session_id
        )
        storage.save_response(
            Response("A2", "A1", "PARTIAL", [], "partial"), session_id
        )
        storage.save_response(
            Response("A3", "A1", "DISAGREE", [], "disagree"), session_id
        )

        stats = storage.get_stats()
        assert stats["agreement_breakdown"]["AGREE"] == 1
        assert stats["agreement_breakdown"]["PARTIAL"] == 1
        assert stats["agreement_breakdown"]["DISAGREE"] == 1


class TestStorageConnectionManagement:
    """Tests for database connection management."""

    def test_connection_per_operation(self, temp_db_path):
        """Each operation should use its own connection."""
        storage = Storage(db_path=temp_db_path)

        # Multiple operations should not fail
        session_id = storage.create_session("code1")
        storage.get_session(session_id)
        storage.list_sessions()

        # All should work without connection issues

    def test_connection_closes_on_error(self, temp_db_path):
        """Connections should close even on error."""
        storage = Storage(db_path=temp_db_path)

        # Try to get non-existent session (should not fail but should close conn)
        result = storage.get_session("nonexistent")
        assert result is None

        # Should still work after
        session_id = storage.create_session("code")
        assert session_id is not None
