
from pathlib import Path
from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load .env file explicitly so os.getenv can read variables that bypass Pydantic
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Resolve the .env next to the backend package so config loads regardless of
# the process working directory (uvicorn/RQ worker/pytest can each differ).
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    """
    Core configuration for the SEEKR backend.
    Loads settings from the environment or a .env file.
    """

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"

    # Project Settings
    PROJECT_NAME: str = "SEEKR Ingestion & Data Layer"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Environment & Auth Configuration
    # ENVIRONMENT controls the default auth posture:
    #   "production" (default) -> auth_enabled=True (secure by default)
    #   "local" / "development" / "test" -> auth_enabled=False
    # ENABLE_AUTH explicitly overrides the environment-derived default.
    # DEV_FALLBACK_ROLE is the role assigned when auth is bypassed locally.
    ENVIRONMENT: str = "production"
    ENABLE_AUTH: Optional[bool] = None
    DEV_FALLBACK_ROLE: str = "viewer"
    
    # PostgreSQL Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "seekr"
    
    # Full Connection String (Overrides individual Postgres settings if provided)
    DATABASE_URL: str | None = None
    
    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Qdrant Configuration
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "seekr_chunks"
    QDRANT_API_KEY: str | None = None
    
    # RQ Job Timeouts
    RQ_DOC_PARSE_TIMEOUT: int = 3600
    RQ_EMBED_TIMEOUT: int = 3600
    RQ_GRAPH_TIMEOUT: int = 7200
    RQ_RETRY_MAX: int = 3
    RQ_RETRY_INTERVALS: str = "10,30,60"

    # Knowledge-graph extraction (P1 -> Neo4j)
    GRAPH_EXTRACTION_ENABLED: bool = True
    # Hard ceiling on chunks considered for extraction. 0 (or negative) means
    # "no cap" — the whole document is processed via windowed, batched extraction.
    GRAPH_EXTRACTION_MAX_CHUNKS: int = 0
    # Chunks per LLM extraction call. The document is split into windows of this
    # size and each window is extracted independently, then merged/canonicalized.
    GRAPH_EXTRACTION_WINDOW: int = 12
    # Max extraction windows run concurrently (bounds memory + gateway pressure).
    GRAPH_EXTRACTION_CONCURRENCY: int = 1

    # Knowledge-graph traversal (P2 retrieval). Previously hardcoded magic
    # numbers inside GraphRetriever; surfaced here so they are tunable and
    # discoverable rather than buried in the algorithm.
    GRAPH_TRAVERSAL_MAX_NODES: int = 50
    GRAPH_TRAVERSAL_MAX_DEPTH: int = 5
    GRAPH_TRAVERSAL_SHALLOW_MAX_NODES: int = 20
    GRAPH_TRAVERSAL_SHALLOW_MAX_DEPTH: int = 2
    # Score a node inherits from its parent per hop (0..1). Higher = flatter decay.
    GRAPH_TRAVERSAL_DECAY: float = 0.85
    # Nodes scoring below this (past the first hop) are pruned from expansion.
    GRAPH_TRAVERSAL_RELEVANCE_THRESHOLD: float = 0.3
    # Multiplier applied to edges whose type is NOT in the query's target set.
    GRAPH_TRAVERSAL_OFFTARGET_MULTIPLIER: float = 0.5
    # Max seeds / passages carried forward.
    GRAPH_TRAVERSAL_MAX_SEEDS: int = 15
    GRAPH_TRAVERSAL_MAX_PASSAGES: int = 20
    
    # Redis & RQ Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str | None = None
    
    # LLM Configuration (OpenAI-compatible endpoint: Fireworks, OpenAI, local, ...)
    # LLM_API_KEY is the primary credential; FAST_MODEL_API_KEY is used by the
    # P2 retrieval classifier and falls back to LLM_API_KEY when unset.
    LLM_API_KEY: str = ""
    FAST_MODEL_API_KEY: str = ""
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: float = 300.0
    LLM_MAX_RETRIES: int = 3

    # Embedding Configuration
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIMENSION: int = 768
    FASTEMBED_CACHE_DIR: str | None = None
    
    # Qdrant Specific
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_NAMESPACE_UUID: str = "12345678-1234-5678-1234-567812345678"
    
    # Model Endpoints
    FAST_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    FAST_MODEL_BASE_URL: str | None = None
    EMBEDDING_MODEL_ENDPOINT: str | None = None
    REMOTE_PARSER_URL: str | None = None
    
    # Storage Configuration
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_REGION: str = "auto"
    S3_BUCKET_NAME: str = "seekr-artifacts"
    
    # LLM Configuration
    LLM_SUPPORTS_JSON_MODE: bool = True
    
    # Retrieval Configuration
    RRF_K: int = 60
    # Lexical (Qdrant text-match) pathway. Uses Qdrant's full-text index
    # via scroll + MatchText for exact keyword recall (tags, part numbers,
    # error codes). Set to False to disable this pathway.
    RETRIEVAL_ENABLE_KEYWORD: bool = True
    
    # Number of fused chunks handed to the generator.
    RETRIEVAL_TOP_K: int = 12

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), case_sensitive=True, extra="ignore")

    @model_validator(mode="after")
    def validate_keys(self):
        if not self.FAST_MODEL_API_KEY and not self.LLM_API_KEY:
            if not self.LLM_BASE_URL or "openai.com" in self.LLM_BASE_URL or "fireworks.ai" in self.LLM_BASE_URL:
                raise ValueError("LLM_API_KEY or FAST_MODEL_API_KEY must be provided for public LLM endpoints.")
        return self

    @property
    def llm_api_key(self) -> str:
        """Primary LLM credential, falling back to the fast-model key."""
        return self.LLM_API_KEY or self.FAST_MODEL_API_KEY

    @property
    def fast_model_api_key(self) -> str:
        """Credential for the P2 fast classifier, falling back to the primary key."""
        return self.FAST_MODEL_API_KEY or self.LLM_API_KEY

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL (psycopg 3 dialect) for the sync engine."""
        if self.DATABASE_URL:
            # SQLAlchemy requires the psycopg dialect explicitly
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def postgres_dsn(self) -> str:
        """Plain libpq DSN for the async psycopg pool (no SQLAlchemy dialect)."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def auth_enabled(self) -> bool:
        """Whether JWT authentication is enforced.

        If ENABLE_AUTH is set explicitly, that wins. Otherwise auth is on
        in production and off everywhere else (local, development, test).
        This is the single source of truth for the entire auth posture.
        """
        if self.ENABLE_AUTH is not None:
            return self.ENABLE_AUTH
        return self.ENVIRONMENT.lower() == "production"

    @property
    def redis_url(self) -> str:
        """Constructs the Redis connection URL."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

# Global settings instance
settings = Settings()


