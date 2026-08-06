/* FIXTURE — the FIRING half of story c4-8's narrowing of the inline-style ban (Q10, AC 17,
   AC 34 n).

   `eslint.config.js`'s `no-restricted-syntax` reserved a custom-property escape hatch for "a
   computed bar height in c4-8" by name, on condition the story changed the rule in the open.
   It did. This file is the proof that the change NARROWED rather than loosened: every component
   below is a `style` attribute that must still be an error afterwards.

   Its own file, not `inline-style-violation.tsx`: that fixture is pinned at exactly 2 messages
   and has been since c2-4, and the pin is what proves the report stayed per-ATTRIBUTE rather
   than becoming per-property. Growing it would destroy the assertion the narrowing is checked
   with.

   The four cases at the bottom joined at the c4-8 REVIEW, which found the shipped draft's
   descendant `:has(ObjectExpression …)` read "contains a compliant literal somewhere" as "IS a
   compliant literal" — so a call or a ternary could smuggle arbitrary properties past all three
   selectors — and found the `/^--/` prefix test admitted `--surface-well`, a REAL design token
   an attribute may not override. The rule now anchors on the attribute's own value wrapper and
   matches the channel allowlist by exact NAME.

   Meant to stay broken; `eslint.config.js` ignores tests/fixtures/**, and
   tests/lint-gates.test.ts lints this through the ESLint Node API with `ignore: false`. */

const someObject = { color: 'red' }
const identity = (style: object): object => style

/* The ordinary case, unchanged by the amendment: a real CSS property set from TSX. */
export function PlainProperty() {
  return <div style={{ height: '62%' }} />
}

/* On the spacing scale and still not a token — the c2-4 argument, restated because a narrowing
   is exactly when someone re-tests whether the "innocent" value slipped through. */
export function OnScaleProperty() {
  return <span style={{ marginTop: '4px' }} />
}

/* ONE non-permitted property re-opens the whole hole. This is the case a rule asking "does it
   contain a custom property?" would wave through, and it is why the property test is NEGATED —
   "has a property that is not a declared channel" — rather than affirmed. */
export function MixedProperties() {
  return <div style={{ '--bar-height': '62%', color: 'red' } as React.CSSProperties} />
}

/* A style attribute that is not a literal object hides its keys from every static reader, so it
   cannot be shown to be custom-property-only. */
export function NotALiteral() {
  return <div style={someObject} />
}

/* A spread hides them just as effectively. */
export function SpreadProperties() {
  return <div style={{ ...someObject, '--bar-height': '62%' } as React.CSSProperties} />
}

/* REVIEW CASE (c4-8): a call WRAPPING a compliant literal is still not a literal — the call's
   RETURN is what reaches the DOM, and no static reader can prove what that is. The shipped
   draft's descendant test saw the inner object and waved the whole attribute through. */
export function WrappedInACall() {
  return <div style={identity({ '--curve-bar-height': '62%' })} />
}

/* REVIEW CASE (c4-8): a ternary is the same evasion with different punctuation — one arm is
   compliant, the other arm is whatever it likes. */
export function WrappedInATernary({ tall }: { tall: boolean }) {
  return (
    <div style={tall ? ({ '--curve-bar-height': '100%' } as React.CSSProperties) : someObject} />
  )
}

/* REVIEW CASE (c4-8): a `--`-prefixed key can name a REAL design token. Setting it inline
   re-themes every descendant that consumes the token, and no stylesheet scan can see the write
   — which is why the hatch is an exact-name allowlist rather than a prefix test. */
export function TokenOverride({ colour }: { colour: string }) {
  return <div style={{ '--surface-well': colour } as React.CSSProperties} />
}

/* REVIEW CASE (c4-8): a custom property that is NOT a declared channel — right prefix, wrong
   name. The allowlist is the one in eslint.config.js beside RUNTIME_CUSTOM_PROPERTIES's in
   tests/token-usage.test.ts; joining it is a story-level act, not a spelling. */
export function UndeclaredChannel({ share }: { share: number }) {
  return <div style={{ '--curve-bar-index': share } as React.CSSProperties} />
}
