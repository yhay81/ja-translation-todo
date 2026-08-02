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
        "SELECT payload_json FROM tasks WHERE published = 1 ORDER BY id",
        "--json",
    ]
    if remote:
        command.append("--remote")
    else:
        command.extend(["--local", "--persist-to", persist_to])
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
        shell=sys.platform == "win32",
    )
    documents = json.loads(result.stdout)
    rows = documents[0]["results"] if documents else []
    return [json.loads(row["payload_json"]) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--persist-to", default="dist/worker/.wrangler/state")
    args = parser.parse_args()

    tasks = fetch_payloads(remote=args.remote, persist_to=args.persist_to)
    if not tasks:
        raise SystemExit("no tasks returned; refusing to wipe catalog/tasks")

    existing = {path.stem: path for path in TASKS_DIR.glob("*.json")}
    exported = set()
    for task in tasks:
        task_id = str(task["id"])
        exported.add(task_id)
        path = TASKS_DIR / f"{task_id}.json"
        path.write_text(
            json.dumps(task, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    removed = sorted(set(existing) - exported)
    for task_id in removed:
        existing[task_id].unlink()
    print(f"exported {len(exported)} tasks, removed {len(removed)} stale files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
