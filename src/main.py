from dotenv import load_dotenv

from groq import Groq


from src.utils import save_file, save_report, topic_to_slug, timestamp_now
from src.generator import build_system_prompt, generate_svg_with_groq
from src.renderer import save_png_from_svg
from src.validator import validate_svg
from src.config import GROQ_API_KEY, MAX_ATTEMPTS, MODEL_NAME

load_dotenv()

model = MODEL_NAME  # or "llama-3.3-70b-versatile"

client = Groq(api_key=GROQ_API_KEY)


# change this each run: "TCP 3-way handshake", "Cell structure", "Photosynthesis", "Water cycle",
# "Human digestive system", "Electric circuit basics", "Solar system overview", "DNA replication process",
# "Ecosystem food web", "Cloud formation process", "Thread lifecycle in programming", "Machine learning workflow",
# "Blockchain transaction flow", "Software development lifecycle", Version control workflow, API request flow,
# "Transport Layer Security (TLS) Handshake Process", "HTTP request-response cycle", "Neural network architecture",
# Neural network architecture, Software development lifecycle, Compiler design stages, Database normalization forms, Object-oriented programming concepts, Data structure visualization, Algorithm flowchart, Computer memory hierarchy, Operating system process management, Network protocol stack, Cloud computing architecture, Cybersecurity attack vectors, Software testing strategies, Mobile app architecture, User interface design principles

TOPIC = "Water condensation"

topic_slug = topic_to_slug(TOPIC)
timestamp = timestamp_now()

SYSTEM_PROMPT = build_system_prompt(topic=TOPIC)


attempt = 1
last_validation = None
svg_text = ""

base_user_prompt = f"Generate an educational SVG for topic: {TOPIC}"

while attempt <= MAX_ATTEMPTS:
    if attempt == 1:
        user_prompt = base_user_prompt
    else:
        # send compact error feedback for regeneration
        errs = (
            "; ".join(last_validation["errors"])
            if last_validation
            else "Unknown validation issue."
        )
        user_prompt = (
            f"{base_user_prompt}\n\n"
            f"Previous output failed validation with these errors: {errs}\n"
            f"Regenerate a corrected SVG that satisfies all rules."
        )

    print(f"\n--- Attempt {attempt}/{MAX_ATTEMPTS} ---")
    svg_text = generate_svg_with_groq(client, SYSTEM_PROMPT, user_prompt)
    last_validation = validate_svg(svg_text)

    if last_validation["xml_valid"] and not last_validation["errors"]:
        print("Validation passed.")
        break
    else:
        print("Validation failed:", last_validation["errors"])
        attempt += 1


# save svg
save_file(f"svg/{topic_slug}_{timestamp}.svg", svg_text)

# New: render PNG from SVG
save_png_from_svg(topic_slug, timestamp)

report_path = f"reports/{topic_slug}_{timestamp}.json"

report_data = {
    "timestamp": timestamp,
    "topic": TOPIC,
    "model": MODEL_NAME,
    "attempts_used": attempt if attempt <= MAX_ATTEMPTS else MAX_ATTEMPTS,
    "max_attempts": MAX_ATTEMPTS,
    "validation": last_validation,
}

save_report(report_path, report_data)
