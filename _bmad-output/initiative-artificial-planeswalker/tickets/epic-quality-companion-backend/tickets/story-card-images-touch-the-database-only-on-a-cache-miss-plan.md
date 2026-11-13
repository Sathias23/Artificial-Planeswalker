---
title: 'Card images touch the database only on a cache miss'
type: 'bugfix'
ticket: '1'
created: '2026-11-13'
status: 'review'
baseline_revision: '4fc5aa2b6ea4a10ba331371b8164bcde12b5d678'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `GET /api/card-image/{id}` takes `DbSession`, so every request, warm disk hits included, runs the four-SELECT readiness probe and keeps a pooled connection checked out through the pacer wait and the CDN fetch (`M7`, research F5). `is_fetchable` reads `parts.port` outside its `try`, so `https://cards.scryfall.io:99999/x` escapes as `500` (`B12-P1`). The 16 MB ceiling counts decoded bytes after httpx has already inflated a gzip chunk (`B12-P3`). `_read_cached` buffers a whole file before its size check (`B12-P4`). `size` is typed `str` where containment relies on the `ImageSize` literal (`B12-P5`). Displaced siblings are unlinked before `os.replace`, so a failed replace deletes the only servable copy (`B12-P6`). A comment in `read_card_image` says "below" for a line above it (`B11-P10`).

**Approach:** The route stops taking `DbSession`. It reads the disk cache first. Only on a miss does it open a session through a context manager in `deps.py` (the same holder, the same probe and the same tokens `get_session` uses, which `get_session` now wraps), read the row, and close the session before the negative cache, the pacer and the fetch. The image client asks for `Accept-Encoding: identity`, the fetch counts raw wire bytes, and an encoded response is refused. Tests pin today's behaviour first, so the diff shows what moved.

**Decisions (from the intent, run straight through):** A warm hit touches nothing in the database, not even the file check. So a cached tile is served `200` while the database is absent, which flips `test_a_warm_tile_against_an_absent_database_still_answers_503`. The dependency-before-validation ordering no longer applies to this route, so `?size=bogus` answers `400` whatever the database state, which flips `test_a_bogus_size_against_an_absent_database_answers_503`. The `Warning:` paragraph on `read_card_image` is wire-visible, so it is corrected and `npm run gen:api` re-emits `openapi.json` and `types.d.ts`. A miss still runs the probe, so a schema-only database still answers `503 database_not_initialized`, not `404`.

## Boundaries & Constraints

**Always:** AD-2 (the companion only reads, and `test_import_boundary.py` stays green). Lazy `%`-style log args. No test reaches the network: use `httpx.MockTransport` through the `build_image_client` factory patch. Fixture databases come from `conftest.py` (`ready_db`, `image_shapes`, `_seed`, `_point_at`) over `tmp_path`. Each new guard is proved red through `uv run python -m scripts.probe_harness --expect-red '<node id>'`, with the tree staged before each plant and the revert checked with `git diff --exit-code <file>`. Rebuild `plugin/` after the `src/` change.

**Never:** No change to the other `DbSession` routes' behaviour, the pacer's constants, the negative-cache policy or the disk-cache layout. No in-flight coalescing. No `src/viewer/` change. No source-text scanning in tests. No other `epic-quality-companion-backend` story's findings (`B12-P2`, `B11-P3`/`P4`, and the rest).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Warm hit | key cached, database ready | `200` from disk; zero SQL statements; zero pool checkouts | none |
| Warm hit, fresh app | key cached, database absent or the engine never created | `200` from disk; `app.state.database.engine` stays `None` | none |
| Cold miss | key not cached | probe and `get_by_id` run, then the session is released; `pool.checkedout() == 0` while the request waits in the pacer or upstream | none |
| Bad port | row URL `https://cards.scryfall.io:99999/x` or `:abc` | `502 image_fetch_failed`, negative-cached | refusal, never `500` |
| Gzip bomb | CDN sends `content-encoding: gzip`, inflating past 16 MB | `502 image_fetch_failed`; peak traced memory stays under `_MAX_IMAGE_BYTES` | refused, never inflated |
| Outbound header | any fetch | request carries `Accept-Encoding: identity` | none |
| Oversized cached file | entry over the ceiling, or empty | a miss; `read_bytes` is never called for it | warning logged |
| Replace fails | `os.replace` raises a non-race `OSError` while a sibling under the other extension exists | sibling survives; the error is counted as before | swallowed by `DiskCache.write` |

</frozen-after-approval>

## Code Map

- `src/companion/app/routes/cards.py:244-339` -- `read_card_image`: drop `session: DbSession`; the disk read stays first; the row read moves inside the new context manager and is closed before `negative_cache`. Rewrite the `:312-333` comment block and the `Warning:` paragraph (`:275-280`, wire-visible) for the new ordering. `:380-384` says a remembered answer costs "a database session", which stays true for the session but not for its lifetime, so make it say the session is released first. `:459-466` "below" becomes "above" (`B11-P10`). `read_card` and its `Warning` stay as they are.
- `src/companion/app/deps.py:240-283` -- `get_session`; `:249-251` and `:29-30` "re-probed on every request"; `:286-312` the `DbSession` docstring lists the image route and "works by arithmetic". Add an `asynccontextmanager` (for example `ready_session(request)`) holding the body of `get_session`, and make `get_session` `async with` it and `yield`. Keep the missing-holder `internal_error` path.
- `src/companion/app/images.py:179-186` -- `is_fetchable` (P1). `:189-210` `build_image_client` headers gain `"Accept-Encoding": "identity"` (P3). `:896-916` count `response.aiter_raw()` and refuse a `content-encoding` other than absent or `identity` before reading the body (P3). Correct `_MAX_IMAGE_BYTES`'s docstring. `:358-398` `_read_cached`: `stat().st_size` (missing, empty, over the ceiling) before `read_bytes()`, keeping the post-read checks (P4). `:335`, `:358`, `:495-546`, `:698`, `:706-762` `size: str` becomes `ImageSize`, including the `_entries` key type (P5). `:401-465` `_write_atomically`: unlink `displaces` only after a successful `os.replace`, not on the lost-race return, and fix the docstring (P6).
- `src/companion/app/main.py:333` -- the cards router keeps `database_responses`; the image route can still answer both `503`s on a miss.
- `docs/companion.md:210` -- "Readiness is re-probed on every request" becomes "every request that reads the database".
- Tests: `tests/unit/companion/test_routes_card_image.py` (`TestDatabaseStatesOutrankParameterValidation` `:379`; `TestTheBurstDoesNotOutlastTheConnectionPool` `:1030`, whose docstring and tripwire describe the old hazard; `stalled_cdn` `:727`; `_until` `:695`; `Recorder.headers`), `tests/unit/companion/test_images.py` (`TestUrlAllowList` `:184`; `TestFetchImage` `:428-476`; the displacement test `:1209`; `TestACacheFailureIsNeverARequestFailure` `:1747-1786`, where `read_bytes` is monkeypatched), and `conftest.py` (`_card`, `_TOP_LEVEL_IMAGES`, `StallableUpstream`).

## Tasks & Acceptance

**Execution:**
- [x] Pin first (commit 1, green on baseline): add the missing pins for today's behaviour: a warm hit runs SQL (count the statements with a class-level `sqlalchemy.event` `before_cursor_execute` listener on `Engine`, removed in `finally`), a queued request holds a pool connection, the outbound request carries httpx's default `Accept-Encoding`, `is_fetchable` raises on a bad port, and a failed replace deletes the sibling. Mark each pin `PINNED (moves in 8.1)` and rewrite it in the commit that moves it.
- [x] `src/companion/app/deps.py` -- the context manager; `get_session` delegates to it; the docstrings say what is now true (the image route is not a `DbSession` route, and the pool paragraph is replaced by a one-line pointer to the route).
- [x] `src/companion/app/routes/cards.py` -- as in the Code Map.
- [x] `src/companion/app/images.py` -- P1, P3, P4, P5 and P6 as in the Code Map.
- [x] Tests (the matrix rows): statement count 0 on a warm hit; a fresh app's warm hit leaves `engine is None`; with `stalled_cdn` and six sizes, wait (`_until`) for six pool check-ins through instance-level `checkout`/`checkin` events on the pool (warm the engine first with `GET /api/cards/{ANCHOR_ID}`), then assert `checkedout() == 0`, four requested and none completed; a bad-port row through the route answers `502 {"reason": "image_fetch_failed"}`, plus both URLs in `TestUrlAllowList`; a gzip bomb through the route answers `502` with `tracemalloc` peak under `_MAX_IMAGE_BYTES`, and `Recorder.headers` shows `identity`; the oversized-cached-file test spies `Path.read_bytes`; the replace-failure test. Flip the two `TestDatabaseStatesOutrankParameterValidation` tests and keep the schema-only test. Rewrite `TestTheBurstDoesNotOutlastTheConnectionPool`: keep the 99-request burst and drop the pool-timeout tripwire.
- [x] `docs/companion.md:210`; `uv run python -m scripts.build_plugin`; from `ui/`, `npm ci` if needed, then `npm run gen:api` (the description changes) and `npm run format:check`.
- [x] Probe proofs (Design Notes), recorded in Implementation Notes as a table with the harness proof lines.

**Acceptance Criteria:**
- Given the finished branch, when the full Python gate runs, then `ruff check`, `ruff format --check`, both `mypy` platforms and `uv run pytest` are green, `test_import_boundary.py` included.
- Given `ui/`, when `npm run gen:types` runs after `gen:api`, then `git diff --exit-code ui/src/api` is clean, and the only change to `openapi.json` is the image route's description.
- Given each plant in Design Notes, when the harness runs with `--expect-red`, then it exits 0 naming the planted test, and `git diff --exit-code` on the planted file is clean afterwards.

## Implementation Notes

Commits on `fix/quality-8-1-image-cache-hit-no-db` over baseline `4fc5aa2`: `f98e04d` (five pins, green on baseline), `cb514e3` (fake CDN bodies streamed, green on baseline, see below), `33107b4` (the fix: `deps.py`, `routes/cards.py`, `images.py`, tests moved and added, `openapi.json`/`types.d.ts`, `plugin/`), `4b2003d` (`docs/companion.md`).

What was built:
- `deps.py`: `ready_session(request)`, an `asynccontextmanager` holding what `get_session` did (missing holder is `internal_error`, the lazy engine, the readiness probe, `database_not_initialized`). `get_session` is now `async with ready_session(request) as session: yield session`. The module docstring says "re-probed on every request that reads the database". The `DbSession` docstring no longer lists the image route; the two pool paragraphs are replaced by one paragraph pointing at `read_card_image`.
- `routes/cards.py`: `read_card_image` takes no `session`. The disk read is first; on a miss `async with ready_session(request)` wraps only `get_by_id`, so the session is closed before the negative cache, the pacer and the fetch. The `Warning:` paragraph (wire-visible) now says a cached image can be `200` while the database is unusable, other requests answer `503` until it is ready, and a bad id or `size` is `400` whatever the database state. The comment blocks at the disk read, the negative cache ("already closed by here") and the `below`/`above` fix (B11-P10) are updated. `read_card` and its `Warning` are unchanged.
- `images.py`: P1 `parts.port` read inside the `try`. P3 `Accept-Encoding: identity` on the client; a `Content-Encoding` other than `identity` (after strip and lowercase) is refused before the body is read; the body is counted from `aiter_raw()`; `_MAX_IMAGE_BYTES`'s docstring says so. P4 `_read_cached` checks `stat().st_size` (empty or over the ceiling is a miss, logged) before `read_bytes()`, and runs the same check on the bytes afterwards through one helper, `_is_servable_size`. P5 `size: ImageSize` on `_cache_path`, `_read_cached`, `DiskCache.path_for`/`read`/`write`, `NegativeCache.is_backing_off`/`record_failure`/`clear` and the `_entries` key. P6 `_write_atomically` unlinks `displaces` only after its own `os.replace` succeeds; the lost-race return unlinks nothing.
- `openapi.json`: the only change is the image route's `description` (the `Warning:` paragraph). `types.d.ts` re-emitted by `gen:types`.

The streamed fakes (`cb514e3`). `httpx.Response(content=b"...")` reads its body at construction, so a `MockTransport` handler built that way hands the client an already-consumed stream, and `aiter_raw()` raises `StreamConsumed` on it (measured: 70 route and unit tests went red on the first run of the fix). No network transport produces that shape. Rather than add a production fallback for a test double, `conftest.streamed(body)` (an async generator yielding the body once) now wraps the body in `Recorder.handle`, `StallableUpstream.handle` and the eleven bytes-bodied handlers in `test_images.py`. The commit was checked green against the baseline `src/` before the fix landed (259 passed in the two image files).

What moved (each pin rewritten with a `MOVED in 8.1` note; `git diff f98e04d..33107b4 -- tests/` is the record):
- Warm hit: three readiness-probe statements per warm tile (no `import_state` table in the fixture, so three, not four) -> zero statements and zero pool checkouts (`test_a_warm_hit_runs_no_sql_and_checks_out_no_connection`; the cold miss under the same listeners runs the probe and the row read on one checkout).
- Queued request: six requests in the route held six connections -> zero held, six check-outs and six check-ins, while four sit upstream and two at the pacer, none completed (`test_a_request_queued_at_the_pacer_holds_no_pool_connection`).
- Outbound `Accept-Encoding`: `gzip, deflate` -> `identity`.
- `is_fetchable("https://cards.scryfall.io:99999/x")` and `:abc`: `ValueError` -> `False`.
- Failed non-race replace: the `.jpg` sibling deleted and the key unreadable -> sibling kept and served, failure still counted (`_consecutive_write_failures == 1`).
- Flipped: `?size=bogus` against an absent database `503` -> `400`; a warm tile against an absent database `503` -> `200` from disk with `app.state.database.engine is None`, and a cold key on the same app still `503 database_not_initialized`. The schema-only test is unchanged and green. The class is renamed `TestTheDatabaseIsConsultedOnlyOnACacheMiss`.
- `TestTheBurstDoesNotOutlastTheConnectionPool`: the 99-request burst is kept; the tripwire (`99 * FETCH_SPACING_SECONDS < pool._timeout / 2`) and the three pool-constant assertions are dropped; the class docstring records the fix.
- New: the route bad-port test (two sizes, `502 image_fetch_failed` each, no request, two negative-cache entries); the gzip-bomb route test (17 MB of zeros gzipped to ~17 KB, `502`, `tracemalloc` peak under `_MAX_IMAGE_BYTES`, the request carried `identity`); unit tests for the encoding refusal (five codings, read unread), `identity` accepted, and the `identity` header; the `read_bytes` spy on the empty and oversized cached-file tests, a non-vacuity spy test, and a grown-after-`stat` test for the post-read check.

One measurement caveat in the pool test. Six concurrent sessions need one overflow connection (pool size 5). When it is returned to a full queue SQLAlchemy closes it, and closing an aiosqlite connection awaits its worker thread, so `checkedout()` read 1 for a turn or two after the sixth `checkin` event (measured: `Connections in pool: 5  Current Overflow: 1`). The test waits (`_until`) for `checkedout() == 0` while every image is still parked upstream, then asserts it.

Probe proofs. The tree was committed before planting. A driver applied each plant alone, ran `uv run python -m scripts.probe_harness --expect-red '<node id>'`, restored the original bytes, then ran `git diff --exit-code <file>`.

| # | Plant (file) | Proof line | Expected RED (node id) | harness exit | `git diff --exit-code` |
|---|--------------|------------|------------------------|--------------|------------------------|
| 1 | the route reads the row before the disk cache (`routes/cards.py`) | `full suite (-m 'not integration'): 3672 collected, 4 failed, 0 errored, exit 1` | `TestTheWarmAnswerMatchesTheColdOne::test_a_warm_hit_runs_no_sql_and_checks_out_no_connection` (also `test_a_warm_hit_consults_no_card_row`, `test_a_warm_tile_against_an_absent_database_is_served_from_disk`, `test_a_request_queued_at_the_pacer_holds_no_pool_connection`) | 0 | 0 |
| 2 | `session: DbSession` restored on `read_card_image` (`routes/cards.py`) | `full suite (-m 'not integration'): 3672 collected, 5 failed, 0 errored, exit 1` | `TestTheBurstDoesNotOutlastTheConnectionPool::test_a_request_queued_at_the_pacer_holds_no_pool_connection` (also both flipped ordering tests, the warm-hit SQL test, and the 99-request burst) | 0 | 0 |
| 3 | `parts.port` back outside the `try` (`images.py`) | `full suite (-m 'not integration'): 3672 collected, 3 failed, 0 errored, exit 1` | `TestTheOutboundRequest::test_a_row_with_a_port_that_will_not_parse_is_a_fetch_failure_not_a_500`, `TestUrlAllowList::test_a_port_that_will_not_parse_is_refused_not_raised[...:99999/x]` and `[...:abc/x]` | 0 | 0 |
| 4 | the `identity` header dropped (`images.py`) | `full suite (-m 'not integration'): 3672 collected, 3 failed, 0 errored, exit 1` | `TestTheOutboundRequest::test_the_request_asks_for_an_unencoded_body` (also the unit header test and the gzip-bomb test, which checks the header) | 0 | 0 |
| 5 | `aiter_bytes` back and the encoding refusal removed (`images.py`) | `full suite (-m 'not integration'): 3672 collected, 6 failed, 0 errored, exit 1` | `TestTheOutboundRequest::test_a_gzip_bomb_is_refused_without_being_inflated` (also the five `test_an_encoded_body_is_refused_before_it_is_read` cases) | 0 | 0 |
| 6 | `_read_cached` reads before the size check (`images.py`) | `full suite (-m 'not integration'): 3672 collected, 2 failed, 0 errored, exit 1` | `TestACacheFailureIsNeverARequestFailure::test_an_oversized_entry_is_a_miss_not_a_served_body`, `::test_a_truncated_entry_is_a_miss_rather_than_an_empty_picture` | 0 | 0 |
| 7 | displaced siblings unlinked before `os.replace` (`images.py`) | `full suite (-m 'not integration'): 3672 collected, 1 failed, 0 errored, exit 1` | `TestTheCacheReadAndWrite::test_a_failed_replace_leaves_the_sibling_servable` | 0 | 0 |

Plant 2 also reddens the 99-request burst. With the parameter restored each request holds two sessions (the dependency's and `ready_session`'s), so 99 concurrent requests can hold all 15 connections while each waits for a second. That is the plant's artefact, not a property of the fix.

P5 (type guard), `mypy src/` with `cache.read(scryfall_id, str(size), face)` planted in `routes/cards.py`, then restored (`git diff --exit-code` 0): `src\companion\app\routes\cards.py:338: error: Argument 2 to "read" of "DiskCache" has incompatible type "str"; expected "Literal['small', 'normal', 'large', 'png', 'art_crop', 'border_crop']"  [arg-type]`.

Gates (finished branch, `4b2003d`): `ruff check .` and `ruff format --check .` clean; `mypy src/` and `mypy src/ --platform win32` no issues (97 files); `uv run pytest` 3697 passed, 2 skipped (`test_import_boundary.py` included). From `ui/` (after `npm ci`): `npm run gen:api` changed only the image route's `description` in `openapi.json`; `npm run gen:types` then `git diff --exit-code ui/src/api` clean after commit; `npm run format:check` clean. `uv run python -m scripts.build_plugin` gives no drift.

Residue and risks for review:
- A warm tile is served while the database is absent or broken (AD-11 already accepted the deleted-row case; this widens it to the whole database). The SPA's database-state panel comes from the other routes, so a deck view can show cached art beside a "not set up" panel. Intended by the Decisions paragraph; worth a look in the browser.
- Between a successful replace and the sibling unlink, a reader can briefly see the older extension (`.jpg` is probed first). It is the same stale-picture class AD-11 accepts, and lasts one unlink.
- An upstream that ignores `identity` and gzips anyway now always fails (`502`, negative-cached). Scryfall's CDN serves images unencoded today; if that changes, every cold tile fails loudly rather than silently inflating.
- The streamed-fake change touches every image fake in the package; a future fake built from a bare `bytes` body will fail with `StreamConsumed`, and the `conftest.streamed` docstring says why.

## Plan Change Log

## Review Triage Log

Pass 1 (lens `quick`, 2026-11-13): 6 findings — high 0, medium 0, low 5, false 0, maybe-false 0, plus 1 rejected as a plan edit. Four **patch**, two rejected, none deferred; no loopback. The lens read the diff without `plugin/` (a generated copy; it checked the three companion files are byte-identical to `src/`).

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | `_read_cached` still calls an unbounded `read_bytes()`, so a file that grows between `stat` and the read is buffered whole before the post-read check rejects it | low | rejected | Real, but only a file that is growing under the cache root while being read reaches it. B12-P4 asked for exactly the `stat` check before `read_bytes()`, and that check is in. A bounded `open().read(n)` would also mean reworking the `read_bytes` spy and explode tests. Unlikely in everyday use, and the fix is more than a direct correction. |
| 2 | `read_card_image`'s `Raises:` names `database_not_initialized` for a miss but omits `database_unavailable`, which a `DatabaseError` inside `ready_session` answers, while the `Warning:` names both | low | patch | Verified: `errors.database_error_handler` answers it. The line now names both. `Raises:` falls after the wire cut, so `gen:api` leaves `openapi.json` unchanged. |
| 3 | `main.py:323` says `database_not_initialized` "is a property of `deps.get_session`, so every data route inherits it", but the image route now reaches `ready_session` directly | low | patch | Verified, and caused by this change. The comment now names `ready_session` and both ways in. `errors.py:89` (`get_session` as a dependency that raises the token) is still true, because `get_session` wraps `ready_session`, so it is left alone. |
| 4 | Probe-table row 1 lists the pool test among its reds without explaining why | — | rejected | The fix would be an edit to this build's plan, which triage rejects. The plant reddened its own target test (`test_a_warm_hit_runs_no_sql_and_checks_out_no_connection`); the extra red does not weaken that proof. |
| 5 | `TestACancelledRequestIsNotAFailure`'s docstring breaks a sentence mid-line | low | patch | Verified. Reflowed to the 100-column limit. |
| 6 | `test_a_warm_hit_runs_no_sql_and_checks_out_no_connection`'s message on `len(cdn.requested) == 2` blames only the warm request | low | patch | Verified: the count is the cold fetch plus the `size=large` miss. The message now names both ways the count can be wrong. |

After the patches: `ruff check .` and `ruff format --check .` clean; `mypy src/` and `mypy src/ --platform win32` no issues; `uv run pytest` 3697 passed, 2 skipped; `scripts.build_plugin` rebuilt `plugin/`; `npm run gen:api` gives no drift; `npm run format:check` clean.

### Pass 2 (Greptile on PR #134)

| # | Finding | Severity | Action | Reason |
|---|---------|----------|--------|--------|
| 1 | Two overlapping cold writes of one key under different extensions can both replace before either unlinks, then each delete the other's fresh file | P2 | patch | Verified, and introduced here: unlinking after the replace (P6) opened the window, while the old unlink-first order always left one file. Impact is one refetch. `_write_atomically` now holds a process-wide `_REPLACE_LOCK` across the replace and the sibling unlinks, so the later writer's entry survives. One lock rather than one per key: the held section is a rename plus at most one unlink, and the companion is a singleton process. New test `test_overlapping_writes_under_different_extensions_leave_the_later_entry` starts the PNG writer the moment the JPEG's replace lands. |

Proof (plant: `with _REPLACE_LOCK:` replaced by `with suppress():`; harness exit 0, `git diff --exit-code` clean after the revert):

```
full suite (-m 'not integration'): 3673 collected, 1 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_images.py::TestTheCacheReadAndWrite::test_overlapping_writes_under_different_extensions_leave_the_later_entry
```

## Design Notes

**Why refuse an encoded body rather than decode it under a bound.** With `identity` requested, a conforming server sends raw bytes. A server that encodes anyway is misbehaving, and decoding under a bound would need a decoder per coding. So `aiter_raw` with the refusal means wire bytes equal served bytes, and the existing ceiling bounds both. The declared `Content-Length` check stays, since it now counts the same bytes.

**Why the miss still probes.** Without the probe, a schema-only or empty database answers `404 card_not_found`, a permanent token for a transient state. The probe now costs four SELECTs once per cold tile, ahead of a 0.1 s paced fetch.

**Plants** (one guard broken each, all reverted): (1) the route reads the row before the disk cache (statement-count test); (2) the session is held across the fetch, with the row read moved back to `DbSession` or the `async with` widened over the fetch (pool check-in test); (3) `parts.port` back outside the `try` (route bad-port test and the `TestUrlAllowList` cases); (4) the `identity` header dropped (header test); (5) `aiter_bytes` back with the encoding refusal removed (gzip-bomb route test); (6) `_read_cached` reads before the size check (spy test); (7) unlink before replace (replace-failure test). P5 is a type guard, so its proof is a `mypy src/` run with a plant (`size=str(size)` passed to `cache.read`), with the error line recorded, because the harness runs pytest only.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- all green
- `uv run python -m scripts.build_plugin` then `git status --short plugin/` -- committed, no drift
- from `ui/`: `npm run gen:api`, `npm run gen:types`, `npm run format:check` -- `openapi.json` and `types.d.ts` committed, no drift
- the probe harness, once per plant -- the proof lines are in Implementation Notes
