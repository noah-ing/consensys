# Contributing to Consensus

Thank you for your interest in contributing to Consensus! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful and constructive. We're all here to build something great together.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Node.js 18+ (for VS Code extension)
- An Anthropic API key

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/consensus-review/consensus.git
   cd consensus
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode:**
   ```bash
   pip install -e ".[dev,web]"
   ```

4. **Set up your API key:**
   ```bash
   export ANTHROPIC_API_KEY="your-api-key"
   ```

5. **Run tests:**
   ```bash
   pytest tests/
   ```

## Project Structure

```
consensus/
├── src/
│   ├── agents/         # AI agent personas and Claude API wrapper
│   ├── db/             # SQLite storage layer
│   ├── export/         # Markdown/HTML export
│   ├── git/            # Git integration helpers
│   ├── models/         # Data models (Review, Vote, Consensus)
│   ├── orchestrator/   # Multi-agent debate coordinator
│   ├── personas/       # Custom personas and teams
│   ├── web/            # FastAPI web server
│   ├── cli.py          # Click CLI commands
│   ├── cache.py        # Review caching
│   ├── config.py       # Configuration loading
│   ├── languages.py    # Language detection
│   ├── metrics.py      # API usage tracking
│   └── settings.py     # Config file handling
├── tests/              # Pytest test suite
├── vscode-extension/   # VS Code extension
├── examples/           # Example code and configs
└── .github/            # GitHub Actions workflows
```

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in GitHub Issues
2. Create a new issue with:
   - Clear title describing the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment info (Python version, OS)

### Suggesting Features

1. Open a GitHub Issue with the `enhancement` label
2. Describe the feature and its use case
3. Discuss the implementation approach

### Submitting Code

1. **Fork the repository**

2. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes:**
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Run the test suite:**
   ```bash
   pytest tests/
   ```

5. **Commit with a clear message:**
   ```bash
   git commit -m "feat: Add new feature description"
   ```

6. **Push and create a Pull Request:**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

### Python

- Use type hints for function signatures
- Follow PEP 8 conventions
- Use dataclasses for structured data
- Keep functions focused and small
- Add docstrings for public functions

Example:
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ReviewResult:
    """Result of a code review."""
    issues: List[str]
    severity: str
    confidence: float
    summary: Optional[str] = None

def analyze_code(code: str, context: str = "") -> ReviewResult:
    """Analyze code for potential issues.

    Args:
        code: The source code to analyze
        context: Optional context about the code

    Returns:
        ReviewResult with issues and severity
    """
    # Implementation
    pass
```

### TypeScript (VS Code Extension)

- Use TypeScript strict mode
- Prefer async/await over callbacks
- Document public APIs with JSDoc

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_agents.py

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Writing Tests

- Use pytest fixtures for shared setup
- Mock external API calls (Anthropic API)
- Test both success and error cases

Example:
```python
import pytest
from unittest.mock import patch

def test_review_detects_issues(mock_anthropic):
    """Test that reviews correctly identify security issues."""
    with patch('src.agents.agent.Anthropic') as mock:
        mock.return_value.messages.create.return_value = mock_response

        agent = Agent(SecurityExpert)
        result = agent.review("eval(input())")

        assert "CRITICAL" in result.severity
        assert len(result.issues) > 0
```

## Pull Request Guidelines

1. **Title**: Use conventional commit format
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation
   - `test:` Tests
   - `refactor:` Code refactoring

2. **Description**: Include:
   - What changes were made
   - Why the changes are needed
   - How to test the changes

3. **Size**: Keep PRs focused and reviewable
   - One feature per PR
   - Split large changes into multiple PRs

4. **Tests**: All tests must pass

5. **Documentation**: Update docs for user-facing changes

## VS Code Extension Development

### Setup

```bash
cd vscode-extension
npm install
npm run compile
```

### Testing

```bash
# Open in VS Code
code .

# Press F5 to launch Extension Development Host
```

### Building

```bash
npm run package  # Creates .vsix file
```

## Release Process

1. Update version in `pyproject.toml` and `src/__init__.py`
2. Update CHANGELOG.md
3. Create a git tag: `git tag v0.x.x`
4. Push tag: `git push --tags`
5. GitHub Actions will build and publish

## Getting Help

- Open a GitHub Issue for bugs or questions
- Join discussions in GitHub Discussions
- Check existing issues and PRs for context

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Consensus!
