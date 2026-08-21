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
 *   (RESOLVED, and left here as the record.) `/*` inside a string used to open a comment that
 *   swallowed source to the next real close, and the reverse pass order broke on quotes inside
 *   comments instead. Neither ordering was safe. `scan()` below now walks the source once,
 *   tracking which construct it is inside, so the class is gone rather than traded.
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
import { join, posix } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

/** The one stylesheet allowed to declare the full-window overlay layer (AC 10). */
const SHELL_CSS = 'src/components/AppShell/AppShell.css'
const SHELL_TSX = 'src/components/AppShell/AppShell.tsx'

/**
 * The shared emptiness helper, pinned by PATH because the presentation-only guard below has
 * to hold it to the same posture as the component that imports it — an exempted module is
 * where the next evasion lives, and this one is exempted from the type-only react rule by
 * construction. It moved out of `AppShell/` in story c2-7 (Q3), where Panel became its second
 * consumer; the exhaustive import list above is the other half of that move.
 */
const FILLED_TS = 'src/components/filled.ts'

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

/**
 * ONE PASS THAT KNOWS ABOUT BOTH COMMENTS AND STRINGS, because two passes cannot.
 *
 * Comments and strings can each contain the other's opener, so whichever runs first is wrong
 * about the input the second one sees. Both orders were MEASURED (Greptile, PR #23), and both
 * lose:
 *
 *   STRIP-THEN-BLANK loses a whole rule. A comment OPENER inside a string starts a comment
 *   that runs to the next real comment CLOSE anywhere in the file, swallowing every
 *   declaration in between — and since `blocksIn` reads the same stripped source, those rules
 *   vanish from EVERY guard here, not just from the literal scan. Silent, and in the
 *   safe-looking direction.
 *
 *   BLANK-THEN-STRIP loses a comment. A one-line comment ending in an apostrophe — `it's` —
 *   followed by a declaration carrying a quoted value pairs those two quotes, blanks the
 *   comment's CLOSE between them, and the comment is then never stripped at all: its prose
 *   leaks into what the guards read as code. This file's own prose is full of apostrophes.
 *
 *   (Neither hazard can be written literally in this comment, which is itself the point.)
 *
 * So neither ordering is a fix, and the earlier version of this header was right to say so.
 * A scanner that tracks which construct it is inside removes the CLASS instead of trading one
 * rare failure for another — the same move the nesting ban made in tests/token-usage.test.ts,
 * and the reason that ban exists rather than a cleverer regex.
 *
 * String CONTENTS are blanked rather than removed, and the quotes are kept, so
 * `content: "}"` stays a well-formed declaration that `declarationsIn` can still read.
 */
const scan = (css: string): { code: string; comments: string[] } => {
  let code = ''
  const comments: string[] = []
  let i = 0

  while (i < css.length) {
    if (css.startsWith('/*', i)) {
      const end = css.indexOf('*/', i + 2)
      const stop = end === -1 ? css.length : end + 2
      comments.push(css.slice(i, stop))
      i = stop
      continue
    }

    const char = css[i]
    if (char === '"' || char === "'") {
      code += char
      i++
      // CSS strings do not span an unescaped newline; stopping there keeps an unterminated
      // quote from eating the rest of the file, which is the failure mode being removed.
      while (i < css.length && css[i] !== char && css[i] !== '\n') {
        i += css[i] === '\\' ? 2 : 1
      }
      if (css[i] === char) {
        code += char
        i++
      }
      continue
    }

    code += char
    i++
  }

  return { code, comments }
}

const stripComments = (css: string) => scan(css).code

const commentsIn = (css: string): string[] => scan(css).comments

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
 * docked bar are not this rule's business. **c5-7 shipped exactly that shape** (2026-08-08):
 * `.connection-pill` is `position: fixed` with `bottom` and `left` alone, so both axes stay
 * released at their far ends and this guard never looks at it. The anticipation was correct and
 * the tolerance is now load-bearing rather than hypothetical.
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
 *
 * STRINGS ARE BLANKED, NOT JUST COMMENTS (Greptile, PR #23). A px length inside a CSS STRING
 * is text, not geometry: `content: "16px"` in a tooltip or a c4-8 axis label is a value
 * the user READS, and there is nothing in DESIGN.md to cite for it. Scanning it as a literal
 * would fail the gate on a stylesheet that is entirely correct — the false positive a later
 * story fights, which this file's own doctrine calls the worse outcome. `blankStrings` already
 * exists three helpers up for the parser; the scanner simply was not using it.
 */
const pxLiteralsIn = (css: string) => [
  ...new Set(stripComments(css).match(/(?<![\d.])\d+(?:\.\d+)?px\b/g) ?? []),
]

/**
 * WHAT THIS IS, STATED AT ITS REAL STRENGTH (C5 R6 demotion, executed at C6 R10, 2026-08-17).
 *
 * This is a STRING-PROXIMITY CHECK. It asks whether the eight characters `DESIGN.md` appear
 * within 60 characters of the literal, in a comment. That is all it asks. It does NOT:
 *
 *   - open DESIGN.md, or check that the file exists;
 *   - resolve a `DESIGN.md:NNN` anchor to a line, or check that the line says anything about
 *     this value — the ~60 line anchors across this suite are UNVERIFIED BY ANYTHING and go
 *     stale silently every time DESIGN.md gains a paragraph (C5 R6 weighed a resolving guard
 *     and DECLINED it; the anchors stay as-is by that decline, and this paragraph is the
 *     honest label that came with it);
 *   - check that the citation is TRUE. A comment reading "452px — DESIGN.md" beside
 *     `width: 999px` fails, because the digits do not match; a comment reading
 *     "999px — DESIGN.md" beside `width: 999px` PASSES, whether or not DESIGN.md has ever
 *     mentioned 999px. The value has to agree with itself, not with the artefact.
 *
 * So what it buys is narrow and worth being clear about: a px literal cannot be added to a
 * component stylesheet with NO stated source beside it. It catches the unsourced value, which
 * is the common failure. It cannot catch a wrong or rotted source — that is review's, and
 * saying so here is what stops the next author reading a green run as more than it is.
 *
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

/**
 * The footer attribution's CSS SOURCE (story c2-10, AC 5, AC 6, AC 7, AC 10, AC 11, AC 12).
 *
 * WHY HERE AND NOT IN `Footer.test.tsx`. jsdom applies no stylesheet and has no layout engine,
 * so a `getComputedStyle` assertion over there reports the defaults and passes over a stylesheet
 * that was never linked — which is c2-7's StatChip defect exactly (a padding the comment claimed
 * and the file never shipped, invisible to every gate). This file already reads component
 * stylesheets as text, which is where those claims are actually decidable. What remains
 * undecidable in EITHER place — whether 10px all-caps legal text is readable, whether the 24px
 * box lays out as 24px, what the ring looks like — is on the epic manual-testing checklist and
 * is claimed nowhere.
 */
describe('the footer attribution stylesheet (story c2-10)', () => {
  const FOOTER_CSS = 'src/components/Footer/Footer.css'
  const footerBlocks = blocksIn(FOOTER_CSS, sourceOf(FOOTER_CSS))
  const footerBlock = (selector: string) => footerBlocks.find((b) => b.selector === selector)

  it('is reading the real stylesheet (non-vacuity)', () => {
    // Every assertion below indexes into this parse. A renamed file or a changed selector would
    // otherwise make each one pass by finding nothing — and git tracks the file, so an untracked
    // stylesheet cannot satisfy it either.
    expect(shippedStylesheets).toContain(FOOTER_CSS)
    expect(footerBlocks.length).toBeGreaterThan(3)
    expect(footerBlock('.footer-attribution')).toBeDefined()
    expect(footerBlock('.footer-attribution-link')).toBeDefined()
  })

  it('uses the passing text tier, not the muted one (AC 10, UX-DR32)', () => {
    // 9.3:1 on --surface-base, versus --text-tertiary's 5.9:1. Both pass WCAG AA; the choice is
    // the AC's own reasoning — this text is legally load-bearing and gets a passing tier rather
    // than a muted one. Asserted as an EXACT value so a later "tidy-up" to tertiary is red.
    expect(valueOf(footerBlock('.footer-attribution')!, 'color')).toBe('var(--text-secondary)')
  })

  it('resolves the colour rather than shadowing it (AC 10)', () => {
    // Q2's ruling, asserted so it cannot silently regress into the race it was ruled out of.
    // CONTAINMENT, not selector equality: an exact-string filter is proven only against the two
    // spellings it lists, and `.app-shell .app-shell-footer { color: ... }` would have re-run
    // the race unseen (review find, 2026-07-30). Any selector that so much as NAMES either
    // class is in scope; the link's own blocks are exempt because their rest colour is pinned
    // to `inherit` below — they take the tier, they do not decide it. DECLARED LIMIT: a
    // selector reaching the footer through an unrelated name (`footer p`) is review's to
    // catch, the way this suite's other structural guards declare theirs.
    const declaringColour = shippedBlocks.filter(
      (b) =>
        (b.selector.includes('app-shell-footer') || b.selector.includes('footer-attribution')) &&
        !b.selector.includes('footer-attribution-link') &&
        declarationsIn(b.body).some(([property]) => property === 'color'),
    )
    expect(declaringColour.map((b) => `${b.file} ${b.selector}`)).toEqual([
      `${FOOTER_CSS} .footer-attribution`,
    ])
    // The exemption's justification, asserted rather than assumed: the link inherits the tier.
    expect(valueOf(footerBlock('.footer-attribution-link')!, 'color')).toBe('inherit')
    // And the shell's rule keeps its LAYOUT job — the pinning mechanism is not what moved.
    expect(valueOf(blockFor('.app-shell-footer')!, 'flex-shrink')).toBe('0')
  })

  it('takes its surface and rule from the DESIGN.md frontmatter (AC 12)', () => {
    const block = footerBlock('.footer-attribution')!
    expect(valueOf(block, 'background')).toBe('var(--surface-base)')
    expect(valueOf(block, 'border-top')).toBe('1px solid var(--border-hairline)')
  })

  it('applies the micro role with BOTH companions in the same block (AC 11)', () => {
    // The block, not the file: `findRoleWithoutCompanions` in token-usage.test.ts reads blocks,
    // and splitting the companions across a base rule and a modifier fails there even though
    // the cascade would produce the right pixels. Asserted here too, because this is the story
    // that took Q1's ruling and the uppercase is the visible half of it.
    const block = footerBlock('.footer-attribution')!
    expect(valueOf(block, 'font')).toBe('var(--type-micro)')
    expect(valueOf(block, 'letter-spacing')).toBe('var(--tracking-micro)')
    expect(valueOf(block, 'text-transform')).toBe('uppercase')
  })

  it('underlines the links at REST, not on hover (AC 5, UX-DR47)', () => {
    // The hover-only affordance UX-DR47 forbids: an underline that appears on hover does not
    // exist for a keyboard or a touch user. So the rest rule must carry it...
    expect(valueOf(footerBlock('.footer-attribution-link')!, 'text-decoration')).toBe('underline')
    // ...and no hover rule may be the thing that introduces it. The FAMILY, not the shorthand:
    // `text-decoration-line: underline` on :hover is the same evasion spelled longhand, and a
    // guard that checks one exact property name is proven only against spellings it lists
    // (review find, 2026-07-30).
    for (const block of footerBlocks.filter((b) => b.selector.includes(':hover'))) {
      expect(
        declarationsIn(block.body)
          .map(([property]) => property)
          .filter((property) => property.startsWith('text-decoration')),
        `${block.selector} introduces a decoration on hover — AC 5 requires it at rest`,
      ).toEqual([])
    }
  })

  it('brightens on hover and on keyboard focus, and rings the focus (AC 6, UX-DR46)', () => {
    expect(valueOf(footerBlock('.footer-attribution-link:hover')!, 'color')).toBe(
      'var(--text-primary)',
    )
    // `:focus-visible`, and built from the three focus tokens that shipped in c2-1 with nothing
    // to point at. These are the first focusable elements in the codebase. The colour brightens
    // here too: hover-only state feedback is the shape UX-DR47 bans, applied to the brightening
    // rather than the underline (review find, 2026-07-30).
    const focus = footerBlock('.footer-attribution-link:focus-visible')!
    expect(valueOf(focus, 'color')).toBe('var(--text-primary)')
    expect(valueOf(focus, 'outline')).toBe('var(--focus-ring-width) solid var(--focus-ring)')
    expect(valueOf(focus, 'outline-offset')).toBe('var(--focus-ring-offset)')
    // No removal anywhere in the file, so there is no replacement to owe. COMMENTS STRIPPED
    // FIRST, and that was measured rather than reasoned: the prose above the rule in Footer.css
    // says the words "outline: none" to explain why it does not appear, and the un-stripped
    // check went red against a stylesheet that is entirely correct. A guard satisfied — or
    // failed — by something other than the thing it is checking is this epic's standing finding.
    expect(stripComments(sourceOf(FOOTER_CSS))).not.toMatch(/outline\s*:\s*none/)
  })

  it('gives each link a >= 24px hit box, both axes, that can actually apply (AC 7)', () => {
    const link = footerBlock('.footer-attribution-link')!
    // BOTH AXES — DESIGN.md:418 says "a >= 24x24px hit area", and delivering one axis while
    // citing the two-axis rule was a review find (2026-07-30).
    for (const axis of ['min-height', 'min-width']) {
      const minimum = valueOf(link, axis)
      expect(minimum, `${axis} is missing from the hit box`).toBeDefined()
      expect(Number.parseFloat(minimum!)).toBeGreaterThanOrEqual(24)
    }
    // THE HALF THAT WOULD BE TRUE IN SOURCE AND FALSE ON SCREEN: the minimums on a plain inline
    // box do nothing at all. The display mode is what makes the declarations mean anything, so
    // it is asserted beside them rather than assumed. `inline-block`, NOT `inline-flex`: text
    // decorations do not propagate into flex items, so a flex anchor renders the release-
    // condition underline as nothing (review find, 2026-07-30) — pinned as an exact value so a
    // tidy-up back to flex is red here rather than invisible until the manual eye check.
    expect(valueOf(link, 'display')).toBe('inline-block')
  })

  it('spends no accent and no semantic colour (DESIGN.md:288)', () => {
    // The accent marks LIVE AGENT ATTENTION. A footer link is neither live nor agent attention.
    // Keyed on the token PREFIX with an exact-match escape hatch for nothing — c2-9's review
    // found an open `--accent` prefix admitting `--accent-dim`, so this checks the family.
    const source = stripComments(sourceOf(FOOTER_CSS))
    for (const banned of ['--accent', '--negative', '--caution', '--positive', '--mana-']) {
      expect(source, `${FOOTER_CSS} spends ${banned}`).not.toContain(banned)
    }
  })

  it('ships no motion, so it owes no reduced-motion fallback (Decide-once #3)', () => {
    const source = stripComments(sourceOf(FOOTER_CSS))
    expect(source).not.toContain('transition')
    expect(source).not.toContain('animation')
  })
})

describe('the overlay slot (AC 7, AC 8, AC 10)', () => {
  it('is inset by the gutter token, not a literal (AC 7)', () => {
    // `--space-gutter`, not `--space-6`. The two are both 32px TODAY, but they are different
    // tokens with different jobs: `--space-6` is a step on the spacing scale, while
    // `--space-gutter` is the named distance that frames the window — and the overlay's whole
    // contract is that its inset COINCIDES with the shell's own frame (Q2 says so in as many
    // words). Pinned to `--space-6`, a later retune of the gutter would silently stop the
    // overlay aligning with the frame it is documented to align with, while this assertion
    // kept passing.
    //
    // This shipped as a ruled deviation from AC 7's original wording (review round 1); **AC 7
    // was then amended to match, by Brad's ruling 2026-07-28**, so the two now agree and this
    // is no longer a deviation from anything. `DESIGN.md` was the last artefact still saying
    // `{spacing.6}` here; story 15-3 corrected all three of its sites to `{spacing.gutter}` on
    // 2026-08-18 and closed the ledger entry, so every artefact and this assertion now name one
    // token for one distance.
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

  it('hides itself when it has no children at all (AC 9, the residue filled() cannot see)', () => {
    // READ THE SOURCE — jsdom applies no stylesheet, so `getComputedStyle` here would report
    // the unstyled default and pass for the wrong reason, which is this file's opening rule.
    //
    // The component refuses to mount the wrapper for every empty shape a CALLER can express,
    // but whether an arbitrary CHILD renders anything is not decidable without rendering it:
    // `overlay={<AgentView />}` is filled by every static measure and `AgentView` may still
    // return null. That leaves a full-window fixed element with no child nodes — AC 9's
    // click-swallower — and `:empty` is what closes it. (Greptile, PR #23.)
    const hidden = shellBlocks.find((b) => b.selector === '.app-shell-overlay:empty')
    expect(hidden, 'no .app-shell-overlay:empty rule in the shell stylesheet').toBeDefined()
    expect(valueOf(hidden!, 'display')).toBe('none')
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
  // family to point at, the declared-token count is pinned byte-for-byte against DESIGN.md's
  // frontmatter (65 since c2-9's ruled `--font-mono`; it read 64 here until that same commit
  // falsified it — review 2026-07-29), so adding one is a DESIGN.md ruling made in the open,
  // never a route around the pin — and it carries a comment naming
  // its source and why it is not a token. c2-9 (480px state panel) and
  // c4-4 (176px grid minimum) inherit a stated rule rather than a habit — and since the
  // review round of 2026-07-28 they inherit it as a GATE, not prose: the citation check runs
  // over EVERY component stylesheet, so the rule ~35 stories inherit is enforced the moment
  // each of them stages its CSS, not re-implemented per story.
  //
  // THIS LIST USED TO NAME "c2-7 (17px StatChip)" FIRST, and that prediction was WRONG —
  // measured in c2-7 and corrected here rather than left standing, because a prediction that
  // was measured wrong is exactly the sentence the next author trusts. The StatChip value is
  // spent through `font-size`, which is GATED (the font-* allowed-list admits only CSS-wide
  // keywords), so it never reached this rule at all. The boundary that mistake found: a
  // geometry literal is a value with NO token family to point at; a type size HAS one, and
  // the answer there is a different role token. c2-7 shipped four component stylesheets and
  // the only literals in them are hairline borders and a 6px dot — all cited, all caught by
  // the loop below.
  //
  // Scope stated plainly: px lengths only. `z-index: 20` is also a geometry literal and is
  // documented in prose beside its rule, but a bare unitless number cannot be told apart
  // from the ones in `minmax(0, 1fr)`, `flex: 1` and `min-width: 0`, so it is review's
  // rather than this guard's.
  // WIDENED BY c4-4, NOT WEAKENED (AC 2). This was `startsWith('src/components/')`, and it is
  // the ONE path-scoped guard a new component tree would have silently exited — which matters
  // more here than anywhere, because c4-4's `176px` grid minimum is exactly the literal this
  // rule exists to police. Of the three guards scoped to `src/components/`, the other two are
  // the primitives' coverage guard and `posture.test.ts`'s component rules, and a container is
  // rightly outside BOTH of those; this one has nothing to do with statefulness, so it follows
  // the component-shaped files wherever they live. A later tree of the same kind adds its root
  // HERE, in the open, and the anchor below is what makes forgetting to visible.
  const COMPONENT_ROOTS = ['src/components/', 'src/containers/']
  const componentStylesheets = shippedStylesheets.filter((f) =>
    COMPONENT_ROOTS.some((root) => f.startsWith(root)),
  )

  it('is reading the component stylesheets at all (non-vacuity), and the shell pins its two', () => {
    // The anchor: the shell is a component stylesheet, and its literals are exactly the two
    // the composition is made of. A NEW shell literal fails here first — deliberately: it is
    // a change to the pinned composition, and updating this list is the open way to make it.
    expect(componentStylesheets).toContain(SHELL_CSS)
    expect(pxLiteralsIn(shellSource).sort()).toEqual(['1100px', '452px'])
    // …and the widened root is REACHING the new tree rather than merely being listed. Without
    // this line the widening could be wrong (a typo in the prefix, a directory renamed) and
    // every literal in it would pass by never being read — the vacuity failure this file's own
    // doctrine calls the worse outcome. `176px` is the value at stake.
    expect(componentStylesheets).toContain('src/containers/CardGrid/CardGrid.css')
    expect(pxLiteralsIn(sourceOf('src/containers/CardGrid/CardGrid.css'))).toEqual(['176px'])
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

describe('the analysis pair row is 1:1 by CONSTRUCTION (story c4-8, Q6, AC 3)', () => {
  // WHY THIS READS THE STYLESHEET RATHER THAN RENDERING. `AnalysisRow.test.tsx` proves the
  // ARITY — one child, two children, none — and jsdom has no layout engine, so it cannot
  // observe the ratio those children resolve to. The specific silent failure: with
  // `flex-basis: auto` the wider panel's CONTENT decides the split, the pair is not 1:1 at all,
  // and every rendered assertion in that file still passes. The rule is therefore read, over
  // the same git-derived list every other guard in this suite walks.
  const ROW_CSS = 'src/components/AnalysisRow/AnalysisRow.css'
  const rowSource = sourceOf(ROW_CSS)
  const childRule = /\.analysis-row\s*>\s*\*\s*\{([^}]*)\}/.exec(rowSource)?.[1] ?? ''

  it('is reading the real stylesheet (non-vacuity)', () => {
    // `shippedStylesheets` is the module-scope git-derived list; an untracked stylesheet would
    // not be in it, so this is also the `git add` check for this file.
    expect(shippedStylesheets).toContain(ROW_CSS)
    expect(childRule.length, 'the `.analysis-row > *` rule was not found at all').toBeGreaterThan(
      10,
    )
  })

  it('gives every child a ZERO-basis flex factor, so the split is not content-driven', () => {
    expect(childRule).toMatch(/flex:\s*1\s+1\s+0\s*;/)
  })

  it('gives every child min-width: 0, so an unbreakable panel cannot widen the app', () => {
    // The per-item half of the argument `.app-shell-column` and `.app-shell-columns` both make:
    // a flex item's default `min-width` is `min-content`, and without this the app's ONE scroll
    // container inherits a horizontal overflow it does not own.
    expect(childRule).toMatch(/min-width:\s*0\s*;/)
  })

  it('uses NO two-track grid — the shape that leaves a dead half-width gutter', () => {
    // c4-7's Q1 rejected exactly this in the price column: "a visible empty column reads as a
    // loading failure". `repeat(2, minmax(0, 1fr))` with one child would do it to HALF the
    // fluid column, and it would look correct in every test until c4-9 shipped.
    expect(rowSource).not.toMatch(/grid-template-columns/)
    expect(rowSource).not.toMatch(/repeat\(/)
  })

  it('spends the panel gap through DESIGN.md’s own token and writes no px literal', () => {
    expect(rowSource).toContain('var(--space-panel-gap)')
    // Belt and braces with the citation guard above: that one requires a DESIGN.md reference
    // near any literal, and this says there is no literal to cite.
    expect(pxLiteralsIn(rowSource)).toEqual([])
  })

  it('HIDES itself when both panels render null — c4-9 closing c4-8’s empty row (Q10, AC 33)', () => {
    // THE OTHER HALF OF `App.test.tsx`'s land-only test, and it has to live here: jsdom applies
    // no stylesheet, so that file can only assert the PRECONDITION (`childNodes` is empty) while
    // the consequence is a CSS rule. Read as source, over the same git-derived list.
    //
    // c4-8 shipped an unconditional `<AnalysisRow>` in `App.tsx`'s deck arm, so a land-only deck
    // left the row's div in the DOM with `.app-shell-column`'s 24px gap still applied beneath
    // the grid — accepted posture, with c4-9 named to revisit it. `:empty` is the revisit, and
    // the reason it is the right one is that it needs NOTHING from `App.tsx`: no curve total, no
    // pip total, no second derivation of what `curve.ts` and `colours.ts` already own.
    const emptyRule = /\.analysis-row:empty\s*\{([^}]*)\}/.exec(rowSource)?.[1] ?? ''
    expect(emptyRule.length, 'the `.analysis-row:empty` rule was not found at all').toBeGreaterThan(
      5,
    )
    expect(emptyRule).toMatch(/display:\s*none\s*;/)

    // AND IT IS `display: none`, NOT `visibility: hidden` — the distinction is the whole point:
    // `visibility: hidden` leaves the element in the flex layout, so the parent's gap survives
    // and the phantom band this rule exists to remove would still be there.
    expect(emptyRule).not.toMatch(/visibility/)
    // Nor is the base rule hiding itself: a `display: none` on `.analysis-row` would hide the
    // row ALWAYS, which every rendered assertion in `App.test.tsx` would still pass (jsdom
    // applies no CSS) — the silent-failure shape this whole describe block is built around.
    const baseRule = /\.analysis-row\s*\{([^}]*)\}/.exec(rowSource)?.[1] ?? ''
    expect(baseRule).toMatch(/display:\s*flex\s*;/)
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
   * `export … from` re-exports are matched too (review 2026-07-29) — they load their module
   * exactly as an import does.
   */
  const importedModules = [
    ...shellComponent.matchAll(/(?:import|export)\s+(?:[^'"]*?\bfrom\s+)?['"]([^'"]+)['"]/g),
  ].map((m) => m[1])

  it('imports nothing but React types and its own stylesheet', () => {
    // A store import, a fetch helper or a hooks module would each pre-empt a design c3-1 and
    // c4-1 own. Asserted as an EXHAUSTIVE list rather than a blocklist: a module nobody
    // thought to ban is exactly the one that would get through — and the stylesheet is in the
    // list rather than checked separately, so a second bare import cannot hide beside it.
    //
    // `../filled` is here deliberately and its presence is the OPEN way to add it: deciding
    // whether a Fragment is empty needs value imports from react, and the next assertion pins
    // this file's react import to types only. Rather than carve an exception into a guard made
    // blunt on purpose, the helper moved to its own module — and this list still pins the set
    // exhaustively, so the exception is one named entry rather than a widened rule.
    //
    // It moved UP a directory in story c2-7 (Q3): Panel needs the identical logic for its
    // header slots, and `../AppShell/filled` would have made every primitive depend on the
    // shell's directory. The path in this list is half the move; FILLED_TS below is the other.
    expect(importedModules.sort()).toEqual(['../filled', './AppShell.css', 'react'])
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

  it('holds the helper module to the same posture', () => {
    // `../filled` is allowed react VALUE imports, which is the whole reason it exists — so the
    // no-state rule has to be asserted there too, or the exemption becomes the hiding place.
    const helper = sourceOf(FILLED_TS)
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/(^|[^:])\/\/[^\n]*/g, '$1')

    expect(helper).not.toMatch(/\buse[A-Z]\w*\s*\(/)
    expect(helper).not.toMatch(/(?<![\w.$])use\s*\(/)
    expect(helper).not.toMatch(/\b(fetch|XMLHttpRequest|EventSource|WebSocket)\s*\(/)
    expect(
      [...helper.matchAll(/(?:import|export)\s+(?:[^'"]*?\bfrom\s+)?['"]([^'"]+)['"]/g)].map(
        (m) => m[1],
      ),
    ).toEqual(['react'])
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
// The presentation-only primitives (stories c2-7 and c2-8; c2-7 AC 5, c2-8 AC 18)
// ---------------------------------------------------------------------------------------

describe('the component primitives are presentation-only, and that is asserted', () => {
  /**
   * The SAME shape the shell's own posture is asserted in, one story up: exhaustive import
   * lists, hooks by FAMILY rather than by name, and comments stripped so documentation does
   * not read as code.
   *
   * Why it is worth asserting at all rather than left to inspection: "these four hold no
   * state" is a decide-once ruling ~20 later component stories inherit, and the day one of
   * them needs a hook it has stopped being a presentation-only primitive. That is a SIGNAL —
   * the component belongs in a different category and its story should say so — and a signal
   * nobody is told about is not one. `useId` is included in the ban deliberately: it is the
   * most reasonable-looking hook a primitive could want (for `aria-labelledby`), which is
   * exactly why the region naming uses `aria-label` instead (Q4).
   *
   * IMPORT LISTS ARE EXHAUSTIVE, not blocklists, for the reason the shell's list gives: a
   * module nobody thought to ban is precisely the one that would get through. A store import,
   * a fetch helper or a hooks module would each pre-empt a design c3-1 and c4-1 own.
   */
  const PRIMITIVES: { file: string; imports: string[] }[] = [
    // `../filled` is Panel's one non-obvious entry, and it is the OPEN way to reuse the
    // helper (AC 17) rather than re-deriving five empty-shape cases that cost c2-6 a Greptile
    // round and two review rounds.
    { file: 'src/components/Panel/Panel.tsx', imports: ['../filled', './Panel.css', 'react'] },
    // Badge grew `../filled` and a VALUE import of `./tones` in review (2026-07-29): empty
    // children render nothing (the same AC 17 logic as Panel's header) and a runtime-unknown
    // tone clamps to neutral against the same list the per-tone tests anchor on.
    {
      file: 'src/components/Badge/Badge.tsx',
      imports: ['../filled', './Badge.css', './tones', 'react'],
    },
    { file: 'src/components/StatChip/StatChip.tsx', imports: ['./StatChip.css', 'react'] },
    {
      file: 'src/components/GroupHeader/GroupHeader.tsx',
      imports: ['./GroupHeader.css', 'react'],
    },
    // Story c2-8's two: the pip and the whole cost. ManaPip imports the parser's COLOUR ORDER
    // (a value) and its `ManaColour` type from one statement — two statements naming the same
    // module would list it twice here, which is the open cost of the exhaustive form working.
    // Neither imports react at all: the automatic JSX runtime means a presentation component
    // with no ReactNode prop needs no import, and the shorter list is the stronger assertion.
    {
      file: 'src/components/ManaPip/ManaPip.tsx',
      imports: ['../ManaCost/parse', './ManaPip.css'],
    },
    {
      file: 'src/components/ManaCost/ManaCost.tsx',
      imports: ['../ManaPip/ManaPip', './ManaCost.css', './parse'],
    },
    // Story c2-9's three. The panel imports `../filled` for the same reason Panel does — the
    // deck list's "is this empty" question is the c2-6 family exactly, and re-deriving it here
    // is what that module exists to prevent. No react import at all: nothing in its props is a
    // `ReactNode`, which is the stronger claim.
    {
      file: 'src/components/StatePanel/StatePanel.tsx',
      imports: ['../filled', './StatePanel.css', './copy'],
    },
    // The copy, and `imports: []` is the strongest form of "these are words and nothing else".
    { file: 'src/components/StatePanel/copy.ts', imports: [] },
    // The wire-token -> panel map. Both of its imports are TYPE-only, and `../../api/schema` is
    // the narrow alias module rather than the generated `./types` — the rule schema.ts states
    // and `wire-contract.test.ts` enforces. It reaches OUT of src/components/ for the first
    // time in this list, which is exactly why it is listed here rather than assumed harmless.
    {
      file: 'src/components/StatePanel/states.ts',
      imports: ['../../api/schema', './copy'],
    },
    // The three helper modules are held to the same posture, for the reason the shell's own
    // suite gives about `filled`: an exempted module is where the next evasion lives.
    { file: FILLED_TS, imports: ['react'] },
    { file: 'src/components/Badge/tones.ts', imports: [] },
    // Story c2-10's two. The footer takes NO PROPS and imports no react — the shortest import
    // list any component in this file has, which is the strongest available form of "this is
    // static" (Q4). Its text runs render as bare strings rather than Fragments, which is what
    // lets the react import stay absent.
    {
      file: 'src/components/Footer/Footer.tsx',
      imports: ['./Footer.css', './copy'],
    },
    // The attribution words and the two hrefs. `imports: []` again — and here it carries more
    // weight than tidiness: this module is a condition of public release (NFR-08), so a fetch
    // helper or a config import arriving in it would be the first thing to check.
    { file: 'src/components/Footer/copy.ts', imports: [] },
    // The mana-cost scanner. It is the first module in this list with a real ALGORITHM in it
    // rather than a datum, and it is held here for the same reason `tones.ts` is: a pure module
    // beside a presentation-only component is exactly where state would arrive first, because
    // nothing in its own file looks like a component. `imports: []` is the strongest form of
    // that claim — no react, no DOM, no store, nothing.
    { file: 'src/components/ManaCost/parse.ts', imports: [] },
    // Story c4-2's one, and the first component in this list that COMPOSES another: it renders
    // `Badge`, which until now had no on-screen consumer at all. No react import — its three
    // props are a string and two numbers, so nothing in them is a `ReactNode`, which is the
    // stronger claim. It is also a declared COPY module (`tests/copy-rules.test.ts`), because
    // the two size labels are the only words this story puts on screen; being both is the shape
    // `AppShell.tsx` already has, and the two lists ask different questions of the same file.
    {
      file: 'src/components/DeckBadges/DeckBadges.tsx',
      imports: ['../Badge/Badge', './DeckBadges.css'],
    },
    // Story c4-3's two, and the first component in this list whose PROPS are a discriminated
    // union rather than a flat bag: the loading well's member has one property, so there is
    // nothing to say in a well that must stay silent, and the unknown variant has no `name` for
    // a copy-paste to fill with a real card's.
    //
    // `../StatePanel/states` is the second cross-tree entry in this list after `states.ts`'s own
    // `../../api/schema`, and it is TYPE-ONLY: the variant union is built FROM `PlaceholderKey`
    // so a third placeholder key in that file fails `tsc` here. No react import — none of its
    // props is a `ReactNode`, which is what also makes the well unable to hide a caller's
    // content when it declares `aria-hidden`.
    //
    // NOTE WHAT IS ABSENT: `src/styles/card-geometry.css`. The shared card shape is @imported by
    // `src/index.css` rather than by the components that consume it, which is what keeps this
    // list free of a cross-tree stylesheet — `posture.test.ts`'s value-import rule would fail a
    // component importing `../../styles/…`, and four later stories would each have had to.
    {
      file: 'src/components/CardPlaceholder/CardPlaceholder.tsx',
      imports: ['../ManaCost/ManaCost', '../StatePanel/states', './CardPlaceholder.css', './copy'],
    },
    // The one authored string this story puts on screen. `imports: []` is not tidiness here: a
    // `ui/tests/` file may import an app module only if that module has no relative imports (the
    // measured `tsc -b` project-boundary rule), and `tests/unknown-card-copy.test.ts` imports
    // this one to assert the shipped label against EXPERIENCE.md byte-for-byte. An import added
    // here would silently un-gate the copy.
    { file: 'src/components/CardPlaceholder/copy.ts', imports: [] },
    // c4-8's analysis pair row. `AppShell.tsx:127` assigned the 1:1 pair to that story BY NAME —
    // "c4-8 composes the row, c4-9 supplies the second panel" — so the row had to be built one
    // story before its second child exists, and it is here rather than in `CONTAINERS` because
    // it holds no state, calls no hook, reads no store and attaches no handler. One prop, and it
    // is `children`. The `react` import is the `ReactNode` type, exactly as `Panel`'s is.
    {
      file: 'src/components/AnalysisRow/AnalysisRow.tsx',
      imports: ['./AnalysisRow.css', 'react'],
    },
  ]

  const withoutComments = (source: string) =>
    source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1')

  it('is reading all ten primitives and all seven helpers (non-vacuity)', () => {
    // Every assertion below loops over PRIMITIVES. A list that had quietly lost a member — a
    // renamed directory, a component moved — would let that member pass by never being read,
    // which is the vacuity failure this file's own doctrine calls the worse outcome. Proving
    // each file EXISTS and is non-trivial is what stops "nothing is wrong" reading the same
    // as "nothing was read".
    // 12 until story c2-10's `Footer.tsx` and `Footer/copy.ts`; 14 until c4-2's `DeckBadges.tsx`;
    // 15 until c4-3's `CardPlaceholder.tsx` and its `copy.ts` — which is the coverage guard below
    // working as designed rather than a number being bumped: the component was written,
    // `git ls-files` saw it, and this list had to name it before the suite went green again.
    // 18 at c4-8's `AnalysisRow` — the pair row `AppShell.tsx:127` assigned to that story by
    // name, built one story before the panel that shares it.
    expect(PRIMITIVES).toHaveLength(18)
    for (const { file } of PRIMITIVES) {
      expect(sourceOf(file).length, `${file} is empty or missing`).toBeGreaterThan(200)
    }
  })

  it('covers every component module on disk — the list cannot silently fall behind', () => {
    // The review (2026-07-29) found PRIMITIVES hand-kept while the stylesheet scan is
    // git-derived: a FIFTH component added under src/components/ would escape every assertion
    // in this suite by never being listed. Same authority as the stylesheet scan — git, not
    // readdir — so an untracked module cannot pass vacuously either. Test files are the dom
    // project's; everything else under src/components/ must be in the list or in the shell's
    // own suite above.
    const onDisk = execFileSync(
      'git',
      ['ls-files', 'src/components/*.ts', 'src/components/*.tsx'],
      {
        cwd: uiRoot,
        encoding: 'utf8',
      },
    )
      .split('\n')
      .filter(Boolean)
      .filter((f) => !/\.test\.tsx?$/.test(f))

    const covered = [...PRIMITIVES.map((p) => p.file), SHELL_TSX].sort()
    expect(onDisk.sort()).toEqual(covered)
  })

  it.each(PRIMITIVES)('$file imports exactly what it declares', ({ file, imports }) => {
    // `from '…'` alone would miss `import './subscribe'` — no `from` clause, no call parens —
    // which is precisely how a module that subscribes on load walks past an "imports nothing
    // but React" check. Bare side-effect imports are matched too, and the stylesheet is IN
    // the list rather than checked separately, so a second bare import cannot hide beside it.
    // `export … from` and `export * from` are matched too (review 2026-07-29): a RE-EXPORT
    // loads its module exactly as an import does, and an "exhaustive" list that only read
    // `import` statements would never see it.
    const source = withoutComments(sourceOf(file))
    const modules = [
      ...source.matchAll(/(?:import|export)\s+(?:[^'"]*?\bfrom\s+)?['"]([^'"]+)['"]/g),
    ].map((m) => m[1])
    expect(modules.sort()).toEqual(imports)

    // The react import must be TYPE-ONLY. Hooks are VALUE imports, so this one line closes the
    // aliasing evasion (`import { useState as s }` never matches a name-keyed regex) at the
    // door instead of chasing spellings at the call site. `filled.ts` is the ONE exemption —
    // deciding whether a Fragment is empty needs `Fragment` and `isValidElement` as values —
    // and it is exempted by name here, in the open. The review (2026-07-29) noted the
    // exemption made it the ONE module where an aliased hook would pass every guard, so its
    // react import is pinned to the exact three names instead: an aliased
    // `useSyncExternalStore as f` cannot ride in beside them without failing this match.
    if (file === FILLED_TS) {
      expect(source).toMatch(
        /import\s+\{\s*Fragment,\s*isValidElement,\s*type ReactNode\s*\}\s+from 'react'/,
      )
    } else {
      expect(source).not.toMatch(/import\s+(?!type\b)[^;\n]*?from\s+['"]react['"]/)
    }
    // And the two runtime routes around static imports are closed by name.
    expect(source).not.toMatch(/\b(?:require|import)\s*\(/)
  })

  it.each(PRIMITIVES)('$file holds no state and subscribes to nothing', ({ file }) => {
    const source = withoutComments(sourceOf(file))

    // Keyed on the hook API FAMILY rather than on named hooks, so a hook this list never
    // heard of is still caught — including React 19's `use()`, the one LOWERCASE hook, which
    // a `use[A-Z]` prefix check alone would wave through.
    expect(source).not.toMatch(/\buse[A-Z]\w*\s*\(/)
    expect(source).not.toMatch(/(?<![\w.$])use\s*\(/)
    expect(source).not.toMatch(/\b(fetch|XMLHttpRequest|EventSource|WebSocket)\s*\(/)
  })

  it.each(PRIMITIVES)('$file has no behavioural contract — no handler, no ref', ({ file }) => {
    const source = withoutComments(sourceOf(file))

    // AC 5's "respond to no interaction", as a shape rather than a list of event names: an
    // `onSomething` PROP declaration and an `onSomething=` JSX attribute are the only two ways
    // a handler reaches a component, and both are caught by the capital after `on`.
    expect(source).not.toMatch(/\bon[A-Z]\w*\s*\??\s*:/)
    expect(source).not.toMatch(/\bon[A-Z]\w*\s*=/)
    // A ref is state's other door: it is how a presentation-only component starts measuring,
    // focusing or observing the DOM it was only supposed to describe. BOTH positions (review
    // 2026-07-29): the handler check reads declaration and JSX, and the ref check used to read
    // JSX only — a `ref?: Ref<…>` PROP declaration was invisible.
    expect(source).not.toMatch(/\bref\s*=/)
    expect(source).not.toMatch(/\bref\s*\??\s*:/)
    // NO SPREAD in the components (review 2026-07-29). A `{...rest}` onto the DOM node is the
    // single most common way a presentation component silently grows a behavioural surface:
    // it defeats the handler check AND the ref check at once, because the names never appear
    // in this file. Rest/spread has no legitimate use in a component whose entire contract is
    // a handful of named props — if one ever needs it, that is the category-change signal
    // AC 5 exists to raise, not a reason to widen this rule. `filled.ts` is exempt for the
    // stated reason that it is not a component: it takes no props to spread, it legitimately
    // spreads an iterable into an array, and its own threat model (an aliased hook) is closed
    // by the pinned react import above.
    if (file !== FILLED_TS) {
      expect(source).not.toMatch(/\.\.\./)
    }
  })

  it('reads code, not the documentation about the code', () => {
    // The non-vacuity half of the comment stripping, in the same shape the shell's suite uses.
    // Panel's prose DOES name `useId` — it explains why the region uses `aria-label` instead —
    // so if stripping ever regressed, the hook assertion above would fail on the
    // documentation, and the repair someone would reach for is deleting the explanation.
    const panel = sourceOf('src/components/Panel/Panel.tsx')
    expect(panel).toMatch(/useId/)
    expect(withoutComments(panel)).not.toMatch(/useId/)
  })

  it('is the WHOLE of src/components/, with no container smuggled in beside it (c4-4, AC 1)', () => {
    // The other direction of c4-4's Q1 ruling, and the reason `src/components/` can still be
    // described in one sentence. Every assertion in this describe block loops over PRIMITIVES,
    // and PRIMITIVES is proven to equal the directory by the coverage guard above — so
    // "everything under src/components/ is presentation-only" is TOTAL, with no exempted member
    // and no filtered-out list. That totality is what makes `posture.test.ts`'s three
    // `it.each(componentSources)` blocks safe to leave keyed on the raw directory, and it is
    // what makes a primitive importing a container a red test for free (see CONTAINERS below).
    expect(PRIMITIVES.map((p) => p.file).every((f) => f.startsWith('src/components/'))).toBe(true)
    expect(PRIMITIVES.some((p) => p.file.startsWith('src/containers/'))).toBe(false)
  })

  it("keeps the mock's min-width out of StatChip.css (AC 11), where the source is actually read", () => {
    // Moved here from StatChip.test.tsx by review (2026-07-29): the DOM version asserted the
    // inline `style` attribute, which a `min-width` in the STYLESHEET would never touch —
    // jsdom applies no CSS, so that test passed vacuously for the exact defect it named.
    // DESIGN.md's `components.stat-chip` declares no min-width, so there is no truthful
    // citation for one; the chip sizes to its content.
    expect(sourceOf('src/components/StatChip/StatChip.css')).not.toMatch(/\bmin-width\s*:/)
  })
})

// ---------------------------------------------------------------------------------------
// The containers (story c4-4, AC 1, AC 2) — the category for a component that BEHAVES
// ---------------------------------------------------------------------------------------

describe('the containers are a declared category with a posture of its own', () => {
  /**
   * WHY THIS LIST EXISTS AT ALL, and why the answer is "because of c4-4".
   *
   * The block above is a SET EQUALITY over `src/components/`, and every member of it is banned
   * from holding a hook of any family, from declaring or attaching an `on*` handler, from
   * holding a `ref` in either position, from spreading, and from importing React as a value.
   * `posture.test.ts` bans three of those a second time over the same directory. A card tile
   * needs `<img onLoad>` to know when the pixels exist and a `ref` to survive the warm-cache
   * race — so a module for it under `src/components/` is a RED TEST BOTH WAYS: listed, the
   * posture bans fire; unlisted, the coverage guard fires.
   *
   * That is not a gate to route around. It is the category-change signal this file says out
   * loud in its own prose — *"the day a primitive needs a hook it has stopped being
   * presentation-only — that is a SIGNAL — the component belongs in a different category and
   * its story should say so"*. c4-4 is the story that says so.
   *
   * ==== WHY A NEW TREE RATHER THAN A SECOND LIST IN THE SAME DIRECTORY ==================
   * The cheaper-looking answer was to keep the files under `src/components/` and widen the
   * covered set with a second list here. MEASURED, that costs more than it saves, and the
   * decisive number is not the count of guards — it is what one of them would stop seeing:
   *
   *   `posture.test.ts:197` bans a value import from outside the tree, and its filter is
   *   `!target.startsWith('src/components/')`. A container living INSIDE that directory would
   *   have to be exempted from the rule — and the exemption would make a PRESENTATION-ONLY
   *   PRIMITIVE IMPORTING A STATEFUL CONTAINER invisible to every guard in the repo, because
   *   the import target would still start with `src/components/`. A primitive that renders a
   *   container has silently acquired everything the primitive posture exists to deny.
   *
   *   With the containers OUTSIDE that tree, the same existing rule catches it with no new
   *   guard, no edit and no exemption — the firing proof is in `posture.test.ts`. The layering
   *   (primitives know nothing of containers; containers compose primitives) is enforced by a
   *   rule that was already green.
   *
   * The real cost of the new tree is ONE guard that had to be widened rather than weakened:
   * the `px`-literal DESIGN.md citation check below is scoped by directory, and it is the gate
   * that polices this story's own `176px` grid minimum. Its scope is now a list of roots. The
   * other two path-scoped guards — this file's coverage guard and posture's component rules —
   * are exactly the ones a container must not be held to, so there is nothing to replace.
   *
   * ==== THE POSTURE, WRITTEN DOWN =======================================================
   * A container MAY hold state, call hooks of any family, declare and attach handlers, hold a
   * `ref`, read the store through `src/state/`, and compose primitives.
   *
   * It may NOT reach the network (the door is `src/api/client.ts` and stays exhaustively
   * named), import a state library directly, write a store slice from outside its own module,
   * or declare a design token. The first three are asserted below; the fourth is a stylesheet
   * property and `token-usage.test.ts` already scans every tracked `.css` in the repo.
   *
   * The import lists are EXHAUSTIVE for the reason the primitives' are: a module nobody
   * thought to ban is precisely the one that would get through.
   */
  const CONTAINERS: { file: string; imports: string[] }[] = [
    // c6-5's agent view — the app's FIRST modal, first focus trap and first `role="dialog"`,
    // and a container for three reasons at once, any ONE of which would fail `posture.test.ts`
    // next door: it holds hooks (`useId`, `useState`, three `useEffect`s and three refs), it
    // attaches handlers, and it registers a listener on `document`. It composes NO primitive —
    // deliberately, and the temptation is real: `Panel`'s header is structurally identical to
    // this shell's, but `Panel` is presentation-only by guard (a `<section aria-label>` with no
    // `role`, no `aria-modal`, no refs and no hooks) and this needs all four. The visual kinship
    // comes from sharing tokens, not markup. `../focusHome` is the third caller of the hand-off
    // c4-11 extracted, and it reaches NO state module at all: the store is `App.tsx`'s to read,
    // and the three dismissal gestures call an `onClose` prop rather than a verb — which is what
    // kept this shell content-agnostic enough for c6-7 to fill and c6-8 to extend — both did.
    {
      file: 'src/containers/AgentView/AgentView.tsx',
      imports: ['../focusHome', './AgentView.css', './copy', 'react'],
    },
    // c6-5's copy module — the TENTH under `src/containers/` and the thirteenth in the app,
    // both counted from `git ls-files` rather than from the entry above (the running "Nth in the
    // app" ordinals in this list disagree with each other across c4-8, c4-10 and c4-12, and
    // adding a fourth guess would deepen that rather than settle it — noted for review, and
    // deliberately not repaired here, since renumbering five other stories' comments is not this
    // story's diff). Two chrome strings, the "AGENT VIEW" kicker and
    // the "Close · esc" pill label, both transcribed from DESIGN.md's shell row. `imports: []`
    // for `CardDetail/copy.ts`'s measured reason: `tests/` is the `nodenext` project and `src/`
    // the `bundler` one, so a `ui/tests` file may import an app module only if that module has no
    // relative imports of its own — and `App.test.tsx` imports this one.
    { file: 'src/containers/AgentView/copy.ts', imports: [] },
    // c6-6's view BODY, FILLED BY c6-7 — the first module to render anything a push carries.
    // c6-6 shipped the empty-push state real and returned `null` for a non-empty one because the
    // rows were the next story's; it was named for the VIEW rather than for the state precisely
    // so that c6-7 could extend this file instead of creating a second one, and that prediction
    // is what this entry now records as fact. `../../state/agentView` is still a TYPE-only
    // import (`AgentViewContent`) and it still reaches the STATE layer rather than `src/api/`:
    // translating the envelope is the store's job, and a body that took a `SuggestionsPayload`
    // would be a second reader of the wire with a second opinion about absent fields.
    //
    // THE IMPORT SET GREW BY EIGHT AND EVERY ONE OF THEM IS A CONTRACT THIS SURFACE INHERITS
    // rather than a convenience: three primitives it composes (`Badge`, `CardPlaceholder`,
    // `ManaCost` — none of them re-implemented, which is the whole reason `src/components/` is a
    // closed set), the card cache (`../../state/cards` — this is the FIRST consumer that must
    // hydrate its OWN ids, because suggested cards are not in the deck and no sweep will ever
    // reach them; AD-12 names agent views as the reason that cache is shared), the faces store
    // (Q5 — flip state is honoured so a printing shows the same face everywhere, while the flip
    // CONTROL is not rendered in a row), the inspection slice (the five verbs unrenamed, which
    // is what `inspection.ts:163` wrote them location-agnostic FOR), and the two image modules
    // `../CardTile/imageUrl` + `../useCardArt` — reached ACROSS containers exactly as c4-5's
    // detail panel reaches them, which is the extraction those two files exist for. `react` is
    // here for the hydration effect. It holds hooks, handlers and a ref, so `posture.test.ts`
    // would fail it under `src/components/` three times over — which is what c6-6's header said
    // when it put the module in this tree a story early.
    {
      file: 'src/containers/SuggestionsView/SuggestionsView.tsx',
      imports: [
        '../../components/Badge/Badge',
        '../../components/CardPlaceholder/CardPlaceholder',
        '../../components/ManaCost/ManaCost',
        '../../state/agentView',
        '../../state/cards',
        '../../state/faces',
        '../../state/inspection',
        '../CardTile/imageUrl',
        '../frontFaceCost',
        '../useCardArt',
        './SuggestionsView.css',
        './copy',
        'react',
      ],
    },
    // c6-6's copy module. One TEMPLATE — the artefact's row writes `{kind}` — plus the
    // placeholder it names and the one-line builder that fills it. `imports: []` for
    // `CardDetail/copy.ts`'s measured reason: `tests/` is the `nodenext` project and `src/` the
    // `bundler` one, so a `ui/tests` file may import an app module only if that module has no
    // relative imports of its own, and `tests/empty-push-copy.test.ts` imports this one. That
    // constraint is also why the builder takes a plain `string` rather than the store's kind
    // union — a type-only import would still be an import.
    { file: 'src/containers/SuggestionsView/copy.ts', imports: [] },
    // 16.1's swaps view — the SECOND view body, built as `SuggestionsView.tsx`'s structural
    // sibling and inheriting the same contracts through almost the same import set. The
    // differences are the story: no `Badge` and no `ManaCost` (a swap row's tiles carry art and
    // a tinted micro label, not a head line), `StatChip` instead (the artefact's chip row
    // reduces to the confidence chip — price and curve are struck by the no-price-data ruling),
    // and `../SuggestionsView/copy` reached ACROSS
    // containers exactly as `../CardTile/imageUrl` is — the empty-push template is kind-generic
    // by design, and a second copy module would be the drift `tests/empty-push-copy.test.ts`
    // exists to prevent. It holds hooks per TILE (two cards per row is why `SwapTile` exists),
    // handlers and the card cache's second self-hydrating consumer, so `posture.test.ts` would
    // fail it under `src/components/` three times over. `../../state/agentView` is TYPE-only,
    // reaching the STATE layer rather than `src/api/` — the props derive from the store union's
    // own `swaps` arm, never from wire types.
    {
      file: 'src/containers/SwapsView/SwapsView.tsx',
      imports: [
        '../../components/CardPlaceholder/CardPlaceholder',
        '../../components/StatChip/StatChip',
        '../../state/agentView',
        '../../state/cards',
        '../../state/faces',
        '../../state/inspection',
        '../CardTile/imageUrl',
        '../SuggestionsView/copy',
        '../useCardArt',
        './SwapsView.css',
        'react',
      ],
    },
    // 16.2's tier-list view — the THIRD view body, `SwapsView.tsx`'s structural sibling with
    // the same inheritance story. The differences are the story again: no `StatChip` (a tier
    // row carries a chip, a note and a strip — no per-item stat exists to chip), and
    // `../frontFaceCost` joins because each tile's accessible name is the card's own front-face
    // name in a visually hidden span (a strip tile has no label element the way a swap tile
    // does, and a nameless button is an anonymous Tab stop). `../SuggestionsView/copy` is
    // reached ACROSS containers for the same kind-generic-template reason, and NO copy module
    // of its own exists — every word the view renders is wire data. It holds hooks per TILE
    // (up to sixty cards per row is why `TierTile` exists), handlers and the card cache's third
    // self-hydrating consumer, so `posture.test.ts` would fail it under `src/components/` three
    // times over. `../../state/agentView` is TYPE-only, reaching the STATE layer rather than
    // `src/api/` — the props derive from the store union's own `tier_list` arm.
    {
      file: 'src/containers/TierListView/TierListView.tsx',
      imports: [
        '../../components/CardPlaceholder/CardPlaceholder',
        '../../state/agentView',
        '../../state/cards',
        '../../state/faces',
        '../../state/inspection',
        '../CardTile/imageUrl',
        '../SuggestionsView/copy',
        '../frontFaceCost',
        '../useCardArt',
        './TierListView.css',
        'react',
      ],
    },
    // c6-8's agent-views nav — the header pills. It reads the agent-view store through TWO
    // per-kind selector hooks and calls one verb on it, which is the whole of its state
    // coupling; `../../api/schema` is a TYPE-only import for the kind union (the rule below
    // reads the specifier, so it is listed either way), and it is reached rather than re-spelled
    // because `schema.ts` is the only home for a wire-derived alias. `react` is here for
    // `useId`, which generates the `aria-describedby` target on a quiet pill. It calls hooks and
    // reads a store, so `posture.test.ts` would fail it under `src/components/` twice over.
    {
      file: 'src/containers/AgentViewsNav/AgentViewsNav.tsx',
      imports: [
        '../../api/schema',
        '../../state/agentView',
        './AgentViewsNav.css',
        './copy',
        './pushTime',
        'react',
      ],
    },
    // c6-8's time formatter, and it is a module of its own for a MECHANICAL reason rather than a
    // conceptual one: `react-refresh/only-export-components` fails a `.tsx` that exports anything
    // but components, and the formatter must be exported because its callers' tests cannot assert
    // its bytes (jsdom inherits the host TZ and ICU build, so a literal `'14:32'` expectation is a
    // machine-dependent test — they compute expectations through the function instead).
    // `frontFaceCost.ts` and `deckMemory.ts` are the shipped precedents for a one-idea module
    // extracted from a container. `imports: []` — it reaches nothing, not even the kind union.
    { file: 'src/containers/AgentViewsNav/pushTime.ts', imports: [] },
    // c6-8's copy module. THREE strings and deliberately not seven: the four PILL LABELS are
    // `AGENT_VIEW_LABELS` in `src/state/agentView.ts`, because c6-6's review ruled that the word
    // for a kind has one owner in the state layer — a view's fallback title and its nav pill's
    // label are the same word. What is here is what belongs to this container alone: the group's
    // kicker, the quiet pill's sentence and the word beside the unread dot. `imports: []` for
    // `CardDetail/copy.ts`'s measured reason, and `tests/agent-views-nav-copy.test.ts` is the
    // importer that makes the constraint load-bearing.
    { file: 'src/containers/AgentViewsNav/copy.ts', imports: [] },
    // c4-4's grid. It holds NO state — a container may, it need not — and it is here because it
    // composes a container and reads the derivation in `src/state/`, either of which
    // `posture.test.ts` would fail under `src/components/`. `../../state/deckGroups` is a
    // TYPE-only import; the rule below reads the specifier, so the entry is listed either way.
    // c4-12 took up the invitation this file's own header left ("a place for c4-12 to put its
    // line"): the empty-deck sentence renders HERE, replacing the `<ul>`. `../../state/deckGroups`
    // was already listed as a TYPE-only import and is now a VALUE one too — `deckIsEmpty`, the one
    // expression `App.tsx`'s `hasCards` is the negation of. That is the whole visible cost of the
    // predicate landing beside `DeckBoards` instead of in a fifth spelling, and this list is where
    // it shows. `./copy` is the new module.
    {
      file: 'src/containers/CardGrid/CardGrid.tsx',
      imports: [
        '../../components/Panel/Panel',
        '../../state/deckGroups',
        '../CardTile/CardTile',
        './CardGrid.css',
        './copy',
      ],
    },
    // c4-12's copy module — the SIXTH in this tree and the ninth in the app. One sentence, the
    // empty-deck line, transcribed byte-for-byte from EXPERIENCE.md. `imports: []` for
    // `CardDetail/copy.ts`'s measured reason: `tests/` is the `nodenext` project and `src/` the
    // `bundler` one, so a `ui/tests` file may import an app module only if that module has no
    // relative imports of its own. `tests/empty-deck-copy.test.ts` imports this one.
    { file: 'src/containers/CardGrid/copy.ts', imports: [] },
    // c4-4's tile, and the module that made this category necessary: a hook, a `ref` and — as of
    // c4-5 — SEVEN `on*` handlers, every one of them banned in the directory next door. TWO
    // stylesheets, deliberately — see QuantityBadge.css's header for the CARD_SHAPED collision
    // that separates them. c4-5 added the inspection verbs and moved the art state machine into
    // the shared hook, which is why `../useCardArt` and `../../state/inspection` are here and
    // `useState`/`useCallback` no longer are.
    // c4-6 added three: the flip control it mounts as a SIBLING of its own button, the face store
    // that decides which side is showing, and the one mirror of `resolve_face_images` — which the
    // tile needs for itself, to decide whether to render a second stacked `<img>` at all. It is
    // still the module that made this category necessary.
    {
      file: 'src/containers/CardTile/CardTile.tsx',
      imports: [
        '../../components/CardPlaceholder/CardPlaceholder',
        '../../state/faces',
        '../../state/inspection',
        '../FlipControl/FlipControl',
        '../imagedFaces',
        '../useCardArt',
        './CardTile.css',
        './QuantityBadge.css',
        './imageUrl',
        'react',
      ],
    },
    // c4-5's detail panel. The most connected container in the tree, and every one of its
    // imports is a permitted root: three primitives it COMPOSES, three state modules it READS
    // (never writes — the verbs live in the slice), one sibling container's path builder, its
    // own two stylesheets and its own copy module. No `zustand`, no `src/api/client`, no
    // `fetch` — the panel decides that a record is needed and `hydrateCard` owns the request.
    // c4-6 added three: the face store, the flip control it mounts as its own copy at the art
    // box's top-left (UX-DR15), and the shared `resolve_face_images` mirror it needs to know
    // whether to draw a second stacked face at `size=large`.
    {
      file: 'src/containers/CardDetail/CardDetail.tsx',
      imports: [
        '../../api/schema',
        '../../components/CardPlaceholder/CardPlaceholder',
        '../../components/ManaCost/ManaCost',
        '../../components/Panel/Panel',
        '../../state/cards',
        '../../state/deckGroups',
        '../../state/faces',
        '../../state/inspection',
        '../CardTile/imageUrl',
        '../FlipControl/FlipControl',
        // c4-11's extraction. The four-line focus hand-off this panel SHIPPED FIRST (c4-5's
        // unpin control, review 2026-08-05) moved to the tree root when the skip link became its
        // second caller — AC 6 requires "exactly one focus home and one implementation of it".
        // The specifier appearing here is the whole visible cost of the extraction, which is what
        // this list is for; `CardDetail.test.tsx:559-579` passing UNCHANGED is what proves it was
        // an extraction rather than a rewrite.
        '../focusHome',
        '../imagedFaces',
        '../useCardArt',
        './CardDetail.css',
        './CardDetailChrome.css',
        './copy',
        './deckMemory',
        'react',
      ],
    },
    // The deck-transition memory (review 2026-08-05): the one deck-shaped fact the panel's
    // inspection clearing needs, module-scope so it survives the panel unmounting on a surface
    // flip. Its own file for `imageUrl`'s stated reason — `react-refresh/only-export-components`
    // makes a helper export from a component file an ESLint error — and NOT in the inspection
    // slice, whose header promises it holds no deck. One import, and it is a TYPE.
    {
      file: 'src/containers/CardDetail/deckMemory.ts',
      imports: ['../../state/deckGroups'],
    },
    // c4-5's copy module — the first one in this tree. `imports: []` for the reason
    // `StatePanel/copy.ts` and `CardPlaceholder/copy.ts` are import-free: `tests/` is the
    // `nodenext` project and `src/` the `bundler` one, so a `ui/tests` file may import an app
    // module only if that module has no relative imports of its own (measured at c3-9 — twelve
    // TS2835 errors with `npm test` green throughout). `tests/pin-announcement-copy.test.ts`
    // imports this one.
    { file: 'src/containers/CardDetail/copy.ts', imports: [] },
    // The three art states and the two halves of the browser-cache race, shared by the tile and
    // the panel from c4-5 onward. It sits at the ROOT of this tree rather than inside either
    // consumer, which is `src/components/filled.ts`'s precedent stated in its own header: "a
    // helper shared by two components does not live inside one of them".
    { file: 'src/containers/useCardArt.ts', imports: ['react'] },
    // c4-6's flip control — the DFC face toggle, mounted TWICE (the tile's frame and the detail
    // panel's art box) from ONE module, because UX-DR15 asks the panel for "its own copy at the
    // same spec" and two components would be two chances to drift. It reads two stores and
    // attaches a handler, every one of which is banned next door. It imports the inspection slice
    // NOT AT ALL, and that absence is load-bearing: decide-once rule 15 is "a flip is not an
    // inspection", and an exhaustive import list is the strongest available form of it — there is
    // no verb in scope to call by accident.
    {
      file: 'src/containers/FlipControl/FlipControl.tsx',
      imports: ['../../state/faces', '../imagedFaces', './FlipControl.css', './copy'],
    },
    // c4-6's copy module — the SECOND in this tree, and the fourth in the app. One string, the
    // control's accessible name. `imports: []` for `CardDetail/copy.ts`'s reason: `tests/` is the
    // `nodenext` project and `src/` the `bundler` one, so a `ui/tests` file may import an app
    // module only if that module has no relative imports of its own.
    { file: 'src/containers/FlipControl/copy.ts', imports: [] },
    // c4-7's deck list — the right column's second panel, and the FIRST production consumer of
    // two primitives that had never been on a screen: `GroupHeader` (zero consumers since it
    // shipped at c2-7) and `Panel` at `level="default"`. It is a container rather than a
    // primitive by the c4-4 Q1 ruling, and it needs the category for the same three reasons the
    // tile did: it calls hooks (`useIsLiveTarget`, `useCardEntry`), it declares five `on*`
    // handlers, and it reads the store through `src/state/`. `../../api/schema` and
    // `../../state/deckGroups` are TYPE-only imports; the rule reads the specifier, so both are
    // listed either way.
    {
      file: 'src/containers/DeckList/DeckList.tsx',
      imports: [
        '../../api/schema',
        '../../components/GroupHeader/GroupHeader',
        '../../components/ManaCost/ManaCost',
        '../../components/Panel/Panel',
        '../../state/cards',
        '../../state/deckGroups',
        '../../state/inspection',
        // Was `./frontFaceCost` until c4-9 promoted that module to this tree's root, where a
        // helper with two consumers belongs. The specifier moving is the whole visible cost of
        // the promotion, and it is visible HERE, which is what this list is for.
        '../frontFaceCost',
        './DeckList.css',
        './copy',
      ],
    },
    // c4-7's copy module — the THIRD in this tree, the fifth in the app. The panel title, the two
    // board labels nobody specified, and the nine type-group headings. `imports: []` is
    // load-bearing here for a sharper reason than usual: AC 19 wants the label map coupled to
    // `TypeGroup` in both directions, which would ordinarily be `satisfies Record<TypeGroup, …>`
    // — and that needs an import this module may not have, because `TS2835` is a RESOLUTION error
    // that fires against the specifier whether or not `import type` erases it at emit. So the map
    // is declared here and ASSERTED in `DeckList.tsx`, which is `CardPlaceholder`'s shape exactly.
    { file: 'src/containers/DeckList/copy.ts', imports: [] },
    // c4-7's front-face resolution. Its own module because `react-refresh/only-export-components`
    // is an ESLint error, so a helper exported from a component file breaks fast refresh — the
    // fifth application of that split after `imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts` and
    // `useCardArt.ts`. It answers one question in two halves: the NAME is free from the deck
    // payload (99.0% of faced cards store the combined string), while the COST is blank at the
    // top level for 87.8% of them and reachable only through the hydration cache — which is why
    // a pure string helper needs `../../state/cards` for a TYPE.
    // MOVED UP ONE LEVEL AT c4-9, and the move is the decision this entry records. It lived at
    // `src/containers/DeckList/frontFaceCost.ts` for exactly as long as it had one consumer;
    // c4-9's colour bar needs the same three-shape resolution (a pip count is a count of the
    // FRONT FACE's pips), so there are now two, in two different container directories.
    // `filled.ts`'s header states the rule — *"a helper shared by two components does not live
    // inside one of them"* — and `imagedFaces.ts` and `useCardArt.ts` sit at this tree's root
    // under it. `imageUrl.ts` stays inside `CardTile/` because it still has one consumer, which
    // is the same rule pointing the other way.
    //
    // ⚠️ A CORRECTION TO c4-9's OWN PREMISE, worth leaving here: that story's context says a
    // container importing from a sibling container's directory *"has no precedent in this
    // repo"*. It has one — `CardTile.tsx` imports `../FlipControl/FlipControl` — and the roots
    // check below permits the shape outright. So the move was chosen on the shared-helper rule,
    // not on the absence of a precedent that in fact exists.
    {
      file: 'src/containers/frontFaceCost.ts',
      imports: ['../api/schema', '../state/cards'],
    },
    // c4-8's mana curve. The SHORTEST import list of any container in this tree, and that is the
    // story's headline rather than an accident: `CardSummary.cmc` rides on the deck payload, so
    // this panel reaches for no cache, no hook and no network — it composes one primitive, reads
    // the derivation `src/state/` already performed, and derives its seven numbers from it. It is
    // the third reader of `surface.boards`, after `CardGrid` and `DeckList`.
    {
      file: 'src/containers/ManaCurve/ManaCurve.tsx',
      imports: [
        '../../components/Panel/Panel',
        '../../state/deckGroups',
        './ManaCurve.css',
        './copy',
        './curve',
        'react',
      ],
    },
    // c4-8's copy module — the FOURTH in this tree, the tenth in the app. `imports: []` for the
    // settled `TS2835` reason, and one that earns it: the per-bar name BUILDER lives here rather
    // than in the component because `copy-rules.test.ts` declares "a string reaching an
    // `aria-label` through an expression" as a residue it cannot read, and declaring the words
    // where the content half scans them is what closes it before a reviewer has to.
    { file: 'src/containers/ManaCurve/copy.ts', imports: [] },
    // c4-8's derivation. Its own module for the same `react-refresh/only-export-components`
    // reason as `frontFaceCost.ts` — the SIXTH application of that split. It reuses `frontFace`
    // and deliberately does NOT reuse `groupOf` — see its header for the 32 corpus lands that
    // reuse would have counted as spells.
    //
    // `../../state/deckGroups` appears TWICE, and that is the exhaustive form working rather
    // than a duplicate: `DeckBoards` is a type and `frontFace` is a value, so they are two
    // statements, and this list is a list of import STATEMENTS. `ManaPip`'s entry above notes
    // the same thing from the other side — it takes a value and a type from ONE statement and
    // is therefore listed once. The single-statement spelling is not available here:
    // `verbatimModuleSyntax` is on in both tsconfigs and nothing in `src/` uses an inline
    // `type` specifier, so matching the house idiom costs one line in this list.
    {
      file: 'src/containers/ManaCurve/curve.ts',
      imports: ['../../state/deckGroups', '../../state/deckGroups'],
    },
    // c4-9's colour distribution — the mana curve's sibling in the analysis row, and the panel
    // with the LONGEST import list of the two by a distance. Where `ManaCurve` reached for no
    // cache at all, this one subscribes to the whole card map: `cmc` rides on `CardSummary` and
    // a pip count does not, so 87.75% of faced cards carry a blank top-level `mana_cost` whose
    // real value only hydration supplies. `../../state/cards` is a VALUE import (`useCardStore`)
    // and it reads only — no `setState`, no slice of its own, no request: `App.tsx` owns the
    // sweep and this panel reads what it has already put there.
    //
    // `../../components/ManaCost/parse` is a TYPE-only import here (`ManaColour`, for the
    // both-directions coupling of `copy.ts`'s labels); the parser's VALUES are used one module
    // over, in `colours.ts`.
    {
      file: 'src/containers/ColourDistribution/ColourDistribution.tsx',
      imports: [
        '../../components/ManaCost/parse',
        '../../components/ManaPip/ManaPip',
        '../../components/Panel/Panel',
        '../../state/cards',
        '../../state/deckGroups',
        './ColourDistribution.css',
        './colours',
        './copy',
        'react',
      ],
    },
    // c4-9's copy module — the FIFTH in this tree, the eleventh in the app. `imports: []` for the
    // settled `TS2835` reason, and one this module earns twice over: it owns the six colour
    // NAMES, which Q9(iv) makes the only route by which a colour reaches a screen-reader user at
    // all (the legend's pip ships decorative). Their coupling to `ManaColour` in both directions
    // is asserted in `ColourDistribution.tsx`, which imports both halves.
    { file: 'src/containers/ColourDistribution/copy.ts', imports: [] },
    // c4-10's format check — and the SHORTEST import list of any container in the tree, which is
    // the entry's whole point. Every other panel in the epic takes `boards` and most reach the
    // card cache; this one takes **no prop at all**, reads its own slice, and imports neither
    // `../../state/cards`, `../../state/deckGroups` nor `../../state/inspection`. That absence is
    // the cleanest don't-break in the epic (AC 13) and it is why this panel is the first to escape
    // c4-6's no-re-drive window STRUCTURALLY rather than by luck of which field it needed.
    //
    // `../../api/schema` is a TYPE-only import (`FormatCheckRow`, for the both-directions
    // couplings of `copy.ts`'s two maps and the tone map). `../../components/Badge/tones` is also
    // type-only (`BadgeTone`) — the third coupling axis, which is what makes `Badge`'s runtime
    // clamp unreachable from this call site rather than merely unused.
    //
    // `../../state/formatCheck` is a VALUE import (`useFormatCheck`) and it READS only: the
    // request lives in that module, `App.tsx` decides when to make it, and this container reaches
    // the network nowhere — which is the ban `shell.test.ts`'s own posture block enforces below.
    {
      file: 'src/containers/FormatCheck/FormatCheck.tsx',
      imports: [
        '../../api/schema',
        '../../components/Badge/Badge',
        '../../components/Badge/tones',
        '../../components/Panel/Panel',
        '../../state/formatCheck',
        './FormatCheck.css',
        './copy',
      ],
    },
    // c4-10's copy module — the SIXTH in this tree, the twelfth in the app. `imports: []` for the
    // settled `TS2835` reason, and this one earns it in a way worth naming: `ui/tests` imports it
    // directly (`tests/format-check-source.test.ts`), so the import-freedom is not a convention
    // here but a load-bearing property that file asserts before it relies on it.
    { file: 'src/containers/FormatCheck/copy.ts', imports: [] },
    // c4-9's derivation — the SEVENTH application of the `react-refresh/only-export-components`
    // split. Two imports of the same parse module for the reason `curve.ts`'s entry spells out:
    // this list is a list of import STATEMENTS, and `verbatimModuleSyntax` makes the inline
    // `type` specifier unavailable, so a value import and a type import are two lines.
    //
    // `../ManaCurve/curve` is the cross-directory import c4-9 ruled IN rather than out, and the
    // asymmetry with `frontFaceCost.ts` above is deliberate: moving a whole module whose every
    // export is shared costs one `git mv`, while splitting ONE export out of `curve.ts` would
    // separate `isLand` from the three-land-policies argument its own docstring makes about it.
    // AC 10 asks for the function to be reused rather than forked, and this is that.
    {
      file: 'src/containers/ColourDistribution/colours.ts',
      imports: [
        '../../components/ManaCost/parse',
        '../../components/ManaCost/parse',
        '../../state/cards',
        '../../state/deckGroups',
        '../ManaCurve/curve',
        '../frontFaceCost',
      ],
    },
    // The one mirror of `resolve_face_images` (c4-6). It sits at the ROOT of this tree rather than
    // inside `FlipControl/` because TWO components need the answer — the control, to decide
    // whether to exist, and `CardTile`, to decide whether to render a second stacked `<img>` for
    // the back face — and `src/components/filled.ts`'s header states the rule for exactly that
    // case: "a helper shared by two components does not live inside one of them". `useCardArt.ts`
    // and `imageUrl.ts` are the two shipped precedents.
    { file: 'src/containers/imagedFaces.ts', imports: ['../state/cards'] },
    // c4-11's skip link — the first Tab stop in the document, and the epic's only purely
    // structural component. It is a CONTAINER rather than a primitive because it attaches
    // `onClick`, `onFocus` and `onBlur`, three handlers `src/components/`'s set-equality posture
    // bans outright. `ui/README.md:548` named c4-11 in the inheriting list before it was written.
    //
    // NOTE WHAT IS ABSENT, because it is the whole shape of the component: no `../../state/…` of
    // any kind. Whether this renders at all is `App.tsx`'s call off the ONE `surfaceOf` answer, so
    // there is no slice in scope for a later edit to re-derive presence from — `deck.ts:388-390`
    // warns by name against a third derivation, and an exhaustive import list is the strongest
    // available form of that warning. No `../../api/…` either: it reaches no network and reads no
    // wire shape.
    {
      file: 'src/containers/SkipLink/SkipLink.tsx',
      imports: ['../focusHome', './SkipLink.css', './copy', 'react'],
    },
    // c4-11's copy module — the FOURTH in this tree, the twelfth in the app. One string, and for
    // once nothing to rule: `DESIGN.md:418`, `EXPERIENCE.md:100` and `epics:506` all carry "Skip
    // past the deck grid" byte for byte. `imports: []` for `CardDetail/copy.ts`'s measured reason:
    // `tests/` is the `nodenext` project and `src/` the `bundler` one, so a `ui/tests` file may
    // import an app module only if that module has no relative imports of its own — and
    // `copy-rules.test.ts` imports this one to compare the string against the artefact.
    { file: 'src/containers/SkipLink/copy.ts', imports: [] },
    // c4-11's focus hand-off — the EIGHTH application of the
    // `react-refresh/only-export-components` split, and the second module promoted to this tree's
    // root for the shared-helper rule after `frontFaceCost.ts`. It has exactly two callers by
    // design: `CardDetail`'s unpin control (which shipped the four lines first, at c4-5) and the
    // skip link. AC 6 makes that a requirement — "exactly one focus home and one implementation of
    // it" — so a third copy of `tabIndex = -1` / focus / remove-on-blur is a defect rather than a
    // duplication.
    //
    // `imports: []`, and it is the strongest statement this list can make about the module: no
    // react, no store, no wire, no DOM library. It takes an `Element` and calls two DOM methods on
    // it. Everything about WHICH element is the caller's, which is why neither caller's lookup
    // lives here — `CardDetail` scopes to its own frame ref, and the skip link cannot scope to
    // anything because it is mounted outside all three landmarks.
    { file: 'src/containers/focusHome.ts', imports: [] },
    // The image-route path builder. `imports: []` is the strongest form of "this is a string,
    // from a string" — no react, no DOM, no store and, above all, no fetch. It is a module of
    // its own because `react-refresh/only-export-components` is an ESLint error and a component
    // file that also exports a helper breaks fast refresh; the split is what lets c4-5 and c4-6
    // extend ONE builder rather than each writing a second template string. Held to the same
    // posture as the components beside it, for the reason `tones.ts` and `parse.ts` are: a pure
    // module next to a component is exactly where behaviour arrives first, because nothing in
    // its own file looks like a component.
    { file: 'src/containers/CardTile/imageUrl.ts', imports: [] },
    // c5-7's connection pill — the FIRST container in this tree from Epic 5, and the first whose
    // reason to be here is the STATE it reads rather than the handlers it attaches: it subscribes
    // to two slices (`connection` from the system store, the deck's name from the deck store) and
    // takes focus, either of which alone bars it from `src/components/`. `:1946` above named c5-7
    // in this category by name, fifteen stories before it landed.
    //
    // BOTH state imports are SELECTOR hooks the modules export, never the stores' write side —
    // `useConnection` was added to `systemState.ts` by this story (Q5, closing dw:5430) precisely
    // so the pill subscribes to one FIELD instead of adding a second selector-less whole-store
    // subscription beside `App`'s. `../../state/socket` is a TYPE import (`ConnectionStatus`),
    // which is what keeps the WebSocket module's behaviour out of this file entirely.
    //
    // NOTE WHAT IS ABSENT: no `../../api/…` of any kind, in either form. The pill reads no wire
    // shape and makes no request — its "is the backend there" answer arrives through the store
    // that c5-6's loop writes, and the `/health` read that WOULD touch the network is c10-1's.
    {
      file: 'src/containers/ConnectionPill/ConnectionPill.tsx',
      imports: [
        '../../state/deck',
        '../../state/socket',
        '../../state/systemState',
        './ConnectionPill.css',
        './copy',
        'react',
      ],
    },
    // c5-7's copy module — the SEVENTH in this tree, and the first that AUTHORS its strings rather
    // than transcribing them: no artefact specified the pill's words at all (see the module's own
    // header). `imports: []` for `CardDetail/copy.ts`'s measured reason — `tests/` is the
    // `nodenext` project and `src/` the `bundler` one, so a `ui/tests` file may import an app
    // module only if that module has no relative imports of its own, and
    // `tests/connection-pill-copy.test.ts` imports this one to gate the strings against
    // EXPERIENCE.md's row.
    { file: 'src/containers/ConnectionPill/copy.ts', imports: [] },
    // c7-5's deck announcer — props-free like the pill it rides beside in App.tsx's
    // connectionPill slot, and a container for the pill's own reason: it subscribes to the deck
    // store (the refetch-settle counter and the two header counts, all primitive selectors) and
    // holds render-time announcement state. It renders ONE visually-hidden polite region —
    // UX-DR45's deck-refetch channel, the app's third — and no visible chrome at all, which is
    // why there is no stylesheet import: `.visually-hidden` is the shared utility and
    // `.deck-announcement` is an identity class the censuses name, not a styled one.
    //
    // ⚠️ `../../state/agentView` JOINED AT c7-6, AND IT IS THE ONE IMPORT WORTH ARGUING ABOUT.
    // UX-DR45's *"nothing announces from behind an open agent view"* needs one bit of overlay
    // state here, and the component's own header spent c7-5 declaring it deliberately did not
    // read any. What makes the addition safe rather than a widening is WHICH export it takes:
    // `useAgentViewIsOpen`, a boolean, and NOT `useOpenAgentView`, whose content object would
    // resubscribe this region to every push's items and title. The import list cannot see that
    // distinction — the announcer's docstring and `agentView.ts`'s selector pair carry it — so
    // it is written here for the reader who arrives at this line first.
    {
      file: 'src/containers/DeckAnnouncer/DeckAnnouncer.tsx',
      imports: ['../../state/agentView', '../../state/deck', './copy', 'react'],
    },
    // c7-5's copy module — `imports: []` for the settled TS2835 reason: `ui/tests` is the
    // `nodenext` project and `src/` the `bundler` one, and
    // tests/deck-announcement-copy.test.ts imports this module directly to gate the template
    // against the artefacts, so the import-freedom is load-bearing rather than conventional.
    { file: 'src/containers/DeckAnnouncer/copy.ts', imports: [] },
  ]

  // A WALK rather than a regex (review 2026-08-04): the first spelling was a `//`-to-newline
  // regex, and the double-faced-name idiom this very component family traffics in — a string
  // holding `'X // Y'` — would have deleted the rest of the line, code included, before any ban
  // below ran. String and template contents are KEPT (the import rules read specifiers out of
  // them); only comments are dropped. Same walker, same declared residue, as posture.test.ts's.
  const withoutComments = (source: string): string => {
    let out = ''
    let index = 0
    while (index < source.length) {
      const pair = source.slice(index, index + 2)
      if (pair === '//') {
        while (index < source.length && source[index] !== '\n') index += 1
        continue
      }
      if (pair === '/*') {
        const close = source.indexOf('*/', index + 2)
        index = close === -1 ? source.length : close + 2
        continue
      }
      const char = source[index]
      if (char === '"' || char === "'" || char === '`') {
        out += char
        index += 1
        while (index < source.length && source[index] !== char) {
          if (source[index] === '\\') {
            out += source[index]
            index += 1
          }
          if (index < source.length) {
            out += source[index]
            index += 1
          }
        }
        if (index < source.length) {
          out += char
          index += 1
        }
        continue
      }
      out += char
      index += 1
    }
    return out
  }

  const containerFilesOnDisk = (): string[] =>
    execFileSync('git', ['ls-files', 'src/containers/*.ts', 'src/containers/*.tsx'], {
      cwd: uiRoot,
      encoding: 'utf8',
    })
      .split('\n')
      .filter(Boolean)

  // The comparison the coverage guard AND its firing half both run (review 2026-08-04 — the
  // firing half's first spelling asserted that appending to an array changes it, which exercised
  // nothing). One function, two feeds: the real `git ls-files` in the guard, the same list plus
  // a planted module in the probe.
  const coversExactly = (onDisk: string[]): boolean => {
    const shipped = onDisk.filter((f) => !/\.test\.tsx?$/.test(f)).sort()
    const listed = CONTAINERS.map((c) => c.file).sort()
    return shipped.length === listed.length && shipped.every((f, i) => f === listed[i])
  }

  it('is reading every container module (non-vacuity)', () => {
    // 3 at c4-4, which created the category; 6 at c4-5, which added the detail panel, its copy
    // module and the shared art hook; 7 since that story's review added the deck-transition
    // memory (2026-08-05); 10 at c4-6, which adds the flip control, its copy module and the one
    // mirror of `resolve_face_images`. The number is pinned rather than derived so that a new
    // container is a DECISION with a diff — the same reason the token inventory is pinned — and
    // the coverage guard below is what makes forgetting to move it impossible rather than merely
    // discouraged.
    // 13 at c4-7, which adds the deck list, its copy module and the front-face resolution.
    // 16 at c4-8, which adds the mana curve, its copy module and its derivation. The panel's
    // PAIR-ROW wrapper is NOT here: `AnalysisRow` holds no state, calls no hook and reads no
    // store, so it is a primitive and lands in `PRIMITIVES` above (c4-4 Q1's category rule
    // applied in the direction it is usually applied against).
    // 19 at c4-9, which adds the colour distribution, its copy module and its derivation. It
    // also MOVES `frontFaceCost.ts` up a level rather than adding a fourth — the count is +3
    // either way, and the coverage guard below is what makes the rename impossible to forget.
    // 21 at c4-10, which adds the format check and its copy module — and only those TWO. It ships
    // no derivation module of its own, because there is nothing to derive: the backend already
    // decided every verdict and `deck_validator.py`'s own guard declares that a rule re-written in
    // TypeScript is invisible to it, so a `rows.ts` here would be the exact hole that guard names.
    // 24 at c4-11, which adds the skip link, its copy module and the focus hand-off. The third is
    // an EXTRACTION rather than a new capability — `CardDetail` shipped those four lines at c4-5
    // and this story gave them a second caller — so the count moves by three while the app grows
    // by one component.
    // 25 at c4-12, and it is the smallest move in the epic: ONE module, a `copy.ts` holding a
    // single sentence. The story renders that sentence from an EXISTING container (`CardGrid`, at
    // the invitation its own header left) and puts its one predicate in an EXISTING state module
    // (`deckIsEmpty`, beside `DeckBoards`), so the tree grows by a copy owner and nothing else —
    // which is the shape a story that adds "one sentence and one conditional" should have.
    // 27 at c5-7, the first Epic 5 story to add a component at all: the connection pill and its
    // copy module. No derivation module — there is nothing to derive. The pill maps a status to a
    // word and a class, and both maps are `Record`s over `ConnectionStatus` small enough to live
    // beside the things they feed (the words in `copy.ts` because they are copy; the dot classes
    // in the component because they are CSS identity). A third module here would be the same
    // decision written twice.
    // 29 at c6-5, which adds the agent view shell and its copy module.
    // 31 at c6-6, which adds the suggestions view's BODY and its copy module — and only those
    // two. The shell it rides inside already existed, the store it reads already existed, and
    // the story's other half (the socket dispatch, the builder, the replace effect) all landed
    // in modules this list already covers. A story that "wires a push to a view" growing the
    // container tree by exactly one component and its words is the shape it should have.
    // 34 at c6-8, which adds the agent-views nav, its copy module and its time formatter. The
    // third is an extraction forced by a LINT RULE rather than by a concept — see its entry —
    // and it is worth the count moving by three rather than hiding a second export inside the
    // component file. The store extension the story needed (per-kind retention, unread flags,
    // the pill vocabulary) landed in `src/state/agentView.ts`, a module this list does not cover
    // and does not need to; the header slot it fills was cut at c2-6.
    // 36 at c7-5, which adds the deck announcer and its copy module — the refetch announcement
    // UX-DR45 licensed and the App live-region censuses moved from two to three for.
    // 37 at 16.1, which adds the swaps view and NOTHING else — no copy module of its own (the
    // empty-push template is shared from `SuggestionsView/copy.ts` by that template's own
    // kind-generic design, and the out/in label words are owned by the component itself, which
    // joins COPY_MODULES on the DeckBadges precedent) and no derivation module. A story that
    // gives a second push kind its view growing this tree by exactly one component is the shape
    // it should have.
    // 38 at 16.2, which adds the tier-list view and NOTHING else — the same one-component shape
    // as 16.1, for the same reasons: the empty-push template stays shared, every rendered word
    // is wire data (so no copy module and no COPY_MODULES entry), and no derivation module —
    // the empty-tier skip is a render-time filter, not a derivation anything else reads.
    expect(CONTAINERS).toHaveLength(38)
    for (const { file } of CONTAINERS) {
      expect(sourceOf(file).length, `${file} is empty or missing`).toBeGreaterThan(200)
    }
  })

  it('covers every container module on disk — the list cannot silently fall behind', () => {
    // THE COVERAGE GUARD THIS CATEGORY SHIPS WITH, IN THE SAME COMMIT THAT CREATES IT (AC 1).
    // An uncovered directory is how the next fifteen component stories would escape every gate
    // in this repo at once — c4-5, c4-6, c4-7, c4-10, c4-11, c5-7, c6-5…c6-8 and c9-1…c9-3 all
    // land here. Same authority as every other file walk in this suite: git, not readdir, so an
    // untracked module cannot pass vacuously either.
    const onDisk = containerFilesOnDisk()
    expect(coversExactly(onDisk)).toBe(true)

    // The `.test.` exemption is for TEST files, and that is checked rather than assumed (review
    // 2026-08-04): a runtime module named `hooks.test.ts` would otherwise ship from this tree
    // covered by no list and held to no posture — a module invisible through its filename.
    for (const file of onDisk.filter((f) => /\.test\.tsx?$/.test(f))) {
      expect(
        sourceOf(file),
        `${file} is exempt from CONTAINERS as a test file, but imports nothing from vitest`,
      ).toMatch(/from ['"]vitest['"]/)
    }
  })

  it.each(CONTAINERS)('$file imports exactly what it declares', ({ file, imports }) => {
    const source = withoutComments(sourceOf(file))
    const modules = [
      ...source.matchAll(/(?:import|export)\s+(?:[^'"]*?\bfrom\s+)?['"]([^'"]+)['"]/g),
    ].map((m) => m[1])
    expect(modules.sort()).toEqual(imports)

    // The two runtime routes around a static import are closed by name, exactly as they are for
    // the primitives: a dynamic `import()` of a store slice is still a door.
    expect(source).not.toMatch(/\b(?:require|import)\s*\(/)
  })

  it.each(CONTAINERS)('$file reaches no module outside the permitted roots', ({ imports }) => {
    // The POSITIVE half of the exhaustive list: even a correctly-declared import must resolve
    // into react, the primitives, the containers themselves, the state layer, or `src/api/` FOR
    // A TYPE. `zustand` and anything else is a category decision, not an import.
    //
    // ==== `src/api/` JOINED AT c4-5, AND IT IS A CATEGORY DECISION MADE IN THE OPEN =======
    // This list read "react, the primitives, the containers themselves, or the state layer",
    // with `src/api/` named as excluded. c4-5's detail panel is the first container that has to
    // NAME a wire shape — it renders a hydrated `Card`, and reads `card_faces[0]` because 100%
    // of the corpus's faced cards carry a blank top-level `oracle_text` — and the alternative to
    // importing the alias is re-declaring the shape, which `tests/wire-contract.test.ts` bans
    // outright and `src/api/schema.ts` exists to make unnecessary.
    //
    // The permission is exactly the one `posture.test.ts` already gives every PRIMITIVE — *"a
    // component may take a TYPE from anywhere and a VALUE from nowhere but its own tree"* — and
    // `states.ts` has taken `ErrorReason` from `../../api/schema` since c3-2 under it. What made
    // that safe there is that types are erased and values are behaviour; the same split is what
    // makes it safe here, and the test BELOW is what enforces the half this one cannot see. A
    // value import of `src/api/client.ts` from a container would be a second network door, so it
    // is banned by name rather than left to the `fetch(` scan, which would never see it.
    //
    // NORMALISED FIRST (review 2026-08-04): the regexes read the specifier's SPELLING, and
    // `'../../state/../api/client'` spells a permitted root while resolving outside every one of
    // them. `posix.normalize` collapses the traversal before the roots are read, so what is
    // tested is where the import GOES, not how it is written.
    const normalised = imports.map((specifier) => {
      if (!specifier.startsWith('.')) return specifier
      const collapsed = posix.normalize(specifier)
      // `normalize` strips a leading `./`; put it back so the roots below read unchanged.
      return collapsed.startsWith('.') ? collapsed : `./${collapsed}`
    })
    const outside = normalised.filter(
      (specifier) =>
        specifier !== 'react' &&
        !specifier.endsWith('.css') &&
        !/^\.\.\/\.\.\/(?:components|state|api)\//.test(specifier) &&
        !/^\.\.?\/[A-Za-z]/.test(specifier),
    )
    expect(outside).toEqual([])
  })

  // ONE regex, used by the guard AND by its firing-half probe below. Extracted at review
  // 2026-08-05: the probe originally re-declared this pattern inline, so a "fix" to the guard's
  // copy would have left the probe green against its private one — the exact vacuous-negative-
  // control failure this suite's own history records twice. `matchAll` species-clones the regex,
  // so sharing one `/g` object between call sites is safe.
  const TYPE_ONLY_IMPORT = /\bimport\s+(type\s+)?[^'"]*?\bfrom\s+['"]([^'"]+)['"]/g

  /**
   * Whether a specifier reaches `src/api/`, AT ANY DEPTH — shared by the guard and by its probe
   * for `TYPE_ONLY_IMPORT`'s reason: a probe matching a private copy proves nothing.
   */
  const REACHES_API = (specifier: string) => /(^|\/)(?:\.\.\/)+api\//.test(`/${specifier}`)

  it.each(CONTAINERS)('$file takes a wire shape as a TYPE and never as a value', ({ file }) => {
    // THE OTHER HALF OF THE c4-5 WIDENING, and the half that carries the weight. The roots check
    // above reads SPECIFIERS, so it cannot tell `import type { Card }` from
    // `import { readCard }` — and one of those is a second door to the network in a codebase
    // whose whole posture is that there is exactly one (`posture.test.ts:339`).
    //
    // Keyed on the FORM rather than on the module, so `src/api/client.ts`, `src/api/types` and
    // an `src/api/` module nobody has written yet are all covered by the same line: any import
    // from that root must be `import type`. That is the identical rule `posture.test.ts` applies
    // to the primitives, restated for the category that did not have it.
    //
    // The INLINE-TYPE form — a `type` keyword inside the braces — is DELIBERATELY not accepted:
    // `verbatimModuleSyntax` is on, so that spelling still emits the import and still RUNS the
    // module. `posture.test.ts` makes the same distinction for the same measured reason.
    // DEPTH-INDEPENDENT, AND THAT IS A c4-9 CORRECTION RATHER THAN A TIDY-UP. This filter read
    // `/(^|\/)\.\.\/\.\.\/api\//` — exactly TWO levels up — which was true of every container
    // while every container lived one directory deep. c4-9 promoted `frontFaceCost.ts` to
    // `src/containers/`, where the same import is written `'../api/schema'`, and the old pattern
    // stops matching it: the module would have gone on importing a wire shape with this guard
    // silently no longer looking. A guard that quietly narrows when a file MOVES is the same
    // coverage-that-reads-as-coverage failure this epic keeps finding, so the pattern now counts
    // one-or-more `../` segments and covers every depth this tree can have.
    const source = withoutComments(sourceOf(file))
    const apiImports = [...source.matchAll(TYPE_ONLY_IMPORT)].filter(([, , specifier]) =>
      REACHES_API(specifier),
    )

    for (const [whole, typeOnly, specifier] of apiImports) {
      expect(
        typeOnly,
        `${file} imports ${specifier} as a VALUE: ${whole.trim()}. A container may take a wire ` +
          `SHAPE from src/api/ (types are erased); it may not take behaviour, because ` +
          `src/api/client.ts is the one door to the network and importing it here would open a ` +
          `second one. Use \`import type\` — and not \`import { type X }\`, which still runs ` +
          `the module under verbatimModuleSyntax.`,
      ).toBeDefined()
    }
  })

  it('would catch a value import from src/api/ — the firing half of the type-only rule', () => {
    // Fed inline rather than by breaking a real file, so the proof survives the repair. Three
    // spellings: the plain value import, the inline-type form that still runs the module, and
    // the one that is legitimately fine. AGAINST THE GUARD'S OWN REGEX (`TYPE_ONLY_IMPORT`,
    // shared above) — a probe matching a private copy proves nothing about the guard.
    const typeOnlyOf = (line: string) => [...line.matchAll(TYPE_ONLY_IMPORT)].map((m) => m[1])

    //
    // The inline-type probe names `Widget`, not a real schema key, and that is not cosmetic:
    // `tests/wire-contract.test.ts` scans every tracked source — this file included — for a
    // declaration whose name matches a `components.schemas` key — and to a regex, an inline-type
    // import of a real shape is indistinguishable from declaring one. Naming a real shape here,
    // even in this comment, fails that guard from inside a probe: measured, not predicted.
    expect(typeOnlyOf("import { readCard } from '../../api/client'")).toEqual([undefined])
    expect(typeOnlyOf("import { type Widget } from '../../api/schema'")).toEqual([undefined])
    expect(typeOnlyOf("import type { Widget } from '../../api/schema'")).toEqual(['type '])

    // AND THE FILTER REACHES BOTH DEPTHS (c4-9). The guard's own selection step is where it
    // silently narrowed: with `frontFaceCost.ts` promoted to `src/containers/`, its wire import
    // is written `'../api/schema'`, which the previous two-levels-exactly pattern did not match
    // at all — so the rule above would have run over an EMPTY list and passed by looking at
    // nothing. Both spellings, and one that must NOT match.
    expect(REACHES_API('../../api/schema')).toBe(true)
    expect(REACHES_API('../api/schema')).toBe(true)
    expect(REACHES_API('../../state/cards')).toBe(false)
    // …and it is genuinely reaching a real container: the promoted module is in the list and
    // spells its import the shorter way, which is the case that made this change necessary.
    expect(CONTAINERS.find((c) => c.file === 'src/containers/frontFaceCost.ts')?.imports).toContain(
      '../api/schema',
    )
  })

  it('keeps oracle paragraph breaks beside the clamp — pre-line in the scroller rule', () => {
    // `oracle_text` separates abilities with `\n` and the panel renders the wire value VERBATIM
    // into one element, so the clamp's own rule must declare `white-space: pre-line` — without
    // it every multi-ability card in the corpus reads as one run-together sentence (found at
    // review 2026-08-05; jsdom evaluates no CSS, so this is a SOURCE claim, asserted against
    // the same block as the clamp so neither declaration moves without the other).
    const oracle = sourceOf('src/containers/CardDetail/CardDetailChrome.css').match(
      /\.card-detail-oracle\s*\{[^}]*\}/,
    )?.[0]
    expect(oracle).toBeDefined()
    expect(oracle).toMatch(/max-height:\s*21em/)
    expect(oracle).toMatch(/white-space:\s*pre-line/)
  })

  it('binds each connection-dot class to ITS status token, not merely to a status token', () => {
    // ⚠️ FOUND BY A FIRING PROOF, NOT BY DESIGN (c5-7, AC 19, probe P15). Every other assertion
    // about the pill's dot reads the DOM, and jsdom evaluates no stylesheet — so
    // `ConnectionPill.test.tsx` proves that `'down'` renders `is-down` and stops there. Pointing
    // `.is-down` at `--caution` in the stylesheet passed the ENTIRE suite green: the one component
    // in the app whose whole job is to signal by colour could ship the wrong colour, on the state
    // that matters most, with 1,866 tests agreeing.
    //
    // The binding is therefore read out of the source, three ways round, because the failure this
    // catches is a SWAP and a swap satisfies any per-class check that only asks "is it a status
    // token". UX-DR29 assigns them by name: positive live, caution reconnecting, negative gone.
    const pillCss = sourceOf('src/containers/ConnectionPill/ConnectionPill.css')
    for (const [modifier, token] of [
      ['is-live', '--positive'],
      ['is-reconnecting', '--caution'],
      ['is-down', '--negative'],
    ] as const) {
      const rule = new RegExp(`\\.connection-pill-dot\\.${modifier}\\s*\\{([^}]*)\\}`).exec(pillCss)
      expect(rule, `no rule found for .connection-pill-dot.${modifier}`).not.toBeNull()
      expect(
        rule![1],
        `.${modifier} does not fill from var(${token}) — UX-DR29 assigns the three status ` +
          `colours to the three states by name, and a swap here is invisible to every DOM test`,
      ).toMatch(new RegExp(`background:\\s*var\\(${token}\\)`))
    }
    // …and the dot spends NOTHING ELSE as a fill: a fourth rule pointing the dot at `--accent`
    // would satisfy all three assertions above and still be wrong (`DESIGN.md:366` reserves the
    // accent for live agent attention).
    const fills = [
      ...pillCss.matchAll(/\.connection-pill-dot[^{]*\{[^}]*background:\s*var\((--[a-z-]+)\)/g),
    ]
    expect(fills.map((m) => m[1]).sort()).toEqual(['--caution', '--negative', '--positive'])
  })

  it("keeps the deck name OUT of the micro/uppercase role the state word takes (c4-3's lesson, a third time)", () => {
    // THE SAME SHAPE AS THE DOT-BINDING GUARD ABOVE, closed by code review rather than a firing
    // proof (c5-7 review, 2026-08-08). `ConnectionPill.test.tsx`'s case-preservation test only
    // proves the deck name STRING is present in the DOM — jsdom never applies `text-transform`,
    // so nothing there can catch a regression that reattaches `--type-micro` (and its
    // `text-transform: uppercase` companion) to `.connection-pill-deck`. An uppercased
    // "SULTAI MIDRANGE" destroys the mixed-case name this pill exists to show — c4-3's lesson,
    // repeated at c4-10, repeated here (`DESIGN.md:479`'s amendment note).
    const pillCss = sourceOf('src/containers/ConnectionPill/ConnectionPill.css')

    // The STATE WORD keeps the micro role — the positive half of the split, so this guard proves
    // a deliberate split rather than a blanket "no uppercase anywhere" rule.
    const stateRule = /\.connection-pill-state\s*\{([^}]*)\}/.exec(pillCss)
    expect(stateRule, 'no rule found for .connection-pill-state').not.toBeNull()
    expect(stateRule![1]).toMatch(/font:\s*var\(--type-micro\)/)
    expect(stateRule![1]).toMatch(/text-transform:\s*uppercase/)

    // The DECK NAME (and its separator, which shares its rule) must NOT take the micro role.
    const deckRule = /\.connection-pill-separator,\s*\.connection-pill-deck\s*\{([^}]*)\}/.exec(
      pillCss,
    )
    expect(deckRule, 'no rule found for .connection-pill-deck').not.toBeNull()
    expect(deckRule![1]).not.toMatch(/--type-micro/)
    expect(deckRule![1]).not.toMatch(/text-transform/)
  })

  it.each(CONTAINERS)('$file makes no request and imports no state library', ({ file }) => {
    const source = withoutComments(sourceOf(file))

    // THE ONE-DOOR RULE, SCOPED. `posture.test.ts` already asserts the door list exhaustively
    // over all of `src/`, and this story leaves that list reading `['src/api/client.ts']` with
    // NO EDIT — an `<img src>` is a request the BROWSER makes, not one the app makes, and no
    // code in `ui/src` ever holds the bytes. Asserted here as well because the containers are
    // the category most likely to reach for one, and a rule stated only in prose is not one.
    expect(source).not.toMatch(/\b(?:fetch|XMLHttpRequest|EventSource|WebSocket)\s*\(/)
    expect(source).not.toMatch(/navigator\.sendBeacon/)
    // AD-12: no second state library, and no reaching past `src/state/` to the one we have.
    expect(source).not.toMatch(/from\s+['"]zustand['"]/)
    // AD-12's other half, and `store-writes.test.ts`'s: nothing outside a slice's own module
    // writes it. A container subscribes; it does not set.
    expect(source).not.toMatch(/\.setState\b/)
  })

  it('ships the blessed track and the token gap — the POSITIVE half of AC 12', () => {
    // Added by review 2026-08-04: everything else in this suite only BANS bad grid forms (the
    // bare `1fr`, the content-floored minmax), so a drift from the blessed track — or a gap
    // quietly moved off `--space-panel-gap` — passed every gate while the component test's
    // header claimed otherwise. These are source claims on the shipped stylesheet; that the
    // grid REFLOWS at real widths stays Task 7's, and jsdom cannot carry it.
    const grid = sourceOf('src/containers/CardGrid/CardGrid.css')
    expect(grid).toMatch(/grid-template-columns:\s*repeat\(auto-fill,\s*minmax\(176px,\s*1fr\)\)/)
    expect(grid).toMatch(/gap:\s*var\(--space-panel-gap\)/)
  })

  it('keeps the empty-deck line calm — the NARROW claim, in place of CALM_STYLESHEETS (c4-12)', () => {
    // Q16'S RULING, MADE AS A PIN RATHER THAN AS A COMMENT. `CALM_STYLESHEETS` in
    // token-usage.test.ts is the obvious home for UX-DR30's "no error styling", but it is keyed on
    // a whole FILE — and this file draws the card grid's arrangement, so joining it would assert
    // calmness over every rule in here and every rule a later story adds. That is a claim about
    // the grid, not about the one line UX-DR30 speaks to. So the claim is made narrowly, here,
    // against the rule block itself.
    //
    // ⚠️ WHAT IT CANNOT SEE, DECLARED: it reads ONE stylesheet's ONE block. A colour, border or
    // background reaching `.card-grid-empty` from another file, an inline style, or a token
    // redefined under a different theme are all invisible to it. Nothing does any of those today
    // (the element is a bare `<p>` with one class, and `token-usage.test.ts` scans every tracked
    // `.css` for declarations), and this comment is the record of the gap rather than a claim
    // that there is none.
    const emptyLineCss = sourceOf('src/containers/CardGrid/CardGrid.css')
    // Comments are stripped BEFORE the block is cut: a `}` inside a comment would truncate the
    // `[^}]*` capture and every declaration after it would escape both pins below — the first of
    // three mechanical evasion holes closed at code review 2026-08-07 (the other two: property
    // case, and `var()` fallback literals).
    const block =
      /\.card-grid-empty\s*\{([^}]*)\}/.exec(emptyLineCss.replace(/\/\*[\s\S]*?\*\//g, ''))?.[1] ??
      ''

    // NON-VACUITY FIRST: a rename or a deleted rule yields `''`, over which every assertion below
    // would pass while asserting nothing — the epic's coverage-that-reads-as-coverage shape, in
    // the exact place it has landed six stories running.
    expect(block.length, '.card-grid-empty is missing from CardGrid.css').toBeGreaterThan(30)

    // Lower-cased because CSS property names are case-insensitive: `Background:` is a live
    // declaration the browser honours, and an `[a-z-]`-only capture would simply not see it —
    // the exactly-three pin would stay green while a fourth property shipped.
    const declared = [...block.matchAll(/^\s*([a-zA-Z-]+)\s*:/gm)]
      .map((m) => m[1].toLowerCase())
      .sort()
    // EXACTLY these three, both directions. An extra `background`, `border`, `padding`,
    // `min-height` or `text-align` is a treatment DESIGN.md does not specify and this is where it
    // surfaces; a missing `margin` is the UA `<p>` margin returning and breaking the panel inset.
    expect(declared).toEqual(['color', 'font', 'margin'])

    // The two tokens DESIGN.md's `components.empty-deck-line` names, and NO others — so a
    // semantic colour (`--negative`, `--caution`) arriving here fails even though it would satisfy
    // the property list above.
    const spent = [...block.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]).sort()
    expect(spent).toEqual(['--text-secondary', '--type-body'])

    // And no `var(--token, fallback)`: the capture above reads only the token NAME, so
    // `var(--text-secondary, red)` would satisfy the exact-token pin while shipping a literal
    // colour through its fallback arm. The scale's tokens carry their own values; a fallback
    // here could only ever be an invented one.
    expect(block).not.toMatch(/var\(\s*--[\w-]+\s*,/)

    // `--type-body` is one of the four roles that need NO companion declaration (display, label
    // and micro carry tracking or transform; body does not) — so the bare `font:` shorthand here
    // is correct rather than an unpaired-role defect, and `token-usage.test.ts`'s companion guard
    // is what would say otherwise. Asserted so the reason is pinned, not remembered.
    expect(block).not.toMatch(/letter-spacing|text-transform|font-variant-numeric/)
  })

  it('is a category that is actually USED — otherwise it is theatre', () => {
    // The non-vacuity half of the ruling itself. If no container ever held a hook, a ref or a
    // handler, this whole directory would be an unjustified second home for presentation-only
    // components and the primitives' posture should simply have been obeyed. `CardTile` is the
    // proof that the category was forced rather than chosen.
    const tile = withoutComments(sourceOf('src/containers/CardTile/CardTile.tsx'))
    expect(tile).toMatch(/\buse[A-Z]\w*\s*\(/)
    expect(tile).toMatch(/\bref\s*=/)
    expect(tile).toMatch(/\bon[A-Z]\w*\s*=/)
  })

  it('would catch a container that never joined the list (probe a)', () => {
    // The firing half of the coverage guard, fed through the SAME comparison the guard runs
    // (review 2026-08-04 — the first spelling asserted that appending to an array changes it,
    // which exercised neither `git ls-files` nor the comparison). Same real `ls-files` output,
    // one planted module: the guard's own function must refuse it — and refuse a `.test.ts`
    // spelling being used to smuggle a runtime module past the exemption is checked in the
    // guard itself.
    const real = containerFilesOnDisk()
    expect(coversExactly(real)).toBe(true)
    expect(coversExactly([...real, 'src/containers/Sneaky/Sneaky.tsx'])).toBe(false)
    // …and the exemption is not a hole in THIS comparison for a listed module gone missing:
    expect(coversExactly(real.filter((f) => f !== 'src/containers/CardTile/CardTile.tsx'))).toBe(
      false,
    )
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
    // c5-7's connection pill is fixed and pinned to a corner — SHIPPED, and silent here; a
    // docked bar spans one axis;
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
    // for. The first story to ship one would inherit a gate it could not pass by writing the
    // right thing — the worst kind, because the fix looks like removing the documentation.
    // (c2-7's StatChip was named here as the likely candidate; it shipped no fractional
    // literal — its 17px comes from a role token, not from geometry — so the invented member
    // stays invented, which is the whole reason it was worth inventing.)
    const css = `/* 17.5px — DESIGN.md says the chip is 17.5px tall. */\n.chip { height: 17.5px; }`
    expect(pxLiteralsIn(css)).toEqual(['17.5px'])
    expect(documented(commentsIn(css), '17.5px')).toBe(true)

    // And the boundary still does its round-1 job: a later `52px` must NOT ride the `52px`
    // inside an existing "452px — DESIGN.md" citation.
    const shared = `/* 452px — DESIGN.md, the right column. */`
    expect(documented(commentsIn(shared), '452px')).toBe(true)
    expect(documented(commentsIn(shared), '52px')).toBe(false)
  })

  it('does not read a px length inside a CSS STRING as geometry (Greptile, PR #23)', () => {
    // `content: "16px"` is text the user READS — a tooltip, an axis label in c4-8 —
    // and there is nothing in DESIGN.md to cite for it. Scanning it as a literal fails the
    // gate on a stylesheet that is entirely correct, which is the false positive this file's
    // doctrine calls worse than the defect. Measured before the fix: it returned ['16px'].
    expect(pxLiteralsIn('.tip::after { content: "16px"; }')).toEqual([])
    expect(pxLiteralsIn(".tip::after { content: '452px'; }")).toEqual([])
    // And a REAL declaration beside a string is still found — blanking must not blind it.
    expect(pxLiteralsIn('.tip { width: 480px; } .tip::after { content: "16px"; }')).toEqual([
      '480px',
    ])
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

  it('scans comments and strings in ONE pass, so neither can hide inside the other', () => {
    // Both two-pass orderings were measured and both lose (Greptile, PR #23). These are the
    // two inputs that killed them; they must now BOTH survive, which no ordering achieves.
    //
    // Strip-then-blank swallowed the middle rule entirely — and since blocksIn reads the same
    // source, it vanished from every guard in this file, not just the literal scan.
    const openerInString =
      '.marker::after { content: "/*"; }\n.panel { width: 480px; }\n/* 300px — DESIGN.md */\n.detail { height: 300px; }'
    expect(pxLiteralsIn(openerInString)).toEqual(['480px', '300px'])
    expect(blocksIn('inline', openerInString).map((b) => b.selector)).toEqual([
      '.marker::after',
      '.panel',
      '.detail',
    ])

    // Blank-then-strip left this comment unstripped, leaking its prose into the "code": the
    // apostrophe in `it's` pairs with the declaration's quote and blanks the `*/` between.
    const apostropheBesideCode = "/* it's */ .a { content: 'x'; width: 480px; }"
    expect(stripComments(apostropheBesideCode)).not.toContain('it')
    expect(blocksIn('inline', apostropheBesideCode).map((b) => b.selector)).toEqual(['.a'])
    expect(commentsIn(apostropheBesideCode)).toEqual(["/* it's */"])
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
    expect(stripComments(`content: 'a\\'b }';`)).not.toContain('}')
    expect(stripComments(`content: "a\\"b }";`)).not.toContain('}')
    // And the plain forms still blank, or the repair would have broken the round-1 case.
    expect(stripComments(`content: '}';`)).not.toContain('}')
    expect(stripComments(`content: "}";`)).not.toContain('}')
    // A real brace OUTSIDE a string must survive — blanking is not deleting.
    expect(stripComments(`.a { color: red; }`)).toContain('}')
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
