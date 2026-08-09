---
title: 'R3 — derived class→token source guard for status tones'
type: 'chore'
created: '2026-08-09'
status: 'cancelled'
review_loop_iteration: 1
baseline_commit: '0492f04'
branch: 'chore/c6-prep-r3-class-token-guard'
context:
  - '{project-root}/ui/tests/token-usage.test.ts'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** jsdom evaluates no stylesheet, so a component test that asserts `toHaveClass('badge-positive')`
proves the class is *emitted* and nothing about what it *paints*. Probe P15 (c5-7) pointed
`.connection-pill-dot.is-down` at `--caution` and all 1,866 frontend tests stayed green. The pill got a
hand-written guard; **the identical hole is open on Badge and StatChip today** — `Badge.test.tsx:31` and
`StatChip.test.tsx:45` both stop at the class — and Epic 6's view stories will add more surfaces of exactly
this shape.

**Approach:** One **derived** source-reading guard: any class whose name ends in a status tone must paint
from that tone's token family and from no other. Derived, not tabulated — it discovers the classes from the
shipped stylesheets and the families from `tokens.css`, so a new `-{tone}` class is covered with no edit.
Epic C5 retrospective action item **R3**.

## Boundaries & Constraints

**Always:**
- The tone vocabulary is `accent`, `positive`, `negative`, `caution` — the four tones that **name a token**.
  `neutral` is a Badge tone but names no token; it is out of the vocabulary by definition, not by exception.
- Read a class's spends across **all** its blocks (`.badge-positive` and `.badge-positive::before` are
  separate blocks and only their union is the truth).
- Derive each tone's token family from `tokens.css` declarations (`--accent`, `--accent-bright`,
  `--accent-dim`, `--accent-glow` are one family). Never hand-type the family list.
- Carry a **non-vacuity anchor**: assert the real tree yields a known count of tone classes. A regex that
  silently matches nothing must fail, not pass.
- Prove the guard **firing and not firing**, the standing pairing agreement — a fixture that swaps a tone's
  token is caught, and `clean.css` is not.

**Ask First:**
- The finder flagging a **legitimate** shipped rule — HALT and report. Do not add an exemption to make it
  green, and do not repair the stylesheet to fit the guard; a false positive means the rule is wrong.

**Never:**
- Do not generalise `is-live` / `is-reconnecting` / `is-down` repo-wide. Ruled out: `is-live` means
  `--positive` on the pill and `--accent` on the deck row, so a repo-wide rule needs a per-component table —
  the hand-typed list this guard exists to avoid, and a false-positive generator besides.
- Do not touch the existing per-component guards. P15's dot binding (`shell.test.ts:2214`), the deck-name
  uppercase split, and ManaPip's 21-class gate all stay — a passing guard is not deleted for being narrower.
- Do not build anything for the deck-row tint (`--accent-glow`, not a status token) or for ManaPip (already
  gated by `token-usage.test.ts:1403` and the `--mana-*` file/fill/markup rules).
- No production CSS or component changes. This is a test-only story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Shipped tree | The 6 tone classes as committed | Finder returns `[]`; guard green | N/A |
| The P15 failure, ported | `.badge-positive` painted from `--negative` | Flagged: class, file, tone expected, token found | Message names the swap, not "a token is wrong" |
| Accent's multi-token family | `.badge-accent` spends `--accent` **and** `--accent-bright` | Clean — same family | N/A |
| Silent no-op | A class spends no `var()` at all | Flagged — a tone class that paints nothing is the mistyped-token case | N/A |
| Vacuity | Selector regex matches nothing | Anchor assertion fails on the count | Guard cannot pass by reading nothing |
| Out of vocabulary | `.badge-neutral::before` → `--surface-overlay` | Ignored; `neutral` names no token | N/A |

</frozen-after-approval>

## Code Map

- `ui/tests/token-usage.test.ts` -- the guard's home; already the cross-file token resolver. Reuse
  `sourceOf` (:57), `blocksIn` (:88 → `{file, selector, body}`, comments stripped), `shippedBlocks` (:1089),
  `fixture` (:38); follow `findAccentDimInOverlayFile` for finder shape and its three-way proof.
- `ui/tests/fixtures/css/token-usage-violation.css` -- existing multi-rule violation fixture; put the tone
  swap here. `clean.css` is the not-firing half.
- `ui/src/styles/tokens.css:108-123` -- the families: accent has 4 members, positive/negative/caution 1 each.
- `ui/src/components/Badge/Badge.css:120-160` -- 4 tone classes × 2 blocks; `.badge-accent` is the
  multi-token case. `ui/src/components/StatChip/StatChip.css:97-103` -- the unguarded pair.

## Tasks & Acceptance

**Execution:**

- [x] `ui/tests/token-usage.test.ts` -- derive `STATUS_TONE_FAMILIES` from `tokens.css`: for each of the four
      tones, the set of declared custom properties named `--{tone}` or `--{tone}-*` -- hand-typing the family
      would re-break on the next token added to the accent ramp.
- [x] `ui/tests/token-usage.test.ts` -- add `findToneClassTokenMismatches(blocks)`: group blocks by the tone
      class in their selector (`\.[a-z][a-z-]*-(accent|positive|negative|caution)\b`), union each class's
      `var(--…)` spends, and flag any class that spends a token from another tone's family or spends none.
- [x] `ui/tests/token-usage.test.ts` -- add the guard `it()` over `shippedBlocks`, plus the non-vacuity
      anchor asserting the real tree's tone-class count and naming the six classes -- a finder that matched
      nothing would otherwise be indistinguishable from a clean tree.
- [x] `ui/tests/fixtures/css/token-usage-violation.css` -- add a `.badge-positive` block painted from
      `var(--negative)` -- P15's exact failure, in the file the firing half already reads.
- [x] `ui/tests/token-usage.test.ts` -- add the firing proof (fixture caught, and its message names the
      class and both tones) and the not-firing proof (`clean.css` returns `[]`).

**Acceptance Criteria:**

- Given the tree as committed, when the guard runs, then it returns no violations **and** the anchor
  confirms it examined the expected tone classes across Badge and StatChip.
- Given `.badge-positive` is repointed at `var(--negative)` in the shipped stylesheet, when the frontend
  suite runs, then it goes red — the regression that 1,868 green tests cannot currently see.
- Given `.badge-accent` spending both `--accent` and `--accent-bright`, when the guard runs, then it is
  clean, because both belong to the accent family derived from `tokens.css`.
- Given a new component ships `.foo-caution` painted from `--caution`, when the guard runs, then it is
  covered with no edit to the guard; painted from `--negative`, it is flagged.
- Given the guard is added, when the full frontend suite runs, then every pre-existing test still passes and
  no per-component guard was deleted.

**AC verification at end of implementation** — every AC verified, including the firing proof, which was
hand-run because R5's harness does not exist:

| AC | Status | Evidence |
|----|--------|----------|
| Clean tree + anchor confirms what it examined | **Verified** | `findToneClassTokenMismatches(shippedBlocks)` → `[]`; the anchor names all six classes (4 Badge + 2 StatChip) and would fail on a silent empty scan |
| Swapped `.badge-positive` reddens the suite | **VERIFIED BY A REAL PLANT** | Repointed `.badge-positive` to `var(--negative)` in the shipped `Badge.css`. Result: **1 failed, 1,872 passed** — the ONLY failure was this guard. That is a direct measurement of P15's thesis: the swap is invisible to every other test in the project. Message named the file, the class and both tones. Reverted via `git checkout --`; tree byte-identical, suite back to 1,873 green |
| `.badge-accent`'s two-token family is clean | **Verified** | Real tree green with `--accent` + `--accent-bright`; the fixture carries the same shape as its silent half; the families test pins accent at 4 members |
| A new `-{tone}` class is covered with no guard edit | **Verified** | The fixture's `.badge-positive` is a class the guard never had hard-coded — it was discovered from the blocks it was handed |
| No pre-existing test regressed, no guard deleted | **Verified** | 1,868 → 1,873 (＋5, all new). `shell.test.ts` P15 guard, deck-name split and ManaPip gate all untouched |

## Spec Change Log

## Design Notes

**Why name-identity and not the state modifiers.** The four surfaces R3 names are not one shape. Badge and
StatChip bind by *name* (`-positive` → `--positive`), which a machine can derive. The pill binds by
*semantics* (UX-DR29: live→positive, reconnecting→caution, down→negative), which it cannot — `.deck-row.is-live`
paints `--accent-glow` because "live" there means *active deck*, not *healthy*. A repo-wide `is-live` rule
would flag that correct rule, and this repo has already ruled that "a false positive c5-7 has to fight is the
worse outcome". So: derive what is derivable, leave P15's hand-written guard owning what is not.

## Verification

**Commands:**
- `cd ui && npx vitest run tests/token-usage.test.ts` -- expected: all green, including the new anchor.
- `cd ui && npm test` -- expected: 69 files, 1868 + new tests, no pre-existing test regressed.
- `cd ui && npm run lint && npm run format:check && npm run typecheck` -- expected: clean.

**Manual checks (if no CLI):**
- Hand-run firing proof (R5's harness does not exist yet, so this is manual as c5-7's fifteen were): repoint
  `.badge-positive` to `var(--negative)` in the shipped CSS, confirm the suite goes RED naming that class,
  then revert and confirm green. Record both outcomes.
