import xml.etree.ElementTree as ET


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
