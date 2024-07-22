import json
from pathlib import Path


def load_config(config_path: Path) -> dict:
    """Load a JSON configuration file."""
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f.readlines()]
