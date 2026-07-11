# Rubric-Walker Review — ARCHITECTURE-SPINE (deck-power-assessment)

- **Spine:** `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md`
- **Reviewer role:** rubric-walker, pre-handoff gate against the GOOD-SPINE CHECKLIST
- **Date:** 2026-07-11
- **Verdict:** **PASS-WITH-FIXES**

The spine is strong: it fixes every real feature→feature-group divergence point, its ADs are
mostly enforceable structural invariants, and — importantly — it correctly ratifies the *real*
brownfield code over two stale planning documents (both the PRD's NFR7 and `project-context.md`'s
"MCP tools are sync def" rule). The gaps are operational, not structural: the network-egress
policy required by FR14 is bound but not enforced by any Rule, and two traceability/operational
details (NFR6, migration backfill path) are thin. None of these let two feature-groups diverge,
so this is not a FAIL — but the FR14 gap is a genuine enforceability miss worth closing before
handoff.

---

## Checklist walk

### 1. Fixes the real divergence points for the level below (feature→FGs), misses none — PASS

The nine cross-FG decisions that would otherwise let two builders diverge are all fixed:

| Divergence risk | Fixed by |
| --- | --- |
| async vs sync/threadpool tool | AD-1 |
| where scoring lives; network/DB in the math | AD-2, AD-9 |
| FormatProfile as data vs per-format strategy classes | AD-3 |
| `game_changer` NULL semantics | AD-4 |
| combo-cache location + sole writer | AD-5 |
| degradation → confidence vs crash/zero | AD-6 |
| result shape + `schema_version` | AD-7 |
| deterministic serialization (diff surface) | AD-8 |
| one oracle-text taxonomy vs forked vocab | AD-10 |

FG1–FG6 each have a home in the Capability→Architecture Map. No structural divergence point is
left open.

Soft spot (not a miss): FR2 format-**inference** location (does `deck.format`-vs-`legalities`
inference run in the pure core or the edge?) is implied by the flowchart's
"edge: resolve format → FormatProfile" but never stated as a Rule. Low risk — it reads over
already-loaded data and is naturally edge orchestration.

### 2. Every AD's Rule is enforceable and actually prevents its stated divergence — MOSTLY PASS (one gap)

Most Rules are enforceable structural invariants (async keyword, file placement, nullable column,
integer scores, sorted lists, repos-return-Pydantic, golden-JSON regression for AD-8).

**Gap — AD-5 / FR14 (HIGH):** AD-5 binds FR14 ("Cache Spellbook responses (≥24h) **with polite
throttling and 429 backoff**") but its Rule only enforces the *cache* half (dedicated table,
content-hash key, 24h TTL, sole writer, distilled records). The **throttle / 429-backoff /
timeout / User-Agent** half of FR14 is enforced by **no** AD. AD-6 governs the *outcome* of a
failed fetch (degrade), and AD-9 says "async httpx I/O adapter" — but nothing pins the client's
egress policy. An implementer could satisfy every stated Rule and still ship an unbounded,
no-timeout, no-backoff HTTP call. The sibling `src/data/importers/scryfall_api.py` already
demonstrates the required pattern (`httpx.AsyncClient(timeout=30.0)`, `max_retries`, exponential
`retry_delay`) and `tenacity>=8.0.0` is an available inherited dep — so the fix is to reuse it,
not invent it. **This is both an enforceability miss (item 2) and the silent operational
dimension of item 7.**

### 3. Nothing under Deferred could let two feature-groups diverge — PASS

- **Dimension signal→0–100 curves + aggregate weights** — deferred, but AD-3 fixes *where* they
  live (`FormatProfile`, frozen/versioned) and that a single scorer reads them. Two FGs cannot
  diverge on structure; only the numeric values are open (legitimate calibration, not architecture).
- **Benchmark-set composition** — a test artifact, not a divergence surface.
- **Combo earliest-turn heuristic** (FR16) — feeds `speed`/`combo_potential`, deferred *method*,
  but AD-2/AD-3 place it in the single pure scorer, so no cross-FG divergence.
- **Snapshot-freshness hard gate** — deferred check; AD-4 documents the assumed GC-list version.
- **PRD §2.1/§8 non-goals** — genuinely out of scope.

No deferred item is a structural fork.

### 4. Named tech is verified-current; "inherited, no new dep" claim holds — PASS (verified)

Checked the spine's Stack table against `pyproject.toml`:

| Spine claim | `pyproject.toml` | Verdict |
| --- | --- | --- |
| Python >=3.12 | py312 target | ✓ |
| mcp / FastMCP >=1.27.0 | `mcp>=1.27.0` | ✓ |
| SQLAlchemy >=2.0.44 / aiosqlite >=0.21.0 | `sqlalchemy[asyncio]>=2.0.44`, `aiosqlite>=0.21.0` | ✓ |
| httpx (Spellbook client) >=0.28.1 | `httpx>=0.28.1` | ✓ |
| pydantic v2 | `pydantic>=2.0.0` | ✓ |

The "**no new runtime dependency**" claim is **verified**: `httpx` is already a first-class dep
and is already used async in `scryfall_api.py` (`httpx.AsyncClient`), so the Spellbook client
reuses it. `tenacity>=8.0.0` (retry/backoff) is also already present — the spine could name it as
the backoff mechanism for the FR14 fix above but does not.

### 5. RATIFIES rather than contradicts the brownfield codebase — PASS (with one deliberate, sound PRD deviation)

- **AD-1 NFR7 override — CORRECT.** PRD NFR7 says the tool "is a stateless **sync `def`**
  (FastMCP threadpool)", and `project-context.md` carries the same general rule. AD-1 overrides
  both to `async def`. Verified against `server.py`: the three sibling analysis tools
  (`analyze_mana_curve`, `detect_synergies`, `validate_deck`, lines 394–463) **are `async def`
  and `await get_deck_with_cards` on the FastMCP loop**; only the Epic-2 search tools
  (`semantic_search_cards`, `find_similar_cards`, lines 465–585) are sync `def`, and the module
  docstring states plainly this is *because* the `sqlite-vec` index is reachable only on the sync
  connection. `assess_deck_power` needs the async deck repo and does **not** touch `sqlite-vec`,
  so it belongs with the async siblings. The override rightly ratifies the real code over a stale
  spec. **Because it formally contradicts a PRD "MUST" (NFR7), it warrants a one-line stakeholder
  sign-off, and `project-context.md`'s blanket "MCP tools are sync def" rule should eventually be
  corrected — it is already false for the Epic-1 tools.**
- **AD-9 placement — ratified.** `src/data/importers/scryfall_api.py` exists (the named sibling);
  `transform_scryfall_card` really lives in `src/data/importers/transformers.py` (matches AD-4's
  seed); repos return Pydantic (`get_deck_with_cards` → `Deck.model_validate`). Import direction
  `data → logic → mcp_server` matches `project-context.md`.
- **AD-5 write-path claims — ratified.** Verified `deck_analysis.py`: curve/synergy/validate are
  **read-only** (`get_deck_with_cards` only), so "first analysis tool to write to `cards.db`" is
  accurate, and "only writer" of the combo-cache *table* is correct. Note `cards.db` already has
  writers (`initialize_database` writes the `cards` table; `build_search_index` writes `card_vec`),
  so the new **cross-driver** concurrency surface — an async-aiosqlite writer alongside sync
  `sqlite-vec` connections and imports — is real. AD-5 leans on "the existing concurrent-writer
  hardening", which is a real commit (`3e4ff50 fix: harden DB against concurrent writers and killed
  imports`). Reasonable ratification, but the async-writer-vs-sync-reader interleave under WAL
  should be an explicit integration test, not an assumption (see finding 5).
- **AD-4 migration — ratified.** `game_changer` does not yet exist anywhere in `src/` (grep
  clean); adding it via a hand-written `scripts/migrate_*.py` matches `project-context.md`'s
  "no Alembic" rule.

### 6. Covers the driving spec's capabilities (FR/NFR coverage) — MOSTLY PASS

**FR1–FR24:** all homed. FR5/FR7/FR8 (curve/MV/land, instant ratio+CMC dist, Karsten) are covered
by the FG2→`logic/assessment` capability map and the paradigm text rather than an ID-level AD
bind — acceptable at feature altitude (per-signal math is legitimately first-implementation), but
they are the least explicitly traced.

**NFRs:** NFR1, NFR2, NFR3, NFR4, NFR5, NFR7, NFR8 all bound and addressed. **NFR6
(Testability / calibration — "a committed benchmark set anchors correctness")** is the one NFR
**absent from `binds`** and never cited by ID. It is *effectively* homed — the Deferred section's
"Benchmark-set composition" bullet and AD-3's "re-run the benchmark" cover the capability — so
this is a **traceability gap, not a coverage hole** (finding 2). Add NFR6 to `binds` and cite it
in the benchmark Deferred bullet.

### 7. Every dimension the FEATURE altitude owns is decided/deferred/open — one silent operational dimension

- **Network egress (NEW, the big one):** partially silent. Cache = decided (AD-5); failure
  outcome = decided (AD-6); but **timeout / 429-backoff / throttle / User-Agent policy is
  undecided and unassigned** despite FR14 explicitly requiring it. Not in any Rule, not in
  Deferred → it is *silent*. See finding 1.
- **Migration / backfill (NEW):** mostly decided (AD-4) but the **backfill data-path is
  unpinned** — `game_changer` cannot be backfilled from existing rows (it was never stored), so a
  bare migration leaves the column NULL until a heavy re-import (~500 MB / ~60k cards, per PRD §7).
  AD-4 + AD-6 absorb the interim gracefully (NULL → `game_changer_data_unavailable` → degraded
  confidence, never a wrong floor), which is good — but the operational cadence (migration then
  re-import, and the expected degraded-confidence window) should be stated, not left implicit.
  This echoes the known **G3 index_unavailable bootstrap-gap** pattern (a migration that
  dead-ends without its upstream data step). See finding 3.
- **Determinism boundary (subtle):** AD-8 promises "byte-identical JSON" for "same deck + snapshot
  + cache". Note this holds only *within a fixed cache-freshness state*: the 24h TTL boundary plus
  a failed refresh flips a `combo_data_stale` reason into `confidence.reasons[]`, changing the
  bytes even though the **scores** stay identical (which is what NFR1 actually guarantees —
  "identical … cached combo data → identical scores"). This is consistent and correct by design,
  but the implementer should understand byte-identity is conditional on cache state, not
  unconditional. Low. See finding 6.
- **Empty-deck path:** AD-7's status enum is `ok | deck_not_found | unsupported_format |
  database_not_initialized | error`. The sibling tools also carry `empty` (no mainboard cards).
  A deck with zero mainboard cards has no explicit status here — it would fall to `error` or an
  odd low-confidence `ok`. Minor. Low.

---

## Findings (ranked)

### 1. [HIGH] FR14's throttle/backoff/timeout half is bound to AD-5 but enforced by no Rule
`category: operational / enforceability`
AD-5 binds FR14 but only enforces caching; the Spellbook client's egress policy (timeout, 429
backoff, polite throttle, User-Agent) — the second half of FR14 and the new network-egress
operational dimension (checklist 7) — is fixed nowhere. An implementer can satisfy every Rule and
ship an unbounded, retry-less call.
**Fix:** add a Rule to AD-9 (or extend AD-5/AD-6) pinning a request timeout, 429/5xx backoff, and
polite throttle + `User-Agent`, explicitly reusing the `scryfall_api.py` + `tenacity` pattern that
already exists in the repo.

### 2. [LOW-MED] NFR6 is omitted from `binds` and never cited by ID
`category: traceability`
NFR6 (committed benchmark set anchors correctness) is effectively homed via the Deferred
"Benchmark-set composition" bullet and AD-3's "re-run the benchmark", but it is the only NFR not in
`binds` and is never referenced. A handoff reader can't trace it.
**Fix:** add `NFR6` to the frontmatter `binds` and cite it in the benchmark Deferred bullet.

### 3. [LOW-MED] AD-4 backfill data-path is unpinned; bare migration → all-NULL degraded window
`category: operational / migration`
`game_changer` can't be backfilled in place (never stored); AD-4 says "additive migration +
backfill" without stating the source. A migration without the ~500 MB re-import leaves every
Commander assessment at degraded confidence. Architecturally absorbed by AD-4/AD-6 NULL semantics,
but the cadence is implicit and mirrors the G3 bootstrap-gap.
**Fix:** state in AD-4 that backfill requires a Scryfall re-import (or bulk-data pass) and that the
interim degraded-confidence window is expected and safe.

### 4. [INFO / STRENGTH] AD-1's NFR7 override is correct but is a formal PRD deviation
`category: ratification`
AD-1 (async `def`) contradicts PRD NFR7 (sync `def`) and `project-context.md`'s blanket
"MCP tools are sync def" — and it is *right* to: the real Epic-1 analysis siblings are async and
`assess_deck_power` doesn't touch `sqlite-vec`. Both source docs are stale for this tool.
**Fix:** flag the deviation for a one-line stakeholder sign-off and schedule a correction to
`project-context.md`'s sync-tool rule.

### 5. [LOW] New cross-driver concurrency surface on `cards.db` should be a real test, not an assumption
`category: operational / concurrency`
AD-5 makes `assess_deck_power` an async-aiosqlite **writer** to `cards.db` while sync `sqlite-vec`
connections and imports also touch the file. AD-5 leans on the existing concurrent-writer hardening
(real: commit `3e4ff50`), which is a fair ratification, but the async-writer/sync-reader interleave
under WAL is a genuinely new pattern.
**Fix:** require an integration test exercising a combo-cache upsert concurrent with a
`sqlite-vec` read; note it in AD-5.

### 6. [LOW] "Byte-identical JSON" (AD-8) is conditional on cache-freshness state
`category: clarity`
The 24h TTL boundary + a failed refresh flips a `combo_data_stale` reason into the sorted
`reasons[]`, changing output bytes though scores stay identical. Consistent with NFR1 (which
guarantees identical *scores*), but AD-8's phrasing can be misread as unconditional byte-identity.
**Fix:** one clause in AD-8 clarifying byte-identity holds within a fixed cache-freshness state;
the score/assessment diff surface is what stays stable across the TTL boundary.

### 7. [LOW] No `empty` status for a zero-mainboard deck
`category: coverage`
AD-7's status enum lacks the sibling tools' `empty`; a deck with no mainboard cards has no clean
status.
**Fix:** add `empty` to the `AssessDeckPowerResult.status` enum for parity with the analysis siblings.

---

## Bottom line

A well-constructed spine that does the hardest job right — it ratifies the actual codebase and
catches that two planning documents are stale on the sync/async question. It holds on tech-currency
(no new dep, versions verified) and leaves no deferred item that can fork two feature-groups. The
one real miss is that the **new network egress isn't governed** (FR14's operational half), plus two
thin traceability/operational details. Close finding 1 (and ideally 2–3) and this is a clean PASS.
