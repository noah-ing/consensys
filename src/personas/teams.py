"""Team presets and configuration for Consensys.

Teams are predefined sets of personas that work well together for
specific review purposes. Users can also set a custom team.
"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.agents.personas import Persona, PERSONAS, PERSONAS_BY_NAME


# Team presets with descriptions
TEAM_PRESETS: Dict[str, Dict[str, Any]] = {
    "full-review": {
        "description": "All 4 experts for comprehensive code review",
        "personas": ["SecurityExpert", "PerformanceEngineer", "ArchitectureCritic", "PragmaticDev"],
    },
    "security-focused": {
        "description": "Security-heavy team for sensitive code",
        "personas": ["SecurityExpert", "PragmaticDev"],
    },
    "performance-focused": {
        "description": "Performance-heavy team for optimization reviews",
        "personas": ["PerformanceEngineer", "PragmaticDev"],
    },
    "quick-check": {
        "description": "Fast review with just the pragmatic developer",
        "personas": ["PragmaticDev"],
    },
}


def get_config_dir() -> Path:
    """Get the Consensys configuration directory.

    Returns:
        Path to the configuration directory
    """
    config_dir = Path.home() / ".consensys"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_team_config_file() -> Path:
    """Get the path to the team configuration file.

    Returns:
        Path to ~/.consensys/team.json
    """
    return get_config_dir() / "team.json"


def get_active_team() -> Optional[str]:
    """Get the currently active team name.

    Returns:
        Team name if set, None for default (full-review)
    """
    config_file = get_team_config_file()

    if not config_file.exists():
        return None

    try:
        with open(config_file, "r") as f:
            data = json.load(f)
        return data.get("active_team")
    except (json.JSONDecodeError, KeyError):
        return None


def get_custom_team_personas() -> Optional[List[str]]:
    """Get custom team persona names if set.

    Returns:
        List of persona names if custom team is set, None otherwise
    """
    config_file = get_team_config_file()

    if not config_file.exists():
        return None

    try:
        with open(config_file, "r") as f:
            data = json.load(f)
        return data.get("custom_personas")
    except (json.JSONDecodeError, KeyError):
        return None


def set_active_team(team_name: Optional[str] = None, custom_personas: Optional[List[str]] = None) -> None:
    """Set the active team.

    Args:
        team_name: Name of a preset team (or None for custom)
        custom_personas: List of persona names for custom team
    """
    config_file = get_team_config_file()

    data = {
        "active_team": team_name,
        "custom_personas": custom_personas,
    }

    with open(config_file, "w") as f:
        json.dump(data, f, indent=2)


def get_team_personas(include_custom: bool = True) -> List[Persona]:
    """Get the personas for the currently active team.

    This function returns the appropriate personas based on the
    current team configuration. If no team is set, returns all
    built-in personas (full-review).

    Args:
        include_custom: Whether to include custom personas in lookups

    Returns:
        List of Persona objects for the active team
    """
    from src.personas.custom import load_custom_personas, get_persona_by_name

    team_name = get_active_team()
    custom_persona_names = get_custom_team_personas()

    # If custom team is set with specific personas
    if custom_persona_names:
        personas = []
        for name in custom_persona_names:
            persona = get_persona_by_name(name) if include_custom else PERSONAS_BY_NAME.get(name)
            if persona:
                personas.append(persona)
        return personas if personas else PERSONAS

    # If a preset team is selected
    if team_name and team_name in TEAM_PRESETS:
        preset = TEAM_PRESETS[team_name]
        personas = []
        for name in preset["personas"]:
            # Check built-in first
            if name in PERSONAS_BY_NAME:
                personas.append(PERSONAS_BY_NAME[name])
            elif include_custom:
                # Check custom personas
                persona = get_persona_by_name(name)
                if persona:
                    personas.append(persona)
        return personas if personas else PERSONAS

    # Default: full-review (all built-in personas)
    return PERSONAS


def clear_team_config() -> None:
    """Clear team configuration, resetting to default."""
    config_file = get_team_config_file()
    if config_file.exists():
        config_file.unlink()
