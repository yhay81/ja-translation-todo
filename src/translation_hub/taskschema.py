"""translation-task/v1 constants and the Worker-side validator.

Full JSON Schema validation (Draft 2020-12) runs in CPython via
``scripts/build_catalog.py``. The Worker cannot afford to vendor
``jsonschema``, so admin writes are checked here with a hand-rolled
validator that enforces the same required fields, enums, and shapes.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

SCHEMA_VERSION = "translation-task/v1"

STATUSES = frozenset(
    {
        "needs_verification",
        "ready",
        "ask_first",
        "in_progress",
        "blocked",
        "done",
        "stale",
    }
)
KINDS = frozenset({"verification", "translation", "maintenance"})
AUTOMATION_LEVELS = frozenset(
    {
        "discover_only",
        "draft_only",
        "draft_pr",
        "pr_allowed",
        "maintenance_allowed",
        "blocked",
    }
)
TRANSLATION_PERMISSIONS = frozenset({"unknown", "explicit", "implied", "forbidden"})
AI_PERMISSIONS = frozenset({"unknown", "explicit", "disclose", "forbidden"})
PR_PERMISSIONS = frozenset({"unknown", "allowed", "ask_first", "forbidden"})
EVIDENCE_KINDS = frozenset(
    {
        "repository",
        "translation_policy",
        "ai_policy",
        "issue",
        "pull_request",
        "contributing",
        "validation",
        "platform",
        "team_activity",
    }
)
VALIDATION_KINDS = frozenset({"command", "structure", "terminology", "semantic_review"})
CREDIT_EXPECTATIONS = frozenset(
    {
        "unknown",
        "commit_author",
        "co_author",
        "contributors_page",
        "acknowledgement",
        "external_link",
    }
)
CHANGE_KINDS = frozenset({"create", "update", "status_change", "auto_refresh", "promote", "import"})

# v1 optional extensions (difficulty / workflow / community / content_type / metrics)
DIFFICULTY_VOLUMES = frozenset({"small", "medium", "large"})
DIFFICULTY_WORKFLOWS = frozenset({"platform", "direct_pr", "fork_hosted", "negotiated"})
DIFFICULTY_DOMAINS = frozenset({"tutorial", "framework_docs", "specification", "book"})
WORKFLOW_PLATFORMS = frozenset(
    {"github", "crowdin", "transifex", "weblate", "gitlocalize", "other"}
)
JAPANESE_TEAM_STATES = frozenset({"active", "inactive", "none", "unknown"})
CONTENT_TYPES = frozenset(
    {"official_docs", "readme", "book", "specification", "ui_strings", "tutorial"}
)

TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

REQUIRED_FIELDS = (
    "schema_version",
    "id",
    "kind",
    "status",
    "title",
    "project",
    "source",
    "target",
    "permissions",
    "automation",
    "evidence",
    "validation",
    "credit",
    "provenance",
)
OPTIONAL_FIELDS = frozenset(
    {"legacy", "difficulty", "workflow", "community", "content_type", "metrics"}
)


class TaskValidationError(ValueError):
    """Raised with a short machine-friendly message for problem responses."""


def validate_task(payload: Any) -> dict[str, Any]:
    """Validate a translation-task/v1 payload; returns it on success."""
    _require(isinstance(payload, dict), "task must be a JSON object")
    unknown = sorted(set(payload) - set(REQUIRED_FIELDS) - OPTIONAL_FIELDS)
    _require(not unknown, f"unknown field: {unknown[0] if unknown else ''}")
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    _require(not missing, f"missing field: {missing[0] if missing else ''}")

    _require(payload["schema_version"] == SCHEMA_VERSION, "schema_version must be v1")
    _require(
        isinstance(payload["id"], str) and TASK_ID_PATTERN.fullmatch(payload["id"]) is not None,
        "id must be a kebab-case slug of at most 120 characters",
    )
    _require_enum(payload["kind"], KINDS, "kind")
    _require_enum(payload["status"], STATUSES, "status")

    title = payload["title"]
    _require(isinstance(title, dict) and set(title) <= {"ja", "en"}, "title must be {ja, en}")
    _require(
        isinstance(title.get("ja"), str) and title["ja"].strip() != "",
        "title.ja is required",
    )
    _require(
        title.get("en") is None or isinstance(title["en"], str),
        "title.en must be a string or null",
    )

    project = payload["project"]
    _require(isinstance(project, dict), "project must be an object")
    _require(
        set(project) <= {"repository", "url", "category", "summary_ja", "license"}
        and {"repository", "url", "category", "summary_ja"} <= set(project),
        "project must contain repository, url, category, summary_ja, license",
    )
    _require(
        isinstance(project["repository"], str)
        and REPOSITORY_PATTERN.fullmatch(project["repository"]) is not None,
        "project.repository must look like owner/name",
    )
    _require_url(project["url"], "project.url")
    _require(
        isinstance(project["category"], str) and project["category"].strip() != "",
        "project.category is required",
    )
    _require(
        isinstance(project["summary_ja"], str) and project["summary_ja"].strip() != "",
        "project.summary_ja is required",
    )
    _require(
        project.get("license") is None or isinstance(project["license"], str),
        "project.license must be a string or null",
    )

    source = payload["source"]
    _require(
        isinstance(source, dict) and set(source) == {"revision", "paths"},
        "source must be {revision, paths}",
    )
    _require(
        source["revision"] is None or isinstance(source["revision"], str),
        "source.revision must be a string or null",
    )
    _require_string_list(source["paths"], "source.paths")

    target = payload["target"]
    _require(
        isinstance(target, dict) and set(target) == {"locale", "paths"},
        "target must be {locale, paths}",
    )
    _require(target["locale"] == "ja-JP", "target.locale must be ja-JP")
    _require_string_list(target["paths"], "target.paths")

    permissions = payload["permissions"]
    _require(
        isinstance(permissions, dict)
        and set(permissions) == {"translation", "ai_assistance", "pull_request"},
        "permissions must be {translation, ai_assistance, pull_request}",
    )
    _require_enum(permissions["translation"], TRANSLATION_PERMISSIONS, "permissions.translation")
    _require_enum(permissions["ai_assistance"], AI_PERMISSIONS, "permissions.ai_assistance")
    _require_enum(permissions["pull_request"], PR_PERMISSIONS, "permissions.pull_request")

    automation = payload["automation"]
    _require(
        isinstance(automation, dict) and set(automation) == {"level", "allowed_actions"},
        "automation must be {level, allowed_actions}",
    )
    _require_enum(automation["level"], AUTOMATION_LEVELS, "automation.level")
    _require_string_list(automation["allowed_actions"], "automation.allowed_actions")

    evidence = payload["evidence"]
    _require(isinstance(evidence, list), "evidence must be an array")
    for index, item in enumerate(evidence):
        _validate_evidence(item, f"evidence[{index}]")

    validation = payload["validation"]
    _require(isinstance(validation, list), "validation must be an array")
    for index, item in enumerate(validation):
        _require(
            isinstance(item, dict) and set(item) == {"kind", "command", "description_ja"},
            f"validation[{index}] must be {{kind, command, description_ja}}",
        )
        _require_enum(item["kind"], VALIDATION_KINDS, f"validation[{index}].kind")
        _require(
            item["command"] is None or isinstance(item["command"], str),
            f"validation[{index}].command must be a string or null",
        )
        _require(
            isinstance(item["description_ja"], str) and item["description_ja"].strip() != "",
            f"validation[{index}].description_ja is required",
        )

    credit = payload["credit"]
    _require(
        isinstance(credit, dict) and set(credit) == {"expected", "public_attribution"},
        "credit must be {expected, public_attribution}",
    )
    _require_enum(credit["expected"], CREDIT_EXPECTATIONS, "credit.expected")
    _require(isinstance(credit["public_attribution"], bool), "credit.public_attribution")

    provenance = payload["provenance"]
    _require(
        isinstance(provenance, dict)
        and set(provenance) == {"revision", "imported_from", "imported_at", "last_verified_at"},
        "provenance must be {revision, imported_from, imported_at, last_verified_at}",
    )
    _require(
        isinstance(provenance["revision"], int)
        and not isinstance(provenance["revision"], bool)
        and provenance["revision"] >= 1,
        "provenance.revision must be an integer >= 1",
    )
    _require(
        provenance["imported_from"] is None or isinstance(provenance["imported_from"], str),
        "provenance.imported_from must be a string or null",
    )
    _require_date(provenance["imported_at"], "provenance.imported_at")
    if provenance["last_verified_at"] is not None:
        _require_date(provenance["last_verified_at"], "provenance.last_verified_at")

    if "legacy" in payload:
        legacy = payload["legacy"]
        _require(isinstance(legacy, dict), "legacy must be an object")
        for key, value in legacy.items():
            _require(
                isinstance(key, str) and (value is None or isinstance(value, str)),
                "legacy values must be strings or null",
            )
    if "difficulty" in payload:
        _validate_difficulty(payload["difficulty"])
    if "workflow" in payload:
        _validate_workflow(payload["workflow"])
    if "community" in payload:
        _validate_community(payload["community"])
    if "content_type" in payload:
        _require_enum(payload["content_type"], CONTENT_TYPES, "content_type")
    if "metrics" in payload:
        _validate_metrics(payload["metrics"])
    return payload


def search_text(task: dict[str, Any]) -> str:
    title = task["title"]
    project = task["project"]
    return " ".join(
        (
            str(task["id"]),
            str(title.get("ja", "")),
            str(title.get("en") or ""),
            str(project["repository"]),
            str(project["category"]),
            str(project["summary_ja"]),
        )
    ).casefold()


def _validate_difficulty(value: Any) -> None:
    _require(
        isinstance(value, dict) and set(value) == {"score", "factors"},
        "difficulty must be {score, factors}",
    )
    _require(
        isinstance(value["score"], int)
        and not isinstance(value["score"], bool)
        and 1 <= value["score"] <= 5,
        "difficulty.score must be an integer from 1 to 5",
    )
    factors = value["factors"]
    _require(
        isinstance(factors, dict) and set(factors) == {"volume", "workflow", "domain"},
        "difficulty.factors must be {volume, workflow, domain}",
    )
    _require_enum(factors["volume"], DIFFICULTY_VOLUMES, "difficulty.factors.volume")
    _require_enum(factors["workflow"], DIFFICULTY_WORKFLOWS, "difficulty.factors.workflow")
    _require_enum(factors["domain"], DIFFICULTY_DOMAINS, "difficulty.factors.domain")


def _validate_workflow(value: Any) -> None:
    _require(
        isinstance(value, dict) and set(value) == {"platform", "platform_url", "translation_repo"},
        "workflow must be {platform, platform_url, translation_repo}",
    )
    _require_enum(value["platform"], WORKFLOW_PLATFORMS, "workflow.platform")
    if value["platform_url"] is not None:
        _require_url(value["platform_url"], "workflow.platform_url")
    _require(
        value["translation_repo"] is None
        or (
            isinstance(value["translation_repo"], str)
            and REPOSITORY_PATTERN.fullmatch(value["translation_repo"]) is not None
        ),
        "workflow.translation_repo must look like owner/name or null",
    )


def _validate_community(value: Any) -> None:
    _require(
        isinstance(value, dict) and set(value) == {"japanese_team", "team_url"},
        "community must be {japanese_team, team_url}",
    )
    _require_enum(value["japanese_team"], JAPANESE_TEAM_STATES, "community.japanese_team")
    if value["team_url"] is not None:
        _require_url(value["team_url"], "community.team_url")


def _validate_metrics(value: Any) -> None:
    _require(
        isinstance(value, dict) and set(value) == {"stars", "observed_at"},
        "metrics must be {stars, observed_at}",
    )
    _require(
        value["stars"] is None
        or (
            isinstance(value["stars"], int)
            and not isinstance(value["stars"], bool)
            and value["stars"] >= 0
        ),
        "metrics.stars must be a non-negative integer or null",
    )
    _require_date(value["observed_at"], "metrics.observed_at")


def _validate_evidence(item: Any, label: str) -> None:
    _require(
        isinstance(item, dict) and set(item) == {"url", "kind", "observed_at", "note_ja"},
        f"{label} must be {{url, kind, observed_at, note_ja}}",
    )
    _require_url(item["url"], f"{label}.url")
    _require_enum(item["kind"], EVIDENCE_KINDS, f"{label}.kind")
    _require_date(item["observed_at"], f"{label}.observed_at")
    _require(
        isinstance(item["note_ja"], str) and 1 <= len(item["note_ja"].strip()) <= 2_000,
        f"{label}.note_ja must be a non-empty string of at most 2000 characters",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TaskValidationError(message)


def _require_enum(value: Any, allowed: frozenset[str], label: str) -> None:
    _require(value in allowed, f"{label} must be one of: {', '.join(sorted(allowed))}")


def _require_url(value: Any, label: str) -> None:
    _require(isinstance(value, str), f"{label} must be an HTTP(S) URL")
    parts = urlsplit(value)
    _require(
        parts.scheme in {"http", "https"} and bool(parts.netloc) and parts.username is None,
        f"{label} must be a public HTTP(S) URL",
    )


def _require_date(value: Any, label: str) -> None:
    _require(isinstance(value, str), f"{label} must be an ISO date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise TaskValidationError(f"{label} must be an ISO date") from exc


def _require_string_list(value: Any, label: str) -> None:
    _require(
        isinstance(value, list) and all(isinstance(item, str) for item in value),
        f"{label} must be an array of strings",
    )
