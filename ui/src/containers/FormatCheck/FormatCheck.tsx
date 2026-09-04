import { Badge } from '../../components/Badge/Badge'
import type { BadgeTone } from '../../components/Badge/tones'
import { Panel } from '../../components/Panel/Panel'
import type { FormatCheckRow } from '../../api/schema'
import { useFormatCheck } from '../../state/formatCheck'
import './FormatCheck.css'
import { CHECK_LABELS, FORMAT_CHECK_TITLE, STATUS_WORDS } from './copy'

/**
 * The format check — six checks, one row each (UX-DR21, UX-DR44, UX-DR47, `DESIGN.md:376`,
 * `:423`, `EXPERIENCE.md:37`, `:96`).
 *
 * ================= THE THIRD CHILD OF THE RIGHT COLUMN =================================
 *
 * `.app-shell-column` is already `display:flex; flex-direction:column; gap: var(--space-panel-gap)`
 * (`AppShell.css:151-156`), so this stacks 24px beneath the deck list with no shell edit.
 * `AppShell.tsx` is NOT touched: its `right` placeholder still fires whenever the slot is empty,
 * which `AppShell.test.tsx` asserts against the component's own props.
 *
 * **This panel has NO requirement lineage in an FR, and citing one would be citing a requirement
 * that does not describe it.** FR-05 (grid + list + curve), FR-17 (the detail panel) and FR-19
 * (faces, flip, placeholders) are the nearest, and none mentions legality, format, banned cards or
 * a validation panel. The lineage is **UX-DR21**, **EXPERIENCE.md:37 / :96** and
 * **DESIGN.md:376 / :423**.
 *
 * ================= THE ROW HAS TWO SLOTS AND THE ENDPOINT HAS THREE FIELDS ==============
 *
 * `DESIGN.md:423` is the entire visual spec — *"label in `{typography.body}`
 * `{colors.text-secondary}`, `Badge` right-aligned, over `{components.legality-row.rule}`"* — and
 * the mock has exactly those two slots. But the wire carries **three** fields and 100% of the
 * information is in the third. Rendered to the letter, the one deck in forty with a real legality
 * violation draws `Legality` and a red pill, and the words **`'Pym Particles' is not legal in
 * brawl.`** appear nowhere on the glass — in a panel whose whole point is *"I find out about a
 * banned card"*.
 *
 * So the row is **three elements in two lines**: the label and the badge on the first, the
 * server-authored `detail` sentence on the second at `--text-tertiary` (**5.43:1** on
 * `--surface-panel`, measured, clear of the 4.5:1 floor). `DESIGN.md:236-237` and `:423` carry the
 * amendment.
 *
 * ⚠️ The sentence is `--type-body`, **not** `--type-micro`, and a GATE decides that rather than
 * taste: `--type-micro` carries an uppercase companion derived from DESIGN.md's own
 * `textTransform:` key, and an uppercased `'PYM PARTICLES' IS NOT LEGAL IN BRAWL.` destroys the
 * card name this panel exists to show. It is distinguished by TIER instead — the `.deck-row`
 * idiom. See `FormatCheck.css` for the three alternatives that were priced and declined.
 *
 * Two consequences, both accepted knowingly:
 *
 *   - **Row height stops being uniform.** Six rows of unequal height is fine; a design that
 *     assumed a fixed row is not, and nothing in the artefacts specifies one — there is no
 *     row-height token, no minimum and no number anywhere for this component.
 *   - **The rotation advisory is 86 characters on 40 of 40 decks, permanently**, so the second
 *     line is not an exception path — it is the panel's permanent height. Measured on the real
 *     screen at the eye-check rather than asserted here, because jsdom has no layout.
 *
 * The two alternatives were priced. A `title=` attribute is hover-only and banned by UX-DR39.
 * *"Detail only when `status !== 'pass'`"* would be a fourth vocabulary decision **and** would
 * hide the size sentence — `Mainboard has 100 cards; the minimum is 60.` is a PASS row, on 45% of
 * the deck table, saying a minimum forty cards below its format's real one.
 *
 * ================= `is_legal` IS BOUND TO NOTHING, AND THAT IS ASSERTED ================
 *
 * The trap: nothing machine-checkable stops `is_legal` being bound straight to the panel headline,
 * and a formatless deck would then render a red headline over six rows none of which is a
 * violation. The wire's own `Warning:` block says to read it as *"certified legal"*, not
 * *"something is wrong"*. Live exposure is **zero** (the trap needs an unrecognised format and all
 * 40 decks have one), which is exactly the condition under which a wrong binding ships green.
 *
 * So: **no headline, no summary badge, no `count` on the `Panel`, and no use of `Panel`'s own
 * `badges` slot** — that last one deliberately rather than by oversight, because it is a third
 * venue for the same synthesized verdict that **no component in this app uses**. UX-DR21 is *"one
 * row per check"* and nothing else; a synthesized verdict is a seventh row the artefacts do not
 * have.
 *
 * `ui/tests/format-check-source.test.ts` asserts the identifier `is_legal` appears nowhere in
 * `src/` outside the generated types and the declared fixture module, which turns that prose
 * `Warning:` into a machine-checkable fact. **The header legality pill does not ship either**: its
 * tone would have to be synthesized from the same fields in the one place with no rows beside it
 * to contradict it.
 *
 * ================= `format_recognized`: THIS COMPONENT DOES NOT READ IT, AND SAYS SO =========
 *
 * Not reading it is a fact about the backend, not an oversight here. A formatless deck is answered
 * with the **identical shape** — `deck_validator.py:550-556`, *"never a different body and never
 * an error"* — and the same function that sets `format_recognized: false` also rewrites the
 * `legality` and `banned` rows to `advisory` with `_unanswerable`'s sentence. So by the time a
 * renderer sees the report, *"this could not be checked"* is **already on the glass twice, in
 * words**. A branch on the boolean could only re-state what those two rows say, and the layout is
 * deliberately the same for a formatless deck; a class or a `data-` attribute with no styling and
 * no consumer would be decoration dressed as a read.
 *
 * What the field IS for is a **non-rendering** consumer — an agent, or a header pill — so it stays
 * on the wire even though this panel never reads it.
 *
 * **The behaviour under that state is pinned rather than assumed**: `FormatCheck.test.tsx` drives
 * a declared-synthetic formatless report through this component and asserts six rows, both
 * advisory sentences rendered, no violation tone anywhere, and **nothing negative produced by
 * `is_legal: false`** — the trap, made a passing test instead of a warning in a docstring.
 *
 * A `format === null` branch **would not compile**, because the generated type is `string`.
 *
 * ================= DISPLAY-ONLY, LITERALLY ============================================
 *
 * No handler, no `tabindex`, no `role="button"`, no inspection verb, nothing focusable. **This
 * panel adds ZERO Tab stops** (UX-DR21 *"display-only"*, UX-DR40, UX-DR47) and touches the
 * inspection slice not at all. It reads no `boards`, starts no hydration and imports the card
 * cache nowhere — worth stating because every sibling panel takes `boards` as its only prop and
 * copying that shape here would have been wrong.
 *
 * There is therefore no hydration re-drive window here at all: the panel derives nothing from the
 * card cache, so the deck sweep landing changes nothing it draws.
 *
 * ================= THE EMPTY CASE, AND WHY THERE ISN'T ONE ============================
 *
 * `ManaCurve` and `ColourDistribution` each hide themselves on their own data — a zero curve, a
 * zero pip total. **This panel's data is never empty: six rows, always.** So there is no self-gate
 * to lean on; hiding the analysis panels on an empty deck is a decision for all three at once, and
 * is deliberately not pre-implemented here.
 *
 * The one `null` this component does return is the state one: `'idle'`, `'loading'` and
 * `'refused'` all draw nothing. See `src/state/formatCheck.ts` for why a refusal is silent and
 * what that costs.
 */

/**
 * The tone each outcome wears (UX-DR21).
 *
 * **Total over the union, and `neutral` is UNREACHABLE by construction** — which is not tidiness
 * but a WCAG constraint: `neutral`'s `--border-strong` hairline is **1.75:1 on `--surface-panel`**
 * (the 1.89:1 figure quoted elsewhere is the `--surface-base` one, and this panel's badges sit on
 * the panel), under 1.4.11's 3:1 non-text floor. The four semantic borders measure **9.19 / 6.75 /
 * 10.59** and **6.21:1** and are fine. So a state distinguished by TONE is safe and a state
 * distinguished by the NEUTRAL BORDER is not — and the way this map guarantees the second never
 * happens is by never returning it.
 *
 * Text over its own 12% wash on `--surface-panel` measures `positive` **7.21:1**, `caution`
 * **8.14:1**, `negative` **5.60:1** — all three clear 4.5:1 with headroom, about 10% below the
 * same badges' figures on `--surface-base`. The alternate themes are unmeasured.
 *
 * ⚠️ `caution` is doing less work here than it looks like it is. `rotation` is advisory on **40 of
 * 40 decks, permanently and by design**, and every advisory in the 240-row corpus is that one
 * sentence — so a caution badge in this panel is FURNITURE, not a signal. A design reading
 * *caution = look at this* would cry wolf on 100% of decks. It stays `caution` because the status
 * genuinely is advisory and lying about it would be worse; what carries the meaning is the
 * sentence beneath.
 */
const TONE_FOR_STATUS = {
  pass: 'positive',
  advisory: 'caution',
  violation: 'negative',
  // `as const`, and it is load-bearing rather than idiomatic: without it every value infers as
  // `string`, which widens `Badge`'s `tone` prop to a type it refuses AND makes
  // {@link EveryToneIsARealBadgeTone} vacuously false — so `tsc` reports the coupling as broken
  // while the real defect is the inference. Measured: both errors, from this one missing keyword.
} as const

/**
 * The couplings, in BOTH directions, and each one catches a different mistake.
 *
 * They live here rather than in `copy.ts` for the reason that module's header gives: it must stay
 * import-free so `ui/tests/` can read it across the tsconfig project boundary, so the maps are
 * declared there and held to their unions here, where both halves are in scope.
 *
 *   {@link EveryCheckHasALabel} / {@link EveryStatusHasATone} — a SEVENTH check name or a FOURTH
 *   status arriving from the backend has no entry, and the row would render `undefined` beside a
 *   real badge. Not hypothetical in kind: `banned` itself was a later addition to the vocabulary.
 *
 *   {@link EveryLabelIsACheck} / {@link EveryToneKeyIsAStatus} — a label or tone written for a
 *   name the wire does not have is dead copy no render can reach. These also close the WIDENING
 *   hole, which is the one that actually bites: annotate either map `Record<string, string>` and
 *   `keyof` becomes `string`, which the first assertion still accepts and this one rejects.
 *
 * {@link EveryToneIsARealBadgeTone} is the third axis and it is separate on purpose: the first two
 * couple the map to the WIRE, this one couples its values to `BADGE_TONES`. Without it a typo
 * (`'postive'`) would satisfy both directions above and render an unstyled pill — the exact
 * failure `Badge`'s own runtime clamp was written for. **With it, the clamp is unreachable from
 * this call site**, which is the answer to that component's docstring: the clamp guards a MAPPING
 * here, not a raw wire value, and this assertion is what closes it at compile time.
 */
type Assert<T extends true> = T

export type EveryCheckHasALabel = Assert<
  [Exclude<FormatCheckRow['check'], keyof typeof CHECK_LABELS>] extends [never] ? true : false
>
export type EveryLabelIsACheck = Assert<
  [Exclude<keyof typeof CHECK_LABELS, FormatCheckRow['check']>] extends [never] ? true : false
>
export type EveryStatusHasAWord = Assert<
  [Exclude<FormatCheckRow['status'], keyof typeof STATUS_WORDS>] extends [never] ? true : false
>
export type EveryWordKeyIsAStatus = Assert<
  [Exclude<keyof typeof STATUS_WORDS, FormatCheckRow['status']>] extends [never] ? true : false
>
export type EveryStatusHasATone = Assert<
  [Exclude<FormatCheckRow['status'], keyof typeof TONE_FOR_STATUS>] extends [never] ? true : false
>
export type EveryToneKeyIsAStatus = Assert<
  [Exclude<keyof typeof TONE_FOR_STATUS, FormatCheckRow['status']>] extends [never] ? true : false
>
export type EveryToneIsARealBadgeTone = Assert<
  [Exclude<(typeof TONE_FOR_STATUS)[keyof typeof TONE_FOR_STATUS], BadgeTone>] extends [never]
    ? true
    : false
>

export function FormatCheck() {
  const state = useFormatCheck()

  // THE ONLY BRANCH IN THIS COMPONENT. `'idle'`, `'loading'` and `'refused'` all draw
  // nothing — never a skeleton, and never a bug panel over a working deck view. The panel
  // materialising ~5 ms after the deck (measured: median 5.2 ms per request in-process) is below
  // the threshold anything would notice.
  if (state.status !== 'report') return null

  const { report } = state

  return (
    /* A TITLED PANEL AT level="default". `<section aria-label>` is what puts "Format check"
       in a screen-reader user's landmark list, and the title is also the `<h2>` a skip link can
       target.

       NO `count` AND NO `badges`. Six is not a number worth putting in the chrome — it is the
       same six on every deck, forever — and the `badges` slot would be a third venue for a
       verdict this panel deliberately does not synthesize. */
    <Panel title={FORMAT_CHECK_TITLE}>
      {/* A `<ul>`/`<li>`, matching `DeckList` and `CardGrid`. Six checks are a list, and
          *"list, 6 items"* is orientation a column of loose divs does not give. A `<dl>` was the
          alternative and it implies a term/definition relationship that label → status word does
          not have once the row carries a third element.

          NO `role` OVERRIDE. ⚠️ This is the THIRD `<ul>` on the deck view, so `App.test.tsx`'s
          `getAllByRole('listitem')` counts are scoped per panel rather than document-wide, and
          this panel's own scoped count is asserted beside the grid's and the deck list's. */}
      <ul className="format-check-rows">
        {report.rows.map((row) => (
          /* THE ORDER IS THE PAYLOAD'S, AND NOTHING HERE SORTS, FILTERS OR GROUPS.
             `CHECK_ORDER` is declared in `deck_validator.py:487-494` and pinned on both sides —
             *"a consumer renders a stable panel because of this constant"*. A local list here
             would be a second copy of that decision, free to disagree with it; the test proves the
             point by feeding a SHUFFLED payload and asserting the render follows it. */
          <li className="format-check-row" key={row.check}>
            <span className="format-check-label">{CHECK_LABELS[row.check]}</span>
            {/* Right-aligned by the row's `minmax(0, 1fr) auto` grid — the first column absorbs
                the free space, so this content-sized track hugs the right edge (not GroupHeader's
                flex-idiom `margin-left: auto`, which is inert inside a content-sized grid cell).
                The word rides beside the tone so colour is never the sole carrier (UX-DR26,
                UX-DR29), and it can never be empty, which is what stops
                `Badge`'s empty-content `null` from silently dropping the pill. */}
            <span className="format-check-badge">
              <Badge tone={TONE_FOR_STATUS[row.status]}>{STATUS_WORDS[row.status]}</Badge>
            </span>
            {/* THE SERVER-AUTHORED SENTENCE. DATA, not copy: `deck_validator.py` writes it and
                interpolates card names, counts and format names into it. It is the only thing on
                this panel that can say WHICH card, which is the whole point of the panel — and it
                is also where the normalised `format` reaches the glass ("Every card is legal in
                brawl."), 24px from the STORED one in the header. Measured: 0 of 40 real decks
                differ, and nothing compares them. */}
            <p className="format-check-detail">{row.detail}</p>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
