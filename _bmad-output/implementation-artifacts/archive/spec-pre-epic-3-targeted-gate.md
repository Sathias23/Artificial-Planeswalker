---
title: 'Pre-Epic-3 Targeted Gate (G1/G2/G3 + nullability audit + index-build docs)'
type: 'chore'
created: '2026-06-27'
status: 'done'
baseline_commit: 'bba39113965890624f61eb5c21e396c4d9348718'
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-2-retro-2026-06-24.md'
  - '{project-root}/_bmad-output/implementation-artifacts/deferred-work.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Epic 2's retro promoted three recurring deferrals to a gate that must clear before Epic 3 (skills) sits on top of the search tools: **G1** `_FakeEmbedder` duplicated across 5 test files, **G2** no `limit` upper bound on the two semantic tools (silent starvation past `over_fetch_k`), **G3** a fresh checkout with no `card_vec` index makes `semantic_search_cards`/`find_similar_cards` raise a raw `OperationalError` (`isError=True`) instead of a usable message. Brad also asked to fold in the **nullability audit** (stale 1-4/1-6 ledger items) and the **D1 docs** task (index-build prerequisite + WAL-checkpoint-before-backup).

**Approach:** One cohesive housekeeping pass — extract a shared fake embedder, add a `limit > 50` guard, add an "index not built" pre-check that returns a structured status, add a regression test confirming the already-present Card nullability validators protect `validate_deck`, document the index-build/backup prerequisites, and close the resolved ledger entries.

## Boundaries & Constraints

**Always:** Pure refactor/hardening — zero change to existing passing behavior (G1 is a no-op rename; nullability validators already exist). All new guards return a graceful `status` (`isError=False`), never raise. Match existing module conventions (validation-vocabulary style, `mode="before"` validator style, `tests/fixtures/` module shape). Keep `mypy --strict` + ruff clean; pre-commit must pass.

**Ask First:** Renaming the public status enum value (proposed `"index_unavailable"`) or choosing a different `limit` ceiling than 50. Any change that would alter an existing tool's success-path output shape.

**Never:** Do NOT fix the long tail of accepted-risk/infra/cosmetic ledger items (LIKE-wildcard escaping, `np.frombuffer` read-only, CWD-relative migration paths, etc.) — only the gate + nullability + docs scope. Do NOT widen `CardSummary`/`Card` field types to `| None` (validators already coerce). Do NOT touch `src/agent`/`src/ui` legacy. Do NOT build the actual index or commit the DB.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Limit over ceiling | `semantic_search_cards`/`find_similar_cards` with `limit=51` | `status="invalid"`, message names the 1–50 range | Graceful, no raise |
| Limit at ceiling | `limit=50` | Normal search (still `ok`/`empty`) | N/A |
| No index table | `card_vec` absent (fresh checkout) | `status="index_unavailable"` + "run `build_card_embeddings`" message | Graceful, `isError=False` |
| Empty index table | `card_vec` exists, 0 rows | `status="index_unavailable"` (same message) | Graceful |
| Index present | `card_vec` populated | Unchanged search behavior | N/A |
| NULL legalities/games card | `validate_deck` over a Card whose `legalities`/`games` were DB-NULL | No `AttributeError`/`TypeError`; card flagged not-legal/unavailable | Coerced `{}`/`[]` by existing validators |

</frozen-after-approval>

## Code Map

- `tests/fixtures/embedder.py` — **NEW**. Canonical `FakeEmbedder` (union: `dim`, `encode`, `encode_batch`, `total_embedded`, deterministic one-hot via `_assigned` modulo `EMBEDDING_DIM`).
- `tests/unit/search/test_query.py`, `tests/unit/search/test_index_builder.py`, `tests/integration/conftest.py`, `tests/integration/mcp_server/test_semantic_search_tool.py`, `tests/integration/mcp_server/test_find_similar_tool.py` — delete local `_FakeEmbedder`/`_FakeVecEmbedder`, import shared `FakeEmbedder`, rename ~46 call sites.
- `src/search/query.py` — **NEW** `index_is_populated(conn) -> bool` (sqlite_master check for `CARD_VEC_TABLE` + non-empty).
- `src/mcp_server/tools/semantic_search.py` — `_MAX_LIMIT = 50` + `limit > 50` guard in `_validation_error`; add `"index_unavailable"` to `SemanticSearchResult.status`; pre-check guard after validation, before `embedder.encode`.
- `src/mcp_server/tools/find_similar.py` — same `limit` guard; add `"index_unavailable"` to `SimilarCardsResult.status`; pre-check guard after validation, before `_resolve_seed`.
- `tests/unit/logic/test_deck_validator.py` — add NULL-legalities/NULL-games regression tests.
- `tests/integration/mcp_server/test_semantic_search_tool.py` + `test_find_similar_tool.py` — add `limit>50` and `index_unavailable` (drop `card_vec`) cases.
- `README.md`, `_bmad-output/project-context.md` — D1 index-build + WAL-checkpoint-before-backup notes.
- `_bmad-output/implementation-artifacts/deferred-work.md` — close resolved entries.

## Tasks & Acceptance

**Execution:**
- [x] `tests/fixtures/embedder.py` — create `FakeEmbedder` covering the union of all 5 fakes; module docstring matching `card_data.py` convention.
- [x] 5 test files — delete local fake classes, add `from tests.fixtures.embedder import FakeEmbedder`, rename instantiations + type annotations.
- [x] `src/search/query.py` — add `index_is_populated(conn)`: return `False` if `card_vec` not in `sqlite_master`, else `bool` of `SELECT EXISTS(SELECT 1 FROM card_vec)`. Bind table name via `CARD_VEC_TABLE`.
- [x] `src/mcp_server/tools/semantic_search.py` — add `_MAX_LIMIT = 50`; in `_validation_error` return a range message when `limit > _MAX_LIMIT`; extend status Literal with `"index_unavailable"`; after validation return that status when `not index_is_populated(conn)`.
- [x] `src/mcp_server/tools/find_similar.py` — same `_MAX_LIMIT`/guard, status extension, and pre-check.
- [x] `tests/unit/logic/test_deck_validator.py` — add tests: a Card with `legalities=None` and one with `games=None` pass through `validate_deck` without raising and produce the expected violations.
- [x] `tests/integration/mcp_server/test_semantic_search_tool.py` + `test_find_similar_tool.py` — add `limit=51 → invalid` and "drop `card_vec` → `index_unavailable`" cases.
- [x] `README.md` + `_bmad-output/project-context.md` — document `uv run python scripts/build_card_embeddings.py` prerequisite and WAL-checkpoint-before-file-copy-backup (NFR10).
- [x] `deferred-work.md` — add a "Resolved by Pre-Epic-3 Targeted Gate (2026-06-27)" section listing the closed G1/G2/G3 + stale nullability entries.

**Acceptance Criteria:**
- Given the suite, when run after G1, then exactly one `FakeEmbedder` definition exists, no `_FakeEmbedder`/`_FakeVecEmbedder` remain, and all 526 prior tests still pass.
- Given either semantic tool, when called with `limit > 50`, then `status="invalid"` with a clear range message; `limit=50` still searches.
- Given a connection whose `card_vec` is missing or empty, when either tool runs, then it returns `status="index_unavailable"` with a build-the-index message and `isError=False` (no `OperationalError` escapes).
- Given a Card with NULL `legalities`/`games`, when `validate_deck` runs, then it does not raise and flags the card as expected.
- Given `mypy --strict` and `ruff`/pre-commit, when run, then all pass clean.

## Design Notes

**G3 placement & rationale:** an empty `card_vec` must be distinguished from a genuine no-match — an empty table would otherwise fall through to `status="empty"` ("relax your filters"), which misleads. Hence a pre-check, not a `try/except OperationalError` (which is too broad and misses the empty case). Guard runs after input validation so bad input still gets `"invalid"` precedence.

**G2 ceiling:** `limit ≤ 50` sits well under `hybrid_search`'s `over_fetch_k=200`, so the over-fetch can never be starved by `limit` (closes both the 2.4 and 2.5 ledger flags at once). Mirror the existing `if limit < 1:` branch.

**Nullability is mostly already done:** `Card` and `CardSummary` carry `@field_validator(..., mode="before")` coercions (`None → ""/[]/{}`), locked by `test_schemas.py:243-333`. `validate_deck`'s `card.legalities.get(...)`/`set(card.games)` are therefore already safe — this tier only adds the missing regression test and closes the stale 1-4/1-6 ledger entries. No schema type changes.

Shared fake (golden shape):
```python
class FakeEmbedder:
    def __init__(self) -> None:
        self.dim = EMBEDDING_DIM
        self._assigned: dict[str, int] = {}
        self.total_embedded = 0
    def encode(self, text: str) -> NDArray[np.float32]:
        return self._vector_for(text)
    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        self.total_embedded += len(texts)
        return [self._vector_for(t) for t in texts]
```

## Verification

**Commands:**
- `uv run pytest -q` — expected: all pass, count ≥ prior 526 (new cases added, 0 regressions).
- `uv run pytest tests/integration/mcp_server/test_semantic_search_tool.py tests/integration/mcp_server/test_find_similar_tool.py tests/unit/logic/test_deck_validator.py -q` — expected: new G2/G3/nullability cases green.
- `uv run ruff check . && uv run ruff format --check .` — expected: clean.
- `uv run mypy src/` — expected: clean (status-Literal additions type-check).
- `grep -rn "_FakeEmbedder\|_FakeVecEmbedder" tests/` — expected: no matches.

## Suggested Review Order

**G3 — graceful "index not built" (the headline change)**

- Entry point: the probe that distinguishes missing / empty / populated `card_vec` without raising.
  [`query.py:189`](../../src/search/query.py#L189)
- Guard placed after validation, before embedding — returns the new status, never an OperationalError.
  [`semantic_search.py:195`](../../src/mcp_server/tools/semantic_search.py#L195)
- Same guard before seed resolution; the whole-index check is distinct from per-seed "not indexed".
  [`find_similar.py:359`](../../src/mcp_server/tools/find_similar.py#L359)
- New `index_unavailable` status on both result models, mirrored into the LLM-facing tool docstrings.
  [`server.py:444`](../../src/mcp_server/server.py#L444)

**G2 — `limit` ceiling**

- `_MAX_LIMIT = 50` kept under `over_fetch_k=200`; rejected in the existing validation chain.
  [`semantic_search.py:121`](../../src/mcp_server/tools/semantic_search.py#L121)
  [`find_similar.py:182`](../../src/mcp_server/tools/find_similar.py#L182)

**G1 — shared fake embedder**

- One canonical `FakeEmbedder` (the union of all five copies) — every test file now imports this.
  [`embedder.py:17`](../../tests/fixtures/embedder.py#L17)

**Nullability regression + peripherals**

- Confirms the existing Card validators protect `validate_deck` from NULL legalities/games.
  [`test_deck_validator.py:637`](../../tests/unit/logic/test_deck_validator.py#L637)
- Index-build prerequisite + WAL-checkpoint-before-backup (D1).
  [`README.md`](../../README.md)
