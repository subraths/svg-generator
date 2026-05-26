from pathlib import Path

from src.agentic_loop import generate_with_agentic_feedback
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
from src.config import MAX_ATTEMPTS, MODEL_NAME, MAX_AGENTIC_ITERS
from src.groq_pool import GroqClientPool


TOPIC = "TCP handshake process"
USE_PLANNER = True
USE_AGENTIC = True


def main():
    pool = GroqClientPool.from_env()

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

    # ---- planner stage ----
    if USE_PLANNER:
        try:
            plan = generate_layout_plan(pool, TOPIC, min_nodes=6)
            plan_path = f"reports/{topic_slug}_{timestamp}_plan.json"
            save_json(plan_path, plan, "plan")
        except Exception as e:
            raise ValueError(f"Planner failed before SVG generation: {e}")

    # ---- agentic path (planner required) ----
    if USE_PLANNER and USE_AGENTIC and plan is not None:
        svg_text, report = generate_with_agentic_feedback(
            pool=pool,
            topic=TOPIC,
            plan=plan,
            max_iters=MAX_AGENTIC_ITERS,
            out_base=f"{topic_slug}_{timestamp}_agentic",
        )
        last_validation = validate_svg(svg_text)
        attempts_used = report.get("iterations", 1)
    else:
        # ---- existing retry loop ----
        while attempt <= MAX_ATTEMPTS:
            print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS} ---")

            if USE_PLANNER and plan is not None:
                if attempt > 1 and last_validation and last_validation["errors"]:
                    feedback = "; ".join(last_validation["errors"])
                    print(f"Regenerating plan due to validation errors: {feedback}")

                    replanned_topic = (
                        f"{TOPIC}. Previous SVG failed with: {feedback}. "
                        "Create a cleaner layout with more spacing, clear connector routing, "
                        "and strict non-overlap."
                    )
                    plan = generate_layout_plan(pool, replanned_topic, min_nodes=6)

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

            svg_text = generate_svg_with_groq(pool, system_prompt, user_prompt)
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

    # Only render PNG if SVG XML is valid
    if last_validation and last_validation.get("xml_valid"):
        save_png_from_svg(topic_slug, timestamp)
    else:
        print("Skipping PNG render: SVG is invalid XML.")

    report = {
        "timestamp": timestamp,
        "topic": TOPIC,
        "model": MODEL_NAME,
        "mode": "v2_planner_agentic"
        if (USE_PLANNER and USE_AGENTIC)
        else ("v2_planner" if USE_PLANNER else "v1_direct"),
        "attempts_used": attempts_used,
        "max_attempts": MAX_ATTEMPTS if not USE_AGENTIC else MAX_AGENTIC_ITERS,
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
