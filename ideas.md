# Multi-Agent Research System — Ideas

## Overview

A multi-agent research system built with **LangGraph** that orchestrates research tasks through a hierarchical agent structure. The system takes a user-defined research goal and breaks it down into actionable tasks, distributing them across specialized sub-agents.

---

## Architecture

### Agent Hierarchy

1. **Lead Researcher Agent** — Takes the user's goal, analyzes it, and generates a structured plan of tasks (in JSON format). Uses structured thinking phases: plan approach, evaluate results, synthesize findings.
2. **Sub-Agents** — Pick up individual tasks from the Lead Researcher and execute them (with web search)
3. **Citation Agent** — Post-processing agent that takes the final research report and source documents, identifies where citations belong, and inserts them into the report

### Memory Layer

- The Lead Researcher **saves plans** to memory and **retrieves context** during the research process
- Provides continuity across iterative research loops
- Enables the system to build on prior findings rather than starting from scratch each iteration

### Iterative Research Loop

- After sub-agents complete their tasks and the Lead Researcher synthesizes results, a **"More research needed?"** decision point is evaluated
- If yes → continue the loop (plan new tasks, spin up sub-agents again)
- If no → exit the loop and proceed to citation processing and final output

### Structured Thinking Phases (Lead Researcher)

1. **Think (Plan Approach)** — Analyze the goal and break it into tasks
2. **Think (Evaluate)** — Assess sub-agent results for quality and completeness
3. **Think (Synthesize Results)** — Combine all findings into a cohesive report

### Result Persistence

- The system persists final results before returning to the user
- Ensures research output is saved even if the session ends unexpectedly

---

## Key Decisions

- **LLM**: Grok (via API)
- **Framework**: LangGraph (latest documentation, production patterns)
- **Config**: All variables stored in `config.py` — no `.env` file
- **Task Format**: JSON — the Lead Researcher outputs tasks as structured JSON for sub-agents to consume
- **Search Tool**: Whichever between Tavily and SerpAPI offers more free-tier requests/day (to be evaluated)
- **Human-in-the-Loop**: Yes — after Lead Researcher generates tasks, the user reviews and approves before sub-agents begin execution
- **Final Output**: Detailed report saved as a text file (.txt) — not just a summary
- **Error Handling**: Sub-agents retry up to 3 times on failure. If still failing, escalate back to Lead Researcher. Lead Researcher then reassigns to another sub-agent or terminates after repeated failures.
- **Memory Backend**: SQLite — research context persists across sessions
- **Citation Sources**: Both web search URLs (from sub-agents) and user-provided documents (PDFs, links)
- **Iterative Loop Limit**: Max 5 research iterations to prevent infinite loops

---

## Design Principles

- **Production-ready** — code must be deployable, not a prototype
- **Modular** — each agent, tool, and utility in its own module
- **Industry-standard** — clean separation of concerns, proper error handling, logging, typing
- **Scalable** — easy to add new sub-agents or modify the research pipeline

---

## Flow (Updated)

```
User Goal
   |
   v
Lead Researcher Agent
   |
   v
Think (Plan Approach) --> Save plan to Memory
   |
   v
Generate tasks (JSON)
   |
   v
Human Review & Approval  <-- (human-in-the-loop)
   |
   v
+------------------------------------------+
|        Iterative Research Loop            |
|                                           |
|  Sub-Agents (web search, execute tasks)   |
|     |  |                                  |
|     |  +--> On failure: retry 3x,         |
|     |       then escalate to Lead         |
|     v                                     |
|  Think (Evaluate) --> Retrieve context    |
|     |                  from Memory        |
|     v                                     |
|  Think (Synthesize Results)               |
|     |                                     |
|     v                                     |
|  More research needed?                    |
|     Yes --> Continue loop                 |
|     No  --> Exit loop                     |
+------------------------------------------+
   |
   v
Citation Agent --> Insert citations into report
   |
   v
Persist Results
   |
   v
Detailed Report with Citations (.txt)
```

---

## Open Questions / Next Steps

- **JSON schema for tasks**: To be drafted later
- **Sub-agent count**: No fixed number — dynamically spin up based on tasks. Not a concern for now.
- **State graph structure**: To be drafted in upcoming sessions (nodes, edges, conditional routing)
- **Search tool selection**: Compare Tavily vs SerpAPI free-tier limits and pick the better option
- Grok API key to be provided and stored in `config.py` ✅
