
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    
    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Qdrant Configuration
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "seekr_chunks"
    
    # RQ Queue Configuration
    RQ_DOC_PARSE_TIMEOUT: int = 300
    RQ_EMBED_TIMEOUT: int = 180
    RQ_GRAPH_TIMEOUT: int = 600
    RQ_RETRY_MAX: int = 3
    RQ_RETRY_INTERVALS: str = "10,30,60"
    
    # Redis & RQ Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # Embedding Configuration
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIMENSION: int = 768
    FASTEMBED_CACHE_DIR: str | None = None
    
    # Qdrant Specific
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_NAMESPACE_UUID: str = "12345678-1234-5678-1234-567812345678"

    
    # Storage Configuration
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    
    # LLM Configuration
    LLM_SUPPORTS_JSON_MODE: bool = True
    
    # Retrieval Configuration
    RRF_K: int = 60

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    @property
    def database_url(self) -> str:
        """Constructs the PostgreSQL connection URL."""
        return f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def redis_url(self) -> str:
        """Constructs the Redis connection URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

# Global settings instance
settings = Settings()


