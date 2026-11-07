# Reviewer lens — adversarial seam

**Target:** `ARCHITECTURE-SPINE.md` (companion-app, 2026-07-25)
**Verdict:** FAIL — five holes where two compliant units still build incompatibly. All closed.

Lens: *"Construct two units one level down that each obey every AD to the letter yet still build
incompatibly."* Method: pick two plausible stories from the phasing, build them mentally against
the spine alone, and look for the place they meet.

## Findings

### S-1 — CRITICAL — AD-11 binds face handling to a column that does not exist

> AD-11 (draft): *"Face handling is driven by the card's `layout`."*

`src/data/models/card.py` has **no `layout` column**. The stored columns are `card_faces`
(JSON list) and `image_uris` (JSON dict). PRD FR-04 carries the same defect — it also says
"driven by the card's Scryfall `layout`".

**The divergence.** A Story-C builder reads the AD, finds no `layout`, and improvises: either
writes a migration + full Scryfall re-import (expensive, and the field would have to be
backfilled), or hardcodes a layout inference from `type_line`. A Story-B builder meanwhile
assumes DFC-ness from `card_faces is not None` — which is *wrong for split/adventure/flip*, since
those have `card_faces` but share one image. The two disagree about which cards get a flip
control (FR-19), and the UX contract silently breaks for adventure cards.

**Fix applied.** Drive face handling from **the presence of per-face `image_uris` inside
`card_faces`** — never from a layout string. This is exactly the correct signal and requires no
schema change: split/adventure/flip carry `card_faces` *without* per-face `image_uris`, so the
presence test naturally excludes them. It also matches what FR-04's own parenthetical already
says. PRD FR-04's `layout` wording should be corrected to match.

### S-2 — HIGH — No REST response/error convention; the UI cannot distinguish two states it must

**The divergence.** The project's MCP tools all return `*Result` objects with a `status` enum
(`ok | deck_not_found | database_not_initialized | …`). Nothing in the draft says whether the
REST layer follows that convention or uses HTTP status codes. Builder A ships
`GET /api/deck/{id}` → `200 {"status":"ok","deck":{…}}`; Builder B ships `200 Deck` with `404` on
absence. Both are defensible; only one matches the UI.

Worse, it is load-bearing for behaviour the UX spine already specifies. **FR-11** requires a
refetch 404 to clear to the *no-active-deck* state. **FR-22** requires a missing database to show
the *"Database not initialized"* state, and NFR-02's risk row requires a transient read failure
to show *"Database updating"*. Those are three different UI surfaces reached from the same
endpoint — and with no convention, they collapse into one indistinguishable failure.

**Fix applied.** New **AD-16**: REST is HTTP-native (status codes carry outcome, bodies carry
Pydantic schemas directly), with a single typed error body and a closed `reason` token set that
maps 1:1 onto the UX spine's state panels.

### S-3 — HIGH — "a defined placeholder response" is ambiguous in the one way that matters

**The divergence.** AD-11 says a failed image fetch "returns a defined placeholder response."
Builder A serves a generic grey card-shaped PNG — perfectly reasonable, and the UI now *cannot
tell* it failed. Builder B returns a non-image status the UI handles. But `DESIGN.md`'s card
placeholder renders **name + mana pips + type line** — data only the client has. Under Builder A
that placeholder can never appear, and the app silently degrades to grey rectangles.

**Fix applied.** AD-11 now states the backend **never serves a substitute image**; failure and
no-image-data are signalled distinguishably so the UI renders its own named placeholder.

### S-4 — HIGH — AD-9's notifier does not say `await` or `create_task`, and the difference is a lost event

**The divergence.** "Fire-and-forget" reads as `asyncio.create_task(...)` to one builder and
"await with a short timeout" to another. `create_task` inside a FastMCP tool that returns
immediately can be **garbage-collected or torn down before it runs** — the event never leaves the
process, and the deck view silently goes stale. The other builder's unbounded `await` makes every
deck mutation wait on the network. Both obey the AD as written.

**Fix applied.** AD-9 now specifies a bounded-timeout `await` (short, ~1 s) — the mutation's
latency cost is capped and the event is actually delivered. Detached tasks are banned by name.

### S-5 — MEDIUM — Nothing owns validating that `companion_set_active_deck`'s deck exists

**The divergence.** The MCP tool has DB access; so does the backend. Builder A validates in the
tool; Builder B validates in the backend; jointly they might validate nowhere, because each
assumes the other did. The UI then holds an active deck ID whose every refetch 404s, landing the
user in a no-active-deck state with no explanation — and the agent was told it succeeded.

**Fix applied.** AD-16 assigns it: the **MCP tool** validates and reports `deck_not_found` to the
agent; the backend stores whatever it is given. AD-7's "no DB read on the push path" does not
apply — `set_active_deck` is control, not a push.

### S-6 — MEDIUM — WS upgrade validates `Host` but not `Origin`

NFR-01's threat model is a malicious local webpage. `Host` validation blocks DNS rebinding;
`Origin` is the header that identifies the *calling page*. **Fix applied** — AD-5 now requires
both on the upgrade.

### S-7 — LOW — Envelope `id` ordering semantics unstated

FR-18 history ordering: a builder assuming ULID-style lexicographic time-ordering gets a wrong
order under UUID4. **Fix applied** — history orders by `ts`; `id` is opaque and used only for
identity and dedupe.

## Pairs checked and found genuinely closed

- Two agent sessions pushing concurrently — EXPERIENCE.md's same-kind-replaces / different-kind-
  switches ruling covers it; backend holds no per-session state.
- SPA client-side routing vs static serving — the UX is one screen with overlays; no history
  routing exists to conflict.
- Cross-tab divergence — explicitly accepted in Deferred, not left silent.
- Active deck surviving a backend restart — FR-07 and AD-15 agree it does not.

## Verdict

Seven holes, all closed in-place. The spine now survives the two-independent-builders test on
every seam examined.
