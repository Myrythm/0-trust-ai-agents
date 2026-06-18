# Feature 12: Demo Seed + End-to-End Smoke + README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the demo runnable end-to-end with a single command. Add `db_query` and `db_write` tools backed by SQLite, a `policy.yaml` that allows SELECTs and denies writes, an `examples/seed_db.py` that populates a sample DB, and a README quickstart. Add an e2e test that simulates the full demo flow without real OpenAI.

**Architecture:** Add `db_query` and `db_write` as tool functions in `app.py` (registered alongside `echo`). Add `policy.yaml` at the repo root with the data-analyst scenario. Add `examples/seed_db.py` to populate `data.db` with `customers` and `orders` tables. Add 3 e2e tests that exercise the full chat→policy→audit→policy page flow with mocked OpenAI. Update `.env.example` and `README.md`.

**Tech Stack:** stdlib `sqlite3`, `pathlib`. No new deps.

---

## File Structure

```
app.py                       # modify: add db_query, db_write tools; update schemas
policy.yaml                  # new (data analyst policy)
examples/seed_db.py          # new
.env.example                 # modify: add ZTA_DB_PATH
README.md                    # modify: full quickstart section
tests/test_app.py            # add 3 e2e tests
```

---

## Contract

**`policy.yaml`** (the data-analyst demo):
```yaml
agent: analyst-bot
default: deny
rules:
  - tool: db_query
    when: "args['sql'].strip().lower().split()[0] in ('select', 'with')"
    decision: allow
    reason: "SELECT/WITH queries are allowed for analyst-bot"
  - tool: db_query
    decision: deny
    reason: "non-SELECT on db_query is not allowed"
  - tool: db_write
    decision: deny
    reason: "db_write is disabled for analyst-bot"
```

**`db_query(sql: str) -> list[dict]`**: executes the SQL via `sqlite3`, returns rows as a list of dicts. **Allowed only when `policy.decide` returns allow.** If the SQL is not a SELECT/WITH, the policy denies it before the tool is called.

**`db_write(sql: str) -> str`**: stub — never actually called because policy denies it. Registered so the policy rule can match and the audit shows the deny.

**`examples/seed_db.py`**: creates `data.db` with `customers` and `orders` tables, populated with 5 customers and 10 orders.

---

## Tasks

### Task 1: Create `policy.yaml` at the repo root

**Files:**
- Create: `policy.yaml`

- [ ] **Step 1: Write the policy file**

```yaml
agent: analyst-bot
default: deny
rules:
  - tool: db_query
    when: "args['sql'].strip().lower().split()[0] in ('select', 'with')"
    decision: allow
    reason: "SELECT/WITH queries are allowed for analyst-bot"
  - tool: db_query
    decision: deny
    reason: "non-SELECT on db_query is not allowed"
  - tool: db_write
    decision: deny
    reason: "db_write is disabled for analyst-bot"
```

---

### Task 2: Create `examples/seed_db.py`

**Files:**
- Create: `examples/seed_db.py`

- [ ] **Step 1: Write the seed script**

```python
"""Populate data.db with sample customers and orders for the demo."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"

CUSTOMERS = [
    ("Alice", "alice@example.com"),
    ("Bob", "bob@example.com"),
    ("Carol", "carol@example.com"),
    ("Dave", "dave@example.com"),
    ("Eve", "eve@example.com"),
]

ORDERS = [
    (1, 19.99, "2024-01-15"),
    (1, 42.50, "2024-03-22"),
    (2, 8.75, "2024-02-10"),
    (2, 99.00, "2024-04-05"),
    (3, 15.00, "2023-12-01"),
    (3, 75.25, "2024-05-12"),
    (4, 200.00, "2024-06-30"),
    (4, 33.33, "2024-07-04"),
    (5, 5.99, "2023-08-19"),
    (5, 12.50, "2024-08-25"),
]


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE customers (
                id   INTEGER PRIMARY KEY,
                name  TEXT NOT NULL,
                email TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE orders (
                id          INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                amount      REAL NOT NULL,
                placed_on   TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
            """
        )
        cur.executemany("INSERT INTO customers (name, email) VALUES (?, ?)", CUSTOMERS)
        cur.executemany(
            "INSERT INTO orders (customer_id, amount, placed_on) VALUES (?, ?, ?)", ORDERS
        )
        conn.commit()
        print(f"Seeded {DB_PATH}: {len(CUSTOMERS)} customers, {len(ORDERS)} orders")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it runs**

Run: `.venv/bin/python examples/seed_db.py && .venv/bin/python -c "import sqlite3; c=sqlite3.connect('data.db'); print(c.execute('SELECT COUNT(*) FROM customers').fetchone())"`
Expected: prints `Seeded .../data.db: 5 customers, 10 orders` then `(5,)`.

---

### Task 3: Modify `app.py` to add `db_query` and `db_write` tools

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add the tool functions and update the OpenAI tool schemas**

Add the functions after `_echo`:

```python
import sqlite3


def _db_query(sql: str) -> list[dict[str, object]]:
    """Execute a SELECT (or WITH) and return rows as list of dicts."""
    db_path = Path(os.environ.get("ZTA_DB_PATH", "./data.db"))
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _db_write(sql: str) -> str:  # pragma: no cover -- denied by policy
    """Stub. Never called because policy denies db_write in MVP."""
    return "db_write is not permitted in this demo"


_TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "db_query",
            "description": "Execute a read-only SQL query against the analyst database. "
            "Only SELECT and WITH statements are allowed.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "db_write",
            "description": "Write to the database. Disabled for analyst-bot.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    },
]
```

Replace the single `_ECHO_TOOL_SCHEMA` reference with `_TOOL_SCHEMAS` in `_run_chat_loop` and in the `client.chat.completions.create(tools=...)` call.

In `_run_chat_loop`, register `_db_query` and `_db_write` (keep `_echo` for compat):

```python
        agent.registry.register(_echo, name="echo")
        agent.registry.register(_db_query, name="db_query")
        agent.registry.register(_db_write, name="db_write")
```

- [ ] **Step 2: Run all app tests; fix any regressions**

The existing tests mock OpenAI to call `echo` only; they should still pass because the LLM picks `echo` and the runtime gates it. The `db_query` / `db_write` tools are registered but not called.

---

### Task 4: Update `.env.example` with `ZTA_DB_PATH`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add the line (if not already present)**

The `.env.example` from F1 already has `ZTA_DB_PATH=./data.db`. No change needed. Verify:

```bash
grep ZTA_DB_PATH .env.example
```

Expected: `ZTA_DB_PATH=./data.db` is present.

---

### Task 5: Add e2e tests

**Files:**
- Modify: `tests/test_app.py`

- [ ] **Step 1: Append 3 e2e tests**

```python
# ---------- F12: Demo end-to-end ----------


def test_e2e_demo_seed_creates_tables(tmp_path: Path) -> None:
    """examples/seed_db.py creates customers + orders tables with rows."""
    import sqlite3
    import subprocess

    db_path = tmp_path / "demo.db"
    env = {"ZTA_DB_PATH": str(db_path)}
    # Run the seed script with a temporary DB path
    import os as _os
    _os.environ["ZTA_DB_PATH"] = str(db_path)
    try:
        result = subprocess.run(
            [".venv/bin/python", "examples/seed_db.py"],
            capture_output=True,
            text=True,
            env={**_os.environ, "ZTA_DB_PATH": str(db_path)},
            check=False,
        )
        assert result.returncode == 0, result.stderr
        conn = sqlite3.connect(str(db_path))
        customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        conn.close()
        assert customers == 5
        assert orders == 10
    finally:
        _os.environ.pop("ZTA_DB_PATH", None)
        if db_path.exists():
            db_path.unlink()


def test_e2e_chat_db_query_allowed(tmp_path: Path, monkeypatch) -> None:
    """Full flow: chat with db_query (SELECT) is allowed, audit shows allow."""
    import sqlite3
    monkeypatch.setenv("ZTA_OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ZTA_DB_PATH", str(tmp_path / "demo.db"))
    # Seed the DB
    seed_db = tmp_path / "demo.db"
    conn = sqlite3.connect(str(seed_db))
    conn.execute("CREATE TABLE customers (id INTEGER, name TEXT)")
    conn.executemany(
        "INSERT INTO customers VALUES (?, ?)", [(1, "Alice"), (2, "Bob"), (3, "Carol")]
    )
    conn.commit()
    conn.close()
    cfg = AppConfig(
        agent_id="analyst-bot",
        policy_path=Path("policy.yaml"),
        audit_path=tmp_path / "a.jsonl",
        key_dir=tmp_path / "keys",
    )
    client = TestClient(create_app(cfg))
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(
            side_effect=[
                Response(
                    200,
                    json=_openai_completion(
                        tool_calls=[("db_query", {"sql": "SELECT * FROM customers"})]
                    ),
                ),
                Response(200, json=_openai_completion(content="3 customers: Alice, Bob, Carol")),
            ]
        )
        resp = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "show all customers"}]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "3 customers" in body["reply"]
    assert any(t["tool"] == "db_query" and t["decision"] == "allow" for t in body["trace"])


def test_e2e_chat_db_write_denied(tmp_path: Path, monkeypatch) -> None:
    """Full flow: chat with db_write is denied by policy, audit shows deny."""
    import sqlite3
    monkeypatch.setenv("ZTA_OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ZTA_DB_PATH", str(tmp_path / "demo.db"))
    seed_db = tmp_path / "demo.db"
    conn = sqlite3.connect(str(seed_db))
    conn.execute("CREATE TABLE customers (id INTEGER, name TEXT)")
    conn.close()
    cfg = AppConfig(
        agent_id="analyst-bot",
        policy_path=Path("policy.yaml"),
        audit_path=tmp_path / "a.jsonl",
        key_dir=tmp_path / "keys",
    )
    client = TestClient(create_app(cfg))
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(
            side_effect=[
                Response(
                    200,
                    json=_openai_completion(
                        tool_calls=[("db_write", {"sql": "DELETE FROM customers"})]
                    ),
                ),
                Response(200, json=_openai_completion(content="I cannot write to the database")),
            ]
        )
        resp = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "delete all customers"}]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "I cannot write to the database"
    assert any(t["tool"] == "db_write" and t["decision"] == "deny" for t in body["trace"])
```

- [ ] **Step 2: Run the e2e tests**

Run: `.venv/bin/pytest tests/test_app.py -v -k e2e`
Expected: 3 pass.

---

### Task 6: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Quickstart section with the full demo flow**

```markdown
## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Seed the demo database (5 customers, 10 orders)
python examples/seed_db.py

# 3. Set your OpenAI key
export ZTA_OPENAI_API_KEY=sk-...
export ZTA_DB_PATH=./data.db

# 4. Run the server
uvicorn app:app --reload

# 5. Open http://localhost:8000
```

## Try the demo

1. **Chat:** "show all customers" — OpenAI calls `db_query("SELECT * FROM customers")`; policy allows; LLM returns a summary.
2. **Chat:** "delete all customers" — OpenAI calls `db_write("DELETE FROM customers")`; policy denies; LLM acknowledges it cannot.
3. **Visit `/audit`** — see the allow/deny events with the hash chain banner. Polls every 3s.
4. **Visit `/policy`** — see the rendered policy rules and the raw YAML.

## Architecture (TL;DR)

```
Browser (Jinja2)
  → FastAPI (app.py)
    → OpenAI Chat Completions (function calling)
      → zta.runtime.session (F6)
        → Policy.decide (F3) → Audit.append (F4)
        → Tool call (db_query, db_write, echo) via ToolRegistry (F5)
        → Identity (F2) signs per agent
```

## Development

```bash
ruff check . && ruff format --check .
mypy zta tests
pytest --cov=zta
```

CI runs all three on every push. See `docs/superpowers/plans/` for feature-by-feature plans.
```

---

### Task 7: Full verification

- [ ] **Step 1: Lint, format, typecheck, coverage**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && \
  .venv/bin/mypy zta tests && .venv/bin/pytest --cov=zta -q
```

Expected: all green; `zta` library coverage ≥ 90%.

- [ ] **Step 2: End-to-end manual smoke (no OpenAI, just to confirm the wiring)**

```bash
.venv/bin/python -c "
from pathlib import Path
import json, tempfile
import os
os.environ['ZTA_DB_PATH'] = 'data.db'
import subprocess
subprocess.run(['.venv/bin/python', 'examples/seed_db.py'], check=True)

from fastapi.testclient import TestClient
import respx
from httpx import Response
from app import AppConfig, create_app
from zta.audit import Audit

with tempfile.TemporaryDirectory() as d:
    td = Path(d)
    cfg = AppConfig(
        agent_id='analyst-bot',
        policy_path=Path('policy.yaml'),
        audit_path=td / 'a.jsonl',
        key_dir=td / 'keys',
    )
    client = TestClient(create_app(cfg))
    with respx.mock(base_url='https://api.openai.com') as mock:
        mock.post('/v1/chat/completions').mock(side_effect=[
            Response(200, json={'id':'x','object':'chat.completion','created':0,'model':'m','choices':[{'index':0,'message':{'role':'assistant','content':None,'tool_calls':[{'id':'c1','type':'function','function':{'name':'db_query','arguments':json.dumps({'sql':'SELECT * FROM customers'})}}]},'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}),
            Response(200, json={'id':'x','object':'chat.completion','created':0,'model':'m','choices':[{'index':0,'message':{'role':'assistant','content':'5 customers'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}),
        ])
        resp = client.post('/chat', json={'messages':[{'role':'user','content':'show all customers'}]})
    print('reply:', resp.json()['reply'])
    print('trace:', [(t['tool'], t['decision']) for t in resp.json()['trace']])
    events = Audit(td / 'a.jsonl').read_all()
    print('audit events:', len(events))
    print('chain valid:', Audit(td / 'a.jsonl').verify_chain())
"
```

Expected:
```
Seeded .../data.db: 5 customers, 10 orders
reply: 5 customers
trace: [('db_query', 'allow')]
audit events: 1
chain valid: True
```

---

### Task 8: Commit, push, auto-merge

- [ ] **Step 1: Stage and commit**

```bash
git add app.py policy.yaml examples/ tests/ README.md \
        docs/superpowers/plans/2026-06-18-f12-demo-seed-smoke.md
git commit -m "feat(f12): demo seed, db_query/db_write tools, e2e smoke, README

- policy.yaml: data-analyst scenario (allow SELECT/WITH, deny db_write)
- examples/seed_db.py: populates data.db with 5 customers + 10 orders
- app.py: adds _db_query (SQLite SELECT) and _db_write (stub) tools;
  _TOOL_SCHEMAS exposes both to OpenAI function calling
- 3 e2e tests: seed script works, db_query allowed, db_write denied
- README: full quickstart + try-the-demo section
- The plan doc"
```

- [ ] **Step 2: Push, create PR, auto-merge**

```bash
git push -u origin feature/f12-demo-seed-smoke
# PR + auto-merge via API
```

---

## Self-Review

**Spec coverage:** Spec section 9 (demo flow acceptance): 5 steps. All demonstrable via the e2e tests + manual smoke. Spec section 7 (file structure): all files present.

**Placeholders:** None. The MVP is end-to-end runnable.

**Type consistency:** New tool functions have type hints. `_TOOL_SCHEMAS` is `list[dict[str, object]]`.

**Security:**
- `db_query` is policy-gated; only SELECT/WITH pass
- `db_write` is policy-deny by default
- Identity, audit, and policy all wired in
- No raw API keys in the codebase
