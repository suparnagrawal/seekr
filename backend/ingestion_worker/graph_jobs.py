"""
P1 knowledge-graph extraction job.

Reads a document's chunk artifacts, asks the configured LLM to extract entities
and relationships, and writes them into Neo4j as `(:Entity {tag, name, type})`
nodes with allow-listed relationship types. This is the stage that populates the
graph consumed by the `/api/v1/graph` endpoint, the graph explorer, and the P2
graph-retrieval pathway.

Runs in parallel with the embedding job (both fan out from parsing) and is
status-neutral: it never mutates the document's lifecycle status, so it cannot
race the embedding job's transition to COMPLETED.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import structlog

from backend.shared.config import settings
from backend.shared.storage import storage_manager
from backend.shared.neo4j_client import neo4j_driver
from backend.app.agents.shared.llm import generate
from backend.shared.database import SessionLocal
from backend.shared.repositories.document_repository import DocumentRepository
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)

# Allow-lists constrain what the LLM can write into the graph schema, preventing
# hallucinated labels/relationship types from polluting Neo4j.
ALLOWED_NODE_TYPES = {
    "equipment", "document", "procedure", "system", "component", "failure_mode",
}
DEFAULT_NODE_TYPE = "component"

ALLOWED_REL_TYPES = {
    "PART_OF", "CONNECTED_TO", "FEEDS", "CONTAINS", "DOCUMENTED_BY",
    "MAINTAINED_BY", "SUSCEPTIBLE_TO", "CAUSES", "REDUNDANT_WITH",
    "REFERENCES", "APPLIES_TO", "SUPPLIES", "RELATED_TO",
}
DEFAULT_REL_TYPE = "RELATED_TO"

_EXTRACTION_SYSTEM_PROMPT = (
    "You are an information-extraction engine for industrial equipment "
    "documentation (manuals, maintenance records, P&IDs). Extract the entities "
    "and relationships described in the text.\n\n"
    "Return STRICT JSON only, no prose, no markdown fences, with this shape:\n"
    "{\n"
    '  "entities": [{"tag": "P-101A", "name": "Centrifugal Pump P-101A", '
    '"type": "equipment"}],\n'
    '  "relationships": [{"source": "P-101A", "target": "V-201", '
    '"type": "FEEDS", "confidence": 0.9}]\n'
    "}\n\n"
    f"`type` for entities MUST be one of: {sorted(ALLOWED_NODE_TYPES)}.\n"
    f"`type` for relationships SHOULD be one of: {sorted(ALLOWED_REL_TYPES)}.\n"
    "`tag` is a short canonical identifier (e.g. an equipment tag like 'P-101A' "
    "or a slug). Reuse the exact same tag for an entity everywhere it appears. "
    "confidence is a float in [0,1]. If nothing is extractable, return empty lists."
)


def _bootstrap_constraint() -> None:
    """Idempotently ensure Entity.tag uniqueness so MERGE is correct and fast."""
    try:
        with neo4j_driver.session() as session:
            session.run(
                "CREATE CONSTRAINT entity_tag_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.tag IS UNIQUE"
            )
    except Exception as exc:  # non-fatal: MERGE still works without the constraint
        logger.warning("neo4j_constraint_bootstrap_failed", error=str(exc))


def _parse_extraction(raw: str) -> Dict[str, List[Dict[str, Any]]]:
    """Defensively parse the LLM's JSON response (tolerating code fences)."""
    text = raw.strip()
    # Strip ```json ... ``` fences if the model added them despite instructions.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Last resort: grab the outermost JSON object.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            logger.warning(
                "graph_extraction_parse_failed_no_json",
                response_length=len(raw),
                first_500=raw[:500],
                last_500=raw[-500:] if len(raw) > 500 else "",
            )
            return {"entities": [], "relationships": []}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.warning(
                "graph_extraction_parse_failed_decode_error",
                response_length=len(raw),
                first_500=raw[:500],
                last_500=raw[-500:] if len(raw) > 500 else "",
            )
            return {"entities": [], "relationships": []}
    return {
        "entities": data.get("entities", []) or [],
        "relationships": data.get("relationships", []) or [],
    }


def _norm_node_type(value: Any) -> str:
    t = str(value or "").strip().lower().replace(" ", "_")
    return t if t in ALLOWED_NODE_TYPES else DEFAULT_NODE_TYPE


def _norm_rel_type(value: Any) -> str:
    r = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    return r if r in ALLOWED_REL_TYPES else DEFAULT_REL_TYPE


async def _extract(chunk_texts: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    joined = "\n\n---\n\n".join(chunk_texts)
    messages = [
        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": joined},
    ]
    raw = await generate(
        messages, 
        temperature=0.0, 
        max_tokens=settings.LLM_MAX_TOKENS,
        response_format={"type": "json_object"}
    )
    return _parse_extraction(raw)


def _write_graph(entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> int:
    """Write validated entities/relationships to Neo4j. Returns nodes written."""
    valid_tags: set[str] = set()
    written = 0

    with neo4j_driver.session() as session:
        for ent in entities:
            tag = str(ent.get("tag") or "").strip()
            if not tag:
                continue
            session.run(
                "MERGE (n:Entity {tag: $tag}) "
                "SET n.name = $name, n.type = $type, n.model_name = $model",
                tag=tag,
                name=str(ent.get("name") or tag),
                type=_norm_node_type(ent.get("type")),
                model=settings.LLM_MODEL,
            )
            valid_tags.add(tag)
            written += 1

        for rel in relationships:
            src = str(rel.get("source") or "").strip()
            tgt = str(rel.get("target") or "").strip()
            if not src or not tgt or src not in valid_tags or tgt not in valid_tags:
                continue
            rel_type = _norm_rel_type(rel.get("type"))
            try:
                confidence = float(rel.get("confidence", 0.8))
            except (TypeError, ValueError):
                confidence = 0.8
            # rel_type is drawn from ALLOWED_REL_TYPES, so this interpolation is safe.
            session.run(
                f"MATCH (a:Entity {{tag: $src}}), (b:Entity {{tag: $tgt}}) "
                f"MERGE (a)-[r:`{rel_type}`]->(b) "
                f"SET r.confidence = $confidence, r.model_name = $model",
                src=src,
                tgt=tgt,
                confidence=confidence,
                model=settings.LLM_MODEL,
            )

    return written


def process_graph_job(document_id: str) -> Dict[str, Any]:
    """
    RQ entrypoint for P1 knowledge-graph extraction.

    Reads chunks.json, extracts entities/relationships with the configured LLM,
    and writes them to Neo4j. Status-neutral and best-effort: extraction failure
    is logged and does not fail the overall ingestion (embedding owns COMPLETED).
    """
    if not settings.GRAPH_EXTRACTION_ENABLED:
        logger.info("graph_extraction_disabled", document_id=document_id)
        with SessionLocal() as db:
            repo = DocumentRepository(db)
            repo.mark_graph_skipped(document_id)
            repo.db.commit()
        return {"status": "skipped", "document_id": document_id}

    logger.info("Starting graph extraction job", document_id=document_id)

    try:
        chunks_path = Path(storage_manager.get_document_dir(document_id)) / "chunks.json"
        if not chunks_path.exists():
            logger.warning("chunks.json missing for graph extraction", document_id=document_id)
            with SessionLocal() as db:
                repo = DocumentRepository(db)
                repo.mark_graph_skipped(document_id)
                repo.db.commit()
            return {"status": "skipped", "reason": "no chunks", "document_id": document_id}

        with chunks_path.open("r", encoding="utf-8") as f:
            chunks = json.load(f)

        texts = [c["text"] for c in chunks[: settings.GRAPH_EXTRACTION_MAX_CHUNKS] if c.get("text")]
        if not texts:
            with SessionLocal() as db:
                repo = DocumentRepository(db)
                repo.mark_graph_skipped(document_id)
                repo.db.commit()
            return {"status": "success", "nodes": 0, "document_id": document_id}

        _bootstrap_constraint()
        extraction = asyncio.run(_extract(texts))
        nodes_written = _write_graph(extraction["entities"], extraction["relationships"])

        # Ensure we mark the graph as built to unblock convergence
        with SessionLocal() as db:
            repo = DocumentRepository(db)
            repo.mark_graph_built(document_id, datetime.now(timezone.utc))
            repo.db.commit()

        logger.info(
            "Graph extraction completed",
            document_id=document_id,
            chunks_used=len(texts),
            entities=len(extraction["entities"]),
            relationships=len(extraction["relationships"]),
            nodes_written=nodes_written,
        )
        return {
            "status": "success",
            "document_id": document_id,
            "nodes": nodes_written,
            "relationships": len(extraction["relationships"]),
        }

    except Exception as exc:
        # Best-effort: a graph-extraction failure must not fail ingestion overall.
        # We record the FAILED state so convergence logic doesn't stall,
        # but the document might still transition to FAILED overall based on convergence logic.
        logger.error("Graph extraction failed", document_id=document_id, error=str(exc), exc_info=True)
        with SessionLocal() as db:
            repo = DocumentRepository(db)
            repo.mark_graph_failed(document_id)
            repo.db.commit()
        return {"status": "failed", "document_id": document_id, "error": str(exc)}
