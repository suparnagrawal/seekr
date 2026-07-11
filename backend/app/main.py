from fastapi import FastAPI
from backend.app.api import query, agents

app = FastAPI(title="SEEKR Fabric API")

app.include_router(query.router, prefix="/api", tags=["query"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
