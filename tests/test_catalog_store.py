from __future__ import annotations

from helpers import sample_task
from translation_hub.catalog_store import MemoryCatalogStore


async def test_upsert_bumps_revisions_and_records_changes():
    store = MemoryCatalogStore()
    task = sample_task()
    outcome, record = await store.upsert_task(
        task, change_kind="import", changed_by="seed:test", now=100
    )
    assert outcome == "created"
    assert record["task_revision"] == 1
    first_revision = await store.catalog_revision()
    assert first_revision != "cat_bootstrap"

    task["status"] = "ready"
    outcome, record = await store.upsert_task(
        task, change_kind="status_change", changed_by="user:u1", now=200
    )
    assert outcome == "updated"
    assert record["task_revision"] == 2
    assert await store.catalog_revision() != first_revision

    changes = await store.recent_changes(limit=10)
    assert [change["change_kind"] for change in changes] == ["status_change", "import"]
    assert changes[0]["changed_by"] == "user:u1"


async def test_optimistic_concurrency_conflict():
    store = MemoryCatalogStore()
    task = sample_task()
    await store.upsert_task(task, change_kind="import", changed_by="seed:test", now=100)

    outcome, _record = await store.upsert_task(
        task,
        change_kind="update",
        changed_by="user:u1",
        expected_task_revision=99,
        now=200,
    )
    assert outcome == "revision_conflict"

    outcome, record = await store.upsert_task(
        task,
        change_kind="update",
        changed_by="user:u1",
        expected_task_revision=1,
        now=300,
    )
    assert outcome == "updated"
    assert record["task_revision"] == 2
