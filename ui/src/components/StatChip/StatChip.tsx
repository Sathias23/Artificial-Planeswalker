import type { ReactNode } from 'react'

import './StatChip.css'

/**
 * StatChip — a micro label over a numeric value, with an optional delta (story c2-7, UX-DR11).
 *
 * PRESENTATION-ONLY (AC 5): no state, no hook, no fetch, no store, no event handler.
 *
 * THE 17px VALUE HAS NO `font-size` (AC 7, Q1). DESIGN.md's `components.stat-chip.value-size`
 * is 17px and the mock writes it as `font: var(--type-numeric); fontSize: 17` — which is a
 * lint ERROR here, measured: the `font-*` allowed-list admits only CSS-wide keywords, so the
 * one declaration this component's spec is built around has no legal spelling. The ruling: the
 * size comes from a ROLE TOKEN plus the numeric companion — `--type-heading` is `500 17px/1.3`
 * against `--type-numeric`'s `500 13px/1.4`, so it is the same weight at the size DESIGN.md
 * asks for, and `font-variant-numeric: var(--type-numeric-features)` restores the tabular
 * digits the heading role does not carry. See StatChip.css, where it is one rule block.
 *
 * THE DELTA IS TINTED BY NUMERIC SIGN (Q6), never by a string prefix. The mock's
 * `String(delta).startsWith('-')` is wrong three ways at once: `-0` stringifies to "0", a
 * Unicode minus is not a hyphen, and anything pre-formatted defeats it entirely. A FORMATTED
 * delta ("+$1.20") is a real future need and is deferred to its first consumer, which will add
 * a sibling prop in the open rather than overloading this one.
 */

export interface StatChipProps {
  /**
   * The micro label above the value. A `ReactNode`, unlike Panel's `title` — recorded, not
   * accidental (review ruling 2026-07-29): Q4 typed `title` as `string` because it doubles as
   * the region's `aria-label`, which must be a string in a hook-free component. This slot is
   * never an accessible name, so markup costs nothing. Emptiness is the CALLER's problem — a
   * chip is only mounted to show a stat, so an empty label is caller error, not a state this
   * component defends against the way Panel's optional slots must.
   */
  label: ReactNode
  /**
   * The value itself. A `ReactNode` because the CALLER owns formatting — "60", "17.5%" and
   * "$12.40" are all real stat values and none of them is a bare number this component could
   * have produced from one.
   */
  value: ReactNode
  /**
   * The change since the last reading. `> 0` renders "+n" tinted positive, `< 0` renders "-n"
   * tinted negative, and `0` renders "0" NEUTRAL with no sign — a zero delta is not an
   * improvement, and tinting it green would report "no change" as a win. A non-finite value
   * renders nothing at all rather than the text "NaN".
   */
  delta?: number
}

/** `+3` / `-2` / `0` — the sign is explicit for a change, and absent for no change. */
const signed = (delta: number): string => (delta > 0 ? `+${delta}` : String(delta))

export function StatChip({ label, value, delta }: StatChipProps) {
  /**
   * `Number.isFinite` FIRST, so `NaN`, `Infinity` and `-Infinity` never reach the sign
   * comparison — each of them would otherwise render its own name as the delta text.
   *
   * `Math.sign`, not `delta > 0 ? … : delta < 0 ? … : …` written out: `Math.sign(-0)` is `-0`,
   * and `-0 === 0` is true, so a negative zero lands on neutral through the same branch a
   * positive zero does. That is the member of this family every shortcut gets wrong, and it is
   * the reason the tone is derived rather than spelled out.
   */
  const hasDelta = delta !== undefined && Number.isFinite(delta)
  const sign = hasDelta ? Math.sign(delta) : 0
  const tone = sign > 0 ? 'positive' : sign < 0 ? 'negative' : 'neutral'

  return (
    <div className="stat-chip">
      <span className="stat-chip-label">{label}</span>
      <span className="stat-chip-row">
        <span className="stat-chip-value">{value}</span>
        {hasDelta ? (
          <span className={`stat-chip-delta stat-chip-delta-${tone}`}>{signed(delta)}</span>
        ) : null}
      </span>
    </div>
  )
}
