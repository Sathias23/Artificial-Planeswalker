# Technology-Currency Review — ARCHITECTURE-SPINE (deck-power-assessment)

**Reviewer lens:** Verify every committed decision was reality-checked against the actual repo and live external sources, not asserted from training data.

**Date:** 2026-07-11
**Spine reviewed:** `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md`

---

## Verdict

**PASS with two nuances.** Nearly every committed decision is verifiable against the repo and against current external sources. The dependency claims, the read-only-siblings claim, the async-httpx precedent, the transformer insertion point, the Scryfall `game_changer` field, and the Commander Spellbook `find-my-combos` endpoint/shape all check out. Two items warrant a note before implementation: (1) the async engine does **not** itself enable WAL — it only sets a busy-timeout, and WAL is turned on out-of-band by the sync search path; and (2) the live Spellbook response is richer than the spine's 2-bucket distillation (nested under `results`, six buckets, not two). Neither is a correctness error in the spine's decisions; both are precision gaps an implementer should be handed.

---

## 1. Dependency / "no new runtime dependency" claim — CONFIRMED

Spine (Stack section, lines 199–212) claims no new runtime dependency and lists the pins. Verified against `pyproject.toml` (`dependencies`, lines 22–33):

| Spine claim | pyproject.toml | Status |
| --- | --- | --- |
| Python >=3.12 | `requires-python = ">=3.12"` | ✓ exact |
| mcp / FastMCP >=1.27.0 | `mcp>=1.27.0` | ✓ exact |
| SQLAlchemy >=2.0.44 | `sqlalchemy[asyncio]>=2.0.44` | ✓ (see note) |
| aiosqlite >=0.21.0 | `aiosqlite>=0.21.0` | ✓ exact |
| httpx >=0.28.1 | `httpx>=0.28.1` | ✓ exact |
| pydantic (v2) >=2.0.0 | `pydantic>=2.0.0` | ✓ exact |

All five named pins are present and match. **No new runtime dependency is required** — the Spellbook client rides the existing `httpx`, the cache repo rides `sqlalchemy[asyncio]` + `aiosqlite`, results ride `pydantic`. Claim is accurate.

Minor precision note (LOW): the spine writes `sqlalchemy>=2.0.44`; the actual pin is `sqlalchemy[asyncio]>=2.0.44`. The `[asyncio]` extra is load-bearing (it's what pulls the async driver stack the whole feature depends on). Cosmetic in the spine's table, but worth stating exactly since the extra is the reason no new async dep is needed.

## 2. AD-5 — first write path to cards.db; sibling analysis tools read-only; WAL/concurrent-writer support

**Sibling analysis tools are read-only — CONFIRMED.** `src/mcp_server/tools/deck_analysis.py` implements all three siblings (`analyze_mana_curve`, `detect_synergies`, `validate_deck`). Every one does exactly one DB touch: `DeckRepository.get_deck_with_cards(deck_id)` (a `SELECT` with eager loads, `deck.py` lines 535–564). No `INSERT`/`UPDATE`/`DELETE`/`commit` anywhere in the analysis-tool path. The spine's claim that "curve/synergy/validate are read-only" and that `assess_deck_power` is "the first analysis tool to write to cards.db" holds. (`DeckRepository` itself has writers — create/add/remove/merge — but those back the deck-management tools, not the analysis tools; the spine's scoping is correct.)

**WAL + concurrent-writer claim — HOLDS, with an ownership nuance (MEDIUM).** The spine says the combo-cache upsert runs "under WAL, on the existing concurrent-writer hardening" (AD-5, line 125). Reality:

- The **async** engine (`src/data/database.py`, `create_engine`, lines 38–46) sets only `connect_args={"timeout": 5}` → SQLite busy-timeout of 5s. It does **not** issue `PRAGMA journal_mode=WAL`. That 5s busy-timeout *is* "the existing concurrent-writer hardening" on the async side (added in the recent "harden DB against concurrent writers" work).
- WAL mode is enabled only by the **sync** sqlite-vec path (`src/search/connection.py:136`, `PRAGMA journal_mode=WAL`, plus `busy_timeout=5000`). WAL is a persistent per-file property, so once the index build has run, `cards.db` stays in WAL and the async writer benefits.

Consequence for the implementer: the assess write path must not *assume* the async engine puts the file in WAL — it doesn't. In practice `initialize_database` + index build set WAL before any deck exists, so the concurrent-writer story is intact. But the combo-cache repo should either rely on that ordering explicitly (documented) or ensure WAL is set, rather than trusting the async engine. Single-writer upsert-by-hash under a 5s busy-timeout is sound; the spine's phrasing just over-credits the async layer with WAL enablement it doesn't own.

## 3. AD-9 — async httpx precedent at the data layer — CONFIRMED

`src/data/importers/scryfall_api.py` exists and uses **async httpx**: `async with httpx.AsyncClient(...)` in both `fetch_bulk_data_list` (line 37) and `download_bulk_data` (line 92), with `await client.get(...)` / `client.stream(...)`. It is a genuine sibling precedent for "an async httpx I/O adapter at the data layer." The AD-9 layer-placement decision is grounded in real code, not asserted.

## 4. AD-4 — transformer insertion point + Scryfall `game_changer` field

**`transform_scryfall_card` exists and is the right insertion point — CONFIRMED.** `src/data/importers/transformers.py:18` defines `transform_scryfall_card(card_json: dict[str, Any]) -> CardModel | None`, reads fields off the Scryfall card JSON dict, and constructs the `CardModel` (lines 106–129). Adding a `game_changer = card_json.get("game_changer")` read here and threading it into the `CardModel(...)` call is exactly the additive change AD-4 describes. It currently does **not** read `game_changer` (correct — it's the new field). The pattern of `.get("field")` for nullable columns (e.g. `keywords`, `color_indicator`) is already established, so AD-4's "nullable, preserve `None`" handling matches house style — and notably the file's existing comment warns against `get(...) or default` coercing JSON nulls, which reinforces AD-4's "never coalesce `None` to `False`" rule.

**Scryfall bulk `game_changer` boolean — CONFIRMED via web check.** Scryfall added Commander Game-Changer tracking and exposes it on the card object as `game_changer: true` (Scryfall announcement, Feb 2025), with a corresponding `is:gamechanger` search filter. Bulk-data files are serialized card objects, so the field is carried in bulk. The field name `game_changer` in AD-4 is correct as written. (Note: it is a boolean on the card object; treat absence/`null` on older/edge card layouts as the "unknown" state AD-4 already prescribes — the nullable-column design is exactly right for the pre-backfill window.)

Sources: Scryfall Card Objects API docs (https://scryfall.com/docs/api/cards); Scryfall announcement "game_changer: true" (https://x.com/scryfall/status/1889394724072460312); `is:gamechanger` filter (https://scryfall.com/search?q=is%3Agamechanger).

## 5. Commander Spellbook `find-my-combos` endpoint + bucketing — CONFIRMED current & keyless

Verified against the live backend source (`SpaceCowMedia/commander-spellbook-backend`, `backend/spellbook/views/find_my_combos.py`) and its tests:

- **Endpoint:** `https://backend.commanderspellbook.com/find-my-combos`, supports both **GET and POST** (`FindMyCombosView`, methods `get`/`post`). Current and live.
- **Keyless:** `permission_classes = []` on the view — **no auth / no API key required**. The spine's "keyless" assumption is correct.
- **Bucket field names:** the serializer emits `included`, `included_by_changing_commanders`, `almost_included`, `almost_included_by_adding_colors`, `almost_included_by_changing_commanders`, `almost_included_by_adding_colors_and_changing_commanders`. The backend's default renderer is `djangorestframework_camel_case.render.CamelCaseJSONRenderer` (settings.py), so the **over-the-wire JSON is camelCased**: `included`, `almostIncluded`, etc. → the spine's `included | almostIncluded` field names are exactly right for what an httpx client parses. (The Python client library de-camelizes back to snake_case, which is why the repo tests read `almost_included` — a client-side artifact, not the wire shape.)

**Nuance for the implementer (LOW→MEDIUM):** the spine's 2-bucket model (`included | almostIncluded`) is a reasonable distillation but is narrower than the live response:
1. The buckets are nested under a top-level **`results`** object, and the response is paginated (`count`, `next`, etc.). The client must read from `results`, not the root.
2. There are **six** buckets, not two. Beyond `included`/`almostIncluded` there are `includedByChangingCommanders`, `almostIncludedByAddingColors`, `almostIncludedByChangingCommanders`, and `almostIncludedByAddingColorsAndChangingCommanders`. For a fixed commander/color-identity deck-power assessment, folding the "by changing commanders"/"by adding colors" variants into (or explicitly excluding them from) the `included`/`almostIncluded` signal is a real modeling decision AD-5 leaves implicit. Recommend the spine or the first implementation task name which buckets feed the combo signal, so two implementers don't diverge.

Sources: `commander-spellbook-backend` `find_my_combos.py` view/serializer and `test_find_my_combos.py`; `settings.py` (`CamelCaseJSONRenderer`); Find My Combos (https://commanderspellbook.com/find-my-combos/); backend root (https://backend.commanderspellbook.com/).

---

## Findings summary

| # | Sev | Area | Finding | Fix |
| --- | --- | --- | --- | --- |
| F1 | MEDIUM | AD-5 (WAL) | The async engine sets only a 5s busy-timeout; it does **not** enable WAL. WAL is turned on out-of-band by the sync search path and persists per-file. The combo-cache writer inherits WAL only because index-build ran first. | State the WAL dependency explicitly, or have the cache repo/migration ensure `journal_mode=WAL`; don't credit the async engine with WAL it doesn't set. |
| F2 | MEDIUM | AD-5 / FR13–15 (Spellbook shape) | Live `find-my-combos` returns 6 buckets nested under a `results` envelope (paginated), not the flat `included`/`almostIncluded` pair the spine implies. | Read from `results`; name which of the 6 buckets feed the combo signal (fixed-commander decks probably want `included` + `almostIncluded` only, excluding the "by changing commanders"/"by adding colors" variants). |
| F3 | LOW | Stack table | Spine lists `sqlalchemy>=2.0.44`; actual pin is `sqlalchemy[asyncio]>=2.0.44`. The `[asyncio]` extra is the reason no new async dep is needed. | Record the extra for exactness. |

## Everything verified accurate

- All five dependency pins present in `pyproject.toml`; "no new runtime dependency" is true.
- Sibling analysis tools (`analyze_mana_curve`/`detect_synergies`/`validate_deck`) are strictly read-only; assess_deck_power genuinely is the first analysis-tool writer.
- `scryfall_api.py` exists and uses async httpx — AD-9's precedent is real.
- `transform_scryfall_card` exists, reads card JSON, builds `CardModel`, uses nullable-`.get` conventions — the right insertion point for `game_changer`, and its existing null-coercion warning reinforces AD-4.
- Scryfall exposes `game_changer` (boolean) on the card object / bulk data — field name confirmed against Scryfall's own announcement.
- Commander Spellbook `find-my-combos` is current, keyless (`permission_classes = []`), GET+POST; wire JSON is camelCase so `included`/`almostIncluded` are the correct field names.
