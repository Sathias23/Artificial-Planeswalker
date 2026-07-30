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
