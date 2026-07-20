# ──────────────────────────────────────────────────────────
# Seekr Backend — Production Dockerfile
# Multi-stage build: deps → runtime (slim image, ~200MB)
# ──────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for psycopg binary build, if needed
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency manifest first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv pip install --system -e ".[dev]"

# ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . /app/backend/
# The parent needs a __init__.py for the `backend.` namespace
RUN touch /app/backend/__init__.py

# Create upload directory
RUN mkdir -p /app/backend/uploads

# Health check via the liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/live || exit 1

EXPOSE 8000

# Default: run the API server. Override with docker-compose for the worker.
CMD ["uvicorn", "backend.fabric_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
