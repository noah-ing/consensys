"""Code DNA extractor for analyzing codebase patterns and characteristics.

This module provides the DNAExtractor class which analyzes a codebase
to extract its unique fingerprint - naming conventions, coding style,
patterns used, and other characteristics.
"""

import ast
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter


@dataclass
class NamingConventions:
    """Naming convention patterns detected in the codebase."""
    function_style: str  # snake_case, camelCase, etc.
    class_style: str  # PascalCase, etc.
    variable_style: str  # snake_case, camelCase, etc.
    constant_style: str  # UPPER_SNAKE_CASE, etc.
    private_prefix: str  # _, __, none
    samples: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class TypeHintCoverage:
    """Type hint usage statistics."""
    functions_with_hints: int
    total_functions: int
    parameters_with_hints: int
    total_parameters: int
    return_type_coverage: float  # percentage
    coverage_percentage: float
    style: str  # full, partial, minimal, none


@dataclass
class DocstringStyle:
    """Docstring patterns detected in the codebase."""
    format: str  # google, numpy, sphinx, simple, none
    coverage_percentage: float
    average_length: int
    samples: List[str] = field(default_factory=list)


@dataclass
class ImportStyle:
    """Import patterns and preferences."""
    prefers_from_imports: bool
    groups_imports: bool
    relative_import_usage: float  # percentage
    common_stdlib: List[str] = field(default_factory=list)
    common_third_party: List[str] = field(default_factory=list)


@dataclass
class ErrorHandlingPattern:
    """Error handling patterns in the codebase."""
    uses_bare_except: bool
    exception_specificity: str  # specific, broad, mixed
    try_block_count: int
    custom_exceptions: List[str] = field(default_factory=list)
    common_handlers: List[str] = field(default_factory=list)


@dataclass
class TestCoverage:
    """Test-related patterns and metrics."""
    has_tests: bool
    test_framework: str  # pytest, unittest, none
    test_file_count: int
    test_to_source_ratio: float
    uses_fixtures: bool
    uses_mocks: bool


@dataclass
class FunctionMetrics:
    """Function-level metrics."""
    average_length: float
    max_length: int
    average_complexity: float  # cyclomatic complexity estimate
    max_complexity: int
    total_functions: int
    deeply_nested_count: int  # functions with >3 nesting levels


@dataclass
class CodebaseFingerprint:
    """Complete DNA fingerprint of a codebase."""
    directory: str
    total_files: int
    total_lines: int
    naming_conventions: NamingConventions
    type_hint_coverage: TypeHintCoverage
    docstring_style: DocstringStyle
    import_style: ImportStyle
    error_handling: ErrorHandlingPattern
    test_coverage: TestCoverage
    function_metrics: FunctionMetrics

    def to_json(self) -> str:
        """Convert fingerprint to JSON string."""
        return json.dumps(asdict(self), indent=2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert fingerprint to dictionary."""
        return asdict(self)

    @classmethod
    def from_json(cls, json_str: str) -> "CodebaseFingerprint":
        """Create fingerprint from JSON string."""
        data = json.loads(json_str)
        return cls(
            directory=data["directory"],
            total_files=data["total_files"],
            total_lines=data["total_lines"],
            naming_conventions=NamingConventions(**data["naming_conventions"]),
            type_hint_coverage=TypeHintCoverage(**data["type_hint_coverage"]),
            docstring_style=DocstringStyle(**data["docstring_style"]),
            import_style=ImportStyle(**data["import_style"]),
            error_handling=ErrorHandlingPattern(**data["error_handling"]),
            test_coverage=TestCoverage(**data["test_coverage"]),
            function_metrics=FunctionMetrics(**data["function_metrics"]),
        )


class DNAExtractor:
    """Extracts the code DNA fingerprint from a codebase.

    Analyzes Python files in a directory to extract patterns including:
    - Naming conventions (function, class, variable styles)
    - Type hint coverage and style
    - Docstring format and coverage
    - Import organization style
    - Error handling patterns
    - Test coverage and framework
    - Function length and complexity metrics
    """

    # Standard library modules for import classification
    STDLIB_MODULES = {
        "os", "sys", "re", "json", "typing", "pathlib", "collections",
        "datetime", "time", "math", "random", "hashlib", "functools",
        "itertools", "dataclasses", "abc", "contextlib", "io", "threading",
        "subprocess", "logging", "unittest", "copy", "enum", "uuid",
        "sqlite3", "urllib", "http", "html", "xml", "email", "csv",
        "tempfile", "shutil", "glob", "fnmatch", "pickle", "base64"
    }

    def __init__(self, directory: str):
        """Initialize extractor with target directory.

        Args:
            directory: Path to the codebase directory to analyze.
        """
        self.directory = Path(directory)
        self.python_files: List[Path] = []
        self.parsed_trees: Dict[Path, ast.AST] = {}
        self.file_contents: Dict[Path, str] = {}

    def _collect_python_files(self) -> None:
        """Collect all Python files in the directory."""
        self.python_files = []
        for pattern in ["**/*.py"]:
            for path in self.directory.rglob("*.py"):
                # Skip common excluded directories
                parts = path.parts
                if any(excluded in parts for excluded in
                       ["__pycache__", ".git", "venv", ".venv", "node_modules",
                        ".eggs", "*.egg-info", "build", "dist"]):
                    continue
                self.python_files.append(path)

    def _parse_files(self) -> None:
        """Parse all Python files into ASTs."""
        for path in self.python_files:
            try:
                content = path.read_text(encoding="utf-8")
                self.file_contents[path] = content
                self.parsed_trees[path] = ast.parse(content)
            except (SyntaxError, UnicodeDecodeError):
                # Skip files that can't be parsed
                pass

    def _analyze_naming_conventions(self) -> NamingConventions:
        """Analyze naming conventions used in the codebase."""
        function_names: List[str] = []
        class_names: List[str] = []
        variable_names: List[str] = []
        constant_names: List[str] = []

        for tree in self.parsed_trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    function_names.append(node.name)
                elif isinstance(node, ast.AsyncFunctionDef):
                    function_names.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    class_names.append(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            # Check if it's likely a constant (all caps)
                            if name.isupper() and "_" in name or name.isupper():
                                constant_names.append(name)
                            else:
                                variable_names.append(name)

        def detect_style(names: List[str]) -> str:
            if not names:
                return "unknown"

            snake_count = sum(1 for n in names if re.match(r'^[a-z][a-z0-9_]*$', n))
            camel_count = sum(1 for n in names if re.match(r'^[a-z][a-zA-Z0-9]*$', n) and any(c.isupper() for c in n))
            pascal_count = sum(1 for n in names if re.match(r'^[A-Z][a-zA-Z0-9]*$', n))
            upper_count = sum(1 for n in names if re.match(r'^[A-Z][A-Z0-9_]*$', n))

            total = len(names)
            if snake_count / total > 0.7:
                return "snake_case"
            elif camel_count / total > 0.7:
                return "camelCase"
            elif pascal_count / total > 0.7:
                return "PascalCase"
            elif upper_count / total > 0.7:
                return "UPPER_SNAKE_CASE"
            return "mixed"

        # Detect private prefix usage
        private_prefixes = [n for n in function_names + variable_names if n.startswith("_")]
        double_underscore = [n for n in private_prefixes if n.startswith("__") and not n.endswith("__")]

        if len(double_underscore) > len(private_prefixes) / 2 and private_prefixes:
            private_prefix = "__"
        elif private_prefixes:
            private_prefix = "_"
        else:
            private_prefix = "none"

        return NamingConventions(
            function_style=detect_style(function_names),
            class_style=detect_style(class_names),
            variable_style=detect_style(variable_names),
            constant_style=detect_style(constant_names) if constant_names else "UPPER_SNAKE_CASE",
            private_prefix=private_prefix,
            samples={
                "functions": function_names[:5],
                "classes": class_names[:5],
                "variables": variable_names[:5],
            }
        )

    def _analyze_type_hints(self) -> TypeHintCoverage:
        """Analyze type hint coverage in the codebase."""
        functions_with_hints = 0
        total_functions = 0
        params_with_hints = 0
        total_params = 0
        functions_with_return = 0

        for tree in self.parsed_trees.values():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
                    has_any_hint = False

                    # Check return type
                    if node.returns is not None:
                        has_any_hint = True
                        functions_with_return += 1

                    # Check parameter annotations
                    for arg in node.args.args + node.args.kwonlyargs:
                        if arg.arg != "self" and arg.arg != "cls":
                            total_params += 1
                            if arg.annotation is not None:
                                params_with_hints += 1
                                has_any_hint = True

                    if has_any_hint:
                        functions_with_hints += 1

        coverage = (params_with_hints / total_params * 100) if total_params > 0 else 0
        return_coverage = (functions_with_return / total_functions * 100) if total_functions > 0 else 0

        # Determine style
        if coverage >= 90:
            style = "full"
        elif coverage >= 50:
            style = "partial"
        elif coverage >= 10:
            style = "minimal"
        else:
            style = "none"

        return TypeHintCoverage(
            functions_with_hints=functions_with_hints,
            total_functions=total_functions,
            parameters_with_hints=params_with_hints,
            total_parameters=total_params,
            return_type_coverage=round(return_coverage, 1),
            coverage_percentage=round(coverage, 1),
            style=style
        )

    def _analyze_docstrings(self) -> DocstringStyle:
        """Analyze docstring patterns in the codebase."""
        docstrings: List[str] = []
        items_with_docstrings = 0
        total_items = 0

        for tree in self.parsed_trees.values():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                    total_items += 1
                    docstring = ast.get_docstring(node)
                    if docstring:
                        docstrings.append(docstring)
                        items_with_docstrings += 1

        # Detect docstring format
        def detect_format(docs: List[str]) -> str:
            if not docs:
                return "none"

            google_count = sum(1 for d in docs if "Args:" in d or "Returns:" in d or "Raises:" in d)
            numpy_count = sum(1 for d in docs if "Parameters\n" in d or "Returns\n" in d)
            sphinx_count = sum(1 for d in docs if ":param " in d or ":returns:" in d or ":type " in d)

            total = len(docs)
            if google_count / total > 0.3:
                return "google"
            elif numpy_count / total > 0.3:
                return "numpy"
            elif sphinx_count / total > 0.3:
                return "sphinx"
            elif total > 0:
                return "simple"
            return "none"

        coverage = (items_with_docstrings / total_items * 100) if total_items > 0 else 0
        avg_length = int(sum(len(d) for d in docstrings) / len(docstrings)) if docstrings else 0

        return DocstringStyle(
            format=detect_format(docstrings),
            coverage_percentage=round(coverage, 1),
            average_length=avg_length,
            samples=docstrings[:3]
        )

    def _analyze_imports(self) -> ImportStyle:
        """Analyze import patterns in the codebase."""
        from_imports = 0
        regular_imports = 0
        relative_imports = 0
        total_imports = 0
        stdlib_counter: Counter = Counter()
        third_party_counter: Counter = Counter()

        for tree in self.parsed_trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    regular_imports += 1
                    total_imports += 1
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        if module in self.STDLIB_MODULES:
                            stdlib_counter[module] += 1
                        else:
                            third_party_counter[module] += 1

                elif isinstance(node, ast.ImportFrom):
                    from_imports += 1
                    total_imports += 1
                    if node.level > 0:
                        relative_imports += 1
                    elif node.module:
                        module = node.module.split(".")[0]
                        if module in self.STDLIB_MODULES:
                            stdlib_counter[module] += 1
                        else:
                            third_party_counter[module] += 1

        # Check if imports appear to be grouped (by looking for blank lines between import blocks)
        groups_imports = False
        for content in self.file_contents.values():
            lines = content.split("\n")
            in_import_block = False
            saw_blank_in_imports = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    if in_import_block and saw_blank_in_imports:
                        groups_imports = True
                        break
                    in_import_block = True
                    saw_blank_in_imports = False
                elif in_import_block and stripped == "":
                    saw_blank_in_imports = True
                elif in_import_block and stripped:
                    in_import_block = False
            if groups_imports:
                break

        relative_pct = (relative_imports / total_imports * 100) if total_imports > 0 else 0

        return ImportStyle(
            prefers_from_imports=from_imports > regular_imports,
            groups_imports=groups_imports,
            relative_import_usage=round(relative_pct, 1),
            common_stdlib=[mod for mod, _ in stdlib_counter.most_common(5)],
            common_third_party=[mod for mod, _ in third_party_counter.most_common(5)]
        )

    def _analyze_error_handling(self) -> ErrorHandlingPattern:
        """Analyze error handling patterns in the codebase."""
        try_count = 0
        bare_except_count = 0
        specific_exceptions: List[str] = []
        custom_exceptions: List[str] = []

        for tree in self.parsed_trees.values():
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    try_count += 1
                    for handler in node.handlers:
                        if handler.type is None:
                            bare_except_count += 1
                        elif isinstance(handler.type, ast.Name):
                            specific_exceptions.append(handler.type.id)
                        elif isinstance(handler.type, ast.Tuple):
                            for exc in handler.type.elts:
                                if isinstance(exc, ast.Name):
                                    specific_exceptions.append(exc.id)

                # Find custom exception definitions
                elif isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and "Exception" in base.id or "Error" in base.id:
                            custom_exceptions.append(node.name)
                        elif isinstance(base, ast.Attribute) and hasattr(base, 'attr'):
                            if "Exception" in base.attr or "Error" in base.attr:
                                custom_exceptions.append(node.name)

        exception_counter = Counter(specific_exceptions)
        common_handlers = [exc for exc, _ in exception_counter.most_common(5)]

        # Determine specificity
        uses_bare = bare_except_count > 0
        if len(set(specific_exceptions)) > 3 and bare_except_count < try_count * 0.1:
            specificity = "specific"
        elif bare_except_count > try_count * 0.3:
            specificity = "broad"
        else:
            specificity = "mixed"

        return ErrorHandlingPattern(
            uses_bare_except=uses_bare,
            exception_specificity=specificity,
            try_block_count=try_count,
            custom_exceptions=list(set(custom_exceptions)),
            common_handlers=common_handlers
        )

    def _analyze_tests(self) -> TestCoverage:
        """Analyze test-related patterns in the codebase."""
        test_files: List[Path] = []
        source_files: List[Path] = []
        uses_fixtures = False
        uses_mocks = False
        framework = "none"

        for path in self.python_files:
            if "test" in path.name.lower() or "test" in str(path.parent).lower():
                test_files.append(path)
            else:
                source_files.append(path)

        # Analyze test files for patterns
        for path in test_files:
            content = self.file_contents.get(path, "")

            # Detect framework
            if "import pytest" in content or "from pytest" in content:
                framework = "pytest"
            elif "import unittest" in content or "from unittest" in content:
                if framework != "pytest":
                    framework = "unittest"

            # Check for fixtures
            if "@pytest.fixture" in content or "@fixture" in content:
                uses_fixtures = True

            # Check for mocks
            if "Mock(" in content or "patch(" in content or "MagicMock" in content:
                uses_mocks = True

        ratio = len(test_files) / len(source_files) if source_files else 0

        return TestCoverage(
            has_tests=len(test_files) > 0,
            test_framework=framework,
            test_file_count=len(test_files),
            test_to_source_ratio=round(ratio, 2),
            uses_fixtures=uses_fixtures,
            uses_mocks=uses_mocks
        )

    def _analyze_function_metrics(self) -> FunctionMetrics:
        """Analyze function-level metrics including length and complexity."""
        function_lengths: List[int] = []
        complexities: List[int] = []
        deeply_nested = 0

        for path, tree in self.parsed_trees.items():
            content = self.file_contents.get(path, "")
            lines = content.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Calculate function length
                    if hasattr(node, "end_lineno") and node.end_lineno:
                        length = node.end_lineno - node.lineno + 1
                    else:
                        # Fallback for older Python versions
                        length = len([n for n in ast.walk(node)])
                    function_lengths.append(length)

                    # Estimate cyclomatic complexity
                    # Count decision points: if, elif, for, while, and, or, except, with
                    complexity = 1  # Base complexity
                    max_depth = 0

                    def count_complexity(n: ast.AST, depth: int = 0) -> Tuple[int, int]:
                        nonlocal max_depth
                        max_depth = max(max_depth, depth)
                        comp = 0

                        if isinstance(n, (ast.If, ast.IfExp)):
                            comp += 1
                        elif isinstance(n, (ast.For, ast.AsyncFor)):
                            comp += 1
                        elif isinstance(n, (ast.While,)):
                            comp += 1
                        elif isinstance(n, ast.ExceptHandler):
                            comp += 1
                        elif isinstance(n, (ast.With, ast.AsyncWith)):
                            comp += 1
                        elif isinstance(n, ast.BoolOp):
                            # and/or add complexity
                            comp += len(n.values) - 1
                        elif isinstance(n, ast.comprehension):
                            comp += 1
                            if n.ifs:
                                comp += len(n.ifs)

                        for child in ast.iter_child_nodes(n):
                            child_comp, _ = count_complexity(child, depth + 1)
                            comp += child_comp

                        return comp, max_depth

                    comp, depth = count_complexity(node)
                    complexity += comp
                    complexities.append(complexity)

                    if depth > 3:
                        deeply_nested += 1

        avg_length = sum(function_lengths) / len(function_lengths) if function_lengths else 0
        max_length = max(function_lengths) if function_lengths else 0
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        max_complexity = max(complexities) if complexities else 0

        return FunctionMetrics(
            average_length=round(avg_length, 1),
            max_length=max_length,
            average_complexity=round(avg_complexity, 1),
            max_complexity=max_complexity,
            total_functions=len(function_lengths),
            deeply_nested_count=deeply_nested
        )

    def extract(self, directory: Optional[str] = None) -> CodebaseFingerprint:
        """Extract the complete DNA fingerprint from the codebase.

        Args:
            directory: Optional directory path. If not provided, uses the
                      directory specified in constructor.

        Returns:
            CodebaseFingerprint containing all extracted patterns.
        """
        if directory:
            self.directory = Path(directory)

        # Collect and parse files
        self._collect_python_files()
        self._parse_files()

        # Count total lines
        total_lines = sum(len(content.split("\n")) for content in self.file_contents.values())

        # Extract all patterns
        return CodebaseFingerprint(
            directory=str(self.directory),
            total_files=len(self.python_files),
            total_lines=total_lines,
            naming_conventions=self._analyze_naming_conventions(),
            type_hint_coverage=self._analyze_type_hints(),
            docstring_style=self._analyze_docstrings(),
            import_style=self._analyze_imports(),
            error_handling=self._analyze_error_handling(),
            test_coverage=self._analyze_tests(),
            function_metrics=self._analyze_function_metrics()
        )
