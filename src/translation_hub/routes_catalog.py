"""Public read endpoints: discovery, stats, task search, bundles, tasks.json."""

from __future__ import annotations

from hayate import Context, Hayate
from hayate_openapi import describe

from . import __version__
from .catalog import SORTS, catalog_stats, search_records, task_bundle
from .catalog_store import catalog_store_from_env
from .common import GITHUB_REPO_URL, now_epoch, parse_integer, problem, timestamp
from .taskschema import KINDS, STATUSES, WORKFLOW_PLATFORMS

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


def register(app: Hayate) -> None:
    @app.get("/healthz")
    @describe(summary="Service health", tags=["system"])
    async def health(c: Context):
        store = catalog_store_from_env(c.env)
        revision = await store.catalog_revision() if store is not None else "unavailable"
        total = len(await store.all_records()) if store is not None else 0
        return c.json(
            {
                "status": "ok",
                "service": "ja-translation-todo",
                "version": __version__,
                "catalog_revision": revision,
                "tasks": total,
            },
            headers={"cache-control": "no-store"},
        )

    @app.get("/api/v2")
    @describe(summary="API discovery document", tags=["system"])
    async def api_root(c: Context):
        store = catalog_store_from_env(c.env)
        revision = await store.catalog_revision() if store is not None else "unavailable"
        return c.json(
            {
                "service": "ja-translation-todo",
                "version": __version__,
                "catalog_revision": revision,
                "capabilities": {"read": True},
                "links": {
                    "tasks": "/api/v2/tasks",
                    "stats": "/api/v2/stats",
                    "task_template": "/api/v2/tasks/{task_id}",
                    "feeds": {"tasks": "/feeds/tasks.atom"},
                    "openapi": "/openapi.json",
                    "mcp": "/mcp",
                    "static_catalog": "/tasks.json",
                    "schema": "/schema/translation-task-v1.schema.json",
                    "agent_instructions": "/llms.txt",
                    "repository": GITHUB_REPO_URL,
                    "contribute": f"{GITHUB_REPO_URL}/blob/master/CONTRIBUTING.md",
                    "verification_playbook": (
                        f"{GITHUB_REPO_URL}/blob/master/docs/verification-playbook.md"
                    ),
                },
                "contribution_contract": {
                    "channel": "GitHub pull requests against catalog/tasks/*.json",
                    "review": "Maintainers review every change; ready requires human review.",
                    "ai_disclosure_required": True,
                },
            }
        )

    @app.get("/api/v2/stats")
    @describe(summary="Catalog statistics", tags=["tasks"])
    async def stats(c: Context):
        store = catalog_store_from_env(c.env)
        if store is None:
            return problem(c, 503, "catalog_unavailable", "The catalog store is not configured.")
        records = await store.all_records()
        revision = await store.catalog_revision()
        return c.json(
            {"catalog_revision": revision, **catalog_stats(records)},
            headers={
                "cache-control": "public, max-age=60, stale-while-revalidate=300",
                "etag": f'"{revision}"',
            },
        )

    @app.get("/api/v2/tasks")
    @describe(
        summary="Search translation tasks",
        tags=["tasks"],
        response=SEARCH_RESPONSE_SCHEMA,
        responses={400: None},
    )
    async def list_tasks(c: Context):
        store = catalog_store_from_env(c.env)
        if store is None:
            return problem(c, 503, "catalog_unavailable", "The catalog store is not configured.")
        status = c.req.query("status")
        kind = c.req.query("kind")
        difficulty = c.req.query("difficulty")
        platform = c.req.query("platform")
        sort = c.req.query("sort") or "updated"
        if status is not None and status not in STATUSES:
            return problem(c, 400, "invalid_status", f"Unknown status: {status}")
        if kind is not None and kind not in KINDS:
            return problem(c, 400, "invalid_kind", f"Unknown kind: {kind}")
        if difficulty is not None and difficulty not in {"easy", "medium", "hard"}:
            return problem(c, 400, "invalid_difficulty", "difficulty must be easy, medium, or hard")
        if platform is not None and platform not in WORKFLOW_PLATFORMS:
            return problem(c, 400, "invalid_platform", f"Unknown platform: {platform}")
        if sort not in SORTS:
            allowed = ", ".join(sorted(SORTS))
            return problem(c, 400, "invalid_sort", f"sort must be one of: {allowed}")

        limit = parse_integer(c.req.query("limit"), default=50, minimum=1, maximum=100)
        offset = parse_integer(c.req.query("cursor"), default=0, minimum=0, maximum=1_000_000)
        if limit is None:
            return problem(c, 400, "invalid_limit", "limit must be an integer from 1 to 100")
        if offset is None:
            return problem(c, 400, "invalid_cursor", "cursor must be a non-negative integer")

        records = await store.all_records()
        revision = await store.catalog_revision()
        result = search_records(
            records,
            query=c.req.query("q"),
            status=status,
            kind=kind,
            category=c.req.query("category"),
            difficulty=difficulty,
            platform=platform,
            sort=sort,
            offset=offset,
            limit=limit,
        )
        result["catalog_revision"] = revision
        result["items"] = [
            task_bundle(record, catalog_revision=revision) for record in result["items"]
        ]
        return c.json(
            result,
            headers={
                "cache-control": "public, max-age=60, stale-while-revalidate=300",
                "etag": f'"{revision}"',
            },
        )

    @app.get("/api/v2/tasks/:id")
    @describe(summary="Get a translation task", tags=["tasks"], responses={404: None})
    async def show_task(c: Context):
        return await _bundle_response(c, cache=False)

    @app.get("/api/v2/tasks/:id/bundle")
    @describe(summary="Get an agent-ready task bundle", tags=["tasks"], responses={404: None})
    async def show_bundle(c: Context):
        return await _bundle_response(c, cache=True)

    @app.get("/tasks.json")
    @describe(summary="Full catalog as a static-style collection", tags=["tasks"])
    async def tasks_json(c: Context):
        store = catalog_store_from_env(c.env)
        if store is None:
            return problem(c, 503, "catalog_unavailable", "The catalog store is not configured.")
        records = await store.all_records()
        revision = await store.catalog_revision()
        return c.json(
            {
                "schema_version": "translation-task-collection/v1",
                "catalog_revision": revision,
                "generated_at": timestamp(now_epoch()),
                "tasks": sorted(
                    (record["task"] for record in records),
                    key=lambda task: task["id"],
                ),
            },
            headers={
                "cache-control": "public, max-age=300, stale-while-revalidate=600",
                "etag": f'"{revision}"',
            },
        )


async def _bundle_response(c: Context, *, cache: bool):
    store = catalog_store_from_env(c.env)
    if store is None:
        return problem(c, 503, "catalog_unavailable", "The catalog store is not configured.")
    record = await store.get_record(c.req.param("id"))
    if record is None:
        return problem(c, 404, "task_not_found", "The requested task does not exist.")
    revision = await store.catalog_revision()
    headers = {"etag": f'"{revision}"'}
    if cache:
        headers["cache-control"] = "public, max-age=60, stale-while-revalidate=300"
    return c.json(task_bundle(record, catalog_revision=revision), headers=headers)
