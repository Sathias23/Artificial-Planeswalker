# Claude Design handoff prompts — Artificial Planeswalker Companion

Assembled 2026-07-22 from the UX run at `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/`. Two prompts, run in sequence:

1. **Prompt 1 — Design system (theming).** Explores 5 candidate themes. Pick a winner.
2. **Prompt 2 — UI (hero screen).** Paste the winning design system into the marked slot; it renders the actual screen.

Save whatever Claude Design emits back into this run folder (e.g. `imports/claude-design/`) and the UX workflow will reconcile it against the spines.

---

## PROMPT 1 — Design system / theming

Create the **design system** for a desktop web app called the **Artificial Planeswalker Companion** — a dark, read-only visual panel for a Magic: The Gathering deckbuilding AI. Produce **5 distinct candidate themes**, each a complete visual personality (not a palette swap): differ on accent philosophy, surface temperature, type register, and depth/elevation language. No screen layouts yet — this is the theming layer only.

### Product context (one paragraph)

The user runs an AI deckbuilding agent in a terminal on one half of an ultrawide monitor; this app fills the other half in a browser. It is "read-only glass": the agent drives, the app shows. It renders a deck of Magic cards with full card art, plus panels of agent-pushed suggestions. The chrome's only job is to make card art look magnificent — a dim gallery wall around the paintings.

### Hard constraints (every theme must respect all of these)

1. **Dark mode only.** No light theme exists.
2. **Card art is the hero.** No large saturated fills, no busy patterns; chrome separates by tone, not color noise.
3. **Never imitative of Wizards of the Coast trade dress.** No Beleren-like fantasy typefaces, no MTG card-frame chrome, no planeswalker-symbol or mana-symbol-shaped elements. Fantasy lives in the card art only; the chrome is a modern product.
4. **"Slick" is the register**: tight, confident, game-adjacent — evoking the premium feel of MTG Arena or Untapped.gg, never a utilitarian dashboard. Acceptance bar: "looks like a deliberate product, not a debug dashboard."
5. **Type**: modern sans (Inter-class), weight-based hierarchy, no decorative faces. Tabular numerals for counts and prices.
6. **Accessibility floor**: every text token ≥ 4.5:1 contrast on every surface it is permitted on (state the computed ratios); focus ring color defined; the accent must read at 3:1 against base surfaces for non-text UI.
7. The five MTG mana colors (white/blue/black/red/green) will appear as **data colors** (curve bars, mana pips) — each theme must include a WUBRG data-color set that sits comfortably on its surfaces, plus a "multicolor/gold" and "colorless" value. Data colors never appear in chrome.

### Deliverables — for each of the 5 themes

- **Name + personality rationale** (2–3 sentences).
- **Color tokens** (hex): surface ramp of 4 (inset well → base canvas → raised panel → overlay row), scrim, 2 border weights, 3 text tiers + inverse, accent family (base / bright / dim / glow), positive / negative / caution, and the 7 WUBRG+gold+colorless data colors.
- **Type scale**: display / heading / body / body-strong / label / micro / numeric — size, weight, line height, letterspacing.
- **Shape & space**: corner radius scale, spacing scale, one-line density philosophy.
- **Elevation & motion language**: how layers separate (shadow? glow? hairline?), 3–4 named durations + easings, and what the accent color *means* (e.g. "accent marks live agent attention only").
- **Contrast table**: each text token × each surface it may sit on, with computed WCAG ratios.
- A small **swatch board** (HTML or image): the surface ramp, text tiers on each surface, accent states, data colors as a strip — enough to feel the theme without a screen.

### Reference points (beat or hybridize, don't repeat)

Already explored: warm gold on near-black warm grays (front-runner); cool blue-violet "arcane glass"; achromatic "graphite gallery" (mana colors as the only color); green-black + copper "copper table"; true-black "editorial ink" with rare crimson; violet "neon drift" with magenta→cyan gradient.

---

## PROMPT 2 — UI (hero screen)

Design the **hero screen** of the Artificial Planeswalker Companion at high fidelity, using the design system pasted below. The system is the law for color, type, shape, spacing, elevation, and motion — your job is composition, hierarchy, and component craft, not re-theming. If the screen exposes a gap in the system (a missing token or state), flag it explicitly rather than inventing silently.

### Design system

> **[PASTE THE WINNING THEME FROM PROMPT 1 HERE — tokens, type scale, elevation/motion language, contrast table]**

### Product context

The user runs an AI deckbuilding agent in a terminal on one half of an ultrawide monitor; this app fills the other half in a browser. It is "read-only glass": **the agent drives, the app shows.** The user's only clicks are to inspect — hover a card, open a detail view. Zero editing controls, no nav bar, no settings — a single focused surface whose only job is to make card art look magnificent.

### The screen (fixed composition — do not rearrange)

A browser viewport ~1260px wide, dark:

- **Deck view** (left ~60%): a Commander deck titled "Rhys Tokens" (Commander · 100 cards). Header row: deck name, format, a small Grid/List view toggle. Below: full card faces (real MTG card proportions, ~63:88 ratio, rounded corners) in a grid, grouped under type-group headers — "Commander (1)", "Creatures (26)", "Lands (36)" etc. A slim **mana curve** bar chart docked at the top edge (bars for mana costs 1–7+, each bar stacked by the system's WUBRG data colors, hairline gaps between segments). One card carries a small "×12" quantity badge (basic lands); singletons show no badge. One double-faced card shows a small circular flip control in its corner. One hovered card tile shows the hover state: slight in-place scale pop (~1.18×) with lift shadow.
- **Agent drawer** (right ~40%): slid in over the deck view, elevated per the system's elevation language, with a "just arrived" live-attention treatment on its leading edge. Header: "Suggestions · 14:02" with a close × (render the system's focus ring on it — the canonical focus-visible illustration). Six rows, each: small card thumbnail + card name + one-line reason ("Protects the whole board for one white mana...") + a small category chip ("Protection", "Draw"). One row is an "Unknown card" placeholder (no art available) — deliberate, not broken. At the drawer's foot: a **session history strip** of 4 small chips ("Suggestions 14:02", "Swaps 13:55"...), active one marked.
- **Connection pill** bottom-left: small pill, "Live · Rhys Tokens".
- **Footer**: one quiet line — "Card data and images © Scryfall. Magic: The Gathering is © Wizards of the Coast. Unofficial Fan Content per the Fan Content Policy." Links underlined, footer text must clear 4.5:1.

### Rules

1. Card art is the hero; chrome never competes. Use stylized gradient stand-ins for card art (real card images can't be embedded) — varied hues so the grid reads richly.
2. Never imitative of WotC trade dress (no fantasy typefaces, card-frame chrome, or mana-symbol-shaped controls).
3. Calm microcopy, second person, no exclamation marks, no emoji.
4. Motion is implied, not required: the drawer reads as freshly slid-in; nothing loops.

### Deliverables

The hero screen as a fully self-contained HTML/CSS mock (inline CSS, no external assets, no JS) — or your highest-fidelity native format. Plus a short list of any system gaps you hit (missing tokens, undefined states).
