from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

from graphify.task_store import TaskStore


class _FakeServer:
    def __init__(self, name, **kwargs):
        self.name = name
        self.tools_handler = None
        self.call_handler = None
        self.resources_handler = None
        self.read_resource_handler = None

    def list_tools(self):
        return lambda fn: setattr(self, "tools_handler", fn)

    def call_tool(self):
        return lambda fn: setattr(self, "call_handler", fn)

    def list_resources(self):
        return lambda fn: setattr(self, "resources_handler", fn)

    def read_resource(self):
        return lambda fn: setattr(self, "read_resource_handler", fn)


def _install_fake_mcp(monkeypatch):
    types_module = ModuleType("mcp.types")
    types_module.AnyUrl = str
    types_module.Tool = lambda **kwargs: SimpleNamespace(**kwargs)
    types_module.Resource = lambda **kwargs: SimpleNamespace(**kwargs)
    types_module.TextContent = lambda **kwargs: SimpleNamespace(**kwargs)
    mcp_module = ModuleType("mcp")
    mcp_module.types = types_module
    server_module = ModuleType("mcp.server")
    server_module.Server = _FakeServer
    monkeypatch.setitem(sys.modules, "mcp", mcp_module)
    monkeypatch.setitem(sys.modules, "mcp.types", types_module)
    monkeypatch.setitem(sys.modules, "mcp.server", server_module)


def _make_run(store):
    stamp = "2026-11-15T00:00:00+00:00"
    run = {
        "schema_version": 1,
        "run_id": "mcp-timeline-run",
        "request": "Exercise MCP timeline tools",
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
        "created_at": stamp,
        "updated_at": stamp,
        "deadline_at": None,
    }
    task = {
        "schema_version": 1,
        "task_id": "mcp-timeline-task",
        "run_id": "mcp-timeline-run",
        "task_type": "implementation",
        "role": "implementer",
        "domain": "technical",
        "objective": "Test MCP timeline access",
        "input": {},
        "data_scopes": ["project:demo"],
        "context_refs": [],
        "depends_on": [],
        "required_capabilities": ["implementation"],
        "output_schema": {"type": "object"},
        "acceptance_criteria": ["Timeline is queryable"],
        "attempt": 0,
        "max_attempts": 1,
        "status": "queued",
        "created_at": stamp,
        "updated_at": stamp,
    }
    store.create_run(run, [task])


def test_mcp_exposes_authenticated_timeline_record_and_query(tmp_path, monkeypatch):
    _install_fake_mcp(monkeypatch)
    monkeypatch.setenv("GRAPHIFY_ORCHESTRATOR_TOKEN", "test-coordinator-token")
    graph_path = tmp_path / "graphify-out" / "graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        json.dumps({"directed": False, "multigraph": False, "graph": {}, "nodes": [], "links": []}),
        encoding="utf-8",
    )
    TaskStore(graph_path.parent / "orchestrator.sqlite3")
    _make_run(TaskStore(graph_path.parent / "orchestrator.sqlite3"))

    from graphify.serve import _build_server

    server = _build_server(str(graph_path))
    tools = asyncio.run(server.tools_handler())
    by_name = {tool.name: tool for tool in tools}
    assert "orchestrator_record_span" in by_name
    assert "orchestrator_list_events" in by_name
    assert "orchestrator_observe_step" in by_name
    assert "orchestrator_redesign_task" in by_name
    assert "coordinator_token" in by_name["orchestrator_list_events"].inputSchema["required"]

    arguments = {
        "run_id": "mcp-timeline-run",
        "task_id": "mcp-timeline-task",
        "name": "mcp-test",
        "started_at": "2026-11-15T09:00:00+09:00",
        "finished_at": "2026-11-15T09:00:01+09:00",
        "outcome": "ok",
        "attributes": {"stage": "review", "test_count": 1},
        "coordinator_token": "test-coordinator-token",
    }
    recorded = asyncio.run(server.call_handler("orchestrator_record_span", arguments))
    span = json.loads(recorded[0].text)
    assert span["duration_ms"] == 1000.0

    events = asyncio.run(server.call_handler(
        "orchestrator_list_events",
        {
            "run_id": "mcp-timeline-run",
            "event_type": "span_completed",
            "limit": 10,
            "include_payload": True,
            "coordinator_token": "test-coordinator-token",
        },
    ))
    timeline = json.loads(events[0].text)
    assert len(timeline) == 1
    assert timeline[0]["payload"]["name"] == "mcp-test"


def test_mcp_timeline_tools_require_coordinator_token(tmp_path, monkeypatch):
    _install_fake_mcp(monkeypatch)
    monkeypatch.setenv("GRAPHIFY_ORCHESTRATOR_TOKEN", "configured-secret")
    graph_path = tmp_path / "graphify-out" / "graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        json.dumps({"directed": False, "multigraph": False, "graph": {}, "nodes": [], "links": []}),
        encoding="utf-8",
    )
    from graphify.serve import _build_server

    server = _build_server(str(graph_path))
    result = asyncio.run(server.call_handler(
        "orchestrator_list_events",
        {"run_id": "some-run", "coordinator_token": "wrong-secret"},
    ))
    assert "Coordinator authentication failed" in result[0].text


def test_mcp_loop_guard_revokes_lease_until_coordinator_redesign(tmp_path, monkeypatch):
    _install_fake_mcp(monkeypatch)
    monkeypatch.setenv("GRAPHIFY_ORCHESTRATOR_TOKEN", "test-coordinator-token")
    graph_path = tmp_path / "graphify-out" / "graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        json.dumps({"directed": False, "multigraph": False, "graph": {}, "nodes": [], "links": []}),
        encoding="utf-8",
    )
    store = TaskStore(graph_path.parent / "orchestrator.sqlite3")
    _make_run(store)
    agent_token = "test-agent-auth-token-with-more-than-24-chars"
    store.register_agent(
        {
            "schema_version": 1,
            "agent_id": "mcp-loop-worker",
            "provider": "test-provider",
            "model": "test-model",
            "model_version": "1",
            "protocol": "mcp",
            "capabilities": ["implementation"],
            "max_concurrency": 1,
            "status": "active",
            "allowed_data_scopes": ["project:demo"],
            "cost_profile": {
                "currency": "USD",
                "input_cost_per_million_tokens": 0.2,
                "cached_input_cost_per_million_tokens": 0.02,
                "output_cost_per_million_tokens": 0.5,
                "verification_cost_per_task": 0.03,
                "expected_retry_cost_per_task": 0.04,
                "expected_escalation_cost_per_task": 0.05,
                "orchestration_cost_per_task": 0.01,
                "pricing_source": "test-prices",
                "effective_at": "2026-11-15T00:00:00Z",
            },
            "quality_profiles": [
                {
                    "role": "implementer",
                    "domain": "technical",
                    "benchmark_id": "test-benchmark",
                    "evaluation_set_hash": "sha256:test-set",
                    "evaluator_version": "test-evaluator",
                    "sample_size": 500,
                    "confidence_level": 0.95,
                    "accuracy_lower_bound": 0.995,
                    "hallucination_upper_bound": 0.005,
                    "evaluated_at": "2026-11-15T00:00:00Z",
                }
            ],
            "registered_at": "2026-11-15T00:00:00Z",
            "updated_at": "2026-11-15T00:00:00Z",
            "auth_token": agent_token,
        },
        trusted_profile=True,
    )
    claimed = store.claim_task("mcp-loop-worker")
    assert claimed is not None

    from graphify.serve import _build_server

    server = _build_server(str(graph_path))
    observed = []
    for _ in range(3):
        response = asyncio.run(server.call_handler(
            "orchestrator_observe_step",
            {
                "task_id": claimed["task_id"],
                "agent_id": "mcp-loop-worker",
                "agent_token": agent_token,
                "lease_token": claimed["lease_token"],
                "action": "repeat the same test command",
                "error": "AssertionError: output unchanged",
                "progress_token": "same-artifact-hash",
            },
        ))
        observed.append(json.loads(response[0].text))
    assert observed[-1]["task_status"] == "needs_redesign"
    assert observed[-1]["may_continue"] is False

    redesigned = asyncio.run(server.call_handler(
        "orchestrator_redesign_task",
        {
            "run_id": "mcp-timeline-run",
            "task_id": claimed["task_id"],
            "strategy": "inspect-test-import-resolution",
            "hypothesis": "the test imports a stale module path",
            "rationale": "the previous command repeated without changing the artifact",
            "coordinator_token": "test-coordinator-token",
        },
    ))
    payload = json.loads(redesigned[0].text)
    assert payload["run"]["status"] == "queued"
    assert payload["tasks"][0]["status"] == "queued"
