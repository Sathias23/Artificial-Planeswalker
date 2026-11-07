---
id: SPEC-deck-workflow-reliability
companions:
  - acceptance.md
sources:
  - C:/Users/Sathias/Ideas/magic-the-gathering/usage-recommendations.md
---

# Deck workflow reliability

## Why

An Arena Brawl deckbuilding session exposed stalled lookup batches, avoidable import/export failures, and misleading assessment results when a Commander profile was used for Brawl. Users need to resolve a deck without direct database workarounds, move it reliably into Arena, and distinguish supported analysis from unsupported scoring.

## Capabilities

- **CAP-1**
  - **intent:** Resolve an entire deck through one dependable bulk lookup request.
  - **success:** Every input receives an ordered, attributable result, including ambiguity and failure; format/platform filters and printing qualifiers are respected. An injected stall produces bounded completion, explicit unfinished outcomes, resource cleanup, and a successful subsequent request.
- **CAP-2**
  - **intent:** Import common deck lists and export decks that Arena can interpret without manual card-name repairs.
  - **success:** Name-only and printing-qualified inputs resolve consistently with bulk lookup; verified Arena exports preserve playable identities, quantities and sections through round trips, including split and double-faced cards. Unexportable cards and import failures are explicit.
- **CAP-3**
  - **intent:** Give Brawl users an honest account of assessment support and combo completeness.
  - **success:** Brawl requests return an explicit unsupported-scoring outcome without substituting a Commander score or strength label; incomplete variants remain suggestions and contribute no credit as functioning combos.

## Constraints

- Lookup and analysis remain observational, stateless MCP operations over stdio; only explicitly requested deck-management operations may mutate decks, and the companion remains read-only.
- Measure orchestration and server/database delays separately before attributing stalls or choosing concurrency limits; fewer calls alone do not establish reliability.
- Bulk lookup and import share resolution semantics, including explicit ambiguity and qualifier fallback reporting.
- Platform availability aggregated across printings is insufficient evidence that a stored printing is Arena-compatible.
- Follow repository generation rules for tool/skill changes and test behavior through real entry points.

## Non-goals

- Calibrating a new Brawl power model, complete Brawl legality validation, atomic deck replacement/swaps, broad synergy-detector expansion, or companion launch diagnostics.

## Success signal

A representative 100-card Arena Brawl deck can be resolved in one request, imported and exported without manual database access or name repairs, and assessed without an unsupported numeric rating. Mixed failures and injected stalls satisfy the cases in acceptance.md without disappearing inputs or lingering resource exhaustion.

## Assumptions

- The review's consolidated three changes supersede the source document's conflicting shortlists.
- The first Brawl deliverable is explicit unsupported scoring; existing additive import behavior remains, with partial success clearly reported.

## Open Questions

- Which batch-size limit, concurrency bound and deadlines meet measured performance needs?
- Which printing-data source will verify Arena printings, and should mismatched qualifiers fail strictly or permit an explicitly reported fallback?
