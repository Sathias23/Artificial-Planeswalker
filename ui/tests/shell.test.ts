/**
 * The application shell's geometry, made a gate (story c2-6).
 *
 * READ THE CSS SOURCE, NEVER A RENDERED DOM. jsdom has no layout engine: it resolves no grid
 * tracks, evaluates no media queries and returns no box geometry, so every `getComputedStyle`
 * assertion about a width, a track or a breakpoint would report nothing and pass for the
 * wrong reason. That trap is the obvious way to write this file, which is why the rule is
 * stated before the first import — the same rule the reduced-motion block in
 * tests/token-usage.test.ts states about itself.
 *
 * Four things here are guards over EVERY shipped stylesheet rather than checks on one file,
 * because each of them describes a defect a later story would introduce somewhere else:
 *
 *   AC 2  — a bare `<n>fr` grid track. `1fr` IS `minmax(auto, 1fr)`, and `auto` floors at
 *           min-content, so one unbreakable child pushes the track past its share and the
 *           grid overflows the window. It is AC 5's defect arriving through the one spelling
 *           that looks correct.
 *   AC 6  — `overflow: hidden`/`clip` on a ROOT element. It makes "the body never scrolls
 *           horizontally" true by CLIPPING the overflowing content rather than fitting it, so
 *           the bug survives, invisible, and the acceptance criterion reports success.
 *   AC 10 — a second full-window fixed layer. UX-DR38 fixes the overlay stack at exactly one
 *           level deep; a second component declaring its own is how that stops being true,
 *           and no value-level rule objects because every declaration involved is legal.
 *   (+)   — a viewport height on the DOCUMENT root. The shell owns the window height at
 *           100dvh; a `body { min-height: 100vh }` beside it is a second, disagreeing height
 *           mechanism, and `vh` is the LARGE viewport height, so the two differ exactly where
 *           it matters.
 *
 * BAN THE FAMILY, NEVER ENUMERATE MEMBERS. Each guard keys on a property FAMILY and a value
 * SHAPE, and the fixture proves it with spellings this file never lists — `overflow-block`,
 * `grid-auto-rows`, the two-value `overflow: hidden auto`, a full-window layer built from four
 * physical longhands and one built from viewport units alone. A guard proven only against the
 * members its own author thought of is an enumeration test wearing a family test's clothes.
 *
 * WHAT THESE GUARDS CANNOT SEE, declared in the same breath as the guards themselves. They
 * are static readers of CSS source. A full-window layer composed at runtime from two classes
 * on one element, a root selector reached through a class this file does not recognise as
 * root, or an overflow set from JavaScript are all invisible here — the render tree lives in
 * TSX and is chosen at runtime. **Review owns that half**, the same split
 * tests/token-usage.test.ts declares for its contrast and numeric-pairing guards.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

/** The one stylesheet allowed to declare the full-window overlay layer (AC 10). */
const SHELL_CSS = 'src/components/AppShell/AppShell.css'
const SHELL_TSX = 'src/components/AppShell/AppShell.tsx'

// git is the file authority, not readdir: it cannot see node_modules, dist or coverage, and a
// stray stylesheet is caught the moment it is committed — which is when CI sees it. A guard
// written against an UNTRACKED file passes vacuously; c2-4 and c2-5 both lost time to that.
//
// `'*.css'` then filter, NOT the pathspec `'src/**/*.css'`. Measured while writing this file:
// git's wildmatch requires `**` to consume at least one path component, so `src/**/*.css`
// returns the three NESTED stylesheets and silently omits `src/index.css` — the file carrying
// the box-sizing reset and the very thing the anchor below is meant to prove is being read.
// The non-vacuity anchor caught it on the first run, which is what anchors are for.
const shippedStylesheets = execFileSync('git', ['ls-files', '*.css'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((f) => f.startsWith('src/'))

const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

// ---------------------------------------------------------------------------------------
// A minimal CSS reader. Deliberately the same shape as the one in token-usage.test.ts, and
// safe for the same reason: native CSS nesting is BANNED in shipped stylesheets by a guard
// there, so a declaration can never sit in a nesting parent where innermost-brace matching
// would miss it. If that ban is ever lifted, both readers become PostCSS at once.
// ---------------------------------------------------------------------------------------

interface Block {
  file: string
  selector: string
  body: string
}

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '')

const commentsIn = (css: string): string[] => css.match(/\/\*[\s\S]*?\*\//g) ?? []

const blocksIn = (file: string, css: string): Block[] =>
  [...stripComments(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => ({
    file,
    selector: match[1].trim().replace(/\s+/g, ' '),
    body: match[2],
  }))

/** Declarations of one block as `[property, value]`, lowercased, `!important` dropped. */
const declarationsIn = (body: string): [string, string][] =>
  body
    .split(';')
    .filter((decl) => decl.includes(':'))
    .map((decl) => {
      const colon = decl.indexOf(':')
      return [
        decl.slice(0, colon).trim().toLowerCase(),
        decl
          .slice(colon + 1)
          .replace(/!important\s*$/i, '')
          .trim()
          .replace(/\s+/g, ' '),
      ] as [string, string]
    })

const valueOf = (block: Block, property: string): string | undefined =>
  declarationsIn(block.body).find(([p]) => p === property)?.[1]

const has = (block: Block, property: RegExp): boolean =>
  declarationsIn(block.body).some(([p]) => property.test(p))

/**
 * Every viewport-relative length unit, as a FAMILY rather than a list: an optional dynamic /
 * small / large prefix, `v`, then one of the six axes. `100vw`, `100dvh`, `50svh`, `40lvmin`
 * and `100vi` all match; `100%`, `100px` and `100em` do not.
 */
const VIEWPORT_UNIT = /\b\d*\.?\d+(?:[dsl]?v(?:w|h|i|b|min|max))\b/i

const HORIZONTAL_SIZE = /^(?:min-|max-)?(?:width|inline-size)$/
const VERTICAL_SIZE = /^(?:min-|max-)?(?:height|block-size)$/

/** A selector part naming the DOCUMENT root — the thing the shell must not fight. */
const DOCUMENT_ROOT = /(^|[\s>+~])(html|body|:root|#root)(?![\w-])/
/** The shell's own root element. `.app-shell-columns` deliberately does NOT match. */
const SHELL_ROOT = /(^|[\s>+~])\.app-shell(?![\w-])/

const selectorParts = (selector: string) => selector.split(',').map((part) => part.trim())

const matchesAnyPart = (selector: string, pattern: RegExp) =>
  selectorParts(selector).some((part) => pattern.test(part))

// ---------------------------------------------------------------------------------------
// The guards
// ---------------------------------------------------------------------------------------

/**
 * AC 2 — a flexible grid track whose MINIMUM is content-derived.
 *
 * Two shapes, one defect. A bare `1fr` is shorthand for `minmax(auto, 1fr)`; an explicit
 * `minmax(auto, 1fr)` or `minmax(min-content, 1fr)` says the same thing out loud. Both floor
 * the track at min-content, so an unbreakable child widens it past its share.
 *
 * `minmax(176px, 1fr)` — c4-4's card grid — is the CORRECT form and must stay silent: its
 * minimum is a real length the author chose, not one the content dictates.
 */
const findContentFlooredTrack = (blocks: Block[]): string[] => {
  const TRACK_PROPERTY = /^grid(?:-(?:template|auto))?(?:-(?:columns|rows))?$/
  const CONTENT_MINIMUM = /^(auto|min-content)$/i
  const advice =
    'A flexible track floored at min-content grows past its share for one unbreakable child ' +
    '(a long card name, a wide table, a <pre>) and the grid overflows the window. Write ' +
    'minmax(0, 1fr) — or a real length minimum, as c4-4s card grid does with minmax(176px, 1fr).'

  const findings: string[] = []
  for (const block of blocks) {
    for (const [property, value] of declarationsIn(block.body)) {
      if (!TRACK_PROPERTY.test(property)) continue
      const where = `${block.file} — \`${block.selector}\` (${property})`

      // An explicit content minimum, said out loud.
      for (const minmax of value.matchAll(/minmax\(([^()]*)\)/gi)) {
        const min = minmax[1].split(',')[0].trim()
        if (CONTENT_MINIMUM.test(min)) {
          findings.push(`${where}: \`minmax(${minmax[1]})\` floors the track at ${min}. ${advice}`)
        }
      }

      // A bare `<n>fr` outside any minmax() is the same thing, spelled shorter.
      const outsideMinmax = value.replace(/minmax\([^()]*\)/gi, '')
      if (/\b\d*\.?\d+fr\b/i.test(outsideMinmax)) {
        findings.push(`${where}: \`${value}\` uses a bare fr track. ${advice}`)
      }
    }
  }
  return findings
}

/**
 * AC 6 — `overflow: hidden` / `clip` on a root element.
 *
 * Keyed on the overflow property FAMILY and on the two clipping values, over the root
 * selectors only. Deliberately NARROW: `overflow-y: auto` on the shell's content region is the
 * app's one legitimate scroll container, and c4-5's detail panel and c6-5's overlay clip on
 * purpose. A blanket ban would be a gate three later stories have to fight, which is a worse
 * outcome than the defect it would prevent.
 */
const findClippedRoot = (blocks: Block[]): string[] => {
  const OVERFLOW_PROPERTY = /^overflow(?:-(?:x|y|block|inline))?$/
  const CLIPS = /(^|\s)(hidden|clip)(\s|$)/i

  return blocks
    .filter(
      (b) => matchesAnyPart(b.selector, DOCUMENT_ROOT) || matchesAnyPart(b.selector, SHELL_ROOT),
    )
    .flatMap((block) =>
      declarationsIn(block.body)
        .filter(([property, value]) => OVERFLOW_PROPERTY.test(property) && CLIPS.test(value))
        .map(
          ([property, value]) =>
            `${block.file} — \`${block.selector}\` sets \`${property}: ${value}\` on a root ` +
            `element. That makes "the body never scrolls horizontally" true by CLIPPING the ` +
            `overflowing content instead of fitting it: the defect survives, invisible, and the ` +
            `acceptance criterion reports success. Fix the track that overflows — usually a ` +
            `bare 1fr or a missing min-width: 0 — rather than hiding it.`,
        ),
    )
}

/**
 * AC 10 / UX-DR38 — a full-window FIXED layer, in every shape that covers the window.
 *
 * "Full-window" means anchored on both axes (by `inset`, by the logical pairs, by the four
 * physical longhands, or by any mix of those) OR sized to the viewport on both axes. A pill
 * pinned to one corner and a bar docked to one edge are neither, and both stay silent — c5-7
 * and a future docked bar are not this rule's business.
 *
 * `position: absolute` is deliberately NOT this shape. An absolute cover inside a positioned
 * parent is a panel's own veil, not a level of the overlay stack.
 */
const findFullWindowFixedLayers = (blocks: Block[]): Block[] =>
  blocks.filter((block) => {
    if (!/(^|\s)fixed(\s|$)/i.test(valueOf(block, 'position') ?? '')) return false

    const anchored =
      has(block, /^inset$/) ||
      ((has(block, /^(inset|inset-block)$/) ||
        (has(block, /^(inset-block-start|top)$/) && has(block, /^(inset-block-end|bottom)$/))) &&
        (has(block, /^(inset|inset-inline)$/) ||
          (has(block, /^(inset-inline-start|left)$/) && has(block, /^(inset-inline-end|right)$/))))

    const viewportSized =
      declarationsIn(block.body).some(
        ([p, v]) => HORIZONTAL_SIZE.test(p) && VIEWPORT_UNIT.test(v),
      ) &&
      declarationsIn(block.body).some(([p, v]) => VERTICAL_SIZE.test(p) && VIEWPORT_UNIT.test(v))

    return anchored || viewportSized
  })

const findUnconfinedOverlays = (blocks: Block[]): string[] =>
  findFullWindowFixedLayers(blocks)
    .filter((block) => block.file !== SHELL_CSS)
    .map(
      (block) =>
        `${block.file} — \`${block.selector}\` declares a full-window fixed layer. UX-DR38 ` +
        `fixes the overlay stack at EXACTLY ONE level deep, and ${SHELL_CSS} already owns it ` +
        `(.app-shell-overlay). Render into the shell's overlay slot instead of declaring a ` +
        `second one; every declaration in a block like this is legal CSS, so nothing else ` +
        `objects.`,
    )

/** The shell owns the window height; the document root must not declare a second one. */
const findViewportHeightOnDocumentRoot = (blocks: Block[]): string[] =>
  blocks
    .filter((b) => matchesAnyPart(b.selector, DOCUMENT_ROOT))
    .flatMap((block) =>
      declarationsIn(block.body)
        .filter(([property, value]) => VERTICAL_SIZE.test(property) && VIEWPORT_UNIT.test(value))
        .map(
          ([property, value]) =>
            `${block.file} — \`${block.selector}\` sets \`${property}: ${value}\`. The shell ` +
            `owns the window height at 100dvh (Q2); a viewport height on the document root is ` +
            `a second, disagreeing mechanism — and \`vh\` is the LARGE viewport height, so on a ` +
            `browser with retracting chrome the page grows taller than the window and the ` +
            `pinned footer scrolls out of it.`,
        ),
    )

// ---------------------------------------------------------------------------------------

const shippedBlocks = shippedStylesheets.flatMap((f) => blocksIn(f, sourceOf(f)))
const shellSource = sourceOf(SHELL_CSS)
const shellBlocks = blocksIn(SHELL_CSS, shellSource)
const blockFor = (selector: string) => shellBlocks.find((b) => b.selector === selector)

describe('the shell stylesheet is read at all (the non-vacuity anchor)', () => {
  // Every guard below filters these lists. An empty one — a wrong cwd, a git call resolving
  // another tree, a file staged too late — would make all four pass by finding nothing at
  // all, which is the failure mode c2-3's review found in every guard it looked at.
  it('is reading real, tracked stylesheets', () => {
    expect(shippedStylesheets).toContain('src/styles/tokens.css')
    expect(shippedStylesheets).toContain('src/index.css')
    expect(shippedStylesheets).toContain(SHELL_CSS)
    expect(shippedBlocks.length).toBeGreaterThan(10)
    expect(shellBlocks.length).toBeGreaterThan(8)
  })
})

describe('the composition (AC 1, AC 2, AC 3, AC 4 — the machine-verifiable half)', () => {
  it('frames the window with the gutter token and separates regions by the panel-gap token', () => {
    // AC 1, mechanically: neither distance is a literal. Their VALUES (32px, 24px) are pinned
    // against DESIGN.md's frontmatter by tests/tokens.test.ts, so this file does not restate
    // them — that would be a second copy to drift.
    const root = blockFor('.app-shell')
    expect(root).toBeDefined()
    expect(valueOf(root!, 'padding')).toBe('var(--space-gutter)')
    expect(valueOf(root!, 'gap')).toBe('var(--space-panel-gap)')

    const columns = blockFor('.app-shell-columns')
    expect(valueOf(columns!, 'gap')).toBe('var(--space-panel-gap)')
    // Panels FLOAT: the separation INSIDE a column is the same distance as between them.
    expect(valueOf(blockFor('.app-shell-column')!, 'gap')).toBe('var(--space-panel-gap)')
  })

  it('pins the 452px track and the fluid track beside it (AC 2, AC 4)', () => {
    // If a later edit "tidies" either half of this, it fails here rather than drifting.
    expect(valueOf(blockFor('.app-shell-columns')!, 'grid-template-columns')).toBe(
      'minmax(0, 1fr) 452px',
    )
  })

  it('drops the right column beneath the left below 1100px, in the CONTEXT range form (AC 3)', () => {
    // The `max-width` spelling is a stylelint ERROR (media-feature-range-notation, from
    // stylelint-config-standard), so this is a gate rather than a style preference — but the
    // VALUE is this test's to pin, because lint has no opinion about which number it is.
    // COMMENTS STRIPPED FIRST. This file's own prose quotes the banned `@media (max-width:
    // 1099px)` spelling in order to warn about it, and the first version of this assertion
    // read that comment and failed — a guard that cannot tell code from the documentation
    // about the code is a guard that punishes writing the documentation.
    const shellCode = stripComments(shellSource)
    expect(shellCode).toMatch(/@media\s*\(\s*width\s*<\s*1100px\s*\)/)
    expect(shellCode).not.toMatch(/@media[^{]*(max-width|min-width)/)

    // And the collapsed track is still floored at zero — the single-column form is exactly
    // where a bare `1fr` looks harmless.
    const collapsed = shellBlocks.filter(
      (b) => b.selector === '.app-shell-columns' && valueOf(b, 'grid-template-columns'),
    )
    expect(collapsed).toHaveLength(2) // the base rule and the one inside the media query
    expect(valueOf(collapsed[1], 'grid-template-columns')).toBe('minmax(0, 1fr)')
  })

  it('floors both the track AND the grid item at zero (AC 2, AC 5)', () => {
    // Two halves of one argument: a grid ITEM also defaults to min-content, so the overflow
    // comes straight back through the child if only the track says it.
    expect(valueOf(blockFor('.app-shell-column')!, 'min-width')).toBe('0')
  })
})

describe('the scroll, and the pinned footer (AC 11, AC 12, AC 13)', () => {
  it('makes the shell exactly one window tall, in dvh (Q2)', () => {
    expect(valueOf(blockFor('.app-shell')!, 'height')).toBe('100dvh')
  })

  it('gives the content region the scroll, and lets it shrink (AC 12)', () => {
    const columns = blockFor('.app-shell-columns')!
    expect(valueOf(columns, 'overflow-y')).toBe('auto')
    // THE ONE-LINE OMISSION WHOSE SYMPTOM POINTS SOMEWHERE ELSE. Without `min-height: 0` a
    // flex child refuses to shrink below its content, its overflow never engages, the PAGE
    // scrolls instead, and the footer leaves the window — reported as a footer bug.
    expect(valueOf(columns, 'min-height')).toBe('0')
    expect(valueOf(columns, 'flex')).toBe('1')
  })

  it('keeps the header and the footer at their content height (AC 11)', () => {
    // The mechanism, asserted rather than left to inspection: the content region is the only
    // child that gives ground, so the footer's visibility is a property of the LAYOUT and not
    // of how much content happens to be on screen. UX-DR32 and NFR-08 make that a release
    // condition, which is why it is a mechanism and not a preference.
    expect(valueOf(blockFor('.app-shell-header')!, 'flex-shrink')).toBe('0')
    expect(valueOf(blockFor('.app-shell-footer')!, 'flex-shrink')).toBe('0')
  })

  it('ships a global box-sizing reset (AC 13)', () => {
    // There was NONE anywhere in ui/ before this story. Under the `content-box` default the
    // shell would be 100dvh + 64px — the gutter added to the height rather than inside it —
    // and the window would scroll. It presents as a footer bug and is not one.
    const reset = blocksIn('src/index.css', sourceOf('src/index.css')).find(
      (b) => b.selector.includes('*') && valueOf(b, 'box-sizing') === 'border-box',
    )
    expect(reset, 'no universal box-sizing: border-box rule in src/index.css').toBeDefined()
    // It must cover pseudo-elements too — they are boxes, and ::before/::after carry padding
    // and borders in every component from c2-7 onwards.
    expect(reset!.selector).toContain('::before')
    expect(reset!.selector).toContain('::after')
  })

  it('lets no document root declare a competing viewport height', () => {
    expect(findViewportHeightOnDocumentRoot(shippedBlocks)).toEqual([])
  })
})

describe('the overlay slot (AC 7, AC 8, AC 10)', () => {
  it('is inset by the gutter token, not a literal (AC 7)', () => {
    expect(valueOf(blockFor('.app-shell-overlay')!, 'inset')).toBe('var(--space-6)')
  })

  it('is FIXED, not absolute (AC 8)', () => {
    // The composition reference is a fixed 1720x1440 slab where absolute and fixed coincide,
    // and its own overlay is `position: absolute`. A real document is TALLER than the window,
    // so absolute would size this to the document: it would scroll away with the page and put
    // its 32px inset nowhere near the window edge. Copying the mock here is the single most
    // likely way to hand c6-5 a broken foundation.
    expect(valueOf(blockFor('.app-shell-overlay')!, 'position')).toBe('fixed')
  })

  it('is the ONLY full-window fixed layer in the app (AC 10, UX-DR38)', () => {
    expect(findUnconfinedOverlays(shippedBlocks)).toEqual([])
    // And exactly one inside the shell's own stylesheet — confinement to a FILE would still
    // admit a second layer declared beside the first.
    const inShell = findFullWindowFixedLayers(shellBlocks)
    expect(inShell.map((b) => b.selector)).toEqual(['.app-shell-overlay'])
  })
})

describe('the real tree is clean under every guard', () => {
  it('has no content-floored grid track anywhere (AC 2)', () => {
    expect(findContentFlooredTrack(shippedBlocks)).toEqual([])
  })

  it('clips no root element (AC 6)', () => {
    expect(findClippedRoot(shippedBlocks)).toEqual([])
  })
})

describe('geometry literals are documented, not merely tolerated (AC 18)', () => {
  // The decide-once ruling this story sets: a geometry literal is ALLOWED — there is no token
  // family to point at, `declaredTokens.size === 64` is pinned and DESIGN.md's frontmatter is
  // asserted byte-for-byte, so adding one is not available — and it carries a comment naming
  // its source and why it is not a token. c2-7 (17px StatChip), c2-9 (480px state panel) and
  // c4-4 (176px grid minimum) inherit a stated rule rather than a habit.
  const comments = commentsIn(shellSource)

  // DERIVED FROM THE CODE, not from a list. Every `<n>px` length in a declaration value or an
  // at-rule prelude has to be accounted for, so a literal a LATER story adds is required to
  // carry its source without anyone remembering to extend this test. Scope stated plainly:
  // px lengths only. `z-index: 20` is also a geometry literal and is documented in prose
  // beside its rule, but a bare unitless number cannot be told apart from the ones in
  // `minmax(0, 1fr)`, `flex: 1` and `min-width: 0`, so it is review's rather than this
  // guard's.
  const literalsInCode = [...new Set(stripComments(shellSource).match(/\b\d+px\b/g) ?? [])]

  /**
   * PROXIMITY, not co-occurrence. The first version of this asked only whether SOME comment
   * mentioned the literal and SOME part of it said "DESIGN.md" — and the probe that deleted
   * the real citation still passed, because the file-header comment happens to contain both
   * the phrase "the 452px track" and a reference to DESIGN.md's frontmatter four hundred
   * characters away. A guard satisfied by something other than the thing it is checking is
   * exactly the defect this epic's reviews have found in every round; requiring the citation
   * to sit within one sentence of the value is what makes it check the citation.
   */
  const documented = (literal: string) =>
    comments.some((comment) =>
      [...comment.matchAll(new RegExp(literal.replace('.', '\\.'), 'g'))].some((match) => {
        const near = comment.slice(Math.max(0, match.index - 60), match.index + 60)
        return near.includes('DESIGN.md')
      }),
    )

  it('sources every px literal in the stylesheet to DESIGN.md, beside the value', () => {
    // The non-vacuity half: there ARE literals to check, and they are the two the composition
    // is made of. If this list ever shrinks to nothing the assertion below is meaningless.
    expect(literalsInCode.sort()).toEqual(['1100px', '452px'])

    for (const literal of literalsInCode) {
      expect(
        documented(literal),
        `${literal} appears in the stylesheet with no DESIGN.md citation within a sentence of it`,
      ).toBe(true)
    }
  })

  it('says, in the file, why these are not tokens', () => {
    expect(shellSource).toContain('AC 18')
    expect(shellSource).toMatch(/not a token|NON-BAN/i)
  })
})

describe('the shell is presentation-only, and that is asserted (AC 16)', () => {
  const shellComponent = sourceOf(SHELL_TSX)
  const importedFrom = [...shellComponent.matchAll(/from\s+'([^']+)'/g)].map((m) => m[1])

  it('imports nothing but React types and its own stylesheet', () => {
    // A store import, a fetch helper or a hooks module would each pre-empt a design c3-1 and
    // c4-1 own. Asserted as an exhaustive list rather than a blocklist: a module nobody
    // thought to ban is exactly the one that would get through.
    expect(importedFrom.sort()).toEqual(['react'])
    expect(shellComponent).toContain("import './AppShell.css'")
  })

  it('holds no state and subscribes to nothing', () => {
    // Keyed on the React state/effect API family rather than on named hooks, so a hook this
    // list never heard of is still caught.
    expect(shellComponent).not.toMatch(/\buse[A-Z]\w*\s*\(/)
    expect(shellComponent).not.toMatch(/\b(fetch|XMLHttpRequest|EventSource|WebSocket)\s*\(/)
  })
})

// ---------------------------------------------------------------------------------------
// The other half of every pair: each guard proven FIRING, on spellings it does not enumerate
// ---------------------------------------------------------------------------------------

describe('the guards themselves fire', () => {
  const violation = blocksIn(
    'tests/fixtures/css/shell-violation.css',
    readFileSync(join(uiRoot, 'tests/fixtures/css/shell-violation.css'), 'utf8'),
  )

  it('is reading the fixture (its own non-vacuity anchor)', () => {
    expect(violation.length).toBeGreaterThan(15)
  })

  it('catches every content-floored track, including the shapes it never lists (AC 2)', () => {
    const joined = findContentFlooredTrack(violation).join('\n')

    expect(joined).toContain('.bare-fr-track')
    expect(joined).toContain('.explicit-auto-minimum') // minmax(auto, 1fr), said out loud
    expect(joined).toContain('.bare-fr-in-repeat') // hidden one level down, and on the row axis
    expect(joined).toContain('.min-content-minimum') // the same floor under another name
    // THE UNENUMERATED PROPERTY: `grid-auto-rows` is nowhere in this file's prose, and the
    // property FAMILY regex catches it anyway. This is the assertion that makes the guard a
    // family test rather than an enumeration test.
    expect(joined).toContain('.bare-fr-in-auto-tracks')

    // The message names its fix — a developer who trips it must not have to read the story.
    for (const finding of findContentFlooredTrack(violation)) {
      expect(finding).toContain('minmax(0, 1fr)')
    }
  })

  it('leaves a real-length minimum alone — c4-4s card grid is the CORRECT form', () => {
    // The silent half, on a block that genuinely uses `fr`. A guard proven only on blocks
    // with no grid template at all would be silent for the wrong reason.
    const legal = violation.filter((b) => b.selector === '.legal-card-grid')
    expect(legal).toHaveLength(1)
    expect(findContentFlooredTrack(legal)).toEqual([])
  })

  it('catches every clipped root, including the shapes it never lists (AC 6)', () => {
    const findings = findClippedRoot(violation)
    const joined = findings.join('\n')

    expect(joined).toContain('body')
    expect(joined).toContain('html')
    expect(joined).toContain(':root')
    // UNENUMERATED PROPERTY — the logical longhand appears in no list in this file.
    expect(joined).toContain('overflow-block')
    // UNENUMERATED VALUE SHAPE — the two-value shorthand, where the banned keyword is not the
    // whole value. A `^hidden$` anchor reads it as clean; c2-5's review found the identical
    // evasion three times, in three different guards.
    expect(joined).toContain('hidden auto')
    expect(findings.length).toBe(5)

    for (const finding of findings) {
      expect(finding).toContain('CLIPPING')
    }
  })

  it('leaves the legitimate scroll and the legitimate clip alone (AC 6, narrow by design)', () => {
    // Two different reasons to stay silent, and BOTH have to hold: `.legal-scroller` is not a
    // root selector and its value is `auto`; `.legal-clipping-panel` clips, but is not a root.
    // c4-5's detail panel and c6-5's overlay are the real components behind that second one.
    const legal = violation.filter((b) =>
      ['.legal-scroller', '.legal-clipping-panel'].includes(b.selector),
    )
    expect(legal).toHaveLength(2)
    expect(findClippedRoot(legal)).toEqual([])
  })

  it('catches a second full-window layer in all four spellings (AC 10)', () => {
    const findings = findUnconfinedOverlays(violation)
    const joined = findings.join('\n')

    expect(joined).toContain('.second-overlay') // inset shorthand
    expect(joined).toContain('.second-overlay-logical') // inset-block + inset-inline
    expect(joined).toContain('.second-overlay-longhands') // four physical longhands
    // NOT ANCHORED AT ALL — sized to the viewport instead. An inset-only check misses it
    // entirely, which is why the shape has two halves.
    expect(joined).toContain('.second-overlay-by-viewport-units')
    expect(findings).toHaveLength(4)

    for (const finding of findings) {
      expect(finding).toContain('UX-DR38')
      expect(finding).toContain('overlay slot')
    }
  })

  it('leaves a corner pill, a docked bar and an absolute cover alone (AC 10, narrow by design)', () => {
    // c5-7's connection pill is fixed and pinned to a corner; a docked bar spans one axis;
    // an absolute cover inside a positioned parent is a panel's own veil. None of them is a
    // level of the overlay stack, and a guard that flagged them would be one three stories
    // have to fight.
    const legal = violation.filter((b) =>
      ['.legal-corner-pill', '.legal-docked-bar', '.legal-absolute-cover'].includes(b.selector),
    )
    expect(legal).toHaveLength(3)
    expect(findFullWindowFixedLayers(legal)).toEqual([])
  })

  it('catches a viewport height on the document root', () => {
    // The exact line this story removed from src/index.css, plus the dynamic-unit spelling of
    // it, so the guard is not anchored on `vh` alone.
    const planted = blocksIn(
      'inline',
      `body { min-height: 100vh; }
       html { height: 100lvh; }
       .app-shell { height: 100dvh; }`,
    )
    const findings = findViewportHeightOnDocumentRoot(planted)
    expect(findings).toHaveLength(2)
    expect(findings.join('\n')).toContain('100vh')
    expect(findings.join('\n')).toContain('100lvh')
    // The shell's own 100dvh is the mechanism, not the defect — it must stay silent.
    expect(findings.join('\n')).not.toContain('.app-shell')
  })
})
