from datetime import datetime
import json


def topic_to_slug(topic):
    return topic.lower().replace(" ", "_")


def timestamp_now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Saved file: {path}")


def save_json(report_path, report_data, type: str):
    experiment_report = report_data

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(experiment_report, f, indent=2)

    print(f"Saved {type}: {report_path}")
