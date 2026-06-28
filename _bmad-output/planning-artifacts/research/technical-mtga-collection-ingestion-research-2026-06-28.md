---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'MTG Arena collection ingestion for the MCP server (existing tooling + reverse-engineering owned-card counts from MTGA local files)'
research_goals: '(1) Find existing knowledge/tooling that programmatically exposes an MTGA player owned-card quantities — including any known MCP/reverse-engineering server. (2) If none suffices, assess feasibility of reverse-engineering owned-card counts from MTGA local files and map a concrete integration path into the Artificial-Planeswalker MCP server.'
user_name: 'Brad'
date: '2026-06-28'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-06-28
**Author:** Brad
**Research Type:** technical

---

## Research Overview

This report investigates how the Artificial-Planeswalker MCP server can learn the user's
real Magic: The Gathering Arena (MTGA) **owned-card quantities**, so deckbuilding and swap
advice can respect the actual collection. It surveys existing tooling first, then assesses
reverse-engineering MTGA's local files, and ends with a build-vs-reuse recommendation and a
concrete integration path into the project's data → logic → mcp_server architecture.

**Headline:** the intuitive plan (parse owned-card counts out of MTGA's log) is dead — Wizards
removed that data from the log in 2021 — but the feature is very achievable by consuming an existing
collector's export, and is a genuine first-mover gap (no MCP server reads an Arena collection today).
See the **Research Synthesis & Executive Summary** at the foot of this document for the full picture.

---

## Technical Research Scope Confirmation

**Research Topic:** MTGA collection ingestion for the MCP server — existing tooling vs.
reverse-engineering owned-card counts from local files

**Research Goals:**
1. Find existing knowledge/tooling that programmatically exposes an MTGA player's owned-card
   quantities — including any known MCP / reverse-engineering server (the "Laurie / Wired" lead).
2. If none suffices, assess feasibility of reverse-engineering owned-card counts from MTGA local
   files and map a concrete integration path into the Artificial-Planeswalker MCP server.

**Technical Research Scope:**

- Existing solutions & prior art — published collection-extraction tools/libraries/APIs and their ToS posture
- The data source — where MTGA stores collection/ownership data locally (logs, detailed-logs toggle, card-id DB)
- Integration approach — mapping arena_id → quantity onto the project's Scryfall schema and MCP tools
- Feasibility, fragility & risks — game-running requirement, patch fragility, ToS/account safety, refresh model
- Build-vs-reuse recommendation — concrete options with trade-offs for a future epic

**Research Methodology:**

- Current web data with rigorous source verification
- Multi-source validation for critical technical claims (log format, ToS specifics)
- Confidence-level framework for uncertain / version-fragile information
- Comprehensive technical coverage tied back to the project's actual architecture

**Scope Confirmed:** 2026-06-28

---

## Technology Stack & Landscape Analysis

> **Methodology note:** findings below come from four parallel web-research passes (existing
> tools, the local-file/log surface, the MCP ecosystem + the "Laurie/Wired" lead, and ToS +
> `arena_id` mapping). Confidence levels and source conflicts are flagged inline.

### ⭐ Headline finding — owned-card counts LEFT the log file in 2021 (HIGH confidence)

The intuitive plan ("parse `Player.log` for a `card-id → quantity` map") **no longer works.**
MTGA's `PlayerInventory.GetPlayerCardsV3` event — historically the only log source of owned-card
counts — was **removed from the log in the August 2021 client update and never replaced.** The
current log still carries decks, draft picks, match/GRE state, and currency/wildcard inventory
(`InventoryInfo` inside the `StartHook` blob: gold, gems, wildcards, vault), **but not per-card
ownership quantities.**
- Source: [Everything We Know About the MTG Arena Log File in 2026 (manasight.gg)](https://blog.manasight.gg/arena-log-format-guide/)
- Corroboration: the most actively-maintained collection tool, mtgatool, gets the collection by
  **reading the live game process's memory** (a Rust port of Unity Spy), not by parsing the log —
  [mtgatool/mtga-reader](https://github.com/mtgatool/mtga-reader).
- **Documented log-shrink trend:** Wizards has *removed* fields over time (Sep 2019 vault, May 2020
  `output_log.txt`→`Player.log` rename, Jul 2021 screen name, **Aug 2021 collection/inventory/draft
  endpoints**, Aug 2022 MMR, Jul 2024 opponent name). The log interface is contracting, not growing.
- **Conflict flagged (MEDIUM confidence on reconciliation):** Untapped.gg's help center still
  describes reading collection from `Player.log`
  ([HearthSim](https://help.hearthsim.net/en/articles/5020719-how-does-the-untapped-gg-companion-work)).
  Best reconciliation: commercial trackers run a native/Overwolf memory-reading component while
  their user-facing copy still says "we watch your log." Their exact internal mechanism is not
  publicly documented — worth treating as not-fully-confirmed.

**Consequence:** the project's framing ("reverse-engineer the collection from MTGA files") splits
into two very different sub-problems — a hard, fragile one (live owned-card counts) and an easy,
stable one (the `grpId → card` name/set database). See below.

### Existing tools that read an MTGA collection (prior art)

| Tool | How it gets the collection | Owned counts? | License / stack | Machine-readable export | Reuse value |
|---|---|---|---|---|---|
| **[frcaton/mtga-tracker-daemon](https://github.com/frcaton/mtga-tracker-daemon)** | Reads **live game memory** | ✅ Yes | GPL-3.0, C#/.NET | ✅ Local HTTP `GET /cards` → `[{grpId, owned}]` JSON | **High (reuse)** |
| **[NthPhantom10/MTGA-collection-exporter](https://github.com/NthPhantom10/MTGA-collection-exporter)** | Scans game memory (user scrolls collection first) | ✅ Yes | **MIT, Python** | ✅ writes `mtga_collection.json` (id + qty) | **High (reuse, stack-aligned)** |
| **[kelesi/mtga-utils](https://github.com/kelesi/mtga-utils)** | Log parse (legacy `GetPlayerCardsV3`) | ⚠️ Old logs only — broken post-2021 | MIT, Python | JSON + Goldfish/deckstats CSV | **Schema reference only** |
| **[17Lands client](https://github.com/rconroy293/mtga-log-client)** | Log parse → uploads to 17Lands | ❌ Draft/game data, not collection | GPL-3.0, C#/Python | No local collection export | Log-watcher pattern ref |
| **Untapped.gg Companion** | Overwolf overlay (log + likely memory) | ✅ (in-app) | Closed | None documented | Low |
| **[Razviar/mtgap](https://github.com/Razviar/mtgap) (MTGA Pro Tracker)** | Desktop, log + native component → their server | ✅ (server-side) | MIT but **archived Apr 2025** | Web account only | Low (abandoned) |
| **[mtgatool-desktop](https://github.com/mtgatool/mtgatool-desktop)** | Electron + `mtga-reader` (memory) | ✅ (collection browser) | GPLv3, TS/Electron | In-app; export unclear | Memory-read reference |

**Take:** a clean machine-readable owned-count export **does exist**, but only via **memory-reading
tools** — best two candidates: **NthPhantom10** (MIT, Python, writes a JSON file → matches our stack
and license posture) and **frcaton daemon** (GPL-3.0, .NET, exposes a live local JSON HTTP API).

### The data source(s) — where ownership actually lives now

1. **`Player.log`** — `…\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log` (prev session kept as
   `Player-prev.log`). **Reset on every launch.** Requires the in-game **Options → Account →
   "Detailed Logs (Plugin Support)"** toggle (client restart needed) for the JSON data blocks.
   Carries decks/drafts/matches/currency — **not** owned-card counts (post-2021).
   ([Wizards support](https://mtgarena-support.wizards.com/hc/en-us/articles/360000726823-Creating-Log-Files-on-PC-Mac-Steam),
   [Draftsim](https://draftsim.com/enable-detailed-logging-in-mtg-arena/))
2. **Live process memory** — the *only* current route to owned counts. Object path (mtga-reader):
   `WrapperController → InventoryManager → _inventoryServiceWrapper → Cards → _entries`. Requires the
   game **running and logged in** (collection is cached in memory; you don't strictly need to open the
   Collection screen, though NthPhantom10's tool asks you to scroll it to be safe). Fragile across Unity/Mono
   updates. ([mtgatool/mtga-reader](https://github.com/mtgatool/mtga-reader))
3. **`Raw_CardDatabase_*.mtga` — a real SQLite DB (the EASY, stable half).** In
   `…\MTGA_Data\Downloads\Raw\`. Open with `sqlite3`. `Cards` table has `GrpId`, `TitleId`,
   `ExpansionCode`, `CollectorNumber`, `Rarity`, `IsToken`; join `Cards.TitleId → Localizations_enUS.LocId`
   for printed names. Glob the filename (suffix changes per build); schema is comparatively stable.
   ([Senryoku/Draftmancer ManageCardData.py](https://github.com/Senryoku/MTGADraft/blob/master/ManageCardData.py))
   *(Sibling `data_cards_*.mtga` under `…\Downloads\Data\` is JSON, not SQLite.)*

### The join key — `arena_id` (grpId) → card identity, and the `oracle_cards` trap

- Scryfall cards carry a nullable **`arena_id`** equal to MTGA's `grpId`
  (`GET /cards/arena/{arena_id}`). *"A large percentage of cards are not available on Arena and do not
  have this ID"* — so expect partial coverage. ([Scryfall](https://scryfall.com/docs/api/cards/arena))
- **⚠️ Project-specific landmine:** `arena_id` is **per-printing**, but this project dedupes its DB on
  **`oracle_cards`** (one row per Oracle ID — see [[db-refresh-uses-oracle-cards]]). `oracle_cards`
  collapses every printing to one representative that is *frequently paper-only with no `arena_id`*, so
  it **drops most arena_ids and cannot round-trip a grpId** from a log/memory read back to a card.
  The same trap hits MTGJSON `AtomicCards` (arena id lives only on printing-level `AllPrintings`, not
  Atomic). **Fix:** build a dedicated **`arena_id → oracle_id/card` lookup from Scryfall `default_cards`**
  (or `all_cards`) as a separate join layer, keeping the existing oracle-deduped store intact.
  ([Scryfall bulk data](https://scryfall.com/docs/api/bulk-data), [MTGJSON Identifiers](https://mtgjson.com/data-models/identifiers/))
- Lightweight alternative map: **[17Lands `cards.csv`](https://17lands-public.s3.amazonaws.com/analysis_data/cards/cards.csv)**
  (`id` = grpId, name, set, rarity, color, mv) — authoritative grpId list straight from Arena logs.

### The MTG MCP ecosystem (prior art) + the "Laurie/Wired" lead

- **The "Laurie from Wired" lead resolves to [LaurieWired](https://x.com/lauriewired/status/1904582573046878333)
  (Laurie Kirk, a Microsoft security researcher) and her project [GhidraMCP](https://github.com/LaurieWired/GhidraMCP)** —
  an MCP server (~9.4k★, Apache-2.0) that lets an LLM drive **Ghidra** to reverse-engineer **native
  binaries**. Impressive, but **the wrong tool here (LOW relevance):** MTGA is Unity C# (Mono/IL2CPP),
  which is handled by Il2CppInspector/dnSpy, not Ghidra — and we don't need binary RE at all, since the
  data is reachable via documented log/memory/SQLite surfaces. Mentioned because it was Brad's lead; it
  validates "RE-via-MCP" as a concept but doesn't apply to the collection problem.
- **Existing MTG MCP servers are all Scryfall / deck-state oriented — NONE read a live MTGA collection.**
  Most comprehensive prior art: **[j4th/mtg-mcp-server](https://github.com/j4th/mtg-mcp-server)** (69 tools,
  aggregates Scryfall/EDHREC/17Lands/Moxfield/Goldfish) and **[bmurdock/scryfall-mcp](https://github.com/bmurdock/scryfall-mcp)**
  (14 tools incl. deckbuilding). **→ The "MCP that knows your Arena collection" is a genuine open gap**
  Artificial-Planeswalker would be first to fill.

### ToS / account-safety posture (informs the build decision)

- **Read-only local LOG parsing = LOW risk.** No documented bans of passive log-readers; WotC ships the
  "Detailed Logs (Plugin Support)" toggle and a support workflow around it; the log only contains the
  player's own already-visible data. *But* this is tolerance/precedent, **not** contractual permission —
  WotC's Terms broadly prohibit "third-party programs or tools not expressly authorized."
- **Memory-reading sits closer to the line.** It's how owned counts are obtained today, and no bans are
  documented for the popular memory-readers, but it's nearer the ToS prohibitions on tools that interact
  with the game process than passive log reading is. This is a real decision input for Step 6.
  ([WotC Terms](https://company.wizards.com/en/legal/terms), [mtga-log-client disclaimer](https://github.com/rconroy293/mtga-log-client))

### Confidence & open questions to carry forward

- **HIGH:** collection counts are not in the current log; `Raw_CardDatabase` is SQLite; Scryfall `arena_id`
  join + the `oracle_cards` trap; no existing MCP reads an Arena collection.
- **MEDIUM / verify-yourself:** exact internal mechanism of the *commercial* trackers; whether frcaton's
  June-2024 memory offsets still match the current 2026 client (test before committing); whether a
  user-friendly "snapshot export" UX is acceptable vs. wanting live sync.

## Integration Patterns Analysis

How the collection data crosses from "outside the sandbox" (MTGA on the user's machine) into the
project's `data → logic → mcp_server` layers. Designed against the project's existing conventions
(FastMCP stdio, **sync `def` tools** on a threadpool with **per-thread SQLite + WAL**, repositories
return Pydantic schemas, `oracle_cards` dedup, `report_bug` untrusted-input rule, **no per-session
server state — D5**).

### A. The ingestion boundary — three interoperability patterns

The MCP server cannot read MTGA's memory itself (and shouldn't — see Step 6 ToS). It consumes the
output of an **external collector**. Three patterns, in increasing coupling:

| Pattern | Mechanism | Pros | Cons | Verdict |
|---|---|---|---|---|
| **P1 — File-drop snapshot** | User runs a collector (e.g. NthPhantom10 exporter) → drops `mtga_collection.json`/CSV → an MCP `import_collection(path)` tool reads it | Zero coupling to a running game; works offline; trivially testable; matches the project's existing **file-based, on-demand** ethos; no extra runtime process owned by us | Manual, point-in-time (stale until re-run); user must install a collector | ✅ **Recommended for v1** |
| **P2 — Local-HTTP poll** | frcaton daemon runs on `localhost:9000`; an MCP `refresh_collection()` tool does `GET /cards` → `[{grpId, owned}]` | One-click "refresh"; live-ish; clean JSON contract | Requires the daemon (GPL-3.0, .NET) running **and** MTGA open+logged-in; a 2nd background process; daemon offsets may lag client patches | ◻ Optional "live" upgrade |
| **P3 — Subprocess shell-out** | MCP tool spawns the collector on demand | Single user action | We'd own launching a memory-reader (ToS-adjacent, fragile, blocks the sync tool thread); platform-specific | ❌ Avoid |

**Recommendation:** ship **P1** first (decoupled, safe, testable), with the **internal contract
designed so P2 can be added later without touching the schema or the consuming tools.**

### B. The canonical internal data contract (normalize at the edge)

The three real-world sources disagree on shape, so normalize all of them to **one internal record**
at the import boundary:

- frcaton daemon `/cards`: `{ "grpId": Number, "owned": Number }` (id only — we resolve identity)
  ([daemon README](https://github.com/frcaton/mtga-tracker-daemon/blob/master/README.md))
- NthPhantom10 export: `{ "count", "name", "set", "cn" }` (identity pre-resolved)
  ([exporter](https://github.com/NthPhantom10/MTGA-collection-exporter))
- ManaBox CSV (de-facto interchange standard): `Name, Set code, Collector number, Quantity, Scryfall ID, …`
  ([ManaBox guide](https://www.manabox.app/guides/collection/import-export/)) — also used as the named
  import preset by Archidekt/Mana Pool, so adopting it gives us free interop with the wider MTG ecosystem.

**Internal `CollectionEntry` (proposed):**
```
arena_id: int | None      # grpId — the primary join key when present
scryfall_id: str | None   # when source provides it (ManaBox)
name/set/collector_no: str | None   # fallback identity for resolution
owned: int                # 0–4 (basics uncapped)
```
**Identity-resolution precedence** (mirrors how all importers do it): `arena_id` → `scryfall_id` →
`set+collector_no` → `name+set`. Stamp every import with a **`source` + `snapshot_at` (UTC, tz-aware
per the project rule)** so staleness is queryable.

### C. The join/transform layer — `arena_id → oracle_id` (resolves the Step-2 landmine)

This is the crux. `arena_id` is **per-printing**; the project's card store is **`oracle_cards`-deduped**
([[db-refresh-uses-oracle-cards]]), which discards most `arena_id`s. So we cannot join collection rows
to the existing card table directly. Pattern:

1. Build a dedicated **`arena_card_map` table** (`arena_id PK, oracle_id, set, collector_no, name`) from
   Scryfall **`default_cards`** bulk (the printing-level file that *retains* `arena_id`) — **not**
   `oracle_cards`. A one-shot builder script, same family as `build_card_embeddings.py`, run/refreshed
   alongside the DB. ([Scryfall bulk data](https://scryfall.com/docs/api/bulk-data))
2. Import resolves each `CollectionEntry.arena_id → oracle_id` via `arena_card_map`, then **aggregates
   owned counts up to the oracle level** (sum across alt-art/reprint grpIds of the same card) so
   downstream deckbuilding — which thinks in oracle cards — gets "I own N of *this card*."
3. Keep `arena_card_map` separate from the oracle store; the existing dedup logic is untouched.

### D. Persistence target (new `collection` table, repository pattern)

- New table `collection_owned` (`oracle_id` or `card_id` FK, `owned` int, `snapshot_at`, `source`) +
  the `arena_card_map` lookup. Follow the project's **hand-written migration script in `scripts/`**
  convention (no Alembic) and `Base.metadata.create_all`.
- New `CollectionRepository` in `src/data` that **returns Pydantic schemas, never ORM models**, with
  the standard write discipline (commit+refresh on success, rollback on `IntegrityError`).
- This is a **single-user** dataset (Brad's own collection) — no per-user partitioning needed for v1,
  consistent with the local-first design.

### E. The MCP surface — Tools (+ optional Resource), and how existing tools consume it

Per the MCP spec, a user dataset can be exposed as a read-only **Resource** (app/user-attached
context) and/or via **Tools** (model-driven queries + all mutations); mutations *must* be Tools, and
Claude hosts consume **Tools** far more reliably than Resources today
([MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts)). Proposed surface:

- **`import_collection(path|payload, source)`** (mutation Tool) — P1 ingest; treats the file as
  **untrusted input** (validate/sanitize like `report_bug`), normalizes (B), resolves (C), upserts (D),
  returns a summary `{cards_imported, unmatched, snapshot_at}`.
- **`refresh_collection()`** (mutation Tool, P2/later) — pulls the local daemon `GET /cards`.
- **`get_collection_summary()` / `query_owned(card or filter)`** (read Tools) — "how many of X do I own",
  counts by set/rarity, totals. **Stateless** (D5): no active-collection session state; the data lives in
  the DB, tools read it.
- **Optional `collection://owned` Resource** — for hosts/users that want to attach the whole collection
  as context; thin read-only view over the same table.
- **Consumption by existing deckbuilding tools (the actual payoff):** keep them **stateless** — add an
  **opt-in `respect_collection: bool` parameter** (default off to preserve current behavior). When true,
  the analyzer/synergy/swap tools left-join candidate cards against `collection_owned` and annotate each
  with `owned` / `craftable` (wildcard) status, so swap suggestions can prefer **cards Brad already owns**.
  This fits the existing "swaps with a concrete reason" model and the **deck_id-as-parameter** pattern —
  no new server state.

### F. Refresh / sync protocol decision

- **v1 = manual snapshot** (P1): explicit `import_collection`; `snapshot_at` surfaces staleness; the
  model can warn "your collection snapshot is 12 days old." Simple, robust, testable. ✅
- **Later = live-ish** (P2): `refresh_collection` against the daemon; or a file-watcher on the export.
  The contract in (B)/(C)/(D) is identical, so this is an additive upgrade, not a rewrite.

### G. Security / trust boundary

- Imported files are **untrusted user input** — apply the project's `report_bug` posture: validate
  types, cap sizes, never `eval`, parameterized SQL only. An `arena_id` is just an int; a malformed
  CSV must fail safe.
- The collector tools live **outside** our process. We never bundle/launch a memory-reader in v1
  (keeps us clear of the ToS gray area — Step 6), we only **consume a file the user produced**.

**Confidence:** HIGH on the data contracts (read from source/READMEs) and the layer mapping (project
conventions). MEDIUM on the eventual P2 daemon path (depends on the daemon staying current with MTGA).

## Architectural Patterns and Design

This step fixes the *shape* of the solution and the load-bearing design decisions, each tied to an
established pattern and to an existing project convention so the build stays idiomatic.

### System architecture pattern — out-of-process collector behind an Anti-Corruption Layer

MTGA's internal model (`grpId`, memory layout, log dialect) is a **foreign, volatile bounded
context**. The right defensive shape is an **Anti-Corruption Layer (ACL)** at the import boundary:
adapter + translation logic that converts whatever the collector emits (`{grpId, owned}`, ManaBox
CSV, `{count,name,set,cn}`) into our domain `CollectionEntry`, then into oracle-level owned counts —
so MTGA concepts never leak into `src/data`/`src/logic`.
- The ACL *is* the normalize-resolve layer from Step 3 (B + C); naming it makes its job explicit:
  **keep `src/logic` MTGA-agnostic.** The collector is an external system; we own only the translator.
- Pattern refs: [Azure — Anti-Corruption Layer](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer),
  [DDD ACL (DevIQ)](https://deviq.com/domain-driven-design/anti-corruption-layer/). Implemented with the
  Adapter/Facade pair the project already favors (repositories as the façade over storage).

### Ingestion architecture — batch snapshot (pull-based), not streaming

Choose **batch/snapshot ingestion** over an event stream. A player's collection changes *slowly*
(packs, drafts, wildcard crafts — not per-second), it's a **single-user desktop** context, and
streaming would demand a 24/7 process and offset-tracking for no latency benefit
([batch vs streaming ingestion — Starburst](https://www.starburst.io/blog/data-ingestion/)).
- v1 is a **pull**: user (or model) triggers `import_collection`; the system reads a point-in-time
  snapshot. **Freshness is modeled, not chased** — every row carries `snapshot_at`, so the model can
  say "your snapshot is N days old" instead of silently trusting stale data.
- P2 (daemon poll) is still pull-based, just lower-friction — **same ingestion semantics**, so it's an
  additive upgrade, never a re-architecture. We explicitly do **not** adopt CDC/streaming.

### Data architecture — bounded separation + idempotent build prerequisite

- **Two new tables, deliberately separated** from the oracle store: `arena_card_map`
  (printing-level: `arena_id → oracle_id/set/cn`) and `collection_owned` (oracle-level counts +
  `snapshot_at`/`source`). This keeps the **printing-vs-oracle impedance mismatch contained** in one
  translation table instead of polluting the deduped card model (the Step-2 landmine, isolated).
- **`arena_card_map` is a build prerequisite, not committed** — built from Scryfall `default_cards`
  by an **idempotent/incremental** script, exactly mirroring the established `card_vec` /
  `build_card_embeddings.py` convention. A fresh checkout has no map; the builder creates it.
- Reuse the existing `ConnectionFactory`/per-thread-SQLite-+-WAL plumbing; no second datastore.

### Resilience pattern — graceful "unavailable" status (project-native)

The project already has the right failure idiom: semantic-search tools return
`status="index_unavailable"` with a build hint rather than a raw `OperationalError`. **Reuse it.**
- If no snapshot has been imported, collection-aware tools return `status="collection_unavailable"`
  with an import hint — **never an exception**, and **deckbuilding still works** (the
  `respect_collection` flag simply no-ops). The collection is an *enhancement*, never a hard dependency.
- Degradation ladder: no collection → ignore ownership; collection present but a card's `arena_id`
  unmatched → treat as unknown/own-0 and **report the unmatched set** (no silent truncation — the
  project's "log what was dropped" rule).

### Integration / boundary placement — capability-as-tool, not skill

Per the locked Phase-2 decision to **build capability-as-tool, not skill**
([[epic-3-retro-phase2-gate]]): ingestion, the join, and queries live as **MCP tools + a
`CollectionRepository`** in the server/data layers. The product **skills** (`magic-deckbuilding`,
`synergy-discovery`, …) stay prompt-side and merely *consume* the new tool output via the
`respect_collection` flag. This preserves the strict layer direction and the stateless-tool contract
(D5) — the collection lives in the DB, tools read it; no per-session "active collection" state.

### Security / trust architecture

- **Trust boundary sits at the file import.** The memory-reader/collector runs in the *user's* trust
  domain, fully outside our process — we never spawn it (v1), never inject, never touch the game.
  We ingest an artifact the user chose to produce.
- Imported payloads are **untrusted input** (the `report_bug` posture): size caps, type validation,
  parameterized SQL, no `eval`. A hostile CSV fails safe and reports, it doesn't corrupt the DB.

### Deployment / operations architecture

- **Local-first, offline, zero new services for v1.** One SQLite file (WAL), one extra builder script,
  the same MCP stdio process. No network egress except the one-shot Scryfall bulk fetch the project
  already performs for card data.
- P2's daemon is an **optional sidecar** the user opts into; our process degrades cleanly when it's
  absent (the resilience pattern above). The MCPB bundle/first-run-init story
  ([[mcpb-claude-desktop-debugging]]) would document the collector as an optional external step.

### Failure-mode → architectural-response summary

| Failure | Architectural response |
|---|---|
| No collection ever imported | `status="collection_unavailable"` + hint; deckbuilding unaffected |
| Snapshot stale | `snapshot_at` surfaced; model warns; never silently trusted |
| `arena_id` unmatched (Alchemy/rebalanced "A-" cards, tokens, brand-new set) | own-0 + **report unmatched count**; refresh `arena_card_map` from latest `default_cards` |
| Collector/daemon absent or offsets stale (post-patch) | P2 tool returns graceful error; fall back to P1 file import |
| Malformed/hostile import file | ACL validation rejects, fails safe, reports |

**Confidence:** HIGH — every choice maps to an existing project pattern (graceful-status, idempotent
builder, repository/ACL, capability-as-tool, untrusted-input) plus two well-established external
patterns (ACL, batch-pull ingestion). The only externally-dependent risk (P2 daemon currency) is
isolated behind the optional-sidecar boundary.

## Implementation Approaches and Technology Adoption

Concrete build plan, sized and sequenced. The guiding principle (matching the project's RAG
de-risk discipline, [[rag-stack-derisk-complete]]): **prove the riskiest external assumption with a
throwaway spike before writing any repo code.**

### Step 0 — De-risk spike (½ day, GO/NO-GO) — DO THIS FIRST

The one assumption that can sink the whole feature: *can a collector actually produce a usable
owned-count snapshot from Brad's live 2026 MTGA client?* (memory offsets in the public tools date to
2024). Spike:
1. Install **NthPhantom10/MTGA-collection-exporter** (MIT, Python) **or** the frcaton daemon; run it
   against the live client; capture `mtga_collection.json` / `GET /cards`.
2. Eyeball ~10 known-owned cards (e.g. "I have 4× [staple], 1× [mythic]") against the output.
3. Confirm the `grpId`s resolve against Scryfall `arena_id`.

**GO** → build Phase A. **NO-GO** (offsets stale) → fall back to manual **ManaBox-CSV-only** import
(user exports from any working tracker), which needs no live memory read. Either way the repo work is
unchanged — only the *source* of the file differs. This keeps the fragile part outside the GO/NO-GO
for the actual feature.

### Adoption strategy — incremental, behind a flag (no big-bang)

Ship read-path first, integrate into deckbuilding second, live-sync last. The
`respect_collection` flag **defaults off**, so existing tool behavior is untouched until the data is
proven — a classic strangler-free additive rollout. No migration of existing data; purely additive
tables.

### Phased roadmap & effort

| Phase | Scope | Key artifacts | Effort |
|---|---|---|---|
| **0. Spike** | Validate a collector on the live client | (throwaway) | **½ day** |
| **A. Read path (MVP)** | Ingest + resolve + query owned counts | `scripts/build_arena_card_map.py` (stream `default_cards` via **ijson** — the project's existing pattern — filter non-null `arena_id`); `scripts/migrate_add_collection.py` (2 tables); `CollectionRepository`; `import_collection` (ManaBox CSV + NthPhantom JSON + daemon JSON) & `get_collection_summary`/`query_owned` MCP tools; `collection_unavailable` graceful status; unit+integration tests | **~2–3 days** |
| **B. Deckbuilding integration** | Ownership-aware advice | `respect_collection: bool` on analyze/synergy/swap tools; annotate candidates `owned`/missing; live smoke via skills | **~1–2 days** |
| **B-stretch. Craftable** | Wildcard-aware "you can craft this" | add wildcard-count source (log `StartHook.InventoryInfo` — gold/gems/**wildcards**/vault — a *separate* read from owned counts) + missing-copy math by rarity | **~1–2 days** |
| **C. Live-ish sync (optional)** | One-click refresh | `refresh_collection` → frcaton daemon `GET /cards`; staleness UX | **~1 day** |

**MVP = Phase 0 + A + B (~1 week).** That already closes the usability gap ("advice respects what I
own"). B-stretch/C are additive.

### Technology / stack choices (reuse the project's existing tools)

- **`default_cards` (525 MB) — not `oracle_cards` (170 MB) — for the map builder**, streamed with
  **`ijson`** (already a project dep for Scryfall import) so the 525 MB never lands fully in memory;
  output table is tiny (only Arena printings). `all_cards` (2.4 GB) is unnecessary.
  ([Scryfall bulk-data](https://scryfall.com/docs/api/bulk-data), sizes verified via
  `api.scryfall.com/bulk-data` 2026-06-28.)
- **Canonical import format = ManaBox CSV** (Step 3): adopting it means *any* tracker that exports
  ManaBox (Archidekt, Mana Pool, …) becomes a valid source — not just MTGA memory-readers. The
  collector becomes pluggable.
- **No new runtime deps for Phase A** — stdlib `csv`/`json`, existing SQLAlchemy/SQLite/ijson. The
  daemon path (C) adds only an `httpx` localhost call (`httpx` already a dep).

### Testing & QA (project conventions)

- **Unit** (`tests/unit/...`, no I/O): the ACL normalize/resolve — feed sample daemon `{grpId,owned}`,
  ManaBox CSV, and NthPhantom JSON fixtures → assert one canonical `CollectionEntry` shape and correct
  `arena_id→oracle_id` aggregation (sum across reprint grpIds).
- **Integration** (`tests/integration/test_mcp_tools.py`, in-process MCP client): drive
  `import_collection` then `query_owned`/`get_collection_summary`; assert `collection_unavailable`
  before import; assert unmatched-`arena_id` reporting.
- **Resolution sanity eval** (mirrors the RAG sanity guard): a tiny fixture of known `grpId → card`
  pairs to catch a silently-broken map after a Scryfall refresh.
- **mypy --strict + ruff + pre-commit** as always; mark any Scryfall-network test `integration`.

### Dev workflow, cost & footprint

- Feature branch off `master` → PR (this is *code*, so branch/PR per [[commit-small-docs-to-main]]).
  Conventional Commits; hand-written migration script (no Alembic); `uv run` for everything.
- **Cost ≈ zero, offline:** one 525 MB Scryfall download (cacheable, same cadence as today's card
  refresh); resulting `arena_card_map` is small; no LLM/API spend; no 24/7 process.

### Risk assessment & mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Collector offsets stale on 2026 client | Med | Step-0 spike gates it; ManaBox-CSV fallback needs no memory read |
| `arena_id` gaps (Alchemy `A-`/rebalanced, tokens, brand-new set) | Med | own-0 + **report unmatched**; refresh map from latest `default_cards`; Alchemy cards have their own arena printings so most resolve |
| oracle aggregation wrong (double-count reprints) | Low | unit test summing multiple grpIds → one oracle card |
| "Craftable" needs wildcards (not in card endpoint) | Med | scoped OUT of MVP; B-stretch reads log `InventoryInfo` separately ([wildcards are a distinct inventory facet](https://draftsim.com/mtg-arena-wildcards/)) |
| ToS posture | Low | v1 consumes a user-produced file only; we never read game memory ourselves (Step 6) |

## Technical Research Recommendations

### Implementation Roadmap
**Spike (½ d) → Phase A read path (2–3 d) → Phase B deckbuilding integration (1–2 d)** = shippable
MVP in ~1 week that makes every deckbuilding tool collection-aware. Then optionally B-stretch
(craftable) and C (live refresh). Build it as a **future epic** (Phase-2 style), capability-as-tool.

### Technology Stack Recommendations
Reuse everything: `ijson` streaming of **`default_cards`**, SQLite/SQLAlchemy + per-thread/WAL,
FastMCP sync tools, repository+Pydantic. **Adopt ManaBox CSV as the import contract** to decouple from
any single collector. Add nothing new for Phase A; `httpx` localhost only if/when C lands.

### Skill Development Requirements
**No new product skills.** Existing skills (`magic-deckbuilding`, `synergy-discovery`,
`mana-curve-analysis`, `format-legality`) consume the new tools via `respect_collection`. The only new
human step is documenting "how to produce a collection snapshot" (the optional collector) in the
MCPB/first-run docs.

### Success Metrics & KPIs
- **Resolution rate:** ≥95% of imported `grpId`s resolve to an oracle card (track unmatched).
- **Correctness:** swap/synergy suggestions under `respect_collection=true` never recommend a card the
  user owns 0 of without flagging it as "needs crafting".
- **Freshness honesty:** every collection-aware answer can cite `snapshot_at`; staleness > N days is
  surfaced, never hidden.
- **Zero-regression:** with the flag off, existing tool outputs are byte-identical to today.

---

# Closing the Collection Gap: Bringing a Player's MTGA Card Ownership Into the MCP Server — Research Synthesis

## Executive Summary

Artificial-Planeswalker gives sharp deckbuilding advice that is, today, **collection-blind** — it
will happily suggest a four-of the user can't field. Closing that gap means teaching the MCP server
how many of each card the user owns in MTG Arena. This research set out to answer two questions: does
a solution already exist, and if not, can ownership be reverse-engineered from MTGA's local files.

The investigation surfaced **one finding that inverts the original premise**: owned-card *quantities*
are **no longer in MTGA's log file**. Wizards removed the `PlayerInventory.GetPlayerCardsV3` log event
in **August 2021** and never replaced it — part of a documented multi-year trend of *shrinking* the
log. So "reverse-engineer the counts from the files" is a dead end for the log; the only current
source of live owned-counts is **reading the running game's process memory**. The card *names*,
however, remain trivially available: the game ships a plain **SQLite** card database
(`Raw_CardDatabase_*.mtga`). The problem thus cleanly splits into a **hard, fragile half** (live owned
counts) and an **easy, stable half** (id → card identity).

The strategic good news is that **the hard half is already solved by others, and the gap is real**.
Two open-source tools (one MIT/Python, one GPL/.NET) already read game memory and export owned counts
as JSON, and the de-facto **ManaBox CSV** interchange format lets *any* mainstream collection tracker
serve as a source. Meanwhile, **no existing MCP server anywhere reads a live Arena collection** —
making this a genuine first-mover capability for the project. The recommended path keeps
Artificial-Planeswalker entirely clear of the ToS gray area: **consume a collection file the user
produced** (we never touch the game), normalize it behind an Anti-Corruption Layer, resolve ids
through a dedicated `arena_card_map`, and expose ownership to the existing deckbuilding tools through
an opt-in flag. It is an ~1-week, zero-new-dependency, fully-offline MVP.

**Key Technical Findings:**
- **The log no longer contains owned-card counts** (removed Aug 2021; HIGH confidence, multi-source).
  The live-memory read is the only current route to quantities; the `grpId→name` map is an easy SQLite lookup.
- **The hard part is pre-built:** [NthPhantom10 exporter](https://github.com/NthPhantom10/MTGA-collection-exporter)
  (MIT, Python, JSON) and [frcaton daemon](https://github.com/frcaton/mtga-tracker-daemon) (GPL, local HTTP `/cards`) already export owned counts.
- **Genuine open gap:** every existing MTG MCP server is Scryfall/deck-state oriented; **none reads an Arena collection.**
- **The "Laurie/Wired" lead is [GhidraMCP](https://github.com/LaurieWired/GhidraMCP)** — real and notable, but the *wrong tool* (it drives Ghidra on native binaries; MTGA is Unity C# and its data is already reachable without binary RE).
- **Project landmine, solved:** `arena_id` is per-printing; the project's `oracle_cards` dedup discards it → build a separate `arena_card_map` from Scryfall **`default_cards`** (525 MB, streamed via the existing `ijson`).
- **ToS-clean path exists:** passive consumption of a user-produced file carries low risk; we never read game memory ourselves.

**Technical Recommendations (top 5):**
1. **Spike before building** (½ day): prove a collector yields a valid owned-count snapshot on the live 2026 client — GO/NO-GO. Fallback if NO-GO: ManaBox-CSV import (no memory read needed).
2. **Build the read path** (Phase A, 2–3 days): `arena_card_map` builder + 2-table migration + `CollectionRepository` + `import_collection`/`query_owned` tools + graceful `collection_unavailable` status.
3. **Adopt ManaBox CSV as the import contract** to decouple from any single collector and gain ecosystem interop for free.
4. **Integrate via an opt-in `respect_collection` flag** (zero-regression) as **capability-as-tool**; existing skills merely consume it.
5. **Ship file-import-only for v1** (ToS-clean); defer daemon live-sync (Phase C) and wildcard-aware "craftable" (B-stretch, a *separate* data source) as additive phases.

## Table of Contents

1. Research Overview & Scope *(top of document)*
2. Technology Stack & Landscape Analysis — existing tools, data sources, the join key, the MCP ecosystem
3. Integration Patterns Analysis — ingestion boundary, data contracts, the `arena_card_map` join, MCP surface
4. Architectural Patterns & Design — ACL, batch-snapshot, graceful degradation, capability-as-tool, trust boundary
5. Implementation Approaches — de-risk spike, phased roadmap, testing, risk table, recommendations
6. Research Synthesis & Executive Summary *(this section)* — findings, recommendations, open decisions, sources

## Research Goals — achieved

> **Goal 1 — find existing knowledge/tooling (incl. the "Laurie/Wired" lead).** ✅ Done. Mapped the
> full tool landscape and the data-source reality; resolved the lead to GhidraMCP and assessed it as
> not-applicable; confirmed no MCP reads an Arena collection.
>
> **Goal 2 — assess reverse-engineering from MTGA files + map an integration path.** ✅ Done. Established
> that counts left the log (memory is the only live source) while the id→card DB is easy SQLite;
> delivered a concrete, project-idiomatic integration design and a sized, phased build plan.

## Open decisions for Brad (to tee up the future epic)

These are product/comfort calls the research can't make for you:

1. **Source of truth:** accept a **live memory-reader** (best UX, slightly closer to the ToS line) *or*
   **CSV-only import** (maximally safe, more manual)? — *Recommendation: support CSV import as the contract; treat the memory-reader as an optional convenience the user installs.*
2. **Scope of "craftable":** owned-only MVP, or include **wildcard-aware** "you can craft this"? (needs a second data source). — *Recommendation: owned-only MVP; craftable as B-stretch.*
3. **Live sync timing:** daemon `refresh_collection` in the MVP or later? — *Recommendation: later (Phase C).*
4. **Single-user assumption** (Brad's own collection, no multi-account) for v1? — *Recommendation: yes.*

## Decision Log

**2026-06-28 — Consume-output, pivot-by-adapter (decided with Brad).**
- **Decision:** Do **not** port memory-reading into our codebase. **Consume an external collector's
  output.** v1 source = **NthPhantom10/MTGA-collection-exporter** (MIT, clean JSON, stack-aligned);
  documented fallbacks = frcaton daemon + *any* ManaBox-CSV exporter.
- **Rationale (the staleness reckoning):** the memory-offset fragility is unavoidable and inherited
  *either way* — owning it doesn't remove it. Consuming output makes that staleness **survivable**
  (graceful `collection_unavailable` degraded mode, deckbuilding unaffected) and **swappable** (CSV
  contract → replace the supplier without touching our code), instead of **fatal + ours** (a red build
  we must personally RE every MTGA patch). Pivot only if/when the chosen collector dies.
- **Load-bearing constraint (do NOT cut):** build to the **canonical `CollectionEntry` contract /
  ManaBox-CSV**, never to one tool's exact format. This is what keeps "pivot later" a ~20-line adapter
  swap rather than a refactor — it *is* the insurance the consume-output choice depends on.
- **Spike reframed:** Step-0 must answer **"is there a *maintained* collector with a *consumable*
  export?"** (not merely "does it run on the 2026 client"). If the whole supplier pool is abandoned,
  re-open the build-vs-own question and scope the feature as explicitly best-effort/manual.

## Future outlook

- **Near-term:** because the log keeps shrinking, expect the *memory-read* route to remain the only
  live source; insulating against it via the ManaBox-CSV contract is the durable hedge.
- **Medium-term:** a working `arena_card_map` + ownership layer is reusable for adjacent features —
  "build me a deck I can play *right now*", budget/wildcard-aware suggestions, and collection-completion
  nudges — and pairs naturally with the planned Arena import/export work ([[arena-import-export-research]]).
- **Ecosystem:** filling the "MCP that knows your collection" gap is a differentiator worth noting in
  the public release ([[public-release-strategy]]).

## Methodology & source verification

Five parallel/targeted web-research passes (existing tools; the local-file/log surface; the MCP
ecosystem + the Laurie lead; ToS + `arena_id` mapping; data contracts), each cited inline, with
confidence levels and source conflicts flagged. Live verification of Scryfall bulk sizes
(`api.scryfall.com/bulk-data`, 2026-06-28). **Confidence: HIGH** on the load-bearing facts (collection
absent from log; SQLite card DB; `arena_id`/`oracle_cards` trap; no existing collection-MCP), **MEDIUM**
on version-fragile externals (commercial trackers' internals; whether 2024-era memory offsets still
match the current client — explicitly gated by the Step-0 spike).

**Primary sources:**
- Log format / collection removed: [manasight 2026 log guide](https://blog.manasight.gg/arena-log-format-guide/) · [Wizards: Creating Log Files](https://mtgarena-support.wizards.com/hc/en-us/articles/360000726823-Creating-Log-Files-on-PC-Mac-Steam) · [Detailed Logs (Draftsim)](https://draftsim.com/enable-detailed-logging-in-mtg-arena/)
- Collectors / memory read: [NthPhantom10 exporter](https://github.com/NthPhantom10/MTGA-collection-exporter) · [frcaton daemon](https://github.com/frcaton/mtga-tracker-daemon) · [mtgatool/mtga-reader](https://github.com/mtgatool/mtga-reader) · [kelesi/mtga-utils](https://github.com/kelesi/mtga-utils)
- Card DB (SQLite): [Senryoku/Draftmancer ManageCardData.py](https://github.com/Senryoku/MTGADraft/blob/master/ManageCardData.py)
- Join key / bulk: [Scryfall arena_id](https://scryfall.com/docs/api/cards/arena) · [Scryfall bulk data](https://scryfall.com/docs/api/bulk-data) · [MTGJSON Identifiers](https://mtgjson.com/data-models/identifiers/) · [17Lands cards.csv](https://17lands-public.s3.amazonaws.com/analysis_data/cards/cards.csv)
- The lead + MCP ecosystem: [GhidraMCP](https://github.com/LaurieWired/GhidraMCP) · [LaurieWired announcement](https://x.com/lauriewired/status/1904582573046878333) · [j4th/mtg-mcp-server](https://github.com/j4th/mtg-mcp-server) · [bmurdock/scryfall-mcp](https://github.com/bmurdock/scryfall-mcp)
- Contracts / patterns: [ManaBox import/export](https://www.manabox.app/guides/collection/import-export/) · [Moxfield import](https://moxfield.com/help/importing-collection) · [MCP server concepts](https://modelcontextprotocol.io/docs/learn/server-concepts) · [Azure ACL pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer) · [batch vs streaming ingestion](https://www.starburst.io/blog/data-ingestion/)
- ToS: [WotC Terms](https://company.wizards.com/en/legal/terms) · [17Lands mtga-log-client](https://github.com/rconroy293/mtga-log-client)

## Conclusion & next steps

The usability gap is real, well-understood, and very closable — just not the way it first appears.
Owned-card *counts* must come from a live collector (memory), not the log; everything else maps
cleanly onto the project's existing patterns. The single most valuable next action is the **½-day
Step-0 spike** to confirm a collector works on the current client. If GO, this becomes a tidy ~1-week
Phase-2-style epic; if NO-GO, the ManaBox-CSV fallback still delivers the feature with more manual
effort. Either way, Artificial-Planeswalker would be the **first MCP server to make an LLM aware of a
player's real Arena collection.**

**Technical Research Completion Date:** 2026-06-28
**Source Verification:** all load-bearing claims cited with current sources
**Technical Confidence Level:** High — multiple independent sources; version-fragile externals flagged and gated by spike

