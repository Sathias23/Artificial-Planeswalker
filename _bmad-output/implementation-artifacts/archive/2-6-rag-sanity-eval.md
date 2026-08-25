---
baseline_commit: aae6b0b
---

# Story 2.6: RAG Sanity Eval

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a small RAG sanity eval — a fixture of natural-language MTG queries each with an **expected card that must appear in the top-K** — that runs the **real quantized embedder** (`bge-small-en-v1.5-onnx-q`) through the **production `semantic_search_cards` hybrid path** over a curated, reproducible card corpus, computes an aggregate **top-K hit-rate**, and **fails (naming the misses) when the hit-rate drops below a single tunable target**,
so that embedding/index regressions and quantized-model recall degradation are caught automatically and the composite-text weighting has a measurable knob to tune against — closing Epic 2 (FR6/FR7/FR13–FR16 are built; this is the **NFR9 quality guard** that proves they actually retrieve the right cards).

## Acceptance Criteria

> Source: [epics.md#Story-2.6](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from the real codebase and the design/research source-of-truth. The eval realizes spec §8 ("a small fixture of `query → expected card appears in top-K` checks to guard regressions in the embedding/index path"), research §"Testing & QA" ("Build it as a small fixture of MTG queries with expected top-K membership; cheap and regression-guarding"), success metric §294 ("≥ target top-K hit-rate on the MTG fixture"), and NFR9 (recall guarded by a sanity eval; **quantized-model recall is the variable to watch**, research §10 open-low). **All four ACs must hold simultaneously.**

**AC1 — A fixture of MTG queries with expected top-K membership → each expected card appears in the top-K (NFR9)**
- **Given** a curated query fixture of `(natural_language_query, expected_card_name, k)` cases over a distinctive MTG corpus
- **When** the eval runs each query through the production semantic-search path and inspects the top-K returned cards
- **Then** for each case it checks whether `expected_card_name` is among the names of the top-`k` hits, and aggregates the results into a **hit-rate** = (cases where the expected card is in top-K) / (total cases).
- **🔴 Clarification — queries are FREE natural language, NOT `compose_card_text` output.** The fake-embedder helper tests ([test_semantic_search_tool.py](../../tests/integration/mcp_server/test_semantic_search_tool.py)) deliberately query a card's *exact composed text* so a one-hot vector ranks it at distance 0 — that is an offline plumbing test, **not** a recall test. This eval must use **honest natural-language descriptions** (e.g. *"deal three damage to any target for one red mana"*, not the card's composed string) so it genuinely measures whether the **quantized model** maps meaning → the right card. Embedding is **symmetric**: the query goes through `Embedder.encode` (same as the index builder used for card text) — do **not** add a query-specific embedding.

**AC2 — Runs through the SAME hybrid path used in production, against a built/fixture index**
- **Given** the eval
- **When** it executes
- **Then** each query goes through the **production hybrid path** — `semantic_search_cards(conn, embedder, query, limit=k)` ([semantic_search.py](../../src/mcp_server/tools/semantic_search.py)) which embeds via the **real** `Embedder` and calls [`hybrid_search`](../../src/search/query.py) (KNN over `card_vec` + JOIN to `cards` + oracle de-dup) — **not** a re-implemented or shortcut query. The index it queries is a **fixture index**: a curated `cards` set whose `card_vec` is built by the production [`build_card_embeddings`](../../src/search/index_builder.py) with the **real** `get_embedder()`, so the eval exercises the exact build→query recipe production uses.
- **🔴 Clarification — use the REAL embedder, never the fake.** The fixture/helper `_FakeEmbedder`/`_FakeVecEmbedder` (one-hot per text) makes recall trivially 100% and proves nothing about the quantized model — using it here would be a silent no-op test. The eval **must** use `get_embedder()` (the Story 2.1 singleton → `bge-small-en-v1.5-onnx-q`, the quantized variant whose recall NFR9 watches). It therefore loads the ~80 MB model on first run (cached at `./data/fastembed_cache`) and **must be `@pytest.mark.integration`**, mirroring [test_real_embedder_ranks_relevant_card_first](../../tests/integration/mcp_server/test_semantic_search_tool.py#L272) and [tests/integration/search/test_embedder.py](../../tests/integration/search/test_embedder.py).

**AC3 — Below-target hit-rate fails/flags so the composite-text weighting can be tuned (NFR9)**
- **Given** the quantized model's recall is the watch variable
- **When** the aggregate hit-rate is below the target
- **Then** the eval **fails** (an `assert hit_rate >= TARGET_HIT_RATE`) with a message that **names every missed query and its expected card** (and, helpfully, what *did* rank in the top-K instead) — so the failure is actionable: the lever is the §6/§169 composite-text weighting (`name + type_line + mana_cost + oracle_text + keywords`), tuned in a *follow-up*, not silently in this story.
- **🔴 Clarification — assert an AGGREGATE hit-rate against ONE tunable target, do not hard-fail per query.** A single quantization-borderline miss must not red the build on noise. `TARGET_HIT_RATE` is a **module-level constant** = the single knob. Calibrate it: run the real model against your final fixture, observe the actual hit-rate (aim to design the corpus + queries so the real model scores ~1.0 with comfortable distance margins), then set the target a notch below the observed value (e.g. observe 12/12 → set target `0.9`) so a *genuine* recall regression trips it while one noisy case does not. The eval is a **measure-and-guard** harness; it does not itself tune the ports.

**AC4 — Part of the active suite; `legacy/` remains excluded**
- **Given** the eval test module
- **When** the suite is collected
- **Then** it lives under `tests/` (collected by `testpaths = ["tests"]`), **not** in `legacy/` (structurally excluded) — i.e. it is part of the **active suite**. It carries the `integration` marker (real model load), so the fast offline subset (`-m "not integration"`) deselects it while the **integration pass runs it**. AC4's "active suite vs `legacy/`" contrast is satisfied: an `integration`-marked test in `tests/` is part of the active suite; it is simply not in the no-download offline subset.
- **And** the eval is fully reproducible/hermetic: a `tmp_path` fixture corpus (no dependency on the developer-only 160 MB `./data/cards.db`), deterministic real embeddings (same input → identical vector, proven in [test_embedder.py](../../tests/integration/search/test_embedder.py)), `factory.close()` teardown, `reset_embedder()` around the real model.

## Tasks / Subtasks

- [x] **Task 0 — Calibration spike: confirm the real quantized model ranks the fixture correctly** (AC: 1, 2, 3) — 15–20 min, throwaway, before locking the fixture/target (mirror the Epic-2 spike discipline; this is the one empirical unknown — *which* queries the quantized model actually nails)
  - [x] On a `tmp_path` DB via `ConnectionFactory`: seed the draft curated corpus (Task 1) into a raw-SQL `cards` table (reuse the `_make_factory`/`_seed_card` shape from [test_semantic_search_tool.py](../../tests/integration/mcp_server/test_semantic_search_tool.py#L50-L99)) and `build_card_embeddings(conn, get_embedder())` (the **real** singleton, persistent `./data/fastembed_cache`).
  - [x] Run each draft `(query, expected, k)` through `semantic_search_cards(conn, get_embedder(), query, limit=k)`. For each case print the top-K names + distances and whether the expected card is present. Record the observed per-query results and the aggregate hit-rate in the Debug Log.
  - [x] Use the spike output to (a) drop/rephrase any query the model genuinely can't resolve within the corpus, (b) add corpus cards if the pool is too small for top-K to be a meaningful test, and (c) set `TARGET_HIT_RATE` from the observed rate minus a small margin. Then delete the spike file. **Do not** ship a query the model fails just to test the failure path — verify the failure path with a deliberately-wrong expectation in a *separate* unit-style assertion if desired (Task 3, optional).

- [x] **Task 1 — The curated corpus + query fixture** (AC: 1, 2) — the data the eval runs on; keep it small, distinctive, and reproducible
  - [x] Define a **curated MTG corpus** of ~16–24 cards with **real, distinctive oracle text** spanning clearly-separated archetypes so that "appears in top-K" is a non-trivial signal (with only 3–4 cards, top-5 contains everything and the test is meaningless). Each card needs the columns `build_card_embeddings` + the JOIN read: `id, oracle_id, name, type_line, mana_cost, oracle_text, keywords, colors, cmc, rarity, set_code, legalities, games` (the [`_make_factory`](../../tests/integration/mcp_server/test_semantic_search_tool.py#L50) `cards` schema). Distinct `oracle_id` per card (no duplicate-printing collapse needed here, but keep ids unique). **Starter set (adjust per Task 0):**

    | name | type_line | key oracle text (gist) | colors | cmc | distinguishes |
    |---|---|---|---|---|---|
    | Lightning Bolt | Instant | deals 3 damage to any target | R | 1 | cheap direct burn |
    | Shock | Instant | deals 2 damage to any target | R | 1 | smaller burn (near-dup of Bolt — tests discrimination) |
    | Counterspell | Instant | counter target spell | U | 2 | hard counter |
    | Llanowar Elves | Creature — Elf Druid | {T}: Add {G} | G | 1 | mono-green mana dork |
    | Birds of Paradise | Creature — Bird | {T}: Add one mana of any color | G | 1 | any-color ramp dork |
    | Wrath of God | Sorcery | Destroy all creatures. They can't be regenerated | W | 4 | board wipe |
    | Murder | Instant | Destroy target creature | B | 3 | single-target removal |
    | Serra Angel | Creature — Angel | Flying, vigilance | W | 5 | white flyer |
    | a flying red dragon | Creature — Dragon | Flying; when it attacks, deals 4 damage | R | 5 | flying red damage dragon |
    | Giant Growth | Instant | Target creature gets +3/+3 until end of turn | G | 1 | combat trick |
    | Divination | Sorcery | Draw two cards | U | 3 | card draw |
    | Sol Ring | Artifact | {T}: Add {C}{C} | (none) | 1 | colorless ramp artifact |
    | Healing Salve / lifegain | Instant | gain 3 life | W | 1 | lifegain |
    | a mill spell | Sorcery | Target player mills N cards | U | 2 | mill |
    | a token maker | Sorcery | Create N 1/1 creature tokens | W | 3 | go-wide tokens |
    | a graveyard recursion | Sorcery | Return target creature card from your graveyard to your hand | B | 2 | reanimation/recursion |

    Add ~4–8 more if Task 0 shows the pool is too thin. Use accurate, well-known oracle text (the embedder is honest — fabricated gibberish text would make rankings meaningless). It is fine to keep names generic where a real card name would be noisy; the **query never names the card**, only describes it.
  - [x] Define the **query fixture** as a list/tuple of `(query: str, expected_card_name: str, k: int)`. Each query is a **natural-language description** of an effect; the expected card is the unambiguous best semantic match *within the corpus*; `k` is small (default **5**). **Starter set (adjust per Task 0):**

    | query (natural language) | expected card | k |
    |---|---|---|
    | "deal three damage to any target for one red mana" | Lightning Bolt | 5 |
    | "counter target spell" | Counterspell | 5 |
    | "a creature that taps to add green mana" | Llanowar Elves | 5 |
    | "destroy all creatures on the battlefield" | Wrath of God | 5 |
    | "flying red dragon that deals damage when it attacks" | (the flying red dragon) | 5 |
    | "destroy a single target creature" | Murder | 5 |
    | "draw cards" | Divination | 5 |
    | "tap a creature for mana of any color" | Birds of Paradise | 5 |
    | "give a creature +3/+3 until end of turn" | Giant Growth | 5 |
    | "cheap artifact that makes colorless mana" | Sol Ring | 5 |
    | "a flying angel" | Serra Angel | 5 |
    | "make a bunch of small creature tokens" | (the token maker) | 5 |

    Keep ≥10 cases so the hit-rate has resolution (each case is worth ~8–10%).
  - [x] Decide placement of the fixture data: inline module-level constants in the test file are fine (small, self-contained), OR a tiny `tests/integration/search/_rag_eval_fixture.py` helper if it reads cleaner. **No new `src/` code** — this is test-only.

- [x] **Task 2 — The eval test module `tests/integration/search/test_rag_eval.py` (NEW)** (AC: 1, 2, 3, 4) — the home next to the existing real-model search integration test
  - [x] Module docstring stating it is the **NFR9 RAG sanity eval**: real quantized embedder, production hybrid path, aggregate top-K hit-rate guard; `integration`-marked (model load), part of the active suite, `legacy/` excluded.
  - [x] A **module-scoped fixture** (e.g. `rag_eval_index`) that builds the corpus **once** (model loads once, ~25 embeds): `reset_embedder()` → `ConnectionFactory(db_path=str(tmp_path_factory.mktemp(...) / "rag.db"))` → create the raw-SQL `cards` table → seed the corpus → `build_card_embeddings(conn, get_embedder())`. Yield `(connection_factory, embedder)`; teardown `factory.close()` + `reset_embedder()`. (Use `tmp_path_factory`, not `tmp_path`, for module scope.)

    > ⚠️ Module-scoped fixtures **cannot** use the function-scoped `tmp_path` — use `tmp_path_factory.mktemp(...)`. If module scope is awkward, function scope is acceptable (the model is cached after the first test in the session; the cost is one extra build per test — keep the number of tests in this file to 1–2).
  - [x] The **main eval test** `@pytest.mark.integration test_rag_sanity_eval_top_k_hit_rate`: iterate the query fixture, call `semantic_search_cards(conn, embedder, query, limit=k)` for each, assert `result.status == "ok"`, collect whether `expected in [hit.card.name for hit in result.cards]`, compute `hit_rate = hits / len(cases)`, and `assert hit_rate >= TARGET_HIT_RATE, <message naming every miss + what ranked instead>`. Define `TARGET_HIT_RATE` as a module constant (set in Task 0).
  - [x] (Optional but recommended) a tiny `@pytest.mark.integration` smoke `test_known_query_ranks_expected_card_first` asserting one canonical, rock-solid case (e.g. *"counter target spell"* → Counterspell **first**) — a fast, unambiguous regression tripwire independent of the aggregate threshold. Keep it to one.

- [x] **Task 3 — (Optional) failure-path unit guard** (AC: 3) — prove the harness actually fails on a regression, without flaking the real eval
  - [x] If you want to verify the assert-and-name-misses logic deterministically, factor the "is expected in top-K" + hit-rate computation into a small pure helper in the test module and unit-test it (no model) with a synthetic results list: an all-hit case passes; a below-target case raises/returns the right message naming the miss. Keep this **non-integration** (pure logic) so it runs in the offline subset. This is the only part that can be offline; the actual recall eval cannot.

- [x] **Task 4 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/integration/search/test_rag_eval.py -m integration -v` → the eval passes; capture the observed hit-rate and the per-query top-K in the Debug Log (this is the real recall measurement, the deliverable's whole point).
  - [x] `uv run pytest tests/ -m "not integration"` → full **active offline suite still green** (baseline **519 passed** after Story 2.5 — keep it green, NFR7). The new eval is deselected here (it's `integration`); if you added the optional Task 3 pure-logic test it runs here and passes.
  - [x] `uv run pytest tests/ -m integration -v` → the integration pass (real model) is green, including the new eval alongside the existing real-embedder tests.
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean for the new test file (and any fixture helper). Don't reformat unrelated pre-existing issues.
  - [x] `uv run mypy src/` → unchanged/clean (this story adds **no `src/` code**; `tests.*` is exempt from `mypy --strict` but still follow ruff/naming). `uv run pre-commit run mypy --all-files` → Passed (no new deps → **no new `additional_dependencies`**).
  - [x] **Optional real-corpus smoke (stronger signal, NOT asserted):** if `./data/cards.db` (38,232-vector index, Story 2.3) is present, run the same query fixture against it via a `ConnectionFactory(db_path="./data/cards.db")` + `get_embedder()` and note the hit-rate in the Debug Log. This is the "built index" half of AC2's "built **or** fixture index"; it is a developer-machine smoke (the 160 MB DB is not a CI/git artifact), so **do not** assert it in a test — the asserted eval is the hermetic fixture corpus.

### Review Findings

- [x] [Review][Patch] Add `assert result.cards` guard before `result.cards[0]` access in `test_known_query_ranks_expected_card_first` [tests/integration/search/test_rag_eval.py:~L370]
- [x] [Review][Defer] `evaluate_hit_rate([])` produces confusing "0 miss(es)" failure message — deferred, theoretical (hardcoded module constant; can't be emptied at runtime)
- [x] [Review][Defer] `reset_embedder()` teardown ordering hazard across modules — deferred, pre-existing (established pattern in test_embedder.py; not introduced by this story)
- [x] [Review][Defer] Yield-fixture setup failure leaves `ConnectionFactory` unclosed — deferred, pre-existing (yield-fixture limitation; tmp files cleaned by tmp_path_factory at session end)

## Dev Notes

### What this story IS — and is NOT

- **IS:** the **capstone NFR9 quality guard for Epic 2** and a **test-only** deliverable — a single new module `tests/integration/search/test_rag_eval.py` (+ optional tiny fixture helper) that builds a curated card corpus with the **real quantized embedder** via the production `build_card_embeddings`, runs a fixture of **natural-language** queries through the production `semantic_search_cards` → `hybrid_search` path, computes an **aggregate top-K hit-rate**, and **asserts it against one tunable `TARGET_HIT_RATE`, naming any misses**. It is the **seventh and final** Epic-2 piece after `ConnectionFactory` (1.2), `Embedder` (2.1), `card_vec` schema (2.2), index builder (2.3), `hybrid_search` (2.4), and `get_card_vector`/find-similar (2.5). It generalizes the existing precursor [`test_real_embedder_ranks_relevant_card_first`](../../tests/integration/mcp_server/test_semantic_search_tool.py#L272) (one query, ranks-first) into a multi-query, hit-rate-thresholded regression eval.
- **IS NOT:** a change to **any** `src/` code. The Embedder, `card_vec` schema, index builder, `hybrid_search`, and the `semantic_search_cards` tool are **frozen ports** — this story consumes them, it does not modify them. **Do not** add `query_embed`/`encode_query`, change the distance metric, alter `compose_card_text`, "improve" recall by editing the builder, or touch `pyproject.toml`/`.pre-commit-config.yaml`. If the eval *reveals* poor recall, that is a **finding the eval surfaces** (AC3) — the composite-text-weighting tuning lever is a **follow-up** response (spec §169), explicitly **out of scope** here. Resist the urge to fix what the eval measures within the same story.

### 🔴 The defining decision: REAL embedder, NATURAL-LANGUAGE queries — anything else is a fake test

Two ways to accidentally write a no-op eval that passes while testing nothing:

1. **Using the fake one-hot embedder** (`_FakeEmbedder`/`_FakeVecEmbedder`). It maps each distinct text to an orthogonal basis vector, so a query that matches a card's composed text ranks it at distance 0 *by construction* — recall is 100% regardless of model quality. That is the right tool for the *plumbing* tests (2.4/2.5 helper tests) and the **wrong** tool here. NFR9 watches the **quantized** `bge-small-en-v1.5-onnx-q` model's recall — so the eval **must** use `get_embedder()`.
2. **Querying with `compose_card_text(...)` output** (the card's exact composed string). Even with the real model, embedding a card's own composed text and asking for that card back is near-trivial (symmetric exact match). The eval must use **honest natural-language descriptions** that do *not* name the card and are phrased as a player would ask — that is what proves meaning→card retrieval.

Get both right and the eval is a genuine recall measurement; get either wrong and it is a green light that guards nothing.

### 🔴 Aggregate hit-rate, not per-query hard-fail — and how to calibrate the target

Real quantized embeddings are **deterministic** (same input → identical vector — proven by [test_embedder.py](../../tests/integration/search/test_embedder.py)), so the eval is **not flaky** given a fixed corpus + queries + model version. But a single query can sit on a semantic borderline within a small corpus; hard-failing per query would red the build on one noisy case. So:

- Compute **one aggregate hit-rate** across all cases and assert `hit_rate >= TARGET_HIT_RATE` (a single module constant — the knob).
- **Calibrate (Task 0):** design the corpus + queries so the real model scores **~1.0 with comfortable margins**, observe the actual rate, then set `TARGET_HIT_RATE` a notch below it (e.g. 12/12 observed → target `0.9`). A real recall regression (e.g. a model swap, a broken build, a `compose_card_text` change) drops several cases and trips the assert; one borderline case does not.
- The failure message **names every miss** (query, expected card, and what *did* rank top-K) so the failure is immediately actionable — pointing at the AC3 composite-text-weighting lever.

### 🔴 Marker & "active suite" — the resolution

- The eval loads the real ~80 MB model → it is `@pytest.mark.integration` (project convention: **every** real-model test is integration-marked — [test_embedder.py](../../tests/integration/search/test_embedder.py), [test_index_builder.py:382](../../tests/unit/search/test_index_builder.py#L382), [test_semantic_search_tool.py:272](../../tests/integration/mcp_server/test_semantic_search_tool.py#L272)). The model is cached at `./data/fastembed_cache` after first download, so reruns are offline.
- AC4's **"part of the active suite … `legacy/` excluded"** contrasts the collected `tests/` tree with the structurally-excluded `legacy/` tree — **not** integration vs offline. An `integration`-marked test under `tests/` **is** part of the active suite; the `-m "not integration"` filter merely scopes the fast offline subset. So: marker = `integration`, location = `tests/integration/search/`, and AC4 is satisfied. State this in Completion Notes so the reviewer doesn't read the integration marker as "excluded from the active suite".

### Building the fixture index (reuse the production build path)

- Seed a raw-SQL `cards` table on a `ConnectionFactory` connection (the [`_make_factory`/`_seed_card`](../../tests/integration/mcp_server/test_semantic_search_tool.py#L50-L99) shape — sync, no async engine needed; `semantic_search_cards` JOINs `cards` on the *same* sync connection in the single-file topology, D2). The async-engine `seeded_vec_db` conftest fixture is **not** reused here: it uses the **fake** embedder and only 4 cards — wrong on both counts for a recall eval.
- Populate `card_vec` with the **production** [`build_card_embeddings(conn, get_embedder())`](../../src/search/index_builder.py) — it self-bootstraps `card_vec` + `card_embedding_meta`, composes text via `compose_card_text`, and serializes with `serialize_float32`. Using the real builder + real embedder means the eval exercises the exact production build→query recipe (AC2). Don't hand-roll vector inserts.
- `keywords`/`colors`/`legalities`/`games` are JSON-text columns; seed them as `json.dumps(...)` (or `None`) exactly as `_seed_card` does. Use `[]` (not `None`) for "no keywords" — real Scryfall data does, and the frozen builder's `_coerce_json_list` turns a JSON `null` into `None` → `TypeError` (the [Story 2.4 fixture gotcha](./2-4-semantic-search-cards-tool-hybrid-query.md#L329)).

### Result shape the eval reads

`semantic_search_cards(conn, embedder, query, limit=k)` returns a [`SemanticSearchResult`](../../src/mcp_server/tools/semantic_search.py) with `status` ∈ `ok`/`empty`/`invalid` and `cards: list[SemanticCardHit]` (each `{ card: CardSummary, distance: float }`, nearest-first, oracle-de-duped, capped at `limit`). The eval reads `result.cards[i].card.name` for top-K membership and may log `result.cards[i].distance` for margin diagnostics. Setting `limit=k` makes `result.cards` exactly the top-K. (No relational filters needed for the core recall eval — pass plain queries; you *may* add one hybrid case, e.g. `colors=["R"]`, to confirm filters+recall compose, but it is not required.)

### Anti-patterns (do NOT do these)

- ❌ Use the **fake** one-hot embedder for the recall eval — it makes recall trivially 100% and tests nothing. Use the real `get_embedder()`.
- ❌ Query with `compose_card_text(...)` output (the card's exact composed string) — use **natural-language** descriptions that don't name the card.
- ❌ Modify **any** `src/` code (Embedder, schema, builder, `hybrid_search`, `semantic_search_cards`, `compose_card_text`) — frozen ports; this story is **test-only**. Recall tuning is a follow-up the eval *enables*, not 2.6 work.
- ❌ Add `query_embed`/`encode_query` or change the distance metric — symmetric `encode` + default L2 are proven (2.4).
- ❌ Re-implement the query path — drive the **production** `semantic_search_cards` → `hybrid_search` (AC2).
- ❌ Hard-fail per query on one borderline miss — assert the **aggregate** hit-rate against the tunable `TARGET_HIT_RATE`, naming misses.
- ❌ Depend on the 160 MB `./data/cards.db` in the asserted test — build a hermetic `tmp_path` fixture corpus; the real-DB run is an optional Debug-Log smoke (AC2 "built **or** fixture index").
- ❌ Make the corpus too small (3–4 cards) — top-K would contain everything and the test would be meaningless; use ~16–24 distinctive cards.
- ❌ Forget `@pytest.mark.integration` (real model load) — but keep it under `tests/` (active suite), not `legacy/` (AC4).
- ❌ Re-download the model into `tmp_path` — use the persistent `./data/fastembed_cache` via `get_embedder()` (the Story 2.1 default cache).
- ❌ Use function-scoped `tmp_path` in a module-scoped fixture — use `tmp_path_factory`. Always `factory.close()` + `reset_embedder()` in teardown; never `/tmp`.
- ❌ Ship a query the model genuinely can't resolve just to exercise the failure branch — calibrate the fixture so the real model passes; test the failure logic (if at all) with a pure-logic unit test (Task 3), not a deliberately-failing real query.

### Previous Story Intelligence (2.4 is the direct template; 2.1/2.3 supply the model + builder)

- **The precursor already exists and is your template:** [`test_real_embedder_ranks_relevant_card_first`](../../tests/integration/mcp_server/test_semantic_search_tool.py#L272) does, for one query, exactly the build-with-real-model-then-query-and-assert flow you generalize — `reset_embedder()`, seed cards via `_make_factory`/`_seed_card`, `build_card_embeddings(conn, get_embedder())`, `semantic_search_cards(conn, embedder, "flying red dragon that deals damage", limit=3)`, assert the dragon ranks first. Story 2.6 = that, lifted to a fixture of queries with an aggregate hit-rate threshold. [Source: [2-4 Dev Agent Record](./2-4-semantic-search-cards-tool-hybrid-query.md).]
- **Story 2.4 proved the real model ranks honestly on real data:** the AC4 smoke returned red Dragons nearest-first for *"flying red dragon that deals damage"* and applied hybrid filters correctly on the 38,232-vector index in 40–51 ms — so a curated-corpus eval with the same model will rank sensibly; your job is to pick queries with unambiguous expected answers. [Source: [2-4 Debug Log](./2-4-semantic-search-cards-tool-hybrid-query.md#L311).]
- **Story 2.1 handed you** `get_embedder()` (singleton, persistent `FASTEMBED_CACHE_DIR` → `./data/fastembed_cache`, the **quantized** `bge-small-en-v1.5-onnx-q`) + `reset_embedder()` for clean test state; `encode("")` raises (irrelevant here — queries are non-empty). [Source: [2-1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md); [embedder.py](../../src/search/embedder.py).]
- **Story 2.3 handed you** `build_card_embeddings(conn, embedder)` (the supported, self-bootstrapping population path — use it, don't hand-roll inserts) + `compose_card_text` (the canonical recipe whose docstring explicitly names *this* story: *"Story 2.6's RAG eval must embed queries against vectors built from this exact recipe"*). [Source: [2-3](./2-3-card-embedding-index-builder-idempotent-incremental.md); [index_builder.py:118](../../src/search/index_builder.py#L118).]
- **Recurring review findings to pre-empt:** `tmp_path`/`tmp_path_factory` not `/tmp`; `factory.close()` (and `reset_embedder()`) teardown; positional row indexing on `ConnectionFactory` connections (n/a here — you read through the tool, not raw rows); Google-style docstrings; ruff-clean. The `_FakeEmbedder` triplication/quadruplication is tracked in [deferred-work](./deferred-work.md) — **do not add a fifth copy**; this story doesn't need a fake embedder at all. [Source: [2-1/2-2/2-4/2-5 reviews](./deferred-work.md).]
- **Baseline green at 519 passed** (`-m "not integration"`) after Story 2.5; `legacy/` excluded. Keep it green (NFR7); this story adds no offline tests except the optional Task 3 pure-logic guard.

### Git Intelligence

- HEAD `aae6b0b` "feat: add find_similar_cards tool + code review patches (Story 2.5)" closed Story 2.5 (the Epic-2 chain: `1d2b7a2` 2.2 → `dc47b94` 2.3 → `d5acfb8`/`171d138` 2.4 → `aae6b0b` 2.5). The Epic-2 cadence is firm and ends here: thin add → focused tests → run-and-capture verify → strict scope discipline. 2.6 is the **last link** (embedder → schema → builder → semantic tool → similar tool → **eval**) and the only **test-only** story in the epic.
- `tests/integration/search/` already exists (holds `test_embedder.py`, the real-model search integration test) — `test_rag_eval.py` joins it. No `src/search/` or `src/mcp_server/` change. Working tree is clean at this baseline — no incidental edits expected beyond the story's File List.

### Latest Tech / Versions (verified for THIS project)

| Item | Value | Source |
|---|---|---|
| Embedding model | `bge-small-en-v1.5-onnx-q` (**quantized**), 384-dim float32, ~3 ms/query, ~3.6 s first-run load | [research §Probe 2](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L229) |
| Recall status | NFR9 watch variable — *"sanity test good; tune via RAG eval; quantized-model recall is the variable to watch"* (open-low) | [research §10 risk register](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L279) |
| Eval shape | small fixture `query → expected card in top-K`; *"the spike is a minimal version"*; ≥ target top-K hit-rate | [spec §8](../../docs/architecture.md); [research §"Testing & QA"/§294](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md#L264) |
| Production path | `semantic_search_cards(conn, embedder, query, limit=k)` → `hybrid_search` (KNN + JOIN + oracle de-dup) | [semantic_search.py](../../src/mcp_server/tools/semantic_search.py); [query.py](../../src/search/query.py) |
| Build path | `build_card_embeddings(conn, embedder)` (self-bootstraps `card_vec`; `compose_card_text` recipe) | [index_builder.py](../../src/search/index_builder.py) |
| Real model cache | `./data/fastembed_cache` (persistent; model downloaded by Stories 2.1/2.3 — present on this machine) | [test_embedder.py:18](../../tests/integration/search/test_embedder.py#L18); ls `data/fastembed_cache` |
| Real index (optional smoke) | `./data/cards.db`: **38,232** vectors (Story 2.3) — developer machine only, not CI/git | [2-3 Debug Log](./2-3-card-embedding-index-builder-idempotent-incremental.md) |
| Marker | `@pytest.mark.integration` (registered in `pyproject.toml`); deselect with `-m "not integration"` | [pyproject.toml:80](../../pyproject.toml) |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) |

### Project Structure Notes

Target additions (everything else unchanged — **test-only story, no `src/` edits**):

```
tests/
  integration/
    search/
      test_embedder.py        # (unchanged, 2.1) — the real-model integration test pattern to mirror
      test_rag_eval.py        # NEW — the RAG sanity eval: real embedder + production hybrid path + top-K hit-rate guard
      _rag_eval_fixture.py    # OPTIONAL NEW — corpus + query fixture data (or inline as module constants)
```

- **Alignment:** matches spec §8 ("RAG sanity eval — `query → expected card in top-K`"), research §"Testing & QA" + roadmap step 5 + success metric ("≥ target top-K hit-rate"), and NFR9. Closes Epic 2's quality gate. No FR adds code; this is the NFR9 guard over FR6/FR13–FR16. [Source: [spec §8/§6/§10](../../docs/architecture.md); [research §Testing/§10/§294](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]
- **Layering check:** a test module consuming the public `src/search` + `src/mcp_server` surface downward — no new production code, no new dependency, no cycle. `src/search`/`src/mcp_server` stay untouched. ✅
- **No new dependencies / no `pyproject.toml` or `.pre-commit-config.yaml` changes** — `fastembed`, `sqlite-vec`, `numpy`, `mcp` are already core; the `integration` marker already exists.

### References

- [epics.md — Epic 2 / Story 2.6](../planning-artifacts/epics.md) — user story + the four BDD ACs (fixture of query→expected-in-top-K; same hybrid path on a built/fixture index; below-target fails/flags for composite-text tuning; active suite, `legacy/` excluded).
- [design spec §8 (Testing) / §6 (RAG) / §10 (Open Questions)](../../docs/architecture.md) — "RAG sanity eval — a small fixture of `query → expected card appears in top-K`"; "validate with the RAG sanity eval and tune the composite if recall is poor".
- [research §"Testing & QA" / §"Risk Register §10" / §"Success Metrics"](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — eval is proven viable (the spike *is* a minimal version); quantized-model recall is the watch variable; "≥ target top-K hit-rate on the MTG fixture".
- [src/mcp_server/tools/semantic_search.py](../../src/mcp_server/tools/semantic_search.py) — `semantic_search_cards(conn, embedder, query, …) -> SemanticSearchResult`; the production path the eval drives (real embedder).
- [src/search/query.py](../../src/search/query.py) — `hybrid_search` (KNN + JOIN + oracle de-dup) reached via the tool.
- [src/search/index_builder.py](../../src/search/index_builder.py) — `build_card_embeddings` (populate the fixture index) + `compose_card_text` (its docstring names this story as the recipe queries must embed against).
- [src/search/embedder.py](../../src/search/embedder.py) — `get_embedder()` (quantized model singleton, persistent cache) + `reset_embedder()`.
- [tests/integration/mcp_server/test_semantic_search_tool.py](../../tests/integration/mcp_server/test_semantic_search_tool.py) — `_make_factory`/`_seed_card` shape to reuse, and `test_real_embedder_ranks_relevant_card_first` (line 272) — the direct precursor to generalize.
- [tests/integration/search/test_embedder.py](../../tests/integration/search/test_embedder.py) — the real-model `@pytest.mark.integration` pattern (persistent cache, `reset_embedder` fixture) and the eval's neighbour module.
- [Story 2.4](./2-4-semantic-search-cards-tool-hybrid-query.md) / [2.3](./2-3-card-embedding-index-builder-idempotent-incremental.md) / [2.1](./2-1-embedder-port-fastembed-singleton-persistent-cache.md) — the tool/builder/model this eval consumes; the JSON-`null` keywords gotcha; recurring review findings.
- [project-context.md](../project-context.md) — RAG regression-guard rule ("semantic-search work must include a small `query → expected card in top-K` sanity eval — the quantized embedding model can silently degrade recall"); testing layout; `integration` marker; ruff/mypy gates.
- [deferred-work.md](./deferred-work.md) — `_FakeEmbedder` triplication/quadruplication (do **not** add a fifth — this story needs no fake embedder).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context)

### Debug Log References

**Task 0 — calibration spike (throwaway `_spike_rag_eval.py`, deleted after use).** Seeded the draft
20-card corpus on a `tmp_path` DB via `ConnectionFactory`, built `card_vec` with the **real**
`get_embedder()` (quantized `bge-small-en-v1.5-onnx-q`), ran each draft query through
`semantic_search_cards(conn, embedder, query, limit=5)`. Observed aggregate **12/12 = 1.0000**. The
only genuinely thin margin was the green-mana-dork query — original phrasing *"a creature that taps
to add green mana"* ranked Llanowar Elves **#4** with a razor-thin **0.0022** gap to the #5 card
(Air Elemental). A phrasing diagnostic found *"a one-mana green creature that taps to add G"* lifts
Llanowar to **#3** (d=0.7183) with a comfortable **0.042** margin — adopted in the final fixture.

Final-fixture per-query result (rank of the expected card / its vec0 distance), real quantized model:

| query | expected | rank | distance |
|---|---|---|---|
| deal three damage to any target for one red mana | Lightning Bolt | 1 | 0.659 |
| counter target spell | Counterspell | 1 | 0.494 |
| a one-mana green creature that taps to add G | Llanowar Elves | 3 | 0.718 |
| destroy all creatures on the battlefield | Wrath of God | 1 | 0.669 |
| flying red dragon that deals damage when it attacks | Skyfire Dragon | 1 | 0.592 |
| destroy a single target creature | Murder | 1 | 0.493 |
| draw cards | Divination | 1 | 0.630 |
| tap a creature for mana of any color | Birds of Paradise | 1 | 0.690 |
| give a creature +3/+3 until end of turn | Giant Growth | 1 | 0.606 |
| cheap artifact that makes colorless mana | Sol Ring | 3 | 0.768 |
| a flying angel | Serra Angel | 1 | 0.678 |
| make a bunch of small creature tokens | Muster the Troops | 1 | 0.647 |

**Aggregate 12/12 = 1.0** (10 of 12 rank #1; Sol Ring and Llanowar Elves rank #3, both inside top-5).
`TARGET_HIT_RATE = 0.9` set a notch below 1.0 → one borderline miss (11/12 = 0.917) stays green, a
genuine ≥2-case regression (≤10/12 = 0.833) trips the assert.

**Task 4 — verification (all commands run, output captured):**
- `uv run pytest tests/integration/search/test_rag_eval.py -m integration -v` → **2 passed, 1
  deselected** (eval + smoke pass; offline unit test deselected).
- `uv run pytest tests/ -m "not integration"` → **521 passed, 5 deselected** in ~15s (offline suite
  green; +1 new pure-logic guard over the ~519–520 baseline; the 2 integration eval tests are
  deselected here).
- `uv run pytest tests/ -m integration -v` → **5 passed, 521 deselected** (the 2 new tests green
  alongside the existing `test_real_embedder_ranks_relevant_card_first`, `test_embedder`,
  `test_index_builder` real-model tests). Total suite = 526.
- `uv run ruff check .` / `uv run ruff format --check .` → the new file is clean (`All checks
  passed!` / `already formatted`); the only remaining findings are **pre-existing & unrelated**
  (`_bmad/scripts/tests/test_resolve_customization.py`, `_bmad/scripts/*`, `card_lookup.py`) — left
  untouched per the "don't reformat unrelated pre-existing issues" instruction.
- `uv run mypy src/` → **Success: no issues found in 46 source files** (no `src/` code added).
- `uv run pre-commit run mypy --all-files` → **Passed** (no new deps → no `additional_dependencies`).
- **Optional real-corpus smoke** (throwaway `_smoke_real_corpus.py`, deleted) against the real
  38,232-vector `./data/cards.db`: **2/12 HIT, NOT asserted.** Every top-5 list is *semantically*
  on-target (burn→Volcanic Hammer/Fire Ambush/Bring Low; board-wipe→End Hostilities/Day of Judgment;
  draw→Card Draw/Brainstorm; *"counter target spell"*→Counterspell is in top-5 = HIT), confirming
  the production path ranks honestly end-to-end on the real 160 MB index. The low specific-card
  hit-rate is expected and is **exactly why AC2 asserts against a hermetic curated fixture**: over
  38k cards there are dozens of equally-valid board wipes / burn spells / draw spells, so "this
  *specific* expected card in top-5" is a far harder, ambiguous task than over a curated 20-card
  pool with one unambiguous best match each. (`Skyfire Dragon` is a fictional fixture card, so that
  case necessarily misses on the real index.)

### Completion Notes List

- **Test-only deliverable, no `src/` change.** One new module `tests/integration/search/test_rag_eval.py`
  consumes the frozen Epic-2 ports (`Embedder`/`get_embedder`, `build_card_embeddings`/
  `compose_card_text`, `hybrid_search`, `semantic_search_cards`) without modifying any of them.
  `mypy src/` unchanged; no `pyproject.toml`/`.pre-commit-config.yaml` edits; no new dependencies.
- **REAL embedder + NATURAL-LANGUAGE queries** (the defining decision). The eval uses `get_embedder()`
  (the quantized `bge-small-en-v1.5-onnx-q` whose recall NFR9 watches) — **never** the fake one-hot
  embedder — and queries are honest effect descriptions that never name the card and are never a
  card's `compose_card_text` output, so it genuinely measures meaning→card retrieval.
- **Aggregate hit-rate, one tunable knob.** `TARGET_HIT_RATE = 0.9` (module constant) asserted
  against the aggregate; no per-query hard-fail. Failure message names every miss + what ranked
  instead, pointing at the composite-text-weighting follow-up lever (AC3) — which is **out of scope**
  for this story (the eval measures and guards; it does not tune the ports).
- **🔵 Reviewer note — marker vs "active suite".** The eval is `@pytest.mark.integration` (it loads
  the real ~80 MB model, per project convention for every real-model test). This does **not** exclude
  it from the active suite: it lives under `tests/` (collected by `testpaths = ["tests"]`), unlike the
  structurally-excluded `legacy/` tree. The `-m "not integration"` filter merely scopes the fast
  offline subset; the integration pass runs it (AC4 satisfied).
- **Hermetic & reproducible** (AC4): module-scoped fixture builds the corpus once on a
  `tmp_path_factory` DB (no dependency on the 160 MB `./data/cards.db`); real embeddings are
  deterministic; teardown does `factory.close()` + `reset_embedder()`.
- **Task 3 pure-logic guard included.** The hit-rate computation + miss-naming logic is factored into
  pure helpers (`evaluate_hit_rate`, `format_failure`) and unit-tested **offline** (non-integration,
  runs in the `-m "not integration"` subset) — proving the assert-and-name path deterministically
  without the model.
- **Out-of-scope working-tree note:** a pre-existing modification to `.gitignore` (adds `/temp/`) was
  present in the working tree and was **not authored by this story** — left untouched, excluded from
  the File List below.

### File List

- `tests/integration/search/test_rag_eval.py` — **NEW.** The NFR9 RAG sanity eval: curated 20-card
  corpus + 12 natural-language query fixture (inline module constants), module-scoped real-model
  build fixture, the integration aggregate-hit-rate eval, the integration `counter target spell`
  first-rank smoke tripwire, and the offline pure-logic helper unit guard.

_(Process artifacts updated by the workflow, not story code: `2-6-rag-sanity-eval.md` status +
Dev Agent Record; `sprint-status.yaml` status → review.)_

## Change Log

| Date | Change |
|---|---|
| 2026-06-24 | Story 2.6 implemented (test-only): added `tests/integration/search/test_rag_eval.py` — NFR9 RAG sanity eval over the real quantized embedder + production hybrid path; calibrated `TARGET_HIT_RATE = 0.9` against an observed 12/12 = 1.0. Offline suite green (521 passed); integration pass green (5 passed). Status → review. |
