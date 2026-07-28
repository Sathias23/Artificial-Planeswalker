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
 * TSX and is chosen at runtime. So is `var()` INDIRECTION: `overflow: var(--clip)` with the
 * keyword hidden in a custom property declared elsewhere evades every value-keyed check,
 * because resolving it needs the cascade. And so is the CROSS-BLOCK cascade: a correct
 * declaration undone by a later rule block with higher specificity (within ONE block the
 * readers below take the LAST declaration, as the cascade does).
 *
 * Three more, added by the second review round rather than discovered later:
 *
 *   THE TOP LAYER. A native `<dialog open>` or a popover is promoted OUT of the document into
 *   the browser's top layer, above every `z-index`, with no `position: fixed` and no inset
 *   anywhere in its CSS. AC 10's shape cannot see it, and UX-DR38's "exactly one level deep"
 *   is a claim about what the user sees, not about what this file can parse.
 *   `::backdrop` is the tell a reviewer should look for.
 *
 *   `/*` INSIDE A STRING. `stripComments` runs before `blankStrings`, so `content: "/*"` opens
 *   a comment that swallows source until the next `* /`. The reverse order would break on
 *   quotes inside comments, which this file's own prose is full of; neither order is safe, and
 *   this one fails on the rarer input.
 *
 *   THE TSX HALF READS SOURCE, NOT SEMANTICS. The presentation-only guard strips comments and
 *   keys on spellings; a hook reached through a namespace (`React.useState`) or a value
 *   smuggled through a re-export would need a real module graph.
 *
 * **Review owns all of those halves**, the same split tests/token-usage.test.ts declares for
 * its contrast and numeric-pairing guards.
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

// Quoted string CONTENTS are blanked before block parsing: a brace inside a string —
// `content: "}"` is legal CSS — would otherwise desynchronise the innermost-brace matcher and
// silently mis-parse every block after it. No guard here inspects string contents, so
// blanking loses nothing.
//
// `(?:\\.|[^"\\\n])*`, not `[^"\n]*`: an ESCAPED QUOTE is legal CSS too, and `content: "\""`
// ends the naive match at the escaped quote — leaving the real closing quote to open a second
// "string" and desynchronising everything after it. That is the identical failure the
// `content: '}'` decoy was added to prove fixed, one round earlier, in the same function.
const blankStrings = (css: string) =>
  css.replace(/"(?:\\.|[^"\\\n])*"/g, '""').replace(/'(?:\\.|[^'\\\n])*'/g, "''")

/**
 * Split a value on TOP-LEVEL whitespace only. `inset: auto var(--x, 8px) auto auto` is four
 * components, not five: a naive `.split(/\s+/)` breaks inside the `var()` and every side after
 * it shifts by one, which silently mis-reads which edges a shorthand anchors.
 */
const topLevelParts = (value: string, separator = /\s/): string[] => {
  const parts: string[] = []
  let depth = 0
  let current = ''
  for (const char of value) {
    if (char === '(') depth++
    else if (char === ')') depth--
    if (depth === 0 && separator.test(char)) {
      if (current) parts.push(current)
      current = ''
    } else {
      current += char
    }
  }
  if (current) parts.push(current)
  return parts
}

const blocksIn = (file: string, css: string): Block[] =>
  [...blankStrings(stripComments(css)).matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => ({
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

// The LAST matching declaration, because that is the one the cascade uses within a block:
// `position: static; position: fixed` IS fixed, and a first-match reader would let exactly
// that spelling walk past the overlay guard and the Q2 height pin.
const valueOf = (block: Block, property: string): string | undefined =>
  declarationsIn(block.body)
    .filter(([p]) => p === property)
    .at(-1)?.[1]

/**
 * A magnitude of 100 or more — the shared prefix of both span families below. The
 * `(?<![\d.])` boundary is what stops `0.100%` reading as `100%` and `1100px`-style
 * neighbours bleeding in; its sibling in `documented()` got the same treatment a round
 * earlier, and this one was the member that repair stopped one short of.
 */
const FULL_MAGNITUDE = String.raw`(?<![\d.])(?:100|1\d{2}|[2-9]\d{2}|\d{4,})(?:\.\d+)?`

/**
 * A viewport-relative length that actually SPANS its axis. The unit family is an optional
 * dynamic / small / large prefix, `v`, then one of the six axes — but the magnitude matters
 * as much as the unit: a fixed drawer at `width: 40vw` is a drawer, not a second full-window
 * layer, and flagging it is the false positive a later story has to fight. `100vw`, `100dvh`
 * and `120svh` match; `40vw` and `99vh` do not. (The percentage half has always had this
 * floor; the unit half did not, which is exactly the asymmetry review found.)
 */
const VIEWPORT_UNIT_SPAN = new RegExp(`${FULL_MAGNITUDE}(?:[dsl]?v(?:w|h|i|b|min|max))\\b`, 'i')

/**
 * A percentage of 100 or more. On a `position: fixed` box — and on `html`, whose containing
 * block is the viewport — a percentage IS a viewport size wearing a different unit, and a
 * guard that reads only the `v*` family would wave `width: 100%; height: 100%` straight
 * through. `100%`, `150%` and `100.5%` match; `50%`, `99%` and `0.100%` do not.
 */
const FULL_PERCENT = new RegExp(`${FULL_MAGNITUDE}%`)

/** A value that spans the viewport on a box whose containing block is the viewport. */
const VIEWPORT_SPAN = new RegExp(`${VIEWPORT_UNIT_SPAN.source}|${FULL_PERCENT.source}`, 'i')

/**
 * The vertical size properties, caps included. The competing-height guard wants `max-height:
 * 100vh` on `body` too: a cap pinned to the viewport is still a second height mechanism the
 * shell has to fight. (There is no horizontal twin — nothing here asks whether the document
 * root is too WIDE; `SPANS_HORIZONTAL` below is the overlay guard's, and is a different
 * question with a different answer about `max-*`.)
 */
const VERTICAL_SIZE = /^(?:min-|max-)?(?:height|block-size)$/

/**
 * The size properties that make a box SPAN an axis — deliberately excluding `max-*`, which is
 * a CAP rather than a size. `max-width: 100%` on a content-sized fixed toast says "never wider
 * than the window", not "as wide as the window", and reading it as a span flags the toast as a
 * full-window overlay. `min-*` stays: `min-width: 100vw` really does span.
 */
const SPANS_HORIZONTAL = /^(?:min-)?(?:width|inline-size)$/
const SPANS_VERTICAL = /^(?:min-)?(?:height|block-size)$/

/**
 * The shell's own root element, anywhere in a part — `div.app-shell` is still the shell
 * root. The `(?![\w-])` lookahead is what keeps `.app-shell-columns` (the one legitimate
 * scroller) from matching.
 */
const SHELL_ROOT = /\.app-shell(?![\w-])/
/** The shell's single scroll container — where a horizontal clip would bury AC 5's defect. */
const SHELL_SCROLLER = /\.app-shell-columns(?![\w-])/

const selectorParts = (selector: string) => selector.split(',').map((part) => part.trim())

const matchesAnyPart = (selector: string, pattern: RegExp) =>
  selectorParts(selector).some((part) => pattern.test(part))

/**
 * Whether a selector can match the DOCUMENT root — the thing the shell must not fight.
 *
 * Three spellings, and the third is why this is a function rather than one regex:
 *
 *   NAMED. `html`, `body`, `:root`, `#root`, at the start of a part, after a combinator, or
 *   inside a functional pseudo-class — `:is(html)` and `:where(html, body)` are the same
 *   family, not a way around it.
 *
 *   UNIVERSAL AS THE SUBJECT. `*` alone matches every element INCLUDING the roots. In
 *   DESCENDANT position it cannot: `.card-tile * { overflow: hidden }` never matches `html`,
 *   and flagging a card tile's inner clip as a clipped ROOT is a false positive c4-4 would
 *   have to fight. The subject/descendant distinction is the whole difference.
 *
 *   NEGATED. `:not(html)` does NOT name `html` — but it still matches `body`, so it is a
 *   root-matching part for the same reason `*` is. Blanking the negation and then asking
 *   whether anything SELECTIVE is left gets both halves right: `:not(html)` reduces to
 *   nothing and fires, `.card-tile :not(.x)` reduces to `.card-tile` and stays silent.
 */
const namesDocumentRoot = (selector: string): boolean =>
  selectorParts(selector).some((rawPart) => {
    const part = rawPart.replace(/:not\((?:[^()]|\([^()]*\))*\)/gi, '').trim()
    if (/(^|[\s>+~(,])(html|body|:root|#root)(?![\w-])/.test(part)) return true
    return part === '*' || part === ''
  })

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
/**
 * Every `minmax(…)` in a value, with its argument text, at ANY nesting depth.
 *
 * A brace-counting scanner rather than a regex, because regexes cannot count: the previous
 * `(?:[^()]|\([^()]*\))*` form crossed exactly ONE level of nested parens, so
 * `minmax(max(min(176px, 25%), 8rem), 1fr)` — two levels, and a plausible responsive
 * evolution of c4-4's grid — was left unstripped and its `1fr` false-fired. Counting depth
 * has no such ceiling.
 */
const minmaxCalls = (value: string): { args: string; start: number; end: number }[] => {
  const calls: { args: string; start: number; end: number }[] = []
  const opener = /minmax\(/gi
  let match: RegExpExecArray | null
  while ((match = opener.exec(value)) !== null) {
    const argsStart = match.index + match[0].length
    let depth = 1
    let i = argsStart
    for (; i < value.length && depth > 0; i++) {
      if (value[i] === '(') depth++
      else if (value[i] === ')') depth--
    }
    if (depth !== 0) break // unbalanced — treat the rest as opaque rather than guessing
    calls.push({ args: value.slice(argsStart, i - 1), start: match.index, end: i })
    opener.lastIndex = i
  }
  return calls
}

const findContentFlooredTrack = (blocks: Block[]): string[] => {
  const TRACK_PROPERTY = /^grid(?:-(?:template|auto))?(?:-(?:columns|rows))?$/
  // `max-content` is in the family too: it is a content-derived floor that overflows HARDER
  // than min-content, and it was the one member the first version of this list forgot.
  const CONTENT_MINIMUM = /^(auto|min-content|max-content)$/i
  const advice =
    'A flexible track floored at min-content grows past its share for one unbreakable child ' +
    '(a long card name, a wide table, a <pre>) and the grid overflows the window. Write ' +
    'minmax(0, 1fr) — or a real length minimum, as c4-4s card grid does with minmax(176px, 1fr).'

  const findings: string[] = []
  for (const block of blocks) {
    for (const [property, value] of declarationsIn(block.body)) {
      if (!TRACK_PROPERTY.test(property)) continue
      const where = `${block.file} — \`${block.selector}\` (${property})`
      const calls = minmaxCalls(value)

      // An explicit content minimum, said out loud. The minimum is the first TOP-LEVEL
      // argument — splitting on a bare comma would cut `minmax(clamp(1rem, 2vw, 3rem), 1fr)`
      // in the wrong place.
      for (const call of calls) {
        const min = (topLevelParts(call.args, /,/)[0] ?? '').trim()
        if (CONTENT_MINIMUM.test(min)) {
          findings.push(`${where}: \`minmax(${call.args})\` floors the track at ${min}. ${advice}`)
        }
      }

      // A bare `<n>fr` outside any minmax() is the same thing, spelled shorter. Cut the
      // minmax spans out right-to-left so earlier offsets stay valid.
      let outsideMinmax = value
      for (const call of [...calls].reverse()) {
        outsideMinmax = outsideMinmax.slice(0, call.start) + outsideMinmax.slice(call.end)
      }
      if (/\b\d*\.?\d+fr\b/i.test(outsideMinmax)) {
        findings.push(`${where}: \`${value}\` uses a bare fr track. ${advice}`)
      }
    }
  }
  return findings
}

/**
 * AC 6 — `overflow: hidden` / `clip` on a root element, or on the shell's one scroller.
 *
 * Keyed on the overflow property FAMILY and on the two clipping values, over the root
 * selectors AND `.app-shell-columns` (review round, 2026-07-28): the scroll container is
 * exactly where an `overflow-x: hidden` would bury AC 5's horizontal overflow, one element
 * below the roots' floor. Its own `overflow-y: auto` is untouched — the guard fires on the
 * two clipping VALUES, not on the property. Still deliberately NARROW below that: c4-5's
 * detail panel and c6-5's overlay clip on purpose, and a blanket ban would be a gate three
 * later stories have to fight, which is a worse outcome than the defect it would prevent.
 */
const findClippedRoot = (blocks: Block[]): string[] => {
  const OVERFLOW_PROPERTY = /^overflow(?:-(?:x|y|block|inline))?$/
  const CLIPS = /(^|\s)(hidden|clip)(\s|$)/i
  // `overflow` is not the only way to clip, and the other two are the family members the
  // first version stopped short of. `contain: paint|strict|content` clips descendants to the
  // padding box — and, on the shell root, additionally makes the element a containing block
  // for `position: fixed`, which would capture the overlay this file spends AC 10 protecting.
  // `clip-path` clips the painted result outright. Both bury AC 5's overflow exactly as
  // `overflow-x: hidden` does, and neither is an `overflow` declaration.
  const CONTAIN_CLIPS = /(^|\s)(paint|strict|content)(\s|$)/i

  const clippingDeclaration = ([property, value]: [string, string]): boolean => {
    if (OVERFLOW_PROPERTY.test(property)) return CLIPS.test(value)
    if (property === 'contain') return CONTAIN_CLIPS.test(value)
    if (property === 'clip-path') return !/^none$/i.test(value)
    return false
  }

  return blocks
    .filter(
      (b) =>
        namesDocumentRoot(b.selector) ||
        matchesAnyPart(b.selector, SHELL_ROOT) ||
        matchesAnyPart(b.selector, SHELL_SCROLLER),
    )
    .flatMap((block) => {
      // Name the element the guard ACTUALLY fired on. The scroller is one level below the
      // roots — the guard's own comment says so — and a message that calls it "a root
      // element" sends the reader to the wrong file.
      const where = namesDocumentRoot(block.selector)
        ? 'a root element'
        : matchesAnyPart(block.selector, SHELL_SCROLLER)
          ? "the shell's single scroll container"
          : "the shell's root element"
      return declarationsIn(block.body)
        .filter(clippingDeclaration)
        .map(
          ([property, value]) =>
            `${block.file} — \`${block.selector}\` sets \`${property}: ${value}\` on ${where}. ` +
            `That makes "the body never scrolls horizontally" true by CLIPPING the ` +
            `overflowing content instead of fitting it: the defect survives, invisible, and the ` +
            `acceptance criterion reports success. Fix the track that overflows — usually a ` +
            `bare 1fr or a missing min-width: 0 — rather than hiding it.`,
        )
    })
}

/**
 * AC 10 / UX-DR38 — a full-window FIXED layer, in every shape that covers the window.
 *
 * "Full-window" means covered on BOTH axes, where an axis is covered by being ANCHORED at
 * both ends (by `inset`, by the logical pairs, by the physical longhands, or by any mix) OR
 * by being SIZED to the viewport (a viewport unit, or a percentage — on a fixed box a
 * percentage resolves against the viewport, so `width: 100%; height: 100%` is the same layer
 * in a different unit). The two mechanisms mix per axis: `inset-block: 0; width: 100vw` is
 * anchored vertically, sized horizontally, and covers the window.
 *
 * ANCHORING IS VALUE-AWARE: `top: 0; bottom: 0` anchors, `inset: auto auto 16px 16px` — a
 * corner pill written in shorthand — does NOT, because `auto` releases the side it names. A
 * presence-only check would flag that pill, and a false positive c5-7 has to fight is the
 * worse outcome. Physical/logical mapping assumes horizontal-tb writing mode, which stylelint
 * already guarantees for shipped stylesheets.
 *
 * A pill pinned to one corner and a bar docked to one edge stay silent — c5-7 and a future
 * docked bar are not this rule's business.
 *
 * `position: absolute` is deliberately NOT this shape. An absolute cover inside a positioned
 * parent is a panel's own veil, not a level of the overlay stack.
 */
const INSET_SIDES = ['top', 'right', 'bottom', 'left'] as const
type Side = (typeof INSET_SIDES)[number]

/**
 * The four physical sides implied by an `inset` shorthand value, in top/right/bottom/left
 * order. Split on TOP-LEVEL whitespace: `inset: auto var(--x, 8px) auto auto` is four
 * components, and a naive split breaks inside the `var()` so every side after it shifts.
 */
const insetShorthandSides = (value: string): string[] => {
  const [t, r = t, b = t, l = r] = topLevelParts(value)
  return [t, r, b, l]
}

/** Whether one physical side ends up anchored (declared, and not `auto`), last declaration wins. */
const sideAnchored = (block: Block, side: Side): boolean => {
  const LOGICAL: Record<Side, string> = {
    top: 'inset-block-start',
    bottom: 'inset-block-end',
    left: 'inset-inline-start',
    right: 'inset-inline-end',
  }
  let value: string | undefined
  for (const [p, v] of declarationsIn(block.body)) {
    if (p === side || p === LOGICAL[side]) value = v
    else if (p === 'inset') value = insetShorthandSides(v)[INSET_SIDES.indexOf(side)]
    else if (p === 'inset-block' && (side === 'top' || side === 'bottom')) {
      const [start, end = start] = topLevelParts(v)
      value = side === 'top' ? start : end
    } else if (p === 'inset-inline' && (side === 'left' || side === 'right')) {
      const [start, end = start] = topLevelParts(v)
      value = side === 'left' ? start : end
    }
  }
  return value !== undefined && !/^auto$/i.test(value)
}

const findFullWindowFixedLayers = (blocks: Block[]): Block[] =>
  blocks.filter((block) => {
    if (!/(^|\s)fixed(\s|$)/i.test(valueOf(block, 'position') ?? '')) return false

    // `SPANS_*`, not `*_SIZE`: `max-*` is a CAP, not a size. `max-width: 100%` on a
    // content-sized fixed toast says "never wider than the window" — reading that as "as wide
    // as the window" flags the toast as a second full-window overlay, which is the false
    // positive a later story fights.
    const sizedAlong = (axis: RegExp) =>
      declarationsIn(block.body).some(([p, v]) => axis.test(p) && VIEWPORT_SPAN.test(v))

    const verticalCovered =
      (sideAnchored(block, 'top') && sideAnchored(block, 'bottom')) || sizedAlong(SPANS_VERTICAL)
    const horizontalCovered =
      (sideAnchored(block, 'left') && sideAnchored(block, 'right')) || sizedAlong(SPANS_HORIZONTAL)

    return verticalCovered && horizontalCovered
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

/**
 * The shell owns the window height; the document root must not declare a second one. `%`
 * counts too: `html`'s containing block is the viewport, so `html { height: 100% }` is the
 * same competing mechanism in a different unit.
 */
const findViewportHeightOnDocumentRoot = (blocks: Block[]): string[] =>
  blocks
    .filter((b) => namesDocumentRoot(b.selector))
    .flatMap((block) =>
      declarationsIn(block.body)
        .filter(([property, value]) => VERTICAL_SIZE.test(property) && VIEWPORT_SPAN.test(value))
        .map(
          ([property, value]) =>
            `${block.file} — \`${block.selector}\` sets \`${property}: ${value}\`. The shell ` +
            `owns the window height at 100dvh (Q2); a viewport height on the document root is ` +
            `a second, disagreeing mechanism — and \`vh\` is the LARGE viewport height, so on a ` +
            `browser with retracting chrome the page grows taller than the window and the ` +
            `pinned footer scrolls out of it.`,
        ),
    )

/**
 * AC 18's two halves — module-scoped so the firing proofs at the foot of this file can reach
 * them. A fractional literal exists nowhere in the tree yet, and "prove the family with a
 * member nobody wrote" is exactly what these repairs need.
 *
 * FRACTIONAL LENGTHS ARE ONE TOKEN. `\b\d+px\b` tokenises `17.5px` as `5px` — `\b` sits
 * happily between the `.` and the `5` — and `documented()`'s own `(?<![\d.])` boundary then
 * makes a perfectly truthful "17.5px — DESIGN.md" citation unsatisfiable for the `5px` it went
 * looking for. The first story to ship a fractional geometry literal would inherit a gate it
 * could not pass by writing the right thing.
 */
const pxLiteralsIn = (css: string) => [
  ...new Set(stripComments(css).match(/(?<![\d.])\d+(?:\.\d+)?px\b/g) ?? []),
]

/**
 * PROXIMITY, not co-occurrence. The first version of this asked only whether SOME comment
 * mentioned the literal and SOME part of it said "DESIGN.md" — and the probe that deleted the
 * real citation still passed, because the file-header comment happens to contain both the
 * phrase "the 452px track" and a reference to DESIGN.md's frontmatter four hundred characters
 * away. A guard satisfied by something other than the thing it is checking is exactly the
 * defect this epic's reviews have found in every round; requiring the citation to sit within
 * one sentence of the value is what makes it check the citation.
 *
 * BOUNDED, not a substring. `new RegExp('52px')` would be satisfied by the `52px` INSIDE
 * "452px — DESIGN.md", so a later literal could ride an earlier one's citation. The lookbehind
 * forbids a digit or dot before the match; nothing need follow `px`.
 */
const documented = (comments: string[], literal: string) =>
  comments.some((comment) =>
    // The literal is regex-ESCAPED before it becomes a pattern: `17.5px` carries a `.`, which
    // as a metacharacter would match `17X5px` and quietly widen the check.
    [...comment.matchAll(new RegExp(`(?<![\\d.])${literal.replace(/\./g, '\\.')}`, 'g'))].some(
      (match) => {
        const near = comment.slice(Math.max(0, match.index - 60), match.index + 60)
        return near.includes('DESIGN.md')
      },
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
    //
    // SCOPED TO THE MEDIA BLOCK'S OWN SOURCE, not `collapsed[1]`. Nothing tied index 1 to
    // "inside the media query": reorder the stylesheet, or add a third `.app-shell-columns`
    // rule anywhere, and the assertion silently starts checking a different rule while
    // staying green. Extracting the block by balanced braces makes the target explicit.
    const mediaBody = (() => {
      const opener = /@media\s*\(\s*width\s*<\s*1100px\s*\)\s*\{/.exec(shellCode)
      if (!opener) return null
      const start = opener.index + opener[0].length
      let depth = 1
      for (let i = start; i < shellCode.length; i++) {
        if (shellCode[i] === '{') depth++
        else if (shellCode[i] === '}' && --depth === 0) return shellCode.slice(start, i)
      }
      return null
    })()
    expect(mediaBody, 'no balanced @media (width < 1100px) block').not.toBeNull()

    const inMedia = blocksIn(SHELL_CSS, mediaBody!).filter(
      (b) => b.selector === '.app-shell-columns',
    )
    expect(inMedia).toHaveLength(1)
    expect(valueOf(inMedia[0], 'grid-template-columns')).toBe('minmax(0, 1fr)')
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
    // `--space-gutter`, not `--space-6` (review round, 2026-07-28 — a deliberate deviation
    // from AC 7's literal spelling, recorded in the story). The two are both 32px TODAY, but
    // they are different tokens: the overlay's whole contract is that its inset coincides
    // with the shell's own frame (Q2 said so in as many words), and if the gutter is ever
    // retuned, an overlay pinned to `--space-6` would silently stop aligning with the frame
    // it is documented to align with — while this assertion kept passing.
    expect(valueOf(blockFor('.app-shell-overlay')!, 'inset')).toBe('var(--space-gutter)')
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
  // c4-4 (176px grid minimum) inherit a stated rule rather than a habit — and since the
  // review round of 2026-07-28 they inherit it as a GATE, not prose: the citation check runs
  // over EVERY component stylesheet, so the rule ~35 stories inherit is enforced the moment
  // each of them stages its CSS, not re-implemented per story.
  //
  // Scope stated plainly: px lengths only. `z-index: 20` is also a geometry literal and is
  // documented in prose beside its rule, but a bare unitless number cannot be told apart
  // from the ones in `minmax(0, 1fr)`, `flex: 1` and `min-width: 0`, so it is review's
  // rather than this guard's.
  const componentStylesheets = shippedStylesheets.filter((f) => f.startsWith('src/components/'))

  it('is reading the component stylesheets at all (non-vacuity), and the shell pins its two', () => {
    // The anchor: the shell is a component stylesheet, and its literals are exactly the two
    // the composition is made of. A NEW shell literal fails here first — deliberately: it is
    // a change to the pinned composition, and updating this list is the open way to make it.
    expect(componentStylesheets).toContain(SHELL_CSS)
    expect(pxLiteralsIn(shellSource).sort()).toEqual(['1100px', '452px'])
  })

  it('sources every px literal in every component stylesheet to DESIGN.md, beside the value', () => {
    for (const file of componentStylesheets) {
      const css = sourceOf(file)
      const comments = commentsIn(css)
      for (const literal of pxLiteralsIn(css)) {
        expect(
          documented(comments, literal),
          `${literal} appears in ${file} with no DESIGN.md citation within a sentence of it`,
        ).toBe(true)
      }
    }
  })

  it('says, in the file, why these are not tokens', () => {
    expect(shellSource).toContain('AC 18')
    expect(shellSource).toMatch(/not a token|NON-BAN/i)
  })
})

describe('the shell is presentation-only, and that is asserted (AC 16)', () => {
  const shellSourceText = sourceOf(SHELL_TSX)

  /**
   * COMMENTS STRIPPED, for the same reason the media-query assertion strips them ten lines
   * above: this file's own prose says the shell "fetches nothing" and names the hooks it does
   * not call, and a guard that reads documentation as code turns red the moment someone
   * documents the rule properly. Block comments first, then line comments — the `[^:]` guard
   * keeps a `https://` inside a string from reading as a comment (there are none today; it is
   * the cheap version of a real tokeniser, and the file header says so).
   */
  const shellComponent = shellSourceText
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')

  /**
   * Every module this file pulls in, INCLUDING bare side-effect imports. `from '…'` alone
   * misses `import './subscribe'` — no `from` clause, no call parens — which is precisely how
   * a module that subscribes on load would walk past an "imports nothing but React" check.
   */
  const importedModules = [
    ...shellComponent.matchAll(/import\s+(?:[^'"]*?\bfrom\s+)?['"]([^'"]+)['"]/g),
  ].map((m) => m[1])

  it('imports nothing but React types and its own stylesheet', () => {
    // A store import, a fetch helper or a hooks module would each pre-empt a design c3-1 and
    // c4-1 own. Asserted as an EXHAUSTIVE list rather than a blocklist: a module nobody
    // thought to ban is exactly the one that would get through — and the stylesheet is in the
    // list rather than checked separately, so a second bare import cannot hide beside it.
    expect(importedModules.sort()).toEqual(['./AppShell.css', 'react'])
    // The react import must be TYPE-ONLY. Hooks are VALUE imports, so this one line closes
    // the aliasing evasion (`import { useState as s }` never matches a name-keyed regex) at
    // the door instead of chasing spellings at the call site.
    expect(shellComponent).not.toMatch(/import\s+(?!type\b)[^;\n]*?from\s+['"]react['"]/)
    // And the two runtime routes around static imports are closed by name.
    expect(shellComponent).not.toMatch(/\b(?:require|import)\s*\(/)
  })

  it('holds no state and subscribes to nothing', () => {
    // Keyed on the React state/effect API family rather than on named hooks, so a hook this
    // list never heard of is still caught — including React 19's `use()`, the one LOWERCASE
    // hook, which a `use[A-Z]` prefix check alone would wave through.
    expect(shellComponent).not.toMatch(/\buse[A-Z]\w*\s*\(/)
    expect(shellComponent).not.toMatch(/(?<![\w.$])use\s*\(/)
    expect(shellComponent).not.toMatch(/\b(fetch|XMLHttpRequest|EventSource|WebSocket)\s*\(/)
  })

  it('reads code, not the documentation about the code', () => {
    // The non-vacuity half of the comment stripping: the real file DOES discuss these APIs in
    // its prose, so if stripping ever regressed the two assertions above would fail on the
    // documentation. Proving the raw source contains what the stripped source does not is
    // what keeps that from being re-introduced silently.
    expect(shellSourceText).toMatch(/fetches nothing/)
    expect(shellComponent).not.toMatch(/fetches nothing/)
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
    expect(joined).toContain('.max-content-minimum') // the member the first list forgot
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
    // The silent half, on blocks that genuinely use `fr`. A guard proven only on blocks
    // with no grid template at all would be silent for the wrong reason. The nested-minmax
    // block is the false-positive probe: a matcher that cannot cross `min()`'s parens leaves
    // the minmax unstripped and flags its 1fr.
    const legal = violation.filter((b) =>
      ['.legal-card-grid', '.legal-nested-minmax', '.legal-doubly-nested-minmax'].includes(
        b.selector,
      ),
    )
    expect(legal).toHaveLength(3)
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
    // UNENUMERATED SELECTORS (review round, 2026-07-28) — the universal selector, the root
    // wrapped in a functional pseudo-class, and the compound `div.app-shell`; plus the
    // scroller, the one element below the roots where a horizontal clip buries AC 5.
    expect(joined).toContain('`*`')
    expect(joined).toContain(':where(html)')
    expect(joined).toContain('div.app-shell')
    expect(joined).toContain('.app-shell-columns')
    // UNENUMERATED PROPERTIES (review round 2) — two ways to clip that never write the word
    // `overflow`, so a guard keyed on that one property family cannot see either.
    expect(joined).toContain('contain: paint')
    expect(joined).toContain('clip-path: inset(0)')
    // NEGATION IS NOT EXEMPTION: `:not(html)` still matches `body`.
    expect(joined).toContain(':not(html)')
    expect(findings.length).toBe(12)

    for (const finding of findings) {
      expect(finding).toContain('CLIPPING')
    }

    // The message names the element it ACTUALLY fired on — the scroller is one level below
    // the roots, and calling it "a root element" sends the reader to the wrong file.
    const scroller = findings.find((f) => f.includes('.app-shell-columns'))
    expect(scroller).toContain("the shell's single scroll container")
    expect(findings.find((f) => f.includes('`body`'))).toContain('a root element')
  })

  it('leaves the legitimate scroll and the legitimate clip alone (AC 6, narrow by design)', () => {
    // Two different reasons to stay silent, and BOTH have to hold: `.legal-scroller` is not a
    // root selector and its value is `auto`; `.legal-clipping-panel` clips, but is not a root.
    // c4-5's detail panel and c6-5's overlay are the real components behind that second one.
    const legal = violation.filter((b) =>
      [
        '.legal-scroller',
        '.legal-clipping-panel',
        // The universal selector in DESCENDANT position, and a negation that still leaves
        // something selective behind. Neither can match `html` or `body` under any document,
        // and c4-4's card tile is the real component behind both (review round 2).
        '.card-tile *',
        '.card-tile :not(.is-live)',
      ].includes(b.selector),
    )
    expect(legal).toHaveLength(4)
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
    // THE UNENUMERATED SPELLINGS (review round, 2026-07-28): `%` on a fixed box resolves
    // against the viewport; the two mechanisms can mix one-per-axis; the LAST `position`
    // declaration is the one the cascade uses; and a `}` inside a string must not blind the
    // parser to everything after it.
    expect(joined).toContain('.second-overlay-by-percentages')
    expect(joined).toContain('.second-overlay-mixed-axes')
    expect(joined).toContain('.second-overlay-cascade')
    expect(joined).toContain('.second-overlay-after-string-brace')
    // An ESCAPED quote is the same desynchronisation the `}` decoy proved fixed, one repair
    // short: a `"[^"]*"` blanker stops at the escaped quote (review round 2).
    expect(joined).toContain('.second-overlay-after-escaped-quote')
    expect(findings).toHaveLength(9)

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
      [
        '.legal-corner-pill',
        '.legal-corner-pill-shorthand',
        '.legal-docked-bar',
        '.legal-absolute-cover',
        // Review round 2 — three more shapes a later story would otherwise have to fight:
        // a shorthand carrying a function (whitespace-splitting shifts every side after it),
        // a fixed drawer sized to PART of the viewport, and a content-sized toast whose
        // percentages are CAPS rather than sizes.
        '.legal-corner-pill-with-function',
        '.legal-fixed-drawer',
        '.legal-fixed-toast',
      ].includes(b.selector),
    )
    expect(legal).toHaveLength(7)
    expect(findFullWindowFixedLayers(legal)).toEqual([])
  })

  it('catches a viewport height on the document root', () => {
    // The exact line this story removed from src/index.css, plus the dynamic-unit spelling of
    // it, so the guard is not anchored on `vh` alone.
    const planted = blocksIn(
      'inline',
      `body { min-height: 100vh; }
       html { height: 100lvh; }
       #root { height: 100%; }
       .app-shell { height: 100dvh; }`,
    )
    const findings = findViewportHeightOnDocumentRoot(planted)
    expect(findings).toHaveLength(3)
    expect(findings.join('\n')).toContain('100vh')
    expect(findings.join('\n')).toContain('100lvh')
    // `%` on the document root resolves against the viewport — the same competing height
    // in a unit the viewport family never matched (review round, 2026-07-28).
    expect(findings.join('\n')).toContain('100%')
    // The shell's own 100dvh is the mechanism, not the defect — it must stay silent.
    expect(findings.join('\n')).not.toContain('.app-shell')
  })

  it('reads a fractional px literal as ONE token, and lets a truthful citation satisfy it', () => {
    // No fractional geometry literal exists yet, so this is the invented member: `\b\d+px\b`
    // tokenises `17.5px` as `5px`, and `documented()`'s own `(?<![\d.])` boundary then makes
    // the truthful "17.5px — DESIGN.md" citation unsatisfiable for the `5px` it went looking
    // for. The first story to ship one (c2-7's StatChip is a candidate) would inherit a gate
    // it could not pass by writing the right thing — the worst kind, because the fix looks
    // like removing the documentation.
    const css = `/* 17.5px — DESIGN.md says the chip is 17.5px tall. */\n.chip { height: 17.5px; }`
    expect(pxLiteralsIn(css)).toEqual(['17.5px'])
    expect(documented(commentsIn(css), '17.5px')).toBe(true)

    // And the boundary still does its round-1 job: a later `52px` must NOT ride the `52px`
    // inside an existing "452px — DESIGN.md" citation.
    const shared = `/* 452px — DESIGN.md, the right column. */`
    expect(documented(commentsIn(shared), '452px')).toBe(true)
    expect(documented(commentsIn(shared), '52px')).toBe(false)
  })

  it('applies the >= 100 span floor to viewport UNITS, not just percentages', () => {
    // The asymmetry review found: `FULL_PERCENT` has always had the floor, `VIEWPORT_UNIT`
    // never did. Asserted on the regexes directly because a magnitude is exactly the kind of
    // thing a fixture cannot enumerate.
    expect(VIEWPORT_SPAN.test('100vw')).toBe(true)
    expect(VIEWPORT_SPAN.test('100dvh')).toBe(true)
    expect(VIEWPORT_SPAN.test('120svh')).toBe(true)
    expect(VIEWPORT_SPAN.test('40vw')).toBe(false)
    expect(VIEWPORT_SPAN.test('99vh')).toBe(false)

    // And the percentage boundary its sibling got in round 1: `0.100%` is a tenth of a
    // percent, not one hundred percent.
    expect(VIEWPORT_SPAN.test('100%')).toBe(true)
    expect(VIEWPORT_SPAN.test('0.100%')).toBe(false)
    expect(VIEWPORT_SPAN.test('50%')).toBe(false)
  })

  it('blanks a string containing an ESCAPED quote, braces and all', () => {
    // PROBED DIRECTLY, not through a fixture block — and that is the finding, not a shortcut.
    // Two fixture-shaped probes were written for this repair and BOTH passed against the
    // naive `"[^"\n]*"` blanker, i.e. proved nothing:
    //
    //   * a decoy whose string held an escaped quote but no brace — nothing to desynchronise;
    //   * a decoy whose string held a brace as well — the stray brace merely truncates the
    //     DECOY's own block, and `([^{}]+)\{([^{}]*)\}` resynchronises on the very next
    //     balanced pair, so the block below it parses correctly either way. (The character
    //     class excludes newlines, so the damage cannot even cross a line.)
    //
    // The repair is still right — a truncated block body is a declaration no guard can see —
    // but the honest proof is of the function, not of a verdict downstream of it. The fixture
    // keeps its decoy as documentation; this is the assertion that fails if the repair is
    // reverted.
    expect(blankStrings(`content: 'a\\'b }';`)).not.toContain('}')
    expect(blankStrings(`content: "a\\"b }";`)).not.toContain('}')
    // And the plain forms still blank, or the repair would have broken the round-1 case.
    expect(blankStrings(`content: '}';`)).not.toContain('}')
    expect(blankStrings(`content: "}";`)).not.toContain('}')
    // A real brace OUTSIDE a string must survive — blanking is not deleting.
    expect(blankStrings(`.a { color: red; }`)).toContain('}')
  })

  it('splits an inset shorthand on TOP-LEVEL whitespace only', () => {
    // `var(--pill-gap, 8px)` is ONE component. Splitting inside it shifts every side after it
    // by one, so the guard reads anchors that were never declared — and the shape it
    // mis-reads is a corner pill, i.e. it invents a full-window layer out of c5-7's pill.
    expect(insetShorthandSides('auto var(--pill-gap, 8px) auto auto')).toEqual([
      'auto',
      'var(--pill-gap, 8px)',
      'auto',
      'auto',
    ])
    // The plain forms still expand the way the shorthand says.
    expect(insetShorthandSides('0')).toEqual(['0', '0', '0', '0'])
    expect(insetShorthandSides('0 auto')).toEqual(['0', 'auto', '0', 'auto'])
  })
})
