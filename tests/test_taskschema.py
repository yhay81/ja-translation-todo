from __future__ import annotations

import pytest

from build_catalog import check_ready_task
from helpers import sample_task
from translation_hub.taskschema import TaskValidationError, validate_task


def test_ready_requires_a_verifiable_translation_task():
    task = sample_task(status="ready")
    with pytest.raises(ValueError, match="source revision and paths"):
        check_ready_task(task)
    task["permissions"]["translation"] = "explicit"
    task["source"] = {"revision": "v1.2", "paths": ["README.md"]}
    task["provenance"]["last_verified_at"] = "2026-11-13"
    task["validation"] = [{"kind": "structure", "description_ja": "見出しを照合する"}]
    task["evidence"] += [
        {**task["evidence"][0], "kind": kind} for kind in ("translation_policy", "pull_request")
    ]
    check_ready_task(task)


def test_sample_task_is_valid():
    assert validate_task(sample_task())["id"] == "verify-example-repo"


def test_manual_validation_can_omit_command():
    task = sample_task(validation=[{"kind": "semantic_review", "description_ja": "訳語を確認する"}])
    assert validate_task(task) == task


def test_optional_extensions_are_accepted():
    task = sample_task(
        difficulty={
            "score": 3,
            "factors": {"volume": "medium", "workflow": "direct_pr", "domain": "framework_docs"},
        },
        workflow={
            "platform": "crowdin",
            "platform_url": "https://crowdin.com/x",
            "translation_repo": None,
        },
        community={"japanese_team": "active", "team_url": None},
        content_type="official_docs",
        metrics={"stars": 1200, "observed_at": "2026-07-01"},
    )
    validate_task(task)


@pytest.mark.parametrize(
    ("mutate", "message_part"),
    [
        (lambda task: task.pop("credit"), "missing field"),
        (lambda task: task.update(status="banana"), "status"),
        (lambda task: task.update(extra=1), "unknown field"),
        (lambda task: task["project"].update(repository="not-a-repo"), "repository"),
        (
            lambda task: task.update(
                difficulty={
                    "score": 9,
                    "factors": {"volume": "small", "workflow": "platform", "domain": "book"},
                }
            ),
            "difficulty.score",
        ),
        (
            lambda task: task["evidence"].append(
                {
                    "url": "ftp://x",
                    "kind": "repository",
                    "observed_at": "2026-07-01",
                    "note_ja": "x",
                }
            ),
            "url",
        ),
    ],
)
def test_invalid_tasks_are_rejected(mutate, message_part):
    task = sample_task()
    mutate(task)
    with pytest.raises(TaskValidationError) as excinfo:
        validate_task(task)
    assert message_part in str(excinfo.value)
