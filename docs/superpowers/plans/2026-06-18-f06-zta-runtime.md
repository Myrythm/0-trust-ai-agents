# Feature 6: `zta.runtime` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `zta/runtime.py` — the `session()` context manager + `Agent` class. This is the thin API the application uses. Every `agent.tool(name, **args)` call flows through Policy, executes the registered tool, and writes an audit event. `Agent.trace` is populated for UI display.

**Architecture:** `session(...)` loads `Identity`, `Policy`, `Audit`; creates a `ToolRegistry`; yields an `Agent` bound to all four. The user registers tools on `agent.registry`, then calls `agent.tool(name, **args)`. `Agent.tool()` generates a `request_id`, calls `policy.decide`, and routes accordingly. `pending_approval` is treated as deny in MVP (with the reason logged). Trace entries are appended to `agent.trace` for the Jinja UI (F9).

**Tech Stack:** stdlib + already-pinned deps (`pydantic` for TraceEntry optional, but plain dataclass is fine). No new deps.

---

## File Structure

```
zta/runtime.py            # session, Agent, ToolResult, TraceEntry
tests/test_runtime.py     # 16 tests
```

---

## Contract (per spec section 3.5)

```python
@dataclass
class ToolResult:
    ok: bool
    value: Any | None = None
    error: str | None = None

@dataclass
class TraceEntry:
    ts: str
    request_id: str
    tool: str
    args: dict[str, Any]
    decision: str           # "allow" | "deny" | "pending_approval" | "error"
    reason: str
    ok: bool
    error: str | None

@dataclass
class Agent:
    agent_id: str
    policy: Policy
    audit: Audit
    identity: Identity
    registry: ToolRegistry
    trace: list[TraceEntry] = field(default_factory=list)

    def tool(self, name: str, **args: Any) -> ToolResult: ...


@contextmanager
def session(
    *,
    agent: str,
    policy: Path,
    audit: Path,
    key_dir: Path,
) -> Iterator[Agent]: ...
```

**`Agent.tool(name, **args)` flow (locked):**

1. Generate `request_id = uuid.uuid4().hex`
2. `decision = self.policy.decide(agent_id=self.agent_id, tool=name, args=args)`
3. `reason = self.policy.reason()`
4. If `decision is ALLOW`:
   - Look up `name` in `self.registry`
   - If not found: `result = ToolResult(ok=False, error="tool not registered: {name}")`; audit decision `error`
   - Else: try to call; on exception, `result = ToolResult(ok=False, error=str(exc))`; audit decision `error`
   - On success, audit decision `allow`
5. If `decision is DENY`: `result = ToolResult(ok=False, error=reason)`; audit `deny`
6. If `decision is PENDING_APPROVAL`: `result = ToolResult(ok=False, error=reason + " (pending_approval denied in MVP)")`; audit `pending_approval`
7. Append `TraceEntry(...)` to `self.trace`
8. Return `result`

**Resource string for audit:** `f"tool:{name}"` (the tool name is the resource surface for MVP).

**Failure modes:**
- `Identity.load_or_create` may create the key file on first run
- `Policy.load` raises `PolicyError` (F3) → `session()` propagates
- `Audit` constructor creates the file (F4) — never raises
- `Agent.tool` with `name` not in registry → graceful `ToolResult(ok=False, error=...)`, audited as `error`

**Thread-safety:** Not thread-safe. MVP runtime is single-threaded.

---

## Tasks

### Task 1: Write the failing test file

**Files:**
- Create: `tests/test_runtime.py`

- [ ] **Step 1: Create the test file with 16 tests**

```python
"""Tests for zta.runtime — session() context manager + Agent."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from zta.audit import Audit
from zta.errors import ZTAError
from zta.identity import Identity
from zta.policy import Decision, Policy
from zta.runtime import Agent, ToolResult, TraceEntry, session
from zta.tools import ToolRegistry, tool


def write_policy(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(dedent(body).lstrip())
    return p


def write_key_dir(tmp_path: Path) -> Path:
    return tmp_path / "keys"


def test_session_creates_identity(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        assert isinstance(a.identity, Identity)
    assert (write_key_dir(tmp_path) / "bot.pem").is_file()


def test_session_yields_agent_with_agent_id(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        assert isinstance(a, Agent)
        assert a.agent_id == "bot"


def test_session_loads_policy(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        assert isinstance(a.policy, Policy)


def test_session_creates_audit(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    audit_path = tmp_path / "a.jsonl"
    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        assert isinstance(a.audit, Audit)
    assert audit_path.exists()


def test_session_registry_is_empty_by_default(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        assert isinstance(a.registry, ToolRegistry)
        assert a.registry.list() == []


def test_session_uses_existing_key(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    kd = write_key_dir(tmp_path)
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=kd) as a1:
        first_pub = a1.identity.public_key_b64
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=kd) as a2:
        assert a2.identity.public_key_b64 == first_pub


def test_agent_tool_allow_executes_and_audits(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: add
            decision: allow
    """)
    audit_path = tmp_path / "a.jsonl"
    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(lambda a, b: a + b, name="add")
        result = a.tool("add", a=2, b=3)
    assert result.ok is True
    assert result.value == 5
    assert result.error is None
    events = Audit(audit_path).read_all()
    assert len(events) == 1
    assert events[0].decision == "allow"
    assert events[0].action == "tool:add"


def test_agent_tool_deny_does_not_execute_and_audits(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: dangerous
            decision: deny
            reason: "too risky"
    """)
    audit_path = tmp_path / "a.jsonl"

    called = {"n": 0}

    def boom() -> str:
        called["n"] += 1
        return "should not happen"

    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(boom, name="dangerous")
        result = a.tool("dangerous")
    assert result.ok is False
    assert "too risky" in (result.error or "")
    assert called["n"] == 0
    events = Audit(audit_path).read_all()
    assert len(events) == 1
    assert events[0].decision == "deny"


def test_agent_tool_unknown_tool_returns_error_and_audits(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: missing
            decision: allow
    """)
    audit_path = tmp_path / "a.jsonl"
    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        result = a.tool("missing")
    assert result.ok is False
    assert "not registered" in (result.error or "")
    events = Audit(audit_path).read_all()
    assert len(events) == 1
    assert events[0].decision == "error"


def test_agent_tool_pending_approval_denies_in_mvp(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: risky
            decision: pending_approval
            reason: "needs human"
    """)
    audit_path = tmp_path / "a.jsonl"
    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(lambda: "x", name="risky")
        result = a.tool("risky")
    assert result.ok is False
    assert "pending_approval" in (result.error or "")
    events = Audit(audit_path).read_all()
    assert events[0].decision == "pending_approval"


def test_agent_tool_exception_returns_error_and_audits(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: kaboom
            decision: allow
    """)
    audit_path = tmp_path / "a.jsonl"

    def kaboom() -> str:
        raise ValueError("nope")

    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(kaboom, name="kaboom")
        result = a.tool("kaboom")
    assert result.ok is False
    assert "nope" in (result.error or "")
    events = Audit(audit_path).read_all()
    assert events[0].decision == "error"


def test_agent_trace_populated_by_tool_calls(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: t1
            decision: allow
          - tool: t2
            decision: deny
            reason: "no"
    """)
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(lambda: "ok", name="t1")
        a.tool("t1")
        a.tool("t2")
    assert len(a.trace) == 2
    assert a.trace[0].tool == "t1" and a.trace[0].decision == "allow"
    assert a.trace[1].tool == "t2" and a.trace[1].decision == "deny"


def test_agent_tool_assigns_request_id(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, "rules: []")
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        rid_holder = {}
        a.registry.register(lambda: rid_holder.setdefault("rid", "x"), name="x")
        a.tool("x")
    assert "rid" in rid_holder
    assert a.trace[0].request_id
    assert a.trace[0].request_id == rid_holder["rid"]  # same call → same request_id


def test_request_id_propagates_to_audit_event(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: x
            decision: allow
    """)
    audit_path = tmp_path / "a.jsonl"
    with session(agent="bot", policy=pol, audit=audit_path, key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(lambda: None, name="x")
        a.tool("x")
    events = Audit(audit_path).read_all()
    assert events[0].request_id == a.trace[0].request_id


def test_tool_result_shape_on_allow(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: x
            decision: allow
    """)
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        a.registry.register(lambda: 42, name="x")
        r = a.tool("x")
    assert isinstance(r, ToolResult)
    assert r.ok is True
    assert r.value == 42
    assert r.error is None


def test_tool_result_shape_on_deny(tmp_path: Path) -> None:
    pol = write_policy(tmp_path, """
        rules:
          - tool: x
            decision: deny
            reason: "nope"
    """)
    with session(agent="bot", policy=pol, audit=tmp_path / "a.jsonl", key_dir=write_key_dir(tmp_path)) as a:
        r = a.tool("x")
    assert isinstance(r, ToolResult)
    assert r.ok is False
    assert r.value is None
    assert r.error == "nope"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_runtime.py -v`
Expected: collection error (`ModuleNotFoundError: No module named 'zta.runtime'`).

---

### Task 2: Implement `zta/runtime.py`

**Files:**
- Create: `zta/runtime.py`

- [ ] **Step 1: Write the implementation**

```python
"""The thin runtime API: session() + Agent.

`session(agent, policy, audit, key_dir)` loads identity, policy, and
audit, creates an empty tool registry, and yields an `Agent`. The
caller registers tools on `agent.registry`, then calls
`agent.tool(name, **args)`. Every call routes through policy, executes
(if allowed), and writes an audit event. `agent.trace` is populated
for UI display.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zta.audit import Audit
from zta.identity import Identity
from zta.policy import Decision, Policy
from zta.tools import ToolRegistry

_log = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """The outcome of one `agent.tool(...)` call."""

    ok: bool
    value: Any | None = None
    error: str | None = None


@dataclass
class TraceEntry:
    """One entry in `agent.trace`, populated per `tool()` call."""

    ts: str
    request_id: str
    tool: str
    args: dict[str, Any]
    decision: str
    reason: str
    ok: bool
    error: str | None


@dataclass
class Agent:
    """The runtime handle inside a session(). Owns identity, policy, audit, registry."""

    agent_id: str
    policy: Policy
    audit: Audit
    identity: Identity
    registry: ToolRegistry
    trace: list[TraceEntry] = field(default_factory=list)

    def tool(self, name: str, **args: Any) -> ToolResult:
        request_id = uuid.uuid4().hex
        decision = self.policy.decide(agent_id=self.agent_id, tool=name, args=args)
        reason = self.policy.reason()
        ts = datetime.now(UTC).isoformat()

        if decision is Decision.DENY:
            return self._record_deny(
                request_id=request_id, ts=ts, name=name, args=args, reason=reason
            )
        if decision is Decision.PENDING_APPROVAL:
            full_reason = f"{reason} (pending_approval denied in MVP)"
            return self._record_pending(
                request_id=request_id, ts=ts, name=name, args=args, reason=full_reason
            )

        # decision is ALLOW (or default-deny which is also a DENY above)
        try:
            fn = self.registry.get(name)
        except Exception as exc:
            return self._record_error(
                request_id=request_id, ts=ts, name=name, args=args, error_msg=str(exc)
            )
        try:
            value = fn(**args)
        except Exception as exc:
            return self._record_error(
                request_id=request_id, ts=ts, name=name, args=args, error_msg=str(exc)
            )
        return self._record_allow(
            request_id=request_id, ts=ts, name=name, args=args, reason=reason, value=value
        )

    def _record_allow(
        self,
        *,
        request_id: str,
        ts: str,
        name: str,
        args: dict[str, Any],
        reason: str,
        value: Any,
    ) -> ToolResult:
        self.audit.append(
            agent_id=self.agent_id,
            request_id=request_id,
            action=f"tool:{name}",
            resource=f"tool:{name}",
            decision="allow",
            reason=reason,
        )
        entry = TraceEntry(
            ts=ts,
            request_id=request_id,
            tool=name,
            args=args,
            decision="allow",
            reason=reason,
            ok=True,
            error=None,
        )
        self.trace.append(entry)
        return ToolResult(ok=True, value=value, error=None)

    def _record_deny(
        self,
        *,
        request_id: str,
        ts: str,
        name: str,
        args: dict[str, Any],
        reason: str,
    ) -> ToolResult:
        self.audit.append(
            agent_id=self.agent_id,
            request_id=request_id,
            action=f"tool:{name}",
            resource=f"tool:{name}",
            decision="deny",
            reason=reason,
        )
        entry = TraceEntry(
            ts=ts,
            request_id=request_id,
            tool=name,
            args=args,
            decision="deny",
            reason=reason,
            ok=False,
            error=reason,
        )
        self.trace.append(entry)
        return ToolResult(ok=False, value=None, error=reason)

    def _record_pending(
        self,
        *,
        request_id: str,
        ts: str,
        name: str,
        args: dict[str, Any],
        reason: str,
    ) -> ToolResult:
        self.audit.append(
            agent_id=self.agent_id,
            request_id=request_id,
            action=f"tool:{name}",
            resource=f"tool:{name}",
            decision="pending_approval",
            reason=reason,
        )
        entry = TraceEntry(
            ts=ts,
            request_id=request_id,
            tool=name,
            args=args,
            decision="pending_approval",
            reason=reason,
            ok=False,
            error=reason,
        )
        self.trace.append(entry)
        return ToolResult(ok=False, value=None, error=reason)

    def _record_error(
        self,
        *,
        request_id: str,
        ts: str,
        name: str,
        args: dict[str, Any],
        error_msg: str,
    ) -> ToolResult:
        self.audit.append(
            agent_id=self.agent_id,
            request_id=request_id,
            action=f"tool:{name}",
            resource=f"tool:{name}",
            decision="error",
            reason=error_msg,
        )
        entry = TraceEntry(
            ts=ts,
            request_id=request_id,
            tool=name,
            args=args,
            decision="error",
            reason=error_msg,
            ok=False,
            error=error_msg,
        )
        self.trace.append(entry)
        return ToolResult(ok=False, value=None, error=error_msg)


@contextmanager
def session(
    *,
    agent: str,
    policy: Path,
    audit: Path,
    key_dir: Path,
) -> Iterator[Agent]:
    """Yield an `Agent` bound to the given identity/policy/audit/key_dir."""
    identity = Identity.load_or_create(agent, key_dir)
    loaded_policy = Policy.load(policy)
    audit_log = Audit(audit)
    yield Agent(
        agent_id=agent,
        policy=loaded_policy,
        audit=audit_log,
        identity=identity,
        registry=ToolRegistry(),
    )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_runtime.py -v`
Expected: 16 tests pass.

---

### Task 3: Full verification

- [ ] **Step 1: Lint, format, typecheck, coverage**

Run:
```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && \
  .venv/bin/mypy zta tests && .venv/bin/pytest --cov=zta -v
```

Expected: all green; library coverage ≥ 90%.

- [ ] **Step 2: End-to-end smoke**

Run:
```bash
.venv/bin/python -c "
from pathlib import Path
import tempfile
from zta.runtime import session
from zta.tools import tool

@tool
def add(a: int, b: int) -> int:
    return a + b

@tool
def boom() -> str:
    raise RuntimeError('nope')

with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    (td / 'p.yaml').write_text('''
rules:
  - tool: add
    decision: allow
  - tool: boom
    decision: deny
    reason: too dangerous
  - tool: ghost
    decision: allow
''')
    with session(agent='bot', policy=td / 'p.yaml', audit=td / 'a.jsonl', key_dir=td / 'keys') as a:
        a.registry.register(add)
        a.registry.register(boom)
        r1 = a.tool('add', a=2, b=3)
        r2 = a.tool('boom')
        r3 = a.tool('ghost')  # not registered
        print('add:', r1.ok, r1.value)
        print('boom:', r2.ok, r2.error)
        print('ghost:', r3.ok, r3.error)
        print('trace len:', len(a.trace))
    from zta.audit import Audit
    events = Audit(td / 'a.jsonl').read_all()
    print('audit events:', len(events))
    print('chain valid:', Audit(td / 'a.jsonl').verify_chain())
"
```

Expected output (the `add:` and `boom:` lines are exact):
```
add: True 5
boom: False too dangerous
ghost: False tool not registered: ghost
trace len: 3
audit events: 3
chain valid: True
```

If any `False` is shown for the first column, or `chain valid: False`, STOP and fix.

---

### Task 4: Commit and push

- [ ] **Step 1: Stage**

Run: `git add zta/runtime.py tests/test_runtime.py docs/superpowers/plans/2026-06-18-f06-zta-runtime.md`

- [ ] **Step 2: Commit**

Run:
```bash
git commit -m "feat(f06): zta.runtime - session() + Agent with policy-gated tool calls

- zta/runtime.py: ToolResult, TraceEntry, Agent, session() context manager
- session(agent, policy, audit, key_dir) loads Identity/Policy/Audit and
  creates an empty ToolRegistry; yields Agent bound to all four
- Agent.tool(name, **args): generates request_id, calls policy.decide,
  routes by decision: allow (execute + audit allow), deny (no execute +
  audit deny), pending_approval (audit + behave as deny in MVP), or
  error (tool missing or raises; audit error)
- Each call appends a TraceEntry to agent.trace for UI display
- 16 unit tests covering session init, tool allow/deny/error/
  pending_approval, trace population, request_id propagation to audit
- E2E smoke: allow + deny + missing-tool + chain-valid"
```

- [ ] **Step 3: Push and open PR**

Run:
```bash
git push -u origin feature/f06-zta-runtime
```

PR body:

```markdown
Implements docs/superpowers/plans/2026-06-18-f06-zta-runtime.md.

## What
- zta/runtime.py: session() context manager + Agent class
- Agent.tool(): policy-gated tool call flow with full audit + trace
- 16 unit tests + e2e smoke

## Verification
- ruff check / format: clean
- mypy zta tests (strict): 0 issues
- pytest --cov=zta: 73+ tests pass, library coverage ≥ 90%
- e2e smoke: allow/deny/missing-tool all behave per spec; chain valid

## Spec
docs/superpowers/specs/2026-06-18-zta-mvp-design.md section 3.5
```

---

## Self-Review

**Spec coverage:** Spec section 3.5 lists `ToolResult`, `Agent`, `session()`, `agent.tool(name, **args)`, `agent.trace`. All present. Tool-call flow (6 steps) implemented as specified. `pending_approval` treated as deny in MVP per spec.

**Placeholders:** None.

**Type consistency:** `ToolResult`, `TraceEntry`, `Agent` all dataclasses with consistent field names. `session` is a contextmanager yielding `Agent`.

**Security:**
- Every call generates a fresh `request_id` and audits it (deny-by-default surface — even the unknown-tool error path writes an audit event)
- Exception in tool is caught and reported as a deny-shape `ToolResult`, not propagated; audit records the error
- `pending_approval` is treated as deny (no silent allow)
- Trace is per-Agent instance; not exposed cross-session
