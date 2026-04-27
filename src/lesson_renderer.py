from __future__ import annotations

import math
from pathlib import Path

import svgwrite

from src.lesson_models import LessonGraph, SVGNode

PANEL_W = 280
CANVAS_W = 1200
CANVAS_H = 800


def _safe_svg_output_path(output_path: Path) -> Path:
    safe = output_path.expanduser().resolve()
    if safe.suffix.lower() != ".svg":
        raise ValueError("output_path must be an .svg file")
    return safe


def _node_box(node: SVGNode):
    return (node.x - node.w / 2, node.y - node.h / 2, node.w, node.h)


def _anchor(node: SVGNode, dx: float, dy: float) -> tuple[float, float]:
    if abs(dx) >= abs(dy):
        return (
            (node.x + node.w / 2, node.y)
            if dx >= 0
            else (node.x - node.w / 2, node.y)
        )
    return (
        (node.x, node.y + node.h / 2)
        if dy >= 0
        else (node.x, node.y - node.h / 2)
    )


def _bezier_path(x1: float, y1: float, x2: float, y2: float) -> str:
    dx = x2 - x1
    bend = max(30.0, min(120.0, abs(dx) * 0.35))
    if dx < 0:
        bend = -bend
    c1x = x1 + dx * 0.25
    c2x = x1 + dx * 0.75
    c1y = y1 - bend
    c2y = y2 - bend
    return f"M {x1:.2f} {y1:.2f} C {c1x:.2f} {c1y:.2f}, {c2x:.2f} {c2y:.2f}, {x2:.2f} {y2:.2f}"


def render_lesson_svg(lesson: LessonGraph, output_path: Path) -> str:
    output_path = _safe_svg_output_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dwg = svgwrite.Drawing(
        filename=str(output_path),
        size=(CANVAS_W, CANVAS_H),
        viewBox=f"0 0 {CANVAS_W} {CANVAS_H}",
    )

    dwg.defs.add(
        dwg.style(
            """
            .highlightable { transition: all 0.2s ease; }
            .highlighted { filter: brightness(1.15); stroke: #f59e0b !important; stroke-width: 3 !important; }
            .node-label { pointer-events: none; }
            """
        )
    )

    marker = dwg.marker(
        id="arrow",
        insert=(10, 5),
        size=(10, 10),
        orient="auto",
        markerUnits="strokeWidth",
    )
    marker.add(dwg.path(d="M 0 0 L 10 5 L 0 10 z", fill="#4b5563"))
    dwg.defs.add(marker)

    dwg.add(
        dwg.rect(
            insert=(0, 0),
            size=(PANEL_W, CANVAS_H),
            fill="#f8fafc",
            stroke="#e2e8f0",
        )
    )
    dwg.add(
        dwg.text(
            "Sub-topics",
            insert=(16, 32),
            font_size="18px",
            font_weight="bold",
            fill="#0f172a",
        )
    )

    max_bullets = int((CANVAS_H - 70) / 28)
    visible = lesson.subtopics[:max_bullets]
    for i, sub in enumerate(visible):
        y = 62 + i * 28
        dwg.add(dwg.circle(center=(18, y - 5), r=3, fill="#3b82f6"))
        dwg.add(
            dwg.text(
                sub.label,
                insert=(28, y),
                id=sub.id,
                class_="highlightable",
                font_size="13px",
                fill="#334155",
            )
        )

    if len(lesson.subtopics) > max_bullets:
        rem = len(lesson.subtopics) - max_bullets
        dwg.add(
            dwg.text(
                f"+{rem} more",
                insert=(28, 62 + max_bullets * 28),
                font_size="12px",
                fill="#64748b",
            )
        )

    dwg.add(dwg.line(start=(PANEL_W, 0), end=(PANEL_W, CANVAS_H), stroke="#cbd5e1"))

    shifted_nodes = {
        n.id: SVGNode(
            id=n.id,
            label=n.label,
            x=n.x + PANEL_W,
            y=n.y,
            w=n.w,
            h=n.h,
        )
        for n in lesson.svg_nodes
    }

    for edge in lesson.svg_edges:
        src = shifted_nodes.get(edge.from_node)
        dst = shifted_nodes.get(edge.to_node)
        if src is None or dst is None:
            continue
        dx = dst.x - src.x
        dy = dst.y - src.y
        x1, y1 = _anchor(src, dx, dy)
        x2, y2 = _anchor(dst, -dx, -dy)
        path_d = _bezier_path(x1, y1, x2, y2)

        edge_id = f"edge-{edge.from_node}-{edge.to_node}"
        dwg.add(
            dwg.path(
                d=path_d,
                id=edge_id,
                class_="highlightable",
                stroke="#4b5563",
                stroke_width=2,
                fill="none",
                marker_end="url(#arrow)",
            )
        )

        if edge.label:
            lx = (x1 + x2) / 2
            ly = (y1 + y2) / 2 - 18
            dwg.add(
                dwg.text(
                    edge.label,
                    insert=(lx, ly),
                    text_anchor="middle",
                    font_size="12px",
                    fill="#475569",
                )
            )

    for node in shifted_nodes.values():
        bx, by, bw, bh = _node_box(node)
        group = dwg.g(id=f"group-{node.id}")
        group.add(
            dwg.rect(
                insert=(bx, by),
                size=(bw, bh),
                rx=10,
                ry=10,
                id=node.id,
                class_="highlightable",
                fill="#e0ecff",
                stroke="#2563eb",
                stroke_width=2,
            )
        )
        group.add(
            dwg.text(
                node.label,
                insert=(node.x, node.y + 4),
                text_anchor="middle",
                class_="node-label",
                font_size="14px",
                font_weight="bold",
                fill="#0f172a",
            )
        )
        dwg.add(group)

    dwg.save()
    return output_path.read_text(encoding="utf-8")
