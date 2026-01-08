"""Performance metrics and cost tracking for API calls.

Tracks API call duration, token usage, and estimated cost for
monitoring and budget management.
"""
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager

from src.config import DATABASE_PATH


# Pricing per million tokens for Claude 3.5 Haiku (as of Jan 2025)
# https://www.anthropic.com/pricing
PRICING = {
    "claude-3-5-haiku-20241022": {
        "input_per_million": 1.00,  # $1.00 per million input tokens
        "output_per_million": 5.00,  # $5.00 per million output tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
    },
    # Default pricing for unknown models
    "default": {
        "input_per_million": 1.00,
        "output_per_million": 5.00,
    },
}


@dataclass
class APIMetric:
    """Single API call metric record."""
    id: Optional[int] = None
    session_id: str = ""
    agent_name: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0
    operation: str = ""  # review, respond, vote, fix
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class MetricsSummary:
    """Aggregated metrics summary."""
    total_calls: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_duration_ms: float = 0.0
    avg_cost_per_call: float = 0.0
    by_agent: Dict[str, Dict] = field(default_factory=dict)
    by_operation: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class CostBreakdown:
    """Cost breakdown by time period."""
    period: str  # daily, weekly, monthly
    start_date: str
    end_date: str
    total_cost_usd: float = 0.0
    total_calls: int = 0
    total_tokens: int = 0
    daily_breakdown: List[Dict] = field(default_factory=list)


class MetricsTracker:
    """Tracks and stores API call metrics in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the metrics tracker.

        Args:
            db_path: Path to SQLite database. Defaults to project database.
        """
        self.db_path = db_path or DATABASE_PATH
        self._create_table()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context management."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _create_table(self) -> None:
        """Create the api_metrics table if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_in INTEGER NOT NULL DEFAULT 0,
                    tokens_out INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    operation TEXT NOT NULL DEFAULT 'review',
                    created_at TEXT NOT NULL
                )
            """)
            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_session
                ON api_metrics(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_created
                ON api_metrics(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_agent
                ON api_metrics(agent_name)
            """)
            conn.commit()

    def calculate_cost(
        self,
        tokens_in: int,
        tokens_out: int,
        model: str = "claude-3-5-haiku-20241022"
    ) -> float:
        """Calculate cost in USD for given token counts.

        Args:
            tokens_in: Number of input tokens
            tokens_out: Number of output tokens
            model: Model name for pricing lookup

        Returns:
            Cost in USD
        """
        pricing = PRICING.get(model, PRICING["default"])
        input_cost = (tokens_in / 1_000_000) * pricing["input_per_million"]
        output_cost = (tokens_out / 1_000_000) * pricing["output_per_million"]
        return round(input_cost + output_cost, 6)

    def record_call(
        self,
        session_id: str,
        agent_name: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
        operation: str = "review",
    ) -> APIMetric:
        """Record an API call metric.

        Args:
            session_id: Review session ID
            agent_name: Name of the agent making the call
            model: Model used for the call
            tokens_in: Input token count
            tokens_out: Output token count
            duration_ms: Call duration in milliseconds
            operation: Type of operation (review, respond, vote, fix)

        Returns:
            The recorded APIMetric
        """
        cost_usd = self.calculate_cost(tokens_in, tokens_out, model)

        metric = APIMetric(
            session_id=session_id,
            agent_name=agent_name,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            operation=operation,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_metrics
                (session_id, agent_name, model, tokens_in, tokens_out,
                 duration_ms, cost_usd, operation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.session_id,
                metric.agent_name,
                metric.model,
                metric.tokens_in,
                metric.tokens_out,
                metric.duration_ms,
                metric.cost_usd,
                metric.operation,
                metric.created_at,
            ))
            conn.commit()
            metric.id = cursor.lastrowid

        return metric

    def get_session_metrics(self, session_id: str) -> List[APIMetric]:
        """Get all metrics for a specific session.

        Args:
            session_id: The session ID to query

        Returns:
            List of APIMetric records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM api_metrics
                WHERE session_id = ?
                ORDER BY created_at
            """, (session_id,))

            metrics = []
            for row in cursor.fetchall():
                metrics.append(APIMetric(
                    id=row["id"],
                    session_id=row["session_id"],
                    agent_name=row["agent_name"],
                    model=row["model"],
                    tokens_in=row["tokens_in"],
                    tokens_out=row["tokens_out"],
                    duration_ms=row["duration_ms"],
                    cost_usd=row["cost_usd"],
                    operation=row["operation"],
                    created_at=row["created_at"],
                ))
            return metrics

    def get_summary(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> MetricsSummary:
        """Get aggregated metrics summary.

        Args:
            since: Start date filter (inclusive)
            until: End date filter (inclusive)

        Returns:
            MetricsSummary with aggregated data
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Build query with optional date filter
            where_clause = ""
            params = []
            if since or until:
                conditions = []
                if since:
                    conditions.append("created_at >= ?")
                    params.append(since.isoformat())
                if until:
                    conditions.append("created_at <= ?")
                    params.append(until.isoformat())
                where_clause = "WHERE " + " AND ".join(conditions)

            # Overall totals
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_calls,
                    COALESCE(SUM(tokens_in), 0) as total_tokens_in,
                    COALESCE(SUM(tokens_out), 0) as total_tokens_out,
                    COALESCE(SUM(cost_usd), 0.0) as total_cost_usd,
                    COALESCE(AVG(duration_ms), 0.0) as avg_duration_ms
                FROM api_metrics
                {where_clause}
            """, params)
            row = cursor.fetchone()

            summary = MetricsSummary(
                total_calls=row["total_calls"],
                total_tokens_in=row["total_tokens_in"],
                total_tokens_out=row["total_tokens_out"],
                total_tokens=row["total_tokens_in"] + row["total_tokens_out"],
                total_cost_usd=round(row["total_cost_usd"], 4),
                avg_duration_ms=round(row["avg_duration_ms"], 1),
            )

            if summary.total_calls > 0:
                summary.avg_cost_per_call = round(
                    summary.total_cost_usd / summary.total_calls, 4
                )

            # By agent breakdown
            cursor.execute(f"""
                SELECT
                    agent_name,
                    COUNT(*) as calls,
                    SUM(tokens_in) as tokens_in,
                    SUM(tokens_out) as tokens_out,
                    SUM(cost_usd) as cost_usd,
                    AVG(duration_ms) as avg_duration_ms
                FROM api_metrics
                {where_clause}
                GROUP BY agent_name
            """, params)

            for row in cursor.fetchall():
                summary.by_agent[row["agent_name"]] = {
                    "calls": row["calls"],
                    "tokens_in": row["tokens_in"],
                    "tokens_out": row["tokens_out"],
                    "cost_usd": round(row["cost_usd"], 4),
                    "avg_duration_ms": round(row["avg_duration_ms"], 1),
                }

            # By operation breakdown
            cursor.execute(f"""
                SELECT
                    operation,
                    COUNT(*) as calls,
                    SUM(tokens_in) as tokens_in,
                    SUM(tokens_out) as tokens_out,
                    SUM(cost_usd) as cost_usd,
                    AVG(duration_ms) as avg_duration_ms
                FROM api_metrics
                {where_clause}
                GROUP BY operation
            """, params)

            for row in cursor.fetchall():
                summary.by_operation[row["operation"]] = {
                    "calls": row["calls"],
                    "tokens_in": row["tokens_in"],
                    "tokens_out": row["tokens_out"],
                    "cost_usd": round(row["cost_usd"], 4),
                    "avg_duration_ms": round(row["avg_duration_ms"], 1),
                }

            return summary

    def get_cost_breakdown(
        self,
        period: str = "daily",
        days: int = 30,
    ) -> CostBreakdown:
        """Get cost breakdown by time period.

        Args:
            period: Time grouping - daily, weekly, or monthly
            days: Number of days to look back

        Returns:
            CostBreakdown with time-based aggregation
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Get totals for the period
            cursor.execute("""
                SELECT
                    COUNT(*) as total_calls,
                    COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens,
                    COALESCE(SUM(cost_usd), 0.0) as total_cost_usd
                FROM api_metrics
                WHERE created_at >= ? AND created_at <= ?
            """, (start_date.isoformat(), end_date.isoformat()))
            totals = cursor.fetchone()

            # Get daily breakdown
            if period == "daily":
                date_format = "%Y-%m-%d"
            elif period == "weekly":
                # SQLite week calculation
                date_format = "%Y-W%W"
            else:  # monthly
                date_format = "%Y-%m"

            cursor.execute(f"""
                SELECT
                    strftime('{date_format}', created_at) as period,
                    COUNT(*) as calls,
                    SUM(tokens_in + tokens_out) as tokens,
                    SUM(cost_usd) as cost_usd
                FROM api_metrics
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY strftime('{date_format}', created_at)
                ORDER BY period DESC
            """, (start_date.isoformat(), end_date.isoformat()))

            daily_breakdown = []
            for row in cursor.fetchall():
                daily_breakdown.append({
                    "period": row["period"],
                    "calls": row["calls"],
                    "tokens": row["tokens"] or 0,
                    "cost_usd": round(row["cost_usd"] or 0.0, 4),
                })

            return CostBreakdown(
                period=period,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                total_cost_usd=round(totals["total_cost_usd"], 4),
                total_calls=totals["total_calls"],
                total_tokens=totals["total_tokens"],
                daily_breakdown=daily_breakdown,
            )

    def check_budget(
        self,
        budget_usd: float,
        period_days: int = 30,
    ) -> Tuple[bool, float, float]:
        """Check if spending is approaching a budget threshold.

        Args:
            budget_usd: Budget limit in USD
            period_days: Number of days for the budget period

        Returns:
            Tuple of (is_over_threshold, current_spending, percentage_used)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(cost_usd), 0.0) as total_cost
                FROM api_metrics
                WHERE created_at >= ? AND created_at <= ?
            """, (start_date.isoformat(), end_date.isoformat()))

            total_cost = cursor.fetchone()["total_cost"]
            percentage = (total_cost / budget_usd * 100) if budget_usd > 0 else 0

            # Alert at 80% threshold
            is_over_threshold = percentage >= 80

            return is_over_threshold, round(total_cost, 4), round(percentage, 1)

    def get_recent_calls(self, limit: int = 20) -> List[APIMetric]:
        """Get most recent API call metrics.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of recent APIMetric records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM api_metrics
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            metrics = []
            for row in cursor.fetchall():
                metrics.append(APIMetric(
                    id=row["id"],
                    session_id=row["session_id"],
                    agent_name=row["agent_name"],
                    model=row["model"],
                    tokens_in=row["tokens_in"],
                    tokens_out=row["tokens_out"],
                    duration_ms=row["duration_ms"],
                    cost_usd=row["cost_usd"],
                    operation=row["operation"],
                    created_at=row["created_at"],
                ))
            return metrics


# Singleton instance for convenience
_metrics_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Get the singleton MetricsTracker instance.

    Returns:
        MetricsTracker instance
    """
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = MetricsTracker()
    return _metrics_tracker


def record_api_call(
    session_id: str,
    agent_name: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    duration_ms: int,
    operation: str = "review",
) -> APIMetric:
    """Convenience function to record an API call.

    Args:
        session_id: Review session ID
        agent_name: Name of the agent
        model: Model used
        tokens_in: Input tokens
        tokens_out: Output tokens
        duration_ms: Duration in milliseconds
        operation: Operation type

    Returns:
        The recorded APIMetric
    """
    return get_metrics_tracker().record_call(
        session_id=session_id,
        agent_name=agent_name,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=duration_ms,
        operation=operation,
    )


@contextmanager
def track_api_call(
    session_id: str,
    agent_name: str,
    model: str,
    operation: str = "review",
):
    """Context manager for tracking API call metrics.

    Usage:
        with track_api_call(session_id, agent_name, model) as tracker:
            response = client.messages.create(...)
            tracker.set_tokens(response.usage.input_tokens, response.usage.output_tokens)

    Args:
        session_id: Review session ID
        agent_name: Name of the agent
        model: Model being used
        operation: Type of operation

    Yields:
        A tracker object with set_tokens() method
    """
    class CallTracker:
        def __init__(self):
            self.tokens_in = 0
            self.tokens_out = 0
            self.start_time = time.time()

        def set_tokens(self, tokens_in: int, tokens_out: int):
            self.tokens_in = tokens_in
            self.tokens_out = tokens_out

    tracker = CallTracker()
    try:
        yield tracker
    finally:
        duration_ms = int((time.time() - tracker.start_time) * 1000)
        if tracker.tokens_in > 0 or tracker.tokens_out > 0:
            record_api_call(
                session_id=session_id,
                agent_name=agent_name,
                model=model,
                tokens_in=tracker.tokens_in,
                tokens_out=tracker.tokens_out,
                duration_ms=duration_ms,
                operation=operation,
            )
