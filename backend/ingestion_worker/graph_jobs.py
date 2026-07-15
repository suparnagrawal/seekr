"""
P1 knowledge-graph extraction job.

Reads a document's chunk artifacts, asks the configured LLM to extract entities
and relationships, and writes them into Neo4j as `(:Entity {tag, name, type})`
nodes with sanitized, dynamic relationship types. This is the stage that
populates the graph consumed by the `/api/v1/graph` endpoint, the graph
explorer, and the P2 graph-retrieval pathway.

Design (Rev. 4 rework):
  * Open-domain extraction: node/relationship types are LLM-derived, not
    allow-listed, so the graph adapts to any document domain. Because those
    strings are interpolated into Cypher labels, `_norm_node_type` /
    `_norm_rel_type` now hard-restrict them to a safe character class
    (`[a-z0-9_]` / `[A-Z0-9_]`), which is the invariant that makes the
    interpolation safe now that the old allow-list is gone.
  * Whole-document coverage: instead of truncating to the first N chunks and
    issuing one LLM call, the document is split into fixed-size *windows*, each
    extracted independently (bounded concurrency), and the per-window results
    are merged and canonicalized before a single batched write.
  * Provenance: every relationship is written with `source_doc_id` and a
    deterministic `fact_id` so graph-derived citations resolve to a real
    document instead of "unknown".

Runs in parallel with the embedding job (both fan out from parsing) and
participates in the document status state machine on every exit path.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import uuid
from collections import defaultdict

from typing import Any, Dict, List, Tuple

import structlog

from backend.shared.config import settings
from backend.shared.storage import storage_manager
from backend.shared.neo4j_client import neo4j_driver
from backend.app.agents.shared.llm import generate
from backend.shared.database import SessionLocal
from backend.shared.repositories.document_repository import DocumentRepository
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)

# We allow dynamic extraction of entities and relationships to support any domain.
DEFAULT_NODE_TYPE = "entity"
DEFAULT_REL_TYPE = "RELATED_TO"

# Character classes permitted in Cypher-interpolated type labels. Everything
# outside these is stripped. This is the safety invariant that replaces the
# removed ALLOWED_NODE_TYPES / ALLOWED_REL_TYPES allow-lists: even a fully
# LLM-controlled (or prompt-injected) type string cannot contain a backtick or
# any other character able to break out of the label context.
_NODE_TYPE_ALLOWED = re.compile(r"[^a-z0-9_]+")
_REL_TYPE_ALLOWED = re.compile(r"[^A-Z0-9_]+")

_EXTRACTION_SYSTEM_PROMPT = (
    "You are an intelligent knowledge graph extraction engine. Read the following text "
    "and extract the key entities and the relationships between them. Adapt the entity "
    "and relationship types to perfectly match the domain of the document (e.g., software, "
    "medical, industrial, financial).\n\n"
    "Return STRICT JSON only, no prose, no markdown fences, with this shape:\n"
    "{\n"
    '  "entities": [{"tag": "Unique_ID_1", "name": "Readable Name", "type": "concept", "description": "A detailed summary of what this entity is, its properties, or its role."}],\n'
    '  "relationships": [{"source": "Unique_ID_1", "target": "Unique_ID_2", '
    '"type": "DEPENDS_ON", "confidence": 0.9, "description": "A detailed explanation of why these two entities are connected and the nature of their relationship."}]\n'
    "}\n\n"
    "`type` for entities should be a lowercase generic category (e.g., 'algorithm', 'component', 'person').\n"
    "`type` for relationships must be UPPERCASE_WITH_UNDERSCORES (e.g., 'USES', 'PART_OF').\n"
    "`tag` is a short canonical identifier (e.g. an acronym, a slug, or exact name). Reuse the exact same tag for an entity everywhere it appears. "
    "`description` MUST be highly detailed and semantic to provide rich context to downstream reasoning agents.\n"
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
    """Normalize an entity type to a safe, lowercase, snake_case label.

    Restricts the result to ``[a-z0-9_]`` so the value is safe to interpolate
    into a Cypher label regardless of what the extraction LLM produced.
    """
    t = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    t = _NODE_TYPE_ALLOWED.sub("", t).strip("_")
    return t if t else DEFAULT_NODE_TYPE


def _norm_rel_type(value: Any) -> str:
    """Normalize a relationship type to a safe UPPER_SNAKE_CASE label.

    Restricts the result to ``[A-Z0-9_]``; anything else (crucially backticks)
    is stripped, closing the Cypher relationship-type injection vector opened
    when the ALLOWED_REL_TYPES allow-list was removed for open-domain support.
    """
    r = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    r = _REL_TYPE_ALLOWED.sub("", r).strip("_")
    return r if r else DEFAULT_REL_TYPE


def _canonical_tag(value: Any) -> str:
    """Normalized key used to detect that two extracted tags are the same entity."""
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _fact_id(document_id: str, source: str, rel_type: str, target: str) -> str:
    """Deterministic id for a relationship so re-extraction is idempotent and
    citations have a stable handle."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}|{source}|{rel_type}|{target}"))


def _window(items: List[str], size: int) -> List[List[str]]:
    size = max(1, size)
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _extract_window(chunk_texts: List[str], ml_gateway_url: str | None = None) -> Dict[str, List[Dict[str, Any]]]:
    joined = "\n\n---\n\n".join(chunk_texts)
    messages = [
        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": joined},
    ]
    logger.info("graph_extraction_window_llm_call", prompt_length=len(joined), chunks=len(chunk_texts))
    
    target_base_url = None
    if ml_gateway_url:
        target_base_url = ml_gateway_url.rstrip('/') + '/v1'
        
    raw = await generate(
        messages,
        temperature=0.0,
        max_tokens=settings.LLM_MAX_TOKENS,
        response_format={"type": "json_object"},
        base_url_override=target_base_url
    )
    return _parse_extraction(raw)


async def _extract(chunk_texts: List[str], ml_gateway_url: str | None = None) -> Dict[str, List[Dict[str, Any]]]:
    """Extract entities/relationships over the whole document via windowed,
    bounded-concurrency LLM calls, then merge the per-window results.

    A single window failing is tolerated: its exception is logged and it
    contributes nothing, rather than failing the whole document.
    """
    windows = _window(chunk_texts, settings.GRAPH_EXTRACTION_WINDOW)
    semaphore = asyncio.Semaphore(max(1, settings.GRAPH_EXTRACTION_CONCURRENCY))

    async def _guarded(win: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        async with semaphore:
            try:
                return await _extract_window(win, ml_gateway_url)
            except Exception as exc:  # noqa: BLE001 - per-window fail-soft
                logger.warning("graph_extraction_window_failed", error=str(exc), exc_info=True)
                return {"entities": [], "relationships": []}

    results = await asyncio.gather(*[_guarded(w) for w in windows])
    return _merge_extractions(results)


def _merge_extractions(
    parts: List[Dict[str, List[Dict[str, Any]]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Canonicalize and de-duplicate entities/relationships across windows.

    Entities are keyed by canonical tag; the richest (longest) description and a
    concrete name/type win. Relationships are keyed by
    (canonical source, rel type, canonical target); the highest confidence and
    richest description win.
    """
    entities: Dict[str, Dict[str, Any]] = {}
    tag_alias: Dict[str, str] = {}  # canonical -> chosen display tag

    for part in parts:
        for ent in part.get("entities", []):
            raw_tag = str(ent.get("tag") or "").strip()
            if not raw_tag:
                continue
            key = _canonical_tag(raw_tag)
            desc = str(ent.get("description") or "")
            name = str(ent.get("name") or raw_tag)
            etype = _norm_node_type(ent.get("type"))

            if key not in entities:
                tag_alias[key] = raw_tag
                entities[key] = {"tag": raw_tag, "name": name, "type": etype, "description": desc}
                continue

            existing = entities[key]
            if len(desc) > len(existing["description"]):
                existing["description"] = desc
            # Prefer a non-default type if we only had the generic fallback.
            if existing["type"] == DEFAULT_NODE_TYPE and etype != DEFAULT_NODE_TYPE:
                existing["type"] = etype
            # Prefer a name that differs from the bare tag.
            if existing["name"] == existing["tag"] and name != raw_tag:
                existing["name"] = name

    valid_keys = set(entities.keys())
    relationships: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for part in parts:
        for rel in part.get("relationships", []):
            src_key = _canonical_tag(rel.get("source"))
            tgt_key = _canonical_tag(rel.get("target"))
            if not src_key or not tgt_key or src_key not in valid_keys or tgt_key not in valid_keys:
                continue
            rel_type = _norm_rel_type(rel.get("type"))
            try:
                confidence = float(rel.get("confidence", 0.8))
            except (TypeError, ValueError):
                confidence = 0.8
            desc = str(rel.get("description") or "")
            src_tag = tag_alias[src_key]
            tgt_tag = tag_alias[tgt_key]
            rkey = (src_key, rel_type, tgt_key)

            if rkey not in relationships:
                relationships[rkey] = {
                    "source": src_tag,
                    "target": tgt_tag,
                    "type": rel_type,
                    "confidence": confidence,
                    "description": desc,
                }
            else:
                existing = relationships[rkey]
                existing["confidence"] = max(existing["confidence"], confidence)
                if len(desc) > len(existing["description"]):
                    existing["description"] = desc

    return {
        "entities": list(entities.values()),
        "relationships": list(relationships.values()),
    }


def _write_graph(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    document_id: str,
) -> int:
    """Write validated entities/relationships to Neo4j. Returns nodes written.

    Relationships are grouped by (already-sanitized) type so each Cypher label
    is a fixed, safe literal per batch. Every relationship carries provenance
    (`source_doc_id`, deterministic `fact_id`) so downstream citations resolve.
    """
    valid_tags: set[str] = set()

    valid_nodes = []
    for ent in entities:
        tag = str(ent.get("tag") or "").strip()
        if not tag:
            continue
        valid_nodes.append(
            {
                "tag": tag,
                "name": str(ent.get("name") or tag),
                "type": _norm_node_type(ent.get("type")),
                "description": str(ent.get("description") or ""),
            }
        )
        valid_tags.add(tag)

    if not valid_nodes:
        return 0

    # Group relationships by sanitized type so the interpolated label is a fixed
    # literal per batch (never attacker-influenced beyond the [A-Z0-9_] class).
    rels_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
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
        rels_by_type[rel_type].append(
            {
                "source": src,
                "target": tgt,
                "confidence": confidence,
                "description": str(rel.get("description") or ""),
                "fact_id": _fact_id(document_id, src, rel_type, tgt),
                "source_doc_id": document_id,
            }
        )

    with neo4j_driver.session() as session:
        batch_size = 100
        for i in range(0, len(valid_nodes), batch_size):
            node_batch = valid_nodes[i : i + batch_size]
            session.run(
                """
                UNWIND $nodes AS node
                MERGE (n:Entity {tag: node.tag})
                SET n.name = node.name,
                    n.type = node.type,
                    n.model_name = $model,
                    // Keep the richest description seen across documents/windows.
                    n.description = CASE
                        WHEN size(coalesce(n.description, '')) >= size(coalesce(node.description, ''))
                        THEN coalesce(n.description, '')
                        ELSE node.description
                    END
                """,
                nodes=node_batch,
                model=settings.LLM_MODEL,
            )

        for r_type, r_list in rels_by_type.items():
            # r_type is guaranteed to match [A-Z0-9_]+ by _norm_rel_type.
            for i in range(0, len(r_list), batch_size):
                rel_batch = r_list[i : i + batch_size]
                session.run(
                    f"""
                    UNWIND $rels AS rel
                    MATCH (a:Entity {{tag: rel.source}}), (b:Entity {{tag: rel.target}})
                    MERGE (a)-[r:`{r_type}`]->(b)
                    SET r.confidence = rel.confidence,
                        r.description = rel.description,
                        r.fact_id = rel.fact_id,
                        r.source_doc_id = rel.source_doc_id,
                        r.model_name = $model
                    """,
                    rels=rel_batch,
                    model=settings.LLM_MODEL,
                )

    return len(valid_nodes)


def _load_chunk_texts(document_id: str) -> List[str]:
    """Read chunk texts from the document's NDJSON artifact, honoring an optional cap."""
    artifact_uri = storage_manager.get_artifact_uri(document_id, "chunks.jsonl")
    try:
        temp_chunks_path = storage_manager.download_to_tempfile(artifact_uri)
    except Exception as e:
        logger.error("Failed to download chunks.jsonl for graph extraction", error=str(e))
        return []
        
    chunks_path = Path(temp_chunks_path)
    if not chunks_path.exists():
        return []
        
    cap = settings.GRAPH_EXTRACTION_MAX_CHUNKS
    texts: List[str] = []
    
    try:
        with chunks_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                c = json.loads(line)
                if c.get("text"):
                    texts.append(c["text"])
                if cap and cap > 0 and len(texts) >= cap:
                    break
    finally:
        if chunks_path.exists():
            os.remove(chunks_path)
            
    return texts


def process_graph_job(document_id: str, ml_gateway_url: str | None = None) -> Dict[str, Any]:
    """
    RQ entrypoint for P1 knowledge-graph extraction.

    Reads chunks.jsonl, extracts entities/relationships with the configured LLM
    over the whole document (windowed), and writes them to Neo4j. Participates
    in the document status state machine on every exit path.
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
        texts = _load_chunk_texts(document_id)
        if not texts:
            logger.warning("no_chunks_for_graph_extraction", document_id=document_id)
            with SessionLocal() as db:
                repo = DocumentRepository(db)
                repo.mark_graph_skipped(document_id)
                repo.db.commit()
            return {"status": "skipped", "reason": "no chunks", "document_id": document_id}

        _bootstrap_constraint()
        extraction = asyncio.run(_extract(texts, ml_gateway_url))
        nodes_written = _write_graph(
            extraction["entities"], extraction["relationships"], document_id
        )

        with SessionLocal() as db:
            repo = DocumentRepository(db)
            repo.mark_graph_built(document_id, datetime.now(timezone.utc))
            repo.db.commit()

        logger.info(
            "Graph extraction completed",
            document_id=document_id,
            chunks_used=len(texts),
            windows=len(_window(texts, settings.GRAPH_EXTRACTION_WINDOW)),
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
        logger.error("Graph extraction failed", document_id=document_id, error=str(exc), exc_info=True)
        with SessionLocal() as db:
            repo = DocumentRepository(db)
            repo.mark_graph_failed(document_id)
            repo.db.commit()

        # Re-raise so RQ registers the job as failed and the DLQ Auto-Recovery
        # Daemon can requeue it when the ML Gateway comes back online.
        from backend.shared.exceptions import IngestionPipelineError

        raise IngestionPipelineError(
            f"Graph Extraction failed: {str(exc)}", stage="Graph Extraction"
        ) from exc
