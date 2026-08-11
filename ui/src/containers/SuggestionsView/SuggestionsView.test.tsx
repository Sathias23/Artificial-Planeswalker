import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SuggestionsView } from './SuggestionsView'
import { EMPTY_PUSH_TEMPLATE, KIND_PLACEHOLDER, emptyPushLine } from './copy'

/**
 * The suggestions view's body (story c6-6, AC 4; Q1's interim shape).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * jsdom evaluates no stylesheet, so nothing here proves the line is `--type-body` in
 * `--text-secondary` and nothing here proves it spends no length of its own. `shell.test.ts`
 * reads that stylesheet as source; `tests/empty-push-copy.test.ts` holds the BYTES of the
 * sentence against `EXPERIENCE.md`. What this file proves is the BRANCH — which of the two
 * states renders, for which input — and that the kind really is interpolated rather than
 * hard-coded.
 *
 * It also cannot judge whether the sentence is blameless and concrete. That is the permanently
 * open ledger entry naming this story, and its discharge is a human reading recorded in the
 * story's Debug Log, not an assertion here.
 */

const ITEM = { card_id: 'c-1', reason: 'Fills the two-drop gap.' }

describe('an empty push renders the artefact’s line (AC 4, UX-DR33, AD-7)', () => {
  it('renders the sentence, with the wire kind substituted', () => {
    render(<SuggestionsView kind="suggestions" items={[]} />)

    expect(screen.getByText(emptyPushLine('suggestions'))).toBeInTheDocument()
    // The substitution really happened: the placeholder is gone from what a reader sees. A
    // component that rendered the raw template would satisfy a `toContain('The agent sent')`
    // check and put `{kind}` on the glass.
    expect(document.body.textContent).not.toContain(KIND_PLACEHOLDER)
    expect(document.body.textContent).toContain('suggestions')
  })

  it('takes the kind from its PROP rather than assuming one', () => {
    // Non-vacuity for the assertion above, and the property c6-8 depends on when a second kind
    // gets a view: a hard-coded `'suggestions'` passes every test above and renders the wrong
    // noun the day a tier list is empty. The cast is what lets this file ask the question a
    // story early — the prop's type is deliberately narrow until c6-8 widens it.
    render(<SuggestionsView kind={'tier_list' as 'suggestions'} items={[]} />)

    expect(screen.getByText(emptyPushLine('tier_list'))).toBeInTheDocument()
  })

  it('is a bare paragraph and NOT a state panel (EXPERIENCE.md’s "no panel")', () => {
    const { container } = render(<SuggestionsView kind="suggestions" items={[]} />)

    const line = container.querySelector('.suggestions-view-empty')
    expect(line).not.toBeNull()
    expect(line?.tagName).toBe('P')
    // No second live region inside the dialog: the view's announcement is the heading's, and a
    // region here would announce the same arrival twice.
    expect(line).not.toHaveAttribute('aria-live')
    expect(screen.queryByRole('region')).toBeNull()
  })
})

describe('a non-empty push renders nothing YET — Q1’s ruling, made visible', () => {
  it('renders no line and no rows when there are items', () => {
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    // The empty-state line must not appear for a push that HAS content — the inverted branch is
    // the ordinary way a `length === 0` check goes wrong, and it would tell a reader with three
    // suggestions waiting that there is nothing to show.
    expect(container.querySelector('.suggestions-view-empty')).toBeNull()
    expect(container.textContent).toBe('')
  })

  it('renders nothing for a one-item push as well as a many-item one (boundary)', () => {
    // `length !== 0` rather than `length > 1` or a truthiness test: the boundary between the two
    // states is exactly one item, so it is asserted at exactly one item.
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM, ITEM, ITEM]} />)
    expect(container.textContent).toBe('')
  })
})

describe('the template is a template (non-vacuity for the gate next door)', () => {
  it('carries exactly one placeholder, and the builder fills it', () => {
    // `tests/empty-push-copy.test.ts` compares this constant against EXPERIENCE.md byte for
    // byte. This asserts the property that makes the comparison meaningful for a RENDERED line:
    // one hole, filled once, leaving no marker behind.
    expect(EMPTY_PUSH_TEMPLATE.split(KIND_PLACEHOLDER)).toHaveLength(2)
    expect(emptyPushLine('suggestions')).not.toContain(KIND_PLACEHOLDER)
    expect(emptyPushLine('suggestions')).toBe(
      'The agent sent an empty suggestions. Nothing to show — ask it for another pass.',
    )
  })
})
