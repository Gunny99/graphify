"""Application service for Graphify's durable workflow lifecycle.

Transport handlers (MCP today, CLI/host adapters next) call this facade.
TaskStore remains the transactional repository; policy and persistence are
not duplicated here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from graphify.task_store import TaskStore


class RunController:
    """Single application boundary for every orchestrated Run operation."""

    def __init__(self, store: TaskStore):
        self._store = store

    def create_run(
        self,
        run: Mapping[str, Any],
        tasks: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return self._store.create_run(run, tasks)

    def list_agents(self) -> list[dict[str, Any]]:
        return self._store.list_agents()

    def claim_task(
        self,
        agent_id: str,
        agent_token: str,
        *,
        lease_seconds: int = 300,
    ) -> dict[str, Any] | None:
        self._store.authenticate_agent(agent_id, agent_token)
        return self._store.claim_task(agent_id, lease_seconds=lease_seconds)

    def heartbeat_task(
        self,
        task_id: str,
        agent_id: str,
        agent_token: str,
        lease_token: str,
        *,
        lease_seconds: int = 300,
    ) -> str:
        self._store.authenticate_agent(agent_id, agent_token)
        return self._store.heartbeat_task(
            task_id, agent_id, lease_token, lease_seconds=lease_seconds
        )

    def submit_result(
        self,
        result: Mapping[str, Any],
        agent_token: str,
        lease_token: str,
    ) -> dict[str, Any]:
        agent = result.get("agent")
        if not isinstance(agent, Mapping):
            raise ValueError("result must contain an agent identity")
        agent_id = agent.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError("result.agent.agent_id must be a non-empty string")
        self._store.authenticate_agent(agent_id, agent_token)
        return self._store.submit_result(result, lease_token)

    def get_verification_payload(
        self,
        task_id: str,
        agent_id: str,
        agent_token: str,
        lease_token: str,
    ) -> dict[str, Any]:
        self._store.authenticate_agent(agent_id, agent_token)
        return self._store.get_verification_payload(task_id, agent_id, lease_token)

    def submit_review(
        self,
        review: Mapping[str, Any],
        agent_token: str,
        lease_token: str,
    ) -> dict[str, Any]:
        reviewer = review.get("reviewer")
        if not isinstance(reviewer, Mapping):
            raise ValueError("review must contain a reviewer identity")
        reviewer_id = reviewer.get("agent_id")
        if not isinstance(reviewer_id, str) or not reviewer_id:
            raise ValueError("review.reviewer.agent_id must be a non-empty string")
        self._store.authenticate_agent(reviewer_id, agent_token)
        return self._store.submit_review(review, lease_token)

    def fail_task(
        self,
        task_id: str,
        agent_id: str,
        agent_token: str,
        lease_token: str,
        reason: str,
        *,
        retryable: bool = True,
    ) -> dict[str, Any]:
        self._store.authenticate_agent(agent_id, agent_token)
        return self._store.fail_task(
            task_id, agent_id, lease_token, reason, retryable=retryable
        )

    def get_run_status(self, run_id: str) -> dict[str, Any]:
        return self._store.get_run_status(run_id)

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return self._store.cancel_run(run_id)

    def record_span(
        self,
        run_id: str,
        *,
        name: str,
        started_at: str,
        finished_at: str,
        task_id: str | None = None,
        outcome: str = "ok",
        attributes: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._store.record_span(
            run_id,
            name=name,
            started_at=started_at,
            finished_at=finished_at,
            task_id=task_id,
            outcome=outcome,
            attributes=attributes,
        )

    def list_events(self, run_id: str, **filters: Any) -> list[dict[str, Any]]:
        return self._store.list_events(run_id, **filters)

    def observe_step(
        self,
        task_id: str,
        agent_id: str,
        agent_token: str,
        lease_token: str,
        action: str,
        *,
        error: str | None = None,
        progress_token: str,
    ) -> dict[str, Any]:
        self._store.authenticate_agent(agent_id, agent_token)
        return self._store.observe_workflow_step(
            task_id,
            agent_id,
            lease_token,
            action,
            error=error,
            progress_token=progress_token,
        )

    def redesign_task(
        self,
        run_id: str,
        task_id: str,
        *,
        strategy: str,
        hypothesis: str,
        rationale: str,
    ) -> dict[str, Any]:
        return self._store.redesign_task(
            run_id,
            task_id,
            strategy=strategy,
            hypothesis=hypothesis,
            rationale=rationale,
        )
