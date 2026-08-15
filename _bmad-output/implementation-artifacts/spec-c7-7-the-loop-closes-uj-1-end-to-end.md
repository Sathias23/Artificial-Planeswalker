---
title: 'c7-7: The loop closes — UJ-1 end to end'
type: 'feature'
created: '2026-08-15'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: 'a4110a8c19350400a3c3b4ba0259e18ac510a0ba'
baseline_commit: 'a4110a8c19350400a3c3b4ba0259e18ac510a0ba'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-c7-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      `scripts/vitest_probe_harness.py` dies with `UnicodeEncodeError` while printing a failing
      test id that contains a non-cp1252 character.
    evidence: |-
      Sighted during c7-7's firing proofs on `inspection.test.ts`'s `absent → absent` row: the
      harness crashes in `print(f"  RED    {nodeid}")` on a Windows console code page, so a plant
      whose RED row carries an em dash or a curly quote produces a crash rather than a proof.
      Worked around throughout this story with `PYTHONIOENCODING=utf-8`, and c7-7 renamed its own
      test ids to ASCII to avoid adding to the hazard — but the harness itself is unrepaired, the
      workaround is recorded in no README or usage line, and the repo's test corpus is full of
      em dashes. Not caused by this story; surfaced by it.
    location: >-
      scripts/vitest_probe_harness.py
    severity: low
  - summary: >-
      All three CDP-harness reporters refuse only on ZERO valid runs — one stamped run out of five
      still prints a figure and exits 0, with no minimum-valid-run floor.
    evidence: |-
      `cmd_budget`, `_report_push` and `_report_refetch` each filter to `good` and refuse only when
      it is empty; the headline prints the `N/M valid runs` ratio, which is what an operator has to
      notice. This is a softer form of the C4 trap the module's own docstring (trap 1) says it
      refuses, and it is house-wide rather than new — `refetch` follows the shape `budget` has had
      since c4-12. A floor belongs on all three at once, which is why it is not this story's patch.
    location: >-
      scripts/cdp_harness.py — cmd_budget, _report_push, _report_refetch
    severity: low
  - summary: >-
      The cold-open render budget (NFR-05) was observed EXCEEDING 1,000 ms on 2 of 5 runs during
      c7-7's Flow 1 walk, on the same instrument that measured 311/363/428 ms at c4-12.
    evidence: |-
      `cdp_harness budget` run A over a copied data dir: 420 / 547 / 1076 ms (exit 2), with two
      runs over budget; an immediate re-run gave 420 / 512 / 754 ms (exit 0). Both are recorded in
      this spec's review addendum rather than only the green one. No `ui/src` runtime byte moved in
      c7-7, so this is not a regression this story introduced — the plausible causes are the OS file
      cache on a freshly copied 325 MB `cards.db` and a machine that had just run two full suites,
      but that is an explanation and not a measurement. The whole distribution has moved well above
      c4-12's figures on the same instrument, and beat 2 of Flow 1 is therefore recorded as
      observed-with-an-outlier. Needs a quiet-machine re-measurement before the epic closes.
    location: >-
      scripts/cdp_harness.py budget — NFR-05, Flow 1 beat 2
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Epic C7 built every link of the chain and **nothing has ever watched the whole chain run.** Five gaps, each found rather than assumed: (1) **no test anywhere observes a `deck_changed` that originated in a mutation tool arriving at a socket** — `test_deck_changed_wiring.py` has the tool and the notifier but no companion, `test_live_backend.py:344` has the process and the socket but hand-builds an `active_deck_changed` envelope, and the middle is unproven; (2) Flow 1's beats are covered piecewise across four `describe`s and **no test walks UJ-1 in one sitting**; (3) **"within roughly a second" has never been measured** for this path — c4-12 observed cold open (311/363/428 ms) and c6-9 observed push (15/21/36 ms), and neither is a commit→repaint number, so SC-2 would close on an argument; (4) the read-only-glass property rests on three indirect guards (`posture.test.ts:341`, `store-writes.test.ts:153`, `:222`) and **nothing forbids a mutating verb** — `grep "method:" ui/src` is empty by omission, not by rule; (5) the swallowed-emit path has never faced a **real HTTP failure through a mutation tool** (only a stubbed `PushOutcome`), and the AC-mandated recording of the accepted staleness window lives only in planning artifacts — `client.py:580` and `server.py:103` are both silent about it.

**Approach:** Close each gap where it is, and record what it cost. One new phase inside the **one** real-process integration test (AD-10 stays one test, one function). A UJ-1 Flow 1 walk in `App.test.tsx` composing the shipped harnesses. A `read-only-glass` guard that bans the mutating verbs outright. A real-loopback 500 proof at the tool level. The staleness ruling written into the two code sites that actually swallow. And a committed `refetch` subcommand on the CDP harness that produces the commit→repaint figure SC-2 closes on — the c4-12/c6-9 instrument, extended rather than re-derived.

## Boundaries & Constraints

**Always:** AD-10 stays intact — the loop proof is a **new phase inside `test_the_real_channel_end_to_end`**, not a new test function and not a new file; the docstring's "Nine phases" count and every phase number stay consistent with reality after the edit. Its subject is the notifier path, so it goes **through** `src.companion.client` deliberately, while every hand-rolled phase stays hand-rolled — the wire-contract independence that `test_live_backend.py:30-38` protects is untouched, and the new phase says so in its own comment. The phase must run while a socket is open on a live backend, with a bound on every await (`_RECV_DEADLINE`). Measurements refuse to report a number for an invalid run — the C4 trap `cdp_harness.py:29-33` exists to refuse; a run that produces no valid figure is recorded as **NOT OBSERVED**, never rounded into a claim. `cdp_harness refetch` takes an **explicit `--data-dir` pointing at a COPY** (`cmd_budget:394-398`'s rule) and **undoes its own mutation** so a re-run is idempotent. Every firing proof goes through the committed harnesses (`vitest_probe_harness --control` warm first, then `--expect-total N --expect-red`; `probe_harness --expect-red` for Python), tree staged before planting, reverted with `git diff --exit-code`. Story branch `feat/companion-c7-7-uj-1-end-to-end` off umbrella `feat/companion-c7`; PR targets the umbrella.

**Block If:** Closing the loop turns out to require **booting a second real backend process** (a second `integration`-marked process test is an AD-10 amendment and an architecture decision, not a story decision) — HALT rather than add one. Or: the commit→repaint measurement cannot be run against a **copy** of a data directory and would have to mutate the operator's real one — HALT rather than write to it.

**Never:** No new MCP tool, route, event kind, `reason` token, store, container, or document-level listener. No production behaviour change on the frontend — this story is coverage, a guard, doc prose, and an instrument; if a `ui/src` runtime byte moves, the mirrors are rebuilt and committed, but nothing here should move one. No repair of anything the walk merely observes: `test_live_backend.py:26-28`'s rule ("record it, not repair it from a test") governs the new phase too. No homing the **unowned** format-check pass→violation announcement (`deferred-work.md:4782-4800`) — it still needs a human UX ruling. No staleness warning in the UI (accepted until FR-16, AD-9). No edit to `sprint-status.yaml` (Brad flips it post-merge). No change to the c7-3/4/5/6 behaviours the walk composes, and no move of the corridor pins at `App.test.tsx:1815-1830`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| The loop, across processes | Live companion + open WS client; `add_card_to_deck` called through a real MCP session | The socket receives `{kind:'deck_changed', payload:{deck_id}}` for exactly that deck; elapsed tool-return→delivery recorded | Bounded `recv`; a miss fails the test, never hangs the run |
| The loop, deletion | `delete_deck` on the same deck | Socket receives `deck_changed` carrying the now-absent id | Same bound |
| UJ-1 climax in the glass | Booted deck, `deck_changed` pushed with an added creature | Card in its type group, group count +1, new curve bar, colour pips shift, header count updates, one announcement — with **no user event dispatched after the push** | N/A |
| A new card's tile | Same push | Tile mounts **without** `data-flashed` (a new tile's appearance is itself the signal, `CardTile.tsx:310-317`); the glow row stays the quantity-bump case | N/A |
| Pin survives dismissal (beat 6) | Suggestions view open, row clicked to pin, Esc | Detail panel still shows the pinned card after the view closes, and still shows it after the climax refetch | N/A |
| Emit POST rejected by a real backend | Real loopback server: `/health` valid, `POST /agent/events` → 500 | Mutation persists, result **byte-identical** to the no-companion baseline, nothing raises, the POST is recorded as really sent | Swallowed + logged; `backend_error` |
| Emit to a wedged backend | Listener accepts, never answers | Mutation still returns `ok`; cost capped by the 1 s `_NOTIFY_TOTAL_SECONDS` bound | Swallowed |
| Any mutating verb in `ui/src` | A `method:`/`sendBeacon`/`<form`/`FormData` spelling appears | The guard fails and names the file | N/A |
| A measurement run that renders nothing | Surfaces never arrive / receipt says `clients: 0` | Harness prints INVALID and refuses a number; exit non-zero | Recorded NOT OBSERVED |

</intent-contract>

## Code Map

**The loop, across processes (AC 1a)**
- `tests/integration/companion/test_live_backend.py` -- the ONE real-process test. `_Backend` :107, `live_data_dir` :221 (monkeypatches `PLANESWALKER_DATA_DIR` for **this** process too, which is exactly why the real notifier will find the running backend's record), `backends` :242, the walk :274, phases at :281/296/308/319/332/344/371/392/412. The open-socket block is :319-390 — **the new phase belongs inside it, on `backend_one`, before the PHASE 8 restart**; renumber the tail and the docstring's "Nine phases" (:18-22, :277-279) together. `_RECV_DEADLINE` :103. Read-only rules to honour: :26-28 (record, don't repair), :30-38 (`push_event` stays hand-rolled — the new phase's use of the client is a *different subject*, and must say so).
- `src/mcp_server/server.py` -- `_emit_deck_changed` :103-123 (the one wrapper; resolves `_notify_deck_changed` as a module global at call time), `create_deck` :260/emit :286, `delete_deck` :307/:322, `add_card_to_deck` :326/:367, `import_decklist` :371/:399, `remove_card_from_deck` :403/:434. All emits are outside the session block. **Docstring gap:** `_emit_deck_changed` never states the accepted staleness window (AC 3's second half).
- `src/companion/client.py` -- `notify_deck_changed` :580, `_NOTIFY_TOTAL_SECONDS = 1.0` :131, the bound applied :646-650, the swallow :651-655 (`except Exception` → `backend_error`), `EVENTS_PATH` :84, envelope minted :639-644. Same docstring gap.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` -- the in-process MCP pattern to copy: `deck_db` fixture :114-128 (file-backed sqlite, two seeded cards), `build_server(session_factory=…)` + `create_connected_server_and_client_session` :415-417. `_RecordingNotifier` :143, `notifier` fixture :170. Existing failure coverage: :403-435 (stubbed outcomes, byte-identical result), :441-472 (real client, no companion). **Absent: a real HTTP failure through a tool.**
- `tests/unit/companion/test_client.py` -- the loopback toolkit to reuse for that: `_StubServer` :196, `StubFleet` :298, `stub_server` fixture :369, `_Sockets` (silent/dead/drip) :381 + `sockets` fixture :481, `health_bytes` :493, `plant_discovery` :506. Cross-test import precedent: `test_deck_changed_wiring.py` already imports `_REPO_WRITE_METHODS` from `test_import_boundary.py`.

**The glass walk (AC 1b, AC 2)**
- `ui/src/App.test.tsx` -- harnesses, all shipped: `bootedDeck()` :3198 (the canonical live-ish entry), `push(kind, payload, id)` :144, `deckDetail(overrides)` :183, `deckCard(name, typeLine, qty, manaCost, cmc)` :164, `answering(...)` :355, `settle()`/`advance(ms)` :414/:416, `decksPolls`/`detailReadsOf`/`pathsSince` :3195/:3189/:3187, `creatureGroupCount()` :3217, region helper :3825 + `settleCount()` :3826, dialog fixtures `dialog()` :4159 / `SUGGESTIONS` :4667 / `pushRows` :5155, `escape()` :5164, `tiles()`/`detailName()`/`unpinControl()` :3500-3502, `focusablesNow()` :1773. The closest existing analogue — and the thing the walk must not duplicate assertion-for-assertion — is :3223 (c7-3 AC 1: type group, curve bar, colour pips, header count, one hydration, one format-check). The glow row is :4043 (a **quantity bump**, not an addition). Do not move :1815-1830.
- `ui/src/containers/CardTile/CardTile.tsx` :310-317 -- a freshly mounted tile never flashes; unit pin `CardTile.test.tsx:913`. The walk asserts *absence* of the glow on a genuinely new card and pins the reason.
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md` :181-193 -- Flow 1's nine beats; the walk covers 2 (deck fills), 5 (view blooms), 6 (pin survives Esc), 9 (climax). :219 is the ruling that beat 6 is *why* click-to-pin exists.

**The audit (AC 4)**
- `ui/tests/read-only-glass.test.ts` -- **NEW**. Source-scan guard over `ui/src/**`: no `method:` on any request init, no `sendBeacon`, no `FormData`, no `<form`, no `XMLHttpRequest.open` with a verb; plus a positive pin that the one door is a bare GET. Follow the house shape: comment-stripped source (`posture.test.ts:159-187` has the stripper and its non-vacuity anchor), exhaustive set equality, a per-rule non-vacuity anchor.
- `ui/src/api/client.ts` :821 -- the one `fetch`, with no `method` option. `ui/tests/posture.test.ts` :144-149 (`BEHAVIOUR_FAMILIES`), :322-341 (one door, set equality), :344-352 (App is not the second). `ui/tests/store-writes.test.ts` :84-87 + :152-154 (`useDeckStore` written only by `src/state/deck.ts`), :203-224 (the slice has no input but the wire). `ui/tests/gate-geometry.test.ts` :42-59 — a new file in `ui/tests/` must satisfy it.

**The measurement (AC 1c)**
- `scripts/cdp_harness.py` -- `Companion` :245 (child on `uv run`, `PLANESWALKER_DATA_DIR` :262, `stop()` kills the tree), `Browser` + `measure_budget` (surfaces/observer, refuses a run whose surfaces did not arrive), `cmd_budget` :391 (the `--data-dir` refusal :394-398, the PUT that sets the active deck :406-412, fresh profile per run), `PUSH_SURFACES` :469, `cmd_push` :697 (warm/blocked/cold arms, priming push, `_print_run` :779, `_report_push` :805 — the "no valid runs, refuse a number" branch). `build_parser` :923. **NEW `refetch` subcommand**: copy-dir data dir + `--deck-id`, boot, set active deck, open a warmed page, then drive a real mutation in-process (`build_server(session_factory=…)` over the copied `cards.db` + the memory client session, with `PLANESWALKER_DATA_DIR` set so the real notifier dials the running companion) and stop the clock at the new card's tile in the DOM; undo the mutation after each run. Two clocks, as `cmd_push` has: bracket, and from-tool-return.
- Observed precedents to match in shape: `c6-9-…md:646-651` (`15/21/36 ms warm-art (n=5)`), `c4-12-…md:1798` (`311/363/428 ms fresh profile … against a 1,000 ms budget`).

**Read-only evidence (do not change):** `ui/src/state/deck.ts` :566-569 (404-clear), :583 (`refetchSettles`), :630-646 (coalescing), :814-823 (the decision table); `ui/src/state/connection.ts` :137-150; `src/companion/app/routes/agent_events.py` :64-104 (ingest + `clients` receipt); `src/companion/app/ws.py` :352 (`broadcast`), :90/:462 (`/ws`); `.github/workflows/ci.yml` :226-286 (why the integration lane is path-scoped, and that a new file there would run); `ARCHITECTURE-SPINE.md` :227-240 (AD-10), :211-225 (AD-9 + the accepted staleness window), :101-112 (AD-2).

## Tasks & Acceptance

**Execution:**
- Task 0: baseline -- `cd ui && npm test` **warm** (expect 79 files / 2256), then `uv run python -m scripts.vitest_probe_harness --control` and record the `--expect-total` it prints; `uv run pytest -m "not integration"` (expect 3020 passed / 1 skipped / 55 deselected). Cut `feat/companion-c7-7-uj-1-end-to-end` off `feat/companion-c7` and record the baseline revision in frontmatter.
- `tests/integration/companion/test_live_backend.py` -- add the loop phase inside the open-socket block on `backend_one`: a file-backed deck DB, `build_server` + an in-process MCP client session, `create_deck` → `add_card_to_deck` → `delete_deck`, each asserted to arrive on the **real socket** as `deck_changed` with the right deck id; assert the add's envelope shape against the contract and record the tool-return→delivery elapsed in the phase's output. Renumber the following phases and the docstring's phase count in the same edit. State in the phase comment why this one goes through `src.companion.client` while the others do not.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` -- add the real-HTTP-failure class: a `_StubServer` whose `/health` is valid and whose `POST /agent/events` answers **500**, plus a wedged-listener row paying the real 1 s bound. Assert per row: mutation persisted, result byte-identical to the no-companion baseline, `isError is False`, nothing raised, and the POST was really sent (recorded on the stub) — the non-vacuity that separates "swallowed" from "never attempted".
- `src/mcp_server/server.py` + `src/companion/client.py` -- prose only: `_emit_deck_changed` and `notify_deck_changed` each record the accepted staleness window as **expected behaviour until FR-16** (AD-9), naming the UI's silence as deliberate. This discharges the half of AC 3 that currently lives only in planning artifacts.
- `ui/src/App.test.tsx` -- new `describe('UJ-1 end to end — the loop closes (c7-7)')`: one continuous walk over Flow 1's beats 2, 5, 6, 9 (deck fills → suggestions view blooms on a push → click-to-pin → Esc dismisses, pin stands → `deck_changed` with an added creature → the four visible consequences + one announcement + the pin still standing), asserting **no user event is dispatched after the climax push**; plus the new-tile no-glow row with its reason pinned. Reuse the shipped harnesses; do not restate c7-3's :3223 assertions verbatim — the walk's subject is the *sequence*, and its comment says which story owns each beat.
- `ui/tests/read-only-glass.test.ts` (new) -- the AC 4 audit guard, per the Code Map's rule list, with a non-vacuity anchor per rule and a positive pin that `client.ts`'s single `fetch` sets no `method`.
- `scripts/cdp_harness.py` -- the `refetch` subcommand + its parser entry, per the Code Map; it refuses a run that renders nothing and undoes its own mutation.
- `tests/unit/test_cdp_harness.py` (new) -- the matrix's last row, which is the *refusal*: `_report_refetch` and `_print_refetch_run` are pure functions over run dicts, so the "measured nothing → refuse a number" branch is provable with no browser, no process and no network. Refusal rows paired with positive twins (C6 R8), each refusal asserting the **absence** of the figure line as well as the non-zero exit.
- Firing proofs -- frontend: warm `--control` first, then one plant per new guard/walk claim through `vitest_probe_harness --expect-total N --expect-red '<substring>'`, revert (`git diff --exit-code`), final `--expect-green`. Python: one plant per new proof through `probe_harness --expect-red '<node id>'`, revert, `--expect-green`. Paste every proof line verbatim.
- Measurement -- copy the real data dir (`%LOCALAPPDATA%/artificial-planeswalker`, ~325 MB), then `uv run python -m scripts.cdp_harness refetch --data-dir <copy> --deck-id <the largest deck in that copy> --runs 5`. The deck is chosen the way c4-12 chose its subject: the largest real deck present (a ~99-card Commander deck), read from `GET /api/decks`; the card added is read from the copied `cards.db` and must be one the deck does not already hold, so the climax is an *appearance*. Paste the min/median/max against the 1,000 ms budget in the c4-12/c6-9 sentence shape. If no valid run is produced, paste the harness's refusal verbatim and record **NOT OBSERVED** with the reason — never a rounded number.
- Measurement, the OTHER two beats (added at review, P1) -- AC 2 names three latency clauses and only one of them is `refetch`'s. Beat 2 (*deck loads within 1 s*) is `cdp_harness budget` and beat 5 (*suggestions bloom within 250 ms*) is `cdp_harness push --arm warm`; both instruments are already committed and both were previously discharged by **quoting c4-12 and c6-9 in prose**. Run all three against the **same copied data dir in one sitting** and record the three figures together as the Flow 1 walk, so the AC closes on observation rather than on citation. A refusal from either is recorded verbatim as NOT OBSERVED with its reason.
- Verification & artifacts -- `cd ui && npm run lint && npm run format:check && npm test`; `uv run pytest -m "not integration"`; `uv run pytest tests/integration/companion/`; `cd ui && npm run build && uv run python -m scripts.build_plugin` then confirm **zero drift** in `src/companion/app/static/` and `plugin/` (this story expects no runtime change; if any byte moved, commit both mirrors and say why).

**Acceptance Criteria:**
- Given a live companion process with a browser-shaped WebSocket client attached, when a real MCP mutation tool commits a change, then that client receives a `deck_changed` envelope carrying the mutated deck's id — the first time in the repo's history that a tool-originated event is observed arriving at a socket — and the same holds for a deletion, with the observed tool-return→delivery time recorded.
- Given the app is open on a loaded deck and the agent adds a card, when the resulting `deck_changed` drives the refetch, then the card appears in its type group with the group count raised, the curve bar for its mana value appears, the colour distribution shifts, the header count updates, and the change is announced exactly once — with no user event dispatched to the browser after the push.
- Given Flow 1 of `EXPERIENCE.md`, when its beats are walked in one continuous sequence, then the deck view fills, a suggestions push blooms its view open, a pinned card survives dismissing that view, the pin still stands after the climax refetch, and every beat's owning story is named in the walk.
- Given the emit POST fails against a real HTTP backend after the mutation has persisted, when the tool returns, then its structured result is byte-identical to the no-companion baseline, nothing raises, the POST is recorded as genuinely attempted, and the accepted staleness window is stated as expected behaviour until FR-16 in the two code sites that swallow.
- Given the shipped frontend source, when it is audited for mutating requests, then no `method:`, `sendBeacon`, `FormData`, `<form` or verb-carrying `XMLHttpRequest.open` exists anywhere in `ui/src`, and the single network door is pinned as a bare GET.
- Given the commit→repaint path, when it is measured through the committed CDP harness against a copied data directory, then a min/median/max figure is recorded against the 1,000 ms budget — or, if no valid run is produced, the harness's refusal is recorded verbatim as NOT OBSERVED with its reason.
- Given the guard suites (shell, keyboard-floor, store-writes, posture, tokens, token-usage, copy-rules, wire-contract, gate-geometry) and the Python suite, when they run, then all pass at their expected counts with no runtime behaviour change, and `uv run pytest -m "not integration"` still boots no server process.

## Spec Change Log

- **The wedged-backend row uses `drip()`, not `silent()` — found by its own firing proof, not predicted.** The I/O matrix says *"Listener accepts, never answers"*, which is `_Sockets.silent()`. Implemented that way, the row passed — and so did the planted regression that removes `_NOTIFY_TOTAL_SECONDS` from `notify_deck_changed`. Reason: `PROBE_TIMEOUT`'s own `read=2.0` ends a silent exchange, so dropping the ~1 s whole-call budget moves the tool call from ~1 s to ~2 s only, and no ceiling loose enough to survive CI jitter is tight enough to catch it. `drip()` answers headers and then feeds body bytes forever, so **no per-read deadline can fire** and only a whole-operation deadline ends it: ~1 s with the budget, ~5 s (`_PROBE_TOTAL_SECONDS`) without. Ceiling set at 3.0 s. The proof reddens on the replant.
- **Two teardown defects in the new `refetch` subcommand, both found by running it rather than by review.** (1) `_Agent` kept an event loop and called `run_until_complete` per tool call; the figures printed and the process then died with *"Attempted to exit cancel scope in a different task than it was entered in"* — `create_connected_server_and_client_session` is an anyio task group and anyio pins its cancel scope to the entering task. The session now lives in one `_serve` coroutine on a dedicated thread, driven over a queue. (2) `cmd_refetch`'s `finally` stopped at the first raising step, skipping `companion.stop()`, which stranded a backend holding the port and made the *next* invocation refuse to start. The teardown is now explicit and total, on `test_live_backend.py`'s rule.
- **`test_deck_changed_wiring.py`'s header sentence "nothing here opens a socket" is now false and was corrected rather than preserved.** The two new rows bind loopback listeners in-process. The property AD-10 actually constrains — *no test outside `tests/integration/companion/test_live_backend.py` boots a companion process* — is unchanged and is what the header now states; `tests/unit/companion/test_client.py` has opened real loopback sockets in the ordinary `-m "not integration"` set since c1-8.
- **The matrix's ninth row had no covering test, and the whole harness module had none — added at the step-03 matrix audit.** "A measurement run that renders nothing → refuses a number" was implemented and never exercised, which is precisely the shape the C4 retrospective recorded (every probe harness that lied did so by producing zero results and being scored anyway) and precisely the shape `cdp_harness.py`'s own trap 1 promises to refuse. `budget` and `push` have carried the same unexercised branch since c4-12; `refetch` no longer does. Scope held to the reporting seam — the browser-driving half still needs Chrome and a copied data dir and stays an operator tool.
- **`vitest_probe_harness` crashes on a test id containing a non-cp1252 character** (`UnicodeEncodeError` in `print(f"  RED    {nodeid}")`, sighted on `inspection.test.ts`'s `absent → absent` row). Worked around with `PYTHONIOENCODING=utf-8`; **not repaired here** — it is a harness defect outside this story's boundary, recorded rather than fixed (`test_live_backend.py:26-28`'s rule applied to a tool).

- **Review round 1 (2026-08-15): 19 patches, 18 applied, 1 partially dismissed.** Three of them found things that were genuinely wrong rather than merely unpolished, and all three are recorded above with the plant that reddens them: `ui/index.html` was outside the read-only-glass sweep while rule 4 exists precisely for it (a real `<form>` passed the guard); the `refetch` data-dir gate let `<real>/copy` through and let an exported `PLANESWALKER_DATA_DIR` disarm the platform-default check; and `refetch` never re-checked that the repaint it timed was push-driven, so a dropped socket would have been reported as an SC-2 figure for the reconnect path. AC 2's beat-2 and beat-5 latency clauses moved from citation to observation, and beat 2 came back with an outlier that is recorded rather than re-run away. P4's causal claim about the comment stripper was dismissed with a measurement (the walker copies string spans, it does not delete them), while its actual ask — real-file anchors in both directions plus a JSX-apostrophe case — was implemented.

## Review Triage Log

### 2026-08-15 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 19: (high 0, medium 6, low 13)
- defer: 3: (high 0, medium 1, low 2)
- reject: 12: (high 0, medium 0, low 12)
- addressed_findings:
  - `[medium]` `[patch]` AC 2's beat-2 and beat-5 latency clauses were discharged by citation to c4-12/c6-9 rather than observed in this walk — ran `budget` and `push` beside `refetch` against one copied data dir and recorded all three figures, including a beat-2 run that exceeded NFR-05 (deferred, not re-run away).
  - `[medium]` `[patch]` The `refetch` measurement never re-checked that the repaint it timed was push-driven (`_SOCKET_LIVE` sampled once, before the primer) — each run now samples the socket at measure time and counts the `deck_changed` frames the page actually received; zero frames, a dead socket or a stamp preceding t0 invalidates the run.
  - `[medium]` `[patch]` `ui/tests/read-only-glass.test.ts` could not see `ui/index.html`, the one shipped file rule 4's own justification describes — sweep widened to `git ls-files index.html src`; a planted `<form action="/api/deck" method="post">` passed before the patch and reddens after. A sixth rule (`.send(`) was added for the WebSocket write channel the first five walked past.
  - `[medium]` `[patch]` The guard's stripper carried synthetic anchors only — added real-repo-file anchors in both directions, a JSX-apostrophe case and a whole-tree "no file was silently emptied" anchor. The finding's causal claim was dismissed with a measurement (see Spec Change Log); its ask was implemented.
  - `[medium]` `[patch]` Two new test ids carried U+2019/U+2014 in the story that documented `vitest_probe_harness`'s `UnicodeEncodeError` on printing a failing id — every test id this story adds is now ASCII, with the reason in the block header.
  - `[medium]` `[patch]` The `refetch` real-data-dir gate was untested and doubly bypassable (plain equality let `<real>/copy` through; mirroring `data_dir()`'s precedence let an exported `PLANESWALKER_DATA_DIR` disarm the platform-default check) — `operator_data_dirs()` now refuses nesting both ways over both candidates without creating any directory, with 16 twinned rows and two firing proofs.
  - `[low]` `[patch]` `_Agent`'s "the one place this harness imports from `src`" was false and the module header was unamended for its first mutating subcommand — both corrected.
  - `[low]` `[patch]` `_card_the_deck_does_not_hold`'s `LIMIT 20000` window made the held-name exclusion partial while the docstring claimed it total — corrected, with the runtime `present=False` gate named as what actually protects the measurement.
  - `[low]` `[patch]` `test_cdp_harness.py`'s scope docstring overstated what needs Chrome, and `_run()`'s fixture was pinned only to itself — the run dict now comes from a shipped builder both sides use, so a key rename fails in CI rather than mid-measurement.
  - `[low]` `[patch]` `_Agent` lifecycle: `close()` raising when `_serve` died before `_requests` existed, `call()` blocking against a dead serve task, `except BaseException` swallowing Ctrl-C and continuing the loop, and a silent join.
  - `[low]` `[patch]` `cmd_refetch` teardown and validation: `start()` outside the try, the undo not guaranteed on a raising run, `--runs < 1` accepted, `_largest_deck` without `raise_for_status`, `layout_ms <= 0` not filtered.
  - `[low]` `[patch]` Phase 8's bare `recv()` per tool made the repo's only loop proof mis-pair on any extra frame — now a kind-filtered `_recv_deck_changed`; the tautological "in order" claim now reads the frames' own `ts` stamps; the scratch DB moved out of the live backend's data directory; `deliveries` typed.
  - `[low]` `[patch]` The user-event recorder's comment cited `focusin` while the list omitted it, and "announced exactly once" rested on two proxies a clear→re-announce cycle would satisfy.
  - `[low]` `[patch]` AC 3's frontend half was unasserted — added the row where a swallowed emit leaves the deck standing, silent, with no error and no staleness warning (planting one reddens it).
  - `[low]` `[patch]` The guard reported a `file:line` computed on stripped source, and its door slice used a bare `indexOf('fetch(')` with a string-blind paren walk.
  - `[low]` `[patch]` `src/companion/client.py` cited `src/state/connection.ts` for a file at `ui/src/state/connection.ts`.
  - `[low]` `[patch]` The two AC-3 docstrings were independent copies of one ruling with no cross-reference and no AD-9 locator.
  - `[low]` `[patch]` The spec's Verification section was stale after the matrix-audit addendum (counts, and `test_cdp_harness.py` in no command).
  - `[low]` `[patch]` Verified the new `describe` resets every slice it touches — no change needed; the block already reset all three.

## Design Notes

- **Why the loop phase extends the one test instead of adding a file.** AD-10 (`ARCHITECTURE-SPINE.md:232-240`) and `ci.yml:226-231` both say "exactly one" — and `ci.yml` is **path-scoped**, so a new file in that directory would silently become a second real-backend test with no gate objecting. The existing walk already owns a booted backend, a live discovery record and an open socket; the loop phase needs precisely those three and nothing else. The file's own rule that it does not go through `client.push_event` is about pinning the **wire contract** independently; the new phase's subject is the **notifier path**, which cannot be observed without the client, and the hand-rolled phases stay hand-rolled beside it.
- **Why the walk overlaps unit coverage on purpose.** `App.test.tsx:3223` already proves the three visible consequences of one refetch. What no test proves is that the *sequence* holds — that a pin taken during a suggestions view is still standing after a climax refetch two beats later, with the announcement firing once across the whole run. Acceptance walks are allowed to re-observe; they are not allowed to be the only place a behaviour is pinned, which is why each beat's comment names its owning story.
- **The glow is the one AC term that must be asserted in the negative.** UJ-1 step 9 says "its quantity badge flashes", but a genuinely new card mounts a new tile, and `CardTile.tsx:310-317` makes a freshly mounted tile flash-free by design — the appearance *is* the signal. The quantity-bump glow is already proven through the real refetch path at `:4043`. The walk therefore asserts the new tile does **not** carry `data-flashed` and cites the ruling, rather than quietly reading the AC as a defect.
- **Why the budget is measured rather than argued.** SC-1 closed on `15/21/36 ms` observed; SC-2 should close the same way. Nothing in the repo has ever timed commit→repaint: c4-12 timed cold open and c6-9 timed push-to-render. The harness is the committed instrument precisely so the next reader re-runs a measurement instead of re-deriving a method, and its refusal branches are load-bearing — a run that renders nothing must not become a number.
- **The measurement mutates a copy, and puts it back.** `cmd_budget:394-398` already tells the operator to copy the data dir; `refetch` inherits that and adds an undo, so a five-run measurement leaves the copy as it found it and can never touch the real one.
- **What this story does not fix.** The unowned format-check pass→violation announcement stays unowned (`deferred-work.md:4782-4800`); the panel→deck mirror focus drop stays ledgered from c7-6; anything the new phase surfaces in a real process gets recorded, not repaired (`test_live_backend.py:26-28`).
- Known flake context: the frontend cold-run eslint timeout (R5, seven sightings) — run the harness control **warm**.

## Observed Results (2026-08-15)

**Baselines (Task 0).** `cd ui && npm test` warm: `Test Files 79 passed (79) / Tests 2256 passed (2256)`. `uv run python -m scripts.vitest_probe_harness --control`: `CONTROL GREEN — score the planted run with:  --expect-total 2293` (run after the story's tests landed; the pre-story control was 2256). `uv run pytest -m "not integration"`: `3020 passed, 1 skipped, 55 deselected in 285.59s`. Branch `feat/companion-c7-7-uj-1-end-to-end` off `feat/companion-c7` at `a4110a8`.

**AC 1a — the loop, observed for the first time.** `uv run pytest tests/integration/companion/` → `1 passed in 4.47s` (was `1 passed in 7.20s` before the phase; the new phase costs nothing measurable). Its recorded figure:

```
c7-7 AC 1a  tool-return -> socket delivery: create_deck 0.000 ms (whole call 63.0 ms),
add_card_to_deck 0.000 ms (whole call 46.0 ms), delete_deck 0.000 ms (whole call 47.0 ms)
```

The finding, and it is the expected one: **the frame is already in the browser-shaped client's receive buffer by the time the tool returns.** The emit is an awaited call inside the tool (AD-9's bounded await, never a detached task), so tool-return -> delivery is sub-microsecond and the emit's whole contribution to a mutation's latency is the 46-63 ms of the call itself.

**AC 1c — commit -> repaint, measured (SC-2).**

```
uv run python -m scripts.cdp_harness refetch --data-dir C:/Users/brads/AppData/Local/Temp/ap-c77-copy   --deck-id 813d0434-1bed-4419-bf9d-d9e4070704c4 --runs 5

deck 813d0434-... ('Atraxa Counter Cabinet v2 (owned)', 99 distinct cards); adding '"Ach! Hans, Run!"'
  prime (discarded): 75 ms
  run 1: commit->repaint 172 ms (from tool return 120 ms, bracket 52 ms)  100 tile(s) on the glass
  run 2: commit->repaint 159 ms (from tool return 39 ms, bracket 120 ms)  100 tile(s) on the glass
  run 3: commit->repaint 261 ms (from tool return 150 ms, bracket 110 ms)  100 tile(s) on the glass
  run 4: commit->repaint 264 ms (from tool return 147 ms, bracket 117 ms)  100 tile(s) on the glass
  run 5: commit->repaint 299 ms (from tool return 95 ms, bracket 203 ms)  100 tile(s) on the glass

commit->repaint over 5/5 valid runs: min 159 / median 261 / max 299 ms   (SC-2 budget: 1000 ms;
conservative bracket -- t0 stamped before the tool call)
  the browser's own share (t0 at the tool returning): min 39 / median 120 / max 150 ms
```

In the c4-12/c6-9 sentence shape: **159/261/299 ms commit->repaint on a real 99-card Commander deck (n=5, warm page) against a 1,000 ms budget** — SC-2 closes on an observation, not an argument. The copy was left as found: 99 `deck_cards` rows for the deck and zero rows anywhere for the added card, verified after the run.

**Firing proofs — frontend** (`--expect-total 2293`; tree staged before each plant, `git diff --exit-code` clean after each revert):

```
plant  ui/src/api/client.ts        method: 'POST' added to the one fetch init
  RED  |node| tests/read-only-glass.test.ts > ... > bans 'a request init carrying a verb'
  RED  |node| tests/read-only-glass.test.ts > ... > hands its init NO verb, and the init is really there

plant  ui/src/containers/CardTile/CardTile.tsx   flash sentinel seeded 0 instead of the mount prop
  RED  |dom| src/App.test.tsx > UJ-1 end to end — the loop closes (c7-7) > does NOT flash the new
       card's badge — a new tile's appearance is itself the signal
  (+ 3 pre-existing c7-5/CardTile rows)

plant  ui/src/state/inspection.ts   R9 membership rule reverted to the pre-R9 deck lookup
  RED  |dom| src/App.test.tsx > UJ-1 end to end — the loop closes (c7-7) > walks Flow 1 — deck fills,
       view blooms, pin survives Esc, and the climax lands untouched
  (+ c7-4's suggestion-pin row and inspection.test.ts's truth-table row)

final  vitest: 80 files / 2293 tests, 0 failed, exit 0
```

**Firing proofs — Python** (`scripts.probe_harness`, full `-m "not integration"` suite, 3023 collected):

```
control  full suite: 3023 collected, 0 failed, exit 0

plant  src/companion/client.py   budget=_NOTIFY_TOTAL_SECONDS dropped from the notify call
  RED  tests/integration/mcp_server/test_deck_changed_wiring.py::
       TestARealHttpFailureCostsTheMutationNothing::
       test_a_wedged_backend_pays_the_bound_and_the_mutation_still_returns_ok
  (+ test_client.py's own one-second-budget row)

plant  src/mcp_server/server.py   add_card_to_deck's emit condition made unreachable
  RED  ...::TestARealHttpFailureCostsTheMutationNothing::
       test_a_real_500_after_the_commit_leaves_the_result_byte_identical
  (+ 3 pre-existing c7-2 emit rows, and the wedged row)

final  full suite: 3023 collected, 0 failed, exit 0
```

**Firing proof — the integration loop phase** (outside `probe_harness`'s marker scope, so run by hand):

```
plant  src/mcp_server/server.py   _emit_deck_changed announces None instead of the deck id
  RED  tests/integration/companion/test_live_backend.py::test_the_real_channel_end_to_end
       assert frame["payload"]["deck_id"] == loop_deck_id
       AssertionError: ('create_deck', {... 'payload': {'deck_id': None} ...})
revert  git diff --exit-code clean; 1 passed in 4.47s
```

**Verification & artifacts.** `cd ui && npm run lint && npm run format:check && npm test` — eslint + stylelint clean, prettier clean, `80 files / 2293 tests` (was 79/2256: +1 file for the guard, +35 guard rows, +2 walk rows). `uv run pytest -m "not integration"` — green at 3023 collected (+2 rows, both the new HTTP-failure ones); still boots no server process. `uv run pytest tests/integration/companion/` — 1 passed. `npm run build && uv run python -m scripts.build_plugin` — **zero drift in `src/companion/app/static/`** (no `ui/src` runtime byte moved, as intended). `plugin/server/src/{companion/client.py,mcp_server/server.py}` DID move and are committed: they mirror the two AC-3 docstrings and carry no behaviour.

### Addendum — the matrix audit (2026-08-15, step-03)

Row 9 of the I/O matrix ("a measurement run that renders nothing") had no covering test: `scripts/cdp_harness.py` had no tests at all. `tests/unit/test_cdp_harness.py` adds ten, and its firing proof ran through the committed harness with the tree staged first:

```
plant  scripts/cdp_harness.py   _report_refetch's no-valid-runs branch returns 0 instead of 1
full suite (-m 'not integration'): 3033 collected, 2 failed, 0 errored, exit 1
  RED    tests/unit/test_cdp_harness.py::TestARunThatMeasuredNothingIsRefused::test_no_valid_runs_refuses_and_prints_no_number
  RED    tests/unit/test_cdp_harness.py::TestARunThatMeasuredNothingIsRefused::test_a_mutation_that_did_not_succeed_is_not_a_measurement

revert  git diff --exit-code -- scripts/cdp_harness.py  clean
final   full suite (-m 'not integration'): 3033 collected, 0 failed, exit 0
```

Counts after the addendum: **Python 3033 collected** (3032 passed, 1 skipped, 55 deselected), frontend unchanged at **80 files / 2293 tests**, `tests/integration/companion/` `1 passed in 4.77s`, and `git status --porcelain -- src/companion/app/static/ plugin/` shows only the two already-committed docstring mirrors — zero new drift.

Every matrix row is now covered by a test that ran and passed: rows 1-2 by `test_live_backend.py`'s PHASE 8, rows 3-5 by the c7-7 walk and its no-flash row in `App.test.tsx`, rows 6-7 by `TestARealHttpFailureCostsTheMutationNothing`, row 8 by `read-only-glass.test.ts`, row 9 by `test_cdp_harness.py`.

### Addendum — the four-layer review (2026-08-15)

0 intent_gap, 0 bad_spec, 19 patches, 2 defers. **18 applied, 1 partially dismissed with evidence.**

**P1 — AC 2's other two latency clauses, now observed rather than cited.** The AC names three, and
only beat 9's was measured; beats 2 and 5 rested on c4-12's and c6-9's figures quoted in prose. All
three instruments run against the **same copied data dir, in one sitting**:

```
budget  (beat 2, deck loads within 1 s)      -- run A
  run 1: 500 ms   run 2: 547 ms   run 3: 1076 ms   run 4: 1046 ms   run 5: 420 ms
  layout time over 5/5 valid runs: min 420 / median 547 / max 1076 ms   (NFR-05 budget: 1000 ms)
  -> EXIT 2. TWO OF FIVE RUNS OVER BUDGET.

push --arm warm  (beat 5, suggestions bloom within 250 ms)
  warm arm, layout over 5/5 valid runs: min 17 / median 19 / max 37 ms   (SC-1 budget: 250 ms)
  card images fetched over the network per run: [0]; painted per run: [6]     -> EXIT 0

refetch  (beat 9, commit -> repaint within 1 s)
  run 1: 221 ms   run 2: 243 ms   run 3: 236 ms   run 4: 240 ms   run 5: 240 ms
                  (each: 100 tile(s) on the glass, 1 deck_changed frame(s))
  commit->repaint over 5/5 valid runs: min 221 / median 240 / max 243 ms   (SC-2 budget: 1000 ms)
  the browser's own share (t0 at the tool returning): min 34 / median 36 / max 86 ms   -> EXIT 0

budget  (beat 2, again -- see below)          -- run B
  layout time over 5/5 valid runs: min 420 / median 512 / max 754 ms   -> EXIT 0
```

**Both budget runs are recorded, and that is deliberate.** Run A exceeded NFR-05 on two of five
cold opens; run B, on the same copy minutes later, did not. The difference is almost certainly the
OS file cache on a freshly copied 325 MB `cards.db` plus a machine that had just finished running
two full test suites — but *almost certainly* is an explanation, not a measurement, and this story's
own rule is that a number is what was observed. Recording only run B would be running until green.
**Beat 2 is therefore recorded as OBSERVED-WITH-AN-OUTLIER, not as clean**, and it is carried to the
retro as a manual-checklist item. Nothing here changed cold-open behaviour: no `ui/src` runtime byte
moved on this story, and both figures sit well above c4-12's 311/363/428 ms on the same instrument,
which is itself worth a look. Beats 5 and 9 pass cleanly.

**P2 — a repaint the harness cannot attribute to a push is no longer a measurement.** `_SOCKET_LIVE`
was sampled once before the primer; if the socket had dropped, the SPA's reconnect re-drive would
produce the tile and `refetch` would print a plausible figure for the wrong path. Each run now
samples the pill *at measure time* and counts the `deck_changed` frames the page actually received —
via a document-start `Proxy` over `window.WebSocket` that adds a listener and touches nothing the app
does. Zero frames, or a dead socket, or a stamp preceding t0, invalidates the run. The primer doubles
as the wiring check for the counter. Visible in every run line above: `1 deck_changed frame(s)`.

**P3 — `ui/index.html` was outside the sweep, and rule 4 is exactly about it.** Widened to
`git ls-files index.html src` (`token-usage.test.ts:740-742`'s pathspec). **The hole was real**: a
`<form action="/api/deck" method="post">` planted in the shipped HTML document passed the guard
before this patch and reddens it after. A **sixth rule** was added rather than declaring the gap —
`client.ts` opens a real WebSocket and `socket.send(...)` carries no verb, no init and no `fetch`, so
the first five walk straight past a page talking back up the channel.

**P4 — the ask applied, the causal claim DISMISSED WITH EVIDENCE.** Real-file stripper anchors in
both directions and a JSX-apostrophe case are added (and the whole-tree "no file was silently
emptied" anchor besides). But the finding's mechanism — *"a straight apostrophe can open a phantom
string span that swallows the code after it, which would make every ban pass vacuously"* — is **not
true of this stripper**, and the difference from c4-11 is the point. c4-11's `withoutComments` was a
REGEX that DELETED what it matched. This is `posture.test.ts`'s WALKER, and every character inside a
string span is appended to the output (see the `out += source[index]` in the string branch).
Measured: `stripComments("<p>don't</p>\n<form onSubmit={x}>\nnavigator.sendBeacon(u)\n")` returns
its input **byte for byte**, with `<form` and `sendBeacon` both intact. A phantom span can only let a
comment survive into the output, which produces a false POSITIVE and never a vacuous pass. The
residue is fail-safe, the direction is now stated in the stripper's docstring, and the new
`does not let a straight apostrophe in JSX text swallow the code after it` row is the tripwire.

**P5 — every test id this story added is now pure ASCII**, and the block header says why: the
mandated `vitest_probe_harness` prints failing ids to a cp1252 console and dies on anything outside
it (sighted on this very story). A row nobody can cheaply plant against later is a row that rots.

**P6 — the gate is exercised, and it was weaker than it looked.** Both holes the review named were
real and both now redden: plain equality let `<real>/copy` through, and mirroring `data_dir()`'s
precedence meant an exported `PLANESWALKER_DATA_DIR` left the **platform-default** directory
unguarded. `operator_data_dirs()` now returns both candidates and refuses nesting in either
direction, and it resolves them **without calling `data_dir()`**, which creates the directory it
resolves — wrong for a gate and wrong for a unit test. Sixteen new rows, every refusal paired with a
positive twin (C6 R8).

**P7-P19 applied as described.** Of note: the `_recv_deck_changed(kind=...)` filter in phase 8
(P12) removes a whole false-negative class from the repo's only end-to-end loop proof; the ordering
claim there is now read off the frames' own `ts` stamps rather than off the tool names `_call`
appended; the phase's scratch database moved out of the live backend's data directory; and P14 added
the frontend half of AC 3 — the glass standing still, silent, with no error and no staleness wording,
when an emit is swallowed. **P19 needed no change**: the block already reset inspection, deck memory
and the agent view in its own `beforeEach`.

**Firing proofs — frontend** (warm control `--expect-total 2305`; tree staged, each revert
`git diff --exit-code` clean):

```
plant  ui/index.html                <form action="/api/deck" method="post">
  RED  |node| tests/read-only-glass.test.ts > ... > bans 'an HTML form (a write affordance that...'

plant  ui/src/state/socket.ts       socket.send('{"kind":"hello"}')
  RED  |node| tests/read-only-glass.test.ts > ... > bans 'a socket write (the WebSocket carries...'
  (+ posture.test.ts's one-door row)

plant  ui/src/state/inspection.ts   R9 membership rule reverted to the pre-R9 deck lookup
  RED  |dom| src/App.test.tsx > UJ-1 end to end - the loop closes (c7-7) > walks Flow 1: ...

plant  ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx   a role="alert" staleness warning
  RED  |dom| src/App.test.tsx > UJ-1 end to end - the loop closes (c7-7) > stands still and says
       nothing when the emit is swallowed (AC 3, the accepted staleness window)
  (+ the walk, + 8 DeckAnnouncer rows)

final  vitest: 80 files / 2305 tests, 0 failed, exit 0
```

**Firing proofs — Python** (`scripts.probe_harness`, 3049 collected):

```
plant  scripts/cdp_harness.py   the gate goes back to plain equality
  RED  tests/unit/test_cdp_harness.py::TestTheRealDataDirectoryIsRefused::
       test_a_directory_inside_the_real_one_is_refused[copy]
  RED  ...::test_a_directory_inside_the_real_one_is_refused[copies/one]
  RED  ...::test_a_directory_containing_the_real_one_is_refused

plant  scripts/cdp_harness.py   the gate mirrors data_dir()'s precedence
  RED  ...::TestTheRealDataDirectoryIsRefused::
       test_the_platform_default_is_refused_even_when_an_override_is_exported

plant  scripts/cdp_harness.py   the deck_changed-frame check disabled
  RED  ...::TestARepaintThisHarnessCannotAttributeToAPushIsNotAMeasurement::
       test_a_run_that_received_no_deck_changed_frame_is_refused
  RED  ...::test_the_per_run_line_names_the_reconnect_hazard

final  full suite (-m 'not integration'): 3049 collected, 0 failed, exit 0
```

**Firing proof — the integration loop phase**, re-run after P12's edits:

```
plant  src/mcp_server/server.py   _emit_deck_changed announces None
  RED  test_live_backend.py:570  assert frame["payload"]["deck_id"] == loop_deck_id
revert  git diff --exit-code clean; 1 passed in 4.51s
```

**Counts after the review.** Frontend **80 files / 2305 tests** (2293 -> +11 guard rows for rule 6
and the stripper anchors, +1 walk row for AC 3's frontend half). Python **3049 collected**
(3033 -> +16 in `tests/unit/test_cdp_harness.py`, which went 10 rows -> 26). Integration
`1 passed in 4.51s`. `cd ui && npm run lint && npm run format:check` clean.
`npm run build && build_plugin` -> **zero drift in `src/companion/app/static/`**; the two
`plugin/server/src/**` Python mirrors carry the P16/P17 docstring edits and nothing else.

### Deferred from this review

- The **cold-open outlier** above (beat 2, two of five runs over NFR-05 on run A) is recorded, not
  chased. It is a pre-existing property of the cold open on a 325 MB database, no `ui/src` byte
  moved on this story, and repairing it is neither this story's boundary nor a change a test can
  drive — `test_live_backend.py:26-28`'s "record it, not repair it" applied to a measurement. Carry
  it to the Epic C7 retro.

## Verification

**Commands:**
- `cd ui && npm run lint && npm run format:check && npm test` -- expected: eslint + stylelint clean, prettier clean, `tsc -b` clean, every vitest file green including the new guard; count risen by the walk + guard only.
- `uv run python -m scripts.vitest_probe_harness --control` (warm), then per-plant `--expect-total N --expect-red '<substring>'`, revert, `--expect-green` -- expected: each plant RED on its named test, reverts byte-clean, final green.
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` per Python plant, then `--expect-green` -- expected: same shape for the new backend proofs.
- `uv run pytest -m "not integration"` -- expected: green at **3049 collected** (3021 before the story; +2 real-HTTP-failure rows in `test_deck_changed_wiring.py`, then +10 at the step-03 matrix audit and +16 more at the review in `tests/unit/test_cdp_harness.py`, which went 10 rows -> 26); still no server process booted.
- `uv run pytest tests/unit/test_cdp_harness.py` -- expected: green; the reporting refusal AND the real-data-dir gate, both reachable with no Chrome, no companion and no network.
- `uv run pytest tests/integration/companion/` -- expected: the one walk passes with its new phase; note the wall-clock (was `1 passed in 7.20s`).
- **The Flow 1 walk, all three instruments, one copied data dir** (AC 2's three latency clauses):
  - `uv run python -m scripts.cdp_harness budget --data-dir <copy> --deck-id <largest> --runs 5` -- beat 2, against 1,000 ms.
  - `uv run python -m scripts.cdp_harness push --data-dir <copy> --arm warm --runs 5` -- beat 5, against 250 ms.
  - `uv run python -m scripts.cdp_harness refetch --data-dir <copy> --deck-id <largest> --runs 5` -- beat 9, against 1,000 ms.
  Expected: five valid runs each and a min/median/max apiece, or an explicit refusal recorded verbatim as NOT OBSERVED. `refetch` additionally refuses the operator's real data dir, undoes every add, and invalidates any run it cannot attribute to a `deck_changed` frame.
- `cd ui && npm run build && uv run python -m scripts.build_plugin && git status --porcelain -- src/companion/app/static/ plugin/` -- expected: **zero drift** (no runtime change intended).

**Manual checks (if no CLI):**
- The real perceptual climax — a card genuinely appearing under Brad's eye with no browser action, the curve bar growing, the glow reading as garnish rather than signal — is what every jsdom test isolates away. Carry it, plus the c7-4/c7-5/c7-6 items already flagged, to the Epic C7 manual-testing checklist at the retro.

## Auto Run Result

Status: done
Blocking condition: none

**What was implemented.** Epic C7's closing story: the loop that the epic built link by link is now
watched end to end, and what it costs is measured rather than argued. A new phase inside the repo's
ONE real-process integration test drives real MCP mutation tools against a real companion process
and asserts the `deck_changed` frames arriving at a real WebSocket client — the first time in the
repo's history that a tool-originated event has been observed reaching a socket. A UJ-1 walk in
jsdom carries Flow 1's beats in one sitting, with "Brad never touched the app" as an actual
recorded assertion rather than a claim. A new `read-only-glass` guard bans the six ways a browser
can write, over the shipped markup as well as the modules. A real-loopback 500 and a wedged
listener prove the swallowed-emit path through real HTTP, and the accepted staleness window is now
stated in the two code sites that do the swallowing. A committed `refetch` subcommand on the CDP
harness produced SC-2's number: **221 / 240 / 243 ms commit→repaint on a real 99-card Commander
deck (n=5, warm page) against a 1,000 ms budget.**

**Files changed**
- `tests/integration/companion/test_live_backend.py` — PHASE 8, the loop across processes (AD-10 intact: one file, one function); tail phases renumbered, docstring count corrected.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` — `TestARealHttpFailureCostsTheMutationNothing`: a real loopback 500 and a drip-fed wedged listener, byte-identical results, POSTs proven sent.
- `src/mcp_server/server.py`, `src/companion/client.py` — docstring prose only: the accepted staleness window as expected behaviour until FR-16, cross-referenced.
- `ui/src/App.test.tsx` — the UJ-1 walk, the new-tile no-glow row, and AC 3's staleness-silence row.
- `ui/tests/read-only-glass.test.ts` (new) — the AC 4 audit guard, six rules, each with firing and silent anchors.
- `scripts/cdp_harness.py` — the `refetch` subcommand, its push-attribution invalidation, and its real-data-dir gate.
- `tests/unit/test_cdp_harness.py` (new) — the reporting refusal and the data-dir gate, both browser-free.
- `plugin/server/src/{companion/client.py,mcp_server/server.py}` — generated mirrors of the two docstrings.

**Review findings.** 4 layers (blind-hunter, edge-case-hunter, verification-gap, intent-alignment).
0 intent_gap, 0 bad_spec, **19 patches** (6 medium, 13 low — 18 applied, 1 of which was applied
while its causal claim was dismissed with a measurement, and 1 verified as needing no change),
**3 deferred** (1 medium, 2 low, in frontmatter), **12 rejected**. Three patches found real defects:
`ui/index.html` sat outside the sweep of the guard whose own rule 4 exists for it, the data-dir gate
was doubly bypassable, and the measurement could not tell a push-driven repaint from a reconnect.

**Follow-up review recommended: true.** Patched findings by severity: high 0, medium 6, low 13
(counting only findings triaged `patch`; the one needing no change is excluded from the score).
Score = 3 × 6 + 1 × 12 = 30, which is ≥ 5.

**Verification performed** (all re-run by the workflow after the patches, not only by the
implementer): `uv run pytest -m "not integration"` → **3048 passed, 1 skipped, 55 deselected**;
`uv run pytest tests/integration/companion/` → **1 passed in 4.45s**; `cd ui && npm run lint` →
eslint + stylelint clean; `npm run format:check` → clean; `npm test` → **80 files / 2305 tests
passed**; `npm run build && uv run python -m scripts.build_plugin` → bundle byte-identical
(`index-DJ7dGud2.js`), **zero drift** in `src/companion/app/static/`, only the two Python mirrors
moved. Every matrix row is covered by a test that ran and passed. Firing proofs: 4 frontend plants,
5 Python plants and 1 integration plant across the story, each RED on its named row, each reverted
`git diff --exit-code` clean, both harness controls finally green.

**Residual risks**
1. **The cold-open outlier.** Flow 1's beat 2 came back at 420/547/**1076** ms on one run (two of
   five over NFR-05) and 420/512/754 ms on the immediate re-run. Both are recorded. No `ui/src`
   runtime byte moved in this story, and the whole distribution sits well above c4-12's
   311/363/428 ms on the same instrument. Deferred with a call for a quiet-machine re-measurement
   before the epic closes — this is the one number in the story that should not be taken at face
   value.
2. **SC-2's figure is an operator measurement, not CI.** That is the c4-12/c6-9 precedent and the
   reason the harness is committed, but the number lives in this document rather than in a gate.
3. **The perceptual half is unprovable in jsdom** — real screen-reader silence, the real focus
   landing, the glow reading as garnish. Carried to the Epic C7 manual-testing checklist.
4. **Two claims about shipped code changed during this story**: `test_live_backend.py`'s "does not
   go through `src.companion.client`" now carries a stated exception, and
   `test_deck_changed_wiring.py`'s "nothing here opens a socket" was false once the real-HTTP rows
   landed and was corrected rather than preserved. Both are argued in place; both are the kind of
   amendment a human should agree with rather than inherit silently.
