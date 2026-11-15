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
