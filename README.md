# Consensys

**Multi-agent AI code review with debate and voting.**

[![PyPI version](https://badge.fury.io/py/consensys.svg)](https://badge.fury.io/py/consensys)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Four AI experts review your code, debate their findings, and vote on the outcome:

- **SecurityExpert** - Vulnerabilities, injection attacks, security best practices
- **PerformanceEngineer** - Efficiency, optimization, resource usage
- **ArchitectureCritic** - Design patterns, SOLID principles, code structure
- **PragmaticDev** - Maintainability, practicality, real-world tradeoffs

## Installation

```bash
# From PyPI
pip install consensys

# With web UI support (quotes required for zsh)
pip install 'consensys[web]'

# From source
git clone https://github.com/noah-ing/consensys.git
cd consensys
pip install -e .
```

## Quick Start

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-api-key"

# Review a file
consensys review myfile.py

# Quick mode (faster, single round)
consensys review myfile.py --quick

# Review with auto-fix suggestions
consensys review myfile.py --fix

# Stream AI thinking in real-time
consensys review file.py --stream

# CI mode: fail on HIGH severity or above
consensys review file.py --fail-on HIGH
```

## Features

- **Multi-agent debate** - AI experts discuss and challenge each other's findings
- **Consensus voting** - Final decision based on expert votes (APPROVE/REJECT/ABSTAIN)
- **Smart caching** - Avoid redundant API calls for unchanged code
- **14+ languages** - Python, JS, TS, Go, Rust, Java, C, C++, Ruby, PHP, Swift, Kotlin, Scala
- **CI/CD integration** - GitHub Action, pre-commit hooks, fail-on thresholds
- **Export options** - Markdown and HTML reports
- **RedTeam mode** - Generate PoC exploits and auto-patches for vulnerabilities
- **Prediction market** - Agents bet tokens on code quality outcomes
- **Code DNA** - Extract codebase style patterns and detect anomalies

## CLI Reference

```bash
# Review a file
consensys review path/to/file.py

# Review inline code snippet
consensys review --code 'def foo(): pass'

# Batch review directory
consensys review-batch src/
consensys review-batch src/ --lang python --parallel 8

# Git integration
consensys diff                  # Review uncommitted changes
consensys commit                # Review staged changes
consensys pr 123                # Review GitHub PR
consensys pr 123 --post         # Post as PR comment

# History
consensys history               # List past sessions
consensys replay abc123         # Replay a review
consensys export abc123 --format md

# Advanced modes
consensys review file.py --redteam    # Generate exploits + patches
consensys review file.py --predict    # Enable prediction market
consensys review file.py --dna        # Check against codebase style
consensys fingerprint src/            # Extract style fingerprint

# Metrics
consensys metrics               # View API usage and costs
```

## Web UI

```bash
# Start the web server
consensys web

# Custom host/port
consensys web --host 0.0.0.0 --port 3000
```

Open `http://localhost:8080` in your browser for real-time streaming reviews.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/review` | POST | Submit code for review |
| `/api/sessions` | GET | List past sessions |
| `/api/sessions/{id}` | GET | Get session details |
| `/ws/review` | WebSocket | Streaming reviews |

```bash
curl -X POST http://localhost:8080/api/review \
  -H "Content-Type: application/json" \
  -d '{"code": "def foo(): eval(input())", "language": "python"}'
```

## GitHub Action

Add to `.github/workflows/consensys.yml`:

```yaml
name: Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: noah-ing/consensys@v1
        with:
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          fail_on: 'HIGH'
          min_severity: 'MEDIUM'
```

**Inputs:** `api_key` (required), `fail_on`, `min_severity`, `quick_mode`, `post_comment`, `files`

**Outputs:** `decision`, `issues_count`, `session_id`, `summary`

## Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.2.1
    hooks:
      - id: consensys-review           # Quick review
      # - id: consensys-review-strict  # Fail on HIGH
      # - id: consensys-review-all     # All languages
```

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Configuration

### Environment Variables

```bash
export ANTHROPIC_API_KEY="your-api-key"
export CONSENSYS_MODEL="claude-3-5-haiku-20241022"
```

### Config File

Create `.consensys.yaml` in your project root:

```yaml
model: claude-3-5-haiku-20241022
min_severity: MEDIUM
fail_on: HIGH
quick_mode: false
default_team: full-review
```

### Team Presets

```bash
consensys set-team --preset security-focused   # SecurityExpert + ArchitectureCritic
consensys set-team --preset quick-check        # SecurityExpert + PragmaticDev
consensys set-team SecurityExpert PragmaticDev # Custom team
```

## Python API

```python
from consensys import DebateOrchestrator
from consensys.personas import PERSONAS

orchestrator = DebateOrchestrator(personas=PERSONAS)
result = orchestrator.run_full_debate(code, context="User input handler")

print(result.final_decision)  # APPROVE, REJECT, or ABSTAIN
print(result.key_issues)
```

## Docker

```bash
# Build and run
docker build -t consensys .
docker run -p 8080:8080 -e ANTHROPIC_API_KEY=your-key consensys
```

Docker Compose:

```yaml
version: "3.8"
services:
  consensys:
    build: .
    ports:
      - "8080:8080"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - consensys-data:/app/data
volumes:
  consensys-data:
```

## RedTeam Mode

Generate proof-of-concept exploits and auto-patches for security vulnerabilities:

```bash
consensys review vulnerable.py --redteam
```

Supports SQL injection, XSS, command injection, path traversal, and auth bypass. All exploits are marked for authorized testing only.

## Prediction Market

Agents bet tokens on code quality predictions. Track accuracy over time:

```bash
consensys review file.py --predict
consensys predict list
consensys predict resolve abc123 --outcome safe
consensys predict leaderboard
```

## Code DNA

Extract codebase style patterns and detect anomalies in new code:

```bash
consensys fingerprint src/           # Extract patterns
consensys review file.py --dna       # Check against patterns
```

Detects naming convention violations, missing type hints, docstring drift, import style differences, and copy-paste indicators.

## Examples

The `examples/` directory contains:

- `vulnerable.py` - 12 common security vulnerabilities
- `clean.py` - Secure alternatives and best practices
- `review-demo.sh` - CLI usage patterns
- `.consensys.yaml` - Example configuration

```bash
# Try it
consensys review examples/vulnerable.py --quick
consensys review examples/clean.py --quick
```

## VS Code Extension

See `vscode-extension/README.md` for the VS Code integration.

## License

MIT

## Contributing

Contributions welcome! Open an issue or submit a PR.

---

Built with Claude by Anthropic
