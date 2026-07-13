#!/usr/bin/env python
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union
import uvicorn
from fastembed import TextEmbedding

app = FastAPI(title="Local OpenAI-Compatible Embedding Server")

print("Loading BAAI/bge-base-en-v1.5 model into RAM...")
# Load the model globally so it stays warm in memory
embedding_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
print("Model loaded successfully!")

class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = "BAAI/bge-base-en-v1.5"

@app.post("/v1/embeddings")
async def create_embedding(request: EmbeddingRequest):
    # Standardize input to a list
    inputs = [request.input] if isinstance(request.input, str) else request.input
    
    # Generate embeddings using the local CPU model
    embeddings = list(embedding_model.embed(inputs))
    
    # Format the response to perfectly match the OpenAI API spec
    data = []
    for i, emb in enumerate(embeddings):
        data.append({
            "object": "embedding",
            "embedding": emb.tolist(),
            "index": i
        })
        
    return {
        "object": "list",
        "data": data,
        "model": request.model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0}
    }

if __name__ == "__main__":
    print("Starting local embedding server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
