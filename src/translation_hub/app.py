"""Hayate application exposing Web API, OpenAPI, and Remote MCP."""

from __future__ import annotations

from hayate import Context, Hayate
from hayate_openapi import OpenApi, describe

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

app = Hayate()

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
    return c.json(
        {
            "service": "ja-translation-todo",
            "version": __version__,
            "catalog_revision": CATALOG_REVISION,
            "capabilities": {
                "read": True,
                "claim": False,
                "result_reporting": False,
            },
            "links": {
                "tasks": "/api/v1/tasks",
                "openapi": "/openapi.json",
                "mcp": "/mcp",
                "static_catalog": "/tasks.json",
                "schema": "/schema/translation-task-v1.schema.json",
                "agent_instructions": "/llms.txt",
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


def problem(c: Context, status: int, code: str, detail: str):
    return c.json(
        {
            "type": f"https://github.com/yhay81/ja-translation-todo/problems/{code}",
            "title": code.replace("_", " "),
            "status": status,
            "detail": detail,
        },
        status=status,
        headers={"content-type": "application/problem+json"},
    )
