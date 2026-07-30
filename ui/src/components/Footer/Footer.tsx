import './Footer.css'
import { ATTRIBUTION } from './copy'

/**
 * The Scryfall and Wizards Fan Content attribution (story c2-10, UX-DR32, NFR-08).
 *
 * THE ONLY COMPONENT IN THIS EPIC WHOSE DELIVERABLE IS A CONDITION OF PUBLIC RELEASE.
 * `DESIGN.md:375` says so in bold. Every other C2 component could ship slightly wrong and be
 * corrected in Epic 4; this one shipping wrong is a licensing defect. That is why the words are
 * gated byte-for-byte against the artefact (`tests/attribution.test.ts`) rather than reviewed by
 * eye, and why `App.test.tsx` asserts the component reaches the real screen rather than trusting
 * that it was wired.
 *
 * IT FILLS A SLOT; IT DOES NOT BUILD ONE. `AppShell` has held a `<footer>` open since c2-6 —
 * the element, the `contentinfo` landmark and the pinning mechanism (`height: 100dvh`,
 * `flex-shrink: 0`, one scroll container) all already exist and are already pinned by three
 * guards in `tests/shell.test.ts`. This component adds NO landmark role of its own: a nested
 * `contentinfo` would be two landmarks where `AppShell.test.tsx` asserts exactly one (AC 13,
 * UX-DR44). "Always visible" is likewise inherited rather than re-implemented — a second height
 * mechanism or a `position: sticky` here would be a regression against those guards, not a
 * belt-and-braces improvement.
 *
 * NO PROPS AT ALL (Q4, Brad 2026-07-30). The copy is fixed and both links are fixed, so a
 * `className` or a slot prop would be speculative generality. It is also the strongest available
 * form of AC 17's "presentation-only": a component with no props cannot have the defect c2-9's
 * Greptile round found, where a prop shape admitted a combination the prose forbids. No state,
 * no hook, no fetch, no store, no subscription, no `on*` handler, no `ref`.
 *
 * NO `react` IMPORT, DELIBERATELY. The automatic JSX runtime means a component with no
 * `ReactNode` prop needs none, and the text runs are rendered as bare strings rather than
 * wrapped in `Fragment`s — React does not require keys for strings in an array, only for
 * elements. The shorter import list is the stronger assertion in `PRIMITIVES`.
 */
export function Footer() {
  return (
    <p className="footer-attribution">
      {ATTRIBUTION.map((part, index) =>
        part.href === undefined ? (
          part.text
        ) : (
          <a
            // The index is a correct key here and nowhere near c2-9's duplicate-name problem:
            // ATTRIBUTION is a module constant that never reorders, never grows and never
            // filters, so position IS identity.
            key={index}
            className="footer-attribution-link"
            href={part.href}
            // Opens in a new tab — EXPERIENCE.md:101 and :144. `rel` is spelled out even though
            // `target="_blank"` implies `noopener` in every current browser: the explicit form is
            // what a reviewer can see, and `noreferrer` is a separate promise the implicit
            // behaviour does not make.
            target="_blank"
            rel="noopener noreferrer"
          >
            {part.text}
          </a>
        ),
      )}
    </p>
  )
}
