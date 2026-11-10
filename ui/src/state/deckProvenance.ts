/**
 * Which saved deck a push is about, and whether it still describes that deck (quick wins 1.5).
 *
 * A push names its deck by `payload.deck_id`, the agent's own claim, which the push tools never
 * check. This slice answers the two questions the claim raises — *what is that deck called* and
 * *has it changed since* — from the one read-only route that already lists every saved deck with
 * its `updated_at`: `GET /api/decks`. The MCP tool cannot answer the second question: it is
 * sessionless, and staleness needs the deck's CURRENT edit time, which only a read at display
 * time has.
 *
 * ================= WHEN IT READS =========================================================
 *
 * Never on a timer and never before it is needed. {@link refreshDeckProvenance} runs when a push
 * carrying a `deck_id` arrives, and that first call sets {@link DeckProvenanceState.wanted}; from
 * then on {@link refreshDeckProvenanceIfWanted} re-reads on `deck_changed` and on each return to
 * `'live'` (`connection.ts`), so an edit made during an outage is still seen. A session whose
 * agent never names a deck makes no extra request at all.
 *
 * Reads are latest-wins by generation, and a failed read KEEPS the previous map: one lost read
 * must not turn every label back into nothing. Before the first successful read, nothing is
 * claimed — no label and no stale marker — because "unknown" is not "missing".
 *
 * ================= WHAT IT DOES NOT DO ====================================================
 *
 * It writes nothing anywhere but this slice (AD-2: the companion only reads), and the label it
 * feeds follows each push's OWN `deck_id`, never the active deck: a history entry for deck A
 * still says "For A" after the glass switches to B.
 */

import { useMemo } from 'react'
import { create } from 'zustand'

import { readDeckSummaries } from '../api/client'
import type { AgentViewContent } from './agentView'
import { useDeckStore } from './deck'

/** What the slice remembers of one saved deck. */
export interface DeckProvenanceEntry {
  readonly name: string
  readonly updatedAt: string
}

export interface DeckProvenanceState {
  /** Whether any read has succeeded. `false` means "unknown", and nothing is claimed from it. */
  readonly loaded: boolean
  /** Whether some push has named a deck this session, so later triggers should re-read. */
  readonly wanted: boolean
  /** The saved decks by id, as of the last successful read. Looked up with `Object.hasOwn`. */
  readonly decks: Readonly<Record<string, DeckProvenanceEntry>>
}

export const INITIAL_DECK_PROVENANCE: DeckProvenanceState = {
  loaded: false,
  wanted: false,
  decks: {},
}

/** One store, written only by this module. */
export const useDeckProvenanceStore = create<DeckProvenanceState>(() => INITIAL_DECK_PROVENANCE)

/** Bumped by every read and by the reset, so only the newest read may write. */
let generation = 0

/** Forget everything and discard any read in flight. **For tests only.** */
export const resetDeckProvenance = (): void => {
  generation += 1
  useDeckProvenanceStore.setState(INITIAL_DECK_PROVENANCE, true)
}

/**
 * The rows as a lookup with NO prototype: a wire id is attacker-adjacent input, and `'__proto__'`
 * must be an ordinary key here rather than a reach into `Object.prototype`.
 */
const lookupOf = (
  rows: readonly { id: string; name: string; updated_at: string }[],
): Record<string, DeckProvenanceEntry> => {
  const decks = Object.create(null) as Record<string, DeckProvenanceEntry>
  for (const row of rows) decks[row.id] = { name: row.name, updatedAt: row.updated_at }
  return decks
}

/**
 * Read `GET /api/decks` once and file the answer. Marks the slice wanted first, so a push that
 * arrives during an outage still arms the later re-reads. Latest-wins: a read overtaken by a
 * newer one writes nothing. A failed read writes nothing either, keeping the previous map.
 */
export const refreshDeckProvenance = async (): Promise<void> => {
  generation += 1
  const mine = generation
  if (!useDeckProvenanceStore.getState().wanted) useDeckProvenanceStore.setState({ wanted: true })
  const outcome = await readDeckSummaries()
  if (mine !== generation || outcome.kind !== 'summaries') return
  useDeckProvenanceStore.setState({ loaded: true, decks: lookupOf(outcome.decks) })
}

/** Re-read only if some push has named a deck this session — the `deck_changed`/reconnect hook. */
export const refreshDeckProvenanceIfWanted = (): void => {
  if (useDeckProvenanceStore.getState().wanted) void refreshDeckProvenance()
}

/** Why a push no longer describes the deck on screen. */
export type StaleReason = 'missing' | 'edited' | 'other_deck'

/** What the provenance line shows: the deck's name (`null` when it is no longer saved) and why it is stale. */
export interface PushProvenance {
  readonly deckName: string | null
  readonly stale: readonly StaleReason[]
}

/** An ISO instant as milliseconds, or `null` for anything `Date` cannot read. */
const instantOf = (value: unknown): number | null => {
  if (typeof value !== 'string') return null
  const at = new Date(value).getTime()
  return Number.isNaN(at) ? null : at
}

/**
 * The provenance of one push, or `null` for "say nothing": the push named no deck, or no read
 * has succeeded yet. Pure, so every row of the I/O matrix is a plain call.
 *
 * - `missing`: the id is absent from a loaded answer — the deck was deleted, or never existed.
 * - `edited`: the deck's `updated_at` is later than the push's `ts`. Either one unparseable makes
 *   no claim: a clock that cannot be read cannot say the deck moved.
 * - `other_deck`: a deck is displayed and it is not this one. With no deck displayed there is no
 *   "deck on screen" to disagree with.
 */
export const provenanceOf = (
  deckId: string | null | undefined,
  ts: unknown,
  entry: DeckProvenanceEntry | undefined,
  loaded: boolean,
  displayedId: string | null,
): PushProvenance | null => {
  if (deckId === null || deckId === undefined || !loaded) return null
  const stale: StaleReason[] = []
  if (entry === undefined) {
    stale.push('missing')
  } else {
    const sent = instantOf(ts)
    const edited = instantOf(entry.updatedAt)
    if (sent !== null && edited !== null && edited > sent) stale.push('edited')
  }
  if (displayedId !== null && displayedId !== deckId) stale.push('other_deck')
  return { deckName: entry === undefined ? null : entry.name, stale }
}

/**
 * The provenance of one push (or of nothing), live: it re-derives when the deck list is re-read
 * and when the displayed deck changes. Every selector returns a primitive or a STORED reference,
 * never a fresh object, so a write elsewhere in either slice cannot loop a render.
 */
export const usePushProvenance = (content: AgentViewContent | null): PushProvenance | null => {
  const deckId = content?.deckId
  const ts = content?.ts
  const loaded = useDeckProvenanceStore((state) => state.loaded)
  const entry = useDeckProvenanceStore((state) =>
    deckId !== undefined && Object.hasOwn(state.decks, deckId) ? state.decks[deckId] : undefined,
  )
  const displayedId = useDeckStore((slice) =>
    slice.deck.status === 'deck' ? slice.deck.detail.id : null,
  )
  return useMemo(
    () => provenanceOf(deckId, ts, entry, loaded, displayedId),
    [deckId, ts, entry, loaded, displayedId],
  )
}
