# Epic C4 Retrospective — The Deck on the Glass

**Date:** 2026-08-07
**Facilitator:** Amelia (Senior Software Engineer)
**Participants:** Sathias (Project Lead), Amelia (Dev), Winston (System Architect), Mary (Business
Analyst), John (Product Manager), Sally (UX Designer), Dana (QA), Paige (Technical Writer)
**Epic:** C4 — 12 of 12 stories `done`, PRs #40–#51 merged into `feat/companion-c4`, tip `2369ab3`
**Makes answerable:** SC-5. **Measures for the first time:** NFR-05.

---

## Delivery Summary

| | |
|---|---|
| Stories | **12 / 12 done** — c4-1 … c4-12, PRs **#40–#51** |
| Commits vs master | 27 · **148 files** · +47,950 / −658 |
| Frontend suite | 731 → **1,694** (+963); 36 → **65** files |
| Python suite | 2,447 → **2,501** — untouched all epic bar one comment in `deck_validator.py` |
| Bundle | JS 202,846 → **224,279 B**; CSS 6,187 → **20,390 B**; font unchanged |
| Registries | tokens 65→69 · primitives 15→18 · **containers 0→24** (new tree, c4-4) · copy modules 5→13 · stores 3→6 · schema aliases 7→12 |
| Reviews | **12 same-day three-layer passes**; ~270 raw findings → ~150 patches; **0 Critical** |
| Greptile | 12 PRs, **1 round each**, **3 inline findings total** |
| Deferred ledger | **+1,530 lines**, 16 new sections; file now 4,669 lines / ~367 entries |

**Shape of the epic:** one store slice (c4-1), the deck bootstrap (c4-2), then the card surface
built outward — placeholder, tile, grid, detail panel, flip control (c4-3 … c4-6) — then the four
analysis panels (c4-7 … c4-10), then the two floors: keyboard (c4-11) and the empty/cold-open
state (c4-12). Largest UX surface in the feature.

---

## What Went Well

### 1. The Greptile number finally moved, and it moved a long way

Measured from the GitHub API — inline-comment provenance and review submissions, not the
in-place-edited summary score (the C2 trap):

| Epic | Round-1 clean | Rounds needed | Total inline findings |
|---|---|---|---|
| C2 | 3 of 10 (30%) | up to 3 | 10 |
| C3 | 3 of 9 (33%) | up to 3 | 10 |
| **C4** | **9 of 12 (75%)** | **1 on every PR** | **3** |

The three: a **P1** on #44 (c4-5, mixed input clearing inspection — real, fixed at `7681e15`); a
**P2** on #40 (c4-1, orphaned hydration return — real, documented at `cbaf087`); and a **P2** on
#49 (c4-10, StrictMode duplicate requests) that **Greptile withdrew itself** after Sathias pointed
at the comment block recording the posture. **From c4-6 onward: zero findings, zero second rounds.**

John (Product Manager): "Two epics of a flat 30-something percent and then 75. That is the first
time this project has moved that number."

### 2. Nine CDP eye-checks, and not one was ceremonial

jsdom evaluates no CSS, no media queries and no geometry, so every visual claim in this epic
needed a real engine. Each check paid:

| Story | What the eye-check found |
|---|---|
| c4-4 | **Two focus indicators at once** — the composite ring on the card plus the UA ring around card-plus-caption. Repaired by making the button the card. |
| c4-5 | The pinned ring measured `--accent`, not the `--accent-dim` the artefact specified (2.70:1); clamp measured at 294px = exactly 14 lines |
| c4-6 | Reduced-motion `visibility` rules vindicated — without them both faces face the viewer at every setting |
| c4-7 | `Panel` default level + `GroupHeader` contrast (8.59:1 / 5.43:1), closing a deferral open since c2-7 |
| c4-8 | The **1.8 px thinnest non-empty bar** — faithful as data, marginal as a picture |
| c4-9 | `Prismatic Dragon` at **45 pips, not 71** — Q1's measurement made visible |
| c4-10 | The violation sentence that `DESIGN.md:423`'s two-slot letter renders **nowhere** |
| c4-11 | Focus-ring appearance (C2 retro item 4, open since C2) discharged |
| c4-12 | The empty deck's **two empty 57px panel shells** — `DESIGN.md`'s own "reads as a loading failure" |

Also caught: a **false bug avoided** at c4-6 — `Marang River Regent // Coil and Catch` genuinely
carries identical `oracle_text` on both faces, so "the oracle didn't change" would have been filed
from a screenshot as a defect that does not exist.

### 3. NFR-05 has a real number for the first time in the project's life

311 / 363 / 428 ms fresh profile (n=5), 238 / 348 / 387 ms repeat visit (n=5), 278 / 313 / 390 ms
cold image cache (n=3), against a **1,000 ms** budget. Every prior figure in the record measured
something else with a different instrument. c4-12 also priced an **available 180 ms improvement**
(swapping two `useEffect` blocks moves the format check from queue position 106 to 7) and
deliberately did not take it, with both comments now naming the other's queue position.

### 4. Task 0 kept correcting the story's own context

Not once as a formality:

- **c4-8** — the AC's requested doc fix ("84 → 82") was **measured wrong and declined**; they are
  three different quantities (84 / 82 / 116) and the ledger's 84 was correct as written.
- **c4-9** — five record corrections, including that `card_faces IS NOT NULL` matches **all 38,261
  rows** (non-faced cards store the JSON string `'null'`) — a false-coverage failure inside the
  measurement instrument itself.
- **c4-11** — §A's own median/mean corrected 82/103 → 78/102.0, with the cause reproduced.
- **c4-12** — 28 orphan `deck_cards` rows across 2 deleted decks; the image cache occupies 220
  shards, not 137.

### 5. Twelve for twelve on the same-day three-layer review, and Criticals stayed at zero

C3 action item 11 held perfectly across the epic's largest surface.

---

## Challenges & Lessons

### 1. "Coverage that reads as coverage" — seven consecutive stories, each in its own flagship guard

| Story | Instance | Sev |
|---|---|---|
| c4-6 | probe (c) passed — no fixture had a card with exactly one imaged face | — |
| c4-7 | `MULTIPLICATION_SIGN` shipped the literal character under a comment claiming an escape, while the story's own new ledger entry mocked `CardTile` for the identical defect | **High** |
| c4-8 | the AC 8 split-card pin was **fabricated** (`'Land // Land'` → `isLand` excluded the card before the derivation ran); two `bucketOf` tautologies stayed green | **High** |
| c4-9 | the `groupOf` land-policy guard was **vacuous** — both fixtures contribute zero pips under either policy — with a comment asserting the opposite of its own `toEqual({})`; plus four fabricated "verified-real" fixtures | — |
| c4-10 | the guard file's own non-vacuity check was `expect(trackedSources.concat(file)).toContain(file)` — true for any string | **High** |
| c4-11 | AC 7's `onKeyDown`-absence test claimed in **two shipped comments** and existing nowhere | **High** |
| c4-12 | the never-blank test titled "…through recovery back to a deck" never advanced the poll | **High** |

**The mechanism:** the guard a story is proudest of is the one nobody re-reads. Five of the seven
landed in the story's own named flagship.

**The counter-measure already exists and worked twice.** c4-11 and c4-12 were both caught by the
guard's **own non-vacuity anchor** before any reviewer saw them. It is not standard practice — it
became one at this retro (R2 below).

**A second-order instance, worth its own line:** c4-12's fix required a measurement, and the
measurement found something new — `poller.ts`'s `RETRIES_QUIETLY` is deliberately `false` for
`internal_error`, so **no recovery edge can ever arrive** for that token or for `deck_not_found`.
The honest test drives real recovery for the two retrying tokens and pins the terminal pair.

### 2. The probe harness lied five times, and its own negative controls caught it every time

| # | Story | Cause |
|---|---|---|
| 1–2 | c4-5, c4-9 | a forward-slash `cwd` with a **lowercase drive letter** breaks vitest's project-config resolution — `'c:/…/ui'` exits 1 with zero tests, `'C:\…\ui'` runs 1,474 and exits 0 |
| 3 | c4-5 | the ledgered standalone-runner crash — `tokens.test.ts` + `token-usage.test.ts` invoked as a pair outside `npm test` both die before a single assertion |
| 4 | c4-10 | `subprocess.run(["npm","test"], shell=True)` on Windows passes only the first list element to `cmd.exe` |
| 5 | c4-11 | a probe that mutated `SkipLink.tsx` into TSX that would not parse — 1,596 tests collected instead of ~1,655, every assertion "caught" for free |

Under any of these, **every probe reads CAUGHT for free**. Each story rebuilt the validation by
hand. There is no shared harness — which makes the negative controls the load-bearing part of the
method and the thing least likely to be re-invented correctly.

### 3. Untracked bundle assets shipped a broken `index.html` — a High, twice

c4-3 and c4-7. Both times: both `index.html`s repointed at new asset filenames, the old assets
deleted, and all four new files `??` untracked. Committed as-is, both SPAs 404 their only script
and stylesheet.

**c4-7 is the story whose headline discovery is that `copy-rules.test.ts`, `token-usage.test.ts`
and `posture.test.ts` all walk `git ls-files` and cannot see an un-added file.** The finding and
its second occurrence are in the same diff. From c4-8 onward every story `git add`ed before
believing a green run, and it did not recur.

### 4. The ledger inverted its own purpose

**Fifteen shipped source modules name `c4-12` in their headers. The ledger named it twice.**
The work a story inherits is discoverable by grepping the **code**, not by reading the ledger.

The same failure mode, twice more:

- The `<div>`-in-`<button>` entry named `c4-5` as its home for **two stories after c4-5 passed on
  it**, because c4-6 re-homed it in its own story record and never in the ledger. c4-11 caught it
  and wrote the lesson down: *"a disposition written in a story file and not in the ledger is a
  disposition nobody will find."*
- c4-7's AC 38 dispositions, AC 42's entry, Q3's residue and three new entries all lived **only**
  in the Dev Agent Record until review demanded the ledger be written.

### 5. Prose and citation drift became the largest patch category

**~60 stale `DESIGN.md:NNN` anchors across 25 files**, behind a guard that requires the *string*
`"DESIGN.md"` within a sentence of every `px` literal and **never resolves the line number**. The
c4-7 / c4-9 / c4-10 / c4-12 frontmatter amendments each grew the file and nothing re-based the
citations; at least one now cites a real but **wrong** component (`FormatCheck.css` → `DESIGN.md:423`,
the card-tile bullet).

Paige (Technical Writer): "That is this epic's own theme sitting inside a citation gate. The guard
looks like it checks the anchor. It checks that the word appears."

Related, and measured: c4-6 corrected five load-bearing comments that said what the code does not
do (the preserve-3d scoping claim was false on all 99 tiles); c4-12 corrected a decide-once
rationale that was **mathematically false** (`emptyDeck` and `!hasCards` are identical inside the
deck branch).

### 6. ⚠️ The per-story context load tripled, and it compounds within the epic

**This is the epic's most actionable finding**, raised by Sathias from the outside — development
turns were getting much longer — and it resolves against the data in a direction neither of the
two obvious hypotheses predicted.

**Per-story diff composition, by category, added lines:**

| Epic | stories | prod code | test | guard | **record** | **(test+guard) ÷ prod** |
|---|---:|---:|---:|---:|---:|---:|
| C2 (frontend) | 10 | 405 | 245 | 632 | 641 | **2.16** |
| C3 (backend) | 9 | 807 | 1,442 | 105 | 417 | **1.92** |
| **C4 (frontend)** | 12 | **995** | 951 | 372 | **1,629** | **1.33** |

**The verification-to-production ratio is the LOWEST of the three epics.** C4 wrote the most
production code per story and the least verification per line of it. The "we are over-testing"
hypothesis is measurably false — that peaked in C2 and has fallen since.

**What grew is the context and the record:**

| Epic | avg `## Dev Notes` | avg story file |
|---|---:|---:|
| C1 | 20 KB | 58 KB |
| C2 | 15 KB | 70 KB |
| C3 | 16 KB | 90 KB |
| **C4** | **41 KB** | **107 KB** |

And it is not a step change — it **compounds within the epic**: c4-1 17 KB → c4-3 27 → c4-5 35 →
c4-7 50 → **c4-9 60 KB**, 3.75× the first story. The driver is visible in the story headers:
**inherited deferrals 9 → 15, don't-breaks 9 → 20, open questions 7 → 17**, with roughly 19 of 20
don't-breaks copied forward unchanged and nothing ever retiring.

**The frontend half of the question is partly true and it earned its keep.** C2 was also frontend
and sat at 15 KB, so "frontend" alone does not explain the jump. But jsdom evaluates no CSS, so
every visual claim needs a real engine — that is a genuine, irreducible frontend cost, it produced
nine findings no test could, and it is a **fixed** cost per story. It is not what grew.

**Honest limit (Dana):** these are proxies. Diff composition and context size are measurable from
the repo; turn duration is not. Wall-clock per story actually *fell* late in the epic — PRs #46,
#47 and #48 merged about two hours apart, #50 in 1.6 h. Elapsed time is not exploding. The
reading-and-writing load per turn is.

**Ruled: R1 below.**

---

## Previous-Retro Continuity — Epic C3's twelve action items

| # | Item | Status |
|---|---|---|
| 1 | R1 — Scryfall JSONL hotfix on master | ✅ done pre-epic, PR #38 at `7631147` |
| 2 | Confirm A2 (FR-22 live) | ✅ done |
| 3 | Complete the checklist before the integration PR | ✅ closed amended, remainder carried with homes |
| 4 | **F1 — a gate banning story-key-shaped strings from rendered text** | ⏳ **open (c8-5)** — but C4 corrected the premise: the survivor is **`c6-8`** in `AppShell.tsx:117`'s nav placeholder, on the glass on every surface since c2-6, and C3's census of six **never looked for a `c6-*` key**. All C4 keys are displaced, each by its own panel, asserted both ways. |
| 5 | **Adopt a live-contract canary** | ✅ **RATIFIED at this retro** — see *Team agreements* |
| 6 | **F4 — the failed-import/companion file-lock interaction needs a home** | ❌ **NOT MET.** Grepped: there is no `deferred-work.md` entry. **Ruled R3 below.** |
| 7 | Correct the "~12 MB" image figures | ✅ done in the C3 retro |
| 8 | Correct `images.py`'s line count | ✅ done in the C3 retro |
| 9 | R2 — promote the banned-family lifecycle | ✅ done in the C3 retro |
| 10 | R3 — record the stalled state's terminal consequence | ✅ done in the C3 retro |
| 11 | **Keep the same-day three-layer review before every PR** | ✅ **12 for 12**, Criticals at zero |
| 12 | **Review-added mechanisms re-enter review** | ⚠️ **11 of 12 — and it failed on the very first PR.** c4-1's Greptile P2 (orphaned hydration return) sits in the **`generation` counter its own three-layer review added**. It then held for eleven consecutive stories. |

**Follow-through: 8 closed, 1 ratified here, 1 partial, 2 open.** The first epic since C1 not at
full follow-through — and item 12's single failure is the most useful data point of the set,
because c4-1 is precisely the story the rule was written for and the rule was one story too late.

---

## Rulings made in this retrospective (Sathias, 2026-08-07)

### R1 — Trigger-gated inheritance, from c5-1

A story's context carries, in full, only the deferrals its own surface can **trigger**. Everything
else becomes a one-line index with its ledger anchor. The don't-break list caps at the items the
diff's own files can actually touch.

```
§Inherited deferrals
  TRIGGERED (n)      — full text, disposition owed
  NOT TRIGGERED (n)  — one line each, ledger anchor only
  DON'T-BREAK (n)    — only what this diff's files touch
```

Rationale: the C2-retro R2 discipline (*every inherited deferral gets a written disposition*) is
what has been catching real defects and it stays. What changes is that a **not-triggered**
disposition costs one line rather than a paragraph. Estimated effect on a c4-9-sized story: Dev
Notes 60 KB → ~22 KB. C5 is backend, where the baseline was already 16 KB, so the drop compounds.

### R2 — Every new guard ships a firing proof

Extends the standing *non-vacuity pairing* agreement with the specific failure this epic committed
seven times. A guard is not done until:

**(a)** a planted violation has been shown **RED through the full `npm test`** — never a
standalone file run — and
**(b)** one line states **what the assertion actually compares**, read against the code rather
than against its own comment.

Would have caught, at the time of writing: c4-8's `Land // Land` fixture, c4-9's zero-pip
`groupOf` guard, c4-10's `.concat` tautology, c4-11's absent `onKeyDown` test.

### R3 — F4 is ledgered and homed on c8-4

The failed-import / file-lock interaction gets a `deferred-work.md` entry with a named owner
(install / first-run readiness). Display behaviour is correct; blast radius is bounded (WAL permits
a second writer, only wholesale file replacement is blocked); it is a **recovery-path** defect, not
an import-path one. Meets C3 action item 6's original success criterion.

### R4 — The empty-deck state ships as written; status quo, recorded, not repaired

The two empty right-column panel shells stand. Adding a fourth panel to the hide list invents spec;
inventing an empty-state sentence puts unsourced words on the glass. The ledger entry stays at
**Medium** with the eye-check attached as the picture to decide against if it is ever revisited.

Sally (UX Designer): "For the record, I think this is the right call and the wrong-looking screen.
Both can be true. The entry keeps the picture, which is what matters."

### R5 — Four ledger items CLOSED with their measurements

1. **`ETag` / conditional requests on `GET /api/cards/{card_id}` — CLOSED as superseded.** c4-1's
   cache issues one request per id per tab and never re-requests a hydrated id, so the entry's own
   worst case is structurally impossible; the client's deliberate `cache: 'no-store'` would make an
   `ETag` inert regardless. Twelve stories exercised the cache on real decks, which is exactly the
   evidence the entry asked for.
2. **The `app/images.py` split — CLOSED as declined.** Parked at the C3 retro pending evidence.
   c4-4 mounted 99 `<img>` at once and c4-6 became the first `?face=` caller; between them the
   route, the pacer, the disk cache and the negative cache were exercised from a real browser and
   **needed no change to any of them**. 1,837 lines is 74.6% prose over 377 lines of code across
   three mechanisms, and the 108-line module header explains the interaction a split would destroy.
3. **`CardPlaceholder`'s `<div>` inside the tile's `<button>` — CLOSED as accepted.** Every engine
   renders it, React 19.2 warns in development only, the accessible name computes normally, and
   c4-6 closed the harder *interactive*-descendant version of the same seam. What remains is a
   spec-letter violation with zero measured accessibility impact against an edit c4-4 was
   explicitly told not to make.
4. **`StatChip` / `EXPERIENCE.md` — the artefact is amended.** `EXPERIENCE.md:34` and `:173` promise
   *"Pip distribution, source counts, deck value"*. Deck value is a **price**, which c4-7 measured
   out of existence (23 columns in `cards`, none a price; the Scryfall importer never reads the
   `prices` object); **source counts** appear in no UX-DR, no `DESIGN.md` line and no AC. Both rows
   are corrected, using the two `DESIGN.md` price amendments as the precedent. `StatChip`'s
   zero-consumer status becomes a stated fact rather than a pending surface.

### R6 — Four process items are C5 work

One committed probe harness · the `DESIGN.md` citation guard · "grep your own key" in the context
pass · a plugin-mirror check reachable from `ui/`. Detailed in *Action Items*.

**Standing rhythm unchanged:** story PRs into the umbrella with Greptile per story; one integration
PR to master after this retro with **no Greptile pass**; a fresh umbrella cut off master for C5.
**Merge ≠ release** — no tag and no CHANGELOG until c8-4.

---

## Team agreements (standing, updated)

Unchanged and still holding: *claims require verification* · *Task 0 story-start verification* ·
*construction-site enumeration* · *gate-output homing* · *error-contract enumeration* ·
*ban the family, never enumerate members* · *probe your own guard before review does* ·
*forward-dated-comment homing* · *open-question homing* · *banned-family lifecycle*.

**Amended:**

- **Non-vacuity pairing → FIRING PROOF** *(R2, this retro).* A new guard ships with a planted
  violation shown red through the full suite, and one line saying what its assertion compares.
  Seven worked failures in C4; two of them (c4-11, c4-12) were caught by the anchor itself, which
  is the evidence the mechanism works when it is present.

**New:**

- **Live-contract canary** *(C3 action item 5, ratified this retro).* Any contract owned by a
  **third party** gets at least one test that reads the third party, run **on a clock rather than
  on a commit**. Worked instance: `tests/integration/data/test_scryfall_live_contract.py`, weekly.
  It exists because the Scryfall bulk-data break was invisible to 2,472 green tests — every one of
  which monkeypatched `fetch_bulk_data_list` — and every data path was dead on the public v0.4.0
  release.
- **Trigger-gated inheritance** *(R1, this retro).* Full text for triggered deferrals, one line and
  a ledger anchor for the rest, don't-breaks scoped to the diff's own files.
- **A disposition lives in the ledger, not only in the story record.** c4-11's sentence, promoted:
  *"a disposition written in a story file and not in the ledger is a disposition nobody will find."*
  A story that re-homes an entry edits `deferred-work.md` in the same commit.

---

## Manual-Testing Checklist — Epic C4

Sourced, as always, from **what every test isolated away**. Twelve stories declared their limits
explicitly, so this list is mostly transcription rather than invention.

**Setup:** `uv run artificial-planeswalker companion` → note the printed
`http://127.0.0.1:<port>`. Set a real deck active over `PUT /api/active-deck`.

### Block F — the screen reader (nothing in 1,694 tests hears anything) 🔴

| # | Do | Why it cannot be tested |
|---|---|---|
| F1 | NVDA or VoiceOver over the card grid — does the tile read as **one utterance**? | jsdom concatenates naming elements with no separator; the suite asserts membership only |
| F2 | Pin a card — is `Pinned — {name}` phrased correctly, **em dash included**? | pinned byte-for-byte against the epic; how a reader speaks the dash is unknowable in jsdom |
| F3 | Tab to a flip control — *"Flip card, toggle button, pressed"*, and how the tile's name reads immediately before it | `aria-pressed` is asserted as an attribute; Chrome's AX tree gives `pressed: true`; phrasing is neither |
| F4 | With a DFC showing its **back**: the tile caption keeps the combined name while the panel says the face's. Deliberate — does it read as a bug? | confirmed on screen at c4-6; only a person can judge it |
| F5 | The visually-hidden curve table (`Cards by mana value`) — does it read as a table? | in the tree, not removed from it; Chrome reports 7 rowheaders + 2 columnheaders |

### Block G — a real keyboard on the real corridor 🔴

| # | Do | Note |
|---|---|---|
| G1 | Tab the whole `Atraxa Counter Cabinet v2` corridor — **205 stops** (99 tiles + 6 flips + 1 oracle + 99 rows) | pinned in-suite; never traversed by a human |
| G2 | Start Tabbing **immediately on a cold open** — flip controls materialise mid-traverse during the ~1 s sweep | c4-6 AC 1's ledgered residue; check focus is neither stranded nor skipped |
| G3 | Mixed mouse + keyboard: focus a tile, then move the mouse away; then hover one card while another has focus | c4-5's two-slot / `lastTransient` recency, the PR #44 P1 — jsdom proves wiring, not feel |
| G4 | Skip link on a **1-card deck** (`Iron Man — reminder`, corridor of 3) and on an **empty** deck | withdrawal ruled by `hasCards` incl. sideboard |
| G5 | The 21em oracle scroller — reach it and scroll it by keyboard | the WCAG 2.1.1 fix c4-11 shipped; the clamp fires only on corpus cards not in any deck |

### Block H — the things a warm loopback hid 🟡

| # | Do | Note |
|---|---|---|
| H1 | Cold open on a **real network** — the sweep's measured **+1.2 s** tail | measured on loopback only; first paint was untouched |
| H2 | **Kill the CDN** and open a deck — the ~124 s dead-CDN first paint has **never been reproduced** | carried from C3; c4-4 could not enter the path (disk cache warm) |
| H3 | **B6 — the negative cache on a real clock** (30 s window, needs an outage + 35 s) | carried from C3, homed on c4-4, **not run** |
| H4 | Watch the render budget on a cold profile — 311–428 ms measured, 1,000 ms budget | no committed harness; every measurement was a scratchpad throwaway (ledgered) |

### Block I — carried from C3 and **still unrendered by a real engine** 🔴

> These four were homed on **c4-2** at the C3 retro. c4-2 acknowledged them and did not run them.
> They are the same known trade, one epic older: a failure now is ambiguous between the panel and
> the wiring, and the wiring is a lot bigger than it was.

| # | Do | Home |
|---|---|---|
| A3 | Corrupt/lock `cards.db` → **`database-updating`**, a *different* panel from A1 from the same 503 | c4-2 (unrun) |
| A4 | Hold A3 > 60 s with ≥ 4 refusals → **`database-updating-stalled`**; then fix the DB and confirm it does **not** recover without a refresh (C3 R3 in the flesh) | c4-2 + c5-6 |
| A5 | Stop the backend with the tab open → panel stays, retries quietly, must **not** claim `disconnected` | c5-6 |
| A6 | Start the browser *before* the backend → known-and-ledgered wrong panel; judge tolerability | c5-6 |

**Also now worth a look on the same run:** c4-2's edge-triggered re-drive — cold-open during a DB
build, then let the build finish, and confirm the glass leaves the stale 503 panel **without a
refresh**. That is the High this epic's second story fixed and it has never been seen.

### Block J — judgement calls only a person can settle 🟡

| # | Look at | Recorded position |
|---|---|---|
| J1 | The **1.8 px thinnest curve bar** against a 0 px empty one (`Infinite Guideline Station`, 1 of 39) | faithful as data; a `min-height` would make small buckets read larger than they are |
| J2 | The **empty-deck screen** — two empty 57px panel shells beside the line | **R4: status quo, ruled.** Look anyway; the entry stays Medium |
| J3 | **CVD identifiability** on the colour bar — measured ΔE ≥ 10 for *distinguishability*, never for *knowing which colour a pip is* | a glyph is the only thing that closes it; not called for on the numbers |
| J4 | The **2,166 reversible-art printings** — flipping shows a second painting of the *same* card | 0 in any live deck; correct, and reads as a bug from a screenshot |
| J5 | Reduced motion at the **OS level** (C4 forced it via a CDP flag on every check) | |

### Block K — cross-surface, still owned by c8-6

| # | Do |
|---|---|
| D1 | Agent `validate_deck` vs REST `format-check` on the same deck — **still nothing compares the two shells** (AD-1's whole promise) |
| D2 | MCP server + companion running at once — c1-9's dispatcher, unexercised since C1 |

✅ **Discharged during C4, no action:** C3's **C1/C2** (a real browser now fetches companion routes
automatically), **C3/C4** (`is_legal` read against its six rows, and the 1-card `historic` deck's
`Mainboard has 1 cards; the minimum is 60.` seen by a human — both closed by name at c4-10's
eye-check), **E1** (deck-list panel on a long deck, measured at 3,198 px), and **C2 retro item 4**
(the focus ring, closed at c4-11).

---

## Significant Discoveries

**No epic-invalidating discovery.** C5's plan is sound as written — it is backend WebSocket
plumbing that depends on C2 and C3, not on C4, and nothing C4 measured changes a C5 contract.

Three findings that carry forward as facts rather than as work:

1. **`_MIN_MAINBOARD`'s deferral was exactly backwards.** `deck_validator.py:171-178` and the
   ledger both claimed brawl is genuinely 60 and only Commander is affected (0 decks). Measured
   through the real ASGI app: this repo's **own shipped skill** says Brawl (Historic) is **100
   exact**, and all **18** brawl decks sit at exactly 100 — so the panel tells **45% of the deck
   table** a minimum 40 cards below its format's, while the named at-risk population is empty. Code
   change **declined** (MCP blast radius — `validate_deck` serves the agent tools); both records
   corrected; severity Low → **Medium** because it is now on the glass.
2. **The format-check panel is never all-green.** `rotation` is advisory on 40 of 40 decks
   permanently (census: 195 pass / 40 advisory / 5 violation over 240 rows), so a caution badge
   there is furniture, not a signal. Recorded in the fixture module rather than promoted to `pass`.
3. **`compute_pip_signals` counts bare pips only** while hybrid and Phyrexian costs are live in 10
   decks (29 + 7 copies, one `{G/W/P}`) — a two-surfaces divergence across five axes, re-homed to a
   Python story owning the scoring surface.

---

## Readiness Assessment

- **Testing & quality:** ✅ 1,694 frontend / 2,501 Python green at every story boundary; ten gates
  including `mypy --platform win32`; bundle and `plugin/` mirror sha256-verified at every boundary.
  ⚠️ Seven stories shipped a false-coverage defect in their own flagship guard — all found, all
  repaired, R2 adopted. ⚠️ The probe harness has no committed home.
- **Deployment:** ⏳ all twelve story PRs merged; `feat/companion-c4` complete at `2369ab3` and
  unreleased. Next is the `feat/companion-c4` → `master` integration PR (**no Greptile**, per the
  standing rule, and it is far over the 100-file threshold at 148). Not a release.
- **Stakeholder acceptance:** ⏳ Sathias ruled eight decisions at this retro and has seen the epic
  on a real screen through nine eye-checks — but **Blocks F, G, I and J have not been run**, and
  Block I has now been carried across two epics. Recommendation below.
- **Technical health:** ✅ strong. Verification-to-production ratio *fell* (2.16 → 1.92 → 1.33)
  while production volume rose; Python untouched for twelve consecutive stories, which is the
  clean-boundary claim actually holding. Honest caveats: the ledger is at ~367 entries and grew
  1,530 lines this epic against few closures, and ~60 `DESIGN.md` citations are stale behind a
  guard that cannot see it.
- **Unresolved blockers for C5:** ✅ **none.** C5 depends on C2 and C3, both on master. One
  housekeeping item: **`.gitignore`'s `/graphify-out/` hunk went to master at `2f543ed` and
  `feat/companion-c4` never received it**, so `git add -A` on the epic branch stages thousands of
  cache files. Fix is a master → branch sync, not a hunk in the integration PR.

---

## Action Items

| # | Action | Owner | Success criteria |
|---|---|---|---|
| 1 | **R1 — trigger-gated inheritance**, from c5-1. Full text for triggered deferrals; one line + ledger anchor for the rest; don't-breaks scoped to the diff's own files. | Sathias (c5-1 onward) | A C5 story's `## Dev Notes` is measurably smaller than C4's 41 KB average without losing a disposition |
| 2 | **R2 — every new guard ships a firing proof** (planted violation red through the FULL suite + one line on what the assertion compares). | Sathias (standing) | No C5 story's review finds a vacuous or tautological assertion in the story's own new guard |
| 3 | **R3 — ledger F4** (failed-import / companion file-lock), **home c8-4**. Closes C3 action item 6. | Amelia — **in this retro** | A `deferred-work.md` entry with a named owner story |
| 4 | **One committed probe harness.** Validates the collected-test count, refuses a run carrying the crash signature, uses a native uppercase-drive path, and carries the do-nothing negative controls. | Sathias (c5-1) | A C5 story runs probes through the committed harness; no story rebuilds the validation |
| 5 | **Fix the `DESIGN.md` citation guard**: resolve the anchor and assert the cited line names the component; re-base the ~60 stale anchors. | Sathias (C5, standalone) | The guard resolves line numbers and the tree is green |
| 6 | **"Grep your own key" in the context pass**: `grep -rn '<story-key>' ui/src src tests` is a step in every story's Task 0, not only a ledger read. | Sathias (c5-1 onward) | Every C5 story's context section lists the source modules naming its key |
| 7 | **Plugin-mirror check reachable from `ui/`** so a frontend-only `npm test` can see a stale mirror. | Sathias (C5) | `npm test` fails on a deliberately stale `plugin/` mirror |
| 8 | **R5 — close the four ledger items** with their measurements (`ETag` superseded · `images.py` split declined · `<div>`-in-`<button>` accepted · `EXPERIENCE.md` rows amended). | Amelia — **in this retro** | Four dispositions written into `deferred-work.md`; `EXPERIENCE.md:34` and `:173` corrected |
| 9 | **Run Block I before the integration PR** — A3–A6 have now been carried across two epics and c4-2 is merged, so the wiring only grows from here. | Sathias | Four panels rendered by a real engine, or carried a third time **as an explicit ruling** |
| 10 | **Sync `.gitignore`'s `/graphify-out/` hunk from master onto the epic branch** before the integration PR. | Sathias | `git status` on the branch is clean of `graphify-out/` |
| 11 | **F1 — the story-key gate** stays open with its premise corrected: the survivor is `c6-8` in `AppShell.tsx:117`, not a `c4-*` key. | Sathias (c8-5) | One test refuses a planted `c9-9` in a component's rendered text |
| 12 | **Keep the same-day three-layer review before every PR** — 12 for 12, and the Greptile round-1 rate moved 33% → 75% under it. Standing. | Sathias (standing) | Every C5 story runs `bmad-code-review` before its PR |
| 13 | **Review-added mechanisms re-enter review.** 11 of 12 in C4, failing only on c4-1 — the story the rule was written for, one story too late. Standing, unchanged. | Sathias (standing) | No C5 story has a confirmed Greptile finding in code its own review added |

---

## Epic C5 Preview — Dependencies, Inheritance, Gaps

**Epic C5: The Agent's Channel.** 8 stories (c5-1 … c5-8). Depends on **C2 and C3 — not on C4.**
The pipe from agent to glass: two credentials that never touch, an authenticated WebSocket the
browser re-establishes on its own, one envelope shape both halves agree on, and a CI check that
stops them diverging.

**Dependencies — all satisfied.** C2's generator (c2-3) produces the TypeScript union from the same
Pydantic source and drift-checks it; C1's Host middleware (c1-5) is reused by the upgrade path
rather than duplicated; c1-7's discovery file already carries the agent token.

**What C5 inherits from C4, by name:**

- **c5-4 / c5-6** — the card cache's **terminal-after-three** asymmetry. c4-5 made it non-theoretical
  (a hover sweep spends attempts) and c4-2's Q7 ruling parks the fix (`resetCardCache()` on a
  recovery transition) here.
- **c5-6** — the **alternating-token backoff damping** (re-homed from c4-1, whose premise turned out
  false: `readCard` has no timer to damp) and the three `disconnected` siblings from C3 R3.
- **c5-4 / c5-6** — c4-2's **no-later-edge residue**: the boot's recovery re-drive fires only from
  `refused`/`none`, so c4-6's accepted no-re-sweep window is the same seam one level in.
- **Deck switching generally** — c4-6's uncancelled in-flight sweep (up to ~198 reads compete with
  the new deck's images) and c4-5's `deckMemory` deck-transition clear both assume Epic 5 owns the
  event.
- **c5-1** — the `tsc -b` cross-project import cascade, re-homed from c4-1 to *"the first story that
  really imports a `src/` module into `ui/tests/`"*, which c5-1's contract work is the likeliest
  candidate for.

**Gaps and risks:**

1. **The context-load fix is unproven.** R1 is adopted on a measurement, not on a worked example.
   c5-1 is the first test and it is also the epic's heaviest story (all four payload shapes frozen
   up front, deliberately).
2. **Block I is now two epics old.** A3–A6 remain unrendered by a real engine, and **c5-6 owns two
   of the four** — so C5 will need them run either way.
3. **C5 adds no third-party contract**, so the newly-ratified canary agreement will not be exercised
   this epic. Noted so its first real test is recognised when it arrives.
4. **The ledger is at ~367 entries** after growing 1,530 lines in C4. R1 reduces the *copy*; nothing
   yet reduces the *source*. If C5's context still feels heavy after c5-2, a closing pass over
   entries measured unreachable from live data is the next lever.

**No blocking dependency is unmet.** C5 is unblocked once the C4 integration PR lands.

---

## Commitments

- **13 action items**, **2 executed inside this retrospective** (R3's ledger entry, R5's four
  closures + the `EXPERIENCE.md` amendment). Ten are newly keyed to `epic: c4` in
  `sprint-status.yaml`; items 11–13 are C3 items **re-adopted rather than re-created**, so they stay
  tracked under `epic: c3` where their history lives — F1 open, the two standing review rules
  closed for C4 and carried into C5.
- **6 rulings** (R1 trigger-gated inheritance · R2 firing proof · R3 F4 homed · R4 empty deck as
  written · R5 four closures · R6 four process items) and **1 standing agreement ratified** (the
  live-contract canary, due at this retro by its own success criterion).
- **A 5-block, 24-item manual-testing checklist**, of which **Block I is carried from C3** and is
  the one the epic's readiness genuinely turns on.

**The epic's own best line, and it came from outside the code:** the question *"is this
over-engineering or frontend overhead?"* had a third answer neither option contained. The
verification-to-production ratio **fell** every epic since C2 while production volume rose. What
tripled was the context each story inherits and the record each story writes — and unlike test
coverage, none of it was ever designed to be bounded.

**Next steps, in order:**

1. Sync `.gitignore` from master onto `feat/companion-c4` (action item 10).
2. Run Block I — or rule it carried a third time, explicitly (action item 9).
3. Integration PR `feat/companion-c4` → `master`, **no Greptile**, 148 files.
4. Cut `feat/companion-c5` off master and begin c5-1 — the first story under trigger-gated
   inheritance and the first to use the committed probe harness.
