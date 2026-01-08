"""Tests for the Code DNA fingerprint extraction and analysis module."""
import os
import tempfile
import json
import pytest
from pathlib import Path

from src.dna.extractor import (
    DNAExtractor,
    CodebaseFingerprint,
    NamingConventions,
    TypeHintCoverage,
    DocstringStyle,
    ImportStyle,
    ErrorHandlingPattern,
    TestCoverage,
    FunctionMetrics,
)
from src.dna.analyzer import (
    DNAAnalyzer,
    Anomaly,
    AnomalySeverity,
)


class TestNamingConventions:
    """Tests for NamingConventions dataclass."""

    def test_naming_conventions_creation(self):
        """Test NamingConventions can be created."""
        conventions = NamingConventions(
            function_style="snake_case",
            class_style="PascalCase",
            variable_style="snake_case",
            constant_style="UPPER_SNAKE_CASE",
            private_prefix="_",
        )
        assert conventions.function_style == "snake_case"
        assert conventions.class_style == "PascalCase"

    def test_naming_conventions_with_samples(self):
        """Test NamingConventions can include samples."""
        conventions = NamingConventions(
            function_style="snake_case",
            class_style="PascalCase",
            variable_style="snake_case",
            constant_style="UPPER_SNAKE_CASE",
            private_prefix="_",
            samples={"functions": ["get_user", "create_order"]}
        )
        assert len(conventions.samples["functions"]) == 2


class TestTypeHintCoverage:
    """Tests for TypeHintCoverage dataclass."""

    def test_type_hint_coverage_creation(self):
        """Test TypeHintCoverage can be created."""
        coverage = TypeHintCoverage(
            functions_with_hints=8,
            total_functions=10,
            parameters_with_hints=20,
            total_parameters=25,
            return_type_coverage=80.0,
            coverage_percentage=80.0,
            style="partial",
        )
        assert coverage.functions_with_hints == 8
        assert coverage.coverage_percentage == 80.0


class TestDocstringStyle:
    """Tests for DocstringStyle dataclass."""

    def test_docstring_style_creation(self):
        """Test DocstringStyle can be created."""
        style = DocstringStyle(
            format="google",
            coverage_percentage=75.0,
            average_length=100,
        )
        assert style.format == "google"
        assert style.coverage_percentage == 75.0


class TestImportStyle:
    """Tests for ImportStyle dataclass."""

    def test_import_style_creation(self):
        """Test ImportStyle can be created."""
        style = ImportStyle(
            prefers_from_imports=True,
            groups_imports=True,
            relative_import_usage=15.5,
        )
        assert style.prefers_from_imports is True
        assert style.relative_import_usage == 15.5


class TestErrorHandlingPattern:
    """Tests for ErrorHandlingPattern dataclass."""

    def test_error_handling_creation(self):
        """Test ErrorHandlingPattern can be created."""
        pattern = ErrorHandlingPattern(
            uses_bare_except=False,
            exception_specificity="specific",
            try_block_count=15,
        )
        assert pattern.uses_bare_except is False
        assert pattern.exception_specificity == "specific"


class TestTestCoverage:
    """Tests for TestCoverage dataclass."""

    def test_test_coverage_creation(self):
        """Test TestCoverage can be created."""
        coverage = TestCoverage(
            has_tests=True,
            test_framework="pytest",
            test_file_count=5,
            test_to_source_ratio=0.5,
            uses_fixtures=True,
            uses_mocks=True,
        )
        assert coverage.has_tests is True
        assert coverage.test_framework == "pytest"


class TestFunctionMetrics:
    """Tests for FunctionMetrics dataclass."""

    def test_function_metrics_creation(self):
        """Test FunctionMetrics can be created."""
        metrics = FunctionMetrics(
            average_length=15.5,
            max_length=100,
            average_complexity=5.2,
            max_complexity=20,
            total_functions=50,
            deeply_nested_count=3,
        )
        assert metrics.average_length == 15.5
        assert metrics.total_functions == 50


class TestCodebaseFingerprint:
    """Tests for CodebaseFingerprint dataclass."""

    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample fingerprint for testing."""
        return CodebaseFingerprint(
            directory="/test/project",
            total_files=10,
            total_lines=1000,
            naming_conventions=NamingConventions(
                function_style="snake_case",
                class_style="PascalCase",
                variable_style="snake_case",
                constant_style="UPPER_SNAKE_CASE",
                private_prefix="_",
            ),
            type_hint_coverage=TypeHintCoverage(
                functions_with_hints=8,
                total_functions=10,
                parameters_with_hints=20,
                total_parameters=25,
                return_type_coverage=80.0,
                coverage_percentage=80.0,
                style="partial",
            ),
            docstring_style=DocstringStyle(
                format="google",
                coverage_percentage=75.0,
                average_length=100,
            ),
            import_style=ImportStyle(
                prefers_from_imports=True,
                groups_imports=True,
                relative_import_usage=15.0,
            ),
            error_handling=ErrorHandlingPattern(
                uses_bare_except=False,
                exception_specificity="specific",
                try_block_count=15,
            ),
            test_coverage=TestCoverage(
                has_tests=True,
                test_framework="pytest",
                test_file_count=5,
                test_to_source_ratio=0.5,
                uses_fixtures=True,
                uses_mocks=True,
            ),
            function_metrics=FunctionMetrics(
                average_length=15.5,
                max_length=100,
                average_complexity=5.2,
                max_complexity=20,
                total_functions=50,
                deeply_nested_count=3,
            ),
        )

    def test_fingerprint_to_json(self, sample_fingerprint):
        """Test fingerprint can be serialized to JSON."""
        json_str = sample_fingerprint.to_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["directory"] == "/test/project"
        assert data["total_files"] == 10

    def test_fingerprint_from_json(self, sample_fingerprint):
        """Test fingerprint can be deserialized from JSON."""
        json_str = sample_fingerprint.to_json()
        restored = CodebaseFingerprint.from_json(json_str)

        assert restored.directory == sample_fingerprint.directory
        assert restored.total_files == sample_fingerprint.total_files
        assert restored.naming_conventions.function_style == "snake_case"

    def test_fingerprint_to_dict(self, sample_fingerprint):
        """Test fingerprint can be converted to dictionary."""
        data = sample_fingerprint.to_dict()
        assert isinstance(data, dict)
        assert "naming_conventions" in data
        assert "type_hint_coverage" in data


class TestDNAExtractor:
    """Tests for DNAExtractor class."""

    @pytest.fixture
    def temp_codebase(self):
        """Create a temporary codebase for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extractor_creation(self, temp_codebase):
        """Test extractor can be created."""
        extractor = DNAExtractor(str(temp_codebase))
        assert extractor.directory == temp_codebase

    def test_extract_empty_directory(self, temp_codebase):
        """Test extraction from empty directory."""
        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.total_files == 0
        assert fingerprint.total_lines == 0

    def test_extract_single_file(self, temp_codebase):
        """Test extraction from directory with single file."""
        # Create a Python file
        (temp_codebase / "test.py").write_text('''
def hello_world():
    """Say hello."""
    print("Hello, World!")
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.total_files == 1
        assert fingerprint.total_lines > 0

    def test_extract_detects_naming_conventions(self, temp_codebase):
        """Test extractor detects naming conventions."""
        # Create file with snake_case functions
        (temp_codebase / "utils.py").write_text('''
def get_user_name():
    pass

def calculate_total_price():
    pass

def validate_input_data():
    pass

class UserService:
    pass

class OrderManager:
    pass
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.naming_conventions.function_style == "snake_case"
        assert fingerprint.naming_conventions.class_style == "PascalCase"

    def test_extract_detects_type_hints(self, temp_codebase):
        """Test extractor detects type hint coverage."""
        (temp_codebase / "typed.py").write_text('''
def add(x: int, y: int) -> int:
    return x + y

def multiply(x: float, y: float) -> float:
    return x * y

def no_hints(a, b):
    return a + b
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.type_hint_coverage.total_functions == 3
        assert fingerprint.type_hint_coverage.functions_with_hints >= 2

    def test_extract_detects_docstring_style(self, temp_codebase):
        """Test extractor detects docstring style."""
        (temp_codebase / "documented.py").write_text('''
def process_data(items: list) -> dict:
    """Process a list of items.

    Args:
        items: List of items to process.

    Returns:
        Dictionary with processed data.
    """
    return {}

def calculate(x, y):
    """Calculate something.

    Args:
        x: First value.
        y: Second value.

    Returns:
        The result.
    """
    return x + y
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.docstring_style.format == "google"

    def test_extract_detects_import_style(self, temp_codebase):
        """Test extractor detects import style."""
        (temp_codebase / "imports.py").write_text('''
from os import path
from typing import List, Dict
from pathlib import Path

import json
import sys

def test():
    pass
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        # More from-imports than regular imports
        assert fingerprint.import_style.prefers_from_imports is True

    def test_extract_detects_error_handling(self, temp_codebase):
        """Test extractor detects error handling patterns."""
        (temp_codebase / "errors.py").write_text('''
def safe_function():
    try:
        result = risky_operation()
    except ValueError as e:
        handle_error(e)
    except TypeError as e:
        handle_type_error(e)
    return result

def another_function():
    try:
        do_something()
    except OSError:
        pass
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.error_handling.uses_bare_except is False
        assert fingerprint.error_handling.try_block_count >= 2

    def test_extract_detects_test_framework(self, temp_codebase):
        """Test extractor detects test framework."""
        # Create test directory
        test_dir = temp_codebase / "tests"
        test_dir.mkdir()
        (test_dir / "test_example.py").write_text('''
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_something(sample_data):
    assert sample_data["key"] == "value"
''')

        # Create source file
        (temp_codebase / "main.py").write_text('''
def main():
    pass
''')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        assert fingerprint.test_coverage.has_tests is True
        assert fingerprint.test_coverage.test_framework == "pytest"
        assert fingerprint.test_coverage.uses_fixtures is True

    def test_extract_skips_excluded_directories(self, temp_codebase):
        """Test extractor skips __pycache__ and other excluded directories."""
        # Create normal file
        (temp_codebase / "main.py").write_text('def main(): pass')

        # Create __pycache__ with files
        pycache = temp_codebase / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-39.pyc").write_text('# compiled')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        # Should only count main.py, not files in __pycache__
        assert fingerprint.total_files == 1


class TestAnomalySeverity:
    """Tests for AnomalySeverity enum."""

    def test_severity_levels(self):
        """Test all severity levels are defined."""
        assert AnomalySeverity.INFO
        assert AnomalySeverity.WARNING
        assert AnomalySeverity.STYLE_VIOLATION


class TestAnomaly:
    """Tests for Anomaly dataclass."""

    def test_anomaly_creation(self):
        """Test Anomaly can be created."""
        anomaly = Anomaly(
            pattern_name="naming_convention",
            expected="snake_case",
            actual="camelCase",
            severity=AnomalySeverity.STYLE_VIOLATION,
            suggestion="Use snake_case for function names",
        )
        assert anomaly.pattern_name == "naming_convention"
        assert anomaly.severity == AnomalySeverity.STYLE_VIOLATION

    def test_anomaly_with_line_number(self):
        """Test Anomaly can include line number."""
        anomaly = Anomaly(
            pattern_name="type_hints",
            expected="type hints",
            actual="no type hints",
            severity=AnomalySeverity.INFO,
            suggestion="Add type hints",
            line_number=42,
        )
        assert anomaly.line_number == 42

    def test_anomaly_to_dict(self):
        """Test Anomaly can be converted to dictionary."""
        anomaly = Anomaly(
            pattern_name="test",
            expected="expected",
            actual="actual",
            severity=AnomalySeverity.WARNING,
            suggestion="suggestion",
        )
        data = anomaly.to_dict()
        assert data["pattern_name"] == "test"
        assert data["severity"] == "WARNING"


class TestDNAAnalyzer:
    """Tests for DNAAnalyzer class."""

    @pytest.fixture
    def sample_fingerprint(self):
        """Create a sample fingerprint for testing."""
        return CodebaseFingerprint(
            directory="/test/project",
            total_files=10,
            total_lines=1000,
            naming_conventions=NamingConventions(
                function_style="snake_case",
                class_style="PascalCase",
                variable_style="snake_case",
                constant_style="UPPER_SNAKE_CASE",
                private_prefix="_",
            ),
            type_hint_coverage=TypeHintCoverage(
                functions_with_hints=9,
                total_functions=10,
                parameters_with_hints=45,
                total_parameters=50,
                return_type_coverage=90.0,
                coverage_percentage=90.0,
                style="full",
            ),
            docstring_style=DocstringStyle(
                format="google",
                coverage_percentage=80.0,
                average_length=100,
            ),
            import_style=ImportStyle(
                prefers_from_imports=True,
                groups_imports=True,
                relative_import_usage=25.0,
            ),
            error_handling=ErrorHandlingPattern(
                uses_bare_except=False,
                exception_specificity="specific",
                try_block_count=20,
            ),
            test_coverage=TestCoverage(
                has_tests=True,
                test_framework="pytest",
                test_file_count=10,
                test_to_source_ratio=1.0,
                uses_fixtures=True,
                uses_mocks=True,
            ),
            function_metrics=FunctionMetrics(
                average_length=15.0,
                max_length=50,
                average_complexity=4.0,
                max_complexity=15,
                total_functions=100,
                deeply_nested_count=2,
            ),
        )

    @pytest.fixture
    def analyzer(self, sample_fingerprint):
        """Create a DNAAnalyzer for testing."""
        return DNAAnalyzer(sample_fingerprint)

    def test_analyzer_creation(self, analyzer, sample_fingerprint):
        """Test analyzer can be created."""
        assert analyzer.fingerprint == sample_fingerprint

    def test_compare_returns_anomalies(self, analyzer):
        """Test compare returns list of anomalies."""
        code = "def foo(): pass"
        anomalies = analyzer.compare(code)
        assert isinstance(anomalies, list)

    def test_detect_naming_convention_violation(self, analyzer):
        """Test analyzer detects naming convention violations."""
        code = '''
def camelCaseFunction():
    pass
'''
        anomalies = analyzer.compare(code)
        naming_violations = [a for a in anomalies if a.pattern_name == "naming_convention"]
        assert len(naming_violations) > 0
        assert any("camelCaseFunction" in str(a.actual) for a in naming_violations)

    def test_detect_class_naming_violation(self, analyzer):
        """Test analyzer detects class naming violations."""
        code = '''
class snake_case_class:
    pass
'''
        anomalies = analyzer.compare(code)
        naming_violations = [a for a in anomalies if a.pattern_name == "naming_convention"]
        assert len(naming_violations) > 0

    def test_detect_missing_type_hints(self, analyzer):
        """Test analyzer detects missing type hints in full-coverage codebase."""
        code = '''
def process_data(items, count):
    return items[:count]
'''
        anomalies = analyzer.compare(code)
        type_violations = [a for a in anomalies if a.pattern_name == "type_hints"]
        assert len(type_violations) > 0

    def test_detect_missing_docstring(self, analyzer):
        """Test analyzer detects missing docstrings."""
        code = '''
def important_public_function(data):
    return process(data)
'''
        anomalies = analyzer.compare(code)
        docstring_violations = [a for a in anomalies if "docstring" in a.pattern_name]
        assert len(docstring_violations) > 0

    def test_detect_bare_except(self, analyzer):
        """Test analyzer detects bare except clauses."""
        code = '''
def risky():
    try:
        do_something()
    except:
        pass
'''
        anomalies = analyzer.compare(code)
        error_violations = [a for a in anomalies if a.pattern_name == "error_handling"]
        assert len(error_violations) > 0
        assert any("bare" in str(a.actual).lower() for a in error_violations)

    def test_detect_outdated_idioms(self, analyzer):
        """Test analyzer detects outdated Python idioms."""
        code = '''
x = "Hello, %s" % name
if x == None:
    pass
'''
        anomalies = analyzer.compare(code)
        idiom_violations = [a for a in anomalies if a.pattern_name == "outdated_idiom"]
        assert len(idiom_violations) > 0

    def test_detect_copy_paste_indicators(self, analyzer):
        """Test analyzer detects copy-paste indicators."""
        code = '''
# Copied from Stack Overflow
def some_function():
    # Source: https://stackoverflow.com/questions/123
    pass
'''
        anomalies = analyzer.compare(code)
        copy_violations = [a for a in anomalies if a.pattern_name == "copy_paste_indicator"]
        assert len(copy_violations) > 0

    def test_detect_ai_generated_indicators(self, analyzer):
        """Test analyzer detects AI-generated code indicators."""
        code = '''
# Generated by Claude
def ai_function():
    pass
'''
        anomalies = analyzer.compare(code)
        ai_violations = [a for a in anomalies if a.pattern_name == "ai_generated_indicator"]
        assert len(ai_violations) > 0

    def test_syntax_error_handling(self, analyzer):
        """Test analyzer handles syntax errors gracefully."""
        code = '''
def broken(
    pass  # Missing closing paren
'''
        anomalies = analyzer.compare(code)
        syntax_errors = [a for a in anomalies if a.pattern_name == "syntax_error"]
        assert len(syntax_errors) > 0

    def test_get_style_match_percentage_perfect_code(self, analyzer):
        """Test style match percentage for perfect code."""
        code = '''
def calculate_total(items: list) -> int:
    """Calculate the total of items.

    Args:
        items: List of numbers to sum.

    Returns:
        The sum of all items.
    """
    return sum(items)
'''
        percentage = analyzer.get_style_match_percentage(code)
        assert percentage >= 50  # Should be reasonably high

    def test_get_style_match_percentage_bad_code(self, analyzer):
        """Test style match percentage for non-conforming code."""
        code = '''
# Copied from Stack Overflow
def badCamelCase():
    try:
        x = None
        if x == None:
            pass
    except:
        pass
'''
        percentage = analyzer.get_style_match_percentage(code)
        assert percentage < 80  # Should be penalized

    def test_summarize_anomalies(self, analyzer):
        """Test anomaly summarization."""
        anomalies = [
            Anomaly(
                pattern_name="naming",
                expected="snake_case",
                actual="camelCase",
                severity=AnomalySeverity.STYLE_VIOLATION,
                suggestion="Fix it",
            ),
            Anomaly(
                pattern_name="naming",
                expected="snake_case",
                actual="camelCase2",
                severity=AnomalySeverity.STYLE_VIOLATION,
                suggestion="Fix it",
            ),
            Anomaly(
                pattern_name="type_hints",
                expected="hints",
                actual="no hints",
                severity=AnomalySeverity.WARNING,
                suggestion="Add hints",
            ),
        ]
        summary = analyzer.summarize_anomalies(anomalies)

        assert summary["total"] == 3
        assert summary["by_severity"]["STYLE_VIOLATION"] == 2
        assert summary["by_severity"]["WARNING"] == 1
        assert summary["by_pattern"]["naming"] == 2


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_codebase(self):
        """Create a temporary codebase for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extract_with_unparseable_file(self, temp_codebase):
        """Test extraction handles unparseable files gracefully."""
        # Create a valid file
        (temp_codebase / "valid.py").write_text('def valid(): pass')

        # Create an invalid Python file
        (temp_codebase / "invalid.py").write_text('def broken(\n# missing close paren')

        extractor = DNAExtractor(str(temp_codebase))
        fingerprint = extractor.extract()

        # Should count only valid file
        assert fingerprint.total_files == 2  # Both found
        # But only valid one parsed

    def test_extract_with_binary_file(self, temp_codebase):
        """Test extraction handles binary files gracefully."""
        # Create a Python file
        (temp_codebase / "main.py").write_text('def main(): pass')

        # Create a file with binary content but .py extension (edge case)
        (temp_codebase / "binary.py").write_bytes(b'\x89PNG\r\n\x1a\n')

        extractor = DNAExtractor(str(temp_codebase))
        # Should not crash
        fingerprint = extractor.extract()
        assert fingerprint.total_files >= 1

    def test_analyze_empty_code(self):
        """Test analyzing empty code."""
        fingerprint = CodebaseFingerprint(
            directory="/test",
            total_files=1,
            total_lines=100,
            naming_conventions=NamingConventions(
                function_style="snake_case",
                class_style="PascalCase",
                variable_style="snake_case",
                constant_style="UPPER_SNAKE_CASE",
                private_prefix="_",
            ),
            type_hint_coverage=TypeHintCoverage(
                functions_with_hints=1,
                total_functions=1,
                parameters_with_hints=2,
                total_parameters=2,
                return_type_coverage=100.0,
                coverage_percentage=100.0,
                style="full",
            ),
            docstring_style=DocstringStyle(
                format="google",
                coverage_percentage=100.0,
                average_length=50,
            ),
            import_style=ImportStyle(
                prefers_from_imports=True,
                groups_imports=True,
                relative_import_usage=10.0,
            ),
            error_handling=ErrorHandlingPattern(
                uses_bare_except=False,
                exception_specificity="specific",
                try_block_count=1,
            ),
            test_coverage=TestCoverage(
                has_tests=True,
                test_framework="pytest",
                test_file_count=1,
                test_to_source_ratio=1.0,
                uses_fixtures=True,
                uses_mocks=True,
            ),
            function_metrics=FunctionMetrics(
                average_length=10.0,
                max_length=20,
                average_complexity=2.0,
                max_complexity=5,
                total_functions=10,
                deeply_nested_count=0,
            ),
        )

        analyzer = DNAAnalyzer(fingerprint)
        anomalies = analyzer.compare("")
        # Empty code should have no anomalies (nothing to check)
        assert isinstance(anomalies, list)

    def test_analyze_only_comments(self):
        """Test analyzing code that is only comments."""
        fingerprint = CodebaseFingerprint(
            directory="/test",
            total_files=1,
            total_lines=100,
            naming_conventions=NamingConventions(
                function_style="snake_case",
                class_style="PascalCase",
                variable_style="snake_case",
                constant_style="UPPER_SNAKE_CASE",
                private_prefix="_",
            ),
            type_hint_coverage=TypeHintCoverage(
                functions_with_hints=1,
                total_functions=1,
                parameters_with_hints=2,
                total_parameters=2,
                return_type_coverage=100.0,
                coverage_percentage=100.0,
                style="full",
            ),
            docstring_style=DocstringStyle(
                format="google",
                coverage_percentage=100.0,
                average_length=50,
            ),
            import_style=ImportStyle(
                prefers_from_imports=True,
                groups_imports=True,
                relative_import_usage=10.0,
            ),
            error_handling=ErrorHandlingPattern(
                uses_bare_except=False,
                exception_specificity="specific",
                try_block_count=1,
            ),
            test_coverage=TestCoverage(
                has_tests=True,
                test_framework="pytest",
                test_file_count=1,
                test_to_source_ratio=1.0,
                uses_fixtures=True,
                uses_mocks=True,
            ),
            function_metrics=FunctionMetrics(
                average_length=10.0,
                max_length=20,
                average_complexity=2.0,
                max_complexity=5,
                total_functions=10,
                deeply_nested_count=0,
            ),
        )

        analyzer = DNAAnalyzer(fingerprint)
        code = '''
# This is just a comment
# Another comment
# Yet another comment
'''
        anomalies = analyzer.compare(code)
        assert isinstance(anomalies, list)
