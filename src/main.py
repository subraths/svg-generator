from pathlib import Path

from groq import Groq


from src.generator import (
    build_system_prompt,
    generate_svg_with_groq,
    build_system_prompt_from_plan,
    build_user_prompt_from_plan,
)
from src.planner import generate_layout_plan
from src.renderer import save_png_from_svg
from src.validator import validate_svg
from src.utils import save_file, save_json, topic_to_slug, timestamp_now
from src.config import GROQ_API_KEY, MAX_ATTEMPTS, MODEL_NAME


# change this each run: "TCP 3-way handshake", "Cell structure", "Photosynthesis", "Water cycle",
# "Human digestive system", "Electric circuit basics", "Solar system overview", "DNA replication process",
# "Ecosystem food web", "Cloud formation process", "Thread lifecycle in programming", "Machine learning workflow",
# "Blockchain transaction flow", "Software development lifecycle", Version control workflow, API request flow,
# "Transport Layer Security (TLS) Handshake Process", "HTTP request-response cycle", "Neural network architecture",
# Neural network architecture, Software development lifecycle, Compiler design stages, Database normalization forms, Object-oriented programming concepts, Data structure visualization, Algorithm flowchart, Computer memory hierarchy, Operating system process management, Network protocol stack, Cloud computing architecture, Cybersecurity attack vectors, Software testing strategies, Mobile app architecture, User interface design principles

TOPIC = "Photosynthesis"
USE_PLANNER = True


def main():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable not defined")

    client = Groq(api_key=GROQ_API_KEY)

    Path("reports").mkdir(exist_ok=True)
    Path("svg").mkdir(exist_ok=True)
    Path("img").mkdir(exist_ok=True)

    topic_slug = topic_to_slug(TOPIC)
    timestamp = timestamp_now()

    plan = None
    base_user_prompt = f"Generate an educational SVG for topic {TOPIC}"
    attempt = 1
    last_validation = None
    svg_text = ""

    # ---- NEW: planner stage (only when USE_PLANNER=True) ----
    if USE_PLANNER:
        try:
            plan = generate_layout_plan(client, TOPIC, min_nodes=6)
            plan_path = f"reports/{topic_slug}_{timestamp}_plan.json"
            save_json(plan_path, plan, "plan")
        except Exception as e:
            raise ValueError(f"Planner failed before SVG generation: {e}")

    # SYSTEM_PROMPT = build_system_prompt(topic=TOPIC)
    # ---- retry loop (same idea as v1, but prompt source differs) ----

    while attempt <= MAX_ATTEMPTS:
        print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS} ---")

        if USE_PLANNER and plan is not None:
            if attempt > 1 and last_validation and last_validation["errors"]:
                feedback = "; ".join(last_validation["errors"])
                print(f"Regenerating plan due to validation errors: {feedback}")

                # lightweight feedback injection into topic prompt
                replanned_topic = (
                    f"{TOPIC}. Previous SVG failed with: {feedback}. "
                    "Create a cleaner layout with more spacing, clear connector routing, "
                    "and strict non-overlap."
                )
                plan = generate_layout_plan(client, replanned_topic, min_nodes=6)

                # overwrite latest plan artifact for traceability
                plan_path = (
                    f"reports/{topic_slug}_{timestamp}_plan_attempt_{attempt}.json"
                )
                save_json(plan_path, plan, "plan")
            system_prompt = build_system_prompt_from_plan()
            user_prompt = build_user_prompt_from_plan(TOPIC, plan)

            if attempt > 1 and last_validation:
                errs = "; ".join(last_validation["errors"])
                user_prompt += (
                    f"\nPrevious SVG failed validation: {errs}\n"
                    "Regenerate corrected SVG while keeping this updated plan."
                )
        else:
            system_prompt = build_system_prompt(TOPIC)
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

        svg_text = generate_svg_with_groq(client, system_prompt, user_prompt)
        last_validation = validate_svg(svg_text)

        if last_validation["xml_valid"] and not last_validation["errors"]:
            print("Validation passed.")
            break

        print("Validation failed:", last_validation["errors"])
        attempt += 1

    attempts_used = min(attempt, MAX_ATTEMPTS)

    # ---- save artifacts ----
    svg_path = f"svg/{topic_slug}_{timestamp}.svg"
    save_file(svg_path, svg_text)
    save_png_from_svg(topic_slug, timestamp)

    report = {
        "timestamp": timestamp,
        "topic": TOPIC,
        "model": MODEL_NAME,
        "mode": "v2_planner" if USE_PLANNER else "v1_direct",
        "attempts_used": attempts_used,
        "max_attempts": MAX_ATTEMPTS,
        "validation": last_validation,
        "artifacts": {
            "svg": svg_path,
            "png": f"img/{topic_slug}_{timestamp}.png",
            "plan": f"reports/{topic_slug}_{timestamp}_plan.json"
            if USE_PLANNER
            else None,
        },
    }

    report_path = f"reports/{topic_slug}_{timestamp}.json"
    save_json(report_path, report, "report")


if __name__ == "__main__":
    main()
