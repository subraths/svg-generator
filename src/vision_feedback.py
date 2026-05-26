import base64
import json
import os
import re
import time
from typing import Dict, Any

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
VISION_MODEL = os.getenv("VISION_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")

# Vision QA resilience knobs
VISION_REQUEST_TIMEOUT_S = float(os.getenv("VISION_REQUEST_TIMEOUT_S", "60"))
VISION_RETRIES = int(os.getenv("VISION_RETRIES", "3"))
VISION_RETRY_BACKOFF_S = float(os.getenv("VISION_RETRY_BACKOFF_S", "2"))
# If true, provider/network errors will not fail the run; they will be treated as a PASS.
VISION_FAIL_OPEN = os.getenv("VISION_FAIL_OPEN", "true").lower() in {"1", "true", "yes", "y"}

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
    """Extract the first JSON object from a string, ignoring extra data."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("No JSON object found in vision response.")
    return m.group(0)


def _provider_failure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured feedback object for provider/network errors."""
    if VISION_FAIL_OPEN:
        return {
            "pass": True,
            "issues": [
                {
                    "type": "provider",
                    "detail": payload.get("detail", "vision provider/network error"),
                }
            ],
            "summary": payload.get("summary", "Vision feedback unavailable; continuing."),
        }

    return {
        "pass": False,
        "issues": [
            {"type": "provider", "detail": payload.get("detail", "provider error")}
        ],
        "summary": payload.get("summary", "Vision feedback unavailable."),
    }


def get_vision_feedback(png_path: str) -> Dict[str, Any]:
    """Get visual QA feedback from OpenRouter.

    This function is designed to be resilient to transient provider/network failures.
    If VISION_FAIL_OPEN is enabled (default), failures will be treated as PASS so
    the pipeline can still complete and produce outputs.
    """

    if not OPENROUTER_API_KEY:
        # If no key is configured, behave like a provider failure (optionally fail-open)
        return _provider_failure(
            {
                "detail": "OPENROUTER_API_KEY not set; skipping vision feedback.",
                "summary": "Vision feedback disabled (no OPENROUTER_API_KEY).",
            }
        )

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

    last_exc: Exception | None = None

    for attempt in range(1, VISION_RETRIES + 1):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "svg-generator",
                },
                data=json.dumps(payload),
                timeout=VISION_REQUEST_TIMEOUT_S,
            )

            # Debug print (kept from original)
            print(resp.status_code, resp.text)

            # Some provider failures are returned as 200 with an embedded error.
            resp.raise_for_status()
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            err = choice.get("error")
            if err:
                return _provider_failure(
                    {
                        "detail": err.get("message", "provider error"),
                        "summary": f"Vision provider error: {err.get('code')}",
                    }
                )

            raw = choice.get("message", {}).get("content") or ""
            try:
                json_text = _extract_first_json(raw)
                return json.loads(json_text)
            except Exception:
                return _provider_failure(
                    {
                        "detail": "Invalid or truncated JSON from vision provider",
                        "summary": "Vision response was cut or malformed.",
                    }
                )

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exc = e
            if attempt < VISION_RETRIES:
                time.sleep(VISION_RETRY_BACKOFF_S * attempt)
                continue
            return _provider_failure(
                {
                    "detail": f"Network error contacting vision provider: {e}",
                    "summary": "Vision network error; continuing.",
                }
            )
        except requests.exceptions.HTTPError as e:
            last_exc = e
            # Non-2xx from OpenRouter itself.
            if attempt < VISION_RETRIES:
                time.sleep(VISION_RETRY_BACKOFF_S * attempt)
                continue
            return _provider_failure(
                {
                    "detail": f"HTTP error from vision provider: {e}",
                    "summary": "Vision HTTP error; continuing.",
                }
            )
        except Exception as e:
            last_exc = e
            if attempt < VISION_RETRIES:
                time.sleep(VISION_RETRY_BACKOFF_S * attempt)
                continue
            return _provider_failure(
                {
                    "detail": f"Unexpected error in vision feedback: {e}",
                    "summary": "Vision feedback error; continuing.",
                }
            )

    # Defensive fallback (should never be reached)
    return _provider_failure(
        {
            "detail": f"Vision feedback failed after retries: {last_exc}",
            "summary": "Vision feedback failed; continuing.",
        }
    )
