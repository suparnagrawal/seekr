import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from backend.shared.database import Base

class Fact(Base):
    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subject_tag: Mapped[str] = mapped_column(String, nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # object_tag is nullable: a fact like "P-301 has inner_diameter 4in" stores
    # the literal in object_value and leaves object_tag NULL.
    object_tag: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # Literal object value (e.g. "4in", "316SS", "150 PSI")
    object_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String, default="active", index=True)
    
    # Citation provenance: {page, bbox, passage_text} from the source document
    source_passage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # How this fact was extracted: "llm", "rule", "manual", etc.
    extraction_method: Mapped[str | None] = mapped_column(String, nullable=True)
    
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facts.id"), nullable=True)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

