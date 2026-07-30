# Epic C2 Retrospective — The Glass: Foundation, Identity & Honest States

**Date:** 2026-07-30
**Facilitator:** Amelia (Developer)
**Participant:** Brad (Project Lead)
**Epic scope:** The frontend's entire foundation, end to end — the `ui/` scaffold under a full
quality gate from the first commit (c2-1), the backend serving the built SPA as a committed
artifact (c2-2), TypeScript types generated from the backend's own OpenAPI with both drift halves
gated (c2-3), the Voltglass token layer (c2-4), self-hosted Space Grotesk with offline parity
(c2-5), the two-column application shell and the first component (c2-6), the four presentation
primitives (c2-7), ManaPip/ManaCost with a total Scryfall cost parser (c2-8), the shared state
panel and every system-state message (c2-9), and the footer attribution as a condition of public
release (c2-10). Second epic of the 10-epic / 76-story companion feature; nothing released.

---

## Delivery Summary

| Metric | Result |
|---|---|
| Stories | **10 / 10 done** — 2026-07-26 → 2026-07-30 |
| PRs | **10 merged** (#18–#27) into `feat/companion-c2`, tip **`f378c56`**. #27 merged during this retrospective, Greptile 5/5 at round 1 |
| Greptile | Round-1 **5/5** on c2-5, c2-8, c2-10; one round 4/5→5/5 on c2-9; three rounds on c2-4 and c2-6 (3/5 → 4/5 → 5/5). **0 P1s survived to a merge** |
| Frontend suite | 0 → **549** across 24 files, six gates (lint, stylelint, format, typecheck, test, build) |
| Python suite | 1,684 → **1,753** (c2-2 + c2-3), then unchanged across the last seven stories — re-run each time, never assumed |
| Code | 52 commits, **133 files, +36,446 / −55** vs `50dddc3` |
| Design layer | **65 tokens** in one themeable block, 4+ literal-ban families with regex property keys, 21 mana colour classes, ~10 guard suites |
| Review load | ~**130 patches** applied, ~**20 decisions escalated to Brad** — all ruled same day. **0 Critical / 0 Major across ten reviews** |
| Deferred ledger | ~**30 entries opened**, **1 closed inside the epic** (typography literals, closed by c2-5) |
| Production incidents | 0 — `feat/companion-c2` has not touched master; nothing released |

---

## What Went Well

- **The epic found one review theme in its first story and it held for all ten: _a value that
  lints clean and renders as nothing._** c2-4's comma-separated animation lists (the epic's only
  High — `animation: pulse 2s infinite, fade 1s` evaded both enforcement layers because a comma
  followed the token), c2-5's `font: var(--type-numeric-features)` (a legal-looking shorthand that
  resolves to `tabular-nums` and is discarded), c2-8's `.mana-pip-uc` rendering a *transparent*
  circle, c2-9's `--accent-dim` at 2.70:1 slipping through an open `--accent` prefix, c2-10's
  `text-decoration-line` longhand walking past a guard keyed on `text-decoration`. The fix shape
  was identical every time: **ban the family, never enumerate members.** A list of two is a list
  someone walks around.

- **And the doctrine found its own exception, which is stronger than a doctrine.** c2-10's
  `rel="noopener noreferrer"` matched the prose detector exactly. The fix generalised the
  `className` precedent into `TOKEN_LIST_ATTRIBUTE` — keyed on tree position, not on sniffing the
  string — and the story documented it as **the one place the "ban the family" rule inverts**: a
  missing entry here is a visible false positive, while a too-broad entry is the failure that
  hides. That distinction was reasoned, not stumbled into.

- **Same-day three-layer review before the PR is now thrice-confirmed as the round-1-5/5 cause.**
  c2-5, c2-8 and c2-10 cleared Greptile in one round. c2-4 and c2-6 took three. The difference was
  not story difficulty — c2-4 and c2-8 are comparably intricate — it was whether Blind Hunter,
  Edge Case Hunter and Acceptance Auditor ran before the PR was raised.

- **Guards were probed against themselves, and it repeatedly caught real holes.** c2-8 planted
  nine evasions, verified each on disk, ran them and reverted them — **nine caught, none passed**,
  a clean sweep recorded as notable precisely because c2-4, c2-6 and c2-7 each had one get
  through. c2-9 found *two* real holes in its own new guard by probing it. c2-10 had two
  self-inflicted finds, both from running a guard it had just written — including an `outline:
  none` check that reddened against a stylesheet explaining in a comment why the declaration does
  not appear. Stripping comments before reading source is now the third guard in this epic to
  learn the comments-vs-source distinction.

- **Copy became a gated artefact, twice, against two different documents.** c2-9 pinned every
  system-state message byte-for-byte against `EXPERIENCE.md` — and *wrote the two missing rows
  into the artefact* rather than into TypeScript, closing the C1 retro's action item 4 and the
  c1-6 corrupt-database ruling in the form the item asked for. c2-10 then pinned the attribution
  against `DESIGN.md`, a second artefact, with a parser that selects the bullet **by structure**
  (38 bullets, 38 distinct labels) and throws loudly on all four shape changes. Copy can no longer
  drift from its contract without reddening. c4-3, c4-12 and c6-6 inherit that mechanism free.

- **Deviations were flagged, never taken silently — ten stories for ten.** c2-1 shipped
  `mypy --platform win32` instead of the epic's literal `--platform linux`, because on ubuntu CI
  the latter is a **no-op** and the C1 retro's success criterion would still not have held — then
  proved it by breaking `msvcrt.locking()` deliberately and pasting both outcomes. c2-3 repaired
  an AC's command that literally does not work (`cd ..` with no return trip; npm errno -4058,
  measured). c2-5 found AC 5's literal wording would be **red on a correct bundle** (React ships
  `w3.org` namespace strings) and split the rule by what each file type can actually do.

- **Both C1 action items met their success criteria and are promoted.** Forward-dated-comment
  homing: c2-6's **AC 20** repaired four such sentences as acceptance criteria and *judged and
  deliberately kept* a fifth, because `clean.tsx:4` describes the fixture's purpose rather than a
  future state — found in the story's own ACs, not by grep, exactly as written. Open-question
  homing: no C2 story discovered a C1 question mid-implementation, and c2-1 arrived carrying R1's
  `changeOrigin` requirement pre-annotated on the epic.

- **c2-10's Q1–Q5 were all ruled "as proposed" — the ninth story running.** Story authoring is
  now calibrated well enough that the open-questions block functions as confirmation rather than
  as a decision queue.

---

## Challenges & Lessons

### 1. Seven stories split an AC into a machine half and a human half — and c2-10 proved the worry real

c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21, c2-8 AC 21, c2-9 AC 21, c2-10 AC 22. jsdom applies
no stylesheet and has no layout engine, so an entire class of frontend acceptance is **not
machine-closable**. It was never faked — `getComputedStyle` was explicitly declined in four stories
on the grounds that it would pass identically on a correct font, a corrupt font and a 404.

Then c2-10's code review found `display: inline-flex` was suppressing AC 5's release-condition
underline — text decoration does not propagate into flex items — so the underline was **true in
source and false on screen**, and six gates plus jsdom are structurally blind to exactly that. It
was found by a human *reading CSS*, not by any gate.

**Lesson:** the machine/human split is honest and correct, but it accrues a backlog of unlooked-at
pixels, and the failure mode inside that backlog is "renders wrongly but legibly" rather than
anything loud. **→ action item R3**: the checklist runs before the integration PR, and the browser
eye-check is now first on it rather than last.

### 2. `card_not_found` is about to repeat the `internal_error` mistake

Epic C3's Story 3.2 extends the closed reason-token set with `card_not_found`. AD-16 says a new
token and its UI state ship **together**. C1 shipped `internal_error` alone; c2-9 spent an
acceptance criterion repairing it, and had to write copy into `EXPERIENCE.md` retroactively.
`EXPERIENCE.md` has no unknown-card-placeholder copy today. **→ action item R1.** Homing it now is
free; homing it in Epic 4 is another repair AC.

### 3. The deferred ledger grew ~30 and closed 1 (C1: 13 opened, 5 closed)

Much of the growth is the right use of the ledger — "a decision on record, not an omission" (the
CVD colour-carrier trade-off, the `{Y}/{Z}/{S}/{L}/{D}/{HW}` omission, the `// ` split-card
reading). But **c3-9 alone now owes five**: the stalled-DB elapsed-time threshold and switch,
runtime validation of wire values before `StatePanel`'s `state` prop, the un-quoted
`EXPERIENCE.md` copy-tail gate, a first look at the five never-rendered states, and C1's un-run
fresh-install check. One story is absorbing an epic's residue. **→ action item R2.**

### 4. The declared-blind-spot list is long enough to need a map

Cascade-blindness in the numeric-pairing guard *and* in the companion guard it spawned;
`git ls-files`-keyed guards that cannot see untracked stylesheets; block-local parsers; the
`REVIEWED_HOSTS` deliberately-brittle baseline; runtime-composed class lists; `var()` indirection;
UX-DR7's unstacked-curve-bar half; the copy guard's second-person/blameless half. Each is
documented **at its own guard**, which is right. Nobody has the list, and "review owns this half"
now appears in roughly eight places. **→ action item R5.**

### 5. `sprint-status.yaml`'s `last_updated` reached 6,438 characters on one line

The c2-2 review flagged it, the c2-3 review recorded that the very diff documenting it made it
longer. The **YAML-parse half has since self-closed** — a later story quoted the scalar, and
`yaml.safe_load` succeeds on the committed tree at `858cabb` (measured this retro). What remained
was that every diff of the file was unreadable. **Fixed in-retro: date + one clause. → R4.**

---

## Previous-Retro Continuity (Epic C1 — 6 action items)

| # | Item | Status |
|---|---|---|
| 1 | **Forward-dated-comment homing** | ✅ **Met its success criterion.** c2-6 AC 20 repaired four such sentences as ACs and kept a fifth with a recorded judgement; c2-7 AC 20 did the same for its own forward-dated inventory. **Closed and promoted to a standing agreement.** |
| 2 | **Open-question homing** | ✅ **Met its success criterion.** No C2 story discovered a C1 question mid-implementation. **Closed and promoted.** |
| 3 | **Close the `--platform` mypy gate gap in c2-1** | ✅ Closed by c2-1 — and closed *better than specified*: `--platform win32`, not the epic's no-op `--platform linux`, proven by a deliberate break that reds win32 and stays green on linux |
| 4 | **c2-9 ships the `internal_error` panel copy** | ✅ Closed by c2-9, in the form the item asked for — **both** rows written into `EXPERIENCE.md`'s copy table (not into TypeScript), byte-for-byte gated by a test that reads the artefact itself. The c1-6 corrupt-database ruling came with it, with the client-side threshold homed at c3-9 |
| 5 | **Confirm the port env-var name** | ✅ Ruled at the C1 retro: `COMPANION_PORT` |
| 6 | **Annotate c2-1 with `changeOrigin` (R1)** | ✅ Executed in the C1 retro |

**Follow-through: 6 of 6 closed, 2 promoted to standing agreements.** Two consecutive epics at
full follow-through, and the two closed *this* epic were the ones a story had to actively honour
rather than a retro executing them for itself.

---

## Epic C3 Preview — Dependencies, Inheritance, Gaps

**Epic C3: Deck Data & Card Imagery on Tap.** 9 stories. The backend answers everything the glass
will ask about a deck and its art; the first epic to touch an external service, so it owns all
pacing, caching, failure and attribution behaviour in one place. Closes **SC-4**.

**C2 dependencies — all satisfied:**

- c2-3's generator reads `app.openapi()` **in process**, and CI gates both drift halves per-file.
  Every C3 endpoint's schema lands in `types.d.ts` with the drift check covering it, no new
  machinery ✅
- c2-9's `states.ts` — `PANEL_FOR_REASON`, `CLIENT_ONLY_STATES`, `RETRIES_QUIETLY` — are total
  maps, typecheck-gated (a seventh `ErrorReason` fails to compile) and written for c3-9 to import ✅
- c1-6's `DatabaseError → 503 database_unavailable` is registered inside `install_error_handling`,
  so c3-1 onward inherit the guard with no per-route ceremony ✅
- The shell, the token layer, the primitives and ManaCost all exist and are gated, so a C3
  frontend surface has nothing to invent ✅
- c2-10 shipped the Scryfall + Wizards attribution and the external-host protocol in
  `tests/fonts.test.ts` — which C3 needs, being the epic that fetches from Scryfall's CDN ✅

**What C3 inherits and must not lose:**

1. **`card_not_found` needs its `EXPERIENCE.md` copy row before c3-2 merges** (R1) — the
   `internal_error` mistake, one epic later, on a story that is already written.
2. **c3-9 carries five inherited deferrals** plus C1 checklist item 4 (R2) — enumerate them as
   ACs at context time rather than discovering them.
3. **The `--mana-*` unstacked-curve-bar half and the copy guard's second-person half are
   review's**, permanently. c4-8's reviewer must look; the gate will not have looked for them.

**No blocking dependency is unmet. C3 is unblocked** once the integration PR lands.

---

## Rulings made in this retrospective (Brad, 2026-07-30)

**R1 — `card_not_found` is homed on c3-2 *with* its `EXPERIENCE.md` copy row, before the token
ships.** AD-16's own rule, applied prospectively this time. c3-2 does not merge with the token
alone.

**R2 — c3-9 stays one story and enumerates its five inherited deferrals as ACs at context time.**
Splitting it would separate the wiring from the fresh-install loop, which is the one place both
are observable together. Flagged at sprint planning as the epic's heaviest story.

**R3 — the manual-testing checklist runs BEFORE the `feat/companion-c2` → `master` integration
PR.** Same reasoning that paid off in C1, where running it early caught the `COMPANION_PORT`
rename while it was still free. Findings are fixes on the C2 umbrella; nothing lands on master
carrying a known visual defect.

> **R3 AMENDED the same day (Brad, 2026-07-30): the integration PR proceeds with the checklist
> PARTIALLY run.** 9 of 14 items closed, 5 carried. The amendment is deliberate and the reasoning
> is recorded rather than left as an omission:
>
> - **The item R3 existed for is closed.** Its rationale was "catch it while a fix is still free",
>   and the only defect of that kind — `inline-flex` suppressing the release-condition underline —
>   is verified fixed on screen.
> - **Merge ≠ release.** No tag, no CHANGELOG until c8-4, so nothing carried here reaches a user.
>   The entire cost of deferring is that a finding becomes a fix on a post-merge branch instead of
>   on the umbrella — and C3 cuts a fresh umbrella off master regardless, so that difference is
>   near-zero.
> - **The carried items are homed, not dropped** — see *Carried checklist residual* below. The one
>   with a real structural consequence (item 9: if the footer needs scrolling, that is a c2-6 shell
>   defect) costs one glance and is named first.

**R4 — `last_updated` is a date plus one clause from now on.** Executed in this retro:
6,438 → 295 characters, `yaml.safe_load` re-verified.

**Standing rhythm unchanged** (ruled 2026-07-26): story PRs into the umbrella with Greptile per
story, one integration PR to master after the retro with **no Greptile pass** (OSS free-tier
budget), a fresh umbrella cut off master for C3. **Merge ≠ release** — no tag and no CHANGELOG
until c8-4.

---

## Manual-Testing Outcomes — run 2026-07-30, Brad (IN PROGRESS)

Run against the `feat/companion-c2` umbrella at `f378c56`, **before** the integration PR (R3).
Checklist item numbers refer to the table below.

**Incidental finding before the first look:** `uv run artificial-planeswalker companion` refused with
*"companion is already running at http://127.0.0.1:8765"* — a companion from the previous day (PID
42564, launched 29/07 16:28:37, `instance_id a91b0c64…`, `companion.json` written one second later)
was still alive. **Not a defect — c1-8/c1-9 working in their strongest form:** probe-first-lock-second
read the discovery file, probed `/health`, got `200`, matched the `instance_id`, and refused a
*verified*-live instance with exit `0`. Free re-confirmation of C1 manual-test block D, ~17 hours
after the fact. Noted because the stale process would have served a bundle predating c2-9 and c2-10.

| # | Check | Result |
|---|---|---|
| 1 | **Footer underline + hover brightening** | ✅ **The underline RENDERS** on both links. This was the epic's one true-in-source/false-on-screen defect — `inline-flex` suppressing AC 5's release-condition underline, invisible to six source-reading gates and to jsdom — and the `inline-block` fix is now **verified on screen**. Hover brightening not yet exercised in the captured state |
| 3 | **10px ALL-CAPS legal text — readable?** | ✅ **Legible.** Dense, but materially better than the Medium severity assumed. Brad's call whether it wants a nudge; the lever remains a `DESIGN.md` amendment in Epic 8, not a frontend change |
| 5 | **Space Grotesk glyphs** | 🟡 **Half closed.** The face is unmistakably Space Grotesk (flat-topped `A`, single-storey `g`), so `@font-face` resolves and the family applies. **Residual: the same look with the network throttled to offline** — which is the entire reason the font is self-hosted. Also still unchecked: no flash of fallback text on load |
| 10 | **State panel appearance** | ✅ **Correct, and centred correctly.** `margin: 0 auto` centres the panel *within its column* (the stylesheet is explicit that it does not know which column it is in), which is what `DESIGN.md:402` asks for — measured on the render, panel centre ≈427 against a left-column centre of ≈424. The 480px measure, the 1px hairline, the large radius and `--surface-panel` lifting off the canvas are all visibly present. `no-active-deck` correctly renders **no guidance paragraph and no command chip**, and the next-action line carries `--accent` weight and colour |
| — | **Footer hairline at content width** | ✅ Spans the content width, aligned with the header and both columns inside the gutter frame — the reading **ratified** at c2-10's code review, now observed rather than argued |
| — | **Header** | ✅ As designed. The kicker and the `h1` both read *Artificial Planeswalker*; that duplication is **c2-6 Q3's provisional state** — c4-2 replaces the `h1` string with the deck name. Recorded so it is not "fixed" |
| 9 | **Footer visible without scrolling** | ⏳ **Open — needs confirming from the live window rather than a capture.** c2-6's Q2 promises a `100dvh` shell whose `<main>` is the single scroll container, so the footer must be in the viewport with no scroll. If it required scrolling, that is a **shell** defect (c2-6), not a footer one |
| 2, 11, 12, 13 | **Badge tone wash / the five unseen states / ManaPip+ManaCost / the CVD read** | ✅ **PASS on Brad's verdict ("it looks really good"), via a throwaway eye-check harness.** These four could not be checked at all before: c2-7 and c2-8 shipped with no on-screen consumer by their own AC 24, and five of six states are never true today. A temporary `App.tsx` composing every tone, every primitive, the interesting mana costs, and all six state panels was run through **`npm run dev`** — never a build, so `static/` and the `plugin/` mirror were never touched — and reverted afterwards. `tsc -b` clean; nothing committed. **The specific sub-claims Brad's overall verdict covers but did not individually report are listed below rather than claimed here** |
| 4, 6, 7, 8, 14 | — | 🔵 **Not run — CARRIED by the R3 amendment.** See *Carried checklist residual* |

### Carried checklist residual (R3 amendment, 2026-07-30)

Five items plus one half-item, each with a named home so none of them floats. Ordered by
consequence, not by effort. The environment they want is already prepared and verified: a fresh
companion (PID 12976, started 19:19:46) serving `f378c56`'s bundle — `index-DE70muY2.js` /
`index-DmxBiI94.css`, both 200, with the content-hashed WOFF2 beside them.

| # | Check | Home | Why it can wait |
|---|---|---|---|
| 9 | **Footer in the viewport with no scrolling** | **c2-6** if it fails — a shell defect, not a footer one | One glance, no devtools. Named first because it is the only carried item whose failure implicates a shipped mechanism (Q2's `100dvh` single scroll container) rather than an appearance |
| 5 | **Space Grotesk with the network throttled offline**, and no flash of fallback text | **c8-4 / c8-5** (release documentation and plugin parity both make claims about what ships) | The mechanical half is fully closed — real WOFF2 by signature and length, git-binary, content-hashed, served `font/woff2`, relative `@font-face`, no external origin in the bundle. Only the eyes-on-glyphs half remains |
| 4 | **Tab to both footer links — the focus ring** | **c4-11**, which already inherits the focus contract | First render of `--focus-ring*` anywhere; c4-11 needs to look regardless, so checking twice is the only thing avoided |
| 7–8 | **~1100 → ~2560px sweep**: no horizontal scrollbar, right column drops below 1100px | **Epic 8 release-readiness pass**, which already owns "does this look right" work | Every value is pinned as CSS source by `tests/shell.test.ts`; what is unverified is the browser honouring it, which no story depends on |
| 14 | **Devtools box inspection of the 24px hit area** | **Epic 8**, beside the 10px legibility question Brad's Q1 ruling already homes there | Both axes and the `display` mode are asserted in source; the open question is only the measured box and whether it grows the 13px line |

**Standing note:** the four unreported sub-claims inside the item-2/12/13 pass (the wash behind the
text, the unmeasured wash contrast numbers, the CVD read, the 0.8 glyph ratio) keep their existing
homes at **c4-2 / c4-3 / c4-10** and are unaffected by this amendment.

**Sub-claims inside the item-2/12/13 pass that were NOT individually reported**, recorded so the
pass is not read as more than it was. Each is cheap to close in the same window:

- **Item 2's actual failure mode** — the `::before` wash rendering *behind* the text rather than over
  it. "Looks good" almost certainly covers it (the failure is invisible text, which is unmissable),
  but it is the one Medium in the epic with no static proof available, so it deserves an explicit yes.
- **The contrast numbers** the c2-7 review flagged as never measured: `--accent-bright` over a 12%
  `--accent` wash, and positive/negative/caution text over their own washes, on any surface. A look
  is not a measurement. Still homed at c4-2 / c4-10.
- **Item 13, the CVD read** — whether a plain `{W}` and a plain `{G}` circle are distinguishable in
  practice, colour being the sole carrier. A pass here means the design contract stands as written;
  the levers if not are a glyph-slot letter or a `DESIGN.md` amendment.
- **The 0.8 glyph-to-pip ratio** (against the mock's 0.62) — flagged in `deferred-work.md` as the
  single value most likely to want a nudge by eye.

**Also confirmed incidentally by the harness:** two forgotten processes from 2026-07-29 16:28 were
still alive — the companion on 8765 (PID 42564) and a Vite dev server on 5173 (PID 6804), started
three seconds apart. The dev server fell back to 5174 without complaint.

**Still owed, in rough order of value:** Tab to both footer links (item 4 — the first focus-ring render
in the codebase, and c4-11 inherits whatever it shows); the offline-throttled font check (item 5's
residual); the scratch render for Badge's tone wash (item 2 — the one remaining Medium with no static
proof available, and it fails as invisible text); ManaPip/ManaCost by eye (item 12); the width sweep
(items 7–8); the five unseen states (item 11); the CVD read (item 13); the devtools box inspection
(item 14).

---

## Manual-Testing Checklist — Epic C2

Everything below is a visual or layout claim that jsdom cannot decide. The source-read half of each
is asserted by a guard; what is listed is only what the CSS *does on screen*. **None of it is
claimed anywhere as verified.** Ordered by risk, not by story.

| # | Check | Why a unit test can't close it |
|---|---|---|
| 1 | **The footer links' persistent underline, and the rest→hover brightening.** Is the underline *there*, and visible at 10px against `--text-secondary`? | The c2-10 review found `inline-flex` plausibly suppressed it entirely — decoration doesn't propagate into flex items. `inline-block` is the fix and **the browser is the only proof it works**. Failure mode: true in source, false on screen |
| 2 | **Badge's tone wash: does it render BEHIND the text?** `::before` at `inset: 0`, `z-index: -1`, `isolation: isolate` | No static proof exists for stacking. Failure is a **solid blank pill with invisible text**, which reads as a content bug rather than a CSS one. Needs a scratch render — nothing imports Badge yet |
| 3 | **The 10px ALL-CAPS legal sentence — is it readable?** | Three sentences of legally load-bearing text at `400 10px/1.3`, uppercased by the derived guard from `DESIGN.md`'s own `textTransform:` key. Ruled ship-as-specified (Q1); **if it reads badly the correction is a `DESIGN.md` amendment in Epic 8**, made with the page in hand |
| 4 | **Tab to both footer links — the focus ring.** | **First focusable elements in the codebase.** `--focus-ring` / `--focus-ring-width` / `--focus-ring-offset` shipped in c2-1 with nothing to point at; this is their first ever render. c4-11 inherits whatever this shows |
| 5 | **Space Grotesk glyphs with the network throttled to offline**, plus no flash of fallback text on load | jsdom loads no fonts and applies no `@font-face`; a `getComputedStyle` assertion would pass identically on a correct font, a corrupt font and a 404 |
| 6 | **Open the real launch URL and confirm the served SPA paints** (`artificial-planeswalker companion`) | c2-2 AC 17's render half. Every machine-checkable probe is green from a Node-less worktree; only a human closes SC-4's render half |
| 7 | **Composition at 1720px against the reference** — header, fluid left column, exactly-452px right column, footer, panels floating with visible canvas between them | jsdom resolves no grid tracks and evaluates no media queries; every geometry assertion in c2-6 reads CSS source |
| 8 | **Sweep ~1100px → ~2560px**: no horizontal scrollbar at any width, and below 1100px the right column **drops beneath** the left rather than compressing | Same — the breakpoint is pinned as source text, never evaluated |
| 9 | **On long content**: footer stays visible without scrolling, and the scrollbar sits at the **content region's** edge, not the window's | The intended app-shell appearance and the accepted consequence of c2-6's Q2 |
| 10 | **The state panel's appearance** — centring, the 480px measure, the hairline border, the large radius, the command chip's recessed `--surface-well` material and mono family, the accent colour and weight of the next-action line | The one panel with a real screen (c2-9 Q1 wired it), and still no `getComputedStyle` assertion anywhere — one would report defaults back over a stylesheet that was never linked |
| 11 | **The five states nobody has seen.** Temporarily flip the `state` prop in `App.tsx`: `database-not-initialized`, `database-updating`, `database-updating-stalled`, `disconnected`, `internal-error` — especially the **command chip** (only three of six show it) and the **two-paragraph** guidance/action stack (`no-active-deck` has no guidance, so it never exercises it) | They render correctly in the suite and have never been looked at. c3-9 wires them for real |
| 12 | **ManaPip / ManaCost by eye** — the `{W/U}` hard-stop gradient reading as a **split** rather than a blur; `{1000000}` growing into a **pill** instead of clipping; the **0.8 glyph-to-pip ratio** (tighter than the mock's 0.62 — *the value most likely to want a nudge*); fifteen B.F.M. pips **wrapping** inside the 452px column | Needs a scratch render — nothing imports them. All fail *legibly but wrongly*. Check `{1000000}` and `{W/U}` first |
| 13 | **CVD check: do a plain `{W}` and a plain `{G}` circle read as distinguishable?** | Colour is a pip's **sole** carrier — no letter, no pattern — so a sighted colour-vision-deficient user cannot read any cost. `DESIGN.md`'s ruled shape compels it and UX-DR7 closes the obvious escape. If they read as indistinguishable in practice, the levers are a glyph-slot letter or a `DESIGN.md` amendment — **Brad's call, against a real screen** |
| 14 | **The 24px hit box as laid out** (devtools box inspection, not by eye) | `min-height`/`min-width: 24px` on an `inline-block` inside a 13px line box will *grow that line*, so the two link runs may sit on a visibly taller line than the text around them, extending below the baseline rather than centring |

**Also worth a look while you're in there** (carried, not C2's): the border/surface separation — the
footer background is the same token as the page canvas, so the **hairline is the only visible
separation**, spanning the content width inside the gutter frame (ratified 2026-07-30, so a
full-bleed rule would now be a new decision).

**Not on this list, deliberately:** C1 checklist items 4 (fresh install) and 5 (live
`COMPANION_PORT`). Both are homed — c3-9 and c8-4 respectively — and neither has a shipped surface
to observe yet.

---

## Action Items

| # | Action | Owner | Success criteria |
|---|---|---|---|
| 1 | **R1 — home `card_not_found` on c3-2 with its `EXPERIENCE.md` copy row**, before the token ships. AD-16 requires token + UI state together; C1 shipped `internal_error` alone and c2-9 paid for it. | Brad (c3-2) | c3-2's record carries a verbatim `EXPERIENCE.md` row for `card_not_found`, and the token + copy land in one commit |
| 2 | **R2 — c3-9 stays one story and enumerates its five inherited deferrals as ACs** at context time; flag it at sprint planning as the epic's heaviest. | Brad (c3-9) | c3-9's ACs name all five by their `deferred-work.md` entry, and none is discovered mid-implementation |
| 3 | **R3 — run the 14-item checklist before the integration PR.** Item 1 is the only proof the `inline-block` fix works; item 2 fails as invisible text. | Brad | The checklist is run; findings are fixes on the C2 umbrella, not on master |
| 4 | **R4 — `last_updated` is a date plus one clause.** The YAML-parse half self-closed; the readability half did not. | Amelia — **done in this retro** | Value under ~300 chars and `yaml.safe_load` still parses (verified: 295) |
| 5 | **One "what the gates cannot see" map in `ui/README.md`** — collect the ~8 declared residues into one section with a link to the guard that owns each, so a reviewer inherits a map instead of re-deriving it. | Brad (c3-1 or the first C3 frontend story) | One README section enumerates every declared blind spot and its owning guard |
| 6 | **Keep the same-day three-layer review before every PR** — thrice-confirmed as the round-1-5/5 cause. Standing, not a one-off. | Brad (standing) | Every C3 story runs `bmad-code-review` before its PR is raised |

### Team agreements (standing, updated)

- **Claims require verification** — stands; every story pasted actual gate output, and c2-8 went
  further by verifying planted probes *on disk* before running them.
- **Task 0 story-start verification** — stands, 10 for 10.
- **Construction-site enumeration** — stands.
- **Gate-output homing** — stands; every AC split this epic went into `deferred-work.md` with a
  named consumer story, not into prose.
- **Error-contract enumeration** — stands; c1-6's pre-registered handler meant C2 added no error
  ceremony at all.
- **Non-vacuity pairing** — stands, and hardened: c2-3, c2-8 and c2-10 each proved a guard fires
  *and* stays silent from the same invocation, and c2-8's non-vacuity anchor caught an allowlist
  entry renamed to an untracked path.
- **Ban the family, never enumerate members** — *new, promoted this retro.* When a gate must
  refuse a class of value, key it on the family (a property-name regex, a token-name prefix, a
  structural position), never on a list of known spellings. The one documented inversion is
  `TOKEN_LIST_ATTRIBUTE` (c2-10), where a missing entry is a loud false positive and a too-broad
  entry is the failure that hides — so exclusions are enumerated and *one-sided*, while
  prohibitions are families.
- **Probe your own guard before review does** — *new, promoted this retro.* A guard written and
  not run against a planted violation is a guard with unknown teeth. c2-8's nine-for-nine sweep,
  c2-9's two self-found holes and c2-10's two self-inflicted finds all came from this.
- **Forward-dated-comment homing** — *promoted this retro.*
- **Open-question homing** — *promoted this retro.*

---

## Readiness Assessment

- **Testing & quality:** ✅ 549 frontend / 1,753 Python, six frontend gates plus the Python gates
  green at every story boundary; bundle and `plugin/` mirror measured (not assumed) at every
  boundary. ⚠️ **Zero visual verification** beyond one wired panel — that is what the checklist is.
  One known pre-existing flake (`test_list_decks_with_strategy_field`) lives in `src/data` and is
  ledgered.
- **Deployment:** ⏳ **all ten story PRs are merged** (#27 landed during this retrospective at
  `f378c56`); `feat/companion-c2` is complete and unreleased. Next is the `feat/companion-c2` →
  `master` integration PR (no Greptile pass, per the standing rule) — **after** the checklist, per
  R3. Not a release: no tag, no CHANGELOG until c8-4.
- **Stakeholder acceptance:** ⏳ **in progress** — the 14-item checklist is running before the
  integration PR (R3). 4 items closed or half-closed, 1 open pending a live-window look, 9 not yet
  run. See *Manual-Testing Outcomes* above. **Headline: the `inline-block` underline fix is verified
  on screen**, which was the single riskiest unverified claim in the epic.
- **Technical health:** ✅ strong. No guard suite needed a rewrite; the token layer absorbed a
  65th member deliberately; ~30 deferrals opened but every one written down with a named consumer.
  The honest caveat is that the *review* surface is now large — ~10 guard suites with ~8 declared
  blind spots — which R5 addresses.
- **Unresolved blockers for C3:** none. R1 and R2 close the two inheritance gaps that existed.

---

## Significant Discovery Alert

**None requiring a plan update.** Every architectural decision C2 tested held: AD-12's
generate-types-from-the-backend's-own-schema (c2-3 closed it, both drift halves gated), AD-13's
Node-is-dev-only boundary (the committed bundle carries none of the toolchain), AD-16's closed
token set (c2-9's panel switch has a closed set to switch on, and `states.ts` is compile-gated),
and UX-DR2/DR6/DR7/DR33/DR38/DR47, each of which now has a guard rather than an intention.

Three recorded deltas, all additive: `--font-mono` is token 65 by Brad's c2-9 ruling (one consumer,
one job — the command chip; a second reach for it is a UX-DR2 conversation); the state panel is
**not** a `Panel` (c2-9 Q6 — `DESIGN.md` declares a separate `components.state-panel.*` block, and
rendering one through the other would have meant threading a second title role through a
primitive, which is how a primitive stops being one); and the footer hairline spans the **content
width** rather than full-bleed (ratified at c2-10's review). `DESIGN.md:328`'s `{spacing.6}` and
`DESIGN.md:342`'s "full width" are the two artefact lines still lagging the implementation — both
homed on **c8-3**, which already owns folding implementation-surfaced corrections back into the
planning artefacts.

---

## Commitments

- Action items: **6** (1 executed in-retro) + 10 standing team agreements (2 new, 2 promoted from C1)
- Rulings: **4** (R1 `card_not_found` homing, R2 c3-9 stays whole, R3 checklist before the
  integration PR, R4 `last_updated` discipline)
- Manual-testing checklist: **14 items**, run before the integration PR
- Epic C1 continuity: **6 of 6 closed, 2 promoted**
- Critical path to C3: ~~merge #27~~ **done, `f378c56`** → run the 14-item checklist → integration
  PR `feat/companion-c2` → `master` → fresh umbrella off master → c3-1 (with **c3-2 carrying R1**
  and **c3-9 carrying R2**)
