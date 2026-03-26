"""
Central configuration for the Multi-Agent Research System.

All runtime variables live here — no .env file.
Replace the dummy API key values with real keys before running.

Sections
────────
1. Groq LLM
2. Tavily Search
3. SQLite (checkpointer + app-level session store)
4. Sub-agent pool
5. Research loop limits
6. Human review
7. Output
8. Logging
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1. Groq LLM
# ─────────────────────────────────────────────────────────────────────────────

GROQ_API_KEY: str = "your_groq_api_key_here"
"""Groq API key. Get yours at https://console.groq.com"""

GROQ_MODEL: str = "openai/gpt-oss-120b"
"""Groq model ID.
Recommended options (fast + capable):
  • llama-3.3-70b-versatile   — best quality, default
  • llama-3.1-8b-instant      — fastest, lower cost
"""

# ─────────────────────────────────────────────────────────────────────────────
# 2. Tavily Search
# ─────────────────────────────────────────────────────────────────────────────

TAVILY_API_KEY: str = "your_tavily_api_key_here"
"""Tavily API key. Get yours at https://tavily.com"""

TAVILY_SEARCH_DEPTH: str = "basic"
"""Tavily search depth.
  • "basic"    — faster, ~1 credit per query  (default)
  • "advanced" — richer results, ~2 credits per query
"""

TAVILY_MAX_RESULTS: int = 5
"""Maximum number of search results returned per query.
Keeping this at 5 balances result quality vs. token usage in the LLM call."""

# ─────────────────────────────────────────────────────────────────────────────
# 3. SQLite
# ─────────────────────────────────────────────────────────────────────────────

SQLITE_DB_PATH: str = "data/research_context/research.db"
"""Path to the SQLite database used by the app-level session store
(session_store.py). Relative to the project root.

NOTE: When langgraph-checkpoint-sqlite is installed, this same path
is also used by the LangGraph SqliteSaver checkpointer in builder.py.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 4. Sub-agent pool
# ─────────────────────────────────────────────────────────────────────────────

MAX_SUB_AGENTS: int = 3
"""Fixed size of the sub-agent worker pool (ThreadPoolExecutor max_workers).
Tasks are assigned dynamically — a free worker picks the next queued task.
"""

MAX_RETRY_COUNT: int = 3
"""Maximum number of retry attempts per task inside a sub-agent worker.
Retries use exponential back-off: 1s → 2s → 4s.
After all retries are exhausted the task is escalated to the Lead Researcher.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 5. Research loop limits
# ─────────────────────────────────────────────────────────────────────────────

MAX_ITERATIONS: int = 5
"""Maximum number of full research loop iterations (plan → execute → evaluate).
When this cap is hit the graph forces synthesis regardless of
research_complete flag. A WARNING is written to the error_log.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 6. Human review
# ─────────────────────────────────────────────────────────────────────────────

HUMAN_REVIEW_TIMEOUT_SECONDS: int = 600
"""Seconds main.py waits for a human /review API call before auto-approving.
When the timeout expires the graph is resumed with {"action": "approve"}
and a note is appended to the session error_log.
600 seconds (10 min) is recommended during development/testing.
Set to 120 (2 min) for production.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 7. Output
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR: str = "output"
"""Directory where final .docx research reports are saved.
Created automatically if it does not exist.
"""

# ─────────────────────────────────────────────────────────────────────────────
# 8. Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_LEVEL: str = "INFO"
"""Root log level for the application.
  • "DEBUG"   — verbose, includes LLM prompt/response details
  • "INFO"    — standard node-level progress messages (default)
  • "WARNING" — only escalations, forced exits, and errors
"""
