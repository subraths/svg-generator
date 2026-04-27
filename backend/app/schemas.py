from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict

NodeImportance = Literal["high", "medium", "low"]
EdgeSemantic = Literal[
    "causal", "definitional", "associative", "comparative", "temporal"
]

DiagramType = Literal[
    "pipeline", "hierarchy", "cycle", "comparison", "network", "timeline"
]


class Concept(BaseModel):
    id: str = Field(..., description="Unique stable ID")
    label: str
    group: Optional[str] = None  # useful for comparison/two-column


class Relationship(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_id: str = Field(..., alias="from_node")
    to_id: str = Field(..., alias="to_node")
    type: Literal["causes", "defines", "contains", "leads_to", "compares", "depends_on"]


class Subtopic(BaseModel):
    id: str
    label: str
    explanation: Optional[str] = None


class ConceptGraph(BaseModel):
    title: str
    type: DiagramType
    concepts: List[Concept]
    relationships: List[Relationship]
    subtopics: List[Subtopic] = []
    narration_order: List[str] = []


class GenerateGraphRequest(BaseModel):
    topic: str


class GenerateGraphResponse(BaseModel):
    graph: ConceptGraph


class EnrichedNodeStyle(BaseModel):
    importance: NodeImportance


class EnrichedEdgeStyle(BaseModel):
    semantic: EdgeSemantic


class EnrichedGraph(BaseModel):
    graph: ConceptGraph
    node_styles: Dict[str, EnrichedNodeStyle]  # key: concept id
    edge_styles: Dict[str, EnrichedEdgeStyle]  # key: "from->to"


class EnrichRequest(BaseModel):
    graph: ConceptGraph


class EnrichResponse(BaseModel):
    enriched: EnrichedGraph
