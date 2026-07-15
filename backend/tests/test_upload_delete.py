"""
Tests for the document deletion endpoint.

Validates:
  - 404 when document does not exist
  - Full cascading deletion (DELETING state → Neo4j → Qdrant → Storage → Postgres)
  - DELETING state is set BEFORE any cascade operations begin
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient

# Mock settings before importing app
with patch("backend.shared.config.settings.S3_ACCESS_KEY_ID", "mock"):
    from backend.fabric_api.main import app

client = TestClient(app)


def test_delete_document_not_found():
    response = client.delete(f"/api/v1/documents/{uuid.uuid4()}")
    assert response.status_code == 404


@patch("backend.shared.repositories.document_repository.DocumentRepository.get_by_id")
@patch("backend.shared.repositories.document_repository.DocumentRepository.update_status")
@patch("backend.shared.repositories.document_repository.DocumentRepository.delete")
@patch("backend.shared.neo4j_client.neo4j_driver.session")
@patch("backend.shared.services.qdrant_service.get_qdrant_service")
@patch("backend.shared.storage.storage_manager.delete_document_dir")
def test_delete_document_success(
    mock_delete_dir, mock_get_qdrant, mock_neo4j_session,
    mock_delete, mock_update_status, mock_get_by_id,
):
    # Setup mocks
    doc_id = str(uuid.uuid4())
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_get_by_id.return_value = mock_doc

    # Mock Neo4j session and transaction
    mock_session_instance = MagicMock()
    mock_neo4j_session.return_value.__enter__.return_value = mock_session_instance
    mock_session_instance.run.return_value = []

    mock_qdrant_instance = MagicMock()
    mock_get_qdrant.return_value = mock_qdrant_instance

    # Execute
    response = client.delete(f"/api/v1/documents/{doc_id}")

    # Verify HTTP response
    assert response.status_code == 204

    # Verify DELETING state was set FIRST (before cascade)
    mock_update_status.assert_called_once_with(doc_id, "DELETING")

    # Verify cascade order: Neo4j queries were issued
    assert mock_session_instance.run.call_count >= 2  # tag extraction + edge delete

    # Verify Qdrant cleanup
    mock_qdrant_instance.delete_by_document_id.assert_called_once_with(doc_id)

    # Verify storage cleanup
    mock_delete_dir.assert_called_once_with(uuid.UUID(doc_id))

    # Verify hard-delete from Postgres (final step)
    mock_delete.assert_called_once_with(doc_id)


@patch("backend.shared.repositories.document_repository.DocumentRepository.get_by_id")
@patch("backend.shared.repositories.document_repository.DocumentRepository.update_status")
@patch("backend.shared.repositories.document_repository.DocumentRepository.delete")
@patch("backend.shared.neo4j_client.neo4j_driver.session")
@patch("backend.shared.services.qdrant_service.get_qdrant_service")
@patch("backend.shared.storage.storage_manager.delete_document_dir")
def test_delete_document_cascade_order(
    mock_delete_dir, mock_get_qdrant, mock_neo4j_session,
    mock_delete, mock_update_status, mock_get_by_id,
):
    """Verify the state machine: DELETING is committed before any destructive ops."""
    doc_id = str(uuid.uuid4())
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_get_by_id.return_value = mock_doc

    # Track call order across mocked subsystems
    call_order = []
    mock_update_status.side_effect = lambda *a, **kw: call_order.append("update_status")
    mock_neo4j_session.return_value.__enter__.return_value.run.side_effect = (
        lambda *a, **kw: call_order.append("neo4j_run") or []
    )
    mock_get_qdrant.return_value.delete_by_document_id.side_effect = (
        lambda *a, **kw: call_order.append("qdrant_delete")
    )
    mock_delete_dir.side_effect = lambda *a, **kw: call_order.append("storage_delete")
    mock_delete.side_effect = lambda *a, **kw: call_order.append("pg_delete")

    response = client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 204

    # DELETING must be the very first action
    assert call_order[0] == "update_status"
    # Hard-delete from Postgres must be the very last action
    assert call_order[-1] == "pg_delete"
