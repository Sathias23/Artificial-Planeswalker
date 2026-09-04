---
title: 'Companion cold-open request diet'
type: 'refactor'
created: '2026-09-04'
status: 'done'
baseline_commit: 'ea031415dd30de338a2943ad29d8977ccff8cc46'
review_loop_iteration: 0
context: ['_bmad-output/specs/spec-quality-audit-p1/SPEC.md', '_bmad-output/specs/spec-quality-audit-p1/batches.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Batch 3 of SPEC-quality-audit-p1 (CAP-3). A companion cold open on the 99-card deck makes ~216 requests: `GET /api/decks` hydrates every card of every deck to compute three counts (117–160 ms on 52 decks); the deck-detail rows carry only a `CardSummary`, so the UI sweeps one `GET /api/cards/{id}` per distinct card (99 requests) and that route sends no cache header; the image route reads the database before the disk cache on every warm tile; and the boot's first frame is `no-active-deck`, which renders `<Welcome>` and fetches the 420 KB unhashed, `no-cache` hero even when a deck is active. Quiet-machine baseline: 529 ms median at 17.3, 395 ms at the 0.5.0 tip (D1).

**Approach:** Add a count-only summary query to `DeckRepository` for the list route. Add a full-card deck shape (`DeckCardFull` nesting `Card`, `DeckDetailFull`) beside the existing summary shapes and answer `GET /api/deck/{id}` with it; the UI seeds its card cache as hydrated from that response and drops the per-card sweep. Send `Cache-Control` on `GET /api/cards/{id}`. Read the image disk cache before the card row. Give `surfaceOf` a `booting` surface that renders nothing until the active-deck read settles. Move the hero to `ui/src/assets/` as a recompressed, content-hashed import. Regenerate `openapi.json`, `types.d.ts`, the SPA bundle and `plugin/` in the same PR, and measure `cdp_harness budget` before and after on a quiet machine.

## Boundaries & Constraints

**Always:** `DeckDetail`, `DeckCardSummary`, `CardSummary` and the MCP `load_deck`/`list_decks`/`create_deck` payloads stay exactly as they are — the new shapes are additions in `src/data/schemas/deck.py`, not edits. The list route keeps its bare-array body, `created_at DESC, id` order, and identical `DeckSummary` values (the SQL counts must equal today's Python counts, including `distinct_cards` across both boards). The format-check route keeps `get_deck_with_cards`. `DbSession` stays a dependency of both card routes so 503 still outranks 400. The disk cache key stays `(card_id, size, face)`; the negative cache stays after the disk read; file I/O stays behind `asyncio.to_thread`. `hydrateCard` and its dedupe/attempt gates stay for ids outside the deck (agent views, card detail). `booting` renders no image and no panel copy. The hero keeps `alt=""`, its `welcome-hero` class, and `width`/`height` attributes equal to the committed file's pixel size. Preflight gate from `batches.md` before the first push; `npm run gen:api`, `npm run build`, `build_plugin` committed in the same PR. Both `cdp_harness budget` medians (before at the story's base commit, after at the tip), with `requests_total` and `card_reads`, go in the PR body and the completion notes.

**Ask First:** Any change to `DeckSummary` fields or to the `/api/decks` or `/api/deck/{id}` paths. Adding a UI dependency for image processing. Any edit under the security files named in SPEC.md constraints. Removing the `summary` tier from `CardEntry`.

**Never:** A companion-local deck model in `src/companion` (AD-1). ETag/conditional requests on the card route. Changing `docs/hero-image.jpg` (provenance source). Touching `load_deck`'s use of `CardSummary`. Comment pruning beyond the sentences this story makes false (CAP-4 is story 5). Modifying `scripts/cdp_harness.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Deck list, mixed decks | 3 decks: 2 boards + commander, sideboard-only, empty | `GET /api/decks` bodies equal `DeckSummary.from_deck(...)` for each, same order; the SQL issues no `deck_cards.card` load | N/A |
| Deck list, no decks | empty table | `[]` | N/A |
| Deck detail | deck with 2 mainboard + 1 sideboard rows | `cards[*].card` is a full `Card` (`legalities`, `image_uris`, `card_faces` present); counts and metadata unchanged from today | N/A |
| Deck detail, unknown id | no such deck | `404 deck_not_found` (unchanged) | N/A |
| Card JSON | known id | `200`, body unchanged, `Cache-Control: private, max-age=3600` | N/A |
| Card JSON, unknown id | well-formed id, no row | `404 card_not_found`, no `Cache-Control` | N/A |
| Warm image, row present | cached `(id, normal, 0)` | `200` from disk; no `CardRepository` call, no CDN request, pacer untouched | N/A |
| Warm image, row deleted | cached file, no card row | `200` from disk (accepted: the disk cache is now the first authority; ledgered in Design Notes) | N/A |
| Cold image | no cached file | DB row → resolve → negative cache → fetch → write, as today; missing row `404 card_not_found`, no image `no_image_data` | unchanged tokens |
| Image, DB unusable | database not initialised, cache hit or miss | `503` (dependency resolves first) | unchanged |
| UI cold open, active deck | active-deck answers deck, detail embeds 2 cards | both cards `hydrated` with zero `/api/cards/` requests; total mount requests = 5 (decks, active-deck, detail, format-check, session); first frame renders no `img` and no panel | N/A |
| UI cold open, no active deck | active-deck answers none | first frame renders nothing; after settle `<Welcome>` with the hero `src` under `/assets/` | N/A |
| UI cold open, backend down | connection `down` before boot settles | `disconnected` panel (connection outranks booting) | N/A |
| UI, active-deck read fails | boot settles `refused`/`none` | booting exits on every settle path; existing panel shown | N/A |
| Agent view row outside deck | id not in the detail | one `GET /api/cards/{id}` as today | N/A |
| Hero asset | `GET /assets/hero-<hash>.jpg` | `200`, `Cache-Control` immutable; `GET /hero.jpg` no longer a 200 image | N/A |

</frozen-after-approval>

## Code Map

- `src/data/repositories/deck.py:240-268` `list_decks` — full two-level `selectinload` (`:264`); keep for MCP. Add `list_deck_summaries(format_filter=None) -> list[DeckSummary]` beside it: `select(DeckModel, sum(case sideboard=false → quantity), sum(case sideboard=true → quantity), count(distinct card_id))` outer-joined to `DeckCardModel`, `group_by(DeckModel.id)`, same order (`:263`); build `DeckSummary` from the row (metadata via the model's `*_list` properties, counts from the aggregates). `_summary_fields` (`schemas/deck.py:205-229`) is the Python reference for the counts.
- `src/data/schemas/deck.py:136-158` `DeckCardSummary`, `:259-309` `DeckDetail.from_deck` — templates. Add `DeckCardFull` (`card: Card`) and `DeckDetailFull(DeckSummary)` with `cards: list[DeckCardFull]` and a `from_deck` mirroring `:299-309` with `Card.model_validate(dc.card)`. Docstrings in the same style; they reach the wire, so obey `test_openapi_contract.py:251-345` (no `Args:`-style sections in what FastAPI emits, no Scryfall host strings).
- `src/companion/app/routes/decks.py:33-59` `read_decks` → `list_deck_summaries()`; delete the ledger comment `:51-57`. `:62-91` `read_deck` → `response_model=DeckDetailFull`, `DeckDetailFull.from_deck`; docstring `:72` references `DeckDetail`. `:94-138` format-check untouched. Module docstring `:1-20` (AD-1) stays true: shapes still come from `src.data`.
- `src/companion/app/routes/cards.py:105-158` `read_card` — return a `JSONResponse`/set `response.headers["Cache-Control"]` via a `Response` parameter; only the 200 carries it. Module docstring `:12-19` says the route sets no cache headers — rewrite. `:223-471` `read_card_image`: move the `cache.read` block (`:328-332`) above the `get_by_id` (`:298`); rewrite the ordering comments `:319-327` and `:352-356`.
- `src/companion/app/images.py:1185` `DiskCache.read(card_id, size, face)` — needs no row; `:856-880` path scheme. No change expected.
- `src/companion/contracts.py:171-181` — prose says clients get card detail from `GET /api/cards/{card_id}`; amend to "or from the deck detail".
- `scripts/dump_openapi.py:20-40` — running count prose (8 paths / 13 components) — the component set becomes: `+DeckCardFull +DeckDetailFull −DeckDetail −DeckCardSummary −CardSummary`; verify by regenerating.
- `ui/src/api/schema.ts:87,97,119` — aliases `CardSummary`, `DeckCardSummary`, `DeckDetail` → repoint to `DeckCardFull`/`DeckDetailFull` (the generated names); `schema.test.ts` gains a type pin that a deck row's `card` is `Card`.
- `ui/src/api/client.ts:610-619` `deckOf` validates only `id`/`name`/`cards` array — no change; `:817` comment "sets no cache headers" — fix.
- `ui/src/state/cards.ts:417-441` `seedCardSummaries` → `seedDeckCards(rows)` writing `{status:'hydrated', card}` (never downgrading a newer hydrated entry; a malformed row is skipped as today); `:600-624` `hydrateDeckCards` — delete; `:514-598` `hydrateCard` stays.
- `ui/src/state/deck.ts:511,574` — the two seeding calls; `:658-660` `Surface` union gains `{ kind: 'booting' }`; `:730-735` `surfaceOf`: after the `down` check, `deck.status === 'booting'` → booting.
- `ui/src/App.tsx:322-325` sweep effect + its comment block `:250-321` — delete; `:596-611` left slot: booting arm renders `null` (or an empty `aria-busy` region), `no-active-deck` arm unchanged.
- `ui/src/state/systemState.ts:13-20,96` — rationale for the initial `no-active-deck` panel — rewrite to say the poller's panel is masked by the booting surface until the active-deck read settles. `poller.ts` unchanged.
- `ui/src/components/Welcome/Welcome.tsx:29` `<img src="/hero.jpg" width="1536" height="1024">`; rationale `:5-18` (says Vite copies it unhashed) — rewrite. `import hero from '../../assets/hero.jpg'`; `Welcome.css:30-39` crops to 240 px high, so a smaller source is fine.
- `ui/public/hero.jpg` (420,280 B, 1536×1024) — delete; write the recompressed file to `ui/src/assets/hero.jpg` with a one-off Pillow step (`uv run python -c ...`: resize to ≤1200 wide, quality ~75, progressive, target ≤150 KB); Pillow is in `uv.lock`. `vite.config.ts` has default `assetsInlineLimit` (4 KB) so the file emits as `assets/hero-<hash>.jpg`; `emptyOutDir` removes the old root copy on rebuild.
- `src/companion/app/spa.py:348-372` — `assets/` prefix is already immutable, everything else `no-cache`; no change. `tests/unit/companion/test_spa.py:375-384` `test_the_hero_art_is_served_from_the_bundle_root` — replace with: the hashed hero under `assets/` is served immutable and `hero.jpg` is absent from `STATIC_DIR`.
- Tests, Python: `tests/unit/companion/test_routes_decks.py:156` `TestDeckList` (add the no-card-load proof via a `selectinload`/statement spy and the counts-equality row), `:239` `TestDeckDetail`, `:672` `TestCommittedSchema` (`{"DeckSummary","DeckDetail",...} <= names` → new names); `test_committed_schema.py:235-267` exact component set; `test_routes_cards.py:67` `TestCardDetail` (header rows); `test_routes_card_image.py:226` `TestNoImagePrecedence`, `:378` `TestDatabaseStatesOutrankParameterValidation`, `:1225`, `:1486`, `:1611` `TestTheWarmAnswerMatchesTheColdOne` (warm no longer consults the repository), `:1904`; `test_import_boundary.py:696-717` `_REPO_READ_METHODS` += `list_deck_summaries`; `tests/unit/data/test_deck_repository*` / `tests/integration/data/test_deck_repository.py` for the new query; `test_openapi_contract.py:151` byte-equality (regenerate).
- Tests, UI: `ui/src/App.test.tsx:1185-1232` cold-open budget (7 → 5, itemised comment rewritten, `/api/cards/` = 0), `:453-560,632-680` first-frame assertions, `:681-756` Welcome/hero and "no img behind panel" (add `booting`), `:758+` transition; `ui/src/state/cards.test.ts` (`seedCardSummaries` → `seedDeckCards`, hydrated seeding, `hydrateDeckCards` suite removed), `deck.test.ts` (`surfaceOf` booting arm, seeding), `Welcome.test.tsx`, `client.test.ts` fixtures carrying `card` objects.
- Docs: `ui/README.md:1290-1305` per-card retry paragraph; `CHANGELOG.md` `[Unreleased] ### Changed` — one bolded entry "**Companion cold-open request diet.**".
- Measurement: `uv run python -m scripts.cdp_harness budget --data-dir <robocopy of %LOCALAPPDATA%\artificial-planeswalker> --deck-id 813d0434-1bed-4419-bf9d-d9e4070704c4 --runs 5 --json <out>` (`scripts/cdp_harness.py:412-465`); it launches the companion itself, needs Chrome, reports `layout_ms` median, `requests_total`, `card_reads`. Quietness is a manual CPU sample (< 5%). Prior evidence: `.worktrees/process/.../archive/perf-evidence-d1-quiet-rerun-2026-08-25.md` (340/395/448 ms, 216 requests, 99 card reads).

## Tasks & Acceptance

**Execution:**
- [x] `src/data/repositories/deck.py`, `tests/unit/companion/test_import_boundary.py` -- `list_deck_summaries` aggregate query; classify it as a read -- deck list without card rows
- [x] `src/data/schemas/deck.py` -- `DeckCardFull` + `DeckDetailFull` (additive) -- full cards on the companion wire, MCP shapes untouched
- [x] `src/companion/app/routes/decks.py` -- list → summaries; detail → `DeckDetailFull`; comment/docstring fixes -- CAP-3
- [x] `src/companion/app/routes/cards.py` -- `Cache-Control: private, max-age=3600` on the 200; disk read before the row on images; comments rewritten -- CAP-3
- [x] `src/companion/contracts.py`, `scripts/dump_openapi.py` -- prose that becomes false -- no drift
- [x] `ui/src/api/schema.ts`, `schema.test.ts`, `client.ts` -- repoint aliases, type pin, header comment -- generated types consumed
- [x] `ui/src/state/cards.ts`, `deck.ts`, `App.tsx`, `systemState.ts` -- hydrated seeding, sweep removed, `booting` surface, comment rewrites -- one deck-detail request, nothing before the active-deck answer
- [x] `ui/src/assets/hero.jpg` (new), `ui/public/hero.jpg` (deleted), `ui/src/components/Welcome/Welcome.tsx` -- recompressed hashed import, matching `width`/`height` -- no hero fetch with an active deck; immutable when shown
- [x] `tests/unit/companion/test_routes_decks.py`, `test_routes_cards.py`, `test_routes_card_image.py`, `test_committed_schema.py`, `test_spa.py`, deck repository tests -- matrix rows -- proof
- [x] `ui/src/App.test.tsx`, `ui/src/state/cards.test.ts`, `deck.test.ts`, `Welcome.test.tsx`, `client.test.ts` -- matrix rows, request budget 7 → 5 -- proof
- [x] `ui/README.md`, `CHANGELOG.md` -- fan-out paragraph, release note -- docs
- [x] `npm run gen:api && npm run build`, `uv run python -m scripts.build_plugin` -- commit `openapi.json`, `types.d.ts`, `src/companion/app/static/`, `plugin/` -- CI drift checks
- [x] Measure `cdp_harness budget` before (base commit) and after (tip) on a quiet machine -- both medians + `requests_total`/`card_reads` in completion notes and PR body -- CAP-3 success

**Acceptance Criteria:**
- Given the committed `ui/src/api/openapi.json`, when `test_openapi_contract.py` and `test_committed_schema.py` run, then they pass and the `/api/deck/{deck_id}` 200 schema's `cards[].card` references `Card`.
- Given a quiet machine and a copy of the operator's data dir, when `cdp_harness budget` runs 5 times before and after, then the after median is at least 150 ms under 529 ms, `card_reads` is 0, and `requests_total` drops by about 100; both runs recorded.
- Given the preflight gate in `batches.md` (including `gen:api`, `build`, `build_plugin`), when run before the first push, then it is green and `git status --porcelain` is empty.
- Given `tests/integration/test_mcp_tools.py` and `tests/integration/mcp_server`, when run, then `load_deck`/`list_decks` payload shapes are unchanged.

## Spec Change Log

## Design Notes

**Additive deck shape, not an edit.** `DeckDetail.cards[].card` is `CardSummary` on purpose: `load_deck` payloads are LLM tokens. Brad's CAP-3 ruling ("embed full Card objects, schema change, no batch endpoint") is met by a sibling shape in `src/data/schemas` that only the companion route answers with; AD-1 holds because the shell still defines nothing. Consequence: `DeckDetail`, `DeckCardSummary`, `CardSummary` leave the companion OpenAPI components (nothing else on the wire uses them) — that is expected, not drift.

**Counts in SQL.** `mainboard_count = SUM(CASE WHEN NOT sideboard THEN quantity ELSE 0 END)`, `sideboard_count` likewise, `distinct_cards = COUNT(DISTINCT card_id)` (today's Python counts distinct ids across both boards — match it, and pin equality against `DeckSummary.from_deck` in a test). `COALESCE(..., 0)` for empty decks.

**Disk before row (AD-11 amendment).** The cache key is validated on write, so a warm read no longer needs the row. The cost is token fidelity for a deleted card with a warm tile (200 instead of 404) — accepted; the row is still consulted on every miss so no new key can enter the cache unvalidated.

**Booting surface.** `surfaceOf` order: `down` → `disconnected`; `deck.status === 'booting'` → `{kind:'booting'}`; `deck` → deck; `refused` → its panel; else `system.panel`. The left slot renders nothing for `booting`. No `StateKey` is added (the copy maps are total and a silent frame has no copy); `poller.ts` and `INITIAL_SYSTEM_STATE` keep `no-active-deck`.

**Seeding.** `seedDeckCards` writes `{status:'hydrated', card}` for every row; a row already `hydrated` from a newer generation is not overwritten. Agent-view ids outside the deck still go through `hydrateCard` (unchanged, one request each, now cacheable).

**Hero.** A one-off Pillow recompression committed as a source asset; no build-time image plugin (no new UI dependency). The `no-cache` root policy in `spa.py` is right for `index.html`/`favicon.svg` and stays.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run mypy src/ --platform win32` -- expected: clean
- `uv run pytest -m "not integration" -q` -- expected: green
- `cd ui && npm run lint && npm run format:check && npm run typecheck && npm test && npm run test:gates && npm run gen:api && npm run build && cd ..` -- expected: green; `openapi.json`, `types.d.ts`, `src/companion/app/static/` changed and staged
- `uv run python -m scripts.build_plugin && git status --porcelain` -- expected: only intended changes, then committed
- `uv run python -m scripts.cdp_harness budget --data-dir <copy> --deck-id 813d0434-1bed-4419-bf9d-d9e4070704c4 --runs 5 --json <out>` -- expected: before at the base commit, after at the tip; after median ≤ 379 ms, `card_reads` 0

**Manual checks (if no CLI):**
- Open the companion with an active deck in a real browser, Network tab, cold cache: one `/api/deck/{id}`, zero `/api/cards/`, zero `hero`; then clear the active deck and confirm the hero loads from `/assets/hero-<hash>.jpg` with an immutable cache header.

## Completion Notes

**Measurement (quiet machine, `cdp_harness budget --runs 5`, real data dir copy, deck
`813d0434-1bed-4419-bf9d-d9e4070704c4`, warm image cache).** Before was measured in a detached
worktree at the story's base commit `ea03141`; after at the tip. Both re-run once with nothing
else on the machine after a first pair showed a bimodal spread traceable to a concurrent test
run — the noisy pair is recorded below because discarding it silently would be the thing this
harness exists to prevent.

| Arm | layout min / median / max | `requests_total` | `card_reads` | format-check queue position |
|---|---|---|---|---|
| before (`ea03141`), quiet | 323 / **416** / 972 ms | 216 | 99 | 109 |
| after (tip), quiet | 129 / **139** / 142 ms | 116 | **0** | 9 |
| before, under load (first pair) | 432 / 436 / 595 ms | 216 | 99 | 109 |
| after, under load (first pair) | 134 / 681 / 938 ms | 116 | 0 | 9 |

Median drop **277 ms** against the base commit and **390 ms** against the SPEC's 529 ms quiet
baseline — both past the 150 ms target. `card_reads` is 0 and `requests_total` falls by exactly
100 (the 99 card reads plus the hero). The 116 that remain are ~99 image requests, the bundle, and
five JSON reads.

**The load arm's spread is the machine, not the change**, and it was checked rather than assumed:
the two routes were timed directly over a real socket in both trees, seven calls each.
`GET /api/decks` went **99 ms -> 3 ms** (the count-only query on 52 decks) and
`GET /api/deck/{id}` stayed at **7 ms** while its body grew from 47,237 to 253,026 bytes. In the
slow browser runs the *header* surface — which paints on the deck-detail settle — was itself
850-1330 ms in, which no 7 ms route can explain.

**What landed beyond the task list, and why.**

- `hydrateCard` now refuses to let a REFUSAL displace a `hydrated` entry at settle time. Seeding
  writes hydrated entries, so the ordinary "hover an unseeded id, the deck detail lands mid-flight,
  the read then 503s" sequence would otherwise overwrite a whole `Card` with an `unknown` entry and
  blank a drawable tile. `cards.test.ts` pins it.
- `seedDeckCards` skips a row without a usable `card_id` or without a `card` object. `deckOf`
  validates the envelope and not the rows, and a hydrated entry no consumer can read is worse than
  an unseen id.
- Every UI test fixture that built a deck row now builds a whole `Card`, including the six real
  MDFC Pathways' `card_faces` (shared with the card-route fixture through one `pathwayFaces`
  helper). A fixture still carrying the bounded summary would have left every flip control
  untested while the suite stayed green.

**Open / risky.**

- The hero is 1000x667 at quality 70 (146,219 B, under the 150 KB target). `Welcome.css` crops it
  to a 240px banner, so 1000px is 2x a ~500px column — but on a very wide window the banner is
  wider than that and the source is now the limit. Nothing measures banner width, so this is a
  judgement, not a measurement.
- `Schemas['CardSummary']` no longer exists, so the `CardSummary` alias in `ui/src/api/schema.ts`
  is now an alias of `Card`. The name was kept deliberately (the Code Map says repoint, not
  rename) and its docstring says so, but ~30 call sites read as narrower than they are. A rename
  is a large, purely mechanical diff and is left for whoever wants it.
- `test_the_list_route_loads_no_card_rows` asserts on the rendered SQL string. It is the honest
  instrument available (an absence of a second `SELECT` is what changed), but it is text about
  generated SQL and will need updating if SQLAlchemy changes how it renders the aggregate.

### Matrix coverage (step-3 audit, 2026-09-04)

| Row | Test |
|---|---|
| Deck list, mixed decks | `tests/unit/companion/test_routes_decks.py::TestDeckList::test_the_sql_counts_equal_the_python_counts_deck_for_deck`, `::test_the_list_route_loads_no_card_rows`; `tests/integration/data/test_deck_repository.py::test_list_deck_summaries_equals_the_python_projection`, `::test_list_deck_summaries_breaks_a_created_at_tie_by_id`, `::test_list_deck_summaries_honours_the_format_filter` |
| Deck list, no decks | `tests/integration/data/test_deck_repository.py::test_list_deck_summaries_is_empty_when_no_decks_exist` |
| Deck detail | `tests/unit/companion/test_routes_decks.py::TestDeckDetail::test_each_entry_nests_the_whole_card`; `::test_the_mcp_deck_shapes_are_untouched_by_the_wire_change` |
| Deck detail, unknown id | existing `TestDeckDetail` 404 case (unchanged, ran) |
| Card JSON | `tests/unit/companion/test_routes_cards.py::TestCardDetail::test_a_found_card_is_cacheable_for_an_hour` |
| Card JSON, unknown id | `…::test_a_missing_card_is_never_cached` |
| Warm image, row present | `tests/unit/companion/test_routes_card_image.py::TestTheWarmAnswerMatchesTheColdOne::test_a_warm_hit_consults_no_card_row` |
| Warm image, row deleted | `…::test_a_warm_tile_survives_its_card_row_being_deleted` |
| Cold image | existing `TestTheFourShapes`, `TestNoImagePrecedence`, `TestTheTwoFailuresAreDistinguishable` (unchanged, ran) |
| Image, DB unusable | `…::TestDatabaseStatesOutrankParameterValidation::test_a_bogus_size_against_an_absent_database_answers_503` (miss) and **`::test_a_warm_tile_against_an_absent_database_still_answers_503` (hit — added by the step-3 audit; the implementer's set covered only the miss)** |
| UI cold open, active deck | `ui/src/App.test.tsx` "renders NO panel and NO image on the first frame, with a deck coming", "fetches NO hero at all on a cold open that lands on a deck", "seeds the card cache HYDRATED and asks the card route for nothing (AC 17)" (request budget 7 → 5) |
| UI cold open, no active deck | `App.test.tsx` "renders nothing on the first frame with NO deck coming either — then the Welcome lands" (hashed `src` is pinned on the Python side, `test_spa.py`) |
| UI cold open, backend down | `ui/src/state/deck.test.ts` `surfaceOf` down-arm cases (booting deck + `down` → `disconnected`) and "shows NOTHING while booting, whatever the poller has decided" |
| UI, active-deck read fails | `deck.test.ts` "exits booting on EVERY settle path the boot has"; `App.test.tsx` "leaves booting on the refusal path too — a 503 boot shows its panel" |
| Agent view row outside deck | `ui/src/state/cards.test.ts` "carries a loading entry for an id OUTSIDE the deck, which is what a hover there does" |
| Hero asset | `tests/unit/companion/test_spa.py::test_the_hero_art_is_a_hashed_immutable_asset`, `::test_no_unhashed_hero_survives_at_the_bundle_root` |

Step-3 re-verification by the coordinator (same day): `ruff check` clean, `ruff format --check` 334 files clean, `mypy src/` and `--platform win32` clean, UI `npm test` / `typecheck` / `lint` / `format:check` all exit 0. Security files (`security.py`, `ws.py`, `body_cap.py`, `app/state.py`, `app/server.py`, `images.py`) are absent from the diff; `git diff` of `src/data/schemas/deck.py` removes no line. Branch `chore/quality-audit-cold-open`, everything staged, nothing committed; this story file is untracked.

### Greptile round 1 (PR #109, 2026-09-04)

Confidence 4/5, one P1 at `ui/src/state/cards.ts:431`: `seedDeckCards` skipped any entry already `hydrated`, so a deck refetch or reconnect after a reimport kept the first-read card record. Valid — the embedded `Card` is the server's current row and is never less fresh than the cache. Fixed at `23f500f`: the payload's card always wins; the "never downgrades" test became "REPLACES a hydrated entry with the payload's card — a refetch is never stale". UI gate, bundle, plugin and `test_spa.py` re-run green before the push.
