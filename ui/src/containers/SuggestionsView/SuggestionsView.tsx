import type { AgentViewContent } from '../../state/agentView'
import { emptyPushLine } from './copy'
import './SuggestionsView.css'

/**
 * What a `suggestions` push puts INSIDE the agent view shell (story c6-6, AC 4; c6-7 fills it).
 *
 * ================= IT IS DELIBERATELY HALF A COMPONENT, AND THAT IS Q1's RULING ========
 *
 * Brad's Q1 ruling (2026-08-11): for a NON-EMPTY push this story renders **nothing** — the
 * shell's title and count are real, and the rows are c6-7's. The empty-push state ships real,
 * because AC 4 is one of this story's own acceptance criteria and the artefact carries its
 * sentence.
 *
 * That makes this module an interim shape on the umbrella branch rather than a finished
 * surface, which is the c6-4/c6-5 precedent (pushes were dropped entirely until now; merge is
 * not release, and nothing ships to a user until c8-4). The alternative — throwaway text rows
 * of `card_id` plus reason — was rejected as work c6-7 deletes, and because a rendered row is
 * what pulls the image, inspection and alt-text contracts forward a story early.
 *
 * It is named for the view rather than for the state so that **c6-7 extends this file instead
 * of creating one**: the empty branch below is already the right branch, and the rows go where
 * the `null` is. AC 3 of this story (an unknown card id degrades to the placeholder while the
 * rest of the push renders) has no subject until that happens, and is recorded as structurally
 * homed on c6-7's own AC 4 — the store retains the ids either way.
 *
 * ================= IT IS A CONTAINER, AND IT READS THE STORE'S TYPE ONLY ================
 *
 * `src/components/` is closed by a set-equality guard, and this module takes the store's content
 * type. That import is TYPE-ONLY and it reaches the STATE layer rather than `src/api/`: the wire
 * shape is `agentView.ts`'s to translate, and a body that took a `SuggestionsPayload` would be a
 * second reader of the envelope with a second opinion about absent fields.
 *
 * It holds no hook, no ref and no handler — today. It is here rather than in `src/components/`
 * because c6-7's rows need all three (the inspection contract is hover/focus/click), and moving
 * a module between the two trees after it has a stylesheet and a copy owner is a bigger diff
 * than putting it in the tree it belongs to now.
 */
export interface SuggestionsViewProps {
  /**
   * The push's own `kind`, interpolated into the empty-push line. Taken from the store's content
   * rather than hard-coded, because the artefact's sentence is a TEMPLATE with a `{kind}` hole in
   * it — writing `'suggestions'` here would be this module deciding what the wire said.
   */
  readonly kind: AgentViewContent['kind']
  /** The pushed rows. Empty is legal and is the state this story renders (AD-7, UX-DR33). */
  readonly items: AgentViewContent['items']
}

export function SuggestionsView({ kind, items }: SuggestionsViewProps) {
  // `length === 0` and never `!items.length` or `items.length ? … : …` — the c2-6 falsy-value
  // family in a numeric test, and `Panel.tsx:73-80`'s idiom. The store's builder guarantees an
  // ARRAY here for every payload the wire admits, so there is no third state to branch on.
  if (items.length !== 0) {
    // c6-7 renders the rows HERE. Rendering nothing is the honest interim answer — see the
    // header for why a throwaway row was rejected — and the shell's own header still reports
    // the real title and the real count, so a non-empty push is visibly a non-empty push.
    return null
  }

  // A bare `<p>`, and NOT a `StatePanel`: EXPERIENCE.md files the empty push under *Voice and
  // Tone* as an in-view line, exactly as it files the empty deck as an in-grid one, and c4-12
  // established that a single sentence in a surface's own body is not a panel. No `aria-live`
  // anywhere near it either — the view's announcement is the heading's, and a second region
  // inside the same dialog would announce the same arrival twice.
  return <p className="suggestions-view-empty">{emptyPushLine(kind)}</p>
}
