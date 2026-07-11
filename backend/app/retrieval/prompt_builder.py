from typing import List
from backend.app.retrieval.models import Chunk

class CitedAnswer:
    def __init__(self, answer: str, citations: List[str]):
        self.answer = answer
        self.citations = citations

class PromptBuilder:
    def build_prompt(self, query: str, chunks: List[Chunk], strict: bool = False) -> str:
        # Mock prompt construction
        return "mock prompt"

    def citations_resolve(self, draft: str, chunks: List[Chunk]) -> bool:
        # Mock regex check for [doc_id:passage_id] tags
        return True

    def self_check(self, draft: str, chunks: List[Chunk]) -> CitedAnswer:
        return CitedAnswer(draft, ["d-91:p-4"])

    async def generate_answer(self, query: str, chunks: List[Chunk]) -> CitedAnswer:
        # Mock LLM generation
        draft = "Pump P-101A has experienced a bearing failure. [d-91:p-4]"
        
        if not self.citations_resolve(draft, chunks):
            # Retry with strict citation instruction
            draft = "Strict: Pump P-101A has experienced a bearing failure. [d-91:p-4]"
            
        return self.self_check(draft, chunks)
