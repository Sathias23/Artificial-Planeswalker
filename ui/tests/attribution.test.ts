/**
 * The attribution sentence is `DESIGN.md` itself — the artefact, not a transcription of it.
 *
 * This is `tests/copy.test.ts`'s pattern pointed at a second artefact (story c2-10, AC 2, AC 3).
 * That file gates the state-panel copy against `EXPERIENCE.md`; this one gates the footer
 * attribution against `DESIGN.md`, because **a copy string is gated against the artefact that
 * WROTE it** and `EXPERIENCE.md` never wrote these words — its footer row (`:101`) is
 * behavioural. See `src/components/Footer/copy.ts` for that whole argument.
 *
 * WHY THIS FILE IS NAMED FOR THE OBLIGATION RATHER THAN THE COMPONENT (Q5, Brad 2026-07-30).
 * What it gates is a licensing condition of public release, not a component's strings, and
 * Epic 8's docs-attribution story (`epics-companion-app.md`, story c8-4) is the natural second
 * consumer of the same parse. `footer-copy.test.ts` would have named the first consumer and
 * mislabelled the contract.
 *
 * THREE THINGS ARE ASSERTED:
 *
 *   1. The sentence, re-joined from its parts IN SOURCE ORDER, is byte-for-byte the artefact's
 *      (AC 2, AC 3). One character of drift in either direction is red.
 *   2. The two hrefs are the ones the repository's `NOTICE` already publishes (AC 8), so the
 *      app and the licence documentation cannot point at two different pages for one obligation.
 *   3. Every link part's text is a substring of the sentence — nothing is authored here that
 *      `DESIGN.md` did not write, not even a link label.
 *
 * THE NON-VACUITY ANCHOR COMES FIRST, and it is the whole reason the parser THROWS rather than
 * returning `undefined`: every assertion below indexes into a parse of a prose artefact, and a
 * moved line, a renamed bullet or a second pair of quotes would otherwise yield an empty or
 * ambiguous read over which the byte-for-byte check asserts nothing while reporting green. c2-9's
 * review found exactly that shape — "a parser which silently tolerates a duplicate row is a
 * parser that stops checking" — so all three failure modes here are loud and named.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { ATTRIBUTION, sentenceOf } from '../src/components/Footer/copy.ts'

/**
 * The ONE place each path is written in this file. Both carry the loud-failure treatment the
 * anchor below applies: the UX artefacts are exported per run, so the dated directory is exactly
 * the kind of path that rots, and `tests/copy.test.ts` and `tests/tokens.test.ts` each pin their
 * own copy of the sibling for the same reason — separate contracts, separate constants.
 */
const DESIGN_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md',
    import.meta.url,
  ),
)
const NOTICE = fileURLToPath(new URL('../../NOTICE', import.meta.url))

/**
 * The `## Components` section of the artefact, and nothing outside it.
 *
 * SCOPED BY STRUCTURE, LOUDLY (review find, 2026-07-30): the first cut of this gate scanned the
 * WHOLE file for labelled bullets, so its bullet count moved — and its duplicate-label throw
 * could fire — on an edit to any unrelated section's lists. DESIGN.md writes labelled bullets
 * in four sections (Colors, Layout, Elevation, Components); only one of them is this gate's
 * contract. The heading is selected by name and the section ends at the next `## ` heading, so
 * a moved section travels with its heading and a DELETED heading is a named failure rather than
 * a silent fall-through to a whole-file scan.
 */
const componentsSectionOf = (raw: string): string => {
  const lines = raw.split(/\r?\n/)
  const start = lines.findIndex((line) => /^##\s+Components\s*$/.test(line))
  if (start === -1) {
    throw new Error(
      'DESIGN.md has no `## Components` heading — the attribution gate reads that section and ' +
        'cannot scope its parse without it. Find where the section moved; do not delete this gate.',
    )
  }
  const end = lines.findIndex((line, index) => index > start && /^##\s/.test(line))
  return lines.slice(start, end === -1 ? undefined : end).join('\n')
}

/**
 * Every `- **Label** …` component bullet in the given section, read as `label -> the whole line`.
 *
 * WHAT SELECTS A BULLET, and why it is not a line number. `DESIGN.md:375` is a line number today
 * and will not be one after the next edit above it. The structure is the bold label at the head
 * of a top-level list item, which is how the Components section names every one of its 24
 * entries — measured at `8c864f8`: 24 bullets in the section, 24 distinct labels.
 *
 * The regex is anchored at the line start and its capture excludes `*`, so the SECOND bold span
 * on the attribution line ("**Required on every surface…**") cannot be mistaken for a label.
 *
 * A DUPLICATED LABEL THROWS. `Map.set` would keep the last bullet and every assertion downstream
 * would still pass — the exact drift this gate exists to catch, hidden by the shape of Map.
 */
const readComponentBullets = (raw: string): Map<string, string> => {
  const bullets = new Map<string, string>()

  for (const line of raw.split(/\r?\n/)) {
    const labelled = /^-\s+\*\*([^*]+)\*\*/.exec(line)
    if (!labelled) continue
    const label = labelled[1].trim()
    if (bullets.has(label)) {
      throw new Error(
        `DESIGN.md writes two component bullets labelled "${label}" — the gate cannot know ` +
          'which one is the contract. De-duplicate the artefact before trusting this suite.',
      )
    }
    bullets.set(label, line)
  }

  return bullets
}

/**
 * The single quoted run on a bullet — the copy, as distinct from the token references around it.
 *
 * EXACTLY ONE, OR IT THROWS. A bullet that quotes two things has no unambiguous "the copy", and
 * a bullet that quotes none has had its copy deleted or reworded into prose. Both are the
 * artefact changing shape underneath the gate, and both must be a named failure rather than a
 * silent `undefined` that the byte-for-byte assertion then compares against.
 *
 * DECLARED CEILING, the way `copy.test.ts` declares its own: the capture is `"([^"]*)"`, so a
 * copy string that CONTAINS a double quote would truncate the read. If UX copy ever needs to
 * quote something, this function is the thing to extend, and this sentence is here so that
 * failure is a lookup rather than a hunt.
 */
const quotedCopyOf = (label: string, bullet: string | undefined): string => {
  if (bullet === undefined) {
    throw new Error(
      `DESIGN.md has no component bullet labelled "${label}". The attribution copy is a ` +
        'condition of public release (NFR-08) — find where it moved, do not delete this gate.',
    )
  }
  const runs = [...bullet.matchAll(/"([^"]*)"/g)].map((match) => match[1])
  if (runs.length !== 1) {
    throw new Error(
      `DESIGN.md's "${label}" bullet yields ${runs.length} quoted runs, not exactly one — ` +
        'the gate cannot tell which is the copy. Found: ' +
        JSON.stringify(runs) +
        (runs.length === 0
          ? ' (a 0-run read on a bullet that still visibly has its copy usually means an ' +
            'editor converted the straight double quotes to curly quotes — restore "…" in the ' +
            'artefact rather than hunting for deleted copy)'
          : ''),
    )
  }
  return runs[0]
}

const attributionFrom = (raw: string = readFileSync(DESIGN_MD, 'utf8')): string =>
  quotedCopyOf(
    'Footer attribution',
    readComponentBullets(componentsSectionOf(raw)).get('Footer attribution'),
  )

const artefactSentence = attributionFrom()
const notice = readFileSync(NOTICE, 'utf8')

describe('the footer attribution is DESIGN.md, byte for byte (AC 1, AC 2)', () => {
  it('parsed the artefact and found real copy in it (non-vacuity)', () => {
    // The three anchors, because an empty or accidental read is the failure this file is shaped
    // around. Asserted as VALUES rather than as "not empty": a parse that yielded some other
    // bullet's prose would satisfy a length check and nothing else here would notice. The count
    // is the COMPONENTS SECTION's, not the file's (review find, 2026-07-30) — an unrelated
    // section gaining a bullet must not turn a licensing gate red.
    // 24 until story c4-12, which added **Empty deck line** under "System presence & states" —
    // the treatment for a deck with zero cards, which DESIGN.md specified NOWHERE before that
    // commit. 25 until story 17.2, whose FR-18 home ruling (2026-08-22) added **History
    // popover** — the fifth nav pill's non-modal disclosure. This pin moving is the intended
    // signal: a Components bullet arriving is a design decision with a diff, and this is one
    // of the two places that says so out loud. 26 until story 17.5 added **Welcome** — the
    // no-active-deck surface (hero above the State panel, deck names as chips).
    expect(readComponentBullets(componentsSectionOf(readFileSync(DESIGN_MD, 'utf8'))).size).toBe(27)
    expect(artefactSentence.length).toBeGreaterThan(100)
    expect(artefactSentence.startsWith('Card data')).toBe(true)
    // And the module side: five parts, so neither loop below can pass by iterating nothing.
    expect(ATTRIBUTION).toHaveLength(5)
  })

  it('re-joins the parts in source order to the artefact sentence exactly (AC 3)', () => {
    // THE DELIVERABLE. Nothing else in this story matters if this is wrong, and it is asserted
    // against the artefact read at test time rather than against a string typed into this file.
    expect(sentenceOf()).toBe(artefactSentence)
  })

  it('writes no run the artefact did not write — link labels included', () => {
    // The join above proves the WHOLE reproduces the sentence; this proves each PART is drawn
    // from it. Together they leave no room for a link label invented to read better on screen,
    // which is the one edit this shape would otherwise make tempting.
    for (const part of ATTRIBUTION) {
      expect(artefactSentence).toContain(part.text)
    }
  })

  it('marks exactly the two runs that are links, and no others', () => {
    // Two links is a property of the SENTENCE (it names two organisations), so it is pinned
    // rather than left to whatever the parts list happens to carry.
    const links = ATTRIBUTION.filter((part) => part.href !== undefined)
    expect(links.map((part) => part.text)).toEqual([
      'Scryfall',
      'Wizards of the Coast Fan Content Policy',
    ])
  })
})

describe('the parser fails loudly rather than asserting nothing (the firing halves)', () => {
  it('throws when the Components section heading is gone', () => {
    // The scope anchor's own firing half: a re-organised artefact must fail by name, not fall
    // through to a whole-file scan that happens to keep working (review find, 2026-07-30).
    expect(() => attributionFrom('- **Footer attribution** — "Card data."')).toThrowError(
      /no `## Components` heading/,
    )
  })

  it('reads only the Components section — an identical label elsewhere is not a duplicate', () => {
    // The silent half of the scoping: DESIGN.md writes labelled bullets in four sections, and a
    // Colors bullet reusing a component's label is not an ambiguity in THIS gate's contract.
    expect(
      attributionFrom(
        '## Colors\n- **Footer attribution** — a swatch note.\n' +
          '## Components\n- **Footer attribution** — "Card data."',
      ),
    ).toBe('Card data.')
  })

  it('throws when the attribution bullet is gone', () => {
    expect(() =>
      attributionFrom('## Components\n- **Something else** — no attribution here.'),
    ).toThrowError(/no component bullet labelled "Footer attribution"/)
  })

  it('throws when the bullet yields no quoted run', () => {
    expect(() =>
      attributionFrom('## Components\n- **Footer attribution** — one quiet line, unquoted.'),
    ).toThrowError(/yields 0 quoted runs/)
  })

  it('throws when the bullet yields a second quoted run', () => {
    // The ambiguity a well-meaning artefact edit introduces: someone quotes a phrase for
    // emphasis on the same line, and a parser that took the FIRST match would silently keep
    // gating the right string until the day the order changed.
    expect(() =>
      attributionFrom(
        '## Components\n- **Footer attribution** — "Card data." and also "a second thing".',
      ),
    ).toThrowError(/yields 2 quoted runs/)
  })

  it('throws on a duplicated bullet label rather than last-writer-wins', () => {
    expect(() =>
      readComponentBullets('- **Footer attribution** — "One."\n- **Footer attribution** — "Two."'),
    ).toThrowError(/two component bullets labelled "Footer attribution"/)
  })

  it('reads two DIFFERENT labels as two bullets (the silent half)', () => {
    // The pair. Without this, a parser that threw on everything would pass every test above.
    expect(readComponentBullets('- **A** — "One."\n- **B** — "Two."').size).toBe(2)
  })

  it('does not mistake a second bold span on the line for a label', () => {
    // The real bullet ends with "**Required on every surface — …**". A label regex that was not
    // anchored would find it, and the map would gain a phantom entry whose "copy" is whatever
    // quotes followed it.
    const parsed = readComponentBullets(
      '- **Footer attribution** — "Words." **Required on every surface.**',
    )
    expect([...parsed.keys()]).toEqual(['Footer attribution'])
  })
})

describe('the hrefs are the NOTICE file’s, not new ones (AC 8)', () => {
  it('is reading a real NOTICE (non-vacuity)', () => {
    expect(notice).toContain('Wizards of the Coast Fan Content Policy')
    expect(notice.length).toBeGreaterThan(500)
  })

  it('publishes the same URL for each obligation as the licence documentation', () => {
    // The app and the docs cannot drift into pointing at two different pages for one licensing
    // obligation. This is the assertion that makes `NOTICE` the single source for both.
    // BOUNDED, not a bare substring (review find, 2026-07-30): `toContain` would pass while the
    // app's URL is a PREFIX of a longer, different URL in NOTICE — the exact drift this test
    // exists to prevent. The lookahead requires the match to end where a URL path could not
    // simply continue.
    for (const part of ATTRIBUTION) {
      if (part.href === undefined) continue
      const escaped = part.href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      expect(
        new RegExp(`${escaped}(?![\\w/-])`).test(notice),
        `${part.href} is in NOTICE only as a prefix of a longer URL, or not at all`,
      ).toBe(true)
    }
  })

  it('uses https for both, and neither ends in a fetchable asset', () => {
    // The offline guarantee restated as an assertion (NFR-06, AC 9): these are hrefs a human
    // clicks, never a request the app makes. An href ending in `.pdf` or `.css` would also turn
    // `fonts.test.ts`'s R3 red, and this is the earlier, clearer failure.
    for (const part of ATTRIBUTION) {
      if (part.href === undefined) continue
      expect(part.href.startsWith('https://')).toBe(true)
      expect(part.href).not.toMatch(/\.(woff2?|ttf|otf|eot|css|m?js|pdf)(\?|#|$)/i)
    }
  })
})
