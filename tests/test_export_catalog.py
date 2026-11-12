import json

import pytest

from export_catalog import write_tasks
from helpers import sample_task


@pytest.mark.parametrize("invalid_id", ["../escaped", "verify-one"])
def test_invalid_export_preserves_existing_catalog(tmp_path, invalid_id):
    directory = tmp_path / "tasks"
    directory.mkdir()
    original = directory / "verify-one.json"
    original.write_text("original", encoding="utf-8")

    with pytest.raises(ValueError):
        write_tasks([sample_task("verify-one"), sample_task(invalid_id)], directory)

    assert original.read_text(encoding="utf-8") == "original"
    assert not (tmp_path / "escaped.json").exists()


def test_export_replaces_catalog_with_valid_tasks(tmp_path):
    old = tmp_path / "verify-old.json"
    old.write_text("{}", encoding="utf-8")
    task = sample_task()

    preserved = sample_task("verify-existing")
    existing = tmp_path / "verify-existing.json"
    original = json.dumps(preserved, ensure_ascii=False, indent=4)
    existing.write_text(original, encoding="utf-8")

    write_tasks([task, preserved], tmp_path)

    assert existing.read_text(encoding="utf-8") == original

    assert json.loads((tmp_path / f"{task['id']}.json").read_text(encoding="utf-8")) == task
    assert not old.exists()
