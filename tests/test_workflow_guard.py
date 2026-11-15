from __future__ import annotations

import pytest

from graphify.workflow_guard import WorkflowLoopGuard


def _guard(**kwargs):
    return WorkflowLoopGuard(strategy="single", hypothesis="inspect then patch", **kwargs)


def test_repeated_action_trips_on_third_observation():
    guard = _guard()
    assert guard.observe("pytest tests/test_a.py", progress_token="tree-a").status == "continue"
    assert guard.observe("pytest tests/test_a.py", progress_token="tree-a").status == "continue"
    decision = guard.observe("pytest tests/test_a.py", progress_token="tree-a")
    assert decision.status == "redesign"
    assert decision.reasons == ("repeated_action",)


def test_repeated_error_normalizes_run_specific_ids():
    guard = _guard(repeated_action_limit=10)
    guard.observe("call backend", error="HTTP 503 request 11111111-1111-4111-8111-111111111111")
    guard.observe("call backend", error="HTTP 503 request 22222222-2222-4222-8222-222222222222")
    decision = guard.observe(
        "call backend",
        error="HTTP 503 request 33333333-3333-4333-8333-333333333333",
    )
    assert decision.status == "redesign"
    assert "repeated_error" in decision.reasons


def test_no_progress_trips_even_when_action_names_differ():
    guard = _guard(repeated_action_limit=10)
    guard.observe("inspect", progress_token="same-output")
    guard.observe("run tests", progress_token="same-output")
    guard.observe("read logs", progress_token="same-output")
    decision = guard.observe("retry", progress_token="same-output")
    assert decision.status == "redesign"
    assert "no_progress" in decision.reasons


def test_real_progress_resets_loop_window():
    guard = _guard()
    guard.observe("inspect", progress_token="tree-a")
    guard.observe("inspect", progress_token="tree-a")
    decision = guard.observe("inspect", progress_token="tree-b")
    assert decision.status == "continue"
    assert decision.action_repeats == 1
    assert decision.no_progress_steps == 0


def test_redesign_requires_new_hypothesis_and_resets_counters():
    guard = _guard(repeated_action_limit=2)
    guard.observe("repeat", progress_token="tree")
    decision = guard.observe("repeat", progress_token="tree")
    assert decision.needs_redesign
    assert guard.propose_redesign(
        strategy="inspect-dependencies",
        hypothesis="the dependency cache is stale",
        rationale="the repeated patch did not change the output",
    )
    assert guard.snapshot()["redesigns"] == 1
    assert guard.observe("inspect lockfile", progress_token="new-tree").status == "continue"


def test_duplicate_redesign_is_terminal():
    guard = _guard(repeated_action_limit=1)
    assert guard.observe("repeat").status == "redesign"
    assert not guard.propose_redesign(
        strategy="single",
        hypothesis="inspect then patch",
        rationale="try it again",
    )
    decision = guard.observe("repeat")
    assert decision.status == "stop"
    assert "duplicate_redesign" in decision.reasons


def test_redesign_budget_is_bounded():
    guard = _guard(repeated_action_limit=1, max_redesigns=1)
    assert guard.observe("same").status == "redesign"
    assert guard.propose_redesign(
        strategy="different",
        hypothesis="different diagnosis",
        rationale="change intervention",
    )
    decision = guard.observe("same")
    assert decision.status == "stop"
    assert "redesign_budget_exhausted" in decision.reasons
    assert not guard.propose_redesign(
        strategy="third",
        hypothesis="third hypothesis",
        rationale="still blocked",
    )


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_guard_rejects_invalid_thresholds(value):
    with pytest.raises(ValueError):
        _guard(repeated_action_limit=value)


def test_loop_guard_round_trips_all_counters_and_redesign_history():
    guard = _guard(repeated_action_limit=5)
    guard.observe("inspect", error="temporary", progress_token="artifact-a")
    guard.observe("inspect", error="temporary", progress_token="artifact-a")
    assert guard.propose_redesign(
        strategy="inspect-imports",
        hypothesis="a stale import path is masking the real module",
        rationale="test the real import target instead of rerunning the same assertion",
    )
    restored = WorkflowLoopGuard.from_state(guard.to_state())
    assert restored.snapshot() == guard.snapshot()
    assert restored.observe("inspect-imports", progress_token="artifact-b").status == "continue"


def test_loop_guard_rejects_corrupt_persisted_state():
    with pytest.raises(ValueError, match="unsupported"):
        WorkflowLoopGuard.from_state({"schema_version": 99})
