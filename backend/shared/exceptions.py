"""
Custom exceptions for the SEEKR domain and infrastructure.
Provides semantic error handling across the backend.
"""

class SeekrError(Exception):
    """Base class for all custom SEEKR exceptions."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class InfrastructureError(SeekrError):
    """Raised when a backing data store (Postgres, Neo4j, Qdrant, Redis) fails."""
    def __init__(self, message: str, service: str):
        super().__init__(f"{service} Error: {message}", status_code=503)
        self.service = service

class ResourceNotFoundError(SeekrError):
    """Raised when a requested document, entity, or graph node cannot be found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)

class DuplicateResourceError(SeekrError):
    """Raised when attempting to create a resource that already exists."""
    def __init__(self, message: str):
        super().__init__(message, status_code=409)

class UnsupportedMediaTypeError(SeekrError):
    """Raised when an uploaded file has an unsupported MIME type."""
    def __init__(self, message: str):
        super().__init__(message, status_code=415)

class PayloadTooLargeError(SeekrError):
    """Raised when an uploaded file exceeds the maximum allowed size."""
    def __init__(self, message: str):
        super().__init__(message, status_code=413)

class ValidationFailedError(SeekrError):
    """Raised when input payload, file format, or extraction schema is invalid."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)

class IngestionPipelineError(SeekrError):
    """Raised when the document extraction pipeline fails (e.g. Docling or OCR failure)."""
    def __init__(self, message: str, stage: str):
        super().__init__(f"Ingestion failed at {stage}: {message}", status_code=500)
        self.stage = stage

class AuthenticationError(SeekrError):
    """Raised when a JWT is invalid, expired, or missing."""
    def __init__(self, message: str = "Authentication required."):
        super().__init__(message, status_code=401)

class AuthorizationError(SeekrError):
    """Raised when an authenticated user lacks the required role for an action."""
    def __init__(self, message: str = "Insufficient permissions."):
        super().__init__(message, status_code=403)
