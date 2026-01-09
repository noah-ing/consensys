# Changelog

All notable changes to Consensys will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-09

### Added
- **Comprehensive Playwright Test Suite** - Full end-to-end browser testing
  - 12 automated tests covering all UI functionality
  - Tests for code submission, agent responses, fixes panel, exports
  - Mobile viewport testing (375px width)
  - Dark mode testing
  - Screenshots saved to docs/screenshots/
- **Unique Terminal/Hacker UI Redesign** - Distinctive visual identity
  - ASCII art logo header
  - JetBrains Mono monospace font throughout
  - Terminal color scheme (green, amber, red, cyan, purple)
  - Sharp edges and intentional design over rounded-everything aesthetic
  - Dark mode as primary (devs prefer dark)
  - Light mode as secondary option
- **CI/CD Pipeline-Style Status Display** - Live progress tracking
  - Progress bar with percentage and timer
  - Job cards for each agent showing running/success states
  - Terminal log with timestamped entries
  - Agent prefixes [SEC]/[PERF]/[ARCH]/[DEV]
- **Terminal-Style Agent Output** - Reviews render like terminal output
  - Command-line style headers ($ SEC_REVIEW --analyze)
  - Tree-style prefixes for issues
  - Severity badges (CRIT/HIGH/MED/LOW)
  - Blinking cursor animation
  - Typing/streaming effect for real-time feel
- **Keyboard Shortcuts for Power Users**
  - Cmd/Ctrl+Enter to submit code
  - Cmd/Ctrl+K to clear and focus input
  - Cmd/Ctrl+E to show export menu
  - Cmd/Ctrl+D to toggle dark/light mode
  - Cmd/Ctrl+1/2/3/4 to jump to sections
  - ? key to show all shortcuts modal
  - Shortcut hints on button hover
- **Sound Effects (Optional)**
  - Subtle click sound on button press
  - Success chime (C-E-G arpeggio) for APPROVE verdict
  - Warning tone (B-G-E descending) for REJECT verdict
  - Optional typing sounds (disabled by default)
  - Master toggle with Ctrl+M shortcut
  - Web Audio API only - no external files
  - Preferences saved to localStorage
- **Real-Time Collaboration / Session Sharing**
  - Shareable session links: /session/{session_id}
  - Anyone with link can view results (read-only)
  - Share Results button copies link to clipboard
  - QR code generation for mobile sharing
  - API: GET /api/sessions/{id}/share returns share_url and qr_code_svg
- **Performance Optimizations**
  - Skeleton loaders with shimmer animation while waiting
  - Lazy-loaded Prism.js syntax highlighting (loads on demand)
  - Debounced character count updates (50ms)
  - GPU-accelerated CSS with will-change and transform3d
  - Performance metrics in console (localStorage perfDebug mode)

### Changed
- Dark mode is now the default theme
- UI uses monospace fonts throughout for code review tool aesthetic
- Agent reviews display in terminal output style
- Status section shows CI/CD pipeline-style progress

### Fixed
- Consensus panel visibility in quick mode
- Reviews container timing issues
- Export panel visibility detection
- "No fixes" message display when no fixes found
- Test reliability improvements with better wait conditions

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
