"""
Prompt templates for every LLM-calling node in the research graph.

Each prompt is a ChatPromptTemplate that accepts named variables and returns
a list of messages ready to be passed to the Groq LLM.

Prompts defined here
────────────────────
1. PLAN_RESEARCH_PROMPT      — Lead Researcher: Think (Plan Approach)
2. EVALUATE_RESULTS_PROMPT   — Lead Researcher: Think (Evaluate)
3. SYNTHESIZE_REPORT_PROMPT  — Lead Researcher: Think (Synthesize Results)
4. HANDLE_ESCALATION_PROMPT  — Lead Researcher: Handle Escalation
5. CITATION_AGENT_PROMPT     — Citation Agent
6. SUB_AGENT_PROMPT          — Sub-Agent: Execute a single research task

Variable reference (per prompt)
────────────────────────────────
PLAN_RESEARCH_PROMPT
    {research_goal}     — the user's original research goal
    {iteration_count}   — current loop iteration number
    {human_feedback}    — user modification notes (empty string on first run)
    {prior_context}     — JSON string of completed task summaries from previous
                          iterations (empty string on first run)

EVALUATE_RESULTS_PROMPT
    {research_goal}     — the user's original research goal
    {iteration_count}   — current loop iteration number
    {max_iterations}    — maximum allowed iterations (from config)
    {results_json}      — JSON string of all sub_agent_results collected so far

SUB_AGENT_PROMPT
    {research_goal}       — overall research goal (context only, not the task)
    {task_title}          — short title of this specific task
    {task_description}    — full task instructions from the Lead Researcher
    {search_results}      — JSON string of raw Tavily search results
    {document_content}    — extracted text from user-provided documents
                            (empty string when no documents are relevant)

SYNTHESIZE_REPORT_PROMPT
    {research_goal}     — the user's original research goal
    {results_json}      — JSON string of all sub_agent_results across all iterations
    {evaluation_notes}  — final evaluation summary from evaluate_results node

HANDLE_ESCALATION_PROMPT
    {research_goal}     — the user's original research goal
    {escalated_tasks}   — JSON string of tasks that exhausted all 3 retries

CITATION_AGENT_PROMPT
    {synthesized_report} — the full pre-citation report text
    {sources}            — newline-separated list of all source URLs / documents
"""

from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────────────────────────────────────────
# 1. PLAN_RESEARCH_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
PLAN_RESEARCH_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Lead Researcher. Your job is to break down a research goal \
into a precise, actionable task list that specialized sub-agents will execute.

RULES
─────
• Output ONLY valid JSON — no markdown fences, no explanation text.
• Produce between 3 and 6 tasks. Each task must target a distinct aspect of \
the research goal.
• Each task must have 2–4 targeted search queries that a web-search agent can \
run directly.
• If this is a re-plan (iteration_count > 0), review the prior_context to \
avoid duplicating already-completed work. Generate tasks that fill the gaps.
• If human_feedback is provided, incorporate it into the task design.

OUTPUT FORMAT (JSON array — no wrapper object):
[
  {{
    "task_id": "<uuid-string>",
    "title": "<short task title>",
    "description": "<detailed instructions for the sub-agent>",
    "search_queries": ["<query 1>", "<query 2>", "<query 3>"],
    "relevant_documents": [],
    "priority": "high" | "medium" | "low",
    "status": "pending",
    "retry_count": 0,
    "assigned_to": ""
  }}
]""",
    ),
    (
        "human",
        """Research Goal: {research_goal}

Iteration: {iteration_count}

Human Feedback (apply if non-empty): {human_feedback}

Prior Completed Work (skip these topics in new tasks): {prior_context}

Generate the task list now as a JSON array.""",
    ),
])


# ─────────────────────────────────────────────────────────────────────────────
# 2. EVALUATE_RESULTS_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
EVALUATE_RESULTS_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Lead Researcher evaluating the work produced by your \
sub-agents. Assess every result for quality, completeness, and relevance to \
the original research goal.

RULES
─────
• Output ONLY valid JSON — no markdown fences, no explanation text.
• Set "research_complete" to true only when the research goal is sufficiently \
addressed across all results collected so far.
• Set "research_complete" to false when there are meaningful gaps, shallow \
findings, or important aspects of the goal left uncovered.
• If iteration_count has reached max_iterations, you MUST set \
"research_complete" to true regardless of gaps (forced exit).
• Write "evaluation_notes" as 3–5 sentences: what was covered well, what gaps \
remain, and what new tasks should focus on (if research is not complete).

OUTPUT FORMAT:
{{
  "research_complete": true | false,
  "evaluation_notes": "<your evaluation summary>"
}}""",
    ),
    (
        "human",
        """Research Goal: {research_goal}

Iteration: {iteration_count} of {max_iterations}

Sub-Agent Results Collected So Far:
{results_json}

Evaluate the results and return your JSON verdict.""",
    ),
])


# ─────────────────────────────────────────────────────────────────────────────
# 3. SYNTHESIZE_REPORT_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
SYNTHESIZE_REPORT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Lead Researcher writing the final research report. \
Synthesize ALL sub-agent findings into a single, cohesive, well-structured \
document that directly addresses the research goal.

RULES
─────
• Write in clear, professional prose. No bullet dumps of raw search results.
• Structure the report with a title, an executive summary, and numbered \
sections — one section per major theme or aspect of the research goal.
• Every factual claim must come from the sub-agent findings provided. Do not \
invent information.
• End the report with a "Key Findings" section that lists the 5–7 most \
important takeaways.
• Do NOT insert citations yourself — a Citation Agent will handle that in the \
next step. Write placeholder markers like [CITE] wherever a citation will be \
needed so the Citation Agent knows where to insert them.
• Output ONLY the report text — no preamble, no JSON wrapper.""",
    ),
    (
        "human",
        """Research Goal: {research_goal}

Evaluation Notes (use these to guide emphasis):
{evaluation_notes}

All Sub-Agent Findings:
{results_json}

Write the full research report now.""",
    ),
])


# ─────────────────────────────────────────────────────────────────────────────
# 4. HANDLE_ESCALATION_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
HANDLE_ESCALATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Lead Researcher handling sub-agent task failures. \
For each escalated task, decide whether to reassign it (with a simplified, \
reworded version) or terminate it (accept the gap and move on).

RULES
─────
• Output ONLY valid JSON — no markdown fences, no explanation text.
• "action" must be "reassign" or "terminate".
• If "reassign": provide a reworded "new_description" and updated \
"new_search_queries" (2–3 simpler queries). Keep the same task_id.
• If "terminate": provide a brief "reason" explaining why the task cannot be \
completed and will be skipped.

OUTPUT FORMAT (JSON array):
[
  {{
    "task_id": "<original task_id>",
    "action": "reassign" | "terminate",
    "new_description": "<reworded task — only when action is reassign>",
    "new_search_queries": ["<q1>", "<q2>"],
    "reason": "<termination reason — only when action is terminate>"
  }}
]""",
    ),
    (
        "human",
        """Research Goal: {research_goal}

Escalated Tasks (failed after 3 retries):
{escalated_tasks}

Decide the action for each task and return the JSON array.""",
    ),
])


# ─────────────────────────────────────────────────────────────────────────────
# 5. CITATION_AGENT_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# 6. SUB_AGENT_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
# Design note
# ───────────
# The sub-agent does NOT call Tavily itself via tool use. Instead, nodes.py
# calls Tavily directly in code, then passes the raw results here so the LLM
# can synthesise them into coherent findings. This keeps the LLM call simple
# and deterministic — no tool-loop overhead.
#
# The sub-agent only needs to produce two things:
#   • "findings"  — a well-written narrative summary of what was discovered
#   • "sources"   — the URLs / document names actually used
#
# task_id, status, retry_count, and error_message are attached by nodes.py
# in code, not by the LLM.
SUB_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Research Sub-Agent. You have been assigned one specific \
research task by the Lead Researcher. Your job is to synthesize the provided \
search results and document content into clear, factual findings that directly \
address your assigned task.

RULES
─────
• Output ONLY valid JSON — no markdown fences, no explanation text.
• Write "findings" as 3–6 sentences of coherent, factual prose. Do not dump \
raw search snippets — synthesize them into a readable summary.
• Only include URLs in "sources" that you actually used to form your findings. \
Do not fabricate URLs.
• Stay strictly within the scope of your assigned task. Do not cover topics \
that belong to other tasks.
• If the search results contain no useful information for this task, set \
"findings" to a clear statement of what could not be found, and set \
"sources" to an empty list.

OUTPUT FORMAT:
{{
  "findings": "<narrative summary of research findings>",
  "sources": ["<url or document name>", "..."]
}}""",
    ),
    (
        "human",
        """Overall Research Goal (context only): {research_goal}

Your Assigned Task
──────────────────
Title: {task_title}
Instructions: {task_description}

Search Results:
{search_results}

Relevant Document Content (empty if none provided):
{document_content}

Synthesize the above into your findings and return the JSON result.""",
    ),
])


# ─────────────────────────────────────────────────────────────────────────────
# 5. CITATION_AGENT_PROMPT
# ─────────────────────────────────────────────────────────────────────────────
CITATION_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Citation Agent. Your sole job is to insert citations into \
a research report and append a numbered reference list at the end.

RULES
─────
• Every [CITE] placeholder in the report must be replaced with a numbered \
citation marker like [1], [2], etc.
• Match each [CITE] to the most relevant source from the provided source list.
• Multiple [CITE] markers may map to the same source — use the same number.
• Append a "References" section at the very end of the report in this format:
    [1] <URL or document name>
    [2] <URL or document name>
    ...
• Do not alter any other part of the report text.
• Output ONLY the final report with citations — no preamble, no explanation.""",
    ),
    (
        "human",
        """Research Report (contains [CITE] placeholders):
{synthesized_report}

Available Sources (one per line):
{sources}

Insert citations and return the complete final report.""",
    ),
])
