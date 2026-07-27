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
  rounded: Record<string, string>
  spacing: Record<string, string>
  components: {
    motion: Record<string, string>
    'focus-ring': Record<string, string>
    elevation: Record<string, string>
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
      Object.keys(tokens).length,
      'the :root block of tokens.css parsed to nothing — did the selector or comment syntax change?',
    ).toBeGreaterThan(50)
  })

  it('declares exactly the inventory and nothing else', () => {
    // Set equality both ways: a missing token fails, and so does a smuggled-in extra one
    // that no story wrote down.
    expect(new Set(Object.keys(tokens))).toEqual(new Set(expectedNames))
    expect(expectedNames).toHaveLength(64)
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

  it('pairs the numeric role with its font-variant-numeric companion (UX-DR3)', () => {
    // The `font` shorthand cannot carry font-variant-numeric, so a role token alone gives
    // proportional digits in a column of counts. c2-5 adds the rule that catches the role
    // being applied without the companion; both tokens have to exist for it to point at.
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
