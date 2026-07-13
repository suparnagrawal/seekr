from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from collections.abc import Generator
from psycopg_pool import AsyncConnectionPool
import structlog

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

# --- Sync Postgres (for RQ) ---
try:
    engine = create_engine(
        settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("PostgreSQL engine initialized.")
except Exception as e:
    logger.error(f"Error initializing PostgreSQL engine: {e}")
    raise

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Async Postgres (for FastAPI / P2) ---
_async_pg_url = settings.postgres_dsn
pg_pool = AsyncConnectionPool(_async_pg_url, open=False)

async def init_db_pools():
    await pg_pool.open()

async def close_db_pools():
    await pg_pool.close()
