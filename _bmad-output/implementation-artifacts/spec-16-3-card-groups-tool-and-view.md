---
title: 'Card groups — tool and view'
type: 'feature'
created: '2026-08-21'
status: 'done'
baseline_revision: '008337e5021e8d312f431451709c23b008e97939'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - 'Empty-push copy grammar (the c6-6 ledger item, now with FOUR data points): the shared template renders "The agent sent an empty suggestions." (c6-6), "…an empty swaps." (16.1), "…an empty tier_list." (16.2), and now "…an empty groups." (16.3) — grammatically wrong, though no underscore this time. Recommendation unchanged: amend EXPERIENCE.md''s Voice-and-Tone cell to take a display noun, then substitute lowercased AGENT_VIEW_LABELS[kind] in emptyPushLine; the template is artefact-gated byte-for-byte, so the artefact moves first.'
---

<intent-contract>

## Intent

**Problem:** The agent cannot push titled card groups to the companion Glass: the `groups` wire contract exists end-to-end, but no MCP tool mints a `GroupsEvent`, and the SPA's dispatch switch still drops `groups` frames — the last unwired push kind, blocking the epic's "one pill per kind" finish line. Additionally, the group section has no `components.*` frontmatter block in DESIGN.md (the pre-c6-7 suggestion-row situation), so its two px spends have nothing to cite.

**Approach:** Amend DESIGN.md first (the c6-7 sanctioned order: artefact moves first) with a minimal `group-section` component block, then add `companion_show_groups(payload)` as the fourth tool on the 16.2-consolidated shared push path, and a `GroupsView` container rendering title + numeral count + rationale + wrapped tile row per the Voltglass group-section spec — including the EXPERIENCE.md:94 quantity-badge rule, which requires a new active-deck quantity selector. Wiring `groups` deletes the socket drop pin entirely. No contract change; no backend route change.

## Boundaries & Constraints

**Always:**
- Tool is `async def`, never raises, posts a self-built `GroupsEvent` through the existing leaf client (`push_event`), and returns exactly one of `displayed | app_not_running | no_clients_connected | payload_rejected | backend_error` plus client count; compact result (<400 chars), no payload echo. `items_pushed` counts **groups** (`len(payload.items)`), never the cards inside them — docstring says so, and a test pins it (the tiers-not-cards precedent, with ≥2 card ids per group in the fixture so a counts-cards bug is off by 2×).
- The shared path stays shared: `_GROUPS_PUSH_MESSAGES = _push_messages("groups")`; extend `_execute_push`'s value-restricted TypeVar tuple and event union by exactly `ShowGroupsResult` / `GroupsEvent`; suggestions/swaps/tier-list wording stays **byte-identical** — every existing push-tool test green untouched, and `TestEveryPushToolSpeaksItsOwnNoun` extends to the fourth noun at all three of its extension points. Result class stays a fourth distinct field-identical model (docstrings are wire-visible, "three distinct classes" prose becomes four); the tool must NOT inject a default title (`DEFAULT_TITLE_BY_KIND` gives the reader "Groups"). Success sentence: "The companion is showing {N} {group|groups} in {M} {tab|tabs}."
- Registered docstring states: Scryfall printing UUIDs (a name will not render); every cap in plain numbers (≤12 groups; per group `title` required non-blank ≤80 — explicitly disambiguated from the optional payload-level `title` ≤80 — `rationale` required non-blank ≤600, `card_ids` ≤60 each ≤128); a group may legitimately name cards the active deck does not run; empty `card_ids` and empty `items` are both legitimate; a maximal field-legal payload can still exceed the 64 KB envelope cap and come back `payload_rejected` (groups is the measured worst case); "send here **and** give your normal answer"; app-must-be-running. The word "Scryfall" must appear (guard).
- DESIGN.md amendment is minimal and additive: a `group-section:` frontmatter block carrying `divider: 1px solid {colors.border-hairline}` and `measure: 900px` (resolving the ~ in the :592 prose), plus a c6-7-style AMENDED comment explaining the artefact-first order. No renumber risk: shipped CSS citations use component paths, not line numbers.
- View: title in `--type-heading`, count as a **bare numeral** in `--type-numeric` `--text-tertiary` (tabular; no authored word — the mock's "N cards" has no copy-cell source), count = the group's valid-card-id list length (the same list the tile row renders); rationale in `--type-body` `--text-secondary` with `max-width: 900px` (cited); groups render in payload order separated by the cited hairline divider; **empty groups are skipped, not rendered as shells** (EXPERIENCE.md:94), including groups whose ids all fail the ladder; a group missing/blank `title` or `rationale` is malformed and degrades that group only; tile row is flex-wrap with derived lh-based tile geometry (the 16.2 tier-tile route — no px tile width, mock's 164px/14px are uncited drift and are not copied); thumbnails `alt=""`; standard inspection contract on every tile.
- Quantity badge: a tile shows `×N` **iff the card is in the active deck at quantity ≥1**, nothing otherwise. This deliberately differs from CardTile's `> 1` gate: here the badge's meaning is "copies in this deck" (EXPERIENCE.md:94) and in-deck-ness itself is the signal, so ×1 is informative and truthful; not-in-deck renders no badge ("×0 would be a lie"). Badge chrome reuses the existing `components.quantity-badge` tokens (own `.group-tile-quantity` class in GroupsView.css with citations); **static** — no flash animation, no `data-flashed` (pushes replace wholesale; there is no "change" to flash). Lookup via a new primitive selector `useDeckCardQuantity(cardId): number | null` on `deck.ts` (containers reading `useDeckStore` directly is sanctioned — ConnectionPill precedent).
- Store `count` = `items.length` (payload groups, raw — matches all three prior kinds); skipping is render-only. Hydration effect keyed on `items` and covers skipped groups' valid ids too (the 16.2 pinned behavior — mirror the pin).
- Wiring `groups` removes the drop concept: socket gains `onGroups`, the `case 'groups': return` drop pin is deleted (default `never` arm remains the only non-delivering path), and every "one kind still dropped" prose site (socket.ts, agentView.ts, App.tsx, agentView.test.ts) is rewritten, not trimmed; App's render ternary becomes total (trailing `null` replaced by the `groups` arm).
- After UI changes: rebuild SPA into `src/companion/app/static/` AND rerun `scripts.build_plugin`; commit both mirrors.

**Block If:** the change appears to require editing `src/companion/contracts.py`, `src/companion/client.py`, or any backend route (red flag against the epic's "no contract change" premise); or the shared-path extension cannot keep an existing suggestions/swaps/tier-list test green without rewording a pinned message; or the guards cannot pass without weakening a pin other than those listed in Tasks; or the DESIGN.md amendment turns out to conflict with an existing artefact-gated test.

**Never:** no generic `companion_display`; no per-session server state; no card-ID validation at ingest or in the tool; no new design primitive or token (pin stays 70); no local type named `GroupItem`/`GroupsEvent`/`GroupsPayload` outside `ui/src/api/` (wire-contract guard — use `PushedGroup`/`UntrustedGroup` aliased from the store union arm); no new empty-push sentence — reuse `emptyPushLine` verbatim (fourth ledger data point recorded in frontmatter `deferred`, not repaired here); no authored words in the view (title/rationale/numeral are wire data; no "cards" label, no aria copy — COPY_MODULES untouched); no `font-size`/`font-weight` longhands (the `--type-*` roles cover heading/numeric/body — the stylelint overrides pin stays 3); no re-sorting/deduping/merging groups; no cross-container reach into `QuantityBadge.css` or `.card-tile-quantity`; no hand-edits under `plugin/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy push | valid `GroupsPayload`, app open, ≥1 client | `status="displayed"`, `clients=N`, `items_pushed=len(items)` (groups); Glass groups view opens/replaces in place; "Card groups" pill activates | No error |
| App closed | no discovery file | `status="app_not_running"`, text result, never raises | Degradation ladder |
| No listeners | app up, 0 WS clients | `status="no_clients_connected"`, push not re-sent | No error |
| Over-cap payload | >12 groups / title >80 / rationale >600 / >60 ids | Pydantic rejects at tool boundary; endpoint 413 → `payload_rejected` if it gets that far | Never truncated |
| Field-legal but >64 KB envelope | 12 maximal groups (~104 KB) | Endpoint 413 → `payload_rejected`; docstring warns | Never truncated |
| Empty payload | `items=[]` | Pushed anyway; view renders shared `emptyPushLine('groups')`, count 0 | No error |
| Empty group | group with `card_ids=[]` (or absent) | Group skipped entirely — title and rationale included — not an empty shell; still counts toward store `count` | Render-only skip |
| Malformed group | item missing/blank `title` or `rationale` | That group degrades (skipped); other groups render | Per-group degradation |
| Card outside active deck | valid UUID, not in deck | Tile renders normally, **no quantity badge** | No error |
| Card in deck, quantity 1 | UUID in active deck ×1 | Tile renders with `×1` badge | No error |
| No active deck loaded | deck store not on `'deck'` arm | No tile shows a badge; view otherwise unaffected | Selector returns null |
| Unknown card id | UUID not in DB | Thumbnail degrades to unknown-card placeholder; group text still renders | Per-card degradation |
| Auth rejected once | 403 on push | Leaf client re-reads discovery, retries exactly once (existing — do not re-prove) | Existing |

</intent-contract>

## Code Map

**Design artefacts (amend first):**
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md` — group-section prose :592 (heading title, numeric count in text-tertiary, body rationale "capped at ~900px measure", wrapped tile row); **no `components.group-section` frontmatter block exists** — add one (`divider: 1px solid {colors.border-hairline}`, `measure: 900px`) with an AMENDED comment; precedent :337-360 (c6-7 suggestion-row: "the treatment is ruled and written HERE FIRST"). Quantity-badge appearance :576; tier-row comparison :331-338/:590; mock composition list :560 includes "Group section".
- `EXPERIENCE.md` (same folder) :94 — the badge rule ("no quantity badge unless the card is in the active deck… ×0 would be a lie"; "Empty groups are skipped"); :71 empty-push cell (byte-gated); :73 already says "the four pills" — nav needs no amendment.
- Mock `imports/claude-design/Planeswalker Companion.dc.html:151-176` — composition reference only; its 14px gap and 164px tile width are UX-DR5 drift, not copied.

**Backend (`src/mcp_server/`):**
- `tools/companion.py` — the fourth mirror. Contracts imports :41-49 (insert `GroupsEvent, GroupsPayload` after `ActiveDeckRequest` :42, alphabetical). `_push_messages` :258-301 (docstring :278 noun list gains "groups"). `_execute_push` :505-551 — extend TypeVar constraint tuple :505 with `ShowGroupsResult` and event union :506 with `| GroupsEvent`; "three distinct classes" prose :461-462/:513-525 becomes four. Model `ShowTierListResult` :454-493 + `_TIER_LIST_PUSH_MESSAGES` :496 + `show_tier_list` :554-601 (pluralizer :594, `shown=f"{items_pushed} {tiers}"` :600). Append `ShowGroupsResult`, `_GROUPS_PUSH_MESSAGES`, `show_groups` after :601 (executor stays above all callers); `shown=f"{items_pushed} {groups}"`, `groups = "group" if items_pushed == 1 else "groups"`.
- `server.py` — payload import :49 (`GroupsPayload` first, alphabetical); result imports :60-65 (insert `ShowGroupsResult` after `SetActiveDeckResult` :61); helper imports :66-69 (insert `show_groups` alias after :66). Registration blocks: suggestions :519-565, swaps :567-613, tier_list :615-663; **new `companion_show_groups` block at :664** (before `analyze_mana_curve` :665), docstring mirroring :617-662's six sections (summary; when-to-use + "send here **and** give your normal answer"; UUIDs + empty-list legitimacy + cards-outside-deck legality; app-running + statelessness; Args with every cap incl. item-title vs payload-title disambiguation and the 64 KB envelope caveat; Returns with the five statuses + `items_pushed` counts **groups** never cards).
- `src/companion/contracts.py` — READ-ONLY, already complete: `GroupItem` :784-827 (`title` ≤80 non-blank :823-825, `rationale` ≤600 non-blank :826, `card_ids` ≤60 each ≤128 :827; name-collision note :787-789); `GroupsPayload` :906-924 (`title?` ≤80 :923, `items` ≤12 :924); `GroupsEvent` :1159-1202; `EventKind` has `groups` :558; `AgentEvent` union :1287; `DEFAULT_TITLE_BY_KIND` `"groups": "Groups"` :1320; envelope-cap note :479-491 (maximal groups envelope 104,067 B > 65,536 B).
- `src/companion/client.py` — READ-ONLY. `push_event` :528 accepts `GroupsEvent` via `AgentEvent`; `PushOutcomeToken` :144.

**Frontend (`ui/`):**
- `src/api/schema.ts` — add `GroupsEvent = Extract<AgentEvent, {kind:'groups'}>` after :345 and `GroupItem = Schemas['GroupItem']` after :439, following the TierListEvent :329-345 / TierItem :423-439 docstring shapes. Generated types exist (`types.d.ts` GroupItem :918-925 — `title`/`rationale` REQUIRED, `card_ids?` optional, the inverse of TierItem's optionality; GroupsEvent :950-964) — no regen.
- `src/state/deck.ts` — NEW selector `useDeckCardQuantity(cardId): number | null` beside `useDeckUpdating` :850 (`'deck'` arm holds `detail.cards: DeckCardSummary[]` keyed by `card_id` with `quantity`, :147; primitive return keeps per-tile subscription discipline per agentView.ts :599-620).
- `src/state/agentView.ts` — imports :67-75 add `GroupItem, GroupsEvent`; `AGENT_VIEW_LABELS` already has `groups: 'Card groups'` :110. Union `groups` arm :213-217 currently `readonly never[]` → `readonly GroupItem[]`; union docstring :176-181 ("socket still drops its frames") rewritten. Mirror `tierListViewOf` :480-513 / `openTierListPush` :543-552 (title = trimmed `payload.title` else `AGENT_VIEW_LABELS.groups`; `count: items.length`; total against absent payload).
- `src/state/socket.ts` — imports :80-86 add `GroupsEvent`; add `onGroups` handler type after `onTierList` :252-262; destructure :356; dispatch: **delete the drop pin :490-497 entirely**, add `case 'groups': onGroups(event); return` beside tier_list :484-489; `default: never` :498-505 stays. Rewrite the "one remaining kind" prose :230-238 and :256-260.
- `src/state/connection.ts` — import :83 add `openGroupsPush`; handler table add `onGroups: openGroupsPush` after :164.
- `src/App.tsx` — import :10-12 add `GroupsView`; render switch :776-782: trailing `: null` :782 replaced by the `groups` arm — the ternary becomes total; rewrite the comment :762-775 (esp. :770-773 "stays UNREACHABLE from the wire").
- `src/containers/GroupsView/` — NEW (`GroupsView.tsx`, `.css`, `.test.tsx`; **no copy.ts** — reuse `emptyPushLine` from `../SuggestionsView/copy` :75-76, its fourth reader). Model: `TierListView.tsx` (props :61-71; store-derived alias `PushedGroup` :73-78 shape; `UntrustedGroup` mapped type :80-81; field ladder :99-142 — here `titleOf`/`rationaleOf` non-blank-required, `cardIdsOf` per-id filter; module-local `GroupTile` per `TierTile` :154-249 with per-card hooks, stale-release :186-191, five inspection verbs :201-205, hidden accessible name :210-212, placeholder ladder :217-246 — plus the quantity badge from `useDeckCardQuantity`; hydration effect :307-311; gate-and-skip flatMap :319-326; `<ul>`/`<li>` :328-339; empty state :342-347). No letter-ramp analogue — do not cargo-cult the `Assert` exhaustiveness idiom :93-97. CSS: section gaps/dividers off the token scale; two cited px literals only (`900px` → DESIGN.md `components.group-section` measure; `1px` divider → same block); tile geometry lh-derived (tier-tile route); badge chrome mirrors `QuantityBadge.css` token spends under `.group-tile-quantity` (no `--radius-pill` concern — GroupsView.css is not CARD_SHAPED-listed; verify).
- Flex-wrap precedents: AgentView.css:106, ColourDistribution.css:173. Badge gotcha: CardTile gates `> 1` (CardTile.tsx:204,:300) — GroupsView's ≥1 gate is deliberate and documented in Boundaries.

**Guard tests that must move (complete list):**
- `tests/integration/test_build_plugin.py` :269-293 tool-name set (+`companion_show_groups` after :283); GroupItem schema-publication twin of :350-369 (assert `"GroupItem" in schema`, `"maxItems"`, `"maxLength"`, `"Scryfall" in description`; per-field loop should lean on `rationale`/`card_ids` — `title` exists at both levels so it discriminates nothing).
- `tests/integration/mcp_server/test_companion_tool.py` — imports :40-49/:53-60; `_groups_payload` fixture mirroring `_tier_payload` :121-148 (≥2 card ids per group); mirror the four tier-list classes :921-1096 (delegation incl. no-injected-title, five outcomes, empty payload pushed, **counts groups not cards** twin of :1047, compact result); extend `TestEveryPushToolSpeaksItsOwnNoun` at :1114-1116 (`_GROUPS_PUSH_MESSAGES == _push_messages("groups")`), :1147-1151 (cases tuple), :1162-1166 (("1 group","2 groups")); byte-pin test :1118-1143 stays suggestions-only by design. Module docstring :1-8 "Two tools, two shapes" — fix in passing.
- `tests/integration/mcp_server/test_companion_degradation.py` — groups closed-app-by-name case inserted at :235 (mirror tier_list :199-234; one-group payload, assert `items_pushed == 1` counts the group not its cards); module docstring :11 "Both companion tools" — fix in passing.
- `ui/src/state/socket.test.ts` — harness :96-122 gains `groupsPushes` (+ stub-handler sites :288, :316, :838); delivered test in the tier shape :747-774 with non-vacuity control; **drop loop :784-800 becomes vacuous (`[]`) — delete it** (unknown-kind/default-arm coverage lives elsewhere; do not iterate an empty list).
- `ui/src/App.test.tsx` — drop test :2588-2606 vacuous — delete; disabled-pill pin :5960 and all-quiet loop :5940-5944 stay as non-vacuity controls but flip where they assert `groups` stays disabled after a groups push; wire-driven end-to-end describe cloned from 16.2's :5575-5677 (push through fake socket → dialog title, section anatomy incl. numeral count + badge presence/absence, pill activation, empty-push sibling).
- `ui/src/state/agentView.test.ts` — clone tier coverage :367-450 for groups (`groupsViewOf` title fallback, retention, open); prose :522 updated; :582/:714 stay valid; `AGENT_VIEW_LABELS` key-order pin :549 unchanged.
- `ui/tests/shell.test.ts` — CONTAINERS entry (sorted imports; TierListView entry :1685-1700 is the shape, plus `'../../state/deck'` — allowed root per :2109-2111/:2144-2145) + length pin :2276 **38→39**.
- `ui/src/state/deck.test.ts` (or the deck store's test home) — `useDeckCardQuantity` coverage: in-deck quantity, not-in-deck null, non-`'deck'` state null.
- `ui/tests/keyboard-floor.test.ts` WELL_CLEAR :529-538 gains `'group-tile'` (derived geometry, tier-tile precedent :535).
- `ui/tests/token-usage.test.ts` — token pin :1177 (70) must NOT move; INVENTORY_CLAIMS :2781-2801 gains `'.group-tile-image :: opacity': 'Image fade-in'` beside :2792.
- Pins that must NOT move: `ui/tests/lint-gates.test.ts` overrides :826 stays 3 (no font longhand); `ui/tests/copy-rules.test.ts` COPY_MODULES untouched (no authored word); `ui/tests/event-union-contract.test.ts` :92/:102 and `ui/tests/agent-views-nav-copy.test.ts` :170/:185 already carry groups — no change.

**Docs/mirrors:** `README.md` :28 catalog cell + :253-254 prose; `CHANGELOG.md` bullet; `plugin/server/` mirrors rebuilt byte-identical via `scripts.build_plugin`.

## Tasks & Acceptance

**Execution:**
1. `DESIGN.md` (ux-designs folder) — add the `group-section:` frontmatter block (`divider: 1px solid {colors.border-hairline}`, `measure: 900px`) with a c6-7-style AMENDED comment — the artefact moves first so the CSS has something to cite.
2. `src/mcp_server/tools/companion.py` — `ShowGroupsResult` + `_GROUPS_PUSH_MESSAGES` + `show_groups` on the shared path; extend `_execute_push`'s TypeVar tuple/event union and the `_push_messages` docstring noun list; prior three kinds byte-identical; `items_pushed` = group count.
3. `src/mcp_server/server.py` — register `companion_show_groups` with the full agent-facing docstring (the docstring is the LLM tool description).
4. `tests/integration/mcp_server/test_companion_tool.py` — mirrored groups push classes incl. counts-groups-not-cards + `TestEveryPushToolSpeaksItsOwnNoun` fourth-noun extension; `tests/integration/mcp_server/test_companion_degradation.py` — closed-app case by tool name over a real MCP session; both stale module docstrings fixed in passing.
5. `tests/integration/test_build_plugin.py` — tool-name set + GroupItem payload-shape publication test — hard gates.
6. `ui/src/api/schema.ts` + `ui/src/state/deck.ts` + `ui/src/state/agentView.ts` + `ui/src/state/socket.ts` + `ui/src/state/connection.ts` + `ui/src/App.tsx` — wire the `groups` kind end-to-end (aliases, `useDeckCardQuantity`, union widening, `groupsViewOf`/`openGroupsPush`, dispatch arm + **drop-pin deletion** + prose rewrites, `onGroups`, total render ternary) — tightly coupled, one coherent change.
7. `ui/src/containers/GroupsView/` — build the view per DESIGN.md group-section: heading title + bare numeral count, ≤900px rationale, hairline dividers, wrapping tile strip with placeholder ladder, inspection verbs, and the in-deck-only quantity badge; payload order; empty/malformed groups skipped render-only; shared empty-push line.
8. `ui/src/containers/GroupsView/GroupsView.test.tsx` + move the guard pins listed in the Code Map (socket harness/delivered/drop-delete, App tests, CONTAINERS 38→39, agentView tests, deck selector tests, keyboard-floor, token-usage inventory row) — including badge tests: ×1 renders for an in-deck singleton, no badge off-deck, no badge with no deck loaded, and hydration-covers-skipped-groups.
9. Rebuild: `cd ui && npm run build`, then `uv run python -m scripts.build_plugin`; update `README.md` + `CHANGELOG.md` — commit committed-artifact mirrors.

**Acceptance Criteria:**
- Given the app closed, when the agent calls `companion_show_groups`, then the tool returns a text result containing `app_not_running` and does not raise (proven over a real in-memory MCP session).
- Given a connected Glass and a valid groups payload, when the tool is called, then the groups view opens (or replaces in place), the "Card groups" pill activates with unread behavior, and each non-empty group renders title, numeral count, rationale, and thumbnails in payload order with empty groups skipped.
- Given a group tile whose card the active deck runs at quantity 1, when the strip renders, then the tile carries `×1`; given a card the deck does not run, the tile carries no badge.
- Given the shared-path extension, when the full suite runs, then every pre-existing suggestions/swaps/tier-list push test passes unmodified.
- Given `items=[]`, when pushed, then `status="displayed"` and the view shows the shared empty-push line for `groups`.
- Given all four kinds shipped, when the full verification suite runs, then the socket module contains no drop arm, the tool-name set-equality test, CONTAINERS pin (39), token pin (70, unmoved), stylelint overrides pin (3, unmoved), and both committed-artifact drift checks all pass.

## Spec Change Log

## Review Triage Log

### 2026-08-21 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 0, medium 1, low 6)
- defer: 0
- reject: 9: (high 0, medium 2, low 7)
- addressed_findings:
  - `[medium]` `[patch]` The quantity badge's reactivity to deck changes was untested — every badge test settled the deck before render, so a non-reactive `getState()`-at-mount reimplementation passed the whole suite while freezing badges at mount-time (breaking the live loop: agent edits deck while the groups view is open). Fixed: test renders with no deck, asserts no badge, then `settleDeck` post-mount and asserts `×3` appears — pinning both the subscription and the null→number transition.
  - `[low]` `[patch]` `cardIdsOf` passed empty/whitespace-only ids: they counted in the numeral, rendered a permanently-dead placeholder, and a whitespace id committed a real `/api/card-image/%20` request. Fixed: filter to trimmed-non-empty strings; the dead `cardId === ''` guard in `GroupTile` removed with an explanatory comment; `['', '  ', 'c-real']` → one tile, numeral 1, pinned.
  - `[low]` `[patch]` Group-level `title`/`rationale` rendered untrimmed while the payload-level title is trimmed. Fixed: `titleOf`/`rationaleOf` trim, symmetry noted in comments, whitespace-padding test added.
  - `[low]` `[patch]` `AgentViewsNav.tsx` still said "the socket still drops `swaps`/`tier_list`/`groups`… exactly one pill can activate until Epic 9 ships" — every claim false after 16.3. Rewritten truthfully (all four kinds delivered; quiet = "no push this session" per UX-DR33).
  - `[low]` `[patch]` CHANGELOG claimed the group title "renders as a heading" but the markup is spans (heading *type*, per DESIGN.md). Wording aligned; markup untouched.
  - `[low]` `[patch]` The `${cardId}:${index}` duplicate-tolerance key comment was untested. Fixed: `['c-dup','c-dup']` renders two tiles, numeral 2.
  - `[low]` `[patch]` The deleted App drop test implicitly pinned that an agent-view push leaves deck endpoints quiet. The 16.3 end-to-end describe now asserts `/api/active-deck` and deck-detail counts are unchanged after the push.

## Design Notes

- Badge-gate ruling: EXPERIENCE.md:94 defines the badge here as "copies in this deck" with suppression only for not-in-deck; the epic restates it. CardTile's `> 1` gate lives in a context where every card is in the deck (×1 is noise); in a group, in-deck-ness is the signal, so ×1 renders. Documented as deliberate divergence at the selector call site.
- Count ruling: DESIGN.md:592 specifies "card count in `{typography.numeric}` `{colors.text-tertiary}`" — a numeral, no authored noun (the mock's "N cards" has no artefact copy source; authored words trigger COPY_MODULES, aim: none). Count = the valid-id list length the strip renders, so it never counts tiles that don't appear.
- Group degrade ladder inverts TierItem's optionality: `title` and `rationale` both required non-blank (blank → group malformed → skipped); `card_ids` optional (absent/empty → legal, group skipped per artefact). Unknown-vs-off-deck are two different predicates on the same tile: unknown id → placeholder (hydration question); off-deck → no badge (deck-store question).
- The mock (`Planeswalker Companion.dc.html:151-176`) is composition reference only; its 14px gap and 164px tile width are off-scale UX-DR5 drift, deliberately not copied — same call as 16.2's tier-tile geometry, carried as a manual-visual-check residual.
- Wiring the last kind deletes machinery rather than extending it: the socket drop pin, both drop-loop tests, and five "one kind still dropped" prose sites all go. Watch for any other comment grep-able by "groups" that asserts undelivered frames.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean
- `uv run mypy src/` -- expected: clean (strict)
- `uv run pytest` -- expected: all pass, pre-existing push-tool tests unmodified
- `cd ui && npm run lint && npm run format:check && npm run typecheck` -- expected: clean
- `cd ui && npm test` -- expected: all pass (shell/tokens/wire-contract/copy/socket/keyboard/lint gates included)
- `cd ui && npm run build && cd .. && uv run python -m scripts.build_plugin` -- expected: succeeds; `git status` shows only intended files; plugin tree byte-matches

## Auto Run Result

Status: done

**Summary:** Story 16.3 shipped — the epic's last push kind. DESIGN.md was amended first (new `components.group-section` frontmatter block: `divider: 1px solid {colors.border-hairline}`, `measure: 900px`, with a c6-7-style AMENDED comment) so the view's two px spends have citations. `companion_show_groups(payload)` was added as the fourth tool on the 16.2-consolidated shared push path (async, never raises, closed five-token outcome + client count, compact result, `items_pushed` counts groups never cards, full agent-facing docstring incl. item-title vs payload-title disambiguation and the 64 KB envelope caveat), together with the GroupsView container (heading-type title + bare numeral count = the valid-id list the strip renders, 900px-measure rationale, hairline dividers, wrapping lh-derived tiles with the full placeholder ladder and inspection contract, payload order, empty/malformed groups skipped render-only, shared empty-push line) and the in-deck-only quantity badge fed by a new `useDeckCardQuantity` primitive selector (`×N` iff the active deck runs the card at ≥1 — the deliberate, documented divergence from CardTile's `> 1` gate; static, no flash). Wiring the last kind deleted the socket drop pin entirely: the dispatch and the App render ternary are now total over all four kinds, and every "one kind still dropped" prose site was rewritten. No changes to `contracts.py`, `client.py`, or any backend route — the epic's "no contract change" premise held to the end.

**Files changed:**
- `_bmad-output/planning-artifacts/ux-designs/.../DESIGN.md` — `group-section` component block added (artefact-first, c6-7 precedent).
- `src/mcp_server/tools/companion.py` — `ShowGroupsResult`, `_GROUPS_PUSH_MESSAGES`, `show_groups`; `_execute_push` TypeVar/event-union extended; noun list updated.
- `src/mcp_server/server.py` — registers `companion_show_groups` with the full agent-facing docstring.
- `ui/src/containers/GroupsView/{GroupsView.tsx,GroupsView.css,GroupsView.test.tsx}` — new container + 40 tests (no copy.ts; shared `emptyPushLine`).
- `ui/src/state/deck.ts` — new `useDeckCardQuantity(cardId)` primitive selector (sums across boards; tests pin it).
- `ui/src/api/schema.ts`, `ui/src/state/{agentView.ts,socket.ts,connection.ts}`, `ui/src/App.tsx` — `groups` wired end-to-end; drop pin deleted; render switch total.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx` — stale "socket still drops" prose rewritten (review patch).
- Tests/guards moved: `tests/integration/test_build_plugin.py` (tool-name set + GroupItem schema publication), `test_companion_tool.py` (four mirrored groups classes + fourth-noun extension of `TestEveryPushToolSpeaksItsOwnNoun`), `test_companion_degradation.py` (closed-app by name; stale docstrings fixed), `ui/src/App.test.tsx` (drop test deleted; wire-driven 16.3 end-to-end describe incl. deck-endpoints-quiet assertion), `ui/src/state/socket.test.ts` (drop loop deleted, delivered test + `groupsPushes` harness field), `ui/src/state/agentView.test.ts`, `ui/src/state/deck.test.ts`, `ui/tests/{shell,keyboard-floor,token-usage}.test.ts` (CONTAINERS 38→39, WELL_CLEAR `group-tile`, image-fade inventory row).
- Docs/artifacts: `README.md` + `CHANGELOG.md`; committed SPA bundle in `src/companion/app/static/` and the `plugin/` mirror rebuilt (byte-matching).

**Review findings:** 7 patches applied (0 high, 1 medium, 6 low — see Review Triage Log), 0 deferred from review (the empty-push copy-grammar ledger item in frontmatter `deferred` was recorded at planning, now with four data points), 9 rejected.

**Follow-up review recommendation:** true — patched counts: high 0, medium 1, low 6; score 3×1 + 1×6 = 9, which meets the ≥5 threshold.

**Verification:** ruff check + format clean; mypy src/ clean (strict, 94 files); pytest 3320 passed / 1 skipped; ui eslint/stylelint, prettier, tsc clean; vitest 2447 passed (83 files); `npm run build` + `scripts.build_plugin` green with mirrors byte-matching and only intended files in `git status`. Matrix audit: every I/O row covered by a test that ran and passed (over-cap and 64 KB rows via pre-existing contract/endpoint cap tests + the five-outcome `payload_rejected` mapping; auth-retry via pre-existing leaf-client coverage per the matrix's own "do not re-prove").

**Residual risks:** the empty-push line renders "an empty groups." (grammatically wrong; fourth ledger data point, carried in frontmatter `deferred` with the EXPERIENCE.md-first recommendation — after four kinds, the item now has no further stories to accumulate in and deserves an owner); group-tile geometry is lh-derived with no DESIGN.md pixel authority beyond the divider/measure — flag for manual visual check, same as 16.1/16.2 tiles; `useDeckCardQuantity` does an O(deck-size) scan per mounted tile on each deck-store write (bounded ≈720 tiles × ~100 rows, judged tolerable; a memoised map is the escape hatch if it ever isn't); the group title/count/rationale are visually heading-typed but not semantic `<h*>` elements (consistent with all sibling views — a future a11y pass could revisit the whole family together); `sprint-status.yaml` still lists 16-3 as `backlog` — the caller's orchestration file, updated by Brad's sprint tooling, not by this run.
