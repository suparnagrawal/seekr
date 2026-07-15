import structlog
from pathlib import Path
from typing import Any
import importlib.metadata
from dataclasses import dataclass

# We will import Docling components dynamically inside methods to avoid massive import penalties 
# at the module level for parts of the app that don't need it.

from backend.shared.exceptions import IngestionPipelineError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger(__name__)

def get_docling_version() -> str:
    try:
        return importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"

@dataclass(slots=True)
class ParsedDocument:
    """Standardized output structure for document parsing."""
    markdown: str
    metadata: dict[str, Any]
    page_count: int
    docling_document: Any | None  # The in-memory DoclingDocument
    chunks: list[dict[str, Any]] | None = None

class ParsingService:
    """
    Wraps the Docling DocumentConverter for robust document extraction.
    Handles OCR fallbacks and structured Markdown generation.
    """
    
    def __init__(self, parser_config: dict[str, Any] | None = None, ml_gateway_url: str | None = None):
        """
        Initializes the service with injectable configuration.
        """
        self._converter = None
        self.ml_gateway_url = ml_gateway_url
        self._config = parser_config or {
            "do_ocr": True,
            "do_table_structure": True,
            "ocr_provider": "easyocr" # Prepare for future selection
        }
        self.docling_version = get_docling_version()
        
    def _get_converter(self):
        """
        Lazy-loads the DocumentConverter to avoid huge startup times
        unless this service is actually used.
        """
        if self._converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = self._config.get("do_ocr", True)
            pipeline_options.do_table_structure = self._config.get("do_table_structure", True)
            
            self._converter = DocumentConverter(
                allowed_formats=[InputFormat.PDF],
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
            logger.info("Docling DocumentConverter initialized", config=self._config, docling_version=self.docling_version)
            
        return self._converter
        
    def parse_document(self, file_path: str) -> ParsedDocument:
        """
        Parses a document using Docling.
        
        Returns:
            ParsedDocument containing markdown, metadata, and page_count.
            
        Raises:
            IngestionPipelineError: If parsing fails.
        """
        is_temp_file = False
        original_file_path = file_path
        
        if file_path.startswith("s3://"):
            from backend.shared.storage import storage_manager
            file_path = storage_manager.download_to_tempfile(file_path)
            is_temp_file = True
            
        path = Path(file_path)
        if not path.exists():
            raise IngestionPipelineError(f"File not found: {file_path}", stage="Docling Initial Load")
            
        logger.info("Starting Docling extraction", file_path=original_file_path, local_path=str(path))
        
        try:
            from backend.shared.config import settings
            
            target_url = None
            if self.ml_gateway_url:
                target_url = self.ml_gateway_url.rstrip('/') + '/parse'
            elif settings.REMOTE_PARSER_URL:
                target_url = settings.REMOTE_PARSER_URL

            if target_url:
                logger.info("Offloading Docling parsing to remote gateway", remote_url=target_url)
                import httpx
                
                @retry(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=2, min=4, max=10),
                    retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
                    reraise=True
                )
                def _do_remote_parse():
                    logger.info("Executing remote parse request", attempt="auto-retry")
                    with open(path, "rb") as f:
                        files = {"file": (path.name, f, "application/pdf")}
                        # We give the remote API up to 5 minutes to parse a large document
                        resp = httpx.post(
                            target_url,
                            files=files,
                            headers={"ngrok-skip-browser-warning": "1"},
                            timeout=300.0
                        )
                    resp.raise_for_status()
                    return resp
                
                response = _do_remote_parse()
                
                data = response.json()
                markdown_content = data["markdown"]
                metadata = data["metadata"]
                page_count = data["page_count"]
                
                # Retrieve pre-computed chunks from the gateway
                chunks = data.get("chunks", None)
                
                # IMPORTANT: DO NOT import DoclingDocument here!
                # Simply importing anything from docling.datamodel can pull in Torch/Transformers 
                # at the module level and instantly OOM the 512MB Render instance.
                docling_document = None
                
                logger.info("Remote Docling extraction completed", file_path=original_file_path, page_count=page_count, has_chunks=bool(chunks))
            else:
                logger.info("Using local Docling parser")
                converter = self._get_converter()
                # Convert the document
                result = converter.convert(path)
                
                # Export to Markdown
                markdown_content = result.document.export_to_markdown()
                
                # Gather metadata
                page_count = len(result.document.pages)
                
                metadata = {
                    "origin": result.input.file.name,
                    "file_size": result.input.file.stat().st_size,
                    "docling_version": self.docling_version,
                    "page_count": page_count,
                    "parser_config": self._config
                }
                
                docling_document = result.document
                logger.info("Local Docling extraction completed", file_path=original_file_path, page_count=page_count)
                chunks = None
                
            return ParsedDocument(
                markdown=markdown_content,
                metadata=metadata,
                page_count=page_count,
                docling_document=docling_document,
                chunks=chunks
            )
            
        except Exception as e:
            logger.error(
                "Docling parsing failed", 
                file_path=original_file_path, 
                exception_type=type(e).__name__, 
                error=str(e),
                exc_info=True
            )
            raise IngestionPipelineError(message=str(e), stage="Docling Conversion")
        finally:
            if is_temp_file and path.exists():
                import os
                os.remove(path)
                logger.info("Deleted temporary download file", temp_path=str(path))

def get_parsing_service() -> ParsingService:
    """Dependency provider for ParsingService."""
    return ParsingService()
