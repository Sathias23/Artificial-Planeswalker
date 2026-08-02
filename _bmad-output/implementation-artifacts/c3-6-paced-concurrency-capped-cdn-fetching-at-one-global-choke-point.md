---
epic: c3
story: c3-6
work_branch: feat/companion-c3
story_branch: feat/companion-c3-6-image-pacer
depends_on: c3-5 (PR #33, merged into the umbrella at 4765bc6) — the image route, the lifespan-owned `httpx.AsyncClient`, `fetch_image`, the allow-list, the two image tokens and the `_BANNED_IDENTIFIERS` guard all exist
baseline_commit: 4765bc6
---

# Story C3.6: Paced, concurrency-capped CDN fetching at one global choke point

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a good citizen of Scryfall's infrastructure,
I want every outbound image fetch to pass through a single pacer,
so that a 100-card deck load is a polite trickle rather than a request storm.

**What this story really is.** c3-5 opened the socket. This one puts a queue in front of it. Every
prior story in this epic shipped a *value* — a payload, a token, a set of bytes — and could be
proven by reading a response. **This story's deliverable is a rate**, and that changes what
"correct" means and what a test has to do to see it.

Three things follow from that one fact:

1. **The first behaviour in this feature whose correctness is timing.** A rate is the classic
   flaky-test generator: the naive proof sleeps, the naive proof is slow, and the naive proof goes
   red on a loaded CI box for reasons that have nothing to do with the code. **The design work here
   is making the timing deterministic**, not making it happen.
2. **The first story that must edit a guard another story wrote against it — by name.**
   `tests/unit/companion/test_routes_card_image.py:657-677` bans `Semaphore`, `BoundedSemaphore`,
   `sleep` and `Lock` from `images.py`, with the comment *"c3-6's pacer"* on the family, and its
   non-vacuity plant asserts `"Semaphore" in names` with the message *"the pacer family missed an
   aliased import"*. c3-5 built the fence and wrote your name on it. Taking a fence down is the
   highest-risk edit in this repo: the standing agreement is that **a red silenced without
   restating its comment is how the next story inherits a lie.**
3. **The first story whose epic ACs are not all its own.** Two of the six cannot be satisfied here
   and their homes must be named rather than fudged: the CM-2 *"a repeat request makes no CDN
   request"* AC is the **disk cache (c3-7)**, and the *"a concurrent push through
   `POST /agent/events` still meets its latency budget"* AC names an endpoint that **does not exist
   until c5-1/c5-5**. Answering them with something adjacent-but-not-that is the failure mode; the
   epic's own AC text is the claim, and an unsatisfiable claim gets an owner, not a paraphrase.

The consequence to internalise before writing code: **this story adds no wire vocabulary and, if it
is done right, regenerates nothing.** `scripts/dump_openapi.py:29-30` already predicts it —
*"Story c3-6's pacer is next, and should need nothing here at all — it adds behaviour to an
existing route rather than a route."* That is a **prediction to confirm by running the generator**,
not a fact to inherit; and it stops being true the moment a wire-visible docstring paragraph gains
a sentence (Q4).

**Everything numeric in this story was measured on this machine at `4765bc6` against the shipped
38,261-card database and the installed toolchain, read-only. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **The module is written and it names you three times.** `src/companion/app/images.py:29-33`:
   *"**no pacer, no concurrency cap** — story **c3-6**. Between this story and that one the route
   fetches unpaced… the window is small and UI-less, not closed."* `_FETCH_TOTAL_SECONDS`'s
   docstring (`:146-154`) says a pathological upstream must not hold *"a connection (and, from
   c3-6, a pacer slot)"* open. And `build_image_client`'s docstring (`:302-303`) constrains your
   design out loud: *"This is **not** the pacer and must not grow into one: c3-6 adds its semaphore
   **around** this client, not inside it."* All three are forward-dated comments this story either
   makes true or re-homes — and the third is a **shipped ruling about where the pacer sits**, not a
   suggestion.

2. **There is exactly one outbound call site, and it is a function.**
   `images.fetch_image(client, url)` (`:390`) is called once, from
   `routes/cards.py:274`, and nothing else in `src/companion` opens a socket to the internet. That
   is what makes *"exactly one pacer in the process — not one per route, per card, or per client"*
   (epic `:1721`) mechanically provable rather than aspirational: put the choke point where the
   call already is, and no caller can route around it.

3. **The client is lifespan-owned and there is a shape to copy exactly.** `main.py:179` creates
   `app.state.image_client = images.build_image_client()` beside `instance_id`, the token, the
   `Database` holder and the `ActiveDeckSlot`; `_shutdown` (`:109-119`) closes it under
   **try/finally** so a raising `aclose()` cannot strand `holder.dispose()` — a review patch, with
   `test_deps.py:807`'s `test_a_failing_image_client_close_does_not_strand_the_engine_dispose`
   pinning it. `build_app()` may create nothing (AD-10). A pacer with no teardown is *cheaper* than
   the client, which is the one thing that makes Q1 a real question.

4. **The test seam is the factory, not the client.** `test_routes_card_image.py:87-103`'s `cdn`
   fixture monkeypatches **`images.build_image_client`**, because the lifespan calls it on startup
   and would overwrite anything a test had put on `app.state` beforehand. Whatever Q1 rules, the
   pacer needs a seam with the same property: **substitutable before the lifespan runs**.

5. **`Recorder` already records every URL, in order** (`test_routes_card_image.py:53-84`). Ordering
   and counting — the two things this story actually has to prove — are already instrumented. What
   it does *not* record is **when**; a timestamp list is the smallest honest addition.

6. **The route's own docstring crosses the wire.** `main.py` truncates Google sections except
   `Note:` and `Warning:` (c3-2's ruling), so the leading paragraph and any `Warning:` in
   `read_card_image` are **published to `openapi.json` and `types.d.ts`**. Adding "requests may
   queue" to the docstring is therefore a wire change with two drift gates behind it, not a comment.
   Q4 rules whether that is wanted; either way it is a decision, and the *silent* version of it —
   editing prose and not regenerating — is a guaranteed red CI.

7. **`ErrorReason` is closed at ten** (`contracts.py`, `errors.py:46-57`:
   `deck_not_found`, `card_not_found`, `no_image_data`, `image_fetch_failed`,
   `database_not_initialized`, `database_unavailable`, `invalid_request`, `forbidden`,
   `payload_too_large`, `internal_error`). c3-5 paid eight ripple sites **twice over** for the last
   two. The proposal here is that this story adds **none** — but that is a consequence of Q4, not
   an assumption: a queue-wait ceiling would need a token or would have to borrow
   `image_fetch_failed`.

8. **`error_response` stamps `Cache-Control: no-store` on every typed error, feature-wide**
   (`errors.py:148-168`, c3-5). Anything this story answers as a failure is already uncacheable.
   Nothing to do; stated so it is not re-done.

9. **The pacing numbers are already researched and recorded — do not re-research them.** c3-5's
   § Latest technical information banked them for this story by name: Scryfall asks for **under 10
   requests/second with 50–100 ms between calls**, `429` plus a ~30 s lockout for excess — **and
   the `*.scryfall.io` file origins, which is the only host family this route fetches from, are
   explicitly exempt from that guidance.** So AD-11's pacer is a **good-citizen and NFR-05 budget
   decision, not a compliance one** (`deferred-work.md`, the c3-6-homed entry). Say that out loud
   in the constant's docstring: a number copied from a rule that does not apply, presented as
   compliance, is exactly the prose-outruns-code finding c3-4 was marked down for.

10. **`asyncio.Semaphore` and `asyncio.Lock` no longer bind an event loop at construction** on
    Python 3.10+, and this repo already relies on it: `deps.Database.__init__` creates its
    `asyncio.Lock` outside any running loop and its docstring (`:101-104`) says exactly why. So
    "constructing a pacer is free and cannot fail" is already established, with a precedent to
    cite rather than a claim to make.

11. **`Database`'s lock docstring is also the template for how to write this one honestly**
    (`deps.py:106-114`): it states what the lock *currently* buys, that the check-then-assign
    cannot actually interleave today, and why it is kept anyway. A pacer whose semaphore never
    binds under the proposed constants deserves the same treatment — **say what is defence and
    what is necessity**, with the arithmetic.

### The guard c3-5 built against this story, and how it must come down

12. **`_BANNED_IDENTIFIERS` (`test_routes_card_image.py:657-677`) is three families in one
    frozenset**, and only one of them is yours:

    | Family | Members | Owner |
    | --- | --- | --- |
    | the pacer | `Semaphore`, `BoundedSemaphore`, `sleep`, `Lock` | **c3-6 — this story** |
    | the disk cache | `mkdir`, `makedirs`, `open`, `write_bytes`, `write_text`, `data_dir`, `NamedTemporaryFile`, `replace` | c3-7 — **stays banned** |
    | the negative cache | `lru_cache`, `cache` | c3-8 — **stays banned** |

    Removing the whole set is wrong; removing four names and leaving the other ten is right. Both
    paired tests move with it:

    - `test_the_scan_sees_a_planted_breach_of_each_family` (`:758-788`) asserts
      `"Semaphore" in names` with the message *"the pacer family missed an aliased import"* — that
      assertion is about the **scanner**, not about the ban, and the distinction matters: the
      scanner must still *see* an aliased `asyncio as aio` semaphore even though seeing one is no
      longer a breach. Keep the scanner proof, move the name out of `_BANNED_IDENTIFIERS`.
    - `test_the_scan_ignores_prose_that_merely_names_the_banned_things` (`:790-808`) plants the
      literal sentence *"No Semaphore here — the pacer is c3-6's"*. That sentence becomes false.

    **The positive half is this story's, and it is the part that has teeth:** with the ban gone,
    nothing stops a *second* semaphore appearing later. Replace the removed family with an
    assertion that there is **exactly one** — one construction site, in one module — so
    "one backend-global choke point" is a gate rather than a sentence.

13. **`test_import_boundary.py` is unchanged and must stay unchanged**, with no exclusions added.
    Nothing about a pacer wants a banned module; stated because every story in this epic has been
    tempted by something.

### What the real data says (measured at `4765bc6`, read-only)

**A real 100-card deck is not 100 images.** Measured against the live database, over the 18 saved
decks with ≥90 cards:

| Deck | Entries | Cards | **Distinct card ids** |
| --- | --- | --- | --- |
| `Atraxa Counter Cabinet` | 99 | 100 | **99** |
| `Infinite Guideline Station v2` | 98 | 100 | **98** |
| `Ezuri Proliferate Poison` | 90 | 100 | **90** |
| `Ayara Black Devotion v2` | 67 | 100 | **67** |
| … 18 decks ≥90 cards | | | **67 – 99**, median ~78 |

Basic lands collapse: **the burst is 67–99 distinct ids, not 100.** Across all 40 saved decks there
are **1,061 distinct card ids** — the whole warm-cache footprint of this user's library, which is
the number c3-7 will care about.

**Per-deck image shapes** (the two 98/99-id decks, resolved through c3-5's rule):

| Deck | Distinct ids | Shape A/B (one image) | Shape C (per-face) | Face images available |
| --- | --- | --- | --- | --- |
| `Atraxa Counter Cabinet` | 99 | 93 | 6 × 2 faces | **105** |
| `Infinite Guideline Station v2` | 98 | 97 | 1 × 2 faces | **99** |

The grid asks for face 0 only, so a cold deck paint is **~99 fetches**, and a DFC flip or a detail
panel adds one more per card at a *different* `(size, face)` key.

**The epic's "~12 MB over ~10 seconds" is arithmetic, and it names the spacing constant.**
12 MB ÷ 99 tiles ≈ **124 KB**, which is a Scryfall `normal` JPEG — so the epic's figure is the grid
size, not `large`/`png`. And ~10 s ÷ 99 tiles ≈ **100 ms per tile**: the epic's own acceptance
observation *is* a 100 ms spacing, evaluated at the top of Scryfall's published 50–100 ms band.
Steady-state throughput for spacing `S`, cap `N`, per-fetch latency `L` is
`min(1/S, N/L)`; a 99-tile deck therefore takes `99 × max(S, L/N)`:

| S | N | L (normal) | Predicted cold paint | Note |
| --- | --- | --- | --- | --- |
| **0.10 s** | **4** | 0.2 s | **9.9 s** | reproduces the epic's stated observation |
| 0.05 s | 4 | 0.2 s | 5.0 s | the fast end of Scryfall's band |
| 0.10 s | 4 | 2.0 s (degraded CDN) | 49.5 s | the **cap** binds, not the spacing — which is the point |
| 0.10 s | unlimited | 2.0 s | 9.9 s, with **~20 sockets open at once** | what "no cap" actually costs |

**The database pool is a second, invisible choke point.** The pool numbers are **measured**:
`create_engine` takes SQLAlchemy's defaults — pool `AsyncAdaptedQueuePool`, **size 5, max_overflow
10 → 15 connections**, `pool_timeout` **30 s**. The consequence is a **claim to verify in Task 0,
not a measurement**: FastAPI runs a `yield`-dependency's teardown *after* the endpoint returns, so
the route's `DbSession` — and its checked-out connection — should still be held **across the pacer
wait**. If that is right, then at 99 concurrent
tiles that means at most 15 requests are inside the route at once and 84 are blocked in the pool,
draining as the pacer releases them. It works under the proposed constants (a 9.9 s total drain,
well inside the 30 s pool timeout) — **and it works by arithmetic, not by design**. Q6 rules what
to do about it; Task 0 proves the hold is real before anything is decided on it.

**Committed artifacts at `4765bc6`, to be left byte-identical if Q4 says so:**
`ui/src/api/openapi.json` — **7 paths** (`/api/active-deck`, `/api/card-image/{scryfall_id}`,
`/api/cards/{card_id}`, `/api/deck/{deck_id}`, `/api/deck/{deck_id}/format-check`, `/api/decks`,
`/health`) and **12 components** (`ActiveDeck`, `ActiveDeckRequest`, `Card`, `CardFace`,
`CardSummary`, `DeckCardSummary`, `DeckDetail`, `DeckSummary`, `ErrorResponse`,
`FormatCheckReport`, `FormatCheckRow`, `HealthResponse`).

**Toolchain on this machine:** Python **3.12.13** · FastAPI **0.140.0** · Starlette **0.48.0** ·
SQLAlchemy **2.0.44** · Pydantic **2.12.0** · httpx **0.28.1** · anyio **4.11.0** · uvicorn
**0.51.0**.

**Suites at the baseline, to be re-measured not inherited:** Python **2275 passed** (c3-5's final
full run; its post-review run with `-m "not integration"` reported **2240 passed, 1 skipped**, so
measure the selection you actually intend to quote) · frontend **568 passed**.

---

## Acceptance Criteria

### The choke point

1. **One pacer, and every outbound image fetch goes through it** (AD-11, epic `:1718-1721`). There
   is exactly **one** semaphore-plus-spacing mechanism in `src/companion`, constructed in exactly
   one place, and **no outbound fetch can bypass it** — enforced structurally per Q1, not by
   convention. `build_image_client`'s shipped ruling holds: the pacer wraps the client, it does not
   live inside it.

2. **"Exactly one" is a gate, not a sentence.** The guard that replaces the removed pacer family in
   `_BANNED_IDENTIFIERS` (landmine 12) asserts a single construction site over the AST, and is
   paired non-vacuously with a planted second one — spelled to evade (an aliased import, a
   differently-named local) per c3-3's lesson.

3. **The concurrency cap and the spacing are two named constants with docstrings that carry their
   arithmetic** (Q2). Each states the number, what it binds, and what it does **not**: in
   particular that Scryfall's 10 req/s + 50–100 ms guidance covers `api.scryfall.com` and that the
   `*.scryfall.io` file origins this route fetches from are **explicitly exempt** — so these
   numbers are a good-citizen and NFR-05 choice, not compliance. A constant justified by a rule
   that does not apply is the prose-outruns-code finding, pre-committed.

### Pacing behaviour

4. **Spacing is enforced between fetch *starts*, globally** — two fetches begun by unrelated
   requests are separated by at least the interval, and the ordering is first-come-first-served
   within one process. Proven deterministically (AC 9), with the observed start times asserted, not
   the elapsed wall clock.

5. **The cap bounds in-flight fetches** — with the CDN made arbitrarily slow, the number of
   simultaneously open upstream requests never exceeds the cap, asserted from the transport's own
   accounting (requests entered minus responses completed), not inferred from timing.

6. **The pacer is `async` throughout and never blocks the event loop** (AD-11, epic `:1723-1726`).
   No `time.sleep`, no `threading` primitive, no `run_in_executor`, no busy-wait. Asserted two
   ways: a source-level scan for the synchronous spellings, **and** a behavioural test that an
   unrelated, non-image endpoint (`/health`) answers promptly while a burst of image fetches is
   queued — with the *number* of interleavings asserted, so a serialised event loop fails it.

   The epic's version of this AC names `POST /agent/events` (`:1726`), which **does not exist until
   c5-1/c5-5**. `/health` is the honest stand-in available today; the literal AC — a concurrent
   **push** meeting its 250 ms budget while images are queued — is homed on **c10-3**, whose own
   AC (`:3580-3582`) already says exactly that, and the substitution is recorded in the story
   record rather than passed off as the same test.

7. **A cancelled request releases its slot.** A client that disconnects while queued or in flight
   must not leak a semaphore permit or a spacing turn — the failure mode is a pacer that
   permanently narrows over a session of scrolling. Asserted by cancelling a queued fetch and
   proving the next one proceeds, with the permit count back where it started.

8. **Queue-wait semantics are ruled and stated** (Q4): whether the wait counts inside
   `_FETCH_TOTAL_SECONDS`'s whole-exchange deadline, whether there is a ceiling on how long a
   request may queue, and what a caller is told about it. Whatever is ruled, the **20 s deadline
   must not silently start ticking while a request is queued** unless that is the explicit ruling,
   because a 99-tile deck would then fail its own tail.

### Determinism — the part that decides whether this story ages well

9. **No test sleeps for real time to prove a rate** (Q3). The timing seam is injected, so pacing
   assertions are exact and cost no wall clock: the suite's total runtime after this story is
   within noise of before, and stated as a before → after measurement. A test that proves spacing
   by measuring elapsed seconds is the thing this AC exists to forbid — it is slow when it passes
   and mysterious when it fails on a loaded box.

10. **The cold-deck observation is reproduced as a computation, and recorded as an expected
    observation rather than a defect** (epic `:1736-1739`, NFR-05 excludes first-fetch paint). A
    test drives **99 distinct image requests** — the measured distinct-id count of a real 100-card
    deck, not a round 100 — through the pacer on the injected clock and asserts the modelled
    elapsed time lands at the epic's ~10 s. The ~12 MB half is **arithmetic on the measured 124 KB
    average** and is stated as such; the real-bytes measurement is **c10-3's** (`:3588-3590`).

### What this story does not build

11. **No disk cache, no negative cache, no backoff, no `image_cache` directory** (c3-7, c3-8,
    AD-10). The two surviving families of `_BANNED_IDENTIFIERS` stay banned and their comments stay
    accurate. Building any hook, registry or placeholder for either is out of scope on c3-4's
    ruling: *an unused hook is a design decision made by a story that cannot see the requirements.*

12. **The epic's CM-2 AC is homed, not paraphrased.** *"An image fetched once is not fetched again
    within the cache lifetime"* (`:1728-1730`) is the **disk cache — c3-7**; there is no cache in
    this story and a repeat request repeats the fetch. Recorded in `deferred-work.md` by name, in
    the module docstring, and in the story record. Q5 rules the one adjacent thing this story could
    honestly own — **in-flight coalescing**, where two *simultaneous* requests for the same URL
    share one fetch — and whichever way it goes, the ruling is written down with its reason.

13. **Fetching stays lazy and nothing pre-fetches** (epic `:1732-1734`). Asserted directly: loading
    a deck through `GET /api/deck/{deck_id}` triggers **zero** outbound requests, proven from the
    same transport recorder that proves a tile request triggers one — the non-vacuity pairing, not
    a bare zero.

14. **No frontend behaviour ships.** `ui/src` is unchanged except — only under Q4 — the two
    generated files and a `ui/README.md` blind-spot row. **c4-4 still owns the tile that fetches an
    image**, and no file under `ui/src` contains a CDN host (the scan c3-5's review landed stays
    green).

### The wire contract

15. **The regeneration prediction is confirmed by running the generator, not by argument.**
    `npm run gen:api` is run and `git status --porcelain` is pasted. Under Q4's proposed ruling the
    expected result is **no diff at all** — 7 paths, 12 components, byte-identical — which also
    confirms `dump_openapi.py:29-30`'s forward-dated claim. If Q4 rules that the route docstring
    gains a wire-visible `Warning:`, both generated files are regenerated and committed together,
    neither hand-edited, and the before → after diff is stated.

16. **Both drift gates are green from the same commit, output pasted:**
    `uv run pytest tests/unit/companion/test_openapi_contract.py`, and from `ui/`
    `npm run gen:types && git status --porcelain`.

### Boundaries, records and the mirror

17. **No write path is opened and no banned module is imported.** `test_import_boundary.py` passes
    **unchanged with no exclusions added**.

18. **The forward-dated-comment inventory is repaired.** Each row becomes true, is re-homed, or is
    recorded with a judgement:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `images.py:27-42` | "**no pacer, no concurrency cap** — story c3-6… the window is small and UI-less, not closed" | **Becomes false** — rewrite; the remaining two absences (c3-7, c3-8) stay and stay accurate |
    | 2 | `images.py:146-154` (`_FETCH_TOTAL_SECONDS`) | "…holding a connection (and, from c3-6, a pacer slot) open indefinitely" | **Becomes present tense** — and restate per Q4's queue-vs-deadline ruling |
    | 3 | `images.py:302-303` (`build_image_client`) | "This is **not** the pacer… c3-6 adds its semaphore *around* this client" | **Becomes true** — say where it went, and that the client still is not it |
    | 4 | `scripts/dump_openapi.py:29-30` | "Story **c3-6**'s pacer is next, and should need nothing here at all" | **Confirm by measurement**, restate as shipped, and name **c3-7** next |
    | 5 | `test_routes_card_image.py:657-677` + `:758-808` | the ban and both pairings | **Landmine 12** — one family out, ten names stay, both plants reworked with comments restated |
    | 6 | `deps.py:283-317` (`DbSession` callers) | "c3-5 is the first consumer that goes on to do something **after** the session closes" | **Correct it if Task 0 disproves it** — the session is held *across* the fetch, not closed before it, and that is load-bearing for Q6 |
    | 7 | `deferred-work.md`'s c3-6-homed entry | "Between this story and c3-6 the image route fetches unpaced… **Home: c3-6**" | **Resolve by name**, with what the entry did not price |

19. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and
    the SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and its mirror
    expected byte-identical (this story ships no runtime frontend code). A change is a finding to
    explain, not a rebuild to wave through.

20. **`deferred-work.md` gains this story's residue with named homes**, at minimum: the CM-2 repeat
    fetch (**c3-7**); the real-bytes and real-latency measurement (**c10-3**); the
    `POST /agent/events` half of the never-blocks-the-loop AC (**c10-3**); the
    session-held-across-the-queue interaction with the 15-connection pool (**Q6's ruling** — home
    it wherever the ruling puts it, with the measured pool numbers in the entry); and whatever
    Q4/Q5 decline. No residue in prose only.

### Testing

21. **The pacer's own tests live in `tests/unit/companion/test_images.py`** beside
    `TestResolveFaceImages`, `TestUrlAllowList`, `TestFetchImage` and `TestImageClient` — the module
    already owns the mechanism's unit tests and this is more of the same, not a new file. Route- and
    app-level behaviour (AC 6, 7, 13) goes in `test_routes_card_image.py` beside the existing
    classes. Reuse `Recorder`, `cdn`, `lifespan_client`, `isolated_data_dir` and `image_shapes`;
    **do not write a second seam**.

22. **No test touches the network** and every pacing test asserts on **what the transport was asked
    for and when**, from the recorder — not on the response alone.

23. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the
    single-pacer scan is paired with a planted second construction site; the no-pre-fetch assertion
    is paired with a request that *does* fetch; the never-blocks-the-loop test is paired with a
    deliberately blocking implementation in a scratch fixture, or with an assertion strong enough
    that a serialised loop fails it.

24. **At least five mutation probes are run, verified on disk before the verdict and reverted
    after** (standing agreement — *probe your own guard before review does*): (a) the semaphore
    removed, leaving only spacing; (b) the spacing removed, leaving only the semaphore; (c) a
    second pacer constructed in a second place; (d) the pacer acquired *after* the fetch instead of
    before, so it paces nothing; (e) `asyncio.sleep` swapped for `time.sleep`, which paces
    correctly and blocks the loop. Paste each result and **read the output before filing it** —
    c3-1's review found three vacuous tests hiding inside a "19 failed" probe result.

25. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus
    the frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`,
    `build`) and both drift checks. Suite counts **and total runtime** stated as *before → after*
    (AC 9 makes the runtime a claim). Baseline to beat, **to be re-measured not inherited**:
    Python **2275 passed** · frontend **568 passed**.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is `4765bc6`; cut
        `feat/companion-c3-6-image-pacer` from it
  - [x] Run and record with **durations**: `uv run pytest`, `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/`
        mirror (AC 19); record the committed `paths` (expect 7) and `components` (expect 12)
  - [x] **Verify the deck numbers yourself**, read-only: distinct card ids per saved deck ≥90 cards
        (expect 67–99), and the shape split on the two 98/99-id decks. If your corpus differs, the
        story's numbers are the claim and yours are the truth — record the difference
  - [x] **Prove the session hold** (landmine 6 / Q6): instrument or assert that the `DbSession`
        connection is still checked out while `fetch_image` is awaited. Measure the pool
        (`AsyncAdaptedQueuePool`, size 5, overflow 10, timeout 30 s) rather than trusting this file

- [x] **Task 1 — The pacer** (AC 1, 3, 4, 5, 6, 7; Q1, Q2, Q3, Q4)
  - [x] The mechanism in `images.py` per Q1, with the injected timing seam per Q3
  - [x] Two named constants with the arithmetic and the exemption note in their docstrings (AC 3)
  - [x] Unit tests on the fake clock **before** wiring it — spacing, cap, ordering, cancellation
  - [x] Say in the docstring what is defence and what is necessity, `deps.Database`'s lock
        docstring being the template (landmine 11)

- [x] **Task 2 — Wiring it in** (AC 1, 2; Q1)
  - [x] Constructed once, per Q1 — lifespan beside `image_client`, or as Q1 rules
  - [x] `fetch_image` cannot be called without it (structural, not conventional)
  - [x] The single-construction-site guard, with its planted second site (AC 2)

- [x] **Task 3 — The guard comes down, carefully** (AC 11; landmine 12)
  - [x] Four names out of `_BANNED_IDENTIFIERS`; **ten stay**; the family comment restated
  - [x] Both pairings reworked — the scanner still sees an aliased `Semaphore`, and the prose test
        stops planting a sentence that is now false
  - [x] Re-run `test_import_boundary.py` explicitly and paste it (AC 17)

- [x] **Task 4 — The behavioural half** (AC 6, 7, 10, 13, 22, 23)
  - [x] `/health` interleaving under a queued burst, with the interleaving *count* asserted
  - [x] The 99-request cold-deck reproduction on the injected clock (AC 10)
  - [x] `GET /api/deck/{deck_id}` triggers zero outbound requests, paired with one that does

- [x] **Task 5 — The wire, confirmed rather than assumed** (AC 15, 16; Q4)
  - [x] `npm run gen:api`; paste `git status --porcelain`; state the diff (measured: **none**)
  - [x] Both drift gates from the same commit

- [x] **Task 6 — Comments, docs, records** (AC 18, 19, 20; Q5, Q6)
  - [x] Work the seven-row forward-dated-comment table
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] `deferred-work.md` entries with named homes, including the c3-6-homed entry **resolved**
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`; set status to `review`

- [x] **Task 7 — Probes** (AC 24)
  - [x] Five mutation probes, each verified on disk and reverted; paste and **read** each result
        — **six run**; five caught, probe (f) found a real hole and probe (a) a false green

- [ ] **Task 8 — Same-day three-layer review before the PR** *(Brad runs this — `dev-story` stops
      at Task 7 with status `review`)*
  - [ ] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before the PR
  - [ ] Apply patches, re-run every gate, paste the output
  - [ ] Raise the PR into `feat/companion-c3`

### Review Findings

<!-- bmad-code-review 2026-08-01: 3 layers (Blind Hunter, Edge Case Hunter, Acceptance Auditor), 8 patch / 2 defer / 8 dismissed -->

- [x] [Review][Patch] The blocking-wait scan misses `from time import sleep` — the one spelling the retired `_BANNED_IDENTIFIERS` ban DID catch [tests/unit/companion/test_images.py:1195-1198] — `_blocking_waits_in`'s `ImportFrom` arm only checks `_BLOCKING_MODULES` (which deliberately excludes `time`), so `from time import sleep` and `from time import sleep as pause` return `[]` — executed and confirmed by the Acceptance Auditor. The docstring claims `sleep` is "banned **through**" the module "with import aliases resolved", and the non-vacuity plant only probes `import time as clock_mod` — the guard is keyed on the syntax its own firing test uses (c3-3's headline finding verbatim; violates AC 6 + AC 23). Fix: treat `from time import sleep` (any alias) as `time.sleep` in the `ImportFrom` arm, track the bound name for bare calls, and add both plants. (blind+edge+auditor, HIGH)
- [x] [Review][Patch] The pool-timeout "cliff" is described as pinned but the pinning test cannot fire [tests/unit/companion/test_routes_card_image.py:1219] — `TestTheBurstDoesNotOutlastTheConnectionPool` monkeypatches `spacing=0.0`, so the shipped `FETCH_SPACING_SECONDS` never participates: raise the spacing to 1.0 and the test stays green while production 500s. `deps.py:309` and the deferred entry both say the hazard is "Pinned by" this test. Fix: add the arithmetic tripwire on the SHIPPED constant — `assert 99 * images.FETCH_SPACING_SECONDS < pool timeout` (with margin) — so slowing the pacer past ~0.3 s/tile goes red by arithmetic, which is exactly the register the docstring argues in. (blind+edge, MEDIUM)
- [x] [Review][Patch] `_wait_for_turn`'s cancellation docstring is false [src/companion/app/images.py:546-548] — "the next caller starts immediately" is wrong: the cancelled caller never advanced `_next_start`, so the next caller waits out the *previous starter's* remaining gap (the mid-spacing-cancellation test itself asserts a 0.1 s gap, not immediacy). Behaviour correct, sentence wrong, in a codebase that gates docstring accuracy. (blind+edge, LOW)
- [x] [Review][Patch] `stalled_cdn` docstring claims "a pacer on virtual time"; it builds a real-time pacer with `spacing=0.0` [tests/unit/companion/test_routes_card_image.py:941,963] — no clock/sleep injected; zeroed spacing also nullifies the turnstile entirely (`_next_start > now` never true). Different regime than described. (blind, LOW)
- [x] [Review][Patch] The 200×`sleep(0)` "every chance to be admitted" wait is the bare-yield race the same file declares unsound [tests/unit/companion/test_routes_card_image.py:1007,1061] — `_until`'s own docstring documents that a fixed yield count is "a race against a thread" (measured failing); if requests 5–6 are still in the aiosqlite thread after 200 zero-time yields, the cap assertion passes vacuously. Fix: use short real sleeps (the `_until` granularity) for the settle window. (blind, LOW)
- [x] [Review][Patch] The one-pacer scan's bound-callable evasion is undeclared [tests/unit/companion/test_images.py, `_pacer_calls_in`] — `cls = images.Pacer; cls()` / `getattr(images, "Pacer")()` construct a second pacer invisibly; every other AST guard in this repo declares its residual holes, this one asserts its two spellings are "how a second pacer would actually arrive". Fix: declare the residual hole in the guard's docstring, house style. (blind, LOW)
- [x] [Review][Patch] Doctest example hardcodes `4` and doctests are not collected [src/companion/app/images.py:487] — `>>> Pacer().available_permits` → `4` duplicates `FETCH_CONCURRENCY` with no gate (no doctest flags in pyproject); a machine-checkable number in prose, unchecked. (blind, LOW)
- [x] [Review][Patch] "No assertion below would change if the machine were ten times slower" is contradicted by `_until`'s own 0.5 s ceiling [tests/unit/companion/test_routes_card_image.py:916,932] — 500 × 1 ms gives up; on a sufficiently loaded box a correct app fails. Bounded-and-loud is fine; the absolutist sentence is false as written. (blind, LOW)
- [x] [Review][Defer] httpx's closed-client `RuntimeError` escapes the `except` tuple as a raw 500 [src/companion/app/images.py:751] — a request still queued in the pacer when lifespan teardown closes `image_client` gets `RuntimeError("client has been closed")`, not in `(TimeoutError, httpx.HTTPError, httpx.InvalidURL)`. Window pre-exists from c3-5 (any in-flight fetch at teardown); this story's queue widens it. Uvicorn's graceful drain covers the normal path; catching `RuntimeError` wholesale would mask programming errors — deferred, pre-existing shape.
- [x] [Review][Defer] Two hand-synchronised stall-able CDN fakes created in parallel [tests/unit/companion/test_images.py:588 `Upstream`; test_routes_card_image.py:889 `StallableCdn`] — near-identical recorders (requested/in_flight/peak/release-Event) in two files; the ledgered two-copies defect class (c3-2 Debug Log 3, c3-3 finding 2) — deferred, consolidate to conftest when a third consumer appears.

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| Pacing is **one backend-global semaphore plus request spacing**, never per-route or per-client | AD-11 | The whole story; "exactly one" is AC 2's gate |
| Pacing is `async` throughout and must never block the event loop | AD-11 | A queued burst must not eat the 250 ms push budget (NFR-05) |
| Fetching is **lazy**; the backend never pre-fetches a deck | AD-11 | AC 13 asserts zero fetches on a deck read |
| The pacer wraps the client; the client is **not** the pacer | `images.py:302-303`, shipped | Q1 may not answer "inside `httpx`" |
| `build_app()` has zero side effects; the lifespan owns effects | AD-10 | Construction may be free, but it may not happen at import-for-effect |
| The status is derived from the token, never chosen at the call site | `errors.py` | A queue ceiling, if Q4 takes one, is a token — not a `status_code=` |
| A route declares only the tokens it uniquely produces | c3-1 AC 6, c3-4 review | Unchanged unless Q4 adds a token |
| One generator, from the backend's own `app.openapi()` | AD-12 | Never hand-edit `openapi.json`; regenerate or leave alone |
| `Note:` and `Warning:` are **wire-visible**; other Google sections are truncated | c3-2 review | Q4's decision is a wire decision |
| Ban the family, never enumerate members | C2 retro, standing | AC 2 and AC 6's scans are family-keyed |
| Probe your own guard before review does | C2 retro, standing | AC 24's five probes are not optional |
| Claims require verification | standing | Paste real output; run the generator, do not predict it |
| Copy lives in `EXPERIENCE.md` and is gated | c2-9 | This story ships **no copy** and no UI state |

### The seven things this story must not break

1. **`tests/unit/companion/test_routes_card_image.py`'s three-family guard** — you are removing one
   family from a set that protects two more. A careless edit that deletes the frozenset takes
   c3-7's and c3-8's fences with it, silently, and neither story exists yet to notice.
2. **`tests/unit/companion/test_import_boundary.py`** — both guards, AST-only, unchanged, no
   exclusions. *"A guard satisfied by obfuscation is theatre."*
3. **`test_openapi_contract.py`'s byte comparison** and `test_committed_schema.py`'s whole-artifact
   pin — a docstring edit you did not mean to make is a red CI, and the fix is regeneration, never
   a hand edit.
4. **`test_deps.py::test_a_failing_image_client_close_does_not_strand_the_engine_dispose`** — if Q1
   puts anything new in `_shutdown`, this test's ordering claim is the one to re-derive.
5. **`test_app.py`'s lifespan tests** — `test_startup_failure_propagates` pins that **only**
   discovery publication may fail at startup. A pacer that can raise on construction breaks that
   asymmetry; a pacer that cannot, does not.
6. **`test_spa.py`** — nothing here adds a route or a router, so it owes nothing. If it goes red,
   something unintended was registered.
7. **`test_routes_cards.py` and `test_images.py`'s existing 40-odd fetch tests** — every one of them
   now goes through the pacer. If the pacer's defaults are what the unit tests run under, a 100 ms
   spacing silently adds ~4 s to the suite. **AC 9's runtime claim is what catches that**, and the
   answer is the injected seam, not a smaller constant smuggled into production.

### Source tree — what exists, what this story touches

```
src/companion/app/
  images.py               EDIT — the pacer (the spine's `app/images.py # proxy: pacer, disk
                                 cache, negative cache` line, :452); the two constants; the
                                 timing seam; three forward-dated paragraphs rewritten
  main.py                 EDIT — the lifespan constructs it (only under Q1's app-state option)
  routes/cards.py         EDIT — only under Q4 (a wire-visible `Warning:`), else untouched
scripts/dump_openapi.py   EDIT (docstring only) — c3-6 shipped and needed nothing; c3-7 next
tests/unit/companion/
  test_images.py              EDIT — the pacer's unit tests, on the fake clock
  test_routes_card_image.py   EDIT — `_BANNED_IDENTIFIERS` (four names out, ten stay), both
                                 pairings, the single-pacer guard, the behavioural tests
  test_routes_decks.py        VERIFY — AC 13's zero-fetch assertion may live here instead
  test_deps.py                VERIFY — shutdown ordering, only under Q1's app-state option
ui/src/api/
  openapi.json, types.d.ts    REGENERATED **only under Q4** — expected byte-identical otherwise
ui/README.md              EDIT — only under Q4
plugin/**                 REBUILT — required by CI's drift gate
_bmad-output/implementation-artifacts/deferred-work.md   EDIT
```

**Not touched, deliberately:** `src/companion/app/errors.py` and `src/companion/contracts.py` (no
new token under Q4's proposal), `src/companion/app/deps.py` (**unless** Q6 rules the session hold
is addressed here, and unless landmine 6's docstring needs correcting — a docstring fix is not a
behaviour change), `src/companion/client.py` (**c6-1** owns the sending half; it is a *localhost*
client and nothing about this pacer applies to it), `src/companion/app/security.py`,
`src/companion/app/spa.py`, `src/companion/app/state.py`, `src/data/**`, `src/logic/**`,
`src/mcp_server/**`, `src/viewer/**`, and every file under `ui/src` (**c4-4** owns the tile).

### Previous story intelligence (c3-1 … c3-5, and their eight review passes)

- **Sixteen of sixteen stories have answered their open questions "as proposed"** (one partial).
  The questions below are written to be answerable the same way, but **Q1, Q4, Q5 and Q6 are
  genuine forks** — they change what ships.
- **The round-1 5/5 Greptile cause is confirmed four times running**: the same-day three-layer
  `bmad-code-review` before raising the PR. Task 8.
- **c3-5's review theme was *the fetch trusted a response `client.get()` had already swallowed*** —
  a constant that documented a protection the code did not deliver, because the check ran after the
  thing it was meant to prevent. **The pacer is exposed to the identical shape**: a semaphore
  acquired after the request is issued, or a spacing computed from completion times rather than
  start times, paces nothing while reading exactly like it does. Probes (d) and (b) exist for that.
- **c3-4's review theme was *prose outrunning code***. Applied here twice: the constants' docstrings
  must not claim compliance with a rule that exempts this host family (AC 3), and the "one global
  choke point" sentence must be a gate before it is a paragraph (AC 2).
- **c3-3's headline finding**: a guard caught **0 of 12** planted evasions because every family was
  keyed on the syntax its own firing tests used. The guard-shaped things here are AC 2's
  single-construction-site scan and AC 6's synchronous-sleep scan. **Plant an evasion against each
  before trusting it.**
- **c3-2's finding**: a true count read as a false rule, published to the wire. Applied here: "a
  100-card deck is 99 fetches" is true of *this* corpus and of the grid's `normal` size only — a
  detail-panel `large` or a DFC flip adds keys. Do not write the number into a wire description.
- **c3-1's R1 finding**: `TestNotShadowedBySpa` passed with the router *deleted*. Applied here:
  a pacing test that asserts only "the response arrived" passes with the pacer deleted. **Assert the
  recorded start ordering and the in-flight count**, which cannot be produced by an absent pacer.
- **c3-1's R3 finding**: identical fixtures prove nothing. Applied here: two fetches must be
  distinguishable in the recorder (different URLs), or an "ordering" assertion is comparing a thing
  to itself.
- **c3-5's own two guards caught their author before review did** — both by being probed in the
  direction their author had not considered. Budget time for that; it is the pattern, not luck.
- **`plugin/**` is not "not touched"** (c3-1's finding 1). A stale mirror is a guaranteed red build.

### Git intelligence

- `4765bc6` — PR #33 merged c3-5 into `feat/companion-c3` (confirmed: local `334d072`, the Greptile
  P1 empty-body fix, is an ancestor of it). `3bfe95f` — PR #32, c3-4. `737ce76` — PR #31, c3-3.
  `2a787ac` — PR #30, c3-2. `a52d6f8` — integration PR #28 on master.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a
  Greptile pass per story**, one integration PR to master after the retro with **no** Greptile pass
  (OSS free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`. The shape to copy: one small `feat`
  commit, then a separate review-patch commit, then the records commit.

### Gotchas specific to this story

- **`sleep`, `Lock`, `Semaphore` and `BoundedSemaphore` are banned in `images.py` today.** The
  suite goes red on your first line of production code, and that red is the guard working. Fix it
  in Task 3 deliberately, not reflexively.
- **A semaphore alone is not spacing, and spacing alone is not a cap.** The epic asks for both
  (`:1720`), and they bind under different conditions — the arithmetic table in § What the real data
  says shows spacing binding at normal latency and the cap binding on a degraded CDN. A design that
  collapses them into one number satisfies neither AC 4 nor AC 5.
- **Spacing must be measured between *starts*, not completions.** Completion-based spacing degrades
  to serialisation the moment the CDN is slow, which is the opposite of a concurrency cap.
- **`asyncio.Semaphore` is fair on CPython's asyncio** (waiters wake FIFO), but do not *rely* on
  strict fairness in an assertion unless you have measured it on this interpreter — assert ordering
  where you have arranged it, not as a general property.
- **`async with` on the semaphore is what makes cancellation safe** (AC 7). A manual
  `acquire()`/`release()` pair around an `await` leaks a permit on `CancelledError`, and a browser
  navigating away from a deck view is exactly that cancellation, ~99 times.
- **`asyncio.timeout` and the queue wait** — `_FETCH_TOTAL_SECONDS` currently wraps the whole
  exchange inside `fetch_image`. If the pacer wait moves *inside* that block, the last tile of a
  cold deck burns its entire 20 s budget queueing and then times out on a fetch that never started.
  Q4 rules it; the failure mode is stated here so it is not discovered.
- **The `DbSession` is still open while you queue** (Task 0 proves it). Pool: 15 connections, 30 s
  timeout, measured. A pacer slower than roughly 0.3 s/tile would push a 99-tile burst past the pool
  timeout and produce a **`sqlalchemy.exc.TimeoutError`**, which is **not** a `DatabaseError` and
  would therefore surface as `500 internal_error`, not `503`. That is the cliff the proposed
  constants sit comfortably away from — and the reason Q6 exists rather than being waved off.
- **Do not let production defaults into the unit suite's hot path.** Forty-odd existing fetch tests
  now traverse the pacer; at 100 ms each that is seconds of pure sleep. AC 9's runtime measurement
  is the detector and Q3's seam is the answer.
- **`mypy --strict` and `--platform win32`** are both gates, and `ruff` `N`/`UP` apply to the new
  code. Google-style docstrings on every public function; module docstring mandatory.
- **No new dependency.** `asyncio` is stdlib and `httpx` is already top-level. Adding none is part
  of the story.
- **`format` is a field name, not a builtin misuse** (project-context.md) — irrelevant here, noted
  because ruff `N` is on.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that
  exactly one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client`, `isolated_data_dir`, `image_shapes`, `_point_at`, `_seed`,
  `_ready_database`, `Recorder` and `cdn`. Do not write a second seam.
- **No unit test may touch the network, and none may sleep for real time to prove a rate** (AC 9).
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. **`npx tsc -b --force` is a separate claim from `npm test`** — c3-2
  measured `tsc -b` caching a clean result over a real failure.

### Architecture rules this story implements

- **AD-11** — the single backend-global semaphore plus request spacing, `async` throughout, lazy
  fetching, and the named owners for the parts it defers (c3-7, c3-8, c10-3).
- **NFR-08** — rate-spaced fetches, the half c3-5 could not deliver. The attribution half is c2-10's
  and shipped; the Fan Content notice is c8-2's.
- **NFR-05** — the pacer must not eat the 250 ms push budget; the cold-deck ~12 MB / ~10 s figure is
  an **expected observation**, and first-fetch image paint is excluded from the budget by the NFR's
  own text.
- **AD-10** — `build_app()` has zero side effects; the lifespan owns anything with an effect.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; this story's claim is
  that it produces **no diff**, and the claim is settled by running it.
- **AD-16** — unchanged: no new token under Q4's proposal, and any queue answer would be a token
  with a status, never a hand-built response.
- **AD-1 / AD-2 / NFR-02** — existing repositories, no second shape, read-only w.r.t. the database.

### Latest technical information (external — banked by c3-5 on 2026-08-01, do not re-research)

- **Sustained traffic under 10 requests/second with 50–100 ms between calls**; excess earns `429`
  and a ~30-second lockout.
- **The `*.scryfall.io` file origins — the image CDN this route talks to — are explicitly exempt
  from that guidance.** This does **not** relax AD-11: the pacer is an architectural decision about
  being a good citizen and about not letting a 100-card burst eat the 250 ms push budget. **AC 3
  requires the constants' docstrings to say this**, so the numbers are chosen knowingly rather than
  presented as compliance they are not.
- **A descriptive `User-Agent` is required and generic agents are routinely blocked** — already
  shipped by c3-5's `_user_agent()`; nothing to do.
- **Scryfall asks consumers to cache what they download, for at least 24 hours** — c3-7's disk
  cache, not this story's.

Sources: [Scryfall API rate limits](https://scryfall.com/docs/api/rate-limits) ·
[Scryfall API docs](https://scryfall.com/docs/api)

### References

- [epics-companion-app.md § Story 3.6](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (1710-1739); **3.7's disk cache** (1741-1774) and **3.8's failure signalling**
  (1776-1803), whose scope this one must not absorb; **Story 10.3** (3560-3599), which owns the
  real profiling and the two ACs this story cannot satisfy; NFR-05 (157-160), NFR-08 (170-172)
- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) —
  **AD-11 (242-270)**, AD-10, AD-12, AD-16, and the Structural Seed's `app/images.py` line (452)
- [c3-5 story record](c3-5-card-image-endpoint-with-face-resolution-and-a-defined-parameter-contract.md) —
  the shipped seam, the eleven review patches, the banked Scryfall research and the guard this
  story must edit
- [deferred-work.md](deferred-work.md) — the **c3-6-homed entry** (the unpaced window) plus the
  c3-7 and c3-8 entries that fence this story's scope
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — the standing agreements (ban the
  family; probe your own guard) and action item 6 (same-day three-layer review)
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — Who owns the pacer instance, and how is bypassing it made impossible?** *(genuine fork)*

AD-11 says *"one backend-global semaphore"*; the epic says *"exactly one pacer in the process — not
one per route, per card, or per client"*. Three ways to have one:

| Option | Verdict |
| --- | --- |
| **A `Pacer` in `images.py`, one instance created in the lifespan beside `image_client`, and passed to `fetch_image` as a required parameter** | **Proposed.** It mirrors the client exactly — same module, same creation site, same substitution seam a test already patches — and the *required parameter* is what makes AC 1 structural: there is no signature that fetches without pacing, so a future caller cannot forget. It needs no teardown, so `_shutdown` and its ordering test are untouched. The honest cost: "one per app" is not literally "one per process" when a test builds forty apps — which is a **feature** (no cross-test bleed) and is worth stating rather than glossing |
| A module-level singleton in `images.py` | **The real alternative**, and it is the literal reading of "backend-global": constructed once at import, reached by everything, impossible to have two of. Rejected because a module-global with mutable timing state leaks between tests — one test's spacing debt becomes the next test's delay — and because `deps.Database`'s docstring already rules against exactly this shape for its lock: *"never a module-level one, which would serialise unrelated apps in a test run and hide a real double-creation bug behind a global"* |
| The pacer inside `build_image_client` (a custom transport wrapper) | **Rejected**, and it is rejected by a shipped sentence: *"This is not the pacer and must not grow into one: c3-6 adds its semaphore around this client, not inside it."* A transport-level pacer would also silently pace anything else that client is ever used for |

*Recommendation: as proposed. Record the measurement that `_shutdown` and `test_deps.py` needed no
edit — the same way c3-5 recorded that `test_spa.py` did not.*

---

**Q2 — The two constants.**

Proposed: **spacing `0.1 s` between fetch starts** and a **concurrency cap of `4`**.

- **0.1 s is not arbitrary and it is not compliance.** It is the top of Scryfall's published
  50–100 ms band *and* it is the number that reproduces the epic's own acceptance observation:
  99 distinct tiles × 0.1 s = **9.9 s**, against the epic's *"roughly 12 MB over roughly 10
  seconds"*. Choosing the conservative end of a band that does not even apply to this host family
  is the good-citizen posture AD-11 asks for, and the docstring must say both halves.
- **The cap is what the spacing cannot do.** At normal latency it never binds
  (`min(1/0.1, 4/0.2) = 10/s`, spacing wins). It binds when the CDN is *slow*: at 2 s latency the
  rate falls to 2/s and at most 4 sockets are open, where an uncapped pacer would hold ~20. **A
  struggling upstream should receive less traffic, not the same amount spread over more
  connections** — that is the cap's entire job, and it is why AC 5 tests it under an
  arbitrarily-slow CDN rather than a normal one.
- Both are module constants with the arithmetic in their docstrings; neither is configurable by
  environment in MVP (nothing needs it, and a knob is a supported interface).

*Recommendation: as proposed, both numbers, with the exemption note (AC 3) in the spacing
constant's docstring.*

---

**Q3 — How is a rate tested without spending real time?**

Proposed: **the pacer takes its clock and its sleep as constructor parameters**, defaulting to
`time.monotonic` and `asyncio.sleep`. Unit tests pass a fake pair that advances a counter instead of
waiting, so AC 4, 5 and 10 assert **exact** start offsets at zero wall-clock cost, and the
99-request cold-deck reproduction (AC 10) runs in milliseconds.

Two alternatives and why not: driving real `asyncio.sleep` with a tiny interval proves the *shape*
but not the *number*, and it is the flaky-on-CI pattern this AC exists to forbid; monkeypatching
`asyncio.sleep` globally in a fixture reaches every await in the process, including httpx's, which
makes failures unreadable.

The seam is two parameters with defaults — it is not a strategy object, a registry or a clock
abstraction — and the route never passes them.

*Recommendation: as proposed. Note in the record whether the existing forty-odd fetch tests needed
the fake pair or simply a zero interval; either is fine, and AC 9's runtime measurement is the
proof.*

---

**Q4 — Queue-wait semantics, and does the wire say anything about them?** *(genuine fork)*

Three parts.

*Where the wait sits.* Proposed: **outside `_FETCH_TOTAL_SECONDS`.** That constant is documented as
*the whole-exchange deadline* — it bounds a conversation with an upstream, and a request that has
not started has no exchange to bound. Putting the queue inside it would make the 99th tile of a cold
deck fail its own 20 s budget having never sent a byte.

*A ceiling on queueing.* Proposed: **none in MVP.** The natural bound is the caller: a browser that
navigates away cancels the request and releases the slot (AC 7), and the only other caller today is
a test. A ceiling would need either a new token (eight ripple sites, for a state no consumer can
act on differently from `image_fetch_failed`) or a false reuse of the transient one. The fallback —
answering `image_fetch_failed` after N seconds queued — is defensible and is what a later story
should take if a real queue ever misbehaves; c3-8 owns the retry semantics that would make it
meaningful.

*What the wire says.* Proposed: **nothing.** The route docstring's wire-visible paragraphs stay
byte-identical, `npm run gen:api` produces no diff (AC 15), and the queueing behaviour is described
in `images.py`'s module docstring and in code comments — read by developers, not published to
`types.d.ts`. The alternative is honest and costs little: a `Warning:` telling c4-4 that a cold-deck
tile can take ~10 s, which regenerates both files and is a real service to the story that builds the
tile. **The reason for proposing silence is that c4-4 needs the *number*, and the number is a
property of this corpus and this machine** — publishing it into the wire contract is exactly c3-2's
"a true count read as a false rule". Put it in `ui/README.md`'s blind-spot section instead, which is
where c4-4 will actually look.

*Recommendation: as proposed, all three parts — with the `ui/README.md` row as the compensating
control for the third.*

---

**Q5 — Does this story take in-flight coalescing?** *(genuine fork)*

The epic's CM-2 AC — *"an image fetched once is not fetched again"* — is the **disk cache, c3-7**,
and this story cannot satisfy it. But there is one neighbouring behaviour c3-6 could honestly own:
**single-flight**, where two requests for the *same* URL arriving while a fetch is already in flight
share that fetch instead of queueing a second one.

| Option | Verdict |
| --- | --- |
| **Decline it; c3-7 owns it with the cache** | **Proposed.** It is a *cache* behaviour, not a *pacing* behaviour: the thing being shared is a result, and the module that will hold results is c3-7's. Building an in-flight result map here means c3-7 either inherits a second cache or deletes one. c3-4's ruling applies with unusual force — *"an unused hook is a design decision made by a story that cannot see the requirements"* — and the requirement here is genuinely unseen: whether the shared result is the bytes, the disk path, or a `Future` depends entirely on what c3-7 builds. Cost, stated: a browser that renders the same card twice on one screen fetches it twice. **Measured, that costs 0 extra fetches on both 98/99-id decks — every deck entry is a distinct id, and duplicate *printings* collapse in `deck_cards` before they reach the route** |
| Take it | **The real alternative.** Duplicate concurrent requests for one URL are the one storm shape a semaphore does *not* prevent, and it is ~15 lines. Rejected on ownership, not on merit — and it becomes obviously right the moment a surface renders the same id twice (a suggestion row beside the deck grid, **c6-4**), which is why the ruling gets a `deferred-work.md` entry either way |

*Recommendation: as proposed — decline, ledger it on c3-7 by name with the measured zero-cost
finding, and note the c6-4 trigger that would change the answer.*

---

**Q6 — The database session is held across the queue wait. Address it here, or ledger it?**
*(genuine fork)*

Measured, not assumed: the pool is `AsyncAdaptedQueuePool`, **size 5 + overflow 10 = 15
connections**, `pool_timeout` **30 s**; and FastAPI runs a `yield`-dependency's teardown *after* the
endpoint returns, so `DbSession` is checked out for the whole endpoint body — including the fetch,
and now including the queue wait. Task 0 proves this before anything is built on it.

| Option | Verdict |
| --- | --- |
| **Accept, pin and ledger** | **Proposed.** Under the Q2 constants a 99-tile burst drains in ~9.9 s, so no request comes near the 30 s pool timeout, and the pool's 15-connection ceiling merely means at most 15 requests sit inside the route while the rest wait outside it — a second queue in front of the first, which is inefficient and harmless. Pin it with a test that a large burst completes without a pool timeout, so the interaction is on the record and a later story that slows the pacer sees the cliff. Ledger the arithmetic — including that a `sqlalchemy.exc.TimeoutError` would surface as `500 internal_error`, **not** `503`, because it is not a `DatabaseError` |
| Restructure the route to release the session before fetching | **The real alternative**, and it is the *clean* answer: read the row, close the session, then queue. Rejected for this story because it means this one route stops using `DbSession` — the annotation c3-1 through c3-5 standardised on and whose docstring says *"the annotation every data-backed handler writes, and the only one it should"* — for a problem that does not bite at the proposed constants. It is a real improvement and belongs beside **c4-1**'s hydration cache, which is already carrying this route's "reads the whole card row" ledger entry |
| Raise `pool_size` | **Rejected.** It changes a shared recipe (`src/data/database.create_engine`) used by the MCP server for a companion-only symptom, and more connections to one SQLite file buys nothing |

*Recommendation: as proposed — accept, pin, ledger on c4-1, and correct `deps.py`'s "the first
consumer that goes on to do something after the session closes" sentence, which Task 0 is likely to
show is simply wrong.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5[1m]`), via `bmad-dev-story`, 2026-08-01.

### Open questions — Brad's answers

**All six as proposed — the 17th story running.**

| Q | Ruling | Consequence |
| --- | --- | --- |
| Q1 | **A `Pacer` in `images.py`, one instance in the lifespan, passed to `fetch_image` as a required parameter** | AC 1 is structural: no signature fetches unpaced. `_shutdown` and `test_deps.py` needed **no edit** — measured, see Debug Log 4 |
| Q2 | **Spacing `0.1 s`, cap `4`**, both with the arithmetic and the exemption note | `FETCH_SPACING_SECONDS`, `FETCH_CONCURRENCY`; the exemption is gated by a test that reads the docstring off the AST |
| Q3 | **Clock and sleep as constructor parameters** | The whole suite gained 39 tests and got *faster*; nothing sleeps to prove a rate |
| Q4 | **Queue outside `_FETCH_TOTAL_SECONDS`; no ceiling; wire says nothing** | `npm run gen:api` produced **no diff at all** — confirmed by running it. The ~10 s figure went into `ui/README.md`'s blind-spot table for c4-4 |
| Q5 | **In-flight coalescing declined, homed on c3-7** | Ledgered with the measured zero-cost finding and c6-4 named as the trigger |
| Q6 | **Accept, pin, ledger on c4-1** | Task 0 proved the premise; the pool interaction is pinned by a 99-request burst test |

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-6-image-pacer` cut from `feat/companion-c3` at **`4765bc6`** (confirmed
against `origin`).

| Gate | Baseline | After |
| --- | --- | --- |
| `uv run pytest` | **2286 passed, 1 skipped — 149.60 s** | **2325 passed, 1 skipped — 147.77 s** |
| `ruff check .` | clean (0.1 s) | clean |
| `ruff format --check .` | 305 files formatted (0.1 s) | clean |
| `mypy src/` | 89 files clean (15.0 s) | clean |
| `mypy src/ --platform win32` | 89 files clean (3.8 s) | clean |
| `npm run lint` | clean (5.7 s) | clean |
| `npm run format:check` | clean (1.3 s) | clean |
| `npx tsc -b --force` | clean (2.0 s) | clean |
| `npm test` | **568 passed, 31 files** (4.6 s) | **568 passed** (unchanged by design) |
| `npm run build` | 195.14 kB js (1.8 s) | identical |

**The story's inherited suite count was stale**: it said Python 2275 (c3-5's final run); measured
at the same commit it is **2286 passed + 1 skipped**. Re-measured rather than inherited, as AC 25
required.

**Schema at baseline:** 7 paths, 12 components — both re-counted, both matching the story.

**SPA bundle + plugin mirror at baseline** (SHA-256, first 16): `index-DE70muY2.js FAEEEA472ADD5078`
· `index-DmxBiI94.css 0A3C142D84B5A98D` · `space-grotesk…woff2 0640890476FC1198` ·
`favicon.svg 9BE16EA2FE3670DE` · `index.html 8E65C0615CF66044`. Mirror identical on all five.
**Re-measured after the story: identical on all five, in both trees** — this story ships no runtime
frontend code, exactly as predicted.

**The deck numbers, re-verified read-only against the live 40-deck corpus** — the story's figures
are confirmed:

| Claim | Story | Measured |
| --- | --- | --- |
| decks with ≥90 cards | 18 | **18** |
| distinct-id range | 67–99 | **67–99** |
| median distinct ids | ~78 | **78** |
| distinct ids across all decks | 1,061 | **1,061** |
| 99-id deck shape split | 93 one-image + 6 per-face = 105 face images | **93 + 6 = 105** |

One correction to the story's table: it names *"the two 98/99-id decks"*, but there are **three** —
`Atraxa Counter Cabinet` and `Atraxa Counter Cabinet v2 (owned)` are both 99, and
`Infinite Guideline Station v2 (owned)` is 98. Conclusion unaffected; the count was wrong.

**The session hold (landmine 6 / Q6) — proved, not inherited.** A throwaway test read the live
pool from inside the mocked CDN handler, i.e. from inside `fetch_image`:

```
TASK 0 SESSION-HOLD MEASUREMENT
  engine = True
  checkedout_during_fetch = 1
  pool_class = AsyncAdaptedQueuePool
  pool_size = 5
  overflow_max = 10
  timeout = 30.0
  checkedout_after_response = 0
```

**Q6's premise holds and `deps.py`'s sentence was wrong.** The session is held *across* the fetch,
not closed before it; all four pool numbers match the story. The scratch test was deleted after
measuring and the claim now lives in a shipped test (`TestTheBurstDoesNotOutlastTheConnectionPool`).

### Debug Log References

1. **The guard c3-5 built against this story fired on the first line of production code**, exactly
   as designed: `AssertionError: images.py reaches for ['Lock', 'Semaphore', 'sleep']`. Taken down
   deliberately in Task 3, not reflexively. (`BoundedSemaphore` never fired — the pacer uses a plain
   `Semaphore` — which is why the family, not the member, was the right thing to remove.)
2. **A structural pin the story did not name went red, and it is the third consecutive story to hit
   one** (c3-2 Debug Log 3, c3-3 finding 2). c3-3's `TestNoRuleInTheShell` bans the literals
   `60`/`15`/`4` anywhere in `src/companion`, and `FETCH_CONCURRENCY = 4` is a CDN concurrency cap
   with no deck vocabulary near it. **Ruled: `4` is declared out of the limit family**, joining `1`
   and the adjacent spellings (`3`, `5`, `16`) that were already declared out on precisely the
   ubiquity argument that applies to `4` — keeping it in was the order of discovery, not a stance.
   The copy limit stays covered by the `.quantity` family (enforcing it means counting copies), the
   residual hole is stated, and both directions are probed. The alternative was renaming a ruled
   production constant to appease a guard, which is the obfuscation that guard's own docstring says
   to treat as a violation. **This is a decision beyond the story and Brad may want to overturn it.**
3. **The first `_until` helper waited on a non-monotonic quantity and it cost a false green** — see
   Probe (a).
4. **Q1's prediction confirmed by measurement**: `_shutdown`, `test_deps.py` and
   `test_app.py::test_startup_failure_propagates` all needed **no edit**. A pacer needs no teardown
   and cannot fail on construction, so neither the shutdown ordering nor the startup asymmetry moved.
   `test_spa.py` likewise untouched: no router, no route.
5. **`test_import_boundary.py` passes unchanged with no exclusions added** (AC 17), run explicitly.

### Probe outputs

Six probes; **five caught, one found a real hole and one found a false green.** Every mutation was
verified on disk before the verdict and every revert verified by SHA-256 against the pre-probe hash
(`images.py 7F18907B…DDCBDF3F`, `main.py 2FE6C638…EA0246D8` — both `True` at the end).

| # | Mutation | Result |
| --- | --- | --- |
| **(a)** | semaphore removed, spacing left | **6 failed** — both cap tests, both cancellation tests, at unit *and* route level. **But `test_health_answers_repeatedly_while_a_burst_of_images_is_queued` PASSED**, see below |
| **(b)** | spacing removed, semaphore left | **4 failed**, headline `assert 0.0 == 9.8` — the cold-deck paint collapsing to instant |
| **(c)** | a second pacer, spelled to evade (`from …images import Pacer as RateGate`) | **2 failed** — `src/companion constructs 2 pacers ([('main.py', 191), ('cards.py', 51)])`, named through the alias |
| **(d)** | pacer acquired *after* the fetch | **11 failed** — spacing, cap and cancellation all collapse |
| **(e)** | `asyncio.sleep` → `time.sleep` | **5 failed**, incl. the source scan naming `['time.sleep']`; the run took 12.6 s because the loop really blocked |
| **(f)** | spacing from **completions**, not starts | **PASSED all 75 tests — a real hole**, see below |

**Probe (a) caught its author first.** `test_health_answers…` passed with the semaphore deleted.
The cause: it waited on `in_flight == 4`, which is **not monotonic** — it is briefly true on the way
up from 1 to 6, and by the final assertion the first four fetches had completed and decremented it
back under the cap. Rewritten to wait on `len(requested)`, which only grows, then spin further
turns and assert the count exactly. Under probe (a) it now reports
`6 of 6 requests reached the CDN while none had completed; the cap is 4`. The class also dropped
from 229 s to 1.2 s, because the false wait was burning its whole timeout.

**Probe (f) found a genuine hole, and it is c3-5's review theme in this story's costume.** Spacing
computed from the previous *completion* rather than the previous *start* passed **every one of the
75 unit tests**, because a mocked fetch is instantaneous — completion time and start time coincide,
so nothing in the suite could distinguish the two designs. In production they diverge exactly when
it matters: completion-based spacing serialises the moment the CDN slows down, which is the
opposite of what a concurrency cap is for. Closed by
`test_spacing_is_between_starts_even_when_nothing_has_completed`, which drives four fetches against
a CDN that **never answers** — start-based admits all four one spacing apart; completion-based has
no completions to space from and reports `[0.0, 0.0, 0.0, 0.0]`.

**And the first attempt at probe (f) was mis-constructed**: it moved the cursor advance into a
`try/finally` with no `yield` in it, which executes immediately and is therefore the same code
relocated. It passed, and that pass meant nothing. Rebuilt properly (the `finally` moved into
`slot()`, after the `yield`) before any verdict was filed — c3-1's lesson about reading probe output
rather than filing it.

### Completion Notes List

**What shipped.** `images.Pacer` — one `asyncio.Semaphore` (the cap) plus a turnstile-guarded
spacing cursor (the rate), created once in the lifespan beside `image_client`, and passed to
`fetch_image` as a **required** parameter so no signature exists that fetches unpaced. Two named
constants carrying their own arithmetic. No new dependency, no new reason token, no new route, no
router edit, **and no wire change at all**.

**The five things worth knowing.**

1. **The regeneration prediction was confirmed by running the generator, not by argument.**
   `npm run gen:api` → `git status --porcelain` lists neither generated file. Seven paths, twelve
   components, byte-identical. `dump_openapi.py`'s forward-dated claim is now a measured fact and
   has been restated as shipped, with c3-7 named next.
2. **The determinism worked.** 40-odd existing fetch tests now traverse the pacer and the suite got
   **faster** — 149.60 s → 147.77 s with 39 more tests. The reason is Q1's per-app pacer: each test
   builds its own app, so each pays zero spacing on its first fetch and there is no cross-test
   timing debt. Nothing in the suite sleeps to prove a rate.
3. **Two of the epic's six ACs have owners rather than paraphrases.** CM-2's *"a repeat request
   makes no CDN request"* is **c3-7**'s (there is no cache here and a repeat request repeats the
   fetch — said in the module docstring, the record and `deferred-work.md`). The
   `POST /agent/events` half of the never-blocks-the-loop AC names an endpoint that does not exist
   until c5-1/c5-5 and is **c10-3**'s; `/health` is the stand-in, with five interleavings asserted
   by *count* so a serialised loop fails it, and the substitution is recorded rather than passed off.
4. **The guard came down by one family of four; ten names stayed.** Both of c3-5's pairings were
   reworked rather than deleted: the scanner test still proves it sees an aliased `Semaphore` (that
   property is what c3-7's and c3-8's families depend on) while asserting it is no longer *banned* —
   and the prose plant that read *"No Semaphore here — the pacer is c3-6's"* was rewritten, because
   it had become false. A third test was added to keep the two claims apart: *the scanner sees it*
   and *the ban refuses it* used to be one assertion, and conflating them is what would have made
   this removal look like removing coverage. The positive half is stronger than the ban was: the
   gate is now *"`src/companion` constructs exactly one pacer"*, probed with an aliased second one.
5. **Q6 is pinned, not fixed, and the arithmetic is on the record.** A 99-request burst completes
   with the pool asserted at size 5 / overflow 10 / timeout 30 s, so the story that eventually slows
   the pacer past ~0.3 s per tile will find the cliff named — including that the resulting
   `sqlalchemy.exc.TimeoutError` surfaces as `500 internal_error`, **not** `503`.

**One decision beyond the story, flagged for Brad**: declaring `4` out of c3-3's limit family
(Debug Log 2). It is consistent with that guard's own stated reasoning and both directions are
probed, but it narrows a guard that survived a round-2 review, and overturning it means choosing a
different concurrency cap instead.

**Seven-row forward-dated-comment table, all worked:**

| # | Location | Action taken |
| --- | --- | --- |
| 1 | `images.py` module docstring | **Rewritten** — the unpaced-window paragraph is gone; c3-7's and c3-8's absences stay and gained CM-2 and coalescing by name |
| 2 | `_FETCH_TOTAL_SECONDS` | **Present tense**, plus Q4's queue-outside-the-deadline ruling and why |
| 3 | `build_image_client` | **True** — says where the pacer went and that the client still is not it |
| 4 | `scripts/dump_openapi.py` | **Confirmed by measurement**, restated as shipped, c3-7 named next |
| 5 | `test_routes_card_image.py` | Four names out, ten stay; both pairings reworked, a third added |
| 6 | `deps.py`'s `DbSession` | **Corrected** — Task 0 disproved "after the session closes"; replaced with the measurement and the pool arithmetic |
| 7 | `deferred-work.md`'s c3-6 entry | **Resolved by name**, with the three things it did not price |

### File List

**Production (4)**

- `src/companion/app/images.py` — the two constants, `Pacer`, `image_pacer`, `_fetch_within_deadline`; `fetch_image` gains a required `pacer`; three forward-dated paragraphs rewritten
- `src/companion/app/main.py` — the lifespan constructs the one `Pacer`; its docstring says why here
- `src/companion/app/routes/cards.py` — reads the pacer beside the client, one guard for both
- `src/companion/app/deps.py` — **docstring only**; corrects the false "after the session closes" claim

**Scripts (1)**

- `scripts/dump_openapi.py` — **docstring only**; the c3-6 prediction restated as measured, c3-7 named

**Tests (3)**

- `tests/unit/companion/test_images.py` — `FakeClock`, `_pacer`, `Upstream`, and the pacer's unit tests (constants, spacing, cap, cancellation, cold deck, one-pacer scan, blocking-wait scan, required-parameter); 17 existing `fetch_image` call sites updated
- `tests/unit/companion/test_routes_card_image.py` — `_BANNED_IDENTIFIERS` (4 out, 10 stay) and its three pairings; `StallableCdn`, `_until`; the `/health` interleaving, cancellation, zero-pre-fetch and pool-burst tests
- `tests/unit/companion/test_routes_format_check.py` — `_LIMIT_LITERALS` narrowed to `{60, 15}` with the ruling written into its docstring; the `copy-limit` case re-homed onto the `.quantity` family; three new firing/silent cases

**Docs and records (3)**

- `ui/README.md` — new blind-spot row for the pacer's ~10 s cold-deck queue (Q4's compensating control for c4-4); the deck-rule guard row updated to five declared holes
- `_bmad-output/implementation-artifacts/deferred-work.md` — the c3-6-homed entry resolved; six new entries with named homes
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status and narrative

**Mirror (4, rebuilt not hand-edited)**

- `plugin/server/src/companion/app/{images,main,deps,routes/cards}.py`

**Not changed, and each verified rather than assumed:** `ui/src/api/openapi.json`,
`ui/src/api/types.d.ts` (regenerated, byte-identical), everything under `ui/src`,
`src/companion/app/{errors,security,spa,state}.py`, `src/companion/contracts.py`,
`src/companion/client.py`, `tests/unit/companion/test_import_boundary.py`, `test_deps.py`,
`test_app.py`, `test_spa.py`, and the SPA bundle in both trees.

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-01 | Story created — context engine analysis over the epic, AD-11, the shipped `images.py`/`cards.py`/`main.py`/`deps.py`, c3-5's record and its eleven review patches, the guard c3-5 built against this story, the live 38,261-card database and 40 saved decks, and the installed toolchain's pool defaults |
| 2026-08-01 | Implemented Tasks 0–7 → status `review`. All six open questions as proposed (17th story running). `images.Pacer` ships — one semaphore plus start-spacing, constructed once in the lifespan, required parameter on `fetch_image`. No wire change: `npm run gen:api` produced **no diff**, confirming `dump_openapi.py`'s forward-dated prediction by measurement. Four names out of `_BANNED_IDENTIFIERS`, ten stay, both pairings reworked and a third added. Python 2286 → **2325** passed with the suite runtime **down** 1.8 s (149.60 s → 147.77 s); frontend 568 unchanged; bundle and mirror re-measured byte-identical. Six mutation probes: five caught, **probe (f) found a real hole** (completion-based spacing was invisible to all 75 tests) and **probe (a) found a false green in my own test** (a non-monotonic wait) — both closed. One decision beyond the story, flagged: `4` declared out of c3-3's deck-limit family after `FETCH_CONCURRENCY = 4` tripped it |
