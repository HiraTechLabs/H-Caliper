from pathlib import Path

from caliper.application.knowledge_graph import parse_knowledge_graph


def test_graph_accepts_valid_nodes_and_edges():
    graph, errors = parse_knowledge_graph(
        "nodes:\n  - {id: api}\n  - {id: db}\nedges:\n  - {from: api, to: db, relation: uses}\n"
    )

    assert graph is not None
    assert errors == []


def test_graph_reports_references_to_unknown_nodes():
    _, errors = parse_knowledge_graph(
        "nodes:\n  - {id: api}\nedges:\n  - {from: api, to: missing, relation: calls}\n"
    )

    assert errors == ["Edge 1 references unknown node(s): to."]


def test_graph_rejects_duplicate_ids_and_unsafe_alias_expansion():
    _, duplicate_errors = parse_knowledge_graph("nodes:\n  - {id: api}\n  - {id: api}\nedges: []\n")
    _, alias_errors = parse_knowledge_graph("nodes: &nodes []\nedges: *nodes\n")

    assert "Graph node ids must be unique." in duplicate_errors
    assert alias_errors == ["Graph YAML is invalid or uses unsupported aliases."]


def test_graph_reports_unhashable_node_ids_without_crashing():
    _, errors = parse_knowledge_graph("nodes:\n  - {id: []}\nedges: []\n")

    assert "Every graph node must have a non-empty string id." in errors


def test_graph_suppresses_unrenderable_structure_and_bounds_diagnostics():
    graph, errors = parse_knowledge_graph("nodes:\n  - invalid-node\nedges: []\n")
    assert graph is None
    assert "Every graph node must have a non-empty string id." in errors

    malformed_edge_graph, edge_errors = parse_knowledge_graph(
        "nodes:\n  - {id: api}\nedges:\n  - {from: [], to: api, relation: calls}\n"
    )
    assert malformed_edge_graph is None
    assert edge_errors == ["Edge 1 must define string from, to, and relation fields."]

    too_large_diagnostics = "nodes:\n  - {id: api}\nedges:\n" + "".join(
        "  - {from: absent, to: api, relation: calls}\n" for _ in range(200)
    )
    _, many_errors = parse_knowledge_graph(too_large_diagnostics)
    assert len(many_errors) == 100


def test_canonical_project_graph_has_no_invalid_references():
    repository_root = Path(__file__).parents[2]
    graph, errors = parse_knowledge_graph(
        (repository_root / ".caliper" / "graph.yaml").read_text(encoding="utf-8")
    )

    assert graph is not None
    assert graph["nodes"]
    assert graph["edges"]
    assert errors == []
