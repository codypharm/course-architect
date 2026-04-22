# AI Course Architect — Backend

FastAPI + LangGraph + Celery backend for the AI Course Architect pipeline.

---

## Architecture

```
              HTTP Request (via CloudFront → ALB)
                           │
                           ▼
              ┌────────────────────────────┐
              │     FastAPI Application     │
              │      (api/main.py)          │
              │                             │
              │  POST /api/v1/courses       │──── enqueue ────┐
              │  GET  /api/v1/courses/:id   │                  │
              │  GET  /api/v1/courses/:id/brief                │
              │  POST .../validation/resume │                  │
              │  POST .../curriculum/resume │                  │
              │  GET  .../users/:id/courses │                  │
              │  POST /api/v1/files         │                  │
              │  GET  /health               │                  │
              └────────────┬───────────────┘                  │
                           │ SQLAlchemy (asyncpg)             │
              ┌────────────▼───────────────┐     ┌────────────▼──────────────┐
              │  Aurora RDS Postgres        │     │  Redis (ElastiCache)       │
              │  CourseRecord ORM table     │     │  Celery broker + backend   │
              │  (status, plan, content)    │     └────────────┬──────────────┘
              └────────────────────────────┘                  │ consume
                                                 ┌────────────▼──────────────┐
                                                 │      Celery Worker         │
                                                 │   (celery_app/tasks.py)    │
                                                 │   NullPool DB engine       │
                                                 └────────────┬──────────────┘
                                                              │ asyncio.run()
                                                 ┌────────────▼──────────────┐
                                                 │     LangGraph Pipeline     │
                                                 │                            │
                                                 │  ┌──────────────────────┐  │
                                                 │  │   preprocessor       │  │
                                                 │  │   read files/URLs    │  │
                                                 │  │   LLM extract+merge  │  │
                                                 │  │   chunk+embed→S3Vec  │  │
                                                 │  └──────────┬───────────┘  │
                                                 │             │               │
                                                 │  ┌──────────▼───────────┐  │
                                                 │  │   validation          │  │
                                                 │  │   age + duration +    │  │
                                                 │  │   depth check         │  │
                                                 │  │   cost estimation     │  │
                                                 │  │   ── HITL #1 ──       │  │
                                                 │  └──────────┬───────────┘  │
                                                 │             │ (if gaps)     │
                                                 │  ┌──────────▼───────────┐  │
                                                 │  │   gap_enrichment     │  │
                                                 │  │   Serper MCP search  │  │
                                                 │  │   (npx stdio)        │  │
                                                 │  │   embed→S3 Vectors   │  │
                                                 │  └──────────┬───────────┘  │
                                                 │             │               │
                                                 │  ┌──────────▼───────────┐  │
                                                 │  │  curriculum_planner  │  │
                                                 │  │  RAG retrieval       │  │
                                                 │  │  → outline LLM call  │  │
                                                 │  │  → parallel content  │  │
                                                 │  │    (asyncio.gather)  │  │
                                                 │  └──────────┬───────────┘  │
                                                 │             │               │
                                                 │  ┌──────────▼───────────┐  │
                                                 │  │  curriculum_review   │  │
                                                 │  │  ── HITL #2 ──       │  │
                                                 │  │  approve → END       │  │
                                                 │  │  retry → planner     │  │
                                                 │  └──────────────────────┘  │
                                                 └────────────────────────────┘
                                                              │
                              ┌───────────────────────────────┼──────────────────┐
                              ▼                               ▼                  ▼
                   ┌──────────────────┐          ┌──────────────────┐  ┌──────────────────┐
                   │  Aurora RDS       │          │   S3 Vectors      │  │   S3 Uploads     │
                   │  LangGraph        │          │   thread-scoped   │  │   raw files from │
                   │  checkpoints      │          │   embeddings      │  │   tutor          │
                   └──────────────────┘          └──────────────────┘  └──────────────────┘
```

---

## Directory Structure

```
backend/
├── api/
│   ├── main.py                    # FastAPI app factory, lifespan (DB + checkpointer + S3 Vectors init)
│   ├── dependencies/
│   │   └── auth.py                # Clerk JWT verification dependency
│   ├── routes/
│   │   ├── courses.py             # Course CRUD + HITL resume endpoints
│   │   └── files.py               # S3 file upload endpoint
│   └── schemas/
│       ├── courses.py             # Request/response Pydantic models
│       └── files.py               # File upload response model
├── celery_app/
│   ├── worker.py                  # Celery app, broker config, queue routing
│   └── tasks.py                   # pipeline_start, pipeline_resume_validation, pipeline_resume_curriculum
├── graph/
│   ├── graph.py                   # LangGraph StateGraph definition, open/close checkpointer
│   └── state.py                   # CourseState TypedDict
├── nodes/
│   ├── preprocessor.py            # Reads uploads + URLs, chunks, embeds, writes S3 Vectors
│   ├── validation.py              # Feasibility report + HITL #1 interrupt
│   ├── gap_enrichment.py          # Serper MCP ReAct agent, fills knowledge gaps
│   ├── curriculum_planner.py      # Generates session outline + parallel content generation
│   └── curriculum_review.py       # HITL #2 interrupt
├── rag/
│   ├── ingest.py                  # chunk → embed → put_vectors
│   ├── retrieval.py               # query_vectors → rerank → return chunks
│   └── store.py                   # Low-level embedding helpers
├── schemas/
│   ├── curriculum.py              # CurriculumPlan, SessionContent Pydantic models
│   ├── preprocessor.py            # KnowledgeSummary Pydantic model
│   └── validation.py              # FeasibilityReport Pydantic model
├── storage/
│   ├── database.py                # SQLAlchemy async engine + session factory
│   ├── models.py                  # CourseRecord ORM model
│   ├── s3.py                      # S3 upload/download/delete helpers
│   └── s3vectors.py               # S3 Vectors put/query/delete + lazy index creation
├── tools/
│   └── curriculum_planner.py      # LangChain tools used by the curriculum planner agent
├── utils/
│   ├── fetchers.py                # URL content fetcher (web pages, YouTube transcripts)
│   ├── logging.py                 # Structured logger factory
│   └── pipeline.py                # derive_pipeline_status, graph_config helpers
├── tests/
│   └── test_agents/               # pytest tests per node
├── main.py                        # Dev entry point (runs uvicorn directly)
├── pyproject.toml                 # uv/pip dependencies
└── .env.example                   # Environment variable template
```

---

## Pipeline Nodes

| Node | Key Reads | Key Writes | HITL |
|---|---|---|---|
| preprocessor | uploaded_files, enrichment_urls | knowledge_summary, vectors in S3 | No |
| validation | knowledge_summary, duration_weeks, audience_age | feasibility_report, flags, estimated_cost_usd | Yes (#1) |
| gap_enrichment | flags, knowledge_summary | enriched knowledge_summary, additional vectors | No |
| curriculum_planner | knowledge_summary, retry_context | curriculum_plan, session_content | No |
| curriculum_review | curriculum_plan, session_content | curriculum_approved, retry_context | Yes (#2) |

---

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | /api/v1/courses | Clerk JWT | Start pipeline, enqueue task |
| GET | /api/v1/courses/:thread_id | Clerk JWT | Poll status / fetch output |
| GET | /api/v1/courses/:thread_id/brief | Clerk JWT | Fetch original brief from checkpoint |
| POST | /api/v1/courses/:thread_id/validation/resume | Clerk JWT | HITL #1 — approve or reject |
| POST | /api/v1/courses/:thread_id/curriculum/resume | Clerk JWT | HITL #2 — approve or retry |
| GET | /api/v1/users/:user_id/courses | Clerk JWT | List all courses for a user |
| POST | /api/v1/files | Clerk JWT | Upload files to S3 |
| GET | /health | None | ALB health probe |

---

## Celery Queues

| Queue | Tasks | When |
|---|---|---|
| high_priority | pipeline_start, pipeline_resume_validation | User waiting interactively |
| generation | pipeline_resume_curriculum (approval) | Background content generation |
| retry | pipeline_resume_curriculum (retry=True) | Background re-generation with retry context |

---

## RAG Pipeline

```
Tutor uploads files / provides URLs
        │
        ▼
preprocessor node
  ├── fetch URL content (utils/fetchers.py)
  ├── read S3 file content
  ├── chunk text (1 500 tokens, 200 overlap)
  ├── embed chunks (text-embedding-3-small, dim=1536)
  └── put_vectors → S3 Vectors (key prefix: "{thread_id}#")
        │
        ▼ (gap enrichment adds more vectors here)
        │
curriculum_planner / content agents
  └── query_vectors(thread_id, query_embedding, top_k=10)
        → cosine similarity search scoped to this thread
        → reranked by relevance
        → top chunks injected into agent context
```

Thread isolation: every vector key is prefixed with `{thread_id}#`, so each pipeline run queries
only its own embeddings. Vectors are deleted at terminal states (completed, rejected, failed).

---

## Database Schema

**Table: `courses`**

| Column | Type | Description |
|---|---|---|
| id | String (PK) | UUID |
| thread_id | String (unique) | LangGraph thread identifier |
| user_id | String | Clerk user ID |
| subject | String | Course subject |
| status | String | Pipeline status (see below) |
| uploaded_files | JSON | List of S3 keys for uploaded files |
| curriculum_plan | JSON | Generated plan — set on completion |
| session_content | JSON | Generated sessions — set on completion |
| created_at | DateTime | UTC timestamp |
| updated_at | DateTime | UTC timestamp, updated on each transition |

**Status values:**

```
queued → processing → awaiting_validation → awaiting_curriculum_review → completed
                                         └─ rejected
                    └─ failed
```

---

## Environment Variables

See [.env.example](.env.example) for the full template. Key variables:

| Variable | Description |
|---|---|
| OPENAI_API_KEY | OpenAI API key (LLM calls + embeddings) |
| DATABASE_URL | Postgres (`postgresql+asyncpg://...`) or SQLite (`sqlite+aiosqlite:///...`) |
| REDIS_URL | Redis URL for Celery broker and result backend |
| S3_UPLOADS_BUCKET | S3 bucket name for raw tutor uploads |
| S3_VECTORS_BUCKET | S3 Vectors vector bucket name (see note below) |
| S3_VECTORS_INDEX | Vector index name (default: `course-chunks`) |
| AWS_REGION | AWS region (e.g. `eu-north-1`) |
| CLERK_JWKS_URL | Clerk JWKS URL for JWT verification |
| ALLOWED_ORIGINS | Comma-separated CORS origins |
| SERPER_API_KEY | Serper API key for gap enrichment Google Search |
| LANGSMITH_API_KEY | LangSmith API key for LangGraph tracing |

> **S3 Vectors note:** The vector bucket must be created manually via CLI — the Terraform AWS
> provider does not yet support `aws_s3vectors_vector_bucket`. Run once per environment:
> ```bash
> aws s3vectors create-vector-bucket --vector-bucket-name <bucket> --region <region>
> aws s3vectors create-index --vector-bucket-name <bucket> --index-name course-chunks \
>   --data-type float32 --dimension 1536 --distance-metric cosine --region <region>
> ```

---

## Local Dev Setup

```bash
# 1. Enter the backend directory
cd backend

# 2. Copy and fill the env file
cp .env.example .env
# Set at minimum: OPENAI_API_KEY, DATABASE_URL=sqlite+aiosqlite:///./courses.db,
#                 REDIS_URL=redis://localhost:6379/0

# 3. Install dependencies
uv sync

# 4. Start Redis (required for Celery)
docker run -p 6379:6379 redis:7-alpine

# 5. Run the API
uv run uvicorn api.main:app --reload --port 8000

# 6. Run the Celery worker (separate terminal)
uv run celery -A celery_app.worker worker -Q high_priority,generation,retry --loglevel=info

# 7. (Optional) Run Flower to monitor tasks
uv run celery -A celery_app.worker flower --port=5555
```

---

## Testing

```bash
cd backend
uv run pytest tests/
```

---

## ECS Services

All four services use the same Docker image from ECR, differentiated only by their container command.

| Service | Command | CPU | Memory | Scaling |
|---|---|---|---|---|
| api | `uvicorn api.main:app --host 0.0.0.0 --port 8000` | 512 | 1024 MB | ALB requests → 1–5 tasks |
| worker | `celery -A celery_app.worker worker -Q high_priority,generation,retry --loglevel=info` | 2048 | 4096 MB | Queue depth → 2–10 tasks |
| beat | `celery -A celery_app.worker beat --loglevel=info` | 256 | 512 MB | Fixed 1 |
| flower | `celery -A celery_app.worker flower --port=5555` | 256 | 512 MB | Fixed 1, VPC-internal |

> **Checkpointer note:** The FastAPI process uses a shared `AsyncConnectionPool` opened during
> lifespan. Celery tasks each call `asyncio.run()` (new event loop per task) and create a fresh
> `AsyncPostgresSaver` connection inside that loop. The Celery DB engine uses `NullPool` for the
> same reason — no connection reuse across event loops.
