# Story 3.1: magic-deckbuilding Orchestrator Skill

Status: ready-for-dev

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

- [ ] Create the skill file `.claude/skills/magic-deckbuilding/SKILL.md` (AC: 1, 4)
  - [ ] YAML frontmatter: `name: magic-deckbuilding` + a `description` that triggers on deckbuilding/improve-my-deck/“what should I cut” style requests (the description is the ONLY trigger signal Claude Code sees — make it specific).
  - [ ] Define the **Planeswalker AI persona** (an expert, opinionated MTG deckbuilding coach — concise, decisive, explains the "why").
- [ ] Encode the **analyze→suggest→explain core loop** as explicit steps (AC: 1, 2)
  - [ ] Step 0 — **Resolve the deck**: get a `deck_id` (via `list_decks`/`load_deck`), or accept a pasted decklist. Pull the list with `load_deck`.
  - [ ] Step 1 — **Analyze**: call `analyze_mana_curve`, `detect_synergies`, and `validate_deck` (pass `format`/`games` every call) and read their structured results.
  - [ ] Step 2 — **Generate candidates**: use `semantic_search_cards` (conceptual intent) and/or `find_similar_cards` (seed-based) and/or `search_cards` (hard filters) to find swap candidates — **over-fetch**, then filter (see Dev Notes "candidate-generator pattern").
  - [ ] Step 3 — **Suggest**: produce **ranked swaps**, each as a cut→add pair (or add/cut) **with a reason** grounded in the Step-1 findings (curve gap, missing synergy, illegal card, etc.).
  - [ ] Step 4 — **Explain**: summarize the deck's state and why the top swaps matter.
- [ ] Wire the **exact MCP tool names** and document the stateless calling contract (AC: 2)
- [ ] Add the **graceful-degradation** rules: handle `index_unavailable`, `not_found`, `ambiguous`, `empty`, `invalid` statuses without breaking the loop (AC: 2)
- [ ] Reference the capability skills `synergy-discovery`, `mana-curve-analysis`, `format-legality` as deeper-dive companions — **without depending on them** (they ship in Stories 3.2–3.4) (AC: 4)
- [ ] Verify: dry-run the loop against the real index on a sample deck (see Verification) — confirm ranked swaps with reasons, statelessness, and no auto-add.

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

### Debug Log References

### Completion Notes List

### File List
