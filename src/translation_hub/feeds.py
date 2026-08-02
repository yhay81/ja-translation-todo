"""Atom feeds: catalog changes and approved contributions."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from hayate import Context, Hayate

from .catalog_store import catalog_store_from_env
from .common import CANONICAL_ORIGIN, problem, timestamp

_CHANGE_LABELS = {
    "create": "新規タスク",
    "update": "更新",
    "status_change": "状態変更",
    "auto_refresh": "自動更新",
    "promote": "昇格",
    "import": "取り込み",
}


def register(app: Hayate) -> None:
    @app.get("/feeds/tasks.atom")
    async def tasks_feed(c: Context):
        store = catalog_store_from_env(c.env)
        if store is None:
            return problem(c, 503, "catalog_unavailable", "The catalog store is not configured.")
        changes = await store.recent_changes(limit=50)
        revision = await store.catalog_revision()
        entries = []
        for change in changes:
            task = change["payload"]
            label = _CHANGE_LABELS.get(change["change_kind"], change["change_kind"])
            title = f"[{label}] {task['title']['ja']} ({task['status']})"
            summary = change.get("change_note") or task["project"]["summary_ja"]
            entries.append(
                _entry(
                    entry_id=(
                        f"{CANONICAL_ORIGIN}/tasks/{change['task_id']}#rev{change['task_revision']}"
                    ),
                    title=title,
                    url=f"{CANONICAL_ORIGIN}/tasks/{change['task_id']}",
                    updated=timestamp(change["created_at"]),
                    summary=summary,
                    author=change["changed_by"],
                )
            )
        return _atom_response(
            c,
            feed_id=f"{CANONICAL_ORIGIN}/feeds/tasks.atom",
            title="ja-translation-todo タスク更新",
            updated=timestamp(changes[0]["created_at"]) if changes else timestamp(0),
            entries=entries,
            etag=revision,
        )


def _entry(
    *,
    entry_id: str,
    title: str,
    url: str,
    updated: str,
    summary: str,
    author: str,
) -> str:
    return (
        "<entry>"
        f"<id>{escape(entry_id)}</id>"
        f"<title>{escape(title)}</title>"
        f'<link href="{escape(url, {chr(34): "&quot;"})}"/>'
        f"<updated>{escape(updated)}</updated>"
        f"<summary>{escape(summary)}</summary>"
        f"<author><name>{escape(author)}</name></author>"
        "</entry>"
    )


def _atom_response(
    c: Context,
    *,
    feed_id: str,
    title: str,
    updated: str,
    entries: list[str],
    etag: str | None,
) -> Any:
    document = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        f"<id>{escape(feed_id)}</id>"
        f"<title>{escape(title)}</title>"
        f"<updated>{escape(updated)}</updated>"
        f'<link rel="self" href="{escape(feed_id, {chr(34): "&quot;"})}"/>'
        f'<link href="{CANONICAL_ORIGIN}/"/>' + "".join(entries) + "</feed>"
    )
    headers = {
        "content-type": "application/atom+xml; charset=utf-8",
        "cache-control": "public, max-age=300",
    }
    if etag is not None:
        headers["etag"] = f'"{etag}"'
    return c.body(document, headers=headers)
