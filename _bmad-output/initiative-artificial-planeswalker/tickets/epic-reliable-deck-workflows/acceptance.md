# Acceptance cases and evidence

## CAP-1: Bulk lookup and reliability

- Accept multiple names with optional printing qualifiers and the existing format/platform filters. Preserve each input's index and original text, including duplicates.
- Return a result for every input: found, ambiguous with candidates, not found, failed, or explicitly unfinished. Expose whether the batch completed; never silently drop queued items.
- Bound work and response size. Choose and document limits from measurements; oversized requests must produce an actionable outcome.
- Define batch and item deadline ownership. Cancel outstanding work and release resources on expiry; a retry must not inherit exhausted capacity from abandoned work.
- Exercise individual calls, three-item batches, 15-item batches, approximately 90-item batches and a representative 100-card deck. Measure tool orchestration separately from server/database processing.
- Verify mixed valid, missing, ambiguous and duplicate inputs, filter behavior, injected queued/running stalls, timeout attribution, and a successful request after cancellation through actual entry points.

## CAP-2: Arena interoperability

- Accept name-only card lines and set/collector-qualified lines. Supplied qualifiers participate in resolution; mismatches must never silently select a different card.
- Share resolution with CAP-1. Resolve front-face names to playable identities where unambiguous and exclude art cards from ordinary playable-card resolution.
- Report each rejected import line and the imported totals. Preserve additive semantics for this scope; partial import must be explicit and retries must have documented behavior.
- Export verified Arena-compatible names and printing identifiers where used. Never infer printing compatibility solely from an identity's aggregated Arena availability.
- Substitute a printing only when verified to represent the same playable identity; otherwise report an unexportable card. Never silently omit it or claim the incomplete output represents the complete deck.
- Verify round trips preserve identity, quantity and Commander/Deck/Sideboard/Companion placement where supported. Cover name-only input, qualified input, invalid qualifiers, unavailable printings, split cards and double-faced cards.
- Include regression examples for The Emperor of Palamecia with FIN 219 and the complete split-card identity associated with Commit. Validate exported examples against Arena acceptance; a round trip through this project's own parser alone is insufficient proof of interoperability.

## CAP-3: Honest Brawl assessment

- A Brawl assessment must explicitly state that numerical scoring is unsupported and must not silently fall back to Commander or label the deck Competitive using that profile.
- Separate complete combo variants from near-complete suggestions. Missing-card variants must not count as functioning combos in assessment scoring.
- Verify the reported scenario of zero complete variants and 18 variants missing one card cannot yield maximum functioning-combo credit. Preserve supported Commander/Standard assessment behavior except for the intended incomplete-combo correction.
- A calibrated Brawl model requires separate evidence and scope; relabeling a Commander profile does not satisfy it.

## Brownfield evidence and limits

- The September 7, 2026 session reported roughly 90 and 15 simultaneous lookups stalling, while individual calls and batches of three completed. Root cause was not established; plugin behavior and orchestration remain candidates.
- Tools were callable; deck creation, edits, validation and companion updates worked. A read-only database batch query bypassed the lookup bottleneck but required elevated access.
- The existing import contract required printing-qualified lines. Name-only rejection and the agent's shortened Commit input were input mistakes, not proof of tool-access failure; broader format support is a usability change.
- Review of src/mcp_server/tools/deck_import.py confirmed parsed qualifiers were not passed to name resolution. src/data/importers/scryfall.py retains canonical printings with platform availability combined across printings, creating a data dependency for verified printing exports.
- The forced Commander assessment reportedly scored 80/100, labeled Competitive, and gave combo potential 100 despite zero complete variants. This is not evidence of calibrated Brawl power.
- Generic synergy detection reportedly returned no patterns and low cohesion despite commander interactions. Broad detection coverage, full Brawl validation, atomic swaps and companion cache-access diagnostics remain deferred; name resolution is included only as needed for CAP-1/CAP-2.

## Implementation decisions to resolve

Record measured limits and deadline ownership before CAP-1 is finalized. Establish the Arena printing-data source and strict-versus-reported-fallback qualifier policy before CAP-2 implementation. These are unresolved design choices, not permission to silently guess identities or omit results.
