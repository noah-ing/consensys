# Consensys

**Multi-agent AI code review with debate and voting.**

[![PyPI version](https://badge.fury.io/py/consensys-review.svg)](https://badge.fury.io/py/consensys-review)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Consensys brings together multiple AI experts to review your code, debate their findings, and reach a collective decision. Each expert has a unique perspective:

- **SecurityExpert** - Focuses on vulnerabilities, injection attacks, and security best practices
- **PerformanceEngineer** - Analyzes efficiency, optimization opportunities, and resource usage
- **ArchitectureCritic** - Evaluates design patterns, SOLID principles, and code structure
- **PragmaticDev** - Balances practicality with best practices, focuses on maintainability

## Quick Start

```bash
# Install
pip install consensys

# Set your API key
export ANTHROPIC_API_KEY="your-api-key"

# Review a file
consensys review myfile.py

# Quick review (faster, for pre-commit hooks)
consensys review myfile.py --quick

# Review with auto-fix suggestions
consensys review myfile.py --fix
```

## Features

- **Multi-agent debate** - AI experts discuss and challenge each other's findings
- **Consensys voting** - Final decision based on expert votes (APPROVE/REJECT/ABSTAIN)
- **Smart caching** - Avoid redundant API calls for unchanged code
- **Language detection** - Supports 14+ programming languages with context-aware prompts
- **CI/CD integration** - GitHub Action, pre-commit hooks, and fail-on thresholds
- **Rich output** - Beautiful terminal UI with syntax highlighting
- **Export options** - Markdown and HTML reports for documentation

## Installation

```bash
# From PyPI
pip install consensys

# With web UI support
pip install consensys[web]

# From source
git clone https://github.com/noah-ing/consensys.git
cd consensys
pip install -e .
```

## Usage

### Command Line

```bash
# Basic review
consensys review path/to/file.py

# Review inline code snippet
consensys review --code 'def foo(): pass'

# Quick mode (Round 1 only, ~3 seconds)
consensys review file.py --quick

# Stream AI thinking in real-time
consensys review file.py --stream

# CI mode: fail on HIGH severity or above
consensys review file.py --fail-on HIGH

# Only show MEDIUM+ severity issues
consensys review file.py --min-severity MEDIUM

# Review only changed lines (git diff)
consensys review file.py --diff-only

# Auto-fix based on review feedback
consensys review file.py --fix --output fixed.py
```

### Batch Review

```bash
# Review all Python files in a directory
consensys review-batch src/

# Parallel processing with 8 workers
consensys review-batch src/ --parallel 8

# Generate markdown report
consensys review-batch src/ --report report.md

# CI mode for batch review
consensys review-batch src/ --fail-on HIGH --quick
```

### Git Integration

```bash
# Review all uncommitted changes
consensys diff

# Review only staged changes (pre-commit)
consensys commit

# Review a GitHub PR
consensys pr 123

# Post review as PR comment
consensys pr 123 --post
```

### History and Replay

```bash
# List recent review sessions
consensys history

# Replay a past review
consensys replay abc123

# Export to markdown
consensys export abc123 --format md

# Export to HTML
consensys export abc123 --format html
```

## GitHub Action

Automatically review pull requests with Consensys.

### Basic Setup

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

### Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `api_key` | Anthropic API key | Yes | - |
| `fail_on` | Severity threshold to fail (LOW, MEDIUM, HIGH, CRITICAL) | No | `CRITICAL` |
| `min_severity` | Minimum severity to display | No | `LOW` |
| `quick_mode` | Use quick mode for faster reviews | No | `true` |
| `post_comment` | Post review summary as PR comment | No | `true` |
| `files` | Glob pattern for files to review | No | Changed files |
| `working_directory` | Working directory | No | `.` |

### Action Outputs

| Output | Description |
|--------|-------------|
| `decision` | Final consensus decision (APPROVE, REJECT, ABSTAIN) |
| `issues_count` | Total number of issues found |
| `session_id` | Review session ID for replay |
| `summary` | Review summary text |

### Advanced Workflow Example

```yaml
name: Consensys Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - '**.py'
      - '**.ts'
      - '**.go'

concurrency:
  group: consensys-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: noah-ing/consensys@v1
        id: review
        with:
          api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          fail_on: 'HIGH'
          min_severity: 'MEDIUM'
          quick_mode: 'true'
          post_comment: 'true'

      - name: Check review result
        if: steps.review.outputs.decision == 'REJECT'
        run: |
          echo "Code review failed with ${{ steps.review.outputs.issues_count }} issues"
          exit 1
```

### Self-Hosted Workflow

If you prefer to use the workflow file directly:

```yaml
# Copy .github/workflows/consensys-review.yml to your repo
# Set ANTHROPIC_API_KEY in repository secrets
```

## Configuration

### Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY="your-api-key"

# Optional
export CONSENSUS_MODEL="claude-3-5-haiku-20241022"
export CONSENSUS_CACHE_TTL="3600"
```

### Configuration Files

Create `.consensus.yaml` in your project root:

```yaml
# .consensus.yaml
default_team: full-review
min_severity: MEDIUM
cache_ttl: 3600
model: claude-3-5-haiku-20241022
fail_on: HIGH
quick_mode: false
```

Or user-level config at `~/.consensus/config.yaml`.

```bash
# Initialize config
consensys config init --project
consensys config init --user

# View current config
consensys config show
```

### Team Configuration

```bash
# Use a preset team
consensys set-team --preset security-focused
consensys set-team --preset quick-check

# Custom team
consensys set-team SecurityExpert PragmaticDev

# Create custom persona
consensys add-persona

# List available teams
consensys teams
```

#### Available Presets

| Preset | Description | Personas |
|--------|-------------|----------|
| `full-review` | Complete 4-agent review | All 4 experts |
| `security-focused` | Security-centric review | SecurityExpert, ArchitectureCritic |
| `performance-focused` | Performance-centric review | PerformanceEngineer, PragmaticDev |
| `quick-check` | Fast 2-agent review | SecurityExpert, PragmaticDev |

## Pre-commit Hook

Integrate Consensys with the [pre-commit](https://pre-commit.com) framework for automatic code review on every commit.

### Basic Setup

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.1.0
    hooks:
      - id: consensys-review
```

### Available Hooks

| Hook ID | Description | Default Behavior |
|---------|-------------|------------------|
| `consensys-review` | Quick AI code review | Python files, warn on issues |
| `consensys-review-strict` | Strict mode | Fails on HIGH severity or above |
| `consensys-review-all` | Multi-language | Python, JS, TS, Go, Rust, Java, etc. |

### Configuration Examples

**Quick review (default):**
```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.1.0
    hooks:
      - id: consensys-review
```

**Strict mode - fail on HIGH severity:**
```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.1.0
    hooks:
      - id: consensys-review-strict
```

**Custom severity threshold:**
```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.1.0
    hooks:
      - id: consensys-review
        args: ['--fail-on', 'CRITICAL']
```

**Only specific files:**
```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.1.0
    hooks:
      - id: consensys-review
        files: ^src/
```

**Multiple languages:**
```yaml
repos:
  - repo: https://github.com/noah-ing/consensys
    rev: v0.1.0
    hooks:
      - id: consensys-review-all
        args: ['--fail-on', 'HIGH']
```

### Running Manually

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run on all files
pre-commit run --all-files

# Run on staged files
pre-commit run consensys-review

# Test from repo
pre-commit try-repo . consensys-review --files myfile.py
```

### Hook Arguments

The hooks accept any arguments supported by `consensys review`:

| Argument | Description |
|----------|-------------|
| `--fail-on SEVERITY` | Exit 1 if issues at SEVERITY or above (LOW, MEDIUM, HIGH, CRITICAL) |
| `--min-severity SEVERITY` | Only show issues at SEVERITY or above |
| `--no-cache` | Force fresh review, bypass cache |

### Environment Setup

Ensure your `ANTHROPIC_API_KEY` is set:

```bash
# In your shell profile (.bashrc, .zshrc, etc.)
export ANTHROPIC_API_KEY="your-api-key"
```

For CI environments, add the key to your secrets manager.

## API Usage

Use Consensys programmatically:

```python
from consensys import DebateOrchestrator
from consensys.personas import PERSONAS

# Create orchestrator
orchestrator = DebateOrchestrator(personas=PERSONAS)

# Run review
code = '''
def process_user_input(data):
    return eval(data)  # Security issue!
'''

consensus = orchestrator.run_full_debate(code, context="User input handler")

print(f"Decision: {consensus.final_decision}")
print(f"Key Issues: {consensus.key_issues}")
```

## Web UI

Consensys includes a web-based interface for code reviews with real-time streaming.

### Starting the Server

```bash
# Start web server on default port 8000
consensys web

# Custom host and port
consensys web --host 0.0.0.0 --port 3000
```

Open `http://localhost:8000` in your browser.

### Web API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check - returns `{"status": "ok"}` |
| `/api/review` | POST | Submit code for review |
| `/api/sessions` | GET | List past review sessions |
| `/api/sessions/{id}` | GET | Get full session details |
| `/ws/review` | WebSocket | Streaming reviews with live updates |

### POST /api/review

Submit code for AI review:

```bash
curl -X POST http://localhost:8000/api/review \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def foo(): eval(input())",
    "context": "User input handler",
    "language": "python",
    "quick": false
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Code to review |
| `context` | string | No | Additional context for reviewers |
| `language` | string | No | Programming language hint |
| `quick` | boolean | No | Use quick mode (default: false) |

**Response:**

```json
{
  "session_id": "abc123...",
  "decision": "REJECT",
  "reviews": [
    {
      "agent_name": "SecurityExpert",
      "issues": ["eval() with user input is dangerous"],
      "suggestions": ["Use ast.literal_eval() for safe parsing"],
      "severity": "CRITICAL",
      "confidence": 0.95,
      "summary": "Critical security vulnerability detected"
    }
  ],
  "consensus": {
    "decision": "REJECT",
    "vote_counts": {"APPROVE": 0, "REJECT": 4, "ABSTAIN": 0},
    "key_issues": ["Code injection vulnerability via eval()"],
    "accepted_suggestions": ["Replace eval() with safe alternative"]
  },
  "vote_counts": {"APPROVE": 0, "REJECT": 4, "ABSTAIN": 0}
}
```

### GET /api/sessions

List past review sessions:

```bash
curl http://localhost:8000/api/sessions?limit=10
```

### GET /api/sessions/{id}

Get full details of a session:

```bash
curl http://localhost:8000/api/sessions/abc123
```

### WebSocket /ws/review

For real-time streaming reviews, connect via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/review');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'review',
    code: 'def foo(): pass',
    context: 'Example function',
    quick: false
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  // message.type: 'status' | 'review' | 'response' | 'vote' | 'consensus' | 'complete' | 'error'
  console.log(message.type, message.data);
};
```

## VS Code Extension

Review code directly in your editor with the Consensys VS Code extension.

### Installation

```bash
# Clone and build from source
cd vscode-extension
npm install
npm run package

# Install the generated .vsix file in VS Code
# Extensions > ... > Install from VSIX...
```

### Prerequisites

The extension requires the Consensys web server running:

```bash
consensys web  # Starts on http://localhost:8000
```

### Features

- **Review Current File**: `Ctrl+Shift+R` (Mac: `Cmd+Shift+R`)
- **Review Selection**: `Ctrl+Shift+Alt+R` (Mac: `Cmd+Shift+Alt+R`)
- **Diagnostic Integration**: Issues appear in Problems panel and as editor squiggles
- **Code Actions**: Quick fix suggestions via lightbulb menu
- **Status Bar**: Real-time review status indicator
- **Auto-Review on Save**: Configurable automatic reviews

### Extension Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `consensus.apiEndpoint` | URL of Consensys web API | `http://localhost:8000` |
| `consensus.autoReviewOnSave` | Review files automatically on save | `false` |

### Status Bar Icons

| Icon | Meaning |
|------|---------|
| Shield | Ready to review (click to start) |
| Spinning | Review in progress |
| Check | Review passed |
| Warning | Warnings found |
| Error | Errors found |

### Context Menu

Right-click in the editor to access:
- **Consensys: Review Current File**
- **Consensys: Review Selection**

## Docker

Deploy Consensys as a containerized web service.

### Quick Start

```bash
# Build the image
docker build -t consensys .

# Run with API key
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your-key consensys
```

### Docker Compose

For persistent storage and easier management:

```yaml
# docker-compose.yml
version: "3.8"

services:
  consensys:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - consensys-data:/app/data
    restart: unless-stopped

volumes:
  consensys-data:
```

```bash
# Start with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Yes |
| `CONSENSUS_DATA_DIR` | Data directory for SQLite | No (default: `/app/data`) |

### Health Check

The container includes a health check that pings `/api/health`:

```bash
docker inspect --format='{{.State.Health.Status}}' consensys-web
```

### Production Deployment

For production, consider:

1. **Reverse proxy**: Use nginx or Traefik for SSL termination
2. **Resource limits**: Set memory and CPU limits in docker-compose
3. **Logging**: Configure log aggregation (e.g., to CloudWatch, Datadog)
4. **Secrets**: Use Docker secrets or environment variable injection

Example with resource limits:

```yaml
services:
  consensys:
    build: .
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Metrics and Cost Tracking

```bash
# View API usage and costs
consensys metrics

# Weekly breakdown
consensys metrics --period weekly

# Set budget alert
consensys metrics --budget 10.00
```

## Supported Languages

Consensys provides language-specific review hints for:

- Python, JavaScript, TypeScript
- Go, Rust, Java
- C, C++, C#
- Ruby, PHP
- Swift, Kotlin, Scala

## Examples

The `examples/` directory contains sample files to help you get started:

### Demo Files

| File | Description |
|------|-------------|
| [`vulnerable.py`](examples/vulnerable.py) | Code with common security vulnerabilities (SQL injection, command injection, etc.) |
| [`clean.py`](examples/clean.py) | Well-written, secure code demonstrating best practices |
| [`review-demo.sh`](examples/review-demo.sh) | Shell script showcasing CLI usage patterns |
| [`github-workflow.yml`](examples/github-workflow.yml) | Complete GitHub Actions workflow example |
| [`.consensus.yaml`](examples/.consensus.yaml) | Example configuration file with all options |

### Try the Demo

```bash
# Clone the repository
git clone https://github.com/noah-ing/consensys.git
cd consensys

# Install
pip install -e .
export ANTHROPIC_API_KEY="your-api-key"

# Review vulnerable code (will find issues)
consensys review examples/vulnerable.py --quick

# Review clean code (should pass)
consensys review examples/clean.py --quick

# Run the full demo script
./examples/review-demo.sh
```

### Vulnerable Code Example

The `vulnerable.py` file demonstrates 12 common security issues:

1. **SQL Injection** - Direct string interpolation in queries
2. **Command Injection** - User input in shell commands
3. **Insecure Deserialization** - Pickle loading untrusted data
4. **Hardcoded Secrets** - Credentials in source code
5. **Path Traversal** - Unvalidated file paths
6. **Weak Random** - Non-cryptographic random for tokens
7. **Missing Validation** - No input sanitization
8. **Eval Injection** - eval() on user input
9. **XXE Vulnerability** - Unsafe XML parsing
10. **Weak Cryptography** - MD5 without salt
11. **Race Conditions** - TOCTOU in bank account
12. **Sensitive Data Logging** - Card numbers in logs

Run Consensys to see how the AI agents identify each issue:

```bash
consensys review examples/vulnerable.py
```

### Clean Code Example

The `clean.py` file shows the secure alternatives:

- Parameterized SQL queries
- Subprocess with list arguments
- JSON instead of pickle
- Environment variables for secrets
- Path validation with resolve()
- secrets module for tokens
- Input validation with dataclasses
- Operator whitelist instead of eval
- PBKDF2 password hashing
- Thread-safe locking

### Configuration Example

Copy the example config to your project:

```bash
# Project-level config
cp examples/.consensus.yaml .consensus.yaml

# User-level config
mkdir -p ~/.consensus
cp examples/.consensus.yaml ~/.consensus/config.yaml
```

The config file includes:
- Team presets and custom persona definitions
- Severity thresholds and fail-on settings
- Language-specific review hints
- Ignore patterns for batch reviews
- API settings (timeout, retries)
- Budget alerts

### GitHub Workflow Example

Copy the workflow to enable PR reviews:

```bash
mkdir -p .github/workflows
cp examples/github-workflow.yml .github/workflows/consensys.yml
```

Add `ANTHROPIC_API_KEY` to your repository secrets, and Consensys will automatically review pull requests.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

---

Built with Claude by Anthropic
