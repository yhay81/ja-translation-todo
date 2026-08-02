"""Read endpoints, pages, feeds, MCP, and the v1 shutdown."""

from __future__ import annotations

from helpers import api, make_env, sample_task, seed


async def seeded_env():
    env = make_env()
    await seed(
        env.CATALOG_STORE,
        sample_task("verify-react", repository="facebook/react", status="ready"),
        sample_task("verify-kubernetes", repository="kubernetes/website", category="Infra"),
    )
    return env


async def test_health_and_discovery():
    env = await seeded_env()
    health = await api(env, "/healthz")
    assert health.status == 200
    body = await health.json()
    assert body["status"] == "ok"
    assert body["tasks"] == 2
    assert body["catalog_revision"].startswith("cat_")

    root = await api(env, "/api/v2")
    root_body = await root.json()
    assert root_body["capabilities"] == {"read": True}
    assert root_body["links"]["mcp"] == "/mcp"
    assert "pull request" in root_body["contribution_contract"]["channel"]


async def test_legacy_host_redirects_to_new_domain():
    env = await seeded_env()
    response = await api(env, "/api/v2/tasks?q=react", host="ja.yusuke-hayashi.com")
    assert response.status == 301
    assert response.headers.get("location") == "https://ja.yhay81.com/api/v2/tasks?q=react"


async def test_api_v1_is_gone():
    env = await seeded_env()
    response = await api(env, "/api/v1/tasks")
    assert response.status == 410
    body = await response.json()
    assert "v2" in body["detail"]


async def test_search_bundle_and_etag():
    env = await seeded_env()
    listing = await api(env, "/api/v2/tasks?q=react&limit=10")
    assert listing.status == 200
    body = await listing.json()
    assert body["total"] == 1
    task = body["items"][0]
    assert task["project"]["repository"] == "facebook/react"
    assert task["task_revision"] == 1
    assert task["links"]["edit"].endswith("/catalog/tasks/verify-react.json")

    detail = await api(env, task["links"]["bundle"])
    assert detail.status == 200
    detail_body = await detail.json()
    assert detail_body["id"] == task["id"]

    stats = await api(env, "/api/v2/stats")
    stats_body = await stats.json()
    assert stats_body["total"] == 2
    assert stats_body["by_category"]["Infra"] == 1


async def test_tasks_json_collection():
    env = await seeded_env()
    response = await api(env, "/tasks.json")
    assert response.status == 200
    body = await response.json()
    assert body["schema_version"] == "translation-task-collection/v1"
    assert [task["id"] for task in body["tasks"]] == ["verify-kubernetes", "verify-react"]


async def test_task_page_injects_ogp_and_initial_data():
    env = await seeded_env()
    page = await api(env, "/tasks/verify-react")
    assert page.status == 200
    html = await page.text()
    assert "og:title" in html
    assert "facebook/react" in html
    assert 'id="initial-data"' in html
    assert html.count("<title>") == 1

    missing = await api(env, "/tasks/nope")
    assert missing.status == 404
    assert "タスクが見つかりません" in await missing.text()


async def test_tasks_feed_renders_atom():
    env = await seeded_env()
    feed = await api(env, "/feeds/tasks.atom")
    assert feed.status == 200
    assert (feed.headers.get("content-type") or "").startswith("application/atom+xml")
    document = await feed.text()
    assert "<feed" in document
    assert "verify-react" in document


async def test_mcp_lists_registry_tools():
    env = await seeded_env()
    response = await api(
        env,
        "/mcp",
        method="POST",
        headers={
            "accept": "application/json",
            "mcp-protocol-version": "2025-06-18",
        },
        json_payload={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status == 200
    tools = (await response.json())["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "search_translation_tasks",
        "get_translation_task",
        "get_agent_instructions",
    }


async def test_openapi_describes_v2_routes():
    env = await seeded_env()
    response = await api(env, "/openapi.json")
    assert response.status == 200
    document = await response.json()
    assert "/api/v2/tasks" in document["paths"]
    assert "/api/v2/tasks/{id}/bundle" in document["paths"]
    assert not any(path.startswith("/api/v1/") for path in document["paths"])
    assert not any("claims" in path for path in document["paths"])
