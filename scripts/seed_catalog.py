"""Seed or update the D1 catalog from catalog/tasks/*.json.

Generates one UPSERT statement per task (existing rows get task_revision+1
and a task_revisions audit entry with change_kind 'import'), bumps
catalog_meta, and either prints the SQL or pipes it through wrangler.

Usage:
  uv run python scripts/seed_catalog.py --out seed.sql
  uv run python scripts/seed_catalog.py --apply --local
  uv run python scripts/seed_catalog.py --apply --remote
"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_catalog import load_tasks  # noqa: E402
from translation_hub.taskschema import search_text  # noqa: E402

DATABASE = "ja-translation-todo"


def sql_quote(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def git_revision() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def render_sql(tasks: list[dict[str, object]]) -> str:
    now = int(time.time())
    changed_by = f"seed:{git_revision()}"
    statements: list[str] = []
    for task in tasks:
        payload = json.dumps(task, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        project = task["project"]
        quoted = [
            sql_quote(str(task["id"])),
            sql_quote(str(task["kind"])),
            sql_quote(str(task["status"])),
            sql_quote(str(project["repository"])),
            sql_quote(str(project["category"])),
            sql_quote(str(task["title"]["ja"])),
            sql_quote(str(task["automation"]["level"])),
            sql_quote(search_text(task)),
            sql_quote(payload),
        ]
        values = ", ".join([*quoted, "1", "1", str(now), str(now)])
        statements.append(
            "INSERT INTO tasks (id, kind, status, repository, category, title_ja,"
            " automation_level, search_text, payload_json, task_revision, published,"
            f" created_at, updated_at)\nVALUES ({values})\n"
            "ON CONFLICT(id) DO UPDATE SET\n"
            "  kind = excluded.kind, status = excluded.status,\n"
            "  repository = excluded.repository, category = excluded.category,\n"
            "  title_ja = excluded.title_ja, automation_level = excluded.automation_level,\n"
            "  search_text = excluded.search_text, payload_json = excluded.payload_json,\n"
            f"  task_revision = tasks.task_revision + 1, updated_at = {now}\n"
            "WHERE excluded.payload_json != tasks.payload_json;"
        )
        statements.append(
            "INSERT OR IGNORE INTO task_revisions (task_id, task_revision, payload_json,"
            " change_kind, changed_by, change_note, created_at)\n"
            f"SELECT id, task_revision, {sql_quote(payload)}, 'import',"
            f" {sql_quote(changed_by)}, NULL, {now}\n"
            f"  FROM tasks WHERE id = {sql_quote(str(task['id']))}"
            f" AND payload_json = {sql_quote(payload)};"
        )
    revision = f"cat_{now}_{secrets.token_hex(4)}"
    statements.append(
        f"UPDATE catalog_meta SET catalog_revision = {sql_quote(revision)},"
        f" updated_at = {now} WHERE id = 1;"
    )
    return "\n".join(statements) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, help="write SQL to this file")
    parser.add_argument("--apply", action="store_true", help="run via wrangler d1 execute")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--remote", action="store_true")
    parser.add_argument(
        "--persist-to",
        default="dist/worker/.wrangler/state",
        help="wrangler state dir for --local",
    )
    args = parser.parse_args()

    tasks = load_tasks()
    sql = render_sql(tasks)
    out_path = args.out or (ROOT / "dist" / "seed_catalog.sql")
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sql, encoding="utf-8", newline="\n")
    print(f"wrote {out_path} ({len(tasks)} tasks)")

    if args.apply:
        command = ["npx", "--yes", "wrangler", "d1", "execute", DATABASE, "--file", str(out_path)]
        if args.remote:
            command.append("--remote")
        else:
            command.extend(["--local", "--persist-to", args.persist_to])
        print("$", " ".join(command))
        completed = subprocess.run(command, cwd=ROOT, check=False, shell=sys.platform == "win32")
        return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
