from __future__ import annotations

import json
import math
import re
import struct
import time
import uuid
import wave
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from src.groq_pool import GroqClientPool
from src.lesson_models import (
    DiagramType,
    LessonBundle,
    LessonGraph,
    NarrationSegment,
    SVGEdge,
    SVGNode,
    Subtopic,
    SyncSegment,
)
from src.lesson_renderer import render_lesson_svg

DIAGRAM_TYPES = [t.value for t in DiagramType]
MAX_NODES = 10
MAX_SUBTOPICS = 8
AUDIO_SEGMENT_RE = re.compile(r"^segment_[0-9]+\.wav$")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "topic"


def _extract_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.replace("```json", "").replace("```", "").strip()
    return t


def _safe_join(base: Path, child: str) -> Path:
    decoded = unquote(child or "")
    if decoded != child:
        raise ValueError("Encoded path fragments are not allowed")
    if not re.fullmatch(r"[a-z0-9_-]+", child):
        raise ValueError("Invalid path fragment")
    if "/" in child or "\\" in child or ".." in child:
        raise ValueError("Invalid path fragment")
    base_resolved = base.expanduser().resolve()
    target = (base_resolved / child).resolve()
    if not target.is_relative_to(base_resolved):
        raise ValueError("Path escapes base directory")
    return target


def _llm_json(pool: GroqClientPool, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    resp = pool.chat_completion_with_failover(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content
    return json.loads(_extract_json(raw))


def classify_diagram_type(topic: str, pool: GroqClientPool | None, use_llm: bool = True) -> DiagramType:
    if use_llm and pool is not None:
        try:
            data = _llm_json(
                pool,
                "You classify educational topics. Return JSON only.",
                (
                    "Classify this topic into one of: pipeline, hierarchy, cycle, comparison, network. "
                    f"Topic: {topic}. Return {{\"diagram_type\": \"...\", \"confidence\": 0-1}}"
                ),
            )
            value = str(data.get("diagram_type", "")).strip().lower()
            if value in DIAGRAM_TYPES:
                return DiagramType(value)
        except Exception:
            pass

    t = topic.lower()
    if any(k in t for k in ["vs", "compare", "difference", "between"]):
        return DiagramType.comparison
    if any(k in t for k in ["cycle", "loop", "lifecycle"]):
        return DiagramType.cycle
    if any(k in t for k in ["architecture", "layers", "hierarchy", "stack"]):
        return DiagramType.hierarchy
    if any(k in t for k in ["flow", "process", "pipeline", "steps"]):
        return DiagramType.pipeline
    return DiagramType.network


def _template_instructions(diagram_type: DiagramType) -> str:
    templates = {
        DiagramType.pipeline: "Use linear left-to-right stages, no cycles, 4-7 nodes.",
        DiagramType.hierarchy: "Use root->children structure, max depth 3, no sibling edges.",
        DiagramType.cycle: "Use closed-loop transitions with one optional entry node.",
        DiagramType.comparison: "Use two groups with mirrored properties and contrast labels.",
        DiagramType.network: "Use central concept with connected supporting concepts.",
    }
    return templates[diagram_type]


def _fallback_graph(topic: str, diagram_type: DiagramType) -> dict[str, Any]:
    base_labels = [
        "Core concept",
        "Component A",
        "Component B",
        "Process",
        "Outcome",
        "Applications",
    ]
    nodes = []
    for i, label in enumerate(base_labels):
        nid = f"node_{i+1}"
        nodes.append({"id": nid, "label": label})

    edges = []
    if diagram_type == DiagramType.cycle:
        for i in range(len(nodes)):
            edges.append({"from": nodes[i]["id"], "to": nodes[(i + 1) % len(nodes)]["id"], "label": ""})
    elif diagram_type == DiagramType.hierarchy:
        for i in range(1, len(nodes)):
            edges.append({"from": nodes[0]["id"], "to": nodes[i]["id"], "label": ""})
    elif diagram_type == DiagramType.comparison:
        edges = [
            {"from": "node_1", "to": "node_3", "label": "similarity"},
            {"from": "node_2", "to": "node_4", "label": "contrast"},
            {"from": "node_1", "to": "node_5", "label": "impact"},
            {"from": "node_2", "to": "node_6", "label": "impact"},
        ]
    else:
        for i in range(len(nodes) - 1):
            edges.append({"from": nodes[i]["id"], "to": nodes[i + 1]["id"], "label": ""})

    subtopics = [
        {"id": "sub_history", "label": "Historical context", "explanation": f"How {topic} evolved over time."},
        {"id": "sub_limits", "label": "Limitations", "explanation": f"Common limits and constraints in {topic}."},
        {"id": "sub_examples", "label": "Practical examples", "explanation": f"Real-world examples of {topic}."},
    ]
    return {"title": topic.title(), "svg_nodes": nodes, "svg_edges": edges, "subtopics": subtopics}


def _layout_nodes(diagram_type: DiagramType, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    n = len(nodes)
    if n == 0:
        return nodes

    if diagram_type == DiagramType.pipeline:
        x_step = 850 / max(1, (n - 1))
        for i, node in enumerate(nodes):
            node.update({"x": 80 + i * x_step, "y": 380, "w": 170, "h": 68})
        return nodes

    if diagram_type == DiagramType.hierarchy:
        levels = [nodes[0:1], nodes[1:3], nodes[3:]]
        y = 180
        for level in levels:
            if not level:
                continue
            step = 820 / (len(level) + 1)
            for i, node in enumerate(level):
                node.update({"x": step * (i + 1), "y": y, "w": 170, "h": 68})
            y += 180
        return nodes

    if diagram_type == DiagramType.cycle:
        cx, cy, r = 450, 380, 220
        for i, node in enumerate(nodes):
            ang = (2 * math.pi * i) / n
            node.update({"x": cx + r * math.cos(ang), "y": cy + r * math.sin(ang), "w": 160, "h": 64})
        return nodes

    if diagram_type == DiagramType.comparison:
        left, right = nodes[::2], nodes[1::2]
        for i, node in enumerate(left):
            node.update({"x": 240, "y": 170 + i * 130, "w": 170, "h": 68})
        for i, node in enumerate(right):
            node.update({"x": 660, "y": 170 + i * 130, "w": 170, "h": 68})
        return nodes

    cols = 3
    for i, node in enumerate(nodes):
        row, col = divmod(i, cols)
        node.update({"x": 170 + col * 280, "y": 170 + row * 180, "w": 170, "h": 68})
    return nodes


def generate_concept_graph(topic: str, diagram_type: DiagramType, pool: GroqClientPool | None, use_llm: bool) -> dict[str, Any]:
    if use_llm and pool is not None:
        try:
            system = "You generate educational concept graph JSON. Return JSON only."
            user = (
                f"Topic: {topic}\n"
                f"Diagram type: {diagram_type.value}\n"
                f"Rules: {_template_instructions(diagram_type)}\n"
                "Output keys: title, svg_nodes[{id,label}], svg_edges[{from,to,label}], subtopics[{id,label,explanation}]\n"
                "Keep 4-8 nodes and <=8 edges."
            )
            graph = _llm_json(pool, system, user)
            if {"title", "svg_nodes", "svg_edges", "subtopics"}.issubset(graph):
                return graph
        except Exception:
            pass
    return _fallback_graph(topic, diagram_type)


def generate_narration(
    graph: dict[str, Any],
    topic: str,
    difficulty: str,
    pool: GroqClientPool | None,
    use_llm: bool,
) -> list[dict[str, str]]:
    if use_llm and pool is not None:
        try:
            data = _llm_json(
                pool,
                "You write short educational narration mapped to ids. Return JSON only.",
                (
                    "Given this graph JSON, produce narration_segments array with objects "
                    "{id,text}. One segment per node/subtopic in teaching order. "
                    f"Difficulty level: {difficulty}. "
                    f"Graph: {json.dumps(graph)}"
                ),
            )
            segs = data.get("narration_segments", [])
            if isinstance(segs, list) and segs:
                return segs
        except Exception:
            pass

    segments = []
    for node in graph.get("svg_nodes", []):
        segments.append(
            {
                "id": node["id"],
                "text": f"At {difficulty} level, {node['label']} is a key part of {topic}.",
            }
        )
    for sub in graph.get("subtopics", []):
        segments.append({"id": sub["id"], "text": sub["explanation"]})
    return segments


def build_sync_map(segments: list[dict[str, str]]) -> list[dict[str, Any]]:
    sync = []
    cursor = 0
    for i, seg in enumerate(segments):
        words = max(4, len(seg["text"].split()))
        dur = max(1800, words * 340)
        sync.append(
            {
                "id": seg["id"],
                "start_ms": cursor,
                "end_ms": cursor + dur,
                "audio_chunk": f"segment_{i}.wav",
            }
        )
        cursor += dur
    return sync


def _graph_checks(graph: LessonGraph) -> list[str]:
    errors: list[str] = []

    if len(graph.svg_nodes) == 0:
        errors.append("svg_nodes cannot be empty")
    if len(graph.svg_nodes) > MAX_NODES:
        errors.append(f"too many nodes: {len(graph.svg_nodes)} > {MAX_NODES}")
    if len(graph.subtopics) > MAX_SUBTOPICS:
        errors.append(f"too many subtopics: {len(graph.subtopics)} > {MAX_SUBTOPICS}")

    ids = {n.id for n in graph.svg_nodes}
    for e in graph.svg_edges:
        if e.from_node not in ids:
            errors.append(f"unknown edge source: {e.from_node}")
        if e.to_node not in ids:
            errors.append(f"unknown edge target: {e.to_node}")

    if graph.svg_nodes:
        adj = defaultdict(set)
        for e in graph.svg_edges:
            if e.from_node in ids and e.to_node in ids:
                adj[e.from_node].add(e.to_node)
                adj[e.to_node].add(e.from_node)
        start = graph.svg_nodes[0].id
        seen = set([start])
        q = deque([start])
        while q:
            cur = q.popleft()
            for nxt in adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        if len(seen) != len(ids):
            errors.append("graph has disconnected nodes")

    narration_ids = [s.id for s in graph.narration_segments]
    order_ids = graph.narration_order
    if set(order_ids) != set(narration_ids):
        errors.append("narration_order ids must match narration_segments ids")

    if any(seg.end_ms <= seg.start_ms for seg in graph.sync_map):
        errors.append("sync_map contains invalid duration")

    return errors


def _simplify_graph(raw: dict[str, Any]) -> dict[str, Any]:
    nodes = raw.get("svg_nodes", [])[:MAX_NODES]
    node_ids = {n.get("id") for n in nodes}
    edges = [
        e
        for e in raw.get("svg_edges", [])
        if e.get("from") in node_ids and e.get("to") in node_ids
    ]
    if not edges and len(nodes) >= 2:
        edges = [
            {"from": nodes[i]["id"], "to": nodes[i + 1]["id"], "label": ""}
            for i in range(len(nodes) - 1)
        ]
    raw["svg_nodes"] = nodes
    raw["svg_edges"] = edges
    raw["subtopics"] = raw.get("subtopics", [])[:MAX_SUBTOPICS]
    return raw


def _tone_wav(path: Path, duration_ms: int, freq: float):
    sample_rate = 22050
    amplitude = 9000
    frames = int(sample_rate * (duration_ms / 1000.0))
    with wave.open(str(path), "w") as wavf:
        wavf.setnchannels(1)
        wavf.setsampwidth(2)
        wavf.setframerate(sample_rate)
        for i in range(frames):
            t = i / sample_rate
            value = int(amplitude * math.sin(2 * math.pi * freq * t))
            wavf.writeframes(struct.pack("<h", value))


def synthesize_audio_segments(sync_map: list[SyncSegment], output_dir: Path):
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, seg in enumerate(sync_map):
        if not AUDIO_SEGMENT_RE.fullmatch(seg.audio_chunk):
            raise ValueError(f"Invalid audio chunk name: {seg.audio_chunk}")
        target = (output_dir / seg.audio_chunk).resolve()
        if not target.is_relative_to(output_dir):
            raise ValueError("Audio chunk path escapes lesson audio directory")
        duration = max(300, seg.end_ms - seg.start_ms)
        _tone_wav(target, duration, freq=220 + (i * 25))


def _to_lesson_graph(raw: dict[str, Any], diagram_type: DiagramType) -> LessonGraph:
    nodes = [SVGNode(**n) for n in raw.get("svg_nodes", [])]
    edges = [SVGEdge(**e) for e in raw.get("svg_edges", [])]
    subtopics = [Subtopic(**s) for s in raw.get("subtopics", [])]
    narrations = [NarrationSegment(**s) for s in raw.get("narration_segments", [])]
    sync = [SyncSegment(**s) for s in raw.get("sync_map", [])]

    return LessonGraph(
        diagram_type=diagram_type,
        title=raw.get("title", "Untitled lesson"),
        svg_nodes=nodes,
        svg_edges=edges,
        subtopics=subtopics,
        narration_order=raw.get("narration_order", []),
        narration_segments=narrations,
        sync_map=sync,
    )


def get_pool_if_available() -> GroqClientPool | None:
    try:
        return GroqClientPool.from_env()
    except Exception:
        return None


def generate_lesson(
    topic: str,
    difficulty: str = "beginner",
    use_llm: bool = True,
    base_dir: Path = Path("data/lessons"),
) -> LessonBundle:
    pool = get_pool_if_available() if use_llm else None
    diagram_type = classify_diagram_type(topic, pool=pool, use_llm=use_llm)
    graph = generate_concept_graph(topic, diagram_type, pool=pool, use_llm=use_llm)
    graph = _simplify_graph(graph)

    graph["svg_nodes"] = _layout_nodes(diagram_type, graph.get("svg_nodes", []))

    narration_segments = generate_narration(
        graph,
        topic,
        difficulty=difficulty,
        pool=pool,
        use_llm=use_llm,
    )
    graph["narration_segments"] = narration_segments
    graph["narration_order"] = [s["id"] for s in narration_segments]
    graph["sync_map"] = build_sync_map(narration_segments)

    lesson = _to_lesson_graph(graph, diagram_type=diagram_type)

    checks = _graph_checks(lesson)
    if checks:
        graph = _simplify_graph(graph)
        graph["svg_nodes"] = _layout_nodes(diagram_type, graph.get("svg_nodes", []))
        valid_ids = {n["id"] for n in graph.get("svg_nodes", [])} | {
            s["id"] for s in graph.get("subtopics", [])
        }
        filtered_narration = [s for s in narration_segments if s["id"] in valid_ids]
        if not filtered_narration:
            filtered_narration = [
                {"id": n["id"], "text": f"At {difficulty} level, {n['label']} is important in {topic}."}
                for n in graph.get("svg_nodes", [])
            ]

        graph["narration_segments"] = filtered_narration
        graph["narration_order"] = [s["id"] for s in filtered_narration]
        graph["sync_map"] = build_sync_map(filtered_narration)
        lesson = _to_lesson_graph(graph, diagram_type=diagram_type)
        final_checks = _graph_checks(lesson)
        if final_checks:
            raise ValueError(
                "Lesson graph failed validation after simplification: "
                + "; ".join(final_checks)
            )

    lesson_id = f"{_slug(topic)}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    lesson_dir = _safe_join(base_dir, lesson_id)
    audio_dir = lesson_dir / "audio"
    lesson_dir.mkdir(parents=True, exist_ok=True)

    svg_path = lesson_dir / "diagram.svg"
    render_lesson_svg(lesson, svg_path)

    synthesize_audio_segments(lesson.sync_map, audio_dir)

    lesson_json = lesson.model_dump(by_alias=True)
    (lesson_dir / "lesson.json").write_text(
        json.dumps({"lesson_id": lesson_id, "lesson": lesson_json}, indent=2),
        encoding="utf-8",
    )

    return LessonBundle(
        lesson_id=lesson_id,
        lesson=lesson,
        svg_path=str(svg_path),
        audio_base_path=str(audio_dir),
    )
