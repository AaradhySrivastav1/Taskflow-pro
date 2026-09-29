# TaskFlow Pro

A workflow platform where a DAG (Directed Acyclic Graph) engine manages task
dependencies and ordering behind a fast, drag-and-drop Kanban board.

**Author:** Aaradhy Srivastava · Roll No. 2301921640001 · G.L. Bajaj Institute of Technology and Management

---

## What this is

Tasks live on a four-column board — **Backlog | In Progress | Review | Done**
— but every task can also declare **prerequisite** tasks. The backend models
this as a directed graph and enforces four guarantees everywhere a task or
dependency changes:

| Rule | What it means here |
|---|---|
| **No Cycles** | Every new dependency edge is checked with a graph traversal before it's saved. A cyclic edge is rejected with a 409, never written. |
| **No Compounding** | Propagating a change downstream uses one visited-set per triggering event, so a task is never re-processed multiple times by the same change, however many paths reach it. |
| **Rollback on Regression** | All graph writes run inside a DB transaction. A task cannot move to Review/Done while Blocked (rejected with 409). If a completed task is reopened, every downstream dependent is automatically re-evaluated and re-blocked if needed. |
| **Persistence** | All state (tasks, edges, status history) lives in a SQL database, not browser memory — a refresh reloads the exact same board. |

A **Blocked / Ready** badge on every card is *computed*, not a field you can
edit directly — it's always derived from whether a task's direct
prerequisites are in the Done column.

## Architecture

```
frontend/  Next.js (React) — Kanban board, drag-and-drop, task + dependency UI
backend/   FastAPI (Python) — REST API, DAG engine, SQLite persistence
```

```
Database Schema ──► Backend API ──► Integration Tests ──► Deployment Pipeline
                          │                                      ▲
                          ▼                                      │
                    Frontend UI ───────────────────────────────────
                          │
                          ▼
                    Code Review ──► Documentation
```
(This is the seeded dependency graph — see `backend/app/seed.py`.)

## Tech stack

- **Frontend:** Next.js (App Router), React, `@hello-pangea/dnd` for drag-and-drop, plain CSS (design tokens in `app/globals.css`)
- **Backend:** FastAPI, SQLAlchemy ORM
- **Database:** SQLite by default (file-based, zero config). Swap to PostgreSQL by changing one env var — see below.
- **AI/LLM:** Google Gemini API (`gemini-2.5-flash`) for the dependency-suggestion feature

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) A Google Gemini API key, for the AI dependency-suggestion feature

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# optional: enable AI suggestions
export GEMINI_API_KEY=...   # Windows: set GEMINI_API_KEY=...

# seed the database with 9 example tasks and 10 dependency edges
python -m app.seed

# run the API
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`).

To use PostgreSQL instead of SQLite:
```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/taskflow
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # defaults to http://localhost:8000, edit if needed
npm run dev
```

Open `http://localhost:3000`.

### 3. Run both together

Keep the two commands above running in separate terminals. The frontend
talks to the backend over plain REST (`NEXT_PUBLIC_API_URL`), so either can
be restarted independently without losing data (it's all in the database).

---

## AI-Tool Declaration

This submission uses AI assistance in two distinct ways, disclosed here as required:

1. **Development-time assistance.** The synopsis and this codebase (backend
   DAG engine, API, frontend Kanban board, README) were built with the help
   of Claude (Anthropic), an AI coding assistant, working from the author's
   problem statement and instructions. All architectural decisions, the
   DAG-engine rules (cycle detection, propagation, rollback), and the final
   review of the generated code are the author's.
2. **Runtime product feature (mandatory requirement).** TaskFlow Pro itself
  calls the **Google Gemini API** at runtime for the **AI-Augmented
   Dependency Suggestion** feature (`backend/app/ai.py`). When a user opens
   a task and clicks "✨ Suggest", the task's title/description and a list
  of the other tasks in the workspace are sent to Gemini, which returns
   candidate prerequisite relationships with a confidence score and a short
   rationale. Suggestions are never written to the database automatically —
   the user must accept each one individually, and an accepted suggestion
   is created through the exact same dependency-creation code path (and
  cycle check) as a manually declared dependency. If no `GEMINI_API_KEY`
   is set, or the API call fails, the feature degrades to an empty
   suggestion list rather than breaking the rest of the app.

---

## Key Assumptions & Limitations

**Assumptions**
- Single-workspace model: this sprint assumes one shared workspace with no
  authentication/user accounts. Anyone with access to the app can create,
  edit, and move any task.
- A task's readiness depends only on its **direct** prerequisites being in
  the **Done** column — there's no notion of partial completion or
  percentage-based progress.
- "Moving a task to Done" is treated as the single event that satisfies a
  prerequisite; there's no separate approval/sign-off step.
- The seeded dependency graph (`backend/app/seed.py`) is illustrative,
  representing one software-delivery pipeline; the engine itself is
  domain-agnostic.

**Limitations**
- **No authentication or per-user permissions.** All users share one board.
- **No real-time multi-user sync.** Two people viewing the board
  simultaneously will each see their own actions reflected instantly, but
  won't see the other's changes until they refresh or trigger another
  fetch (no WebSocket/polling layer yet).
- **No notifications.** Propagation updates the database and the UI on
  next load, but doesn't email/Slack anyone when a task they own becomes
  Ready or gets re-Blocked.
- **AI suggestions are advisory only** and depend on an external API call;
  they can be wrong, and the system intentionally requires human
  acceptance before any suggested edge is created.
- **No due-date-driven auto-scheduling.** Due dates are stored and shown,
  but the engine doesn't currently shift a downstream task's due date
  automatically when an upstream task's date slips — only its
  Blocked/Ready status propagates.
- **Deployment is local by default.** A live deployment URL is optional per
  the assignment; deploying the two services (e.g. Render/Railway for the
  API, Vercel for the frontend) is documented above as the DB-swap step but
  not executed as part of this submission.
- **Single-developer sprint scope.** Larger-scale concerns (rate limiting,
  structured logging, automated test suite beyond manual verification,
  horizontal scaling) are noted as natural next steps, not implemented here.

---

## Repository layout

```
taskflow-pro/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app + CORS
│   │   ├── database.py      SQLAlchemy engine/session
│   │   ├── models.py        Task, TaskDependency, StatusHistory
│   │   ├── schemas.py       Pydantic request/response models
│   │   ├── dag.py           The DAG engine (cycle check, readiness, propagation, rollback)
│   │   ├── ai.py            Gemini API dependency-suggestion logic
│   │   ├── seed.py          Seeds 9 tasks / 10 dependency edges
│   │   └── routers/         tasks.py, dependencies.py, ai_router.py
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.js
    │   ├── layout.js
    │   ├── globals.css
    │   ├── lib/api.js       Fetch client for the backend
    │   └── components/      Board.jsx, Column.jsx, TaskCard.jsx, TaskModal.jsx
    └── package.json
```
