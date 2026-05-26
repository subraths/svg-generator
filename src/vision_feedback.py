import base64
import json
import os
import re
from typing import Dict, Any

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
VISION_MODEL = "nvidia/nemotron-nano-12b-v2-vl:free"

RUBRIC = """
Evaluate the diagram for:
1) Overlap between nodes or text
2) Arrow endpoints: arrows should touch node boundary, not go inside
3) Text readability (font size/contrast/placement)
4) Spacing consistency
5) Overall alignment and visual cleanliness
6) Return ONLY valid JSON. No explanation. No markdown.

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
    with open(png_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _extract_first_json(text: str) -> str:
    """
    Extract the first JSON object from a string, ignoring extra data.
    Handles duplicate JSON or extra narration.
    """
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in vision response.")
    return m.group(0)


def get_vision_feedback(png_path: str) -> Dict[str, Any]:
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
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "svg-generator",
        },
        data=json.dumps(payload),
        timeout=60,
    )
    print(resp.status_code, resp.text)

    resp.raise_for_status()
    data = resp.json()
    choice = data.get("choices", [{}])[0]
    err = choice.get("error")
    if err:
        return {
            "pass": False,
            "issues": [
                {"type": "provider", "detail": err.get("message", "provider error")}
            ],
            "summary": f"Vision provider error: {err.get('code')}",
        }

    raw = choice.get("message", {}).get("content") or ""
    try:
        json_text = _extract_first_json(raw)
        return json.loads(json_text)
    except Exception:
        return {
            "pass": False,
            "issues": [{"type": "vision", "detail": "Invalid or truncated JSON"}],
            "summary": "Vision response was cut or malformed.",
        }
