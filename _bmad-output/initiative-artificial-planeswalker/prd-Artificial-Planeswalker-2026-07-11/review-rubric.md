# PRD Quality Review — Deck Power-Level Assessment (Artificial Planeswalker)

## Overall verdict

This is a genuinely good lean PRD: it has a real thesis (own-deck relative comparison), it makes its
decisions out loud, and its scope honesty is exemplary — non-goals, rejected forks (4a vs 4b), and
roadmap deferrals are all explicit and reasoned. What's at risk is the *scoring engine's* done-ness:
the per-dimension 0–100 computations and the aggregate weights are undefined (partly acknowledged as
open questions), and the single acceptance gate (Success Metric 1) depends on a benchmark set that is
itself an open question. Those are the two things that will slow downstream architecture/epics work.
Gate: **PASS-WITH-FIXES.**

## Decision-readiness — strong

A decision-maker can act on this. Real decisions are stated as decisions, not smuggled in as
"considerations": the compare tool is rejected in favour of caller-side diffing (§1.1, addendum A),
Game Changer sourcing chose Fork 4b over 4a *with the trade-off named* (addendum A: auto-updating
single-source-of-truth at the cost of a heavy re-import and freshness coupled to import cadence), and
absolute cross-format scoring, EDHREC, and meta-tier are each cut with a stated reason. Open Questions
(§9) are genuinely open (weighting, benchmark composition, earliest-turn heuristic), not rhetorical.

The one real tension: **the acceptance gate rests on an unresolved open question.** Success Metric 1
("Calibration benchmark passes") is the named acceptance gate, but the benchmark's *composition* is
Open Question #2. As written, the definition-of-done for the whole feature is not yet decidable.

### Findings
- **high** Acceptance gate depends on an open question (§6 SM1 ↔ §9 Q2) — the committed benchmark is *the* acceptance gate, yet its membership (which precons, which cEDH lists) is still open. Until composed, "done" is undecidable. *Fix:* commit at least a seed benchmark (e.g. 2–3 named WotC precons + 2 named cEDH lists) into the PRD or a linked file, even if it grows later, so the gate is testable on day one.

## Substance over theater — strong

No persona theater — personas were deliberately dropped for a single-operator tool, and the one usage
narrative (§3, Brad) actually exercises the headline diff use case rather than decorating it. The Vision
(§1.2) is product-specific (scoring + version-diffing a saved deck, honest about uncertainty) and would
not swap cleanly into another PRD. NFRs are earned, not boilerplate: NFR1 determinism is explicitly
justified as *what makes the diff trustworthy*, and the Karsten formulas / bracket-gating constants
(addendum C) are concrete thresholds, not "must be reliable." No findings.

## Strategic coherence — strong

The PRD has a clear thesis and bets on it: relative comparison of the owner's own decks is named the
headline (§1.1, Goal 2 marked *Headline goal*), and the feature set follows from it — determinism
(NFR1), stable diffable structured output (Goal 2 / FR22), and Success Metric 2 (diff sensitivity) all
serve that one arc rather than reading as a capability backlog. Counter-metrics are present and pointed
("no over-rating goodstuff piles", "no false precision"), directly targeting the source research's
hardest failure mode. This is not a backlog with headings.

## Done-ness clarity — thin (the load-bearing weakness)

Most FRs carry a testable consequence: FR1 (named tool + exact repository path + format enum), FR3
(count unresolved cards → confidence), FR8 (Karsten delta → flood/screw flag), FR11 (a concrete schema
field + backfill), FR14 (≥24h cache, 429 backoff). Good. But the **scoring core is underspecified in a
way that will block FG5 story creation**:

- **FR16** asks to "compute the 7-dimension vector … each 0–100" but gives no mapping from signals to
  any dimension's 0–100 value. An engineer cannot tell how "resilience" or "speed" becomes a number.
  The source research (`docs/deck-assess.md`) describes the dimensions conceptually but likewise gives
  no per-dimension formula.
- **FR19** "weighted-aggregate the vector" — the weights are Open Question #1 (hand-tuned then
  validated). Acceptable to defer *tuning*, but the aggregation *method* and the initial weight table
  should be pinned so FG5 is buildable and the determinism guarantee (NFR1) is well-defined.
- **FR21** confidence is `low | medium | high` derived from four factors, but there are **no thresholds**
  for what tips low→medium→high. Two implementers would produce different confidence outputs from the
  same deck — which also makes NFR1 determinism partly unverifiable across builds.
- **FR9** "8×8 structural-coverage gaps (e.g. 'ramp below baseline')" — "baseline" is undefined.
- Soft language in Success Metrics: SM1 "known cEDH lists … score high" (no threshold; the source
  research used ≥90 absolute, but absolute score is cut from v1, so a for-format threshold is needed);
  Counter-metric "must not score top-tier" (undefined band).

None of this is fatal for a hobby PRD that plans to hand-tune against a benchmark — but it is the
dimension downstream leans on hardest, and right now the FG5 stories can't be written without inventing
the scoring math.

### Findings
- **high** Per-dimension scoring is unspecified (FR16) — no signal→0–100 mapping for any of the seven dimensions; blocks FG5 story creation. *Fix:* specify (even roughly) how each dimension is derived from the FR5–FR15 signals, or explicitly state the per-dimension formulas are an architecture deliverable and mark FG5 as design-blocked until then.
- **medium** Aggregate weights + method undefined (FR19, §9 Q1) — deferring tuning is fine, but pin the aggregation method and a starting weight table so the build is deterministic and testable. *Fix:* include an initial documented weight vector (the source research says "start with transparent hand-tuned weights").
- **medium** Confidence has no thresholds (FR21) — `low/medium/high` factors are listed but not bounded, so the output isn't reproducible across implementations and weakly undermines NFR1. *Fix:* give threshold rules (e.g. ≥N unresolved cards or Spellbook-unreachable ⇒ at most `medium`).
- **low** Undefined "baseline"/"top-tier" adjectives (FR9, §6 counter-metric). *Fix:* cite the 8×8 baseline counts (addendum has redundancy figures) and a numeric for-format band for "top-tier".

## Scope honesty — strong

Among the best parts of this PRD. Non-Goals are explicit (§2.1) and cross-linked to the roadmap (§8);
rejected alternatives are catalogued with trade-offs (addendum A); de-scoping (absolute score,
percentile, EDHREC fields) is stated at the output-schema level (FR22, addendum B/D), not done silently.
Risks (§7) name the uncomfortable truths honestly — intent is not observable, cEDH can't be
auto-asserted, Standard has no official rubric. Open-items density (3 Open Questions + a handful of
deferrals) is entirely appropriate for the stakes. The only nit: the PRD uses no `[ASSUMPTION]` tags on
inferences (e.g. FR2's format inference, the bracket-tag→power map in addendum B), but for a solo
author who is also the operator, that formalism would be overhead, not value — not a defect here.

## Downstream usability — adequate

This PRD is chain-top (it feeds architecture and epics), so traceability matters. FR/NFR IDs are
contiguous and unique (FR1–FR23, NFR1–NFR7); cross-references resolve (§2.1→§8, NFR6→§6, FR11→addendum,
FR22→`docs/deck-assess.md`). The single narrative has a named protagonist (Brad). Two gaps:

1. **No Glossary.** Terms are mostly used consistently, but three overlapping scoring scales circulate —
   the 1–5 Bracket, the for-format 0–100, and a "familiar 1–10 secondary projection" (introduced only in
   FR19, never shown in the narrative, absent from Goals). A downstream reader could conflate them. A
   short glossary fixing "Bracket", "for-format score", "1–10 projection", "dimension vector",
   "confidence" would remove that risk.
2. Terminology drift is minor: "for-format 0–100 score" vs "for-format score" vs "score" — same referent,
   fine, but a glossary would anchor it.

### Findings
- **medium** No Glossary + three coexisting score scales (Goals, FR18/19, §3) — 1–5 Bracket vs 0–100 for-format vs 1–10 projection risk conflation downstream; the 1–10 projection appears only in FR19. *Fix:* add a 6–8 term glossary; either surface the 1–10 projection in Goals/§3 or cut it if it earns nothing.

## Shape fit — strong

Correctly shaped. This is a single-operator capability spec, and the PRD adopts exactly that form:
capability/FR-centric, one usage narrative instead of formal UJs, operational success metrics
(calibration/determinism/diff-sensitivity) rather than user-facing engagement metrics. It is neither
over-formalized (no UJ theater for a solo tool) nor under-formalized (the narrative + FRs + NFRs carry
the intent). NFR7 (stateless sync `def`, framework-free `src/logic`, MCP conventions) shows the shape is
matched to the actual codebase. No findings.

## Additional cross-cutting findings

- **medium** Unsupported-format behavior undefined (FR1/FR2) — FR1 accepts `commander | standard`, FR2 infers format from stored data; if inference yields Modern/Pioneer/etc., the PRD doesn't say whether the tool errors, defaults to a format, or degrades. This is a reachable path that could block or surprise downstream. *Fix:* state the fallback (e.g. unsupported inferred format ⇒ error with message, or fall back to `standard` heuristic path with a confidence reason).
- **medium** Spellbook schema-drift risk not surfaced in §7 — addendum B flags "verify live camelCase keys against the backend Swagger," implying real API-contract fragility, but §7 only lists availability (caching/backoff). Schema drift would silently break combo detection. *Fix:* add a §7 risk line for Spellbook response-schema drift, mitigated by tests against a captured fixture.
- **low** "Bracket floor (1–5)" vs "never assert Bracket 5" (FR18) — the stated range is 1–5 but output is effectively 1–4 (B5 flagged as candidacy only). Slightly self-contradictory wording. *Fix:* say "floor 1–4; B5 surfaced only as `cedh_candidate`."
- **low** Determinism input set (NFR1 ↔ SM3) — NFR1 correctly conditions determinism on fixed snapshot + cached combo data + profile version; SM3 says "identical inputs → identical output" without naming that those three are part of "inputs." *Fix:* make SM3 reference the NFR1 input tuple so the regression test pins snapshot/cache/profile.

## Mechanical notes

- **ID continuity:** FR1–FR23 and NFR1–NFR7 contiguous, unique, no gaps or duplicates. Good.
- **Cross-refs:** all resolve — §2.1→§8, §7/FR11→addendum, FR22/addendum→`docs/deck-assess.md §7.3`, NFR3→existing `index_unavailable` pattern.
- **Assumptions Index:** none present; no inline `[ASSUMPTION]` tags to round-trip. Acceptable for a solo PRD (see Scope honesty).
- **Glossary:** absent — see Downstream usability (medium).
- **Narrative protagonist:** §3 names Brad and carries context inline. Good.
- **Score-scale drift:** 1–5 / 0–100 / 1–10 — flagged above; the 1–10 projection is the least anchored (FR19 only).
- **Required sections for shape/stakes:** all present (Overview, Vision, Goals, Non-goals, narrative, FRs, NFRs, Success/Counter-metrics, Dependencies/Risks, Roadmap, Open Questions) plus a downstream-depth addendum. Appropriate and complete for a lean single-operator PRD.
