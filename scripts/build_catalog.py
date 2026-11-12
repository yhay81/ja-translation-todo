"""Validate catalog/tasks/*.json and refresh the public schema and GitHub indexes.

The runtime catalog lives in D1 (see scripts/seed_catalog.py); this script
is the CPython-side quality gate: full Draft 2020-12 validation, unique
ids, filename/id agreement, plus a cross-check against the Worker-side
light validator so both stay in sync.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "catalog" / "tasks"
SCHEMA_PATH = ROOT / "schema" / "translation-task-v1.schema.json"
PUBLIC_SCHEMA = ROOT / "public" / "schema" / SCHEMA_PATH.name

sys.path.insert(0, str(ROOT / "src"))

from translation_hub.catalog import stars_sort_key, task_stars  # noqa: E402
from translation_hub.common import CANONICAL_ORIGIN  # noqa: E402
from translation_hub.taskschema import TaskValidationError, validate_task  # noqa: E402


def check_ready_task(task: dict[str, Any]) -> None:
    """Check the publication requirements documented in CONTRIBUTING.md."""
    if task["status"] != "ready":
        return

    kinds = {entry["kind"] for entry in task["evidence"]}
    checks = {
        "translation policy": task["permissions"]["translation"] == "explicit"
        and "translation_policy" in kinds,
        "repository evidence": "repository" in kinds,
        "existing work check": bool(kinds & {"issue", "pull_request", "team_activity"}),
        "source revision and paths": task["source"]["revision"] and task["source"]["paths"],
        "validation steps": task["validation"],
        "verification date": task["provenance"]["last_verified_at"],
    }
    missing = [label for label, confirmed in checks.items() if not confirmed]
    if missing:
        raise ValueError(f"{task['id']}: ready task is missing {', '.join(missing)}")


def load_tasks() -> list[dict[str, Any]]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    tasks: list[dict[str, Any]] = []
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
        check_ready_task(task)
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


INDEX_FILES = {
    "CSS": "css.md",
    "JavaScript": "javascript.md",
    "Python": "python.md",
    "Command Line Tools": "command-line.md",
}
INDEX_NOTE = "[カタログ](catalog/tasks/)から自動生成しています。スター数の多い順です。"


def markdown_text(value: str) -> str:
    single_line = " ".join(value.split())
    return re.sub(r"([\\`*_~\[\]#])", r"\\\1", html.escape(single_line, quote=False))


def category_indexes(tasks: list[dict[str, Any]]) -> dict[str, str]:
    by_category: dict[str, list[str]] = {}
    for task in sorted(tasks, key=stars_sort_key):
        project = task["project"]
        repo = markdown_text(project["repository"])
        title = markdown_text(task["title"]["ja"])
        stars = task_stars(task)
        count = f"★ {stars:,}" if stars is not None else "スター数未確認"
        link = f"{CANONICAL_ORIGIN}/tasks/{task['id']}"
        row = f"- [{repo} — {title}]({link}) · {count}"
        by_category.setdefault(project["category"], []).append(row)

    empty = "現在、このカテゴリのタスクはありません。"
    indexes = {}
    for category, filename in INDEX_FILES.items():
        rows = by_category.pop(category, [empty])
        indexes[filename] = "\n".join([f"# {category}", "", INDEX_NOTE, "", *rows, ""])

    lines = ["# その他のカテゴリ", "", INDEX_NOTE, ""]
    for category, rows in sorted(by_category.items()):
        lines.extend([f"## {markdown_text(category)}", "", *rows, ""])
    if not by_category:
        lines.extend([empty, ""])
    indexes["others.md"] = "\n".join(lines)
    return indexes


def write_or_check(path: Path, content: str, *, check: bool) -> None:
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"stale generated file: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    tasks = load_tasks()
    write_or_check(PUBLIC_SCHEMA, SCHEMA_PATH.read_text(encoding="utf-8"), check=args.check)
    for filename, content in category_indexes(tasks).items():
        write_or_check(ROOT / filename, content, check=args.check)
    print(f"catalog valid: {len(tasks)} tasks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
