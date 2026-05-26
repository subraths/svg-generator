import xml.etree.ElementTree as ET


def collect_allowed_highlight_ids(plan: dict | None, svg_text: str) -> list[str]:
    ordered_ids = []
    seen = set()

    if plan and isinstance(plan.get("nodes"), list):
        for node in plan["nodes"]:
            node_id = node.get("id") if isinstance(node, dict) else None
            if isinstance(node_id, str) and node_id and node_id not in seen:
                seen.add(node_id)
                ordered_ids.append(node_id)

    root = ET.fromstring(svg_text)
    for el in root.iter():
        svg_id = el.attrib.get("id")
        if isinstance(svg_id, str) and svg_id and svg_id not in seen:
            seen.add(svg_id)
            ordered_ids.append(svg_id)

    return ordered_ids


def build_explanation_plan(
    lesson_title: str, highlight_ids: list[str], learning_goals: list[str] | None = None
) -> dict:
    segments = []
    for idx, target_id in enumerate(highlight_ids, start=1):
        seg_id = f"seg_{idx:02d}"
        segments.append(
            {
                "seg_id": seg_id,
                "text": f"Focus on {target_id.replace('_', ' ')} in this diagram.",
                "highlights": [target_id],
            }
        )

    return {
        "lesson_title": lesson_title,
        "learning_goals": learning_goals or [],
        "segments": segments,
    }


def validate_explanation_plan(
    explanation_plan: dict, allowed_highlight_ids: list[str]
) -> list[str]:
    errors = []
    segments = explanation_plan.get("segments")
    if not isinstance(segments, list) or not segments:
        return ["Explanation plan must contain at least one segment."]

    allowed = set(allowed_highlight_ids)
    seg_ids = []
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict):
            errors.append(f"segments[{i}] must be an object.")
            continue

        seg_id = segment.get("seg_id")
        if not isinstance(seg_id, str) or not seg_id.strip():
            errors.append(f"segments[{i}].seg_id must be a non-empty string.")
        else:
            seg_ids.append(seg_id)

        text = segment.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"segments[{i}].text must be non-empty.")

        highlights = segment.get("highlights")
        if not isinstance(highlights, list) or not highlights:
            errors.append(f"segments[{i}].highlights must be a non-empty array.")
            continue

        for highlight_id in highlights:
            if highlight_id not in allowed:
                errors.append(
                    f"segments[{i}].highlights references unknown id '{highlight_id}'."
                )

    if len(seg_ids) != len(set(seg_ids)):
        errors.append("Segment IDs must be unique.")

    return errors
