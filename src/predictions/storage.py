"""SQLite storage for prediction market data."""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.config import DATABASE_PATH
from src.predictions.models import (
    Prediction,
    Bet,
    Outcome,
    AgentScore,
    PredictionType,
    OutcomeResult,
)


class PredictionStorage:
    """SQLite storage for prediction market data."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database. Defaults to DATABASE_PATH from config.
        """
        self.db_path = db_path or DATABASE_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables for prediction market."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Predictions table - tracks predictions about code
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    code_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    prediction_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Bets table - tracks bets on predictions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    bet_id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    prediction_id TEXT NOT NULL,
                    tokens_wagered INTEGER NOT NULL,
                    predicted_outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
                )
            """)

            # Outcomes table - resolved prediction outcomes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    prediction_id TEXT NOT NULL UNIQUE,
                    actual_result TEXT NOT NULL,
                    resolved_at TEXT NOT NULL,
                    incident_link TEXT,
                    FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
                )
            """)

            # Agent scores table - tracks agent performance
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_scores (
                    agent_name TEXT PRIMARY KEY,
                    tokens INTEGER NOT NULL DEFAULT 1000,
                    total_bets INTEGER NOT NULL DEFAULT 0,
                    wins INTEGER NOT NULL DEFAULT 0,
                    losses INTEGER NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL
                )
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_predictions_code_hash
                ON predictions(code_hash)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bets_prediction
                ON bets(prediction_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bets_agent
                ON bets(agent_name)
            """)

            conn.commit()
        finally:
            conn.close()

    # Prediction operations
    def save_prediction(self, prediction: Prediction) -> str:
        """Save a prediction to the database.

        Args:
            prediction: The prediction to save

        Returns:
            The prediction ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictions
                (prediction_id, code_hash, file_path, prediction_type, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    prediction.prediction_id,
                    prediction.code_hash,
                    prediction.file_path,
                    prediction.prediction_type.value,
                    prediction.confidence,
                    (prediction.timestamp or datetime.now()).isoformat()
                )
            )
            conn.commit()
            return prediction.prediction_id
        finally:
            conn.close()

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """Get a prediction by ID.

        Args:
            prediction_id: The prediction ID

        Returns:
            Prediction object or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM predictions WHERE prediction_id = ?",
                (prediction_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return Prediction(
                prediction_id=row["prediction_id"],
                code_hash=row["code_hash"],
                file_path=row["file_path"],
                prediction_type=PredictionType(row["prediction_type"]),
                confidence=row["confidence"],
                timestamp=datetime.fromisoformat(row["created_at"])
            )
        finally:
            conn.close()

    def list_predictions(self, resolved: Optional[bool] = None, limit: int = 50) -> List[Prediction]:
        """List predictions with optional filter for resolved/unresolved.

        Args:
            resolved: If True, only resolved; if False, only unresolved; if None, all
            limit: Maximum number of predictions to return

        Returns:
            List of Prediction objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if resolved is None:
                cursor.execute(
                    """
                    SELECT * FROM predictions
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            elif resolved:
                cursor.execute(
                    """
                    SELECT p.* FROM predictions p
                    INNER JOIN outcomes o ON p.prediction_id = o.prediction_id
                    ORDER BY p.created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            else:
                cursor.execute(
                    """
                    SELECT p.* FROM predictions p
                    LEFT JOIN outcomes o ON p.prediction_id = o.prediction_id
                    WHERE o.outcome_id IS NULL
                    ORDER BY p.created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )

            predictions = []
            for row in cursor.fetchall():
                predictions.append(Prediction(
                    prediction_id=row["prediction_id"],
                    code_hash=row["code_hash"],
                    file_path=row["file_path"],
                    prediction_type=PredictionType(row["prediction_type"]),
                    confidence=row["confidence"],
                    timestamp=datetime.fromisoformat(row["created_at"])
                ))
            return predictions
        finally:
            conn.close()

    # Bet operations
    def save_bet(self, bet: Bet) -> str:
        """Save a bet to the database.

        Args:
            bet: The bet to save

        Returns:
            The bet ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO bets
                (bet_id, agent_name, prediction_id, tokens_wagered, predicted_outcome, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bet.bet_id,
                    bet.agent_name,
                    bet.prediction_id,
                    bet.tokens_wagered,
                    bet.predicted_outcome.value,
                    (bet.timestamp or datetime.now()).isoformat()
                )
            )
            conn.commit()
            return bet.bet_id
        finally:
            conn.close()

    def get_bets_for_prediction(self, prediction_id: str) -> List[Bet]:
        """Get all bets for a prediction.

        Args:
            prediction_id: The prediction ID

        Returns:
            List of Bet objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bets WHERE prediction_id = ? ORDER BY created_at",
                (prediction_id,)
            )
            bets = []
            for row in cursor.fetchall():
                bets.append(Bet(
                    bet_id=row["bet_id"],
                    agent_name=row["agent_name"],
                    prediction_id=row["prediction_id"],
                    tokens_wagered=row["tokens_wagered"],
                    predicted_outcome=OutcomeResult(row["predicted_outcome"]),
                    timestamp=datetime.fromisoformat(row["created_at"])
                ))
            return bets
        finally:
            conn.close()

    def get_bets_by_agent(self, agent_name: str) -> List[Bet]:
        """Get all bets placed by an agent.

        Args:
            agent_name: The agent's name

        Returns:
            List of Bet objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bets WHERE agent_name = ? ORDER BY created_at DESC",
                (agent_name,)
            )
            bets = []
            for row in cursor.fetchall():
                bets.append(Bet(
                    bet_id=row["bet_id"],
                    agent_name=row["agent_name"],
                    prediction_id=row["prediction_id"],
                    tokens_wagered=row["tokens_wagered"],
                    predicted_outcome=OutcomeResult(row["predicted_outcome"]),
                    timestamp=datetime.fromisoformat(row["created_at"])
                ))
            return bets
        finally:
            conn.close()

    # Outcome operations
    def save_outcome(self, outcome: Outcome) -> str:
        """Save an outcome to the database.

        Args:
            outcome: The outcome to save

        Returns:
            The outcome ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO outcomes
                (outcome_id, prediction_id, actual_result, resolved_at, incident_link)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    outcome.outcome_id,
                    outcome.prediction_id,
                    outcome.actual_result.value,
                    (outcome.resolved_at or datetime.now()).isoformat(),
                    outcome.incident_link
                )
            )
            conn.commit()
            return outcome.outcome_id
        finally:
            conn.close()

    def get_outcome(self, prediction_id: str) -> Optional[Outcome]:
        """Get the outcome for a prediction.

        Args:
            prediction_id: The prediction ID

        Returns:
            Outcome object or None if not resolved
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM outcomes WHERE prediction_id = ?",
                (prediction_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            return Outcome(
                outcome_id=row["outcome_id"],
                prediction_id=row["prediction_id"],
                actual_result=OutcomeResult(row["actual_result"]),
                resolved_at=datetime.fromisoformat(row["resolved_at"]),
                incident_link=row["incident_link"]
            )
        finally:
            conn.close()

    # Agent score operations
    def get_agent_score(self, agent_name: str) -> AgentScore:
        """Get an agent's score, creating if not exists.

        Args:
            agent_name: The agent's name

        Returns:
            AgentScore object
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent_scores WHERE agent_name = ?",
                (agent_name,)
            )
            row = cursor.fetchone()
            if row:
                return AgentScore(
                    agent_name=row["agent_name"],
                    tokens=row["tokens"],
                    total_bets=row["total_bets"],
                    wins=row["wins"],
                    losses=row["losses"],
                    last_updated=datetime.fromisoformat(row["last_updated"])
                )

            # Create new agent score with default tokens
            score = AgentScore(agent_name=agent_name)
            cursor.execute(
                """
                INSERT INTO agent_scores
                (agent_name, tokens, total_bets, wins, losses, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    score.agent_name,
                    score.tokens,
                    score.total_bets,
                    score.wins,
                    score.losses,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
            return score
        finally:
            conn.close()

    def update_agent_score(self, score: AgentScore) -> None:
        """Update an agent's score.

        Args:
            score: The updated score
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO agent_scores
                (agent_name, tokens, total_bets, wins, losses, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    score.agent_name,
                    score.tokens,
                    score.total_bets,
                    score.wins,
                    score.losses,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
        finally:
            conn.close()

    def get_leaderboard(self, limit: int = 10) -> List[AgentScore]:
        """Get agents ranked by accuracy.

        Args:
            limit: Maximum number of agents to return

        Returns:
            List of AgentScore objects sorted by accuracy
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Sort by accuracy (wins/total_bets), then by tokens
            cursor.execute(
                """
                SELECT * FROM agent_scores
                WHERE total_bets > 0
                ORDER BY (CAST(wins AS REAL) / total_bets) DESC, tokens DESC
                LIMIT ?
                """,
                (limit,)
            )
            scores = []
            for row in cursor.fetchall():
                scores.append(AgentScore(
                    agent_name=row["agent_name"],
                    tokens=row["tokens"],
                    total_bets=row["total_bets"],
                    wins=row["wins"],
                    losses=row["losses"],
                    last_updated=datetime.fromisoformat(row["last_updated"])
                ))
            return scores
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics for the prediction market.

        Returns:
            Dict with statistics
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total predictions
            cursor.execute("SELECT COUNT(*) as count FROM predictions")
            total_predictions = cursor.fetchone()["count"]

            # Resolved predictions
            cursor.execute("SELECT COUNT(*) as count FROM outcomes")
            resolved_predictions = cursor.fetchone()["count"]

            # Total bets
            cursor.execute("SELECT COUNT(*) as count FROM bets")
            total_bets = cursor.fetchone()["count"]

            # Total tokens wagered
            cursor.execute("SELECT COALESCE(SUM(tokens_wagered), 0) as total FROM bets")
            total_tokens_wagered = cursor.fetchone()["total"]

            # Active agents
            cursor.execute("SELECT COUNT(*) as count FROM agent_scores")
            active_agents = cursor.fetchone()["count"]

            return {
                "total_predictions": total_predictions,
                "resolved_predictions": resolved_predictions,
                "open_predictions": total_predictions - resolved_predictions,
                "total_bets": total_bets,
                "total_tokens_wagered": total_tokens_wagered,
                "active_agents": active_agents,
            }
        finally:
            conn.close()
