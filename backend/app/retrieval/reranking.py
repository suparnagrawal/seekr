from typing import List
import re

from backend.app.retrieval.interfaces import SearchQuery, TraversalContext
from backend.app.retrieval.models import Chunk

class MetadataReranker:
    """
    Lightweight metadata-aware reranker that operates on a fused list of chunks.
    Applies small additive bonuses to the RRF score based on structural metadata
    (filename, headings, explicit definitions) to gently nudge primary sources
    above secondary references.
    """
    
    # RRF scores are typically 0.01 - 0.05.
    # We use very small bonuses to avoid completely overriding semantic quality.
    # Maximum cumulative bonus to prevent metadata from completely overpowering RRF
    MAX_METADATA_BONUS = 0.008
    FILENAME_BONUS = 0.005
    HEADING_BONUS = 0.003
    EXACT_ENTITY_BONUS = 0.002

    def _normalize(self, text: str, is_filename: bool = False) -> str:
        """Strip non-alphanumeric characters and lowercase for robust matching."""
        if not text:
            return ""
        # Remove extension if it's a filename
        if is_filename:
            text = text.rsplit('.', 1)[0]
        return re.sub(r'[^a-z0-9]', '', text.lower())

    def rerank(self, chunks: List[Chunk], query: SearchQuery, context: TraversalContext) -> List[Chunk]:
        import structlog
        logger = structlog.get_logger(__name__)
        
        logger.info("explicit_tags", tags=context.explicit_tags)
        
        if not chunks:
            return chunks

        normalized_entities = [self._normalize(tag) for tag in context.explicit_tags if tag]
        
        # Fallback to query keywords if no explicit tags exist.
        # This acts as insurance if the LLM strategy formulation fails or Neo4j lacks exact matches.
        if not normalized_entities:
            # Extract meaningful words from query (length > 3) to use as lightweight token extraction
            words = re.findall(r'\b[a-zA-Z0-9]{4,}\b', query.text.lower())
            # Basic stopword filter
            stopwords = {"what", "when", "where", "which", "how", "this", "that", "there", "then"}
            normalized_entities = [w for w in words if w not in stopwords]
            logger.info("using_query_fallback", fallback_entities=normalized_entities)
            
        if not normalized_entities:
            return chunks

        total_bonus_applied = 0.0
        chunks_boosted = 0

        for chunk in chunks:
            original_score = chunk.score
            bonus = 0.0
            payload = chunk.payload
            
            filename = payload.get("filename", "")
            norm_filename = self._normalize(filename, is_filename=True)
            
            headings = payload.get("headings", [])
            norm_headings = [self._normalize(h) for h in headings]
            
            chunk_text = chunk.text.lower()
            
            for entity in normalized_entities:
                if not entity:
                    continue
                
                # 1. Filename Bonus
                if norm_filename and (entity in norm_filename or norm_filename in entity):
                    bonus += self.FILENAME_BONUS
                
                # 2. Heading Bonus
                for norm_h in norm_headings:
                    if entity in norm_h:
                        bonus += self.HEADING_BONUS
                        break  # Only apply once per entity
                        
                # 3. Exact Entity Bonus (Definition heuristic)
                # Check if the text explicitly starts with or defines the entity
                raw_entity = next((tag for tag in context.explicit_tags if self._normalize(tag) == entity), entity).lower()
                if raw_entity in chunk_text:
                    if chunk_text.startswith(raw_entity) or f"{raw_entity} is" in chunk_text or f"{raw_entity} defines" in chunk_text:
                        bonus += self.EXACT_ENTITY_BONUS

            # Apply capped bonus to nudge ranking safely
            if bonus > 0:
                capped_bonus = min(bonus, self.MAX_METADATA_BONUS)
                chunk.score += capped_bonus
                total_bonus_applied += capped_bonus
                chunks_boosted += 1

            logger.debug(
                "metadata_rerank_chunk",
                filename=chunk.payload.get("filename"),
                original_score=original_score,
                bonus=bonus,
                capped_bonus=min(bonus, self.MAX_METADATA_BONUS) if bonus > 0 else 0.0,
                final_score=chunk.score,
            )

        if chunks_boosted > 0:
            logger.info("metadata_rerank_summary", chunks_boosted=chunks_boosted, total_bonus=total_bonus_applied)

        # Re-sort descending by the new boosted score
        chunks.sort(key=lambda x: -x.score)
        return chunks
