---
baseline_commit: a6f745dd4014baf656ba21d6bdb174b7337dbc2a
---

# Story 3.1: magic-deckbuilding Orchestrator Skill

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player,
I want a "Planeswalker AI" orchestrator skill that runs the analyze→suggest→explain loop,
so that I get ranked card swaps with reasons rather than raw tool output.

## Acceptance Criteria

1. **Given** `.claude/skills/magic-deckbuilding/`, **when** the skill is present, **then** it defines the Planeswalker AI persona and the core loop: pull list → mana curve → synergies → legality → ranked swaps with reasons (FR17).
2. **Given** a deck, **when** the orchestrator runs, **then** it invokes the Epic 1+2 tools (`search_cards`/`semantic_search_cards`, `analyze_mana_curve`, `detect_synergies`, `validate_deck`) in order and synthesizes a recommendation.
3. **Given** swap suggestions, **when** produced, **then** each includes a reason **and** they are ranked.
4. **Given** the skill metadata, **when** loaded, **then** its `description` triggers for deckbuilding requests **and** it references the capability skills (`synergy-discovery`, `mana-curve-analysis`, `format-legality`).

## Tasks / Subtasks

- [x] Create the skill file `.claude/skills/magic-deckbuilding/SKILL.md` (AC: 1, 4)
  - [x] YAML frontmatter: `name: magic-deckbuilding` + a `description` that triggers on deckbuilding/improve-my-deck/“what should I cut” style requests (the description is the ONLY trigger signal Claude Code sees — make it specific).
  - [x] Define the **Planeswalker AI persona** (an expert, opinionated MTG deckbuilding coach — concise, decisive, explains the "why").
- [x] Encode the **analyze→suggest→explain core loop** as explicit steps (AC: 1, 2)
  - [x] Step 0 — **Resolve the deck**: get a `deck_id` (via `list_decks`/`load_deck`), or accept a pasted decklist. Pull the list with `load_deck`.
  - [x] Step 1 — **Analyze**: call `analyze_mana_curve`, `detect_synergies`, and `validate_deck` (pass `format`/`games` every call) and read their structured results.
  - [x] Step 2 — **Generate candidates**: use `semantic_search_cards` (conceptual intent) and/or `find_similar_cards` (seed-based) and/or `search_cards` (hard filters) to find swap candidates — **over-fetch**, then filter (see Dev Notes "candidate-generator pattern").
  - [x] Step 3 — **Suggest**: produce **ranked swaps**, each as a cut→add pair (or add/cut) **with a reason** grounded in the Step-1 findings (curve gap, missing synergy, illegal card, etc.).
  - [x] Step 4 — **Explain**: summarize the deck's state and why the top swaps matter.
- [x] Wire the **exact MCP tool names** and document the stateless calling contract (AC: 2)
- [x] Add the **graceful-degradation** rules: handle `index_unavailable`, `not_found`, `ambiguous`, `empty`, `invalid` statuses without breaking the loop (AC: 2)
- [x] Reference the capability skills `synergy-discovery`, `mana-curve-analysis`, `format-legality` as deeper-dive companions — **without depending on them** (they ship in Stories 3.2–3.4) (AC: 4)
- [x] Verify: dry-run the loop against the real index on a sample deck (see Verification) — confirm ranked swaps with reasons, statelessness, and no auto-add.

## Dev Notes

### What this story IS — and is NOT

- **IS:** a single Claude Code **skill** — a `SKILL.md` Markdown file with YAML frontmatter under `.claude/skills/magic-deckbuilding/`. It encodes **judgment and a cross-tool workflow** (spec §7, D4). The "implementation" is prose/instructions the agent follows, **not Python**.
- **IS NOT:** new tools, new `src/` code, or a restatement of tool signatures. Do **not** add MCP tools or touch `src/`. There is no `mypy`/`ruff`/`pytest` gate on a skill file.
- **Frozen-port discipline (Epic 1/2 lesson):** the orchestrator consumes the *frozen* tool surface as-is. If a tool's output feels insufficient, prefer working within it (or log a deferred enhancement) over changing the tool in this story.

### Skill file format (match existing convention)

Every skill under `.claude/skills/` is a directory containing `SKILL.md` with this frontmatter shape (see any `.claude/skills/bmad-*/SKILL.md`):

```markdown
---
name: magic-deckbuilding
description: '<one line that makes Claude Code auto-invoke this for deckbuilding help — e.g. "Expert MTG deckbuilding coach: analyzes a deck''s curve, synergies, and legality and proposes ranked card swaps with reasons. Use when the user wants to build, improve, tune, or get feedback on a Magic deck.">'
---

# Planeswalker AI — Deckbuilding Orchestrator
<persona + the loop>
```

- `.claude/skills/magic-deckbuilding/` is the **first project (non-BMAD) skill** in this repo — all existing skills are `bmad-*`. Follow their `name`/`description` style; the `description` is the sole trigger signal, so make it specific to deckbuilding intent.
- Skills may include supporting files in the directory if helpful, but a single `SKILL.md` is sufficient and preferred here.

### The tools the orchestrator calls (exact MCP names + contract)

The server is registered as `artificial-planeswalker` (`.mcp.json`), so tools are invoked as `mcp__artificial-planeswalker__<tool>`:

| Tool | Key params | Returns (`status` + payload) |
|------|-----------|------------------------------|
| `mcp__artificial-planeswalker__list_decks` | `format?` | `ok` (`decks` summaries) / `empty` |
| `mcp__artificial-planeswalker__load_deck` | `deck_id` | `ok` (`deck` + cards) / `not_found` |
| `mcp__artificial-planeswalker__analyze_mana_curve` | `deck_id` | `ok` (`distribution`, `total_lands/spells`, `average_cmc`, `land_ratio`, `issues`, `recommendations`) / `empty` / `deck_not_found` / `error` |
| `mcp__artificial-planeswalker__detect_synergies` | `deck_id` | `ok` (`synergies[]`, `synergy_count`, `deck_cohesion` low/moderate/high) / `empty` / `deck_not_found` / `error` |
| `mcp__artificial-planeswalker__validate_deck` | `deck_id`, `format="standard"`, `games?` | `ok` (`report.is_legal` + violations) / `deck_not_found` / `invalid` / `error` |
| `mcp__artificial-planeswalker__semantic_search_cards` | `query`, `colors?`, `color_mode?`, `mana_value_min/max?`, `format?`, `games?`, `limit≤50` | `ok` (`cards[]` each with `distance`, nearest-first) / `empty` / `invalid` / `index_unavailable` |
| `mcp__artificial-planeswalker__find_similar_cards` | `card_name?`\|`card_id?`, `colors?`, … , `limit≤50` | `ok` (`cards[]` + `seed`) / `empty` / `not_found` / `ambiguous` / `invalid` / `index_unavailable` |
| `mcp__artificial-planeswalker__search_cards` | relational filters, `format?`, `games?`, `page`, `page_size` | `ok` / `empty` / `invalid` |
| `mcp__artificial-planeswalker__lookup_card_by_name` | `card_name`, `format?`, `games?` | `found` / `ambiguous` / `not_found` |

**Stateless contract (D5 — non-negotiable):** the server holds NO state. The orchestrator must pass `format`/`games` on **every** call and track the **active `deck_id`** itself (in the conversation). There is no "active deck" or remembered format on the server.

### ⭐ Candidate-generator pattern (the orchestrator's core value — from the live test)

`TOOL_PERFORMANCE_REPORT.md` (2026-06-27) proved the semantic tools rank by **topical proximity, not logical conjunction**: a compound ask ("removal that *also* reanimates") returns cards matching *either* effect, blended — the best "both" card ranked 14th. This is the orchestrator's reason to exist:

- **Treat `semantic_search_cards` / `find_similar_cards` as high-recall candidate generators.** Over-fetch (request a generous `limit`, ≤50), then have the orchestrator apply the **logical-intersection filter** itself: read each candidate's `oracle_text`/`type_line` and keep only those that satisfy the *whole* intent, discarding partial matches.
- **Present ranked candidates *with reasons* (retro design-input I1)** — never "the one right card." Recall is breadth-over-precision on the real 38k corpus.
- **`distance` is comparable *within* a single call only** (~0.44–0.61 observed) — use as a relative nearest-first signal, never an absolute quality threshold.
- **`find_similar_cards` cross-color leakage:** with no `colors` filter, off-color cards surface. When the deck has a defined color identity, **pass `colors`** (the deck's colors) to keep candidates on-color.

### Graceful degradation (the loop must never dead-end)

The tools now return structured statuses (no raw exceptions for these) — handle each:
- `index_unavailable` → tell the user the semantic index isn't built and surface the tool's own message (import → build chain); **fall back to `search_cards`** (relational) so the loop still produces suggestions.
- `find_similar_cards` `ambiguous` → present the `matches` and ask the user to pick (or re-call with a `card_id`).
- `not_found` / `empty` → adjust the query/filters or tell the user plainly; do not invent cards.
- `validate_deck` `deck_not_found` / curve/synergy `empty` → report and continue with what's available.

### HARD behavioral contracts

- **Never auto-add or auto-remove cards** without explicit user intent. Analysis (curve, synergy, legality) is **observational only**; proposing swaps is advisory. Applying a swap (`add_card_to_deck`/`remove_card_from_deck`) requires the user to confirm first. (project-context anti-pattern: "Don't auto-add cards … without explicit user intent.")
- If the user pastes a raw decklist rather than a saved deck, **building/persisting it (create_deck + add) is an explicit action requiring consent** — analysis of a pasted list can be done in-conversation without persisting.

### Capability skills (3.2–3.4) — reference, don't depend

The epic note: "the orchestrator (3.1) functions standalone by calling tools directly; the capability skills (3.2–3.4) are independent." Reference `synergy-discovery`, `mana-curve-analysis`, and `format-legality` by name as deeper-dive companions the user can reach for, but **3.1 must work today by calling tools directly** — those skills do not exist yet (Stories 3.2–3.4). Do not make the orchestrator's loop depend on them.

### Project Structure Notes

- New directory: `.claude/skills/magic-deckbuilding/` with `SKILL.md`. Consistent with the repo's tracked-skills convention (commit `bba3911` tracks `.claude/` skills).
- No `src/`, test, or dependency changes. This is a content artifact.
- Phase-1 client is Claude Code via `.mcp.json` (already wired); no UI.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1] — story statement + ACs + the standalone/independent note.
- [Source: docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md#7] — Claude skills suite shape; [#5] tool catalog; [#3 D4/D5] focused-suite + statelessness.
- [Source: _bmad-output/project-context.md] — skill conventions, stateless MCP rules, "don't auto-add cards" contract, RAG index prerequisite + `index_unavailable`.
- [Source: _bmad-output/implementation-artifacts/epic-2-retro-2026-06-24.md#6] — design-input I1 (ranked candidates with reasons; recall is breadth-over-precision).
- [Source: TOOL_PERFORMANCE_REPORT.md] — live-test findings: compound-intent dilution, candidate-generator pattern, `distance` within-call-only, cross-color leakage.
- [Source: src/mcp_server/server.py] — exact tool names, params, and return `status` enums (the contract above).

## Verification

A skill has no automated test harness — verify by **dry-running the orchestration** (the retro's "dry-run on the real index before encoding judgment" practice):

- On a sample saved deck (`deck_id` from `list_decks`), run the full loop and confirm:
  - All four analysis/search tool families are invoked with `format`/`games` passed per call.
  - Output is **ranked swaps, each with a reason** grounded in the curve/synergy/legality findings (AC 3).
  - Compound asks are intersection-filtered (not raw "either-effect" lists).
  - No card is added/removed without explicit confirmation.
- Confirm the skill auto-triggers on a natural request ("help me improve my Standard deck") — i.e. the `description` is specific enough.
- Confirm graceful handling when the index is unavailable (loop falls back to `search_cards`).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Code, dev-story workflow)

### Debug Log References

Live dry-run against the real MCP server (`artificial-planeswalker`) on saved deck **"Prismatic Dragon"** (`deck_id a6ec5c97-…`, 59-card five-color Dragons — deliberately chosen for its under-60 mainboard to exercise a real legality violation):

- `list_decks` → `ok` (10 decks). `load_deck` → `ok` (38 distinct cards).
- `analyze_mana_curve` → `ok`: `average_cmc` 4.66, distribution `{1:2, 2:1, 3:2, 4:5, 5:17, 6:8}`, 24 lands / 35 spells, `issues: ["Top-heavy curve: 71.4% of spells cost 5+ mana"]`.
- `detect_synergies` → `ok`: `deck_cohesion: high`, strong Dragon tribal (28 Dragons / 5 payoffs).
- `validate_deck(format=standard, games=["arena"])` → `ok`, `report.is_legal: false`: `min_deck_size` (59 < 60) + 8 `game_availability` violations (Temple duals not on Arena).
- `semantic_search_cards(mana_value_max=3, format=standard, games=["arena"], limit=15)` → `ok`: top hit **Mox Jasper** (dist 0.598), on-theme cheap accelerants — confirms over-fetch + intersection-filter pattern.
- `find_similar_cards(card_name="Sarkhan, Dragon Ascendant", format, games)` → `ok`, resolved `seed` echoed; results show the documented **seed-blend artifact** (orchestrator must filter).
- `search_cards(types=["Artifact"], oracle_text=["Add one mana of any color"], mana_value_max=2, format, games)` → `ok` (24 matches) — confirms the relational **fallback** path used on `index_unavailable`.

### Completion Notes List

- Deliverable is a single content artifact: `.claude/skills/magic-deckbuilding/SKILL.md` (first non-BMAD project skill). No `src/`, tests, or deps touched — there is no mypy/ruff/pytest gate on a skill file (per Dev Notes).
- **AC1** ✅ — defines the **Planeswalker AI** persona and the explicit `analyze → suggest → explain` loop (Steps 0–5).
- **AC2** ✅ — wires the exact `mcp__artificial-planeswalker__*` tool names with a verified contract table (params + every `status` enum, cross-checked against `src/mcp_server/server.py`), the non-negotiable **stateless** rule (pass `format`/`games` every call; track `deck_id` yourself), and full **graceful-degradation** handling for `index_unavailable` (→ `search_cards` fallback), `ambiguous`, `not_found`, `empty`, `deck_not_found`, `invalid`, `error`.
- **AC3** ✅ — Step 3 mandates **ranked** cut→add swaps, each with a one-line reason grounded in a Step-1 finding; includes an output-format example table. Dry-run produced exactly this shape.
- **AC4** ✅ — `description` is deckbuilding-trigger-specific (registry auto-loaded it, confirmed via system-reminder) **and** references the three capability companions (`synergy-discovery`, `mana-curve-analysis`, `format-legality`) both in the description and a dedicated body section — explicitly "reference, don't depend" (they ship in 3.2–3.4).
- Encoded the live-test **candidate-generator pattern** (over-fetch ≤50 → logical-intersection filter; `distance` is within-call-only; pass deck `colors` to `find_similar_cards`) and the **hard behavioral contract** (never auto-add/remove; persisting a pasted list needs consent).
- Frontmatter fix: the `description` contains a colon ("Magic: The Gathering") and an apostrophe — wrapped it as a single-quoted YAML scalar with doubled apostrophe (validated it parses).

### File List

- `.claude/skills/magic-deckbuilding/SKILL.md` (new) — the orchestrator skill.
- `_bmad-output/implementation-artifacts/3-1-magic-deckbuilding-orchestrator-skill.md` (modified) — frontmatter `baseline_commit`, task checkboxes, Dev Agent Record, Change Log, Status.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — story status `ready-for-dev` → `in-progress` → `review`.

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-06-27 | 0.1 | Story drafted (create-story); status `ready-for-dev`. |
| 2026-06-27 | 1.0 | Implemented `magic-deckbuilding/SKILL.md` (persona + analyze→suggest→explain loop + verified tool contract + graceful degradation + capability-skill references). Verified via live dry-run on deck "Prismatic Dragon". All ACs satisfied; status → `review`. |
