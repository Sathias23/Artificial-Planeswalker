# Claude Design Import — Review

Reviewer: import review pass · 2026-07-25
Source: Claude Design project `3bb77343-987c-46b8-98cf-4eec374ae797` — "Artificial Planeswalker companion app"

**Framing:** this design was developed directly in Claude Design, independently of the `claude-design-handoff-prompt.md` prompts and of the `DESIGN.md` / `EXPERIENCE.md` spines. So the places where it departs from those documents are **decisions, not defects** — they're catalogued in §3 as upstream work, not findings. §1 and §2 are the review proper: problems the design has on its own terms, and constraints the built app will hit regardless of styling.

## What came back

| Artifact | Content |
|---|---|
| `Planeswalker Companion.dc.html` | One screen, 1720×1440, live-data template (not a static mock — needs `support.js` + React globals). A Standard Boros Aggro 60-card list, three-region layout, plus three full-screen modal "agent views". |
| `_ds/readme.md` | Design-system spec: 5 candidate themes with rationale, tokens, type scales, elevation/motion language, per-theme contrast tables. **Voltglass chosen**, shipped as `:root`. |
| `_ds/tokens/theme-*.css` | 5 themes as `data-theme` scopes; Voltglass doubles as `:root`. |
| `_ds/tokens/typography.css`, `motion.css`, `fonts.css` | Shared role scaffold + per-theme overrides; Google Fonts CDN import. |
| `_ds/_ds_bundle.js` | 10 React components: Panel, Badge, StatChip, AgentStatus, CardTile, DeckRow, ManaPip, ManaCost, ManaCurve, SuggestionCard. |
| `_ds/_adherence.oxlintrc.json` | Lint contract: per-component prop allowlists + enum values, bans raw hex/px in JSX. *(left upstream — machine artifact)* |
| `_ds/_ds_manifest.json` | Token/card index compiled from the above. *(left upstream — derived)* |
| `support.js` | Generated `dc-runtime` (React template renderer). Not design content; **not copied** — 70 KB of build output. |

## Verdict

The theming layer is strong and directly usable. Five themes that are genuinely distinct personalities rather than palette swaps — they differ on radius scale (0→16px), motion philosophy (Ink's 0ms cut vs Voltglass's 900ms aurora), elevation strategy (glow rim / soft shadow / none / hairline-only), and type family and weight approach. The contrast tables are real: recomputed independently, Voltglass `text-tertiary #8b91ad` on `surface-overlay #222639` = **4.81:1** against the claimed 4.8. Every text token clears 4.5:1 on all four surfaces in all five themes as stated, and `accent-dim` is correctly fenced to non-text use at ≥3:1. Trade dress is respected throughout — no fantasy faces, no card-frame chrome, `ManaPip` deliberately a plain dot.

The screen has real craft in it. What holds it back is not its direction but its finish: a handful of genuine bugs in the components, a system that doesn't yet contain the patterns the screen invented, and no states.

---

## 1. Defects — internal to the design

These are wrong on the design's own terms: bugs, or contradictions with the design system's own stated rules.

- **high · `ManaCurve` always renders a dead leading column.** `curve[Math.min(5, d.cmc)]` fills a 6-slot array with lands excluded, so index 0 can never be non-zero — every deck shows an empty "0" bucket. Also the axis labels come from `i === curve.length - 1 ? i + '+' : i`, which prints `0 1 2 3 4 5+`. For a deck with a real top end the `5+` bucket silently absorbs everything above 5 with no indication.

- **high · `ManaCurve` fills bars with `var(--mana-colorless)`.** The readme's own hard constraints say "data colors never appear in chrome" — this is a data token used as chrome fill, and it reads semantically as *colorless mana* when it means *generic bar*. Use a neutral chrome token, or commit to actually stacking the bars by colour.

- **high · `Panel`'s elevation logic is inverted, and hard-codes a shadow two themes ban.** `boxShadow: live ? 'var(--shadow-raise)' : '0 12px 32px rgba(0,0,0,0.5)'`. Graphite and Ink set `--shadow-raise: none`, so under those themes a *live* panel loses its elevation while an *idle* one gets a heavy shadow their personalities explicitly forbid ("no shadows, no glow"; "1px rules only"). The same literal shadow is hard-coded in `CardTile` and the card-detail preview. Latent under Voltglass, where it happens to read correctly. *Fix:* both branches through tokens; add `--shadow-rest` so shadowless themes can opt out of both.

- **medium · `Badge` hard-codes Voltglass values for three of five tones.** `positive` / `negative` / `caution` use literal `rgba(95,212,160,…)`, `rgba(255,122,134,…)`, `rgba(255,194,102,…)` for background and border while the foreground is correctly tokenized. Switch to Gilt or Ink and the text colour changes but the tint doesn't. *Fix:* `color-mix()` against the semantic token, or per-theme tint tokens.

- **medium · The readme's type spec and the shipped CSS disagree for the chosen theme.** `typography.css` has per-theme blocks for gilt/graphite/verdigris/ink but **none for voltglass**, so Voltglass falls through to `:root`. The readme specifies Voltglass micro at 10/400 and body-strong at 700; `:root` gives 10.5/500 and 600. Two of seven roles ship different from their own documentation.

- **medium · Tabular numerals are a stated hard constraint the token doesn't carry.** Every component sets `fontVariantNumeric: 'tabular-nums'` by hand and the screen repeats it inline; anyone writing `font: var(--type-numeric)` alone silently gets proportional figures — which is exactly the jitter the constraint exists to prevent. *Fix:* a companion `--numeric-features` token or a `.numeric` utility so it can't be forgotten.

- **medium · Two card aspect ratios coexist.** Tiles are `width × 1.4` (1:1.400); the detail preview is `aspect-ratio: 488/680` (1:1.393). A printed card is 63:88 (1:1.397). Small, but it means card imagery is cropped fractionally differently in two places on the same screen. *Fix:* one geometry token pair.

- **low · `ManaCurve.highlight` is dead code.** The prop is the only path to the accent colour in that component and the screen never passes it.

- **low · The spacing scale is defined and then bypassed.** The screen inline-codes 32 / 24 / 18 / 16 / 14 / 12 / 10 / 9 / 8 / 7 / 6 / 4px — of these 18, 14, 9, 7 (plus the 26px arrow and 44px tier letter) aren't on the declared 4/8/12/16/24/32/48 scale. Worth noting that `_adherence.oxlintrc.json` *would* catch raw px and raw hex, but it lints the JSX components, not the screen template — so the screen escapes its own guardrail.

- **low · Mock data doesn't reconcile.** Panel title says "16 distinct"; the deck array has 17 entries. Card-groups copy says the budget swap "takes the list from $214 to $137"; the computed deck value renders $234.50. Header badge and Format check both claim a 15-card sideboard; no sideboard is modelled. (What does reconcile: 60 cards, 15 one-drops, and the four swap deltas summing to the stated +$6.90.)

- **low · `ManaCost` mishandles real Scryfall cost strings.** The regex `/\d+|[WUBRGC]/gi` turns `{2/R}` into two separate pips and drops `{X}` entirely. Fine for the mock's hand-written costs; it will misrender hybrid and X costs on live data.

## 2. Constraints the built app hits regardless of design

Not styling opinions — facts about this product that the implementation has to satisfy whatever the screen looks like.

- **critical · The Fan Content Policy / Scryfall attribution has to exist in the shipped app.** It's a condition of releasing publicly under the FCP, and it's the one thing here that isn't negotiable by design taste. A mock not drawing it is fine; the app not having it is not. Currently there's also no `FooterAttribution` component in the system to render it with.

- **high · Google Fonts CDN is the wrong delivery for this product.** `tokens/fonts.css` `@import`s all five families from `fonts.googleapis.com`. The companion is served from `localhost:8765`, its selling point is a single command with no config, and the local card database exists precisely so it doesn't depend on the network. A CDN webfont means the UI falls back to `sans-serif` offline and makes an outbound request from a local tool. It also loads five families to ship one. *Fix:* self-host the chosen family, bundled with the backend's static assets.

- **high · `AgentStatus` models a signal the backend doesn't have.** Its states are `idle | thinking | streaming` — agent cognition. The app observes tool-call pushes over a WebSocket; it has no visibility into what the agent is doing between them. As designed this component can only ever show `idle`. If you want agent presence on the glass, the honest axis is transport state (connected / reconnecting / backend gone) plus the active deck name. It also runs `apc-pulse … infinite`, a looping ambient animation — currently unused, so latent.

- **medium · Card images are hotlinked from the Scryfall API, per tile, per render.** `art()` builds `https://api.scryfall.com/cards/named?exact=…&format=image`, a redirect endpoint, called for every tile in the grid, every overlay, and the preview. Real images need to go through the backend proxy with caching and a placeholder on failure. A legitimate mock shortcut — but exactly the kind of line that gets lifted verbatim, so it's worth an in-file comment.

- **medium · Keyboard and focus have no path yet.** All six controls are `<div onClick>`; card selection is `onMouseEnter` only, so there's no click or Enter route to the detail panel; overlays have no dialog semantics or focus handling. This is largely an artifact of how `.dc.html` templates get authored rather than a design decision — but `--focus-ring` is defined in all five themes and consumed by nothing, so the visual answer doesn't exist yet either. Worth designing the focus state now while the tokens are being settled, rather than retrofitting it.

- **medium · The screen renders one state: fully-loaded happy path.** Cold open, no active deck, database not initialized, database updating, refetch in flight, reconnecting, backend gone, deck deleted, unknown card, missing image, empty deck — none are drawn. For this product the states are most of the design work (the entire cold-start flow is states), and `CardTile`'s no-art branch currently renders `ART — NAME` in micro caps, which is a debug affordance rather than a designed placeholder.

## 3. Upstream — the design won, the documents are stale

Deliberate departures. Listing them because `DESIGN.md`, `EXPERIENCE.md` and the PRD still describe the old shape, and dev stories will be written against whichever document is authoritative.

| The design decided | The documents still say | Consequence |
|---|---|---|
| **Voltglass** — cool blue-violet, Space Grotesk | `DESIGN.md` frontmatter: warm gold on warm near-black, `#131110` / `#E8B44A`, Inter, with contrast pairs already computed | `DESIGN.md` Colors + Typography need rewriting around Voltglass and re-verifying. Note Gilt is *not* the old palette either — different hexes, different accent, different family |
| Full-window three-region dashboard, 1720px | Deck view + agent drawer over the right 40%, deck stays visible, ~800–2560px range | `DESIGN.md` Layout & Spacing, `EXPERIENCE.md` Foundation + IA |
| Agent content in user-clickable full-screen modals, reached from an "Agent views" header nav | "Read-only glass — the agent drives"; pushes arrive, the drawer overlays 40% with no scrim; one-level overlay stack (detail over drawer) | The biggest one: it changes the product premise the PRD is written around. If it stands, the PRD's read-only framing and the FR-08 push semantics need restating |
| Card detail as a persistent right-column panel, hover-driven | Modal Detail view over a scrim, click-driven, focus-trapped | `EXPERIENCE.md` Component Patterns + Interaction Primitives |
| Standard, 60-card, sideboard, format legality, price totals | Commander 100-card as the canonical example; prices secondary | Mostly example-data framing, but "Format check" and "Deck value" are new surfaces with no FR behind them |
| Tier S/A/B/C/**D** | S/A/B/C | Minor, but the spine also says empty buckets are skipped |
| 10 components | 17 named components across both spines | The screen invents ~8 more inline (swap row, tier row, detail panel, quantity badge, overlay chrome, nav pill, group header, stat row) — those want promoting into the system before stories consume them, otherwise implementers inherit inline CSS instead of tokens |

## Passes worth recording

So they don't get "fixed" into regressions:

- **The contrast tables verify.** Independently recomputed — see Verdict. This is the most trustworthy part of the import.
- **The five themes are actual personalities**, not a palette swap.
- **Trade dress is respected throughout** — no fantasy faces, no card-frame chrome, no symbol lookalikes; `ManaPip` is deliberately a plain dot, which the readme calls out as an explicit anti-trade-dress choice.
- **Data colours stay out of chrome** everywhere except the `ManaCurve` fill — the colour-distribution bar and pips are correct uses.
- **`_adherence.oxlintrc.json` is a genuine guardrail** worth keeping: it pins each component's prop names and enum values and bans raw hex and raw px in JSX.
- **Esc-to-close is wired**, and card images carry `alt={name}`.
- **`--focus-ring` is defined per theme** (= accent-bright). The token is right even though nothing consumes it yet.

## Mechanical notes

- `review-accessibility.md` in the run folder is **stale in one place**: its critical finding computes `text-muted` at 3.32:1 on `surface-base`, but the shipped `DESIGN.md` carries `text-muted: #9A9080`, which recomputes to **6.04:1** on `#131110` (the file claims 5.99). That critical was remediated; it shouldn't be re-opened.
- The design project is `type: PROJECT_TYPE_PROJECT`, not `PROJECT_TYPE_DESIGN_SYSTEM`. That type is immutable at creation, so this project can't later be consumed as a design-system source by tooling that requires the type.
- Voltglass is scoped `:root, [data-theme="voltglass"]`, so its tokens also apply globally outside any themed wrapper. Harmless while one theme ships.
- `.dc.html` is not a standalone mock — it needs `support.js` plus React/ReactDOM globals and can't be opened from disk.
- `support.js` and the two machine artifacts were deliberately not copied locally; they're generated or derived and live upstream.
