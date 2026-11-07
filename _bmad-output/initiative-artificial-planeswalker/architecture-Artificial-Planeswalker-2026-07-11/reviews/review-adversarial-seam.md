# Adversarial Seam Review — ARCHITECTURE-SPINE (deck-power-assessment)

- **Spine:** `ARCHITECTURE-SPINE.md` (deck-power-assessment, 2026-07-11, status: final)
- **Sources cross-read:** `docs/deck-assess.md` (research paper §7.3 schema), `prds/.../prd.md` (FR/NFR)
- **Method:** For each seam I construct two implementation units one level down — two feature-groups, or two developers implementing two FRs — that each obey **every AD to the letter** yet produce **incompatible artifacts**. Each such pair is a hole to close with a new/tightened AD.
- **Verdict:** The functional-core/impure-shell split (AD-1, AD-2, AD-9) is sound and well-fenced. The determinism *intent* (AD-8) is strong but the *shared data shapes it depends on are under-pinned*. The combo record, the `reasons[]`/`structural_gaps` vocabularies, the dimension key-set, the 1–10 projection, and the cache-key algorithm are all specified in prose in one AD and re-specified differently (or left open) in another. Multiple pairs build to green tests and still diff-clash. **9 findings: 2 critical, 4 high, 3 medium.**

---

## CRITICAL

### F1 — The combo record has two incompatible shapes: AD-5's cache row vs AD-7's `flags.combos`

**Units:** FG4 dev implementing AD-5 (combo-cache repo) vs FG6 dev implementing AD-7 (`flags.combos` output).

**Both obey their AD:**
- **AD-5** pins the "distilled records actually used" as exactly: `bucket (included|almostIncluded)`, `bracket_tag`, `produces`, `popularity`, `earliest_turn_estimate`. That is the whole field list in the invariant. So the FG4 dev writes a cache row / Pydantic schema with **those five fields and no others**.
- **AD-7** pins `flags.combos` to "the `docs/deck-assess.md` schema minus absolute_score / band / percentile / EDHREC." The docs combo record (deck-assess.md §7.3) is:
  ```json
  { "cards": ["Card A","Card B"], "type": "two-card-infinite",
    "produces": "infinite mana", "spellbook_id": "1234-5678",
    "bracket_tag": "Ruthless", "earliest_turn_estimate": 6, "popularity": 20431 }
  ```
  So the FG6 dev needs `cards[]`, `type`, and `spellbook_id` — **none of which AD-5 stored**.

**Incompatible artifact:** The core receives combos from the cache (AD-2: "combo data enters the core frozen"). The cache, built to AD-5's field list, carries no `cards`, no `spellbook_id`, no `type`. FG6 cannot populate `flags.combos` — the very audit surface FR23/NFR2 exist for ("surface the exact cards/combos that drove the result"). It also cannot build the two-card-infinite Bracket trigger cleanly (FR15/FR18 need `type`/`cards`). Result: `KeyError`, or FG6 silently re-fetching card names from somewhere else and drifting from the cached set.

**Tightening (new AD or extend AD-5):** Define one canonical frozen `ComboRecord` Pydantic model that is simultaneously (a) what the cache stores, (b) what enters the core, and (c) what AD-7 emits in `flags.combos`. Pin its full field set: `cards: list[str]` (sorted, canonical Scryfall names), `spellbook_id: str`, `type: str`, `produces: str`, `bracket_tag: <enum>`, `bucket: included|almostIncluded`, `popularity: int`, `earliest_turn_estimate: int`. AD-5's list is currently a **subset** of what AD-7 requires — make them the same object.

### F2 — `reasons[]` and `structural_gaps[]`: closed enum vs free strings with embedded counts — breaks AD-8 sort-determinism and the diff

**Units:** FG6 dev A implementing FR21 confidence per AD-6 vs FG6 dev B implementing FR9/FR23 `structural_gaps` per AD-7 — and even one dev across two runs.

**Both obey their AD:**
- **AD-6** enumerates *some* reason tokens as snake_case machine codes: `combo_data_stale`, `combo_data_unavailable`, `game_changer_data_unavailable`. But it leaves the reasons for **unresolved/ambiguous cards**, **multiplayer variance**, and **format-profile freshness** un-tokenized. The docs schema (deck-assess.md §7.3) models those as **free human phrases with embedded counts**: `["2 cards unresolved", "multiplayer variance", "combo line ambiguous"]`.
- **AD-8** requires all lists including `confidence.reasons[]` be emitted in "deterministic sorted order" and requires byte-identical JSON for the same inputs.

**Incompatible artifacts:**
- Dev A emits `"2 cards unresolved"`; Dev B (or a refactor) emits `"cards_unresolved"` or `"unresolved:2"`. Same condition, three strings — the diff surface (`assessment` block) is now vocabulary-dependent, not condition-dependent. A caller diffing two runs sees phantom reason churn.
- **Embedded counts poison the sort and the diff.** `"10 cards unresolved"` sorts *before* `"2 cards unresolved"` (lexical `'1' < '2'`), so AD-8's "sorted order" is not stable under count changes. And a one-card edit changes the reason string (`2`→`3`), manufacturing diff noise in the exact use case (goal #2) the spine exists to protect.
- Identical hole for `flags.structural_gaps`: docs shows `["ramp below 8x8 baseline (6)"]` — free string with an embedded count, inside the diff surface.

**Tightening (new AD):** Declare `confidence.reasons[]` and `flags.structural_gaps[]` **closed enums of snake_case codes**, enumerate the full set (`cards_unresolved`, `combo_data_stale`, `combo_data_unavailable`, `game_changer_data_unavailable`, `multiplayer_variance`, `format_profile_stale`; gaps: `ramp_below_baseline`, `interaction_below_baseline`, `draw_below_baseline`, `land_count_off`, …), **forbid embedded counts** (any count lives in a separate structured field, never in the token), and pin the sort to Unicode codepoint over the tokens. Human phrasing/counts appear only in the pure-projection `summary` (AD-8 already makes `summary` a deterministic projection).

---

## HIGH

### F3 — `bracket_tag` casing is unpinned: API UPPERCASE vs docs Title-case → combo→bracket map silently misses

**Units:** FG4 dev distilling the Spellbook response (AD-5) vs FG5 dev writing the combo→bracket classifier in the core (AD-10 lists "combo→bracket" as a core function).

**Both obey their AD:** AD-5 says the cache "carries `bracket_tag`" — the FG4 dev stores what the API returns. Research §3.3 states the backend value is **UPPERCASE** (`RUTHLESS`→4, `SPICY`/`POWERFUL`→3, `ODDBALL`/`PRECON_APPROPRIATE`→2, `CASUAL`→1). The docs §7.3 schema, which AD-7 makes authoritative for output shape, shows **Title-case** `"bracket_tag": "Ruthless"`.

**Incompatible artifact:** FG4 caches `"RUTHLESS"`; FG5's core map keys on `"Ruthless"` (docs form). Lookup misses → every combo falls to a default bracket contribution → wrong Bracket floor (FR18) and wrong `combo_potential`, **deterministically wrong** (so tests pass on a fixed snapshot and the bug ships). It also means the cached `bracket_tag` and the emitted `flags.combos.bracket_tag` (AD-7/docs) differ in case between the two decks a caller diffs if the two were built by different code paths.

**Tightening:** Pin `bracket_tag` as a closed enum with exact casing, normalized **at the edge** to one canonical form (recommend the backend UPPERCASE set) before it enters the core; the core's tag→power table keys on exactly that set; AD-7 output emits exactly that set (update the docs example). Also pin the fallback when a tag is unknown/absent.

### F4 — The 7 dimension keys are not pinned as an always-present closed set across Commander and Standard

**Units:** FG5 Commander scorer dev vs FG5 Standard scorer dev (both under AD-2/AD-3/FR16), consuming per-format `FormatProfile`.

**Both obey their AD:** AD-3 says per-dimension mappings "live as typed frozen constants in FormatProfile, **one profile per format**," and the scorer "reads it and branches on it." FR16 lists 7 dimensions; FR20 says Standard is "heuristic-only (curve / interaction / Karsten-60 / combos)" — i.e. Standard has **no meaningful resilience or card_advantage signal**. AD-7 says "7-dimension vector" but never states every key is present with an integer for every format.

**Incompatible artifacts:**
- Commander profile defines all 7; Commander scorer emits all 7 with ints.
- Standard profile, honoring FR20, defines only the 5 it can compute; Standard scorer **omits** `resilience` and `card_advantage`. Or a different dev emits them as `null`, or as `0`. Three encodings of "not computed": absent key, `null`, `0` — three different diffs, and a caller with `assessment["dimensions"]["resilience"]` breaks on Standard.
- Key spelling is also only pinned by the docs example (`mana_efficiency`, `card_advantage`, `combo_potential`); nothing stops `manaEfficiency` / `mana_eff`.

**Tightening (extend AD-3/AD-7):** Pin the exact 7 keys as a frozen tuple (`speed, consistency, resilience, interaction, mana_efficiency, card_advantage, combo_potential`), **required present in every assessment for every supported format**, each an `int` 0–100 — never absent, never `null`. A format that cannot compute a dimension must still emit an integer (documented default) plus a `confidence.reasons[]` code, not drop or null the key. The key set is a spine invariant, not a per-profile choice.

### F5 — The 1–10 projection: formula, rounding mode, precision, and JSON type are all unpinned → cross-build non-determinism

**Units:** FG5 dev deriving the projection (FR19) vs FG6 dev serializing it (AD-8) — and build-to-build.

**Both obey their AD:** AD-8 says only "the 1–10 projection **rounded to fixed precision**." FR19 says "derive the familiar 1–10 as a secondary projection." The glossary says the floor is **1**. None of these pin: (a) the mapping formula, (b) the rounding mode, (c) the digit count, (d) number-vs-string.

**Incompatible artifacts:**
- **Formula divergence (correctness, not just formatting):** Dev A uses `score/10` → range 0.0–10.0 (violates the "1–10" floor). Dev B uses `1 + score*9/100` → range 1.0–10.0. For `score=68`: A=6.8, B=7.12. **Different numbers**, both "obeying" FR19.
- **Rounding mode:** Python's default `round()` is banker's rounding (half-even); `7.05 → 7.0`. A dev using `Decimal`/half-up gets `7.1`. Same input, two builds, different byte output → AD-8's byte-identity claim fails *across builds*, the exact thing NFR8 says fixed mappings must guarantee.
- **JSON type:** `7.0` as a float may serialize as `7.0` or, through an int-collapsing encoder, as `7`. `"7.0"` vs `7.0` vs `7` are three diffs.
- **Ownership ambiguity feeds this:** is the 1–10 rescale a "weight" (Deferred → owned by FormatProfile, per-format, AD-3) or a serialization rule (AD-8)? If FG5 puts it in the profile and FG6 hardcodes it, two projections coexist.

**Tightening (extend AD-8):** Pin one formula (recommend `1 + for_format_score * 9 / 100`), one rounding mode (half-up via `Decimal`, explicit), exactly one decimal place, emitted as a JSON **number**, and assign single ownership (serialization layer, not the profile). State it is *derived from `for_format_score`* so it can never disagree with the score it projects.

### F6 — The content-hash cache key has no pinned algorithm or single owner (AD-5)

**Units:** the edge computing the key to *look up* vs the repo computing the key to *write* (AD-5 names both the edge as sole writer and "reached through a repository"), and any two devs.

**Both obey their AD:** AD-5 says only: "Key = **content hash of (sorted commanders + sorted mainboard names)**." Unpinned: hash function, string canonicalization, separator, multiplicity handling, name normalization, and *which layer owns the function*.

**Incompatible / dangerous artifacts:**
- **`hash()` is non-deterministic:** a dev reaching for Python's builtin `hash()` on the tuple gets a per-process PYTHONHASHSEED-salted value → cache never hits across runs **and** it's the one place a non-deterministic function could leak into behavior. Nothing in AD-5 forbids it.
- **Multiplicity blindness:** "mainboard names" — Commander is singleton, but **Standard runs 4-ofs**. If names are set-deduped, two different Standard decks (4× Lightning Bolt vs 1× Lightning Bolt, same name set) **collide to one key** → deck B gets deck A's combos → wrong score, silently, deterministically.
- **Concatenation ambiguity:** `["A","BC"]` and `["AB","C"]` hash equal without a separator/JSON encoding.
- **Normalization drift:** split/DFC cards (`Fire // Ice`), accented names (`Lim-Dûl`), case — edge lookups and repo writes canonicalize differently → permanent misses.

**Tightening (new AD):** Pin the cache key as a single named **pure** function with one owner (recommend a pure helper in `logic/assessment` so both edge and repo call the same code): `sha256` hex of a canonical `json.dumps` of `{"commanders": sorted(...), "main": sorted(...)}` using canonical Scryfall names, NFC-normalized, case-sensitive, **multiplicities included** (or explicitly documented as excluded and why), fixed key order. Forbid builtin `hash()`. Both read and write paths MUST call this one function.

### F7 — `earliest_turn_estimate` has two owners: edge-cached (AD-5) vs core heuristic (AD-2/FR16/Deferred)

**Units:** FG4 dev (fetch/distill, AD-5) vs FG5 dev (pure scorer, AD-2/AD-10).

**Both obey their AD:** AD-5 lists `earliest_turn_estimate` as a **distilled field written into the cache row** — so the edge computes it at fetch time. But FR16 says `speed` is "estimated deterministically from curve + ramp density + **combo earliest-turn heuristics**," the Deferred section calls the "combo earliest-turn heuristic" an implementation-phase deliverable that "feeds the `speed` and `combo_potential` dimensions" (i.e. lives in the **pure core**, AD-2/AD-10), and AD-2 says all scoring heuristics are pure core functions.

**Incompatible artifacts:** The estimate depends on the *deck's* curve/ramp (FR16), not just the combo. FG4 computes it from Spellbook-intrinsic data (`mana_needed`) at fetch time and caches it. FG5 computes it in the core from the deck's resolved combo pieces + curve. **Two different numbers for the same combo**, and the Bracket floor (early two-card infinite → Bracket 4, FR18) and `speed`/`combo_potential` now depend on *which* one the aggregator reads. Worse: if the edge-cached value is deck-curve-dependent but keyed only by the deck-hash, it's *coincidentally* stable; if it's combo-intrinsic, it disagrees with the core's deck-aware value.

**Tightening:** Assign one owner. Recommended: the cache stores only Spellbook-intrinsic raw inputs (`mana_needed`, the combo `cards`), and `earliest_turn_estimate` is computed **once in the pure core** from (combo pieces resolved in deck + curve), so it stays deterministic and deck-aware and cannot fork. If instead it must be combo-intrinsic and edge-computed, delete it from the core's responsibilities and state that `speed` reads the cached value verbatim. Either way, remove the double ownership AD-5 and FR16 currently create.

---

## MEDIUM

### F8 — TTL boundary operator and owner unpinned; the staleness reason makes AD-8's "same cache" ambiguous

**Units:** repo TTL check (AD-5, row carries `fetched_at`, 24h TTL) vs edge degradation logic (AD-6, "expired entry + fetch fails → stale + reason").

**Both obey their AD:** AD-5 puts `fetched_at`/TTL on the row (repo territory); AD-6 puts the expired-vs-fresh branch and the `combo_data_stale` reason at the edge. Neither pins the boundary operator (`age > 24h` vs `age >= 24h`) nor **which layer decides**. Both need the clock (fine — both are shell), but two owners of one predicate drift at the boundary.

**Determinism hole:** AD-8 promises byte-identical JSON for "same deck + snapshot + **cache**." But whether `combo_data_stale` appears — and whether combos are used at full vs stale contribution — depends on **wall-clock vs `fetched_at`**. The same deck against the same cache row, run at `fetched_at+23h` vs `+25h` with the network down, yields different `reasons[]` and different combo contribution → **different bytes**. AD-8's guarantee is really conditional on the *freshness verdict*, not just the cache contents, and the spine doesn't say so.

**Tightening:** Pin the TTL predicate (operator + 24h constant) as a single function owned by the repo; the edge consumes its verdict. State explicitly in AD-8 that determinism holds for "same deck + snapshot + **same cache freshness verdict**," so callers diff two runs close in time. Optionally make the diff surface exclude staleness-derived reasons, or document them as expected diff.

### F9 — `cedh_candidate` is double-homed; and the `flags` key-set isn't format-gated

**Units:** the bracket classifier (AD-7 "Bracket 1–5 with cEDH **candidacy** flag") vs the flags-builder (AD-7 `flags.cedh_candidate`); and Commander vs Standard flag emission.

**Both obey their AD:** AD-7 lists cEDH candidacy **both** inside the categorical/bracket block *and* as `flags.cedh_candidate`. Two code paths, one truth — they can disagree (categorical says candidate, flags says false). Separately, AD-7's `flags` list (`game_changers, combos, structural_gaps, mass_land_denial, extra_turn_chains, cedh_candidate`) is stated unconditionally, but `mass_land_denial` / `extra_turn_chains` / `cedh_candidate` are Commander-only concepts (Bracket triggers). A Standard dev may omit them (key drift) or emit them false (noise), with no rule either way.

**Tightening:** Single source of truth for `cedh_candidate` (compute once, reference it in both the categorical view and flags, or drop it from one). Pin whether `flags` keys are always present across formats (recommend: always present; Commander-only booleans are `false` for Standard) so the key-set is format-invariant for stable diffing.

### F10 — Assessment presence on non-`ok` status, and the placement of the three version tokens, are unpinned

**Units:** error-path dev (AD-7 status enum) vs happy-path dev; and any dev placing version fields.

**Both obey their AD:** AD-7 says the Result *has* `status`, `summary`, `assessment`, `schema_version`, but never says whether `assessment` is `null`/absent when `status ∈ {deck_not_found, unsupported_format, database_not_initialized, error}`. Dev A returns `assessment: null`; Dev B returns a zero-filled 7-dimension block. A caller's diff/parse breaks on the disagreement. Separately there are **three** version-ish tokens — `schema_version` (AD-7), `format_profile_version` (AD-3/FR4), `game_changers_version` (AD-3 flag) — with no pinned placement or diff-surface membership. If `format_profile_version` lands *outside* the `assessment` diff surface, a profile bump (which should change scores) won't show in the assessment diff; if inside, it will. Two devs choose differently.

**Tightening:** Pin `assessment = null` for every non-`ok` status and present+complete for `ok`. Pin the placement of all three version fields and explicitly state which sit **inside** the `assessment` diff surface (recommend `format_profile_version` and `game_changers_version` inside, since a version change should surface in the diff; `schema_version` outside as an envelope field).

---

## Seams checked and found adequately pinned (no incompatible pair constructed)

- **AD-1 async tool** — unambiguous; overrides NFR7 explicitly.
- **AD-3 rubric selector** enum `brackets | heuristic_only` — closed, pinned.
- **AD-9 layer placement** — clear owner per artifact.
- **AD-4 `game_changer` NULL semantics** — the "never coalesce None to False" rule is crisp; the "absent count must not lower the floor" phrasing is slightly murky but both reasonable readings (count only confirmed `True`) converge. Low risk; consider a one-line clarification.

---

## Priority to close (author's recommendation)

1. **F1** (combo record) and **F2** (reasons/gaps vocabulary) are the two that will silently corrupt the headline diff use case — close first.
2. **F5** (1–10 projection) and **F6** (cache key) are the two determinism/correctness landmines (`round()` half-even, `hash()` salt, 4-of collisions) — close next.
3. **F3, F4, F7** are cross-owner shape/ownership forks that will surface as integration bugs — close before FG4/FG5/FG6 branch.
4. **F8–F10** are containable with one-line tightenings to AD-5/AD-7/AD-8.
