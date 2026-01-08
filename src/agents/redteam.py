"""RedTeam agent for exploit generation and security testing."""
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MAX_TOKENS
from src.agents.personas import Persona


# Supported vulnerability types
VULNERABILITY_TYPES = [
    "sql_injection",
    "xss",
    "command_injection",
    "path_traversal",
    "auth_bypass",
]


@dataclass
class ExploitResult:
    """Result of exploit generation for a vulnerability.

    Attributes:
        vulnerability_type: Type of vulnerability (e.g., sql_injection, xss)
        exploit_code: The exploit code demonstrating the vulnerability
        payload: The malicious payload that triggers the vulnerability
        curl_command: A curl command to test the exploit (if applicable)
        explanation: Detailed explanation of how the exploit works
        success_indicators: How to verify the exploit worked
        poc_warning: Safety warning that this is for demonstration only
    """
    vulnerability_type: str
    exploit_code: str
    payload: str
    curl_command: str
    explanation: str
    success_indicators: List[str] = field(default_factory=list)
    poc_warning: str = field(default="[PoC ONLY] This exploit is for demonstration and authorized security testing only. Do not use against systems without explicit permission.")


@dataclass
class PatchResult:
    """Result of auto-patch generation for a vulnerability.

    Attributes:
        patched_code: The fixed code with vulnerability remediated
        diff: Unified diff showing changes between original and patched code
        explanation: Detailed explanation of the fix and why it works
        verification_test: A test or command to verify the exploit no longer works
        before_after: Comparison showing exploit works before but not after
    """
    patched_code: str
    diff: str
    explanation: str
    verification_test: str
    before_after: str = field(default="")


# RedTeam persona definition
RedTeamPersona = Persona(
    name="RedTeam",
    role="Adversarial Security Researcher",
    system_prompt="""You are an adversarial security researcher who specializes in writing proof-of-concept exploits.
Your mission is to demonstrate how vulnerabilities can be exploited in practice.

When analyzing code for vulnerabilities, you:
- Identify the exact vulnerable code paths
- Craft working exploits that demonstrate the vulnerability
- Provide curl commands or test scripts to trigger the exploit
- Explain the attack vector in detail
- Suggest how to verify the exploit worked

IMPORTANT ETHICAL GUIDELINES:
- All exploits are for AUTHORIZED SECURITY TESTING and EDUCATION only
- Always mark outputs as proof-of-concept demonstrations
- Include responsible disclosure recommendations
- Never provide exploits for mass exploitation or illegal purposes

You support these vulnerability types:
- SQL Injection: Crafting malicious SQL payloads
- XSS (Cross-Site Scripting): Injecting malicious JavaScript
- Command Injection: Escaping to execute shell commands
- Path Traversal: Accessing files outside intended directories
- Authentication Bypass: Circumventing authentication mechanisms

When generating exploits, be specific and practical. Real exploits that demonstrate real risk.""",
    priorities=[
        "Vulnerability exploitation",
        "Proof-of-concept development",
        "Attack vector documentation",
        "Security testing",
        "Responsible disclosure"
    ],
    review_style="adversarial and thorough, thinking like an attacker"
)


class RedTeamAgent:
    """Agent that generates proof-of-concept exploits for identified vulnerabilities.

    This agent is designed for authorized security testing, penetration testing,
    CTF competitions, and educational purposes. All generated exploits are
    clearly marked as proof-of-concept demonstrations.
    """

    def __init__(self, session_id: Optional[str] = None):
        """Initialize the RedTeam agent.

        Args:
            session_id: Optional session ID for tracking
        """
        self.persona = RedTeamPersona
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = DEFAULT_MODEL
        self.max_tokens = MAX_TOKENS
        self.session_id = session_id or ""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)),
        reraise=True
    )
    def _call_api(self, system_prompt: str, user_message: str) -> str:
        """Make a Claude API call with retry logic.

        Args:
            system_prompt: The system prompt to use
            user_message: The user message/query

        Returns:
            The assistant's response text
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        return response.content[0].text

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from API response, handling markdown code blocks.

        Args:
            response: Raw API response string

        Returns:
            Parsed JSON dictionary
        """
        import re
        text = response.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Fix control characters inside JSON strings
        def fix_control_chars(match):
            s = match.group(0)
            s = s.replace('\n', '\\n')
            s = s.replace('\r', '\\r')
            s = s.replace('\t', '\\t')
            s = re.sub(r'[\x00-\x1f]', '', s)
            return s

        text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_control_chars, text)

        return json.loads(text)

    def _build_exploit_prompt(self, vulnerability_type: str) -> str:
        """Build the system prompt for exploit generation.

        Args:
            vulnerability_type: The type of vulnerability to exploit

        Returns:
            Complete system prompt string
        """
        vuln_instructions = {
            "sql_injection": """
For SQL Injection, create:
- A payload that extracts data (SELECT) or modifies data (UPDATE/DELETE)
- Show how to bypass authentication or extract sensitive data
- Include both error-based and blind injection techniques if applicable""",

            "xss": """
For XSS (Cross-Site Scripting), create:
- A payload that executes JavaScript in the victim's browser
- Show cookie theft, DOM manipulation, or phishing scenarios
- Include both reflected and stored XSS payloads if applicable""",

            "command_injection": """
For Command Injection, create:
- A payload that executes arbitrary shell commands
- Show command chaining techniques (;, |, &&, ||, backticks)
- Include payloads for different OS targets if applicable""",

            "path_traversal": """
For Path Traversal, create:
- A payload that accesses files outside the intended directory
- Show techniques to read sensitive files (/etc/passwd, config files)
- Include URL encoding and null byte techniques if applicable""",

            "auth_bypass": """
For Authentication Bypass, create:
- A technique to bypass login or access controls
- Show JWT manipulation, session fixation, or logic flaws
- Include default credentials or predictable tokens if applicable"""
        }

        base = self.persona.system_prompt
        specific = vuln_instructions.get(vulnerability_type, "")

        return f"""{base}

{specific}

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
    "exploit_code": "The complete exploit code or script",
    "payload": "The specific malicious payload",
    "curl_command": "A curl command to test (or 'N/A' if not applicable)",
    "explanation": "Detailed explanation of how this exploit works",
    "success_indicators": ["indicator1", "indicator2"]
}}

Mark all code as [PoC] proof-of-concept. This is for authorized security testing only."""

    def generate_exploit(
        self,
        code: str,
        vulnerability: str,
        context: Optional[str] = None
    ) -> ExploitResult:
        """Generate a proof-of-concept exploit for a vulnerability.

        This method creates a working exploit demonstration for authorized
        security testing purposes. All generated exploits are clearly marked
        as proof-of-concept and include responsible disclosure guidance.

        Args:
            code: The vulnerable code to analyze
            vulnerability: Type of vulnerability (sql_injection, xss,
                          command_injection, path_traversal, auth_bypass)
            context: Optional context about the code (endpoints, framework, etc.)

        Returns:
            ExploitResult containing the exploit code, payload, and explanation

        Raises:
            ValueError: If vulnerability type is not supported
        """
        # Validate vulnerability type
        vuln_lower = vulnerability.lower().replace("-", "_").replace(" ", "_")
        if vuln_lower not in VULNERABILITY_TYPES:
            raise ValueError(
                f"Unsupported vulnerability type: {vulnerability}. "
                f"Supported types: {', '.join(VULNERABILITY_TYPES)}"
            )

        system_prompt = self._build_exploit_prompt(vuln_lower)

        user_message = f"""[AUTHORIZED SECURITY TESTING]

Analyze this code for {vulnerability} vulnerability and generate a proof-of-concept exploit:

```
{code}
```
"""
        if context:
            user_message += f"\nAdditional context: {context}"

        user_message += """

Generate a working exploit that demonstrates this vulnerability.
This is for authorized penetration testing and security education only."""

        response = self._call_api(system_prompt, user_message)
        data = self._parse_json_response(response)

        # Build the result with safety markings
        return ExploitResult(
            vulnerability_type=vuln_lower,
            exploit_code=data.get("exploit_code", ""),
            payload=data.get("payload", ""),
            curl_command=data.get("curl_command", "N/A"),
            explanation=data.get("explanation", ""),
            success_indicators=data.get("success_indicators", []),
            poc_warning="[PoC ONLY] This exploit is for demonstration and authorized security testing only. Do not use against systems without explicit permission."
        )

    def _build_patch_prompt(self, vulnerability_type: str) -> str:
        """Build the system prompt for patch generation.

        Args:
            vulnerability_type: The type of vulnerability to patch

        Returns:
            Complete system prompt string
        """
        patch_instructions = {
            "sql_injection": """
For SQL Injection fixes:
- Use parameterized queries or prepared statements
- Never concatenate user input directly into SQL
- Use ORM methods where available
- Validate and sanitize input as defense in depth""",

            "xss": """
For XSS (Cross-Site Scripting) fixes:
- Escape HTML entities in output
- Use Content-Security-Policy headers
- Sanitize user input before storage and display
- Use framework auto-escaping features""",

            "command_injection": """
For Command Injection fixes:
- Use subprocess with list arguments (no shell=True)
- Validate input against allowlist
- Escape shell metacharacters if shell is required
- Consider using language-native alternatives to shell commands""",

            "path_traversal": """
For Path Traversal fixes:
- Use Path.resolve() and validate against base directory
- Reject paths containing .. or absolute paths
- Use os.path.basename for filenames only
- Implement allowlist of permitted directories""",

            "auth_bypass": """
For Authentication Bypass fixes:
- Use cryptographically secure session tokens
- Implement proper session validation
- Use constant-time comparison for secrets
- Add rate limiting and account lockout"""
        }

        specific = patch_instructions.get(vulnerability_type, "")

        return f"""You are a security engineer who specializes in fixing vulnerabilities.
Your mission is to create secure patches that fix vulnerabilities without breaking functionality.

When generating patches, you:
- Preserve the original functionality while removing the security flaw
- Follow secure coding best practices for the language
- Provide clear explanations of why the fix works
- Include verification tests to prove the vulnerability is fixed

{specific}

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
    "patched_code": "The complete fixed code",
    "diff": "Unified diff showing changes (use --- original and +++ patched)",
    "explanation": "Detailed explanation of the fix",
    "verification_test": "Python code or curl command to verify the fix works",
    "before_after": "Description showing exploit works before but fails after"
}}

Generate production-ready secure code."""

    def generate_patch(
        self,
        code: str,
        exploit: ExploitResult,
        context: Optional[str] = None
    ) -> PatchResult:
        """Generate a security patch for a vulnerability.

        Creates a patched version of the code that fixes the vulnerability
        demonstrated by the exploit, without breaking functionality.

        Args:
            code: The vulnerable code to patch
            exploit: The ExploitResult showing the vulnerability
            context: Optional context about the code

        Returns:
            PatchResult containing patched code, diff, and verification
        """
        system_prompt = self._build_patch_prompt(exploit.vulnerability_type)

        user_message = f"""Fix this vulnerability in the code.

VULNERABLE CODE:
```
{code}
```

VULNERABILITY TYPE: {exploit.vulnerability_type}

EXPLOIT THAT WORKS:
```
{exploit.exploit_code}
```

PAYLOAD: {exploit.payload}

HOW IT WORKS: {exploit.explanation}
"""
        if context:
            user_message += f"\nCONTEXT: {context}"

        user_message += """

Generate a secure patch that:
1. Fixes the vulnerability completely
2. Preserves original functionality
3. Follows security best practices
4. Includes verification that the exploit no longer works"""

        response = self._call_api(system_prompt, user_message)
        data = self._parse_json_response(response)

        return PatchResult(
            patched_code=data.get("patched_code", ""),
            diff=data.get("diff", ""),
            explanation=data.get("explanation", ""),
            verification_test=data.get("verification_test", ""),
            before_after=data.get("before_after", ""),
        )

    def __repr__(self) -> str:
        return f"RedTeamAgent(persona={self.persona.name})"
