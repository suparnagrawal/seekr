# HISTORICAL SCRIPT: This file tests the deprecated GraphIndexer.
# It is not executed in production and remains here for archival purposes.

from backend.deprecated.graph_indexer import get_graph_indexer

def run_mock_ingestion():
    """
    Simulates a successful LLM extraction of an equipment manual
    to verify that GraphIndexer constraints, Cypher generation,
    and Python validations correctly operate.
    """
    print("Starting Mock Ingestion...")
    indexer = get_graph_indexer()
    
    # 1. Bootstrap the constraints
    print("Bootstrapping Graph Indexer...")
    indexer.bootstrap()
    
    # 2. Define the Mock Data
    document_id = "test-doc-123"
    graph_data = {
        "nodes": [
            {
                "tag": "Pump P-101",
                "label": "Equipment",
                "properties": {"manufacturer": "Flowserve"}
            },
            {
                "tag": "Impeller Damage",
                "label": "Fault",
                "properties": {"severity": "High"}
            },
            {
                "tag": "Replace Impeller",
                "label": "Procedure",
                "properties": {"estimated_hours": 4}
            },
            {
                "tag": "Invalid Node Type",
                "label": "SomethingElse",
                "properties": {}
            }
        ],
        "edges": [
            {
                "source": "Pump P-101",
                "target": "Impeller Damage",
                "type": "INDICATES",
                "confidence": 0.95
            },
            {
                "source": "Replace Impeller",
                "target": "Impeller Damage",
                "type": "MITIGATES",
                "confidence": 0.88
            },
            {
                "source": "Missing Source Node", # Edge pointing nowhere (MATCH will fail gracefully)
                "target": "Impeller Damage",
                "type": "CAUSES",
                "confidence": 0.5
            },
            {
                "source": "Pump P-101",
                "target": "Impeller Damage",
                "type": "INVALID_RELATION", # Python validation will drop this
                "confidence": 0.1
            }
        ]
    }
    
    # 3. Index the data
    print(f"Indexing Graph Data for Document: {document_id}")
    indexer.index_graph_data(document_id, graph_data)
    print("Mock Ingestion Complete.\n")

if __name__ == "__main__":
    run_mock_ingestion()
