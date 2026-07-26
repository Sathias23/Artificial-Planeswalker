---
name: Artificial-Planeswalker Companion
description: 'Dark-only, card-art-forward visual identity for the companion app — Voltglass: cool blue-violet smoked glass with one luminous periwinkle accent, game-adjacent, never imitative of WotC trade dress.'
status: approved
updated: 2026-07-25
theme: voltglass
sources:
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/addendum.md
  - EXPERIENCE.md (peer — behavior contract)
  - imports/claude-design/ (design as-built, 2026-07-25)
composition-reference: imports/claude-design/Planeswalker Companion.dc.html
colors:
  # Dark mode only. Voltglass — cool blue-violet surfaces, translucent panes over a void.
  # Token names match the shipped CSS custom properties exactly (tokens/theme-voltglass.css).
  surface-well: '#0D0F1A'
  surface-base: '#12141F'
  surface-panel: '#191C2B'
  surface-overlay: '#222639'
  scrim: 'rgba(8,9,18,0.75)'
  border-hairline: '#2C3048'
  border-strong: '#3D4266'
  text-primary: '#E9EBF5'
  text-secondary: '#B3B8CF'
  text-tertiary: '#8B91AD'
  text-inverse: '#10121C'
  accent: '#8B93FF'
  accent-bright: '#B3BAFF'
  accent-dim: '#575FBE'
  accent-glow: 'rgba(139,147,255,0.22)'
  focus-ring: '#B3BAFF'
  positive: '#5FD4A0'
  negative: '#FF7A86'
  caution: '#FFC266'
  # WUBRG data colors — curve bars, mana pips, color-identity dots ONLY. Never chrome.
  mana-w: '#E8E6D6'
  mana-u: '#5CB2F0'
  mana-b: '#AB93CF'
  mana-r: '#F0716B'
  mana-g: '#5EC98A'
  mana-gold: '#E0B95E'
  mana-colorless: '#9AA0B5'
typography:
  # Space Grotesk. One family; hierarchy by weight and size.
  display:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 30px
    fontWeight: '500'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  heading:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 17px
    fontWeight: '500'
    lineHeight: '1.3'
  body:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  body-strong:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 14px
    fontWeight: '700'
    lineHeight: '1.5'
  label:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 11px
    fontWeight: '500'
    lineHeight: '1.3'
    letterSpacing: 0.1em
    textTransform: uppercase
  micro:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 10px
    fontWeight: '400'
    lineHeight: '1.3'
    letterSpacing: 0.08em
    textTransform: uppercase
  numeric:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.4'
    fontVariantNumeric: tabular-nums
    numeric-features: 'font-variant-numeric: tabular-nums'
rounded:
  sm: 6px
  md: 10px
  lg: 16px
  pill: 999px
  card: '4.75% / 3.4%'
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 24px
  '6': 32px
  '7': 48px
  gutter: 32px
  panel-gap: 24px
components:
  motion:
    pulse: 100ms
    glide: 240ms
    bloom: 480ms
    aurora: 900ms
    ease-out: 'cubic-bezier(0.25,0.1,0.25,1)'
    ease-glide: 'cubic-bezier(0.4,0,0.2,1)'
    ease-snap: 'cubic-bezier(0.2,0,0,1)'
  focus-ring:
    color: '{colors.focus-ring}'
    width: 2px
    offset: 2px
  elevation:
    shadow-raise: '0 0 0 1px rgba(139,147,255,0.14), 0 12px 32px rgba(0,0,0,0.5)'
    shadow-rest: '0 12px 32px rgba(0,0,0,0.5)'
    glow: '0 0 16px {colors.accent-glow}'
  panel:
    background: '{colors.surface-panel}'
    background-overlay: '{colors.surface-overlay}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.lg}'
    header-padding: '10px 14px'
    body-padding: '12px 14px'
  badge:
    radius: '{rounded.pill}'
    padding: '2px 9px'
    type: '{typography.label}'
  stat-chip:
    background: '{colors.surface-well}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.md}'
    value-size: 17px
  card-tile:
    radius: '{rounded.card}'
    aspect: '63 / 88'
    shadow: '{components.elevation.shadow-rest}'
    live-ring: '0 0 0 1px {colors.accent}, 0 0 20px {colors.accent-glow}'
    focus-ring-over-art: '0 0 0 2px {colors.focus-ring}, 0 0 0 4px {colors.surface-base}'
    hover-scale: '1.06'
    transition: '{components.motion.glide} {components.motion.ease-glide}'
  dfc-flip:
    background: '{colors.scrim}'
    backdrop: 'blur(6px)'
    border: '1px solid {colors.border-strong}'
    foreground: '{colors.text-primary}'
    hover-foreground: '{colors.accent-bright}'
    radius: '{rounded.pill}'
    size: 28px
    hit-area: 32px
    rest-opacity: '0.65'
    flip: '{components.motion.glide} {components.motion.ease-glide}'
  quantity-badge:
    background: '{colors.scrim}'
    foreground: '{colors.text-primary}'
    border: '1px solid {colors.border-strong}'
    radius: '{rounded.pill}'
    backdrop: 'blur(6px)'
  deck-row:
    columns: '34px 1fr auto 64px'
    radius: '{rounded.sm}'
    live-background: '{colors.accent-glow}'
    live-rule: 'inset 2px 0 0 {colors.accent}'
  group-header:
    type: '{typography.label}'
    foreground: '{colors.text-secondary}'
    rule: '1px solid {colors.border-hairline}'
  curve-bar:
    track: '{colors.surface-well}'
    fill: '{colors.border-strong}'
    radius: '{rounded.sm}'
    segment-hairline: '1px {colors.surface-well}'
  color-bar:
    track: '{colors.surface-well}'
    height: 14px
    radius: '{rounded.pill}'
  card-detail:
    background: '{colors.surface-overlay}'
    radius: '{rounded.lg}'
    art-radius: '{rounded.card}'
    pinned-ring: '0 0 0 1px {colors.accent-dim}'
  legality-row:
    rule: '1px solid {colors.border-hairline}'
    padding: '9px 2px'
  nav-pill:
    background: '{colors.surface-panel}'
    border: '1px solid {colors.border-strong}'
    radius: '{rounded.pill}'
    padding: '7px 14px'
    foreground: '{colors.text-secondary}'
    hover-border: '{colors.accent-dim}'
    hover-foreground: '{colors.accent-bright}'
    hover-glow: '{components.elevation.glow}'
    unread-dot: '{colors.accent}'
  agent-view:
    scrim: '{colors.scrim}'
    backdrop: 'blur(16px)'
    background: '{colors.surface-panel}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.lg}'
    shadow: '{components.elevation.shadow-raise}'
    inset: '{spacing.6}'
    enter: '{components.motion.bloom} {components.motion.ease-glide}'
  swap-row:
    background: '{colors.surface-overlay}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.md}'
    out-tint: '{colors.negative}'
    in-tint: '{colors.positive}'
    arrow: '{colors.accent}'
  tier-row:
    background: '{colors.surface-overlay}'
    chip-background: '{colors.surface-well}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.md}'
    chip-width: 132px
    letter-size: 44px
    letter-weight: '500'
  suggestion-row:
    background: '{colors.surface-overlay}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.md}'
    thumb-radius: '{rounded.card}'
  connection-pill:
    background: '{colors.surface-panel}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.pill}'
    dot-size: 8px
  state-panel:
    background: '{colors.surface-panel}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.lg}'
    max-width: 480px
  card-placeholder:
    background: '{colors.surface-overlay}'
    border: '1px solid {colors.border-strong}'
    radius: '{rounded.card}'
  skip-link:
    background: '{colors.surface-panel}'
    foreground: '{colors.accent}'
    border: '1px solid {colors.accent-dim}'
    radius: '{rounded.sm}'
  footer-attribution:
    foreground: '{colors.text-secondary}'
    background: '{colors.surface-base}'
    border-top: '1px solid {colors.border-hairline}'
    type: '{typography.micro}'
---

## Brand & Style

The companion app is **read-only glass beside a terminal**: a dark, quiet pane whose only job is to make card art look magnificent while an agent does the talking. The register is *game-adjacent premium* — the confident, tight feel of Arena or Untapped.gg — achieved entirely through our own vocabulary.

The identity is **Voltglass**: cool blue-violet surfaces that read as smoked glass panes floating over a void, with one luminous periwinkle accent that *glows rather than fills*. The colder register deliberately flatters the blue, black and night-scene card art that dominates the format, and the low-chroma surfaces let the WUBRG data colors and the art itself carry every saturated note on screen.

Two hard rules define the aesthetic:

1. **Card art is the fantasy element. Chrome is not.** Every fantasy note — serif lettering, ornament, parchment, frames — is banned from the UI. The interface is a dim gallery wall; the cards are the paintings.
2. **Never imitative of WotC trade dress.** No Beleren-like typefaces, no reproduction of MTG card-frame chrome, no planeswalker-symbol lookalikes, no mana-symbol-shaped UI controls. `ManaPip` is a plain colored dot, deliberately. Evoke the *feeling* of Arena; copy nothing from it.

Everything else follows from "slick": airy panel separation, weight-based type hierarchy, motion that glides rather than bounces, and an accent used sparingly enough that it always means something.

> **History.** This file previously specified a warm-gold-on-warm-near-black identity. That direction was superseded on 2026-07-25 by the Voltglass system developed directly in Claude Design. Gilt Gallery — the nearest warm-gold survivor — is retained as `[data-theme="gilt"]` alongside Graphite, Verdigris and Ink, but it is *not* the old palette; every hex differs. Voltglass is the shipping theme and `:root`.

## Colors

Surfaces are cool blue-violet, low-chroma. The ramp is shallow because card art provides all the visual richness; chrome layers separate by tone, not by color.

- **Surface ramp** — `{colors.surface-well}` (inset: curve track, color-bar track, stat chips, tier chips) → `{colors.surface-base}` (page canvas) → `{colors.surface-panel}` (panels, agent-view shell) → `{colors.surface-overlay}` (rows and cards *within* panels). One step per layer; never skip two.
- **Periwinkle accent** — `{colors.accent}` is the only chromatic chrome color. It marks *live agent attention*: the card currently under inspection, an agent-view header's kind label, a nav pill with an unread push, focus rings, the primary line of a state panel's next action. `{colors.accent-bright}` for hover/active and the focus ring; `{colors.accent-dim}` for borders and inactive accent; `{colors.accent-glow}` only inside soft glows and live-row tints. **The accent glows; it never fills.** The largest permitted accent area is a tier letter.
- **Text** — `{colors.text-primary}` for names and headlines, `{colors.text-secondary}` for body copy, reasons, rationale and metadata, `{colors.text-tertiary}` for de-emphasized numerics, axis labels, captions and timestamps. `{colors.text-inverse}` on accent and mana fills. All three tiers clear 4.5:1 on all four surfaces — see the table below — so tier choice is a matter of hierarchy, not of legality.
- **Semantic** — `{colors.positive}` / `{colors.negative}` / `{colors.caution}` appear in badges, swap in/out labels, and the connection pill. No red error fills, no toast color-coding: system states get calm panels, not alarm colors.
- **WUBRG data colors** (`mana-w` … `mana-colorless`) are **data ink only**: mana pips, color-distribution bars, color-identity dots. They never color buttons, borders, backgrounds, or any interactive chrome — *including* curve-bar fills, which use `{components.curve-bar.fill}` (a chrome token) unless the bar is genuinely stacked by color.

### Contrast (computed WCAG 2.x relative luminance, not claimed)

| Token | on well | on base | on panel | on overlay |
|---|---|---|---|---|
| `text-primary` | 15.9 | 15.4 | 14.2 | 12.6 |
| `text-secondary` | 9.6 | 9.3 | 8.6 | 7.6 |
| `text-tertiary` | 6.1 | 5.9 | 5.4 | **4.8** |
| `accent` (as text) | 7.0 | 6.7 | 6.2 | 5.5 |
| `accent-bright` | 10.3 | 9.9 | 9.2 | 8.1 |
| `positive` | 10.3 | 10.0 | 9.2 | 8.1 |
| `negative` | 7.6 | 7.3 | 6.7 | 6.0 |
| `caution` | 11.9 | 11.5 | 10.6 | 9.4 |
| `accent-dim` (non-text only) | 3.41 | 3.30 | 3.05 | **2.70 ✗** |

`text-inverse` on `accent` = 6.9; on `accent-bright` = 10.1; on `positive` / `caution` = 8.3 / 9.7.

**Every text token clears 4.5:1 on every surface.** Two consequences are load-bearing:

- **`text-tertiary` on `surface-overlay` is 4.8:1** — passing, but it is the tightest pair in the system and has no headroom. Do not darken it, and do not introduce a fifth surface above `surface-overlay`.
- **`accent-dim` fails the 3:1 non-text floor on `surface-overlay` (2.70:1).** It is permitted as a border or indicator on `well`, `base` and `panel` only. Where a live/selected marker sits on an `overlay` surface — suggestion rows, swap rows, tier rows — use `{colors.accent}` (5.5:1) instead. The design-system readme's blanket claim that accent-dim "clears 3:1 on base surfaces" is true only for the lower three.

## Typography

One family: **Space Grotesk** (fallback `system-ui, sans-serif`). Hierarchy comes from weight and size, never from a second family. Roles:

- `{typography.display}` — the deck name. The only 30px moment on screen.
- `{typography.heading}` — panel titles that carry a real name (card detail name, agent-view title, group titles).
- `{typography.body}` / `{typography.body-strong}` — reasons, rationale, oracle text, state-panel copy, group descriptions.
- `{typography.label}` — panel titles, type-group headers, nav pills, badges. Uppercase, tracked 0.1em. Keep label strings short: at 11px with that tracking, a long title is effortful to read. Panel titles that need to carry counts should put the count in `{typography.numeric}` beside the label, not inside it.
- `{typography.micro}` — kicker labels, stat-chip labels, timestamps, footer attribution. Uppercase, tracked 0.08em.
- `{typography.numeric}` — every count, quantity, price, and axis value. **Always tabular.**

Tabular numerals are non-negotiable — columns of prices and live-updating counts must not jitter. The CSS `font` shorthand cannot carry `font-variant-numeric`, so `{typography.numeric}` defines the feature separately as `{typography.numeric.numeric-features}`, and the two are always applied together. Never set `font: var(--type-numeric)` alone.

No italics except quoted oracle flavor text (which arrives styled from card data). No weight below 400 on dark surfaces.

**Font delivery:** the family is **self-hosted**, bundled with the backend's static assets. No CDN import. The app is served from `localhost` and must render identically with no network — a webfont that falls back to `system-ui` offline is a visible regression in the product's core posture.

## Layout & Spacing

Scale: 4 / 8 / 12 / 16 / 24 / 32 / 48. `{spacing.gutter}` (32px) frames the window; `{spacing.panel-gap}` (24px) separates panels; `{spacing.5}` (24px) is the card-grid gap; `{spacing.2}`–`{spacing.3}` for internal clusters. **Every value in the UI comes from this scale** — the mock's 18/14/9/7px one-offs are drift, not spec.

The screen is a **two-column composition** under a full-width header:

- **Header** — product kicker + deck name (left), format/size badges, and the agent-view nav (right).
- **Left column (fluid)** — the card-art grid panel, with the mana-curve and color-distribution panels below it as a 1:1 pair.
- **Right column (452px fixed)** — card detail, deck list, format check, stacked.
- **Footer** — attribution, full width, pinned to the window bottom.

Panels *float*: airy separation with visible canvas between them is the theme's density philosophy, not spare padding. The card grid is `repeat(auto-fill, minmax(176px, 1fr))`; tiles hold a fixed 63:88 aspect and reflow. The app targets a window from ~1100px (below which the right column drops beneath the left) up to ~2560px (half an ultrawide). Design reference width is 1720px.

Agent views take the whole window as a scrim-backed overlay inset by `{spacing.6}`.

## Elevation & Depth

Three devices:

- **Translucency + blur** — the agent-view scrim (`{components.agent-view.backdrop}`) and the quantity badge (`blur(6px)` over `{colors.scrim}`). This is the theme's signature: layers read as glass, not as paper.
- **Deep shadow** — `{components.elevation.shadow-rest}` on card tiles and panels at rest; `{components.elevation.shadow-raise}` (shadow **plus** a 1px accent-tinted rim) on the agent-view shell and on anything carrying live agent attention. Both are tokens; **neither is ever written as a literal**. Themes that declare themselves shadowless (`graphite`, `ink`) set both to `none`, so a component that hard-codes a shadow breaks them — and, because `shadow-raise` is the *live* state, a component that hard-codes the *rest* shadow inverts the hierarchy under those themes.
- **Accent glow** — `{components.elevation.glow}` marks *the thing the agent just did or the thing you are inspecting*: the live card tile's ring, a nav pill with an unread push, the live deck row's tint. Glows are moments, not steady states; they fade over `{components.motion.glide}`.

Tonal layering (the surface ramp) does the everyday hierarchy work. Borders are hairline and only where tone alone is ambiguous.

## Shapes

`{rounded.sm}` (6px) small chips and rows; `{rounded.md}` (10px) inner cards and rows; `{rounded.lg}` (16px) panels and the agent-view shell; `{rounded.pill}` badges, nav pills, quantity badges, the connection pill.

**Card imagery keeps printed-card geometry.** Tiles, thumbnails, placeholders and the detail art all use `{rounded.card}` (`4.75% / 3.4%` — the real card corner ratio) at a `{components.card-tile.aspect}` of 63:88, so faces clip cleanly at any tile width and `png` faces with transparent corners sit flush. Nothing else in the UI borrows the card radius, and cards never borrow a chrome radius — **cards must be the only card-shaped things on screen, and they must actually be card-shaped.** (The mock uses `radius-md` on tiles and two different aspect ratios, 1:1.400 for tiles and 1:1.393 for the detail art; both are corrected here.)

## Components

→ **Composition reference:** `imports/claude-design/Planeswalker Companion.dc.html` demonstrates Panel, Badge, StatChip, Card tile, Quantity badge, Mana curve, Color distribution, ManaPip/ManaCost, Deck row, Group header, Card detail panel, Format check, Agent view, Swap row, Tier row and Group section in composition. It does **not** demonstrate — and these are specified here without a visual precedent — DFC flip control, Suggestion row, Connection pill, State panel, Card placeholder, Skip link, or Footer attribution. Read the mock for arrangement and density; read this file for the rules, which correct it in several places (card geometry, tokenized shadows, `accent-dim` restrictions, spacing scale).

### Containers & chrome

- **Panel** — the universal container. `{components.panel.background}` (or `{components.panel.background-overlay}` at `level="overlay"`) inside `{components.panel.border}` at `{components.panel.radius}`. Optional header: title in `{typography.label}` `{colors.text-secondary}`, an optional count in `{typography.numeric}` `{colors.text-tertiary}`, badges right-aligned. `live` swaps the title to `{colors.accent}`, adds a 6px accent dot, and raises elevation to `{components.elevation.shadow-raise}`. Rest elevation is `{components.elevation.shadow-rest}` — **both via token**.
- **Badge** — pill, `{typography.label}`, 5 tones: neutral (`surface-overlay` / `text-secondary` / `border-strong`), accent, positive, negative, caution. Semantic tones tint background and border from their own semantic token — never from hard-coded RGB, which breaks every non-Voltglass theme.
- **StatChip** — label in `{typography.micro}` `{colors.text-tertiary}` over a 17px `{typography.numeric}` value in `{colors.text-primary}`, on `{components.stat-chip.background}`. Optional delta in `{typography.micro}`, tinted `{colors.positive}` / `{colors.negative}` by sign.
- **Agent views nav** (the nav pill) — the agent-view controls in the header, and the "Close · esc" control inside a view. `{components.nav-pill.padding}` at `{rounded.pill}`, `{typography.label}`. Hover/focus: border to `{components.nav-pill.hover-border}`, text to `{components.nav-pill.hover-foreground}`, plus `{components.nav-pill.hover-glow}`. A pill whose view has an unread push carries a `{components.nav-pill.unread-dot}` — the accent's meaning is "the agent put something here", so an unread push is exactly what it marks.
- **Skip link** — "Skip past the deck grid": visually hidden until it receives keyboard focus; on focus it appears at the window's top-left as a `{components.skip-link.radius}` chip on `{components.skip-link.background}` with `{components.skip-link.border}`, text in `{typography.body-strong}` `{components.skip-link.foreground}`, carrying the standard `{components.focus-ring}`. It exists because the card grid can be 100+ Tab stops sitting between the header nav and everything in the right column. Behavior in EXPERIENCE.md.
- **Footer attribution** — one quiet line, full width, `{components.footer-attribution.background}` above `{components.footer-attribution.border-top}`, `{typography.micro}` in `{components.footer-attribution.foreground}` (`text-secondary`, 9.3:1 — this text is legally load-bearing and gets a passing tier, not a muted one): "Card data and imagery courtesy of Scryfall. Unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy. Not approved/endorsed by Wizards." Links persistently underlined (identifiable at rest, not hover-only); hover brightens to `{colors.text-primary}`; each link's hit area ≥ 24px tall. Visible without scrolling, and never louder than this. **Required on every surface — this is a condition of public release, not a design choice.**

### Deck data

- **Card tile** — the grid unit. The card face *is* the tile: no frame, no title bar — chrome-free art at `{components.card-tile.radius}` and `{components.card-tile.aspect}`, with `{components.card-tile.shadow}`. Caption below in `{typography.label}` `{colors.text-secondary}`, single-line ellipsis. `live` (the card under inspection) adds `{components.card-tile.live-ring}`. Hover/focus: `{components.card-tile.hover-scale}` in place over `{components.card-tile.transition}`, raising z-index so neighbors slide under — restrained here because the grid sits beside a persistent detail panel that already does the "look closer" work. Because a tile's focus indicator sits over arbitrary card art rather than a known surface, tiles use `{components.card-tile.focus-ring-over-art}` — the focus ring plus a dark outer edge — so the indicator is visible against a light or a dark painting alike. `live` uses `{colors.accent}`, not `accent-dim`, because tiles also appear on `surface-overlay` inside agent views where `accent-dim` fails the 3:1 floor.
- **DFC flip control** — rendered only on double-faced cards. A circular `{components.dfc-flip.radius}` button at `{components.dfc-flip.size}` with a `{components.dfc-flip.hit-area}` hit box, pinned to the tile's **top-left** inside `{spacing.2}` — the top-right is occupied by the quantity badge, and the two must never collide. It shares the badge's material so the pair reads as one family: `{components.dfc-flip.background}` with `{components.dfc-flip.backdrop}` and `{components.dfc-flip.border}`, carrying a stroke-based two-arrow rotate glyph in `{components.dfc-flip.foreground}` — a plain UI glyph, never anything that could read as a mana or set symbol. Opacity `{components.dfc-flip.rest-opacity}` at rest so it never competes with the art, 1.0 when its tile is hovered or focused; hovering the control itself tints the glyph `{components.dfc-flip.hover-foreground}`. It is visibly a control, not part of the card, so flip-versus-inspect is unambiguous. Flip animation: 3D Y-rotation over `{components.dfc-flip.flip}`. The card detail panel gets its own copy of the control at the same spec, pinned to its art's top-left.
- **Quantity badge** — `{typography.numeric}` count ("×4") pinned top-right inside `{spacing.2}` of the tile, on `{components.quantity-badge.background}` with `{components.quantity-badge.backdrop}` and `{components.quantity-badge.border}`. When a quantity changes on refetch it flashes the accent glow once — garnish; the accessible signal is the group-header count plus the live-region announcement.
- **Mana curve** — bars per mana value on a `{components.curve-bar.track}` well at `{components.curve-bar.radius}`. Buckets are **1 … 7+**; lands are excluded; DFCs bucket by front face. Counts above bars in `{typography.numeric}` `{colors.text-tertiary}`; axis labels in `{typography.micro}`. Bars fill with `{components.curve-bar.fill}` — a *chrome* token. If bars are stacked by color, segments run in fixed order W·U·B·R·G·gold·colorless separated by `{components.curve-bar.segment-hairline}`, multicolor cards contribute one `mana-gold` segment, and the segments are `aria-hidden` decoration: the accessible data is the per-bar name and the visually-hidden table. Never fill an unstacked bar with a `mana-*` token.
- **Color distribution** — a single `{components.color-bar.height}` bar at `{rounded.pill}` on `{components.color-bar.track}`, segmented by `mana-*` proportional to pip count, with a legend of `ManaPip` + count + percentage below. This is data ink used correctly.
- **ManaPip / ManaCost** — a plain circle filled with the `mana-*` token, `{colors.text-inverse}` numeral inside for generic costs. Deliberately not a mana-symbol shape. `ManaCost` parses full Scryfall cost strings: braces, hybrid (`{2/R}`, `{W/U}`) as a split or dual-tinted pip, Phyrexian, and `{X}` — never silently dropping a symbol it doesn't recognize.
- **Deck row** — the text-list unit. `{components.deck-row.columns}`: quantity in `{typography.numeric}` `{colors.text-tertiary}`, name in `{typography.body}` (`body-strong` `{colors.text-primary}` when live), mana cost as pips, price right-aligned in `{typography.numeric}`. `live` tints the row `{components.deck-row.live-background}` with `{components.deck-row.live-rule}`.
- **Group header** — type-group dividers ("CREATURES") in `{typography.label}` `{components.group-header.foreground}` with the count right-aligned in `{typography.numeric}` `{colors.text-tertiary}`, over `{components.group-header.rule}`.
- **Card detail panel** — the persistent right-column panel at `level="overlay"`. Full card face at `{components.card-detail.art-radius}` on `{components.card-detail.background}`, then name in `{typography.heading}` with mana cost right-aligned, type line in `{typography.body}` `{colors.text-secondary}` with price right-aligned in `{typography.numeric}`, and note/oracle text in `{typography.body}` `{colors.text-secondary}`. When pinned (see EXPERIENCE.md) it carries `{components.card-detail.pinned-ring}`.
- **Format check** (the legality row) — label in `{typography.body}` `{colors.text-secondary}`, `Badge` right-aligned, over `{components.legality-row.rule}`.
- **Card placeholder** (named + unknown-card variants) — a deliberately designed stand-in, never a broken-image glyph: card-shaped at `{components.card-placeholder.radius}` on `{components.card-placeholder.background}` with `{components.card-placeholder.border}`, rendering in chrome type — name centered in `{typography.body-strong}`, mana cost as pips above, type line in `{typography.micro}` `{colors.text-secondary}`. Unknown-card variant: name slot reads "Unknown card" with the truncated ID in `{colors.text-secondary}` (the ID is the only identifying information — load-bearing, so never a de-emphasized tier). Image-loading wells use the same shape on `{colors.surface-well}` with no text.

### Agent views

- **Agent view** (the shell) — full-window overlay: `{components.agent-view.scrim}` with `{components.agent-view.backdrop}`, inset `{components.agent-view.inset}`, containing a `{components.agent-view.background}` shell at `{components.agent-view.radius}` with `{components.agent-view.shadow}`. Header row: "AGENT VIEW" kicker in `{typography.micro}` `{colors.accent}`, title in `{typography.heading}`, a summary count in `{typography.body}` `{colors.text-tertiary}`, and a "Close · esc" nav pill right-aligned. Enters over `{components.agent-view.enter}` as a fade + 8px rise. Body scrolls.
- **Swap row** — out-card and in-card tiles side by side joined by a `{components.swap-row.arrow}` glyph, on `{components.swap-row.background}` at `{components.swap-row.radius}`. "Out · N copies" in `{typography.micro}` `{components.swap-row.out-tint}` above the out tile; "In · N copies" in `{components.swap-row.in-tint}` above the in tile. Tints appear on the labels only — **never on the art**. Rationale in `{typography.body}` `{colors.text-secondary}` right of the pair, with `StatChip`s for price/curve/confidence beneath.
- **Tier row** — a `{components.tier-row.chip-width}` chip on `{components.tier-row.chip-background}` carrying the tier letter at `{components.tier-row.letter-size}` / `{components.tier-row.letter-weight}` with the tier name in `{typography.micro}` `{colors.text-tertiary}` beneath, then a note in `{typography.body}` `{colors.text-secondary}` and a thumbnail row. Tier letters use `accent-bright` (S) · `accent` (A) · `text-primary` (B) · `text-secondary` (C) · `text-tertiary` (D). At 44px the letters are large text, so all five clear the floor comfortably; the letter is also always accompanied by its name in text, so color is never the sole carrier of rank. Empty tiers are skipped, not rendered as empty shells.
- **Suggestion row** — card thumbnail at `{components.suggestion-row.thumb-radius}` (full row height — art-forward) left, then an action `Badge`, name in `{typography.body-strong}`, mana cost, optional confidence in `{typography.micro}` `{colors.text-tertiary}` right-aligned, and a one-line reason in `{typography.body}` `{colors.text-secondary}` beneath. `live` marks the row with `{colors.accent}` — **not `accent-dim`**, which fails 3:1 on this surface.
- **Group section** — title in `{typography.heading}` with card count in `{typography.numeric}` `{colors.text-tertiary}`, description in `{typography.body}` `{colors.text-secondary}` capped at ~900px measure, then a wrapped tile row.

### System presence & states

- **Connection pill** — bottom-left, `{components.connection-pill.radius}` on `{components.connection-pill.background}` with `{components.connection-pill.border}`: a `{components.connection-pill.dot-size}` dot (`{colors.positive}` live · `{colors.caution}` reconnecting · `{colors.negative}` backend gone — all **static**, no pulse) plus `{typography.micro}` text naming the state and the active deck name. The dot never carries the state alone. Quiet at rest; it never animates. *This replaces `AgentStatus`, whose `idle | thinking | streaming` vocabulary describes agent cognition the app has no signal for.*
- **State panel** — the shared shell for no-active-deck, database-not-initialized, database-updating and disconnected states: centered on `{components.state-panel.background}` at `{components.state-panel.radius}` with `{components.state-panel.border}`, max-width `{components.state-panel.max-width}`. Headline `{typography.heading}`, guidance `{typography.body}` `{colors.text-secondary}`, the concrete next action on its own line in `{typography.body-strong}` `{colors.accent}` (commands in a monospace-styled inline chip on `{colors.surface-well}`). No illustrations, no sad-face icons — calm text on a calm panel.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Let card art carry all color and fantasy; keep chrome cool-gray and quiet | Tint, overlay, gradient-fade, or watermark card art — art renders untouched, always |
| Use the accent for live agent attention, inspection, focus, and the next action | Use the accent as a large fill, decorative border, or steady-state chrome |
| Use WUBRG colors as data ink (pips, color bars, stacked curve segments) | Color any button, background, border — or an *unstacked* curve bar — with a `mana-*` token |
| One sans (Space Grotesk), hierarchy by weight; tabular numerals on every count | Beleren-like or any fantasy/serif display face; icon fonts styled as mana symbols |
| Self-host the font with the backend's static assets | Import webfonts from a CDN — the app must render identically offline |
| Every shadow and radius through a token | Hard-code a shadow or an RGB literal — it silently breaks the four non-Voltglass themes |
| `accent-dim` for borders on `well` / `base` / `panel` | `accent-dim` on `surface-overlay` (2.70:1 — use `accent`) |
| Card-radius (4.75%/3.4%) + 63:88 on every card face, thumbnail and placeholder | Card-shaped chrome, or chrome-shaped cards |
| Calm state panels with a concrete next action in `body-strong` accent | Error pages, red alert fills, toast storms, exclamation marks |
| Brief motion (100–480ms) that glides, always honoring `prefers-reduced-motion` | Looping ambient animation, pulsing dots, parallax, anything over `{components.motion.aurora}` |
| Every interactive element gets a real `<button>`/`<a>`, a ≥ 24×24px hit area, and a visible `{components.focus-ring}` | `<div onClick>`, hover-only affordances, or `outline: none` without a replacement |
| Route card images through the backend proxy with caching and a placeholder fallback | Hotlink `api.scryfall.com/cards/…?format=image` per tile per render |
