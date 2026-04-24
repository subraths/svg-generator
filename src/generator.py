import json

from src.config import CANVAS_H, CANVAS_W, MODEL_NAME


def build_system_prompt(topic: str) -> str:
    return f"""You are an expert educational SVG diagram generator.

    Return ONLY valid SVG XML.
    No markdown fences.
    Canvas must be exactly width="{CANVAS_W}" height="{CANVAS_H}".
    Use clear labels with readable font-size (>=16).

    Task:
    Create a simple educational diagram for: "{topic}"

    Rules:
    1) Group each logical concept in <g id="..."> with short snake_case ids.
    2) Include at least 6 concept groups.
    3) Keep layout clean: avoid overlaps, keep spacing between blocks.
    4) Use arrows/lines to show relationships or flow.
    5) Keep style minimal and classroom-friendly.
    6) All text must be inside canvas bounds.
    7) Do not use external assets/images/fonts/scripts.
    8) Define arrow marker in <defs> with id containing arrow.
    9) Use marker-end arrows on connectors.
    """


def generate_svg_with_groq(client, system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    svg_text = response.choices[0].message.content.strip()
    svg_text = (
        svg_text.replace("```svg", "").replace("```xml", "").replace("```", "").strip()
    )
    return svg_text


def build_system_prompt_from_plan() -> str:
    return f"""You are an expert SVG generator.
Return ONLY valid SVG XML. No markdown.

Canvas must be exactly width="{CANVAS_W}" height="{CANVAS_H}".
Use <g id="..."> for each node id from the plan.
Draw rectangles or circles and centered labels for nodes.
Draw connectors for all edges with marker-end arrows.
Define arrow marker in <defs> with id containing "arrow".
Do not place text outside canvas.
Do not use external assets/scripts.
"""


def build_user_prompt_from_plan(topic: str, plan: dict) -> str:
    return (
        f"Generate an educational SVG for topic: {topic}\n\n"
        f"Use this layout plan exactly (JSON):\n{json.dumps(plan, indent=2)}\n\n"
        "Requirements:\n"
        "- Keep node ids exactly as given.\n"
        "- Connect edges from source box boundary to target box boundary.\n"
        "- Keep output clean and readable.\n"
    )
