/**
 * The one focus hand-off in the app: give an element focus without leaving a Tab stop behind.
 *
 * ================= WHY THIS IS A MODULE AND NOT A SECOND COPY (c4-11 Q2, AC 6) =========
 *
 * Two callers need the identical four lines, and they were written for each other:
 *
 *   1. `CardDetail`'s unpin control (c4-5, review 2026-08-05). Activating it DESTROYS the
 *      activated element — the button renders only while pinned — and a removed `activeElement`
 *      drops keyboard focus to `<body>`, restarting Tab from the top of the page.
 *   2. `SkipLink` (c4-11). Its whole purpose is to move focus past the grid, to the same `<h2>`.
 *
 * `CardDetail.tsx:388` already said so before this module existed — *"the one element c4-11's
 * skip link already targets, so the two stories converge on a single focus home"* — and AC 6
 * makes it a requirement rather than a nicety: **there is exactly one focus home and one
 * implementation of it.** Two copies of this would be one that gets the blur cleanup repaired and
 * one that does not.
 *
 * It lives at the ROOT of `src/containers/` rather than inside either caller, under the rule
 * `src/components/filled.ts` states and `imagedFaces.ts`, `useCardArt.ts` and `frontFaceCost.ts`
 * already follow: *"a helper shared by two components does not live inside one of them"*. It is
 * its own module rather than an export beside a component because
 * `react-refresh/only-export-components` is an ESLint **error** — the eighth application of that
 * split.
 *
 * ================= WHY `tabIndex` IS SET IMPERATIVELY AND REMOVED ON BLUR ==============
 *
 * A heading is not focusable, so `.focus()` alone does nothing. `tabIndex = -1` makes it
 * programmatically focusable **without** adding a Tab stop — but if it were left behind, the panel
 * at rest would carry a `[tabindex]`, and that attribute's ABSENCE is what `CardDetail`'s AC 25
 * not-a-modal assertion checks. So it is added on the way in and removed on the way out, and the
 * element at rest is exactly what it was before.
 *
 * `{ once: true }` is load-bearing rather than tidy: without it every hand-off would stack another
 * listener on the same element, and a heading focused fifty times in a session would carry fifty
 * live listeners that each try to remove an attribute already gone.
 *
 * ================= WHAT IT DELIBERATELY DOES NOT DO ===================================
 *
 * **No scrolling.** `focus()` scrolls the target into view by default and that is correct here —
 * `.app-shell-columns` is the app's single scroll container (`AppShell.tsx:29-32`), so the browser
 * scrolls the column rather than the window, and a skip link that focused an off-screen heading
 * without showing it would satisfy WCAG 2.4.1 and fail the reader.
 *
 * **No focus trap, no return-focus contract.** `CardDetail` *"neither stacks nor traps"*
 * (UX-DR38); this moves focus once and forgets. c6-5's agent view is the app's only modal and
 * builds both of those FOR ITSELF, in `AgentView.tsx`, without changing anything here — it
 * calls this helper for the two hand-offs that are hand-offs (focus to its heading on open, and
 * the `<h1>` fallback when the element it remembered has left the document) and keeps its trap
 * and its restore ref private. The ordinary restore is a plain `.focus()` rather than this
 * function, deliberately: the remembered element HAD focus, so it is already focusable, and
 * writing `tabIndex = -1` onto a native control would evict a real Tab stop until its next blur.
 */

/**
 * The `id` on `CardDetail`'s frame — the skip link's target, and the only AUTHORED DOM id in
 * `ui/src`.
 *
 * *"The only DOM id"* until c6-5, which gives the agent view's `<h2>` one for `aria-labelledby`
 * — from `useId()` rather than from a constant, which is the distinction this line now draws
 * rather than a hole in it. The two cases are genuinely different: that id is minted and
 * consumed inside ONE element tree and cannot collide with anything, while this one is a
 * handle two modules in different directories have to agree on, which is exactly why it is
 * written down. A second hand-written id would be a second thing to keep unique; a `useId` is
 * not.
 *
 * A shared constant rather than two string literals, because the element that CARRIES it and the
 * code that LOOKS IT UP live in different directories, and a typo in either would fail silently:
 * `getElementById` returns `null`, `focusHome` refuses, and the link would simply do nothing on
 * activation with no test necessarily noticing. Both sides import this.
 *
 * Not copy, and deliberately not in a `copy.ts`: an `id` is never read aloud and reaches none of
 * the nine attributes `copy-rules.test.ts` collects. It is a DOM handle.
 *
 * Why an id at all, rather than the positional `querySelector('h2')` the panel uses internally:
 * `CardDetail` can scope its own lookup to its own frame ref, and the skip link cannot — it is
 * mounted OUTSIDE all three landmarks, before the `<header>`. A document-wide `'h2'` would find
 * the **mana curve's** heading, because the left column precedes the right in document order.
 */
export const SKIP_TARGET_ID = 'card-detail'

/**
 * Move keyboard focus to `target`, leaving no `[tabindex]` behind once focus departs.
 *
 * Args:
 *   target: The element to focus, or any of the nullish/`null` values the two DOM lookups that
 *     feed this can return. A non-element is refused rather than thrown on, because both call
 *     sites are event handlers where a throw would surface as a broken control.
 *
 * Returns:
 *   `true` if focus actually moved to `target` — verified against `document.activeElement`, not
 *   assumed from calling `.focus()` — and `false` when the target was missing or refused focus.
 *   Neither current caller branches on it (there is nothing more either could do on `false`; the
 *   `SkipLink` withdrawal hand-off's fallback IS this call), but the refusal path cleans up after
 *   itself: a failed `focus()` must not strand `tabindex="-1"` on the element, because that
 *   attribute's absence at rest is what `CardDetail`'s AC 25 not-a-modal assertion checks.
 *
 * Example:
 *   focusHome(document.getElementById(SKIP_TARGET_ID)?.querySelector('h2'))
 */
export const focusHome = (target: Element | null | undefined): boolean => {
  if (!(target instanceof HTMLElement)) return false
  // An element already carrying its own `tabindex` (the oracle scroller's `0`) is already
  // programmatically focusable — writing −1 over it and later REMOVING the attribute would
  // permanently evict a real Tab stop. Focus it as-is and leave its attribute alone.
  if (target.hasAttribute('tabindex')) {
    target.focus()
    return document.activeElement === target
  }
  target.tabIndex = -1
  target.addEventListener('blur', () => target.removeAttribute('tabindex'), { once: true })
  target.focus()
  if (document.activeElement !== target) {
    // Refused (inert/non-rendered target): the blur listener will never fire, so the attribute
    // it exists to remove is removed here instead.
    target.removeAttribute('tabindex')
    return false
  }
  return true
}
