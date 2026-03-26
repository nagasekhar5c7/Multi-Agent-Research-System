"""
Conditional edge routing functions for the research graph.

Each function receives the full ResearchState and returns the name of the
next node as a string. These strings must exactly match the node names
registered in builder.py.

Three conditional edges
────────────────────────
1. route_human_review      — after human_review node
2. route_after_execution   — after execute_tasks node
3. route_research_loop     — after evaluate_results node
"""

import logging

from config.config import MAX_ITERATIONS
from src.app.graph.state import ResearchState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Edge 1 — after human_review
# ─────────────────────────────────────────────────────────────────────────────
def route_human_review(state: ResearchState) -> str:
    """Route based on whether the user approved the task list.

    True  → proceed to task execution
    False → loop back to re-plan (user rejected or requested modifications)
    """
    if state.get("human_approved", False):
        logger.info("Edge route_human_review → execute_tasks")
        return "execute_tasks"

    logger.info("Edge route_human_review → plan_research (not approved)")
    return "plan_research"


# ─────────────────────────────────────────────────────────────────────────────
# Edge 2 — after execute_tasks
# ─────────────────────────────────────────────────────────────────────────────
def route_after_execution(state: ResearchState) -> str:
    """Route based on whether any tasks were escalated after all retries.

    Escalations present → Lead Researcher must handle them first
    No escalations      → proceed directly to evaluation
    """
    escalated = state.get("escalated_tasks", [])

    if escalated:
        logger.info(
            "Edge route_after_execution → handle_escalation (%d escalated)",
            len(escalated),
        )
        return "handle_escalation"

    logger.info("Edge route_after_execution → evaluate_results")
    return "evaluate_results"


# ─────────────────────────────────────────────────────────────────────────────
# Edge 3 — after evaluate_results
# ─────────────────────────────────────────────────────────────────────────────
def route_research_loop(state: ResearchState) -> str:
    """Route based on research completeness and iteration cap.

    Exits the loop (→ synthesize_report) when:
      • research_complete is True  (Lead Researcher is satisfied), OR
      • iteration_count >= MAX_ITERATIONS  (forced exit at cap)

    Continues the loop (→ plan_research) when:
      • research_complete is False AND iteration_count < MAX_ITERATIONS
    """
    research_complete: bool = state.get("research_complete", False)
    iteration_count: int = state.get("iteration_count", 0)

    if research_complete or iteration_count >= MAX_ITERATIONS:
        if not research_complete:
            logger.warning(
                "Edge route_research_loop → synthesize_report "
                "(forced exit — iteration cap %d reached)",
                MAX_ITERATIONS,
            )
        else:
            logger.info(
                "Edge route_research_loop → synthesize_report "
                "(research complete at iteration %d)",
                iteration_count,
            )
        return "synthesize_report"

    logger.info(
        "Edge route_research_loop → plan_research "
        "(iteration %d / %d, research not complete)",
        iteration_count,
        MAX_ITERATIONS,
    )
    return "plan_research"
