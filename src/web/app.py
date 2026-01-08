"""FastAPI web application for Consensys code review."""
import asyncio
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src.db.storage import Storage
from src.orchestrator.debate import DebateOrchestrator
from src.agents.personas import PERSONAS
from src.languages import detect_language

# FastAPI app
app = FastAPI(
    title="Consensys",
    description="Multi-agent AI code review with debate and voting",
    version="0.1.2",
)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Request/Response models
class ReviewRequest(BaseModel):
    """Request body for code review."""
    code: str
    context: Optional[str] = None
    language: Optional[str] = None
    quick: bool = False


class FixSuggestion(BaseModel):
    """A suggested fix for an issue found during review.

    Attributes:
        issue: Description of the issue
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        original_code: The problematic code snippet
        fixed_code: The suggested fix
        explanation: Why this fix resolves the issue
        line: Line number where the issue occurs (if applicable)
        agent_name: Name of the agent that suggested this fix
    """
    issue: str
    severity: str
    original_code: Optional[str] = None
    fixed_code: Optional[str] = None
    explanation: Optional[str] = None
    line: Optional[int] = None
    agent_name: Optional[str] = None


class ReviewResponse(BaseModel):
    """Response from code review.

    Attributes:
        session_id: Unique session identifier
        decision: Final verdict (APPROVE, REJECT, ABSTAIN)
        reviews: List of individual agent reviews
        consensus: Aggregated consensus data
        vote_counts: Breakdown of votes by type
        fixes: List of suggested fixes extracted from all reviews
    """
    session_id: str
    decision: str
    reviews: List[Dict[str, Any]]
    consensus: Optional[Dict[str, Any]] = None
    vote_counts: Dict[str, int]
    fixes: List[FixSuggestion] = []


class SessionSummary(BaseModel):
    """Summary of a review session."""
    session_id: str
    code_preview: str
    created_at: str
    final_decision: Optional[str] = None


class SessionDetail(BaseModel):
    """Full details of a review session.

    Attributes:
        session_id: Unique session identifier
        code: The code that was reviewed
        context: Optional context provided for the review
        created_at: Timestamp when session was created
        final_decision: Final verdict (APPROVE, REJECT, ABSTAIN)
        reviews: List of individual agent reviews
        responses: List of agent responses/rebuttals
        votes: List of agent votes
        consensus: Aggregated consensus data
        fixes: List of suggested fixes extracted from all reviews
    """
    session_id: str
    code: str
    context: Optional[str]
    created_at: str
    final_decision: Optional[str]
    reviews: List[Dict[str, Any]]
    responses: List[Dict[str, Any]]
    votes: List[Dict[str, Any]]
    consensus: Optional[Dict[str, Any]]
    fixes: List[FixSuggestion] = []


# Storage instance (will be created per-request for thread safety)
def get_storage() -> Storage:
    """Get a storage instance."""
    return Storage()


def extract_fixes_from_reviews(reviews: List[Any], review_dicts: List[Dict[str, Any]] = None) -> List[FixSuggestion]:
    """Extract fix suggestions from review issues.

    Iterates through all reviews and extracts issues that have fix suggestions,
    converting them into FixSuggestion objects.

    Args:
        reviews: List of Review objects or review dicts
        review_dicts: Optional pre-converted review dicts (for session retrieval)

    Returns:
        List of FixSuggestion objects with fix data
    """
    fixes = []

    # Use review_dicts if provided, otherwise convert reviews
    items = review_dicts if review_dicts else reviews

    for review in items:
        # Handle both Review objects and dicts
        agent_name = review.agent_name if hasattr(review, 'agent_name') else review.get('agent_name', 'Unknown')
        issues = review.issues if hasattr(review, 'issues') else review.get('issues', [])

        for issue in issues:
            # Skip issues without fix suggestions
            fix_code = issue.get('fix')
            if not fix_code:
                continue

            fixes.append(FixSuggestion(
                issue=issue.get('description', 'Unknown issue'),
                severity=issue.get('severity', 'LOW'),
                original_code=issue.get('original_code'),
                fixed_code=fix_code,
                explanation=issue.get('description'),  # Use description as explanation
                line=issue.get('line'),
                agent_name=agent_name,
            ))

    return fixes


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Check API health status."""
    return {"status": "ok", "service": "consensus", "version": "0.1.0"}


# Review endpoint
@app.post("/api/review", response_model=ReviewResponse)
async def review_code(request: ReviewRequest):
    """Submit code for review by AI agents.

    POST /api/review

    Request Body:
        code (str, required): The code to review
        context (str, optional): Additional context about the code
        language (str, optional): Programming language hint
        quick (bool, optional): If true, skip debate rounds (default: false)

    Response:
        session_id (str): Unique identifier for this review session
        decision (str): Final verdict - APPROVE, REJECT, or ABSTAIN
        reviews (list): Individual agent reviews with issues, suggestions
        consensus (dict): Aggregated consensus with vote_counts, key_issues
        vote_counts (dict): Breakdown by vote type {APPROVE, REJECT, ABSTAIN}
        fixes (list): Suggested fixes extracted from all reviews
            - issue (str): Description of the issue
            - severity (str): CRITICAL, HIGH, MEDIUM, or LOW
            - original_code (str): The problematic code snippet
            - fixed_code (str): The suggested fix
            - explanation (str): Why this fix resolves the issue
            - line (int): Line number where issue occurs
            - agent_name (str): Name of agent that suggested fix

    Example Response:
        {
            "session_id": "abc123",
            "decision": "REJECT",
            "reviews": [...],
            "consensus": {...},
            "vote_counts": {"APPROVE": 1, "REJECT": 3, "ABSTAIN": 0},
            "fixes": [
                {
                    "issue": "SQL injection vulnerability",
                    "severity": "CRITICAL",
                    "original_code": "query = f\"SELECT * FROM users WHERE id={id}\"",
                    "fixed_code": "query = \"SELECT * FROM users WHERE id=?\"; cursor.execute(query, (id,))",
                    "explanation": "Use parameterized queries to prevent SQL injection",
                    "line": 15,
                    "agent_name": "SecurityExpert"
                }
            ]
        }
    """
    # Create orchestrator with fresh storage
    storage = get_storage()

    # Detect language if provided
    language_info = None
    if request.language:
        language_info = detect_language(None, request.code)
    else:
        language_info = detect_language(None, request.code)

    # Create a quiet orchestrator (no console output for API)
    from rich.console import Console
    from io import StringIO
    quiet_console = Console(file=StringIO(), quiet=True)

    orchestrator = DebateOrchestrator(
        storage=storage,
        console=quiet_console,
        language=language_info,
    )

    # Run review in thread pool to not block
    loop = asyncio.get_event_loop()

    if request.quick:
        # Quick mode: Round 1 only
        def run_quick():
            orchestrator.start_review(request.code, request.context)
            consensus = orchestrator._build_quick_consensus()
            return (orchestrator.reviews, consensus, orchestrator.session_id)

        with ThreadPoolExecutor(max_workers=1) as executor:
            reviews, consensus, session_id = await loop.run_in_executor(
                executor, run_quick
            )
    else:
        # Full debate: reviews, responses, voting, consensus
        def run_full():
            consensus = orchestrator.run_full_debate(request.code, request.context)
            return (
                orchestrator.reviews,
                orchestrator.responses,
                orchestrator.votes,
                consensus,
                orchestrator.session_id,
            )

        with ThreadPoolExecutor(max_workers=1) as executor:
            reviews, responses, votes, consensus, session_id = await loop.run_in_executor(
                executor, run_full
            )

    # Convert reviews to dicts
    review_dicts = []
    for review in reviews:
        review_dicts.append({
            "agent_name": review.agent_name,
            "issues": review.issues,
            "suggestions": review.suggestions,
            "severity": review.severity,
            "confidence": review.confidence,
            "summary": review.summary,
        })

    # Build consensus dict
    consensus_dict = None
    vote_counts = {"APPROVE": 0, "REJECT": 0, "ABSTAIN": 0}

    if consensus:
        vote_counts = consensus.vote_counts
        consensus_dict = {
            "decision": consensus.final_decision.value if hasattr(consensus.final_decision, 'value') else str(consensus.final_decision),
            "vote_counts": consensus.vote_counts,
            "key_issues": consensus.key_issues,
            "accepted_suggestions": consensus.accepted_suggestions,
        }

    decision = consensus_dict["decision"] if consensus_dict else "PENDING"

    # Extract fixes from reviews
    fixes = extract_fixes_from_reviews(reviews)

    return ReviewResponse(
        session_id=session_id,
        decision=decision,
        reviews=review_dicts,
        consensus=consensus_dict,
        vote_counts=vote_counts,
        fixes=fixes,
    )


# List sessions
@app.get("/api/sessions")
async def list_sessions(limit: int = 50) -> List[SessionSummary]:
    """List past review sessions.

    Args:
        limit: Maximum number of sessions to return (default 50)

    Returns:
        List of session summaries
    """
    storage = get_storage()
    sessions = storage.list_sessions(limit=limit)

    result = []
    for session in sessions:
        # Create preview of code (first 100 chars)
        code = session.get("code_snippet", "")
        code_preview = code[:100] + "..." if len(code) > 100 else code

        result.append(SessionSummary(
            session_id=session["session_id"],
            code_preview=code_preview,
            created_at=session["created_at"],
            final_decision=session.get("final_decision"),
        ))

    return result


# Get session details
@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> SessionDetail:
    """Get full details of a review session.

    GET /api/sessions/{session_id}

    Path Parameters:
        session_id (str): Full or partial session ID prefix

    Response:
        session_id (str): Full session identifier
        code (str): The code that was reviewed
        context (str): Optional context provided for review
        created_at (str): ISO timestamp when session was created
        final_decision (str): APPROVE, REJECT, or ABSTAIN
        reviews (list): Individual agent reviews
        responses (list): Agent responses/rebuttals from debate
        votes (list): Individual agent votes with reasoning
        consensus (dict): Final consensus with vote_counts, key_issues
        fixes (list): Suggested fixes extracted from all reviews
            - issue (str): Description of the issue
            - severity (str): CRITICAL, HIGH, MEDIUM, or LOW
            - original_code (str): The problematic code snippet
            - fixed_code (str): The suggested fix
            - explanation (str): Why this fix resolves the issue
            - line (int): Line number where issue occurs
            - agent_name (str): Name of agent that suggested fix

    Raises:
        404: Session not found
    """
    storage = get_storage()

    # Try exact match first
    session = storage.get_session(session_id)

    # If not found, try partial match
    if not session:
        sessions = storage.list_sessions(limit=100)
        for s in sessions:
            if s["session_id"].startswith(session_id):
                session = storage.get_session(s["session_id"])
                session_id = s["session_id"]
                break

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Get all related data
    reviews = storage.get_reviews(session_id)
    responses = storage.get_responses(session_id)
    votes = storage.get_votes(session_id)
    consensus = storage.get_consensus(session_id)

    # Convert to dicts
    review_dicts = [
        {
            "agent_name": r.agent_name,
            "issues": r.issues,
            "suggestions": r.suggestions,
            "severity": r.severity,
            "confidence": r.confidence,
            "summary": r.summary,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in reviews
    ]

    response_dicts = [
        {
            "agent_name": r.agent_name,
            "responding_to": r.responding_to,
            "agreement_level": r.agreement_level.value if hasattr(r.agreement_level, 'value') else str(r.agreement_level),
            "points": r.points,
            "summary": r.summary,
        }
        for r in responses
    ]

    vote_dicts = [
        {
            "agent_name": v.agent_name,
            "decision": v.decision.value if hasattr(v.decision, 'value') else str(v.decision),
            "reasoning": v.reasoning,
        }
        for v in votes
    ]

    consensus_dict = None
    if consensus:
        consensus_dict = {
            "decision": consensus.final_decision.value if hasattr(consensus.final_decision, 'value') else str(consensus.final_decision),
            "vote_counts": consensus.vote_counts,
            "key_issues": consensus.key_issues,
            "accepted_suggestions": consensus.accepted_suggestions,
        }

    # Extract fixes from reviews
    fixes = extract_fixes_from_reviews(reviews)

    return SessionDetail(
        session_id=session_id,
        code=session["code_snippet"],
        context=session.get("context"),
        created_at=session["created_at"],
        final_decision=session.get("final_decision"),
        reviews=review_dicts,
        responses=response_dicts,
        votes=vote_dicts,
        consensus=consensus_dict,
        fixes=fixes,
    )


# WebSocket for streaming reviews
@app.websocket("/ws/review")
async def websocket_review(websocket: WebSocket):
    """WebSocket endpoint for streaming code reviews.

    Message format (client -> server):
    {
        "type": "review",
        "code": "...",
        "context": "...",
        "quick": false
    }

    Response format (server -> client):
    {
        "type": "status" | "review" | "fix" | "response" | "vote" | "consensus" | "complete" | "error",
        "data": { ... }
    }

    Fix message data format:
    {
        "type": "fix",
        "data": {
            "issue": "Description of the issue",
            "severity": "CRITICAL|HIGH|MEDIUM|LOW",
            "original_code": "problematic code",
            "fixed_code": "corrected code",
            "explanation": "why this fix resolves the issue",
            "line": 10,
            "agent_name": "SecurityExpert"
        }
    }
    """
    await websocket.accept()

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            if data.get("type") != "review":
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Unknown message type"}
                })
                continue

            code = data.get("code", "")
            context = data.get("context")
            quick = data.get("quick", False)

            if not code:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "No code provided"}
                })
                continue

            # Send status update
            await websocket.send_json({
                "type": "status",
                "data": {"message": "Starting review..."}
            })

            # Create storage and orchestrator
            storage = get_storage()
            language_info = detect_language(None, code)

            from rich.console import Console
            from io import StringIO
            quiet_console = Console(file=StringIO(), quiet=True)

            orchestrator = DebateOrchestrator(
                storage=storage,
                console=quiet_console,
                language=language_info,
            )

            # Run review with streaming updates
            loop = asyncio.get_event_loop()

            def run_review():
                orchestrator.start_review(code, context)
                return orchestrator

            # Run initial review
            await websocket.send_json({
                "type": "status",
                "data": {"message": "Agents reviewing code..."}
            })

            with ThreadPoolExecutor(max_workers=1) as executor:
                orchestrator = await loop.run_in_executor(executor, run_review)

            # Send individual reviews and stream fixes as they are found
            all_fixes = []
            for review in orchestrator.reviews:
                await websocket.send_json({
                    "type": "review",
                    "data": {
                        "agent_name": review.agent_name,
                        "issues": review.issues,
                        "suggestions": review.suggestions,
                        "severity": review.severity,
                        "confidence": review.confidence,
                        "summary": review.summary,
                    }
                })

                # Stream fixes from this review
                for issue in review.issues:
                    fix_code = issue.get('fix')
                    if fix_code:
                        fix_data = {
                            "issue": issue.get('description', 'Unknown issue'),
                            "severity": issue.get('severity', 'LOW'),
                            "original_code": issue.get('original_code'),
                            "fixed_code": fix_code,
                            "explanation": issue.get('description'),
                            "line": issue.get('line'),
                            "agent_name": review.agent_name,
                        }
                        all_fixes.append(fix_data)
                        await websocket.send_json({
                            "type": "fix",
                            "data": fix_data
                        })

            if quick:
                # Quick mode: build quick consensus
                def build_quick():
                    return orchestrator._build_quick_consensus()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    consensus = await loop.run_in_executor(executor, build_quick)
            else:
                # Full mode: run responses, voting, consensus
                await websocket.send_json({
                    "type": "status",
                    "data": {"message": "Agents debating..."}
                })

                def run_responses():
                    return orchestrator.run_responses()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    responses = await loop.run_in_executor(executor, run_responses)

                # Send responses
                for response in responses:
                    await websocket.send_json({
                        "type": "response",
                        "data": {
                            "agent_name": response.agent_name,
                            "responding_to": response.responding_to,
                            "agreement_level": response.agreement_level.value if hasattr(response.agreement_level, 'value') else str(response.agreement_level),
                            "points": response.points,
                            "summary": response.summary,
                        }
                    })

                await websocket.send_json({
                    "type": "status",
                    "data": {"message": "Agents voting..."}
                })

                def run_voting():
                    return orchestrator.run_voting()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    votes = await loop.run_in_executor(executor, run_voting)

                # Send votes
                for vote in votes:
                    await websocket.send_json({
                        "type": "vote",
                        "data": {
                            "agent_name": vote.agent_name,
                            "decision": vote.decision.value if hasattr(vote.decision, 'value') else str(vote.decision),
                            "reasoning": vote.reasoning,
                        }
                    })

                def build_consensus():
                    return orchestrator.build_consensus()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    consensus = await loop.run_in_executor(executor, build_consensus)

            # Send consensus
            consensus_data = {
                "decision": consensus.final_decision.value if hasattr(consensus.final_decision, 'value') else str(consensus.final_decision),
                "vote_counts": consensus.vote_counts,
                "key_issues": consensus.key_issues,
                "accepted_suggestions": consensus.accepted_suggestions,
            }

            await websocket.send_json({
                "type": "consensus",
                "data": consensus_data
            })

            # Send complete with all fixes included
            await websocket.send_json({
                "type": "complete",
                "data": {
                    "session_id": orchestrator.session_id,
                    "decision": consensus_data["decision"],
                    "fixes": all_fixes,
                    "fix_count": len(all_fixes),
                }
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass


# Root endpoint - serve frontend
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    else:
        return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Consensys - AI Code Review</title>
    <style>
        body { font-family: system-ui; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; }
        .api-doc { background: #f5f5f5; padding: 20px; border-radius: 8px; }
        code { background: #e0e0e0; padding: 2px 6px; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Consensys - Multi-Agent Code Review</h1>
    <div class="api-doc">
        <h2>API Endpoints</h2>
        <ul>
            <li><code>GET /api/health</code> - Health check</li>
            <li><code>POST /api/review</code> - Submit code for review</li>
            <li><code>GET /api/sessions</code> - List past sessions</li>
            <li><code>GET /api/sessions/{id}</code> - Get session details</li>
            <li><code>WebSocket /ws/review</code> - Streaming reviews</li>
        </ul>
        <p>Full frontend coming soon. See <code>/static/index.html</code></p>
    </div>
</body>
</html>
        """)


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the web server.

    Args:
        host: Host to bind to (default 0.0.0.0)
        port: Port to listen on (default 8000)
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
