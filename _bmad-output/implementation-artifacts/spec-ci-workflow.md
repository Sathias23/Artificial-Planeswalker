---
title: 'GitHub Actions CI workflow + issue/PR templates'
type: 'chore'
created: '2026-06-28'
status: 'done'
baseline_commit: '47505c749910491c591cb49cbcf0b637d7c8bb51'
context:
  - '{project-root}/CONTRIBUTING.md'
  - '{project-root}/SECURITY.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The public release (§6 of the release strategy) needs automated quality gates and contributor onboarding scaffolding. There is no `.github/` directory at all — PRs run no checks, and there are no issue/PR templates to guide contributors.

**Approach:** Add a single GitHub Actions workflow that mirrors the local pre-commit/CONTRIBUTING gates (`ruff check` → `ruff format --check` → `mypy src/` → `pytest -m "not integration"`) on a Python 3.12/3.13 matrix using `uv`, plus Markdown issue templates (bug, feature) and a pull-request template consistent with the existing CONTRIBUTING and SECURITY docs.

## Boundaries & Constraints

**Always:**
- Install via the official `astral-sh/setup-uv` action with caching enabled; install Python through it (matrix-driven). Pin third-party actions by commit SHA with a trailing `# vX.Y.Z` comment. Sync with `uv sync --locked` (the tracked `uv.lock` is authoritative — never re-resolve in CI; `--locked` additionally fails the run if the lock has drifted from `pyproject.toml`).
- Run gates as separate steps in this order so each fails the job independently: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run pytest -m "not integration"`.
- Matrix `python-version: ["3.12", "3.13"]` on `ubuntu-latest`, `fail-fast: false`.
- Trigger on `push` to `master` and on all `pull_request` events. Set workflow-level `permissions: contents: read`. Add a `concurrency` group keyed on the ref that cancels superseded **PR** runs only (`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`) so push-to-master runs always finish.
- Issue/PR templates must be consistent with the shipped `CONTRIBUTING.md` (gate commands, Conventional Commits, branch-off-master) and `SECURITY.md` (private reporting — never solicit security reports via a public issue).

**Ask First:**
- If `uv sync --frozen` unexpectedly fails to resolve on the 3.13 leg (verified safe against the lock — onnxruntime 1.27.0 has cp313 wheels), drop to a 3.12-only matrix rather than loosening or regenerating the lock.

**Never:**
- Do not run integration tests, build the embedding index, download the model, install the `observability` extra, or require any secret/API key in CI.
- Do not add Dependabot, CodeQL, release-publishing, or secret-scanning automation here — those are separate release-strategy items (secret scan stays manual, Brad's call).
- Do not modify `src/`, tests, `pyproject.toml`, `.pre-commit-config.yaml`, or the README. This run only adds files under `.github/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean PR | Code passes all gates | Both matrix legs green; merge unblocked | N/A |
| Lint violation | A ruff rule fails | `ruff check` step fails red; later steps don't mask it | Job fails, blocks merge |
| Format drift | File not ruff-formatted | `ruff format --check` step fails red | Job fails |
| Type error | `mypy --strict` finds an error in `src/` | `mypy src/` step fails red | Job fails |
| Test failure | A non-integration test fails | `pytest -m "not integration"` step fails red | Job fails |
| Security report intent | Contributor opens "New issue" | Templates offer bug/feature only; security routed to private reporting via config link | N/A |

</frozen-after-approval>

## Code Map

- `.github/workflows/ci.yml` -- NEW: the CI workflow (matrix lint/type/test job).
- `.github/PULL_REQUEST_TEMPLATE.md` -- NEW: PR description + checklist mirroring CONTRIBUTING quality gates.
- `.github/ISSUE_TEMPLATE/bug_report.md` -- NEW: bug report (Markdown front-matter template, label `bug`).
- `.github/ISSUE_TEMPLATE/feature_request.md` -- NEW: feature request (label `enhancement`).
- `.github/ISSUE_TEMPLATE/config.yml` -- NEW: `blank_issues_enabled: true` + a contact link routing security reports to `SECURITY.md` (no public security issues).
- `pyproject.toml` / `.pre-commit-config.yaml` / `CONTRIBUTING.md` -- READ-ONLY reference: source of the exact gate commands, matrix versions, and conventions to mirror.

## Tasks & Acceptance

**Execution:**
- [x] `.github/workflows/ci.yml` -- author the matrix workflow per Boundaries (setup-uv + cache, `uv sync --frozen`, four ordered gate steps, push+PR triggers, least-privilege permissions, concurrency cancel) -- automate the §6 quality gates for the public repo.
- [x] `.github/PULL_REQUEST_TEMPLATE.md` -- summary, related-issue, change-type, and a checklist (ruff lint/format clean, `mypy src/` clean, tests pass, Conventional Commit, docs updated if needed) -- guide contributors to the same gates CI enforces.
- [x] `.github/ISSUE_TEMPLATE/bug_report.md` -- description, repro steps, expected vs actual, environment (OS, Python, uv, MCP client) -- standardize bug reports.
- [x] `.github/ISSUE_TEMPLATE/feature_request.md` -- problem, proposed solution, alternatives, context -- standardize enhancement requests.
- [x] `.github/ISSUE_TEMPLATE/config.yml` -- contact link sending security reports to `SECURITY.md` / GitHub private reporting -- keep vulnerabilities out of public issues.

**Acceptance Criteria:**
- Given a fresh checkout on a Linux runner with no DB/model/keys/network, when the workflow runs, then `uv sync --frozen` succeeds and all four gate steps pass on both 3.12 and 3.13.
- Given the workflow YAML, when validated (actionlint / GitHub parse), then it has no syntax errors and pins third-party actions by commit SHA with a version comment (`actions/checkout@<sha> # v7.0.0`, `astral-sh/setup-uv@<sha> # v8.2.0`).
- Given a contributor opens the new-issue chooser, when they look for security reporting, then only bug/feature templates appear and a contact link directs them to private disclosure per `SECURITY.md`.
- Given the PR template, when a PR is opened, then its checklist matches CONTRIBUTING's quality gates verbatim in intent (ruff, mypy, pytest, Conventional Commits).

## Spec Change Log

- **2026-06-28 — post-review hardening (human-authorized, Brad).** After CHECKPOINT-1 approval and the 3-reviewer pass, Brad opted into three optional tweaks; the frozen `Always` block was renegotiated accordingly:
  - `uv sync --frozen` → `uv sync --locked` — keeps the lock authoritative *and* fails CI on lock/`pyproject.toml` drift (avoids a stale-lock false-green). Rejected the reviewer's paired `--all-extras` (would install the `observability`/logfire extra, violating "Never").
  - `cancel-in-progress: true` → `${{ github.event_name == 'pull_request' }}` — cancels only superseded PR runs so a rapid push to `master` never leaves the default branch without a completed check.
  - Actions SHA-pinned with version comments (`checkout@…#v7.0.0`, `setup-uv@…#v8.2.0`) for supply-chain hardening; also bumped `checkout@v4→v7.0.0` and `setup-uv@v5→v8.2.0`. **KEEP:** the four-gate order, headless `-m "not integration"` scoping, and Markdown-template choice all survived re-derivation unchanged. No Dependabot added (out of scope) — SHA pins are bumped manually.

## Design Notes

- **Headless-safe, no `testpaths` tricks:** investigation confirmed `pytest -m "not integration"` needs nothing heavy — only 12 tests carry `@pytest.mark.integration`, collection imports nothing heavy, `tests/conftest.py` is a no-op, and there is no `legacy/` tree.
- **mypy parity:** `uv run mypy src/` (synced venv) passes the same as pre-commit's isolated run because `ignore_missing_imports = true` and `src/` never imports `requests` — so do **not** copy pre-commit's vestigial `types-requests` into CI.
- **Markdown templates** chosen over YAML issue forms for low-maintenance simplicity (switchable later).
- Sketch:
  ```yaml
  on: { push: { branches: [master] }, pull_request: {} }
  permissions: { contents: read }
  concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }
  jobs:
    quality:
      strategy: { fail-fast: false, matrix: { python-version: ["3.12","3.13"] } }
      steps: [checkout, setup-uv(cache, python-version), uv sync --frozen, ruff check ., ruff format --check ., mypy src/, pytest -m "not integration"]
  ```

## Verification

**Commands:**
- `uv run ruff check .` -- expected: clean (exit 0), proving the CI lint gate passes.
- `uv run ruff format --check .` -- expected: clean, proving the format gate passes.
- `uv run mypy src/` -- expected: `Success: no issues found`, proving the type gate passes.
- `uv run pytest -m "not integration"` -- expected: all selected tests pass, no model download/network.
- `actionlint .github/workflows/ci.yml` (if available) -- expected: no findings; else inspect YAML manually.

**Manual checks:**
- After the PR is opened, confirm the `CI` workflow runs and both `3.12` and `3.13` legs go green (the PR is its own first CI proof).
- Open the repo "New issue" chooser locally/visually-review the template files: bug + feature shown, security routed to private reporting.

## Suggested Review Order

**CI pipeline** (the gate that runs on every PR/push)

- Entry point — the four quality gates, separate steps in dependency order so each fails independently.
  [`ci.yml:40`](../../.github/workflows/ci.yml#L40)

- Matrix: same gates on Python 3.12 and 3.13, `fail-fast: false` so one leg's failure still shows the other.
  [`ci.yml:27`](../../.github/workflows/ci.yml#L27)

- Safety envelope — least-privilege token, push-to-master + all-PR triggers, concurrency cancels superseded runs.
  [`ci.yml:13`](../../.github/workflows/ci.yml#L13)

**Contributor templates** (peripheral, no runtime effect)

- PR checklist mirrors the CI gates so contributors self-check before pushing.
  [`PULL_REQUEST_TEMPLATE.md:18`](../../.github/PULL_REQUEST_TEMPLATE.md#L18)

- Security reports routed to private disclosure (branch-agnostic `/security/policy`) — never a public issue.
  [`config.yml:4`](../../.github/ISSUE_TEMPLATE/config.yml#L4)

- Bug and feature issue templates (labels `bug` / `enhancement`).
  [`bug_report.md:2`](../../.github/ISSUE_TEMPLATE/bug_report.md#L2)
