from __future__ import annotations

from translation_hub.app import app


async def test_health_and_api_discovery():
    health = await app.request("/healthz")
    assert health.status == 200
    health_body = await health.json()
    assert health_body["status"] == "ok"
    assert health_body["tasks"] > 0

    root = await app.request("/api/v1")
    body = await root.json()
    assert body["capabilities"] == {
        "read": True,
        "claim": False,
        "lease_renewal": False,
        "result_reporting": False,
    }
    assert body["links"]["mcp"] == "/mcp"


async def test_search_and_task_bundle():
    response = await app.request("/api/v1/tasks?q=kubernetes&limit=1")
    assert response.status == 200
    body = await response.json()
    assert body["total"] == 1
    task = body["items"][0]
    assert task["project"]["repository"] == "kubernetes/website"
    assert task["execution_contract"]["must_not_auto_merge"] is True

    detail = await app.request(task["links"]["bundle"])
    assert detail.status == 200
    assert (await detail.json())["id"] == task["id"]


async def test_invalid_filter_is_problem_json():
    response = await app.request("/api/v1/tasks?status=made-up")
    assert response.status == 400
    assert response.headers.get("content-type") == "application/problem+json"
    assert (await response.json())["title"] == "invalid status"


async def test_missing_task_is_404():
    response = await app.request("/api/v1/tasks/not-a-real-task")
    assert response.status == 404
    assert (await response.json())["title"] == "task not found"


async def test_openapi_describes_task_routes():
    response = await app.request("/openapi.json")
    assert response.status == 200
    document = await response.json()
    assert document["openapi"] == "3.1.1"
    assert "/api/v1/tasks" in document["paths"]
    assert "/api/v1/tasks/{id}/bundle" in document["paths"]
    assert "/api/v1/tasks/{id}/claims" in document["paths"]
    assert "/api/v1/claims/{id}/reports" in document["paths"]
    claim_operation = document["paths"]["/api/v1/tasks/{id}/claims"]["post"]
    claim_schema = claim_operation["requestBody"]["content"]["application/json"]["schema"]
    assert set(claim_schema["required"]) == {"agent_id", "catalog_revision"}
    report_operation = document["paths"]["/api/v1/claims/{id}/reports"]["post"]
    assert "requestBody" in report_operation


async def test_mcp_lists_registry_tools_without_a_session():
    response = await app.request(
        "/mcp",
        method="POST",
        headers={
            "accept": "application/json",
            "mcp-protocol-version": "2025-06-18",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status == 200
    tools = (await response.json())["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert names == {
        "search_translation_tasks",
        "get_translation_task",
        "get_agent_instructions",
    }
