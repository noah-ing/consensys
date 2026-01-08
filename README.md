# Consensus

**Multi-agent AI code review with debate and voting.**

[![PyPI version](https://badge.fury.io/py/consensus-review.svg)](https://badge.fury.io/py/consensus-review)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Consensus brings together multiple AI experts to review your code, debate their findings, and reach a collective decision. Each expert has a unique perspective:

- **SecurityExpert** - Focuses on vulnerabilities, injection attacks, and security best practices
- **PerformanceEngineer** - Analyzes efficiency, optimization opportunities, and resource usage
- **ArchitectureCritic** - Evaluates design patterns, SOLID principles, and code structure
- **PragmaticDev** - Balances practicality with best practices, focuses on maintainability

## Quick Start

```bash
# Install
pip install consensus-review

# Set your API key
export ANTHROPIC_API_KEY="your-api-key"

# Review a file
consensus review myfile.py

# Quick review (faster, for pre-commit hooks)
consensus review myfile.py --quick

# Review with auto-fix suggestions
consensus review myfile.py --fix
```

## Features

- **Multi-agent debate** - AI experts discuss and challenge each other's findings
- **Consensus voting** - Final decision based on expert votes (APPROVE/REJECT/ABSTAIN)
- **Smart caching** - Avoid redundant API calls for unchanged code
- **Language detection** - Supports 14+ programming languages with context-aware prompts
- **CI/CD integration** - GitHub Action, pre-commit hooks, and fail-on thresholds
- **Rich output** - Beautiful terminal UI with syntax highlighting
- **Export options** - Markdown and HTML reports for documentation

## Installation

```bash
# From PyPI
pip install consensus-review

# With web UI support
pip install consensus-review[web]

# From source
git clone https://github.com/consensus-review/consensus.git
cd consensus
pip install -e .
```

## Usage

### Command Line

```bash
# Basic review
consensus review path/to/file.py

# Review inline code snippet
consensus review --code 'def foo(): pass'

# Quick mode (Round 1 only, ~3 seconds)
consensus review file.py --quick

# Stream AI thinking in real-time
consensus review file.py --stream

# CI mode: fail on HIGH severity or above
consensus review file.py --fail-on HIGH

# Only show MEDIUM+ severity issues
consensus review file.py --min-severity MEDIUM

# Review only changed lines (git diff)
consensus review file.py --diff-only

# Auto-fix based on review feedback
consensus review file.py --fix --output fixed.py
```

### Batch Review

```bash
# Review all Python files in a directory
consensus review-batch src/

# Parallel processing with 8 workers
consensus review-batch src/ --parallel 8

# Generate markdown report
consensus review-batch src/ --report report.md

# CI mode for batch review
consensus review-batch src/ --fail-on HIGH --quick
```

### Git Integration

```bash
# Review all uncommitted changes
consensus diff

# Review only staged changes (pre-commit)
consensus commit

# Review a GitHub PR
consensus pr 123

# Post review as PR comment
consensus pr 123 --post
```

### History and Replay

```bash
# List recent review sessions
consensus history

# Replay a past review
consensus replay abc123

# Export to markdown
consensus export abc123 --format md

# Export to HTML
consensus export abc123 --format html
```

## GitHub Action

Automatically review pull requests with Consensus.

### Basic Setup

Add to `.github/workflows/consensus.yml`:

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

      - uses: consensus-review/consensus@v1
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
name: Consensus Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - '**.py'
      - '**.ts'
      - '**.go'

concurrency:
  group: consensus-${{ github.event.pull_request.number }}
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

      - uses: consensus-review/consensus@v1
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
# Copy .github/workflows/consensus-review.yml to your repo
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
consensus config init --project
consensus config init --user

# View current config
consensus config show
```

### Team Configuration

```bash
# Use a preset team
consensus set-team --preset security-focused
consensus set-team --preset quick-check

# Custom team
consensus set-team SecurityExpert PragmaticDev

# Create custom persona
consensus add-persona

# List available teams
consensus teams
```

#### Available Presets

| Preset | Description | Personas |
|--------|-------------|----------|
| `full-review` | Complete 4-agent review | All 4 experts |
| `security-focused` | Security-centric review | SecurityExpert, ArchitectureCritic |
| `performance-focused` | Performance-centric review | PerformanceEngineer, PragmaticDev |
| `quick-check` | Fast 2-agent review | SecurityExpert, PragmaticDev |

## Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/consensus-review/consensus
    rev: v0.1.0
    hooks:
      - id: consensus-review
        args: ['--quick', '--fail-on', 'HIGH']
```

Or install the built-in hook:

```bash
consensus install-hooks --git
```

## API Usage

Use Consensus programmatically:

```python
from consensus import DebateOrchestrator
from consensus.personas import PERSONAS

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

## Metrics and Cost Tracking

```bash
# View API usage and costs
consensus metrics

# Weekly breakdown
consensus metrics --period weekly

# Set budget alert
consensus metrics --budget 10.00
```

## Supported Languages

Consensus provides language-specific review hints for:

- Python, JavaScript, TypeScript
- Go, Rust, Java
- C, C++, C#
- Ruby, PHP
- Swift, Kotlin, Scala

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

---

Built with Claude by Anthropic
