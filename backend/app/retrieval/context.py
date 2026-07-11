from typing import List, Optional
import os
from openai import AsyncOpenAI
from backend.app.retrieval.models import TraversalContext, QueryType
from backend.app.retrieval.interfaces import SearchQuery
from backend.app.db.queries import pg_facts
import structlog

logger = structlog.get_logger(__name__)

FAST_MODEL_API_KEY = os.getenv("FAST_MODEL_API_KEY", "")
EMBEDDING_MODEL_ENDPOINT = os.getenv("EMBEDDING_MODEL_ENDPOINT", "http://localhost:11434/v1")

# We use the standard OpenAI client since it can point to any compliant endpoint
openai_client = AsyncOpenAI(api_key=FAST_MODEL_API_KEY or "dummy")
embed_client = AsyncOpenAI(api_key="dummy", base_url=EMBEDDING_MODEL_ENDPOINT)

class ContextAssembler:
    def __init__(self, embedding_service=None):
        self.embedding_service = embedding_service

    async def assemble(
        self, query: SearchQuery
    ) -> TraversalContext:
        explicit = await self.resolve_entities(query.text)
        
        history_texts = await self.get_recent_messages(query.session_id, limit=5)
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
            implicit_tags=implicit[:5],  # Cap to prevent context explosion
            query_type=final_query_type,
            query_embedding=await self._get_embedding(query.text)
        )

    async def resolve_entities(self, text: str) -> List[str]:
        # Very naive mock of entity resolution.
        # In a real system, we would use an NER model or fuzzy match against entity_registry
        tags = []
        if "P-101A" in text:
            tags.append("P-101A")
        if "P-101B" in text:
            tags.append("P-101B")
        return tags

    async def get_recent_messages(self, session_id: str, limit: int = 5) -> List[str]:
        # Mocking chat history fetch from DB for now
        return []

    async def classify_query(self, query: str) -> QueryType:
        query_lower = query.lower()
        # Simple regex pre-filter as per architecture doc
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
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Classify the query as one of: factual, diagnostic, procedural, open. Return only the single word."},
                    {"role": "user", "content": query}
                ],
                max_tokens=10
            )
            cat = response.choices[0].message.content.strip().lower()
            if cat in [e.value for e in QueryType]:
                return QueryType(cat)
        except Exception as e:
            logger.warning("LLM query classification failed, defaulting to OPEN.", error=str(e))
        
        return QueryType.OPEN

    async def _get_embedding(self, text: str) -> List[float]:
        try:
            if self.embedding_service:
                vectors = self.embedding_service.embed_batch([text])
                return vectors[0]
        except Exception as e:
            logger.error("Embedding failed, falling back to zeroes.", error=str(e))
        from backend.shared.config import settings
        return [0.0] * settings.EMBEDDING_DIMENSION  # Fallback for local dev

