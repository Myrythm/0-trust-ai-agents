"""Tests for zta.policy — YAML rule engine with deny-by-default decisions."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from zta.errors import PolicyError, ZTAError
from zta.policy import Decision, Policy


def write_policy(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(dedent(body).lstrip())
    return p


def test_load_returns_policy(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: x
            decision: allow
    """,
    )
    pol = Policy.load(p)
    assert isinstance(pol, Policy)


def test_load_missing_file_raises_policy_error(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        Policy.load(tmp_path / "nope.yaml")


def test_load_invalid_yaml_raises_policy_error(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("rules: [unclosed")
    with pytest.raises(PolicyError):
        Policy.load(p)


def test_load_rule_without_tool_raises(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - decision: allow
    """,
    )
    with pytest.raises(PolicyError):
        Policy.load(p)


def test_load_rule_with_bad_decision_raises(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: x
            decision: maybe
    """,
    )
    with pytest.raises(PolicyError):
        Policy.load(p)


def test_policy_error_is_zta_error() -> None:
    assert issubclass(PolicyError, ZTAError)


def test_default_deny_when_no_rules_match(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: other
            decision: allow
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="ghost", args={}) is Decision.DENY


def test_default_field_deny_explicit(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        default: deny
        rules: []
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="x", args={}) is Decision.DENY


def test_default_field_allow_silently_becomes_deny(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        default: allow
        rules: []
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="x", args={}) is Decision.DENY


def test_allow_rule_matches(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: db_query
            decision: allow
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="db_query", args={}) is Decision.ALLOW


def test_deny_rule_with_reason(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: db_write
            decision: deny
            reason: "db_write is disabled for analyst-bot"
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="db_write", args={}) is Decision.DENY
    assert "db_write is disabled" in pol.reason()


def test_first_match_wins(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: db_query
            decision: deny
            reason: "first match"
          - tool: db_query
            decision: allow
            reason: "second match (should not win)"
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="db_query", args={}) is Decision.DENY
    assert "first match" in pol.reason()


def test_rule_without_when_matches_all_calls_to_tool(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: db_query
            decision: deny
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="db_query", args={"sql": "SELECT 1"}) is Decision.DENY
    assert pol.decide(agent_id="a", tool="db_query", args={"sql": "DROP TABLE x"}) is Decision.DENY


def test_when_expression_evaluates_args(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: db_query
            when: "args['sql'].strip().lower().startswith('select')"
            decision: allow
            reason: "SELECT is allowed"
          - tool: db_query
            decision: deny
            reason: "non-SELECT on db_query"
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="db_query", args={"sql": "SELECT 1"}) is Decision.ALLOW
    assert pol.decide(agent_id="a", tool="db_query", args={"sql": "DROP TABLE x"}) is Decision.DENY


def test_when_expression_error_skips_rule(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: db_query
            when: "args['sql'].startswith('select')"
            decision: allow
          - tool: db_query
            decision: deny
            reason: "fallback deny"
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="db_query", args={}) is Decision.DENY
    assert "fallback deny" in pol.reason()


def test_when_expression_cannot_use_builtins(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: x
            when: "__import__('os').system('echo PWNED')"
            decision: allow
          - tool: x
            decision: deny
            reason: "fallback"
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="x", args={}) is Decision.DENY


def test_agent_specific_policy_only_applies_to_named_agent(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        agent: analyst-bot
        rules:
          - tool: x
            decision: allow
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="analyst-bot", tool="x", args={}) is Decision.ALLOW
    assert pol.decide(agent_id="other-bot", tool="x", args={}) is Decision.DENY


def test_policy_without_agent_applies_to_all(tmp_path: Path) -> None:
    p = write_policy(
        tmp_path,
        """
        rules:
          - tool: x
            decision: allow
    """,
    )
    pol = Policy.load(p)
    assert pol.decide(agent_id="a", tool="x", args={}) is Decision.ALLOW
    assert pol.decide(agent_id="b", tool="x", args={}) is Decision.ALLOW
