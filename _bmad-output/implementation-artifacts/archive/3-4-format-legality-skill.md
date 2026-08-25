---
baseline_commit: 56353e6d159999429bcef76ac11186d940fda319
---

# Story 3.4: format-legality Skill

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a player,
I want a format-legality skill,
so that I get format rules, validation, and sideboard guidance.

## Acceptance Criteria

1. **Given** `.claude/skills/format-legality/`, **when** invoked, **then** it encodes format rules and uses `validate_deck` for legality checks and sideboard guidance (FR17).
2. **Given** a deck and format, **when** run, **then** it reports legality issues (deck size, copy limits, illegal cards) with **how to comply**.
3. **Given** varying format/games, **when** run, **then** they are passed as parameters (statelessness, FR3).

## Tasks / Subtasks

- [x] Create the skill file `.claude/skills/format-legality/SKILL.md` (AC: 1)
  - [x] YAML frontmatter: `name: format-legality` + a `description` that triggers on legality/"is my deck legal"/"format rules"/"is this card banned"/"sideboard"/"can I play X in [format]"/"is this Standard/Modern/Commander legal"/rotation requests. The `description` is the **only** trigger signal Claude Code sees — make it specific to **format-legality / banlist / rotation / sideboard** intent and distinct from the `magic-deckbuilding` orchestrator ("improve my whole deck"), `synergy-discovery` ("what combos with X"), and `mana-curve-analysis` ("is my curve healthy").
  - [x] Define a tight persona/role: a **format & rules judge** that *interprets* `validate_deck`'s raw report into a plain-language verdict + concrete fixes, supplies the format rules the tool hard-codes/ignores, and gives sideboard guidance — not one that just echoes the tool's `violations`.
- [x] **Encode the format rules layer** AC1 demands — the construction rules per format (deck size, copy limit, sideboard, singleton, card pool, rotation/banlist concept) for at least Standard, Pioneer, Modern, Legacy, Vintage, Pauper, Commander, Brawl/Standard Brawl, and Limited (Draft/Sealed). This is the **knowledge** the tool lacks (the tool hard-codes a single constructed-60 ruleset; see below) (AC: 1)
- [x] **Call `validate_deck` and interpret its report into actionable guidance + how-to-comply** (AC: 2)
  - [x] Resolve a saved `deck_id` (via `list_decks`/`load_deck`) — `validate_deck` has **no pasted-list path** (saved `deck_id` only).
  - [x] Read every field of `ValidateDeckResult` → `report` (`is_legal`, `format`, `mainboard_count`, `sideboard_count`, `violations[]` with `rule`/`card_name?`/`detail`) and translate each violation into a plain verdict + a concrete fix ("cut 1 copy of X to hit the 4-max", "add 5 cards to reach the 60-card minimum", "swap illegal card Y for a legal alternative", "trim the sideboard from 17 to 15"), not a raw dump.
- [x] **Encode what `validate_deck` is blind to / hard-codes** (the skill's entire value-add basis — see "The core distinction" below): the **60-card / 15-sideboard / 4-copy limits are hard-coded regardless of `format`** (only per-card legality is format-aware); singleton (Commander/Brawl), 100-card Commander, color identity, 40-card Limited minimum, and the no-copy-limit of Limited are **not** checked; the per-card legality check is a raw `legalities.get(format) != "legal"` that is **case-sensitive**, **silently fails on an unknown format key**, and **collapses `banned`/`restricted`/`not_legal` into one message** (AC: 1, 2)
- [x] **Bake in the lowercase-format + valid-format-key contract** — `validate_deck` does `format.strip()` but **NOT** `.lower()`, and Scryfall legality keys are all lowercase. Passing `"Standard"`/`"Commander"`/`"EDH"` → `legalities.get(...)` returns `None` → **every card** flagged `format_legality`. The skill must map the user's words to a **valid lowercase Scryfall format key** before every call, and treat an "all cards illegal" result as a **likely wrong/invalid format string**, not a genuinely all-illegal deck (AC: 2, 3)
- [x] **Add the per-format reinterpretation of the tool's structural flags** (AC: 1, 2)
  - [x] **Suppress false positives:** a 40-card Limited deck flagged `min_deck_size` (tool wants 60) is *legal* in Limited; a Limited deck with 5+ of one common flagged `copy_limit` is *legal* (no 4-copy limit in Limited). Say the flag is a constructed-60 artifact, not a real Limited violation.
  - [x] **Add missed violations the tool can't see:** for Commander/Brawl, check the **singleton rule** yourself (max 1 of each non-basic, read the decklist via `load_deck`) and the **size** the tool doesn't enforce (Commander = exactly 100; the tool's ≥60 check passes a 100-card deck without verifying it); note color-identity as a rule you can flag but not fully verify from the tool.
- [x] **Document the exact `validate_deck` contract** (params incl. the lowercase-`format` requirement and `games` enum, every `status` value, the `report` shape, every `violation.rule` value and when `card_name` is `None`, mainboard-only-by-quantity for size, copy-limit-combined-across-both-boards, basics exempt) + the supporting tools it may call (`list_decks`/`load_deck`, `lookup_card_by_name` to explain *why* a card is illegal and what it IS legal in, and `search_cards`/`semantic_search_cards` to find legal replacements) (AC: 2, 3)
- [x] **Add the "explain WHY a card is illegal" path via `lookup_card_by_name`** — `validate_deck`'s `format_legality` detail only says "not legal in {format}". The skill looks the card up, reads its `legalities` dict, and explains the real reason (rotated out, never in the format, **banned**, or **restricted** — Vintage-legal at 1 copy but over-flagged by the tool) and which formats it *is* legal in ("this is Pioneer-legal, not Standard — did you mean Pioneer?") (AC: 2)
- [x] **Encode sideboard guidance as judgment (AC1) — the tool only checks sideboard *size*.** `validate_deck` verifies `sideboard_count ≤ 15` and nothing else; it gives **zero** sideboard strategy. The skill supplies it: what a sideboard is for, the 15-card max, Best-of-one (Arena, often 0 sideboard) vs Best-of-three, and how to build one for the format/meta (AC: 1)
- [x] If the skill surfaces concrete **legal replacement** cards for an illegal/over-limit card via search, apply the **candidate-generator pattern** (over-fetch ≤50 → intersection-filter by reading `oracle_text`/`type_line`; `distance` within-call-only; **pass `format`/`games`** so candidates are legal where the player plays) and the **graceful-degradation** rules (AC: 2)
- [x] **Add graceful degradation** for every status the skill can hit: `validate_deck` (`deck_not_found`/`invalid`/`error`), `lookup_card_by_name` (`found`/`ambiguous`/`not_found`), and, if search is used, `index_unavailable`/`empty`/`invalid` — never dead-end. Include the **all-cards-illegal → suspect wrong format string** recovery rule unique to this skill (AC: 2)
- [x] **Add the hard behavioral contracts:** observational/advisory only, never auto-add/remove cards, statelessness (pass `format`/`games` on every accepting call, in lowercase; track `deck_id` yourself); persisting a pasted list to get a `deck_id` needs explicit consent + per-line failure handling + never validating a half-built deck (AC: 1, 3)
- [x] Cross-reference the `magic-deckbuilding` orchestrator (deliver on its promise that this skill is "thorough legality, banlist, and rotation guidance **beyond** a single `validate_deck` check") and stay **independent** of `synergy-discovery` / `mana-curve-analysis` (AC: 1)
- [x] Verify by **dry-running** the workflow against the real MCP server (see Verification) — confirm interpretive guidance + how-to-comply (not a raw dump), the format-rules reinterpretation (Limited false-positive, Commander singleton miss), the lowercase-format gotcha caught, sideboard guidance, graceful degradation, statelessness, and no auto-mutate.

## Dev Notes

### What this story IS — and is NOT

- **IS:** a single Claude Code **skill** — a `SKILL.md` Markdown file with YAML frontmatter under `.claude/skills/format-legality/`. It encodes **judgment, format-rules knowledge, and an interpretation workflow** (spec §7, D4; FR17). The "implementation" is prose/instructions the agent follows, **not Python**.
- **IS NOT:** new tools, new `src/` code, or a restatement of the tool signature. Do **not** add MCP tools or touch `src/`. There is **no** `mypy`/`ruff`/`pytest` gate on a skill file.
- **Frozen-port discipline (Epic 1/2 lesson, reaffirmed by 3.1/3.2/3.3):** consume the *frozen* tool surface as-is. `validate_deck` checks what it checks; if its output is insufficient (it is — it's constructed-60-only), **reason past it in the skill** (that's the value-add) — do **not** change the tool or `src/`. In particular, **do not try to make `validate_deck` honor non-60 deck sizes, singleton, or color identity** — it doesn't, by design (D-1.6b), and adding it is out of scope. Supply those rules *in the skill*.
- **Scope guard (this is the focused legality dive, not the orchestrator):** 3.1 (`magic-deckbuilding`) already calls `validate_deck` as one step of its analyze→suggest→explain loop and treats illegal/over-limit cards as "mandatory cut" candidates. This skill is the **deep single-topic pass on legality** that 3.1 points to ("thorough legality, banlist, and rotation guidance beyond a single `validate_deck` check"). Don't reimplement the whole swap loop; do go deeper on format rules, banlist/rotation *reasons*, and sideboard than a single `validate_deck` call.

### Skill file format (match the established convention)

Every skill under `.claude/skills/` is a directory containing `SKILL.md` with this frontmatter shape — model it on the siblings, most directly the post-review `.claude/skills/synergy-discovery/SKILL.md` (3.2) and `.claude/skills/mana-curve-analysis/SKILL.md` (3.3):

```markdown
---
name: format-legality
description: '<one specific line that auto-invokes this for legality/banlist/rotation/sideboard help — distinct from the orchestrator and the other two capability skills>'
---

# <Persona/role title>
<role + format-rules knowledge + validate_deck contract + what-the-tool-can't-see + per-format reinterpretation + why-illegal (lookup) path + sideboard guidance + degradation + hard rules + companions>
```

- **YAML scalar gotcha (hit in 3.1, 3.2 *and* 3.3):** the `description` contains a colon ("Magic: The Gathering") and almost certainly an apostrophe — wrap it as a **single-quoted** YAML scalar and **double every apostrophe** (`''`). Validate it parses (quick `python -c "import frontmatter; frontmatter.load('.../SKILL.md')"` or eyeball against the three siblings, which all do this).
- The `description` is the **sole** trigger signal — make it specific to *format legality / banlist / rotation / sideboard* intent and clearly distinct from the orchestrator's "improve my deck", synergy-discovery's "what combos with X", and mana-curve-analysis's "is my curve healthy", so the right skill fires.
- A single `SKILL.md` is sufficient and preferred (supporting files allowed but unnecessary).

### The core distinction — why this skill exists beyond `validate_deck`

`validate_deck` is a **constructed-60 validator with hard-coded structural rules**; only the per-card legality check is format-aware (source: [src/logic/deck_validator.py](src/logic/deck_validator.py) + the tool wrapper [src/mcp_server/tools/deck_analysis.py](src/mcp_server/tools/deck_analysis.py#L254)). **Read both before writing the skill.** It checks exactly five rules:

| `violation.rule` | Exact rule (from `validate_deck`) | `card_name`? |
|---|---|---|
| `min_deck_size` | mainboard (by quantity) `< 60` — **hard-coded 60, regardless of `format`** | `None` (whole-deck) |
| `max_sideboard_size` | sideboard (by quantity) `> 15` — **hard-coded 15** | `None` (whole-deck) |
| `copy_limit` | `> 4` copies of a non-basic, **combined across mainboard + sideboard**; basics exempt (`"basic land" in type_line.lower()`) — **hard-coded 4** | card name |
| `format_legality` | `card.legalities.get(format) != "legal"` per distinct card | card name |
| `game_availability` | when `games` given, card not available on any requested platform (`set(card.games) & set(games)` empty) | card name |

`is_legal` is `True` **iff** `violations` is empty. **`_MIN_MAINBOARD = 60`, `_MAX_SIDEBOARD = 15`, `_MAX_COPIES = 4` are constants applied for every format** (D-1.6b, an explicit Phase-1 limitation in the source). That gap is the entire reason this skill exists.

**What the tool is blind to / gets wrong (your value-add must cover these):**

- **Structural rules are constructed-60, not format-aware.** Only the *per-card legality* lookup uses `format`; size/sideboard/copies do not. So:
  - **Commander / Brawl (singleton):** the tool checks `copy_limit` at **4**, so a Commander deck with 4× Sol Ring **passes** the copy check though it's illegal (singleton = max 1). It also does **not** verify the **100-card** size (its `≥60` check passes a 100-card deck blindly), the single legendary commander, or the **color-identity** rule. **You** must apply the singleton rule (read the list via `load_deck` and flag any non-basic with quantity > 1) and state the 100-card / commander / color-identity rules the tool can't enforce.
  - **Limited (Draft/Sealed):** a legal **40-card** deck is **falsely** flagged `min_deck_size` (tool wants 60), and Limited has **no 4-copy limit** (play what you opened), so a 5×-common deck is **falsely** flagged `copy_limit`. Recognize these as constructed-60 artifacts and suppress them for Limited.
- **Per-card legality is a raw `legalities.get(format) != "legal"`** with three traps:
  - **Case-sensitive.** The tool does `format.strip()` but **not** `.lower()`. Scryfall legality keys are **all lowercase**. Pass `"Standard"` / `"Commander"` / `"EDH"` and `.get()` returns `None` → **every** card flagged `format_legality`. **Always pass a lowercase, valid format key.** If a `validate_deck` result shows *every* card illegal, suspect a **wrong/invalid format string** first — not a genuinely all-illegal deck.
  - **Valid format keys (exact set present in this DB's `legalities`):** `alchemy, brawl, commander, competitivebrawl, duel, future, gladiator, historic, legacy, modern, oathbreaker, oldschool, pauper, paupercommander, penny, pioneer, predh, premodern, standard, standardbrawl, timeless, tlr, vintage`. An unknown/misspelled key (`"explorer"`, `"edh"`, `"pio"`, `"frontier"`) → `.get()` `None` → whole deck flagged illegal (no error raised). **Map the user's words to a key in this set** (EDH/Commander→`commander`, "Arena Standard"→`standard` + `games=["arena"]`, "cEDH"→`commander`, "Historic Brawl"→`brawl`, "Standard Brawl"→`standardbrawl`). Note **`explorer` is *not* a key here** — you can't validate Explorer against this data; say so rather than passing a key that flags everything.
  - **Collapses `banned` / `restricted` / `not_legal` into one message.** Scryfall values are `legal`, `not_legal`, `banned`, `restricted` (the live DB shows `legal`/`not_legal`/`banned`; `restricted` exists in the vocabulary for Vintage). The tool treats **all** non-`legal` as the same `format_legality` violation ("not legal in {format}"). It gives **no** banlist nuance and **over-flags `restricted`** cards (which are actually legal at 1 copy in Vintage). Your value-add: read the card's `legalities` via `lookup_card_by_name` and explain the *real* reason (rotated out / never in format / **banned** / **restricted**).
  - **Empty `legalities` (`{}`)** — NULL-coerced for some tokens/split cards ([src/data/schemas/card.py](src/data/schemas/card.py#L79)) → `.get()` `None` → flagged illegal. A rare edge to note, not crash on.
- **Sideboard *strategy* is entirely yours.** The tool checks only `sideboard_count ≤ 15`. AC1 demands "sideboard guidance," so the skill teaches what a sideboard is for, the 15-card max, Bo1 (Arena, often 0 SB) vs Bo3, and how to build one for the format/meta. None of that comes from the tool.

So: `validate_deck` is a **floor, not a verdict**. Never relay its `violations` verbatim as the final word — reinterpret them for *this* format and explain how to comply.

### The format rules to encode (AC1 "encodes format rules")

Bake a compact, correct rules reference into the skill. **Defer the live banlist/rotation truth to `validate_deck`'s per-card legality** (it reflects current Scryfall data) and explain rotation/banlist *conceptually* — do **not** hardcode a volatile banned-card list or the current Standard set rotation (it goes stale). Encode the *structural* rules (stable) and the *concept* of banlists/rotation:

| Format | Min deck | Copy limit | Sideboard | Singleton? | Pool / notes |
|---|---|---|---|---|---|
| Standard | 60 | 4 | ≤15 | no | recent sets; **rotates** (~3 yrs); has a banlist |
| Pioneer | 60 | 4 | ≤15 | no | RTR-forward; non-rotating; banlist |
| Modern | 60 | 4 | ≤15 | no | 8ED/Modern-forward; non-rotating; banlist |
| Legacy | 60 | 4 | ≤15 | no | nearly all cards; banlist (no restricted) |
| Vintage | 60 | 4 | ≤15 | no | all cards; **banned + restricted** (restricted = max 1) |
| Pauper | 60 | 4 | ≤15 | no | commons only; banlist |
| Commander (EDH) | **100 (exact)** | **1** (singleton) | none (traditional) | **yes** | 1 legendary commander; **color-identity** rule; banlist |
| Brawl / Standard Brawl | 100 / 60 | 1 (singleton) | none | **yes** | Brawl = Historic pool (`brawl`); Standard Brawl = Standard pool (`standardbrawl`) |
| Limited (Draft/Sealed) | **40** | **unlimited** | rest of pool | no | your opened pool; basics free |

(Keep this tight — it's a reference, not a rulebook. The point is to *reinterpret* the tool's constructed-60 output, not to relitigate every format's full rules.)

### The tool you call + its supporting cast (exact names + return contract)

Server id is `artificial-planeswalker`, so every tool is `mcp__artificial-planeswalker__<tool>`. Each returns a `status` plus a payload — **branch on `status`, never assume `ok`.** (Contract cross-checked against `src/mcp_server/` ground truth — same tables verified in 3.1/3.2/3.3.)

| Tool | Key params | `status` values (payload on success) |
|------|-----------|--------------------------------------|
| `validate_deck` | `deck_id`, `format` (default `"standard"` — **pass an explicit lowercase key**), `games?` (`paper`/`arena`/`mtgo`) | `ok` (`report`: `is_legal`, `format`, `mainboard_count`, `sideboard_count`, `violations[]` each `{rule, card_name?, detail}`) · `deck_not_found` · `invalid` (bad `games` value) · `error` |
| `list_decks` | `format?` | `ok` (`decks[]`) · `empty` · `error` |
| `load_deck` | `deck_id` | `ok` (`deck` + cards) · `not_found` · `error` |
| `lookup_card_by_name` | `card_name`, `format?`, `games?` | **`found`** (`card` w/ full `legalities` dict + `type_line`) · `ambiguous` (`matches`) · `not_found` — success is **`found`**, NOT `ok` |
| `search_cards` | `colors?`, `color_mode?` (`any`/`all`/`exact`/`at_most`), `types?`, `keywords?`, `oracle_text?`, `mana_value_min/max?`, `rarity?`, `format?`, `games?`, `page`, `page_size` (**silently capped at 50, not rejected**) | `ok` (`cards[]` + pagination) · `empty` · `invalid` |
| `semantic_search_cards` | `query`, `colors?`, `color_mode?`, `mana_value_min/max?`, `format?`, `games?`, `limit` (default 10, **max 50**) | `ok` (`cards[]`, each a `card` + `distance`, nearest-first) · `empty` · `invalid` · `index_unavailable` |

**`validate_deck` report specifics (carry these exactly):**

- **`format` must be a lowercase, valid Scryfall key** (see the list above). The tool does not lowercase it and does not validate it against the key set; a bad key silently flags every card `format_legality`.
- **`violation.rule` is one of:** `min_deck_size`, `max_sideboard_size`, `copy_limit`, `format_legality`, `game_availability`. **`card_name` is `None`** for the two whole-deck rules (`min_deck_size`, `max_sideboard_size`) and the offending card's name for the other three. Don't expect a `card_name` on a size violation.
- **Size is mainboard-only, by quantity** (a 4-of counts 4×); **sideboard is separate** (`sideboard_count`). The **copy limit is counted across mainboard + sideboard combined** (so 3 main + 2 side of one non-basic = 5 → `copy_limit`). Basics are exempt (`"basic land" in type_line`).
- **`games` on `validate_deck`** produces `game_availability` violations per card; a `games` value outside `paper`/`arena`/`mtgo` returns `status="invalid"` (not a violation).

**Notes that bite if ignored (carry forward from 3.1/3.2/3.3 — identical here):**

- **`validate_deck` reads a saved `deck_id` only** — there is no pasted-list path. Mainboard/sideboard split comes from the saved deck's `deck_cards`.
- **`lookup_card_by_name` success is `found`, not `ok`** — the one tool whose success sentinel differs; don't apply the "assume `ok`" reflex or a good lookup reads as a miss. Its `card.legalities` is the full format→status dict you need to explain *why* a card is illegal and what it IS legal in.
- **`semantic_search_cards.limit` hard-caps at 50** → `limit > 50` returns `status="invalid"` (a real error). `search_cards.page_size` is **silently clamped** to 50, not rejected — don't imply the two behave the same (one hard-rejects, one clamps).
- **Valid `games` are exactly `paper` / `arena` / `mtgo`** — any other value (`"mtga"`, `"online"`, …) returns `invalid` from every tool that accepts `games`.
- **`mana_value_min/max` / `colors` / `types` on the search tools** are how you find a *legal replacement* for an illegal card (pass `format`/`games` so the replacement is itself legal).

**Stateless contract (D5 — non-negotiable):** the server holds **no** state. `validate_deck` takes `format`/`games` as **per-call parameters** — pass them (lowercase `format`) on **every** call, and track the active `deck_id` yourself. There is no remembered format or "active deck."

### ⭐ AC2 — "how to comply" is the deliverable, not just "what's wrong"

AC2 requires the skill to report legality issues **with how to comply**. A bare violation list is a failure of this skill. Map each `violation.rule` to a concrete fix:

- **`min_deck_size`** → "add N more cards to reach the 60-card minimum" (or, for Limited, "this is *fine* — 40 is legal in Limited; the tool assumes constructed-60").
- **`max_sideboard_size`** → "trim the sideboard from {sideboard_count} to 15; cut the {N} least useful."
- **`copy_limit`** → "you have {total} copies of {card} across both boards; cut {total−4} to hit the 4-max" (or, for a singleton format, "Commander is singleton — cut to exactly 1"; or, for Limited, "no copy limit in Limited — this is legal").
- **`format_legality`** → `lookup_card_by_name` to explain the *reason* (rotated / banned / restricted / not-in-format) and offer a **legal replacement** (search with `format`/`games`), or "did you mean {other format it's legal in}?".
- **`game_availability`** → "{card} isn't on {platform}; either drop it or play on a platform where it exists ({the platforms in `card.games`})."

Rank fixes by severity: **illegal/over-limit cards and singleton breaks are mandatory** (the deck is illegal until fixed); size shortfalls are mandatory; sideboard trims are mandatory; everything else is advisory. Keep the output bounded and itemized — verdict first, then the fix list.

### Sideboard guidance (AC1) — the tool gives you only the size rule

`validate_deck` checks **only** `sideboard_count ≤ 15` (and counts sideboard copies toward the combined 4-limit). Everything about *what a sideboard is and how to build it* is the skill's judgment:

- **What it's for:** 15 cards you swap in between games of a Best-of-three match to shore up bad matchups (extra removal vs aggro, artifact/enchantment hate, graveyard hate, counter-magic vs control).
- **The 15-card max** (constructed); **Best-of-one** (much of Arena ladder) typically runs **0 sideboard** — note the Bo1/Bo3 distinction so you don't tell a Bo1 player to build 15.
- **Singleton formats** (Commander/Brawl) have **no traditional sideboard** — don't advise one; mention the 100/singleton construction instead.
- Tie guidance to the deck's colors/plan and the format meta at a high level — keep it bounded (a few archetypal sideboard categories), not a 15-card list dump.

### Optional: surface concrete legal replacements (candidate-generator pattern)

When a card is illegal/over-limit, AC2's "how to comply" can be generic ("cut it, add a legal removal spell") *or* concrete cards. To deliver on the orchestrator's "thorough legality guidance" promise, the skill **may** turn an illegal card into legal replacement candidates via `search_cards` (hard type/color/CMC filter, `format`/`games` set) or `semantic_search_cards` (conceptual — "Standard-legal removal like {illegal card}"). When you do:

1. **Over-fetch** (generous `limit` ≤ 50), then **intersection-filter** by reading each hit's `oracle_text`/`type_line` — keep only cards that fill the same role *and* are on-color/legal. Semantic tools rank by **topical proximity, not logical conjunction** (proven in `TOOL_PERFORMANCE_REPORT.md`: the best compound-match card ranked 14th), so never echo their raw order as a recommendation ranking.
2. **`distance` is a within-call relative signal only** (~0.44–0.71 observed across siblings) — nearest-first inside one result set, never an absolute quality bar or cross-call comparison.
3. **Pass `format`/`games`** so every replacement is itself legal where the player plays (this is the whole point in a legality skill).

This is an *enhancement*, not the core — the core is the legality verdict + how-to-comply. Keep suggestions bounded (a handful per problem card), each with a one-line "legal {format} stand-in for {cut card}" reason.

### Format-aware interpretation (precedence rule — don't silently default)

`validate_deck`'s structural rules are format-blind and its legality check is only as good as the `format` key you pass, so the **skill** owns format awareness:

- **Format precedence (from 3.1/3.2/3.3 review findings):** *infer* the format from the decklist / the user's words; if **ambiguous, ask** — do **not** silently assume Standard, or you'll validate a Commander/Modern/Limited deck against the wrong ruleset and emit confident-but-bogus "mandatory cut" verdicts. Fall back to `"standard"` only as a last resort when the user declines to specify.
- **Map the user's term to a valid lowercase key** *before* calling (EDH→`commander`, "Standard Brawl"→`standardbrawl`, etc.); if their format has no key in the set (e.g. Explorer), say so honestly rather than passing a key that flags everything.
- Once known, use the format to (a) pass the right `format`/`games`, and (b) reinterpret the tool's constructed-60 structural flags through that format's real rules (Limited 40-card, Commander singleton/100, etc.).

### Graceful degradation (the skill must never dead-end)

The tools return structured statuses, not raw exceptions — handle each (mirror 3.1/3.2/3.3 wording):

- **`validate_deck` `deck_not_found`** — the `deck_id` is stale/wrong. Re-resolve via `list_decks` or confirm the deck with the user; don't retry the same id.
- **`validate_deck` `invalid`** — a bad `games` value (outside `paper`/`arena`/`mtgo`). Read the message, fix the games list, retry.
- **`validate_deck` `error`** — a DB failure. Report honestly; don't fabricate a verdict.
- **All-cards-`format_legality` result (the silent trap, unique to this skill):** if `report.is_legal` is `false` and **every** distinct card has a `format_legality` violation, **suspect a wrong-case or invalid `format` string** (`"Standard"` instead of `"standard"`, or an unsupported key like `"explorer"`) before telling the user their whole deck is illegal. Re-check the format key against the valid set and re-run.
- **`lookup_card_by_name` `ambiguous`** — present the `matches`, ask the user to pick. Don't guess.
- **`lookup_card_by_name` `not_found`** — the name didn't resolve — fix spelling / re-query; don't retry the same string.
- **`index_unavailable`** (semantic search only, if used for replacements): tell the user the semantic index isn't built and surface the build chain (**import Scryfall data → `scripts/build_card_embeddings.py` → search**); **fall back to `search_cards`** (relational type/color/CMC filter, `format`/`games` set) — a near-perfect substitute for finding a legal replacement since you're filtering on hard legality anyway.
- **`empty`** (`search_cards`/`semantic_search_cards`): relax filters (widen colors/CMC) and retry, or say so. **Never invent cards.**
- **`invalid`** (search tools): a bad parameter — read the message and fix. Common causes: `limit > 50`, or a `games` value outside `paper`/`arena`/`mtgo`.

### Hard behavioral contracts (do not break these)

- **Never auto-add or auto-remove cards.** Legality analysis is **observational / advisory only** — it diagnoses and suggests fixes; it does **not** touch any deck. Proposing a cut/swap is advice; *applying* it needs explicit user confirmation. (project-context anti-pattern: "Don't auto-add cards … without explicit user intent"; analysis is observational only.)
- **`validate_deck` needs a saved deck.** To validate a *pasted* list, persisting it (`create_deck` + per-line `add_card_to_deck`) is an **explicit action requiring consent** — offer it, don't assume it. If you do persist, handle per-line write failures (`ambiguous`/`card_not_found`/`invalid`) and **never validate a half-built deck** (the size/legality math would be computed on a deck silently missing cards — exactly the failure that produces a bogus `min_deck_size` flag). Alternatively, reason about a pasted list's legality yourself (you know the format rules) without persisting.
- **Statelessness:** track `deck_id` yourself; pass `format` (lowercase) / `games` on every accepting call. The server remembers nothing.
- **Stay inside the frozen tool surface.** Work within `validate_deck`'s output; if it feels insufficient, reason past it (that's the job) — don't ask to change the tool or `src/` (and specifically don't try to give `validate_deck` format-aware size/copy/singleton rules — supply them in the skill instead).

### Previous-story intelligence (Stories 3.1, 3.2 & 3.3 — directly applicable)

All three siblings were hardened by adversarial code review (3.1's findings are the canonical checklist — [3-1-magic-deckbuilding-orchestrator-skill.md#Review Findings]); their findings are *your* pre-emptive checklist (don't re-introduce them):

- **Document every status enum you reference, including off-convention ones** (`lookup_card_by_name` → `found`, not `ok`; `validate_deck` → `deck_not_found`/`invalid`/`error`). 3.1's reviewers flagged every missing/under-documented branch (High/Medium findings).
- **Give a format-precedence rule, not a silent `standard` default** (3.1 Medium finding — wrong format → bogus "mandatory cut" verdicts). This is **the central risk for *this* skill**, since both the structural reinterpretation *and* the legality lookup depend entirely on the right format key.
- **Surface the lowercase + valid-key requirement explicitly** — it's the single most catastrophic-looking silent failure mode here (every card "illegal"), and it's unique to the legality skill. None of the siblings had to deal with it because they passed `format` through to search tools, which key into legalities the same way but rarely surface an all-illegal result so visibly.
- **Make any `index_unavailable` fallback tool-appropriate** — `search_cards` replaces `semantic_search_cards` cleanly for legal-replacement finding (you're filtering on hard legality + type/color), so the fallback is *strong* here. Say so honestly.
- **Don't imply symmetric rejection** for `search_cards.page_size` (silent clamp) vs semantic `limit` (hard reject) (3.1 Low finding).
- **Keep output bounded and self-consistent** (3.2 Low finding: examples must match the stated "handful per problem" guidance).
- **YAML single-quote + doubled-apostrophe** for the colon/apostrophe in the `description` (3.1, 3.2 *and* 3.3 hit this).
- **Dry-run on the real tools before encoding judgment** (retro practice, used by 3.1/3.2/3.3). Use saved decks from `list_decks` — **"Prismatic Dragon"** (`deck_id a6ec5c97-cda4-4694-ad88-7f26ac60a13d`, a **59-card** five-color Dragons deck) is an ideal dry-run target: at 59 mainboard it should trip a **real `min_deck_size`** violation (<60), and as a five-color pile it's a good legality/format-key test. **"Mardu Midrange v2"** is the other known saved deck.

### Git intelligence

Recent commits are the Epic-3 skill work, each shipping a single `SKILL.md` under `.claude/skills/` with a Conventional Commit:

```
56353e6 Merge pull request #3 … magic-deckbuilding-orchestrator-skill   (HEAD, baseline)
dd138a0 feat: add synergy-discovery skill (Story 3.2)
9ffe006 fix: apply Story 3.1 code-review patches (contract-fidelity hardening)
af85d58 feat: add magic-deckbuilding orchestrator skill (Story 3.1)
```

**Pattern to match:** the skill ships as a single `.claude/skills/format-legality/SKILL.md`; commit is `feat:` (Conventional Commits); `.claude/` skills are tracked in-repo. **No `src/`, test, or dependency changes** accompanied 3.1/3.2/3.3, and none should accompany 3.4 — this is a content artifact. HEAD baseline for this story is `56353e6`.

> **Note on Story 3.3:** the `mana-curve-analysis` skill (Story 3.3) is **implemented but in `review` and not yet committed** (it's untracked under `.claude/skills/mana-curve-analysis/`). Build 3.4 as the **fourth and final** Epic-3 skill; you can read 3.3's `SKILL.md` on disk as the freshest structural exemplar, but don't assume it's in git history. With 3.4, all four `FR17` skills (orchestrator + three capability skills) are complete — Epic 3 is then done pending its (optional) retrospective.

### Project Structure Notes

- New directory: `.claude/skills/format-legality/` with `SKILL.md`. Consistent with the tracked-skills convention and the siblings `.claude/skills/magic-deckbuilding/` (3.1), `.claude/skills/synergy-discovery/` (3.2), `.claude/skills/mana-curve-analysis/` (3.3).
- No `src/`, test, or dependency changes — content artifact only. No `mypy`/`ruff`/`pytest` gate applies to a `SKILL.md`.
- Phase-1 client is Claude Code via `.mcp.json` (already wired); no UI.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4] — story statement + the 3 ACs; the "capability skills (3.2–3.4) are independent" / "orchestrator (3.1) functions standalone" notes; FR17 (skills suite).
- [Source: docs/architecture.md#7] — Claude skills suite shape ("`format-legality` — format rules, validation, sideboard guidance"); [#5] tool catalog; [#3 D4/D5] focused-suite + statelessness.
- [Source: _bmad-output/project-context.md] — skill conventions, stateless-MCP rules, "don't auto-add cards / analysis is observational only" contract, semantic `limit ≤ 50` cap, `search_cards.page_size` clamp.
- [Source: src/logic/deck_validator.py] — the exact rules `validate_deck` applies: `_MIN_MAINBOARD = 60` / `_MAX_SIDEBOARD = 15` / `_MAX_COPIES = 4` **hard-coded for every format** (D-1.6b); copy-limit combined across both boards; basics exempt via `is_basic_land` (`"basic land" in type_line.lower()`); per-card legality is `card.legalities.get(format) != "legal"`; the `DeckViolation.rule` enum and which rules carry a `card_name`.
- [Source: src/mcp_server/tools/deck_analysis.py#validate_deck] — the `ValidateDeckResult` contract: `status` (`ok`/`deck_not_found`/`invalid`/`error`), the nested `DeckValidationReport` (`is_legal`/`format`/`mainboard_count`/`sideboard_count`/`violations[]`), `deck_id`+`format`(lowercase, default `"standard"`)+`games?` params, mainboard-only-by-quantity for size, the `_VALID_GAMES` enum (`paper`/`arena`/`mtgo`).
- [Source: src/data/schemas/card.py] — `Card.legalities: dict[str, str]` (format→status), `Card.games: list[str]`, and the NULL→`{}`/`[]` coercion that makes a no-legalities card read as illegal.
- [Source: cards.db `legalities`] — the **exact valid lowercase format keys** the legality check honors: `alchemy, brawl, commander, competitivebrawl, duel, future, gladiator, historic, legacy, modern, oathbreaker, oldschool, pauper, paupercommander, penny, pioneer, predh, premodern, standard, standardbrawl, timeless, tlr, vintage` (note: **no `explorer`**); legality values seen: `legal`/`not_legal`/`banned` (`restricted` exists in Scryfall's vocabulary for Vintage).
- [Source: src/mcp_server/tools/card_lookup.py / card_search.py / semantic_search.py] — contracts for the "explain why illegal" + legal-replacement path (`lookup_card_by_name` → `found` with full `legalities`; `search_cards` page_size clamp; `semantic_search_cards` `limit ≤ 50` → `invalid`, `index_unavailable`).
- [Source: .claude/skills/magic-deckbuilding/SKILL.md] — the orchestrator: persona/section style, verified tool table, candidate-generator pattern, graceful-degradation wording to reuse; **and the exact promise this skill must deliver on** ("`format-legality` — thorough legality, banlist, and rotation guidance beyond a single `validate_deck` check").
- [Source: .claude/skills/synergy-discovery/SKILL.md & .claude/skills/mana-curve-analysis/SKILL.md] — the two most-refined siblings (post-review): mirror their structure (persona → "what the tool can't see" → contract table → candidate-generator → degradation → hard rules → output example → companions).
- [Source: _bmad-output/implementation-artifacts/3-1-magic-deckbuilding-orchestrator-skill.md#Review Findings] (+ 3-2 / 3-3) — the contract-fidelity patches to NOT re-introduce (status-enum coverage incl. `found`, format precedence not silent-`standard`, tool-appropriate `index_unavailable` fallback, `page_size` clamp vs `limit` reject, bounded/self-consistent examples, YAML single-quote scalar).
- [Source: TOOL_PERFORMANCE_REPORT.md] — compound-intent dilution (best match ranked 14th), candidate-generator pattern, `distance` within-call-only, clean output contract.

## Verification

A skill has no automated test harness — verify by **dry-running the workflow** against the real `artificial-planeswalker` MCP server (the retro's "dry-run on the real index/tools before encoding judgment" practice). Read-only except where you explicitly get consent to persist:

- **Saved-deck validation + how-to-comply (AC 2):** pick a real `deck_id` from `list_decks` — **"Prismatic Dragon"** is ideal (a **59-card** deck → expect a real `min_deck_size` violation, mainboard < 60) → `validate_deck(deck_id, format="standard")` → confirm the skill **interprets** `report.violations` into a verdict + concrete fixes ("add 1 card to reach 60", per-card legality explained), not a raw dump. Confirm it reads `report.is_legal`, `mainboard_count`, and each `violation.rule`/`card_name`/`detail` correctly (and that `card_name` is `None` on the size violation).
- **The lowercase-format gotcha (the critical one):** run `validate_deck(deck_id, format="Standard")` (capital S) and confirm the skill recognizes an **all-cards-`format_legality`** result as a **wrong format string**, not a genuinely all-illegal deck — and re-runs with `"standard"`. This is the single most important behavior to prove.
- **Format reinterpretation (AC 1):** validate the same deck with `format="commander"` and confirm the skill notes the tool **does not** check singleton/100-card/color-identity and supplies those rules itself (reading the list via `load_deck` to flag any non-basic at quantity > 1). For a hypothetical 40-card Limited deck, confirm the skill calls a `min_deck_size`/`copy_limit` flag a **constructed-60 false positive**, not a real Limited violation.
- **Why-illegal explanation:** for a flagged card, `lookup_card_by_name` it and confirm the skill reads `legalities` to explain the *reason* (rotated / banned / not-in-format) and which formats it IS legal in — rather than parroting "not legal in standard".
- **Sideboard guidance (AC 1):** ask "how should I build my sideboard for {format}?" → confirm the skill **explains** purpose, the 15-card max, Bo1 vs Bo3, and singleton-format caveats — content the tool does not provide.
- **`games` + invalid handling (AC 3):** run `validate_deck(deck_id, format="standard", games=["paper"])` and confirm `game_availability` handling; run with `games=["mtga"]` and confirm the skill handles `status="invalid"` by fixing to `paper`/`arena`/`mtgo`.
- **Legal-replacement candidates (optional enhancement):** if the skill surfaces replacements for an illegal card, confirm over-fetch + intersection-filter, `format`/`games`/`colors` passed, and bounded output.
- **Graceful degradation:** confirm sensible handling of `validate_deck` `deck_not_found`/`invalid`/`error`, the all-illegal→wrong-format recovery, and (if search used) `index_unavailable` → `search_cards` fallback.
- **Statelessness & no auto-mutate:** confirm `format` (lowercase) / `games` passed on every accepting call, `deck_id` tracked in-conversation, and **no card added/removed** anywhere.
- **Auto-trigger:** confirm the skill registers with the intended `description` and fires on a natural legality request ("is my deck Standard-legal?", "is {card} banned in Modern?", "help me build a sideboard", "did this rotate out?") without colliding with the orchestrator's "improve my deck" trigger or the other two capability skills.

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context) — bmad-dev-story workflow.

### Debug Log References

Live dry-run against the `artificial-planeswalker` MCP server (read-only; no decks mutated):

- `list_decks` → confirmed **"Prismatic Dragon"** `deck_id a6ec5c97-cda4-4694-ad88-7f26ac60a13d`, **59-card** mainboard.
- `validate_deck(deck_id, format="standard")` → `is_legal:false`, **1** violation: `min_deck_size` (`card_name:null`, "Mainboard has 59 cards; standard requires at least 60"). Otherwise legal. ✔ real size violation.
- `validate_deck(deck_id, format="Standard")` (capital S) → **39** violations: `min_deck_size` + a `format_legality` on **every** distinct card, including all five basic lands (Plains/Mountain/Forest/Island/Swamp). ✔ the lowercase-format trap proven live (`report.format` echoes "Standard").
- `validate_deck(deck_id, format="commander")` → only `min_deck_size` "commander requires at least **60**" (hard-coded 60, not 100) and **no singleton flag** despite duplicate non-basics. ✔ proves the tool's structural rules are format-blind.
- `lookup_card_by_name("Armament Dragon")` → `found`, `legalities.standard == "legal"` (confirms the capital-S "Armament Dragon not legal" was a false alarm).
- `lookup_card_by_name("Lightning Bolt")` → `found`, `standard:not_legal` but `modern/legacy/pauper/vintage/commander:legal` and **`historic:banned`** — live example of `banned` ≠ `not_legal` (the nuance the tool flattens).
- `lookup_card_by_name("Lightning Bolt", format="standard")` → returned a **different** card, "Emeritus of Conflict // Lightning Bolt" (a standard-legal name-partial), NOT the real Lightning Bolt. ✔ the format param is a legality *filter* that can silently substitute a look-alike → encoded the "look up illegal cards with NO format filter" rule.

### Completion Notes List

- Implemented Story 3.4 as a single content artifact: `.claude/skills/format-legality/SKILL.md` (no `src/`, test, or dependency changes — matches the 3.1/3.2/3.3 pattern; no `mypy`/`ruff`/`pytest` gate applies to a skill file).
- Persona = **Format Judge** that interprets `validate_deck`'s constructed-60 report into a plain-language verdict + how-to-comply, supplies the per-format rules the tool hard-codes/ignores, explains banlist/rotation reasons via `lookup_card_by_name`, and gives sideboard guidance.
- Cross-checked the `validate_deck` contract against source ground truth: `src/logic/deck_validator.py` (`_MIN_MAINBOARD=60`/`_MAX_SIDEBOARD=15`/`_MAX_COPIES=4` hard-coded for every format; copy-limit combined across both boards; basics exempt; `card.legalities.get(format) != "legal"`) and `src/mcp_server/tools/deck_analysis.py` (`format.strip()` with **no** `.lower()`; `status` `ok`/`deck_not_found`/`invalid`/`error`; `_VALID_GAMES`).
- Added the lowercase-format + valid-Scryfall-key contract (full 23-key set; `explorer` explicitly **not** a key), the all-cards-illegal→wrong-format recovery rule, per-format reinterpretation (Limited 40-card false-positive suppression; Commander singleton/100/color-identity additions), the why-illegal `lookup_card_by_name` path with the no-format-filter caveat, sideboard guidance (Bo1/Bo3, singleton-no-SB), the candidate-generator pattern for legal replacements, graceful degradation for every status, and the hard behavioral contracts (observational-only/no auto-mutate, consent-to-persist, statelessness).
- Pre-empted the 3.1/3.2/3.3 review findings: documented off-convention status enums (`lookup_card_by_name`→`found`), format-precedence-not-silent-`standard`, `page_size` clamp vs `limit` hard-reject asymmetry, tool-appropriate `index_unavailable`→`search_cards` fallback, bounded/self-consistent examples, and the single-quoted/doubled-apostrophe YAML scalar.
- YAML frontmatter validated via `yaml.safe_load` across all four Epic-3 skills (parses clean; `name='format-legality'`). Skill auto-registered with its intended trigger description (confirmed by the harness skill list). All three ACs satisfied; full Verification checklist exercised against the live tools.

### File List

- `.claude/skills/format-legality/SKILL.md` (new) — the format-legality skill.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — story 3.4 status ready-for-dev → in-progress → review.
- `_bmad-output/implementation-artifacts/3-4-format-legality-skill.md` (modified) — tasks checked; Dev Agent Record, File List, Change Log, Status updated.

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-06-27 | 0.1 | Story drafted (create-story); status `ready-for-dev`. Ultimate context engine analysis completed — comprehensive developer guide created. |
| 2026-06-27 | 1.0 | Implemented `format-legality` SKILL.md (bmad-dev-story). Encoded format-rules layer, lowercase-format contract, per-format reinterpretation, why-illegal lookup path, sideboard guidance, candidate-generator + graceful degradation + hard contracts. Verified via live MCP dry-run (Prismatic Dragon: standard/Standard/commander + Lightning Bolt/Armament Dragon lookups). All ACs met. Status → `review`. |

## Review Findings (Code Review — 2026-06-27)

Adversarial review: Blind Hunter + Edge Case Hunter (source-grounded) + Acceptance Auditor. **All 3 ACs COVERED**; the source-grounded layer verified the `validate_deck` contract (hard-coded 60/15/4, combined-board copy count, basics-exempt, `legalities.get(format)` legality, the five `violation.rule` enums + `card_name=None` rules, `format.strip()`-but-not-`.lower()`, the `found`-not-`ok` sentinel, and the **real** look-alike partial-match fallback) as **exactly accurate**. Two data claims were verified against `data/cards.db` during triage (see P2, P5). Five patches + one defer; ~7 blind/edge findings dismissed as false-positives or already-handled.

### Patch

- [x] [Review][Patch] `report.is_legal` is itself constructed-60-blind — don't echo it for Limited/Commander [.claude/skills/format-legality/SKILL.md:106,121-123] — Source computes `report.is_legal = not violations`, so a legal 40-card Limited or a Commander deck that trips the **hard-coded** `min_deck_size`/`copy_limit` false-positives returns `is_legal: false`, and that boolean stays false even after the skill "suppresses" the individual violation. The skill tells the agent to reinterpret the *violations* but never warns that `is_legal` itself is unreliable for non-60 formats — an agent that leads with `is_legal` wrongly announces "illegal." Add: for Limited/Commander, trust your reinterpreted verdict, not the tool's `is_legal`. (Source: edge; Severity: **Medium** — most impactful finding.)
- [x] [Review][Patch] `restricted` parenthetical is factually wrong — the DB *does* contain `restricted` [.claude/skills/format-legality/SKILL.md:128-130] — The skill says "(the live DB shows `legal`/`not_legal`/`banned`; `restricted` exists in the vocabulary…)". **Verified against `data/cards.db`:** legality values are `not_legal` 516,210 · `legal` 361,794 · `banned` 1,265 · **`restricted` 90**. `restricted` IS present — fixing this *strengthens* the skill's own value-add (the tool over-flagging restricted Vintage cards is a real, occurring case). Correct to "all four values occur, incl. `restricted` (~90 Vintage entries)." (Source: blind, verified; Severity: Low.)
- [x] [Review][Patch] Brawl / Standard Brawl table row compresses "100 / 60" ambiguously [.claude/skills/format-legality/SKILL.md:73] — Facts are correct (Brawl = 100/Historic = `brawl`; Standard Brawl = 60/Standard = `standardbrawl`), but the single "100 / 60" cell forces a positional mapping and risks applying the 100-card floor to Standard Brawl. Split into two rows or annotate each size with its key. (Source: blind; Severity: Low.)
- [x] [Review][Patch] Loose wording "all 39 cards as illegal" — one of the 39 is the size rule, not a card [.claude/skills/format-legality/SKILL.md:407-415] — The example correctly states "39 violations: `min_deck_size` plus a `format_legality` on every distinct card" (1 size + 38 distinct), but the agent-facing line then calls it "all 39 cards." Count is grounded in the live dry-run; only the phrasing conflates a rule with a card. Tighten to "flagged every card (39 violations: the size flag + a `format_legality` per distinct card)." (Source: blind+auditor; Severity: Low.)
- [x] [Review][Patch] (optional) Hard-coded 23-key format list — add a "current DB snapshot" caveat [.claude/skills/format-legality/SKILL.md:159-163] — **Verified the 23-key list is an exact 100% match** to the DB's current `legalities` keys (`explorer` correctly absent), so it is accurate today. But the skill elsewhere warns "do not hardcode a volatile … list (it goes stale)" then presents this as a closed allow-list to *refuse* keys against. Reconcile: note it is the current DB snapshot and the real test is whether `legalities.get(key)` resolves, so a future-added key isn't wrongly rejected. (Source: blind+edge; Severity: Low.)

### Defer

- [x] [Review][Defer] `validate_deck` silently skips deck rows whose `dc.card is None` from copy/legality checks while still counting them in `mainboard_count` [.claude/skills/format-legality/SKILL.md] — deferred, pre-existing tool/data edge — Source `src/logic/deck_validator.py` does `if dc.card is None: continue` before tallying copies/legality, but `mainboard_count` sums quantity unconditionally. A saved deck with an orphaned card join (a `card_id` no longer in the DB) passes copy/legality vacuously while still counting toward the 60-card size, so a "legal" result can hide un-validated phantom cards. Obscure; a one-line caveat could be added to the "what the tool can't see" section later. (Source: edge; Severity: Low.)
