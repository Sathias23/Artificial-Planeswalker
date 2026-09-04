/**
 * The attribution sentence, and the ONLY place it lives.
 *
 * This is the copy contract applied to the one string in the app that is a **licensing
 * obligation** rather than a design choice. `DESIGN.md:375` says so in bold — "Required on every
 * surface — this is a condition of public release, not a design choice" — and NFR-08 and UX-DR32
 * say it twice more. Every other sentence in the app could be slightly wrong and be corrected
 * later; this one shipping wrong is a licensing defect.
 *
 * ================= WHY THE ARTEFACT IS `DESIGN.md` AND NOT `EXPERIENCE.md` ===============
 *
 * The verbatim-gate mechanism was built against `EXPERIENCE.md`, and this module inherits the
 * MECHANISM, not the source file.
 * `EXPERIENCE.md`'s Voice-and-Tone table has **no footer row**: its footer entry (`:101`) is
 * BEHAVIOURAL ("Static. … links persistently underlined … and open in a new tab"), and it never
 * writes the words. The words exist in exactly one artefact — `DESIGN.md:375`, inside one pair
 * of straight double quotes — so that is what `tests/attribution.test.ts` reads.
 *
 * The rule this generalises to, and the one a later module should apply rather than copying the
 * file path: **a copy string is gated against the artefact that WROTE it.** Two artefacts, two
 * gates, deliberately — `copy.test.ts` owns EXPERIENCE.md's states, this module's gate owns
 * DESIGN.md's attribution.
 *
 * ================= WHY THIS IS A LIST OF PARTS AND NOT THREE STRINGS ====================
 *
 * Two runs of the sentence are links ("Scryfall", "Wizards of the Coast Fan Content Policy") and
 * the rest is text. Authoring three separate text strings beside two link labels would be **two
 * spellings of one value**, which is precisely what a verbatim gate exists to prevent: the five
 * fragments could drift apart while each remained individually plausible, and no assertion
 * against the artefact would notice.
 *
 * So the sentence is a list of parts in SOURCE ORDER, each tagged link-or-text, and
 * `sentenceOf` re-joins them. The gate asserts that the join is byte-for-byte `DESIGN.md`'s
 * sentence. Nothing here is authored that the artefact did not write — the footer merely
 * knows which two runs are links. This is the `bodyOf` shape, and `copy.ts:164-171` is the
 * worked example it was taken from.
 *
 * ================= THE HREFS ARE THE `NOTICE` FILE'S, NOT NEW ONES ======================
 *
 * Both URLs are the canonical ones the repository's own `NOTICE` already uses —
 * `NOTICE:11` and `NOTICE:25` — so the app and the licence documentation cannot drift into
 * pointing at two different pages for the same obligation.
 *
 * NOTHING IS FETCHED. These are hrefs a human clicks, which is why adding two hosts to
 * `REVIEWED_HOSTS` in `tests/fonts.test.ts` does not touch the offline guarantee (NFR-06): the
 * app still renders identically with the network blocked. See that file for the protocol.
 */

/** A run of the sentence: plain text, or text that is a link to `href`. */
export interface AttributionPart {
  /** One run of `DESIGN.md`'s sentence, verbatim, in source order. */
  readonly text: string
  /** Present iff this run is a link. Absent runs render as plain text. */
  readonly href?: string
}

/**
 * The attribution sentence, split at its two link boundaries.
 *
 * The leading and trailing spaces inside the text runs are load-bearing — they are part of
 * `DESIGN.md`'s sentence, and the concatenation invariant in `tests/attribution.test.ts` is what
 * keeps them so. Do not "tidy" them; the gate will fail, correctly.
 */
export const ATTRIBUTION: readonly AttributionPart[] = [
  { text: 'Card data and imagery courtesy of ' },
  { text: 'Scryfall', href: 'https://scryfall.com/docs/api' },
  { text: '. Unofficial Fan Content permitted under the ' },
  {
    text: 'Wizards of the Coast Fan Content Policy',
    href: 'https://company.wizards.com/en/legal/fancontentpolicy',
  },
  { text: '. Not approved/endorsed by Wizards.' },
]

/**
 * The sentence as `DESIGN.md` wrote it: every part, in source order, joined by nothing.
 *
 * Exported rather than inlined into the test for the reason `bodyOf` gives — the thing
 * asserted must be the thing the module can PRODUCE. A test that re-implemented the join would
 * be asserting its own arithmetic, and would stay green while the renderer drifted.
 *
 * No `parts` parameter, by the same doctrine that gives the component no props: every caller
 * calls it bare, and a parameter would admit joins the gate never covers. There is one
 * sentence; this produces it.
 */
export const sentenceOf = (): string => ATTRIBUTION.map((part) => part.text).join('')
