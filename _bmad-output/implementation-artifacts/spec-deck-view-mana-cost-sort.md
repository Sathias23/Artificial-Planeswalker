---
title: 'Sort deck-view cards by ascending mana value within each type group'
type: 'feature'
created: '2026-08-27'
status: 'done'
review_loop_iteration: 0
baseline_commit: '22aa78d14b8ec6b51d73feff7ac6d8eabb59e775'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Cards in the companion's main card grid and the right-hand deck-list panel render in raw payload order, which the wire itself documents as "not meaningful" — the deck view looks unsorted and illogical.

**Approach:** Impose Arena-style order at the single derivation point (`boardsOf` in `ui/src/state/deckGroups.ts`): within each board/group, sort ascending by mana value (`card.cmc`), ties broken alphabetically by `card.name`. Both views, and the cold-open selection, inherit it with no component changes.

## Boundaries & Constraints

**Always:**
- The sort lives ONLY in `boardsOf` (deckGroups.ts). CardGrid, DeckList, and `coldOpenTargetOf` keep reading the derived order verbatim — that "one derivation, no consumer re-sorts" invariant is the module's founding rule and must survive.
- Sort mainboard groups, the sideboard, and the commander board with the same comparator (commander is usually 1 card; consistency is free).
- The comparator must be stable and deterministic: ascending `cmc` (a float — 0.5 exists), tie → `name` (use `localeCompare`), and never mutate the input array.
- Conservation identities (quantity sums vs `mainboard_count`/`sideboard_count`) must remain untouched.

**Ask First:**
- Any change to the between-group order (`TYPE_GROUPS`) or to which board a card lands in — out of this spec's scope.

**Never:**
- Do not sort in CardGrid/DeckList/GroupsView components.
- Do not touch `GroupsView`/`TierListView` (agent-pushed views — their payload order is the agent's, deliberately).
- Do not reuse `bucketOf` from `curve.ts` (it clamps at 7+ and folds 0/1 — wrong for ordering).
- Do not change backend/wire order.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Mixed-cmc group | Creatures cmc 4, 1, 2 (payload order) | Rendered 1, 2, 4 in grid and list | N/A |
| Tied cmc | Two cards, same cmc | Alphabetical by name (localeCompare) | N/A |
| Fractional cmc | `Little Girl` cmc 0.5 beside cmc 0 and 1 | Sorts between them (0 < 0.5 < 1) | N/A |
| Lands group | All cmc 0 | Alphabetical | N/A |
| Cold-open target | No commander; first group's cards were payload-ordered | Target = lowest-cmc (then name) card of first populated group | N/A |
| Genuine split card | `cmc` is the combined faces' value | Sorts by that combined value — accepted, same caveat the mana curve documents | N/A |

</frozen-after-approval>

## Code Map

- `ui/src/state/deckGroups.ts` — THE change site. `boardsOf` (:252-273) builds `sideboard`/`commander`/`mainboard`; add an exported comparator (e.g. `byManaValueThenName`) and apply it to each board's card arrays. Amend the `TYPE_GROUPS` docstring paragraph (:78-80) saying c4-5's "first card" rests only on group order.
- `ui/src/api/types.d.ts:569-588` — `CardSummary`: `cmc: number` (non-nullable float), `name: string`. `schema.ts:115-117` explicitly names `deckGroups.ts` as the consumer that must impose order.
- `ui/src/containers/CardGrid/CardGrid.tsx:103-108`, `ui/src/containers/DeckList/DeckList.tsx:240-249` — read-only; their "nothing here sorts" comments stay TRUE. Touch only a sentence that claims payload order specifically.
- `ui/src/state/inspection.ts:341-369` — `coldOpenTargetOf`: no code change; docstring's "there is no sort" narrative should note order now arrives sorted.
- `ui/src/state/deck.ts:512,575` — `boardsOfDeck` runs once at settle time, so the sort is per-fetch, not per-render. No change.
- `ui/src/state/deckGroups.test.ts` — add comparator + within-group order tests; check :363-366 (`['Pym Particles','Reversible Thing']` in `Other`) still holds under fixture cmc/name values.
- `ui/src/containers/DeckList/DeckList.test.tsx:669-692` — probe e DIRECTLY forbids sorted order. Rewrite: distinct cmcs supplied descending, assert ascending render, `not.toEqual` payload order.
- `ui/src/containers/CardGrid/CardGrid.test.tsx` — no within-group order test exists (gap); add one mirroring the DeckList probe.
- `ui/src/App.test.tsx:3767-3795` — Llanowar Elves (cmc 1) vs Grizzly Bears (cmc 2): stays green; verify only.
- Firing proof per project rule: `uv run python -m scripts.vitest_probe_harness --control` (warm), then `--expect-total N --expect-red '<substring>'` with the sort deliberately broken.

## Tasks & Acceptance

**Execution:**
- [x] `ui/src/state/deckGroups.test.ts` — write failing tests first: exported comparator (cmc asc, name tiebreak, 0.5 case, stability/no-mutation) and within-group order for mainboard/sideboard/commander, fixtures supplied in descending cmc; verify/adjust the `Other`-group fixture at :363-366. *(Fixture holds: both `Other` rows are cmc 0 and already alphabetical; a comment now says the order is the comparator's answer.)*
- [x] `ui/src/state/deckGroups.ts` — add exported comparator + apply in `boardsOf` to commander, each mainboard group, and sideboard; amend TYPE_GROUPS docstring.
- [x] `ui/src/containers/DeckList/DeckList.test.tsx` — rewrite probe e (:669-692) to assert ascending-cmc order and forbid payload order.
- [x] `ui/src/containers/CardGrid/CardGrid.test.tsx` — add a within-group order test (fixture in descending cmc).
- [x] `ui/src/state/inspection.ts` — docstring amendment only (order now sorted upstream); inspection tests green in the full run.
- [x] Firing proof — control `vitest: 86 files / 2616 tests, 0 failed, exit 0` (`--expect-total 2616`). Plant 1 (inverted cmc): `vitest: 86 files / 2616 tests, 8 failed, exit 1` — RED in deckGroups.test.ts (×5), CardGrid.test.tsx, DeckList.test.tsx probe e, and App.test.tsx's cold-open fallback. Plant 2 (tiebreak dropped): `vitest: 86 files / 2616 tests, 3 failed, exit 1` — the three tie tests. Restored: `--expect-total 2616 --expect-green` → `vitest: 86 files / 2616 tests, 0 failed, exit 0`.

**Acceptance Criteria:**
- Given a deck whose payload lists a group's cards in descending cmc, when the deck settles, then the card grid tiles and the deck-list rows for that group both show ascending cmc, ties alphabetical.
- Given no commander and a first type group whose cheapest card is not first in the payload, when the deck cold-opens, then the inspected/default card is the cheapest (then alphabetically first) card of that group.
- Given the full suite (`npm test` in `ui/`), typecheck, and lint, when run after the change, then all pass with the DeckList probe-e rewrite asserting the new order.

## Verification

**Commands:**
- `cd ui && npm test` — expected: full vitest suite green.
- `cd ui && npm run typecheck && npm run lint` — expected: clean.
- `uv run python -m scripts.vitest_probe_harness --control` then `... --expect-total N --expect-red '<substring>'` — expected: harness prints a pasteable proof line for the planted violation.

**Manual checks (if no CLI):**
- Open the companion on a real deck: grid and right-hand list show each type group cheapest-first, Arena-like.
