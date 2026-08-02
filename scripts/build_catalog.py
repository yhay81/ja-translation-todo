"""Validate catalog/tasks/*.json and refresh the public schema copy.

The runtime catalog lives in D1 (see scripts/seed_catalog.py); this script
is the CPython-side quality gate: full Draft 2020-12 validation, unique
ids, filename/id agreement, plus a cross-check against the Worker-side
light validator so both stay in sync.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "catalog" / "tasks"
SCHEMA_PATH = ROOT / "schema" / "translation-task-v1.schema.json"
PUBLIC_SCHEMA = ROOT / "public" / "schema" / SCHEMA_PATH.name

sys.path.insert(0, str(ROOT / "src"))

from translation_hub.taskschema import TaskValidationError, validate_task  # noqa: E402


def load_tasks() -> list[dict[str, object]]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    tasks: list[dict[str, object]] = []
    seen: set[str] = set()

    for path in sorted(TASKS_DIR.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(task), key=lambda item: list(item.path))
        if errors:
            details = "\n".join(
                f"{path.relative_to(ROOT)}:{'/'.join(map(str, error.path))}: {error.message}"
                for error in errors
            )
            raise ValueError(details)
        try:
            validate_task(task)
        except TaskValidationError as exc:
            raise ValueError(
                f"{path.relative_to(ROOT)}: worker-side validator disagrees: {exc}"
            ) from exc
        task_id = str(task["id"])
        if task_id in seen:
            raise ValueError(f"duplicate task id: {task_id}")
        if path.stem != task_id:
            raise ValueError(f"{path.relative_to(ROOT)} must be named {task_id}.json")
        seen.add(task_id)
        tasks.append(task)

    if not tasks:
        raise ValueError("catalog must contain at least one task")
    return tasks


def write_or_check(*, check: bool) -> None:
    content = SCHEMA_PATH.read_text(encoding="utf-8")
    if check:
        if not PUBLIC_SCHEMA.exists() or PUBLIC_SCHEMA.read_text(encoding="utf-8") != content:
            raise SystemExit(f"stale schema copy: {PUBLIC_SCHEMA.relative_to(ROOT)}")
        return
    PUBLIC_SCHEMA.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_SCHEMA.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    tasks = load_tasks()
    write_or_check(check=args.check)
    print(f"catalog valid: {len(tasks)} tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
