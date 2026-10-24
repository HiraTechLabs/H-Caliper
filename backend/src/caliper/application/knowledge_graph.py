from typing import Any

import yaml


class NoAliasSafeLoader(yaml.SafeLoader):
    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("YAML aliases are not supported in graph files")
        return super().compose_node(parent, index)


def parse_knowledge_graph(content: str) -> tuple[dict[str, Any] | None, list[str]]:
    if len(content.encode("utf-8")) > 128 * 1024:
        return None, ["Graph file exceeds the 128 KiB validation limit."]
    try:
        value = yaml.load(content, Loader=NoAliasSafeLoader)
    except (yaml.YAMLError, RecursionError):
        return None, ["Graph YAML is invalid or uses unsupported aliases."]
    if not isinstance(value, dict):
        return None, ["Graph root must be a mapping."]
    nodes = value.get("nodes")
    edges = value.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return None, ["Graph must contain node and edge lists."]

    errors: list[str] = []

    def add_error(message: str) -> None:
        if len(errors) < 100:
            errors.append(message)

    raw_node_ids = [item.get("id") for item in nodes if isinstance(item, dict)]
    if len(raw_node_ids) != len(nodes) or any(
        not isinstance(item, str) or not item for item in raw_node_ids
    ):
        add_error("Every graph node must have a non-empty string id.")
    node_ids = [item for item in raw_node_ids if isinstance(item, str) and item]
    if len(set(node_ids)) != len(node_ids):
        add_error("Graph node ids must be unique.")
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        for field in ("label", "kind", "status"):
            if field in node and not isinstance(node[field], str):
                add_error(f"Node {index + 1} field {field} must be a string.")
    if errors:
        return None, errors

    known_ids = set(node_ids)
    safe_edges: list[dict[str, str]] = []
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            add_error(f"Edge {index + 1} must be a mapping.")
            return None, errors
        if any(
            not isinstance(edge.get(key), str) or not edge[key]
            for key in ("from", "to", "relation")
        ):
            add_error(f"Edge {index + 1} must define string from, to, and relation fields.")
            return None, errors
        missing = [key for key in ("from", "to") if edge[key] not in known_ids]
        if missing:
            add_error(f"Edge {index + 1} references unknown node(s): {', '.join(missing)}.")
        safe_edges.append({key: edge[key] for key in ("from", "to", "relation")})
    safe_nodes = [
        {key: node[key] for key in ("id", "label", "kind", "status") if key in node}
        for node in nodes
    ]
    return {"nodes": safe_nodes, "edges": safe_edges}, errors
