---
title: 'MTGA Collection Ingestion — Step-0 Collector Spike (GO/NO-GO)'
type: 'chore'
created: '2026-07-20'
status: 'done'
route: 'one-shot'
---

# MTGA Collection Ingestion — Step-0 Collector Spike (GO/NO-GO)

## Intent

**Problem:** The decided collection-ingestion path (research 2026-06-28) hinged on one unproven
assumption: that an external memory-reading collector still works against the live 2026 MTGA
client — public collectors' scan logic could have rotted.

**Approach:** Run the ½-day spike as designed: execute `NthPhantom10/MTGA-collection-exporter`
(MIT) against the live client from a throwaway scratchpad copy, verify known owned counts, and
confirm exported grpIds resolve via the local Arena card DB and Scryfall `arena_id`. Record the
verdict and Phase-A implications in a spike report; no repo code changes.

## Suggested Review Order

1. [spike-mtga-collector-go-no-go-2026-07-20.md](../planning-artifacts/research/spike-mtga-collector-go-no-go-2026-07-20.md)
   — the whole deliverable: **GO** verdict, evidence table, the four bit-rot patches, Phase-A implications.
2. [technical-mtga-collection-ingestion-research-2026-06-28.md](../planning-artifacts/research/technical-mtga-collection-ingestion-research-2026-06-28.md)
   — §"Step 0 — De-risk spike" for what was specified vs. what ran (only if you want the baseline).
