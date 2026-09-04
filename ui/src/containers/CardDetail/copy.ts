/**
 * Every word the card detail panel authors (UX-DR33, UX-DR45).
 *
 * Three strings, and they are the whole of it. **The card's name, type line, oracle text and
 * mana cost are DATA** — they arrive from the wire and are deliberately NOT in this module, for
 * the reason `CardPlaceholder/copy.ts` states about its own: a copy owner that also held card
 * names would make the claim `COPY_MODULES` exists to state meaningless.
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — measured: importing one with
 * extensionless relative imports produces twelve `TS2835` errors with `npm test` green
 * throughout. `tests/pin-announcement-copy.test.ts` imports this file, so it stays import-free
 * exactly as `StatePanel/copy.ts` and `CardPlaceholder/copy.ts` do.
 */

/**
 * The panel's title — and therefore its accessible name, its `<h2>`, and the element **the skip
 * link moves focus to** (UX-DR44).
 *
 * `Panel` renders `<section aria-label={title}>` with the title as an `<h2 className=
 * "panel-title">`, so this one string satisfies *"`role="region"` labelled 'Card detail'"* with
 * no ARIA written by hand.
 *
 * **It is the panel's name, not the card's**, and that is a requirement rather than a
 * convenience: a heading that changed on every hover would rename a landmark forty times during
 * one sweep of the grid, and the skip link's target would be a name nobody could predict.
 */
export const PANEL_TITLE = 'Card detail'

/**
 * The control that releases a pin (UX-DR20, UX-DR47).
 *
 * ==== IT IS SPECIFIED NOWHERE, AND THIS IS THE DECISION ===============================
 * UX-DR20 *requires* it — *"click the panel's unpin control to release"* — and no artefact gives
 * it a size, a glyph, a position, a label or a token. So: a **word**, not a symbol. `DESIGN.md`'s
 * brand rules make a novel glyph a risk in their own right and UX-DR7 bans symbol-lookalikes
 * outright, and there is no icon set in this codebase to draw from — the one pictographic thing
 * the app ships is a mana pip, which means something else entirely.
 *
 * One word rather than a sentence, because it is a button label and `DESIGN.md` puts panel
 * chrome in `{typography.label}` — which the type gate then renders in CAPITALS, exactly as it
 * does the panel title beside it. The string stays lower-case here: the uppercase is CSS, so the
 * accessible name, the clipboard and this constant all keep the plain word (the same reasoning
 * as the tile caption's uppercase, applied to a control).
 */
export const UNPIN_LABEL = 'Unpin'

/**
 * What the polite live region says when a card is pinned (UX-DR45).
 *
 * ==== THE TRAILING PERIOD: NO. AND THE TWO ARTEFACTS DISAGREE ==========================
 * Decided rather than assumed, because the two sources are not identical:
 *
 *   `epics-companion-app.md:2029` and `:599` — **`"Pinned — {card name}"`**, twice, no period.
 *   `EXPERIENCE.md:154` — *"…via a separate polite region: "Pinned — Adeline, Resplendent
 *   Cathar.""*, inside a prose sentence that itself ends there.
 *
 * **No trailing period**, on three grounds. `epics-companion-app.md` states a TEMPLATE, twice, and a
 * template is the normative form of a string with a hole in it; EXPERIENCE.md's full stop is
 * indistinguishable from the terminator of the sentence carrying the example, which the template
 * has no such ambiguity about; and the announcement is a LABEL rather than a sentence — it names
 * what just happened, in the same voice as the panel title beside it.
 *
 * The em dash is U+2014, matching both artefacts. It is written as a literal rather than an
 * escape because — unlike the tile badge's multiplication sign, which a keyboard can substitute an ASCII
 * `x` for invisibly — an ASCII hyphen beside it reads and measures differently, and the
 * byte-for-byte gate in `tests/pin-announcement-copy.test.ts` compares this against the
 * artefact's own em dash.
 *
 * ==== IT IS A FUNCTION SO THAT THE HOLE IS FILLED IN ONE PLACE ========================
 * `aria-live` announces a CHANGE, so the component's job is to set this string once per pin and
 * never to recompute it as hydration lands — otherwise a card whose name resolves from
 * `card_faces` after the pin would announce a second time for the same pin, which *"exactly
 * once"* forbids.
 *
 * Args:
 *   name: The card's name, verbatim and unsplit, exactly as the deck payload carries it.
 *
 * Returns:
 *   The whole announcement.
 */
export const pinnedAnnouncement = (name: string): string => `Pinned — ${name}`

/**
 * The oracle scroller's accessible name.
 *
 * ==== WHY A CLAMPED PARAGRAPH NEEDS A NAME AT ALL =====================================
 * The rules text is clamped at `max-height: 21em` — 294px, 14 lines, measured live — with
 * `overflow-y: auto`. WCAG 2.1.1 requires that scrollable content be reachable from a keyboard
 * *whenever* it can overflow, so the element takes `tabindex="0"`. A Tab stop with no accessible
 * name announces as an unlabelled group, which is worse than the defect it repairs — so it takes
 * `role="group"` and this string together, or none of the three.
 *
 * `role="group"` rather than `role="region"`: a region is a LANDMARK, and a landmark per card
 * would put a nameless-until-hydrated entry in every screen reader's landmark list and move the
 * count `AppShell.test.tsx` pins. A group is a grouping, which is what this is.
 *
 * **The words name the box, not its contents.** "Rules text" is what the box holds; the card's
 * own oracle text is DATA and stays out of this module for the reason the header states. A label
 * naming the card would rename this element on every hover — the exact defect `PANEL_TITLE`'s
 * note above exists to prevent, one element further down the same panel.
 *
 * Sentence case, no trailing period: it is a label in the same voice as `UNPIN_LABEL`, and it is
 * spoken as a name rather than read as a sentence.
 */
export const ORACLE_SCROLLER_LABEL = 'Rules text'
