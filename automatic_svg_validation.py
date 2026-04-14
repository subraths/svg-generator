import re
import xml.etree.ElementTree as ET


def validate_svg(svg_text: str):
    report = {
        "xml_valid": False,
        "width": None,
        "height": None,
        "group_ids": [],
        "group_count": 0,
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

    return report


validation = validate_svg(svg_text)
print("\n=== VALIDATION REPORT ===")
for k, v in validation.items():
    print(f"{k}: {v}")
