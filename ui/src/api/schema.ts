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
