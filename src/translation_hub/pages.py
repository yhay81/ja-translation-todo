"""Server-rendered heads for task pages: OGP metadata + initial data.

Crawlers do not run the SPA's JavaScript, so ``/tasks/:id`` is handled by
the Worker: it fetches the SPA shell from the ASSETS binding and injects
``<!--ssr:head-->`` / ``<!--ssr:data-->`` markers with task metadata and
an inline JSON payload the client uses to skip its first fetch.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from hayate import Context, Hayate

from .catalog import task_bundle
from .catalog_store import catalog_store_from_env
from .common import CANONICAL_ORIGIN, env_value

HEAD_MARKER = "<!--ssr:head-->"
DATA_MARKER = "<!--ssr:data-->"


def register(app: Hayate) -> None:
    @app.get("/tasks/:id")
    async def task_page(c: Context):
        shell = await _shell_html(c)
        if shell is None:
            return c.text("service unavailable", status=503)

        store = catalog_store_from_env(c.env)
        record = await store.get_record(c.req.param("id")) if store is not None else None
        if record is None:
            head = _head_block(
                title="タスクが見つかりません | ja-translation-todo",
                description="指定された日本語化タスクは存在しないか、削除されています。",
                url=f"{CANONICAL_ORIGIN}{c.req.url.pathname}",
            )
            return c.html(_inject(shell, head, None), status=404)

        task = record["task"]
        revision = await store.catalog_revision()
        title = f"{task['title']['ja']} | ja-translation-todo"
        description = str(task["project"]["summary_ja"])[:200]
        head = _head_block(
            title=title,
            description=description,
            url=f"{CANONICAL_ORIGIN}/tasks/{task['id']}",
        )
        initial = task_bundle(record, catalog_revision=revision)
        return c.html(_inject(shell, head, initial))


async def _shell_html(c: Context) -> str | None:
    assets = env_value(c.env, "ASSETS")
    if assets is None:
        return None
    host = c.req.url.hostname or "ja.yhay81.com"
    response = await assets.fetch(f"https://{host}/index.html")
    status = int(getattr(response, "status", 0) or 0)
    if status != 200:
        return None
    text = await response.text()
    return str(text)


def _head_block(*, title: str, description: str, url: str) -> str:
    safe_title = html.escape(title, quote=True)
    safe_description = html.escape(description, quote=True)
    safe_url = html.escape(url, quote=True)
    return (
        f"<title>{safe_title}</title>"
        f'<meta name="description" content="{safe_description}">'
        f'<link rel="canonical" href="{safe_url}">'
        f'<meta property="og:type" content="article">'
        f'<meta property="og:title" content="{safe_title}">'
        f'<meta property="og:description" content="{safe_description}">'
        f'<meta property="og:url" content="{safe_url}">'
        f'<meta property="og:site_name" content="ja-translation-todo">'
        f'<meta name="twitter:card" content="summary">'
    )


_STATIC_TITLE = re.compile(r"<title>.*?</title>", re.DOTALL)


def _inject(shell: str, head: str, initial: dict[str, Any] | None) -> str:
    # The shell ships a static <title>; drop it so the injected one wins
    # (browsers and crawlers use the first title in the document).
    document = _STATIC_TITLE.sub("", shell, count=1)
    document = document.replace(HEAD_MARKER, head, 1)
    if initial is not None:
        payload = json.dumps(initial, ensure_ascii=False).replace("</", "<\\/")
        document = document.replace(
            DATA_MARKER,
            f'<script type="application/json" id="initial-data">{payload}</script>',
            1,
        )
    return document
