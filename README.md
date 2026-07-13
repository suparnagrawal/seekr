# Seekr

Seekr is a production-grade retrieval-augmented generation (RAG) system designed for complex industrial document intelligence. It ingests technical documents, constructs a knowledge graph, and exposes a multi-agent reasoning layer that answers natural language queries with full provenance and citation support.

The system is built across three architectural phases, each layered on the last:

- **P1 -- Ingestion Foundation.** Resilient document parsing, chunking, embedding, and knowledge graph extraction.
- **P2 -- Hybrid Retrieval Pipeline.** Three-pathway retrieval (dense, lexical, graph traversal) fused via Reciprocal Rank Fusion.
- **P3 -- Multi-Agent Reasoning.** Copilot orchestrator with LangGraph-based escalation to specialist workers.

---

## Architecture

```
                         +------------------+
                         |   Next.js 16     |
                         |   Frontend       |
                         |  (React 19, TS)  |
                         +--------+---------+
                                  |
                           SSE / REST
                                  |
                         +--------v---------+
                         |   FastAPI         |
                         |   Fabric API      |
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
     +--------v-------+  +-------v--------+  +-------v--------+
     | P3 Agent Layer  |  | P2 Retrieval   |  | P1 Ingestion   |
     | (Copilot,       |  | Pipeline       |  | Worker (RQ)    |
     |  Supervisor,    |  | (Dense, KW,    |  | Parsing,       |
     |  Workers)       |  |  Graph, RRF)   |  | Chunking,      |
     +--------+--------+  +-------+--------+  | Embedding,     |
              |                   |            | Graph Extract) |
              |                   |            +--+----+----+---+
              |                   |               |    |    |
         +----v----+         +----v----+     +----v--+ | +--v----+
         | OpenAI- |         | Qdrant  |     | S3    | | | Neo4j |
         | compat  |         | (vec)   |     |       | | |       |
         | LLM     |         +---------+     +-------+ | +-------+
         +---------+                            +-------v-------+
                                                | PostgreSQL    |
                                                | (metadata,    |
                                                |  entities,    |
                                                |  FTS)         |
                                                +---------------+
```

### Core Technologies

| Layer          | Technology                                              |
| -------------- | ------------------------------------------------------- |
| API            | FastAPI (async, application factory pattern)             |
| Frontend       | Next.js 16, React 19, TypeScript, Tailwind CSS 4         |
| Database       | PostgreSQL 15 (SQLAlchemy 2 ORM, Alembic migrations)     |
| Vector Store   | Qdrant v1.18 (dense cosine similarity)                   |
| Graph Store    | Neo4j 5 (Cypher, async driver)                           |
| Task Queue     | Redis 7 + RQ (background ingestion with retry policies)  |
| Parsing        | IBM Docling (layout-aware PDF extraction with OCR)        |
| Embeddings     | FastEmbed (`BAAI/bge-base-en-v1.5`, 768-dim)             |
| LLM            | OpenAI-compatible API (configurable: OpenAI, Fireworks, local VLLM) |
| Agent Runtime  | LangGraph (state-machine orchestration for escalation)    |
| Object Storage | S3-compatible (AWS S3, Supabase, Cloudflare R2)           |
| Auth           | JWT with remote JWKS validation (RS256)                   |
| CI             | GitHub Actions (Ruff lint, Pytest, Next.js build)         |

---

## P1 -- Ingestion Pipeline

Documents uploaded via the `/api/v1/upload` endpoint enter a multi-stage background pipeline orchestrated by RQ.

**Stage sequence:**

1. **Upload and Deduplication.** The file is streamed to S3 while computing a SHA-256 hash. A unique constraint on the hash column prevents duplicate processing; concurrent uploads of the same file are handled via PostgreSQL constraint introspection.

2. **Parsing.** IBM Docling extracts structured Markdown from PDFs with full OCR and table structure recognition. Parsing can be offloaded to a remote GPU gateway over an ngrok tunnel for resource-constrained deployments.

3. **Hierarchical Chunking.** Docling's `HierarchicalChunker` segments the parsed document using layout-aware heading boundaries. Each chunk receives a deterministic SHA-256 ID derived from its content, heading path, and page location.

4. **Embedding and Indexing.** FastEmbed generates 768-dimensional vectors in batches of 32. Vectors are upserted directly to Qdrant with full provenance metadata. The job is resumable: on restart, it queries Qdrant for already-indexed chunk IDs and skips them.

5. **Knowledge Graph Extraction.** The document is split into fixed-size windows (configurable, default 12 chunks per window). Each window is sent to the configured LLM for open-domain entity and relationship extraction. Results across windows are canonicalized and deduplicated before a single batched write to Neo4j. Node and relationship types are LLM-derived (not allow-listed), with all interpolated Cypher labels hard-restricted to `[a-z0-9_]` / `[A-Z0-9_]` character classes to prevent injection.

Steps 4 and 5 fan out in parallel from the parsing stage. The document tracks fine-grained status transitions:
`UPLOADED -> QUEUED -> PROCESSING -> PARSED -> EMBEDDING/GRAPH_BUILDING -> EMBEDDED/GRAPH_BUILT -> COMPLETED`.

**Resilience features:**

- Exponential backoff retry policies on all RQ jobs.
- A `CleanupService` rolls back orphaned S3 artifacts and database rows on failure.
- A DLQ Auto-Recovery Daemon polls the RQ `FailedJobRegistry` every 60 seconds; when the external ML gateway comes back online, it automatically requeues all failed jobs.
- Infrastructure boot uses synchronous exponential backoff probes against Redis, Qdrant, and Neo4j before accepting traffic.

---

## P2 -- Retrieval Pipeline

The retrieval layer is built on an object-oriented pipeline architecture with pluggable retriever pathways and a formal fusion strategy.

**Pathways:**

| Retriever   | Source      | Description                                                                                                                   |
| ----------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Dense       | Qdrant      | Cosine similarity search over BGE embeddings.                                                                                 |
| Keyword     | PostgreSQL  | Full-text search via `plainto_tsquery` on the `chunks.fts` column. Restores exact-match recall for tags, part numbers, codes. |
| Graph       | Neo4j       | Level-synchronous best-first traversal from entity seeds, with configurable decay, relevance pruning, and hub/bridge detection.|

All retrievers implement a `BaseRetriever` abstract class that enforces a standard error boundary: a failing pathway returns an empty result rather than crashing the pipeline.

**Fusion:**

Results from all active pathways are merged via Reciprocal Rank Fusion (RRF). The fused set is truncated to `RETRIEVAL_TOP_K` (default 8) chunks before being passed to the generation layer.

**Context Assembly:**

Before retrieval, a `ContextAssembler` builds a `TraversalContext` by:

1. Classifying the query type (factual, diagnostic, procedural, open) via heuristic rules with LLM fallback.
2. Formulating a graph search strategy: the LLM extracts entity search terms and target relationship types from the query and recent conversation history.
3. Resolving explicit and implicit entity tags from PostgreSQL's entity registry.
4. Generating a query embedding via a cascading fallback chain (remote endpoint, OpenAI, local FastEmbed).

**Graph Traversal:**

The `GraphRetriever` implements a level-synchronous traversal that fetches all neighbors for an entire expansion wave in a single batched Cypher query, bounding round-trips by depth rather than node count. Traversal parameters (max nodes, max depth, decay factor, relevance threshold, off-target multiplier) are fully configurable via environment variables. For diagnostic and open queries, additional bridge-node and hub-detection passes supplement the primary traversal.

---

## P3 -- Agent Layer

The agent layer implements a Copilot-Supervisor-Worker architecture for multi-step reasoning, with all responses streamed as Server-Sent Events (SSE).

**Copilot** (`/api/v1/query`): The primary entry point. Retrieves context via P2, streams an initial LLM-generated answer, then evaluates whether the query requires specialist reasoning.

**Supervisor**: A pure routing component. If the Copilot escalates, the Supervisor classifies the query into one of three specialist domains using LLM-based routing with keyword-based and default fallbacks. The Supervisor never performs retrieval, generation, or database access.

**Specialist Workers** (also available as direct endpoints):

| Worker    | Endpoint              | Domain                                                |
| --------- | --------------------- | ----------------------------------------------------- |
| Asset     | `/api/v1/agents/asset`    | Asset history, specifications, maintenance records    |
| Diagnose  | `/api/v1/agents/diagnose` | Root-cause analysis, failure investigation            |
| Comply    | `/api/v1/agents/comply`   | Regulatory compliance, safety protocol verification   |

Direct agent endpoints bypass the Copilot and Supervisor entirely. They construct `AgentState` from the request and invoke the worker workflow directly.

The LangGraph workflow manages the state machine for escalated queries: `Supervisor -> Router -> Worker -> Stream`. All LLM calls (streaming and non-streaming) are centralized in a shared invocation layer with Tenacity retry policies and explicit reasoning-content filtering.

---

## Frontend

The frontend is a Next.js 16 application (React 19, TypeScript) with the following views:

| Route          | Description                                                        |
| -------------- | ------------------------------------------------------------------ |
| `/`            | Knowledge graph explorer (Cytoscape.js) with entity side panel     |
| `/documents`   | Document management: upload, status tracking, retry failed jobs    |
| `/agents/diagnose` | Direct diagnostic agent interface                             |
| `/compliance`  | Compliance verification interface                                  |
| `/entity/[tag]`| Deep entity detail view                                            |

State management uses Zustand. Authentication is handled via JWT with a React context provider. The UI is built with Tailwind CSS 4, Framer Motion animations, and Lucide icons.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker and Docker Compose

### 1. Start Infrastructure

```bash
docker compose up -d
```

This provisions PostgreSQL, Redis, Qdrant, and Neo4j with persistent volumes.

### 2. Backend Setup

```bash
cd backend
cp .env.example .env       # Edit with your LLM API key and connection strings
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 3. Database Migrations

```bash
cd backend
alembic upgrade head
```

### 4. Run the API Server

```bash
uv run uvicorn backend.fabric_api.main:app --reload --port 8000
```

### 5. Run the Ingestion Worker

In a separate terminal:

```bash
cd backend
uv run python -m backend.ingestion_worker.main
```

### 6. Frontend Setup

```bash
cd frontend
cp .env.example .env       # Configure API URL and auth settings
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000` and the API at `http://localhost:8000`.

---

## Configuration

All backend configuration is centralized in `backend/shared/config.py` via Pydantic Settings, loaded from the `.env` file adjacent to the backend package. Key configuration groups:

| Group                  | Variables                                                              |
| ---------------------- | ---------------------------------------------------------------------- |
| LLM                   | `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TEMPERATURE`         |
| PostgreSQL             | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `DATABASE_URL` |
| Neo4j                  | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`                            |
| Qdrant                 | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION`                      |
| Redis                  | `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL`                                |
| Graph Extraction       | `GRAPH_EXTRACTION_ENABLED`, `GRAPH_EXTRACTION_WINDOW`, `GRAPH_EXTRACTION_CONCURRENCY` |
| Graph Traversal        | `GRAPH_TRAVERSAL_MAX_NODES`, `GRAPH_TRAVERSAL_DECAY`, `GRAPH_TRAVERSAL_RELEVANCE_THRESHOLD` |
| Retrieval              | `RETRIEVAL_TOP_K`, `RETRIEVAL_ENABLE_KEYWORD`, `RRF_K`                 |
| Object Storage         | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_BUCKET_NAME`                |
| Auth                   | `ENABLE_AUTH`, `JWKS_URL`, `JWT_AUDIENCE`                               |
| Remote ML Gateway      | `REMOTE_PARSER_URL`, `EMBEDDING_MODEL_ENDPOINT`, `LLM_BASE_URL`        |

Authentication is toggled via `ENABLE_AUTH`. When disabled (default for local development), all endpoints are open. When enabled, all non-health endpoints require a valid JWT verified against the configured JWKS URL.

---

## Project Structure

```
seekr/
  backend/
    fabric_api/           # FastAPI application (routes, lifespan, middleware)
      routes/             #   /upload, /documents, /status, /health, /ready
    app/
      api/                # P2/P3 API routers (query, agents, graph)
      retrieval/          # P2 retrieval pipeline
        retrievers/       #   Dense, Keyword, Graph implementations
      agents/             # P3 agent layer
        copilot/          #   Query orchestrator, trigger classifier
        supervisor/       #   LLM + keyword routing
        asset/            #   Asset specialist worker
        diagnose/         #   Diagnostic specialist worker
        comply/           #   Compliance specialist worker
        graph/            #   LangGraph escalation workflow
        shared/           #   LLM client, streaming, state, tools
      db/                 # Query functions (Qdrant, Neo4j, PostgreSQL, Redis)
      schemas/            # Pydantic request/response schemas
      kg/                 # Knowledge graph shared tools
    ingestion_worker/     # RQ background jobs
      jobs.py             #   Parsing + chunking pipeline
      embedding_jobs.py   #   Embedding + Qdrant indexing
      graph_jobs.py       #   LLM-based entity/relationship extraction
      orchestrator.py     #   Job chaining and fan-out
    shared/               # Cross-cutting concerns
      config.py           #   Centralized Pydantic Settings
      models/             #   SQLAlchemy models (Document, Entity, Fact)
      services/           #   Parsing, Chunking, Embedding, Qdrant, Upload
      repositories/       #   Document repository (data access layer)
      storage.py          #   S3-compatible object storage
      security.py         #   JWT/JWKS authentication
    alembic/              # Database migration scripts
    tests/                # Pytest suite
  frontend/
    app/                  # Next.js App Router pages
      (dashboard)/        #   Authenticated dashboard routes
      login/              #   Authentication page
    components/           #   React components (graph, agents, layout, UI)
    lib/                  #   API client, auth context, stores, types
  scripts/                # Deployment and utility scripts
  docs/                   # Architecture specs and handover documents
  docker-compose.yml      # Infrastructure services
  .github/workflows/      # CI pipeline
```

---

## Testing

```bash
cd backend
uv run pytest tests/
```

The test suite covers upload idempotency, retrieval pipeline correctness, graph extraction parsing, and JWT security validation. CI runs Ruff linting, the full Pytest suite against containerized infrastructure, and a Next.js production build on every push to `main`.

---

## Deployment

The repository includes Render deployment scripts (`scripts/render-build.sh`, `scripts/render-start.sh`). The start script launches the RQ ingestion worker in the background with a 20-second delayed start to avoid ONNX/CPU deadlocks with the Uvicorn process. Thread-count environment variables (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, etc.) are pinned to 1 to minimize memory footprint on constrained instances.

For resource-constrained deployments, heavy ML workloads (Docling parsing, embedding generation, LLM inference) can be offloaded to a remote GPU notebook via ngrok. The backend detects the presence of `REMOTE_PARSER_URL` and `LLM_BASE_URL` and routes accordingly.

---

## License

MIT License. See [LICENSE](LICENSE) for details.