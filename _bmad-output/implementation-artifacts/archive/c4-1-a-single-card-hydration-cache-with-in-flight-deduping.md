---
epic: c4
story: c4-1
work_branch: feat/companion-c4
story_branch: feat/companion-c4-1-hydration-cache
depends_on: Epic C3 in full (merged to master via PR #39 at `eb3f20a`) — but the load-bearing dependencies are **c3-9**, which shipped `src/api/decks.ts` and the `src/state/` slice as *the seam this story extends*, **c3-2** (`GET /api/cards/{card_id}`), and **c3-1** (`GET /api/deck/{deck_id}`, whose response already carries a `CardSummary` per card — read §"What the real data says" before designing anything)
baseline_commit: 61a787a
---

# Story C4.1: A single card-hydration cache with in-flight deduping

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer building every card-rendering surface,
I want one owner for card lookups in the store,
so that sweeping a cursor across a hundred tiles doesn't fire a hundred duplicate requests for cards already in memory.

**What this story really is.** It is the first story of the largest UX surface in the feature, and
it ships **no pixels**. Its whole product is a store slice and a request path that eleven later
stories consume without opening again. Five facts about it are not what the title suggests, and the
first one changes the design:

1. **The deck response already hydrates every card, partially.** `GET /api/deck/{deck_id}` returns
   `DeckDetail`, whose `cards` is a list of `DeckCardSummary`, each of which **embeds a full
   `CardSummary`** — id, name, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `rarity`,
   `set_code` (`src/data/schemas/deck.py:275-281`). Measured on the largest real deck on this
   machine (99 distinct tiles): the `CardSummary` fields are **38,182 bytes**, and they arrive in
   the **one** request c4-2 already makes. The full `Card` rows for the same 99 cards are
   **212,436 bytes** — **5.6×** — and would cost **99 requests**. **So "hydrate the grid" is not
   this story's job, and building it would be 99 requests for data that already arrived.**

2. **The UX artefact states the two-tier contract in one sentence, and it is the design.**
   `EXPERIENCE.md`'s Card detail panel row: *"Content hydrates from `GET /api/cards/{card_id}` +
   `GET /api/card-image/{scryfall_id}?size=large`; **name and cost are known at hover time and
   render immediately, the rest fills in place — no spinner**."* "Known at hover time" **is the
   `CardSummary` from the deck payload**. The full `Card` — power, toughness, legalities,
   `card_faces`, `set_name`, `collector_number` — is what `GET /api/cards/{card_id}` adds. The
   cache therefore has **three** per-id conditions, not two, and the epic's own AC asks for exactly
   that distinction: *"consumers can distinguish 'unknown card' from 'still loading'"*.

3. **Images are not this cache's business, and building a byte cache for them is the most likely
   wrong turn.** Art reaches the screen through `<img src="/api/card-image/…">` — the browser's own
   HTTP cache, backed by `IMAGE_CACHE_CONTROL = "public, max-age=31536000, immutable"`
   (`images.py:167`) and, on the server, c3-7's sharded disk cache. There is **no `fetch` for image
   bytes anywhere in this story.** The one image concern that *is* this story's is the failure
   token (`no_image_data` / `image_fetch_failed`), and even that is **c4-3's** render — see AC 14.

4. **There is a guard that will fail on the obvious file layout, and it names this story in its own
   assertion.** `ui/tests/posture.test.ts:318` asserts `doors).toEqual(['src/api/decks.ts'])` —
   exactly one module in `ui/src` may contain a `fetch(`. Its comment reads *"**c4-1 adds routes to
   this module**; a second `fetch` anywhere else is a second spelling of the same thing and fails
   here rather than in review."* A new `src/api/cards.ts` is a **red test**, not a review comment.
   **Q1 rules this**, and whichever way it goes, the guard and `ui/README.md` are edited in the same
   commit.

5. **The per-card routes are NOT retry-safe, and c3-9 wrote the warning in three places expecting
   this story to walk into it.** Measured at c3-2 and pinned in `test_routes_cards.py`: a malformed
   id sent to a backend with no database answers **`database_not_initialized`, not
   `invalid_request`**, because FastAPI solves dependencies before it collects parameter-validation
   errors. `/api/decks` is immune **structurally** — it has no path parameter. `/api/cards/{card_id}`
   is not. **A retry loop copied from `poller.ts` retries a request whose id can never succeed,
   forever.**

**Everything numeric in this story was measured on this machine at `61a787a`, read-only, against
the live database at `%LOCALAPPDATA%\artificial-planeswalker\cards.db` and the installed toolchain.
Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **`src/api/decks.ts` is the ONE door to the network, and its shape is the shape to extend.**
   `readDecks()` returns a **total outcome union** — `{kind:'decks'}` | `{kind:'error', reason}` |
   `{kind:'unreachable'}` — and **never rejects**. Four failure inputs (a non-2xx with no body, a
   body that is not JSON, a body with no `reason`, a network rejection) are four distinct values in
   that union. Its header states the ruling: *"this module is the seam c4-1 EXTENDS, not a throwaway
   c4-1 replaces… **the deduping goes around it**, not through it."* A card read that throws, or
   that returns `null`, is a second contract in one file.

2. **`src/state/` holds the store, and it is one `create<T>()` with no middleware.**
   `systemState.ts` is `create<SystemState>(() => INITIAL_SYSTEM_STATE)` plus a `useSystemState()`
   hook that owns the poller's lifetime in a `useEffect`. Its header says *"**c4-1 extends this
   store; it does not replace it.** The card cache and the in-flight deduping are new slices beside
   this one."* **AD-12: no second data-fetching or state-management library joins zustand** — no
   TanStack Query, no SWR, no Redux, no Jotai — and `ui/tests/package-contract.test.ts` enforces it
   against `package.json`, so it is a red test rather than a review note.

3. **`useSystemState`'s "one consumer" rule is a rule, and this story is where it gets tested.**
   Its docstring: *"**`App` is the ONE consumer, and that is a rule, not an observation.** Every
   mounted caller creates its OWN poller… A future component that needs this state reads
   `useSystemStore` directly and lets the root keep the poll."* Whatever hook this story exports for
   card reads must not repeat the poller's mistake in a new costume: **N mounted tiles must not
   create N request owners.**

4. **`panel.ts` is the one place a wire token becomes a `StateKey`, and it is total over every
   string.** `panelFor(reason: string | null): StateKey` uses `Object.hasOwn(PANEL_FOR_REASON, …)`
   deliberately — *"a wire string is attacker-adjacent input by construction"*. A card read's
   `reason` does **not** go through it: `card_not_found` maps to `null` in `PANEL_FOR_REASON`, which
   `panelFor` would turn into `'internal-error'` — **a whole-screen error panel for one missing
   card, which is the exact FR-13 failure `states.ts` spends a paragraph banning.** See AC 13.

5. **`states.ts` already decided what a card token means, and the decision is not a panel.**
   `PLACEHOLDER_FOR_REASON` (`states.ts:166`) maps `card_not_found → 'unknown-card'`,
   `no_image_data → 'named-card'`, `image_fetch_failed → 'named-card'`. `NO_UI_RESPONSE`
   (`states.ts:182`) holds `invalid_request`, `forbidden`, `payload_too_large`. Three type-level
   asserts prove the classification is a **set equality**. **Consume these; do not write a `switch`
   and do not add a fourth vocabulary.**

6. **The wire types are generated and `src/api/schema.ts` is the only door to them.** It exports
   **four** aliases today — `HealthResponse`, `ErrorResponse`, `DeckSummary`, `ErrorReason`.
   `ui/tests/wire-contract.test.ts` derives its ban from `components.schemas`, so **`Card`,
   `CardSummary`, `CardFace`, `DeckDetail` and `DeckCardSummary` are all banned type names anywhere
   in tracked TypeScript outside `src/api/`**, and importing `./types` directly is banned too. This
   story is the ledgered home for adding the aliases (see AC 3).

7. **`error_responses` is per-include and already declares what a card read can answer.**
   `GET /api/cards/{card_id}` publishes `card_not_found` (404) plus the app-wide set —
   `invalid_request` (400), `payload_too_large` (413), `database_not_initialized` /
   `database_unavailable` (503), `internal_error` (500). The 413 on a body-less GET is a **known
   wart, ruled and re-homed on c5-5** (deferred-work, c3-2 round 2); the generated contract still
   offers it to this story's fetch layer. Handle it as an unremarkable member of the token union —
   `states.ts` classifies it `NO_UI_RESPONSE` — and do **not** curate it here.

8. **The two vitest projects are already split, and the split has a `tsc` trap in it.**
   `src/**/*.test.{ts,tsx}` → **jsdom**; `tests/**/*.test.{ts,tsx}` → **node**.
   `ui/tests/gate-geometry.test.ts` forbids `.tsx` test files under `tests/`. **The trap** (ledgered
   on this story): importing a real `src/` module from `ui/tests/` pulls it into the node project,
   where its extensionless relative imports become `TS2835` and **cascade** into unrelated-looking
   errors — and `npm test` stays fully green throughout, because it is a `tsc`-only failure that
   `tsc -b`'s incremental cache can hide. **`npx tsc -b --force` is what makes it deterministic.**

### What the real data says (measured at `61a787a`, read-only)

**The corpus and the decks.**

| Property | Measured |
| --- | --- |
| Cards in the shipped database | **38,261** |
| Cards with a `card_faces` array | **3,225** |
| Cards with **no image anywhere** (no `image_uris` *and* no face carries one) | **79** |
| Saved decks | **40** |
| `deck_cards` rows in total | **2,027** |
| **Distinct card ids across all 40 decks** | **1,061** |
| Non-canonical `card_id` values in `deck_cards` | **0** |
| Dangling `deck_cards → cards` references | **0** |

**The largest real deck — "Atraxa Counter Cabinet v2 (owned)", the 100-tile grid the epic AC
describes, and it exists.**

| Property | Measured |
| --- | --- |
| Distinct card ids (**= tiles**) | **99** |
| Total quantity | **100** |
| Double-faced cards in it | **6** |
| Cards with no image at all | **0** |
| Full `Card` payload for all 99 | **212,436 bytes** (**2,146**/card) |
| The `CardSummary` fields for all 99 | **38,182 bytes** (**386**/card) |
| Ratio | **5.6×** |
| Requests to obtain the summaries | **1** (the deck detail c4-2 already fetches) |
| Requests to obtain the full rows | **99** |

**Read the last two rows together. They are the whole argument of Q2.**

**The frontend, today.**

| Property | Measured over `ui/src` (tracked `.ts`/`.tsx`, excluding `*.test.*`) |
| --- | --- |
| `fetch(` call sites | **1** — `src/api/decks.ts:154`, and `posture.test.ts` pins the file list exhaustively |
| Hook call sites | **3** — `App.tsx:71`, `systemState.ts:62` (`useEffect`), `systemState.ts:71` |
| `zustand` imports | **1** — `systemState.ts:32` |
| Timers | **1** — `poller.ts:201` (`setTimeout`) |
| Components with an on-screen consumer | **2 of 8** — `StatePanel`, `Footer` |
| Aliases exported by `src/api/schema.ts` | **4** |

**The gate baseline (verify it yourself in Task 0; do not trust this table).**

| Gate | Measured at `61a787a` |
| --- | --- |
| `npm test` | **731 passed, 36 files**, 4.05 s |
| `uv run pytest -m "not integration"` | **2,447 passed, 1 skipped, 54 deselected**, 143.29 s — measured on this branch, not inherited from the retro |
| `npm run lint` / `format:check` / `npx tsc -b --force` / `npm run build` | green |

## Acceptance Criteria

### The cache, and the one thing it is for

1. **Exactly one card cache exists in the store, and it is keyed by the Scryfall printing uuid.**
   One slice, one owner, `card_id` as the key — the same identifier `deck_cards.card_id`,
   `GET /api/cards/{card_id}` and `GET /api/card-image/{scryfall_id}` all carry (AD-12, and the
   spine's *"Card identity is the **Scryfall printing UUID**, everywhere, always"*). A second cache
   keyed by oracle id, by name, or by anything else is the failure this AC exists to prevent.

2. **No component fetches card data directly.** After this story there is still exactly **one**
   module in `ui/src` containing a `fetch(`, and `ui/tests/posture.test.ts`'s network-door
   assertion is **still exhaustive and still green** — whether that means the list is unchanged or
   the list plus the guard's comment are edited together is Q1's call, but the property "one door,
   asserted by name" survives this story unweakened.

3. **The wire aliases this story needs are added to `src/api/schema.ts`, and nothing re-declares
   them.** `Card`, `CardSummary`, `CardFace`, `DeckDetail` and `DeckCardSummary` are banned type
   names everywhere in tracked TypeScript outside `src/api/` — the ban is *derived* from
   `components.schemas`, so it grew on its own when c3-2 and c3-1 landed. Add the aliases the
   story's own code needs, **each with a docstring naming its consumer**, and add **no alias that
   has no consumer in this commit** (an unused export is dead code, and c3-2 declined to add these
   for exactly that reason). `ui/tests/wire-contract.test.ts` stays green with no edit.

### The three conditions a card id can be in

4. **The cache distinguishes *unknown*, *summary-known* and *fully hydrated*, and consumers can
   read the difference** (epic AC; `EXPERIENCE.md`'s *"name and cost are known at hover time…
   the rest fills in place — no spinner"*). "Still loading" and "unknown card" are **not** the same
   value and must not be inferred from `undefined`. A consumer holding a summary must be able to
   render name, cost and type line **without** waiting for a request, and must be able to tell that
   the full record has not arrived yet.

5. **Seeding the cache from a deck payload is free and does not issue a request.** Handing the
   cache the `DeckCardSummary[]` from `GET /api/deck/{deck_id}` populates the summary tier for
   every id in it, issues **zero** requests, and leaves each id's hydration tier untouched. This is
   the mechanism that makes the measured 5.6× / 99-request cost in §"What the real data says" a
   cost this app never pays. **c4-2 calls this; this story ships and tests it.**

6. **A full hydration is requested only when something actually needs the full record**, never
   eagerly for a whole deck. AC 5's seeding is not a hydration, and nothing in this story walks a
   deck issuing per-card reads.

### Deduping, which is the story's title

7. **Two simultaneous requests for the same uncached id produce ONE request, and both callers
   receive its result** (epic AC, AD-12). The in-flight promise is shared, not the result copied —
   and it is keyed by id, so two *different* ids still make two requests.

8. **An already-hydrated id is never re-requested.** A second read of a hydrated id makes no
   request at all.

9. **The 100-tile sweep is measured, not asserted.** A test drives a cursor sweep across a
   **99-id** working set **twice** and counts the requests: each distinct id is fetched **at most
   once**, over both sweeps. Use the real number — 99 is the largest deck on this machine, measured,
   and the epic's "100-tile grid" is not a round figure someone invented.

10. **The in-flight entry is released on every outcome — success, refusal and network rejection
    alike.** A permanently-pending entry after a failed read is the bug this AC exists to catch: it
    is invisible to a success-path test and turns one bad request into an id that can never be read
    again. Prove the release on all three outcomes.

### The refusals, and the retry trap c3-9 wrote down for this story

11. **`404 card_not_found` marks the id unknown, and it is not re-requested on every render**
    (epic AC, FR-13). The negative answer is remembered. Whether it is remembered *forever* or with
    an expiry is **Q4**; whatever is chosen, "re-requested on every render" is out.

12. **A per-id read has a BOUND ON ATTEMPTS, and the bound is not derived from the token alone.**
    This is the trap: a malformed id reaching a backend with no database answers
    `database_not_initialized` — a token `RETRIES_QUIETLY` says to retry quietly — and the request
    can never succeed. Measured at c3-2, pinned in `test_routes_cards.py`, and written into
    `decks.ts`'s header, `ui/README.md` and `deferred-work.md` **because this is the story that
    would walk into it**. A test must prove the loop terminates for an id that answers `503`
    forever.

13. **A card-read refusal NEVER puts a state panel on the glass.** `panelFor()` is not called on a
    card outcome. `card_not_found` maps to `null` in `PANEL_FOR_REASON`, and `panelFor` clamps
    `null` to `'internal-error'` — so routing a card refusal through it would replace a working deck
    view with *"The companion hit a bug"* because one card was missing. That is the FR-13 failure
    `states.ts:98-104` names outright (*"No banner, no apology"*). Prove it: a `card_not_found` on
    one id leaves the system panel untouched.

14. **The token reaches the consumer intact; the placeholder is c4-3's.** The cache records *which*
    reason refused an id, using the vocabulary already in `states.ts` — it does not invent a second
    one, and it does not render anything. `no_image_data` and `image_fetch_failed` are **image**
    tokens and can never be answered by `GET /api/cards/{card_id}`; do not handle them here.

15. **The malformed-id-from-data case is decided, not discovered** (ledgered on this story,
    Medium). A `card_id` that fails the route's shape gate answers `400 invalid_request`, which
    `states.ts` classifies `NO_UI_RESPONSE` — *nothing on the glass, anywhere* — one character of
    input away from `card_not_found`'s placeholder. Measured today: **0 of 2,027** `deck_cards` rows
    are non-canonical, so this is latent, not live. **Decide it here** (Q5): either the cache treats
    a `400` on a card read as a placeholder case, or it is explicitly declined with the reason
    written down. Not deciding is not an option — this AC exists because the ledger homed it here.

### Boundaries — what this story must not do

16. **This story renders nothing.** No component, no CSS, no copy, no `EXPERIENCE.md` string. A new
    user-facing sentence here is a signal that scope has slipped: the grid is **c4-4**, the
    placeholders are **c4-3**, the detail panel is **c4-5**, the deck bootstrap is **c4-2**.
    `ui/tests/copy-rules.test.ts` will fail on prose in a non-copy module regardless.

17. **This story does not fetch a deck.** `GET /api/deck/{deck_id}`, `GET /api/active-deck` and the
    boot sequence are **c4-2's**. AC 5's seeding takes deck cards as an **argument**; it does not go
    and get them.

18. **This story does not fetch image bytes.** See §"What this story really is" item 3. `<img>` +
    the browser's HTTP cache is the mechanism, and it is already built and already measured
    (~99 ms/image cold, ~10.3 ms warm, 8.5 MB for a 99-card deck — C3 retro Block B).

19. **`AppShell.tsx` and the eight primitives are untouched.** `ui/tests/shell.test.ts` pins their
    imports as **exhaustive lists** and bans hooks, `fetch(` and `WebSocket(` in each. A store
    import added to any of them is a red gate, and rightly: those components are presentation-only
    by a decide-once ruling ~20 stories inherit.

20. **`App.tsx` does not become the second network door.** `posture.test.ts:321-334` asserts it
    directly, in both directions — it must not match the network family, and it must still match
    `useSystemState(`, so the guard is a boundary rather than a ban on a file that does nothing.

21. **No second state or data-fetching library, and no second code generator.** Asserted by
    `ui/tests/package-contract.test.ts` against `package.json`. If this story adds a dependency at
    all, the addition is argued in the story record, not just installed.

### The generated artifacts and the mirror

22. **If any Pydantic model changes, `npm run gen:api` runs and both generated files are committed
    together.** This story is not expected to change one — it consumes contracts that already ship —
    and if it turns out to need one, that is a finding worth writing down, not a quiet edit.
    A commit with a fresh `openapi.json` and a stale `types.d.ts` is red in CI.

23. **The SPA bundle and the `plugin/` mirror are rebuilt and their change is MEASURED, not
    assumed.** `npm run build` writes into `src/companion/app/static/` — **it mutates `src/`** — and
    `scripts/build_plugin.py` regenerates the mirror; CI drift-checks both. Record the before/after
    hashes. This story changes `ui/src`, so **the bundle is expected to change**; a story that
    reports "byte-identical" here has probably not built.

### Testing

24. **Every AC above has a test, and the tests live in the project that can see what they assert.**
    Store and fetch-layer tests are colocated under `src/` (jsdom project, no configuration needed);
    guard tests belong in `ui/tests/` (node project) and must respect the `tsc -b` cross-project
    import trap in §"The seam" item 8 — if this story imports a real app module from `ui/tests/`,
    it must run **`npx tsc -b --force`** and record the result, because that is the ledgered home
    for the trap and `npm test` will not show it.

25. **The request count is the assertion, not the bytes.** Deduping is a claim about how many
    requests were issued. Every dedupe AC (7, 8, 9, 10) asserts a **count** from an injected
    reader — following `poller.ts`'s `read?: () => Promise<DecksOutcome>` injection, which exists
    precisely so tests need no global `fetch` stub.

26. **Evasion probes, in the manner this epic has established.** For each new guard or contract
    this story ships, write the probe that *should* defeat it and prove it does not. C2 and C3 both
    found real holes this way — c2-9 found two in its own guard by probing it. At minimum, probe:
    (a) a second `fetch(` added to a new module; (b) two callers racing the same id; (c) an id that
    refuses forever; (d) a cache entry left in-flight after a rejection.

27. **All five frontend gates and all five Python gates are green at the end, with counts recorded
    before and after.** `npm run lint`, `format:check`, `npx tsc -b --force`, `npm test`,
    `npm run build`; `uv run pytest`, `ruff check`, `ruff format --check`, `mypy src/`,
    `mypy src/ --platform win32`. The Python side should be **unchanged** — say so explicitly if it
    is, and investigate if it is not.

### The ledger this story inherits

28. **The nine `deferred-work.md` entries homed on `c4-1` are enumerated with a disposition each**
    (C2 retro ruling R2: inherited deferrals are ACs *at context time* so that none is discovered
    mid-implementation). They are listed in §"The nine inherited deferrals" below. For each:
    **implement**, **re-home by name**, or **decline with a reason**. "Not mentioned" is a failure
    of this AC.

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (AC 27; standing agreement)
  - [x] Confirm `feat/companion-c4` is cut from master at **`61a787a`**; cut
        `feat/companion-c4-1-hydration-cache` from it
  - [x] Run and record with **durations**: `uv run pytest` (expect **2,447 passed, 1 skipped**),
        `ruff check`, `ruff format --check`, `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (expect
        **731 passed, 36 files**), `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/`
        mirror (AC 23)
  - [x] **Verify the frontend table in §"What the real data says" yourself**, read-only. If the
        `fetch(` count is not 1 or the door is not `src/api/decks.ts`, the story's premise has
        changed and the record says so
  - [x] **Read `src/api/decks.ts` end to end, then `src/state/systemState.ts`, then
        `src/components/StatePanel/states.ts`.** In that order. They are the specification

- [x] **Task 1 — The seam and the file layout, decided before any code** (AC 2, 3, 16-21; Q1)
  - [x] Apply Q1's ruling: which module holds the card `fetch`, and what happens to
        `posture.test.ts`'s exhaustive door list
  - [x] If the list changes, edit the guard **and** its comment **and** `ui/README.md`'s
        *"Not here yet"* section **in the same commit as the first card fetch** — "prose outrunning
        code" is this epic's standing finding, four rounds running
  - [x] Add the `src/api/schema.ts` aliases the story's own code needs, each with a docstring
        naming its consumer; add none without one (AC 3)
  - [x] Place the new files before writing them: a `.tsx` test under `ui/tests/` is a red gate

- [x] **Task 2 — The cache slice** (AC 1, 4, 5, 6)
  - [x] One slice beside `systemState.ts`, keyed by printing uuid, in the existing zustand store
  - [x] Model the three conditions explicitly (Q2) — unknown / summary-known / hydrated — as
        *values*, never as `undefined` versus present
  - [x] Ship the deck-seeding entry point (AC 5) that c4-2 will call, and test that it issues zero
        requests
  - [x] Decide and document the consumer-facing read API (Q3) so N tiles do not become N owners —
        the `useSystemState` "one consumer" docstring is the precedent to read first

- [x] **Task 3 — The request path** (AC 2, 7, 8, 10, 25)
  - [x] Extend the fetch layer with the card read, matching `readDecks`'s **total outcome union,
        never rejects** shape
  - [x] Implement in-flight deduping **around** the request helper, not inside it
  - [x] Release the in-flight entry on **all three** outcomes; prove each (AC 10)
  - [x] Inject the reader for tests the way `createPoller` does; assert **counts**

- [x] **Task 4 — Refusals, the retry bound, and the FR-13 posture** (AC 11-15; Q4, Q5)
  - [x] Remember `card_not_found` per Q4's ruling; prove it is not re-requested on render
  - [x] Implement the per-id attempt bound (AC 12) and write the c3-2 measurement into the
        docstring beside it — the reason must travel with the constant, as
        `READ_TIMEOUT_MS`/`STALLED_AFTER_MS` do
  - [x] Prove a card refusal does not reach `panelFor()` and does not change the system panel
  - [x] Rule Q5 (the malformed-id-from-data case) and record the ruling in the code

- [x] **Task 5 — The sweep measurement** (AC 9)
  - [x] Drive a **99-id** working set, twice, counting requests; assert at most one per distinct id
  - [x] Keep the fixture honest: 99 distinct uuids, because that is the measured largest real deck

- [x] **Task 6 — Evasion probes** (AC 26)
  - [x] Probe (a)-(d) from AC 26 at minimum; record every probe and its outcome, including any that
        **passed** — a probe that defeats your own guard is the most valuable line in the record

- [x] **Task 7 — The ledger, the docs and the artifacts** (AC 22, 23, 27, 28)
  - [x] Give each of the nine inherited deferrals a disposition (AC 28)
  - [x] Update `ui/README.md`: the *"Not here yet"* seam paragraph, and — noticed while writing this
        story — **line 154 still says `schema.ts` re-exports three aliases when it exports four**
        (`DeckSummary` landed in c3-9). Correct it rather than leaving a second stale claim
  - [x] Rebuild the bundle and the `plugin/` mirror; record before/after hashes (AC 23)
  - [x] Re-run all ten gates; record counts and durations

### Review Findings

Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor), 2026-08-02.
No AC outright violated; auditor re-ran `npx tsc -b --force` and `npm test` independently (808/37,
matching the record). Severity is triaged, not the hunters' own.

- [x] [Review][Patch] **HIGH — A refusal clobbers a summary seeded mid-flight.** `hydrateCard`
      captures `summaryOf(existing)` before `await read()` and `entryFor` writes that stale
      snapshot into the `unknown` entry — a `seedCardSummaries` landing while the read is in
      flight (exactly the c4-2 deck-fetch-overlaps-hover flow) is erased by a settling refusal,
      and the tile that was drawable goes blank. Found independently by all three layers. Fix:
      re-read the store's current summary at settle time. The existing test seeds only *after*
      settlement, so the breaking order is the untested one [ui/src/state/cards.ts:453]
- [x] [Review][Patch] **MED — The AC 5/AC 6 "zero requests" assertions are vacuous.** The counted
      reader is never handed to `seedCardSummaries` (it takes no reader), so
      `expect(reader.read).not.toHaveBeenCalled()` cannot fail for any implementation. Spy on the
      real request path (global `fetch`, as `client.test.ts` already does)
      [ui/src/state/cards.test.ts:195]
- [x] [Review][Patch] **MED — The AC 10 "releases after a SUCCESS" test cannot fail.** It proves
      release via a *different* id, but `inFlight` is per-id, so a leaked entry never blocks
      another id. Falsifiable shape: hydrate to success, delete the entry from the store, hydrate
      again — a leaked settled promise would be joined and no second request made
      [ui/src/state/cards.test.ts:315]
- [x] [Review][Patch] **LOW — A read settling after `resetCardCache` resurrects its entry into the
      fresh store.** The pending IIFE's `put()` has no staleness check; reset clears the maps but
      cannot cancel the continuation. Cross-test contamination today, a real bug the moment reset
      is reused for deck switch. Fix: a module-scope generation counter checked before `put`
      [ui/src/state/cards.ts:454]
- [x] [Review][Patch] **LOW — An empty-string id addresses the bare collection route.**
      `cardPath('')` is `/api/cards/` — a different endpoint shape; the "stays one path segment"
      guarantee has no segment to protect. Guard in `hydrateCard` (terminal unknown, no request),
      per Q5's own logic, plus a test beside the hostile-id matrix [ui/src/api/client.ts:136]
- [x] [Review][Patch] **LOW — `cardOf` accepts a blank `name` that `namesOf` would drop.** A `200`
      whose `name` is `''`/whitespace hydrates and renders nameless; the deck half of the same
      file rejects exactly this, citing FR-13. Add the `trim()` check (contract-violation posture)
      [ui/src/api/client.ts:206]
- [x] [Review][Patch] **LOW — `deferredReader` keeps only the last caller's resolver.** Two
      concurrent reads through one fixture: `settle()` reaches only the second; the first stays
      pending past the test's end. Queue the resolvers per call [ui/src/state/cards.test.ts:95]
- [x] [Review][Patch] **LOW — The image-token test comment claims a contract assertion that does
      not exist.** Both the test comment and `CARD_READ_IS_RETRYABLE`'s docstring say the tokens'
      absence is "asserted against the committed contract"; nothing reads `openapi.json`. Add the
      real assertion (import the JSON, check the route's `error_responses`) — cheaper than
      softening two comments and worth more [ui/src/state/cards.test.ts:598]
- [x] [Review][Patch] **LOW — The default-reader wiring is untested.** Every test injects a
      reader; nothing proves `hydrateCard(id)` reaches `readCard`/`cardPath`/`fetch` in production
      form. One global-fetch-stub test covers the seam the cache stands on
      [ui/src/state/cards.ts:427]
- [x] [Review][Patch] **LOW — Prose/code drift, four small spots.** (1) `INITIAL_CARD_CACHE`:
      "Exported so tests can restore it" — no test imports it (they use `resetCardCache`);
      (2) the story record's File List names `CARD_READ_IS_RETRYABLE` among exports but it is
      module-private (correctly so); (3) the "3 × 99 = 297" worst-case reads as a ceiling but the
      id population is unbounded (Epic 6 agent views, the module's own header); (4) `hydrated`'s
      "Everything the corpus holds" overpromises past `cardOf`'s declared two-field residue
      [ui/src/state/cards.ts:242]
- [x] [Review][Defer] **Three transient failures make an id terminal for the tab's life while the
      whole-screen poller self-heals (FR-22 asymmetry)** [ui/src/state/cards.ts:389] — deferred,
      already a declared residue in this record with the named fix
      (`resetCardCache`-on-`deck_changed`, c4-2's event); now also ledgered in deferred-work.md
- [x] [Review][Defer] **`useCardEntry` has no test** [ui/src/state/cards.ts:484] — deferred:
      exercising the hook needs a React render harness and no testing library exists in the
      dependency set (AC 21 bans casual additions); c4-3/c4-5 are its first real consumers. The
      "dead export" half of the finding is dismissed — Q3's ruling ships the selector here by
      design, same declared-but-unread precedent as c3-2's `states.ts`

Dismissed as noise or already-ruled (6): a `400` with an unreadable body drawing no placeholder
(the fix — carrying the status code — contradicts AD-16's "nothing keys off a bare status");
`seedCardSummaries` lacking runtime guards (wire validation belongs at the network door, which
c4-2's deck read owns); the `{id, name}`-only `Card`-with-holes (declared residue, ruled: the
openapi drift gate is the answer); AC 14's unknown-token narrowing to `null` (intent-consistent,
documented); AC 26's probes not being diff-verifiable (they are applied-and-reverted by the
epic's established manner); the second `create()` call (flagged by the record itself, argued and
sound).

**All 10 patches applied and re-gated, 2026-08-02.** The mid-flight fix re-reads the store's
summary at settle time; a `generation` counter makes post-reset orphan writes land nowhere, with
an identity-checked in-flight delete so an orphan cannot release a newer read; the empty id is
refused terminally in `hydrateCard` with zero requests (`/api/cards/` is a different route);
`cardOf` now rules blank `id`/`name` as not-this-contract, matching `namesOf`'s FR-13 posture;
the AC 5/6 counts spy on global `fetch` (the only honest count for a function that takes no
reader), the AC 10 success-release test is falsifiable on the same id, `deferredReader` flushes
all pending resolvers, the image-token contract claim is now a real assertion against
`openapi.json` in `tests/wire-contract.test.ts`, and one stubbed-global test proves the
`= readCard` default reaches `fetch` at `/api/cards/{id}`. Gates after patches: `npm test`
**816 passed, 37 files** (was 808 — +8); `npx tsc -b --force`, `npm run lint`,
`npm run format:check` green; `npm run build` + `scripts/build_plugin.py` re-run — the JS bundle
is **byte-identical** (`index-CAF8aktq.js` unchanged), which is the tree-shaking confirmation
that every patched production line lives on the not-yet-imported `readCard` path; CSS and mirror
unchanged. Python untouched by the patch set (zero `.py` files in the diff).

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

1. **AD-12, verbatim:** *"Card hydration has one owner: a single card cache in the zustand store,
   keyed by card ID, that dedupes in-flight requests. The detail panel updates on hover across a
   100-tile grid and every agent view hydrates its own thumbnails, so per-component fetching would
   fire duplicate requests for the same card on every cursor sweep. **No second data-fetching or
   state library** joins zustand."* Note the second sentence: **agent views (Epic 6) are the other
   consumer**, which is why the cache is a store slice and not a deck-scoped structure.

2. **AD-16:** HTTP status carries the outcome; success bodies are the Pydantic schemas **unwrapped**;
   every non-2xx carries one typed body with a **closed snake_case `reason`**. *"Nothing in the SPA
   keys off a bare status code."* A card read branches on the **token**, not on `response.status`.

3. **The spine's consistency conventions:** *"Card identity is the **Scryfall printing UUID**,
   everywhere, always"* and *"REST is the schema boundary — the UI never assumes DB schema"* and
   *"its state comes from exactly two inputs — REST responses and WebSocket messages. Nothing else
   may write the store."*

4. **c2-6/c2-7's component rules** — irrelevant to this story except as a boundary: it ships no
   component, so none of them applies, and if one starts applying, scope has slipped (AC 16).

5. **c3-9's Q1 ruling**, restated in the ledger for this story to read: `src/api/decks.ts` and the
   `src/state/` slice are the seam **c4-1 extends**; per-card routes are **not** retry-safe;
   `STALLED_AFTER_MS = 60_000` with a `STALLED_MIN_REFUSALS = 4` floor; the poll schedule is
   2 s → ×2 → 30 s ceiling.

### The nine things this story must not break

1. `posture.test.ts`'s **exhaustive** network-door list (`:308-334`) — one door, and `App.tsx` is
   not it.
2. `package-contract.test.ts`'s **no-second-state-library** and **no-second-codegen** bans.
3. `wire-contract.test.ts`'s ban on re-declaring any `components.schemas` shape outside `src/api/`,
   and on importing `./types` outside `schema.ts`.
4. `shell.test.ts`'s nine **exhaustive import lists** and the hook/fetch/WebSocket bans over
   `AppShell.tsx` and the eight primitives.
5. `gate-geometry.test.ts`'s "no `.tsx` test files under `ui/tests/`".
6. `copy-rules.test.ts`'s prose ban outside declared copy modules — and the `!`/emoji/"something
   went wrong" string ban across **all** of `src/`.
7. `states.ts`'s four type-level asserts. They are a set equality over the token vocabulary; adding
   a token classification here without adding the token is a `typecheck` failure naming it.
8. `App.test.tsx`'s FR-22 transition test — one mount, two answers, one component. The store gains a
   slice; the poller's lifetime and `useSystemStore`'s identity must survive it.
9. The **committed bundle + `plugin/` mirror** drift gates. `npm run build` mutates `src/`.

### Source tree — what exists, what this story touches

```
ui/src/
  api/
    decks.ts        ← THE network door (posture.test.ts pins it by name). Q1 decides its future
    schema.ts       ← the only reader of types.d.ts; 4 aliases today, this story adds more (AC 3)
    types.d.ts      ← GENERATED, committed, drift-checked. Never hand-edit
    openapi.json    ← GENERATED, committed. `npm run gen:api` rewrites both
  state/
    systemState.ts  ← the zustand store + useSystemState. This story adds a slice BESIDE it
    poller.ts       ← the backoff, the stalled clock, the injected-reader test pattern to copy
    panel.ts        ← wire token → StateKey. NOT on the card path (AC 13)
  components/       ← UNTOUCHED. Eight primitives, all pinned by exhaustive import lists
  App.tsx           ← UNTOUCHED by this story (c4-2 is where the deck arrives)
ui/tests/           ← node project. Guard tests only, no .tsx, mind the tsc -b trap
```

**Backend: read-only.** `GET /api/cards/{card_id}` (`src/companion/app/routes/cards.py:105-158`) is
complete, tested and shipped. This story consumes it and changes nothing under `src/`.

### The nine inherited deferrals (AC 28 — give each a disposition)

Search `deferred-work.md` for `c4-1`. Summarised, with the line where each lives:

1. **`tsc -b` cross-project import cascade** (`:2053`, Medium) — importing a real `src/` module from
   `ui/tests/` produces `TS2835` cascades that point at the wrong file, while `npm test` stays
   green and `tsc -b`'s cache can hide it. *Home: c4-1, "the first story that will want to import
   real app modules into `ui/tests` at any scale — a fetch layer is exactly the thing whose tests
   reach across."* Fix shapes listed there; none taken yet.
2. **A malformed card id from DATA renders nothing at all** (`:2072`, Medium-if-fires) — see AC 15.
   *Home: c4-1, with c4-3 as its consumer.*
3. **No sanctioned `Card` alias in `schema.ts`** (`:2084`, Low) — see AC 3. *Home: c4-1, the first
   frontend story to consume a wire shape.*
4. **`GET /api/cards/{card_id}` sets no cache headers** (`:2094`, Low, **half closed**) — no `ETag`,
   no `Cache-Control`, no conditional requests on a resource immutable between database refreshes.
   c3-7 corrected the false docstring claim; the missing headers stay homed here, *"beside the
   hydration cache they belong with."* Note the interaction: an in-memory cache may make server
   headers moot **for this app** — which is an argument to re-home, not to ignore.
5. **The `DbSession` is held across the pacer queue wait** (`:2468`, Low now / **High** if the
   constants change) — pool 5+10=15, timeout 30 s; a pacer slower than ~0.3 s/tile pushes the burst
   past the pool timeout and surfaces as `500 internal_error`, not `503`. Pinned by
   `TestTheBurstDoesNotOutlastTheConnectionPool`. *Home: c4-1, beside the hydration cache.*
6. **An image request reads the whole card row** (`:2580`, Low) — AD-1 is satisfied by writing no
   query, so an image request pays for oracle text and legalities to read one URL. *Home: c4-1,
   "the layer that could make this free."*
7. **Alternating `database_unavailable`/`database_not_initialized` pins the backoff near base**
   (`:3126`) — every outcome-identity flip resets `delay` to `POLL_BASE_MS`, so sustained
   alternation approaches one request per 2 s. *Home: c4-1, which copies this seam and "should
   decide whether token-change resets need damping."*
8. **`images.py`'s split decision is parked** (`:2792`, Low) — 1,837 lines, 377 of them code, three
   mechanisms. *Home: re-decide with c4-1's hydration cache in view.* Most likely disposition:
   re-home to the C4 retro, since this story adds no code to `images.py`.
9. **The c4-1/c4-2 seam restatement** (`:3155`) — *"Home: c4-1 and c4-2 read this before
   extending."* Disposition: read it (done, in §"The seam"), and say so.

### Project structure notes — the conventions a new module inherits

- **A store slice is not a component.** No `.css`, no directory-per-thing; `src/state/*.ts` is flat
  and each file has a module docstring stating what it owns and what it deliberately does not.
- **Docstrings are Google-style and carry the arithmetic.** Every constant in `poller.ts` and
  `decks.ts` carries the sum that produced it (`READ_TIMEOUT_MS`: *"the backend's SQLite connection
  waits up to 5 s… twice it means no true answer is ever cut off"*). A bare number in this codebase
  is a defect. Match it.
- **Named exports only, no barrels, no default export** except `App.tsx`'s.
- **`verbatimModuleSyntax` is on** — `import type` for types, always.
- **Prettier and ESLint are gates, not preferences**, and `ui/.gitattributes` forces LF (the repo
  sets `core.autocrlf=true`; without it `prettier --check` is red on Windows and green on CI from
  the same commit).

### Open questions — answer these before writing code

**Q1 — Where does the card `fetch` live, and what happens to the one-door guard?**
*Proposed:* **rename the module to a route-neutral name and update `posture.test.ts` in the same
commit** — e.g. `src/api/client.ts` (or keep `decks.ts` and accept that it holds card routes). The
guard's comment already anticipates growth (*"c4-1 adds routes to this module"*), so the *property*
being asserted is "one door, named exhaustively", not "the door is called `decks.ts`". A module
named for decks that holds `readCard` is a name that lies, and this epic has now found "prose
outrunning code" four times. *The alternative* — a second module `src/api/cards.ts` — is the natural
layout and **fails a green test by design**; taking it means arguing that the one-door property
should become a per-directory rule instead, which is a real weakening and should be argued in the
open if chosen. **Whichever is chosen, the guard, its comment and `ui/README.md`'s "Not here yet"
are edited in the same commit** (AC 2, Task 1).

**Q2 — How are the three conditions modelled?**
*Proposed:* a **discriminated union per id**, in the manner of `DecksOutcome` —
`{status:'summary', card: CardSummary}` | `{status:'hydrated', card: Card}` |
`{status:'loading', card: CardSummary | null}` | `{status:'unknown', reason: ErrorReason}` — so
`undefined` means only *"this id has never been seen"* and every other condition is a **value the
compiler can exhaust**. Rationale: this is the shape c3-9 chose for `DecksOutcome` and `panelFor`
proved out, and it is what makes AC 4's *"consumers can distinguish"* mechanically true rather than
a convention. *The alternative* — parallel `Map`s for cards / loading / errors — makes three
invariants that can disagree, and the disagreement is invisible until a consumer reads two of them.

**Q3 — What is the consumer-facing read API, and who owns the request?**
*Proposed:* a **store action** (`hydrate(cardId)`) that any consumer may call plus a plain selector
hook that subscribes, with the *request* owned by the store rather than by the calling component's
effect. Rationale: `useSystemState`'s docstring is explicit that a hook which starts work per mount
multiplies that work per consumer, and the detail panel, the tiles and (Epic 6) the agent views will
all read the same ids. *The alternative* — a `useCard(id)` hook that fetches in an effect — reads
better at the call site and is exactly the mistake `useSystemState` warns about, unless the
deduping makes the multiplication harmless. **If that alternative is chosen, AC 7's dedupe test must
be written against N mounted consumers, not two bare calls.**

**Q4 — Is a `card_not_found` remembered forever, or with an expiry?**
*Proposed:* **forever, for the life of the tab**, with the reason written beside it. Rationale: a
card row is immutable between database refreshes, and a database refresh is a restart-scale event
(`initialize_database` takes minutes, and c3-9's poller already exists to notice the transition).
An expiry buys re-fetching an id that the corpus genuinely does not contain — measured today: **0
dangling references across 2,027 deck rows**, so the population that would benefit is empty. *The
alternative* — a TTL — is what c3-8's negative image cache chose (300 s window with backoff), and
the difference is worth stating rather than copying: **an image failure is transient by nature (a
CDN), a `card_not_found` is a statement about local data.** If a TTL is chosen anyway, say which
event it is really waiting for.

**Q5 — Does a `400 invalid_request` on a card read become a placeholder?**
*Proposed:* **yes — treat a `400` on a per-card read as the unknown-card case**, and say so in the
code. Rationale: `states.ts` classifies `invalid_request` as *"no UI response at all — the SPA never
generates a malformed request"*, and that premise is exactly what fails here: the id came from
`deck_cards`, which carries **no shape constraint**, FK enforcement is off on the async engine, and
the planned Arena `arena_card_map` work introduces ids from a second source. An id the app cannot
render is an id the app cannot render, whichever token says so. *The alternative* — declining, on
the grounds that `states.ts`'s classification is a decided contract — is defensible **only if it is
written down as a decline with the ledger entry re-homed by name**, because "0 of 2,027 today" is a
fact about today's data, not a guarantee. **Do not leave it undecided** (AC 15).

**Q6 — Does this story ship the backoff damping the ledger asks about (deferral 7)?**
*Proposed:* **no — re-home it on c5-6.** Rationale: the damping question is about `poller.ts`'s
whole-screen poll, and c5-6 already owns the family of three sibling entries about that poller's
re-drive behaviour (ruled at the C3 retro, R3: *"c5-6 resolves the family; it should not solve one
third of it"*). This story does not copy `poller.ts`'s backoff at all if AC 12's bound is per-id
attempts rather than a token-driven retry loop. *If* the bound turns out to need a schedule, this
answer changes and the damping decision comes with it.

**Q7 — Do deferrals 4, 5 and 6 (the three backend ones) belong in this story at all?**
*Proposed:* **re-home all three, by name, with the reason.** They are homed here on the theory that
a hydration cache is the layer that makes them moot; measured, that theory holds for 4 (an in-memory
cache means the missing `ETag` costs one request per id per tab) and is **irrelevant** for 5 and 6,
which are properties of the *image* route this story does not touch. Re-homing three backend items
out of a frontend story is the honest move, and it is a named re-home, not a silent drop. *The
alternative* — implementing 4's `ETag` — is a backend change in a story whose whole product is a
store slice, and it would make AC 27's "the Python side is unchanged" false for no measured gain.

### References

- Epic story text: [epics-companion-app.md#Story 4.1](_bmad-output/planning-artifacts/epics-companion-app.md#L1844-L1876) · Epic 4 header [#L1837-L1843](_bmad-output/planning-artifacts/epics-companion-app.md#L1837-L1843) · Epic list entry [#L783-L797](_bmad-output/planning-artifacts/epics-companion-app.md#L783-L797)
- FR-05, FR-13, FR-19, NFR-05: [epics-companion-app.md#L27](_bmad-output/planning-artifacts/epics-companion-app.md#L27) · [#L89](_bmad-output/planning-artifacts/epics-companion-app.md#L89) · [#L113](_bmad-output/planning-artifacts/epics-companion-app.md#L113) · [#L157](_bmad-output/planning-artifacts/epics-companion-app.md#L157)
- **AD-12 (the rule this story implements)**: [ARCHITECTURE-SPINE.md#L272-L291](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L272-L291) · AD-16 [#L329-L352](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L329-L352) · the consistency conventions [#L355-L360](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L355-L360)
- **The two-tier hydration contract, in one sentence**: [EXPERIENCE.md — Card detail panel row](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L86) · Card tile [#L82](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L82) · skeleton-vs-placeholder policy [#L166](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L166) · the no-announce rule for transient targets [#L154](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L154)
- **The seam to extend**: [decks.ts](ui/src/api/decks.ts) — the c4-1/c4-2 ruling [#L4-L39](ui/src/api/decks.ts#L4-L39), the outcome union [#L88-L91](ui/src/api/decks.ts#L88-L91) · [systemState.ts](ui/src/state/systemState.ts) — the one-consumer rule [#L49-L60](ui/src/state/systemState.ts#L49-L60) · [poller.ts](ui/src/state/poller.ts) — the injected reader [#L122-L132](ui/src/state/poller.ts#L122-L132)
- **The token vocabulary and its classifications**: [states.ts#L91-L134](ui/src/components/StatePanel/states.ts#L91-L134) · `PLACEHOLDER_FOR_REASON` [#L166-L170](ui/src/components/StatePanel/states.ts#L166-L170) · `NO_UI_RESPONSE` [#L182-L186](ui/src/components/StatePanel/states.ts#L182-L186) · the boundary that must NOT see a card token [panel.ts#L70-L71](ui/src/state/panel.ts#L70-L71)
- **The endpoint**: [cards.py#L105-L158](src/companion/app/routes/cards.py#L105-L158) — note the `Warning:` about 503-outranks-400 · the deck projection that pre-hydrates [deck.py#L234-L281](src/data/schemas/deck.py#L234-L281)
- **The guards that will fail first**: [posture.test.ts#L308-L334](ui/tests/posture.test.ts#L308-L334) · [wire-contract.test.ts](ui/tests/wire-contract.test.ts) · [package-contract.test.ts](ui/tests/package-contract.test.ts) · [shell.test.ts#L1040-L1180](ui/tests/shell.test.ts#L1040-L1180)
- **The seam documentation to correct**: [ui/README.md#L959-L1000](ui/README.md#L959-L1000) — and the stale alias count at [#L154](ui/README.md#L154)
- **The nine inherited deferrals**: [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — search `c4-1`
- **What C4 inherits, by story**: [epic-c3-retro-2026-08-02.md#L540-L580](_bmad-output/implementation-artifacts/epic-c3-retro-2026-08-02.md#L540-L580)
- Project rules: [project-context.md](_bmad-output/project-context.md) · frontend conventions [ui/README.md](ui/README.md)

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Code, `bmad-dev-story`), 2026-08-02.

### Debug Log References

**The baseline, measured at `61a787a` on `feat/companion-c4-1-hydration-cache` (Task 0).** Every
number in §"What the real data says" was re-verified rather than trusted:

| Gate | Baseline | After |
| --- | --- | --- |
| `npm test` | **731 passed, 36 files**, 3.96 s | **808 passed, 37 files**, 4.72 s (**+77**) |
| `npx tsc -b --force` | green, 2.0 s | green, 2.2 s |
| `npm run lint` | green, 5.3 s | green |
| `npm run format:check` | green, 1.3 s | green |
| `npm run build` | green | green, bundle **CHANGED** (below) |
| `uv run pytest -m "not integration"` | **2,447 passed, 1 skipped, 54 deselected**, 90.6 s | **2,447 / 1 / 54**, 170.9 s |
| `uv run ruff check .` | green | green |
| `uv run ruff format --check .` | green, 307 files | green, 307 files |
| `uv run mypy src/` | green, 89 files | green, 89 files |
| `uv run mypy src/ --platform win32` | green, 89 files | green, 89 files |

**The Python side is unchanged, and that is the expected result, not a coincidence** (AC 27): this
story adds no Python, changes no Pydantic model, and therefore leaves `openapi.json` and
`types.d.ts` untouched (AC 22 — `git status` shows neither). The pytest runtime difference
(90.6 s → 170.9 s) is this machine's known measurement noise, ledgered at the C3 retro
(*"three consecutive runs… too noisy to support a before→after claim"*), not a signal.

**The frontend premise table, re-verified read-only.** `fetch(` call sites in tracked non-test
`ui/src`: **1**, and the door is **`src/api/decks.ts`** — the story's premise held exactly. (A naive
`grep` also matches the word *"refetch"* inside a `states.ts` comment; `posture.test.ts` strips
comments with a character walker, which is why its count is the authoritative one.)

**The bundle and the mirror, MEASURED changed** (AC 23):

| Asset | Before | After |
| --- | --- | --- |
| `index-*.js` | `index-CfiLRdVp.js` · `0E1DE820FD0B2B88` · 198.56 kB | `index-CAF8aktq.js` · `BA5D18CDA62C6737` · **198.65 kB** |
| `index-*.css` | `0A3C142D84B5A98D` | `0A3C142D84B5A98D` — **identical** |
| `index.html` | `AD09FAA401BF34A0` | `0017A9B10FAC33D1` (the asset filename) |
| woff2 / favicon | unchanged | unchanged |

**The CSS being byte-identical is the confirmation that AC 16 held**: this story ships no pixels, so
a changed stylesheet would have been the signal that scope had slipped. The +0.09 kB of JS is the
`client.ts` refactor (two readers onto one shared `request()`); **`src/state/cards.ts` is not in the
bundle at all**, because nothing imports it yet — its consumers are c4-2 (`seedCardSummaries`), c4-3
and c4-5 (`useCardEntry`, `hydrateCard`). That is the same declared-but-unread state c3-2's
`states.ts` classification shipped in, and it is what AC 16 asks for. `scripts/build_plugin.py`
regenerated the mirror; both trees carry the new asset.

**One thing went red that `npm test` could not see, and it is the ledger entry homed on this story
arriving from the unexpected direction.** After removing four `as CardOutcome` assertions that
ESLint's `no-unnecessary-type-assertion` called redundant, `npm test` stayed **fully green at 808**
while `npx tsc -b --force` failed with `TS2345` — an untyped `it.each` table widens `kind` to
`string`, which vitest never evaluates as a type. Deferral 1 predicted exactly this asymmetry
(*"`npm test` stays fully green throughout — this is a `tsc`-only failure"*) for a different
mechanism. Fixed by typing the table (`it.each<[string, CardOutcome]>`) rather than restoring the
casts, so both gates are satisfied by one construct. **`npx tsc -b --force` earned its place in
AC 27 during this story, not in theory.**

### Completion Notes List

**All seven open questions were answered AS PROPOSED.** That is the ninth story running, and in two
cases the measurement while implementing *strengthened* the proposal rather than merely confirming
it (Q6 and Q7 below).

- **Q1 — where the card `fetch` lives.** As proposed: **`src/api/decks.ts` → `src/api/client.ts`**,
  and `posture.test.ts:328`'s exhaustive door list moved with it **in the same commit as the first
  card fetch**, along with the guard's comment and `ui/README.md`'s *"Not here yet"* section. The
  property the guard protects is *"one door, named exhaustively"*, not *"the door is called
  `decks.ts`"*; a module named for decks that exports `readCard` is the "prose outrunning code"
  finding this epic has now made four times. The alternative (a second `src/api/cards.ts`) fails a
  green assertion by design and would have meant weakening a one-door rule into a per-directory one
  to buy a filename. The rename is `git mv`-clean and the deck half of `client.test.ts` is unchanged
  — which doubles as the regression proof that folding both readers onto one shared `request()`
  helper changed no behaviour.
- **Q2 — the three conditions.** As proposed: a **discriminated union per id**, `summary` /
  `loading` / `hydrated` / `unknown`, so `undefined` means only *"never seen"* and every other
  condition is a value the compiler can exhaust. `loading` carries `summary: CardSummary | null` so
  a tile that was drawable before a hover stays drawable during it (`EXPERIENCE.md`'s "fills in
  place"). `unknown` carries four fields — `reason`, `placeholder`, `summary`, `retryable` — for
  the reasons in its docstring.
- **Q3 — the read API.** As proposed: **`hydrateCard(cardId)` is a plain function that owns the
  request; `useCardEntry(cardId)` is a pure selector that starts nothing.** A `useCard(id)` that
  fetched in an effect is the `useSystemState` mistake in a new costume, and the deduping would
  merely have hidden it at the cost of N effects and N cleanup paths. AC 7's dedupe test is
  nonetheless written against **50** concurrent callers as well as two.
- **Q4 — is a `card_not_found` remembered forever.** As proposed: **forever, for the life of the
  tab**, recorded in `CARD_READ_IS_RETRYABLE`'s docstring beside the entry. A card row is immutable
  between database refreshes and a refresh is a restart-scale event; 0 of 2,027 deck rows dangle
  today, so the population a TTL would help is empty. The contrast with c3-8's 300 s negative image
  cache is written down rather than left implicit: **an image failure is transient by nature (a
  CDN), a `card_not_found` is a statement about local data.**
- **Q5 — does a `400 invalid_request` become a placeholder.** As proposed: **yes**, and closed on
  *both* fix shapes the ledger offered rather than one. `PLACEHOLDER_FOR_CARD_REFUSAL` maps it to
  `states.ts`'s own `'unknown-card'` key, beside `card_not_found` — whose value is read OUT of
  `PLACEHOLDER_FOR_REASON` rather than re-typed, so the two cannot drift. `states.ts` is
  **untouched**: adding `invalid_request` to `PLACEHOLDER_FOR_REASON` would break
  `ReasonClassificationsAreDisjoint`, and rightly, because the destination is context-dependent
  rather than a property of the token. The second shape landed too — `cardPath()` runs the id
  through `encodeURIComponent`, so a `card_id` carrying `/`, `?` or `#` can no longer change *which
  route* is addressed.
- **Q6 — does this story ship the backoff damping.** As proposed: **no, re-homed to c5-6** — and
  the premise the deferral was homed on turned out to be **false**, which is worth more than the
  re-home. c4-1 does not copy `poller.ts`'s seam at all: `readCard` has no schedule, no backoff and
  **no timer**, and AC 12's bound is a cumulative attempt count per id. There is no `delay` for a
  token change to reset, so there is nothing here to damp.
- **Q7 — do deferrals 4, 5 and 6 belong here.** As proposed: **re-homed, all three, by name.** And
  the measured verdict differs per item, which is the point of doing it rather than waving: for #4
  (no cache headers) the "the cache makes it moot" theory **holds** — one request per id per tab
  means the entry's own worst case is now structurally impossible — so it goes to the **C4 retro**
  as close-or-do. For #5 and #6 the theory is simply **wrong**: both are properties of the *image*
  route, which this story never calls, so they go to **c4-4** (the art grid), the story that will
  actually produce the burst.

**Two design decisions that are NOT open questions but are worth a reviewer's attention:**

1. **`src/state/cards.ts` is a second `create()` call, and it is still exactly one card cache
   (AC 1).** AD-12 bans a second state **library**, not a second store instance, and folding the
   cache into `useSystemStore` would be a measurable defect: `useSystemState` subscribes **with no
   selector**, so every tile's hydration would re-render `App` and the whole tree — 99 whole-app
   renders on the very sweep this module exists to make cheap. `systemState.ts`'s own header calls
   the cache *"a new slice BESIDE this one"*. Argued at length in the module header.
2. **The attempt bound and the token are ONE decision, read in one place.** `retryable` is computed
   as `!spent(cardId) && (reason === null || CARD_READ_IS_RETRYABLE[reason])`, and
   `hydrateCard`'s only terminal gate is `!existing.retryable`. An earlier draft had a separate
   attempts check at the gate *and* a post-hoc adjustment of the field; that is two copies of one
   invariant, free to disagree, so it was collapsed. The field a consumer reads *is* the gate's
   answer.

**Evasion probes — nine run, nine caught, none passed** (AC 26). Each plant was applied to real
tracked source, the relevant suite run, and the plant reverted:

| # | Probe | Result |
| --- | --- | --- |
| **a** | A second `fetch(` in a new tracked module (`src/state/rogue.ts`) | **CAUGHT** — `posture.test.ts` named the file: `+ "src/state/rogue.ts"` |
| **b** | Defeat the in-flight join (`hydrateCard` never shares the promise) | **CAUGHT** — 3 tests, incl. the 50-caller and concurrent-sweep cases |
| **c** | Remove the attempt bound (`retryable` from the token alone) | **CAUGHT** — 5 tests; the 503-forever loop ran to 500 requests |
| **d** | Leak the in-flight entry after a rejection (no inner `catch`, delete on success only) | **CAUGHT** — 2 tests, both rejection shapes (sync throw and open-promise reject) |
| e | Seeding downgrades a hydrated id | **CAUGHT** — 3 tests |
| f | Route a card refusal through `panelFor()` into `useSystemStore` | **CAUGHT** — 8 tests |
| g | Drop `invalid_request` from `PLACEHOLDER_FOR_CARD_REFUSAL` (undo Q5) | **CAUGHT** — 1 test |
| h | Re-declare `CardSummary` outside `src/api/` | **CAUGHT** — `wire-contract.test.ts`: `src/state/plant.ts declares CardSummary` |
| i | Remove `encodeURIComponent` from `cardPath` | **CAUGHT** — 5 tests |
| j | Delete `card_not_found` from `CARD_READ_IS_RETRYABLE` (an 11th-token simulation) | **CAUGHT by `tsc`, naming the token** — `TS1360 … does not satisfy Record<…>` plus a `TS7053` at the index site; `npm test` would have stayed green |
| k | A component importing `useCardEntry` from the new slice | **CAUGHT** — `posture.test.ts`, both halves (value-import door AND behaviour family) |

Probe **j** is the one worth reading: it is the same mechanism that caught c3-2's seventh token and
c3-4's eighth, still working on a map this story wrote, and it fails in a gate `vitest` cannot see.

**Declared residues, none closed here:**

- **An alias added to `schema.ts` with no consumer is not gated.** AC 3 is a rule, not a test —
  `wire-contract.test.ts` reads the export list to *grow the ban*, not to demand a consumer. Nothing
  would fail if a future story added `DeckDetail` unused. Review owns it, as it owns the copy-guard's
  three declared residues.
- **`cardOf` validates two fields of a 42-field record.** A `200` carrying `{id, name}` and nothing
  else is accepted and reaches consumers as a `Card` with holes. That is a backend contract
  violation (`response_model=Card` makes it a FastAPI bug), not attacker input, and the answer is the
  openapi drift gate rather than a hand-maintained second copy of the schema. Stated in the
  function's docstring.
- **`MAX_ATTEMPTS_PER_CARD = 3` has no live recovery path once spent.** A backend that refuses for
  the first three hovers of an id and then recovers leaves that id un-hydrated for the tab's life.
  Bounded and deliberate (worst case 3 × 99 = 297 requests), and the recovery is a reload — the same
  one `poller.ts` implies for the whole screen. If c4-5's detail panel makes this visible in
  practice, a `resetCardCache()`-on-`deck_changed` hook is the natural fix and c4-2 owns that event.

**The nine inherited deferrals (AC 28), each with a disposition** — all annotated in place in
`deferred-work.md`, none left as "not mentioned":

| # | Entry | Disposition |
| --- | --- | --- |
| 1 | `tsc -b` cross-project import cascade (`:2053`) | **NOT TRIGGERED → re-homed.** c4-1's tests live in the app project; the one `ui/tests/` change reads source as *text*. `npx tsc -b --force` green. Home: the first story that really imports a `src/` module into `ui/tests/` (likely **c5-1**). |
| 2 | Malformed card id from DATA (`:2072`) | **✅ RESOLVED** — Q5 placeholder **and** `encodeURIComponent`. Both fix shapes, test-pinned. c4-3 renders it. |
| 3 | No sanctioned `Card` alias (`:2084`) | **✅ RESOLVED** — `Card`, `CardSummary`, `DeckCardSummary` added with named consumers. `CardFace`/`DeckDetail` deliberately **not** (no consumer here). |
| 4 | `GET /api/cards/{card_id}` sets no cache headers (`:2101`) | **RE-HOMED → C4 retrospective** (Q7). The cache makes the entry's own worst case structurally impossible; `no-store` would make an `ETag` inert; a backend change here would falsify AC 27. |
| 5 | `DbSession` held across the pacer queue wait (`:2468`) | **RE-HOMED → c4-4** (Q7). An image-route property; c4-1 issues no image request. c4-4 is the first surface that mounts ~99 `<img>` at once. |
| 6 | An image request reads the whole card row (`:2584`) | **RE-HOMED → c4-4** (Q7). The "the cache could make this free" theory is **wrong** — the cache holds JSON rows, the waste is on a route it never calls. |
| 7 | Alternating tokens pin the backoff near base (`:3132`) | **RE-HOMED → c5-6** (Q6). c4-1 copies no backoff, so there is nothing to damp; c5-6 owns the sibling family (C3 retro R3). |
| 8 | `images.py`'s split decision parked (`:2824`) | **RE-HOMED → C4 retrospective.** The cache is now "in view" and the answer is that it changes nothing about `images.py`; c4-4/c4-6 will supply the real evidence. |
| 9 | The c4-1/c4-2 seam restatement (`:3164`) | **✅ READ AND ACTED ON; half closed.** Seam extended not replaced, deduping went around it, the retry warning produced `MAX_ATTEMPTS_PER_CARD`. Amended: the door is now `client.ts`. **c4-2's half stands.** |

**Two further entries name c4-1 in a shared home and were checked rather than assumed:**
the generated-type optionality asymmetry (`:1894`, "Home: c4-1/c4-2") is **not triggered** — none of
its fields appears on the three aliases c4-1 consumed, so it is c4-2's alone, annotated as such; and
the `413`-on-a-body-less-GET wart (`:2120`) was handled exactly as §"The seam" item 7 instructed —
as an unremarkable member of the token union, classified `false` in `CARD_READ_IS_RETRYABLE` with no
curation, its re-home on c5-5 untouched.

### File List

**Renamed (`git mv`, Q1):**

- `ui/src/api/decks.ts` → `ui/src/api/client.ts` — the one network door; header rewritten for the
  rename, `CARD_PATH_PREFIX`, `cardPath()`, `CardOutcome`, `cardOf()`, `readCard()` and the shared
  `request()` helper added
- `ui/src/api/decks.test.ts` → `ui/src/api/client.test.ts` — deck half unchanged (the refactor's
  regression proof); +30 assertions for the card read

**Added:**

- `ui/src/state/cards.ts` — the one card cache. Exports: `CardEntry`, `CardCacheState`,
  `INITIAL_CARD_CACHE`, `MAX_ATTEMPTS_PER_CARD`, `useCardStore`, `seedCardSummaries`,
  `hydrateCard`, `useCardEntry`, `resetCardCache`. Module-private, deliberately:
  `CARD_READ_IS_RETRYABLE` and `PLACEHOLDER_FOR_CARD_REFUSAL` — consumers read the entry's own
  `retryable`/`placeholder` fields rather than re-deriving them (review corrected this list;
  the first draft named the two private maps as if exported)
- `ui/src/state/cards.test.ts` — 47 tests, every assertion a request COUNT from an injected reader

**Modified:**

- `ui/src/api/schema.ts` — `Card`, `CardSummary`, `DeckCardSummary` aliases, each naming its consumer
- `ui/src/state/poller.ts` — import path only (`../api/decks` → `../api/client`)
- `ui/src/state/poller.test.ts` — import path + one docstring reference
- `ui/tests/posture.test.ts` — the exhaustive door list, its comment, two planted-evasion spellings,
  and one new plant (`import { hydrateCard } from '../../state/cards'`)
- `ui/tests/copy-tails.test.ts` — the source path it reads `DECKS_PATH` out of
- `ui/README.md` — the stale three-vs-four alias count (now seven), and the whole *"Not here yet"*
  seam section rewritten for what actually shipped
- `_bmad-output/implementation-artifacts/deferred-work.md` — 10 entries annotated with dispositions
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status + narrative
- `_bmad-output/implementation-artifacts/c4-1-…​.md` — this file

**Regenerated (committed artifacts):**

- `src/companion/app/static/index.html`, `src/companion/app/static/assets/index-CAF8aktq.js`
  (replacing `index-CfiLRdVp.js`)
- `plugin/server/src/companion/app/static/…` — the same two, mirrored

### Change Log

| Date | Version | Description |
| --- | --- | --- |
| 2026-08-02 | 0.2 | **IMPLEMENTED → review.** The one card cache, the in-flight deduping and the card read. **All 7 open questions AS PROPOSED** (ninth story running), with two of them strengthened by measurement rather than merely confirmed: Q6's premise turned out false (this story copies no backoff, so there is nothing to damp) and Q7's "the cache makes it moot" theory holds for deferral 4 and is wrong for 5 and 6, which are image-route properties re-homed to c4-4. **Q1's rename is the visible change**: `src/api/decks.ts` → `src/api/client.ts`, with `posture.test.ts`'s exhaustive door list, its comment and `ui/README.md` moved in the same commit as the first card fetch — the guard's property is "one door, named exhaustively", not the filename. The cache is a **second `create()` and still one cache**, argued in the header: folding it into `useSystemStore` (which `useSystemState` subscribes to with no selector) would re-render the whole app on every tile's hydration. AC 12's bound is a **cumulative per-id attempt count**, not a retry loop — no timer anywhere — and `retryable` is one predicate read at the gate and reported in the value. **Nine evasion probes, nine caught, none passed**; probe (j) failed in `tsc` alone while `npm test` stayed green, which is deferral 1's asymmetry arriving from an unexpected direction — and it bit for real once during implementation. 731 → **808 frontend** (36 → 37 files); Python **2,447 / 1 / 54 unchanged**, as expected for a story that adds no Python. Bundle + mirror MEASURED changed (JS only; **CSS byte-identical**, which is AC 16's confirmation). Nine inherited deferrals: **3 resolved, 5 re-homed by name, 1 not-triggered-and-re-homed**; two further shared-home entries checked and annotated. |
| 2026-08-02 | 0.1 | **CONTEXTED off `61a787a`** on the freshly-cut `feat/companion-c4`. The headline finding is that the story's own title is slightly misleading: `GET /api/deck/{id}` already embeds a `CardSummary` per card, so the cache is a **two-tier** structure whose bulk tier arrives free in one request — measured at 38,182 vs 212,436 bytes and 1 vs 99 requests on the largest real deck (99 tiles). `EXPERIENCE.md:86` states that contract in one sentence and it had not been connected to this story before. 28 ACs, 7 open questions, 9 inherited deferrals, 9 named don't-breaks. Baseline 731 frontend / 36 files. |
