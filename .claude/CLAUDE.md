# AI Course Architect — CLAUDE.md

This file is the source of truth for Claude Code working on this project.
Read it fully before writing any code, suggesting any architecture changes, or answering any questions about the stack.

---

## Project Overview

**AI Course Architect** is a production-grade, multi-agent system that helps tutors and educators generate complete, structured courses from a knowledge base they provide.

A tutor inputs their intent — subject, audience age, duration, preferred format. The system vets the brief, confirms feasibility with the tutor, then autonomously generates a full course: session schedules, lesson content, video scripts, quizzes, and worksheets.

This is a **creator-facing AI product**, not a research tool. The end user is a tutor or independent educator who has real pain around curriculum preparation.

NOTE: always comment your code and add doc strings

---

## Core User Flow

```
1.  Tutor uploads knowledge base (PDFs, notes, URLs)
2.  Tutor configures: subject, audience age, course duration, session count, preferred format
3.  Intake Agent gathers and clarifies the brief conversationally
4.  Validation Agent vets feasibility, age appropriateness, content gaps, estimated cost
5.  Human-in-the-Loop checkpoint — tutor sees pre-flight report and approves or revises
6.  MCP Enrichment Agents augment the knowledge base from external sources
7.  Curriculum Planner Agent generates session-by-session schedule
8.  Specialist Content Agents generate per-session content (lessons, scripts, quizzes, worksheets)
9.  Critic Agent reviews all output for coherence, age-appropriateness, and pedagogical flow
10. Tutor receives structured course pack — schedule, content, downloadable scripts
11. [Optional] Tutor clicks Retry + adds refinement context → pipeline re-runs from Curriculum Planner
```

---

## Architecture

### Agent Orchestration
- **Framework:** LangGraph
- **Why LangGraph:** Stateful multi-step pipeline where each node depends on accumulated state. Native support for Human-in-the-Loop (HITL) checkpoints, conditional branching, and LangSmith observability.
- **Do not suggest switching to CrewAI, AutoGen, or OpenAI Agents SDK.** This decision is final.

### Agent Graph Structure

```
[Intake Agent]
      ↓
[Validation Agent]
      ↓
[HITL Checkpoint] ←── loops back to Intake if tutor requests revision
      ↓ (approved)
[MCP Enrichment Agent]
      ↓
[Curriculum Planner Agent]
      ↓
[Content Generation Agents] (parallel per session)
  ├── Lesson Writer Agent
  ├── Script Writer Agent
  ├── Quiz Generator Agent
  └── Worksheet Designer Agent
      ↓
[Critic / Review Agent]
      ↓
[Output Formatter]

--- Retry Entry Point ---

[Retry Entry] ← tutor clicks retry + optional context
      ↓
[Curriculum Planner Agent]  ← receives original state + retry_context
      ↓
[Content Generation Agents]
      ↓
[Critic Agent]
      ↓
[Output Formatter]
```

### Shared State Object

Every node reads from and writes to a single `CourseState` TypedDict. Never pass data between nodes through any mechanism other than state.

```python
class CourseState(TypedDict):
    # Intake
    subject: str
    audience_age: str
    audience_level: str
    duration_weeks: int
    sessions_per_week: int
    sessions_total: int
    preferred_formats: list[str]          # ["lesson", "video_script", "quiz", "worksheet"]
    uploaded_files: list[str]

    # Validation
    feasibility_report: dict
    flags: list[str]
    suggestions: list[str]
    estimated_cost_usd: float

    # Human verdict
    user_approved: bool
    user_revisions: str

    # Enrichment
    enriched_knowledge_base: str

    # Generation
    curriculum_plan: dict                 # {week: int, session: int, topic: str, objectives: list}
    session_content: list[dict]           # per-session output objects

    # Review
    critic_feedback: dict
    critic_approved: bool

    # Retry
    retry_count: int                      # starts at 0, max 5
    retry_context: str                    # tutor's refinement instruction, empty string if none
    retry_history: list[dict]             # [{retry_count, retry_context, timestamp}]
```

---

## AWS Infrastructure Stack

This project is deployed exclusively on AWS. Do not suggest any non-AWS services. Everything runs inside a single VPC.

### Full Stack

| Layer | Service | Notes |
|---|---|---|
| Compute | ECS Fargate | Four separate services — see below |
| API | FastAPI on Fargate | Behind ALB |
| Queue broker | ElastiCache (Redis) | Celery broker + result backend |
| Task workers | Celery on Fargate | Separate service, scales on queue depth |
| Worker scheduler | Celery Beat on Fargate | Separate service, fixed at 1 task always |
| Worker monitor | Flower on Fargate | Separate service, internal VPC only |
| Database | Aurora RDS Serverless v2 (Postgres) | Same VPC, auto-scales to zero when idle |
| File storage | S3 | Raw uploads, generated course output |
| Vector store | S3 Vectors | Embeddings for RAG pipeline |
| Container registry | ECR | One image, multiple entry points |
| Load balancer | ALB | In front of FastAPI only |
| Logs + metrics | CloudWatch | All services |
| Agent observability | LangSmith | LangGraph step tracing, token costs |

---

### ECS Fargate — Four Separate Services, One Image

All four services use the **same Docker image** pushed to ECR. They are differentiated by their container command in the Fargate task definition — not by separate images. One build, one push to ECR, four deployments with different entry points.

```
ECR Image: your-app:latest  (full codebase)

ECS Cluster
│
├── FastAPI Service
│     Command:  uvicorn api.main:app --host 0.0.0.0
│     CPU:      512      Memory: 1024 MB
│     Scaling:  ALB request count → 1 to 5 tasks
│
├── Celery Worker Service
│     Command:  celery -A queue.worker worker
│     CPU:      2048     Memory: 4096 MB  (heavy — LLM calls + LangGraph)
│     Scaling:  ElastiCache queue depth → 2 to 10 tasks
│
├── Celery Beat Service
│     Command:  celery -A queue.worker beat
│     CPU:      256      Memory: 512 MB
│     Scaling:  Fixed at exactly 1 task — never scale this
│
└── Flower Service
      Command:  celery -A queue.worker flower
      CPU:      256      Memory: 512 MB
      Scaling:  Fixed at 1 task — internal VPC access only, never public
```

**Why four separate services:**
- FastAPI and Celery workers have different CPU and memory profiles
- Workers scale on queue depth, API scales on request count — they need independent scaling policies
- A heavy generation job on a shared container would slow API responses for all users
- Beat must always run as exactly one task — running it alongside workers causes duplicate task scheduling

---

### Queue Architecture (Redis + Celery)

Three Celery queues with separate worker pools:

```
high_priority   →  intake + vetting (fast, cheap, user is waiting interactively)
generation      →  full course generation (slow, expensive, runs in background)
retry           →  re-generation with user context (same as generation, carries retry_context)
```

Celery config essentials:
```python
CELERY_TASK_ROUTES = {
    "tasks.run_intake":      {"queue": "high_priority"},
    "tasks.run_generation":  {"queue": "generation"},
    "tasks.run_retry":       {"queue": "retry"},
}
CELERY_WORKER_CONCURRENCY = 4
CELERY_TASK_ACKS_LATE = True              # task only acked after completion, survives worker crash
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_RETRY_BACKOFF = True
```

Monitor workers via **Flower** — internal VPC access only, never exposed publicly.

---

### S3 Vectors — RAG Pipeline

S3 Vectors is the vector store for the RAG pipeline. Do not suggest Pinecone, Weaviate, pgvector, or any other vector database. S3 Vectors keeps the entire stack inside AWS within the same VPC.

**How it is used:**

```
Tutor uploads knowledge base
        ↓
Ingest pipeline chunks and embeds the content
        ↓
Embeddings stored in S3 Vectors bucket
        ↓
MCP Enrichment Agent stores external content embeddings there too
        ↓
Curriculum Planner + all Content Agents query S3 Vectors
for relevant chunks per session topic at generation time
```

Every content-generating agent retrieves only the chunks relevant to its specific session. The full knowledge base is never stuffed into context. This keeps prompt size and token cost controlled on large knowledge bases.

---

### Aurora RDS Serverless v2

- Postgres-compatible, lives in the same VPC as all Fargate services — no cross-network latency
- Serverless v2 — scales to zero when idle, scales up instantly under load
- Stores: user accounts, course metadata, job state, generation history, retry history
- Do not suggest Supabase — Aurora is the deliberate AWS-native choice

---

### Lambda

Lambda is **not used for the core pipeline.** The LangGraph pipeline is stateful, has HITL pause points, and runs 2–5 minutes — all of which break Lambda's execution model.

Lambda is acceptable only for peripheral, stateless, event-driven tasks:
- S3 event triggers (e.g. initiating ingest pipeline on file upload)
- Notification or email dispatch
- Scheduled lightweight cleanup jobs

If Lambda is proposed for anything touching the LangGraph graph or Celery workers, reject it.

---

## Retry Flow

A tutor can trigger a full retry after seeing the generated course output. Retry is not a fresh run — it carries the original approved state forward plus new context the tutor provides.

**Examples of retry context:**
- "Make the course shorter"
- "The tone is too advanced for my students"
- "Add more practical exercises"
- "Week 3 content is too thin"

**What re-runs vs what is preserved:**

| Component | On Retry |
|---|---|
| Intake data | Preserved — not re-collected |
| Validation report | Preserved — not re-run |
| HITL checkpoint | Skipped — tutor already approved the brief |
| MCP enrichment | Skipped — knowledge base already enriched |
| Curriculum plan | Re-generated with retry_context applied |
| All session content | Re-generated with retry_context applied |
| Critic review | Re-runs on new output |

**Retry context is a hard constraint** — injected into the system prompt of every re-running agent with the label `HARD CONSTRAINT:`. Not passed as a variable, not softened, not paraphrased.

**Retry history accumulates** — by retry 3, the Curriculum Planner receives the full chain of all previous feedback and must honour all of them together, not just the latest.

**Retry limit:** Maximum 5 retries per course. Enforced at the API layer before enqueueing. After 5, the tutor is prompted to start a new brief.

---

## Build Philosophy

### Order of Operations

Always build in this order:
1. **Pipeline first** — LangGraph graph working end to end in raw Python, no infrastructure
2. **Validate agent flow** — each node correct in isolation and in sequence
3. **Wire FastAPI** — wrap the working pipeline in an API layer
4. **Add Redis + Celery** — drop the pipeline behind a queue once task boundaries are clear
5. **Docker Compose** — written once the full local dev architecture is known and stable
6. **AWS deployment** — Fargate task definitions written last, mirroring Docker Compose services

Do not write Docker Compose or Fargate task definitions speculatively. They describe a known architecture, not a hoped-for one.

### Infrastructure Rules
- Never add infrastructure to solve problems that do not exist yet
- Never suggest Lambda for the core pipeline — ruled out permanently
- Never suggest splitting LangGraph nodes into separate Fargate services
- Never suggest non-AWS services — the stack is AWS-only inside one VPC
- Never suggest App Runner — AWS is removing it

---

## Agent Design Rules

### Intake Agent
- Conversational, not a form dump
- Must probe vague answers before proceeding
- Does not pass control to Validation until all required state fields are populated
- Required fields before handoff: `subject`, `audience_age`, `audience_level`, `duration_weeks`, `sessions_per_week`, `preferred_formats`

### Validation Agent
- Produces a structured `feasibility_report` dict — not prose, not a boolean
- Must check: age appropriateness, duration feasibility, knowledge base depth vs schedule, estimated token cost
- Flags are surfaced to the tutor at the HITL checkpoint — never silently resolved

### HITL Checkpoint
- LangGraph `interrupt()` call — graph pauses, does not proceed without explicit user approval
- UI must show: all flags, all suggestions, estimated cost, approve / revise buttons
- On "revise": loops back to Intake Agent with context about what needs clarification
- On "approve": proceeds to MCP enrichment — no further HITL unless Critic Agent escalates

### MCP Enrichment Agent
- Runs after user approval, never before
- Only enriches gaps flagged in the feasibility report
- Enriched content is embedded and stored in S3 Vectors alongside tutor-uploaded content
- Noisy or irrelevant MCP results must be filtered before embedding

### Content Generation Agents
- Each agent retrieves relevant chunks from S3 Vectors for its specific session only — never the full knowledge base
- Age constraint must be enforced in every agent's system prompt
- Script Writer format: intro → learning objectives → body → summary → call to action
- On retry: `retry_context` injected as `HARD CONSTRAINT:` in the system prompt

### Critic Agent
- Reviews all sessions holistically for: curriculum coherence, age-appropriateness, topic progression, gaps or repetition
- Can self-correct minor issues before output
- Escalates blocking issues back to the HITL checkpoint — does not silently drop sessions

---

## Prompt Engineering Rules

- Age range must appear in the system prompt of every content-generating agent
- Tone calibration: under 10 → simple vocabulary, story-based. 10–14 → concrete, relatable. 15–18 → abstract reasoning introduced. Adults → peer tone, professional examples
- Never hallucinate citations — if S3 Vectors returns no relevant chunk, flag the gap, do not invent content
- Structured outputs via Pydantic models for all agent outputs — no free-form text between nodes
- On retry: `retry_context` appears verbatim as `HARD CONSTRAINT: {retry_context}` at the top of the system prompt

---

## File Structure (target, not enforced yet)

```
/
├── CLAUDE.md
├── Dockerfile                   ← single image used by all four Fargate services
├── agents/
│   ├── intake.py
│   ├── validation.py
│   ├── enrichment.py
│   ├── curriculum_planner.py
│   ├── content/
│   │   ├── lesson_writer.py
│   │   ├── script_writer.py
│   │   ├── quiz_generator.py
│   │   └── worksheet_designer.py
│   └── critic.py
├── graph/
│   ├── state.py                 ← CourseState TypedDict
│   ├── graph.py                 ← LangGraph graph definition
│   └── checkpoints.py          ← HITL interrupt logic
├── api/
│   ├── main.py
│   ├── routes/
│   └── schemas/
├── queue/
│   ├── worker.py                ← Celery worker + beat + flower entry points
│   └── tasks.py                 ← task definitions and enqueue logic
├── rag/
│   ├── ingest.py                ← chunk, embed, write to S3 Vectors
│   └── retrieval.py             ← query S3 Vectors per session topic
├── storage/
│   ├── aurora.py                ← Postgres via Aurora RDS
│   └── s3.py                   ← raw file storage
├── mcp/
│   └── adapters.py              ← MCP tool wrappers
├── tests/
│   ├── test_agents/
│   └── test_graph/
├── docker-compose.yml           ← written after architecture is stable
├── infra/
│   └── fargate/                 ← four task definitions, written last
└── .env.example
```

---

## What Not To Do

- Do not suggest RQ — Redis + Celery is the deliberate choice
- Do not suggest AutoGen — wrong paradigm for a sequential pipeline
- Do not suggest Lambda for the core pipeline — ruled out permanently
- Do not suggest App Runner — AWS is removing it
- Do not suggest any non-AWS services — the stack is AWS-only
- Do not suggest Pinecone, Weaviate, or pgvector — S3 Vectors is the deliberate choice
- Do not suggest Supabase — Aurora RDS Serverless v2 is the deliberate choice
- Do not merge FastAPI and Celery worker into the same Fargate service — they scale differently and have different resource profiles
- Do not create separate Docker images per Fargate service — one image, different container commands
- Do not split LangGraph nodes into separate Fargate services
- Do not write Docker Compose or Fargate task definitions before the architecture is stable
- Do not add infrastructure before it is needed by a real problem
- Do not skip the HITL checkpoint — it is a core product feature, not optional
- Do not resolve Validation flags silently — they must always reach the tutor
- Do not let any content agent run without audience age in its system prompt
- Do not stuff the full knowledge base into context — always retrieve from S3 Vectors
- Do not invent citations or sources in any agent output
- Do not re-run intake, validation, HITL, or MCP enrichment on retry
- Do not treat retry_context as optional guidance — it is a hard constraint
- Do not allow more than 5 retries per course — enforce at the API layer



NOTE: I am taking the lea in this project, not you
---

## Current Build Phase

**Phase 1 — Pipeline Only (active)**

Goal: Get the LangGraph graph running end to end in raw Python. No infrastructure, no containers, no queue.

Nodes to build in order:
1. `CourseState` TypedDict in `graph/state.py`
2. Intake Agent — conversational, probing, populates all required state fields
3. Validation Agent — structured feasibility report, never silent
4. HITL Checkpoint — LangGraph `interrupt()`, approve / revise loop
5. Wire the three nodes into a graph and test the full approval and revision flow

Infrastructure, RAG pipeline, API, queue, and AWS deployment come after Phase 1 is complete and validated.