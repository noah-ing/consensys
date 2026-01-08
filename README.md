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
- **RedTeam mode** - Generate proof-of-concept exploits and auto-patches for vulnerabilities
- **Prediction market** - Agents bet tokens on code quality outcomes, track accuracy over time
- **Code DNA fingerprinting** - Extract codebase style patterns and detect anomalies

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
export CONSENSYS_MODEL="claude-3-5-haiku-20241022"
export CONSENSYS_CACHE_TTL="3600"
```

### Configuration Files

Create `.consensys.yaml` in your project root:

```yaml
# .consensys.yaml
default_team: full-review
min_severity: MEDIUM
cache_ttl: 3600
model: claude-3-5-haiku-20241022
fail_on: HIGH
quick_mode: false
```

Or user-level config at `~/.consensys/config.yaml`.

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
| `CONSENSYS_DATA_DIR` | Data directory for SQLite | No (default: `/app/data`) |

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

## RedTeam Mode

Generate proof-of-concept exploits and auto-patches for security vulnerabilities found during review.

### Basic Usage

```bash
# Review with exploit generation
consensys review vulnerable.py --redteam

# Combine with quick mode for faster results
consensys review vulnerable.py --redteam --quick
```

### How It Works

1. Standard review identifies security issues
2. RedTeam agent generates PoC exploits for each vulnerability
3. Auto-patch generator creates secure fixes
4. Before/after comparison shows the fix in action

### Supported Vulnerability Types

| Type | Description | Example Exploit |
|------|-------------|-----------------|
| SQL Injection | Query manipulation via user input | `' OR '1'='1` payloads |
| XSS | Cross-site scripting | `<script>` injection |
| Command Injection | Shell command execution | `; rm -rf /` payloads |
| Path Traversal | Directory escape | `../../../etc/passwd` |
| Auth Bypass | Authentication circumvention | Token manipulation |

### Safety Notice

All generated exploits are clearly marked as proof-of-concept for authorized security testing only. The `poc_warning` field in results reminds users to use exploits responsibly.

### Example Output

```python
# ExploitResult
{
    "vulnerability_type": "sql_injection",
    "exploit_code": "user_input = \"' OR '1'='1'--\"",
    "payload": "' OR '1'='1'--",
    "curl_command": "curl -X POST -d \"username=' OR '1'='1'--\" ...",
    "explanation": "Bypasses authentication by always-true condition",
    "poc_warning": "For authorized security testing only"
}

# PatchResult
{
    "patched_code": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    "diff": "- query = f\"SELECT * FROM users WHERE id = {user_id}\"\n+ cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
    "explanation": "Use parameterized queries to prevent SQL injection",
    "verification_test": "assert \"'\" not in sanitized_input"
}
```

## Prediction Market

Agents place token bets on code quality predictions. Track accuracy over time and weight votes by historical performance.

### Basic Usage

```bash
# Review with predictions enabled
consensys review file.py --predict

# View open predictions awaiting resolution
consensys predict list

# Resolve a prediction after incident/no-incident
consensys predict resolve abc123 --outcome safe
consensys predict resolve abc123 --outcome incident

# View agent accuracy leaderboard
consensys predict leaderboard
```

### How It Works

1. During review, each agent places a bet on code quality outcome
2. Agents start with 1000 tokens each
3. When code is deployed and outcome is known, resolve the prediction
4. Winners gain tokens proportional to their confidence
5. Losers forfeit their wagered tokens
6. Agent voting weights adjust based on historical accuracy

### Prediction Types

| Type | Predicted Outcome |
|------|-------------------|
| `BUG_WILL_OCCUR` | Code will cause bugs in production |
| `SECURITY_INCIDENT` | Code will lead to security breach |
| `PERFORMANCE_ISSUE` | Code will cause performance problems |
| `MAINTENANCE_PROBLEM` | Code will be difficult to maintain |
| `CODE_IS_SAFE` | Code is production-ready |

### Token Economics

- Starting balance: 1000 tokens per agent
- Winning bet returns: stake + (stake * (1 + confidence))
- Losing bet: tokens already deducted at bet time
- Voting weight: 0.5 + accuracy + token_bonus (max 2.0x)

### Commands

```bash
# List predictions with status
consensys predict list
# Output: ID, File, Type, Confidence, Bets, Status

# Resolve with incident link
consensys predict resolve abc123 --outcome incident --link "https://github.com/..."

# Leaderboard shows voting weights
consensys predict leaderboard
# Output: Agent, Tokens, Bets, Wins, Accuracy, Weight
```

## Code DNA Fingerprinting

Extract coding style patterns from your codebase and detect anomalies in new code.

### Basic Usage

```bash
# Extract fingerprint from codebase
consensys fingerprint src/

# Save to custom location
consensys fingerprint src/ --output my-project.json

# Review code against fingerprint
consensys review file.py --dna
```

### How It Works

1. Fingerprint command analyzes all Python files in a directory
2. Extracts patterns for naming, types, docs, imports, error handling
3. Saves fingerprint to `.consensys-dna.json`
4. Review with `--dna` compares new code against established patterns
5. Reports anomalies and style match percentage

### Extracted Patterns

| Category | What It Detects |
|----------|-----------------|
| Naming Conventions | Function, class, variable naming styles (snake_case, camelCase, PascalCase) |
| Type Hints | Coverage percentage, parameter vs return hint ratio |
| Docstrings | Format (Google, NumPy, Sphinx, simple), coverage percentage |
| Imports | From-import preference, grouping style, relative import usage |
| Error Handling | Bare except usage, exception specificity, custom exceptions |
| Function Metrics | Average length, max length, cyclomatic complexity |

### Anomaly Detection

The analyzer detects:

- **Naming violations** - Functions/classes not matching codebase style
- **Missing type hints** - When codebase has high coverage but new code lacks hints
- **Docstring style drift** - Using different docstring format than established
- **Import style differences** - Different import organization patterns
- **Outdated idioms** - Using `% formatting` instead of f-strings, `== None` instead of `is None`
- **Copy-paste indicators** - Comments like "From Stack Overflow", "Credit:", etc.
- **AI-generated markers** - Verbose docstrings, "Generated by" comments

### Severity Levels

| Level | Meaning |
|-------|---------|
| `INFO` | Minor style difference, informational only |
| `WARNING` | Notable deviation from codebase patterns |
| `STYLE_VIOLATION` | Clear violation of established conventions |

### Example Output

```bash
consensys review new_feature.py --dna

# Output:
# Style Match: 72%
#
# Anomalies Found:
# | Line | Severity | Pattern | Issue |
# |------|----------|---------|-------|
# | 15   | WARNING  | naming  | Function 'getData' uses camelCase, codebase uses snake_case |
# | 23   | INFO     | type_hints | Missing return type hint |
# | 45   | STYLE_VIOLATION | copy_paste | Comment indicates Stack Overflow source |
```

### Fingerprint File

The `.consensys-dna.json` file contains:

```json
{
    "naming_conventions": {
        "function_style": "snake_case",
        "class_style": "PascalCase",
        "variable_style": "snake_case"
    },
    "type_hint_coverage": {
        "functions_with_hints": 0.85,
        "parameters_with_hints": 0.72
    },
    "docstring_style": {
        "format": "google",
        "coverage": 0.68
    },
    "function_metrics": {
        "average_length": 12.5,
        "max_length": 45,
        "average_complexity": 3.2
    }
}
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
| [`.consensys.yaml`](examples/.consensys.yaml) | Example configuration file with all options |

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
cp examples/.consensys.yaml .consensys.yaml

# User-level config
mkdir -p ~/.consensys
cp examples/.consensys.yaml ~/.consensys/config.yaml
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
