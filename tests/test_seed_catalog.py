from __future__ import annotations

import sqlite3
from pathlib import Path

from helpers import sample_task
from seed_catalog import render_sql


def test_repeated_seeds_preserve_history_and_follow_publication():
    db = sqlite3.connect(":memory:")
    for migration in sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql")):
        db.executescript(migration.read_text(encoding="utf-8"))

    retained = sample_task("retained")
    restored = sample_task("restored")
    db.executescript(render_sql([retained, restored]))
    retained["title"]["ja"] = "更新したタイトル"
    for _ in range(2):
        db.executescript(render_sql([retained]))
    assert db.execute("SELECT id, task_revision FROM tasks WHERE published = 1").fetchall() == [
        ("retained", 2)
    ]

    for _ in range(2):
        db.executescript(render_sql([retained, restored]))
    assert db.execute(
        "SELECT id, task_revision FROM tasks WHERE published = 1 ORDER BY id"
    ).fetchall() == [("restored", 3), ("retained", 2)]
    assert db.execute(
        "SELECT task_id, task_revision FROM task_revisions ORDER BY task_id, task_revision"
    ).fetchall() == [
        ("restored", 1),
        ("restored", 2),
        ("restored", 3),
        ("retained", 1),
        ("retained", 2),
    ]
    db.close()
