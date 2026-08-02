"""Shared helpers for route modules: env access, problem responses, time."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from hayate import Context

CANONICAL_ORIGIN = "https://ja.yhay81.com"
LEGACY_HOSTS = frozenset({"ja.yusuke-hayashi.com"})
GITHUB_REPO_URL = "https://github.com/yhay81/ja-translation-todo"


def env_value(env: Any, name: str) -> Any:
    if env is None:
        return None
    if isinstance(env, dict):
        return env.get(name)
    return getattr(env, name, None)


def now_epoch() -> int:
    return int(time.time())


def timestamp(value: int) -> str:
    return datetime.fromtimestamp(int(value), UTC).isoformat().replace("+00:00", "Z")


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
            "type": f"{GITHUB_REPO_URL}/problems/{code}",
            "title": code.replace("_", " "),
            "status": status,
            "detail": detail,
        },
        status=status,
        headers=response_headers,
    )


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
