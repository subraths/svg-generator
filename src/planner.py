import json
from src.config import MODEL_NAME, CANVAS_W, CANVAS_H
from src.groq_pool import GroqClientPool


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
    "edges": [
        {
            "from": "node_id",
            "to": "node_id",
            "label": "optional short text but try to include",
        }
    ],
}


def _extract_json(text: str) -> str:
    t = text.strip()
    t = t.replace("```json", "").replace("```", "").strip()
    return t


def generate_layout_plan(pool: GroqClientPool, topic: str, min_nodes: int = 6) -> dict:

    with open("edited_samples/photosynthesis.svg", "r") as f:
        example_svg = f.read()

    system_prompt = f"""
        You are an expert SVG diagram PLANNER for an educational tutor.

        You do NOT generate SVG. You generate ONLY a JSON layout plan that will later be converted to SVG.
        Return ONLY valid JSON. No markdown. No comments.

        Hard constraints (MUST FOLLOW):
        - Canvas size is fixed: width={CANVAS_W}, height={CANVAS_H}.
        - Coordinates must be multiples of 20 (grid-aligned).
        - Every node must be fully inside the canvas bounds (including its width/height).
        - No overlaps: maintain >= 20px spacing between node bounding boxes.
        - Text must be readable: prefer short labels that fit inside nodes; use multi-line labels only if schema supports it.
        - IDs must be stable, short, and snake_case. Do NOT use spaces. Do NOT change IDs once assigned.
        - Each node must represent ONE clear concept. Avoid vague nodes like "Other" or "Misc".
        - Edges must be meaningful and directionally correct for the topic (cause→effect, step→next step, input→output).
        - The plan must be self-contained and consistent: every edge source/target must exist.
        - Labels MUST fit inside their node boxes.
        - If a label would be longer than ~18 characters OR more than 2–3 words, you MUST insert line breaks using '\\n'
          so it renders as multiple lines inside the box.
          Example: "Transmission Control Protocol" -> "Transmission\\nControl\\nProtocol"
        - Prefer 1–3 lines per label. Avoid single very long lines.
        - Do NOT use hyphenation. Break on spaces between words.

        Educational quality constraints:
        - Organize the diagram as a teaching flow:
        1) Start/overview node(s)
        2) Core steps/components (main chain)
        3) Supporting concepts (side nodes)
        4) Output/summary node(s)
        - Prefer 2–4 major stages with subcomponents rather than a flat list.
        - Use labels that a learner would understand (avoid jargon unless necessary).
        
        ID convention:
        - Node ids must be noun-like (e.g., "client", "syn_sent"), not "box1".
        - Edge ids should be "from_to" style (e.g., "client_to_server_syn").

        Output must follow this JSON schema exactly:
        {json.dumps(PLANNER_SCHEMA_HINT, indent=2)}
        
        Here is an example SVG: {example_svg}

        Before returning JSON, verify for every node:
        - schema validity
        - grid alignment
        - no overlaps
        - all elements in bounds
        - minimum node count met
        - label has '\\n' inserted if it is long (e.g., > 18 chars or > 3 words)
        - each line is short enough to fit visually
    """

    user_prompt = f"""
        Topic: {topic}

        Requirements:
        - Minimum nodes: {min_nodes}
        - Create a clear educational diagram plan suitable for a narrated tutor.
        - Use concise labels, but include key terms a student should remember.
        - Include directional edges that represent the learning flow.

        Layout preference (choose the best one for this topic):
        - Horizontal pipeline (left→right) for processes / sequences
        - Vertical flow (top→bottom) for step-by-step procedures
        - Hub-and-spoke for definitions / taxonomy
        - Two-column compare/contrast if the topic naturally splits into two groups

        Label formatting requirement:
        - Ensure labels never overflow node boxes.
        - Use '\\n' to split long labels into 2–3 lines (break on word boundaries).

        Node/edge guidance:
        - Each node: unique id (snake_case) + label.
        - Edges: connect only when there is a real relationship; label edges only when it adds clarity.

        Return ONLY the JSON plan.
    """

    resp = pool.chat_completion_with_failover(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    raw = resp.choices[0].message.content
    plan_text = _extract_json(raw)

    plan = json.loads(plan_text)

    errors = validate_plan(plan, min_nodes=min_nodes)
    if errors:
        raise ValueError("Invalid plan: " + "; ".join(errors))

    return plan


def _boxes_too_close(a, b, min_gap=20):
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    # enforce spacing by expanding both boxes
    ax1 -= min_gap
    ay1 -= min_gap
    ax2 += min_gap
    ay2 += min_gap
    bx1 -= min_gap
    by1 -= min_gap
    bx2 += min_gap
    by2 += min_gap

    return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)


def validate_plan(plan: dict, min_nodes: int = 6) -> list[str]:
    errors = []

    if "nodes" not in plan or "edges" not in plan:
        return ["Plan must contain 'nodes' and 'edges'."]
    if not isinstance(plan["nodes"], list) or not isinstance(plan["edges"], list):
        return ["'nodes' and 'edges' must be arrays."]

    nodes = plan["nodes"]
    edges = plan["edges"]

    if len(nodes) < min_nodes:
        errors.append(f"Too few nodes: {len(nodes)} < {min_nodes}")

    ids = []
    boxes = []

    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errors.append(f"nodes[{i}] is not an object.")
            continue

        nid = n.get("id")
        lbl = n.get("label")
        x, y, w, h = n.get("x"), n.get("y"), n.get("w"), n.get("h")

        if not nid or not isinstance(nid, str):
            errors.append(f"nodes[{i}].id missing/invalid.")
        else:
            ids.append(nid)

        if not lbl or not isinstance(lbl, str):
            errors.append(f"nodes[{i}].label missing/invalid.")

        try:
            x = float(x)
            y = float(y)
            w = float(w)
            h = float(h)
        except Exception:
            errors.append(f"nodes[{i}] has non-numeric geometry.")
            continue

        if w <= 0 or h <= 0:
            errors.append(f"nodes[{i}] has non-positive size.")

        # bounds check
        if x < 0 or y < 0 or x + w > CANVAS_W or y + h > CANVAS_H:
            errors.append(f"nodes[{i}] out of canvas bounds.")

        boxes.append((nid or f"node_{i}", x, y, w, h))

    # duplicate IDs
    if len(ids) != len(set(ids)):
        errors.append("Duplicate node ids found.")

    id_set = set(ids)

    MIN_GAP_HARD = 2.0  # only reject if essentially touching/overlapping
    MIN_GAP_WARN = 12.0  # optional diagnostics only

    warnings = []

    # spacing / overlap check
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            id_a, ax, ay, aw, ah = boxes[i]
            id_b, bx, by, bw, bh = boxes[j]
            A = (ax, ay, aw, ah)
            B = (bx, by, bw, bh)

            if _boxes_overlap(A, B):
                errors.append(f"Nodes overlap: {id_a} vs {id_b}")
                continue  # no need to check gap if they already overlap

            gap = _edge_gap(A, B)
            if gap < MIN_GAP_HARD:
                errors.append(f"Nodes too close: {id_a} vs {id_b} (gap={gap:.1f}px)")
            elif gap < MIN_GAP_WARN:
                warnings.append(f"Nodes close: {id_a} vs {id_b} (gap={gap:.1f}px)")

    # edge validation
    for k, e in enumerate(edges):
        if not isinstance(e, dict):
            errors.append(f"edges[{k}] is not an object.")
            continue

        src = e.get("from")
        dst = e.get("to")

        if src not in id_set:
            errors.append(f"edges[{k}].from references unknown node '{src}'.")
        if dst not in id_set:
            errors.append(f"edges[{k}].to references unknown node '{dst}'.")
        if src == dst:
            errors.append(f"edges[{k}] self-loop not allowed ('{src}' -> '{dst}').")

    return errors


def _boxes_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def _edge_gap(a, b):
    # minimum axis gap between two non-overlapping boxes (0 if overlapping/projection intersect)
    ax, ay, aw, ah = a
    bx, by, bw, bh = b

    gap_x = max(0.0, max(bx - (ax + aw), ax - (bx + bw)))
    gap_y = max(0.0, max(by - (ay + ah), ay - (by + bh)))
    return max(gap_x, gap_y)
