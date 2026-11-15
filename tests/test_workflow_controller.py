from __future__ import annotations

from unittest.mock import Mock

import pytest

from graphify.workflow import RunController


def test_controller_is_the_single_authenticated_claim_boundary():
    store = Mock()
    store.claim_task.return_value = {"task_id": "task-1"}
    controller = RunController(store)

    result = controller.claim_task("agent-1", "agent-token", lease_seconds=90)

    assert result == {"task_id": "task-1"}
    store.authenticate_agent.assert_called_once_with("agent-1", "agent-token")
    store.claim_task.assert_called_once_with("agent-1", lease_seconds=90)


def test_controller_authenticates_the_result_producer_not_a_caller_supplied_id():
    store = Mock()
    store.submit_result.return_value = {"run": {"status": "awaiting_review"}}
    controller = RunController(store)
    result = {
        "agent": {"agent_id": "producer-7"},
        "result_id": "result-1",
    }

    response = controller.submit_result(result, "producer-token", "lease-token")

    assert response["run"]["status"] == "awaiting_review"
    store.authenticate_agent.assert_called_once_with("producer-7", "producer-token")
    store.submit_result.assert_called_once_with(result, "lease-token")


def test_controller_refuses_result_without_bound_agent_identity():
    store = Mock()
    controller = RunController(store)

    with pytest.raises(ValueError, match="agent identity"):
        controller.submit_result({"result_id": "result-1"}, "token", "lease")

    store.authenticate_agent.assert_not_called()
    store.submit_result.assert_not_called()


def test_controller_authenticates_reviewer_identity_before_review_submission():
    store = Mock()
    store.submit_review.return_value = {"run": {"status": "accepted"}}
    controller = RunController(store)
    review = {"reviewer": {"agent_id": "reviewer-9"}, "review_id": "review-1"}

    response = controller.submit_review(review, "reviewer-token", "review-lease")

    assert response["run"]["status"] == "accepted"
    store.authenticate_agent.assert_called_once_with("reviewer-9", "reviewer-token")
    store.submit_review.assert_called_once_with(review, "review-lease")



def test_controller_uses_trusted_operator_registration_boundary():
    store = Mock()
    store.register_agent.return_value = {"agent_id": "worker-1"}
    controller = RunController(store)
    profile = {"agent_id": "worker-1", "auth_token": "one-time-secret"}

    result = controller.register_agent(profile)

    assert result == {"agent_id": "worker-1"}
    store.register_agent.assert_called_once_with(profile, trusted_profile=True)
