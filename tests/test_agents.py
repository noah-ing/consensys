"""Tests for agent personas and Agent wrapper class."""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.agents.personas import (
    Persona,
    PERSONAS,
    PERSONAS_BY_NAME,
    SecurityExpert,
    PerformanceEngineer,
    ArchitectureCritic,
    PragmaticDev,
    DEBATE_PERSONAS,
    DEBATE_PERSONAS_BY_NAME,
)
from src.agents.agent import Agent, ReviewResult, ResponseResult, VoteResult, CodeFixer, FixResult
from src.models.review import VoteDecision


class TestPersonas:
    """Tests for persona definitions."""

    def test_personas_list_has_four_personas(self):
        """PERSONAS list should contain exactly 4 personas."""
        assert len(PERSONAS) == 4

    def test_personas_by_name_lookup(self):
        """PERSONAS_BY_NAME should allow lookup by name."""
        assert "SecurityExpert" in PERSONAS_BY_NAME
        assert "PerformanceEngineer" in PERSONAS_BY_NAME
        assert "ArchitectureCritic" in PERSONAS_BY_NAME
        assert "PragmaticDev" in PERSONAS_BY_NAME

    def test_persona_has_required_fields(self):
        """Each persona should have all required fields."""
        for persona in PERSONAS:
            assert hasattr(persona, "name")
            assert hasattr(persona, "role")
            assert hasattr(persona, "system_prompt")
            assert hasattr(persona, "priorities")
            assert hasattr(persona, "review_style")

    def test_security_expert_persona(self):
        """SecurityExpert should have security-focused attributes."""
        assert SecurityExpert.name == "SecurityExpert"
        assert SecurityExpert.role == "Application Security Specialist"
        assert "security" in SecurityExpert.system_prompt.lower()
        assert len(SecurityExpert.priorities) > 0

    def test_performance_engineer_persona(self):
        """PerformanceEngineer should have performance-focused attributes."""
        assert PerformanceEngineer.name == "PerformanceEngineer"
        assert "Performance" in PerformanceEngineer.role
        assert "performance" in PerformanceEngineer.system_prompt.lower()

    def test_architecture_critic_persona(self):
        """ArchitectureCritic should have architecture-focused attributes."""
        assert ArchitectureCritic.name == "ArchitectureCritic"
        assert "Architect" in ArchitectureCritic.role
        assert "design" in ArchitectureCritic.system_prompt.lower()

    def test_pragmatic_dev_persona(self):
        """PragmaticDev should have pragmatism-focused attributes."""
        assert PragmaticDev.name == "PragmaticDev"
        assert "Pragmatist" in PragmaticDev.role
        assert "simplicity" in PragmaticDev.system_prompt.lower()

    def test_debate_personas_exist(self):
        """DEBATE_PERSONAS should contain confrontational versions."""
        assert len(DEBATE_PERSONAS) == 4
        assert len(DEBATE_PERSONAS_BY_NAME) == 4

    def test_debate_personas_more_confrontational(self):
        """Debate personas should have more confrontational prompts."""
        for persona in DEBATE_PERSONAS:
            prompt_lower = persona.system_prompt.lower()
            assert "disagree" in prompt_lower or "push back" in prompt_lower


class TestPersonaDataclass:
    """Tests for Persona dataclass behavior."""

    def test_persona_creation(self):
        """Should be able to create a custom persona."""
        custom = Persona(
            name="TestExpert",
            role="Test Role",
            system_prompt="Test prompt",
            priorities=["priority1", "priority2"],
            review_style="test style",
        )
        assert custom.name == "TestExpert"
        assert custom.role == "Test Role"
        assert len(custom.priorities) == 2


class TestAgent:
    """Tests for Agent wrapper class."""

    @patch("src.agents.agent.Anthropic")
    def test_agent_creation(self, mock_anthropic):
        """Agent should initialize with a persona."""
        agent = Agent(SecurityExpert)
        assert agent.persona == SecurityExpert
        assert agent.persona.name == "SecurityExpert"

    @patch("src.agents.agent.Anthropic")
    def test_agent_repr(self, mock_anthropic):
        """Agent __repr__ should include persona name."""
        agent = Agent(SecurityExpert)
        repr_str = repr(agent)
        assert "SecurityExpert" in repr_str

    @patch("src.agents.agent.Anthropic")
    def test_build_system_prompt_review(self, mock_anthropic):
        """_build_system_prompt should include persona details for review task."""
        agent = Agent(SecurityExpert)
        prompt = agent._build_system_prompt("review")
        assert "security" in prompt.lower()
        assert "JSON" in prompt
        assert "issues" in prompt

    @patch("src.agents.agent.Anthropic")
    def test_build_system_prompt_respond(self, mock_anthropic):
        """_build_system_prompt should include response instructions."""
        agent = Agent(SecurityExpert)
        prompt = agent._build_system_prompt("respond")
        assert "agreement_level" in prompt
        assert "AGREE" in prompt

    @patch("src.agents.agent.Anthropic")
    def test_build_system_prompt_vote(self, mock_anthropic):
        """_build_system_prompt should include vote instructions."""
        agent = Agent(SecurityExpert)
        prompt = agent._build_system_prompt("vote")
        assert "decision" in prompt
        assert "APPROVE" in prompt
        assert "REJECT" in prompt

    @patch("src.agents.agent.Anthropic")
    def test_parse_json_response_clean(self, mock_anthropic):
        """_parse_json_response should handle clean JSON."""
        agent = Agent(SecurityExpert)
        data = agent._parse_json_response('{"key": "value"}')
        assert data == {"key": "value"}

    @patch("src.agents.agent.Anthropic")
    def test_parse_json_response_with_markdown(self, mock_anthropic):
        """_parse_json_response should strip markdown code blocks."""
        agent = Agent(SecurityExpert)
        response = '''```json
{"key": "value"}
```'''
        data = agent._parse_json_response(response)
        assert data == {"key": "value"}

    @patch("src.agents.agent.Anthropic")
    def test_review_returns_review_result(self, mock_anthropic, mock_anthropic_response):
        """review() should return a ReviewResult."""
        mock_anthropic.return_value.messages.create.return_value = mock_anthropic_response
        agent = Agent(SecurityExpert)
        result = agent.review("x = 1")

        assert isinstance(result, ReviewResult)
        assert result.agent_name == "SecurityExpert"
        assert isinstance(result.issues, list)
        assert isinstance(result.suggestions, list)

    @patch("src.agents.agent.Anthropic")
    def test_review_with_context(self, mock_anthropic, mock_anthropic_response):
        """review() should accept optional context."""
        mock_anthropic.return_value.messages.create.return_value = mock_anthropic_response
        agent = Agent(SecurityExpert)
        result = agent.review("x = 1", context="This is test code")

        assert isinstance(result, ReviewResult)
        # Verify context was passed (checking the mock was called)
        call_args = mock_anthropic.return_value.messages.create.call_args
        assert "test code" in str(call_args)

    @patch("src.agents.agent.Anthropic")
    def test_respond_to_returns_response_result(self, mock_anthropic, mock_anthropic_respond_response):
        """respond_to() should return a ResponseResult."""
        mock_anthropic.return_value.messages.create.return_value = mock_anthropic_respond_response
        agent = Agent(PragmaticDev)

        other_review = ReviewResult(
            agent_name="SecurityExpert",
            issues=[{"description": "Test", "severity": "HIGH"}],
            suggestions=["Fix it"],
            severity="HIGH",
            confidence=0.9,
            summary="Test review",
        )

        result = agent.respond_to(other_review, "x = 1")

        assert isinstance(result, ResponseResult)
        assert result.agent_name == "PragmaticDev"
        assert result.responding_to == "SecurityExpert"

    @patch("src.agents.agent.Anthropic")
    def test_vote_returns_vote_result(self, mock_anthropic, mock_anthropic_vote_response):
        """vote() should return a VoteResult."""
        mock_anthropic.return_value.messages.create.return_value = mock_anthropic_vote_response
        agent = Agent(SecurityExpert)

        reviews = [
            ReviewResult(
                agent_name="Test",
                issues=[],
                suggestions=[],
                severity="LOW",
                confidence=0.8,
                summary="Looks good",
            )
        ]

        result = agent.vote("x = 1", reviews)

        assert isinstance(result, VoteResult)
        assert result.agent_name == "SecurityExpert"
        assert isinstance(result.decision, VoteDecision)

    @patch("src.agents.agent.Anthropic")
    def test_vote_with_responses(self, mock_anthropic, mock_anthropic_vote_response):
        """vote() should accept optional responses."""
        mock_anthropic.return_value.messages.create.return_value = mock_anthropic_vote_response
        agent = Agent(SecurityExpert)

        reviews = [ReviewResult("Test", [], [], "LOW", 0.8, "OK")]
        responses = [ResponseResult("Test2", "Test", "AGREE", ["Point"], "Agreed")]

        result = agent.vote("x = 1", reviews, responses)
        assert isinstance(result, VoteResult)


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_review_result_defaults(self):
        """ReviewResult should have sensible defaults."""
        result = ReviewResult(agent_name="Test")
        assert result.agent_name == "Test"
        assert result.issues == []
        assert result.suggestions == []
        assert result.severity == "LOW"
        assert result.confidence == 0.8
        assert result.summary == ""

    def test_review_result_with_data(self):
        """ReviewResult should store provided data."""
        result = ReviewResult(
            agent_name="SecurityExpert",
            issues=[{"description": "Issue", "severity": "HIGH"}],
            suggestions=["Fix it"],
            severity="HIGH",
            confidence=0.95,
            summary="Problems found",
        )
        assert result.agent_name == "SecurityExpert"
        assert len(result.issues) == 1
        assert result.severity == "HIGH"


class TestResponseResult:
    """Tests for ResponseResult dataclass."""

    def test_response_result_defaults(self):
        """ResponseResult should have sensible defaults."""
        result = ResponseResult(agent_name="Test", responding_to="Other")
        assert result.agreement_level == "PARTIAL"
        assert result.points == []

    def test_response_result_with_data(self):
        """ResponseResult should store provided data."""
        result = ResponseResult(
            agent_name="Test",
            responding_to="Other",
            agreement_level="AGREE",
            points=["Good point"],
            summary="I agree",
        )
        assert result.agreement_level == "AGREE"
        assert len(result.points) == 1


class TestVoteResult:
    """Tests for VoteResult dataclass."""

    def test_vote_result_defaults(self):
        """VoteResult should default to ABSTAIN."""
        result = VoteResult(agent_name="Test")
        assert result.decision == VoteDecision.ABSTAIN
        assert result.reasoning == ""

    def test_vote_result_with_decision(self):
        """VoteResult should store vote decision."""
        result = VoteResult(
            agent_name="Test",
            decision=VoteDecision.APPROVE,
            reasoning="Code is good",
        )
        assert result.decision == VoteDecision.APPROVE


class TestCodeFixer:
    """Tests for CodeFixer class."""

    @patch("src.agents.agent.Anthropic")
    def test_code_fixer_creation(self, mock_anthropic):
        """CodeFixer should initialize without errors."""
        fixer = CodeFixer()
        assert fixer.model is not None

    @patch("src.agents.agent.Anthropic")
    def test_code_fixer_fix_code(self, mock_anthropic):
        """fix_code() should return FixResult."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '''{"fixed_code": "x = 1\\nprint(x)", "changes_made": ["Fixed issue"], "explanation": "Done"}'''
        mock_anthropic.return_value.messages.create.return_value = mock_response

        fixer = CodeFixer()
        result = fixer.fix_code(
            code="x=1\nprint x",
            issues=[{"description": "Syntax error", "severity": "HIGH"}],
            suggestions=["Use print()"],
        )

        assert isinstance(result, FixResult)
        assert result.original_code == "x=1\nprint x"
        assert "x = 1" in result.fixed_code
