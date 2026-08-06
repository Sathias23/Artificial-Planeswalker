/* FIXTURE — the acceptance half of the inline-style pair. Styling comes from a class, so the
   values live in a .css file where every c2-4 gate can see them.

   This is what c2-6 and c2-7 write. If this file ever starts reporting the inline-style rule,
   the ban has been over-tightened into something the first real component has to fight. */

export function ClassStyled() {
  return (
    <div className="panel">
      <span className="panel__title">Styled through a class, valued through tokens.</span>
    </div>
  )
}

/* `className` computed at runtime is still not an inline style — the rule keys on the `style`
   attribute specifically, not on anything dynamic. */
export function ConditionallyStyled({ isLive }: { isLive: boolean }) {
  return <div className={isLive ? 'deck-row deck-row--live' : 'deck-row'}>Row</div>
}

/* THE ONE SHAPE THE BAN ADMITS, ADDED BY STORY c4-8 (Q10, AC 17, AC 34 n′).

   The fixture named *clean* is the honest place for it: this file is the one that says "this
   shape is permitted", and it is asserted at ZERO messages for the inline-style rule in the
   same invocation that asserts inline-style-violation.tsx at exactly two.

   A data-driven bar height cannot be a class — the value is computed from the deck at render
   time — so `no-restricted-syntax` was NARROWED rather than disabled: an object literal whose
   keys are all DECLARED runtime channels passes, and the value is consumed by a `.css` rule
   (`height: var(--curve-bar-height)`) where stylelint and tests/token-usage.test.ts can both
   see it. Nothing about the token layer is weakened: this attribute carries a NUMBER, not a
   style.

   ONE property, and it is the whole allowlist. The c4-8 review tightened the hatch from the
   `/^--/` prefix to the exact channel NAME (a prefix admits `--surface-well`, a real token an
   attribute may not override), so this fixture carries the one declared channel; the
   second-property and wrong-name cases live in custom-property-violation.tsx, where they FIRE.

   THE CAST IS NOT OPTIONAL, AND IT CORRECTS THE STORY'S OWN PREMISE. c4-8's Q10 says a dynamic
   value "sets a CSS CUSTOM PROPERTY through the style attribute's own typing". Measured with
   `npx tsc -b --force` at React 19.2: it does not. `React.CSSProperties` extends csstype's
   `Properties`, which has no index signature for `--`-prefixed keys, so the object literal is
   `TS2353: '--curve-bar-height' does not exist in type 'Properties<…>'`. The escape hatch is
   real; the typing that was supposed to carry it is not. */
export function CustomPropertyStyled({ share }: { share: number }) {
  return (
    <div
      className="mana-curve-bar"
      style={{ '--curve-bar-height': `${share * 100}%` } as React.CSSProperties}
    />
  )
}

/* THE FALSE-POSITIVE HALF OF THE REVIEW'S DIRECT-CHILD CORRECTION. An object literal nested
   inside a permitted property's VALUE is not a style object at all — it is an argument to
   whatever computes the value. The shipped draft's descendant `:has` reached into it and
   errored; the anchored selector reads only the attribute's own top-level keys. */
const withUnit = (options: { scale: number }): string => `${options.scale}%`
export function NestedValueObject({ share }: { share: number }) {
  return (
    <div
      className="mana-curve-bar"
      style={{ '--curve-bar-height': withUnit({ scale: share * 100 }) } as React.CSSProperties}
    />
  )
}
