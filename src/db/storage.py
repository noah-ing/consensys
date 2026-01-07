"""SQLite storage for reviews, responses, and votes."""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.config import DATABASE_PATH
from src.models.review import (
    Review,
    Response,
    Vote,
    Consensus,
    VoteDecision,
    create_session_id,
)


class Storage:
    """SQLite storage for debate history."""

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
        """Initialize database tables."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Sessions table - tracks each review session
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    code_snippet TEXT NOT NULL,
                    context TEXT,
                    created_at TEXT NOT NULL,
                    final_decision TEXT,
                    completed_at TEXT
                )
            """)

            # Reviews table - stores individual agent reviews
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    issues TEXT NOT NULL,  -- JSON array
                    suggestions TEXT NOT NULL,  -- JSON array
                    severity TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    summary TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Responses table - stores debate responses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    responding_to TEXT NOT NULL,
                    agreement_level TEXT NOT NULL,
                    points TEXT NOT NULL,  -- JSON array
                    summary TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Votes table - stores final votes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reasoning TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Consensus table - stores final consensus
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS consensus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    final_decision TEXT NOT NULL,
                    vote_counts TEXT NOT NULL,  -- JSON object
                    key_issues TEXT NOT NULL,  -- JSON array
                    accepted_suggestions TEXT NOT NULL,  -- JSON array
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reviews_session
                ON reviews(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_responses_session
                ON responses(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_votes_session
                ON votes(session_id)
            """)

            conn.commit()
        finally:
            conn.close()

    # Session operations
    def create_session(self, code: str, context: Optional[str] = None) -> str:
        """Create a new review session.

        Args:
            code: The code to be reviewed
            context: Optional context for the review

        Returns:
            The session ID
        """
        session_id = create_session_id()
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_id, code_snippet, context, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, code, context, datetime.now().isoformat())
            )
            conn.commit()
            return session_id
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details by ID.

        Args:
            session_id: The session ID

        Returns:
            Session dict or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sessions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    # Review operations
    def save_review(self, review: Review, session_id: str) -> int:
        """Save a review to the database.

        Args:
            review: The review to save
            session_id: The session this review belongs to

        Returns:
            The review ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO reviews
                (session_id, agent_name, issues, suggestions, severity, confidence, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    review.agent_name,
                    json.dumps(review.issues),
                    json.dumps(review.suggestions),
                    review.severity,
                    review.confidence,
                    review.summary,
                    (review.timestamp or datetime.now()).isoformat()
                )
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_reviews(self, session_id: str) -> List[Review]:
        """Get all reviews for a session.

        Args:
            session_id: The session ID

        Returns:
            List of Review objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reviews WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            )
            reviews = []
            for row in cursor.fetchall():
                reviews.append(Review(
                    agent_name=row["agent_name"],
                    issues=json.loads(row["issues"]),
                    suggestions=json.loads(row["suggestions"]),
                    severity=row["severity"],
                    confidence=row["confidence"],
                    summary=row["summary"] or "",
                    session_id=row["session_id"],
                    timestamp=datetime.fromisoformat(row["created_at"])
                ))
            return reviews
        finally:
            conn.close()

    # Response operations
    def save_response(self, response: Response, session_id: str) -> int:
        """Save a response to the database.

        Args:
            response: The response to save
            session_id: The session this response belongs to

        Returns:
            The response ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO responses
                (session_id, agent_name, responding_to, agreement_level, points, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    response.agent_name,
                    response.responding_to,
                    response.agreement_level,
                    json.dumps(response.points),
                    response.summary,
                    (response.timestamp or datetime.now()).isoformat()
                )
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_responses(self, session_id: str) -> List[Response]:
        """Get all responses for a session.

        Args:
            session_id: The session ID

        Returns:
            List of Response objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM responses WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(Response(
                    agent_name=row["agent_name"],
                    responding_to=row["responding_to"],
                    agreement_level=row["agreement_level"],
                    points=json.loads(row["points"]),
                    summary=row["summary"] or "",
                    session_id=row["session_id"],
                    timestamp=datetime.fromisoformat(row["created_at"])
                ))
            return responses
        finally:
            conn.close()

    # Vote operations
    def save_vote(self, vote: Vote, session_id: str) -> int:
        """Save a vote to the database.

        Args:
            vote: The vote to save
            session_id: The session this vote belongs to

        Returns:
            The vote ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Store decision as string value
            decision_str = vote.decision.value if isinstance(vote.decision, VoteDecision) else vote.decision
            cursor.execute(
                """
                INSERT INTO votes
                (session_id, agent_name, decision, reasoning, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    vote.agent_name,
                    decision_str,
                    vote.reasoning,
                    (vote.timestamp or datetime.now()).isoformat()
                )
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_votes(self, session_id: str) -> List[Vote]:
        """Get all votes for a session.

        Args:
            session_id: The session ID

        Returns:
            List of Vote objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM votes WHERE session_id = ? ORDER BY created_at",
                (session_id,)
            )
            votes = []
            for row in cursor.fetchall():
                try:
                    decision = VoteDecision(row["decision"])
                except ValueError:
                    decision = VoteDecision.ABSTAIN
                votes.append(Vote(
                    agent_name=row["agent_name"],
                    decision=decision,
                    reasoning=row["reasoning"] or "",
                    session_id=row["session_id"],
                    timestamp=datetime.fromisoformat(row["created_at"])
                ))
            return votes
        finally:
            conn.close()

    # Consensus operations
    def save_consensus(self, consensus: Consensus) -> int:
        """Save consensus to the database.

        Args:
            consensus: The consensus to save

        Returns:
            The consensus ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            decision_str = consensus.final_decision.value if isinstance(
                consensus.final_decision, VoteDecision
            ) else consensus.final_decision
            cursor.execute(
                """
                INSERT INTO consensus
                (session_id, final_decision, vote_counts, key_issues, accepted_suggestions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    consensus.session_id,
                    decision_str,
                    json.dumps(consensus.vote_counts),
                    json.dumps(consensus.key_issues),
                    json.dumps(consensus.accepted_suggestions),
                    (consensus.timestamp or datetime.now()).isoformat()
                )
            )
            # Update session with final decision
            cursor.execute(
                """
                UPDATE sessions
                SET final_decision = ?, completed_at = ?
                WHERE session_id = ?
                """,
                (decision_str, datetime.now().isoformat(), consensus.session_id)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_consensus(self, session_id: str) -> Optional[Consensus]:
        """Get consensus for a session.

        Args:
            session_id: The session ID

        Returns:
            Consensus object or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM consensus WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Get the session to get code and context
            session = self.get_session(session_id)

            try:
                decision = VoteDecision(row["final_decision"])
            except ValueError:
                decision = VoteDecision.ABSTAIN

            return Consensus(
                final_decision=decision,
                vote_counts=json.loads(row["vote_counts"]),
                key_issues=json.loads(row["key_issues"]),
                accepted_suggestions=json.loads(row["accepted_suggestions"]),
                session_id=row["session_id"],
                code_snippet=session["code_snippet"] if session else "",
                context=session["context"] if session else None,
                timestamp=datetime.fromisoformat(row["created_at"])
            )
        finally:
            conn.close()

    # Stats operations
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all sessions.

        Returns:
            Dict with statistics
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total sessions
            cursor.execute("SELECT COUNT(*) as count FROM sessions")
            total_sessions = cursor.fetchone()["count"]

            # Completed sessions
            cursor.execute(
                "SELECT COUNT(*) as count FROM sessions WHERE completed_at IS NOT NULL"
            )
            completed_sessions = cursor.fetchone()["count"]

            # Vote breakdown
            cursor.execute(
                """
                SELECT decision, COUNT(*) as count
                FROM votes
                GROUP BY decision
                """
            )
            vote_breakdown = {row["decision"]: row["count"] for row in cursor.fetchall()}

            # Agreement levels
            cursor.execute(
                """
                SELECT agreement_level, COUNT(*) as count
                FROM responses
                GROUP BY agreement_level
                """
            )
            agreement_breakdown = {
                row["agreement_level"]: row["count"] for row in cursor.fetchall()
            }

            return {
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "vote_breakdown": vote_breakdown,
                "agreement_breakdown": agreement_breakdown,
            }
        finally:
            conn.close()
