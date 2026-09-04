/**
 * Every word the deck list panel authors.
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — importing one with extensionless
 * relative imports produces `TS2835` errors that `npm test` does not see. This module stays
 * import-free exactly as every other copy module does.
 *
 * ================= WHAT THAT COSTS, AND WHERE THE COST IS PAID =========================
 *
 * {@link GROUP_LABELS} is coupled to `deckGroups.ts`'s `TypeGroup` **in both directions**, so
 * that a tenth group and a widening to `string` are both `tsc` failures. The obvious spelling —
 * `satisfies Record<TypeGroup, string>` — needs an `import type` of that union, and `import type`
 * does not help: `TS2835` is a RESOLUTION error, raised against the module specifier, and it
 * fires whether or not the import is erased at emit.
 *
 * So the map is declared here, plainly, and the coupling is asserted in `DeckList.tsx`, which
 * imports both. That is `CardPlaceholder`'s shape exactly — an import-free `copy.ts` beside a
 * component file carrying `type Assert<T extends true> = T` — and it is why that component can be
 * held to `PlaceholderKey` while its words stay importable by `ui/tests/`. The coupling is not
 * weaker for living one file away; it is the same `tsc` failure, raised from the file that has
 * both halves in scope.
 *
 * ================= WHAT IS COPY HERE, AND WHAT IS EMPHATICALLY NOT =====================
 *
 * Card names, type lines, mana costs and quantities are **data** — they arrive from the wire and
 * no author wrote them. Moving them here to make the module look complete would be the opposite
 * of what the copy guard is for: `COPY_MODULES` is a claim about where AUTHORED WORDS live, and a
 * module that also held card names would make that claim meaningless: card data is not copy.
 *
 * The GROUP labels below sit on the copy side of that line even though they are named after data,
 * and the distinction is worth stating because it is the one a later reader will question:
 * `TYPE_GROUPS`'s members are the STORE's internal vocabulary, not the wire's. `type_line` says
 * `'Legendary Creature — Human Soldier'`; nothing on the wire ever says `'Creature'` alone, and
 * nothing at all says `'Creatures'`. The plural forms below were chosen by an author, from
 * DESIGN.md's one worked example, and that makes them copy.
 */

/**
 * The panel's title, and therefore its `<section>`'s accessible name.
 *
 * Sourced, not invented: `EXPERIENCE.md:36` names this surface *"Deck list panel"* in the P0
 * component table and `:87` calls its unit a *"Deck row"*. The word "panel" is dropped because
 * the element already IS one — a `<section>` named "Deck list panel" announces its own kind twice
 * to a screen-reader user, once from the name and once from the region role.
 *
 * Sentence case with no period, in the voice `FLIP_LABEL` and `UNPIN_LABEL` established: the
 * string stays in its readable case and any uppercase is CSS, so the accessible name and the
 * clipboard both keep the word a person would say.
 */
export const DECK_LIST_TITLE = 'Deck list'

/**
 * The commander section's label.
 *
 * Specified in NO artefact. `deckGroups.ts` partitions the board and `CardGrid` draws it
 * unlabelled, so this is the only place the word appears — and neither DESIGN.md nor
 * EXPERIENCE.md gives it. Singular because a deck
 * has one commander in 15 of the 16 real decks that have any; the partner/background case renders
 * two rows under the same heading, which reads correctly either way, where "Commanders" would
 * read wrongly for the common case.
 */
export const COMMANDER_LABEL = 'Commander'

/**
 * The sideboard section's label.
 *
 * Also specified in no artefact. `CardGrid` deliberately does not draw the sideboard, so this
 * panel is where its 41 rows across 5 real decks appear at all.
 */
export const SIDEBOARD_LABEL = 'Sideboard'

/**
 * The type-group headings, keyed by `deckGroups.ts`'s `TypeGroup`.
 *
 * ================= PLURAL, BECAUSE THE ARTEFACT'S ONE EXAMPLE IS ======================
 *
 * DESIGN.md's group-header line gives exactly one worked example and it is `"CREATURES"`
 * (`DESIGN.md:392`, *"type-group dividers ("CREATURES")"*). `TYPE_GROUPS` is singular because it
 * is a classification — a card IS a Creature — while a header names a COLLECTION of them. Both
 * are right in their own place, which is why this map exists rather than the store's strings
 * being rendered raw: rendering `TYPE_GROUPS` directly would put the store's internal vocabulary
 * on the glass AND make DESIGN.md's single worked example wrong.
 *
 * Uppercasing is NOT done here. `GroupHeader.css` applies `text-transform: uppercase` to the
 * label, and `GroupHeader.tsx` says so in its prop docstring — *"uppercased by CSS, not by the
 * caller"*. A pre-uppercased string here would be uppercased twice (harmless) while destroying
 * the readable form for anyone reading the accessible name or copying the text (not harmless).
 *
 * ================= `Sorceries`, AND `Other` STAYING SINGULAR ==========================
 *
 * `Sorcery` pluralises irregularly and is the one entry a mechanical `+ 's'` would get wrong —
 * which is the second reason this is a map rather than a derivation.
 *
 * **`Other` is deliberately not pluralised.** It is the residual bucket, not a card type: no card
 * is "an Other", so "Others" names nothing. It reads as "everything else", which is what it is.
 * One live row needs it today (see `deckGroups.ts`) and that row's type line is literally
 * `'Card'`, so this heading is the only thing on screen telling a reader why it is filed apart.
 *
 * `Battle` is present and correct with **zero rows in every real deck** — 39 cards in the corpus,
 * 0 in any deck. It is here because `TYPE_GROUPS` carries it, the coupling below is exhaustive,
 * and a group that appears the day someone adds a Siege must not fall back to a missing label.
 */
export const GROUP_LABELS = {
  Creature: 'Creatures',
  Planeswalker: 'Planeswalkers',
  Battle: 'Battles',
  Instant: 'Instants',
  Sorcery: 'Sorceries',
  Artifact: 'Artifacts',
  Enchantment: 'Enchantments',
  Land: 'Lands',
  Other: 'Other',
}
