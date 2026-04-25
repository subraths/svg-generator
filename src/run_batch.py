from pathlib import Path
import csv
from datetime import datetime, UTC

import cairosvg

from src.config import MAX_ATTEMPTS, MODEL_NAME, CANVAS_W, CANVAS_H
from src.generator import (
    generate_svg_with_groq,
    build_system_prompt,
    build_system_prompt_from_plan,
    build_user_prompt_from_plan,
)
from src.planner import generate_layout_plan
from src.validator import validate_svg
from src.utils import topic_to_slug, timestamp_now, save_file, save_json
from src.groq_pool import GroqClientPool

pool = GroqClientPool.from_env()


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


def classify_failure(last_validation: dict, fatal_error: str = ""):
    if fatal_error:
        if "Invalid plan" in fatal_error or "Planner failed" in fatal_error:
            return "planner_invalid", fatal_error
        return "fatal_error", fatal_error

    if not last_validation:
        return "unknown", "No validation report."

    errs = " | ".join(last_validation.get("errors", []))

    if "XML parse error" in errs or not last_validation.get("xml_valid", False):
        return "xml_invalid", errs
    if "overlapping rect groups" in errs:
        return "overlap", errs
    if (
        "Too few connector elements" in errs
        or "No connectors use marker-end arrows" in errs
    ):
        return "connector_missing", errs
    if "No arrow marker definition found" in errs:
        return "arrow_marker_missing", errs
    if "Less than 6 concept groups found" in errs:
        return "too_few_groups", errs

    return "unknown", errs if errs else "Unknown failure."


def build_failed_row(topic: str, mode: str, batch_stamp: str, err: Exception):
    ftype, fdetail = classify_failure(None, str(err))
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
        "failure_type": ftype,
        "failure_detail": fdetail,
        "fatal_error": str(err),
    }


def run_one_topic(pool: GroqClientPool, topic: str, mode: str, batch_stamp: str):
    tstamp = timestamp_now()
    topic_slug = topic_to_slug(topic)
    base_user_prompt = f"Generate an educational SVG for topic: {topic}"

    plan = None
    plan_path = ""
    if mode == "v2_planner":
        planner_attempts = 0
        while planner_attempts < 3:
            try:
                plan = generate_layout_plan(pool, topic, min_nodes=6)
                plan_path = f"reports/{topic_slug}_{batch_stamp}_{mode}_plan.json"
                save_json(plan_path, plan, "plan")
                break
            except Exception as e:
                planner_attempts += 1
                if planner_attempts >= 3:
                    raise ValueError(f"Planner failed after 3 tries: {e}")

    attempt = 1
    last_validation = None
    svg_text = ""

    while attempt <= MAX_ATTEMPTS:
        if mode == "v2_planner":
            if attempt > 1 and last_validation and last_validation["errors"]:
                feedback = "; ".join(last_validation["errors"])
                replanned_topic = (
                    f"{topic}. Previous SVG failed with: {feedback}. "
                    "Create a cleaner non-overlapping layout with clearer routing."
                )
                plan = generate_layout_plan(pool, replanned_topic, min_nodes=6)
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
        svg_text = generate_svg_with_groq(pool, system_prompt, user_prompt)
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

    failure_type, failure_detail = ("", "")
    if not passed:
        failure_type, failure_detail = classify_failure(last_validation)

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
        "failure_type": failure_type,
        "failure_detail": failure_detail,
        "fatal_error": "",
    }
    return row, passed


def save_manifest(batch_stamp: str, started_at: str, finished_at: str, csv_path: str):
    manifest = {
        "batch_stamp": batch_stamp,
        "started_at": started_at,
        "finished_at": finished_at,
        "model": MODEL_NAME,
        "max_attempts": MAX_ATTEMPTS,
        "canvas": {"width": CANVAS_W, "height": CANVAS_H},
        "topics": TOPICS,
        "modes": MODES,
        "output_csv": csv_path,
    }
    save_json(f"reports/manifest_{batch_stamp}.json", manifest, "manifest")


def run_batch():
    Path("reports").mkdir(exist_ok=True)
    Path("svg").mkdir(exist_ok=True)
    Path("img").mkdir(exist_ok=True)

    batch_stamp = timestamp_now()
    started_at = datetime.now(UTC).isoformat()
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
                "failure_type",
                "failure_detail",
                "fatal_error",
            ],
        )
        writer.writeheader()

        for topic in TOPICS:
            for mode in MODES:
                try:
                    row, passed = run_one_topic(pool, topic, mode, batch_stamp)
                except Exception as e:
                    print(f"[{mode}] [{topic}] FAILED hard: {e}")
                    row = build_failed_row(topic, mode, batch_stamp, e)
                    passed = False

                writer.writerow(row)
                if passed:
                    passed_count += 1

    finished_at = datetime.now(UTC).isoformat()
    save_manifest(batch_stamp, started_at, finished_at, csv_path)

    print(f"\nBatch compare complete: {passed_count}/{total_runs} passed")
    print(f"CSV saved: {csv_path}")


if __name__ == "__main__":
    run_batch()
