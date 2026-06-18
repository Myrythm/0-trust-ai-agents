"""Policy engine: YAML rule matching with deny-by-default decisions.

A `Policy` is loaded from a YAML file and answers `decide(...)` calls.
Rules are evaluated in order; the first whose `tool` matches the call
and whose optional `when` expression returns truthy is the winner. No
match → default deny.

`when` is a restricted Python expression evaluated with
`eval(expr, {"__builtins__": {}}, {"args": args})` — builtins are
stripped, and the only namespace is the `args` dict passed to
`decide`. An expression that raises is treated as "does not match"
and the next rule is tried.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from zta.errors import PolicyError

_log = logging.getLogger(__name__)

_DEFAULT_REASON = "no rule matched; default deny"


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    PENDING_APPROVAL = "pending_approval"


@dataclass
class _Rule:
    tool: str
    decision: Decision
    when: str | None = None
    reason: str | None = None
    agent: str | None = None


@dataclass
class Policy:
    """A loaded policy. Holds parsed rules and the most recent decide() reason."""

    _rules: list[_Rule] = field(default_factory=list)
    _default: Decision = Decision.DENY
    _last_reason: str = ""

    @classmethod
    def load(cls, path: Path) -> Policy:
        if not path.exists():
            raise PolicyError(f"policy file not found: {path}")
        try:
            raw = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise PolicyError(f"invalid YAML in policy file {path}: {exc}") from exc
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise PolicyError(f"policy file root must be a mapping: {path}")

        agent = raw.get("agent")
        if agent is not None and not isinstance(agent, str):
            raise PolicyError(f"policy 'agent' must be a string: {path}")

        default_raw = raw.get("default", "deny")
        default = cls._parse_decision(default_raw, path)
        if default is Decision.ALLOW:
            _log.warning("policy default=allow coerced to deny (deny-by-default invariant)")
            default = Decision.DENY

        rules_raw = raw.get("rules", []) or []
        if not isinstance(rules_raw, list):
            raise PolicyError(f"policy 'rules' must be a list: {path}")
        rules: list[_Rule] = []
        for idx, r in enumerate(rules_raw):
            if not isinstance(r, dict):
                raise PolicyError(f"rule #{idx} is not a mapping: {path}")
            if "tool" not in r:
                raise PolicyError(f"rule #{idx} missing 'tool': {path}")
            if not isinstance(r["tool"], str):
                raise PolicyError(f"rule #{idx} 'tool' must be a string: {path}")
            when = r.get("when")
            if when is not None and not isinstance(when, str):
                raise PolicyError(f"rule #{idx} 'when' must be a string: {path}")
            decision = cls._parse_decision(r.get("decision", "deny"), path)
            reason = r.get("reason")
            if reason is not None and not isinstance(reason, str):
                raise PolicyError(f"rule #{idx} 'reason' must be a string: {path}")
            rules.append(
                _Rule(
                    tool=r["tool"],
                    decision=decision,
                    when=when,
                    reason=reason,
                    agent=agent,
                )
            )
        return cls(_rules=rules, _default=default)

    @staticmethod
    def _parse_decision(value: Any, path: Path) -> Decision:
        if isinstance(value, Decision):
            return value
        if isinstance(value, str):
            try:
                return Decision(value)
            except ValueError as exc:
                raise PolicyError(
                    f"invalid decision value {value!r} in {path}; "
                    f"must be one of allow|deny|pending_approval"
                ) from exc
        raise PolicyError(f"decision must be a string, got {type(value).__name__} in {path}")

    def decide(self, *, agent_id: str, tool: str, args: dict[str, Any]) -> Decision:
        for rule in self._rules:
            if rule.agent is not None and rule.agent != agent_id:
                continue
            if rule.tool != tool:
                continue
            if rule.when is not None and not self._eval_when(rule.when, args):
                continue
            self._last_reason = rule.reason or _rule_default_reason(rule)
            return rule.decision
        self._last_reason = _DEFAULT_REASON
        return self._default

    def reason(self) -> str:
        return self._last_reason

    @staticmethod
    def _eval_when(expr: str, args: dict[str, Any]) -> bool:
        try:
            result = eval(expr, {"__builtins__": {}}, {"args": args})  # noqa: S307
        except Exception as exc:
            _log.warning("policy 'when' expression failed (skipping rule): %s", exc)
            return False
        return bool(result)


def _rule_default_reason(rule: _Rule) -> str:
    if rule.decision is Decision.ALLOW:
        return f"allowed by rule for tool={rule.tool!r}"
    if rule.decision is Decision.DENY:
        return f"denied by rule for tool={rule.tool!r}"
    return f"pending approval by rule for tool={rule.tool!r}"
