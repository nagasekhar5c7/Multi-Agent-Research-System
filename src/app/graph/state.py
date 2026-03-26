"""
ResearchState — the single shared state object passed through every node in
the LangGraph research graph.

Reducer rules
─────────────
• Annotated[list[...], operator.add]  → LangGraph APPENDS new items rather
  than overwriting. Used for lists that accumulate across iterations/nodes:
  sub_agent_results, all_sources, error_log.

• Plain fields (str, int, bool, list[dict]) → last-write wins; each node
  that touches them simply returns the updated value.
"""

import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    research_goal: str
    """The raw research goal submitted by the user."""

    user_documents: list[str]
    """File paths or URLs of PDFs / links provided by the user.
    Empty list when no documents are supplied."""

    # ── Planning ───────────────────────────────────────────────────────────
    tasks: list[dict]
    """Current active task list produced by plan_research.
    Each item follows the Task Schema defined in graph_design.md.
    Overwritten on every re-plan."""

    human_feedback: str
    """Optional modification notes entered by the user at the human_review
    interrupt. Empty string when the user approves without changes."""

    human_approved: bool
    """True  → proceed to execute_tasks.
    False → route back to plan_research.
    Also set to True automatically on 2-minute auto-approve timeout."""

    # ── Execution tracking ─────────────────────────────────────────────────
    iteration_count: int
    """Number of full research loops completed. Starts at 0. Capped at
    MAX_ITERATIONS (default 5) by route_research_loop."""

    sub_agent_results: Annotated[list[dict], operator.add]
    """Results returned by sub-agents, accumulated across ALL iterations.
    Each item follows the Sub-Agent Result Schema in graph_design.md.
    Uses operator.add so new results are appended, never overwritten."""

    all_sources: Annotated[list[str], operator.add]
    """Every source URL and document path collected by sub-agents across
    all iterations. Feeds into the Citation Agent. Appended, not replaced."""

    escalated_tasks: list[dict]
    """Tasks that exhausted all 3 retries and could not be completed.
    Populated by execute_tasks; cleared / acted on by handle_escalation."""

    # ── Evaluation ─────────────────────────────────────────────────────────
    evaluation_notes: str
    """Lead Researcher's written evaluation of the current iteration's
    sub-agent results. Overwritten each iteration."""

    research_complete: bool
    """Set by evaluate_results.
    True  → research goal is sufficiently addressed; exit the loop.
    False → more research needed; loop back to plan_research."""

    # ── Output ─────────────────────────────────────────────────────────────
    synthesized_report: str
    """Pre-citation unified research report produced by synthesize_report."""

    final_report: str
    """synthesized_report with inline citations inserted by citation_agent."""

    output_path: str
    """Absolute path to the saved .docx file. Set by save_output."""

    # ── Error tracking ─────────────────────────────────────────────────────
    error_log: Annotated[list[str], operator.add]
    """Running log of errors, escalations, auto-approvals, and forced loop
    terminations. Appended to by any node that encounters an issue."""
