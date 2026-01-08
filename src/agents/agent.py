"""Agent wrapper for Claude API calls with persona-based system prompts."""
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MAX_TOKENS
from src.agents.personas import Persona
from src.models.review import VoteDecision
from src.languages import LanguageInfo, get_language_prompt_hints, GENERIC
from src.metrics import record_api_call


@dataclass
class ReviewResult:
    """Structured result from a code review."""
    agent_name: str
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "LOW"  # CRITICAL, HIGH, MEDIUM, LOW
    confidence: float = 0.8
    summary: str = ""


@dataclass
class ResponseResult:
    """Structured response to another agent's review."""
    agent_name: str
    responding_to: str
    agreement_level: str = "PARTIAL"  # AGREE, PARTIAL, DISAGREE
    points: List[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class VoteResult:
    """Structured vote on code quality."""
    agent_name: str
    decision: VoteDecision = VoteDecision.ABSTAIN
    reasoning: str = ""


class Agent:
    """Wraps Claude API calls with a specific persona's system prompt."""

    def __init__(self, persona: Persona, session_id: Optional[str] = None):
        """Initialize agent with a persona.

        Args:
            persona: The persona defining this agent's behavior and focus
            session_id: Optional session ID for metrics tracking
        """
        self.persona = persona
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = DEFAULT_MODEL
        self.max_tokens = MAX_TOKENS
        self.session_id = session_id or ""

    def _build_system_prompt(self, task_type: str, language: Optional[LanguageInfo] = None) -> str:
        """Build a complete system prompt for a specific task.

        Args:
            task_type: One of 'review', 'respond', or 'vote'
            language: Optional language info for language-specific hints

        Returns:
            Complete system prompt string
        """
        base = self.persona.system_prompt

        task_instructions = {
            "review": """
When reviewing code, provide your analysis in the following JSON format:
{
    "issues": [{"description": "...", "severity": "CRITICAL|HIGH|MEDIUM|LOW", "line": null}],
    "suggestions": ["suggestion 1", "suggestion 2"],
    "severity": "CRITICAL|HIGH|MEDIUM|LOW",
    "confidence": 0.0-1.0,
    "summary": "Brief overall assessment"
}

Be thorough but fair. Only report real issues, not style preferences unless they impact readability.""",

            "respond": """
When responding to another reviewer's points, provide your response in JSON format:
{
    "agreement_level": "AGREE|PARTIAL|DISAGREE",
    "points": ["point 1", "point 2"],
    "summary": "Brief summary of your position"
}

Be constructive. If you agree, say so. If you disagree, explain why with evidence.""",

            "vote": """
When voting on code, provide your vote in JSON format:
{
    "decision": "APPROVE|REJECT|ABSTAIN",
    "reasoning": "Detailed explanation of your vote"
}

APPROVE: Code is good to merge (minor issues acceptable)
REJECT: Code has significant issues that must be fixed
ABSTAIN: You don't have enough context or expertise to judge"""
        }

        # Add language-specific hints for review tasks
        language_hints = ""
        if task_type == "review" and language and language.name != "text":
            language_hints = get_language_prompt_hints(language)

        return f"""{base}

Review style: {self.persona.review_style}
Your priorities: {', '.join(self.persona.priorities)}
{language_hints}

{task_instructions.get(task_type, '')}

IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation outside the JSON."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)),
        reraise=True
    )
    def _call_api(self, system_prompt: str, user_message: str, operation: str = "review") -> str:
        """Make a Claude API call with retry logic and metrics tracking.

        Args:
            system_prompt: The system prompt to use
            user_message: The user message/query
            operation: The type of operation (review, respond, vote, fix)

        Returns:
            The assistant's response text
        """
        start_time = time.time()

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        # Record metrics
        duration_ms = int((time.time() - start_time) * 1000)
        if self.session_id and hasattr(response, 'usage'):
            record_api_call(
                session_id=self.session_id,
                agent_name=self.persona.name,
                model=self.model,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                duration_ms=duration_ms,
                operation=operation,
            )

        return response.content[0].text

    def _call_api_streaming(
        self,
        system_prompt: str,
        user_message: str,
        on_token: Optional[callable] = None,
        operation: str = "review"
    ) -> str:
        """Make a streaming Claude API call with metrics tracking.

        Args:
            system_prompt: The system prompt to use
            user_message: The user message/query
            on_token: Callback function called with each token
            operation: The type of operation (review, respond, vote, fix)

        Returns:
            The complete response text
        """
        start_time = time.time()
        full_response = []

        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        ) as stream:
            for text in stream.text_stream:
                full_response.append(text)
                if on_token:
                    on_token(text)

            # Get final message for usage stats
            final_message = stream.get_final_message()

        # Record metrics
        duration_ms = int((time.time() - start_time) * 1000)
        if self.session_id and hasattr(final_message, 'usage'):
            record_api_call(
                session_id=self.session_id,
                agent_name=self.persona.name,
                model=self.model,
                tokens_in=final_message.usage.input_tokens,
                tokens_out=final_message.usage.output_tokens,
                duration_ms=duration_ms,
                operation=operation,
            )

        return "".join(full_response)

    def review_streaming(
        self,
        code: str,
        context: Optional[str] = None,
        on_token: Optional[callable] = None,
        language: Optional[LanguageInfo] = None
    ) -> ReviewResult:
        """Review code with streaming output.

        Args:
            code: The code to review
            context: Optional context about the code
            on_token: Callback for streaming tokens
            language: Optional language info for language-specific hints

        Returns:
            ReviewResult with issues, suggestions, and overall assessment
        """
        system_prompt = self._build_system_prompt("review", language=language)

        user_message = f"Please review the following code:\n\n```\n{code}\n```"
        if context:
            user_message = f"Context: {context}\n\n{user_message}"

        response = self._call_api_streaming(system_prompt, user_message, on_token)
        data = self._parse_json_response(response)

        return ReviewResult(
            agent_name=self.persona.name,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            severity=data.get("severity", "LOW"),
            confidence=data.get("confidence", 0.8),
            summary=data.get("summary", "")
        )

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from API response, handling markdown code blocks.

        Args:
            response: Raw API response string

        Returns:
            Parsed JSON dictionary
        """
        text = response.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Fix control characters inside JSON strings
        # Replace actual newlines/tabs inside strings with escaped versions
        import re

        def fix_control_chars(match):
            """Escape control characters inside JSON string values."""
            s = match.group(0)
            s = s.replace('\n', '\\n')
            s = s.replace('\r', '\\r')
            s = s.replace('\t', '\\t')
            # Remove other control characters
            s = re.sub(r'[\x00-\x1f]', '', s)
            return s

        # Match JSON string values and fix control chars within them
        text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_control_chars, text)

        return json.loads(text)

    def review(self, code: str, context: Optional[str] = None, language: Optional[LanguageInfo] = None) -> ReviewResult:
        """Review code and return structured feedback.

        Args:
            code: The code to review
            context: Optional context about the code (purpose, file name, etc.)
            language: Optional language info for language-specific hints

        Returns:
            ReviewResult with issues, suggestions, and overall assessment
        """
        system_prompt = self._build_system_prompt("review", language=language)

        user_message = f"Please review the following code:\n\n```\n{code}\n```"
        if context:
            user_message = f"Context: {context}\n\n{user_message}"

        response = self._call_api(system_prompt, user_message)
        data = self._parse_json_response(response)

        return ReviewResult(
            agent_name=self.persona.name,
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            severity=data.get("severity", "LOW"),
            confidence=data.get("confidence", 0.8),
            summary=data.get("summary", "")
        )

    def respond_to(self, other_review: ReviewResult, original_code: str) -> ResponseResult:
        """Respond to another agent's review.

        Args:
            other_review: The review to respond to
            original_code: The original code being reviewed

        Returns:
            ResponseResult with agreement level and response points
        """
        system_prompt = self._build_system_prompt("respond")

        # Format the other review for context
        review_summary = f"""
{other_review.agent_name}'s Review:
- Severity: {other_review.severity}
- Confidence: {other_review.confidence}
- Issues: {json.dumps(other_review.issues, indent=2)}
- Suggestions: {json.dumps(other_review.suggestions, indent=2)}
- Summary: {other_review.summary}
"""

        user_message = f"""Original code:
```
{original_code}
```

{review_summary}

Please respond to {other_review.agent_name}'s review above. Do you agree with their assessment? What would you add or challenge?"""

        response = self._call_api(system_prompt, user_message, operation="respond")
        data = self._parse_json_response(response)

        return ResponseResult(
            agent_name=self.persona.name,
            responding_to=other_review.agent_name,
            agreement_level=data.get("agreement_level", "PARTIAL"),
            points=data.get("points", []),
            summary=data.get("summary", "")
        )

    def vote(self, code: str, reviews: List[ReviewResult], responses: Optional[List[ResponseResult]] = None) -> VoteResult:
        """Vote on whether code should be approved.

        Args:
            code: The code being voted on
            reviews: All reviews from the debate
            responses: Optional responses from the debate round

        Returns:
            VoteResult with decision and reasoning
        """
        system_prompt = self._build_system_prompt("vote")

        # Build summary of the debate
        debate_summary = "Reviews:\n"
        for review in reviews:
            debate_summary += f"\n{review.agent_name} ({review.severity}):\n"
            debate_summary += f"  Summary: {review.summary}\n"
            if review.issues:
                debate_summary += f"  Issues: {len(review.issues)} found\n"

        if responses:
            debate_summary += "\n\nDebate Responses:\n"
            for resp in responses:
                debate_summary += f"\n{resp.agent_name} -> {resp.responding_to}: {resp.agreement_level}\n"
                debate_summary += f"  {resp.summary}\n"

        user_message = f"""Code under review:
```
{code}
```

{debate_summary}

Based on the code and the debate above, cast your vote. Consider all perspectives but make your own judgment based on your expertise and priorities."""

        response = self._call_api(system_prompt, user_message, operation="vote")
        data = self._parse_json_response(response)

        decision_str = data.get("decision", "ABSTAIN").upper()
        try:
            decision = VoteDecision(decision_str)
        except ValueError:
            decision = VoteDecision.ABSTAIN

        return VoteResult(
            agent_name=self.persona.name,
            decision=decision,
            reasoning=data.get("reasoning", "")
        )

    def __repr__(self) -> str:
        return f"Agent(persona={self.persona.name})"


@dataclass
class FixResult:
    """Result of code fix operation."""
    original_code: str
    fixed_code: str
    changes_made: List[str]
    explanation: str


class CodeFixer:
    """Fixes code based on consensus review feedback."""

    def __init__(self, session_id: Optional[str] = None):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = DEFAULT_MODEL
        self.max_tokens = 4096  # More tokens for code output
        self.session_id = session_id or ""

    def fix_code(
        self,
        code: str,
        issues: List[Dict[str, Any]],
        suggestions: List[str],
        context: Optional[str] = None
    ) -> FixResult:
        """Fix code based on review feedback.

        Args:
            code: The original code to fix
            issues: List of issues found in review
            suggestions: List of improvement suggestions
            context: Optional context about the code

        Returns:
            FixResult with fixed code and explanation
        """
        system_prompt = """You are an expert code fixer. Rewrite code to fix all identified issues.

RESPOND ONLY WITH VALID JSON. Use \\n for newlines in code. Example:
{"fixed_code": "def foo():\\n    return bar", "changes_made": ["Fixed X"], "explanation": "Brief explanation"}

Rules:
1. Fix ALL identified issues
2. Maintain original functionality
3. Use best practices
4. Use \\n for newlines in the fixed_code string"""

        issues_text = "\n".join([
            f"- {issue.get('description', str(issue))} (severity: {issue.get('severity', 'unknown')})"
            for issue in issues
        ])
        suggestions_text = "\n".join([f"- {s}" for s in suggestions])

        user_message = f"""Fix this code based on the review feedback:

## Original Code
```
{code}
```

## Issues Found
{issues_text}

## Suggestions
{suggestions_text}
"""
        if context:
            user_message = f"Context: {context}\n\n{user_message}"

        start_time = time.time()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        # Record metrics
        duration_ms = int((time.time() - start_time) * 1000)
        if self.session_id and hasattr(response, 'usage'):
            record_api_call(
                session_id=self.session_id,
                agent_name="CodeFixer",
                model=self.model,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                duration_ms=duration_ms,
                operation="fix",
            )

        text = response.content[0].text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        # Fix control characters
        import re
        def fix_ctrl(m):
            s = m.group(0)
            s = s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
            s = re.sub(r'[\x00-\x1f]', '', s)
            return s
        text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_ctrl, text)

        data = json.loads(text)

        # Unescape the fixed code
        fixed_code = data.get("fixed_code", code)
        fixed_code = fixed_code.replace('\\n', '\n').replace('\\t', '\t')

        return FixResult(
            original_code=code,
            fixed_code=fixed_code,
            changes_made=data.get("changes_made", []),
            explanation=data.get("explanation", "")
        )
