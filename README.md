# AI Course Architect

A production-grade multi-agent system that generates complete, structured courses from a tutor's
knowledge base. Upload PDFs, notes, or URLs — the system vets the brief, fills knowledge gaps, and
produces a full session-by-session course pack with lessons, quizzes, and video scripts.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         BROWSER / CLIENT                         │
│            React 19 + TypeScript + TailwindCSS + Clerk           │
└─────────────────────────┬────────────────────────────────────────┘
                          │ HTTPS
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                      AWS CloudFront CDN                          │
│    /          → S3  (React SPA static assets)                    │
│    /api/*     → ALB (FastAPI backend)                            │
└─────────────┬────────────────────────┬───────────────────────────┘
              │                        │
              ▼                        ▼
   ┌────────────────────┐   ┌─────────────────────┐
   │  S3 Frontend Bucket│   │  ALB  (HTTP :80)     │
   └────────────────────┘   └──────────┬──────────┘
                                        │
                             ┌──────────▼──────────┐
                             │  ECS Fargate — API   │
                             │  FastAPI  :8000      │
                             └──────────┬──────────┘
                                        │ enqueue task
                                        ▼
                             ┌─────────────────────┐
                             │  ElastiCache Redis   │◄──────────────┐
                             │  Celery broker +     │               │
                             │  result backend      │               │
                             └──────────┬──────────┘               │
                                        │                           │
                    ┌───────────────────┼──────────────┐           │
                    ▼                   ▼               ▼           │
       ┌──────────────────┐  ┌────────────────┐  ┌──────────────┐  │
       │ ECS — Worker     │  │ ECS — Beat     │  │ ECS — Flower │  │
       │ Celery+LangGraph │  │ (scheduler)    │  │ (VPC-only)   │  │
       └────────┬─────────┘  └────────────────┘  └──────────────┘  │
                │ asyncio.run()                                      │
   ┌────────────▼──────────────────────────────────────────────┐    │
   │                    LangGraph Pipeline                     │    │
   │                                                           │    │
   │  preprocessor → validation ──(HITL #1)──┐                │    │
   │                                          │                │    │
   │                                 gap_enrichment            │    │
   │                                    (Serper MCP)           │    │
   │                                          │                │    │
   │                         ┌────────────────┘                │    │
   │                         │                                 │    │
   │                 curriculum_planner                        │    │
   │                         │                                 │    │
   │                 curriculum_review ──(HITL #2)             │    │
   │                         │           │                     │    │
   │                        END        retry → curriculum_planner   │
   └───────────────────┬─────────────────────────────────────┘    │
                        │ read/write                                │
          ┌─────────────┼──────────────┐                           │
          ▼             ▼              ▼                           │
 ┌──────────────┐ ┌───────────┐ ┌───────────────┐                 │
 │ Aurora RDS   │ │ S3 Uploads│ │ S3 Vectors    │                 │
 │ Postgres     │ │ (files)   │ │ (embeddings)  │                 │
 │ app state +  │ └───────────┘ └───────────────┘                 │
 │ checkpoints  │                                                   │
 └──────────────┘                                                   │
          │ status updates                                          │
          └──────────────────────────────────────────────────────────┘
```

---

## User Flow

**1. Tutor uploads knowledge base (PDFs, notes, URLs)**
The frontend POSTs the brief to `/api/v1/courses`. FastAPI generates a `thread_id` (UUID), creates
a `CourseRecord` row in the database with status `queued`, enqueues a `pipeline_start` task onto
the Redis `high_priority` queue, and immediately returns the `thread_id` to the frontend. The
frontend starts polling `GET /api/v1/courses/:thread_id` on an interval from this point.

**2. Tutor configures subject, audience age, duration, session count, and preferred formats**
These fields are submitted with the brief and written into the LangGraph initial state.

**3. Preprocessor runs**
The Celery worker picks up the task from Redis and calls `asyncio.run()`, which creates a fresh
event loop and builds a LangGraph graph with a Postgres checkpointer keyed to the `thread_id`.
The preprocessor node reads uploaded files from S3 and fetches any URLs the tutor provided — all
URL fetches run concurrently via `asyncio.gather`. The combined text is chunked (~1 500 tokens,
200 overlap), each chunk is embedded using OpenAI `text-embedding-3-small`, and the embeddings are
stored in S3 Vectors under the key prefix `{thread_id}#` so they are isolated to this run.

**4. Validation Agent vets feasibility, age-appropriateness, content gaps, and estimated cost**
The validation node reads the knowledge summary produced by the preprocessor and produces a
structured feasibility report. It then calls LangGraph `interrupt()` — the graph pauses here, the
worker writes status `awaiting_validation` to the database and returns. The `thread_id` is now the
address of the paused graph state in Postgres.

**5. HITL #1 — tutor sees the pre-flight report and approves or abandons**
The frontend poll hits `GET /api/v1/courses/:thread_id`. The API reads the `CourseRecord` status
from the database, then calls `graph.aget_state(thread_id)` to read the full interrupt payload from
the LangGraph Postgres checkpoint — feasibility report, flags, estimated cost — and returns it to
the frontend. The tutor approves or rejects via `POST .../validation/resume`, which enqueues a
`pipeline_resume_validation` task. If rejected the graph routes to END and status becomes
`rejected`. If approved the pipeline continues.

**6. Gap Enrichment Agent searches Google to fill flagged knowledge gaps**
If the validation report flagged missing topics, the gap enrichment node spawns a Serper MCP server
subprocess via `npx` and runs a ReAct agent that issues one Google search per gap. Results are
embedded and added to S3 Vectors alongside the original knowledge base. On any failure (missing key,
network error) gaps are cleared and the pipeline advances without stalling.

**7. Curriculum Planner Agent generates the session-by-session schedule**
The curriculum planner queries S3 Vectors to retrieve the most relevant chunks for each session
topic, builds a session outline with an LLM call, then generates the full content for every session
in parallel — all sessions run concurrently via `asyncio.gather`, so a 12-session course takes the
same wall-clock time as generating one session.

**8. HITL #2 — tutor approves the curriculum or requests a retry with refinement context**
The graph hits another `interrupt()`. Status becomes `awaiting_curriculum_review`. Same polling
pattern — the frontend reads the checkpoint via `graph.aget_state(thread_id)` and displays the
full generated plan. The tutor approves via `POST .../curriculum/resume` or clicks retry and
types a refinement note (e.g. "make it shorter", "add more exercises").

**9. On approval — course is saved and vectors are cleaned up**
The graph routes to END. The worker writes `curriculum_plan` and `session_content` into the
database, status becomes `completed`, and all S3 Vectors for this `thread_id` are deleted.

**10. On retry — pipeline re-runs from the curriculum planner**
The retry context is injected as a hard constraint (`HARD CONSTRAINT: {text}`) into the curriculum
planner's system prompt. The plan is regenerated with that constraint honoured and loops back to
HITL #2. Up to 5 retries are allowed; the `thread_id` and all prior state are preserved throughout.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript 6, TailwindCSS 4, Vite 5, Clerk |
| API | FastAPI, Python 3.13, uvicorn |
| Agent Orchestration | LangGraph |
| Task Queue | Celery, Redis (ElastiCache) |
| Database | Aurora RDS Serverless v2 (Postgres) / SQLite (dev) |
| Vector Store | AWS S3 Vectors |
| File Storage | AWS S3 |
| Infrastructure | ECS Fargate, ALB, CloudFront, Terraform |
| Observability | LangSmith, CloudWatch |
| Auth | Clerk (JWT) |

---

## Quick Start (Local Dev)

**Prerequisites:** Python 3.13, [uv](https://docs.astral.sh/uv/), Node.js 20, Redis

```bash
# Backend
cd backend
cp .env.example .env          # fill in OPENAI_API_KEY, DATABASE_URL, etc.
uv sync
uv run uvicorn api.main:app --reload --port 8000

# Celery worker (separate terminal)
cd backend
uv run celery -A celery_app.worker worker -Q high_priority,generation,retry --loglevel=info

# Frontend (separate terminal)
npm install
npm run dev
```

---

## Repository Structure

```
.
├── Dockerfile                   # single image for all 4 ECS services
├── package.json                 # frontend (React/Vite)
├── src/                         # frontend source
├── backend/                     # Python backend
│   ├── api/                     # FastAPI app, routes, schemas
│   ├── celery_app/              # Celery worker config and task definitions
│   ├── graph/                   # LangGraph graph definition and state
│   ├── nodes/                   # LangGraph node implementations
│   ├── rag/                     # RAG ingest and retrieval (S3 Vectors)
│   ├── schemas/                 # Pydantic output schemas shared across nodes
│   ├── storage/                 # Database ORM, S3, S3 Vectors helpers
│   ├── tools/                   # LangChain tools used by agents
│   ├── utils/                   # Logging, pipeline helpers, URL fetchers
│   └── tests/                   # pytest test suite
├── infra/
│   └── terraform/               # Terraform modules and environment configs
└── .github/
    └── workflows/               # CI, staging deploy, prod deploy
```

---

## Deployment

| Event | Action |
|---|---|
| Push to `main` | Auto-deploys to **staging** via `deploy-staging.yml` |
| Manual `workflow_dispatch` | Deploys to **prod** — requires reviewer approval in GitHub Environment |

---

## Further Reading

- [Backend README](./backend/README.md) — pipeline nodes, API reference, local dev setup
