from __future__ import annotations

from enum import Enum
from typing import List
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiagramType(str, Enum):
    pipeline = "pipeline"
    hierarchy = "hierarchy"
    cycle = "cycle"
    comparison = "comparison"
    network = "network"


class SVGNode(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    x: float
    y: float
    w: float = 180
    h: float = 70


class SVGEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_node: str = Field(alias="from", min_length=1)
    to_node: str = Field(alias="to", min_length=1)
    label: str = ""


class Subtopic(BaseModel):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    parent_id: Optional[str] = None
    bullet_points: List[str] = Field(default_factory=list)


class NarrationSegment(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class SyncSegment(BaseModel):
    id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    audio_chunk: str

    @field_validator("end_ms")
    @classmethod
    def _end_after_start(cls, v: int, info):
        start = info.data.get("start_ms", 0)
        if v < start:
            raise ValueError("end_ms must be >= start_ms")
        return v


class LessonGraph(BaseModel):
    diagram_type: DiagramType
    title: str = Field(min_length=1)
    svg_nodes: List[SVGNode]
    svg_edges: List[SVGEdge]
    subtopics: List[Subtopic]
    narration_order: List[str]
    narration_segments: List[NarrationSegment]
    sync_map: List[SyncSegment] = Field(default_factory=list)


class LessonBundle(BaseModel):
    lesson_id: str
    lesson: LessonGraph
    svg_path: str
    audio_base_path: str


class GenerateLessonRequest(BaseModel):
    topic: str = Field(min_length=2)
    difficulty: str = "beginner"
    use_llm: bool = True
