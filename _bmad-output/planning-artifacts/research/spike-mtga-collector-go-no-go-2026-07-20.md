# Step-0 Spike: MTGA Collection Collector on the Live 2026 Client — **GO**

**Date:** 2026-07-20 · **Verdict:** **GO on feasibility** — confirmed 2026-07-20 by Brad's
in-client count check (Yuna, Hope of Spira ×3, Get Lost ×3, Omnath, Locus of the Roil ×1 all
match the export). See "The reframed question" for the supplier-viability half.
**Question under test** (from [technical-mtga-collection-ingestion-research-2026-06-28.md](technical-mtga-collection-ingestion-research-2026-06-28.md)):
*Can a collector produce a usable owned-count snapshot from the live 2026 MTGA client?* — plus the
2026-06-28 addendum's reframe: *is there a MAINTAINED collector with a CONSUMABLE export?*

## Result

`NthPhantom10/MTGA-collection-exporter` (MIT, Python, last commit 2026-03-16), run 2026-07-20
against the live Steam client, extracted **7,935 per-printing `{grpId: qty}` entries** in one scan.

| Check | Result |
|---|---|
| Memory scan (pymem, anchor-calibrated) | ✅ collection block found; 7,935 entries |
| Local id→name resolution (`Raw_CardDatabase_*.mtga`) | ✅ **7,935/7,935 (100%)** |
| Scryfall `arena_id` join (30-card random sample) | ✅ **30/30 resolved**; all 30 names exactly equal (note: the checker's match predicate was looser than exact — exactness was confirmed after the fact) |
| Known-count eyeball | ✅ Brad confirmed in-client 2026-07-20: Yuna ×3, Get Lost ×3, Omnath ×1 all match |

**Count evidence, honestly bounded.** Four cards seeded as qty-1 anchors from Brawl singleton decks
came back ×1 in the export (Omnath, Locus of the Roil; Nylea, Keen-Eyed; Craterhoof Behemoth (TDM);
plus Toski ×1 unseeded). Kotis, the Fangkeeper and Sephiroth, Fabled SOLDIER — also seeded qty-1 —
came back ×4, plausible from their Standard builds but not externally confirmed. Up the Beanstalk ×4
and Assassin's Trophy ×4 are deck-derived plausibility only. Note the scan log shows Sephiroth's
qty-1 anchor *did* pattern-match somewhere (likely a deck-list structure holding `(grpId, 1)`), so
anchor hits are NOT proof of exact collection counts — the export's counts rest on the 1-of
agreements and Brad's in-client confirmation (Yuna ×3, Get Lost ×3, Omnath ×1 — includes
non-anchor, non-4-capped counts), not on scan mechanics. No completeness cross-check of the
7,935 total was possible in-session (no in-client total compared, single scan run); `find_blocks`'s
largest-block heuristic could in principle truncate — worth a second-run diff in Phase A testing.

## The reframed question: maintained collector with a consumable export?

**Strictly: no. Practically: yes, as a trivially-re-patchable MIT base.** After only 4 months of
drift, the stock tool (a) loads **0 cards** from the current client's card DB (localization text
moved to `Localizations_enUS(LocId, Loc)`; the stock `Localizations(Id, Text, Format)` query dies),
and (b) crashes outright on grpIds whose packed bytes contain regex metacharacters —
`pymem.pattern_scan_all` compiles the pattern as a regex, and e.g. Nylea 70696 = `0x11428` contains
`0x28` = `(`. Fix: `re.escape()`. Additionally its export drops what Phase A wants: v2.0 aggregates
to name/set and discards raw grpIds.

Patches applied to the throwaway spike copy (upstream untouched): the schema fallback, the
`re.escape` fix, Brad's custom Steam library path (`C:\games\...` — stock hardcodes 3 paths and
otherwise falls back to a 525 MB Scryfall download), and an added raw `{grpId: qty}` dump. A fourth
issue was hit in our *checker*, not patched into the exporter copy: Scryfall returned HTTP 400 to
python-requests' default User-Agent (observed live, then fixed with a real UA header and re-run
successfully; the exporter's own Scryfall fallback also failed before a UA was ever relevant —
`'download_uri'` KeyError — and was not exercised further since the local DB path worked).
Cosmetic: the `█` progress bar needs `PYTHONIOENCODING=utf-8` on piped Windows output.
Upstream is 362 lines; all patches are one-to-five-liners.

**Consequence per the addendum:** supplier viability is confirmed *as self-maintained MIT code*,
not as a hands-off dependency. This re-opens a narrow decision for the epic (see below); it does
not overturn the consume-output architecture, ACL, or ManaBox-CSV canonical contract.

## Findings to carry into Phase A

1. **Per-printing entries confirmed first-hand:** Lightning Strike = 6 grpIds (XLN ×4, M19 ×4,
   DMU ×2, DFT ×1, MSH ×1, TLA ×1 = 13 copies). `arena_card_map` + oracle-level aggregation is
   mandatory, as predicted. The added raw-id dump is one *adapter input* behind the ACL — the
   canonical contract stays ManaBox CSV (which carries no grpIds; name/set/cn resolves instead).
2. **Anchor traps for onboarding docs:** anchors must name the *owned printing* — the JMP
   Craterhoof anchor (72447) missed silently because Brad owns only the TDM printing (95660).
   Wrong-quantity anchors also miss. Deck-derived seeding (this spike pre-seeded
   `last_anchors.json` from saved Brawl singletons, bypassing the interactive 5-card prompt — which
   was therefore never exercised) is a promising pattern, not a validated UX.
3. **The 30/30 Scryfall sample does NOT retire the `arena_id`-gap risk** (~0.4% coverage, no
   deliberately-risky ids like Alchemy `A-`/rebalanced probed). The research's Med-likelihood gap
   risk and its report-unmatched mitigation stand unchanged. The strong result is the 100% *local*
   resolution.
4. **Open decision for Brad at epic kickoff** — how users obtain a working collector:
   (a) document a patch-set/fork of the MIT exporter (keeps "we never read game memory ourselves");
   (b) ship our own thin exporter script derived from it. **(b) would reverse the recorded
   2026-06-28 decision** ("do NOT port memory-reading into our codebase") and weaken the ToS-risk
   mitigation that rests on it — flagged, not recommended. Import tools stay collector-agnostic
   either way.
5. Snapshot is point-in-time; staleness/degraded-mode design from the research stands.

Spike artifacts (patched exporter, checker, raw export, resolution report) are throwaway in the
session scratchpad; nothing entered `src/`. Spec trace:
[spec-mtga-collection-step0-spike.md](../../implementation-artifacts/spec-mtga-collection-step0-spike.md).
