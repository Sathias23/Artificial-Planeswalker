/**
 * The format-check fixtures every format-check test draws from.
 *
 * ================= WHY ONE MODULE, AND WHY IT IS A PLAIN `.ts` =========================
 *
 * **One**, because two fixture sets claiming to model the same measured corpus drift the moment
 * one of them is corrected — `tests/unit/companion/conftest.py`'s own header records that
 * happening. Three files need these reports (`formatCheck.test.ts`, `FormatCheck.test.tsx`,
 * and the pins in `formatCheck.fixtures.test.ts`), and they read the same bytes.
 *
 * **A plain `.ts`, not a `.test.ts`.** Importing a test file registers its describes in every
 * importer's collection, so data AND pins in one `.test.ts` would run the pins once per
 * importer, silently inflating the suite's pass count with duplicates. Data lives here; the
 * pins live in `formatCheck.fixtures.test.ts`, which imports this module and runs once.
 *
 * That classification has a price this header names rather than hides: a plain `src/` module is
 * scanned by the source-level gates a test file is exempt from. The six `detail` strings are
 * **wire data, not copy** — authored by `src/logic/deck_validator.py` and arriving over the
 * network exactly as a card name does — and the bodies must carry `is_legal` because
 * a fixture models the real response shape. So this file is registered BY NAME in the two gates
 * that would otherwise flag it: `tests/copy-rules.test.ts`'s `WIRE_FIXTURE_MODULES` (with the
 * data-not-copy reason) and the `is_legal` scan in `tests/format-check-source.test.ts` (a fixture
 * describing the field is not the app binding it). A NAMED registry entry with a reason, rather
 * than the blanket test-file exemption.
 *
 * ================= EVERY FIXTURE IS REAL, OR SAYS EXACTLY WHAT IS NOT ==================
 *
 * Measured read-only, driving the **real ASGI app in-process** against the shipped
 * database. There is no third category: a fixture is either a **verified real** response or
 * **declared synthetic in place**, with the declaration naming what is real about it and what is
 * not. Five of the states this panel must render have **zero** real instances in the corpus, and
 * each one below names the honest route that produced its sentences.
 */

import type { FormatCheckReport, FormatCheckRow } from '../api/schema'

/** The permanent rotation advisory. 86 characters, on **40 of 40 decks, forever**. */
export const ROTATION_ADVISORY: FormatCheckRow = {
  check: 'rotation',
  status: 'advisory',
  detail: 'Rotation exposure cannot be checked: the local card data carries no set release dates.',
}

/**
 * ✅ **VERIFIED REAL.** `GET /api/deck/{id}/format-check` for a real all-pass Standard deck
 * (`Temur Dragonstorm v2`), verbatim. 195 of the corpus's 240 rows say one of these five
 * sentences; this is what 35 of the 40 real decks look like.
 */
export const ALL_PASS_REPORT: FormatCheckReport = {
  is_legal: true,
  format: 'standard',
  format_recognized: true,
  mainboard_count: 60,
  sideboard_count: 0,
  rows: [
    { check: 'legality', status: 'pass', detail: 'Every card is legal in standard.' },
    { check: 'size', status: 'pass', detail: 'Mainboard has 60 cards; the minimum is 60.' },
    {
      check: 'copy_limit',
      status: 'pass',
      detail: 'No card exceeds the copy limit; basic lands are exempt.',
    },
    { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
    { check: 'banned', status: 'pass', detail: 'No card is banned in standard.' },
    ROTATION_ADVISORY,
  ],
}

/**
 * ✅ **VERIFIED REAL.** `Kotis, the Fangkeeper — 100-card Brawl` — the **only** deck in the corpus
 * with a real legality violation.
 *
 * It carries the measurement in one body: the size row says `the minimum is 60` on a deck whose
 * format is **exact-100** (`plugin/skills/format-legality/SKILL.md:77`), and all 18 brawl decks
 * sit at exactly 100, so the sentence is wrong for **45% of the deck table** while no badge flips.
 * `is_legal` is `false` here **and** there is a violation row, which is the ordinary case; the
 * trap is `FORMATLESS_REPORT` below.
 */
export const BRAWL_VIOLATION_REPORT: FormatCheckReport = {
  is_legal: false,
  format: 'brawl',
  format_recognized: true,
  mainboard_count: 100,
  sideboard_count: 0,
  rows: [
    { check: 'legality', status: 'violation', detail: "'Pym Particles' is not legal in brawl." },
    { check: 'size', status: 'pass', detail: 'Mainboard has 100 cards; the minimum is 60.' },
    {
      check: 'copy_limit',
      status: 'pass',
      detail: 'No card exceeds the copy limit; basic lands are exempt.',
    },
    { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
    { check: 'banned', status: 'pass', detail: 'No card is banned in brawl.' },
    ROTATION_ADVISORY,
  ],
}

/**
 * ✅ **VERIFIED REAL.** `Iron Man, Modern Marvel — reminder`, a one-card `historic` deck — and the
 * live singular/plural defect:
 * **`'Mainboard has 1 cards; the minimum is 60.'`** It is Python copy, in
 * `deck_validator.py:693`, and it is ledgered rather than fixed here (Python is untouched).
 */
export const ONE_CARD_REPORT: FormatCheckReport = {
  is_legal: false,
  format: 'historic',
  format_recognized: true,
  mainboard_count: 1,
  sideboard_count: 0,
  rows: [
    { check: 'legality', status: 'pass', detail: 'Every card is legal in historic.' },
    { check: 'size', status: 'violation', detail: 'Mainboard has 1 cards; the minimum is 60.' },
    {
      check: 'copy_limit',
      status: 'pass',
      detail: 'No card exceeds the copy limit; basic lands are exempt.',
    },
    { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
    { check: 'banned', status: 'pass', detail: 'No card is banned in historic.' },
    ROTATION_ADVISORY,
  ],
}

/**
 * ⚠️ **DECLARED SYNTHETIC — a REAL deck with its format overridden to `'potato'`.**
 *
 * `format_recognized: false` has **zero** real instances: all 40 decks carry a format this project
 * knows. Produced by taking the real all-pass Standard deck above, setting `format = 'potato'`,
 * and running the real `format_check` — so the two advisory sentences are the backend's, not
 * invented. What is synthetic is the format string alone.
 *
 * **This is the `is_legal` trap, on demand**: `is_legal` is `false`
 * while **not one row is a violation**. It is the fixture the trap pin drives — and note what the
 * backend does NOT change: `size`, `copy_limit` and `sideboard` keep answering normally, so this
 * is six ordinary rows and never a second layout.
 */
export const FORMATLESS_REPORT: FormatCheckReport = {
  is_legal: false,
  format: 'potato',
  format_recognized: false,
  mainboard_count: 60,
  sideboard_count: 0,
  rows: [
    {
      check: 'legality',
      status: 'advisory',
      detail: "'potato' is not a recognized format, so legality could not be checked.",
    },
    { check: 'size', status: 'pass', detail: 'Mainboard has 60 cards; the minimum is 60.' },
    {
      check: 'copy_limit',
      status: 'pass',
      detail: 'No card exceeds the copy limit; basic lands are exempt.',
    },
    { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
    {
      check: 'banned',
      status: 'advisory',
      detail: "'potato' is not a recognized format, so banned cards could not be checked.",
    },
    ROTATION_ADVISORY,
  ],
}

/**
 * ⚠️ **DECLARED SYNTHETIC — the same real deck with a BLANK format.**
 *
 * The other spelling of the same state, and it is a different sentence rather than the same one
 * with an empty quote: `_unanswerable` deliberately writes prose when there is no format to name,
 * because `'' is not a recognized format` is true and reads as a bug. Measured, not paraphrased.
 */
export const NO_FORMAT_REPORT: FormatCheckReport = {
  ...FORMATLESS_REPORT,
  format: '',
  rows: [
    {
      check: 'legality',
      status: 'advisory',
      detail: 'There is no format to check against, so legality could not be checked.',
    },
    ...FORMATLESS_REPORT.rows.slice(1, 4),
    {
      check: 'banned',
      status: 'advisory',
      detail: 'There is no format to check against, so banned cards could not be checked.',
    },
    ROTATION_ADVISORY,
  ],
}

/**
 * ⚠️ **DECLARED SYNTHETIC — a REAL deck re-checked against a format it was not saved in.**
 *
 * A `copy_limit` / `singleton` violation has **zero** real instances, and so does the `(+N more)`
 * suffix — every offending deck in the corpus has exactly **one** raw violation. Produced by
 * taking the real all-pass Standard deck and running the real `format_check` against
 * `'commander'`: a real deck, a real card (`Candy Trail`), a real rule, a **synthetic format**.
 *
 * It is the only fixture carrying `(+15 more)`, which is the whole reason it exists — `_summarise`
 * has no live instance and its suffix would otherwise ship unrendered. Note the row it lands on:
 * `singleton` and `copy_limit` are two validator rules mapping to **one** row.
 */
export const SINGLETON_VIOLATION_REPORT: FormatCheckReport = {
  is_legal: false,
  format: 'commander',
  format_recognized: true,
  mainboard_count: 60,
  sideboard_count: 0,
  rows: [
    { check: 'legality', status: 'pass', detail: 'Every card is legal in commander.' },
    { check: 'size', status: 'pass', detail: 'Mainboard has 60 cards; the minimum is 60.' },
    {
      check: 'copy_limit',
      status: 'violation',
      detail:
        "2 copies of 'Candy Trail'; commander is a singleton format (max 1 copy of any " +
        'non-basic card). (+15 more)',
    },
    { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
    { check: 'banned', status: 'pass', detail: 'No card is banned in commander.' },
    ROTATION_ADVISORY,
  ],
}

/**
 * ⚠️ **DECLARED SYNTHETIC — the real brawl deck plus one REAL brawl-banned card.**
 *
 * A `banned` violation has **zero** real instances: no saved deck holds a banned card in any
 * format. `Time Warp` is a real card whose stored `legalities.brawl` is literally `'banned'`
 * (measured; 35 corpus cards are banned in brawl), added to the real `Kotis` deck and run through
 * the real `format_check`. The card is real, the rule is real, the format is real; the deck
 * membership is what is synthetic.
 *
 * It also carries a **sideboard** violation, which likewise has zero real instances (35 of 40
 * decks have no sideboard at all) — produced separately by declaring a real deck's rows sideboard
 * — so this one fixture renders **three violation rows at once**, which no real deck does.
 *
 * ⚠️ And the composite is one step MORE synthetic than its ingredients: the two halves are each
 * real backend output, but **this merged body as a whole was never emitted by any real
 * `format_check` run** — no single request produced these six rows together. The ingredients are
 * real; their union is the synthetic part.
 */
export const MULTI_VIOLATION_REPORT: FormatCheckReport = {
  is_legal: false,
  format: 'brawl',
  format_recognized: true,
  mainboard_count: 101,
  sideboard_count: 60,
  rows: [
    { check: 'legality', status: 'violation', detail: "'Pym Particles' is not legal in brawl." },
    { check: 'size', status: 'pass', detail: 'Mainboard has 101 cards; the minimum is 60.' },
    {
      check: 'copy_limit',
      status: 'pass',
      detail: 'No card exceeds the copy limit; basic lands are exempt.',
    },
    {
      check: 'sideboard',
      status: 'violation',
      detail: 'Sideboard has 60 cards; the maximum is 15.',
    },
    { check: 'banned', status: 'violation', detail: "'Time Warp' is banned in brawl." },
    ROTATION_ADVISORY,
  ],
}

/** Every fixture in this module, so the pins over it cannot be selective. */
export const ALL_FIXTURES: { name: string; report: FormatCheckReport }[] = [
  { name: 'ALL_PASS_REPORT', report: ALL_PASS_REPORT },
  { name: 'BRAWL_VIOLATION_REPORT', report: BRAWL_VIOLATION_REPORT },
  { name: 'ONE_CARD_REPORT', report: ONE_CARD_REPORT },
  { name: 'FORMATLESS_REPORT', report: FORMATLESS_REPORT },
  { name: 'NO_FORMAT_REPORT', report: NO_FORMAT_REPORT },
  { name: 'SINGLETON_VIOLATION_REPORT', report: SINGLETON_VIOLATION_REPORT },
  { name: 'MULTI_VIOLATION_REPORT', report: MULTI_VIOLATION_REPORT },
]
