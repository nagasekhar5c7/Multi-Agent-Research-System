# Multi-Agent Research System — Agent Specification

> This is the golden reference document for designing and implementing the multi-agent research system. All implementation decisions must align with this specification.

---

## 1. System Overview

A multi-agent research system built with **LangGraph** that takes a user-defined research goal, decomposes it into structured tasks, executes them via specialized sub-agents with web search capabilities, and produces a detailed research report with citations. The system uses **Groq LLM** for all agent reasoning.

---

## 2. Technology Stack

| Component        | Choice                                                                 |
|------------------|------------------------------------------------------------------------|
| Framework        | LangGraph (latest stable, production patterns)                         |
| LLM              | Groq (via API)                                                         |
| Memory Backend   | SQLite (persists research context across sessions)                     |
| Search Tool      | Tavily or SerpAPI (whichever offers more free-tier requests/day)       |
| Citation Sources | Web search URLs + user-provided documents (PDFs, links)                |
| Configuration    | `config.py` — all variables stored here, no `.env` file               |
| Final Output     | Detailed research report with citations, saved as `.docx`               |

---

## 3. Agent Definitions

### 3.1 Lead Researcher Agent

**Role:** The primary planning and coordination agent. It receives the user's research goal, creates a structured plan, delegates tasks to sub-agents, evaluates their output, and synthesizes the final research.

**Responsibilities:**

- Receive and interpret the user's research goal
- Break the goal into discrete, actionable tasks output in **JSON format**
- Save the research plan to **Memory (SQLite)**
- Delegate tasks to Sub-Agents
- Evaluate sub-agent results for quality and completeness (retrieve context from Memory)
- Synthesize all findings into a cohesive detailed report
- Decide whether more research iterations are needed
- Handle escalations from failed sub-agents (reassign to another sub-agent or terminate)

**Structured Thinking Phases:**

The Lead Researcher operates through three explicit reasoning phases:

1. **Think (Plan Approach)** — Analyze the user's goal, identify key aspects to research, and decompose into tasks. Save the plan to Memory.
2. **Think (Evaluate)** — After sub-agents return results, assess each result for quality, completeness, and relevance. Retrieve prior context from Memory to inform evaluation.
3. **Think (Synthesize Results)** — Combine all sub-agent findings into a unified, cohesive detailed report. Determine if the research goal has been sufficiently addressed.

---

### 3.2 Sub-Agents

**Role:** Task executors. Each sub-agent picks up a specific task assigned by the Lead Researcher and performs research using web search and/or provided documents.

**Responsibilities:**

- Receive a single task (from the Lead Researcher's JSON task list)
- Execute the task using web search tools (Tavily or SerpAPI)
- Process user-provided documents (PDFs, links) if relevant to the task
- Return structured results back to the Lead Researcher
- Track and return source URLs/documents used for citation purposes

**Scaling:**

- No fixed number of sub-agents
- Dynamically created based on the number of tasks the Lead Researcher generates
- Multiple sub-agents can execute tasks in parallel

**Error Handling:**

- On failure: **retry up to 3 times**
- If still failing after 3 retries: **escalate back to the Lead Researcher**
- The Lead Researcher then decides to either:
  - Reassign the task to a different sub-agent
  - Terminate after repeated failures

---

### 3.3 Citation Agent

**Role:** Post-processing agent responsible for adding citations to the final research report.

**Responsibilities:**

- Receive the synthesized research report from the Lead Researcher
- Receive all source documents and URLs collected by sub-agents
- Identify locations in the report where citations should be inserted
- Match claims/statements to their source materials
- Return the final report with citations properly inserted

**Citation Sources:**

- Web search URLs used by sub-agents during research
- User-provided documents (PDFs, links)

---

## 4. Memory Layer

**Backend:** SQLite

**Purpose:** Provide continuity and context across the iterative research loop.

**Operations:**

- **Save Plan** — When the Lead Researcher creates a research plan, it is persisted to SQLite
- **Retrieve Context** — During evaluation and synthesis phases, the Lead Researcher retrieves prior plans, findings, and context from SQLite
- **Cross-Session Persistence** — Research context survives across separate sessions, enabling long-running or resumed research

---

## 5. System Flow

### Step-by-step execution:

1. **User submits a research goal**
2. **Lead Researcher — Think (Plan Approach)**
   - Analyzes the goal
   - Breaks it into tasks (JSON format)
   - Saves the plan to Memory (SQLite)
3. **Human-in-the-Loop Review**
   - The generated tasks are presented to the user
   - The user reviews and approves (or modifies) before execution proceeds
4. **Iterative Research Loop** (max 5 iterations)
   - Sub-Agents are dynamically created and assigned tasks
   - Sub-Agents execute tasks using web search and/or provided documents
   - Sub-Agents return results (with source URLs/documents)
   - **Lead Researcher — Think (Evaluate)** — Assesses results, retrieves context from Memory
   - **Lead Researcher — Think (Synthesize Results)** — Combines findings
   - **Decision: More research needed?**
     - Yes → Continue loop (generate new tasks, spin up sub-agents again)
     - No → Exit loop
5. **Citation Agent**
   - Processes the synthesized report and all source materials
   - Inserts citations into the report
6. **Result Persistence**
   - Final report is persisted (survives session interruptions)
7. **Output**
   - Detailed research report with citations saved as `.docx`
   - Returned to the user

---

## 6. Human-in-the-Loop

**Trigger Point:** After the Lead Researcher generates tasks (Step 3).

**Behavior:**

- The system pauses execution and presents the task list to the user
- The user can review, approve, modify, or reject tasks
- Execution only proceeds to the iterative research loop after user approval

---

## 7. Error Handling Strategy

| Scenario                          | Action                                                        |
|-----------------------------------|---------------------------------------------------------------|
| Sub-agent task failure            | Retry up to 3 times                                           |
| Sub-agent fails after 3 retries   | Escalate to Lead Researcher                                   |
| Lead Researcher receives escalation | Reassign to another sub-agent or terminate gracefully        |
| Iterative loop exceeds limit      | Force exit after max 5 iterations                             |

---

## 8. Design Principles

- **Production-ready** — Code must be deployable, not a prototype
- **Modular** — Each agent, tool, and utility in its own module
- **Industry-standard** — Clean separation of concerns, proper error handling, logging, type hints
- **Scalable** — Easy to add new sub-agents or modify the research pipeline

---

## 9. Configuration

All configuration lives in `config.py`. No `.env` file.

**Expected variables:**

- Groq API key
- Groqagents.md    file. Look for a directory structure. Create the directory structure in my current working directory. Please make sure that you don't try to write any code. Only create empty files under the directory model name / endpoint
- Search tool API key (Tavily or SerpAPI)
- SQLite database path
- Max retry count (default: 3)
- Max research iterations (default: 5)
- Output file path / directory

---

## 10. Open Items

- JSON schema for tasks generated by the Lead Researcher — to be drafted
- State graph structure in LangGraph (nodes, edges, conditional routing) — to be drafted
- Search tool selection (Tavily vs SerpAPI) — compare free-tier limits and finalize
- Groq API key — to be provided by user

---

## 11. Folder Structure

```
LangGraph_Live/
│
├── .venv/                                # Virtual environment (UV managed)
├── pyproject.toml                        # UV package dependency manager config
├── uv.lock                              # UV lock file
│
├── config/
│   └── config.py                        # All configuration variables (API keys, model settings, paths, limits)
│
├── main.py                              # Entry point — initializes and runs the LangGraph state graph
│
├── src/app/
│   └── graph/
│       ├── __init__.py
│       ├── state.py                     # LangGraph state definition (TypedDict / Pydantic model)
│       ├── nodes.py                     # Graph node functions (one per step in the flow)
│       ├── edges.py                     # Graph edge definitions
│       ├── prompts.py                   # Prompt templates for all agents
│       └── builder.py                   # Graph construction (nodes, edges, conditional routing)
│
├── src/utils/
│   └── tools/
│       ├── __init__.py
│       ├── search.py                    # Web search tool wrapper (Tavily or SerpAPI)
│       └── document_loader.py           # PDF and link processing for user-provided documents
│
├── data/
│   └── research_context/
│       ├── __init__.py
│       └── session_store.py             # SQLite session memory (save plans, retrieve context, cross-session persistence)
│
├── output/
│   └── (generated .txt reports saved here)
│
├── ideas.md                             # Raw brainstorming notes
├── agents.md                            # Golden reference specification (this file)
```
