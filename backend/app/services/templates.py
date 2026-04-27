from app.schemas import DiagramType

TEMPLATES: dict[DiagramType, str] = {
    "pipeline": "Template: sequential stages, left-to-right, max 6 nodes, no cycles.",
    "hierarchy": "Template: rooted tree, max depth 3, no sibling edges.",
    "cycle": "Template: closed loop, one entry node, transition edges.",
    "comparison": "Template: exactly two groups, each with header + 3-4 properties.",
    "network": "Template: bounded concept network, max 8 nodes, meaningful edge types.",
    "timeline": "Template: chronological sequence with time markers and milestones.",
}
