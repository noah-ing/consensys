# Changelog

All notable changes to Consensys will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
