"""Versioned contracts and local quality/cost policy for agent orchestration.

This module is deliberately provider-neutral and uses only the Python standard
library. It can be used by MCP handlers, host adapters, tests, and offline tools
without starting an agent or making a model/API call.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import math
import re
from typing import Any


SCHEMA_VERSION = 1

RUN_STATUSES = frozenset({
    "queued", "running", "awaiting_review", "accepted", "provisional",
    "failed", "cancelled",
})
TASK_TYPES = frozenset({
    "research", "analysis", "implementation", "verification", "integration",
})
TASK_STATUSES = frozenset({
    "queued", "leased", "submitted", "needs_review", "accepted", "rejected",
    "failed", "blocked", "cancelled",
})
AGENT_STATUSES = frozenset({"active", "paused", "disabled"})
RESULT_STATUSES = frozenset({"submitted", "failed"})
CLAIM_TYPES = frozenset({"factual", "inference", "recommendation", "opinion"})
REVIEW_VERDICTS = frozenset({"supported", "contradicted", "insufficient"})
REVIEW_STATUSES = frozenset({"accepted", "provisional", "needs_review", "rejected"})
EXECUTION_STRATEGIES = frozenset({
    "single_agent",
    "single_with_review",
    "read_only_exploration",
    "parallel_independent",
})


class OrchestrationValidationError(ValueError):
    """Raised when an orchestration contract is malformed or inconsistent."""


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OrchestrationValidationError(f"{path} must be an object")
    return value


def _string(value: Any, path: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise OrchestrationValidationError(f"{path} must be a non-empty string")
    return value


def _strings(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise OrchestrationValidationError(f"{path} must be a list of strings")
    result = [_string(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if len(result) != len(set(result)):
        raise OrchestrationValidationError(f"{path} must not contain duplicates")
    return result


def _objects(value: Any, path: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise OrchestrationValidationError(f"{path} must be a list")
    return [_object(item, f"{path}[{index}]") for index, item in enumerate(value)]


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise OrchestrationValidationError(f"{path} must be an integer >= {minimum}")
    return value


def _number(value: Any, path: str, *, minimum: float = 0.0, maximum: float | None = None) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise OrchestrationValidationError(f"{path} must be a number")
    number = float(value)
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        bound = f" between {minimum} and {maximum}" if maximum is not None else f" >= {minimum}"
        raise OrchestrationValidationError(f"{path} must be finite and{bound}")
    return number


def _timestamp(value: Any, path: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    stamp = _string(value, path)
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OrchestrationValidationError(f"{path} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise OrchestrationValidationError(f"{path} must include a timezone")


def _schema_version(payload: Mapping[str, Any], path: str) -> None:
    version = _integer(payload.get("schema_version"), f"{path}.schema_version", minimum=1)
    if version != SCHEMA_VERSION:
        raise OrchestrationValidationError(
            f"{path}.schema_version {version} is unsupported; expected {SCHEMA_VERSION}"
        )


def _validate_evidence_ref(value: Any, path: str) -> Mapping[str, Any]:
    evidence = _object(value, path)
    _string(evidence.get("source_id"), f"{path}.source_id")
    _string(evidence.get("source_type"), f"{path}.source_type")
    locator = any(
        isinstance(evidence.get(key), str) and evidence[key].strip()
        for key in ("uri", "location", "content_hash")
    )
    if not locator:
        raise OrchestrationValidationError(
            f"{path} must include at least one of uri, location, or content_hash"
        )
    for key in ("uri", "location", "excerpt", "content_hash"):
        if key in evidence and evidence[key] is not None:
            _string(evidence[key], f"{path}.{key}", allow_empty=(key == "excerpt"))
    return evidence


def _validate_cost_profile(value: Any, path: str) -> Mapping[str, Any]:
    profile = _object(value, path)
    _string(profile.get("currency"), f"{path}.currency")
    for key in (
        "input_cost_per_million_tokens",
        "cached_input_cost_per_million_tokens",
        "output_cost_per_million_tokens",
        "verification_cost_per_task",
        "expected_retry_cost_per_task",
        "expected_escalation_cost_per_task",
        "orchestration_cost_per_task",
    ):
        _number(profile.get(key), f"{path}.{key}")
    _string(profile.get("pricing_source"), f"{path}.pricing_source")
    _timestamp(profile.get("effective_at"), f"{path}.effective_at")
    return profile


def _validate_quality_profile(value: Any, path: str) -> Mapping[str, Any]:
    profile = _object(value, path)
    for key in ("role", "domain", "benchmark_id", "evaluation_set_hash", "evaluator_version"):
        _string(profile.get(key), f"{path}.{key}")
    _integer(profile.get("sample_size"), f"{path}.sample_size", minimum=1)
    _number(profile.get("confidence_level"), f"{path}.confidence_level", minimum=0.0, maximum=1.0)
    _number(profile.get("accuracy_lower_bound"), f"{path}.accuracy_lower_bound", minimum=0.0, maximum=1.0)
    _number(profile.get("hallucination_upper_bound"), f"{path}.hallucination_upper_bound", minimum=0.0, maximum=1.0)
    _timestamp(profile.get("evaluated_at"), f"{path}.evaluated_at")
    return profile



def choose_execution_strategy(
    *,
    task_type: str,
    independent_workstreams: int = 1,
    has_dependencies: bool = False,
    shared_state_required: bool = False,
    file_write_sets_disjoint: bool = False,
    read_only_exploration_needed: bool = False,
    context_pressure_high: bool = False,
    requires_independent_review: bool = False,
    estimated_single_cost: float | None = None,
    estimated_parallel_total_cost: float | None = None,
    estimated_single_seconds: float | None = None,
    estimated_parallel_seconds: float | None = None,
    hard_deadline_requires_parallelism: bool = False,
    max_parallel_agents: int = 3,
) -> dict[str, Any]:
    """Choose the least-complex strategy; single-session execution is the default."""
    _string(task_type, "task_type")
    workstreams = _integer(independent_workstreams, "independent_workstreams", minimum=1)
    max_workers = _integer(max_parallel_agents, "max_parallel_agents", minimum=1)
    if max_workers > 3:
        raise OrchestrationValidationError("max_parallel_agents cannot exceed 3")
    single_cost = (
        _number(estimated_single_cost, "estimated_single_cost")
        if estimated_single_cost is not None else None
    )
    parallel_cost = (
        _number(estimated_parallel_total_cost, "estimated_parallel_total_cost")
        if estimated_parallel_total_cost is not None else None
    )
    single_seconds = (
        _number(estimated_single_seconds, "estimated_single_seconds")
        if estimated_single_seconds is not None else None
    )
    parallel_seconds = (
        _number(estimated_parallel_seconds, "estimated_parallel_seconds")
        if estimated_parallel_seconds is not None else None
    )

    # Every delegation path needs a measured total-cost or hard-deadline benefit.
    # Context pressure alone does not justify parallel work when its cost/benefit
    # is unknown; fall back to the main session and collect measurements first.
    cost_ok = (
        single_cost is not None
        and parallel_cost is not None
        and parallel_cost <= single_cost
    )
    deadline_ok = (
        hard_deadline_requires_parallelism
        and single_seconds is not None
        and parallel_seconds is not None
        and parallel_seconds < single_seconds
    )

    if (
        read_only_exploration_needed
        and context_pressure_high
        and workstreams >= 2
        and max_workers >= 2
        and (cost_ok or deadline_ok)
    ):
        return {
            "strategy": "read_only_exploration",
            "max_parallel_agents": min(max_workers, workstreams, 3),
            "read_only": True,
            "reason": "Large-scope read-only exploration has a measured cost or hard-deadline benefit.",
        }

    if (
        workstreams >= 2
        and not has_dependencies
        and not shared_state_required
        and file_write_sets_disjoint
        and max_workers >= 2
    ):
        if cost_ok or deadline_ok:
            return {
                "strategy": "parallel_independent",
                "max_parallel_agents": min(max_workers, workstreams, 3),
                "read_only": False,
                "write_conflicts_checked": True,
                "reason": (
                    "Independent workstreams have disjoint write sets and "
                    "parallelism has a measured cost or deadline benefit."
                ),
            }

    # Research and analysis usually produce material factual claims; preserve
    # one main work session and add only the independent evidence-review stage.
    if task_type in {"research", "analysis"}:
        requires_independent_review = True

    if requires_independent_review:
        return {
            "strategy": "single_with_review",
            "max_parallel_agents": 1,
            "read_only": False,
            "reason": "Keep implementation in one session and invoke one independent reviewer after completion.",
        }

    return {
        "strategy": "single_agent",
        "max_parallel_agents": 1,
        "read_only": False,
        "reason": (
            "Default to one session for sequential, coupled, small, or non-profitable parallel work."
        ),
    }


def validate_run_envelope(value: Any) -> Mapping[str, Any]:
    """Validate a run contract, including the non-negotiable quality/cost policy."""
    run = _object(value, "run")
    _schema_version(run, "run")
    for key in ("run_id", "request"):
        _string(run.get(key), f"run.{key}")
    if run.get("status") not in RUN_STATUSES:
        raise OrchestrationValidationError(f"run.status must be one of {sorted(RUN_STATUSES)}")
    quality = _object(run.get("quality_policy"), "run.quality_policy")
    accuracy_target = _number(quality.get("accuracy_target"), "run.quality_policy.accuracy_target", minimum=0.0, maximum=1.0)
    hallucination_max = _number(quality.get("hallucination_max"), "run.quality_policy.hallucination_max", minimum=0.0, maximum=1.0)
    confidence_level = _number(quality.get("confidence_level"), "run.quality_policy.confidence_level", minimum=0.0, maximum=1.0)
    if accuracy_target <= 0.99:
        raise OrchestrationValidationError("accuracy_target must be strictly greater than 0.99")
    if hallucination_max >= 0.01:
        raise OrchestrationValidationError("hallucination_max must be strictly less than 0.01")
    if confidence_level < 0.95:
        raise OrchestrationValidationError("quality_policy.confidence_level must be at least 0.95")
    if quality.get("require_evidence_for_material_claims") is not True:
        raise OrchestrationValidationError("material factual claims must require evidence")
    if quality.get("independent_verification") is not True:
        raise OrchestrationValidationError("independent_verification must be true")
    execution = _object(run.get("execution_policy"), "run.execution_policy")
    strategy = execution.get("strategy")
    if strategy not in EXECUTION_STRATEGIES:
        raise OrchestrationValidationError(
            f"run.execution_policy.strategy must be one of {sorted(EXECUTION_STRATEGIES)}"
        )
    max_parallel = _integer(
        execution.get("max_parallel_agents"),
        "run.execution_policy.max_parallel_agents",
        minimum=1,
    )
    if max_parallel > 3:
        raise OrchestrationValidationError("max_parallel_agents cannot exceed 3")
    if strategy in {"single_agent", "single_with_review"} and max_parallel != 1:
        raise OrchestrationValidationError(
            f"{strategy} must use max_parallel_agents=1 for worker execution"
        )
    if strategy == "parallel_independent" and max_parallel < 2:
        raise OrchestrationValidationError(
            "parallel_independent requires at least two independent workers"
        )
    if strategy == "read_only_exploration" and execution.get("read_only") is not True:
        raise OrchestrationValidationError("read_only_exploration requires read_only=true")
    if strategy == "parallel_independent" and execution.get("write_conflicts_checked") is not True:
        raise OrchestrationValidationError(
            "parallel_independent requires write_conflicts_checked=true"
        )
    cost = _object(run.get("cost_policy"), "run.cost_policy")
    _string(cost.get("currency"), "run.cost_policy.currency")
    _number(cost.get("max_total"), "run.cost_policy.max_total")
    if cost.get("optimization_rule") != "lowest_total_cost_among_qualified":
        raise OrchestrationValidationError(
            "cost_policy.optimization_rule must be lowest_total_cost_among_qualified"
        )
    _timestamp(run.get("created_at"), "run.created_at")
    _timestamp(run.get("updated_at"), "run.updated_at")
    _timestamp(run.get("deadline_at"), "run.deadline_at", optional=True)
    return run


def validate_task_envelope(value: Any) -> Mapping[str, Any]:
    """Validate a versioned, independently claimable task."""
    task = _object(value, "task")
    _schema_version(task, "task")
    for key in ("task_id", "run_id", "role", "domain", "objective"):
        _string(task.get(key), f"task.{key}")
    if task.get("task_type") not in TASK_TYPES:
        raise OrchestrationValidationError(f"task.task_type must be one of {sorted(TASK_TYPES)}")
    task_input = _object(task.get("input"), "task.input")
    data_scopes = _strings(task.get("data_scopes"), "task.data_scopes")
    if not data_scopes:
        raise OrchestrationValidationError("task.data_scopes must contain at least one scope")
    for key in ("excluded_agent_ids", "failed_agent_ids"):
        if key in task_input:
            _strings(task_input[key], f"task.input.{key}")
    for key in (
        "estimated_input_tokens",
        "estimated_output_tokens",
        "estimated_cached_input_tokens",
    ):
        if key in task_input:
            _integer(task_input[key], f"task.input.{key}")
    if (
        task_input.get("estimated_cached_input_tokens", 0)
        > task_input.get("estimated_input_tokens", 0)
    ):
        raise OrchestrationValidationError(
            "estimated_cached_input_tokens cannot exceed estimated_input_tokens"
        )
    _objects(task.get("context_refs"), "task.context_refs")
    dependencies = _strings(task.get("depends_on"), "task.depends_on")
    if task.get("task_id") in dependencies:
        raise OrchestrationValidationError("task cannot depend on itself")
    _strings(task.get("required_capabilities"), "task.required_capabilities")
    _object(task.get("output_schema"), "task.output_schema")
    _strings(task.get("acceptance_criteria"), "task.acceptance_criteria")
    attempt = _integer(task.get("attempt"), "task.attempt")
    max_attempts = _integer(task.get("max_attempts"), "task.max_attempts", minimum=1)
    if attempt > max_attempts:
        raise OrchestrationValidationError("task.attempt cannot exceed task.max_attempts")
    if task.get("status") not in TASK_STATUSES:
        raise OrchestrationValidationError(f"task.status must be one of {sorted(TASK_STATUSES)}")
    if "priority" in task:
        _integer(task["priority"], "task.priority")
    for key in ("parent_task_id", "quality_policy_ref"):
        if key in task and task[key] is not None:
            _string(task[key], f"task.{key}")
    if task.get("cost_budget") is not None:
        budget = _object(task["cost_budget"], "task.cost_budget")
        _string(budget.get("currency"), "task.cost_budget.currency")
        _number(budget.get("max_total"), "task.cost_budget.max_total")
    _timestamp(task.get("created_at"), "task.created_at")
    _timestamp(task.get("updated_at"), "task.updated_at")
    _timestamp(task.get("deadline_at"), "task.deadline_at", optional=True)
    return task


def validate_task_graph(tasks: Sequence[Mapping[str, Any]]) -> None:
    """Reject duplicate IDs, unknown dependencies, and dependency cycles."""
    if isinstance(tasks, (str, bytes)) or not isinstance(tasks, Sequence):
        raise OrchestrationValidationError("tasks must be a sequence of task objects")
    by_id: dict[str, Mapping[str, Any]] = {}
    for item in tasks:
        task = validate_task_envelope(item)
        task_id = str(task["task_id"])
        if task_id in by_id:
            raise OrchestrationValidationError(f"duplicate task_id: {task_id}")
        by_id[task_id] = task
    indegree = {task_id: 0 for task_id in by_id}
    dependents: dict[str, list[str]] = {task_id: [] for task_id in by_id}
    for task_id, task in by_id.items():
        for dependency in task["depends_on"]:
            if dependency not in by_id:
                raise OrchestrationValidationError(
                    f"task {task_id} references unknown dependency {dependency}"
                )
            indegree[task_id] += 1
            dependents[dependency].append(task_id)
    ready = [task_id for task_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for child in dependents[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(by_id):
        raise OrchestrationValidationError("task dependency graph contains a cycle")



def _write_path_parts(value: str, path: str) -> tuple[str, ...]:
    """Normalize a project-relative write path for overlap checks."""
    if value != value.strip() or not value:
        raise OrchestrationValidationError(f"{path} must be a non-empty project-relative path")
    if value.startswith(("/", "~")) or "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise OrchestrationValidationError(f"{path} must be a project-relative POSIX path")
    parts = []
    for part in value.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise OrchestrationValidationError(f"{path} cannot contain a parent path segment")
        parts.append(part)
    if not parts:
        raise OrchestrationValidationError(f"{path} must identify a file or directory")
    return tuple(parts)


def _write_paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    return longer[:len(shorter)] == shorter


def validate_execution_plan(
    run: Mapping[str, Any],
    tasks: Sequence[Mapping[str, Any]],
) -> None:
    """Validate that the declared strategy matches the actual task topology."""
    policy = run["execution_policy"]
    strategy = policy["strategy"]
    max_workers = int(policy["max_parallel_agents"])
    if strategy in {"single_agent", "single_with_review"}:
        if max_workers != 1:
            raise OrchestrationValidationError("single-session strategies require one worker slot")
        main_tasks = [task for task in tasks if not task["depends_on"]]
        if len(main_tasks) != 1:
            raise OrchestrationValidationError(
                f"{strategy} requires exactly one main work task with no dependencies; "
                "all additional tasks must depend on that task graph"
            )
        return

    if not 2 <= len(tasks) <= max_workers:
        raise OrchestrationValidationError(
            f"{strategy} requires 2..{max_workers} tasks"
        )

    if strategy == "read_only_exploration":
        for task in tasks:
            task_input = task["input"]
            if task_input.get("read_only") is not True:
                raise OrchestrationValidationError(
                    "all exploration tasks must declare input.read_only=true"
                )
            if task_input.get("write_set"):
                raise OrchestrationValidationError(
                    "read-only exploration tasks cannot declare write_set"
                )
            if "read_only" not in task["required_capabilities"]:
                raise OrchestrationValidationError(
                    "read-only exploration requires read_only capability"
                )
            if task["depends_on"]:
                raise OrchestrationValidationError(
                    "read-only exploration tasks must be independent"
                )
        return

    if strategy == "parallel_independent":
        seen: list[tuple[str, tuple[str, ...], str]] = []
        for task in tasks:
            task_input = task["input"]
            if task["depends_on"]:
                raise OrchestrationValidationError(
                    "parallel implementation tasks cannot have dependencies"
                )
            if task_input.get("shared_state_required") is True:
                raise OrchestrationValidationError(
                    "parallel implementation tasks cannot share mutable state"
                )
            write_set = _strings(task_input.get("write_set"), f"task {task['task_id']}.input.write_set")
            if not write_set:
                raise OrchestrationValidationError(
                    "parallel implementation tasks require explicit write_set declarations"
                )
            for write_path in write_set:
                parts = _write_path_parts(
                    write_path, f"task {task['task_id']}.input.write_set"
                )
                for prior_task_id, prior_parts, prior_path in seen:
                    if _write_paths_overlap(parts, prior_parts):
                        raise OrchestrationValidationError(
                            "parallel task write sets overlap after path normalization: "
                            f"task {task['task_id']} {write_path!r} conflicts with "
                            f"task {prior_task_id} {prior_path!r}"
                        )
                seen.append((str(task["task_id"]), parts, write_path))
        return

def validate_agent_profile(value: Any) -> Mapping[str, Any]:
    """Validate an agent identity, capability, cost, and evaluation profile."""
    agent = _object(value, "agent")
    _schema_version(agent, "agent")
    for key in ("agent_id", "provider", "model", "model_version", "protocol"):
        _string(agent.get(key), f"agent.{key}")
    _strings(agent.get("capabilities"), "agent.capabilities")
    allowed_scopes = _strings(agent.get("allowed_data_scopes"), "agent.allowed_data_scopes")
    if not allowed_scopes:
        raise OrchestrationValidationError("agent.allowed_data_scopes must contain at least one scope")
    _integer(agent.get("max_concurrency"), "agent.max_concurrency", minimum=1)
    if agent.get("status") not in AGENT_STATUSES:
        raise OrchestrationValidationError(f"agent.status must be one of {sorted(AGENT_STATUSES)}")
    _validate_cost_profile(agent.get("cost_profile"), "agent.cost_profile")
    profiles = _objects(agent.get("quality_profiles"), "agent.quality_profiles")
    seen: set[tuple[str, str]] = set()
    for index, profile in enumerate(profiles):
        _validate_quality_profile(profile, f"agent.quality_profiles[{index}]")
        key = (str(profile["role"]), str(profile["domain"]))
        if key in seen:
            raise OrchestrationValidationError(
                f"agent.quality_profiles contains duplicate role/domain: {key}"
            )
        seen.add(key)
    _timestamp(agent.get("registered_at"), "agent.registered_at")
    _timestamp(agent.get("updated_at"), "agent.updated_at")
    return agent


def validate_result_envelope(value: Any) -> Mapping[str, Any]:
    """Validate one immutable agent submission; claims remain unverified at submission."""
    result = _object(value, "result")
    _schema_version(result, "result")
    for key in ("result_id", "run_id", "task_id"):
        _string(result.get(key), f"result.{key}")
    _integer(result.get("attempt"), "result.attempt", minimum=1)
    agent = _object(result.get("agent"), "result.agent")
    for key in ("agent_id", "provider", "model", "model_version"):
        _string(agent.get(key), f"result.agent.{key}")
    if result.get("status") not in RESULT_STATUSES:
        raise OrchestrationValidationError(f"result.status must be one of {sorted(RESULT_STATUSES)}")
    _object(result.get("output"), "result.output")
    claims = _objects(result.get("claims"), "result.claims")
    claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        path = f"result.claims[{index}]"
        claim_id = _string(claim.get("claim_id"), f"{path}.claim_id")
        if claim_id in claim_ids:
            raise OrchestrationValidationError(f"duplicate claim_id: {claim_id}")
        claim_ids.add(claim_id)
        _string(claim.get("statement"), f"{path}.statement")
        if claim.get("claim_type") not in CLAIM_TYPES:
            raise OrchestrationValidationError(f"{path}.claim_type is invalid")
        if not isinstance(claim.get("material"), bool):
            raise OrchestrationValidationError(f"{path}.material must be a boolean")
        evidence = _objects(claim.get("evidence"), f"{path}.evidence")
        for evidence_index, item in enumerate(evidence):
            _validate_evidence_ref(item, f"{path}.evidence[{evidence_index}]")
    for index, evidence in enumerate(_objects(result.get("evidence"), "result.evidence")):
        _validate_evidence_ref(evidence, f"result.evidence[{index}]")
    _strings(result.get("uncertainties"), "result.uncertainties")
    usage = _object(result.get("usage"), "result.usage")
    for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
        _integer(usage.get(key), f"result.usage.{key}")
    _number(usage.get("direct_cost"), "result.usage.direct_cost")
    _string(usage.get("currency"), "result.usage.currency")
    _string(usage.get("pricing_source"), "result.usage.pricing_source")
    _timestamp(result.get("created_at"), "result.created_at")
    return result


def validate_review_envelope(value: Any, result: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate an independent review and require a verdict for every material claim."""
    validate_result_envelope(result)
    review = _object(value, "review")
    _schema_version(review, "review")
    for key in ("review_id", "run_id", "task_id", "result_id", "review_task_id"):
        _string(review.get(key), f"review.{key}")
    if (
        review["run_id"] != result["run_id"]
        or review["task_id"] != result["task_id"]
        or review["result_id"] != result["result_id"]
    ):
        raise OrchestrationValidationError("review run/task/result IDs must match the submitted result")
    reviewer = _object(review.get("reviewer"), "review.reviewer")
    for key in ("agent_id", "provider", "model", "model_version"):
        _string(reviewer.get(key), f"review.reviewer.{key}")
    producer = result["agent"]
    same_agent = reviewer["agent_id"] == producer["agent_id"]
    same_model = (
        reviewer["model"] == producer["model"]
        and reviewer["model_version"] == producer["model_version"]
    )
    if same_agent or same_model:
        raise OrchestrationValidationError(
            "reviewer must be independent of the producing agent and model"
        )
    if review.get("status") not in REVIEW_STATUSES:
        raise OrchestrationValidationError(f"review.status must be one of {sorted(REVIEW_STATUSES)}")
    submitted = {str(claim["claim_id"]): claim for claim in result["claims"]}
    seen: set[str] = set()
    reviewed = _objects(review.get("claims"), "review.claims")
    for index, claim_review in enumerate(reviewed):
        path = f"review.claims[{index}]"
        claim_id = _string(claim_review.get("claim_id"), f"{path}.claim_id")
        if claim_id not in submitted:
            raise OrchestrationValidationError(f"{path}.claim_id does not exist in the submitted result")
        if claim_id in seen:
            raise OrchestrationValidationError(f"duplicate review for claim_id: {claim_id}")
        seen.add(claim_id)
        if claim_review.get("verdict") not in REVIEW_VERDICTS:
            raise OrchestrationValidationError(f"{path}.verdict is invalid")
        evidence = _objects(claim_review.get("evidence"), f"{path}.evidence")
        for evidence_index, item in enumerate(evidence):
            _validate_evidence_ref(item, f"{path}.evidence[{evidence_index}]")
        if claim_review.get("verdict") == "supported" and not evidence:
            raise OrchestrationValidationError(f"{path}: supported verdict requires verifier evidence")
    for claim_id, claim in submitted.items():
        if claim.get("material") and claim.get("claim_type") in {"factual", "inference"} and claim_id not in seen:
            raise OrchestrationValidationError(f"material claim {claim_id} has no independent review verdict")
    if review.get("status") == "accepted":
        material_ids = {
            claim_id for claim_id, claim in submitted.items()
            if claim.get("material") and claim.get("claim_type") in {"factual", "inference"}
        }
        if any(item["verdict"] != "supported" for item in reviewed if item["claim_id"] in material_ids):
            raise OrchestrationValidationError(
                "an accepted review cannot contain contradicted or insufficient material claims"
            )
    usage = _object(review.get("usage"), "review.usage")
    for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
        _integer(usage.get(key), f"review.usage.{key}")
    _number(usage.get("direct_cost"), "review.usage.direct_cost")
    _string(usage.get("currency"), "review.usage.currency")
    _string(usage.get("pricing_source"), "review.usage.pricing_source")
    _timestamp(review.get("created_at"), "review.created_at")
    return review


def compute_claim_metrics(
    result: Mapping[str, Any],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute claim metrics from review verdicts; never trust agent-supplied percentages."""
    review_by_id = {str(item["claim_id"]): item for item in review["claims"]}
    material = [
        claim for claim in result["claims"]
        if claim["material"] and claim["claim_type"] in {"factual", "inference"}
    ]
    total = len(material)
    counts = {"supported": 0, "contradicted": 0, "insufficient": 0, "unreviewed": 0}
    evidence_count = 0
    for claim in material:
        reviewed = review_by_id.get(str(claim["claim_id"]))
        if reviewed is None:
            counts["unreviewed"] += 1
        else:
            counts[reviewed["verdict"]] += 1
        if claim.get("evidence") or (reviewed and reviewed.get("evidence")):
            evidence_count += 1
    return {
        "total_material_claims": total,
        "supported_claims": counts["supported"],
        "contradicted_claims": counts["contradicted"],
        "insufficient_claims": counts["insufficient"],
        "unreviewed_claims": counts["unreviewed"],
        "accuracy": counts["supported"] / total if total else None,
        "hallucination_rate": (counts["contradicted"] + counts["insufficient"]) / total if total else None,
        "evidence_coverage": evidence_count / total if total else 1.0,
        "review_complete": counts["unreviewed"] == 0,
    }


def quality_profile_qualifies(
    profile: Mapping[str, Any],
    *,
    accuracy_target: float = 0.99,
    hallucination_max: float = 0.01,
    minimum_confidence_level: float = 0.95,
) -> bool:
    """Return True only for independently evaluated profiles meeting strict bounds."""
    _validate_quality_profile(profile, "quality_profile")
    return (
        float(profile["accuracy_lower_bound"]) > accuracy_target
        and float(profile["hallucination_upper_bound"]) < hallucination_max
        and float(profile["confidence_level"]) >= minimum_confidence_level
    )



def result_meets_quality_gate(
    result: Mapping[str, Any],
    review: Mapping[str, Any],
    producer_agent: Mapping[str, Any],
    verifier_agent: Mapping[str, Any],
    *,
    task_role: str,
    domain: str,
    accuracy_target: float = 0.99,
    hallucination_max: float = 0.01,
) -> bool:
    """Gate a result on independent review and qualified producer/verifier agents."""
    validate_result_envelope(result)
    validate_review_envelope(review, result)
    producer = validate_agent_profile(producer_agent)
    verifier = validate_agent_profile(verifier_agent)
    if review.get("status") != "accepted":
        return False

    producer_identity = result["agent"]
    verifier_identity = review["reviewer"]
    for key in ("agent_id", "provider", "model", "model_version"):
        if producer[key] != producer_identity[key]:
            raise OrchestrationValidationError(
                f"producer agent profile does not match result.agent.{key}"
            )
        if verifier[key] != verifier_identity[key]:
            raise OrchestrationValidationError(
                f"verifier agent profile does not match review.reviewer.{key}"
            )
    if (
        producer["agent_id"] == verifier["agent_id"]
        or (
            producer["provider"],
            producer["model"],
            producer["model_version"],
        ) == (
            verifier["provider"],
            verifier["model"],
            verifier["model_version"],
        )
    ):
        return False

    producer_profile = next((
        item for item in producer["quality_profiles"]
        if item["role"] == task_role and item["domain"] == domain
    ), None)
    verifier_profile = next((
        item for item in verifier["quality_profiles"]
        if item["role"] == "verifier" and item["domain"] == domain
    ), None)
    if producer_profile is None or verifier_profile is None:
        return False
    if not quality_profile_qualifies(
        producer_profile,
        accuracy_target=accuracy_target,
        hallucination_max=hallucination_max,
    ):
        return False
    if not quality_profile_qualifies(
        verifier_profile,
        accuracy_target=accuracy_target,
        hallucination_max=hallucination_max,
    ):
        return False
    metrics = compute_claim_metrics(result, review)
    return (
        metrics["review_complete"]
        and metrics["supported_claims"] == metrics["total_material_claims"]
        and metrics["contradicted_claims"] == 0
        and metrics["insufficient_claims"] == 0
        and metrics["evidence_coverage"] == 1.0
        and (
            metrics["accuracy"] is None
            or metrics["accuracy"] > accuracy_target
        )
        and (
            metrics["hallucination_rate"] is None
            or metrics["hallucination_rate"] < hallucination_max
        )
    )

def estimate_end_to_end_cost(
    cost_profile: Mapping[str, Any],
    input_tokens: int,
    output_tokens: int,
    *,
    cached_input_tokens: int = 0,
) -> float:
    """Estimate generation plus verifier/retry/escalation/orchestration cost."""
    _validate_cost_profile(cost_profile, "cost_profile")
    inputs = _integer(input_tokens, "input_tokens")
    outputs = _integer(output_tokens, "output_tokens")
    cached = _integer(cached_input_tokens, "cached_input_tokens")
    if cached > inputs:
        raise OrchestrationValidationError("cached_input_tokens cannot exceed input_tokens")
    uncached = inputs - cached
    generation = (
        uncached * float(cost_profile["input_cost_per_million_tokens"])
        + cached * float(cost_profile["cached_input_cost_per_million_tokens"])
        + outputs * float(cost_profile["output_cost_per_million_tokens"])
    ) / 1_000_000
    return generation + sum(float(cost_profile[key]) for key in (
        "verification_cost_per_task",
        "expected_retry_cost_per_task",
        "expected_escalation_cost_per_task",
        "orchestration_cost_per_task",
    ))


def rank_qualified_agents(
    agents: Sequence[Mapping[str, Any]],
    *,
    role: str,
    domain: str,
    currency: str,
    estimated_input_tokens: int,
    estimated_output_tokens: int,
    estimated_cached_input_tokens: int = 0,
    accuracy_target: float = 0.99,
    hallucination_max: float = 0.01,
    quality_equivalence_tolerance: float = 0.001,
) -> list[dict[str, Any]]:
    """Choose the cheapest model only inside a measured same-quality cohort.

    Candidates must meet the strict run threshold and be evaluated on the same
    benchmark/evaluation set/evaluator version. The chosen candidate must also
    be within the explicit non-inferiority tolerance of the cohort's best
    accuracy lower bound and best hallucination upper bound.
    """
    _string(role, "role")
    _string(domain, "domain")
    _string(currency, "currency")
    tolerance = _number(
        quality_equivalence_tolerance,
        "quality_equivalence_tolerance",
        minimum=0.0,
        maximum=0.01,
    )
    qualified: list[dict[str, Any]] = []
    for value in agents:
        agent = validate_agent_profile(value)
        if agent["status"] != "active":
            continue
        profile = next((
            item for item in agent["quality_profiles"]
            if item["role"] == role and item["domain"] == domain
        ), None)
        if profile is None or not quality_profile_qualifies(
            profile,
            accuracy_target=accuracy_target,
            hallucination_max=hallucination_max,
        ):
            continue
        cost_profile = agent["cost_profile"]
        if cost_profile["currency"] != currency:
            continue
        qualified.append({"agent": agent, "profile": profile, "cost_profile": cost_profile})

    if not qualified:
        return []

    cohorts: dict[tuple[str, str, str, float], list[dict[str, Any]]] = {}
    for item in qualified:
        profile = item["profile"]
        cohort_key = (
            profile["benchmark_id"],
            profile["evaluation_set_hash"],
            profile["evaluator_version"],
            float(profile["confidence_level"]),
        )
        cohorts.setdefault(cohort_key, []).append(item)

    # Cross-benchmark scores are not directly comparable. Use the largest
    # common cohort; if only one qualified model is represented, don't pretend
    # it was compared against models evaluated on a different set.
    cohort = max(
        cohorts.values(),
        key=lambda group: (
            len(group),
            sum(int(item["profile"]["sample_size"]) for item in group),
            max(str(item["profile"]["evaluated_at"]) for item in group),
        ),
    )
    best_accuracy = max(float(item["profile"]["accuracy_lower_bound"]) for item in cohort)
    best_hallucination = min(float(item["profile"]["hallucination_upper_bound"]) for item in cohort)

    ranked: list[dict[str, Any]] = []
    for item in cohort:
        profile = item["profile"]
        if float(profile["accuracy_lower_bound"]) < best_accuracy - tolerance:
            continue
        if float(profile["hallucination_upper_bound"]) > best_hallucination + tolerance:
            continue
        agent = item["agent"]
        total = estimate_end_to_end_cost(
            item["cost_profile"],
            estimated_input_tokens,
            estimated_output_tokens,
            cached_input_tokens=estimated_cached_input_tokens,
        )
        ranked.append({
            "agent_id": agent["agent_id"],
            "provider": agent["provider"],
            "model": agent["model"],
            "quality_profile": profile,
            "estimated_total_cost": total,
            "currency": currency,
        })
    return sorted(ranked, key=lambda item: (item["estimated_total_cost"], item["agent_id"]))
