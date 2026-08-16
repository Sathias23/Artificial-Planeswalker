/**
 * The deck-refetch announcement (story c7-5, UX-DR45).
 *
 * ================= ONE SENTENCE, TRANSCRIBED, WITH A HOLE IN IT ========================
 *
 * "Deck updated — 62 cards" is the worked example BOTH artefacts carry — `EXPERIENCE.md`'s
 * live-region row ("Deck refetches announce once per coalesced refetch, on completion") and the
 * epic's Story 7.5 AC — spaced em dash U+2014 included, the same separator the connection pill's
 * `DECK_SEPARATOR` cites this very row for. So the template is transcribed rather than authored,
 * and `tests/deck-announcement-copy.test.ts` gates the shipped builder against both artefacts,
 * the `pin-announcement-copy.test.ts` shape: copy is gated against whatever wrote it.
 *
 * ================= WHAT THE NUMBER IS, AND WHY THE SUM LIVES HERE ======================
 *
 * The announced count is EVERYTHING ON THE GLASS — `mainboard_count + sideboard_count`, the
 * payload's own numbers. By the conservation identity (`deckGroups.ts`: commander + mainboard
 * quantities sum to `mainboard_count`, sideboard to `sideboard_count`) this equals the sum of
 * every group-header count, which is the sibling accessible signal UX-DR43 names — so the
 * announcement and the headers can never disagree, and a sideboard-only mutation still moves the
 * announced number. The FOLD is in this builder rather than in the announcer so the whole
 * sentence — words, dash, arithmetic and pluralisation — has one address and one gate.
 *
 * ================= THE SINGULAR IS INVENTED, AND THIS COMMENT SAYS SO ==================
 *
 * No artefact states a one-card form. `ManaCurve/copy.ts:109-111` is the recorded precedent for
 * inventing one in the open — its `cards` noun singularises on the count being exactly 1 — and
 * the identical rule applies here: "Deck updated — 1 card". Zero keeps the plural ("0 cards"),
 * which is the honest sentence for a refetch that settles an emptied deck.
 *
 * The COUNTS are data off the wire and the deck's NAME is deliberately not in this sentence —
 * a copy module that interpolated more than the number would blur the data line every entry in
 * `COPY_MODULES` draws.
 *
 * `imports: []` for the settled `TS2835` reason: `ui/tests` is the `nodenext` project and `src/`
 * the `bundler` one, so `tests/deck-announcement-copy.test.ts` may import this module only while
 * it has no relative imports of its own. The import-freedom is load-bearing, not conventional.
 */

/**
 * The whole announcement, from the payload's two counts.
 *
 * Args:
 *   mainboardCount: `DeckDetail.mainboard_count`, verbatim (commander included, per the backend's
 *     own split).
 *   sideboardCount: `DeckDetail.sideboard_count`, verbatim.
 *
 * Returns:
 *   The string the polite `deck-announcement` region speaks, e.g. "Deck updated — 62 cards".
 */
export const deckUpdatedAnnouncement = (mainboardCount: number, sideboardCount: number): string => {
  const count = mainboardCount + sideboardCount
  return `Deck updated — ${count} ${count === 1 ? 'card' : 'cards'}`
}
