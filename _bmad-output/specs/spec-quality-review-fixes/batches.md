# Batches

PR grouping for SPEC-quality-review-fixes. Two Greptile runs. Order is top to bottom.

| Batch | Capabilities | Review | Files touched | Generated artifacts to rebuild |
|---|---|---|---|---|
| 0 | CAP-6 | no Greptile; straight to master | `AGENTS.md` (new, via `bmad-project-context`), `CLAUDE.md` (new, one line: `@AGENTS.md`), `_bmad-output/project-context.md` (absorbed then deleted); no `customize.toml` edits | none |
| 1 | CAP-1, CAP-4, CAP-5 | Greptile run 1 | `src/data/database.py` (connect hook: pragma, orphan cleanup), `src/data/repositories/deck.py` (delete, add, bulk add, remove, quantity, identity helper), `src/data/importers/scryfall.py` (verify stale-card delete order under enforcement), `src/search/index_builder.py` (metadata invalidation), `tests/integration/data/test_deck_repository.py`, `tests/unit/data/test_database.py`, `tests/unit/search/test_index_builder.py` | `plugin/` if any tool surface moves |
| 2 | CAP-2, CAP-3 | Greptile run 2 | `ui/src/state/connection.ts` (re-drive on every `live`, or subscribe before snapshot), `ui/src/state/deck.ts` (restart the stopped poll on a transient refusal), `ui/src/state/socket.ts` only if the reconnect signal changes shape, `ui/src/state/connection.test.ts`, `ui/src/state/deck.test.ts`, `ui/src/App.test.tsx` ("boots exactly once" may count differently; the no-boot-on-re-render assertion stays) | `src/companion/app/static/`, `plugin/` |

## Preflight gate (before the first push of batches 1 and 2)

```
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32 && uv run pytest -q
cd ui && npm run lint && npm run format:check && npm run typecheck && npm test -- --run && npm run build && npm run gen:types && cd ..
uv run python -m scripts.build_plugin && git status --porcelain
```

Batch 1 runs the integration-marked tests too: the cascade and import tests live there, and the
review's own run deselected them.

## Evidence the review reproduced (2026-09-06, isolated databases)

| Finding | Reproduction |
|---|---|
| CAP-1 | `PRAGMA foreign_keys` = 0; one association row survived its deck's deletion |
| CAP-4 | Adding a coloured card left `color_identity=[]` and `updated_at` unchanged; a card with empty `colors` and blue `color_identity` still gave an empty deck identity |
| CAP-5 | Changing a card from red / mana value 1 to green / mana value 3 was reported as skipped; index metadata stayed red / 1 |
| CAP-2, CAP-3 | Source and test inspection only; not reproduced in a browser |

## Regression tests to add

- CAP-1: pragma reads 1 on a fresh connection from each engine; `delete_deck` leaves no
  association rows; dangling deck insert raises; seeded orphans are gone after the connect hook.
- CAP-2: active deck switched between snapshot response and first socket open.
- CAP-3: poll recovers before the deck refusal settles, and after; permanently refusing id does
  not loop; superseded request does not overwrite.
- CAP-4: one test per mutation path asserting `updated_at` advanced and identity recomputed;
  identity-only colours.
- CAP-5: colours-only change and mana-value-only change each refresh filter metadata with the
  embedder uncalled.
- CAP-6: a check that no `persistent_facts`-matched file names Chainlit or PydanticAI as current
  belongs in the CAP-6 PR description, not in the test suite.
