---
epic: c2
story: c2-10
work_branch: feat/companion-c2
story_branch: feat/companion-c2-10-footer-attribution
depends_on: none — c2-9 (PR #26) is merged into the umbrella at efa2435
baseline_commit: 8c864f8
---

# Story C2.10: Footer attribution on every surface

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the maintainer publishing this app,
I want the Scryfall and Wizards Fan Content notices visible on every screen,
so that the public release meets its licensing obligations rather than relying on a page nobody
visits.

**What this story really is.** It is the last story of Epic C2, and it is the only one in the epic
whose deliverable is a **condition of public release** rather than a design choice — `DESIGN.md:375`
says exactly that, in bold, and `NFR-08` and `UX-DR32` say it twice more. Every other C2 story could
ship slightly wrong and be corrected in Epic 4. This one shipping wrong is a licensing defect.

Three things make it different from the nine before it:

1. **The shell has been holding the slot open for four stories.** `AppShell.css:174-185` names this
   story in a comment — "c2-10 fills it with the Scryfall and Fan Content notices" — and
   `AppShell.tsx:140` renders a placeholder that says the same thing. The element, the landmark and
   the layout mechanism already exist and are already gated. **This story fills a slot; it does not
   build one.** Restructuring the shell here would be the wrong repair.
2. **It is the first story to put an external host in the bundle.** The app is offline-first
   (`NFR-06`), and `tests/fonts.test.ts` enforces that with a four-rule scan whose fourth rule is
   *"the set of external hosts present equals a reviewed baseline."* Today that baseline is
   `www.w3.org` and `react.dev`. Two hosts join it here, in the open, with reasons — landmine 4.
3. **The copy is verbatim from an artefact, and the artefact is `DESIGN.md`, not `EXPERIENCE.md`.**
   c2-9 built the mechanism for exactly this (`tests/copy.test.ts` reads `EXPERIENCE.md` itself and
   asserts byte-for-byte), and `ui/README.md:733` names *"c2-10's attribution"* as the first story to
   inherit it. But `EXPERIENCE.md`'s Voice-and-Tone table has **no footer row** — its footer entry
   (`EXPERIENCE.md:101`) is behavioural, not the words. The words are in `DESIGN.md:375`, inside
   straight double quotes. Landmine 5.

**Fourteen things were measured on this machine at `8c864f8` — do not rediscover them.** They are
listed below in the order they will bite.

### The shell already decided most of this

1. **`.app-shell-footer` already sets type and colour, and one of them is WRONG for this story.**
   `AppShell.css:179-185` is:

   ```css
   .app-shell-footer {
     flex-shrink: 0;
     font: var(--type-micro);
     letter-spacing: var(--tracking-micro);
     color: var(--text-tertiary);
     text-transform: uppercase;
   }
   ```

   `--text-tertiary` is 5.9:1 on `--surface-base`. **AC 3 requires `--text-secondary` at 9.3:1**, and
   the reason is written into the AC itself: this text is legally load-bearing and gets a passing
   tier, not a muted one. The line has to change. **Where** it changes is Q2 — two single-class
   selectors setting `color` is a source-order race, and this repo has already been bitten once by a
   cascade it did not model (c2-6's last-wins finding).

2. **`--type-micro` is `400 10px/1.3` and DESIGN.md declares the micro role UPPERCASE.**
   `tokens.css:147`, `tokens.css:151` (`--tracking-micro: 0.08em`), and the companion guard in
   `tests/token-usage.test.ts:874-960` **derives** the uppercase requirement from `DESIGN.md`'s own
   `textTransform:` key — so any rule applying `var(--type-micro)` without
   `text-transform: uppercase` in the **same block** is a test failure, and the same for the tracking
   sibling. The consequence is not cosmetic: **the three-sentence legal notice renders as 10px
   all-caps.** That is what `DESIGN.md:324` and `:375` specify together. It is Q1, because it is a
   real legibility trade-off on the one string in the app that has to be readable, and the
   alternative costs a `DESIGN.md` amendment rather than a frontend decision.

3. **The footer is *literally* always in the window already, and no work here is required to keep it
   there.** `AppShell.css:51-57` (`height: 100dvh`), `:65` and `:179` (`flex-shrink: 0` on header and
   footer), and `:137-145` (`min-height: 0; overflow-y: auto` on the single scroller) are the
   mechanism, pinned by `tests/shell.test.ts`. **AC 1 is therefore mostly already true** — what this
   story owes it is the assertion at the surface level plus not breaking the mechanism. A second
   height mechanism, a `position: sticky`, or a `100vh` anywhere is a regression against three
   existing guards, not a belt-and-braces improvement.

4. **`<footer>` and the `contentinfo` landmark already exist** (`AppShell.tsx:139`), and
   `AppShell.test.tsx` already asserts exactly one of each landmark. **AC 5 costs nothing** — do not
   add a second `<footer>`, and do not put `role="contentinfo"` on the component this story adds. A
   nested `contentinfo` inside the shell's own would be two landmarks where the shell's suite asserts
   one.

### The gates that will fire, and what they want

5. **The copy's source artefact is `DESIGN.md:375`, and it is prose, not frontmatter.** The exact
   string, inside one pair of straight double quotes on that line:

   > Card data and imagery courtesy of Scryfall. Unofficial Fan Content permitted under the Wizards
   > of the Coast Fan Content Policy. Not approved/endorsed by Wizards.

   The verbatim gate must **parse the artefact, select by structure, and fail loudly on anything
   other than exactly one quoted run on that bullet** — c2-9's review found that a parser which
   silently tolerates a duplicate row is a parser that stops checking. Note the character detail that
   will bite a hand-typed copy: `approved/endorsed` has **no spaces around the slash**, and there is
   no Oxford anything to normalise. Byte-for-byte means byte-for-byte.

6. **The string has to be broken around two anchors, and the c2-9 mechanism for that already
   exists.** "Scryfall" and "Wizards of the Coast Fan Content Policy" are links; the rest is text. Do
   **not** author three separate strings — that is two spellings of one value, which is what the
   verbatim gate exists to prevent. Use c2-9's shape: a **list of parts in source order**, each
   tagged link-or-text, with a **concatenation invariant** asserting that re-joining the parts
   reproduces `DESIGN.md`'s sentence exactly (`copy.ts:164-171` and `copy.test.ts` are the worked
   example). Nothing is written that `DESIGN.md` did not write; the footer merely knows which runs
   are links.

7. **`COPY_MODULES` in `tests/copy-rules.test.ts:103-121` must gain this story's copy module.** This
   is *decide-once ruling #1 of story c2-9*, and c2-10's attribution is the first of the four stories
   it names. Two mechanical requirements, both asserted by the non-vacuity test at
   `copy-rules.test.ts:324-351`: the reason string must be **longer than 40 characters**, and the
   extractor must find **more than 3 strings** in the module. A copy module holding one sentence in
   one string fails the second — which the list-of-parts shape (landmine 6) satisfies naturally.
   Without the entry, the file half fails the moment the sentence is committed anywhere.

8. **`PRIMITIVES` in `tests/shell.test.ts:983-1041` is git-derived and will fail on sight.** The
   coverage check at `:1058-1079` runs `git ls-files 'src/components/*.ts' 'src/components/*.tsx'` —
   git's `*` **crosses `/`**, so it sees nested component files — and asserts set equality against the
   list. Every new module under `src/components/` needs an entry with an **exhaustive import list**,
   and the non-vacuity pin `expect(PRIMITIVES).toHaveLength(12)` at `:1052` must move to the new
   count. Each listed file must also be **over 200 bytes**. The same suite then asserts no hook, no
   `on*` prop, no `ref` — which the footer satisfies trivially, being static.

9. **`tests/fonts.test.ts`'s R4 fails the moment the bundle names a new host.** `REVIEWED_HOSTS` at
   `:335-338` is `www.w3.org` and `react.dev`. Add **both** new hosts with the reason each is not a
   fetch. Two sibling rules constrain *where* the URLs may live:
   - **R1 — no external host in any `.css` or `.html` in the built bundle, at all.** So the hrefs live
     in TypeScript only. Never in `index.html`, never in a `content:` or `url()` in a stylesheet.
   - **R3 — no fetchable asset extension anywhere.** Both hrefs end in a path segment with no
     extension, so this stays silent. A link to a `.pdf` policy copy would not.

10. **The `px` citation guard covers every stylesheet under `src/components/`.**
    `tests/shell.test.ts:587-630` extracts every `Npx` literal from each tracked component stylesheet
    and requires the substring `DESIGN.md` **within one sentence** of it (the check is bounded and
    lookbehind-anchored, so a literal cannot ride a neighbour's citation, and a file-header mention
    400 characters away does **not** count — that exact evasion was measured in c2-6). AC 4's 24px hit
    area is citable and truthfully so: `DESIGN.md:375` says *"each link's hit area ≥ 24px tall"* and
    `DESIGN.md:418` says *"a ≥ 24×24px hit area"*. Write the citation beside the value.

11. **There is no motion budget to spend here.** AC 4's hover brightening is a colour change. If a
    `transition` is added it must be built from `--motion-*` tokens (literal durations are banned as
    an accessibility gate) **and** registered in the reduced-motion inventory at the foot of
    `tokens.css` — `ui/README.md:323` calls a motion with no registered fallback an incomplete story.
    The cheapest correct answer is **no transition**, and then there is no inventory entry to owe.

12. **`--accent` is not this component's to spend.** `DESIGN.md:288`: the accent marks *live agent
    attention*. A footer link is neither live nor agent attention. The colours here are exactly the
    two the spec names — `--text-secondary` at rest, `--text-primary` on hover — plus `--focus-ring`
    for focus. `--accent-dim` is banned from primitives outright (`ui/README.md:722-729`).

### Scope, and what will change underneath

13. **The bundle WILL change, and so will the plugin mirror.** `App.tsx` gaining an import is exactly
    what changed the bundle in c2-9 (the first change since c2-6) — tree-shaking no longer excludes
    the module. **Measure it and record the answer**; do not predict it. `npm run build` writes into
    `src/companion/app/static/` (committed), and `uv run python -m scripts.build_plugin` regenerates
    the mirror. CI fails on a stale copy of either.

14. **`AppShell.test.tsx`'s footer-placeholder assertion stays green and must not be deleted.** It
    tests the shell against **its own props** (footer absent → placeholder), which is still true.
    What changes is which of the two the running app shows — the same displacement c2-9 did to the
    left column, and `App.tsx:16-41` is the worked example of how to record it. Do not delete the
    placeholder or the assertion; displace it and say so.

---

## Acceptance Criteria

### The words

1. **Given** the footer attribution renders, **when** its text is read, **then** it states, byte for
   byte: `Card data and imagery courtesy of Scryfall. Unofficial Fan Content permitted under the
   Wizards of the Coast Fan Content Policy. Not approved/endorsed by Wizards.` (UX-DR32,
   `DESIGN.md:375`)

2. **Given** that sentence, **when** the test suite runs, **then** it is asserted **byte for byte
   against `DESIGN.md` itself** — the artefact is read at test time, not transcribed — and the parse
   fails loudly if the source bullet does not yield exactly one quoted run (the c2-9 pattern,
   `tests/copy.test.ts`).

3. **Given** the sentence is rendered in parts so that two runs can be links, **when** those parts are
   re-joined in source order, **then** they reproduce `DESIGN.md`'s sentence exactly, asserted by
   concatenation — nothing is authored that the artefact did not write (c2-9's ruling, `copy.ts`).

4. **Given** the copy module, **when** `tests/copy-rules.test.ts` runs, **then** the module is listed
   in `COPY_MODULES` with the reason it owns copy, and no prose in this story lives outside it. The
   content half (no `!`, no emoji, no "something went wrong") passes unchanged.

### The links

5. **Given** the footer links, **when** they render at rest, **then** they are **persistently
   underlined** — identifiable without hovering — and each opens in a new tab (`target="_blank"` with
   `rel="noopener noreferrer"`). (UX-DR32, `EXPERIENCE.md:101`)

6. **Given** a footer link, **when** it is hovered, **then** it brightens from `--text-secondary` to
   `--text-primary`; **and when** it is focused from the keyboard, **then** it shows a visible focus
   ring built from `--focus-ring` / `--focus-ring-width` / `--focus-ring-offset`. No `outline: none`
   without a replacement. (UX-DR46, UX-DR47)

7. **Given** a footer link, **when** its hit area is inspected in the stylesheet source, **then** it
   is at least **24px tall**, and the literal carries a `DESIGN.md` citation within one sentence of
   it — the named non-ban, used correctly. (UX-DR32, UX-DR47)

8. **Given** the two link hrefs, **when** they are read, **then** they are the same canonical URLs the
   repository's `NOTICE` already uses, and the host of each is listed in `REVIEWED_HOSTS` in
   `tests/fonts.test.ts` with the reason it is not a fetch.

9. **Given** the built bundle, **when** `tests/fonts.test.ts` runs, **then** no `.css` or `.html` in
   it names any external host (R1 unchanged), no font-CDN host appears anywhere (R2 unchanged), no
   fetchable asset extension appears (R3 unchanged), and the external-host set equals the new
   reviewed baseline (R4). The offline guarantee (NFR-06) is untouched: **nothing is fetched** — the
   two hosts are hrefs a human clicks.

### Colour, type and semantics

10. **Given** the footer text, **when** its colour is inspected, **then** it is `--text-secondary`
    (9.3:1 on `--surface-base`) and **not** `--text-tertiary` — a passing tier, not a muted one,
    because this text is legally load-bearing. `AppShell.css`'s current `--text-tertiary` on
    `.app-shell-footer` is resolved, not shadowed by a second rule of equal specificity. (UX-DR32,
    AC-level landmine 1)

11. **Given** the footer's typography, **when** the token guards run, **then** the type role is
    applied with **both** companions in the same block — `letter-spacing: var(--tracking-micro)` and
    `text-transform: uppercase` where the role is `--type-micro` — and no `font-size`,
    `line-height`, `letter-spacing` or `font-*` literal appears anywhere. (Q1 decides the role; the
    companion rule holds either way.)

12. **Given** the footer surface, **when** its stylesheet is read, **then** its background is
    `--surface-base` and it sits above a `1px solid var(--border-hairline)` top border, per
    `DESIGN.md`'s `components.footer-attribution` frontmatter.

13. **Given** the rendered page, **when** its landmarks are inspected, **then** there is **exactly
    one** `contentinfo` — the shell's existing `<footer>`. The component this story adds declares no
    landmark role of its own. (UX-DR44)

### Every surface, and the release condition

14. **Given** the application root, **when** it renders, **then** the attribution is present inside
    the shell's `footer` slot, and the shell's footer placeholder line is **displaced, not deleted** —
    `AppShell.test.tsx`'s placeholder assertion still passes against the component's own props.

15. **Given** the app's top-level surfaces, **when** the suite runs, **then** each asserts the
    attribution is present **by role and by text** — this is a release condition, not a design
    choice. The mechanism by which "every surface" is enforced rather than merely asserted for
    today's one surface is Q3, and whatever is chosen is written down where the next surface's author
    will read it.

16. **Given** the footer component, **when** `tests/shell.test.ts` runs, **then** every new module is
    in `PRIMITIVES` with an exhaustive import list, the non-vacuity length pin is updated, and the
    git-derived coverage check is green **because the list is complete**, not because a file is
    untracked.

17. **Given** the component, **when** its source is read, **then** it is presentation-only: no state,
    no hook, no fetch, no store, no subscription, no `on*` handler prop, no `ref`. It takes no props
    at all unless Q4 rules otherwise.

### Boundaries, records and proof

18. **Given** this story's diff, **when** it is inspected, **then** it touches no `.py` outside the
    regenerated plugin mirror, no `pyproject.toml`, no `uv.lock`, no `package.json`, no new
    dependency, no route, no store and no fetch layer. `DESIGN.md` and `EXPERIENCE.md` are **read,
    not edited** — unless Q1 rules a type-role change, which is a UX-artefact amendment made in the
    open with its reason.

19. **Given** `ui/README.md`, **when** this story lands, **then** it records: the external-host
    protocol (how a later story adds a reviewed host), which artefact the footer copy is gated
    against and why it is `DESIGN.md` rather than `EXPERIENCE.md`, the resolution of the
    `.app-shell-footer` colour, and the repair of the *Not here yet* paragraph, which currently says
    the footer's attribution text is c2-10's.

20. **Given** the five frontend gates and the Python suite, **when** they run, **then** all six are
    green: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run build`,
    and `uv run pytest -m "not integration"` at its unchanged count. The committed bundle and the
    plugin mirror are regenerated, and whether either **changed** is measured and recorded either
    way.

21. **Given** each new or amended guard, **when** the story claims it works, **then** the evasion was
    **planted, caught, and the output pasted** — including at least: a one-character edit to
    `DESIGN.md`'s attribution sentence; a third external host in the bundle; the attribution sentence
    written outside the declared copy module; an uncited `px` literal in the new stylesheet; and the
    type role applied without a companion. Ban the family, never enumerate members.

22. **Given** AC 5, AC 6, AC 7 and AC 10, **when** the story reports on them, **then** the parts jsdom
    cannot decide (underline at rest, hover brightening, focus-ring appearance, the 24px hit box as
    laid out, and whether 10px all-caps legal text is actually readable) are **stated as
    not-dev-verified and added to the epic manual-testing checklist**, not claimed. The source-read
    half of each is still asserted.

---

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement)
  - [x] Branch off `feat/companion-c2` as `feat/companion-c2-10-footer-attribution`; confirm
        `baseline_commit` is `8c864f8`
  - [x] `cd ui && npm test` → record the count (expected **504 passed**); `npm run lint`,
        `npm run format:check`, `npm run typecheck`, `npm run build` all exit 0
  - [x] Repo root: `uv run pytest -m "not integration"` → expect **1,753 passed**. *If
        `test_list_decks_with_strategy_field` fails, it is the known `created_at`-tie flake — re-run
        before investigating.*
  - [x] `git status --porcelain -- src/companion/app/static/ plugin/` clean **after** a build, so a
        later drift is provably yours
  - [x] Record every number in the Dev Agent Record

- [x] **Task 1 — settle the decisions before writing anything** (Q1–Q5)
  - [x] Confirm Brad's answers to Q1–Q5 are in hand; if any is "not as proposed", re-read the ACs it
        touches before starting
  - [x] Write one throwaway probe stylesheet exercising the chosen type role, the underline, the
        hover colour and the 24px hit area; `npm run lint` it; **delete it**. Measure the companion
        guard's demands before committing to a shape.

- [x] **Task 2 — the copy module and its verbatim gate, first, because it is the deliverable**
      (AC 1, 2, 3, 4)
  - [x] The copy module under `src/components/Footer/`; `git add` immediately so every git-derived
        guard can see it
  - [x] The sentence as a **list of parts in source order**, each tagged link-or-text, carrying the
        href for the link parts
  - [x] A node-project test that reads `DESIGN.md` by one path constant, selects the
        footer-attribution bullet **by structure**, and extracts the quoted run
  - [x] **Non-vacuity anchor first**: assert the bullet was found and yielded **exactly one** quoted
        run, so a moved line or a second pair of quotes fails loudly rather than asserting nothing
  - [x] The byte-for-byte assertion, and the concatenation invariant (AC 3)
  - [x] Add the module to `COPY_MODULES` with a reason **over 40 characters**; confirm the extractor
        finds **more than 3 strings** in it

- [x] **Task 3 — the component and its stylesheet** (AC 5, 6, 7, 10, 11, 12, 13, 17)
  - [x] `src/components/Footer/{Footer.tsx, Footer.css, Footer.test.tsx}`; `git add` immediately
  - [x] No landmark role, no `role="contentinfo"` — the shell's `<footer>` is the landmark
  - [x] Links: `target="_blank"`, `rel="noopener noreferrer"`, persistent underline, hover to
        `--text-primary`, `:focus-visible` ring from the focus tokens
  - [x] The 24px hit-area literal **with its `DESIGN.md` citation in the same sentence**
  - [x] Resolve the `.app-shell-footer` colour per Q2 — one rule owns it, no equal-specificity race
  - [x] `npm run lint` after **every** block; the companion guards fail on the block, not on the file

- [x] **Task 4 — the external hosts** (AC 8, 9)
  - [x] Add both hosts to `REVIEWED_HOSTS` in `tests/fonts.test.ts`, each with the reason it is not a
        fetch
  - [x] Confirm R1/R2/R3 stay silent — the hrefs live in TypeScript only, and neither ends in an
        asset extension
  - [x] Cross-check the URLs against the repository's `NOTICE` so the app and the docs cannot drift

- [x] **Task 5 — registration and the screen** (AC 14, 15, 16)
  - [x] Add every new module to `PRIMITIVES` with exhaustive import lists; move the length pin; run
        `tests/shell.test.ts` and confirm the coverage check is green because the list is complete
  - [x] `App.tsx` passes the footer into the shell's `footer` slot, with the displacement of the
        shell's placeholder recorded in the file the way c2-9 recorded the left column's
  - [x] `App.test.tsx` asserts the attribution by role and text (AC 15); implement Q3's mechanism for
        "every surface" and write down where the next surface's author will read it
  - [x] Confirm `AppShell.test.tsx`'s footer-placeholder assertion is **still green**, unmodified

- [x] **Task 6 — records** (AC 19)
  - [x] `ui/README.md`: the reviewed-host protocol; which artefact gates this copy and why; the
        footer-colour resolution; repair the *Not here yet* paragraph (`:829`) and the components
        section
  - [x] `AppShell.css:174-178`'s comment — the slot is filled now; correct it rather than leaving a
        forward-looking sentence that has come true
  - [x] `deferred-work.md`: this story's not-dev-verified visual entries (AC 22)

- [x] **Task 7 — rebuild, mirror, prove** (AC 18, 20)
  - [x] `npm run build`; `uv run python -m scripts.build_plugin`; **measure** whether either tree
        changed and record the answer either way
  - [x] Re-run all five frontend gates and the Python suite (expect **1,753**, unchanged)
  - [x] Scope proof: `git diff --stat` shows no `.py` outside the mirror, no `pyproject.toml`, no
        `uv.lock`, no `package.json`
  - [x] `git status --porcelain` clean

- [x] **Task 8 — probe the evasions before claiming done** (AC 21)
  - [x] For each new or amended guard, plant the evasion, confirm it is caught, revert, paste the
        output
  - [x] **Verify the mutation landed before believing the verdict**, and **read what landed on disk**
  - [x] Probe at least: a one-character edit to the attribution sentence in `DESIGN.md`; a third
        external host in the bundle (and one spelled protocol-relative); the sentence written into a
        module outside `COPY_MODULES`; an uncited `24px`; `--type-micro` without its uppercase
        companion; a new tracked module under `src/components/` missing from `PRIMITIVES`
  - [x] **Ban the family, never enumerate members** — prove each guard with a spelling it does not
        list

### Review Findings

- [x] [Review][Decision→Patch] AC 21's evidentiary form — **RULED (Brad, 2026-07-30, code
      review): re-run the load-bearing probe subset (1: one-char `DESIGN.md` edit; 7: reverted
      `footer` prop; 2b: protocol-relative host) and paste the outputs into the Dev Agent
      Record.** Done — outputs pasted under "Review probe outputs" in the Dev Agent Record.
- [x] [Review][Decision] `DESIGN.md:342`'s "full width" vs the shipped content-width hairline —
      **RULED (Brad, 2026-07-30, code review): the content-width reading is RATIFIED.** The
      hairline aligns with the header and columns inside the shell's `var(--space-gutter)`
      frame. Recorded here and in `deferred-work.md` so it reads as a ruling, not a unilateral
      call.
- [x] [Review][Patch] `display: inline-flex` likely suppresses the persistent underline in real
      browsers — text decoration on a flex container does not propagate into flex items, so AC 5's
      release-condition underline plausibly renders as no underline at all; every gate reads CSS
      source only and jsdom cannot see it [ui/src/components/Footer/Footer.css:77-82]
- [x] [Review][Patch] `readComponentBullets` scans the whole of DESIGN.md, not the Components
      section — any new `- **Label**` bullet anywhere reds the licensing gate's `toBe(38)` pin,
      and a cross-section label collision throws spuriously; scope the parse to the Components
      section [ui/tests/attribution.test.ts:68-85,129]
- [x] [Review][Patch] `REVIEWED_HOSTS` is checked one-directionally (subset, not the equality the
      README claims) — a stale entry stays pre-approved forever; assert each reviewed host still
      occurs in the bundle [ui/tests/fonts.test.ts:354-360,421]
- [x] [Review][Patch] The hover-decoration guard checks the exact property name
      `text-decoration` — the longhand `text-decoration-line: underline` on `:hover` evades it;
      ban the property family [ui/tests/shell.test.ts:829-838]
- [x] [Review][Patch] The exactly-one-`color` guard filters on two exact selector strings — a
      later `.app-shell .app-shell-footer { color: … }` or `footer p` rule reintroduces the Q2
      cascade race unseen; match selectors containing the class names [ui/tests/shell.test.ts:790-800]
- [x] [Review][Patch] The NOTICE href check is raw substring containment — a NOTICE URL of which
      the app's href is a prefix passes while the two point at different pages; use a
      boundary-aware match [ui/tests/attribution.test.ts:215-219]
- [x] [Review][Patch] The 24×24 hit-area citation delivers one axis — `min-height: 24px` with no
      `min-width`; add the width half and its assertion [ui/src/components/Footer/Footer.css:80]
- [x] [Review][Patch] Keyboard focus does not get the brightening hover gets — `:hover` moves to
      `--text-primary` but `:focus-visible` is ring-only, a mild hover-only affordance in a story
      arguing against them; add the colour to the focus block [ui/src/components/Footer/Footer.css:85-100]
- [x] [Review][Patch] The `rel` prose-exclusion is element-agnostic — a custom component treating
      `rel` as arbitrary copy (`<Hint rel="ask your agent…" />`) skips the prose gate; scope the
      skip to intrinsic (lowercase) elements where HTML's token-list grammar applies
      [ui/tests/copy-rules.test.ts:1018-1026]
- [x] [Review][Patch] `sentenceOf`'s `parts` parameter is speculative generality nothing uses —
      every caller calls it bare, and the same diff's Q4 doctrine bans exactly this shape one file
      over; remove the parameter [ui/src/components/Footer/copy.ts:83]
- [x] [Review][Patch] The `no-quoted-run` error conflates "copy deleted" with "quote style
      changed" — a curly-quote conversion yields 0 runs with a message pointing at deletion; name
      the smart-quote case in the error [ui/tests/attribution.test.ts:108-114]
- [x] [Review][Patch] Dev Agent Record claims "eleven new source-read assertions in
      shell.test.ts" — the new describe block contains ten `it` blocks; correct the count
      [story file, Completion Notes + Change Log]
- [x] [Review][Patch] README cross-reference points the wrong direction — "See _The footer
      attribution_ below" while the section is above the referencing bullet [ui/README.md:937-938]
- [x] [Review][Patch] Comment overclaims an accessible-name assertion — the code asserts
      `link.textContent`, not an accessible-name query; align the comment or the assertion
      [ui/src/components/Footer/Footer.test.tsx:63-64]

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| From | Ruling | Where it is written |
|---|---|---|
| c2-6 | one directory per component, three files, no barrels; flat kebab-case classes | `ui/README.md:394-416` |
| c2-6 | the shell owns the window and the single scroll container — the footer is *literally* in the window | `AppShell.css:35-57`, `README:433-447` |
| c2-7 | primitives are hook-free; `filled()` for emptiness; a component module exports the component and types only | `README:465-535` |
| c2-8 | geometry with no token family is expressed off the type role, or is a **cited** literal | `README:591-618` |
| c2-9 | user-facing prose lives in a declared copy module; a copy string is gated against the artefact that wrote it; parts re-join by concatenation | `README:731-810` |
| c2-9 | the shell's placeholder for a filled slot is **displaced, not deleted**, and the displacement is recorded in `App.tsx` | `App.tsx:16-41`, `README:835-841` |

### The five things this story must not break

1. **The single scroll container.** No second `100dvh`/`100vh`, no `position: sticky` on the footer,
   no `overflow: hidden` on a root. Three separate guards in `tests/shell.test.ts` cover this.
2. **Exactly one of each landmark.** `AppShell.test.tsx` asserts one `banner`, one `main`, one
   `contentinfo`. The footer component adds no role.
3. **The token layer's literal bans.** No hex, no `rgb()`, no literal spacing/radius/shadow/duration,
   no `font-size`, no inline `style={{…}}`, no native CSS nesting, no component-declared custom
   property.
4. **`declaredTokens.size === 65`.** This story adds **no token**. If a value seems to need one, it
   is a `DESIGN.md` amendment, not a frontend decision — and `DESIGN.md`'s
   `components.footer-attribution` frontmatter already carries all four values this needs.
5. **The offline guarantee.** Nothing is fetched. The two external hosts are hrefs, and the reviewed
   baseline is how that claim is kept honest rather than asserted.

### Source tree — what exists, what this story adds

```
ui/
  src/
    App.tsx                          UPDATE  — pass the footer into the shell's `footer` slot
    App.test.tsx                     UPDATE  — AC 15's surface assertion
    components/
      AppShell/AppShell.css          UPDATE  — the footer colour (Q2), and the stale comment
      Footer/Footer.tsx              NEW
      Footer/Footer.css              NEW
      Footer/Footer.test.tsx         NEW     — colocated, lands in the `dom` project automatically
      Footer/copy.ts                 NEW     — the words + the hrefs, as parts (name per Q5)
  tests/
    attribution.test.ts              NEW     — the DESIGN.md verbatim gate (name per Q5)
    copy-rules.test.ts               UPDATE  — COPY_MODULES gains the copy module
    fonts.test.ts                    UPDATE  — REVIEWED_HOSTS gains two hosts
    shell.test.ts                    UPDATE  — PRIMITIVES gains the new modules; length pin moves
  README.md                          UPDATE  — AC 19
src/companion/app/static/**          REGEN   — `npm run build`
plugin/**                            REGEN   — `uv run python -m scripts.build_plugin`
_bmad-output/implementation-artifacts/deferred-work.md   UPDATE — AC 22
```

Nothing else. No `.py`, no dependency, no route, no store, no fetch.

### Previous story intelligence (c2-9, PR #26, Greptile 4/5 → 5/5)

- **The one P2 Greptile found was a *type* problem, and the fix was a type-only change** — a flat
  `decks` prop let future wiring render deck names under the wrong copy. The lesson that transfers:
  when a prop shape permits a combination the prose forbids, **constrain the type and leave the
  renderer dumb**. Relevant here only if Q4 gives the footer props at all; the recommendation is that
  it takes none.
- **Review theme, twice over: "a guard proven only against spellings it lists."** The `--accent`
  allowlist admitted `--accent-dim` through an open prefix. Apply it directly to the reviewed-host
  list: `scryfall.com` and `www.scryfall.com` are different hosts to a host-set check, and so are
  `company.wizards.com` and `magic.wizards.com`. Decide the exact host string, and probe a
  protocol-relative spelling.
- **"The thing one layer above the tested thing is unproven."** Reverting `App.tsx`'s `left` prop kept
  all 487 tests green. AC 15 exists so that reverting `App.tsx`'s `footer` prop does **not** stay
  green. Write that assertion before writing the component if it helps.
- **A prediction measured wrong is corrected in place, not quietly applied.** c2-9 found the mono
  stack needed a fourth cost nobody predicted (stylelint's `value-keyword-case`). Expect one such
  here and record it.
- **Same-day three-layer review before the PR is now three-for-three on round-1 Greptile passes**
  (c2-5, c2-8; c2-9 was 4/5 at round 1 on a genuine finding). Keep the pattern.

### Git intelligence

Last five commits are all c2-9's landing (`8c864f8`, `efa2435`, `b93dafd`, `d789eb5`, `109a7d9`).
The shapes worth copying from `d789eb5`: the artefact-reading gate with a loud parser, the copy
module with its parts, the `PRIMITIVES` entries with exhaustive imports, and the `App.tsx` header
comment that records a displacement rather than performing one silently.

### Gotchas specific to this story

- **`git add` new files immediately.** Four separate guards derive their file lists from
  `git ls-files`. An untracked new module passes every one of them **vacuously** — the failure mode
  is a green suite that read nothing.
- **The companion guards read the *block*, not the file.** `letter-spacing` and `text-transform` must
  sit in the same rule block as the `font: var(--type-*)` that requires them. Splitting them across a
  base rule and a modifier is a failure even though the cascade would produce the right pixels.
- **`text-transform: uppercase` does not change the DOM text**, so the verbatim gate, the copy-rules
  content half and the accessibility tree are all unaffected by Q1's outcome. Only the render is.
- **`rel="noopener noreferrer"` is not optional** even though `target="_blank"` implies `noopener` in
  current browsers — the explicit form is what a reviewer can see.
- **Prettier will reflow long JSX.** Run `npm run format:check` before assuming a lint failure is
  semantic.
- **Line endings are forced to LF.** A hand-edited test fixture with CRLF is red on Windows and green
  on CI from the same commit.

### Testing standards

- Node-project gate/guard tests live in `ui/tests/*.test.ts`; component tests are **colocated**
  `.test.tsx` and land in the `dom` project automatically (`tests/gate-geometry.test.ts` fails a
  `.tsx` test under `tests/`).
- **Assert by role, through `@testing-library/react`** — never by class name, never by test id. AC 15
  is `getByRole('contentinfo')` plus the text; AC 5's link assertions are `getAllByRole('link')` with
  their accessible names and `href`s.
- **Non-vacuity anchor first, in every guard.** An empty scan must not read as silence.
- **A guard's limits go in its own header comment**, the way `copy-rules.test.ts:48-72` and
  `surfaces.ts` declare theirs. A limit that is not written down reads as coverage.
- `npm test` does not build; `npm run build` mutates `src/` — check `git status` before committing.

### Architecture rules this story implements

- **NFR-08** — visible Scryfall attribution in the app footer, plus the WotC Fan Content Policy
  notice for the public release.
- **NFR-06** — offline parity is untouched; the two hosts are links, not fetches.
- **UX-DR32** — the footer attribution spec in full (copy, tier, links, hit area, always visible).
- **UX-DR44** — `<footer>` exposing `contentinfo`; exactly one.
- **UX-DR46 / UX-DR47** — visible focus ring, ≥24px hit area, no hover-only affordance.
- **UX-DR33** — the voice rules, enforced by `tests/copy-rules.test.ts`; the second-person-and-
  blameless half is **review's**, declared as residue 1 in that guard's header and naming c2-10 by
  name.

### References

- [Source: `_bmad-output/planning-artifacts/epics-companion-app.md#Story 2.10`] — the six ACs
- [Source: `.../ux-designs/.../DESIGN.md:261-265`] — `components.footer-attribution` frontmatter
- [Source: `.../ux-designs/.../DESIGN.md:324`, `:342`, `:375`] — the micro role, the layout slot, the
  full footer spec **and the verbatim sentence**
- [Source: `.../ux-designs/.../DESIGN.md:418`] — the ≥24×24px hit-area rule
- [Source: `.../ux-designs/.../EXPERIENCE.md:48`, `:101`, `:141`, `:144`, `:155`] — P0 status, the
  behavioural contract, Tab order, Enter behaviour, hit targets
- [Source: `_bmad-output/planning-artifacts/epics-companion-app.md:170-172`] — NFR-08
- [Source: `ui/README.md:183-352`] — the token layer and its ban table
- [Source: `ui/README.md:731-810`] — the copy contract c2-10 inherits
- [Source: `ui/src/components/AppShell/AppShell.css:174-185`] — the slot this story fills
- [Source: `ui/tests/fonts.test.ts:292-400`] — the four external-reference rules
- [Source: `ui/tests/copy-rules.test.ts:103-121`] — `COPY_MODULES`
- [Source: `ui/tests/shell.test.ts:983-1079`] — `PRIMITIVES` and its git-derived coverage check
- [Source: `NOTICE`] — the canonical attribution URLs

---

## Open questions for Brad — answer before `dev-story`

**Q1 — The legal sentence renders as 10px ALL-CAPS. Ship it, or amend `DESIGN.md`?**
`DESIGN.md:324` assigns footer attribution to `{typography.micro}`, which is `400 10px/1.3` with
`0.08em` tracking and is declared **uppercase**; `tests/token-usage.test.ts` derives that requirement
from the artefact, so applying the role without `text-transform: uppercase` is a test failure. The
result is three sentences of legally load-bearing text at 10px in capitals. The contrast AC exists
precisely because this text must be readable — and case and size are the other two halves of
readability, which no AC covers.
*Recommendation: **ship the spec as written** (micro + uppercase + `--text-secondary`).* It is what
the artefact says, it is the "one quiet line, never louder than this" register, the DOM text is
unaffected so nothing about the contract or the screen reader changes, and deviating means amending a
UX artefact on a frontend story. **Flag it on the epic manual-testing checklist as the first thing to
look at** — if it reads badly by eye, the correction is a `DESIGN.md` amendment in Epic 8's
release-readiness pass, made with the rendered page in hand rather than from the spec.
*Alternative if you want it readable now: `--type-body` (13px, no uppercase, no tracking companion)
plus a one-line `DESIGN.md` amendment recording why.*

**Q2 — Who owns the footer's colour and type: `AppShell.css` or `Footer.css`?**
`.app-shell-footer` currently sets `--text-tertiary` + the micro role. `Footer.css` will set
`--text-secondary` + the same role. Two single-class selectors setting `color` is decided by source
order, which is decided by import order — a race this repo has already been bitten by once.
*Recommendation: **strip the type and colour out of `.app-shell-footer`, leaving it `flex-shrink: 0`
only**, and let `Footer.css` own everything `DESIGN.md` assigns to `components.footer-attribution`
(foreground, background, border-top, type).* The shell keeps layout, the component keeps appearance,
and there is no cascade to reason about. The shell's placeholder line has its own class and its own
`--type-body`, so it is unaffected.

**Q3 — What does "every top-level surface" mean when there is exactly one surface?**
AC 6 of the epic asks a test suite covering every top-level surface to assert the footer. Today
`App.tsx` is the only surface, so a literal reading is one assertion — and that assertion is
satisfied for the life of the app by a single `render(<App />)`.
*Recommendation: **assert it at `App.tsx` and make the rule structural rather than enumerated** — a
guard asserting that `App.tsx` renders the shell with a non-empty `footer` prop, plus a written rule
in `ui/README.md` that every future surface renders through `AppShell` (which is already true: there
is one shell, one `footer` slot, and no router).* An enumerated surface list would be a list its
author thought of, which is this epic's standing finding. The structural version costs one test and
is right when c6-5's agent view arrives — the overlay renders **inside** the shell, so the footer
survives it by construction.

**Q4 — Does `Footer` take any props?**
The copy is fixed and the links are fixed. A `className` or a slot prop would be speculative
generality.
*Recommendation: **no props at all.*** It is the strongest form of "this is static", it makes AC 17
trivial, and c2-9's Greptile finding was precisely about a prop shape admitting states the prose
forbids — a component with no props cannot have that defect.

**Q5 — Naming: the copy module and the gate file.**
c2-9 used `src/components/StatePanel/copy.ts` + `ui/tests/copy.test.ts`. `copy.test.ts` is taken and
owns the `EXPERIENCE.md` half.
*Recommendation: **`src/components/Footer/copy.ts`** (same convention, different directory — the
`COPY_MODULES` map is keyed by full path, so no collision) and **`ui/tests/attribution.test.ts`** for
the `DESIGN.md` verbatim gate. Naming it `attribution` rather than `footer-copy` is deliberate: what
it gates is a licensing obligation, and Epic 8's docs-attribution story (`epics:3269`) is the natural
second consumer of the same parse.*

---

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, `bmad-dev-story`), 2026-07-30.

### Baseline (Task 0, measured — not assumed)

Branched `feat/companion-c2-10-footer-attribution` off `feat/companion-c2` at `8c864f8`
(`git rev-parse HEAD` confirmed the frontmatter's `baseline_commit`).

| Gate | Baseline | Final |
|---|---|---|
| `npm test` | **504 passed** / 26 files | **546 passed** / 28 files |
| `uv run pytest -m "not integration"` | **1,753 passed**, 1 skipped | **1,753 passed**, 1 skipped |
| `npm run lint` | exit 0 | exit 0 |
| `npm run format:check` | exit 0 | exit 0 |
| `npm run typecheck` | exit 0 | exit 0 |
| `npm run build` | exit 0 | exit 0 |
| bundle + mirror after build | clean | clean |

The Python suite hit `test_list_decks_with_strategy_field` once on the final run — the known
`created_at`-tie flake the story names. Re-run per the instruction: **1,753 passed**. Not
investigated further, and not a regression.

### Debug Log References

**Bundle and mirror: MEASURED CHANGED, both hashes.** This is the first story of the epic to
move the **CSS** hash as well as the JS, because it is the first to add a stylesheet that reaches
an on-screen consumer — c2-9 changed JS only.

| Artefact | Baseline | Final |
|---|---|---|
| `assets/index-*.css` | `index-C-cdYYMS.css` (4.57 kB) | `index-BNWx870j.css` (5.01 kB) |
| `assets/index-*.js` | `index-D_x1yvrv.js` (194.56 kB) | `index-DI8FuBU0.js` (195.14 kB) |
| `index.html` | — | modified (hashed asset names) |
| font `.woff2` | `space-grotesk-…-BhU9QXUp.woff2` | unchanged |

`plugin/` mirror regenerated by `uv run python -m scripts.build_plugin` and moves in step. A
final `npm run build` produced no unstaged drift, so the committed bundle matches a fresh build.

**Nine evasion probes planted in the real tree, all nine caught.** Every mutation was verified on
disk before the verdict was believed, and every revert was verified after. None passed.

| # | Evasion (spelled to defeat an enumeration) | Guard | Result |
|---|---|---|---|
| 1 | **One character** of `DESIGN.md`'s sentence: `Wizards.` → `wizards.` | `attribution.test.ts` | 2 failures |
| 2a | `www.scryfall.com` — the **`www` form of an already-listed host** | `fonts.test.ts` R4 | 2 failures |
| 2b | `//telemetry.example.net/beacon` — **protocol-relative**, unlisted | R4 + NOTICE + https checks | 4 failures |
| 3 | The sentence written into `Footer.tsx`, outside `COPY_MODULES` | `copy-rules.test.ts` file half | 1 failure, naming the module |
| 4a | `min-width: 44px` — **a literal nobody enumerated** | `shell.test.ts` citation guard | 1 failure |
| 4b | `24px` kept, `DESIGN.md` moved **out of proximity** (still in file) | same | 1 failure |
| 5 | `--type-micro` without `text-transform: uppercase` | `token-usage.test.ts` | 1 failure |
| 6 | A new **git-tracked** module under `src/components/` absent from `PRIMITIVES` | `shell.test.ts` coverage | 1 failure |
| 7 | **`App.tsx`'s `footer` prop silently reverted** | `App.test.tsx` | 3 failures |
| 8 | `--accent-bright` — an **unnamed family member** inside a `var()` **fallback** | `shell.test.ts` | 2 failures |
| 9 | The underline moved from rest to **hover-only** | `shell.test.ts` | 1 failure |

Probe 7 is the load-bearing one: it is c2-9's measured hole reproduced in this story's shape
(reverting `App.tsx`'s `left` prop kept all 487 tests green). Probe 4b is c2-6's: a citation
elsewhere in the same file does not satisfy a proximity check. Probe 2a is c2-9's review theme
applied to the one list in the repo where it bites hardest.

### Review probe outputs (D1 ruling, 2026-07-30 — the load-bearing subset, re-run and pasted)

Each mutation was verified on disk before the run and reverted (and re-verified) after.
Note the post-review counts: the review's patches changed the bundle hashes again
(`index-DmxBiI94.css` / `index-DE70muY2.js`) and the suite is now 549.

**Probe 1 — one character of `DESIGN.md`'s sentence (`Wizards.` → `wizards.`):**

```
× re-joins the parts in source order to the artefact sentence exactly (AC 3) 3ms
× writes no run the artefact did not write — link labels included 1ms
FAIL  |node| tests/attribution.test.ts > ... > re-joins the parts in source order ...
AssertionError: expected 'Card data and imagery courtesy of Scr…' to be 'Card data and
imagery courtesy of Scr…' // Object.is equality
FAIL  |node| tests/attribution.test.ts > ... > writes no run the artefact did not write ...
AssertionError: expected '...' to contain '. Not approved/endorsed by Wizards.'
Tests  2 failed | 13 passed (15)
```

**Probe 7 — `App.tsx`'s `footer` prop silently reverted:**

```
× renders inside the contentinfo landmark, by role and by text 7ms
× exposes both attribution links from the rendered app, not just from the component 6ms
× leaves no surface without it — the slot is filled, not merely fillable (Q3) 3ms
FAIL  AssertionError: expected 'Scryfall and Fan Content attribution …' to be 'Card data
and imagery courtesy of Scr…' // Object.is equality
FAIL  TestingLibraryElementError: Unable to find an accessible element with the role "link"
FAIL  AssertionError: expected 'Scryfall and Fan Content attribution …' not to contain
'lands here'
Tests  3 failed | 3 passed (6)
```

**Probe 2b — a protocol-relative host planted in the built bundle
(`// probe: fetch("//telemetry.example.net/beacon")` appended to `assets/index-DE70muY2.js`):**

```
× names no external host in any .css or .html, and no font CDN anywhere 5ms
× leaves the real bundle alone in the same invocation (the silent half) 1ms
+ "assets/index-DE70muY2.js references //telemetry.example.net/beacon — a host no reviewer
has signed off. Every external host in the bundle is listed in REVIEWED_HOSTS in this file
with the reason it is not a fetch. ..."
Tests  2 failed | 18 passed (20)
```

(2 failures here, not the original table's 4: the original probe planted the host as an href
in `copy.ts`, which additionally trips the NOTICE and https checks; this re-run planted it in
the bundle itself, which is R4's half alone. Both spellings are caught.)

After each revert: `attribution.test.ts` 15/15, `App.test.tsx` 6/6, `fonts.test.ts` 20/20.

### Completion Notes List

**All five open questions answered "as proposed" — the ninth story running.** Q1 ship the micro
role as specified (10px all-caps), Q2 `Footer.css` owns appearance, Q3 structural not enumerated,
Q4 no props, Q5 `Footer/copy.ts` + `tests/attribution.test.ts`.

**One thing was measured differently from the story's plan and is recorded rather than quietly
applied.** The story predicted no gate change beyond the four it named. In fact
`tests/copy-rules.test.ts` had to gain a **structural exclusion**: `rel="noopener noreferrer"` is
two space-separated Latin words and matched the `PROSE` detector exactly, failing the file half
against a component containing no copy at all. The fix is the existing `className` precedent
generalised — an attribute whose value is an HTML **space-separated token list** is chrome by
construction, skipped by tree position rather than by sniffing the string, and `CLASS_ATTRIBUTE`
was renamed `TOKEN_LIST_ATTRIBUTE` to match its contents. Both halves are probed (silent on
`rel`, still firing on real copy inside the same anchor), and the exclusion is **one-sided**: the
content half still reads those attributes, which is now asserted rather than merely claimed.
This list is documented as **the one place this epic's "ban the family, never enumerate members"
rule inverts** — a missing entry is a visible false positive; a too-broad entry is the failure
that hides.

**A second self-inflicted find, caught by running the guard I had just written.** The new
`outline: none` check read the file **text**, and `Footer.css`'s own comment says the words
"outline: none" to explain why it does not appear — so the guard went red against a stylesheet
that is entirely correct. Repaired by stripping comments first, which is the same
comments-vs-source distinction this epic has now hit in three separate guards.

**What shipped.** The copy module as a list of parts gated by concatenation against `DESIGN.md`
itself; a parser that selects the bullet **by structure** (38 bullets, 38 distinct labels
measured at `8c864f8`) and **throws loudly** on all four shape changes — no bullet, no quoted
run, a second quoted run, a duplicated label — each with its own firing test plus a silent half;
the component (no props, no react import, no landmark role, both links `target="_blank"` with
both `rel` tokens spelled out); the stylesheet (the micro role with **both** companions in one
block, `--text-secondary` not `--text-tertiary`, underline at rest, hover to `--text-primary`,
the first `:focus-visible` ring in the codebase, one cited `24px` hit box); and ten new
source-read assertions in `shell.test.ts` where CSS is actually decidable. (Recorded as
"eleven" until the review's count correction, 2026-07-30.)

**Q2's ruling removed a race rather than winning it.** `.app-shell-footer` is now
`flex-shrink: 0` only. A guard asserts that **exactly one block in the whole tree** declares that
colour, so the equal-specificity race cannot reappear — which is stronger than having picked a
winner.

**Q3 cost one test and is right through Epic 6.** c6-5's agent view renders into the shell's
`overlay` slot, not a route, so the footer survives it by construction.

**Two firsts worth flagging for later stories.** These are the **first focusable elements in the
codebase**, so `--focus-ring` / `--focus-ring-width` / `--focus-ring-offset` get their first ever
render here (they shipped in c2-1 with nothing to point at) — c4-11 inherits whatever the eye
check finds. And this is the **first story to put an external host in the bundle**; the protocol
for adding one is now written in `tests/fonts.test.ts` and `ui/README.md` rather than inferable
only from this diff.

**Not dev-verified, and claimed nowhere** (AC 22 — five entries appended to `deferred-work.md`):
the 10px all-caps legibility (**first on the manual-testing checklist**, Brad's Q1 ruling
explicitly homes any correction at Epic 8), the 24px box as laid out, the underline and hover
brightening at 10px, the focus ring's appearance, and the border/surface separation. jsdom
applies no stylesheet and has no layout engine; there is deliberately no `getComputedStyle`
assertion anywhere in this story.

**Scope proof.** No `.py` outside the regenerated mirror, no `pyproject.toml`, no `uv.lock`, no
`package.json`, no new dependency, no route, no store, no fetch. `DESIGN.md` and `EXPERIENCE.md`
were **read, not edited** — Q1 took the spec as written, so no artefact amendment was owed.
**No token added; `declaredTokens.size` stays 65.**

## File List

**New**

- `ui/src/components/Footer/copy.ts`
- `ui/src/components/Footer/Footer.tsx`
- `ui/src/components/Footer/Footer.css`
- `ui/src/components/Footer/Footer.test.tsx`
- `ui/tests/attribution.test.ts`

**Modified**

- `ui/src/App.tsx` — the `footer` prop, the displacement record, Q3's structural rule
- `ui/src/App.test.tsx` — AC 15's three surface assertions
- `ui/src/components/AppShell/AppShell.css` — Q2: footer rule stripped to `flex-shrink: 0`; stale comment corrected
- `ui/tests/copy-rules.test.ts` — `COPY_MODULES` entry; `TOKEN_LIST_ATTRIBUTE` (was `CLASS_ATTRIBUTE`) + two proofs
- `ui/tests/fonts.test.ts` — two `REVIEWED_HOSTS` entries + the add-a-host protocol
- `ui/tests/shell.test.ts` — two `PRIMITIVES` entries, length pin 12 → 14, ten footer-stylesheet assertions
- `ui/README.md` — the footer-attribution section, the external-host protocol, *Not here yet* repaired, OFL sentence corrected
- `_bmad-output/implementation-artifacts/deferred-work.md` — five not-dev-verified visual entries
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status
- `_bmad-output/implementation-artifacts/c2-10-footer-attribution-on-every-surface.md` — this record

**Regenerated**

- `src/companion/app/static/**` — `npm run build` (both hashes changed)
- `plugin/server/src/companion/app/static/**` — `uv run python -m scripts.build_plugin`

## Change Log

| Date | Version | Description | Author |
|---|---|---|---|
| 2026-07-30 | 0.1 | Story contexted off `8c864f8` — 14 landmines, 22 ACs, 5 open questions | Bob (SM) |
| 2026-07-30 | 1.1 | Adversarial code review (3 layers) → done. 2 decisions ruled (probe subset re-run + pasted; content-width footer RATIFIED), 15 patches applied, 5 findings dismissed. Headline: `display: inline-flex` was suppressing the release-condition underline in real browsers (decoration does not propagate into flex items) — now `inline-block`, both hit-area axes, focus brightening added; the attribution parser scoped to `## Components` (pin 38→24 section bullets); R4 gains its equality half; four guard evasions closed (decoration longhand, colour-selector containment, NOTICE prefix, `rel` on custom components). Suite 546 → 549; Python 1,753 unchanged; bundle + mirror regenerated (hashes moved again: `DmxBiI94.css` / `DE70muY2.js`). | Claude (code review) |
| 2026-07-30 | 1.0 | Implemented → review. Q1–Q5 all as proposed (9th story running). Copy module + `DESIGN.md` verbatim gate, the component, the stylesheet, two reviewed hosts, `PRIMITIVES` 12→14, Q3's structural surface rule. Suites 504 → 546 frontend, Python 1,753 unchanged; six gates green; bundle + mirror MEASURED CHANGED (both hashes — first CSS-hash change of the epic). Nine evasion probes, all nine caught. One unpredicted gate cost recorded in place: `rel="noopener noreferrer"` matched the prose detector, fixed structurally as `TOKEN_LIST_ATTRIBUTE`. No token, no dependency, no `.py`, no artefact amendment. | Amelia (Dev) |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

CODE REVIEW 2026-07-30 → done — three-layer bmad-code-review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): 27 raw findings → 2 rulings + 15 patches applied + 5 dismissed, 0 deferred. HEADLINE (a real browser bug no gate could see): display: inline-flex on the links SUPPRESSES the release-condition underline — text decoration does not propagate into flex items, so AC 5's central visual claim was true in source and false on screen; now inline-block with BOTH hit-area axes (min-width joined min-height — the citation named the 24×24 rule and delivered one axis) and the display value pinned as exact so a tidy-up back to flex is red. ALSO: the attribution parser was FILE-scoped, so any DESIGN.md bullet edit anywhere reddened the licensing gate — now scoped to `## Components` by structure with its own firing/silent halves (pin 38 → 24 section bullets); R4 gained its EQUALITY half (a reviewed host that leaves the bundle is now loud, closing the stale-pre-approval hole); the hover-decoration guard bans the text-decoration FAMILY not the shorthand; the one-colour guard matches selectors by CONTAINMENT not the two spellings it listed; the NOTICE href check is boundary-aware (a prefix of a longer URL no longer passes); the rel prose-exclusion stops at INTRINSIC elements (a custom component's rel prop is copy again); :focus-visible brightens like hover (UX-DR47 applied to the brightening); sentenceOf lost its speculative parts parameter (Q4's own doctrine); the 0-run parser error now names the curly-quote case. 2 RULINGS (Brad): AC 21's evidentiary form — the load-bearing probe subset RE-RUN with outputs PASTED into the record (probe 1: 2 failures; probe 7: 3 failures; probe 2b: 2 failures, R4 naming the planted host); and DESIGN.md:342's 'full width' — the content-width reading RATIFIED (hairline aligns with header and columns inside the gutter frame; no longer a unilateral call). 5 dismissed: the dated-artefact path (documented, matches both sibling gates), the hand-typed placeholder strings (the textContent-toBe and href assertions carry the regression regardless), the determinism-test name, the line-number-citation convention, Function.length's declared runtime floor. Suites 546 → 549 frontend / Python 1,753 unchanged; six gates green; bundle + mirror REGENERATED AGAIN (hashes moved a second time: index-DmxBiI94.css / index-DE70muY2.js). Epic C2 is 10 of 10 implemented+reviewed; next = PR to the umbrella, then the C2 retrospective. Previously — IMPLEMENTED 2026-07-30 off 8c864f8 — the last story of Epic C2, and the only one whose deliverable is a CONDITION OF PUBLIC RELEASE. Q1-Q5 all 'as proposed' (9th story running). SHIPPED: the copy module as a LIST OF PARTS gated by concatenation against DESIGN.md ITSELF — c2-9's mechanism pointed at a SECOND artefact, because EXPERIENCE.md's table has no footer row (its :101 entry is behavioural) and the words exist only at DESIGN.md:375; the parser selects the bullet BY STRUCTURE (38 bullets / 38 distinct labels measured at 8c864f8, so the duplicate-label throw is safe on the real artefact) and THROWS LOUDLY on all four shape changes — no bullet, no quoted run, a SECOND quoted run, a duplicated label — each with its own firing test AND a silent half. The component takes NO PROPS and imports no react (the shortest PRIMITIVES entry in the file), declares NO landmark role (the shell's <footer> is the one contentinfo), and both links carry target=_blank with both rel tokens spelled out. The stylesheet applies the micro role with BOTH companions in one block, --text-secondary NOT --text-tertiary, underline AT REST, hover to --text-primary, ONE cited 24px hit box, and the FIRST :focus-visible ring in the codebase (the --focus-ring* tokens shipped in c2-1 with nothing to point at). Q2 REMOVED a cascade race rather than winning it: .app-shell-footer is now flex-shrink: 0 ONLY, and a guard asserts exactly ONE block in the whole tree declares that colour. Q3's 'every surface' is STRUCTURAL not enumerated (one AppShell, one footer slot, no router) and holds through Epic 6 unamended, since c6-5's agent view is an overlay INSIDE the shell. TWO SELF-INFLICTED FINDS, both caught by running my own new guards and both fixed structurally: rel="noopener noreferrer" is two space-separated Latin words and matched the PROSE detector, reddening a component with no copy in it — repaired by generalising the existing className precedent (CLASS_ATTRIBUTE -> TOKEN_LIST_ATTRIBUTE, keyed on TREE POSITION not on sniffing the string, one-sided so the content half still reads those attributes, and documented as THE ONE PLACE this epic's 'ban the family' rule INVERTS because a missing exclusion is a visible false positive while a too-broad one hides); and the new `outline: none` check read FILE TEXT, so Footer.css's own comment explaining why it does not appear turned it red — the comments-vs-source distinction, now hit in three separate guards. Suites 504 -> 546 frontend / Python 1,753 re-run unchanged (one hit of the known created_at-tie flake, re-run clean per the story's own instruction); six gates green; tokens UNCHANGED at 65. BUNDLE + MIRROR MEASURED CHANGED ON BOTH HASHES (index-C-cdYYMS.css -> index-BNWx870j.css AND index-D_x1yvrv.js -> index-DI8FuBU0.js) — the first CSS-hash change of the epic, because this is the first story to add a stylesheet with an on-screen consumer. NINE evasion probes, ALL NINE CAUGHT, every mutation verified on disk before the verdict and every revert verified after: the load-bearing three are probe 7 (App.tsx's footer prop silently reverted — c2-9's measured hole reproduced in this story's shape, 3 failures), probe 2a (www.scryfall.com, the www form of an ALREADY-LISTED host) and probe 4b (24px kept but DESIGN.md moved out of PROXIMITY while still in the file — c2-6's evasion). AC 22 split: 5 not-dev-verified visual entries in deferred-work.md, headed by whether 10px ALL-CAPS legal text is actually readable — Brad's Q1 ruling ships the spec as written and homes any correction at Epic 8's release-readiness pass, with the rendered page in hand. DESIGN.md and EXPERIENCE.md READ, NOT EDITED. No token, no dependency, no .py outside the mirror, no route, no store, no fetch. Previously — contexted 2026-07-30 off 8c864f8 with 14 landmines, 22 ACs and 5 open questions PR #27 MERGED into the umbrella at f378c56 (2026-07-30), Greptile 5/5 at ROUND 1 — the epic ends 3-for-3 on same-day-three-layer-review-then-round-1-5/5.
