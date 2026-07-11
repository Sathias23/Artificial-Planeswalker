# Assessing Magic: The Gathering Deck Power Level — A Technical Research Paper for the "Artificial Planeswalker" MCP Server

## Executive Summary

Deck "power level" in Magic: The Gathering is best modeled not as a single number but as a **multi-dimensional, format-normalized estimate with an explicit confidence interval**. The single most important architectural recommendation for Artificial Planeswalker is a **hybrid pipeline**: deterministic heuristics and data lookups produce fast, explainable signals (mana curve, ramp/draw/interaction counts, Game Changer membership, two-card combo detection, mana-base quality); these signals are combined into both a categorical label (the format's native rubric — WotC Commander Brackets for EDH, archetype/tier for 60-card formats) and a continuous 0–100 "absolute" score that is deliberately anchored per-format so that a "strong-for-Standard" deck does not masquerade as absolutely powerful.

Three findings drive the design:

1. **Format sets the baseline.** The absolute power ceiling rises Standard < Pioneer < Modern < Legacy < Vintage, driven by card-pool size, ban philosophy, and mana-base quality; Commander/cEDH, Pauper, and Limited sit on separate axes. Any cross-format score must apply a per-format offset/scale.
2. **The community has already converged on structured rubrics.** The old subjective 1–10 scale is being replaced by WotC's official 5-tier Commander Brackets (Feb 2025, updated through Feb 2026) built around a curated **Game Changers** list and hard triggers (mass land denial, two-card combos, extra-turn chains). This is directly machine-checkable.
3. **Excellent free data and combo APIs exist** (Scryfall, EDHREC JSON endpoints, Commander Spellbook `find-my-combos`, MTGJSON, 17Lands), making a heuristic+data tool tractable today; ML and full-game simulation are valuable as *validation and calibration* layers, not as the primary v1 engine.

---

## 1. Power-Level Theory and Cross-Format Scaling

### 1.1 What "power level" actually means

Power level conflates several distinct properties that a good tool should separate:

- **Speed** — how fast the deck can win (average/goldfish win turn).
- **Consistency** — probability of executing the game plan (hypergeometric access to key pieces + mana).
- **Resilience** — ability to recover from disruption (removal, counters, board wipes).
- **Interaction density** — how much the deck can disrupt opponents.
- **Ceiling vs. floor** — best-case explosive draws vs. typical draws.

In singleton multiplayer Commander, "power" also trades against a *social* axis: the format is explicitly "social-first," so a purely win-oriented metric is incomplete. As one Star City Games analysis put it, victory "takes a backseat to social interaction and meaningful participation" in non-cEDH Commander.

### 1.2 The cross-format power hierarchy

The canonical constructed hierarchy by *absolute* power:

**Standard < Pioneer < Modern < Legacy < Vintage**

- **Standard**: only the most recent ~5–8 sets; rotates annually; deliberately balanced; lowest absolute ceiling.
- **Pioneer**: non-rotating, Return to Ravnica (2012) forward; "middle ground between Standard and Modern."
- **Modern**: 2003 (Mirrodin/8th Edition) forward, boosted by Modern Horizons sets; "power level above Standard … without being broken." Turn-4 is the classic "fundamental turn."
- **Legacy**: eternal, nearly all cards; dual lands, Force of Will, Brainstorm; small ban list. Games commonly resolve turns 5–7 despite turn-1 combo potential.
- **Vintage**: eternal; the only format where the Power Nine and other degenerate cards are legal (restricted to 1 copy). Highest absolute ceiling and fastest kills.

Off the main axis:

- **Pauper**: commons only — much lower absolute power ceiling, but still a tuned constructed format with its own meta.
- **Commander/EDH**: 100-card singleton, 40 life, multiplayer (3–5), 1 copy max. Power spans from precon-casual to **cEDH** (turn 1–4 kills), so it needs its *own* internal scale (Brackets).
- **Limited (Draft/Sealed)**: 40-card decks from a restricted, random pool; "power" is relative to the specific set and measured empirically (17Lands win rates), not against constructed.

### 1.3 What drives the baseline

Four levers set each format's baseline:

1. **Card-pool size & quality** — more sets = more degenerate cards and better answers.
2. **Ban/restricted philosophy** — Standard/Modern ban aggressively for power; Vintage restricts instead of bans; Commander uses a small ban list plus the Brackets/Game Changers overlay.
3. **Mana-base quality** — the single biggest hidden lever. Fetch+dual/shock mana in Legacy/Vintage enables greedy multicolor curves that Standard cannot support, raising both speed and consistency.
4. **Format speed** — the empirical "average turn the game ends" is a proxy for baseline power. Rough community consensus: Vintage/cEDH fastest (turns 1–4), Legacy/Modern mid (turns 4–7), Standard slower (turns 5–7+), casual Commander slowest (8+ turns).

**Design implication:** the tool must first identify the format (or accept it as input), then apply a **format profile** containing: legal card pool, ban/restricted list, a baseline offset, and an expected win-turn distribution. A raw heuristic score is then interpreted *relative to that profile* for the "for-format" rating and *shifted by the offset* for the "absolute" rating.

---

## 2. Options for Representing Power Level (with trade-offs)

This is the menu the user asked for. Each option is independently implementable; the recommended architecture (§7) combines several.

### Option A — Commander 1–10 scale (legacy community standard)
- **What:** informal 1 (jank) to 10 (cEDH).
- **Pros:** universally understood; single scalar.
- **Cons:** notoriously subjective — "what's a 7?" is a running joke; clusters heavily around 7; no shared definition; meaningless without a reference playgroup. Multiple sources (Star City Games, MTG Rocks, TappedOut) document its collapse.
- **Verdict:** Support as a *derived, secondary* output for familiarity; never the primary representation.

### Option B — WotC Commander Brackets (official categorical, 2025+)
- **What:** 5 tiers — **Bracket 1 Exhibition, 2 Core, 3 Upgraded, 4 Optimized, 5 cEDH** — gated by hard criteria: count of **Game Changers**, presence of **mass land denial**, **extra-turn chains**, and **two-card infinite combos**, plus expected win-turn "vibes."
- **Pros:** official, concrete, machine-checkable, community-adopted; already integrated by Archidekt/Moxfield/Scryfall (`is:gamechanger`).
- **Cons:** intentionally not a fine gradient; explicitly *intent-based* (WotC stresses it is "not an exact science"); Bracket 5 (cEDH) is self-selected and cannot be reliably auto-detected from cards alone.
- **Verdict:** The primary representation *for Commander*.

### Option C — Continuous 0–100 (or 0–10 float) score
- **What:** a weighted aggregate of dimension sub-scores.
- **Pros:** fine-grained; sortable; supports thresholds and diffs (useful for "did my edit make the deck stronger?").
- **Cons:** false precision risk; needs calibration/anchoring or the number is arbitrary; must be format-anchored.
- **Verdict:** Recommended as the *absolute* cross-format scalar, always paired with a confidence interval and the categorical label.

### Option D — Multi-dimensional vector (radar profile)
- **What:** separate scores for **speed, consistency, resilience, interaction, mana efficiency, card advantage, combo potential**.
- **Pros:** most informative; matches how expert players actually reason; avoids collapsing orthogonal properties; naturally explains *why* a deck is strong.
- **Cons:** harder to compare two decks with one glance; needs a UI or structured output to be useful.
- **Verdict:** Recommended as the core internal representation; the scalar and label are projections of it.

### Option E — Percentile / relative-to-meta
- **What:** "this deck is stronger than X% of tracked decks for this commander/format."
- **Pros:** intuitive; naturally format-normalized; leverages EDHREC/17Lands/tournament corpora.
- **Cons:** requires a reference corpus and is only as good as it; meta-dependent and time-varying.
- **Verdict:** Excellent *complementary* output where corpus data exists (Commander via EDHREC, Limited via 17Lands, 60-card via MTGTop8/Goldfish).

### Option F — Descriptive/categorical labels
- **What:** words like "Unfocused / Focused / Tuned / High-Power / Competitive," or Commander Spellbook's combo tags (Casual/Precon/Oddball/Powerful/Spicy/Ruthless).
- **Pros:** honest about imprecision; good for humans and LLM agents.
- **Cons:** coarse; boundary cases ambiguous.
- **Verdict:** Use as the human-facing summary layer atop the numeric/vector core.

### Option G — Uncertainty representation (essential for an "approximate" tool)
- **What:** attach a **confidence interval** or qualitative confidence (low/med/high) to every score, plus flags for what reduced confidence (unknown cards, missing meta data, combo ambiguity, custom/un-cards).
- **Pros:** epistemically honest; the user explicitly wants an *approximate* assessment; prevents over-trust; ideal for agent consumption.
- **Cons:** slightly more complex output schema.
- **Verdict:** Mandatory. Represent as `{score, low, high, confidence, reasons[]}`.

---

## 3. Implementation Approaches (ordered by complexity)

### 3.1 Heuristic / rule-based (v1 core — build this first)

Deterministic, fast, fully explainable. Compute from Scryfall card objects + oracle-text parsing:

**Deck-composition counts (per Command Zone / 8×8 templates):**
- **Mana curve** and **average mana value (MV)**.
- **Land count** and **ramp count** (mana rocks, dorks, land-fetch).
- **Card-draw / advantage** count.
- **Removal / interaction** count (spot removal, board wipes, counters), with an **instant-speed ratio** and **CMC distribution** of answers.
- **Tutor density** (note: WotC *removed* tutor restrictions from Brackets in Oct 2025, relying on Game Changers to catch the efficient ones — so tutors inform the *soft* score, not the bracket floor).
- **Win-condition identification** (combo pieces, "you win the game" text, evasive/haymaker finishers).

**Community heuristics worth encoding:**
- **8×8 theory** (and 7×9 / 9×7 variants): 1 commander + ~35 lands + 8 categories × 8 cards = 64 spells. Deviations flag structural gaps (e.g., <6 ramp or <6 interaction in Commander is a weakness signal). The "Command Zone template" (≈10 ramp, ≈10 draw, ≈10 interaction incl. ≥3 board wipes, ~37 lands) is a good reference vector.
- **Rule of 8 / redundancy:** 4 copies → 39.9% to see one in the opening 7; 8 copies (or functional equivalents) → 65.4%; 12 → 80.9%. Drives consistency scoring in singleton formats where "functional equivalents" substitute for 4-ofs.
- **Karsten land-count formula.** Devised by Frank Karsten (Pro Tour Hall of Famer with a PhD in Operations Research), derived via regression on tens of thousands of winning tournament decklists. **99-card Commander:** `Lands ≈ 31.42 + 3.13 × avgMV − 0.28 × (cheap card draw + ramp)`. **60-card:** `Lands ≈ 19.59 + 1.90 × avgMV − 0.28 × (cheap card draw + ramp)`. Flag mana-screw/flood risk when actual land count deviates from the recommendation.

**Hard bracket triggers (Commander):** detect mass land denial, extra-turn chains, and count Game Changers to set the bracket floor exactly per the WotC decision tree.

### 3.2 Card-level power metrics (data-driven scoring)

Score individual cards and aggregate:

- **Game Changers membership** — Scryfall `is:gamechanger` (also `isGameChanger` in MTGJSON). The list launched at **exactly 40 cards on February 11, 2025** (five white, nine blue, seven black, two red, three green, four multicolor, ten colorless) and stands at **exactly 53 cards as of the February 9, 2026 update**, synced live via Scryfall's `is:gamechanger` query. This is the strongest single card-level power signal in Commander. Per the bracket rules, Game Changers **are not allowed in Brackets 1–2, are limited to 3 per deck in Bracket 3, and are unrestricted in Brackets 4–5** — so a single Game Changer automatically makes a deck Bracket 3 or higher.
- **EDHREC inclusion & synergy/lift scores** — from `json.edhrec.com` endpoints. Inclusion rate = staple-ness; synergy (`synergy = %-in-commander-decks − %-in-color-identity-decks`, now being migrated to "lift") = build-around importance. Also exposes **salt scores** (annual survey, 0–4) as a proxy for oppressive/format-warping cards.
- **17Lands GIH WR / OH WR / IWD** — the empirical gold standard for *Limited* card power; per-set. GIH WR (games-in-hand win rate) is the least-biased single metric; IWD (improvement-when-drawn) isolates a card's marginal impact.
- **Format staples / tournament inclusion rates** — from MTGGoldfish / MTGTop8 metagame pages for 60-card formats.
- **Card price as a weak power proxy** — high price often correlates with power/demand (Reserved List staples, fetches), but is noisy (collectability, scarcity). Use only as a low-weight tiebreaker, never a primary signal.
- **EDHREC rank** (also in MTGJSON as `edhrecRank`, `edhrecSaltiness`) — general Commander playability.

### 3.3 Combo detection (data-driven, high value)

**Commander Spellbook `find-my-combos`** is the key primitive:
- `POST https://backend.commanderspellbook.com/find-my-combos` with JSON body `{ "commanders": [...], "main": [...] }`. Helper endpoints `card-list-from-text` and `card-list-from-url` parse a pasted list or a Moxfield/Archidekt/Goldfish URL into those fields.
- Response `results` buckets combos into **`included`** (fully present), **`almostIncluded`** (one card away, in color identity), and change-commander/add-color buckets. (Verify exact camelCase keys against the live Swagger at `backend.commanderspellbook.com/schema/swagger/`.)
- Per-variant fields: `id` (e.g. `1234-5678`), `produces`/results, `easy_prerequisites` + `notable_prerequisites`, `description` (steps), `mana_needed`, `identity`, `popularity` (EDHREC deck count), `spoiler` (unreleased), per-format legality flags (`legal_commander`, `legal_modern`, …), prices, and a **`bracket_tag`** + integer `bracket`.
- **Bracket-tag → power mapping** (verbatim from backend source `variant.py`): `RUTHLESS`→4, `SPICY`→3, `POWERFUL`→3, `ODDBALL`→2, `PRECON_APPROPRIATE`→2, `CASUAL`→1.
- The backend also exposes an **`estimate-bracket`** endpoint for whole-deck bracket estimation.
- **No auth/API key required; MIT-licensed; no published hard rate limit** — implement polite throttling + 429 backoff. The database exposes **over 97,606 combos as of 2026**, sourced daily from the Commander Spellbook database; confirm the live count via the paginated `variants` endpoint `count` field.

Combo detection feeds: (a) the hard "two-card infinite combo" bracket trigger, (b) the combo-potential dimension, and (c) speed estimation (early-game combos → fast).

### 3.4 Simulation-based approaches (validation & calibration layer)

- **Hypergeometric calculations (analytical, cheap):** compute exact probabilities of drawing key cards / land counts / combo pieces by turn N. Use the multivariate hypergeometric for multi-piece combos and colored-source requirements. This directly powers the **consistency** dimension. (Worked examples: a 60/24-land deck has ~91% for ≥2 lands in the opening 7; a single copy in a 99-card deck is only ~12% to appear by turn 5 — hence the need for tutors/redundancy in singleton formats.)
- **Karsten mana math:** colored-source requirements — e.g., in a 60-card deck a single pip needs ~14 sources (~86% by the opening hand), double-pip ~18 (~69% for ≥2). His per-format land baselines (aggro 19–22, midrange 23–26, control ~27 in 60-card; 35–38 in Commander) anchor mana-base grading.
- **Monte Carlo goldfish simulation:** shuffle-and-draw thousands of games with a simplified play policy to estimate **goldfish win-turn distribution** (speed) and mulligan/keep rates (consistency). Tractable without a full rules engine if you model only mana + key-piece access.
- **Full-game engines (Forge, XMage):** open-source Java rules engines with AI opponents and ~all cards implemented (XMage advertises 20,000+ unique cards; Forge lists ~114 unimplemented of 16,000+). Too heavy for per-request MCP calls, but invaluable **offline** to *calibrate* heuristic weights against actual win rates and to sanity-check combo lines. Note their AIs are weak at combo/control, so treat simulated win rates as noisy ground truth.

### 3.5 Machine-learning approaches (calibration / stretch)

- **Tournament-result models:** supervised win-rate/placement prediction from deck features (mana curve, synergy, color balance, archetype). Prior art includes a Commander tournament "guesser" project targeting top-3 winner prediction; a caveat is that public labeled Commander-result corpora are thin.
- **Card & deck embeddings (card2vec-style):** contrastive/Siamese models projecting cards and decks into a shared space (Bertram, Fürnkranz & Müller — Contextual Preference Ranking, arXiv 2105.11864, 2021, and 2024; "Learning With Generalised Card Representations," arXiv 2407.05879, 2024). Useful for synergy/archetype clustering and "nearest known deck" percentile scoring.
- **LLM-based assessment:** an LLM (the coding agent itself) can read oracle text + structured signals and produce a natural-language rationale and label. Strong for explanation and edge cases; weak for calibrated numbers — keep it as a *reasoning/summary* layer over deterministic signals, not the scorer.
- **RL / drafting agents:** LOCM-based RL deck-builders and UrzaGPT (LoRA-tuned LLM for card selection, arXiv 2508.08382, 2025) are relevant to *building/drafting*, less to power scoring; note for the roadmap.

**Heuristics vs. ML for an MCP tool:** heuristics win on latency, determinism, explainability, and zero training-data cost — critical when an AI coding agent needs a fast, auditable answer. ML/embeddings/percentiles add value for synergy detection and meta-relative scoring but should be *optional enrichment* backed by cached data, not the critical path.

---

## 4. Format-Specific Rubric Adjustments

The tool should switch rubric by format:

**60-card competitive (Standard/Pioneer/Modern/Legacy/Vintage/Pauper):**
- Expect **4-of consistency** (redundancy via literal duplicates, not functional equivalents).
- Score against the **metagame**: power is matchup- and meta-dependent; a deck's tier comes from tournament results (MTGTop8/Goldfish), not raw card quality.
- **Sideboard** exists (15 cards) — evaluate best-of-3 adaptability separately.
- Speed vs. interaction balance judged against the format's fundamental turn.
- Mana base graded with Karsten 60-card numbers.

**100-card singleton Commander:**
- **Bracket system is the native rubric**; Game Changers + hard triggers set the floor.
- Consistency relies on **functional redundancy + tutors** (singleton, so no 4-ofs); use rule-of-8 equivalence.
- **Multiplayer politics & variance** inflate uncertainty — widen confidence intervals.
- Karsten Commander land formula; 33–40 lands + 10–15 ramp typical.
- cEDH (Bracket 5) is self-declared; the tool should *flag candidacy* (dense fast mana + tutors + compact combo + free interaction like Force of Will/Fierce Guardianship) but not assert it.

**Limited (Draft/Sealed):**
- Power is **empirical and set-specific** — drive off 17Lands GIH WR per card; there is no cross-format absolute.
- Curve, creature count, removal count, and "bomb" density matter more than combos.
- 40-card, 17-land baseline; mana math scaled accordingly.

---

## 5. Data Sources & API Reference

| Source | Data | Access | Notes / ToU |
|---|---|---|---|
| **Scryfall** | Card objects, oracle text, MV, colors, color identity, legalities (all formats), prices (USD/EUR/Tix), `is:gamechanger` | REST, no key; `/cards/collection` batch ≤75 ids (2 req/s) | 429 → 30s lockout; must send `User-Agent` + `Accept`. **Cache ≥24h; prefer bulk data files.** Cannot paywall or repackage. |
| **MTGJSON** | Bulk card/legality/deck data, `isGameChanger`, `edhrecRank`, `edhrecSaltiness`, format-filtered files (Standard/Modern/Legacy/…) | Static downloadable JSON/CSV/SQLite/Parquet, built daily | Best for offline local DB; no rate limit (static files). |
| **EDHREC** | Commander inclusion %, synergy/lift, salt scores, average decklists, Game Changers rankings | Unofficial `json.edhrec.com/pages/...json` endpoints | **No official public API** — undocumented, may change; polite use + caching. Data sourced from Archidekt/Moxfield/Scryfall decks. |
| **Commander Spellbook** | Combo DB, `find-my-combos`, `estimate-bracket`, bracket tags, prerequisites/steps/results | REST `backend.commanderspellbook.com`, no key | MIT license; no published rate limit → 429 backoff. Powers EDHREC's combo feature. 97,606+ combos (2026). |
| **17Lands** | Limited win rates (GIH/OH/GD WR, ALSA, ATA), per set | Public card-data pages / datasets | Gold standard for Limited card power. |
| **MTGGoldfish / MTGTop8** | Constructed metagame, archetype tiers, tournament decklists, prices | Web (scrape/parse) | For 60-card meta-relative scoring; respect ToS. |
| **Moxfield / Archidekt** | Decklist hosting, bracket estimation, text import/export | Moxfield: read via community-known endpoints; Archidekt: read-only deck queries | Prefer plain-text decklist import; both support text import/export. Treat as decklist *ingestion*, not power source. |
| **Forge / XMage** | Full rules engines + AI | Local Java apps (open source) | Offline calibration/validation only. |

**Ingestion note:** Artificial Planeswalker should accept a decklist (text or Moxfield/Archidekt/Goldfish URL), resolve every card against a **local Scryfall bulk snapshot** (refreshed daily) for zero-latency card data and legality, and call Commander Spellbook / EDHREC live (with caching) for combos and meta signals.

---

## 6. Prior Art Survey

- **WotC Commander Brackets + Game Changers** (introduced Feb 11, 2025; updates Apr 22, Oct 21, 2025, and Feb 9, 2026): the authoritative categorical rubric. Tutor restrictions were **removed in the Oct 2025 update** (relying on Game Changers to catch efficient tutors). The Oct 2025 update also **delisted ten cards** — Deflecting Swat, Expropriate, Food Chain, Jin-Gitaxias (Core Augur), Kinnan (Bonder Prodigy), Sway of the Stars, Urza (Lord High Artificer), Vorinclex (Voice of Hunger), Winota (Joiner of Forces), and Yuriko (the Tiger's Shadow) — on the grounds that high-MV spells are fair and players can opt out of specific commanders in pregame talk. The **Feb 9, 2026 update added Farewell** (Gavin Verhey: it "removes pretty much everything, adding a lot of rebuilding time and starting from square one, which isn't enjoyable for many players") and re-added Biorhythm after its unban.
- **Bracket/power calculators:** Draftsim EDH Power Level calculator, ScrollVault Commander Bracket Calculator (claims validation against WotC precons + cEDH archetypes), edhpowerlevel.com (demand/price-driven), Cards Realm, EDHMeta, Spellweave, Playgroup.gg (reports Game-Changer-containing decks winning ~12–15% more often across tracked games). Archidekt and Moxfield have built-in bracket/Game Changer detection.
- **Formula-based:** Disciple of the Vault's `P = 2/A + ((D/2 + T + R/2)/2) + I/20` (A = avg MV, D = draw, T = tutor, R = ramp, I = interaction) — an example of an explicit heuristic scoring function (with documented edge-case failures, e.g. commander-centric aggro/tribal decks).
- **Combo tooling:** Commander Spellbook (combo DB + API), "Combinator" (jamese.dev) deck-combo finder.
- **ML/academic:** MTG_tournament_guesser (win prediction); generalised card representations & CPR embeddings (arXiv 2407.05879; arXiv 2105.11864); UrzaGPT (arXiv 2508.08382); RL drafting on LOCM (ScienceDirect); neural card classification (arXiv 1810.03744); MTG-as-Turing-complete and RoboRosewater (generative) as context. Ryan Saxe / 17Lands represent the state of the art in *Limited* card evaluation and draft-pick modeling.
- **MCP prior art:** a "Scryfall Connector" MCP server already exposes Scryfall + Commander Spellbook to agents with rate-limit/backoff handling; an EDHREC MCP server wraps the `json.edhrec.com` endpoints. Artificial Planeswalker can interoperate with or supersede these.

---

## 7. Recommended Architecture for Artificial Planeswalker

### 7.1 Pipeline

1. **Ingest & resolve** — parse decklist; resolve cards against local Scryfall bulk snapshot; detect/accept format; load the **format profile** (legal pool, ban/restricted list, baseline offset, expected win-turn distribution, rubric selector).
2. **Extract features (heuristics)** — curve, avg MV, land/ramp/draw/removal/tutor counts, interaction CMC + instant ratio, win-condition tags, Karsten land delta, rule-of-8 redundancy, 8×8 category coverage.
3. **Enrich (data)** — Game Changer membership; EDHREC inclusion/synergy/salt (Commander) or 17Lands WR (Limited) or meta-tier (60-card); Commander Spellbook combos + bracket tags.
4. **Analyze (probabilistic)** — hypergeometric consistency (key-piece & mana access by turn); optional Monte Carlo goldfish for win-turn distribution.
5. **Score & classify** —
   - Compute the **7-dimension vector** (speed, consistency, resilience, interaction, mana efficiency, card advantage, combo potential), each 0–100.
   - Apply **hard bracket triggers** (Commander) to set the categorical floor.
   - Weighted-aggregate the vector into a **for-format 0–100** score; add the format **offset/scale** for the **absolute 0–100** score.
   - Derive the familiar **Commander 1–10** and **percentile** (if corpus available) as secondary projections.
6. **Quantify uncertainty** — set confidence from card-resolution completeness, corpus coverage, combo ambiguity, and format (multiplayer variance widens intervals). Emit interval + reasons.
7. **Explain** — LLM/summary layer turns the vector + flags into human-readable rationale, listing the specific cards/combos that drove the score.

### 7.2 Ensemble weighting

Start with transparent, hand-tuned weights (documented, adjustable), then **calibrate offline** against: WotC precons (should land Bracket 2), known cEDH lists (Bracket 5 / 90–100 absolute), 17Lands WR for Limited, and MTGTop8 tiers for 60-card. Optionally regress weights against Forge/XMage or tournament win rates as a later ML pass. Keep the heuristic path authoritative and deterministic; ML only re-weights or supplies percentile/synergy enrichment.

### 7.3 Proposed MCP output schema (JSON)

```json
{
  "format": "commander",
  "format_profile_version": "2026-02",
  "assessment": {
    "categorical": {
      "system": "wotc_commander_brackets",
      "label": "Upgraded",
      "bracket": 3,
      "bracket_floor_reason": "3 Game Changers; no mass land denial; one late-game 2-card combo"
    },
    "for_format_score": { "value": 68, "low": 60, "high": 74, "scale": "0-100" },
    "absolute_score":  { "value": 55, "low": 47, "high": 62, "scale": "0-100",
                          "format_offset_applied": -13 },
    "legacy_scale": { "commander_1_10": 7.0 },
    "percentile": { "corpus": "edhrec:commander:<cmdr>", "value": 72 },
    "confidence": "medium",
    "confidence_reasons": ["2 cards unresolved", "multiplayer variance", "combo line ambiguous"]
  },
  "dimensions": {
    "speed":          { "score": 62, "avg_win_turn_estimate": 8.5, "method": "montecarlo+heuristic" },
    "consistency":    { "score": 71, "notes": "hypergeometric: key piece by T5 = 58%" },
    "resilience":     { "score": 60 },
    "interaction":    { "score": 65, "instant_speed_ratio": 0.55, "count": 11 },
    "mana_efficiency":{ "score": 74, "land_count": 36, "karsten_recommended": 37, "flood_risk": "low" },
    "card_advantage": { "score": 70, "engine_count": 6 },
    "combo_potential":{ "score": 45 }
  },
  "flags": {
    "game_changers": ["Rhystic Study", "Cyclonic Rift", "Demonic Tutor"],
    "combos": [
      { "cards": ["Card A","Card B"], "type": "two-card-infinite",
        "produces": "infinite mana", "spellbook_id": "1234-5678",
        "bracket_tag": "Ruthless", "earliest_turn_estimate": 6, "popularity": 20431 }
    ],
    "mass_land_denial": false,
    "extra_turn_chains": false,
    "cedh_candidate": false,
    "structural_gaps": ["ramp below 8x8 baseline (6)"]
  },
  "reasoning": "Human-readable summary generated from the above signals.",
  "data_sources": ["scryfall@2026-07-09-bulk", "edhrec", "commander_spellbook", "hypergeometric"]
}
```

Design notes: every score carries a range; categorical + numeric + percentile coexist so agents can choose; `flags` surface the exact cards/combos driving the result for auditability; `format_offset_applied` makes cross-format normalization explicit and inspectable.

---

## 8. Recommendations (staged)

**Stage 1 — Heuristic MVP (highest ROI).** Local Scryfall bulk snapshot + oracle-text feature extraction; Game Changers detection; hard bracket triggers; Karsten land math; hypergeometric consistency; rule-of-8 / 8×8 structural checks. Output the full schema with the 7-dimension vector, for-format & absolute scores, Commander bracket, and confidence. Deterministic, fast, explainable. *Benchmark to advance:* WotC precons classify as Bracket 2 and known cEDH lists as candidates ≥90 absolute in a held-out set.

**Stage 2 — Data enrichment.** Integrate Commander Spellbook `find-my-combos` (combo dimension + two-card trigger + speed), EDHREC inclusion/synergy/salt (Commander percentile), 17Lands WR (Limited), MTGTop8/Goldfish tiers (60-card meta percentile). Add caching + 429 backoff. *Benchmark:* percentile outputs correlate with EDHREC/17Lands rankings; combo detection matches Spellbook's own `included` set.

**Stage 3 — Simulation & calibration.** Monte Carlo goldfish for win-turn distributions; offline calibration of ensemble weights against Forge/XMage sims and tournament data. *Benchmark:* simulated win-turn medians track community "fundamental turn" expectations per format.

**Stage 4 — ML / embeddings (optional).** Card/deck embeddings for synergy clustering and "nearest known archetype" percentile; LLM rationale layer. Only if Stages 1–3 leave measurable accuracy gaps.

**Cross-cutting:** always ship the confidence interval; never present the absolute scalar without the categorical label and format context; keep every numeric output traceable to the cards/data that produced it.

---

## 9. Caveats & Known Pitfalls

- **"Pile of good cards" problem:** high average card quality ≠ high deck power. Cohesion/synergy and a coherent win plan matter; a tool that only sums card scores will over-rate incoherent goodstuff piles. The synergy/8×8-coverage and combo dimensions partially counter this, but it remains the hardest failure mode.
- **Meta-dependence:** power is relative to the field; a deck strong in one pod/meta is weak in another. Percentile outputs are time- and corpus-bound.
- **Intent is not observable:** WotC stresses Brackets are intent-based and "not an exact science." A deck can satisfy Bracket 2's letter while playing far above it. Auto-classification therefore has an irreducible error band — hence mandatory confidence intervals and the community rule of thumb to "bracket up when in doubt."
- **cEDH cannot be auto-asserted** from cards alone; only flagged as a candidate.
- **Data freshness & fragility:** the Game Changers list, ban lists, and metas change (multiple 2025–2026 updates already). EDHREC endpoints are unofficial and may break. Version the format profile and cache defensively.
- **Card price is a poor power proxy** — driven by scarcity/collectability as much as power; keep low-weight.
- **Simulation AIs are weak** at combo/control; treat engine win rates as noisy.
- **Singleton variance & multiplayer politics** make Commander inherently higher-variance to score than 60-card 4-of decks — reflect this in wider intervals.
- **Universes Beyond / new sets** continually add cards; unresolved or brand-new cards should lower confidence rather than silently score as zero.

---

### Appendix: Quick-reference constants for implementation
- **Karsten Commander lands:** `31.42 + 3.13·avgMV − 0.28·(cheap draw+ramp)`; typical 33–40 lands + 10–15 ramp.
- **Karsten 60-card lands:** `19.59 + 1.90·avgMV − 0.28·(cheap draw+ramp)`; aggro 19–22, midrange 23–26, control ~27.
- **Colored sources (60-card):** 1 pip ≈14 sources (~86% opener), 2 pips ≈18 (~69% for ≥2).
- **Redundancy (60-card opener):** 4 copies 39.9%, 8 copies 65.4%, 12 copies 80.9%.
- **Game Changers:** 40 cards at launch (Feb 11, 2025) → 53 as of Feb 9, 2026; `is:gamechanger` on Scryfall.
- **Commander Brackets gating:** 0 GC → B1–2; 1–3 GC → B3; 4+ GC / mass land denial / early two-card infinite → B4; cEDH (B5) self-declared.
- **Spellbook bracket tags → power:** Ruthless 4, Spicy 3, Powerful 3, Oddball 2, Precon-Appropriate 2, Casual 1.