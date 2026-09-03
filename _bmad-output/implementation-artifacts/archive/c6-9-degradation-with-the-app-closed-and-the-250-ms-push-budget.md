---
baseline_commit: 6586209
---

<!--
  Story context created 2026-08-12 by create-story (ultimate context engine analysis).
  Sources: epics-companion-app.md (Story 6.9 :2979-3014, Epic 6 :2684-2689, NFR-05 :157-160,
  FR-06 :60-62, FR-12 :83-87, AD-8 :241-245, NFR coverage :783, Story 10.3 :3656-3694),
  EXPERIENCE.md (Latency & Freshness Contract :160-168, UJ-1 step 5 :187), DESIGN.md
  (motion.bloom :123), companion-app-feature-brief.md (SC-1/SC-3 :131-136), shipped code at
  6586209 (client.py, mcp_server/tools/companion.py, app/routes/agent_events.py, app/ws.py,
  ui: socket.ts, connection.ts, agentView.ts, App.tsx, AgentView.tsx/.css, SuggestionsView.tsx,
  cards.ts, useCardArt.ts, scripts/cdp_harness.py), test suites (test_client.py,
  test_companion_tool.py, test_routes_agent_events.py, test_import_boundary.py,
  test_live_backend.py, socket.test.ts, AgentView.test.tsx, SuggestionsView.test.tsx),
  c4-12 story record (the 1 s budget measurement precedent — Q7/Q9 clock rulings, :1798 result
  format, :732 no-Playwright/no-suite-assertion rulings), c6-1/c6-2/c6-4/c6-8 records,
  deferred-work.md, sprint-status.yaml.
-->

# Story c6-9: Degradation with the app closed, and the 250 ms push budget

Status: done

## Story

As Brad running my agent with no browser open,
I want every workflow to work exactly as it did before the companion existed,
So that the app is something I open when I want it, not something I have to run.

## The story in one paragraph

This is the epic-closing **verification** story, and most of its acceptance criteria are already
built: c6-1's leaf client owns the closed outcome vocabulary and never raises
(`client.py:123-129`), c6-2/c6-4's tools return compact text results whose degradation, echo
hygiene and per-branch compactness are pinned on **every** status branch
(`test_companion_tool.py:365-473`, `:622-653`), and the backend push path performs no database
round-trip by test-asserted construction (`test_routes_agent_events.py:736-768`). What has never
happened is **observation**: no `performance.*` call exists anywhere in `ui/`, no run of the app
has ever produced a number, and SC-1's "within 250 ms" is still a sentence someone wrote. The
repo already owns the instrument — `scripts/cdp_harness.py`, promoted to a committed asset at
the C4 retro, whose `budget` subcommand measured c4-12's 1 s deck budget with a document-start
MutationObserver stamping `performance.now()` at first DOM entry of each named surface. This
story adds a **push arm** to that harness (suggestions-view surfaces, a push-triggered clock
that starts when the harness's own token-authenticated `POST /agent/events` returns — the tool
boundary in substance, in the harness's established `:404` idiom), runs it against a real backend + real
headless Chrome with a warm image cache, and records the observed figures with hardware and
conditions, exactly as c4-12 did (`c4-12:1798`). It also closes SC-3's one genuine gap — the
import-boundary guard proves no *companion* coupling, but nothing sweeps the **other 19 tools'**
modules for it — and prose-syncs the fulfilled `c6-9` forward references. Expected diff: Python
tests grow, frontend suite **2,123/75 stays unmoved**, tokens hold at 70, and `ui/` runtime code
changes by at most one comment (AgentView.tsx:325's prose-sync ⇒ rebuild both mirrors).

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md:2985-3014`, numbered for citation.)*

1. **Given** the companion backend is not running **When** any companion tool is called **Then**
   it returns `app_not_running` as a text result, the agent presents the content in chat as
   usual, and **no agent turn errors** (FR-12, SC-3)
2. **Given** the backend is running but no browser tab is connected **When** a push tool is
   called **Then** it returns `no_clients_connected`, so Brad can be told the content was not
   displayed (FR-06, FR-12)
3. **Given** every agent workflow that existed before this feature **When** it is exercised with
   the companion app closed **Then** it completes successfully — closing **SC-3**
4. **Given** the app is open with a warm image cache **When** a suggestions push completes at
   the tool boundary **Then** the view reaches **painted layout within 250 ms** — view layout,
   text, and cached-or-placeholder art (SC-1, NFR-05) **And** the clock stops at first paint of
   the laid-out content, **not** at animation settle; the 480 ms entry animation runs on top of
   a complete layout and is never inside the budget
5. **Given** the 250 ms budget **When** the push path is inspected **Then** the view never
   blocks on image fetches, and card hydration runs concurrently with the open animation
   (NFR-05)
6. **Given** the measurement **When** acceptance is recorded **Then** it is an observed figure,
   not an assumption
7. **Given** all companion tool results **When** their token cost is measured across a session
   **Then** they add negligible overhead and never echo payloads (CM-1)

**What is genuinely new here vs. already shipped:** AC 1 and AC 2 are shipped and tested
(citations in Dev Notes) — this story *confirms end-to-end* rather than builds. AC 3 has a
structural half shipped (the leaf/app import guard) and a sweep half missing. AC 4/5/6 are the
story's real work: nothing has ever been measured. AC 7 is pinned per-result on every branch;
only the "across a session" framing is unaddressed, and it closes by arithmetic, not mechanism.

**Scope boundaries (build none of these):** Story 10.3 (Phase 2) owns the *hardening* half of
NFR-05 — profiling the image pacer under a cold-cache deck load, the **concurrent push while
images are queued** case (`ws.py:375-378` names c10-3 for exactly this), CDN request counting
(CM-2), the cache-footprint figure, and closing any measured gap "or recording an accepted
deviation". This story observes the plain warm-cache push budget once, credibly, and closes
SC-1/SC-3 for Phase 1 acceptance. No Epic 7 notifier work (AD-9 is c7-1's), no new view kinds,
no wire change of any kind: `contracts.py`, `openapi.json`, `types.d.ts` untouched. **No
Playwright** and **no budget assertion in the test suite** — both ruled at c4-12 Q9
(`c4-12:732`) and inherited here, not re-litigated.

## Tasks / Subtasks

- [x] **Task 0 — Baselines, branch, and grep dispositions** (protects everything)
  - [x] Branch `feat/companion-c6-9-push-budget` cut from `feat/companion-c6` at or after
        `6586209` (the c6-8 merge record).
  - [x] Frontend baseline: `npm test` from an **uppercase** drive path; expect **2,123 passed /
        75 files**; validate the collected count before trusting any run (Landmine 1). This
        story predicts the frontend suite **does not move** — a moved count means scope crept.
  - [x] Python baseline: `uv run pytest -m "not integration"` — expect **2,907 passed / 1
        skipped / 55 deselected**; this story's new tests grow it.
  - [x] `grep -rn "c6-9"` across `src/`, `ui/`, `tests/`, `scripts/`, `docs/`, `_bmad-output/`
        — known sites listed in Dev Notes; build the dispositions table. Story records stay
        records; `ui/src/containers/AgentView/AgentView.tsx:325` is the one live-code
        forward reference this story fulfils.
- [x] **Task 1 — The SC-3 sweep** (AC 1, AC 3)
  - [x] Extend `tests/unit/companion/test_import_boundary.py` (or a sibling module beside it —
        dev's call, argued in place) with the sweep the existing guard stops short of: walk
        **every module under `src/mcp_server/`** and assert that only the three sites that
        legitimately reference `src.companion` today do so —
        `src/mcp_server/tools/companion.py` (the two tools), `server.py` (the leaf imports:
        `contracts.SuggestionsPayload` at `:44` + the tool helpers), and `__main__.py` (the
        dispatcher's **function-local** `src.companion.app.server` import, already exempted by
        name via c1-1's `_APP_IMPORT_EXEMPT` ruling). The shipped guard proves the *app* half
        (`test_import_boundary.py:509-558` — no `src.companion.app` import anywhere in the MCP
        server); this closes the *leaf* half: a pre-existing tool that quietly grew a companion
        dependency is exactly how SC-3 silently breaks in a later epic.
  - [x] End-to-end confirmation with a genuinely absent backend: with `PLANESWALKER_DATA_DIR`
        pointed at a tmp dir containing **no discovery file**, drive both companion tools
        through the established in-process MCP client harness and assert `app_not_running`
        text results and zero raised exceptions; drive one representative pre-existing tool
        (e.g. `list_decks`) in the same session and assert it is bit-for-bit indifferent.
        (The unit suite already proves the client against dead ports and corrupt discovery
        files over real loopback sockets — `test_client.py:1022-1077` — so this is the
        *tool-boundary* confirmation, not a re-proof of the transport.)
  - [x] Record the SC-3 closure argument in the story record: structural guard + sweep + the
        fact that the entire pre-existing suite has always run backend-less + AD-15's
        `view_deck` kept rendering (deprecation is c8-1's, removal is post-Phase-2).
- [x] **Task 2 — CM-1's session framing** (AC 7)
  - [x] No new mechanism. The per-result bound is already pinned on **every** branch of both
        tools at the worst case (60-item payload, oversized ids):
        `test_companion_tool.py:365-473` (control) and `:622-653` (push — `< 400` chars,
        sentinel-absence, exact field set).
  - [x] Close the "across a session" wording by arithmetic recorded in the story record:
        worst-case result ≈ 400 chars ≈ ~100 tokens; a heavy session (every deck switch and
        push UJ-1 contemplates) stays in the low thousands of tokens with zero payload echo.
        Cite the pins; do not duplicate them.
- [x] **Task 3 — The harness push arm** (AC 4, AC 5, AC 6; Q1/Q2/Q3 rulings)
  - [x] Extend `scripts/cdp_harness.py` with a `push` subcommand beside `budget`/`panels`/
        `shot`, reusing `Browser`, `Companion`, and the `_OBSERVER` document-start
        MutationObserver verbatim. New suggestions `SURFACES` set (per Q2): the dialog root,
        the view heading, the rows list, the first row's name and reason nodes — the stop is
        the **last** of the set, matching `measure_budget()`'s existing rule.
  - [x] The clock (Q2): t0 = the moment the harness's **own token-authenticated
        `POST /agent/events` returns** (the harness's shipped `:404-408` idiom — token read
        straight from `companion.json`; the tool boundary in substance, since
        `companion_show_suggestions` is validation + exactly this POST + message mapping,
        `companion.py:279-334`); stop = the observer's first-DOM-entry stamp of the last
        surface. **The harness stays free of `src/companion` imports** — its own contract
        (`cdp_harness.py:16-17`), and the c5-8 Q3 principle: a client bug and a backend bug
        must not be able to fail the same assertion, so the instrument must not measure
        through the leaf it isn't measuring. Both ends must land on the page's clock — the
        stop side is `performance.timeOrigin`-based already; stamp t0 by evaluating
        `performance.now()` in the page immediately after the POST returns (the evaluation
        round-trip lands AFTER t0, so any error is conservative), or an equivalent the dev
        argues in place.
        Document in the subcommand's docstring why DOM-entry-at-commit is the honest "first
        paint of laid-out content": the entering frame renders the complete layout at
        `opacity: 0` and the 480 ms bloom (`tokens.css:185`, `AgentView.css:74-97`) is
        presentation on top (`AgentView.tsx:165-174`), so animation settle is structurally
        outside the stop by construction, not by subtraction.
  - [x] Arms (Q3): **warm-art arm is the AC** — prime with one discarded push of the same
        card ids (fills the browser image cache via `/api/card-image/*`'s
        `immutable` caching and the disk cache behind it), then measure n ≥ 5 pushes;
        **cold-art arm recorded as observation only** (placeholder paint is inside the budget,
        first-fetch image paint is excluded — NFR-05's own words); **image-block arm proves
        AC 5** — CDP-block `/api/card-image/*`, push, and the layout must still paint inside
        the budget with placeholder art (the "never blocks on image fetches" claim, observed
        rather than asserted).
  - [x] Payload: a realistic six-item suggestions push with real Scryfall ids from the seeded
        data dir (UJ-1's own shape, `EXPERIENCE.md:187`); also one 60-item worst-case run,
        recorded as observation.
  - [x] Harness discipline (all three recorded traps, `cdp_harness.py:28-38`): a run that
        stamps zero surfaces must **fail loudly** (`missing` non-empty ⇒ non-zero exit), never
        print a vacuous pass; uppercase drive path; no `shell=True`.
- [x] **Task 4 — Run the measurement and record the figures** (AC 4, AC 6)
  - [x] Real backend on an isolated `--data-dir` seeded with an initialized `cards.db` (the
        harness's existing `Companion` bootstrap), real headless Chrome, real WS ticket +
        upgrade, real discovery-file token — no stubs anywhere on the measured path.
  - [x] Record per-arm figures (min/median/max, n per arm) **with hardware and conditions**,
        in this story record's Dev Agent Record — the `c4-12:1798` format verbatim
        ("NFR-05 met: … against a 1,000 ms budget" is the sentence shape to mirror).
  - [x] Breach protocol (Q4): any warm-arm run over 250 ms ⇒ **stop and diagnose** before
        writing anything; a fix needs its own ruling if it touches shipped behaviour; "accepted
        deviation with its reason" is Brad's call alone, never the dev's default. Do not tune
        the harness until the number fits.
- [x] **Task 5 — Ripple, prose-sync, and mirrors** (Task 0's dispositions discharged)
  - [x] `AgentView.tsx:325` ("c6-9 measures the budget this is excluded from") — prose-sync to
        past tense with the observed figure's home named. This is a comment in a runtime file:
        **rebuild `npm run build` → `src/companion/app/static/` then
        `uv run python -m scripts.build_plugin`, sha256-verify both mirrors** (the bundle is
        expected byte-identical since comments are stripped — verify, don't assume; c6-8
        rebuilt for exactly this class of edit).
  - [x] `ws.py:375-378`'s "the 250 ms concurrent-push measurement is c10-3's" **stays as
        written** — it names the concurrent-under-load case, which remains 10.3's; disposition
        recorded, not edited.
  - [x] Story records (c6-4/c6-5/c6-6/c6-7/c6-8) and `sprint-status.yaml` mentions: records
        stay records.
  - [x] Docs sweep: grep the **claim**, not the sentence — any "unmeasured"/"not yet measured"
        prose about the push budget in `ui/README.md` / `docs/` gets synced to the observed
        state; tool counts don't move (no new tool).
- [x] **Task 6 — Planted red, gates, ledger, records**
  - [x] Plant 1 (guard): make a non-companion tool module import `src.companion.client` —
        predict the new SC-3 sweep red, the shipped leaf/app guard green (it checks the app
        half only). Proves the sweep sees what the existing guard cannot.
  - [x] Plant 2 (harness non-vacuity): run the `push` subcommand with a selector that never
        enters the DOM — predict a loud failure with `missing` named, exit non-zero. This is
        the C4 zero-assertion trap, proven against this subcommand rather than remembered.
  - [x] Plant 3 (clock integrity): sever the WS delivery (kill the socket before the push) —
        predict the harness reports no stamp rather than a small number (the frame never
        arrived; a number here would mean the clock is measuring the wrong thing).
  - [x] Predictions recorded before each run; full suites after; collected counts validated;
        stage everything before each plant; revert, `git diff --exit-code` clean.
  - [x] `uv run ruff check . --fix` / `format`; `uv run pytest -m "not integration"` strictly
        above 2,907; `npm test` **exactly 2,123/75** (a moved frontend count = unplanned scope);
        tokens 70 untouched by inspection (no `ui/src` stylesheet or token diff at all).
  - [x] Ledger reconciliation in `deferred-work.md`: no inherited entry is homed to c6-9
        (verified at story creation) — annotate the in-flight-coalescing entry only if the
        image-block arm's observations bear on it; add entries only for measured residue.
  - [x] Dev Notes KB self-check (10–20 KB band); record suite arithmetic before/after; update
        this record + `sprint-status.yaml`.

*(Per the standing workflow: implement Tasks 0–6, set status `review`, STOP — Brad runs the
three-layer review and raises the PR into `feat/companion-c6`. This is the epic's last story:
after merge, next is the C6 retrospective.)*

### Review Findings

*(bmad-code-review, 2026-08-12 — Blind Hunter, Edge Case Hunter, Acceptance Auditor, run in
parallel against the diff at baseline `6586209`. Acceptance Auditor independently re-read the
full spec against the diff — allow-list/site count, +14 test delta, the byte-length of the
sha256 citation, AD-10's "directory is not a marker" claim — and confirmed each checks out;
its one substantive note (the `PUSH_SURFACES` set never includes an art element, so AC 4's
"cached-or-placeholder art" clause is asserted by the `useCardArt.ts` mechanism rather than
measured at the `stop` instant) matches Q2's ruled surface set verbatim and is dismissed below
as already handled by that ruling, not a diff-introduced gap.)*

- [x] [Review][Patch] A failed push (non-2xx from `POST /agent/events` — a stale/wrong token
  → 403, or `--items` above the contract's 60-item cap → 400 `payload_rejected`) was reported
  identically to a genuine rendering failure. `measure_push` (`scripts/cdp_harness.py:574-660`)
  captured `response.status_code` only to gate `clients` (`clients = response.json().get(
  "clients") if response.status_code == 200 else None`) — the status code and response body
  were never carried into the result dict or printed. `_print_run` (`:777-795`) then reported
  every such run as `INVALID -- surfaces never arrived: [...] (the view never rendered them)`,
  which read as a rendering defect and hid that the POST itself failed. This contradicted the
  function's own stated discipline ("a bad run says why, and never prints a number it does not
  have") and diverged from this same file's own established idiom: `cmd_budget`'s
  `PUT /api/active-deck` call (`:408-417`) explicitly checks `response.status_code != 200` and
  raises `SystemExit` naming the code and body. **Fixed**: `measure_push` now captures
  `response_text` (truncated) alongside `status_code`, and `_print_run` checks
  `status_code != 200` first, printing the code and body before falling through to the
  surfaces/clients checks. `ruff check` clean; no test exercises this script's internals
  (Q9's standing ruling), so verified by inspection and `py_compile`.
  [`scripts/cdp_harness.py:574-663`, `:777-800`]

- [x] [Review][Defer] The pre-existing `outside_app` role in `find_import_violations`
  (`tests/unit/companion/test_import_boundary.py:491`, `elif imported.module_level:`) only
  flags **module-level** `src.companion.app` imports — a function-local
  `import src.companion.app` anywhere outside `src/mcp_server` and the app package would pass
  silently. The new SC-3 sweep this story adds makes exactly this "a deferred import is still a
  dependency" argument for its own function-local coverage, but the untouched app-side guard
  keeps the identical blind spot. Not introduced by this diff — pre-existing, unmodified code
  path. [`tests/unit/companion/test_import_boundary.py:491`] — deferred, pre-existing

- [x] [Review][Defer] `_COMPANION_REFERENCE_ALLOWED`
  (`tests/unit/companion/test_import_boundary.py:162-172`) exempts whole files by name rather
  than specific import sites — nothing constrains which `src.companion` symbols
  `server.py`/`companion.py` may import later, so a future unrelated companion import landing
  in an already-exempted file would sail through undetected. Matches the granularity of the
  pre-existing `_APP_IMPORT_EXEMPT` idiom it sits beside; tightening to import-site-level
  tracking would be a larger redesign than this story's scope.
  [`tests/unit/companion/test_import_boundary.py:162-172`] — deferred, pre-existing (same
  idiom as `_APP_IMPORT_EXEMPT`)

- [x] [Review][Defer] `_seeded_card_ids` (`scripts/cdp_harness.py:498-515`) always reads
  `decks[0]` from `GET /api/decks`, whose ordering the route's own docstring states is only
  "newest first… not a strict guarantee" under ties. A repeated `push` invocation against the
  same data dir could silently draw ids from a different deck than a prior run, with nothing in
  the harness's output recording which deck was actually used.
  [`scripts/cdp_harness.py:498-515`] — deferred, pre-existing (harness usability, not a
  measured-figure defect)

- [x] [Review][Defer] `--card-ids` (`scripts/cdp_harness.py:946`) bypasses
  `_seeded_card_ids`'s real-Scryfall-id guarantee entirely — passing fabricated or
  non-existent ids together with `--arm warm` silently defeats the warm arm's whole premise
  (priming real art into the browser cache), with no validation or warning. Not exercised by
  this story's own recorded measurement (real deck ids were used throughout), so the recorded
  figures are unaffected — a future-run footgun only. [`scripts/cdp_harness.py:946`] —
  deferred, pre-existing (future-run usability only; this story's own recorded figures are
  unaffected)

- [x] [Review][Defer] The image-warmth counters (`images_requested`/`images_from_network`/
  `images_painted`, `scripts/cdp_harness.py:660-672`) are read as a single point sample after a
  fixed `--image-settle` sleep (default 2.5 s), unlike `layout_ms`, which polls via
  `_await_surfaces` until the surfaces actually arrive or a deadline passes. A slow machine or
  network could still have images in flight when the sample is taken, silently under-counting
  the warmth metrics. Does not affect the reported budget verdict (`layout_ms`, the
  min/median/max figures) — only the supplementary network/painted counts.
  [`scripts/cdp_harness.py:660-672`] — deferred, pre-existing (informational metrics only;
  does not affect the recorded budget verdict)

*(12 findings dismissed as noise, already-mitigated by the harness's own non-vacuity discipline,
matching an established idiom already shipped elsewhere in the same file, or matching an
explicit ruling already made in this story's own spec (Q2's surface set; Q5's rejection of a
21-tool mega-test in favor of the `src/mcp_server/`-scoped sweep; landmine 6's "don't average
across payload sizes" covering the 60-item cycling design) — not reproduced here. Full detail
available on request.)*

## Dev Notes

### What is already shipped and tested (verified at story creation — cite, don't rebuild)

**AC 1 — `app_not_running`, never raises.**
- The closed five-token vocabulary: `src/companion/client.py:123-129` (`PushOutcomeToken`),
  `:169` (`PUSH_OUTCOMES` derived via `get_args`, so the sets cannot drift), `:173-195`
  (`PushOutcome`, frozen, `clients: int | None` where `None` ≠ `0` by ruling).
- No discovery file / corrupt file / dead port / silent listener / foreign identity → all
  `app_not_running`, proven against **real loopback sockets, no mocked transports**:
  `tests/unit/companion/test_client.py:1022`, `:1034`, `:1044`, `:1063`, `:1071`. A
  `MemoryError` is deliberately NOT laundered into `app_not_running` (`:723`).
- Tool level: `companion.py:255-258` is the exact `app_not_running` sentence;
  `test_companion_tool.py:656-680` (`TestTheAppBeingClosedIsReportedAndNothingMore`) asserts
  the closed app is named as such AND that no message on any branch contains a directive
  (`instead` / `skip` / `no need to` / `don't`) that would condition the agent's own written
  answer — AC 1's "presents the content in chat as usual" is guarded from the result side.
- Retry-once on 403 alone, at most two POSTs ever, identity re-proven per attempt:
  `client.py:454-492`, `:430-451`.

**AC 2 — `no_clients_connected`.** The number is the **delivered** count, not the registry
count — ruled at `agent_events.py:36-45`, asserted at `test_routes_agent_events.py:221-286`
(`:248` proves the route never reads `connected_count`). `200 + clients == 0` maps to the token
at `client.py:420-422`; tool passthrough pinned at `test_companion_tool.py:575`.

**AC 5's structural truth (this story observes it, c6-5/c6-7 built it).**
- The push path has **no database and no `create_task`**: `agent_events.py:30-34` (not a
  `DbSession`, not a repository import, card ids never checked against the corpus — tested at
  `test_routes_agent_events.py:736-768`); `ws.py:371-378` (one serialization before the loop
  `:406`, snapshot iteration `:410`, per-client try with DEBUG-logged discards `:411-418`).
- The view renders complete layout first, bloom on top: `AgentView.tsx:165-174` (the
  `entering` rAF flip; "the DOM is complete and interactive at the first render"),
  `AgentView.css:74-97` + `tokens.css:185` (the 480 ms `--motion-bloom`), and
  `AgentView.test.tsx:234-269` (enters/leaves the entering state; `:735` a replace does NOT
  re-run the bloom).
- Hydration is effect-driven, deduped, and deliberately sequenced AFTER the commit that sets
  every `<img src>`: `SuggestionsView.tsx:406-425` ("the pictures are already queued when the
  metadata requests start"), `cards.ts:274` (in-flight dedupe), `cards.ts:58-63` (the cache
  does not fetch images — art is `<img src="/api/card-image/…">`, `Cache-Control: immutable`).
- The warm-cache mechanism the measurement leans on: `useCardArt.ts:130-166` —
  `settleIfCached` reads `node.complete`/`naturalWidth` so a cached image settles without a
  `load` event; `:66-72` says in its own words that this claim is **unprovable in jsdom** and
  checked by eye — this story is where it finally gets a number.

**AC 7 — CM-1, per-result.** `companion.py:48-67` (`_ECHO_LIMIT = 48`, measured rationale),
`:220-222` ("Counts, never contents"); `ShowSuggestionsResult` carries
`{status, clients, items_pushed, message}` and nothing else (field set pinned at
`test_companion_tool.py:648`); `< 400` chars on every branch at the 60-item cap (`:626`),
sentinel strings planted in the payload asserted absent from the dumped result (`:637-646`);
the HTTP receipt echoes nothing (`test_routes_agent_events.py:161`); the client logs neither
payload nor credential (`client.py:350-352`, `:476-477`).

**SC-3's structural half.** `test_import_boundary.py:509-558`: the MCP server never imports
`src.companion.app` (so a stdio session never loads FastAPI/uvicorn), and leaf modules import
only their allowed surface. Both companion tools are unconditional registrations
(`server.py:418-490`) whose degradation is total — there is no flag whose absence could error.
`view_deck` still renders HTML (AD-15; deprecation prose is c8-1's).

### The instrument (Q1's subject — read before extending)

`scripts/cdp_harness.py` — the house measurement asset, committed at the C4 retro:
- `Browser` (`:104`): headless Chrome, **fresh profile**, raw CDP over
  `websockets.sync.client` (already a dev dep; **no new dependency** — anything
  `npm install`- or `uv add`-shaped is a wrong turn).
- `Companion` (`:242`): boots the real backend as a direct child on an isolated `--data-dir`.
- `_OBSERVER` (`:327-354`): document-start MutationObserver stamping `performance.now()` at
  first DOM entry per named selector, `window.__t0 = performance.timeOrigin`.
- `measure_budget()` (`:357-385`): the stop is the **last** of the surface set; returns
  `layout_ms`, `missing`, `observer_error`, resource-timing counts. `SURFACES` (`:72-79`) is
  currently the deck set — the push arm needs its own set, not a widening of the deck one.
- Recorded traps (`:28-38`): a zero-assertion run once read as a pass; lowercase drive
  letters; `shell=True` on Windows. Plant 2 exists because of the first.
- `Browser.block()`/`unblock()` (`:210-215`) already exist — the AC-5 image-block arm is a
  reuse, not new machinery.

The push arm's one genuinely new mechanic vs. `budget`: the clock does not start at
navigation. The harness must (1) navigate, wait for the socket to be live (the connection
pill's state or a WS-open probe), (2) prime caches per arm, (3) POST the suggestions envelope
to `/agent/events` with the token read from `companion.json` — the shipped `:404-408` idiom;
**never import `src/companion`** (the module contract at `:16-17`, and the c5-8 Q3
independence principle), (4) land t0 on the page clock (see Task 3). The harness is a script:
exempt from the `^src/` mypy hook but not from ruff; `print()` is fine here (scripts/), and
polling deadlines are fine here — the "a test that sleeps is a defect" rule
(`app/state.py:239`) binds tests, not the harness.

### The c4-12 precedent — this story's shape, one budget earlier

c4-12 measured the 1 s cold-open budget and is the template for every judgement call here:
- **Q7 ruling**: what the clock measures is defined before the harness is written — here,
  Q2 does that job (t0 at the tool boundary, stop at last-surface DOM entry, bloom excluded
  by construction).
- **Q9 ruling**: **no Playwright, no budget assertion in the test suite** — the measurement is
  a script run recorded in the story record, not CI. Inherited verbatim.
- **Result format** (`c4-12:1798`): *"NFR-05 met: 311/363/428 ms fresh profile, 238/348/387 ms
  repeat visit, 278/313/390 ms cold image cache — against a 1,000 ms budget"* — min/median/max
  per arm, n stated, hardware and conditions alongside. AC 6 is satisfied by exactly this
  sentence shape with this story's arms.
- c4-12 also proved the harness can lie (its zero-assertion trap) — hence Plant 2 is
  mandatory, not optional.

### Ruled — settled, do not re-derive

1. **A push auto-opens its view** (confirmed ruling 1, 2026-07-25) — SC-1 is 250 ms
   push-to-**render**, not time-to-notification. The budget's full definition lives at
   `EXPERIENCE.md:160-168` and `NFR-05` (`epics:157-160`): "render" = view layout + text +
   cached-or-placeholder art; first-fetch image paint excluded; clock stops at first paint of
   laid-out content, not animation settle; under reduced motion the two coincide.
2. **The 480 ms bloom is never inside the budget** — built that way at c6-5 (Ruled #3 there;
   `AgentView.tsx:325` names this story as the one that measures what it excluded).
3. **Ownership split with 10.3**: this story = the plain warm-cache push-to-render figure,
   closing SC-1/SC-3 for Phase 1. 10.3 = Phase-2 hardening: pacer-under-load, concurrent push
   while a cold deck's images are queued, CM-2 request counting, cache footprint, and the
   close-or-accept-deviation pass. `ws.py:375-378` names c10-3 for the concurrent case and is
   **correct as written**.
4. **`displayed` means WS delivery, not paint** — the count is socket-write delivery
   (`ws.py:352-421`). The budget is measured by the harness's observer, never inferred from
   the tool result.
5. **R2 standing rule**: no forward-looking cross-module prose; fulfilled `c6-9` references
   get prose-synced to truth in this diff.
6. **The static/plugin rebuild rule** and **merge ≠ release** (story PR → `feat/companion-c6`,
   Greptile per story; dev stops at `review`; no tag/CHANGELOG until c8-4).
7. **Outcome tokens carry no counts and no free phrases** (c6-1, AD-8); the MCP layer spells
   the field `status`, the leaf spells it `outcome` (dw:3098 collision ruling) — the sweep
   test must not "unify" them.

### Landmines specific to this story

1. **Windows false-red + the two flakes**: `npm test` from a lowercase drive letter resolves
   no vitest config (~67 failed suites); the cold-start `lint-gates.test.ts` timeout re-runs
   warm; the worker-fork crash silently drops a whole file — validate the **collected count**
   before scoring any run. The same lowercase-drive trap is recorded inside `cdp_harness.py`
   itself (`:28-38`).
2. **The frontend suite is predicted NOT to move.** This story adds no `ui/src` behaviour. If
   any frontend guard goes red or the count moves, stop and understand — the likeliest cause
   is an accidental edit beyond AgentView's one comment line.
3. **A comment edit in a runtime `.tsx` still triggers the mirror rule.** Rebuild both mirrors
   and sha256-verify; expect byte-identical bundles (comments are stripped) but verify — c6-8
   rebuilt twice for prose-only reformatting.
4. **The harness measures the app it's pointed at.** The backend serves the **committed**
   `static/` bundle, not `ui/src` — a stale bundle measures the wrong code. Verify the
   bundle's hash matches the current build before recording any figure.
5. **Warm ≠ warm enough.** The browser image cache and the backend disk cache are two
   different warmths. The AC's "warm image cache" is the app-side experience: prime by
   pushing the same ids once and letting the images settle (watch resource-timing counts go
   to zero on the measured run — `measure_budget()` already surfaces them), not by merely
   pre-filling the backend's disk cache.
6. **The 60-item cap run can drift the figure** — record it as its own observation; the AC's
   scenario is UJ-1's realistic six-card push. Don't average across payload sizes.
7. **The push needs the live discovery token** — the backend writes `companion.json` into the
   `--data-dir` on boot; the harness reads the token from that exact file (the `:404` idiom).
   A token read from a stale or different data dir gets a 403 and measures nothing — the
   c1-7 rendezvous lesson, in script form. The envelope must be a valid `suggestions` union
   member (`{kind, id, ts, payload}`, AD-6) or the 400 turns the run into a
   `payload_rejected` measurement of nothing.
8. **The SC-3 sweep must be AST-shaped, not grep-shaped** — the existing boundary suite walks
   ASTs precisely because string matching misses aliased/function-local imports
   (`test_import_boundary.py`'s own conventions: role tables, named exemption constants,
   firing proofs). Extend in its idiom: an exemption is a named constant with a comment, and
   the plant proves the guard fires.
9. **Don't touch**: `src/companion/**` production code, `src/mcp_server/**` production code,
   `ui/src/**` beyond AgentView's one comment, `contracts.py`, generated
   `types.d.ts`/`openapi.json` (no `gen:api`), `static/` and `plugin/` by hand,
   `test_live_backend.py` (the nine-phase real-socket test is c5-8's and complete — the
   harness is the measurement home, not that test).
10. **The measured path must be stub-free end to end** — real process, real discovery file,
    real token, real WS ticket + upgrade, real Chrome. A stub anywhere on it converts AC 6's
    "observed figure" back into an assumption with extra steps.

### Testing requirements

- **Suite arithmetic**: Python strictly > 2,907 (the SC-3 sweep + the tool-boundary
  degradation confirmation); frontend **exactly 2,123/75**; tokens 70 untouched.
- **House style**: every behavioural assert pairs with a non-vacuity guard and a *why*
  message naming the AC; absence-only asserts get their positive twin (standing practice
  since c6-7's plant-3 lesson).
- **The harness is not a test** — it ships no `assert` into either suite (c4-12 Q9). Its
  discipline is exit codes + the three plants.
- **Plants** (Task 6): three, with predicted blast radius recorded before running, collected
  counts validated, staged before planting, reverted clean.

### Previous-story intelligence

- **c6-8** (PR #70): the epic's first double-clean review (three-layer zero findings +
  Greptile 5/5 zero). Its three measured contradictions are this story's method warning:
  a story-spec claim about a byte, a mechanism, or a blast radius is a **prediction**, and
  the dev records what measurement actually said (the ASCII apostrophe; the corridor-helper
  defect; plant 2's blast radius). Same protocol here — especially for the observed figures.
- **c6-4**: the push tool's echo hygiene is guarded by tests on **all five** branches because
  c6-2's Greptile lesson was "grep the whole pattern, not the cited branch". The ripple sweep
  greps the claim, not the sentence (its 7-live-sites-vs-3-predicted result).
- **c6-1**: the client's test harness runs against real loopback listeners with scripted
  responses — the degradation confirmations in Task 1 reuse that posture at the tool seam,
  not mocks.
- **c4-12**: everything in "The c4-12 precedent" above; also its Q7 lesson that defining the
  clock is a *ruling*, not an implementation detail.
- **c5-8**: boot-as-direct-child (terminate/wait suffices; `uv run` makes a grandchild
  needing `taskkill /F /T` — the harness's `Companion` already knows this), readiness = the
  discovery file, never stdout.

### The known `c6-9` ripple sites (Task 0's starting list)

- `ui/src/containers/AgentView/AgentView.tsx:325` — the one live-code forward reference;
  prose-sync + mirror rebuild (Task 5).
- `_bmad-output/implementation-artifacts/` story records c6-4 (:291), c6-5 (:36, :70, :262,
  :268, :638), c6-6 (:38, :69, :341), c6-7 (:45, :83, :678), c6-8 (:84, :929) — records stay
  records.
- `sprint-status.yaml` — this story's key + the epic-c6 header comment.
- Expect more than listed — every story since c6-4 has written toward this one.

### Project structure notes

- **Expected diff**: `scripts/cdp_harness.py` (the push arm) · `tests/unit/companion/
  test_import_boundary.py` or a named sibling (the SC-3 sweep) · `tests/integration/
  mcp_server/test_companion_tool.py` or a named sibling (the tool-boundary degradation
  confirmation) · `ui/src/containers/AgentView/AgentView.tsx` (one comment) · rebuilt
  `src/companion/app/static/**` + `plugin/**` (expected byte-identical — verified, not
  assumed) · records (this file, `deferred-work.md` if anything is measured into it,
  `sprint-status.yaml`, `ui/README.md`/`docs/` only where a stale "unmeasured" claim lives).
- **Never**: new dependency (Python or npm); `ui/src` behaviour; wire/contract changes;
  Playwright or any e2e framework; a budget assertion in CI; hand edits under `static/` or
  `plugin/`.
- The harness stays one file — `cdp_harness.py` is the committed instrument and grows a
  subcommand, not a package.

### References

- Story + epic: `epics-companion-app.md` — Story 6.9 (:2979-3014), Epic 6 preamble
  (:2684-2689), NFR-05 (:157-160), FR-06 (:60-62), FR-12 (:83-87), AD-8 (:241-245), NFR
  coverage row (:783), Story 10.3 (:3656-3694, the ownership boundary), testing posture
  (:304-310 — Playwright deferred, SC-5 human).
- UX: `EXPERIENCE.md` — Latency & Freshness Contract (:160-168, the budget's defining
  paragraph), UJ-1 step 5 (:187). `DESIGN.md` — `motion.bloom: 480ms` (:123).
- Success criteria: `docs/companion-app-feature-brief.md:131-136` (SC-1, SC-3 verbatim).
- Shipped code: `src/companion/client.py` (:64-195, :350-352, :385-492, :495-544),
  `src/mcp_server/tools/companion.py` (:48-67, :98-125, :238-267, :279-334),
  `src/mcp_server/server.py` (:418-490), `src/companion/app/routes/agent_events.py`
  (:30-45, :64-104), `src/companion/app/ws.py` (:352-421, :371-378),
  `ui/src/state/socket.ts` (:425-459), `ui/src/state/connection.ts` (:93-129),
  `ui/src/state/agentView.ts` (:395-425), `ui/src/App.tsx` (:627-661),
  `ui/src/containers/AgentView/AgentView.tsx` (:165-174, :325) + `.css` (:74-97),
  `ui/src/containers/SuggestionsView/SuggestionsView.tsx` (:406-425),
  `ui/src/state/cards.ts` (:58-63, :274, :514), `ui/src/containers/useCardArt.ts`
  (:66-72, :130-166), `ui/src/styles/tokens.css` (:185).
- The instrument: `scripts/cdp_harness.py` (:19-38, :72-79, :104, :182-218, :242, :327-385).
- Guards + tests: `tests/unit/companion/test_client.py` (:723, :824-825, :914, :1022-1077,
  :1151, :1378, :1476), `tests/integration/mcp_server/test_companion_tool.py` (:231,
  :365-473, :540-562, :575, :622-653, :656-680), `tests/unit/companion/
  test_routes_agent_events.py` (:161, :221-286, :736-768), `tests/unit/companion/
  test_import_boundary.py` (:509-558), `tests/integration/companion/test_live_backend.py`
  (:274).
- Records: `c4-12-empty-deck-state-and-the-cold-open-render-budget.md` (:705, :722, :732,
  :1798), `c6-1-…md` (rulings table, completion notes), `c6-4-…md` (:525-563),
  `c6-8-…md` (whole record — the measured-contradictions protocol), `deferred-work.md`
  (checked: nothing homed to c6-9), `epic-c5-retro-2026-08-09.md` (P15, R2).

## Open questions for Brad (recommendations first — rule before code)

1. **The instrument.** Nothing has ever observed the push budget and jsdom structurally
   cannot (no layout, no paint, no images). **Recommend: extend `scripts/cdp_harness.py` —
   the committed C4-retro instrument that already measured the sibling 1 s budget — with a
   `push` subcommand (real backend, real Chrome, document-start MutationObserver), inheriting
   c4-12 Q9's two rulings verbatim: no Playwright, no budget assertion in the test suite.**
   The figure lives in this story record with hardware and conditions, c4-12's format.
   Alternatives: a manual DevTools protocol (unrepeatable, and 10.3 would rebuild the
   instrument anyway); wiring the harness into CI (a latency assertion on shared runners is a
   flake generator — measurement stays a local, recorded act).
2. **The clock.** SC-1 says "within 250 ms of the tool call completing"; NFR-05 says the
   clock stops at first paint of laid-out content, animation excluded. **Recommend: t0 = the
   harness's own token-authenticated `POST /agent/events` returning (its shipped `:404-408`
   idiom — the tool boundary in substance, since the tool is validation + exactly this POST +
   message mapping; and the harness's `:16-17` contract of importing nothing from
   `src/companion` stays intact, per c5-8 Q3's independence principle), stop = the observer's
   first-DOM-entry stamp of the LAST of the suggestions surface set (dialog root, heading,
   rows list, first row's name and reason), t0 landed on the page clock by an immediate
   post-POST `performance.now()` evaluation whose round-trip error is conservative.**
   DOM-entry-at-commit is the honest "first paint of
   laid-out content" stop: the entering frame commits the complete layout at `opacity: 0` and
   the 480 ms bloom is presentation on top, so animation settle is outside the stop by
   construction. One honest wrinkle recorded rather than hidden: the WS frame is broadcast
   *during* the POST the tool awaits, so the frame can be in the tab before t0 — that is
   faithful to SC-1's own wording (the budget is generous by exactly the overlap), and the
   figure is recorded with this definition beside it. Alternatives: t0 at the backend's
   broadcast (flatters the app, unfaithful to "tool call completing" — rejected); timing the
   real leaf `push_event()` inside the harness (rejected — it breaks the harness's own
   imports-nothing-from-`src/companion` contract at `:16-17` and couples the instrument to
   the client it isn't measuring; the leaf's probe overhead sits *before* the POST either
   way, so the boundary measured is the same).
3. **The arms.** **Recommend three: (a) warm-art (the AC) — prime with one discarded push of
   the same six ids, then n ≥ 5 measured pushes; (b) image-block (proves AC 5) — CDP-block
   `/api/card-image/*` and the layout must still paint inside the budget with placeholders;
   (c) cold-art, observation only (NFR-05 excludes first-fetch paint from the budget), n ≥ 3.
   Plus one 60-item worst-case run recorded as its own observation, never averaged with the
   six-item arm.** Alternative: warm-only — cheaper, but AC 5 would stay "true by
   construction" instead of observed, and this story exists because construction-truths were
   never enough for NFR-05.
4. **Breach protocol.** If a warm-arm run exceeds 250 ms: **recommend stop-and-diagnose with
   no code change before a ruling — a fix that touches shipped behaviour is its own decision,
   and "accepted deviation with its reason" (10.3's language) is yours alone, never the
   dev's default.** Expectation set honestly: c4-12 painted a full 100-card deck in ~310-430
   ms; a six-row view over an already-open socket should sit far inside 250 ms — but that
   sentence is exactly the kind this story exists to stop shipping unobserved.
5. **The SC-3 sweep's shape.** **Recommend: an AST sweep in the import-boundary suite's own
   idiom asserting only the three legitimate sites (`tools/companion.py`, `server.py`'s leaf
   imports, `__main__.py`'s exempted function-local dispatcher import) reference
   `src.companion` anywhere under `src/mcp_server/`, plus one in-process MCP session with no
   discovery file driving
   both companion tools (→ `app_not_running`, no exception) and one representative
   pre-existing tool (→ indifferent), with the full closure argument recorded (structural
   guard + sweep + the suite's backend-less history + AD-15's `view_deck` kept rendering).**
   Alternative: drive all 21 tools backend-less in one mega-test — rejected: the existing
   suite already exercises every tool with no backend on every run, so the mega-test would
   re-prove the suite's own operating conditions at real maintenance cost.

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, dev-story workflow). All **5 open questions ruled AS RECOMMENDED by
Brad pre-code, no overrides** — recorded before any file was touched.

### Debug Log References

- Baselines at `6586209`, both matching the story's predictions exactly: frontend **2,123 passed /
  75 files** (one cold-start `lint-gates.test.ts` timeout, Landmine 1's known flake — re-ran warm
  27/27, so the collected count was validated before the run was scored); Python **2,907 passed /
  1 skipped / 55 deselected**.
- Measurement runs: `uv run python -m scripts.cdp_harness push --data-dir <copy> --arm {warm,
  blocked,cold}`, raw per-run JSON written to the scratchpad (`warm.json`, `blocked.json`,
  `cold.json`, `warm60.json`).
- Plants 1–3, each with its prediction recorded before the run (below), each reverted with
  `git diff --exit-code` clean.

### Completion Notes List

#### The measurement — AC 4, AC 6 (the first observed figure this budget has ever had)

**NFR-05 / SC-1 met: 15/21/36 ms warm-art (n=5), 15/18/44 ms image-blocked (n=5), 17/18/42 ms
cold-art (n=3), 26/28/50 ms at the 60-item cap (n=5) — against a 250 ms budget.**

Min/median/max, conservative bracket (see the clock note below). Conditions: AMD Ryzen 9 7950X
(16C/32T), 64 GB, Windows 11 Pro 10.0.26200; Chrome 151.0.7922.108 `--headless=new`, fresh profile,
1440×1000; real companion backend as a child process on an **isolated copy** of the data dir
(250 MB `cards.db` + the 63 MB `image_cache`, so no measured request ever left the machine); real
discovery-file token, real WS ticket + upgrade, real `POST /agent/events`. **No stubs anywhere on
the measured path.** Payload: UJ-1's shape — six suggestions with real Scryfall printing ids read
from a saved deck over the backend's own REST surface.

Per-arm, with what each one is for:

| Arm | n | min / median / max | Images | What it establishes |
|---|---|---|---|---|
| **warm-art** | 5 | **15 / 21 / 36 ms** | 0 of 6 off the network, 6 painted | **The AC.** Warm cache confirmed by measurement, not by assertion: the discarded primer fetched 6, every measured run fetched 0. |
| **image-blocked** | 5 | **15 / 18 / 44 ms** | 0 painted, `/api/card-image/*` failed at the transport | **AC 5, observed.** 6 rows laid out with every picture blocked — the view provably never blocks on image fetches. |
| **cold-art** | 3 | 17 / 18 / 42 ms | 6 of 6 off the network | Observation only (NFR-05 excludes first-fetch paint). Browser cache cold, backend disk cache warm — stated, because they are two different warmths. |
| **60-item cap** | 5 | 26 / 28 / 50 ms | 0 off the network, 60 painted | Its own observation, never averaged with the six-item arm. 60 rows over 18 distinct ids (the deck's distinct count; ids cycled). |

No arm came near the budget, so **Q4's breach protocol was never triggered** and nothing was tuned.

#### Measured contradiction 1 — the clock's error ran the wrong way (Q2, load-bearing)

Q2 as written specified t0 = *an in-page `performance.now()` evaluated immediately after the POST
returns*, "so any error is conservative". **Measured, that is backwards.** A stamp taken *after*
t0 is later than t0, so `stop − t_post` **shrinks** the measured window — it flatters the app. A
gate written to the story's rationale would have understated the latency and agreed with itself
forever.

Implemented instead as a **bracket**, which preserves Q2's intent (t0 at the tool boundary, error
in the safe direction) and strengthens it: `t_pre` is stamped in-page *before* the POST is issued
and `t_post` immediately after it returns, so the true t0 provably lies between them. The harness
reports and exits on `stop − t_pre` — which includes the entire POST and therefore **over**-states
the latency — and records `stop − t_post` as SC-1's literal reading. The figures above are all the
conservative end.

**And the literal reading is negative** — min/median/max of −2/−1/−1 ms (warm), −6/−5/−4 ms (60
items). This is not an error; it is the story's own predicted wrinkle, observed: `broadcast()` is
awaited *inside* the route before the response is written, so the WS frame is in the tab and the
view is laid out **before the POST returns**. SC-1's "within 250 ms of the tool call completing"
is met by a render that has already finished when the tool call completes. Recorded with the
definition beside it rather than reported as a suspiciously good number.

#### Measured contradiction 2 — the warmth metric read an empty buffer

The first draft read `performance.getEntriesByType('resource')` at the layout stamp and reported a
flawless **"0 images off the network" on a stone-cold cache**. A `PerformanceResourceTiming` entry
is published when a fetch *ends*, so at layout+ε the buffer is empty and every arm looks perfectly
warm. Fixed by taking the image observation after a settle — which costs the figure nothing,
because every timestamp in the result was stamped in-page by the observer before the settle begins
— and by adding a positive control (`images_painted`, counted from
`.suggestion-row-image[data-loaded="true"]`). Without that control, a run that fetched nothing
because it **rendered** nothing would have been indistinguishable from a perfectly warm one. This
is Landmine 5 ("warm ≠ warm enough") arriving in a shape the landmine did not predict.

#### Measured contradiction 3 — a test fixture, not the guard

The SC-3 sweep's relative-import firing proof was written as `from ..companion.contracts import …`
in a `src/mcp_server/tools/` file. `src/mcp_server/tools/` is two packages deep, so `..` resolves
to `src.mcp_server` and the guard correctly reported nothing. The resolver was right and the
fixture was wrong; corrected to `...` with the reason recorded inline at the fixture.

#### AC 1 / AC 3 — the SC-3 closure argument

Four independent legs, only one of which is new:

1. **Structural, shipped:** `test_import_boundary.py::TestLeafAppGuard` — `src/mcp_server` never
   imports `src.companion.app`, so a stdio MCP session never loads FastAPI or uvicorn.
2. **Structural, new (this story):** `TestNoPreExistingToolDependsOnTheCompanion` — an AST sweep of
   **every** module under `src/mcp_server/`, asserting that only the three sites in
   `_COMPANION_REFERENCE_ALLOWED` reference `src.companion` at all. It fires on **function-local**
   imports too, because a deferred import is still a dependency at call time. The allow-list is a
   dict carrying each site's reason, and a staleness pin fails any entry that stops needing its
   exemption — so it cannot rot into a blanket permission.
   `test_the_existing_app_guard_would_not_have_caught_it` makes the justification mechanical rather
   than prose: handed a tool importing the leaf client, the shipped guard returns nothing.
3. **Behavioural, new (this story):** `tests/integration/mcp_server/test_companion_degradation.py`
   — with `PLANESWALKER_DATA_DIR` pointed at a directory holding no discovery file (asserted
   absent, so the file cannot silently measure a live companion on Brad's own machine), both
   companion tools are driven through a real in-process MCP session: `app_not_running` in the
   **text** result as well as the structured one, `isError` false, no exception. `list_decks` is
   driven either side of a failed push in the same session and its result is asserted
   **byte-identical**, which is stronger than asserting `status == "ok"` twice.
4. **Historical:** the entire pre-existing suite has always run with no companion, and AD-15's
   `view_deck` still renders (deprecation is c8-1's, removal post-Phase-2).

#### AC 7 — CM-1 across a session, by arithmetic

No new mechanism; the per-result bound is already pinned on every branch of both tools. Measured
the worst case rather than repeating the story's estimate: the largest result any branch can
produce is **369 characters** (`control/database_not_initialized`, 48-char echo + the 225-char
shared message), with `push/app_not_running` at 220 and the ordinary `push/displayed` at 121 —
every branch inside the 400-char convention the tests pin. At ~4 chars/token that is **~92 tokens
worst case and ~30 for the ordinary success**. A heavy UJ-1 session — say twenty companion calls
across deck switches and pushes — is **~600–1,800 tokens**, with **zero payload echo** (the
sentinel-absence assertions at `test_companion_tool.py:637-646` are what make that a fact rather
than a hope). Negligible against any session budget.

#### Plants (predictions recorded before each run)

| Plant | Prediction | Measured |
|---|---|---|
| **1 — guard** | A non-companion tool importing `src.companion.client` reds the new sweep; the shipped leaf/app guard stays green | **Confirmed.** Exactly 1 failure, `test_only_the_three_named_sites_reference_the_companion`, naming file:line:symbol. 59 passed, including the shipped app guard. |
| **2 — harness non-vacuity** | A surface that never enters the DOM fails loudly with `missing` named, exit non-zero, no number | **Confirmed.** Both runs `INVALID -- surfaces never arrived: ['plant-2-never-arrives']`, then `NO VALID RUNS -- refusing to report a number`, exit 1. |
| **3 — clock integrity** | Severing WS delivery yields *no stamp*, not a small number | **Confirmed, and it took three attempts to even reach the interesting branch** — the harness refused at the socket gate, then at the reload gate, and only with both downgraded did the push go out. With nobody listening, **all five surfaces** were reported missing and no number printed. A clock measuring the wrong thing would have produced a small number here. |

#### Ripple dispositions

- `ui/src/containers/AgentView/AgentView.tsx:325` — **the one live-code forward reference**,
  prose-synced to past tense naming this record as the figures' home (R2).
- `src/companion/app/ws.py:375-378` — **stays as written.** It names the concurrent-under-load
  measurement, which remains Story 10.3's. Disposition recorded, not edited.
- `src/companion/app/images.py:883` — cites the 250 ms budget as a comparison; correct as written.
- Story records c6-4/c6-5/c6-6/c6-7/c6-8 and `sprint-status.yaml` history — records stay records.
- **Docs sweep found nothing to sync.** Grepping the *claim* (`unmeasured`, `not yet measured`,
  `250 ?ms`) across `docs/`, `ui/README.md`, `src/`, `ui/src` and `scripts/` returned only the spec
  statements themselves (`companion-app-feature-brief.md:107`, `:133`), the two code comments
  dispositioned above, and unrelated uses of the word "unmeasured". This is the **first** story
  since c6-4 where the ripple came in *at* the predicted size rather than above it.
- **Ledger:** no inherited entry is homed to c6-9 (re-verified). The in-flight-coalescing entry was
  **not** annotated — it is already CLOSED as "not wanted" by Brad's ruling (dw:72-73), and the
  image-block arm bears on whether the view *waits* for images, not on whether concurrent fetches
  for one key are deduped. No new entries: the measurement left no residue, and every Phase-2
  hardening question it touches is already homed to Story 10.3.

#### Gates and suite arithmetic

- `uv run ruff check .` / `ruff format` — clean.
- Python **2,907 → 2,921** (+14: 10 in the SC-3 sweep, 4 in the degradation module). Strictly above
  2,907 as required.
- Frontend **exactly 2,123 / 75, all green** — the story predicted the frontend suite would not
  move, and it did not. Tokens **70, untouched** (no `ui/src` stylesheet or token diff at all).
- **Mirrors rebuilt and sha256-verified.** `AgentView.tsx` is a runtime file, so a comment-only
  edit still triggers the rule. Both `src/companion/app/static/assets/index-D-5ylWSq.js` and
  `plugin/server/src/companion/app/static/assets/index-D-5ylWSq.js` hash
  `58772555DC1C6B338AEF4ADC06CAF98EB1406F7C6FFCA801FF2709578153B043`, and `git status` reports
  both trees clean against HEAD — the bundle is byte-identical because comments are stripped, as
  predicted. **Verified, not assumed** (Landmine 3), and the measurement was run *after* the
  rebuild, so the figures describe the committed bundle (Landmine 4).
- No new dependency, Python or npm. No wire change: `contracts.py`, `openapi.json`, `types.d.ts`
  untouched. No Playwright, no budget assertion in either suite (c4-12 Q9, inherited verbatim).

### File List

- `scripts/cdp_harness.py` — **modified.** The `push` subcommand: `PUSH_SURFACES`, the bracketed
  clock, three arms, the warmth metric and its positive control, and the parser entry.
- `tests/unit/companion/test_import_boundary.py` — **modified.** The SC-3 leaf sweep:
  `_COMPANION_REFERENCE_ALLOWED`, `find_companion_reference_violations`,
  `TestNoPreExistingToolDependsOnTheCompanion`, `TestSC3SweepDetectsViolations`.
- `tests/integration/mcp_server/test_companion_degradation.py` — **added.** The tool-boundary
  degradation confirmation against a genuinely absent backend.
- `ui/src/containers/AgentView/AgentView.tsx` — **modified.** One comment (the `c6-9` prose-sync).
- `src/companion/app/static/**`, `plugin/**` — rebuilt, byte-identical, no diff.
- `_bmad-output/implementation-artifacts/c6-9-…md` — this record.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions.

## Change Log

- 2026-08-12 — Story context created (create-story, ultimate context engine analysis).
  Baseline `6586209` (frontend 2,123/75, Python 2,907/1/55, tokens 70). Code archaeology
  finding that shapes the whole story: ACs 1/2/7 are already shipped and pinned by
  c6-1/c6-2/c6-4 (cited, not rebuilt); the genuine work is the SC-3 sweep (the one structural
  gap), the first-ever observed 250 ms figure via a push arm on the committed
  `scripts/cdp_harness.py` (c4-12's instrument and precedent), and the ownership boundary
  with Story 10.3 stated rather than discovered. 5 open questions with recommendations await
  Brad's pre-code ruling — Q2 (the clock definition) is the load-bearing one. Status →
  ready-for-dev.
- 2026-08-12 — Story IMPLEMENTED (dev-story) → review. All 5 questions RULED AS RECOMMENDED by Brad
  pre-code, no overrides. **The 250 ms push budget has a number for the first time: 15/21/36 ms
  warm-art over 5 runs against a 250 ms budget**, plus 15/18/44 ms with every card image blocked at
  the transport (AC 5 observed rather than argued), 17/18/42 ms cold-art (observation only) and
  26/28/50 ms at the 60-item cap (its own observation). Real backend, real headless Chrome, real
  discovery token, real WS upgrade, no stubs on the measured path; the measurement ran against the
  rebuilt committed bundle, not `ui/src`. **Q2's stated rationale was disproved by measurement**:
  stamping t0 *after* the POST returns shrinks the window rather than widening it, so the clock
  ships as a bracket (`t_pre` before the POST, `t_post` after) with the conservative end reported —
  and SC-1's literal reading comes out **negative** (−2/−1/−1 ms), because `broadcast()` is awaited
  inside the route and the view is laid out before the tool call completes. Two further
  contradictions recorded rather than smoothed: the first warmth metric read an empty
  resource-timing buffer and reported a flawless "0 off the network" on a cold cache (fixed, plus a
  positive control counting painted pictures); and the sweep's relative-import fixture used `..`
  where `src/mcp_server/tools/` needs `...` — the resolver was right, the fixture was wrong. SC-3
  closes on four legs: the shipped app guard, a NEW AST leaf sweep over every `src/mcp_server`
  module (firing on function-local imports too, with a staleness pin on its three-site allow-list
  and a test proving the shipped guard structurally cannot see what it sees), a new tool-boundary
  degradation module driving both companion tools through a real MCP session against an absent
  backend, and the suite's backend-less history. CM-1 closed by measured arithmetic: worst-case
  result **369 chars ≈ ~92 tokens**, heavy session ~600–1,800 tokens, zero payload echo. Plants 3/3
  confirmed with predictions recorded first — plant 3 needed two harness gates downgraded before
  the push could even go out, which is itself the non-vacuity result. Python **2,907 → 2,921**
  (+14); frontend **exactly 2,123/75 unmoved** as predicted; tokens 70 unmoved. Both mirrors
  rebuilt and sha256-verified byte-identical. Ripple came in AT the predicted size — the first time
  since c6-4. Ledger: no new entries, and the in-flight-coalescing entry deliberately NOT annotated
  (already closed as "not wanted"; the image-block arm bears on waiting, not on dedupe). Next: Brad
  runs the three-layer review, then the PR into `feat/companion-c6` — after which the epic's last
  step is the C6 retrospective.
