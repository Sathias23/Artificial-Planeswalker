---
epic: c2
story: c2-5
work_branch: feat/companion-c2
story_branch: feat/companion-c2-5-space-grotesk
depends_on: PR #21 (c2-4) must be merged into feat/companion-c2 first — see Blocking dependency
baseline_commit: ff39129ed92fd30ee00ee43d0b127fc57ee2ffc0
---

# Story C2.5: Self-hosted Space Grotesk with offline parity and tabular numerals

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad using the app with no network,
I want the typeface to load from the app's own assets,
so that the product looks identical offline, which is its entire posture.

**What this story really is.** It is the **first story in the feature that ships a binary**, and
the first that has to *obtain* an asset rather than write one. Everything else in `ui/` so far
is text that git normalises freely; a `.woff2` that git touches is a font that does not decode.
It is also the story that closes **the one value family c2-4 left ungated** — typography
literals — which c2-4's review deferred here by name.

So the deliverable is three things that are easy to mistake for one: **the binary** (sourced,
committed, provably intact), **the `@font-face` that makes `--font-sans` real** (already
declared by c2-4, currently resolving to `system-ui`), and **the guards that make "offline" and
"tabular numerals" mechanical facts rather than review items.**

**Ten things were measured on this machine at `c4ddd68` — do not rediscover them:**

1. **The font binaries do not exist anywhere in this repo, and the imported design system
   points at a CDN.** `git ls-files` matches no `.woff2`/`.woff`/`.ttf`/`.otf` at all, and the
   imported `_ds/tokens/fonts.css` is a single Google Fonts `@import` whose own comment reads
   *"Webfonts via Google Fonts CDN — no binaries were provided; flagged in readme."* Sourcing
   the file is this story's first act, not an assumption. Q1 rules on how.

2. **The variable font is 5.6× smaller than the static set and covers every weight the design
   uses.** Measured with `npm pack --dry-run`: `@fontsource-variable/space-grotesk@5.3.0`
   (OFL-1.1) ships **`space-grotesk-latin-wght-normal.woff2` at 22.3 kB**, latin-ext at 18.9 kB,
   vietnamese at 6.7 kB and a 4.4 kB `LICENSE` — **67.4 kB unpacked**. The static
   `@fontsource/space-grotesk` is **377.5 kB unpacked**. DESIGN.md's seven roles use weights
   **400, 500 and 700**; the variable axis is 300–700, so **one 22.3 kB file covers all of them**.

3. **`function-url-quotes` rejects the obvious `@font-face`.** Measured: `src:
   url(./space-grotesk-latin-wght-normal.woff2) format('woff2')` → **1 error**
   (`Expected quotes around "url" function argument`). The quoted form
   `url('./…woff2')` exits **0 — entirely clean**, and that includes `font-weight: 300 700`,
   the variable-range syntax, which survives every rule c2-4 added.

4. **NOTHING in the current config catches a CDN `@import`.** Measured: a file containing only
   `@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk');` lints **exit 0**.
   The offline AC's guard has to be new — no existing rule, in either layer, covers it.

5. **The binary-safety attribute is already in place — for `.woff2` only.** `ui/.gitattributes`
   declares `* text=auto eol=lf` and then `*.woff2 binary` (pre-placed by c2-1, the same
   move as its `.prettierignore` entry). `core.autocrlf` is **`true`** on this machine, so that
   line is load-bearing, not decorative. **`.woff` (v1) is NOT listed** — shipping a v1 fallback
   would be corrupted on checkout, silently, on Windows only. The root `.gitattributes` already
   carries `src/companion/app/static/** -text`, and its comment names this story as the reason.

6. **The serving layer is already correct, and forward-dated to this story.** `spa.py` registers
   `.woff2 → font/woff2` and `.woff → font/woff`, both marked `# c2-5`, because `mimetypes`
   resolves `.woff2` to `None` on this machine and Starlette's `FileResponse` falls back to
   `text/plain` — a font served as text does not load. Those two markers plus the
   `.gitattributes` comment are forward-dated comments this story repairs (AC 13).

7. **Fonts must reach `assets/`, never `public/`.** Measured in `spa.py`: `_IMMUTABLE_CACHE_CONTROL`
   (`public, max-age=31536000, immutable`) is applied by checking whether the first path segment
   is `assets`; everything else gets `no-cache`. A font in `ui/public/` lands at the output
   **root**, unhashed, and is revalidated on every load. A font referenced from CSS is
   content-hashed into `assets/` and cached for a year. Vite's default `assetsInlineLimit` is
   4096 bytes, so a 22 kB font is emitted as a file rather than base64-inlined into the CSS.

8. **No Python test needs editing.** `tests/unit/companion/test_spa.py::_asset()` globs
   `assets/*{suffix}` and **prefers** names starting `index-`, so a `space-grotesk-*.woff2`
   sibling cannot be picked up by the `.js`/`.css` assertions; `test_the_committed_bundle_has_hashed_assets`
   asserts only that js and css exist. Re-run the suite to prove it, but expect no edit.

9. **`--font-sans` must NOT change, and no token may be added.** `tests/tokens.test.ts` asserts
   `--font-sans` equals DESIGN.md's `typography.*.fontFamily` exactly
   (`'Space Grotesk', system-ui, sans-serif`), and `tests/token-usage.test.ts` asserts
   `declaredTokens.size === 64`. Keeping `system-ui` in the stack is therefore mandatory *and*
   correct — it is the safety net if the font ever 404s, not a regression.

10. **c2-4's guards pick up a new stylesheet automatically.** `shippedStylesheets` is
    `git ls-files '*.css'` minus fixtures, so a new `ui/src/styles/fonts.css` is scanned by the
    nesting, contrast, token-declaration, unknown-token and animation guards **the moment it is
    committed** — and by nothing at all until then (c2-4 hit exactly this: an untracked
    `tokens.css` made a guard vacuous until it was staged). `git add` early.

**What this story does not do.** No components (c2-6 builds the shell, c2-7 the primitives), no
layout, no state panel or copy (c2-9), no second typeface ever, no Python, no route, no runtime
dependency. It does not restyle anything: the type roles already exist and already resolve.

## Blocking dependency

**This story cannot start until PR #21 (c2-4) is merged into `feat/companion-c2`.** It builds
directly on `--font-sans`, `--type-numeric`, `--type-numeric-features`, the `overrides` entry in
`.stylelintrc.json` and five guards in `tests/token-usage.test.ts`, none of which exist on the
umbrella branch yet. Branch off the umbrella **after** the merge, and record the merge commit as
`baseline_commit`.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's five blocks imply
but do not state; each says why it exists. An AC the epic did not write down is still an AC
(standing agreement: a story must leave the system working end to end).

### The font itself

**AC 1 [epic].** **Given** the font files, **when** the build runs, **then** they are bundled
with the backend's static assets and served from the same origin (AD-13) — i.e. emitted into
`src/companion/app/static/assets/` by `npm run build`, content-hashed, and committed along with
the `plugin/` mirror.

**AC 2.** **Given** the committed binary, **when** it is inspected, **then** it is **provably a
real WOFF2** — a test asserts the file exists, is over 10 kB, and begins with the four-byte
signature `wOF2`. *Why: `core.autocrlf=true` plus a missing or mis-ordered `.gitattributes` line
corrupts a font silently, on Windows only, on a fresh clone — the exact shape of the bug c2-2
measured for `index.html` and could only find by checking bytes. A font that fails to decode
falls back to `system-ui`, which is indistinguishable from "the `@font-face` didn't apply".*

**AC 3.** **Given** the OFL-1.1 licence, **when** the font ships, **then** its licence text is
committed beside the binary and is referenced where attribution lives. *Why: OFL-1.1 requires
the licence to accompany the font. c2-10 owns footer attribution; this story owes it the file
and the fact, not the UI.*

### Offline parity

**AC 4 [epic].** **Given** the app is loaded with all external network access blocked, **when**
it renders, **then** Space Grotesk displays, not the `system-ui` fallback (UX-DR2, NFR-06).

> **This AC has a machine-verifiable half and a human half, and the story record must say
> which is which.** *Mechanical:* the binary is a real WOFF2 (AC 2), it is emitted into
> `assets/` and served with `font/woff2` (AC 1), the `@font-face` points at that emitted asset
> by a relative URL (AC 6), and nothing in the bundle reaches an external host (AC 5). Those
> four together mean there is nothing left to fetch. *Human:* **that the glyphs on screen are
> actually Space Grotesk.** jsdom does not load fonts, does not apply `@font-face`, and reports
> whatever family string it was given — a `getComputedStyle` assertion here is vacuous by
> construction, exactly like the reduced-motion trap c2-4's AC 13 exists to name. **Do not
> fake it.** Put "fonts render offline, in a browser, with the network throttled to offline"
> on the epic manual-testing checklist, as c2-2 did for its browser-render half, and say so
> plainly in the Completion Notes.

**AC 5 [epic].** **Given** the built bundle, **when** it is inspected, **then** **no `@import`
or `<link>` to a font CDN exists anywhere in it** — enforced by a real guard over the committed
`src/companion/app/static/` tree (every `.html`, `.css` and `.js`), failing on any
`http://`/`https://`/`//` reference to an external host, with `fonts.googleapis.com` and
`fonts.gstatic.com` named explicitly. Proven firing and not firing. *Landmine 4: nothing in
either lint layer catches this today, so it is new work, not a re-verification.*

**AC 6.** **Given** the `@font-face`, **when** it is authored, **then** its `src` is a
**relative** URL resolved by the bundler, never an absolute path or an origin — so the bundle
is position-independent and the hash rewriting works. Asserted by the same guard as AC 5.

### Tabular numerals (UX-DR3)

**AC 7 [epic].** **Given** any count, quantity, price or axis value renders, **when** its
computed style is inspected, **then** `font-variant-numeric: tabular-nums` is applied.

**AC 8 [epic].** **Given** the CSS `font` shorthand cannot carry `font-variant-numeric`,
**when** the numeric role is applied, **then** the role and its numeric-features property are
applied together, **and a lint rule or unit test fails on the numeric role being applied
alone.** Enforced as a co-occurrence guard over every `ui/src/**/*.css` rule block — the same
shape as c2-4's `--accent-dim` × `--surface-overlay` guard — failing on a block that sets
`font: var(--type-numeric)` without `font-variant-numeric: var(--type-numeric-features)`, with
a failure message naming the missing declaration. Proven firing and not firing.

**AC 9.** **Given** the guard in AC 8, **when** it is written, **then** it states plainly which
half it cannot see: a component that applies the role in one rule and the features in another,
or via a shared class, is **not** caught. *Why: c2-4's review found the contrast guard shipped
as "a real guard" with no mention of its equally real cross-block limit, and made documenting
that limit a patch. Do not repeat it — declare the boundary in the same breath as the guard.*

### The typography-literal ban (the family c2-4 left open)

**AC 10.** **Given** any component stylesheet, **when** stylelint inspects it, **then** a
hard-coded `font`, `font-family`, `font-size`, `font-weight`, `line-height` or `letter-spacing`
value **fails**, permitting only the role tokens (`var(--type-*)`), the family token
(`var(--font-sans)`), the tracking tokens (`var(--tracking-*)`) and the CSS-wide keywords.
*Why: this is c2-4's single deferral, homed here by its review. Typography is the last value
family a component can hard-code with nothing objecting.*

**AC 11 [epic].** **Given** any text on a dark surface, **when** its weight is inspected,
**then** it is **400 or above**, and **no second font family is introduced** (UX-DR2) —
mechanically, a consequence of AC 10: the only legal sources are seven role tokens whose
weights are 400/500/700 and one family token. State that reasoning in the record rather than
adding a redundant numeric guard, **and** prove it by asserting the role tokens' weights.

**AC 11b.** **Given** AC 10 bans font-family *values*, **when** the "one family" rule is
enforced, **then** a guard additionally confines **`@font-face` itself** to the font
stylesheet, over every `ui/src/**/*.css`. *Why this is not covered by AC 10: an `@font-face`
block does not consume a family, it **declares** one. A component shipping its own
`@font-face` introduces a second typeface while every value-level rule stays silent — the
exact shape of c2-4's "no component may declare a token", and it fails the same way for the
same reason.* Proven firing and not firing.

**AC 12.** **Given** the `@font-face` block legitimately declares `font-family`, `font-weight`
and `font-style`, **when** AC 10 is configured, **then** its exemption is a **path-scoped
`overrides` entry** naming the font stylesheet — never a `stylelint-disable` comment — and is
the narrowest that works. If it ends up wider than the font-property rules, say why in the
record. *This is c2-4's Decide-once #1 applied to a second file; the exemption list is now two
paths, and that is the moment to check it is still a list and not a habit.*

### Records and boundaries

**AC 13.** **Given** the forward-dated sentences that name this story, **when** it lands,
**then** each is repaired in the same commit (C1 retro homing rule): `.gitattributes:14`,
`src/companion/app/spa.py:76`, `spa.py:84`, `spa.py:85`, `ui/README.md:284`,
`ui/src/index.css:9`, `ui/src/styles/tokens.css:47`, `ui/src/styles/tokens.css:109`,
`ui/tests/tokens.test.ts:286`. **And** the `Story 2.5` references under
`_bmad-output/implementation-artifacts/2-*.md` and `5-*.md` are **not touched** — those are the
Epic-2 RAG and deck-power stories, different stories with colliding numbers.

**AC 14.** **Given** any CSS or asset change, **when** the story is committed, **then** the SPA
bundle is rebuilt (`cd ui && npm run build`) and the **committed bundle and its `plugin/` mirror
are both regenerated and committed** — otherwise c2-2's sync check and the `plugin/` drift check
both go red. The bundle now gains a third asset type; landmine 8 says no Python test needs
editing, so prove that rather than assume it.

**AC 15.** **Given** the dependency graph, **when** it is inspected, **then** this story adds
**no runtime dependency**. Any devDependency it adds carries a `"//"` note giving its reason and
does not trip `tests/package-contract.test.ts` — which, per c2-4's review, now enforces
`yaml`'s "tests only" rule and is the pattern any new entry follows.

**AC 16.** **Given** the scope, **when** the diff is inspected, **then** it touches no `.py`
file, no route, no component, and nothing under `src/` except the regenerated
`src/companion/app/static/` bundle and its `plugin/` mirror. `pyproject.toml` and `uv.lock` are
untouched. `ui/index.html` may be touched **only** for the preload link (Q5).

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement)
  - [x] Confirm PR #21 is merged and branch off `feat/companion-c2`; record `baseline_commit`
  - [x] `cd ui && npm test` → expect **142 passed / 12 files**; `npm run lint`,
        `npm run format:check`, `npm run typecheck`, `npm run build` all green
  - [x] Repo root: `uv run pytest -m "not integration"` → expect **1,753 passed / 1 skipped /
        45 deselected**. *If `test_list_decks_with_strategy_field` fails, it is the known
        `created_at`-tie flake — re-run before investigating (c2-4 proved it FAIL/PASS/PASS).*
  - [x] `git status --porcelain -- src/companion/app/static/ plugin/` clean **after** a build,
        so a later drift is provably yours
  - [x] Record every number in the Dev Agent Record

- [x] **Task 1 — obtain the binary, with provenance** (AC 1, 2, 3, per Q1/Q2)
  - [x] Fetch via `npm pack @fontsource-variable/space-grotesk`, extract **only** the subset
        file(s) Q2 rules on, plus `LICENSE`
  - [x] Commit under the path Q1 rules on; **`git add` immediately** (landmine 10)
  - [x] Verify the committed bytes: size, and the `wOF2` signature — *before* trusting any
        visual check

- [x] **Task 2 — the `@font-face` and the wiring** (AC 1, 4, 6)
  - [x] `ui/src/styles/fonts.css` — quoted `url('…')` (landmine 3), `font-weight: 300 700`,
        `font-display` per Q3, `unicode-range` per Q2
  - [x] Import it from `index.css` **above** the token import, both before any other rule
  - [x] `npm run build`; **inspect the emitted CSS and `assets/`** to confirm the font was
        hashed into `assets/` and the URL rewritten (landmine 7)

- [x] **Task 3 — the offline guard** (AC 5, 6)
  - [x] Guard over every file in the committed `static/` tree failing on an external reference,
        naming the two Google Fonts hosts explicitly
  - [x] Non-vacuity anchor first: assert the tree was found and is populated
  - [x] Proven both ways — plant a CDN reference in a fixture, not in the real bundle

- [x] **Task 4 — the numeric-pairing guard** (AC 7, 8, 9)
  - [x] Co-occurrence guard in `tests/token-usage.test.ts`, message naming the missing
        declaration; proven firing and not firing
  - [x] Comment stating the cross-block half it cannot see (AC 9)

- [x] **Task 5 — the typography-literal ban** (AC 10, 11, 11b, 12)
  - [x] `.stylelintrc.json`: the six properties, allowed-list keyed to the token families
  - [x] Extend the `overrides` entry to the font stylesheet, narrowest form
  - [x] Assert the role tokens' weights are 400/500/700 (AC 11's proof)
  - [x] Guard confining `@font-face` to the font stylesheet (AC 11b), proven both ways
  - [x] Proven pairs in `clean.css` / a new violation fixture, **by rule name and count**

- [x] **Task 6 — records and the forward-dated sentences** (AC 13)
  - [x] Repair all nine (**ten** — one the story did not list); leave the Epic-2/deck-power
        `Story 2.5` references alone
  - [x] `ui/README.md`: the font section, the second exemption, the offline guard

- [x] **Task 7 — rebuild, mirror, prove** (AC 14, 15, 16)
  - [x] `npm run build`; `uv run python -m scripts.build_plugin`; commit both
  - [x] Re-run all five frontend gates and the Python suite (expect no Python edit — landmine 8)
  - [x] Scope proof: `git diff --stat` shows no `.py`, no `pyproject.toml`, no `uv.lock`
  - [x] `git status --porcelain` clean — no stray `.tgz` or unpacked tarball (gotcha 12)
  - [x] Add "fonts render offline, in a browser, network throttled to offline" to the epic
        manual-testing checklist, and state in Completion Notes that AC 4's render half is
        **not** dev-verified (the c2-2 precedent)

- [x] **Task 8 — probe the evasions before claiming done**
  - [x] For each new guard, plant the evasion, confirm it is caught, revert, paste the output
  - [x] **Verify the mutation landed before believing the verdict**, and **read what landed on
        disk** — c2-4's nesting probe planted flat CSS and the guard was right to stay silent
  - [x] **Ban the family, never enumerate members** — see Gotcha 6

### Review Findings

Adversarial review 2026-07-28 (Blind Hunter + Edge Case Hunter + Acceptance Auditor, triaged):
1 decision-needed, 14 patch, 2 defer, 0 dismissed. The review theme, one more time: **the one
exempted thing is where the next evasion lives** — the carve-out property, the exempted file,
the allowed namespace each turned out to admit exactly the class they were carved out to manage.

**All 15 patches applied 2026-07-28** (the decision resolved to a patch — Brad ruled extend).
After the round: frontend **173 passed / 13 files** (was 172 — one net new test), Python
**1,753 passed** unchanged, all five gates exit 0, bundle rebuilt byte-identical (every CSS
edit was comment-only, and Vite strips comments). The typography fixture now proves **25**
violations by rule name and count (was 19); the base allowed-list has **six** typography keys
(was four) and the fonts.css override carries its own message and a drift guard updated to
base-minus-six.

- [x] [Review][Decision] **`word-spacing` (and `text-indent`) escape the typography-literal
  ban** — Q4 ruled the six properties plus their longhands; these are siblings, not longhands,
  so no rule keys them and `word-spacing: 0.5em` lints clean everywhere. Extending the ban is
  cheap and matches "ban the family", but it widens a Brad ruling, so it is Brad's call:
  (a) extend the catch-all to cover them (allowed: `0` + CSS-wide keywords — no token governs
  them), or (b) record them as out-of-scope residue in deferred-work.md.
  **RESOLVED — Brad ruled (a), extend the ban (2026-07-28).** Applied with the patch round:
  `word-spacing`/`text-indent` share a key with `line-height`, proven both ways in the fixture
  and in `clean.css` (`0` stays legal).
- [x] [Review][Patch] **`font: var(--type-numeric-features)` lints clean and renders as
  nothing** — the `/^font$/` allowed regex admits the whole `--type-*` namespace, and this
  member resolves to `tabular-nums`, an invalid `font` shorthand that is discarded; the pairing
  guard's role regex deliberately excludes it and the unknown-token guard is silent because the
  token exists. The story's own review theme, alive in its newest rule. [ui/.stylelintrc.json:46]
- [x] [Review][Patch] **A standalone `font-variant-numeric` literal is invisible to both
  layers, and the recorded justification overclaims** — the lookahead carves the property out of
  stylelint entirely, and `findUnpairedNumericRole` only inspects blocks containing the role, so
  `.foo { font-variant-numeric: oldstyle-nums; }` in a role-less block passes everything while
  the lint-gates comment asserts that hole does not exist. Give the property its own allowed-list
  entry (`var(--type-numeric-features)` + CSS-wide keywords) and correct the three comments.
  [ui/.stylelintrc.json:54, ui/tests/lint-gates.test.ts]
- [x] [Review][Patch] **A second `@font-face` inside fonts.css itself is caught by nothing** —
  `findStrayFontFaces` filters the file out, the presence assertion is `toContain` (≥1, not
  ==1), the family test asserts presence not exclusivity, and the stylelint override exempts the
  file from the family rules. "One family, forever" needs: exactly one `@font-face` in
  fonts.css, and every `font-family:` in it is 'Space Grotesk'. [ui/tests/fonts.test.ts:185,217]
- [x] [Review][Patch] **`src:` extraction is first-match on the unstripped file** — a future
  comment containing an example `src: url(…)` shadows the real descriptor, and a second `src:`
  descriptor is never validated. Strip comments, `matchAll`, assert exactly one, validate all.
  [ui/tests/fonts.test.ts:112]
- [x] [Review][Patch] **JSON-escaped URLs (`https:\/\/host`) are invisible to all four bundle
  rules** — the spelling JSON-serialised strings in a minified bundle genuinely use contains no
  consecutive slashes; IPv6-literal hosts also fail the host class. Normalise `\/` before
  matching and disclose the IPv6 residue. [ui/tests/fonts.test.ts:316]
- [x] [Review][Patch] **Base64 `data:` URIs will false-trigger the URL matcher** — the first
  asset Vite inlines (default `assetsInlineLimit` 4096 B) puts base64 containing `//` into the
  emitted CSS, and R1's total ban fires on a garbage host. Fails red (safe), but the guard's own
  header says a guard that fires on clean input is one someone switches off. Strip `data:` spans
  before matching. [ui/tests/fonts.test.ts:316]
- [x] [Review][Patch] **Unknown binary types in the bundle are utf8-decoded and regex-scanned**
  — `isBinary` is a fixed extension list, so a future `.wasm`/`.mp3`/`.pdf` member is read as
  mojibake and scanned. Make classification exhaustive: known-text read, known-binary listed,
  unknown extension fails with "classify me". [ui/tests/fonts.test.ts:386]
- [x] [Review][Patch] **`crossorigin="use-credentials"` satisfies the preload assertion while
  defeating it** — `toMatch(/crossorigin/)` pins presence, not mode; font fetches are
  anonymous-mode, so a credentialed preload downloads the file twice — the exact failure the
  comment says it prevents. Pin the bare/`anonymous` form. [ui/tests/fonts.test.ts:438]
- [x] [Review][Patch] **`0` is allowed for every `font-*` longhand, and the catch-all lookahead
  carries two dead alternatives** — `font-weight: 0` / `font-stretch: 0` are invalid CSS that
  lints clean (the theme again); `0` is only valid for `line-height`. And `font$` /
  `letter-spacing$` in the lookahead can never match the body `(font-[a-z-]+|line-height)$`, so
  they misdescribe the mechanics. Split `line-height` out with `0`; drop `0` and the dead
  alternatives from the catch-all. [ui/.stylelintrc.json:54-55]
- [x] [Review][Patch] **The unicode-range ".notdef boxes" rationale is factually wrong, in
  three places** — per CSS font matching, a character inside the range but absent from the cmap
  falls back to the next family per-glyph; a too-wide range affects download/use triggering, not
  glyph fallback. The decision (copy verbatim) is right; the recorded reason misteaches.
  [ui/src/styles/fonts.css:36-38, ui/tests/fonts.test.ts:134-136, ui/README.md]
- [x] [Review][Patch] **The "fonts first" @import ordering rationale is wrong** — `@font-face`
  registration is order-independent in the CSSOM; both imports merely need to precede every
  rule. Stated as load-bearing, it invites a wrong "fix" later. [ui/src/index.css:16-19]
- [x] [Review][Patch] **README ban-table row overstates the offline guard** — "any URL to
  another origin in the built bundle | a guard" is false as written: R4 permits the reviewed
  hosts (`www.w3.org`, `react.dev`). The prose gets it right; the table row is the part people
  quote. [ui/README.md]
- [x] [Review][Patch] **The fonts.css override drops the guiding message for the seven restated
  families** — a spacing/shadow violation inside fonts.css reports stylelint's default text
  instead of the token-family guidance every other file gets. [ui/.stylelintrc.json:91-113]
- [x] [Review][Patch] **AC 11's weight proof relocated without a record** — the story's
  source-tree table homed it in `tokens.test.ts`; it shipped in `fonts.test.ts` (correctly), and
  the Completion Notes' divergence list does not mention the move. One sentence in the record.
  [this file, Completion Notes]
- [x] [Review][Defer] **`git ls-files`-keyed guards cannot see untracked stylesheets**
  [ui/tests/fonts.test.ts:199, ui/tests/token-usage.test.ts:45] — deferred: deliberate,
  comment-owned trade-off inherited from c2-4's `shippedStylesheets` pattern; widening every
  such guard with `--others --exclude-standard` is a one-sweep decision across the suite, not a
  c2-5 patch.
- [x] [Review][Defer] **`:root { font: var(--type-body) }` pins the rem basis to 14px and
  overrides the browser's default-font-size preference** [ui/src/index.css:29] — deferred:
  consequence of the design system being px-based (DESIGN.md), not of this story; the 14px
  change itself is recorded in Completion Notes and nothing in `ui/` uses `rem` today. Belongs
  to any future accessibility/rem pass.

## Dev Notes

### Decide-once rulings this story sets (c2-6 … c2-10, c4, c6, c7 inherit)

1. **One family, forever.** No second typeface is introduced by any later story. The seven role
   tokens are the only way to set type.
2. **The numeric role never travels alone.** `font: var(--type-numeric)` without
   `font-variant-numeric: var(--type-numeric-features)` is a defect, in the same rule block.
3. **The font stylesheet joins the token file as an exempt path** — and that list stays a list
   of two named paths, not a growing habit.

### The one thing c2-4 handed to this story

c2-4's review deferred exactly one item here, and `deferred-work.md` carries it: *"Typography
literals are the ungated family in the 'every value is a token' set. The c2-4 literal bans cover
colour/shadow/radius/spacing, but no rule keys `font`, `font-size`, `font-weight`, `line-height`
or `letter-spacing`."* AC 10 is that deferral. Closing it makes the "every value is a token"
claim true for the first time.

### Previous story intelligence (c2-4, PR #21, 5/5 at Greptile round 3)

- **The review theme ran through every round: _a value that lints clean and renders as
  nothing_.** Four instances — a wrong-family token (`padding: var(--radius-pill)`),
  `padding: auto`, a non-motion `var()` in a `transition`, and a literal hidden in
  `min()`/`max()`/`clamp()`. **This story's equivalents exist**: `font-weight: var(--space-1)`
  is the same wrong-family shape, and `font: var(--type-numeric)` alone renders *proportional*
  digits — visibly wrong rather than absent, which is harder to notice, not easier.
- **The fix shape that generalises: ban the family, never enumerate members** — and prove it
  with an *invented* member so the test is a family test rather than an enumeration test.
  c2-4 learned this twice: once as landmine 5 (regex property keys), then had to learn it again
  when `calc(` was banned and `min`/`max`/`clamp` walked through.
- **Value regexes must be keyed to the category prefix.** `var(--space-1)` in a `font-weight`
  is invalid CSS that renders as nothing, and the unknown-token guard cannot catch it because
  the token exists. Key AC 10's allowed-list to `--type-*`/`--font-*`/`--tracking-*`.
- **Every guard gets a proven pair from one invocation, asserted by rule name and count.**
- **Declare a guard's blind spot in the same breath as the guard** (AC 9).
- All five of c2-4's open questions were answered "as proposed" before Task 0, and nothing
  surfaced mid-story — the third story running to hold that. The five below are written to be
  answerable in one pass for the same reason.

### Git intelligence

The last nine commits are all c2-4, in the house shape: **implementation → records → review
patches (message names the theme) → records → …**. Conventional Commits, scope `companion`.
Branch off `feat/companion-c2` as `feat/companion-c2-5-space-grotesk`; the story PR targets the
umbrella with a Greptile pass (the per-epic integration PR gets none — standing rule).

Worth copying from c2-4's review rounds: when a patch **invalidates an earlier proof**, replace
the proof rather than re-assert it. (Adding the duration ban made stylelint fire on
`animation: pulse 2s 3` for the `2s`, so the "stylelint is silent on the count" claim would have
kept passing for the wrong reason.)

### Source tree — what exists, what this story adds

```
ui/
  .stylelintrc.json          UPDATE  + the six font-property rules; overrides gains fonts.css
  README.md                  UPDATE  font section; repair line 284
  index.html                 UPDATE? preload link only, per Q5
  src/
    assets/fonts/            NEW?    the .woff2 + LICENSE (path per Q1)
    styles/
      fonts.css              NEW     the @font-face, and nothing else
    index.css                UPDATE  import fonts.css first; repair line 9
    styles/tokens.css        UPDATE  repair the two forward-dated comments (comments only —
                                     NO token changes, landmine 9)
  tests/
    fonts.test.ts            NEW     binary integrity (wOF2), offline guard, @font-face shape
    token-usage.test.ts      UPDATE  the numeric-pairing guard
    lint-gates.test.ts       UPDATE  a proven pair per new rule
    tokens.test.ts           UPDATE  role-weight assertion (AC 11); repair line 286
    fixtures/css/…           UPDATE  typography violations + the legal forms
src/companion/app/spa.py     UPDATE  comments only — repair the three c2-5 markers
.gitattributes               UPDATE  comment only — repair line 14; consider `*.woff` (landmine 5)
src/companion/app/static/    REGENERATED
plugin/…/static/             REGENERATED
```

Nothing else. No `.py` logic, no route, no component.

### Gotchas specific to this story

1. **Quote the `url()`** (landmine 3). One measured error, trivially avoided, and the only
   thing standing between a correct `@font-face` and a red gate.

2. **`git add` the font before running the guards** (landmine 10). `shippedStylesheets` and any
   `git ls-files`-based guard cannot see an untracked file, so a font-integrity test written
   against an untracked binary passes vacuously. c2-4 hit this exact trap with `tokens.css`.

3. **Check the bytes, not the render.** A corrupted font and an unapplied `@font-face` look
   identical in a browser — both show `system-ui`. AC 2's `wOF2` signature check distinguishes
   them, and is the first thing to run when the font "doesn't work".

4. **`preload` needs `crossorigin` even same-origin.** Font fetches are always CORS-mode, so a
   `<link rel="preload" as="font">` without `crossorigin` causes the browser to download the
   file **twice** — once for the preload, once for the real request. If Q5 lands, get this
   right or the optimisation is a pessimisation.

5. **Do not touch `--font-sans`, and do not add a token** (landmine 9). Two existing assertions
   pin them. If a change feels necessary, that is a signal to re-read, not to edit the test.

6. **Ban the family, not the member.** The single most expensive lesson of c2-4, learned twice.
   For AC 10 that means: key on a property-name regex covering all six properties *and their
   longhands* (`font-size-adjust`, `font-stretch`, `font-optical-sizing`… and note `font` is a
   shorthand that carries five of them at once), and prove the ban with a property the test did
   not enumerate.

7. **A CSS `@import` must precede every other rule.** `index.css` already opens with a comment
   then `@import url('./styles/tokens.css')`. The font import goes *beside* it, above the
   `:root` block — two imports, both before any rule, or the browser drops the second.

8. **`Story 2.5` under `_bmad-output/implementation-artifacts/2-*.md` and `5-*.md` is a
   different story** (AC 13) — Epic-2 RAG (`find_similar_cards`) and deck-power both share the
   number. Repair only the nine `c2-5` sentences listed.

9. **The bundle gains a third asset type.** Expect `test_spa.py` to stay green untouched
   (landmine 8) — but the mirror parity test compares asset **bytes**, so the font must survive
   the `plugin/` copy identically. The root `.gitattributes` already covers both trees.

10. **`npm run build` is the only thing that regenerates the bundle** — the pre-commit hook
    mirrors `src/` into `plugin/` but never rebuilds from `ui/`.

11. **Copy the `unicode-range` from the package, never invent it.** `@fontsource-variable`'s
    own `index.css`/`wght.css` carry the exact range each subset file contains. A range wider
    than the file's real coverage makes the browser *stop falling back* for characters the font
    does not have — the result is `.notdef` boxes rather than a graceful `system-ui`
    substitution, which is worse than having no `unicode-range` at all.

12. **Extract the tarball outside `ui/`.** `npm pack` drops a `.tgz` in the working directory,
    and anything left in `ui/` is a candidate for accidental commit — c2-4 lost a cycle to
    exactly this when a scratch `.mjs` file tripped `gate-geometry.test.ts`'s extension ban.
    Unpack in the scratchpad, copy the two files you want, and leave nothing behind. The
    `git status --porcelain` check at the end of Task 7 is what catches it if you do.

13. **`ui/public/` is not wrong, it is wrong *for this*.** The favicon legitimately lives there
    because it needs a stable, unhashed URL that `index.html` can name. A font needs the
    opposite: a content hash, so it can be cached immutably for a year (landmine 7). Do not
    read "fonts go in assets" as "public/ was a mistake".

### Testing standards

- vitest, two projects: new gate/guard tests are **node**-project tests under `ui/tests/`.
  A `.test.tsx` under `tests/` is banned by `gate-geometry.test.ts`.
- **Every new lint rule gets a proven pair** from one invocation, asserted by **rule name and
  count**, per fixture file (never in aggregate — that is what keeps c2-1's ten-warning outline
  count and c2-4's counts independent of each other).
- **Non-vacuity anchor first** in any test that filters a list.
- Fixtures live in `tests/fixtures/`, are excluded from `npm run lint` by CLI
  `--ignore-pattern`, and are meant to stay broken.
- Python side: no new tests; re-run the suite to prove landmine 8.

### Architecture rules this story implements

- **UX-DR2** — self-host, no CDN, one family, weight ≥ 400.
- **UX-DR3** — tabular numerals, and the pairing rule that makes them real.
- **NFR-06** — renders identically offline.
- **AD-13** — the build output is a committed artefact; a font is a bundle change.
- **NFR-07** — the frontend gates are the enforcement mechanism.
- **FR-20** — the visual identity; this story finishes the type half of it.

### References

- [epics-companion-app.md#Story-2.5](_bmad-output/planning-artifacts/epics-companion-app.md) —
  the five AC blocks (lines 1345-1373)
- [epics-companion-app.md#UX-DR2..3](_bmad-output/planning-artifacts/epics-companion-app.md) —
  self-hosting and tabular numerals (lines 343-349)
- [DESIGN.md frontmatter](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  — the seven type roles and their weights (400/500/700), lines 43-86
- [\_ds/tokens/fonts.css](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/_ds/tokens/fonts.css)
  — the CDN `@import` and its "no binaries were provided" note; **the thing this story replaces**
- [c2-4 story record](_bmad-output/implementation-artifacts/c2-4-the-voltglass-token-layer.md) —
  the token layer, its five guards, the review theme, and the deferral this story closes
- [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — the c2-4 entry
  homing typography literals here
- [ui/README.md#The-token-layer](ui/README.md) — the gate table this story extends
- [src/companion/app/spa.py](src/companion/app/spa.py) — the mimetype registration and the
  `assets/`-keyed cache policy
- [epic-c1-retro-2026-07-26.md](_bmad-output/implementation-artifacts/epic-c1-retro-2026-07-26.md)
  — forward-dated-comment homing, open-question homing, non-vacuity pairing

## Open questions for Brad — answer before `dev-story`

Each carries a recommendation; "as proposed" on all five is a complete answer.

**Q1 — how is the binary obtained, and does it get committed?** *Recommendation:* run
`npm pack @fontsource-variable/space-grotesk`, extract **only** the subset `.woff2` and the
`LICENSE`, and **commit both under `ui/src/assets/fonts/`** — no dependency added, the font
referenced by a relative `url()` from `fonts.css`, and Vite hashes it into `assets/`. The
alternative (add `@fontsource-variable/space-grotesk` as a devDependency and import its CSS)
pulls latin-ext and vietnamese into the build unless overridden, puts a `node_modules` path in
the build graph for one 22 kB binary, and makes an offline `npm ci` a prerequisite for a font
we have already chosen. Committing it matches the repo's existing posture — the SPA bundle is a
committed artefact for the same reason.

**Q2 — which subsets, and is `unicode-range` declared?** *Recommendation:* **latin only**
(22.3 kB), **with** its `unicode-range` declared. Latin-1 covers the diacritics that actually
appear in card names (Æ, é, û, ö), and declaring the range means an out-of-range glyph falls
back to `system-ui` for that character instead of rendering `.notdef` boxes. Adding latin-ext
costs 18.9 kB — nearly doubling the font payload — for glyphs an English card database does not
use. If a real card name turns up broken later, adding a second `@font-face` is a one-file change.

**Q3 — `font-display`?** *Recommendation:* **`swap`, plus the preload in Q5.** UX-DR2 calls a
`system-ui` fallback a visible regression, which argues for `block` — but `block` renders
*invisible text* for up to 3 s if anything goes wrong, and a same-origin 22 kB font on localhost
arrives in single-digit milliseconds. `swap` + preload collapses the flash to nothing in the
normal case and degrades to readable text in the abnormal one. `optional` is the third option
and is wrong here: it permits the browser to skip the font entirely on a slow connection, which
is precisely the regression UX-DR2 names.

**Q4 — how far does the typography-literal ban reach?** *Recommendation:* the six properties in
AC 10, keyed by a **family regex** covering their longhands, allowing only `var(--type-*)`,
`var(--font-sans)`, `var(--tracking-*)`, `0`, and the CSS-wide keywords — and **not** extending
to `font-variant-numeric`, whose only legal value (`var(--type-numeric-features)`) is already
implied by AC 8's pairing guard. Treat `line-height` as in scope even though it is not strictly
typography-only: it is carried by every role token, so a literal there is drift by the same
argument as the rest.

**Q5 — does this story own the preload link in `ui/index.html`?** *Recommendation:* **yes** —
one `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the single subset file.
It is the difference between the flash Q3 accepts and no flash at all, it is three lines, and
the alternative is a c2-6 story touching `index.html` for a reason that belongs to this one.
Note the file is Vite's *source* template, so the href must be the built asset path — if that
proves awkward to express, say so in the record and drop the preload rather than hard-coding a
hash that the next build invalidates.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

**Task 0 — baseline at `ff39129`** (the PR #21 merge commit; branch `feat/companion-c2-5-space-grotesk`
off the umbrella). Every number matched the story's prediction exactly:

| Gate | Result |
| --- | --- |
| `npm test` | **142 passed / 12 files** |
| `npm run lint` / `format:check` / `typecheck` / `build` | all exit 0 |
| `uv run pytest -m "not integration"` | **1,753 passed / 1 skipped / 45 deselected** |
| `git status --porcelain -- src/companion/app/static/ plugin/` after a build | clean |
| `core.autocrlf` | `true` (so the binary attribute is load-bearing, as landmine 5 said) |

The known `test_list_decks_with_strategy_field` flake did not appear in any of the three full
Python runs.

**Task 1 — the binary, measured rather than assumed.** `npm pack
@fontsource-variable/space-grotesk@5.3.0` in the scratchpad produced exactly the story's
inventory: `space-grotesk-latin-wght-normal.woff2` at **22,288 bytes**, latin-ext at 18,940,
vietnamese at 6,712, `LICENSE` at 4,401. Only the latin subset and the licence were copied in.
Staged immediately (landmine 10); `git cat-file -p :<path> | wc -c` → 22288 and the first four
bytes are `wOF2`. `git check-attr text diff` → `text: unset`, `diff: unset`.

**Task 2 — the build.** The font is emitted as
`assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2` (22.28 kB), the emitted CSS carries
`src:url(/assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2)format("woff2")`, and — the Q5
question — Vite **did** rewrite the `index.html` preload `href` from the source path to that same
hashed URL, and emitted the file **once** rather than twice. So the preload landed as
recommended; no hash was hard-coded and none had to be.

**Task 8 — seven evasion probes, each verified on disk before the verdict was believed.**

| # | Mutation (verified present) | Result |
| --- | --- | --- |
| 1 | first 4 bytes → `wOFF` | `is a real WOFF2` FAILS — `Received: "wOFF"` |
| 2 | comment out `*.woff2 binary` | `check-attr` → `text: auto`; `declared binary to git` FAILS |
| 3 | `@font-face { font-family: 'Comic Sans MS'; … }` appended to `src/App.css` | confinement guard FAILS **and** stylelint reports the family literal — two independent layers |
| 4 | `.count-column { font: var(--type-numeric); }` in `App.css` | pairing guard FAILS; stylelint correctly silent (the value is legal, the pairing is the guard's job) |
| 5 | `font-size: 15px; font-stretch: 87.5%` in `App.css` | stylelint reports **2** errors — including the longhand nobody enumerated |
| 6 | added `/^opacity$/i` to the base allowed-list only | override-drift guard FAILS: *"the fonts.css override has drifted"* (base 12 keys, override 7) |
| 7 | real Google Fonts `@import` in `src/index.css`, then `npm run build` | **`npx stylelint src/index.css` exits 0** — landmine 4 confirmed end to end — and the offline guard on the rebuilt bundle FAILS |

Probe 7 is the one worth keeping: it proves both halves of the story's fourth landmine in one
pass — that nothing in either lint layer objects to a CDN import, and that the new guard is the
only thing standing between the design system's own `fonts.css` and the shipped bundle. Every
mutation was reverted and the bundle rebuilt; `git diff` over `src/companion/app/static/` and
`plugin/` is empty afterwards.

**Final gates.** Frontend **172 passed / 13 files** (was 142/12 — 30 new tests). Python
**1,753 passed / 1 skipped / 45 deselected**, byte-for-byte the baseline number: landmine 8 held
and **no Python test needed editing**. `lint`, `format:check`, `typecheck`, `build` all exit 0.
`git status --porcelain` shows no untracked file — no `.tgz`, no unpacked tarball (gotcha 12; the
tarball was unpacked in the scratchpad and never entered `ui/`).

### Completion Notes List

**AC 4's render half is NOT dev-verified, and that is deliberate.** Everything mechanical is
closed — the binary is a real WOFF2 by signature, exact length and WOFF2 header; git resolves it
as binary so a Windows checkout cannot normalise it; it is emitted content-hashed into `assets/`
and served `font/woff2`; the `@font-face` reaches it by a relative url; nothing in the bundle
names another origin. **What no test here can prove is that the glyphs on screen are Space
Grotesk.** jsdom does not load fonts and does not apply `@font-face`; a `getComputedStyle`
assertion would pass identically on a correct font, a corrupt font and a 404, which is the exact
vacuity trap c2-4's AC 13 exists to name. That check is a browser with the network throttled to
offline, and it is now on the epic manual-testing checklist via `deferred-work.md` — the same
split c2-2 took for its own browser-render half.

**Three things diverged from the story as written, all deliberate:**

1. **The offline guard could not be "fail on any external URL", because the clean bundle already
   contains external URLs.** Measured: React's DOM code carries `http://www.w3.org/…` namespace
   identifiers (arguments to `createElementNS`) and a `https://react.dev/errors/` error-string
   base, and `favicon.svg` carries an SVG `xmlns`. AC 5's literal wording would be **red on a
   correct bundle**. So the rule is split by what each file type can actually do: `.css` and
   `.html` get a **total** ban (which is where a font CDN reference can actually live, and where
   AC 5's wording holds exactly); every file gets a font-CDN **host-family** ban and a fetchable
   **asset-extension** ban; and the remaining external hosts are compared against a reviewed
   baseline, so a dependency that starts phoning home turns the test red. The two Google hosts
   are asserted by name as AC 5 requires. Cost and blind spot are both recorded in
   `deferred-work.md`.
2. **AC 9's predicted blind spot was the wrong way round.** The story expected a split pair (role
   in one rule, features in another) to read as clean. Measured, the guard **reports** it — it is
   block-local, so a split pair is a false *failure*, not a false pass, and that is the safe
   direction and exactly the decide-once ruling ("in the same rule block"). The **real** blind
   spot is the cascade: `.is-compact { font-variant-numeric: normal; }` undoing a correct pair on
   the same element is invisible, because that block sets no `font` and so is never examined. The
   guard, the README and `deferred-work.md` all state the measured limit rather than the
   predicted one, and it is asserted as a deliberate blind spot so it fails loudly if the guard
   ever grows a cross-block reader.
3. **AC 12's exemption is the base map minus its four typography keys, not a `null`.** A
   stylelint override *replaces* a rule's whole option object rather than merging into it, so
   nulling `declaration-property-value-allowed-list` for `fonts.css` would also have switched off
   the shadow, radius, spacing, gap and duration bans there — much wider than "the font-property
   rules". Restating the other seven entries is the genuinely narrowest form, and its one real
   risk (a family added to the base rule later and not carried across) is closed *mechanically*:
   `tests/lint-gates.test.ts` asserts the override equals the base map minus exactly its four
   type keys, and probe 6 shows that assertion firing. The exemption list is still **two named
   paths**, and the test asserts that too — a third entry is a decision, not a detail.

**Two scope notes.**

- **`index.css` gained a real change, not just a comment.** `:root` was `font-family:
  var(--font-sans); line-height: 1.5;` — and `line-height: 1.5` was the last untokenised
  typography value in the shipped CSS, so it had to go for AC 10 to be true. It is now
  `font: var(--type-body)`, the role token that carries family, size, weight and line-height
  together. **This changes the document base size from the browser default 16px to DESIGN.md's
  14px body role** — a visible change, and the correct one: 14px is what the contract says body
  text is, and every later component inherits it. Verified safe for spacing: nothing in `ui/`
  uses `rem`, so no length depends on the root font size.
- **Two `.py` files are touched, comment-only, against AC 16's blanket "no `.py`".** AC 13 names
  `spa.py:76/84/85` explicitly and the story's own source-tree table says `spa.py UPDATE comments
  only`, so AC 13 is the more specific instruction and wins. `tests/unit/companion/test_spa.py`
  is a **tenth** forward-dated sentence the story's list of nine missed (`# c2-5 ships fonts into
  this same directory`); the C1-retro homing rule says repair it, so it is repaired. Both diffs
  are comments. No route, no component, no logic, and `pyproject.toml`/`uv.lock` are untouched
  (AC 15: **no dependency added, runtime or dev** — `package.json` and `package-lock.json` are
  not in the diff at all).

**One relocation the divergence list above missed (added at review):** AC 11's role-weight
proof was planned for `tokens.test.ts` (the story's source-tree table) and shipped in
`fonts.test.ts` (`proves the role tokens hold only weights 400, 500 and 700`), beside the
axis assertion it depends on; `tokens.test.ts` received the comment-only repair. The proof
itself is complete — this line exists because the move went unrecorded.

**One thing widened beyond the ask, cheaply.** `ui/.gitattributes` gained `*.woff`, `*.ttf` and
`*.otf` beside the existing `*.woff2` (landmine 5 flagged `.woff` as missing). Only `.woff2`
ships, but the cost of listing the family is nothing and the cost of a later story adding a
fallback subset without remembering the line is a corruption **CI cannot see** — CI is ubuntu,
where `core.autocrlf` is off. Same reasoning `spa.py` already uses for registering `.woff`.

**Decide-once rulings this story sets** (c2-6 … c2-10, c4, c6, c7 inherit) — all three hold as
written: one family forever (enforced by the `@font-face` confinement guard, not convention);
the numeric role never travels alone *in the same rule block*; and the exempt-path list is two
named paths, asserted.

### File List

**New**

- `ui/src/assets/fonts/space-grotesk-latin-wght-normal.woff2` (22,288 bytes, `wOF2`)
- `ui/src/assets/fonts/LICENSE-OFL-1.1.txt`
- `ui/src/styles/fonts.css`
- `ui/tests/fonts.test.ts`
- `ui/tests/fixtures/css/typography-violation.css`
- `ui/tests/fixtures/css/font-cdn-violation.css`

**Modified**

- `ui/.stylelintrc.json` — four typography entries; the `fonts.css` `overrides` entry
- `ui/.gitattributes` — the font family declared binary, with its reason
- `ui/index.html` — the preload link (Q5)
- `ui/src/index.css` — the `fonts.css` import; `:root` now uses `font: var(--type-body)`
- `ui/src/styles/tokens.css` — comments only (two forward-dated sentences repaired)
- `ui/tests/token-usage.test.ts` — `findUnpairedNumericRole` and its four proofs
- `ui/tests/lint-gates.test.ts` — the typography-ban, family-ban, override and drift proofs
- `ui/tests/tokens.test.ts` — comment only (one forward-dated sentence repaired)
- `ui/tests/fixtures/css/clean.css` — four legal typography shapes
- `ui/tests/fixtures/css/token-usage-violation.css` — four unpaired-numeric shapes
- `ui/README.md` — the gate table, the two exemptions, and a new *typeface is self-hosted* section
- `.gitattributes` — comment only (forward-dated sentence repaired)
- `src/companion/app/spa.py` — comments only (three forward-dated markers repaired)
- `tests/unit/companion/test_spa.py` — comment only (the tenth forward-dated sentence)
- `_bmad-output/implementation-artifacts/deferred-work.md` — c2-4's deferral closed; three new
  entries incl. the manual-testing item
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status tracking

**Regenerated**

- `src/companion/app/static/**` — bundle, now carrying the hashed `.woff2`
- `plugin/server/src/companion/app/static/**` — the mirror (font bytes verified identical)
- `plugin/server/src/companion/app/spa.py` — mirror of the comment repair

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-07-28 | 1.2 | PR #22 GREEN — Greptile 5/5 at round 1 (the first story this epic to clear in one round), merged into `feat/companion-c2` at `502a646`. | Brad + Claude Fable 5 |
| 2026-07-28 | 1.1 | Adversarial code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): 1 decision, 14 patches, 2 defers, 0 dismissed. Theme: *the one exempted thing is where the next evasion lives* — `font: var(--type-numeric-features)` passed the namespace-wide `font` rule; a standalone `font-variant-numeric` literal passed both layers through its carve-out; a second `@font-face` inside the one exempted file was caught by nothing. All 15 patches applied (Brad ruled the word-spacing/text-indent extension in): six typography keys in the base allowed-list, `font-variant-numeric` admits only its token, fonts.css pinned to one face/one family, offline guard normalises JSON-escaped URLs and strips data: URIs, exhaustive bundle-member classification, crossorigin mode pinned, two wrong rationale comments corrected (unicode-range, @import order), README/table fixes, override message restored. Two defers to deferred-work.md (ls-files window; rem-basis/px design). Frontend 173, Python 1,753, bundle byte-identical. Status → done. | Claude Fable 5 (code review) |
| 2026-07-28 | 1.0 | Implemented. All five open questions answered "as proposed" before Task 0. 22,288-byte variable latin subset committed with its OFL licence; one `@font-face` in `src/styles/fonts.css`; preload in `index.html` (Vite rewrote the source href to the hashed asset, emitting the font once). Four new gate families: the offline guard over the committed bundle, the numeric-pairing guard, the typography-literal ban (family regex, four token-keyed entries), and the `@font-face` confinement guard. Suites 172 frontend (was 142) / 1,753 Python (unchanged — landmine 8 held, no Python test edited). Three deliberate divergences recorded in Completion Notes: the offline guard had to split by file type because a clean bundle already contains w3.org and react.dev URLs; AC 9's predicted blind spot was the wrong way round (measured: the guard is block-local, so a split pair is a false failure — the real blind spot is the cascade); AC 12's exemption is the base map minus its four type keys, with a drift guard, because a stylelint override replaces rather than merges. Ten forward-dated sentences repaired, not nine. AC 4's browser-render half deferred to the epic manual-testing checklist (c2-2 precedent). | Amelia (Dev) |
| 2026-07-27 | 0.1 | Story contexted from epic + DESIGN.md + the imported design system. Ten landmines measured at `c4ddd68` — notably that no font binary exists in the repo at all and the import points at a CDN, that the variable font is 5.6× smaller than the static set (22.3 kB latin, one file, covers 400/500/700), that `function-url-quotes` rejects the obvious `@font-face`, and that NOTHING currently catches a CDN `@import`. 17 ACs, 12 beyond the epic's five blocks; five open questions homed with recommendations. AC 4 split into its machine-verifiable and human halves rather than implied (the c2-2 browser-render precedent); AC 11b added because `@font-face` DECLARES a family and so escapes every value-level rule. Closes c2-4's single deferral (typography literals). BLOCKED on PR #21 merging. | Bob (SM) |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

PR #22 MERGED at 502a646 -- Greptile 5/5 at ROUND 1, first one-round clear of the epic; review PASSED 2026-07-28 (1 decision + 14 patches, all applied; theme: the one exempted thing is where the next evasion lives — the fvn carve-out, the exempted fonts.css and the --type-* namespace each admitted the class they were carved out to manage; Brad ruled word-spacing/text-indent INTO the ban; 2 defers to deferred-work.md; suites 173/1,753, bundle byte-identical); implemented 2026-07-28 off ff39129; 22,288-byte variable subset + OFL licence committed, one @font-face, preload rewritten by Vite; 4 new gate families (offline guard, numeric pairing, typography-literal ban, @font-face confinement); 7 evasion probes all fired; suites 172 frontend (was 142) / 1,753 Python unchanged; 10 forward-dated sentences repaired; AC 4's browser-render half deferred to the epic manual-testing checklist
