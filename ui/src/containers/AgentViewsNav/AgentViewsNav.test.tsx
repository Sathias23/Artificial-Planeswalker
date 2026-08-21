import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
import { HISTORY_LABEL, HISTORY_QUIET_TOOLTIP, NAV_GROUP_LABEL, QUIET_TOOLTIP, UNREAD_WORD } from './copy'
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

const contentOf = (kind: AgentViewKind, over: Partial<AgentViewContent> = {}): AgentViewContent =>
  // Cast since 16.1 made `AgentViewContent` a per-kind discriminated union: `items: []` is a
  // legal member of every arm, but a computed `kind` cannot select one for the compiler.
  ({
    id: `push-${kind}`,
    ts: '2026-08-12T14:32:00+00:00',
    kind,
    title: AGENT_VIEW_LABELS[kind],
    count: 0,
    items: [],
    ...over,
  }) as AgentViewContent

/** The pill for a kind, by its accessible name's leading label. */
const pillFor = (kind: AgentViewKind): HTMLElement =>
  screen.getByRole('button', { name: new RegExp(`^${AGENT_VIEW_LABELS[kind]}`) })

afterEach(() => {
  resetAgentView()
})

describe('the nav renders one pill per kind, in enum order (AC 1, AC 6, Q3)', () => {
  it('renders exactly five pills — four kinds plus History (17.2)', () => {
    render(<AgentViewsNav />)
    expect(screen.getAllByRole('button')).toHaveLength(5)
  })

  it('renders them in the ruled order — Suggestions, Swaps, Tier list, Card groups, History', () => {
    // Q3 took the wire enum's order over the mock's and the IA table's. `PILL_ORDER` derives it
    // from the vocabulary table's declaration order rather than authoring it a second time, so
    // this assertion is what keeps that derivation honest: a reordered table reorders the glass.
    // History renders LAST, outside the map (2026-08-22 ruling: immediately after the Card
    // groups pill), which is also the proof it is not keyed into the kind enum.
    render(<AgentViewsNav />)
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Suggestions',
      'Swaps',
      'Tier list',
      'Card groups',
      HISTORY_LABEL,
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
    // …and the sibling pills are unharmed, which is what "degrades alone" means.
    expect(screen.getAllByRole('button')).toHaveLength(5)
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
    // …and the sibling pills are unharmed, which is what "degrades alone" means.
    expect(screen.getAllByRole('button')).toHaveLength(5)
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

// =========================================================================================
// STORY 17.2 — the History pill and its popover
// =========================================================================================

/** A push with its own id and ts, so history rows can be told apart. */
const historyPush = (n: number, kind: AgentViewKind = 'suggestions'): AgentViewContent =>
  contentOf(kind, {
    id: `push-h${n}`,
    ts: `2026-08-22T10:${String(n).padStart(2, '0')}:00+00:00`,
    title: `Push ${n}`,
  })

const historyPill = (): HTMLButtonElement =>
  screen.getByRole<HTMLButtonElement>('button', { name: HISTORY_LABEL })

const popover = (): HTMLElement | null => document.querySelector('.agent-views-nav-popover')
const entries = (): HTMLButtonElement[] => [
  ...document.querySelectorAll<HTMLButtonElement>('.agent-views-nav-entry'),
]

describe('the History pill is quiet until the first push of ANY kind (17.2)', () => {
  it('renders disabled with its OWN sentence in both channels, outside the accessible name', () => {
    render(<AgentViewsNav />)
    const pill = historyPill()
    expect(pill.disabled).toBe(true)
    expect(pill.getAttribute('title')).toBe(HISTORY_QUIET_TOOLTIP)
    const describedBy = pill.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy!)?.textContent).toBe(HISTORY_QUIET_TOOLTIP)
    // The sentence is its own, about the SESSION, not the kind pills' per-kind one.
    expect(HISTORY_QUIET_TOOLTIP).not.toBe(QUIET_TOOLTIP)
    // Outside the button: the name stays the one word.
    expect(pill.textContent).toBe(HISTORY_LABEL)
  })

  it('declares itself a closed disclosure even while quiet', () => {
    render(<AgentViewsNav />)
    expect(historyPill().getAttribute('aria-haspopup')).toBe('true')
    expect(historyPill().getAttribute('aria-expanded')).toBe('false')
    // …and controls nothing yet: an `aria-controls` naming an unmounted id would be a dangling
    // reference, the same silence a dangling `aria-describedby` is.
    expect(historyPill().getAttribute('aria-controls')).toBeNull()
  })

  it('carries a stroke-based clock glyph, hidden from the accessibility tree', () => {
    const { container } = render(<AgentViewsNav />)
    const glyph = container.querySelector('.agent-views-nav-clock')!
    expect(glyph).not.toBeNull()
    expect(glyph.getAttribute('aria-hidden')).toBe('true')
    // Stroke-based, per the DESIGN.md note — a plain UI glyph, never a filled set-symbol shape.
    for (const shape of glyph.querySelectorAll('circle, path')) {
      expect(shape.getAttribute('fill')).toBe('none')
      expect(shape.getAttribute('stroke')).toBe('currentColor')
    }
  })

  it('activates on the first push of ANY kind — a swaps push counts (unlike the kind pills)', () => {
    openAgentView(historyPush(1, 'swaps'))
    render(<AgentViewsNav />)
    expect(historyPill().disabled).toBe(false)
    expect(historyPill().getAttribute('title')).toBeNull()
    expect(historyPill().getAttribute('aria-describedby')).toBeNull()
    // Non-vacuity twin: the suggestions KIND pill is still quiet beside it.
    expect((pillFor('suggestions') as HTMLButtonElement).disabled).toBe(true)
  })

  it('NEVER carries an unread dot, even while a kind pill does', () => {
    openAgentView(historyPush(1, 'suggestions'))
    openAgentView(historyPush(2, 'swaps')) // displaces suggestions → its KIND pill is unread
    render(<AgentViewsNav />)
    expect(pillFor('suggestions').textContent).toContain(UNREAD_WORD)
    expect(historyPill().textContent).not.toContain(UNREAD_WORD)
    expect(historyPill().querySelector('.agent-views-nav-dot')).toBeNull()
  })
})

describe('the popover lists the session’s pushes, newest first (17.2)', () => {
  beforeEachHistory()

  it('toggles open on click, with aria-expanded following', () => {
    render(<AgentViewsNav />)
    expect(popover()).toBeNull()
    fireEvent.click(historyPill())
    expect(popover()).not.toBeNull()
    expect(historyPill().getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(historyPill())
    expect(popover()).toBeNull()
    expect(historyPill().getAttribute('aria-expanded')).toBe('false')
  })

  it('associates pill and popover programmatically — aria-controls resolves while open (review finding 10)', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    const controls = historyPill().getAttribute('aria-controls')
    expect(controls).toBeTruthy()
    // A real element, resolved through the id — not merely an attribute pointing somewhere.
    expect(document.getElementById(controls!)).toBe(popover())
    fireEvent.click(historyPill())
    // Withdrawn with the popover: a controls reference to an unmounted id is a dangling one.
    expect(historyPill().getAttribute('aria-controls')).toBeNull()
  })

  it('renders one real <button> per push, newest first, kind + title + time', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())

    const held = entries()
    expect(held).toHaveLength(3)
    // Newest first — the STORE's order, rendered without re-sorting.
    expect(held.map((e) => e.querySelector('.agent-views-nav-entry-title')?.textContent)).toEqual([
      'Push 3',
      'Push 2',
      'Push 1',
    ])
    // Kind word from the one vocabulary table; time through pushTimeLabel with the raw ts.
    expect(held[0].querySelector('.agent-views-nav-entry-kind')?.textContent).toBe(
      AGENT_VIEW_LABELS.swaps,
    )
    const time = held[0].querySelector('time')!
    expect(time.getAttribute('datetime')).toBe('2026-08-22T10:03:00+00:00')
    expect(time.textContent).toBe(pushTimeLabel('2026-08-22T10:03:00+00:00'))
  })

  it('omits the title when the agent supplied none — the fallback is not read out twice', () => {
    resetAgentView()
    openAgentView(contentOf('suggestions')) // title === the kind's own word (the fallback)
    closeAgentView() // the popover only shows while no view is on the glass
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    expect(entries()).toHaveLength(1)
    expect(entries()[0].querySelector('.agent-views-nav-entry-title')).toBeNull()
    expect(entries()[0].querySelector('.agent-views-nav-entry-kind')?.textContent).toBe(
      AGENT_VIEW_LABELS.suggestions,
    )
  })

  it('degrades an entry’s TIME alone on an unparseable ts — the entry stays activatable', () => {
    resetAgentView()
    openAgentView(contentOf('suggestions', { id: 'push-bad', ts: 'yesterday', title: 'Bad clock' }))
    closeAgentView() // the popover only shows while no view is on the glass
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    expect(entries()).toHaveLength(1)
    expect(entries()[0].querySelector('time')).toBeNull()
    fireEvent.click(entries()[0])
    expect(useAgentViewStore.getState().status).toBe('open')
    expect(useAgentViewStore.getState().content?.id).toBe('push-bad')
  })

  it('is NOT a modal, landmark, listbox or live region — a plain group of buttons', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    const root = popover()!
    expect(root.getAttribute('role')).toBeNull()
    expect(root.getAttribute('aria-modal')).toBeNull()
    expect(root.getAttribute('aria-live')).toBeNull()
    expect(document.querySelector('[aria-live]')).toBeNull()
    expect(screen.queryByRole('navigation')).toBeNull()
    expect(screen.queryByRole('listbox')).toBeNull()
    // Every entry is a real button in document order, no roving tabindex anywhere.
    for (const entry of entries()) {
      expect(entry.tagName).toBe('BUTTON')
      expect(entry.getAttribute('tabindex')).toBeNull()
    }
  })

  it('moves focus to the FIRST (newest) entry on open', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    expect(document.activeElement).toBe(entries()[0])
  })
})

describe('the popover’s four dismissals (17.2)', () => {
  beforeEachHistory()

  it('entry activation closes FIRST (focus → pill), then opens that exact push’s view', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    const second = entries()[1]
    fireEvent.click(second)

    expect(popover()).toBeNull()
    // That exact push, by object identity, through the store's reopenPush.
    expect(useAgentViewStore.getState().status).toBe('open')
    expect(useAgentViewStore.getState().content?.id).toBe('push-h2')
    expect(useAgentViewStore.getState().content).toBe(
      useAgentViewStore.getState().history.find((e) => e.id === 'push-h2'),
    )
    // Focus went to the pill on close — which is what the (absent-here) view shell would then
    // capture as its return target; App.test.tsx composes that half.
    expect(document.activeElement).toBe(historyPill())
  })

  it('Esc closes the popover and returns focus to the pill — consuming the keystroke', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    expect(document.activeElement).toBe(entries()[0])

    const consumed = !fireEvent.keyDown(document.activeElement!, { key: 'Escape' })

    expect(popover()).toBeNull()
    expect(document.activeElement).toBe(historyPill())
    // `preventDefault()` was called — the node-level half of the Esc layering, which is what
    // keeps the SAME keystroke from also releasing an active pin (CardDetail honours
    // `defaultPrevented`; UX-DR39's amended order: view → popover → pin).
    expect(consumed).toBe(true)
  })

  it('Esc with focus on the PILL — inside the wrapper, outside the popover — closes and CONSUMES (review finding 3)', () => {
    // The toggle puts focus exactly here, so this is the ordinary second-Esc position. The
    // consuming listener sits on the WRAPPER, not the popover root, precisely so this keystroke
    // is consumed too — an active pin elsewhere must survive it (UX-DR39's amended order).
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    act(() => {
      historyPill().focus()
    })
    const consumed = !fireEvent.keyDown(historyPill(), { key: 'Escape' })
    expect(popover()).toBeNull()
    expect(consumed).toBe(true)
    expect(document.activeElement).toBe(historyPill())
  })

  it('Esc with focus OUTSIDE the wrapper still closes it — the document-level bubble half', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    // Focus wanders out entirely (the entries are ordinary Tab stops, so this is reachable) —
    // onto an active KIND pill, a live control outside the pill+popover wrapper. Selected by
    // CLASS rather than through `pillFor`: with the popover open, the swaps HISTORY ENTRY's
    // accessible name also starts with the kind word, and the role query would find both.
    const swapsPill = [...document.querySelectorAll<HTMLButtonElement>('.agent-views-nav-pill')].find(
      (p) => p.textContent?.startsWith(AGENT_VIEW_LABELS.swaps),
    )!
    act(() => {
      swapsPill.focus()
    })
    const consumed = !fireEvent.keyDown(swapsPill, { key: 'Escape' })
    expect(popover()).toBeNull()
    // The document half does NOT consume — outside the wrapper there is no layering of its own
    // to arbitrate (the accepted pin residual is pinned at the App seam).
    expect(consumed).toBe(false)
    // And focus is NOT yanked back to the History pill: it sat on a live control outside the
    // wrapper, and closing must not reverse a decision it did not make.
    expect(document.activeElement).toBe(swapsPill)
  })

  it('stays closed when the view closes right after a push closed it (review finding 1)', () => {
    // The regression this pins: the first shipped form parked the `open` reset in a
    // requestAnimationFrame, and a view closed before that frame fired cancelled the reset in
    // the effect cleanup — the popover then sprang back uninvited the moment the view left the
    // glass. Fake timers hold every frame back, so the close-before-frame ordering is exact.
    vi.useFakeTimers()
    try {
      render(<AgentViewsNav />)
      fireEvent.click(historyPill())
      expect(popover()).not.toBeNull()
      act(() => {
        openAgentView(historyPush(9)) // a push arrives: its view opens, the popover closes…
      })
      expect(popover()).toBeNull()
      act(() => {
        closeAgentView() // …and the view is dismissed before any frame can fire
      })
      // The popover must NOT spring back: the reset was synchronous, not parked on a frame.
      expect(popover()).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('outside pointerdown closes it; a press INSIDE does not', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    fireEvent.pointerDown(entries()[0])
    expect(popover()).not.toBeNull()
    fireEvent.pointerDown(document.body)
    expect(popover()).toBeNull()
  })

  it('closes when a view opens by ANY route — popover and modal never coexist', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    expect(popover()).not.toBeNull()
    act(() => {
      openAgentView(historyPush(9)) // a push arriving while the popover is open
    })
    expect(popover()).toBeNull()
    expect(useAgentViewStore.getState().status).toBe('open')
    // …and the withdrawn entries are really gone from the Tab order (transient stops).
    expect(entries()).toHaveLength(0)
  })
})

describe('the popover’s enter fade starts from a state and settles (17.2, review finding 7)', () => {
  beforeEachHistory()

  // Fake timers, for `AgentView.test.tsx:234-258`'s exact reason: this is the one popover
  // behaviour with a frame in the middle of it, and the fake clock stands in for
  // `requestAnimationFrame` so BOTH ends of the transition are assertable — the starting state
  // a real-timer test could never catch, and the settled state it would have to wait for. A
  // broken flip here would ship a permanently `opacity: 0` popover on a fully green suite,
  // which is the failure this pair exists to make loud.
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('mounts IN the entering state, so the transition has somewhere to come from', () => {
    // `HistoryPopover.css` hangs `opacity: 0` on this exact attribute value; a component that
    // settled during its own first commit would paint the rest state immediately and fade
    // nothing at all.
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    expect(popover()!.getAttribute('data-entering')).toBe('true')
  })

  it('leaves the entering state on the next frame, so the fade runs', () => {
    render(<AgentViewsNav />)
    fireEvent.click(historyPill())
    act(() => {
      vi.advanceTimersByTime(20)
    })
    // The attribute is REMOVED (not set to 'false'): the CSS keys on `[data-entering='true']`
    // and the settled popover carries no residue.
    expect(popover()!.hasAttribute('data-entering')).toBe(false)
  })
})

/** Three mixed-kind pushes, oldest to newest — the standing fixture for the popover suites. */
function beforeEachHistory() {
  beforeEach(() => {
    openAgentView(historyPush(1, 'suggestions'))
    openAgentView(historyPush(2, 'tier_list'))
    openAgentView(historyPush(3, 'swaps'))
    closeAgentView()
  })
}
