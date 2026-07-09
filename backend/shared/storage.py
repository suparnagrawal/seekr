import hashlib
import uuid
from pathlib import Path
import structlog
from fastapi import UploadFile

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

class StorageManager:
    """
    Manages local filesystem operations for the SEEKR backend.
    """
    
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
    def get_document_dir(self, document_id: uuid.UUID | str) -> Path:
        """Returns the artifact directory for a document, creating it if necessary."""
        doc_dir = self.upload_dir / str(document_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    def save_and_hash_file(self, file: UploadFile, document_id: uuid.UUID) -> tuple[str, str]:
        """
        Saves the uploaded file to the document's artifact directory synchronously 
        and computes its SHA256 hash in one pass.
        Returns a tuple of (stored_path, sha256_hash).
        """
        doc_dir = self.get_document_dir(document_id)
        extension = Path(file.filename or "").suffix
        if not extension:
            extension = ".pdf"
            
        stored_filename = f"original{extension}"
        stored_path = doc_dir / stored_filename
        
        sha256_hash = hashlib.sha256()
        
        # Reset file pointer before reading
        file.file.seek(0)
        
        with stored_path.open("wb") as buffer:
            while chunk := file.file.read(8192):
                buffer.write(chunk)
                sha256_hash.update(chunk)
                
        logger.info("Original file saved to disk and hashed", stored_path=str(stored_path))
        return str(stored_path), sha256_hash.hexdigest()
        
    def delete_document_dir(self, document_id: uuid.UUID | str) -> None:
        """
        Deletes the entire document artifact directory. Used for cleanup on failure.
        """
        import shutil
        doc_dir = self.upload_dir / str(document_id)
        if doc_dir.exists() and doc_dir.is_dir():
            shutil.rmtree(doc_dir)
            logger.info("Document directory deleted during cleanup", document_id=str(document_id))
            
    def save_artifact(self, document_id: uuid.UUID | str, filename: str, content: str | bytes) -> str:
        """
        Saves a parsed artifact (like parsed.md or metadata.json) to the document's directory.
        Returns the absolute stored path.
        """
        doc_dir = self.get_document_dir(document_id)
        stored_path = doc_dir / filename
        
        if isinstance(content, str):
            with stored_path.open("w", encoding="utf-8") as f:
                f.write(content)
        else:
            with stored_path.open("wb") as f:
                f.write(content)
                
        logger.info("Artifact saved to disk", stored_path=str(stored_path))
        return str(stored_path)

storage_manager = StorageManager()
