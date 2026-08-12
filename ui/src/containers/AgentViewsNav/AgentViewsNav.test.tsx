import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { AgentViewKind } from '../../api/schema'
import {
  AGENT_VIEW_LABELS,
  type AgentViewContent,
  closeAgentView,
  openAgentView,
  resetAgentView,
  useAgentViewStore,
} from '../../state/agentView'
import { AgentViewsNav } from './AgentViewsNav'
import { NAV_GROUP_LABEL, QUIET_TOOLTIP, UNREAD_WORD } from './copy'
import { pushTimeLabel } from './pushTime'

/**
 * The agent-views nav's pills (story c6-8).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * jsdom evaluates no stylesheet, so nothing here proves a quiet pill is `text-tertiary`, that the
 * unread dot is 8px and `--accent`, that the labels are uppercased by their type role, or that a
 * pill clears 24px in either direction. Those are read as SOURCE by `token-usage.test.ts`,
 * `shell.test.ts` and `keyboard-floor.test.ts`, and are seen with eyes on the C6 manual checklist
 * (c8-6) — this story adds the header pills to the app's unviewed-pixels surface, extending the
 * declaration c6-7 made about the rows.
 *
 * jsdom also renders no tooltip and runs no sequential focus navigation: `title` is asserted as
 * an attribute, never as a thing that appears, and *"the pills sit ahead of the grid in the Tab
 * order"* (AC 6) is a DOM-order claim proved in `App.test.tsx` against the whole document, not
 * here against a nav rendered alone.
 *
 * What this file proves is the BRANCH and the WIRING: which element renders for which store
 * state, which handler reaches which verb, and what the accessibility tree is told.
 *
 * ================= HOUSE RULES OBSERVED ==============================================
 *
 * Every behavioural assertion pairs with a non-vacuity control, and every absence-only assertion
 * has its positive twin in the same suite — c6-7's plant-3 lesson, where a test that only checked
 * *"X is not there"* was satisfied by a component with no handlers wired at all. `fireEvent`
 * only; vitest globals are OFF, so `describe`/`it`/`expect` are imported.
 */

const contentOf = (
  kind: AgentViewKind,
  over: Partial<AgentViewContent> = {},
): AgentViewContent => ({
  id: `push-${kind}`,
  ts: '2026-08-12T14:32:00+00:00',
  kind,
  title: AGENT_VIEW_LABELS[kind],
  count: 0,
  items: [],
  ...over,
})

/** The pill for a kind, by its accessible name's leading label. */
const pillFor = (kind: AgentViewKind): HTMLElement =>
  screen.getByRole('button', { name: new RegExp(`^${AGENT_VIEW_LABELS[kind]}`) })

afterEach(() => {
  resetAgentView()
})

describe('the nav renders one pill per kind, in enum order (AC 1, AC 6, Q3)', () => {
  it('renders exactly four pills', () => {
    render(<AgentViewsNav />)
    expect(screen.getAllByRole('button')).toHaveLength(4)
  })

  it('renders them in the ruled order — Suggestions, Swaps, Tier list, Card groups', () => {
    // Q3 took the wire enum's order over the mock's and the IA table's. `PILL_ORDER` derives it
    // from the vocabulary table's declaration order rather than authoring it a second time, so
    // this assertion is what keeps that derivation honest: a reordered table reorders the glass.
    render(<AgentViewsNav />)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Suggestions',
      'Swaps',
      'Tier list',
      'Card groups',
    ])
  })

  it('names the group on the glass (Q5)', () => {
    render(<AgentViewsNav />)
    expect(screen.getByText(NAV_GROUP_LABEL)).toBeTruthy()
  })

  it('adds NO navigation landmark (Q5, UX-DR44)', () => {
    // The absence is the ruling: the pills open overlays, they do not navigate. Its positive
    // twin is the assertion above — the group IS named, visibly, which is what the landmark
    // would otherwise have been reached for.
    render(<AgentViewsNav />)
    expect(screen.queryByRole('navigation')).toBeNull()
  })
})

describe('a kind with no push this session is QUIET (AC 1, Q2)', () => {
  it('renders every pill disabled on a cold open', () => {
    render(<AgentViewsNav />)
    for (const pill of screen.getAllByRole('button')) {
      expect((pill as HTMLButtonElement).disabled).toBe(true)
    }
  })

  it('carries the tooltip and the same sentence as a programmatic description', () => {
    render(<AgentViewsNav />)
    const pill = pillFor('swaps')
    expect(pill.getAttribute('title')).toBe(QUIET_TOOLTIP)
    // The description is a real element, resolved through the id — not merely an attribute that
    // points somewhere. A dangling `aria-describedby` is silence, which is the failure Q2's
    // ruling exists to prevent.
    const describedBy = pill.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy!)?.textContent).toBe(QUIET_TOOLTIP)
  })

  it('keeps the description OUT of the accessible name', () => {
    // If the hidden span sat inside the button, the pill would be named "Swaps Your agent hasn't
    // sent this yet." and then described with the same sentence again.
    render(<AgentViewsNav />)
    expect(pillFor('swaps').textContent).toBe('Swaps')
  })

  it('gives two mounted navs DIFFERENT description ids (why it is useId, not a constant)', () => {
    // `AgentView.test.tsx:204`'s assertion, applied to this component's own generated ids: a
    // hand-written `agent-views-nav-swaps-hint` would collide the moment anything rendered two
    // navs, and `aria-describedby` would silently resolve to whichever came first.
    const { container: a } = render(<AgentViewsNav />)
    const { container: b } = render(<AgentViewsNav />)
    const idOf = (root: Element) => root.querySelector('button')!.getAttribute('aria-describedby')
    expect(idOf(a)).not.toBe(idOf(b))
    expect(idOf(a)).toBeTruthy()
  })

  it('carries no tabindex, in any spelling (Landmine 2, UX-DR40)', () => {
    // `keyboard-floor.test.ts` pins exactly ONE named tabindex exception in this app, and it is
    // not this. Its positive twin is the disabled assertion above: quiet is expressed by the
    // attribute that removes the element from the Tab order honestly.
    render(<AgentViewsNav />)
    for (const pill of screen.getAllByRole('button')) {
      expect(pill.getAttribute('tabindex')).toBeNull()
      expect(pill.getAttribute('tabIndex')).toBeNull()
    }
  })

  it('does nothing when clicked, and the store is untouched', () => {
    render(<AgentViewsNav />)
    fireEvent.click(pillFor('groups'))
    expect(useAgentViewStore.getState().status).toBe('closed')
    expect(useAgentViewStore.getState().content).toBeNull()
  })

  it('shows no time and no unread dot', () => {
    const { container } = render(<AgentViewsNav />)
    expect(container.querySelector('time')).toBeNull()
    expect(container.querySelector('.agent-views-nav-dot')).toBeNull()
  })
})

describe('a kind that HAS pushed is active and shows its time (AC 2, Q4)', () => {
  it('drops `disabled` on that kind’s pill and no other', () => {
    // The non-vacuity control for every "is active" assertion below: exactly one pill changes.
    openAgentView(contentOf('suggestions'))
    render(<AgentViewsNav />)
    expect((pillFor('suggestions') as HTMLButtonElement).disabled).toBe(false)
    expect((pillFor('swaps') as HTMLButtonElement).disabled).toBe(true)
    expect((pillFor('tier_list') as HTMLButtonElement).disabled).toBe(true)
    expect((pillFor('groups') as HTMLButtonElement).disabled).toBe(true)
  })

  it('drops the tooltip and the description with it', () => {
    openAgentView(contentOf('suggestions'))
    render(<AgentViewsNav />)
    expect(pillFor('suggestions').getAttribute('title')).toBeNull()
    expect(pillFor('suggestions').getAttribute('aria-describedby')).toBeNull()
    // Positive twin: the quiet pill beside it still has both.
    expect(pillFor('swaps').getAttribute('title')).toBe(QUIET_TOOLTIP)
  })

  it('renders the push time in a <time> carrying the raw ts', () => {
    const ts = '2026-08-12T14:32:00+00:00'
    openAgentView(contentOf('suggestions', { ts }))
    const { container } = render(<AgentViewsNav />)
    const time = container.querySelector('time')!
    expect(time.getAttribute('datetime')).toBe(ts)
    // Computed through the same formatter, never asserted as bytes: jsdom inherits the host's TZ
    // and ICU build, so a literal '14:32' here would be a machine-dependent test (Landmine 6).
    expect(time.textContent).toBe(pushTimeLabel(ts))
    expect(time.textContent).toBeTruthy()
  })

  it('shows a DIFFERENT time for a different ts — the formatter is really reading it', () => {
    // The non-vacuity twin of the assertion above, which a formatter returning a constant would
    // otherwise satisfy.
    const morning = '2026-08-12T04:05:00+00:00'
    const evening = '2026-08-12T19:45:00+00:00'
    expect(pushTimeLabel(morning)).not.toBe(pushTimeLabel(evening))
  })

  it('stays active but renders NO time when the ts is unparseable', () => {
    // Reachable: `agentEventOf` validates the `kind` discriminant and nothing else, so a frame
    // with `ts: "yesterday"` reaches the store typed as an ISO string — and
    // `Intl.DateTimeFormat.format` THROWS a RangeError on an Invalid Date. Unguarded, one bad
    // field would take the whole header down. The pill degrades alone (FR-13, AD-7).
    expect(pushTimeLabel('yesterday')).toBeNull()
    openAgentView(contentOf('suggestions', { ts: 'yesterday' }))
    const { container } = render(<AgentViewsNav />)
    expect((pillFor('suggestions') as HTMLButtonElement).disabled).toBe(false)
    expect(container.querySelector('time')).toBeNull()
    // …and the three quiet pills are unharmed, which is what "degrades alone" means.
    expect(screen.getAllByRole('button')).toHaveLength(4)
  })

  it('stays active and shows no time when the ts is entirely ABSENT (review fix, 2026-08-12)', () => {
    // Distinct from the "unparseable" case above (a present-but-garbage `ts` string): this is a
    // retained push whose `ts` KEY is missing altogether — the other half of `agentEventOf`'s
    // "validates only `kind`" gap. Activeness must come from `useAgentViewHasPush` (retention
    // presence), not from `.ts` presence — the bug this test guards against made a pill with a
    // real, already-shown push render QUIET, indistinguishable from "never pushed", which left
    // it permanently unreachable after the next dismissal (UX-DR34's "re-openable for the rest
    // of the session").
    const malformed = { ...contentOf('suggestions') } as { ts?: string }
    delete malformed.ts
    openAgentView(malformed as unknown as AgentViewContent)
    const { container } = render(<AgentViewsNav />)
    expect((pillFor('suggestions') as HTMLButtonElement).disabled).toBe(false)
    expect(container.querySelector('time')).toBeNull()
    // …and the three quiet pills are unharmed, which is what "degrades alone" means.
    expect(screen.getAllByRole('button')).toHaveLength(4)
  })

  it('survives a dismissal — a pill is active because the kind PUSHED, not because it is open', () => {
    openAgentView(contentOf('suggestions'))
    closeAgentView()
    render(<AgentViewsNav />)
    expect((pillFor('suggestions') as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('the unread dot (AC 3, Q6)', () => {
  /** Open `first`, then push `second` over it — the only way to make anything unread. */
  const displace = (first: AgentViewKind, second: AgentViewKind): void => {
    openAgentView(contentOf(first))
    openAgentView(contentOf(second))
  }

  it('renders a presentational dot AND the word, on the displaced pill only', () => {
    displace('suggestions', 'swaps')
    const { container } = render(<AgentViewsNav />)
    const dots = container.querySelectorAll('.agent-views-nav-dot')
    expect(dots).toHaveLength(1)
    expect(dots[0].getAttribute('aria-hidden')).toBe('true')
    // UX-DR29: the dot never carries the state alone. The word is IN the accessible name.
    expect(pillFor('suggestions').textContent).toContain(UNREAD_WORD)
    // The non-vacuity twin — the pill that was just opened is read, and says so by omission.
    expect(pillFor('swaps').textContent).not.toContain(UNREAD_WORD)
  })

  it('adds no live region — the pill must not announce (UX-DR45)', () => {
    // UX-DR45 enumerates exactly three live regions and this pill is not one. Absence-only, so
    // its positive twin is the assertion above: the state IS conveyed, as a word in the name.
    displace('suggestions', 'swaps')
    const { container } = render(<AgentViewsNav />)
    expect(container.querySelector('[aria-live]')).toBeNull()
  })

  it('clears when the view is re-opened from its pill', () => {
    displace('suggestions', 'swaps')
    const { container } = render(<AgentViewsNav />)
    expect(container.querySelectorAll('.agent-views-nav-dot')).toHaveLength(1)
    fireEvent.click(pillFor('suggestions'))
    // Now `swaps` is the displaced one — the count holds at one, but it MOVED, which is a
    // stronger claim than "an unread dot exists somewhere".
    expect(pillFor('suggestions').textContent).not.toContain(UNREAD_WORD)
    expect(pillFor('swaps').textContent).toContain(UNREAD_WORD)
  })
})

describe('clicking an active pill re-opens its view (AC 4)', () => {
  it('puts the SAME content back — object identity, not a rebuild', () => {
    const pushed = contentOf('suggestions')
    openAgentView(pushed)
    closeAgentView()
    render(<AgentViewsNav />)
    fireEvent.click(pillFor('suggestions'))
    expect(useAgentViewStore.getState().status).toBe('open')
    expect(useAgentViewStore.getState().content).toBe(pushed)
  })

  it('re-opens the LAST push of that kind after a replace', () => {
    // c6-6's replace-in-place, seen from the nav: retention holds one view per kind, the newest.
    openAgentView(contentOf('suggestions', { id: 'first' }))
    const second = contentOf('suggestions', { id: 'second' })
    openAgentView(second)
    closeAgentView()
    render(<AgentViewsNav />)
    fireEvent.click(pillFor('suggestions'))
    expect(useAgentViewStore.getState().content).toBe(second)
  })

  it('needs no onKeyDown — Enter is the button’s own click (UX-DR39, dw:49)', () => {
    // The absence dw:49 asked this story for, with its positive twin: the CLICK the browser
    // synthesises from Enter does reach the verb, which is why no handler is needed. A synthetic
    // keydown must NOT be what re-opens the view — that path is starved while a view is open.
    openAgentView(contentOf('suggestions'))
    closeAgentView()
    render(<AgentViewsNav />)
    const pill = pillFor('suggestions')
    fireEvent.keyDown(pill, { key: 'Enter' })
    expect(useAgentViewStore.getState().status).toBe('closed')
    fireEvent.click(pill)
    expect(useAgentViewStore.getState().status).toBe('open')
  })
})
