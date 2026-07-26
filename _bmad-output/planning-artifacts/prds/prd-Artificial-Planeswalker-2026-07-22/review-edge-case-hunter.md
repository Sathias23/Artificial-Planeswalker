# Edge-Case Hunter Review — Companion App PRD

**Target:** `prd.md` + `addendum.md` (prd-Artificial-Planeswalker-2026-07-22)
**Method:** exhaustive branch/boundary walk of the FR/NFR set across six domains: service lifecycle, deck sync, imagery, agent panel, auth, database. Only unhandled or under-specified cases are reported; cases the PRD/addendum already covers (ephemeral-port fallback, stale-discovery health check, WAL + read-only connections, DFC `face` param + per-face cache keys, WS reconnect-and-refetch, mid-refresh "database updating" state, max-payload-size parking in OQ-A) were verified and discarded.

**Severity legend**
- **REQ** — needs an FR/NFR change or addition before the PRD is implementation-ready.
- **AMEND** — a one-sentence clarifying amendment to an existing FR/NFR is recommended; otherwise ambiguity leaks downstream.
- **DESIGN** — genuinely delegable to architecture/UX; listed so the downstream doc has a checklist, no PRD change required.

---

## 1. Service lifecycle

### EC-01 — Two backend instances started concurrently — **REQ**
**Scenario:** User (or a second terminal/session) runs `companion` twice. Per FR-01 the second instance falls back to an ephemeral port and per FR-14 overwrites the discovery file. Result: two live backends, tools follow the newest discovery file, any UI open against the first instance keeps a live WS but never receives another agent event.
**Why uncovered:** FR-01/FR-14 define fallback and file-write behavior but no singleton policy — nothing says whether a second instance must refuse to start, take over, or coexist; the risk table's port-conflict row assumes the conflicting listener is a *different* app.
**Severity:** REQ. Feature A needs one requirement: single-instance enforcement (e.g. health-check the discovered instance and exit "already running") or an explicitly defined winner. This is a product behavior, not a design detail — it decides what the user sees when they double-launch.

### EC-02 — Backend restarts onto a different (ephemeral) port while UI is open — **DESIGN**
**Scenario:** Backend crashes/restarts; original port now taken, so it comes up ephemeral. The browser tab's origin is dead; NFR-04 backoff reconnects forever against a port nothing listens on. The browser cannot read the discovery file, so the UI has no rediscovery path — only the terminal shows the new URL.
**Why uncovered:** FR-15 covers *showing* disconnected status; nothing covers recovery guidance when the port changed.
**Severity:** DESIGN (UX spec: disconnected state should tell the user to check the terminal/relaunch URL). Delegable, but the UX spec should receive it explicitly.

### EC-03 — Corrupt or partially written discovery file — **DESIGN**
**Scenario:** Crash mid-write (FR-14 "writes and refreshes") or truncated JSON leaves `companion.json` unparseable; separately, a tool may read the file while the backend is rewriting it.
**Why uncovered:** The risk table handles *stale-but-valid* files via `GET /health`; FR-12 handles *unreachable* backends. An unparseable file is a distinct branch — tools have no port to health-check. Atomic write (temp+rename) is never required.
**Severity:** DESIGN. Amend nothing; hand architecture two lines: parse failure ⇒ treat as "app not running" (FR-12 path), and discovery-file writes must be atomic.

### EC-04 — Stale discovery file, port reclaimed by a foreign process — **AMEND**
**Scenario:** Backend crashed; another local app now listens on the recorded port and happens to answer `GET /health` with 200. The tool proceeds to POST the shared token (and payload) to an unknown process.
**Why uncovered:** The risk-table mitigation ("validate with lightweight `GET /health`") verifies liveness, not identity. NFR-01 threat model covers browser→localhost attacks, not token disclosure to a port squatter.
**Severity:** AMEND. One clause in NFR-01 or the risk row: health/identity response must prove it is *this app instance* (e.g. echoes an instance ID from the discovery file) before the token is sent.

---

## 2. Deck sync & agent control

### EC-05 — Active-deck state: where it lives, and the never-set case — **REQ**
**Scenario:** (a) User opens `localhost:8765` before any `companion_set_active_deck` call — what does the deck view render? (b) User refreshes the page — is the active deck remembered? (c) Backend restarts — does the active deck survive? All three depend on where active-deck state lives (backend memory? per-WS-client? browser store only?), which the PRD never states.
**Why uncovered:** FR-07 defines the switching tool, FR-15 the display, and the addendum names an `activeDeck` zustand slice — but the authoritative locus and the empty/initial state are unspecified. Note the tension with CM-3 ("no new server-side session state anywhere"): if read literally, the backend may not hold the active deck either, yet the UI must survive refresh (NFR-04 "refetches the active deck on reconnect" presumes someone remembers which deck is active).
**Severity:** REQ. FR-07 needs one sentence naming the state owner and the defined empty state (e.g. "backend holds the active-deck ID in memory; before any set-active call, and after backend restart, the UI shows a no-active-deck state listing available decks"). CM-3 should be scoped to the MCP server if the backend is the owner.

### EC-06 — Active deck deleted while active — **AMEND**
**Scenario:** `delete_deck` removes the deck the UI is displaying. If deletion emits `deck_changed`, the refetch of `GET /api/deck/{id}` returns 404; if it doesn't emit, the UI shows a ghost deck indefinitely.
**Why uncovered:** FR-11 covers mutation→event→refetch for decks that still exist; no FR defines the refetch-404 branch or whether delete counts as a mutation for FR-11.
**Severity:** AMEND. FR-11 one-liner: deletion emits the event, and a refetch that 404s clears to the no-active-deck state (as defined by EC-05).

### EC-07 — `deck_changed` for a non-active deck — **AMEND**
**Scenario:** Agent mutates deck B while deck A is active (multi-deck sessions are normal). FR-11 says "the UI refetches on receipt" — refetches what? If the event carries no deck ID, every mutation anywhere triggers an active-deck refetch (harmless but noisy); if it carries one, the UI should filter — neither is stated. FR-16's *deliberately* deck-agnostic event implies FR-11's event is deck-scoped, but only by inference.
**Why uncovered:** FR-11 does not state whether the event identifies the deck or whether the UI filters against the active deck.
**Severity:** AMEND. One clause: `deck_changed` carries the deck ID; UI refetches only when it matches the active deck (deck-list panel may refresh regardless).

### EC-08 — Refetch racing a second mutation — **DESIGN**
**Scenario:** Two rapid mutations fire two `deck_changed` events; the UI issues two refetches whose responses can arrive out of order, leaving the *older* decklist rendered last.
**Why uncovered:** NFR-04's "something changed, refetch" model never requires latest-wins (coalescing, in-flight cancellation, or a monotonic version check).
**Severity:** DESIGN. Standard client-side pattern; delegate with an explicit note that NFR-04 implies latest-wins semantics.

### EC-09 — Agent event delivered to zero connected clients — **REQ**
**Scenario:** Backend is up (health passes) but no browser tab is open, or the only tab is mid-reconnect. FR-06 "relays payloads to all connected UI clients" is a silent no-op at zero clients; the MCP tool returns its success text and the agent tells the user "shown in the app" about content nobody saw. Same branch swallows `deck_changed` fired during a WS gap — deck sync self-heals via NFR-04's reconnect refetch, but agent-panel pushes are gone forever (fire-and-forget, no server history by design).
**Why uncovered:** FR-12 distinguishes only reachable/unreachable; there is no "reachable but nobody watching" outcome, and no requirement that the events endpoint report delivery reach.
**Severity:** REQ. FR-06 (or FR-12) should require the backend to report connected-client count in the `/agent/events` response so tools can return honest text ("companion app running but no browser connected — content not displayed"). This changes the tool contract, so it belongs in the PRD.

### EC-10 — Mutation persists but event emission fails — **DESIGN**
**Scenario:** A deck-mutation tool persists to SQLite, then its `deck_changed` POST fails (backend just died, token stale). Deck and UI now diverge until the next successful event or a page refresh; FR-16 (the polling fallback) is P2 and absent from MVP.
**Why uncovered:** FR-12's graceful-degradation text covers the *companion tools*; FR-11 never states whether existing mutation tools surface or swallow emission failure, and MVP has no fallback sync path.
**Severity:** DESIGN. Acceptable MVP behavior (reconnect-refetch covers most gaps), but architecture should decide deliberately: emission failure is silently swallowed (mutation result must not degrade) and the residual staleness window is accepted until FR-16.

---

## 3. Card imagery

### EC-11 — Card with no `image_uris` at all — **AMEND**
**Scenario:** Some Scryfall records carry `image_status: missing/placeholder` and null `image_uris` (and some `card_faces` entries lack per-face URIs). FR-04 "sizes resolve from the locally stored `image_uris`" has no branch for absent data; FR-05/FR-19's art grid has no placeholder requirement.
**Why uncovered:** The addendum verifies image data exists for the common case; the missing-image case appears nowhere.
**Severity:** AMEND. One clause in FR-04 (defined 404/placeholder response for imageless cards) plus a placeholder-card mention in FR-19/UX spec.

### EC-12 — Multi-face layouts beyond the DFC front/back model — **AMEND**
**Scenario:** FR-19 specifies click-to-flip for "double-faced cards" only. Meld results are *separate card objects* (the back face lives on a different printing UUID); split/adventure/battle cards are single-image but their `card_faces` array has two entries with no per-face images; Kamigawa flip cards are single-image rotated. A `face` param interpreted naively as "index into card_faces" 404s or mis-renders these layouts.
**Why uncovered:** The addendum's verified-availability note covers the transform/modal-DFC case only; the layout taxonomy (`cards.layout`) is never referenced by FR-04/FR-19.
**Severity:** AMEND. FR-04/FR-19 should say behavior is driven by Scryfall `layout` (faces exist only where per-face `image_uris` exist; all other layouts serve the single image), leaving per-layout rendering to the UX spec.

### EC-13 — Invalid `size`/`face` parameter values — **DESIGN**
**Scenario:** `size=huge`, `face=3` on a two-faced card, `face=1` on a single-faced card, or a `size` absent from that card's stored map. Response (400 vs. fallback-to-nearest-size) is unspecified.
**Why uncovered:** FR-04 defines only the happy path for both params.
**Severity:** DESIGN. Pure API-contract detail; delegate with a default suggestion (unknown size → 400; missing face → 404; single-faced + face=0 → the image).

### EC-14 — Scryfall CDN unreachable on a cold cache — **AMEND**
**Scenario:** First-ever deck load offline or behind a blocked CDN: every image fetch fails. Unspecified: what FR-04 returns (5xx? placeholder?), what the grid shows, and — critically — whether the backend retries. Naive per-render retries against a down/rate-limiting CDN violate CM-2's no-request-storms intent; nothing requires negative caching or backoff.
**Why uncovered:** NFR-06 explicitly scopes offline support to *after warm-up*; the cold-cache failure branch and its retry policy appear nowhere.
**Severity:** AMEND. Add a clause to FR-04 or NFR-06: on CDN failure serve a defined error/placeholder, apply backoff/negative caching so CM-2 holds, and retry on subsequent requests once reachable.

### EC-15 — Image cache: no size bound, no eviction, no integrity — **AMEND**
**Scenario:** (a) The disk cache grows unboundedly (full-face PNGs are ~1–2 MB; heavy use reaches GBs) — no NFR bounds it or names its location for uninstall/cleanup docs. (b) A crash mid-download leaves a truncated file that is then served forever ("disk-caching thereafter" has no validation branch). (c) A DB refresh can change a card's `image_uris` (rescans); a cache keyed by `scryfall_id+size+face` serves the outdated image indefinitely.
**Why uncovered:** FR-04/NFR-08 mandate caching but say nothing about bounds, atomic writes, integrity, or invalidation.
**Severity:** AMEND for (a) — cache location + bound/cleanup policy is a user-visible product property worth one NFR sentence. DESIGN for (b) and (c) — atomic temp-file writes and accepted staleness are architecture calls.

---

## 4. Agent panel

### EC-16 — Push references a card ID not in the local DB — **DESIGN**
**Scenario:** Agent hallucinates a UUID, or a data refresh removed the printing between resolution and push. `POST /agent/events` is fire-and-forget (presumably no ID validation), so the UI's FR-03 hydration 404s per card. Whether the UI drops the entry, shows an "unknown card" placeholder, or breaks the panel is unspecified — and whether the backend validates IDs at ingest is an open locus question.
**Why uncovered:** FR-13 defines the ID convention and hydration path but no failure branch; OQ-A parks schema *shape*, not referential validity.
**Severity:** DESIGN. Feed OQ-A: schema/endpoint decides validation locus; UI must render unknown-ID entries degraded, never fail the whole push.

### EC-17 — Empty payloads — **DESIGN**
**Scenario:** `companion_show_suggestions` with zero suggestions, a tier list whose tiers are all empty, a swap list with no pairs. Valid-but-empty renders (blank panel slide-in with animation per FR-20) are unspecified.
**Why uncovered:** OQ-A parks *max* sizes explicitly; minimums/empty semantics are not parked or covered.
**Severity:** DESIGN. Add empty-payload semantics (reject at schema vs. render empty-state) to the OQ-A parking list.

### EC-18 — Backend reachable but rejects the request — **REQ**
**Scenario:** The backend answers, with 4xx: 401 (stale token — see EC-20), 400/422 (schema mismatch after a version skew between an old MCP session and a newly upgraded backend), 413 (over the OQ-A max size). FR-12 promises graceful degradation only "if the backend is unreachable" — a rejecting backend is a different branch, and per FR-12's letter a tool could surface a hard error here.
**Why uncovered:** FR-12's condition is literally reachability; no FR defines tool behavior on non-2xx responses.
**Severity:** REQ. Broaden FR-12 to "unreachable *or any non-success response*" — the never-hard-error guarantee is the product promise, and the current wording leaves the most likely real-world failure (auth/schema skew) outside it.

*(Checked and already covered, not findings: push-before-deck-load — panel hydrates independently of deck state; history across reconnect — FR-18's clears-on-refresh rule is consistent, and gap-during-disconnect is EC-09; oversized-payload limits — parked in OQ-A.)*

---

## 5. Auth

### EC-19 — Ticket lifecycle details — **DESIGN**
**Scenario:** NFR-01's short-lived WS ticket: expiry duration, single-use vs. reusable, and the UI branch when an upgrade is rejected (ticket expired between `GET /api/session` and the upgrade — e.g. laptop slept mid-handshake). NFR-04's backoff loop must re-mint a ticket each attempt, which is implied but unstated.
**Why uncovered:** NFR-01 specifies existence and rejection, not lifetime, reuse, or the retry contract.
**Severity:** DESIGN. Architecture-level; note that reconnect must fetch a fresh ticket per attempt.

### EC-20 — Token rotation on backend restart vs. long-lived MCP session — **REQ**
**Scenario:** FR-14 implies a fresh token per backend startup. An MCP session started earlier read the old discovery file; if tools cache `{port, token}` per session (natural for a per-call latency budget), every post-restart call gets 401 for the rest of the session even though the app is running fine.
**Why uncovered:** No FR states whether tools read the discovery file per call or cache it, nor that a 401 must trigger re-read-and-retry. Combined with FR-12's unreachable-only wording (EC-18), the likely observed behavior is a misleading "app not running" — or an error — while the app is visibly open.
**Severity:** REQ. One sentence in FR-14 or FR-12: tools re-read the discovery file on each call (or on any auth failure) so a restarted backend is picked up transparently within a session.

---

## 6. Database

### EC-21 — DB file missing or never initialized at backend startup — **REQ**
**Scenario:** Fresh install (SC-4: "single `uv` command, no additional configuration") where the user launches the companion *before* any MCP session has built the central DB — project policy is build-on-first-run by the MCP side. `mode=ro` connections cannot create the file; the backend either crashes at startup or 500s on every deck/card endpoint.
**Why uncovered:** NFR-02 mandates read-only access; the risk table covers *transient* read failure mid-refresh; nobody covers the DB-not-yet-existing state, which SC-4's zero-config promise makes a first-run-likely path.
**Severity:** REQ. Feature A/F needs the defined state: backend starts successfully without a DB, serves the SPA, and the UI shows a "database not initialized — run the agent once / initialize_database" state rather than an error page. This is the first thing a curious fresh installer may hit.

### EC-22 — Read-only open of a WAL database — **DESIGN**
**Scenario:** SQLite gotcha: a `mode=ro` connection on a WAL-mode DB needs the `-shm` file to exist (or the `immutable` flag); if the backend starts when no writer has the DB open and `-shm` is absent, the open/first-read can fail even though the DB is healthy. Conversely `immutable=1` would break FR-16's ability to see refreshes.
**Why uncovered:** NFR-02 pairs "WAL" with "mode=ro" as if free of interaction; the failure branch between them is real and Windows-relevant.
**Severity:** DESIGN. Architecture must pick the concrete open recipe; flag it so it isn't discovered as a Story-1 bug.

*(Checked and already covered: bulk-refresh lock contention and the transient "database updating" surface — risk table; single-writer discipline — NFR-02; out-of-band change detection — FR-16, explicitly P2.)*

---

## Tally

| Severity | Count | IDs |
|---|---|---|
| REQ — FR/NFR change needed | 6 | EC-01, EC-05, EC-09, EC-18, EC-20, EC-21 |
| AMEND — one-line clarification recommended | 7 | EC-04, EC-06, EC-07, EC-11, EC-12, EC-14, EC-15 |
| DESIGN — delegable, hand down as checklist | 9 | EC-02, EC-03, EC-08, EC-10, EC-13, EC-16, EC-17, EC-19, EC-22 |
| **Total** | **22** | |

**Themes for the PRD editor:** (1) FR-12's degradation promise is scoped to "unreachable" but three found branches (4xx rejection, stale token, zero clients) sit outside it — one broadened sentence closes EC-09/EC-18/EC-20's product half. (2) Active-deck state ownership (EC-05) is the largest single ambiguity and touches FR-07, FR-15, NFR-04, and CM-3. (3) First-run ordering (EC-21) collides with SC-4's zero-config promise. All DESIGN items should ride into the architecture/UX-spec inputs as a checklist so they are decided deliberately rather than discovered.
