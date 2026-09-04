/**
 * The one module that reads the generated wire types (AD-12).
 *
 * `types.d.ts` is generated verbatim from the backend's own `app.openapi()` and is shaped for a
 * generator, not for a reader: reaching a response body means indexing
 * `components['schemas'][…]` or `paths['/x']['get']['responses'][200]['content']['application/json']`.
 * Every module that does that for itself invents its own spelling of one shape, and before long
 * the same type has five names. So the indexing happens **here, once**, and the rest of `ui/src`
 * imports a narrow alias.
 *
 * Two rules, both enforced rather than documented:
 *
 * 1. **Nothing outside `src/api/` imports `./types` directly.** Add an alias below, then use the
 *    alias. An alias is added in the commit that gives it a consumer, never before: an export with
 *    no consumer is dead code.
 * 2. **Nothing outside `src/api/` re-declares a shape the backend already describes** — no
 *    hand-written `interface HealthResponse`. `ui/tests/wire-contract.test.ts` reads the
 *    `components.schemas` keys out of the committed `openapi.json` and fails on any such
 *    declaration, so the rule grows on its own as models are added, with no edit to the test.
 *
 *    A Pydantic model that no route references never reaches `components.schemas` at all, so
 *    declaring a union buys no TypeScript until something puts it on a route: *the code that
 *    defines a wire type and the code that publishes it are not always the same.*
 *
 * `import type` / `export type` only: `verbatimModuleSyntax` is on, and nothing about a `.d.ts`
 * may reach the runtime bundle.
 */

import type { components, paths } from './types'

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
 * The deck poll reads `name` and nothing else, because the only thing it renders is the
 * `no-active-deck` panel's deck list (`EXPERIENCE.md`: *"names only, non-clickable — the agent
 * drives"*). The deck bootstrap is the consumer that reads the counts.
 */
export type DeckSummary = Schemas['DeckSummary']

/**
 * The body of `GET /api/cards/{card_id}`: everything known about one printing.
 *
 * **Consumer: `readCard` in `src/api/client.ts`, and the `hydrated` tier of the card cache**
 * (`src/state/cards.ts`). This is the *expensive* half of the two-tier hydration contract —
 * measured on the largest real deck (99 tiles), the full rows are **212,436 bytes over 99
 * requests** against **38,182 bytes in one** for the summaries below, a 5.6× ratio. So it is
 * fetched per id, on demand, and never for a whole deck.
 */
export type Card = Schemas['Card']

/**
 * The card fields a deck row carries.
 *
 * **An alias of {@link Card}**, and it used to be a genuinely narrower shape: the deck detail once
 * embedded a bounded `CardSummary` (name, mana cost, cmc, type line, oracle text, colours, rarity,
 * set code and nothing more) and every tile that needed legalities, images or faces paid one
 * `GET /api/cards/{card_id}` for them — 99 requests on the largest real deck. The deck detail now
 * embeds the whole record, so the two are the same type and the name is kept only because it reads
 * correctly at the call sites that want *"whatever the deck row carried"*.
 *
 * The bounded `CardSummary` still exists in `src/data/schemas` and still rides on the MCP
 * `load_deck` payload, where every field is an LLM token. It simply no longer reaches this wire.
 */
export type CardSummary = Card

/**
 * One entry of `DeckDetail.cards`: the quantity, the board, the commander flag — and an embedded
 * whole {@link Card}.
 *
 * **Consumer: `seedDeckCards` in `src/state/cards.ts`**, which writes every row into the card
 * cache as a HYDRATED entry. That is what makes the per-card sweep unnecessary: the deck detail is
 * the only card request a deck view makes.
 */
export type DeckCardSummary = Schemas['DeckCardFull']

/**
 * The body of `GET /api/deck/{deck_id}`: a saved deck's metadata, its three counts and its
 * whole card list.
 *
 * **Consumer: `readDeck` in `src/api/client.ts`, and the `deck` arm of the deck slice**
 * (`src/state/deck.ts`). This is the payload the app's whole deck view is derived from — the
 * type grouping, the header's name and badges, and (via {@link DeckCardSummary}) the card cache
 * itself, every entry hydrated, all out of ONE request.
 *
 * The wire's own docstring records the fact the derivation rests on: *"The order of `cards` is
 * not meaningful… A consumer that wants a stable presentation order (by type, by mana value, by
 * name) must sort them itself."* `src/state/deckGroups.ts` is that consumer.
 */
export type DeckDetail = Schemas['DeckDetailFull']

/**
 * The body of `GET /api/active-deck`: which deck the companion is displaying, or `null`.
 *
 * **Consumer: `readActiveDeck` in `src/api/client.ts`**, the first of the two requests the boot
 * makes. `deck_id: null` is **the answer, not the absence of one** — the slot lives
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
 * **Consumer: the card detail panel** (`src/containers/CardDetail/CardDetail.tsx`).
 *
 * ==== WHY THE DETAIL PANEL READS FACES AT ALL ==========================================
 * `CardSummary` already carries `oracle_text`, so for a single-faced card hydration adds nothing
 * this panel can DRAW — while **all 3,225 cards in the shipped corpus that carry `card_faces`
 * have a BLANK top-level `oracle_text`, 100% of them**, and 2,274 carry the degenerate type line
 * `Card // Card`. For that population the real name, type line and rules text exist ONLY here.
 * Six of the 99 cards in the largest real deck are in it, so hydration fills in place for 6% of a
 * deck rather than all of it, and this is the field it fills from.
 *
 * ==== EVERY FIELD IS OPTIONAL **AND** NULLABLE, AND THAT IS THE WIRE, NOT CAUTION =====
 * The backend models a face as all-optional with an open index signature, so a consumer must
 * narrow every field it reads — which is why `CardDetail` runs each one through the same
 * `given()` string narrowing the tile and the placeholder use, rather than through truthiness.
 * `image_uris` is here for completeness and the flip control; the detail panel does not read it,
 * because art goes through `cardImageUrl` and never through a URL taken off a record (AD-11,
 * `tests/no-scryfall-hosts.test.ts`).
 */
export type CardFace = Schemas['CardFace']

/**
 * One row of `GET /api/deck/{deck_id}/format-check`: which check, how it came out, and why.
 *
 * **Consumer: the format check panel** (`src/containers/FormatCheck/FormatCheck.tsx`), through
 * `readFormatCheck` in `src/api/client.ts` and the slice in `src/state/formatCheck.ts`.
 *
 * Three facts a reader of this alias needs, all of them the backend's and none of them re-derived
 * here:
 *
 *   - **`check` is a machine token and there is no label field anywhere on the wire.** The six
 *     human labels are authored copy and live in `FormatCheck/copy.ts`.
 *   - **Both enums generate as plain string-literal unions**, so a `switch` over `status` is
 *     exhaustible by `tsc` and a seventh `check` name is a compile failure at the label map.
 *   - **`detail` is DATA, not copy.** It is authored by `src/logic/deck_validator.py` and arrives
 *     on the wire exactly as a card name does, which is why it is not in a copy module (the
 *     argument `DeckList/copy.ts` makes for card names).
 */
export type FormatCheckRow = Schemas['FormatCheckRow']

/**
 * The body of `GET /api/deck/{deck_id}/format-check`: a deck's construction legality as one row
 * per check rather than a list of faults.
 *
 * **Consumer: the format check panel.** See {@link FormatCheckRow}.
 *
 * ==== `is_legal` IS A TRAP, AND THIS ALIAS IS WHERE A READER MEETS IT ==================
 * The Pydantic model's own `Warning:` block (`deck_validator.py:557-565`) says it: `is_legal` is
 * **not** a summary of the rows. It answers `false` both for a deck that breaks a rule and for a
 * deck that could not be checked, so binding it to a headline renders a red verdict over six rows
 * none of which is a violation. Read it as *"certified legal"*. **The UI binds it to nothing at
 * all**, and `ui/tests/format-check-source.test.ts` asserts the identifier appears nowhere in
 * `src/` outside the generated types and the declared fixture module — which is what turns that
 * prose warning into a machine-checkable fact.
 *
 * To show a fault, look for `rows.some((r) => r.status === 'violation')`. To show "cannot be
 * checked", branch on `format_recognized` — **not** on `format === null`, which would not even
 * compile: the generated type is `string`, and an absent format is the empty string.
 *
 * `format` here is the **normalised** value (`format.strip().lower()`), while `DeckDetail.format`
 * — which `DeckBadges` already renders 24px away in the header — is the **stored** one. Measured,
 * **0 of 40** real decks differ, and nothing in the UI compares them.
 */
export type FormatCheckReport = Schemas['FormatCheckReport']

/**
 * The body of `GET /api/session`: one short-lived, single-use credential for one socket upgrade.
 *
 * **Consumer: `readSessionTicket` in `src/api/client.ts`**, called once per connect
 * ATTEMPT — not once per session, not once per tab. The wire's own docstring is unusually
 * prescriptive about that and every clause of it is a constraint on the loop rather than advice:
 * *"single-use"*, *"it cannot be stored, shared between tabs, or reused across reconnects"*, and
 * — the clause that decides the ordering inside the backoff — *"consuming it destroys it whether
 * or not the handshake then succeeds, so a retry needs a fresh ticket, including after an upgrade
 * that failed for an unrelated reason"*.
 */
export type SessionTicket = Schemas['SessionTicket']

/**
 * One frame off the WebSocket: the `{kind, id, ts, payload}` envelope, as a closed six-member
 * discriminated union (AD-6).
 *
 * **Consumer: `agentEventOf` in `src/api/client.ts` and the one dispatch switch in
 * `src/state/socket.ts`**.
 *
 * ==== IT IS REACHED THROUGH A ROUTE, NOT THROUGH `components.schemas` ==================
 * There is no `AgentEvent` in `components.schemas` — the union is a Python
 * `Annotated[… , Field(discriminator="kind")]`, and a discriminated union is not itself a named
 * model. What the generator emits is the six MEMBERS as schemas plus the union spelled inline at
 * the one place a route references it, which is `POST /agent/events`'s request body. So this
 * alias indexes `paths` rather than `Schemas`: *the code that defines a wire type and the code
 * that publishes it are not always the same.*
 *
 * **The direction is inverted and that is not a bug.** `/agent/events` is what the AGENT posts;
 * this alias is what the BROWSER receives. They are the same envelope — `ws.py` broadcasts the
 * ingested event verbatim — so reading the client's frame type off the server's request body is
 * reading the one declaration both halves share, rather than writing a second one that could
 * drift from it. If a later story gives the socket its own published schema, this alias moves and
 * nothing that consumes it changes.
 */
export type AgentEvent =
  paths['/agent/events']['post']['requestBody']['content']['application/json']

/**
 * The six `kind` discriminants, as a union — `'suggestions' | 'swaps' | … | 'active_deck_changed'`.
 *
 * Derived from {@link AgentEvent} rather than re-listed, for `ErrorReason`'s reason: a seventh
 * kind added on the Python side arrives here through the generator instead of through someone
 * remembering, and the total `switch` in `src/state/socket.ts` fails `npm run typecheck` naming
 * the kind it does not handle. A hand-written copy of the six strings would compile forever.
 */
export type AgentEventKind = AgentEvent['kind']

/**
 * The four kinds that are a VIEW — `'suggestions' | 'swaps' | 'tier_list' | 'groups'`.
 *
 * **Consumer: `src/state/agentView.ts` and `containers/AgentViewsNav`**, whose whole design is
 * generic over the closed `kind` enum: a new view kind's pill becomes active with no nav work,
 * which is only true if the nav is written against this union rather than against the kinds that
 * happen to have a view today.
 *
 * `Exclude` over the SYSTEM kinds rather than a fresh list of the four, and the direction
 * matters: a fifth agent-view kind added on the Python side arrives here through the generator
 * and the nav grows a pill without an edit, which is the property the nav relies on. A
 * hand-written `'suggestions' | 'swaps' | 'tier_list' | 'groups'` would compile forever and grow
 * never — {@link AgentEventKind}'s own docstring one line up makes the same argument.
 *
 * The two excluded literals are spelled here rather than imported from `src/state/`: `src/api/`
 * is below it and may not import upward. This file also owns the OTHER side of the
 * partition — {@link SystemEvent}, whose `Extract` pair names the same two literals — so both
 * spellings of the pair now live in THIS file, one per direction of the split, and `socket.ts`
 * derives from `SystemEvent` rather than re-spelling anything. Both spellings are DERIVED, so a
 * kind renamed on the Python side breaks the `Extract`/`Exclude` loudly instead of silently
 * dropping a member. The wire-name ban is about re-declaring backend *shapes* (`SwapsPayload`,
 * `TierListEvent`); a discriminant literal in a derivation is what both spellings are.
 */
export type AgentViewKind = Exclude<AgentEventKind, 'deck_changed' | 'active_deck_changed'>

/**
 * One `suggestions` frame — the envelope, narrowed to the member `kind: 'suggestions'` selects.
 *
 * **Consumer: `suggestionsViewOf` in `src/state/agentView.ts`.**
 *
 * `Extract` over {@link AgentEvent} rather than `Schemas['SuggestionsEvent']`, and the difference
 * is not cosmetic: the union is what the dispatch switch narrows, so extracting from it is the
 * one spelling that cannot disagree with the thing being narrowed. Indexing `components.schemas`
 * would name a second declaration of the same shape and let the two drift the day the route's
 * union stops including it.
 *
 * ⚠️ `payload` is REQUIRED in this type and OPTIONAL on the wire in practice: `agentEventOf`
 * (`client.ts`) validates the `kind` discriminant and nothing else, so a frame of
 * `{"kind":"suggestions"}` reaches a consumer typed as a full event. The builder that reads this
 * shape is total for exactly that reason — see its docstring.
 */
export type SuggestionsEvent = Extract<AgentEvent, { kind: 'suggestions' }>

/**
 * One `swaps` frame — the envelope, narrowed to the member `kind: 'swaps'` selects.
 *
 * **Consumer: `swapsViewOf` in `src/state/agentView.ts`.**
 *
 * `Extract` over {@link AgentEvent} rather than `Schemas['SwapsEvent']`, for
 * {@link SuggestionsEvent}'s reason verbatim: the union is what the dispatch switch narrows, so
 * extracting from it is the one spelling that cannot disagree with the thing being narrowed.
 *
 * ⚠️ `payload` is REQUIRED in this type and OPTIONAL on the wire in practice — the exact caveat
 * {@link SuggestionsEvent} carries: `agentEventOf` (`client.ts`) validates the `kind`
 * discriminant and nothing else, so a frame of `{"kind":"swaps"}` reaches a consumer typed as a
 * full event. The builder that reads this shape is total for exactly that reason.
 */
export type SwapsEvent = Extract<AgentEvent, { kind: 'swaps' }>

/**
 * One `tier_list` frame — the envelope, narrowed to the member `kind: 'tier_list'` selects.
 *
 * **Consumer: `tierListViewOf` in `src/state/agentView.ts`.**
 *
 * `Extract` over {@link AgentEvent} rather than `Schemas['TierListEvent']`, for
 * {@link SuggestionsEvent}'s reason verbatim: the union is what the dispatch switch narrows, so
 * extracting from it is the one spelling that cannot disagree with the thing being narrowed.
 *
 * ⚠️ `payload` is REQUIRED in this type and OPTIONAL on the wire in practice — the exact caveat
 * {@link SuggestionsEvent} carries: `agentEventOf` (`client.ts`) validates the `kind`
 * discriminant and nothing else, so a frame of `{"kind":"tier_list"}` reaches a consumer typed
 * as a full event. The builder that reads this shape is total for exactly that reason.
 */
export type TierListEvent = Extract<AgentEvent, { kind: 'tier_list' }>

/**
 * One `groups` frame — the envelope, narrowed to the member `kind: 'groups'` selects.
 *
 * **Consumer: `groupsViewOf` in `src/state/agentView.ts`.**
 *
 * `Extract` over {@link AgentEvent} rather than `Schemas['GroupsEvent']`, for
 * {@link SuggestionsEvent}'s reason verbatim: the union is what the dispatch switch narrows, so
 * extracting from it is the one spelling that cannot disagree with the thing being narrowed.
 *
 * ⚠️ `payload` is REQUIRED in this type and OPTIONAL on the wire in practice — the exact caveat
 * {@link SuggestionsEvent} carries: `agentEventOf` (`client.ts`) validates the `kind`
 * discriminant and nothing else, so a frame of `{"kind":"groups"}` reaches a consumer typed
 * as a full event. The builder that reads this shape is total for exactly that reason.
 */
export type GroupsEvent = Extract<AgentEvent, { kind: 'groups' }>

/**
 * One `deck_changed` frame — the envelope, narrowed to the member `kind: 'deck_changed'` selects.
 *
 * **Consumers: the dispatch seam (`src/state/socket.ts` → `connection.ts`)**, which reads
 * `payload.deck_id` to decide between a single-deck refetch and a full boot re-drive.
 *
 * `Extract` over {@link AgentEvent} rather than `Schemas['DeckChangedEvent']`, for
 * {@link SuggestionsEvent}'s reason verbatim: the union is what the dispatch switch narrows, so
 * extracting from it is the one spelling that cannot disagree with the thing being narrowed.
 *
 * ⚠️ `payload` is REQUIRED in this type and OPTIONAL on the wire in practice — the exact caveat
 * {@link SuggestionsEvent} carries: `agentEventOf` (`client.ts`) validates the `kind`
 * discriminant and nothing else, so a frame of `{"kind":"deck_changed"}` reaches a consumer typed
 * as a full event. And `deck_id` is nullable BY DESIGN even on a well-formed wire
 * (`types.d.ts`: a deck-agnostic emission is a committed later phase). So the one read of
 * `payload.deck_id` must be total twice over — absent payload, and absent/null/blank id — and
 * `connection.ts` folds all of those to `null`, "refetch whatever is active".
 */
export type DeckChangedEvent = Extract<AgentEvent, { kind: 'deck_changed' }>

/**
 * One `active_deck_changed` frame — the other system kind, aliased beside its sibling so the
 * dispatch seam can carry BOTH as one typed union.
 *
 * Its payload's `deck_id` is deliberately never read — `connection.ts` re-drives the full boot,
 * which asks `GET /api/active-deck` first, so the client can never refetch the deck it is leaving
 * (`contracts.py:902-905`). The alias exists so that {@link SystemEvent} is a derivation rather
 * than a hand-written pair.
 */
export type ActiveDeckChangedEvent = Extract<AgentEvent, { kind: 'active_deck_changed' }>

/**
 * The two system frames as one union — what `socket.ts`'s `onSystemEvent` carries.
 *
 * The two members stay distinct types with distinct discriminants, so the consumer that branches
 * on `kind` narrows to the right payload in one step — conflating them is the bug
 * `contracts.py:902-905` warns about, and the union keeps it unrepresentable: there is no way to
 * read a `deck_id` here without first saying which kind's `deck_id` is meant.
 */
export type SystemEvent = DeckChangedEvent | ActiveDeckChangedEvent

/**
 * One suggested card: `{card_id, reason, category?, confidence?}` (AD-7).
 *
 * **Consumers: `AgentViewContent` in `src/state/agentView.ts`**, which retains the items so that
 * `SuggestionsView.tsx` can render rows and the nav pills can re-open a view against current card
 * data.
 *
 * Reached through `Schemas` rather than through {@link SuggestionsEvent}'s payload, because it is
 * a named model on the Python side and the generator emits it as one. `SuggestionsPayload` is
 * deliberately NOT aliased: nothing outside the builder ever holds a payload — the builder takes
 * an envelope and returns store content — so an alias for it would have no consumer.
 */
export type SuggestionItem = Schemas['SuggestionItem']

/**
 * One proposed trade: `{out_card_id, in_card_id, rationale, out_qty, in_qty, confidence?}` (AD-7).
 *
 * **Consumer: the `swaps` arm of `AgentViewContent` in `src/state/agentView.ts`**, which retains the items so `SwapsView` can render and re-hydrate them — the exact shape of
 * {@link SuggestionItem}'s consumer one entry up, for the second view kind.
 *
 * Reached through `Schemas` rather than through {@link SwapsEvent}'s payload, because it is a
 * named model on the Python side and the generator emits it as one. `SwapsPayload` is
 * deliberately NOT aliased: nothing outside the builder ever holds a payload, so an alias for it
 * would have no consumer.
 *
 * There is deliberately **no price field** — the wire itself carries none
 * (`types.d.ts`, the `SwapItem` docstring): no price data exists anywhere in this system, so a
 * price chip could never be populated. Render confidence, never price.
 */
export type SwapItem = Schemas['SwapItem']

/**
 * One tier: `{letter, name, note?, card_ids}` (AD-7).
 *
 * **Consumer: the `tier_list` arm of `AgentViewContent` in `src/state/agentView.ts`**, which
 * retains the items so `TierListView` can render and re-hydrate them — the exact shape of
 * {@link SwapItem}'s consumer one entry up, for the third view kind.
 *
 * Reached through `Schemas` rather than through {@link TierListEvent}'s payload, because it is a
 * named model on the Python side and the generator emits it as one. `TierListPayload` is
 * deliberately NOT aliased: nothing outside the builder ever holds a payload, so an alias for it
 * would have no consumer.
 *
 * The `letter` is the closed five-value `S|A|B|C|D` vocabulary and `name` is its accessible
 * carrier of rank (`types.d.ts`: colour alone must never be what tells a reader that S beats D)
 * — which is why the view renders the name beside the letter, always.
 */
export type TierItem = Schemas['TierItem']

/**
 * One named group of cards: `{title, rationale, card_ids}` (AD-7).
 *
 * **Consumer: the `groups` arm of `AgentViewContent` in `src/state/agentView.ts`**, which
 * retains the items so `GroupsView` can render and re-hydrate them — the exact shape of
 * {@link TierItem}'s consumer one entry up, for the fourth and last view kind.
 *
 * Reached through `Schemas` rather than through {@link GroupsEvent}'s payload, because it is a
 * named model on the Python side and the generator emits it as one. `GroupsPayload` is
 * deliberately NOT aliased: nothing outside the builder ever holds a payload, so an alias for
 * it would have no consumer.
 *
 * The optionality is the INVERSE of {@link TierItem}'s: `title` and `rationale` are both
 * REQUIRED non-blank on the wire (the title is the only thing distinguishing one group from
 * the next, and the rationale is the paragraph the group exists to carry), while `card_ids` is
 * optional and may be empty — the view skips an empty group rather than rejecting it. The
 * group's own `title` is distinct from the payload-level view header of the same name.
 */
export type GroupItem = Schemas['GroupItem']

/**
 * The closed set of reason tokens (AD-16), as a TypeScript string union.
 *
 * Derived from `ErrorResponse` rather than re-listed, so a token added or removed on the Python
 * side arrives here through the generator instead of through someone remembering. This union is
 * what the state panels switch on — a token silently dropped from it would compile fine and lose
 * a panel, which is why `schema.test.ts` pins every member by name. **Ten** today; this sentence
 * and that file are where the count is written, so they are where an eleventh has to be added.
 *
 * Not every member reaches the glass, and that is by design rather than by omission: `forbidden`
 * and `payload_too_large` are answered to the **agent**, and `components/StatePanel/states.ts` is
 * where each token's destination — panel, placeholder, or deliberately nothing — is recorded in a
 * form the compiler checks.
 *
 * `no_image_data` and `image_fetch_failed` share ONE destination while staying distinct on the
 * wire: both draw the named Card placeholder, and they are separate tokens because only one of
 * them may ever be retried. `states.ts` records that pairing.
 */
export type ErrorReason = ErrorResponse['reason']
