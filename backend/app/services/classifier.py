from app.schemas import DiagramType


def classify_topic(topic: str) -> DiagramType:
    t = topic.lower()

    if any(k in t for k in ["vs", "compare", "difference", "sql vs", "tcp vs"]):
        return "comparison"
    if any(
        k in t for k in ["lifecycle", "pipeline", "process", "request flow", "steps"]
    ):
        return "pipeline"
    if any(k in t for k in ["architecture", "layers", "hierarchy", "tree", "taxonomy"]):
        return "hierarchy"
    if any(k in t for k in ["cycle", "loop", "scheduling", "feedback"]):
        return "cycle"
    if any(k in t for k in ["history", "timeline", "evolution"]):
        return "timeline"

    return "network"
