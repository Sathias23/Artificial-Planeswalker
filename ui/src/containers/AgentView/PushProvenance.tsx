import { Badge } from '../../components/Badge/Badge'
import type { PushProvenance as Provenance } from '../../state/deckProvenance'
import { PROVENANCE_MISSING_LABEL, STALE_BADGE, STALE_REASON_LINES, provenanceLabel } from './copy'
import './PushProvenance.css'

/**
 * Which saved deck a push is about, and whether it is stale (quick wins 1.5) — one quiet line.
 *
 * Presentational: the provenance is derived by `usePushProvenance` and handed in, so this renders
 * nothing for `null` (the push named no deck, or the deck list has not been read yet) and decides
 * nothing itself. It holds NO focusable element and NO live region: under the agent view's header
 * it sits outside the `aria-live` heading, and inside a history entry it is part of a button's
 * accessible name, where a focusable child would be invalid.
 *
 * `compact` is the history-entry form: a `<span>` (a button admits phrasing content only) carrying
 * the label and the badge but not the reason sentences, which would crowd a one-line row. The full
 * form is a `<p>` and states every reason.
 */
export function PushProvenance({
  provenance,
  compact = false,
}: {
  provenance: Provenance | null
  compact?: boolean
}) {
  if (provenance === null) return null
  const label =
    provenance.deckName === null ? PROVENANCE_MISSING_LABEL : provenanceLabel(provenance.deckName)
  const stale = provenance.stale.length > 0
  const parts = (
    <>
      <span className="push-provenance-deck">{label}</span>
      {stale ? <Badge tone="caution">{STALE_BADGE}</Badge> : null}
      {compact
        ? null
        : provenance.stale.map((reason) =>
            reason === 'missing' ? null : (
              <span key={reason} className="push-provenance-reason">
                {STALE_REASON_LINES[reason]}
              </span>
            ),
          )}
    </>
  )
  return compact ? (
    <span className="push-provenance push-provenance-compact" data-stale={stale}>
      {parts}
    </span>
  ) : (
    <p className="push-provenance" data-stale={stale}>
      {parts}
    </p>
  )
}
