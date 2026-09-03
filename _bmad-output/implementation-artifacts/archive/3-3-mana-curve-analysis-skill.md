---
baseline_commit: 56353e6d159999429bcef76ac11186d940fda319
---

# Story 3.3: mana-curve-analysis Skill

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player,
I want a mana-curve-analysis skill,
so that I understand whether my curve is healthy and how to fix it.

## Acceptance Criteria

1. **Given** `.claude/skills/mana-curve-analysis/`, **when** invoked, **then** it explains how to read a curve, what "too top-heavy" means, and gives contextual feedback (FR17).
2. **Given** a deck, **when** run, **then** it calls `analyze_mana_curve` and interprets the result into **actionable guidance**.
3. **Given** repeated card additions, **when** feedback is given, **then** it is **throttled and contextual, not spammy**.

## Tasks / Subtasks

- [x] Create the skill file `.claude/skills/mana-curve-analysis/SKILL.md` (AC: 1)
  - [x] YAML frontmatter: `name: mana-curve-analysis` + a `description` that triggers on curve/CMC/"is my curve healthy"/"too top-heavy"/"how many lands"/"fix my curve"/"too slow"/"clunky draws" requests. The `description` is the **only** trigger signal Claude Code sees — make it specific to **curve/land/consistency** intent and distinct from the `magic-deckbuilding` orchestrator ("improve my whole deck") and from `synergy-discovery` ("what combos with X").
  - [x] Define a tight persona/role: a mana-base & curve coach that *interprets* the raw numbers into a verdict and a fix, not one that just echoes the tool's `issues`/`recommendations`.
- [x] **Teach how to read a curve** — encode the educational layer AC1 demands: what a mana curve *is* (spell-CMC histogram, lands excluded), what a healthy shape looks like **per archetype**, what **"too top-heavy"** means and why it hurts (clunky hands, slow starts, dead early turns, flood-vulnerability), and mana **screw vs flood** + **curve gaps** (AC: 1)
- [x] **Call `analyze_mana_curve` and interpret it into actionable guidance** (AC: 2)
  - [x] Resolve a saved `deck_id` (via `list_decks`/`load_deck`) — `analyze_mana_curve` has **no pasted-list path** (saved `deck_id` only).
  - [x] Read every field of `ManaCurveResult` (`distribution`, `total_lands`/`total_spells`, `average_cmc`, `land_ratio`, `playable_cards_by_turn`, `issues`, `recommendations`) and translate it into a verdict + concrete next moves (e.g. "trim two 6-drops for 2-drops", "add ~3 lands"), not a raw dump.
- [x] **Encode the throttled/contextual-feedback behavior as *judgment* (AC: 3) — there is NO MCP tool for it.** The legacy `generate_contextual_feedback` throttling logic was **dropped from the tool surface** (D-1.6g); the skill must reproduce its *spirit* in conversation: when the user iteratively adds cards and asks for feedback each time, only speak up when something **material** changed (early construction, a significant bucket shift, or a newly-appeared problem) — otherwise stay quiet. Do **not** re-dump the full analysis on every add.
- [x] **Add the format/archetype interpretation lens** — `analyze_mana_curve` is **format- and archetype-blind** (its thresholds are hard-coded for a generic 60-card deck and it takes **no `format` param**). The skill supplies the lens the tool lacks: infer archetype (aggro/midrange/control) and format, then re-read the tool's generic verdict through it (a "top-heavy" flag is *expected* for control/ramp; a low land count is *correct* for aggro) (AC: 1, 2)
- [x] **Document the exact `analyze_mana_curve` contract** (params, every `status` enum, return fields, mainboard-only-by-quantity, and the JSON int-keys-as-strings gotcha) + the supporting tools it may call (`list_decks`/`load_deck`, and optionally `search_cards`/`semantic_search_cards`/`lookup_card_by_name` to find concrete fix-it cards) (AC: 2)
- [x] **Encode what the tool is blind to** (its value-add basis): ramp/mana-rocks/dorks not counted as mana sources, MDFC "spell // land" cards distorting the land count, printed CMC ≠ effective cost (X spells, cost reducers, alt costs), format differences (Commander/Limited math), and `cmc=None` → CMC-0 bucket (AC: 1, 2)
- [x] If the skill surfaces concrete fix-it cards via search, apply the **candidate-generator pattern** (over-fetch ≤50 → intersection-filter by reading `oracle_text`/`type_line`; `distance` within-call-only; pass deck `colors`/`format`/`games`) and the **graceful-degradation** rules (AC: 2)
- [x] **Add graceful degradation** for every status the skill can hit: `analyze_mana_curve` (`empty`/`deck_not_found`/`error`) and, if search is used, `index_unavailable`/`ambiguous`/`empty`/`not_found`/`invalid`/`error` — never dead-end (AC: 2)
- [x] **Add the hard behavioral contracts:** observational/advisory only, never auto-add/remove cards, statelessness (pass `format`/`games` on every accepting call; track `deck_id` yourself); persisting a pasted list to get a `deck_id` needs explicit consent + per-line failure handling (AC: 1, 3)
- [x] Cross-reference the `magic-deckbuilding` orchestrator (deliver on its promise that this skill is "detailed curve/land/consistency tuning **beyond** the `analyze_mana_curve` summary") and stay **independent** of `synergy-discovery` / `format-legality` (AC: 1)
- [x] Verify by **dry-running** the workflow against the real MCP server (see Verification) — confirm interpretive guidance (not a raw dump), the archetype/format lens, the throttled-feedback behavior, graceful degradation, statelessness, and no auto-add.

## Dev Notes

### What this story IS — and is NOT

- **IS:** a single Claude Code **skill** — a `SKILL.md` Markdown file with YAML frontmatter under `.claude/skills/mana-curve-analysis/`. It encodes **judgment and an interpretation workflow** (spec §7, D4; FR17). The "implementation" is prose/instructions the agent follows, **not Python**.
- **IS NOT:** new tools, new `src/` code, or a restatement of the tool signature. Do **not** add MCP tools or touch `src/`. There is **no** `mypy`/`ruff`/`pytest` gate on a skill file.
- **Frozen-port discipline (Epic 1/2 lesson, reaffirmed by 3.1 & 3.2):** consume the *frozen* tool surface as-is. `analyze_mana_curve` returns what it returns; if its output feels insufficient, **reason past it in the skill** (that's the value-add) — do **not** change the tool or `src/` in this story. In particular, **do not try to add a `format` parameter to `analyze_mana_curve`** — it doesn't have one, and adding it is out of scope.
- **Scope guard (this is the focused curve dive, not the orchestrator):** 3.1 (`magic-deckbuilding`) already calls `analyze_mana_curve` as one step of its analyze→suggest→explain loop and gives an *at-a-glance* curve read. This skill is the **deep single-topic pass on the mana base** that 3.1 points to ("detailed curve/land/consistency tuning beyond the `analyze_mana_curve` summary"). Don't reimplement the whole swap loop here; do go deeper on the curve than the tool's raw `issues`/`recommendations` alone.

### Skill file format (match the established convention)

Every skill under `.claude/skills/` is a directory containing `SKILL.md` with this frontmatter shape — model it on the siblings `.claude/skills/magic-deckbuilding/SKILL.md` (3.1) and `.claude/skills/synergy-discovery/SKILL.md` (3.2):

```markdown
---
name: mana-curve-analysis
description: '<one specific line that auto-invokes this for curve/land/consistency help — e.g. "Read and tune a Magic: The Gathering deck''s mana curve. Calls analyze_mana_curve, then explains whether the curve is healthy, what ''too top-heavy'' means, the land count, and how to fix gaps — interpreted for the deck''s archetype and format. Use when the user asks if their curve/mana base is good, why their draws are clunky/slow, how many lands to run, or how to fix the curve.">'
---

# <Persona/role title>
<role + how-to-read-a-curve teaching + analyze_mana_curve contract + archetype/format lens + what-the-tool-can't-see + throttled-feedback judgment + degradation + hard rules + companions>
```

- **YAML scalar gotcha (hit in 3.1 *and* 3.2):** the `description` contains a colon ("Magic: The Gathering") and almost certainly an apostrophe — wrap it as a **single-quoted** YAML scalar and **double every apostrophe** (`''`). Validate it parses (e.g. quick `python -c "import yaml,frontmatter"` or eyeball against the two siblings, which both do this).
- The `description` is the **sole** trigger signal — make it specific to *curve / mana-base / consistency* intent and clearly distinct from the orchestrator's "improve my deck" trigger and synergy-discovery's "what combos with X", so the right skill fires.
- A single `SKILL.md` is sufficient and preferred (supporting files allowed but unnecessary).

### The core distinction — why this skill exists beyond `analyze_mana_curve`

`analyze_mana_curve` is a **generic, format-/archetype-blind heuristic** (source: [src/logic/mana_curve.py](src/logic/mana_curve.py)). Read it before writing the skill. It hard-codes these thresholds against a generic ~60-card deck, with **no notion of the deck's format or archetype**:

| Flag the tool raises | Exact rule (from `_detect_issues`) |
|---|---|
| Mana **screw** risk | `land_ratio < 35%` ("typical decks run 38–42%") |
| Mana **flood** risk | `land_ratio > 45%` |
| **High avg CMC** | `average_cmc > 3.5` **and** `land_ratio < 40%` |
| **Curve gaps** | ≥ 2 of CMC {1,2,3,4} have zero spells |
| **Top-heavy** | `> 25%` of spells cost **5+** mana |
| **Very few early plays** | spells at CMC 1 + CMC 2 ≤ **1** |

Its `recommendations` target a flat **40% lands** regardless of plan. **This is correct for a midrange 60-card deck and wrong/misleading for everything else** — and that gap is the entire reason this skill exists.

**What the tool is blind to (your value-add must cover these):**

- **Archetype.** A "top-heavy" flag is a *problem* for aggro but *expected and fine* for control/ramp. A 34% land count is *correct* for a 17-land aggro deck but the tool flags it as "mana screw risk". The tool can't tell — **you** must classify the deck (aggro / midrange / control) and re-read the verdict through that lens. The logic's own (legacy) archetype bands give you a code-grounded starting heuristic: **avg CMC ≤ 2.5 → aggro, ≤ 3.5 → midrange, else control** (`_infer_archetype`). Use them as a floor, then apply real judgment (deck contents, the user's stated plan).
- **Format.** `analyze_mana_curve` takes **only `deck_id`** — no `format`. Commander (100-card singleton, ~36–38 lands + heavy ramp), Limited (~17 lands / 40 cards = 42.5%), and Brawl all break the 38–42%/60-card assumptions. Establish the format yourself and adjust the math.
- **Ramp / mana rocks / dorks.** The tool counts a "land" only as `"Land" in type_line` — it does **not** count Llanowar Elves, Signets, Treasure-makers, or rituals as mana sources. A ramp deck legitimately running 22 lands + 10 accelerants reads as "mana screw + top-heavy" when it's perfectly fine. Flag this.
- **MDFC / "spell // land" cards.** A modal double-faced card whose `type_line` contains "Land" (e.g. `... // ... Land`) is counted as a **land**, inflating `total_lands`/`land_ratio`; one whose front is a spell may still register as a land. Note the distortion when a deck runs them.
- **Printed CMC ≠ effective cost.** X-spells use printed CMC (so `{X}{R}` reads as low), cost reducers / affinity / convoke / alternative costs make cards cheaper in practice, and `cmc=None` spells land in the **CMC-0 bucket**. The histogram is printed-cost, not play-cost.
- **`playable_cards_by_turn` is a rough proxy** — it assumes 1 land/turn on the play and is cumulative (`cards with cmc ≤ turn`); it ignores whether you'll actually have the right *colors*. Use it to illustrate early-game density, not as a guarantee.

So: `analyze_mana_curve` is a **floor, not a verdict**. Never relay its `issues`/`recommendations` verbatim as the final word — interpret them for *this* deck.

### The tool you call + its supporting cast (exact names + return contract)

Server id is `artificial-planeswalker`, so every tool is `mcp__artificial-planeswalker__<tool>`. Each returns a `status` plus a payload — **branch on `status`, never assume `ok`.** (Contract cross-checked against `src/mcp_server/` ground truth — same tables verified in 3.1/3.2.)

| Tool | Key params | `status` values (payload on success) |
|------|-----------|--------------------------------------|
| `analyze_mana_curve` | `deck_id` **only** (no `format`) | `ok` (`distribution`, `total_lands`, `total_spells`, `average_cmc`, `playable_cards_by_turn`, `land_ratio`, `issues[]`, `recommendations[]`) · `empty` (no mainboard cards) · `deck_not_found` · `error` |
| `list_decks` | `format?` | `ok` (`decks[]`) · `empty` · `error` |
| `load_deck` | `deck_id` | `ok` (`deck` + cards) · `not_found` · `error` |
| `semantic_search_cards` | `query`, `colors?`, `color_mode?` (`any`/`all`/`exact`/`at_most`), `mana_value_min/max?`, `format?`, `games?`, `limit` (default 10, **max 50**) | `ok` (`cards[]`, each a `card` + `distance`, nearest-first) · `empty` · `invalid` · `index_unavailable` |
| `search_cards` | `colors?`, `color_mode?`, `types?`, `keywords?`, `oracle_text?`, `mana_value_min/max?`, `rarity?`, `format?`, `games?`, `page`, `page_size` (**silently capped at 50, not rejected**) | `ok` (`cards[]` + pagination) · `empty` · `invalid` |
| `lookup_card_by_name` | `card_name`, `format?`, `games?` | **`found`** (`card` w/ full `oracle_text`/`type_line`) · `ambiguous` (`matches`) · `not_found` — success is **`found`**, NOT `ok` |

**Notes that bite if ignored (carry these forward from 3.1/3.2 — identical here):**

- **`analyze_mana_curve` reads the mainboard only** (sideboard excluded) and **expands by quantity** — a 4-of counts 4×. It needs a **saved `deck_id`**; there is no pasted-list path.
- **`distribution` and `playable_cards_by_turn` keys serialize as *strings* at the MCP client boundary** (JSON object keys are strings even though the Python dict keys are ints — the tool docstring calls this out explicitly). Read `distribution["5"]`, not `distribution[5]`, when parsing the result; don't let an int-key lookup silently miss.
- **`mana_value_min/max` on the search tools is your curve-targeting filter** — use it to fetch exactly the CMC slot you're trying to fill (e.g. `mana_value_max=2` for early plays).
- **`semantic_search_cards.limit` hard-caps at 50** → `limit > 50` returns `status="invalid"` (a real error). `search_cards.page_size` is **silently clamped** to 50, not rejected — don't imply the two behave the same (one hard-rejects, one clamps).
- **`lookup_card_by_name` success is `found`, not `ok`** — the one tool whose success sentinel differs; don't apply the "assume `ok`" reflex or a good lookup reads as a miss.
- **Valid `games` are exactly `paper` / `arena` / `mtgo`** — any other value (`"mtga"`, `"online"`, …) returns `invalid` from every tool that accepts `games`.

**Stateless contract (D5 — non-negotiable):** the server holds **no** state. `analyze_mana_curve` itself takes only `deck_id` (no format/games), but any `search_cards`/`semantic_search_cards`/`lookup_card_by_name` you run for fix-it candidates **must** carry `format`/`games` every call, and you track the active `deck_id` yourself. There is no remembered format or "active deck."

### ⭐ AC3 — throttled, contextual feedback is YOUR judgment (there is NO tool for it)

This is the easiest part of the story to get wrong. **There is no MCP tool that returns contextual add-a-card feedback.** The logic module *has* a `generate_contextual_feedback(...)` function ([src/logic/mana_curve.py:243](src/logic/mana_curve.py#L243)) with throttling built in — but it is **legacy and was deliberately dropped from the MCP surface** (the old auto-feedback/`toggle_auto_feedback` machinery was removed under D-1.6g / project-context "stateless tools"). **Do not look for, document, or try to call a `contextual_feedback` / `add_card` feedback tool — it does not exist.** `add_card_to_deck` returns only `ok`/`exists`/`deck_not_found`/`card_not_found`/`ambiguous`/`invalid`/`error` — no feedback payload.

So AC3 is satisfied by the skill **encoding the throttling *as conversational judgment***. Mirror the spirit of the legacy throttle (use it as the design reference, not as a tool to call):

- **Early construction (deck still small, < ~5 cards): always give a short note.** The curve isn't established yet; light guidance is welcome.
- **Otherwise, only speak up when something *material* changed:**
  - a **significant shift** in the curve's shape (the legacy rule: the added card's CMC bucket moved > 15% of the deck), **or**
  - a **newly-appeared problem** — the deck just became **top-heavy** (> 25% at 5+) or now **lacks early plays** (note: the legacy *throttle* uses a softer "≤ 3 cards at CMC 1–2" trigger here, vs the full analysis's "≤ 1" — both are in the source; the throttle is intentionally more eager to warn).
  - **Otherwise: stay quiet** (or a one-liner at most). Do **not** re-run and re-dump the whole `analyze_mana_curve` report after every single add — that is exactly the "spammy" failure AC3 forbids.
- **Priority when you do speak:** a warning (top-heavy / no early plays) outranks positive reinforcement, which outranks a neutral observation — same precedence the legacy code used.
- Keep each note **conversational and brief** (coaching tone), and tie it to the deck's inferred archetype ("for an aggro build, that 6-drop pushes your curve up — you're light on 1–2s").

Frame this in the skill as: *the user adds cards over a session; you watch the curve and chime in only at meaningful moments, not on every card.*

### Teaching layer — "how to read a curve" + "too top-heavy" (AC1)

AC1 explicitly requires the skill to **explain how to read a curve and what "too top-heavy" means** — bake this teaching content into the skill so it can educate, not just diagnose:

- **What a curve is:** a histogram of your *spells* by mana value (lands excluded). You read it left-to-right: cheap plays on the left, expensive on the right. A healthy curve lets you do something meaningful on each of the first several turns.
- **Healthy shape is archetype-dependent:** aggro wants a low curve peaking at **1–2** (act fast, close before the opponent stabilizes); midrange peaks at **2–3** with a few top-end threats; control is flatter and **higher**, leaning on cheap interaction + a small number of expensive finishers (its top-end is a feature, not a bug).
- **"Too top-heavy"** = too many expensive (5+) spells relative to cheap ones. Why it hurts: clunky opening hands, **dead early turns** (nothing to cast), you fall behind on board, and you're punished by both aggression and a stumble on lands. The tool flags > 25% at 5+; whether that's *bad* depends on archetype (a control/ramp deck living above the curve is doing it on purpose).
- **Mana screw vs flood:** too few lands → you can't cast your spells (screw); too many → you draw lands instead of action (flood). The tool's generic band is **38–42% lands** for a 60-card deck; translate to a concrete land *count* for the user (≈ 22–25 lands in 60), and adjust for archetype/format (aggro ≈ 16–18, control ≈ 25–27, Commander ≈ 36–38 + ramp, Limited ≈ 17/40).
- **Curve gaps:** an empty cheap slot (e.g. no 2-drops) means a turn with nothing to do — concretely costly in fast formats.

### Optional: surface concrete fix-it cards (candidate-generator pattern)

AC2 is satisfied by **actionable guidance** — which can be generic ("trim two 6-drops, add ~3 two-drops") *or* concrete cards. To deliver on the orchestrator's "detailed tuning" promise, the skill **may** turn a diagnosed gap into real candidates via `search_cards` (hard CMC/type/color filter — e.g. `mana_value_max=2`, on-color) or `semantic_search_cards` (conceptual — "efficient aggressive one-drop"). When you do:

1. **Over-fetch** (generous `limit` ≤ 50), then **intersection-filter** by reading each hit's `oracle_text`/`type_line` — keep only cards that actually fill the slot *and* fit the deck's plan/colors. The semantic tools rank by **topical proximity, not logical conjunction** (proven in `TOOL_PERFORMANCE_REPORT.md`: the best compound-match card ranked 14th), so never echo their raw order as a recommendation ranking.
2. **`distance` is a within-call relative signal only** (~0.44–0.61 observed) — nearest-first inside one result set, never an absolute quality bar or cross-call comparison.
3. **Pass the deck's `colors` and `format`/`games`** so candidates are on-color and legal where the player plays.

This is an *enhancement*, not the core — the core is interpreting the curve. Keep card suggestions bounded (a handful per gap), each with a one-line "fills your empty 2-slot" reason.

### Format-aware interpretation (precedence rule — don't silently default)

`analyze_mana_curve` is format-blind, so the **skill** owns format awareness:

- **Format precedence (from 3.1/3.2 review findings):** *infer* the format from the decklist / the user's words; if **ambiguous, ask** — do **not** silently assume Standard, or you'll judge a Commander/Limited deck against 60-card constructed math and give wrong land/curve advice. Fall back to `"standard"` only as a last resort when the user declines to specify.
- Once known, use the format to set the right land-count and curve expectations (see the teaching layer) and to pass `format`/`games` on any search calls.

### Graceful degradation (the skill must never dead-end)

The tools return structured statuses, not raw exceptions — handle each (mirror 3.1/3.2 wording):

- **`analyze_mana_curve` `empty`** — the deck has no mainboard cards (or only a sideboard). Report it plainly and pivot to teaching / asking for the list; don't crash or invent a curve.
- **`analyze_mana_curve` `deck_not_found`** — the `deck_id` is stale/wrong. Re-resolve via `list_decks` or confirm the deck with the user; don't retry the same id.
- **`analyze_mana_curve` `error`** — a DB failure. Report honestly; don't fabricate an analysis.
- **`index_unavailable`** (semantic search only, if used): tell the user the semantic index isn't built and surface the build chain (**import Scryfall data → `scripts/build_card_embeddings.py` → search**); **fall back to `search_cards`** (relational CMC/type/color filter) — for *curve* candidate-finding this is a near-perfect substitute since you're filtering on `mana_value` anyway.
- **`ambiguous`** (`lookup_card_by_name`): present the `matches`, ask the user to pick. Don't guess.
- **`empty`** (`search_cards`/`semantic_search_cards`): relax filters (widen colors/CMC) and retry, or say so. **Never invent cards.**
- **`not_found`** (`lookup_card_by_name`): the name didn't resolve — fix spelling / re-query; don't retry the same string.
- **`invalid`**: a bad parameter — read the message and fix. Common causes: `limit > 50`, or a `games` value outside `paper`/`arena`/`mtgo`.

### Hard behavioral contracts (do not break these)

- **Never auto-add or auto-remove cards.** Curve analysis is **observational / advisory only** — it diagnoses and suggests; it does **not** touch any deck. Proposing a swap is advice; *applying* it needs explicit user confirmation. (project-context anti-pattern: "Don't auto-add cards … without explicit user intent"; "analysis (mana curve, synergy) is observational only.")
- **`analyze_mana_curve` needs a saved deck.** To analyze a *pasted* list, persisting it (`create_deck` + per-line `add_card_to_deck`) is an **explicit action requiring consent** — offer it, don't assume it. If you do persist, handle the per-line write failures (`ambiguous`/`card_not_found`/`invalid`) and **never analyze a half-built deck** (the curve/land math would be computed on a deck silently missing cards). Alternatively, reason about a pasted list's curve yourself without persisting.
- **Statelessness:** track `deck_id` yourself; pass `format`/`games` on every search call. The server remembers nothing.
- **Stay inside the frozen tool surface.** Work within `analyze_mana_curve`'s output; if it feels insufficient, reason past it (that's the job) — don't ask to change the tool or `src/` (and specifically don't try to give `analyze_mana_curve` a `format` argument).

### Previous-story intelligence (Stories 3.1 & 3.2 — directly applicable)

Both siblings were hardened by adversarial code review; their findings are *your* pre-emptive checklist (don't re-introduce them):

- **Document every status enum you reference, including off-convention ones** (`lookup_card_by_name` → `found`, not `ok`). 3.1/3.2 reviewers flagged every missing/under-documented branch.
- **Give a format-precedence rule, not a silent `standard` default** (3.1 Medium finding — wrong format → bogus land/curve advice). Especially important here, since the tool itself is format-blind.
- **Make any `index_unavailable` fallback tool-appropriate** — `search_cards` replaces `semantic_search_cards` cleanly for curve gaps (you're filtering on `mana_value`), so the fallback is *stronger* here than in 3.2. Say so honestly.
- **Don't imply symmetric rejection** for `search_cards.page_size` (silent clamp) vs semantic `limit` (hard reject).
- **Keep output bounded and self-consistent** (3.2 Low finding: examples must match the stated "handful per theme/gap" guidance).
- **YAML single-quote + doubled-apostrophe** for the colon/apostrophe in the `description` (both 3.1 and 3.2 hit this).
- **Dry-run on the real index before encoding judgment** (retro practice, used by both 3.1 and 3.2). 3.1/3.2 used saved decks **"Prismatic Dragon"** (`deck_id a6ec5c97-…`, a 59-card five-color top-heavy Dragons deck — `average_cmc` 4.66, distribution `{1:2, 2:1, 3:2, 4:5, 5:17, 6:8}`, flagged "Top-heavy curve: 71.4% of spells cost 5+") and **"Mardu Midrange v2"** from `list_decks`. **"Prismatic Dragon" is an ideal dry-run target here** — it's a real, already-flagged top-heavy curve to interpret (and a great test of the archetype lens: is 71% at 5+ a problem, or is this a ramp/Dragons top-end?).

### Git intelligence

Recent commits are the Epic-3 skill work, each shipping a single `SKILL.md` under `.claude/skills/` with a Conventional Commit:

```
56353e6 Merge pull request #3 … magic-deckbuilding-orchestrator-skill
dd138a0 feat: add synergy-discovery skill (Story 3.2)
9ffe006 fix: apply Story 3.1 code-review patches (contract-fidelity hardening)
af85d58 feat: add magic-deckbuilding orchestrator skill (Story 3.1)
```

**Pattern to match:** the skill ships as a single `.claude/skills/mana-curve-analysis/SKILL.md`; commit is `feat:` (Conventional Commits); `.claude/` skills are tracked in-repo. **No `src/`, test, or dependency changes** accompanied 3.1 or 3.2, and none should accompany 3.3 — this is a content artifact. HEAD baseline for this story is `56353e6`.

### Project Structure Notes

- New directory: `.claude/skills/mana-curve-analysis/` with `SKILL.md`. Consistent with the tracked-skills convention and the siblings `.claude/skills/magic-deckbuilding/` (3.1) and `.claude/skills/synergy-discovery/` (3.2).
- No `src/`, test, or dependency changes — content artifact only. No `mypy`/`ruff`/`pytest` gate applies to a `SKILL.md`.
- Phase-1 client is Claude Code via `.mcp.json` (already wired); no UI.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3] — story statement + the 3 ACs; the "capability skills (3.2–3.4) are independent" / "orchestrator (3.1) functions standalone" notes.
- [Source: docs/architecture.md#7] — Claude skills suite shape; [#5] tool catalog; [#3 D4/D5] focused-suite + statelessness; [D-1.6g] drop of the auto-feedback/active-deck machinery.
- [Source: _bmad-output/project-context.md] — skill conventions, stateless-MCP rules, "don't auto-add cards / analysis is observational only" contract, RAG index prerequisite + `index_unavailable`, semantic `limit ≤ 50` cap.
- [Source: src/logic/mana_curve.py] — the exact heuristics `analyze_mana_curve` applies (`_detect_issues`/`_generate_recommendations` thresholds: 35/45% land bands, >3.5 avg-CMC, ≥2 curve gaps, >25% top-heavy, ≤1 early plays) **and** the legacy `generate_contextual_feedback` throttle (`<5` cards / >15% bucket shift / new problem; archetype bands ≤2.5/≤3.5) that AC3 must reproduce *as judgment* (it is NOT an MCP tool).
- [Source: src/mcp_server/tools/deck_analysis.py#analyze_mana_curve] — the `ManaCurveResult` contract: `status` (`ok`/`empty`/`deck_not_found`/`error`), all eight analysis fields, `deck_id`-only params (no `format`), mainboard-only-by-quantity, and the JSON int-keys-as-strings note on `distribution`/`playable_cards_by_turn`.
- [Source: src/mcp_server/tools/card_search.py / semantic_search.py / card_lookup.py] — contracts for the optional fix-it-candidate search path (`search_cards` page_size clamp; `semantic_search_cards` `limit ≤ 50` → `invalid`, `index_unavailable`; `lookup_card_by_name` → `found`).
- [Source: .claude/skills/magic-deckbuilding/SKILL.md] — the orchestrator: persona/section style, verified tool table, candidate-generator pattern, graceful-degradation wording to reuse; **and the exact promise this skill must deliver on** ("`mana-curve-analysis` — detailed curve/land/consistency tuning beyond the `analyze_mana_curve` summary").
- [Source: .claude/skills/synergy-discovery/SKILL.md] — the most-refined sibling (post-review): mirror its structure (persona → "what the tool can't see" → contract table → candidate-generator → degradation → hard rules → output example → companions).
- [Source: _bmad-output/implementation-artifacts/3-1-magic-deckbuilding-orchestrator-skill.md#Review Findings] & [3-2-synergy-discovery-skill.md#Review Findings] — the contract-fidelity patches to NOT re-introduce (status-enum coverage, format precedence, tool-appropriate fallback, page_size vs limit, bounded/self-consistent examples, YAML scalar).
- [Source: TOOL_PERFORMANCE_REPORT.md] — compound-intent dilution (best match ranked 14th), candidate-generator pattern, `distance` within-call-only, clean output contract.

## Verification

A skill has no automated test harness — verify by **dry-running the workflow** against the real `artificial-planeswalker` MCP server (the retro's "dry-run on the real index/tools before encoding judgment" practice):

- **Saved-deck interpretation (AC 2):** pick a real `deck_id` from `list_decks` — **"Prismatic Dragon"** is ideal (a known top-heavy curve) → `analyze_mana_curve(deck_id)` → confirm the skill **interprets** the result (verdict + archetype/format lens + concrete next moves), rather than echoing the raw `issues`/`recommendations`. Confirm it correctly reads `distribution` despite **string keys** at the JSON boundary, and that it questions whether "71% at 5+" is a real fault for *this* deck (Dragons top-end / ramp) vs a generic flag.
- **Teaching (AC 1):** ask "how do I read my curve / is it too top-heavy?" → confirm the skill **explains** what a curve is, what top-heavy means and why it hurts, and screw/flood/gaps — not just numbers.
- **Throttled feedback (AC 3):** simulate the user adding several cards in a row and asking for feedback each time → confirm the skill **only** comments at material moments (early construction, a real shape shift, a newly-appeared problem) and **stays quiet otherwise** — it does NOT re-dump the full analysis on every add, and it does NOT try to call a (non-existent) contextual-feedback tool.
- **Fix-it candidates (optional enhancement):** if the skill surfaces concrete cards for a gap, confirm over-fetch + intersection-filter, `format`/`games`/`colors` passed, and bounded output.
- **Graceful degradation:** confirm sensible handling of `analyze_mana_curve` `empty`/`deck_not_found`/`error`, and (if search is used) `index_unavailable` → `search_cards` fallback.
- **Statelessness & no-auto-add:** confirm `format`/`games` passed on every search call, `deck_id` tracked in-conversation, and **no card added/removed** anywhere.
- **Auto-trigger:** confirm the skill registers with the intended `description` and fires on a natural curve request ("is my curve healthy?", "how many lands should I run?", "why are my draws so clunky?") without colliding with the orchestrator's "improve my deck" trigger or synergy-discovery's "what combos with X".

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context)

### Debug Log References

Live dry-run against the `artificial-planeswalker` MCP server (read-only — no deck mutated):

- `list_decks` → confirmed "Prismatic Dragon" `deck_id a6ec5c97-cda4-4694-ad88-7f26ac60a13d` (59-card five-color Dragons).
- `analyze_mana_curve(a6ec5c97…)` → `status: ok`, `distribution {"1":2,"2":1,"3":2,"4":5,"5":17,"6":8}` (**string keys confirmed at the JSON boundary**), `total_spells 35` / `total_lands 24`, `average_cmc 4.66`, `land_ratio 40.68%`, single issue `"Top-heavy curve: 71.4% of spells cost 5+ mana"`. Grounded the output example and the archetype-lens reading (top-end is the ramp/Dragons plan, not a fault).
- `search_cards(colors=[R,B], color_mode=at_most, types=[Creature], mana_value_max=2, format=standard, page_size=5)` → `status: ok`, 334 matches paginated to 5 — confirmed the curve-targeting `mana_value_max` filter and `page_size` bound for the fix-it-candidate path.
- `semantic_search_cards("efficient cheap removal…", colors=[R,B], mana_value_max=2, format=standard, limit=5)` → `status: ok` (index **live**, not `index_unavailable`); ranked a pump spell (Full Bore) and a draw spell (Demand Answers) **above** real removal (Fell) — a live demonstration of the topical-proximity-not-conjunction caveat the skill warns about. Observed `distance` 0.67–0.71, so corrected the skill's distance note (sibling skills cited ~0.44–0.61; widened to ~0.44–0.71 and reframed as "ordering within a call, not an absolute bar").
- YAML frontmatter validated via PyYAML (`name`/`description` only; colon + doubled-apostrophe scalar parses clean). Skill auto-registered with its curve-specific `description`, distinct from the `magic-deckbuilding` and `synergy-discovery` triggers.

### Completion Notes List

- Delivered a single content artifact — `.claude/skills/mana-curve-analysis/SKILL.md` — per the established `.claude/skills/` convention (siblings 3.1/3.2). No `src/`, test, or dependency changes (none apply to a SKILL.md; there is no mypy/ruff/pytest gate).
- **AC1 (teaching + "too top-heavy"):** "How to read a curve" section explains what a curve is (spell histogram, lands excluded), healthy shape **per archetype**, what "too top-heavy" means and **why it hurts** (clunky hands, dead early turns, fall behind), and mana screw/flood + curve gaps with concrete land *counts*.
- **AC2 (call + interpret into actionable guidance):** documents the exact `analyze_mana_curve` contract (`deck_id`-only, all eight fields, every `status` enum, mainboard-only-by-quantity, **string-keyed `distribution`/`playable_cards_by_turn`**), a resolve→analyze→interpret workflow that produces a verdict + concrete moves (not a raw dump), the archetype/format lens the tool lacks, an explicit "what the tool is blind to" section (ramp/rocks/dorks, MDFC spell//land, printed≠effective CMC, format math, `cmc=None`→0 bucket), and an optional candidate-generator path (over-fetch ≤50 → intersection-filter; `mana_value` targeting; pass `colors`/`format`/`games`).
- **AC3 (throttled, contextual feedback):** encoded as **conversational judgment**, explicitly noting there is **no MCP tool** for it (legacy `generate_contextual_feedback` dropped under D-1.6g). Reproduces the legacy throttle's spirit: always-note in early construction (<5 cards), otherwise speak up only on a material shift (>15% bucket move) or a newly-appeared problem (top-heavy >25% at 5+, or the softer throttle trigger ≤3 at CMC 1–2), warning > positive > neutral precedence, stay quiet otherwise — never re-dump the full report per add.
- Graceful degradation for every status the skill can hit; hard behavioral contracts (observational/advisory only, never auto-add/remove, statelessness, persist-needs-consent with per-line failure handling, stay inside the frozen tool surface — do not give `analyze_mana_curve` a `format` arg).
- Pre-empted the 3.1/3.2 review findings: full status-enum coverage incl. `lookup_card_by_name` → `found`; format-precedence rule (infer → ask → `standard` last); tool-appropriate `index_unavailable` → `search_cards` fallback (stronger here since the filter is `mana_value`); `page_size` silent-clamp vs semantic `limit` hard-reject distinguished; bounded/self-consistent output example; single-quoted + doubled-apostrophe YAML scalar.
- Verification was a live dry-run (a SKILL.md has no automated test harness) — see Debug Log References.

### File List

- `.claude/skills/mana-curve-analysis/SKILL.md` (new) — the mana-curve-analysis skill.

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-06-27 | 0.1 | Story drafted (create-story); status `ready-for-dev`. Ultimate context engine analysis completed — comprehensive developer guide created. |
| 2026-06-27 | 1.0 | Implemented `.claude/skills/mana-curve-analysis/SKILL.md` (AC1–AC3); verified via live MCP dry-run (Prismatic Dragon curve interpretation, candidate-generator path, YAML validation). Status → `review`. |

## Review Findings (Code Review — 2026-06-27)

Adversarial review: Blind Hunter + Edge Case Hunter (source-grounded) + Acceptance Auditor. **All 3 ACs COVERED**; the source-grounded layer verified the documented `analyze_mana_curve` contract (thresholds, archetype bands, throttle triggers, field names, string-key serialization) as **exactly accurate**. One actionable patch; 13 blind/edge findings dismissed as false-positives (distinct-concept land bands 35/45 vs typical 38–42; ≤1 vs ≤3 early-play triggers are real, context-distinct source values; the Prismatic-Dragon example arithmetic verifies — 35 spells/24 lands/avg 4.66/71.4% at 5+ all correct).

### Patch

- [x] [Review][Patch] `distribution` omits zero-spell CMC buckets — guard absent keys with `.get(k, 0)` [.claude/skills/mana-curve-analysis/SKILL.md:171-174] — The skill correctly warns to read `distribution["5"]` (string key) not `distribution[5]`, but `analyze_mana_curve` builds `distribution` **sparsely** (source `src/logic/mana_curve.py`): a CMC slot with zero spells is **absent**, not `0`. An agent summing `distribution["1"] + distribution["2"]` on a deck with no 2-drops hits a missing key — the exact silent-miss the note warns against, left open for present-vs-absent. Add: read buckets via `.get("2", 0)`. (Source: edge; Severity: Low–Medium.)
