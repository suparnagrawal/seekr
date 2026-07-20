from typing import Dict, Any, List
from backend.shared.neo4j_client import get_neo4j_async

async def get_entity_specs(tag: str) -> Dict[str, Any]:
    """Retrieve specifications (properties and related metric nodes) for an entity."""
    driver = get_neo4j_async()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (n:Entity {tag: $tag})
            OPTIONAL MATCH (n)-[r]->(v:Entity)
            RETURN n.name AS name, n.type AS type, n.description AS description,
                   collect({rel: type(r), val: v.tag, desc: r.description}) AS specs
            """,
            tag=tag,
        )
        record = await result.single()
        if not record:
            return {}
            
        specs = {}
        for spec in record["specs"]:
            if spec["rel"]:
                specs[spec["rel"]] = {"value": spec["val"], "description": spec["desc"]}
                
        return {
            "tag": tag,
            "name": record["name"],
            "type": record["type"],
            "description": record["description"],
            "specifications": specs
        }

async def compare_specs(tags: List[str]) -> Dict[str, Dict[str, Any]]:
    """Compare specifications side-by-side for multiple entities."""
    comparison = {}
    for tag in tags:
        comparison[tag] = await get_entity_specs(tag)
    return comparison

async def find_by_type(entity_type: str) -> List[Dict[str, Any]]:
    """Find all entities of a given type."""
    driver = get_neo4j_async()
    async with driver.session() as session:
        result = await session.run(
            "MATCH (n:Entity) WHERE n.type =~ '(?i)' + $type RETURN n.tag AS tag, n.name AS name LIMIT 20",
            type=entity_type
        )
        records = await result.data()
        return records
