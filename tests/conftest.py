"""Shared pytest fixtures for Consensus tests."""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agents.personas import Persona, PERSONAS, SecurityExpert, PerformanceEngineer
from src.models.review import Review, Response, Vote, Consensus, VoteDecision
from src.db.storage import Storage


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)
        # Cleanup after test
        try:
            os.unlink(f.name)
        except OSError:
            pass


@pytest.fixture
def storage(temp_db_path):
    """Create a Storage instance with a temporary database."""
    return Storage(db_path=temp_db_path)


@pytest.fixture
def sample_code():
    """Sample Python code for testing reviews."""
    return '''def calculate_total(items):
    total = 0
    for item in items:
        total += item['price'] * item['quantity']
    return total
'''


@pytest.fixture
def sample_code_with_issues():
    """Sample code with obvious issues for testing."""
    return '''import os
def execute_command(user_input):
    os.system(user_input)  # Command injection vulnerability
    return True
'''


@pytest.fixture
def sample_review():
    """Sample Review object for testing."""
    return Review(
        agent_name="SecurityExpert",
        issues=[
            {"description": "Command injection vulnerability", "severity": "CRITICAL", "line": 3},
            {"description": "No input validation", "severity": "HIGH", "line": 2},
        ],
        suggestions=["Use subprocess with shell=False", "Validate and sanitize input"],
        severity="CRITICAL",
        confidence=0.95,
        summary="Critical security vulnerabilities found",
        session_id="test-session-123",
    )


@pytest.fixture
def sample_response():
    """Sample Response object for testing."""
    return Response(
        agent_name="PragmaticDev",
        responding_to="SecurityExpert",
        agreement_level="AGREE",
        points=["Agree this is a critical issue", "Should be fixed immediately"],
        summary="Fully agree with security assessment",
        session_id="test-session-123",
    )


@pytest.fixture
def sample_vote():
    """Sample Vote object for testing."""
    return Vote(
        agent_name="SecurityExpert",
        decision=VoteDecision.REJECT,
        reasoning="Critical security issues must be addressed",
        session_id="test-session-123",
    )


@pytest.fixture
def sample_consensus():
    """Sample Consensus object for testing."""
    return Consensus(
        final_decision=VoteDecision.REJECT,
        vote_counts={"APPROVE": 1, "REJECT": 3, "ABSTAIN": 0},
        key_issues=[{"description": "Command injection", "severity": "CRITICAL"}],
        accepted_suggestions=["Use subprocess with shell=False"],
        session_id="test-session-123",
        code_snippet="os.system(user_input)",
    )


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = '''{
        "issues": [{"description": "Test issue", "severity": "LOW", "line": 1}],
        "suggestions": ["Test suggestion"],
        "severity": "LOW",
        "confidence": 0.8,
        "summary": "Test summary"
    }'''
    return mock_response


@pytest.fixture
def mock_anthropic_vote_response():
    """Mock Anthropic API vote response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = '''{
        "decision": "APPROVE",
        "reasoning": "Code looks good with minor issues"
    }'''
    return mock_response


@pytest.fixture
def mock_anthropic_respond_response():
    """Mock Anthropic API respond response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = '''{
        "agreement_level": "AGREE",
        "points": ["Good point about security"],
        "summary": "I agree with the assessment"
    }'''
    return mock_response
