"""Review caching to avoid duplicate API calls."""
import hashlib
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path

from src.config import DATABASE_PATH


# Default cache TTL: 1 hour
DEFAULT_CACHE_TTL_SECONDS = 3600


@dataclass
class CachedReview:
    """Cached review result."""
    code_hash: str
    persona: str
    issues: List[Dict[str, Any]]
    suggestions: List[str]
    severity: str
    confidence: float
    summary: str
    created_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        """Check if this cached review has expired."""
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issues": self.issues,
            "suggestions": self.suggestions,
            "severity": self.severity,
            "confidence": self.confidence,
            "summary": self.summary,
        }


class ReviewCache:
    """SQLite-backed cache for review results."""

    def __init__(self, db_path: Optional[Path] = None, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        """Initialize cache.

        Args:
            db_path: Path to SQLite database. Defaults to DATABASE_PATH from config.
            ttl_seconds: Cache TTL in seconds. Defaults to 1 hour.
        """
        self.db_path = db_path or DATABASE_PATH
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize cache table."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_hash TEXT NOT NULL,
                    persona TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    UNIQUE(code_hash, persona)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_review_cache_lookup
                ON review_cache(code_hash, persona)
            """)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def hash_code(code: str, context: Optional[str] = None) -> str:
        """Generate a hash for code + context combination.

        Args:
            code: The code to hash
            context: Optional context to include in hash

        Returns:
            SHA256 hash string
        """
        content = code
        if context:
            content = f"{context}\n---\n{code}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, code_hash: str, persona: str) -> Optional[CachedReview]:
        """Get cached review if it exists and is not expired.

        Args:
            code_hash: Hash of the code
            persona: Name of the persona/agent

        Returns:
            CachedReview if found and valid, None otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM review_cache
                WHERE code_hash = ? AND persona = ?
                """,
                (code_hash, persona)
            )
            row = cursor.fetchone()

            if not row:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                # Expired - delete it
                cursor.execute(
                    "DELETE FROM review_cache WHERE code_hash = ? AND persona = ?",
                    (code_hash, persona)
                )
                conn.commit()
                return None

            result_data = json.loads(row["result_json"])
            return CachedReview(
                code_hash=row["code_hash"],
                persona=row["persona"],
                issues=result_data.get("issues", []),
                suggestions=result_data.get("suggestions", []),
                severity=result_data.get("severity", "LOW"),
                confidence=result_data.get("confidence", 0.8),
                summary=result_data.get("summary", ""),
                created_at=datetime.fromisoformat(row["created_at"]),
                expires_at=expires_at,
            )
        finally:
            conn.close()

    def set(
        self,
        code_hash: str,
        persona: str,
        issues: List[Dict[str, Any]],
        suggestions: List[str],
        severity: str,
        confidence: float,
        summary: str,
        ttl_seconds: Optional[int] = None
    ) -> CachedReview:
        """Cache a review result.

        Args:
            code_hash: Hash of the code
            persona: Name of the persona/agent
            issues: List of issues found
            suggestions: List of suggestions
            severity: Overall severity rating
            confidence: Confidence score
            summary: Review summary
            ttl_seconds: Optional custom TTL, uses default if not provided

        Returns:
            The cached review object
        """
        ttl = ttl_seconds or self.ttl_seconds
        now = datetime.now()
        expires_at = now + timedelta(seconds=ttl)

        result_json = json.dumps({
            "issues": issues,
            "suggestions": suggestions,
            "severity": severity,
            "confidence": confidence,
            "summary": summary,
        })

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO review_cache
                (code_hash, persona, result_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (code_hash, persona, result_json, now.isoformat(), expires_at.isoformat())
            )
            conn.commit()

            return CachedReview(
                code_hash=code_hash,
                persona=persona,
                issues=issues,
                suggestions=suggestions,
                severity=severity,
                confidence=confidence,
                summary=summary,
                created_at=now,
                expires_at=expires_at,
            )
        finally:
            conn.close()

    def invalidate(self, code_hash: str, persona: Optional[str] = None):
        """Invalidate cached reviews.

        Args:
            code_hash: Hash of the code
            persona: Optional persona to invalidate. If None, invalidates all for this code.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if persona:
                cursor.execute(
                    "DELETE FROM review_cache WHERE code_hash = ? AND persona = ?",
                    (code_hash, persona)
                )
            else:
                cursor.execute(
                    "DELETE FROM review_cache WHERE code_hash = ?",
                    (code_hash,)
                )
            conn.commit()
        finally:
            conn.close()

    def clear_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute(
                "DELETE FROM review_cache WHERE expires_at < ?",
                (now,)
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def clear_all(self) -> int:
        """Remove all cache entries.

        Returns:
            Number of entries removed
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM review_cache")
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total entries
            cursor.execute("SELECT COUNT(*) as count FROM review_cache")
            total = cursor.fetchone()["count"]

            # Expired entries
            now = datetime.now().isoformat()
            cursor.execute(
                "SELECT COUNT(*) as count FROM review_cache WHERE expires_at < ?",
                (now,)
            )
            expired = cursor.fetchone()["count"]

            # Entries by persona
            cursor.execute(
                """
                SELECT persona, COUNT(*) as count
                FROM review_cache
                GROUP BY persona
                """
            )
            by_persona = {row["persona"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_entries": total,
                "expired_entries": expired,
                "valid_entries": total - expired,
                "by_persona": by_persona,
                "ttl_seconds": self.ttl_seconds,
            }
        finally:
            conn.close()


# Singleton instance for convenience
_cache_instance: Optional[ReviewCache] = None


def get_cache(ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> ReviewCache:
    """Get the singleton cache instance.

    Args:
        ttl_seconds: Cache TTL in seconds

    Returns:
        ReviewCache singleton instance
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ReviewCache(ttl_seconds=ttl_seconds)
    return _cache_instance


def get_cached_review(
    code: str,
    persona: str,
    context: Optional[str] = None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
) -> Optional[CachedReview]:
    """Convenience function to get a cached review.

    Args:
        code: The code that was reviewed
        persona: Name of the persona/agent
        context: Optional context for the review
        ttl_seconds: Cache TTL in seconds

    Returns:
        CachedReview if found and valid, None otherwise
    """
    cache = get_cache(ttl_seconds)
    code_hash = ReviewCache.hash_code(code, context)
    return cache.get(code_hash, persona)


def cache_review(
    code: str,
    persona: str,
    issues: List[Dict[str, Any]],
    suggestions: List[str],
    severity: str,
    confidence: float,
    summary: str,
    context: Optional[str] = None,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
) -> CachedReview:
    """Convenience function to cache a review result.

    Args:
        code: The code that was reviewed
        persona: Name of the persona/agent
        issues: List of issues found
        suggestions: List of suggestions
        severity: Overall severity rating
        confidence: Confidence score
        summary: Review summary
        context: Optional context for the review
        ttl_seconds: Cache TTL in seconds

    Returns:
        The cached review object
    """
    cache = get_cache(ttl_seconds)
    code_hash = ReviewCache.hash_code(code, context)
    return cache.set(
        code_hash=code_hash,
        persona=persona,
        issues=issues,
        suggestions=suggestions,
        severity=severity,
        confidence=confidence,
        summary=summary,
        ttl_seconds=ttl_seconds,
    )
