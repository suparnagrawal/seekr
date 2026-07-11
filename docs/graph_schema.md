# Seekr Industrial Knowledge Graph Ontology

**Version**: 1

This document defines the strict, shared graph ontology contract between P1 (Ingestion/Extraction), P2 (Retrieval), and P3 (Agents). 
All extracted entities and relationships MUST adhere to this schema.

## Node Requirements

To support the P2 `neo4j_neighbors()` and `pathways.py` cypher queries, every node must possess:
1. **Label (`entity_type`)**: The primary class of the node (e.g., `:Equipment`).
2. **Property `tag`**: A canonical, string identifier for the node (e.g., `tag: "Pump P-101A"`). P2 relies entirely on exact matches of the `tag` property for seeds and neighbor lookups.
3. **Property `document_ids`**: A list of `document_id` UUID strings where this node was mentioned, establishing provenance.

## Node Entity Types (Labels)

| Label | Description | Example `tag` |
| :--- | :--- | :--- |
| `Equipment` | Primary industrial machines or assets. | `"Centrifugal Pump"`, `"Compressor C-200"` |
| `Component` | Sub-parts of an Equipment. | `"Impeller"`, `"Mechanical Seal"` |
| `Fault` | Failure modes or root causes. | `"Cavitation"`, `"Bearing Wear"`, `"Overheating"` |
| `Procedure` | Maintenance or operational actions. | `"Vibration Analysis"`, `"Startup Sequence"` |
| `Parameter` | Measurable values or conditions. | `"Discharge Pressure"`, `"High Temperature"` |
| `Concept` | General industrial terminology (fallback). | `"Fluid Dynamics"`, `"Preventative Maintenance"` |

## Relationship Types

To support robust graph traversal (e.g., failure propagation), relationships must be strictly categorized:

| Relationship Type | Source Label | Target Label | Description |
| :--- | :--- | :--- | :--- |
| `HAS_PART` | `Equipment` | `Component` | Hierarchical breakdown of assets. |
| `CAUSES` | `Fault`, `Procedure` | `Fault`, `Parameter` | Causal chain (e.g., Cavitation CAUSES Vibration). |
| `INDICATES` | `Parameter` | `Fault` | Symptoms leading to diagnosis. |
| `REQUIRES` | `Fault`, `Equipment` | `Procedure` | Actions needed to resolve or maintain. |
| `MITIGATES` | `Procedure` | `Fault` | Actions that prevent or solve a fault. |
| `RELATED_TO` | `Any` | `Any` | Generic semantic relationship (fallback). |

## Edge Properties

Every edge should optionally include:
1. **Property `confidence`** (Float, 0.0 to 1.0): Represents the LLM's confidence in the relationship. P2's adaptive traversal uses this as a decay factor (`COALESCE(r.confidence, 1.0)`).
2. **Property `document_ids`** (List of Strings): The source documents that provided evidence for this edge.
