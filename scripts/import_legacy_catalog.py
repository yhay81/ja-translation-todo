"""One-time importer from the historical Markdown list to verification tasks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "docs" / "legacy-list.md"
OUTPUT = ROOT / "catalog" / "tasks"

SECTION_RE = re.compile(r"^## (.+)$")
ENTRY_RE = re.compile(r"^### \[([^\]]+)\]\((https?://github\.com/[^)]+)\)$")
FIELD_RE = re.compile(r"^- ([^:\N{FULLWIDTH COLON}]+)[:\N{FULLWIDTH COLON}]\s*(.*)$")


def repository_from_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"not a repository URL: {url}")
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def slug(repository: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", repository.lower()).strip("-")
    return f"verify-{normalized}"


def parse_entries(text: str) -> list[dict[str, object]]:
    category = "Other"
    current: dict[str, object] | None = None
    entries: list[dict[str, object]] = []

    for line in text.splitlines():
        section = SECTION_RE.match(line)
        if section:
            category = section.group(1)
            continue

        entry = ENTRY_RE.match(line)
        if entry:
            if current is not None:
                entries.append(current)
            url = entry.group(2)
            current = {
                "label": entry.group(1),
                "url": url,
                "repository": repository_from_url(url),
                "category": category,
                "fields": {},
            }
            continue

        field = FIELD_RE.match(line)
        if field and current is not None:
            fields = current["fields"]
            assert isinstance(fields, dict)
            fields[field.group(1).strip()] = field.group(2).strip()

    if current is not None:
        entries.append(current)
    return entries


def to_task(entry: dict[str, object]) -> dict[str, object]:
    fields = entry["fields"]
    assert isinstance(fields, dict)
    repository = str(entry["repository"])
    url = str(entry["url"])
    summary = str(fields.get("概要", ""))
    return {
        "schema_version": "translation-task/v1",
        "id": slug(repository),
        "kind": "verification",
        "status": "needs_verification",
        "title": {
            "ja": f"{repository} の日本語化参加方法を再検証",
            "en": f"Re-verify the Japanese translation workflow for {repository}",
        },
        "project": {
            "repository": repository,
            "url": url,
            "category": str(entry["category"]),
            "summary_ja": summary,
            "license": fields.get("ライセンス") or None,
        },
        "source": {"revision": None, "paths": []},
        "target": {"locale": "ja-JP", "paths": []},
        "permissions": {
            "translation": "unknown",
            "ai_assistance": "unknown",
            "pull_request": "unknown",
        },
        "automation": {
            "level": "discover_only",
            "allowed_actions": [
                "inspect_public_metadata",
                "find_translation_policy",
                "find_existing_work",
                "report_evidence",
            ],
        },
        "evidence": [
            {
                "url": url,
                "kind": "repository",
                "observed_at": "2025-12-31",
                "note_ja": "旧一覧に掲載されていたrepository。翻訳方針の根拠としては未検証。",
            }
        ],
        "validation": [],
        "credit": {"expected": "unknown", "public_attribution": True},
        "provenance": {
            "revision": 1,
            "imported_from": "docs/legacy-list.md",
            "imported_at": "2026-07-25",
            "last_verified_at": None,
        },
        "legacy": {str(key): str(value) for key, value in fields.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="replace imported task files")
    args = parser.parse_args()

    entries = parse_entries(LEGACY.read_text(encoding="utf-8"))
    if not entries:
        raise SystemExit("no legacy entries found")

    if OUTPUT.exists() and any(OUTPUT.glob("verify-*.json")):
        if not args.force:
            raise SystemExit("legacy task files already exist; pass --force to replace them")
        for path in OUTPUT.glob("verify-*.json"):
            path.unlink()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        task = to_task(entry)
        path = OUTPUT / f"{task['id']}.json"
        path.write_text(
            json.dumps(task, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    print(f"imported {len(entries)} tasks into {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
