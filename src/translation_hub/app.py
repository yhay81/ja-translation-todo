"""Hayate application exposing Web API, OpenAPI, and Remote MCP."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit

from hayate import Context, Hayate
from hayate_openapi import OpenApi, describe, validated

from . import __version__
from .catalog import (
    CATALOG_REVISION,
    KINDS,
    STATUSES,
    catalog_stats,
    get_task,
    search_tasks,
    task_bundle,
)
from .coordination import store_from_env

app = Hayate()

AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,63}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
REPORT_OUTCOMES = frozenset({"evidence_found", "no_policy_found", "blocked", "stale"})
RECOMMENDED_STATUSES = frozenset({"needs_verification", "ready", "ask_first", "blocked", "stale"})
EVIDENCE_KINDS = frozenset(
    {
        "repository",
        "translation_policy",
        "ai_policy",
        "issue",
        "pull_request",
        "contributing",
        "validation",
    }
)
DEFAULT_LEASE_SECONDS = 900
MIN_LEASE_SECONDS = 300
MAX_LEASE_SECONDS = 3600

CLAIM_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["agent_id", "catalog_revision"],
    "properties": {
        "agent_id": {
            "type": "string",
            "pattern": AGENT_ID_PATTERN.pattern,
            "minLength": 3,
            "maxLength": 64,
        },
        "catalog_revision": {"type": "string", "minLength": 1},
        "lease_seconds": {
            "type": "integer",
            "minimum": MIN_LEASE_SECONDS,
            "maximum": MAX_LEASE_SECONDS,
            "default": DEFAULT_LEASE_SECONDS,
        },
    },
}
LEASE_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "lease_seconds": {
            "type": "integer",
            "minimum": MIN_LEASE_SECONDS,
            "maximum": MAX_LEASE_SECONDS,
            "default": DEFAULT_LEASE_SECONDS,
        }
    },
}
RELEASE_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"reason": {"type": ["string", "null"], "maxLength": 500}},
}
REPORT_REQUEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outcome", "summary_ja"],
    "properties": {
        "outcome": {"type": "string", "enum": sorted(REPORT_OUTCOMES)},
        "summary_ja": {"type": "string", "minLength": 1, "maxLength": 4_000},
        "evidence": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["url", "kind", "observed_at", "note_ja"],
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "kind": {"type": "string", "enum": sorted(EVIDENCE_KINDS)},
                    "observed_at": {"type": "string", "format": "date"},
                    "note_ja": {"type": "string", "minLength": 1, "maxLength": 2_000},
                },
            },
        },
        "recommended_status": {
            "type": ["string", "null"],
            "enum": [*sorted(RECOMMENDED_STATUSES), None],
        },
        "external_actions_performed": {
            "type": "array",
            "maxItems": 10,
            "items": {"type": "string", "maxLength": 500},
        },
    },
}

SEARCH_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "catalog_revision", "total", "items"],
    "properties": {
        "schema_version": {"const": "translation-task-search/v1"},
        "catalog_revision": {"type": "string"},
        "total": {"type": "integer"},
        "next_cursor": {"type": ["string", "null"]},
        "items": {"type": "array", "items": {"type": "object"}},
    },
}


@app.get("/healthz")
@describe(summary="Service health", tags=["system"])
async def health(c: Context):
    return c.json(
        {
            "status": "ok",
            "service": "ja-translation-todo",
            "version": __version__,
            "catalog_revision": CATALOG_REVISION,
            "tasks": catalog_stats()["total"],
        },
        headers={"cache-control": "no-store"},
    )


@app.get("/api/v1")
@describe(summary="API discovery document", tags=["system"])
async def api_root(c: Context):
    write_available = _write_available(c.env)
    return c.json(
        {
            "service": "ja-translation-todo",
            "version": __version__,
            "catalog_revision": CATALOG_REVISION,
            "capabilities": {
                "read": True,
                "claim": write_available,
                "lease_renewal": write_available,
                "result_reporting": write_available,
            },
            "links": {
                "tasks": "/api/v1/tasks",
                "claim_template": "/api/v1/tasks/{task_id}/claims",
                "claim_status_template": "/api/v1/claims/{claim_id}",
                "claim_renew_template": "/api/v1/claims/{claim_id}/renew",
                "claim_release_template": "/api/v1/claims/{claim_id}/release",
                "report_template": "/api/v1/claims/{claim_id}/reports",
                "openapi": "/openapi.json",
                "mcp": "/mcp",
                "static_catalog": "/tasks.json",
                "schema": "/schema/translation-task-v1.schema.json",
                "agent_instructions": "/llms.txt",
            },
            "write_contract": {
                "authentication": "Bearer agent API token",
                "idempotency_header": "Idempotency-Key",
                "claim_token_header": "X-Claim-Token",
                "default_lease_seconds": DEFAULT_LEASE_SECONDS,
                "maximum_lease_seconds": MAX_LEASE_SECONDS,
                "reports_are_untrusted_until_reviewed": True,
            },
        }
    )


@app.get("/api/v1/stats")
@describe(summary="Catalog statistics", tags=["tasks"])
async def stats(c: Context):
    return c.json(
        {
            "catalog_revision": CATALOG_REVISION,
            **catalog_stats(),
        }
    )


@app.get("/api/v1/tasks")
@describe(
    summary="Search translation tasks",
    tags=["tasks"],
    response=SEARCH_RESPONSE_SCHEMA,
    responses={400: None},
)
async def list_tasks(c: Context):
    status = c.req.query("status")
    kind = c.req.query("kind")
    if status is not None and status not in STATUSES:
        return problem(c, 400, "invalid_status", f"Unknown status: {status}")
    if kind is not None and kind not in KINDS:
        return problem(c, 400, "invalid_kind", f"Unknown kind: {kind}")

    limit = parse_integer(c.req.query("limit"), default=50, minimum=1, maximum=100)
    offset = parse_integer(c.req.query("cursor"), default=0, minimum=0, maximum=1_000_000)
    if limit is None:
        return problem(c, 400, "invalid_limit", "limit must be an integer from 1 to 100")
    if offset is None:
        return problem(c, 400, "invalid_cursor", "cursor must be a non-negative integer")

    result = search_tasks(
        query=c.req.query("q"),
        status=status,
        kind=kind,
        category=c.req.query("category"),
        offset=offset,
        limit=limit,
    )
    result["items"] = [task_bundle(task) for task in result["items"]]
    return c.json(
        result,
        headers={
            "cache-control": "public, max-age=60, stale-while-revalidate=300",
            "etag": f'"{CATALOG_REVISION}"',
        },
    )


@app.get("/api/v1/tasks/:id")
@describe(summary="Get a translation task", tags=["tasks"], responses={404: None})
async def show_task(c: Context):
    task = get_task(c.req.param("id"))
    if task is None:
        return problem(c, 404, "task_not_found", "The requested task does not exist.")
    return c.json(task_bundle(task), headers={"etag": f'"{CATALOG_REVISION}"'})


@app.get("/api/v1/tasks/:id/bundle")
@describe(summary="Get an agent-ready task bundle", tags=["tasks"], responses={404: None})
async def show_bundle(c: Context):
    task = get_task(c.req.param("id"))
    if task is None:
        return problem(c, 404, "task_not_found", "The requested task does not exist.")
    return c.json(
        task_bundle(task),
        headers={
            "cache-control": "public, max-age=60, stale-while-revalidate=300",
            "etag": f'"{CATALOG_REVISION}"',
        },
    )


@app.post("/api/v1/tasks/:id/claims", validated("json", CLAIM_REQUEST_SCHEMA))
@describe(
    summary="Claim a task lease",
    description=(
        "Requires Bearer authentication and Idempotency-Key. "
        "The request must use the catalog_revision from a fresh task bundle."
    ),
    tags=["coordination"],
    responses={400: None, 401: None, 409: None, 429: None, 503: None},
)
async def create_claim(c: Context):
    store, bearer_token, error = _write_prerequisites(c)
    if error is not None:
        return error

    task = get_task(c.req.param("id"))
    if task is None:
        return problem(c, 404, "task_not_found", "The requested task does not exist.")
    if task["status"] in {"blocked", "done"} or task["automation"]["level"] == "blocked":
        return problem(c, 409, "task_not_claimable", "The task is not open for agent work.")

    payload, error = await _json_object(c)
    if error is not None:
        return error
    error = _reject_unknown_fields(c, payload, {"agent_id", "catalog_revision", "lease_seconds"})
    if error is not None:
        return error
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not AGENT_ID_PATTERN.fullmatch(agent_id):
        return problem(
            c,
            422,
            "invalid_agent_id",
            (
                "agent_id must be 3-64 characters using letters, digits, "
                "dot, colon, dash, or underscore."
            ),
        )
    requested_revision = payload.get("catalog_revision")
    if requested_revision != CATALOG_REVISION:
        return problem(
            c,
            409,
            "catalog_revision_mismatch",
            "Fetch a fresh task bundle and claim its catalog_revision.",
        )
    lease_seconds = _lease_seconds(payload.get("lease_seconds"))
    if lease_seconds is None:
        return problem(
            c,
            422,
            "invalid_lease",
            f"lease_seconds must be an integer from {MIN_LEASE_SECONDS} to {MAX_LEASE_SECONDS}.",
        )
    idempotency_key, error = _idempotency_key(c)
    if error is not None:
        return error
    if not await _within_write_limit(c, agent_id):
        return problem(
            c,
            429,
            "rate_limited",
            "The authenticated agent exceeded the write rate limit.",
            headers={"retry-after": "60"},
        )

    request_body = {
        "agent_id": agent_id,
        "catalog_revision": requested_revision,
        "lease_seconds": lease_seconds,
    }
    request_hash = _request_hash(request_body)
    now = _now()
    claim_id = f"clm_{secrets.token_urlsafe(18)}"
    claim_token = _claim_token(bearer_token, claim_id, agent_id)
    claim = {
        "id": claim_id,
        "task_id": task["id"],
        "agent_id": agent_id,
        "idempotency_key": idempotency_key,
        "request_hash": request_hash,
        "claim_token_hash": _token_hash(claim_token),
        "catalog_revision": CATALOG_REVISION,
        "state": "active",
        "lease_expires_at": now + lease_seconds,
        "created_at": now,
        "updated_at": now,
        "release_idempotency_key": None,
        "release_request_hash": None,
        "release_reason": None,
    }
    outcome, stored = await store.claim_task(claim=claim, now=now)
    if outcome == "idempotency_conflict":
        return problem(
            c,
            409,
            "idempotency_conflict",
            "The Idempotency-Key was already used with a different request.",
        )
    if outcome == "already_claimed":
        retry_after = max(int(stored["lease_expires_at"]) - now, 1)
        return problem(
            c,
            409,
            "task_already_claimed",
            "Another active lease already covers this task.",
            headers={"retry-after": str(retry_after)},
        )

    replayed = outcome == "replayed"
    replay_token = _claim_token(bearer_token, stored["id"], stored["agent_id"])
    return c.json(
        {
            "schema_version": "translation-task-claim/v1",
            "claim": _public_claim(stored),
            "claim_token": replay_token,
            "replayed": replayed,
            "links": _claim_links(stored["id"]),
        },
        status=200 if replayed else 201,
        headers={
            "cache-control": "no-store",
            "location": f"/api/v1/claims/{stored['id']}",
        },
    )


@app.get("/api/v1/claims/:id")
@describe(
    summary="Read an authenticated claim",
    tags=["coordination"],
    responses={401: None, 403: None, 404: None, 503: None},
)
async def show_claim(c: Context):
    store, _bearer_token, error = _write_prerequisites(c)
    if error is not None:
        return error
    claim, error = await _authorized_claim(c, store)
    if error is not None:
        return error
    report = await store.latest_report(claim["id"])
    return c.json(
        {
            "schema_version": "translation-task-claim/v1",
            "claim": _public_claim(claim),
            "report": _public_report(report) if report is not None else None,
            "links": _claim_links(claim["id"]),
        },
        headers={"cache-control": "no-store"},
    )


@app.post("/api/v1/claims/:id/renew", validated("json", LEASE_REQUEST_SCHEMA))
@describe(
    summary="Renew an active task lease",
    description="Requires Bearer authentication, X-Claim-Token, and Idempotency-Key.",
    tags=["coordination"],
    responses={400: None, 401: None, 403: None, 409: None, 429: None, 503: None},
)
async def renew_claim(c: Context):
    store, _bearer_token, error = _write_prerequisites(c)
    if error is not None:
        return error
    claim, error = await _authorized_claim(c, store)
    if error is not None:
        return error

    payload, error = await _json_object(c)
    if error is not None:
        return error
    error = _reject_unknown_fields(c, payload, {"lease_seconds"})
    if error is not None:
        return error
    lease_seconds = _lease_seconds(payload.get("lease_seconds"))
    if lease_seconds is None:
        return problem(
            c,
            422,
            "invalid_lease",
            f"lease_seconds must be an integer from {MIN_LEASE_SECONDS} to {MAX_LEASE_SECONDS}.",
        )
    idempotency_key, error = _idempotency_key(c)
    if error is not None:
        return error
    if not await _within_write_limit(c, claim["agent_id"]):
        return problem(
            c,
            429,
            "rate_limited",
            "The authenticated agent exceeded the write rate limit.",
            headers={"retry-after": "60"},
        )

    now = _now()
    request_hash = _request_hash({"lease_seconds": lease_seconds})
    outcome, event = await store.renew_claim(
        claim_id=claim["id"],
        event_id=f"evt_{secrets.token_urlsafe(18)}",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        lease_expires_at=now + lease_seconds,
        now=now,
    )
    if outcome == "idempotency_conflict":
        return problem(
            c,
            409,
            "idempotency_conflict",
            "The Idempotency-Key was already used with a different request.",
        )
    if outcome == "claim_not_active" or event is None:
        return problem(c, 409, "claim_not_active", "The claim expired or is no longer active.")
    return c.json(
        {
            "schema_version": "translation-task-lease/v1",
            "claim_id": claim["id"],
            "state": "active",
            "lease_expires_at": _timestamp(event["lease_expires_at"]),
            "replayed": outcome == "replayed",
            "links": _claim_links(claim["id"]),
        },
        headers={"cache-control": "no-store"},
    )


@app.post("/api/v1/claims/:id/release", validated("json", RELEASE_REQUEST_SCHEMA))
@describe(
    summary="Release a task claim",
    description="Requires Bearer authentication, X-Claim-Token, and Idempotency-Key.",
    tags=["coordination"],
    responses={400: None, 401: None, 403: None, 409: None, 429: None, 503: None},
)
async def release_claim(c: Context):
    store, _bearer_token, error = _write_prerequisites(c)
    if error is not None:
        return error
    claim, error = await _authorized_claim(c, store)
    if error is not None:
        return error

    payload, error = await _json_object(c)
    if error is not None:
        return error
    error = _reject_unknown_fields(c, payload, {"reason"})
    if error is not None:
        return error
    reason = payload.get("reason")
    if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
        return problem(
            c,
            422,
            "invalid_reason",
            "reason must be a string of at most 500 characters.",
        )
    idempotency_key, error = _idempotency_key(c)
    if error is not None:
        return error
    if not await _within_write_limit(c, claim["agent_id"]):
        return problem(
            c,
            429,
            "rate_limited",
            "The authenticated agent exceeded the write rate limit.",
            headers={"retry-after": "60"},
        )

    request_hash = _request_hash({"reason": reason})
    outcome, stored = await store.release_claim(
        claim_id=claim["id"],
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        reason=reason,
        now=_now(),
    )
    if outcome == "idempotency_conflict":
        return problem(
            c,
            409,
            "idempotency_conflict",
            "The Idempotency-Key was already used with a different request.",
        )
    if outcome == "claim_not_active":
        return problem(c, 409, "claim_not_active", "The claim is no longer active.")
    if stored is None:
        return problem(c, 404, "claim_not_found", "The requested claim does not exist.")
    return c.json(
        {
            "schema_version": "translation-task-claim/v1",
            "claim": _public_claim(stored),
            "replayed": outcome == "replayed",
            "links": _claim_links(stored["id"]),
        },
        headers={"cache-control": "no-store"},
    )


@app.post("/api/v1/claims/:id/reports", validated("json", REPORT_REQUEST_SCHEMA))
@describe(
    summary="Report evidence from a claimed task",
    description=(
        "Requires Bearer authentication, X-Claim-Token, and Idempotency-Key. "
        "Reports remain untrusted until human review."
    ),
    tags=["coordination"],
    responses={400: None, 401: None, 403: None, 409: None, 422: None, 429: None, 503: None},
)
async def create_report(c: Context):
    store, _bearer_token, error = _write_prerequisites(c)
    if error is not None:
        return error
    claim, error = await _authorized_claim(c, store)
    if error is not None:
        return error

    task = get_task(claim["task_id"])
    if task is None:
        return problem(c, 409, "catalog_changed", "The claimed task is no longer in the catalog.")
    if claim["catalog_revision"] != CATALOG_REVISION:
        return problem(
            c,
            409,
            "catalog_changed",
            "The catalog changed after this claim. Release it and fetch a fresh task bundle.",
        )
    payload, error = await _json_object(c)
    if error is not None:
        return error
    normalized, validation_error = _validated_report(payload, task)
    if validation_error is not None:
        return problem(c, 422, validation_error[0], validation_error[1])
    idempotency_key, error = _idempotency_key(c)
    if error is not None:
        return error
    if not await _within_write_limit(c, claim["agent_id"]):
        return problem(
            c,
            429,
            "rate_limited",
            "The authenticated agent exceeded the write rate limit.",
            headers={"retry-after": "60"},
        )

    now = _now()
    request_hash = _request_hash(normalized)
    report = {
        "id": f"rpt_{secrets.token_urlsafe(18)}",
        "claim_id": claim["id"],
        "idempotency_key": idempotency_key,
        "request_hash": request_hash,
        "payload_json": json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "created_at": now,
    }
    outcome, stored = await store.create_report(report=report, now=now)
    if outcome == "idempotency_conflict":
        return problem(
            c,
            409,
            "idempotency_conflict",
            "The Idempotency-Key was already used with a different request.",
        )
    if outcome == "claim_not_active" or stored is None:
        return problem(c, 409, "claim_not_active", "The claim expired or is no longer active.")
    return c.json(
        {
            "schema_version": "translation-task-report/v1",
            "report": _public_report(stored),
            "claim_state": "completed",
            "replayed": outcome == "replayed",
            "review_required": True,
            "links": _claim_links(claim["id"]),
        },
        status=200 if outcome == "replayed" else 201,
        headers={"cache-control": "no-store"},
    )


@app.on("GET", "/mcp")
@app.on("POST", "/mcp")
@app.on("DELETE", "/mcp")
async def mcp_route(c: Context):
    from hayate_mcp import McpMount

    mount = getattr(app, "_translation_mcp_mount", None)
    if mount is None:
        from .mcp_server import build_server

        mount = McpMount(build_server(), path="/mcp", stateless=True)
        app._translation_mcp_mount = mount
    return await mount.fetch(c.req)


OpenApi(
    app,
    title="ja-translation-todo API",
    version=__version__,
    description=(
        "Evidence-backed Japanese OSS translation tasks for humans and AI agents. "
        "Read automation.level before taking any external action."
    ),
).register(app)


def parse_integer(
    raw: str | None,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int | None:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def _write_available(env: Any) -> bool:
    return store_from_env(env) is not None and _env_value(env, "AGENT_API_TOKEN_SHA256") is not None


def _write_prerequisites(c: Context):
    store = store_from_env(c.env)
    expected_hash = _env_value(c.env, "AGENT_API_TOKEN_SHA256")
    if store is None or expected_hash is None:
        return (
            None,
            None,
            problem(
                c,
                503,
                "write_plane_unavailable",
                "The authenticated coordination plane is not configured.",
                headers={"retry-after": "300"},
            ),
        )
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_hash):
        return (
            None,
            None,
            problem(
                c,
                503,
                "write_plane_misconfigured",
                "The coordination plane credential is misconfigured.",
            ),
        )

    authorization = c.req.header("authorization")
    scheme, separator, credential = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not credential:
        return (
            None,
            None,
            problem(
                c,
                401,
                "authorization_required",
                "Provide the agent API token as a Bearer credential.",
                headers={"www-authenticate": 'Bearer realm="ja-translation-todo"'},
            ),
        )
    bearer_token = credential.strip()
    if not hmac.compare_digest(_token_hash(bearer_token), expected_hash.lower()):
        return (
            None,
            None,
            problem(
                c,
                401,
                "invalid_credential",
                "The Bearer credential is invalid.",
                headers={
                    "www-authenticate": (
                        'Bearer realm="ja-translation-todo", error="invalid_token"'
                    )
                },
            ),
        )
    return store, bearer_token, None


async def _authorized_claim(c: Context, store: Any):
    claim_id = c.req.param("id")
    claim = await store.get_claim(claim_id, now=_now())
    if claim is None:
        return None, problem(c, 404, "claim_not_found", "The requested claim does not exist.")
    presented = c.req.header("x-claim-token")
    if presented is None or not hmac.compare_digest(
        _token_hash(presented),
        str(claim["claim_token_hash"]),
    ):
        return (
            None,
            problem(
                c,
                403,
                "claim_token_required",
                "Provide the token issued for this claim in X-Claim-Token.",
            ),
        )
    return claim, None


async def _json_object(c: Context):
    content_length = c.req.header("content-length")
    if content_length is not None:
        try:
            if int(content_length) > 32_768:
                return None, problem(
                    c,
                    413,
                    "payload_too_large",
                    "Coordination request bodies are limited to 32 KiB.",
                )
        except ValueError:
            return None, problem(c, 400, "invalid_content_length", "Invalid Content-Length.")
    try:
        payload = c.req.valid("json")
    except KeyError:
        try:
            payload = await c.req.json()
        except (TypeError, ValueError, json.JSONDecodeError):
            return None, problem(c, 400, "invalid_json", "The request body must be a JSON object.")
    if not isinstance(payload, dict):
        return None, problem(c, 400, "invalid_json", "The request body must be a JSON object.")
    return payload, None


def _idempotency_key(c: Context):
    value = c.req.header("idempotency-key")
    if value is None or not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        return (
            None,
            problem(
                c,
                400,
                "invalid_idempotency_key",
                "Idempotency-Key must be 8-128 URL-safe characters.",
            ),
        )
    return value, None


def _reject_unknown_fields(c: Context, payload: dict[str, Any], allowed: set[str]):
    unknown = sorted(set(payload) - allowed)
    if not unknown:
        return None
    return problem(
        c,
        422,
        "unknown_request_field",
        f"Unknown request field: {unknown[0]}",
    )


async def _within_write_limit(c: Context, agent_id: str) -> bool:
    limiter = _env_value(c.env, "WRITE_RATE_LIMITER")
    if limiter is None:
        return True
    result = await limiter.limit({"key": f"agent:{agent_id}"})
    if isinstance(result, dict):
        return bool(result.get("success"))
    return bool(getattr(result, "success", False))


def _validated_report(
    payload: dict[str, Any],
    task: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, str] | None]:
    allowed_fields = {
        "outcome",
        "summary_ja",
        "evidence",
        "recommended_status",
        "external_actions_performed",
    }
    unknown = sorted(set(payload) - allowed_fields)
    if unknown:
        return {}, (
            "unknown_report_field",
            f"Unknown report field: {unknown[0]}",
        )

    outcome = payload.get("outcome")
    if outcome not in REPORT_OUTCOMES:
        allowed_outcomes = ", ".join(sorted(REPORT_OUTCOMES))
        return {}, ("invalid_outcome", f"outcome must be one of: {allowed_outcomes}.")
    summary = payload.get("summary_ja")
    if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 4_000:
        return {}, (
            "invalid_summary",
            "summary_ja must be a non-empty string of at most 4000 characters.",
        )
    recommended = payload.get("recommended_status")
    if recommended is not None and recommended not in RECOMMENDED_STATUSES:
        return {}, (
            "invalid_recommended_status",
            "recommended_status is not a reviewable catalog status.",
        )

    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) > 20:
        return {}, ("invalid_evidence", "evidence must be an array with at most 20 entries.")
    normalized_evidence: list[dict[str, str]] = []
    for index, item in enumerate(evidence):
        normalized, error = _validated_evidence(item)
        if error is not None:
            return {}, (
                "invalid_evidence",
                f"evidence[{index}]: {error}",
            )
        normalized_evidence.append(normalized)
    if outcome == "evidence_found" and not normalized_evidence:
        return {}, ("evidence_required", "evidence_found requires at least one evidence entry.")

    external_actions = payload.get("external_actions_performed", [])
    if (
        not isinstance(external_actions, list)
        or len(external_actions) > 10
        or any(not isinstance(action, str) or len(action) > 500 for action in external_actions)
    ):
        return {}, (
            "invalid_external_actions",
            "external_actions_performed must contain at most 10 short strings.",
        )
    if task["automation"]["level"] == "discover_only" and external_actions:
        return {}, (
            "automation_boundary_exceeded",
            "discover_only tasks cannot report that external write actions were performed.",
        )

    return (
        {
            "outcome": outcome,
            "summary_ja": summary.strip(),
            "evidence": normalized_evidence,
            "recommended_status": recommended,
            "external_actions_performed": external_actions,
        },
        None,
    )


def _validated_evidence(item: Any) -> tuple[dict[str, str], str | None]:
    if not isinstance(item, dict):
        return {}, "entry must be an object"
    if set(item) != {"url", "kind", "observed_at", "note_ja"}:
        return {}, "entry must contain only url, kind, observed_at, and note_ja"
    url = item.get("url")
    if not isinstance(url, str):
        return {}, "url must be a public HTTP(S) URL"
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username is not None:
        return {}, "url must be a public HTTP(S) URL without credentials"
    kind = item.get("kind")
    if kind not in EVIDENCE_KINDS:
        return {}, "kind is not supported"
    observed_at = item.get("observed_at")
    if not isinstance(observed_at, str):
        return {}, "observed_at must be an ISO date"
    try:
        date.fromisoformat(observed_at)
    except ValueError:
        return {}, "observed_at must be an ISO date"
    note = item.get("note_ja")
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 2_000:
        return {}, "note_ja must be a non-empty string of at most 2000 characters"
    return (
        {
            "url": url,
            "kind": kind,
            "observed_at": observed_at,
            "note_ja": note.strip(),
        },
        None,
    )


def _lease_seconds(value: Any) -> int | None:
    if value is None:
        return DEFAULT_LEASE_SECONDS
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if MIN_LEASE_SECONDS <= value <= MAX_LEASE_SECONDS else None


def _claim_token(bearer_token: str, claim_id: str, agent_id: str) -> str:
    digest = hmac.new(
        bearer_token.encode(),
        f"{claim_id}:{agent_id}".encode(),
        hashlib.sha256,
    ).digest()
    return "jtc_" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _public_claim(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": claim["id"],
        "task_id": claim["task_id"],
        "agent_id": claim["agent_id"],
        "catalog_revision": claim["catalog_revision"],
        "state": claim["state"],
        "lease_expires_at": _timestamp(claim["lease_expires_at"]),
        "created_at": _timestamp(claim["created_at"]),
        "updated_at": _timestamp(claim["updated_at"]),
        "release_reason": claim.get("release_reason"),
    }


def _public_report(report: dict[str, Any]) -> dict[str, Any]:
    payload = report.get("payload")
    if payload is None:
        payload = json.loads(report["payload_json"])
    return {
        "id": report["id"],
        "claim_id": report["claim_id"],
        "created_at": _timestamp(report["created_at"]),
        **payload,
    }


def _claim_links(claim_id: str) -> dict[str, str]:
    base = f"/api/v1/claims/{claim_id}"
    return {
        "self": base,
        "renew": f"{base}/renew",
        "release": f"{base}/release",
        "report": f"{base}/reports",
    }


def _timestamp(value: int) -> str:
    return datetime.fromtimestamp(int(value), UTC).isoformat().replace("+00:00", "Z")


def _now() -> int:
    return int(time.time())


def _env_value(env: Any, name: str) -> Any:
    if env is None:
        return None
    if isinstance(env, dict):
        return env.get(name)
    return getattr(env, name, None)


def problem(
    c: Context,
    status: int,
    code: str,
    detail: str,
    *,
    headers: dict[str, str] | None = None,
):
    response_headers = {"content-type": "application/problem+json"}
    if headers is not None:
        response_headers.update(headers)
    return c.json(
        {
            "type": f"https://github.com/yhay81/ja-translation-todo/problems/{code}",
            "title": code.replace("_", " "),
            "status": status,
            "detail": detail,
        },
        status=status,
        headers=response_headers,
    )
