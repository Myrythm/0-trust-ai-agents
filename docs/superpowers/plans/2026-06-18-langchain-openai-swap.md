# Replace OpenAI SDK with LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the bare `openai` SDK client in `app.py` with `langchain-openai`'s `ChatOpenAI`, keeping the manual tool-calling loop and ZTA runtime integration unchanged.

**Architecture:** Monolith swap — only `app.py` changes structurally. `ChatOpenAI.bind_tools(_TOOL_SCHEMAS).invoke(messages)` replaces `client.chat.completions.create(...)`. `AIMessage.tool_calls` (with pre-parsed `args` dicts) replaces the bare SDK's `tc.function.arguments` JSON strings. The existing `respx`-mocked tests are the contract: they mock `https://api.openai.com/v1/chat/completions` (the same endpoint `ChatOpenAI` hits) and assert on the unchanged `/chat` reply/trace shape.

**Tech Stack:** `langchain-openai>=1.0,<2.0` (latest `1.3.2`, pulls `langchain-core` 1.4.x and `openai` as transitive deps), `respx` for testing, existing `httpx`. No new deps beyond the swap.

**Spec:** `docs/superpowers/specs/2026-06-18-langchain-openai-swap-design.md`

---

## File Structure

```
pyproject.toml                # modify: openai>=1.30 -> langchain-openai>=1.0,<2.0
app.py                        # modify: import + _get_chat_model + _run_chat_loop (lines 28, 109-166)
tests/test_app.py             # modify: cosmetic docstring/test-name wording only (contract unchanged)
README.md                     # modify: wording "OpenAI function calling" -> "LangChain tool calling"
.env.example                  # modify: comment wording
```

No new files. No `zta/` library changes.

---

## Task 1: Swap the dependency in `pyproject.toml` and install

**Files:**
- Modify: `pyproject.toml:22`

- [ ] **Step 1: Replace the openai dependency line**

In `pyproject.toml`, change line 22 from:

```toml
  "openai>=1.30",
```

to:

```toml
  "langchain-openai>=1.0,<2.0",
```

- [ ] **Step 2: Install the new dep into the venv**

Run:

```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: installs `langchain-openai`, `langchain-core`, keeps `openai` as transitive, keeps `respx`/`httpx`.

- [ ] **Step 3: Verify the import resolves**

Run:

```bash
.venv/bin/python -c "from langchain_openai import ChatOpenAI; print(ChatOpenAI)"
```

Expected: prints `<class 'langchain_openai.chat_models.base.ChatOpenAI'>` with no ImportError.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: swap openai SDK for langchain-openai in dependencies"
```

---

## Task 2: Swap the import and client factory in `app.py`

**Files:**
- Modify: `app.py:28` (import), `app.py:109-115` (`_get_openai_client`)

- [ ] **Step 1: Replace the import on line 28**

Change:

```python
from openai import OpenAI
```

to:

```python
from langchain_openai import ChatOpenAI
```

- [ ] **Step 2: Rename `_get_openai_client` to `_get_chat_model` and return `ChatOpenAI`**

Replace the function at `app.py:109-115`:

```python
def _get_openai_client() -> OpenAI:
    api_key = os.environ.get("ZTA_OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="ZTA_OPENAI_API_KEY environment variable is not set"
        )
    return OpenAI(api_key=api_key)
```

with:

```python
def _get_chat_model() -> ChatOpenAI:
    api_key = os.environ.get("ZTA_OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="ZTA_OPENAI_API_KEY environment variable is not set"
        )
    model = os.environ.get("ZTA_OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, api_key=api_key)
```

Note: `model` resolution moves here from `_run_chat_loop` (see Task 3).

- [ ] **Step 3: Run the missing-api-key test to verify it still passes**

Run:

```bash
.venv/bin/pytest tests/test_app.py::test_chat_openai_missing_api_key_returns_500 -v
```

Expected: PASS (the 500-on-missing-key behavior is preserved).

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor(app): swap OpenAI client for ChatOpenAI factory"
```

---

## Task 3: Rewrite `_run_chat_loop` to use `ChatOpenAI.bind_tools().invoke()`

**Files:**
- Modify: `app.py:118-166` (`_run_chat_loop`)

The existing `respx`-mocked tests are the contract. They must still pass after this rewrite.

- [ ] **Step 1: Run the chat tests to capture the baseline failure**

Run:

```bash
.venv/bin/pytest tests/test_app.py -v -k "chat" 2>&1 | tail -30
```

Expected: FAIL — `_run_chat_loop` still calls `_get_openai_client()` / `client.chat.completions.create(...)` which no longer exist. This confirms the tests exercise the path we're about to rewrite.

- [ ] **Step 2: Replace `_run_chat_loop` body**

Replace `app.py:118-166` (the entire `_run_chat_loop` function):

```python
def _run_chat_loop(
    messages: list[dict[str, object]],
    cfg: AppConfig,
) -> tuple[list[dict[str, object]], str, list[dict[str, object]]]:
    """Run the OpenAI tool-calling loop. Returns (final_messages, reply, trace_dicts)."""
    client = _get_openai_client()
    model = os.environ.get("ZTA_OPENAI_MODEL", "gpt-4o-mini")
    with session(
        agent=cfg.agent_id,
        policy=cfg.policy_path,
        audit=cfg.audit_path,
        key_dir=cfg.key_dir,
    ) as agent:
        agent.registry.register(_echo, name="echo")
        agent.registry.register(_db_query, name="db_query")
        agent.registry.register(_db_write, name="db_write")
        for _ in range(MAX_TOOL_ITERATIONS):
            completion = client.chat.completions.create(
                model=model, messages=messages, tools=_TOOL_SCHEMAS
            )
            msg = completion.choices[0].message
            if not msg.tool_calls:
                messages.append({"role": "assistant", "content": msg.content or ""})
                return messages, msg.content or "", [t.__dict__ for t in agent.trace]
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                fn_args = json.loads(tc.function.arguments)
                result = agent.tool(tc.function.name, **fn_args)
                tool_content = str(result.value) if result.ok else (result.error or "")
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_content})
    raise HTTPException(
        status_code=500, detail=f"too many tool iterations (>{MAX_TOOL_ITERATIONS})"
    )
```

with:

```python
def _run_chat_loop(
    messages: list[dict[str, object]],
    cfg: AppConfig,
) -> tuple[list[dict[str, object]], str, list[dict[str, object]]]:
    """Run the LangChain ChatOpenAI tool-calling loop. Returns (final_messages, reply, trace_dicts)."""
    chat = _get_chat_model().bind_tools(_TOOL_SCHEMAS)
    with session(
        agent=cfg.agent_id,
        policy=cfg.policy_path,
        audit=cfg.audit_path,
        key_dir=cfg.key_dir,
    ) as agent:
        agent.registry.register(_echo, name="echo")
        agent.registry.register(_db_query, name="db_query")
        agent.registry.register(_db_write, name="db_write")
        for _ in range(MAX_TOOL_ITERATIONS):
            ai = chat.invoke(messages)
            if not ai.tool_calls:
                messages.append({"role": "assistant", "content": ai.content or ""})
                return messages, ai.content or "", [t.__dict__ for t in agent.trace]
            messages.append(
                {
                    "role": "assistant",
                    "content": ai.content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"]),
                            },
                        }
                        for tc in ai.tool_calls
                    ],
                }
            )
            for tc in ai.tool_calls:
                result = agent.tool(tc["name"], **tc["args"])
                tool_content = str(result.value) if result.ok else (result.error or "")
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": tool_content}
                )
    raise HTTPException(
        status_code=500, detail=f"too many tool iterations (>{MAX_TOOL_ITERATIONS})"
    )
```

Key differences from the old body:
1. `_get_openai_client()` + `model` env read → `_get_chat_model().bind_tools(_TOOL_SCHEMAS)` (model read moved into the factory in Task 2).
2. `client.chat.completions.create(model=..., messages=..., tools=...)` → `chat.invoke(messages)` (tools already bound; messages passed as dicts which LangChain accepts).
3. `completion.choices[0].message` → `ai` (an `AIMessage`).
4. `msg.tool_calls` (list of `ChatCompletionMessageToolCall` Pydantic objects with `.id`, `.function.name`, `.function.arguments` JSON string) → `ai.tool_calls` (list of dicts with `["id"]`, `["name"]`, `["args"]` already-parsed dict).
5. `json.loads(tc.function.arguments)` → dropped; `tc["args"]` is already parsed.
6. `tc.id` / `tc.function.name` → `tc["id"]` / `tc["name"]`.
7. The assistant message dict appended back to `messages` keeps the same OpenAI wire shape (`{"id","type":"function","function":{"name","arguments": json.dumps(...)}}`) so the next `invoke` and the `respx` mocks stay compatible.

- [ ] **Step 3: Run the full chat test suite**

Run:

```bash
.venv/bin/pytest tests/test_app.py -v -k "chat" 2>&1 | tail -40
```

Expected: all `chat` tests PASS, including:
- `test_chat_runs_echo_tool_through_zta`
- `test_chat_deny_via_runtime_call`
- `test_chat_audits_to_configured_path`
- `test_chat_openai_no_function_call_returns_content`
- `test_chat_openai_tool_deny_propagates`
- `test_chat_form_post_returns_html_with_reply`
- `test_chat_form_post_renders_trace_panel`
- `test_e2e_chat_db_query_allowed`
- `test_e2e_chat_db_write_denied`

If any fail due to LangChain echoing messages differently on the second `invoke`, inspect the failure: the most likely cause is the `tool_calls` field shape in the echoed assistant dict. The construction in Step 2 already uses the OpenAI wire shape, so failures here should be rare; if one occurs, fix the dict construction in `_run_chat_loop` (not the test).

- [ ] **Step 4: Run the full test suite to confirm no regressions**

Run:

```bash
.venv/bin/pytest --cov=zta 2>&1 | tail -20
```

Expected: all tests PASS; coverage stays at or above the 70% floor (`pyproject.toml:94`).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "refactor(app): rewrite _run_chat_loop to use ChatOpenAI.bind_tools().invoke()"
```

---

## Task 4: Update the module docstring in `app.py`

**Files:**
- Modify: `app.py:1-13` (module docstring)

- [ ] **Step 1: Update the F8 sentence in the docstring**

In `app.py`, the module docstring currently says (lines 4-7):

```
This file lives at the repo root (not under `zta/`) because it is the
demo service that USES the ZTA library. F7 shipped the JSON skeleton;
F8 wired OpenAI function calling; F9 added the Jinja2 chat UI; F10
and F11 wrapped the audit and policy endpoints in templates; F12
adds db_query/db_write tools, the seed script, and e2e smoke.
```

Change the `F8 wired OpenAI function calling` clause to:

```
F8 wired OpenAI function calling (since swapped to LangChain ChatOpenAI);
```

So the full sentence becomes:

```
F8 wired OpenAI function calling (since swapped to LangChain ChatOpenAI); F9 added the Jinja2 chat UI; F10
and F11 wrapped the audit and policy endpoints in templates; F12
adds db_query/db_write tools, the seed script, and e2e smoke.
```

- [ ] **Step 2: Run ruff to confirm no formatting issues**

Run:

```bash
.venv/bin/ruff check app.py && .venv/bin/ruff format --check app.py
```

Expected: both pass with no output.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "docs(app): note LangChain swap in module docstring"
```

---

## Task 5: Update test docstring wording in `tests/test_app.py`

**Files:**
- Modify: `tests/test_app.py:1` (module docstring), `tests/test_app.py:41-46` (`_openai_completion` docstring)

The contract (mocks + assertions) is unchanged; only descriptive wording that names the bare SDK is touched.

- [ ] **Step 1: Update the module docstring**

`tests/test_app.py:1` currently:

```python
"""Tests for the FastAPI app (F7 + F8)."""
```

change to:

```python
"""Tests for the FastAPI app (F7 + F8; F8 now uses LangChain ChatOpenAI)."""
```

- [ ] **Step 2: Update the `_openai_completion` helper docstring**

`tests/test_app.py:41-46` currently:

```python
def _openai_completion(
    content: str | None = None,
    tool_calls: list[tuple[str, dict[str, object]]] | None = None,
    model: str = "gpt-4o-mini",
) -> dict[str, object]:
    """Build a canned OpenAI ChatCompletion response."""
```

change the docstring to:

```python
    """Build a canned OpenAI ChatCompletion response (still valid for ChatOpenAI)."""
```

The helper itself is unchanged — `ChatOpenAI` parses the same OpenAI ChatCompletion JSON shape.

- [ ] **Step 3: Run the test suite to confirm wording changes didn't break anything**

Run:

```bash
.venv/bin/pytest tests/test_app.py -q 2>&1 | tail -10
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_app.py
git commit -m "docs(tests): note ChatOpenAI in app test docstrings"
```

---

## Task 6: Update `README.md` and `.env.example` wording

**Files:**
- Modify: `README.md:6`, `README.md:46`, `.env.example:8`

- [ ] **Step 1: Update `README.md` line 6**

Change:

```
uses OpenAI function calling, the ZTA library intercepts each call,
```

to:

```
uses LangChain tool calling (ChatOpenAI), the ZTA library intercepts each call,
```

- [ ] **Step 2: Update `README.md` architecture TL;DR line 46**

Change:

```
    -> OpenAI Chat Completions (function calling)
```

to:

```
    -> LangChain ChatOpenAI (tool calling)
```

- [ ] **Step 3: Update `.env.example` comment line 8**

Change:

```
# --- OpenAI (used by F8+) ---
```

to:

```
# --- LangChain / OpenAI (used by F8+) ---
```

Env var names (`ZTA_OPENAI_API_KEY`, `ZTA_OPENAI_MODEL`) are unchanged.

- [ ] **Step 4: Commit**

```bash
git add README.md .env.example
git commit -m "docs: reflect LangChain ChatOpenAI in README and .env.example"
```

---

## Task 7: Full verification and PR

**Files:** none (verification + push)

- [ ] **Step 1: Run ruff lint + format check**

Run:

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Expected: both pass with no errors.

- [ ] **Step 2: Run mypy strict**

Run:

```bash
.venv/bin/mypy zta tests
```

Expected: no errors. If mypy complains about `ai.tool_calls` / `tc["args"]` typing on `app.py`, note that `app.py` is already exempted from `disallow_untyped_defs` (`pyproject.toml:76-79` overrides `module = ["tests.*", "app"]`), but `strict = true` still applies. If a specific LangChain type stub is missing, add a targeted `# type: ignore[...]` with the error code on the offending line — do not loosen the global config.

- [ ] **Step 3: Run the full test suite with coverage**

Run:

```bash
.venv/bin/pytest --cov=zta 2>&1 | tail -20
```

Expected: all tests PASS; coverage >= 70%.

- [ ] **Step 4: Push the branch**

Run:

```bash
git push -u origin feature/langchain-openai-swap
```

- [ ] **Step 5: Open the PR**

Run:

```bash
gh pr create --title "refactor: replace OpenAI SDK with LangChain ChatOpenAI" --body "..." --base main
```

PR body should summarize: what changed (app.py swap), what didn't (zta/ library, env vars, test contract), verification results, and the spec/plan doc links. Request the user's review.

- [ ] **Step 6: Confirm CI is green**

Run:

```bash
gh pr checks
```

Expected: all required checks (ruff, mypy, pytest) pass. If a check fails, fix locally, commit, push again.

---

## Self-Review Notes

- **Spec coverage:** spec section 3 (deps) → Task 1; section 4.1-4.2 (import + factory) → Task 2; section 4.3-4.4 (schema unchanged + loop) → Task 3; section 4.5 (docstring) → Task 4; section 5 (tests) → Task 5; section 6 (README/.env) → Task 6; section 7 (verification) → Task 7. All sections covered.
- **No placeholders:** every code step contains the exact code; every command step contains the exact command and expected result.
- **Type consistency:** `_get_chat_model` (Task 2) is referenced by `_run_chat_loop` (Task 3). `ai.tool_calls` dict keys (`["id"]`, `["name"]`, `["args"]`) are used consistently in Task 3 and match the Context7-verified `AIMessage.tool_calls` shape.
