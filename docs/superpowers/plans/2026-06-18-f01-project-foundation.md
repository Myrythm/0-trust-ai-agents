# Feature 1: Project Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the Python project foundation — `pyproject.toml` with all runtime + dev dependencies, package layout, `pytest`/`ruff`/`mypy` configuration, GitHub Actions CI (lint + typecheck + test), `.env.example`, and a smoke test that proves the import path works. No business logic yet.

**Architecture:** A single Python package `zta/` installed via `pip install -e ".[dev]"`. CI runs on every push to any branch and on PRs to `main`. Local dev loop: `ruff check`, `ruff format`, `mypy src tests`, `pytest --cov`.

**Tech Stack:** Python 3.11+, `hatchling` build backend, `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `ruff`, `mypy` (strict).

---

## File Structure

Files created in this feature (no modifications of existing files):

```
0trust-ai-agents/
├── pyproject.toml                    # project metadata + deps + tool configs
├── .env.example                      # ZTA_OPENAI_API_KEY, ZTA_POLICY_PATH, etc.
├── .github/
│   └── workflows/
│       └── ci.yml                    # GitHub Actions: lint, typecheck, test
├── zta/
│   ├── __init__.py                   # version string only
│   └── py.typed                      # marker so mypy treats it as a typed package
├── tests/
│   ├── __init__.py                   # empty marker
│   ├── conftest.py                   # sys.path bootstrap, env fixture
│   └── test_import.py                # one smoke test
└── .gitignore                        # add Python ignores (already present, extend if needed)
```

**Responsibility per file:**
- `pyproject.toml` — single source of truth for deps, tool configs, packaging
- `.env.example` — documents env vars used by later features (F7+)
- `.github/workflows/ci.yml` — CI on push + PR
- `zta/__init__.py` — `__version__ = "0.1.0"`, no other exports
- `zta/py.typed` — empty marker file; tells mypy the package has type info
- `tests/conftest.py` — adds `src/` to `sys.path` for editable installs without re-install
- `tests/test_import.py` — asserts `import zta` and `zta.__version__` are accessible

---

## Tasks

### Task 1: Write `pyproject.toml`

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create the file with the full content below**

```toml
[build-system]
requires = ["hatchling>=1.18"]
build-backend = "hatchling.build"

[project]
name = "zta"
version = "0.1.0"
description = "Zero Trust control plane for AI agents (MVP)"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "Apache-2.0" }
authors = [{ name = "Zero Trust AI Agents" }]
keywords = ["zero-trust", "ai-agents", "security"]

dependencies = [
  "pyyaml>=6.0",
  "cryptography>=42.0",
  "pydantic>=2.6",
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "jinja2>=3.1",
  "openai>=1.30",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "pytest-cov>=4.1",
  "respx>=0.21",
  "ruff>=0.3",
  "mypy>=1.8",
]

[tool.hatch.build.targets.wheel]
packages = ["zta"]

[tool.ruff]
line-length = 100
target-version = "py311"
src = ["zta", "tests"]

[tool.ruff.lint]
select = [
  "E", "F", "I", "B", "UP", "N", "S", "C4", "RET", "SIM", "TID", "PT", "RUF",
]
ignore = ["S101", "E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S", "N", "B008", "B017"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
warn_return_any = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
no_implicit_optional = true
plugins = ["pydantic.mypy"]
mypy_path = "zta"

[[tool.mypy.overrides]]
module = ["docker.*", "boto3.*", "botocore.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["zta"]
branch = true

[tool.coverage.report]
show_missing = true
skip_covered = false
fail_under = 70
```

- [ ] **Step 2: Verify the file parses**

Run: `python -c "import tomllib; tomllib.loads(open('pyproject.toml').read())"`
Expected: no output (success).

---

### Task 2: Create `zta/__init__.py` and `zta/py.typed`

**Files:**
- Create: `zta/__init__.py`
- Create: `zta/py.typed`

- [ ] **Step 1: Create `zta/__init__.py` with the version string only**

```python
"""Zero Trust control plane for AI agents (MVP)."""

from __future__ import annotations

__version__ = "0.1.0"
```

- [ ] **Step 2: Create empty `zta/py.typed` marker file**

Run: `touch zta/py.typed`
Expected: file exists, empty.

---

### Task 3: Write the failing smoke test

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/test_import.py`

- [ ] **Step 1: Create empty `tests/__init__.py`**

Run: `touch tests/__init__.py`

- [ ] **Step 2: Create `tests/conftest.py` with sys.path bootstrap and env fixture**

```python
"""Shared pytest fixtures for the ZTA MVP."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "zta"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ZTA_ENV", "test")
    monkeypatch.setenv("ZTA_LOG_LEVEL", "WARNING")
    yield
```

- [ ] **Step 3: Create `tests/test_import.py` with the smoke test**

```python
"""Smoke test: the package imports and exposes a version string."""

from __future__ import annotations


def test_zta_imports() -> None:
    import zta

    assert zta.__version__ == "0.1.0"


def test_zta_version_is_string() -> None:
    import zta

    assert isinstance(zta.__version__, str)
    assert len(zta.__version__.split(".")) == 3
```

- [ ] **Step 4: Run the test to verify it fails (no venv yet, this is expected)**

Run: `python -m pytest tests/test_import.py -v`
Expected: `ModuleNotFoundError: No module named 'zta'` (or `No module named 'pytest'`).

If pytest is missing too, that's fine — Task 4 will install deps.

---

### Task 4: Create the venv and install the project + dev deps

**Files:** none

- [ ] **Step 1: Create a venv using `uv` (or fall back to `python -m venv`)**

Run (preferred — `uv` is faster):
```bash
uv venv .venv --python 3.11
```

Fallback if `uv` is not available:
```bash
python3.11 -m venv .venv
```

Expected: `.venv/` directory created.

- [ ] **Step 2: Install the project in editable mode with dev deps**

Run (with `uv`):
```bash
uv pip install --python .venv/bin/python -e ".[dev]"
```

Run (with stock pip):
```bash
.venv/bin/pip install -e ".[dev]"
```

Expected: installation succeeds; key packages installed include `pytest`, `ruff`, `mypy`, `pydantic`, `fastapi`, `cryptography`, `pyyaml`, `openai`, `jinja2`, `httpx`.

- [ ] **Step 3: Run the smoke test — it should now PASS**

Run: `.venv/bin/pytest tests/test_import.py -v`
Expected:
```
tests/test_import.py::test_zta_imports PASSED
tests/test_import.py::test_zta_version_is_string PASSED
2 passed
```

---

### Task 5: Run the full verification trio (lint, format, typecheck, test)

**Files:** none

- [ ] **Step 1: Ruff lint**

Run: `.venv/bin/ruff check .`
Expected: `All checks passed!`

- [ ] **Step 2: Ruff format check**

Run: `.venv/bin/ruff format --check .`
Expected: `N files already formatted`

- [ ] **Step 3: mypy strict typecheck**

Run: `.venv/bin/mypy zta tests`
Expected: `Success: no issues found in N source files`

- [ ] **Step 4: pytest with coverage**

Run: `.venv/bin/pytest --cov=zta -v`
Expected: 2 tests pass; coverage report shows `TOTAL ... 100%` (only `zta/__init__.py` exists).

---

### Task 6: Create `.env.example`

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example` documenting env vars used by later features**

```bash
# ZTA service environment template.
# Copy to .env and fill in real values. Never commit .env.

# --- General ---
ZTA_ENV=dev
ZTA_LOG_LEVEL=INFO

# --- OpenAI (used by F8+) ---
ZTA_OPENAI_API_KEY=
ZTA_OPENAI_MODEL=gpt-4o-mini

# --- Policy + audit (used by F6+) ---
ZTA_POLICY_PATH=./policy.yaml
ZTA_AUDIT_PATH=./audit.jsonl

# --- Identity (used by F2+) ---
ZTA_KEY_DIR=./.zta/keys

# --- Demo data (used by F12+) ---
ZTA_DB_PATH=./data.db
```

---

### Task 7: Create GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: ci

on:
  push:
    branches: [main, "feature/**"]
  pull_request:
    branches: [main]

permissions:
  contents: read

env:
  PYTHON_VERSION: "3.11"

jobs:
  lint:
    name: ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install "ruff>=0.3"
      - run: ruff check .
      - run: ruff format --check .

  typecheck:
    name: mypy
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: mypy zta tests

  test:
    name: pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install -e ".[dev]"
      - run: pytest --cov=zta --cov-report=xml
      - uses: actions/upload-artifact@v4
        with:
          name: coverage
          path: coverage.xml
```

- [ ] **Step 2: Verify the YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml').read())"`
Expected: no output (success).

---

### Task 8: Commit

**Files:** all of the above

- [ ] **Step 1: Stage everything**

Run: `git add pyproject.toml .env.example .github/ zta/ tests/`
Expected: clean staging (no `audit.jsonl`, no `.venv`, no `__pycache__` — those are gitignored).

- [ ] **Step 2: Commit with conventional message**

Run:
```bash
git commit -m "feat(f01): project foundation - pyproject, CI, smoke test

- pyproject.toml: hatchling build, runtime deps (pyyaml, cryptography,
  pydantic, fastapi, uvicorn, jinja2, openai, httpx), dev deps (pytest,
  pytest-asyncio, pytest-cov, respx, ruff, mypy strict)
- zta/ package skeleton with __version__ and py.typed marker
- tests/ with conftest (sys.path bootstrap, env fixture) and one smoke test
- .env.example documenting env vars for future features
- GitHub Actions CI: ruff (lint + format check), mypy strict, pytest
  with coverage, on push to main + feature/* and PRs to main"
```

- [ ] **Step 3: Create the feature branch and push**

Run:
```bash
git switch -c feature/f01-project-foundation
git push -u origin feature/f01-project-foundation
```

Expected: branch pushed to origin. Open the PR (URL printed by `gh` if available, or via the GitHub web UI). The PR description should reference this plan file.

---

## Verification Checklist (run all before opening the PR)

- [ ] `.venv/bin/ruff check .` → clean
- [ ] `.venv/bin/ruff format --check .` → clean
- [ ] `.venv/bin/mypy zta tests` → 0 issues
- [ ] `.venv/bin/pytest --cov=zta -v` → 2 passed, coverage 100%
- [ ] `python -c "import zta; print(zta.__version__)"` → prints `0.1.0`
- [ ] Branch pushed; PR opened; user is assigned as reviewer

---

## Self-Review

**Spec coverage:** Spec section 7 (File Structure) lists `pyproject.toml`, `.env.example`, `.github/workflows/ci.yml` — all covered.
**Placeholders:** None. All commands exact; all code complete.
**Type consistency:** `zta.__version__` is referenced in test as `str`; matches `__init__.py` definition.
**No duplicate `[tool.ruff.lint.per-file-ignores]` keys** in `pyproject.toml` — task 1's final snippet is the single source.
