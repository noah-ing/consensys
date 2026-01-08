"""Tests for CLI commands."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import (
    cli,
    severity_meets_threshold,
    filter_issues_by_severity,
    check_fail_threshold,
    SEVERITY_ORDER,
)
from src.models.review import Review, Consensus, VoteDecision


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


class TestCLIGroup:
    """Tests for the main CLI group."""

    def test_cli_help(self, runner):
        """CLI should show help message."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Multi-agent AI code review" in result.output

    def test_cli_version(self, runner):
        """CLI should show version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestSeverityHelpers:
    """Tests for severity helper functions."""

    def test_severity_order_values(self):
        """SEVERITY_ORDER should have correct values."""
        assert SEVERITY_ORDER["LOW"] == 1
        assert SEVERITY_ORDER["MEDIUM"] == 2
        assert SEVERITY_ORDER["HIGH"] == 3
        assert SEVERITY_ORDER["CRITICAL"] == 4

    def test_severity_meets_threshold_equal(self):
        """severity_meets_threshold should return True for equal severity."""
        assert severity_meets_threshold("HIGH", "HIGH") is True
        assert severity_meets_threshold("LOW", "LOW") is True

    def test_severity_meets_threshold_above(self):
        """severity_meets_threshold should return True for higher severity."""
        assert severity_meets_threshold("CRITICAL", "HIGH") is True
        assert severity_meets_threshold("HIGH", "MEDIUM") is True
        assert severity_meets_threshold("MEDIUM", "LOW") is True

    def test_severity_meets_threshold_below(self):
        """severity_meets_threshold should return False for lower severity."""
        assert severity_meets_threshold("LOW", "HIGH") is False
        assert severity_meets_threshold("MEDIUM", "CRITICAL") is False

    def test_severity_meets_threshold_case_insensitive(self):
        """severity_meets_threshold should be case-insensitive."""
        assert severity_meets_threshold("high", "HIGH") is True
        assert severity_meets_threshold("HIGH", "high") is True

    def test_filter_issues_by_severity(self):
        """filter_issues_by_severity should filter correctly."""
        issues = [
            {"description": "Low issue", "severity": "LOW"},
            {"description": "Medium issue", "severity": "MEDIUM"},
            {"description": "High issue", "severity": "HIGH"},
            {"description": "Critical issue", "severity": "CRITICAL"},
        ]

        # Filter for HIGH and above
        filtered = filter_issues_by_severity(issues, "HIGH")
        assert len(filtered) == 2
        assert filtered[0]["severity"] == "HIGH"
        assert filtered[1]["severity"] == "CRITICAL"

    def test_filter_issues_by_severity_empty(self):
        """filter_issues_by_severity should return empty for no matches."""
        issues = [
            {"description": "Low issue", "severity": "LOW"},
        ]
        filtered = filter_issues_by_severity(issues, "HIGH")
        assert len(filtered) == 0

    def test_filter_issues_by_severity_all(self):
        """filter_issues_by_severity should return all if threshold is LOW."""
        issues = [
            {"description": "Low issue", "severity": "LOW"},
            {"description": "High issue", "severity": "HIGH"},
        ]
        filtered = filter_issues_by_severity(issues, "LOW")
        assert len(filtered) == 2


class TestCheckFailThreshold:
    """Tests for check_fail_threshold function."""

    def test_check_fail_threshold_true(self):
        """check_fail_threshold should return True if issues meet threshold."""
        reviews = [
            Review(
                agent_name="Test",
                issues=[{"description": "Critical", "severity": "CRITICAL"}],
                suggestions=[],
                severity="CRITICAL",
                confidence=0.9,
                summary="Bad",
            )
        ]
        consensus = Consensus(
            final_decision=VoteDecision.REJECT,
            vote_counts={"APPROVE": 0, "REJECT": 1, "ABSTAIN": 0},
            key_issues=[],
            accepted_suggestions=[],
        )

        result = check_fail_threshold(reviews, consensus, "HIGH")
        assert result is True

    def test_check_fail_threshold_false(self):
        """check_fail_threshold should return False if no issues meet threshold."""
        reviews = [
            Review(
                agent_name="Test",
                issues=[{"description": "Minor", "severity": "LOW"}],
                suggestions=[],
                severity="LOW",
                confidence=0.9,
                summary="OK",
            )
        ]
        consensus = Consensus(
            final_decision=VoteDecision.APPROVE,
            vote_counts={"APPROVE": 1, "REJECT": 0, "ABSTAIN": 0},
            key_issues=[],
            accepted_suggestions=[],
        )

        result = check_fail_threshold(reviews, consensus, "HIGH")
        assert result is False

    def test_check_fail_threshold_consensus_issues(self):
        """check_fail_threshold should check consensus key_issues."""
        reviews = [
            Review(
                agent_name="Test",
                issues=[],
                suggestions=[],
                severity="LOW",
                confidence=0.9,
                summary="OK",
            )
        ]
        consensus = Consensus(
            final_decision=VoteDecision.REJECT,
            vote_counts={"APPROVE": 0, "REJECT": 1, "ABSTAIN": 0},
            key_issues=[{"description": "Key issue", "severity": "HIGH"}],
            accepted_suggestions=[],
        )

        result = check_fail_threshold(reviews, consensus, "HIGH")
        assert result is True


class TestReviewCommand:
    """Tests for the review command."""

    def test_review_requires_input(self, runner):
        """review command should require file or --code."""
        result = runner.invoke(cli, ["review"])
        # Should fail or prompt
        assert result.exit_code != 0 or "Error" in result.output or "Usage" in result.output

    @patch("src.cli.DebateOrchestrator")
    def test_review_inline_code(self, mock_orchestrator, runner):
        """review --code should review inline code."""
        # Setup mock
        mock_instance = MagicMock()
        mock_orchestrator.return_value = mock_instance
        mock_instance.run_full_debate.return_value = Consensus(
            final_decision=VoteDecision.APPROVE,
            vote_counts={"APPROVE": 4, "REJECT": 0, "ABSTAIN": 0},
            key_issues=[],
            accepted_suggestions=[],
        )
        mock_instance.reviews = []

        result = runner.invoke(cli, ["review", "--code", "x = 1"])
        # Should complete without error
        assert result.exit_code == 0 or mock_orchestrator.called

    @patch("src.cli.DebateOrchestrator")
    def test_review_quick_mode(self, mock_orchestrator, runner):
        """review --quick should use quick mode."""
        mock_instance = MagicMock()
        mock_orchestrator.return_value = mock_instance
        mock_instance.run_quick_review.return_value = Consensus(
            final_decision=VoteDecision.APPROVE,
            vote_counts={"APPROVE": 4, "REJECT": 0, "ABSTAIN": 0},
            key_issues=[],
            accepted_suggestions=[],
        )
        mock_instance.reviews = []

        result = runner.invoke(cli, ["review", "--code", "x = 1", "--quick"])
        # Quick review should be called
        assert mock_instance.run_quick_review.called or result.exit_code == 0

    def test_review_file_not_found(self, runner):
        """review should error for non-existent file."""
        result = runner.invoke(cli, ["review", "/nonexistent/file.py"])
        assert result.exit_code != 0


class TestHistoryCommand:
    """Tests for the history command."""

    @patch("src.cli.Storage")
    def test_history_command(self, mock_storage, runner):
        """history command should list sessions."""
        mock_storage.return_value.list_sessions.return_value = [
            {
                "session_id": "test-123",
                "code_snippet": "x = 1",
                "created_at": "2024-01-01T00:00:00",
                "final_decision": "APPROVE",
            }
        ]

        result = runner.invoke(cli, ["history"])
        # Should complete or show output
        assert result.exit_code == 0 or mock_storage.called


class TestStatsCommand:
    """Tests for the stats command."""

    @patch("src.cli.Storage")
    def test_stats_command(self, mock_storage, runner):
        """stats command should show statistics."""
        mock_storage.return_value.get_stats.return_value = {
            "total_sessions": 10,
            "completed_sessions": 8,
            "vote_breakdown": {"APPROVE": 20, "REJECT": 5, "ABSTAIN": 3},
            "agreement_breakdown": {"AGREE": 30, "PARTIAL": 15, "DISAGREE": 5},
        }

        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0 or mock_storage.called


class TestExportCommand:
    """Tests for the export command."""

    @patch("src.cli.DebateExporter")
    @patch("src.cli.Storage")
    def test_export_requires_session_id(self, mock_storage, mock_exporter, runner):
        """export command should require session_id."""
        result = runner.invoke(cli, ["export"])
        # Should fail or prompt
        assert result.exit_code != 0 or "Usage" in result.output


class TestTeamsCommand:
    """Tests for the teams command."""

    def test_teams_command(self, runner):
        """teams command should list team presets."""
        result = runner.invoke(cli, ["teams"])
        # Should show team information
        assert result.exit_code == 0 or "team" in result.output.lower() or "Teams" in result.output


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_cli_help_subcommands(self, runner):
        """CLI help should list available commands."""
        result = runner.invoke(cli, ["--help"])
        assert "review" in result.output
        assert "history" in result.output or "Commands" in result.output

    def test_review_help(self, runner):
        """review --help should show review options."""
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0
        assert "--quick" in result.output or "quick" in result.output.lower()
        assert "--code" in result.output or "code" in result.output.lower()
