---
title: 'Codebase research: codebase architecture'
type: codebase
ask: |-
  Step 1 (architecture pass) of review-codebase-2026-11. How far has the code drifted from
  docs/architecture.md and the AD-n decisions in the 2026-07-25 architecture spine? (1) Where are
  the layer boundaries bent (data, then logic, then mcp_server; src/data and src/logic
  framework-free)? (2) Where are AD-2, AD-3, stateless tools and the frozen viewer (AD-15) bent?
  (3) Where do the MCP tools, the companion backend and the UI duplicate logic (status
  vocabularies, card resolution, formatting, validation)? (4) What are the main performance risks
  (database access, event-loop blocking, sqlite-vec, the companion image path, UI request and
  render patterns)? Rank findings by impact, each with cost today, what fixing buys, and width.
  Do not re-raise what the 2026-09-03 audit or the 2026-09-06 quality review fixed.
repository: 'C:/Users/Sathias/Projects/Artificial-Planeswalker'
commit: 'ee0263d652a46f021515860bbc2a19e3dac60eed'
branch: 'master'
status: complete
validation: 'normal'
claims: {verified: 27, disputed: 1}
created: '2026-11-07'
updated: '2026-11-07'
---

# Codebase research: codebase architecture

The architectural rules hold. No import goes the wrong way across the layers. Nothing under
`src/companion/` writes to the database. The MCP server imports nothing from `src/companion/app/`
except through the one documented exemption, and no tool keeps per-session state. The drift is in
three other places:

- **The same card statistic is computed several ways.** Land count, mana-value buckets and colour
  counts each have more than one implementation across `src/logic`, `src/viewer` and `ui/src`, and
  they give different answers for the same deck. One copy-limit rule is wrong.
- **Two earlier fixes stopped short.** The NOCASE name index (#108) never reached
  `find_similar`. The `list_deck_summaries` fast path (#109) never reached the MCP `list_decks`
  tool.
- **The companion image route does more database work than it needs.** Every image request runs a
  readiness probe and keeps a pooled connection checked out, including while it waits in the
  CDN pacer.

## How this was researched

- **Commit:** every claim is read at `ee0263d`. The only commit after it (`06752d6`) adds the
  review plan and changes no code.
- **Who read what:** three locators, six analyzers (Q5 to Q10), one historian and two verifiers
  read the code through git. Q1 to Q4 are answered from the locator digests plus one direct check.
- **Verification:** 28 load-bearing claims went to the verifiers. 27 were verified, and 1 (ref 23)
  was disputed on scope only.
- **Limits:**
  - The plan gate was not held interactively. The session was flagged non-interactive and the ask
    came as a bounded list, so the brief's ten questions ran as drafted.
  - The research firewall was only partly in force. Subagent prompts carried only the questions,
    but the subagents loaded `AGENTS.md`, which states the architectural rules.
- **Departure from the template:** the codebase template asks for no recommendations. This report
  adds `## Findings ranked by impact` because the ask requested costs and fixes. Every line in that
  section rests on a cited claim from the question sections.

## Questions

1. **What touches X:** the imports of `src/data`, `src/logic` and `src/search`; what
   `src/mcp_server` imports from `src.companion`; what `src/companion` imports.
2. **What touches X:** what under `src/companion/` can change persisted state, and what mutable
   state `src/mcp_server/` keeps across tool calls.
3. **How does X work:** `src/viewer/`, its callers, and the logic it shares or duplicates.
4. **Where does X live:** the status, outcome and reason token sets, and where each one is
   restated.
5. **How does X work:** how each entry point turns a card name or id into a card row.
6. **Where does X live:** colour order and identity, pip parsing, type-line classification,
   legality, copy limits and display formatting, and where each is done more than once.
7. **How does X work:** the queries repository reads issue, the indexes behind them, and calls made
   once per item inside a loop.
8. **How does X work:** blocking work on async paths, and the sqlite-vec query from end to end.
9. **How does X work:** `GET /api/card-image/{id}` from end to end, and the cache headers on the
   other companion read routes.
10. **How does X work:** how the SPA fetches data, and how its components subscribe to the stores.

## Findings ranked by impact

Each finding gives what it costs today, what fixing it buys, and how wide it is. The evidence is in
the question sections it names.

### F1. The same card statistics disagree across MCP output, the companion UI and the viewer (Q6)

**What disagrees.** Land detection has five rules, mana-value bucketing has four schemes, and
colour counting has three different quantities under similar labels:

| Input | MCP tools (`src/logic`) | Companion UI | Viewer |
|---|---|---|---|
| An MDFC "Sorcery // Land" | Counts as a land | Counts as a spell | Counts as a spell |
| A card with mana value 0 | Bucket 0 | Bucket 1 | Bucket 1 |
| A card with mana value 7 or more | Its exact value | "7+" | "6+" |
| Kitchen Finks ×4 | 0 green and 0 white pips | 8 green and 8 white | 4 multicolour cards |

**What it costs today:** the agent reports one land count and curve in chat, and the companion
beside it shows another for the same deck. The product's premise is that the agent drives and the
app shows, so the two should agree. Nothing tests that they do.

**What fixing it buys:** one definition per statistic. The cheapest shape is for `src/logic` to
own each one and ship the computed figures in the deck-detail payload. The UI would then draw
numbers instead of re-deriving them, which follows AD-12's "the UI never assumes DB schema" one
step further.

**How wide it is:**
- Python: `mana_curve.py`, `assessment/mana_base.py`, `assessment/classifiers.py` and
  `viewer/view_model.py`.
- UI: `ManaCurve/curve.ts`, `ColourDistribution/colours.ts` and `state/deckGroups.ts`.
- About eight functions in total. The viewer is frozen (AD-15), so it is left to diverge until it
  is removed.

### F2. Snow basics are held to the copy limit (Q6)

**What happens:** `is_basic_land` looks for the text "basic land", and "Basic Snow Land — Forest"
does not contain it. `validate_deck` therefore flags five or more snow basics as a `copy_limit`
violation.

**What it costs today:** a wrong legality verdict for any deck with snow basics, in both the
`validate_deck` tool and the companion format check.

**What fixing it buys:** a correct verdict and one regression test.

**How wide it is:** one function. The second copy-limit rule, `validate_card_addition`
(mainboard-only, always 4, ignores the format), has no caller in `src` and is dead code.

### F3. The NOCASE fix did not reach `find_similar`, and three card-name resolvers exist (Q5)

**What happens:**
- `find_similar._resolve_seed` still matches names with `lower(name) = lower(?)`, which no index
  serves. PR #108 changed only the repository method and did not touch `find_similar.py`.
- The three resolvers order their ambiguous results differently.
- Only `lookup_card` applies the format and games filters.
- The repeated-pattern pitfall in `AGENTS.md` describes exactly this kind of partial fix.

**What it costs today:**
- A full table scan for each `find_similar_cards` call by name. #108 measured this lookup at about
  58 ms before the fix and about 0.5 ms after. It runs off the event loop, so it costs latency,
  not responsiveness.
- An LLM-facing inconsistency: the same name can produce different candidate lists, and different
  status tokens (`found`/`not_found` versus `ok`/`card_not_found`), depending on which tool the
  agent calls.

**What fixing it buys:** one resolver with one ordering and one token set, and indexed lookups
everywhere.

**How wide it is:**
- Three resolvers.
- Three copies of the `_MAX_MATCHES` and `_REFINE_THRESHOLD` constants.
- One duplicated message pair in `remove_card_from_deck`.
- One missing `strip()` in `lookup_card`.

### F4. The MCP `list_decks` tool eager-loads every card of every deck (Q7)

**What happens:** PR #109 added `list_deck_summaries` and switched only the companion route to it.
It left the MCP tool on purpose, to keep the story's scope. The tool still loads every
`deck_cards` row and every card row with no `LIMIT`, then throws them away to compute three
counts.

**What it costs today:** #109 measured this read at 99 ms for 52 decks, against 3 ms for the
summary path. The cost grows with the size of the deck library, and the agent pays it on every
`list_decks` call.

**What fixing it buys:** about a 30× faster tool, through a small change. `list_deck_summaries`
already takes the same format filter, so the remaining work is to keep the MCP payload
byte-identical.

**How wide it is:** one tool.

### F5. Image requests hold a database connection for the whole handler, pacer wait included (Q9)

**What happens:**
- `get_session` runs the readiness probe (up to four SELECTs) before the handler starts, even for
  a warm disk-cache hit that never reads the card row.
- The yield dependency keeps the session checked out until the handler returns, including while the
  request waits in the CDN pacer.

**What it costs today:**
- About four extra statements plus a connection checkout on every image.
- A cold 100-card deck queues about 100 image requests against a 15-connection pool. The pacer
  allows 4 fetches at once and spaces their starts 0.1 s apart.
- When the CDN is unreachable, the pacer goes slower than the pool timeout allows, so requests
  could fail with `500 internal_error` instead of the image placeholder. This is the analyzer's
  inference and was not reproduced.

**What fixing it buys:**
- Warm hits that never touch the database.
- A connection held only for the one `get_by_id`.
- No pool-exhaustion failure mode.

**How wide it is:** one route and its dependency. The unbounded disk cache is accepted by AD-11 and
is not drift.

### F6. `initialize_database` still runs parts of the import on the MCP event loop (Q8)

**What happens:**
- The 2026-09-03 audit's P1 #2 moved both import parses off the loop. The tool itself is still
  awaited on the loop, so other parts of the import still run there:
  - 10 MB synchronous file writes during the download (about 50 for the roughly 500 MB file);
  - building and compiling each 1,000-row insert batch;
  - the reconcile pass over about 60k rows.
- The module docstring in `server.py` says this tool offloads "its heavy passes the same way" as
  the search tools. That is true of the two parse passes only, not of the tool as a whole.
- The tool's result tells the caller to run `build_search_index` with `prune=true`, but the MCP
  tool has no `prune` parameter.

**What it costs today:**
- Loop stalls (MCP pings and cancellation) during an import that takes minutes. Imports are rare,
  so the impact is low.
- The prune instruction is an LLM-facing contract bug: the agent is told to make a call it cannot
  make.

**What fixing it buys:** a responsive server during an update, and an instruction the agent can
act on.

**How wide it is:** one tool, two importer functions and one docstring.

### F7. Semantic search can return short or empty results under format or games filters (Q8)

**What happens:** `hybrid_search` always takes the 200 nearest neighbours. It applies the legality
and games filters after the join, and it never widens k. The colour and mana-value filters apply
inside the KNN step, so they cannot cause this.

**What it costs today:** a narrow format (for example `pauper` or `oldschool`), or a game filter,
can starve the result. The tool answers `status="empty"` even when legal matches exist beyond
rank 200.

**What fixing it buys:** complete filtered results. Any change needs the recall sanity eval that
`AGENTS.md` requires.

**How wide it is:** one function. This over-fetch-then-filter shape is the documented design, so
this is a risk in the design rather than drift from it.

### F8. Every store write re-renders every card tile (Q10)

**What happens:**
- `App` subscribes to the whole system store with no selector.
- No component uses `memo`.
- `seedDeckCards` writes a new entry object for every row.

**What it costs today:**
- All tiles re-render twice on a cold open (the boot, then the reconcile re-drive).
- Up to about four full-tree renders follow each `deck_changed`.
- Two comments claim the opposite ("re-renders only when its own card's record lands", and "App
  owns a `hydrateCard` sweep").
- At 100 tiles this is unlikely to be visible, but cold open has a release-gating budget.

**What fixing it buys:** renders scoped to what changed, and comments that match the code.

**How wide it is:** `systemState.ts`, `cards.ts`, `CardTile`, `ColourDistribution`, and two stale
comments.

### F9. Conventions and docs that no longer match the code (Q2, Q7, Q4)

**What does not match:**
- **`AGENTS.md` and the `deck.py` comments:** both say relationships default to `lazy="noload"`.
  `DeckCardModel.card` and `DeckCardModel.deck` use SQLAlchemy's default lazy select. Under async,
  touching one that is not loaded raises instead of reading empty.
- **`find_deck_by_name`:** its docstring promises the first match, but the method raises when two
  decks match.
- **`docs/architecture.md` §5:** its tool catalogue stops at 16 tools. It also still plans "stdio →
  HTTP/SSE later", which contradicts the stdio-only rule.
- **The status vocabulary:**
  - The push outcome tokens are restated in four result models.
  - The REST reason set appears in `contracts.py`, `errors.py`, the router lists in `main.py`,
    `states.ts` and `cards.ts`. These copies are mostly type-checked (`get_args`,
    `satisfies Record<ErrorReason, …>`).
  - The real gaps are the ones no type checker sees: `set_card_quantity` says `card_not_found`
    where `remove_card_from_deck` says `not_in_deck`, and the resolvers' token sets differ (F3).

**What it costs today:** traps for the next contributor or agent. The lazy-load mismatch can turn
into a runtime error.

**What fixing it buys:** instructions and comments that can be trusted.

**How wide it is:** about six docstrings or comments, one `AGENTS.md` line, and one doc section.

### F10. Dead or unsafe repository methods, and two missing indexes (Q7)

**Dead or unsafe methods:**
- `merge_decks` commits once per row, so a failure partway through leaves a half-merged deck. It
  has no caller.
- `find_deck_by_name` raises on two matches and has no caller in `src`.
- `find_by_colors`, `find_by_type` and `search_by_keywords` are called only by a script.
- `validate_card_addition` is dead (F2).

**Missing indexes:**
- Nothing indexes `cards.oracle_id`, which every unique-oracle search query groups by.
- Nothing indexes `deck_cards` starting with `card_id`, the foreign-key child column.

**What it costs today:** maintenance and traps. The index cost was not measured: no EXPLAIN was
run.

**What fixing it buys:** about five fewer public methods. Any index needs a measured case first.

**How wide it is:** five methods and two possible indexes.

### What holds (no finding)

- **Layering:** `src/data` and `src/logic` import no web or MCP framework, and `src/logic` imports
  only `src.data.schemas`. One mild bend: `src/data/importers` imports `httpx` for the Scryfall and
  Spellbook downloads, so network I/O lives in the data layer.
- **AD-2:** nothing in `src/companion` writes to the database. Its file writes (the discovery file,
  the image cache and the lock file) are the ones AD-4 and AD-11 sanction. Its engine skips the
  index DDL and orphan-sweep hooks.
- **AD-3:** it holds, with one documented exception. The only `src.companion.app` import from
  `src/mcp_server` is the function-local one in the AD-14 dispatcher, and the boundary test exempts
  it by name.
- **Stateless tools:** the module-level shared `httpx` client, the embedder singleton and the
  per-thread sqlite connections are process caches. None of them holds session state.
- **AD-15:** the viewer is frozen and deprecated, and its removal is scheduled for "the next minor
  release once the companion is proven". v0.5.1 was a patch release, so the removal is pending, not
  overdue.

### Not re-raised (closed by earlier reviews)

These were not reported again:

- From the 2026-09-03 audit and its follow-ups:
  - the NOCASE index in the repository (#108);
  - the search tools under `to_thread` (#108);
  - the cold-open request diet: summary route, embedded cards, card Cache-Control (#109);
  - the shared `httpx` client.
- From the 2026-09-06 review:
  - foreign-key enforcement and the orphan sweep;
  - deck metadata on every mutation;
  - search-index metadata refresh;
  - the subscription gap (#113);
  - transient deck recovery.

The extra active-deck, deck and format-check read on every connected cold open is the cost #113
accepted, so it is recorded here and not raised.

## 1. Imports across the layers

No module in `src/data`, `src/logic` or `src/search` imports `src.mcp_server`, `src.companion`,
`src.viewer`, `fastapi`, `starlette`, `mcp` or `uvicorn`. Those names appear only in docstrings,
such as `src/paths.py:3-4 (module) @ ee0263d`, which states the import direction. The
framework-free rule holds with one exception: the data layer imports `httpx` in two API clients,
`src/data/importers/scryfall_api.py:8 (module) @ ee0263d` and
`src/data/importers/spellbook_api.py:23 (module) @ ee0263d`.

The other imports:

- **Inside `src`:**
  - `src/logic` imports only `src.data.schemas` and `src.logic`, for example
    `src/logic/deck_validator.py:24-25 (module) @ ee0263d`.
  - `src/search` reaches `src.data` once, at `src/search/query.py:35 (module) @ ee0263d`
    (`is_import_in_progress_sync`).
- **From `src/mcp_server` into `src.companion`:**
  - The leaf: `src/mcp_server/server.py:48-50 (module) @ ee0263d` and
    `src/mcp_server/tools/companion.py:40-45 (module) @ ee0263d`.
  - The app, once: a function-local import in the AD-14 dispatcher,
    `src/mcp_server/__main__.py:243 (_run_companion) @ ee0263d`. The boundary test exempts that
    file by name at `tests/unit/companion/test_import_boundary.py:142 (_APP_IMPORT_EXEMPT) @ ee0263d`.
- **From `src/companion` into the core:**
  - The repositories and schemas: `src/companion/app/routes/decks.py:25-27 (module) @ ee0263d` and
    `src/companion/app/routes/cards.py:56-57 (module) @ ee0263d`.
  - `src.logic` once, `format_check`.
  - Nothing from `src.mcp_server`.
- **From `src/viewer`:** only `src.data.schemas`, at
  `src/viewer/view_model.py:14-15 (module) @ ee0263d`.

## 2. Persisted state in the companion, and mutable state in the MCP server

**Database writes from `src/companion`: none.** No session `add`, `delete`, `merge`, `flush` or
`commit`, no DML construct, no `text()`, no `sqlite3` and no `PRAGMA` appears in it (per the
locator's search).

**Its engine.** The engine passes `ensure_indexes=False`
(`src/companion/app/deps.py:157-193 (_create) @ ee0263d`), and `create_engine` registers the NOCASE
DDL and orphan-sweep hooks only when that flag is true
(`src/data/database.py:238-284 (create_engine) @ ee0263d`). The engine gets the per-connection
`foreign_keys` PRAGMA and nothing else.

**File writes**, all outside the database:

- the discovery file: `src/companion/discovery.py:115 (write_discovery) @ ee0263d`
  (temp, fsync, replace);
- the image cache: `src/companion/app/images.py:401 (_write_atomically) @ ee0263d`;
- the instance lock: `src/companion/app/singleton.py:97 (acquire_instance_lock) @ ee0263d`.

**Mutable state in the MCP server:**

- **Captured by every tool call:** the build closure holds the session factory, the connection
  factory and the embedder (`src/mcp_server/server.py:184-187 (build_server) @ ee0263d`).
- **Module globals:**
  - the shared `(loop, httpx.AsyncClient)` pair at `src/companion/client.py:135 (_shared) @ ee0263d`;
  - the embedder singleton at `src/search/embedder.py:195-220 (get_embedder) @ ee0263d`;
  - per-thread sqlite connections at
    `src/search/connection.py:98-118 (ConnectionFactory.get_connection) @ ee0263d`.
- None of these holds a deck, a format or other caller state. The other module-level values in the
  tools are read-only constants.

## 3. The viewer

**What it is.** `src/viewer` is marked FROZEN (`src/viewer/__init__.py:1-21 (module) @ ee0263d`).
It renders HTML from a view model, writes it to a temp file and opens a browser
(`src/viewer/present.py:39-58 (present_deck) @ ee0263d`).

**Who calls it.** The `view_deck` tool is still registered and marked DEPRECATED. It calls
`present_deck` through `to_thread`, at `src/mcp_server/tools/view_deck.py:61-97 (view_deck) @ ee0263d`
and `src/mcp_server/server.py:573-601 (view_deck) @ ee0263d`. The viewer imports nothing from
`src/logic` or `src/companion`, so it carries its own copies of the land, bucket, pip and colour
helpers, compared in §6.

**History:**

- It was added in `9b9e8af "feat: add read-only HTML deck viewer + open-on-command script"` and
  `b296f99 "feat(mcp): add view_deck tool to render a deck in the browser"`.
- It was deprecated and frozen in
  `22c9a56 "chore: deprecate view_deck and freeze src/viewer (story 15.1)" #84`, whose message
  defers removal "to the next minor release once the companion is proven".
- No later commit the historian followed removes it or reschedules the removal.

## 4. Status, outcome and reason tokens

**Companion REST reasons.** `src/companion/contracts.py:76-87 (ErrorReason) @ ee0263d` defines ten
tokens. They are restated in these places:

- the status map in `src/companion/app/errors.py:46-56 (STATUS_BY_REASON) @ ee0263d`, which is
  checked against the type with `get_args`;
- the per-router lists in `src/companion/app/main.py:322-351 (build_app) @ ee0263d`;
- in the UI:
  - `ui/src/components/StatePanel/states.ts:69 (PANEL_FOR_REASON) @ ee0263d`;
  - `ui/src/state/cards.ts:65-84 (CARD_READ_IS_RETRYABLE) @ ee0263d`, which carries
    `satisfies Record<ErrorReason, boolean>`;
  - literal matches at `ui/src/state/deck.ts:319 (refetchSequence) @ ee0263d` and
    `ui/src/state/poller.ts:237 (createPoller) @ ee0263d`.

**Companion push outcomes.** `src/companion/client.py:85-91 (PushOutcomeToken) @ ee0263d` defines
five tokens.

- The four push result models restate the five literally, for example
  `src/mcp_server/tools/companion.py:253-259 (ShowSuggestionsResult) @ ee0263d`.
- `SetActiveDeckResult` adds `deck_not_found`, `database_not_initialized` and `error` (line 112).
- `CompanionStatusResult` has its own `running | not_running | error` (line 765). That is why
  ref 23 was disputed on scope: the restatement holds for the push tools only.

**MCP tool `status` literals.** Each tool module declares its own, and `database_not_initialized`,
`error` and `deck_not_found` recur across them (per the locator digest). Two inconsistencies a type
checker cannot see:

- When the card is not in the board, `set_card_quantity` answers `card_not_found`
  (`src/mcp_server/tools/deck_management.py:795-800 (set_card_quantity) @ ee0263d`, in the function
  defined at line 706), while
  `remove_card_from_deck` answers `not_in_deck`
  (`src/mcp_server/tools/deck_management.py:928-930 (remove_card_from_deck) @ ee0263d`).
- The card resolvers return `found`/`not_found` in one tool and `ok`/`card_not_found` in another
  (§5).

**Other sets written twice:**

- In `src/logic`, `FormatCheckName` is restated as `CHECK_ORDER` at
  `src/logic/deck_validator.py:484-493 (FormatCheckName) @ ee0263d`.
- In the UI:
  - the six event kinds appear in `ui/src/api/client.ts:288 (AGENT_EVENT_KINDS) @ ee0263d`;
  - the confidence tokens appear in both
    `ui/src/containers/SuggestionsView/SuggestionsView.tsx:126 (CONFIDENCE_TOKENS) @ ee0263d` and
    `ui/src/containers/SwapsView/SwapsView.tsx:85 (CONFIDENCE_TOKENS) @ ee0263d`.

## 5. Card resolution

**Three name resolvers exist:**

- **The repository pair, called by `lookup_card`:** `find_by_name_exact` then
  `find_by_name_partial`, with the format and games filters
  (`src/mcp_server/tools/card_lookup.py:67-84 (lookup_card) @ ee0263d`).
- **The same pair, called by `resolve_card` without filters:**
  `src/mcp_server/tools/deck_management.py:239-270 (resolve_card) @ ee0263d`. `resolve_card`
  serves `add_card_to_deck`, `set_card_quantity`, `remove_card_from_deck`, and `import_decklist`
  once per line (`src/mcp_server/tools/deck_import.py:449-457 (import_decklist) @ ee0263d`).
- **Raw SQL in `find_similar`**, on the sync sqlite connection:
  `src/mcp_server/tools/find_similar.py:206-301 (_resolve_seed) @ ee0263d`.

**How the repository and `find_similar` match differently:**

- **Exact match:** the repository uses `COLLATE NOCASE` equality
  (`src/data/repositories/card.py:154-211 (find_by_name_exact) @ ee0263d`). `find_similar` uses
  `lower(name) = lower(?)`. The indexes are declared with NOCASE collation at
  `src/data/models/card.py:26-29 (CardModel) @ ee0263d`, and nothing indexes `lower(name)`, so
  `find_similar`'s exact match scans the table. This was reasoned from SQLite's planner rules, not
  run through EXPLAIN.
- **Collapsing to one row per card:** the repository does it in SQL with no `ORDER BY`.
  `find_similar` does it in Python, ordered by id. The two `[:10]` candidate lists can therefore
  differ.
- **Ambiguous results:** each resolver has its own buckets and messages. The match constants are
  respelled at `src/mcp_server/tools/card_lookup.py:21-23 (module) @ ee0263d` and
  `src/mcp_server/tools/find_similar.py:58-59 (module) @ ee0263d`.

**Trimming.** `lookup_card` checks the name for blankness but passes it to the exact match
unstripped, so a name with stray whitespace misses the exact match. The other callers strip.

**History.**

- `_resolve_seed`'s `lower()` SQL arrived in
  `3b2d021 "feat: add find_similar_cards tool + code review patches (Story 2.5)"`.
- The repository moved to NOCASE in
  `4058265 "perf: indexed name lookup, single-transaction import, off-loop search tools" #108`.
  That PR measured about 58 ms (`SCAN`) before and about 0.5 ms (`SEARCH USING INDEX`) after, and
  did not touch `find_similar.py`.

**The companion and the UI accept ids only.**

- Both card routes check the id against a canonical-uuid pattern before calling `get_by_id`
  (`src/companion/app/routes/cards.py:116-173 (read_card) @ ee0263d`).
- The push contracts keep card ids unvalidated on purpose (AD-7).
- The UI hydrates by id through one deduped cache
  (`ui/src/state/cards.ts:247 (hydrateCard) @ ee0263d`).
- Combo matching uses a fourth name normalisation, `name_keys`, which adds the front-face key
  (`src/data/schemas/combo.py:34-52 (name_keys) @ ee0263d`).

## 6. Duplicated classification, parsing and validation

**Land detection.** Each site applies a different test:

- **`analyze_mana_curve`:** case-sensitive `"Land"` anywhere in the joined type line
  (`src/logic/mana_curve.py:74 (analyze_mana_curve) @ ee0263d`).
- **`_is_land`:** lowercase `"land"` over the whole line. Its docstring says an MDFC counts as a
  land (`src/logic/assessment/mana_base.py:69-78 (_is_land) @ ee0263d`).
- **The viewer:** the front face only, as a lowercase substring
  (`src/viewer/view_model.py:166-174 (is_land) @ ee0263d`).
- **The UI curve:** the whole word `Land` on the front face, before the em dash
  (`ui/src/containers/ManaCurve/curve.ts:121-122 (isLand) @ ee0263d`).
- **The UI group headers:** the first type word wins, and `Creature` is checked before `Land`
  (`ui/src/state/deckGroups.ts:176-181 (groupOf) @ ee0263d`).

Inputs that split them:

- **"Sorcery // Land":** a land in the MCP tools, a spell in the viewer and the UI.
- **A "Lander" subtype:** a land in every Python test, including the viewer's, but not in the UI.
- **Dryad Arbor:** a land everywhere, but filed under Creature in the UI group headers.

**Mana-value buckets:**

- **`analyze_mana_curve`:** truncates with `int()`, keeps a 0 bucket, and has no cap
  (`src/logic/mana_curve.py:82-88 (analyze_mana_curve) @ ee0263d`).
- **The viewer:** folds values of 1 or less into 1 and caps at "6+"
  (`src/viewer/view_model.py:149-163 (card_bucket) @ ee0263d`).
- **The UI:** rounds with `Math.round`, folds values of 1 or less into 1, and caps at "7+"
  (`ui/src/containers/ManaCurve/curve.ts:157-161 (bucketOf) @ ee0263d`).

**Colour counts:**

- **The MCP assessment:** counts only bare `{W}` to `{G}` pips, so hybrid, Phyrexian and twobrid
  symbols add nothing (`src/logic/assessment/mana_base.py:341-388 (compute_pip_signals) @ ee0263d`).
- **The UI colour bar:** counts every colour a symbol carries, front face only
  (`ui/src/containers/ColourDistribution/colours.ts:218-256 (coloursOf) @ ee0263d`).
- **The viewer pie:** counts cards by colour class, not pips
  (`src/viewer/view_model.py:131-146 (classify_color) @ ee0263d`).

**Copy limits:**

- `is_basic_land` tests for "basic land" in the lowercased type line, so snow basics fail it
  (`src/logic/deck_validator.py:41-65 (is_basic_land) @ ee0263d`).
- Through it, `validate_deck` holds snow basics to 4 copies, or 1 in singleton formats
  (`src/logic/deck_validator.py:404-407 (validate_deck) @ ee0263d`).
- Copies are counted per printing (`card_id`), across mainboard and sideboard.
- A second rule, `validate_card_addition`, counts the mainboard only, always allows 4, and has no
  caller in `src` (`src/logic/deck_validator.py:92-160 (validate_card_addition) @ ee0263d`).

**Duplicated, but giving the same answer:**

- **Deck colour identity:** computed by both
  `src/data/repositories/deck.py:863-872 (_refresh_deck_metadata) @ ee0263d` and the raw-SQL repair
  in `src/data/database.py:132-162 (_repair_deck_metadata) @ ee0263d`.
- **Board counts:** computed in the schema, the SQL summary and the validator.
- **The WUBRG order:** written out separately in five Python files and one TypeScript file.
- **Validation constants:** `_VALID_COLORS` is defined in three tool modules and `_VALID_GAMES` in
  four (per the locator digest).

## 7. Repository reads, indexes and per-item loops

**The MCP `list_decks` tool.** It calls the repository method that eager-loads `deck_cards` and
every card with no `LIMIT`, then keeps only three counts per deck. See
`src/data/repositories/deck.py:344-372 (list_decks) @ ee0263d` and
`src/mcp_server/tools/deck_management.py:273-315 (list_decks) @ ee0263d`.

The companion route uses the grouped-count method instead
(`src/data/repositories/deck.py:374-433 (list_deck_summaries) @ ee0263d`). That method came from
`0032507 "perf: companion cold-open request diet" #109`, which measured the route at 99 ms before
and 3 ms after on 52 decks. It left the MCP tool unchanged as a stated scope choice ("list_decks
and the MCP tool are untouched").

**Unbounded reads and full scans:**

- **Partial name match:** `find_by_name_partial` uses a leading-wildcard `ilike` with no `LIMIT`,
  and `resolve_card` cuts the result to 10 only after fetching it all. An import resolves each line
  separately, with up to two queries per line, then writes all lines in one bulk insert.
- **Advanced search:** `search_advanced` evaluates its filtered set twice, once for the count and
  once for the page. The unique-oracle filter groups by `oracle_id`, which has no index.
- **`deck_cards`:** no index starts with the foreign-key child column `card_id`.

**Lazy loading.** `DeckCardModel.deck` and `.card` declare no `lazy` option, so they use the
default lazy select (`src/data/models/deck_card.py:43-46 (DeckCardModel) @ ee0263d`). The only
`noload` relationship is `DeckModel.deck_cards`. This contradicts both `AGENTS.md` and the comments
at `src/data/repositories/deck.py:519-520 (add_card_to_deck) @ ee0263d` and
`src/data/repositories/deck.py:620-621 (add_cards_to_deck) @ ee0263d`.

**Dead or unsafe methods:**

- **`merge_decks`:** one committing call per source row, so it is not atomic, and it has no caller
  (`src/data/repositories/deck.py:1078-1122 (merge_decks) @ ee0263d`).
- **`find_deck_by_name`:** its docstring promises the first match, but `scalar_one_or_none` raises
  when two decks match (`src/data/repositories/deck.py:435-458 (find_deck_by_name) @ ee0263d`).

## 8. Blocking work on async paths, and the sqlite-vec query

**`initialize_database` runs on the loop.** The tool awaits its helper with no `to_thread`
(`src/mcp_server/server.py:1163-1192 (initialize_database) @ ee0263d`). The search tools do use
`to_thread` (`src/mcp_server/server.py:1031-1090 (semantic_search_cards) @ ee0263d`). The module
docstring says this tool offloads "its heavy passes the same way"
(`src/mcp_server/server.py:18-19 (module) @ ee0263d`). That holds for the two parse passes only:
the tool itself is not wrapped, so the rest of the import runs on the loop.

Inside the import, these parts still run on the loop:

- **The download:** the network reads are async, but each 10 MB chunk is written synchronously
  (`src/data/importers/scryfall_api.py:70-172 (download_bulk_data) @ ee0263d`).
- **The insert batches:** each 1,000-row batch is built and compiled on the loop.
- **The reconcile pass:** about 60k rows are processed in Python on the loop.

The two parse passes run off the loop, through `to_thread`.

**A prune instruction the agent cannot follow.** After a reconcile that deleted rows, the tool
tells the caller to run `build_search_index` with `prune=true`
(`src/mcp_server/tools/initialize_database.py:198-203 (initialize_database) @ ee0263d`). The MCP
tool takes only `rebuild` (`src/mcp_server/server.py:1194-1219 (build_search_index) @ ee0263d`).

**Smaller blocking calls, all bounded:**

- `read_discovery` on every companion push;
- `import_decklist` parsing (capped at 50,000 characters);
- the companion's startup writes, which run before it serves any request.

The Spellbook import blocks its loop throughout, but only a script calls it.

**The sqlite-vec path.**

- The tool runs `asyncio.to_thread`. The worker takes a per-thread connection with the extension
  loaded (`src/search/connection.py:98-118 (ConnectionFactory.get_connection) @ ee0263d`) and the
  process-wide embedder.
- `hybrid_search` always uses `k = 200`; neither caller passes a different value
  (`src/search/query.py:254-399 (hybrid_search) @ ee0263d`).
- The mana-value and colour predicates run inside the KNN step.
- The legality and games filters, the seed exclusion and the oracle de-duplication run after the
  join. Nothing widens k, so a filter that rejects most of the 200 candidates produces a short or
  `empty` result.

## 9. The companion image path and read routes

**The steps, in order.** For `GET /api/card-image/{id}`
(`src/companion/app/routes/cards.py:244-441 (read_card_image) @ ee0263d`):

1. The `DbSession` dependency opens a session and runs the readiness probe, up to four SELECTs,
   never cached (`src/companion/app/deps.py:240-283 (get_session) @ ee0263d`).
2. The handler reads the disk cache. A hit returns at once.
3. On a miss, it reads the card row.
4. It checks the negative cache.
5. It fetches through the pacer: `Semaphore(4)`, plus a 0.1 s gap between fetch starts
   (`src/companion/app/images.py:253-290 (Pacer) @ ee0263d`).
6. It writes the image to the cache before returning.

**The session stays checked out for the whole handler.** That includes the time a request waits in
the pacer. The `DbSession` docstring records `checkedout() == 1` during the fetch
(`src/companion/app/deps.py:295-312 (DbSession) @ ee0263d`).
The pool is the default 5 plus 10 overflow, with a 30 s timeout.

**What a cold deck costs.** A cold 100-printing deck queues about 100 requests, and the last fetch
starts about 9.9 s in. When the CDN is dead, the pacer goes slower than the pool timeout allows.
That inference, unverified, is that requests could fail with `500 internal_error`.

**Cache bounds.** The disk cache has no bound
(`src/companion/app/images.py:468-603 (DiskCache) @ ee0263d`), which AD-11 accepts. The negative
cache holds at most 2048 entries.

**Headers:**

- **Images:** `Cache-Control: public, max-age=31536000, immutable`, with no ETag.
- **`/api/cards/{id}`:** `private, max-age=3600`. The UI never benefits from it, because its only
  fetch helper passes `cache: 'no-store'`
  (`ui/src/api/client.ts:373-412 (request) @ ee0263d`). The comment there says this is deliberate.
- **The deck routes:** no Cache-Control at all.
- **Errors:** `no-store`.

No batch card route exists. The deck detail embeds full card records, so it serves as the batch.

## 10. SPA fetching and rendering

**A cold open of a 100-card deck makes these requests:**

1. `/api/decks`, `/api/active-deck` and `/api/session`, together and independent.
2. `/api/deck/{id}`, after the active-deck answer.
3. The socket upgrade, after the session answer.
4. Images: about one per tile, plus back faces and the detail panel's large image.
5. A format check.
6. When the socket goes live, `/health` and a full second boot: active-deck, deck and format check
   again (`ui/src/state/connection.ts:113-192 (useAgentConnection) @ ee0263d`,
   `ui/src/state/deck.ts:485-492 (reconcileDeckBoot) @ ee0263d`).

That comes to 9 JSON requests, 1 socket and about 101 images, with no per-card hydration.

**Why the second boot happens.** It comes from
`aec9c90 "fix: reconcile the deck boot on first connect and probe the poll after a transient deck refusal (CAP-2, CAP-3)" #113`,
whose PR accepts "one extra active-deck, deck and format-check read after first paint".

**Re-renders:**

- `useSystemState` returns the whole system store with no selector
  (`ui/src/state/systemState.ts:230-248 (useSystemState) @ ee0263d`), and no component uses `memo`
  or `useShallow`. Every `App` render therefore re-renders all tiles, rows, the curve and the colour
  bar.
- `seedDeckCards` writes a new entry object for every row
  (`ui/src/state/cards.ts:194-208 (seedDeckCards) @ ee0263d`), so every per-id subscriber
  re-renders on each seed: twice per cold open and once per refetch.
- Two comments say App owns a `hydrateCard` sweep and that a tile re-renders only when its own
  record lands. App never calls `hydrateCard`, and neither claim holds.

**Handling `deck_changed`.** The handler aborts the previous refetch and issues one new deck read,
so the latest response wins. It also restarts the stopped poll and triggers one format check per
settle: about three requests per event.

## Where the answers meet

- **`CardRepository.find_by_name_exact`:** reached from §5 (resolution) and §7 (per-line import
  queries).
  - It applies `COLLATE NOCASE` equality with `ORDER BY id LIMIT 1`
    (`src/data/repositories/card.py:154-211 (find_by_name_exact) @ ee0263d`).
  - It rejects nothing itself; the callers reject blank names.
- **`get_session`:** reached from §8 (the companion loop) and §9 (every read route). It raises
  `database_not_initialized` when the file or the cards are missing, and `internal_error` when no
  holder is wired (`src/companion/app/deps.py:240-283 (get_session) @ ee0263d`).
- **`hybrid_search`:** reached from §5 (seed resolution feeds it) and §8 (the vec path). It takes
  `limit` and `k` as given, and its callers reject limits outside 1 to 50
  (`src/search/query.py:254-399 (hybrid_search) @ ee0263d`).

## Open questions

- **The pool-exhaustion inference in §9 (dead CDN) was not reproduced.** The next ask: under a dead
  CDN and a cold 100-card deck, how many image requests return 500 rather than 502, with the
  browser's per-origin connection limit in play?
- **No EXPLAIN was run.** The next ask: what query plans do `search_advanced` with
  `unique_oracle`, `find_by_name_partial` and `_resolve_seed`'s exact match use on the real
  `cards.db`, and how long do they take?
- **The MCP SDK's per-request dispatch was not read**, because it is outside the repository. That
  leaves open whether a blocked loop also delays concurrent tool calls.
- **Out of scope here:** the agent views' `hydrateCard` loops, `faces.ts`, `agentView.ts`,
  `scripts/` and `tests/` (step 3 of the plan covers tests).
- **No ADR is proposed.** The decisions the historian found are already recorded in a PR, or are
  covered by an existing AD:
  - #109 scoped out the MCP tool;
  - #113 chose a full re-boot;
  - AD-15 schedules the viewer's removal;
  - AD-2 covers the companion skipping index DDL.

  None is both undocumented and hard to reverse.

## Prior documents

- `docs/architecture.md` (the MCP pivot design) and the 2026-07-25 architecture spine (AD-1 to
  AD-16): the baseline this report measures drift against.
- `_bmad-output/initiative-artificial-planeswalker/quality-audit-2026-09-03/quality-audit-2026-09-03.md`
  and `docs/quality-review-2026-09-06.md`: used only to exclude what they closed.
- No ADR files exist in the repository.
