import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, BigInteger, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PARSED = "PARSED"
    EMBEDDING = "EMBEDDING"
    EMBEDDED = "EMBEDDED"
    INDEXING = "INDEXING"
    GRAPH_BUILDING = "GRAPH_BUILDING"
    GRAPH_BUILT = "GRAPH_BUILT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True, default=DocumentStatus.UPLOADED.value)
    
    parsed_text_path: Mapped[str | None] = mapped_column(String, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Embedding metadata
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Graph metadata
    graph_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    graph_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
