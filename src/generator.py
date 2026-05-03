import json
import re
import time
from typing import Callable

from groq import Groq

from src.config import CANVAS_H, CANVAS_W, MODEL_NAME
from src.config import MODEL_NAME

# global/shared limiter instance (or inject it)
from src.groq_pool import GroqClientPool
from src.rate_limit import SimpleRateLimiter, estimate_tokens

limiter = SimpleRateLimiter(min_interval_sec=2.5, daily_token_budget=190_000)


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


def generate_svg_with_groq(
    pool: GroqClientPool, system_prompt: str, user_prompt: str
) -> str:
    resp = pool.chat_completion_with_failover(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    text = resp.choices[0].message.content or ""

    # strip markdown fences if model returns ```svg ... ```
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    return text


def build_system_prompt_from_plan() -> str:
    return f"""You are an expert SVG generator.
Return ONLY valid SVG XML. No markdown.

Canvas must be exactly width="{CANVAS_W}" height="{CANVAS_H}".
Use <g id="..."> for each node id from the plan.
Draw rectangles or circles and centered labels for nodes.
Draw connectors for all edges with marker-end arrows.
Define arrow marker in <defs> with id containing "arrow".
Connect edges from source box boundary to target box boundary.
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


def _parse_retry_after_seconds(msg: str, default_sec: int = 30) -> int:
    """
    Parse strings like:
    'Please try again in 9m57.456s'
    'Please try again in 45.2s'
    """
    if not msg:
        return default_sec

    m = re.search(r"Please try again in\s+((?:(\d+)m)?([\d.]+)s)", msg)
    if not m:
        return default_sec

    mins = int(m.group(2)) if m.group(2) else 0
    secs = float(m.group(3)) if m.group(3) else 0.0
    total = int(mins * 60 + secs + 0.999)  # ceil-ish
    return max(1, total)


def _wait_with_progress(total_sec: int, prefix: str = "Rate-limited"):
    start = time.time()
    for i in range(total_sec):
        elapsed = int(time.time() - start)
        remaining = total_sec - i
        print(
            f"{prefix}: elapsed={elapsed}s remaining={remaining}s", end="\r", flush=True
        )
        time.sleep(1)
    print(" " * 100, end="\r")  # clear line


def _is_429_rate_limit(err: Exception) -> bool:
    s = str(err)
    return ("429" in s) and ("rate_limit_exceeded" in s or "Rate limit reached" in s)


def call_groq_with_429_retry(
    request_fn: Callable[[], object],
    max_retries: int = 8,
    label: str = "Groq call",
):
    """
    request_fn should execute ONE API request and return response.
    Retries only on rate-limit 429.
    """
    attempt = 0
    while True:
        try:
            return request_fn()
        except Exception as e:
            attempt += 1
            if not _is_429_rate_limit(e) or attempt > max_retries:
                raise

            msg = str(e)
            wait_sec = _parse_retry_after_seconds(msg, default_sec=30)
            print(
                f"\n[{label}] 429 received (attempt {attempt}/{max_retries}). Waiting {wait_sec}s..."
            )
            _wait_with_progress(wait_sec, prefix=f"[{label}] waiting")
