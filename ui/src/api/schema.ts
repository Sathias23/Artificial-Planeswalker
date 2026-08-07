/**
 * The one module that reads the generated wire types (AD-12, story c2-3 Decide-once #2).
 *
 * `types.d.ts` is generated verbatim from the backend's own `app.openapi()` and is shaped for a
 * generator, not for a reader: reaching a response body means indexing
 * `components['schemas'][…]` or `paths['/x']['get']['responses'][200]['content']['application/json']`.
 * Every module that does that for itself invents its own spelling of one shape, and four stories
 * later the same type has five names. So the indexing happens **here, once**, and the rest of
 * `ui/src` imports a narrow alias.
 *
 * Two rules, both enforced rather than documented:
 *
 * 1. **Nothing outside `src/api/` imports `./types` directly.** Add an alias below, then use the
 *    alias.
 * 2. **Nothing outside `src/api/` re-declares a shape the backend already describes** — no
 *    hand-written `interface HealthResponse`. `ui/tests/wire-contract.test.ts` reads the
 *    `components.schemas` keys out of the committed `openapi.json` and fails on any such
 *    declaration, so the rule grows on its own — it did exactly that when **c3-1** added the four
 *    deck models, with no edit to the test, and it will again when **c5-1** adds the event
 *    envelope.
 *
 * `import type` / `export type` only: `verbatimModuleSyntax` is on, and nothing about a `.d.ts`
 * may reach the runtime bundle.
 */

import type { components } from './types'

/** Every named shape in `components.schemas`, keyed by its Pydantic class name. */
type Schemas = components['schemas']

/**
 * The body of `GET /health` — the companion's unauthenticated identity probe (FR-14).
 *
 * `status` is a `'ok'` literal, not `string`: it is the closed token the backend's
 * `Literal["ok"]` declares, and `ui/src/api/schema.test.ts` pins it that way.
 */
export type HealthResponse = Schemas['HealthResponse']

/** The body of every non-2xx response: the reason token, and nothing else (AD-16). */
export type ErrorResponse = Schemas['ErrorResponse']

/**
 * One entry of `GET /api/decks`' bare array: a saved deck's metadata and its three counts.
 *
 * The first alias with a RUNTIME consumer (**c3-9**), and it is deliberately narrow in how it is
 * used: this story's poll reads `name` and nothing else, because the only thing it renders is the
 * `no-active-deck` panel's deck list (`EXPERIENCE.md`: *"names only, non-clickable — the agent
 * drives"*). **c4-2** owns the deck bootstrap and is the story that reads the counts; it extends
 * this alias's consumer rather than adding a second one.
 */
export type DeckSummary = Schemas['DeckSummary']

/**
 * The body of `GET /api/cards/{card_id}`: everything known about one printing.
 *
 * **Consumer: `readCard` in `src/api/client.ts`, and the `hydrated` tier of the card cache**
 * (`src/state/cards.ts`, story c4-1). This is the *expensive* half of the two-tier hydration
 * contract — measured on the largest real deck (99 tiles), the full rows are **212,436 bytes over
 * 99 requests** against **38,182 bytes in one** for the summaries below, a 5.6× ratio. So it is
 * fetched per id, on demand, and never for a whole deck.
 *
 * Ledgered on c4-1 since c3-2 (*"`Card` is now a banned type name across all of `ui/`, and there
 * is no sanctioned alias"*): c3-2 declined to add it because an export with no consumer is dead
 * code. This commit is the one that gives it one.
 */
export type Card = Schemas['Card']

/**
 * The bounded card fields a list response carries: name, mana cost, cmc, type line, oracle text,
 * colours, rarity, set code — no legalities, no images, no faces.
 *
 * **Consumer: the `summary` tier of the card cache** (`src/state/cards.ts`). This is the tier that
 * makes `EXPERIENCE.md`'s *"name and cost are known at hover time and render immediately, the rest
 * fills in place — no spinner"* mechanically true: the summaries arrive already embedded in the
 * deck payload, so a consumer can draw a tile before any per-card request exists.
 */
export type CardSummary = Schemas['CardSummary']

/**
 * One entry of `DeckDetail.cards`: the quantity, the board, the commander flag — and an embedded
 * {@link CardSummary}.
 *
 * **Consumer: `seedCardSummaries` in `src/state/cards.ts`**, the AC 5 entry point **c4-2** calls
 * with the deck payload it fetches. c4-1 takes these as an ARGUMENT and never goes and gets them:
 * `GET /api/deck/{deck_id}` is c4-2's route, not this story's.
 */
export type DeckCardSummary = Schemas['DeckCardSummary']

/**
 * The body of `GET /api/deck/{deck_id}`: a saved deck's metadata, its three counts and its
 * whole card list.
 *
 * **Consumer: `readDeck` in `src/api/client.ts`, and the `deck` arm of the deck slice**
 * (`src/state/deck.ts`, story c4-2). This is the payload the app's whole deck view is derived
 * from — the type grouping, the header's name and badges, and (via {@link DeckCardSummary})
 * the card cache's summary tier, all out of ONE request. Measured on the largest real deck on
 * this machine (99 distinct cards, 100 total): **47,458 bytes, one request**.
 *
 * Ledgered since c3-2 and declined twice on the same reason — an export with no consumer is
 * dead code (c3-2 declined it; c4-1 declined it again, having no fetch for it). This commit is
 * the one that gives it one. (`CardFace` was declined here too, and assigned to **c4-6**;
 * **c4-5** turned out to be its first consumer — see {@link CardFace} for the measurement that
 * moved it, stated as a ledger correction rather than a silent edit.)
 *
 * The wire's own docstring records the fact the derivation rests on: *"The order of `cards` is
 * not meaningful… A consumer that wants a stable presentation order (by type, by mana value, by
 * name) must sort them itself."* `src/state/deckGroups.ts` is that consumer.
 */
export type DeckDetail = Schemas['DeckDetail']

/**
 * The body of `GET /api/active-deck`: which deck the companion is displaying, or `null`.
 *
 * **Consumer: `readActiveDeck` in `src/api/client.ts`**, the first of the two requests story
 * c4-2's boot makes. `deck_id: null` is **the answer, not the absence of one** — the slot lives
 * in the backend's memory and dies with the process (FR-07), so a cold open after any restart
 * reports `null` and that is the ordinary case rather than an error path.
 *
 * Two things the model's own docstring instructs a reader of it to do, both honoured in
 * `client.ts`: interpolate the id into `GET /api/deck/{deck_id}` **URL-encoded, like any path
 * segment**, and treat `deck_not_found` from that second request as *"the ordinary case, not a
 * broken invariant"* — nothing validates the id on the way in.
 */
export type ActiveDeck = Schemas['ActiveDeck']

/**
 * One face of a multi-faced printing: its own name, mana cost, type line, oracle text and — when
 * the card's artwork is per-face — its own images.
 *
 * **Consumer: the card detail panel** (`src/containers/CardDetail/CardDetail.tsx`, story c4-5).
 *
 * ==== A LEDGER CORRECTION, STATED RATHER THAN MADE SILENTLY ============================
 * This alias was declined at c3-2 and again above, with `c4-6` (*"renders the flip control"*)
 * named as its inheritor. **c4-5 turned out to be the first consumer**, on a measurement the
 * received two-tier story had never been checked against: `CardSummary` already carries
 * `oracle_text`, so for a single-faced card hydration adds nothing this panel can DRAW — while
 * **all 3,225 cards in the shipped corpus that carry `card_faces` have a BLANK top-level
 * `oracle_text`, 100% of them**, and 2,274 carry the degenerate type line `Card // Card`. For
 * that population the real name, type line and rules text exist ONLY here. Six of the 99 cards
 * in the largest real deck are in it. So *"the rest fills in place"* is true — it just fills in
 * place for 6% of a deck rather than all of it, and this is the field it fills from.
 *
 * ==== EVERY FIELD IS OPTIONAL **AND** NULLABLE, AND THAT IS THE WIRE, NOT CAUTION =====
 * The backend models a face as all-optional with an open index signature, so a consumer must
 * narrow every field it reads — which is why `CardDetail` runs each one through the same
 * `given()` string narrowing the tile and the placeholder use, rather than through truthiness.
 * `image_uris` is here for completeness and **c4-6's** flip control; nothing in c4-5 reads it,
 * because art goes through `cardImageUrl` and never through a URL taken off a record (AD-11,
 * `tests/no-scryfall-hosts.test.ts`).
 */
export type CardFace = Schemas['CardFace']

/**
 * One row of `GET /api/deck/{deck_id}/format-check`: which check, how it came out, and why.
 *
 * **Consumer: the format check panel** (`src/containers/FormatCheck/FormatCheck.tsx`, story
 * c4-10), through `readFormatCheck` in `src/api/client.ts` and the slice in
 * `src/state/formatCheck.ts`.
 *
 * Declined at c3-3 with `c4-1 owns the aliases` as the reason, and declined again at c4-1 for the
 * standing rule this file's header states: **an alias is added in the commit that gives it a
 * consumer**, never before. This is that commit.
 *
 * Three facts a reader of this alias needs, all of them the backend's and none of them re-derived
 * here:
 *
 *   - **`check` is a machine token and there is no label field anywhere on the wire.** The six
 *     human labels are authored copy and live in `FormatCheck/copy.ts`.
 *   - **Both enums generate as plain string-literal unions**, so a `switch` over `status` is
 *     exhaustible by `tsc` and a seventh `check` name is a compile failure at the label map.
 *   - **`detail` is DATA, not copy.** It is authored by `src/logic/deck_validator.py` and arrives
 *     on the wire exactly as a card name does, which is why it is not in a copy module (c4-10
 *     Q15, the argument `DeckList/copy.ts:25-31` makes verbatim).
 */
export type FormatCheckRow = Schemas['FormatCheckRow']

/**
 * The body of `GET /api/deck/{deck_id}/format-check`: a deck's construction legality as one row
 * per check rather than a list of faults.
 *
 * **Consumer: the format check panel** (story c4-10). See {@link FormatCheckRow}.
 *
 * ==== `is_legal` IS A TRAP, AND THIS ALIAS IS WHERE A READER MEETS IT ==================
 * The Pydantic model's own `Warning:` block (`deck_validator.py:557-565`) says it: `is_legal` is
 * **not** a summary of the rows. It answers `false` both for a deck that breaks a rule and for a
 * deck that could not be checked, so binding it to a headline renders a red verdict over six rows
 * none of which is a violation. Read it as *"certified legal"*. **c4-10 binds it to nothing at
 * all**, and `ui/tests/format-check-source.test.ts` asserts the identifier appears nowhere in
 * `src/` outside the generated types and the declared fixture module — which is what turns that
 * prose warning into a machine-checkable fact (`deferred-work.md:2430-2437` recorded that no
 * such guard existed).
 *
 * To show a fault, look for `rows.some((r) => r.status === 'violation')`. To show "cannot be
 * checked", branch on `format_recognized` — **not** on `format === null`, which would not even
 * compile: the generated type is `string`, and an absent format is the empty string.
 *
 * `format` here is the **normalised** value (`format.strip().lower()`), while `DeckDetail.format`
 * — which `DeckBadges` already renders 24px away in the header — is the **stored** one. This story
 * is the first thing in the app to hold both at once; measured, **0 of 40** real decks differ, and
 * nothing in the UI compares them (c4-10 Q14).
 */
export type FormatCheckReport = Schemas['FormatCheckReport']

/**
 * The closed set of reason tokens (AD-16), as a TypeScript string union.
 *
 * Derived from `ErrorResponse` rather than re-listed, so a token added or removed on the Python
 * side arrives here through the generator instead of through someone remembering. This union is
 * what **c2-9**'s state panels switch on — a token silently dropped from it would compile fine and
 * lose a panel, which is why `schema.test.ts` pins every member by name. **Ten** as of c3-5
 * (`no_image_data`, `image_fetch_failed`); this sentence and that file are where the count is
 * written, so they are where an eleventh has to be added.
 *
 * Not every member reaches the glass, and that is by design rather than by omission: `forbidden`
 * and `payload_too_large` are answered to the **agent**, and `components/StatePanel/states.ts` is
 * where each token's destination — panel, placeholder, or deliberately nothing — is recorded in a
 * form the compiler checks.
 *
 * c3-5's pair are the first two tokens that share ONE destination while staying distinct on the
 * wire: both draw the named Card placeholder, and they are separate tokens because only one of
 * them may ever be retried. Distinguishable-on-the-wire and identical-on-the-glass is a
 * combination this union had not carried before; `states.ts` records it.
 */
export type ErrorReason = ErrorResponse['reason']
