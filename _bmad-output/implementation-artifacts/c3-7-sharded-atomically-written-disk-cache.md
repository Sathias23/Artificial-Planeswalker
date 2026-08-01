---
epic: c3
story: c3-7
work_branch: feat/companion-c3
story_branch: feat/companion-c3-7-image-disk-cache
depends_on: c3-6 (PR #34, merged into the umbrella at 2927336) — `images.Pacer`, the lifespan-owned `image_client` + `image_pacer`, `fetch_image(client, url, pacer)`, the allow-list, the two image tokens, and the `_BANNED_IDENTIFIERS` family that names this story
baseline_commit: 2927336
---

# Story C3.7: Sharded, atomically written disk cache

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad running this app for months,
I want cached card art stored somewhere predictable and never half-written,
so that the cache survives crashes and I can find and delete it when I want to.

**What this story really is.** c3-5 opened the socket. c3-6 put a queue in front of it. This one
puts a *floor* under it — and it is the first story in this feature that **writes to the user's
disk**.

Four things follow from that one fact, and each of them changes what "correct" means:

1. **This is the first write path in `src/companion`, in a package whose defining guard is that it
   never writes.** AD-2 makes `src/mcp_server` the sole writer and
   `tests/unit/companion/test_import_boundary.py` enforces it. That guard is about the *database* —
   it bans repository write methods, session mutators, DML constructs and schema creation — and it
   explicitly permits file I/O (`_SRC_FILE_FLUSH`, id `file-flush-in-atomic-write`, was added for
   `discovery.py`'s temp+rename). So the guard does not fire, and **that is the landmine**: the one
   test whose name promises "the companion never writes" will stay green while this story teaches
   the companion to write ~12 MB per deck. The boundary being crossed is real; the guard that
   sounds like it covers it does not. Say so out loud rather than letting a green suite imply
   otherwise.
2. **The first blocking call on the async path, and the shipped guard is structurally blind to
   it.** `test_images.py::TestTheLoopIsNeverBlocked` scans `images.py` for synchronous waits — its
   `_BLOCKING_MODULES` set is `{threading, concurrent.futures, multiprocessing, subprocess}` plus
   `time.sleep`, resolved through aliases. A `Path.read_bytes()` or an `os.fsync()` is none of
   those. AD-11 says the image path is *"`async` throughout — it must never block the event
   loop"*; a synchronous file read satisfies every test in the repository and contradicts the
   architecture decision. **Q2 rules it, and whatever is ruled needs a guard that can see it**
   (c3-3's headline finding, third story running: a family keyed on the syntax its own firing test
   uses catches nothing else).
3. **The second story running that must take down a fence a previous story wrote against it — and
   this time the fence is eight names, not four.** `_BANNED_IDENTIFIERS`
   (`test_routes_card_image.py:661-675`) bans `mkdir`, `makedirs`, `open`, `write_bytes`,
   `write_text`, `data_dir`, `NamedTemporaryFile` and `replace` from `images.py` under the comment
   *"c3-7's disk cache"*, leaving `lru_cache` and `cache` for c3-8. c3-6 established exactly how
   this is done — **remove your family, leave the rest, restate the comment, and replace the ban
   with a positive gate that is stronger than the ban was.** Copy that, including the part where
   both non-vacuity pairings are reworked rather than deleted.
4. **This is the story that satisfies the epic AC c3-6 could not.** CM-2 — *"an image fetched once
   is not fetched again within the cache lifetime"* — was homed here by name, in `images.py`'s
   module docstring, in c3-6's record and in `deferred-work.md`. It is now yours, and it is the
   only one of this epic's six ACs that another story has been waiting on.

**Everything numeric in this story was measured on this machine at `2927336` against the shipped
38,261-card database and the installed toolchain, read-only. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **The module names you three times, and one of the three is a *ruling*, not a note.**
   `src/companion/app/images.py:36-56`:

   * *"**no disk cache** — story **c3-7**, which also owns the cache directory under
     ``data_dir()``. Nothing here writes a file, and ``build_app()`` creates no directory
     (AD-10). This is also where the epic's CM-2 acceptance criterion lives… **c3-6 does not
     satisfy it and does not pretend to**"* — becomes false the day you ship; rewrite it, keep
     c3-8's absence, and make the CM-2 sentence a *shipped* claim rather than a homed one.
   * *"**no in-flight coalescing** — also **c3-7** (Q5, Brad 2026-08-01)… it was declined here on
     ownership rather than merit: the thing being shared is a *result*, and whether that result is
     bytes, a disk path or a ``Future`` depends entirely on what c3-7 builds"* — **that sentence
     names the question you now have the information to answer** (Q5 below). Whichever way it goes,
     the paragraph stops being a deferral and becomes a decision.
   * *"no negative cache and no backoff — story **c3-8**"* — untouched, and it must stay accurate.

2. **There is exactly one outbound call site and it is already a function with a required pacer.**
   `images.fetch_image(client, url, pacer)` (`:617`) is called once, from `routes/cards.py:286`.
   c3-6 made the pacer a **required parameter** specifically so no signature exists that fetches
   unpaced — *"there is no signature here that fetches unpaced, so a future caller cannot forget
   one"*. Whatever shape Q1 takes, **that property must survive**: a cache that lets a caller reach
   the network by a second door undoes AC 1 of the story before it.

3. **The lifespan is where effectful things are made, and it now has three of them in a row.**
   `main.py:188-191` creates `deps.Database()`, `state.ActiveDeckSlot()`,
   `images.build_image_client()` and `images.Pacer()` on consecutive lines, each with its own
   documented reason for being there rather than in `build_app()`. `_shutdown` (`:81-119`) closes
   the client under try/finally and disposes the engine. **A cache needs no teardown**, exactly
   like the pacer — but unlike the pacer, **creating it can fail**, and that is what makes Q6 a
   real question rather than a formality.

4. **`build_app()` may not resolve a data path, and the reason is stated in its own docstring.**
   `main.py:3-6`: *"it… resolves no data path, because :func:`src.paths.data_dir` ends in
   ``mkdir(parents=True, exist_ok=True)`` and would therefore *create* the data directory just by
   being called."* `discovery.py:88-92` says the same for `discovery_path()`: resolved **at call
   time, never at import**, and never as a default argument. A module-level
   `_CACHE_ROOT = paths.data_dir() / "image_cache"` in `images.py` would break AD-10 by *importing*
   the module. This is the single easiest mistake available in this story.

5. **The atomic write already exists in this repository and it is fully reasoned.**
   `src/companion/discovery.py:114-175` (`write_discovery`) is the template, and its docstring
   carries every decision you would otherwise re-derive: `tempfile.mkstemp(dir=target.parent)`
   rather than a fixed `.tmp` name (two writers cannot splice); the temp file in **the target's own
   directory** because `os.replace` is atomic only within one filesystem; `os.replace` rather than
   `os.rename` because *"the latter raises ``FileExistsError`` over an existing file on Windows"*;
   `os.fdopen` with a `BaseException` guard so a failed `fdopen` does not leak the descriptor (and
   on Windows hold the temp file against the unlink); cleanup under
   `contextlib.suppress(OSError)` so a cleanup failure never displaces the real error; and the
   directory deliberately **not** fsynced. **Read it before writing a line.** The one decision it
   makes that this story should probably *not* copy is `os.fsync` — see Q3.

6. **`src.paths` is importable from `src/companion/app` and `PLANESWALKER_DATA_DIR` already works
   end to end.** `singleton.py` and `discovery.py` both call `paths.data_dir()`; the AD-3 leaf
   allow-list names `src.paths` explicitly; and `tests/unit/companion/conftest.py`'s **autouse**
   `isolated_data_dir` fixture points `PLANESWALKER_DATA_DIR` at each test's own `tmp_path`. So
   **every companion test already gets a private cache directory for free** — you inherit
   isolation rather than building it, and a test that writes into the developer's real
   `%LOCALAPPDATA%` is a bug in your code, not a missing fixture.

7. **`Recorder` records every URL in order, and `cdn` patches the factory not the client**
   (`test_routes_card_image.py:57-104`). A cache hit records **nothing**, which is exactly the
   assertion CM-2 needs: `cdn.requested == [url]` after *two* requests is the whole story in one
   line. `StallableCdn` (`:878`) parks every request on an `asyncio.Event` for the concurrency
   tests. `test_images.py` has a near-identical `Upstream` — **you are the third consumer, and
   `deferred-work.md` names you as the trigger to consolidate them** (see landmine 14).

8. **`IMAGE_CACHE_CONTROL` and the `nosniff` header are already right for both paths.**
   `routes/cards.py:291-295` stamps `Cache-Control: public, max-age=31536000, immutable` and
   `X-Content-Type-Options: nosniff` on the success response. A warm hit is the same success
   response and inherits both with no code. `error_response` stamps `no-store` on every typed
   error feature-wide. Nothing to do; stated so it is not re-done, and so a divergence between the
   cold and warm answers is recognised as a defect rather than shipped as a subtlety.

9. **`ErrorReason` is closed at ten and this story adds none.** A cache read failure, a cache write
   failure and a missing shard are all *invisible* to the caller by design: the fetch still
   answers. The only outcome vocabulary is what c3-5 shipped. If you find yourself wanting an
   eleventh token, the design went wrong — see AC 9.

10. **The face/size contract is fixed and the cache key must mirror it exactly.** `ImageSize` is a
    closed six-member `Literal`; `face` is `Query(ge=0)` bounded by `len(resolve_face_images(...))`.
    The cache is reached **only after** `card_not_found`, `no_image_data` and the size lookup have
    all passed, so every key the cache ever sees is already validated. That is what makes the path
    components safe — and it is a reason to state, not a reason to skip the containment assertion
    (AC 5).

11. **c3-6's `Pacer` must not be entered on a cache hit.** NFR-06 is *"after image-cache warm-up,
    the app is fully functional with no network access"* and the epic's own AC is *"the app runs
    with no network after the cache is warm → it is served from disk"*. A cache check that sits
    *inside* `pacer.slot()` would make a warm 99-tile deck take 9.9 seconds and hold the CDN's rate
    budget against a request that never leaves the machine. The check goes **before** the pacer,
    and AC 6 turns that into a measurement on c3-6's injected clock rather than a sentence.

12. **`cards.py`'s module docstring makes a claim this story either implements or corrects.**
    `routes/cards.py:4-6` calls `read_card` and `read_card_image` siblings sharing *"same
    identifier, same corpus, **same cache story**"*. `deferred-work.md` records that there is no
    cache story on the `read_card` side at all, and homes the repair on *"**c3-7** (the sharded
    disk cache) or **c4-1** (the hydration cache), whichever lands first — and whichever it is
    should either implement the shared story or correct that docstring."* You land first. Q1's
    scope note answers it; the wrong answer is to leave the sentence.

### The guard c3-6 left standing against this story, and how it must come down

13. **`_BANNED_IDENTIFIERS` (`test_routes_card_image.py:661-675`) is now two families, and one of
    them is yours:**

    | Family | Members | Owner |
    | --- | --- | --- |
    | the disk cache | `mkdir`, `makedirs`, `open`, `write_bytes`, `write_text`, `data_dir`, `NamedTemporaryFile`, `replace` | **c3-7 — this story** |
    | the negative cache | `lru_cache`, `cache` | c3-8 — **stays banned** |

    c3-6 wrote the procedure down by doing it; follow it exactly. **Eight names out, two stay**,
    and **three** paired tests move with them:

    - `test_the_scan_sees_a_planted_breach_of_each_family` (`:771-818`) asserts `"mkdir" in names`
      with the message *"the disk-cache family missed a method call on a local"*. That assertion is
      about the **scanner**, not the ban — it proves an AST walk sees a method call on a local,
      which is the property c3-8's `lru_cache`/`cache` family still depends on. **Keep the scanner
      proof, move the name out of `_BANNED_IDENTIFIERS`, restate the message** — exactly what c3-6
      did with `Semaphore`.
    - `test_a_planted_breach_of_a_surviving_family_actually_fires_the_ban` (`:821-840`) plants
      `NamedTemporaryFile` and asserts `names & _BANNED_IDENTIFIERS == {"NamedTemporaryFile"}`.
      **That becomes `set()` and the test becomes a lie that passes as a failure.** Re-plant it on
      a surviving family (`lru_cache` / `functools.cache`), or the firing half of the guard is
      gone with no red to announce it.
    - `test_the_scan_ignores_prose_that_merely_names_the_banned_things` (`:843-864`) plants the
      docstring *"Nothing here calls mkdir or data_dir, and there is no lru_cache."* Two thirds of
      that sentence stops being a ban. The prose-immunity claim is still worth proving — re-plant
      it so it is proving something.

    **The positive half is this story's, and it is where the teeth go.** With the ban gone, nothing
    stops `images.py` writing anywhere it likes. c3-6's replacement for the pacer ban was *"`src/
    companion` constructs exactly **one** pacer"*, probed with an aliased second construction site.
    The analogue here is stated in AC 4 and AC 5: **one write site, and every path it can produce
    is under the cache root.**

14. **`test_import_boundary.py` stays unchanged with no exclusions added.** Nothing about a disk
    cache wants a banned *database* write path. Stated because every story in this epic has been
    tempted by something — and because this is the story where a green import-boundary suite is
    most likely to be misread as "the write guard covered it" (see § What this story really is,
    point 1).

15. **`TestExactlyOnePacer` and `TestTheLoopIsNeverBlocked` (`test_images.py:1106-1296`) are c3-6's
    and both are load-bearing here.** The first scans all of `src/companion` for `Pacer()`
    construction sites and asserts exactly one, in the lifespan — a `DiskCache` constructed in the
    lifespan under Q1 does **not** disturb it, but it should be **mirrored** rather than left
    unguarded. The second is the blind-to-file-I/O scan of § point 2, and it is the guard Q2's
    ruling has to extend.

### What the real data says (measured at `2927336`, read-only)

**The extension is not derivable from the size key, and it is measured to three digits.** Over all
**245,760** stored image URLs in the shipped 38,261-card corpus:

| Size key | `.jpg` | `.png` |
| --- | --- | --- |
| `small`, `normal`, `large`, `art_crop`, `border_crop` (top-level) | 35,404 each | 0 |
| `png` (top-level) | **3** | 35,401 |
| all six (per-face) | 5,556 each except `png` | `png`: 5,556 |

The three exceptions are the `https://errors.scryfall.com/soon.jpg` placeholders on
**Sparkspitter**, **Ondu Champion** and **Gorehorn Minotaurs** — real cards, already seeded by
`test_routes_card_image.py`'s allow-list test. So `<ext>` must come from the **resolved URL or the
response `Content-Type`, never from the size name**; a cache filename of `png_0.png` holding JPEG
bytes is silent and corrupts a cache rather than failing (`deferred-work.md`, the c3-5-homed entry,
Severity Medium **for this story**). **Exactly two extensions exist across the whole corpus:
`.jpg` and `.png`.**

**The shard is well chosen and the arithmetic is measurable.** Card ids are Scryfall uuid v4s, so
the first two hex characters are uniform:

| Property | Measured |
| --- | --- |
| Distinct two-hex shards used | **256 of 256** |
| Cards per shard | **107 – 218**, mean **149.5** |
| Card directories, flat | **38,261** — AD-11's *"roughly 60,000 entries"* |

**A real deck's warm footprint.** From c3-6's measurement, re-verified: a 100-card deck resolves to
**67–99 distinct card ids** (median ~78 over the 18 saved decks with ≥90 cards); the grid asks for
face 0 at `normal` only, so a cold paint is **~99 files**. Across all 40 saved decks there are
**1,061 distinct card ids** — the whole warm footprint of this user's library at one size, roughly
**130 MB** at the epic's ~124 KB average. That average is **arithmetic** (12 MB ÷ 99 tiles), not a
measurement; the real-bytes measurement is **c10-3**'s (epic `:3588-3590`) and this story must not
claim it.

**A prediction to verify rather than assume, and it is the one that tells you the key is right.**
`test_routes_card_image.py:490-515` drives **three different card ids that share one URL**
(`https://errors.scryfall.com/soon.jpg`) and asserts `cdn.requested == [url] * 3`. Under AD-11's
key — **id + size + face, never the URL** — those are three distinct cache entries and the test
should pass **unchanged**. If it goes red, the key was built on the URL, which would also make
every data refresh a full cache miss (`deferred-work.md`, the cache-buster entry). Run it and say
which happened.

**Existing fetch tests that repeat a request are the regression surface.** Forty-odd tests now
traverse the cache. Two shapes matter and both were checked at the baseline:

* `test_the_same_recorder_does_see_a_card_that_fetches` (`:245-258`) requests **two different**
  cards through one client — unaffected.
* the six-size parametrisation (`:281`) and the face tests use **distinct keys** — unaffected.
* `TestTheColdDeckPaint` (`test_images.py:992`) and `TestTheBurstDoesNotOutlastTheConnectionPool`
  (`test_routes_card_image.py:1203`) drive **99 distinct** urls/ids — unaffected, *provided* the
  cache is reached through the real key. A test that starts recording fewer fetches than it did is
  either CM-2 working or a key collision; **read which**, do not assume.

**Committed artifacts at `2927336`, expected byte-identical (AC 12):** `ui/src/api/openapi.json` —
**7 paths** (`/api/active-deck`, `/api/card-image/{scryfall_id}`, `/api/cards/{card_id}`,
`/api/deck/{deck_id}`, `/api/deck/{deck_id}/format-check`, `/api/decks`, `/health`) and **12
components** (`ActiveDeck`, `ActiveDeckRequest`, `Card`, `CardFace`, `CardSummary`,
`DeckCardSummary`, `DeckDetail`, `DeckSummary`, `ErrorResponse`, `FormatCheckReport`,
`FormatCheckRow`, `HealthResponse`). `scripts/dump_openapi.py:34-35` already predicts it — *"Story
**c3-7**'s disk cache is next and is expected to be the second: a cache changes where bytes come
from, not what the operation promises."* **Confirm by running the generator, not by argument.**

**Toolchain on this machine:** Python **3.12.13** · FastAPI **0.140.0** · Starlette **0.48.0** ·
SQLAlchemy **2.0.44** · Pydantic **2.12.0** · httpx **0.28.1** · anyio **4.11.0** · uvicorn
**0.51.0**. `anyio` is **not** a declared dependency in `pyproject.toml` — it arrives transitively
through Starlette and httpx. `asyncio.to_thread` is stdlib and needs nothing (Q2).

**Suites at the baseline, to be re-measured not inherited:** Python **2325 passed, 1 skipped —
147.77 s** · frontend **568 passed, 31 files**. SPA bundle SHA-256 (first 16), identical in
`src/companion/app/static/` and the `plugin/` mirror: `index-DE70muY2.js FAEEEA472ADD5078` ·
`index-DmxBiI94.css 0A3C142D84B5A98D` · `space-grotesk…woff2 0640890476FC1198` ·
`favicon.svg 9BE16EA2FE3670DE` · `index.html 8E65C0615CF66044`.

---

## Acceptance Criteria

### The cache itself

1. **The path is exactly AD-11's, character for character** (epic `:1749-1752`, NFR-09):
   `data_dir()/image_cache/<id[0:2]>/<id>/<size>_<face>.<ext>`. Asserted as a **constructed string**
   against a known id, size and face — not as a regex, and not by round-tripping the writer's own
   output through the reader (which passes with both halves wrong). The two-hex shard is stated
   with its measured justification: 256 shards, 107–218 cards each, against a flat 38,261.

2. **`<ext>` comes from the resolved URL or the response `Content-Type` — never from the size
   key** (`deferred-work.md`, c3-5-homed, Severity Medium). Pinned by a test over the **three real
   cards** whose `png` size resolves to a `.jpg` URL (Sparkspitter, Ondu Champion, Gorehorn
   Minotaurs — already seeded in `test_routes_card_image.py`), asserting the file that lands on
   disk is `png_0.jpg` and not `png_0.png`. Paired with an ordinary `png` card that *does* land as
   `.png`, so the assertion is a discrimination rather than a constant.

3. **The key is id + size + face and excludes the URL's `?<timestamp>` cache-buster** (AD-11).
   Two consequences, both asserted: three different cards sharing one URL produce **three** cache
   entries and three fetches (the shipped `errors.scryfall.com` test, predicted to pass
   unchanged — see § What the real data says); and a card whose stored `image_uris` changes still
   hits the **existing** entry. The second is the documented staleness AD-11 *accepts*
   (epic `:1763-1766`) — it is asserted and documented, **not** solved, and the docstring says so.

4. **Every cache write is atomic: a uniquely-named temp file in the target's own directory, then
   `os.replace`** (epic `:1754-1757`, NFR-09). `discovery.write_discovery` is the template and its
   reasoning is inherited rather than re-derived: `mkstemp` over a fixed `.tmp` name, the temp file
   beside the target (one filesystem), `os.replace` over `os.rename` (Windows `FileExistsError`),
   the `os.fdopen` descriptor guard, and cleanup under `contextlib.suppress(OSError)`. **A crash
   mid-write can never leave a truncated file a later read would serve**, asserted directly: a
   write interrupted after the temp file exists and before the replace leaves the target absent (or
   at its previous contents) and leaves no `.tmp` litter.

5. **There is exactly one write site, and every path it can produce is inside the cache root** —
   the positive gate replacing the removed `_BANNED_IDENTIFIERS` family (landmine 13). Asserted two
   ways: an AST scan of `src/companion` finding a single `os.replace`/rename-into-place site,
   **and** a containment assertion that the resolved cache path for any accepted `(id, size, face)`
   is under the resolved root. Both are guard-shaped and therefore both are paired non-vacuously
   (AC 20), the scan with a second write site **spelled to evade** (an aliased `from os import
   replace as move`, a differently-named local) per c3-3's lesson.

### Behaviour

6. **A repeat request makes no CDN request — the epic's CM-2 criterion, satisfied here at last**
   (epic `:1728-1730`, homed on this story by `images.py`, c3-6's record and `deferred-work.md`).
   Asserted from `Recorder.requested`: two requests for the same `(id, size, face)` produce **one**
   recorded URL and two identical `200` bodies. **And the warm path never enters the pacer**
   (landmine 11) — proven on c3-6's injected clock, not by wall time: a warm burst of 99 tiles
   advances the fake clock by **zero** spacing intervals, where the cold burst advances it by 98.

7. **With the cache warm and the network gone, the image is still served** (epic `:1772-1774`,
   NFR-06). Driven with a transport that **raises on every request** — not one that 404s — so a
   cache miss is a loud failure rather than a plausible one, and paired with an uncached key
   through the same transport that correctly answers `502 image_fetch_failed`.

8. **A cache hit is byte-identical to the cold answer, headers included.** Same body, same
   `Cache-Control: public, max-age=31536000, immutable`, same `X-Content-Type-Options: nosniff`,
   same status. The one field where cold and warm can legitimately differ is `Content-Type` — Q4
   rules it, and **whatever is ruled is asserted as an equality or as a named, tested divergence**;
   it is not left for c4-4 to discover that the second render of a tile has a different media type
   from the first.

9. **A cache failure is never a request failure** — and it introduces no new reason token
   (landmine 9). An unwritable directory, a `PermissionError` on `os.replace` (the realistic
   Windows case: another handle open on the target), a truncated or unreadable cache file, and a
   cache root that is a *file* rather than a directory all degrade to *"fetch it"* and log; none
   of them changes the response the client receives. Asserted for **read failure** and **write
   failure** separately, each with the served response checked, not merely the absence of an
   exception.

10. **Fetching stays lazy and nothing pre-fetches or pre-warms** (AD-11, epic `:1732-1734`). The
    cache is filled **only** by a request that was actually served. `GET /api/deck/{deck_id}`
    triggers zero outbound requests and writes zero files — the second half is new and is asserted
    by listing the cache root, paired with a tile request that *does* write one.

11. **No eviction, no size accounting, no TTL, no index** (epic `:1768-1770`, AD-11). The cache is
    unbounded in MVP. Building any hook, counter, manifest or sweep is out of scope on c3-4's
    ruling — *an unused hook is a design decision made by a story that cannot see the
    requirements* — and the documented location and removal command are **c8-2**'s (epic
    `:3185-3212`), not this story's. The expected footprint is recorded here so c8-2 inherits a
    measured number rather than a guess: **1,061 distinct ids ≈ 130 MB** at one size for this
    user's whole 40-deck library.

### The wire contract

12. **The regeneration prediction is confirmed by running the generator, not by argument.**
    `npm run gen:api` is run and `git status --porcelain` is pasted. The expected result is **no
    diff at all** — 7 paths, 12 components, byte-identical — which also confirms
    `dump_openapi.py:34-35`'s forward-dated claim and makes it the **second** measured instance of
    a behaviour-only story. Any wire-visible docstring edit (`main.py`'s `_DOCSTRING_SECTIONS`
    keeps the leading paragraph and any `Note:`/`Warning:`) makes that false and must be
    regenerated and committed, never hand-edited.

13. **Both drift gates are green from the same commit, output pasted:**
    `uv run pytest tests/unit/companion/test_openapi_contract.py`, and from `ui/`
    `npm run gen:types && git status --porcelain`.

14. **No frontend behaviour ships.** `ui/src` is unchanged. `ui/README.md` gains at most a
    blind-spot row if Q2/Q4 produce a number c4-4 needs; the SPA bundle in both trees is
    **re-measured** against the Task 0 hashes and expected byte-identical (AC 19).

### Boundaries, records and the mirror

15. **No database write path is opened and no banned module is imported.**
    `test_import_boundary.py` passes **unchanged with no exclusions added** (landmine 14) — run
    explicitly and pasted. **And the story record states plainly that this guard does not cover
    filesystem writes**, so a future reader does not mistake its green for coverage of what this
    story built.

16. **The forward-dated-comment inventory is repaired.** Each row becomes true, is re-homed, or is
    recorded with a judgement:

    | # | Location | What it says | Action |
    | --- | --- | --- | --- |
    | 1 | `images.py:36-43` | "**no disk cache** — story c3-7… **c3-6 does not satisfy [CM-2] and does not pretend to**" | **Becomes false** — rewrite; c3-8's absence stays and stays accurate |
    | 2 | `images.py:44-50` | "**no in-flight coalescing** — also c3-7… depends entirely on what c3-7 builds" | **Q5 answers it** — deferral becomes decision, either way |
    | 3 | `images.py:118-121` (`IMAGE_CACHE_CONTROL`) | "AD-11 keys the cache on id + size + face and **accepts serving a stale image**… (the ``?<timestamp>`` cache-buster is deliberately *not* part of that key)" | **Becomes present tense** — the key it describes now exists |
    | 4 | `routes/cards.py:4-6` | the two routes share "**same cache story**" | **Implement or correct** (landmine 12, `deferred-work.md`) |
    | 5 | `test_routes_card_image.py:661-675` + `:766-864` | the ban and all three pairings | **Landmine 13** — eight names out, two stay, three plants reworked, comments restated |
    | 6 | `scripts/dump_openapi.py:34-35` | "Story **c3-7**'s disk cache is next and is expected to be the second" | **Confirm by measurement**, restate as shipped, name **c3-8** next |
    | 7 | `deferred-work.md`'s five c3-7-homed entries | CM-2; coalescing; `<ext>`; the cache-buster key; the two CDN fakes | **Resolve each by name**, with what it did not price |

17. **`deferred-work.md` gains this story's residue with named homes**, at minimum: whatever Q3,
    Q4, Q5 and Q6 decline; the eviction policy and the documented removal command (**c8-2**); the
    real-bytes footprint measurement (**c10-3**); and the `read_card` cache story if Q1 scopes it
    out (**c4-1**). No residue in prose only.

18. **The five unconditionally c3-7-homed `deferred-work.md` entries are each closed or explicitly
    re-homed** — CM-2, in-flight coalescing, the `<ext>` derivation, the cache-buster/key note, and
    the two hand-synchronised stall-able CDN fakes (for which **this story is the third consumer
    the entry names as the trigger**). **Plus the one conditionally homed entry** — *"`GET
    /api/cards/{card_id}` sets no cache headers… **Home: c3-7** (the sharded disk cache) **or
    c4-1** (the hydration cache), whichever lands first — and whichever it is should either
    implement the shared story or correct that docstring"*. This story lands first, so it answers
    it (Q1's sub-question), and the entry is updated either way rather than left addressed to a
    condition that has already resolved.

19. **The plugin mirror is rebuilt and committed** (`uv run python -m scripts.build_plugin`), and
    the SPA bundle is **re-measured, not assumed**: `src/companion/app/static/` and its mirror
    expected byte-identical against Task 0's five hashes. A change is a finding to explain, not a
    rebuild to wave through (c3-1's finding 1: `plugin/**` is not "not touched").

### Testing

20. **Non-vacuity pairing on every guard-shaped assertion** (standing agreement): each proves it
    **fires** and proves it **stays silent** from the same invocation. Concretely — the one-write-
    site scan is paired with a planted second site spelled to evade; the containment assertion is
    paired with a path that escapes; the no-pre-fetch/no-pre-write assertion is paired with a
    request that *does* write; the CM-2 zero-second-fetch assertion is paired with a distinct key
    that *does* fetch.

21. **The cache's own tests live in `tests/unit/companion/test_images.py`** beside
    `TestResolveFaceImages`, `TestFetchImage`, `TestImageClient` and c3-6's pacer classes — the
    module owns the mechanism's unit tests. Route- and app-level behaviour (AC 6, 7, 8, 9, 10) goes
    in `test_routes_card_image.py`. Reuse `Recorder`, `cdn`, `lifespan_client`, `isolated_data_dir`
    and `image_shapes`; **do not write a second seam**, and **do not write a third stall-able CDN
    fake** — AC 18 says consolidate the two that exist.

22. **No test touches the network, no test writes outside `tmp_path`, and no test sleeps for real
    time.** The autouse `isolated_data_dir` fixture gives every test a private
    `PLANESWALKER_DATA_DIR`; a test asserting on the cache must resolve its root **through the same
    code the app uses**, never by rebuilding the path from `tmp_path` (which would pass with the
    production path wrong). c3-6's injected clock is what AC 6's zero-spacing claim rides on.

23. **At least five mutation probes are run, verified on disk before the verdict and reverted
    after** (standing agreement — *probe your own guard before review does*): (a) the cache read
    removed, so every request refetches; (b) the cache **write** removed, so nothing is ever
    stored; (c) the temp+replace collapsed into a direct `open(target, "wb")`, which passes every
    functional test and destroys the atomicity claim; (d) `<ext>` taken from the size key instead
    of the URL, which is silent on 245,757 of 245,760 URLs; (e) the shard dropped, so every file
    lands flat under `image_cache/`; and (f) — the one that maps onto c3-5's and c3-6's shared
    review theme — **the cache checked *after* the pacer slot is taken**, which caches correctly
    and paces a warm deck anyway. Paste each result and **read the output before filing it**
    (c3-1's review found three vacuous tests hiding inside a "19 failed" probe result; c3-6's probe
    (f) found a real hole and probe (a) a false green in its author's own test).

24. **Every gate is re-run and its output pasted**: `uv run pytest`, `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, plus
    the frontend gates from `ui/` (`lint`, `format:check`, **`npx tsc -b --force`**, `test`,
    `build`) and both drift checks. Suite counts **and total runtime** stated as *before → after* —
    a synchronous fsync per write would show up here and nowhere else. Baseline to beat, **to be
    re-measured not inherited**: Python **2325 passed, 1 skipped, 147.77 s** · frontend **568
    passed**.

---

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (standing agreement)
  - [x] `git fetch origin feat/companion-c3`; confirm the umbrella tip is **`2927336`** (PR #34,
        c3-6, merged 2026-08-01); cut `feat/companion-c3-7-image-disk-cache` from it
  - [x] Run and record with **durations**: `uv run pytest`, `ruff check`, `ruff format --check`,
        `mypy src/`, `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (count),
        `npm run build`
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*` and the `plugin/`
        mirror (AC 19); record the committed `paths` (expect 7) and `components` (expect 12)
  - [x] **Verify the corpus numbers yourself**, read-only: the `<ext>`-by-size table (expect
        `png`→`.jpg` exactly **3** times), the shard distribution (expect **256** shards,
        **107–218** per shard) and the 1,061 distinct ids across saved decks. If your corpus
        differs, the story's numbers are the claim and yours are the truth — record the difference
  - [x] **Measure what a cache write actually costs on this machine** before Q2/Q3 are acted on:
        time a `mkstemp` + write + `os.replace` of a 124 KB payload, with and without `os.fsync`,
        into the real data directory. That number is the evidence behind both rulings

- [x] **Task 1 — The cache mechanism** (AC 1, 2, 3, 4, 9; Q1, Q2, Q3, Q4)
  - [x] The key, the path and the extension rule in `images.py` per Q1 — resolved **at call
        time**, never at import or as a default argument (landmine 4)
  - [x] The atomic write, with `discovery.write_discovery` read first and its reasoning inherited
        rather than re-derived (landmine 5)
  - [x] The read, and the failure posture: every cache error degrades to *fetch it* and logs
  - [x] Unit tests **before** wiring it in — path construction, extension derivation, the three
        real `png`→`.jpg` cards, atomicity, and each failure mode

- [x] **Task 2 — Wiring it in** (AC 5, 6, 7, 8, 10; Q1)
  - [x] The orchestration: cache read → (miss) pacer → fetch → cache write → serve. **The cache
        check sits outside `pacer.slot()`** (landmine 11)
  - [x] `fetch_image`'s required-pacer property survives — no second door to the network
        (landmine 2)
  - [x] The cache root created by the lifespan, per Q6 — **never** `build_app()` (AD-10)
  - [x] The one-write-site scan and the containment assertion, each with its planted evasion

- [x] **Task 3 — The guard comes down, carefully** (AC 5; landmine 13)
  - [x] Eight names out of `_BANNED_IDENTIFIERS`; **two stay**; the family comment restated
  - [x] All **three** pairings reworked — the scanner proof keeps its `mkdir` claim with a
        restated message; the firing test is re-planted on a surviving family; the prose test
        stops planting names that are no longer banned
  - [x] Extend `TestTheLoopIsNeverBlocked` per Q2's ruling so the file-I/O shape is visible to it
  - [x] Re-run `test_import_boundary.py` explicitly and paste it (AC 15)

- [x] **Task 4 — The behavioural half** (AC 6, 7, 8, 9, 10, 20, 22)
  - [x] CM-2: two requests, one fetch — and the warm burst costing **zero** spacing on the
        injected clock
  - [x] Offline: a transport that **raises**, warm key served, cold key correctly `502`
  - [x] Cold-vs-warm response equality, including headers and Q4's `Content-Type` ruling
  - [x] Cache read failure and cache write failure, each with the served response asserted
  - [x] `GET /api/deck/{deck_id}` writes zero files, paired with a tile request that writes one
  - [x] Verify the three-cards-one-URL prediction (`test_routes_card_image.py:490-515`) and
        **state which way it went**

- [x] **Task 5 — The wire, confirmed rather than assumed** (AC 12, 13)
  - [x] `npm run gen:api`; paste `git status --porcelain`; state the diff (predicted: **none**)
  - [x] Both drift gates from the same commit

- [x] **Task 6 — Comments, docs, records** (AC 16, 17, 18, 19; Q5)
  - [x] Work the seven-row forward-dated-comment table
  - [x] Close or re-home all five c3-7-homed `deferred-work.md` entries, including consolidating
        the two stall-able CDN fakes into `conftest.py` (AC 18)
  - [x] Rebuild + commit the plugin mirror; re-measure the bundle against Task 0
  - [x] Fill the Dev Agent Record; update `sprint-status.yaml`; set status to `review`

- [x] **Task 7 — Probes** (AC 23)
  - [x] Six mutation probes, each verified on disk and reverted; paste and **read** each result

- [ ] **Task 8 — Same-day three-layer review before the PR** *(Brad runs this — `dev-story` stops
      at Task 7 with status `review`)*
  - [x] `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor) before the PR
  - [x] Apply patches, re-run every gate, paste the output — all 14 applied (1 resolved decision
        + 13 patches); gates: `uv run pytest` **2395 passed, 1 skipped — 123.40 s** (was 2386) ·
        `ruff check` clean · `ruff format --check` 305 files clean · `mypy src/` and
        `mypy src/ --platform win32` no issues in 89 files · `ui` lint / format:check /
        `tsc -b --force` / test (568) / build all clean · `gen:api` + `gen:types` **no diff** ·
        plugin mirror rebuilt, byte-identical on all three changed files
  - [x] Raise the PR into `feat/companion-c3` — **PR #35**, 2026-08-01, two commits (`2f048c0`
        feat incl. the 14 folded-in review patches, `7d29438` records)

### Review Findings (2026-08-01, three layers: Blind Hunter + Edge Case Hunter + Acceptance Auditor)

- [x] [Review][Decision] **Resolved: option 1 (Brad, 2026-08-01) — the `Content-Type` wins, URL suffix demoted to fallback; applied as a patch.** The URL suffix beats a disagreeing `Content-Type`, so the warm/cold divergence is NOT "bounded to parameters" — found by all three layers. `cache_extension` (images.py:693-702) prefers the URL's suffix; if the CDN ever serves `image/png` (or any servable non-SVG `image/*`) from a `.jpg`-suffixed URL, the entry is stored as `.jpg` and every warm hit serves `image/jpeg` under `nosniff` + `immutable` for a year while the cold answer said `image/png` — a full media-type flip, while `_image_response`'s docstring and `TestTheWarmAnswerMatchesTheColdOne` claim the divergence is bounded to parameters. Options: (1) flip the priority — Content-Type first, URL suffix as fallback, so the warm answer always matches what the cold path served; (2) keep URL-first and weaken the "bounded to parameters" claim, pinning the disagreement case as a named tested divergence; (3) serve-and-don't-cache when the two sources disagree.
- [x] [Review][Patch] The one-write-site scan is blind to `Path.replace`/`Path.rename` and to a rebound local, and the second evasion is pinned as a sanctioned non-firing case [tests/unit/companion/test_images.py:1899-1938] — `_write_sites_in` resolves only `Name` owners mapping to `os`/`shutil` and `ImportFrom` aliases; `temp_path.replace(target)` (genuine rename-into-place, the pathlib spelling the retired identifier ban DID catch) and `handler = os.replace; handler(...)` (the "differently-named local" AC 5 names as a required plant) both walk through silently, and the quiet-direction test plants exactly `handler = os.replace` and asserts silence. The deferred blind-spot entry declares only non-rename mechanisms. Extend the scanner (one-positional-arg `.replace`/`.rename` attribute calls — `str.replace` takes two — plus `Name`-assignment tracking of `os.replace`), rework both plants.
- [x] [Review][Patch] Q2's "reached only through `asyncio.to_thread`" is unenforced and its non-vacuity check is a substring over prose [tests/unit/companion/test_images.py:2144-2154] — inlining `_read_cached(...)` in `DiskCache.read` (deleting the `to_thread` hop) blocks the loop 4.97 ms/tile, passes every functional test, and keeps the gate green because helper names are not in `_FILE_IO_CALLS` and `"to_thread" in source` is satisfied by comments. Replace with an AST assertion: each sync helper is reached via an `asyncio.to_thread` call, and the async wrappers contain no direct call to either helper.
- [x] [Review][Patch] The warm read path has no size cap — the cold path's `_MAX_IMAGE_BYTES` guard does not exist on read [src/companion/app/images.py:776] — an oversized file at a valid cache path is read whole and served immutable; treat payloads over `_MAX_IMAGE_BYTES` as a logged miss.
- [x] [Review][Patch] Non-`OSError` failures in the cache path fail the request, contradicting "every failure is swallowed" [src/companion/app/images.py:957,1002-1009] — `asyncio.to_thread` itself raising (e.g. `RuntimeError` at interpreter shutdown) escapes `DiskCache.read`/`write` and 500s a request whose bytes were servable; broaden the catch in the two async wrappers to `Exception`, log, degrade to fetch/serve.
- [x] [Review][Patch] A stale entry under the other extension permanently shadows a freshly written one, and a poisoned sibling logs a WARNING on every request forever [src/companion/app/images.py:773-789] — `_read_cached` returns the first hit in fixed order and nothing ever removes the sibling; after a successful `os.replace`, unlink the other extension's entry under `suppress(OSError)`.
- [x] [Review][Patch] AC 3's refreshed-row consequence is asserted only in a shape that cannot fail, while `IMAGE_CACHE_CONTROL`'s docstring claims it is asserted [tests/unit/companion/test_images.py:2493-2510 region] — `DiskCache.read` takes no URL, so the cache-buster test is true by signature; add a route-level test that mutates the stored `image_uris` timestamp between two requests and asserts a hit with zero new fetches.
- [x] [Review][Patch] AC 2's three-real-cards disk pin drives only Sparkspitter to disk at `png` size [tests/unit/companion/test_routes_card_image.py] — the three-card route test requests only `normal`; parametrize the `png_0.jpg` disk assertion over all three named cards.
- [x] [Review][Patch] The prose-immunity pairing's justification is false and its scanner half cannot fire on prose by construction [tests/unit/companion/test_routes_card_image.py:3446-3465 region] — the docstring claims `images.py` "names `lru_cache`" (it does not, verified by grep), and `_negative_cache_reaches` parses imports/attributes only, so the assertion can never fail; correct the docstring and restate the test around the string-literal half that retains bite.
- [x] [Review][Patch] The burst seeder is duplicated inside the same file — the ledgered two-copies defect class, reintroduced by the diff that closed it [tests/unit/companion/test_routes_card_image.py] — `test_a_full_deck_sized_burst_completes_without_a_pool_timeout` re-implements `_seed_burst()`'s id scheme inline; call the helper.
- [x] [Review][Patch] The live-observed Windows same-key `os.replace` race lost its only route-level reproduction in this diff [tests/unit/companion/test_routes_card_image.py] — the burst fixture repair (99 distinct ids) removed the only real-filesystem two-writers-one-target traversal; the only remaining coverage monkeypatches `os.replace`. Add a route-level concurrent same-key test through the real tmp filesystem.
- [x] [Review][Patch] `_FILE_IO_CALLS` omits `stat`/`exists`/`is_file`/`touch` — the likeliest next edit ("check before read" in the async route) would be invisible to the loop guard [tests/unit/companion/test_images.py:2033 region] — add the probe-shaped members to the family now.
- [x] [Review][Patch] Ledger gaps — five residues live in prose only, violating AC 17's "no residue in prose only" [_bmad-output/implementation-artifacts/deferred-work.md] — add entries for: Q4's declined sidecar / warm `Content-Type` parameter drop; `.tmp` litter from a hard kill (no sweep exists, c8-2's entry covers cache content only); a transient startup `OSError` disabling the cache for the whole process (no retry, one WARNING at boot); an existing-but-unwritable root staying "enabled" and warning per write (~99/paint) because Q6's probe covers creation only; and `DiskCache`'s containment-by-contract (`card_id` validated only by the route's regex — declared blind spot homed on c3-8, the module's next caller).
- [x] [Review][Patch] AC 14's conditional was left unresolved — `ui/README.md` gains no blind-spot row and no recorded judgement, though Q4 produced a c4-4-facing fact (warm hits drop `Content-Type` parameters; a tile's second render can differ from its first) [ui/README.md] — add the row.
- Dismissed as noise (4): corrupt-but-nonempty entries served immutable (undetectable without the integrity infrastructure AD-11 declines; external tampering is outside the threat model); a warm hit masking a partial-wiring bug (unreachable — the lifespan sets all four state fields consecutively and any exception there fails the launch); the lambda false-positive in `_module_level_calls` (latent, false-positive direction, no consequence today); the CM-2 ledger entry naming `Recorder.requested` (verified accurate — the `cdn` fixture IS a `Recorder`).

---

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

| Ruling | Source | What it means here |
| --- | --- | --- |
| Cache path is `data_dir()/image_cache/<id[0:2]>/<id>/<size>_<face>.<ext>`, **temp + rename** | AD-11 | AC 1 and AC 4; not a design space |
| Cache key is **id + size + face**; a changed `image_uris` serves the stale entry | AD-11 | AC 3 — accepted and documented, never "improved" by keying on the URL |
| **No eviction in MVP**; documented location + removal command are **c8-2**'s | AD-11, NFR-09 | AC 11 — no counter, no sweep, no manifest |
| `build_app()` has zero side effects; the lifespan owns effects | AD-10 | The cache root is created in the lifespan; nothing resolves `data_dir()` at import |
| Fetching is **lazy**; the backend never pre-fetches a deck | AD-11 | AC 10, now with a no-pre-*write* half |
| The pacer wraps the client; every outbound fetch passes one choke point | AD-11, c3-6 | A cache hit skips the pacer; a cache miss may not skip it |
| The backend never serves a substitute image | AD-11 | A corrupt or unreadable cache entry is a *refetch*, never a served placeholder |
| The status is derived from the token, never chosen at the call site | `errors.py` | AC 9 adds no token and no `status_code=` |
| One generator, from the backend's own `app.openapi()` | AD-12 | Never hand-edit `openapi.json`; regenerate or leave alone |
| `Note:` and `Warning:` are **wire-visible**; other Google sections are truncated | c3-2 review | A route-docstring edit is a wire decision |
| Ban the family, never enumerate members | C2 retro, standing | AC 5's scans are family-keyed |
| Probe your own guard before review does | C2 retro, standing | AC 23's six probes are not optional |
| Claims require verification | standing | Paste real output; run the generator, do not predict it |
| Copy lives in `EXPERIENCE.md` and is gated | c2-9 | This story ships **no copy** and no UI state |

### The seven things this story must not break

1. **`_BANNED_IDENTIFIERS`' surviving family.** You are removing eight names from a set that still
   fences c3-8. Deleting the frozenset takes an unwritten story's fence with it, silently, and
   c3-8 does not exist yet to notice. c3-6 removed four names from ten and left six standing —
   copy the procedure, not just the outcome.
2. **`test_import_boundary.py`** — both guards, AST-only, unchanged, no exclusions. *"A guard
   satisfied by obfuscation is theatre."* And see AC 15: its green does not mean what it sounds
   like for this story.
3. **`test_openapi_contract.py`'s byte comparison** and `test_committed_schema.py`'s whole-artifact
   pin — a docstring edit you did not mean to make is a red CI, and the fix is regeneration, never
   a hand edit.
4. **`test_app.py::test_startup_failure_propagates`** — it pins that **only** discovery publication
   may fail the launch, by monkeypatching `uuid.uuid4` to raise and asserting it escapes. Q6 is
   precisely about whether a cache-root `mkdir` may join that set. A cache created in the lifespan
   that **cannot** fail the launch leaves the asymmetry intact; one that can, changes a ruling and
   must say so.
5. **`test_deps.py::test_a_failing_image_client_close_does_not_strand_the_engine_dispose`** — if Q1
   puts anything new in `_shutdown`, this test's ordering claim is the one to re-derive. A cache
   needing teardown is a smell: the pacer needed none and neither should this.
6. **`test_spa.py`** — nothing here adds a route or a router, so it owes nothing. If it goes red,
   something unintended was registered.
7. **`test_images.py`'s and `test_routes_card_image.py`'s existing ~40 fetch tests** — every one of
   them now traverses the cache. `isolated_data_dir` keeps them cold and independent; a test whose
   recorded fetch count *changes* is either CM-2 working or a key collision, and the difference is
   read, not assumed (§ What the real data says).

### Source tree — what exists, what this story touches

```
src/companion/app/
  images.py               EDIT — the cache (the spine's `app/images.py # proxy: pacer, disk
                                 cache, negative cache` line, :452); the path, key and
                                 extension rules; the atomic write; the read; three
                                 forward-dated paragraphs rewritten
  main.py                 EDIT — the lifespan creates the cache root (Q6); the docstring says
                                 why here, and why its failure posture differs from discovery's
  routes/cards.py         EDIT — the one call site becomes cache-then-fetch (Q1); the "same
                                 cache story" docstring claim implemented or corrected
scripts/dump_openapi.py   EDIT (docstring only) — c3-7 shipped and needed nothing; c3-8 next
tests/unit/companion/
  conftest.py                 EDIT — the consolidated stall-able CDN fake (AC 18)
  test_images.py              EDIT — the cache's unit tests; `TestTheLoopIsNeverBlocked`
                                 extended per Q2; the ~17 `fetch_image` call sites verified
  test_routes_card_image.py   EDIT — `_BANNED_IDENTIFIERS` (eight out, two stay), all three
                                 pairings, the one-write-site + containment guards, CM-2,
                                 offline, cold-vs-warm, the two failure postures
  test_routes_decks.py        VERIFY — AC 10's zero-write assertion may live here instead
  test_app.py                 VERIFY — the startup asymmetry, only under Q6's failing option
  test_deps.py                VERIFY — shutdown ordering, only if Q1 adds a teardown
ui/src/api/
  openapi.json, types.d.ts    REGENERATED — expected byte-identical; run it, do not assume it
ui/README.md              EDIT — only if Q2/Q4 produce a number c4-4 needs
plugin/**                 REBUILT — required by CI's drift gate
_bmad-output/implementation-artifacts/deferred-work.md   EDIT
```

**Not touched, deliberately:** `src/companion/app/errors.py` and `src/companion/contracts.py` (no
new token — AC 9), `src/companion/app/deps.py` (the session/pool interaction is unchanged by a
cache; if anything a warm hit *shortens* the hold), `src/companion/discovery.py` (**read it, copy
its reasoning, do not import from it** — a leaf module and an app module sharing a private write
helper is a boundary question this story has no reason to open), `src/companion/client.py`,
`src/companion/app/{security,spa,state,singleton}.py`, `src/paths.py` (`data_dir()` is used as it
stands; **do not add an `image_cache_dir()` helper there** unless Q1 rules it — `src/paths` is
shared with the MCP server and the search layer, and a companion-only path in it is a widened
surface for one consumer), `src/data/**`, `src/logic/**`, `src/mcp_server/**`, `src/viewer/**`,
and every file under `ui/src` (**c4-4** owns the tile).

### Previous story intelligence (c3-1 … c3-6, and their nine review passes)

- **Seventeen of seventeen stories have answered their open questions "as proposed"** (one
  partial). The questions below are written to be answerable the same way, but **Q1, Q2, Q5 and Q6
  are genuine forks** — they change what ships.
- **The round-1 5/5 Greptile cause is confirmed five times running**: the same-day three-layer
  `bmad-code-review` before raising the PR. Task 8.
- **c3-6's review theme was *a guard keyed on the syntax its own firing test used*** — the
  blocking-wait scan missed `from time import sleep`, the one spelling the *retired* ban had
  caught, and all three review layers found it. **This story's guards are exposed to the identical
  shape**: the one-write-site scan (AC 5) and the extended blocking-I/O scan (Q2) will both be
  written by someone who knows exactly how they will be spelled. **Plant an evasion against each
  before trusting it**, and plant it in a spelling you would not have chosen.
- **c3-6's probe (f) is the shape to fear here.** Completion-based spacing passed all 75 unit tests
  because a mocked fetch is instantaneous. The analogue: **a cache write that happens after the
  response is returned**, or **a cache read that runs inside the pacer slot** — both cache
  correctly, both pass every functional assertion, and both are wrong in production only. Probe (f)
  of AC 23 exists for the second; the first is why AC 6 measures the clock rather than the bytes.
- **c3-5's review theme was *the fetch trusted a response `client.get()` had already swallowed*** —
  a check that ran after the thing it was meant to prevent. Applied here: a "the file is complete"
  check performed on the *target* after the replace proves nothing about what a concurrent reader
  saw; atomicity is a property of the write sequence, not of a post-hoc assertion.
- **c3-4's review theme was *prose outrunning code***. Applied here twice: the module docstring must
  not claim atomicity the write sequence does not deliver (probe (c) exists for that), and it must
  not claim durability that Q3 declines to buy (see Q3 — *atomic* and *fsynced* are different
  words).
- **c3-3's headline finding**: a guard caught **0 of 12** planted evasions. AC 5 and Q2's extended
  scan are the guard-shaped things here.
- **c3-2's finding**: a true count read as a false rule, published to the wire. Applied here: *"the
  corpus contains only `.jpg` and `.png`"* is true of **this** corpus, measured today. It justifies
  an explicit two-entry extension→media-type map; it does **not** justify a code path that raises
  or corrupts on a third extension, and it must not be published as a wire promise.
- **c3-1's R1 finding**: `TestNotShadowedBySpa` passed with the router *deleted*. Applied here: a
  cache test that asserts only "the second response was 200" passes with the cache deleted.
  **Assert the recorded fetch count and the file on disk**, neither of which a missing cache can
  produce.
- **c3-1's R3 finding**: identical fixtures prove nothing. Applied here: two cache keys must be
  distinguishable on disk *and* in the body — `Recorder` already keys its body on the URL, which is
  what makes a mis-keyed cache visible rather than merely silent.
- **`plugin/**` is not "not touched"** (c3-1's finding 1). A stale mirror is a guaranteed red build.
- **Every story in this epic has hit a structural pin it did not name** (c3-2 Debug Log 3, c3-3
  finding 2, c3-6 Debug Log 2 — three running). Budget for one. The likeliest candidates here are
  `test_routes_format_check.py::TestNoRuleInTheShell`'s literal families (currently `{60, 15}`
  after c3-6 narrowed it — `2` for the shard width is not in it, checked) and the
  `_BANNED_IDENTIFIERS` prose plant.
- **One c3-6 decision is still open and Brad may overturn it**: `4` was declared out of c3-3's
  deck-limit family so that `images.FETCH_CONCURRENCY = 4` could keep its name (c3-6 Debug Log 2,
  flagged in that story's Completion Notes as *"a decision beyond the story"*). If Brad overturns
  it, the fix is a different concurrency cap, not a rename — and that lands in `images.py`, this
  story's file. **Check whether it has been ruled before starting**, so the two edits do not
  collide in one commit.

### Git intelligence

- **`2927336`** — PR #34 merged c3-6 into `feat/companion-c3` on 2026-08-01 (`ae4be12` records,
  `2bd7642` the pacer). `4765bc6` — PR #33, c3-5. `3bfe95f` — PR #32, c3-4. `737ce76` — PR #31,
  c3-3. `2a787ac` — PR #30, c3-2. `a52d6f8` — integration PR #28 on master.
- The C2/C3 rhythm holds: **story branch off the umbrella, story PR into the umbrella with a
  Greptile pass per story**, one integration PR to master after the retro with **no** Greptile pass
  (OSS free-tier budget, standing rule). Merge ≠ release — no tag, no CHANGELOG until c8-4.
- Commit style: Conventional Commits, `feat(companion): …`. The shape to copy: one small `feat`
  commit, then a separate review-patch commit, then the records commit.

### Gotchas specific to this story

- **`mkdir`, `open`, `replace`, `data_dir` and four more are banned in `images.py` today.** The
  suite goes red on your first line of production code, and that red is the guard working. Fix it
  in Task 3 deliberately, not reflexively — and **not by deleting the frozenset**.
- **`data_dir()` mkdirs as a side effect of being called.** A module-level constant, a default
  argument, or a call inside `build_app()` all break AD-10 and `test_app.py`'s inertness claims.
  `discovery.discovery_path()`'s docstring is the precedent, verbatim.
- **`os.replace` on Windows fails if another handle holds the *target* open.** Two concurrent
  requests for the same key (no coalescing, unless Q5 takes it) will both write; the loser gets a
  `PermissionError`. AC 9 makes that a log line, not a 500 — but only if you catch `OSError` and
  not just the happy path.
- **A cache root that is a *file*, or a `<id>` directory that already exists as a file**, are the
  two shapes `mkdir(parents=True, exist_ok=True)` still raises on (`FileExistsError`/`NotADirectory
  Error`). Both are AC 9 cases.
- **`mimetypes.guess_type` is not safe on this platform, and `spa.py` says why**: it consults the
  **Windows registry**, which any installed application can rewrite, and `mimetypes.init()`
  discards prior `add_type` calls. Q4's extension→media-type answer must be an explicit map in this
  module's own source, not a library lookup.
- **`art_crop` and `border_crop` contain underscores**, so `<size>_<face>` yields `art_crop_0.jpg`.
  The filename is only ever **constructed**, never parsed back — keep it that way, and say so, or
  the first person to write a parser gets an ambiguous split.
- **`asyncio.to_thread` is stdlib; `anyio` is not a declared dependency** (`pyproject.toml`'s
  `dependencies` list has twelve entries and `anyio` is not one — it arrives through Starlette and
  httpx). Q2's answer should not add a dependency, and `threading` / `concurrent.futures` are
  *banned by name* in `images.py` by c3-6's scan — reaching for a `ThreadPoolExecutor` directly
  turns that guard red, correctly.
- **`os.fsync` is not free and its cost lands in AC 24's runtime number.** Task 0 measures it
  before Q3 is acted on. *Atomic* means a reader never sees a partial file; *durable* means the
  file survives a power cut. AD-11 and NFR-09 ask for the first.
- **Do not let a warm cache silently make the suite faster in a way that hides a regression.** The
  runtime is a claim (AC 24) in both directions: a large *drop* would mean tests are hitting a
  shared cache across tests, which `isolated_data_dir` is supposed to make impossible.
- **`mypy --strict` and `--platform win32`** are both gates. `--platform win32` matters more than
  usual here: `os.replace`, `os.chmod` and `tempfile.mkstemp` have platform-conditional stubs, and
  `discovery.py` already carries the POSIX-only `chmod` note.
- **No new dependency.** `os`, `tempfile`, `pathlib`, `contextlib` and `asyncio` are stdlib.
- **Google-style docstrings on every public function; module docstring mandatory; ruff `N`/`UP`
  apply.** `format` as a field name is a project convention — irrelevant here, noted because `N` is
  on.

### Testing standards

- `pytest` config is in `pyproject.toml`; `asyncio_mode = "auto"` — write `async def test_…` with
  **no** `@pytest.mark.asyncio`.
- Layout mirrors `src/`: `tests/unit/companion/` for anything driven in-process over
  `httpx.ASGITransport`. This story adds **no** `integration`-marked test — AD-10 rules that
  exactly one such test exists in the whole feature and it belongs to **c5-8**.
- Reuse `lifespan_client`, `isolated_data_dir`, `image_shapes`, `_point_at`, `_seed`,
  `_ready_database`, `Recorder` and `cdn`. Consolidate the two stall-able CDN fakes into
  `conftest.py` rather than adding a third (AC 18).
- **No unit test may touch the network, write outside `tmp_path`, or sleep for real time.**
- `tests.*` is exempt from `mypy --strict` but not from ruff or the naming rules.
- Paste real gate output. **`npx tsc -b --force` is a separate claim from `npm test`** — c3-2
  measured `tsc -b` caching a clean result over a real failure.

### Architecture rules this story implements

- **AD-11** — the content-addressed, sharded, atomically written, **unbounded** disk cache; the
  accepted staleness; the "never a substitute image" rule extended to a corrupt cache entry.
- **NFR-09** — image cache stewardship: the documented location and the atomic write. The **README
  and uninstall notes half is c8-2's** (epic `:3185-3212`) and this story must not absorb it —
  what it owes c8-2 is a measured footprint number, not documentation.
- **NFR-06** — offline after warm-up: AC 7 is the first test in this feature that proves it for
  images. (The self-hosted font half shipped at c2-5.)
- **CM-2** — *an image fetched once is not fetched again within the cache lifetime*. This story's
  headline, and the only epic AC another story has been waiting on.
- **AD-10** — `build_app()` has zero side effects; the lifespan owns anything with an effect,
  including this cache's root directory.
- **AD-2 / NFR-02** — read-only with respect to the **database**. Filesystem writes are outside
  that guard's scope, which AC 15 requires the record to state rather than imply.
- **AD-12 / NFR-03** — one generator from the backend's own `app.openapi()`; this story's claim is
  that it produces **no diff**, settled by running it.
- **AD-16** — unchanged: no new token, and every cache failure is invisible to the wire.

### Latest technical information (external — banked by c3-5 on 2026-08-01, do not re-research)

- **Scryfall asks consumers to cache what they download, for at least 24 hours.** That request was
  banked for **this story** by name. It is the *only* one of the four banked items that is c3-7's,
  and it is worth stating plainly in the module docstring: an unbounded, never-evicting local cache
  satisfies a 24-hour minimum by a wide margin, and the reason there is no TTL is that AD-11 keys
  on id + size + face and **accepts** the staleness a refresh introduces — not that the guidance
  was overlooked.
- Sustained traffic under 10 requests/second with 50–100 ms between calls; excess earns `429` and a
  ~30-second lockout — **but the `*.scryfall.io` file origins this route fetches from are
  explicitly exempt.** Already written into `FETCH_SPACING_SECONDS`' docstring and gated by a test.
  Nothing to do; stated so it is not re-derived.
- A descriptive `User-Agent` is required — shipped by c3-5's `_user_agent()`.

Sources: [Scryfall API rate limits](https://scryfall.com/docs/api/rate-limits) ·
[Scryfall API docs](https://scryfall.com/docs/api)

### References

- [epics-companion-app.md § Story 3.7](../planning-artifacts/epics-companion-app.md) — the ACs this
  story expands (1741-1774); **3.8's failure signalling** (1776-1803), whose scope this one must
  not absorb; **Story 8.2** (3185-3212), which owns the README, the removal command and the
  uninstall notes; **Story 10.3** (3560-3599), which owns real-bytes profiling; NFR-06 (162-163),
  NFR-08 (170-172), NFR-09 (174-176)
- [ARCHITECTURE-SPINE.md](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md) —
  **AD-11 (242-270)**, AD-2, AD-10, AD-12, AD-16, and the Structural Seed's `app/images.py` line (452)
- [c3-6 story record](c3-6-paced-concurrency-capped-cdn-fetching-at-one-global-choke-point.md) —
  the pacer, the injected clock, the eight review patches, and the *procedure* for taking down a
  family of a shared `_BANNED_IDENTIFIERS` set
- [c3-5 story record](c3-5-card-image-endpoint-with-face-resolution-and-a-defined-parameter-contract.md) —
  the route, the allow-list, the two image tokens, and the banked Scryfall research
- [deferred-work.md](deferred-work.md) — the **five c3-7-homed entries** (CM-2; in-flight
  coalescing; `<ext>` not derivable from the size key; the cache-buster and the id-based key; the
  two stall-able CDN fakes) plus the c3-8 entries that fence this story's scope
- [epic-c2-retro-2026-07-30.md](epic-c2-retro-2026-07-30.md) — the standing agreements (ban the
  family; probe your own guard) and action item 6 (same-day three-layer review)
- [project-context.md](../project-context.md) — layer boundaries, async rules, docstring style,
  ruff/mypy gates

---

## Open questions for Brad — answer before `dev-story`

**Q1 — What shape is the cache, and who owns the instance?** *(genuine fork)*

The pacer's answer was *"a class in `images.py`, one instance created in the lifespan, passed as a
required parameter"*, and it worked. But a cache differs from a pacer in one way that matters: it
**resolves a path**, and `data_dir()` mkdirs.

| Option | Verdict |
| --- | --- |
| **A `DiskCache` in `images.py`, one instance created in the lifespan beside `Pacer`, holding the resolved root; reached by the route through an `image_cache(app)` accessor** | **Proposed.** It mirrors the client and the pacer exactly — same module, same creation site, same accessor shape, same *"`None` means the lifespan did not run"* ruling — and it is the only option where the root is resolved **once, at startup**, which is what AD-11's *"the lifespan creates it — never `build_app()`"* actually asks for. It gives tests the substitution seam the `cdn` fixture already relies on, and per-app instances mean no cross-test bleed (`deps.Database`'s shipped ruling against module globals). It needs no teardown, so `_shutdown` and `test_deps.py` stay untouched — a prediction to **confirm by measurement**, as c3-6 did |
| Module-level functions in `images.py` (`cache_path()`, `read_cached()`, `write_cached()`) resolving `data_dir()` on every call | **The real alternative**, and it is simpler. Rejected because it makes the *lifespan's* creation of the directory decorative — every call would create it anyway — and because it puts a `data_dir()` call on the hot path of every image request, where `discovery.py` and `singleton.py` both call it once |
| A new module `src/companion/app/image_cache.py` | **Rejected by the spine**, which draws the disk cache inside `app/images.py`: *`images.py  # proxy: pacer, disk cache, negative cache  (AD-11)`*. c3-8 lands in the same file. Three mechanisms in one module is a real weight, but splitting it is a decision for whoever finds `images.py` unmanageable, with all three shipped — not for the story that adds the second |

*Sub-question, and it is small: does this story also give `GET /api/cards/{card_id}` the cache
headers `cards.py`'s docstring already claims the two routes share?* **Proposed: no — correct the
docstring and leave the ledger entry homed on c4-1.** A card row's cache story is `ETag`/
conditional requests over a database read, which shares nothing with a file on disk but the word.
Implementing it here would be a second mechanism smuggled in under a docstring's phrasing.

*Recommendation: as proposed, both parts.*

---

**Q2 — Is the file I/O offloaded to a thread, or done inline on the event loop?** *(genuine fork)*

AD-11: *"Pacing is `async` throughout — it **must never block the event loop**, or a queued image
burst would eat the 250 ms push budget"* (NFR-05). A `Path.read_bytes()` of 124 KB and a
`mkstemp`+write+`replace` of the same are both synchronous, and **no shipped guard can see them** —
`_BLOCKING_MODULES` covers `threading`, `concurrent.futures`, `multiprocessing`, `subprocess` and
`time.sleep`, none of which a file read is.

| Option | Verdict |
| --- | --- |
| **`asyncio.to_thread` for both the read and the write** | **Proposed.** Stdlib, no new dependency, and it makes AD-11's sentence literally true rather than true-in-practice. It is also what Starlette's own `FileResponse` does (via `anyio.to_thread`), so it is the platform's answer rather than this story's invention. Cost: a thread hop per image, which on a warm 99-tile paint is 99 hops — measurably cheaper than 99 fetches, and Task 0 measures it rather than asserting it |
| Inline, with a measured justification | **The real alternative**, and it is defensible on numbers: a 124 KB read from a local SSD is sub-millisecond, and the 250 ms push budget has room for a thousand of them. Rejected because the *write* is the other half — with `os.fsync` it is milliseconds, without it the OS can still block on a dirty-page flush — and because "measured fast on this machine" is exactly the claim NFR-05 gets tested against on someone else's. If Brad prefers this, the ruling needs the measurement **in the docstring**, in the manner of `Pacer`'s defence-vs-necessity paragraph |
| Thread the write only, inline the read | **Rejected as the worst of both**: it needs the same guard, states a subtler rule, and saves one thread hop on the path that is already the fast one |

**Either way, the guard has to be extended** (AC 5 / Task 3): `TestTheLoopIsNeverBlocked` must gain
a family that can *see* synchronous file I/O in `images.py` — proposed shape: every `open`,
`read_bytes`, `write_bytes`, `mkstemp`, `replace` and `fsync` call site must be lexically inside a
**non-`async`** helper, with the async path reaching it only through `asyncio.to_thread`. Probed
with an evasion (the call moved directly into an `async def`, and an aliased `from os import
replace as move`).

*Recommendation: as proposed — `asyncio.to_thread` for both, plus the extended guard.*

---

**Q3 — Does the cache write `fsync` before the rename?**

`discovery.write_discovery` does, and its docstring explains why the *directory* is not fsynced.
Copying it wholesale would be the easy move and it would be wrong.

Proposed: **no `fsync`.** The AC asks that *"a crash mid-write can never leave a truncated file that
a later read would serve"* — that is **atomicity**, delivered by temp + `os.replace`, and it holds
without `fsync` because the rename is what makes the file visible under its real name. `fsync` buys
**durability** — surviving a power cut — and a cache entry lost to a power cut costs one refetch.
The discovery file is different in exactly the way that matters: it is a rendezvous whose loss makes
a running app unreachable, and it is written once per process, not 99 times per deck.

The cost is measurable and Task 0 measures it: an `fsync` per entry on a cold 99-tile deck is 99
forced disk flushes, and on some Windows configurations that is tens of milliseconds each. **Say
this in the docstring in both directions** — *atomic, deliberately not durable, and here is the
difference* — because "atomically written" is routinely read as "fsynced", and c3-4's review theme
was prose outrunning code.

*Recommendation: as proposed. If Task 0 measures `fsync` at under ~1 ms on this machine, record the
number and keep the ruling anyway: the reason is the semantics, not the cost.*

---

**Q4 — What `Content-Type` does a warm hit serve?**

The cold path echoes **the upstream's own** header verbatim, parameters included — c3-5's shipped
ruling: *"what the upstream said about its own bytes is more accurate than anything derived from the
size key"*. A warm hit has only `<ext>`.

Proposed: **derive it from the extension through an explicit two-entry map in `images.py`**
(`.jpg → image/jpeg`, `.png → image/png`), justified by measurement — those are the only two
extensions across all 245,760 stored URLs — and **never** through `mimetypes.guess_type`, which
`spa.py`'s docstring documents as consulting the Windows registry and being reset by any
third-party `mimetypes.init()`.

The honest consequence, which AC 8 requires be asserted rather than discovered: **if an upstream
ever sends `image/jpeg; charset=binary`, the cold answer carries the parameter and the warm answer
does not.** That is a real divergence, it is bounded to parameters, no browser behaves differently
for it, and it is pinned by a test that states it. The alternative — storing the content type in a
sidecar file or in the filename — doubles the entries on disk and re-opens the atomicity question
for a pair of files, to preserve a parameter no measured response actually sends.

*Recommendation: as proposed, with the divergence named and tested rather than glossed.*

---

**Q5 — Does this story take in-flight coalescing?** *(genuine fork, inherited by name from c3-6)*

c3-6 declined it and homed it here, with a stated reason that this story now resolves: *"whether
that result is bytes, a disk path or a `Future` depends entirely on what c3-7 builds."* It builds
bytes on disk. So the question is genuinely open for the first time.

| Option | Verdict |
| --- | --- |
| **Decline again; re-home on c3-8** | **Proposed.** The measured cost today is still **zero extra fetches** on both 99-distinct-id decks — duplicate printings collapse in `deck_cards` before they reach the route — so this buys nothing observable. More importantly, **c3-8 needs the same structure for a different reason**: a negative cache has to answer *"is a fetch for this key already in flight or already known-failed?"*, and building the in-flight half here means c3-8 either inherits a map shaped for successes or replaces it. One mechanism, built once, by the story that can see both halves. c3-4's ruling applies unchanged. Cost, stated: two simultaneous requests for one key both fetch and both write, and on Windows the loser's `os.replace` may raise `PermissionError` — which AC 9 already makes a log line |
| Take it | **The real alternative**, and it is now cheap and well-defined: a `dict[key, asyncio.Future]` around the fetch, ~15 lines, and it removes the concurrent-replace race entirely rather than tolerating it. Rejected on ownership and on measured value, **not** on merit — and the trigger that flips the answer is unchanged: **c6-4**'s suggestion rows beside the deck grid are the first surface that renders the same card id twice on one screen |

*Recommendation: as proposed — decline, re-home on **c3-8** with the c6-4 trigger restated, and
record that the reason has changed (c3-6 declined it for not knowing the result's shape; c3-7
declines it for the shape being shared with c3-8's).*

---

**Q6 — What happens when the cache directory cannot be created?** *(genuine fork)*

AD-11's AC is unambiguous about *where*: *"the lifespan creates it — never `build_app()`"*. It says
nothing about *what if it fails* — and `test_app.py::test_startup_failure_propagates` pins that
**publishing the discovery file is the only startup step that may fail the launch** (AD-15,
Decide-once #3).

| Option | Verdict |
| --- | --- |
| **Create it in the lifespan; a failure is logged at WARNING and the cache is disabled for the process** | **Proposed.** The app is **fully functional** without a cache — every request simply fetches, exactly as it did at c3-6 — so failing the launch is disproportionate in a way the discovery file's failure is not. AD-15's own reasoning is the discriminator and it is worth quoting in the docstring: *"a half-launched rendezvous"* leaves every agent tool reporting `app_not_running` while the app visibly runs, with nothing on either surface explaining the contradiction; a missing cache leaves an app that works and is slower. **The startup asymmetry stays literally true** — discovery is still the only step that can fail the launch — and `test_app.py` needs no edit, which is a prediction to confirm |
| Create it in the lifespan and let `OSError` propagate | **The real alternative**, and it has a genuine argument: `data_dir()` itself already mkdirs, so a data directory this unwritable will fail `write_discovery` two lines later anyway, making the extra failure mode nearly unreachable. Rejected because *nearly* is the operative word — a **file** named `image_cache` in the data directory is a `FileExistsError` that discovery would sail past — and because taking it means editing the ruling `test_startup_failure_propagates` exists to protect, for a degradation that is not an outage |
| Create it lazily on first write | **Rejected**, and by the AC's own text: *"Given the cache directory does not exist, when the backend starts, then the lifespan creates it."* The per-card shard directories are a different matter — those are necessarily created at write time, and that is not the directory the AC names |

*Recommendation: as proposed. Record which of the two `mkdir`s is the AC's (the root, at startup)
and which is incidental (`<id[0:2]>/<id>`, at write time), because a reader who conflates them will
think the AC is either unsatisfied or over-satisfied.*

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via Claude Code.

### Open questions — Brad's answers

**All six as proposed** (Brad, 2026-08-01) — the 18th story running. Plus one standing decision ruled:

| Q | Ruling |
| --- | --- |
| **Q1** | A `DiskCache` class in `images.py`, one instance created in the lifespan beside `Pacer`, holding the resolved root, reached through an `image_cache(app)` accessor. Sub-question: **no** — `GET /api/cards/{card_id}` gets no cache headers here; the `cards.py` docstring is **corrected** and the ledger entry stays homed on c4-1 |
| **Q2** | `asyncio.to_thread` for **both** the read and the write, plus the blocking-I/O guard extended so the file-I/O shape is visible to it |
| **Q3** | **No `fsync`.** Atomic, deliberately not durable — stated in the docstring in both directions |
| **Q4** | Warm-hit `Content-Type` from an explicit two-entry extension→media-type map in `images.py`; never `mimetypes.guess_type`; the parameter divergence named and tested |
| **Q5** | **Decline** in-flight coalescing again; re-home on **c3-8** with the c6-4 trigger restated, and record that the *reason* has changed |
| **Q6** | The lifespan creates the cache root; a failure logs at WARNING and **disables the cache for the process**. The startup asymmetry stays literally true and `test_app.py` needs no edit |
| **c3-6's open decision** | **Leave as c3-6 shipped it** — `4` stays out of c3-3's deck-limit family and `images.FETCH_CONCURRENCY` keeps its name. This story touches neither |

### Baseline (Task 0, measured — not assumed)

Branch `feat/companion-c3-7-image-disk-cache` cut from **`2927336`** (`origin/feat/companion-c3`
tip, PR #34, c3-6 — confirmed by `git rev-parse`).

**Gates at the baseline, all green:**

| Gate | Result |
| --- | --- |
| `uv run pytest` | **2326 passed, 1 skipped — 126.10 s** |
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 305 files already formatted |
| `uv run mypy src/` | Success: no issues found in 89 source files |
| `uv run mypy src/ --platform win32` | Success: no issues found in 89 source files |
| `ui/` `npm run lint` | clean (eslint + stylelint) |
| `ui/` `npm run format:check` | All matched files use Prettier code style! |
| `ui/` `npx tsc -b --force` | exit 0, no output |
| `ui/` `npm test` | **568 passed, 31 files** — 4.38 s |
| `ui/` `npm run build` | built in 136 ms |

**One difference from the story's inherited number, recorded rather than smoothed over:** the story
states **2325 passed**; this machine measures **2326 passed** at the same commit. The story's count
was taken during c3-6's own run; one test has been added between that measurement and the merge.
The number to beat is therefore **2326 / 126.10 s**, not the story's.

**SPA bundle SHA-256 (first 16), `src/companion/app/static/` and the `plugin/` mirror
(`plugin/server/src/companion/app/static/`) — byte-identical to each other and to the story's five:**

| File | SHA-256 (16) |
| --- | --- |
| `index-DE70muY2.js` | `FAEEEA472ADD5078` |
| `index-DmxBiI94.css` | `0A3C142D84B5A98D` |
| `space-grotesk-latin-wght-normal-BhU9QXUp.woff2` | `0640890476FC1198` |
| `favicon.svg` | `9BE16EA2FE3670DE` |
| `index.html` | `8E65C0615CF66044` |

**Committed wire artifact:** `ui/src/api/openapi.json` — **7 paths**, **12 components**, exactly the
sets the story names.

**The corpus numbers, re-measured myself against the live 38,261-card database, read-only. Every
one of the story's figures reproduced exactly:**

| Claim | Story | Measured |
| --- | --- | --- |
| Total stored image URLs | 245,760 | **245,760** ✓ |
| `cards.scryfall.io` / `errors.scryfall.com` | 245,742 / 18 | **245,742 / 18** ✓ |
| Top-level `small`/`normal`/`large`/`art_crop`/`border_crop` → `.jpg` | 35,404 each | **35,404 each, 0 `.png`** ✓ |
| Top-level `png` → `.jpg` | **3** | **3** (and 35,401 `.png`) ✓ |
| Per-face, each size | 5,556 | **5,556 each**; `png` all `.png` ✓ |
| Distinct extensions across the whole corpus | `.jpg`, `.png` | **exactly those two** ✓ |
| The three `png`→`.jpg` cards | Sparkspitter, Ondu Champion, Gorehorn Minotaurs | **all three, by name** ✓ |
| Cards / shards used / per-shard | 38,261 / 256 / 107–218 | **38,261 / 256 of 256 / 107–218, mean 149.5** ✓ |
| Saved decks / distinct card ids | 40 / 1,061 | **40 / 1,061** ✓ |

**The write-cost measurement Q2 and Q3 both rest on** — `mkstemp` + write + `os.replace` of a
124 KB payload into the real `%LOCALAPPDATA%` data directory, 200 iterations each, probe directory
removed afterwards:

| Operation | mean | median | p95 | max | × 99 tiles |
| --- | --- | --- | --- | --- | --- |
| atomic write, **no** `fsync` | **0.460 ms** | 0.430 | 0.651 | 0.873 | **0.045 s** |
| atomic write, **with** `fsync` | **2.909 ms** | 2.818 | 3.753 | 5.408 | **0.288 s** |
| `read_bytes()` of 124 KB | **4.972 ms** | 4.893 | 5.941 | — | **0.492 s** |
| `asyncio.to_thread` hop (no-op) | **0.131 ms** | 0.029 | 0.116 | — | **0.013 s** |

**Two findings here changed how much weight the rulings carry, and both are the opposite of what
was assumed:**

1. **The read is the expensive half, not the write** — 4.97 ms against 0.46 ms, roughly 11×. Q2's
   "inline, with a measured justification" alternative was argued on the premise that *"a 124 KB
   read from a local SSD is sub-millisecond"*. On this machine it is **five milliseconds** (a
   Defender-scanned read on a real `%LOCALAPPDATA%` path), and a warm 99-tile paint would block the
   event loop for **~0.49 s** — twice NFR-05's whole 250 ms push budget, from the path the cache
   was supposed to make fast. Q2 as proposed is not a formality; it is the ruling that keeps AD-11
   true. The thread hop it costs is **0.131 ms**, ~38× cheaper than the read it moves.
2. **`fsync` costs 6.3× the whole rest of the write** (2.909 ms vs 0.460 ms). Q3's recommendation
   said to keep the ruling even if `fsync` measured under ~1 ms *because the reason is the
   semantics, not the cost*. It does not measure under 1 ms — so the ruling is carried by both
   arguments at once, and the docstring says the semantics one first.

### Debug Log References

**1 — The structural pin this story hit, and it is the fourth story running.** `_BLOCKING_CALLS`
(`test_images.py`, c3-6) banned **`to_thread`** by name in `images.py`, under the rule *an*
`async def` *must not reach a thread pool*. That is precisely the mechanism Q2 rules as the
**sanctioned** one — so the first green run of the cache turned it red, correctly. The ban came
down and `run_in_executor` stayed, on a distinction that is not cosmetic: `run_in_executor` takes a
caller-supplied loop and executor and can silently reintroduce an unbounded pool, where
`to_thread` uses the running loop's own bounded default. The replacement is stronger, as c3-6's
procedure requires: `TestFileIoNeverRunsOnTheLoop` gates that every file-I/O call site is lexically
inside a **non-`async`** helper — *"the thread is where the blocking call is"*, which the ban could
not express at all. (The story predicted a structural pin and named two candidates —
`TestNoRuleInTheShell`'s literal families and the prose plant. It was neither.)

**2 — `_BANNED_IDENTIFIERS` fired on the bare token `cache`, and the fix was not a rename.**
c3-8's family was `{"lru_cache", "cache"}` as bare tokens, and a bare `cache` cannot tell
`functools.cache` the decorator from `cache` the local variable — which `image_cache()`'s accessor
has. After this story `images.py` legitimately holds cache vocabulary throughout, so a bare-token
ban is a fence around the thing that was built. Renaming the local to appease it is the
obfuscation c3-6's own docstring says to treat as a violation. So the two survivors were **re-keyed
onto `functools`, resolved through imports** — narrower where it was wrong and **wider** where it
matters: `from functools import cache as memo` and `import functools as ft; @ft.cache` are now
caught and neither was before. c3-8's fence is stronger than it was, not weaker.

**3 — `git checkout` destroyed uncommitted work mid-probe, and it is recorded rather than quietly
fixed.** Reverting probe (a) with `git checkout src/companion/app/routes/cards.py` restored the
file from **HEAD**, not from my working state — silently discarding every c3-7 edit to that file
(four edits, ~60 lines). Caught immediately by the post-revert SHA-256 not matching the pre-probe
hash, which is exactly why that check exists; the edits were reapplied from context and the file
re-verified byte-identical (`ceb295c278b61e1c`) before probing resumed. **Every subsequent probe
reverted from a real file backup, never from git.** No committed file was affected. c3-3's Debug
Log 4 is the same shape (a truncated file mid-probe) and the same lesson: the probe procedure needs
its own backup, because the work under probe is by definition uncommitted.

**4 — Patching `images.tempfile.mkstemp` reaches `discovery.py` too**, because they are the same
module object — so a write-failure test that patched before startup broke `write_discovery`, the
one startup step allowed to fail the launch, and the app never started. The patch moved inside the
lifespan. Recorded in the test's own docstring because the same trap waits for the next filesystem
failure case added there.

**5 — The story's claim about `TestTheBurstDoesNotOutlastTheConnectionPool` is false, and the test
was wrong before this story touched it.** The story states it *"drives 99 distinct urls/ids —
unaffected"*. It drove `SINGLE_FACE_ID` **ninety-nine times**, and its own docstring called that
*"the measured distinct-id count of a real 100-card deck"*. Invisible while every request fetched;
a red the moment a cache existed (`len(recorded) == 3`, plus a live `PermissionError` from two
concurrent writers racing `os.replace` — the Windows case AC 9 exists for). The story demanded
this be *read* rather than assumed, and the reading is: **CM-2 working, not a key collision** — the
three recorded URLs are identical and all 99 responses were 200. Repaired to seed 99 distinct ids,
which is what the docstring always claimed, so the pool arithmetic it exists to protect is once
again measured over 99 real traversals.

### Probe outputs

Six probes, each verified **on disk** before the verdict and each reverted from a file backup with
the SHA-256 re-checked afterwards. Pre-probe hashes: `images.py` `0217d690ac17f5c9`,
`cards.py` `ceb295c278b61e1c` — both matched exactly after every revert.

| # | Mutation | Result | What it says |
| --- | --- | --- | --- |
| **(a)** | the cache **read** removed — every request refetches | **5 failed** | CM-2, the distinct-key pairing, the clock test, the offline test and the `Content-Type` divergence. Not caught by the write/disk assertions, correctly — a removed read does not stop a write |
| **(b)** | the cache **write** removed — nothing is ever stored | **8 failed** | incl. `test_but_asking_for_a_tile_does_write_exactly_one` (the no-pre-write pairing) and `…served_from_a_file_that_actually_exists`. **Also the runtime control**: companion suite **43.38 s** with the write gone vs **43.02 s** with it — the write costs nothing detectable |
| **(c)** | temp+replace collapsed into `open(target, "wb")` | **9 failed** | **and every functional and CM-2 test still passed**, exactly as the story predicted. Caught only by the atomicity tests, the **one-write-site scan** and the not-vacuous gate — i.e. by the three things that replaced the removed ban. This is the probe that justifies AC 5's positive gate existing at all |
| **(d)** | `<ext>` from the size key instead of the URL | **2 failed → 4 after repair** | **This probe found a real gap in my own coverage.** Two unit tests caught it and **nothing at the route level** — so the assertion that mattered most, *what the client is told the bytes are*, was not being made. Added the disk-level pairing and a route test proving a `png`-size Sparkspitter request serves `image/jpeg` warm; the probe then fired **4**, including the mislabel |
| **(e)** | the shard dropped — everything flat under `image_cache/` | **10 failed** | path construction, the write site, the temp-file location, and four route-level entry assertions |
| **(f)** | the cache checked **inside** `pacer.slot()` | **1 failed** | **910 others passed.** The story's headline fear, confirmed: it caches perfectly and paces a warm deck anyway. Caught only by the injected-clock test — `197` spacing intervals where 98 are correct — which is the whole reason AC 6 measures the clock and not the bytes |

### Completion Notes List

- **All six open questions answered "as proposed"** — the 18th story running. Brad also ruled c3-6's
  standing open decision: `4` stays out of c3-3's deck-limit family, `FETCH_CONCURRENCY` keeps its
  name, and this story touched neither.
- **CM-2 is satisfied.** The only one of this epic's six acceptance criteria that another story had
  been waiting on. Asserted on `Recorder.requested` — one recorded URL for two requests — and on a
  **file that exists at AD-11's path**, because c3-1's R1 finding is that a second-`200` assertion
  passes with the mechanism deleted.
- **Two guards came down, each replaced by something stronger, following c3-6's written procedure.**
  Eight names out of `_BANNED_IDENTIFIERS` and `to_thread` out of `_BLOCKING_CALLS`; all three
  `_BANNED_IDENTIFIERS` pairings reworked rather than deleted — including the firing test, which
  planted `NamedTemporaryFile` and would otherwise have degraded to `set() == set()`, *a test that
  passes because it now proves nothing*. Two new positive gates: **one rename-into-place site per
  module, two modules, both named**, and **no file I/O on the event loop**.
- **AC 5's own text is not achievable and the gate says so.** It asks for *"a single
  `os.replace`/rename-into-place site"* in `src/companion`; `discovery.write_discovery` has had one
  since c1-7. The gate asserts **exactly two modules, once each, both named** — strictly stronger
  than a count, since a second site *inside* either named module also fires it.
- **Q2 is load-bearing, not a formality, and the measurement inverted the assumption behind its
  alternative.** The rejected option was argued on *"a 124 KB read from a local SSD is
  sub-millisecond"*. Measured here: the **read is 4.97 ms** — 11× the 0.46 ms write — so 99 warm
  tiles inline would block the loop for ~0.49 s, **twice NFR-05's entire 250 ms push budget**, from
  the path the cache exists to make fast. The `to_thread` hop it costs is 0.13 ms.
- **Q3's ruling is carried by both of its arguments.** `fsync` measured **2.909 ms** against the
  whole write's **0.460 ms** — it does *not* come in under the ~1 ms the recommendation hedged
  against. *Atomic* and *durable* are stated in the docstring in both directions, because
  "atomically written" is routinely read as "fsynced".
- **The wire is untouched, confirmed by running the generator.** `npm run gen:api` produced **no
  diff at all** — neither generated file appears in `git status --porcelain`; 7 paths, 12
  components. That makes this the **second measured instance** of a behaviour-only story, which is
  enough to state the rule rather than the observation, and `dump_openapi.py` now does, naming
  **c3-8** next.
- **Every corpus number in the story reproduced exactly** against the live 38,261-card database —
  245,760 URLs, `png`→`.jpg` exactly 3 times on the three named cards, only `.jpg`/`.png`, 256/256
  shards at 107–218, 40 decks / 1,061 distinct ids. One number differed: the story's inherited
  suite count of 2325 measured **2326** here, recorded rather than smoothed over.
- **The three-cards-one-URL prediction went the predicted way.** `test_the_measured_errors_
  scryfall_com_cards_are_served_not_refused` passed **unchanged** — three fetches for three ids
  sharing one URL — which is what makes "the key is not the URL" a measurement rather than an
  intention. A companion assertion now states the cache half directly: three entries on disk.
- **AC 24's runtime claim cannot be made honestly on this machine, and saying so is the finding.**
  Three consecutive full-suite runs of identical code: **118.40 / 119.12 / 167.56 s** — a 49 s
  spread against a single 126.10 s baseline sample. An intermediate 143.36 s reading was initially
  attributed to the cache's disk I/O; **that attribution was wrong and is withdrawn.** The
  meaningful measurement is the targeted one, and probe (b) supplies it: 43.38 s without the cache
  write vs 43.02 s with it. Ledgered as a measurement-practice note for later stories.
- **`test_import_boundary.py` passes unchanged with no exclusions added** (50 passed, `git diff`
  empty) — **and its green does not mean what its name suggests for this story.** That guard is
  about the *database*: it bans repository writes, session mutators, DML and schema creation, and
  it *explicitly permits* file I/O (its own clean case is `file-flush-in-atomic-write`). So the one
  test whose name promises the companion never writes stayed green while this story taught it to
  write ~12 MB per deck. Said here, in `DiskCache`'s docstring, and in AC 15 — a real boundary was
  crossed and the guard that sounds like it covers it does not.
- **Nine deferred entries added, six c3-7-homed entries closed or re-homed by name**, including the
  conditionally-homed `read_card` cache-header entry (this story landed first, corrected the
  docstring, left the headers on c4-1) and the two hand-synchronised CDN fakes, now one
  `StallableUpstream` in `conftest.py` — which is where the consolidation turned up that the two
  fakes had **already drifted** (one had a clock and no `completed`, the other the reverse).

### File List

| File | Change |
| --- | --- |
| `src/companion/app/images.py` | **EDIT** — `DiskCache`, `cache_root`, `cache_extension`, `build_image_cache`, `image_cache`, `_cache_path`, `_read_cached`, `_write_atomically`, `CACHE_DIRECTORY_NAME`, `CACHE_MEDIA_TYPES`; three forward-dated paragraphs rewritten |
| `src/companion/app/main.py` | **EDIT** — the lifespan builds the cache (Q6); docstring states why its failure posture differs from discovery's |
| `src/companion/app/routes/cards.py` | **EDIT** — cache-then-fetch orchestration, `_image_response`, the "same cache story" claim corrected |
| `scripts/dump_openapi.py` | **EDIT** (docstring only) — c3-7 shipped and needed nothing; the rule stated; c3-8 named next |
| `tests/unit/companion/conftest.py` | **EDIT** — `FakeClock` and `StallableUpstream` consolidated here (AC 18) |
| `tests/unit/companion/test_images.py` | **EDIT** — the cache's unit tests; `TestExactlyOneImageWriteSite`; `TestFileIoNeverRunsOnTheLoop`; `TestNoDataPathIsResolvedAtImportTime`; `_BLOCKING_CALLS` re-keyed; local fakes removed |
| `tests/unit/companion/test_routes_card_image.py` | **EDIT** — `_BANNED_IDENTIFIERS` re-keyed onto `functools`, all three pairings reworked plus a fourth; CM-2, the injected-clock warm burst, offline, cold-vs-warm, both failure postures, the no-pre-write pairing; the burst test's fixture repaired; `StallableCdn` removed |
| `plugin/server/src/companion/app/{images,main,routes/cards}.py` | **REBUILT** — CI drift gate |
| `_bmad-output/implementation-artifacts/deferred-work.md` | **EDIT** — six entries closed/re-homed, nine added |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | **EDIT** — status |
| `_bmad-output/implementation-artifacts/c3-7-sharded-atomically-written-disk-cache.md` | **EDIT** — this record |

**Not touched, as planned:** `errors.py`, `contracts.py` (no new token), `deps.py`, `discovery.py`
(read, reasoning inherited, nothing imported), `src/paths.py` (no `image_cache_dir()` helper added),
`test_import_boundary.py`, `test_app.py`, `test_deps.py`, `test_spa.py`, all of `ui/src`, and
`ui/src/api/{openapi.json,types.d.ts}` (regenerated, no diff).

### Gates (AC 24 — every one re-run from the same tree, output pasted)

| Gate | Baseline | After |
| --- | --- | --- |
| `uv run pytest` | 2326 passed, 1 skipped — 126.10 s | **2386 passed, 1 skipped** — 118.40 / 119.12 / 167.56 s over three runs |
| `uv run ruff check .` | All checks passed! | **All checks passed!** |
| `uv run ruff format --check .` | 305 files already formatted | **305 files already formatted** |
| `uv run mypy src/` | no issues, 89 files | **no issues, 89 files** |
| `uv run mypy src/ --platform win32` | no issues, 89 files | **no issues, 89 files** |
| `uv run pytest …/test_import_boundary.py` | — | **50 passed**, file unchanged, no exclusions added |
| `uv run pytest …/test_openapi_contract.py` | — | **17 passed** |
| `ui/` `npm run lint` | clean | **clean** |
| `ui/` `npm run format:check` | Prettier clean | **Prettier clean** |
| `ui/` `npx tsc -b --force` | exit 0 | **exit 0** |
| `ui/` `npm test` | 568 passed, 31 files | **568 passed, 31 files** (unchanged by design) |
| `ui/` `npm run build` | built | **built**, no committed bundle file changed |
| `npm run gen:api` → `git status --porcelain` | — | **no diff** — 7 paths, 12 components |
| `npm run gen:types` → `git status --porcelain` | — | **no diff** |
| SPA bundle, `src/` and `plugin/` mirror | five hashes | **all ten byte-identical** to Task 0 |

**On the runtime row:** three consecutive runs of identical code spread **49 seconds**, so no
whole-suite before→after claim is supportable on this machine from single samples — see the
withdrawn attribution in the Completion Notes and the ledgered measurement-practice entry. The
targeted control is probe (b): the companion suite ran **43.38 s** with the cache write removed
against **43.02 s** with it, so the write costs nothing detectable — which is exactly the check
AC 24 wanted, since an added `os.fsync` is what would have shown up there.

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-01 | Story created — context engine analysis over the epic, AD-11/NFR-06/NFR-09, the shipped `images.py`/`cards.py`/`main.py`/`deps.py`/`discovery.py`, c3-6's record and its eight review patches, the two guards c3-5 and c3-6 left standing against this story, the live 38,261-card database (245,760 URLs re-measured for the extension and shard tables), and the installed toolchain |
| 2026-08-01 | **Implemented → `review`.** All six open questions as proposed (18th story running); c3-6's standing `FETCH_CONCURRENCY` decision left as shipped. `images.DiskCache` ships — AD-11's sharded path, the URL/`Content-Type` extension rule, temp+`os.replace` with no `fsync`, both halves on `asyncio.to_thread`, every failure degrading to *fetch it*. **CM-2 satisfied** — the epic AC c3-6 homed here by name. **Two guards taken down and each replaced by a stronger positive gate**: eight names out of `_BANNED_IDENTIFIERS` (the two survivors re-keyed onto `functools`, resolved through imports — narrower where it was wrong, wider where it matters), `to_thread` out of `_BLOCKING_CALLS`, all three pairings reworked plus a fourth added, and two new gates — one rename-into-place site per module in exactly two named modules, and no file I/O on the event loop. `npm run gen:api` produced **no diff**, the second measured behaviour-only story. Suites 2326 → 2386 Python, frontend 568 unchanged; twelve gates green; SPA bundle and plugin mirror re-measured byte-identical on all ten files. Six probes, each verified on disk and reverted by hash: **(c)** passed every functional test and was caught only by the gates that replaced the ban; **(f)** was caught by exactly one test out of 911; **(d)** found a real gap in this story's own coverage — the route-level mislabel assertion was missing and was added. Five debug-log findings, including a false claim in the story's own text (the pool-burst test drove one id 99 times, not 99 distinct ones) and a `git checkout` that discarded uncommitted work mid-probe, caught by the hash check. |
