import json
from pathlib import Path


def load_latest_summary():
    files = sorted(Path("reports").glob("summary_*.json"))
    if not files:
        raise SystemExit("No summary_*.json found in reports/. Run metrics first.")
    with open(files[-1], "r", encoding="utf-8") as f:
        return json.load(f), str(files[-1])


def main():
    # thresholds (tune as needed)
    MIN_OVERALL_PASS_RATE = 95.0
    MIN_V2_PASS_RATE = 95.0
    MAX_V2_MINUS_V1_ATTEMPTS = 0.2  # v2 should not be significantly worse on retries

    summary, path = load_latest_summary()
    print(f"Using summary: {path}")

    overall = summary.get("overall", {})
    by_mode = summary.get("by_mode", {})
    delta = summary.get("delta_v2_minus_v1", {})

    failures = []

    overall_pass = float(overall.get("pass_rate", 0.0))
    if overall_pass < MIN_OVERALL_PASS_RATE:
        failures.append(
            f"Overall pass rate too low: {overall_pass:.2f}% < {MIN_OVERALL_PASS_RATE:.2f}%"
        )

    v2 = by_mode.get("v2_planner", {})
    v2_pass = float(v2.get("pass_rate", 0.0))
    if v2_pass < MIN_V2_PASS_RATE:
        failures.append(
            f"v2_planner pass rate too low: {v2_pass:.2f}% < {MIN_V2_PASS_RATE:.2f}%"
        )

    attempts_delta = float(delta.get("avg_attempts_delta_v2_minus_v1", 0.0))
    if attempts_delta > MAX_V2_MINUS_V1_ATTEMPTS:
        failures.append(
            "v2_planner retries are too high vs v1: "
            f"{attempts_delta:.2f} > {MAX_V2_MINUS_V1_ATTEMPTS:.2f}"
        )

    if failures:
        print("\nQUALITY GATE: FAIL")
        for f in failures:
            print(f"- {f}")
        raise SystemExit(1)

    print("\nQUALITY GATE: PASS")
    print(
        f"- overall_pass_rate={overall_pass:.2f}%\n"
        f"- v2_pass_rate={v2_pass:.2f}%\n"
        f"- avg_attempts_delta_v2_minus_v1={attempts_delta:.2f}"
    )


if __name__ == "__main__":
    main()
