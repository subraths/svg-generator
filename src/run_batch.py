from pathlib import Path
import csv

from groq import Groq

from src.config import GROQ_API_KEY, MAX_ATTEMPTS, MAX_PLANNER_ATTEMPTS, MODEL_NAME
from src.generator import (
    generate_svg_with_groq,
    build_system_prompt,
    build_system_prompt_from_plan,
    build_user_prompt_from_plan,
)
from src.planner import generate_layout_plan
from src.validator import validate_svg
from src.utils import topic_to_slug, timestamp_now, save_file, save_json
import cairosvg


TOPICS = [
    "TCP 3-way handshake",
    "Transformer architecture",
    "Cell structure",
    "DNS resolution flow",
    "Photosynthesis process",
    "HTTP request lifecycle",
    "Neural network forward pass",
    "CPU memory hierarchy",
    "Kubernetes pod lifecycle",
    "Blockchain transaction flow",
]

MODES = ["v1_direct", "v2_planner"]


def run_one_topic(client, topic: str, mode: str, batch_stamp: str):
    tstamp = timestamp_now()
    topic_slug = topic_to_slug(topic)

    base_user_prompt = f"Generate an educational SVG for topic: {topic}"

    plan = None
    plan_path = ""
    if mode == "v2_planner":
        planner_attempts = 0
        while planner_attempts < MAX_PLANNER_ATTEMPTS:
            try:
                plan = generate_layout_plan(client, topic, min_nodes=6)
                plan_path = f"reports/{topic_slug}_{batch_stamp}_{mode}_plan.json"
                save_json(plan_path, plan, "plan")
                break
            except Exception as e:
                planner_attempts += 1
                if planner_attempts >= MAX_PLANNER_ATTEMPTS:
                    raise ValueError(
                        f"Planner failed after {MAX_PLANNER_ATTEMPTS} tries: {e}"
                    )

    attempt = 1
    last_validation = None
    svg_text = ""

    while attempt <= MAX_ATTEMPTS:
        if mode == "v2_planner":
            # replan on failed attempts
            if attempt > 1 and last_validation and last_validation["errors"]:
                feedback = "; ".join(last_validation["errors"])
                replanned_topic = (
                    f"{topic}. Previous SVG failed with: {feedback}. "
                    "Create a cleaner non-overlapping layout with clearer routing."
                )
                plan = generate_layout_plan(client, replanned_topic, min_nodes=6)
                plan_path = f"reports/{topic_slug}_{batch_stamp}_{mode}_plan_attempt_{attempt}.json"
                save_json(plan_path, plan, "plan")

            system_prompt = build_system_prompt_from_plan()
            user_prompt = build_user_prompt_from_plan(topic, plan)
            if attempt > 1 and last_validation:
                errs = "; ".join(last_validation["errors"])
                user_prompt += (
                    f"\nPrevious SVG failed validation: {errs}\n"
                    "Regenerate corrected SVG while keeping this updated plan."
                )

        else:
            system_prompt = build_system_prompt(topic)
            if attempt == 1:
                user_prompt = base_user_prompt
            else:
                errs = (
                    "; ".join(last_validation["errors"])
                    if last_validation
                    else "Unknown validation issue."
                )
                user_prompt = (
                    f"{base_user_prompt}\n\n"
                    f"Previous output failed validation with these errors: {errs}\n"
                    "Regenerate a corrected SVG that satisfies all rules."
                )

        print(f"[{mode}] [{topic}] Attempt {attempt}/{MAX_ATTEMPTS}")
        svg_text = generate_svg_with_groq(client, system_prompt, user_prompt)
        last_validation = validate_svg(svg_text)

        if last_validation["xml_valid"] and not last_validation["errors"]:
            break
        attempt += 1

    attempts_used = min(attempt, MAX_ATTEMPTS)
    passed = bool(
        last_validation
        and last_validation["xml_valid"]
        and len(last_validation["errors"]) == 0
    )

    base_name = f"{topic_slug}_{batch_stamp}_{mode}"
    svg_path = f"svg/{base_name}.svg"
    png_path = f"img/{base_name}.png"
    report_path = f"reports/{base_name}.json"

    save_file(svg_path, svg_text)
    cairosvg.svg2png(url=svg_path, write_to=png_path)

    report = {
        "timestamp": tstamp,
        "batch_stamp": batch_stamp,
        "topic": topic,
        "mode": mode,
        "model": MODEL_NAME,
        "attempts_used": attempts_used,
        "max_attempts": MAX_ATTEMPTS,
        "validation": last_validation,
        "artifacts": {
            "svg": svg_path,
            "png": png_path,
            "plan": plan_path if mode == "v2_planner" else None,
        },
    }
    save_json(report_path, report, "report")

    row = {
        "timestamp": tstamp,
        "batch_stamp": batch_stamp,
        "topic": topic,
        "mode": mode,
        "model": MODEL_NAME,
        "attempts_used": attempts_used,
        "xml_valid": last_validation["xml_valid"] if last_validation else False,
        "group_count": last_validation["group_count"] if last_validation else 0,
        "rect_count": last_validation["rect_count"] if last_validation else 0,
        "connector_elements_total": last_validation["connector_elements_total"]
        if last_validation
        else 0,
        "overlap_count": len(last_validation["overlap_pairs"])
        if last_validation
        else 0,
        "error_count": len(last_validation["errors"]) if last_validation else 1,
        "passed": passed,
        "plan_path": plan_path,
        "svg_path": svg_path,
        "png_path": png_path,
    }
    return row, passed


def run_batch():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in environment/.env")

    client = Groq(api_key=GROQ_API_KEY)

    Path("reports").mkdir(exist_ok=True)
    Path("svg").mkdir(exist_ok=True)
    Path("img").mkdir(exist_ok=True)

    batch_stamp = timestamp_now()
    csv_path = f"reports/batch_compare_{batch_stamp}.csv"

    passed_count = 0
    total_runs = len(TOPICS) * len(MODES)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "batch_stamp",
                "topic",
                "mode",
                "model",
                "attempts_used",
                "xml_valid",
                "group_count",
                "rect_count",
                "connector_elements_total",
                "overlap_count",
                "error_count",
                "passed",
                "plan_path",
                "svg_path",
                "png_path",
                "fatal_error",
            ],
        )
        writer.writeheader()

        for topic in TOPICS:
            for mode in MODES:
                try:
                    row, passed = run_one_topic(client, topic, mode, batch_stamp)

                except Exception as e:
                    print(f"[{mode}] [{topic}] FAILED hard: {e}")
                    row = build_failed_row(topic, mode, batch_stamp, e)
                    passed = False

                writer.writerow(row)
                if passed:
                    passed_count += 1

    print(f"\nBatch compare complete: {passed_count}/{total_runs} passed")
    print(f"CSV saved: {csv_path}")


def build_failed_row(topic: str, mode: str, batch_stamp: str, err: Exception):
    return {
        "timestamp": timestamp_now(),
        "batch_stamp": batch_stamp,
        "topic": topic,
        "mode": mode,
        "model": MODEL_NAME,
        "attempts_used": 0,
        "xml_valid": False,
        "group_count": 0,
        "rect_count": 0,
        "connector_elements_total": 0,
        "overlap_count": 0,
        "error_count": 1,
        "passed": False,
        "plan_path": "",
        "svg_path": "",
        "png_path": "",
        "fatal_error": str(err),
    }


if __name__ == "__main__":
    run_batch()
