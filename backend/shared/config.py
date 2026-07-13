
from pathlib import Path
from typing import Optional
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

    # Project Settings
    PROJECT_NAME: str = "SEEKR Ingestion & Data Layer"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
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
    
    # RQ Queue Configuration
    RQ_DOC_PARSE_TIMEOUT: int = 300
    RQ_EMBED_TIMEOUT: int = 180
    RQ_GRAPH_TIMEOUT: int = 600
    RQ_RETRY_MAX: int = 3
    RQ_RETRY_INTERVALS: str = "10,30,60"

    # Knowledge-graph extraction (P1 -> Neo4j)
    GRAPH_EXTRACTION_ENABLED: bool = True
    GRAPH_EXTRACTION_MAX_CHUNKS: int = 40
    
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
    LLM_TIMEOUT: float = 60.0
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
    
    # LLM Configuration
    LLM_SUPPORTS_JSON_MODE: bool = True
    
    # Retrieval Configuration
    RRF_K: int = 60

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), case_sensitive=True, extra="ignore")

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
    def redis_url(self) -> str:
        """Constructs the Redis connection URL."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

# Global settings instance
settings = Settings()


