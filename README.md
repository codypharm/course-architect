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

1. Tutor uploads knowledge base (PDFs, notes, URLs)
2. Tutor configures subject, audience age, duration, session count, and preferred formats
3. Pipeline preprocesses uploads — chunks, embeds, stores in S3 Vectors
4. Validation Agent vets feasibility, age-appropriateness, content gaps, estimated cost
5. **HITL #1** — tutor sees the pre-flight report and approves or abandons
6. Gap Enrichment Agent searches Google (Serper MCP) to fill flagged knowledge gaps
7. Curriculum Planner Agent generates the session-by-session schedule
8. Content Agents generate per-session lessons, video scripts, quizzes, and worksheets in parallel
9. **HITL #2** — tutor approves the curriculum or requests a retry with refinement context
10. Tutor receives the complete structured course pack

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
- [CLAUDE.md](./.claude/CLAUDE.md) — architecture decisions and build rules
