"""Language detection and language-specific review hints for multi-language support."""
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from pathlib import Path


@dataclass
class LanguageInfo:
    """Information about a programming language for code review."""
    name: str
    display_name: str
    file_extensions: List[str]
    syntax_highlight: str  # For Rich syntax highlighting
    review_hints: List[str] = field(default_factory=list)
    common_issues: List[str] = field(default_factory=list)


# Language definitions with review hints
PYTHON = LanguageInfo(
    name="python",
    display_name="Python",
    file_extensions=[".py", ".pyw", ".pyi"],
    syntax_highlight="python",
    review_hints=[
        "Check for proper exception handling (avoid bare except:)",
        "Verify type hints are used appropriately",
        "Look for mutable default arguments in function definitions",
        "Check for potential issues with variable scoping",
        "Ensure context managers (with statements) are used for resources",
    ],
    common_issues=[
        "Missing type annotations",
        "Bare except clauses",
        "Mutable default arguments",
        "Not using context managers",
        "Import order violations (stdlib, third-party, local)",
    ]
)

JAVASCRIPT = LanguageInfo(
    name="javascript",
    display_name="JavaScript",
    file_extensions=[".js", ".mjs", ".cjs", ".jsx"],
    syntax_highlight="javascript",
    review_hints=[
        "Check for proper error handling in async/await code",
        "Verify use of const/let instead of var",
        "Look for potential null/undefined reference errors",
        "Check for proper event listener cleanup",
        "Verify proper handling of Promises",
    ],
    common_issues=[
        "Using var instead of const/let",
        "Missing error handling in async functions",
        "Potential null/undefined dereferences",
        "Memory leaks from event listeners",
        "Callback hell instead of async/await",
    ]
)

TYPESCRIPT = LanguageInfo(
    name="typescript",
    display_name="TypeScript",
    file_extensions=[".ts", ".tsx", ".mts", ".cts"],
    syntax_highlight="typescript",
    review_hints=[
        "Check for proper use of TypeScript's type system",
        "Verify no use of 'any' type where specific types are possible",
        "Look for proper null/undefined handling with strict mode",
        "Check interface vs type alias usage appropriateness",
        "Verify proper generic constraints are used",
    ],
    common_issues=[
        "Overuse of 'any' type",
        "Missing strict null checks",
        "Type assertions (as) instead of proper typing",
        "Not leveraging discriminated unions",
        "Ignoring TypeScript compiler warnings",
    ]
)

GO = LanguageInfo(
    name="go",
    display_name="Go",
    file_extensions=[".go"],
    syntax_highlight="go",
    review_hints=[
        "Check that all errors are handled (not ignored with _)",
        "Verify proper use of goroutines and channels",
        "Look for potential race conditions in concurrent code",
        "Check for proper resource cleanup with defer",
        "Verify idiomatic Go naming conventions",
    ],
    common_issues=[
        "Ignoring returned errors",
        "Race conditions in goroutines",
        "Not using defer for cleanup",
        "Goroutine leaks",
        "Not following Go naming conventions",
    ]
)

RUST = LanguageInfo(
    name="rust",
    display_name="Rust",
    file_extensions=[".rs"],
    syntax_highlight="rust",
    review_hints=[
        "Check for proper ownership and borrowing patterns",
        "Verify Result/Option types are handled properly",
        "Look for unnecessary cloning or allocations",
        "Check for proper use of lifetimes",
        "Verify unsafe code is minimal and well-documented",
    ],
    common_issues=[
        "Unnecessary cloning",
        "Unwrapping Results/Options without error handling",
        "Overuse of unsafe blocks",
        "Lifetime issues",
        "Not using iterators efficiently",
    ]
)

JAVA = LanguageInfo(
    name="java",
    display_name="Java",
    file_extensions=[".java"],
    syntax_highlight="java",
    review_hints=[
        "Check for proper exception handling and resource management",
        "Verify use of try-with-resources for AutoCloseable",
        "Look for potential null pointer exceptions",
        "Check for proper synchronization in concurrent code",
        "Verify immutability where appropriate",
    ],
    common_issues=[
        "Null pointer exceptions",
        "Resource leaks (streams, connections)",
        "Improper exception handling",
        "Thread safety issues",
        "Not using Optional for nullable returns",
    ]
)

CPP = LanguageInfo(
    name="cpp",
    display_name="C++",
    file_extensions=[".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".h"],
    syntax_highlight="cpp",
    review_hints=[
        "Check for memory management issues (leaks, use-after-free)",
        "Verify RAII patterns are used for resource management",
        "Look for potential buffer overflows",
        "Check for proper use of smart pointers",
        "Verify const correctness",
    ],
    common_issues=[
        "Memory leaks",
        "Use-after-free",
        "Buffer overflows",
        "Not using smart pointers",
        "Missing const qualifiers",
    ]
)

C = LanguageInfo(
    name="c",
    display_name="C",
    file_extensions=[".c"],
    syntax_highlight="c",
    review_hints=[
        "Check for buffer overflows and bounds checking",
        "Verify all allocated memory is freed",
        "Look for potential null pointer dereferences",
        "Check for proper error handling",
        "Verify no undefined behavior patterns",
    ],
    common_issues=[
        "Buffer overflows",
        "Memory leaks",
        "Null pointer dereferences",
        "Undefined behavior",
        "Missing error checks",
    ]
)

RUBY = LanguageInfo(
    name="ruby",
    display_name="Ruby",
    file_extensions=[".rb", ".rake", ".gemspec"],
    syntax_highlight="ruby",
    review_hints=[
        "Check for proper exception handling",
        "Verify blocks are used idiomatically",
        "Look for potential nil reference errors",
        "Check for proper use of symbols vs strings",
        "Verify Rails-specific best practices if applicable",
    ],
    common_issues=[
        "NoMethodError on nil",
        "Not using blocks idiomatically",
        "N+1 query problems (Rails)",
        "Missing validations",
        "Improper exception handling",
    ]
)

PHP = LanguageInfo(
    name="php",
    display_name="PHP",
    file_extensions=[".php", ".phtml", ".php5", ".php7"],
    syntax_highlight="php",
    review_hints=[
        "Check for SQL injection vulnerabilities",
        "Verify proper input sanitization",
        "Look for XSS vulnerabilities in output",
        "Check for proper error handling",
        "Verify type declarations are used (PHP 7+)",
    ],
    common_issues=[
        "SQL injection",
        "XSS vulnerabilities",
        "Missing input validation",
        "Not using prepared statements",
        "Undefined variable access",
    ]
)

CSHARP = LanguageInfo(
    name="csharp",
    display_name="C#",
    file_extensions=[".cs"],
    syntax_highlight="csharp",
    review_hints=[
        "Check for proper null handling (nullable reference types)",
        "Verify async/await patterns are correct",
        "Look for proper IDisposable usage",
        "Check for thread safety in concurrent code",
        "Verify LINQ queries are efficient",
    ],
    common_issues=[
        "Null reference exceptions",
        "Async void instead of async Task",
        "Missing IDisposable implementation",
        "Not awaiting Tasks",
        "Inefficient LINQ queries",
    ]
)

SWIFT = LanguageInfo(
    name="swift",
    display_name="Swift",
    file_extensions=[".swift"],
    syntax_highlight="swift",
    review_hints=[
        "Check for proper optional handling",
        "Verify memory management (ARC, weak/unowned references)",
        "Look for potential retain cycles",
        "Check for proper error handling with throws",
        "Verify protocol conformance is complete",
    ],
    common_issues=[
        "Force unwrapping optionals",
        "Retain cycles",
        "Not using weak/unowned appropriately",
        "Missing error handling",
        "Improper use of implicitly unwrapped optionals",
    ]
)

KOTLIN = LanguageInfo(
    name="kotlin",
    display_name="Kotlin",
    file_extensions=[".kt", ".kts"],
    syntax_highlight="kotlin",
    review_hints=[
        "Check for proper null safety usage",
        "Verify coroutine patterns are correct",
        "Look for proper scope function usage (let, apply, etc.)",
        "Check for proper data class usage",
        "Verify idiomatic Kotlin patterns",
    ],
    common_issues=[
        "Unnecessary null checks (!!)",
        "Improper coroutine scope management",
        "Not using data classes for DTOs",
        "Java-style code instead of idiomatic Kotlin",
        "Blocking calls in coroutines",
    ]
)

SCALA = LanguageInfo(
    name="scala",
    display_name="Scala",
    file_extensions=[".scala", ".sc"],
    syntax_highlight="scala",
    review_hints=[
        "Check for proper Option/Either handling",
        "Verify immutability is preferred",
        "Look for proper pattern matching usage",
        "Check for Future composition patterns",
        "Verify type inference is not obscuring types",
    ],
    common_issues=[
        "Calling .get on Option",
        "Mutable state",
        "Improper Future handling",
        "Overly complex implicit usage",
        "Not using pattern matching",
    ]
)

# Fallback for unknown languages
GENERIC = LanguageInfo(
    name="text",
    display_name="Code",
    file_extensions=[],
    syntax_highlight="text",
    review_hints=[
        "Check for proper error handling",
        "Verify input validation",
        "Look for potential security issues",
        "Check for code clarity and readability",
        "Verify proper resource management",
    ],
    common_issues=[]
)

# All supported languages
SUPPORTED_LANGUAGES: Dict[str, LanguageInfo] = {
    "python": PYTHON,
    "javascript": JAVASCRIPT,
    "typescript": TYPESCRIPT,
    "go": GO,
    "rust": RUST,
    "java": JAVA,
    "cpp": CPP,
    "c": C,
    "ruby": RUBY,
    "php": PHP,
    "csharp": CSHARP,
    "swift": SWIFT,
    "kotlin": KOTLIN,
    "scala": SCALA,
}

# Extension to language mapping
EXTENSION_MAP: Dict[str, str] = {}
for lang_name, lang_info in SUPPORTED_LANGUAGES.items():
    for ext in lang_info.file_extensions:
        EXTENSION_MAP[ext] = lang_name


def detect_language(file_path: Optional[str] = None, code: Optional[str] = None) -> LanguageInfo:
    """Detect the programming language from file extension or code content.

    Args:
        file_path: Optional file path to detect language from extension
        code: Optional code content for heuristic detection (fallback)

    Returns:
        LanguageInfo for the detected language
    """
    # Try file extension first
    if file_path:
        path = Path(file_path)
        ext = path.suffix.lower()

        # Handle .h files (could be C or C++)
        if ext == ".h":
            # Check for C++ indicators in code if available
            if code:
                cpp_indicators = ["class ", "template", "namespace", "std::", "public:", "private:", "virtual"]
                if any(indicator in code for indicator in cpp_indicators):
                    return CPP
            return C  # Default to C for .h files

        if ext in EXTENSION_MAP:
            return SUPPORTED_LANGUAGES[EXTENSION_MAP[ext]]

    # Heuristic detection from code content (fallback)
    if code:
        code_sample = code[:2000]  # Look at first 2000 chars

        # Check for shebang
        if code_sample.startswith("#!/usr/bin/env python") or code_sample.startswith("#!/usr/bin/python"):
            return PYTHON
        if code_sample.startswith("#!/usr/bin/env node") or code_sample.startswith("#!/usr/bin/node"):
            return JAVASCRIPT
        if code_sample.startswith("#!/usr/bin/env ruby") or code_sample.startswith("#!/usr/bin/ruby"):
            return RUBY

        # Check for language-specific patterns
        if "package main" in code_sample and "func " in code_sample:
            return GO
        if "fn main()" in code_sample or "fn " in code_sample and "->" in code_sample:
            return RUST
        if "<?php" in code_sample:
            return PHP
        if "public class " in code_sample or "private class " in code_sample:
            if "namespace " in code_sample or "using System" in code_sample:
                return CSHARP
            return JAVA
        if "import Foundation" in code_sample or "import UIKit" in code_sample:
            return SWIFT
        if "fun " in code_sample and ("val " in code_sample or "var " in code_sample):
            return KOTLIN
        if "def " in code_sample and ":" in code_sample:
            # Could be Python or Ruby
            if "end" in code_sample and not "endif" in code_sample:
                return RUBY
            return PYTHON
        if "const " in code_sample or "let " in code_sample or "function " in code_sample:
            # Could be JS or TS
            if ": " in code_sample and ("interface " in code_sample or "type " in code_sample):
                return TYPESCRIPT
            return JAVASCRIPT

    return GENERIC


def get_language_prompt_hints(language: LanguageInfo) -> str:
    """Generate language-specific review hints for the AI prompt.

    Args:
        language: The LanguageInfo for the detected language

    Returns:
        String with language-specific review instructions
    """
    if language.name == "text":
        return ""

    hints = [f"\nYou are reviewing {language.display_name} code."]

    if language.review_hints:
        hints.append(f"\n{language.display_name}-specific review points:")
        for hint in language.review_hints[:3]:  # Top 3 hints
            hints.append(f"- {hint}")

    if language.common_issues:
        hints.append(f"\nCommon {language.display_name} issues to watch for:")
        for issue in language.common_issues[:3]:  # Top 3 issues
            hints.append(f"- {issue}")

    return "\n".join(hints)


def get_syntax_highlight_language(file_path: Optional[str] = None, language: Optional[LanguageInfo] = None) -> str:
    """Get the syntax highlighting language name for Rich.

    Args:
        file_path: Optional file path
        language: Optional pre-detected LanguageInfo

    Returns:
        String for Rich Syntax highlighting (e.g., 'python', 'javascript')
    """
    if language:
        return language.syntax_highlight

    if file_path:
        detected = detect_language(file_path=file_path)
        return detected.syntax_highlight

    return "text"
