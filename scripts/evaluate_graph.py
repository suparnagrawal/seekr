
from backend.shared.neo4j_client import neo4j_driver

def evaluate_graph():
    """
    Evaluates the Neo4j Knowledge Graph to determine extraction quality.
    Outputs metrics around nodes, edges, duplicates, and connectivity.
    """
    print("Starting Graph Evaluation...\n")
    
    with neo4j_driver.session() as session:
        # 1. Total Nodes
        result = session.run("MATCH (n) RETURN count(n) AS total_nodes")
        total_nodes = result.single()["total_nodes"]
        print(f"Total Nodes: {total_nodes}")
        
        # 2. Total Edges
        result = session.run("MATCH ()-[r]->() RETURN count(r) AS total_edges")
        total_edges = result.single()["total_edges"]
        print(f"Total Edges: {total_edges}")
        
        # 3. Duplicate Tags
        result = session.run("""
            MATCH (n:Entity)
            WITH n.tag AS tag, count(n) AS c
            WHERE c > 1
            RETURN count(tag) AS duplicate_tags
        """)
        duplicate_tags = result.single()["duplicate_tags"]
        print(f"Duplicate Tags (Canonicalization needed): {duplicate_tags}")
        
        # 4. Orphan Nodes (Nodes with no relationships)
        result = session.run("""
            MATCH (n)
            WHERE NOT (n)-[]-()
            RETURN count(n) AS orphans
        """)
        orphans = result.single()["orphans"]
        print(f"Orphan Nodes (Isolated): {orphans} ({(orphans / total_nodes * 100) if total_nodes else 0:.1f}%)")
        
        # 5. Average Degree
        result = session.run("""
            MATCH (n)
            WITH n, size((n)-[]-()) AS degree
            RETURN avg(degree) AS avg_degree
        """)
        avg_degree = result.single()["avg_degree"]
        print(f"Average Node Degree: {avg_degree:.2f}" if avg_degree else "Average Node Degree: 0")
        
        # 6. Label Distribution
        print("\nLabel Distribution:")
        result = session.run("""
            MATCH (n:Entity)
            WITH labels(n) AS lbls
            UNWIND lbls AS label
            WHERE label <> 'Entity'
            RETURN label, count(*) AS count
            ORDER BY count DESC
        """)
        for record in result:
            print(f"  {record['label']}: {record['count']}")
            
        # 7. Relationship Distribution
        print("\nRelationship Distribution:")
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(r) AS count
            ORDER BY count DESC
        """)
        for record in result:
            print(f"  {record['rel_type']}: {record['count']}")
            
        # 8. Confidence Histogram (simplified into buckets)
        print("\nConfidence Distribution:")
        result = session.run("""
            MATCH ()-[r]->()
            WITH COALESCE(r.confidence, 0.5) AS conf
            RETURN 
                sum(CASE WHEN conf >= 0.8 THEN 1 ELSE 0 END) AS high,
                sum(CASE WHEN conf >= 0.5 AND conf < 0.8 THEN 1 ELSE 0 END) AS medium,
                sum(CASE WHEN conf < 0.5 THEN 1 ELSE 0 END) AS low
        """)
        hist = result.single()
        print(f"  High (>= 0.8): {hist['high']}")
        print(f"  Medium (0.5 - 0.79): {hist['medium']}")
        print(f"  Low (< 0.5): {hist['low']}")
        
        # 9. Documents processed
        print("\nDocument Statistics:")
        result = session.run("""
            MATCH (n:Entity)
            UNWIND n.document_ids AS doc_id
            RETURN count(DISTINCT doc_id) AS total_docs
        """)
        total_docs = result.single()["total_docs"]
        print(f"  Total Documents indexed in Graph: {total_docs}")
        if total_docs and total_nodes:
            print(f"  Nodes per Document: {total_nodes / total_docs:.1f}")
            print(f"  Edges per Document: {total_edges / total_docs:.1f}")

if __name__ == "__main__":
    evaluate_graph()
