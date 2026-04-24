from pathlib import Path
import csv

from groq import Groq

from src.config import GROQ_API_KEY, MAX_ATTEMPTS, MODEL_NAME
from src.generator import generate_svg_with_groq, build_system_prompt
from src.validator import validate_svg
from src.renderer import save_png_from_svg
from src.utils import topic_to_slug, timestamp_now, save_file, save_json


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


def run_batch():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not found in environment/.env")

    client = Groq(api_key=GROQ_API_KEY)

    Path("reports").mkdir(exist_ok=True)
    Path("svg").mkdir(exist_ok=True)
    Path("img").mkdir(exist_ok=True)

    batch_stamp = timestamp_now()
    csv_path = f"reports/batch_{batch_stamp}.csv"

    passed_count = 0

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "topic",
                "model",
                "attempts_used",
                "xml_valid",
                "group_count",
                "rect_count",
                "connector_elements_total",
                "overlap_count",
                "error_count",
                "passed",
            ],
        )
        writer.writeheader()

        for topic in TOPICS:
            tstamp = timestamp_now()
            topic_slug = topic_to_slug(topic)

            base_user_prompt = f"Generate an educational SVG for topic: {topic}"
            system_prompt = build_system_prompt(topic)

            attempt = 1
            last_validation = None
            svg_text = ""

            while attempt <= MAX_ATTEMPTS:
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

                print(f"[{topic}] Attempt {attempt}/{MAX_ATTEMPTS}")
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
            if passed:
                passed_count += 1

            svg_path = f"svg/{topic_slug}_{tstamp}.svg"
            png_path = f"img/{topic_slug}_{tstamp}.png"
            report_path = f"reports/{topic_slug}_{tstamp}.json"

            save_file(svg_path, svg_text)
            save_png_from_svg(topic_slug, tstamp)

            report = {
                "timestamp": tstamp,
                "topic": topic,
                "model": MODEL_NAME,
                "attempts_used": attempts_used,
                "max_attempts": MAX_ATTEMPTS,
                "validation": last_validation,
                "artifacts": {
                    "svg": svg_path,
                    "png": png_path,
                    "csv": csv_path,
                },
            }
            save_json(report_path, report, "report")

            writer.writerow(
                {
                    "timestamp": tstamp,
                    "topic": topic,
                    "model": MODEL_NAME,
                    "attempts_used": attempts_used,
                    "xml_valid": last_validation["xml_valid"]
                    if last_validation
                    else False,
                    "group_count": last_validation["group_count"]
                    if last_validation
                    else 0,
                    "rect_count": last_validation["rect_count"]
                    if last_validation
                    else 0,
                    "connector_elements_total": last_validation[
                        "connector_elements_total"
                    ]
                    if last_validation
                    else 0,
                    "overlap_count": len(last_validation["overlap_pairs"])
                    if last_validation
                    else 0,
                    "error_count": len(last_validation["errors"])
                    if last_validation
                    else 1,
                    "passed": passed,
                }
            )

    print(f"\nBatch complete: {passed_count}/{len(TOPICS)} passed")
    print(f"CSV saved: {csv_path}")


if __name__ == "__main__":
    run_batch()
