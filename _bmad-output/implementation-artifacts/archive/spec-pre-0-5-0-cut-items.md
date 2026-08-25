---
title: 'Pre-0.5.0-cut items: epic-17 retro items 1–5 + epic-16 items 91/92/93'
type: 'chore'
created: '2026-08-23'
status: 'done'
baseline_revision: '030d53c5a4e2b62017216d0fb910167a4bc3dbfd'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['multiple-goals', 'oversized']
deferred:
  - summary: >-
      The release-gating quiet-machine re-measure was never obtained: both the item-8 session and
      the review pass found the machine loaded (bg3_dx11 foreground, CPU ~22-28% vs the ~6% quiet
      baseline), so the quiet-machine drift trend (c4-12 363 → R2 420 → 17.3 529 ms medians) has no
      comparable fourth point for Brad's 0.5.0 cut decision.
    evidence: |-
      perf-evidence-precut-2026-08-23.md D1 records the loaded run verbatim (587/652/798 ms,
      EXIT 0 — budget safe a fortiori); the review pass re-sampled CPU at 26-28% with bg3_dx11
      still running, so the ~3-minute quiet re-run stayed non-executable unattended. Instrument,
      deck and JSON path are ready.
    location: >-
      _bmad-output/implementation-artifacts/perf-evidence-precut-2026-08-23.md
    severity: medium
  - summary: >-
      SuggestionsView still lacks the E16-91 whitespace-id gate its three sibling views now carry:
      a suggestions item with card_id '  ' hydrates for real and commits /api/cards/%20.
    evidence: |-
      ui/src/containers/SuggestionsView/SuggestionsView.tsx cardIdOf is still the bare coercer;
      no test in SuggestionsView.test.tsx feeds a whitespace-only card_id. Pre-existing — E16-91's
      ruling named only TierListView and SwapsView — surfaced by the verification-gap reviewer,
      which demonstrated the request path end-to-end.
    location: >-
      ui/src/containers/SuggestionsView/SuggestionsView.tsx
    severity: medium
  - summary: >-
      A non-latest history revisit still clears unread[kind] even though the newest push (which the
      kind pill keeps re-opening after the R3 guard) was never seen — the unread semantics were
      outside R3's ruling and need their own ruling before changing.
    evidence: |-
      openAgentView clears unread[content.kind] unconditionally; the R3 guard scopes only the
      retained write. Scenario: newest push arrives unread, user revisits an older envelope from
      the History popover — the kind reads as seen.
    location: >-
      ui/src/state/agentView.ts
    severity: medium
  - summary: >-
      The companion skill's branch list has no arm for companion_status's 'error' status, which is
      in the tool's closed vocabulary.
    evidence: |-
      .claude/skills/companion/SKILL.md step 2 branches on running/not_running only;
      test_the_status_vocabulary_is_closed pins {running, not_running, error}. Pre-existing since
      17.4.
    location: >-
      .claude/skills/companion/SKILL.md
    severity: low
---

<intent-contract>

## Intent

**Problem:** The epic-17 retro (accepted-with-open-items, `epic-17-retro-2026-08-23.md`) ruled five remediation items and pulled epic-16 items 91/92/93 into the pre-cut window; item 5 (cold-open diagnosis + re-measure) is release-gating for 0.5.0. Until they land, shipped code states falsehoods (`companion_status` unknown-vs-zero tabs), an unguarded Escape seam couples the epic's own two stories, a history revisit corrupts the latest-per-kind contract, `--open` races a not-yet-listening socket, two ledger lines contradict spec frontmatter, and the performance evidence predates the last two stories.

**Approach:** Land all eight items as focused commits on `feat/companion-epic-17` (the normal dev loop before the integration PR): UI hardening + tests, backend/tool honesty + tests, skill copy + plugin rebuild, ledger corrections, and a fresh quiet-machine `budget`-arm measurement with a per-surface drift diagnosis recorded as committed evidence.

## Boundaries & Constraints

**Always:** Prove each new guard test with a planted violation through the committed harnesses (`scripts.probe_harness` for pytest, `scripts.vitest_probe_harness` — `--control` first, warm — for vitest) and paste the proof lines into the run record. Rebuild `plugin/` when skills or `src/` change (pre-commit hook enforces). Keep AD-15: no `src.companion.app.*` import in `src/mcp_server/tools/companion.py`; `webbrowser` only in `server.py`. Conventional Commits. The measurement copies the operator data dir (robocopy to scratchpad) — never point the harness at `C:\Users\brads\AppData\Local\artificial-planeswalker` itself, and never commit the copy.

**Block If:** The re-measure produces zero valid runs after two attempts, or Chrome/the data dir/deck `813d0434-1bed-4419-bf9d-d9e4070704c4` is unavailable — HALT `blocked`, condition `cold-open re-measure not executable`. (A median/max over budget is NOT a block: record it verbatim as a deviation for Brad's cut decision and continue.)

**Never:** Do not touch epic-17 retro action item 6 (post-0.5.0 deferred bundle: R4 ResizeObserver, R8 skills-vocabulary gate, R9 instrument hardening, R10 tooltip hedge, A5 positive control) or epic-16 item 95. Do not change the hero art, the `no-cache` policy family, push-message wording tables, or `_serve`/uvicorn handoff beyond `sock.listen()`. Do not edit `AppShell.tsx`. Do not "fix" the drift by changing budgets or the instrument's validity rules.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| status: tabs open | health `clients >= 1` | "…{n} tab(s) open — nothing to do." (unchanged) | — |
| status: zero tabs | health `clients == 0` | current no-tab message (unchanged) | — |
| status: unknown count | `clients` absent or negative | distinct message saying the tab count is unknown (older companion), not asserting "no browser tab is open"; still read-only | never a negative count in copy |
| Esc during IME/consumed | `isComposing` or `defaultPrevented` keydown | ConnectionPill suppression bit NOT latched | — |
| Esc with popover open + tooltip revealed | one Escape | popover closes (it `preventDefault()`s); pill tooltip stays revealed | — |
| history revisit of non-latest entry | `reopenPush(oldId)` | view opens old envelope; `retained[kind]` and pill recency untouched | — |
| kind-pill reopen / latest revisit | entry `=== retained[kind]` | unchanged behavior (self-assignment fine) | — |
| `--open` fast browser | browser request lands before uvicorn starts | connection queued (socket listening), served when uvicorn accepts | no connection-refused |
| lock-held launch | instance lock held, no identity yet | skill names the "already starting up" outcome: wait/re-check, no retry loop | — |
| whitespace ids in tier/swaps | `card_ids: ['', '  ', 'c-real']` | one tile; blank ids never render, count, or hydrate | no `/api/card-image/%20` |
| re-measure over budget | median or max ≥ 1000 ms | recorded verbatim as deviation + flagged in run record for Brad | not a HALT |

</intent-contract>

## Code Map

**Item 1 — Escape seam (R1/A4/A7):**
- `ui/src/containers/ConnectionPill/ConnectionPill.tsx:126-132` — document Escape listener, positive polarity `event.key === 'Escape'`, no guards → normalize to the negated early-return form with `isComposing`/`defaultPrevented` (matches AgentViewsNav:403/420). Stale comment at `:121-125` ("the only Escape-consuming surface is the agent view") — rewrite to name the History popover.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx:33-37` — cites deleted `AppShell.tsx:200` `slot(nav, …)` text as live → repair to past tense/17.5 reality. `closePopover` `:348-359` vs duplicated subscription body `:376-386` — collapse (subscription body calls `closeRef.current()`; `closeRef` declared `:346`, kept fresh `:360-362`).
- `ui/tests/keyboard-floor.test.ts:719-752` census (ConnectionPill already listed `:751`); non-vacuity loop `:789-800` names only 3 files probing literal `"event.key !== 'Escape'"` → after normalization add the 4th path.
- `ui/src/App.test.tsx:6408-6700` — 17.2 History block; no test composes popover + pill tooltip. Add one: reveal tooltip (`fireEvent.focus`/`mouseEnter` on pill button per `ConnectionPill.test.tsx` idiom, tooltip = `getByRole('tooltip')`, suppression = `className` contains `is-suppressed`), open popover, one `fireEvent.keyDown(document.body, {key:'Escape'})` → popover closed, tooltip not suppressed.

**Item 2 — companion_status honesty (R2/R7):**
- `src/mcp_server/tools/companion.py:822-831` — `clients` fold + `if clients:` conflates None with 0 → three-way branch; docstring `:795-796` updated. Existing stub test `test_an_older_companion_without_the_count_reads_as_no_tab` (in `TestCompanionStatusIsReadOnlyAndNamesTheNextStep`, `tests/integration/mcp_server/test_companion_tool.py:1449`, fixture `status_stubs` `:1425`) must flip to the new unknown-arm message.
- `.claude/skills/companion/SKILL.md:28` — `clients 0 (or null) — nobody is looking` → split: `0` = nobody looking (run launch_command); `null` = count unknown (older companion; a tab may already be open — prefer giving the user the `url` over popping a possibly-duplicate tab). Mirror `plugin/skills/companion/SKILL.md` via rebuild.
- Real-parse test: `StubFleet`/`stub_server` fixture (`tests/unit/companion/test_client.py:295-370`, redeclared in `test_deck_changed_wiring.py:510`) serves any GET path; `health_bytes(instance_id, **extra)` helper (`test_client.py:493`). Drive `companion_status` with real `_client_live_instance`/`_client_probe_health` against a stub serving `health_bytes("…", clients=1)` on a real socket, discovery record pointing at `stub.port` (pattern: `_record(port=…)` `test_companion_tool.py:1421`; degradation twin at `test_companion_degradation.py:134-150`). Identity in the health body must match the discovery record for `live_instance` to verify.

**Item 3 — `--open` launch window (R5/R6):**
- `src/companion/app/server.py:385-388` — wrong "bound and listening" comment; add `sock.listen()` before `_open_browser` (uvicorn's later `listen()` on the same socket is harmless); `bind_localhost_socket` docstring `:176-177` ("deliberately not listened") — amend to name the `--open` exception or move listen unconditionally with docstring updated.
- Tests: `tests/unit/companion/test_server.py` `class TestOpenBrowser:949` (fixtures `recorded_serve`, `browser`, `loopback`). New test: with `_serve` stubbed, a client `socket.connect` to the bound port succeeds at the moment `_open_browser` is invoked (proves listen precedes browser).
- `.claude/skills/companion/SKILL.md` step 3 (~`:42`) names only the URL line and `already running at` → add the third stdout outcome `another companion is already starting up` (server.py:359): wait, then re-run `companion_status`; do not retry the launch in a loop.

**Item 4 — history-revisit retained guard (R3):**
- `ui/src/state/agentView.ts:435-455` `openAgentView`; retained write `:452`. Latest-for-kind check is reference identity: entry in `history` holds the SAME object as `retained[kind]` (docstring `:280-298`; `ts` unsafe, `id` unordered). Guard: when `content` is already in `state.history` and `content !== state.retained[content.kind]`, keep `state.retained` unchanged (one-clause conditional on the retained value only; status/content/unread writes unchanged; `historyWith` `:411-433` arm 1 already no-ops on same reference). Update docstring `:345-355` write enumeration. `reopenPush` `:520-524` needs no change. Store tests live beside the existing agentView state tests (locate by `reopenPush`/`retained` in `ui/`): add revisit-leaves-retained-unchanged + kind-pill-reopen-still-writes cases.

**Item 5 — cold-open diagnosis + re-measure (R11/A10, release-gating):**
- Ledger fixes: `_bmad-output/implementation-artifacts/spec-17-3-measure-latency-budgets-close-gaps.md:156` and `perf-evidence-17-3-2026-08-22.md:254-255` both say "`deferred` stays empty" while spec frontmatter carries the medium cold-open-drift deferral → correct both lines to name the one deferred item (do not touch the frontmatter or other lines).
- Hero cache header: ALREADY pinned — `tests/unit/companion/test_spa.py:375` `test_the_hero_art_is_served_from_the_bundle_root` asserts `image/jpeg` + `cache-control: no-cache` (+ `TestCacheHeaders:341` family; policy in `src/companion/app/spa.py:348-371`, `_REVALIDATE_CACHE_CONTROL:72`). R11's "no test pins it" is contradicted by source: verify the test exists and is green, cite it in the evidence doc; add nothing unless it is missing.
- Re-measure: robocopy `C:\Users\brads\AppData\Local\artificial-planeswalker` → scratchpad copy (exclude nothing; ~454 MB); sample CPU quietness (17.3 recorded ~6% samples); run `uv run python -m scripts.cdp_harness budget --data-dir <copy> --deck-id 813d0434-1bed-4419-bf9d-d9e4070704c4 --runs 5 --json _bmad-output/implementation-artifacts/nfr05-budget-2026-08-23.json` (argparse `scripts/cdp_harness.py:1989-2000`; measures last-of-six-surfaces layout ms vs literal 1000; fresh Chrome profile per run; needs the committed SPA bundle). Chrome present at `C:\Program Files\Google\Chrome\Application\chrome.exe`.
- Diagnosis: prior JSONs `nfr05-budget-2026-08-22.json` (layout `[430.6,528.6,531.0,433.2,960.3]`; spread lives entirely in the `format-check` surface — `header` ~37 ms, other panels ~90-107 ms) and `nfr05-quiet-remeasure-2026-08-16.json`; write `perf-evidence-precut-2026-08-23.md` (hardware/conditions, verbatim console, per-surface comparison table across the three sessions, where the drift lives, hero-pin citation, unambiguous deviations section; model on `perf-evidence-17-3-2026-08-22.md`). 17.4/17.5 landed no code on the measured deck-view path (hero renders only in the no-deck Welcome arm, `ui/src/App.tsx:604-605`) — the diagnosis must confirm or refute that from the numbers.

**E16-91 — whitespace-id filter port:**
- Reference: `ui/src/containers/GroupsView/GroupsView.tsx:136-141` `cardIdsOf` trimmed-non-empty filter; pinned test `GroupsView.test.tsx:223-240` (`card_ids: ['', '  ', 'c-group-3']` → 1 tile, count `'1'`).
- `ui/src/containers/TierListView/TierListView.tsx:137,141-142` — `cardIdOf` coerces, keeps blanks (consumed `:309,:323`) → adopt GroupsView-style filter in its `cardIdsOf`; clone the pinned test into `TierListView.test.tsx`.
- `ui/src/containers/SwapsView/SwapsView.tsx:100` — same coercer (used `:246,:252,:275-276,:293`) → trim guard: whitespace-only → `''` so the existing unknown/`cardId === ''` arm handles it (swaps rows are single ids, not lists); pinned test in `SwapsView.test.tsx` (`'  '` → unknown arm, never hydrates).

**E16-92 — docstring accuracy (one commit + plugin rebuild):**
- `src/mcp_server/server.py:718` (groups tool docstring) "the companion skips that group's tiles" → "the group is not displayed at all".
- `src/mcp_server/tools/companion.py:317` "all three tables" → four (test at `test_companion_tool.py:1328-1331` reads all four).
- 64 KB envelope note (`src/mcp_server/server.py:739-744`, groups only) → copy the equivalent note into `companion_show_tier_list` (`:652`) and `companion_show_swaps` (`:603`) `Args: payload:` blocks with each tool's own worst-case phrasing. Check the four schema-publication guards in `test_build_plugin.py` (298/326/352/377) still pass.

**E16-93 — guard hardening pair:**
- New test in `test_companion_tool.py`: each of `_PUSH_MESSAGES:312` / `_SWAPS_PUSH_MESSAGES:408` / `_TIER_LIST_PUSH_MESSAGES:504` / `_GROUPS_PUSH_MESSAGES:658` has keys exactly `set(get_args(PushOutcomeToken)) - {'displayed'}` (`PushOutcomeToken` = `src/companion/client.py:144-149`; verify the actual key set first — widened vocabulary must fail by name).
- Mirrors for swaps/tier_list/groups of the suggestions-only closed-app coverage: `TestTheAppBeingClosedIsReportedAndNothingMore:758` and `test_no_clients_connected_is_pushed_once_and_never_re_sent:677`; plus sibling-channel-empty assertions in the swaps/tier delivery tests (mirror how the suggestions tests assert; existing per-kind classes at `:843/:1016/:1192`).

## Tasks & Acceptance

**Execution (suggested commit per item; run the relevant suite after each):**
1. `ui/src/containers/ConnectionPill/ConnectionPill.tsx` + `AgentViewsNav.tsx` + `ui/tests/keyboard-floor.test.ts` + `ui/src/App.test.tsx` — Escape-seam hardening per Code Map item 1 — R1/A4/A7.
2. `ui/src/state/agentView.ts` + its store tests — retained-write guard per Code Map item 4 — R3 (ruled).
3. `ui/src/containers/TierListView/*` + `SwapsView/*` + tests — whitespace-id filter port — E16-91.
4. `src/mcp_server/tools/companion.py` + `.claude/skills/companion/SKILL.md` + tests — status honesty + real-parse test — R2/R7. (Plugin rebuilds via pre-commit.)
5. `src/companion/app/server.py` + `tests/unit/companion/test_server.py` + companion SKILL.md — listen-before-open + lock-held skill bullet — R5/R6.
6. `src/mcp_server/server.py` + `src/mcp_server/tools/companion.py` — docstring accuracy — E16-92.
7. `tests/integration/mcp_server/test_companion_tool.py` — key-tie test + closed-app/sibling mirrors — E16-93.
8. Ledgers + re-measure: fix the two ledger lines; robocopy, quietness sample, run the budget arm, commit `nfr05-budget-2026-08-23.json` + `perf-evidence-precut-2026-08-23.md` with the per-surface diagnosis — R11/A10.

**Acceptance Criteria:**
- Given a health body without `clients` (or negative), when `companion_status` runs, then the result says the tab count is unknown and never claims "no browser tab is open"; given `clients: 1` over a real stub socket (no monkeypatched client functions), then the tool reports the tab.
- Given the History popover open and the pill tooltip revealed, when Escape is pressed once, then the popover closes and the tooltip is not suppressed (App-level test).
- Given a history revisit of a non-latest entry, when the view opens, then `retained[kind]` still holds the newest envelope; a kind-pill reopen still behaves as before.
- Given `--open` with `_serve` stubbed, when `_open_browser` fires, then a TCP connect to the bound port already succeeds.
- Given `card_ids: ['', '  ', <real>]` in tier-list (and the swaps analog), when rendered, then exactly one tile renders/counts/hydrates.
- Given the four push-message tables, when the vocabulary test runs, then each table's keys are pinned to `PushOutcomeToken` minus `displayed`; swaps/tier_list/groups each have closed-app and pushed-once coverage mirroring suggestions.
- Given the branch tip and a quiet machine, when the budget arm runs 5 fresh-profile runs, then a committed JSON + evidence doc exist with min/median/max, per-surface drift diagnosis, and the hero cache-header pin cited; an over-budget number is recorded as a deviation, not hidden.
- Given the two corrected ledger lines, when read against spec-17-3 frontmatter, then all three agree there is one medium deferred item.
- Given every new guard test, when its planted violation runs through the committed probe harness (full suite), then it shows RED, and the proof lines are pasted into the run record.

## Auto Run Result

**Executed 2026-08-23.** Items 1–7 landed as seven focused commits on `feat/companion-epic-17`
(`6ec1a6a` R1/A4/A7, `2c9cb38` R3, `7fd3aeb` E16-91, `5cad020` R2/R7, `54e7e53` R5/R6,
`edbc115` E16-92, `c84d4cd` E16-93); item 8's ledger fixes + re-measure evidence in the final
commit. Plugin mirrors rebuilt by the pre-commit hook per commit; `git diff --exit-code plugin/`
clean at tip.

**Deviations from the Code Map, recorded:**
- Item 1's App-level seam test delivers the Escape at the focused element (the popover entry)
  rather than `fireEvent.keyDown(document.body, …)` as the Code Map sketched: the mechanism the
  scenario table itself names — "popover closes (it `preventDefault()`s)" — is the WRAPPER
  half's `preventDefault`, which only fires when the keystroke bubbles through the wrapper.
  Fired at `document.body` the event reaches only the document halves, ConnectionPill's
  listener (registered at mount, before the popover's) sees `defaultPrevented === false`, and
  the tooltip would suppress — i.e. the Code Map's literal dispatch target contradicts its own
  expected outcome. The block's existing `escape()` helper ("Esc, delivered where a browser
  delivers it: at the focused element, bubbling") is used instead.
- E16-93's "sibling-channel-empty assertions in the swaps/tier delivery tests" live in
  `ui/src/state/socket.test.ts` (the R6 finding's actual site — the suggestions/swaps/tier
  DELIVERS tests), not in `test_companion_tool.py`; commit `c84d4cd` carries both files.
- The R2 unknown-count message reads "…did not report a usable tab count (an older companion,
  or a malformed reply) — a tab may already be open. Give the user {url} rather than opening a
  possibly-duplicate tab." — the distinct, never-negative, never-"no tab" sentence the matrix
  requires. (An earlier wording asserted "too old" as fact; the review pass reworded it, since
  ``None`` also covers a malformed or negative body.)
- E16-91's TierListView port also changes NON-string id handling: a non-string entry previously
  coerced to `''` and spent a permanently-dead unknown-card placeholder slot; the GroupsView
  filter the Code Map prescribes drops it before render, count and hydration alike, and the old
  pinned test (2 tiles, one placeholder) was rewritten to the filtered contract (1 tile).
  SwapsView deliberately keeps the placeholder arm — a swap row's two tile slots (out/in) are
  structural, so a bad id degrades one slot rather than deleting it.

**Probe-harness proofs (planted violations, full-suite runs, verbatim):**

Pytest — plants: `_push_messages` widened with a `planted_extra_token` key; the status unknown
arm reverted to the old "no browser tab is open" sentence; `sock.listen()` removed from the
`--open` path. RED run:

```
full suite (-m 'not integration'): 3341 collected, 9 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_companion_tool.py::TestEveryPushToolSpeaksItsOwnNoun::test_each_table_keys_exactly_the_client_vocabulary_minus_displayed[_PUSH_MESSAGES]
  RED    ...[_SWAPS_PUSH_MESSAGES] / [_TIER_LIST_PUSH_MESSAGES] / [_GROUPS_PUSH_MESSAGES]
  RED    tests/integration/mcp_server/test_companion_tool.py::TestCompanionStatusIsReadOnlyAndNamesTheNextStep::test_an_older_companion_without_the_count_reads_as_count_unknown
  RED    tests/integration/mcp_server/test_companion_tool.py::TestCompanionStatusOverARealSocket::test_a_real_health_body_without_the_count_reads_as_unknown
  RED    tests/unit/companion/test_server.py::TestOpenBrowser::test_the_port_accepts_a_connection_the_moment_the_browser_is_asked
  (+ expected collateral: the suggestions byte-pin and negative-count tests)
```

Plants reverted (`git diff --exit-code src/` clean), GREEN run:

```
full suite (-m 'not integration'): 3341 collected, 0 failed, exit 0
```

Vitest — control (warm, after a full `npm test`): `vitest: 86 files / 2588 tests, 0 failed,
exit 0 → --expect-total 2588`. Plants: ConnectionPill guard reverted to positive polarity with
no guards; TierListView `cardIdsOf` reverted to the coercing `map`; SwapsView `cardIdOf` trim
dropped; the agentView revisit guard forced `false`. RED run:

```
vitest: 86 files / 2588 tests, 8 failed, exit 1
  RED  keyboard-floor.test.ts > … > is genuinely reading the listeners it names (non-vacuity)
  RED  App.test.tsx > … > Esc closes the popover without suppressing the connection pill tooltip (17.1 x 17.2 seam)
  RED  agentView.test.ts > reopenPush … > re-opens the entry by IDENTITY — an older push of an already-re-pushed kind included
  RED  agentView.test.ts > reopenPush … > leaves `retained` — the OBJECT itself — untouched on a non-latest revisit (pre-cut R3)
  RED  SwapsView.test.tsx > … > renders a WHITESPACE-ONLY id as the unknown placeholder — the terminal arm, no image (E16-91)
  RED  SwapsView.test.tsx > … > never hydrates a WHITESPACE-ONLY id — it folds to the unknown arm before any request
  RED  TierListView.test.tsx > … > filters a NON-STRING id inside a tier — the good neighbour renders alone, no crash
  RED  TierListView.test.tsx > … > filters an empty or whitespace-only id — it never renders, never counts, never hydrates
```

Plants reverted (`git diff --exit-code ui/src` clean), GREEN run:
`vitest: 86 files / 2588 tests, 0 failed, exit 0`.

**Gates at tip:** `npm test` 2588/2588; `npm run typecheck && npm run lint && npm run
format:check` clean; `uv run pytest tests/unit/companion tests/integration/mcp_server
tests/integration/test_build_plugin.py` 1977 passed / 6 skipped; `ruff check` / `ruff format
--check` / `mypy src/` clean. Hero cache-header pin verified green
(`test_spa.py::test_the_hero_art_is_served_from_the_bundle_root` + `TestCacheHeaders`), so
R11's "no test pins it" is refuted — nothing added, citation carried into the evidence doc.

**Item 8 re-measure (commit `3c3aae4`; the orchestrator's matrix-audit commit `d871fc7` sits
above it):** ledger lines corrected (spec-17-3 run-result line + perf-evidence-17-3
§9 closing line now both name the one medium deferred item, agreeing with the frontmatter).
Budget arm: **587/652/798 ms over 5/5 valid runs, EXIT 0 — under budget** — but on a
NON-QUIET machine (a foreground game ran throughout; CPU samples 21.6/22.6/23.3% vs 17.3's
~6%), recorded verbatim as deviation D1 in `perf-evidence-precut-2026-08-23.md` for Brad's cut
decision: the budget verdict is safe a fortiori, the quiet-machine drift trend gains no
comparable fourth point, and a quiet re-run (~3 min) is ready to go if the cut wants one.
Diagnosis: between the two QUIET sessions the drift lives entirely in `format-check`
(header/grid flat); and the Code Map's "17.4/17.5 landed no code on the measured deck-view
path" is REFUTED at the network level for 17.5 — `/hero.jpg` (420,280 bytes) is fetched on
every cold open via the boot's transient pre-active-deck frame (`requests_total` 215→216,
format-check queue 108→109), confirmed by a URL-dump diagnostic pasted in the evidence doc.
Hero cache pin verified green and cited (§5). Artifacts: `perf-evidence-precut-2026-08-23.md`
+ `nfr05-budget-2026-08-23.json`.

**Matrix test audit (step-03, orchestrator):** every matrix row traced to a covering test that
ran and passed, with one gap found and closed — the "Esc during IME/consumed" row had only
source-string coverage (keyboard-floor probe) plus the App seam test for the consumed half; two
behavioral tests were added to `ConnectionPill.test.tsx` (commit `d871fc7`). The first draft of
the consumed-Escape test was itself caught vacuous by its own firing proof (raw
`dispatchEvent` outside `act()` — stayed green under the planted violation) and was rewritten
as a capture-phase consumer around `fireEvent`. Proofs (planted: both guards dropped from the
pill listener): control `vitest: 86 files / 2590 tests, 0 failed, exit 0 → --expect-total
2590`; RED run `vitest: 86 files / 2590 tests, 3 failed, exit 1` (the two new ConnectionPill
tests + the composed App seam test); revert `git diff --exit-code` clean; GREEN run
`vitest: 86 files / 2590 tests, 0 failed, exit 0`. The lock-held-launch matrix row is prose in
the companion skill (no runtime surface; the skills-vocabulary gate is deferred R8 by ruling) —
verified by inspection: SKILL.md step 3 names the `another companion is already starting up`
outcome with wait-and-re-check guidance. Full verification re-run by the orchestrator at tip:
vitest 2590/0, pytest targeted suites 1982 passed / 1 skipped, ruff/format/mypy clean,
`git diff --exit-code plugin/` clean.

**Review pass (2026-08-23, four parallel layers: blind hunter, edge-case hunter, verification-gap, intent-alignment):** 0 intent gaps, 0 bad-spec findings, 9 patches applied (1 medium — the stale SPA bundle — + 8 low, commits `fcdfd37`/`47503e2`/`3b47505`), 4 deferred to frontmatter (quiet re-run still blocked by the running game; SuggestionsView whitespace gap; unread-on-revisit semantics; skill `error` arm), 10 rejected. Follow-up review recommendation: patched counts high 0 / medium 1 / low 8 → score 3×1 + 8 = 11 ≥ 5 → `followup_review_recommended: true`. Post-patch verification at tip `3b47505`: vitest 2590/2590, targeted pytest suites green (254 spot + full targeted runs), ruff/format/mypy clean, plugin mirror in sync, tree clean.

**Residual risks:** the 0.5.0 cut decision still lacks a quiet-machine cold-open datapoint (deferred, medium — D1 in the evidence doc; ~3-minute re-run ready whenever the machine is quiet); the intent-alignment audit notes item 5's re-measure half is a load-confounded budget confirmation whose decision-grade content is the structural-counter diagnosis (the `/hero.jpg` +1 request refutation), which is honest but weaker than the trend point Brad's ruling asked for.

## Spec Change Log

## Review Triage Log

### 2026-08-23 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 9: (high 0, medium 1, low 8)
- defer: 4: (high 0, medium 3, low 1)
- reject: 10
- addressed_findings:
  - `[medium]` `[patch]` Committed SPA bundle was stale (last rebuilt at 17.5) — this story's UI fixes were absent from the shipped artifact; rebuilt via `npm run build` and committed with the plugin mirror (`fcdfd37`).
  - `[low]` `[patch]` Companion skill step 4 polled a `clients` count that is `null` forever against an older companion; added the no-re-poll clause (`47503e2`).
  - `[low]` `[patch]` Unknown-count message asserted "too old" as fact for what may be a malformed reply; reworded without losing the pinned substrings (`47503e2`).
  - `[low]` `[patch]` Evidence doc: 363 ms trend point uncited — attributed to c4-12 (`3b47505`).
  - `[low]` `[patch]` Evidence doc: approximate "line ~375" reference dropped for the stable test node id (`3b47505`).
  - `[low]` `[patch]` Evidence doc: added the `no-cache` = 304-revalidation note so the hero fetch's real-world cost is not overstated (`3b47505`).
  - `[low]` `[patch]` Run record: item 8's commit hash (`3c3aae4`) and the matrix-audit commit (`d871fc7`) recorded (`3b47505`).
  - `[low]` `[patch]` Run record: TierListView non-string behavior flip (placeholder-and-counts → filtered, per the ruled GroupsView-filter port) recorded as an explicit deviation (`3b47505`).
  - `[low]` `[patch]` `nfr05-budget-2026-08-23.json` trailing newline for sibling consistency (`3b47505`).

Rejected (noise / contradicted / by-design): 214→215 request move already recorded as 17.3's O2; double-listen under real uvicorn (well-defined socket semantics, disproportionate to test); SwapsView in-side whitespace twin (one shared fold function); real-socket zero/negative arms (AC named 1 and unknown; fold arms stub-pinned); `--open` test port-inference (pinned by TestRun); `closeRef` staleness (ref assigned before the subscription effect); groups sibling-empty asserts (already present, socket.test.ts:832-836); non-`--open` listen window (no consumer races that path); hero-pin "non-delivery" (R11's premise refuted by the existing test_spa pin); revisit-guard undefined-slot clause (state unreachable — resetAgentView is test-only and clears retained+history together).

## Design Notes

- ConnectionPill normalization to the negated guard form is what lets the keyboard-floor string probe cover it — do both together, not a probe that accepts two spellings.
- The retained-write guard must key on reference identity (`content !== state.retained[content.kind]` while `content` is in `history`), not `ts`/`id` ordering — the store docstring rules both out.
- For the real-parse status test, the stub server answers every GET path with the configured body, so one stub serves both the identity probe and `/health` — make the body's `instance` match the discovery record or `live_instance` will refuse.
- Vitest firing proofs: run `--control` warm (one prior `npm test`) before scoring planted runs; stage the tree before planting; revert with `git diff --exit-code <file>` as the check.

## Verification

**Commands:**
- `cd ui && npm test` — expected: all green (full vitest suite).
- `cd ui && npm run typecheck && npm run lint && npm run format:check` — expected: clean.
- `uv run pytest tests/unit/companion tests/integration/mcp_server tests/integration/test_build_plugin.py` — expected: all green.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` — expected: clean.
- `uv run python -m scripts.probe_harness --expect-red '<new key-tie test node id>'` (with planted violation) — expected: harness proof line RED, then `--expect-green` after revert.
- `uv run python -m scripts.vitest_probe_harness --control` then `--expect-total N --expect-red '<keyboard-floor|TierListView>'` (planted) — expected: proof lines.
- `uv run python -m scripts.cdp_harness budget --data-dir <scratchpad copy> --deck-id 813d0434-1bed-4419-bf9d-d9e4070704c4 --runs 5 --json _bmad-output/implementation-artifacts/nfr05-budget-2026-08-23.json` — expected: 5/5 valid runs, summary line printed; exit 0 under budget (exit 2 = over budget: record, continue).
- `git diff --exit-code plugin/` after pre-commit — expected: plugin mirror in sync.
