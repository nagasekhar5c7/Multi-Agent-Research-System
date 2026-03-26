"""
FastAPI entry point for the Multi-Agent Research System.

Endpoints
─────────
  POST /research                     — start a new research session
  GET  /research/{session_id}        — poll status / get results
  POST /research/{session_id}/review — submit human review decision

Human-review flow
─────────────────
  1. POST /research   → graph runs until human_review interrupt → returns
  2. GET  /research/{session_id} shows status="awaiting_review" + task list
  3. Within HUMAN_REVIEW_TIMEOUT_SECONDS (120 s):
       POST /research/{session_id}/review  {"action": "approve" | "modify" | "reject",
                                            "feedback": "..."}
  4. If no review arrives in time → auto-approve and continue

Run
───
  uvicorn main:app --reload
"""

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel

from config.config import HUMAN_REVIEW_TIMEOUT_SECONDS, LOG_LEVEL
from src.app.graph.builder import research_graph

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-Agent Research System",
    description="LangGraph-powered research pipeline with human-in-the-loop review.",
    version="1.0.0",
)


# ─────────────────────────────────────────────────────────────────────────────
# In-memory session registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SessionInfo:
    session_id: str
    config: dict
    status: str = "initializing"        # initializing | running | awaiting_review
                                        # | complete | error
    interrupt_data: dict | None = None  # task list surfaced by human_review node
    review_response: dict | None = None # set by /review endpoint
    review_event: asyncio.Event = field(default_factory=asyncio.Event)
    result: dict | None = None
    error: str | None = None


# session_id → SessionInfo
_sessions: dict[str, SessionInfo] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class StartResearchRequest(BaseModel):
    research_goal: str
    user_documents: list[str] = []


class ReviewRequest(BaseModel):
    action: str   # "approve" | "modify" | "reject"
    feedback: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Background graph runner
# ─────────────────────────────────────────────────────────────────────────────

async def _run_graph(session_id: str, initial_state: dict) -> None:
    """Run the research graph to completion, handling interrupt cycles.

    The graph may pause at human_review more than once (e.g. user rejects
    → re-plan → human_review again). This loop handles every interrupt
    until the graph is fully done.
    """
    info = _sessions[session_id]
    loop = asyncio.get_event_loop()
    config = info.config

    try:
        info.status = "running"
        logger.info("Session %s: graph started", session_id)

        # ── Initial invoke ─────────────────────────────────────────────────
        result: dict[str, Any] = await loop.run_in_executor(
            None,
            lambda: research_graph.invoke(initial_state, config=config),
        )

        # ── Interrupt-resume loop ──────────────────────────────────────────
        # After each invoke(), check whether the graph is paused at an
        # interrupt. If so, wait for review (or timeout), then resume.
        while True:
            graph_state = research_graph.get_state(config)

            # No more nodes to run → graph is complete
            if not graph_state.next:
                break

            # Extract interrupt payload from the pending task
            interrupt_value: dict | None = None
            for task in graph_state.tasks:
                if task.interrupts:
                    interrupt_value = task.interrupts[0].value
                    break

            if interrupt_value is None:
                # Pending nodes but no interrupt — shouldn't happen; break safely
                break

            # Surface the task list for the /status endpoint
            info.status = "awaiting_review"
            info.interrupt_data = interrupt_value
            info.review_event.clear()

            logger.info(
                "Session %s: awaiting human review (timeout=%ds)",
                session_id, HUMAN_REVIEW_TIMEOUT_SECONDS,
            )

            # Wait for /review call or auto-approve on timeout
            try:
                await asyncio.wait_for(
                    info.review_event.wait(),
                    timeout=float(HUMAN_REVIEW_TIMEOUT_SECONDS),
                )
                resume_payload = info.review_response or {"action": "approve"}
                logger.info("Session %s: review received — action=%s", session_id, resume_payload.get("action"))
            except asyncio.TimeoutError:
                resume_payload = {"action": "approve"}
                logger.warning(
                    "Session %s: human review timed out after %ds — auto-approving",
                    session_id, HUMAN_REVIEW_TIMEOUT_SECONDS,
                )

            # Resume graph from the interrupt
            info.status = "running"
            result = await loop.run_in_executor(
                None,
                lambda: research_graph.invoke(
                    Command(resume=resume_payload), config=config
                ),
            )

        info.result = result
        info.status = "complete"
        logger.info(
            "Session %s: complete — output_path=%s",
            session_id, result.get("output_path", "N/A"),
        )

    except Exception as exc:
        info.status = "error"
        info.error = str(exc)
        logger.exception("Session %s: graph error — %s", session_id, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/research", status_code=202)
async def start_research(body: StartResearchRequest) -> dict:
    """Start a new research session.

    Returns a session_id to poll with GET /research/{session_id}.
    """
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    info = SessionInfo(session_id=session_id, config=config)
    _sessions[session_id] = info

    # Build the initial graph state — only the fields nodes actually read;
    # LangGraph fills missing fields with their TypedDict defaults.
    initial_state: dict = {
        "research_goal":    body.research_goal,
        "user_documents":   body.user_documents,
        "iteration_count":  0,
        "sub_agent_results": [],
        "all_sources":      [],
        "escalated_tasks":  [],
        "error_log":        [],
        "human_approved":   False,
        "human_feedback":   "",
        "research_complete": False,
        "tasks":            [],
        "evaluation_notes": "",
        "synthesized_report": "",
        "final_report":     "",
        "output_path":      "",
    }

    asyncio.create_task(_run_graph(session_id, initial_state))

    logger.info("Session %s: created for goal: %r", session_id, body.research_goal[:80])
    return {"session_id": session_id, "status": "started"}


@app.get("/research/{session_id}")
async def get_status(session_id: str) -> dict:
    """Poll the status of a research session.

    Possible statuses:
        initializing    — session created, graph not yet running
        running         — graph nodes executing
        awaiting_review — paused at human_review interrupt; task list included
        complete        — finished; output_path points to the .docx file
        error           — unrecoverable error; error field contains message
    """
    info = _sessions.get(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found.")

    response: dict[str, Any] = {
        "session_id": session_id,
        "status": info.status,
    }

    if info.status == "awaiting_review" and info.interrupt_data:
        response["review_prompt"] = info.interrupt_data

    if info.status == "complete" and info.result:
        response["output_path"] = info.result.get("output_path", "")
        response["final_report_preview"] = (info.result.get("final_report", "")[:500] + "...")

    if info.status == "error":
        response["error"] = info.error

    return response


@app.post("/research/{session_id}/review")
async def submit_review(session_id: str, body: ReviewRequest) -> dict:
    """Submit a human review decision for a paused session.

    Body:
        action   — "approve" | "modify" | "reject"
        feedback — required when action is "modify" or "reject"
    """
    info = _sessions.get(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found.")

    if info.status != "awaiting_review":
        raise HTTPException(
            status_code=400,
            detail=f"Session is not awaiting review (current status: {info.status}).",
        )

    action = body.action.lower()
    if action not in ("approve", "modify", "reject"):
        raise HTTPException(
            status_code=422,
            detail="action must be one of: approve, modify, reject.",
        )

    info.review_response = {"action": action, "feedback": body.feedback}
    info.review_event.set()  # unblock the waiting _run_graph coroutine

    logger.info("Session %s: review submitted — action=%s", session_id, action)
    return {"session_id": session_id, "action": action, "status": "review accepted"}


# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "active_sessions": len(_sessions)}


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
