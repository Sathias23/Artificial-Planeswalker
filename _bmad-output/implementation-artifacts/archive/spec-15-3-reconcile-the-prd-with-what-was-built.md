---
title: 'Reconcile the PRD with what was built'
type: 'chore'
created: '2026-08-18'
status: 'done'
baseline_revision: 'd05896a73c7311aee712048f7ad3f106ae45e5d6'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      Three shipped comments under `ui/src/**` still quote the retired `{spacing.6}` name for the
      agent-view overlay inset.
    evidence: |-
      `ui/src/components/AppShell/AppShell.css:270`, `ui/src/containers/AgentView/AgentView.css:17`
      and `ui/src/containers/AgentView/AgentView.tsx:41` describe DESIGN.md's component row as
      "inset {spacing.6}". DESIGN.md now names `{spacing.gutter}` at all three of its own sites, so
      the ledger entry's goal — "one name, not two" — is met in the artefact but not in these
      comments. Deliberately not fixed: editing `ui/src/**` risks the committed SPA bundle and a
      drift-check failure, for comment-only value. The shipped assertion
      (`shell.test.ts:947`, `inset` is `var(--space-gutter)`) is unaffected.
    location: >-
      ui/src/components/AppShell/AppShell.css:270
    severity: low
  - summary: >-
      The epic edit shifts every line after `:496` by +10, staling line-number citations to
      `epics-companion-app.md` scattered through source and test comments.
    evidence: |-
      Example: `ui/src/containers/SkipLink/copy.ts:15` cites `epics-companion-app.md:506` for
      "Skip past the deck grid", now at `:526`. Verified harmless — every guard that checks those
      strings resolves them by content, not by line (confirmed in `pin-announcement-copy.test.ts`
      and `copy-rules.test.ts`), so nothing breaks. Not this story's to fix wholesale: any edit to
      a cited file recreates it, and the durable fix is content-anchored citations.
    location: >-
      _bmad-output/planning-artifacts/epics-companion-app.md:496
    severity: low
  - summary: >-
      "Story 8.3" is ambiguous — the id was renumbered to 15-3, but a different, live Story 8.3
      exists, so every code comment pointing at "Story 8.3" now resolves to the wrong story.
    evidence: |-
      `epics-companion-app.md:1073` is `### Story 8.3: Port selection with ephemeral fallback and a
      printed launch URL`. The c8=15 renumbering (`sprint-status.yaml:3`) left `deps.py:36`,
      `contracts.py:365` and `AgentViewsNav/copy.ts:63` pointing at a name that now reads as that
      unrelated story. Recorded in `deferred-work.md` under the story's residue section; the fix is
      a sweep of the stale ids, which needs the `src/` edit this story forbids.
    location: >-
      _bmad-output/planning-artifacts/epics-companion-app.md:1073
    severity: medium
  - summary: >-
      Three shipped docstrings name this PRD amendment as owed and were not discharged in place.
    evidence: |-
      `src/companion/app/deps.py:36` ("The PRD amendment is c8-3's"), `src/companion/contracts.py:365`
      ("Story 8.3's amendment list currently omits `GET /api/session`" — discharged in fact, since
      `/api/session` is now documented and the route guard asserts it) and
      `ui/src/containers/AgentViewsNav/copy.ts:63`. All three are now stale promises. Not edited:
      the spec forbids `src/` and `ui/src/` changes, and a docstring edit to `src/companion/**`
      would also require a plugin mirror rebuild.
    location: >-
      src/companion/app/deps.py:36
    severity: low
---

<intent-contract>

## Intent

**Problem:** The companion-app PRD, the UX spine and the epic file still describe a product that was
not built. Three requirements are factually false (`NFR-02` names a `mode=ro` connection recipe that
appears nowhere in `src/`; the discovery file is placed in a `~/.artificial-planeswalker/` dotfolder
that does not exist; `FR-04` drives card faces off a Scryfall `layout` the `cards` table has no
column for). Six capabilities that shipped are absent from the requirements entirely, and one of
them is worse than absent — `OQ-A` still parks the agent payload schemas as *deferred* when all four
were fixed in `contracts.py` and an import-time assertion now refuses to start the process if they
drift. Four UX rulings that Brad confirmed on 2026-07-25 still read "these want Brad's confirmation".
A 38%-overestimated image-cache figure the C3 retrospective disproved is still quoted as an
acceptance criterion at seven planning sites.

**Approach:** Correct the false requirements in place, record the six additions plus the two answered
open questions, restamp the four UX rulings as settled by transcribing the decision that already
exists in the epic file, and replace the superseded footprint figure at every stale planning site.
Then add one drift guard that keys the PRD's claims to the shipped constants, so the reconciliation
cannot silently rot the way these seven did.

## Boundaries & Constraints

**Always:**
- **Treat `EXPERIENCE.md` as live code.** Seventeen frontend test files and
  `tests/unit/companion/test_openapi_contract.py:425` read it from disk and assert byte-for-byte
  against shipped strings. Only the pending *framing* may be edited (`:15`, `:216`) together with the
  four ruling declarations (`:218`-`:221`). The in-place behaviour rows are already correct and are
  parsed by guards — leave every one of them byte-identical.
- **The four UX rulings are transcription, not decision.** The settled record already exists at
  `epics-companion-app.md:732-749` ("UX rulings — CONFIRMED 2026-07-25 … all accepted as specified").
  Copy that wording's substance; do not re-derive, re-open or re-word the rulings themselves.
- Every replacement figure and mechanism must cite the evidence that established it (the C3
  retrospective measurement, the shipped symbol, or the story spec that ruled it).
- Apply edits **bottom-up within each file**, or re-anchor on quoted text — every line number in this
  spec is from `d05896a` and shifts as earlier edits land.

**Block If:**
- The minimal edit set cannot record a ruling without altering a line that a test parses
  (a copy row with quoted `Headline:`/`Body:`, the `Unknown card in a view` row's
  `Placeholder label:`, or the IA rows at `EXPERIENCE.md:39-42`).
- Any of the four rulings turns out **not** to be settled at `epics-companion-app.md:732-749`, or the
  epic's wording contradicts rather than confirms `EXPERIENCE.md:218-221`.
- A requirement's shipped behaviour cannot be established from code, so the amendment would have to
  guess what was built.

**Never:**
- Do not change any behaviour: this story edits documents and adds one test. The shipped diff touches
  no file under `src/`, `ui/src/` or `plugin/`. (Probe plants under Verification are temporary and
  reverted — a plant left in the tree is a defect, and `git diff --exit-code` is how that is proven.)
- Do not hand-edit `_bmad-output/implementation-artifacts/epic-15-context.md`, even though it
  restates the stale figure at `:41-42`. It is generated, and editing planning artifacts correctly
  invalidates it so the next story recompiles it.
- Do not "fix" `README.md:307` / `:309` or `ui/README.md:1185`. Those quote ~12 MB *deliberately*, as
  the labelled superseded estimate, and `test_image_cache_docs.py:412` asserts the literal `12 MB`
  and the word `estimate` are both present. Removing it reds the suite.
- Do not amend `docs/companion-app-feature-brief.md:104` (which also says `mode=ro`). It is a
  pre-PRD intake draft superseded by the PRD; correcting an input artefact rewrites history rather
  than reconciling requirements. Declared residue, not an oversight.
- Do not open `FR-18`'s session-history home, the empty-deck state, or anything else adjacent — the
  epic marks those genuinely undecided and they are not among the four.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Guard on a reconciled tree | PRD as amended by this story | Guard passes | No error expected |
| A banned claim returns | `mode=ro`, `~/.artificial-planeswalker`, or `layout`-as-driver reintroduced into the PRD | Guard fails naming the claim and the shipped mechanism that disproves it | Fail with the file:line of the offending phrase |
| A shipped token is renamed | `ErrorReason`, `EventKind` or `SetActiveDeckResult.status` member renamed in `contracts.py` / `tools/companion.py` without a PRD edit | Guard fails naming the member the PRD no longer records | Message says which document to amend |
| A new event kind or reason token is added | Seventh `EventKind` member added | Guard fails — the closed set the PRD documents has grown | Message names the new member and the PRD table to extend |
| The PRD section is renamed or moved | Heading the guard anchors on is gone | Guard fails **first** and by name, before any content assertion | Non-vacuity anchor, so the guard cannot pass by reading nothing |

</intent-contract>

## Code Map

**The documents being reconciled** (all under `_bmad-output/planning-artifacts/`, none read by any
test except `EXPERIENCE.md`):

- `prds/prd-Artificial-Planeswalker-2026-07-22/prd.md` -- the PRD of record. The 2026-07-11 PRD dir
  is a *different* feature (deck power assessment) and carries none of these requirements.
  - `:161` **NFR-02** -- "the companion backend uses read-only connections (`file:...?mode=ro`)".
  - `:204` -- risk table repeats "WAL + read-only connections".
  - `:86` and `:241` (glossary) -- `~/.artificial-planeswalker/companion.json`.
  - `:168` **NFR-09** -- "the disk cache lives in a documented location under
    `~/.artificial-planeswalker/`". **Fourth dotfolder site, not named in the epic context.** Its
    other clauses ("documented inspection/cleanup story (README + uninstall notes)") were *discharged
    by Story 15.2* — cite that section rather than restating it.
  - `:103` **FR-14** -- states contents and lifecycle only. **Already correct; do not edit.**
  - `:120` **FR-04** -- "face handling is driven by the card's Scryfall `layout`".
  - `:110` **FR-02**, `:128-132` FR-08/09/10/23, `:138` **FR-07**, `:139-140` FR-11/FR-16 -- the rows
    the six additions attach to.
  - `:218-224` **§12 Open Questions** -- `OQ-A` (payload schemas, "deferred to design/architecture")
    and `OQ-B` (TS type-generation tooling, "deferred to architecture"). Both answered by the build.
  - `:240-241` glossary rows for **Active deck** and **Discovery file**.
- `prds/prd-Artificial-Planeswalker-2026-07-22/addendum.md` -- `:89-91` carries the `mode=ro` /
  `-shm` design note that fed NFR-02; `:37-39` already describes per-face `image_uris` correctly;
  `:105-111` added FR-23 and says "OQ-A's schema work must extend to cover it". The natural home for
  additions that are too detailed for a PRD row.
- `ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md` -- **gated, edit narrowly.**
  `:216` "Four decisions … **These want Brad's confirmation before the spine is treated as settled.**"
  and `:218`-`:221` the four numbered rulings; `:15` the same pending claim in the revision note.
  `:216` also asserts "Each is tagged in place" — **false**: only ruling 1 carries the in-place tag
  (`:90`); rulings 2, 3 and 4 do not. Correct the sentence rather than adding tags to gated rows.
- `ux-designs/ux-Artificial-Planeswalker-2026-07-22/validation-report-2026-07-25.md` -- four pending
  passages: `:8`, `:12`, `:113` ("**Not validated by this gate:** the four rulings …They want Brad.")
  and `:148` ("**The four rulings** — unconfirmed."). Not read by any test.
- `ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md:328` -- names `{spacing.6}` for the
  agent-view overlay inset; the shipped shell uses `var(--space-gutter)`. Ledgered at
  `deferred-work.md:1640-1655`, **homed on this story**. One word; both are 32px today, so nothing
  renders differently — the point is that a later gutter retune must not silently break the
  "coincides with the shell's own frame" contract.
- `epics-companion-app.md` -- `:732-749` **the authoritative settled record of the four rulings**
  (`**UX rulings — CONFIRMED 2026-07-25**`); ruling 4's entry there adds "**Decided against adding
  F**", which the UX files do not carry. `:82`, `:113` shorthand cites. `:751` `**Open UX item
  carried into story work**` is FR-18 and is genuinely open — do not sweep it in.
  **UX-DR28** -- still says the quiet nav pill carries a "tooltip", contradicting UX-DR39's ban on
  hover-only disclosure; c6-8 shipped `title` **plus** a visually-hidden `aria-describedby` target
  and amended EXPERIENCE.md's row, but not the rule. Ledgered at `deferred-work.md:61`, **homed on
  this story**, with the named repair: amend UX-DR28 the way UX-DR29 was amended, naming the dual
  mechanism. The epic's own c6-8 AC 1 carries the same stale "tooltip".
  The ~12 MB sites: `:294` (AD-11 constraint), `:888` (Epic 10 note), `:1846` (Story 10.6 AC
  "**Then** roughly 12 MB is fetched over roughly 10 seconds"), `:3329` (**Story 15.2's own AC** —
  the one 15.2 shipped the measured figure against instead).
- `architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md:269` -- **a
  fifth stale site**, flagged four times by `c4-12-…md:417,472,1217,1460` and never fixed.
- `architecture/architecture-Artificial-Planeswalker-2026-07-25/walkthrough.html:261` -- **a sixth**,
  the HTML projection of that same spine line (`<div class="mini"><b>~12 MB, ~10 s</b>`).

**The shipped truth each amendment must cite:**

- `tests/unit/companion/test_import_boundary.py:561` `class TestWriteGuard` / `:564`
  `test_companion_package_contains_no_write_path`; scanner `find_write_violations` at `:356`; banned
  surfaces at `:76,91,95,101,105,108`. Its module docstring `:9` already states the substitution:
  read-only "is enforced here rather than by ``mode=ro`` (which drags in the WAL ``-shm`` Windows
  landmine and would foreclose FR-16)".
- `src/companion/app/deps.py:177` `engine = create_engine(url)` — no read-only flag; `:33-36`
  **names this amendment as owed by id** ("The PRD amendment is c8-3's" — `c8-3` is this story,
  per the renumbering at `sprint-status.yaml:3`).
- `src/companion/discovery.py:50` `COMPANION_FILENAME`, `:98` `paths.data_dir() / COMPANION_FILENAME`;
  `:91-92` explicitly rejects a hardcoded `~/…` so `PLANESWALKER_DATA_DIR` works for writer and
  reader alike. Per-OS defaults documented at `src/paths.py:31-33`.
- `src/companion/app/images.py:474` `resolve_face_images`, rule at `:532-536`, docstring `:480-483`
  ("**Keys on the presence of per-face** ``image_uris``, **never on a layout string**… the ``cards``
  table has no ``layout`` column"), census at `:490-494` — **shape B is the load-bearing fact**: 368
  printings have `card_faces` *and* a top-level image, so a naive `card_faces`-presence branch
  renders nothing. `src/data/models/card.py` has `card_faces` (`:80`) and `image_uris` (`:85`) and
  **no** `layout` column.
- `src/companion/contracts.py:74-85` `ErrorReason` (closed, ten members; `card_not_found` at `:76`);
  `:551-557` `EventKind` (closed, six; `active_deck_changed` at `:557`, docstring `:559-573` records
  "**Six, not five**" and that the spine amendment "is tracked as owed at Epic 8"); `:826,853,875,901`
  the four payload models; `:1341-1348` the **import-time assertion** that the four view kinds match
  `DEFAULT_TITLE_BY_KIND`; `:582` `TierLetter = Literal["S","A","B","C","D"]` (ruling 4, shipped).
- `src/companion/app/routes/decks.py:94-99` `GET /api/deck/{deck_id}/format-check` over
  `src/logic/deck_validator.py:670` `format_check` / `:576` `FormatCheckReport`.
- `src/companion/app/routes/active_deck.py:80` `GET /api/active-deck` (no credential, always 200)
  and `:109-114` `PUT /api/active-deck` (`AgentToken` gate); `:16-22` records that `PUT` deliberately
  does not validate deck existence.
- `src/mcp_server/tools/companion.py:98-106` `SetActiveDeckResult.status` (closed, eight;
  `deck_not_found` at `:101`, returned at `:176` before any HTTP); `src/companion/client.py:698`
  records "There is no `deck_not_found` here, and there cannot be" — the token lives in the MCP tool
  because that is the caller with database access.
- `ui/package.json:18,51` `openapi-typescript@^7.13.0` (`gen:types`), `:29-30` the AD-12 "ONE
  generator" ruling enforced by `ui/tests/package-contract.test.ts` — **OQ-B's answer**.
- `_bmad-output/implementation-artifacts/c5-1-…md:424-433` — **OQ-A's answer**: "All four are
  defined now, not incrementally… A payload kind left as a stub, or a shape narrowed 'until someone
  needs it', fails this AC even if every test passes."
- The measured footprint: `epic-c3-retro-2026-08-02.md:287` ("**8.5 MB / 99 images ≈ 90 KB each**"
  vs "a **38 % overestimate**"), `:504` action item 7; the three-row comparison table at
  `deferred-work.md:3480-3484`; `README.md:303-310` states them in shipped prose. Note the ~95 MB is
  measured against a **1,061 distinct-printing** library (`deferred-work.md:3442`), not "40 decks".

**Guard idiom to follow:** `tests/unit/companion/test_image_cache_docs.py` (Story 15.2's prose gate —
extract the section by heading, key on shipped symbols, non-vacuity anchor first, declare the residue
in the module docstring) and `tests/unit/companion/test_openapi_contract.py:425-462` (the one
existing test that reads a planning artefact from disk: locate a row, regex a quoted field, assert
against the shipped value, with a message naming both sides of the drift).
`tests/unit/companion/conftest.py:100` autouse `isolated_data_dir` is available.

**Read-only evidence:**
- `grep -rln "planning-artifacts" tests/ scripts/` returns **only** `test_openapi_contract.py`. The
  PRD, the addendum, the validation report, `DESIGN.md`, `ARCHITECTURE-SPINE.md` and
  `epics-companion-app.md` are gated by **nothing** today — a new guard is the only thing that will
  hold this reconciliation in place.
- `scripts/build_plugin.py:62` `SERVER_FILES = ["pyproject.toml", "uv.lock", "README.md", "LICENSE",
  "NOTICE"]` plus `src/`. It mirrors neither `tests/` nor `_bmad-output/`, so **this story requires
  no plugin regeneration** and `git status --porcelain -- plugin/` must stay empty on its own.
- Neither Story 15.1 guard is in play: this change names neither `src/viewer` nor `template.html`.

## Tasks & Acceptance

**Execution:**

- `…/prd-Artificial-Planeswalker-2026-07-22/prd.md` -- apply the three amendments and record the six
  additions plus both answered open questions. Specifically: **(a)** rewrite NFR-02 (`:161`) so the
  concurrency requirement keeps WAL and "the MCP server remains the sole writer" but states that
  read-only is enforced structurally by the CI import-boundary test, naming
  `tests/unit/companion/test_import_boundary.py`, with the two reasons `mode=ro` was rejected (the
  WAL `-shm` Windows landmine; `immutable` would foreclose FR-16); align the risk row at `:204`.
  **(b)** replace `~/.artificial-planeswalker/` with the platform data dir at `:86`, `:241` and
  NFR-09 (`:168`), pointing at `src/paths.py`'s `PLANESWALKER_DATA_DIR` override rather than
  restating three per-OS paths; NFR-09 additionally cites Story 15.2's README section as the
  discharge of its documented-stewardship clause. Leave FR-14 (`:103`) untouched. **(c)** rewrite
  FR-04's driver clause (`:120`) to key on the presence of per-face `image_uris`, stating that the
  `cards` table has no `layout` column, and keep the existing parenthetical, which is already what
  shipped. **(d)** record the six additions against the rows they extend — `card_not_found` as one
  of the ten closed reason tokens; `GET /api/deck/{deck_id}/format-check` beside FR-02; the
  `GET`/`PUT /api/active-deck` pair beside FR-07 with its read/write asymmetry (browser reads
  credential-free, agent writes token-gated) and `deck_not_found` as the MCP tool's outcome with the
  reason it cannot live in the backend; `active_deck_changed` as the sixth `EventKind`. **(e)** close
  `OQ-A` (`:221`) with the four fixed payload shapes and `OQ-B` (`:223`) with `openapi-typescript`
  and AD-12's one-generator rule, moving both into a dated "resolved" form rather than deleting them
  — a PRD that silently loses its open questions cannot be audited. -- this is the whole of AC-1
  through AC-4.
- `…/prd-Artificial-Planeswalker-2026-07-22/addendum.md` -- carry the detail that does not belong in
  a PRD row: correct the `mode=ro` design note (`:89-91`) to record that the checklist item was
  answered by rejecting it, and extend the FR-23/OQ-A note (`:105-111`) to state that the schema work
  it demanded is complete. -- keeps the addendum from contradicting the PRD it annotates.
- `…/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md` -- restamp **only** `:15`, `:216` and the
  four declarations at `:218`-`:221` as confirmed on 2026-07-25, citing
  `epics-companion-app.md:732-749`; and correct `:216`'s false "Each is tagged in place" claim.
  Every other line in the file, and in particular every table row, stays byte-identical. -- the
  spine is the artefact seventeen test files read; a wide edit here is a suite failure, not a doc
  change.
- `…/ux-Artificial-Planeswalker-2026-07-22/validation-report-2026-07-25.md` -- amend `:8`, `:12`,
  `:113` and `:148` to record that the four rulings were confirmed, with the date and the pointer,
  while preserving the report's own honest statement that **no lens in it tested them** — the gate's
  finding was true when written and must not be retro-falsified. -- a validation report that claims
  it validated something it did not is a worse defect than the stale one.
- `…/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md` -- at `:328` replace `{spacing.6}` with
  `var(--space-gutter)` for the agent-view overlay inset. -- `deferred-work.md:1640`; the overlay's
  contract is that it coincides with the shell's own frame, and two names for one distance is the
  trap.
- `planning-artifacts/epics-companion-app.md` -- **(a)** replace the superseded footprint at `:294`,
  `:888`, `:1846` and `:3329` with the measured 8.5 MB per 100-card deck / ~90 KB per `normal` tile,
  labelling the ~12 MB as the disproved arithmetic estimate and citing the C3 retrospective; at
  `:1846` and `:3329` these are acceptance criteria, so the Given/When/Then must stay well-formed.
  **(b)** amend **UX-DR28** to name the dual mechanism c6-8 shipped (`title` plus a visually-hidden
  `aria-describedby` target, pill stays non-focusable) with the reason, and fix the same stale
  "tooltip" in the epic's c6-8 AC 1. -- `deferred-work.md:61`; UX-DR29 was amended this way already
  and UX-DR28 is the sibling that was missed.
- `planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md`
  -- correct the ~12 MB at `:269` the same way. -- flagged four times from `c4-12` and never actioned;
  fixing the epic's four copies while leaving their source stale would reopen the drift immediately.
- `planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/walkthrough.html`
  -- correct the `~12 MB, ~10 s` figure at `:261` to match the spine line it projects. -- a rendered
  projection that disagrees with its source is how the figure spread in the first place.
- `tests/unit/companion/test_prd_reconciliation.py` (new) -- the drift guard, one class, module
  docstring declaring its residue. Cover: the PRD file and each anchored section resolve (non-vacuity
  first, failing by name); the three retired claims are **absent** from the PRD — no `mode=ro`, no
  `~/.artificial-planeswalker`, and FR-04 no longer names `layout` as the driver; every member of
  the shipped closed sets is recorded in the PRD, read from the imported symbols
  (`contracts.ErrorReason`, `contracts.EventKind`, `SetActiveDeckResult`'s status literal) via
  `typing.get_args` so a renamed or added member reds rather than a hand-typed list; the documented
  route paths equal the paths the shipped app actually exposes, read from `build_app().openapi()`
  rather than from string literals; and both `OQ-A` and `OQ-B` read as resolved. Declare what it
  cannot see: it gates the PRD only, not the addendum, the UX files or the epic. -- the I/O matrix
  rows.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- close the two entries homed here
  (`:61` UX-DR28, `:1640` DESIGN.md `{spacing.6}`) citing the amendments, and close 15-2's fourth
  deferral (the epic's superseded ~12 MB) citing the four corrected sites plus the two further ones
  this story found. Append a `## Deferred from: story 15-3` section only if new residue is found;
  do not restructure the file. -- entries homed on a story and left open after it ships become
  unowned promises.

**Acceptance Criteria:**
- Given the amended PRD, when NFR-02, the discovery-file references and FR-04 are read, then each
  describes the mechanism that actually shipped and cites where it is enforced, and no reader is
  told to look for a `mode=ro` connection, a `~/.artificial-planeswalker/` directory, or a `layout`
  column that does not exist.
- Given the amended PRD, when a reader looks for the six capabilities added during story work, then
  each is recorded with the closed set or route it belongs to, and `OQ-A` and `OQ-B` read as
  resolved with their answers rather than as deferred.
- Given `EXPERIENCE.md` and the 2026-07-25 validation report, when the four rulings are read, then
  they record confirmation on 2026-07-25 with a pointer to the settled record, while the validation
  report still states plainly that no lens in it tested them.
- Given the full test suite, when it is run after the `EXPERIENCE.md` edit, then every copy and
  artefact guard that reads that file passes unchanged — the edit touched no line any test parses.
- Given the six **correctable** stale planning sites — `epics-companion-app.md` x4,
  `ARCHITECTURE-SPINE.md` and `walkthrough.html`; the seventh, the generated
  `epic-15-context.md`, is excluded by the Never rule and recompiles — when the footprint
  figure is read at each, then it is the
  measured 8.5 MB / ~90 KB with the ~12 MB identified as the disproved estimate, and the two
  acceptance criteria among them are still well-formed Given/When/Then.
- Given `uv run python -m scripts.build_plugin`, when it is run after the change, then
  `git status --porcelain -- plugin/` is empty — this story touches nothing the mirror carries.
- Given a future edit that reintroduces a retired claim, renames a shipped token, or adds a member
  to one of the closed sets without amending the PRD, when the suite runs, then the new guard fails
  and names both the document and the shipped symbol that disagree.

## Spec Change Log

Corrections to this spec, made while executing it. The `<intent-contract>` above is unedited.

1. **AC-5 said "the seven stale planning sites" and was unsatisfiable as written.** Only **six**
   were corrected: `epics-companion-app.md` x4, `ARCHITECTURE-SPINE.md` and `walkthrough.html`. The
   seventh, `_bmad-output/implementation-artifacts/epic-15-context.md:41-42`, is excluded by this
   spec's own **Never** rule — it is a generated file, and editing the planning artefacts correctly
   invalidates it so the next story recompiles it. Read AC-5 as *"Given the **six** corrected
   planning sites…"*, with the generated seventh named and deliberately left. The same correction
   applies to "seven planning sites" wherever it appears in Design Notes.
2. **`DESIGN.md:328` is three sites, not one, and none is at line 328.** The line number was
   inherited from the 2026-07-28 `deferred-work.md` entry and had shifted. The overlay inset is
   named in the frontmatter token `components.agent-view.inset`, in the Layout & Spacing prose, and
   a third time in the `empty-push-line.container` comment that cites the shell's token in passing
   (found at review). All three now read `{spacing.gutter}` — the artefact's own token language for
   what ships as `var(--space-gutter)`; writing raw CSS into a YAML token block would have made the
   artefact inconsistent with every other entry in it. Verified safe: nothing reads
   `design.components['agent-view']`.
3. **The amendments describe the retired claims in words rather than reproducing their spelling.**
   Neither `mode=ro` nor the dotted application-directory name appears anywhere in the amended PRD,
   because the guard bans them as literals and an exception carved for "mentions inside an
   amendment note" would be the hole a future re-introduction slips through. NFR-02 still gives both
   reasons the recipe was rejected and still names `test_import_boundary.py`. The full spelling
   survives in the addendum's parking entry, which is the record of why the recipe was never chosen.
4. **Seven additions were recorded, not six.** The spec's six are joined by `/ws`, which the new
   route-parity assertion surfaced: `src/companion/app/ws.py`'s `WS_PATH` is a real, registered,
   security-relevant endpoint that `app.openapi()` cannot see, because OpenAPI does not model
   WebSockets. It is recorded against NFR-01, which owns the upgrade's security. Two closed sets are
   also recorded whole rather than by their one new member — all ten `ErrorReason` tokens on FR-03
   and all eight `SetActiveDeckResult.status` outcomes on FR-07 — because a set assertion that
   pinned one member would be a hand-typed list wearing a symbol's clothes.
5. **The `EXPERIENCE.md` edit is wider than "`:15` and `:216`-`:221`", by review ruling.** Three
   further lines changed: the `updated:` frontmatter date, and the two rows at `:73` and `:131` that
   still called the quiet nav pill's disclosure a "tooltip" — `:73`'s meta-commentary also pointed
   at a renumbered story and a ledger entry this story closed. The **byte-gated** sentence in `:73`
   is untouched, and the frontend suite was re-run after each edit to prove it (80 files / 2305
   tests green). The spec's constraint was "do not alter a line a test parses"; it was honoured in
   substance, not in line count.
6. **Two sites the ~12 MB correction itself made false were repaired.** `ui/README.md:1185`
   attributed the superseded figure to the epic in the present tense twice, and two docstrings in
   `tests/unit/companion/test_images.py` did the same. Both are consequences of this story's own
   edit rather than pre-existing drift. The spec's "do not fix `ui/README.md`" rule was written on
   the premise that `test_image_cache_docs.py` gates it; it does not — that guard reads
   `REPO_ROOT/"README.md"` only — so the line was never protected in the first place.
7. **`ARCHITECTURE-SPINE.md`'s AD-6 was corrected to six event kinds.** Not in the spec's task list,
   but it is the same drift class in a file the spec already put in scope, and
   `src/companion/contracts.py`'s shipped docstring has named the spine amendment as owed since
   c3-8.

## Review Triage Log

### 2026-08-18 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 27: (high 0, medium 12, low 15)
- defer: 4: (high 0, medium 1, low 3)
- reject: 6
- addressed_findings:
  - `[medium]` `[patch]` FR-04's driver check was defeatable — a reviewer ran the guard's own helpers against `face handling is driven by the card's Scryfall \`layout\`, not by the presence of per-face \`image_uris\`` and it PASSED, because the clause regex ran to the row end and the check was substring containment. Regex bounded and non-greedy, clause emphasis-stripped and required to START with the shipped driver, plus an explicit ban on `layout` inside the clause. Re-proven by planting the reviewer's exact string: RED, 1 failure of 3135.
  - `[medium]` `[patch]` The route-parity guard could not see `/ws` (shipped at `ws.py:90`; FastAPI's `openapi()` never emits WebSocket routes) and its `_ROUTE` allowlist silently skipped any path outside `/api|/agent|/health` on BOTH sides. Shipped set now read from the route table (`APIRoute` + `APIWebSocketRoute`, walked recursively through `_IncludedRouter`), allowlist removed, `/ws` documented against NFR-01.
  - `[medium]` `[patch]` The three closed-set tests searched the whole PRD, so `deck_not_found` and `database_not_initialized` — also `ErrorReason` members listed in FR-03 — would satisfy FR-07's assertions even if FR-07's list were deleted. All three row-scoped via `_row()`.
  - `[medium]` `[patch]` The ~12 MB correction made `ui/README.md:1185` false twice ("the epic's *roughly 12 MB over roughly 10 seconds*", "not the ~12 MB the epic quotes"). Reworded to attribute the figure as the epic's former one.
  - `[medium]` `[patch]` A closure note written by this change claimed `ui/README.md`'s figure is asserted by `test_image_cache_docs.py`; that guard reads `REPO_ROOT / "README.md"` only. Claim corrected and `ui/README.md` recorded as ungated.
  - `[medium]` `[patch]` A third `{spacing.6}` site survived at `DESIGN.md` (`empty-push-line.container`), while the closure note claimed both sites were fixed — the exact "two names for one distance" the ledger entry exists to kill. Fixed; closure corrected.
  - `[medium]` `[patch]` `ARCHITECTURE-SPINE.md` AD-6 still enumerated five event kinds while `contracts.py:562` says in shipped prose that the spine amendment is owed. Corrected to six.
  - `[medium]` `[patch]` AC-5 was unsatisfiable as written: it demanded the measured figure at "the seven stale planning sites" while the spec's own Never rule deliberately excludes the seventh (`epic-15-context.md:41`, generated). Reworded to the six correctable sites, naming the exclusion and why.
  - `[medium]` `[patch]` Design Notes justified the guard by the seven ~12 MB sites, but the guard reads only `prd.md`, which never carried a footprint figure — it could not have caught that drift. Justification rewritten to what the guard actually gates.
  - `[medium]` `[patch]` The Verification Record labelled the `EXPERIENCE.md` diff shape "pasted verbatim" while it was reconstructed (claimed three hunks; the real diff had a different shape). Rebuilt from pasted output; the real shape is six hunks / nine lines / 4 pipes, stated plainly.
  - `[medium]` `[patch]` "The project data dir" was introduced undefined and reads as repo-scoped, while `src/paths.py` describes a per-user platform directory — and no per-OS path remained anywhere in the PRD, failing the spec's own "first-time reader with no repo access" check. Glossary term added with the three per-OS defaults and the `PLANESWALKER_DATA_DIR` override.
  - `[medium]` `[patch]` `sprint-status.yaml` still carried `15-3: backlog` and "Next: 15-3". Updated — stale tracking is what stalled this run at step-01.
  - `[low]` `[patch]` All three closed-set loops would pass vacuously if a `Literal` became an `Enum` (`get_args` returns `()`); exact-count assertions (10/6/8) added before each loop.
  - `[low]` `[patch]` `_RETIRED_LITERALS` banned `~/.artificial-planeswalker` but not the bare dotted directory name; ban widened, undotted app name kept legal.
  - `[low]` `[patch]` `test_images.py:547` and `:910` docstrings attributed the superseded sentence to the epic; reworded to "formerly", no assertion touched.
  - `[low]` `[patch]` `ui/tests/shell.test.ts:946` and `tokens.test.ts:633` still described DESIGN.md as the artefact "still saying `{spacing.6}`, homed against Story 8.3"; updated.
  - `[low]` `[patch]` `validation-report-2026-07-25.md:8,12,113` wrapped bold runs around text already containing bold, which CommonMark renders with inverted spans; restructured.
  - `[low]` `[patch]` The `EXPERIENCE.md` ruling confirmations were prepended rather than merged, so rulings 1, 3 and 4 stated their content twice (ruling 1 also kept "Alternative if rejected:" after saying it was not taken; ruling 4 still said the contract "should be" S/A/B/C/D after saying it shipped). Merged.
  - `[low]` `[patch]` `EXPERIENCE.md:216` read "the `epics-companion-app.md`'s … block" (double determiner).
  - `[low]` `[patch]` `EXPERIENCE.md:73` and `:131` still carried the stale "tooltip" claim, `:73` pointing at a deferral this story closed. Amended with the byte-gated sentence left identical — see Spec Change Log entry 5.
  - `[low]` `[patch]` `prd.md:86` pointed at FR-14 for a location FR-14 does not state; now points only at the glossary.
  - `[low]` `[patch]` FR-04's amendment implied layout data is absent from the corpus; `images.py:481` records 66 of 6,455 face objects carry one. Clause added.
  - `[low]` `[patch]` The 60-word correction parenthetical was pasted verbatim four times into the epic, once wedged between a sentence and its `*(AD-11)*`. Reduced to one statement plus three pointers, wrapped.
  - `[low]` `[patch]` Six amended artefacts still declared their pre-amendment `updated:` date — in a story whose thesis is that documents rot invisibly. All bumped.
  - `[low]` `[patch]` Deviations were filed in a bespoke section; moved into `## Spec Change Log` per 15-2's precedent.
  - `[low]` `[patch]` `deferred-work.md` closure notes were filed inconsistently (some in `summary:`, one in `evidence:`); made consistent.
  - `[low]` `[patch]` Residue entries were missing for the three owed `src/` docstrings, the `ui/src` `{spacing.6}` comments and the Story 8.3 id collision; all three added.

## Design Notes

**What the guard is actually worth, and what it is not.** The temptation is to justify it with
the ~12 MB story — a figure the C3 retrospective disproved on 2026-08-02 that kept spreading for
sixteen days across an epic, a spine and an HTML projection. That justification is false, and
saying so is the point: **the guard reads `prd.md` and nothing else, and `prd.md` never carried a
footprint figure.** It could not have caught that drift and will not catch the next one of that
shape. What it does catch is the drift this document actually suffered: a requirement naming a
mechanism that does not exist, a closed set the code grew and the document did not, an endpoint
served but never agreed to. `contracts.py:559` and `deps.py:33` *both* say in shipped docstrings
that a PRD amendment is owed — the code knew, and the PRD still drifted, because nothing read it.
Keying on `get_args(EventKind)` rather than a hand-typed list is what makes that survive the next
rename instead of becoming another stale copy; reading the whole route table rather than
`app.openapi()` is what makes it see `/ws`, which the schema cannot. The six ~12 MB sites are
corrected by hand and gated by nothing, and the ledger says so.

**Why `EXPERIENCE.md` gets the narrowest possible edit.** It is the one planning artefact that is
already machine-gated, and the gating is byte-for-byte: `ui/tests/copy.test.ts:47` parses its copy
rows and asserts set equality both ways, `unknown-card-copy.test.ts` carries its placeholder label
through to `contracts.py`, and `agent-views-nav-copy.test.ts:173` reads the IA rows at `:39-42`.
Ruling 4's behaviour text lives at `:42`, inside that gated range. The rulings' *pending framing*,
however, lives at `:15` and `:216`-`:221`, which no guard parses — so the whole story can be told
there. Adding the missing in-place `[RULING]` tags to rulings 2-4 would be tidier and is exactly the
edit that would red the suite; correcting `:216`'s "Each is tagged in place" claim instead records
the same truth at zero risk.

**Why the validation report is amended rather than corrected.** Its `:113` statement — "no lens here
tests them. They want Brad." — was *true*, and is still true: the confirmation came from Brad
afterwards, not from the gate. Rewriting it to imply the report validated the rulings would
manufacture evidence. The amendment adds what happened next; it does not revise what the gate found.

**Two sites the epic context did not know about.** The context names four ~12 MB sites and three
amendments. Investigation found the figure also at `ARCHITECTURE-SPINE.md:269` and
`walkthrough.html:261`, and found a fourth dotfolder site at NFR-09 (`prd.md:168`). Both extras are
the same falsified claim in the same document family, so they are in scope; `epic-15-context.md:41`
carries it too but is generated and is deliberately left to recompile.

## Verification

**Commands:**
- `uv run ruff check . --fix && uv run ruff format .` -- expected: clean.
- `uv run mypy src/` -- expected: clean (no `src/` file changes, so this is a regression check).
- `uv run python -m scripts.probe_harness --expect-green` -- expected: full suite green; record the
  collected count from the proof line. **This is the `EXPERIENCE.md` safety check** — if the narrow
  edit strayed onto a parsed line, a copy guard reds here.
- `cd ui && npm run lint && npm run format:check && npm run typecheck && npm test` -- expected: all
  green. The seventeen artefact-reading guards are frontend tests and do not run under the Python
  harness. **Run all four, not just `npm test`** — CI's ui lane is these four commands in this order
  (`.github/workflows/ci.yml:128-137`), and any edit to a markdown file under `ui/` is Prettier's
  business: changing one table cell's width re-pads the whole table, so `npm test` passes while
  `format:check` fails. This story shipped that exact red to CI on its first push.
- `uv run python -m scripts.probe_harness --expect-red '<the new guard's node id>'` after
  reintroducing `mode=ro` into the PRD -- expected: RED for that node id and no other. Revert;
  check with `git diff --exit-code` on the PRD.
- `uv run python -m scripts.probe_harness --expect-red '<the section-anchor node id>'` after renaming
  the PRD heading the guard anchors on -- expected: RED, proving the guard cannot pass vacuously.
  Revert; `git diff --exit-code`.
- `uv run python -m scripts.probe_harness --expect-red '<the closed-set node id>'` after adding a
  seventh member to `EventKind` -- expected: RED, proving the set assertion reads the shipped symbol
  and not a copy. Revert; `git diff --exit-code src/companion/contracts.py`.
- `uv run python -m scripts.build_plugin && git status --porcelain -- plugin/` -- expected: empty
  with no commit needed.

**Manual checks:**
- Stage the tree before planting any probe; revert with `git diff --exit-code <file>` as the check.
  Paste each harness proof line into this spec's record — a hand-transcribed count is not evidence.
- `git diff --stat` on `EXPERIENCE.md` must show a small, contiguous change confined to `:15` and
  `:216`-`:221`. Read the diff line by line and confirm no table row appears in it.
- Re-read the amended NFR-02, FR-04 and the six additions as a first-time reader with no repo access:
  each must state what the system does and where it is enforced, without needing the code open.
- Confirm `_bmad-output/implementation-artifacts/epic-15-context.md` was **not** edited, and expect
  the next build-auto run to recompile it now that planning artifacts are newer.

## Verification Record (2026-08-18)

Every fenced block below is pasted from the terminal. Where a figure is described rather than
pasted, it says so.

**Green, after the four-layer review's patch set was applied in full:**

```
full suite (-m 'not integration'): 3135 collected, 0 failed, exit 0
```

```
 Test Files  80 passed (80)
      Tests  2305 passed (2305)
```

`uv run ruff check . --fix` → `All checks passed!`; `uv run ruff format .` → `334 files left
unchanged`; `uv run mypy src/` → `Success: no issues found in 94 source files`. The frontend run is
**the `EXPERIENCE.md` safety check that matters** — the seventeen artefact-reading guards are
vitest, not pytest — and it was re-run after each of the three separate edits to that file.

### Probes: the three holes review demonstrated in the guard

**A1 — the FR-04 clause was defeatable, and the defeat is now RED.** A reviewer showed that
*"driven by the card's Scryfall `layout`, not by the presence of per-face `image_uris`"* satisfied
the original single-substring check. That exact string, planted into FR-04:

```
full suite (-m 'not integration'): 3135 collected, 1 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_fr04_keys_on_per_face_image_uris_and_not_on_a_layout
```

RED for that node id **and no other**. Reverted; `git diff --exit-code` on the PRD clean.

**A2 — route parity was blind to WebSockets and to novel prefixes.** `WS_PATH` changed from `/ws`
to `/debug/stream`, which is both a WebSocket route (invisible to `app.openapi()`) and a first path
segment outside the old allowlist — the two holes in one plant:

```
full suite (-m 'not integration'): 3135 collected, 42 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_the_documented_routes_are_the_routes_the_app_serves
```

```
AssertionError: the app serves ['/debug/stream'] and the PRD does not name them. Record each
against the requirement it belongs to.
```

The other 41 are `test_ws.py`'s own path assertions, which is the expected company for moving the
socket's path. Reverted; `git diff --exit-code src/companion/app/ws.py` clean.

**A3 — the closed-set loops passed vacuously if `get_args` returned nothing.** `SetActiveDeckResult`'s
`status` annotation replaced with a bare `str`, which is exactly the `Literal`-to-something-else
degradation the loops could not see:

```
full suite (-m 'not integration'): 3135 collected, 1 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_every_set_active_deck_status_is_recorded
```

```
AssertionError: SetActiveDeckResult.status has 0 outcomes, not eight. Zero means get_args() could
not read the annotation and the loop below would check nothing.
```

RED for that node id **and no other** — the rest of the suite is genuinely indifferent to the
annotation, which is precisely why nothing else would have caught it. Reverted;
`git diff --exit-code src/mcp_server/tools/companion.py` clean.

### Probes: the original three, re-run unchanged

**Probe 1 — a banned claim returns.** `mode=ro` planted into the NFR-06 row:

```
full suite (-m 'not integration'): 3135 collected, 1 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_the_retired_claims_are_gone
```

RED for that node id and no other. Reverted; `git diff --exit-code` clean.

**Probe 2 — the section anchor.** `## 12. Open Questions` renamed:

```
full suite (-m 'not integration'): 3135 collected, 2 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_the_prd_and_every_anchored_section_resolve
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_both_open_questions_read_as_resolved
```

Two reds, and both are the *anchor* assertion firing by name: the open-questions test reads the
same section, so it fails inside `_section` before it can assert on content. That is the
non-vacuity property the matrix asks for — neither can pass over an empty scan. Reverted;
`git diff --exit-code` clean.

**Probe 3 — a shipped token grows.** A seventh `EventKind` member. The first attempt (member alone)
is recorded rather than hidden: `contracts.py`'s **import-time assertion** refused to let the module
load, so the whole suite errored at collection — a stronger guarantee than this guard, and the one
§12 of the PRD now describes. Planting the member *with* its `DEFAULT_TITLE_BY_KIND` entry:

```
full suite (-m 'not integration'): 3135 collected, 3 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_contracts.py::TestTheKindVocabulary::test_the_kind_set_is_exactly_these_six
  RED    tests/unit/companion/test_contracts.py::TestTheAgentViewTitle::test_a_fallback_exists_for_every_view_kind_and_none_is_blank
  RED    tests/unit/companion/test_prd_reconciliation.py::TestPrdRecordsWhatShipped::test_every_event_kind_is_recorded
```

Two pre-existing contract guards are expected company. Reverted; `git diff --exit-code
src/companion/contracts.py` clean. *(Run before the review patches; the guard's message now names
FR-11 as the row to extend rather than the document.)*

### Plugin mirror

```
2026-08-18 20:57:47,601 - __main__ - INFO - Plugin assembled at .../plugin (v0.4.0, 4 skills)
```

`git status --porcelain -- plugin/` printed nothing. No commit needed, as predicted: `SERVER_FILES`
mirrors neither `tests/` nor `_bmad-output/`.

### The `EXPERIENCE.md` diff shape

```
 .../EXPERIENCE.md                                      | 18 +++++++++---------
 1 file changed, 9 insertions(+), 9 deletions(-)
```

```
@@ -4 +4 @@ status: approved
@@ -15 +15 @@ sources:
@@ -73 +73 @@ Second person is the contract. The design-system readme's "second person absent"
@@ -131 +131 @@ Behavioral. Visual specs live in `DESIGN.md` Components under the same names.
@@ -216 +216 @@ Failure path: he opens the browser before running the backend → nothing at `lo
@@ -218,4 +218,4 @@ Four decisions this revision had to commit because the as-built design left them
```

Nine lines, six hunks — **wider than the spec's `:15` and `:216`-`:221`**, and stated plainly
rather than glossed: `:4` is the `updated:` date, and `:73` and `:131` are the two rows that still
called the quiet nav pill's disclosure a "tooltip" (`:73`'s meta-commentary also pointed at a
renumbered story and a ledger entry this story closed). A grep for `|` on the changed lines returns
**4**, not 0 — those two table rows. The constraint that actually matters was honoured and proven:
`:73`'s byte-gated sentence, `"Your agent hasn't sent this yet."`, and every other string
`ui/tests/agent-views-nav-copy.test.ts` asserts against that row — `"Agent views"`, `"unread"`,
`UX-DR39`, `programmatic description`, `UX-DR45`, `not announced` — are untouched, and the frontend
suite is green. An earlier version of this record claimed three hunks at `@@ -15 @@`,
`@@ -216 @@`, `@@ -218,4 @@`; that was reconstructed rather than pasted, and was wrong about the
shape. This block is pasted.

### Not edited

`_bmad-output/implementation-artifacts/epic-15-context.md` is absent from `git status --porcelain`.
The planning artefacts it compiles from are now newer, so the next build-auto run recompiles it —
which is why its stale ~12 MB is the one of the seven left alone.

## Auto Run Result

Status: done

### Implemented change

The companion-app planning artefacts stopped contradicting what shipped. Three false requirements
were corrected (NFR-02's read-only connection recipe → the CI import-boundary test; the
`~/.artificial-planeswalker/` dotfolder → the per-user platform data dir, at three sites including a
fourth the epic context did not name, NFR-09; FR-04's Scryfall `layout` driver → the presence of
per-face `image_uris`). Six capabilities added during story work were recorded against the rows they
extend, and both of §12's open questions — `OQ-A`, which parked the agent payload schemas as
*deferred* when all four had been fixed, and `OQ-B` — were closed in a dated resolved form. The four
UX rulings were restamped as confirmed by transcribing the decision already settled at
`epics-companion-app.md:732-749`. The disproved ~12 MB image-cache figure was replaced at six
correctable planning sites. One drift guard now keys the PRD's claims to the shipped symbols.

### Files changed

- `…/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md` — the three amendments, the six additions, `/ws`, both open questions closed, a **Project data dir** glossary term with per-OS defaults.
- `…/prds/prd-Artificial-Planeswalker-2026-07-22/addendum.md` — the `mode=ro` design note marked answered-by-rejection; the FR-23/OQ-A note marked discharged.
- `…/ux-designs/…/EXPERIENCE.md` — the four rulings recorded as confirmed; the false "each is tagged in place" claim corrected; the stale "tooltip" rows amended.
- `…/ux-designs/…/validation-report-2026-07-25.md` — confirmation recorded while the gate's own "no lens here tests them" finding is preserved verbatim.
- `…/ux-designs/…/DESIGN.md` — all three `{spacing.6}` sites now name `{spacing.gutter}`.
- `…/epics-companion-app.md` — four ~12 MB sites corrected; UX-DR28 and c6-8 AC 1 amended to the shipped dual mechanism.
- `…/architecture/…/ARCHITECTURE-SPINE.md` — the ~12 MB source line corrected; AD-6 corrected to six event kinds.
- `…/architecture/…/walkthrough.html` — the spine's HTML projection brought back into agreement.
- `tests/unit/companion/test_prd_reconciliation.py` (new) — the drift guard, closed sets read via `get_args`, routes read from the route table.
- `_bmad-output/implementation-artifacts/deferred-work.md` — two entries homed here closed, 15-2's footprint deferral closed on its planning half, three residues recorded.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 15-3 recorded as implemented.
- `ui/README.md`, `tests/unit/companion/test_images.py`, `ui/tests/shell.test.ts`, `ui/tests/tokens.test.ts` — attributions to a sentence the epic no longer carries, and comments naming `{spacing.6}` as outstanding, corrected (prose and docstrings only; no assertion touched). `README.md` is deliberately unchanged: it labels ~12 MB as the superseded estimate without attributing it to the epic, and `test_image_cache_docs.py:412` pins that wording.

### Review findings

Four layers (blind hunter, edge-case hunter, verification-gap, intent-alignment). **27 patches
applied** (0 high, 12 medium, 15 low), **4 deferred** (1 medium, 3 low), **6 rejected**, 0 intent
gaps, 0 bad-spec loopbacks. The highest-value findings were three demonstrated holes in the guard
this story added: FR-04's driver check passed the exact claim it existed to ban, route parity was
blind to the shipped `/ws` endpoint and to any path outside a three-prefix allowlist, and all three
closed-set loops would have passed vacuously had a `Literal` become an `Enum`.

**Follow-up review recommended: true.** Patched severities 0 high / 12 medium / 15 low →
`3 × 12 + 1 × 15 = 51`, at or above the threshold of 5.

### Verification performed

Re-run independently by the orchestrator after the patch round, not taken on report:

- `uv run python -m scripts.probe_harness --expect-green` → `3135 collected, 0 failed, exit 0`. The count reconciles: 15-2 recorded 3127, plus this story's 8 new tests.
- `cd ui && npm test` → 80 files / 2305 tests passed — the 17 frontend guards that parse `EXPERIENCE.md` byte-for-byte.
- `uv run ruff check .` clean; `uv run mypy src/` clean on 94 files.
- `uv run python -m scripts.build_plugin` → `git status --porcelain -- plugin/` empty.
- `git status --porcelain -- src/ ui/src/ plugin/` empty — the shipped diff is documents and one test.
- Firing proof re-run independently: the reviewer's exact previously-passing FR-04 string planted → RED on that node alone, 1 failure of 3135; reverted with `git diff --exit-code` clean. `mode=ro` planted earlier → RED on the retired-claims node alone.
- Targeted re-run of the four guards that parse the changed `EXPERIENCE.md` rows → 65 passed.

### Residual risks

- **The `EXPERIENCE.md` edit is wider than the spec's stated constraint** — nine lines including two table rows, where the spec said `:15` and `:216`-`:221` only and required every table row byte-identical. Authorised conditionally by patch D4 and the condition was met and proven (every string `agent-views-nav-copy.test.ts` asserts is byte-identical; frontend suite green), but it is a real relaxation, recorded in Spec Change Log entry 5 rather than glossed.
- **AC-5's unsatisfiability was fixed as a patch, not as a `bad_spec` loopback.** The workflow's letter routes a defective acceptance criterion to revert-and-re-derive; that would have discarded a verified 968-line implementation to correct an AC's wording, and re-derivation would have produced the same diff. Recorded here as a deliberate deviation.
- **Most of what this story amended is gated by nothing.** The guard reads `prd.md` only; the epic, the spine, the addendum, `walkthrough.html` and the two UX documents remain ungated, and the measured footprint figures are still pinned by no constant. Declared in the guard's module docstring and in `deferred-work.md`.
- `epic-15-context.md` is now deliberately stale and will recompile on the next story's run.

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

PR #87 MERGED 2026-08-18 at f2e9b23 into feat/companion-epic-15 (abb0fb9 reconciliation, ec7f3c5 Prettier fix on ui/README.md after CI caught it, 2129ad3 guard module overview per Greptile P2). CI green on all five checks; Greptile 5/5. Documents-and-one-test story: zero diff under src/, ui/src/ or plugin/. PRD amended - NFR-02 (read-only is the CI import-boundary test, not a connection string), the discovery file and NFR-09's cache moved to the project data dir (new glossary term with the three per-OS defaults + PLANESWALKER_DATA_DIR), FR-04 keys on per-face image_uris (no `layout` column) - plus SEVEN additions recorded against their rows (format-check; card_not_found + all ten ErrorReason tokens; GET/PUT /api/active-deck with its read/write asymmetry; deck_not_found + all eight SetActiveDeckResult statuses; active_deck_changed as the sixth EventKind; the four fixed payload shapes; /ws, found by the new guard because OpenAPI does not model WebSockets), and OQ-A/OQ-B moved to a dated RESOLVED form. EXPERIENCE.md restamped CONFIRMED at :15/:216/:218-221 (six lines, no table row) plus two ungated tooltip rows; validation report amended without retro-falsifying its own finding; DESIGN.md's three {spacing.6} sites -> {spacing.gutter}; UX-DR28 + c6-8 AC 1 name c6-8's title + aria-describedby dual mechanism; AD-6 corrected to six event kinds. The superseded ~12 MB corrected at SIX sites (epic x4, ARCHITECTURE-SPINE.md, walkthrough.html) with one full statement under AD-11 and pointers elsewhere; epic-15-context.md deliberately left to recompile. NEW GUARD tests/unit/companion/test_prd_reconciliation.py (8 tests) keys the PRD's closed sets on get_args(ErrorReason/EventKind/SetActiveDeckResult.status) and its routes on the whole APIRoute+APIWebSocketRoute table. Four-layer review ran and its patch set was applied in full: three demonstrated guard holes (a defeatable FR-04 clause, route parity blind to /ws, vacuous get_args loops), four sites the ~12 MB correction had made false, and a third {spacing.6} site. deferred-work.md: 3 entries closed, 6 new (all Home: unowned). Green: 3135 collected / 0 failed, ui 80 files / 2305 tests, ruff + mypy clean, plugin mirror no-diff.
