"""Tests for scripts/stats/common.py: the remote budget, part status, dataset selection."""

import pytest

from stats import common
from stats.common import Budget, RemoteLimit, part_status


def test_budget_refuses_a_read_that_would_pass_the_mb_limit():
    budget = Budget(max_mb=1)
    budget.check(600_000)
    budget.charge(600_000)
    with pytest.raises(RemoteLimit, match="1 MB remote limit"):
        budget.check(500_000)  # refused before the read, not after
    assert budget.bytes == 600_000


def test_budget_time_limit(monkeypatch):
    budget = Budget(max_minutes=1)
    budget.check()
    monkeypatch.setattr(common.time, "monotonic", lambda: budget.start + 61)
    with pytest.raises(RemoteLimit, match="1 min remote limit"):
        budget.check()


def test_budget_without_limits_never_stops():
    budget = Budget()
    budget.charge(10**12)
    budget.check(10**12)


@pytest.mark.parametrize(
    ("problems", "incomplete", "status"),
    [([], False, "ok"), ([], True, "incomplete"), (["no remotes"], False, "needs_local"), (["x"], True, "needs_local")],
)
def test_part_status(problems, incomplete, status):
    assert part_status(problems, incomplete) == status


def test_select_datasets():
    names = ["a", "b", "c"]
    assert common.select_datasets(names) == names
    assert common.select_datasets(names, "b") == ["b"]
    assert common.select_datasets(names, exclude="a, c") == ["b"]
    with pytest.raises(SystemExit, match="Dataset 'z' not found"):
        common.select_datasets(names, "z")
