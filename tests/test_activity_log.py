import json
import time
from pathlib import Path

from modules.core import config
from modules.watcher.activity_log import ActivityLog


def test_ring_cap_drops_oldest(tmp_path):
    act = ActivityLog(path=tmp_path / "activity.json", max_entries=3)
    for name in ["a", "b", "c", "d"]:
        act.append({"kind": "created", "name": name})
    assert len(act.entries) == 3
    assert [e["name"] for e in act.entries] == ["b", "c", "d"]


def test_newest_first_view(tmp_path):
    act = ActivityLog(path=tmp_path / "activity.json", max_entries=5)
    act.append({"kind": "created", "name": "first"})
    act.append({"kind": "deleted", "name": "second"})
    view = act.newest_first(1)
    assert view[0]["name"] == "second"


def test_save_and_reload_across_restart(tmp_path):
    path = tmp_path / "activity.json"
    act = ActivityLog(path=path, max_entries=5)
    act.append({"kind": "modified", "name": "x.md", "diff_summary": "1 line added"})
    act.save()
    assert path.exists()

    reloaded = ActivityLog(path=path, max_entries=5)
    assert reloaded.load() is True
    assert reloaded.entries[-1]["name"] == "x.md"
    assert reloaded.entries[-1]["diff_summary"] == "1 line added"


def test_load_missing_file_starts_empty(tmp_path):
    act = ActivityLog(path=tmp_path / "nope.json")
    assert act.load() is True or act.entries == []
    assert act.entries == []
