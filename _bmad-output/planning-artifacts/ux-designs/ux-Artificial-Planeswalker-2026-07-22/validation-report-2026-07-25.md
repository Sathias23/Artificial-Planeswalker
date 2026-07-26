# Validation Report — Artificial-Planeswalker Companion (Voltglass revision)

- **DESIGN.md:** `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md`
- **EXPERIENCE.md:** `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md`
- **Run at:** 2026-07-25 (Reviewer Gate; lenses: rubric walker + accessibility)
- **Supersedes:** `validation-report.md`, `validation-report.html`, `review-rubric.md`, `review-accessibility.md` (all 2026-07-22, against the pre-Voltglass spines)

> **Reviewer's note on independence.** This gate was run by the same author who rewrote both spines on 2026-07-25. That is a real weakness of this report and it should be read with that in mind: self-review reliably finds mechanical defects and reliably misses framing errors. The findings below lean heavily on things that can be *computed* — token resolution, contrast arithmetic, name parity, reference integrity — precisely because those don't depend on the author's judgement. The four rulings in EXPERIENCE.md remain the least-tested part of the pair and are **not** validated by this gate; they need Brad.

## Gate status: **CLOSED 2026-07-25** — both spines `status: approved`

All four highs and the four blocking mediums are resolved; see **Gate close** at the foot for what changed and one correction to a finding in this report. H3 is closed as an accepted, recorded deferral rather than a fix. The four EXPERIENCE.md rulings remain author-made and untested by any lens here.

---

## Overall verdict (as run, before close)

**Pass with conditions.** The pair is internally coherent and extractable: all 118 distinct `{path.to.token}` references resolve, both files parse as YAML, all eight canonical sections are present in order in each, and the contrast table in DESIGN.md was recomputed from the hex values rather than copied — it verifies, and it corrects one claim the upstream design system got wrong.

Four highs block a clean close, and they cluster in one place: **the design added surfaces faster than the PRD and the spines added contracts for them.** One IA row cites a tool that does not exist. One FR (double-faced cards) has no design anywhere. And the keyboard floor — the thing the 2026-07-22 gate spent four highs on — is only partly recovered, because the redesign put a 100-tile grid back in the middle of the Tab order.

Seven findings were self-inflicted contradictions introduced by the 07-25 rewrite; **four were closed during this pass** and are recorded below as closed, with what changed.

## Category verdicts

| Category | Verdict | Δ vs 2026-07-22 |
|---|---|---|
| Flow coverage | strong | = (3 flows now, was 2) |
| Token completeness | strong | = |
| Component coverage | **adequate** | ↓ (5 components lack behavioral rows; DFC flip lost entirely) |
| State coverage | strong | ↑ (agent-view interaction states added) |
| Visual reference coverage | **adequate** | ↓ (a mock now exists and neither spine points at it) |
| Bloat & overspecification | adequate | ↓ (frontmatter grew ~50%; several single-use tokens) |
| Inheritance discipline | **adequate** | ↓ (invented tool name; FR-05 citation lost then restored) |
| Shape fit | strong | = |

## Findings

### high (4)

**H1 · [Inheritance] `companion_show_groups` does not exist.** EXPERIENCE.md's IA table reaches the Card-groups view from `companion_show_groups(payload)`. The PRD names four companion tools — `companion_set_active_deck`, `companion_show_suggestions`, `companion_show_swaps`, `companion_show_tier_list` — and this is not among them. The design introduced a fourth agent view with no tool behind it, and the spine invented a plausible name to fill the gap, which is exactly the failure mode the "verbatim names mirror the PRD" discipline exists to catch. *Fix:* either add the tool as a new FR in the PRD addendum (and with it the payload contract, since groups carry a title + rationale paragraph + card list, unlike any existing push), or drop Card groups from the IA until it has one. **Decision required — not closable by editing the spines.**

**H2 · [Component] The DFC flip control has no spec in either spine, and double-faced cards are currently unviewable.** The as-built design has no flip affordance; the 07-25 rewrite recorded this as a residual rather than specifying it, which means a P0-adjacent FR now has zero design surface. A story-dev implementing it must invent the control, its hit target, its interaction with the inspection contract (does flipping change the detail panel's face?), and its persistence across `deck_changed`. This is the same shape as the 07-22 gate's single high (a named surface with no component spec) and should be treated the same way. *Fix:* a design pass producing a paired entry in both spines. **Blocking for any story touching DFCs.**

**H3 · [Accessibility] The Tab order routes every keyboard user through the entire card grid.** Declared order is skip link → header nav → card tiles (visual order) → deck rows → connection pill → footer links. On a 100-card deck that is 100+ stops between the header and *everything* in the right column — the deck list, the connection pill, and the legally-required footer links. Moving the nav ahead of the grid (as the rewrite did) fixes reaching agent views and nothing else. The skip link is the only mitigation and it was, until this pass, unspecified. *Partially closed:* the skip link is now specified in both spines (see C2) and targets the detail panel heading, which lands the user in the right column. **Still open:** one skip link is a single escape hatch for a column containing four panels; the deck list is reachable but the grid remains an unavoidable 100-stop corridor for anyone traversing forward. *Fix:* consider making the grid a single composite Tab stop with arrow-key navigation inside it — explicitly out of MVP scope per Interaction Primitives, which is a defensible deferral but should be a recorded one rather than silent.

**H4 · [Accessibility] The card detail panel was a live region driven by hover.** Semantic structure declared `aria-live="polite"` on the panel while Component Patterns had hover *and focus* updating its target. Sweeping a cursor across a 60-card grid, or arrowing through it, would fire one polite announcement per card — an announcement flood that makes the panel actively hostile to screen-reader users, in a product where that panel is the primary reading surface. **Closed this pass** (see C1).

### medium (9)

**M1 · [Component] Five components carry a visual spec but no behavioral rules.** Panel, Badge, StatChip, Group header, and ManaPip/ManaCost appear in DESIGN.md Components with no row in EXPERIENCE.md Component Patterns. The 07-22 gate's standard was that every named component carries both. These five are genuinely presentational, so the omission is defensible — but it should be stated, not silent, or the next reviewer re-raises it. *Fix:* one line under Component Patterns naming them as presentation-only primitives with no behavior of their own.

**M2 · [Flow / Latency] SC-1's 250 ms budget and the agent view's 480 ms entry animation are not reconciled.** `{components.motion.bloom}` is 480ms and the view enters over it; SC-1 requires "painted panel layout within 250 ms of tool-call completion". The Latency contract defines "rendered" as layout + text + cached-or-placeholder art but never says whether the clock stops at first paint of the animating layer or at animation settle. Under the strict reading the design cannot meet SC-1 at all. *Fix:* one clause — the budget is measured to first paint of the view's laid-out content, and the entry animation runs on top of an already-complete layout.

**M3 · [Visual reference] A mock now exists and neither spine references it.** `imports/claude-design/` holds the as-built screen. EXPERIENCE.md lists it under `sources`; DESIGN.md has **no `sources` frontmatter at all**, and neither file carries a `→ Composition reference:` line on any component. The 07-22 gate recorded this category as "strong (vacuous)" because there were no visual references to orphan; that is no longer true. *Fix:* add `sources` to DESIGN.md, and composition references on the components the mock actually demonstrates.

**M4 · [Accessibility] `{components.card-tile.live-ring}` used `accent-dim`, which the same file bans.** DESIGN.md Colors establishes that `accent-dim` fails the 3:1 non-text floor on `surface-overlay` (2.70:1) and restricts it to well/base/panel. Card tiles appear on `surface-overlay` inside swap rows and tier rows, so the live ring violated the rule three paragraphs after it was written. **Closed this pass** (see C3).

**M5 · [Accessibility] The focus indicator on card tiles sits over arbitrary card art.** Every other focusable element has a known surface behind it, so `focus-ring` at 8.1–10.3:1 is safe. A card tile's ring sits over a painting that may be near-white or near-black, and the 3:1 non-text floor cannot be guaranteed against unknown imagery. Card tiles are the most numerous focusable element in the app. **Closed this pass** (see C4).

**M6 · [Token] `--numeric-features` was referenced in prose but defined nowhere.** DESIGN.md Typography instructed implementers to pair the `font` shorthand with a `--numeric-features` custom property that appeared in no token block — an unresolvable reference in the one place the file calls a rule non-negotiable. **Closed this pass** (see C5).

**M7 · [State] Agent-view behavior during left-column state transitions was unspecified.** What happens to an open Suggestions view when a refetch 404s to No-active-deck, or when the deck refetch completes behind it? **Closed this pass** — two State Patterns rows added, ruling that agent content stays valid (it is about cards, not about deck presence) and that nothing announces from behind a modal.

**M8 · [Inheritance] FR-05 lost its citation.** Removing the view toggle removed the only reference to FR-05 from either spine, leaving the requirement apparently unserved when it is in fact satisfied differently. **Closed this pass** — the Deck list panel row now cites FR-05 and states how.

**M9 · [Inheritance] NFR-08 is never cited by ID.** The footer attribution is described as "a condition of public release" in DESIGN.md and as required in EXPERIENCE.md, but neither cites NFR-08, which the previous draft did. For the one item in this pair that is a legal obligation, the traceable ID is worth keeping. *Fix:* one citation in each file.

### low (9)

- **L1** Flow 3 (Revisiting a push) has no climax beat and no failure path, unlike Flows 1 and 2. What happens when a revisited push references cards the deck no longer contains is stated in Component Patterns but not exercised in the flow. *Fix:* add the failure path, or fold Flow 3 into Flow 1 as a coda.
- **L2** `{components.motion.ease-out}`, `{components.motion.ease-snap}` and the whole `{components.badge}` group are defined and referenced by nothing in `{…}` form — only `ease-glide` is used, and Badge is named in prose only. The 07-22 gate raised the identical finding against `easing-standard`; the rewrite carried the pattern forward rather than fixing it. *Fix:* bind them or drop them.
- **L3** The seven `mana-*` tokens are never referenced in `{colors.mana-…}` form, only as bare prose names. They resolve, but a consumer grepping for `{colors.` misses them.
- **L4** Session history (FR-18) is absent from the IA table entirely. It is honestly recorded under Residuals, but a reader working from the IA table alone won't know the surface was considered and deferred.
- **L5** Several single-use values were tokenized that the 07-22 gate explicitly said should not be (`tier-row.chip-width`, `letter-size`, `letter-weight`, `deck-row.columns`, `color-bar.height`). Mild ceremony; frontmatter grew from 15 to 24 component groups.
- **L6** "Responsive & Platform" remains a dropped default. It was defensible when there were no breakpoints; the rewrite introduced one (~1100px, right column drops beneath left), which strengthens the case for the section.
- **L7** The card detail panel's content swap on inspection change has no `prefers-reduced-motion` entry — the inventory claims to be exhaustive.
- **L8** Right-column panel visibility is specified for cold-open-no-deck but not for the database-not-initialized or disconnected states, which also put a State panel in the left column.
- **L9** `POST /agent/events` no longer appears in either spine; the agent-view IA rows cite tool names instead. Nothing dangles, but the endpoint was previously a verbatim-name anchor.

## Closed during this pass

| # | Was | Now |
|---|---|---|
| **C1** (H4) | Detail panel `aria-live="polite"` + hover-driven target = one announcement per card hovered | Panel is **not** a live region. Only a *pin* announces, once, via a separate polite region. Transient hover/focus changes are silent |
| **C2** (H3, partial) | Tab order's first stop was a skip link with no spec in either file | Skip link specified in both — DESIGN.md Components + frontmatter tokens, EXPERIENCE.md Component Patterns. Targets the detail panel heading; withdrawn when a State panel replaces the grid |
| **C3** (M4) | `card-tile.live-ring` used `accent-dim` (2.70:1 on the overlay surfaces where tiles appear inside agent views) | Uses `{colors.accent}` (5.5:1), with the reason stated inline so it isn't "corrected" back |
| **C4** (M5) | Focus ring over card art had no contrast guarantee | New `{components.card-tile.focus-ring-over-art}` — ring plus a dark outer edge, legible over light or dark art |
| **C5** (M6) | `--numeric-features` referenced, undefined | Defined as `{typography.numeric.numeric-features}`; prose rewritten to reference it |
| **C6** (M7) | Agent-view behavior during state transitions unspecified | Two State Patterns rows added |
| **C7** (M8) | FR-05 uncited after the toggle was removed | Cited on the Deck list panel with an explanation of how it's satisfied |

## Mechanical checks

- **Token resolution:** 117 distinct `{…}` references extracted from both files and walked against the DESIGN.md frontmatter tree; **all resolve**. No color token missing a value. One component group — `components.badge` — is defined but never referenced in `{…}` form (Badge is named in prose only); see L2.
- **YAML:** both files parse. DESIGN.md — 26 colors, 7 typography roles, 24 component groups. *(An unquoted `Voltglass:` in the `description` broke parsing on first write and was fixed.)*
- **Contrast:** recomputed from hex via WCAG relative luminance, not copied from the design system's readme. All 9 rows of the DESIGN.md table verify. Two results are load-bearing and both were **absent from or wrong in** the upstream readme: `accent-dim` on `surface-overlay` is **2.70:1** (fails the 3:1 non-text floor — the readme claims a blanket pass on "base surfaces"), and `text-tertiary` on `surface-overlay` is **4.81:1**, the tightest pair in the system with no headroom.
- **Name parity:** all 22 DESIGN.md component names now appear byte-identical in EXPERIENCE.md where a behavioral row exists. Four drifted after the rewrite (Card detail/Card detail panel, Nav pill/Agent views nav, Agent view shell/Agent view, Legality row/Format check) and were aligned before this gate ran.
- **Shape:** DESIGN.md — 8 canonical sections, canonical order. EXPERIENCE.md — 8 required defaults present, plus Latency & Freshness, Inspiration & Anti-patterns, Rulings, Residuals. One default (Responsive & Platform) dropped, see L6.
- **Status:** both spines are still `status: draft`.

## Gate recommendation

**Pass with conditions.** Close before the pair is treated as implementation-ready:

1. **H1** — resolve `companion_show_groups`: add the tool to the PRD or drop the view. *Requires a decision.*
2. **H2** — design the DFC flip control into both spines. *Requires a design pass.*
3. **H3** — record the arrow-key-grid-navigation deferral explicitly, or adopt it.
4. **M1, M2, M3, M9** — four small edits: name the presentation-only primitives, reconcile SC-1 against the entry animation, add `sources` + composition references, cite NFR-08.

Lows at author's discretion. Then flip both files to `status: approved`.

**Not validated by this gate:** the four rulings in EXPERIENCE.md (push auto-opens its view; hover-transient + click-to-pin; detail panel is non-modal; tier D). They are product decisions made by the author of both the spines and this report, and no lens here tests them. They want Brad.

---

## Gate close — 2026-07-25

Brad's dispositions: H1 new FR + design · H2 new FR + design · H3 defer · H4 agree closed.

### Correction to this report

**H2 was miscategorised.** It was raised as needing a new FR. It does not: **FR-19 already mandates the flip control** — "Double-faced cards show the front face with a dedicated flip control — distinct from clicking the card, which opens the detail view (FR-17)". The gap was a missing *design*, not a missing requirement. No duplicate FR was created; had one been, the PRD would now carry two requirements for one control. The finding stands as written in substance — the control had no spec — but its remedy was half what was recorded.

### Dispositions

| # | Disposition | What changed |
|---|---|---|
| **H1** | **Closed — new FR + design** | `FR-23` (`companion_show_groups`, P1) added to PRD Feature D and Phase 2. Addendum records that its payload shape is **not** covered by OQ-A's parked constraints — groups carry a title and prose rationale, and may reference cards outside the active deck — so schema work must extend. IA and Component Patterns now cite FR-23. Design consequence found while specifying: tiles in a group carry **no quantity badge** unless the card is in the deck, since the badge means "copies in this deck" and "×0" would be false. |
| **H2** | **Closed — design only** (see correction) | DFC flip control fully specified in both spines. Visual: circular 28px control, 32px hit area, pinned **top-left** — the top-right is occupied by the quantity badge in this design, a collision the previous draft never faced. Shares the badge's scrim+blur material; stroke-based rotate glyph, never symbol-like. Behavioral: own click target with `stopPropagation`, never sets/pins/clears inspection; Tab order immediately after its own tile; state keyed by printing UUID, survives `deck_changed`, per-tab, resets on refresh; flipped state follows the printing everywhere it appears, and hovering a flipped tile targets *that face*. Rendered only where per-face `image_uris` exist (FR-04) — split/adventure/flip layouts get no control. Reduced-motion fallback added. |
| **H3** | **Closed — deferred, recorded** | Arrow-key grid navigation is now an explicit `[DEFERRED 2026-07-25 — gate H3]` entry in Interaction Primitives, stating the cost plainly: 100+ sequential Tab stops between header and right column, skip link as sole mitigation, accepted on the mouse-first posture. Carries a **revisit-before-public-release** flag, because the footer's Fan Content Policy links sit behind the grid in the Tab order. |
| **H4** | **Closed — agreed** | As recorded in C1. |
| **M1** | Closed | Panel, Badge, StatChip, Group header, ManaPip/ManaCost declared presentation-only primitives with no behavioral contract — stated, not silent. |
| **M2** | Closed | SC-1's clock stops at first paint of laid-out content; the 480 ms entry animation runs on top of a complete layout and is never inside the budget. |
| **M3** | Closed | `sources` added to DESIGN.md; `composition-reference` on both. Components section carries a reference naming what the mock does and does **not** demonstrate — seven components are specified with no visual precedent. |
| **M9** | Closed | NFR-08 cited on both footer entries. |

### Post-close verification

- 127 distinct token references walked against the frontmatter tree — **all resolve**. Component groups: 25.
- Both files parse; both `status: approved`.
- FR/NFR/SC citations now present across the pair: FR-04, 05, 06, 07, 08, 11, 12, 13, 16, 18, 19, 22, 23; NFR-02, 04, 05, 08; SC-1, 2, 4, 5.

### Remaining, by choice

- **Lows L1–L9** — author's discretion, unactioned.
- **Session history (FR-18)** — still a residual; the nav pill's last-push timestamp covers "re-open the latest of each kind", not "the last ~20 pushes".
- **The four rulings** — unconfirmed.
- **Upstream design-system defects** — `ManaCurve`'s dead bucket, `Panel`'s inverted elevation, `Badge`'s hard-coded RGB, the missing Voltglass typography block, `SuggestionCard`'s `accent-dim`. These live in the Claude Design project, not in these spines, and the spines now specify the corrected behavior in each case.
