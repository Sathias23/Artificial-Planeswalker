# Historian digest @ ee0263d

(10 commits followed: 3b2d021, e7b83dc, 4058265, 5e49405 (root, blame only), 0032507, 642cbc6, 22c9a56, b296f99, 9b9e8af, aec9c90. Item 4 only by blame/subject.)

## 1. Exact name match
- card.py find_by_name_exact introduced 5e49405 "chore: reorganize docs per BMad Alpha.22 folder conventions" (2026-01-04, root); last touched 4058265 "perf: indexed name lookup, single-transaction import, off-loop search tools" #108 (2026-09-04), owning lines 165-170 and 194-200 (NOCASE filter).
- find_similar.py _resolve_seed introduced 3b2d021 "feat: add find_similar_cards tool + code review patches (Story 2.5)" (2026-06-24), owning 61 of 62 lines incl. the lower() line; last touched e7b83dc "chore: prune provenance from src comments and docstrings" (2026-09-04), comment only at :252.
- LB #108 (CAP-1) added NOCASE indexes + collated equality + connect-time migration; PR numbers find_by_name_exact ~58 ms SCAN -> ~0.5 ms SEARCH USING INDEX ix_cards_name_nocase; docstring: "One collated term per index: SQLite's OR optimisation needs an index for each term or it falls back to a scan." #108 did NOT touch find_similar.py (file list and stat); it moved find_similar_cards under to_thread in server.py only (CAP-2). _resolve_seed's lower() SQL left as it was.

## 2. list_decks vs list_deck_summaries
- deck.py list_decks introduced 5e49405 (root); last touched 642cbc6 "chore: clear Epic 1 tech-debt prep gate (nullability, flaky test, optional wins)" (2026-06-21).
- LB list_deck_summaries introduced 0032507 "perf: companion cold-open request diet" #109 (2026-09-04). Switched only GET /api/decks; removed comment had accepted the cost ("eager-loads every card of every deck… to compute three integers"); PR: GET /api/decks on 52 decks 99 ms -> 3 ms.
- MCP tool kept list_decks by stated scope: PR #109 "GET /api/decks uses it; list_decks and the MCP tool are untouched"; route comment "The MCP list_decks tool keeps the eager-loaded path"; PR pins MCP payloads byte-identical; no performance reason given. deck_management.list_decks from 8404f12 (Story 1.5, 2026-06-20) and 14077a9 (2026-06-28); line 309 from 8c0164f (c3-1, 2026-07-31). list_deck_summaries accepts the same format filter.

## 3. Viewer
- 9b9e8af "feat: add read-only HTML deck viewer + open-on-command script" (2026-06-27); b296f99 "feat(mcp): add view_deck tool to render a deck in the browser" (2026-06-28).
- LB 22c9a56 "chore: deprecate view_deck and freeze src/viewer (story 15.1)" #84 (2026-08-17), to master via #91: deprecation in tool docstring, FROZEN marker, tests/unit/viewer/test_viewer_freeze.py, CHANGELOG Deprecated. "removal is deferred to the next minor release once the companion is proven". Nothing shows removal carried out or rescheduled.

## 4. cache: 'no-store' (not followed)
- Introduced 22e3d40 "feat(companion): c4-1 — the one card cache with in-flight deduping" (2026-08-02); rationale comment from 9547a0d "chore: prune provenance from ui comments, styles and config prose" (2026-09-05): poll must observe backend state change (readiness re-probed per request, FR-22) and card read wants determinism against Cache-Control private max-age=3600. Card route header added in 0032507 #109. Original rationale unverified.

## 5. reconcileDeckBoot on live
- LB aec9c90 "fix: reconcile the deck boot on first connect and probe the poll after a transient deck refusal (CAP-2, CAP-3)" #113 (2026-09-06). Race: boot snapshot and socket open independent, a broadcast in the gap reached nobody. Decisions: full re-boot over id compare (would miss a same-deck deck_changed); no subscribe-first (blocked WS would never load a deck); trigger on 'live' not onReconnected; never delay first paint. Accepted cost (PR #113): "a connected cold open performs one extra active-deck, deck and format-check read after first paint… Time to first paint is unchanged."
