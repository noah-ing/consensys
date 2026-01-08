"""Custom persona loading and saving for Consensys.

Custom personas are stored in ~/.consensys/personas.json and can be
created interactively via the CLI.
"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.agents.personas import Persona, PERSONAS, PERSONAS_BY_NAME


def get_config_dir() -> Path:
    """Get the Consensys configuration directory.

    Creates ~/.consensys if it doesn't exist.

    Returns:
        Path to the configuration directory
    """
    config_dir = Path.home() / ".consensys"
    config_dir.mkdir(exist_ok=True)
    return config_dir


def get_personas_file() -> Path:
    """Get the path to the custom personas file.

    Returns:
        Path to ~/.consensys/personas.json
    """
    return get_config_dir() / "personas.json"


def load_custom_personas() -> List[Persona]:
    """Load custom personas from ~/.consensys/personas.json.

    Returns:
        List of custom Persona objects
    """
    personas_file = get_personas_file()

    if not personas_file.exists():
        return []

    try:
        with open(personas_file, "r") as f:
            data = json.load(f)

        personas = []
        for item in data:
            persona = Persona(
                name=item["name"],
                role=item["role"],
                system_prompt=item["system_prompt"],
                priorities=item["priorities"],
                review_style=item["review_style"],
            )
            personas.append(persona)

        return personas
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def save_custom_personas(personas: List[Persona]) -> None:
    """Save custom personas to ~/.consensys/personas.json.

    Args:
        personas: List of Persona objects to save
    """
    personas_file = get_personas_file()

    data = []
    for persona in personas:
        data.append({
            "name": persona.name,
            "role": persona.role,
            "system_prompt": persona.system_prompt,
            "priorities": persona.priorities,
            "review_style": persona.review_style,
        })

    with open(personas_file, "w") as f:
        json.dump(data, f, indent=2)


def save_custom_persona(persona: Persona) -> None:
    """Save a single custom persona, adding to existing ones.

    Args:
        persona: Persona object to save
    """
    existing = load_custom_personas()

    # Replace if exists, otherwise append
    found = False
    for i, p in enumerate(existing):
        if p.name == persona.name:
            existing[i] = persona
            found = True
            break

    if not found:
        existing.append(persona)

    save_custom_personas(existing)


def delete_custom_persona(name: str) -> bool:
    """Delete a custom persona by name.

    Args:
        name: Name of the persona to delete

    Returns:
        True if deleted, False if not found
    """
    existing = load_custom_personas()

    for i, p in enumerate(existing):
        if p.name == name:
            existing.pop(i)
            save_custom_personas(existing)
            return True

    return False


def get_all_personas() -> List[Persona]:
    """Get all personas (built-in + custom).

    Returns:
        Combined list of built-in and custom personas
    """
    custom = load_custom_personas()
    return PERSONAS + custom


def get_persona_by_name(name: str) -> Optional[Persona]:
    """Get a persona by name (checks built-in and custom).

    Args:
        name: Name of the persona

    Returns:
        Persona object or None if not found
    """
    # Check built-in first
    if name in PERSONAS_BY_NAME:
        return PERSONAS_BY_NAME[name]

    # Check custom
    for persona in load_custom_personas():
        if persona.name == name:
            return persona

    return None


def list_all_persona_names() -> List[str]:
    """Get names of all available personas.

    Returns:
        List of persona names
    """
    return [p.name for p in get_all_personas()]
