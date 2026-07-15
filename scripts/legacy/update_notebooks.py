import json
import os

new_gateway_code = """%%writefile seekr_ml_gateway.py
import uvicorn
import httpx
import os
import sys
import unicodedata
import re
import hashlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pyngrok import ngrok
from fastembed import TextEmbedding
from docling.document_converter import DocumentConverter
from docling.chunking import HierarchicalChunker

# Force unbuffered output for prints in this script
sys.stdout.reconfigure(line_buffering=True)

# Lazy-loaded models
embedding_model = None
doc_converter = None
chunker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_model, doc_converter, chunker
    print("Loading FastEmbed...")
    embedding_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5", threads=4)
    print("Loading Docling...")
    doc_converter = DocumentConverter()
    print("Loading Hierarchical Chunker...")
    chunker = HierarchicalChunker()
    print("Unified Gateway Ready!")

    # Launch Ngrok Tunnel
    ngrok_token = os.getenv("NGROK_AUTH_TOKEN")
    ngrok_domain = os.getenv("NGROK_STATIC_DOMAIN")
    if ngrok_token and ngrok_domain:
        ngrok.set_auth_token(ngrok_token)
        # Clean the domain of https:// and trailing slashes to prevent PyngrokNgrokHTTPError 9038
        clean_domain = ngrok_domain.replace("https://", "").replace("http://", "").strip("/")
        public_url = ngrok.connect(8000, domain=clean_domain).public_url
        print("\\n" + "="*60)
        print("\\033[92mSEEKR ML GATEWAY IS LIVE!\\033[0m")
        print("="*60)
        print(f"Add these variables to your Render .env file:")
        print(f"LLM_BASE_URL={public_url}/v1")
        print(f"FAST_MODEL_BASE_URL={public_url}/v1")
        print(f"EMBEDDING_MODEL_ENDPOINT={public_url}/v1")
        print(f"REMOTE_PARSER_URL={public_url}/parse")
        print("="*60 + "\\n")
    else:
        print("WARNING: Ngrok Token or Domain not provided. Running locally only.")
    yield

app = FastAPI(title="Seekr Unified ML Gateway", lifespan=lifespan)

# --- ROUTE 1: Docling Parsing & Chunking ---
@app.post("/parse")
async def parse_document(file: UploadFile = File(...)):
    print(f"[Docling] Parsing document: {file.filename}")
    file_bytes = await file.read()
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(file_bytes)
        
    result = doc_converter.convert(temp_path)
    
    print(f"[Docling] Chunking document: {file.filename}")
    chunks_iter = chunker.chunk(result.document)
    
    artifact_chunks = []
    for index, chunk in enumerate(chunks_iter):
        chunk_text = chunk.text
        chunk_meta = chunk.meta.export_json_dict() if chunk.meta else {}
        
        headings = chunk_meta.get("headings", [])
        heading_path = "/".join(headings) if headings else "root"
        
        page_numbers = []
        for item in chunk_meta.get("doc_items", []):
            for prov in item.get("prov", []):
                if "page_no" in prov:
                    page_numbers.append(str(prov["page_no"]))
        page_str = ",".join(sorted(set(page_numbers))) if page_numbers else "0"
        
        normalized_text = unicodedata.normalize("NFKC", chunk_text.strip())
        normalized_text = re.sub(r'\\s+', ' ', normalized_text)
        
        artifact_chunks.append({
            "text": chunk_text,
            "headings": headings,
            "page_numbers": [int(p) for p in page_numbers] if page_numbers else [],
            "bbox": None,
            "chunk_index": index,
            "token_count": len(chunk_text.split()),
            "normalized_text": normalized_text,
            "heading_path": heading_path,
            "page_str": page_str
        })
    
    print(f"[Docling] Successfully processed {len(artifact_chunks)} chunks for {file.filename}")
    
    return {
        "markdown": result.document.export_to_markdown(),
        "metadata": {
            "origin": file.filename,
            "page_count": len(result.document.pages)
        },
        "page_count": len(result.document.pages),
        "chunks": artifact_chunks
    }

# --- ROUTE 2: FastEmbed Embeddings (OpenAI Compatible) ---
@app.post("/v1/embeddings")
async def create_embeddings(request: Request):
    body = await request.json()
    texts = body.get("input", [])
    if isinstance(texts, str):
        texts = [texts]
        
    print(f"[FastEmbed] Start embedding {len(texts)} chunks")
    embeddings = list(embedding_model.embed(texts))
    print(f"[FastEmbed] Finished embedding {len(texts)} chunks")
    
    data = []
    for i, vec in enumerate(embeddings):
        data.append({
            "object": "embedding",
            "embedding": vec.tolist(),
            "index": i
        })
        
    return {
        "object": "list",
        "data": data,
        "model": "BAAI/bge-base-en-v1.5",
        "usage": {"prompt_tokens": 0, "total_tokens": 0}
    }

# --- ROUTE 3: Proxy LLM to Background vLLM ---
client = httpx.AsyncClient(base_url="http://localhost:8001")

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_vllm(path: str, request: Request):
    print(f"[vLLM Proxy] Routing /{path}")
    req = client.build_request(
        method=request.method,
        url=f"/v1/{path}",
        headers=request.headers.raw,
        content=await request.body()
    )
    response = await client.send(req, stream=True)
    return StreamingResponse(
        response.aiter_raw(),
        status_code=response.status_code,
        headers={k: v for k, v in response.headers.items() if k.lower() not in ('content-length', 'transfer-encoding')}
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
"""

def update_notebook(filepath):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath}, does not exist.")
        return
        
    with open(filepath, 'r') as f:
        data = json.load(f)
        
    for cell in data.get('cells', []):
        if cell.get('cell_type') == 'code':
            source = cell.get('source', [])
            if source and source[0].startswith('%%writefile seekr_ml_gateway.py'):
                # Replace the entire cell source
                # The format expected by Jupyter is a list of strings with newlines
                lines = [line + '\n' for line in new_gateway_code.split('\n')]
                # Remove the last empty newline if it exists
                if lines and lines[-1] == '\n':
                    lines.pop()
                cell['source'] = lines
                print(f"Updated gateway code in {filepath}")
                break
                
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=1)

update_notebook('seekr_unified_notebook.ipynb')
update_notebook('colab_gpu_use.ipynb')
