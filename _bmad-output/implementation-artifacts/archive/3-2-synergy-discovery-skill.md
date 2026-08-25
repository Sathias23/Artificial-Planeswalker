---
baseline_commit: 9ffe006e328173d1da87dc9173c3fbc05d0b1021
---

# Story 3.2: synergy-discovery Skill

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player,
I want a synergy-discovery skill,
so that I can find and understand card interactions for my deck or strategy.

## Acceptance Criteria

1. **Given** `.claude/skills/synergy-discovery/`, **when** invoked, **then** it combines `semantic_search_cards` + `detect_synergies` to surface and explain interactions (FR17).
2. **Given** a strategy or seed cards, **when** run, **then** it returns candidate cards with explanations of *why* they synergize.
3. **Given** the results, **when** presented, **then** they are format-aware (`format`/`games` passed as parameters) and **bounded** to avoid overwhelming the player.

## Tasks / Subtasks

- [x] Create the skill file `.claude/skills/synergy-discovery/SKILL.md` (AC: 1)
  - [x] YAML frontmatter: `name: synergy-discovery` + a `description` that triggers on synergy/interaction/combo/"what works with"/"what pairs with X" requests. The `description` is the **only** trigger signal Claude Code sees — make it specific and distinct from the `magic-deckbuilding` orchestrator (this skill is a focused *single-topic dive* on interactions, not the full analyze→suggest→explain loop).
  - [x] Define a tight persona/role: a synergy/interaction specialist that maps how cards work *together* and explains the engine, not just lists cards.
- [x] Encode the **three invocation modes** and which tools each uses (AC: 1, 2)
  - [x] **Strategy / archetype mode** (no deck) — e.g. "Golgari sacrifice", "graveyard recursion in Standard": drive `semantic_search_cards` with conceptual queries to surface enablers, engines, and payoffs; explain how the pieces chain.
  - [x] **Seed-card mode** — "what synergizes with **[card]**?": `lookup_card_by_name` the seed for its real `oracle_text`/`type_line`, optionally `find_similar_cards` for near-neighbours, then `semantic_search_cards` for cards that *interact with* (not merely resemble) the seed's mechanics.
  - [x] **Saved-deck mode** — "find more synergies for my deck": call `detect_synergies` (`deck_id`) to read existing patterns + `deck_cohesion`, then `semantic_search_cards` to find **new** pieces that reinforce a detected (or latent) synergy.
- [x] **Surface AND explain interactions** — each candidate carries a concrete "why they synergize" sentence naming the interaction (engine/loop/payoff), not a generic "this is good" (AC: 2)
- [x] Document the **exact MCP tool contracts** for the tools this skill calls, and the stateless calling rule (pass `format`/`games` every call) (AC: 1, 3)
- [x] Encode the **`detect_synergies` coverage limits** so the skill knows what the detector is *blind to* and must reason about itself (tribal + 12 keywords + only 3 mechanic combos) (AC: 1)
- [x] Encode the **candidate-generator pattern** (over-fetch ≤50 → logical-intersection filter; `distance` is within-call-only; pass deck `colors` to keep candidates on-color) — doubly important here because synergy is inherently a *conjunction* and semantic search ranks by topical proximity (AC: 2)
- [x] Make output **format-aware and bounded**: group candidates into a few synergy themes with a handful of cards each, not a 50-card dump (AC: 3)
- [x] Add **graceful-degradation** rules: handle `index_unavailable`, `not_found`, `ambiguous`, `empty`, `invalid`, `error` without dead-ending (AC: 1)
- [x] Add the **hard behavioral contracts**: observational/advisory only, never auto-add cards, statelessness; persisting a pasted/strategy list to get a `deck_id` for `detect_synergies` needs explicit consent (AC: 1)
- [x] Cross-reference the `magic-deckbuilding` orchestrator (this is its "deeper synergy dive" companion) and stay **independent** of `mana-curve-analysis` / `format-legality` (Stories 3.3–3.4, not yet shipped) (AC: 1)
- [x] Verify: dry-run all three modes against the real index/MCP server (see Verification) — confirm candidates-with-interaction-explanations, format-awareness, bounded output, statelessness, and no auto-add.

## Dev Notes

### What this story IS — and is NOT

- **IS:** a single Claude Code **skill** — a `SKILL.md` Markdown file with YAML frontmatter under `.claude/skills/synergy-discovery/`. It encodes **judgment and a cross-tool workflow** (spec §7, D4; FR17). The "implementation" is prose/instructions the agent follows, **not Python**.
- **IS NOT:** new tools, new `src/` code, or a restatement of tool signatures. Do **not** add MCP tools or touch `src/`. There is **no** `mypy`/`ruff`/`pytest` gate on a skill file.
- **Frozen-port discipline (Epic 1/2 lesson, reaffirmed by 3.1):** consume the *frozen* tool surface as-is. If a tool's output feels insufficient, work within it (or log a deferred enhancement) — do **not** change a tool or `src/` in this story.
- **Scope guard (this is the focused dive, not the orchestrator):** 3.1 (`magic-deckbuilding`) already runs the full analyze→suggest→explain loop and gives an *at-a-glance* synergy read. This skill is the **deep single-topic pass on interactions** that 3.1 points to. Don't reimplement the whole loop here; do go deeper on synergy than `detect_synergies` alone can.

### Skill file format (match the established convention)

Every skill under `.claude/skills/` is a directory containing `SKILL.md` with this frontmatter shape (model it on the sibling `.claude/skills/magic-deckbuilding/SKILL.md` shipped in 3.1):

```markdown
---
name: synergy-discovery
description: '<one specific line that auto-invokes this for synergy/interaction/combo discovery — e.g. "Find and explain Magic: The Gathering card synergies and interactions. Given a strategy, a seed card, or a saved deck, surfaces candidate cards and explains *why* they work together (engines, payoffs, combos). Use when the user asks what synergizes/pairs/combos with a card or theme, or wants to deepen a deck''s interactions.">'
---

# <Persona/role title>
<role + the three modes + the tool contracts + candidate-generator + degradation + hard rules>
```

- **YAML scalar gotcha (bit 3.1):** the `description` will contain a colon ("Magic: The Gathering") and likely an apostrophe — wrap it as a **single-quoted** YAML scalar and **double any apostrophe** (`''`). 3.1 hit exactly this; validate it parses.
- The `description` is the **sole** trigger signal — make it specific to *interaction/synergy* intent and clearly distinct from the orchestrator's "improve my deck" trigger, so the right skill fires.
- A single `SKILL.md` is sufficient and preferred (supporting files allowed but unnecessary here).

### The core distinction — why this skill exists beyond `detect_synergies`

`detect_synergies` is **intra-deck and pattern-limited**. Read [src/logic/synergy.py](src/logic/synergy.py) before writing the skill — it only ever finds:

- **Tribal** — shared creature types, threshold ≥ 5 creatures of one type (+ optional tribal-payoff text match), and a hard-coded exclusion list of generic classes (`Scout`, `Warrior`, `Soldier`, `Wizard`, `Cleric`, `Rogue`, `Shaman`, `Druid`, `Knight`, `Berserker`, `Archer`) — so e.g. a Soldiers theme is **invisible** to it.
- **Keyword** — only the 12 in `COMMON_KEYWORDS` (`flying, lifelink, deathtouch, trample, vigilance, first strike, double strike, menace, reach, haste, hexproof, indestructible`), needs ≥ 4 carriers **and** ≥ 1 "matters" payoff.
- **Mechanic combos** — exactly **three**, by regex: `sacrifice` (sac outlet + death trigger), `graveyard` (self-mill + graveyard payoff), `card_draw` (repeatable draw + discard/madness payoff).

Everything else — flicker/blink, +1/+1 counters, energy, treasure/tokens, lifegain payoffs, untap loops, spellslinger/prowess, equipment/auras, landfall, two-card combos — is **completely invisible** to `detect_synergies`. It also operates **only on a saved `deck_id`'s mainboard** and surfaces **no new cards** (only what's already in the deck).

**So this skill's value-add (the whole reason it exists):**
1. Use `detect_synergies` (when there's a saved deck) to ground discovery in what the deck *already* does and how cohesive it is.
2. Use `semantic_search_cards` as a high-recall candidate generator to surface **new** pieces — including interactions the detector is blind to.
3. Apply **your own judgment** to explain the interaction (the engine/loop/payoff), name the cards, and keep it format-legal and bounded.

`detect_synergies` is a floor, not a ceiling — never present its output as the complete synergy picture.

### The tools this skill calls (exact MCP names + return contract)

Server id is `artificial-planeswalker`, so every tool is `mcp__artificial-planeswalker__<tool>`. Each returns a `status` plus a payload — **branch on `status`, never assume `ok`.** (Contract cross-checked against `src/mcp_server/` ground truth; same table 3.1 verified.)

| Tool | Key params | `status` values (payload on success) |
|------|-----------|--------------------------------------|
| `semantic_search_cards` | `query`, `colors?`, `color_mode?` (`any`/`all`/`exact`/`at_most`), `mana_value_min/max?`, `format?`, `games?`, `limit` (default 10, **max 50**) | `ok` (`cards[]`, each a card + `distance`, nearest-first) · `empty` · `invalid` · `index_unavailable` |
| `detect_synergies` | `deck_id` | `ok` (`synergies[]` each w/ `pattern_type`/`subtype`/`affected_cards`/`explanation`/`strength`; `synergy_count`; `deck_cohesion` `low`/`moderate`/`high`) · `empty` · `deck_not_found` · `error` |
| `find_similar_cards` | `card_name?` \| `card_id?`, `colors?`, `color_mode?`, `mana_value_min/max?`, `format?`, `games?`, `limit` (default 10, **max 50**) | `ok` (`cards[]` + resolved `seed`) · `empty` · `not_found` · `ambiguous` (`matches`) · `invalid` · `index_unavailable` |
| `lookup_card_by_name` | `card_name`, `format?`, `games?` | **`found`** (`card` w/ full `oracle_text`/`type_line`) · `ambiguous` (`matches`) · `not_found` — success is **`found`**, NOT `ok` |
| `search_cards` | `colors?`, `color_mode?`, `types?`, `keywords?`, `oracle_text?`, `mana_value_min/max?`, `rarity?`, `format?`, `games?`, `page`, `page_size` (**silently capped at 50, not rejected**) | `ok` (`cards[]` + pagination) · `empty` · `invalid` |

**Stateless contract (D5 — non-negotiable):** the server holds **no** state. Pass `format`/`games` on **every** call that accepts them, and track the active `deck_id` yourself in the conversation. There is no remembered format or "active deck."

Notes that bite if ignored (carry these from 3.1 — they're identical here):
- **`semantic_search_cards.limit` / `find_similar_cards.limit` hard-cap at 50** → `limit > 50` returns `status="invalid"` (a real error). Request a generous-but-≤50 `limit` and filter down yourself.
- **`search_cards.page_size` is *silently clamped* to 50, not rejected** — page through; don't assume a >50 request errored.
- **`lookup_card_by_name` success is `found`, not `ok`** — the one tool whose success sentinel differs; don't apply the "assume `ok`" reflex or a good lookup reads as a miss.
- **Valid `games` are exactly `paper` / `arena` / `mtgo`** — any other value (e.g. `"mtga"`, `"online"`) returns `invalid` from every tool that accepts `games`.
- **`detect_synergies` reads the mainboard only** (sideboard excluded) and **requires a saved `deck_id`** — it has no pasted-list path.

### ⭐ Candidate-generator pattern (your core value-add — doubly important for synergy)

The semantic tools rank by **topical proximity, not logical conjunction** (proven in `TOOL_PERFORMANCE_REPORT.md`, 2026-06-27: a compound "removal that *also* reanimates" ask put the best "both" card **14th**). Synergy discovery is *inherently* a conjunction ("card that sacrifices **and** rewards death"), so this caveat hits hardest here:

1. **Over-fetch.** Request a generous `limit` (≤50) so the real interaction pieces are *in* the set even when they're not ranked at the top.
2. **Apply the logical-intersection filter yourself.** Read each candidate's `oracle_text`/`type_line` and keep only cards that genuinely complete the interaction; discard topical-but-irrelevant matches. Use `lookup_card_by_name` to get full detail on a borderline card before judging it.
3. **Re-rank by *fit*, then present with the interaction reason** — never echo the tool's raw order as if it were a synergy ranking. The tool's order is topical distance; yours is interaction strength.
4. **`distance` is a within-call relative signal only** (~0.44–0.61 observed). Use it to read nearest-first *inside one result set*; never treat an absolute value as a quality threshold or compare across calls.
5. **For `find_similar_cards`, pass the deck's/seed's `colors`** when there's a defined color identity — the default is unconstrained and leaks off-color cards through the seed vector.

### Format-aware & bounded output (AC 3)

- **Format-aware:** establish `format` (and optional `games`) up front and pass them on **every** `semantic_search_cards` / `find_similar_cards` / `search_cards` call so candidates are legal where the player actually plays. Format precedence (from 3.1): **infer** from the strategy/decklist/words; if **ambiguous, ask**; fall back to `"standard"` only as a last resort.
- **Bounded:** group findings into a **few synergy themes** (≈2–4), each with a **handful** of cards (≈3–5), every card carrying its one-line interaction reason. Do **not** dump 50 raw hits. If a theme has many candidates, present the strongest and offer to go deeper — the AC explicitly says *bounded to avoid overwhelming the player*.

### Graceful degradation (the skill must never dead-end)

The tools return structured statuses, not raw exceptions — handle each (mirrors 3.1's handling; reuse that wording):

- **`index_unavailable`** (semantic tools only): tell the user the semantic index isn't built and surface the tool's own build hint (real chain: import Scryfall data → `scripts/build_card_embeddings.py` → search). Then degrade so discovery still produces value:
  - For `semantic_search_cards`, **fall back to `search_cards`** — translate the synergy intent into relational filters (`types`/`keywords`/`oracle_text`/`colors`/CMC). This is the *core* fallback for this skill.
  - For `find_similar_cards`, there is **no relational similar-to-seed**; `lookup_card_by_name` the seed, then approximate with a `search_cards` filter on its type line / colors / mana value, and say it's a degraded substitute.
- **`ambiguous`** (`find_similar_cards`, `lookup_card_by_name`): present the `matches`, ask the user to pick (or re-call with `card_id`). Don't guess.
- **`empty`** (`semantic_search_cards`, `search_cards`, `find_similar_cards`): no hits — relax filters (widen colors/CMC, drop a constraint) and retry, or say so plainly. **Never invent cards.**
- **`not_found`** — two cases: *name unresolved* (`lookup_card_by_name`, or `find_similar_cards` with `seed` **absent**) → fix spelling / re-query, don't retry the same string; *seed real but unindexed* (`find_similar_cards` with `seed` **populated**) → retrying is futile, degrade like `index_unavailable` for that seed.
- **`deck_not_found`** (`detect_synergies`): the `deck_id` is stale — re-resolve via `list_decks` / confirm with the user. (`detect_synergies` `empty` = no mainboard cards: report and continue from strategy/seed reasoning instead.)
- **`invalid`**: a bad parameter — read the message and fix. Common causes: `limit > 50`, or a `games` value outside `paper`/`arena`/`mtgo`.
- **`error`** (any tool): report honestly, continue with whatever else succeeded, never pretend the failed step passed.

### Hard behavioral contracts (do not break these)

- **Never auto-add or auto-remove cards.** Synergy discovery is **observational/advisory only** — it surfaces and explains candidates; it does not touch any deck. (project-context anti-pattern: "Don't auto-add cards … without explicit user intent.")
- **`detect_synergies` needs a saved deck.** If the user wants a deck-grounded run from a *pasted* list or strategy, persisting it (`create_deck` + per-line `add_card_to_deck`) is an **explicit action requiring consent** — offer it, don't assume it. You can do strategy/seed discovery entirely without persisting.
- **Statelessness:** pass `format`/`games` on every call; track `deck_id` yourself. The server remembers nothing.
- **Stay inside the frozen tool surface.** Work within the tools' output; don't request `src/`/tool changes to finish this skill.

### Relationship to the orchestrator and sibling skills (reference, don't depend)

- The shipped `magic-deckbuilding` orchestrator (3.1) already names this skill as its deep-dive companion: *"`synergy-discovery` — deep synergy mapping and combo/engine discovery beyond the at-a-glance `detect_synergies` read."* Make this skill **deliver on that promise** so the cross-reference is honest.
- Epic note: *"the capability skills (3.2–3.4) are independent of one another."* This skill must **work standalone** and must **not** depend on `mana-curve-analysis` or `format-legality` (Stories 3.3–3.4, not yet built). You may mention them as adjacent next steps, but the loop must not block on them.

### Previous-story intelligence (Story 3.1 — directly applicable)

3.1 built the sibling skill in the same directory tree and was hardened by an adversarial code review. Carry these forward (they were the actual review findings):

- **Document every status enum you reference**, including the off-convention ones (`lookup_card_by_name` → `found`; write tools → `exists`/`not_in_deck`) — the reviewer flagged each missing/under-documented branch.
- **Don't conflate `not_found` cases** — name-unresolved vs seed-unindexed are different recoveries (3.1 Low finding).
- **Don't imply symmetric rejection** for `search_cards.page_size` (silent clamp) vs semantic `limit` (hard reject).
- **Give a format-precedence rule**, not a silent `standard` default (3.1 Medium finding — wrong format → bogus legality/availability).
- **`index_unavailable` fallback must be tool-appropriate** — `search_cards` can replace `semantic_search_cards` but is *not* a similar-to-seed replacement for `find_similar_cards` (3.1 Medium finding).
- 3.1's live dry-run used saved five-color Dragons deck **"Prismatic Dragon"** (`deck_id a6ec5c97-…`, from `list_decks`) — a convenient real deck for the saved-deck-mode dry-run here too.

### Git intelligence

Recent commits are the 3.1 skill work: `af85d58 feat: add magic-deckbuilding orchestrator skill (Story 3.1)` then `9ffe006 fix: apply Story 3.1 code-review patches (contract-fidelity hardening)` (the baseline for this story). Pattern to match: skill ships as a single `SKILL.md`; commits are Conventional Commits (`feat:`/`fix:`); `.claude/` skills are tracked in-repo. No `src/`/test/dependency changes accompanied 3.1 and none should accompany 3.2.

### Project Structure Notes

- New directory: `.claude/skills/synergy-discovery/` with `SKILL.md`. Consistent with the tracked-skills convention and the sibling `.claude/skills/magic-deckbuilding/`.
- No `src/`, test, or dependency changes — this is a content artifact. No mypy/ruff/pytest gate applies.
- Phase-1 client is Claude Code via `.mcp.json` (already wired); no UI.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.2] — story statement + the 3 ACs + the "capability skills are independent" / "orchestrator standalone" notes.
- [Source: docs/architecture.md#7] — Claude skills suite shape; [#5] tool catalog; [#3 D4/D5] focused-suite + statelessness.
- [Source: _bmad-output/project-context.md] — skill conventions, stateless-MCP rules, "don't auto-add cards" contract, RAG index prerequisite + `index_unavailable`, semantic `limit ≤ 50` cap.
- [Source: src/logic/synergy.py] — exactly what `detect_synergies` can and cannot detect (tribal/12-keyword/3-mechanic limits + excluded generic types) — the basis for this skill's value-add.
- [Source: src/mcp_server/tools/deck_analysis.py#detect_synergies] — `SynergyResult` contract (`synergies[]`, `synergy_count`, `deck_cohesion`; `ok`/`empty`/`deck_not_found`/`error`); mainboard-only.
- [Source: src/mcp_server/tools/semantic_search.py] — `semantic_search_cards` contract (`limit ≤ 50` → `invalid`; `index_unavailable`; `empty`; per-hit `distance`).
- [Source: .claude/skills/magic-deckbuilding/SKILL.md] — the sibling skill: persona/section style, verified tool table, candidate-generator pattern, graceful-degradation wording to reuse.
- [Source: _bmad-output/implementation-artifacts/3-1-magic-deckbuilding-orchestrator-skill.md#Review Findings] — the 16 contract-fidelity patches to not re-introduce.
- [Source: _bmad-output/implementation-artifacts/epic-2-retro-2026-06-24.md#6] — design-input I1 (ranked candidates with reasons; recall is breadth-over-precision).
- [Source: TOOL_PERFORMANCE_REPORT.md] — compound-intent dilution, candidate-generator pattern, `distance` within-call-only, cross-color leakage.

## Verification

A skill has no automated test harness — verify by **dry-running the workflow** (the retro's "dry-run on the real index before encoding judgment" practice). Run all three modes against the real `artificial-planeswalker` MCP server:

- **Strategy mode:** e.g. "sacrifice synergies for a Standard deck" → `semantic_search_cards` (over-fetch, `format=standard`, `games` as needed) → intersection-filter → confirm output is **a few themes, each card with a concrete interaction reason**, bounded (not a 50-card dump).
- **Seed-card mode:** "what synergizes with **[a real card]**?" → `lookup_card_by_name` (expect `found`) → `find_similar_cards`/`semantic_search_cards` → confirm candidates explain the *interaction*, not mere resemblance; confirm `colors` passed to keep on-color.
- **Saved-deck mode:** pick a real `deck_id` from `list_decks` (e.g. "Prismatic Dragon") → `detect_synergies` → read `deck_cohesion` + existing patterns → `semantic_search_cards` for **new** reinforcing pieces → confirm it surfaces synergies *beyond* the detector's tribal/keyword/3-mechanic coverage.
- Confirm `format`/`games` passed on **every** accepting call (statelessness), and **no card is added/removed** anywhere.
- Confirm graceful handling when the index is unavailable (falls back to `search_cards`; `find_similar_cards` degrades via lookup-seed approximation).
- Confirm the skill **auto-triggers** on a natural synergy request ("what combos with [card]?", "find synergies for my graveyard deck") and does **not** collide with the orchestrator's "improve my deck" trigger — i.e. the `description` is specific.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context)

### Debug Log References

No debug log required. This is a content-only skill artifact — no `src/`, test, or dependency
changes, and no `mypy`/`ruff`/`pytest` gate applies to a `SKILL.md` (per Dev Notes). Verification
was a live dry-run against the real `artificial-planeswalker` MCP server (see Completion Notes).

### Completion Notes List

**What was built:** a single Claude Code skill, `.claude/skills/synergy-discovery/SKILL.md`,
modeled on the sibling `magic-deckbuilding/SKILL.md` (3.1) for section style, the verified tool
table, the candidate-generator pattern, and the graceful-degradation wording. It encodes the
persona (Synergy Cartographer), the three invocation modes (strategy / seed-card / saved-deck),
the exact MCP tool contracts + statelessness rule, the `detect_synergies` coverage limits, the
candidate-generator (over-fetch → intersection-filter) pattern, format-aware + bounded output,
graceful degradation for every status enum, and the hard behavioral contracts.

**Contract fidelity (re-verified against `src/` ground truth, not just the 3.1 table):**
- `detect_synergies` → `src/mcp_server/tools/deck_analysis.py` + `src/logic/synergy.py`: statuses
  `ok`/`empty`/`deck_not_found`/`error`; tribal (≥5, excluded generic classes), 12 keywords,
  3 mechanic combos; mainboard-only; surfaces no new cards.
- `semantic_search_cards` / `find_similar_cards` → `semantic_search.py` / `find_similar.py`:
  `limit` hard-caps at 50 (`_MAX_LIMIT`) → `invalid`; `index_unavailable` guard before embed;
  `find_similar` `seed` populated for the "found-but-unindexed" `not_found` sub-case vs absent for
  name-unresolved; exactly-one-of `card_name`/`card_id`. Each hit's `card` already carries
  `oracle_text`/`type_line` (so intersection-filtering needs no extra lookup per card).
- `lookup_card_by_name` → `card_lookup.py`: success sentinel is **`found`**, not `ok`.

**Live dry-run (all three modes, real MCP server, index built):**
- *Strategy:* `semantic_search_cards("repeatable sacrifice outlet…", format=standard, limit=20)` →
  `ok`, but returned mostly topical-not-conjunction noise (Treasure/Clue makers, edicts,
  additional-cost sacrifice spells) — live proof of the dilution caveat and why the
  intersection-filter is the skill's core value-add. A role-targeted payoff query
  (`colors=["B"]`, `color_mode=at_most`) surfaced real aristocrats payoffs (Pactdoll Terror,
  Wicked Visitor) amid noise.
- *Seed:* `lookup_card_by_name("Mayhem Devil")` → **`found`** with full oracle text and
  `standard: not_legal` (concrete proof format-awareness matters). `find_similar_cards("Corrupted
  Conviction", format=standard, colors=["B"])` → `ok` with `seed` echoed and on-color results;
  confirmed find-similar returns resemblance/redundancy, not necessarily interaction.
- *Saved-deck:* `detect_synergies` on **Mardu Midrange v2** → `ok`, found tribal Human +
  sacrifice combo (`moderate` cohesion) but blind to the deck's Villain/lifedrain aristocrats
  engine. On **Prismatic Dragon** → `ok`, strong Dragon tribal **plus spurious `//`/`Sorcery`/
  `Instant` "tribes"** from the parser splitting double-faced type lines on `//`. This
  false-positive failure mode was folded back into the skill (read `affected_cards`, sanity-check
  `subtype`).
- *Statelessness* verified — `format`/`colors` passed and applied on every accepting call.
  *No-auto-add* verified — only read/observational tools were called; nothing mutated a deck.
  *Auto-trigger* confirmed — the harness registered the skill with the intended `description`,
  distinct from the orchestrator's "improve my deck" trigger.

**Not live-testable:** `index_unavailable` (the index is built and cannot be torn down here); its
fallback to `search_cards` is source-verified via the `index_is_populated` guards in
`semantic_search.py` / `find_similar.py`. All other statuses (`invalid`/`ambiguous`/`empty`/
`not_found`/`deck_not_found`/`error`) are documented from source.

**Scope discipline:** no `src/`, test, or dependency changes (frozen-port discipline); the only
new file is the skill. Did not reimplement the orchestrator loop — this is the focused synergy dive.

### File List

- `.claude/skills/synergy-discovery/SKILL.md` (new) — the synergy-discovery skill.

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-06-27 | 0.1 | Story drafted (create-story); status `ready-for-dev`. Ultimate context engine analysis completed — comprehensive developer guide created. |
| 2026-06-27 | 1.0 | Implemented `synergy-discovery` SKILL.md (3 modes, verified tool contracts, detector limits incl. live-found `//` false-positive, candidate-generator, bounded/format-aware output, graceful degradation, hard contracts). Tool contracts re-verified against `src/`; all three modes dry-run against the live MCP server. Status → `review`. |

## Review Findings

Adversarial code review (bmad-code-review, 2026-06-27): three parallel layers (Blind Hunter,
Edge Case Hunter, Acceptance Auditor). Acceptance Auditor confirmed all 3 ACs, every task box,
and all five Story-3.1 regression traps avoided. No critical/high blocking issues. 6 patches
(1 Medium, 5 Low), 0 decision-needed, 0 deferred, 13 dismissed (false positives / handled
in-context / spec-mandated). Conflicting reviewer claims were resolved against `src/` ground truth.

- [x] [Review][Patch] (Medium) Persist path names write tools with no failure-mode guidance — the consent-gated `create_deck` + per-line `add_card_to_deck` path is the file's only state mutation, yet `add_card_to_deck`'s common failure statuses on a pasted list (`ambiguous`/`card_not_found`/`invalid`, per `src/mcp_server/tools/deck_management.py`) are undocumented and neither write tool is in the tool table. Add brief guidance: resolve/disambiguate names first, report skipped lines, never leave a half-built deck silently. [.claude/skills/synergy-discovery/SKILL.md:255-258]
- [x] [Review][Patch] (Low) `detect_synergies` `//` false-positive mechanism misdescribed — text says the parser "splits the type line on `//`"; source `_extract_creature_types` splits on `[—-]` (em-dash/hyphen) then on whitespace, so a double-faced card's `//` separator and back-face type words (`Sorcery`/`Instant`) survive as junk tokens. The symptom and the sanity-check advice are correct; only the stated cause is wrong. [.claude/skills/synergy-discovery/SKILL.md:119-122] (src: src/logic/synergy.py:541)
- [x] [Review][Patch] (Low) `load_deck` table row over-lists `invalid` — `load_deck` only ever emits `ok`/`not_found`/`error`; the `invalid` in the shared `DeckResult` model is `create_deck`'s blank-name path (function docstring confirms). Drop `invalid` from the `load_deck` row or annotate it as never-emitted. [.claude/skills/synergy-discovery/SKILL.md:148] (src: src/mcp_server/tools/deck_management.py:311-337)
- [x] [Review][Patch] (Low) Seed-unindexed `not_found` recovery is misleading — "degrade like `index_unavailable`" would surface a "build the index" hint even though the index IS built in that case (only the one card lacks a vector). Tighten to: use the `search_cards` seed-approximation without telling the user to build the index. [.claude/skills/synergy-discovery/SKILL.md:239-241] (src: src/mcp_server/tools/find_similar.py:359-392)
- [x] [Review][Patch] (Low) "intersect the roles" wording is ambiguous — a literal set-intersection of disjoint role result-sets (sac outlets vs death payoffs are different cards) is empty by construction. Reword to "assemble the engine from the separate role searches". ("intersection-filter each result set" elsewhere is fine.) [.claude/skills/synergy-discovery/SKILL.md:56-57,178-180]
- [x] [Review][Patch] (Low) Bounded-output example undershoots its own guidance — the example shows 2 themes × 2 cards, below the stated "≈3–5 cards per theme". Bump the example or soften the number to stay self-consistent. [.claude/skills/synergy-discovery/SKILL.md:273-281]
