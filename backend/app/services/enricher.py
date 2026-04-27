from app.schemas import (
    ConceptGraph,
    EnrichedGraph,
    EnrichedNodeStyle,
    EnrichedEdgeStyle,
)


def enrich_graph(graph: ConceptGraph) -> EnrichedGraph:
    # Stub heuristic (replace with LLM pass-2 later)

    node_styles = {}
    for i, c in enumerate(graph.concepts):
        if i == 0:
            node_styles[c.id] = EnrichedNodeStyle(importance="high")
        elif i < 3:
            node_styles[c.id] = EnrichedNodeStyle(importance="medium")
        else:
            node_styles[c.id] = EnrichedNodeStyle(importance="low")

    edge_styles = {}
    for r in graph.relationships:
        key = f"{r.from_id}->{r.to_id}"
        semantic = "associative"

        if r.type in ("causes", "leads_to"):
            semantic = "causal"
        elif r.type in ("defines", "contains"):
            semantic = "definitional"
        elif r.type == "compares":
            semantic = "comparative"

        edge_styles[key] = EnrichedEdgeStyle(semantic=semantic)

    return EnrichedGraph(
        graph=graph,
        node_styles=node_styles,
        edge_styles=edge_styles,
    )
