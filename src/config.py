"""Configuration for the Consensus code review system."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Model configuration
DEFAULT_MODEL = "claude-3-5-haiku-20241022"
MAX_TOKENS = 4096

# Database configuration
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "consensus.db"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)
