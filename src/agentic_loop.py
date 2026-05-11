from typing import Tuple, Optional, Dict, Any

import cairosvg

from src.groq_pool import GroqClientPool
from src.generator import (
    generate_svg_with_groq,
    build_system_prompt_from_plan,
    build_user_prompt_from_plan,
)
from src.validator import validate_svg
from src.vision_feedback import get_vision_feedback
from src.utils import save_file, save_json


def render_svg_to_png(svg_text: str, png_path: str) -> None:
    """
    Convert SVG text to PNG file on disk.
    This PNG is then sent to the vision model for critique.
    """
    cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), write_to=png_path)


def generate_with_agentic_feedback(
    pool: GroqClientPool,
    topic: str,
    plan: dict,
    max_iters: int = 3,
    out_base: str = "agentic",
) -> Tuple[str, Dict[str, Any]]:
    """
    Iterative loop:
      1) Generate SVG from plan
      2) Validate SVG XML
      3) Convert to PNG
      4) Ask vision model for critique
      5) Feed critique back into generator prompt
    Stop when critique says PASS or max_iters reached.

    Returns: (best_svg_text, report)
    """
    system_prompt = build_system_prompt_from_plan()

    best_svg = ""
    last_feedback: Optional[dict] = None
    history = []

    for i in range(1, max_iters + 1):
        # Build user prompt with optional feedback instructions.
        user_prompt = build_user_prompt_from_plan(topic, plan, feedback=last_feedback)

        # Generate SVG with Groq.
        svg_text = generate_svg_with_groq(pool, system_prompt, user_prompt)

        # Validate SVG before any PNG conversion.
        validation = validate_svg(svg_text)
        if not validation.get("xml_valid"):
            # Save invalid SVG for debugging and retry this iteration.
            svg_path = f"svg/{out_base}_iter{i}_invalid.svg"
            save_file(svg_path, svg_text)

            history.append(
                {
                    "iteration": i,
                    "svg_path": svg_path,
                    "png_path": None,
                    "feedback": None,
                    "validation": validation,
                }
            )
            # Move to next iteration without vision critique.
            last_feedback = {
                "pass": False,
                "issues": [{"type": "xml", "detail": "Invalid SVG XML"}],
                "summary": "SVG XML invalid; regenerate with strict XML correctness.",
            }
            continue

        # Only if XML is valid proceed to PNG + vision critique.
        svg_path = f"svg/{out_base}_iter{i}.svg"
        save_file(svg_path, svg_text)

        png_path = f"img/{out_base}_iter{i}.png"
        render_svg_to_png(svg_text, png_path)

        # Ask vision model for critique.
        feedback = get_vision_feedback(png_path)

        history.append(
            {
                "iteration": i,
                "svg_path": svg_path,
                "png_path": png_path,
                "feedback": feedback,
                "validation": validation,
            }
        )

        best_svg = svg_text
        last_feedback = feedback

        # Stop early if vision model approves.
        if feedback.get("pass") is True:
            break

    report = {
        "topic": topic,
        "iterations": len(history),
        "history": history,
        "final_feedback": last_feedback,
    }

    # Save report for traceability.
    save_json(f"reports/{out_base}_agentic_report.json", report, "agentic_report")

    return best_svg, report
