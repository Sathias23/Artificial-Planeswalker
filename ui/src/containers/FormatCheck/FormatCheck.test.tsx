/**
 * The format check panel (story c4-10, AC 4–6, 14–20, 22–33).
 *
 * ⚠️ **Role queries here are scoped through the panel, never `getByRole('banner')`.** `aria-query`
 * maps `<header>` to `banner` unconditionally, so every titled `Panel` is a phantom `banner` in
 * jsdom and none in a browser. This panel takes the jsdom count from **five to six**; the eye-check
 * reports Chrome's own number beside it.
 *
 * Every fixture comes from `src/state/formatCheck.fixtures.ts`, where each one declares
 * whether it is a verified real response or synthetic and how it was produced (AC 26).
 */

import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import type { FormatCheckReport } from '../../api/schema'
import { BADGE_TONES } from '../../components/Badge/tones'
import { loadFormatCheck, resetFormatCheckState } from '../../state/formatCheck'
import {
  ALL_PASS_REPORT,
  BRAWL_VIOLATION_REPORT,
  FORMATLESS_REPORT,
  MULTI_VIOLATION_REPORT,
  NO_FORMAT_REPORT,
  ONE_CARD_REPORT,
  SINGLETON_VIOLATION_REPORT,
} from '../../state/formatCheck.fixtures'
import { FormatCheck } from './FormatCheck'
import { CHECK_LABELS, FORMAT_CHECK_TITLE, STATUS_WORDS } from './copy'

/** Put a report in the store the way production does — through the slice's own action. */
const showing = async (report: FormatCheckReport) => {
  await loadFormatCheck('deck-1', () => Promise.resolve({ kind: 'report', report }))
  return render(<FormatCheck />)
}

const panel = () => screen.getByRole('region', { name: FORMAT_CHECK_TITLE })

const rowsOf = (report: FormatCheckReport) => report.rows.map((row) => row.check)

beforeEach(() => {
  resetFormatCheckState()
})

describe('the panel is a titled Panel with no verdict in its chrome (AC 4, Q4)', () => {
  it('renders a named region whose h2 is the title', async () => {
    await showing(ALL_PASS_REPORT)

    expect(panel()).toBeVisible()
    expect(
      within(panel()).getByRole('heading', { level: 2, name: FORMAT_CHECK_TITLE }),
    ).toBeVisible()
  })

  it('renders NO count and NO badge in the panel header (Q4)', async () => {
    await showing(BRAWL_VIOLATION_REPORT)

    // `Panel`'s `badges` slot has never been used by any component in this app, which makes it
    // easy to overlook rather than safe: it is a third venue for the same synthesized verdict.
    // The container is unconditional in `Panel.css`, so the assertion is on its EMPTINESS.
    const badgeSlot = panel().querySelector('.panel-badges')
    expect(badgeSlot).not.toBeNull()
    expect(badgeSlot!.childNodes).toHaveLength(0)
    expect(panel().querySelector('.panel-count')).toBeNull()
  })

  it('is at level="default" — not the overlay CardDetail uses', async () => {
    await showing(ALL_PASS_REPORT)

    expect(panel().classList.contains('panel-overlay')).toBe(false)
  })
})

describe('exactly six rows, in the payload’s order, never sorted (AC 14, AC 5, Q9)', () => {
  it('renders one list item per row, six of them', async () => {
    await showing(ALL_PASS_REPORT)

    // SCOPED to this panel (AC 5). `App.test.tsx:647` predicted this story by name as the one
    // that would break a document-wide `getAllByRole('listitem')`; the scoping it added at c4-7
    // holds, and this is the panel's own count beside the grid's and the deck list's.
    expect(within(panel()).getAllByRole('listitem')).toHaveLength(6)
  })

  it('follows the PAYLOAD’s order, not a local list — proved with a shuffled payload', async () => {
    // The assertion that would notice a `CHECK_ORDER` copied into TypeScript. `CHECK_ORDER` is
    // declared in `deck_validator.py:487-494` and pinned on both sides there; a panel that
    // sorted would be re-deciding something the backend already decided, and would keep passing
    // every "six rows" test while silently disagreeing with the contract.
    const shuffled: FormatCheckReport = {
      ...ALL_PASS_REPORT,
      rows: [...ALL_PASS_REPORT.rows].reverse(),
    }
    await showing(shuffled)

    const rendered = within(panel())
      .getAllByRole('listitem')
      .map((item) => item.querySelector('.format-check-label')?.textContent)
    expect(rendered).toEqual(rowsOf(shuffled).map((check) => CHECK_LABELS[check]))
    // …and it is genuinely the reverse of the declared order, so the fixture is not vacuous.
    expect(rendered[0]).toBe(CHECK_LABELS.rotation)
    expect(rendered[5]).toBe(CHECK_LABELS.legality)
  })

  it('renders the six labels, and NOT the machine tokens (AC 15)', async () => {
    await showing(ALL_PASS_REPORT)

    for (const check of rowsOf(ALL_PASS_REPORT)) {
      expect(within(panel()).getByText(CHECK_LABELS[check])).toBeVisible()
    }
    // The wire's tokens never reach the glass. `copy_limit` is the one that would be visible as
    // itself if the map were bypassed — it is the only token with an underscore in it.
    expect(panel().textContent).not.toContain('copy_limit')
    expect(panel().textContent).not.toContain('format_recognized')
  })

  it('does NOT ship the mock’s `Banned or restricted` label (Q3, AC 15)', async () => {
    await showing(ALL_PASS_REPORT)

    // A false label: `deck_validator.py:433-452` reports a `restricted` card through the LEGALITY
    // row, deliberately and pinned on the Python side, so a row labelled "Banned or restricted"
    // could never fire for a restricted card in any format.
    expect(panel().textContent).not.toContain('Banned or restricted')
    expect(within(panel()).getByText('Banned cards')).toBeVisible()
  })
})

describe('the badge carries the status WORD, and the tone rides beside it (AC 16, 17, 31)', () => {
  it('renders the three status words rather than the mock’s derived values (Q1)', async () => {
    await showing(MULTI_VIOLATION_REPORT)

    expect(within(panel()).getAllByText(STATUS_WORDS.violation)).toHaveLength(3)
    expect(within(panel()).getAllByText(STATUS_WORDS.pass)).toHaveLength(2)
    expect(within(panel()).getAllByText(STATUS_WORDS.advisory)).toHaveLength(1)

    // The mock's six derived values do not ship. Computing them would be a construction rule
    // written in TypeScript, which `find_rule_violations` declares in writing it cannot see.
    for (const invented of ['60 / 60', 'no violations', '11 cards', '15 / 15']) {
      expect(panel().textContent).not.toContain(invented)
    }
  })

  it('maps pass→positive, advisory→caution, violation→negative (AC 17)', async () => {
    await showing(MULTI_VIOLATION_REPORT)

    const toneOf = (check: string) =>
      within(panel())
        .getAllByRole('listitem')
        .find(
          (item) =>
            item.querySelector('.format-check-label')?.textContent ===
            CHECK_LABELS[check as keyof typeof CHECK_LABELS],
        )
        ?.querySelector('.badge')?.className

    expect(toneOf('size')).toContain('badge-positive')
    expect(toneOf('rotation')).toContain('badge-caution')
    expect(toneOf('banned')).toContain('badge-negative')
  })

  it('never produces a fourth tone, and NEVER `neutral` (AC 17)', async () => {
    // The live WCAG constraint `ui/README.md:1394-1397` records for this story by name: neutral's
    // `--border-strong` hairline is 1.75:1 on `--surface-panel` (re-measured — the recorded
    // 1.89:1 is the `--surface-base` figure), under 1.4.11's 3:1 non-text floor. The four
    // semantic borders are 9.19 / 6.75 / 10.59 / 6.21:1 and are fine. So a state distinguished by
    // TONE is safe and a state distinguished by the NEUTRAL BORDER is not.
    const seen = new Set<string>()
    for (const report of [ALL_PASS_REPORT, MULTI_VIOLATION_REPORT, FORMATLESS_REPORT]) {
      resetFormatCheckState()
      const view = await showing(report)
      for (const badge of view.container.querySelectorAll('.badge')) {
        for (const cls of badge.classList) if (cls.startsWith('badge-')) seen.add(cls)
      }
      view.unmount()
    }

    expect([...seen].sort()).toEqual(['badge-caution', 'badge-negative', 'badge-positive'])
    expect(seen.has('badge-neutral')).toBe(false)
    // …and the tones that DO ship are real members of the primitive's own list, so a typo could
    // not have produced an unstyled pill that these assertions would still accept.
    for (const cls of seen) {
      expect(BADGE_TONES as readonly string[]).toContain(cls.replace('badge-', ''))
    }
  })

  it('never renders an EMPTY badge — `Badge` would silently drop the pill', async () => {
    // `Badge` returns `null` for empty content ("a bordered, washed, empty pill — visible chrome
    // announcing nothing"), so a blank status word would leave a bare label row with no signal at
    // all and nothing would fail. Six rows, six pills, every one with text.
    await showing(ALL_PASS_REPORT)

    const badges = panel().querySelectorAll('.badge')
    expect(badges).toHaveLength(6)
    for (const badge of badges) expect(badge.textContent?.trim()).not.toBe('')
  })

  it('says it in WORDS, so colour is never the sole carrier (AC 31, UX-DR26/29)', async () => {
    await showing(BRAWL_VIOLATION_REPORT)

    // Asserting the WORD, not the class: the row must read the same in greyscale. The class-based
    // assertions above prove the tone map; this one proves the tone is never the only signal.
    const legality = within(panel())
      .getAllByRole('listitem')
      .find(
        (item) => item.querySelector('.format-check-label')?.textContent === CHECK_LABELS.legality,
      )
    expect(legality?.textContent).toContain(STATUS_WORDS.violation)
  })
})

describe('the detail sentence is on the glass — the whole of the user statement (AC 18, Q2)', () => {
  it('renders the banned-card sentence the two-slot row could not tell', async () => {
    await showing(BRAWL_VIOLATION_REPORT)

    // THE STORY'S OWN USER STATEMENT, made true: "I find out about a banned card". Rendered to
    // `DESIGN.md:423`'s letter — a label and a right-aligned Badge — this sentence appears
    // NOWHERE, on the one deck in forty that has a real legality violation.
    expect(within(panel()).getByText("'Pym Particles' is not legal in brawl.")).toBeVisible()
  })

  it('renders all six sentences, passes included — not only the bad news', async () => {
    await showing(ALL_PASS_REPORT)

    for (const row of ALL_PASS_REPORT.rows) {
      expect(within(panel()).getByText(row.detail)).toBeVisible()
    }
  })

  it('renders the size sentence a brawl deck sees, minimum and all (AC 28)', async () => {
    await showing(BRAWL_VIOLATION_REPORT)

    // §2's finding, on the glass: a PASS sentence naming a minimum forty cards below the format's
    // real one, for 18 of 40 decks. This is also why "detail only when status !== 'pass'" was
    // rejected — it would hide exactly this.
    expect(within(panel()).getByText('Mainboard has 100 cards; the minimum is 60.')).toBeVisible()
  })

  it('renders `Mainboard has 1 cards` — a live plural defect, in front of a person', async () => {
    await showing(ONE_CARD_REPORT)

    expect(within(panel()).getByText('Mainboard has 1 cards; the minimum is 60.')).toBeVisible()
  })

  it('renders the `(+N more)` suffix, which has no live instance at all', async () => {
    await showing(SINGLETON_VIOLATION_REPORT)

    expect(
      within(panel()).getByText(
        "2 copies of 'Candy Trail'; commander is a singleton format (max 1 copy of any " +
          'non-basic card). (+15 more)',
      ),
    ).toBeVisible()
  })

  it('renders the 86-character rotation advisory on every fixture — permanent furniture', async () => {
    for (const report of [ALL_PASS_REPORT, BRAWL_VIOLATION_REPORT, FORMATLESS_REPORT]) {
      resetFormatCheckState()
      const view = await showing(report)
      expect(
        within(panel()).getByText(
          'Rotation exposure cannot be checked: the local card data carries no set release dates.',
        ),
      ).toBeVisible()
      view.unmount()
    }
  })
})

describe('the formatless report: six rows, no second layout, nothing negative (Q8, AC 20)', () => {
  it.each([
    ['a named unrecognised format', FORMATLESS_REPORT],
    ['no format at all', NO_FORMAT_REPORT],
  ])('renders %s as an ordinary six-row report', async (_label, report) => {
    await showing(report)

    expect(within(panel()).getAllByRole('listitem')).toHaveLength(6)
    // Both advisory sentences reach the glass — the reading of `format_recognized` that Q8 asks
    // for, performed by this suite against the real field rather than by a decorative branch in
    // the component (see FormatCheck.tsx's header for why the component does not read it).
    const legality = report.rows.find((row) => row.check === 'legality')!
    const banned = report.rows.find((row) => row.check === 'banned')!
    expect(within(panel()).getByText(legality.detail)).toBeVisible()
    expect(within(panel()).getByText(banned.detail)).toBeVisible()
  })

  it('produces NOTHING negative from `is_legal: false` with zero violation rows (AC 19)', async () => {
    // THE TRAP, as a passing test. `deferred-work.md:2430-2437` homes it here by name and says
    // nothing machine-checkable stops it; live exposure is ZERO, which is exactly the condition
    // under which a wrong binding ships green. This fixture is the only way to produce it.
    expect(FORMATLESS_REPORT.is_legal).toBe(false)
    expect(FORMATLESS_REPORT.rows.some((row) => row.status === 'violation')).toBe(false)

    await showing(FORMATLESS_REPORT)

    expect(panel().querySelectorAll('.badge-negative')).toHaveLength(0)
    expect(panel().textContent).not.toContain(STATUS_WORDS.violation)
    // Three advisories — legality, banned, rotation — and three passes. The panel says "could not
    // be checked" three times and "is wrong" never, which is what `is_legal: false` actually means
    // here.
    expect(panel().querySelectorAll('.badge-caution')).toHaveLength(3)
    expect(panel().querySelectorAll('.badge-positive')).toHaveLength(3)
  })

  it('renders no `null`, no `undefined` and no format string in its chrome (Q14)', async () => {
    await showing(FORMATLESS_REPORT)

    expect(panel().textContent).not.toContain('undefined')
    expect(panel().textContent).not.toContain('null')
    // The panel's own chrome — its title and its six labels — names no format. The DETAIL
    // sentences do interpolate the NORMALISED format, and that is data arriving from the wire:
    // "'potato' is not a recognized format…". Measured: 0 of 40 real decks have a normalised
    // format that differs from the stored one `DeckBadges` renders in the header.
    const chrome = [FORMAT_CHECK_TITLE, ...Object.values(CHECK_LABELS)].join(' ')
    for (const format of ['standard', 'brawl', 'potato', 'historic', 'commander']) {
      expect(chrome.toLowerCase()).not.toContain(format)
    }
  })
})

describe('the three silent states draw nothing (Q6, AC 12)', () => {
  it('renders null before anything has been asked', () => {
    const { container } = render(<FormatCheck />)

    expect(container).toBeEmptyDOMElement()
  })

  it('renders null while a read is in flight — never a skeleton', () => {
    void loadFormatCheck('deck-1', () => new Promise(() => {}))
    const { container } = render(<FormatCheck />)

    expect(container).toBeEmptyDOMElement()
  })

  it.each([
    ['a refusal', { kind: 'error' as const, reason: 'deck_not_found' }],
    ['an unreachable backend', { kind: 'unreachable' as const }],
  ])('renders null for %s, and puts no panel on the glass', async (_label, outcome) => {
    await loadFormatCheck('deck-1', () => Promise.resolve(outcome))
    const { container } = render(<FormatCheck />)

    // The CARD precedent, not the deck one (Q6): the deck is still on the glass, so routing this
    // through `panelFor` would replace a working view with "The companion hit a bug" because one
    // auxiliary read failed — FR-13 inverted. The declared cost is that the failure is silent.
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('region', { name: FORMAT_CHECK_TITLE })).toBeNull()
  })
})

describe('display-only, literally (AC 6, UX-DR21, UX-DR40, UX-DR47)', () => {
  it('adds ZERO Tab stops and nothing is clickable', async () => {
    const view = await showing(MULTI_VIOLATION_REPORT)

    expect(view.container.querySelectorAll('button, a, input, select, textarea')).toHaveLength(0)
    expect(view.container.querySelectorAll('[tabindex]')).toHaveLength(0)
    expect(view.container.querySelectorAll('[role="button"]')).toHaveLength(0)
    expect(view.container.querySelectorAll('[onclick]')).toHaveLength(0)
  })

  it('a click changes nothing observable', async () => {
    const view = await showing(BRAWL_VIOLATION_REPORT)
    const before = view.container.innerHTML

    // `fireEvent` is the suite's only DOM-event idiom (c4-5 Q9). Clicking a row must be inert:
    // this panel touches the inspection slice not at all — no `setHovered`, no `togglePin`.
    for (const row of view.container.querySelectorAll('.format-check-row')) fireEvent.click(row)

    expect(view.container.innerHTML).toBe(before)
  })

  it('adds no `aria-live` region (AC 29, Q16)', async () => {
    const view = await showing(ALL_PASS_REPORT)

    // `CardDetail`'s single polite region stays the only one. Nothing here moves after first
    // paint: there is no refetch (Q7) and this panel derives nothing from the hydration sweep.
    expect(view.container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(view.container.querySelectorAll('[role="status"], [role="alert"]')).toHaveLength(0)
  })

  it('renders CALMLY — no alert role, no exclamation mark, no icon (AC 33, UX-DR30)', async () => {
    const view = await showing(MULTI_VIOLATION_REPORT)

    expect(view.container.querySelectorAll('svg, img')).toHaveLength(0)
    // The backend authors every sentence and none of them shouts; this asserts that the PANEL
    // adds nothing that does. Three violations on screen and not one exclamation mark.
    expect(view.container.textContent).not.toContain('!')
  })

  it('overrides no list role — the `<ul>` stays a list (AC 5)', async () => {
    const view = await showing(ALL_PASS_REPORT)

    const list = view.container.querySelector('.format-check-rows')
    expect(list?.tagName).toBe('UL')
    expect(list?.getAttribute('role')).toBeNull()
  })
})
