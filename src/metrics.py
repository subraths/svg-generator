import csv
import sys
from pathlib import Path
from statistics import mean
import json
from datetime import datetime


def to_bool(v):
    return str(v).strip().lower() in {"1", "true", "yes"}


def to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def compute_metrics(csv_path: str):
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("No rows found in CSV.")
        return

    total = len(rows)
    passed_rows = [r for r in rows if to_bool(r.get("passed", False))]
    failed_rows = [r for r in rows if not to_bool(r.get("passed", False))]

    attempts = [to_int(r.get("attempts_used", 0)) for r in rows]
    connectors = [to_int(r.get("connector_elements_total", 0)) for r in rows]
    overlaps = [to_int(r.get("overlap_count", 0)) for r in rows]
    errors = [to_int(r.get("error_count", 0)) for r in rows]
    group_counts = [to_int(r.get("group_count", 0)) for r in rows]

    pass_rate = (len(passed_rows) / total) * 100.0

    print("\n=== Batch Metrics ===")
    print(f"CSV: {csv_path}")
    print(f"Total topics: {total}")
    print(f"Passed: {len(passed_rows)}")
    print(f"Failed: {len(failed_rows)}")
    print(f"Pass rate: {pass_rate:.2f}%")
    print(f"Avg attempts: {mean(attempts):.2f}")
    print(f"Avg connectors: {mean(connectors):.2f}")
    print(f"Avg overlaps: {mean(overlaps):.2f}")
    print(f"Avg errors: {mean(errors):.2f}")
    print(f"Avg group_count: {mean(group_counts):.2f}")

    summary = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "csv": csv_path,
        "total_topics": total,
        "passed": len(passed_rows),
        "failed": len(failed_rows),
        "pass_rate": round(pass_rate, 2),
        "avg_attempts": round(mean(attempts), 2),
        "avg_connectors": round(mean(connectors), 2),
        "avg_overlaps": round(mean(overlaps), 2),
        "avg_errors": round(mean(errors), 2),
        "avg_group_count": round(mean(group_counts), 2),
        "failed_topics": [
            {
                "topic": r.get("topic"),
                "error_count": to_int(r.get("error_count", 0)),
                "attempts_used": to_int(r.get("attempts_used", 0)),
            }
            for r in failed_rows
        ],
    }

    out_path = f"reports/summary_{summary['timestamp']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved summary: {out_path}")

    if failed_rows:
        print("\nFailed topics:")
        for r in failed_rows:
            print(
                f"- {r.get('topic')} (errors={r.get('error_count')}, attempts={r.get('attempts_used')})"
            )


if __name__ == "__main__":
    # Usage:
    # python -m src.metrics reports/batch_YYYYMMDD_HHMMSS.csv
    if len(sys.argv) < 2:
        # fallback: pick latest batch csv
        files = sorted(Path("reports").glob("batch_*.csv"))
        if not files:
            raise SystemExit(
                "No batch CSV found. Pass path explicitly: python -m src.metrics <csv_path>"
            )
        csv_file = str(files[-1])
    else:
        csv_file = sys.argv[1]

    compute_metrics(csv_file)
