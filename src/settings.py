"""Configuration file support for Consensys.

Supports loading configuration from multiple sources with precedence:
1. CLI flags (highest priority)
2. Project-level config (.consensus.yaml or .consensus.json in repo root)
3. User-level config (~/.consensus/config.yaml)
4. Default values (lowest priority)

Config options:
- default_team: Team preset name or list of persona names
- min_severity: Minimum severity for display (LOW, MEDIUM, HIGH, CRITICAL)
- cache_ttl: Cache time-to-live in seconds (default 3600)
- model: Claude model to use (default claude-3-5-haiku-20241022)
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Try to import yaml, fall back to None if not installed
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False


# Default configuration values
DEFAULT_MODEL = "claude-3-5-haiku-20241022"
DEFAULT_CACHE_TTL = 3600  # 1 hour
DEFAULT_TEAM = "full-review"


@dataclass
class ConsensysConfig:
    """Configuration for Consensys code review.

    Attributes:
        default_team: Team preset name or list of persona names
        min_severity: Minimum severity for display
        cache_ttl: Cache time-to-live in seconds
        model: Claude model to use
        fail_on: Severity threshold for CI failure
        quick_mode: Default to quick mode
        source_files: List of files this config was loaded from
    """
    default_team: Optional[Union[str, List[str]]] = None
    min_severity: Optional[str] = None
    cache_ttl: int = DEFAULT_CACHE_TTL
    model: str = DEFAULT_MODEL
    fail_on: Optional[str] = None
    quick_mode: bool = False
    source_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "default_team": self.default_team,
            "min_severity": self.min_severity,
            "cache_ttl": self.cache_ttl,
            "model": self.model,
            "fail_on": self.fail_on,
            "quick_mode": self.quick_mode,
        }


def get_user_config_dir() -> Path:
    """Get the user-level configuration directory.

    Returns:
        Path to ~/.consensus
    """
    config_dir = Path.home() / ".consensus"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_user_config_file() -> Path:
    """Get the path to the user-level config file.

    Returns:
        Path to ~/.consensus/config.yaml
    """
    return get_user_config_dir() / "config.yaml"


def find_project_config() -> Optional[Path]:
    """Find project-level config file.

    Searches current directory and parent directories for:
    - .consensus.yaml
    - .consensus.json

    Returns:
        Path to config file if found, None otherwise
    """
    # Start from current working directory
    current = Path.cwd()

    # Search up to 10 parent directories
    for _ in range(10):
        # Check for yaml config
        yaml_config = current / ".consensus.yaml"
        if yaml_config.exists():
            return yaml_config

        # Check for json config
        json_config = current / ".consensus.json"
        if json_config.exists():
            return json_config

        # Move to parent
        parent = current.parent
        if parent == current:  # Reached root
            break
        current = parent

    return None


def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        path: Path to the YAML file

    Returns:
        Dictionary of configuration values
    """
    if not YAML_AVAILABLE:
        return {}

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_json_file(path: Path) -> Dict[str, Any]:
    """Load a JSON configuration file.

    Args:
        path: Path to the JSON file

    Returns:
        Dictionary of configuration values
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_config_file(path: Path) -> Dict[str, Any]:
    """Load a configuration file (YAML or JSON).

    Args:
        path: Path to the config file

    Returns:
        Dictionary of configuration values
    """
    if path.suffix in (".yaml", ".yml"):
        return load_yaml_file(path)
    elif path.suffix == ".json":
        return load_json_file(path)
    else:
        # Try to determine by content or name
        if ".yaml" in path.name or ".yml" in path.name:
            return load_yaml_file(path)
        return load_json_file(path)


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two configuration dictionaries.

    Override values take precedence over base values.
    None values in override do not override base values.

    Args:
        base: Base configuration
        override: Override configuration

    Returns:
        Merged configuration
    """
    result = base.copy()
    for key, value in override.items():
        if value is not None:
            result[key] = value
    return result


def load_config() -> ConsensysConfig:
    """Load configuration from all sources.

    Precedence (highest to lowest):
    1. Project-level config (.consensus.yaml or .consensus.json)
    2. User-level config (~/.consensus/config.yaml)
    3. Default values

    Returns:
        ConsensysConfig with merged values
    """
    config_data: Dict[str, Any] = {}
    source_files: List[str] = []

    # Load user-level config first (lowest precedence)
    user_config_file = get_user_config_file()
    if user_config_file.exists():
        user_data = load_config_file(user_config_file)
        config_data = merge_configs(config_data, user_data)
        source_files.append(str(user_config_file))

    # Load project-level config (higher precedence)
    project_config_file = find_project_config()
    if project_config_file:
        project_data = load_config_file(project_config_file)
        config_data = merge_configs(config_data, project_data)
        source_files.append(str(project_config_file))

    # Build ConsensysConfig with defaults
    return ConsensysConfig(
        default_team=config_data.get("default_team"),
        min_severity=config_data.get("min_severity"),
        cache_ttl=config_data.get("cache_ttl", DEFAULT_CACHE_TTL),
        model=config_data.get("model", DEFAULT_MODEL),
        fail_on=config_data.get("fail_on"),
        quick_mode=config_data.get("quick_mode", False),
        source_files=source_files,
    )


def save_user_config(config: ConsensysConfig) -> None:
    """Save configuration to user-level config file.

    Args:
        config: Configuration to save
    """
    config_file = get_user_config_file()
    data = config.to_dict()

    # Remove None values for cleaner output
    data = {k: v for k, v in data.items() if v is not None}

    if YAML_AVAILABLE:
        with open(config_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    else:
        # Fall back to JSON if yaml not available
        json_file = get_user_config_dir() / "config.json"
        with open(json_file, "w") as f:
            json.dump(data, f, indent=2)


def get_effective_config(
    cli_min_severity: Optional[str] = None,
    cli_fail_on: Optional[str] = None,
    cli_quick: Optional[bool] = None,
    cli_no_cache: Optional[bool] = None,
) -> ConsensysConfig:
    """Get effective configuration with CLI overrides.

    CLI flags take highest precedence over file-based config.

    Args:
        cli_min_severity: --min-severity CLI flag
        cli_fail_on: --fail-on CLI flag
        cli_quick: --quick CLI flag
        cli_no_cache: --no-cache CLI flag

    Returns:
        ConsensysConfig with CLI overrides applied
    """
    config = load_config()

    # Apply CLI overrides
    if cli_min_severity is not None:
        config.min_severity = cli_min_severity
    if cli_fail_on is not None:
        config.fail_on = cli_fail_on
    if cli_quick is not None:
        config.quick_mode = cli_quick

    # Note: cli_no_cache doesn't have a config equivalent,
    # it always forces fresh reviews when specified

    return config


def create_example_config(path: Optional[Path] = None) -> str:
    """Create an example configuration file content.

    Args:
        path: Optional path to write to (if None, returns content only)

    Returns:
        Example configuration as YAML string
    """
    example = """# Consensys Configuration
# Place this file in your project root as .consensus.yaml
# Or in ~/.consensus/config.yaml for user-level defaults

# Default team for reviews
# Can be a preset name: full-review, security-focused, performance-focused, quick-check
# Or a list of persona names: [SecurityExpert, PragmaticDev]
default_team: full-review

# Minimum severity to display in output
# Options: LOW, MEDIUM, HIGH, CRITICAL
# min_severity: MEDIUM

# Severity threshold for CI failure (exit code 1)
# Options: LOW, MEDIUM, HIGH, CRITICAL
# fail_on: HIGH

# Cache time-to-live in seconds (default: 3600 = 1 hour)
cache_ttl: 3600

# Claude model to use for reviews
model: claude-3-5-haiku-20241022

# Use quick mode by default (Round 1 only, no debate)
quick_mode: false
"""

    if path:
        path.write_text(example)

    return example
