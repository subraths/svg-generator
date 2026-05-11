from typing import Dict, Any


def feedback_to_instructions(feedback: Dict[str, Any]) -> str:
    """
    Convert vision feedback JSON into explicit fix instructions.
    Keeps fixes narrow and specific.
    """
    if not feedback:
        return ""

    if feedback.get("pass") is True:
        return "No fixes required."

    issues = feedback.get("issues", [])
    if not issues:
        return "Fix any visual issues detected by the critic."

    lines = [
        "Fix the following issues in the SVG (do not change layout unless required):"
    ]
    for i, issue in enumerate(issues, start=1):
        itype = issue.get("type", "unknown")
        detail = issue.get("detail", "")
        lines.append(f"{i}. [{itype}] {detail}")

    return "\n".join(lines)
