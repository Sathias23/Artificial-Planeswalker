/**
 * The format check's SOURCE-level gates (story c4-10, AC 13, 19, 22–25, 30, 33, 35).
 *
 * **Why these live in `tests/` rather than beside the component.** Three of them read files off
 * disk and one of them walks `git ls-files`; the `dom` vitest project runs under jsdom, where
 * `import.meta.url` is not a `file:` URL and `fileURLToPath` throws outright (measured — the first
 * draft of `FormatCheck.test.tsx` failed to collect with `TypeError: The URL must be of scheme
 * file`). The `node` project is where a file-reading assertion belongs, which is the same split
 * `shell.test.ts` already uses for c4-9's *"assert the CSS half against the stylesheet source"*.
 *
 * And two of them could not be written in jsdom at all: **jsdom applies no stylesheet and has no
 * layout engine**, so every geometry claim in this story is about the stylesheet SOURCE or the
 * class, never a rendered pixel. The eye-check owns the rest.
 *
 * This file imports `src/containers/FormatCheck/copy.ts` — legal precisely because that module is
 * import-free, which is the property its own header exists to preserve and which the first test
 * below asserts rather than assumes.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// The EXPLICIT `.ts` extension is required, not stylistic: `tests/` is the `nodenext` project, and
// an extensionless relative specifier is `TS2835` — the very error `copy.ts`'s own header is about,
// arriving from the other side. `unknown-card-copy.test.ts` and `pin-announcement-copy.test.ts`
// both spell it this way; this file measured it the hard way and now matches them.
import {
  CHECK_LABELS,
  FORMAT_CHECK_TITLE,
  STATUS_WORDS,
} from '../src/containers/FormatCheck/copy.ts'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

/**
 * Comments stripped, so a doc comment that MENTIONS an identifier is not read as using it.
 *
 * **This is load-bearing rather than tidy, and the first draft of this file proved it**: every
 * ban below fired against its own explanatory comment. `FormatCheck.css`'s header names `9px 2px`
 * as the value it REFUSES, cites `DESIGN.md`, and explains why `--type-numeric`, `--radius-card`
 * and `--mana-*` are absent — so a raw-source scan reported the file as violating six rules it
 * documents itself for obeying. A guard that reads prose as code does not check the code.
 *
 * ⚠️ DECLARED LIMIT (c4-10 review): this is a regex pair, not a tokenizer, and it has two known
 * false-strip modes — a `/*` INSIDE a string literal consumes to the next asterisk-slash, and a
 * `//` inside a string (this codebase's own `' // '` card-name separator, which `DeckList`
 * handles by name) deletes the string's tail before the bans run. No file scanned here trips
 * either today; the first edit that adds such a literal to a scanned module changes what this
 * guard READS without changing what SHIPS. If one of the four modules ever needs a `' // '` or
 * `'/*'` literal, replace this stripper with a real tokenizer rather than widening the regexes.
 */
const codeOf = (repoRelative: string) =>
  sourceOf(repoRelative)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')

// git, not readdir — the authority every guard in this project uses: node_modules, dist and
// coverage are invisible to it, and a committed module cannot escape CI. DECLARED LIMIT (the c4-7
// false-green): an un-`git add`ed module is equally invisible, so a new module and its staging
// must land together.
const trackedSources = execFileSync('git', ['ls-files', 'src/*.ts', 'src/*.tsx'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)

// The stylesheet is tracked separately: the ls-files globs above CANNOT match a `.css`, and the
// c4-10 review found the first draft papering over exactly that with a `.concat(file)` that made
// the tracked-file assertion below true for any string, always — the vacuous-guard class this
// file exists to refuse. Two lists, each asserted against the glob that can actually see it.
const trackedStyles = execFileSync('git', ['ls-files', 'src/*.css'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)

const TSX = 'src/containers/FormatCheck/FormatCheck.tsx'
const CSS = 'src/containers/FormatCheck/FormatCheck.css'
const COPY = 'src/containers/FormatCheck/copy.ts'
const SLICE = 'src/state/formatCheck.ts'
const FIXTURES = 'src/state/formatCheck.fixtures.ts'

describe('the guard reads a populated tree (non-vacuity)', () => {
  it('sees this story’s own modules', () => {
    // Without this, a wrong cwd or an unstaged tree would make every scan below pass by finding
    // nothing — which is the shape of the false green c4-9's review found twice in one story.
    // These assertions are against the LISTS THEMSELVES (no `.concat` — the review's High): an
    // un-`git add`ed module goes red here instead of sailing through the `is_legal` scan unseen.
    for (const file of [TSX, COPY, SLICE, FIXTURES]) {
      expect(trackedSources).toContain(file)
    }
    expect(trackedStyles).toContain(CSS)
    for (const file of [TSX, CSS, COPY, SLICE, FIXTURES]) {
      expect(sourceOf(file).length).toBeGreaterThan(200)
    }
    expect(trackedSources.length).toBeGreaterThan(30)
  })
})

describe('`is_legal` is bound to NOTHING, and that is machine-checkable now (AC 19, Q4)', () => {
  it('appears nowhere in src/ outside the generated types', () => {
    // `deferred-work.md:2430-2437`: *"Nothing machine-checkable stops c4-10 from binding
    // `is_legal` straight to the panel headline — a formatless deck would then render a red
    // headline over six rows none of which is a violation."* THIS IS THAT THING. The wire's own
    // `Warning:` block is prose; this turns it into a fact a regression reddens.
    //
    // Live exposure is ZERO (the trap needs an unrecognised format and all 40 real decks have
    // one), which is exactly the condition under which a wrong binding ships green — so the guard
    // is the only thing that would ever notice.
    const offenders = trackedSources.filter((file) => {
      // The generated types are the ONE legal home: describing a field is not binding it.
      if (file === 'src/api/types.d.ts') return false
      // Test files carry it because a fixture must model a real response — and the formatless
      // fixture sets it `false` deliberately, which is the trap this rule exists for.
      if (/\.test\.tsx?$/.test(file)) return false
      // The wire-fixture data module (c4-10 review, decision 2a): plain `.ts` so its pins run
      // once instead of once per importer, registered HERE BY NAME rather than by the blanket
      // above. A fixture body must carry `is_legal` because it models the real response shape —
      // describing the field is not binding it, exactly as for the generated types. The file's
      // own pins (`formatCheck.fixtures.test.ts`) hold the declaration honest.
      if (file === 'src/state/formatCheck.fixtures.ts') return false
      // Comments are stripped rather than files skipped, so `schema.ts`'s long doc comment about
      // the trap is not an offender while a real `report.is_legal` in that module still would be.
      return /\bis_legal\b/.test(codeOf(file))
    })

    expect(offenders).toEqual([])
  })

  it('is a NON-VACUOUS scan — it can see the identifier where one really is', () => {
    // Otherwise a typo in the pattern would make the rule pass forever. Proven against the
    // generated types, which genuinely declare the field, through the SAME predicate.
    expect(/\bis_legal\b/.test(codeOf('src/api/types.d.ts'))).toBe(true)
    // …and the doc-comment exemption is real rather than theoretical: `schema.ts` DOES mention
    // the identifier in prose, and is not an offender.
    expect(sourceOf('src/api/schema.ts')).toMatch(/\bis_legal\b/)
    expect(codeOf('src/api/schema.ts')).not.toMatch(/\bis_legal\b/)
  })
})

describe('the container keeps its posture (AC 13, AC 6, rulings 1, 2, 2b)', () => {
  it('reaches the network nowhere, and imports no state library', () => {
    // `shell.test.ts:2071-2086` enforces this over every container; asserting it here too is not
    // duplication but scope — that guard is a family ban, and these are this story's own named
    // paths, so a failure says WHICH rule this panel broke.
    expect(codeOf(TSX)).not.toMatch(/\bfetch\b|XMLHttpRequest|EventSource|WebSocket/)
    expect(codeOf(TSX)).not.toMatch(/from 'zustand'/)
    expect(codeOf(TSX)).not.toMatch(/\.setState\b/)
    expect(codeOf(TSX)).not.toMatch(/api\/client/)
  })

  it('never reads `boards`, the card cache, the inspection slice or the hydration sweep', () => {
    // The cleanest don't-break in the epic, and worth asserting because EVERY sibling panel takes
    // `boards` as its only prop — copying that shape here would have been wrong. AD-12's single
    // derivation and `deckMemory.ts`'s reference identity are untouched, and this is the reason
    // this panel is the first in the epic to escape c4-6's no-re-drive window structurally.
    for (const forbidden of [
      /\bboards\b/,
      /state\/cards/,
      /state\/inspection/,
      /state\/deckGroups/,
      /hydrate/,
      /useCardEntry|readCardEntry/,
    ]) {
      expect(codeOf(TSX)).not.toMatch(forbidden)
    }
  })

  it('imports its wire type with a STATEMENT-form `import type` (ruling 2b)', () => {
    // `shell.test.ts:1986-2023` reads the STATEMENT form, because `verbatimModuleSyntax` still
    // runs the module for the inline `import { type X }` spelling (c4-5 decision 2).
    expect(sourceOf(TSX)).toMatch(/^import type \{[^}]*\} from '\.\.\/\.\.\/api\/schema'$/m)
    expect(sourceOf(TSX)).not.toMatch(/^import \{[^}]*\btype\b[^}]*\} from '\.\.\/\.\.\/api\//m)
  })

  it('declares no design token and writes no inline style (rulings 6, 23)', () => {
    // `RUNTIME_CUSTOM_PROPERTIES` keeps its two entries and `eslint.config.js:204-240` is
    // untouched: this panel has NO computed geometry, so the custom-property channel c4-8 opened
    // and c4-9 extended is not triggered here. Stated rather than left as an absence.
    expect(codeOf(TSX)).not.toMatch(/style=\{/)
    expect(codeOf(TSX)).not.toMatch(/--[a-z-]+:/)
  })
})

describe('the slice is the ONE writer, and holds no timer (AC 9, AC 11)', () => {
  it('writes its store through exactly one setState call site', () => {
    const calls = codeOf(SLICE).match(/\.setState\(/g) ?? []
    expect(calls).toHaveLength(1)
  })

  it('holds no timer, no retry loop and no backoff', () => {
    // Q7: there is no refetch, and c7-3 owns `deck_changed`. A timer here would be a second
    // coalescing rule to reconcile with that story's.
    for (const forbidden of [
      /setInterval/,
      /setTimeout/,
      /requestAnimationFrame/,
      /\bwhile\s*\(/,
    ]) {
      expect(codeOf(SLICE)).not.toMatch(forbidden)
    }
  })

  it('decides no panel — `panelFor` is not imported (Q6, FR-13)', () => {
    // Routing an auxiliary panel's refusal through `panelFor` would replace a working deck view
    // with "The companion hit a bug", which is FR-13 inverted. The card precedent, not the deck.
    expect(codeOf(SLICE)).not.toMatch(/panelFor|state\/panel|PANEL_FOR_REASON/)
  })
})

describe('the stylesheet says what jsdom cannot (AC 22, 23, 24, 25, 30, 33)', () => {
  it('spells the hairline with its DESIGN.md citation, and skips the last row (Q11)', () => {
    // The CITATION is read from the raw source — it lives in a comment, which is the whole point
    // of the idiom `GroupHeader.css:22-23` established. The RULE is read from the stripped code,
    // because the citation itself spells `{colors.border-hairline}` and its closing brace would
    // terminate a `[^}]*` block match against the raw text.
    expect(sourceOf(CSS)).toMatch(/components\.legality-row\.rule/)
    expect(codeOf(CSS)).toMatch(
      /\.format-check-row:not\(:last-child\)\s*\{[^}]*border-bottom:\s*1px solid var\(--border-hairline\)/,
    )
  })

  it('right-aligns the badge through the grid’s content-sized end track — and carries no dead margin', () => {
    // The c4-10 review found the first draft crediting `margin-left: auto` (GroupHeader.css's
    // FLEX idiom) while shipping a GRID row — inside a `minmax(0, 1fr) auto` grid the badge's
    // `auto` track hugs its content, so an auto margin has no free space to consume and is inert.
    // The real mechanism is the track list itself: column one absorbs the free space, column two
    // hugs the right edge. Asserted here so a future reader deleting the grid cannot trust a
    // comment about a margin that never did the work — and the dead declaration is BANNED, not
    // merely dropped, so it cannot quietly return with its old caption.
    expect(codeOf(CSS)).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/)
    expect(codeOf(CSS)).not.toMatch(/margin-left:\s*auto/)
  })

  it('uses the SCALE for padding — never the artefact’s off-scale `9px 2px` (Q10, AC 24)', () => {
    // `DESIGN.md:237` carries `'9px 2px'`; neither number is on the 4/8/12/16/24/32/48 scale,
    // UX-DR5 names `9` in its own drift list, and stylelint refuses both outright.
    expect(codeOf(CSS)).toMatch(/padding:\s*var\(--space-2\)\s+var\(--space-1\)/)
    expect(codeOf(CSS)).not.toMatch(/9px/)
  })

  it('ships exactly ONE px literal, and it is the cited hairline (AC 24, ruling 7)', () => {
    // Ruling 7 requires a `DESIGN.md:NNN` citation within 60 characters of any `px` literal in
    // `src/containers/`. This file triggers it exactly once, and that once is cited — so the rule
    // is satisfied by not being triggered, which is stated rather than left as a silent absence.
    const literals = codeOf(CSS).match(/\b\d+px\b/g) ?? []
    expect(literals).toEqual(['1px'])
  })

  it('never uses a bare `1fr` track (shell.test.ts:960) and floors the label at 0', () => {
    expect(codeOf(CSS)).toMatch(/grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/)
    expect(codeOf(CSS)).toMatch(/\.format-check-label\s*\{[^}]*min-width:\s*0/)
  })

  it('sets the detail line by TIER, never in the uppercase micro role (AC 23, Q2)', () => {
    // A STATED DEVIATION FROM Q2, FOUND BY A GATE. `--type-micro` carries an uppercase companion
    // DERIVED from DESIGN.md's own `textTransform:` key, so `findRoleWithoutCompanions` refuses
    // it without `text-transform: uppercase` in the same block — and WITH it the sentence renders
    // "'PYM PARTICLES' IS NOT LEGAL IN BRAWL.", destroying the card name the panel exists to
    // show. (`Footer.css:29-35` accepts that consequence for the legal attribution and says so.)
    //
    // So the sentence is distinguished by TIER rather than by SIZE, which is `.deck-row`'s idiom
    // one directory over — and `--type-body` requires no companion at all, so nothing is being
    // routed around here: the guard is satisfied by not applying the role it constrains.
    const block = codeOf(CSS).match(/\.format-check-detail\s*\{[^}]*\}/)?.[0] ?? ''
    expect(block).toContain('font: var(--type-body)')
    expect(block).toContain('color: var(--text-tertiary)')
    expect(codeOf(CSS)).not.toMatch(/--type-micro/)
    // …and no `text-transform` anywhere in the file: this panel uppercases nothing of its own.
    // `Badge`'s pill is uppercased by `Badge.css`, which is the primitive's business, not ours.
    expect(codeOf(CSS)).not.toMatch(/text-transform/)
  })

  it('ships NO numeric role, so its companion rule is not triggered (AC 23)', () => {
    // `findUnpairedNumericRole` fires on `--type-numeric` without `font-variant-numeric`. This
    // panel renders no number at all — the counts on the wire reach no chrome (Q4, Q14) — so the
    // rule is satisfied by not being triggered, which is stated rather than left as an absence.
    expect(codeOf(CSS)).not.toMatch(/--type-numeric/)
  })

  it('draws no card and spends no mana token (AC 25, UX-DR4, UX-DR7)', () => {
    expect(codeOf(CSS)).not.toMatch(/--radius-card/)
    expect(codeOf(CSS)).not.toMatch(/aspect-ratio/)
    expect(codeOf(CSS)).not.toMatch(/--mana-/)
  })

  it('animates nothing, and bans no outline it never draws (AC 30, ruling 9)', () => {
    // UX-DR42's exhaustive inventory has no format-check row and this story adds none, so the
    // reduced-motion block needs no entry and the shipped-motion pin holds at 4.
    expect(codeOf(CSS)).not.toMatch(/\btransition\s*:/)
    expect(codeOf(CSS)).not.toMatch(/\banimation[-a-z]*\s*:/)
    // `(?<![-\w])` so `text-transform:` — which this file DOES declare, and must — is not read as
    // the `transform:` property. The two are unrelated and only one of them moves anything.
    expect(codeOf(CSS)).not.toMatch(/(?<![-\w])transform\s*:/)
    // Every element here is display-only, so `:focus-visible` would have no subject — and
    // `outline: none` appears nowhere in any of its four spellings.
    expect(codeOf(CSS)).not.toMatch(/outline\s*:\s*(none|0|0px|hidden)\b/)
  })

  it('declares no colour outside the two text tiers DESIGN.md:423 names (AC 33)', () => {
    // The panel spends `--negative` through `Badge`, never here — which is what makes its absence
    // from `CALM_STYLESHEETS` a SCOPE ruling rather than a loophole
    // (`token-usage.test.ts:1002-1021` says so naming this story).
    //
    // EVERY `color:` declaration is collected, whatever its value — the c4-10 review found the
    // first draft matching only `color: var(...)`, so a literal `color: #ff0000` matched nothing
    // and passed. With the value unconstrained, the exact-equality below IS the firing half: any
    // third declaration, var() or literal, enters the list and fails it.
    const colours = (codeOf(CSS).match(/(?<![-\w])color:\s*[^;]+/g) ?? [])
      .map((declaration) => declaration.trim())
      .sort()
    expect(colours).toEqual(['color: var(--text-secondary)', 'color: var(--text-tertiary)'])
    expect(codeOf(CSS)).not.toMatch(/--negative|--caution|--positive/)
    // …and no colour LITERAL in any property: stylelint's token discipline owns the general rule,
    // and this restates it for the one file whose calm-surface scope ruling leans on it.
    expect(codeOf(CSS)).not.toMatch(/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(/)
  })

  it('uses this component’s own flat kebab-case prefix throughout (ruling 5)', () => {
    const classes = codeOf(CSS).match(/\.[a-z][a-z0-9-]*(?=[\s,:{])/g) ?? []
    // Non-vacuity: the file really does declare classes, so an empty match set cannot pass.
    expect(new Set(classes).size).toBeGreaterThanOrEqual(4)
    for (const cls of new Set(classes)) {
      expect(cls, `${cls} is not prefixed with the component`).toMatch(/^\.format-check(-[a-z]+)*$/)
    }
    // …and never the BEM double-underscore form stylelint refuses.
    expect(codeOf(CSS)).not.toMatch(/__/)
  })
})

describe('copy.ts is import-free and holds only authored words (AC 35, Q15)', () => {
  it('has no imports at all — the property that lets THIS file read it', () => {
    // `tests/` is `nodenext` and `src/` is `bundler`; `TS2835` is a RESOLUTION error raised
    // against the specifier, and it fires whether or not `import type` erases it at emit
    // (measured at c3-9: twelve errors with `npm test` green throughout).
    expect(codeOf(COPY)).not.toMatch(/^\s*import\b/m)
  })

  it('does NOT hold the backend’s sentences — those are data (Q15)', () => {
    // A copy owner that also held the wire's prose would make `COPY_MODULES`'s claim meaningless,
    // exactly as one holding card names would (decide-once rule 14, `DeckList/copy.ts:25-31`).
    for (const sentence of [
      'Every card is legal in',
      'Mainboard has',
      'No card exceeds the copy limit',
      'Rotation exposure cannot be checked',
      'is not legal in',
      'is banned in',
    ]) {
      expect(codeOf(COPY)).not.toContain(sentence)
    }
  })

  it('ships the six labels Q3 ruled, and not the mock’s false one', () => {
    expect(CHECK_LABELS).toEqual({
      legality: 'Legality',
      size: 'Maindeck size',
      copy_limit: 'Copy limit',
      sideboard: 'Sideboard',
      banned: 'Banned cards',
      rotation: 'Rotation exposure',
    })
    // `'Banned or restricted'` is a FALSE label: `deck_validator.py` reports a `restricted` card
    // through the LEGALITY row, deliberately and pinned, so it could never fire for one.
    expect(Object.values(CHECK_LABELS)).not.toContain('Banned or restricted')
    // …and no label is a FORMAT STRING, which is what the mock's first slot actually held (Q14).
    for (const label of Object.values(CHECK_LABELS)) {
      for (const format of ['standard', 'brawl', 'historic', 'commander', 'potato']) {
        expect(label.toLowerCase()).not.toContain(format)
      }
    }
  })

  it('keeps every authored string in READABLE case — uppercase is CSS', () => {
    // Storing 'PASS' here would uppercase twice (harmless) while destroying the readable form for
    // anyone reading the accessible name or copying the text (not harmless) — GROUP_LABELS' rule.
    for (const word of [...Object.values(STATUS_WORDS), ...Object.values(CHECK_LABELS)]) {
      expect(word).not.toBe(word.toUpperCase())
      expect(word.trim()).toBe(word)
      // Sentence case, no periods — `DECK_LIST_TITLE`'s voice.
      expect(word.endsWith('.')).toBe(false)
    }
    expect(FORMAT_CHECK_TITLE).toBe('Format check')
  })

  it('ships the three status WORDS, and none of the mock’s derived values (Q1)', () => {
    expect(STATUS_WORDS).toEqual({ pass: 'Pass', advisory: 'Advisory', violation: 'Violation' })
    // Computing `'60 / 60'` or `'no violations'` would be a construction rule written in
    // TypeScript — the fifth declared hole in c3-3's own rule guard, which `find_rule_violations`
    // states in writing it cannot see (`ui/README.md:1149`).
    const words = Object.values(STATUS_WORDS).join(' ')
    for (const invented of ['/', 'none', 'cards', 'legal']) {
      expect(words.toLowerCase()).not.toContain(invented)
    }
  })
})
