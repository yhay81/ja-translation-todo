"""Export the live D1 catalog back to catalog/tasks/*.json for git audit.

Usage:
  uv run python scripts/export_catalog.py --local
  uv run python scripts/export_catalog.py --remote
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from translation_hub.taskschema import validate_task

ROOT = Path(__file__).resolve().parents[1]
TASKS_DIR = ROOT / "catalog" / "tasks"
DATABASE = "ja-translation-todo"


def fetch_payloads(*, remote: bool, persist_to: str) -> list[dict[str, object]]:
    command = [
        "npx",
        "--yes",
        "wrangler",
        "d1",
        "execute",
        DATABASE,
        "--command",
        "SELECT id, payload_json FROM tasks WHERE published = 1 ORDER BY id",
        "--json",
    ]
    if remote:
        command.append("--remote")
    else:
        command.extend(["--local", "--persist-to", persist_to])
    result = subprocess.run(
        command,
        capture_output=True,
        encoding="utf-8",
        cwd=ROOT,
        check=True,
        shell=sys.platform == "win32",
    )
    documents = json.loads(result.stdout)
    rows = documents[0]["results"] if documents else []
    tasks = []
    for row in rows:
        task = json.loads(row["payload_json"])
        if task["id"] != row["id"]:
            raise ValueError(f"D1 row id does not match payload: {row['id']}")
        tasks.append(task)
    return tasks


def write_tasks(tasks: list[dict[str, object]], directory: Path) -> None:
    if not tasks:
        raise ValueError("no tasks returned; refusing to wipe catalog/tasks")

    existing = {path.stem: path for path in directory.glob("*.json")}
    exported = set()
    with TemporaryDirectory(dir=directory) as staging:
        for task in tasks:
            task_id = validate_task(task)["id"]
            if task_id in exported:
                raise ValueError(f"duplicate task id: {task_id}")
            exported.add(task_id)
            current = existing.get(task_id)
            if current is not None and not current.is_symlink():
                try:
                    if json.loads(current.read_text(encoding="utf-8")) == task:
                        continue
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass  # Replace a malformed local file with the validated export.
            path = Path(staging) / f"{task_id}.json"
            path.write_text(
                json.dumps(task, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )

        # Commit complete files only after every row has passed validation.
        for path in Path(staging).iterdir():
            path.replace(directory / path.name)
        removed = existing.keys() - exported
        for task_id in removed:
            existing[task_id].unlink()
    print(f"exported {len(exported)} tasks, removed {len(removed)} stale files")


def main() -> int:
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--remote", action="store_true")
    target.add_argument("--local", action="store_true")
    parser.add_argument("--persist-to", default="dist/worker/.wrangler/state")
    args = parser.parse_args()

    tasks = fetch_payloads(remote=args.remote, persist_to=args.persist_to)
    write_tasks(tasks, TASKS_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
