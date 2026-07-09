# Seekr: Industrial Knowledge Fabric

Seekr is an advanced, production-grade ingestion and retrieval engine (RAG) designed to process, embed, and query complex industrial documents. 

The project is currently at the completion of **Phase 1 (P1): Ingestion Foundation**, establishing a highly resilient, scalable pipeline for document processing.

## 🏗️ Architecture (P1: Ingestion)

The P1 backend is built on a modern, asynchronous Python stack orchestrated via FastAPI and RQ (Redis Queue).

### Core Technologies
- **API**: FastAPI
- **Database**: PostgreSQL 15 (SQLAlchemy ORM + Alembic)
- **Vector Store**: Qdrant v1.9.1 (Dense & Sparse capabilities)
- **Graph Store**: Neo4j 5
- **Task Queue**: Redis 7 + RQ
- **Parsing**: IBM Docling
- **Embeddings**: FastEmbed (`BAAI/bge-base-en-v1.5`)

### Key Ingestion Features
- **Idempotent Uploads**: Deterministic `sha256` hashing prevents duplicate document processing. Uses precise PostgreSQL constraint introspection to handle concurrent upload race conditions.
- **Robust Background Processing**: Long-running parsing and embedding tasks are decoupled via RQ, configured with dynamic timeouts and centralized exponential backoff policies (`rq_policy.py`).
- **Distributed Transaction Recovery**: A dedicated `CleanupService` orchestrates rollback compensations, ensuring that database failures or queue errors never leave orphaned artifact directories or dangling rows.
- **Synchronous Infrastructure Boot**: FastAPI `lifespan` implements granular, synchronous exponential backoff checks (`wait_for_dependency`) for Redis, Qdrant, and Neo4j, ensuring seamless cold boots in containerized environments.

## 🚀 Getting Started

### 1. Start Infrastructure
Seekr requires PostgreSQL, Redis, Qdrant, and Neo4j. A pre-configured, pinned `docker-compose.yml` is provided in the repository root.

```bash
docker-compose up -d
```

### 2. Environment Setup
Create a virtual environment and install dependencies. The backend uses `uv` for lightning-fast package management.

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 3. Database Migrations
Initialize the PostgreSQL schema using Alembic:

```bash
cd backend
alembic upgrade head
```

### 4. Run the API
Start the FastAPI server:

```bash
uv run uvicorn backend.fabric_api.main:app --reload --port 8000
```

### 5. Run the Ingestion Worker
In a separate terminal window, start the RQ worker to process background ingestion tasks:

```bash
cd backend
uv run python -m backend.ingestion_worker.worker
```

## 🛣️ Roadmap

- [x] **P1: Ingestion Foundation** (Current)
- [ ] **P2: Hybrid Retrieval Pipeline** (Upcoming: RRF, Dense + Keyword, Reranking, Context Assembly)
- [ ] **P3: Knowledge Graph Integration** (Entity extraction and Cypher queries)