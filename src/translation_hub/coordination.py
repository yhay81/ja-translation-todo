"""Idempotent task claims and evidence reports backed by Cloudflare D1."""

from __future__ import annotations

import copy
import json
from typing import Any

CLAIM_STATES = frozenset({"active", "released", "completed", "expired"})

_CLAIM_COLUMNS = (
    "id",
    "task_id",
    "agent_id",
    "idempotency_key",
    "request_hash",
    "claim_token_hash",
    "catalog_revision",
    "state",
    "lease_expires_at",
    "created_at",
    "updated_at",
    "release_idempotency_key",
    "release_request_hash",
    "release_reason",
)
_CLAIM_SELECT = ", ".join(_CLAIM_COLUMNS)


def store_from_env(env: Any) -> MemoryCoordinationStore | D1CoordinationStore | None:
    """Resolve an injected test store or the production D1 binding."""
    if env is None:
        return None
    injected = getattr(env, "COORDINATION_STORE", None)
    if injected is not None:
        return injected
    database = getattr(env, "DB", None)
    return D1CoordinationStore(database) if database is not None else None


class MemoryCoordinationStore:
    """Deterministic in-memory implementation used by contract tests."""

    def __init__(self) -> None:
        self.claims: dict[str, dict[str, Any]] = {}
        self.lease_events: dict[tuple[str, str], dict[str, Any]] = {}
        self.reports: dict[tuple[str, str], dict[str, Any]] = {}

    async def claim_task(
        self,
        *,
        claim: dict[str, Any],
        now: int,
    ) -> tuple[str, dict[str, Any]]:
        for current in self.claims.values():
            if current["state"] == "active" and current["lease_expires_at"] <= now:
                current["state"] = "expired"
                current["updated_at"] = now

        for current in self.claims.values():
            if (
                current["agent_id"] == claim["agent_id"]
                and current["idempotency_key"] == claim["idempotency_key"]
            ):
                if current["request_hash"] != claim["request_hash"]:
                    return "idempotency_conflict", _clone(current)
                return "replayed", _clone(current)

        for current in self.claims.values():
            if current["task_id"] == claim["task_id"] and current["state"] == "active":
                return "already_claimed", _clone(current)

        self.claims[claim["id"]] = _clone(claim)
        return "created", _clone(claim)

    async def get_claim(self, claim_id: str, *, now: int) -> dict[str, Any] | None:
        claim = self.claims.get(claim_id)
        if claim is None:
            return None
        if claim["state"] == "active" and claim["lease_expires_at"] <= now:
            claim["state"] = "expired"
            claim["updated_at"] = now
        return _clone(claim)

    async def renew_claim(
        self,
        *,
        claim_id: str,
        event_id: str,
        idempotency_key: str,
        request_hash: str,
        lease_expires_at: int,
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        event_key = (claim_id, idempotency_key)
        event = self.lease_events.get(event_key)
        if event is not None:
            if event["request_hash"] != request_hash:
                return "idempotency_conflict", _clone(event)
            return "replayed", _clone(event)

        claim = await self.get_claim(claim_id, now=now)
        if claim is None or claim["state"] != "active":
            return "claim_not_active", None

        event = {
            "id": event_id,
            "claim_id": claim_id,
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "lease_expires_at": lease_expires_at,
            "applied": 1,
            "created_at": now,
        }
        self.lease_events[event_key] = event
        self.claims[claim_id]["lease_expires_at"] = lease_expires_at
        self.claims[claim_id]["updated_at"] = now
        return "renewed", _clone(event)

    async def release_claim(
        self,
        *,
        claim_id: str,
        idempotency_key: str,
        request_hash: str,
        reason: str | None,
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        claim = await self.get_claim(claim_id, now=now)
        if claim is None:
            return "claim_not_found", None
        if claim["release_idempotency_key"] == idempotency_key:
            if claim["release_request_hash"] != request_hash:
                return "idempotency_conflict", claim
            return "replayed", claim
        if claim["state"] != "active":
            return "claim_not_active", claim

        stored = self.claims[claim_id]
        stored.update(
            {
                "state": "released",
                "updated_at": now,
                "release_idempotency_key": idempotency_key,
                "release_request_hash": request_hash,
                "release_reason": reason,
            }
        )
        return "released", _clone(stored)

    async def create_report(
        self,
        *,
        report: dict[str, Any],
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        report_key = (report["claim_id"], report["idempotency_key"])
        existing = self.reports.get(report_key)
        if existing is not None:
            if existing["request_hash"] != report["request_hash"]:
                return "idempotency_conflict", _decode_report(_clone(existing))
            return "replayed", _decode_report(_clone(existing))

        claim = await self.get_claim(report["claim_id"], now=now)
        if claim is None or claim["state"] != "active":
            return "claim_not_active", None

        self.reports[report_key] = _clone(report)
        self.claims[report["claim_id"]]["state"] = "completed"
        self.claims[report["claim_id"]]["updated_at"] = now
        return "created", _decode_report(_clone(report))

    async def latest_report(self, claim_id: str) -> dict[str, Any] | None:
        reports = [report for report in self.reports.values() if report["claim_id"] == claim_id]
        if not reports:
            return None
        return _decode_report(_clone(max(reports, key=lambda item: item["created_at"])))


class D1CoordinationStore:
    """Cloudflare D1 implementation using prepared statements only."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def claim_task(
        self,
        *,
        claim: dict[str, Any],
        now: int,
    ) -> tuple[str, dict[str, Any]]:
        await self._run(
            """
            UPDATE claims
               SET state = 'expired', updated_at = ?1
             WHERE task_id = ?2 AND state = 'active' AND lease_expires_at <= ?1
            """,
            now,
            claim["task_id"],
        )
        existing = await self._first(
            f"""
            SELECT {_CLAIM_SELECT}
              FROM claims
             WHERE agent_id = ?1 AND idempotency_key = ?2
            """,
            claim["agent_id"],
            claim["idempotency_key"],
        )
        if existing is not None:
            if existing["request_hash"] != claim["request_hash"]:
                return "idempotency_conflict", existing
            return "replayed", existing

        placeholders = ", ".join(f"?{index}" for index in range(1, len(_CLAIM_COLUMNS) + 1))
        rows = await self._run_rows(
            f"""
            INSERT OR IGNORE INTO claims ({_CLAIM_SELECT})
            VALUES ({placeholders})
            RETURNING {_CLAIM_SELECT}
            """,
            *(claim[column] for column in _CLAIM_COLUMNS),
        )
        if rows:
            return "created", rows[0]

        existing = await self._first(
            f"""
            SELECT {_CLAIM_SELECT}
              FROM claims
             WHERE agent_id = ?1 AND idempotency_key = ?2
            """,
            claim["agent_id"],
            claim["idempotency_key"],
        )
        if existing is not None:
            if existing["request_hash"] != claim["request_hash"]:
                return "idempotency_conflict", existing
            return "replayed", existing

        active = await self._first(
            f"""
            SELECT {_CLAIM_SELECT}
              FROM claims
             WHERE task_id = ?1 AND state = 'active'
            """,
            claim["task_id"],
        )
        if active is None:
            raise RuntimeError("D1 did not return an inserted or conflicting claim")
        return "already_claimed", active

    async def get_claim(self, claim_id: str, *, now: int) -> dict[str, Any] | None:
        await self._run(
            """
            UPDATE claims
               SET state = 'expired', updated_at = ?1
             WHERE id = ?2 AND state = 'active' AND lease_expires_at <= ?1
            """,
            now,
            claim_id,
        )
        return await self._first(
            f"SELECT {_CLAIM_SELECT} FROM claims WHERE id = ?1",
            claim_id,
        )

    async def renew_claim(
        self,
        *,
        claim_id: str,
        event_id: str,
        idempotency_key: str,
        request_hash: str,
        lease_expires_at: int,
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        existing = await self._first(
            """
            SELECT id, claim_id, idempotency_key, request_hash, lease_expires_at,
                   applied, created_at
              FROM lease_events
             WHERE claim_id = ?1 AND idempotency_key = ?2
            """,
            claim_id,
            idempotency_key,
        )
        if existing is not None:
            if existing["request_hash"] != request_hash:
                return "idempotency_conflict", existing
            return "replayed", existing

        await self.database.batch(
            [
                self.database.prepare(
                    """
                    INSERT OR IGNORE INTO lease_events
                      (id, claim_id, idempotency_key, request_hash,
                       lease_expires_at, applied, created_at)
                    VALUES (?1, ?2, ?3, ?4, ?5, 0, ?6)
                    """
                ).bind(
                    event_id,
                    claim_id,
                    idempotency_key,
                    request_hash,
                    lease_expires_at,
                    now,
                ),
                self.database.prepare(
                    """
                    UPDATE claims
                       SET lease_expires_at = ?1, updated_at = ?2
                     WHERE id = ?3 AND state = 'active' AND lease_expires_at > ?2
                       AND EXISTS (
                         SELECT 1 FROM lease_events
                          WHERE claim_id = ?3 AND idempotency_key = ?4 AND applied = 0
                       )
                    """
                ).bind(lease_expires_at, now, claim_id, idempotency_key),
                self.database.prepare(
                    """
                    UPDATE lease_events
                       SET applied = 1
                     WHERE claim_id = ?1 AND idempotency_key = ?2 AND applied = 0
                       AND EXISTS (
                         SELECT 1 FROM claims
                          WHERE id = ?1 AND state = 'active'
                            AND lease_expires_at = lease_events.lease_expires_at
                       )
                    """
                ).bind(claim_id, idempotency_key),
            ]
        )
        event = await self._first(
            """
            SELECT id, claim_id, idempotency_key, request_hash, lease_expires_at,
                   applied, created_at
              FROM lease_events
             WHERE claim_id = ?1 AND idempotency_key = ?2
            """,
            claim_id,
            idempotency_key,
        )
        if event is None or not event["applied"]:
            return "claim_not_active", event
        if event["request_hash"] != request_hash:
            return "idempotency_conflict", event
        return "renewed", event

    async def release_claim(
        self,
        *,
        claim_id: str,
        idempotency_key: str,
        request_hash: str,
        reason: str | None,
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        claim = await self.get_claim(claim_id, now=now)
        if claim is None:
            return "claim_not_found", None
        if claim["release_idempotency_key"] == idempotency_key:
            if claim["release_request_hash"] != request_hash:
                return "idempotency_conflict", claim
            return "replayed", claim
        if claim["state"] != "active":
            return "claim_not_active", claim

        rows = await self._run_rows(
            f"""
            UPDATE claims
               SET state = 'released',
                   updated_at = ?1,
                   release_idempotency_key = ?2,
                   release_request_hash = ?3,
                   release_reason = ?4
             WHERE id = ?5 AND state = 'active' AND lease_expires_at > ?1
            RETURNING {_CLAIM_SELECT}
            """,
            now,
            idempotency_key,
            request_hash,
            reason,
            claim_id,
        )
        if rows:
            return "released", rows[0]
        latest = await self.get_claim(claim_id, now=now)
        return "claim_not_active", latest

    async def create_report(
        self,
        *,
        report: dict[str, Any],
        now: int,
    ) -> tuple[str, dict[str, Any] | None]:
        existing = await self._report(report["claim_id"], report["idempotency_key"])
        if existing is not None:
            if existing["request_hash"] != report["request_hash"]:
                return "idempotency_conflict", existing
            return "replayed", existing

        await self.database.batch(
            [
                self.database.prepare(
                    """
                    INSERT OR IGNORE INTO reports
                      (id, claim_id, idempotency_key, request_hash, payload_json, created_at)
                    SELECT ?1, ?2, ?3, ?4, ?5, ?6
                     WHERE EXISTS (
                       SELECT 1 FROM claims
                        WHERE id = ?2 AND state = 'active' AND lease_expires_at > ?6
                     )
                    """
                ).bind(
                    report["id"],
                    report["claim_id"],
                    report["idempotency_key"],
                    report["request_hash"],
                    report["payload_json"],
                    report["created_at"],
                ),
                self.database.prepare(
                    """
                    UPDATE claims
                       SET state = 'completed', updated_at = ?1
                     WHERE id = ?2 AND state = 'active'
                       AND EXISTS (
                         SELECT 1 FROM reports
                          WHERE claim_id = ?2 AND idempotency_key = ?3
                       )
                    """
                ).bind(now, report["claim_id"], report["idempotency_key"]),
            ]
        )
        stored = await self._report(report["claim_id"], report["idempotency_key"])
        if stored is None:
            return "claim_not_active", None
        if stored["request_hash"] != report["request_hash"]:
            return "idempotency_conflict", stored
        return "created", stored

    async def latest_report(self, claim_id: str) -> dict[str, Any] | None:
        row = await self._first(
            """
            SELECT id, claim_id, idempotency_key, request_hash, payload_json, created_at
              FROM reports
             WHERE claim_id = ?1
             ORDER BY created_at DESC
             LIMIT 1
            """,
            claim_id,
        )
        return _decode_report(row)

    async def _report(self, claim_id: str, idempotency_key: str) -> dict[str, Any] | None:
        row = await self._first(
            """
            SELECT id, claim_id, idempotency_key, request_hash, payload_json, created_at
              FROM reports
             WHERE claim_id = ?1 AND idempotency_key = ?2
            """,
            claim_id,
            idempotency_key,
        )
        return _decode_report(row)

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

    async def _run_rows(self, sql: str, *parameters: Any) -> list[dict[str, Any]]:
        result = await self._run(sql, *parameters)
        values = getattr(result, "results", None)
        if values is None and isinstance(result, dict):
            values = result.get("results")
        values = _to_python(values)
        return [_mapping(row) or {} for row in values or []]


def _decode_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if report is None:
        return None
    decoded = dict(report)
    decoded["payload"] = json.loads(decoded.pop("payload_json"))
    return decoded


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


def _clone(value: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(value)
