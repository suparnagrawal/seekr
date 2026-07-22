import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.shared.config import settings

print(f"REMOTE_PARSER_URL: {settings.REMOTE_PARSER_URL}")
print(f"EMBEDDING_MODEL_ENDPOINT: {settings.EMBEDDING_MODEL_ENDPOINT}")
print(f"LLM_BASE_URL: {settings.LLM_BASE_URL}")
print(f"LLM_MODEL: {settings.LLM_MODEL}")
