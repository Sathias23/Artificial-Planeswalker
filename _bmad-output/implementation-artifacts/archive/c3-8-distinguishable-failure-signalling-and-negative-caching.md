---
epic: c3
story: c3-8
work_branch: feat/companion-c3
story_branch: feat/companion-c3-8-negative-cache
depends_on: c3-7 (PR #35, merged into the umbrella at 3aef5d1) — `images.DiskCache`, `build_image_cache`, `image_cache(app)`, `cache_root`, `cache_extension`, `CACHE_MEDIA_TYPES`, the lifespan's four consecutive state lines, `conftest.FakeClock`/`StallableUpstream`, and the **last** `_BANNED_IDENTIFIERS` family — which names this story
baseline_commit: 3aef5d1
---

# Story C3.8: Distinguishable failure signalling and negative caching

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the browser UI,
I want to know the difference between "this card has no art" and "the fetch failed",
so that I can draw the named placeholder the design specifies instead of showing a grey rectangle.

**What this story really is.** c3-5 opened the socket, c3-6 put a queue in front of it, c3-7 put a
floor under it. This one gives it a **memory of its own failures** — and four things about it are
not what the title suggests:

1. **Three of this story's five epic acceptance criteria are already satisfied, and were satisfied
   by c3-5.** The epic's AC 1 (*"signals the failure distinguishably from a card that has no image
   data at all… in neither case does the backend serve a substitute image"*), AC 3 (*"a card has no
   `image_uris` at all → a stable no-image response and no fetch is ever attempted"*) and AC 5
   (*"the client has enough information to render the named placeholder"*) shipped three stories
   ago as `no_image_data` + `image_fetch_failed`, and `contracts.py:98-108` says so by name. **This
   is the single most dangerous fact in the story**: an implementer who reads the title will either
   rebuild what exists or — much likelier — never verify it, and ship a story whose headline claim
   is inherited rather than proved. AC 1-3 below are *verification* ACs, and they are first for
   that reason. What is genuinely new is the epic's **AC 2** (negative-cached with backoff) and
   **AC 4** (the retry after the window).

2. **This is the first mechanism in this feature whose correctness is *forgetting*.** The disk
   cache never forgets and that is its whole design; a negative cache that never forgets is two
   defects at once — a permanently broken tile that no recovery can clear, and an unbounded map
   with **245,760** reachable keys (measured below, exactly the number of stored image URLs).
   Every hard question in this story is about expiry and about bounds, and neither is visible in a
   functional test that makes two requests.

3. **It empties `_BANNED_IDENTIFIERS` — or discovers that it must not.** The set is down to two
   names, `functools.cache` and `functools.lru_cache`, under the comment *"c3-8's negative cache.
   The LAST family in this set."* c3-6 took four names out of fourteen and c3-7 eight of the
   remaining ten, each replacing its family with a stronger positive gate. The reflex is to
   complete the pattern. **Read Q5 before you do**: the reason those two were banned turns out to
   be a reason they stay banned, and "the guard comes down because it is my turn" is precisely the
   move c3-6's own procedure warns about.

4. **No wire change at all, and it is predicted by name.** `dump_openapi.py:39` already says
   *"Story **c3-8**'s failure signalling and negative caching is next, and it is expected to be the
   third [behaviour-only story] for exactly that reason — the vocabulary it needs
   (`image_fetch_failed`) already ships. Confirm it by running the generator… a prediction of 'no
   diff' that is argued rather than measured has told you nothing."*

**This story inherits nine `deferred-work.md` entries homed on it by name — more than any story in
this epic.** They are enumerated in AC 20 and each one is answered, not surveyed. Two of them
(the transient-startup `OSError` and the unwritable root) are a *fourth* mechanism's worth of work
if taken naively; Q4 exists to size them.

**Everything numeric in this story was measured on this machine at `3aef5d1` against the shipped
38,261-card database and the installed toolchain, read-only. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **There is exactly one outbound call site, it has a required pacer, and it collapses every
   failure cause into one token.** `images.fetch_image(client, url, pacer)`
   (`src/companion/app/images.py:1168`) is called once, from `routes/cards.py:351`. Its docstring
   enumerates eight distinct failure causes — a refused URL, a connect or read failure, a
   whole-exchange timeout, any non-2xx, a non-servable content type, an oversized body, an empty
   body — and states that *"every upstream outcome collapses to the same answer, because they mean
   the same thing to a caller"*. **That collapse is load-bearing for Q3**: a per-cause backoff
   policy would require `fetch_image` to tell its caller *why*, which widens a deliberately closed
   one-token contract for a class of failure this corpus does not contain.

2. **The route's order is already established and the new check has exactly one correct home.**
   `read_card_image` (`routes/cards.py:294-368`) runs: `card_not_found` → `resolve_face_images` →
   `no_image_data` (face out of range) → `no_image_data` (size missing) → **disk cache read** →
   the client/pacer wiring guard → `fetch_image` → `cache.write` → `_image_response`. The negative
   check belongs **after the disk read and before the wiring guard**: a key with a warm entry is
   served whatever its failure history, and a negative hit needs neither a client nor a pacer.

3. **`DiskCache` is the shape to mirror and its three-way accessor ruling is already written.**
   A class in `images.py`; one instance created in the lifespan (`main.py:206`); a `build_*`
   factory when creation can fail; an `image_cache(app) -> DiskCache | None` accessor whose
   docstring states precisely what `None` means and *why it differs* from `image_client`'s and
   `image_pacer`'s `None` (`images.py:1110-1130`). A negative cache **cannot fail to construct** —
   it is a dict and a clock — so it is `Pacer`-shaped, not `DiskCache`-shaped, and
   `test_app.py::test_startup_failure_propagates` stays untouched. **Confirm that prediction by
   measurement**, as c3-6 and c3-7 both did.

4. **`Pacer` is the precedent for anything whose correctness is time, and the clock is already
   injectable.** `Pacer.__init__` takes `clock` and `sleep` as parameters *"so a test can assert
   exact start offsets at zero wall-clock cost — a rate proved by measuring elapsed real time is
   slow when it passes and mysterious when it fails on a loaded box"* (`images.py:534-544`).
   **A backoff is the same class of thing and gets the same treatment.**
   `tests/unit/companion/conftest.py:483` already ships `FakeClock`, consolidated there by c3-7,
   with a re-entrancy assertion that makes it refuse rather than lie.

5. **The failure response is already right and this story must not touch it.**
   `errors.error_response` stamps `Cache-Control: no-store` on every typed error feature-wide
   (c3-5), the status is derived from the token and never chosen at the call site, and
   `test_routes_card_image.py:637-644` pins that a fetch failure carries `no-store`. **A negative
   hit is the same typed error and inherits all of it with no code** — which is what makes AC 5's
   byte-identity claim cheap to assert and a divergence a defect rather than a subtlety.

6. **`ErrorReason` is closed at ten and this story adds none — and that is written down twice, in
   advance.** `contracts.py:104`: *"c3-8 adds negative caching and backoff as pure behaviour with
   no wire change at all because the vocabulary was paid for here."* `contracts.py:162`: *"only
   this one may ever be retried. c3-8 owns the negative cache and the backoff; until then a failure
   is simply not cached."* Both sentences become present tense (AC 15). If you find yourself
   wanting an eleventh token, the design went wrong — and `contracts.py:110-116` lists the eight
   edit sites so the cost is not a surprise.

7. **The UI half of this story shipped before the tokens did, and it is gated byte-for-byte.**
   `EXPERIENCE.md`'s Failure and Edge Cases table already reads: *"CDN fetch failure | Any image |
   Backend serves the placeholder response (FR-04); UI renders the named Card placeholder;
   **negative-cached with backoff — no request storms, no per-image retry UI**."*
   `ui/tests/named-card-copy.test.ts` holds it against the artefact itself. **That row has been a
   forward-dated promise since the artefact was exported; this story is what makes it true**, and
   it needs no edit on either side (AC 17 — a prediction to confirm, not assume).

8. **The two guards c3-7 built are load-bearing here and neither should need an edit.**
   `TestFileIoNeverRunsOnTheLoop` (`test_images.py:2258`) requires every file-I/O call site in
   `images.py` to be lexically inside a non-`async` helper reached only through
   `asyncio.to_thread`; an **in-memory** negative cache adds no file I/O and leaves it silent —
   which is a claim to *assert*, because Q1's persisted alternative would change it.
   `TestExactlyOneImageWriteSite` (`test_images.py:2027`) accounts for rename-into-place by module;
   a negative cache that writes nothing leaves it at two modules, once each.

9. **`TestExactlyOnePacer` (`test_images.py:1012`) is the template for this story's positive
   gate.** It scans **all of `src/companion`** for `Pacer()` construction sites and asserts exactly
   one, in the lifespan, with a planted aliased second site as its firing half. Mirror it, do not
   reinvent it — and plant the evasion in a spelling you would not have chosen (c3-6's review
   theme, and c3-3's headline finding: a guard keyed on the syntax its own firing test uses catches
   nothing else).

10. **The test seams you need all exist and c3-7 consolidated the last two.** `Recorder` + the
    `cdn` fixture (`test_routes_card_image.py:59-109`) patch the **factory**, not the client, and
    record every URL in order — `cdn.requested == []` after a second request is the whole negative
    cache in one line, exactly as it was for CM-2. `Recorder.raises` and `Recorder.status` are the
    two failure knobs and both already exist. `conftest.StallableUpstream(clock, hold=True)` parks
    every request on an `asyncio.Event`. The autouse `isolated_data_dir` fixture gives every test a
    private `PLANESWALKER_DATA_DIR`. **Write no third fake** — c3-7 paid the consolidation cost and
    `deferred-work.md` records how two copies had already drifted.

11. **`routes/cards.py` contains no `try`/`except` today, and c3-1's record calls that out as a
    property.** Recording a failure means catching `CompanionError` around `fetch_image` and
    re-raising it. That is the first exception handler in this module, it is unavoidable under any
    Q1 option (the negative cache is keyed on id + size + face, which `fetch_image` is not given
    and must not be), and it needs to be a deliberate, documented three-line shape rather than a
    quiet growth. **A bare `except Exception` here would swallow `CancelledError`'s siblings and
    turn a wiring bug into a remembered CDN failure** — see AC 10.

### The guard this story is fenced by, and why taking it down is a real question

12. **`_BANNED_IDENTIFIERS` (`test_routes_card_image.py:663-711`) is one family and it is yours:**

    | Family | Members | Owner |
    | --- | --- | --- |
    | the negative cache | `functools.cache`, `functools.lru_cache` | **c3-8 — this story, and the last one in the set** |

    c3-6 and c3-7 each removed a family and each replaced it with something stronger, and the
    procedure is written down in that docstring by both of them. **But this set is different in a
    way neither predecessor's was**: `Semaphore` and `mkdir` were banned because *c3-6 and c3-7 had
    not happened yet*, and the day they shipped the ban fenced the thing that was built.
    `functools.cache` and `lru_cache` were banned for that reason **and** for a second one that
    survives this story: they cannot express a TTL, `cache_clear()` is all-or-nothing so a single
    key cannot be invalidated on recovery, and an `lru_cache` over a failure is precisely the
    permanently-broken-tile defect AD-11's *"with backoff"* exists to prevent. **Q5 decides
    this, and the recommendation is against completing the pattern.**

    Four paired tests key on the set and every one of them is affected by whichever way Q5 goes:

    - `test_no_negative_cache_is_built` (`:805-811`) — becomes false the day you ship if the set
      survives unchanged; it is the assertion that must change under either option.
    - `test_a_planted_breach_of_a_surviving_family_actually_fires_the_ban` (`:885-909`) and
      `test_the_ban_catches_the_module_alias_spelling_too` (`:911-925`) — the firing halves. If the
      set empties, both degrade to `set() == set()`: **a test that passes because it now proves
      nothing**, which is exactly the failure mode c3-7 caught and re-planted rather than deleted.
    - `test_the_scan_ignores_prose_that_merely_names_the_banned_things` (`:927-971`) — its plant
      has been rewritten twice already, at c3-6 and c3-7, each time because the sentence it planted
      stopped being a ban. It will need rewriting a third time under either option, and its
      docstring says why in the story's own words: *"a plant nobody rewrites is how a test file
      starts asserting yesterday's design."*
    - `test_the_scan_sees_a_planted_breach_of_each_family` (`:826-883`) asserts on the **scanner**,
      not the ban, for `Semaphore` and `mkdir` — both already retired names. Its `functools` arm is
      the only one still tied to a live ban.

13. **`test_import_boundary.py` stays unchanged with no exclusions added.** Nothing about an
    in-memory failure map wants a banned database write path. Stated because every story in this
    epic has been tempted by something — and because c3-7's record establishes that this guard's
    green **does not** cover filesystem writes, a distinction Q1's persisted option would make
    relevant again.

### What the real data says (measured at `3aef5d1`, read-only)

**The key space is exactly the number of stored image URLs, and it is the memory bound.** The
negative cache is keyed on id + size + face — the same key AD-11 gives the disk cache — so the
number of keys that can ever exist is the number of (card, size, face) triples the corpus can
resolve:

| Property | Measured |
| --- | --- |
| Cards | **38,261** |
| Distinct `(id, size, face)` keys resolvable | **245,760** |
| Cards resolving to **0** faces (no servable image anywhere) | **79** |
| Cards resolving to **1** face | **35,404** |
| Cards resolving to **2** faces | **2,778** |
| Hosts across all stored URLs | `cards.scryfall.io` **245,742** · `errors.scryfall.com` **18** |

Three consequences, all load-bearing:

* **An unbounded map is a 245,760-entry map**, which is the arithmetic behind AC 8. It is not
  reachable in one session, and that is not a bound.
* **The 79 image-less cards never reach the negative cache at all.** They answer `no_image_data`
  four lines before the cache is consulted, so *"no fetch is ever attempted"* (the epic's AC 3) is
  satisfied structurally and the negative cache is not the thing that satisfies it. Say so.
* **Zero stored URLs sit outside the allow-list**, so an `is_fetchable` refusal — the permanent
  failure c3-5's review homed here — is **unreachable against this corpus**. That is the whole of
  Q3's evidence.

**The first paint against a dead CDN is not protected by this story, and claiming otherwise would
be the story's own version of prose outrunning code.** A 99-tile deck resolves to 99 **distinct**
keys, so nothing is remembered yet. Steady-state throughput is `min(1/spacing, concurrency/latency)`
= `min(1/0.1, 4/5.0)` = **0.8 fetches/second** at the shipped `_FETCH_TIMEOUT.connect = 5.0` — so a
cold paint against an unreachable CDN takes roughly **124 seconds** and issues all 99 requests. What
this story removes is **every subsequent paint**: a reload, a second tab, a scroll back. That is
what *"no request storms"* means here, and it is worth writing in the module docstring, because a
reader who expects the first paint to be protected will read the pacer as broken.

**The regression surface is smaller than c3-7's and its shape is different.** Forty-odd tests
traverse the fetch path; what matters now is any test that requests **the same failing key twice
within one app instance**, and any test where a *non-failure* could be recorded as one:

* `TestUpstreamFailures` (`:525-601`) — six cases, each one request against a fresh app. Unaffected,
  predicted.
* `TestADisconnectingClientReleasesItsSlot::test_a_fetch_still_succeeds_after_a_cancellation`
  (`:1205`) — cancels a request, then succeeds on **the same key**. **This is the test that fails
  if a cancellation is recorded as a failure** (AC 10). Predicted to pass unchanged; run it and say
  which happened.
* `TestWithTheNetworkGone::test_a_cold_key_through_the_same_dead_transport_is_still_a_502`
  (`:1904`) — one cold request through a raising transport. Unaffected.
* `TestTheBurstDoesNotOutlastTheConnectionPool` (`:1316`) — 99 distinct succeeding ids. Unaffected.

A test whose recorded fetch count *changes* is either the negative cache working or a key
collision; **read which**, do not assume. c3-7's Debug Log 5 is the precedent — the story text
claimed a test drove 99 distinct ids and it drove one id 99 times.

**Committed artifacts at `3aef5d1`, expected byte-identical (AC 16):** `ui/src/api/openapi.json` —
**7 paths** (`/api/active-deck`, `/api/card-image/{scryfall_id}`, `/api/cards/{card_id}`,
`/api/deck/{deck_id}`, `/api/deck/{deck_id}/format-check`, `/api/decks`, `/health`) and **12
components** (`ActiveDeck`, `ActiveDeckRequest`, `Card`, `CardFace`, `CardSummary`,
`DeckCardSummary`, `DeckDetail`, `DeckSummary`, `ErrorResponse`, `FormatCheckReport`,
`FormatCheckRow`, `HealthResponse`).

**Toolchain (c3-7's measurement, to be re-confirmed at Task 0):** Python **3.12.13** · FastAPI
**0.140.0** · Starlette **0.48.0** · SQLAlchemy **2.0.44** · Pydantic **2.12.0** · httpx **0.28.1**
· anyio **4.11.0** · uvicorn **0.51.0**. **No new dependency is needed or wanted**: `time`,
`collections` and `dataclasses` are stdlib, and `threading`/`concurrent.futures` are banned by name
in `images.py` by a scan that is still live.

**Suites at c3-7's tip, to be re-measured not inherited:** Python **2395 passed, 1 skipped —
123.40 s** · frontend **568 passed, 31 files**. SPA bundle SHA-256 (first 16), identical in
`src/companion/app/static/` and the `plugin/` mirror: `index-DE70muY2.js FAEEEA472ADD5078` ·
`index-DmxBiI94.css 0A3C142D84B5A98D` · `space-grotesk…woff2 0640890476FC1198` ·
`favicon.svg 9BE16EA2FE3670DE` · `index.html 8E65C0615CF66044`.

**On measuring runtime:** c3-7 ledgered that this machine's whole-suite runtime spreads **49 s
across three runs of identical code**, so a before→after whole-suite claim is unsupportable from
single samples. AC 23 asks for the **narrowest suite that contains the change** (`tests/unit/
companion/`), more than one sample, and no whole-suite delta read as signal.

---

## Acceptance Criteria

### What is already true — verified, not rebuilt

1. **The epic's distinguishable-signalling criterion is satisfied by the shipped tokens, and this
   story proves it rather than inheriting it** (epic `:1784-1787`, AD-11). A card with no artwork
   answers `404 no_image_data`; a CDN failure answers `502 image_fetch_failed`; **neither ever
   returns a substitute image**. Asserted as a *discrimination* from one test — the two responses
   differ in status and token — and the "no substitute" half asserted on the **bytes**, because a
   status-only assertion passes with a grey rectangle in the body. Name in the record which of
   these assertions already existed and which are new.

2. **A card with no `image_uris` attempts no fetch, and the negative cache is not what makes that
   true** (epic `:1793-1795`). The `no_image_data` answer precedes the cache by four lines, so the
   **79** image-less cards in the corpus never produce a cache key at all. Asserted on
   `cdn.requested == []` (already shipped at `:238`), **plus** a new assertion that no negative
   entry is created for them — the pairing that distinguishes "never fetched" from "fetched and
   remembered as failed".

3. **The client has everything it needs to draw the named placeholder** (epic `:1801-1803`,
   UX-DR22). Verified as a *contract* claim, not re-implemented: `GET /api/cards/{card_id}` already
   returns name, mana cost and type line, and both image failures are typed tokens the SPA's
   `PLACEHOLDER_FOR_REASON` classification already maps. No frontend code ships (AC 17).

### The negative cache

4. **A request for a key inside its backoff window makes no CDN request and never enters the
   pacer.** Asserted from `Recorder.requested` — a second request adds **zero** recorded URLs — and
   from c3-6's injected clock, which a negative hit advances by **zero** spacing intervals. This
   mirrors c3-7 AC 6 deliberately: the clock is what catches a check placed *inside* `pacer.slot()`,
   which remembers correctly and paces a remembered failure anyway. Paired with a **distinct** key
   through the same transport that does fetch.

4b. **The same claim at deck scale, because that is the user-visible one.** Using the existing
   `_seed_burst` helper (99 distinct ids — repaired by c3-7 to actually be distinct): a first paint
   against a dead CDN issues **99** fetches and 99 `502`s, and an immediate **second** paint issues
   **zero** and answers 99 `502`s from memory. State plainly, in the record and in the module
   docstring, what this does **not** fix: the *first* paint still costs ~124 s and 99 requests
   (§ What the real data says), because 99 distinct keys have nothing remembered yet. The pacer
   bounds that paint; this story bounds every one after it. A claim that the storm is solved within
   one paint would be this story's own version of prose outrunning code (c3-4's review theme).

5. **A negative hit is byte-identical to a real fetch failure.** Same `502`, same
   `{"reason": "image_fetch_failed"}`, same `Cache-Control: no-store`, same absence of every
   success header. **No new reason token** — `ErrorReason` stays closed at ten (`contracts.py:65`),
   and `test_errors.py`'s two pins are unchanged. Asserted as an equality between the cold failure
   response and the remembered one, field by field, not as two independent status assertions.

6. **The backoff is exponential, bounded, and proved on the injected clock at its exact
   boundaries** (epic `:1789-1791`, AD-11). Q2 fixes the base, the multiplier and the ceiling; the
   assertions are: one failure sets the first window; a request at `expiry - ε` fetches nothing; a
   request at `expiry` fetches; consecutive failures escalate through the schedule; and the delay
   **stops** at the ceiling rather than growing forever. Every one on `FakeClock`, none on wall
   time. The chosen numbers are stated in the constant's own docstring **with their arithmetic**,
   in the manner of `FETCH_SPACING_SECONDS` — a base shorter than one cold deck paint (9.9 s) would
   re-admit the storm it exists to prevent, and that is the reasoning that has to survive, not the
   number.

7. **Recovery is complete: after the window the fetch is retried, the image is cached normally on
   disk, and the key's failure history is cleared** (epic `:1797-1799`). The last clause is the one
   a functional test misses: a key that failed four times and then succeeded must start its **next**
   failure at the base delay, not at the escalated one. Asserted as a discrimination — fail ×N,
   succeed, fail once, and measure the resulting window against the base rather than against
   step N+1.

8. **The map is bounded, the bound is stated with its arithmetic, and eviction costs exactly one
   fetch.** **245,760** keys are reachable (§ What the real data says); an unbounded map is not a
   design, it is the absence of one. Q2 fixes the cap and the eviction rule. Asserted directly: a
   plant of cap + N distinct failing keys leaves the map at exactly the cap, and the evicted key
   fetches again on its next request — which is the honest cost, asserted rather than described.
   Expired entries are pruned rather than merely ignored, or the cap is reached by garbage.

9. **Nothing is persisted and nothing survives the process.** The negative cache writes no file
   (asserted by listing the cache root after a failing burst — it holds nothing new) and a fresh app
   remembers nothing. That is a *ruling* with a reason, not an omission: `image_fetch_failed` is the
   token this codebase defines as **transient**, restarting the companion is the user's one obvious
   remedy, and a failure state that outlived the restart would make the remedy not work.

10. **A cancelled request is not a failure.** A browser navigating away from a deck view cancels
    ~99 requests; recording those would poison the whole deck for one backoff window from a user
    action that failed at nothing. Asserted directly, and the existing
    `test_a_fetch_still_succeeds_after_a_cancellation` (`:1205`) is the shipped test that must stay
    green — run it explicitly and state which way it went. The mechanism is the narrow `except
    CompanionError` of seam 11: `CancelledError` inherits `BaseException`, so a bare `except
    Exception` would already miss it, and an `except CompanionError` cannot see it at all.

11. **A missing disk cache and a missing negative cache are independent.** An app whose
    `build_image_cache` returned `None` (Q6's disabled-cache path) still negative-caches, and an
    app with a warm disk entry serves it regardless of that key's failure history. Both asserted;
    the second is the ordering claim of seam 2 stated as behaviour.

### The failure posture over time

12. **Whatever Q4 rules about the disk cache learning from its own failures ships with its own
    test, or is declined in `deferred-work.md` with a named home.** The two ledgered entries — a
    transient startup `OSError` disabling the cache for the whole process with one WARNING, and an
    existing-but-unwritable root warning ~99 times per cold paint forever — are both *"the cache's
    failure posture over time"*, which is why they were homed here. Neither may be left as prose.

### The wire contract

13. **The regeneration prediction is confirmed by running the generator, not by argument.**
    `npm run gen:api` is run and `git status --porcelain` is pasted. Expected: **no diff at all** —
    7 paths, 12 components — making this the **third** measured behaviour-only story and settling
    `dump_openapi.py:39`'s forward-dated claim. Any wire-visible docstring edit (`main.py`'s
    `_DOCSTRING_SECTIONS` keeps the leading paragraph and any `Note:`/`Warning:`) makes that false
    and must be regenerated and committed, never hand-edited.

14. **Both drift gates are green from the same commit, output pasted:**
    `uv run pytest tests/unit/companion/test_openapi_contract.py`, and from `ui/`
    `npm run gen:types && git status --porcelain`.

15. **The two forward-dated sentences in `contracts.py` become present tense.** `:104`
    (*"c3-8 adds negative caching and backoff as pure behaviour with no wire change at all"*) and
    `:162` (*"c3-8 owns the negative cache and the backoff; until then a failure is simply not
    cached"*). Both are **wire-visible prose on a shared leaf module**, so each edit is checked
    against AC 13's no-diff claim rather than assumed harmless.

16. **No frontend behaviour ships, and `ui/README.md` gains the blind-spot row this story
    unconditionally owes.** `ui/src` is unchanged. The row is **not** conditional — Q2 as proposed
    produces exactly the c4-4-facing fact that table exists for: **a tile can stay a placeholder
    for up to the ceiling after the CDN has recovered**, because the backend answers from memory
    and the SPA has no per-image retry UI (`EXPERIENCE.md`'s own words). c3-7's review filed a
    patch for leaving precisely this kind of conditional unresolved; do not repeat it. If Q2 is
    overturned, the row states whatever number replaces it. The SPA bundle in both trees is
    **re-measured** against the Task 0 hashes and expected byte-identical (AC 22).

17. **`EXPERIENCE.md`'s promise becomes true and neither it nor its gate is edited.** The *"CDN
    fetch failure … negative-cached with backoff — no request storms, no per-image retry UI"* row
    has been a forward-dated claim since the artefact was exported; `ui/tests/
    named-card-copy.test.ts` holds it byte-for-byte and is predicted to pass **unchanged**. Confirm
    by running it, and state in the record that the UI half of this story was written before the
    backend half — the inverse of the pairing problem AD-16 exists to prevent.

### Boundaries, guards, records and the mirror

18. **`_BANNED_IDENTIFIERS` is resolved per Q5, deliberately, and all four pairings are reworked
    rather than left.** Whichever way it goes, no test in that class may end as `set() == set()` or
    plant a name that is no longer banned. If the set survives, the surviving ban is **stronger**
    than it was (a permanent ruling with a stated reason beats a reservation); if it retires, the
    replacement positive gate is named in the same commit and is stronger than the ban it replaces
    — c3-6's procedure, applied a third time.

19. **The positive gate this story owes, whatever Q5 rules: one construction site, and the map is
    bounded.** Mirrors `TestExactlyOnePacer` — an AST scan of **all of `src/companion`** finding
    exactly one negative-cache construction site, in the lifespan, with a planted aliased second
    site as the firing half — **plus** AC 8's runtime bound. Guard-shaped, therefore paired
    non-vacuously (AC 21), and the plant spelled to evade (c3-3's headline finding: a guard caught
    0 of 12 planted evasions).

20. **No database write path is opened; `test_import_boundary.py` passes unchanged with no
    exclusions added** — run explicitly and pasted. **And the nine `deferred-work.md` entries homed
    on this story are each closed or explicitly re-homed by name**, with what each did not price:

    | # | Entry | Expected disposition |
    | --- | --- | --- |
    | 1 | *A fetch failure is answered and forgotten* (c3-5) | **CLOSED** — this story's headline |
    | 2 | *A refused or unparseable stored URL answers the transient token* (c3-5 review) | **Q3** |
    | 3 | *In-flight coalescing, re-homed from c3-7* (Q5 there) | **Q6 here** |
    | 4 | *No ceiling on how long a request may queue* (c3-6, "if ever") | **Q7 here** |
    | 5 | *Two simultaneous requests both fetch and both write* (c3-7) | resolved by Q6, or re-homed with it |
    | 6 | *A transient startup `OSError` disables the cache for the process* (c3-7 review) | **Q4** |
    | 7 | *An unwritable root warns on every write forever* (c3-7 review) | **Q4** |
    | 8 | *`images.py` holds three mechanisms and is 1,307 lines* (c3-7) | **Q8** — c3-8 **or the C3 retro** |
    | 9 | *`DiskCache` trusts its callers for containment* (c3-7 review) | **Q9** — this story is the named next caller |

21. **`deferred-work.md` gains this story's own residue with named homes**, at minimum whatever
    Q2, Q3, Q4, Q6 and Q7 decline, and the first-paint exposure of § What the real data says (a
    dead CDN still costs one full 124 s paint per process). **No residue in prose only.**

22. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and
    the SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and its mirror
    expected byte-identical against Task 0's five hashes. A change is a finding to explain, not a
    rebuild to wave through (c3-1's finding 1: `plugin/**` is not "not touched").

### Testing

23. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the
    one-construction-site scan is paired with a planted second site spelled to evade; the
    bounded-map assertion is paired with the eviction that *does* happen; the zero-fetch assertion
    is paired with a distinct key that *does* fetch; the no-persistence assertion is paired with a
    disk write that *does* land.

24. **The mechanism's unit tests live in `tests/unit/companion/test_images.py`** beside
    `TestResolveFaceImages`, `TestFetchImage`, the pacer classes and c3-7's cache classes — the
    module owns its mechanisms' unit tests. Route- and app-level behaviour (AC 1-5, 7, 9-11) goes
    in `test_routes_card_image.py`. Reuse `Recorder`, `cdn`, `lifespan_client`, `isolated_data_dir`,
    `image_shapes`, `FakeClock` and `StallableUpstream`; **write no second seam and no third fake**.
    No test touches the network, writes outside `tmp_path`, or sleeps for real time.

25. **At least five mutation probes are run, verified before the verdict and reverted from a file
    backup — never from git** (standing agreement, and c3-7 Debug Log 3: `git checkout` discarded
    uncommitted work mid-probe): (a) the negative-cache **read** removed, so every failure refetches;
    (b) the **record** removed, so nothing is ever remembered; (c) the **expiry** removed, so a key
    fails forever — the permanently-broken-tile defect, which passes every "no second fetch" test;
    (d) the **bound** removed, so the map grows without limit — invisible to every functional
    assertion; (e) the **clear-on-success** removed, so a recovered key keeps its escalated delay;
    and (f) — the c3-5/c3-6/c3-7 shared review theme in this story's costume — the negative check
    moved **inside** `pacer.slot()`, which remembers correctly and paces a remembered failure
    anyway. Paste each result and **read the output before filing it** (c3-6's probe (f) found a
    real hole; c3-7's probe (d) found a gap in its author's own coverage).

26. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus
    the frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`,
    `build`) and both drift checks. Suite counts stated as *before → after*; **the runtime claim is
    made on `tests/unit/companion/` over more than one sample**, per c3-7's ledgered
    measurement-practice note, and no whole-suite delta on this box is read as signal.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is **`3aef5d1`** (PR #35,
        c3-7, merged 2026-08-02); cut `feat/companion-c3-8-negative-cache` from it
  - [x] Run and record with **durations**: `uv run pytest`, `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32` — **plus `uv run pytest tests/unit/companion/`
        three times**, which is the suite AC 26's runtime claim is made on
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/`
        mirror (AC 22); record the committed `paths` (expect 7) and `components` (expect 12)
  - [x] **Verify the corpus numbers yourself**, read-only: 38,261 cards, **245,760** resolvable
        `(id, size, face)` keys, the 0/1/2-face histogram (**79** / 35,404 / 2,778) and the two
        hosts (245,742 / 18). If your corpus differs, the story's numbers are the claim and yours
        are the truth — record the difference
  - [x] **Confirm which of AC 1-3's assertions already exist** before writing any: grep
        `test_routes_card_image.py` for the shipped `no_image_data`/`image_fetch_failed`
        discrimination and the `no fetch is attempted` test, and list what is genuinely new

- [x] **Task 1 — The mechanism** (AC 6, 8, 9; Q1, Q2)
  - [x] The class in `images.py` per Q1 — key, entry shape, injected clock, the backoff schedule
        and the bound, each constant carrying its arithmetic in its own docstring
  - [x] Unit tests **before** wiring it in: the exact expiry boundaries on `FakeClock`, the
        escalation, the ceiling, the prune, the cap and the eviction cost
  - [x] Confirm the prediction that construction cannot fail — so no `build_*` factory, no
        `_shutdown` change, and `test_app.py`/`test_deps.py` need no edit

- [x] **Task 2 — Wiring it in** (AC 4, 5, 7, 10, 11; Q1)
  - [x] The lifespan creates it beside the pacer and the disk cache; the accessor mirrors
        `image_pacer`, and its docstring states what `None` means here
  - [x] The route: check **after** the disk read, **before** the wiring guard, **outside**
        `pacer.slot()`; the narrow `except CompanionError` that records and re-raises; the clear on
        success
  - [x] The one-construction-site scan with its planted evasion (AC 19)

- [x] **Task 3 — The guard, resolved rather than reflexively removed** (AC 18; Q5)
  - [x] Apply Q5's ruling to `_BANNED_IDENTIFIERS` and restate the family comment either way
  - [x] Rework **all four** pairings so none is vacuous and none plants a retired name
  - [x] Re-run `test_import_boundary.py` explicitly and paste it (AC 20)

- [x] **Task 4 — The behavioural half** (AC 1, 2, 3, 4, 4b, 5, 7, 10, 11, 23)
  - [x] The three verification ACs first, with what was already asserted named as such
  - [x] Two failing requests, one recorded URL, and **zero** spacing intervals on the clock
  - [x] The deck-scale pair via `_seed_burst`: 99 fetches cold, **zero** on the second paint — and
        the first-paint exposure written down rather than glossed
  - [x] Byte-identity between the cold failure and the remembered one
  - [x] Recovery: retry after the window, disk-cached, history cleared, next failure at the base
  - [x] Cancellation is not a failure — and run `test_a_fetch_still_succeeds_after_a_cancellation`
        explicitly, stating which way it went
  - [x] No file is written by the negative path; a fresh app remembers nothing

- [x] **Task 5 — The failure posture over time** (AC 12; Q4)
  - [x] Implement or decline per Q4, with a test or a ledger entry — never prose

- [x] **Task 6 — The wire, confirmed rather than assumed** (AC 13, 14, 15, 17)
  - [x] `contracts.py`'s two forward-dated sentences to present tense
  - [x] `npm run gen:api`; paste `git status --porcelain`; state the diff (predicted: **none**)
  - [x] Both drift gates from the same commit; run `named-card-copy.test.ts` explicitly

- [x] **Task 7 — Comments, docs, records** (AC 16, 20, 21, 22; Q3, Q6, Q7, Q8, Q9)
  - [x] Work the nine-entry inherited-deferral table; close or re-home each **by name**
  - [x] Rewrite `images.py`'s *"no negative cache and no backoff — story c3-8"* paragraph; keep
        the in-flight-coalescing paragraph accurate under Q6's answer either way
  - [x] `dump_openapi.py`: c3-8 shipped and needed nothing; name **c3-9** next
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`; set status to `review`

- [x] **Task 8 — Probes** (AC 25)
  - [x] Six mutation probes, each verified and reverted **from a file backup**; paste and **read**
        each result

- [x] **Task 9 — Same-day three-layer review before the PR** *(Brad runs this — `dev-story` stops
      at Task 8 with status `review`)*
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before the PR —
        run 2026-08-02; 3 decisions, 13 patches, 1 deferral, 3 dismissed (findings below)
  - [x] Apply patches, re-run every gate, paste the output — 2461 passed, 1 skipped; all gates
        green (Change Log + Review record additions)
  - [x] Raise the PR into `feat/companion-c3` — **PR #36**, 2026-08-02

### Review Findings

Three-layer review run 2026-08-02 (Blind Hunter + Edge Case Hunter + Acceptance Auditor), diff vs
`3aef5d1`. Production mechanism confirmed sound by all three layers (placement, narrow catch,
clock-proofs, mirror byte-identity all verified); the findings cluster in the new tests, the new
log sites, and the record.

- [x] [Review][Decision] **RESOLVED (Brad, 2026-08-02): accept the shipped design + honest docs.**
      The write-failure counter's transient-safety claim does not survive burst writes — a ~6 s
      transient during a cold paint (~0.8 writes/s) spans 5 *consecutive* writes and permanently
      disables the cache's writes (Q4 declined re-enable). Ruling: keep the design (consequence is
      only lost caching; images still served); becomes a patch — the docstring states the burst
      exposure honestly, and the exposure is ledgered with **Home: c8-2**.
      [`images.py:378,1210-1241`]
- [x] [Review][Decision] **RESOLVED (Brad, 2026-08-02): decline + ledger on c4-4.** The backoff
      502 carries no `Retry-After` header though the route holds `retry_after` when it answers;
      a standard header would give c4-4 one correct action without a new token, but it is a
      wire-visible change this story's rulings excluded. Deferred so the tile author decides with
      the UI in view — ledgered beside the blind-spot row, **Home: c4-4**. [`routes/cards.py:360`]
- [x] [Review][Decision] **RESOLVED (Brad, 2026-08-02): keep ratified.** The wire-crossing
      `ErrorResponse` docstring expansion (which falsified AC 13/16's predictions) stays — the
      JSDoc is genuinely useful to c4-4, the regeneration was done properly, and the falsified
      prediction is honestly recorded. Pairs with the drift-gate patch pinning the published
      30/300 to the constants. [`contracts.py`, `ui/src/api/*`]
- [x] [Review][Patch] Both AC 10 cancellation tests are timing-vacuous: `create_task` →
      `sleep(0)` → `cancel()` lands the `CancelledError` at the route's *first* await (the DB
      read), before the `try` block is entered, with `cdn` in success mode — `entry_count == 0`
      passes even under a record-on-`BaseException` mutation. `StallableUpstream` (shipped for
      exactly this) is unused by any c3-8 test. Park a fetch, cancel mid-flight, then assert.
      [`test_routes_card_image.py:2733-2766`]
- [x] [Review][Patch] `test_the_next_request_for_the_same_key_still_reaches_the_cdn` does not
      request the same key — the cancelled request is `(id, normal, 0)`, the follow-up uses
      `params={"size": "large"}`. This is the change-the-key dodge Debug Log 4 documents repairing
      in the AC 7 test, reshipped under a name that claims "same key".
      [`test_routes_card_image.py:2752-2773`]
- [x] [Review][Patch] The per-hit INFO log on every negative-cache hit reintroduces the log-storm
      class Q4 just closed for writes — ~99 INFO lines per paint, every paint, for the outage's
      duration, unbounded and untested; and symmetrically, nothing logs when a window *opens* or
      escalates, so an operator diagnosing a stuck tile has only repeated hit-lines with no window
      duration. Demote the per-hit line to DEBUG and log once (bounded) at record/escalation.
      [`routes/cards.py:353-359`]
- [x] [Review][Patch] A same-key concurrent-write race loser (the ledgered Windows `os.replace`
      `PermissionError`) now counts toward disabling the disk cache's writes — the tolerated log
      line becomes progress toward a latch. Treat `PermissionError` where the target already
      exists as benign (the racing winner stored the entry). [`images.py:1210-1216`]
- [x] [Review][Patch] `NegativeCache` validates no constructor parameter: `max_entries=0` makes
      `_evict_earliest_expiry` call `min()` on an empty dict (ValueError on the failure path);
      `base > ceiling` leaves the *first* delay unclamped, falsifying `_RememberedFailure`'s
      "already clamped" docstring; `multiplier < 1` silently decays. Only reachable via injected
      kwargs, but tests inject `max_entries=1/2/4`. Clamp the first delay and validate/guard.
      [`images.py:1407-1424,1488-1494`]
- [x] [Review][Patch] The wire prose now hardcodes "30 seconds"/"capped at 300" in
      `ErrorResponse`'s published docstring with no drift gate tying it to
      `NEGATIVE_CACHE_BASE_SECONDS`/`NEGATIVE_CACHE_CEILING_SECONDS` — a future renumbering ships
      a wire contract describing the old schedule, suite green. Add the pin.
      [`contracts.py`, `test_images.py`]
- [x] [Review][Patch] A remembered failure still pays a full DB session, query and face
      resolution per request — correct ordering (token fidelity), but the cost is nowhere stated
      while cheaper orderings' rejections are documented exhaustively. One sentence at the
      placement comment. [`routes/cards.py:334-351`]
- [x] [Review][Patch] `test_the_last_warning_says_the_cache_is_being_disabled` asserts on
      `caplog.records[-1]` unfiltered by logger — any later record from another logger flips it
      for reasons unrelated to its claim. Filter to the images logger.
      [`test_images.py:1907-1909`]
- [x] [Review][Patch] `_evict_earliest_expiry`'s "cost is exactly one extra fetch" undercounts
      when the evicted entry is an expired-but-retained *history* entry: the real cost is that
      key's escalation reset — the very defect `_forget_stale`'s horizon exists to prevent. One
      honest sentence. [`images.py:1551-1559`]
- [x] [Review][Patch] AC 10's explicit-run requirement is unmet in the record:
      `test_a_fetch_still_succeeds_after_a_cancellation` was never named as run, in either
      direction ("run it explicitly and state which way it went"). Run and state.
      [story record, Gates table]
- [x] [Review][Patch] AC 13's pasted-porcelain requirement is unmet — Debug Log 3 narrates the
      diff but no `git status --porcelain` output is pasted anywhere. Run and paste.
      [story record, Debug Log 3]
- [x] [Review][Patch] AC 17's required record statement is missing — "state in the record that
      the UI half was written before the backend half". Add the sentence. [story record]
- [x] [Review][Defer] Concurrent duplicate requests for one key escalate the schedule per-record
      (N duplicates = N steps off one outage instant) and each record slides the window forward —
      documented as deliberate, harmless while duplicates collapse in `deck_cards`, but c6-4's
      duplicate-tile surface makes it the normal case [`images.py:1461-1496`] — deferred, becomes
      real at c6-4; ledgered beside the coalescing entry.

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| A fetch failure and a card with no image data are signalled **distinguishably**; the backend never serves a substitute image | AD-11 | AC 1 — already shipped at c3-5; verify, do not rebuild |
| `ErrorReason` is closed at ten; a new token needs its UI state in the same commit | AD-16, C2 retro R1 | AC 5 adds none, and `contracts.py` predicted that in writing |
| The status is derived from the token, never chosen at the call site | `errors.py` | A negative hit raises the token and nothing else |
| `Cache-Control: no-store` on every typed error, feature-wide | c3-5 | AC 5 inherits it with no code |
| Cache key is **id + size + face**, never the URL | AD-11 | The negative cache uses the same key, for the same reason |
| The pacer wraps the client; a request that issues no request owes the rate nothing | AD-11, c3-7 | AC 4's zero-spacing claim, measured on the clock |
| `build_app()` has zero side effects; the lifespan owns effects | AD-10 | The negative cache is created in the lifespan |
| Publishing the discovery file is the **only** startup step that may fail the launch | AD-15, c3-7 Q6 | A cache that cannot fail to construct keeps that literally true |
| One generator, from the backend's own `app.openapi()` | AD-12 | Never hand-edit `openapi.json` |
| `Note:` and `Warning:` are **wire-visible**; other Google sections are truncated | c3-2 review | A route- or contract-docstring edit is a wire decision |
| Ban the family, never enumerate members | C2 retro, standing | AC 19's scan is family-keyed |
| An unused hook is a design decision made by a story that cannot see the requirements | c3-4 | Q3, Q6 and Q7 all turn on it |
| Probe your own guard before review does | C2 retro, standing | AC 25's six probes are not optional |
| Claims require verification | standing | Paste real output; run the generator, do not predict it |
| Copy lives in `EXPERIENCE.md` and is gated | c2-9 | This story ships **no copy** and no UI state |

### The seven things this story must not break

1. **`test_a_fetch_still_succeeds_after_a_cancellation`** (`test_routes_card_image.py:1205`). It
   cancels a request and then succeeds **on the same key**. It is the shipped test that a
   record-on-any-exception implementation turns red, and it is the reason AC 10 exists.
2. **`test_import_boundary.py`** — both guards, AST-only, unchanged, no exclusions. *"A guard
   satisfied by obfuscation is theatre."*
3. **`test_openapi_contract.py`'s byte comparison** and `test_committed_schema.py`'s whole-artifact
   pin — a docstring edit you did not mean to make is a red CI, and the fix is regeneration, never
   a hand edit. `contracts.py` is a wire module; AC 15 edits it.
4. **`test_app.py::test_startup_failure_propagates`** — it pins that **only** discovery publication
   may fail the launch. A negative cache that cannot fail to construct leaves it untouched; one
   that can, changes a ruling and must say so.
5. **`test_deps.py::test_a_failing_image_client_close_does_not_strand_the_engine_dispose`** — if
   anything new lands in `_shutdown`, that ordering claim must be re-derived. A failure map needing
   teardown is a smell: neither the pacer nor the disk cache needed one.
6. **`TestFileIoNeverRunsOnTheLoop` and `TestExactlyOneImageWriteSite`** (c3-7) — an in-memory
   mechanism leaves both silent, which AC 8's structural half should *assert* rather than assume.
   Q1's persisted alternative makes both of them this story's problem.
7. **The ~40 shipped fetch tests.** Every one of them now traverses a negative cache as well as a
   disk cache. A test whose recorded fetch count changes is either the mechanism working or a key
   collision, and the difference is **read**, not assumed (c3-7 Debug Log 5).

### Source tree — what exists, what this story touches

```
src/companion/app/
  images.py               EDIT — the negative cache (the spine's `app/images.py # proxy: pacer,
                                 disk cache, negative cache` line, :452 — the THIRD and last
                                 mechanism that line names); the backoff constants with their
                                 arithmetic; the "no negative cache" paragraph rewritten; the
                                 in-flight paragraph made accurate under Q6
  main.py                 EDIT — the lifespan creates it; the docstring says why it needs no
                                 factory and no teardown, unlike the disk cache on the line above
  routes/cards.py         EDIT — the check between the disk read and the wiring guard; the
                                 narrow `except CompanionError` that records and re-raises; the
                                 clear on success
src/companion/contracts.py  EDIT (docstrings only) — the two forward-dated c3-8 sentences
                                 (:104, :162) become present tense. WIRE-VISIBLE — verify AC 13
scripts/dump_openapi.py   EDIT (docstring only) — c3-8 shipped and needed nothing; c3-9 next
tests/unit/companion/
  test_images.py              EDIT — the mechanism's unit tests; the one-construction-site scan;
                                 `_BLOCKING_CALLS`/`_FILE_IO_CALLS` verified untouched
  test_routes_card_image.py   EDIT — `_BANNED_IDENTIFIERS` per Q5 and all four pairings; the
                                 zero-fetch/zero-spacing pair; byte-identity; recovery;
                                 cancellation; no-persistence
  test_app.py                 VERIFY — the startup asymmetry (expected untouched)
  test_deps.py                VERIFY — shutdown ordering (expected untouched)
  test_errors.py              VERIFY — the token count pins (expected untouched)
ui/src/api/
  openapi.json, types.d.ts    REGENERATED — expected byte-identical; run it, do not assume it
ui/README.md              EDIT — only if Q2 produces a number c4-4 needs
plugin/**                 REBUILT — required by CI's drift gate
_bmad-output/implementation-artifacts/deferred-work.md   EDIT
```

**Not touched, deliberately:** `src/companion/app/errors.py` (no new token — AC 5),
`src/companion/app/deps.py`, `src/companion/discovery.py`, `src/companion/client.py`,
`src/companion/app/{security,spa,state,singleton}.py`, `src/paths.py`, `src/data/**`,
`src/logic/**`, `src/mcp_server/**`, `src/viewer/**`,
`_bmad-output/planning-artifacts/ux-designs/**/EXPERIENCE.md` (**the copy already exists and is
gated — this story makes it true, it does not write it**), `ui/tests/named-card-copy.test.ts`, and
every file under `ui/src` (**c4-4** owns the tile).

### Previous story intelligence (c3-1 … c3-7, and their eleven review passes)

- **Eighteen of eighteen stories have answered their open questions "as proposed"** (one partial).
  The questions below are written to be answerable the same way, but **Q1, Q2, Q4, Q5 and Q6 are
  genuine forks** — they change what ships, and **Q5's recommendation is deliberately against the
  pattern the last two stories set**.
- **The round-1 Greptile cause is confirmed six times running**: the same-day three-layer
  `bmad-code-review` before raising the PR. Task 9.
- **The shared review theme of c3-5, c3-6 and c3-7 is one shape: a check that runs after — or
  inside — the thing it was meant to prevent.** c3-5's fetch trusted a response `client.get()` had
  already swallowed; c3-6's completion-based spacing passed all 75 unit tests because a mocked
  fetch is instantaneous; c3-7's probe (f) put the cache read inside `pacer.slot()` and was caught
  by **one test out of 911**. This story's version is probe (f) again, and its second version is a
  failure recorded *after* the response is returned. **AC 4 measures the clock and not the bytes
  for exactly this reason.**
- **c3-7's review found seven defects in code the review itself had asked for**, which is the
  argument for probing the *repair* as hard as the original. Two of its Greptile P1s were both in
  review-added code.
- **c3-3's headline finding**: a guard caught **0 of 12** planted evasions. AC 19's scan is the
  guard-shaped thing here, and it will be written by someone who knows exactly how it will be
  spelled.
- **c3-2's finding**: a true count read as a false rule. Applied here: *"zero stored URLs sit
  outside the allow-list"* is true of **this** corpus, measured today. It justifies declining a
  per-cause policy (Q3); it does **not** justify code that misbehaves if one appears, and it must
  not be published as a wire promise.
- **c3-1's R1 finding**: `TestNotShadowedBySpa` passed with the router *deleted*. Applied here: a
  test asserting only "the second response was also 502" passes with the negative cache deleted.
  **Assert the recorded fetch count and the clock**, neither of which a missing mechanism produces.
- **Every story in this epic has hit a structural pin it did not name** (c3-2 Debug Log 3, c3-3
  finding 2, c3-6 Debug Log 2, c3-7 Debug Log 1 — four running). Budget for one. The likeliest
  candidates here: `TestNoRuleInTheShell`'s banned literals in `src/companion` (measured at
  `frozenset({60, 15})` — **`60` is on Q2's proposed schedule**; see Gotchas), and
  `_BANNED_IDENTIFIERS` itself if Q5 goes the retiring way.
- **c3-7 ledgered a measurement-practice note that this story is the first to inherit**: this box's
  whole-suite runtime spreads 49 s across identical runs. Use `tests/unit/companion/`, more than
  one sample (AC 26).

### Git intelligence

- **`3aef5d1`** — PR #35 merged c3-7 into `feat/companion-c3` on 2026-08-02. Story commits on the
  branch: `2f048c0` (feat, incl. 14 folded-in review patches), `7d29438` (records), `bf93dac`
  (PR raised), `23d74b8` (Greptile P1s), `e6e27ba` (Greptile round 2). `2927336` — PR #34, c3-6.
  `4765bc6` — PR #33, c3-5. `a52d6f8` — integration PR #28 on master.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a
  Greptile pass per story**, one integration PR to master after the retro with **no** Greptile pass
  (OSS free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`. The shape to copy: one small `feat`
  commit, then a separate review-patch commit, then the records commit.

### Gotchas specific to this story

- **`functools.cache` and `functools.lru_cache` are banned in `images.py` today**, resolved through
  imports and through the module alias. The suite goes red on your first line if you reach for
  either — and **that red may be correct**; see Q5 before treating it as an obstacle.
- **`60` and `15` are banned literals anywhere in `src/companion`** — `_LIMIT_LITERALS =
  frozenset({60, 15})` (`test_routes_format_check.py:645`), scanned over **every** `.py` file under
  `src/companion` by `TestNoRuleInTheShell`, in any numeric spelling including `60.0`. (`4` was
  *declared out* by c3-6 so `FETCH_CONCURRENCY` could keep its name; `1`, `3`, `5` and `16` were
  already out as ubiquitous.) **Q2's proposed schedule is 30 → 60 → 120 → 240 → 300, so `60` is on
  it — and it is safe only because a base of `30` with a multiplier of `2` never writes `60` as a
  literal.** Spelling the schedule as an explicit tuple `(30, 60, 120, 240, 300)` turns that guard
  red. This is the fourth consecutive story to hit a structural pin it did not name; this one is
  named, greppable and avoidable in advance, so hitting it anyway is a finding about the reading
  rather than about the guard.
- **`Recorder`'s failure knobs (`raises`, `status`) are global to the recorder, not per URL.** A
  test that needs "key A fails, key B succeeds" sets `cdn.raises`, makes A's request, clears it,
  then makes B's — the sequencing is the seam, and AC 4's non-vacuity pairing depends on it. Extend
  `Recorder` only if that genuinely will not express a case, and if you do, extend the one in
  `test_routes_card_image.py` rather than adding another (c3-7 paid the consolidation cost).
- **`time.sleep` and the whole `threading`/`concurrent.futures`/`multiprocessing`/`subprocess`
  family are banned by name in `images.py`** (`_blocking_waits_in`, with import aliases resolved).
  A backoff implemented by sleeping is both a guard violation and a design error: the caller is
  **answered immediately** with the typed failure, never made to wait out the window.
- **`time.monotonic` is the clock, never `time.time`.** A wall clock moves backwards on an NTP
  step and across a DST boundary, which would either free every entry at once or freeze one for an
  hour. `Pacer` already made this choice and its docstring says so.
- **A negative hit must not enter `pacer.slot()`.** Same reasoning as c3-7's warm path: a request
  that issues no request owes the rate nothing, and a check inside the slot would make a remembered
  failure cost a spacing turn against a CDN it never contacts. Probe (f) exists for this.
- **`except CompanionError`, never `except Exception`.** `CancelledError` inherits `BaseException`
  so it escapes both, but a broad catch would record `internal_error` (the wiring bug) as a CDN
  failure and back off a key whose real problem is that the lifespan did not run.
- **The route currently has no `try`/`except` at all** and c3-1's record names that as a property.
  Adding one is unavoidable; adding a *second* is a smell.
- **`mypy --strict` and `--platform win32`** are both gates, and `tests.*` is exempt from strict but
  not from ruff or the naming rules.
- **No new dependency.** `time`, `collections`, `dataclasses` and `typing` are stdlib.
- **Google-style docstrings on every public function; module docstring mandatory; ruff `N`/`UP`
  apply.** Every constant carries its arithmetic, in the manner of `FETCH_SPACING_SECONDS` — a
  number without its reasoning is the thing the next story will change for the wrong reason.
- **Do not write a TTL into the *disk* cache.** AD-11 rules it unbounded and never-evicting, and
  c3-7 shipped that with a measured footprint. The two caches have opposite policies on purpose:
  a success is durable, a failure expires.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that
  exactly one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client`, `isolated_data_dir`, `image_shapes`, `_point_at`, `_seed`,
  `_ready_database`, `Recorder`, `cdn`, `FakeClock` and `StallableUpstream`.
- **No unit test may touch the network, write outside `tmp_path`, or sleep for real time.** A
  backoff test that sleeps is the one thing this story could plausibly get wrong and still pass.
- Paste real gate output. **`npx tsc -b --force` is a separate claim from `npm test`** — c3-2
  measured `tsc -b` caching a clean result over a real failure.

### Architecture rules this story implements

- **AD-11** — *"Failures are negative-cached with backoff; a card with no `image_uris` is never
  fetched"*, and *"the backend never serves a substitute image: a fetch failure and a card with no
  image data are signalled distinguishably so the client renders DESIGN.md's named placeholder."*
  The second half is verified (c3-5 shipped it); the first is built here.
- **FR-04** — the image proxy's failure behaviour, completed.
- **AD-16** — unchanged: no new token, and the closed set stays closed at ten.
- **AD-10** — `build_app()` has zero side effects; the lifespan owns anything with an effect.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; this story's claim is
  that it produces **no diff**, settled by running it.
- **NFR-05** — the 250 ms push budget: an in-memory dict lookup is not a thread hop and not a file
  read, which is why Q1's in-memory option needs no `asyncio.to_thread` and Q1's persisted option
  would.
- **UX-DR22 / `EXPERIENCE.md`** — the named Card placeholder, and the *"no request storms, no
  per-image retry UI"* promise this story makes true.

### Latest technical information (external — banked by c3-5 on 2026-08-01, do not re-research)

- **Scryfall asks consumers to cache what they download for at least 24 hours** — c3-7's, and
  already written into `DiskCache`'s docstring. Nothing here changes it; stated so it is not
  re-derived.
- **Sustained traffic under 10 requests/second with 50–100 ms between calls; excess earns `429` and
  a ~30-second lockout** — **but the `*.scryfall.io` file origins this route fetches from are
  explicitly exempt.** Already written into `FETCH_SPACING_SECONDS`' docstring and gated by a test.
  Worth one thought here that the earlier stories did not need: **a `429` is an ordinary non-2xx
  and therefore an `image_fetch_failed`**, so it is a failure this story now backs off from — which
  is the one place where the negative cache doubles as rate-limit courtesy rather than only as a
  storm guard. Say it if it is true of your implementation; do not claim compliance the exemption
  makes unnecessary.
- A descriptive `User-Agent` is required — shipped by c3-5's `_user_agent()`.

Sources: [Scryfall API rate limits](https://scryfall.com/docs/api/rate-limits) ·
[Scryfall API docs](https://scryfall.com/docs/api)

### References

- [epics-companion-app.md § Story 3.8](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (1776-1803); **3.7's cache** (1741-1774), already shipped; **3.9** (1805-1833),
  whose scope this one must not absorb; **Story 8.2** (3185-3212), which owns cache stewardship;
  **Story 10.3** (3560-3599), which owns real-bytes and real-latency profiling; UX-DR22 (453)
- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) —
  **AD-11 (242-270)**, AD-10, AD-12, AD-15, AD-16, and the Structural Seed's
  `app/images.py  # proxy: pacer, disk cache, negative cache` line (452)
- [c3-7 story record](c3-7-sharded-atomically-written-disk-cache.md) — the disk cache, the
  lifespan pattern, the Q6 disable-don't-fail ruling, the 14 review patches, the two Greptile
  rounds, and the **procedure for taking down a family of `_BANNED_IDENTIFIERS`**
- [c3-6 story record](c3-6-paced-concurrency-capped-cdn-fetching-at-one-global-choke-point.md) —
  the pacer, the injected clock, and probe (f)
- [c3-5 story record](c3-5-card-image-endpoint-with-face-resolution-and-a-defined-parameter-contract.md) —
  the two image tokens, the route, and the banked Scryfall research
- [deferred-work.md](deferred-work.md) — the **nine c3-8-homed entries** enumerated in AC 20
- [EXPERIENCE.md](../planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md) —
  the *"CDN fetch failure"* row (128) this story makes true, and the *"Card with no image data"*
  row (127) c3-5 already satisfied
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — the standing agreements (ban the
  family; probe your own guard; same-day three-layer review) and R1's token+copy pairing rule
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — What shape is the negative cache, and does it persist?** *(genuine fork)*

| Option | Verdict |
| --- | --- |
| **A `NegativeCache` class in `images.py`, in-memory, one instance created in the lifespan beside `Pacer` and `DiskCache`, injected clock, reached through a `negative_cache(app)` accessor** | **Proposed.** It mirrors the two mechanisms already in this module exactly — same file, same creation site, same accessor shape — and it is `Pacer`-shaped rather than `DiskCache`-shaped in the one way that matters: **constructing it cannot fail**, so no `build_*` factory, no `_shutdown` change, and the startup asymmetry `test_app.py::test_startup_failure_propagates` pins stays literally true. In-memory also means **no file I/O**, which keeps c3-7's `TestFileIoNeverRunsOnTheLoop` and `TestExactlyOneImageWriteSite` silent and needs no `asyncio.to_thread` hop on the hot path. Non-persistence is the *substantive* half and it is a ruling with a reason: `image_fetch_failed` is defined as **transient**, restarting the companion is the user's one obvious remedy, and a failure that outlived the restart would make that remedy not work |
| Persist it beside the disk cache | **The real alternative.** It would survive a restart, which for a genuinely dead CDN saves one wasted paint per launch. Rejected because it inverts the token's own meaning, because it re-opens the atomic-write question for a *negative* fact (a truncated failure record read as a failure is a permanently broken tile — the exact defect `_read_cached`'s zero-byte check exists to prevent), and because it makes a bounded map an unbounded file with no eviction policy that AD-11 declines to design |
| Module-level dict in `images.py` | **Rejected** on `deps.Database`'s shipped ruling against module globals: it would share failure state across every app in a test run and hide a real double-creation bug behind a global. Per-app instances are what make AC 9's "a fresh app remembers nothing" testable at all |

*Sub-question, and it decides where three lines go: does the **route** record the failure (a narrow
`except CompanionError` around `fetch_image` that records and re-raises), or does `fetch_image`
take the cache?* **Proposed: the route.** `fetch_image` is given a URL and the key is
id + size + face; handing it a key it does not otherwise need would widen the one function whose
narrow signature is the reason no caller can fetch unpaced. The cost, stated: this is the first
`try`/`except` in `routes/cards.py`, and c3-1's record names its absence as a property.

*Recommendation: as proposed, both parts.*

---

**Q2 — What are the numbers: base delay, growth, ceiling, and the cap on entries?** *(genuine fork)*

AD-11 says *"negative-cached with backoff"* and nothing more; `EXPERIENCE.md` says *"no request
storms, no per-image retry UI"*. Both are satisfied by a wide range of numbers, so the numbers need
arithmetic rather than taste — in the manner of `FETCH_SPACING_SECONDS`, whose docstring derives
0.1 s from the epic's own acceptance observation.

**Proposed:**

| Constant | Value | The arithmetic |
| --- | --- | --- |
| Base delay | **30 s** | It must exceed **one full cold deck paint**, or a second paint that begins after the first ends re-admits the storm. A cold 99-tile paint is 9.9 s at the shipped spacing; 30 s is ~3× that, and comfortably longer than a human reload cycle |
| Growth | **× 2** per consecutive failure | Five steps from base to ceiling — enough to distinguish a blip from an outage without a schedule nobody can hold in their head |
| Ceiling | **300 s** | A genuinely dead CDN settles at one attempt per tile per five minutes. It bounds the *"broken until"* window a user experiences after recovery, which is the number c4-4 would want in `ui/README.md` (AC 16) |
| Max entries | **2,048** | This user's **whole 40-deck library is 1,061 distinct card ids**; at the grid's one size that is 1,061 keys, so 2,048 is ~2× the worst realistic working set and ~0.8 % of the 245,760 reachable keys. Bounded memory, and eviction is only ever reachable by a failure pattern no real session produces |
| Eviction | prune expired on insert; if still at the cap, drop the entry with the **earliest** `retry_after` | Expiry-first is free and correct; the tiebreak drops the entry closest to being useless anyway. **Cost of an eviction is exactly one extra fetch**, which is the honest statement and is what AC 8 asserts |

**None of `30`, `2`, `300` or `2048` is in `TestNoRuleInTheShell`'s banned literal family
(`{60, 15, 4}`) — checked. Re-check at Task 0 rather than trusting this sentence.**

*The real alternative* is a flat cooldown with no growth — simpler, one constant, and it satisfies
the AC's letter. Rejected because *"with backoff"* is the AC's actual word and because a flat
cooldown treats a one-second blip and a week-long outage identically. If Brad prefers it, the
ruling wants the flat number in the docstring with the same arithmetic.

*Recommendation: as proposed, with every number carrying its arithmetic in its own docstring.*

---

**Q3 — Does the backoff policy distinguish permanent failures from transient ones?**

c3-5's review homed this here by name: an `is_fetchable` refusal or an unparseable stored URL
answers `image_fetch_failed` — the transient token — though the refusal is a permanent fact of the
row, and *"c3-8, which owns the negative cache and backoff, decides retry semantics for
permanently-failing URLs (e.g. an unbounded/permanent negative-cache entry for `is_fetchable`
refusals)."*

Proposed: **no — one uniform policy, and record why.** Three reasons, in order of weight:

1. **The class is unreachable against this corpus.** All 245,760 stored URLs are on the two
   allow-listed hosts; **zero** would be refused. A permanent-entry branch would be an unused hook
   — c3-4's ruling exactly.
2. **`fetch_image` deliberately collapses every cause into one token**, and its docstring argues
   that collapse at length. Distinguishing here means either widening that contract or
   re-implementing `is_fetchable` at the call site — a second truth about which URLs are fetchable,
   which is the thing AD-1 exists to prevent.
3. **The cost of getting it wrong is asymmetric.** A permanent entry for a URL that was *not*
   permanently bad is a tile broken until restart; a 300 s ceiling on a URL that *is* permanently
   bad costs one request per five minutes against a host that answers instantly.

*Recommendation: as proposed — uniform, with the c3-5 review entry closed by name and the corpus
measurement recorded as the evidence.*

---

**Q4 — Does the disk cache learn from its own failures?** *(genuine fork — this is the one that
can double the story)*

Two `deferred-work.md` entries from c3-7's review are homed here, both described as *"the cache's
failure posture over time"*:

* a **transient** startup `OSError` disables the disk cache for the whole process, announced by one
  WARNING at boot, with no retry and no re-attempt on first write; and
* a root that **exists but is unwritable** leaves the cache "enabled" and logs a WARNING on every
  write — ~99 times per cold deck paint, forever.

| Option | Verdict |
| --- | --- |
| **Take the second only: a consecutive-write-failure counter that disables the disk cache and logs once** | **Proposed.** It closes the louder of the two entries with one small mechanism that belongs to the story that is already reasoning about *"how many times do we try before we stop"*, and it is the same shape as the backoff: a count, a threshold, a state change. The first entry is then re-homed with an honest reason: retrying the root creation means deciding *when*, which is a lifecycle question (at first write? on a timer?) that this story has no requirement to answer |
| Take both | **The real alternative.** A lazy re-attempt of `mkdir` on first write after a startup failure is genuinely small. Rejected because it makes `DiskCache` mutable in a way it is not today, and because it needs a second policy (how often to re-attempt) that nothing measures |
| Decline both, re-home on c8-2 | **The honest minimum**, and defensible: neither entry is a defect — requests are unharmed in both cases (c3-7 AC 9) — and c8-2 owns cache stewardship. Rejected as *proposed* because "logs 99 WARNINGs per deck paint forever" is the kind of thing that reads as broken to the first user who opens a log, and it is cheap here |

*Recommendation: as proposed — take the second, re-home the first on c8-2 beside the stewardship
entry, and say plainly in the record which of the two was taken and why.*

---

**Q5 — Does `_BANNED_IDENTIFIERS` retire, or become a permanent ruling?** *(genuine fork, and the
recommendation is deliberately against the pattern)*

c3-6 removed its family and c3-7 removed its family, each replacing it with a stronger positive
gate. The set is now two names — `functools.cache`, `functools.lru_cache` — under the comment *"the
LAST family in this set"*, and the reflex is to complete the pattern.

| Option | Verdict |
| --- | --- |
| **Keep the ban, restate the comment: it stops being a *reservation* and becomes a *ruling*** | **Proposed.** The two predecessors' families were banned **because their story had not happened yet** — the day c3-6 and c3-7 shipped, each ban fenced the thing that was built, which is why removal was correct. These two were banned for that reason **and for a second one that outlives this story**: `functools.cache`/`lru_cache` cannot express a TTL (a remembered failure would never expire — the permanently-broken-tile defect AD-11's *"with backoff"* exists to prevent), and `cache_clear()` is all-or-nothing, so AC 7's clear-a-single-key-on-recovery is unimplementable on top of it. **They are still the wrong tool the day this story ships**, so the fence is not around the thing that was built. Restating the comment costs one paragraph and **all four pairings keep their teeth with no rework at all** — which is the cheapest outcome as well as the most honest one |
| Retire the set and replace it with a positive gate | **The real alternative**, and it has the pattern behind it. The replacement would be AC 19's one-construction-site scan plus AC 8's bounded-map property. Rejected because a positive gate that says *"there is exactly one negative cache and it is bounded"* does **not** say *"and it is not a `functools` memoisation"* — the two claims are orthogonal, and a bounded single instance built on `lru_cache` would satisfy the new gate while reintroducing the defect the old ban prevented. **Retiring it would be the first removal in this epic that loses coverage rather than replacing it** |
| Keep it and add the positive gate anyway | **This is what AC 18 + AC 19 actually ask for** under the proposed option — the ban is not a substitute for the construction-site scan, and the scan is not a substitute for the ban |

*Recommendation: as proposed — keep the ban, rewrite its comment from "reserved for c3-8" to "the
wrong tool, permanently, and here is why", re-aim `test_no_negative_cache_is_built` (which becomes
false the day you ship) at the surviving claim, and add the positive gate on top rather than
instead. State in the record that this is the first family in this epic that was **not** removed by
the story that owned it, and why.*

---

**Q6 — Does this story take in-flight coalescing?** *(genuine fork, third time of asking)*

c3-6 declined it for not knowing the result's shape. c3-7 built that shape (bytes on disk) and
declined it anyway, re-homing it here with a specific reason: *"c3-8 needs the same structure for a
different question — is a fetch for this key already in flight, or already known-failed? — so an
in-flight map built here for successes only would be inherited wrong or replaced. One mechanism,
built once, by the story that can see both halves."*

| Option | Verdict |
| --- | --- |
| **Decline a third time; re-home on c6-4, the trigger both predecessors named** | **Proposed, and the reasoning c3-7 wrote turns out not to survive contact.** A negative cache does **not** need an in-flight state to be correct: a request whose fetch is in flight simply also fetches, and the failure is recorded when it fails. *"Is a fetch already in flight"* was c3-7's phrasing of a hypothetical, not a requirement of anything in AC 4-11. What coalescing actually shares is a **124 KB payload across two awaiting requests** — a `Future` holding bytes, with its own failure modes (a cancelled leader, an exception fanned out to followers) needing their own tests — and that is a different mechanism from a small expiring failure record, not the same one. Measured value today remains **zero extra fetches** on both 99-distinct-id decks, because duplicate printings collapse in `deck_cards` before they reach the route. c3-4's unused-hook ruling applies unchanged |
| Take it | **The real alternative**, and it has c3-7's explicit expectation behind it, which is a genuine argument on its own — three consecutive declines is a pattern worth Brad's eye rather than an agent's. It is ~15 lines, and it would close the ledgered Windows `os.replace` `PermissionError` race (entry 5 of AC 20's table) rather than leaving it as a tolerated log line |

*Recommendation: as proposed — decline, re-home on **c6-4** with the trigger restated, and record
that the reason changed **again**: c3-6 declined it for not knowing the result's shape, c3-7 for
the shape being shared with this story's, and c3-8 because that sharing turned out not to be real.
If Brad prefers to take it, it is a Task of its own with its own ACs, not a rider on Task 2.*

---

**Q7 — Does this story add a ceiling on how long a request may queue?**

c3-6 ledgered it *"Home: c3-8, if ever"*, on the reasoning that a queue ceiling only becomes
meaningful once something owns retry semantics that would make a caller act differently on it.

Proposed: **no.** The natural bound is still the caller — a client that disconnects cancels the
request and releases its slot, pinned two ways. A ceiling would answer `image_fetch_failed` for a
request that never reached the CDN, which this story would then **negative-cache for 30 seconds**:
a queue that is merely long would start manufacturing remembered failures, which is strictly worse
than the queue. That is a new argument the entry did not have, and it is worth recording as the
reason rather than repeating "no measured symptom".

*Recommendation: as proposed — decline, and update the ledger entry with the new reason.*

---

**Q8 — Does `images.py` split now that it holds all three mechanisms?**

`deferred-work.md` homes this on *"c3-8 or the C3 retro"*. The file is **1,307 lines** at
`3aef5d1` and this story adds a fourth section to it.

Proposed: **no split here; re-home on the C3 retro** with the final measured line count. The spine
draws all three mechanisms inside `app/images.py` (`# proxy: pacer, disk cache, negative cache`),
so splitting is a decision to diverge from the spine — which belongs to a retro with all three
shipped and c4-1's hydration cache in view, not to the story that adds the third while writing it.

*Recommendation: as proposed. Record the post-story line count so the retro inherits a number.*

---

**Q9 — Does `DiskCache` gain containment validation, or restate its trust chain?**

c3-7's review declared a blind spot: `path_for("../../..", …)` escapes the root, and the route's
`_CARD_ID_PATTERN`, closed `ImageSize` and bounded `face` are the whole guard — *"the module's next
callers are already named — c3-8's negative cache in this same file, c6-4's suggestion tiles — and
the first one that passes an unvalidated id gets a traversal write. **Home: c3-8**, which touches
this class next and should either validate at the class boundary or restate the trust chain."*

Proposed: **restate, and say precisely why the answer is not "validate".** The negative cache
**builds no path** — it is a dict keyed on a tuple — so it cannot be the caller that turns an
unvalidated id into a traversal write, and adding validation to `DiskCache` on its account would be
protecting against this story rather than because of it. What this story owes is the restatement:
the trust chain is the route's three constraints, it is named in `DiskCache`'s docstring, and
**c6-4 is now the sole remaining named caller** and inherits the entry.

*Recommendation: as proposed — restate, re-home the entry on c6-4, and record that the reason this
caller is safe is structural (no path) rather than a promise.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5[1m]`), via `bmad-dev-story`.

### Open questions — Brad's answers

Answered 2026-08-02, before any code was written. **All nine "as proposed" — the 19th story
running**, and this time that phrase is doing more work than usual: Q5's proposal was deliberately
*against* the pattern its two predecessors set, and Q6's proposal explicitly overturns the reason
c3-7 wrote when it re-homed the entry here.

| Q | Ruling |
| --- | --- |
| **Q1** | **As proposed, both parts.** A `NegativeCache` class in `images.py`, in-memory, one instance created in the lifespan beside `Pacer` and `DiskCache`, injected clock, reached through a `negative_cache(app)` accessor. Construction cannot fail → no `build_*` factory, no `_shutdown` change, `test_app.py::test_startup_failure_propagates` untouched. **The route records the failure**, via a narrow `except CompanionError` around `fetch_image` — the first `try`/`except` in `routes/cards.py`, taken deliberately rather than widening `fetch_image`'s signature |
| **Q2** | **As proposed.** Base **30 s**, growth **× 2**, ceiling **300 s**, cap **2,048** entries; eviction prunes expired on insert and then drops the earliest `retry_after`. Every number carries its arithmetic in its own docstring |
| **Q3** | **As proposed — one uniform policy.** No permanent-vs-transient split. The class is unreachable against this corpus (all 245,760 stored URLs sit on the two allow-listed hosts), `fetch_image`'s one-token collapse stays closed, and the error cost is asymmetric. The c3-5 review entry is closed by name with the corpus measurement as its evidence |
| **Q4** | **As proposed — take the second only.** A consecutive-write-failure counter that disables the disk cache and logs **once**, closing the "~99 WARNINGs per cold paint forever" entry. The transient-startup-`OSError` entry is re-homed on **c8-2** |
| **Q5** | **As proposed — keep the ban, and restate it as a permanent ruling.** `functools.cache`/`lru_cache` cannot express a TTL and `cache_clear()` is all-or-nothing, so AC 7's clear-one-key-on-recovery is unimplementable on them: they are still the wrong tool the day this story ships. The positive gate (AC 19) is added **on top**, not instead. **The first family in this epic not removed by the story that owned it** |
| **Q6** | **As proposed — decline a third time, re-home on c6-4.** And record that the reason changed *again*: c3-6 declined for not knowing the result's shape, c3-7 for the shape being shared with this story's, and c3-8 because that sharing turned out not to be real — a negative cache needs no in-flight state to be correct |
| **Q7** | **As proposed — no queue ceiling**, with the new argument recorded: a ceiling would answer `image_fetch_failed` for a request that never reached the CDN, which this story would then negative-cache for 30 s, so a merely-long queue would start manufacturing remembered failures |
| **Q8** | **As proposed — no split here; re-home on the C3 retro** with the final measured line count |
| **Q9** | **As proposed — restate, do not validate.** The negative cache builds no path, so it structurally cannot be the caller that turns an unvalidated id into a traversal write. **c6-4** becomes the sole remaining named caller and inherits the entry |

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-8-negative-cache` cut from **`3aef5d1`**, confirmed as the tip of
`origin/feat/companion-c3` (PR #35, c3-7). `git diff HEAD 3aef5d1` was **empty** — the merge commit's
tree is identical to `e6e27ba`, so the cut carried the working tree with no conflict.

**Gates, before any change:**

| Gate | Result |
| --- | --- |
| `uv run pytest` | **2392 passed, 1 skipped — 178.70 s** |
| `uv run pytest tests/unit/companion/` ×3 | **917 passed, 1 skipped** — 47.03 s / 47.69 s / 44.14 s |
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 305 files already formatted |
| `uv run mypy src/` | Success: no issues found in 89 source files |
| `uv run mypy src/ --platform win32` | Success: no issues found in 89 source files |
| `ui/ npm run lint` | clean (eslint + stylelint) |
| `ui/ npm run format:check` | All matched files use Prettier code style! |
| `ui/ npx tsc -b --force` | exit 0 |
| `ui/ npm test` | **31 files / 568 tests passed** |
| `ui/ npm run build` | built in 144 ms, exit 0 |

**FINDING — the inherited baseline was stale in both numbers.** The story text carries c3-7's
*"2395 passed, 1 skipped — 123.40 s"*. Measured here at the same tree: **2392 passed** and
**178.70 s**. The count is three tests lower and the runtime 55 s higher. Neither is a defect —
c3-7's own ledgered measurement-practice note says this box spreads ~49 s across identical runs, and
178.70 vs 123.40 is inside that once the machine is loaded — but *"the story's numbers are the claim
and yours are the truth"* applies to the suite count as much as to the corpus, and **2392 → after**
is the pair AC 26 is stated against. This is the fourth consecutive story whose inherited baseline
did not survive being re-measured (c3-6 found 2286 where 2275 was claimed).

**AC 26's narrow suite is vindicated by its own baseline, and this is worth stating because c3-7
could only assert the negative.** Three consecutive runs of `tests/unit/companion/` on identical code
spread **3.55 s** (47.03 / 47.69 / 44.14). The whole suite spreads ~49 s on this box. So the narrow
suite is not merely *smaller* — it is roughly **fourteen times more repeatable**, which is what makes
a before→after runtime claim on it supportable where the whole-suite one is not.

**MEASUREMENT-PRACTICE NOTE, new and worth carrying forward.** Chaining `npx tsc -b --force` and
`npm test` in **one** PowerShell invocation produced a spurious `Test Files 30 passed (31) /
Tests 564 passed (568) / Errors 1 error`. Run standalone immediately afterwards, the identical tree
gave **31/31 and 568/568**. The two commands contend over the TypeScript build state, so a chained
run is not a measurement of either. Every frontend gate below was run as its own invocation, and
c3-2's finding that *"`npx tsc -b --force` is a separate claim from `npm test`"* now has a second
half: it is also a separate **invocation**.

**Corpus, re-verified read-only against the live 38,261-card database — every number in the story
confirmed exactly, none corrected:**

| Property | Story's claim | Measured |
| --- | --- | --- |
| Cards | 38,261 | **38,261** ✓ |
| Distinct `(id, size, face)` keys resolvable | 245,760 | **245,760** ✓ |
| Cards resolving to 0 faces | 79 | **79** ✓ |
| Cards resolving to 1 face | 35,404 | **35,404** ✓ |
| Cards resolving to 2 faces | 2,778 | **2,778** ✓ |
| `cards.scryfall.io` / `errors.scryfall.com` | 245,742 / 18 | **245,742 / 18** ✓ |
| URLs outside the allow-list or not `https` | 0 | **0** ✓ |

The last row is the whole of **Q3**'s evidence and it was measured rather than inherited: an
`is_fetchable` refusal is unreachable against this corpus, so a permanent-failure branch would be
c3-4's unused hook exactly.

**Committed wire artefacts:** `ui/src/api/openapi.json` holds **7 paths** and **12 components**,
matching the story's enumeration name for name.

**SPA bundle SHA-256 (first 16), identical in `src/companion/app/static/` and the
`plugin/server/src/companion/app/static/` mirror** — all five match the story's Task 0 values:

```
index-DE70muY2.js                                FAEEEA472ADD5078
index-DmxBiI94.css                               0A3C142D84B5A98D
space-grotesk-latin-wght-normal-BhU9QXUp.woff2   0640890476FC1198
favicon.svg                                      9BE16EA2FE3670DE
index.html                                       8E65C0615CF66044
```

**Toolchain, re-confirmed and matching c3-7's measurement in every entry:** Python **3.12.13** ·
FastAPI **0.140.0** · Starlette **0.48.0** · SQLAlchemy **2.0.44** · Pydantic **2.12.0** · httpx
**0.28.1** · anyio **4.11.0** · uvicorn **0.51.0**.

**Structural pin re-checked rather than trusted (Gotchas):** `_LIMIT_LITERALS` is
`frozenset({60, 15})` at `test_routes_format_check.py:645`, scanned as an integer constant *anywhere*
under `src/companion` in any numeric spelling. **None of `30`, `2`, `300` or `2048` is a member**, so
Q2's constants are safe — and they are safe only because the schedule is spelled as
`base × multiplier` with a ceiling. An explicit `(30, 60, 120, 240, 300)` tuple would write `60` as a
literal and turn that guard red.

**AC 1-3 — which assertions already exist, established by reading before writing any:**

| Claim | Status at `3aef5d1` |
| --- | --- |
| A card with no artwork answers `404 no_image_data` | **Exists** — `test_shape_d_answers_no_image_data` (`:183`) and four more |
| A CDN failure answers `502 image_fetch_failed` | **Exists** — `TestUpstreamFailures`, six cases (`:525-596`) |
| The failure half serves no substitute image, asserted on the **bytes** | **Exists** — `test_a_failure_never_returns_a_substitute_image` (`:586`): content-type, body equality and `len(content) < 100` |
| The **`no_image_data`** half serves no substitute image, asserted on the bytes | **NEW** — every existing assertion on that half is status + `.json()`, never the body length or the content type |
| The two answers asserted as a **discrimination from one test** | **NEW** — the two tokens are proved in separate classes on separate fixtures; nothing pins that they differ |
| No fetch is attempted for a card with no image data | **Exists** — `:238` plus its non-vacuity pair at `:247` |
| …and no **negative entry** is created for it | **NEW** — the mechanism does not exist yet |
| `GET /api/cards/{card_id}` carries name, mana cost and type line | **Exists** — c3-2's route and its tests |
| The SPA maps both tokens to the `named-card` placeholder | **Exists** — `states.test.ts:65-80`, including the `not.toBe('unknown-card')` discrimination |

So AC 1-3 are three genuinely new assertions on top of a claim that is otherwise already proved,
which is exactly what the story predicted and the reason they are verification ACs.

### Debug Log References

**1 — The first implementation of the mechanism was wrong in a way three of my own unit tests
caught immediately, and the distinction is the most important thing in this story.** I wrote
`_prune_expired` to drop entries at `retry_after` — the obvious reading of "expired". Three tests
went red at once, all escalation tests. The reason is that **a window closing means *this key may
be fetched again*; it does not mean *this key never failed*.** Dropping the entry at `retry_after`
resets the count on every attempt, so a key against a permanently dead CDN cycles at the base 30 s
forever and the schedule AC 6 specifies is **unreachable in production** — while a naive escalation
test still passes, because it steps the clock only as far as it must. The fix is a retention horizon
of `retry_after + ceiling`: the entry outlives its own window by one full ceiling, and only then is
the key forgotten. That is a **fifth number Q2 did not fix**, so it is derived from the ceiling
rather than declared, documented on `_forget_stale`, asserted from both sides, and ledgered.

**2 — The escalation cannot be computed from a failure count, and that is a real overflow rather
than a hypothetical.** `base * multiplier ** (count - 1)` raises `OverflowError` once a key has
failed a few thousand times — reachable on a tab left open against a dead CDN. The entry therefore
stores the **delay**, carried forward and clamped each step, which is O(1), cannot overflow and
produces an identical schedule. Recorded because the count-based version is what a reader would
expect to find.

**3 — AC 13's central prediction is FALSE, and it was settled by running the generator exactly as
`dump_openapi.py` insisted.** The story predicted "no diff at all" and this being the **third**
measured behaviour-only story. Measured: **7 paths and 12 components before and after** — the
structural half held perfectly, and no reason token was added — but `npm run gen:api` produced a
**real diff in both generated files**, because AC 15's own required edit to `ErrorResponse`'s class
docstring crosses the wire. Two things were learned that nobody gets right from first principles:

* **a class docstring on a Pydantic wire model is published in its entirety** — bullet list and
  all, not merely its leading paragraph (the Google-section truncation rule applies to *route*
  docstrings); and
* **an attribute docstring on a `Literal` type alias is not published at all** — the same commit's
  edit to `ErrorReason`'s docstring, twelve lines away in the same file, did not cross the wire.

Two docstrings, one file, opposite sides of the boundary. The edit was **kept** rather than reverted,
on c3-2's and c3-3's precedent: c4-4's tile author now reads the 300-second recovery window in the
generated JSDoc where they work. `dump_openapi.py` is rewritten to record the corrected rule and
names **c3-9** next. **This story is not the third behaviour-only story, and the record says so.**

**4 — Probe (e) found a real hole in the test I wrote specifically for that acceptance criterion.**
Deleting the route's `clear`-on-success call left **all 980 tests green**. The cause: my route-level
recovery test switched to `size=large` after the recovery to dodge the warm disk cache — which
changes the *key*, so the second failure landed on a key that had never failed and the assertion
held whether or not anything was cleared. Repaired by disabling the disk cache for that test so the
**same** key can succeed and fail again; the probe then fired. This is c3-7's probe (d) repeating
exactly — *the probe found a gap in its author's own coverage* — and it is the second consecutive
story where that happened.

**5 — Probe (f) was caught by exactly 2 tests out of 981, and both are the clock-measuring ones.**
The negative check moved inside `pacer.slot()` remembers perfectly: every fetch-count assertion,
every byte-identity assertion and every status assertion passed. Only `test_a_second_request_adds_
no_fetch_and_no_spacing…` and the deck-scale test saw it. That is the c3-5/c3-6/c3-7 shared review
theme reproduced for a fourth story running, and it is the whole argument for AC 4 measuring the
injected clock rather than the response.

**6 — The inherited baseline was stale in both numbers, and the narrow suite is measurably the
right instrument.** The story carried c3-7's *"2395 passed — 123.40 s"*; measured at the same tree,
**2392 passed — 178.70 s**. Separately, three runs of `tests/unit/companion/` on identical code
spread **3.55 s** against the whole suite's ledgered 49 s — so the narrow suite is roughly
**fourteen times more repeatable**, which is what makes AC 26's runtime claim supportable at all.

**7 — A measurement-practice note that cost a false red.** Chaining `npx tsc -b --force` and
`npm test` in one PowerShell invocation reported `30 passed (31) / 564 passed (568) / 1 error`. The
identical tree run standalone gave **31/31 and 568/568**. The two contend over the TypeScript build
state, so a chained run measures neither. c3-2 established that `tsc -b --force` is a separate
*claim* from `npm test`; it is also a separate **invocation**.

**8 — The structural pin this story was warned about did NOT fire, because the warning was heeded.**
`_LIMIT_LITERALS = frozenset({60, 15})` bans `60` anywhere under `src/companion`, and Q2's schedule
runs 30 → 60 → 120 → 240 → 300. It is safe only because the schedule is computed as
`previous x multiplier` and never written as a literal tuple. Re-checked at Task 0 rather than
trusted, and written into `NEGATIVE_CACHE_MULTIPLIER`'s docstring so the next author does not
"simplify" it into a tuple. **Five consecutive stories have hit an unnamed structural pin; this one
was named in advance and avoided**, which is the first time that has happened in this epic.

**9 — `ui/README.md` failed `format:check` on the first pass.** The blind-spot row I added was not
Prettier-formatted. Fixed with `npx prettier --write`; noted because the row is a table cell long
enough that the failure is easy to miss locally and would have been a red CI.

### Probe outputs

Six probes, each **verified on disk before the verdict** and each **reverted from a file backup and
re-verified by SHA-256** — never from git (c3-7's Debug Log 3, where `git checkout` discarded
uncommitted work mid-probe). Pre-probe hashes: `cards.py C6B2959564FA8AEF`, `images.py
9637BECE23189DB2`; both matched exactly after every revert.

| # | Mutation | Result | What it tells you |
| --- | --- | --- | --- |
| **(a)** | the negative-cache **read** disabled (`if False and …`) | **6 failed**, 974 passed | Every failure refetches. Caught broadly, as expected of the headline behaviour |
| **(b)** | the **record** disabled | **7 failed**, 973 passed | Nothing is ever remembered. One more than (a) — `test_but_a_real_fetch_failure_does_leave_one`, the non-vacuity pair for AC 2, which (a) leaves intact |
| **(c)** | the **expiry** removed (`is_backing_off` returns on presence alone) | **4 failed**, 976 passed | The permanently-broken-tile defect. **It passes every "no second fetch" test**, exactly as the story predicted; only the two expiry-boundary units and both recovery tests see it |
| **(d)** | the **bound** disabled | **3 failed**, 977 passed | The map grows without limit. **Invisible to every route-level assertion** — all three catches are unit tests, which is the argument for AC 8 having units at all |
| **(e)** | **clear-on-success** disabled | **PASSED 980/980 — a real hole** | See Debug Log 4. My own AC 7 test dodged the disk cache by changing the key and stopped testing recovery. Repaired, re-run under the same mutation: **1 failed** |
| **(f)** | the negative check moved **inside** `pacer.slot()` | **2 failed**, 978 passed | The shared review theme, fourth story running. Remembers correctly; paces a request it never sends. **Caught by 2 tests of 981, both clock-measuring** |

Probe (e) is the one that earned its keep, and probe (c) is the one worth reading twice: a
mechanism that never forgets satisfies every functional assertion a reviewer would think to write.

### Completion Notes List

**What shipped.** `images.NegativeCache` — an in-memory, expiring, bounded map of recently-failed
`(id, size, face)` keys, constructed once in the lifespan beside `Pacer` and `DiskCache`, reached
through a `negative_cache(app)` accessor. Base **30 s**, doubling per consecutive failure, ceiling
**300 s**, cap **2,048** entries, pruned on insert and evicted by earliest expiry. The route checks
it **after** the disk read, **before** the wiring guard and **outside** `pacer.slot()`, records
through the module's first `try`/`except` (`except CompanionError`, narrow), and clears on every
success. Plus Q4's consecutive-write-failure counter on `DiskCache`. **No new reason token, no new
route, no new dependency, no `build_*` factory, no `_shutdown` change.**

**The three verification ACs were verified, and three genuinely new assertions came out of it.**
AC 1-3 shipped at c3-5, so the danger was inheriting the claim rather than proving it. Established
by reading before writing: the two tokens, the six upstream-failure cases, the no-fetch assertion
and the SPA's `PLACEHOLDER_FOR_REASON` mapping all already existed. What did **not** exist, and now
does: the two answers asserted as a **discrimination from one test**; the "no substitute image"
half asserted on the **bytes** for the `no_image_data` token (it had only ever been status +
`.json()`, and a status-only assertion passes with a grey rectangle in the body); and the pairing
that distinguishes *never fetched* from *fetched and remembered as failed*.

**All nine open questions were answered "as proposed" — the 19th story running — but two of them
went against the grain and both were confirmed by the work.** Q5 kept `_BANNED_IDENTIFIERS` rather
than retiring it: `functools.cache`/`lru_cache` cannot express a TTL and `cache_clear()` cannot
address one key, so they are still the wrong tool the day the mechanism ships — **the first family
in this epic the owning story did not remove**, and retiring it would have been the first removal
that *lost* coverage rather than replacing it. The positive gate (`TestExactlyOneNegativeCache`)
was added **on top**. Q6 declined in-flight coalescing a third time and recorded that **c3-7's
stated reason did not survive contact**: a negative cache needs no in-flight state at all.

**AC 13's prediction was false and this is not the third behaviour-only story.** See Debug Log 3 —
7 paths and 12 components unchanged, but the required `contracts.py` edit crossed the wire because a
Pydantic model's class docstring is published in full. Kept deliberately; both generated files
regenerated and committed; `dump_openapi.py` rewritten with the corrected rule.

**Probe (e) found a real hole in my own AC 7 coverage** (Debug Log 4), which is the second
consecutive story where a probe caught its author rather than confirming them.

**Everything the story asked to be measured was measured, and one inherited claim was corrected.**
Every corpus number confirmed exactly (38,261 / 245,760 / 79 / 35,404 / 2,778 / 245,742 / 18 / **0**
outside the allow-list, which is all of Q3's evidence). The inherited suite baseline was stale —
2392, not 2395.

### File List

**Production (4):**

- `src/companion/app/images.py` — `NegativeCache`, `_RememberedFailure`, `negative_cache()`, the
  four `NEGATIVE_CACHE_*` constants and `DISK_CACHE_WRITE_FAILURE_LIMIT`; `DiskCache`'s write-failure
  counter and `_note_write_failure`; Q9's trust-chain restatement; the module docstring's
  negative-cache, coalescing, queue-ceiling and per-cause paragraphs. 1,307 → **1,475 lines**
- `src/companion/app/main.py` — the lifespan constructs it; the comment stating why it needs no
  factory and no teardown
- `src/companion/app/routes/cards.py` — the negative check, the module's first `try`/`except`, the
  clear on success, the `Raises:` docstring. 337 → **376 lines**
- `src/companion/contracts.py` — the two forward-dated c3-8 sentences to present tense
  (**wire-visible**; see Debug Log 3)

**Tests (2):**

- `tests/unit/companion/test_images.py` — the mechanism's 30 unit tests (constants, window,
  recovery, bounds, memory-only), `TestExactlyOneNegativeCache` with the shared
  `_construction_sites` scanner, and Q4's 8 write-counter tests
- `tests/unit/companion/test_routes_card_image.py` — `_BANNED_IDENTIFIERS` restated as a permanent
  ruling and all four pairings reworked; the `remembered` fixture; the three verification-AC classes
  and the six behavioural classes

**Docs, generated and mirrored (7):**

- `scripts/dump_openapi.py` — the corrected wire-visibility rule; c3-9 named next
- `ui/README.md` — the blind-spot row AC 16 owes unconditionally
- `ui/src/api/openapi.json`, `ui/src/api/types.d.ts` — regenerated, never hand-edited
- `plugin/server/src/companion/app/{images,main,routes/cards}.py`,
  `plugin/server/src/companion/contracts.py` — 4 mirrored files, rebuilt and committed
- `_bmad-output/implementation-artifacts/deferred-work.md` — nine inherited entries worked, five new
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c3-8-…md` (this file)

### Gates (AC 26 — every one re-run from the same tree, output pasted)

| Gate | Before | After |
| --- | --- | --- |
| `uv run pytest` | 2392 passed, 1 skipped — 178.70 s | **2455 passed, 1 skipped — 123.39 s** |
| `uv run pytest tests/unit/companion/` ×3 | 917 passed, 1 skipped — 47.03 / 47.69 / 44.14 s | **980 passed, 1 skipped — 48.85 / 49.04 / 49.09 s** |
| `uv run ruff check .` | All checks passed! | **All checks passed!** |
| `uv run ruff format --check .` | 305 files already formatted | **305 files already formatted** |
| `uv run mypy src/` | no issues, 89 files | **no issues, 89 files** |
| `uv run mypy src/ --platform win32` | no issues, 89 files | **no issues, 89 files** |
| `ui/ npm run lint` | clean | **clean (exit 0)** |
| `ui/ npm run format:check` | clean | **All matched files use Prettier code style!** |
| `ui/ npx tsc -b --force` | exit 0 | **exit 0** |
| `ui/ npm test` | 31 files / 568 tests | **31 files / 568 tests** (unchanged by design) |
| `ui/ npm run build` | exit 0 | **exit 0** |
| `test_import_boundary.py` (explicit, AC 20) | 50 passed | **50 passed, unchanged, no exclusions added** |
| `test_openapi_contract.py` (drift, AC 14) | 17 passed | **17 passed** |
| `named-card-copy.test.ts` (explicit, AC 17) | 6 passed | **6 passed, unchanged** |
| `gen:api` / `gen:types` re-run (AC 14) | — | **byte-identical on the second run** — reproducible |
| SPA bundle, both trees (AC 22) | 5 hashes | **all 10 files byte-identical to Task 0** |

**Suites: 2392 → 2455 Python (+63) · 980 in the companion package · frontend 568 unchanged.**

**The runtime claim, made honestly.** On `tests/unit/companion/` — the suite that contains the
change, and the one AC 26 requires — the before mean is **46.29 s** (spread 3.55 s) and the after
mean is **49.00 s** (spread 0.24 s), so **+2.71 s for 63 new tests**. That difference is smaller
than the spread the *baseline itself* showed across three runs of identical code, so it is reported
as an observation and **not** as a measurement of the mechanism's cost. No whole-suite delta is read
as signal: the full suite went 178.70 s → 123.39 s while gaining 63 tests, which is c3-7's ledgered
49-second machine noise and nothing else.

### Review record additions (Task 9, 2026-08-02)

**AC 10's explicit run, stated as required.**
`test_routes_card_image.py::TestADisconnectingClientReleasesItsSlot::test_a_fetch_still_succeeds_after_a_cancellation`
was run explicitly on the patched tree: **PASSED (1 passed in 0.39 s)**. It went the way the story
predicted — a cancellation is not recorded and the same key succeeds afterwards.

**AC 13's porcelain, pasted as required.** `npm run gen:api` re-run from `ui/`, then
`git status --porcelain -- ui/src/api`:

```
 M ui/src/api/openapi.json
 M ui/src/api/types.d.ts
```

Those two `M` lines are this story's own committed-to-be wire diff (Debug Log 3) unchanged by the
re-run — the diff stat after regeneration (`openapi.json | 2 +-`, `types.d.ts | 9 +++++++--`) is
byte-identical to the diff before it, confirming the generator is reproducible against this tree.

**AC 17's missing statement, added as required:** the UI half of this story was written before the
backend half — `EXPERIENCE.md`'s *"negative-cached with backoff — no request storms, no per-image
retry UI"* row and its byte-for-byte gate shipped with the UX artefact export, before any of this
story's code existed — which is the **inverse** of the pairing problem AD-16 exists to prevent
(a token shipping without its UI state); here the UI state waited for its token behaviour.

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-02 | **Greptile round 2: 4/5 again, no new inline finding, but the summary named a residual to round 1's fix — CONFIRMED and patched at `ab86a66`.** The size-keyed carve-out could be satisfied by a non-empty target whose *reads* are denied while `stat` still reports a positive size: `_read_cached` treats an unreadable file as a miss, so the key would refetch forever with every write swallowed as a lost race and the latch never advancing — the round-1 defect one level up. Fix: the benign branch proves **servability**, not size — it reads a byte exactly as `_read_cached` will (readable and non-empty ⇒ the next request is a warm hit, so the benign verdict is self-certifying; any `OSError` on the probe counts as not-stored). `test_an_unreadable_non_empty_target_is_counted_not_swallowed` pins the case. Companion suite 988 → **989**; all gates green; mirror rebuilt; replied on the PR thread |
| 2026-08-02 | **Greptile round 1 on PR #36: 4/5, one P1 — CONFIRMED and patched at `0c3423b`, in review-added code (the c3-7 pattern, second epic running).** The lost-race `PermissionError` carve-out (itself a Task 9 review patch) treated any *existing* target as the racing winner's entry and took the success branch. Two holes: `_read_cached` treats a zero-byte file as a miss, so a locked **empty** target would refetch forever — every write swallowed as a race, the counter reset each time, the latch never announcing the stuck root; and the reset itself let races interleaved with genuine failures keep a broken root below the limit indefinitely. Fix: `_write_atomically` returns whether its own replace **landed**; the benign branch requires `target.stat().st_size > 0` (a winner's entry is never empty — `fetch_image` refuses empty bodies; a failed stat counts as not-stored); and `DiskCache.write` resets the counter **only on a landed replace** — a lost race is neither a failure to count nor a success to reset on. Two new tests pin both halves; companion suite 986 → **988**; all gates green; mirror rebuilt; replied on the PR |
| 2026-08-02 | **Three-layer review (Task 9) → `done`.** Blind Hunter + Edge Case Hunter + Acceptance Auditor over the full diff; production mechanism confirmed sound by all three layers. 3 decisions (Brad): the write-latch burst exposure accepted with honest docs + c8-2 ledger entry; `Retry-After` declined + ledgered on c4-4; the wire-crossing `ErrorResponse` docstring keep ratified. 13 patches applied — headline: both AC 10 cancellation tests were timing-vacuous (cancelled at the route's first await, CDN in success mode) and the "same key" follow-up used a *different* key (`size=large`, probe (e)'s dodge reshipped); both reworked on `stalled_cdn` with the cancel parked mid-fetch and the two recorded URLs asserted identical. Also: per-hit backoff INFO → DEBUG with one bounded INFO per record; the Windows lost-race `PermissionError` carve-out (target-exists → not counted, non-vacuously paired); `NegativeCache` constructor guards + first-delay clamp; a wire-prose drift gate pinning "starts at 30 seconds"/"capped at 300"/"doubles" to the constants; the remembered-hit DB-cost sentence; the caplog logger filter; the eviction-cost asterisk; and the three record gaps (AC 10 explicit run PASSED, AC 13 porcelain pasted, AC 17 inverse-pairing statement). 1 deferral: per-record escalation under concurrent duplicates → c6-4. 3 findings dismissed as noise. Suites **2455 → 2461** (+6), companion 986; ruff/format/mypy/mypy-win32 clean; drift gate 17 passed; gen:api reproducible; plugin mirror rebuilt |
| 2026-08-02 | **Implemented → `review`.** All nine open questions answered "as proposed" (19 of 19 running), including Q5 keeping the last `_BANNED_IDENTIFIERS` family as a permanent ruling — deliberately against the pattern its two predecessors set, and the first family in this epic the owning story did not remove — and Q6 declining in-flight coalescing a third time on the ground that c3-7's stated reason did not survive contact. Shipped `images.NegativeCache` (30 s base, ×2, 300 s ceiling, 2,048 cap, cleared on recovery) wired between the disk read and the wiring guard, outside `pacer.slot()`, recording through the module's first `try`/`except`; plus Q4's consecutive-write-failure counter on `DiskCache`. **No new reason token, no new route, no new dependency, no `build_*` factory, no `_shutdown` change.** Suites 2392 → 2455 Python (+63), frontend 568 unchanged by design; every gate green including `mypy --platform win32` and a forced `tsc`; SPA bundle byte-identical in both trees. **AC 13's central prediction measured FALSE** — 7 paths / 12 components unchanged, but `ErrorResponse`'s class docstring is published in full so AC 15's own required edit crossed the wire, while `ErrorReason`'s attribute docstring twelve lines away did not; kept deliberately so c4-4 reads the 300 s recovery window in the JSDoc, both files regenerated, `dump_openapi.py` corrected. **Probe (e) passed and exposed a real hole in this story's own AC 7 test** (it dodged the disk cache by changing the key, so it had stopped testing recovery); repaired and re-probed. Probe (f) caught by 2 tests of 981, both clock-measuring. Nine inherited deferred entries closed or re-homed by name, five new ones ledgered. Corrected the inherited baseline: 2392, not the 2395 the story carried |
| 2026-08-02 | Story created — context engine analysis over the epic (Story 3.8 and the three ACs c3-5 already satisfied), AD-11/AD-16/FR-04/UX-DR22, the shipped `images.py` (1,307 lines), `routes/cards.py`, `main.py` and `contracts.py`, c3-7's record and its 14 review patches plus two Greptile rounds, the last standing `_BANNED_IDENTIFIERS` family, the **nine** `deferred-work.md` entries homed on this story by name, `EXPERIENCE.md`'s forward-dated backoff promise and its gate, and the live 38,261-card database (245,760 resolvable keys, the 0/1/2-face histogram and the two hosts re-measured for the bound and for Q3) |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

IMPLEMENTED -> review 2026-08-02 off 3aef5d1 — the negative cache with backoff, the THIRD and last mechanism the spine draws inside app/images.py. All 9 open questions "as proposed" (19 of 19 running), and TWO of them went against the grain: Q5 KEPT the last _BANNED_IDENTIFIERS family as a PERMANENT RULING rather than retiring it with the story that owned it — the first family in this epic not removed by its owner, because functools.cache/lru_cache cannot express a TTL and cache_clear() cannot address ONE key, so they are still the wrong tool the day the mechanism ships; retiring them would have been the first removal in this epic that LOST coverage rather than replacing it, and the positive gate (TestExactlyOneNegativeCache) was added ON TOP instead. Q6 declined in-flight coalescing a THIRD time and recorded that c3-7's stated reason DID NOT SURVIVE CONTACT: a negative cache needs no in-flight state at all — c3-7 re-homed it here expecting a shared structure that turned out not to exist — re-homed on c6-4. SHIPPED: images.NegativeCache (base 30 s, x2 per consecutive failure, 300 s ceiling, 2,048-entry cap, pruned on insert, evicted by earliest expiry, cleared entirely on recovery), constructed ONCE in the lifespan beside Pacer and DiskCache with a negative_cache(app) accessor; the route checks it AFTER the disk read, BEFORE the wiring guard and OUTSIDE pacer.slot(), records through the module's FIRST try/except (narrow `except CompanionError` — CancelledError inherits BaseException so a bare `except Exception` would already miss it), and clears on every success. Plus Q4's consecutive-write-failure counter on DiskCache, closing the ledgered "~99 WARNINGs per cold paint forever" entry (5 consecutive failures disable WRITES only, announced once; reads keep working for NFR-06; one success resets; per-instance state). NO new reason token, NO new route, NO new dependency, NO build_* factory, NO _shutdown change — so test_app.py's startup asymmetry and test_deps.py's shutdown ordering both needed NO edit, a prediction confirmed by measurement. THE HEADLINE CORRECTION: AC 13's central prediction is FALSE and this is NOT the third behaviour-only story. 7 paths / 12 components unchanged — the structural half held perfectly — but `npm run gen:api` produced a REAL DIFF in both generated files, because AC 15's own REQUIRED edit to ErrorResponse's class docstring crosses the wire: a Pydantic model's class docstring is published IN ITS ENTIRETY (bullet list and all), while ErrorReason's attribute docstring TWELVE LINES AWAY in the same file is not published at all. Two docstrings, one file, opposite sides of the boundary — settled by RUNNING the generator exactly as dump_openapi.py insisted. The edit was KEPT rather than reverted on c3-2's and c3-3's precedent, so c4-4's tile author reads the 300 s recovery window in the generated JSDoc; both files regenerated and committed, dump_openapi.py rewritten with the corrected rule and c3-9 named next. PROBE (e) PASSED — a REAL HOLE in this story's own AC 7 coverage: deleting the route's clear-on-success left all 980 tests green, because my recovery test switched to size=large to dodge the warm disk cache and thereby stopped testing the recovered key at all. Repaired (disk cache disabled so the SAME key can succeed then fail) and re-probed: 1 failed. That is c3-7's probe (d) repeating — the probe catching its author rather than confirming them, second consecutive story. PROBE (f) — the negative check moved INSIDE pacer.slot() — was caught by exactly 2 tests of 981 and BOTH are the clock-measuring ones; every byte-identity, fetch-count and status assertion passed, which is the c3-5/c3-6/c3-7 shared review theme reproduced for a FOURTH story running and the whole argument for AC 4 measuring the injected clock. Probe (c), the expiry removed, passes every "no second fetch" test and is caught only by the boundary units and both recovery tests. Probe (d), the bound removed, is INVISIBLE to every route-level assertion. FIRST IMPLEMENTATION WAS WRONG AND THREE OF MY OWN UNIT TESTS CAUGHT IT: pruning at retry_after resets the escalation on every attempt, so a key against a permanently dead CDN cycles at the base 30 s forever and AC 6's schedule is unreachable in production — fixed with a retention horizon of retry_after + ceiling, a FIFTH number Q2 did not fix, derived rather than declared and ledgered. Also: the delay is stored rather than a failure count, because base * multiplier ** count raises OverflowError on a long-lived key. THE THREE VERIFICATION ACs were verified rather than inherited, and produced three genuinely new assertions: the two tokens asserted as a DISCRIMINATION from one test (they had only ever been proved in separate classes on separate fixtures); the "no substitute image" half asserted on the BYTES for no_image_data (it had only ever been status + .json(), and a status-only assertion passes with a grey rectangle in the body); and the pairing that separates "never fetched" from "fetched and remembered as failed". The structural pin the story NAMED IN ADVANCE did not fire — _LIMIT_LITERALS bans 60 anywhere under src/companion and Q2's schedule contains it, safe only because it is computed as previous x multiplier and never written as a literal tuple; five consecutive stories hit an unnamed pin and this is the first to name and avoid one. Corpus re-verified read-only, every number confirmed exactly (38,261 / 245,760 / 79 / 35,404 / 2,778 / 245,742 / 18 / ZERO outside the allow-list, which is all of Q3's evidence). Corrected the inherited baseline: 2392 passed, not the 2395 the story carried. Suites 2392 -> 2455 Python (+63) / companion 917 -> 980 / frontend 568 UNCHANGED by design; every gate green incl. mypy --platform win32 and a FORCED tsc; test_import_boundary.py 50 passed unchanged with NO exclusions; named-card-copy.test.ts 6 passed UNCHANGED, so EXPERIENCE.md's forward-dated backoff promise became true with no edit on either side; SPA bundle + plugin mirror RE-MEASURED byte-identical on all ten files. Nine inherited deferred entries closed or re-homed BY NAME (2 closed, 7 re-homed on c6-4/c8-2/the C3 retro) plus five new ones incl. the ~124 s first-paint exposure -> c10-3. images.py 1,307 -> 1,475 lines, recorded so the C3 retro inherits a number. Next = Brad's Task 9 same-day three-layer review, then the PR into feat/companion-c3. Previously — CONTEXTED 2026-08-02 off 3aef5d1 (PR #35, c3-7). Story file written; 9 open questions, 5 of them genuine forks. Headline finding: THREE of this story's five epic ACs already shipped at c3-5 (the distinguishable tokens, the never-fetch-for-no-image-data path, the placeholder data) - AC 1-3 are VERIFICATION ACs and are first for that reason; only the backoff and the retry are new. Q5 recommends AGAINST the pattern the last two stories set: functools.cache/lru_cache stay banned, because unlike Semaphore (c3-6) and mkdir (c3-7) they are still the wrong tool the day this ships (no TTL; cache_clear is all-or-nothing, so AC 7 clear-one-key-on-recovery is unimplementable on them) - the first family in this epic NOT removed by the story that owned it. Q6 declines in-flight coalescing a THIRD time and states why c3-7 reasoning does not survive contact (a negative cache needs no in-flight state; coalescing shares a 124 KB payload, a different mechanism). Measured read-only: 245,760 resolvable (id,size,face) keys = the memory bound; 79 image-less cards never reach the cache; ZERO stored URLs outside the allow-list, which is all of Q3 evidence; a cold paint against a dead CDN is ~124 s at min(1/0.1, 4/5.0) = 0.8 fetch/s and this story does NOT fix it - it fixes every paint after. Structural pin named in advance: _LIMIT_LITERALS = {60, 15} scans all of src/companion and 60 sits on Q2 proposed 30->60->120->240->300 schedule (safe only because base x2 never writes it as a literal). Nine deferred-work entries homed here, enumerated as an AC table.
