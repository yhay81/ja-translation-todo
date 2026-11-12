from build_catalog import category_indexes
from helpers import sample_task


def test_indexes_group_tasks_and_escape_catalog_text():
    unknown = sample_task("verify-a")
    zero = sample_task("verify-z", metrics={"stars": 0})
    high = sample_task("verify-b", metrics={"stars": 12})
    legacy = sample_task("verify-legacy", metrics={"stars": None}, legacy={"Star": "15"})
    other = sample_task("verify-x", category="Other\n# section")
    other["title"]["ja"] = "[link](https://example.org) <img>"

    indexes = category_indexes([unknown, zero, high, other, legacy])

    assert set(indexes) == {"css.md", "javascript.md", "python.md", "command-line.md", "others.md"}
    listing = indexes["javascript.md"]
    assert "/tasks/verify-legacy) · ★ 15" in listing
    assert listing.index("/tasks/verify-legacy)") < listing.index("/tasks/verify-b)")
    assert listing.index("/tasks/verify-b)") < listing.index("/tasks/verify-z)")
    assert listing.index("/tasks/verify-z)") < listing.index("/tasks/verify-a)")
    assert "★ 0" in listing and "スター数未確認" in listing
    assert "/tasks/verify-x)" not in listing
    remaining = indexes["others.md"]
    assert r"## Other \# section" in remaining
    assert r"\[link\](https://example.org) &lt;img&gt;" in remaining
    assert "https://ja.yhay81.com/tasks/verify-x)" in remaining
