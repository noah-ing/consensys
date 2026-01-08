# Consensys - Multi-agent code review with AI debate
# This module provides the public API for the consensys package.

# Re-export the version
from src import __version__

# Re-export main CLI entry point
from src.cli import main, cli

# Re-export key components for programmatic use
from src.orchestrator.debate import DebateOrchestrator
from src.db.storage import Storage
from src.agents.agent import Agent
from src.agents.personas import PERSONAS, PERSONAS_BY_NAME, Persona
from src.models.review import Review, Response, Vote, Consensus, VoteDecision

__all__ = [
    "__version__",
    "main",
    "cli",
    "DebateOrchestrator",
    "Storage",
    "Agent",
    "PERSONAS",
    "PERSONAS_BY_NAME",
    "Persona",
    "Review",
    "Response",
    "Vote",
    "Consensus",
    "VoteDecision",
]
