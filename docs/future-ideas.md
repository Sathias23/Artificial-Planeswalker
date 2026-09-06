# Future ideas

Feature and ideas review, 2026-09-06.

Prioritize trustworthy legality checks and a complete **propose → preview → apply → compare → export** workflow. The repository already has substantial analysis and visual presentation capabilities; connecting them should deliver more value than adding more presentation modes.

This is a source-based product review of the MCP tools, companion, analysis engine, and relevant tests. It does not include a browser usability test. Rankings reflect expected user benefit and engineering effort, not measured usage data. These are proposals, not committed scope.

## Existing strengths

Preserve local operation without an API key, structured and semantic search, deterministic assessments with confidence information, and the companion's card inspection, curve/colour panels, legality checks, suggestions, swaps, tiers, groups, and session history.

Keep the companion read-only, database mutations in MCP, analysis observational, and MCP tools stateless. New display capabilities belong in the companion, not the frozen viewer.

## Ranked opportunities

Complexity: **S** = contained extension; **M** = coordinated changes across several layers; **L** = new persistence, data sources, or substantial domain modelling.

| Rank | Change / feature | Area | Complexity | Return | Why prioritize it |
|---|---|---|---|---|---|
| 1 | **Complete format-aware legality** | Both | M–L | Very high | Correctness underpins every recommendation. Add format-specific sizes, commander eligibility/identity, restricted cards, and copy exceptions; explicitly identify unchecked rules. |
| 2 | **Transactional changes with a before/after preview** | Both | M | Very high | Turn displayed swaps into a coherent change plan. Preview legality, curve and assessment effects; apply the entire plan in one transaction through MCP. |
| 3 | **Rename decks and set quantities directly** | MCP | S | High | Basic edits currently require awkward workflows. Relevant repository methods already exist, making this a strong quick win. |
| 4 | **Clone a deck** | MCP | S–M | High | Makes experimenting and using the existing power comparison straightforward. Preserve boards, commanders, quantities and metadata. |
| 5 | **Plain-text import and dedicated export** | Both | S–M | High | Accept common `4 Card Name` lists; export plain text and Arena-compatible lists, with copy/download in the companion. Completes the journey back to playing. |
| 6 | **Deck/revision labels on recommendations** | Companion + contracts | S–M | High | Show which deck a suggestion belongs to and whether it predates an edit. Distinguish agent confidence from computed evidence. |
| 7 | **Assessment and comparison panels** | Companion | M | High | Surface the existing seven dimensions, structural gaps, combos and confidence details visually. A before/after explanation is more useful than another isolated score. |
| 8 | **Deck browsing, search and display controls** | Companion | S–M | High | Browse saved decks locally, filter cards, change grouping, and inspect sideboard art without a chat round trip. |
| 9 | **Deck-aware candidate search** | MCP | M | High | Combine existing search with format, commander identity, missing roles, curve needs and cards already included. Reduce repeated agent orchestration. |
| 10 | **Casting consistency and opening-hand exploration** | Both | M–L | High | Answer “Can I cast this on turn three?” Extend existing probability calculations with play/draw assumptions, coloured sources and tapped lands. |
| 11 | **Unified data status and freshness** | Both | S–M | Medium–high | Show card refresh date, embedding coverage and combo snapshot readiness together, with a precise recovery action. |
| 12 | **Saved revisions, diffs and undo** | Both | L | High | Preserve experiments and recover previous configurations. Build after cloning and transactional changes establish the foundations. |
| 13 | **Owned-card collection and missing-card lists** | Both | L | High for collection users | Makes recommendations immediately usable. Start with imported quantities and “owned only” constraints. |
| 14 | **Saved sideboard plans** | Both | M | Medium–high | Record matchup, play/draw, ins/outs and rationale; validate the resulting list. Converts transient advice into reusable preparation. |
| 15 | **Budget-aware upgrades** | Both | L | Audience-dependent | Useful, but requires pricing, currency, printing and freshness handling. It is a data feature, not just a search filter. |

## Findings behind the ranking

### Legality needs attention first

The shared validator deliberately applies a 60-card minimum and 15-card sideboard maximum across formats. It has singleton support, but omits Commander-specific construction checks and restricted-card semantics. A successful verdict can therefore imply more coverage than exists.

First expose coverage limitations clearly, then implement the missing rule profiles. Commander’s size and colour-identity requirements are part of the [official format rules](https://magic.wizards.com/en/formats/commander).

Evidence: [shared validator](../src/logic/deck_validator.py), [MCP analysis tools](../src/mcp_server/tools/deck_analysis.py), and [companion format-check route](../src/companion/app/routes/decks.py).

### Complete the improvement workflow

The comparison tool's documentation tells callers to manually copy a deck before editing it. Meanwhile, swaps are displayed as pairs with rationale and optional confidence. A useful experience would be:

> These five swaps reduce expensive spells, add two interaction pieces, and preserve legality. Here is the candidate list and what changed.

Add an observational change-preview operation that constructs the candidate in memory and reuses the existing legality, curve and assessment pipelines. Apply changes through a separate explicit MCP mutation, in one transaction, with an expected revision so a proposal cannot silently overwrite intervening edits. Validate the combined plan, not just each swap independently.

Expose the existing metadata and quantity update capabilities through MCP, preserving omitted-versus-cleared semantics and deck-change notifications. Add cloning before full revision history. Plain-text import and dedicated export complete this workflow; preserve the existing bulk import's transactional behavior.

Evidence: [tool registration and comparison workflow](../src/mcp_server/server.py), [deck repository](../src/data/repositories/deck.py), [bulk import](../src/mcp_server/tools/deck_import.py), and [swap presentation](../ui/src/containers/SwapsView/SwapsView.tsx).

### Make the companion easier to explore

Saved deck names are currently informational, and the art grid excludes sideboard cards. Local browsing, filters and sideboard display would improve ordinary use without introducing database writes. Browsing should clearly indicate whether the user is following the agent's active deck or inspecting another one.

Add assessment and comparison panels over existing analysis capabilities. Present dimensions, structural gaps, confidence, and the reasons for changes together, rather than emphasizing an isolated aggregate score.

Evidence: [welcome screen](../ui/src/components/Welcome/Welcome.tsx), [card grid](../ui/src/containers/CardGrid/CardGrid.tsx), [deck grouping](../ui/src/state/deckGroups.ts), and [assessment comparison](../src/mcp_server/tools/compare_deck_power.py).

### Extend history and recommendation provenance

There is already an in-memory history of 20 agent pushes. What is missing is durable preservation and deck/revision context. Start with report export and provenance; add MCP-backed saved reports later.

Attach the originating deck and revision to recommendations, mark outdated proposals, and distinguish agent-supplied confidence from deterministic evidence. Historical suggestions should remain understandable after switching decks or editing their source deck.

Evidence: [agent-view state](../ui/src/state/agentView.ts) and [companion payload contracts](../src/companion/contracts.py).

### Invest in assessment credibility alongside features

Calibration benchmarks and real-model search evaluations already exist. Expand them with held-out decks, broader archetypes and realistic search queries before widening scoring claims. Make evaluation reproducible without depending on an operator's local card database, and report quality by format and archetype.

Casting analysis should extend the existing probability calculations and make assumptions visible. The current cards-seen convention does not model mulligans, and coloured-source heuristics have documented limitations. Add play/draw controls, conditional and tapped-source handling, and per-spell casting estimates incrementally.

Evidence: [assessment profiles](../src/logic/assessment/profiles.py), [assessment benchmarks](../tests/integration/logic/test_assessment_benchmark.py), [search evaluation](../tests/integration/search/test_rag_eval.py), [probability calculations](../src/logic/assessment/consistency.py), and [mana-base analysis](../src/logic/assessment/mana_base.py).

### Add practical constraints in stages

Deck-aware search can compose existing retrieval with structural gaps and explicit user constraints. Return reasons and evidence without promising globally optimal recommendations from heuristic scores.

Collection support should start with user-imported owned quantities and missing-card lists. Budget support comes later: the current card model has no pricing data, so price filters require a data model, printing/currency decisions and freshness semantics.

Saved sideboard plans should begin with user-entered matchup notes and validated ins/outs, rather than predicted matchup win rates.

Evidence: [search tools](../src/mcp_server/server.py), [structural coverage signals](../src/logic/assessment/consistency.py), [card model](../src/data/models/card.py), and [deck model](../src/data/models/deck.py).

## Suggested delivery sequence

1. **Quick wins:** metadata/quantity tools, clone, export, recommendation provenance, and visible legality coverage.
2. **Core investment:** format rules, transactional preview/apply, and companion comparison panels.
3. **Depth:** casting consistency, constrained search, revisions, then collection support.

## Defer for now

Defer a full game simulator, automated metagame win-rate predictions, multiplayer hosting, and additional decorative view modes. Each brings considerable scope before improving the repository's most important unfinished workflow.
