# Addendum — Deck Power-Level Assessment

Depth that belongs downstream (architecture / implementation), not in the PRD narrative.

## A. Rejected alternatives & options considered

- **Dedicated `compare_decks` tool** — rejected. `assess_deck_power` is the single primitive;
  comparison is caller-side (run twice, diff the JSON). Keeps the server stateless and the surface
  minimal.
- **Game Changers via a versioned static list (Fork 4a)** — rejected in favour of 4b (import
  field). Trade-off: 4a is offline and versioned with the profile but needs manual bumps; 4b is a
  single source of truth (Scryfall bulk `game_changer`) that auto-updates on re-import, at the cost
  of a heavy re-import and coupling GC freshness to import cadence. Chosen: **4b**.
- **60-card meta-tier scoring (MTGTop8 / MTGGoldfish)** — rejected for v1. Requires web scraping,
  is ToS-touchy, and violates the otherwise all-local design. Standard stays heuristic-only.
- **EDHREC enrichment (inclusion / synergy / salt / percentile)** — cut from v1. Unofficial,
  fragile endpoint; low value for own-deck comparison (the primary use case). Roadmap candidate.
- **Calibrated cross-format absolute score + per-format offset** — cut. The hardest, least reliable
  part of the source research and unnecessary for comparing the owner's own decks. Roadmap.
- **Monte Carlo goldfish + ML/embeddings** — deferred. v1 consistency is analytical
  (hypergeometric), which is deterministic and cheap.

## B. Technical-how notes (for architecture)

- **Data model change (FR11).** Add `game_changer: bool` to `CardModel` (`src/data/models/card.py`)
  and `Card` schema (`src/data/schemas/card.py`); extract it in `transform_scryfall_card`
  (`src/data/importers/transformers.py`) from the Scryfall bulk `game_changer` field. Add a
  hand-written migration script under `scripts/` (no Alembic) and re-import to backfill. Consider
  whether `game_changer` should also be surfaced on `CardSummary` (currently drops
  legalities/keywords) — assessment reads full `Card` rows, so not strictly required.
- **Deck loading.** Use `DeckRepository.get_deck_with_cards(deck_id)` — it eager-loads full `Card`
  rows (legalities + oracle_text present). Do **not** use the MCP `load_deck` summary projection,
  which drops `legalities` and `keywords`.
- **MCP tool shape.** Sync `def` on the FastMCP threadpool; per-thread SQLite connection + WAL;
  stateless (`deck_id` / `format` as parameters). Lives in `src/mcp_server/tools/`. Domain logic
  (feature extraction, scoring, hypergeometric) belongs in `src/logic` (framework-free); the tool is
  a thin wrapper returning structured results + a formatted summary string.
- **Combo integration.** `find-my-combos` via `httpx`; cache layer keyed by deck contents; 429
  backoff via `tenacity`. Verify live camelCase keys against the backend Swagger. Bracket-tag→power
  map: Ruthless 4, Spicy 3, Powerful 3, Oddball 2, Precon-Appropriate 2, Casual 1.
- **Output schema.** Base on the `docs/deck-assess.md` §7.3 JSON, removing `absolute_score`,
  `percentile`, EDHREC-derived fields, **and the per-score numeric `low`/`high` band** for v1
  (confidence is categorical only — FR21). Keep `format_profile_version`, the dimension vector,
  `flags`, `confidence` + `confidence_reasons`, `reasoning`, and add a **descriptive tier label**
  alongside each for-format score (FR24).

## C. Implementation constants (from source research §Appendix)

- **Karsten Commander lands:** `31.42 + 3.13·avgMV − 0.28·(cheap draw + ramp)`; typical 33–40 lands
  + 10–15 ramp.
- **Karsten 60-card lands:** `19.59 + 1.90·avgMV − 0.28·(cheap draw + ramp)`; aggro 19–22, midrange
  23–26, control ~27.
- **Redundancy (60-card opener):** 4 copies 39.9%, 8 copies 65.4%, 12 copies 80.9%.
- **Commander Brackets gating:** 0 GC → B1–2; 1–3 GC → B3; 4+ GC / mass land denial / early
  two-card infinite → B4; cEDH (B5) self-declared (flag candidacy only).
- **Game Changers list:** ~53 cards as of Feb 9 2026; Scryfall `game_changer` / `is:gamechanger`.

## D. Calibration benchmark (to be composed)

Held-out set anchoring the acceptance gate (Success Metric 1): WotC precons should land ~Bracket 2;
known cEDH lists should flag as cEDH candidates / score high. Weighting of the 7-dimension aggregate
starts hand-tuned (documented, adjustable) and is validated against this set. Membership TBD (open
question in PRD §9).
