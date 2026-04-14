import csv
from pathlib import Path

from src.config import MAX_ATTEMPTS, MODEL_NAME
from src.generator import generate_svg_with_groq, build_system_prompt
from src.validator import validate_svg
from src.renderer import save_png_from_svg
from src.utils import topic_to_slug, timestamp_now, save_file, save_report


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


def run_batch(client):
    Path("reports").mkdir(exist_ok=True)
    Path("svg").mkdir(exist_ok=True)
    Path("img").mkdir(exist_ok=True)

    batch_stamp = timestamp_now()
    csv_path = f"reports/batch_{batch_stamp}.csv"

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
            system_prompt = build_system_prompt(topic)

            attempt = 1
            last_validation = {}
            svg_text = ""
            base_user_prompt = f"Generate an educational SVG for topic: {topic}"

            while attempt <= MAX_ATTEMPTS:
                user_prompt = (
                    base_user_prompt
                    if attempt == 1
                    else (
                        f"{base_user_prompt}\n\n"
                        f"Previous output failed validation with errors: {'; '.join(last_validation['errors'])}\n"
                        "Regenerate a corrected SVG that satisfies all rules."
                    )
                )

                svg_text = generate_svg_with_groq(client, system_prompt, user_prompt)
                last_validation = validate_svg(svg_text)

                if last_validation["xml_valid"] and not last_validation["errors"]:
                    break
                attempt += 1

            svg_path = f"svg/{topic_slug}_{tstamp}.svg"
            save_file(svg_path, svg_text)
            save_png_from_svg(topic_slug, tstamp)

            report = {
                "timestamp": tstamp,
                "topic": topic,
                "model": MODEL_NAME,
                "attempts_used": min(attempt, MAX_ATTEMPTS),
                "max_attempts": MAX_ATTEMPTS,
                "validation": last_validation,
            }
            save_report(f"reports/{topic_slug}_{tstamp}.json", report)

            writer.writerow(
                {
                    "timestamp": tstamp,
                    "topic": topic,
                    "model": MODEL_NAME,
                    "attempts_used": min(attempt, MAX_ATTEMPTS),
                    "xml_valid": last_validation["xml_valid"],
                    "group_count": last_validation["group_count"],
                    "rect_count": last_validation["rect_count"],
                    "connector_elements_total": last_validation[
                        "connector_elements_total"
                    ],
                    "overlap_count": len(last_validation["overlap_pairs"]),
                    "error_count": len(last_validation["errors"]),
                    "passed": last_validation["xml_valid"]
                    and len(last_validation["errors"]) == 0,
                }
            )

    print(f"Batch complete. CSV: {csv_path}")
