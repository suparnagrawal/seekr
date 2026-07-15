import os
import httpx
from openai import OpenAI

# Grab the ngrok URL from .env
with open('backend/.env', 'r') as f:
    for line in f:
        if line.startswith('EMBEDDING_MODEL_ENDPOINT='):
            endpoint = line.strip().split('=', 1)[1]

print(f"Testing endpoint: {endpoint}")

client = OpenAI(
    base_url=endpoint,
    api_key="dummy",
    default_headers={"ngrok-skip-browser-warning": "1"},
    http_client=httpx.Client(event_hooks={'request': [lambda r: print(f"URL: {r.url}")]})
)

try:
    res = client.embeddings.create(input=["hello"], model="BAAI/bge-base-en-v1.5", timeout=10.0)
    print("Success:", res.data[0].embedding[:3])
except Exception as e:
    print("Failed:", type(e), e)
