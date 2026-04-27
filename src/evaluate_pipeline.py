from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from src.generator import build_system_prompt, generate_svg_with_groq
from src.groq_pool import GroqClientPool
from src.lesson_pipeline import generate_lesson, get_pool_if_available
from src.validator import validate_svg

TOPICS = [
    "TCP 3-way handshake",
    "Photosynthesis",
    "Neural network architecture",
    "HTTP request lifecycle",
]


def run_evaluation():
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    rows = []

    pool = get_pool_if_available()

    for topic in TOPICS:
        # Baseline direct SVG
        baseline = {
            "topic": topic,
            "mode": "direct_svg",
            "latency_ms": None,
            "xml_valid": False,
            "error_count": 1,
            "overlap_count": 0,
            "quiz_score": None,
        }
        if pool is not None:
            t0 = time.perf_counter()
            svg = generate_svg_with_groq(
                pool,
                build_system_prompt(topic),
                f"Generate an educational SVG for topic: {topic}",
            )
            t1 = time.perf_counter()
            val = validate_svg(svg)
            baseline.update(
                {
                    "latency_ms": round((t1 - t0) * 1000, 2),
                    "xml_valid": val["xml_valid"],
                    "error_count": len(val["errors"]),
                    "overlap_count": len(val["overlap_pairs"]),
                }
            )
        rows.append(baseline)

        # Structured pipeline
        t0 = time.perf_counter()
        bundle = generate_lesson(topic=topic, use_llm=pool is not None)
        t1 = time.perf_counter()
        svg_text = Path(bundle.svg_path).read_text(encoding="utf-8")
        val = validate_svg(svg_text)
        rows.append(
            {
                "topic": topic,
                "mode": "structured_pipeline",
                "latency_ms": round((t1 - t0) * 1000, 2),
                "xml_valid": val["xml_valid"],
                "error_count": len(val["errors"]),
                "overlap_count": len(val["overlap_pairs"]),
                "quiz_score": None,
            }
        )

    csv_path = reports_dir / f"evaluation_{ts}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "topic",
                "mode",
                "latency_ms",
                "xml_valid",
                "error_count",
                "overlap_count",
                "quiz_score",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "rows": rows,
        "metrics": {
            "structural_validity_rate": round(
                (sum(1 for r in rows if r["xml_valid"]) / len(rows)) * 100, 2
            ),
            "avg_overlap_rate": round(
                sum(r["overlap_count"] for r in rows) / len(rows), 2
            ),
            "avg_latency_ms": round(
                sum((r["latency_ms"] or 0) for r in rows) / len(rows), 2
            ),
            "note": "User comprehension quiz score should be added from human-study results.",
        },
    }

    json_path = reports_dir / f"evaluation_{ts}.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Saved: {csv_path}")
    print(f"Saved: {json_path}")


if __name__ == "__main__":
    run_evaluation()
