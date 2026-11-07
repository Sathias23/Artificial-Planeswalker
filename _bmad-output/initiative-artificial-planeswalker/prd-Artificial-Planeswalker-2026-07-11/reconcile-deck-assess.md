# Input Reconciliation — `docs/deck-assess.md` → PRD + Addendum

**Date:** 2026-07-11
**Source input:** `docs/deck-assess.md` (research paper)
**Derived artifacts:** `prd.md`, `addendum.md` (same folder)

## Method

Read the source research paper end to end, then read both derived artifacts. Flagged
only material items that the PRD/addendum **silently dropped** — present in the research,
not reflected in the derived specs, and **not** among the author's declared deliberate v1
cuts.

**Declared v1 cuts (NOT flagged, confirmed cleanly out of scope):** calibrated
cross-format absolute score + per-format offset, EDHREC enrichment (inclusion/synergy/
salt/percentile), Monte Carlo goldfish simulation, ML/embeddings, Limited/Draft, 60-card
meta-tier scraping (MTGTop8/Goldfish), dedicated compare tool.

**Items correctly carried across (spot-check, no action needed):** 7-dimension vector,
Game Changers detection + bracket gating, hard triggers (mass land denial, extra-turn
chains), two-card combo detection via Spellbook + bracket-tag mapping, Karsten land-count
formulas, rule-of-8 redundancy, 8×8 structural coverage, hypergeometric consistency,
"pile of good cards" counter-metric, cEDH candidate-only flagging, "bracket up when in
doubt," graceful degradation, format-profile versioning, unresolved-cards-lower-confidence.

---

## GAPS (highest value first)

### Gap A — Numeric confidence *interval* (`low`/`high`) collapsed into a bare confidence *level*

**Research:** Option G (§2) calls `{score, low, high, confidence, reasons[]}` **"Mandatory."**
The §7.3 schema attaches a `low`/`high` band to *every* score (`for_format_score: {value:68,
low:60, high:74}`). §7.1 step 6 says "Emit interval + reasons." The §8 cross-cutting rule:
"always ship the confidence interval."

**Artifacts:** FR21 emits only a categorical `confidence` (`low|medium|high`) + `reasons[]` —
the numeric band is gone from the FR text. FR19 produces a single for-format value and a 1–10
projection with no interval. FR22 says "return the `deck-assess.md` schema minus absolute/
percentile/EDHREC," which technically *retains* the `for_format_score.low/high` fields, but no
FR ever specifies **how** the band is computed. Net effect: the paper's single most-emphasized
epistemic-honesty mechanism is either dropped or left undefined, and the two FRs contradict
(FR22 keeps the fields, FR19/FR21 never populate them).

**Why Brad may want to reconsider:** This is the qualitative "honest about uncertainty" spine
of the whole design. A bare `medium` label communicates far less than `68 (60–74)`. Decide
explicitly: compute a real band, or consciously drop it and reconcile FR19/FR21/FR22.

### Gap B — Descriptive/categorical *label* layer (Option F) dropped, worst for Standard

**Research:** Option F recommends human-facing descriptive labels ("Unfocused / Focused /
Tuned / High-Power / Competitive") as "the human-facing summary layer atop the numeric/vector
core," precisely because words are "honest about imprecision." §8 cross-cutting: "never present
the absolute scalar without the categorical label."

**Artifacts:** Commander keeps the WotC Bracket label (Exhibition/Core/Upgraded/Optimized/
cEDH) — good. But **Standard (FR20) gets a bare 0–100 number with no label at all** ("No
Bracket, no meta-tier percentile"). A naked scalar with no descriptive tier is exactly the
"false precision" the paper warns against, and Standard is the format with the *least* rubric
backing the number.

**Why Brad may want to reconsider:** A lightweight descriptive band for Standard (and as a
tone-softening summary word generally) costs almost nothing and preserves the research's
humble voice. Without it, Standard output reads as more precise than it is.

### Gap C — `speed` dimension retained, but its primary engine (goldfish win-turn) was cut, leaving it under-specified

**Research:** Speed = "average/goldfish win turn" (§1.1). The §7.3 schema shows
`speed: {avg_win_turn_estimate: 8.5, method: "montecarlo+heuristic"}`. Monte Carlo goldfish
(§3.4) is the paper's main tool for the win-turn distribution.

**Artifacts:** FR16 keeps `speed` as one of the seven dimensions. Monte Carlo is a declared v1
cut. But nothing in the FRs says how `speed`/`avg_win_turn_estimate` is derived deterministically
once simulation is gone. The only deterministic speed signals available are combo
earliest-turn (FR13) and curve/avg-MV.

**Why Brad may want to reconsider:** This is a tension, not just an omission — a dimension is
promised whose main computation method is explicitly out of scope. Either specify the
heuristic proxy (curve + combo earliest-turn + format win-turn band) or mark `speed` as a
low-confidence/coarse dimension in v1. Right now it silently over-promises.

### Gap D — Mana-base *quality* reduced to land *count*; colored-source / pip consistency dropped

**Research:** §1.3 names mana-base quality "the single biggest hidden lever." §3.4 + Appendix
give the colored-source math distinct from land count: 1 pip ≈14 sources (~86% opener), 2 pips
≈18 (~69% for ≥2), plus multivariate hypergeometric for colored-source requirements feeding the
consistency dimension.

**Artifacts:** FR8 keeps only the **Karsten land-*count* delta**. Addendum §C copies the land
formulas and redundancy percentages but omits the colored-source/pip numbers. FR17
(hypergeometric) mentions "mana access by turn" but no FR encodes colored-pip source
requirements. So `mana_efficiency` and `consistency` grade quantity of lands, not quality of
fixing — for a Commander tool where multicolor fixing is central, that under-weights the lever
the paper calls most important.

**Why Brad may want to reconsider:** Colored-source consistency is cheap deterministic math
(already have colors/pips locally) and directly strengthens two dimensions. Its omission is
easy to miss because "Karsten" appears to be covered.

### Gap E — Commander's "social-first" framing dropped (tone/voice nuance)

**Research:** §1.1 stresses Commander "is explicitly 'social-first,'" victory "takes a backseat
to social interaction and meaningful participation," and "a purely win-oriented metric is
incomplete." §9 reinforces intent-not-observable and the social axis.

**Artifacts:** Neither the PRD nor addendum mentions the social dimension or frames the
Commander output as anything other than a power/win metric. The tool as specified will happily
imply a higher-bracket deck is "better," which the research explicitly says is wrong framing for
non-cEDH Commander.

**Why Brad may want to reconsider:** Pure qualitative/voice item the FR structure naturally
loses. Cheap to honor: a one-line caveat in the human-readable `reasoning`/summary that a higher
bracket ≠ "better," only "higher-powered / less casual-social." Preserves the paper's honest
tone.

---

## Secondary gaps (lower value; note-and-decide)

### Gap F — Spellbook `estimate-bracket` endpoint not used as a free cross-check

§3.3 notes the backend exposes an `estimate-bracket` whole-deck endpoint. The PRD computes the
Bracket entirely itself (FR18) and already calls the same backend for combos (FR13). Using
`estimate-bracket` as a cheap confidence cross-check (agreement → higher confidence; divergence
→ lower) is a low-cost signal that was dropped. Not required, but a natural free calibration
input the artifacts don't mention.

### Gap G — Standard sideboard / best-of-3 adaptability edge case dropped

§4 (60-card rubric) calls out the 15-card sideboard and "evaluate best-of-3 adaptability
separately." Standard decks have sideboards; FR20 ignores them entirely. Minor given Standard is
the "lighter second format," but it's a real 60-card evaluation axis silently omitted — worth a
one-line explicit "sideboard out of scope for v1" so it's a decision, not an oversight.

### Gap H — Heuristic-formula edge-case failure caveat not carried into Risks

§6 documents that explicit formula scorers (Disciple of the Vault's `P = …`) have "documented
edge-case failures, e.g. commander-centric aggro/tribal decks." The PRD's own weighted aggregate
(FR19) is the same class of scorer and inherits the same blind spot (commander-as-engine /
tribal payoff decks whose power lives in one card, not the 99). This caveat belongs in §7
Risks / §9 Open Questions but is absent.

---

## Summary of recommended reconsideration

The FR structure preserved the *quantitative skeleton* well but shed most of the research's
*epistemic-honesty and voice* layer: the numeric confidence band (A), descriptive labels (B),
the social-first framing (E), and the honest under-specification of `speed` once simulation was
cut (C). Gap D is the one substantive *analytical* omission hiding behind a covered-looking
label ("Karsten"). Gaps F–H are cheap decisions worth making explicit rather than leaving
silent.
