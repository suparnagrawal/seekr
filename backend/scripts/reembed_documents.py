"""
Migration script: Re-embed existing documents with heading-aware embeddings.

Handles the legacy chunks.json → chunks.jsonl format mismatch.
Existing documents were ingested before the S3 migration and have local
chunks.json files (JSON arrays). This script reads them, converts to NDJSON,
uploads to S3, deletes old Qdrant points, and re-runs the embedding job.

Usage:
    uv run python -m backend.scripts.reembed_documents [--dry-run] [--document-id UUID]
"""

import argparse
import json
import os
import structlog

from backend.shared.database import SessionLocal
from backend.shared.repositories.document_repository import DocumentRepository
from backend.shared.config import settings
from backend.shared.storage import storage_manager
from backend.shared.services.qdrant_service import get_qdrant_service
from backend.shared.services.embedding_service import get_embedding_service
from backend.shared.models.document import DocumentStatus

logger = structlog.get_logger(__name__)


def _read_local_chunks_json(document_id: str) -> list[dict] | None:
    """Try to read legacy local chunks.json for a document."""
    local_path = settings.UPLOAD_DIR / str(document_id) / "chunks.json"
    if not local_path.exists():
        return None
    with open(local_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _upload_as_ndjson(document_id: str, chunks: list[dict]) -> None:
    """Convert a list of chunk dicts to NDJSON and upload to S3."""
    ndjson = "\n".join(json.dumps(c) for c in chunks)
    storage_manager.save_artifact(document_id, "chunks.jsonl", ndjson)
    logger.info("Uploaded chunks.jsonl to S3", document_id=document_id, chunk_count=len(chunks))


def _delete_qdrant_points(document_id: str) -> None:
    """Delete all existing Qdrant points for a document."""
    qdrant_service = get_qdrant_service()
    from qdrant_client.http import models
    qdrant_service._get_client().delete(
        collection_name=qdrant_service.collection_name,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )
    logger.info("Deleted Qdrant points", document_id=document_id)


def reembed_document(document_id: str, dry_run: bool = False) -> bool:
    """Re-embed a single document with heading-aware embeddings."""
    logger.info("Processing document", document_id=document_id, dry_run=dry_run)

    # Step 1: Read legacy chunks.json
    chunks = _read_local_chunks_json(document_id)
    if chunks is None:
        logger.warning("No local chunks.json found, skipping", document_id=document_id)
        return False

    logger.info("Read local chunks.json", document_id=document_id, chunk_count=len(chunks))

    if dry_run:
        logger.info("[DRY RUN] Would upload NDJSON, delete Qdrant points, and re-embed",
                     document_id=document_id, chunk_count=len(chunks))
        return True

    # Step 2: Upload as NDJSON to S3
    _upload_as_ndjson(document_id, chunks)

    # Step 3: Delete old Qdrant points (forces re-embedding past the idempotency check)
    _delete_qdrant_points(document_id)

    # Step 4: Re-run embedding job (uses the new heading-aware logic)
    from backend.ingestion_worker.embedding_jobs import process_embedding_job
    result = process_embedding_job(document_id)
    logger.info("Re-embedding complete", document_id=document_id, result=result)
    return True


def main():
    parser = argparse.ArgumentParser(description="Re-embed documents with heading-aware embeddings")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without making changes")
    parser.add_argument("--document-id", type=str, help="Re-embed a single document by UUID")
    args = parser.parse_args()

    with SessionLocal() as db:
        repo = DocumentRepository(db)

        if args.document_id:
            doc_ids = [args.document_id]
        else:
            # Get all completed documents
            docs = repo.list_all()
            doc_ids = [str(d.id) for d in docs if d.status in (
                DocumentStatus.COMPLETED.value,
                DocumentStatus.EMBEDDED.value,
                "completed", "embedded",
            )]

    logger.info("Documents to process", count=len(doc_ids), dry_run=args.dry_run)

    success = 0
    failed = 0
    skipped = 0

    for doc_id in doc_ids:
        try:
            if reembed_document(doc_id, dry_run=args.dry_run):
                success += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error("Failed to re-embed document", document_id=doc_id, error=str(e), exc_info=True)
            failed += 1

    logger.info("Migration complete", success=success, failed=failed, skipped=skipped)


if __name__ == "__main__":
    main()
