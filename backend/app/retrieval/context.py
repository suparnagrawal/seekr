from typing import List, Optional
from openai import AsyncOpenAI
from backend.app.retrieval.models import TraversalContext, QueryType
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.db.queries import neo4j_resolve_entities, neo4j_resolve_entities_batch, get_redis_session_history
from backend.shared.config import settings
import asyncio
import structlog
import httpx

logger = structlog.get_logger(__name__)

from backend.shared.llm_clients import get_llm_client

def _get_p2_client() -> AsyncOpenAI:
    return get_llm_client(
        api_key=settings.fast_model_api_key,
        base_url=settings.LLM_BASE_URL
    )


async def _formulate_graph_strategy(query: str, history: List[str]) -> dict:
    history_str = "\n".join(history[-3:]) if history else "None"
    system_prompt = (
        "You are an expert Graph Query Planner for an industrial knowledge base. "
        "Analyze the user's query and the chat history to formulate a targeted graph search strategy.\n\n"
        "Return STRICT JSON only, no markdown fences, with this exact schema:\n"
        "{\n"
        '  "search_terms": ["list", "of", "clean", "specific", "entity", "names", "or", "tags", "from", "the", "query"],\n'
        '  "relationship_types": ["list", "of", "UPPERCASE_WITH_UNDERSCORES", "relationship", "types", "relevant", "to", "the", "query", "intent"]\n'
        "}\n\n"
        "Example relationship types: CONNECTED_TO, FEEDS_INTO, CONTROLS, PART_OF, DEPENDS_ON, ATTACHED_TO.\n"
        "Extract only the physical components or critical concepts as search terms. Strip out conversational filler."
    )
    
    try:
        client = _get_p2_client()
        response = await client.chat.completions.create(
            model=settings.FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"History:\n{history_str}\n\nQuery: {query}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=150
        )
        import json
        content = response.choices[0].message.content
        if content is None:
            return {"search_terms": [], "relationship_types": []}
        content = content.strip()
        data = json.loads(content)
        return {
            "search_terms": data.get("search_terms", []),
            "relationship_types": data.get("relationship_types", [])
        }
    except Exception as e:
        logger.warning("Graph strategy formulation failed", error=str(e))
        return {"search_terms": [], "relationship_types": []}


from backend.shared.query_classification import classify_query_heuristic

async def _classify_query_with_fallback(query: str) -> QueryType:
    result = classify_query_heuristic(query)
    if result is not None:
        return result
        
    # LLM fallback
    try:
        client = _get_p2_client()
        response = await client.chat.completions.create(
            model=settings.FAST_MODEL,
            messages=[
                {"role": "system", "content": "Classify the query as one of: factual, diagnostic, procedural, open. Return only the single word."},
                {"role": "user", "content": query}
            ],
            max_tokens=10
        )
        cat = response.choices[0].message.content.strip().lower()
        if cat in [e.value for e in QueryType]:
            return QueryType(cat)
    except Exception:
        pass
    
    return QueryType.OPEN


async def _embed_with_fallback(text: str, embedding_service=None) -> List[float]:
    fast_model_api_key = settings.fast_model_api_key
    if settings.EMBEDDING_MODEL_ENDPOINT:
        try:
            client = AsyncOpenAI(
                api_key=fast_model_api_key or "dummy",
                base_url=settings.EMBEDDING_MODEL_ENDPOINT,
                timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0),
                default_headers={"ngrok-skip-browser-warning": "1"}
            )
            response = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=[text])
            return response.data[0].embedding
        except Exception:
            logger.warning("Custom embedding endpoint failed; trying fallback")

    if fast_model_api_key and fast_model_api_key != "<replace_with_your_api_key>":
        try:
            client = AsyncOpenAI(api_key=fast_model_api_key, timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0))
            response = await client.embeddings.create(model="text-embedding-3-small", input=[text])
            return response.data[0].embedding
        except Exception:
            logger.warning("OpenAI embeddings failed; trying local embedding service")

    try:
        service = embedding_service
        if service is None:
            from backend.shared.services.embedding_service import get_embedding_service

            service = get_embedding_service()
        vectors = service.embed_batch([text])
        return vectors[0]
    except Exception as e:
        logger.error("all_embedding_backends_failed", query_text=text[:100], error=str(e))
        return [0.0] * settings.EMBEDDING_DIMENSION

class ContextAssembler:
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service

    async def assemble(self, query: SearchQuery) -> TraversalContext:
        history_texts = await self.get_recent_messages(query.session_id, limit=5)
        
        # 1. Formulate Pre-Traversal Strategy and Embed concurrently
        strategy_task = asyncio.create_task(_formulate_graph_strategy(query.text, history_texts))
        embedding_task = asyncio.create_task(self._get_embedding(query.text))
        strategy, query_embedding = await asyncio.gather(strategy_task, embedding_task)
        
        search_terms = strategy.get("search_terms") or [query.text]
        target_relationship_types = strategy.get("relationship_types") or []
        
        # 2. Resolve Entities using batch query
        explicit = set(await self.resolve_entities_batch(search_terms))
        history_tags = set(await self.resolve_entities_batch(history_texts))

        implicit = list(history_tags - set(explicit))
        if query.focused_tag and query.focused_tag not in explicit:
            implicit.insert(0, query.focused_tag)

        final_query_type = query.query_type
        if final_query_type == QueryType.OPEN:
            final_query_type = await self.classify_query(query.text)

        return TraversalContext(
            explicit_tags=list(explicit),
            implicit_tags=implicit[:5],
            query_type=final_query_type,
            query_embedding=query_embedding,
            target_relationship_types=target_relationship_types
        )

    async def resolve_entities(self, text: str) -> List[str]:
        return await neo4j_resolve_entities(text)
        
    async def resolve_entities_batch(self, texts: List[str]) -> List[str]:
        return await neo4j_resolve_entities_batch(texts)

    async def get_recent_messages(self, session_id: str, limit: int = 5) -> List[str]:
        return await get_redis_session_history(session_id, limit)

    async def classify_query(self, query: str) -> QueryType:
        return await _classify_query_with_fallback(query)

    async def _get_embedding(self, text: str) -> List[float]:
        return await _embed_with_fallback(text, self.embedding_service)


async def assemble_context(
    query: str,
    session_id: str,
    focused_tag: Optional[str] = None,
    query_type: Optional[QueryType] = None,
) -> TraversalContext:
    assembler = ContextAssembler()
    return await assembler.assemble(
        SearchQuery(
            text=query,
            session_id=session_id,
            focused_tag=focused_tag,
            query_type=query_type or QueryType.OPEN,
        )
    )