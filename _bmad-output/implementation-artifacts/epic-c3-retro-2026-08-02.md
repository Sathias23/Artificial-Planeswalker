# Epic C3 Retrospective — Deck Data & Card Imagery on Tap

**Date:** 2026-08-02
**Facilitator:** Amelia (Senior Software Engineer)
**Participants:** Sathias (Project Lead), Amelia (Dev), Winston (System Architect), Mary (Business
Analyst), John (Product Manager), Sally (UX Designer), Paige (Technical Writer)
**Epic:** C3 — 9 of 9 stories `done`, PRs #29–#37 merged into `feat/companion-c3`, tip `9077753`
**Closes:** SC-4. Satisfies CM-2.

---

## Delivery Summary

| | |
|---|---|
| Stories | **9 / 9 done** — c3-1 … c3-9, PRs **#29–#37**, all merged into the umbrella |
| Commits vs master | 51 commits · **104 files** · +39,051 / −643 |
| Python suite | 1,753 → **2,472** (+719) |
| Frontend suite | 549 → **731** (+182) |
| Reviews | 9 same-day three-layer passes + 3 round-2 full-branch passes; **~130 patches**, **0 Critical/Major** |
| Greptile | 10 inline findings across 9 PRs; **3 of 9 clean at round 1** |
| Deferred ledger | **99 entries opened**, 18 closed/resolved in-epic (file total: 265) |
| Wire growth | 2 → **7 paths**, 6 → **14 components**, 6 → **8 reason tokens** |

**Shape of the epic:** four REST endpoints (c3-1 … c3-4), then the entire external-service surface
in one place (c3-5 … c3-8: the image route, the pacer, the disk cache, the negative cache), then
the feature's first runtime frontend behaviour (c3-9). It is the only externally-paced work in the
companion feature.

---

## What Went Well

**1. SC-4 is closed and CM-2 is satisfied — with the AC re-homed rather than paraphrased.**
c3-6 could not satisfy the "a repeat request makes no CDN request" AC (there is no cache in a
pacer), so it named c3-7 as the owner in the ledger, the module docstring *and* the record instead
of writing a test that appeared to cover it. c3-7 satisfied it. The `POST /agent/events` half went
to c10-3 the same way, with `/health` recorded as a declared stand-in.

**2. Open questions: 19 consecutive stories ruled exactly as proposed.**
c3-1 through c3-8 had not a single question overturned. c3-9 ended the run with **one** refinement
(Q5 — a `fetch` rejection is not an absent token; clamping it to `internal-error` would have stopped
the poll on one transient blip). ~57 questions across the epic, one overruled.

**3. "Probe your own guard" — one epic old, and it caught its author twice.**
c3-8's probe (e) passed 980/980 and thereby exposed the author's *own* AC 7 test dodging the disk
cache by changing the key. c3-9 repeated the pattern. Neither would have been found by review.

**4. Two behaviour-only stories confirmed a no-wire-change prediction by running the generator.**
c3-6 and c3-7 both produced a `gen:api` no-diff and said so as a measurement. c3-8 predicted the
same and **measured it FALSE** — a Pydantic *class* docstring publishes in full while an attribute
docstring twelve lines away does not — then wrote the distinction into `scripts/dump_openapi.py`
and annotated both sites in `contracts.py` with `#` comments (proven not to reach `app.openapi()`).

**5. Wire discipline held under a closed-set extension, twice.**
`card_not_found` (c3-2) and `forbidden` (c3-4) and the two-at-a-time `no_image_data` /
`image_fetch_failed` (c3-5) each shipped with all ripple sites and a UI destination in one commit.
AD-16's rule — a new token and its UI state land together — was applied prospectively rather than
repaired afterwards, which is what C2's R1 asked for.

**6. Manual testing produced the epic's best evidence.** See *Manual-Testing Outcomes* — real CDN
latency, the true cache footprint and NFR-05's warm budget were all measured for the first time,
and a field-P0 with nothing to do with C3 was found.

---

## Challenges & Lessons

### 1. Greptile's survivors clustered in one file, and in review-added code

Measured from the GitHub API (reading `Reviews (N)` footers and inline-comment provenance — not the
in-place-edited summary score, per the C2 trap):

| Story | PR | Rounds | Findings | Location | Disposition |
|---|---|---:|---:|---|---|
| c3-1 | #29 | 1 | 0 | — | clean |
| c3-2 | #30 | 2 | 2 | `app/routes/cards.py` | both real → 503-masks-400 promoted to a wire-visible `Warning:` |
| c3-3 | #31 | 2 | 2 | **`src/logic/deck_validator.py`** | both accurate, both ruled/ledgered (D-1.6b scope) |
| c3-4 | #32 | 1 | 0 | — | clean |
| c3-5 | #33 | 2 | 1 | **`app/images.py`** | confirmed, patched `334d072` |
| c3-6 | #34 | 1 | 0 | — | clean |
| c3-7 | #35 | **3** | 3 | **`app/images.py`** | 2 confirmed+patched, 1 declined-as-designed |
| c3-8 | #36 | **3** | 1 | **`app/images.py`** | confirmed — *in review-added code* |
| c3-9 | #37 | 2 | 1 | `ui/src/api/decks.ts:146` | confirmed — *in review-added code* |

**The round-1 clear rate did not move: C2 was 3 of 10, C3 was 3 of 9.** An earlier framing in this
session claimed the streak "broke"; the data says otherwise and the claim is withdrawn. What
changed is *where the survivors live*:

- **Five of the ten findings — and every P1 from c3-5 onward — are in `src/companion/app/images.py`.**
  Three of the four PRs needing more than one Greptile round were that file.
- **Three consecutive stories (c3-7, c3-8, c3-9) had their confirmed finding in code the same-day
  three-layer review had just added.** The implementer noticed at the time and wrote "the c3-7
  pattern, 2nd story running", then "3rd story running" — it was seen, and never became a rule.

**The mechanism, stated plainly:** a three-layer review produces ~13 patches, written *after* the
last adversarial pass and shipped in the same commit as the code they fix. **They are the only
lines in a story that no layer ever looked at.** We built a review that hardens the implementation
and leaves its own output bare.

**Counterweight (John):** every one was caught by Greptile before merge and patched the same day.
Zero reached master. This is a "we are paying Greptile for a pass we could do ourselves" finding,
not a quality failure.

**Mary's note:** c3-3's two P1s are the only findings in the epic that reached `src/logic` — shared
truth, visible to the MCP agent surface as well as the glass. Both were accurate. Both were
**declined** and ledgered as D-1.6b scope. The ruling stands; the pattern is worth noticing.

### 2. The story's own new guards were evadable — and each replacement was weaker than the ban it retired

Three instances, one shape:

- **c3-3**: *"The guard I wrote was theatre and was measured to be."* Twelve planted violations
  through `find_rule_violations`, **all twelve returned `[]`** — including a seven-line composite
  reimplementing four rules at once. Every family was keyed on the syntax its own firing tests
  happened to use.
- **c3-6**: the replacement blocking-wait scanner missed `from time import sleep` — *the exact
  spelling the retired name-ban did catch*.
- **c3-7**: the one-write-site scan missed `Path.replace` and `Path.rename`, and its `to_thread`
  non-vacuity check was `"to_thread" in source`, satisfied by comments after every real call is
  deleted.

**"Ban the family, never enumerate members" is a C2 agreement violated three times in C3 by the
people who promoted it.** All three were found by probing, and all three were repaired and
re-probed — the agreement works; what was missing was a *procedure* for the retire-and-replace
moment. Ruled below as R2.

### 3. Structural pins nobody named went red — four stories running

c3-2, c3-3, c3-6, c3-7. c3-3's is the sharp one: the story named `test_routes_decks.py`'s
component-name set and wrote *"there is no excuse for finding it during a probe"* — and the pin
that actually failed was `test_routes_cards.py`'s. Two hand-synchronised copies; the prose tracked
one. c3-4 fixed the class by consolidating component/path pins into `test_committed_schema.py`
(Q5), and c3-6/c3-7 still each hit one the story had not predicted.

### 4. The deferred ledger tripled its growth rate

| Epic | Opened | Closed in-epic |
|---|---:|---:|
| C1 | 13 | 5 |
| C2 | ~30 | 1 |
| **C3** | **99** | **18** |

265 entries in the file. 18 closed is better than C2's 1 in both absolute and relative terms, and
every entry carries a named home — but 99 in nine stories is a different regime, and C4 is twelve
stories on the largest UX surface in the feature.

### 5. `images.py` is 74.6% prose, and the number that was supposed to settle its future was wrong

c3-8's ledger entry says *"the final number measured so the retro inherits a fact rather than an
impression: `images.py` is now 1,475 lines (1,307 at `3aef5d1`)."* The `3aef5d1` figure is correct.
The "now" figure was never re-measured. Measured at `16976c5` — c3-8's own merge commit — and at
HEAD:

```
src/companion/app/images.py            1,837 lines
  ├─ docstrings + comments             1,370   (74.6%)
  ├─ lines containing code               377   (20.5%)
  └─ blank                               289   (15.7%)
```

Largest docstrings: module header **108**, `NegativeCache` 75, `DiskCache` 69, `_write_atomically`
67, `fetch_image` 65, `Pacer` 59.

**The split argument changes shape entirely under the real number.** 377 lines of code across three
mechanisms is ~125 lines each — not unmanageable. Splitting would split *documentation*, and the
108-line module header explains the interaction a split would destroy (cache checked *before* the
pacer; negative cache *outside* `pacer.slot()`). Winston's counter to the finding-density argument:
c3-5/c3-7/c3-8 are the three hardest stories in the epic — **finding density tracks difficulty, not
line count.**

**Decision PARKED by Sathias pending manual testing.** The measurement above is the input; c3-8's
1,475 figure is corrected in `deferred-work.md` either way.

### 6. R4's prose migrated rather than shrank

`last_updated` held all epic (currently ~190 chars). The prose moved into the
`development_status` comments — `c3-1`'s is ~8,000 characters on one line. **R4 named a location,
not a behaviour.**

### 7. A C2 prediction closed false

C2's retro predicted *"C3 will likely fit under Greptile's 100-file threshold."* Measured: **104
files.** Moot in practice — the standing rule gives integration PRs no Greptile pass — but the
prediction is closed as wrong, and C4 will be far over.

---

## Previous-Retro Continuity (Epic C2 — 6 action items)

| # | Item | Status |
|---|---|---|
| 1 | **R1 — `card_not_found` + copy row on c3-2** | ✅ **Paid in full.** Token, all seven ripple sites and the verbatim `EXPERIENCE.md` row (gated from disk in `ui/tests/unknown-card-copy.test.ts`) in one commit |
| 2 | **R2 — c3-9 stays one story, five deferrals as ACs** | ✅ Shipped as one story; Q1–Q10 ruled at context time; **none discovered mid-implementation** |
| 3 | **R3 — checklist before the integration PR** | ✅ Run, amended — 9 of 14, 5 carried with homes. The item it existed for (the `inline-block` underline) closed |
| 4 | **R4 — `last_updated` = date + one clause** | ✅ Held. See *Challenge 6* — the prose migrated to the story comments |
| 5 | **"What the gates cannot see" map** | ✅ Closed by c3-1 (11 rows in `ui/README.md`), grown by c3-3, c3-7 and c3-9 |
| 6 | **Same-day three-layer review before every PR** | ✅ **9 for 9.** Its claimed *effect* (round-1 5/5) held flat rather than improving — see *Challenge 1* |

**Follow-through: 6 of 6 closed. Third consecutive epic at full follow-through.**

---

## Manual-Testing Outcomes — run 2026-08-02, Sathias

### ✅ A1 — `database-not-initialized` on a genuinely empty data dir — **PASS**

First time any C3 frontend surface has been seen. Confirmed on screen:

- The panel renders; headline / guidance / action are three distinct beats. Q3's "list of parts
  concatenated in source order" reads as *guidance-then-action* exactly as the shape forces.
- The `initialize_database` command chip renders in `--font-mono` — the 65th token, shipped by c2-9
  with no consumer. It has one now, and it is legible.
- The panel is **horizontally centred** in the left column (panel centre ≈ 440 px, column centre
  ≈ 437 px) — C2's measurement holds with real content in it.
- **C2's `inline-block` footer-underline fix still holds** with C2 on master: links underlined at
  rest, 10 px all-caps legible, footer in the window, no horizontal scroll.

**Findings (see Action Items):**

- **F1 🔴 — story keys are rendering in the shipped UI and no gate refuses them.** Three placeholder
  strings on the *fresh-install first-run view* contain internal identifiers: `c2-7`, `c4-2`,
  `c4-10` (header), `c6-8` (nav), `c4-5`/`c4-7`/`c4-10` (right column). All are homed and correct
  for today; nothing anywhere would stop one surviving to c8-4.
- **F2 — the kicker and the `h1` say the same words.** c2-6's Q3 shipping the product name
  provisionally; c4-2 replaces the string. Known and self-resolving, but it does read as a defect
  on screen — recorded so c4-2 does not treat the swap as cosmetic.
- **F3 — vertical anchoring on an empty page.** The panel is top-aligned with a large void beneath.
  Correct once a deck fills the column; a judgement call for the one case where the column is
  guaranteed empty. A c4-12 (empty deck state) conversation, not a C3 fix.

### ✅ A2 — the live `503 → 200` transition — **PASS** (confirmed by Sathias, 2026-08-02)

**FR-22 is observed.** A complete `cards.db` planted into an empty `PLANESWALKER_DATA_DIR` while the
tab was open, and **the page came alive on its own — no refresh.** This was the single
highest-value unverified claim in the epic and the reason c3-9 exists: every prior proof was
DOM-level (`App.test.tsx`'s FR-22 block asserts the transition from one mount, and probe (f)
confirms a remount-driven implementation fails it), and the visual claim was made nowhere.

**This closes A7 by implication.** `cache: 'no-store'` on the poll request was only ever a
source-level assertion — jsdom has no HTTP cache — and the ledgered risk was that a real browser
caching the `503` would make the page *never* come alive. It came alive, so the header is honoured
in practice. The entry is resolved rather than carried.

*Recorded as observed. No timing figure was captured; the poll's base interval is 2 s with a ×2
backoff to a 30 s ceiling, so the observed delay is bounded by wherever the backoff had reached.*

**Findings from the failed-import detour:**

- **F4 🟡 — a failed first import leaves a schema-only `cards.db` that the companion then locks.**
  The importer creates the schema *before* downloading; a failed download leaves a rows-less
  database behind, and the companion's next poll (≤30 s) opens it under c1-6's lazy engine. From
  that moment the user **cannot delete or replace the partial database** without stopping the
  companion — while the panel tells them to re-run the command. The *display* is correct
  (`is_database_initialized` returns `False` for present-but-empty). Blast radius is bounded:
  a second process *writing into* the file is fine under WAL — only wholesale file replacement is
  blocked. A recovery-path defect, not an import-path one. Adjacent to but distinct from c1-6's
  ledgered *"cached-engine path re-plants a zero-byte file"*.
- **F5 — the failure validated the panel by accident.** A genuinely broken first run — not a
  simulated one — produced the correct state, correct copy and correct quiet retry. c3-9 handled an
  error path nobody wrote a test for, because the path did not exist when it was written.

### ✅ Block B — the CDN nobody had actually contacted — **PASS, 15/16, zero code defects**

Driven by `Run-C3-BlockB.ps1` (port auto-discovered from `companion.json`, which incidentally
exercised c1-7's discovery file).

| Check | Result |
|---|---|
| B1 face 0 / face 1 serve, **byte lengths differ** | ✅ 67,976 vs 71,361 — face resolution is real, not a front-face fallback |
| B1 `?face=9` | ✅ `404 no_image_data` |
| B1 eyeball — Westvale Abbey → Ormendahl | ✅ **confirmed by Sathias** |
| B1 `Cache-Control` | ✅ `public, max-age=31536000, immutable` |
| B2 Memory Lapse (1 of the 79 with no image) | ✅ `404 no_image_data`, not a 500 |
| B3 Sparkspitter `?size=png` | ✅ `200` **`image/jpeg`**, cached as `png_0.jpg` — **D1 confirmed on the card it was ruled for** |
| B4 `art_crop` / `border_crop` | ✅ serve and cache correctly (see correction below) |
| B5 CM-2 — warm run added **0 files, 0 bytes** | ✅ **CM-2 observed, not asserted** |
| B5 `.tmp` litter after 99 real writes | ✅ **0** — c3-7's atomic write survived a real Windows FS with live AV |

**First-ever measurements:**

| Measurement | Value | Against |
|---|---|---|
| **Real Scryfall CDN latency** | **~99 ms / image** | never measured before |
| Cold, sequential | 19.66 s = 199 ms/tile | 100 ms pacer spacing + 99 ms CDN |
| **Warm, from disk cache** | **10.3 ms / tile** (1.02 s for 99) | NFR-05's 1 s deck-render budget |
| Cache footprint | **8.5 MB / 99 images ≈ 90 KB each** | the epic's "~12 MB / ~124 KB" — a **38 % overestimate** |
| Files written | 104 = 5 + **99 of 99** | every one cached |

**Three conclusions Winston drew:**

1. **c3-6's pacer constants are vindicated by measurement, not modelling.** Throughput is
   `min(1/spacing, concurrency/latency)` = `min(1/0.1, 4/0.099)` = `min(10, 40.6)` — **the spacing
   turnstile binds, with 4× headroom on the semaphore.** Exactly the regime c3-6 chose for. The
   epic's ~10 s cold-paint figure is correct *for a concurrent client*; the sequential test driver
   doubled it.
2. **The epic's "~12 MB" is a 38 % overestimate** and has been quoted in the epic file, the spine
   and three story records without anyone having fetched an image.
3. **NFR-05 has more headroom than claimed** — 10.3 ms per warm tile *sequentially*. The 1 s budget
   will be constrained by paint, not by the backend.

### Corrections to the test script (all the facilitator's, zero code defects)

- **The one B4 "FAIL" was a false assertion.** `cache_extension()` takes the **`Content-Type` and
  nothing else** — the size key is unavailable to it *by construction*, which is D1's entire point.
  `art_crop`/`border_crop` return `image/jpeg`, map to `.jpg` and cache correctly.
  `CACHE_MEDIA_TYPES` is keyed by **media type**, not by size; Greptile's "accepted formats bypass
  the cache" was about `image/webp`, which no Scryfall image currently serves.
- The shard sample printed zeros because the path is two levels: `<root>/<id[0:2]>/<id>/<size>_<face>.<ext>`.
- The `~9.9 s` prediction models a *concurrent* client and was printed by a *sequential* one.

> **The lesson is the epic's own theme, committed while writing the retro:** the manual-testing
> script is a guard, and it shipped a false assertion because its premise was never probed. "Ban
> the family, never enumerate members" and "probe your own guard before review does" apply to the
> checklist as much as to the codebase.

---

## 🚨 Significant Discovery — the Scryfall import path is dead

Found while running A2. **Not a C3 defect; a released-product P0.**

Scryfall changed the bulk-data API. Measured against the live endpoint 2026-08-02:

| | Was | Is now |
|---|---|---|
| download key | `download_uri` | **`jsonl_download_uri`** |
| size key | `size` (uncompressed) | **`compressed_size`** |
| payload format | `.json` — one top-level JSON **array** | **`.jsonl.gz`** — gzip'd newline-delimited JSON |

`download_uri` and `size` are **gone from every entry**, on both the list and per-entry endpoints,
across all 7 bulk types. No deprecation, no fallback.

**Blast radius — none of it is the companion:**

- `scripts/import_scryfall_data.py` — every DB refresh
- `src/mcp_server/tools/initialize_database.py` — **the first-run path for every user**
- `src/data/importers/scryfall.py::import_scryfall_bulk_data` — the shared function both call

**v0.4.0 is public and released. A person installing today cannot obtain data by any supported
route.**

**Why 2,472 green tests did not see it.** Every test monkeypatches `fetch_bulk_data_list`
(`tests/integration/data/test_scryfall_import_e2e.py:543`,
`tests/unit/data/importers/test_download_hardening.py:121`). **Nothing in the suite has ever called
`api.scryfall.com/bulk-data`.** The upstream contract is asserted only against our own fixture *of*
it — the epic's recurring "a guard proven only against the spellings it lists", except the
"spelling" is a third party's JSON schema and the consequence is a dead product.

**The bitter one:** c3-9's entire deliverable is a fresh install that guides instead of erroring.
The panel A1 confirmed reads *"In your agent session, ask it to initialize the database
(`initialize_database`)."* **The guidance is flawless; the destination is broken.** This is the
class of defect manual testing exists for and no test could have found.

**Fix shape (sized, not started):**

1. `parser.py::stream_cards` (`:45` uses `ijson.items(f, "item")`, which requires a top-level array)
   — detect gzip and yield per-line `json.loads`; keep the array path for existing fixtures
2. `scryfall.py:351-352` — `jsonl_download_uri` / `compressed_size`
3. `_max_download_bytes` — now bounds a *compressed* download; ceiling arithmetic and the
   `file_size_mb` log line both need re-reading
4. `_validate_download_uri` — ✅ no change, `data.scryfall.io` already passes
5. Both streaming passes re-open the file, so decompression happens twice (~24 MB compressed for
   `oracle_cards`) — a decision, not an accident
6. **A test that calls the live endpoint and asserts the keys exist** — the thing whose absence
   caused this

---

## Rulings made in this retrospective (Sathias, 2026-08-02)

**R1 — the Scryfall JSONL migration is a hotfix on master, now, ahead of the C3 integration PR.**
It is a released-product P0 and fully independent of the companion. C3's integration PR then merges
onto a product that can actually obtain data.

**R2 — the banned-family retire-or-keep procedure is promoted to a standing team agreement.**
Three worked examples exist (c3-6 removed 4 names and replaced them with a positive AST gate; c3-7
removed 8 and re-keyed the survivors onto `functools` imports; c3-8 *kept* its family as a
permanent ruling because `functools.cache` cannot express a TTL). The reasoning lived in a
frozenset's docstring, where no story author looks before starting. Wording in *Team agreements*
below.

**R3 — `database-updating-stalled`'s terminal behaviour is ACCEPTED and ledgered; c5-6 dissolves
it.** `RETRIES_QUIETLY['database-updating-stalled']` stays `false`. The consequence — a user who
does exactly what the panel says and succeeds still needs a manual refresh — is recorded
explicitly rather than left implied. Its two sibling cases are already homed on c5-6's WebSocket
reconnect; all three resolve together. **No `EXPERIENCE.md` amendment.**

**PARKED — splitting `app/images.py`.** Deferred pending manual testing. The 1,837-line / 377-code
measurement is the input; c3-8's 1,475 figure is corrected in the ledger regardless.

**Standing rhythm unchanged:** story PRs into the umbrella with Greptile per story; one integration
PR to master after the retro with **no Greptile pass**; a fresh umbrella cut off master for C4.
**Merge ≠ release** — no tag and no CHANGELOG until c8-4.

---

## Manual-Testing Checklist — Epic C3

Sourced from *what every test isolated away*: a real browser, a real CDN, a real clock, a real
filesystem under contention, and the two shells answering the same question.

**Setup:** `uv run artificial-planeswalker companion` → note the printed `http://127.0.0.1:<port>`.

### Block A — the five panels (c3-9) 🔴

| # | Do | Status |
|---|---|---|
| A1 | Empty `PLANESWALKER_DATA_DIR`, no `cards.db`, open in a browser → `database-not-initialized` | ✅ **PASS** (F1–F3) |
| A2 | Plant a complete `cards.db` while the tab is open → the page comes alive with no refresh | ✅ **PASS — FR-22 observed** |
| A3 | Corrupt/lock `cards.db` → **`database-updating`**, a *different* panel from A1 from the same 503 | ⬜ not run |
| A4 | Hold A3 >60 s with ≥4 poll refusals → escalation to **`database-updating-stalled`**; then fix the DB and confirm it does **not** recover without a refresh (R3 in the flesh) | ⬜ not run |
| A5 | Stop the backend with the tab open → the panel stays and retries quietly; must **not** show `disconnected` (c5-6's) or a stack | ⬜ not run |
| A6 | Start the browser *before* the backend → known-and-ledgered wrong panel; judge tolerability until c5-6 | ⬜ not run |
| A7 | During A2, watch the network tab — a cached `503` would make the page never come alive | ✅ **closed by implication** — the page came alive, so `no-store` is honoured |

### Block B — the CDN ✅ **COMPLETE**

`Run-C3-BlockB.ps1` — B1–B5 pass, 15/16 checks, the one FAIL was a false assertion in the script.

| # | | Status |
|---|---|---|
| B1 | Face resolution — Westvale Abbey // Ormendahl | ✅ PASS incl. eyeball |
| B2 | No image anywhere — Memory Lapse | ✅ PASS |
| B3 | `size=png` → `.jpg` — Sparkspitter (D1) | ✅ PASS |
| B4 | `art_crop` / `border_crop` | ✅ PASS (serve **and** cache — script assertion corrected) |
| B5 | CM-2 on a real 99-card deck | ✅ PASS + first-ever latency/footprint measurements |
| B6 | Negative cache on a real clock (30 s window) | ⬜ not run — needs a network outage + 35 s |

> ### Checklist CLOSED by Sathias, 2026-08-02 — the remainder is CARRIED, with homes
>
> Manual testing ended after A1, A2, A7 and Block B. The reasoning follows the C2 R3 amendment
> precedent, and the carried items are homed rather than dropped:
>
> - **The two items the checklist existed for are closed.** FR-22 comes alive in a real browser
>   (A2) and CM-2 is a measured zero-request warm run (B5). Neither had ever been observed.
> - **Merge ≠ release.** No tag and no CHANGELOG until c8-4, so nothing carried reaches a user.
> - **Every remaining item has an owner story below.** The cost of carrying is that a finding
>   becomes a fix on a later branch instead of on this umbrella — not that it goes unlooked-at.
>
> **The one cost worth stating plainly, so it is a known trade rather than a discovery later:**
> A3–A6 are the three panels a real engine has never rendered, and **c4-2 is the story that makes
> them routinely reachable.** Run against C3's poller alone, a failure means *the panel is wrong*.
> Run after c4-2, a failure means *the panel or the new wiring* is wrong. Carrying them does not
> add risk — merge ≠ release — it adds diagnostic cost to whoever hits one. Recorded, ruled,
> proceeding.
>
> | Carried | Home |
> |---|---|
> | **A3** `database-updating` never rendered | **c4-2** — renders four of the five panels for real |
> | **A4** `database-updating-stalled` never rendered; R3's terminal behaviour never felt | **c4-2** (appearance) + **c5-6** (the recovery R3 ruled it owns) |
> | **A5** backend stopped — panel must stay and not claim `disconnected` | **c5-6**, which owns `disconnected` |
> | **A6** browser started before backend — known wrong panel | **c5-6** (already ledgered) |
> | **B6** negative cache on a real clock | **c4-4** — the first story where a person watches images fail |
> | **C1/C2** no companion route fetched by a real browser | **c4-1 / c4-2** — they make it automatic |
> | **C3/C4** `is_legal` vs its six rows | **c4-10** (already ledgered — nothing machine-checkable stops the binding) |
> | **C5** 503-outranks-400 retry trap | **c4-1** (already ledgered; the `Warning:` is in the JSDoc) |
> | **C6** `active-deck` auth surface | **c5-5**, which inherits the `AgentToken` seam |
> | **D1** agent `validate_deck` vs REST `format-check` — **AD-1's promise, owned by nobody** | **c8-6** (SC-5 acceptance) — newly homed here, it had no owner |
> | **D2** MCP server + companion running together | **c8-4 / c8-5** (install + release readiness) |
> | **E1/E2** carried from C2 | **c4-11** / **c2-6 if it fails** |
>
> **D1 is the one that changed owner at this retro.** Nothing in 2,472 tests compares the two
> shells' output for the same deck, and no story owned checking it. It is AD-1's central claim —
> one implementation, two surfaces — and it is now on c8-6 rather than nowhere.

### Block C — endpoints a browser has never called

| # | Do | Status |
|---|---|---|
| C1 | `/api/decks` in the address bar — **no companion route has ever been fetched by a real browser** | ⬜ |
| C2 | `/api/deck/813d0434-…` — the 99-distinct-id worst case | ⬜ |
| C3 | `…/format-check` on that brawl deck — **read `is_legal` against the six rows**; c4-10 binds this to a panel headline with nothing machine-checkable stopping it | ⬜ |
| C4 | `/api/deck/5cd42e7f-…/format-check` — the 1-card `historic` deck; the min-size row saying "60", D-1.6b visible to a human | ⬜ |
| C5 | `/api/cards/00000000-…` → 404; `/api/cards/NOT-A-UUID` → 400; then with the DB stopped → **503 wins over 400** | ⬜ |
| C6 | `/api/active-deck` GET (200) then PUT without a token (403 `forbidden`) | ⬜ |

### Block D — cross-surface agreement (never tested at all)

| # | Do | Status |
|---|---|---|
| D1 | Agent `validate_deck` vs REST `format-check` on the same deck — **nothing in 2,472 tests compares the two outputs** (AD-1's whole promise) | ⬜ |
| D2 | MCP server and companion running at once — c1-9's dispatcher, unexercised since C1 | ⬜ |

### Block E — carried from C2

| # | | Status |
|---|---|---|
| E1 | Deck-list panel with a genuinely long deck *(homed c4-11)* | ⬜ |
| E2 | Does the footer ever require scrolling? *(if yes, a c2-6 shell defect)* | ⬜ |

---

## Action Items

| # | Action | Owner | Success criteria |
|---|---|---|---|
| 1 | ~~**R1 — Scryfall JSONL hotfix on master**~~ — ✅ **DONE 2026-08-02, PR #38 merged at `7631147`** (Greptile 5/5 at round 1, zero inline findings). Both halves of the criterion met: the importer completes against the live API (**38,485 cards, 0 errors** from `scryfall_oracle_cards.jsonl.gz`) and `tests/integration/data/test_scryfall_live_contract.py` calls the real endpoint **through the production resolver**, run weekly by a new scheduled workflow. `stream_cards` decides the payload shape by **reading the bytes**; `_resolve_download_uri` names the keys that actually arrived. Probed: the pre-break key list reds the canary 5 ways against the live API. | Sathias | ✅ met |
| 2 | ~~**Confirm A2**~~ — ✅ **DONE 2026-08-02.** The page came alive with no refresh, observed. FR-22 is no longer a DOM-only claim, and A7's cached-`503` risk is closed by implication. | Sathias | ✅ met |
| 3 | ~~Complete the checklist before the integration PR~~ — ✅ **CLOSED 2026-08-02 in its amended form**, exactly as C2's R3 was: A1/A2/A7 + Block B run, **the remainder carried with a named home each** (table in *Manual-Testing Outcomes*). The item's purpose — the two make-or-break claims — is met, and **D1 gained an owner it never had** (c8-6). | Sathias | ✅ met — every remaining item carried with a named home |
| 4 | **F1 — a gate banning story-key-shaped strings from rendered text.** Ban the family: `/\bc\d+-\d+\b/` in any string reaching the DOM. Catches all three of today's placeholders and every future one. | Sathias (c8-5, or earlier if a C4 story is nearer) | One test refuses a planted `c9-9` in a component's rendered text |
| 5 | **Adopt a live-contract canary** — any contract owned by a third party gets at least one test that reads the third party. Proposed as a standing agreement; needs ratification. | Sathias | Ruled at the C4 retro at the latest; the R1 test is its first instance |
| 6 | **F4 — the failed-import/companion file-lock interaction** needs a home. Recovery path, not import path. | Sathias | A `deferred-work.md` entry with a named owner story |
| 7 | **Correct the epic's "~12 MB / ~124 KB" figure to the measured 8.5 MB / ~90 KB**, and record the ~99 ms CDN latency where c4-4 will look. | Amelia — **done in this retro** | `deferred-work.md` + `ui/README.md` carry the measured numbers |
| 8 | **Correct c3-8's `images.py` line count** 1,475 → **1,837** in `deferred-work.md`, with the 74.6 %-prose / 377-code breakdown, so the parked split decision resumes from a fact. | Amelia — **done in this retro** | The ledger entry carries the measured breakdown |
| 9 | **R2 — promote the banned-family lifecycle** to the standing agreements. | Amelia — **done in this retro** | Recorded below |
| 10 | **R3 — record the stalled state's terminal consequence** and confirm c5-6 owns all three siblings. | Amelia — **done in this retro** | The `deferred-work.md` entry is re-homed from "C3 retro" to c5-6 with the ruling |
| 11 | **Keep the same-day three-layer review before every PR** — 9 for 9, and still the mechanism that keeps Critical/Major at zero. Standing. | Sathias (standing) | Every C4 story runs `bmad-code-review` before its PR |
| 12 | **Review-added mechanisms re-enter review.** A review patch that adds a *mechanism* (not a test, not prose) gets one adversarial pass before the commit lands. Three consecutive stories had Greptile's finding in review-added code. | Sathias (standing, from C4) | No C4 story has a confirmed Greptile finding in code its own review added |

### Team agreements (standing, updated)

- **Claims require verification** — stands, and was the epic's best habit: `gen:api` no-diff *run*
  rather than argued (c3-6, c3-7), and c3-8 measuring its own prediction FALSE.
- **Task 0 story-start verification** — stands. c3-6's Task 0 disproved a shipped docstring's claim
  about the DB pool by reading the live object.
- **Construction-site enumeration** — stands.
- **Gate-output homing** — stands; every re-homed AC named a story key in the same commit.
- **Error-contract enumeration** — stands; c1-6's pre-registered handler meant C3 added two 503
  paths with no per-route ceremony.
- **Non-vacuity pairing** — stands, and c3-3 showed its limit: a pairing proves the guard *can*
  fire, not that it fires on anything but its own examples.
- **Ban the family, never enumerate members** — stands, **violated three times this epic by its own
  promoters**, caught by probing every time.
- **Probe your own guard before review does** — stands, and returned two author-caught defects
  (c3-8's probe (e), c3-9).
- **Forward-dated-comment homing** — stands.
- **Open-question homing** — stands; 19 consecutive stories with no question overturned.
- **Banned-family lifecycle** — *new, promoted this retro (R2).* A story that owns a banned
  identifier family must explicitly **retire it, re-key it, or keep it with a written reason** — and
  a replacement must be probed against **the spellings the retired ban caught**, not only against
  new ones. c3-6 (`from time import sleep`) and c3-7 (`Path.replace`) are the two worked failures;
  c3-8 is the worked *keep*. Removing a family without a replacement that covers its members is a
  coverage loss disguised as a cleanup.

---

## Epic C4 Preview — Dependencies, Inheritance, Gaps

**Epic C4: The Deck on the Glass.** 12 stories. Largest UX surface in the feature; the first epic
where **SC-5** becomes answerable. Depends on C2 **and** C3.

**C3 dependencies — all satisfied.** Every endpoint C4 needs exists, is typed, is drift-gated and
now has at least one measured real-world number behind it.

**What C4 inherits, by story:**

- **c4-1** — c3-9's `src/api/decks.ts` + `src/state/` slice is the seam it **extends** (card cache,
  in-flight deduping, per-card routes — which are **not** retry-safe: they carry path parameters).
  Also inherits: the DbSession held across the pacer queue wait (pool 5+10=15, timeout 30 s — works
  by arithmetic); Q2's reset-on-flip backoff, which needs a damping decision; and the whole-row read
  on the image path.
- **c4-2** — inherits a poll already calling `GET /api/decks`; its job is to read the *deck*, not the
  deck names. **It renders four of the five panels for real** — A3–A6 are its acceptance surface.
- **c4-3** — `CardFace` is typed (c3-5); the 79 no-image cards are its measured placeholder
  population; the CVD colour-sole-carrier eye-check is homed here.
- **c4-4** — **warm paint ≈ 10.3 ms/tile, cold ≈ 99 ms/tile, 8.5 MB for a 99-card deck** (measured
  this retro). Warm reads drop `Content-Type` parameters; `Retry-After` was declined; the 300 s
  negative-cache window is in the JSDoc. This is the story that first produces genuine concurrency,
  so it is the first that can make the semaphore bind.
- **c4-6** — the DFC flip control, the densest single component in the feature. B1 confirmed face
  resolution works end to end on a real transform card.
- **c4-10** — `is_legal: false` with zero violation rows; **nothing machine-checkable stops binding
  it to the panel headline** — the `Warning:` block is the only guard. `format_recognized: bool`
  ships declared-but-unread; delete it if c4-10 never reads it.
- **c4-11** — C2 checklist item 4 is carried here.
- **c4-12** — F3's empty-page vertical anchoring.

**Gaps and risks:**

1. **Four of the five state panels have still never been seen** — c4-2 is where they become
   routinely reachable. Running A3–A6 *before* c4-2 is cheaper than after.
2. **The ledger is at 265 entries** and C4 is 12 stories on the largest surface. Consider a closing
   pass rather than only an opening one.
3. **C4's integration PR will be far over Greptile's 100-file threshold** — already structurally
   handled (story PRs are the review gate), but expect it.
4. **`app/images.py`'s split decision is parked** and c4-1 adds the hydration cache that was the
   other half of the argument.

**No blocking dependency is unmet.** C4 is unblocked once R1's hotfix and the C3 integration PR
land.

---

## Readiness Assessment

- **Testing & quality:** ✅ 2,472 Python / 731 frontend green at every story boundary; fourteen
  gates including `mypy --platform win32`, both drift gates byte-reproducible, bundle and `plugin/`
  mirror measured (not assumed) at every boundary. ⚠️ One pre-existing `list_decks` tie-order flake,
  ledgered Medium after five confirmations. ⚠️ **The external contract had no test at all** — R1.
- **Deployment:** ⏳ all nine story PRs merged; `feat/companion-c3` complete at `9077753` and
  unreleased. Next is **R1's hotfix to master**, then the `feat/companion-c3` → `master` integration
  PR (no Greptile). Not a release — no tag, no CHANGELOG until c8-4.
- **Stakeholder acceptance:** ✅ **accepted 2026-08-02.** A1, **A2**, A7 and Block B run — **FR-22
  observed in a real browser** and **CM-2 measured**, the epic's two make-or-break claims. Sathias
  closed the checklist there; the remainder is **carried with a named home each**, per the C2 R3
  precedent. Known trade, stated rather than discovered: A3–A6's three panels are still unrendered
  by a real engine and c4-2 will make a failure ambiguous between panel and wiring.
- **Technical health:** ✅ strong. No guard suite needed a rewrite; three new mechanisms shipped with
  determinism (injected clock/sleep) rather than sleeps in tests; the suite got *faster* while
  gaining 719 tests. Honest caveats: `images.py` holds three mechanisms under a parked split
  decision, and the review surface is now ~14 gate suites with a declared blind-spot map that only
  exists because C2 demanded it.
- **Unresolved blockers for C4:** ✅ **none.** R1's Scryfall hotfix merged to master at `7631147`
  on 2026-08-02, so the integration PR now lands on a product that can obtain data — which was the
  entire reason R1 was sequenced first. A dry-run merge of `master` into `feat/companion-c3` is
  **clean, no conflicts**.

---

## Commitments

- **12 action items**, **6 closed** in or during this retrospective — including R1, whose fix
  shipped to master the same day the retrospective found the break.
- **3 rulings** (R1 hotfix, R2 agreement, R3 accept-and-ledger); **1 decision parked** (`images.py`
  split).
- **1 significant discovery** requiring work outside the epic — the Scryfall bulk-data API break.
- **24-item manual-testing checklist**: **A1, A2, A7 and Block B closed** (18 checks); A3–A6, B6 and
  Blocks C/D/E remain.

**The epic's two make-or-break claims are both closed.** FR-22 comes alive on its own in a real
browser (A2), and CM-2 is a measured zero-CDN-request warm run rather than a green test (B5).
Neither had ever been observed before today.

**Next steps, in order:**

1. ~~R1 — the Scryfall hotfix~~ ✅ **merged at `7631147`.**
2. Finish the checklist — A3–A6 are the three panels a real engine has still never rendered, and
   c4-2 is about to make them routinely reachable, at which point a failure is ambiguous between
   the panels and the new wiring. Findings become fixes on the C3 umbrella.
3. Integration PR `feat/companion-c3` → `master`, no Greptile. Merge is clean.
4. Cut `feat/companion-c4` off master and begin c4-1.
