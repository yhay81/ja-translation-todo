from __future__ import annotations

from helpers import sample_task
from translation_hub.catalog import catalog_stats, search_records, task_bundle


def record(task, revision=1, updated_at=1_700_000_000):
    return {
        "task": task,
        "task_revision": revision,
        "created_at": updated_at,
        "updated_at": updated_at,
    }


RECORDS = [
    record(
        sample_task(
            "verify-react",
            repository="facebook/react",
            status="ready",
            category="JavaScript",
            difficulty={
                "score": 2,
                "factors": {"volume": "small", "workflow": "platform", "domain": "tutorial"},
            },
            workflow={"platform": "crowdin", "platform_url": None, "translation_repo": None},
            metrics={"stars": 200_000, "observed_at": "2026-07-01"},
        ),
        updated_at=1_700_000_300,
    ),
    record(
        sample_task(
            "verify-kubernetes",
            repository="kubernetes/website",
            category="Infra",
            difficulty={
                "score": 5,
                "factors": {"volume": "large", "workflow": "direct_pr", "domain": "specification"},
            },
        ),
        updated_at=1_700_000_200,
    ),
    record(
        sample_task("verify-requests", repository="psf/requests", category="Python"),
        updated_at=1_700_000_100,
    ),
]


def test_filters_by_status_category_and_query():
    assert search_records(RECORDS, status="ready")["total"] == 1
    assert search_records(RECORDS, category="python")["total"] == 1
    assert search_records(RECORDS, query="kubernetes")["total"] == 1
    assert search_records(RECORDS, difficulty="easy")["total"] == 1
    assert search_records(RECORDS, platform="crowdin")["total"] == 1


def test_sorts_and_paginates():
    by_updated = search_records(RECORDS, sort="updated", limit=2)
    assert [r["task"]["id"] for r in by_updated["items"]] == ["verify-react", "verify-kubernetes"]
    assert by_updated["next_cursor"] == "2"

    by_stars = search_records(RECORDS, sort="stars")
    assert by_stars["items"][0]["task"]["id"] == "verify-react"

    by_status = search_records(RECORDS, sort="status")
    assert by_status["items"][0]["task"]["status"] == "ready"

    by_difficulty = search_records(RECORDS, sort="difficulty")
    assert by_difficulty["items"][0]["task"]["id"] == "verify-react"


def test_stats_aggregates():
    stats = catalog_stats(RECORDS)
    assert stats["total"] == 3
    assert stats["by_status"]["ready"] == 1
    assert stats["by_category"] == {"Infra": 1, "JavaScript": 1, "Python": 1}
    assert stats["by_difficulty"]["2"] == 1
    assert stats["by_difficulty"]["5"] == 1
    assert stats["by_difficulty"]["unrated"] == 1


def test_task_bundle_contract_and_links():
    bundle = task_bundle(RECORDS[0], catalog_revision="cat_x")
    assert bundle["catalog_revision"] == "cat_x"
    assert bundle["task_revision"] == 1
    assert bundle["links"]["self"] == "/api/v2/tasks/verify-react"
    assert bundle["links"]["page"] == "/tasks/verify-react"
    assert bundle["links"]["edit"].endswith("/catalog/tasks/verify-react.json")
    assert bundle["execution_contract"]["must_not_auto_merge"] is True
