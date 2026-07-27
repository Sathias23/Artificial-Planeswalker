/* FIXTURE — the firing half of the inline-style ban (story c2-4 review, Brad's ruling
   2026-07-27). Meant to stay broken; `eslint.config.js` ignores tests/fixtures/**, and
   tests/lint-gates.test.ts lints this through the ESLint Node API with `ignore: false`.

   Every value below is one the CSS gates would have rejected instantly — an off-scale
   padding, a hard-coded rest shadow, a raw hex, a literal duration that the reduced-motion
   block cannot reach — and not one of them is visible to stylelint or to
   tests/token-usage.test.ts, because those stop at *.css. That is the whole point. */

export function InlineStyled() {
  return (
    <div
      style={{
        padding: '18px',
        boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
        color: '#8b93ff',
        transition: 'opacity 300ms',
      }}
    >
      Every one of these would fail the CSS gates. None of them is a .css file.
    </div>
  )
}

/* Even a single, innocent-looking property is the same hole: it is the precedent, and the
   next author copies the pattern rather than the value. */
export function OneInnocentProperty() {
  return <span style={{ marginTop: '4px' }}>4px is on the scale. It is still not a token.</span>
}
