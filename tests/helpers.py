"""Shared test doubles and request helpers for the read-only v2 app."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from hayate import Request

from translation_hub.app import app
from translation_hub.catalog_store import MemoryCatalogStore

SHELL_HTML = (
    "<html><head><title>static</title><!--ssr:head--></head>"
    "<body><div id='app'></div><!--ssr:data--></body></html>"
)


def sample_task(
    task_id: str = "verify-example-repo",
    *,
    repository: str = "example/repo",
    status: str = "needs_verification",
    automation_level: str = "discover_only",
    category: str = "JavaScript",
    **overrides: Any,
) -> dict[str, Any]:
    task = {
        "schema_version": "translation-task/v1",
        "id": task_id,
        "kind": "verification",
        "status": status,
        "title": {"ja": f"{repository} の再検証", "en": None},
        "project": {
            "repository": repository,
            "url": f"https://github.com/{repository}",
            "category": category,
            "summary_ja": f"{repository} の翻訳機会を検証する。",
            "license": "MIT",
        },
        "source": {"revision": None, "paths": []},
        "target": {"locale": "ja-JP", "paths": []},
        "permissions": {
            "translation": "unknown",
            "ai_assistance": "unknown",
            "pull_request": "unknown",
        },
        "automation": {
            "level": automation_level,
            "allowed_actions": [
                "inspect_public_metadata",
                "find_translation_policy",
                "find_existing_work",
                "report_evidence",
            ],
        },
        "evidence": [
            {
                "url": f"https://github.com/{repository}",
                "kind": "repository",
                "observed_at": "2026-07-01",
                "note_ja": "リポジトリの存在を確認。",
            }
        ],
        "validation": [],
        "credit": {"expected": "unknown", "public_attribution": True},
        "provenance": {
            "revision": 1,
            "imported_from": None,
            "imported_at": "2026-07-01",
            "last_verified_at": None,
        },
    }
    task.update(overrides)
    return task


class AssetsStub:
    def __init__(self, html: str = SHELL_HTML) -> None:
        self.html = html

    async def fetch(self, _url: str):
        html = self.html

        class _Response:
            status = 200

            async def text(self) -> str:
                return html

        return _Response()


async def seed(store: MemoryCatalogStore, *tasks: dict[str, Any]) -> None:
    for index, task in enumerate(tasks):
        await store.upsert_task(
            task,
            change_kind="import",
            changed_by="seed:test",
            now=1_700_000_000 + index,
        )


def make_env(**overrides: Any) -> SimpleNamespace:
    env = SimpleNamespace(
        CATALOG_STORE=MemoryCatalogStore(),
        ASSETS=AssetsStub(),
    )
    for key, value in overrides.items():
        setattr(env, key, value)
    return env


async def api(
    env: Any,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_payload: Any = None,
    host: str = "ja.yhay81.com",
):
    merged = dict(headers or {})
    body = None
    if json_payload is not None:
        body = json.dumps(json_payload)
        merged.setdefault("content-type", "application/json")
    request = Request(
        f"https://{host}{path}",
        method=method,
        headers=merged,
        body=body,
    )
    return await app.fetch(request, env=env)
