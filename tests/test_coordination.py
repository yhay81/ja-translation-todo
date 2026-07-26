from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from hayate import Request

from translation_hub.app import app
from translation_hub.catalog import CATALOG_REVISION
from translation_hub.coordination import MemoryCoordinationStore

TOKEN = "jat_test_agent_token_0123456789"
TASK_ID = "verify-kubernetes-website"


def make_env():
    return SimpleNamespace(
        COORDINATION_STORE=MemoryCoordinationStore(),
        AGENT_API_TOKEN_SHA256=hashlib.sha256(TOKEN.encode()).hexdigest(),
    )


async def write_request(
    env,
    path: str,
    *,
    payload: dict,
    idempotency_key: str | None = None,
    claim_token: str | None = None,
    authenticated: bool = True,
):
    headers = {"content-type": "application/json"}
    if authenticated:
        headers["authorization"] = f"Bearer {TOKEN}"
    if idempotency_key is not None:
        headers["idempotency-key"] = idempotency_key
    if claim_token is not None:
        headers["x-claim-token"] = claim_token
    request = Request(
        f"http://localhost{path}",
        method="POST",
        headers=headers,
        body=json.dumps(payload),
    )
    return await app.fetch(request, env=env)


async def read_claim(env, claim_id: str, claim_token: str):
    request = Request(
        f"http://localhost/api/v1/claims/{claim_id}",
        headers={
            "authorization": f"Bearer {TOKEN}",
            "x-claim-token": claim_token,
        },
    )
    return await app.fetch(request, env=env)


async def create_test_claim(env, *, key: str = "claim-key-0001"):
    response = await write_request(
        env,
        f"/api/v1/tasks/{TASK_ID}/claims",
        payload={
            "agent_id": "codex:test",
            "catalog_revision": CATALOG_REVISION,
            "lease_seconds": 900,
        },
        idempotency_key=key,
    )
    return response, await response.json()


async def test_claim_requires_authentication_and_is_idempotent():
    env = make_env()
    unauthorized = await write_request(
        env,
        f"/api/v1/tasks/{TASK_ID}/claims",
        payload={"agent_id": "codex:test", "catalog_revision": CATALOG_REVISION},
        idempotency_key="claim-key-0001",
        authenticated=False,
    )
    assert unauthorized.status == 401
    assert unauthorized.headers.get("www-authenticate").startswith("Bearer")

    created, first = await create_test_claim(env)
    assert created.status == 201
    assert first["claim"]["state"] == "active"
    assert first["claim_token"].startswith("jtc_")
    assert first["replayed"] is False

    replayed, second = await create_test_claim(env)
    assert replayed.status == 200
    assert second["replayed"] is True
    assert second["claim"]["id"] == first["claim"]["id"]
    assert second["claim_token"] == first["claim_token"]

    conflict = await write_request(
        env,
        f"/api/v1/tasks/{TASK_ID}/claims",
        payload={
            "agent_id": "codex:test",
            "catalog_revision": CATALOG_REVISION,
            "lease_seconds": 1200,
        },
        idempotency_key="claim-key-0001",
    )
    assert conflict.status == 409
    assert (await conflict.json())["title"] == "idempotency conflict"


async def test_active_claim_blocks_another_agent():
    env = make_env()
    await create_test_claim(env)
    response = await write_request(
        env,
        f"/api/v1/tasks/{TASK_ID}/claims",
        payload={
            "agent_id": "other-agent",
            "catalog_revision": CATALOG_REVISION,
            "lease_seconds": 900,
        },
        idempotency_key="claim-key-0002",
    )
    assert response.status == 409
    assert (await response.json())["title"] == "task already claimed"
    assert int(response.headers.get("retry-after")) > 0


async def test_claim_can_be_renewed_and_released():
    env = make_env()
    _response, created = await create_test_claim(env)
    claim_id = created["claim"]["id"]
    claim_token = created["claim_token"]

    renewed = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/renew",
        payload={"lease_seconds": 1200},
        idempotency_key="renew-key-0001",
        claim_token=claim_token,
    )
    renewed_body = await renewed.json()
    assert renewed.status == 200
    assert renewed_body["state"] == "active"
    assert renewed_body["replayed"] is False

    renewal_replay = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/renew",
        payload={"lease_seconds": 1200},
        idempotency_key="renew-key-0001",
        claim_token=claim_token,
    )
    assert (await renewal_replay.json())["replayed"] is True

    released = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/release",
        payload={"reason": "capacity changed"},
        idempotency_key="release-key-01",
        claim_token=claim_token,
    )
    assert released.status == 200
    assert (await released.json())["claim"]["state"] == "released"

    release_replay = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/release",
        payload={"reason": "capacity changed"},
        idempotency_key="release-key-01",
        claim_token=claim_token,
    )
    assert (await release_replay.json())["replayed"] is True


async def test_discover_only_report_is_review_gated_and_idempotent():
    env = make_env()
    _response, created = await create_test_claim(env)
    claim_id = created["claim"]["id"]
    claim_token = created["claim_token"]

    unsafe = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/reports",
        payload={
            "outcome": "evidence_found",
            "summary_ja": "外部PRも作成した",
            "evidence": [
                {
                    "url": "https://github.com/kubernetes/website",
                    "kind": "repository",
                    "observed_at": "2026-07-25",
                    "note_ja": "公開repositoryを確認",
                }
            ],
            "external_actions_performed": ["opened_pull_request"],
        },
        idempotency_key="report-key-001",
        claim_token=claim_token,
    )
    assert unsafe.status == 422
    assert (await unsafe.json())["title"] == "automation boundary exceeded"

    report_payload = {
        "outcome": "evidence_found",
        "summary_ja": "公開されている翻訳方針を確認した",
        "evidence": [
            {
                "url": (
                    "https://github.com/kubernetes/website/blob/main/"
                    "content/en/docs/contribute/localization.md"
                ),
                "kind": "translation_policy",
                "observed_at": "2026-07-25",
                "note_ja": "公式repository内のlocalization guide",
            }
        ],
        "recommended_status": "needs_verification",
        "external_actions_performed": [],
    }
    reported = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/reports",
        payload=report_payload,
        idempotency_key="report-key-001",
        claim_token=claim_token,
    )
    body = await reported.json()
    assert reported.status == 201
    assert body["claim_state"] == "completed"
    assert body["review_required"] is True
    assert body["report"]["evidence"][0]["kind"] == "translation_policy"

    replayed = await write_request(
        env,
        f"/api/v1/claims/{claim_id}/reports",
        payload=report_payload,
        idempotency_key="report-key-001",
        claim_token=claim_token,
    )
    replayed_body = await replayed.json()
    assert replayed.status == 200
    assert replayed_body["replayed"] is True
    assert replayed_body["report"]["id"] == body["report"]["id"]

    status = await read_claim(env, claim_id, claim_token)
    status_body = await status.json()
    assert status_body["claim"]["state"] == "completed"
    assert status_body["report"]["id"] == body["report"]["id"]
