/**
 * The keyboard floor, app-wide (story c4-11, AC 12, AC 16, AC 17, AC 20, UX-DR41, UX-DR46,
 * UX-DR47).
 *
 * ================= WHAT THIS FILE ADDS THAT NOTHING ELSE CHECKS ========================
 *
 * Five focusable elements shipped across five stories, and each one's own test file asserts its
 * own ring. That is exactly the shape this epic's reviews keep catching: **every element is
 * covered and the SET is not.** A sixth element added by a later story with no `:focus-visible`
 * rule at all breaks no existing test — its component's file does not know it should have one,
 * and no file looks across the whole app.
 *
 * So the rule here is the one with teeth, and AC 16 states it in exactly these words: every
 * focusable element carries **one of exactly two** treatments, **and none carries neither**.
 *
 * ================= THE SET IS DERIVED, NEVER LISTED ===================================
 *
 * A list would be a list of the elements someone thought of, which is the failure this guard
 * exists to prevent — and it is the failure the C3 retro's F1 count made in a neighbouring
 * dimension (six story keys counted, a seventh never looked for; c4-11 Q14). So the focusable set
 * comes out of the SOURCE: every `<button>`, every `<a>` and every element carrying a `tabIndex`
 * in every shipped `.tsx`, matched to its class, matched to a `:focus-visible` rule.
 *
 * The non-vacuity anchors below are what make that claim checkable. A guard that derived an EMPTY
 * set would pass every assertion in this file by looking at nothing.
 *
 * ================= WHAT IT CANNOT SEE, DECLARED =======================================
 *
 * **The rendered box.** jsdom has no layout, so `min-width: 24px` here is a claim about a
 * DECLARATION. Whether the painted hit box is really ≥24×24 — and whether the ring is really
 * visible against a light card face — is the eye-check's, and it is stated rather than implied.
 * The jsdom half proves the TAG; the eye-check proves the BOX.
 *
 * **Specificity and the cascade.** This file asks whether a rule EXISTS for a class, not whether
 * something later outranks it. `CardTile.css:54-75` records a real instance of that trap being
 * found by eye; a selector-weight model is a bigger instrument than this guard needs and would
 * be the wrong place to put it.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = join(dirname(fileURLToPath(import.meta.url)), '..')

/**
 * `git ls-files`, for the reason every registry guard in this repo uses it — and with the limit
 * this epic learned the hard way DECLARED rather than claimed away: **an un-`git add`ed file is
 * invisible here and passes vacuously.** That was a false green at c4-7 and an untracked-bundle
 * High at c4-3 and again at c4-7. This guard cannot close it; `deferred-work.md:3938-3946` owns
 * it, and the mitigation is the workflow step (`git add` before believing a run), not this line.
 */
const tracked = (pattern: string) =>
  execFileSync('git', ['ls-files', pattern], { cwd: uiRoot, encoding: 'utf8' })
    .split('\n')
    .filter(Boolean)
    .filter((f) => f.startsWith('src/'))

const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

const shippedModules = tracked('*.tsx').filter((f) => !f.includes('.test.'))
const shippedStylesheets = tracked('*.css')

/**
 * Whether the character at `index` is escaped by a backslash — counted, not peeked. A single
 * `source[i - 1] !== '\\'` check misreads a string ENDING in an escaped backslash (`'…\\'`): the
 * closing quote looks escaped, quote state never exits, and every scanner downstream goes blind
 * for the rest of the file (code review 2026-08-07).
 */
const isEscaped = (source: string, index: number): boolean => {
  let backslashes = 0
  for (let i = index - 1; i >= 0 && source[i] === '\\'; i -= 1) backslashes += 1
  return backslashes % 2 === 1
}

/**
 * Comments stripped, so a `<button>` discussed in a docstring is not counted as one shipped.
 *
 * ⚠️ THIS FILE'S THIRD SILENT-MANGLING REPAIR, and the first two are kept on record because the
 * class keeps recurring. (1) Stripping the JSX form `{/* … *\/}` with a backtracking regex
 * swallowed 4,700 characters of `FlipControl.tsx` — 10,257 bytes in, 611 out — excusing the
 * component from every rule in this file. (2) A naive `<button[^>]*>` truncated at the `>` inside
 * `onClick={() => …}` (see {@link openingTagAt}). (3) The first shipped form of THIS function was
 * a pair of regexes whose line-comment stage protected only `://` — so any string literal
 * containing `' // '` (`frontFaceCost.ts:67`'s `FACE_SEPARATOR`, this repo's normal split-card
 * data) was truncated mid-string, leaving a dangling quote that silently poisoned every stateful
 * scan after it (code review 2026-08-07). So the stripper is now STATEFUL: it tracks quote state
 * (with {@link isEscaped}) and removes comments only OUTSIDE strings.
 *
 * KNOWN LIMIT, declared: regex LITERALS are not modelled. A shipped regex containing a quote
 * character would open phantom quote state here — none does today, and the by-file non-vacuity
 * anchor is what turns that from silent to loud if one ever appears.
 */
const withoutComments = (source: string): string => {
  let out = ''
  let i = 0
  let quote: string | null = null
  while (i < source.length) {
    const ch = source[i]
    if (quote !== null) {
      out += ch
      if (ch === quote && !isEscaped(source, i)) quote = null
      i += 1
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      quote = ch
      out += ch
      i += 1
      continue
    }
    if (ch === '/' && source[i + 1] === '*') {
      const end = source.indexOf('*/', i + 2)
      i = end === -1 ? source.length : end + 2
      continue
    }
    if (ch === '/' && source[i + 1] === '/') {
      const end = source.indexOf('\n', i)
      i = end === -1 ? source.length : end
      continue
    }
    out += ch
    i += 1
  }
  return out
}

interface Focusable {
  readonly file: string
  readonly tag: string
  /** The element's own class list, as written. Empty when it carries none. */
  readonly classes: readonly string[]
  /** Whether the opening tag declares a `tabIndex`. */
  readonly hasTabIndex: boolean
  /** The literal `tabIndex` value as written, for the positive-tabindex ban. */
  readonly tabIndexValue: string | null
}

/**
 * The attribute text of the opening tag starting at `start`, or `null` if it never closes.
 *
 * ⚠️ A NAIVE `<button[^>]*>` DOES NOT WORK HERE, and it fails SILENTLY — which is worth recording
 * because the first draft of this guard shipped it and the non-vacuity anchors caught it. An
 * arrow function in a handler (`onClick={() => …}`) contains a `>`, so the match stops mid-tag:
 * `CardTile`'s button came back with an EMPTY class list and `FlipControl`'s was not found at
 * all. A guard that mis-parses a component simply excuses it from every rule below.
 *
 * So the scan tracks brace depth and quoting, and returns at the first `>` at depth zero. That is
 * enough for JSX (this repo's is Prettier-formatted) without pulling in a parser.
 */
const openingTagAt = (source: string, start: number): string | null => {
  let depth = 0
  let quote: string | null = null
  for (let i = start; i < source.length; i += 1) {
    const ch = source[i]
    if (quote !== null) {
      // `isEscaped` COUNTS backslashes: `'…\\'` ends its string, and a `!== '\\'` peek would say
      // it does not — leaving the scanner in quote state for the rest of the file.
      if (ch === quote && !isEscaped(source, i)) quote = null
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') quote = ch
    else if (ch === '{') depth += 1
    else if (ch === '}') depth -= 1
    else if (ch === '>' && depth === 0) return source.slice(start, i)
  }
  return null
}

/**
 * Every class name reachable from a `className` attribute, string-literal or expression.
 *
 * `CardTile` writes `className={live ? 'card-shape card-tile is-live' : 'card-shape card-tile'}`,
 * so reading only the `className="…"` form misses it entirely. Every quoted run inside the
 * expression is collected — a superset, deliberately: for the coverage question below, "could
 * this element ever carry this class" is the right question, and a conditional class that
 * sometimes applies still needs a ring.
 */
const classesIn = (attrs: string): string[] => {
  const at = /className\s*=\s*/.exec(attrs)
  if (at === null) return []
  const rest = attrs.slice(at.index + at[0].length)
  const value = rest.startsWith('{')
    ? (openingBraceRun(rest) ?? '')
    : (/^"([^"]*)"/.exec(rest)?.[1] ?? '')
  const quoted = [...value.matchAll(/['"`]([^'"`]*)['"`]/g)].map((m) => m[1])
  const raw = quoted.length > 0 ? quoted.join(' ') : value
  return raw.split(/\s+/).filter(Boolean)
}

/** The text inside a leading `{…}`, brace-balanced. */
const openingBraceRun = (rest: string): string | null => {
  let depth = 0
  for (let i = 0; i < rest.length; i += 1) {
    if (rest[i] === '{') depth += 1
    else if (rest[i] === '}') {
      depth -= 1
      if (depth === 0) return rest.slice(1, i)
    }
  }
  return null
}

/**
 * Every focusable element the app ships, read out of the JSX.
 *
 * Opening tags only, and the three kinds that can take focus in this codebase: `<button>`, `<a>`
 * (which in this app always carries an `href`) and anything declaring a `tabIndex`. There is no
 * fourth kind, because `<input>`, `<select>` and `<textarea>` do not appear anywhere in `ui/src`
 * — this app has no form controls at all — and the assertion that this stays true is in this file
 * rather than in a comment, because the day one appears it would be focusable with no `tabIndex`
 * and would slip past every rule below.
 */
const focusablesIn = (file: string): Focusable[] => {
  const source = withoutComments(sourceOf(file))
  const found: Focusable[] = []
  for (const match of source.matchAll(/<([a-z][a-zA-Z0-9]*)\b/g)) {
    const tag = match[1]
    const attrs = openingTagAt(source, match.index + match[0].length)
    if (attrs === null) continue
    const hasTabIndex = /\btabIndex\s*=/.test(attrs)
    if (tag !== 'button' && tag !== 'a' && !hasTabIndex) continue
    found.push({
      file,
      tag,
      classes: classesIn(attrs),
      hasTabIndex,
      tabIndexValue: /\btabIndex\s*=\s*\{?\s*(-?\d+)/.exec(attrs)?.[1] ?? null,
    })
  }
  return found
}

const FOCUSABLES = shippedModules.flatMap(focusablesIn)

// ---------------------------------------------------------------------------------------

/** One `:focus-visible` rule: the classes it targets, and the declarations it makes. */
interface FocusRule {
  readonly file: string
  readonly selector: string
  readonly body: string
}

const focusRules: FocusRule[] = shippedStylesheets.flatMap((file) => {
  const css = sourceOf(file).replace(/\/\*[\s\S]*?\*\//g, '')
  return [...css.matchAll(/([^{}]*:focus-visible[^{}]*)\{([^{}]*)\}/g)].map((m) => ({
    file,
    selector: m[1].trim(),
    body: m[2],
  }))
})

/** The rules whose selector mentions this class at all. */
const rulesFor = (className: string) =>
  focusRules.filter((r) => new RegExp(`\\.${className}(?![\\w-])`).test(r.selector))

const OVER_ART = 'over-art composite'
const KNOWN_SURFACE = 'known-surface outline'

/**
 * Which of the two treatments a class carries, or `null` for the failure AC 16 is about.
 *
 * The two tiers, from `DESIGN.md` and gate correction C4:
 *
 *   **over art** — `box-shadow: var(--shadow-focus-ring-over-art)` PLUS an authored outline at
 *   **offset 0**. `--focus-ring-offset` is deliberately NOT used: `CardTile.css:192-193` records
 *   why — *"the offset that suits a text link is what would split this ring in two"*.
 *
 *   **over a known surface** — the plain outline at `--focus-ring-offset`.
 *
 * A class carrying BOTH, or NEITHER, is the finding.
 */
const treatmentOf = (className: string): string[] => {
  const bodies = rulesFor(className).map((r) => r.body)
  const tiers = new Set<string>()
  for (const body of bodies) {
    const hasOutline = /outline\s*:\s*var\(--focus-ring-width\)/.test(body)
    if (!hasOutline) continue
    if (/box-shadow\s*:[^;]*--shadow-focus-ring-over-art/.test(body)) tiers.add(OVER_ART)
    else if (/outline-offset\s*:\s*0\b/.test(body)) tiers.add(OVER_ART)
    else if (/outline-offset\s*:\s*var\(--focus-ring-offset\)/.test(body)) tiers.add(KNOWN_SURFACE)
  }
  return [...tiers]
}

// ---------------------------------------------------------------------------------------

describe('the guard is reading the app at all (non-vacuity)', () => {
  it('found the shipped modules, the stylesheets and the focus rules', () => {
    // Every assertion in this file loops over one of these three. An empty one — a wrong cwd, a
    // git call resolving nothing, a regex that stopped matching — turns the whole file into a set
    // of tautologies. That is the coverage-that-reads-as-coverage failure this epic has found in
    // its own flagship guard in FOUR consecutive stories, so it is checked first and by name.
    expect(shippedModules.length).toBeGreaterThan(15)
    expect(shippedStylesheets.length).toBeGreaterThan(15)
    expect(focusRules.length).toBeGreaterThan(4)
  })

  it('found every focusable element the app is known to ship, by file', () => {
    // The count is NOT pinned to a number, deliberately: a pin would have to move for every new
    // control and would say nothing about whether the SET was found. What is pinned is that each
    // known host file contributed at least one — so a parser that silently stopped matching one
    // component's JSX fails here instead of quietly excusing that component from every rule below.
    const files = new Set(FOCUSABLES.map((f) => f.file))
    for (const known of [
      'src/containers/CardTile/CardTile.tsx',
      'src/containers/FlipControl/FlipControl.tsx',
      'src/containers/DeckList/DeckList.tsx',
      'src/containers/CardDetail/CardDetail.tsx',
      'src/components/Footer/Footer.tsx',
      'src/containers/SkipLink/SkipLink.tsx',
      // c5-7's connection pill — the app's LAST Tab stop before the footer links, and the first
      // focusable element Epic 5 ships. A parser that stopped seeing it would excuse it from the
      // ring rule, the hit-box rule and the real-control rule in one silent step.
      'src/containers/ConnectionPill/ConnectionPill.tsx',
    ]) {
      expect(files, `no focusable element found in ${known}`).toContain(known)
    }
  })

  it('classifies the two shipped tiers as DIFFERENT, which is what makes the rule bite', () => {
    // If `treatmentOf` collapsed both tiers to one label — or to `null` for both — the
    // "exactly one of two" rule below would still pass for every element while checking nothing.
    // Two known members, one from each tier, asserted to be classified apart.
    expect(treatmentOf('card-tile')).toEqual([OVER_ART])
    expect(treatmentOf('footer-attribution-link')).toEqual([KNOWN_SURFACE])
    // c5-7's pill sits on `--surface-panel`, so it takes the known-surface tier too — asserted
    // here rather than only through the loop below, because a NEW member classified as `[]` would
    // be reported by that loop as a missing ring when the real fault could be the parser.
    expect(treatmentOf('connection-pill')).toEqual([KNOWN_SURFACE])
    // …and a class with no rule at all really does come back empty, which is the failure signal.
    expect(treatmentOf('card-detail-headline')).toEqual([])
  })
})

describe('every focusable element carries exactly one of two focus treatments (AC 16)', () => {
  it('and NONE carries neither — the clause nothing checked before this story', () => {
    const uncovered: string[] = []
    for (const focusable of FOCUSABLES) {
      const tiers = focusable.classes.flatMap(treatmentOf)
      const unique = [...new Set(tiers)]
      if (unique.length !== 1) {
        uncovered.push(
          `${focusable.file} — <${focusable.tag} class="${focusable.classes.join(' ')}"> has ` +
            `${unique.length === 0 ? 'NO' : unique.length} focus treatment(s) ` +
            `[${unique.join(', ')}]. UX-DR46 requires a visible keyboard indicator on every ` +
            `focusable element, and this app draws exactly two: the over-art composite at ` +
            `offset 0 for anything sitting on card art, and the plain outline at ` +
            `--focus-ring-offset for anything on a known surface.`,
        )
      }
    }
    expect(uncovered).toEqual([])
  })
})

describe('the ring’s spelling does not drift (AC 17, AC 18)', () => {
  it('never removes the UA outline, in any of its four spellings', () => {
    // The UA ring may only be REPLACED. stylelint enforces this too; the duplicate is deliberate,
    // because a stylelint rule is one config edit from gone and this states the requirement where
    // the reason for it is written.
    for (const file of shippedStylesheets) {
      const css = sourceOf(file).replace(/\/\*[\s\S]*?\*\//g, '')
      for (const spelling of [
        /outline\s*:\s*none/i,
        /outline\s*:\s*0(?![\w.])/i,
        /outline-style\s*:\s*none/i,
        /outline-width\s*:\s*0(?![\w.])/i,
      ]) {
        expect(spelling.test(css), `${file} removes the focus outline (${spelling})`).toBe(false)
      }
    }
  })

  it('uses --focus-ring, not --accent-bright, in every ring (Q6)', () => {
    // The two tokens carry ONE hex — `#b3baff`, at `tokens.css:109` and `:116` — so nothing on
    // screen distinguishes them and no eye-check ever could. `DESIGN.md:31` and `:332` disagree
    // about which one the ring is; `tokens.css:113-115` settles it, because `--focus-ring` exists
    // for precisely this. A guard keyed on token IDENTITY sees a difference a human cannot.
    //
    // ==== NARROWED TO THE RING'S OWN PROPERTIES (c6-5, 2026-08-10) ======================
    // This read the WHOLE rule body until c6-5, which was the same claim while no `:focus-visible`
    // rule declared anything but a ring. The agent view's close pill is DESIGN.md's nav pill
    // (`:451`), whose spec gives hover AND focus the same three changes — border to
    // `{nav-pill.hover-border}`, TEXT to `{nav-pill.hover-foreground}` (which is `accent-bright`)
    // and `{nav-pill.hover-glow}`. A body-wide ban made that spec unshippable: the foreground of
    // a focused control is not a ring, and there is no other token for "the pill's text is lit".
    //
    // So the ban is keyed on the properties that actually DRAW an indicator. That is what the
    // test's own name, message and Q6 rationale have always said — *"in every RING"* — and it
    // leaves the drift this guard exists to catch fully covered: `outline`, `outline-color` and
    // `box-shadow` are the only ways a ring reaches the screen, and `--accent-bright` in any of
    // them is still red. Narrowing rather than exempting the class, because an exemption list
    // had to grow again at c6-8's nav pills, which carry the identical spec — and did: see
    // `.agent-views-nav-pill:focus-visible` in that stylesheet, whose accent-bright is a TEXT
    // colour and whose outline is the plain ring, exactly as this narrowing anticipated.
    const RING_PROPERTIES = /^(outline|outline-color|box-shadow)$/i
    for (const rule of focusRules) {
      const ringDeclarations = rule.body.split(';').filter((declaration) => {
        const colon = declaration.indexOf(':')
        return colon !== -1 && RING_PROPERTIES.test(declaration.slice(0, colon).trim())
      })
      expect(
        ringDeclarations.some((declaration) => declaration.includes('--accent-bright')),
        `${rule.file} — \`${rule.selector}\` draws its ring from --accent-bright; ` +
          `--focus-ring is the token for a focus indicator and carries the same value`,
      ).toBe(false)
    }
  })

  it('would still catch a ring drawn from --accent-bright — the firing half', () => {
    // The narrowing above is only safe if the narrowed guard still fires, so the proof is fed
    // inline rather than by breaking a real stylesheet. Both ring spellings are planted, and the
    // `color:` declaration that the narrowing deliberately admits is planted beside them so the
    // difference between the two is asserted rather than described.
    const ringsIn = (body: string) =>
      body.split(';').filter((declaration) => {
        const colon = declaration.indexOf(':')
        return (
          colon !== -1 &&
          /^(outline|outline-color|box-shadow)$/i.test(declaration.slice(0, colon).trim())
        )
      })

    expect(
      ringsIn('outline: 2px solid var(--accent-bright);').some((d) =>
        d.includes('--accent-bright'),
      ),
    ).toBe(true)
    expect(
      ringsIn('box-shadow: 0 0 0 2px var(--accent-bright);').some((d) =>
        d.includes('--accent-bright'),
      ),
    ).toBe(true)
    expect(
      ringsIn(
        'color: var(--accent-bright); outline: var(--focus-ring-width) solid var(--focus-ring);',
      ).some((d) => d.includes('--accent-bright')),
    ).toBe(false)
  })

  it('keeps --focus-ring-offset UNUSED on the two over-art elements (AC 17)', () => {
    // The offset-0 spelling is load-bearing rather than incidental: the composite is a ring plus a
    // separating band, and an offset would split it in two. `CardTile.css:192-193` says so.
    for (const className of ['card-tile', 'flip-control']) {
      for (const rule of rulesFor(className)) {
        expect(
          rule.body.includes('--focus-ring-offset'),
          `${rule.file} — \`${rule.selector}\` uses --focus-ring-offset on an over-art element`,
        ).toBe(false)
      }
    }
  })
})

describe('every interactive element is a real control with a real hit box (AC 20, UX-DR47)', () => {
  it('is a <button> or an <a>, never a div with a handler — derived, not listed', () => {
    // The TAG half. A `<div onClick>` is banned by ESLint too (`jsx-a11y/no-static-element-
    // interactions`); this asserts the positive form of the same rule over the derived set, so a
    // future element that satisfies the linter by adding `role="button"` and a `tabIndex` — which
    // the linter accepts — still fails here unless it is a real control.
    const impostors = FOCUSABLES.filter(
      (f) => f.tag !== 'button' && f.tag !== 'a' && f.classes.join(' ') !== 'card-detail-oracle',
    )
    expect(
      impostors.map((f) => `${f.file} — <${f.tag} class="${f.classes.join(' ')}">`),
      'a focusable element that is not a real <button>/<a>. The one permitted exception is the ' +
        'oracle scroller, which is focusable for WCAG 2.1.1 (scrollable content must be ' +
        'reachable) and is NOT an interactive control — it has no handler and activates nothing.',
    ).toEqual([])
  })

  it('declares a ≥24×24px hit box on BOTH axes wherever the type is under the floor', () => {
    // `--type-body-strong` is `700 14px/1.5` — a 21px line box, UNDER the 24px floor on its own.
    // So the two elements whose box is text-sized declare the minimum on both axes, which is
    // `Footer.css:83-89`'s idiom. The tile, the flip control and the deck row are all sized well
    // clear of it by their own geometry, which is why this asserts the DECLARATION where it is
    // needed rather than demanding it everywhere.
    //
    // AND THE SPLIT IS DERIVED OVER THE WHOLE SET, not hand-listed (code review 2026-08-07: the
    // first shipped form listed the two classes with a prose "sized well clear" reason nothing
    // backed, so a later TEXT-SIZED control would have shipped silently). Every focusable must
    // fall in one of the two named groups; a new one in neither reddens this test and forces the
    // author to classify it — declare the minimum, or claim well-clear where the claim is
    // checked-in and eye-checkable.
    // `connection-pill` joins at c5-7 and it is the clearest member of the group: its tallest
    // text is `--type-body`'s 14px at 1.5 (a 21px line box) beside a `--type-micro` word, so the
    // pill is UNDER the floor on its own geometry and declares both minimums explicitly.
    // `agent-view-close` joins at c6-5 for the connection pill's reason exactly: it is a nav
    // pill on `--type-label` (11px at 1.3 — a 14px line box), so it is UNDER the floor on its
    // own geometry however much padding it carries, and it declares both minimums explicitly.
    // `agent-views-nav-pill` joins at c6-8, and it is the prediction two lines up landing
    // exactly as written: it IS the nav pill, on the same `--type-label` (11px at 1.3 — a 14px
    // line box) as the close pill it shares a DESIGN.md block with, so it is under the floor on
    // its own geometry however much padding it carries, and it declares both minimums in the
    // same rule. Four members of this group now, and every one of them is a pill.
    // `agent-views-nav-entry` joins at 17.2, the fifth pill-family member in all but shape: a
    // history-popover entry's tallest line is `--type-body`'s 14px at 1.5 (a 21px box) beside
    // an 11px label, so the row is under the floor on its own geometry however much padding it
    // carries, and it declares both minimums in its own rule (EXPERIENCE.md's "every entry has
    // a ≥ 24×24px hit area" made a declaration rather than a claim).
    const DECLARES_MIN = [
      'footer-attribution-link',
      'skip-link',
      'connection-pill',
      'agent-view-close',
      'agent-views-nav-pill',
      'agent-views-nav-entry',
    ]
    // Well clear BY MEASURED GEOMETRY, each with its eye-check on record: the tile is card-sized,
    // the flip control's hit box is 32×32 (c4-6), the deck row spans the panel at ≥34px, the
    // unpin control measured 61×30 (c4-5), and the oracle scroller is a multi-line text block.
    // `suggestion-row` joins at c6-7, and it is the most clearly-clear member of the group: the
    // row is a two-line grid — a head line on `--type-body-strong` (14px at 1.5 = a 21px line
    // box) over a reason on `--type-body` (another 21px), separated by `--space-2` and wrapped in
    // `--space-2` of block padding, so it is ~66px tall before the thumbnail is considered. The
    // thumbnail spans that whole height at 63:88 and the row spans the view's width, so BOTH axes
    // are clear by an order of magnitude on the short one. This is a derived-geometry claim like
    // the deck row's above; the pixels are the C6 manual checklist's (c8-6), as they are for
    // every other member.
    // `swap-tile` joins at 16.1, on the suggestion row's derived-geometry argument: the tile is
    // a flex column of a micro label (10px at 1.3 — a 13px line box) over a card-shaped thumb
    // whose slot declares `min-height: 6lh` against `--type-body` (6 × 21px = 126px), with the
    // width following from 63:88 (≈90px) — both axes clear of the 24px floor by multiples. The
    // pixels are the manual checklist's, as for every other member.
    // `tier-tile` joins at 16.2, minus the swap tile's label line: the tile IS its card-shaped
    // thumb slot, which declares an explicit `width: 176px` (DESIGN.md's tier-row thumb-width,
    // added 2026-08-23 — the first spelling here claimed a width "following from 63:88", a
    // derivation that never produced one: an aspect-ratio box with no in-flow content has no
    // intrinsic width) with the HEIGHT following from 63:88 (≈246px) — both axes clear of the
    // 24px floor by multiples. The pixels are the manual checklist's, as for every other member.
    // `group-tile` joins at 16.3, on the swap tile's argument — a `min-height: 6lh` slot
    // against `--type-body` (6 × 21px = 126px), a 63:88-derived width, multiples of the floor
    // claimed on both axes. (That width derivation is the one the tier tile's correction above
    // records as never having produced a width; the group tile still rides it, a recorded
    // follow-up — the 126px HEIGHT alone clears the 24px floor by multiples either way.) The
    // pixels are the manual checklist's, as for every other member.
    const WELL_CLEAR = [
      'card-tile',
      'flip-control',
      'deck-row',
      'suggestion-row',
      'swap-tile',
      'tier-tile',
      'group-tile',
      'card-detail-unpin',
      'card-detail-oracle',
    ]
    for (const focusable of FOCUSABLES) {
      const classified =
        focusable.classes.some((c) => DECLARES_MIN.includes(c)) ||
        focusable.classes.some((c) => WELL_CLEAR.includes(c))
      expect(
        classified,
        `${focusable.file} — <${focusable.tag} class="${focusable.classes.join(' ')}"> is in ` +
          `neither hit-box group: declare min-width/min-height 24px, or add it to WELL_CLEAR ` +
          `with its measured geometry`,
      ).toBe(true)
    }
    for (const className of DECLARES_MIN) {
      const css = shippedStylesheets
        .map(sourceOf)
        .filter((s) => s.includes(`.${className}`))
        .join('\n')
      expect(css, `${className} declares no min-width`).toMatch(/min-width:\s*24px/)
      expect(css, `${className} declares no min-height`).toMatch(/min-height:\s*24px/)
    }
    // ⚠️ THE RENDERED BOX IS NOT ASSERTED HERE AND CANNOT BE. jsdom resolves no layout, so this is
    // a claim about source. The measured box is the eye-check's, and c2-10's own residue
    // (`deferred-work.md:1634-1640`) is about exactly that gap for the footer links.
  })

  it('ships no form control, so there is no fourth kind of focusable to have missed', () => {
    // `focusablesIn` looks for three shapes. That is complete only while the app has no
    // `<input>`, `<select>` or `<textarea>` — all of which are focusable with no `tabIndex` and
    // would slip past every rule above. Asserted rather than assumed, so the day Epic 6 adds a
    // text input this guard fails and gets extended instead of silently narrowing.
    for (const file of shippedModules) {
      const source = withoutComments(sourceOf(file))
      expect(source, `${file} ships a form control this guard does not model`).not.toMatch(
        /<(input|select|textarea)\b/,
      )
    }
  })

  it('passes no tabIndex through a CAPITALIZED component, the fifth kind (code review 2026-08-07)', () => {
    // `focusablesIn` sees lowercase tags only — a `<Badge tabIndex={0}>`, or any primitive
    // spreading props onto a DOM node, would ship a REAL Tab stop invisible to every rule in this
    // file. Same posture as the form-control assertion above: ban the idiom loudly, so the day a
    // component legitimately needs one, this guard is EXTENDED to model it instead of silently
    // not seeing it.
    for (const file of shippedModules) {
      const source = withoutComments(sourceOf(file))
      for (const match of source.matchAll(/<([A-Z][a-zA-Z0-9]*)\b/g)) {
        const attrs = openingTagAt(source, match.index + match[0].length)
        expect(
          attrs !== null && /\btabIndex\s*=/.test(attrs),
          `${file} passes tabIndex to <${match[1]}> — a focusable this guard cannot see`,
        ).toBe(false)
      }
    }
  })
})

describe('the document keyboard layering is one listener, in the bubble phase (AC 29)', () => {
  /**
   * Every `document.addEventListener` for a key event in shipped source, with its phase.
   *
   * ⚠️ **THIS GUARD EXISTS BECAUSE PROBE (j) PASSED.** c4-11 enumerated "a second document-level
   * key listener" as an evasion to probe, added one in the CAPTURE phase, ran the full suite —
   * and **nothing went red**. The contract was written down in four places (`CardDetail.tsx:88-101`,
   * the story's don't-break list, `EXPERIENCE.md`, UX-DR39) and enforced nowhere. Recorded rather
   * than quietly fixed, per this epic's standing rule.
   *
   * What the contract is: `CardDetail` registers ONE `keydown` on `document`, in the **bubble**
   * phase, to release a pin on Esc, and the agent view registers ONE in the **capture** phase,
   * which closes the view and calls `stopPropagation()` so the pin survives (UX-DR39: *"Esc
   * closes the topmost thing"*). Capture at the document runs before the bubble listener for
   * EVERY target, which is what makes the layering hold even when focus sits on `<body>` — an
   * element-scoped handler could not manage that, and the first written form of the contract had
   * exactly that hole (found at review 2026-08-05).
   *
   * **THE RESERVATION IS NOW FILLED (c6-5, 2026-08-10).** This guard shipped asserting that NO
   * listener anywhere used the capture phase, holding it empty for the agent view that did not
   * yet exist. That view now exists, so the rule becomes what it was always going to become: an
   * ENUMERATED table of who owns which phase, below. The change is deliberately not a relaxation
   * — "no capture anywhere" is replaced by "exactly these two listeners, each in exactly this
   * phase", which is strictly more than the old rule asserted, and a third listener in either
   * phase is still red.
   *
   * A listener outside that table breaks the contract in one of two ways: a second capture one
   * races the agent view for the same Esc, and a second bubble one makes the ordering between
   * two same-phase listeners depend on module import order.
   */
  /**
   * The remaining call arguments starting just after the event-name comma, extracted with a
   * balanced-paren scan. ⚠️ The first shipped form captured `([^)]*)\)` — which truncates at the
   * FIRST `)`, so an inline arrow handler (`(e) => onKey(e), true`) hid its third argument
   * OUTSIDE the inspected text and the phase assertion below passed on the truncated string: the
   * precise probe-(j) hole this guard was built to close, still open along one syntactic path
   * (code review 2026-08-07).
   */
  const callArgsFrom = (source: string, start: number): string => {
    let depth = 1
    let quote: string | null = null
    for (let i = start; i < source.length; i += 1) {
      const ch = source[i]
      if (quote !== null) {
        if (ch === quote && !isEscaped(source, i)) quote = null
        continue
      }
      if (ch === '"' || ch === "'" || ch === '`') quote = ch
      else if (ch === '(') depth += 1
      else if (ch === ')') {
        depth -= 1
        if (depth === 0) return source.slice(start, i)
      }
    }
    return source.slice(start)
  }

  /** `rest` split on top-level commas only — commas inside `(){}[]` or strings do not count. */
  const topLevelArgs = (rest: string): string[] => {
    const args: string[] = []
    let depth = 0
    let quote: string | null = null
    let from = 0
    for (let i = 0; i < rest.length; i += 1) {
      const ch = rest[i]
      if (quote !== null) {
        if (ch === quote && !isEscaped(rest, i)) quote = null
        continue
      }
      if (ch === '"' || ch === "'" || ch === '`') quote = ch
      else if (ch === '(' || ch === '{' || ch === '[') depth += 1
      else if (ch === ')' || ch === '}' || ch === ']') depth -= 1
      else if (ch === ',' && depth === 0) {
        args.push(rest.slice(from, i))
        from = i + 1
      }
    }
    args.push(rest.slice(from))
    return args
  }

  // BOTH global receivers, not just `document`: a `window` capture listener runs before
  // CardDetail's document bubble listener for EVERY target, so the contract is broken exactly as
  // hard by `window.addEventListener` — which the first shipped scan did not watch (code review
  // 2026-08-07). Element-ref receivers (`document.body`, `document.documentElement`) remain
  // outside this model, declared: nothing ships one, and either would first need a ref to those
  // nodes, which no container has a reason to hold.
  const keyListeners = tracked('*.ts')
    .concat(shippedModules)
    .filter((f) => !f.includes('.test.'))
    .flatMap((file) => {
      const source = withoutComments(sourceOf(file))
      return [
        ...source.matchAll(
          /\b(document|window)\.addEventListener\(\s*['"](keydown|keyup|keypress)['"]\s*,/g,
        ),
      ].map((m) => ({
        file,
        receiver: m[1],
        event: m[2],
        rest: callArgsFrom(source, (m.index ?? 0) + m[0].length),
      }))
    })

  /**
   * WHO OWNS WHICH PHASE. In the order the scan finds them, which is `git ls-files` order.
   *
   * Enumerated rather than derived, exactly like `token-usage.test.ts`'s shipped-motion pin and
   * for the same reason: a story that adds, removes or RE-PHASES a document key listener moves
   * this table on purpose, in the same commit, and a story that does it by accident goes red.
   * There is no rule that could derive "the agent view captures and the detail panel bubbles" —
   * that is UX-DR39's layering, which lives in prose and in this list.
   */
  const DOCUMENT_KEY_LISTENERS: { entry: string; capture: boolean }[] = [
    // c6-5. Closes the view and calls `stopPropagation()`, so this Esc never reaches the bubble
    // listener below and the pin survives (EXPERIENCE.md:141, Flow 1 :188). Registered only
    // while a view is open — an always-mounted capture listener would swallow Esc for the pin
    // when nothing is showing, which inverts UX-DR39 rather than implementing it.
    { entry: 'src/containers/AgentView/AgentView.tsx:document.keydown', capture: true },
    // 17.2. Closes the history popover — at the document because the popover's entries are
    // ordinary document-order Tab stops, so focus can wander OUT of the popover while it stays
    // open, and an element-scoped handler would never hear that Esc. BUBBLE, registered only
    // while the popover shows, never stopping propagation: the agent view's capture listener
    // above pre-empts it while a view is open (when the popover is closed by invariant anyway,
    // so the pre-emption is belt on braces). Sharing the bubble phase with the two listeners
    // below is safe by the same defaultPrevented discipline they use — AND the layering
    // UX-DR39's amended order needs (Esc closes the popover WITHOUT releasing an active pin)
    // is carried by a node-level listener on the pill+popover WRAPPER (not the popover root —
    // focus legitimately sits on the pill while the popover is open), which runs before every
    // document listener and calls `preventDefault()`; this document twin and CardDetail's
    // release both honour that flag, so a popover Esc struck with focus inside the wrapper
    // closes exactly one layer. With focus OUTSIDE the wrapper, this listener and CardDetail's
    // both act — the residual the entries-as-ordinary-Tab-stops ruling accepts, PINNED in
    // App.test.tsx (17.2) and carried in EXPERIENCE.md's Esc bullet, not merely recorded here.
    { entry: 'src/containers/AgentViewsNav/AgentViewsNav.tsx:document.keydown', capture: false },
    // c4-5. Releases the pin, in the bubble phase, so the capture listener above always wins.
    { entry: 'src/containers/CardDetail/CardDetail.tsx:document.keydown', capture: false },
    // 17.1. Suppresses the pill's tooltip reveal (WCAG 1.4.13 dismissable) — at the document
    // because a hover-only reveal holds no focus, so the key lands on `document.body` and a
    // button handler would never hear it. BUBBLE, and sharing the phase with CardDetail's is
    // safe HERE though it would not be in general: neither bubble listener stops propagation,
    // and their effects are independent (one Esc may release the pin AND dismiss the tooltip —
    // there is no order in which those two outcomes differ), so import order still decides
    // nothing. The agent view's capture listener keeps pre-empting both, which is UX-DR39's
    // layering: while a view is open the pill sits under the scrim anyway.
    { entry: 'src/containers/ConnectionPill/ConnectionPill.tsx:document.keydown', capture: false },
  ]

  it('registers exactly these document key listeners, and names their owners', () => {
    expect(
      keyListeners.map((l) => `${l.file}:${l.receiver}.${l.event}`),
      'the document keyboard layering admits exactly four listeners — the agent view’s Esc in ' +
        'CAPTURE, and the history popover’s, CardDetail’s and the connection pill’s in BUBBLE ' +
        '(safe together because none stops propagation and the popover/pin ordering rides ' +
        'defaultPrevented from the popover’s node-level listener — see the table). Any ' +
        'OTHER listener (on document OR window) breaks UX-DR39’s "Esc closes the topmost ' +
        'thing" ordering, and a same-phase listener whose effect interacts with an existing ' +
        'one makes the outcome depend on module import order.',
    ).toEqual(DOCUMENT_KEY_LISTENERS.map((l) => l.entry))
  })

  it('registers each listener in the phase UX-DR39 gives it', () => {
    // The THIRD argument decides the phase: `true` or `{ capture: true }` is capture, anything
    // else is bubble. Asserted on that argument ALONE — isolated by a top-level-comma split so an
    // inline handler whose BODY contains `true` (`(e) => setOpen(true)`) cannot false-positive,
    // and a third argument hiding behind an arrow's `)` cannot escape.
    //
    // BOTH DIRECTIONS, which is what makes this stronger than the "no capture anywhere" rule it
    // replaces: the agent view's listener must BE capture (a bubble one would race CardDetail's
    // by import order and release the pin on the same Esc that closes the view), and
    // CardDetail's must NOT be (a capture one would pre-empt the view it is supposed to lose to).
    for (const listener of keyListeners) {
      const entry = `${listener.file}:${listener.receiver}.${listener.event}`
      const declared = DOCUMENT_KEY_LISTENERS.find((l) => l.entry === entry)
      const phaseArg = topLevelArgs(listener.rest)[1] ?? ''
      expect(
        /\btrue\b|capture\s*:\s*true/.test(phaseArg),
        `${entry} is registered in the ${declared?.capture ? 'BUBBLE' : 'CAPTURE'} phase; ` +
          `UX-DR39 gives it ${declared?.capture ? 'CAPTURE' : 'BUBBLE'} (CardDetail.tsx:88-101)`,
      ).toBe(declared?.capture ?? false)
    }
  })

  it('is genuinely reading the listeners it names (non-vacuity)', () => {
    // Without this, a regex that stopped matching would report an EMPTY list — and the phase rule
    // above would pass by looping over nothing. Both shipped listeners are asserted to be found
    // AND to be the Esc handlers they claim to be.
    expect(keyListeners).toHaveLength(DOCUMENT_KEY_LISTENERS.length)
    for (const file of [
      'src/containers/AgentView/AgentView.tsx',
      'src/containers/AgentViewsNav/AgentViewsNav.tsx',
      'src/containers/CardDetail/CardDetail.tsx',
      'src/containers/ConnectionPill/ConnectionPill.tsx',
    ]) {
      expect(withoutComments(sourceOf(file))).toContain("event.key !== 'Escape'")
    }
    // The half the phase loop cannot see: the agent view's listener is only useful if it STOPS
    // the event, and a capture listener that forgot to would close the view and release the pin
    // on one keystroke — the exact regression dw:4766-4773 was written about.
    expect(
      withoutComments(sourceOf('src/containers/AgentView/AgentView.tsx')),
      'the capture-phase listener must call stopPropagation(), or one Esc closes the view AND ' +
        'releases the pin (UX-DR39, dw:4766-4773)',
    ).toContain('event.stopPropagation()')
  })
})

describe('the Tab order is document order, not tabindex (AC 12, c4-6)', () => {
  it('declares no POSITIVE tabindex anywhere', () => {
    // A positive `tabindex` would be a new doctrine for this app: it reorders the Tab sequence
    // independently of the DOM, and every order assertion in this repo reads document order.
    for (const focusable of FOCUSABLES) {
      const value = focusable.tabIndexValue
      if (value === null) continue
      expect(
        Number(value),
        `${focusable.file} — <${focusable.tag}> declares tabIndex=${value}`,
      ).toBeLessThanOrEqual(0)
    }
  })

  it('names its ONE tabindex exception, and nothing else carries one (AC 12)', () => {
    // The exceptions are enumerated BY NAME rather than counted, so a second `tabIndex` added
    // anywhere fails even though a count would still look plausible.
    const declared = FOCUSABLES.filter((f) => f.hasTabIndex).map(
      (f) => `${f.file}:${f.classes.join(' ')}=${f.tabIndexValue}`,
    )
    expect(declared).toEqual([
      // The oracle scroller — c4-11's WCAG 2.1.1 stop (`deferred-work.md:3875-3883`). The only
      // `tabIndex` in JSX in the whole app.
      'src/containers/CardDetail/CardDetail.tsx:card-detail-oracle=0',
    ])
  })

  it('sets the focus-home tabindex IMPERATIVELY, in exactly one module (AC 6)', () => {
    // `tabIndex = -1` on a heading is the shipped exception, and it is imperative so the element
    // at REST carries no attribute — which is what `CardDetail`'s not-a-modal assertion checks.
    // ONE module, because AC 6 requires one focus home and one implementation of it.
    const owners = tracked('*.ts')
      .concat(shippedModules)
      .filter((f) => !f.includes('.test.'))
      .filter((f) => /\.tabIndex\s*=/.test(withoutComments(sourceOf(f))))
    expect(owners).toEqual(['src/containers/focusHome.ts'])
  })
})
