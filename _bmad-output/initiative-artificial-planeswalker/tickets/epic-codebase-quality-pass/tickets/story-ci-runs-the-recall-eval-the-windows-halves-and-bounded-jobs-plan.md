---
title: 'CI runs the recall eval, the Windows halves and bounded jobs'
type: 'chore'
ticket: 4
created: '2026-11-10'
status: 'built'
baseline_revision: 'de2da8c4a698eb08b447ccac6319fb710c10ff3f'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The semantic recall eval (the one silent-degradation risk AGENTS.md names) and the other model-backed search tests run in no CI job; the `msvcrt` / Windows-socket halves of `test_singleton.py`, `test_server.py`, `test_discovery.py` and `test_images.py` run only on the maintainer's machine; `quality` and `frontend` have no timeout, so a hang (such as the shared-image-cache spin logged by 4.2) burns six hours and blocks the `master` concurrency group; uv floats to whatever is latest; and a commit that only deletes a `src/` file skips the `build-plugin-sync` hook (T1-3-D1, T2-D3, T2-P3, T2-P5, T2-P8).

**Approach:** Add a scheduled, path-filtered `recall-eval` workflow that caches the fastembed model keyed on the locked fastembed version and runs the model-backed search, embedder, semantic-tool and index-builder integration tests (option (a) of T2-D3; the assessment benchmark stays local, as the review rules in every option; required checks stay model-free). Run the four per-platform companion unit files by path on the existing Windows job (option (a) of T1-3-D1), keeping its name since it is the required check. Give `quality` and `frontend` `timeout-minutes: 15`, pin uv with `version:` on every `setup-uv` step, and set `always_run: true` on `build-plugin-sync`.

</frozen-after-approval>

## Implementation Notes

Oneshot: about 100 lines of CI and hook config across four files, with no source or test code.

- Files: new `.github/workflows/recall-eval.yml`; `.github/workflows/ci.yml` (header, uv pin on both setup-uv steps, `timeout-minutes: 15` on `quality` and `frontend`, a second pytest step on `companion-integration`); `.github/workflows/live-contract.yml` (uv pin); `.pre-commit-config.yaml` (`always_run: true` on `build-plugin-sync`, its `files` filter removed); `AGENTS.md` (which job runs what).
- T2-D3: the recall job runs 5 tests (`test_rag_eval.py` x2, `test_embedder.py`, `test_semantic_search_tool.py::test_real_embedder_ranks_relevant_card_first`, `test_index_builder.py::test_real_embedder_end_to_end`) selected by path plus `-m integration`. The 12 assessment-benchmark tests (the review counted 11) stay local: they read the operator's real `cards.db`, and the review keeps them local under every option. Of the 16, 5 now run in CI.
- T2-D3: the PR/push runs restore the model from `actions/cache` (v6.1.0, SHA-pinned) keyed on the installed fastembed version (0.8.0 today) and the model name. The weekly run skips the cache on purpose: fastembed resolves `qdrant/bge-small-en-v1.5-onnx-q`'s current HF revision at download (`fastembed/common/model_management.py:235`), so only a fresh download tests what a new install fetches. The workflow file is in its own path filter, so this PR runs it.
- T1-3-D1: the four files run as a second step on `companion-integration`, whose `name:` is kept because `companion real-socket test (windows, py3.12)` is the only required status check on `master` (`gh api .../branches/master/protection`). `test_discovery.py:129`'s chmod test still skips on Windows; the review's "inject a PermissionError instead" idea is not part of option (a) and was not done.
- T2-P3: 15 min is about seven times the measured jobs (quality under 2 min, frontend about 2 min 11 s on the 4.1 master run). The 4.2 image-cache spin is unbounded (30+ min observed), so it now fails at 15 min, and `-v` (in `addopts`) leaves the stuck test's id as the log's last line. Every job in all three workflows now has `timeout-minutes`. No `pytest-timeout` (optional in the review; it would add a dev dependency and a `uv.lock` change).
- T2-P5: pinned with `version: "0.13.7"` on all four setup-uv steps, the version the last green master run resolved as "latest". Not `[tool.uv] required-version`: `build_plugin.py` copies `pyproject.toml` into `plugin/server/` verbatim (`SERVER_FILES`), so an exact pin there would refuse plugin users' uv. The maintainer's local uv is 0.12.13, behind CI; not changed here.
- T2-P8: one rebuild measured at 0.41-0.44 s (three runs). Grep of the pattern: the `mypy` hook (`files: ^src/`) skips a deletion-only commit the same way (a deleted module still imported elsewhere passes locally, CI catches it); story 4.65 rewrites that hook under D10, so it is logged in `deferred-work.md` for 4.65 rather than changed here. `ruff`, `ruff-format`, `no-local-machine-paths` and `ui-prettier-check` cannot fail on a deletion.
- Surprise: committing in a worktree crashes the installed hook (`SRE module mismatch`): it runs pre-commit from the main checkout's 3.12 venv, which then breaks inside this worktree's 3.13 venv. Commits here went through a hook shim kept outside the repo that runs the same `pre-commit hook-impl --config=.pre-commit-config.yaml --hook-type=pre-commit` from the worktree's own uv environment, so every hook still ran.

Verified locally:
- The recall job's pytest command from an empty `FASTEMBED_CACHE_DIR`: 5 passed, 36 deselected, exit 0, 13 s including the model download.
- The Windows step's four files on Windows 11: 277 passed, 1 skipped (the chmod test) in 3.84 s.
- T2-P8 in a throwaway worktree: on the old config, a staged deletion of `src/mcp_server/tools/messages.py` gives `rebuild plugin/ ... (no files to check) Skipped`, exit 0. On the new config, the control commit (config only) passed `build-plugin-sync`, and the deletion-only commit failed it (`Failed - files were modified by this hook`, exit 1, commit refused, `plugin/server/src/mcp_server/tools/messages.py` deleted by the rebuild).
- `actionlint` 1.7.12 on all three workflows: clean, exit 0; on a copy with a planted bad `timeout-minutes` and step reference it reports both, exit 1.
- Python gate: ruff, ruff format, mypy (both platforms) clean; `uv run pytest` 3346 passed, 2 skipped, 137.88 s.

Only the PR's CI run can prove: the Windows step on `windows-latest`, the uv pin taking effect, the recall job (cache miss, model download, cache save), and the timeouts parsing as job settings. The weekly cold-cache run and a cache hit can only show up on later runs.

## Verification

**Commands:**
- `uv run pytest -m integration tests/integration/search/ tests/integration/mcp_server/test_semantic_search_tool.py tests/unit/search/test_index_builder.py` with `FASTEMBED_CACHE_DIR` on an empty scratch dir -- expected: 5 passed from a cold model cache (the recall job's command).
- `uv run pytest tests/unit/companion/test_singleton.py tests/unit/companion/test_server.py tests/unit/companion/test_discovery.py tests/unit/companion/test_images.py` on Windows -- expected: all pass (the Windows step's command).
- In a scratch worktree, a commit that only deletes a `src/` file: expected to skip `build-plugin-sync` before the fix and fail it after (plugin/ modified).
- Python gate: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- expected: all pass.

**Manual checks (if no CLI):**
- Every job in `.github/workflows/*.yml` carries `timeout-minutes`, and every `setup-uv` step carries the same `version:`.
- Only the PR's CI run can prove the workflows themselves: the Windows step, the timeouts, the uv pin, and the recall job (on a PR it runs because the workflow file is in its path filter).

## Review Triage Log

Quick lens, pass 1: 5 findings; 0 high, 2 medium, 3 low, 0 false, 0 maybe-false. All five patched.

- medium, patch: `recall-eval.yml`'s path filter left out modules the search tools import directly (`src/paths.py`, `src/data/import_state.py`, `src/data/schemas/card.py`, `card_search.py`, `messages.py`) and `tests/integration/conftest.py`. Confirmed by grepping the `from src` imports of `src/search/*.py` and the three tools. Added all six; the push and pull_request lists are now one YAML anchor so they cannot drift (actionlint clean, both resolve to the same 18 paths).
- medium, patch: the cache key's model half was the literal `bge-small-en-v1.5`, so a model switch with no fastembed bump would hit the old key exactly, skip the save and re-download on every run. The key now reads `MODEL_NAME` from `src/search/embedder.py` (locally `BAAI-bge-small-en-v1.5`, fastembed `0.8.0`).
- low, patch: the Windows step's comment named `test_discovery.py`'s chmod test, which skips on `nt` (`test_discovery.py:129`); reworded to the os.replace-over-an-existing-file path, and the over-long line rewrapped.
- low, patch: the per-platform unit step ran only if the real-socket step passed, so one failure hid the other suite. It now runs with `if: ${{ !cancelled() && steps.sync.outcome == 'success' }}`.
- low, patch: the comment above the local hooks still said the plugin rebuilds "when a source input changes"; reworded to "every commit".
