import json
import sys
from pathlib import Path


def count_templates(json_path: str) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    intents = data.get("intents", {})
    counts = {name: len(intent.get("templates", [])) for name, intent in intents.items()}
    total = sum(counts.values())

    # Pretty-print per-intent counts (sorted by count, descending)
    width = max(len(name) for name in counts) if counts else 0
    print(f"{'Intent':<{width}}  Templates")
    print(f"{'-' * width}  ---------")
    for name, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        print(f"{name:<{width}}  {count}")

    print(f"\nTotal intents:   {len(counts)}")
    print(f"Total templates: {total}")


if __name__ == "__main__":
    path = "question_templates.json"
    if not Path(path).exists():
        sys.exit(f"File not found: {path}")
    count_templates(path)