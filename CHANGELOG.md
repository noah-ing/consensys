# Changelog

All notable changes to Consensys will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-01-08

### Added
- **Actionable Fix Suggestions** - Every code issue now includes specific fix code
  - Agent prompts updated to always provide concrete fix suggestions
  - Each issue includes `fix` field with actual code and `original_code` for context
  - Fixes reference line numbers for precise localization
- **Suggested Fixes UI Panel** - New section in web UI below Final Verdict
  - Fixes grouped by severity (Critical, High, Medium, Low)
  - Syntax highlighting for all code snippets using Prism.js
  - Copy-to-clipboard buttons for easy code copying
  - Collapsible sections for each severity level
- **Before/After Diff View** - Visual comparison of problematic vs fixed code
  - Toggle button to show diff view for each fix
  - Side-by-side display with red/green highlighting
  - Line numbers in diff view
  - Responsive design for mobile (stacks vertically)
- **Apply All Fixes** - Generate fully fixed version of submitted code
  - Combines all non-conflicting fixes into one output
  - Bottom-to-top merge strategy to avoid line conflicts
  - Shows count of applied fixes
  - Copy Fixed Code button
- **Export Options** - Multiple export formats for review results
  - Export as Markdown with issues and fixes
  - Export as JSON for CI/CD integration
  - Export as GitHub Issue format with labels and checkboxes
  - All formats include agent reviews, votes, and fixes
- **Quick Action Buttons** - Common security fix patterns
  - 10 predefined patterns (SQL injection, XSS, path traversal, etc.)
  - Expandable cards with documentation links (OWASP, CWE)
  - Related issues grouped under each pattern
- **Updated API** - Fix suggestions in all API responses
  - POST /api/review returns fixes array
  - WebSocket /ws/review streams fixes as generated
  - GET /api/sessions/{id} includes fixes
  - New FixSuggestion Pydantic model

### Changed
- Review model updated with `fix` and `original_code` fields
- CLI displays fix suggestions below each issue
- Debate orchestrator extracts and aggregates fixes

## [0.1.2] - 2026-01-08

### Fixed
- Minor bug fixes and stability improvements

## [0.1.1] - 2026-01-08

### Added
- Multi-language batch review support for 14 programming languages
  - Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP, Swift, Kotlin, Scala
  - New `--lang` option to filter by specific language
  - New `--extensions` option for custom extension filtering
- Web UI extras via optional dependencies
  - Install with `pip install 'consensys[web]'`
  - Includes FastAPI, uvicorn, websockets, and jinja2
- `consensys web` command to start the web UI server
  - Default port 8080 with `--port` and `--host` options
  - REST API and WebSocket support for real-time reviews

### Changed
- `consensys review-batch` now finds all supported language files by default
- Updated default web server port from 8000 to 8080

## [0.1.0] - 2026-01-07

### Added
- Initial release of Consensys
- Multi-agent code review with 4 expert personas
  - SecurityExpert, PerformanceEngineer, ArchitectureCritic, PragmaticDev
- Three-round debate system: Review, Response/Rebuttal, Vote
- Consensus building with majority voting
- CLI commands: review, review-batch, history, replay, pr, diff, commit
- Git integration for PR and diff reviews
- SQLite storage for review history
- Review caching with TTL expiry
- Markdown and HTML export
- API metrics tracking
- Configuration file support (YAML/JSON)
- Language detection for 14 programming languages
