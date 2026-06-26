# Semantic Tool Performance Report

**Date:** 2026-06-27
**Tools evaluated:** `semantic_search_cards`, `find_similar_cards`
**Corpus:** Scryfall `oracle_cards` — 38,232 unique cards, 384-dim `bge-small-en-v1.5` embeddings
**Basis:** Two real queries run against the live MCP server, assessed for workflow and result quality (not latency).

---

## 1. Summary

Both tools returned relevant, sensibly-ranked results and proved usable for real card discovery. The semantic layer clearly understands *meaning* rather than keywords — it grouped reanimation and removal effects together without either term appearing verbatim in card text. The main weaknesses are (a) a hard setup dependency that blocks the first call entirely, and (b) **recall/precision on compound intents**: a query asking for two effects in one card surfaces cards that satisfy *either* effect, mixed together, leaving the human to filter for the intersection.

| Dimension | `semantic_search_cards` | `find_similar_cards` |
|---|---|---|
| First-run readiness | ❌ Failed — index not built | ✅ Worked once index existed |
| Result relevance | ✅ Good, on-theme | ✅ Good, tightly on-theme |
| Ranking quality | ⚠️ Reasonable, but partial matches outranked exact ones | ✅ Strong — closest functional cousins ranked high |
| Compound-intent precision | ⚠️ Weak — returned "either effect", not "both" | ⚠️ Inherits seed's blended meaning |
| Output usability | ✅ Clean structured summaries + distance | ✅ Same, plus resolved `seed` echo |

---

## 2. `semantic_search_cards`

**Query:** *"destroy or kill target creature and return a creature card from your graveyard to the battlefield, removal that also reanimates"* — filtered to black (`colors=["B"]`), limit 20.

### Workflow
- **First call failed cleanly** with `status: "index_unavailable"` and an actionable message naming the exact build command. Good failure ergonomics, but a hard blocker: the underlying `cards` table was *also* empty, so the documented fix (`build_card_embeddings.py`) failed too with `no such table: cards`. The real prerequisite chain — **import Scryfall data → build embeddings → search** — was not surfaced by the error; it had to be discovered manually.
- Once both steps ran (38,232 cards imported in ~5.5s; embeddings built in ~242s), the same query succeeded with `status: "ok"`.

### Result quality
- **Relevance:** High. Every one of the 20 hits was a black graveyard/removal card — no off-theme noise.
- **Precision on the actual ask:** Moderate. The request was for cards doing **both** removal *and* battlefield reanimation. The result set was dominated by cards doing only **one**:
  - Pure reanimation (`Reanimate`, `Raise Dead`, `Disentomb`, `Return to Battle`) ranked at the very top (distance ~0.52).
  - The genuine "both" cards — `Come Back Wrong`, `Live or Die`, `Deadly Plot`, `Betrayal of Flesh` — were present but **interleaved** with and sometimes **outranked by** partial matches.
  - `Betrayal of Flesh`, arguably the single best answer (modal kill-or-reanimate *with entwine to do both*), ranked **14th**.
- **Ranking takeaway:** Embedding distance tracks topical similarity, not logical conjunction. A card that strongly matches half the query ("return a creature to the battlefield") scores closer than a card that moderately matches the whole query. The human had to do the final intersection filtering.

---

## 3. `find_similar_cards`

**Seed:** `Live or Die` ({3}{B}{B} instant — *return a creature to the battlefield* **or** *destroy a creature*), limit 15.

### Workflow
- Ran first try (index now populated). Seed resolved correctly via fuzzy name match, and the response echoed the resolved `seed` object — useful for confirming the tool keyed off the right card.
- Correctly **excluded the seed and its reprints**, so results were true alternatives, not the card echoed back.

### Result quality
- **Relevance:** High and noticeably *tighter* than the free-text search. The nearest hits captured Live or Die's dual "kill **or** reanimate" identity well:
  - `Deadly Plot` (modal destroy / reanimate-Zombie) and `Betrayal of Flesh` (destroy / reanimate, entwine both) are near-exact functional cousins and ranked in the top 3.
  - `Back for More` ranked #1 (reanimate-to-battlefield + fight) — defensible, though it's Golgari, not mono-black.
- **Seed-blend artifact:** Because the seed has *two* effects, similarity bled toward cards matching *either* lobe of its meaning — pure removal (`Fatal Push`), pure reanimation (`Grim Return`), and even color/graveyard-adjacent cards in other colors (`Return to Nature`, `Ojutai's Command`, `Continue?`) appeared further down. This is the same compound-intent dilution seen in the free-text tool, inherited through the seed vector.
- **Cross-color leakage:** With no color filter applied, white/green/blue cards surfaced. The tool *supports* `colors`/`color_mode` filters that would have removed these; not a tool defect, but worth noting the default is unconstrained.

---

## 4. Cross-cutting observations

1. **Setup is a cliff, not a ramp.** The very first useful action in the system requires two undocumented-in-error prerequisite steps. A combined bootstrap (or an error message that names the *whole* chain) would prevent a dead-end first experience.
2. **Compound queries dilute.** Both tools rank by topical proximity, so "A **and** B" queries return "A or B" results blended together. For multi-effect intent, the tools are best treated as **high-recall candidate generators** with a human/LLM doing the final logical filter — which is exactly how they were used here, successfully.
3. **Output contract is clean.** Both return lightweight, consistent summaries (`name`, `mana_cost`, `cmc`, `type_line`, `oracle_text`, `colors`, `rarity`, `set_code`) plus a `distance` relevance signal and a clear `status`. Easy to post-process and rank.
4. **`distance` is comparable within a call, not across calls.** Useful as a relative signal; the absolute values (~0.44–0.61 here) shouldn't be read as a quality threshold.

---

## 5. Recommendations

- **Bootstrap UX:** Have `build_card_embeddings.py` detect an empty `cards` table and emit the prerequisite import command, or ship a single `setup` entrypoint that chains import → build.
- **Compound-intent help:** Consider an optional re-rank that rewards cards matching *multiple* clauses of a query, or document the "candidate generator + filter" pattern so callers know to over-fetch and post-filter.
- **Default filters:** For `find_similar_cards`, consider defaulting color identity to the seed's colors (overridable) to cut cross-color leakage.
- **Verdict:** Both tools are fit for purpose for exploratory card discovery. Relevance is strong; the only real friction is first-run setup and the expected dilution on multi-effect asks.
