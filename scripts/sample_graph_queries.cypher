// Sample Seekr Graph Queries
// Use these in the Neo4j Browser or Cypher Shell for debugging P1 extraction quality.

// 1. Basic Counts
MATCH (n) RETURN count(n) AS total_nodes;
MATCH ()-[r]->() RETURN count(r) AS total_edges;

// 2. View latest Equipment extracted
MATCH (n:Entity:Equipment) 
RETURN n.tag, n.properties, n.document_ids 
LIMIT 20;

// 3. View connected Faults
MATCH (e:Equipment)-[r]->(f:Fault)
RETURN e.tag AS Equipment, type(r) AS Relation, f.tag AS Fault, r.confidence AS Confidence
ORDER BY r.confidence DESC
LIMIT 20;

// 4. Find highly connected hubs (similar to P2 detect_hubs)
MATCH (n:Entity)-[r]-()
WITH n, count(r) AS degree
WHERE degree > 3
RETURN n.tag, labels(n)[1] AS type, degree
ORDER BY degree DESC
LIMIT 10;

// 5. Find Orphan Nodes (Nodes without any relationships)
MATCH (n:Entity)
WHERE NOT (n)-[]-()
RETURN n.tag, labels(n)[1] AS type
LIMIT 20;

// 6. Check for duplicate tags (Canonicalization needed)
MATCH (n:Entity)
WITH n.tag AS tag, count(n) AS tag_count
WHERE tag_count > 1
RETURN tag, tag_count
ORDER BY tag_count DESC;
