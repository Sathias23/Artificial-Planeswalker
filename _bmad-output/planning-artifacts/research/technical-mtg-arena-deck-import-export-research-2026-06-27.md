---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'MTG Arena deck import/export (round-trip)'
research_goals: 'Implementation feasibility — build round-trip MTGA import/export as MCP tools in the Artificial-Planeswalker stack, including card-identity mapping between Arena''s set/collector-number scheme and our oracle-card SQLite DB. Deep & focused on the MCP-server integration, with citations.'
user_name: 'Brad'
date: '2026-06-27'
web_research_enabled: true
source_verification: true
---

# Research Report: technical

**Date:** 2026-06-27
**Author:** Brad
**Research Type:** technical

---

## Research Overview

This report investigates how **Artificial-Planeswalker can import and export decks to/from Magic: The Gathering Arena**, with an implementation-feasibility focus and deep treatment of the card-identity mapping problem. The research was conducted across six gated steps (scope → technology stack → integration patterns → architecture → implementation → synthesis), with web findings verified against **live Scryfall and MTGJSON APIs** and against the **actual Artificial-Planeswalker codebase**.

**The bottom line: this is highly feasible and small.** There is no official Arena deck API — the entire ecosystem (Moxfield, Archidekt, MTGGoldfish, AetherHub) round-trips via a **plaintext clipboard format** and resolves card identity through **Scryfall/MTGJSON**. Our existing Python/SQLite/FastMCP stack already stores the needed printing-level fields (`set_code`, `collector_number`, `games`, `card_faces`); the feature is two FastMCP tools + one pure parser/renderer module + a small data-build step, with **zero new runtime dependencies**. Full Deck+Sideboard round-trip is ~3.5–4 days of work; Commander/Brawl adds ~1 day (needs a schema migration).

The two genuine decisions are: **(1)** ensuring the resolver has an *Arena-available* printing per card (our DB is refreshed with `oracle_cards`, which may not carry the Arena printing — mitigated by a derived `arena_printing` map plus live fallback); and **(2)** the deck schema's lack of a commander/companion zone (v1 lossy, v2 migration). The full executive summary, recommendations, and consolidated sources are in the **Research Synthesis** section at the end of this document.

---

## Technical Research Scope Confirmation

**Research Topic:** MTG Arena deck import/export (round-trip)
**Research Goals:** Implementation feasibility — build round-trip MTGA import/export as MCP tools in the Artificial-Planeswalker stack, including card-identity mapping between Arena's set/collector-number scheme and our oracle-card SQLite DB. Deep & focused on the MCP-server integration, with citations.

**Technical Research Scope:**

- Format / spec analysis — the exact MTGA plaintext deck-list format (clipboard Import/Export), line grammar, deck/sideboard/companion sections, and edge cases (basic lands, MDFCs/split/adventure, Alchemy `A-` cards, set-code quirks)
- Integration patterns — whether an official WotC API exists; how third-party builders (Moxfield, Archidekt, Deckstats, 17Lands, untapped.gg) import/export Arena lists and what data sources they rely on
- Card-identity mapping — mapping Arena set/collector# ↔ our Scryfall oracle-card DB (set-code differences, collector-number mismatches, Arena-only/rebalanced cards, name → importable printing resolution)
- Implementation approach — concrete design for two MCP tools (`export_deck_to_arena`, `import_deck_from_arena`) wrapping our repositories/schemas
- Risks & constraints — TOS/legal, format brittleness, round-trip fidelity, data-source maintenance burden

**Research Methodology:**

- Current web data with rigorous source verification (official WotC docs + Scryfall/MTGJSON + builder docs)
- Multi-source validation for critical technical claims (format grammar and set-code mapping)
- Confidence level framework for uncertain / community-reverse-engineered information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-06-27

---

## Technology Stack Analysis

> For this topic the "technology stack" is not languages/clouds but the **data formats, card-data sources, identity-mapping layer, and existing tooling** that any Arena import/export feature must sit on. Findings below are web-verified; several were validated directly against the live Scryfall and MTGJSON APIs. Confidence levels: **High** = official or empirically verified; **Medium** = corroborated community sources; **Low** = single/unverified source.

### The Arena Deck-List Format (the transport layer)

The de-facto contract is a **plaintext clipboard format** read/written by Arena's in-client **Import** / **Export** buttons. Wizards documents the *existence* of the headers and the rebalanced-card "A" marker, but has **never published a formal grammar** — the token-level rules are community-reverse-engineered. _(Confidence: High that no official grammar exists.)_

- **Line grammar:** `<qty> <Card Name>` optionally followed by `(<SET>) <CollectorNumber>`, one card per line — e.g. `4 Doom Foretold (ELD) 187`. The `(SET) #` selector is **optional**, but when present **both** set code and collector number are required together. A bare `4 Lightning Bolt` imports the newest/owned printing. _(High)_
- **Quantity:** Arena-native form is a bare number (`4 Name`); the `4x Name` variant is accepted by some third-party parsers, not confirmed Arena-native. _(Medium)_
- **Sections:** literal, case-insensitive headers on their own line — `About` + `Name <deck name>` (optional metadata block), `Deck`, `Sideboard`, `Commander`, `Companion` — blank-line separated; cards default to mainboard with no header. A `Commander` block triggers Commander/Brawl format auto-detection. _(High for header set; the `About`/`Name` block and Commander/Companion support are WotC-documented additions.)_
- **Basic lands:** formatted like any card, are the **only** entries allowed to exceed 4 copies, and `(SET) #` is optional (selects art). _(High)_
- **Gotchas:** **strip leading zeros** from collector numbers (Arena rejects `007`); names case-insensitive but must be spelled correctly. _(Medium)_
- _Sources:_ Draftsim import/export guides (https://draftsim.com/mtg-arena-import-deck/, https://draftsim.com/mtg-arena-export-deck/); MTGGoldfish Arena download (https://www.mtggoldfish.com/deck/arena_download/1029081); Wizards Alchemy page (https://magic.wizards.com/en/mtgarena/alchemy); **verbatim real Arena export** file `im-sticky/mtg-decklist-parser/example/doom - companion.txt`; Decklist.gg parser docs (https://decklist.gg/docs/deck-import).

### Multi-Faced & Special Cards (format edge cases)

- **Front-name-only** is the universally safe encoding for adventure / flip / transform / MDFC cards. True **split cards** keep the full `Front // Back` form. Emitting `Front // Back` for an MDFC is the **#1 cause of import errors** — strip everything from `//` onward for MDFCs. _(High for adventure/flip/transform & split; Medium-High for MDFC caveat. Scryfall layouts doc: https://scryfall.com/docs/api/layouts.)_
- **Alchemy / rebalanced cards** carry an **`A-` name prefix** (e.g. `A-Esika's Chariot`); the prefix is the disambiguator for import/export only. Omitting `A-` imports the original; including it imports the rebalanced version. _(High. MTG Wiki https://mtg.fandom.com/wiki/Alchemy_card; Wizards Alchemy page.)_

### Card-Data Sources (the identity backbone)

There is **no Arena API** for cards; the whole ecosystem resolves identity via **Scryfall** and/or **MTGJSON**.

- **Scryfall** card object exposes the Arena-critical fields: `arena_id` (Integer, nullable — "a large percentage of cards… do not have this ID"), `set`, `collector_number` (String, may contain letters/`★`), `games` (array incl. `"arena"`), `oracle_id`, `lang`, `layout`, `promo_types`, `security_stamp` (`"arena"` for rebalanced), `digital`. Search supports `game:arena` (live: **15,766** Arena cards), `set:`/`cn:`, `is:rebalanced` (live: 216), and `block:y22…y25` for Alchemy year-groups. **Bulk data:** use **`default_cards`** (every English printing) for Arena resolution — **not** `oracle_cards`, which keeps one "most-recognizable" printing per oracle id that frequently has `arena_id: null`. _(High — verified against live `api.scryfall.com`. Docs: https://scryfall.com/docs/api/cards, https://scryfall.com/docs/api/bulk-data, https://scryfall.com/docs/syntax.)_
  - ⚠️ **Project note:** our `cards.db` is refreshed with `--type oracle_cards` ([[db-refresh-uses-oracle-cards]]). That is fine for the oracle DB, but **Arena `(SET) #` resolution cannot rely on `oracle_cards` alone** — it needs `default_cards` (or live `/cards/search`) to see the actual Arena printing.
- **MTGJSON** exposes `identifiers.mtgArenaId` (typed as **String** — coerce vs Scryfall's Integer), `availability` (array incl. `"arena"`), `setCode`, `number`, `isRebalanced` (bool), `rebalancedPrintings` (uuid list, walks original→rebalanced), plus `scryfallId`/`scryfallOracleId` join keys. _(High — verified live against `mtgjson.com/api/v5/YMID.json`. Docs: https://mtgjson.com/data-models/identifiers/, https://mtgjson.com/data-models/card/card-set/.)_

### Set-Code & Identity Mapping Layer (the hard part)

Three layers of set codes diverge and must be reconciled:

1. **Paper/Scryfall code** (`dom`, `neo`, `stx`).
2. **Scryfall per-Alchemy-set code** (`ymid`, `yneo`, `sta`, `anb`, `ajmp`, `ha1`–`ha7`).
3. **Arena internal code** — Alchemy uses a **year-block** (`Y22`–`Y25`, one code spanning several Alchemy sets), surfaced by Scryfall via `block`/`block_code`, **not** `code`.

Confirmed divergences & traps:
- Arena historically uses **`DAR`** for Dominaria where Scryfall/paper use **`DOM`** — so printing-pinning must use the **Arena** code, not the Scryfall code. _(Medium-High — verbatim `4 Isolated Chapel (DAR) 241` in a real export.)_
- `set:y22` **fails** on Scryfall (it's a `block`, not a `code`); use `block:y22` or specific `set:ymid`. _(High.)_
- **`arena_id` is NOT a safe primary key:** a rebalanced `A-` card shares its `arena_id` with the original (verified: `A-Acererak`/`afr A-87` and `Acererak`/`afr 87` both `arena_id 77192`), and promo duplicates can share an `arena_id` too. Use `arena_id` as an *availability flag*; derive the importable string from the chosen printing's `set`+`collector_number`, and detect rebalanced via `promo_types ⊇ {rebalanced}` / `A-` prefix / MTGJSON `isRebalanced`. _(High — empirically verified.)_
- Arena-specific codes confirmed: `STA` (Mystical Archive), `JMP`/`J21`/`J25`, `HA1`–`HA7`, Y-prefixed Alchemy sets, `EA#` (Explorer Anthology), `AA#` (Arena Anthology, 2025), and Arena-only `ANB`/`ANA`. _(High except ANA/ANB exact expansion = Low. Untapped.gg codex: https://mtga.untapped.gg/codex/sets.)_

### Existing Tools & Open-Source Libraries

- **Online builders** with Arena import **and** export: **Moxfield** ("Copy for MTGA"), **Archidekt** (emits fully-qualified lines), **TappedOut**, **MTGGoldfish** (dedicated `arena_download` page + log-based Deck Sync), **AetherHub** (no-login Deck Converter), **Deckstats**, **mtgdecks.net**. Common omission: cards not in Arena's pool are silently dropped on "Copy for MTGA". _(High.)_
- **Log-based companions** (read the local Arena `Player.log` after the user enables *Detailed Logs (Plugin Support)*, never an API): **17Lands**, **untapped.gg companion**, **MTGGoldfish Arena Deck Sync**, **MTGAHelper**, **MTGATracker** (abandoned). They map Arena's internal **`grpId`** to identity via MTGJSON/Scryfall datasets. _(High.)_
- **Open-source parsers:** `im-sticky/mtg-decklist-parser` (JS, parse-only, models mainboard/sideboard/commander/companion); `lheyberger/mtg-parser` (Python, **active**, parses MTGA/MTGO text + 10 builder sources); `mtgatracker/python-mtga` (Python Arena card lookup, grpId-based, likely abandoned); `kelesi/mtga-utils` (collection export from logs). **scrython** wraps the Scryfall API. _(High.)_ ⚠️ **Gap:** no widely-maintained library whose primary job is **generating** Arena text from structured data — generation is typically in-house string templating.

### Official API Availability

**There is no official, public WotC/Arena deck API (read or write).** The Arena client is closed; the only sanctioned data surface is the local detailed log file. Every tool converges on (a) plaintext clipboard transport and (b) Scryfall/MTGJSON for identity. _(High — WotC support docs describe only clipboard import/export; corroborated by the entire tracker ecosystem's log-based design.)_

### Fit With Our Stack

Our existing stack is well-matched: **Python 3.12** + **SQLite `cards.db`** (Scryfall-derived) + **FastMCP** tools wrapping repositories. Import/export is **pure string parsing/templating + DB lookups** — no new heavy dependency, no network call at runtime if the DB carries the needed fields. The single structural prerequisite is ensuring the DB stores per-printing **`set` + `collector_number`** (and ideally `arena_id` / a `games`-includes-arena flag), which `oracle_cards` does not fully provide — flagged for the integration-patterns and implementation steps.

## Integration Patterns Analysis

> "Integration" here is unusual: there is **no API to integrate with**. The patterns are (a) the interop **contract** (clipboard plaintext), (b) the **round-trip data flow** and its fidelity/failure modes, (c) the **printing-resolution algorithm** that bridges our DB to Arena identity, and (d) the **Scryfall integration constraints** that govern our card-data pipeline. Confidence tags as before.

### Interoperability Model

- **No Arena deck API exists** (confirmed in Step 2). The two real integration surfaces are: **(1) clipboard plaintext** (Arena's in-client Import/Export buttons) and **(2) the local `Player.log`** (read-only, requires the user to enable *Detailed Logs (Plugin Support)*; used by trackers for collection/draft, not needed for deck import/export). _(High.)_
- For Artificial-Planeswalker, the right surface is **(1) clipboard plaintext** — generate a string the user pastes into Arena, and parse a string the user copies out of Arena. This is the same pattern every builder (Moxfield, Archidekt, MTGGoldfish, AetherHub) uses. _(High.)_

### The Round-Trip Data Flow

**Export (our deck → Arena):** `DeckModel` → for each `deck_card`, resolve name → Arena printing `(SET, collector_number)` → render line `qty Name (SET) #` under `Deck`/`Sideboard`/`Commander`/`Companion` headers → return the string for the user to copy.

**Import (Arena list → our deck):** paste string → tokenize lines into `(qty, name, set?, collector#?, section)` → resolve each to a card in our DB → build/update a `Deck` via repositories → report unresolved lines.

**Asymmetry to design around:** Arena's **Export always emits fully-qualified** `qty Name (SET) #` lines, but **Import accepts both** fully-qualified and **bare `qty Name`** (WotC's own example decklist uses bare names, e.g. `25 Swamp`). This asymmetry is the root of most round-trip surprises. _(High — WotC "Importing a Deck" support article.)_

### Data Format Contract & Interchange Formats

| Format | Encoding | Card identity key | Relation to Arena |
|---|---|---|---|
| **Arena text** | plaintext | `name`, optionally `(SET) collector#` | our target |
| **MTGO `.dek`** | XML | **MUID / `CatID`** (numeric per printing) | needs `mtgo_id` mapping (Scryfall `mtgo_id`, `/cards/mtgo/:id`) |
| **Cockatrice `.cod`** | XML | card **name** (+ optional set) | trivially close to Arena text |
| **Generic `.txt` ("MTGO format")** | plaintext | name (+ optional `(SET) #`) | Arena text minus the strict `(SET) #` |

Conversion deltas: Arena ⇄ Cockatrice/.txt is trivial (same `qty name (SET) #` shape); the only risks are MDFC `//`, Arena-only set codes, and `A-` names. MTGO `.dek` requires MUID↔name mapping. _(High for MTGO MUID + name-keyed formats; Medium on exact `.cod` element spelling. Cockatrice issue #4247; Cockatrice export docs.)_ **Recommendation:** ship Arena text first; treat `.txt`/MTGO/Cockatrice as cheap future add-ons sharing the same resolver.

### The Printing-Resolution Algorithm (the integration crux)

For **export**, resolve each card name → an Arena-importable `(SET) collector_number`:

1. Query Arena printings of the exact name (`!"name" game:arena`, unique=prints) — or look them up in our DB if it carries the needed fields.
2. **Exclude rebalanced** unless wanted (drop `promo_types ⊇ {rebalanced}` / `A-` collector numbers).
3. Prefer `lang=en`; prefer a recent non-promo Standard/expansion printing (sort by `released_at` desc).
4. Emit `(SET.upper()) collector_number`, **stripping leading zeros**.
5. **Fallbacks:** if multiple printings and none clearly preferred → newest non-promo English (Arena substitutes an owned printing anyway). If **zero Arena printings** → the card is not importable; surface it rather than emitting a paper-only `(SET) #` that Arena can't resolve. If only an `A-` printing exists → that is the correct form.

For **import**, resolve each parsed line → a card in our DB:

1. If `(SET, collector#)` present → look up by set+collector number (most precise; **ignores name typos / foreign names**). _(High.)_
2. Else resolve by exact name; for multi-faced cards match on **front-face name** (strip everything from `//`).
3. Handle the `A-` prefix explicitly (rebalanced vs original).
4. Collect unresolved lines into a report rather than failing the whole import.

> ⚠️ The resolver needs per-printing `set` + `collector_number` (+ ideally `arena_id`/`games`). Our `oracle_cards`-derived `cards.db` may not carry the specific Arena printing — see the data-prerequisite flagged in Step 2 and revisited in the architecture/implementation steps. _(High.)_

### Round-Trip Fidelity & Failure Modes

Arena import is **best-effort, not atomic** — it does not hard-fail the whole paste. Behaviors: empty clipboard → "input string is empty"; malformed line → **"Invalid line"**; well-formed but un-owned/not-in-pool cards → **highlighted on the right to craft with wildcards**, the rest still imports. _(High on highlight-and-craft; Medium on the exact silent-drop-vs-error edge for a well-formed nonexistent card.)_

Enumerated failure modes to defend against (all map to resolver rules above):

| # | Failure | Mitigation in our tools |
|---|---|---|
| 1 | Name typo / foreign name | Prefer `(SET) #` resolution (ignores name) _(High)_ |
| 2 | Card not in Arena pool | Detect zero Arena printings; report, don't emit junk _(High)_ |
| 3 | MDFC `// back` errors | Emit/parse **front face only** _(High)_ |
| 4 | Invalid/unknown set code | Validate against Arena set codes; fall back to bare name _(High)_ |
| 5 | Over-specified printing marks owned card "missing" | Prefer a sane default printing; allow name-only export mode _(High — MTGAZone)_ |
| 6 | Leading-zero collector # rejected | Strip leading zeros _(High)_ |
| 7 | Rebalanced `A-` mismatch | Explicit `A-` handling per target format _(Medium-High)_ |
| 8 | Qty > 4 non-basic | Validate (basics exempt) _(Medium)_ |

### Scryfall Integration Constraints (data pipeline)

These govern how we source/refresh the card data behind resolution. _(All High — verbatim from live Scryfall docs.)_

- **Rate limits (per-endpoint):** `/cards/search`, `/cards/named`, `/cards/random`, `/cards/collection` = **2/sec (500 ms)**; all other endpoints = **10/sec**. The `*.scryfall.io` file origins (bulk downloads) have **no rate limit**. HTTP **429** → 30-second lockout, escalating to ban; "It is not acceptable to ignore HTTP 429 responses."
- **Required headers on every request:** an accurate **`User-Agent`** (e.g. `ArtificialPlaneswalker/1.0`) and an **`Accept`** header. "Do not allow HTTP libraries to choose the header for you."
- **Caching:** "cache the data you download… at least for 24 hours"; for bulk name/price/image resolution **you must use the bulk data files**.
- **Bulk cadence:** daily exports, collected once every 12 h; gameplay-only data is fine to refresh **weekly / on set release**. Files: `oracle_cards` (~169 MB, one per oracle id), `default_cards` (~525 MB, every English printing), `all_cards` (~2.36 GB, every language).
- **Batch resolution:** `POST /cards/collection` — **max 75 identifiers per request**, 2/sec, accepts `set`+`collector_number` and `name`(+`set`) keys, returns a `not_found` array, **do not rely on positional index**.
- _Sources:_ https://scryfall.com/docs/api, .../rate-limits, .../bulk-data, .../cards/collection.

**Integration implication for us:** resolve **locally against the cached bulk file** (refreshed weekly / on set release) — not the live API at runtime. A full deck resolves with zero network calls; the live `/cards/collection` batch endpoint is a fallback only.

### MCP Tool Boundaries (how this lands in our server)

Per project context, new capability = **FastMCP tools** (sync `def`, threadpooled, per-thread SQLite + WAL) wrapping repositories and **returning structured results**. Two natural tools:

- `export_deck_to_arena(deck_id, …)` → `{ arena_text, unresolved: [...], warnings: [...] }`
- `import_deck_from_arena(arena_text, …)` → `{ deck_id | preview, resolved: [...], unresolved: [...] }`

Both are stateless (D5: `deck_id`/params supplied by caller, no per-session state), wrap the existing deck repositories, and live above `src/data`/`src/logic` (no format logic leaks into the domain core). The format parser/renderer is a pure, well-unit-tested module in `src/logic` (framework-free). _(Design grounded in `project-context.md`.)_

### Integration Security & Legal/TOS

- **Untrusted input:** `import_deck_from_arena` parses user-pasted text — treat as untrusted (bounded sizes, no eval, robust tokenizer, never crash on malformed lines). Aligns with the existing `report_bug` "untrusted input" stance. _(Project rule.)_
- **Legal:** operate under the **WotC Fan Content Policy** (the umbrella Scryfall itself uses). Constraints: don't paywall Scryfall data, don't imply Scryfall/WotC endorsement, preserve artist/copyright credit on any images, and add genuine end-user value (no bare republishing). Credit Scryfall as the data source. _(High — Scryfall "Use of Scryfall Data and Images". The "CC-licensed data" claim is imprecise — Medium.)_

## Architectural Patterns and Design

> This section grounds the design in the **actual Artificial-Planeswalker codebase** (verified by source exploration) and resolves the build-vs-buy decisions. The headline: the architecture is a clean fit for our layered MCP design, and most of the heavy lifting is already in the DB — the genuine decisions are (1) the printing-resolution data source and (2) the deck-model zone gap.

### Codebase Reality Check (what already exists)

- **`CardModel` ([src/data/models/card.py](src/data/models/card.py)) already stores the printing-level fields we need:** `set_code`, `set_name`, `collector_number`, `games` (JSON array incl. `"arena"`), `card_faces` (JSON), `oracle_id`, `legalities`, `image_uris`. _(High — verified.)_
- **The Scryfall import ([scripts/import_scryfall_data.py](scripts/import_scryfall_data.py) → [src/data/importers/transformers.py](src/data/importers/transformers.py)) defaults to `--type default_cards`** (every English printing), and maps `set`→`set_code`, `set_name`, `collector_number`, `games`, `card_faces`. **It does NOT capture `arena_id`, `mtgo_id`, `lang`, `layout`, or `promo_types`.** _(High — verified.)_
  - ⚠️ **Correction to the Step 2/3 flag:** the *script default* is `default_cards`, but standing practice ([[db-refresh-uses-oracle-cards]]) refreshes with `--type oracle_cards` (one "most-recognizable" printing per oracle id). **Which bulk type the live `cards.db` was last built from decides whether the stored `(set_code, collector_number)` is an Arena printing.** This is the central data decision below.
- **Deck model:** `DeckModel` ([src/data/models/deck.py](src/data/models/deck.py)) has `format` (string). `DeckCardModel` ([src/data/models/deck_card.py](src/data/models/deck_card.py)) uses a **composite PK `(deck_id, card_id, sideboard)`** with `quantity` + a `sideboard` boolean — **mainboard/sideboard only; no commander or companion zone.** Cards are referenced by `card_id` (Scryfall UUID), never by name. _(High — verified.)_
- **MCP tools** are FastMCP `@mcp.tool()`; deck tools are **async** (`async with session_factory()`), returning Pydantic result models with a `status: Literal[...]` field (e.g. `lookup_card_by_name`, `add_card_to_deck`). _(High.)_
- **Logic layer** ([src/logic/](src/logic/)) holds pure, DB-free modules (`deck_validator`, `mana_curve`, `synergy`) that take Pydantic schemas — the natural home for a pure parser/renderer. _(High.)_
- **Repository methods** exist for everything import needs: `DeckRepository.create_deck/add_card_to_deck/update_card_quantity`, `CardRepository.find_by_name_exact/find_by_name_partial/get_by_id`. **Missing:** a `find_by_set_and_collector_number(...)` lookup for precise import resolution. _(High.)_

### Data Architecture — the printing-resolution source (KEY DECISION)

Export needs, per card, an **Arena-available** `(set_code, collector_number)`. The options:

| Option | Description | Trade-off |
|---|---|---|
| **A. Re-import with `default_cards`** | Use the script default so every Arena printing is present; filter by `games ∋ "arena"`. | Simplest; but multiplies card rows per oracle id and may disturb the semantic-search/lookup dedup that oracle_cards gives. Conflicts with current practice. |
| **B. (Recommended) Separate `arena_printing` lookup** | Keep oracle_cards as the primary DB; add a small derived table/JSON `oracle_id → (arena_set, collector_number, arena_id)` built by a one-pass scan of `default_cards` (or `game:arena` search). Resolver consults it. | Keeps the main DB clean and current practice intact; the Arena map is a focused, separately-refreshable artifact. Extra build step. |
| **C. Live fallback** | For any card whose stored printing isn't Arena-available, call Scryfall `!"name" game:arena` at runtime. | Zero pre-build, but adds latency + rate-limit exposure; violates "resolve locally" preference. Good as a *fallback only*. |

**Recommendation:** **B + C** — a derived Arena-printing map for offline resolution, with live Scryfall as a graceful fallback for misses. Whichever option, **add `arena_id` capture to the transformer** (cheap, one line) so `games ∋ "arena"` + `arena_id` give a reliable availability flag. _(Reasoning grounded in verified DB state + Step 3 Scryfall rules.)_

### Set-Code Mapping Architecture (build-vs-buy → BUY-tiny)

Decisive finding: **no canonical Arena↔Scryfall set-code registry exists, but the divergence surface is tiny and stable.** _(High.)_

- For **~95% of recent sets, Scryfall `set.upper()` IS the Arena code** (`STX`, `NEO`, `MID`, `STA`, …).
- The only classic-expansion collision is **Dominaria `dom` → Arena `DAR`** (not derivable from any Scryfall/MTGJSON field — `mtgo_code: "dar"` is a coincidence, not a rule). Plus Arena Jumpstart `ajmp → JMP`.
- **Alchemy/digital sets** bucket into per-year Arena codes (`ymid/yvow/… → Y22`, `ydmu/… → Y23`, `y…→ Y24/Y25/Y26`) — and **Scryfall's `block_code` already returns these year codes** (`/sets/ymid` → `block_code: "y22"`), so they're auto-derivable if we capture `block_code`.

**Decision:** ship a small `SCRYFALL_TO_ARENA_SET` override dict in `src/logic` (seed from Draftmancer's ~25-entry `MTGASetConversions`), default to `set.upper()`, and (optionally) derive Alchemy year codes from `block_code` to shrink the hand-maintained part to essentially just `DAR` + `JMP`. Maintenance ≈ one dict edited once every few years. _(High. Sources: github.com/Senryoku/Draftmancer ManageCardData.py; github.com/FugiTech/deckmaster cards.py; live Scryfall Sets API.)_

### Deck-Model Fit & the Commander/Companion Gap

- **Deck + Sideboard map cleanly** to the existing `sideboard` boolean. _(High.)_
- **Commander / Companion have no home** in the current schema (composite PK is `(deck_id, card_id, sideboard)`; no zone/section). Options:
  - **v1 (no migration):** support `Deck`/`Sideboard` fully; place a Companion in the sideboard (where it lives in paper rules anyway) and a Commander in the mainboard, recording the commander `card_id` in `tags`/`strategy`. Lossy but unblocks 90% of use cases.
  - **v2 (migration):** widen `DeckCardModel` with a `zone` enum (`mainboard|sideboard|commander|companion`), changing the composite PK — a hand-written migration script per project convention (no Alembic). Round-trips Commander/Brawl losslessly.
- **Recommendation:** scope v1 first (Standard/limited/60-card constructed round-trips perfectly), flag v2 as a follow-up for Commander/Brawl. _(Design decision — surfaced for Brad.)_

### Component Design (where each piece lives)

```
src/logic/arena_format.py      # PURE: parse(text)->ArenaDeck ; render(ArenaDeck)->text
                               #   + SCRYFALL_TO_ARENA_SET map, A-/MDFC/leading-zero rules
src/logic/arena_resolver.py    # bridges ArenaDeck.cards <-> Card schemas via repositories
                               #   (or keep resolution in the tool/service layer)
src/data/repositories/card.py  # NEW: find_by_set_and_collector_number(set_code, cn)
scripts/build_arena_printings.py  # builds the derived arena_printing map (Option B)
src/mcp_server/server.py       # NEW async tools: export_deck_to_arena / import_deck_from_arena
```

- **Parser/renderer = pure functions** (no DB) → trivially unit-testable and property-testable. Follows the `deck_validator` precedent. _(High.)_
- **Resolver** is the only DB-touching piece; it uses repositories and the Arena-printing map. Import direction stays `data → logic → mcp_server`. _(High — matches layer rules.)_
- **Tools are thin & stateless** (D5): `deck_id`/`arena_text` are caller-supplied; tools wrap `DeckRepository` + resolver and return `status`-tagged Pydantic models. _(High.)_

### Error-Handling & Security Patterns

- **Best-effort, never-throw parsing:** malformed lines collected into an `unresolved`/`warnings` list (mirrors Arena's own behavior); the tool returns `status="partial"` rather than aborting. Matches existing tool result conventions. _(High.)_
- **Untrusted input:** `import_deck_from_arena` bounds input size, uses a strict tokenizer (no `eval`), and treats pasted text like the existing `report_bug` untrusted-content stance. _(Project rule.)_
- **Transaction discipline:** import writes go through repositories that already do commit/rollback-on-error — reuse, don't reinvent. _(High.)_

### Testing Architecture

- **Unit** ([tests/unit/logic/]): parser/renderer over a fixture corpus of **real Arena exports** covering the hard cases — MDFC (`//`), Alchemy `A-`, Dominaria `DAR`, basics > 4, Commander/Companion blocks, bare-name vs fully-qualified lines.
- **Property-based round-trip:** `parse(render(deck)) == deck` for the supported zones (the parser/renderer being pure makes this clean).
- **Integration** ([tests/integration/test_mcp_tools.py]): drive `export_deck_to_arena`/`import_deck_from_arena` end-to-end against a seeded DB; assert `(set_code, collector_number)` resolution and `unresolved` reporting.
- _(All consistent with the project's pytest conventions — `asyncio_mode=auto`, mirror layout.)_

### Key Architectural Decisions (ADR-style summary)

| # | Decision | Choice | Confidence |
|---|---|---|---|
| AD1 | Integration surface | Clipboard plaintext (no API, no log parsing) | High |
| AD2 | Printing-resolution source | Derived `arena_printing` map (Option B) + live Scryfall fallback; capture `arena_id` in import | High |
| AD3 | Set-code mapping | `set.upper()` + tiny `SCRYFALL_TO_ARENA_SET` override; derive Alchemy from `block_code` | High |
| AD4 | Parser/renderer placement | Pure module in `src/logic` (front-name-only, `A-`, leading-zero rules) | High |
| AD5 | Tool shape | Two async FastMCP tools wrapping repositories, `status`-tagged results | High |
| AD6 | Commander/Companion | v1 lossy (sideboard/tags), v2 `zone` enum migration | Medium (scope choice) |
| AD7 | Resolution precedence | `(set, cn)` → exact name (front face) → fail-to-report | High |

## Implementation Approaches and Technology Adoption

> The build is small, additive, and fits the project's conventions exactly: two FastMCP tools + one pure logic module + one data-build script, with **zero new runtime dependencies** (stdlib `re` only). Below: adoption strategy, the verified parser grammar, testing, effort/phasing, and risks.

### Adoption Strategy

- **Additive, incremental, no legacy disruption.** Import/export are new MCP tools wrapping existing repositories — they don't touch the `src/agent`/`src/ui` legacy layers and align with the MCP-server direction of record. Ship export first (smaller, no DB writes), then import. _(Design.)_
- **Vertical-slice phasing:** each phase is independently shippable and testable (export → import → Commander/Brawl). Matches the project's epic/story cadence (e.g. Story 3.1 structure). _(Project convention.)_

### The Parser — Concrete Reference Grammar (verified)

Synthesized from three open-source parsers (`lheyberger/mtg-parser` pyparsing grammar, `im-sticky/mtg-decklist-parser` JS, `NCMulder/MTG_Scripts` single-regex). None alone covers all edge cases; the combination below does. _(High confidence for the four canonical Arena forms; Medium for exotic collector numbers like `★`/`s`-suffixed promos.)_

```python
import re

# One anchored capturing regex: the (SET) num trailer is optional and atomic,
# so a bare "4 Lightning Bolt" puts everything in <name>.
CARD_LINE_RE = re.compile(
    r'^\s*'
    r'(?P<qty>\d+)\s*[xX]?\s+'                  # quantity, optional x/X
    r'(?P<name>.+?)'                            # card name (lazy)
    r'(?:\s+\((?P<set>[A-Za-z0-9]+)\)'          # optional  (SET)
    r'\s+(?P<num>[A-Za-z0-9\-★]+))?'       # ...with collector#
    r'\s*$'
)
SECTION_RE = re.compile(r'^(?P<sec>deck|sideboard|commander|companion)\s*$', re.IGNORECASE)
COMMENT_RE = re.compile(r'^\s*(//|#)')

# Per-line post-processing:
#   qty  = int(m["qty"])                       # int() strips leading zeros
#   name = m["name"].split("//")[0].strip()    # FRONT face only (split/MDFC/A- safe)
#   set_ = m["set"].upper() if m["set"] else None
#   num  = m["num"].lstrip("0") or m["num"]    # strip leading zeros if numeric
```

**Section state machine** (mirrors the JS reference): a header line switches the current section and is skipped; a blank line while in `deck` flips to `sideboard` (Arena's implicit separator); comments/blanks otherwise ignored; cards default to mainboard before any header. _(High.)_

Verified parse of the four hard forms: `4 Lightning Bolt`, `4 Lightning Bolt (2X2) 117`, `1 A-Cunning Geysermage (YDMU) 5`, and `2 Valki, God of Lies // Tibalt, Cosmic Impostor (KHM) 137` → all yield correct `(qty, name-front, set, num)`. _(Sources: github.com/lheyberger/mtg-parser, github.com/im-sticky/mtg-decklist-parser, github.com/NCMulder/MTG_Scripts.)_

### Dependencies & Tooling

- **Runtime:** none new — `re`, the existing repositories, and `cards.db`. (Live-Scryfall fallback would reuse the existing `httpx` dep.) _(High.)_
- **Build-time:** the `arena_printing` map (AD2) is produced by a `scripts/build_arena_printings.py` that reads the `default_cards` bulk (already supported by the importer) or queries `game:arena`. Refresh weekly / on set release (Scryfall cadence). _(High.)_
- Honors all project tooling gates (ruff, `mypy --strict`, pytest, conventional commits, Google docstrings — the MCP tool docstrings double as LLM-facing descriptions). _(Project rules.)_

### Testing & Quality Assurance

- **Unit** (pure parser/renderer): a fixture corpus of **real Arena exports** covering MDFC `//`, Alchemy `A-`, Dominaria `DAR`, basics > 4, Commander/Companion blocks, bare vs fully-qualified lines, comments, blank-line section flips, malformed lines.
- **Property-based round-trip:** `parse(render(deck)) == deck` for supported zones (clean because parser/renderer are pure).
- **Integration** (`tests/integration/test_mcp_tools.py`): drive both tools against a seeded DB; assert `(set, cn)` resolution, `unresolved` reporting, untrusted-input robustness (huge/garbage input never throws). _(All match project pytest conventions.)_

### Deployment & Operations

- **No infrastructure.** The feature is in-process MCP tools; the only operational task is the periodic `arena_printing`/`cards.db` refresh, which is an existing script-driven workflow. _(High.)_

### Effort & Phasing (rough, solo-dev)

| Phase | Deliverable | Effort |
|---|---|---|
| P0 | `arena_id` capture in transformer + `build_arena_printings.py` + `find_by_set_and_collector_number` repo method | ~0.5–1 day |
| P1 | `src/logic/arena_format.py` (parser + renderer + set-map) with full unit/round-trip tests | ~1–1.5 days |
| P2 | `export_deck_to_arena` MCP tool + integration tests | ~0.5 day |
| P3 | `import_deck_from_arena` MCP tool (resolver, partial-failure reporting) + integration tests | ~1 day |
| P4 (opt) | Commander/Companion `zone`-enum migration + round-trip | ~1 day |

_Total ~3.5–4 days for full round-trip (Deck+Sideboard); +1 day for Commander/Brawl. Estimates exclude review cycles._

### Risk Assessment and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `cards.db` built from `oracle_cards` lacks the Arena printing | **High** (current practice) | Export emits non-Arena `(set, cn)` | AD2: derived `arena_printing` map + `games ∋ arena` filter + live fallback |
| Format is undocumented/can drift | Low-Med | Parser breaks on a new form | Best-effort parser, fixture corpus, `unresolved` reporting (never hard-fail) |
| Set-code divergence (DAR, Alchemy) | Certain but bounded | Wrong `(SET)` for a few sets | AD3: `set.upper()` + ~25-entry override map; derive Alchemy from `block_code` |
| Commander/Companion zone gap | Certain | Lossy Commander round-trip | AD6: v1 lossy, v2 migration |
| Scryfall rate-limit/ban on live fallback | Low | Resolution failures | Resolve from local bulk; fallback throttled to 2/s with `User-Agent`, honor 429 |
| MDFC `//` import errors in Arena | Med | User import fails | Emit/parse front-face only |

## Technical Research Recommendations

### Implementation Roadmap

1. **P0 — Data prerequisite.** Add `arena_id` to the import transformer; add `CardRepository.find_by_set_and_collector_number`; build the `arena_printing` resolution artifact from `default_cards`. *Unblocks reliable export.*
2. **P1 — Pure format module.** `src/logic/arena_format.py`: parser (regex + section state machine), renderer, `SCRYFALL_TO_ARENA_SET` map, edge-case rules (front-face, `A-`, leading zeros). Full unit + property round-trip tests.
3. **P2 — Export tool.** `export_deck_to_arena(deck_id, name_only=False)` → `{status, arena_text, unresolved, warnings}`.
4. **P3 — Import tool.** `import_deck_from_arena(arena_text, format, …)` → `{status, deck_id|preview, resolved, unresolved}` with partial-failure reporting.
5. **P4 (optional) — Commander/Brawl.** `zone`-enum migration to round-trip Commander/Companion losslessly.

Frame each as a BMAD story (AC + tasks + dev notes) consistent with the existing Epic-3 artifacts.

### Technology Stack Recommendations

- **Keep it boring:** stdlib `re` for parsing; existing repositories for persistence; FastMCP `@mcp.tool()` (async, matching deck tools) returning `status`-tagged Pydantic models. No parser library needed (pyparsing/etc. are overkill for this grammar). Reuse `httpx` only for the optional live fallback.

### Skill / Effort Requirements

- Pure Python + regex + the existing layered patterns — no new skill area. The only domain subtlety (set-code mapping, `A-`/MDFC handling) is fully documented in this report and seedable from the cited reference maps.

### Success Metrics & KPIs

- **Round-trip fidelity:** ≥ 99% of cards in a Standard deck survive export → re-import (measured on a fixture corpus). Commander excluded until P4.
- **Resolution coverage:** % of Arena-legal cards exportable with a valid `(SET) #` (target ≈ 100% for Standard-legal; report the residual).
- **Robustness:** zero unhandled exceptions on a fuzz/garbage-input corpus; every unresolved line surfaced, never silently dropped.
- **Parser accuracy:** 100% on the canonical-forms unit corpus; tracked as a regression gate.

---

# Research Synthesis: Round-Tripping Decks Between Artificial-Planeswalker and MTG Arena

## Executive Summary

Magic: The Gathering Arena is the game's primary digital client, and its **deck import/export is the lingua franca of the entire MTG tooling ecosystem** — netdecking is ubiquitous, and every major builder (Moxfield, the de-facto default, plus Archidekt, MTGGoldfish, AetherHub) competes in part on how cleanly it round-trips with Arena. For a deckbuilding assistant like Artificial-Planeswalker, import/export is not a nice-to-have; it is the bridge that lets a user act on our advice inside the game they actually play. ([Draftsim](https://draftsim.com/mtg-arena-import-deck/), [MTG Arena Zone](https://mtgazone.com/import/), [Moxfield review](https://draftsim.com/best-mtg-deck-builder/))

The decisive finding is that this capability is **both small to build and architecturally low-risk**, because Arena is a closed client with **no public deck API** — so there is nothing to authenticate against, reverse-engineer at the network layer, or maintain a fragile integration with. Instead, the whole ecosystem converges on a **plaintext clipboard format** (`<qty> Name (SET) collector#`) for transport, and on **Scryfall/MTGJSON** for card identity. Artificial-Planeswalker already runs on exactly the right substrate: a Python/SQLite/FastMCP stack whose `CardModel` already stores `set_code`, `collector_number`, `games`, and `card_faces`. The feature reduces to **string parsing/templating + database lookups** — two FastMCP tools, one pure `src/logic` module, and a small data-build step, with **zero new runtime dependencies**.

The work is genuinely bounded: roughly **3.5–4 days** for a full Deck+Sideboard round-trip, plus ~1 day for Commander/Brawl (which needs a small hand-written schema migration). The two real decisions — both fully resolved in this report — are (1) guaranteeing the resolver sees an *Arena-available* printing per card (our `oracle_cards`-refreshed DB may not, so we add a derived `arena_printing` map with a live-Scryfall fallback), and (2) the deck schema's missing commander/companion zone (ship v1 lossy, add a `zone` enum in v2). Everything else — the format grammar, the set-code divergences, the failure modes — is well-understood, verified, and seedable from public reference implementations.

### Key Technical Findings

- **No official Arena deck API exists; clipboard plaintext is the universal contract.** Confirmed across the ecosystem and WotC support docs. _(High.)_
- **Card identity is resolved via Scryfall/MTGJSON, not Arena.** Our DB already carries `set_code`, `collector_number`, `games`, `card_faces`, `oracle_id`. _(High — verified against the codebase.)_
- **The hard part is printing selection, not parsing.** Export must pick an *Arena-available* `(SET) collector#`; `arena_id` is **not** a safe key (rebalanced `A-` cards share it with the original). Derive the importable string from the chosen printing's `set`+`collector_number`. _(High — verified live.)_
- **Set-code divergence is real but tiny and bounded:** `set.upper()` works for ~95% of sets; the exceptions are essentially `dom→DAR`, `ajmp→JMP`, and per-year Alchemy codes (derivable from Scryfall `block_code`). A ~25-line override map covers it. _(High.)_
- **Arena import is best-effort, not atomic** — it highlights un-owned cards to craft and flags malformed lines rather than aborting; our tools should mirror this with `unresolved` reporting. _(High.)_
- **A verified parser grammar already exists** (synthesized from three OSS parsers) handling bare names, `(SET) #`, `A-` Alchemy, and `//` split→front-face. _(High.)_
- **Our deck schema lacks a commander/companion zone** (only a `sideboard` boolean) — the one schema constraint on lossless Commander round-trip. _(High — verified.)_

### Technical Recommendations (Top 5)

1. **Build it as two stateless async FastMCP tools** — `export_deck_to_arena` and `import_deck_from_arena` — wrapping the existing repositories, with a pure parser/renderer in `src/logic/arena_format.py`.
2. **Resolve printings offline via a derived `arena_printing` map** (built from `default_cards`/`game:arena`), with live Scryfall as a throttled fallback; add `arena_id` capture to the import transformer.
3. **Implement set-code mapping as `set.upper()` + a small override dict**, deriving Alchemy year codes from `block_code`. Don't take on a full external Arena dataset.
4. **Ship Deck+Sideboard round-trip first (P0–P3); defer Commander/Brawl to a v2 `zone`-enum migration.**
5. **Make robustness a first-class requirement:** best-effort parsing that never throws, surfaces every `unresolved` line, treats pasted text as untrusted, and is guarded by a real-Arena-export fixture corpus + property-based round-trip tests.

## Reading Guide (Table of Contents)

This document is organized as a working technical reference. The detailed analysis precedes this synthesis:

1. **Technical Research Scope Confirmation** — goals, scope, methodology.
2. **Technology Stack Analysis** — the Arena format, multi-faced/special cards, Scryfall & MTGJSON data sources, set-code & identity mapping, existing tools/libraries, official-API availability, fit with our stack.
3. **Integration Patterns Analysis** — interop model, round-trip data flow, interchange formats, the printing-resolution algorithm, fidelity & failure modes, Scryfall integration constraints, MCP tool boundaries, security & legal.
4. **Architectural Patterns and Design** — codebase reality check, the data-source decision (AD2), set-code mapping (AD3), the deck-model zone gap (AD6), component design, error/security patterns, testing, and the **ADR-style decision table (AD1–AD7)**.
5. **Implementation Approaches** — adoption strategy, the **verified parser grammar/regex**, dependencies, testing, effort/phasing, and the **risk table**.
6. **Technical Research Recommendations** — roadmap (P0–P4), stack, success metrics.
7. **Research Synthesis** *(this section)* — executive summary, significance, methodology, future outlook, consolidated sources, conclusion.

## Significance & Methodology

**Why it matters now.** With netdecking the norm and Moxfield/MTGGoldfish having normalized one-click Arena export, users expect any serious deck tool to round-trip with Arena. Adding it turns Artificial-Planeswalker from an advisor into a tool whose recommendations are *immediately playable* — the natural completion of the analyze→suggest→explain loop the Planeswalker AI orchestrator already runs (Story 3.1).

**Methodology.** Six gated research steps with mandatory source verification. Web claims were triangulated across official (WotC support, Scryfall/MTGJSON docs), semi-official (Scryfall/Untapped data), and community (Draftsim, MTG Arena Zone, MTG Wiki, OSS repos) sources, with **confidence levels** attached to every material claim. Critically, the highest-stakes claims were **empirically verified against live `api.scryfall.com` / `mtgjson.com` endpoints** (e.g. the `arena_id` collision between rebalanced and original cards, the `block_code`→Alchemy-year mapping, `/cards/collection` limits), and the architecture was grounded by **direct exploration of the Artificial-Planeswalker source** (card/deck models, importer, MCP server, repositories). Where WotC has published no formal grammar, that gap is stated explicitly and the rules are flagged as community-reverse-engineered.

## Future Outlook

- **Format stability:** the Arena line grammar has been stable 2021→2025; the only additive changes were the `About`/`Name` block and Commander/Companion headers. Low drift risk; a best-effort parser absorbs minor additions. _(High.)_
- **Alchemy growth:** WotC continues shipping Y-prefixed Alchemy sets (through Y26+). Deriving Alchemy codes from `block_code` future-proofs the set-code map so new digital sets map automatically. _(High.)_
- **An official API remains unlikely:** Arena stays a closed client; the durable integration surface is clipboard text + Scryfall/MTGJSON. Build to that, not to a hoped-for API. _(High.)_
- **Natural extensions:** once the pure resolver exists, `.txt`/MTGO `.dek`/Cockatrice `.cod` import become cheap add-ons; collection-aware export (reading `Player.log`) is a larger, optional future capability.

## Source Documentation & Verification

**Official / first-party:** WotC "Importing a Deck" support article; WotC Alchemy page (`magic.wizards.com/en/mtgarena/alchemy`). _(Format headers + `A-` marker are the only WotC-documented specifics.)_

**Semi-official / authoritative data (verified live):** Scryfall API docs & live endpoints — [cards](https://scryfall.com/docs/api/cards), [bulk-data](https://scryfall.com/docs/api/bulk-data), [sets](https://scryfall.com/docs/api/sets), [syntax](https://scryfall.com/docs/syntax), [collection](https://scryfall.com/docs/api/cards/collection), [rate-limits](https://scryfall.com/docs/api/rate-limits), [layouts](https://scryfall.com/docs/api/layouts); MTGJSON [identifiers](https://mtgjson.com/data-models/identifiers/), [card-set](https://mtgjson.com/data-models/card/card-set/), [set](https://mtgjson.com/data-models/set/).

**Community / reference:** [Draftsim import](https://draftsim.com/mtg-arena-import-deck/) / [export](https://draftsim.com/mtg-arena-export-deck/) / [Alchemy](https://draftsim.com/mtg-arena-alchemy-rebalanced-cards/); [MTG Arena Zone import](https://mtgazone.com/import/); [MTG Wiki Alchemy](https://mtg.fandom.com/wiki/Alchemy_card); [Untapped.gg set codex](https://mtga.untapped.gg/codex/sets); [MTGGoldfish Arena export](https://www.mtggoldfish.com/deck/arena_download/1029081) & [Deck Sync](https://www.mtggoldfish.com/articles/introducing-mtg-arena-deck-sync); [Cockatrice export docs](https://cockatrice.github.io/docs/d0/d51/exporting_decks.html).

**Reference implementations (parser grammar + set-code map):** [lheyberger/mtg-parser](https://github.com/lheyberger/mtg-parser) (Python, active); [im-sticky/mtg-decklist-parser](https://github.com/im-sticky/mtg-decklist-parser) (JS); [NCMulder/MTG_Scripts](https://github.com/NCMulder/MTG_Scripts) (single-regex); [Senryoku/Draftmancer](https://github.com/Senryoku/Draftmancer) (`MTGASetConversions` map); [FugiTech/deckmaster](https://github.com/FugiTech/deckmaster) (`DAR` override); [mtgatracker/python-mtga](https://github.com/mtgatracker/python-mtga) (Arena `set_id` proof).

**Codebase (ground truth):** [src/data/models/card.py](src/data/models/card.py), [src/data/models/deck.py](src/data/models/deck.py), [src/data/models/deck_card.py](src/data/models/deck_card.py), [src/data/importers/transformers.py](src/data/importers/transformers.py), [scripts/import_scryfall_data.py](scripts/import_scryfall_data.py), [src/mcp_server/server.py](src/mcp_server/server.py), [src/logic/](src/logic/), [src/data/repositories/deck.py](src/data/repositories/deck.py).

**Confidence & limitations:** Format/data/architecture claims are predominantly **High** (official or empirically verified). Residual **Medium/Low** items: the exact silent-drop-vs-error behavior for a well-formed-but-nonexistent card on import; precise Arena-importer leniency rules (closed-client behavior); exotic collector-number/`.cod` element specifics. WotC publishes no formal grammar, so token-level rules are community-reverse-engineered (clearly flagged throughout).

## Conclusion & Next Steps

Round-tripping decks with MTG Arena is a **high-value, low-risk, ~4-day feature** that fits Artificial-Planeswalker's MCP architecture cleanly and completes the Planeswalker AI loop by making recommendations immediately playable. The path is fully de-risked: the format and its edge cases are documented, the card-identity mapping is solved (with the one DB-printing caveat mitigated), and a verified parser grammar and set-code map are ready to adapt.

**Recommended next steps:**
1. **Decide the two open scope questions:** (a) accept the AD2 derived-`arena_printing` approach (vs. re-importing `default_cards`), and (b) confirm v1 = Deck+Sideboard only, with Commander/Brawl as a later v2.
2. **Turn the P0–P4 roadmap into BMAD stories** under a new Epic (mirroring the Epic-3 story format), starting with P0 (data prerequisite) and P1 (pure `arena_format.py`).
3. **Stand up the real-Arena-export fixture corpus** early — it is the single most valuable asset for both unit and round-trip tests.

---

**Technical Research Completion Date:** 2026-06-27
**Source Verification:** All material claims cited; highest-stakes claims verified against live Scryfall/MTGJSON APIs and the Artificial-Planeswalker codebase.
**Overall Confidence:** High — multiple authoritative sources plus empirical verification.

_This document is an authoritative technical reference for implementing MTG Arena deck import/export in Artificial-Planeswalker, and the basis for scoping the implementation epic._


