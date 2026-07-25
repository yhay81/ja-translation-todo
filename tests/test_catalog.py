from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from translation_hub.catalog import CATALOG_REVISION, TASKS, catalog_stats, search_tasks

ROOT = Path(__file__).resolve().parents[1]


def test_every_source_task_matches_schema():
    schema = json.loads(
        (ROOT / "schema" / "translation-task-v1.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    paths = sorted((ROOT / "catalog" / "tasks").glob("*.json"))
    assert len(paths) == len(TASKS)
    for path in paths:
        task = json.loads(path.read_text(encoding="utf-8"))
        assert not list(validator.iter_errors(task)), path
        assert task["id"] == path.stem


def test_imported_tasks_cannot_trigger_translation():
    assert TASKS
    for task in TASKS:
        if task["provenance"]["imported_from"] == "docs/legacy-list.md":
            assert task["status"] == "needs_verification"
            assert task["kind"] == "verification"
            assert task["automation"]["level"] == "discover_only"
            assert task["source"]["revision"] is None


def test_search_is_filtered_and_paginated():
    result = search_tasks(category="JavaScript", kind="verification", offset=0, limit=2)
    assert result["catalog_revision"] == CATALOG_REVISION
    assert result["total"] >= 2
    assert len(result["items"]) == 2
    assert result["next_cursor"] == "2"
    assert all(item["project"]["category"] == "JavaScript" for item in result["items"])


def test_stats_match_catalog():
    stats = catalog_stats()
    assert stats["total"] == len(TASKS)
    assert sum(stats["by_status"].values()) == len(TASKS)
    assert sum(stats["by_kind"].values()) == len(TASKS)
