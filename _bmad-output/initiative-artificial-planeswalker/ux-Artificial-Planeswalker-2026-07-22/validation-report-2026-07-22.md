> ## ⚠ SUPERSEDED — 2026-07-25
>
> This document reviews the **pre-Voltglass** spine pair (warm-gold identity, agent drawer, modal Detail view, grid/list view toggle, `text-muted`). Those artifacts no longer exist: `DESIGN.md` and `EXPERIENCE.md` were rewritten on 2026-07-25 to match the design built in Claude Design.
>
> Findings here reference tokens, components and surfaces that have been removed. **Do not action them.** The current gate is `validation-report-2026-07-25.md`.
>
> Retained for history only.
# Validation Report — Artificial-Planeswalker

- **DESIGN.md:** `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md`
- **EXPERIENCE.md:** `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md`
- **Run at:** 2026-07-22 (Reviewer Gate at Finalize; lenses: rubric walker + accessibility)

## Overall verdict

This is a clean, extractable spine pair: every `{path.to.token}` reference in both files resolves to a defined frontmatter token, all 14 named components carry both a visual spec (DESIGN.md) and real behavioral rules (EXPERIENCE.md), verbatim names (tools, endpoints, `deck_changed`, image sizes, UJ-1) mirror the PRD exactly, and the delegated-design rulings the addendum pushed to UX are each committed with a concrete decision. One high-severity gap blocks a fully clean handoff: the **Deck view text list view and its view toggle** — a P0 surface named in the IA table (FR-05) — have no component spec in either spine. The rubric walker's gate recommendation is **pass with conditions**: close that high plus the three mediums (empty-deck state, curve multicolor bucketing, modal focus management) before mocks, lows at author's discretion.

The accessibility reviewer materially shifts that picture: it adds one critical and five highs, computed from the spine's own hex values rather than its prose claims. The critical is arithmetically self-refuting spec text — every sanctioned use of `text-muted` is 11px micro text that can never qualify for the 3:1 large-text escape hatch the restriction leans on, and one of those uses is the legally load-bearing NFR-08 Scryfall/Fan-Content-Policy footer shipping below AA. The highs include a de-facto keyboard trap (100+ tab stops between page focus and the drawer a push just filled), color-only mana-curve encoding with adjacent-segment contrast as low as 1.03:1, and the product's own climax moment — the deck updating by itself — carrying zero accessible signal. All of these are spec-level fixes now and expensive after implementation; the conditions for gate close should therefore extend to the accessibility critical and highs alongside the rubric's.

## Category verdicts

- Flow coverage — strong
- Token completeness — strong
- Component coverage — adequate
- State coverage — adequate
- Visual reference coverage — strong (vacuous)
- Bloat & overspecification — strong
- Inheritance discipline — strong
- Shape fit — strong

## Findings by severity

### Critical (1)

**[Accessibility]** — `text-muted` restriction is vacuous; its sanctioned uses fail the spine's own floor (§ DESIGN.md Colors + Footer attribution; EXPERIENCE.md Accessibility Floor)
DESIGN.md admits `text-muted` is "below AA body contrast — large/incidental text only," but both sanctioned uses render in `{typography.micro}` (11px) — footer attribution (`text-muted` on `surface-base` = **3.32:1**) and timestamps. 11px/500 is not WCAG large text (large = ≥24px, or ≥18.66px bold); the floor in EXPERIENCE.md ("all body text ≥ 4.5:1; large text ≥ 3:1") therefore requires **4.5:1** for every place `text-muted` is actually permitted, and it hits at most 3.45:1 on any surface. The design system contains no legitimate `text-muted` use at all. Worse, the footer is the NFR-08 Scryfall attribution and WotC Fan Content Policy notice — legally load-bearing text for a public release, shipped below AA.
Fix: Either lighten `text-muted` to ≥ #8A8172-ish (≥4.5:1 on `surface-base`) or restate the floor honestly (e.g., footer runs `text-secondary` at reduced size; kill `text-muted` from type-bearing roles, keep it for disabled/decorative only).

### High (6)

**[Component coverage]** — Deck view text list view + view toggle have no component spec, P0/FR-05 (§ DESIGN.md Components / EXPERIENCE.md Component Patterns, IA table)
The Deck view text list view (P0, FR-05) and its view toggle ("Reached from: View toggle in deck header") have no component spec anywhere: no text-list row visual spec in DESIGN.md (only an oblique "mana pips in text lists" in Colors), no toggle control, no behavioral rules in EXPERIENCE.md — default view, toggle persistence across refetch/refresh, row click → Detail view?, row anatomy, position in the Tab order all unstated. A story-dev implementing FR-05 must invent a P0 surface.
Fix: Add a "View toggle" and "Text list row" pair to both spines (row anatomy: name in `body-strong`, mana pips, quantity, type-group headers reuse `label`; toggle default = grid, per-tab persistence, rows click through to Detail view; insert toggle into the Tab-order list).

**[Accessibility]** — Unknown-card truncated ID at 2.87:1 — the only identifying information, below even the large-text bar (§ DESIGN.md Components → Card placeholder)
Unknown-card truncated ID is `text-muted` micro on `surface-overlay` = **2.87:1** — below even the 3:1 large-text bar, and it is load-bearing: it is the *only* identifying information for an unknown card (the name slot literally says "Unknown card"). Directly violates DESIGN.md's own Don't ("`text-muted` for any load-bearing text") within DESIGN.md's own Card placeholder spec.
Fix: Render the truncated ID in `text-secondary` (6.21:1 on overlay — passes).

**[Accessibility]** — Tier "A" chip fails AA; its foreground is never stated (§ DESIGN.md Components → Tier row)
Label chips are `{typography.heading}` = 17px/600, not large text (needs ≥18.66px bold), so the floor is 4.5:1. If the A chip keeps `label-foreground` (`text-inverse`) on `accent-dim`, that is **3.62:1** — fail. (S on `accent` = 9.48:1 passes; B/C as `text-secondary` on `surface-overlay` = 6.21:1 pass.) The spec never states the A chip's foreground, which is itself a defect.
Fix: Specify A's foreground explicitly and make it pass — `text-inverse` on `accent` at reduced opacity is a trap; use `accent-bright` text on `surface-overlay` (10.8:1) with an `accent-dim` border, or bump the chip type to ≥19px/700.

**[Accessibility]** — Tab order is a de-facto keyboard trap for the drawer (§ EXPERIENCE.md Interaction Primitives)
Declared order "tiles → flip controls → drawer rows → pill → footer links" means 100+ stops on a Commander deck between page focus and the Agent drawer's content, dismiss ×, and history strip — every time a push arrives. No skip link, no focus management on drawer open/close/content-replace; a push that replaces drawer content in place will silently destroy focus if it was on a row. "Tiles → flip controls" reads as two sequential groups, divorcing each flip control from its card; and the drawer ×, history chips, deck view toggle, and Detail-view close are absent from both the Tab enumeration and the Enter-activation list. This is not the arrow-key grid nav the PRD rejected — it is the declared floor failing its own "reachable and operable" bar.
Fix: (1) Interleave each flip control immediately after its tile; (2) add a skip link ("Skip to agent panel") and/or move focus to the drawer header on open, returning it on close; (3) on in-place content replacement, move focus to the drawer header; (4) extend the Tab + Enter enumeration to every interactive element: drawer ×, history chips, view toggle, Detail × and flip, footer links.

**[Accessibility]** — Mana-curve stacked segments are color-only encoding with unusable adjacent contrast (§ DESIGN.md Components → Mana curve bars)
Segment-vs-segment ratios: mana-blue/mana-red **1.03:1**, blue/colorless 1.13, black/green 1.07, green/colorless 1.07 — every non-white adjacent pair under 1.3:1, white-vs-others tops out at 2.73:1. No separator, pattern, label, or text alternative is specified for the per-bucket color breakdown; only the total count above each bar is text (violates WCAG 1.4.1 use-of-color and the 3:1 non-text graphics floor).
Fix: Either declare the color breakdown decorative-only (counts are the data; `aria-hidden` on segments plus a text/tooltip breakdown in the bar's accessible name), or add 1px `surface-inset` separators between segments plus an accessible per-bar name ("3 cost: 5 cards — 3 green, 2 red"). Separators alone do not fix CVD ambiguity; the accessible name does.

**[Accessibility]** — Deck-change climax is invisible to assistive tech; the "non-motion signal" is itself motion (§ EXPERIENCE.md Accessibility Floor + Component Patterns → Quantity badge)
aria-live is scoped to the pill and drawer header only; deck refetches explicitly "do not announce." The declared non-motion signals for a deck change are (a) a gold glow flash fading over 200ms — a transient animation, missable and non-existent for AT — and (b) a group-header count silently changing text. UJ-1's climax ("the deck view updates by itself within a second") therefore has no accessible signal at all.
Fix: Keep refetch-level silence, but add one coalesced polite announcement per settled `deck_changed` ("Deck updated — Creatures 25") — the refetch-coalescing machinery already exists to debounce it; and stop calling the glow flash "the non-motion signal" — the count text is the non-motion signal, the flash is garnish.

### Medium (8)

**[Component coverage]** — Mana curve bars: multicolor-card bucketing undecided (§ DESIGN.md Components → Mana curve bars)
`colors.mana-gold` is defined and Colors names it in the WUBRG range, but the curve-bar spec says segments are "proportional to that cost bucket's color makeup" using `{colors.mana-white}` … `{colors.mana-colorless}` — excluding gold. Whether a Golgari card contributes one gold segment or fractional black+green segments is unspecified, and it changes the visual and the computation.
Fix: One sentence committing a rule (recommend: multicolor cards render a single `mana-gold` segment; pips elsewhere stay per-color).

**[State coverage]** — Empty active deck (0 cards) has no state (§ EXPERIENCE.md State Patterns)
`create_deck` produces empty decks and `companion_set_active_deck` can target one; Flow 2 even mentions "(empty or imported) decks". What the Deck view renders for an active deck with zero cards — empty grid? a state-panel variant? zero-height curve bars? — is unspecified.
Fix: One State Patterns row (recommend: deck header + name render, calm in-grid line "This deck is empty — ask your agent to add cards", curve hidden).

**[State coverage]** — Modal focus management is unspecified (§ EXPERIENCE.md Accessibility Floor / Detail view pattern row)
Esc layering and Tab order exist, but nothing says the Detail view (a modal over a scrim) traps focus while open or returns focus to the invoking tile/row on close; same question for the drawer (likely non-trapping since the deck view stays interactive — but that's reviewer inference, not the spine's ruling). Downstream a11y behavior will be invented inconsistently. (Converges with the accessibility reviewer's Detail-view modal finding below.)
Fix: Two sentences in Accessibility Floor or the Detail view pattern row (Detail view: trap + restore; Agent drawer: no trap, deck view remains in tab order).

**[Accessibility]** — Reduced-motion coverage is a partial list posing as "every motion" (§ EXPERIENCE.md Accessibility Floor; DESIGN.md Do's and Don'ts)
The floor enumerates drawer slide, hover pop, image fade-in, curve bar animation, glow pulse — but the spines also specify: push-replace crossfade (200ms), DFC flip 3D Y-rotation, Detail view fade + 4px rise, and the refetch header shimmer; none has a stated fallback. Separately, the reconnecting pill's "gentle pulse" is a looping ambient animation — which DESIGN.md's own Don'ts column bans outright — and its reduced-motion state is unspecified.
Fix: Make the inventory exhaustive with a per-motion fallback table (crossfade → instant swap; flip → instant face swap; detail → instant appear; shimmer → static "updating" text or nothing; pulse → static caution dot, state already carried by dot-color + pill text). One blanket sentence will not survive implementation.

**[Accessibility]** — Pill hover disclosure violates the spine's own hover-only ban (§ EXPERIENCE.md Component Patterns → Connection status pill vs. Interaction Primitives → Banned)
"Hover reveals the port and instance ID" — port/instance appear nowhere else in the UI, making this exactly the "hover-only disclosure of unique information" that Interaction Primitives bans, with no keyboard or screen-reader path specified.
Fix: Make the pill focusable with the same disclosure on focus (tooltip pattern with `aria-describedby`), or print port/instance in the Disconnected state panel where it is actually needed.

**[Accessibility]** — Zero semantic structure specified (§ EXPERIENCE.md Component Patterns; DESIGN.md Components)
Neither spine assigns a single ARIA role, landmark, or heading level: is the drawer a `complementary` region or a non-modal `dialog`? Is the Detail view `role="dialog" aria-modal="true"` (it must be — it has a scrim and Esc)? Are "CREATURES — 24" group headers headings? Is the deck grid a list? For a spec that calls itself "the behavior contract," the accessibility tree is entirely implementer's choice.
Fix: One short mapping table: deck name = h1; group headers = h2; drawer = `aside`/`region` labeled by push kind, its header a h2; Detail view = modal dialog labeled by card name; grid + drawer lists = `ul`; state panel = `region` with h2 headline.

**[Accessibility]** — Detail view modal behavior half-specified: no trap, no initial focus, no focus return (§ EXPERIENCE.md Component Patterns → Detail view)
Open/close triggers exist, but no focus trap, no initial-focus target, and no focus-return-to-origin on close. Without a trap, Tab from inside the "modal" wanders into the 100-tile grid behind the scrim; without focus return, Esc dumps keyboard users at the document top. (Converges with the rubric walker's modal-focus-management finding above.)
Fix: Specify: focus moves to the dialog on open (close button or dialog itself), Tab cycles within it, close returns focus to the originating tile/row.

**[Accessibility]** — Footer links unidentifiable at rest (§ DESIGN.md Components → Footer attribution)
Underline appears only on hover, and the surrounding text is the same `text-muted` — so at rest a link is distinguished by literally nothing (not even color), failing WCAG 1.4.1 and mouse-less discovery.
Fix: Persistent underline (quiet is fine — underline in the same color reads calm), hover merely brightens to `text-secondary`.

### Low (14)

**[Flow coverage]** — P1 features have no Key Flow (§ EXPERIENCE.md Key Flows)
P1 features (Swap panel FR-09, Tier-list panel FR-10, Session history FR-18) have no Key Flow. Their behavior is fully specified in Component Patterns + State Patterns, and the PRD names no journey for them, so this is acceptable — noted for completeness only.
Fix: None required; optionally add a one-flow "revisit a push" beat when P1 lands.

**[Token completeness]** — `easing-standard` defined but never referenced (§ DESIGN.md frontmatter ~line 93)
`components.motion.easing-standard` is defined but never referenced by any component or prose in either file.
Fix: Either bind it (e.g., image fade-in, badge glow fade) or drop it.

**[Token completeness]** — fontWeight 650/550 require a variable font (§ DESIGN.md Typography)
`fontWeight` values `'650'` and `'550'` (display, label) require a variable font; the declared fallbacks (`'Segoe UI', system-ui`) only carry static weights and will snap to 600/500.
Fix: One sentence in Typography stating the intended static-fallback rounding.

**[Token completeness]** — Gold-glow shadow specified inline, not tokenized (§ DESIGN.md Elevation & Depth)
The gold-glow shadow (`0 0 0 1px {colors.accent-dim}, 0 0 16px {colors.accent-glow}`) is a load-bearing recurring treatment specified inline rather than as a component token.
Fix: Optional `components.glow` token for single-source reuse.

**[Component coverage]** — Frontmatter component keys drift from prose names (§ DESIGN.md frontmatter)
`swap-row` / "Swap pair row", `detail-overlay` / "Detail view", `status-pill` / "Connection status pill", `curve-bar` / "Mana curve bars". All references resolve explicitly so nothing breaks; noted for grep-ability.
Fix: Optional key alignment.

**[State coverage]** — Detail view hydration state unstated (§ EXPERIENCE.md State Patterns / skeleton policy)
`GET /api/cards/{card_id}` runs on open, but what shows in the right column before it resolves is unstated (placeholder-then-fill covers imagery only). On localhost this is sub-perceptual; still, the skeleton-vs-placeholder policy could name it.
Fix: One clause extending the policy to Detail-view text hydration.

**[State coverage]** — Behavior below the ~800px floor undefined (§ EXPERIENCE.md Foundation, [ASSUMPTION]-tagged)
Behavior below the ~800px floor (already [ASSUMPTION]-tagged) is undefined — acceptable for a desktop-posture tool.
Fix: A minimum-supported-width statement would close it.

**[Bloat & overspecification]** — Untokenized pixel one-offs (§ DESIGN.md Components, various)
Detail view "min 320px", State panel "max-width 480px", pill "8px status dot", swap-row "3px left rule", flip-control "hit-area ≥ 32px". Each appears exactly once, so tokenizing would be ceremony; flagged only so nobody mistakes them for missing tokens.
Fix: None.

**[Inheritance discipline]** — "Agent panel" vs "Agent drawer" dual naming (§ EXPERIENCE.md IA table / Component Patterns)
DESIGN.md bridges it explicitly ("Agent drawer — the Agent panel") and EXPERIENCE.md's IA row says "(slide-over drawer)", so no reference dangles — but a consumer grepping "Agent panel" won't hit the Component Patterns row.
Fix: Optional "(the Agent panel)" parenthetical on the EXPERIENCE.md component row.

**[Inheritance discipline]** — SC-2 cited loosely alongside the 1 s deck-render bound (§ EXPERIENCE.md Latency & Freshness; Flow 1 step 8)
SC-2 itself carries no timing — the number comes from NFR-05/UJ-1, which are co-cited, so nothing false is claimed; the citation is just loose.
Fix: None required.

**[Shape fit]** — Reflow rules split across files with no cross-pointer (§ EXPERIENCE.md Foundation / DESIGN.md Layout & Spacing)
Reflow rules are split between EXPERIENCE.md Foundation (window range) and DESIGN.md Layout & Spacing (column behavior) with no cross-pointer.
Fix: Optional one-line pointer in Foundation ("column reflow rules in DESIGN.md Layout & Spacing").

**[Accessibility]** — Hit targets below WCAG 2.5.8's 24px minimum likely (§ DESIGN.md/EXPERIENCE.md component specs)
Likely offenders: session-history chips (micro 11px text chips, height unspecified), footer links (single 11px line), and the drawer/Detail × buttons (size unspecified). Only the DFC flip control declares a compliant target (≥32px).
Fix: Declare ≥24×24px minimum interactive box (padding counts) for ×, history chips, and footer links in the spec, matching the flip-control precedent.

**[Accessibility]** — Thumbnail alt duplication: screen readers hear every card twice per row (§ EXPERIENCE.md Accessibility Floor, alt policy applied to rows)
Suggestion/swap/tier rows put the card name in visible text *and* alt = card name on the adjacent thumbnail.
Fix: alt="" (decorative) on thumbnails whose row already names the card; keep the name-alt rule for grid tiles and Detail view where the image is the only carrier.

**[Accessibility]** — Unstated foreground colors invite drift (§ DESIGN.md Typography / Components)
Group headers ("CREATURES — 24", `label` 12px — not large, needs 4.5:1) and the Detail-view type line have no declared color. `text-secondary` passes everywhere (≥6.2:1); `text-muted` passes nowhere. Say which.
Fix: Declare `text-secondary` explicitly for both.

## Reviewer files

- `review-rubric.md`
- `review-accessibility.md`
