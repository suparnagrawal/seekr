"""
System-wide constants for the SEEKR backend.
Ensures consistency between Fabric API and Ingestion Worker.
"""

# Versioning
API_V1_PREFIX = "/api/v1"
PROJECT_VERSION = "1.0.0"

# Redis Queues
INGESTION_QUEUE_NAME = "ingestion_queue"
# Timeouts
JOB_TIMEOUT_SECONDS = 3600  # 1 hour
DEFAULT_RETRY_COUNT = 3

# Chunking defaults
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Graph traversal defaults
DEFAULT_GRAPH_TRAVERSAL_DEPTH = 2
MAX_GRAPH_TRAVERSAL_DEPTH = 5

# Security
ROLE_TECHNICIAN = "Technician"
ROLE_ENGINEER = "Engineer"
ROLE_COMPLIANCE_OFFICER = "Compliance Officer"
ROLE_ADMIN = "Admin"

# External API Utilities
NGROK_HEADERS = {"ngrok-skip-browser-warning": "1"}

def resolve_gateway_url(ml_gateway_url: str | None, path: str) -> str | None:
    if not ml_gateway_url:
        return None
    return ml_gateway_url.rstrip('/') + (path if path.startswith('/') else '/' + path)
