# Implementation Plans Index — ZTA MVP

**Date:** 2026-06-18
**Source spec:** `docs/superpowers/specs/2026-06-18-zta-mvp-design.md`
**Workflow:** code per feature → push at `feature/{name}` → PR → user reviews

---

## Feature Breakdown (12 features)

Each feature is one branch, one plan doc, one PR. Library modules (2–6) and page modules (9–11) are independent and reviewable on their own.

| #  | Feature                         | Plan doc                                                        | Depends on          | Branch                              |
|----|---------------------------------|-----------------------------------------------------------------|---------------------|-------------------------------------|
| 1  | Project foundation              | `2026-06-18-f01-project-foundation.md`                          | —                   | `feature/f01-project-foundation`    |
| 2  | `zta.identity`                  | `2026-06-18-f02-zta-identity.md`                                | F1                  | `feature/f02-zta-identity`          |
| 3  | `zta.policy`                    | `2026-06-18-f03-zta-policy.md`                                  | F1                  | `feature/f03-zta-policy`            |
| 4  | `zta.audit`                     | `2026-06-18-f04-zta-audit.md`                                   | F1                  | `feature/f04-zta-audit`             |
| 5  | `zta.tools`                     | `2026-06-18-f05-zta-tools.md`                                   | F1                  | `feature/f05-zta-tools`             |
| 6  | `zta.runtime`                   | `2026-06-18-f06-zta-runtime.md`                                 | F2, F3, F4, F5      | `feature/f06-zta-runtime`           |
| 7  | FastAPI app skeleton            | `2026-06-18-f07-fastapi-skeleton.md`                            | F6                  | `feature/f07-fastapi-skeleton`      |
| 8  | OpenAI integration              | `2026-06-18-f08-openai-integration.md`                          | F7                  | `feature/f08-openai-integration`    |
| 9  | Jinja2 chat UI                  | `2026-06-18-f09-jinja-chat-ui.md`                               | F8                  | `feature/f09-jinja-chat-ui`         |
| 10 | Audit UI                        | `2026-06-18-f10-audit-ui.md`                                    | F4, F7              | `feature/f10-audit-ui`              |
| 11 | Policy UI                       | `2026-06-18-f11-policy-ui.md`                                   | F3, F7              | `feature/f11-policy-ui`             |
| 12 | Demo seed + smoke test + README | `2026-06-18-f12-demo-seed-smoke.md`                             | F8, F9, F10, F11    | `feature/f12-demo-seed-smoke`       |

**Parallelizable (F2–F5):** Library modules are independent of each other (each only depends on F1). They can be developed in any order or in parallel branches. F2–F5 are the natural concurrency point.

---

## Shared Conventions Across All Features

- **Python:** 3.11+
- **Build:** `hatchling` (PEP 621)
- **Test:** `pytest`, `pytest-asyncio`, `respx` for HTTP mocking
- **Lint:** `ruff` (E, F, I, B, UP, N, S, C4, RET, SIM, TID, PT, RUF)
- **Format:** `ruff format`
- **Typecheck:** `mypy --strict`
- **Coverage:** 70% minimum; library modules 90% (enforced by F1 CI)
- **Commit style:** Conventional Commits (`feat:`, `test:`, `ci:`, `docs:`, `chore:`, `fix:`)
- **Branch naming:** `feature/f{NN}-{kebab-name}`
- **One PR per feature.** PR description references the plan file path.

---

## How a Feature Plan Looks

Each plan has:
- Header (goal, architecture, tech stack)
- File Structure section (which files to create/modify)
- Bite-sized Tasks (TDD: failing test → run → impl → run → commit)
- Verification (ruff, mypy, pytest, smoke)

---

## Feature 1 — Project Foundation (this is the only plan written in full below; the rest are in stub form for now)

See `2026-06-18-f01-project-foundation.md`. After F1 merges, the workflow is:
1. Branch from `main`: `git switch -c feature/f02-zta-identity`
2. Read `2026-06-18-f02-zta-identity.md`
3. Implement task by task, committing per step
4. Push: `git push -u origin feature/f02-zta-identity`
5. Open PR; user reviews; merge; next feature

---

## Stubs for F2–F12 (filled in just before that feature starts)

The details for F2–F12 will be written just before each feature is started. The spec (`docs/superpowers/specs/2026-06-18-zta-mvp-design.md`) is the source of truth for contracts; the plan for each feature just turns that contract into bite-sized TDD steps.

If a feature is started and the spec is ambiguous, the spec gets clarified first (a small `docs/superpowers/specs/` amendment), then the plan is written, then the feature is implemented.
