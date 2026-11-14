from pathlib import Path

import pytest

from graphify.cli import _parse_agent_register_args


@pytest.mark.parametrize(
    ("arguments", "expected_profile", "expected_graph"),
    [
        (
            ["--graph", "custom/graph.json", "agent-profile-template.json"],
            "agent-profile-template.json",
            "custom/graph.json",
        ),
        (
            ["agent-profile-template.json", "--graph", "custom/graph.json"],
            "agent-profile-template.json",
            "custom/graph.json",
        ),
        (
            ["--graph=custom/graph.json", "agent-profile-template.json"],
            "agent-profile-template.json",
            "custom/graph.json",
        ),
    ],
)
def test_agent_register_parses_graph_option_before_or_after_profile(
    arguments, expected_profile, expected_graph
):
    profile, graph = _parse_agent_register_args(arguments)
    assert profile == expected_profile
    assert graph == Path(expected_graph)


def test_agent_register_rejects_missing_graph_value():
    with pytest.raises(ValueError, match="--graph requires a path"):
        _parse_agent_register_args(["--graph"])
