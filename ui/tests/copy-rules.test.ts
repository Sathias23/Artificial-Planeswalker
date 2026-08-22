/**
 * UX-DR33's voice rules, as a gate (story c2-9, AC 6, AC 13).
 *
 * "No exclamation marks, no emoji, no mascot; never blame — 'something went wrong' is banned"
 * is a rule about USER-FACING COPY, and the measurement that shaped this file is that a naive
 * repo-wide ban on either string **fails on the day it is written, against the wrong files**:
 *
 *   `"something went wrong"` already appears TWICE inside `ui/src` — `api/openapi.json:90` and
 *   `api/types.d.ts:46` — in both cases QUOTING THE BAN ITSELF, inside generated files no
 *   author may hand-edit.
 *
 *   `!` is an OPERATOR in nine of the eleven modules under `src/components/`.
 *
 * ================= HOW BOTH ARE OUT OF SCOPE **BY CONSTRUCTION** =======================
 *
 * Not by a special case listing today's two files — that list would be wrong the moment a third
 * arrived. This guard reads the TypeScript **AST**, not the text:
 *
 *   A COMMENT IS NOT A STRING NODE. `types.d.ts:46` lives in a JSDoc block, and the parser
 *   simply never yields it. The same is true of every future doc comment that quotes the rule,
 *   including this file's own header, which contains the banned phrase four times.
 *
 *   `!` AS AN OPERATOR IS A `PrefixUnaryExpression`, not a `StringLiteral`. `!filled(x)` is
 *   invisible here for the same reason, permanently, in files nobody has written yet.
 *
 *   `openapi.json` IS NOT SCANNED AT ALL. It is generated from the backend's own
 *   `app.openapi()` (AD-12) and is not a source of rendered copy; `wire-contract.test.ts` owns
 *   it. Stated so that "the guard skips it" is a scope decision on the record and not a hole.
 *
 * `typescript` is already a direct devDependency (it IS `npm run typecheck`), so this adds no
 * dependency — AC 24 holds.
 *
 * ================= THE TWO HALVES, BECAUSE ONE IS WORTHLESS WITHOUT THE OTHER ===========
 *
 * c2-8's data-ink guard is the precedent, and its review round is the reason this is written as
 * a pair: a rule about what copy may CONTAIN is worthless if copy can live anywhere, and a rule
 * about where copy may LIVE is worthless if it is never read.
 *
 *   THE FILE HALF — user-facing prose may only live in an enumerated, git-checked set of copy
 *   modules. A sentence introduced anywhere else fails, naming the module it belongs in.
 *
 *   THE CONTENT HALF — EVERY string literal in EVERY module is checked, prose-shaped or not.
 *   Deliberately NOT gated behind the prose detector, and that was MEASURED rather than
 *   reasoned: a one-word-plus-pictograph string matches no prose pattern at all, and the first
 *   draft of this guard let exactly that through. The ban costs nothing to apply widely, and
 *   the residue it closes is real — a word table of single words is where a mascot would sit.
 *
 * ================= WHAT THIS GUARD DOES **NOT** DECIDE, DECLARED ========================
 *
 * The same division of labour `src/styles/surfaces.ts` and `findAccentDimOnOverlay` declare for
 * their own halves. Five residues, all REVIEW'S (4 and 5 were undeclared until the review of
 * 2026-07-29 — a guard limit that is not written down reads as coverage):
 *
 *   1. WHETHER A SENTENCE IS SECOND-PERSON AND BLAMELESS. Not statically decidable, and the
 *      most important half of UX-DR33. A reviewer of c2-10, c4-3, c4-12 and c6-6 must READ the
 *      copy; this file will not have read it.
 *   2. COPY ASSEMBLED FROM SINGLE WORDS AT RUNTIME. `describeManaCost` builds "2 generic, white
 *      or blue" out of a word table — no entry of which is prose-shaped. That module is in
 *      `COPY_MODULES` deliberately (so the content half covers its table), but a NEW module
 *      doing the same thing would not be detected by the file half. The realistic mitigation is
 *      that the accessible-name attribute it feeds IS detected wherever it is a literal.
 *   3. A STRING REACHING AN `aria-label` THROUGH AN EXPRESSION. `aria-label={describe(x)}` is a
 *      call, not a literal; the value is only knowable at runtime. Component tests assert the
 *      rendered result instead — `StatePanel.test.tsx` does exactly that over the real DOM.
 *   4. THE PROSE DETECTOR IS LATIN-SCRIPT. Two space-separated `A-Za-z` words is the shape; a
 *      sentence in a non-Latin script matches nothing. This product's copy contract
 *      (EXPERIENCE.md) is English, so the residue is theoretical until a localisation story
 *      exists — which would own widening the detector, not this file.
 *   5. A SINGLE WORD RENDERED AS A JSX EXPRESSION CHILD. `<p>{'Loading'}</p>` is a string
 *      literal in no user-facing attribute that fails the two-word shape, so the file half
 *      never collects it. The content half still bans its characters; whether the word belongs
 *      in a copy module is review's, like residue 2.
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

// git, not readdir — the authority every other guard in this project uses: node_modules, dist
// and coverage are invisible to it, and a committed module cannot escape CI. DECLARED LIMIT
// (the c4-7 false-green, corrected at review — this comment used to claim the opposite): an
// un-`git add`ed module is equally invisible, so a NEW module passes this sweep vacuously until
// it is staged. The tree-walk redesign is ledgered in deferred-work.md; until then the registry
// entry for a new module and the `git add` must land together.
/**
 * Wire-fixture modules: plain `src/` files holding VERBATIM backend responses for tests to share.
 *
 * Their sentences are DATA, not copy — authored by `src/logic/deck_validator.py` and arriving
 * over the network exactly as a card name does (c4-10 Q15) — so `COPY_MODULES` may not own them
 * (a copy owner holding wire sentences would make that Map's claim meaningless, decide-once rule
 * 14) and this scan must not collect them. A NAMED registry with a reason, rather than the
 * test-file blanket the c4-10 review's deferred C4-retro item warns about: adding a file here is
 * a declaration that every string in it is a recorded backend response, and the file's own pins
 * (`formatCheck.fixtures.test.ts`) are what hold that declaration to the shipped contract.
 */
const WIRE_FIXTURE_MODULES: Map<string, string> = new Map([
  [
    'src/state/formatCheck.fixtures.ts',
    'the format-check fixture bodies (story c4-10, review decision 2a) — verified-real or ' +
      'declared-synthetic `GET /api/deck/{id}/format-check` responses whose `detail` sentences ' +
      'are deck_validator.py output, shared by three test files and pinned by ' +
      'formatCheck.fixtures.test.ts. Split out of that test file because a test module imported ' +
      'by other test modules registers its describes in every importer.',
  ],
])

const shippedModules = execFileSync('git', ['ls-files', 'src/*.ts', 'src/*.tsx'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((file) => !/\.test\.tsx?$/.test(file))
  .filter((file) => !WIRE_FIXTURE_MODULES.has(file))

/**
 * Where user-facing copy may live -> why that module is a copy owner.
 *
 * A later story with a sentence in it — c2-10's attribution, c4-3's "Unknown card", c4-12's
 * empty-deck line, c6-6's empty push (which took the invitation this line held open for it, and
 * a second entry beside it for the fallback view title) — ADDS AN ENTRY HERE with its reason,
 * rather than inventing a second mechanism. That is decide-once ruling #1 of story c2-9.
 */
const COPY_MODULES: Map<string, string> = new Map([
  [
    'src/components/StatePanel/copy.ts',
    'the state-panel copy, and the ONLY place it lives — asserted byte-for-byte against ' +
      'EXPERIENCE.md by tests/copy.test.ts (story c2-9).',
  ],
  [
    'src/components/AppShell/AppShell.tsx',
    'the placeholder line for each empty region, each naming the story that replaces it, plus ' +
      'the product kicker and the h1 fallback (story c2-1, AC 21). Every one of these is copy ' +
      'with a scheduled death. And one permanent resident since c7-4: the "Updating…" line the ' +
      'reduced-motion swap shows while a refetch is in flight — authored, spelled with U+2026 ' +
      'because the epic AC and the UX-DR42 inventory both write it verbatim (UX-DR33: ship ' +
      'specified copy as specified), and asserted by codepoint in AppShell.test.tsx on the ' +
      'U+00B7 precedent. That trailing ellipsis does NOT contradict the c5-7 ruling that ' +
      'banned one after "Reconnecting": the pill names a STEADY state, where "…" promises the ' +
      'looping animation tokens.css bans repo-wide, while "Updating…" marks a bounded ' +
      'in-flight window that provably ends — the flag that shows it is cleared on every ' +
      'terminal path, drops and aborts included. Recorded here so the two rulings stay one ' +
      'coherent precedent: a trailing ellipsis is legal exactly when the state it decorates ' +
      'is guaranteed to finish.',
  ],
  [
    'src/components/Footer/copy.ts',
    'the Scryfall and Fan Content attribution — the one string in the app that is a condition ' +
      'of public release (NFR-08) rather than a design choice. Asserted byte-for-byte against ' +
      'DESIGN.md by tests/attribution.test.ts, which is a DIFFERENT artefact from the state ' +
      'panel gate above: copy is gated against whatever wrote it (story c2-10).',
  ],
  [
    'src/components/ManaCost/parse.ts',
    'the word table `describeManaCost` speaks a mana cost from — "2 generic, white or blue" ' +
      '(story c2-8, UX-DR18). Prose assembled from single words, which is why it is listed ' +
      'DELIBERATELY rather than caught: see residue 2 in this file header.',
  ],
  [
    'src/components/DeckBadges/DeckBadges.tsx',
    'the two size-badge labels — the only words story c4-2 puts on screen. The deck NAME and ' +
      'the FORMAT beside them are data, not copy, and arrive as props; these two are authored, ' +
      'so they are declared here rather than smuggled past the prose detector as single words ' +
      '(which is residue 5 of this file header, and using it deliberately would be an evasion ' +
      'of the guard rather than a use of it). The legality claim the mock shows beside them is ' +
      "c4-10's, over an endpoint c4-2 never calls.",
  ],
  [
    'src/components/CardPlaceholder/copy.ts',
    'the unknown-card placeholder label — the ONE authored string story c4-3 puts on screen, and ' +
      'a contract with an artefact rather than a structural fragment: EXPERIENCE.md spells it, ' +
      '`states.ts` routes `card_not_found` to it, and tests/unknown-card-copy.test.ts asserts the ' +
      'shipped constant against the artefact byte-for-byte — which is the assertion that file has ' +
      'promised since c3-2 would move here "the day c4-3 lands". The card NAME, TYPE LINE, mana ' +
      'COST and truncated ID the same component renders are DATA, arrive as props, and are ' +
      'deliberately not in this module: a copy owner that also held card names would make the ' +
      'claim this Map exists to state meaningless.',
  ],
  [
    'src/containers/CardDetail/copy.ts',
    'the card detail panel’s three authored strings (story c4-5): the panel TITLE — which is ' +
      'also its `role="region"` name and the `<h2>` c4-11’s skip link targets — the unpin ' +
      'control’s label, and the pin announcement UX-DR45 fires once per pin. The first copy ' +
      'module under `src/containers/`, and the reason the list is keyed on the FILE rather than ' +
      'on a directory. The announcement is gated byte-for-byte against the epic’s own template ' +
      'by tests/pin-announcement-copy.test.ts, the way the state-panel copy is gated against ' +
      'EXPERIENCE.md and the attribution against DESIGN.md: copy is gated against whatever ' +
      'wrote it. The card NAME, TYPE LINE, oracle TEXT and mana COST the same component renders ' +
      'are DATA, arrive from the wire, and are deliberately not in this module.',
  ],
  [
    'src/containers/FlipControl/copy.ts',
    'the DFC flip control’s accessible name — the ONE authored string story c4-6 puts anywhere ' +
      'near a screen, and it is never SEEN: it reaches a reader only through `aria-label`, which ' +
      'is why it is owned here rather than left as a literal in the component. DESIGN.md ' +
      'describes the control’s material, size, position and glyph and gives it no label at all, ' +
      'so the string is a decision (Q6) and the module states it. It is deliberately STATIC ' +
      '(Q11): a name that named the target face — "Show Murkwater Pathway" — would be card DATA ' +
      'in a read-aloud attribute, which is exactly what this file’s attribute half collects and ' +
      'what decide-once rule 16 forbids; the STATE travels on `aria-pressed` instead. The card ' +
      'NAME, its FACES and their TYPE LINES are data, arrive from the wire, and are not here.',
  ],
  [
    'src/containers/DeckList/copy.ts',
    'the deck list panel’s authored words (story c4-7): the panel TITLE — sourced from ' +
      'EXPERIENCE.md:36, which names this surface, with "panel" dropped because a `<section>` ' +
      'called "Deck list panel" announces its own kind twice — the COMMANDER and SIDEBOARD ' +
      'labels, and the nine type-group HEADINGS. The two board labels are specified in NO ' +
      'artefact and were handed here by name (deckGroups.ts:188, CardGrid.tsx:27), so they are ' +
      'decisions this module states rather than quotes. The group headings sit on the copy side ' +
      'of the data line even though they are named after card types, and the distinction is the ' +
      'one a later reader will question: `TYPE_GROUPS`’ members are the STORE’s internal ' +
      'vocabulary, never the wire’s — `type_line` says "Legendary Creature — Human Soldier", ' +
      'nothing on the wire says "Creature" alone and nothing at all says "Creatures". The plural ' +
      'forms were chosen by an author from DESIGN.md’s one worked example, which is what makes ' +
      'them copy; uppercasing stays in CSS so the accessible name keeps the readable word. The ' +
      'card NAMES, TYPE LINES, mana COSTS and QUANTITIES the same component renders are DATA, ' +
      'arrive from the wire, and are deliberately not in this module.',
  ],
  [
    'src/containers/ManaCurve/copy.ts',
    'the mana curve panel’s authored words (story c4-8): the panel TITLE, the `<figure>`’s own ' +
      'accessible NAME — deliberately a different string, because a region and the graphic ' +
      'inside it sharing one name makes a screen-reader user hear it twice with nothing to tell ' +
      'them apart — the visually-hidden table’s CAPTION and its two column HEADERS, the `+` that ' +
      'makes the last bucket open-ended, and the per-bar name BUILDER. That builder is why this ' +
      'module matters more than its size suggests: it is residue 3 of this file’s own header — a ' +
      'string reaching an `aria-label` through an EXPRESSION, which the attribute half cannot ' +
      'read — so the words are declared here first rather than left as literals in the ' +
      'component, and the content half then scans every one of them. UX-DR17 supplies exactly ' +
      'one worked example ("3 drops: 8 cards") and NO pluralisation rule, so "1 drop: 1 card" is ' +
      'INVENTED and the module says so in the open; the open-ended bucket keeps the plural ' +
      'because "7+" names a range rather than one value. The COUNTS and the MANA VALUES ' +
      'interpolated into those sentences are DATA, computed from the deck, and are deliberately ' +
      'not in this module.',
  ],
  [
    'src/containers/ColourDistribution/copy.ts',
    'the colour distribution panel’s authored words (story c4-9): the panel TITLE — sourced ' +
      'verbatim from DESIGN.md:408’s anatomy list, exactly as c4-8 sourced "Mana curve" — the ' +
      '`<figure>`’s own accessible NAME (a different string, for c4-8’s reason: a region and the ' +
      'graphic inside it sharing one name makes a screen-reader user hear it twice), the six ' +
      'COLOUR NAMES, the unit noun in "12 pips" and the "%" sign. The colour names carry more ' +
      'weight here than a label usually does, and that is the whole reason this module exists: ' +
      'Q9(iv) ships the legend’s ManaPip DECORATIVE, so UX-DR18’s "the legend is the accessible ' +
      'data path" resolves to these six words being the ONLY route by which a colour reaches a ' +
      'screen-reader user at all. They also sit on the copy side of the data line for ' +
      'GROUP_LABELS’ reason one axis over: the wire says "{W}" and parse.ts says "w", and ' +
      'NOTHING anywhere says "White" — an author chose it. A SECOND word table for the six ' +
      'colours now exists beside parse.ts’s private COLOUR_NAMES, deliberately and in different ' +
      'registers (that one is lowercase inside a spoken sentence, this one capitalised and ' +
      'standalone), and the module states the divergence rather than leaving two lists silent. ' +
      'The pluralisation of "pip" is INVENTED — UX-DR18 specifies no noun at all — and says so. ' +
      'The COUNTS and the PERCENTAGES are DATA, computed from the deck, and are not here.',
  ],
  [
    'src/containers/FormatCheck/copy.ts',
    'the format check panel’s authored words (story c4-10): the panel TITLE — sourced from ' +
      'DESIGN.md:423 and EXPERIENCE.md:37, with "panel" dropped for DECK_LIST_TITLE’s reason — ' +
      'the six row LABELS, and the three STATUS WORDS the badge carries. This module exists ' +
      'because the wire has NO label field at all: `check` is a machine token (`copy_limit`), ' +
      'and nothing on the wire, in DESIGN.md or in EXPERIENCE.md’s prose ever says "Copy limit". ' +
      'Two of the six labels are decisions rather than quotations and the module states both: ' +
      'the mock’s first slot holds a FORMAT STRING ("Standard"), not a label, which Q14 keeps ' +
      'out of this panel’s chrome — so "Legality" is authored from EXPERIENCE.md:37’s IA row — ' +
      'and the mock’s "Banned or restricted" is a FALSE label that does not ship, because ' +
      'deck_validator.py reports a `restricted` card through the LEGALITY row deliberately and ' +
      'pinned, so a row so labelled could never fire for one. The three status words are the ' +
      'wire’s own vocabulary rather than the mock’s six derived values ("60 / 60", "no ' +
      'violations", "11 cards"), which are on the wire nowhere and whose computation would be a ' +
      'construction rule written in TypeScript — the fifth declared hole in c3-3’s own rule ' +
      'guard, which find_rule_violations states in writing it cannot see. THE SIX `detail` ' +
      'SENTENCES ARE NOT HERE AND MUST NOT BE: they are authored by src/logic/deck_validator.py ' +
      'and arrive over the wire exactly as a card name does, so moving them here would make this ' +
      'Map’s whole claim meaningless (decide-once rule 14). Uppercasing stays in Badge.css so ' +
      'the readable word survives for anyone copying the text.',
  ],
  [
    'src/containers/SkipLink/copy.ts',
    'the skip link’s one authored string (story c4-11): "Skip past the deck grid", the visible ' +
      'text and therefore the accessible name of the first Tab stop in the document. It is here ' +
      'for the ordinary reason every copy module is — a sentence the user reads needs one ' +
      'address for UX-DR33’s voice rules to point at — but it is UNUSUAL in this epic for having ' +
      'NOTHING TO RULE: DESIGN.md:418, EXPERIENCE.md:100 and epics:506 all carry the string byte ' +
      'for byte, with no disagreement about case, punctuation or wording, so it is transcribed ' +
      'rather than authored and the content half below compares it against the artefact. WHAT ' +
      'THE WORDS PROMISE IS ALSO A MEASURED CLAIM AND THE MODULE STATES IT: "past the deck grid" ' +
      'is exactly what the link delivers and deliberately no more — it moves focus to the card ' +
      'detail panel’s heading, and on the largest real deck the FOOTER is still 101 Tab stops ' +
      'beyond that, because c4-7’s deck list sits between them. A label promising the end of the ' +
      'page would be a label that lies on 36 of 40 real decks, so the residue is carried on c8-6 ' +
      'by name instead of being papered over with wording. No other words: the link announces ' +
      'nothing (there is no aria-live here — the app’s polite regions are CardDetail’s pin ' +
      'announcement and, since c5-7, the connection pill’s; this string is in neither), and the ' +
      'DOM id it targets is a handle rather than copy, so SKIP_TARGET_ID ' +
      'lives in focusHome.ts where both sides of the lookup can import it.',
  ],
  [
    'src/containers/CardGrid/copy.ts',
    'the empty-deck line (story c4-12): "This deck is empty — ask your agent to add cards.", the ' +
      'ONE authored sentence a deck with zero cards on every board puts on the glass, rendered in ' +
      'place of the grid’s `<ul>` inside the untitled `CardGrid` panel. Like the skip link’s ' +
      'string it is TRANSCRIBED rather than authored — EXPERIENCE.md’s Voice and Tone table ' +
      'carries it, em dash U+2014 and trailing period included — and tests/empty-deck-copy.test.ts ' +
      'compares the shipped constant against that table cell byte-for-byte, which is copy gated ' +
      'against whatever wrote it, exactly as the state panel is against EXPERIENCE.md and the ' +
      'attribution against DESIGN.md. Shipping the artefact’s own words is ALSO the disposition of ' +
      'a permanently-open ledger entry: the copy guard can check registration and banned ' +
      'characters and cannot judge whether a sentence is blameless, and its own text says "a ' +
      'reviewer of c2-10, c4-3, c4-12 and c6-6 must READ the copy" — c4-3 discharged that ' +
      'judgement by shipping EXPERIENCE.md’s label verbatim and recorded that c4-12 owed the same ' +
      'reading, which the story’s Debug Log records having performed. The module holds NOTHING ' +
      'ELSE: the panel is untitled by c4-4’s ruling so there is no title here, the deck NAME and ' +
      'COUNTS an empty deck still renders are data on other components, and the line is not ' +
      'announced — no aria-live anywhere near it. (That clause used to end "CardDetail’s single ' +
      'polite region stays the app’s only one"; c5-7 shipped the second, so the claim that ' +
      'survives is the one this module actually makes: the empty-deck line does not announce.)',
  ],
  [
    'src/containers/ConnectionPill/copy.ts',
    'the connection pill’s words (story c5-7): the three STATE WORDS — "Connected", ' +
      '"Reconnecting", "Backend gone — retrying quietly" — the em-dash SEPARATOR that joins a ' +
      'state to the active deck’s name, and the builder that assembles the pill’s whole text. It ' +
      'is the FIRST module in this Map that AUTHORS rather than transcribes, and the reason is ' +
      'that no artefact ever specified these strings: DESIGN.md:479 describes the pill’s ' +
      'material — a dot, micro text "naming the state", the deck name — and gives not one word of ' +
      'that text, while EXPERIENCE.md:97’s "live · reconnecting · backend gone" is a vocabulary ' +
      'for the spec’s readers rather than copy for the glass. So the strings are a DECISION (Q3, ' +
      'Brad 2026-08-08), stated here in the open, written into EXPERIENCE.md’s connection-pill ' +
      'copy row in the same commit, and gated against that row by ' +
      'tests/connection-pill-copy.test.ts — copy is gated against whatever wrote it, and when a ' +
      'story is what writes it, the artefact and the constant land together. TWO VOICE DECISIONS ' +
      'ARE LOAD-BEARING AND THE MODULE ARGUES BOTH: there is no ellipsis after "Reconnecting", ' +
      'because a trailing "…" promises the animation tokens.css:305-312 bans repo-wide while ' +
      'naming this very component as the reason the ban exists — a ruling about STEADY states, ' +
      'not a flat character ban: c7-4\'s "Updating…" is the recorded exception (see the AppShell ' +
      'entry above), legal because it marks a bounded in-flight window whose flag is cleared on ' +
      "every terminal path, where the pill's states persist indefinitely and an ellipsis there " +
      'would promise motion that never ends; and "Backend gone" states a fact ' +
      'about a process rather than blaming anyone, which is UX-DR33’s rule applied to the one ' +
      'string in this app most likely to reach for an apology. The DECK NAME is data — it arrives ' +
      'from the wire through the deck slice and is deliberately not in this module.',
  ],
  [
    'src/containers/AgentView/copy.ts',
    'the agent view shell’s two chrome strings (story c6-5): the "AGENT VIEW" accent KICKER ' +
      'and the "Close · esc" PILL LABEL. Both are transcribed from DESIGN.md rather than ' +
      'authored — the shell’s own component row (:471) names the kicker and the pill in ' +
      'those words — so this module quotes an artefact the way the state-panel copy quotes ' +
      'EXPERIENCE.md, and the pin that holds it is AgentView.test.tsx asserting the exact ' +
      'bytes rather than a second verbatim gate: DESIGN.md carries these inside a component ' +
      'anatomy row rather than in a copy table, so there is no artefact ROW to join against ' +
      'the way tests/copy.test.ts joins the six state-panel bodies. The pill label is the ' +
      'app’s only accessible name containing a KEY name, and that is UX-DR23 asking the ' +
      'shell to teach its Esc dismissal rather than leave it to be discovered. The separator ' +
      'is U+00B7 MIDDLE DOT with spaces around it, asserted by codepoint, because "looks ' +
      'like a dot" is exactly the class of difference an eye scanning a diff waves through. ' +
      'The view’s TITLE and its summary COUNT are DATA — they arrive as props from the ' +
      'store, and since c6-6 from a pushed envelope — and are deliberately not in this ' +
      'module. The one exception c6-6 makes to that sentence is registered separately below: ' +
      'the word a view is called when the agent supplies NO title is authored copy, and it ' +
      'lives in the state layer beside the builder that applies it, not here.',
  ],
  [
    'src/state/agentView.ts',
    'the app’s WORD FOR EACH KIND OF AGENT VIEW — `AGENT_VIEW_LABELS`, four strings: ' +
      '"Suggestions" / "Swaps" / "Tier list" / "Card groups" (story c6-8, Task 2), which serve ' +
      'as BOTH the nav pill’s label and the fallback title a view is called when the pushed ' +
      '`payload.title` is absent, null or blank (story c6-6, Q7 — the entry this one grew ' +
      'from, and `SUGGESTIONS_VIEW_TITLE` is now read off the table rather than declared ' +
      'beside it, so the two spellings cannot drift). Sentence case as stored; ' +
      '`{typography.label}` uppercases at render, which is a STYLE and not a spelling — the ' +
      'string a screen reader speaks is the one in this table. THE FIRST ' +
      'ENTRY IN THIS MAP UNDER `src/state/`, and the placement is the decision worth stating. ' +
      'A wire-supplied title is DATA and stays data; this is what the app says when nobody ' +
      'named the view, which makes it authored copy with the same claim on this Map as any ' +
      'panel title. It is not in `src/containers/AgentView/copy.ts` — the obvious home — for ' +
      'two reasons pointing the same way: `deferred-work.md`’s dialog-accessible-name entry ' +
      'asks for the non-blank guard "at the point content is constructed", which is ' +
      '`suggestionsViewOf` in this module, and a store may not import a container; and c6-8’s ' +
      'nav pill needs the same word for the same kind, so a constant owned by any single ' +
      'container would be the wrong address for its second reader (decide-once ruling #1 of ' +
      'story c2-9, applied across a layer boundary rather than within one) — and c6-8 IS that ' +
      'second reader, so the table is that prediction discharged rather than restated, with ' +
      'Epic 9’s three view stories the third, fourth and fifth readers already named. They are ' +
      'CAPITALISED AS NAMES rather than assembled from the wire kind — the rejected ' +
      'alternative — because a runtime-assembled user-facing string is residue 3 of this ' +
      'file’s own header, and because "Card groups" is not derivable from `groups` by any rule ' +
      'at all. The table is `satisfies Record<AgentViewKind, string>`, so a fifth kind on the ' +
      'Python side fails typecheck here naming the kind with no word yet. The ' +
      'module holds NOTHING ELSE of this kind: the pushed title, the count, the items, their ' +
      'reasons and the envelope’s `id`/`ts` are all DATA off the wire.',
  ],
  [
    'src/containers/AgentViewsNav/copy.ts',
    'the agent-views nav’s three strings (story c6-8; Q2, Q5, Q6). ONE IS TRANSCRIBED: the ' +
      'quiet pill’s "Your agent hasn’t sent this yet." is EXPERIENCE.md:73’s, byte for byte, ' +
      'and `tests/agent-views-nav-copy.test.ts` gates it against that row rather than against ' +
      'a retyped literal — which matters more than usual here, because the artefact’s ' +
      'apostrophe is the ASCII U+0027 and not the typographic U+2019 a reader of the rendered ' +
      'Markdown would assume. TWO ARE AUTHORED, on c5-7’s precedent for copy with no artefact ' +
      'until its story writes one, and both were written into EXPERIENCE.md’s nav-pill row in ' +
      'the same commit so the gate has a row to read: the group’s visible kicker "Agent views" ' +
      '(Q5 — the group has no `<nav>` landmark, so this is what names it, for everyone rather ' +
      'than for ARIA only), and the word "unread" (Q6), which sits visually-hidden inside an ' +
      'unread pill’s accessible name so the accent dot never carries that state in colour ' +
      'alone (UX-DR29, WCAG 1.4.1). WHAT IS DELIBERATELY NOT HERE: the four PILL LABELS. They ' +
      'are `AGENT_VIEW_LABELS` in `src/state/agentView.ts` — see that entry above — because a ' +
      'kind’s word has one owner, and a second copy of those four strings in this file is ' +
      'exactly the drift that ruling was made to prevent. The formatted push TIME is not copy ' +
      'either: it is wire data through `Intl.DateTimeFormat`, and a locale render has no bytes ' +
      'to gate.',
  ],
  [
    'src/containers/SuggestionsView/copy.ts',
    'the empty-push line (story c6-6, AC 4; amended at the epic-16 retro, item 4): "The ' +
      'agent’s {noun} came back empty. Nothing to show — ask it for another pass.", the ONE ' +
      'authored sentence a push carrying no items puts on the glass, rendered in place of the ' +
      'rows inside the agent view’s body. Like the empty-deck line it is TRANSCRIBED rather ' +
      'than authored — EXPERIENCE.md’s Voice and Tone table carries it, em dash U+2014 and ' +
      'trailing period included — and tests/empty-push-copy.test.ts compares the shipped ' +
      'constant against that table cell byte-for-byte, which is copy gated against whatever ' +
      'wrote it. It is the FIRST entry in this Map whose artefact string is a TEMPLATE: the row ' +
      'writes "{noun}" and enumerates the four display nouns beside it, so the constant ships ' +
      'the placeholder, a transcribed noun table (gated against the cell’s enumeration; pinned ' +
      'to lowercased AGENT_VIEW_LABELS from agentView.test.ts), and a one-line builder ' +
      'substitutes the kind’s noun — the kind is a closed wire literal, never user data, which ' +
      'is the whole of c6-4’s echo-hygiene rule applied here. The residue this entry declared ' +
      'for four epics (the wire-kind substitution read "an empty suggestions" and put ' +
      '"tier_list"’s underscore on the glass) was RULED release-gating and repaired ' +
      'artefact-first at the epic-16 retro. Shipping the artefact’s own words is ALSO the ' +
      'disposition of ' +
      'the permanently-open copy-guard entry whose text names this story: "a reviewer of ' +
      'c2-10, c4-3, c4-12 and c6-6 must READ the copy", and c4-12’s disposition recorded that ' +
      '"c6-6 still owes it" — the story’s Debug Log records the reading having been performed. ' +
      'The module holds NOTHING ELSE: the view’s title and count are the shell’s props, the ' +
      'card names and reasons a non-empty push carries are DATA, and the line is not announced ' +
      '— the heading’s live region is the view’s one announcement.',
  ],
  [
    'src/containers/SwapsView/SwapsView.tsx',
    'the swap tile’s two label templates (story 16.1): "Out · {N} copies" and "In · {N} ' +
      'copies", the literal wording `contracts.py`’s SwapItem docstring fixes and DESIGN.md’s ' +
      'swap-row row repeats. The words "Out", "In" and "copies" are authored — the wire carries ' +
      'only the quantities — so the component is declared here on the DeckBadges precedent ' +
      'rather than smuggled past the prose detector as template spans (residue 5 of this ' +
      'file’s header, and using it deliberately would be an evasion of the guard rather than a ' +
      'use of it). Plural always, zero included: the contract writes "N copies" literally, "0 ' +
      'copies" is a designed case, and no artefact specifies a singular form, so none is ' +
      'invented. The module also owns the confidence chip’s LABEL, "Confidence": DESIGN.md’s ' +
      'swap-row names a confidence StatChip and spells no label word for it, so the word is ' +
      'authored here, while the chip’s VALUE stays the wire token — data, not copy. The module ' +
      'holds NOTHING ELSE authored: the empty-push line is ' +
      '`SuggestionsView/copy.ts`’s shared template (one sentence, one owner — the reason this ' +
      'story ships no copy.ts of its own), the rationale and confidence value a row renders are ' +
      'DATA off the wire, and the arrow glyph is aria-hidden chrome.',
  ],
  [
    'src/containers/DeckAnnouncer/copy.ts',
    'the deck-refetch announcement (story c7-5, UX-DR45): "Deck updated — {N} card(s)", the one ' +
      'sentence the coalesced-refetch live region ever speaks — exactly once per settled ' +
      'refetch, on completion. TRANSCRIBED rather than authored: EXPERIENCE.md’s live-region row ' +
      'and the epic’s Story 7.5 AC both carry the worked example "Deck updated — 62 cards", ' +
      'spaced em dash U+2014 included, and tests/deck-announcement-copy.test.ts gates the ' +
      'shipped builder against both artefacts — copy is gated against whatever wrote it. The ' +
      'singular "1 card" is INVENTED on ManaCurve/copy.ts’s recorded precedent (no artefact ' +
      'states a one-card form) and the module says so in the open. The COUNT is data — ' +
      'mainboard_count + sideboard_count off the wire, summed in the builder so the announced ' +
      'number and the group-header counts can never disagree (deckGroups.ts’s conservation ' +
      'identity) — and the deck’s NAME is deliberately not in the sentence.',
  ],
])

/**
 * Attributes whose value is read aloud, whatever its shape.
 *
 * This IS an enumerated list — the one shape the epic's standing rule warns about — because the
 * ARIA family genuinely cannot be keyed structurally: `aria-live` and `aria-hidden` carry
 * single-token values that are chrome, so `aria-*` as a family would redden every component.
 * The mitigation is stated instead of pretended away: the list carries every string-valued
 * ARIA attribute of the current spec (the braille and valuetext ones were absent until the
 * review of 2026-07-29 found the gap), and a new read-aloud attribute joining the platform
 * must be added HERE, which review checks the day a story first uses it.
 */
const USER_FACING_ATTRIBUTE = new Set([
  'aria-label',
  'aria-description',
  'aria-roledescription',
  'aria-placeholder',
  'aria-valuetext',
  'aria-braillelabel',
  'aria-brailleroledescription',
  'alt',
  'title',
  'placeholder',
])

/**
 * PROSE, defined structurally: two or more space-separated words.
 *
 * Every chrome string this codebase produces is a single token by rules that are themselves
 * gated — `selector-class-pattern` makes class names kebab-case with no spaces, roles and
 * token names are single words, module specifiers are paths. A sentence has spaces between
 * words. That is the whole discriminator, and it is stated rather than tuned.
 */
const PROSE = /[A-Za-z][A-Za-z'’-]*\s+[A-Za-z][A-Za-z'’-]*/

interface FoundString {
  file: string
  line: number
  text: string
  /** Why it was collected — which makes the two halves able to ask different questions. */
  source: 'jsx-text' | 'attribute' | 'prose' | 'any-string'
}

/**
 * Attributes whose value is a SPACE-SEPARATED MACHINE TOKEN LIST, which is chrome by
 * construction — see the walker below for why this is keyed on the attribute rather than on the
 * string.
 *
 * `rel` joined in story c2-10, MEASURED not anticipated: the footer's
 * `rel="noopener noreferrer"` is two space-separated Latin words and matched `PROSE` exactly,
 * failing the file half against a component that contains no copy at all. It is the same
 * category as `className` — HTML defines both as an unordered set of unique space-separated
 * tokens drawn from a fixed vocabulary, so neither can ever be a sentence.
 *
 * THIS LIST IS AN EXCLUSION LIST, WHICH IS THE ONE PLACE THIS EPIC'S "BAN THE FAMILY, NEVER
 * ENUMERATE MEMBERS" RULE INVERTS — and that is worth stating rather than leaving as an
 * inconsistency. A missing entry here produces a FALSE POSITIVE: a later story adding
 * `ping="/a /b"` or `sandbox="allow-scripts allow-forms"` goes red, reads this comment, and adds
 * its attribute in the open. A too-broad entry would produce a false NEGATIVE, which is the
 * failure that hides. So the list stays narrow and grows visibly, one measured member at a time.
 */
const TOKEN_LIST_ATTRIBUTE = new Set(['className', 'class', 'rel'])

/**
 * True when the attribute sits on an intrinsic (lowercase) JSX element — `<a rel>`, never
 * `<Hint rel>`. The walker's token-list skip is scoped by this, because HTML's grammar only
 * constrains HTML's own elements; on a component, any prop can carry any string.
 */
const isOnIntrinsicElement = (attribute: ts.JsxAttribute): boolean => {
  const owner = attribute.parent.parent
  return (
    (ts.isJsxOpeningElement(owner) || ts.isJsxSelfClosingElement(owner)) &&
    ts.isIdentifier(owner.tagName) &&
    /^[a-z]/.test(owner.tagName.text)
  )
}

/** Every literal string node in a file, whatever its position. The CONTENT half reads this. */
const allStringsIn = (file: string, source: string): FoundString[] =>
  walk(file, source, { includeEverything: true })

/**
 * Every string a reader could plausibly see: JSX text, a user-facing attribute, or prose.
 *
 * Template literals contribute their literal SPANS: `` `Phyrexian ${body}` `` yields
 * "Phyrexian ". The interpolated part is a runtime value and is residue 3.
 */
const userFacingStringsIn = (file: string, source: string): FoundString[] =>
  walk(file, source, { includeEverything: false })

function walk(
  file: string,
  source: string,
  { includeEverything }: { includeEverything: boolean },
): FoundString[] {
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true)
  const found: FoundString[] = []

  const at = (node: ts.Node) => tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1

  const visit = (node: ts.Node): void => {
    // A `className` value is CHROME BY CONSTRUCTION, and skipping the whole attribute subtree
    // is what makes that structural rather than a guess about the string. MEASURED, not
    // anticipated: the first version of this guard flagged `` `badge badge-${shown}` ``,
    // `` `mana-pip mana-pip-${…}` `` and `` `stat-chip-delta stat-chip-delta-${tone}` `` as
    // prose, because two space-separated class tokens look exactly like two words. Sniffing the
    // string instead ("is it all kebab-case?") would wave through a lowercase sentence like
    // 'ask your agent'. Class names have their own gate — stylelint's `selector-class-pattern`
    // — so nothing is left unpoliced by excluding them here. The CONTENT half still reads them.
    //
    // `rel` joined the set in c2-10 for the identical reason and with the identical measurement
    // (`rel="noopener noreferrer"`); see TOKEN_LIST_ATTRIBUTE for why this one list grows by
    // enumeration while every other rule in this epic bans by family.
    //
    // INTRINSIC ELEMENTS ONLY (review find, 2026-07-30): the token-list grammar is a property
    // of HTML's vocabulary, not of the attribute NAME. A custom component is free to treat a
    // prop called `rel` (or `className`) as arbitrary copy — `<Hint rel="ask your agent…" />` —
    // so the skip stops at real HTML, where a lowercase tag is what "real HTML" means to JSX.
    if (
      !includeEverything &&
      ts.isJsxAttribute(node) &&
      ts.isIdentifier(node.name) &&
      TOKEN_LIST_ATTRIBUTE.has(node.name.text) &&
      isOnIntrinsicElement(node)
    ) {
      return
    }

    if (ts.isJsxText(node)) {
      const text = node.text.trim()
      if (/[A-Za-z]/.test(text)) {
        found.push({ file, line: at(node), text, source: 'jsx-text' })
      } else if (includeEverything && text !== '') {
        // LETTERLESS JSX TEXT IS STILL ON SCREEN. `<p>🎉</p>` and `<p>!</p>` contain no letter,
        // so the file half's prose shapes rightly ignore them — but the first version of this
        // walker yielded them to NEITHER half, which was a spelling of the evasion this guard
        // exists for, found by the review of 2026-07-29. The content half reads them.
        found.push({ file, line: at(node), text, source: 'any-string' })
      }
    } else if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node)
    ) {
      // A module specifier is a path, never copy. Excluded by its POSITION in the tree rather
      // than by looking at the string, so `import './Panel.css'` and a same-named copy string
      // are told apart correctly.
      const parent = node.parent
      const isSpecifier =
        (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) &&
        parent.moduleSpecifier === node

      if (!isSpecifier) {
        const attribute =
          ts.isJsxAttribute(parent) && ts.isIdentifier(parent.name)
            ? parent.name.text
            : ts.isJsxAttribute(parent.parent) && ts.isIdentifier(parent.parent.name)
              ? parent.parent.name.text
              : undefined

        if (attribute !== undefined && USER_FACING_ATTRIBUTE.has(attribute)) {
          // AN EMPTY `alt` IS THE ABSENCE OF COPY, NOT COPY — AND `alt` ALONE (story c4-4;
          // narrowed to its motivating case by review ruling 2026-08-04). The first component
          // in this codebase to write an `alt` attribute wrote `alt=""` — the WCAG-required
          // spelling for a decorative image, the whole point of UX-DR48's row-thumbnail clause
          // — and this branch collected the empty string, so the file half demanded that a
          // component owning NO WORDS AT ALL join COPY_MODULES.
          //
          // The exemption is `alt`-scoped ON PURPOSE: `alt=""` is the one empty spelling with a
          // defined, correct meaning ("decorative"). An empty `aria-label` is not its analogue —
          // it participates in the accname algorithm and can strip a control's name to the empty
          // string, which is a defect this gate should surface (as "copy that needs an owner",
          // the only voice it has) rather than bless. Whitespace-only counts as empty here, so a
          // stray space inside `alt=" "` cannot re-open the false failure the narrowing fixed.
          // Both directions are proven in the pairs below.
          if (!(attribute === 'alt' && node.text.trim() === '')) {
            found.push({ file, line: at(node), text: node.text, source: 'attribute' })
          }
        } else if (PROSE.test(node.text)) {
          found.push({ file, line: at(node), text: node.text, source: 'prose' })
        } else if (includeEverything && node.text !== '') {
          found.push({ file, line: at(node), text: node.text, source: 'any-string' })
        }
      }
    }
    ts.forEachChild(node, visit)
  }

  visit(tree)
  return found
}

/** THE FILE HALF: prose outside a declared copy module. */
const findCopyOutsideACopyModule = (
  files: string[],
  read: (file: string) => string = sourceOf,
  owners: Map<string, string> = COPY_MODULES,
): string[] =>
  files
    .filter((file) => !owners.has(file))
    .flatMap((file) =>
      userFacingStringsIn(file, read(file)).map(
        (hit) =>
          `${hit.file}:${hit.line} renders user-facing copy: ${JSON.stringify(hit.text)}. ` +
          `Every sentence the user reads lives in a declared copy module, so UX-DR33's voice ` +
          `rules have one address to point at (story c2-9, AC 13). Move it into one of ` +
          `[${[...owners.keys()].join(', ')}], or add this file to COPY_MODULES in ` +
          `tests/copy-rules.test.ts with the reason it owns copy.`,
      ),
    )

/**
 * THE CONTENT HALF: the bans, keyed by CHARACTER FAMILY wherever a family exists.
 *
 * "Ban the family, never enumerate members" is this epic's standing review finding in five
 * consecutive stories, and an emoji is the case that proves it — there is no list of emoji you
 * can write down that is still complete next year.
 *
 *   EMOJI -> `\p{Extended_Pictographic}`, the Unicode property itself. Every pictograph,
 *   including ones assigned after this was written, with no list to maintain.
 *
 *   EXCLAMATION MARK -> NFKC-normalise, then look for `!`. Unicode's own compatibility
 *   decompositions do the enumerating: `！` (FF01), `︕` (FE15) and `﹗` (FE57) all fold to `!`,
 *   `‼` (203C) folds to `!!` and `⁉` (2049) to `!?`. A hand-written list of those five is
 *   exactly the kind of list c2-8's review round rejected; this derives them.
 */
const BANNED: { name: string; hit: (text: string) => boolean; why: string }[] = [
  {
    name: 'an exclamation mark',
    hit: (text) => text.normalize('NFKC').includes('!'),
    why: 'UX-DR33: calm, terminal-literate copy. The full-width and compatibility spellings fold to `!` under NFKC and are caught by the same check.',
  },
  {
    name: 'an emoji or pictograph',
    hit: (text) => /\p{Extended_Pictographic}/u.test(text),
    why: 'UX-DR33: no emoji, no mascot. Keyed on the Unicode property, so a pictograph nobody listed is still caught.',
  },
  {
    name: 'the banned phrase "something went wrong"',
    hit: (text) => /something\s+went\s+wrong/i.test(text),
    why: 'UX-DR33: never blame, and never be vague. Name what happened and give the next action.',
  },
]

const findBannedCopy = (files: string[], read: (file: string) => string = sourceOf): string[] =>
  files.flatMap((file) =>
    allStringsIn(file, read(file)).flatMap((hit) =>
      BANNED.filter((ban) => ban.hit(hit.text)).map(
        (ban) =>
          `${hit.file}:${hit.line} contains ${ban.name}: ${JSON.stringify(hit.text)}. ${ban.why}`,
      ),
    ),
  )

// ---------------------------------------------------------------------------------------

describe('user-facing copy lives in one place (AC 13, the file half)', () => {
  it('is reading real modules and finding the real copy in them (non-vacuity)', () => {
    // Three anchors, because an empty scan is the failure this whole file is shaped around.
    expect(shippedModules.length).toBeGreaterThan(10)
    expect(shippedModules).toContain('src/components/StatePanel/copy.ts')

    for (const [file, reason] of COPY_MODULES) {
      expect(shippedModules, `COPY_MODULES names ${file}, which git does not track`).toContain(file)
      expect(reason.length, `${file} is listed with no reason`).toBeGreaterThan(40)
      expect(
        allStringsIn(file, sourceOf(file)).length,
        `${file} is declared a copy module but the extractor found no strings in it`,
      ).toBeGreaterThan(0)
    }

    // THE SCALE ANCHOR, WHICH IS WHAT THE PER-MODULE THRESHOLD USED TO CARRY. It read
    // `toBeGreaterThan(3)` per module until story c4-3, and that number was tuned to modules
    // holding a table of words — it made a copy module with exactly ONE authored string fail for
    // being correct. `CardPlaceholder/copy.ts` is that module: its whole content is the label
    // `"Unknown card"` gated byte-for-byte against EXPERIENCE.md, and the card name, type line
    // and id the same component renders are DATA that must NOT be moved here. Padding the module
    // to satisfy a threshold would have been the exact failure its own header warns about.
    //
    // So the per-module check became "the extractor sees something", and the strength moved to
    // where it belongs: a TOTAL across the declared modules, which still fails loudly if the AST
    // walk silently stops returning strings — the failure this whole file is shaped around.
    const total = [...COPY_MODULES.keys()].reduce(
      (sum, file) => sum + allStringsIn(file, sourceOf(file)).length,
      0,
    )
    expect(
      total,
      'the string extractor is returning almost nothing across every copy module',
    ).toBeGreaterThan(20)

    // And the extractor really sees the artefact copy, not merely "some strings".
    expect(
      userFacingStringsIn(
        'src/components/StatePanel/copy.ts',
        sourceOf('src/components/StatePanel/copy.ts'),
      ).map((hit) => hit.text),
    ).toContain('No deck on the glass.')
    // …and the CONTENT half's extractor reaches strings the prose detector never would: the
    // word table `describeManaCost` speaks a cost from is entirely single words.
    expect(
      allStringsIn('src/components/ManaCost/parse.ts', sourceOf('src/components/ManaCost/parse.ts'))
        .length,
    ).toBeGreaterThan(10)
  })

  it('finds no user-facing copy outside a declared copy module', () => {
    expect(findCopyOutsideACopyModule(shippedModules)).toEqual([])
  })

  it.each([
    ['an empty alt', '<img alt="" />'],
    ['a whitespace-only alt', '<img alt=" " />'],
  ])('does not read %s as copy — the silent half (c4-4)', (_label, markup) => {
    // MEASURED BY c4-4, WHICH WROTE THE FIRST `alt` IN THIS CODEBASE. `alt=""` is the
    // WCAG-required spelling for a decorative image — the card tile's picture is decorative
    // because its caption names it, which is UX-DR48's own row-thumbnail logic — and the first
    // draft of this walker collected the empty string, so the file half demanded that a
    // component containing NO WORDS join COPY_MODULES. A copy owner that owns no copy makes
    // this Map's claim meaningless, which is the failure the c4-3 threshold change was already
    // about. The whitespace spelling is exempt too, so one stray keystroke inside the quotes
    // cannot re-open the same false failure.
    expect(
      findCopyOutsideACopyModule(['src/probe.tsx'], () => `export const P = () => ${markup}`),
    ).toEqual([])
  })

  it.each([
    ['alt', '<img alt="Black Lotus, a jewelled flower" />'],
    ['aria-label', '<span aria-label="four copies in the deck" />'],
    // The exemption is `alt`-scoped (review ruling 2026-08-04): an empty `aria-label` strips a
    // control's accessible name — a defect, not a decorative declaration — so it is COLLECTED,
    // and the demand to join COPY_MODULES is the flag that makes someone look at it.
    ['an EMPTY aria-label', '<span aria-label="" />'],
    ['an EMPTY title', '<a title="" />'],
  ])('still reads %s as copy — the firing half (c4-4)', (_label, markup) => {
    expect(
      findCopyOutsideACopyModule(['src/probe.tsx'], () => `export const P = () => ${markup}`),
    ).toHaveLength(1)
  })
})

describe('what that copy may not contain (AC 6, AC 13, the content half)', () => {
  it('ships no exclamation mark, emoji or blame anywhere in src', () => {
    // Over EVERY module, not only the copy owners: the ban costs nothing to apply widely, and
    // the generated `types.d.ts` is included deliberately — its occurrence of the banned phrase
    // is in a JSDoc comment, which the AST never yields, so this scan proves that claim rather
    // than assuming it.
    expect(findBannedCopy(shippedModules)).toEqual([])
  })

  it('reads the generated wire types without tripping on the ban they QUOTE', () => {
    // The measurement this file was designed around, asserted rather than described: the phrase
    // IS in that file, and the guard is silent because it is in a comment.
    expect(sourceOf('src/api/types.d.ts').toLowerCase()).toContain('something went wrong')
    expect(findBannedCopy(['src/api/types.d.ts'])).toEqual([])
  })
})

describe('the guard itself fires, and stays silent where it should (the other half)', () => {
  const OWNERS = new Map([['src/copy.ts', 'the fixture copy module, for these proofs.']])
  const probeFile = (source: string, file = 'src/thing.tsx') =>
    findCopyOutsideACopyModule([file], () => source, OWNERS)
  const probeBan = (source: string, file = 'src/thing.tsx') => findBannedCopy([file], () => source)

  it.each([
    ['a sentence in JSX text', 'export const A = () => <p>Ask your agent for a deck.</p>'],
    ['a sentence in a string literal', "export const message = 'Ask your agent for a deck.'"],
    ['a sentence in a template literal', 'export const m = `Ask your agent for a deck.`'],
    ['a sentence in a template span', 'export const m = (n: string) => `Ask your agent for ${n}`'],
    // A ONE-WORD accessible name, which the prose detector alone would miss entirely. This is
    // why the attribute list exists beside it.
    ['a one-word accessible name', 'export const A = () => <span aria-label="Loading" />'],
    ['an alt text', 'export const A = () => <span alt="Chart" />'],
    // One of the read-aloud attributes the list was missing until the review of 2026-07-29.
    ['a one-word aria-valuetext', 'export const A = () => <div aria-valuetext="High" />'],
  ])('catches %s outside a copy module', (_label, source) => {
    const findings = probeFile(source)
    expect(findings).toHaveLength(1)
    // The house rule: the message names the fix.
    expect(findings[0]).toContain('COPY_MODULES')
  })

  it('says nothing about the chrome strings every component is made of (the silent half)', () => {
    // If any of these tripped, the guard would be unusable and would be disabled — which is how
    // a gate becomes a comment. Each is a real shape from a real component in this repo.
    expect(
      probeFile(`
        import './Panel.css'
        import { filled } from '../filled'
        export const A = ({ live }: { live?: boolean }) => {
          const classes = ['panel']
          if (live) classes.push('panel-live')
          // The three class-name TEMPLATES this guard was measured against: two space-separated
          // class tokens read as two words to any prose detector, and all three shipped already.
          return (
            <section className={\`panel panel-\${live ? 'live' : 'rest'}\`} role="region">
              <span className={classes.join(' ')} />
              <span className="stat-chip-delta stat-chip-delta-positive" />
            </section>
          )
        }
      `),
    ).toEqual([])
  })

  it('says nothing about a `rel` token list, and still reads the link text (story c2-10)', () => {
    // THE SILENT HALF, with the exact shape that failed: `rel="noopener noreferrer"` is two
    // space-separated Latin words and matched PROSE, reddening a component containing no copy.
    // `target` needs no entry — `_blank` is a single token — which is why only `rel` was added.
    expect(
      probeFile(`
        export const A = () => (
          <a className="footer-attribution-link" href="https://example.test/x"
             target="_blank" rel="noopener noreferrer" />
        )
      `),
    ).toEqual([])

    // THE FIRING HALF, and the one that matters: excluding the ATTRIBUTE must not excuse the
    // ELEMENT. Real copy sitting inside the very same anchor is still caught, so the exclusion
    // is scoped to the attribute subtree rather than to links.
    const withCopy = probeFile(`
      export const A = () => (
        <a rel="noopener noreferrer" href="https://example.test/x">Read the policy here</a>
      )
    `)
    expect(withCopy).toHaveLength(1)
    expect(withCopy[0]).toContain('Read the policy here')

    // THE ELEMENT SCOPE (review find, 2026-07-30): the exclusion is a property of HTML's
    // vocabulary, not of the attribute name. A custom component treating `rel` as arbitrary
    // copy gets no skip — the grammar that makes the value chrome does not apply there.
    const onComponent = probeFile(
      'export const A = () => <Hint rel="ask your agent to add lands" />',
    )
    expect(onComponent).toHaveLength(1)
    expect(onComponent[0]).toContain('ask your agent to add lands')
  })

  it('keeps the CONTENT half reading token-list attributes (the exclusion is one-sided)', () => {
    // `includeEverything` ignores TOKEN_LIST_ATTRIBUTE entirely, so an emoji smuggled into a
    // `rel` or a `className` is still banned. Stated as an assertion because "the content half
    // still reads them" is a claim the comment makes twice and nothing proved.
    const found = probeBan('export const A = () => <a rel="noopener 🎉" />')
    expect(found).toHaveLength(1)
    expect(found[0]).toContain('an emoji or pictograph')
  })

  it('says nothing about prose INSIDE a declared copy module', () => {
    expect(
      findCopyOutsideACopyModule(
        ['src/copy.ts'],
        () => "export const m = 'Ask your agent for a deck.'",
        OWNERS,
      ),
    ).toEqual([])
  })

  it('never reads a COMMENT as copy — the measured reason this uses the AST', () => {
    // Both bans, quoted in a comment, in both comment syntaxes. Text-based guards fail here,
    // and this is the assertion that says the AST choice is load-bearing rather than tidy.
    const source = `
      /** Never say "something went wrong"! And no emoji 🎉 in copy. */
      // Also banned: "Something Went Wrong"!
      export const ok = 'panel-live'
    `
    expect(probeFile(source)).toEqual([])
    expect(probeBan(source)).toEqual([])
  })

  it('never reads the `!` OPERATOR as an exclamation mark', () => {
    // Nine of eleven modules under src/components/ use `!` as an operator. A text-based ban
    // fails on all nine the day it is written.
    expect(probeBan('export const a = (x: unknown) => !x && ![].length ? 1 : 2')).toEqual([])
  })

  it.each([
    ['a plain exclamation mark', "export const m = 'Deck loaded!'", 'exclamation'],
    // THE FAMILY PROBES: three spellings the ban never lists, folded by NFKC rather than by a
    // hand-written table.
    ['a full-width exclamation mark', "export const m = 'Deck loaded！'", 'exclamation'],
    ['a double exclamation mark', "export const m = 'Deck loaded‼'", 'exclamation'],
    ['an interrobang', "export const m = 'Deck loaded⁉'", 'exclamation'],
    // …and an emoji the ban never lists, from a block assigned long after most emoji lists.
    ['an emoji', "export const m = 'Deck loaded \u{1FAE0}'", 'emoji'],
    ['a mascot pictograph', "export const m = 'Sorry \u{1F63F}'", 'emoji'],
    [
      'the banned phrase',
      "export const m = 'Sorry, something Went   wrong.'",
      'something went wrong',
    ],
    // LETTERLESS JSX TEXT (review 2026-07-29): not a string-literal node and no `A-Za-z`, so
    // the first walker yielded these to neither half. The content half now reads them.
    ['an emoji as bare JSX text', 'export const A = () => <p>🎉</p>', 'emoji'],
    ['an exclamation mark as bare JSX text', 'export const A = () => <p>!</p>', 'exclamation'],
    // …and the enumerated-attribute gap the same review found: a read-aloud ARIA attribute the
    // original list never named, carrying a banned character in a single-word value.
    [
      'an emoji in an aria-valuetext',
      'export const A = () => <div aria-valuetext="high🔥" />',
      'emoji',
    ],
  ])('catches %s', (_label, source, expected) => {
    const findings = probeBan(source)
    // `toBeGreaterThan(0)` rather than an exact count, and the reason is itself a measurement:
    // `‼` and `⁉` are BOTH exclamation marks under NFKC and Extended_Pictographic characters, so
    // they legitimately trip two bans at once. Pinning the count would have made the guard being
    // right look like a defect. The silent-half tests above are what keep this honest.
    expect(findings.length).toBeGreaterThan(0)
    expect(findings.join(' | ')).toContain(expected)
  })

  it('catches a banned character in a SINGLE-WORD entry, which no prose detector sees', () => {
    // The MEASURED reason the content half is not gated behind the prose detector.
    const source = "export const W = 'white\u{1F7E1}'"
    const findings = findBannedCopy(['src/parse.ts'], () => source)
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain('emoji')
    // …and the file half is correctly SILENT on it, which is what makes the pair necessary
    // rather than redundant: neither half would have caught this alone.
    expect(findCopyOutsideACopyModule(['src/parse.ts'], () => source, OWNERS)).toEqual([])
  })
})
