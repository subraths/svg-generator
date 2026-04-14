import json
from src.config import MODEL_NAME, CANVAS_W, CANVAS_H


PLANNER_SCHEMA_HINT = {
    "diagram_type": "flow|architecture|cycle|anatomy",
    "title": "string",
    "nodes": [
        {
            "id": "snake_case_id",
            "label": "short label",
            "x": 100,
            "y": 100,
            "w": 180,
            "h": 70,
        }
    ],
    "edges": [{"from": "node_id", "to": "node_id", "label": "optional short text"}],
}


def _extract_json(text: str) -> str:
    t = text.strip()
    t = t.replace("```json", "").replace("```", "").strip()
    return t


def generate_layout_plan(client, topic: str, min_nodes: int = 6) -> dict:
    system_prompt = f"""You are a diagram planner.
Return ONLY valid JSON (no markdown).

Canvas: width={CANVAS_W}, height={CANVAS_H}
Use grid-aligned coordinates (multiples of 20).
Avoid overlaps. Keep at least 20px spacing between node boxes.
All nodes must stay within canvas bounds.

Output schema:
{json.dumps(PLANNER_SCHEMA_HINT, indent=2)}
"""

    user_prompt = (
        f"Create a layout plan JSON for topic: {topic}\n"
        f"Minimum nodes: {min_nodes}\n"
        f"Include meaningful educational structure and correct directional edges."
    )

    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    raw = resp.choices[0].message.content
    plan_text = _extract_json(raw)

    plan = json.loads(plan_text)

    # Minimal guardrails
    if "nodes" not in plan or "edges" not in plan:
        raise ValueError("Planner output missing 'nodes' or 'edges'.")
    if len(plan["nodes"]) < min_nodes:
        raise ValueError(
            f"Planner returned too few nodes: {len(plan['nodes'])} < {min_nodes}"
        )

    return plan
