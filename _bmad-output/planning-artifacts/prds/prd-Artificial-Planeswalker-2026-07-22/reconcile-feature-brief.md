# Reconciliation: Feature Brief → PRD + Addendum

**Source input:** `docs/companion-app-feature-brief.md` (2026-07-22)
**Targets:** `prd.md`, `addendum.md` (this directory)
**Date:** 2026-07-22

Known intentional deltas (per intake instructions) are **not** reported as gaps: OQ-2/3/4
resolved by the user (separate tools; power panel post-MVP; latest + session history);
OQ-1/OQ-5 deferred to design with constraints parked in the addendum; new FR-18/19/20/21,
G5, SC-5, CM-1..3, NFR-08 added deliberately.

## Verdict

**No substantive gaps.** Every requirement, decision, risk, and success criterion in the
brief lands in the PRD or addendum. Three minor wording/coverage losses and one
intentionally corrected internal inconsistency are noted below (M1–M4). None blocks
downstream work; M1 is the only one worth a one-line fix.

## Per-section coverage table

| Brief section | Item | Landed in | Status |
|---|---|---|---|
| §1 Overview | Side-by-side companion, presentation-layer-only, never bypasses/duplicates logic | PRD §1 | Covered |
| §2 Problem | Visual activity, structured results, no persistent synced surface | PRD §2 | Covered (lightly reworded, no loss) |
| §3 Goals | G1 live deck view | PRD §4 G1 | Covered verbatim |
| | G2 agent-pushed ephemeral content | PRD §4 G2 | Covered verbatim |
| | G3 local-first / no API keys | PRD §4 G3 | Covered |
| | G4 stateless MCP + graceful degradation | PRD §4 G4 | Covered verbatim |
| §4 Non-goals | NG1–NG5 | PRD §5 NG1–NG5 | All covered (NG5 slightly strengthened: "work identically") |
| §5 Users | Single local user, browser snapped beside terminal | PRD §3 + UJ-1 | Covered and elaborated |
| §6 Architecture | Three processes; FastMCP stdio stateless; backend responsibilities (SPA, read-only REST, WS broadcast, authed `/agent/events`, image proxy+cache, discovery file); Vite+React SPA; two state inputs | PRD §6 | Covered |
| | zustand; agent never touches store; handlers call `store.setState`; suggested slices | Addendum (key decisions) | Covered |
| | Agent-push data flow; deck-sync flow | PRD §6 (condensed) | Covered |
| | Fallback paragraph: decks are DB rows not files; `PRAGMA data_version` polling | PRD FR-16 + addendum transport bullet | Covered |
| §7 FR-01 | Configurable port, default 8765 | PRD FR-01 (Feature A) | Covered; ephemeral fallback merged in from risk table |
| §7 FR-02 | `/api/decks`, `/api/deck/{id}` | PRD FR-02 | Covered verbatim |
| §7 FR-03 | `/api/cards/{card_id}` hydration | PRD FR-03 | Covered verbatim |
| §7 FR-04 | Image proxy + disk cache | PRD FR-04 | Covered; deliberately extended with `face=` param (backed by addendum DFC verification) |
| §7 FR-05 | Grid + list view, type groups, curve summary | PRD FR-05 | Covered verbatim |
| §7 FR-06 | `POST /agent/events` + WS relay | PRD FR-06 | Covered verbatim |
| §7 FR-07 | `companion_set_active_deck` | PRD FR-07 (Feature E) | Covered verbatim |
| §7 FR-08 | `companion_show_suggestions` | PRD FR-08 | Covered verbatim |
| §7 FR-09 | `companion_show_swaps`, P1 | PRD FR-09, P1 | Covered verbatim |
| §7 FR-10 | `companion_show_tier_list`, P1 | PRD FR-10, P1 | Covered verbatim |
| §7 FR-11 | Mutation tools emit `deck_changed` | PRD FR-11 | Covered verbatim |
| §7 FR-12 | Graceful degradation, never hard error | PRD FR-12 | Covered verbatim |
| §7 FR-13 | IDs only; printing UUID canon; name→ID stays in MCP tools | PRD FR-13 | Covered; see M2 (dropped tail clause) |
| §7 FR-14 | Discovery file lifecycle | PRD FR-14 | Covered; `{port, token}` contents made explicit |
| §7 FR-15 | Connection status + active deck | PRD FR-15, P1 | Covered verbatim |
| §7 FR-16 | `data_version` polling, P2 | PRD FR-16, P2 | Covered verbatim |
| §7 FR-17 | Card detail view, P1 | PRD FR-17, P1 | Covered ("full art" → "full-size card face", consistent with FR-19) |
| §8 NFR-01 | Security: 127.0.0.1, token, CORS, WS ticket, Host validation | PRD NFR-01 | Covered; see M1 (two rationale clauses dropped) |
| §8 NFR-02 | WAL, read-only connections, sole writer | PRD NFR-02 | Covered verbatim |
| §8 NFR-03 | Pydantic contract, REST as schema boundary | PRD NFR-03 | Covered verbatim |
| §8 NFR-04 | Reconnect + refetch, fire-and-forget | PRD NFR-04 | Covered verbatim |
| §8 NFR-05 | 1 s render / 250 ms latency | PRD NFR-05 | Covered verbatim |
| §8 NFR-06 | Offline after cache warm-up | PRD NFR-06 | Covered verbatim |
| §8 NFR-07 | Tooling parity; Node dev/CI-only | PRD NFR-07 | Covered; "mypy" strengthened to "mypy strict" (matches project reality, not a weakening) |
| §9 Decisions | Web-first not Electron; Tauri preferred; same-URL wrap argument | Addendum bullet 1 | Covered |
| | FastAPI shared codebase | Addendum bullet 2 | Covered; console-script detail merged here |
| | HTTP+WS transport, not file-watching | Addendum bullet 3 | Covered; see M4 (brief's internal inconsistency corrected) |
| | zustand client-side only + slices | Addendum bullet 4 | Covered; `agentPanel` slice updated for FR-18 (consistent) |
| | Distribution: console script + plugin skill | Addendum bullets 2 & 6 | Covered |
| | Frontend packaging: bundle as package data, CI drift-check, `plugin/` mirror | Addendum bullet 5 | Covered verbatim |
| §10 Risks | App closed | PRD risk 1 | Covered |
| | Port conflict | PRD risk 2 + FR-01 | Covered |
| | Stale discovery file / `GET /health` | PRD risk 3 | Covered |
| | SQLite lock contention / "database updating" state | PRD risk 4 | Covered |
| | Scryfall hotlink etiquette | NFR-08 + CM-2 + NFR-06 | Covered elsewhere; see M3 (row removed from risk table) |
| | Payload schema drift | PRD risk 5 | Covered; drift-check made explicit |
| §11 Success | SC-1–SC-4 | PRD §9 | All covered verbatim |
| §12 Open Qs | OQ-1 → OQ-A (deferred, constraints parked) | PRD §12 + addendum | Intentional |
| | OQ-2/3/4 resolved | Addendum "Rejected alternatives" + FR-18/FR-21 | Intentional |
| | OQ-5 → OQ-B | PRD §12 + addendum | Intentional |
| §13 Phasing | Phase 1: FR-01–08, 11–14; NFR-01–04, 06 | PRD §11 Phase 1 | Covered; +FR-19/20, NFR-08 deliberate |
| | Phase 2: FR-09, 10, 15, 17; NFR-05 | PRD §11 Phase 2 | Covered; +FR-18 deliberate |
| | Phase 3: FR-16, Tauri, UI edits, power panel | PRD §11 Phase 3 | Covered (power panel = FR-21) |

## Detailed gap discussion

### M1 — NFR-01 lost two security-rationale clauses (minor, worth restoring one line)

The brief's NFR-01 contains two clauses the PRD condensed away:

1. *"upgrades without a valid ticket are rejected"* — the PRD says WS upgrades "are
   authenticated via a short-lived ticket", which implies rejection but no longer states
   the enforcement behavior. An implementer could read "authenticated" as
   best-effort/logging. One clause restores the hard requirement.
2. *"Together these mitigate malicious-webpage-to-localhost attacks"* — the threat-model
   summary naming the attack class the whole NFR-01 stack exists to stop. Without it, the
   ticket + Host-validation mechanisms read as arbitrary hardening; downstream architecture
   loses the "why" that lets it evaluate substitutions. The parenthetical "(CORS-protected,
   so unreadable cross-origin)" rationale for why the ticket endpoint is safe was also
   dropped.

Suggested fix: append to PRD NFR-01 something like "Upgrades without a valid ticket are
rejected. Together these mitigate malicious-webpage-to-localhost attacks."

### M2 — FR-13 dropped the agent-usage tail clause (trivial)

Brief FR-13 ends "...agents use the IDs those tools return." The PRD keeps the
resolution-ownership statement but drops this operational instruction for agent-facing
docs/tool docstrings. Substantively implied; zero risk to requirements, mild loss for
whoever writes the companion-tool docstrings/skill. No action needed, or fold into the
plugin-skill bullet in the addendum.

### M3 — Scryfall hotlink risk row removed from the risk table (covered elsewhere)

The brief's risk table had "Scryfall image hotlink etiquette → disk cache per FR-04
satisfies Scryfall's caching guidance and enables offline use". The PRD risk table drops
this row, but the content is fully absorbed: NFR-08 (disk caching, no hotlink hammering,
attribution), CM-2 (at most one CDN hit per image+size), NFR-06 (offline). Net coverage is
*stronger* than the brief; only the risk-register framing is gone. Not a gap in substance.

### M4 — Brief's file-watching inconsistency was silently corrected (intentional, not a gap)

Brief §9 says "File-watching is reserved for the FR-16 fallback", but brief §6 and FR-16
themselves say file-watching does not apply (decks are DB rows) and the fallback is
`PRAGMA data_version` polling. The addendum's transport bullet resolves this in favor of
the polling description, which matches FR-16 in both documents. Recording here so the
divergence from the brief's literal §9 text is traceable as a correction, not a drop.

### Confirmed non-gaps (checked explicitly)

- **Tone/philosophy:** "presentation layer only", "never bypasses or duplicates",
  local-first/no-API-key, stateless/session-scoped, "the agent drives, the app shows"
  spirit — all present; the PRD's UJ-1 and G5/FR-20 amplify rather than dilute.
- **Priorities:** every FR keeps its brief priority (P0/P1/P2) unchanged; regrouping into
  Features A–G loses no assignments.
- **Weakened wording:** none found; the deltas run in the strengthening direction
  (mypy → mypy strict, NG5 "identically", explicit drift-check, `{port, token}` contents).
- **Caveats:** "vitest or similar", "e.g. S/A/B/C", "prices if present in local data",
  "or similar console script", "fire-and-forget", "refetch over diff/patch" — all retained.
