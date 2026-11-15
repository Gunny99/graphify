from __future__ import annotations

import pytest

from graphify.task_store import TaskNotFoundError, TaskStore


STAMP = "2026-11-15T00:00:00+00:00"


def _run():
    return {
        "schema_version": 1,
        "run_id": "timeline-run",
        "request": "Exercise the run timeline",
        "status": "queued",
        "execution_policy": {
            "strategy": "single_agent",
            "max_parallel_agents": 1,
            "read_only": False,
        },
        "quality_policy": {
            "accuracy_target": 0.9901,
            "hallucination_max": 0.0099,
            "confidence_level": 0.95,
            "require_evidence_for_material_claims": True,
            "independent_verification": True,
        },
        "cost_policy": {
            "currency": "USD",
            "max_total": 2.0,
            "optimization_rule": "lowest_total_cost_among_qualified",
        },
        "created_at": STAMP,
        "updated_at": STAMP,
        "deadline_at": None,
    }


def _task():
    return {
        "schema_version": 1,
        "task_id": "timeline-task",
        "run_id": "timeline-run",
        "task_type": "implementation",
        "role": "implementer",
        "domain": "technical",
        "objective": "Record a test span",
        "input": {},
        "data_scopes": ["project:demo"],
        "context_refs": [],
        "depends_on": [],
        "required_capabilities": ["implementation"],
        "output_schema": {"type": "object"},
        "acceptance_criteria": ["Span is retrievable"],
        "attempt": 0,
        "max_attempts": 1,
        "status": "queued",
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _store(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    store.create_run(_run(), [_task()])
    return store


def test_record_span_appends_to_existing_event_ledger_and_is_filterable(tmp_path):
    store = _store(tmp_path)
    span = store.record_span(
        "timeline-run",
        task_id="timeline-task",
        name="targeted-tests",
        started_at="2026-11-15T09:00:00+09:00",
        finished_at="2026-11-15T09:00:02+09:00",
        attributes={"stage": "test", "test_count": 12, "cache_hit": False},
    )

    events = store.list_events(
        "timeline-run",
        task_id="timeline-task",
        event_type="span_completed",
    )
    assert len(events) == 1
    assert events[0]["event_id"] == span["event_id"]
    assert events[0]["payload"]["duration_ms"] == 2000.0
    assert events[0]["payload"]["attributes"]["test_count"] == 12
    assert events[0]["payload"]["started_at"] == "2026-11-15T00:00:00+00:00"


def test_timeline_supports_cursor_time_range_and_limit(tmp_path):
    store = _store(tmp_path)
    first = store.record_span(
        "timeline-run",
        name="first",
        started_at="2026-11-15T00:00:00Z",
        finished_at="2026-11-15T00:00:01Z",
    )
    second = store.record_span(
        "timeline-run",
        name="second",
        started_at="2026-11-15T00:01:00Z",
        finished_at="2026-11-15T00:01:01Z",
    )

    page = store.list_events(
        "timeline-run",
        event_type="span_completed",
        after_event_id=first["event_id"],
        since="2026-11-15T00:00:30Z",
        until="2026-11-15T00:02:00Z",
        limit=1,
    )
    assert [event["payload"]["name"] for event in page] == ["second"]
    assert page[0]["event_id"] == second["event_id"]


def test_span_rejects_prompt_like_or_unknown_attributes(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="unsupported span attribute"):
        store.record_span(
            "timeline-run",
            name="bad-span",
            started_at="2026-11-15T00:00:00Z",
            finished_at="2026-11-15T00:00:01Z",
            attributes={"prompt": "do not store this"},
        )


@pytest.mark.parametrize(
    ("started_at", "finished_at", "match"),
    [
        ("2026-11-15T00:00:00", "2026-11-15T00:00:01Z", "timezone"),
        ("2026-11-15T00:00:02Z", "2026-11-15T00:00:01Z", "precede"),
    ],
)
def test_span_rejects_invalid_timestamps(tmp_path, started_at, finished_at, match):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match=match):
        store.record_span(
            "timeline-run",
            name="invalid-span",
            started_at=started_at,
            finished_at=finished_at,
        )


def test_span_requires_task_to_belong_to_the_run(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(TaskNotFoundError, match="does not belong"):
        store.record_span(
            "timeline-run",
            task_id="other-task",
            name="foreign-span",
            started_at="2026-11-15T00:00:00Z",
            finished_at="2026-11-15T00:00:01Z",
        )


def test_timeline_rejects_unknown_runs_and_unbounded_queries(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(TaskNotFoundError, match="run not found"):
        store.list_events("missing-run")
    with pytest.raises(ValueError, match="between 1 and 500"):
        store.list_events("timeline-run", limit=10000)
    with pytest.raises(ValueError, match="later"):
        store.list_events(
            "timeline-run",
            since="2026-11-16T00:00:00Z",
            until="2026-11-15T00:00:00Z",
        )

def test_span_rejects_freeform_labels_and_non_object_attributes(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="stable operation label"):
        store.record_span(
            "timeline-run",
            name="run shell command --token secret",
            started_at="2026-11-15T00:00:00Z",
            finished_at="2026-11-15T00:00:01Z",
        )
    with pytest.raises(ValueError, match="attributes must be an object"):
        store.record_span(
            "timeline-run",
            name="test-span",
            started_at="2026-11-15T00:00:00Z",
            finished_at="2026-11-15T00:00:01Z",
            attributes=["not", "an", "object"],
        )
