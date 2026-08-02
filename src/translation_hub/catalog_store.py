"""Dynamic catalog storage: D1 in production, in-memory for tests.

The store owns durability and revision bookkeeping only; filtering and
aggregation live in :mod:`translation_hub.catalog`. Every write bumps the
per-task ``task_revision`` and the global ``catalog_revision`` in the same
batch, and appends the full payload to ``task_revisions`` for audit.
"""

from __future__ import annotations

import copy
import json
import secrets
from typing import Any

from .taskschema import search_text

_TASK_COLUMNS = "id, payload_json, task_revision, created_at, updated_at"

# One isolate-wide cache shared by every D1CatalogStore instance: the row
# count is small (<200), so a single revision check per request is enough.
_D1_CACHE: dict[str, Any] = {"revision": None, "records": None}


def catalog_store_from_env(env: Any):
    if env is None:
        return None
    injected = getattr(env, "CATALOG_STORE", None)
    if injected is not None:
        return injected
    database = getattr(env, "DB", None)
    return D1CatalogStore(database) if database is not None else None


def new_catalog_revision(now: int) -> str:
    return f"cat_{now}_{secrets.token_hex(4)}"


class MemoryCatalogStore:
    """Deterministic in-memory implementation used by contract tests."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}
        self.changes: list[dict[str, Any]] = []
        self.revision = "cat_bootstrap"

    async def catalog_revision(self) -> str:
        return self.revision

    async def all_records(self) -> list[dict[str, Any]]:
        return [copy.deepcopy(record) for record in self.records.values()]

    async def get_record(self, task_id: str) -> dict[str, Any] | None:
        record = self.records.get(task_id)
        return copy.deepcopy(record) if record is not None else None

    async def upsert_task(
        self,
        payload: dict[str, Any],
        *,
        change_kind: str,
        changed_by: str,
        change_note: str | None = None,
        expected_task_revision: int | None = None,
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        current = self.records.get(payload["id"])
        if current is None:
            if expected_task_revision is not None:
                return "revision_conflict", None
            record = {
                "task": copy.deepcopy(payload),
                "task_revision": 1,
                "created_at": now,
                "updated_at": now,
            }
            outcome = "created"
        else:
            if (
                expected_task_revision is not None
                and current["task_revision"] != expected_task_revision
            ):
                return "revision_conflict", copy.deepcopy(current)
            record = {
                "task": copy.deepcopy(payload),
                "task_revision": current["task_revision"] + 1,
                "created_at": current["created_at"],
                "updated_at": now,
            }
            outcome = "updated"
        self.records[payload["id"]] = record
        self.changes.append(
            {
                "task_id": payload["id"],
                "task_revision": record["task_revision"],
                "payload": copy.deepcopy(payload),
                "change_kind": change_kind,
                "changed_by": changed_by,
                "change_note": change_note,
                "created_at": now,
            }
        )
        self.revision = new_catalog_revision(now)
        return outcome, copy.deepcopy(record)

    async def recent_changes(self, *, limit: int = 50) -> list[dict[str, Any]]:
        ordered = sorted(
            self.changes,
            key=lambda change: (change["created_at"], change["task_revision"]),
            reverse=True,
        )
        return [copy.deepcopy(change) for change in ordered[:limit]]


class D1CatalogStore:
    """Cloudflare D1 implementation with an isolate-level record cache."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def catalog_revision(self) -> str:
        row = await self._first("SELECT catalog_revision FROM catalog_meta WHERE id = 1")
        return str(row["catalog_revision"]) if row is not None else "cat_bootstrap"

    async def all_records(self) -> list[dict[str, Any]]:
        revision = await self.catalog_revision()
        if _D1_CACHE["revision"] == revision and _D1_CACHE["records"] is not None:
            return _D1_CACHE["records"]
        result = await self._run(
            f"SELECT {_TASK_COLUMNS} FROM tasks WHERE published = 1 ORDER BY id"
        )
        rows = _rows(result)
        records = [_record(row) for row in rows]
        _D1_CACHE["revision"] = revision
        _D1_CACHE["records"] = records
        return records

    async def get_record(self, task_id: str) -> dict[str, Any] | None:
        row = await self._first(
            f"SELECT {_TASK_COLUMNS} FROM tasks WHERE id = ?1 AND published = 1",
            task_id,
        )
        return _record(row) if row is not None else None

    async def upsert_task(
        self,
        payload: dict[str, Any],
        *,
        change_kind: str,
        changed_by: str,
        change_note: str | None = None,
        expected_task_revision: int | None = None,
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        current = await self._first(
            "SELECT task_revision, created_at FROM tasks WHERE id = ?1",
            payload["id"],
        )
        if current is None:
            if expected_task_revision is not None:
                return "revision_conflict", None
            next_revision = 1
            outcome = "created"
        else:
            current_revision = int(current["task_revision"])
            if expected_task_revision is not None and current_revision != expected_task_revision:
                return "revision_conflict", await self.get_record(payload["id"])
            next_revision = current_revision + 1
            outcome = "updated"

        payload_json = _dumps(payload)
        statements = [
            self.database.prepare(
                """
                INSERT INTO tasks
                  (id, kind, status, repository, category, title_ja, automation_level,
                   search_text, payload_json, task_revision, published, created_at, updated_at)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, 1, ?11, ?11)
                ON CONFLICT(id) DO UPDATE SET
                  kind = excluded.kind,
                  status = excluded.status,
                  repository = excluded.repository,
                  category = excluded.category,
                  title_ja = excluded.title_ja,
                  automation_level = excluded.automation_level,
                  search_text = excluded.search_text,
                  payload_json = excluded.payload_json,
                  task_revision = ?10,
                  updated_at = ?11
                WHERE tasks.task_revision = ?10 - 1
                """
            ).bind(
                payload["id"],
                payload["kind"],
                payload["status"],
                payload["project"]["repository"],
                payload["project"]["category"],
                payload["title"]["ja"],
                payload["automation"]["level"],
                search_text(payload),
                payload_json,
                next_revision,
                now,
            ),
            self.database.prepare(
                """
                INSERT OR IGNORE INTO task_revisions
                  (task_id, task_revision, payload_json, change_kind, changed_by,
                   change_note, created_at)
                SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7
                 WHERE EXISTS (
                   SELECT 1 FROM tasks WHERE id = ?1 AND task_revision = ?2
                 )
                """
            ).bind(
                payload["id"],
                next_revision,
                payload_json,
                change_kind,
                changed_by,
                change_note,
                now,
            ),
            self.database.prepare(
                """
                UPDATE catalog_meta
                   SET catalog_revision = ?1, updated_at = ?2
                 WHERE id = 1
                   AND EXISTS (
                     SELECT 1 FROM tasks WHERE id = ?3 AND task_revision = ?4
                   )
                """
            ).bind(new_catalog_revision(now), now, payload["id"], next_revision),
        ]
        await self.database.batch(statements)

        stored = await self._first(
            f"SELECT {_TASK_COLUMNS} FROM tasks WHERE id = ?1",
            payload["id"],
        )
        _D1_CACHE["revision"] = None
        _D1_CACHE["records"] = None
        if stored is None or int(stored["task_revision"]) != next_revision:
            return "revision_conflict", _record(stored) if stored is not None else None
        return outcome, _record(stored)

    async def recent_changes(self, *, limit: int = 50) -> list[dict[str, Any]]:
        result = await self._run(
            """
            SELECT task_id, task_revision, payload_json, change_kind, changed_by,
                   change_note, created_at
              FROM task_revisions
             ORDER BY created_at DESC, task_revision DESC
             LIMIT ?1
            """,
            limit,
        )
        changes = []
        for row in _rows(result):
            changes.append(
                {
                    "task_id": row["task_id"],
                    "task_revision": int(row["task_revision"]),
                    "payload": json.loads(row["payload_json"]),
                    "change_kind": row["change_kind"],
                    "changed_by": row["changed_by"],
                    "change_note": row["change_note"],
                    "created_at": int(row["created_at"]),
                }
            )
        return changes

    async def _first(self, sql: str, *parameters: Any) -> dict[str, Any] | None:
        statement = self.database.prepare(sql)
        if parameters:
            statement = statement.bind(*parameters)
        return _mapping(await statement.first())

    async def _run(self, sql: str, *parameters: Any) -> Any:
        statement = self.database.prepare(sql)
        if parameters:
            statement = statement.bind(*parameters)
        return await statement.run()


def _record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": json.loads(row["payload_json"]),
        "task_revision": int(row["task_revision"]),
        "created_at": int(row["created_at"]),
        "updated_at": int(row["updated_at"]),
    }


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rows(result: Any) -> list[dict[str, Any]]:
    values = getattr(result, "results", None)
    if values is None and isinstance(result, dict):
        values = result.get("results")
    values = _to_python(values)
    return [_mapping(row) or {} for row in values or []]


def _mapping(value: Any) -> dict[str, Any] | None:
    value = _to_python(value)
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): _to_python(item) for key, item in value.items()}
    try:
        return {str(key): _to_python(item) for key, item in dict(value).items()}
    except (TypeError, ValueError) as exc:
        raise TypeError(f"expected a D1 row mapping, got {type(value).__name__}") from exc


def _to_python(value: Any) -> Any:
    converter = getattr(value, "to_py", None)
    return converter() if converter is not None else value
