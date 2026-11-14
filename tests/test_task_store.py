from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import pytest

from graphify.task_store import (
    TaskLeaseError,
    TaskStore,
    TaskStoreError,
)
from graphify.orchestration import OrchestrationValidationError


STAMP = "2026-11-14T00:00:00Z"


def _quality(role: str = "researcher", *, accuracy: float = 0.995, hallucination: float = 0.005):
    return {
        "role": role,
        "domain": "technical",
        "benchmark_id": "technical-v1",
        "evaluation_set_hash": "sha256:held-out",
        "evaluator_version": "human-v1",
        "sample_size": 500,
        "confidence_level": 0.95,
        "accuracy_lower_bound": accuracy,
        "hallucination_upper_bound": hallucination,
        "evaluated_at": STAMP,
    }


def _agent(
    agent_id: str,
    provider: str,
    model: str,
    *,
    role: str = "researcher",
    input_cost: float = 0.2,
    cached_cost: float = 0.02,
    output_cost: float = 0.5,
    accuracy: float = 0.995,
    hallucination: float = 0.005,
    max_concurrency: int = 2,
) -> dict:
    return {
        "schema_version": 1,
        "agent_id": agent_id,
        "provider": provider,
        "model": model,
        "model_version": "1",
        "protocol": "mcp",
        "capabilities": ["research", "verify"],
        "max_concurrency": max_concurrency,
        "status": "active",
        "allowed_data_scopes": ["project:demo"],
        "cost_profile": {
            "currency": "USD",
            "input_cost_per_million_tokens": input_cost,
            "cached_input_cost_per_million_tokens": cached_cost,
            "output_cost_per_million_tokens": output_cost,
            "verification_cost_per_task": 0.03,
            "expected_retry_cost_per_task": 0.04,
            "expected_escalation_cost_per_task": 0.05,
            "orchestration_cost_per_task": 0.01,
            "pricing_source": f"{provider}-published-prices-2026-11",
            "effective_at": STAMP,
        },
        "quality_profiles": [_quality(role, accuracy=accuracy, hallucination=hallucination)],
        "registered_at": STAMP,
        "updated_at": STAMP,
    }


def _run(
    run_id: str = "run-1",
    *,
    max_total: float = 5.0,
    strategy: str = "single_with_review",
    max_parallel_agents: int = 1,
) -> dict:
    return {
        "schema_version": 1,
        "run_id": run_id,
        "request": "Verify the stated behaviour from primary sources.",
        "status": "queued",
        "execution_policy": {
            "strategy": strategy,
            "max_parallel_agents": max_parallel_agents,
            "read_only": strategy == "read_only_exploration",
            "write_conflicts_checked": strategy == "parallel_independent",
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
            "max_total": max_total,
            "optimization_rule": "lowest_total_cost_among_qualified",
        },
        "created_at": STAMP,
        "updated_at": STAMP,
        "deadline_at": None,
    }


def _task(
    task_id: str,
    run_id: str = "run-1",
    *,
    depends_on=None,
    estimate=1_000,
    domain="technical",
):
    return {
        "schema_version": 1,
        "task_id": task_id,
        "run_id": run_id,
        "task_type": "research",
        "role": "researcher",
        "domain": domain,
        "objective": f"Research {task_id}",
        "input": {
            "question": "What is supported by the source?",
            "estimated_input_tokens": estimate,
            "estimated_output_tokens": 1_000,
            "estimated_cached_input_tokens": 0,
        },
        "data_scopes": ["project:demo"],
        "context_refs": [],
        "depends_on": list(depends_on or []),
        "required_capabilities": ["research"],
        "output_schema": {"type": "object"},
        "acceptance_criteria": ["All material claims have evidence"],
        "cost_budget": {"currency": "USD", "max_total": 5.0},
        "attempt": 0,
        "max_attempts": 2,
        "status": "queued",
        "created_at": STAMP,
        "updated_at": STAMP,
        "deadline_at": None,
    }


def _evidence():
    return {
        "source_id": "source-1",
        "source_type": "repository_file",
        "uri": "https://example.invalid/source",
        "location": "docs/api.md:L10-L12",
        "excerpt": "The API guarantees stable task identifiers.",
        "content_hash": "sha256:source",
    }


def _result(task_id: str, agent: dict, *, result_id="result-1", attempt=1):
    return {
        "schema_version": 1,
        "result_id": result_id,
        "run_id": "run-1",
        "task_id": task_id,
        "attempt": attempt,
        "agent": {
            "agent_id": agent["agent_id"],
            "provider": agent["provider"],
            "model": agent["model"],
            "model_version": agent["model_version"],
        },
        "status": "submitted",
        "output": {"answer": "Stable task identifiers are guaranteed."},
        "claims": [{
            "claim_id": "claim-1",
            "statement": "Stable task identifiers are guaranteed.",
            "claim_type": "factual",
            "material": True,
            "evidence": [_evidence()],
        }],
        "evidence": [_evidence()],
        "uncertainties": [],
        "usage": {
            "input_tokens": 1_000,
            "output_tokens": 100,
            "cached_input_tokens": 100,
            "direct_cost": 999.0,
            "currency": "USD",
            "pricing_source": "untrusted-agent-claim",
        },
        "created_at": STAMP,
    }


def _review(
    result: dict, verifier: dict, *, review_task_id: str, review_id="review-1"
):
    return {
        "schema_version": 1,
        "review_id": review_id,
        "run_id": result["run_id"],
        "task_id": result["task_id"],
        "result_id": result["result_id"],
        "review_task_id": review_task_id,
        "reviewer": {
            "agent_id": verifier["agent_id"],
            "provider": verifier["provider"],
            "model": verifier["model"],
            "model_version": verifier["model_version"],
        },
        "status": "accepted",
        "claims": [{
            "claim_id": "claim-1",
            "verdict": "supported",
            "evidence": [_evidence()],
            "notes": "Matched the cited source.",
        }],
        "usage": {
            "input_tokens": 1_000,
            "output_tokens": 100,
            "cached_input_tokens": 100,
            "direct_cost": 999.0,
            "currency": "USD",
            "pricing_source": "untrusted-reviewer-claim",
        },
        "created_at": STAMP,
    }


def _register(store: TaskStore, agent: dict) -> str:
    token = f"test-agent-token::{agent['agent_id']}::secret"
    profile = dict(agent)
    profile["auth_token"] = token
    store.register_agent(profile, trusted_profile=True)
    store.authenticate_agent(agent["agent_id"], token)
    return token


def test_claim_uses_lowest_cost_qualified_agent_and_enforces_dependency(tmp_path):
    store = TaskStore(tmp_path / "graphify-out" / "orchestrator.sqlite3")
    premium = _agent("premium", "provider-premium", "premium-model", input_cost=0.5, output_cost=1.0)
    budget = _agent("budget", "provider-budget", "budget-model", input_cost=0.05, output_cost=0.1)
    unqualified = _agent(
        "cheap-unqualified", "provider-unqualified", "cheap-model",
        input_cost=0.001, output_cost=0.001, accuracy=0.98, hallucination=0.02,
    )
    verifier = _agent(
        "verifier", "independent-provider", "verifier-model",
        role="verifier", input_cost=0.1, output_cost=0.2,
    )
    for agent in (premium, budget, unqualified, verifier):
        _register(store, agent)
    store.create_run(_run(), [_task("task-1"), _task("task-2", depends_on=["task-1"])])

    assert store.claim_task("premium") is None
    assert store.claim_task("cheap-unqualified") is None
    claimed = store.claim_task("budget")
    assert claimed is not None
    assert claimed["task_id"] == "task-1"
    assert claimed["attempt"] == 1
    assert claimed["lease_token"]
    assert store.claim_task("budget") is None  # task-2 waits for task-1 acceptance

    result = _result("task-1", budget)
    returned = store.submit_result(result, claimed["lease_token"])
    assert returned["tasks"][0]["status"] == "submitted"
    assert store.get_run_status("run-1")["tasks"][1]["status"] == "queued"
    assert store.claim_task("budget") is None

    verification = store.claim_task("verifier")
    assert verification is not None
    assert verification["task_type"] == "verification"
    payload = store.get_verification_payload(
        verification["task_id"], "verifier", verification["lease_token"]
    )
    assert payload["result"]["result_id"] == result["result_id"]
    assert payload["result"]["output"]["answer"]
    with pytest.raises(TaskLeaseError):
        store.get_verification_payload(
            verification["task_id"], "verifier", "wrong-token"
        )
    review = _review(result, verifier, review_task_id=verification["task_id"])
    with pytest.raises(TaskLeaseError):
        store.submit_review(review, "wrong-token")
    reviewed = store.submit_review(review, verification["lease_token"])
    task_states = {task["task_id"]: task["status"] for task in reviewed["tasks"]}
    assert task_states["task-1"] == "accepted"
    assert task_states["task-2"] == "queued"
    assert store.claim_task("budget")["task_id"] == "task-2"

    # Token charges are calculated from the trusted price sheet, never the agent's $999 claim.
    cost = store.get_run_status("run-1")["total_direct_cost"]
    expected_result_cost = (900 * 0.05 + 100 * 0.02 + 100 * 0.1) / 1_000_000
    expected_review_cost = (900 * 0.1 + 100 * 0.02 + 100 * 0.2) / 1_000_000
    assert math.isclose(cost, expected_result_cost + expected_review_cost)


def test_agent_authentication_token_is_required_and_not_returned_by_list(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent = _agent("agent-1", "provider", "model")
    token = _register(store, agent)
    with pytest.raises(TaskLeaseError, match="authentication failed"):
        store.authenticate_agent("agent-1", "wrong-token")
    listed = store.list_agents()
    assert len(listed) == 1
    assert listed[0]["agent_id"] == "agent-1"
    assert "auth_token" not in listed[0]
    assert "_auth_token_hash" not in listed[0]


def test_agent_cannot_self_assert_trusted_quality_or_price_profile(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    profile = _agent("agent-1", "provider", "model")
    with pytest.raises(TaskStoreError, match="trusted local operator"):
        store.register_agent(profile)
    _register(store, profile)


def test_leases_reject_wrong_tokens_and_retry_only_within_attempt_budget(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent = _agent("agent-1", "provider", "model", max_concurrency=1)
    _register(store, agent)
    task = _task("task-1")
    task["max_attempts"] = 2
    store.create_run(_run(), [task])

    first = store.claim_task("agent-1")
    assert first is not None and first["attempt"] == 1
    with pytest.raises(TaskLeaseError, match="invalid lease token"):
        store.fail_task("task-1", "agent-1", "wrong-token", "temporary failure")
    failed = store.fail_task("task-1", "agent-1", first["lease_token"], "temporary failure")
    assert failed["tasks"][0]["status"] == "queued"

    second = store.claim_task("agent-1")
    assert second is not None and second["attempt"] == 2
    terminal = store.fail_task(
        "task-1", "agent-1", second["lease_token"], "permanent failure", retryable=True
    )
    assert terminal["tasks"][0]["status"] == "failed"
    assert terminal["run"]["status"] == "failed"


def test_expected_cost_is_reserved_across_concurrent_leases(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    expensive = _agent(
        "agent-1", "provider", "model",
        input_cost=0.2, cached_cost=0.02, output_cost=0.5,
    )
    _register(store, expensive)
    first_task = _task("task-1", estimate=1_000_000)
    second_task = _task("task-2", estimate=1_000_000)
    first_task["input"]["write_set"] = ["src/one.py"]
    second_task["input"]["write_set"] = ["src/two.py"]
    store.create_run(
        _run(max_total=0.5, strategy="parallel_independent", max_parallel_agents=2),
        [first_task, second_task],
    )
    first = store.claim_task("agent-1")
    assert first is not None
    assert store.claim_task("agent-1") is None
    status = store.get_run_status("run-1")
    assert status["tasks"][0]["status"] == "leased"
    assert status["tasks"][1]["status"] == "queued"
    assert status["reserved_cost"] > 0


def test_independent_queued_tasks_continue_after_another_branch_fails(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent = _agent("agent-1", "provider", "model", max_concurrency=2)
    _register(store, agent)
    first_task = _task("failed-branch")
    second_task = _task("independent-branch")
    first_task["input"]["write_set"] = ["src/first.py"]
    second_task["input"]["write_set"] = ["src/second.py"]
    store.create_run(
        _run(strategy="parallel_independent", max_parallel_agents=2),
        [first_task, second_task],
    )
    first = store.claim_task("agent-1")
    assert first is not None
    second = store.claim_task("agent-1")
    assert second is not None
    status = store.fail_task(
        first["task_id"], "agent-1", first["lease_token"], "permanent", retryable=False
    )
    assert status["run"]["status"] in {"running", "queued"}
    assert status["tasks"][1]["status"] == "leased"

def test_read_only_exploration_results_with_material_claims_are_independently_reviewed(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    explorer = _agent("explorer", "explorer-provider", "explorer-model", max_concurrency=2)
    explorer["capabilities"].append("read_only")
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, explorer)
    _register(store, verifier)

    tasks = [_task("explore-1"), _task("explore-2")]
    for task in tasks:
        task["input"]["read_only"] = True
        task["required_capabilities"] = ["read_only", "research"]
    store.create_run(
        _run(strategy="read_only_exploration", max_parallel_agents=2),
        tasks,
    )

    claimed = store.claim_task("explorer")
    assert claimed is not None
    result = _result(claimed["task_id"], explorer)
    submitted = store.submit_result(result, claimed["lease_token"])
    states = {task["task_id"]: task["status"] for task in submitted["tasks"]}
    assert states[claimed["task_id"]] == "submitted"

    verification = store.claim_task("verifier")
    assert verification is not None
    assert verification["task_type"] == "verification"
    payload = store.get_verification_payload(
        verification["task_id"], "verifier", verification["lease_token"]
    )
    assert payload["result"]["result_id"] == result["result_id"]




def test_task_scope_filters_agents_and_prevents_out_of_scope_cheapest_agent_from_blocking(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    outsider = _agent("outsider", "cheap-provider", "cheap-model", input_cost=0.001)
    outsider["allowed_data_scopes"] = ["project:other"]
    allowed = _agent("allowed", "allowed-provider", "allowed-model", input_cost=0.2)
    _register(store, outsider)
    _register(store, allowed)
    task = _task("scoped-task")
    task["input"]["write_set"] = ["src/a.py"]
    second = _task("second-task")
    second["input"]["write_set"] = ["src/b.py"]
    store.create_run(_run(strategy="parallel_independent", max_parallel_agents=2), [task, second])

    assert store.claim_task("outsider") is None
    claimed = store.claim_task("allowed")
    assert claimed is not None and claimed["task_id"] == "scoped-task"


def test_stale_active_agent_does_not_block_cheaper_agent_ranking(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    offline = _agent("offline", "cheap-provider", "cheap-model", input_cost=0.001)
    polling = _agent("polling", "polling-provider", "polling-model", input_cost=0.2)
    _register(store, offline)
    _register(store, polling)
    task = _task("task-1")
    task["input"]["write_set"] = ["src/a.py"]
    second = _task("task-2")
    second["input"]["write_set"] = ["src/b.py"]
    store.create_run(_run(strategy="parallel_independent", max_parallel_agents=2), [task, second])
    with store._connect() as con:
        con.execute(
            "UPDATE agents SET updated_at=? WHERE agent_id=?",
            ("2000-01-01T00:00:00+00:00", "offline"),
        )

    claimed = store.claim_task("polling")
    assert claimed is not None and claimed["task_id"] == "task-1"


def test_failed_agent_is_skipped_when_an_alternative_is_available(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    cheap = _agent("cheap", "cheap-provider", "cheap-model", input_cost=0.001)
    fallback = _agent("fallback", "fallback-provider", "fallback-model", input_cost=0.2)
    _register(store, cheap)
    _register(store, fallback)
    task = _task("task-1")
    task["input"]["write_set"] = ["src/a.py"]
    second = _task("task-2")
    second["input"]["write_set"] = ["src/b.py"]
    store.create_run(_run(strategy="parallel_independent", max_parallel_agents=2), [task, second])

    first = store.claim_task("cheap")
    assert first is not None
    failed = store.fail_task("task-1", "cheap", first["lease_token"], "transient failure")
    assert failed["tasks"][0]["status"] == "queued"

    second_claim = store.claim_task("fallback")
    assert second_claim is not None and second_claim["attempt"] == 2


def test_single_with_review_always_creates_review_for_claimless_implementation(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, producer)
    _register(store, verifier)
    task = _task("implementation")
    task["task_type"] = "implementation"
    store.create_run(_run(strategy="single_with_review"), [task])

    claimed = store.claim_task("producer")
    assert claimed is not None
    result = _result("implementation", producer)
    result["claims"] = []
    result["evidence"] = []
    submitted = store.submit_result(result, claimed["lease_token"])
    source = next(t for t in submitted["tasks"] if t["task_id"] == "implementation")
    verification = next(t for t in submitted["tasks"] if t["task_type"] == "verification")
    assert source["status"] == "submitted"
    assert source["verification_task_id"] == verification["task_id"]
    assert verification["status"] == "queued"


def test_rejected_review_is_terminal_and_never_queues_a_second_reviewer(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, producer)
    _register(store, verifier)
    store.create_run(_run(), [_task("task-1")])
    claimed = store.claim_task("producer")
    assert claimed is not None
    result = _result("task-1", producer)
    store.submit_result(result, claimed["lease_token"])
    verification = store.claim_task("verifier")
    assert verification is not None
    review = _review(result, verifier, review_task_id=verification["task_id"])
    review["status"] = "rejected"
    review["claims"][0]["verdict"] = "contradicted"

    status = store.submit_review(review, verification["lease_token"])
    states = {t["task_id"]: t["status"] for t in status["tasks"]}
    assert states["task-1"] == "rejected"
    assert states[verification["task_id"]] == "accepted"
    assert status["run"]["status"] == "failed"


def test_insufficient_review_without_an_alternate_verifier_becomes_provisional(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, producer)
    _register(store, verifier)
    store.create_run(_run(), [_task("task-1")])
    claimed = store.claim_task("producer")
    assert claimed is not None
    result = _result("task-1", producer)
    store.submit_result(result, claimed["lease_token"])
    verification = store.claim_task("verifier")
    assert verification is not None
    review = _review(result, verifier, review_task_id=verification["task_id"])
    review["status"] = "needs_review"
    review["claims"][0]["verdict"] = "insufficient"

    status = store.submit_review(review, verification["lease_token"])
    states = {t["task_id"]: t["status"] for t in status["tasks"]}
    assert states["task-1"] == "needs_review"
    assert states[verification["task_id"]] == "accepted"
    assert status["run"]["status"] == "provisional"


def test_task_that_cannot_fit_run_budget_is_failed_instead_of_left_queued(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    expensive = _agent(
        "expensive", "expensive-provider", "expensive-model",
        input_cost=100.0, cached_cost=100.0, output_cost=100.0,
    )
    _register(store, expensive)
    store.create_run(_run(max_total=0.01, strategy="single_agent"), [_task("task-1")])

    assert store.claim_task("expensive") is None
    status = store.get_run_status("run-1")
    assert status["tasks"][0]["status"] == "failed"
    assert status["run"]["status"] == "failed"



def test_failed_verification_marks_source_needs_review_and_run_provisional(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, producer)
    _register(store, verifier)
    store.create_run(_run(), [_task("task-1")])

    claimed = store.claim_task("producer")
    assert claimed is not None
    result = _result("task-1", producer)
    store.submit_result(result, claimed["lease_token"])
    verification = store.claim_task("verifier")
    assert verification is not None

    status = store.fail_task(
        verification["task_id"], "verifier", verification["lease_token"],
        "verifier process crashed", retryable=False,
    )
    states = {task["task_id"]: task["status"] for task in status["tasks"]}
    assert states["task-1"] == "needs_review"
    assert states[verification["task_id"]] == "failed"
    assert status["run"]["status"] == "provisional"


def test_exhausted_verification_lease_marks_source_needs_review(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier1 = _agent("verifier-1", "verifier-provider-1", "verifier-model-1", role="verifier")
    verifier2 = _agent("verifier-2", "verifier-provider-2", "verifier-model-2", role="verifier")
    _register(store, producer)
    _register(store, verifier1)
    _register(store, verifier2)
    store.create_run(_run(), [_task("task-1")])

    claimed = store.claim_task("producer")
    assert claimed is not None
    result = _result("task-1", producer)
    store.submit_result(result, claimed["lease_token"])
    first_verification = store.claim_task("verifier-1")
    assert first_verification is not None
    with store._transaction() as con:
        con.execute(
            "UPDATE tasks SET lease_expires_at=0 WHERE task_id=?",
            (first_verification["task_id"],),
        )

    second_verification = store.claim_task("verifier-2")
    assert second_verification is not None
    assert second_verification["attempt"] == 2
    with store._transaction() as con:
        con.execute(
            "UPDATE tasks SET lease_expires_at=0 WHERE task_id=?",
            (second_verification["task_id"],),
        )

    # Any task claim runs the expiry reaper before selecting a new task.
    store.claim_task("producer")
    status = store.get_run_status("run-1")
    states = {task["task_id"]: task["status"] for task in status["tasks"]}
    assert states["task-1"] == "needs_review"
    assert states[second_verification["task_id"]] == "failed"
    assert status["run"]["status"] == "provisional"


def test_result_cannot_adopt_an_existing_task_as_its_verification_task(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    _register(store, producer)
    store.create_run(_run(), [_task("task-1")])

    claimed = store.claim_task("producer")
    assert claimed is not None

    # A task in another run can occupy the predictable verification::<result_id>
    # namespace. It must never be adopted as the verifier for this result.
    store.create_run(
        _run("run-2", strategy="single_agent"),
        [_task("verification::collision", "run-2")],
    )
    result = _result("task-1", producer, result_id="collision")
    with pytest.raises(TaskStoreError, match="verification task ID collision"):
        store.submit_result(result, claimed["lease_token"])

    status = store.get_run_status("run-1")
    assert status["tasks"][0]["status"] == "leased"
    with store._connect() as con:
        assert con.execute(
            "SELECT COUNT(*) FROM results WHERE result_id='collision'"
        ).fetchone()[0] == 0


@pytest.mark.parametrize("strategy", ["single_agent", "single_with_review"])
def test_single_session_strategy_rejects_multiple_main_tasks(tmp_path, strategy):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    with pytest.raises(OrchestrationValidationError, match="exactly one main work task"):
        store.create_run(
            _run(strategy=strategy),
            [_task("task-1"), _task("task-2")],
        )



def test_failed_result_retry_reserves_only_unspent_cost(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent = _agent(
        "budget-agent", "provider", "model",
        input_cost=100.0, cached_cost=0.0, output_cost=100.0,
    )
    _register(store, agent)
    task = _task("task-1")
    task["input"]["estimated_input_tokens"] = 1_000_000
    task["input"]["estimated_output_tokens"] = 1_000_000
    task["input"]["estimated_cached_input_tokens"] = 0
    task["cost_budget"]["max_total"] = 300.0
    store.create_run(_run(max_total=205.0, strategy="single_agent"), [task])

    claimed = store.claim_task("budget-agent")
    assert claimed is not None
    failed_result = _result("task-1", agent)
    failed_result["status"] = "failed"
    failed_result["usage"].update({
        "input_tokens": 100_000,
        "output_tokens": 0,
        "cached_input_tokens": 0,
    })
    status = store.submit_result(failed_result, claimed["lease_token"])

    actual = status["total_direct_cost"]
    reserved = status["reserved_cost"]
    assert status["tasks"][0]["status"] == "queued"
    assert status["run"]["status"] == "queued"
    # This attempt has an exact usage record, so its old estimate is released;
    # the next lease will receive a fresh estimate.
    assert reserved == pytest.approx(0.0)
    assert actual + reserved <= 205.0


def test_insufficient_review_retry_reserves_only_unspent_verification_cost(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier1 = _agent(
        "verifier-1", "verifier-provider-1", "verifier-model-1",
        role="verifier", input_cost=0.1, cached_cost=0.01, output_cost=0.2,
    )
    verifier2 = _agent(
        "verifier-2", "verifier-provider-2", "verifier-model-2",
        role="verifier", input_cost=0.2, cached_cost=0.02, output_cost=0.4,
    )
    _register(store, producer)
    _register(store, verifier1)
    _register(store, verifier2)
    store.create_run(_run(), [_task("task-1")])

    producer_lease = store.claim_task("producer")
    assert producer_lease is not None
    result = _result("task-1", producer)
    store.submit_result(result, producer_lease["lease_token"])

    verification = store.claim_task("verifier-1")
    assert verification is not None
    review = _review(result, verifier1, review_task_id=verification["task_id"])
    review["status"] = "needs_review"
    review["claims"][0]["verdict"] = "insufficient"

    status = store.submit_review(review, verification["lease_token"])
    with store._connect() as con:
        row = con.execute(
            "SELECT task_json FROM tasks WHERE task_id=?",
            (verification["task_id"],),
        ).fetchone()
    retry_task = json.loads(row["task_json"])
    assert retry_task["status"] == "queued"
    assert "estimated_cost_reserved" not in retry_task
    assert status["reserved_cost"] == pytest.approx(0.0)

    # The next verifier lease gets a fresh reservation based on its own model.
    second_attempt = store.claim_task("verifier-2")
    assert second_attempt is not None
    assert second_attempt["task_id"] == verification["task_id"]
    assert second_attempt["estimated_cost_reserved"] > 0


@pytest.mark.parametrize("final_source_status", ["submitted", "needs_review"])
def test_agent_profile_is_immutable_while_result_awaits_verification(
    tmp_path, final_source_status
):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    producer_token = _register(store, producer)
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, verifier)
    store.create_run(_run(), [_task("task-1")])

    claimed = store.claim_task("producer")
    assert claimed is not None
    result = _result("task-1", producer)
    store.submit_result(result, claimed["lease_token"])

    if final_source_status == "needs_review":
        verification = store.claim_task("verifier")
        assert verification is not None
        review = _review(result, verifier, review_task_id=verification["task_id"])
        review["status"] = "needs_review"
        review["claims"][0]["verdict"] = "insufficient"
        status = store.submit_review(review, verification["lease_token"])
        source = next(item for item in status["tasks"] if item["task_id"] == "task-1")
        assert source["status"] == "needs_review"

    changed = dict(producer)
    changed["model_version"] = "2"
    changed["auth_token"] = producer_token
    with pytest.raises(TaskStoreError, match="pending verification results"):
        store.register_agent(changed, trusted_profile=True)



def test_needs_review_dependency_stays_dormant_and_run_becomes_provisional(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    producer = _agent("producer", "producer-provider", "producer-model")
    verifier = _agent("verifier", "verifier-provider", "verifier-model", role="verifier")
    _register(store, producer)
    _register(store, verifier)
    store.create_run(
        _run(),
        [_task("task-1"), _task("task-2", depends_on=["task-1"])],
    )
    producer_lease = store.claim_task("producer")
    assert producer_lease is not None and producer_lease["task_id"] == "task-1"
    result = _result("task-1", producer)
    store.submit_result(result, producer_lease["lease_token"])
    verification = store.claim_task("verifier")
    assert verification is not None
    review = _review(result, verifier, review_task_id=verification["task_id"])
    review["status"] = "needs_review"
    review["claims"][0]["verdict"] = "insufficient"
    status = store.submit_review(review, verification["lease_token"])
    states = {item["task_id"]: item["status"] for item in status["tasks"]}
    assert states["task-1"] == "needs_review"
    assert states["task-2"] == "queued"
    assert status["run"]["status"] == "provisional"
    assert store.claim_task("producer") is None
    assert store.get_run_status("run-1")["run"]["status"] == "provisional"



def test_retryable_fail_task_keeps_unreported_reserve_across_reclaim(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent1 = _agent("agent-1", "provider-1", "model-1")
    _register(store, agent1)
    store.create_run(_run(strategy="single_agent"), [_task("task-1")])
    claimed = store.claim_task("agent-1")
    assert claimed is not None
    original_reserve = claimed["estimated_cost_reserved"]

    status = store.fail_task(
        "task-1", "agent-1", claimed["lease_token"],
        "worker failed without usage telemetry", retryable=True,
    )
    assert status["tasks"][0]["status"] == "queued"
    assert status["reserved_cost"] == pytest.approx(original_reserve)
    with store._connect() as con:
        row = con.execute(
            "SELECT task_json FROM tasks WHERE task_id='task-1'"
        ).fetchone()
    persisted = json.loads(row["task_json"])
    assert persisted["unreported_cost_reserved"] == pytest.approx(original_reserve)
    assert "estimated_cost_reserved" not in persisted

    # Reclaiming overwrites the per-attempt estimate, but not the prior unknown spend reserve.
    second = store.claim_task("agent-1")
    assert second is not None
    assert second["task_id"] == "task-1"
    assert second["estimated_cost_reserved"] > 0
    status = store.get_run_status("run-1")
    assert status["reserved_cost"] == pytest.approx(
        original_reserve + second["estimated_cost_reserved"]
    )
    assert status["run"]["status"] == "running"


def test_expired_retryable_lease_keeps_unreported_reserve_across_reclaim(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent1 = _agent("agent-1", "provider-1", "model-1")
    _register(store, agent1)
    store.create_run(_run(strategy="single_agent"), [_task("task-1")])
    claimed = store.claim_task("agent-1")
    assert claimed is not None
    original_reserve = claimed["estimated_cost_reserved"]

    with store._transaction() as con:
        con.execute(
            "UPDATE tasks SET lease_expires_at=0 WHERE task_id='task-1'"
        )
        store._reap_expired_leases(
            con, datetime.now(timezone.utc).timestamp() + 1
        )

    status = store.get_run_status("run-1")
    assert status["tasks"][0]["status"] == "queued"
    assert status["reserved_cost"] == pytest.approx(original_reserve)
    with store._connect() as con:
        row = con.execute(
            "SELECT task_json FROM tasks WHERE task_id='task-1'"
        ).fetchone()
    persisted = json.loads(row["task_json"])
    assert persisted["unreported_cost_reserved"] == pytest.approx(original_reserve)
    assert "estimated_cost_reserved" not in persisted

    second = store.claim_task("agent-1")
    assert second is not None
    assert second["task_id"] == "task-1"
    assert second["estimated_cost_reserved"] > 0
    status = store.get_run_status("run-1")
    assert status["reserved_cost"] == pytest.approx(
        original_reserve + second["estimated_cost_reserved"]
    )



def test_unreported_retry_spend_counts_against_task_budget(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent = _agent(
        "agent-1", "provider", "model",
        input_cost=100.0, cached_cost=0.0, output_cost=0.0,
    )
    for key in (
        "verification_cost_per_task",
        "expected_retry_cost_per_task",
        "expected_escalation_cost_per_task",
        "orchestration_cost_per_task",
    ):
        agent["cost_profile"][key] = 0.0
    _register(store, agent)
    task = _task("task-1", estimate=1_000_000)
    task["input"]["estimated_output_tokens"] = 0
    task["input"]["estimated_cached_input_tokens"] = 0
    task["cost_budget"]["max_total"] = 150.0
    store.create_run(_run(max_total=300.0, strategy="single_agent"), [task])

    first = store.claim_task("agent-1")
    assert first is not None
    assert first["estimated_cost_reserved"] == pytest.approx(100.0)
    failed = store.fail_task(
        "task-1", "agent-1", first["lease_token"],
        "worker terminated without usage telemetry", retryable=True,
    )
    assert failed["tasks"][0]["status"] == "queued"

    # A second $100 estimate plus the first attempt's unreported $100 reserve
    # would exceed the task-level $150 ceiling even though the run cap is $300.
    assert store.claim_task("agent-1") is None
    status = store.get_run_status("run-1")
    assert status["tasks"][0]["status"] == "failed"
    with store._connect() as con:
        row = con.execute(
            "SELECT task_json FROM tasks WHERE task_id='task-1'"
        ).fetchone()
    assert json.loads(row["task_json"])["last_failure"] == "task_cost_budget_exceeded"
