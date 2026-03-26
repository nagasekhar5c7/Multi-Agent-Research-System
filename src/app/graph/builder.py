"""
Graph construction — wires all nodes, edges, and conditional routing into a
compiled LangGraph StateGraph.

Exported symbol
───────────────
    research_graph  — the compiled, checkpointed graph ready for invocation.

Usage (from main.py)
────────────────────
    from src.app.graph.builder import research_graph

    # Start a new research session
    config = {"configurable": {"thread_id": session_id}}
    result = research_graph.invoke(initial_state, config=config)

    # Resume after human_review interrupt
    from langgraph.types import Command
    research_graph.invoke(Command(resume={"action": "approve"}), config=config)

Checkpointer note
─────────────────
    Currently uses MemorySaver (in-process, non-persistent).
    To enable cross-session persistence, install langgraph-checkpoint-sqlite:

        uv add langgraph-checkpoint-sqlite

    Then swap the checkpointer block below:

        from langgraph.checkpoint.sqlite import SqliteSaver
        checkpointer = SqliteSaver.from_conn_string(SQLITE_DB_PATH)
"""

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.app.graph.edges import (
    route_after_execution,
    route_human_review,
    route_research_loop,
)
from src.app.graph.nodes import (
    citation_agent_node,
    evaluate_results_node,
    execute_tasks_node,
    handle_escalation_node,
    human_review_node,
    plan_research_node,
    save_output_node,
    synthesize_report_node,
)
from src.app.graph.state import ResearchState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Construct and return the compiled research graph.

    Separated into its own function so the graph can be rebuilt in tests
    without re-importing the module.
    """
    builder = StateGraph(ResearchState)

    # ── Register nodes ────────────────────────────────────────────────────
    builder.add_node("plan_research",    plan_research_node)
    builder.add_node("human_review",     human_review_node)
    builder.add_node("execute_tasks",    execute_tasks_node)
    builder.add_node("handle_escalation", handle_escalation_node)
    builder.add_node("evaluate_results", evaluate_results_node)
    builder.add_node("synthesize_report", synthesize_report_node)
    builder.add_node("citation_agent",   citation_agent_node)
    builder.add_node("save_output",      save_output_node)

    # ── Direct (unconditional) edges ──────────────────────────────────────
    builder.add_edge(START,              "plan_research")
    builder.add_edge("plan_research",    "human_review")
    builder.add_edge("handle_escalation", "evaluate_results")
    builder.add_edge("synthesize_report", "citation_agent")
    builder.add_edge("citation_agent",   "save_output")
    builder.add_edge("save_output",      END)

    # ── Conditional edges ─────────────────────────────────────────────────

    # After human_review: approved → execute_tasks | rejected → plan_research
    builder.add_conditional_edges(
        "human_review",
        route_human_review,
        {
            "execute_tasks": "execute_tasks",
            "plan_research": "plan_research",
        },
    )

    # After execute_tasks: escalations present → handle_escalation
    #                      no escalations      → evaluate_results
    builder.add_conditional_edges(
        "execute_tasks",
        route_after_execution,
        {
            "handle_escalation": "handle_escalation",
            "evaluate_results":  "evaluate_results",
        },
    )

    # After evaluate_results: more research needed → plan_research
    #                         complete / cap hit   → synthesize_report
    builder.add_conditional_edges(
        "evaluate_results",
        route_research_loop,
        {
            "plan_research":    "plan_research",
            "synthesize_report": "synthesize_report",
        },
    )

    # ── Checkpointer ──────────────────────────────────────────────────────
    # MemorySaver: in-process only — state is lost when the process restarts.
    # Swap for SqliteSaver (see module docstring) for production persistence.
    checkpointer = MemorySaver()

    compiled = builder.compile(checkpointer=checkpointer)
    logger.info("Research graph compiled successfully.")
    return compiled


# Module-level compiled graph — imported directly by main.py
research_graph = build_graph()
