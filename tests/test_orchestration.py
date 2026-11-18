from __future__ import annotations

import math

import pytest

from graphify.orchestration import (
    OrchestrationValidationError,
    compute_claim_metrics,
    estimate_end_to_end_cost,
    quality_profile_qualifies,
    rank_qualified_agents,
    result_meets_quality_gate,
    validate_agent_profile,
    validate_result_envelope,
    validate_review_envelope,
    validate_run_envelope,
    validate_task_envelope,
    validate_task_graph,
)


STAMP = "2026-11-14T00:00:00Z"


def _quality_profile(
    *,
    role: str = "researcher",
    domain: str = "technical",
    accuracy: float = 0.995,
    hallucination: float = 0.005,
) -> dict:
    return {
        "role": role,
        "domain": domain,
        "benchmark_id": "technical-claims-v1",
        "evaluation_set_hash": "sha256:eval-set",
        "evaluator_version": "human-adjudication-v1",
        "sample_size": 500,
        "confidence_level": 0.95,
        "accuracy_lower_bound": accuracy,
        "hallucination_upper_bound": hallucination,
        "evaluated_at": STAMP,
    }


def _cost_profile(
    *,
    input_cost: float = 0.2,
    cached_cost: float = 0.02,
    output_cost: float = 0.5,
    verification: float = 0.03,
    retry: float = 0.04,
    escalation: float = 0.05,
    orchestration: float = 0.01,
) -> dict:
    return {
        "currency": "USD",
        "input_cost_per_million_tokens": input_cost,
        "cached_input_cost_per_million_tokens": cached_cost,
        "output_cost_per_million_tokens": output_cost,
        "verification_cost_per_task": verification,
        "expected_retry_cost_per_task": retry,
        "expected_escalation_cost_per_task": escalation,
        "orchestration_cost_per_task": orchestration,
        "pricing_source": "test-price-sheet-v1",
        "effective_at": STAMP,
    }


def _agent(
    agent_id: str,
    *,
    input_cost: float,
    cached_cost: float,
    output_cost: float,
    accuracy: float = 0.995,
    hallucination: float = 0.005,
    status: str = "active",
    profile_role: str = "researcher",
    provider: str = "test-provider",
    model: str | None = None,
    profile_domain: str = "technical",
) -> dict:
    return {
        "schema_version": 1,
        "agent_id": agent_id,
        "provider": provider,
        "model": model or agent_id,
        "model_version": "1",
        "protocol": "mcp",
        "capabilities": ["research"],
        "max_concurrency": 2,
        "status": status,
        "allowed_data_scopes": ["project:demo"],
        "cost_profile": _cost_profile(
            input_cost=input_cost,
            cached_cost=cached_cost,
            output_cost=output_cost,
            verification=0.02,
            retry=0.02,
            escalation=0.02,
            orchestration=0.01,
        ),
        "quality_profiles": [_quality_profile(
            role=profile_role,
            domain=profile_domain,
            accuracy=accuracy,
            hallucination=hallucination,
        )],
        "registered_at": STAMP,
        "updated_at": STAMP,
    }


def _task(task_id: str, depends_on: list[str] | None = None) -> dict:
    return {
        "schema_version": 1,
        "task_id": task_id,
        "run_id": "run-1",
        "task_type": "research",
        "role": "researcher",
        "domain": "technical",
        "objective": "Find evidence for a factual claim",
        "input": {"question": "What does the API guarantee?"},
        "data_scopes": ["project:demo"],
        "context_refs": [],
        "depends_on": depends_on or [],
        "required_capabilities": ["research"],
        "output_schema": {"type": "object"},
        "acceptance_criteria": ["Every material claim has traceable evidence"],
        "attempt": 0,
        "max_attempts": 2,
        "status": "queued",
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _evidence() -> dict:
    return {
        "source_id": "source-1",
        "source_type": "repository_file",
        "uri": "https://example.invalid/source",
        "location": "docs/api.md:L10-L12",
        "excerpt": "The API guarantees stable task identifiers.",
        "content_hash": "sha256:source",
    }


def _result() -> dict:
    return {
        "schema_version": 1,
        "result_id": "result-1",
        "run_id": "run-1",
        "task_id": "task-1",
        "attempt": 1,
        "agent": {
            "agent_id": "agent-1",
            "provider": "test-provider",
            "model": "test-model",
            "model_version": "1",
        },
        "status": "submitted",
        "output": {"answer": "The API guarantees stable task identifiers."},
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 150,
            "cached_input_tokens": 0,
            "direct_cost": 0.01,
            "currency": "USD",
            "pricing_source": "test-price-sheet-v1",
        },
        "claims": [{
            "claim_id": "claim-1",
            "statement": "The API guarantees stable task identifiers.",
            "claim_type": "factual",
            "material": True,
            "evidence": [_evidence()],
        }],
        "evidence": [_evidence()],
        "uncertainties": [],
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cached_input_tokens": 0,
            "direct_cost": 0.01,
            "currency": "USD",
            "pricing_source": "test-price-sheet-v1",
        },
        "created_at": STAMP,
    }


def _review(*, verdict: str = "supported", status: str = "accepted") -> dict:
    return {
        "schema_version": 1,
        "review_id": "review-1",
        "run_id": "run-1",
        "task_id": "task-1",
        "result_id": "result-1",
        "review_task_id": "verification::result-1",
        "reviewer": {
            "agent_id": "independent-reviewer",
            "provider": "different-provider",
            "model": "independent-model",
            "model_version": "1",
        },
        "status": status,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cached_input_tokens": 0,
            "direct_cost": 0.01,
            "currency": "USD",
            "pricing_source": "test-price-sheet-v1",
        },
        "claims": [{
            "claim_id": "claim-1",
            "verdict": verdict,
            "evidence": [_evidence()] if verdict == "supported" else [],
            "notes": "Checked against the cited source.",
        }],
        "created_at": STAMP,
    }


def test_run_envelope_requires_strict_quality_targets_and_cost_rule():
    run = {
        "schema_version": 1,
        "run_id": "run-1",
        "request": "Research and verify the API behaviour",
        "status": "queued",
        "execution_policy": {
            "strategy": "single_with_review",
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
            "max_total": 5.0,
            "optimization_rule": "lowest_total_cost_among_qualified",
        },
        "created_at": STAMP,
        "updated_at": STAMP,
        "deadline_at": None,
    }
    assert validate_run_envelope(run) is run

    bad_accuracy = {**run, "quality_policy": {**run["quality_policy"], "accuracy_target": 0.99}}
    with pytest.raises(OrchestrationValidationError, match="strictly greater"):
        validate_run_envelope(bad_accuracy)

    bad_hallucination = {
        **run,
        "quality_policy": {**run["quality_policy"], "hallucination_max": 0.01},
    }
    with pytest.raises(OrchestrationValidationError, match="strictly less"):
        validate_run_envelope(bad_hallucination)



def test_execution_strategy_defaults_to_single_session_and_only_parallelizes_disjoint_work():
    from graphify.orchestration import choose_execution_strategy

    sequential = choose_execution_strategy(
        task_type="implementation",
        independent_workstreams=3,
        has_dependencies=True,
        file_write_sets_disjoint=True,
        estimated_single_cost=1.0,
        estimated_parallel_total_cost=0.5,
    )
    assert sequential["strategy"] == "single_agent"

    single_file = choose_execution_strategy(
        task_type="implementation",
        independent_workstreams=1,
        file_write_sets_disjoint=True,
        estimated_single_cost=1.0,
        estimated_parallel_total_cost=0.5,
    )
    assert single_file["strategy"] == "single_agent"

    independent = choose_execution_strategy(
        task_type="implementation",
        independent_workstreams=3,
        file_write_sets_disjoint=True,
        estimated_single_cost=1.0,
        estimated_parallel_total_cost=0.9,
        max_parallel_agents=3,
    )
    assert independent["strategy"] == "parallel_independent"
    assert independent["max_parallel_agents"] == 3

    exploration_without_measurement = choose_execution_strategy(
        task_type="research",
        independent_workstreams=3,
        read_only_exploration_needed=True,
        context_pressure_high=True,
    )
    assert exploration_without_measurement["strategy"] == "single_with_review"

    exploration = choose_execution_strategy(
        task_type="research",
        independent_workstreams=3,
        read_only_exploration_needed=True,
        context_pressure_high=True,
        estimated_single_cost=1.0,
        estimated_parallel_total_cost=0.9,
    )
    assert exploration["strategy"] == "read_only_exploration"
    assert exploration["read_only"] is True

    deadline_exploration = choose_execution_strategy(
        task_type="implementation",
        independent_workstreams=3,
        read_only_exploration_needed=True,
        context_pressure_high=True,
        estimated_single_seconds=120.0,
        estimated_parallel_seconds=60.0,
        hard_deadline_requires_parallelism=True,
    )
    assert deadline_exploration["strategy"] == "read_only_exploration"

    one_slot_exploration = choose_execution_strategy(
        task_type="implementation",
        independent_workstreams=3,
        read_only_exploration_needed=True,
        context_pressure_high=True,
        estimated_single_cost=1.0,
        estimated_parallel_total_cost=0.9,
        max_parallel_agents=1,
    )
    assert one_slot_exploration["strategy"] == "single_agent"


def test_execution_plan_rejects_overlapping_parallel_write_sets():
    from graphify.orchestration import validate_execution_plan

    run = {
        "execution_policy": {
            "strategy": "parallel_independent",
            "max_parallel_agents": 2,
            "write_conflicts_checked": True,
        }
    }
    first = _task("task-1")
    second = _task("task-2")
    first["input"]["write_set"] = ["src/a.py"]
    second["input"]["write_set"] = ["src/a.py"]
    with pytest.raises(OrchestrationValidationError, match="overlap"):
        validate_execution_plan(run, [first, second])


@pytest.mark.parametrize(
    "left,right",
    [("src/a.py", "./src/a.py"), ("src/", "src/a.py"), ("src//a.py", "src/a.py")],
)
def test_execution_plan_normalizes_and_checks_parent_write_paths(left, right):
    from graphify.orchestration import validate_execution_plan

    run = {
        "execution_policy": {
            "strategy": "parallel_independent",
            "max_parallel_agents": 2,
            "write_conflicts_checked": True,
        }
    }
    first, second = _task("task-1"), _task("task-2")
    first["input"]["write_set"] = [left]
    second["input"]["write_set"] = [right]
    with pytest.raises(OrchestrationValidationError, match="overlap after path normalization"):
        validate_execution_plan(run, [first, second])


@pytest.mark.parametrize("write_path", ["../secret.txt", "/etc/passwd", "src\\\\file.py"])
def test_execution_plan_rejects_non_project_relative_write_paths(write_path):
    from graphify.orchestration import validate_execution_plan

    run = {
        "execution_policy": {
            "strategy": "parallel_independent",
            "max_parallel_agents": 2,
            "write_conflicts_checked": True,
        }
    }
    first, second = _task("task-1"), _task("task-2")
    first["input"]["write_set"] = [write_path]
    second["input"]["write_set"] = ["other/file.py"]
    with pytest.raises(OrchestrationValidationError, match="project-relative|parent path"):
        validate_execution_plan(run, [first, second])


def test_task_graph_rejects_unknown_dependencies_and_cycles():
    first = _task("task-1")
    second = _task("task-2", ["task-1"])
    validate_task_graph([first, second])

    with pytest.raises(OrchestrationValidationError, match="unknown dependency"):
        validate_task_graph([_task("task-2", ["missing"])])

    with pytest.raises(OrchestrationValidationError, match="cycle"):
        validate_task_graph([_task("task-1", ["task-2"]), _task("task-2", ["task-1"])])


def test_result_and_independent_review_compute_claim_metrics_from_verdicts():
    result = _result()
    review = _review()
    validate_result_envelope(result)
    validate_review_envelope(review, result)

    metrics = compute_claim_metrics(result, review)
    assert metrics == {
        "total_material_claims": 1,
        "supported_claims": 1,
        "contradicted_claims": 0,
        "insufficient_claims": 0,
        "unreviewed_claims": 0,
        "accuracy": 1.0,
        "hallucination_rate": 0.0,
        "evidence_coverage": 1.0,
        "review_complete": True,
    }
    producer = _agent(
        "agent-1", input_cost=0.1, cached_cost=0.01, output_cost=0.2,
        model="test-model",
    )
    verifier = _agent(
        "independent-reviewer",
        input_cost=0.1,
        cached_cost=0.01,
        output_cost=0.2,
        profile_role="verifier",
        provider="different-provider",
        model="independent-model",
    )
    assert result_meets_quality_gate(
        result, review, producer, verifier, task_role="researcher", domain="technical"
    )
    weak_verifier = _agent(
        "independent-reviewer",
        input_cost=0.1,
        cached_cost=0.01,
        output_cost=0.2,
        profile_role="verifier",
        provider="different-provider",
        model="independent-model",
        accuracy=0.99,
    )
    assert not result_meets_quality_gate(
        result, review, producer, weak_verifier,
        task_role="researcher", domain="technical",
    )


def test_review_rejects_same_agent_or_same_model_as_verifier():
    result = _result()
    same_agent = _review()
    same_agent["reviewer"]["agent_id"] = result["agent"]["agent_id"]
    with pytest.raises(OrchestrationValidationError, match="independent"):
        validate_review_envelope(same_agent, result)

    same_model = _review()
    same_model["reviewer"].update({
        "provider": result["agent"]["provider"],
        "model": result["agent"]["model"],
        "model_version": result["agent"]["model_version"],
    })
    with pytest.raises(OrchestrationValidationError, match="independent"):
        validate_review_envelope(same_model, result)


def test_quality_gate_rejects_unverified_or_unsupported_material_claims():
    result = _result()
    insufficient = _review(verdict="insufficient", status="needs_review")
    producer = _agent(
        "agent-1", input_cost=0.1, cached_cost=0.01, output_cost=0.2,
        model="test-model",
    )
    verifier = _agent(
        "independent-reviewer", input_cost=0.1, cached_cost=0.01,
        output_cost=0.2, profile_role="verifier",
        provider="different-provider", model="independent-model",
    )
    assert not result_meets_quality_gate(
        result, insufficient, producer, verifier,
        task_role="researcher", domain="technical",
    )

    unreviewed = _review()
    unreviewed["claims"] = []
    with pytest.raises(OrchestrationValidationError, match="no independent review verdict"):
        validate_review_envelope(unreviewed, result)


def test_quality_profile_requires_strict_bounds_and_independent_evaluation():
    assert quality_profile_qualifies(_quality_profile())
    assert not quality_profile_qualifies(_quality_profile(accuracy=0.99))
    assert not quality_profile_qualifies(_quality_profile(hallucination=0.01))
    assert not quality_profile_qualifies(_quality_profile(accuracy=0.995, hallucination=0.005) | {
        "confidence_level": 0.90
    })


def test_cost_estimate_includes_cached_input_verification_retry_and_escalation():
    estimated = estimate_end_to_end_cost(
        _cost_profile(),
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cached_input_tokens=200_000,
    )
    assert math.isclose(estimated, 0.794)
    with pytest.raises(OrchestrationValidationError, match="cannot exceed"):
        estimate_end_to_end_cost(
            _cost_profile(), input_tokens=10, output_tokens=10, cached_input_tokens=11
        )


def test_router_uses_cheapest_model_only_among_quality_qualified_candidates():
    underqualified = _agent(
        "cheap-but-unqualified",
        input_cost=0.001,
        cached_cost=0.0001,
        output_cost=0.002,
        accuracy=0.98,
        hallucination=0.02,
    )
    qualified_premium = _agent(
        "premium",
        input_cost=0.20,
        cached_cost=0.02,
        output_cost=0.50,
        accuracy=0.997,
        hallucination=0.003,
    )
    qualified_budget = _agent(
        "budget",
        input_cost=0.05,
        cached_cost=0.005,
        output_cost=0.10,
        accuracy=0.9965,
        hallucination=0.0035,
    )
    non_equivalent = _agent(
        "cheaper-but-worse",
        input_cost=0.001,
        cached_cost=0.0001,
        output_cost=0.002,
        accuracy=0.992,
        hallucination=0.008,
    )
    ranked = rank_qualified_agents(
        [qualified_premium, underqualified, qualified_budget, non_equivalent],
        role="researcher",
        domain="technical",
        currency="USD",
        estimated_input_tokens=1_000_000,
        estimated_output_tokens=1_000_000,
        estimated_cached_input_tokens=200_000,
    )
    assert [item["agent_id"] for item in ranked] == ["budget", "premium"]
    assert ranked[0]["estimated_total_cost"] < ranked[1]["estimated_total_cost"]


def test_agent_contract_rejects_an_unknown_or_missing_cost_component():
    agent = _agent("agent-1", input_cost=0.1, cached_cost=0.01, output_cost=0.2)
    validate_agent_profile(agent)
    agent["cost_profile"].pop("expected_retry_cost_per_task")
    with pytest.raises(OrchestrationValidationError, match="expected_retry_cost_per_task"):
        validate_agent_profile(agent)
