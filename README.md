# Multi-Agent Research System

A production-ready multi-agent research pipeline built with **LangGraph 0.2.x**, **Groq LLM**, and **Tavily** web search. Submit a research goal via REST API, review and approve the generated task plan, and receive a fully cited `.docx` research report.

---

## How it works

```
User submits goal
       │
       ▼
 plan_research          ← Lead Researcher decomposes goal into JSON tasks
       │
       ▼
 human_review           ← INTERRUPT: approve / modify / reject via API
  (10-min timeout)        Auto-approves if no response within timeout
       │
       ▼
 execute_tasks          ← 3 sub-agents run in parallel (ThreadPoolExecutor)
  (3 sub-agents)          Each agent: Tavily search → LLM synthesis → result
       │
       ├── escalations? → handle_escalation → reassign or terminate
       │
       ▼
 evaluate_results       ← Lead Researcher assesses quality + completeness
       │
       ├── incomplete + iterations < 5 → loop back to plan_research
       │
       ▼
 synthesize_report      ← Lead Researcher combines all findings
       │
       ▼
 citation_agent         ← Matches claims to sources, inserts [1][2]... markers
       │
       ▼
 save_output            ← Writes .docx to output/
```

---

## Technology stack

| Component        | Choice                                      |
|-----------------|---------------------------------------------|
| Framework        | LangGraph 0.2.70                           |
| LLM              | Groq — `openai/gpt-oss-120b`               |
| Web search       | Tavily                                      |
| Memory backend   | SQLite (app-level) + MemorySaver (LangGraph checkpoint) |
| Sub-agent pool   | `ThreadPoolExecutor(max_workers=3)`         |
| API              | FastAPI + Uvicorn                           |
| Output           | `.docx` via python-docx                     |

---

## Project structure

```
LangGraph_Live/
│
├── main.py                              # FastAPI entry point
├── pyproject.toml                       # UV dependency config
│
├── config/
│   └── config.py                        # All config variables (API keys, limits)
│
├── src/app/graph/
│   ├── state.py                         # ResearchState TypedDict (15 fields)
│   ├── prompts.py                       # 6 ChatPromptTemplates (one per agent role)
│   ├── nodes.py                         # 8 node functions
│   ├── edges.py                         # 3 conditional routing functions
│   └── builder.py                       # Compiled StateGraph — import research_graph
│
├── src/utils/tools/
│   ├── search.py                        # Tavily wrapper → run_tavily_search()
│   └── document_loader.py               # PDF + URL + text file loader
│
├── data/research_context/
│   └── session_store.py                 # SQLite store (plans, results, reports)
│
├── output/                              # Generated .docx reports saved here
│
├── agents.md                            # Agent specification (golden reference)
└── graph_design.md                      # Graph design: nodes, edges, state, Mermaid diagram
```

---

## Setup

### 1. Add API keys to `config/config.py`

```python
GROQ_API_KEY  = "your-groq-key"      # https://console.groq.com
TAVILY_API_KEY = "your-tavily-key"   # https://tavily.com
```

### 2. Install dependencies

```bash
# Using the project's anaconda environment (packages already installed globally)
# or with uv:
uv sync
```

### 3. Start the server

```bash
uvicorn main:app --reload --port 8000
```

---

## API usage

### Start a research session

```bash
curl -s -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "research_goal": "What are the latest advancements in large language models in 2024–2025?",
    "user_documents": []
  }' | python3 -m json.tool
```

Response:
```json
{ "session_id": "abc123...", "status": "started" }
```

---

### Poll status

```bash
curl -s http://localhost:8000/research/<SESSION_ID> | python3 -m json.tool
```

| Status | Meaning |
|---|---|
| `initializing` | Session created, graph not yet started |
| `running` | Nodes executing (planning, searching, evaluating) |
| `awaiting_review` | Paused — task list ready for your review |
| `complete` | Done — `output_path` contains the `.docx` file |
| `error` | Unrecoverable error — `error` field has details |

---

### Submit human review (when `awaiting_review`)

```bash
# Approve
curl -s -X POST http://localhost:8000/research/<SESSION_ID>/review \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "feedback": ""}' | python3 -m json.tool

# Request modifications
curl -s -X POST http://localhost:8000/research/<SESSION_ID>/review \
  -H "Content-Type: application/json" \
  -d '{"action": "modify", "feedback": "Focus only on open-source models"}' | python3 -m json.tool

# Reject and re-plan
curl -s -X POST http://localhost:8000/research/<SESSION_ID>/review \
  -H "Content-Type: application/json" \
  -d '{"action": "reject", "feedback": "Too broad — narrow to reasoning benchmarks only"}' | python3 -m json.tool
```

> **Auto-approve timeout:** If no review is submitted within `HUMAN_REVIEW_TIMEOUT_SECONDS` (default: 600s), the system approves automatically and continues.

---

### Poll loop (macOS / zsh)

```bash
SESSION_ID="your-session-id-here"

while true; do
  RESPONSE=$(curl -s http://localhost:8000/research/$SESSION_ID)
  CURRENT=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "$(date '+%H:%M:%S') — status: $CURRENT"

  if [ "$CURRENT" = "awaiting_review" ]; then
    echo "\n>>> TASK LIST READY — approve now"
    echo $RESPONSE | python3 -m json.tool
    break
  elif [ "$CURRENT" = "complete" ]; then
    echo "\n>>> RESEARCH COMPLETE"
    echo $RESPONSE | python3 -m json.tool
    break
  elif [ "$CURRENT" = "error" ]; then
    echo "\n>>> ERROR"
    echo $RESPONSE | python3 -m json.tool
    break
  fi

  sleep 8
done
```

---

### Health check

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

---

## Configuration reference (`config/config.py`)

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Groq API key (required) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model ID |
| `TAVILY_API_KEY` | — | Tavily API key (required) |
| `TAVILY_SEARCH_DEPTH` | `basic` | `basic` or `advanced` |
| `TAVILY_MAX_RESULTS` | `5` | Results per search query |
| `SQLITE_DB_PATH` | `data/research_context/research.db` | App-level SQLite store |
| `MAX_SUB_AGENTS` | `3` | Worker pool size (ThreadPoolExecutor) |
| `MAX_RETRY_COUNT` | `3` | Retries per sub-agent task (exponential back-off) |
| `MAX_ITERATIONS` | `5` | Max research loop iterations before forced synthesis |
| `HUMAN_REVIEW_TIMEOUT_SECONDS` | `600` | Auto-approve after this many seconds (dev: 600, prod: 120) |
| `OUTPUT_DIR` | `output` | Directory for generated `.docx` reports |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |

---

## User-provided documents

Pass file paths or URLs with the initial request:

```bash
curl -s -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "research_goal": "Summarise the attached paper on mixture-of-experts",
    "user_documents": [
      "/path/to/paper.pdf",
      "https://example.com/article"
    ]
  }'
```

Supported formats: **PDF**, **web URLs**, **plain text files**.

---

## Design documents

- [`agents.md`](agents.md) — full agent specification (golden reference)
- [`graph_design.md`](graph_design.md) — node/edge/state design + Mermaid diagram

To visualise the graph, paste the Mermaid code block from `graph_design.md` into [mermaid.live](https://mermaid.live).
