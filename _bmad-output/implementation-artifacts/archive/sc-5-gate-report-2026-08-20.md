# SC-5 Gate Report — "a deliberate product, not a debug dashboard" (story 15-6)

- **Run date:** 2026-08-20
- **Baseline commit:** `e5aa74f` on `feat/companion-epic-15` (15-1..15-5 all merged; reconciled umbrella)
- **Scope:** 7 acceptance criteria; 3 motion deltas (M1–M3) + 2 structural findings (M4, M5); 2 footer findings (F1, F2); 1 revisit flag; 24 inherited inbox items
- **Evidence dossier:** `spec-15-6-the-sc-5-gate.md` §Code Map — investigated 2026-08-20 at `58372f9`, three parallel audits, both anchors per finding. This report summarizes; the spec carries the full anchors.
- **The walk:** Brad viewed the live companion 2026-08-20 (master @ `999bacd` + Epic 14, Atraxa 100-card deck active, `http://127.0.0.1:8765`) — preliminary ruling recorded in `sc-5-preliminary-ruling-2026-08-20.md`.

## Summary

| AC | Criterion | Audit state |
|---|---|---|
| 1 | The deliberate-product judgement (Brad only) | **Preliminary ruling on record**: positive — "it looks good", from repeated exposure |
| 2 | Anti-patterns (raw JSON, log panes, id tables, error pages, toasts, alert colours) | **All six clean** with evidence; caveats A1 (caution-as-furniture) and A2 (10px legal text) |
| 3 | The four-panel tension | Judged in the walk (composition, typography, restraint) |
| 4 | Arrow-key revisit flag (`EXPERIENCE.md:144`) | Consequence pinned: 206 Tab stops max, 101 after skip link; "tabs work well" per preliminary ruling — formal disposition needed |
| 5 | Reduced-motion inventory | Nothing pulses or loops (0 keyframes/animations, double-guarded); **M1–M3 outside the inventory**, M4 is a subject-less prohibition (keep), M5 is the guard gap that let them through |
| 6 | Footer attribution (NFR-08) | Structural on every surface, byte-gated copy; **F1**: behind a 75% scrim while an agent view is open; F2 mitigated by the 1100px floor |
| 7 | The record | This document, on the pre-Epic-7 skeleton |

## Findings requiring a ruling

- **F1 — agent-view scrim occludes the attribution.** `.app-shell-overlay` is the same box as the shell's padding box; the scrim (75% + 16px blur) covers the footer while a view is open (`AppShell.css:282-286`, `AgentView.css:46-51`, `tokens.css:92`). NFR-08 says every surface. Ruling: "an open modal is not a surface" (record in EXPERIENCE/DESIGN) or a scrim cut-out (new story). jsdom cannot see this; no test covers it.
- **M1 — flip-control chrome fade** (`FlipControl.css:98`) — no inventory row; UX-DR42 demands one. The cleanest delta: behavior is fine (duration-only), the row is the obligation.
- **M2 — suggestion-row live tint** (`SuggestionsView.css:119-121`) — a no-new-row ruling is already recorded twice (`SuggestionsView.css:113-118`, `c6-7-…md:186`); accept the ruling or add the row.
- **M3 — suggestion thumbnail fade** (`SuggestionsView.css:211`) — claims coverage under row 4 "Image fade-in (c4-4)"; defensible if row 4 reads as a class; wants the explicit word.
- **M4 — inventory row 10 has no subject** — it is a prohibition closing validation L7; record as satisfied-by-absence, do not delete. (No ruling needed; disposition recorded here.)
- **M5 — the completeness guard reads `transform` only** (`token-usage.test.ts:2544-2605`) — blind to opacity/height/background-color/box-shadow, the exact class M1–M3 fall into. Remediation lands with the M-rulings.
- **AC 4 — the arrow-key flag** (`EXPERIENCE.md:144`, "[DEFERRED 2026-07-25 — gate H3] … Revisit before public release") — re-accept with the measured corridor (206/101), or adopt roving-tabindex (an ESLint-error-class change + new story).

## Inherited inbox (each needs a named disposition — none may be left unmentioned)

From c4-12's conformance list: UX-DR20 empty-panel contradiction (rendered as "reads as a loading failure"); StatChip without a surface; 10px ALL-CAPS legal text (= caveat A2, ruled "ship as written" 2026-07-30); the `rem` basis; skip link not reaching the footer.
From the C7 retro: manual checklist **L1–L10**, unrun. Carried from C6: **K3** (keyboard-only walk), **K5** (screen-reader pass), **J4** (sub-1100px floor), **J5** (dev proxy), **J6** (`internal-error` first render — fifth home, owed a decision, not a sixth carry).
From the C3 retro: **D1** (agent `validate_deck` vs REST `format-check` parity — "AD-1's promise, owned by nobody").
From `deferred-work.md`: `:4977` (skip-link/footer corridor), `:5150` (NOT TOUCHED), `:6038` (connection pill +1), `:4820`/`:5110` (homed "c7-3 or 15-6"), `:1926-1936` (legal text), `:1599-1601` (footer visible without scrolling — eye-check).

## Standing caveats

- jsdom paints nothing: every "visible" claim in the suite is a mechanism read from CSS source, strictly weaker than a human seeing it. The walk is the only paint-level evidence.
- The 2026-07-25 validation gate was self-reviewed; its four rulings always needed Brad (its own words).
- The preliminary ruling's "bottom footer is visible" was given without specifying the agent-view-open case — F1 is ruled separately below, not inferred.

## Not blockers (recorded, no action gated)

- Caveat A1: `caution` badge appears on ~100% of real decks (rotation advisory) — furniture, not signal, by the component's own comment.
- F2: connection-pill overlap below 1100px — mitigated by the enforced `min-width: 1100px`, reasoning recorded in place.
- Residual NFR-05 drift (~15–20% vs c4-12) — under budget, recorded at the Epic 14 retro F7 addendum.

## Review sheet (Brad)

Walked live 2026-08-20 (preliminary ruling, `sc-5-preliminary-ruling-2026-08-20.md`); rulings below
given interactively the same day and transcribed verbatim from Brad's selections.

- [x] AC 1 — deliberate product: **PASS** ("I have seen it multiple times during the process and it looks good")
- [x] AC 2 — anti-patterns: **PASS** (all six clean by audit; caveats A1/A2 re-accepted below)
- [x] AC 3 — four-panel tension: **PASS** (covered by the AC 1 judgement)
- [x] AC 4 — revisit flag consciously actioned or re-accepted: **DONE** — **RE-ACCEPTED** ("Tabs work well"; 206/101 corridor accepted with the numbers on record)
- [x] AC 5 — motion inventory reconciled: **DONE** — M1 gets its inventory row; M2/M3 existing no-row rulings accepted (row 4 read as a class); M4 recorded satisfied-by-absence; M5 guard extended to the blind class
- [x] AC 6 — footer attribution: **DONE** — **F1 ruled: an open modal is not a surface**; attribution is structural and visible on every surface proper; F2 stands mitigated
- [x] AC 7 — the record: **DONE** (this document)

**Inherited inbox dispositions** (detail in `deferred-work.md` §Dispositions from: the SC-5 gate):
all items **RE-ACCEPTED under the ship-and-adjust ruling** ("we can always adjust after
completion") — anything real surfaces as a bug, not a gate — except: **J6 is CLOSED as DECLINED**
(five homes without a run is the decision; it does not get a sixth), and the 10px legal text /
UX-DR20 / StatChip / `rem` basis / skip-link-corridor items carry their existing recorded rulings
forward unchanged. D1 (validate_deck vs format-check parity) stays in the ledger as unowned — it is
a backend parity question, not a glass question, and this gate does not adopt it.

> **Gate ruling (Brad, 2026-08-20):** SC-5 is accepted — the companion reads as a deliberate
> product, judged over repeated exposure through the build and a live walk today. Accepted with
> rulings: an open agent view is not a surface for NFR-08's purposes; the arrow-key flag is
> re-accepted with the measured corridor (206 stops max, 101 post-skip-link); M1 enters the motion
> inventory, M2/M3 stand on their recorded rulings, and the completeness guard closes the class.
> Deferred rather than resolved: the inherited manual-checklist items (L1–L10, K3, K5, J4, J5),
> re-accepted as ship-and-adjust, and D1, left unowned in the ledger.
> **SC-5 is CLOSED; the 0.5.0 release cut (withheld by 15-4/15-5 ruling) is unblocked.**
