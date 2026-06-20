---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: ['docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md']
workflowType: 'research'
lastStep: 6
status: complete
verdict: 'GO — stack proven end-to-end on Windows / CPython 3.12.13; D2 and D6 ship as written; no driver fallback required'
research_type: 'technical'
research_topic: 'sqlite-vec + fastembed RAG stack on Windows'
research_goals: 'De-risk the Phase 1 RAG stack before building: (1) confirm sqlite-vec loads cleanly as a SQLite extension under uv/Python on Windows, with a concrete fallback; (2) confirm fastembed (ONNX) installs/runs on Windows and ships bge-small-en-v1.5 (384-dim) offline; (3) validate the hybrid relational-JOIN-vector query path and expected build time / footprint / latency for ~60k cards.'
user_name: 'Brad'
date: '2026-06-20'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-06-20
**Author:** Brad
**Research Type:** technical

---

## Research Overview

This is a **Phase-1 de-risk** ("Step 0") for the MCP-server architecture pivot. It validates the RAG stack the pivot depends on — `sqlite-vec` + `fastembed` over a single SQLite file — *before* it becomes foundational, with explicit attention to the project's Windows + `uv` environment. Method: web verification against primary sources (sqlite-vec, fastembed, FastMCP, CPython, SQLite) combined with a **live empirical spike on the project's actual interpreter**, with confidence levels on every claim.

**Verdict: GO.** The stack runs end-to-end on CPython 3.12.13 / SQLite 3.50.4 / Windows with **no fallbacks required**. The feared Windows `enable_load_extension` blocker does not apply to this build; `sqlite-vec` v0.1.9 loads cleanly; the §6 hybrid metadata-filtered KNN works; and `fastembed` (`bge-small-en-v1.5`, 384-dim, ~3 ms/query) produces correct semantic rankings of card text. Decisions **D2** and **D6** ship as written. Residual unknowns are soft — embedding-recall tuning and the core/agent coupling surface — both managed incrementally behind two thin ports.

The full executive summary, the D1–D7 verdict, the six concrete design deltas to feed back into the spec, the final §10 risk register, and the implementation roadmap are in the **Research Synthesis** section at the end of this document.

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technical Research Scope Confirmation

**Research Topic:** sqlite-vec + fastembed RAG stack on Windows

**Research Goals:** De-risk the Phase 1 RAG stack before building — (1) confirm `sqlite-vec` loads cleanly as a SQLite extension under uv/Python on Windows, with a concrete fallback; (2) confirm `fastembed` (ONNX) installs/runs on Windows and ships `bge-small-en-v1.5` (384-dim) offline; (3) validate the hybrid relational-JOIN-vector query path and expected build time / footprint / latency for ~60k cards.

**Technical Research Scope:**

- Technology Stack & Packaging — sqlite-vec / fastembed install + load under uv on Windows; `enable_load_extension` gotcha; wheel/binary availability
- Architecture & Integration Patterns — single-file hybrid query (relational predicates JOIN `vec0` KNN)
- Implementation Approaches — idempotent/incremental index build over ~60k cards; embedding-text composition; FastMCP wiring
- Performance Considerations — build time, on-disk footprint, query latency for ~60k × 384-dim on CPU; brute-force vs ANN
- Fallback Options — alternate SQLite build, bundled binary, or alternative store (LanceDB / Chroma / numpy)

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Optional empirical verification on the local Windows + uv environment

**Scope Confirmed:** 2026-06-20

---

## Technology Stack Analysis

> Methodology note: claims below are web-verified against current sources (June 2026) with confidence levels. The two items marked **VERIFY EMPIRICALLY** are the decision-gating unknowns that should be settled with a spike on the target Windows + `uv` environment before build (see §Implementation Research).

### Component 1 — `sqlite-vec` (the vector extension)

`sqlite-vec` is a pure-C, single-file loadable SQLite extension (`vec0` virtual table). Stable since v0.1.0 (Aug 2024); latest **v0.1.9 (Mar 31, 2026)**. Brute-force KNN only (no ANN index), supports binary quantization, designed to "run anywhere." The PyPI package `sqlite-vec` bundles the compiled extension and a `sqlite_vec.load(conn)` helper.

- **Loading pattern (per official docs):**
  ```python
  import sqlite3, sqlite_vec
  db = sqlite3.connect(":memory:")
  db.enable_load_extension(True)
  sqlite_vec.load(db)
  db.enable_load_extension(False)
  ```
- **Windows history:** two distinct failure reports, **both now closed**: `vec0.dll` "specified module could not be found" (DLL-dependency/runtime — [#13](https://github.com/asg017/sqlite-vec/issues/13), [#45](https://github.com/asg017/sqlite-vec/issues/45)). Closed status + ongoing Windows-aware development on the newest wheels is encouraging but the resolution text wasn't readable from the issue headers. _Confidence: medium that current wheels load cleanly; **VERIFY EMPIRICALLY**._
- _Sources: [sqlite-vec GitHub](https://github.com/asg017/sqlite-vec), [Python usage docs](https://alexgarcia.xyz/sqlite-vec/python.html), [PyPI](https://pypi.org/project/sqlite-vec/), [v0.1.0 release notes](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html)._

### Component 2 — The Python SQLite driver (the actual gating factor)

The real Windows risk is **not** `sqlite-vec` — it's whether the Python SQLite driver exposes `enable_load_extension`.

- Python's **stdlib `sqlite3` is "not built with loadable extension support by default"** ([Python docs](https://docs.python.org/3/library/sqlite3.html)). On Windows python.org builds this has historically been **disabled at compile time** → `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'` ([CPython #95656](https://github.com/python/cpython/issues/95656)).
- CPython #95656 is now **CLOSED with PR #95662**, which *may* enable it in recent Windows builds — but the current docs still describe the feature as off-by-default and I could **not** confirm the exact Python version that flipped it. _Confidence: medium; **VERIFY EMPIRICALLY** on the target interpreter (`python -c "import sqlite3; sqlite3.connect(':memory:').enable_load_extension(True)"`)._
- **Robust driver fallback — `apsw`:** Another Python SQLite Wrapper (Roger Binns) ships **Windows wheels** via pip, bundles its own recent SQLite, and fully supports `enable_load_extension`/`load_extension`. `sqlite-vec` is documented to work with apsw. This is the recommended fallback that **preserves the single-SQLite-file design**. Caveat: apsw is not a 100% DB-API drop-in for stdlib `sqlite3`, so the data layer must reach SQLite through a thin connection factory rather than hardcoding `sqlite3.connect`. _Confidence: high._
- **Ruled out / weak:** `sqlean.py` — **no Windows wheels** and does not load third-party extensions ([repo](https://github.com/nalgeon/sqlean.py)). `pysqlite3` / `pysqlite3-binary` — contradictory Windows-wheel availability, historically Linux-focused ([pysqlite3](https://github.com/coleifer/pysqlite3)); secondary at best.
- _Sources: [CPython #95656](https://github.com/python/cpython/issues/95656), [Python sqlite3 docs](https://docs.python.org/3/library/sqlite3.html), [APSW docs](https://rogerbinns.github.io/apsw/), [sqlite-vec Python docs](https://alexgarcia.xyz/sqlite-vec/python.html)._

### Component 3 — `fastembed` (embeddings, D6) — CONFIRMED GOOD ON WINDOWS

- `pip install fastembed` (CPU). Default model **`BAAI/bge-small-en-v1.5` (384-dim)**, runs on **ONNX Runtime with no PyTorch** dependency.
- Auto-downloads + caches the model on first use (`FASTEMBED_CACHE_DIR` / `cache_dir`); **offline** after the first fetch. Windows-supported (common pitfall is installing the wrong `onnxruntime` vs `onnxruntime-gpu` variant — use plain CPU). _Confidence: high; D6 holds on Windows._
- _Sources: [fastembed GitHub](https://github.com/qdrant/fastembed), [PyPI](https://pypi.org/project/fastembed/), [Getting Started](https://qdrant.github.io/fastembed/Getting%20Started/), [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)._

### Component 4 — Performance & storage at Phase-1 scale (~60k × 384-dim) — CONFIRMED COMFORTABLE

- `sqlite-vec` is **brute-force only**; published benchmarks show ~100k vectors at small dimensions (384/768/1024) returning KNN in **<75ms**. 60k @ 384-dim sits well inside that envelope.
- On-disk: 60k × 384 × 4 bytes ≈ **~92 MB** of raw float32 vectors (plus index/overhead); binary quantization can shrink ~32×. Modest for a one-time build. _Confidence: high that performance/footprint are fine for Phase 1._
- **Scale ceiling:** brute-force "doesn't scale" past ~1M vectors. If the catalog grows or latency tightens, options are binary quantization, ANN via **`vectorlite`** (HNSW, 3x–100x faster, lower recall — also a loadable extension), or a store swap to **LanceDB** (disk ANN, pip wheel, no extension loading).
- _Sources: [Alex Garcia v0.1.0 post](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html), [vectorlite benchmarks](https://github.com/1yefuwang1/vectorlite), [MarkTechPost release coverage](https://www.marktechpost.com/2024/08/04/sqlite-vec-v0-1-0-released-portable-vector-database-extension-for-sqlite-with-support-for-1-million-128-dimensional-vectors-binary-quantization-and-extensive-sdks/)._

### Fallback ladder (the "have a fallback ready" §10 asked for)

1. **Stdlib `sqlite3`** — *iff* the target Python's Windows build supports `load_extension`. Simplest; verify first.
2. **`apsw` + `sqlite_vec.load()`** — robust, Windows wheels, **keeps the one-SQLite-file design**. **Recommended default if (1) fails.**
3. `pysqlite3` — only if it has Windows wheels for the target version; secondary.
4. **Store swap → LanceDB** — abandons the "one file, relational JOIN vector" elegance but eliminates extension loading entirely. Last resort.
5. Alt extension `sqlite-vector` (sqliteai, ships Windows binaries) — still needs a `load_extension`-capable driver, so it does **not** bypass the Component-2 risk.

### Architectural implication to feed back into the spec

D2's "one SQLite file" goal **is** achievable on Windows, but the data layer **must not hardcode `sqlite3.connect`** — route SQLite access through a thin **connection factory** so `apsw` can be substituted without touching tool logic. This is small and aligns with the spec's own "extract a core facade as we hit coupling" note (§4). Decisions D2/D6 survive this research; the only addition is the connection-factory seam plus a one-command load-extension probe in the index builder's preflight.

_Confidence summary: fastembed (high) · performance/footprint (high) · apsw fallback viability (high) · stdlib-sqlite3-on-Windows native support (medium — verify) · current sqlite-vec wheel loads cleanly on Win11 (medium — verify)._

---

## Integration Patterns Analysis

> For this stack the meaningful integrations are: (1) relational ↔ vector hybrid query, (2) embedding ↔ storage serialization, (3) the incremental index-build pipeline, (4) MCP/FastMCP tool wiring, (5) the driver seam. Generic API/protocol patterns (REST/gRPC/OAuth/Kafka) are N/A for a local stdio MCP server.

### A. Relational ↔ vector hybrid query — §6's core claim is VALIDATED (with a design choice)

The spec's headline example — *"semantically like Glorybringer, Standard-legal red 4-drops"* — is directly supported. Since **v0.1.6 (Nov 2024)** `sqlite-vec` supports **metadata columns** declared inside the `vec0` table and usable in the `WHERE` clause of a KNN query, plus **partition keys** and **auxiliary columns**. There are two composition patterns, and the choice is a real Phase-1 decision:

- **Pattern 1 — metadata columns (pre-filter, fastest):** declare filterable attributes directly in `vec0`; sqlite-vec applies them as a KNN-aware bitmap *before* distance calc.
  ```sql
  SELECT card_id, distance
  FROM card_vec
  WHERE embedding MATCH :query_vec
    AND k = 20
    AND mana_value BETWEEN 4 AND 4
    AND color_red = 1;        -- metadata columns indexed in vec0
  ```
  Constraint: **a `k = ?` or `LIMIT` is mandatory** on every KNN query ([#116](https://github.com/asg017/sqlite-vec/issues/116)). Auxiliary (`+col`) columns can be stored but **cannot** be filtered on ([#121](https://github.com/asg017/sqlite-vec/issues/121)).
- **Pattern 2 — JOIN to the relational `cards` table (post-filter, most flexible):** run KNN in a subquery/CTE, then JOIN to the full relational row and apply arbitrary predicates ([#196](https://github.com/asg017/sqlite-vec/issues/196)). Caveat: KNN returns its `k` first, so **over-fetch `k`** (e.g. 100–200) before filtering down, or high-selectivity filters will starve the result set.

**Recommendation for MTG:** hybrid of both. Put **low-cardinality, high-selectivity numeric/boolean filters as metadata columns** (mana value, the 5 color booleans) for cheap pre-filtering; resolve **multi-valued / many-format legality and full card display data via JOIN** to the relational `cards` table (format-legality is one-card-to-many-formats and models poorly as a single metadata column). Over-fetch `k` then JOIN-filter. This realizes §6's "one call" promise. _Confidence: high — pattern is documented and idiomatic._
_Sources: [metadata release post](https://alexgarcia.xyz/blog/2024/sqlite-vec-metadata-release/index.html), [#26 metadata tracking](https://github.com/asg017/sqlite-vec/issues/26), [#29 partition keys](https://github.com/asg017/sqlite-vec/issues/29), [#116 k constraint](https://github.com/asg017/sqlite-vec/issues/116), [#196 JOIN filtering](https://github.com/asg017/sqlite-vec/issues/196), [ARCHITECTURE.md](https://github.com/asg017/sqlite-vec/blob/main/ARCHITECTURE.md)._

### B. Embedding ↔ storage serialization — clean

SQLite has no native vector type; vectors are stored as BLOBs. `sqlite_vec.serialize_float32()` (alias `serialize_f32`) converts a Python float list to the expected BLOB. `fastembed` emits NumPy arrays, which can be bound directly via the buffer protocol **provided they're cast `.astype(np.float32)`** (fastembed is already float32; the cast is a safety net). Official reference: `examples/simple-python/demo.py`. _Confidence: high._
_Sources: [sqlite-vec Python docs](https://alexgarcia.xyz/sqlite-vec/python.html), [demo.py](https://github.com/asg017/sqlite-vec/blob/main/examples/simple-python/demo.py), [Simon Willison TIL](https://til.simonwillison.net/sqlite/sqlite-vec), [TDS: RAG in SQLite](https://towardsdatascience.com/retrieval-augmented-generation-in-sqlite/)._

### C. Incremental index-build pipeline (§6 "idempotent + incremental")

The build script integrates fastembed → serialize → `vec0` insert, keyed by `card_id`. Idempotency/incrementality via a **content hash** of the composite embedded text (`name + type_line + mana_cost + oracle_text + keywords`) stored alongside the row; on re-import, embed only cards whose hash changed or are new. Batch fastembed `embed()` over chunks for throughput. The `vec0` insert binds `rowid = card_id` so relational rows and vectors stay JOIN-aligned. _Confidence: high — standard pattern; throughput/footprint already bounded in §Performance._

### D. MCP / FastMCP wiring (D7 transport pluggability) — current & confirmed

**FastMCP v3.2.4 (Apr 2026)** powers ~70% of MCP servers: decorator-based `@mcp.tool`, **auto JSON-schema from Python type hints**, and **stdio / HTTP / SSE transports** selectable at `mcp.run()` — which is exactly D7 (stdio now → HTTP/SSE later **without touching tool code**). Stateless tools (D5) map perfectly to plain decorated functions. One dependency decision: the standalone **`fastmcp` (PrefectHQ, v3.x)** vs. the **`FastMCP` bundled in the official `mcp` SDK (v1.27.0)** — the bundled one is the leaner dependency and the most natural fit for a Claude Code `.mcp.json` stdio server; adopt the standalone only if you need its extra auth/proxy features later. _Confidence: high._
_Sources: [fastmcp PyPI](https://pypi.org/project/fastmcp/), [PrefectHQ/fastmcp](https://github.com/prefecthq/fastmcp), [official mcp python-sdk](https://github.com/modelcontextprotocol/python-sdk), [FastMCP 2026 guide](https://www.danilchenko.dev/posts/fastmcp-mcp-server/)._

### E. Driver seam (carried from §Technology Stack)

Both the index builder and the MCP server must obtain connections through **one connection factory** that (a) enables `load_extension`, (b) calls `sqlite_vec.load(conn)`, and (c) can return either stdlib `sqlite3` or `apsw` per the Windows probe. Centralizing this is the single integration point that absorbs the Component-2 risk; tool functions stay driver-agnostic. _Confidence: high (design), pending the empirical driver decision._

_Integration confidence summary: hybrid query pattern (high) · serialization (high) · index pipeline (high) · FastMCP transport pluggability (high) · driver seam design (high)._

---

## Architectural Patterns and Design

> Focused on assembling *this* stack correctly. Generic enterprise patterns (microservices, ESB, serverless, service mesh) are N/A for a single-process local stdio server. The relevant patterns are hexagonal ports/adapters, the server concurrency/threading model, the embedding-model lifecycle, single-file data topology, and statelessness.

### System Architecture Pattern — Hexagonal (ports & adapters), single process

Clean assembly that honors the spec's §4 "agent-agnostic facade":

- **Domain core (unchanged):** `src/data` repositories + `src/logic` validators — pure, no infra imports.
- **Ports (new, thin):** `ConnectionFactory` (yields a `load_extension`-capable SQLite connection with `sqlite_vec.load()` applied) and `Embedder` (`encode(text) -> float32 vector`).
- **Adapters (new):** `sqlite3`/`apsw` connection factory; `fastembed` embedder; FastMCP tool layer mapping protocol calls → core. The index builder is an **offline batch adapter** reusing the same two ports.

This keeps tools driver-agnostic and embedder-agnostic — the Windows driver decision and any future embedder swap touch one adapter each. _Confidence: high (standard pattern, matches §4)._

### Concurrency & Threading Model — the one real gotcha

Both blocking surfaces (SQLite I/O and fastembed inference) interact with FastMCP's async loop:

- **FastMCP auto-dispatches *synchronous* `def` tools to a threadpool**, so blocking work doesn't stall the event loop ([FastMCP Tools docs](https://gofastmcp.com/servers/tools)). A known caveat exists where sync tools can still block under some setups ([python-sdk #1839](https://github.com/modelcontextprotocol/python-sdk/issues/1839)) — so **define tools as plain `def`** (let FastMCP threadpool them) and avoid mixing blocking calls inside `async def` without `run_in_executor`.
- **SQLite is not freely thread-shareable.** `check_same_thread=False` only disables Python's guard and risks corruption unless the build's threadsafety level is adequate ([Anderegg](https://ricardoanderegg.com/posts/python-sqlite-thread-safety/)). The clean pattern: **WAL mode + a connection per worker thread** (the `ConnectionFactory` hands each thread its own connection). WAL gives concurrent readers during a write ([SQLite forum](https://sqlite.org/forum/info/461653af585fb599)) — ideal for a read-heavy card-search server; the only writers at serve-time are deck CRUD (single-writer is fine).
- **GIL:** ONNX Runtime releases the GIL during native inference, so threadpooled embedding still gets real parallelism; at Phase-1 concurrency (one Claude Code client) contention is negligible.

_Confidence: high. This is the assembly detail most likely to bite if ignored._

### Embedding-Model Lifecycle — process-lifetime singleton

`fastembed` first call downloads/caches the model; subsequent batches ~**10ms**. The model is **thread-safe and read-only at inference**, so share **one lazily-loaded instance** across all tool calls via a process-lifetime singleton — never instantiate per call (load is expensive). onnxruntime thread count is tunable. Note: parallel requests can show non-deterministic latency ([fastembed #191](https://github.com/qdrant/fastembed/discussions/191)) — irrelevant at Phase-1 scale, but Phase 2 (HTTP) may warrant a dedicated embedding worker. _Confidence: high._
_Sources: [fastembed thread-safety discussion](https://github.com/qdrant/fastembed/discussions/191), [Markaicode production guide](https://markaicode.com/integrate/fastembed-with-hugging-face/)._

### Data Architecture — single-file topology (validates D2)

One SQLite file in **WAL mode**: relational tables (cards, decks) + the `card_vec` `vec0` virtual table, `rowid = card_id`.

- **Pro:** atomic single-file backup, JOIN relational ⨝ vector in one query, no second service/process — which is exactly what makes multiple clients + later HTTP transport clean.
- **Cons to manage:** `vec0` is a virtual table → a model/dimension change means **rebuild the vec table** (treat as a migration); WAL must be **checkpointed before file-copy backups**; heavy concurrent writes are limited (not our profile).
- _Validates D2 architecturally for ~60k cards. The "RAG-in-the-database" pattern keeps the system single-process and is the right call at this scale; revisit only if the catalog reaches millions (→ ANN/`vectorlite` or a store swap)._
_Sources: [SQLite concurrency overview](https://iifx.dev/en/articles/17373144), [SQLite WAL forum](https://sqlite.org/forum/info/461653af585fb599)._

### Statelessness (validates D5)

Tools are pure functions: no session state, format/games are parameters, "active deck" is a client-supplied `deck_id`. This is what *enables* the threadpool model (no shared mutable session to guard) and HTTP scale-out later (D7). _Confidence: high — design already specified; research confirms it composes with the concurrency model._

### Security / Operations (right-sized)

Local stdio server, no network surface in Phase 1 → no auth needed (Claude Code spawns it via `.mcp.json`). Embeddings/model are local (no API keys, no egress — a benefit of D2/D6). The only operational task is the **one-time/incremental index build** (offline script) and WAL-checkpointed backups. Auth/transport security re-enters at Phase 2 (HTTP/SSE) — FastMCP provides JWT/OAuth then. _Confidence: high._

_Architecture confidence summary: hexagonal layering (high) · concurrency/threading model (high) · embedding singleton (high) · single-file topology / D2 (high) · statelessness / D5 (high)._

---

## Implementation Approaches and Technology Adoption

### 🎯 Empirical spike — both `VERIFY EMPIRICALLY` gates RESOLVED on the real environment

Ran on the **project's actual interpreter** via `uv run --with` (ephemeral, auto-cleaned): **CPython 3.12.13**, bundled **SQLite 3.50.4**, Windows 11, `uv 0.11.7`.

**Probe 1 — extension loading + hybrid KNN (no downloads):**
```
stdlib sqlite3 has enable_load_extension: True          ← the gate everyone warns about: OPEN on this build
sqlite-vec vec_version: v0.1.9                            ← current wheel loads cleanly, no DLL error
hybrid KNN (k=2, mana_value=4): [(1, 0.0), (2, 1.5999)]  ← metadata pre-filter excluded the mana_value=2 card
```
→ **The stdlib `sqlite3` on the project's Windows Python build DOES expose `enable_load_extension`, and `sqlite-vec` v0.1.9 loads with no fallback driver.** The Windows DLL-load issues (#13/#45) do not reproduce on the current wheel. `apsw` is **not required** — it stays a documented contingency only.

**Probe 2 — fastembed + RAG sanity (first-run model download):**
```
model: qdrant/bge-small-en-v1.5-onnx-q   dim: 384   dtype: float32
model load incl. first-run download: 3.61s   embed 5 cards: 15ms   single query embed: 3ms
ranking for "a hasty flying red dragon that deals direct damage":
  #4 Thundermaw Hellkite 0.652 | #1 Glorybringer 0.675 | #2 Shock 0.796 | #5 Counterspell 0.860 | #3 Llanowar Elves 0.889
```
→ **D6 confirmed on Windows**: fastembed installs (onnxruntime + numpy), emits 384-dim float32 at ~3ms/query, and semantic ranking of real card text is correct (both dragons top-2). The §6 embedded-text composition concept works even on terse text.

**Two operational gotchas the spike surfaced (must address in build):**
1. **fastembed cached to a *Temp* dir** (`%LOCALAPPDATA%\Temp\fastembed_cache`) by default — volatile. **Pin `FASTEMBED_CACHE_DIR` (or `cache_dir=`) to a persistent project path** so the model survives reboots/cleanup and stays offline.
2. fastembed's default ships the **quantized** ONNX variant (`bge-small-en-v1.5-onnx-q`), not full-precision. Recall was good in the sanity test; revisit only if the RAG eval shows weakness (the §10 "embedding text composition / weighting" open question). Minor: Windows HF cache falls back to file-copy (no symlinks without Developer Mode) → more disk; `hf_xet` not installed → HTTP download. Both harmless.

_Confidence: high (executed, reproducible). Sources: local spike, 2026-06-20._

### Technology Adoption Strategy — incremental, reuse-first

Matches the spec's "pragmatic, not big-bang" stance (§4):
- Keep `src/data` + `src/logic` behaviorally unchanged; introduce the two **ports** (`ConnectionFactory`, `Embedder`) and extract the core facade only where agent coupling is actually hit.
- **Connection factory** now de-scoped from "risk mitigation" to "good hygiene": default to stdlib `sqlite3`; keep the factory seam so `apsw` *could* drop in for a future environment that lacks `enable_load_extension`, but Phase 1 ships on stdlib.
- Land the RAG layer behind the same ports the build script uses, so build-time and serve-time share one code path.

### Observed dependency set (pin these)

| Package | Observed | Notes |
|---|---|---|
| Python | 3.12.13 (project) | stdlib `sqlite3` has `enable_load_extension` ✅ |
| SQLite (bundled) | 3.50.4 | supports loadable extensions on this build |
| `sqlite-vec` | v0.1.9 | loadable extension + `serialize_float32` |
| `fastembed` | latest (ONNX) | pulls `onnxruntime`, `numpy` |
| embedding model | `bge-small-en-v1.5-onnx-q` (384-dim) | set persistent `FASTEMBED_CACHE_DIR` |
| `mcp` SDK / `fastmcp` | v1.27 SDK / v3.2.4 | bundled `FastMCP` is the lean default |

### Testing & Quality Assurance (validates spec §8)

- The **RAG sanity eval is proven viable** — the spike *is* a minimal version (`query → expected card in top-K`). Build it as a small fixture of MTG queries with expected top-K membership; cheap and regression-guarding.
- **MCP integration tests** drive each tool through an in-process FastMCP client (FastMCP supports in-memory client transport) — no subprocess needed.
- Existing `tests/unit` for `data`/`logic` stay valid; `legacy/` excluded.

### Deployment & Operations (right-sized)

- Phase 1 = local stdio, launched by Claude Code via `.mcp.json`. No service to host.
- **Index build** is an offline, idempotent/incremental script (content-hash gated). One-time ~60k embed at ~3ms each ≈ a few minutes single-threaded; batch for throughput.
- **Backups:** checkpoint WAL before file-copy. **Migrations:** a model/dimension change ⇒ rebuild the `card_vec` table.

### Risk Assessment & Mitigation — §10 status after research

| §10 risk | Status |
|---|---|
| `sqlite-vec` packaging on Windows under `uv` | **RETIRED** — loads on stdlib `sqlite3` / Py 3.12.13; fallback ladder documented if a future env differs |
| Embedding-text composition / weighting | **OPEN (low)** — sanity test good; tune via RAG eval; quantized-model recall is the variable to watch |
| Core/agent coupling surface | **OPEN (managed)** — handled incrementally behind the two ports; extent still unknown until `src/agent` moves |
| Index build time / footprint | **RETIRED** — ~3ms/embed; ~92 MB raw vectors at 60k×384; minutes to build |

### Implementation Roadmap (feeds epics/stories)

1. **Restructure & deps** — archive `src/agent`+`src/ui`→`legacy/`; add `src/mcp_server`, `src/search`; move `pydantic-ai`/`chainlit` to optional `legacy` group; add `mcp`, `sqlite-vec`, `fastembed`.
2. **Search core** — `ConnectionFactory` (load `sqlite_vec`), `Embedder` (fastembed singleton, persistent cache), `card_vec` schema (metadata cols: mana_value + 5 color booleans), `scripts/build_card_embeddings.py` (idempotent/incremental).
3. **MCP server** — FastMCP stdio; port existing tools; add `semantic_search_cards` + `find_similar_cards` (over-fetch `k`, then JOIN/filter); statelessness (D5).
4. **Skills suite** — orchestrator + capability skills (§7).
5. **Tests** — MCP integration (in-memory client) + RAG sanity eval.

### Success Metrics / KPIs

- Tool parity: all ported tools pass integration tests; 2 new search tools return correct hybrid results.
- RAG eval: ≥ target top-K hit-rate on the MTG fixture.
- Query latency: semantic search end-to-end < ~100ms at 60k (embed ~3ms + brute-force KNN).
- Build: full 60k index in minutes; incremental re-import embeds only changed cards.

_Implementation confidence summary: stack proven end-to-end on Windows (high) · adoption path (high) · testing approach (high) · residual tuning of embedding recall (low-risk, open)._

---

# Research Synthesis — RAG on Rails: De-Risking `sqlite-vec` + `fastembed` (Windows / uv)

## Executive Summary

**Verdict: GO.** The Phase-1 RAG stack is proven working end-to-end on the project's real interpreter (Windows, CPython 3.12.13, SQLite 3.50.4) with **no fallbacks required**. Decisions **D2** (`sqlite-vec` + one SQLite file) and **D6** (`fastembed` / `bge-small-en-v1.5`) ship as written. The widely-feared Windows blocker — Python's stdlib `sqlite3` lacking `enable_load_extension` — **does not apply to this build** (it returned `True`), and `sqlite-vec` v0.1.9 loaded cleanly with no DLL error. The hybrid metadata-filtered KNN that §6 depends on works, and a live semantic query ranked the two dragons above burn / counterspell / mana-dork — the embedding approach is sound even on terse card text.

The research upgraded confidence from "plausible per documentation" to "executed on the target machine." The only residual unknowns are **soft**: tuning embedding recall (fastembed ships a *quantized* model variant) and the **core/agent coupling surface**, which the architecture absorbs incrementally behind two thin ports.

**Key Technical Findings**

- **Windows extension-loading is a non-issue on this build** — `enable_load_extension: True`; `sqlite-vec` v0.1.9 loads on stdlib `sqlite3`. `apsw` demoted to a documented contingency.
- **`fastembed` is fast and accurate on Windows** — 384-dim float32, ~3 ms/query, 3.6 s one-time model load; correct semantic ranking of MTG card text.
- **§6 hybrid query validated** — `vec0` metadata columns pre-filter the KNN (mandatory `k`/`LIMIT` constraint); JOIN to the relational table for multi-valued attributes (over-fetch `k`).
- **One architectural gotcha** — both SQLite I/O and embedding inference are blocking: define MCP tools as sync `def` (FastMCP threadpools them), use WAL + a connection per worker thread, and hold the embedding model as a process-lifetime singleton.

**Technical Recommendations**

1. Ship Phase 1 on **stdlib `sqlite3`**; keep a one-line `ConnectionFactory` seam so `apsw` *could* drop in later. Do not build the fallback now.
2. Pin **`FASTEMBED_CACHE_DIR`** to a persistent project path (it defaulted to a volatile *Temp* dir).
3. Data model: `mana_value` + the 5 color booleans as `vec0` **metadata columns**; format-legality + display fields via **JOIN**.
4. Tools as sync `def` + **WAL + per-thread connections** + **embedding singleton**.
5. Build the **RAG sanity eval** (this spike is its seed) and watch quantized-model recall.

## Table of Contents

1. Introduction & Methodology
2. Verdict — Decisions D1–D7 Status
3. Technical Landscape (Stack) — see §Technology Stack Analysis
4. Integration & Architecture — see §Integration Patterns / §Architectural Patterns
5. Performance — see §Technology Stack Analysis (Component 4)
6. Design Deltas to Feed Back into the Spec
7. Risk Register — §10 Final Status
8. Implementation Roadmap
9. Sources & Verification

## 1. Introduction & Methodology

This document settles the single open question from the MCP-server pivot spec that could have forced a redesign: *is the `sqlite-vec` + `fastembed` RAG stack viable on the project's Windows + `uv` environment?* (spec §10, decisions D2/D6). Methodology: multi-source web verification against primary sources, then a **live empirical spike** executed via `uv run --with` (ephemeral, auto-cleaned) on the project's actual interpreter. Every claim carries a confidence level; the two decision-gating unknowns were marked `VERIFY EMPIRICALLY` and then resolved by the spike.

**Goals achieved:** (1) sqlite-vec loading on Windows — **resolved (works)**; (2) fastembed on Windows + offline model — **resolved (works)**; (3) hybrid query path + build/latency/footprint — **resolved (validated)**.

## 2. Verdict — Decisions D1–D7

| Decision | Status after research |
|---|---|
| D1 Python + FastMCP, reuse core | ✅ Confirmed (FastMCP v3.2.4 / `mcp` SDK; bundled FastMCP = lean default) |
| **D2 `sqlite-vec` + one SQLite file** | ✅ **Proven on Windows** — no driver fallback needed |
| D3 Archive agent + UI | ✅ Unaffected |
| D4 Focused skills suite | ✅ Unaffected |
| D5 Stateless per call | ✅ Confirmed — enables threadpool model + later HTTP |
| **D6 `fastembed` / bge-small-en-v1.5** | ✅ **Proven on Windows** — 384-dim, ~3 ms, offline |
| D7 stdio, pluggable | ✅ Confirmed — FastMCP swaps stdio→HTTP/SSE at `mcp.run()` |

## 6. Design Deltas to Feed Back into the Spec

- **Add a `ConnectionFactory` port** — enables `load_extension`, calls `sqlite_vec.load`, returns stdlib `sqlite3` *or* `apsw`. Default stdlib.
- **Add an `Embedder` port** — fastembed singleton with a persistent `FASTEMBED_CACHE_DIR`.
- **`card_vec` schema** — metadata columns `mana_value` + `color_{w,u,b,r,g}`; note auxiliary (`+`) columns cannot be filtered.
- **Tool concurrency rule** — sync `def`; WAL; connection per thread.
- **Search tools** — `semantic_search_cards` / `find_similar_cards` over-fetch `k` then JOIN-filter; every KNN query requires `k`/`LIMIT`.
- **Operations** — WAL-checkpoint before file-copy backups; a model/dimension change ⇒ rebuild `card_vec`.

## 7. Risk Register — §10 Final Status

| §10 risk | Final status |
|---|---|
| sqlite-vec packaging on Windows / uv | 🟢 **Retired** (proven on stdlib sqlite3 / Py 3.12.13) |
| Index build time / footprint | 🟢 **Retired** (~3 ms/embed; ~92 MB raw @ 60k×384; minutes to build) |
| Embedding-text composition / weighting | 🟡 Open-low (tune via RAG eval; quantized-model recall is the variable) |
| Core / agent coupling surface | 🟡 Open-managed (incremental, behind the two ports) |

## 8. Implementation Roadmap (feeds epics & stories)

1. **Restructure & deps** — archive `src/agent`+`src/ui`→`legacy/`; add `src/mcp_server`, `src/search`; move `pydantic-ai`/`chainlit` to optional `legacy` group; add `mcp`, `sqlite-vec`, `fastembed`.
2. **Search core** — `ConnectionFactory`, `Embedder` (singleton + persistent cache), `card_vec` schema, `scripts/build_card_embeddings.py` (idempotent/incremental via content hash).
3. **MCP server** — FastMCP stdio; port existing tools; add the two search tools (over-fetch `k` → JOIN/filter); statelessness (D5).
4. **Skills suite** — orchestrator + capability skills (§7).
5. **Tests** — MCP integration (in-memory client) + RAG sanity eval.

## 9. Sources & Verification

Verified against primary documentation plus a live local spike (2026-06-20):

- **sqlite-vec:** [GitHub](https://github.com/asg017/sqlite-vec) · [Python docs](https://alexgarcia.xyz/sqlite-vec/python.html) · [metadata release](https://alexgarcia.xyz/blog/2024/sqlite-vec-metadata-release/index.html) · [v0.1.0 post](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html) · issues [#13](https://github.com/asg017/sqlite-vec/issues/13)/[#45](https://github.com/asg017/sqlite-vec/issues/45)/[#116](https://github.com/asg017/sqlite-vec/issues/116)/[#196](https://github.com/asg017/sqlite-vec/issues/196)/[#121](https://github.com/asg017/sqlite-vec/issues/121)
- **Python / SQLite:** [CPython #95656](https://github.com/python/cpython/issues/95656) · [sqlite3 docs](https://docs.python.org/3/library/sqlite3.html) · [thread-safety](https://ricardoanderegg.com/posts/python-sqlite-thread-safety/) · [WAL forum](https://sqlite.org/forum/info/461653af585fb599)
- **Driver fallbacks:** [APSW](https://rogerbinns.github.io/apsw/) · [sqlean.py](https://github.com/nalgeon/sqlean.py) · [pysqlite3](https://github.com/coleifer/pysqlite3)
- **fastembed:** [GitHub](https://github.com/qdrant/fastembed) · [PyPI](https://pypi.org/project/fastembed/) · [thread-safety #191](https://github.com/qdrant/fastembed/discussions/191) · [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5)
- **FastMCP:** [Tools docs](https://gofastmcp.com/servers/tools) · [PrefectHQ/fastmcp](https://github.com/prefecthq/fastmcp) · [official mcp SDK](https://github.com/modelcontextprotocol/python-sdk) · [sync-tool #1839](https://github.com/modelcontextprotocol/python-sdk/issues/1839)
- **Local spike (primary evidence):** CPython 3.12.13 / SQLite 3.50.4 / `uv` 0.11.7 / Windows 11 — Probe 1 (extension load + hybrid KNN) and Probe 2 (fastembed + RAG ranking), 2026-06-20.

## Technical Research Conclusion

The pivot's foundational technical bet is **validated and de-risked**. The single risk that could have invalidated a locked decision (sqlite-vec on Windows) is retired with executed evidence, and the architecture has a clear, small set of design deltas to carry forward.

**Next step:** proceed to **`[CE]` Create Epics and Stories**, carrying the six design deltas (§6) and the roadmap (§8) into the architecture/epics input.

---

**Technical Research Completion Date:** 2026-06-20
**Source Verification:** All claims cited; decision-gating claims confirmed by live spike
**Technical Confidence Level:** High — primary sources + executed empirical evidence
