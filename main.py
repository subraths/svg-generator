import os
import json
from datetime import datetime

from dotenv import load_dotenv

from groq import Groq

import xml.etree.ElementTree as ET
import cairosvg

load_dotenv()

model = "openai/gpt-oss-120b"  # or "llama-3.3-70b-versatile"

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)


# change this each run: "TCP 3-way handshake", "Cell structure", "Photosynthesis", "Water cycle",
# "Human digestive system", "Electric circuit basics", "Solar system overview", "DNA replication process",
# "Ecosystem food web", "Cloud formation process", "Thread lifecycle in programming", "Machine learning workflow",
# "Blockchain transaction flow", "Software development lifecycle", Version control workflow, API request flow,
# "Transport Layer Security (TLS) Handshake Process", "HTTP request-response cycle", "Neural network architecture",
# Neural network architecture, Software development lifecycle, Compiler design stages, Database normalization forms, Object-oriented programming concepts, Data structure visualization, Algorithm flowchart, Computer memory hierarchy, Operating system process management, Network protocol stack, Cloud computing architecture, Cybersecurity attack vectors, Software testing strategies, Mobile app architecture, User interface design principles

TOPIC = "Transformer architecture"

topic_slug = TOPIC.lower().replace(" ", "_")
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

SYSTEM_PROMPT = f"""You are an expert educational SVG diagram generator.

Return ONLY valid SVG XML.
No markdown fences.
Canvas must be exactly width="1000" height="700".
Use clear labels with readable font-size (>=16).

Task:
Create a simple educational diagram for: "{TOPIC}"

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


def validate_svg(svg_text: str):
    report = {
        "xml_valid": False,
        "width": None,
        "height": None,
        "group_ids": [],
        "group_count": 0,
        "rect_count": 0,
        "overlap_pairs": [],
        "line_count": 0,
        "polyline_count": 0,
        "path_count": 0,
        "marker_arrow_defined": False,
        "connector_elements_total": 0,
        "has_duplicate_ids": False,
        "errors": [],
    }

    try:
        root = ET.fromstring(svg_text)
        report["xml_valid"] = True
    except Exception as e:
        report["errors"].append(f"XML parse error: {e}")
        return report

    # Root checks
    if root.tag.lower().endswith("svg"):
        report["width"] = root.attrib.get("width")
        report["height"] = root.attrib.get("height")
    else:
        report["errors"].append("Root element is not <svg>.")

    # Find all <g id="...">
    ids = []
    # collect rects as (id_or_unknown, x, y, w, h)
    rects = []
    current_gid_stack = []

    # Build parent map (ElementTree has no parent pointer)
    parent_map = {c: p for p in root.iter() for c in p}

    def find_parent_gid(el):
        cur = el
        while cur in parent_map:
            cur = parent_map[cur]
            if cur.tag.lower().endswith("g") and "id" in cur.attrib:
                return cur.attrib["id"]
        return "unknown"

    for el in root.iter():
        if el.tag.lower().endswith("rect"):
            try:
                x = float(el.attrib.get("x", "0"))
                y = float(el.attrib.get("y", "0"))
                w = float(el.attrib.get("width", "0"))
                h = float(el.attrib.get("height", "0"))
                if w > 0 and h > 0:
                    gid = find_parent_gid(el)
                    rects.append((gid, x, y, w, h))
            except Exception:
                report["errors"].append("Invalid rect numeric attributes found.")

    report["rect_count"] = len(rects)

    # check overlaps with small padding (8px)
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            gid_a, ax, ay, aw, ah = rects[i]
            gid_b, bx, by, bw, bh = rects[j]
            if rects_overlap((ax, ay, aw, ah), (bx, by, bw, bh), padding=8):
                # Ignore overlap if same group (often intentional)
                if gid_a != gid_b:
                    report["overlap_pairs"].append([gid_a, gid_b])

    if report["overlap_pairs"]:
        report["errors"].append(
            f"Detected overlapping rect groups: {report['overlap_pairs']}"
        )

    for el in root.iter():
        tag = el.tag.lower()
        if tag.endswith("g"):
            gid = el.attrib.get("id")
            if gid:
                ids.append(gid)

    report["group_ids"] = ids
    report["group_count"] = len(ids)
    report["has_duplicate_ids"] = len(ids) != len(set(ids))
    if report["has_duplicate_ids"]:
        report["errors"].append("Duplicate <g id> values found.")

    if report["group_count"] < 6:
        report["errors"].append("Less than 6 concept groups found.")

    line_count = 0
    polyline_count = 0
    path_count = 0
    marker_arrow_defined = False
    connectors_with_arrow = 0

    # detect marker definition
    for el in root.iter():
        tag = el.tag.lower()
        if tag.endswith("marker"):
            mid = el.attrib.get("id", "").lower()
            if "arrow" in mid:
                marker_arrow_defined = True

        # count connector primitives + arrow usage
    for el in root.iter():
        tag = el.tag.lower()
        if tag.endswith("line"):
            line_count += 1
            if "marker-end" in el.attrib:
                connectors_with_arrow += 1
        elif tag.endswith("polyline"):
            polyline_count += 1
            if "marker-end" in el.attrib:
                connectors_with_arrow += 1
        elif tag.endswith("path"):
            path_count += 1
            if "marker-end" in el.attrib:
                connectors_with_arrow += 1

    connector_total = line_count + polyline_count + path_count

    report["line_count"] = line_count
    report["polyline_count"] = polyline_count
    report["path_count"] = path_count
    report["marker_arrow_defined"] = marker_arrow_defined
    report["connector_elements_total"] = connector_total

    # rules
    if connector_total < 3:
        report["errors"].append(
            "Too few connector elements (<line>/<polyline>/<path>)."
        )
    if not marker_arrow_defined:
        report["errors"].append(
            "No arrow marker definition found (expected <marker id containing 'arrow'>)."
        )
    if connectors_with_arrow == 0:
        report["errors"].append("No connectors use marker-end arrows.")

    return report


def generate_svg_with_groq(client, system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    svg_text = response.choices[0].message.content.strip()
    svg_text = (
        svg_text.replace("```svg", "").replace("```xml", "").replace("```", "").strip()
    )
    return svg_text


def rects_overlap(a, b, padding=0):
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    # expand boxes slightly with padding to enforce spacing
    ax1 -= padding
    ay1 -= padding
    ax2 += padding
    ay2 += padding
    bx1 -= padding
    by1 -= padding
    bx2 += padding
    by2 += padding

    return not (ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1)


max_attempts = 5
attempt = 1
last_validation = None
svg_text = ""

base_user_prompt = f"Generate an educational SVG for topic: {TOPIC}"

while attempt <= max_attempts:
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

    print(f"\n--- Attempt {attempt}/{max_attempts} ---")
    svg_text = generate_svg_with_groq(client, SYSTEM_PROMPT, user_prompt)
    last_validation = validate_svg(svg_text)

    if last_validation["xml_valid"] and not last_validation["errors"]:
        print("Validation passed.")
        break
    else:
        print("Validation failed:", last_validation["errors"])
        attempt += 1


with open(f"svg/{topic_slug}_{timestamp}.svg", "w", encoding="utf-8") as f:
    f.write(svg_text)

# New: render PNG from SVG
cairosvg.svg2png(
    url=f"svg/{topic_slug}_{timestamp}.svg",
    write_to=f"img/{topic_slug}_{timestamp}.png",
)

report_path = f"reports/{topic_slug}_{timestamp}.json"

experiment_report = {
    "timestamp": timestamp,
    "topic": TOPIC,
    "model": model,
    "attempts_used": attempt if attempt <= max_attempts else max_attempts,
    "max_attempts": max_attempts,
    "validation": last_validation,
}

with open(report_path, "w", encoding="utf-8") as f:
    json.dump(experiment_report, f, indent=2)

print(f"Saved {report_path}")
