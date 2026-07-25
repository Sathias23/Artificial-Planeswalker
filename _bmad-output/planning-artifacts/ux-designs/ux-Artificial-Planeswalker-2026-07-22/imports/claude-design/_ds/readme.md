# Artificial Planeswalker Companion — Design System (Theming Layer)

A dark, read-only visual panel for a Magic: The Gathering deckbuilding AI. The agent runs in a terminal on half an ultrawide; this app fills the other half in a browser. It is **read-only glass**: the agent drives, the app shows — a deck of cards with full art plus panels of agent-pushed suggestions. The chrome's only job is to make card art look magnificent: a dim gallery wall around the paintings.

**Sources:** none attached — built from the written brief only (no codebase, Figma, or brand assets). **No logo exists**; render the product name in plain type wherever a mark would go.

**Current scope: theming layer + component primitives.** 5 candidate themes (Voltglass chosen) and a read-only component set; no full screens yet. Each theme is a `data-theme` scope in `tokens/`; **`:root` defaults to Voltglass — the chosen theme.** The four runners-up remain available via `<html data-theme="gilt|graphite|verdigris|ink">` for reference.

## Hard constraints (all themes)
- Dark only. Card art is the hero: no large saturated fills, chrome separates by tone.
- Never imitative of WotC trade dress — no fantasy faces, card-frame chrome, or mana-symbol shapes. Fantasy lives in the art; the chrome is a modern product.
- Register: slick, tight, game-adjacent (Arena/Untapped premium feel), never a debug dashboard.
- Modern sans, weight-based hierarchy, `font-variant-numeric: tabular-nums` on all counts/prices.
- Every text token ≥4.5:1 on every permitted surface (tables below); accent ≥3:1 on base surfaces for non-text UI; `--focus-ring` defined per theme (= accent-bright).
- WUBRG + gold + colorless data colors (`--mana-*`) for curve bars and pips only — **data colors never appear in chrome**.

## Shared scaffold
- Surface ramp of 4: `--surface-well` (inset) → `--surface-base` (canvas) → `--surface-panel` (raised) → `--surface-overlay` (top row), plus `--scrim`.
- Spacing: 4 / 8 / 12 / 16 / 24 / 32 / 48 (`--space-1..7`).
- Type roles: display / heading / body / body-strong / label / micro / numeric (`--type-*`, `--tracking-*`). Labels and micro are uppercase with tracking in every theme.
- Motion: `--dur-1..4` + `--ease-out/glide/snap`, values themed.

---

## 01 · Gilt Gallery (`data-theme="gilt"`)
Warm gold on warm near-black grays — the museum after hours, brass picture lights on dark walls. Evolves the front-runner: the gold is reserved and jewelry-like, never UI-yellow; warmth in the grays keeps card art skin tones and golds glowing. **Accent means live agent attention only** — a gold hairline or chip marks what the agent is looking at right now.

- Surfaces: `#121010 / #191616 / #221e1c / #2c2723` · scrim `rgba(10,8,7,.72)` · borders `#383028`, `#4a4038`
- Text: `#f2ece2 / #c4bbac / #9d9584` · inverse `#171310`
- Accent: base `#d4a94f` · bright `#eccb7a` · dim `#8a6f3a` (non-text) · glow `rgba(212,169,79,.18)`
- Semantic: `#86c98b / #e07862 / #ec9548` · Data: W `#e6dcbf` U `#6aa3e0` B `#a08cb8` R `#e2705a` G `#6fbf73` M `#cf9440` C `#a8a29a` (chrome gold is brighter/cooler than data-gold; they never co-occur in chrome)
- Type: **Schibsted Grotesk**. display 28/600/1.15/−0.01em · heading 18/600/1.3 · body 14/400/1.55 · body-strong 14/600 · label 11/500/0.06em caps · micro 10.5/500/0.05em caps · numeric 13/500 tnum
- Shape/space: radius 4/8/12/pill; density: gallery calm — generous outer margins, tight internal clusters.
- Elevation/motion: 1px warm hairline + one soft low shadow (`0 8px 24px rgba(0,0,0,.35)`) on overlay tier only. whisper 120ms / settle 220ms / drift 400ms / reveal 650ms, ease-out. Everything fades and settles; nothing bounces.

Contrast (token × surface: well / base / panel / overlay):
- primary 16.1 / 15.3 / 14.1 / 12.6 · secondary 10.0 / 9.5 / 8.7 / 7.8 · tertiary 6.4 / 6.1 / 5.6 / 5.0
- accent-as-text 8.7 / 8.2 / 7.6 / 6.7 · bright 12.1 / 11.5 / 10.5 / 9.4 · inverse-on-accent 8.2, on-bright 11.5
- positive 9.7+ · negative 6.4/6.0/5.5/5.0 · caution 8.1+ · accent-dim (non-text) 3.99 on well, 3.78 on base ✓ 3:1

## 02 · Voltglass — CHOSEN THEME (default, `:root`)
Arcane glass hybridized with neon drift: cool blue-violet translucency, one luminous periwinkle. Panels feel like smoked glass panes floating over a void; the accent glows rather than fills. Colder register flatters blue/black card art and night scenes.

- Surfaces: `#0d0f1a / #12141f / #191c2b / #222639` · scrim `rgba(8,9,18,.75)` · borders `#2c3048`, `#3d4266`
- Text: `#e9ebf5 / #b3b8cf / #8b91ad` · inverse `#10121c`
- Accent: base `#8b93ff` · bright `#b3baff` · dim `#575fbe` (non-text) · glow `rgba(139,147,255,.22)`
- Semantic: `#5fd4a0 / #ff7a86 / #ffc266` · Data: W `#e8e6d6` U `#5cb2f0` B `#ab93cf` R `#f0716b` G `#5ec98a` M `#e0b95e` C `#9aa0b5`
- Type: **Space Grotesk**. display 30/500/1.1/−0.02em · heading 17/500/1.3 · body 14/400/1.5 · body-strong 14/700 · label 11/500/0.1em caps · micro 10/400/0.08em caps · numeric 13/500 tnum
- Shape/space: radius 6/10/16/pill; density: airy — panels float with visible void between them.
- Elevation/motion: translucency + backdrop-blur(16px) on overlay tier, accent glow rim (`0 0 0 1px rgba(139,147,255,.14)`) + deep shadow. Accent = agent's live focus; glow intensity may breathe on active rows. pulse 100ms / glide 240ms / bloom 480ms / aurora 900ms, ease-glide.

Contrast (well / base / panel / overlay):
- primary 16.1 / 15.4 / 14.2 / 12.6 · secondary 9.7 / 9.3 / 8.6 / 7.6 · tertiary 6.1 / 5.9 / 5.4 / 4.8
- accent-as-text 7.0 / 6.7 / 6.2 / 5.5 · bright 10.4 / 9.9 / 9.2 / 8.1 · inverse-on-accent 6.7, on-bright 9.9
- positive 10.4+ · negative 7.6+ · caution 12.0+ · accent-dim (non-text) 3.4 on base ✓

## 03 · Graphite Gallery (`data-theme="graphite"`)
Achromatic monochrome: pure neutral grays, accent is white itself. Mana colors become the only color on screen — every pip and curve bar sings against zero-chroma chrome. The most severe and most gallery-like option; risk is coldness, reward is total art focus.

- Surfaces: `#101010 / #161616 / #1e1e1e / #282828` · scrim `rgba(0,0,0,.7)` · borders `#333333`, `#444444`
- Text: `#f0f0f0 / #bdbdbd / #949494` · inverse `#111111`
- Accent: base `#f5f5f5` · bright `#ffffff` · dim `#8c8c8c` · glow `rgba(255,255,255,.12)` — "accent" = full-white emphasis; agent attention is marked by brightness, not hue.
- Semantic (kept low-chroma): `#8fc9a0 / #d98c8c / #d9c08c` · Data: W `#e9e2c8` U `#5da4e6` B `#a98fd1` R `#e0685c` G `#63b56f` M `#d4aa4e` C `#a3a3a3`
- Type: **Archivo**. display 26/700/1.1/−0.015em · heading 16/700/1.3 · body 13.5/400/1.5 · body-strong 13.5/600 · label 11/600/0.08em caps · micro 10/500/0.06em caps · numeric 13/500 tnum
- Shape/space: radius 2/4/6/pill — near-square; density: tight, columnar, print-catalog.
- Elevation/motion: **no shadows, no glow** — layers separate by tonal step + hairline only. snap 80ms / step 160ms / fade 320ms (no fourth duration; nothing lingers), ease-snap.

Contrast (well / base / panel / overlay):
- primary 16.7 / 15.9 / 14.6 / 12.9 · secondary 10.1 / 9.6 / 8.9 / 7.9 · tertiary 6.3 / 6.0 / 5.5 / 4.9
- accent-as-text 17.5+ · bright 19.0+ · inverse-on-accent 16.6, on-bright 18.1 · dim 5.4 on base ✓
- positive 10.0+ · negative 7.3+ · caution 10.8+

## 04 · Verdigris Table (`data-theme="verdigris"`)
Green-black surfaces with copper — the tournament table after hours: dark felt, warm metal fittings. The green cast is felt more than seen; copper reads craftsmanlike rather than techy. Warmest personality of the five; friendly without losing edge.

- Surfaces: `#0e1310 / #131a16 / #1a231e / #243029` · scrim `rgba(7,10,8,.72)` · borders `#2e3c34`, `#3f5146`
- Text: `#eaf0ea / #b7c4ba / #8fa094` · inverse `#0f1512`
- Accent: base `#d08a5a` · bright `#e8ab7e` · dim `#8a5a38` (non-text) · glow `rgba(208,138,90,.2)`
- Semantic: `#6cc98f / #e6796b / #e0b45c` · Data: W `#e4dcc2` U `#62a8de` B `#a693c4` R `#e06e5c` G `#71cc7e` (brightened to pop on green surfaces) M `#d6ae56` C `#a2aaa2`
- Type: **Manrope**. display 28/700/1.2/−0.01em · heading 17/700/1.35 · body 14/400/1.6 · body-strong 14/700 · label 11.5/600/0.04em caps · micro 10.5/500/0.04em caps · numeric 13/600 tnum
- Shape/space: radius 6/10/14/pill; density: comfortable — roomier line heights, softer clusters.
- Elevation/motion: soft ambient shadow (`0 6px 20px rgba(0,0,0,.4)`) + **copper hairline appears only on the row the agent is acting on**. deal 140ms / slide 260ms / settle 420ms / dwell 700ms, ease-out.

Contrast (well / base / panel / overlay):
- primary 16.2 / 15.3 / 13.9 / 11.9 · secondary 10.4 / 9.8 / 8.9 / 7.6 · tertiary 6.8 / 6.4 / 5.9 / 5.0
- accent-as-text 6.7 / 6.3 / 5.7 / 4.9 · bright 9.4 / 8.9 / 8.1 / 6.9 · inverse-on-accent 6.3, on-bright 8.9
- positive 9.3+ · negative 6.5/6.2/5.6/4.8 · caution 9.7+ · accent-dim (non-text) 3.0 on base ✓

## 05 · Ink & Ember (`data-theme="ink"`)
True-black editorial: paper-white type on absolute black, one ember of crimson used almost never. Reads like a beautifully set night-mode magazine about the deck. Sharpest corners, biggest type jumps, motion as cuts and fades — the print register of the five.

- Surfaces: `#000000 / #0a0a0a / #141414 / #1f1f1f` · scrim `rgba(0,0,0,.8)` · borders `#2b2b2b`, `#3d3d3d`
- Text: `#f5f2ee / #c2beb8 / #96928c` · inverse `#0a0a0a`
- Accent: base `#e25852` · bright `#ff7a6e` · dim `#b23f38` (non-text) · glow `rgba(226,88,82,.16)` — crimson is rationed: one live-attention marker at a time, never two.
- Semantic: `#79c791 / #ff9587 / #e6b95c` (negative is a lighter salmon, deliberately distinct from accent crimson) · Data: W `#ece3c6` U `#66a9e8` B `#ad94d6` R `#e5705f` M `#d8b056` G `#6cc178` C `#a6a29c`
- Type: **Instrument Sans**. display 34/700/1.05/−0.02em · heading 19/700/1.25 · body 14/400/1.55 · body-strong 14/700 · label 11/500/0.12em caps · micro 10/400/0.06em caps · numeric 13/500 tnum
- Shape/space: radius 0/2/4/pill — print-sharp; density: editorial columns, strong vertical rhythm.
- Elevation/motion: **1px rules only** — no shadows, no glow fills; layers separate by tone + rule. cut 0ms / beat 140ms / turn 280ms (fades and instant cuts; nothing eases longer than 280ms), ease-snap.

Contrast (well / base / panel / overlay):
- primary 18.8 / 17.7 / 16.5 / 14.8 · secondary 11.4 / 10.7 / 10.0 / 8.9 · tertiary 6.8 / 6.4 / 6.0 / 5.3
- accent-as-text 5.8 / 5.4 / 5.1 / 4.5 · bright 8.3 / 7.8 / 7.3 / 6.5 · inverse-on-accent 5.4, on-bright 7.8
- positive 10.4+ · negative 9.9+ · caution 11.5+ · accent-dim (non-text) 3.5 on base ✓

All ratios computed programmatically (WCAG relative luminance). Every text token clears 4.5:1 on all four surfaces; every accent-dim clears 3:1 on base surfaces and is restricted to non-text UI.

## Content fundamentals
No product copy exists yet. Provisional voice (to confirm): terse and declarative — the agent narrates, the panel labels. Sentence case everywhere except LABEL/MICRO tiers (uppercase, tracked). No emoji, no exclamation points. Numbers are facts: tabular, right-aligned. Second person absent — the panel describes the deck, not the user ("4 copies exceeds curve target", not "You have too many").

## Iconography
No icon assets provided. When screens are built: a single stroke-based CDN set (Lucide, 1.5px stroke) sized to the label tier, colored `--text-secondary`, accent only under agent attention. No emoji, no filled/duotone mixing. **Flagged: this is a substitution proposal, not a sourced asset.**

## Index
- `styles.css` — global entry (imports everything below)
- `tokens/theme-*.css` — Voltglass is the `:root` default (chosen); gilt/graphite/verdigris/ink kept as scoped candidates
- `tokens/typography.css`, `tokens/motion.css` — role scaffolds + per-theme overrides
- `tokens/fonts.css` — Google Fonts CDN imports (no binaries — flagged)
- `guidelines/themes/*.html` — swatch boards (Design System tab, group "Themes")
- `thumbnail.html`, `SKILL.md`
- `components/core/` — Panel, Badge, StatChip, AgentStatus
- `components/data/` — ManaPip, ManaCost, ManaCurve, DeckRow, CardTile
- `components/agent/` — SuggestionCard
- No UI kit screens, assets, or logo yet.

## Intentional additions
No source defined a component inventory (from-scratch run), so the set above was authored to the product's read-only needs: containers, agent presence, and deck-data display. No form controls exist on purpose — the agent drives, the app shows. ManaPip is a plain colored dot, deliberately not a mana-symbol shape.
