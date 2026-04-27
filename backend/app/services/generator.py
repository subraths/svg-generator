from app.schemas import ConceptGraph, Concept, Relationship, Subtopic
from app.services.classifier import classify_topic
from app.services.templates import TEMPLATES
from app.services.validator import validate_and_repair_graph


def generate_graph_for_topic(topic: str) -> ConceptGraph:
    diagram_type = classify_topic(topic)
    _template_hint = TEMPLATES[diagram_type]

    draft = ConceptGraph(
        title=topic,
        type=diagram_type,
        concepts=[
            Concept(id="input", label="Input"),
            Concept(id="process", label="Process"),
            Concept(id="output", label="Output"),
        ],
        relationships=[
            Relationship(from_node="input", to_node="process", type="leads_to"),
            Relationship(from_node="process", to_node="output", type="leads_to"),
        ],
        subtopics=[Subtopic(id="sub-1", label="Edge cases")],
        narration_order=[
            "input",
            "process",
            "output",
            "sub-1",
        ],  # validator will clean invalid IDs.
    )

    # Always return a validated graph to keep downstream logic stable.
    return validate_and_repair_graph(draft)
