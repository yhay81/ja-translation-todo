"""Hayate application assembly: read-only Web API v2, feeds, pages, MCP.

Catalog updates flow through GitHub pull requests against
``catalog/tasks/*.json`` (see docs/verification-playbook.md); the Worker
serves the seeded D1 catalog and has no write plane.
"""

from __future__ import annotations

from hayate import Context, Hayate
from hayate_openapi import OpenApi

from . import __version__
from .common import CANONICAL_ORIGIN, LEGACY_HOSTS, problem

app = Hayate()


@app.use
async def redirect_legacy_hosts(c: Context, next_) -> None:
    """301 the retired ja.yusuke-hayashi.com domain to ja.yhay81.com."""
    host = c.req.url.hostname
    if host in LEGACY_HOSTS:
        target = f"{CANONICAL_ORIGIN}{c.req.url.pathname}{c.req.url.search or ''}"
        c.res = c.redirect(target, status=301)
        return
    await next_()


from . import feeds, pages, routes_catalog  # noqa: E402

routes_catalog.register(app)
feeds.register(app)
pages.register(app)


@app.on("GET", "/api/v1/*")
@app.on("POST", "/api/v1/*")
@app.on("DELETE", "/api/v1/*")
@app.on("PATCH", "/api/v1/*")
@app.on("PUT", "/api/v1/*")
async def api_v1_gone(c: Context):
    """v1 was retired by the ja.yhay81.com rebuild; point clients at v2."""
    return problem(
        c,
        410,
        "api_v1_retired",
        "API v1 was removed. Use /api/v2 (see /api/v2 for the discovery document).",
    )


@app.on("GET", "/mcp")
@app.on("POST", "/mcp")
@app.on("DELETE", "/mcp")
async def mcp_route(c: Context):
    from hayate_mcp import McpMount

    from .mcp_server import build_server

    # Stateless transport: the server is bound to this request's env so MCP
    # tools read the same D1-backed catalog as the REST API.
    mount = McpMount(build_server(c.env), path="/mcp", stateless=True)
    return await mount.fetch(c.req)


OpenApi(
    app,
    title="ja-translation-todo API",
    version=__version__,
    description=(
        "Evidence-backed Japanese OSS translation tasks for humans and AI agents. "
        "Read automation.level before taking any external action. "
        "Catalog updates are made via GitHub pull requests."
    ),
).register(app)
