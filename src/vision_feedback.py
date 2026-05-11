import base64
import json
import os
from typing import Dict, Any

import requests


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
VISION_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"

RUBRIC = """
Evaluate the diagram for:
1) Overlap between nodes or text
2) Arrow endpoints: arrows should touch node boundary, not go inside
3) Text readability (font size/contrast/placement)
4) Spacing consistency
5) Overall alignment and visual cleanliness

Return ONLY JSON with schema:
{
  "pass": true|false,
  "issues": [
    {"type": "overlap|arrows|readability|spacing|alignment", "detail": "..."}
  ],
  "summary": "short overall comment"
}
"""


def _png_to_base64(png_path: str) -> str:
    """
    Load PNG from disk and return base64 data.
    """
    with open(png_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_vision_feedback(png_path: str) -> Dict[str, Any]:
    """
    Send PNG to OpenRouter vision model for critique.
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    b64 = _png_to_base64(png_path)

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict visual QA agent for SVG diagrams.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": RUBRIC},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            },
        ],
        "temperature": 0.1,
    }

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=60,
    )
    print(resp.status_code, resp.text)

    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]

    # Strip accidental code fences.
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()

    return json.loads(text)
