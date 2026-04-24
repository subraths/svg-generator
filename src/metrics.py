import csv
import sys
from pathlib import Path
from statistics import mean
import json
from datetime import datetime
from collections import defaultdict


def to_bool(v):
    return str(v).strip().lower() in {"1", "true", "yes"}


def to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def safe_mean(vals):
    return round(mean(vals), 2) if vals else 0.0


def summarize_rows(rows):
    total = len(rows)
    passed_rows = [r for r in rows if to_bool(r.get("passed", False))]
    failed_rows = [r for r in rows if not to_bool(r.get("passed", False))]

    attempts = [to_int(r.get("attempts_used", 0)) for r in rows]
    connectors = [to_int(r.get("connector_elements_total", 0)) for r in rows]
    overlaps = [to_int(r.get("overlap_count", 0)) for r in rows]
    errors = [to_int(r.get("error_count", 0)) for r in rows]
    group_counts = [to_int(r.get("group_count", 0)) for r in rows]

    pass_rate = (len(passed_rows) / total) * 100.0 if total else 0.0

    return {
        "total_topics": total,
        "passed": len(passed_rows),
        "failed": len(failed_rows),
        "pass_rate": round(pass_rate, 2),
        "avg_attempts": safe_mean(attempts),
        "avg_connectors": safe_mean(connectors),
        "avg_overlaps": safe_mean(overlaps),
        "avg_errors": safe_mean(errors),
        "avg_group_count": safe_mean(group_counts),
        "failed_topics": [
            {
                "topic": r.get("topic"),
                "mode": r.get("mode", ""),
                "error_count": to_int(r.get("error_count", 0)),
                "attempts_used": to_int(r.get("attempts_used", 0)),
                "fatal_error": r.get("fatal_error", ""),
            }
            for r in failed_rows
        ],
    }


def compute_metrics(csv_path: str):
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("No rows found in CSV.")
        return

    print("\n=== Batch Metrics (Overall) ===")
    overall = summarize_rows(rows)
    print(f"CSV: {csv_path}")
    print(f"Total runs: {overall['total_topics']}")
    print(f"Passed: {overall['passed']}")
    print(f"Failed: {overall['failed']}")
    print(f"Pass rate: {overall['pass_rate']:.2f}%")
    print(f"Avg attempts: {overall['avg_attempts']:.2f}")
    print(f"Avg connectors: {overall['avg_connectors']:.2f}")
    print(f"Avg overlaps: {overall['avg_overlaps']:.2f}")
    print(f"Avg errors: {overall['avg_errors']:.2f}")
    print(f"Avg group_count: {overall['avg_group_count']:.2f}")

    # Group by mode
    by_mode = defaultdict(list)
    for r in rows:
        by_mode[r.get("mode", "unknown")].append(r)

    mode_summaries = {}
    print("\n=== Mode-wise Comparison ===")
    for mode, mrows in by_mode.items():
        s = summarize_rows(mrows)
        mode_summaries[mode] = s
        print(
            f"\n[{mode}] total={s['total_topics']} passed={s['passed']} failed={s['failed']} "
            f"pass_rate={s['pass_rate']:.2f}% avg_attempts={s['avg_attempts']:.2f} "
            f"avg_errors={s['avg_errors']:.2f} avg_overlaps={s['avg_overlaps']:.2f}"
        )

    # Optional delta if both known modes exist
    delta = {}
    if "v1_direct" in mode_summaries and "v2_planner" in mode_summaries:
        v1 = mode_summaries["v1_direct"]
        v2 = mode_summaries["v2_planner"]
        delta = {
            "pass_rate_delta_v2_minus_v1": round(v2["pass_rate"] - v1["pass_rate"], 2),
            "avg_attempts_delta_v2_minus_v1": round(
                v2["avg_attempts"] - v1["avg_attempts"], 2
            ),
            "avg_errors_delta_v2_minus_v1": round(
                v2["avg_errors"] - v1["avg_errors"], 2
            ),
            "avg_overlaps_delta_v2_minus_v1": round(
                v2["avg_overlaps"] - v1["avg_overlaps"], 2
            ),
        }
        print("\n=== Delta (v2_planner - v1_direct) ===")
        for k, v in delta.items():
            print(f"{k}: {v}")

    summary = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "csv": csv_path,
        "overall": overall,
        "by_mode": mode_summaries,
        "delta_v2_minus_v1": delta,
    }

    out_path = f"reports/summary_{summary['timestamp']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved summary: {out_path}")

    # Print failures compactly
    all_failed = overall["failed_topics"]
    if all_failed:
        print("\nFailed runs:")
        for r in all_failed:
            print(
                f"- [{r.get('mode', '')}] {r.get('topic')} "
                f"(errors={r.get('error_count')}, attempts={r.get('attempts_used')}) "
                f"{'fatal=' + r.get('fatal_error') if r.get('fatal_error') else ''}"
            )


if __name__ == "__main__":
    # Usage:
    # python -m src.metrics reports/batch_compare_YYYYMMDD_HHMMSS.csv
    if len(sys.argv) < 2:
        files = sorted(Path("reports").glob("batch_compare_*.csv"))
        if not files:
            files = sorted(Path("reports").glob("batch_*.csv"))
        if not files:
            raise SystemExit(
                "No batch CSV found. Pass path explicitly: python -m src.metrics <csv_path>"
            )
        csv_file = str(files[-1])
    else:
        csv_file = sys.argv[1]

    compute_metrics(csv_file)
