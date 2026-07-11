import structlog
from typing import Dict, Any, List

from backend.shared.neo4j_client import neo4j_driver
from backend.shared.exceptions import InfrastructureError

logger = structlog.get_logger(__name__)

ALLOWED_LABELS = {"Equipment", "Component", "Fault", "Procedure", "Parameter", "Concept"}
ALLOWED_RELATIONS = {"HAS_PART", "CAUSES", "INDICATES", "REQUIRES", "MITIGATES", "RELATED_TO"}

class GraphIndexer:
    """
    Handles bulk insertion of extracted nodes and edges into Neo4j.
    Uses UNWIND for efficient batched execution.
    """
    
    def bootstrap(self) -> None:
        """
        Creates necessary constraints and indices for the graph.
        Should be called during application startup.
        """
        try:
            with neo4j_driver.session() as session:
                session.run("CREATE CONSTRAINT entity_tag IF NOT EXISTS FOR (e:Entity) REQUIRE e.tag IS UNIQUE")
                logger.info("✓ Entity constraint exists")
                # Also create index on entity_type even though we use multi-labels now, it doesn't hurt and was requested.
                session.run("CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)")
                logger.info("✓ entity_type index exists")
            logger.info("Successfully bootstrapped Graph database constraints.")
        except Exception as e:
            logger.error("Failed to bootstrap Graph database", error=str(e), exc_info=True)
            raise InfrastructureError(f"Neo4j bootstrap failed: {str(e)}", service="Neo4j") from e
    
    def index_graph_data(self, document_id: str, graph_data: Dict[str, Any]) -> None:
        """
        Indexes nodes and edges from the LLM extraction output.
        """
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        if not nodes and not edges:
            logger.info("No graph data to index", document_id=document_id)
            return

        try:
            with neo4j_driver.session() as session:
                # 1. Index Nodes Grouped by Label
                if nodes:
                    nodes_by_label = {}
                    for node in nodes:
                        # Extract node from dict if it was parsed as dict, or use it if it's an object
                        label = node.get("label") if isinstance(node, dict) else getattr(node, "label", None)
                        if label not in ALLOWED_LABELS:
                            logger.warning("Skipping node with invalid label", label=label)
                            continue
                        nodes_by_label.setdefault(label, []).append(node)
                    
                    for label, label_nodes in nodes_by_label.items():
                        query = f"""
                        UNWIND $nodes AS node
                        MERGE (n:Entity:{label} {{tag: node.tag}})
                        SET n += node.properties
                        SET n.canonical_tag = node.tag
                        SET n.extractor_version = $extractor_version
                        SET n.ontology_version = $ontology_version
                        SET n.model_name = $model_name
                        SET n.document_ids = COALESCE(n.document_ids, [])
                        WITH n WHERE NOT $document_id IN n.document_ids
                        SET n.document_ids = n.document_ids + [$document_id]
                        """
                        session.run(
                            query,
                            nodes=label_nodes,
                            document_id=document_id,
                            extractor_version="v1",
                            ontology_version="v1",
                            model_name="gpt-4o-mini"
                        )
                
                # 2. Index Edges Grouped by Type
                if edges:
                    edges_by_type = {}
                    for edge in edges:
                        source = edge.get("source") if isinstance(edge, dict) else getattr(edge, "source", None)
                        target = edge.get("target") if isinstance(edge, dict) else getattr(edge, "target", None)
                        edge_type = edge.get("type") if isinstance(edge, dict) else getattr(edge, "type", None)
                        
                        if source == target:
                            logger.warning("Skipping self-loop edge", document_id=document_id, source=source, target=target, type=edge_type)
                            continue
                            
                        if not source or not target:
                            logger.warning("Skipping edge with missing source or target", document_id=document_id, source=source, target=target, type=edge_type)
                            continue
                            
                        if edge_type not in ALLOWED_RELATIONS:
                            logger.warning("Skipping edge with invalid type", document_id=document_id, source=source, target=target, type=edge_type)
                            continue
                        edges_by_type.setdefault(edge_type, []).append(edge)
                        
                    for edge_type, type_edges in edges_by_type.items():
                        query = f"""
                        UNWIND $edges AS edge
                        MATCH (source:Entity {{tag: edge.source}})
                        MATCH (target:Entity {{tag: edge.target}})
                        MERGE (source)-[r:{edge_type}]->(target)
                        SET r.confidence = COALESCE(edge.confidence, 0.5)
                        SET r.extractor_version = $extractor_version
                        SET r.ontology_version = $ontology_version
                        SET r.model_name = $model_name
                        SET r.document_ids = COALESCE(r.document_ids, [])
                        WITH r WHERE NOT $document_id IN r.document_ids
                        SET r.document_ids = r.document_ids + [$document_id]
                        """
                        session.run(
                            query,
                            edges=type_edges,
                            document_id=document_id,
                            extractor_version="v1",
                            ontology_version="v1",
                            model_name="gpt-4o-mini"
                        )
                    
            logger.info("Successfully indexed graph data", document_id=document_id, node_count=len(nodes), edge_count=len(edges))
            
        except Exception as e:
            logger.error("Failed to index graph data in Neo4j", document_id=document_id, error=str(e), exc_info=True)
            raise InfrastructureError(f"Neo4j indexing failed: {str(e)}", service="Neo4j") from e

def get_graph_indexer() -> GraphIndexer:
    return GraphIndexer()
