from __future__ import annotations

from datetime import datetime, timezone
import math
import pytest

from graphify.task_store import (
    TaskLeaseError,
    TaskStore,
    TaskStoreError,
)
from graphify.orchestration import OrchestrationValidationError


STAMP = "2026-11-14T00:00:00Z"


def _quality(
    role: str = "researcher",
    *,
    domain: str = "technical",
    accuracy: float = 0.995,
    hallucination: float = 0.005,
):
    return {
        "role": role,
        "domain": domain,
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



def test_result_domain_must_match_task_domain(tmp_path):
    store = TaskStore(tmp_path / "orchestrator.sqlite3")
    agent = _agent("agent-1", "provider", "model")
    agent["quality_profiles"].append(_quality(domain="ziwei_saju"))
    _register(store, agent)
    task = _task("ziwei-task", domain="ziwei_saju")
    store.create_run(_run(), [task])
    claimed = store.claim_task("agent-1")
    assert claimed is not None

    # A generic result cannot satisfy a task explicitly declared for ziwei_saju.
    result = _result("ziwei-task", agent)
    with pytest.raises(TaskStoreError, match="ziwei_saju tasks require"):
        store.submit_result(result, claimed["lease_token"])

    # Nor can a result silently claim a different domain.
    result = _result("ziwei-task", agent)
    result["output"]["domain"] = "technical"
    with pytest.raises(TaskStoreError, match="result domain"):
        store.submit_result(result, claimed["lease_token"])
