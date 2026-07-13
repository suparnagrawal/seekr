from typing import List, Optional
from openai import AsyncOpenAI
from backend.app.retrieval.models import TraversalContext, QueryType
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.db.queries import pg_resolve_entities, get_redis_session_history
from backend.shared.config import settings
import structlog
import httpx

logger = structlog.get_logger(__name__)
# OpenAI-compatible client for the fast query classifier. Key, base URL, and
# model all come from the single central settings object so the P2 retrieval
# layer and the P3 agent layer target the exact same LLM endpoint.
openai_client = AsyncOpenAI(
    api_key=settings.fast_model_api_key or "dummy",
    max_retries=settings.LLM_MAX_RETRIES,
    timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0),
    default_headers={"ngrok-skip-browser-warning": "1"},
    **({"base_url": settings.LLM_BASE_URL} if settings.LLM_BASE_URL else {}),
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
        response = await openai_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"History:\n{history_str}\n\nQuery: {query}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=150
        )
        import json
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        return {
            "search_terms": data.get("search_terms", []),
            "relationship_types": data.get("relationship_types", [])
        }
    except Exception as e:
        logger.warning("Graph strategy formulation failed", error=str(e))
        return {"search_terms": [], "relationship_types": []}


async def _classify_query_with_fallback(query: str) -> QueryType:
    query_lower = query.lower()
    if any(m in query_lower for m in ["why", "keeps failing", "root cause"]):
        return QueryType.DIAGNOSTIC
    if any(m in query_lower for m in ["how do i", "steps to"]):
        return QueryType.PROCEDURAL
    if any(m in query_lower for m in ["which", "compatible", "compare"]):
        return QueryType.OPEN
    if any(m in query_lower for m in ["what", "when"]):
        return QueryType.FACTUAL
        
    # LLM fallback
    try:
        response = await openai_client.chat.completions.create(
            model=settings.LLM_MODEL,
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
            async with AsyncOpenAI(
                api_key=fast_model_api_key or "dummy",
                base_url=settings.EMBEDDING_MODEL_ENDPOINT,
                timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0),
                default_headers={"ngrok-skip-browser-warning": "1"}
            ) as client:
                response = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=[text])
                return response.data[0].embedding
        except Exception:
            logger.warning("Custom embedding endpoint failed; trying fallback")

    if fast_model_api_key and fast_model_api_key != "<replace_with_your_api_key>":
        try:
            async with AsyncOpenAI(api_key=fast_model_api_key, timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=60.0)) as client:
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
    except Exception:
        return [0.0] * settings.EMBEDDING_DIMENSION

class ContextAssembler:
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service

    async def assemble(self, query: SearchQuery) -> TraversalContext:
        history_texts = await self.get_recent_messages(query.session_id, limit=5)
        
        # 1. Formulate Pre-Traversal Strategy
        strategy = await _formulate_graph_strategy(query.text, history_texts)
        search_terms = strategy.get("search_terms") or [query.text]
        target_relationship_types = strategy.get("relationship_types") or []
        
        # 2. Resolve Entities using clean search terms instead of raw query
        explicit = set()
        for term in search_terms:
            resolved = await self.resolve_entities(term)
            explicit.update(resolved)
        explicit = list(explicit)

        history_tags = set()
        for msg in history_texts:
            history_tags.update(await self.resolve_entities(msg))

        implicit = list(history_tags - set(explicit))
        if query.focused_tag and query.focused_tag not in explicit:
            implicit.insert(0, query.focused_tag)

        final_query_type = query.query_type
        if final_query_type == QueryType.OPEN:
            final_query_type = await self.classify_query(query.text)

        return TraversalContext(
            explicit_tags=explicit,
            implicit_tags=implicit[:5],
            query_type=final_query_type,
            query_embedding=await self._get_embedding(query.text),
            target_relationship_types=target_relationship_types
        )

    async def resolve_entities(self, text: str) -> List[str]:
        return await pg_resolve_entities(text)

    async def get_recent_messages(self, session_id: str, limit: int = 5) -> List[str]:
        return await get_redis_session_history(session_id, limit)

    async def classify_query(self, query: str) -> QueryType:
        return await _classify_query_with_fallback(query)

    async def _get_embedding(self, text: str) -> List[float]:
        return await _embed_with_fallback(text, self.embedding_service)


async def resolve_entities(text: str) -> List[str]:
    return await pg_resolve_entities(text)


async def get_recent_messages(session_id: str, limit: int = 5) -> List[str]:
    return await get_redis_session_history(session_id, limit)


async def classify_query(query: str) -> QueryType:
    return await _classify_query_with_fallback(query)


async def embed(text: str) -> List[float]:
    return await _embed_with_fallback(text)


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