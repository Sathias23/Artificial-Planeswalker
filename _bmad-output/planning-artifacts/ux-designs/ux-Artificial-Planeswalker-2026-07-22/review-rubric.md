> ## ⚠ SUPERSEDED — 2026-07-25
>
> This document reviews the **pre-Voltglass** spine pair (warm-gold identity, agent drawer, modal Detail view, grid/list view toggle, `text-muted`). Those artifacts no longer exist: `DESIGN.md` and `EXPERIENCE.md` were rewritten on 2026-07-25 to match the design built in Claude Design.
>
> Findings here reference tokens, components and surfaces that have been removed. **Do not action them.** The current gate is `validation-report-2026-07-25.md`.
>
> Retained for history only.
# Spine Pair Review — Artificial-Planeswalker

Reviewer: rubric-walker (BMad UX Reviewer Gate) · 2026-07-22
Files: `DESIGN.md`, `EXPERIENCE.md` (run folder `ux-Artificial-Planeswalker-2026-07-22`)

## Overall verdict

This is a clean, extractable spine pair: every `{path.to.token}` reference in both files resolves to a defined frontmatter token, all 14 named components carry both a visual spec (DESIGN.md) and real behavioral rules (EXPERIENCE.md), verbatim names (tools, endpoints, `deck_changed`, image sizes, UJ-1) mirror the PRD exactly, and the delegated-design rulings the addendum pushed to UX are each committed with a concrete decision. One high-severity gap blocks a fully clean handoff: the **Deck view text list view and its view toggle** — a P0 surface named in the IA table (FR-05) — have no component spec in either spine. Fix that plus the three mediums and a downstream consumer can source-extract without inventing anything.

## 1. Flow coverage — strong

Sources define exactly one journey, **UJ-1 — Brewing session** (prd.md §3), plus SC-1–SC-5 which read as flow assertions. EXPERIENCE.md Flow 1 carries the verbatim UJ name, a named protagonist (Brad), 8 numbered steps, an explicit climax beat (step 8, the agent-drives/glass-shows loop closing), and two failure paths (unknown-ID entry per FR-13; swallowed event POST / accepted staleness). Flow 2 — Cold start is an invented flow but earns its place: it operationalizes SC-4 + FR-22 + the disconnected-state guidance the addendum delegated to UX, with protagonist, numbered steps, climax, and two failure paths. SC-1/SC-2 timing assertions appear inside the flows with correct citations.

### Findings
- **low** P1 features (Swap panel FR-09, Tier-list panel FR-10, Session history FR-18) have no Key Flow (EXPERIENCE.md Key Flows). Their behavior is fully specified in Component Patterns + State Patterns, and the PRD names no journey for them, so this is acceptable — noted for completeness only. *Fix:* none required; optionally add a one-flow "revisit a push" beat when P1 lands.

## 2. Token completeness — strong

Extracted the full frontmatter (25 colors, 7 typography roles, 4 radii, 9 spacing entries, 15 component token groups incl. `motion` and `focus-ring`) and every `{…}` reference in the prose of both files plus the intra-frontmatter references. **All resolve.** Every color token has a hex value (two use 8-digit hex with alpha: `scrim`, `accent-glow` — valid). Dark-only per confirmed decision, so no light pairs expected. Contrast targets are stated for the load-bearing pairs (DESIGN.md Colors: `text-primary` ≥ 12:1, `text-secondary` ≈ 6.7:1 AA, `accent` ≈ 8:1, `negative` ≈ 5:1, `text-muted` ≈ 3.2:1 explicitly restricted below-AA — restriction enforced in Do's and Don'ts and re-cited in EXPERIENCE Accessibility Floor). EXPERIENCE.md's token references (`{components.card-tile.hover-scale}`, `{components.agent-drawer.slide}`, `{components.motion.duration-base}`, `{components.motion.duration-fast}`, `{components.focus-ring}`, `{colors.text-muted}`) all resolve to DESIGN.md by name.

### Findings
- **low** `components.motion.easing-standard` is defined but never referenced by any component or prose in either file (DESIGN.md frontmatter line ~93). *Fix:* either bind it (e.g., image fade-in, badge glow fade) or drop it.
- **low** `fontWeight` values `'650'` and `'550'` (display, label) require a variable font; the declared fallbacks (`'Segoe UI', system-ui`) only carry static weights and will snap to 600/500. *Fix:* one sentence in Typography stating the intended static-fallback rounding.
- **low** Gold-glow shadow (`0 0 0 1px {colors.accent-dim}, 0 0 16px {colors.accent-glow}`, Elevation & Depth) is a load-bearing recurring treatment specified inline rather than as a component token. *Fix:* optional `components.glow` token for single-source reuse.

## 3. Component coverage — adequate

14 components extracted from all usage sites: Card tile, DFC flip control, Quantity badge, Agent drawer, Suggestion row, Swap pair row, Tier row, Detail view, Session history, Mana curve bars, Connection status pill, State panel, Card placeholder, Footer attribution. **All 14 have a visual entry in DESIGN.md Components and a behavioral row in EXPERIENCE.md Component Patterns, under identical names, with real rules on both sides** (e.g., DFC flip control: hit-area ≥ 32px, `stopPropagation`, `?face=`, per-tab persistence behaviorally; circular control, opacity ramp, 3D Y-rotation visually). The Card placeholder's unknown-card variant is specified in both spines including its behavioral exception (no Detail view).

### Findings
- **high** The **Deck view text list view** (P0, FR-05) and its **view toggle** ("Reached from: View toggle in deck header", EXPERIENCE.md IA table) have no component spec anywhere: no text-list row visual spec in DESIGN.md Components (only an oblique "mana pips in text lists" in Colors), no toggle control in DESIGN.md, no behavioral rules in EXPERIENCE.md Component Patterns (default view, toggle persistence across refetch/refresh, row click → Detail view?, row anatomy, position in the Tab order — all unstated). A story-dev implementing FR-05 must invent a P0 surface. *Fix:* add a "View toggle" and "Text list row" pair to both spines (row anatomy: name in `body-strong`, mana pips, quantity, type-group headers reuse `label`; toggle default = grid, per-tab persistence, rows click through to Detail view; insert toggle into the Tab-order list).
- **medium** **Mana curve bars: multicolor-card bucketing is undecided.** `colors.mana-gold` is defined and Colors names it in the WUBRG range, but the curve-bar spec (DESIGN.md Components) says segments are "proportional to that cost bucket's color makeup" using `{colors.mana-white}` … `{colors.mana-colorless}` — excluding gold. Whether a Golgari card contributes one gold segment or fractional black+green segments is unspecified, and it changes the visual and the computation. *Fix:* one sentence committing a rule (recommend: multicolor cards render a single `mana-gold` segment; pips elsewhere stay per-color).
- **low** Frontmatter component keys drift from prose names (`swap-row` / "Swap pair row", `detail-overlay` / "Detail view", `status-pill` / "Connection status pill", `curve-bar` / "Mana curve bars"). All references resolve explicitly so nothing breaks; noted for grep-ability. *Fix:* optional key alignment.

## 4. State coverage — adequate

Walked all 17 IA surfaces against the extraction digest's exhaustive states list (§8). Covered: cold open (deck / no deck), DB-not-initialized (incl. self-transition), DB-updating, refetch-in-flight (shimmer, latest-wins, coalescing), WS live/reconnecting/backend-gone (with ticket re-mint per NFR-01/NFR-04), deck deleted (404 → no-active-deck, FR-11), unknown card in push (FR-13), no-image-data placeholder (FR-19), CDN failure (FR-04, negative-cache), empty push (confirmed ruling, OQ-A side locked), DFC flip across re-renders, cross-tab, stale discovery file (correctly noted as tool-side/no UI), Deck power panel correctly fenced as Phase 3. Focus states covered via `{components.focus-ring}` + focus-visible rule. Session history empty state handled (strip hidden until first push).

### Findings
- **medium** **Empty active deck (0 cards) has no state.** `create_deck` produces empty decks and `companion_set_active_deck` can target one; Flow 2 even mentions "(empty or imported) decks". What the Deck view renders for an active deck with zero cards — empty grid? a state-panel variant? zero-height curve bars? — is unspecified (EXPERIENCE.md State Patterns). *Fix:* one State Patterns row (recommend: deck header + name render, calm in-grid line "This deck is empty — ask your agent to add cards", curve hidden).
- **medium** **Modal focus management is unspecified.** Esc layering and Tab order exist, but nothing says the Detail view (a modal over a scrim) traps focus while open or returns focus to the invoking tile/row on close; same question for the drawer (likely non-trapping since the deck view stays interactive — but that's my inference, not the spine's ruling). Downstream a11y behavior will be invented inconsistently. *Fix:* two sentences in Accessibility Floor or the Detail view pattern row (Detail view: trap + restore; Agent drawer: no trap, deck view remains in tab order).
- **low** Detail view hydration state: `GET /api/cards/{card_id}` runs on open, but what shows in the right column before it resolves is unstated (placeholder-then-fill covers imagery only). On localhost this is sub-perceptual; still, the skeleton-vs-placeholder policy could name it. *Fix:* one clause extending the policy to Detail-view text hydration.
- **low** Behavior below the ~800px floor (already [ASSUMPTION]-tagged) is undefined — acceptable for a desktop-posture tool; a minimum-supported-width statement would close it.

## 5. Visual reference coverage — strong (vacuous)

The run folder contains no `mockups/` or `wireframes/` directories and `imports/` is empty — verified by listing. This matches the workflow (mocks come after this gate) and the memlog's "no user-supplied imports" event. Consequently there are no orphaned references: neither spine contains a `→ Composition reference:` line (the examples show these appearing only once mocks exist). No findings. Note for the post-mock pass: FR-20 names "reference screenshots, comparison set" as part of the concrete visual direction — the Inspiration & Anti-patterns section carries the comparison set in prose; the screenshot half lands with the mocks and should be re-checked then.

## 6. Bloat & overspecification — strong

Both files are tight for the surface count they carry. DESIGN.md's editorial voice is doing decision work ("dim gallery wall; the cards are the paintings" directly generates the no-tint/no-frame rules). EXPERIENCE.md prose is behavioral, not narrative; its one verbatim PRD quote (the read-only-glass principle) is flagged as verbatim and is the product's governing constraint, not restatement. Tables are used where tables work (IA, Voice and Tone, Component Patterns, State Patterns). No persona/FR/scope restatement — the spines cite FR/SC/NFR IDs instead of copying them, which is the right altitude.

### Findings
- **low** A handful of untokenized pixel one-offs (Detail view "min 320px", State panel "max-width 480px", pill "8px status dot", swap-row "3px left rule", flip-control "hit-area ≥ 32px"). Each appears exactly once, so tokenizing would be ceremony; flagged only so nobody mistakes them for missing tokens. *Fix:* none.

## 7. Inheritance discipline — strong

- `sources` frontmatter resolves: both PRD paths exist on disk; the `DESIGN.md (peer)` entry resolves within the run folder.
- Verbatim names all mirror the PRD/extraction digest exactly: **UJ-1 — Brewing session**; surfaces (Deck view, Agent panel, Suggestion/Swap/Tier-list panel, Detail view, No-active-deck, "Database not initialized", "Database updating"); tools (`companion_set_active_deck`, `companion_show_suggestions`, `companion_show_swaps`, `companion_show_tier_list`); endpoints (`GET /api/decks`, `GET /api/deck/{id}`, `GET /api/cards/{card_id}`, `GET /api/card-image/{scryfall_id}`, `POST /agent/events`, `GET /health`, `GET /api/session`); `deck_changed`; image sizes (`small`/`normal`/`large`/`png`); discovery-file authority; tier labels S/A/B/C.
- FR/NFR/SC citations spot-checked against the PRD: FR-08 replace semantics, FR-07 restart → no-active-deck, FR-11 delete-404, FR-13 partial-push, FR-22, NFR-02, NFR-04 ticket re-mint, NFR-05 timings, SC-1 250 ms — all accurate.
- Neither spine restates the PRD glossary (correct — terms are used, not redefined, and usage matches the PRD definitions). Component names are identical across all four sections of the pair.
- Assumption hygiene is exemplary: confirmed rulings are labeled "confirmed ruling 2026-07-22" (empty-push render, drawer re-open — matching memlog line 20), while the still-delegated rulings (DFC flip persistence, cross-tab divergence, keyboard floor, pill hover detail, announcement scope, window bounds, staleness silence) carry `[ASSUMPTION]` tags **with a concrete committed ruling in each** — so extraction is never blocked; the tag is provenance, not indecision.

### Findings
- **low** "Agent panel" (PRD surface name, IA table) vs "Agent drawer" (component realizing it) is dual naming. DESIGN.md bridges it explicitly ("Agent drawer — the Agent panel") and EXPERIENCE.md's IA row says "(slide-over drawer)", so no reference dangles — but a consumer grepping "Agent panel" won't hit the Component Patterns row. *Fix:* optional "(the Agent panel)" parenthetical on the EXPERIENCE.md component row.
- **low** SC-2 is cited alongside the 1 s deck-render bound (Latency & Freshness; Flow 1 step 8). SC-2 itself carries no timing — the number comes from NFR-05/UJ-1, which are co-cited, so nothing false is claimed; the citation is just loose. *Fix:* none required.

## 8. Shape fit — strong

- **DESIGN.md:** all eight canonical sections present in canonical order (Brand & Style → Colors → Typography → Layout & Spacing → Elevation & Depth → Shapes → Components → Do's and Don'ts). Frontmatter complete per spec (name, description, colors as flat hex object, typography objects, rounded, spacing, components with `{…}` refs).
- **EXPERIENCE.md:** all eight required defaults present (Foundation, Information Architecture, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Key Flows). Required-when-applicable **Inspiration & Anti-patterns is present** — correctly triggered by the Arena/Untapped.gg references in FR-20 and the memlog, and it does real work (each rejection ties to a constraint: trade dress → Fan Content Policy, debug dashboard → SC-5, write affordances → product premise).
- Invented sections earn their place: **Latency & Freshness Contract** converts NFR-04/NFR-05/SC-1 into implementable UX rules (skeleton-vs-placeholder policy, coalescing, freshness posture) that no default section would house.
- One default dropped: **Responsive & Platform**. Defensible — single fluid desktop surface, no breakpoints, no platform variance; the reflow behavior lives in DESIGN.md Layout & Spacing (3→8+ columns, fixed 63:88 tiles) and Foundation (window range). The drawer's fixed 40% at the 800px floor (a 320px drawer) is survivable per the suggestion-row spec, so nothing breaks.

### Findings
- **low** Reflow rules are split between EXPERIENCE.md Foundation (window range) and DESIGN.md Layout & Spacing (column behavior) with no cross-pointer. *Fix:* optional one-line pointer in Foundation ("column reflow rules in DESIGN.md Layout & Spacing").

## Mechanical notes

- All 14 component names byte-identical across DESIGN.md Components, EXPERIENCE.md Component Patterns, and both files' prose references. Frontmatter kebab keys drift from prose names in four cases (see §3 low) but every reference is explicit, so nothing dangles.
- All `{…}` references in both files resolve; no reference to an undefined token, no color token missing a hex. `easing-standard` is defined-but-unused (§2).
- `.memlog.md` line 17 records "27 colors" and "81 token refs"; the shipped frontmatter has **25** color tokens. Log-vs-artifact drift only — the artifact is internally consistent and the artifact wins. No action needed beyond awareness.
- `sources` frontmatter: both PRD paths verified on disk; peer DESIGN.md reference resolves. EXPERIENCE.md frontmatter matches the example shape (name, status, sources, updated). DESIGN.md adds `status`/`updated` beyond the spec's listed keys — harmless extension, consistent with the pair.
- Run folder contains only the two spines, `.memlog.md`, `.working/prd-extraction.md`, and an empty `imports/` — no mockups/wireframes, as expected pre-gate.
- Memlog rulings ledger reconciles with the spines: 3 confirmed rulings marked "confirmed", the remainder correctly still `[ASSUMPTION]`-tagged with committed rulings. The two most consequential tagged rulings (DFC flip persistence keyed by printing UUID; per-tab history, no cross-tab sync) are exactly the ones the PRD addendum delegated to the UX spec, so the spine deciding them is the intended resolution — recommend Brad's sign-off converts those tags at gate close.

## Finding totals

| Severity | Count |
|---|---|
| critical | 0 |
| high | 1 |
| medium | 3 |
| low | 11 |

Gate recommendation: **pass with conditions** — close the high (text list view + view toggle spec) and the three mediums (empty-deck state, curve multicolor bucketing, modal focus management) before mocks; lows at author's discretion.
