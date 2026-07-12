from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from collections.abc import Generator
import structlog

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

try:
    engine = create_engine(
        settings.database_url,
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
    """
    Dependency to get a database session.
    Yields the session and ensures it is closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
