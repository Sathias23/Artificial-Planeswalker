/**
 * UX-DR33's voice rules, as a gate (story c2-9, AC 6, AC 13).
 *
 * "No exclamation marks, no emoji, no mascot; never blame — 'something went wrong' is banned"
 * is a rule about USER-FACING COPY, and the measurement that shaped this file is that a naive
 * repo-wide ban on either string **fails on the day it is written, against the wrong files**:
 *
 *   `"something went wrong"` already appears TWICE inside `ui/src` — `api/openapi.json:90` and
 *   `api/types.d.ts:46` — in both cases QUOTING THE BAN ITSELF, inside generated files no
 *   author may hand-edit.
 *
 *   `!` is an OPERATOR in nine of the eleven modules under `src/components/`.
 *
 * ================= HOW BOTH ARE OUT OF SCOPE **BY CONSTRUCTION** =======================
 *
 * Not by a special case listing today's two files — that list would be wrong the moment a third
 * arrived. This guard reads the TypeScript **AST**, not the text:
 *
 *   A COMMENT IS NOT A STRING NODE. `types.d.ts:46` lives in a JSDoc block, and the parser
 *   simply never yields it. The same is true of every future doc comment that quotes the rule,
 *   including this file's own header, which contains the banned phrase four times.
 *
 *   `!` AS AN OPERATOR IS A `PrefixUnaryExpression`, not a `StringLiteral`. `!filled(x)` is
 *   invisible here for the same reason, permanently, in files nobody has written yet.
 *
 *   `openapi.json` IS NOT SCANNED AT ALL. It is generated from the backend's own
 *   `app.openapi()` (AD-12) and is not a source of rendered copy; `wire-contract.test.ts` owns
 *   it. Stated so that "the guard skips it" is a scope decision on the record and not a hole.
 *
 * `typescript` is already a direct devDependency (it IS `npm run typecheck`), so this adds no
 * dependency — AC 24 holds.
 *
 * ================= THE TWO HALVES, BECAUSE ONE IS WORTHLESS WITHOUT THE OTHER ===========
 *
 * c2-8's data-ink guard is the precedent, and its review round is the reason this is written as
 * a pair: a rule about what copy may CONTAIN is worthless if copy can live anywhere, and a rule
 * about where copy may LIVE is worthless if it is never read.
 *
 *   THE FILE HALF — user-facing prose may only live in an enumerated, git-checked set of copy
 *   modules. A sentence introduced anywhere else fails, naming the module it belongs in.
 *
 *   THE CONTENT HALF — EVERY string literal in EVERY module is checked, prose-shaped or not.
 *   Deliberately NOT gated behind the prose detector, and that was MEASURED rather than
 *   reasoned: a one-word-plus-pictograph string matches no prose pattern at all, and the first
 *   draft of this guard let exactly that through. The ban costs nothing to apply widely, and
 *   the residue it closes is real — a word table of single words is where a mascot would sit.
 *
 * ================= WHAT THIS GUARD DOES **NOT** DECIDE, DECLARED ========================
 *
 * The same division of labour `src/styles/surfaces.ts` and `findAccentDimOnOverlay` declare for
 * their own halves. Five residues, all REVIEW'S (4 and 5 were undeclared until the review of
 * 2026-07-29 — a guard limit that is not written down reads as coverage):
 *
 *   1. WHETHER A SENTENCE IS SECOND-PERSON AND BLAMELESS. Not statically decidable, and the
 *      most important half of UX-DR33. A reviewer of c2-10, c4-3, c4-12 and c6-6 must READ the
 *      copy; this file will not have read it.
 *   2. COPY ASSEMBLED FROM SINGLE WORDS AT RUNTIME. `describeManaCost` builds "2 generic, white
 *      or blue" out of a word table — no entry of which is prose-shaped. That module is in
 *      `COPY_MODULES` deliberately (so the content half covers its table), but a NEW module
 *      doing the same thing would not be detected by the file half. The realistic mitigation is
 *      that the accessible-name attribute it feeds IS detected wherever it is a literal.
 *   3. A STRING REACHING AN `aria-label` THROUGH AN EXPRESSION. `aria-label={describe(x)}` is a
 *      call, not a literal; the value is only knowable at runtime. Component tests assert the
 *      rendered result instead — `StatePanel.test.tsx` does exactly that over the real DOM.
 *   4. THE PROSE DETECTOR IS LATIN-SCRIPT. Two space-separated `A-Za-z` words is the shape; a
 *      sentence in a non-Latin script matches nothing. This product's copy contract
 *      (EXPERIENCE.md) is English, so the residue is theoretical until a localisation story
 *      exists — which would own widening the detector, not this file.
 *   5. A SINGLE WORD RENDERED AS A JSX EXPRESSION CHILD. `<p>{'Loading'}</p>` is a string
 *      literal in no user-facing attribute that fails the two-word shape, so the file half
 *      never collects it. The content half still bans its characters; whether the word belongs
 *      in a copy module is review's, like residue 2.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

// git, not readdir — the authority every other guard in this project uses, so an untracked
// module cannot pass vacuously and a committed one cannot escape CI.
const shippedModules = execFileSync('git', ['ls-files', 'src/*.ts', 'src/*.tsx'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((file) => !/\.test\.tsx?$/.test(file))

/**
 * Where user-facing copy may live -> why that module is a copy owner.
 *
 * A later story with a sentence in it — c2-10's attribution, c4-3's "Unknown card", c4-12's
 * empty-deck line, c6-6's empty push — ADDS AN ENTRY HERE with its reason, rather than
 * inventing a second mechanism. That is decide-once ruling #1 of story c2-9.
 */
const COPY_MODULES: Map<string, string> = new Map([
  [
    'src/components/StatePanel/copy.ts',
    'the state-panel copy, and the ONLY place it lives — asserted byte-for-byte against ' +
      'EXPERIENCE.md by tests/copy.test.ts (story c2-9).',
  ],
  [
    'src/components/AppShell/AppShell.tsx',
    'the placeholder line for each empty region, each naming the story that replaces it, plus ' +
      'the product kicker and the h1 fallback (story c2-1, AC 21). Every one of these is copy ' +
      'with a scheduled death.',
  ],
  [
    'src/components/ManaCost/parse.ts',
    'the word table `describeManaCost` speaks a mana cost from — "2 generic, white or blue" ' +
      '(story c2-8, UX-DR18). Prose assembled from single words, which is why it is listed ' +
      'DELIBERATELY rather than caught: see residue 2 in this file header.',
  ],
])

/**
 * Attributes whose value is read aloud, whatever its shape.
 *
 * This IS an enumerated list — the one shape the epic's standing rule warns about — because the
 * ARIA family genuinely cannot be keyed structurally: `aria-live` and `aria-hidden` carry
 * single-token values that are chrome, so `aria-*` as a family would redden every component.
 * The mitigation is stated instead of pretended away: the list carries every string-valued
 * ARIA attribute of the current spec (the braille and valuetext ones were absent until the
 * review of 2026-07-29 found the gap), and a new read-aloud attribute joining the platform
 * must be added HERE, which review checks the day a story first uses it.
 */
const USER_FACING_ATTRIBUTE = new Set([
  'aria-label',
  'aria-description',
  'aria-roledescription',
  'aria-placeholder',
  'aria-valuetext',
  'aria-braillelabel',
  'aria-brailleroledescription',
  'alt',
  'title',
  'placeholder',
])

/**
 * PROSE, defined structurally: two or more space-separated words.
 *
 * Every chrome string this codebase produces is a single token by rules that are themselves
 * gated — `selector-class-pattern` makes class names kebab-case with no spaces, roles and
 * token names are single words, module specifiers are paths. A sentence has spaces between
 * words. That is the whole discriminator, and it is stated rather than tuned.
 */
const PROSE = /[A-Za-z][A-Za-z'’-]*\s+[A-Za-z][A-Za-z'’-]*/

interface FoundString {
  file: string
  line: number
  text: string
  /** Why it was collected — which makes the two halves able to ask different questions. */
  source: 'jsx-text' | 'attribute' | 'prose' | 'any-string'
}

/** Attributes whose value is a CLASS NAME, which is chrome by construction — see below. */
const CLASS_ATTRIBUTE = new Set(['className', 'class'])

/** Every literal string node in a file, whatever its position. The CONTENT half reads this. */
const allStringsIn = (file: string, source: string): FoundString[] =>
  walk(file, source, { includeEverything: true })

/**
 * Every string a reader could plausibly see: JSX text, a user-facing attribute, or prose.
 *
 * Template literals contribute their literal SPANS: `` `Phyrexian ${body}` `` yields
 * "Phyrexian ". The interpolated part is a runtime value and is residue 3.
 */
const userFacingStringsIn = (file: string, source: string): FoundString[] =>
  walk(file, source, { includeEverything: false })

function walk(
  file: string,
  source: string,
  { includeEverything }: { includeEverything: boolean },
): FoundString[] {
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true)
  const found: FoundString[] = []

  const at = (node: ts.Node) => tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1

  const visit = (node: ts.Node): void => {
    // A `className` value is CHROME BY CONSTRUCTION, and skipping the whole attribute subtree
    // is what makes that structural rather than a guess about the string. MEASURED, not
    // anticipated: the first version of this guard flagged `` `badge badge-${shown}` ``,
    // `` `mana-pip mana-pip-${…}` `` and `` `stat-chip-delta stat-chip-delta-${tone}` `` as
    // prose, because two space-separated class tokens look exactly like two words. Sniffing the
    // string instead ("is it all kebab-case?") would wave through a lowercase sentence like
    // 'ask your agent'. Class names have their own gate — stylelint's `selector-class-pattern`
    // — so nothing is left unpoliced by excluding them here. The CONTENT half still reads them.
    if (
      !includeEverything &&
      ts.isJsxAttribute(node) &&
      ts.isIdentifier(node.name) &&
      CLASS_ATTRIBUTE.has(node.name.text)
    ) {
      return
    }

    if (ts.isJsxText(node)) {
      const text = node.text.trim()
      if (/[A-Za-z]/.test(text)) {
        found.push({ file, line: at(node), text, source: 'jsx-text' })
      } else if (includeEverything && text !== '') {
        // LETTERLESS JSX TEXT IS STILL ON SCREEN. `<p>🎉</p>` and `<p>!</p>` contain no letter,
        // so the file half's prose shapes rightly ignore them — but the first version of this
        // walker yielded them to NEITHER half, which was a spelling of the evasion this guard
        // exists for, found by the review of 2026-07-29. The content half reads them.
        found.push({ file, line: at(node), text, source: 'any-string' })
      }
    } else if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node)
    ) {
      // A module specifier is a path, never copy. Excluded by its POSITION in the tree rather
      // than by looking at the string, so `import './Panel.css'` and a same-named copy string
      // are told apart correctly.
      const parent = node.parent
      const isSpecifier =
        (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) &&
        parent.moduleSpecifier === node

      if (!isSpecifier) {
        const attribute =
          ts.isJsxAttribute(parent) && ts.isIdentifier(parent.name)
            ? parent.name.text
            : ts.isJsxAttribute(parent.parent) && ts.isIdentifier(parent.parent.name)
              ? parent.parent.name.text
              : undefined

        if (attribute !== undefined && USER_FACING_ATTRIBUTE.has(attribute)) {
          found.push({ file, line: at(node), text: node.text, source: 'attribute' })
        } else if (PROSE.test(node.text)) {
          found.push({ file, line: at(node), text: node.text, source: 'prose' })
        } else if (includeEverything && node.text !== '') {
          found.push({ file, line: at(node), text: node.text, source: 'any-string' })
        }
      }
    }
    ts.forEachChild(node, visit)
  }

  visit(tree)
  return found
}

/** THE FILE HALF: prose outside a declared copy module. */
const findCopyOutsideACopyModule = (
  files: string[],
  read: (file: string) => string = sourceOf,
  owners: Map<string, string> = COPY_MODULES,
): string[] =>
  files
    .filter((file) => !owners.has(file))
    .flatMap((file) =>
      userFacingStringsIn(file, read(file)).map(
        (hit) =>
          `${hit.file}:${hit.line} renders user-facing copy: ${JSON.stringify(hit.text)}. ` +
          `Every sentence the user reads lives in a declared copy module, so UX-DR33's voice ` +
          `rules have one address to point at (story c2-9, AC 13). Move it into one of ` +
          `[${[...owners.keys()].join(', ')}], or add this file to COPY_MODULES in ` +
          `tests/copy-rules.test.ts with the reason it owns copy.`,
      ),
    )

/**
 * THE CONTENT HALF: the bans, keyed by CHARACTER FAMILY wherever a family exists.
 *
 * "Ban the family, never enumerate members" is this epic's standing review finding in five
 * consecutive stories, and an emoji is the case that proves it — there is no list of emoji you
 * can write down that is still complete next year.
 *
 *   EMOJI -> `\p{Extended_Pictographic}`, the Unicode property itself. Every pictograph,
 *   including ones assigned after this was written, with no list to maintain.
 *
 *   EXCLAMATION MARK -> NFKC-normalise, then look for `!`. Unicode's own compatibility
 *   decompositions do the enumerating: `！` (FF01), `︕` (FE15) and `﹗` (FE57) all fold to `!`,
 *   `‼` (203C) folds to `!!` and `⁉` (2049) to `!?`. A hand-written list of those five is
 *   exactly the kind of list c2-8's review round rejected; this derives them.
 */
const BANNED: { name: string; hit: (text: string) => boolean; why: string }[] = [
  {
    name: 'an exclamation mark',
    hit: (text) => text.normalize('NFKC').includes('!'),
    why: 'UX-DR33: calm, terminal-literate copy. The full-width and compatibility spellings fold to `!` under NFKC and are caught by the same check.',
  },
  {
    name: 'an emoji or pictograph',
    hit: (text) => /\p{Extended_Pictographic}/u.test(text),
    why: 'UX-DR33: no emoji, no mascot. Keyed on the Unicode property, so a pictograph nobody listed is still caught.',
  },
  {
    name: 'the banned phrase "something went wrong"',
    hit: (text) => /something\s+went\s+wrong/i.test(text),
    why: 'UX-DR33: never blame, and never be vague. Name what happened and give the next action.',
  },
]

const findBannedCopy = (files: string[], read: (file: string) => string = sourceOf): string[] =>
  files.flatMap((file) =>
    allStringsIn(file, read(file)).flatMap((hit) =>
      BANNED.filter((ban) => ban.hit(hit.text)).map(
        (ban) =>
          `${hit.file}:${hit.line} contains ${ban.name}: ${JSON.stringify(hit.text)}. ${ban.why}`,
      ),
    ),
  )

// ---------------------------------------------------------------------------------------

describe('user-facing copy lives in one place (AC 13, the file half)', () => {
  it('is reading real modules and finding the real copy in them (non-vacuity)', () => {
    // Three anchors, because an empty scan is the failure this whole file is shaped around.
    expect(shippedModules.length).toBeGreaterThan(10)
    expect(shippedModules).toContain('src/components/StatePanel/copy.ts')

    for (const [file, reason] of COPY_MODULES) {
      expect(shippedModules, `COPY_MODULES names ${file}, which git does not track`).toContain(file)
      expect(reason.length, `${file} is listed with no reason`).toBeGreaterThan(40)
      expect(
        allStringsIn(file, sourceOf(file)).length,
        `${file} is declared a copy module but the extractor found no strings in it`,
      ).toBeGreaterThan(3)
    }

    // And the extractor really sees the artefact copy, not merely "some strings".
    expect(
      userFacingStringsIn(
        'src/components/StatePanel/copy.ts',
        sourceOf('src/components/StatePanel/copy.ts'),
      ).map((hit) => hit.text),
    ).toContain('No deck on the glass.')
    // …and the CONTENT half's extractor reaches strings the prose detector never would: the
    // word table `describeManaCost` speaks a cost from is entirely single words.
    expect(
      allStringsIn('src/components/ManaCost/parse.ts', sourceOf('src/components/ManaCost/parse.ts'))
        .length,
    ).toBeGreaterThan(10)
  })

  it('finds no user-facing copy outside a declared copy module', () => {
    expect(findCopyOutsideACopyModule(shippedModules)).toEqual([])
  })
})

describe('what that copy may not contain (AC 6, AC 13, the content half)', () => {
  it('ships no exclamation mark, emoji or blame anywhere in src', () => {
    // Over EVERY module, not only the copy owners: the ban costs nothing to apply widely, and
    // the generated `types.d.ts` is included deliberately — its occurrence of the banned phrase
    // is in a JSDoc comment, which the AST never yields, so this scan proves that claim rather
    // than assuming it.
    expect(findBannedCopy(shippedModules)).toEqual([])
  })

  it('reads the generated wire types without tripping on the ban they QUOTE', () => {
    // The measurement this file was designed around, asserted rather than described: the phrase
    // IS in that file, and the guard is silent because it is in a comment.
    expect(sourceOf('src/api/types.d.ts').toLowerCase()).toContain('something went wrong')
    expect(findBannedCopy(['src/api/types.d.ts'])).toEqual([])
  })
})

describe('the guard itself fires, and stays silent where it should (the other half)', () => {
  const OWNERS = new Map([['src/copy.ts', 'the fixture copy module, for these proofs.']])
  const probeFile = (source: string, file = 'src/thing.tsx') =>
    findCopyOutsideACopyModule([file], () => source, OWNERS)
  const probeBan = (source: string, file = 'src/thing.tsx') => findBannedCopy([file], () => source)

  it.each([
    ['a sentence in JSX text', 'export const A = () => <p>Ask your agent for a deck.</p>'],
    ['a sentence in a string literal', "export const message = 'Ask your agent for a deck.'"],
    ['a sentence in a template literal', 'export const m = `Ask your agent for a deck.`'],
    ['a sentence in a template span', 'export const m = (n: string) => `Ask your agent for ${n}`'],
    // A ONE-WORD accessible name, which the prose detector alone would miss entirely. This is
    // why the attribute list exists beside it.
    ['a one-word accessible name', 'export const A = () => <span aria-label="Loading" />'],
    ['an alt text', 'export const A = () => <span alt="Chart" />'],
    // One of the read-aloud attributes the list was missing until the review of 2026-07-29.
    ['a one-word aria-valuetext', 'export const A = () => <div aria-valuetext="High" />'],
  ])('catches %s outside a copy module', (_label, source) => {
    const findings = probeFile(source)
    expect(findings).toHaveLength(1)
    // The house rule: the message names the fix.
    expect(findings[0]).toContain('COPY_MODULES')
  })

  it('says nothing about the chrome strings every component is made of (the silent half)', () => {
    // If any of these tripped, the guard would be unusable and would be disabled — which is how
    // a gate becomes a comment. Each is a real shape from a real component in this repo.
    expect(
      probeFile(`
        import './Panel.css'
        import { filled } from '../filled'
        export const A = ({ live }: { live?: boolean }) => {
          const classes = ['panel']
          if (live) classes.push('panel-live')
          // The three class-name TEMPLATES this guard was measured against: two space-separated
          // class tokens read as two words to any prose detector, and all three shipped already.
          return (
            <section className={\`panel panel-\${live ? 'live' : 'rest'}\`} role="region">
              <span className={classes.join(' ')} />
              <span className="stat-chip-delta stat-chip-delta-positive" />
            </section>
          )
        }
      `),
    ).toEqual([])
  })

  it('says nothing about prose INSIDE a declared copy module', () => {
    expect(
      findCopyOutsideACopyModule(
        ['src/copy.ts'],
        () => "export const m = 'Ask your agent for a deck.'",
        OWNERS,
      ),
    ).toEqual([])
  })

  it('never reads a COMMENT as copy — the measured reason this uses the AST', () => {
    // Both bans, quoted in a comment, in both comment syntaxes. Text-based guards fail here,
    // and this is the assertion that says the AST choice is load-bearing rather than tidy.
    const source = `
      /** Never say "something went wrong"! And no emoji 🎉 in copy. */
      // Also banned: "Something Went Wrong"!
      export const ok = 'panel-live'
    `
    expect(probeFile(source)).toEqual([])
    expect(probeBan(source)).toEqual([])
  })

  it('never reads the `!` OPERATOR as an exclamation mark', () => {
    // Nine of eleven modules under src/components/ use `!` as an operator. A text-based ban
    // fails on all nine the day it is written.
    expect(probeBan('export const a = (x: unknown) => !x && ![].length ? 1 : 2')).toEqual([])
  })

  it.each([
    ['a plain exclamation mark', "export const m = 'Deck loaded!'", 'exclamation'],
    // THE FAMILY PROBES: three spellings the ban never lists, folded by NFKC rather than by a
    // hand-written table.
    ['a full-width exclamation mark', "export const m = 'Deck loaded！'", 'exclamation'],
    ['a double exclamation mark', "export const m = 'Deck loaded‼'", 'exclamation'],
    ['an interrobang', "export const m = 'Deck loaded⁉'", 'exclamation'],
    // …and an emoji the ban never lists, from a block assigned long after most emoji lists.
    ['an emoji', "export const m = 'Deck loaded \u{1FAE0}'", 'emoji'],
    ['a mascot pictograph', "export const m = 'Sorry \u{1F63F}'", 'emoji'],
    [
      'the banned phrase',
      "export const m = 'Sorry, something Went   wrong.'",
      'something went wrong',
    ],
    // LETTERLESS JSX TEXT (review 2026-07-29): not a string-literal node and no `A-Za-z`, so
    // the first walker yielded these to neither half. The content half now reads them.
    ['an emoji as bare JSX text', 'export const A = () => <p>🎉</p>', 'emoji'],
    ['an exclamation mark as bare JSX text', 'export const A = () => <p>!</p>', 'exclamation'],
    // …and the enumerated-attribute gap the same review found: a read-aloud ARIA attribute the
    // original list never named, carrying a banned character in a single-word value.
    [
      'an emoji in an aria-valuetext',
      'export const A = () => <div aria-valuetext="high🔥" />',
      'emoji',
    ],
  ])('catches %s', (_label, source, expected) => {
    const findings = probeBan(source)
    // `toBeGreaterThan(0)` rather than an exact count, and the reason is itself a measurement:
    // `‼` and `⁉` are BOTH exclamation marks under NFKC and Extended_Pictographic characters, so
    // they legitimately trip two bans at once. Pinning the count would have made the guard being
    // right look like a defect. The silent-half tests above are what keep this honest.
    expect(findings.length).toBeGreaterThan(0)
    expect(findings.join(' | ')).toContain(expected)
  })

  it('catches a banned character in a SINGLE-WORD entry, which no prose detector sees', () => {
    // The MEASURED reason the content half is not gated behind the prose detector.
    const source = "export const W = 'white\u{1F7E1}'"
    const findings = findBannedCopy(['src/parse.ts'], () => source)
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain('emoji')
    // …and the file half is correctly SILENT on it, which is what makes the pair necessary
    // rather than redundant: neither half would have caught this alone.
    expect(findCopyOutsideACopyModule(['src/parse.ts'], () => source, OWNERS)).toEqual([])
  })
})
