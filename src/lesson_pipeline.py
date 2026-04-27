from __future__ import annotations

import json
import math
import os
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

try:
    from elevenlabs.client import ElevenLabs
except Exception:  # pragma: no cover - optional during local setup
    ElevenLabs = None

DIAGRAM_TYPES = [t.value for t in DiagramType]
MAX_NODES = 10
MAX_SUBTOPICS = 16
AUDIO_SEGMENT_RE = re.compile(r"^segment_[0-9]+\.wav$")

MIN_WORDS_FOR_TIMING = 4
MIN_SEGMENT_DURATION_MS = 1800
MS_PER_WORD = 340

ELEVENLABS_SAMPLE_RATE = 22050
ELEVENLABS_OUTPUT_FORMAT = "pcm_22050"
DEFAULT_ELEVENLABS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"



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



def _has_placeholder_content(items: list[dict[str, Any]]) -> bool:
    patterns = [
        r"^component\s+[a-z0-9]+$",
        r"^node\s*[0-9]+$",
        r"^item\s*[0-9]+$",
        r"^step\s*[0-9]+$",
        r"^topic\s*[0-9]+$",
    ]
    for item in items:
        label = str(item.get("label", "")).strip().lower()
        if not label:
            return True
        if any(re.match(p, label) for p in patterns):
            return True
    return False



def classify_diagram_type(
    topic: str, pool: GroqClientPool | None, use_llm: bool = True
) -> DiagramType:
    if use_llm and pool is not None:
        try:
            data = _llm_json(
                pool,
                """You are an educational diagram classifier.
Return strictly JSON with keys: diagram_type, confidence, rationale.
Allowed diagram_type values only: pipeline, hierarchy, cycle, comparison, network.
No markdown or extra keys.
""",
                (
                    f"Topic: {topic}\n"
                    "Classify this topic by explanatory structure only, not by domain buzzwords.\n"
                    "Return: {\"diagram_type\":\"...\",\"confidence\":0.0-1.0,\"rationale\":\"short\"}"
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
        DiagramType.pipeline: "Use linear left-to-right stages, no cycles, 5-8 nodes.",
        DiagramType.hierarchy: "Use parent-child decomposition, 2-3 depth levels, 5-8 nodes.",
        DiagramType.cycle: "Use a true loop with named transitions and at least one feedback edge.",
        DiagramType.comparison: "Use two contrasting branches plus shared criteria/outcomes.",
        DiagramType.network: "Use a hub-and-spoke or multi-cluster concept map with meaningful links.",
    }
    return templates[diagram_type]


def generate_explanation(
    topic: str,
    difficulty: str,
    pool: GroqClientPool | None,
    use_llm: bool,
) -> dict[str, Any]:
    if use_llm and pool is not None:
        try:
            data = _llm_json(
                pool,
                """You are an educational explainer.
Return JSON only with keys:
{
  "overview": "2-4 sentence explanation grounded in the topic",
  "key_points": ["point 1", "point 2", "point 3"]
}
No placeholders.
""",
                (
                    f"Topic: {topic}\n"
                    f"Difficulty: {difficulty}\n"
                    "Use practical terminology and causal relationships."
                ),
            )
            if isinstance(data, dict) and isinstance(data.get("overview"), str):
                points = data.get("key_points", [])
                if not isinstance(points, list):
                    points = []
                return {
                    "overview": data["overview"].strip(),
                    "key_points": [str(p).strip() for p in points if str(p).strip()],
                }
        except Exception:
            pass
    return {
        "overview": (
            f"{topic} can be understood as an interacting set of concepts where each stage "
            "influences downstream outcomes and trade-offs."
        ),
        "key_points": [
            "Identify the core mechanism first.",
            "Track dependencies between major components.",
            "Validate outcomes with observable signals.",
        ],
    }


def _fallback_graph(topic: str, diagram_type: DiagramType) -> dict[str, Any]:
    title = topic.title()
    if diagram_type == DiagramType.pipeline:
        labels = [
            "Input acquisition",
            "Preprocessing",
            "Core transformation",
            "Quality validation",
            "Output delivery",
            "Monitoring feedback",
        ]
    elif diagram_type == DiagramType.hierarchy:
        labels = [
            f"{title} overview",
            "Foundational layer",
            "Control layer",
            "Execution layer",
            "Observation layer",
            "Improvement loop",
        ]
    elif diagram_type == DiagramType.cycle:
        labels = [
            "Initiation",
            "Build-up",
            "Peak activity",
            "Release",
            "Recovery",
            "Re-entry trigger",
        ]
    elif diagram_type == DiagramType.comparison:
        labels = [
            "Approach A",
            "Approach B",
            "Strength profile",
            "Risk profile",
            "Best-fit context",
            "Decision rule",
        ]
    else:
        labels = [
            f"{title} core",
            "Inputs",
            "Mechanisms",
            "Dependencies",
            "Outcomes",
            "Failure points",
        ]

    nodes = [{"id": f"node_{i+1}", "label": label} for i, label in enumerate(labels)]

    edges: list[dict[str, str]] = []
    if diagram_type == DiagramType.cycle:
        for i in range(len(nodes)):
            edges.append(
                {
                    "from_node": nodes[i]["id"],
                    "to_node": nodes[(i + 1) % len(nodes)]["id"],
                    "label": "next phase",
                }
            )
    elif diagram_type == DiagramType.hierarchy:
        for i in range(1, len(nodes)):
            edges.append(
                {
                    "from_node": nodes[0]["id"],
                    "to_node": nodes[i]["id"],
                    "label": "contains",
                }
            )
    else:
        for i in range(len(nodes) - 1):
            edges.append(
                {
                    "from_node": nodes[i]["id"],
                    "to_node": nodes[i + 1]["id"],
                    "label": "leads to",
                }
            )

    subtopics: list[dict[str, Any]] = []
    for node in nodes:
        sid = f"sub_{node['id']}"
        subtopics.append(
            {
                "id": sid,
                "parent_id": node["id"],
                "label": f"{node['label']} explanation",
                "explanation": f"How {node['label'].lower()} influences {topic} in practical settings.",
                "bullet_points": [
                    f"Key signal: {node['label'].lower()} affects reliability.",
                    f"Checkpoint: validate {node['label'].lower()} with an observable metric.",
                ],
            }
        )

    return {
        "title": title,
        "svg_nodes": nodes,
        "svg_edges": edges,
        "subtopics": subtopics,
    }



def _layout_nodes(
    diagram_type: DiagramType, nodes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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
            node.update(
                {
                    "x": cx + r * math.cos(ang),
                    "y": cy + r * math.sin(ang),
                    "w": 160,
                    "h": 64,
                }
            )
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



def generate_concept_graph(
    topic: str,
    diagram_type: DiagramType,
    explanation: dict[str, Any],
    pool: GroqClientPool | None,
    use_llm: bool,
) -> dict[str, Any]:
    if use_llm and pool is not None:
        for attempt in range(2):
            try:
                system = f"""You generate high-quality educational concept graph JSON.
Return JSON only, no markdown.
Avoid placeholders like 'Component A' / 'Node 1' / 'Step 1'.
Every label and explanation must be domain-specific for the topic.

Required schema:
{{
  "title": "string",
  "svg_nodes": [{{"id": "snake_case", "label": "domain-specific"}}],
  "svg_edges": [{{"from": "node_id", "to": "node_id", "label": "relationship"}}],
  "subtopics": [{{
    "id": "snake_case",
    "parent_id": "node_id",
    "label": "concise subtitle",
    "explanation": "2-3 sentence educational explanation",
    "bullet_points": ["fact 1", "fact 2"]
  }}]
}}
"""
                user = (
                    f"Topic: {topic}\n"
                    f"Explanation overview: {explanation.get('overview', '')}\n"
                    f"Key points: {json.dumps(explanation.get('key_points', []))}\n"
                    f"Diagram type: {diagram_type.value}\n"
                    f"Rules: {_template_instructions(diagram_type)}\n"
                    "Use 5-8 nodes and up to 12 edges.\n"
                    "Create at least one subtopic for each node.\n"
                    "Subtopics must reference valid node ids via parent_id.\n"
                    "Explain mechanisms, trade-offs, and practical cues.\n"
                    "If uncertain, still produce best educational estimate with concrete terminology."
                )
                graph = _llm_json(pool, system, user)
                if {"title", "svg_nodes", "svg_edges", "subtopics"}.issubset(graph):
                    if attempt == 0 and _has_placeholder_content(graph.get("svg_nodes", [])):
                        continue
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
                """You write concise educational narration.
Return JSON only: {"narration_segments":[{"id":"...","text":"..."}]}
One segment per node and one segment per subtopic.
Narration must follow pedagogical order: foundations -> mechanism -> implications.
""",
                (
                    f"Difficulty level: {difficulty}\n"
                    f"Topic: {topic}\n"
                    f"Graph: {json.dumps(graph)}\n"
                    "Keep each segment 1-2 sentences and avoid repetition."
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
                "text": f"At {difficulty} level, {node['label']} is a critical concept inside {topic}.",
            }
        )
    for sub in graph.get("subtopics", []):
        points = "; ".join(sub.get("bullet_points", [])[:2])
        text = f"{sub['explanation']}"
        if points:
            text += f" Key points: {points}."
        segments.append({"id": sub["id"], "text": text})
    return segments



def _build_sync_map_from_durations(
    segment_durations: list[tuple[str, int, str]],
) -> list[dict[str, Any]]:
    sync = []
    cursor = 0
    for seg_id, duration_ms, audio_chunk in segment_durations:
        dur = max(MIN_SEGMENT_DURATION_MS, duration_ms)
        sync.append(
            {
                "id": seg_id,
                "start_ms": cursor,
                "end_ms": cursor + dur,
                "audio_chunk": audio_chunk,
            }
        )
        cursor += dur
    return sync



def _estimated_sync_map(segments: list[dict[str, str]]) -> list[dict[str, Any]]:
    cursor = 0
    output: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        words = max(MIN_WORDS_FOR_TIMING, len(seg["text"].split()))
        dur = max(MIN_SEGMENT_DURATION_MS, words * MS_PER_WORD)
        output.append(
            {
                "id": seg["id"],
                "start_ms": cursor,
                "end_ms": cursor + dur,
                "audio_chunk": f"segment_{i}.wav",
            }
        )
        cursor += dur
    return output



def _graph_checks(graph: LessonGraph) -> list[str]:
    errors: list[str] = []

    if len(graph.svg_nodes) == 0:
        errors.append("svg_nodes cannot be empty")
    if len(graph.svg_nodes) > MAX_NODES:
        errors.append(f"too many nodes: {len(graph.svg_nodes)} > {MAX_NODES}")
    if len(graph.subtopics) > MAX_SUBTOPICS:
        errors.append(f"too many subtopics: {len(graph.subtopics)} > {MAX_SUBTOPICS}")

    ids = {n.id for n in graph.svg_nodes}
    sub_ids = {s.id for s in graph.subtopics}

    for sub in graph.subtopics:
        if sub.parent_id and sub.parent_id not in ids:
            errors.append(f"subtopic {sub.id} has unknown parent_id: {sub.parent_id}")

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
        seen = {start}
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

    allowed_narration_ids = ids | sub_ids
    bad_narration_ids = [nid for nid in narration_ids if nid not in allowed_narration_ids]
    if bad_narration_ids:
        errors.append(f"narration has unknown ids: {bad_narration_ids}")

    if any(seg.end_ms <= seg.start_ms for seg in graph.sync_map):
        errors.append("sync_map contains invalid duration")

    return errors



def _simplify_graph(raw: dict[str, Any]) -> dict[str, Any]:
    nodes = raw.get("svg_nodes", [])[:MAX_NODES]
    node_ids = {n.get("id") for n in nodes}
    edges = [
        e
        for e in raw.get("svg_edges", [])
        if (e.get("from") or e.get("from_node")) in node_ids
        and (e.get("to") or e.get("to_node")) in node_ids
    ]
    if not edges and len(nodes) >= 2:
        edges = [
            {
                "from_node": nodes[i]["id"],
                "to_node": nodes[i + 1]["id"],
                "label": "related",
            }
            for i in range(len(nodes) - 1)
        ]

    subtopics = [
        s
        for s in raw.get("subtopics", [])
        if s.get("parent_id") in node_ids or not s.get("parent_id")
    ][:MAX_SUBTOPICS]

    if not subtopics:
        subtopics = [
            {
                "id": f"sub_{n['id']}",
                "parent_id": n["id"],
                "label": f"{n['label']} details",
                "explanation": f"Practical explanation for {n['label'].lower()}.",
                "bullet_points": [
                    f"Observe {n['label'].lower()} through measurable indicators.",
                    f"Relate {n['label'].lower()} to end outcomes.",
                ],
            }
            for n in nodes[: min(6, len(nodes))]
        ]

    raw["svg_nodes"] = nodes
    raw["svg_edges"] = edges
    raw["subtopics"] = subtopics
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



def _write_pcm_as_wav(target: Path, pcm_bytes: bytes, sample_rate: int = ELEVENLABS_SAMPLE_RATE):
    with wave.open(str(target), "wb") as wavf:
        wavf.setnchannels(1)
        wavf.setsampwidth(2)
        wavf.setframerate(sample_rate)
        wavf.writeframes(pcm_bytes)



def _duration_ms_from_pcm_bytes(pcm_bytes: bytes, sample_rate: int = ELEVENLABS_SAMPLE_RATE) -> int:
    samples = len(pcm_bytes) / 2.0
    return max(1, int((samples / sample_rate) * 1000))



def synthesize_audio_segments(
    narration_segments: list[dict[str, str]], output_dir: Path
) -> list[tuple[str, int, str]]:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("ELEVEN_LABS_TTS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVEN_LABS_TTS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID).strip()
    model_id = os.getenv("ELEVEN_LABS_TTS_MODEL_ID", DEFAULT_ELEVENLABS_MODEL_ID).strip()

    if api_key and len(api_key) < 16:
        raise ValueError(
            "ELEVEN_LABS_TTS_API_KEY appears invalid (must be at least 16 characters)."
        )

    if api_key and ElevenLabs is not None:
        client = ElevenLabs(api_key=api_key)
        results: list[tuple[str, int, str]] = []

        for i, seg in enumerate(narration_segments):
            audio_chunk = f"segment_{i}.wav"
            if not AUDIO_SEGMENT_RE.fullmatch(audio_chunk):
                raise ValueError(f"Invalid audio chunk name: {audio_chunk}")
            target = (output_dir / audio_chunk).resolve()
            if not target.is_relative_to(output_dir):
                raise ValueError("Audio chunk path escapes lesson audio directory")

            audio_stream = client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=model_id,
                output_format=ELEVENLABS_OUTPUT_FORMAT,
                text=seg["text"],
            )
            pcm_bytes = b"".join(audio_stream)
            if not pcm_bytes:
                raise ValueError("ElevenLabs returned empty audio payload")
            _write_pcm_as_wav(target, pcm_bytes)
            duration_ms = _duration_ms_from_pcm_bytes(pcm_bytes)
            results.append((seg["id"], duration_ms, audio_chunk))
        return results

    # fallback for local/dev environments when ELEVEN_LABS_TTS_API_KEY is not set
    results = []
    for i, seg in enumerate(narration_segments):
        audio_chunk = f"segment_{i}.wav"
        target = (output_dir / audio_chunk).resolve()
        if not target.is_relative_to(output_dir):
            raise ValueError("Audio chunk path escapes lesson audio directory")

        words = max(MIN_WORDS_FOR_TIMING, len(seg["text"].split()))
        duration_ms = max(MIN_SEGMENT_DURATION_MS, words * MS_PER_WORD)
        _tone_wav(target, duration_ms, freq=220 + (i * 25))
        results.append((seg["id"], duration_ms, audio_chunk))
    return results



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



def _to_svg_json_payload(raw: dict[str, Any], diagram_type: DiagramType) -> dict[str, Any]:
    edges = []
    for e in raw.get("svg_edges", []):
        edges.append(
            {
                "from": e.get("from") or e.get("from_node"),
                "to": e.get("to") or e.get("to_node"),
                "label": e.get("label", ""),
            }
        )
    return {
        "title": raw.get("title", ""),
        "diagram_type": diagram_type.value,
        "svg_nodes": raw.get("svg_nodes", []),
        "svg_edges": edges,
        "subtopics": raw.get("subtopics", []),
    }


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
    explanation = generate_explanation(
        topic=topic,
        difficulty=difficulty,
        pool=pool,
        use_llm=use_llm,
    )
    graph = generate_concept_graph(
        topic,
        diagram_type,
        explanation=explanation,
        pool=pool,
        use_llm=use_llm,
    )
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
    graph["sync_map"] = _estimated_sync_map(narration_segments)

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
                {
                    "id": n["id"],
                    "text": f"At {difficulty} level, {n['label']} is important in {topic}.",
                }
                for n in graph.get("svg_nodes", [])
            ]

        graph["narration_segments"] = filtered_narration
        graph["narration_order"] = [s["id"] for s in filtered_narration]
        graph["sync_map"] = _estimated_sync_map(filtered_narration)
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

    audio_meta = synthesize_audio_segments(graph["narration_segments"], audio_dir)
    graph["sync_map"] = _build_sync_map_from_durations(audio_meta)
    lesson = _to_lesson_graph(graph, diagram_type=diagram_type)

    svg_path = lesson_dir / "diagram.svg"
    render_lesson_svg(lesson, svg_path)

    lesson_json = lesson.model_dump(by_alias=True)
    svg_json = _to_svg_json_payload(graph, diagram_type=diagram_type)
    (lesson_dir / "lesson.json").write_text(
        json.dumps(
            {
                "lesson_id": lesson_id,
                "explanation": explanation.get("overview", ""),
                "svg_json": svg_json,
                "lesson": lesson_json,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return LessonBundle(
        lesson_id=lesson_id,
        lesson=lesson,
        svg_path=str(svg_path),
        audio_base_path=str(audio_dir),
        explanation=explanation.get("overview", ""),
        svg_json=svg_json,
    )
