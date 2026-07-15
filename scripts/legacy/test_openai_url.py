from openai import OpenAI
import httpx

client = OpenAI(
    base_url="https://example.com/v1",
    api_key="dummy",
    http_client=httpx.Client(event_hooks={'request': [lambda r: print("URL:", r.url)]})
)
try:
    client.embeddings.create(input=["test"], model="test")
except Exception as e:
    pass
