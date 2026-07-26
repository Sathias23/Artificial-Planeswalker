/**
 * The component half of AC 11. Renders through @testing-library/react under jsdom and
 * asserts on what a user can actually perceive, so emptying App.tsx turns the suite red —
 * a check the story requires to be demonstrated, not assumed.
 *
 * The jsdom environment, the jest-dom matchers and afterEach(cleanup) all come from the
 * `dom` vitest project in vite.config.ts; nothing needs setting up per file.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('renders the product name as the page heading', () => {
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Artificial Planeswalker' })).toBeVisible()
  })

  it('renders inside a main landmark', () => {
    render(<App />)

    expect(screen.getByRole('main')).toBeInTheDocument()
  })
})
