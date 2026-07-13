import hashlib
import uuid
import boto3
import structlog
import os
import shutil
from botocore.client import Config
from fastapi import UploadFile

from backend.shared.config import settings

logger = structlog.get_logger(__name__)

class StorageManager:
    """
    Manages remote S3 operations for the SEEKR backend.
    """
    
    def __init__(self):
        self.bucket = settings.S3_BUCKET_NAME
        
        # Check if we should fallback to local storage
        self.use_local = not bool(settings.S3_ACCESS_KEY_ID)
        if self.use_local:
            self.upload_dir = settings.UPLOAD_DIR
            os.makedirs(self.upload_dir, exist_ok=True)
            logger.info("S3 credentials not found, falling back to local disk storage", upload_dir=str(self.upload_dir))
            return
            
        # Configure boto3 client
        client_kwargs = {}
        if settings.S3_ENDPOINT_URL:
            client_kwargs['endpoint_url'] = settings.S3_ENDPOINT_URL
        if settings.S3_ACCESS_KEY_ID:
            client_kwargs['aws_access_key_id'] = settings.S3_ACCESS_KEY_ID
        if settings.S3_SECRET_ACCESS_KEY:
            client_kwargs['aws_secret_access_key'] = settings.S3_SECRET_ACCESS_KEY
        if settings.S3_REGION:
            client_kwargs['region_name'] = settings.S3_REGION
            
        # For Supabase / R2 compat
        client_kwargs['config'] = Config(signature_version='s3v4')
            
        self.s3_client = boto3.client('s3', **client_kwargs)
        
    def get_object_key(self, document_id: uuid.UUID | str, filename: str) -> str:
        """Returns the S3 object key for an artifact."""
        return f"{document_id}/{filename}"
        
    def get_artifact_uri(self, document_id: uuid.UUID | str, filename: str) -> str:
        """Returns the URI (S3 or local path) for an artifact."""
        if self.use_local:
            return str(self.upload_dir / str(document_id) / filename)
        return f"s3://{self.bucket}/{self.get_object_key(document_id, filename)}"

    def save_and_hash_file(self, file: UploadFile, document_id: uuid.UUID) -> tuple[str, str]:
        """
        Computes SHA256 hash of the uploaded file and uploads it to S3.
        Returns a tuple of (s3_uri, sha256_hash).
        """
        import tempfile
        import os
        from pathlib import Path
        
        extension = Path(file.filename or "").suffix
        if not extension:
            extension = ".pdf"
            
        stored_filename = f"original{extension}"
        object_key = self.get_object_key(document_id, stored_filename)
        
        sha256_hash = hashlib.sha256()
        
        # Reset file pointer before reading
        file.file.seek(0)
        
        # We write to a temporary file first to calculate hash and safely upload to S3
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            while chunk := file.file.read(8192):
                temp_file.write(chunk)
                sha256_hash.update(chunk)
                
        try:
            if self.use_local:
                local_dir = self.upload_dir / str(document_id)
                os.makedirs(local_dir, exist_ok=True)
                target_path = local_dir / stored_filename
                shutil.move(temp_path, str(target_path))
                logger.info("Original file saved to local storage and hashed", local_path=str(target_path))
                return str(target_path), sha256_hash.hexdigest()
            else:
                self.s3_client.upload_file(temp_path, self.bucket, object_key)
                s3_uri = f"s3://{self.bucket}/{object_key}"
                logger.info("Original file uploaded to S3 and hashed", s3_uri=s3_uri)
                return s3_uri, sha256_hash.hexdigest()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    def delete_document_dir(self, document_id: uuid.UUID | str) -> None:
        """
        Deletes all objects in S3 matching the document's prefix.
        """
        if self.use_local:
            local_dir = self.upload_dir / str(document_id)
            if local_dir.exists() and local_dir.is_dir():
                try:
                    shutil.rmtree(str(local_dir))
                    logger.info("Document artifacts deleted from local storage", document_id=str(document_id))
                except Exception as e:
                    logger.error("Failed to delete document artifacts from local storage", error=str(e), document_id=str(document_id))
            return
            
        prefix = f"{document_id}/"
        try:
            # Paginate through all objects with the prefix and delete them
            paginator = self.s3_client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects_to_delete:
                        self.s3_client.delete_objects(
                            Bucket=self.bucket,
                            Delete={'Objects': objects_to_delete}
                        )
            logger.info("Document artifacts deleted from S3", document_id=str(document_id))
        except Exception as e:
            logger.error("Failed to delete document artifacts from S3", error=str(e), document_id=str(document_id))
            
    def save_artifact(self, document_id: uuid.UUID | str, filename: str, content: str | bytes) -> str:
        """
        Saves a parsed artifact (like parsed.md or metadata.json) directly to S3.
        Returns the S3 URI.
        """
        body = content.encode('utf-8') if isinstance(content, str) else content
        
        if self.use_local:
            local_dir = self.upload_dir / str(document_id)
            os.makedirs(local_dir, exist_ok=True)
            target_path = local_dir / filename
            with open(target_path, "wb") as f:
                f.write(body)
            logger.info("Artifact saved to local storage", local_path=str(target_path))
            return str(target_path)
            
        object_key = self.get_object_key(document_id, filename)
        
        self.s3_client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=body
        )
                
        s3_uri = f"s3://{self.bucket}/{object_key}"
        logger.info("Artifact uploaded to S3", s3_uri=s3_uri)
        return s3_uri

    def download_to_tempfile(self, s3_uri: str) -> str:
        """
        Downloads an S3 object to a local temporary file and returns its path.
        The caller is responsible for deleting the file.
        """
        import tempfile
        if not s3_uri.startswith("s3://"):
            return s3_uri # Fallback if it's already a local path somehow
            
        # Parse s3://bucket/key
        parts = s3_uri.replace("s3://", "").split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        bucket, key = parts
        
        import os
        from pathlib import Path
        extension = Path(key).suffix or ".tmp"
        
        temp_fd, temp_path = tempfile.mkstemp(suffix=extension)
        os.close(temp_fd)
        
        logger.info("Downloading from S3 to temp file", s3_uri=s3_uri, temp_path=temp_path)
        self.s3_client.download_file(bucket, key, temp_path)
        return temp_path

storage_manager = StorageManager()
