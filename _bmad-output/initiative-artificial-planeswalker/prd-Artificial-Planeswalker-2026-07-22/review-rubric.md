# PRD Quality Review — Companion App (Artificial Planeswalker), 2026-07-22

Calibration applied: feature-level PRD for a single-maintainer, single-operator open-source project; release-grade bar; chain-top (feeds UX spec → architecture → epics/stories). FR ID non-contiguity within feature groups is by design (brief numbering preserved) and is not flagged.

## Overall verdict

This is a genuinely decision-ready PRD: it states its bets ("presentation layer only," web-first, per-tool push API, session-only history), preserves the rationale for what it rejected, and keeps its two open questions honestly open with named downstream owners. The main exposure is downstream-usability polish for a chain-top document — no glossary anchor for its handful of coined terms, one phasing/NFR inconsistency, and two latency/overhead figures whose test conditions are underspecified — none of which threatens the product thesis, all of which will be felt when epics and tests are cut from it.

## Decision-readiness — strong

Decisions are stated as decisions, and the addendum's "Rejected alternatives" section (§Rejected alternatives) is the strongest part of the artifact: each rejection names what was given up and why ("per-tool docstrings give the agent sharper affordances, and payload validation stays a plain model per tool instead of a discriminated union"; persistent history "cuts against the stateless fire-and-forget event model"). The Open Questions (§12 OQ-A/OQ-B) are actually open — each names its downstream owner and OQ-A parks its resolved constraints in the addendum rather than pretending they don't exist. The risk table (§10) pairs every risk with a mechanism, not a platitude ("Tools validate with lightweight `GET /health` before POSTing; failure means 'app not running'"). No findings.

## Substance over theater — strong

Nothing here is furniture. The single user description (§3) is one paragraph and it drives real decisions (NG3 localhost-only, SC-5 "judged by Brad, the sole quality gate"). NFRs carry product-specific content, not boilerplate: NFR-01 is a concrete localhost threat model (WS ticket auth "CORS alone does not protect WebSockets," Host-header validation against DNS rebinding), NFR-02 names the exact SQLite mode and connection string, NFR-08 ties attribution to the project's existing MIT + Scryfall stance. Counter-metrics (CM-1..3) are the kind that only exist because someone thought about failure modes (token overhead, CDN request storms, session-state creep). The one soft spot is CM-1's "negligible latency and token overhead" — see Done-ness.

## Strategic coherence — strong

The thesis is stated in §2 in one sentence — "Deck building is a visual activity" — and everything downstream serves it: G5 makes the aesthetic explicitly load-bearing ("the visual experience is the point of the feature, not a byproduct"), FR-20 is P0 rather than a nice-to-have, FR-19 mandates full card faces over art crops, and the risk table treats "Dark-theme polish under-delivers" as a first-class risk with a mitigation (UX spec before implementation, SC-5 gate). MVP scope kind is experience/platform hybrid and the phasing logic matches: the addendum states the sequencing rationale outright ("MVP proves the push pipe with suggestions; the radar-chart panel lands in Phase 3 once the core loop is solid"). Success criteria validate the thesis (SC-1 render latency, SC-5 "deliberate product, not a debug dashboard") rather than measuring activity, and counter-metrics are present. No findings.

## Done-ness clarity — adequate

Most FRs carry a testable consequence, including the ones that could easily have been adjectives: FR-12 defines "degrade gracefully" concretely ("return a text result noting the app is not running — never a hard error"), FR-01 specifies the fallback behavior, FR-11 specifies event-after-persist ordering, and FR-13 pins the canonical ID to a specific column ("`cards.id`, the value in `deck_cards.card_id`"). FR-20's aesthetic language ("subtle motion," "evoking Arena/Untapped.gg") is inherently untestable, but the PRD handles this honestly by delegating to the UX spec and naming a human gate (SC-5) — acceptable for a solo project where the judge is the user. The findings below are the residue.

### Findings

- **medium** SC-1 / NFR-05 latency figures lack their test conditions (§9 SC-1, §8 NFR-05) — SC-1 requires "a rendered suggestion panel with card art within 250 ms of the tool call completing," but a cold-cache suggestion (six never-seen images fetched from the Scryfall CDN) cannot meet 250 ms. NFR-05 conditions the 1 s deck-view render on "warm image cache" but leaves event-to-render unconditioned. A downstream test written literally from SC-1 will fail or be quietly weakened. *Fix:* add "with warm image cache" (or "excluding first-fetch image latency") to SC-1 and to NFR-05's event-to-render clause.
- **low** CM-1 "negligible latency and token overhead" is unquantified (§9 CM-1) — the mechanism is specified ("tools return compact text, never dump payloads back into chat") but "negligible" gives a story writer no acceptance bound. *Fix:* a rough ceiling, e.g. "tool text returns under ~200 tokens; no payload echo."
- **low** FR-02 "metadata" is undefined (§7 Feature B) — "`GET /api/deck/{id}` returns a full decklist with card IDs, quantities, and metadata." Which metadata (name, format, timestamps, commander?) is left to inference; the existing `load_deck` tool shape is the likely intent but is not cited. *Fix:* one clause: "metadata (name, format, description — matching `load_deck` output)."

## Scope honesty — strong

Non-Goals do real work: NG1 (read-only UI, edits get "a future feature with its own brief"), NG5 (chat output preserved so "agent workflows work identically without the app") each forecloses a silent assumption a reader would otherwise make. Phase 3 explicitly re-lists the deferred items rather than letting them vanish. De-scoping is done in the open — the addendum's rejected-alternatives section is de-scoping with receipts. Open-items density is low (2 OQs, 0 assumptions) which is right for a PRD downstream of an adversarially-reviewed brief. One structural note: the PRD uses no `[ASSUMPTION]` tags or Assumptions Index at all. Given the brief-first pipeline (decisions were confirmed upstream, per the §1 framing and the addendum's "from the feature brief" sourcing), the zero count reads as earned rather than evasive, but at least one inference looks unconfirmed-in-this-document (see finding).

### Findings

- **low** No `[ASSUMPTION]` tags where mild inferences exist (§8 NFR-05, §9 SC-1) — e.g., the 250 ms / 1 s numbers appear without provenance; whether they were user-confirmed or author-invented is invisible. On a chain-top PRD the tag is cheap insurance. *Fix:* tag the performance thresholds (and any other author-chosen numbers) as assumptions, with a two-line index.

## Downstream usability — adequate

Cross-reference integrity is good: FR-13 → FR-03/FR-04 resolves; §12 OQ-A → addendum parking resolves; the risk table's references (FR-12, §12) resolve; every FR-01..21 appears in exactly one phase in §11, and Priority↔Phase mapping is perfectly consistent (all P0s in Phase 1, all P1s in Phase 2, both P2s in Phase 3). Brownfield code references are accurate — `cards.image_uris` in `src/data/models/card.py`, per-face `image_uris` handling in `src/data/importers/transformers.py`, and `deck_cards.card_id` all check out against the codebase. The UJ has a named protagonist (Brad) carrying context inline. The gap for a chain-top document is terminological anchoring.

### Findings

- **medium** No Glossary (whole document) — the PRD coins several load-bearing terms — "agent panel," "discovery file," "push"/"pushed content," "active deck," "companion backend," "companion tools" — that the UX spec, architecture, and stories will all need to use identically. Usage is currently consistent, but there is no anchor to keep three downstream documents from drifting (e.g., "suggestion panel" in UJ-1 and SC-5 vs. "agent panel" in Feature D — same surface? the reader must infer yes). *Fix:* a six-to-eight-entry glossary; explicitly equate or distinguish "suggestion panel" and "agent panel."
- **low** NFR-07 is absent from §11 Phasing while §1 promises "release-grade docs, install polish, and CI parity apply from the start" (§8 NFR-07, §11) — every other NFR is phase-assigned; NFR-07's omission is presumably "always-on from Phase 1" but an epic-slicer has to guess. *Fix:* add NFR-07 to the Phase 1 list or a one-line "NFR-07 applies to all phases."

## Shape fit — strong

The shape matches the product exactly. Single-operator local tool → capability-spec core (FR tables grouped by feature) with precisely one UJ, which is the right number: UJ-1 (§3) earns its place by being the load-bearing demonstration of the interaction model ("the agent drives, the app shows" — a phrase that does more spec work than several FRs would). Success criteria are operational rather than market-facing (SC-4 single-command launch, SC-3 works-with-app-closed), which fits. Chain-top obligations are met structurally — §6 explicitly defers mechanism to "the addendum and downstream architecture," FR-20 defers visual direction to the UX spec, and the addendum is organized as parking for exactly those consumers. Not over-formalized: no persona roster, no market sizing, no innovation section for a feature that doesn't claim novelty. No findings.

## Mechanical notes

- **ID continuity:** FR-01..21 all present exactly once across §7 and §11; non-contiguous ordering within feature groups is by design (brief numbering preserved) — cross-reference integrity holds. NFR-01..08, SC-1..5, CM-1..3, NG1..5, G1..5, OQ-A/B: no gaps or duplicates.
- **Assumptions Index roundtrip:** vacuously satisfied (zero inline tags, no index). See Scope honesty finding.
- **Terminology drift (minor):** "suggestion panel" (UJ-1, SC-5) vs. "agent panel" (Feature D, FR-18, addendum zustand slice `agentPanel`) — same UI surface, two names. "Companion app" / "the app" / "the UI" / "Browser UI" used interchangeably; harmless but a glossary would settle it.
- **§9 heading says "Success Criteria & Counter-Metrics"** and uses SC-/CM- IDs rather than SM-; internally consistent, no downstream impact.
- **Addendum hygiene:** rejected-alternative labels reference brief-era OQ numbers (OQ-2/OQ-3/OQ-4) that do not exist in this PRD's OQ-A/OQ-B scheme — the provenance is clear from context, but a stray reader may hunt for a missing OQ-2. Cosmetic.
- **UJ protagonist:** UJ-1 names Brad inline. Compliant.
