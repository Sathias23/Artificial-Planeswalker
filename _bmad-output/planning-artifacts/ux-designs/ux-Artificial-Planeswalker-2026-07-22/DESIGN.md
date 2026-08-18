---
name: Artificial-Planeswalker Companion
description: 'Dark-only, card-art-forward visual identity for the companion app — Voltglass: cool blue-violet smoked glass with one luminous periwinkle accent, game-adjacent, never imitative of WotC trade dress.'
status: approved
updated: 2026-08-18
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
fonts:
  # The UI family is declared per-role above — every `typography.*.fontFamily` is the same
  # string, which is what "one family" means and what `--font-sans` is derived from.
  #
  # `mono` is NOT a type role and never carries hierarchy. It has exactly one job: the command
  # literals inside State panel copy (`initialize_database`, `artificial-planeswalker
  # companion`) — DATA the user is about to type into a terminal, never chrome and never
  # display type. A system stack, deliberately: no @font-face, no download, no new asset, so
  # the offline guarantee (NFR-06) and the one-@font-face rule are untouched.
  # Added by story c2-9 (Q2, Brad's ruling 2026-07-29) — the State panel spec below already
  # said "monospace-styled" and there was no legal way to spell it.
  # The branded names are QUOTED and the two generic keywords are BARE, and both halves are
  # measured, not stylistic: unquoted, stylelint's `value-keyword-case` demands `sfmono-regular`
  # / `menlo` / `consolas`, which name nothing; quoted, `monospace` would stop being the CSS
  # generic. The shipped token carries this string byte for byte.
  mono: "ui-monospace, 'SFMono-Regular', 'Menlo', 'Consolas', monospace"
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
    # AMENDED 2026-08-07 (story c4-12, Q13). These read `'10px 14px'` and `'12px 14px'`, transcribed
    # from the composition reference. **The Layout & Spacing section below bans `14` BY NAME** —
    # *"the mock's 18/14/9/7px one-offs are drift, not spec"* — and `10` is off the
    # 4/8/12/16/24/32/48 scale too, so stylelint's allowed-list refuses both outright: they are a
    # BUILD FAILURE, not a preference. `Panel.css` has shipped the scale pairs since c2-7 and its
    # comments name these two values as the mock's; what was never done is amending the artefact
    # they were also written into, which left this file specifying a value the app is forbidden to
    # ship. Same repair, same reason, as `components.legality-row.padding` below.
    header-padding: '{spacing.2} {spacing.3}'
    body-padding: '{spacing.3}'
  badge:
    radius: '{rounded.pill}'
    # AMENDED 2026-08-07 (story c4-12, Q13). This read `'2px 9px'`. `9` is in the Layout & Spacing
    # section's own enumerated drift list and `2` is off the scale; `Badge.css` has shipped
    # `{spacing.1} {spacing.2}` since c2-7. The third and last of the family — the c4-10 amendment
    # named these two files as *"the identical repair … already shipped twice"* and amended only
    # the legality row.
    padding: '{spacing.1} {spacing.2}'
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
    # AMENDED 2026-08-06 (story c4-7, Q1). This read `'34px 1fr auto 64px'`, whose fourth track
    # reserved 64px for a right-aligned PRICE. There is no price data anywhere in this system and
    # there never has been — measured, not inferred: `cards` has 23 columns and none is a price,
    # no schema declares one, and `src/data/importers/transformers.py` (the field-by-field
    # Scryfall projection) never reads the `prices` object at all, so it was never imported rather
    # than dropped downstream. `tests/unit/companion/test_routes_cards.py:136` asserts the absence
    # ON PURPOSE, under Brad's c3-2 Q4 ruling that the endpoint ships no price rather than a
    # permanently-null one; c4-5 closed the identical clause on the card detail panel BY ABSENCE.
    # A dead 64px gutter is the alternative and it is worse — a visible empty column reads as a
    # loading failure rather than as an absent feature.
    # The bare `1fr` also could not ship verbatim: `shell.test.ts:960` bans a content-floored
    # track, because `1fr` means `minmax(auto, 1fr)` and one unbreakable card name would widen the
    # column past its share. `minmax(0, 1fr)` is the guard's own named correct form.
    # Stated inline so it is not "corrected" back, exactly as the c4-5 amendment above asks.
    # AMENDED AGAIN 2026-08-06 (c4-7 review ruling): the quantity track was a fixed `34px`, sized
    # to the corpus maximum (×34) — a measurement, not a bound. Unlimited-copy cards (Relentless
    # Rats and kin) put ×100 one import away, and a fixed track would clip the digits into the
    # name column. `minmax(34px, max-content)` floors at today's width and grows only when a
    # wider quantity actually arrives.
    columns: 'minmax(34px, max-content) minmax(0, 1fr) auto'
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
    # Added 2026-08-06 (story c4-9, Q7) as a MEASURED accessibility repair rather than a
    # preference, and deliberately the same value `curve-bar.segment-hairline` already carries.
    # WCAG 2.x over the shipped hexes: all 15 adjacent `mana-*` pairs are under the 3:1 non-text
    # floor, 8 of them under 1.3:1, worst `mana-b`/`mana-colorless` at 1.03:1 and best
    # `mana-w`/`mana-r` at 2.30:1. But EVERY segment clears `surface-well` at 6.62:1 (`mana-r`)
    # to 15.20:1 (`mana-w`), so a 1px separator in the TRACK colour turns 15 sub-3:1 boundaries
    # into 15 at 6.62:1 or better, with no new token and no new colour. It closes
    # DISTINGUISHABILITY only; identifiability is the legend's, and the two are different
    # problems (deferred-work.md:1447-1471, open at Medium).
    segment-hairline: '1px {colors.surface-well}'
  card-detail:
    background: '{colors.surface-overlay}'
    radius: '{rounded.lg}'
    art-radius: '{rounded.card}'
    # AMENDED 2026-08-05 (story c4-5, Q2). This read `{colors.accent-dim}`, on a component whose
    # own `background` two lines up is `{colors.surface-overlay}` — the exact pairing the Colors
    # table below measures at 2.70:1 and bans by name. It is the identical defect the 07-25 gate
    # closed as M4/C3 for `card-tile.live-ring`, and the fix was never carried across to this
    # ring. `{colors.accent}` is 5.5:1 on this surface and is that table's own named substitute.
    # Stated inline so it is not "corrected" back, exactly as C3 asked.
    pinned-ring: '0 0 0 1px {colors.accent}'
  legality-row:
    rule: '1px solid {colors.border-hairline}'
    # AMENDED 2026-08-06 (story c4-10, Q10). This read `'9px 2px'`. Neither number is on the
    # 4/8/12/16/24/32/48 spacing scale, the Layout & Spacing section below names the mock's
    # "18/14/9/7px one-offs" as drift rather than spec — `9` is in that enumerated list — and
    # stylelint's allowed-list refuses both outright, measured: it is a BUILD FAILURE, not a
    # preference. `{spacing.2} {spacing.1}` (8px / 4px) is the nearest scale pair in both axes.
    # The identical repair is already shipped twice with its citation inline: Panel.css:63-69
    # ('10px 14px' -> 8/12) and Badge.css:52-54 ('2px 9px' -> 4/8, the same two numbers).
    # No token is added for it — validation-report-2026-07-25.md:75 already flags this component
    # family as over-tokenised, and both values resolve to existing scale tokens.
    padding: '{spacing.2} {spacing.1}'
  nav-pill:
    background: '{colors.surface-panel}'
    border: '1px solid {colors.border-strong}'
    radius: '{rounded.pill}'
    # AMENDED 2026-08-12 (story c6-8, Task 1). This read `'7px 14px'`. Neither number is on the
    # 4/8/12/16/24/32/48 spacing scale, and the Layout & Spacing section below names the mock's
    # "18/14/9/7px one-offs" as drift rather than spec — BOTH numbers are inside that enumerated
    # list — so stylelint's allowed-list refuses them outright: a BUILD FAILURE, not a preference.
    # `{spacing.2} {spacing.3}` (8px / 12px) is the nearest scale pair on both axes, and it is
    # ALREADY SHIPPED on this very component: Brad's c6-5 Q4 ruling (2026-08-10) put exactly
    # these values on the "Close · esc" control (`AgentView.css:164`), which the component
    # description below declares to be this same pill — *"the agent-view controls in the header,
    # and the 'Close · esc' control inside a view"*. That ruling recorded the amendment as owed
    # and this is it; c6-8's header pills ship the identical rule, so one spec now has one value.
    # The same repair is shipped three times over with its citation inline:
    # `components.legality-row.padding` above ('9px 2px' → 8/4), Panel.css:63-69 ('10px 14px' →
    # 8/12, the same pair) and Badge.css:52-54 ('2px 9px' → 4/8). No token is added — both
    # values resolve to existing scale tokens.
    padding: '{spacing.2} {spacing.3}'
    foreground: '{colors.text-secondary}'
    # THE QUIET STATE, added 2026-08-12 (story c6-8, AC 1, Q2). EXPERIENCE.md:73 promises a
    # state this block had no value for: a pill whose kind has received no push this session
    # renders *"disabled-quiet (`text-tertiary`, no hover glow)"*. It is the BASE pill with one
    # colour swapped — no separate background, border or radius, and deliberately NO hover rule
    # rather than a neutralised one, because the element ships `disabled` and a hover treatment
    # on it would be a promise the pointer cannot keep. `{colors.text-tertiary}` measures 5.43:1
    # on `{colors.surface-panel}` — the pair `components.legality-row`'s detail line already
    # banks on — so quiet is de-emphasised without dropping below the 4.5:1 text floor.
    quiet-foreground: '{colors.text-tertiary}'
    # THE LAST PUSH'S TIME, added 2026-08-12 (story c6-8, AC 2, Q4). UX-DR28 puts the push time
    # on the pill, and four artefacts say "shows the last push's time" while none specifies a
    # rendering. Neither value is a new opinion: `{typography.micro}` is the Type section's own
    # role for timestamps (*"kicker labels, stat-chip labels, timestamps, footer attribution"*)
    # and `{colors.text-tertiary}` is the Colors section's (*"de-emphasized numerics, axis
    # labels, captions and timestamps"*) — this is the artefact's existing doctrine read onto
    # this component. The time is ABSOLUTE and STATIC (local hour + minute), updated only when a
    # new push replaces it, which is UX-DR43's wording; a self-updating relative clock would be
    # a render loop and an update surface nothing specs.
    time-type: '{typography.micro}'
    time-foreground: '{colors.text-tertiary}'
    unread-dot: '{colors.accent}'
    # GEOMETRY FOR THE DOT ABOVE, added 2026-08-12 (story c6-8, AC 3, Q6). The block gave the
    # dot a colour and no size. 8px cites the other IN-PILL dot in the system — the connection
    # pill's (UX-DR29) — rather than the Panel live dot's 6px, because a dot inside a pill
    # beside label text is the same optical problem in both places. Static: no arrival pulse or
    # glow ("glows are moments, not steady states" below), which would also cost a
    # motion-inventory entry this story does not own. The dot never carries the state alone —
    # UX-DR29's rule — so the pill's accessible name says "unread" in words as well.
    unread-dot-size: 8px
  agent-view:
    scrim: '{colors.scrim}'
    backdrop: 'blur(16px)'
    background: '{colors.surface-panel}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.lg}'
    shadow: '{components.elevation.shadow-raise}'
    # AMENDED 2026-08-18 (story 15.3). This read `'{spacing.6}'`. Both steps are 32px today, so
    # nothing renders differently — but the overlay's contract is that its inset **coincides with
    # the shell's own frame**, and the frame is `{spacing.gutter}` (shipped as `var(--space-gutter)`,
    # `AppShell.css`). Named as a scale step, a later retune of the gutter would silently break the
    # alignment while every assertion kept passing. Two names for one distance is the trap; this is
    # Brad's 2026-07-28 ruling on story c2-6's AC 7, finally carried back into the artefact.
    inset: '{spacing.gutter}'
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
    # AMENDED 2026-08-11 (story c6-7, Q2). This block carried four values — background, border,
    # radius, thumb-radius — and nothing about SPACING, ROW HEIGHT or the LIVE MARKER's form,
    # while the component description below already promised all three ("full row height",
    # "`live` marks the row with `{colors.accent}`"). The row is also on this file's own
    # no-visual-precedent list (see the Composition reference note), so there are no mock pixels
    # to read the missing values off either. That made "the suggestions view matches DESIGN.md"
    # UNSATISFIABLE rather than merely unchecked, in the same way c4-12 found the empty-deck line
    # unsatisfiable: `ui/tests/shell.test.ts` requires every `px` literal in a component
    # stylesheet to carry a DESIGN.md citation within a sentence of the value, and there was
    # nothing here to cite. The treatment is therefore ruled and written HERE FIRST and
    # `SuggestionsView.css` written against it — the other order produces either a red guard or
    # an invented citation.
    #
    # EVERY VALUE COMES FROM THE SPACING SCALE, and the row height comes from NONE of them. The
    # thumbnail is a full card face at 63:88 spanning the row's height (the description's
    # "art-forward"), so a fixed row height would either crop the card or fix the thumbnail's
    # width by arithmetic done in a stylesheet. Instead the row is CONTENT-DRIVEN — two text
    # lines (name/badge/cost/confidence, then the reason) plus the padding below — and the
    # thumbnail's width follows from that height through its own aspect ratio. Nothing here
    # spends a px, which is the same resolution `empty-deck-line` reached for the same reason.
    background: '{colors.surface-overlay}'
    border: '1px solid {colors.border-hairline}'
    radius: '{rounded.md}'
    thumb-radius: '{rounded.card}'
    padding: '{spacing.2} {spacing.3}'
    # TWO-VALUE, MATCHING THE GRID IT SPACES: `{spacing.3}` is the column gap (thumbnail to
    # text), `{spacing.2}` is the row gap (head line to reason line) — the same pair the
    # `.suggestion-row-head`/`.suggestions-view-rows` clusters already use for "internal cluster"
    # spacing (code review, 2026-08-11 — the single-value citation shipped here matched only the
    # column half; corrected to name both).
    gap: '{spacing.2} {spacing.3}'
    height: 'content-driven — two text lines plus padding; the thumbnail spans it at {components.card-tile.aspect} and its width follows'
    # THE LIVE MARKER, AT THE OVERLAY-LEGAL TONE. Same shape as `components.deck-row`'s pair —
    # a flat tint plus a 2px inset rule down the leading edge — because it marks the same thing
    # (the card currently under inspection) and a second visual language for one meaning is
    # drift. It is an INSET shadow rather than a `border-left` for that component's reason: a
    # border shifts every column 2px sideways on becoming live, and a cursor sweeping a list
    # turns that into a shimmer.
    # `{colors.accent}` and NEVER `{colors.accent-dim}`: this row's own background is
    # `{colors.surface-overlay}`, where accent-dim measures 2.70:1 and fails the 3:1 non-text
    # floor — the ban the Contrast table names this component in, and which the description
    # below already carries in bold.
    live-background: '{colors.accent-glow}'
    live-rule: 'inset 2px 0 0 {colors.accent}'
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
  empty-deck-line:
    # ADDED 2026-08-07 (story c4-12, Q2). This file specified the empty-deck state NOWHERE. The
    # entire written specification was two EXPERIENCE.md table cells (`:70`, `:113`) carrying the
    # copy, the type role, the colour and the words "no panel, no error styling" — while spacing,
    # alignment, the container, a minimum height and the list semantics were all unlegislated.
    # That made "the deck view matches DESIGN.md" UNSATISFIABLE for this branch rather than
    # merely unchecked: `ui/tests/shell.test.ts` requires every `px` literal in a component
    # stylesheet to carry a DESIGN.md citation within a sentence of the value, and there was
    # nothing to cite. The treatment is therefore ruled and written here FIRST, and
    # `CardGrid.css` written against it — the other order produces either a red guard or an
    # invented citation.
    #
    # IT SPENDS NO LENGTH OF ITS OWN, and that is the decision rather than an omission. The line
    # is the untitled card-grid Panel's ONLY child, so `{components.panel.body-padding}` already
    # supplies the inset; a second one would be a value invented to fill a gap rather than a
    # decision, which is the drift the Layout & Spacing scale exists to prevent. No min-height
    # either: reserving grid-sized space for content that is deliberately absent is what makes an
    # empty state read as a loading failure (see the Deck data note on that failure mode).
    type: '{typography.body}'
    foreground: '{colors.text-secondary}'
    container: 'the untitled card-grid Panel — {components.panel.body-padding} is the whole of its inset'
  empty-push-line:
    # ADDED 2026-08-11 (story c6-7, Q2), and it is `empty-deck-line`'s sibling in every respect
    # that matters. c6-6 shipped this state — the sentence a push with zero items shows in place
    # of its rows — against the empty-DECK block's values, cited, because the two are the same
    # kind of thing: one calm sentence standing in for absent content inside a surface that
    # already supplies its own padding. That story had no acceptance criterion asking for an
    # artefact amendment and correctly declined to make one quietly, recording the gap instead
    # (`deferred-work.md:22`, homed on this story by name). This story amends the block above it
    # anyway, so the sibling's own block is one entry of the same amendment rather than a
    # separate act.
    #
    # IT SPENDS NO LENGTH OF ITS OWN, for the identical reason: the line is the agent view
    # body's only child in this state, and that body already spends `{spacing.4}` around
    # whatever it holds — note this is the BODY's inset, not `{components.agent-view.inset}`,
    # which is the shell's own inset from the window edge. No min-height either; reserving
    # list-sized space for content that is deliberately absent is what makes an empty state
    # read as a loading failure.
    #
    # IT REPLACES THE `<ul>` rather than sitting inside it (the c4-12 semantics, unchanged): a
    # `<p>` inside a `<ul>` is invalid against UX-DR44's mandated list semantics, and an empty
    # list left beside the sentence announces "list, 0 items" before the sentence explaining
    # why. The words themselves are EXPERIENCE.md's Voice-and-Tone row and are transcribed by
    # the copy module, never authored here.
    type: '{typography.body}'
    foreground: '{colors.text-secondary}'
    # `{spacing.4}`, NOT `{components.agent-view.inset}` (`{spacing.gutter}`) — the shell's inset from
    # the window edge is a different value from the BODY's own padding, exactly as the note two
    # comments up says. Corrected by code review (2026-08-11): this field cited the shell's
    # token where the body's own (`.agent-view-body`'s `padding: 0 var(--space-4) var(--space-4)`)
    # was meant.
    container: 'the agent view body — {spacing.4} is the whole of its inset'
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

> **The one exception, and why it is not one.** `{fonts.mono}` is a second family, and it carries no hierarchy: it styles command literals inside State panel copy — a string the user is about to type into a terminal, which is *data*, the same category as a mana pip's colour. Chrome and display type remain single-family. It is a system stack (no `@font-face`, no download), so the offline guarantee stands. Added by story c2-9.

- `{typography.display}` — the deck name. The only 30px moment on screen.
- `{typography.heading}` — panel titles that carry a real name (card detail name, agent-view title, group titles).
- `{typography.body}` / `{typography.body-strong}` — reasons, rationale, oracle text, state-panel copy, group descriptions.
- `{typography.label}` — panel titles, type-group headers, nav pills, badges. Uppercase, tracked 0.1em. Keep label strings short: at 11px with that tracking, a long title is effortful to read. Panel titles that need to carry counts should put the count in `{typography.numeric}` beside the label, not inside it.
- `{typography.micro}` — kicker labels, stat-chip labels, timestamps, footer attribution. Uppercase, tracked 0.08em.
- `{typography.numeric}` — every count, quantity and axis value. **Always tabular.** (*Amended 2026-08-07, story c4-12, Q13*: this listed *price* among the roles, a residue of the same removal `components.deck-row.columns` and the Card detail panel bullet each recorded in 2026-08-06 — **there is no price data anywhere in this system**, so the role has nothing priced to set.)

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

Agent views take the whole window as a scrim-backed overlay inset by `{spacing.gutter}` — the same token that frames the window, because the overlay's inset must coincide with the shell's own frame rather than merely equal it today. *(Amended 2026-08-18, story 15.3; this said `{spacing.6}`, which is the same 32px by coincidence.)*

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
- **Agent views nav** (the nav pill) — the agent-view controls in the header, and the "Close · esc" control inside a view. `{components.nav-pill.padding}` at `{rounded.pill}`, `{typography.label}`. Hover/focus: border to `{components.nav-pill.hover-border}`, text to `{components.nav-pill.hover-foreground}`, plus `{components.nav-pill.hover-glow}`. A pill whose view has an unread push carries a `{components.nav-pill.unread-dot}` at `{components.nav-pill.unread-dot-size}` — the accent's meaning is "the agent put something here", so an unread push is exactly what it marks. **Three states, added 2026-08-12 (story c6-8), because the block above carried a hover treatment and an unread dot and the header nav needs the other three-quarters of the component to exist:** a pill whose kind has received no push this session is **quiet** — `{components.nav-pill.quiet-foreground}`, no hover rule at all, and not focusable (it ships `disabled`, so the cold-open Tab order contains no pill at all, which is UX-DR40's enumeration read literally); a pill whose kind HAS received one is active and carries **the last push's time** after its label in `{components.nav-pill.time-type}` `{components.nav-pill.time-foreground}`, absolute and static; and the unread dot is presentational (`aria-hidden`) with the word "unread" in the button's accessible name beside it, because UX-DR29 already ruled that the dot never carries the state alone and UX-DR45 does not license this pill to announce. The quiet pill's copy is EXPERIENCE.md:73's, byte-for-byte, and it reaches assistive technology as a programmatic description as well as a pointer tooltip — UX-DR39 bans hover-only disclosure of unique information, and the connection pill was already repaired once for exactly this shape (see EXPERIENCE.md's amended nav-pill row).
- **Skip link** — "Skip past the deck grid": visually hidden until it receives keyboard focus; on focus it appears at the window's top-left as a `{components.skip-link.radius}` chip on `{components.skip-link.background}` with `{components.skip-link.border}`, text in `{typography.body-strong}` `{components.skip-link.foreground}`, carrying the standard `{components.focus-ring}`. It exists because the card grid puts a long run of Tab stops between the header nav and everything in the right column — **measured 2026-08-07 on the largest real deck (Atraxa Counter Cabinet v2, 99 tiles): 205 stops from the top of the document to the footer, of which the link skips 102.0 on average** (amended 2026-08-07, story c4-12, Q13; this read *"100+ Tab stops"* while EXPERIENCE.md already carried c4-11's measured figures, so the two peer artefacts disagreed about the same number). Behavior in EXPERIENCE.md.
- **Footer attribution** — one quiet line, full width, `{components.footer-attribution.background}` above `{components.footer-attribution.border-top}`, `{typography.micro}` in `{components.footer-attribution.foreground}` (`text-secondary`, 9.3:1 — this text is legally load-bearing and gets a passing tier, not a muted one): "Card data and imagery courtesy of Scryfall. Unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy. Not approved/endorsed by Wizards." Links persistently underlined (identifiable at rest, not hover-only); hover brightens to `{colors.text-primary}`; each link's hit area ≥ 24px tall. Visible without scrolling, and never louder than this. **Required on every surface — this is a condition of public release, not a design choice.**

### Deck data

- **Card tile** — the grid unit. The card face *is* the tile: no frame, no title bar — chrome-free art at `{components.card-tile.radius}` and `{components.card-tile.aspect}`, with `{components.card-tile.shadow}`. Caption below in `{typography.label}` `{colors.text-secondary}`, single-line ellipsis. `live` (the card under inspection) adds `{components.card-tile.live-ring}`. Hover/focus: `{components.card-tile.hover-scale}` in place over `{components.card-tile.transition}`, raising z-index so neighbors slide under — restrained here because the grid sits beside a persistent detail panel that already does the "look closer" work. Because a tile's focus indicator sits over arbitrary card art rather than a known surface, tiles use `{components.card-tile.focus-ring-over-art}` — the focus ring plus a dark outer edge — so the indicator is visible against a light or a dark painting alike. `live` uses `{colors.accent}`, not `accent-dim`, because tiles also appear on `surface-overlay` inside agent views where `accent-dim` fails the 3:1 floor.
- **DFC flip control** — rendered only on double-faced cards. A circular `{components.dfc-flip.radius}` button at `{components.dfc-flip.size}` with a `{components.dfc-flip.hit-area}` hit box, pinned to the tile's **top-left** inside `{spacing.2}` — the top-right is occupied by the quantity badge, and the two must never collide. It shares the badge's material so the pair reads as one family: `{components.dfc-flip.background}` with `{components.dfc-flip.backdrop}` and `{components.dfc-flip.border}`, carrying a stroke-based two-arrow rotate glyph in `{components.dfc-flip.foreground}` — a plain UI glyph, never anything that could read as a mana or set symbol. Opacity `{components.dfc-flip.rest-opacity}` at rest so it never competes with the art, 1.0 when its tile is hovered or focused; hovering the control itself tints the glyph `{components.dfc-flip.hover-foreground}`. It is visibly a control, not part of the card, so flip-versus-inspect is unambiguous. Flip animation: 3D Y-rotation over `{components.dfc-flip.flip}`. The card detail panel gets its own copy of the control at the same spec, pinned to its art's top-left.
- **Quantity badge** — `{typography.numeric}` count ("×4") pinned top-right inside `{spacing.2}` of the tile, on `{components.quantity-badge.background}` with `{components.quantity-badge.backdrop}` and `{components.quantity-badge.border}`. When a quantity changes on refetch it flashes the accent glow once — garnish; the accessible signal is the group-header count plus the live-region announcement.
- **Mana curve** — bars per mana value on a `{components.curve-bar.track}` well at `{components.curve-bar.radius}`. Buckets are **1 … 7+**; lands are excluded; DFCs bucket by front face. Counts above bars in `{typography.numeric}` `{colors.text-tertiary}`; axis labels in `{typography.micro}`. Bars fill with `{components.curve-bar.fill}` — a *chrome* token. If bars are stacked by color, segments run in fixed order W·U·B·R·G·gold·colorless separated by `{components.curve-bar.segment-hairline}`, multicolor cards contribute one `mana-gold` segment, and the segments are `aria-hidden` decoration: the accessible data is the per-bar name and the visually-hidden table. Never fill an unstacked bar with a `mana-*` token.
- **Color distribution** — a single `{components.color-bar.height}` bar at `{rounded.pill}` on `{components.color-bar.track}`, segmented by `mana-*` proportional to pip count, with a legend of `ManaPip` + count + percentage below. This is data ink used correctly. Adjacent segments are separated by `{components.color-bar.segment-hairline}` — **added 2026-08-06 (story c4-9, Q7) as a contrast correction rather than a preference**; the frontmatter carries the measurement, and the outer edges take none because the pill's ends are already the track. **"Proportional to pip count" means the FRONT FACE's pips** — amended 2026-08-06 (c4-9, Q1), because the clause resolved two ways and no artefact said which: counting the whole `mana_cost` string counts both halves of a split, Adventure or Omen cost, and measured against the shipped database that moves **10 of 40 real decks and re-orders the segments of 2** (`Prismatic Dragon` falls from 71 pips to 45 — 37% of its bar — and its order changes from B>U>G>R>W to U>B>G>R>W; the cause is the current-Standard TDM Omen cycle, not a corner case). The front face is what every other surface already reads — UX-DR17, FR-05, and the deck row's own cost — so a whole-string bar would be the only one in the app that does not. A **hybrid pip credits every colour it can be paid with**, so the counts sum to more than the symbols printed on the cards; Phyrexian is a modifier and not a colour; generic and `{X}` count for nobody; **lands are excluded**, because a land that taps for mana is a *source* rather than a demand. The legend's `ManaPip` is **decorative** and each entry names its colour in TEXT — that text is the accessible data path, which is why the bar itself is `aria-hidden`. **`mana-gold` does not appear here**: gold is a card-level property and a *pip* is never gold.
- **ManaPip / ManaCost** — a plain circle filled with the `mana-*` token, `{colors.text-inverse}` numeral inside for generic costs. Deliberately not a mana-symbol shape. `ManaCost` parses full Scryfall cost strings: braces, hybrid (`{2/R}`, `{W/U}`) as a split or dual-tinted pip, Phyrexian, and `{X}` — never silently dropping a symbol it doesn't recognize.
- **Deck row** — the text-list unit. `{components.deck-row.columns}`: quantity in `{typography.numeric}` `{colors.text-tertiary}`, name in `{typography.body}` (`body-strong` `{colors.text-primary}` when live), mana cost as pips. `live` tints the row `{components.deck-row.live-background}` with `{components.deck-row.live-rule}`, and the quantity moves to `{colors.text-secondary}` while it is live — **added 2026-08-06 (story c4-7), as a contrast correction rather than a preference**: `{colors.accent-glow}` composites over `{colors.surface-panel}` to `#32365A`, where `{colors.text-tertiary}` measures 3.73:1 against a 13px numeral and fails the 4.5:1 small-text floor, while measuring 5.43:1 at rest. This is a *fifth* surface the Contrast table below does not cover — it lists the four named surfaces, and a tinted row is none of them. Same family as the `card-tile.live-ring` and `card-detail.pinned-ring` corrections. **There is no price column** — amended 2026-08-06 (story c4-7, Q1); see the frontmatter note on `components.deck-row.columns` for the measurement. A double-faced row shows the **front face's** name and cost (UX-DR19): the name splits from the summary, but 87.8% of faced cards carry a blank top-level `mana_cost` whose real value lives only in `card_faces[0]`, so that half depends on hydration and paints late.
- **Group header** — type-group dividers ("CREATURES") in `{typography.label}` `{components.group-header.foreground}` with the count right-aligned in `{typography.numeric}` `{colors.text-tertiary}`, over `{components.group-header.rule}`.
- **Card detail panel** — the persistent right-column panel at `level="overlay"`. Full card face at `{components.card-detail.art-radius}` on `{components.card-detail.background}`, then name in `{typography.heading}` with mana cost right-aligned, type line in `{typography.body}` `{colors.text-secondary}` — **no price beside it**: amended 2026-08-06 (c4-7 review) to match the deck-row amendment above; there is no price data anywhere in this system, c4-5 shipped this panel without one under Brad's c3-2 Q4 ruling, and this line previously still specified "price right-aligned in `{typography.numeric}`", inviting exactly the "correction" the amendments exist to prevent — and note/oracle text in `{typography.body}` `{colors.text-secondary}`. When pinned (see EXPERIENCE.md) it carries `{components.card-detail.pinned-ring}`. That ring uses `{colors.accent}`, **not `accent-dim`** — this panel's own background is `surface-overlay`, where `accent-dim` is 2.70:1 and fails the 3:1 non-text floor; the same correction the gate made for `{components.card-tile.live-ring}`.
- **Format check** (the legality row) — label in `{typography.body}` `{colors.text-secondary}`, `Badge` right-aligned, over `{components.legality-row.rule}`, **with the check's `detail` sentence on a second line beneath the label in `{typography.body}` `{colors.text-tertiary}`** — the second line **added 2026-08-06 (story c4-10, Q2)**, as a correctness repair rather than a preference. This row had two slots and the endpoint it renders has **three fields, with 100% of the information in the third**: the wire carries `check` (a machine token — there is no label field anywhere on it), `status` (`pass`/`advisory`/`violation`) and `detail` (a server-authored sentence). Rendered to the two-slot letter, the one deck in forty with a real legality violation draws `Legality` and a red pill while the words **`'Pym Particles' is not legal in brawl.`** appear nowhere on the glass — in the panel whose own user story is *"I find out about a banned card"*. Three consequences, all measured on a real screen: **row height stops being uniform** (66.3px for a one-line detail, 86.3px for two, at 452px wide) and nothing in these artefacts ever specified one; the rotation advisory is 86 characters on **40 of 40 decks permanently**, so the second line is the panel's ordinary height rather than an exception path; and the whole panel measures **452 × 475px** on an all-pass deck. The sentence is `{typography.body}` and **not** `{typography.micro}` — micro carries `textTransform: uppercase`, and `'PYM PARTICLES' IS NOT LEGAL IN BRAWL.` destroys the card name the row exists to show — so it is distinguished from the label by TIER, which is `components.deck-row`'s own idiom; `{colors.text-tertiary}` measures 5.43:1 on `{colors.surface-panel}`. Two things the panel deliberately does **not** draw: **no headline verdict, no summary badge and no count** (`is_legal` is `false` both for a deck that breaks a rule and for one that could not be checked, so binding it renders a red verdict over six rows none of which is a violation), and **no format string in its own chrome** — this report's `format` is normalised while the header's badge is the stored value. The badge carries the **status word** (`Pass` / `Advisory` / `Violation`) rather than the mock's derived values (`'60 / 60'`, `'no violations'`, `'11 cards'`), which exist on the wire nowhere and whose computation would be a construction rule written in TypeScript, invisible to every Python guard. The mock's first label is a **format name** (`'Standard'`), not a label, and its `'Banned or restricted'` is a false label — see EXPERIENCE.md's amended component row.
- **Card placeholder** (named + unknown-card variants) — a deliberately designed stand-in, never a broken-image glyph: card-shaped at `{components.card-placeholder.radius}` on `{components.card-placeholder.background}` with `{components.card-placeholder.border}`, rendering in chrome type — name centered in `{typography.body-strong}`, mana cost as pips above, type line in `{typography.micro}` `{colors.text-secondary}`. Unknown-card variant: name slot reads "Unknown card" with the truncated ID in `{colors.text-secondary}` (the ID is the only identifying information — load-bearing, so never a de-emphasized tier). Image-loading wells use the same shape on `{colors.surface-well}` with no text.

### Agent views

- **Agent view** (the shell) — full-window overlay: `{components.agent-view.scrim}` with `{components.agent-view.backdrop}`, inset `{components.agent-view.inset}`, containing a `{components.agent-view.background}` shell at `{components.agent-view.radius}` with `{components.agent-view.shadow}`. Header row: "AGENT VIEW" kicker in `{typography.micro}` `{colors.accent}`, title in `{typography.heading}`, a summary count in `{typography.body}` `{colors.text-tertiary}`, and a "Close · esc" nav pill right-aligned. Enters over `{components.agent-view.enter}` as a fade + 8px rise. Body scrolls.
- **Swap row** — out-card and in-card tiles side by side joined by a `{components.swap-row.arrow}` glyph, on `{components.swap-row.background}` at `{components.swap-row.radius}`. "Out · N copies" in `{typography.micro}` `{components.swap-row.out-tint}` above the out tile; "In · N copies" in `{components.swap-row.in-tint}` above the in tile. Tints appear on the labels only — **never on the art**. Rationale in `{typography.body}` `{colors.text-secondary}` right of the pair, with `StatChip`s for price/curve/confidence beneath.
- **Tier row** — a `{components.tier-row.chip-width}` chip on `{components.tier-row.chip-background}` carrying the tier letter at `{components.tier-row.letter-size}` / `{components.tier-row.letter-weight}` with the tier name in `{typography.micro}` `{colors.text-tertiary}` beneath, then a note in `{typography.body}` `{colors.text-secondary}` and a thumbnail row. Tier letters use `accent-bright` (S) · `accent` (A) · `text-primary` (B) · `text-secondary` (C) · `text-tertiary` (D). At 44px the letters are large text, so all five clear the floor comfortably; the letter is also always accompanied by its name in text, so color is never the sole carrier of rank. Empty tiers are skipped, not rendered as empty shells.
- **Suggestion row** — card thumbnail at `{components.suggestion-row.thumb-radius}` (full row height — art-forward) left, then a `Badge`, name in `{typography.body-strong}`, mana cost, optional confidence in `{typography.micro}` `{colors.text-tertiary}` right-aligned, and a one-line reason in `{typography.body}` `{colors.text-secondary}` beneath, at `{components.suggestion-row.padding}` and `{components.suggestion-row.gap}`. `live` marks the row with `{colors.accent}` — **not `accent-dim`**, which fails 3:1 on this surface — as `{components.suggestion-row.live-background}` plus `{components.suggestion-row.live-rule}`. **The badge is the item's `category`, and "action" was struck 2026-08-11 (story c6-7, Q1)**: this line read *"an action `Badge`"*, and there is **no `action` field on the wire** — `SuggestionItem` is `{card_id, reason, category?, confidence?}` and `contracts.py` says of `category` that it *"renders inside a badge"*, capped at 80 characters, *"capped at what a badge can hold"*. An "action" badge would therefore have had to be an authored word ("ADD") standing for a decision no tool sends, on a surface `EXPERIENCE.md` calls read-only glass. The badge takes the **neutral** tone — the only tone that invents nothing, since no mapping from free-text categories to the four semantic tones exists — and **no badge renders at all when `category` is absent**. EXPERIENCE.md's component row carried the same doubled claim ("action badge … optional category chip") and is annotated in the same commit; its own IA row (`:39`) already said only *"card + one-line reason + optional category"*.
- **Group section** — title in `{typography.heading}` with card count in `{typography.numeric}` `{colors.text-tertiary}`, description in `{typography.body}` `{colors.text-secondary}` capped at ~900px measure, then a wrapped tile row.

### System presence & states

- **Connection pill** — bottom-left, `{components.connection-pill.radius}` on `{components.connection-pill.background}` with `{components.connection-pill.border}`: a `{components.connection-pill.dot-size}` dot (`{colors.positive}` live · `{colors.caution}` reconnecting · `{colors.negative}` backend gone — all **static**, no pulse) plus `{typography.micro}` text naming the state and the active deck name. The dot never carries the state alone. Quiet at rest; it never animates. *This replaces `AgentStatus`, whose `idle | thinking | streaming` vocabulary describes agent cognition the app has no signal for.* **Amended 2026-08-08 (story c5-7): the micro role applies to the STATE WORD only; the active deck NAME takes `{typography.body}` `{colors.text-secondary}` beside it.** `{typography.micro}` carries `textTransform: uppercase` from this file's own frontmatter, and an uppercased `SULTAI MIDRANGE` destroys the mixed-case name the pill exists to show — the identical wall c4-10 hit with the format check's server-authored sentence (`:236-237`) and c4-3 hit with the unknown-card label. The resolution is the same one, and the shipped precedent for the pairing is in this app's own header: `app-shell-kicker` is micro/uppercase/tertiary and the deck name beside it is not. The words themselves are in `EXPERIENCE.md`'s connection-pill copy row, authored by that story because no artefact had them.
- **State panel** — the shared shell for no-active-deck, database-not-initialized, database-updating and disconnected states: centered on `{components.state-panel.background}` at `{components.state-panel.radius}` with `{components.state-panel.border}`, max-width `{components.state-panel.max-width}`. Headline `{typography.heading}`, guidance `{typography.body}` `{colors.text-secondary}`, the concrete next action on its own line in `{typography.body-strong}` `{colors.accent}` (commands in an inline chip on `{colors.surface-well}` at `{rounded.sm}` in `{fonts.mono}` — the *only* place a second family appears, because a command is data the user retypes). No illustrations, no sad-face icons — calm text on a calm panel. The panel also covers **database-updating-stalled** and **internal-error**, added with their copy in story c2-9; a panel whose state has no honest next action renders none rather than inventing one.
- **Empty deck line** — what a loaded deck with **zero cards** shows in place of its grid: the one sentence *"This deck is empty — ask your agent to add cards."* (EXPERIENCE.md's Voice and Tone row is the source; it is transcribed, not authored) in `{components.empty-deck-line.type}` `{components.empty-deck-line.foreground}`, as the **only child of the untitled card-grid Panel**. It **replaces** the `<ul>` rather than sitting inside or beside it: a `<p>` inside a `<ul>` is invalid against UX-DR44's mandated list semantics, and an empty list left beside the sentence announces *"list, 0 items"* to a screen-reader user **before** the sentence explaining why. **No panel of its own, no error styling, no icon, no `aria-live`** — an empty deck is the NORMAL state at creation (`create_deck` writes no card, and `remove_card_from_deck` never deletes the deck), it arrives as a plain 200 with `cards: []`, and it reaches the glass through the same loaded-deck surface a full deck does. It takes **no inset, no minimum height and no centering of its own** — `{components.panel.body-padding}` is the whole of its spacing, per the frontmatter note. The **mana curve, color distribution and format check** panels are hidden in this state (EXPERIENCE.md); the **card detail and deck list panels are not** — they render their frames with no card and no rows, which no artefact describes and which is recorded as an open artefact defect against UX-DR20 rather than repaired by inventing copy. **Added 2026-08-07 (story c4-12, Q2)**, because until this amendment the state was specified in EXPERIENCE.md only and this file's own rule — *"Every value in the UI comes from this scale"* — had nothing here to point at.

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
