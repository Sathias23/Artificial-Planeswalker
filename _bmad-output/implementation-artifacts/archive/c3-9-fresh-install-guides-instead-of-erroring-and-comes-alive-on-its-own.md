---
epic: c3
story: c3-9
work_branch: feat/companion-c3
story_branch: feat/companion-c3-9-fresh-install
depends_on: c3-8 (PR #36, merged into the umbrella at 16976c5) — but the load-bearing dependency is **c2-9**, which shipped `StatePanel`, `copy.ts` and `states.ts` as declarations written *for this story to read*, and **c3-1** (`GET /api/decks`, `GET /api/deck/{id}`), which is the endpoint this story polls
baseline_commit: 16976c5
---

# Story C3.9: Fresh install guides instead of erroring, and comes alive on its own

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad on a brand-new machine,
I want the app to tell me the card database isn't built yet and then start working by itself once it is,
so that going from a fresh install to card art on screen never involves a config file or an error page.

**What this story really is.** Eight stories of Epic C3 built backend. This one is the **only
frontend story in the epic**, and it is the story twenty other stories have been writing notes to.
Five facts about it are not what the title suggests, and the first one is the most dangerous:

1. **This is the first runtime behaviour in `ui/src`, full stop.** Measured at `16976c5`: across
   every tracked `.ts`/`.tsx` under `ui/src`, there are **zero** `fetch(` calls, **zero** hook
   calls, **zero** `setTimeout`/`setInterval`, and **zero** imports of `zustand` — the only hits
   for any of those spellings are inside comments explaining that they do not exist yet
   (`StatePanel.tsx:9`, `states.ts:220`, `filled.ts:8`). The SPA today is `App.tsx` composing a
   shell, a hard-coded `<StatePanel state="no-active-deck" />` and a footer. **Everything this
   story does is new machinery in a codebase whose every existing guard was written on the
   assumption that there is none.** Expect the guards to be the hard part, not the polling.

2. **`states.ts` is a 318-line specification addressed to this story by name, and nothing has ever
   executed a line of it.** `PANEL_FOR_REASON` (`:91`), `CLIENT_ONLY_STATES` (`:200`) and
   `RETRIES_QUIETLY` (`:223`) are total maps, proved by `npm run typecheck` and consumed by
   nothing — so they are tree-shaken out of the bundle entirely. Three separate docstrings say
   *"the wiring that reads this map is c3-9's"*. **Read that file before writing any code.** It
   already decided which token draws which panel, which states have no token at all, and which
   states may retry themselves; re-deriving any of it is the reinvention it exists to prevent.

3. **Twelve `deferred-work.md` entries are homed on this story by name — more than any story in
   the feature** (c3-8 held the previous record at nine). C2 retro ruling R2
   (`sprint-status.yaml:489`) named **five** and required them to be ACs *at context time* so that
   *"none is discovered mid-implementation"*. The ledger actually holds **twelve**; all twelve are
   enumerated in AC 22 with a disposition each. R2 also flags this as **the epic's heaviest
   story** and rules that it **stays ONE story**.

4. **The scope boundary with c4-1 and c4-2 is the hardest decision here, and today's
   documentation says this story may not do what its own epic AC requires.** `ui/README.md:960-964`
   states plainly: *"**c4-1** owns the runtime `fetch` layer, the store and its in-flight deduping,
   and **c4-2** owns the deck bootstrap that calls `GET /api/decks`"*. This story's epic AC 3
   requires it to transition *"to the no-active-deck state, **listing available decks**"* — which
   is `GET /api/decks`. **Q1 rules this**, and whatever it rules, `ui/README.md`'s *"Not here yet"*
   section is edited in the same commit (AC 19). Shipping a fetch while that paragraph still
   assigns fetching to c4-1 is the "prose outrunning code" failure this epic has now found four
   times.

5. **The two `503` tokens have different triggers, and the difference decides where the stalled
   escalation goes.** Read `src/data/database.py:125-150`: `is_database_initialized` returns
   `False` — i.e. `database_not_initialized` — for a missing file, a missing `cards` table, an
   **empty** table, **and a partial import killed mid-way**. So the *"Card database not set up
   yet"* panel is what shows for the **entire multi-minute first build**, which is precisely what
   its copy promises (*"First build takes a few minutes — this page will come alive on its own
   when it's ready"*). `database_unavailable` is a different animal: it is a SQLAlchemy
   `DatabaseError` — *database is locked*, *file is not a database* — routed by
   `errors.database_error_handler`. **The stalled escalation belongs to the second only** (Q3).
   Escalating a first build to *"Reads haven't resumed for a while"* would call a working import
   stalled, and that panel's whole subject is whether the words are true.

**Everything numeric in this story was measured on this machine at `16976c5` against the shipped
database and the installed toolchain, read-only. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **The panel, its words and its gate are done, and none of them may be edited.** `StatePanel`
   renders six states from `copy.ts`'s `STATE_COPY`; `ui/tests/copy.test.ts` asserts every
   `Headline:` and every re-joined `Body:` **byte-for-byte against `EXPERIENCE.md` itself**. This
   story ships **no copy** — every string it needs already exists and is already gated. A new
   user-facing sentence in this story is a signal that something has gone wrong (AC 16).

2. **The token→panel map is written, typed and total.** `PANEL_FOR_REASON` maps `deck_not_found`
   → `no-active-deck`, `database_not_initialized` → `database-not-initialized`,
   `database_unavailable` → `database-updating`, `internal_error` → `internal-error`, and six
   tokens to `null` with each `null` further classified (`PLACEHOLDER_FOR_REASON`,
   `NO_UI_RESPONSE`) and three type-level asserts proving the classification is a set equality.
   **Consume it; do not write a `switch`.**

3. **`RETRIES_QUIETLY` is the retry contract this story is held to, and it is not uniform.**
   `database-not-initialized: true`, `database-updating: true`, `disconnected: true`;
   `no-active-deck: false`, `database-updating-stalled: false`, `internal-error: false`. Its
   docstring says why each: `internal_error` is deterministic, so *"a quiet retry loop would hammer
   a broken backend while showing the user a calm panel that never changes"*. **A poller that
   retries every state is wrong against a contract already written down.**

4. **`CLIENT_ONLY_STATES` names the two panels with no wire token**, and they split cleanly by
   owner: `disconnected` is **c5-6's** (the WebSocket backoff exhausting its retries — there is no
   response to carry a token) and `database-updating-stalled` is **this story's**, produced by
   elapsed time on the client. So this story can select **five** of the six panels and must not
   claim the sixth.

5. **Every 503 this story polls for is already produced, already tested, and already reachable
   through a real route.** `deps.get_session` (`deps.py:236-279`) re-probes readiness on **every**
   request and never caches — *"a database created while the backend is running must be picked up
   with no restart (FR-22), which a remembered `True` would break as surely as a remembered
   `False`"*. `GET /api/decks` therefore flips from `503` to `200` on its own the moment the import
   finishes. **The backend half of FR-22 is done. This story is the client half.**

6. **The wire types are generated and the alias module is the only door.**
   `ui/src/api/schema.ts` exports `ErrorReason`; `ui/tests/wire-contract.test.ts` bans re-declaring
   any shape the backend describes anywhere in tracked TypeScript outside `src/api/`, and bans
   importing `./types` directly. A hand-written `interface DeckSummary` in a new fetch module is a
   red test, not a style note.

7. **The presentation-only guards are exhaustive import lists, and they cover `AppShell.tsx` and
   the eight primitives — but NOT `App.tsx`.** `ui/tests/shell.test.ts:1023-1107` pins
   `AppShell.tsx` to exactly `['../filled', './AppShell.css', 'react']`, a **type-only** react
   import, and no `use[A-Z](`/`use(`/`fetch(`/`WebSocket(`; `:1131-1180` does the same per
   primitive. Measured: `src/App.tsx` is in **neither** list. That is the gap this story lands in,
   and AC 18 is about whether it should stay a gap.

8. **`error_responses` is the one declaration site and it is already per-include.**
   `main.py:461-472`: the database-backed routers get
   `("invalid_request", "payload_too_large", "database_unavailable", "internal_error")`; the
   active-deck router gets two. `errors.error_responses` (`errors.py:171-229`) already collapses
   tokens sharing a status into one entry naming each — a documented behaviour that **has never
   fired**, because `database_not_initialized` has never been declared anywhere (Q4).

9. **The route is where the token meets the status, and nothing else may choose one.**
   `STATUS_BY_REASON` (`errors.py:46-57`) is the single pairing. A client that keys off a bare
   status rather than the body's `reason` is reading the weaker half of a contract deliberately
   built the other way round (AD-16: *"nothing in the SPA keys off a bare status code"*).

10. **The test seams exist and the two vitest projects are already split.** `vite.config.ts` puts
    `src/**/*.test.{ts,tsx}` in the **jsdom** project (with `test-setup.ts` registering jest-dom
    and `afterEach(cleanup)`) and `tests/**/*.test.{ts,tsx}` in the **node** project. A component
    or hook test is colocated and needs no configuration; a guard test goes in `ui/tests/`.
    `ui/tests/gate-geometry.test.ts` forbids `.tsx` test files under `tests/`.

### What the real data says (measured at `16976c5`, read-only)

**The SPA has no runtime behaviour at all.**

| Property | Measured over `ui/src` (tracked `.ts`/`.tsx`, excluding `*.test.*`) |
| --- | --- |
| `fetch(` / `XMLHttpRequest` / `EventSource` / `WebSocket(` call sites | **0** |
| React hook call sites (`use[A-Z]…(`, `use(`) | **0** |
| `setTimeout` / `setInterval` call sites | **0** |
| `zustand` imports anywhere in `ui/src` or `ui/tests` | **0** (it is a declared dependency with no consumer; `tests/package-contract.test.ts:72` asserts the dependency exists so its "no second store" ban is not vacuous) |
| Runtime consumers of `states.ts` | **0** — the whole module is erased from the bundle |

**The committed wire contract, all eight operations, and the hole in it.** Read out of
`ui/src/api/openapi.json`:

| Operation | Declared non-200 responses |
| --- | --- |
| `GET /health` | 400 `invalid_request` · 413 `payload_too_large` · **503 `database_unavailable`** · 500 `internal_error` |
| `GET /api/decks` | 400 · 413 · **503 `database_unavailable`** · 500 |
| `GET /api/deck/{deck_id}` | 400 · 413 · **503 `database_unavailable`** · 500 · 404 `deck_not_found` |
| `GET /api/deck/{deck_id}/format-check` | 400 · 413 · **503 `database_unavailable`** · 500 · 404 `deck_not_found` |
| `GET /api/cards/{card_id}` | 400 · 413 · **503 `database_unavailable`** · 500 · 404 `card_not_found` |
| `GET /api/card-image/{scryfall_id}` | 400 · 413 · **503 `database_unavailable`** · 500 · 404 `card_not_found \| no_image_data` · 502 `image_fetch_failed` |
| `GET /api/active-deck` | 400 · 500 |
| `PUT /api/active-deck` | 400 · 500 · 403 `forbidden` |

Three consequences, all load-bearing:

* **`database_not_initialized` appears nowhere in the document, on any route** — while six routes
  can answer it and `TestDatabaseStates` asserts it by name in three test modules. **On a fresh
  install it is the most common 503 the UI will ever see, and it is the one this story exists to
  render.** Q4 rules it; the count stopped rising only because c3-6, c3-7 and c3-8 added no routes.
* **`/health` declares a 503 it structurally cannot answer** — it takes no session. Inherited from
  c1-2 and deliberately not narrowed since (`main.py:450`: *"narrowing a c1-2 route's committed
  schema is not this story's call"*). Noted so a reader does not treat `/health`'s 503 as a
  readiness signal: it is not one.
* **Six body-less GETs publish a 413.** That is the ledgered wart homed here-or-sooner (Q8).

**The state machine this story implements, derived from the shipped backend rather than invented:**

| What the poll sees | Panel | Retries? | Source |
| --- | --- | --- | --- |
| `200` + one or more decks | *(no panel — hand off to c4-2)* | — | this story renders the no-active-deck panel until c4-2 |
| `200` + empty list | `no-active-deck`, deck list empty | `false` | `RETRIES_QUIETLY` |
| `503 database_not_initialized` | `database-not-initialized` | `true` | fresh install, **and the whole first import** (`database.py:135-138`) |
| `503 database_unavailable` | `database-updating` | `true` | a `DatabaseError` — locked, or not-a-database |
| …the same, continuously, past the threshold | `database-updating-stalled` | `false` | **Q3 — this story's only new number** |
| `500 internal_error` | `internal-error` | `false` | deterministic; `RETRIES_QUIETLY` forbids retrying it |
| a token this build does not know | `internal-error` | `false` | **Q5** — version skew is a bug, not a new state |

**Suites at the umbrella tip, measured not inherited:** Python **2464 passed, 1 skipped —
122.07 s** · frontend **568 passed, 31 files — 4.27 s**. (c3-8's record says 2461; its two Greptile
rounds added three after that record was written. Measure, do not inherit — that is the point.)

**Committed artifacts at `16976c5`, byte-identical unless Q4 rules otherwise:**
`ui/src/api/openapi.json` — **7 paths**, **12 components** (`ActiveDeck`, `ActiveDeckRequest`,
`Card`, `CardFace`, `CardSummary`, `DeckCardSummary`, `DeckDetail`, `DeckSummary`, `ErrorResponse`,
`FormatCheckReport`, `FormatCheckRow`, `HealthResponse`).

**SPA bundle SHA-256 (first 16), identical in `src/companion/app/static/assets/` and the `plugin/`
mirror:** `index-DE70muY2.js FAEEEA472ADD5078` · `index-DmxBiI94.css 0A3C142D84B5A98D` ·
`space-grotesk-latin-wght-normal-BhU9QXUp.woff2 0640890476FC1198`. **These WILL change** — this is
the first story since c2-10 to add a line of shipped frontend code, so a byte-identical bundle
would mean the wiring did not reach the module graph (`states.ts` is tree-shaken today for exactly
that reason). AC 24 asserts the bundle changed *and* that both trees agree.

**On measuring runtime:** c3-7 ledgered that this box spreads whole-suite runtime **49 s across
three runs of identical code**, so a before→after whole-suite claim is unsupportable from single
samples. AC 26 asks for the narrowest suite containing the change and more than one sample.

---

## Acceptance Criteria

### The fresh-install path — the story's headline, proved end to end

1. **A fresh install with no card database renders the "Card database not set up yet." panel, and
   no error page, stack trace or red styling appears anywhere** (epic `:1813-1816`, FR-22, UX-DR30,
   UX-DR33). Asserted at the **`App` root** by role and accessible name — `getByRole('region', {
   name: 'Card database not set up yet.' })` — the same shape `App.test.tsx:56` already uses for
   the static panel, so this AC *replaces* that assertion rather than sitting beside it. The
   no-red half is inherited structurally (`tests/token-usage.test.ts` bans `--negative`/`--caution`
   from the state panel's stylesheet) and is **stated as inherited**, not re-asserted.

2. **The panel is chosen from the wire token through `PANEL_FOR_REASON`, not from a status code
   and not from a `switch`.** Asserted by construction: a test that serves `503` with each of the
   two database tokens gets two *different* panels from one status. This is AD-16's whole argument
   made executable for the first time — *"nothing in the SPA keys off a bare status code"*.

3. **While that state is showing, the app is retrying on a backoff — not spinning, and not
   hammering** (epic `:1818-1820`). Asserted on a **fake timer** with the exact schedule Q2 fixes:
   the first retry lands at the base delay, the delay grows by the multiplier, and it **stops** at
   the ceiling rather than growing forever. No test sleeps for real time. The chosen numbers carry
   their arithmetic in the constant's own docstring, in the manner of `FETCH_SPACING_SECONDS`.

4. **The transition is automatic, and it is asserted as a transition rather than as two renders**
   (epic `:1822-1824`, FR-22). One mounted app, a poll that answers `503 database_not_initialized`
   and then `200` with deck names, **no remount, no user action, no `location.reload()`** — the
   panel becomes `no-active-deck` and the deck names appear beneath it. A test that unmounts and
   re-renders proves nothing about FR-22 and is the shape to avoid.

5. **A transient read failure shows the "Card database is updating." panel, distinct from the
   not-initialized one, and retries silently** (epic `:1826-1829`, AD-16, UX-DR33). Asserted as a
   *discrimination*: both are `503`, and the two panels differ. The distinction is the reason
   AD-16 exists (spine `:335`).

6. **The escalation to "Card database still updating." fires on continuous `database_unavailable`
   only — never on `database_not_initialized`** (Q3; closes the c1-6/c2-9 residue). Asserted both
   ways from one fake clock: continuous `database_unavailable` past the threshold escalates and
   **stops retrying** (`RETRIES_QUIETLY['database-updating-stalled'] === false`); continuous
   `database_not_initialized` for **ten times** the threshold does **not** escalate, because a
   multi-minute first build is the normal case and its own copy already says so. A single
   `200` in between resets the elapsed clock.

7. **`RETRIES_QUIETLY` is the retry contract and it is read at runtime, not paraphrased.** The
   poller consults the map rather than carrying its own list of retryable states, asserted by a
   test that flips one entry and observes the behaviour follow it. `internal-error` and
   `no-active-deck` must not be polled.

### Runtime safety at the wire boundary

8. **A wire value is validated before it reaches `StatePanel`'s `state` prop** (Q5; closes the
   c2-9 review residue). `STATE_COPY[state]` at `StatePanel.tsx:104` has no fallback branch — an
   unrecognised key yields `undefined` and `copy.headline` throws, which is *the error screen this
   story exists to ban*. (The ledger says `:92`; it is `:104` at `16976c5` — **verify the line
   before citing it**.) The validation lives at the boundary, is **total by construction**, and is
   asserted with a token that is not in the union at all, delivered as untyped JSON.

9. **A response body that is not the shape the contract promises does not crash the app.** A `503`
   with no body, a body that is not JSON, a body with no `reason`, and a network rejection are four
   distinct inputs and none of them may produce an unhandled render exception. Each is asserted.
   This is the same class as AC 8 and is separate from it because the failure arrives one layer
   earlier.

10. **The poller does not retry a request whose failure a retry cannot change** (closes the c3-2
    `503`-outranks-`400` residue). Measured at c3-2 and pinned in `test_routes_cards.py`: a
    malformed id sent to a backend with no database answers `database_not_initialized`, **not**
    `invalid_request`, because FastAPI solves dependencies before collecting validation errors. A
    client that treats both database tokens as "retry quietly" will therefore retry a request whose
    id can never succeed. The poll target this story owns has **no path parameter**, which is what
    makes it immune — **state that as the reason it is safe**, and state it where **c4-1** will
    read it, because c4-1's per-card fetches are not.

### The states nobody has ever looked at

11. **The five never-rendered panels are looked at in a browser and the result is recorded**
    (closes the c2-9 residue). `database-not-initialized`, `database-updating`,
    `database-updating-stalled` and `internal-error` become reachable in the running app for the
    first time; `disconnected` stays **c5-6's** and is looked at by temporarily passing the prop.
    What has never been seen: the **command chip** (only three states have one) and the
    **two-paragraph guidance/action stack** (`no-active-deck` has no guidance, so it exercises
    neither). Findings go in the record and on the **epic manual-testing checklist**, not into an
    unasserted claim.

### The wire contract, and the ruling this story owes

12. **`database_not_initialized`'s absence from the OpenAPI document is RULED, not surveyed**
    (Q4; closes the c3-1 review residue re-confirmed at c3-2). Whichever way it goes, the outcome
    lands in code or in the contract docs — never as a third "still open" note. If it is declared,
    `error_responses`' documented collapse behaviour fires **for the first time** (both 503 tokens
    in one entry naming each), `npm run gen:api` is run, and both generated files are regenerated
    and committed together — never hand-edited.

13. **The regeneration outcome is confirmed by running the generator and pasting
    `git status --porcelain`, not by argument.** `scripts/dump_openapi.py` says this story is *"not
    expected to be behaviour-only"* and that the thing to confirm is **which** changes are
    structural and which are prose. Both drift gates green from the same commit:
    `uv run pytest tests/unit/companion/test_openapi_contract.py`, and from `ui/`
    `npm run gen:types && git status --porcelain`.

14. **Whatever Q4 rules, `src/companion/contracts.py` gains the wire-visibility markers it has been
    missing** (Q9; closes the c3-7 review residue). c3-8 measured that `ErrorResponse`'s **class**
    docstring is published in full while `ErrorReason`'s attribute docstring twelve lines away is
    not — a 50/50 guess for every future author, documented only in `scripts/dump_openapi.py`. One
    line at each site. This is itself a wire decision, so it is checked against AC 13 rather than
    assumed harmless.

### The copy contract

15. **The un-quoted tails of `EXPERIENCE.md`'s copy rows are either gated or declined with a named
    home** (Q6; closes the c2-9 review residue). The verbatim gate captures `Headline:` and `Body:`
    only (`copy.test.ts:90-91`), so four clauses are contract nobody checks — and **three of the
    four constrain this story specifically**: the no-active-deck row's deck-list clause
    (`EXPERIENCE.md:63`), the stalled row's *"the client decides when 'a while' has passed (c3-9
    owns the threshold)"* (`:66`), and the internal-error row's *"Deterministic: this state never
    retries itself"* (`:68`). Their TypeScript mirrors are `RETRIES_QUIETLY`, the `decks` prop and
    the threshold this story ships. **Prose only is not an acceptable outcome.**

16. **No new user-facing copy ships, and `EXPERIENCE.md` is not edited.** Every string this story
    needs already exists and is already gated byte-for-byte. `ui/tests/copy.test.ts`,
    `copy-rules.test.ts` and `named-card-copy.test.ts` are predicted to pass **unchanged** — run
    them and say so. If a new sentence turns out to be needed, that is a `EXPERIENCE.md` amendment
    and a question, not a string.

### Boundaries, guards and the documentation that describes them

17. **The `states.ts` declarations gain their first runtime consumer, and any that stay unconsumed
    are named** (closes two residues, c2-9's and c3-2's). `PANEL_FOR_REASON` and `RETRIES_QUIETLY`
    are consumed by this story. `PLACEHOLDER_FOR_REASON` and `NO_UI_RESPONSE` are **c4-3's** and
    stay declarations — say so explicitly, because their own ledger entry says *"if neither
    consumes it, that is a signal the structure was over-built and it should be deleted rather than
    maintained"*, and this story is one of the two named consumers.

18. **The presentation-only posture survives contact with state, and where it stops is asserted
    rather than assumed** (Q1). `AppShell.tsx` and all eight primitives keep their exhaustive
    import lists and their hook bans — **run `tests/shell.test.ts` explicitly and paste it**. The
    new stateful code lives outside every directory those lists cover, and the guard for *that*
    boundary is this story's to build or to decline with a reason. Note the measured asymmetry:
    `src/App.tsx` is covered by neither list today.

19. **`ui/README.md` is corrected in the same commit as the code that falsifies it** (AC 4 of the
    C2 retro's standing "declared blind spot is still a claim" rule). At minimum: *"Not here yet"*
    (`:958-964`) currently assigns the fetch layer to c4-1 and `GET /api/decks` to c4-2; the
    left-column displacement note (`:980-984`) says c3-9 *"owns the transition"* in the future
    tense; and the **blind-spot table** gains this story's row — the c4-1/c4-2-facing facts about
    what the poller does, what it does **not** cover (per-card fetches, the WebSocket), and the
    threshold number.

20. **No database write path is opened and no backend boundary moves.**
    `tests/unit/companion/test_import_boundary.py` passes **unchanged with no exclusions added** —
    run explicitly and pasted. Stated because every story in this epic has been tempted by
    something, and because Q4 and Q7 both touch backend modules.

21. **`get_session`'s whole-request SHARED lock is ruled on rather than inherited silently**
    (Q7; closes the c3-1 review residue). `is_database_initialized(session)` autobegins a
    transaction and `get_session` yields without commit or rollback, so the read lock is held for
    the whole request; there is **no WAL pragma on the companion's engine**, while NFR-02 calls for
    WAL reads. **This is the exact concurrency FR-22 presumes** — a database created while the
    backend runs, picked up with no restart — and this story is the one that polls during an
    import. Either it is fixed with a test, or it is re-homed on **c10-3** by name with the
    measurement that says it does not bite today.

22. **All twelve `deferred-work.md` entries homed on this story are closed or explicitly re-homed
    by name.** R2's success criterion is that none is discovered mid-implementation, so the table
    is the contract:

    | # | Entry (source) | Expected disposition |
    | --- | --- | --- |
    | 1 | Stalled-state threshold + the `database-updating` → `database-updating-stalled` switch (c1-6 review → c2-9 ruling) | **Q3 — shipped** (AC 6) |
    | 2 | FR-22's fresh-install start has no live confirmation; empty data dir never run (c1-9) | **Task 8 — hand-run** (AC 25) |
    | 3 | The five states nobody can see yet (c2-9) | **AC 11 — looked at** |
    | 4 | `states.ts` has no runtime consumer (c2-9) | **CLOSED** (AC 17) |
    | 5 | A runtime-unknown `state` key crashes `StatePanel` (c2-9 review) | **Q5** (AC 8) |
    | 6 | The un-quoted tails of `EXPERIENCE.md`'s copy rows are ungated (c2-9 review) | **Q6** (AC 15) |
    | 7 | `database_not_initialized` undeclared in OpenAPI, on three routes and rising (c3-1 review, re-confirmed c3-2) | **Q4** (AC 12) |
    | 8 | `get_session` holds a SHARED lock for the whole request; no WAL pragma (c3-1 review) | **Q7** (AC 21) |
    | 9 | `503` outranks `400`: a malformed id with no database answers a retryable token (c3-2 review) | **AC 10** |
    | 10 | The panel-less token classification is gated by the compiler but read by nothing (c3-2 review) | **partly closed** — the panel half is this story's, the placeholder half stays **c4-3's** (AC 17) |
    | 11 | A body-less GET publishes `413 payload_too_large` (c3-2 round-2 review) | **Q8** |
    | 12 | `ErrorResponse`'s class docstring is published in full and nothing says so at the edit site (c3-7 review) | **Q9** (AC 14) |

23. **`deferred-work.md` gains this story's own residue with named homes** — at minimum whatever
    Q4, Q6, Q7 and Q8 decline, everything AC 11's browser pass finds, and the c4-1/c4-2 seam
    boundary Q1 draws. **No residue in prose only.**

24. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and
    the SPA bundle is **re-measured against Task 0's three hashes**. Unlike c3-6/c3-7/c3-8, the
    bundle is **expected to change** — a byte-identical bundle here means the new module never
    entered the graph. Both trees must agree byte-for-byte with each other; a disagreement is a
    finding to explain, not a rebuild to wave through (c3-1's finding 1).

### Testing

25. **The fresh-install path is hand-run against a real empty data directory, and the result is
    recorded** (closes deferral 2; C1 manual-checklist item 4). `PLANESWALKER_DATA_DIR` pointed at
    an empty directory, `uv run artificial-planeswalker companion`, open the printed URL, confirm
    the panel; then run `initialize_database` in an agent session (or plant a populated `cards.db`)
    and **watch the page transition without a refresh**. This is `EXPERIENCE.md`'s Flow 2
    (`:194-201`) walked end to end, and it is what closes **SC-4**. **No unit test substitutes for
    it** — the whole story is about what a human sees on a machine that has never run this before.

25b. **Where the tests live, so no file falls between the two vitest projects.** Component and
    hook behaviour is **colocated** under `ui/src/**` and lands in the **jsdom** project
    automatically (jest-dom matchers and `afterEach(cleanup)` come from `test-setup.ts` — nothing
    to set up per file). Guard-shaped suites that read source or config go in **`ui/tests/`** and
    land in the **node** project; `ui/tests/gate-geometry.test.ts` forbids `.tsx` test files there.
    Any backend change from Q4/Q7/Q8/Q9 is tested in **`tests/unit/companion/`**, beside
    `test_openapi_contract.py`, `test_committed_schema.py` and `test_deps.py` — reuse those
    modules' fixtures and **write no second seam**. No test touches the network, sleeps for real
    time, or writes outside `tmp_path` / a temporary data dir.

26. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the
    backoff-stops-at-the-ceiling assertion is paired with the growth that *does* happen; the
    "no escalation on `database_not_initialized`" assertion is paired with the escalation that
    *does* happen on `database_unavailable`; the unknown-token clamp is paired with a known token
    that maps normally; any new import/hook guard is paired with a planted breach **spelled to
    evade** (c3-3's headline finding: a guard keyed on the syntax its own firing test uses caught
    0 of 12 planted evasions).

27. **At least five mutation probes are run, verified before the verdict and reverted from a file
    backup — never from `git`** (standing agreement; c3-7 Debug Log 3: `git checkout` discarded
    uncommitted work mid-probe): (a) the **backoff ceiling** removed, so the delay grows forever —
    invisible to every "it retries" test; (b) the **`RETRIES_QUIETLY` consult** replaced with
    "always retry", so `internal-error` is hammered behind a calm panel; (c) the **elapsed-clock
    reset** removed, so one good response no longer clears the stalled countdown; (d) the
    **runtime validation** removed, so an unknown token reaches `STATE_COPY` — this must produce
    the render crash AC 8 exists to prevent, and if it does not, the validation is not where the
    story thinks it is; (e) the **escalation guard** removed, so a first build escalates to
    stalled; and (f) — the epic's shared review theme in this story's costume — the transition
    driven by a **remount** rather than by state, which passes every "the panel is right" assertion
    while FR-22's *"no manual refresh"* is false. **Paste each result and read it before filing
    it** (c3-6's probe (f) found a real hole; c3-7's probe (d) found a gap in its author's own
    coverage).

28. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus
    the frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`,
    `build`) and both drift checks. Suite counts stated as *before → after* from the measured
    baseline (**2464/1 skipped** · **568/31**); the runtime claim is made on the narrowest suite
    containing the change over more than one sample, and no whole-suite delta on this box is read
    as signal.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is **`16976c5`** (PR #36,
        c3-8, merged 2026-08-02); cut `feat/companion-c3-9-fresh-install` from it
  - [x] Run and record with **durations**: `uv run pytest` (expect **2464 passed, 1 skipped**),
        `ruff check`, `ruff format --check`, `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (expect
        **568 passed, 31 files**), `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/`
        mirror (AC 24); record the committed `paths` (expect **7**) and `components` (expect **12**)
  - [x] **Verify the "no runtime behaviour" table yourself**, read-only: zero `fetch(`, zero hook
        calls, zero timers, zero `zustand` imports in `ui/src`. If any is non-zero, the story's
        premise has changed and the record says so
  - [x] **Read `states.ts` end to end, and `RETRIES_QUIETLY` twice.** It is the specification

- [x] **Task 1 — The seam, decided before any code** (AC 18, 19, 25b; Q1)
  - [x] Apply Q1's ruling: where the fetch lives, whether it is a store slice or a hook, and what
        exactly c4-1 and c4-2 inherit versus replace
  - [x] Write the boundary down where the next author works — `ui/README.md`'s *"Not here yet"*
        and the module's own header — **in the same commit as the first fetch**
  - [x] Decide and implement (or decline with a reason) the posture guard for the new directory
  - [x] Place the new files per AC 25b **before** writing them; a `.tsx` test under `ui/tests/` is
        a red gate and a `tests/` file importing an app module needs `npx tsc -b --force` to see

- [x] **Task 2 — The wire boundary** (AC 2, 8, 9, 10; Q5)
  - [x] The one place a response becomes a `StateKey`: token → `PANEL_FOR_REASON` → panel, with
        an unknown or absent token clamped per Q5
  - [x] Unit tests **before** wiring: four malformed inputs (no body, non-JSON, no `reason`,
        network rejection) and one out-of-union token
  - [x] The `ErrorReason` alias comes from `src/api/schema.ts` — no re-declared shape anywhere
        (`tests/wire-contract.test.ts` will say so if not)

- [x] **Task 3 — The poller** (AC 3, 6, 7; Q2, Q3)
  - [x] The backoff, with each constant carrying its arithmetic in its own docstring
  - [x] `RETRIES_QUIETLY` consulted at runtime, never paraphrased
  - [x] The elapsed clock for the stalled escalation, keyed to `database_unavailable` only, and
        **reset by any non-`database_unavailable` outcome**
  - [x] Every timing test on fake timers; none sleeps for real time

- [x] **Task 4 — The transition** (AC 1, 4, 5)
  - [x] Wire it into `App.tsx`, replacing the static `state="no-active-deck"` (`App.tsx:73`) and
        its comment block, which is written entirely about that constant
  - [x] `App.test.tsx:47-57` currently asserts the static panel and its comment names this story
        as the inheritor — update it to assert the wire-driven choice
  - [x] The transition test: **one mount**, two responses, no remount, no reload

- [x] **Task 5 — The backend rulings** (AC 12, 13, 14, 20, 21; Q4, Q7, Q8, Q9)
  - [x] Apply Q4 to `error_responses` / `build_app()`; if declared, confirm the collapse behaviour
        fires and regenerate both artifacts together
  - [x] Apply Q9's markers in `contracts.py`; check them against AC 13 rather than assuming
  - [x] Apply or re-home Q7 (WAL / lock hold) and Q8 (413 on body-less GETs), each with a test or
        a ledger entry — never prose
  - [x] Run `test_import_boundary.py` explicitly and paste it

- [x] **Task 6 — The copy contract** (AC 15, 16; Q6)
  - [x] Apply Q6 to the four un-quoted tails: extend the gate, or decline with a named home
  - [x] Run `copy.test.ts`, `copy-rules.test.ts` and `named-card-copy.test.ts` explicitly and
        state that they passed **unchanged**

- [x] **Task 7 — Docs, records, mirror** (AC 17, 19, 22, 23, 24)
  - [x] Work the twelve-entry inherited-deferral table; close or re-home each **by name**
  - [x] `ui/README.md`: *"Not here yet"*, the left-column displacement note, and the blind-spot row
  - [x] `scripts/dump_openapi.py`: what this story actually did to the wire, and what is next
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle (**expected to change**)
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`; set status to `review`

- [ ] **Task 8 — The hand-run, which nothing substitutes for** (AC 11, 25)
  - [~] `PLANESWALKER_DATA_DIR` at an empty directory → the panel → a real
        `initialize_database` → the transition, with **no refresh**. Record what happened —
        **DONE at the HTTP layer** (empty dir → companion starts, no `cards.db` planted →
        `503 database_not_initialized` → `cards.db` planted with the server running → `200` with
        real deck names, same process). **NOT DONE in a browser**: nobody watched the page.
  - [ ] Look at all five newly-reachable panels in a browser — the command chip and the
        two-paragraph stack especially — and record the findings for the epic checklist —
        **NOT DONE.** Four of the five are now *reachable* (`disconnected` stays c5-6's), and the
        recipe is in `deferred-work.md`; the look-at itself needs eyes and is on the epic
        manual-testing checklist.

- [x] **Task 9 — Probes** (AC 26, 27)
  - [x] Six mutation probes, each verified and reverted **from a file backup**; paste and **read**
        each result

- [ ] **Task 10 — Same-day three-layer review before the PR** *(Brad runs this — `dev-story` stops
      at Task 9 with status `review`)*
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before the PR —
        run 2026-08-02: 1 decision (resolved), 13 patches (all applied), 2 defers (ledgered),
        1 dismissed. Findings below.
  - [x] Apply patches, re-run every gate, paste the output — Python **2472 passed, 1 skipped**
        (218.77 s); `ruff check` clean; `ruff format --check` 305 files clean; `mypy src/` and
        `--platform win32` clean (89 files each). Frontend **730 passed, 36 files** (4.60 s);
        `lint`, `format:check`, `npx tsc -b --force`, `build` all clean. Bundle rebuilt →
        `index-DVyKlzKd.js ED89F6474885A685`; plugin mirror `diff -r` identical.
  - [x] Raise the PR into `feat/companion-c3` — **PR #37**, 2026-08-02
  - [x] **Greptile round 1: 4/5, one P2 — CONFIRMED, in review-added code (third story running:
        c3-7, c3-8, now c3-9).** The review-added `AbortSignal.timeout` had an undeclared browser
        floor, and the failure without it is the worst this module can produce: in a runtime
        without the API the constructor throws INSIDE the `try`, so every poll reads as
        `unreachable` before `fetch` ever runs — a calm panel retrying forever against a healthy
        backend it never contacts. Reachability is marginal (`vite.config.ts` sets no
        `build.target`, so the bundle's own `baseline-widely-available` floor — Chrome/Edge 107+,
        Firefox 104+, Safari 16+ — postdates the API everywhere: Chrome 103, Firefox 100,
        Safari 15.4), but the shape masquerades as a lost backend. Patched per Brad's ruling
        (option 1): a `typeof` guard degrades an out-of-floor browser to NO timeout — never to
        permanently unreachable — with the floor subsumption declared at the guard, plus a test
        stubbing the API away and asserting the request still goes out and the answer is still
        read. Frontend 730 → **731 passed**; all gates green; bundle → `index-CfiLRdVp.js
        0E1DE820FD0B2B88`, mirror `diff -r` identical.

### Review Findings (bmad-code-review, 2026-08-02)

- [x] [Review][Decision] AC 11's browser look-at and AC 25's watched transition are NOT done —
      both declared in the record and re-homed to the epic manual-testing checklist with a recipe.
      **Resolved: re-home accepted** — the epic checklist owns the look-at; recipe recorded in
      `deferred-work.md`.
- [x] [Review][Patch] Poller `stop()`/`start()` reuse races a stale in-flight read and leaks a
      second timer chain; `delay`/`lastOutcome`/`unavailableSince` survive `stop()`, so stopped
      wall-time counts toward the 60 s threshold [ui/src/state/poller.ts:135-232] — **fixed**:
      generation counter carried by every tick and timer; all schedule state resets on `start()`;
      paired tests (stale-drop + one-chain, restart-resets)
- [x] [Review][Patch] No fetch timeout: a backend that accepts the connection but never responds
      wedges the poll forever behind a calm panel — no retry, no escalation
      [ui/src/api/decks.ts:127] — **fixed**: `AbortSignal.timeout(READ_TIMEOUT_MS = 10_000)`,
      arithmetic against `database.py`'s 5 s busy timeout in the constant's docstring; three tests
- [x] [Review][Patch] Stalled escalation is pure wall-clock (`Date.now`): suspend/resume or
      background-tab timer throttling escalates after as few as two refusals, contradicting the
      docstring's "at least six consecutive refusals" — and the escalated state is terminal
      [ui/src/state/poller.ts:194] — **fixed**: `STALLED_MIN_REFUSALS = 4` observation floor
      alongside the elapsed clock; never binds on the live schedule (asserted); suspend test pins
      both halves
- [x] [Review][Patch] Every decided poll emits a fresh `{panel, decks: []}` object, re-rendering
      the whole app per tick with nothing changed [ui/src/state/poller.ts:197] — **fixed**:
      emissions deduplicated against the last update; change-still-emits paired test
- [x] [Review][Patch] `identify()` stringifies a `null` reason as `"error:null"`, colliding with a
      hypothetical literal token and merging distinct malformed refusals into one identity
      [ui/src/state/poller.ts:169-170] — **fixed**: token-less refusal is bare `'error'`, which
      `'error:' + token` can never spell
- [x] [Review][Patch] A second `useSystemState` consumer silently spawns a second, independent
      poller; nothing pins single-consumership [ui/src/state/systemState.ts:55-63] — **fixed**:
      the one-consumer rule written loudly on the hook (read `useSystemStore` directly instead),
      per this codebase's named-once convention
- [x] [Review][Patch] `posture.test.ts`'s comment stripper eats string literals containing `/*` or
      `//`, blinding the identifier-family scan after them [ui/tests/posture.test.ts, `codeOf`]
      — **fixed**: regex replaced with a string-aware walker (string/template contents kept for
      the import rules); regex-literal residue declared; firing + silent tests added
- [x] [Review][Patch] `copy-tails.test.ts` reads `RETRIES_QUIETLY` source without comment-stripping
      — a commented-out entry would still satisfy the gate (backstopped by `tsc` today)
      [ui/tests/copy-tails.test.ts] — **fixed**: body comment-stripped before the entry regex;
      commented-out-entry test added
- [x] [Review][Patch] Test gap: a `200` with a non-JSON body (`response.ok && body === null`) is
      the one branch combination no test pins [ui/src/api/decks.test.ts] — **fixed**: pinned
      (captive-portal shape → `{kind: 'error', reason: null}`)
- [x] [Review][Patch] Dev Agent Record File List omits `tests/unit/companion/test_routes_cards.py`
      [this file, File List] — **fixed**: listed, with what changed in it
- [x] [Review][Patch] AC 23's Q1 seam-boundary residue has no `deferred-work.md` entry — the new
      section's preamble reinterprets the AC's letter [deferred-work.md] — **fixed**: ledger entry
      added, homed on c4-1/c4-2 by name
- [x] [Review][Patch] The first-frame panel choice (`no-active-deck` before the first answer) is
      argued only in a module header; no ruling covers it — one sentence in the record
      [ui/src/state/systemState.ts + this file] — **fixed**: recorded in Completion Notes
- [x] [Review][Patch] Q3's ruling reads "as proposed" but the proposal's arithmetic ("four
      attempts") was silently corrected to six in the shipped docstring [this file, Q3 ruling]
      — **fixed**: correction recorded in the ruling table
- [x] [Review][Defer] Alternating `database_unavailable`/`database_not_initialized` resets the
      backoff on every flip, pinning the poll near 2 s during an interleaved import
      [ui/src/state/poller.ts:174-177] — deferred: Q2 rules reset-on-any-change; cost ledgered
      against c4-1, which copies this seam
- [x] [Review][Defer] `database-updating-stalled` permanently forfeits FR-22's self-transition —
      after the user fixes the database, only a manual refresh recovers
      [ui/src/state/poller.ts:217 + states.ts:233] — deferred: `RETRIES_QUIETLY` contract
      (states.ts is read-only this story); ledgered for the C3 retro

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| Every non-2xx carries a closed `reason` token mapping 1:1 to a UX state; **nothing in the SPA keys off a bare status code** | AD-16, spine `:329-345` | AC 2 is this rule's first executable proof |
| A new token and the UI state it drives ship together | AD-16, C2 retro R1 | This story adds **no token** — every state it renders was paired long ago |
| The database engine is lazy and its absence is a **served UI state**, not a startup failure | AD-10, spine `:225-239` | The backend half of FR-22 is done; this is the client half |
| Readiness is re-probed every request and never cached | c1-6, `deps.py:245-247` | The `503` → `200` flip needs no restart and no cache-busting |
| The status is derived from the token, never chosen at the call site | `errors.py:46-57` | A client reading the status alone is reading the weaker half |
| One generator, from the backend's own `app.openapi()`; never hand-edit `openapi.json` | AD-12 | Q4's declaration is a regeneration, not an edit |
| A class docstring on a wire model is published **in full**; an attribute docstring on a `Literal` alias is **not** | c3-8, measured | Q9 writes that down at the edit sites |
| Copy lives in `EXPERIENCE.md` and is gated byte-for-byte | c2-9 | This story ships **no copy** |
| `zustand` is the one store; no second data-fetching or state library | AD-12, `package-contract.test.ts` | Q1 chooses within that constraint, never around it |
| Primitives and the shell are presentation-only, hook-free, asserted by exhaustive import lists | c2-6, c2-7 | The new state lives outside them; AC 18 says where the line is |
| A geometry literal is legal **only** with a true `DESIGN.md` citation | c2-6 / c2-8 | This story should need none — it adds behaviour, not layout |
| Ban the family, never enumerate members | C2 retro, standing | Any new guard is family-keyed |
| Probe your own guard before review does | C2 retro, standing | AC 27's six probes are not optional |
| A declared blind spot is still a claim | C2 retro | AC 19's README edits are part of the code change, not follow-up |
| Claims require verification | standing | Run the generator; hand-run the install; paste real output |

### The nine things this story must not break

1. **`ui/tests/copy.test.ts`** — six rows parsed, six panels, every headline and every re-joined
   body byte-identical to `EXPERIENCE.md`. Predicted green **unchanged** (AC 16). If Q6 extends the
   gate, the extension is additive and the six existing assertions stay exactly as they are.
2. **`ui/tests/shell.test.ts`'s exhaustive import lists** — nine of them
   (`AppShell` + eight primitives). A store import, a fetch helper or a hooks module inside any of
   those directories fails the build, and that is the guard working, not an obstacle.
3. **`ui/tests/wire-contract.test.ts`** — no re-declared wire shape anywhere outside `src/api/`,
   and no direct import of `./types`. A new fetch module is exactly where this gets violated.
4. **`ui/tests/copy-rules.test.ts`** — user-facing prose only in a declared `COPY_MODULES` entry,
   and no `!`, emoji or "something went wrong" in **any** string under `src/`. A new module with a
   friendly error string fails here.
5. **`src/api/schema.test.ts`'s ten-member `ErrorReason` union**, and `states.ts`'s `satisfies`
   clause — both are **typecheck** gates, not test gates. `npm test` stays green over a broken
   union; `npx tsc -b --force` is what catches it (`ui/README.md:179-181`).
6. **`tests/unit/companion/test_import_boundary.py`** — AST-only, unchanged, no exclusions.
   *"A guard satisfied by obfuscation is theatre."*
7. **`test_openapi_contract.py`'s byte comparison** and `test_committed_schema.py`'s whole-artifact
   pin — a docstring edit you did not mean to make is a red CI, and the fix is regeneration, never
   a hand edit. Q4 and Q9 both edit wire-visible modules.
8. **`test_app.py::test_startup_failure_propagates`** — publishing the discovery file is still the
   only startup step that may fail a launch. Nothing in this story should touch it; if Q7 adds a
   WAL pragma to engine creation, re-derive that claim rather than assuming it.
9. **`App.test.tsx`'s three existing assertions.** Two survive untouched (the `main` landmark, the
   `h1`); the third (`:47-57`) is *about* the static panel and its own comment names this story as
   the thing that replaces it. Replacing it is correct; deleting it is not.

### Source tree — what exists, what this story touches

```
ui/src/
  App.tsx                  EDIT — the static `state="no-active-deck"` (:73) becomes the
                                  wire-driven choice; the 55-line comment block above it is
                                  written entirely about that constant and is rewritten, not
                                  amended
  App.test.tsx             EDIT — :47-57 asserts the static panel; it becomes the transition
  api/                     ADD?  — the fetch helper, if Q1 puts it here. `schema.ts` is the only
                                  door to the generated types and stays that way
  <the new stateful module> ADD  — the poller, the backoff, the elapsed clock and the wire→panel
                                  boundary. Location and shape are Q1's
  components/StatePanel/
    states.ts              READ ONLY — the specification. Consumed, not edited
    copy.ts, StatePanel.*  READ ONLY — no copy ships and the panel stays presentation-only
src/companion/
  app/main.py              EDIT? — `build_app()`'s per-include `responses`, if Q4 declares
  app/deps.py              EDIT? — the WAL pragma / lock hold, if Q7 fixes rather than re-homes
  contracts.py             EDIT (comments) — Q9's wire-visibility markers. WIRE-VISIBLE: verify
scripts/dump_openapi.py    EDIT (docstring) — what this story did to the wire, and what is next
ui/README.md               EDIT — "Not here yet", the left-column note, the blind-spot row
ui/src/api/openapi.json    REGENERATED? — only via `npm run gen:api`, never by hand
ui/src/api/types.d.ts      REGENERATED? — likewise, and committed in the same commit
src/companion/app/static/  REBUILT — expected to CHANGE (AC 24)
plugin/                    REBUILT — must match `static/` byte-for-byte
_bmad-output/implementation-artifacts/deferred-work.md   EDIT — twelve closed/re-homed, plus residue
```

### Project structure notes — the conventions a new module inherits

**Frontend.** One directory per component, three files, **no barrels** (`ui/README.md:397-413`);
`src` is already in `tsconfig.app.json`'s `include`, so a new module under `src/` needs **no**
configuration change — if one seems to, the file is in the wrong place. A **new top-level
directory under `ui/`** (not under `src/`) does need adding to a tsconfig `include`, or ESLint's
`projectService` errors on every file in it (`ui/README.md:950-956`). Class names are flat
kebab-case; a component module may export the component and types but **not** a helper function or
an array/object constant (`react-refresh/only-export-components`, measured in c2-7) — give a helper
its own module, as `src/components/filled.ts` and `Badge/tones.ts` do. `eslint-plugin-react-hooks`
is installed and its rules apply to the first hook this repo has ever written, including the
exhaustive-deps rule; `verbatimModuleSyntax` is on, so type imports are `import type`.

**Backend.** Python 3.12, `mypy --strict` on `src/` (both platforms — `--platform win32` is a
separate CI invocation), ruff `line-length = 100`, Google-style docstrings on every public
function, module docstrings required, `datetime.now(UTC)` only, `%`-style lazy logging args.
`src/companion/app` is async; `src/companion/contracts.py` is a **leaf** and may import only the
stdlib, pydantic, httpx, `src.paths` and sibling leaves — `test_import_boundary.py` enforces it.
Run everything through `uv run`.

### Open questions — answer these before writing code

**Q1 — Where does the fetch live, and what do c4-1 and c4-2 inherit?**
*Proposed:* **create the store's first slice** (a `system` slice) plus one narrow request helper
under `src/api/`, and declare both as the seam c4-1 **extends** rather than replaces. Rationale:
AD-12 already rules that zustand is the one store and bans a second state mechanism, so a
throwaway standalone hook would be deleted by c4-1 and would leave a second spelling of "fetch
JSON" behind it in the meantime. c4-1 then adds the card cache and the in-flight deduping to a
store that exists; c4-2 adds the deck bootstrap to a poller that already calls `GET /api/decks`.
*The alternative* — a self-contained hook with no store — is cheaper this week and costs c4-1 a
migration; it is worth taking only if Q1 also decides that this story's poll should not survive
c4-1 at all. **Whichever is chosen, `ui/README.md:958-964` is edited in the same commit** (AC 19).

**Q2 — The poll schedule.** *Proposed:* base **2 s**, multiplier **2**, ceiling **30 s**, no
jitter (one client, one localhost backend, nothing to thunder against). Arithmetic to put in the
docstring: a first build takes minutes, so a fixed 2 s poll would issue ~150 requests against a
backend that is deliberately busy importing; a ceiling above 30 s makes the *"comes alive on its
own"* promise feel broken to a human watching the screen. The backoff **resets to base on any
change of outcome**, so the transition is fast even after a long wait.

**Q3 — The stalled threshold, and what it escalates.** *Proposed:* **60 s of continuous
`database_unavailable`**, and **`database_unavailable` only**. Arithmetic: at Q2's schedule that is
at least four consecutive failed attempts with the last two at the ceiling, so a single slow write
burst cannot escalate. `database_not_initialized` **never** escalates — a multi-minute first build
is its normal case and its own copy says so. Any non-`database_unavailable` outcome resets the
clock. This is the number `EXPERIENCE.md:66` has been holding open for this story since c2-9.

**Q4 — Declare `database_not_initialized` in OpenAPI?** *Proposed:* **yes, on the database-backed
includes only** — the exact set `main.py:465-466` already groups. It is the most common 503 a fresh
install ever sees; the UI's whole fresh-install path switches on it; `error_responses`' documented
collapse behaviour was written for precisely this and has never fired; and the alternative is a
contract that under-documents the one state this story exists to render. The cost is a real wire
diff and a regeneration — which AC 13 requires anyway. **Do not** add it to `/health` or the
active-deck router, which cannot answer it.

**Q5 — The runtime-validation shape.** *Proposed:* validate **at the boundary**, and clamp an
unknown or absent token to **`internal-error`**. A token this build does not recognise means a
backend/frontend version skew, which is a bug — `internal-error`'s copy (*"The companion hit a
bug… Restart the companion"*) is true for it, and `RETRIES_QUIETLY` already forbids retrying it.
`StatePanel` gains **no** fallback branch: it stays presentation-only and the totality is proved at
the one place values enter. AC 27's probe (d) is what keeps that claim honest.

**Q6 — The un-quoted copy tails.** *Proposed:* **extend the gate**, for the three tails that
constrain this story (the deck-list clause, the threshold clause, the never-retries clause) and
leave the connection-pill tail to **c5-6**. Three of the four are assertions *about this story's
own behaviour* living in an ungated part of the artefact; gating them is a handful of lines in a
parser that already walks every table line. If it is declined, it is re-homed by name — not left
as a fourth "candidate home" note.

**Q7 — WAL and the whole-request read lock.** *Proposed:* **measure first, then rule.** Run a real
`initialize_database` against a backend that is polling (Task 8 does this anyway) and see whether
the poll's SHARED lock actually stalls the writer. If it does, that is FR-22 failing in the exact
scenario this story owns, and the WAL pragma belongs here. If it does not, re-home on **c10-3**
with the measurement attached — a re-home with a number is worth more than a fix without one.

**Q8 — The 413 on body-less GETs.** *Proposed:* **record it as a known wart in the contract docs
and re-home**, rather than curating `error_responses` per method. The ledger homes it on *"the next
story that touches `error_responses`' declaration helper, else c3-9"* — and Q4 touches the *caller*,
not the helper. Curating per method is a real change to a shared declaration site with six routes
of blast radius, made in a story whose frontend half is already the largest in the epic.

**Q9 — The `contracts.py` wire-visibility markers.** *Proposed:* **as ledgered** — one line above
`ErrorResponse`'s class docstring saying it is published in full, and one above `ErrorReason`'s
saying it is not. c3-7 declined it because *"even a comment edit is a wire decision that would want
its own regeneration"*; this story regenerates anyway under Q4, so the objection dissolves.

**Q10 — Does this story render `disconnected`?** *Proposed:* **no.** It is `CLIENT_ONLY_STATES`'
other member and its condition is the WebSocket backoff exhausting its retries — **c5-6's**. This
story looks at it in a browser (AC 11) by passing the prop by hand, and selects it never.

### References

- Epic story text: [epics-companion-app.md#Story 3.9](_bmad-output/planning-artifacts/epics-companion-app.md#L1805-L1833)
- FR-22, SC-4, NFR-02: [prd.md](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L104) · [#L161](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L161) · [#L180-L182](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md#L180-L182)
- AD-10, AD-11, AD-12, AD-16: [ARCHITECTURE-SPINE.md](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L225-L345)
- UX-DR30 (state panel), UX-DR33 (copy): [epics-companion-app.md#L500-L523](_bmad-output/planning-artifacts/epics-companion-app.md#L500-L523)
- The copy rows and Flow 2: [EXPERIENCE.md#L61-L70](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L61-L70) · [#L194-L201](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L194-L201) · the fresh-install and bulk-refresh rows [#L114-L115](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L114-L115)
- The specification written for this story: [states.ts](ui/src/components/StatePanel/states.ts) — `PANEL_FOR_REASON` [#L91](ui/src/components/StatePanel/states.ts#L91), `CLIENT_ONLY_STATES` [#L200](ui/src/components/StatePanel/states.ts#L200), `RETRIES_QUIETLY` [#L223](ui/src/components/StatePanel/states.ts#L223)
- The panel and its words: [StatePanel.tsx#L103-L146](ui/src/components/StatePanel/StatePanel.tsx#L103-L146) · [copy.ts#L89-L162](ui/src/components/StatePanel/copy.ts#L89-L162) · the verbatim gate [copy.test.ts#L82-L162](ui/tests/copy.test.ts#L82-L162)
- The static panel this story replaces: [App.tsx#L72-L74](ui/src/App.tsx#L72-L74) · [App.test.tsx#L47-L57](ui/src/App.test.tsx#L47-L57)
- The 503 producer and the readiness rule: [deps.py#L236-L279](src/companion/app/deps.py#L236-L279) · [database.py#L125-L155](src/data/database.py#L125-L155)
- The token/status pairing and the declaration helper: [errors.py#L46-L57](src/companion/app/errors.py#L46-L57) · [errors.py#L171-L229](src/companion/app/errors.py#L171-L229) · [main.py#L460-L472](src/companion/app/main.py#L460-L472)
- The wire alias module: [schema.ts](ui/src/api/schema.ts) · the generation contract [ui/README.md#L127-L171](ui/README.md#L127-L171)
- The seam boundary this story must correct: [ui/README.md#L958-L984](ui/README.md#L958-L984)
- The twelve inherited deferrals: [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — search `c3-9`
- C2 retro ruling R2 (this story stays ONE story; the deferrals are ACs at context time): [sprint-status.yaml#L488-L491](_bmad-output/implementation-artifacts/sprint-status.yaml#L488-L491)
- Project rules: [project-context.md](_bmad-output/project-context.md)

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Opus 5, 1M context), via the `bmad-dev-story` workflow.

### Debug Log References

**1 — The story's own line citation was stale, and the throw is one line earlier than described.**
The ledger and AC 8 both point at `STATE_COPY[state]` and predict `copy.headline` throws. Measured
at `16976c5`: the index is `StatePanel.tsx:104` (the ledger says `:92`), and probe (d) shows the
crash is actually `TypeError: Cannot read properties of undefined (reading 'body')` — thrown by
`guidanceOf(copy)` on the line *after* the index, before `copy.headline` is ever read. Same class,
same fix, one line off. Corrected in `deferred-work.md` rather than left to be re-found.

**2 — A `tests/` file importing an app module broke `tsc` while `npm test` stayed green — a KNOWN
blind spot that caught me anyway.** `ui/tests/` is `tsconfig.node.json` (`nodenext`, `lib: ES2023`,
`types: ["node"]`), and importing `DECKS_PATH` / `RETRIES_QUIETLY` / `STALLED_AFTER_MS` dragged
`decks.ts`, `poller.ts` and `states.ts` into that project: **twelve** errors — `TS2835` on every
relative import (nodenext wants extensions), `TS2353` on `RequestInit.cache` (a DOM type the node
project has no lib for), and three cascading `TS2344`s from `states.ts`' type-level asserts once
its own import had failed. `npm test` was green throughout. `ui/README.md`'s blind-spot table
already carries this row, including *"cascading into errors that name the importee's type asserts,
not the import"* — so this is the row earning its place, not a discovery, and the first draft of
`copy-tails.test.ts` claimed it as new until the table was read. Resolution: read the mirrors out
of SOURCE, which is what every other suite in `ui/tests/` does.

**3 — `satisfies` preserves literal types, so AC 7's "flip one entry" needs a cast.**
`RETRIES_QUIETLY['internal-error']` is typed `false`, not `boolean`, so the compiler refuses the
flip. The cast in `poller.test.ts` is the assertion rather than a workaround — the test is
deliberately violating a contract the runtime is supposed to be reading — and it is restored in a
`finally` with a post-condition check, so the ban is not silently disabled for whatever runs next.

**4 — The guards only see COMMITTED files, and four assertions passed vacuously until `git add`.**
`posture.test.ts` (like `wire-contract.test.ts` and `gate-geometry.test.ts`) keys on `git ls-files`.
Before the new modules were tracked, "there is exactly one door to the network" found **zero** doors
and the non-vacuity anchor was what caught it. Worth knowing when adding a guard alongside the code
it guards.

**5 — Task 8's browser half was not run, and no unit test substitutes for it.** This environment
has no browser automation (`playwright`, `puppeteer`, `selenium` all absent) and installing one is
a new dependency the story does not call for. Everything scriptable WAS run live and is recorded
below; what nobody has seen is the page transitioning and the four newly-reachable panels rendered
by a real engine. Stated as unverified rather than inferred from the jsdom tests.

**6 — Probe (g) confirmed the posture guard's declared split rather than its strength.** A breach
planted in a real `StatePanel.tsx` — `import { useSyncExternalStore as sync } from 'react'` plus a
call through `globalThis[String.fromCharCode(102)]` — was caught by the IMPORT door (both the new
tree-wide rule and `shell.test.ts`'s per-file list) and **not** by the identifier patterns. That is
exactly what the file's header declares, and it is why the door is the primary layer.

### Completion Notes List

**All ten open questions ruled; nine as proposed, one refined with a reason.**

| Q | Ruling |
| --- | --- |
| Q1 seam | **As proposed.** `src/api/decks.ts` (one door) + `src/state/` (the store's first slice). Declared as the seam **c4-1 extends**, not a throwaway it replaces. `ui/README.md` corrected in the same commit. |
| Q2 schedule | **As proposed.** base 2 s, ×2, ceiling 30 s, no jitter; resets to base on any change of outcome. Each constant carries its arithmetic. |
| Q3 threshold | **As proposed.** `STALLED_AFTER_MS = 60_000`, armed by `database_unavailable` and nothing else, reset by every other outcome. *Correction the ruling first left unrecorded (review):* the proposal's arithmetic said **four** consecutive attempts; the true schedule gives **six** (t = 0, 2, 6, 14, 30, 60 s) — the shipped docstring carries the right sum. The review also added `STALLED_MIN_REFUSALS = 4` as a floor of real observations, because `Date.now()` keeps counting through a suspend or a throttled background tab while the schedule does not. |
| Q4 OpenAPI | **As proposed.** Declared on the database-backed includes only. Five operations changed; `error_responses`' collapse fired for the first time. |
| Q5 validation | **As proposed for tokens, REFINED for transport.** Unknown/absent/panel-less token → `internal-error`, at one total boundary. A `fetch` **rejection** is treated separately: no response means no state, so the panel stands and the poll retries. Reason: `RETRIES_QUIETLY['internal-error']` is `false`, so clamping a transient blip there would stop the poll permanently — the opposite of FR-22. `disconnected` is c5-6's (Q10) so it cannot be claimed; the residue is ledgered against c5-6. |
| Q6 copy tails | **As proposed.** Three gated in a new file; the connection-pill tail declined and re-homed on **c5-6** by name. |
| Q7 WAL / lock | **Measured, then re-homed on c10-3** with numbers (see below). |
| Q8 413 | **As proposed.** Recorded as a known wart in `scripts/dump_openapi.py`; re-homed on **c5-5** by name (the story that makes the 413 real). |
| Q9 markers | **As proposed**, and the measurement dissolves c3-7's objection: a `#` comment above a wire model produces **no wire diff** — confirmed by running the generator, not by argument. |
| Q10 disconnected | **As proposed.** Never selected. |

**What shipped.** Four source modules and the first runtime behaviour in `ui/src`:
`api/decks.ts` (the one `fetch`, a total outcome union that never rejects), `state/panel.ts`
(`panelFor` — the one place a wire value becomes a `StateKey`, total by construction, consuming
`PANEL_FOR_REASON`'s key set as the runtime membership test so there is still no second list),
`state/poller.ts` (the backoff, the elapsed clock, `RETRIES_QUIETLY` indexed at runtime) and
`state/systemState.ts` (zustand's first consumer since c2-1, plus the one hook). `App.tsx`'s static
`state="no-active-deck"` became the wire-driven choice.

**Two new guards, both family-keyed.** `tests/posture.test.ts` states the presentation-only rule
over the WHOLE component tree rather than per directory — *a component may take a TYPE from
anywhere and a VALUE from nowhere but its own tree and React* — which closes the "tenth primitive
arrives with no list entry" hole `shell.test.ts`'s nine enumerated lists leave open, and pins
`src/api/decks.ts` as the only network door in `ui/src`. `tests/copy-tails.test.ts` gates three of
`EXPERIENCE.md`'s four un-quoted tails against their TypeScript mirrors in both directions.

**Q7, measured on a real running companion** (writer takes `BEGIN IMMEDIATE` ×5, quiet then under
four saturating `GET /api/decks` threads at ~0.16–0.31 s each):

| Journal mode | writer QUIET (median / max) | writer CONTENDED (median / max) |
| --- | --- | --- |
| `wal` | 0.0097 s / 0.0125 s | **0.0080 s / 0.0092 s** — no effect at all |
| `delete` | 0.0079 s / 0.0093 s | 0.0079 s / **0.2131 s** — one read's worth of wait |

Three findings: the companion's engine genuinely has **no** WAL pragma (`src/data/database.py` sets
only `timeout=5`); WAL is a **persistent file property** set by `src/search/connection.py`'s sync
factory, so any database with an embedding index is WAL forever and the companion inherits it
without asking; but a database created by `init_database` measures **`delete`** — so the
fresh-install case is the non-WAL row. It still does not bite: the worst measured effect is 0.21 s
on one write under saturation the product never generates, against a 5 s busy timeout, and this
poll issues one request every 2–30 s. **Re-homed on c10-3 with the numbers.**

**The live fresh-install run** (closes deferral 2, first time ever): empty `PLANESWALKER_DATA_DIR`
→ the companion **started**, printed its URL, published discovery, planted **no** `cards.db`;
`GET /health` `200`; `GET /api/decks` `503 {"reason":"database_not_initialized"}` with
`cache-control: no-store`; `GET /` served the SPA carrying the new bundle. A populated `cards.db`
copied in **with the server still running** → the very next `GET /api/decks` answered `200` with
real deck names. **No restart.** FR-22's backend half is now confirmed rather than inferred.

**Not done, and stated as not done:** nobody opened the page in a browser. The transition and the
four newly-reachable panels are gated in jsdom from one mount (probe (f) proves a remount-driven
implementation fails), but the *visual* claim is made nowhere. On the epic manual-testing checklist
with a recipe.

**Seven mutation probes, each verified and reverted from a FILE BACKUP** (never `git checkout` —
c3-7 Debug Log 3), every result read before filing:

| Probe | What was removed | Result |
| --- | --- | --- |
| (a) | the backoff **ceiling** | **5 failures** — the growth assertions stay green, the clamp and three escalation tests go red |
| (b) | the `RETRIES_QUIETLY` **consult** ("always retry") | **5 failures**, including `internal-error` being hammered and the app-level "stops polling once the database is there" |
| (c) | the elapsed-clock **reset** | **2 failures** — both reset paths |
| (d) | the runtime **validation** | **23 failures**, and the render crash AC 8 exists to prevent: `TypeError: Cannot read properties of undefined (reading 'body')`. The validation is where the story thinks it is. |
| (e) | the **escalation guard** (arm on any error) | **4 failures**, including "NEVER escalates `database_not_initialized`" by name |
| (f) | the transition driven by a **remount** (snapshot instead of subscription) | **7 failures**, including the FR-22 one-mount test |
| (g) | a posture breach in a real component, **spelled to evade** | **2 failures**, both at the IMPORT door; the identifier layer missed it, exactly as declared |

**All twelve inherited deferrals dispositioned by name** — 1 ✅ (Q3 shipped), 2 ✅ (live run,
backend half), 3 ⚠️ partly (reachable ✅, browser look-at ✗ → checklist), 4 ✅, 5 ✅ (Q5, plus two
corrections to the entry's own text), 6 ✅ (Q6; fourth tail → **c5-6**), 7 ✅ (Q4), 8 ✅ measured →
**c10-3**, 9 ✅ (structural — no path parameter, asserted), 10 ⚠️ half (panel half consumed;
classification stays **c4-3's**, with the delete signal restated), 11 ✅ recorded → **c5-5**,
12 ✅ (Q9). Eight residue entries added, every one with a named home.

**Gates, all green and all pasted in the session.** Python **2464 → 2472 passed, 1 skipped** (192.74 s); `ruff check`, `ruff format --check` (305 files), `mypy src/` and `mypy src/ --platform win32` (89 files each) all clean. Frontend **568 → 718 passed, 31 → 36 files**; `lint`, `format:check`, `npx tsc -b --force` and `build` all clean. Both drift gates green from the same commit: `test_openapi_contract.py` 17 passed, and `npm run gen:api` re-run against the staged files leaves `git status --porcelain` with no worktree change — the generator reproduces the committed bytes. `test_import_boundary.py` **50 passed, unchanged, no exclusions added**. `copy.test.ts` + `copy-rules.test.ts` + `named-card-copy.test.ts` **61 passed with a byte-empty `git diff`** — the AC 16 prediction held. `shell.test.ts` **93 passed**, its nine exhaustive import lists untouched.
Runtime is claimed on the NARROWEST suite containing the change, over three samples each: the frontend one (156 tests) at **1.55 / 1.55 / 1.52 s**, and `tests/unit/companion` (997 passed, 1 skipped) at **87.1 / 69.1 / 59.8 s**. That second spread — 27 s across three runs of identical code — is exactly why no whole-suite delta on this box is read as signal (c3-7 ledgered 49 s), and it is why the frontend number is the one worth quoting.

**Bundle re-measured and CHANGED, as AC 24 required it to be:**
`index-DE70muY2.js FAEEEA472ADD5078` → `index-kDIAckYA.js 1A23A6165C3F486F` (195.14 → 198.26 kB,
25 → 33 modules). CSS and font **byte-identical** — this story ships behaviour, not styling. The
`plugin/` mirror was rebuilt and `diff -r` reports the two trees **identical**.
*Post-review rebuild:* the applied review patches moved the bundle again, to
`index-DVyKlzKd.js ED89F6474885A685` (198.51 kB); `diff -r` again reports both trees identical.

**The first frame is `no-active-deck` by deliberate choice, recorded here (review).** Before the
first answer lands, `INITIAL_SYSTEM_STATE` renders the c2-9 static panel — momentarily untrue on
a database-less machine. No Q ruled it; the argument lives in `systemState.ts`'s header: no panel
at all hands the `left` slot back to its placeholder, a guessed database state would present a
guess as fact, and on localhost the first answer arrives in milliseconds, so the constant governs
one frame.

**Review patches applied (bmad-code-review, 2026-08-02).** Three medium findings both hunters hit
independently, all fixed with paired tests: a generation counter so a `stop()`/`start()` restart
drops stale in-flight answers and cannot fork a second timer chain (state resets on `start()`);
`AbortSignal.timeout(READ_TIMEOUT_MS = 10_000)` on the one fetch, so a backend that accepts and
never responds becomes `unreachable` instead of freezing the loop; and `STALLED_MIN_REFUSALS` so
wall time alone cannot escalate across a suspend. Plus: emissions deduplicated to changes,
`identify()`'s token-less sentinel made collision-free, the single-consumer rule written loudly on
`useSystemState`, `posture.test.ts`'s stripper rebuilt as a string-aware walker, `copy-tails`'
reader comment-stripped, and the `200`-with-non-JSON-body branch pinned. Frontend suite
718 → **730 passed** (36 files); lint, format, `tsc -b --force`, build all green.

### File List

**Added**
- `ui/src/api/decks.ts`
- `ui/src/api/decks.test.ts`
- `ui/src/state/panel.ts`
- `ui/src/state/panel.test.ts`
- `ui/src/state/poller.ts`
- `ui/src/state/poller.test.ts`
- `ui/src/state/systemState.ts`
- `ui/tests/posture.test.ts`
- `ui/tests/copy-tails.test.ts`
- `src/companion/app/static/assets/index-DVyKlzKd.js` (built; superseded the intermediate
  `index-kDIAckYA.js` after the review patches)
- `plugin/server/src/companion/app/static/assets/index-DVyKlzKd.js` (mirror)

**Modified**
- `ui/src/App.tsx`
- `ui/src/App.test.tsx`
- `ui/src/api/schema.ts`
- `ui/src/api/openapi.json` (regenerated — never hand-edited)
- `ui/src/api/types.d.ts` (regenerated)
- `ui/README.md`
- `src/companion/app/main.py`
- `src/companion/contracts.py`
- `scripts/dump_openapi.py`
- `tests/unit/companion/test_committed_schema.py`
- `tests/unit/companion/test_routes_cards.py` (a c3-2 pin renamed and its 503 assertion updated —
  omitted from this list until the review caught it)
- `src/companion/app/static/index.html` (built)
- `plugin/server/src/companion/app/main.py` (mirror)
- `plugin/server/src/companion/contracts.py` (mirror)
- `plugin/server/src/companion/app/static/index.html` (mirror)
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c3-9-fresh-install-guides-instead-of-erroring-and-comes-alive-on-its-own.md`

**Deleted**
- `src/companion/app/static/assets/index-DE70muY2.js` (superseded by the rebuild)
- `plugin/server/src/companion/app/static/assets/index-DE70muY2.js` (mirror)

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-02 | Implemented c3-9 off `16976c5`. First runtime behaviour in `ui/src`: one `fetch`, one zustand slice, one poller, one total wire→panel boundary. Q1–Q10 all ruled (nine as proposed; Q5 refined for transport failures). Q4 declared `database_not_initialized` on the database-backed includes — five operations changed and `error_responses`' collapse fired for the first time. Two new family-keyed guards. Twelve inherited deferrals closed or re-homed by name; eight residue entries added. Seven mutation probes, all caught. Live fresh-install run confirms FR-22's `503`→`200` with no restart; the browser look-at is NOT done and is on the epic checklist. Status → `review`. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

CODE REVIEW -> done 2026-08-02: three layers (Blind Hunter + Edge Case Hunter + Acceptance Auditor), 1 decision resolved (AC 11/25's browser halves — re-home to the epic manual-testing checklist ACCEPTED), 13 patches applied (headlines, each found by BOTH hunters independently: a generation counter so stop()/start() cannot apply a stale in-flight read or fork a second timer chain, with all schedule state reset on start(); AbortSignal.timeout(READ_TIMEOUT_MS=10 s) so a backend that accepts-and-never-answers becomes `unreachable` instead of freezing the loop forever; STALLED_MIN_REFUSALS=4 so wall-clock alone cannot escalate across a suspend/throttled tab — plus emission dedup to CHANGES, the identify() null-sentinel collision, the one-consumer rule written on useSystemState, posture.test.ts's stripper rebuilt as a string-aware walker, copy-tails' reader comment-stripped, the 200-with-non-JSON-body branch pinned, and three record repairs), 2 defers ledgered with homes (Q2's reset-on-flip cost -> c4-1; the stalled state's terminal forfeit of FR-22's self-transition -> C3 retro), 1 dismissed. Frontend 718 -> 730 (36 files); every gate re-run green (Python 2472/1 skipped, ruff, format, mypy both platforms, lint, format:check, tsc -b --force, build); bundle re-measured CHANGED again (1A23A616 -> ED89F647) with the plugin mirror diff -r identical. PR into feat/companion-c3 is the remaining step. Previously — IMPLEMENTED 2026-08-02 off 16976c5 — the epic's only frontend story, and the FIRST runtime behaviour in ui/src at all: one fetch (src/api/decks.ts, asserted to be the only network door in the SPA), one zustand slice (its first consumer since c2-1), one poller (2 s / x2 / 30 s ceiling) and one total wire->panel boundary that finally consumes PANEL_FOR_REASON and RETRIES_QUIETLY — the 318-line specification c2-9 wrote for this story and nothing had ever executed. All ten open questions ruled, nine as proposed; Q5 REFINED with a reason (a fetch REJECTION is not an absent token: clamping it to internal-error would have stopped the poll permanently on one blip, because RETRIES_QUIETLY says internal-error never retries — so a transport failure claims no state and retries, and the disconnected panel stays c5-6's per Q10). Q4 declared database_not_initialized on the database-backed includes: five operations changed and error_responses' documented COLLAPSE fired for the first time in seven stories. Q7 was MEASURED rather than argued and re-homed on c10-3 with numbers — the companion's engine has no WAL pragma, but WAL is a persistent FILE property set by src/search/connection.py, so an indexed database is WAL forever while a freshly created one measures `delete`; contended write latency 0.0080 s (wal) vs 0.2131 s max (delete) under four saturating readers, against a 5 s busy timeout and a poll that fires once every 2-30 s. Q9's markers proved a `#` comment above a wire model costs NO wire diff, dissolving c3-7's objection by measurement. TWO NEW FAMILY-KEYED GUARDS: posture.test.ts states presentation-only over the WHOLE component tree (a component may take a TYPE from anywhere and a VALUE from nowhere but its own tree and React) rather than as nine enumerated import lists, and pins the one network door; copy-tails.test.ts gates three of EXPERIENCE.md's four un-quoted tails against their TypeScript mirrors both ways. THE LIVE FRESH-INSTALL RUN HAPPENED (closes a c1-9 deferral nobody had ever run): empty data dir -> companion starts, plants no cards.db -> 503 database_not_initialized -> cards.db planted with the server RUNNING -> the next request answers 200 with real deck names, no restart. NOT DONE and stated as not done: nobody opened it in a browser — the transition and the four newly-reachable panels are gated in jsdom from ONE mount (probe (f) proves a remount-driven implementation fails) but the visual claim is made nowhere, and it is on the epic manual-testing checklist. Twelve inherited deferrals all dispositioned by name (10 closed, 2 partly), eight residue entries added, every one homed. Seven mutation probes, all caught — (d) produced the exact render crash AC 8 exists to prevent, and (g) confirmed the new guard's DECLARED split: the import door caught the evasive spelling, the identifier layer did not. Suites 2464 -> 2472 Python, 568 -> 718 frontend (31 -> 36 files). Bundle MEASURED CHANGED (FAEEEA47 -> 1A23A616, 25 -> 33 modules) with CSS and font byte-identical, and the plugin mirror diff -r identical.
