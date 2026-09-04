import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Welcome } from './Welcome'

describe('Welcome (story 17.5)', () => {
  it('puts a DECORATIVE hero above the unchanged no-active-deck panel', () => {
    const { container } = render(<Welcome decks={['Boros Aggro', 'Sultai Midrange']} />)

    const hero = container.querySelector('img.welcome-hero')!
    expect(hero).not.toBeNull()
    // Decorative, WCAG-spelled: `alt=""`, served same-origin, never hot-linked.
    expect(hero.getAttribute('alt')).toBe('')
    // An IMPORTED asset, not a public path: Vite resolves the import, so the built bundle emits
    // it under `assets/` with a content hash and `spa.py` serves that immutable. The assertion is
    // therefore "same-origin, from the module graph", not a literal — a literal would be pinning
    // the dev server's own URL shape.
    const src = hero.getAttribute('src') ?? ''
    expect(src.startsWith('http')).toBe(false)
    expect(src).toContain('hero')
    expect(src.endsWith('.jpg')).toBe(true)
    // The intrinsic size attributes match the committed file, so the reserved box is the real
    // aspect ratio rather than the pre-recompression one.
    expect(hero.getAttribute('width')).toBe('1000')
    expect(hero.getAttribute('height')).toBe('667')
    // Above, not in: the image precedes the panel region in document order and is not inside it.
    const panel = screen.getByRole('region', { name: 'No deck on the glass.' })
    expect(panel.contains(hero)).toBe(false)
    expect(hero.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('keeps the deck names as a non-clickable list — no link, no button in the subtree', () => {
    const { container } = render(<Welcome decks={['Boros Aggro', 'Sultai Midrange']} />)

    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(container.querySelectorAll('a, button, [tabindex]')).toHaveLength(0)
  })

  it('renders no list at all on a fresh install with no decks', () => {
    render(<Welcome decks={[]} />)

    expect(screen.queryByRole('list')).toBeNull()
    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeInTheDocument()
  })
})
