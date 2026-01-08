"""Tests for the RedTeam agent module."""
import json
import pytest
from unittest.mock import MagicMock, patch

from src.agents.redteam import (
    RedTeamAgent,
    RedTeamPersona,
    ExploitResult,
    PatchResult,
    VULNERABILITY_TYPES,
)


class TestExploitResult:
    """Tests for ExploitResult dataclass."""

    def test_exploit_result_creation(self):
        """Test ExploitResult can be created with required fields."""
        result = ExploitResult(
            vulnerability_type="sql_injection",
            exploit_code="' OR 1=1 --",
            payload="'; DROP TABLE users; --",
            curl_command="curl 'http://example.com?id=' OR 1=1 --'",
            explanation="SQL injection bypasses authentication",
        )
        assert result.vulnerability_type == "sql_injection"
        assert result.exploit_code == "' OR 1=1 --"
        assert result.payload == "'; DROP TABLE users; --"
        assert result.curl_command == "curl 'http://example.com?id=' OR 1=1 --'"
        assert "SQL injection" in result.explanation

    def test_exploit_result_has_poc_warning(self):
        """Test ExploitResult includes PoC warning by default."""
        result = ExploitResult(
            vulnerability_type="xss",
            exploit_code="<script>alert(1)</script>",
            payload="<script>alert(1)</script>",
            curl_command="N/A",
            explanation="XSS attack",
        )
        assert "PoC" in result.poc_warning
        assert "authorized" in result.poc_warning.lower()

    def test_exploit_result_success_indicators(self):
        """Test ExploitResult can have success indicators."""
        result = ExploitResult(
            vulnerability_type="command_injection",
            exploit_code="; id",
            payload="; cat /etc/passwd",
            curl_command="curl 'http://example.com?cmd=;id'",
            explanation="Command injection",
            success_indicators=["uid=", "gid=", "groups="],
        )
        assert len(result.success_indicators) == 3
        assert "uid=" in result.success_indicators


class TestPatchResult:
    """Tests for PatchResult dataclass."""

    def test_patch_result_creation(self):
        """Test PatchResult can be created with required fields."""
        result = PatchResult(
            patched_code="cursor.execute(query, (param,))",
            diff="- cursor.execute(query + param)\n+ cursor.execute(query, (param,))",
            explanation="Use parameterized queries",
            verification_test="assert '; DROP' not in result",
        )
        assert "execute" in result.patched_code
        assert "+" in result.diff
        assert "-" in result.diff

    def test_patch_result_before_after(self):
        """Test PatchResult can include before/after comparison."""
        result = PatchResult(
            patched_code="safe_code()",
            diff="diff output",
            explanation="Fixed vulnerability",
            verification_test="test",
            before_after="Before: exploit works\nAfter: exploit blocked",
        )
        assert "Before:" in result.before_after
        assert "After:" in result.before_after


class TestRedTeamPersona:
    """Tests for RedTeam persona definition."""

    def test_persona_exists(self):
        """Test RedTeamPersona is defined."""
        assert RedTeamPersona is not None
        assert RedTeamPersona.name == "RedTeam"

    def test_persona_has_security_focus(self):
        """Test persona has security-focused attributes."""
        assert "adversarial" in RedTeamPersona.system_prompt.lower()
        assert "security" in RedTeamPersona.system_prompt.lower()
        assert "exploit" in RedTeamPersona.system_prompt.lower()

    def test_persona_has_ethical_guidelines(self):
        """Test persona includes ethical guidelines."""
        assert "AUTHORIZED" in RedTeamPersona.system_prompt
        assert "EDUCATION" in RedTeamPersona.system_prompt

    def test_persona_priorities(self):
        """Test persona has appropriate priorities."""
        assert "Vulnerability exploitation" in RedTeamPersona.priorities
        assert "Security testing" in RedTeamPersona.priorities


class TestVulnerabilityTypes:
    """Tests for supported vulnerability types."""

    def test_vulnerability_types_defined(self):
        """Test vulnerability types list exists."""
        assert len(VULNERABILITY_TYPES) == 5

    def test_sql_injection_supported(self):
        """Test SQL injection is supported."""
        assert "sql_injection" in VULNERABILITY_TYPES

    def test_xss_supported(self):
        """Test XSS is supported."""
        assert "xss" in VULNERABILITY_TYPES

    def test_command_injection_supported(self):
        """Test command injection is supported."""
        assert "command_injection" in VULNERABILITY_TYPES

    def test_path_traversal_supported(self):
        """Test path traversal is supported."""
        assert "path_traversal" in VULNERABILITY_TYPES

    def test_auth_bypass_supported(self):
        """Test auth bypass is supported."""
        assert "auth_bypass" in VULNERABILITY_TYPES


class TestRedTeamAgent:
    """Tests for RedTeamAgent class."""

    @pytest.fixture
    def agent(self):
        """Create a RedTeamAgent instance."""
        with patch('src.agents.redteam.Anthropic'):
            return RedTeamAgent(session_id="test-session")

    def test_agent_creation(self, agent):
        """Test agent can be created."""
        assert agent.persona == RedTeamPersona
        assert agent.session_id == "test-session"

    def test_agent_repr(self, agent):
        """Test agent string representation."""
        repr_str = repr(agent)
        assert "RedTeamAgent" in repr_str
        assert "RedTeam" in repr_str

    def test_generate_exploit_validates_vulnerability_type(self, agent):
        """Test generate_exploit validates vulnerability type."""
        with pytest.raises(ValueError) as exc_info:
            agent.generate_exploit(
                code="def foo(): pass",
                vulnerability="unsupported_vuln"
            )
        assert "Unsupported vulnerability type" in str(exc_info.value)
        assert "sql_injection" in str(exc_info.value)  # Shows valid types

    def test_generate_exploit_normalizes_vulnerability_type(self, agent):
        """Test generate_exploit normalizes vulnerability type variations."""
        # Mock the API call
        mock_response = json.dumps({
            "exploit_code": "test exploit",
            "payload": "test payload",
            "curl_command": "curl test",
            "explanation": "test explanation",
            "success_indicators": ["indicator1"]
        })
        agent._call_api = MagicMock(return_value=mock_response)

        # Test various formats
        for vuln_format in ["SQL Injection", "sql-injection", "SQL_INJECTION"]:
            result = agent.generate_exploit(
                code="query = 'SELECT * FROM users WHERE id=' + user_id",
                vulnerability=vuln_format
            )
            assert result.vulnerability_type == "sql_injection"

    @pytest.fixture
    def mock_exploit_response(self):
        """Create a mock API response for exploit generation."""
        return json.dumps({
            "exploit_code": "' OR 1=1 --",
            "payload": "admin'--",
            "curl_command": "curl 'http://test.com/login?user=admin%27--'",
            "explanation": "This SQL injection bypasses authentication by commenting out the password check.",
            "success_indicators": ["Login successful", "Welcome admin"]
        })

    def test_generate_exploit_returns_exploit_result(self, agent, mock_exploit_response):
        """Test generate_exploit returns ExploitResult."""
        agent._call_api = MagicMock(return_value=mock_exploit_response)

        result = agent.generate_exploit(
            code="SELECT * FROM users WHERE user='" + "' + username",
            vulnerability="sql_injection"
        )

        assert isinstance(result, ExploitResult)
        assert result.vulnerability_type == "sql_injection"
        assert "1=1" in result.exploit_code
        assert result.curl_command.startswith("curl")
        assert "[PoC" in result.poc_warning

    def test_generate_exploit_with_context(self, agent, mock_exploit_response):
        """Test generate_exploit accepts context parameter."""
        agent._call_api = MagicMock(return_value=mock_exploit_response)

        result = agent.generate_exploit(
            code="query = f'SELECT * FROM users WHERE id={user_id}'",
            vulnerability="sql_injection",
            context="This is a Flask web application using SQLite"
        )

        assert isinstance(result, ExploitResult)
        # Verify context was passed to the API
        call_args = agent._call_api.call_args
        assert "Flask" in call_args[0][1]  # user_message argument

    @pytest.fixture
    def mock_patch_response(self):
        """Create a mock API response for patch generation."""
        return json.dumps({
            "patched_code": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            "diff": "- query = f'SELECT * FROM users WHERE id={user_id}'\n+ cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            "explanation": "Use parameterized queries to prevent SQL injection",
            "verification_test": "assert '; DROP' not in result",
            "before_after": "Before: SQL injection works\nAfter: SQL injection blocked"
        })

    def test_generate_patch_returns_patch_result(self, agent, mock_patch_response):
        """Test generate_patch returns PatchResult."""
        agent._call_api = MagicMock(return_value=mock_patch_response)

        # First create an exploit result
        exploit = ExploitResult(
            vulnerability_type="sql_injection",
            exploit_code="' OR 1=1 --",
            payload="admin'--",
            curl_command="curl test",
            explanation="SQL injection"
        )

        result = agent.generate_patch(
            code="query = f'SELECT * FROM users WHERE id={user_id}'",
            exploit=exploit
        )

        assert isinstance(result, PatchResult)
        assert "?" in result.patched_code  # Parameterized query
        assert "+" in result.diff
        assert "-" in result.diff

    def test_parse_json_response_handles_markdown_blocks(self, agent):
        """Test JSON parsing handles markdown code blocks."""
        markdown_response = '''```json
{
    "exploit_code": "test",
    "payload": "test",
    "curl_command": "N/A",
    "explanation": "test",
    "success_indicators": []
}
```'''
        result = agent._parse_json_response(markdown_response)
        assert result["exploit_code"] == "test"

    def test_parse_json_response_handles_plain_json(self, agent):
        """Test JSON parsing handles plain JSON."""
        plain_response = '{"key": "value"}'
        result = agent._parse_json_response(plain_response)
        assert result["key"] == "value"

    def test_build_exploit_prompt_includes_vulnerability_instructions(self, agent):
        """Test exploit prompt includes vulnerability-specific instructions."""
        prompt = agent._build_exploit_prompt("sql_injection")
        assert "SQL" in prompt
        assert "parameterized" in prompt.lower() or "injection" in prompt.lower()

        prompt = agent._build_exploit_prompt("xss")
        assert "XSS" in prompt or "Cross-Site" in prompt

    def test_build_patch_prompt_includes_fix_instructions(self, agent):
        """Test patch prompt includes fix instructions."""
        prompt = agent._build_patch_prompt("sql_injection")
        assert "parameterized" in prompt.lower()
        assert "prepared statements" in prompt.lower()

        prompt = agent._build_patch_prompt("command_injection")
        assert "subprocess" in prompt.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def agent(self):
        """Create a RedTeamAgent instance."""
        with patch('src.agents.redteam.Anthropic'):
            return RedTeamAgent()

    def test_empty_code_still_works(self, agent):
        """Test agent handles empty code."""
        mock_response = json.dumps({
            "exploit_code": "",
            "payload": "",
            "curl_command": "N/A",
            "explanation": "No vulnerability found in empty code",
            "success_indicators": []
        })
        agent._call_api = MagicMock(return_value=mock_response)

        result = agent.generate_exploit(code="", vulnerability="sql_injection")
        assert isinstance(result, ExploitResult)

    def test_missing_fields_in_response_use_defaults(self, agent):
        """Test agent handles missing fields in API response."""
        incomplete_response = json.dumps({
            "explanation": "Partial response"
        })
        agent._call_api = MagicMock(return_value=incomplete_response)

        result = agent.generate_exploit(
            code="vulnerable_code()",
            vulnerability="sql_injection"
        )
        assert result.exploit_code == ""
        assert result.payload == ""
        assert result.curl_command == "N/A"

    def test_no_vulnerability_found_returns_empty_result(self, agent):
        """Test agent handles code with no vulnerabilities."""
        safe_response = json.dumps({
            "exploit_code": "No exploitable vulnerability found",
            "payload": "N/A",
            "curl_command": "N/A",
            "explanation": "The code uses parameterized queries and is not vulnerable to SQL injection.",
            "success_indicators": []
        })
        agent._call_api = MagicMock(return_value=safe_response)

        result = agent.generate_exploit(
            code="cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            vulnerability="sql_injection"
        )
        assert "not vulnerable" in result.explanation.lower() or "No exploitable" in result.exploit_code

    def test_perfect_code_patch(self, agent):
        """Test patching already secure code."""
        mock_response = json.dumps({
            "patched_code": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            "diff": "No changes needed - code is already secure",
            "explanation": "The code already uses parameterized queries",
            "verification_test": "# Already secure",
            "before_after": "N/A"
        })
        agent._call_api = MagicMock(return_value=mock_response)

        exploit = ExploitResult(
            vulnerability_type="sql_injection",
            exploit_code="N/A",
            payload="N/A",
            curl_command="N/A",
            explanation="No vulnerability"
        )

        result = agent.generate_patch(
            code="cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            exploit=exploit
        )
        assert "already" in result.explanation.lower() or "No changes" in result.diff
