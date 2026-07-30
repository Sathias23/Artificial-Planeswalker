/**
 * App's own job, now that it has one: composing the shell.
 *
 * The landmark, header and slot assertions moved to
 * `src/components/AppShell/AppShell.test.tsx` in story c2-6, where the element structure
 * actually lives — asserting them twice would mean two files to update when c4-2 changes the
 * heading, and the second one would be the one nobody remembers. What stays here is the part
 * only this file can be wrong about: that the root renders the shell at all, and that it
 * renders exactly one of it.
 *
 * The jsdom environment, the jest-dom matchers and afterEach(cleanup) all come from the `dom`
 * vitest project in vite.config.ts; nothing needs setting up per file.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'
import { sentenceOf } from './components/Footer/copy'

describe('App', () => {
  it('renders the application shell', () => {
    render(<App />)

    // By role, not by class name — and ONE landmark, not the full triple: the landmark
    // CONTRACT (exactly one banner/main/contentinfo, Q4's structure) is AppShell.test.tsx's,
    // and re-asserting it here would be exactly the duplication this file's header says was
    // moved — two files to update when Q4's structure changes, and the second one forgotten.
    //
    // What this assertion is and is NOT: `main` alone proves App renders SOMETHING with a
    // main landmark, which a bare `<main/>` impostor would also satisfy. The composition
    // proof is the heading test below — the shell supplies that heading, and an impostor
    // would not. Together they are the pair; neither carries it alone, and an earlier version
    // of this comment claimed the first one did.
    expect(screen.getAllByRole('main')).toHaveLength(1)
  })

  it('gives the document a top-level heading before any deck exists', () => {
    // Q3's ruling, asserted at the root because it is a property of what a fresh install
    // SHOWS, not of the shell in isolation: the no-active-deck state is the state the app
    // starts in, and it must not be heading-less. c4-2 replaces the string via `deckName`.
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Artificial Planeswalker' })).toBeVisible()
  })

  it('wires the no-active-deck state panel into the shell — Q1 made this the point', () => {
    // The review of 2026-07-29 measured that reverting App.tsx's `left` prop — the story's
    // headline decision, the cause of the bundle change, the thing a human can finally look
    // at — kept every test green. Landmine 18's "wiring breaks neither file" was permission to
    // wire without fear, not a reason to leave the wiring unasserted. By role and accessible
    // name, because that is what the panel IS to a screen reader; c3-9 replaces the static
    // choice with the wire-driven one and inherits this assertion.
    render(<App />)

    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeVisible()
  })
})

/**
 * The attribution on every top-level surface (story c2-10, AC 15, NFR-08, UX-DR32).
 *
 * THIS IS A RELEASE CONDITION, NOT A DESIGN CHOICE — `DESIGN.md:375` says so in bold. So it is
 * asserted at the ROOT, where a human would look, rather than only in `Footer.test.tsx` where
 * the component is rendered in isolation. c2-9's review measured the exact hole this closes:
 * reverting `App.tsx`'s `left` prop kept all 487 tests green, because nothing asserted the
 * wiring one layer above the component. Reverting the `footer` prop must not stay green.
 *
 * "EVERY SURFACE" IS STRUCTURAL, NOT ENUMERATED (Q3, Brad 2026-07-30). There is one `AppShell`,
 * one `footer` slot and no router, so every surface renders through `App`. An enumerated list of
 * surfaces would be a list its author thought of — this epic's standing finding. The rule is
 * written into `App.tsx` and `ui/README.md` where the next surface's author will read it, and
 * the second test below is what makes it a gate rather than a note.
 */
describe('the attribution is on the surface (c2-10, AC 15)', () => {
  it('renders inside the contentinfo landmark, by role and by text', () => {
    render(<App />)

    const contentinfo = screen.getByRole('contentinfo')
    // BY TEXT, against the copy module's own join — so this assertion cannot drift from the
    // artefact independently of `tests/attribution.test.ts`. `toHaveTextContent` would be a
    // substring check; the landmark's whole text is the sentence and nothing else.
    expect(contentinfo.textContent).toBe(sentenceOf())
  })

  it('exposes both attribution links from the rendered app, not just from the component', () => {
    render(<App />)

    const links = within(screen.getByRole('contentinfo')).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      'https://scryfall.com/docs/api',
      'https://company.wizards.com/en/legal/fancontentpolicy',
    ])
  })

  it('leaves no surface without it — the slot is filled, not merely fillable (Q3)', () => {
    render(<App />)

    // The structural half. The shell renders a PLACEHOLDER whenever `footer` is empty, so a
    // reverted or dropped `footer` prop presents as the placeholder line rather than as an
    // empty landmark — which a "is the landmark non-empty" check would happily accept. Naming
    // the placeholder is what makes that specific regression fail here.
    expect(screen.getByRole('contentinfo').textContent).not.toContain('lands here')
    expect(screen.queryByText(/Scryfall and Fan Content attribution lands here/)).toBeNull()
  })
})
