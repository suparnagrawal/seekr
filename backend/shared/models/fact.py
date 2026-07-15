import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject_tag: Mapped[str] = mapped_column(String, nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String, nullable=False, index=True)
    object_tag: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facts.id"), nullable=True)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
