"""Unit tests for the P1 graph-extraction sanitization, canonicalization, and
provenance logic in ingestion_worker/graph_jobs.py.

These are pure-function tests (no Neo4j/LLM), covering the safety invariant that
replaced the removed ALLOWED_REL_TYPES allow-list plus the cross-window merge.
"""

from backend.ingestion_worker.graph_jobs import (
    _norm_node_type,
    _norm_rel_type,
    _canonical_tag,
    _fact_id,
    _window,
    _merge_extractions,
    DEFAULT_NODE_TYPE,
    DEFAULT_REL_TYPE,
)


class TestRelTypeSanitization:
    def test_backtick_is_stripped(self):
        # The core injection vector: a backtick must never survive into the label.
        assert "`" not in _norm_rel_type("USES`")
        assert "`" not in _norm_rel_type("a`]->(x)<-[:PWN")

    def test_cypher_breakout_payload_neutralized(self):
        payload = "REL`]->() DETACH DELETE n //"
        out = _norm_rel_type(payload)
        assert all(c.isalnum() or c == "_" for c in out)
        assert out.isupper() or out.replace("_", "").isdigit() or "_" in out

    def test_normal_types_preserved(self):
        assert _norm_rel_type("depends on") == "DEPENDS_ON"
        assert _norm_rel_type("PART-OF") == "PART_OF"
        assert _norm_rel_type("feeds_into") == "FEEDS_INTO"

    def test_empty_falls_back_to_default(self):
        assert _norm_rel_type("") == DEFAULT_REL_TYPE
        assert _norm_rel_type(None) == DEFAULT_REL_TYPE
        # A string of only illegal chars sanitizes to empty -> default.
        assert _norm_rel_type("`~!@#") == DEFAULT_REL_TYPE

    def test_only_allowed_charclass(self):
        import re
        for candidate in ["Foo Bar", "x-y-z", "A`B", "语言", "n)-[:X]-("]:
            out = _norm_rel_type(candidate)
            assert re.fullmatch(r"[A-Z0-9_]+", out), out


class TestNodeTypeSanitization:
    def test_backtick_stripped_and_lowercased(self):
        out = _norm_node_type("Component`")
        assert "`" not in out
        assert out == out.lower()

    def test_normal_types(self):
        assert _norm_node_type("Algorithm") == "algorithm"
        assert _norm_node_type("failure mode") == "failure_mode"

    def test_empty_default(self):
        assert _norm_node_type("") == DEFAULT_NODE_TYPE
        assert _norm_node_type("###") == DEFAULT_NODE_TYPE

    def test_only_allowed_charclass(self):
        import re
        for candidate in ["Foo Bar", "A`B", "n)-[:X]"]:
            out = _norm_node_type(candidate)
            assert re.fullmatch(r"[a-z0-9_]+", out), out


class TestCanonicalTagAndFactId:
    def test_canonical_tag_casefold_and_whitespace(self):
        assert _canonical_tag("  P-101A ") == _canonical_tag("p-101a")
        assert _canonical_tag("Pump   Assembly") == _canonical_tag("pump assembly")

    def test_fact_id_deterministic(self):
        a = _fact_id("doc1", "P-101A", "FEEDS", "TANK-1")
        b = _fact_id("doc1", "P-101A", "FEEDS", "TANK-1")
        assert a == b

    def test_fact_id_varies_with_inputs(self):
        base = _fact_id("doc1", "A", "R", "B")
        assert base != _fact_id("doc2", "A", "R", "B")
        assert base != _fact_id("doc1", "A", "R2", "B")
        assert base != _fact_id("doc1", "A", "R", "C")


class TestWindow:
    def test_windows_cover_all_items(self):
        items = [str(i) for i in range(25)]
        windows = _window(items, 10)
        assert len(windows) == 3
        assert sum(len(w) for w in windows) == 25
        assert [x for w in windows for x in w] == items

    def test_window_size_floor(self):
        assert _window(["a", "b"], 0) == [["a"], ["b"]]


class TestMergeExtractions:
    def test_entity_dedup_keeps_richest_description(self):
        parts = [
            {"entities": [{"tag": "P-101A", "name": "Pump", "type": "component", "description": "short"}],
             "relationships": []},
            {"entities": [{"tag": "p-101a", "name": "Pump A", "type": "component",
                           "description": "a much longer and richer description of the pump"}],
             "relationships": []},
        ]
        merged = _merge_extractions(parts)
        assert len(merged["entities"]) == 1
        ent = merged["entities"][0]
        assert ent["description"] == "a much longer and richer description of the pump"

    def test_relationship_dedup_takes_max_confidence(self):
        parts = [
            {"entities": [{"tag": "A", "name": "A", "type": "x", "description": ""},
                          {"tag": "B", "name": "B", "type": "x", "description": ""}],
             "relationships": [{"source": "A", "target": "B", "type": "FEEDS", "confidence": 0.5, "description": ""}]},
            {"entities": [],
             "relationships": [{"source": "a", "target": "b", "type": "feeds", "confidence": 0.9,
                                "description": "detailed"}]},
        ]
        merged = _merge_extractions(parts)
        assert len(merged["relationships"]) == 1
        rel = merged["relationships"][0]
        assert rel["confidence"] == 0.9
        assert rel["type"] == "FEEDS"
        assert rel["description"] == "detailed"

    def test_relationship_dropped_when_endpoint_missing(self):
        parts = [
            {"entities": [{"tag": "A", "name": "A", "type": "x", "description": ""}],
             "relationships": [{"source": "A", "target": "GHOST", "type": "FEEDS", "confidence": 0.9}]},
        ]
        merged = _merge_extractions(parts)
        assert merged["relationships"] == []

    def test_malicious_rel_type_sanitized_in_merge(self):
        parts = [
            {"entities": [{"tag": "A", "name": "A", "type": "x", "description": ""},
                          {"tag": "B", "name": "B", "type": "x", "description": ""}],
             "relationships": [{"source": "A", "target": "B", "type": "R`]->() DELETE n",
                                "confidence": 0.9}]},
        ]
        merged = _merge_extractions(parts)
        assert len(merged["relationships"]) == 1
        assert "`" not in merged["relationships"][0]["type"]
