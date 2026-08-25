---
title: 'Story 17.1: Connection pill status detail'
type: 'feature'
created: '2026-08-21'
status: 'done'
baseline_revision: 'b3ed54e3a4a80228b5db75ab37b75927551691b5'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      Tooltip anchoring geometry is a constant offset that assumes a one-line pill and the current
      --type-body size; a long deck name wrapping the pill, a type-scale change, or browser zoom
      breaks the flush/overlap anchoring (and with it the WCAG 1.4.13 pointer-travel guarantee).
    evidence: |-
      ConnectionPill.css anchors the tooltip at
      calc(--space-gutter + --space-6 + --space-6 - --space-1), derived in a comment from an
      assumed ~31px pill box. jsdom resolves no layout, so no test can guard it; repo convention
      assigns exact geometry to the eye-check, which covers default width/normal names only.
    location: >-
      ui/src/containers/ConnectionPill/ConnectionPill.css
    severity: low
---

<intent-contract>

## Intent

**Problem:** With more than one thing running, Brad cannot tell which backend instance a tab is talking to — the connection pill names the state but not the identity, so a stale tab and a live one look the same (FR-15, AD-4).

**Approach:** Surface port + instance id in a tooltip on the existing pill: a `readInstanceId()` health read through the one network door, stored on the system slice, refreshed on every transition to `live`, revealed on hover **or keyboard focus** and tied to the pill via `aria-describedby` (UX-DR29, UX-DR39, UX-DR44).

## Boundaries & Constraints

**Always:**
- Network access only in `ui/src/api/client.ts` (posture test pins the door list to exactly that file).
- One writer per store: the new `applyInstanceId` verb lives in `systemState.ts`; the trigger module holds no `setState` and names no store.
- The pill stays static: no `animation`, no `transition` anywhere in `ConnectionPill.css`; reveal is an instant visibility flip.
- The tooltip element sits OUTSIDE the `<button>` — inside it, its text would join the accessible name and break the pinned accname `Connected—Sultai Midrange`.
- The dot never carries state alone; the live region announces status transitions only — an identity change must NOT announce.
- Port comes from `window.location` (fallback `443`/`80` by protocol when empty) — never a configured number.
- Instance id shown in full, case preserved: it is data, so it may not take `--type-micro` (uppercase transform) — c4-3/c4-10's lesson.
- New copy is authored in `ConnectionPill/copy.ts`, written into EXPERIENCE.md's connection-pill row in the same commit, and gated by `connection-pill-copy.test.ts` (c5-7 precedent).
- Tokens only in CSS; this file is not in `CALM_STYLESHEETS` but spends no `--accent`.

**Block If:** `GET /health` shape on the wire disagrees with `HealthResponse` in `ui/src/api/schema.ts`; or the keyboard-floor / accname pins cannot be kept while adding the tooltip.

**Never:** No backend changes (health endpoint ships since c1). No client count in the tooltip. No new store. No `title` attribute as the only path (hover-only ban). No polling of `/health` — it is read on transitions to `live` only. No session-history work (17.2) or profiling (17.3).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First connect | status → `live`, health returns `{status:"ok", instance_id:"abc"}` | store `instanceId: "abc"`; tooltip = port + id | No error expected |
| Reconnect to new process | second `live` after failures, health returns new id | tooltip shows the NEW id (AC-4) | No error expected |
| Cold open, not yet live | `instanceId: null` | tooltip = port + "not yet confirmed" copy | No error expected |
| Health read fails / malformed 200 / non-200 | `readInstanceId()` → `null` | store left unchanged (last-confirmed semantics) | Swallowed; never rejects |
| Out-of-order responses | two refreshes resolve reversed | latest-issued refresh wins (generation guard) | No error expected |
| Escape while revealed | keydown Escape on focused pill | tooltip suppressed until blur/mouse-leave (WCAG 1.4.13 dismissable) | No error expected |

</intent-contract>

## Code Map

- `ui/src/containers/ConnectionPill/ConnectionPill.tsx` -- the pill; its own header ("NO TOOLTIP, NO GET /health" block, lines 40–47) reserves exactly this story; real `<button>` already shipped for `aria-describedby`; announcement `<p>` must stay a live region that identity changes never touch.
- `ui/src/containers/ConnectionPill/copy.ts` -- authored copy module, import-free (nodenext test imports it directly); add `tooltipText(port, instanceId|null)`.
- `ui/src/containers/ConnectionPill/ConnectionPill.css` -- pill is `position: fixed` bottom-left (`--space-gutter` / `--space-gutter + --space-6`); file-wide motion ban; tooltip block goes here.
- `ui/src/api/client.ts` -- the ONE network door; mirror `readSessionTicket` (line 1011) via the internal `request()` helper; add `HEALTH_PATH = '/health'` and `readInstanceId(): Promise<string | null>`.
- `ui/src/api/schema.ts:47` -- `HealthResponse = { status: 'ok'; instance_id: string }` already generated and pinned.
- `ui/src/state/systemState.ts` -- system slice + its one writer; add `instanceId: string | null` (initial `null`), `applyInstanceId`, selector hook `useInstanceId` (the `useConnection` pattern, line 131).
- `ui/src/state/identity.ts` (new) -- `refreshInstanceId(read = readInstanceId)` with a monotonic generation guard; calls `applyInstanceId` on success only; holds no `setState`, names no store.
- `ui/src/state/connection.ts:109` -- `onStatus: applyConnection` becomes a wrapper that also fires `void refreshInstanceId()` when the status is `'live'` (covers first connect AND every reconnect — the socket emits on change only).
- `ui/src/containers/ConnectionPill/ConnectionPill.test.tsx` -- pins accname/announcement; extend, don't break.
- `ui/tests/connection-pill-copy.test.ts` -- copy↔EXPERIENCE.md gate; extend for the tooltip strings.
- `ui/tests/keyboard-floor.test.ts:319,334,504` -- pill pinned as focusable, known-surface ring, `DECLARES_MIN`; keep all three true.
- `ui/src/containers/AgentViewsNav/AgentViewsNav.tsx:159-176` -- the shipped describedby precedent (visually-hidden description); 17.1 differs: the reveal must be VISUAL on focus too.
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md:98` and `DESIGN.md:617` -- the pill's rows; amend with tooltip copy/material (amendment-with-story precedent).

## Tasks & Acceptance

**Execution:**
- `ui/src/api/client.ts` -- add `HEALTH_PATH` + `readInstanceId()` returning `instance_id` on a valid 200, else `null`; never rejects -- health is unauthenticated, so no token plumbing.
- `ui/src/state/systemState.ts` -- add `instanceId` field, `applyInstanceId` verb, `useInstanceId` selector hook -- keeps the one-writer rule and the pill's fine-grained re-render.
- `ui/src/state/identity.ts` -- new refresh verb with injected reader + generation guard; failure leaves the store untouched -- last-confirmed identity semantics.
- `ui/src/state/connection.ts` -- trigger refresh on every transition to `'live'` -- AC-4's reconnect visibility with one trigger point.
- `ui/src/containers/ConnectionPill/copy.ts` -- author `tooltipText` (em-dash join, full id; `null` → "not yet confirmed" phrasing) -- one builder so DOM text and description agree.
- `ui/src/containers/ConnectionPill/ConnectionPill.tsx` -- render tooltip as a sibling AFTER the button (announcement `<p>` stays last): `role="tooltip"`, stable id, `aria-describedby` on the button always wired; Escape-suppression state cleared on blur/mouse-leave -- visual reveal is CSS's job.
- `ui/src/containers/ConnectionPill/ConnectionPill.css` -- tooltip fixed, anchored flush above the pill from existing spacing tokens (flush so the pointer can travel onto it — 1.4.13 hoverable); visible on pill `:hover`/`:focus-visible` and tooltip `:hover`, gated by the suppression class; `--surface-overlay` / `--border-hairline` / `--radius-sm` / `--type-body` `--text-secondary`; no motion; exact clearance is the eye-check's.
- `ui/src/containers/ConnectionPill/ConnectionPill.test.tsx` + `ui/src/state` tests + `ui/src/api/client.test.ts` -- unit-test the I/O matrix rows, describedby resolves to the tooltip text, accname pin unchanged, identity change does not announce.
- `ui/tests/connection-pill-copy.test.ts` + `EXPERIENCE.md` + `DESIGN.md` -- write tooltip strings into the row, extend the gate, amend the DESIGN bullet (story 17.1) -- the copy-ships-with-the-artefact precedent.

**Acceptance Criteria:**
- Given the pill, when hovered or keyboard-focused, then the tooltip shows port and instance id, and `aria-describedby` on the button resolves to that element (jsdom asserts wiring + content; visual reveal is CSS + eye-check).
- Given a backend restart with a new instance id, when the tab reconnects, then the tooltip reflects the new id without a reload.
- Given the pill at rest, when observed, then nothing animates and the pill's text/accname/announcement behavior is byte-identical to before this story.
- Given the Tab order, when the pill is reached, then it is still the last stop before the footer with the known-surface ring and ≥24×24px hit area (existing keyboard-floor suite stays green).

## Design Notes

- Trigger on `onStatus('live')` rather than `onReconnected`: the first connect needs the id too, and the socket's emit-on-change makes `live` fire exactly once per (re)connection.
- Identity is retained through `reconnecting`/`down` — it truthfully names the last-confirmed backend, unlike the deck name (which stays withheld in `down`; do not touch that asymmetry).
- The nav-pill `title`+hidden-description shape is NOT enough here: 17.1's AC requires visual reveal on keyboard focus, so the description element itself is the visible tooltip.

## Verification

**Commands:**
- `cd ui && npm test` -- expected: full suite green (includes posture, store-writes, keyboard-floor, token-usage, copy gates).
- `cd ui && npx tsc -b && npm run lint` -- expected: clean.
- `uv run python -m scripts.vitest_probe_harness --control` then planted-RED run per project-context Testing Rules -- expected: a pasteable proof line for one new guard (suggested plant: break the describedby wiring).

**Manual checks (if no CLI):**
- Eye-check: tooltip clearance/flush anchoring above the pill at default width; reveal on hover and on Tab focus; Escape hides it.

## Spec Change Log

## Review Triage Log

### 2026-08-21 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 0, medium 1, low 9)
- defer: 1: (high 0, medium 0, low 1)
- reject: 8
- addressed_findings:
  - `[medium]` `[patch]` Escape could not dismiss a hover-only reveal (keydown sat on the button; with focus elsewhere the key never reached it) and a passing pointer re-revealed a focus-dismissed tooltip — moved Escape to a document-level keydown listener (registered in keyboard-floor's listener census), made clearing per-channel (blur always; mouse-leave only when unfocused), rewrote the Escape test suite realistically.
  - `[low]` `[patch]` `instanceIdOf` passed a padded id through raw, defeating `applyInstanceId`'s equality guard — now returns the trimmed id, with test.
  - `[low]` `[patch]` `HEALTH_PATH` was only compared to itself (a wrong route would ship as a silent, permanent "not yet confirmed") — pinned to the literal `'/health'`.
  - `[low]` `[patch]` The "no auth" test asserted only path shape — now asserts the fetch carries no credential header (header names exactly `['accept']`).
  - `[low]` `[patch]` `applyInstanceId`'s same-value guard was unobserved — added subscriber notification-count tests.
  - `[low]` `[patch]` "describedby is ALWAYS wired" was untested while suppressed — asserted after Escape.
  - `[low]` `[patch]` `pagePort()`'s zero-argument production arm was never executed — added a smoke test against jsdom's own location.
  - `[low]` `[patch]` Stray double blank line in ConnectionPill.tsx removed.
  - `[low]` `[patch]` Tooltip could overflow a narrow viewport — max-width clamped with `min(..., 100vw - 2*gutter)`.
  - `[low]` `[patch]` Artefact wording: DESIGN.md now records the deliberate few-pixel-overlap ruling ("flush" contradicted the CSS); EXPERIENCE.md's row now carries the Esc-dismissal contract; the copy gate was extended for both.

Rejected as noise: file://-protocol port fallback (unsupported deployment); stopPropagation on Escape (no coexisting Escape surface today — commented instead); schema/backend "missing from diff" (pre-existing, verified present); applyConnection/refresh ordering race (covered at the identity seam); port-from-/health literal reading (the wire carries no port field — window.location is the only implementable reading, argued in code and artefacts); composed socket-to-glass reconnect test (the repo's seam division assigns composition to App.test.tsx); jsdom-cannot-see-the-reveal (platform limit; the eye-check owns it — residual risk below); AC-5 focus-ring/hit-area re-verification (c5-7's keyboard-floor pins remain green).

## Auto Run Result

**Summary:** Story 17.1 shipped — the connection pill now reveals the page's port and the backend's last-confirmed `GET /health` instance id in a tooltip on hover or keyboard focus, tied via `aria-describedby`, refreshed on every transition to `live` so a reconnect to a different process is visible. Escape dismisses (document-level, WCAG 1.4.13); identity changes never announce; nothing animates.

**Files changed:**
- `ui/src/api/client.ts` / `client.test.ts` — `HEALTH_PATH` + `readInstanceId()` (trimmed id, every failure folds to null) through the one network door; route/auth/shape tests.
- `ui/src/state/systemState.ts` — `instanceId` slice field, change-detected `applyInstanceId` verb, `useInstanceId` selector.
- `ui/src/state/identity.ts` / `identity.test.ts` — refresh verb with generation guard; last-confirmed and latest-issued-wins semantics tested.
- `ui/src/state/connection.ts` / `connection.test.ts` (new) — `onStatus` wrapper fires the refresh on every transition to `'live'`.
- `ui/src/containers/ConnectionPill/ConnectionPill.tsx` / `.css` / `.test.tsx` / `copy.ts` / `port.ts` (new) — tooltip element, reveal CSS, Escape suppression, authored copy, port resolver.
- `ui/src/state/deck.test.ts`, `ui/tests/shell.test.ts`, `ui/tests/keyboard-floor.test.ts`, `ui/tests/connection-pill-copy.test.ts` — fixture/census/gate extensions.
- `_bmad-output/planning-artifacts/ux-designs/.../EXPERIENCE.md`, `DESIGN.md` — pill row/bullet amended with tooltip copy, material, and dismissal rulings (story 17.1).

**Review findings breakdown:** 10 patches applied (1 medium, 9 low), 1 deferred (low — anchoring geometry under non-default conditions), 8 rejected. No intent gaps, no spec repairs.

**Follow-up review recommendation:** true — patched counts: high 0, medium 1, low 9; score 3×1 + 1×9 = 12 ≥ 5.

**Verification:** `cd ui && npm test` → 85 files / 2499 tests green (posture, store-writes, keyboard-floor, token-usage, copy gates included); `npx tsc -b` clean; `npm run lint` (eslint + stylelint) clean — all re-run by the coordinator after patches. Probe proof (implementation round): planted RED caught by name — `RED |dom| src/containers/ConnectionPill/ConnectionPill.test.tsx > … > wires aria-describedby to the tooltip, and the description IS its text` at `--expect-total 2490`; control green before and after. Patch round re-verified at 2499.

**Residual risks:** the reveal itself (hover/focus visibility, anchoring clearance, hover hold-open) is CSS jsdom cannot observe — the spec's manual eye-check is owed in a real browser; tooltip geometry under non-default conditions is the one deferred item.
