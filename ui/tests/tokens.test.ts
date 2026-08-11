/**
 * The token layer is asserted against DESIGN.md itself — the contract, not a copy of it.
 *
 * AD-12's lesson, applied to CSS: two spellings of one value is one value that will drift.
 * The UX artefact's YAML frontmatter is the single source, so this suite reads it directly
 * rather than testing src/styles/tokens.css against a second manifest committed inside ui/.
 * The cost is a devDependency (`yaml`, see package.json's "//" note) and one path constant.
 *
 * TWO NORMALISATIONS ARE MANDATORY, and both were measured rather than guessed:
 *
 *   1. DESIGN.md writes `rgba(8,9,18,0.75)`. That exact string produces FIFTEEN stylelint
 *      errors across five declarations under stylelint-config-standard
 *      (color-function-alias-notation, color-function-notation: 'modern',
 *      alpha-value-notation: 'percentage'), so the token file writes the same colour as
 *      `rgb(8 9 18 / 75%)`. A string comparison would fail on notation while the colours
 *      are identical.
 *   2. Prettier lowercases CSS hex colours, and DESIGN.md's frontmatter is uppercase
 *      (`#0D0F1A`). A string comparison would fail on case for all 22 hex values.
 *
 * So colours are compared as PARSED NUMERIC TUPLES. That is strictly stronger than a string
 * compare: `#0D0F1A` and `rgb(13 15 26)` are the same colour and this suite says so, while
 * `#0D0F1B` is a different colour and this suite fails.
 *
 * DESIGN.md also uses `{colors.accent-glow}`-style references, and the CSS uses
 * `var(--accent-glow)` for the same job. Both are resolved before comparing, so the
 * composite values (--glow, the focus ring) are checked end to end rather than skipped.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { parse } from 'yaml'
import { describe, expect, it } from 'vitest'

/**
 * The ONE place this path is written. It carries a date because the UX artefacts are
 * exported per-run; if they are ever re-exported, this constant is the single edit — and
 * the "frontmatter parsed" anchor below turns a stale path into a loud, named failure
 * instead of a suite that asserts nothing over an empty object.
 */
const DESIGN_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md',
    import.meta.url,
  ),
)

const TOKENS_CSS = fileURLToPath(new URL('../src/styles/tokens.css', import.meta.url))

// ---------------------------------------------------------------------------------------
// Reading the two sides
// ---------------------------------------------------------------------------------------

interface TypeRole {
  fontFamily: string
  fontSize: string
  fontWeight: string
  lineHeight: string
  letterSpacing?: string
  fontVariantNumeric?: string
}

interface DesignFrontmatter {
  colors: Record<string, string>
  typography: Record<string, TypeRole>
  /**
   * Families that are NOT type roles. Added by story c2-9 (Q2): `typography.*` is typed as a
   * complete `TypeRole` — family, size, weight, line-height — so a bare family has nowhere to
   * live in it, and putting one there would break both the 7-role loop and the
   * "every role names the same family" assertion that MAKES `--font-sans` single.
   * `fonts.mono` is therefore a sibling section rather than an eighth role, which is also the
   * honest shape: a mono family with a `fontSize` would be claiming a hierarchy it does not
   * have.
   */
  fonts: Record<string, string>
  rounded: Record<string, string>
  spacing: Record<string, string>
  components: {
    motion: Record<string, string>
    'focus-ring': Record<string, string>
    elevation: Record<string, string>
    /**
     * Added by story c4-4 (Q2). The token layer carries ONE composite that is not an
     * elevation — `focus-ring-over-art`, which DESIGN.md files here rather than under
     * `components.elevation` because it is a per-component treatment rather than a step on
     * the depth ramp. Typed so the assertion below reads the artefact rather than an `any`:
     * a `components.card-tile` block that vanished from DESIGN.md would fail loudly at the
     * `toBeDefined()` anchor instead of comparing `undefined` to `undefined`.
     */
    'card-tile': Record<string, string>
    /**
     * Added by story c4-5 (Q2, Q4). The panel's own block, and the second per-component
     * composite home — `pinned-ring` lives here for the same reason `card-tile.live-ring`
     * lives next door. Typed rather than reached through an `any` so that a `components.
     * card-detail` block vanishing from DESIGN.md fails at the `toBeDefined()` anchor instead
     * of comparing `undefined` to `undefined`, which is c4-4's own lesson applied.
     */
    'card-detail': Record<string, string>
    /**
     * Added by story c4-7 (Q1, Q6). The deck row's block — home to `live-rule`, the fourth
     * per-component composite, and to `columns`, whose amendment in this same commit dropped a
     * 64px price track that had no data source anywhere in the system. Typed for the reason the
     * two above are: a `components.deck-row` block vanishing from DESIGN.md must fail at the
     * `toBeDefined()` anchor rather than compare `undefined` to `undefined`.
     */
    'deck-row': Record<string, string>
    /**
     * Added by story c6-7 (Q2). The suggestion row's block — home to the fifth per-component
     * composite (`live-rule`) and to the `padding`, `gap` and `height` that story's amendment
     * added, because the block carried four values and the component description below the
     * frontmatter already promised all four of these. Typed for the reason the three above are:
     * the block vanishing from DESIGN.md must fail at the `toBeDefined()` anchor rather than
     * compare `undefined` to `undefined`.
     */
    'suggestion-row': Record<string, string>
    /**
     * The empty-DECK line (c4-12) and the empty-PUSH line (c6-7) — two names for one kind of
     * thing, which is why the tests below compare them to each other rather than each to a
     * retyped constant. The second block discharges `deferred-work.md:22`.
     */
    'empty-deck-line': Record<string, string>
    'empty-push-line': Record<string, string>
  }
}

const readFrontmatter = (): DesignFrontmatter => {
  const raw = readFileSync(DESIGN_MD, 'utf8')
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(raw)
  if (!match) {
    throw new Error(`No YAML frontmatter found in ${DESIGN_MD} — has the artefact moved?`)
  }
  return parse(match[1]) as DesignFrontmatter
}

const design = readFrontmatter()

/**
 * Custom properties declared in the `:root, [data-theme='voltglass']` block — that block
 * SPECIFICALLY, found by its selector and closed by brace counting.
 *
 * The obvious implementation (slice from the first `{` to the last `}` before the first
 * `@media`) is correct only while this file holds exactly one block, and the file's own
 * header comment invites the opposite: an alternate theme ships as a sibling
 * `[data-theme="gilt"]` block. With one added, that slicing would fold gilt's overrides into
 * the Voltglass inventory and the set-equality assertion below would start failing for a
 * reason that has nothing to do with what it is testing. Anchoring on the selector means a
 * second theme is simply invisible here, which is the correct behaviour for a suite named
 * after the Voltglass contract. (Review finding, Low.)
 */
const readTokens = (): Record<string, string> => {
  const source = readFileSync(TOKENS_CSS, 'utf8')
  // Comments first: they contain colons, semicolons and the odd `--token` mention.
  const withoutComments = source.replace(/\/\*[\s\S]*?\*\//g, '')

  const opener = /:root,\s*\[data-theme='voltglass']\s*\{/.exec(withoutComments)
  if (!opener) {
    throw new Error(
      `No \`:root, [data-theme='voltglass']\` block found in ${TOKENS_CSS} — did the selector change?`,
    )
  }
  const start = opener.index + opener[0].length
  let depth = 1
  let end = -1
  for (let i = start; i < withoutComments.length; i++) {
    if (withoutComments[i] === '{') depth++
    else if (withoutComments[i] === '}' && --depth === 0) {
      end = i
      break
    }
  }
  if (end === -1) throw new Error(`Unbalanced braces in ${TOKENS_CSS}`)
  const body = withoutComments.slice(start, end)

  const tokens: Record<string, string> = {}
  for (const decl of body.split(';')) {
    const colon = decl.indexOf(':')
    if (colon === -1) continue
    const name = decl.slice(0, colon).trim()
    if (!name.startsWith('--')) continue
    tokens[name] = decl
      .slice(colon + 1)
      .trim()
      .replace(/\s+/g, ' ')
  }
  return tokens
}

const tokens = readTokens()
const tokensSource = readFileSync(TOKENS_CSS, 'utf8')

// ---------------------------------------------------------------------------------------
// Normalisation
// ---------------------------------------------------------------------------------------

const COLOUR_LITERAL = /#[0-9a-f]{3,8}\b|rgba?\([^)]*\)/gi

/** A colour as `[r, g, b, a]`, whatever notation it arrived in. */
const parseColour = (raw: string): [number, number, number, number] => {
  const value = raw.trim().toLowerCase()

  if (value.startsWith('#')) {
    let hex = value.slice(1)
    if (hex.length === 3 || hex.length === 4) {
      hex = [...hex].map((c) => c + c).join('')
    }
    const channel = (at: number) => parseInt(hex.slice(at, at + 2), 16)
    return [
      channel(0),
      channel(2),
      channel(4),
      hex.length === 8 ? Number((channel(6) / 255).toFixed(4)) : 1,
    ]
  }

  const inner = value.slice(value.indexOf('(') + 1, value.lastIndexOf(')'))
  const [rgbPart, slashAlpha] = inner.split('/')
  const parts = rgbPart.split(/[\s,]+/).filter(Boolean)

  const channel = (token: string) =>
    token.endsWith('%')
      ? Math.round((parseFloat(token) * 255) / 100)
      : Math.round(parseFloat(token))
  const alphaOf = (token: string | undefined) => {
    if (token === undefined) return 1
    const trimmed = token.trim()
    return Number(
      (trimmed.endsWith('%') ? parseFloat(trimmed) / 100 : parseFloat(trimmed)).toFixed(4),
    )
  }

  return [channel(parts[0]), channel(parts[1]), channel(parts[2]), alphaOf(slashAlpha ?? parts[3])]
}

/** `{colors.accent-glow}` (DESIGN.md) and `var(--accent-glow)` (CSS) both become the colour. */
const resolveReferences = (value: string): string =>
  value
    .replace(
      /\{colors\.([a-z0-9-]+)\}/g,
      (_, key: string) => design.colors[key] ?? `{colors.${key}}`,
    )
    .replace(/var\(--([a-z0-9-]+)\)/g, (whole, key: string) => tokens[`--${key}`] ?? whole)

/**
 * Comparable form: references resolved, every colour literal rewritten to its numeric
 * tuple, whitespace collapsed, and the cosmetic space after a comma removed (DESIGN.md
 * writes `cubic-bezier(0.25,0.1,0.25,1)`; Prettier writes `cubic-bezier(0.25, 0.1, 0.25, 1)`).
 */
const normalise = (value: string): string =>
  resolveReferences(value)
    .replace(COLOUR_LITERAL, (literal) => `rgba(${parseColour(literal).join(',')})`)
    .replace(/\s+/g, ' ')
    .replace(/\s*,\s*/g, ',')
    .replace(/\s*\/\s*/g, ' / ')
    .trim()
    .toLowerCase()

// ---------------------------------------------------------------------------------------
// The expected inventory, DERIVED from the frontmatter rather than retyped
// ---------------------------------------------------------------------------------------

const TYPE_ROLES = ['display', 'heading', 'body', 'body-strong', 'label', 'micro', 'numeric']

const expectedNames = [
  '--font-sans',
  '--font-mono',
  ...Object.keys(design.colors).map((k) => `--${k}`),
  ...TYPE_ROLES.map((r) => `--type-${r}`),
  '--tracking-display',
  '--tracking-label',
  '--tracking-micro',
  '--type-numeric-features',
  ...Object.keys(design.rounded).map((k) => `--radius-${k}`),
  ...Object.keys(design.spacing).map((k) => `--space-${k}`),
  ...['pulse', 'glide', 'bloom', 'aurora'].map((k) => `--motion-${k}`),
  ...['ease-out', 'ease-glide', 'ease-snap'].map((k) => `--${k}`),
  '--focus-ring-width',
  '--focus-ring-offset',
  '--shadow-raise',
  '--shadow-rest',
  '--glow',
  // Story c4-4 (Q2). The first composite this layer carries that is not an elevation: DESIGN.md
  // files it under `components.card-tile`, not `components.elevation`, so it cannot be derived
  // from the block the three above come from — it is hand-listed for the same reason they are,
  // and its value is asserted against the artefact just as theirs is.
  '--shadow-focus-ring-over-art',
  // Story c4-5 (Q4). The two INSPECTION rings, and the same reason: both are per-component
  // treatments filed under `components.card-tile` / `components.card-detail` rather than on the
  // depth ramp, so neither is derivable from a frontmatter block. `--shadow-live-ring`'s ABSENCE
  // was an assertion of its own until this story — see the repaired test below, which is the
  // mechanism that told this author the pin moves with the value.
  '--shadow-live-ring',
  '--shadow-pinned-ring',
  // Story c4-7 (Q6). The deck row's live rule, and the same reason a fourth time: DESIGN.md files
  // it under `components.deck-row`, not `components.elevation`, so it is not derivable from a
  // frontmatter block and is hand-listed like the three above. It is the first of the four that
  // is an INSET shadow — asserted below against the artefact, byte-for-byte, exactly as they are.
  '--shadow-deck-row-live',
  // Story c6-7 (Q2). The suggestion row's live rule — the fifth hand-listed composite, filed
  // under `components.suggestion-row` in an amendment this story made to DESIGN.md before
  // writing the stylesheet that cites it. Identical in VALUE to the deck row's rule above and
  // deliberately not the same token: the two live under two independently-amendable artefact
  // blocks, and sharing a name would let an amendment to one silently move the other.
  '--shadow-suggestion-row-live',
]

// ---------------------------------------------------------------------------------------

describe('the token layer is DESIGN.md (AC 1)', () => {
  // THE NON-VACUITY ANCHOR, and it comes first on purpose. Every assertion below indexes
  // into these two objects; if DESIGN.md moved, or the CSS block regex stopped matching,
  // both would be `{}` and a `for (const …of Object.entries({}))` loop asserts NOTHING while
  // reporting green. This is the c2-3 review's whole theme in one test.
  it('parsed both sides, and they are populated', () => {
    expect(
      Object.keys(design.colors),
      `DESIGN.md frontmatter did not parse — is ${DESIGN_MD} still there?`,
    ).toHaveLength(26)
    expect(Object.keys(design.typography)).toHaveLength(7)
    expect(
      Object.keys(design.fonts),
      'DESIGN.md frontmatter has no `fonts:` section — did the c2-9 entry get dropped?',
    ).toEqual(['mono'])
    expect(
      Object.keys(tokens).length,
      'the :root block of tokens.css parsed to nothing — did the selector or comment syntax change?',
    ).toBeGreaterThan(50)
  })

  it('declares exactly the inventory and nothing else', () => {
    // Set equality both ways: a missing token fails, and so does a smuggled-in extra one
    // that no story wrote down.
    expect(new Set(Object.keys(tokens))).toEqual(new Set(expectedNames))
    // 64 until story c2-9, which added `--font-mono` (Q2); 65 until story c4-4, which added
    // `--shadow-focus-ring-over-art` (Q2 again, and for the same kind of reason — a composite
    // stylelint forbids inline); 66 until story c4-5, which added BOTH inspection rings
    // (`--shadow-live-ring` and `--shadow-pinned-ring`, Q4) in one commit because one story
    // gives both a consumer. The count is pinned rather than derived so that adding a token is a
    // DECISION with a diff, not a side effect — and this line moving is the open cost the ruling
    // accepted. Its sibling is `declaredTokens.size` in tests/token-usage.test.ts; both move
    // together or the pair is wrong. 68 until story c4-7, which added `--shadow-deck-row-live`
    // (Q6) — the deck row's inset live rule, which stylelint's box-shadow allowed-list forbids
    // inline exactly as it forbids the three composites above. 69 until story c6-7, which added
    // `--shadow-suggestion-row-live` (Q2) — the same inset marker one surface over, at the one
    // place in the app where `--accent-dim` would actually fail its floor rather than merely
    // be weak.
    expect(expectedNames).toHaveLength(70)
  })

  it('ships all 26 colours at exactly the DESIGN.md value', () => {
    for (const [key, value] of Object.entries(design.colors)) {
      expect(tokens[`--${key}`], `--${key} is missing`).toBeDefined()
      expect(normalise(tokens[`--${key}`]), `--${key} differs from DESIGN.md`).toBe(
        normalise(value),
      )
    }
  })

  it('ships the 7 type roles as complete font shorthands over --font-sans', () => {
    for (const role of TYPE_ROLES) {
      const spec = design.typography[role]
      expect(tokens[`--type-${role}`]).toBe(
        `${spec.fontWeight} ${spec.fontSize}/${spec.lineHeight} var(--font-sans)`,
      )
    }
  })

  it('resolves --font-sans to the family every role names', () => {
    const families = new Set(Object.values(design.typography).map((r) => r.fontFamily))
    expect(families.size, 'DESIGN.md uses more than one family — the token cannot be single').toBe(
      1,
    )
    expect(tokens['--font-sans']).toBe([...families][0])
    expect(tokens['--font-sans']).toContain('Space Grotesk')
  })

  it('resolves --font-mono to the one non-role family DESIGN.md declares (c2-9, Q2)', () => {
    // Byte-for-byte against the artefact, exactly as every other value here. The one thing
    // worth asserting BESIDE equality: this stack must stay system-generic, because the whole
    // argument for admitting a second family was that it costs no @font-face, no download and
    // no committed binary. A webfont name appearing here would silently re-open NFR-06.
    expect(tokens['--font-mono']).toBe(design.fonts.mono)
    expect(tokens['--font-mono']).toMatch(/(^|\s)monospace$/)
    expect(
      tokens['--font-mono'],
      'a mono stack that names the UI family is not a mono stack',
    ).not.toContain('Space Grotesk')
  })

  it('pairs the numeric role with its font-variant-numeric companion (UX-DR3)', () => {
    // The `font` shorthand cannot carry font-variant-numeric, so a role token alone gives
    // proportional digits in a column of counts. The rule that fails the role applied without
    // the companion is `findUnpairedNumericRole` in tests/token-usage.test.ts; this is the
    // assertion that both tokens it points at still exist and still say what it expects.
    expect(tokens['--type-numeric-features']).toBe(design.typography.numeric.fontVariantNumeric)
    expect(tokens['--type-numeric-features']).toBe('tabular-nums')
  })

  it('carries the tracking companions the font shorthand cannot express', () => {
    expect(tokens['--tracking-display']).toBe(design.typography.display.letterSpacing)
    expect(tokens['--tracking-label']).toBe(design.typography.label.letterSpacing)
    expect(tokens['--tracking-micro']).toBe(design.typography.micro.letterSpacing)
  })

  it('ships 4 radii plus the card radius, which is a percentage pair', () => {
    const radii = Object.keys(tokens).filter((k) => k.startsWith('--radius-'))
    expect(radii).toHaveLength(5)
    for (const [key, value] of Object.entries(design.rounded)) {
      expect(normalise(tokens[`--radius-${key}`]), `--radius-${key}`).toBe(normalise(value))
    }
    // UX-DR4's card geometry is a ratio, not a length. Anything parsing radii must not
    // assume `px`; this assertion is here so that assumption fails loudly if it is ever made.
    expect(tokens['--radius-card']).not.toContain('px')
    expect(tokens['--radius-card']).toContain('%')
  })

  it('ships the 7-step spacing scale plus gutter and panel-gap, and no off-scale value', () => {
    const spacing = Object.keys(tokens).filter((k) => k.startsWith('--space-'))
    expect(spacing).toHaveLength(9)
    for (const [key, value] of Object.entries(design.spacing)) {
      expect(tokens[`--space-${key}`], `--space-${key}`).toBe(value)
    }
    // UX-DR5: the imported mock's 18/14/9/7px one-offs are drift, and this is the assertion
    // that says so — the scale is 4/8/12/16/24/32/48 and nothing else.
    expect(['1', '2', '3', '4', '5', '6', '7'].map((n) => tokens[`--space-${n}`])).toEqual([
      '4px',
      '8px',
      '12px',
      '16px',
      '24px',
      '32px',
      '48px',
    ])
  })

  it('ships 4 named durations and 3 easings', () => {
    const durations = Object.keys(tokens).filter((k) => k.startsWith('--motion-'))
    const easings = Object.keys(tokens).filter((k) => k.startsWith('--ease-'))
    expect(durations).toHaveLength(4)
    expect(easings).toHaveLength(3)

    const motion = design.components.motion
    for (const name of ['pulse', 'glide', 'bloom', 'aurora']) {
      expect(tokens[`--motion-${name}`], `--motion-${name}`).toBe(motion[name])
    }
    for (const name of ['ease-out', 'ease-glide', 'ease-snap']) {
      expect(normalise(tokens[`--${name}`]), `--${name}`).toBe(normalise(motion[name]))
    }
  })

  it('ships the focus ring as colour, width and offset', () => {
    const ring = design.components['focus-ring']
    expect(normalise(tokens['--focus-ring'])).toBe(normalise(ring.color))
    expect(tokens['--focus-ring-width']).toBe(ring.width)
    expect(tokens['--focus-ring-offset']).toBe(ring.offset)
  })

  it('ships the 3 elevation tokens, composites resolved', () => {
    const elevation = design.components.elevation
    expect(normalise(tokens['--shadow-raise'])).toBe(normalise(elevation['shadow-raise']))
    expect(normalise(tokens['--shadow-rest'])).toBe(normalise(elevation['shadow-rest']))
    // --glow is `0 0 16px var(--accent-glow)` here and `0 0 16px {colors.accent-glow}` there;
    // both sides resolve to the same rgba tuple before comparing, so the reference itself is
    // checked rather than waved through.
    expect(normalise(tokens['--glow'])).toBe(normalise(elevation.glow))
    expect(tokens['--glow']).toContain('var(--accent-glow)')
  })

  it("ships the card tile's focus-ring composite at DESIGN.md's value (c4-4, Q2)", () => {
    // Held to exactly the standard the three elevation tokens above are held to, and for the
    // same reason: the whole argument for a composite being a TOKEN rather than an inline
    // box-shadow is that the layer is the single source — which is worth nothing if the value
    // is not the artefact's. Both sides resolve their references before comparing, so
    // `{colors.focus-ring}` / `var(--focus-ring)` is checked rather than waved through.
    const tile = design.components['card-tile']
    expect(
      tile['focus-ring-over-art'],
      "DESIGN.md's components.card-tile has no focus-ring-over-art — did the artefact change shape?",
    ).toBeDefined()
    expect(normalise(tokens['--shadow-focus-ring-over-art'])).toBe(
      normalise(tile['focus-ring-over-art']),
    )
    // The two references are the POINT of the composite (it must survive a theme swap), so a
    // value that resolved correctly today by being written out in hex would still be wrong.
    expect(tokens['--shadow-focus-ring-over-art']).toContain('var(--focus-ring)')
    expect(tokens['--shadow-focus-ring-over-art']).toContain('var(--surface-base)')
  })

  it("ships the card tile's LIVE ring at DESIGN.md's value (c4-5, Q4 — the repaired pin)", () => {
    // THIS TEST READ "does NOT ship the live ring, because nothing sets `live` until c4-5", and
    // its own comment named this repair: *"if c4-5 adds the second, this test is the one that
    // tells its author the pin moves with it"*. It did exactly that, so it is REPAIRED rather
    // than deleted — deleting it would throw away the mechanism at the moment it worked, and
    // leave the next absent-by-design token with nothing to tell its story either.
    //
    // The assertion inverts and everything else about it stays: the artefact still has to
    // declare the value, and the token still has to equal it byte-for-byte with references
    // resolved on both sides.
    const tile = design.components['card-tile']
    expect(
      tile['live-ring'],
      "DESIGN.md's components.card-tile has no live-ring — did the artefact change shape?",
    ).toBeDefined()
    expect(normalise(tokens['--shadow-live-ring'])).toBe(normalise(tile['live-ring']))
    // `--accent`, NEVER `--accent-dim` — the M4/C3 correction, which lives in the artefact and
    // is asserted here so a "tidy-up" back to the dim tone fails rather than ships (UX-DR6).
    expect(tokens['--shadow-live-ring']).toContain('var(--accent)')
    expect(tokens['--shadow-live-ring']).not.toContain('var(--accent-dim)')
  })

  it("ships the detail panel's PINNED ring at DESIGN.md's amended value (c4-5, Q2)", () => {
    // THE ARTEFACT WAS AMENDED IN THIS COMMIT, and this assertion is what makes that visible
    // rather than convenient: DESIGN.md declared `pinned-ring: '0 0 0 1px {colors.accent-dim}'`
    // on a component whose `background` it declares as `{colors.surface-overlay}` — 2.70:1, the
    // pairing its own Colors table bans by name, and the identical defect the UX gate closed as
    // M4/C3 for the live ring above without carrying the fix across.
    //
    // Because this suite compares byte-for-byte against the frontmatter, the two ways to be
    // wrong are both loud: shipping `--accent` against an unamended artefact fails HERE, and
    // shipping `--accent-dim` to satisfy an unamended artefact ships a 2.70:1 indicator that no
    // guard could catch (`findAccentDimOnOverlay` is same-block only, and the background is the
    // PARENT `Panel`'s). Amending the artefact is the only repair that leaves both true.
    const detail = design.components['card-detail']
    expect(
      detail['pinned-ring'],
      "DESIGN.md's components.card-detail has no pinned-ring — did the artefact change shape?",
    ).toBeDefined()
    expect(normalise(tokens['--shadow-pinned-ring'])).toBe(normalise(detail['pinned-ring']))
    expect(tokens['--shadow-pinned-ring']).toContain('var(--accent)')
    expect(tokens['--shadow-pinned-ring']).not.toContain('var(--accent-dim)')
    // …and the artefact itself no longer names the banned tone on this component, which is the
    // half that stops the amendment being silently reverted upstream.
    expect(detail['pinned-ring']).not.toContain('accent-dim')
    expect(detail.background).toBe('{colors.surface-overlay}')
  })

  it("ships the deck row's LIVE RULE at DESIGN.md's value (c4-7, Q6)", () => {
    // The fourth hand-listed composite, and the first INSET one. It is a token for the reason the
    // three above are: .stylelintrc.json's box-shadow allowed-list admits `none` or a comma-list
    // of var(--shadow-…) / var(--glow) and nothing else, so `inset 2px 0 0 …` cannot be written
    // in DeckList.css at all.
    const row = design.components['deck-row']
    expect(
      row['live-rule'],
      "DESIGN.md's components.deck-row has no live-rule — did the artefact change shape?",
    ).toBeDefined()
    expect(normalise(tokens['--shadow-deck-row-live'])).toBe(normalise(row['live-rule']))
    // `inset` is the whole point — a `border-left` would shift every column 2px sideways on
    // becoming live, and a cursor sweeping a dense row list would read that as a shimmer.
    expect(tokens['--shadow-deck-row-live']).toContain('inset')
    // The M4/C3 ban, inherited rather than repaired: this is the one live marker in the app whose
    // artefact specified `{colors.accent}` correctly the first time, and this pins it there.
    expect(tokens['--shadow-deck-row-live']).toContain('var(--accent)')
    expect(tokens['--shadow-deck-row-live']).not.toContain('var(--accent-dim)')
    expect(row['live-rule']).not.toContain('accent-dim')
  })

  it("ships the suggestion row's LIVE RULE at DESIGN.md's amended value (c6-7, Q2, AC 3)", () => {
    // THE ARTEFACT WAS AMENDED IN THIS COMMIT, and this test is what makes the amendment
    // load-bearing rather than decorative — the mechanism c4-7's price-track test established.
    // `components.suggestion-row` carried four values and none of them was a marker, a padding
    // or a gap, while the component description below the frontmatter already promised a `live`
    // marker in `{colors.accent}`. The row is also on this file's own no-visual-precedent list,
    // so there were no mock pixels to read the missing values off.
    const row = design.components['suggestion-row']
    expect(
      row['live-rule'],
      "DESIGN.md's components.suggestion-row has no live-rule — was the c6-7 amendment reverted?",
    ).toBeDefined()
    expect(normalise(tokens['--shadow-suggestion-row-live'])).toBe(normalise(row['live-rule']))
    // Inset, for the deck row's reason: a `border-left` shifts every column 2px sideways on
    // becoming live and a cursor sweeping the list reads that as a shimmer.
    expect(tokens['--shadow-suggestion-row-live']).toContain('inset')

    // THE BAN, AT THE ONE SURFACE WHERE IT IS A REAL FAILURE RATHER THAN A WEAKNESS (AC 3).
    // This row's resting background is `surface-overlay`, where `accent-dim` measures 2.70:1 —
    // under the 3:1 non-text floor — and DESIGN.md's Contrast table names suggestion rows in
    // that ban explicitly. Pinned on BOTH sides, token and artefact, so neither can drift back.
    expect(tokens['--shadow-suggestion-row-live']).toContain('var(--accent)')
    expect(tokens['--shadow-suggestion-row-live']).not.toContain('var(--accent-dim)')
    expect(row['live-rule']).not.toContain('accent-dim')
    expect(
      row.background,
      'the ban above is only meaningful while this row actually sits on the overlay surface',
    ).toBe('{colors.surface-overlay}')

    // THE REST OF THE AMENDMENT, pinned because `SuggestionsView.css` cites these by name and a
    // citation to a value that has silently vanished is worse than no citation at all.
    expect(row.padding, 'components.suggestion-row.padding — added by c6-7 (Q2)').toBe(
      '{spacing.2} {spacing.3}',
    )
    // Two-value, matching `padding` above: `{spacing.3}` is the column gap (thumbnail to text),
    // `{spacing.2}` is the row gap (head line to reason line) — corrected by code review
    // (2026-08-11) from a single-value citation that named only the column half.
    expect(row.gap, 'components.suggestion-row.gap — added by c6-7 (Q2)').toBe(
      '{spacing.2} {spacing.3}',
    )
    // Content-driven, and that is the decision rather than a missing number: a fixed row height
    // would either crop the 63:88 thumbnail that spans the row or fix its width by arithmetic
    // done in a stylesheet. It carries no px, which is why the stylesheet needs none.
    expect(row.height, 'components.suggestion-row.height — added by c6-7 (Q2)').toContain(
      'content-driven',
    )
    expect(row.height).not.toMatch(/\d+px/)
  })

  it('carries a treatment for the empty PUSH line, not only the empty DECK line (c6-7, Q2)', () => {
    // ADDED IN THIS COMMIT, discharging `deferred-work.md:22` at the story the ledger homed it
    // on by name. c6-6 shipped the empty-push state against `empty-deck-line`'s values, CITED,
    // and declined to amend an artefact nobody had asked it to amend; this story amends the
    // suggestion-row block anyway, so the sibling's block is one entry of the same amendment.
    const line = design.components['empty-push-line']
    expect(
      line,
      'DESIGN.md has no components.empty-push-line — was the c6-7 amendment reverted? (deferred-work.md:22)',
    ).toBeDefined()

    // THE SIBLING TEST, and it is the point: these two states are the same kind of thing — one
    // calm sentence standing in for absent content inside a surface that supplies its own
    // padding — so a divergence in type role or colour between them is a defect, not a choice.
    const deckLine = design.components['empty-deck-line']
    expect(line.type).toBe(deckLine.type)
    expect(line.foreground).toBe(deckLine.foreground)
    expect(line.type).toBe('{typography.body}')
    expect(line.foreground).toBe('{colors.text-secondary}')

    // IT SPENDS NO LENGTH OF ITS OWN. No px anywhere in the block, and no min-height: reserving
    // list-sized space for content that is deliberately absent is what makes an empty state
    // read as a loading failure.
    expect(JSON.stringify(line)).not.toMatch(/\d+px/)
    expect(Object.keys(line).sort()).toEqual(['container', 'foreground', 'type'])

    // THE CONTAINER CITES THE BODY'S OWN INSET, NOT THE SHELL'S (code review, 2026-08-11): the
    // two are different tokens — `{components.agent-view.inset}` is `{spacing.6}`, the shell's
    // distance from the window edge, while `.agent-view-body`'s actual padding is `{spacing.4}`.
    // A citation naming the wrong one is exactly the drift this suite exists to catch.
    expect(line.container).toBe('the agent view body — {spacing.4} is the whole of its inset')
  })

  it('has no price track left in the deck row, and the artefact says why (c4-7, Q1, AC 12)', () => {
    // THE ARTEFACT WAS AMENDED IN THIS COMMIT (Q1), and this is the assertion that makes it
    // visible rather than convenient — the same mechanism the pinned-ring amendment above uses.
    //
    // The fourth track reserved 64px for a right-aligned PRICE. Measured at `d51b467`: `cards`
    // has 23 columns and none is a price, no schema declares one, and the Scryfall importer never
    // reads the `prices` object at all — the data was never imported rather than dropped.
    // `tests/unit/companion/test_routes_cards.py:136` asserts that absence on purpose.
    const row = design.components['deck-row']
    // `minmax(34px, max-content)`, not a bare `34px` (c4-7 review ruling): 34 is the corpus
    // maximum quantity, which is a measurement and not a bound — an unlimited-copy import
    // (×100 Relentless Rats) must widen the track rather than clip into the name column.
    expect(row.columns).toBe('minmax(34px, max-content) minmax(0, 1fr) auto')
    expect(row.columns).not.toContain('64px')
    // …and the bare `1fr` could not have shipped either — `shell.test.ts:960` bans a
    // content-floored track, and `minmax(0, 1fr)` is that guard's own named correct form.
    expect(row.columns).not.toMatch(/(^|\s)1fr(\s|$)/)
  })

  it('declares every token in one themeable block (AC 2)', () => {
    // The MVP ships Voltglass only, but an alternate `[data-theme="…"]` block must be
    // addable later without touching a single component stylesheet. That is only true if
    // the selector already carries the theme attribute today.
    expect(tokensSource).toMatch(/:root,\s*\[data-theme='voltglass']\s*\{/)
  })
})

describe('the normalisers themselves (they are load-bearing)', () => {
  // A comparison helper that silently returns the same value for everything turns every
  // assertion above into a tautology. These fix its behaviour in both directions.
  it('reads every notation of the same colour as the same colour', () => {
    expect(parseColour('#0D0F1A')).toEqual([13, 15, 26, 1])
    expect(parseColour('#0d0f1a')).toEqual([13, 15, 26, 1])
    expect(parseColour('rgb(13 15 26)')).toEqual([13, 15, 26, 1])
    expect(parseColour('rgba(8,9,18,0.75)')).toEqual([8, 9, 18, 0.75])
    expect(parseColour('rgb(8 9 18 / 75%)')).toEqual([8, 9, 18, 0.75])
    expect(parseColour('#fff')).toEqual([255, 255, 255, 1])
  })

  it('reads a DIFFERENT colour as different — one digit is enough', () => {
    expect(parseColour('#0d0f1b')).not.toEqual(parseColour('#0d0f1a'))
    expect(normalise('#0d0f1b')).not.toBe(normalise('rgba(13,15,26,1)'))
    expect(normalise('rgb(8 9 18 / 74%)')).not.toBe(normalise('rgba(8,9,18,0.75)'))
  })

  it('collapses only cosmetic differences', () => {
    expect(normalise('cubic-bezier(0.25, 0.1, 0.25, 1)')).toBe(
      normalise('cubic-bezier(0.25,0.1,0.25,1)'),
    )
    expect(normalise('cubic-bezier(0.25,0.1,0.25,1)')).not.toBe(
      normalise('cubic-bezier(0.4,0,0.2,1)'),
    )
  })
})
