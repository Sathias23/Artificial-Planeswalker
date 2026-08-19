---
title: 'Release documentation for the companion app'
type: 'chore'
created: '2026-08-19'
status: 'done'
baseline_revision: '2ea1f4af4f8ce9632dd9fed1e25f2d5a9c6ad024'
baseline_commit: '2ea1f4af4f8ce9632dd9fed1e25f2d5a9c6ad024'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The companion app ships — committed bundle, console script, discovery file, single-instance
lock — and the README never says how to start it. `grep -i companion README.md` returns a tool-table row
labelled *(in development)*, the image-cache section Story 15.2 wrote, and the data-dir leftovers list.
There is no launch command anywhere, so Story 15.1's deprecation of `view_deck` currently points a reader
at a replacement they cannot start. The CHANGELOG is worse: `[Unreleased]` carries only 15.1's
`### Deprecated` block, so the entire companion app — two new runtime dependencies included — is unrecorded.

**Approach:** Write the companion's release documentation out of the shipped strings rather than out of the
planning artefacts: one new README section covering what it is, that it is optional, how to launch it, and
how to self-diagnose a port conflict or a fresh install with no card database; a CHANGELOG `[Unreleased]`
entry recording the app, its dependencies with floors, and why TypeScript is capped; and an attribution
correction so the docs claim imagery the app actually caches.

## Boundaries & Constraints

**Always:**
- Every user-facing string in the docs is **quoted from shipped code**, not paraphrased and not taken from
  a planning artefact. The Code Map gives the `file:line` for each. Where the code's own docstring already
  explains a behaviour, that docstring is the source.
- `uv run artificial-planeswalker companion` is the single documented launch command, spelled identically
  everywhere it appears.
- New README prose goes **outside `README.md:242-348`**. That range is `### Image cache (companion app)`,
  gated byte-close by `tests/unit/companion/test_image_cache_docs.py`.
- **After any `README.md` or `NOTICE` edit**, run `uv run python -m scripts.build_plugin` and commit the
  regenerated `plugin/server/**`. The pre-commit hook that would do this is not installed on this machine;
  CI's `quality` job fails on both matrix legs if `plugin/` is dirty.
- The CHANGELOG entry sits under the existing `## [Unreleased]`, with `### Added` and `### Changed`
  **above** the existing `### Deprecated` block, per Keep a Changelog ordering.

**Ask First:**
- Any edit **inside** `README.md:242-348`. Eleven assertions read that section, several by exact literal.
- Any edit to `ui/src/**`, `ui/tests/**` or the committed SPA bundle.
- Any change that would make this story cut a release rather than describe one.

**Never:**
- **Do not bump `pyproject.toml:3`, do not date a release heading, do not add `[0.5.0]` link definitions.**
  Ruled 2026-08-19: Story 15.6 is the SC-5 gate, and dating a release before its gate has run would be a
  claim the repo cannot back. The cut is a separate act after 15.6.
- Do not touch the footer copy (`ui/src/components/Footer/copy.ts`). It is byte-gated against `DESIGN.md`
  by `ui/tests/attribution.test.ts:174-178`, and this story's attribution work is on the docs side only.
- Do not fix the F4 database-lock defect in code. Ruled 2026-08-19: document the recovery, leave the entry
  ledgered.
- Do not edit `EXPERIENCE.md`, `DESIGN.md` or `prd.md`. 15.3 reconciled them and they are now gated.
- Do not repair the stale `DESIGN.md:375` citations in `ui/src/components/Footer/copy.ts:5,16` and
  `Footer.tsx:8` (the line is now `:569`). Comment-only value against a bundle-drift risk — 15.3 declined
  the identical trade and this story follows that precedent.
- Do not invent a number. Every figure is measured and already written down somewhere shipped.

## I/O & Edge-Case Matrix

The reader is the "input" here; the docs are the output. Each row is a situation a first-time user meets
and the behaviour the documentation must let them predict without reading source.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal launch | `uv run artificial-planeswalker companion` on a working install | Docs state one line is printed — `[planeswalker] companion running at http://127.0.0.1:8765 — open this URL in your browser (Ctrl-C to stop)` — and that this is the only launch line, since uvicorn's own banner is suppressed | N/A |
| Preferred port taken | Port 8765 in use | Docs state the app announces the fallback on stdout and keeps running on an ephemeral port; the printed URL is always the real one | Never fatal — any `OSError` on bind triggers fallback, not an exit |
| Second instance, steady state | A verified companion already answering | Docs quote `[planeswalker] companion is already running at http://127.0.0.1:{port} — open that URL, or stop the other instance before starting a new one`, and state the exit status is `0` | Success, not an error |
| Second instance, startup window | Another companion mid-launch, lock refused | Docs quote `[planeswalker] another companion is already starting up — wait for it to print its URL, or stop it before starting a new one`, and explain it names no URL because none can be stated honestly yet | Success, exit `0` |
| Custom port | `COMPANION_PORT` set, or `--port N` | Docs give precedence `--port` → `COMPANION_PORT` → default 8765, and state a value outside `0..65535` is ignored with a warning rather than refused | Non-integer `--port` is a usage error, exit `2`; a bad env value only warns |
| Fresh install, no card database | No `cards.db` in the data dir | Docs state the app **starts anyway**, serves the page, and the panel reads `Card database not set up yet.` and directs the user to ask their agent to run `initialize_database` | The app never crashes on a missing database; readiness is re-probed per request, so it comes alive with no restart |
| Failed first import | A partial, schema-only `cards.db` the running companion has opened | Docs state the recovery: stop the companion with Ctrl-C first, then delete or re-import | Bounded — only wholesale file replacement is blocked, and stopping the app releases it |
| Stop | Ctrl-C | Docs state exit status `0`, `companion.json` removed, `companion.lock` deliberately retained | N/A |
| Unclean exit | Crash or kill | Docs state `companion.json` is left behind stale and the next launch reclaims it | Treated as the expected post-crash state, not an error |

</frozen-after-approval>

## Code Map

**The two files this story writes**

- `README.md` (393 lines) — the target. Heading tree: `## What it does` (19), `## Requirements` (52),
  `## Quick start` (58), `## Connect your client` (84-194), `## Where the data lives` (196),
  `### Image cache (companion app)` (242-348), `## Development` (350), `## License & attribution` (375),
  `## Acknowledgments` (388).
  - `:28` — the `**Companion app** *(in development)*` table row. The label is now false; this story's
    section is what replaces it.
  - `:25` — `view_deck` *(deprecated — use the companion app)*, shipped by 15.1. This is the dead-end
    pointer 15.1 deferred here by name.
  - `:196-209` — the `| OS | Default location |` table the new section links back to via
    `[Where the data lives](#where-the-data-lives)`. README uses in-page anchors freely.
  - `:327-341` — the existing leftovers list (`companion.lock`, `companion.json`), already correct.
  - `:350-373` — `## Development`'s ASCII source tree **omits `src/companion/`, `src/viewer/` and `ui/`**.
  - `:379-386` — the Scryfall paragraph and the Fan Content blockquote.
  - **House style to match:** GFM tables, fences tagged `bash`/`powershell`/`json`/`toml`,
    `<details><summary>` collapsibles for per-client variants, bold run-in lead-ins (`**Layout.**`,
    `**Inspect it.**`), `>` blockquote callouts, absolute GitHub blob URLs for repo files but relative for
    `LICENSE`, wrapping at ~95-100 columns.
- `CHANGELOG.md` (227 lines) — Keep a Changelog 1.1.0 + SemVer, declared at `:1-6`.
  - `:8-22` — `## [Unreleased]`, currently a lone `### Deprecated` block from 15.1.
  - `:24` — `## [0.4.0] - 2026-07-18`, the last release.
  - `:60`, `:212` — **`### Upgrade notes` is an established local convention**, always last in its release.
  - `:223-227` — link definitions at the bottom. **Not touched by this story** (no version cut).
  - Entry style: `- ` bullets, bold lead-in naming the subject with a backticked symbol inside the bold,
    em dash, then 3-12 wrapped lines of narrative prose at ~72 columns. Commands are inline code spans,
    never fenced. Caveats are italicised trailing qualifiers (`*Experimental:* …`, `:39`).

**Launch, port, single instance — the strings to quote**

- `pyproject.toml:49-50` — `[project.scripts]`, `artificial-planeswalker = "src.mcp_server.__main__:main"`.
- `src/mcp_server/__main__.py:44-58` — `_USAGE`, verbatim. `:7-10` the three invocation forms. `:110-123`
  bare invocation runs the MCP server over stdio, deliberately unchanged. `:136-149` — `2` is the **only**
  non-zero status this program mints. `:152-189` `--port` parsing; a non-integer is a usage error, an
  out-of-range integer is not. `:234-241` Ctrl-C returns `0`.
  - ⚠️ `:59-64` — the usage text **deliberately names no port number**, because an AST test allows exactly
    one occurrence of the literal in `src/` + `scripts/`. Quoting it in the README is fine; adding a number
    into code is not.
- `src/companion/app/server.py:52-56` — `HOST = "127.0.0.1"`, `DEFAULT_PORT = 8765` ("the single place in
  `src/` that names the number"). `:58-66` `PORT_ENV_VAR = "COMPANION_PORT"`. `:84-132`
  `resolve_preferred_port` — precedence and the two warning paths. `:167-213` ephemeral fallback on **any**
  `OSError`. `:346-351` the fallback stdout line. `:352-356` the launch line. `:290-296` why the literal
  `127.0.0.1` and not `localhost` (IPv4-only socket; `localhost` resolves to `::1` first on Windows and
  modern Linux). `:5-11` uvicorn's own banner is suppressed, so the printed line is the only one.
  `:272-284` — three outcomes, **all three successes that exit `0`**.
  - `:317-323` and `:329-335` — the **two** "already running" messages. The AC says "the message"; there
    are two, and the difference is the point.
- `src/companion/app/singleton.py:65-66` `LOCK_FILENAME = "companion.lock"`; `:11-21` why it is never
  unlinked (the lock attaches to the inode) — already reflected at `README.md:331-334`.
- `src/companion/discovery.py:50-51` `COMPANION_FILENAME = "companion.json"`; `:1-8` sole rendezvous, no
  env var and no port scan; `:211-267` removed on clean shutdown only, ownership-guarded; `:179-208` a
  stale file reads as *app not running*. `src/companion/app/server.py:254-267` — the next launch reclaims
  it and logs at INFO, because AD-15 treats a stale file as the expected post-crash state.

**Fresh install with no card database**

- `src/companion/app/deps.py:3-12` — the quotable shipped truth: a fresh install ships no card database
  because the Scryfall set is excluded by licence, and AD-10 makes its absence "a served UI state, not a
  startup failure". `:13-20`, `:160-178` — the file check precedes engine creation, so no zero-byte
  `cards.db` is ever planted. `:29-31`, `:279-280` — readiness re-probed per request, never cached, so a
  database built while the backend runs is picked up with no restart.
- `src/companion/app/routes/health.py:10-28` — `GET /health` takes no session and has no failure path.
- `src/companion/contracts.py:77`, `:186` — `database_not_initialized`, "fresh install, no card database
  yet"; `src/companion/app/errors.py:51` maps it to `503`.
- `ui/src/components/StatePanel/copy.ts:97-109` — the panel the user actually reads: headline
  `Card database not set up yet.`, action ``In your agent session, ask it to initialize the database
  (`initialize_database`).``, guidance `First build takes a few minutes — this page will come alive on its
  own when it's ready.`
- `ui/src/state/poller.ts:60-62`, `:100`, `:232` — `database_not_initialized` **never escalates**, at any
  elapsed time, because a first import takes minutes.
- **F4, the recovery to document:** `deferred-work.md:5340-5356`. A failed first import leaves a
  schema-only `cards.db`; the companion's next poll opens it under the lazy engine and from that moment
  the file cannot be deleted or replaced until the app stops. Display is already correct
  (`is_database_initialized` returns `False` for present-but-empty). Documented, not fixed.

**Node is never required at install or runtime**

- `src/companion/app/spa.py:1-7` — the quotable line: the bundle is "generated output, committed to the
  repository… Nothing here builds anything — that is the whole point of AD-13, and it is what makes SC-4
  true rather than aspirational." `:46-51` `STATIC_DIR`.
- `pyproject.toml:24`, `:34` — `fastapi` and `uvicorn[standard]` are in the **base** dependency list, so
  no extra and no group is needed for the companion.
- `pyproject.toml:109-110` — `packages = ["src"]`, so the bundle is packaged with the wheel.
- `.github/workflows/ci.yml:117`, `:147`, `:170-177` — Node is dev/CI-only, and CI fails on bundle drift.
  **The honest caveat the README owes:** Node *is* required to change the UI.

**Dependencies — the diff is `v0.4.0..HEAD`, not `master...HEAD`**

`git diff master...HEAD -- pyproject.toml` is **empty**; this branch touches no dependency file. Everything
the companion added landed on `master` after the `v0.4.0` tag.

- `pyproject.toml:24` `fastapi>=0.139.2` (runtime) · `:34` `uvicorn[standard]>=0.51.0` (runtime) ·
  `:63` `websockets>=12.0` (**dev group only**, rationale inline at `:60-62`: `scripts/cdp_harness.py`
  speaks the WebSocket-only DevTools protocol).
- **Not new — do not list:** `httpx>=0.28.1` (`:26`) predates `v0.3.0`; `starlette` is never declared and
  arrives transitively via FastAPI.
- `pyproject.toml:41-43` — the sole optional group, `observability`, unchanged by the companion.
- `ui/package.json:7` `"node": ">=20.19.0"` · `:55` `typescript: ">=5.9 <6.1"`, reasoned at `:27` ·
  `:45` `eslint: "^9"`, reasoned at `:28` · `:39` `@testing-library/jest-dom: "~6.9.1"`, reasoned at `:31`.

**Attribution**

- `NOTICE:10-13` Scryfall (says **card data** only) · `:23-30` Fan Content, "Not approved or endorsed",
  trademark line. `pyproject.toml:8` `license-files = ["LICENSE", "NOTICE"]`.
- `README.md:379-381` Scryfall paragraph (**card data** only) · `:383-386` the Fan Content blockquote.
- `ui/src/components/Footer/copy.ts:64-73` — the app already says **`Card data and imagery courtesy of
  Scryfall.`** This is the divergence to close: the app caches images (`README.md:242-244`) and the docs
  do not admit it.
- `ui/tests/attribution.test.ts:271-286` — every footer `href` must appear in root `NOTICE` as a bounded
  match. **Both links must survive the NOTICE edit**: `https://scryfall.com/docs/api` and
  `https://company.wizards.com/en/legal/fancontentpolicy`.

**Node-floor copy drift (deferral homed here)**

- `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md:396`
  — stack table row reads `>=20`.
- `_bmad-output/planning-artifacts/epics-companion-app.md:333` — `Node >=20 (dev/CI only).`
- `epics-companion-app.md:1330` is Story c2-1's own shipped AC (`the build succeeds on Node >= 20`).
  **Left alone deliberately** — retroactively editing a done story's AC is a different act from correcting
  a stack table, and CI's `node-version: 20` resolves to the latest 20.x, which satisfies the real floor.

**Read-only evidence — what can and cannot break**

- `grep -rln "README\|CHANGELOG"` over `tests/`, `ui/tests/`, `ui/src/`, `scripts/`: **exactly one test
  reads root `README.md`** (`test_image_cache_docs.py`, section 242-348 only) and **zero tests read
  `CHANGELOG.md`**. `tests/unit/companion/test_prd_reconciliation.py:57-58` states in its own docstring
  that it gates the PRD and only the PRD.
- `test_image_cache_docs.py:480-513` **proves** that edits before the section, and appended sections after
  it, do not move the guard. The new `## The companion app` section is therefore free.
- Prettier's `.` runs under `working-directory: ui`, and there is no root `.prettierrc`/`.prettierignore`.
  **Root `README.md`/`CHANGELOG.md` are outside Prettier's scope** — the `ui/README.md` table-repadding
  failure from 15.3 cannot recur here unless this story touches `ui/`. It does not.
- `.pre-commit-config.yaml:34-39` — `build-plugin-sync`'s `files:` regex includes `README\.md`;
  `scripts/build_plugin.py:62` `SERVER_FILES` carries `README.md` and `NOTICE` but **not** `CHANGELOG.md`.
- `ui/tests/*copy*.test.ts` read `epics-companion-app.md` — so the Node-floor edit at `:333` must be
  followed by the frontend suite, even though the edited line is a stack-table row. 15.3 recorded that
  every such guard resolves by content and not by line number; this story re-proves it rather than
  assuming it.

## Tasks & Acceptance

**Execution:**

- [x] `README.md` -- add a new `## The companion app` section between `## Connect your client` (ends 194)
      and `## Where the data lives` (196) -- this is the story. It must cover, in the file's own voice:
      what the companion is and that **it is optional — every agent workflow completes with the app
      closed**; the single launch command; the launch line the user will see; that **Node is never required
      at install or runtime** (with the honest caveat that it is required to change the UI); port
      selection, precedence and the ephemeral fallback; the single-instance rule with **both** "already
      running" messages; what the discovery file is and what an unclean exit leaves; and the fresh-install
      narrative — the app starts anyway and the page directs the reader to `initialize_database`.
      Cross-link `[Where the data lives](#where-the-data-lives)` and the image-cache section.
- [x] `README.md` -- inside that section, a short **recovery note** for a failed first import: stop the
      companion first, then delete or re-import the partial database -- F4, documented not fixed.
- [x] `README.md:28` -- drop `*(in development)*` from the Companion app row and link it to the new
      section -- the label is false and it is the first thing a reader meets.
- [x] `README.md:52-56` -- `## Requirements`: state that the companion adds no new prerequisite -- the
      absence of a Node line is the point, so say it rather than leaving it inferred.
- [x] `README.md:350-373` -- add `src/companion/`, `ui/` and `src/viewer/` *(frozen)* to the source tree --
      the tree currently omits the entire subject of this epic.
- [x] `README.md:379-381` and `NOTICE:10-13` -- widen the Scryfall attribution to name **imagery**
      alongside card data -- the footer already claims it and the app caches it. Keep both URLs byte-exact.
- [x] `CHANGELOG.md:8` -- under `## [Unreleased]`, add `### Added` and `### Changed` **above** the existing
      `### Deprecated` -- recording the companion app, its two runtime dependencies with floors
      (`fastapi>=0.139.2`, `uvicorn[standard]>=0.51.0`) and the dev-only `websockets>=12.0`, the Node
      dev/CI-only floor `>=20.19.0`, and **why TypeScript is pinned `>=5.9 <6.1`** — an open floor installs
      TypeScript 7, which `typescript-eslint@8` (peer `>=4.8.4 <6.1.0`) refuses, breaking the lint gate;
      the cap is declared locally so the constraint is owned rather than inherited from a transitive peer.
- [x] `ARCHITECTURE-SPINE.md:396` and `epics-companion-app.md:333` -- correct the Node floor `>=20` →
      `>=20.19.0` -- the measured floor, per `ui/package.json:7`. Leave `epics-companion-app.md:1330`.
- [x] `plugin/server/**` -- regenerate with `uv run python -m scripts.build_plugin` and commit -- mandatory
      after the `README.md` and `NOTICE` edits; the sync hook does not run on commit on this machine.

**Acceptance Criteria:**

- Given the README, when the companion section is read, then it explains what the app is, that it is
  optional, and that every agent workflow works without it.
- Given the launch instructions, when they are followed, then `uv run artificial-planeswalker companion`
  is the single documented command and it is spelled identically at every occurrence in the repo's docs.
- Given a reader hitting a port conflict, when they consult only the README, then they can predict the
  behaviour without reading source: the default port, the precedence, the ephemeral fallback, and both
  "already running" messages with their exit status.
- Given a fresh install with no card database, when the docs describe first run, then they say the app
  starts anyway and directs the user to `initialize_database`, and they give the recovery for a partial
  database left by a failed import.
- Given the CHANGELOG, when `[Unreleased]` is read, then it records the companion app, the `view_deck`
  deprecation (already present), and the new dependencies with their version floors including the
  TypeScript cap's reason — and **no version has been cut**: `pyproject.toml:3` still reads `0.4.0`, no
  release heading is dated, and no `[0.5.0]` link definition exists.
- Given the licensing obligations, when the docs are reviewed, then Scryfall attribution naming imagery
  and the Wizards of the Coast Fan Content Policy notice appear in both `README.md` and `NOTICE`, and both
  URLs still match the footer's byte-for-byte.
- Given the edited tree, when the gates run, then `test_image_cache_docs.py` is green, the frontend suite
  is unmoved, and `git status --porcelain -- plugin/` is empty after a rebuild.

## Spec Change Log

- **2026-08-19 — prose guard added (review-driven, no intent change).** The Matrix Test Audit found
  all nine I/O matrix rows uncovered: `test_server.py` matches the announcement strings because it
  is the source-side test of them, not a README reader. Closed with
  `tests/unit/companion/test_companion_docs.py`. The Tasks list did not name a test because the
  Code Map's read-only survey read "exactly one test reads root `README.md`" as a *constraint* and
  not as a gap; it was both. No frozen intent moved — the guard asserts the section the Tasks list
  already required.
- **2026-08-19 — the ephemeral-fallback example's invented port removed.** The first cut printed
  `http://127.0.0.1:54321`, which "Do not invent a number" forbids. Not sourced but **deleted**: an
  ephemeral port is whatever the kernel had free, so no literal can be correct. The fenced block now
  carries the fallback line alone and the prose says the launch line follows it with the real port.
- **2026-08-19 — three-layer review patch set applied.** No intent gaps and no spec deviations. Two
  classes of change, both outside frozen intent: guard coverage (nine proven holes, each planted and
  now red) and documentation correctness (a false "prints exactly one line", the CHANGELOG's
  TypeScript rationale contradicting the measured result it summarises, a missing `### Upgrade
  notes` and `### Security` block, the image cache absent from the disk requirement, and the
  `view_deck` dead-end pointer the Intent names — still unlinked until this pass).

## Design Notes

**Why the section goes where it goes.** `### Image cache (companion app)` is the densest and most
fragile prose in the repo: eleven assertions read `README.md:242-348`, several by exact literal, and the
extractor terminates on an ATX heading of *any* level — so a `####` inserted inside it truncates the
section and starves every downstream check. The guard's own tests at `:480-513` prove the converse: prose
added before the section, or appended after it, cannot move it. Placing `## The companion app` at 195,
immediately after the per-client collapsibles and immediately before `## Where the data lives`, puts the
launch story where a reader arrives at it — right after wiring up their client — and keeps it entirely
outside the guarded range. The image-cache section then reads as the deeper dive it already is.

**Quote the code, not the plan.** Every number and message in this story exists in exactly one shipped
place, and the epic has already been bitten once by a figure that spread for sixteen days after being
disproved. `DEFAULT_PORT = 8765` is "the single place in `src/` that names the number", the launch line is
the only line uvicorn lets the user see, and `deps.py:3-12` already explains the fresh-install contract
better than a paraphrase would. The Code Map gives a `file:line` for each so the implementer transcribes
rather than reconstructs — and so a later reader can check the docs against the source in one hop.

**The "already running" message is two messages, and that is worth the words.** One names a URL because a
live companion was verified answering; the other refuses to name one because the other instance has not
printed its port yet. Collapsing them into a single sentence would document a system that does not exist,
and the distinction is exactly what makes a duplicate launch self-diagnosable. Both exit `0` — all three
of `run()`'s outcomes are successes, which is itself worth stating, because a reader who sees "already
running" and checks `$LASTEXITCODE` should not conclude something failed.

**What this story deliberately does not close.** The version stays at `0.4.0` and no heading is dated,
because the SC-5 gate is Story 15.6 and a dated release heading would assert a judgement Brad has not yet
made. The F4 lock defect is documented rather than fixed, so it stays open in the ledger with its severity
intact. The stale `DESIGN.md:375` citations under `ui/src/**` stay stale, following 15.3's precedent: a
comment-only fix is not worth a bundle-drift risk. Each of these is a decision with a reason, not an
oversight, and the review pass should read them as ruled.

## Verification

**Commands:**
- `uv run pytest tests/unit/companion/test_image_cache_docs.py -q` -- expected: 11 passed. This is the one
  test that reads root `README.md`; run it first and after every README edit.
- `uv run pytest -q` -- expected: no regression against the baseline measured at task 0. Record the
  collected count before editing anything and compare, rather than trusting "looks green".
- `cd ui && npm test` -- expected: unmoved. Required because `ui/tests/*copy*.test.ts` read
  `epics-companion-app.md`, which task 8 edits. Not `npm run format:check` — this story touches no `ui/`
  file, so Prettier is out of scope.
- `uv run python -m scripts.build_plugin && git status --porcelain -- plugin/` -- expected: empty output.
  Run **after the last edit**, not before; `README.md` and `NOTICE` are both in `SERVER_FILES`.
- `git diff --stat` -- expected: `src/` and `ui/src/` absent from the list. This story writes no code.

**Manual checks:**
- Read the new section against `src/companion/app/server.py:317-356` with both files open, and confirm
  every quoted message is character-identical, em dashes included.
- Confirm `pyproject.toml:3` still reads `version = "0.4.0"` and `CHANGELOG.md` has no `[0.5.0]` heading
  and no new link definition.
- Confirm the two attribution URLs in `NOTICE` are byte-identical to
  `ui/src/components/Footer/copy.ts:66,70` after the imagery edit.

## Verification Record

**Prose guard added after review.** The Matrix Test Audit found all nine I/O matrix rows uncovered:
`test_server.py` matches the announcement strings because it is the *source-side* test of them, not a
README reader, so `## The companion app` was gated by nothing. Closed by
`tests/unit/companion/test_companion_docs.py` (15 tests), written to `test_image_cache_docs.py`'s
idiom — heading-anchored, fence-aware extraction with a non-vacuity anchor, every claim keyed on a
shipped symbol (`server.HOST`, `server.DEFAULT_PORT`, `server.PORT_ENV_VAR`, `server._MIN_PORT`,
`server._MAX_PORT`, `discovery.COMPANION_FILENAME`, `singleton.LOCK_FILENAME`,
`paths.database_path()`, `SetActiveDeckResult.status`) or read out of source (`server.py`'s AST for
the four `[planeswalker]` announcements, `__main__.py`'s AST for every integer `return`,
`pyproject.toml` for the console script and the base dependencies, `_USAGE` for the subcommand, and
`ui/src/components/StatePanel/copy.ts` for the three fresh-install panel lines, looked up by the
kebab spelling of the shipped `database_not_initialized` reason token). Residue is declared in the
module docstring.

**Matrix coverage.** Row 1 → `test_every_line_the_runner_prints_is_quoted_verbatim`,
`test_the_quoted_launch_line_carries_the_shipped_host_and_default_port`,
`test_the_documented_launch_command_is_the_installed_console_script`. Row 2 →
`test_every_line_the_runner_prints_is_quoted_verbatim`. Rows 3-4 →
`test_both_already_running_messages_are_documented_and_kept_apart`,
`test_the_documented_exit_statuses_are_the_only_ones_the_dispatcher_returns`. Row 5 →
`test_the_default_port_and_both_overrides_are_the_shipped_ones` (precedence *exercised* against
`resolve_preferred_port`, not merely asserted) plus the exit-status test. Row 6 →
`test_the_fresh_install_narrative_quotes_the_shipped_panel`. Row 7 →
`test_the_failed_import_recovery_says_stop_the_app_first`. Rows 8-9 →
`test_the_discovery_and_lock_filenames_are_the_shipped_constants`.

**One deliberate divergence from `test_image_cache_docs.py`:** its extractor terminates on an ATX
heading of *any* level, correct for a `###` section with no subsections. `## The companion app` owns
six `###` subsections, so this extractor terminates on a heading of the section's own level or
higher, derived from `SECTION_HEADING`. Both bounds are tested, including that the neighbouring
`### Image cache (companion app)` stays *outside* the extraction — otherwise an assertion here could
pass on story 15-2's prose.

**Two counts, two populations — not two baselines.** `scripts.probe_harness` owns its argv and runs
`-m "not integration"`, so its figures (3150 → 3155) deliberately exclude the integration tests that
`uv run pytest -q` collects (3188 → 3203 → 3208). Both grew by exactly the number of tests added, and
neither is a regression against the other.

**Firing proofs** — full suite via `uv run python -m scripts.probe_harness`, one plant per assertion
family, tree staged before each plant and each revert verified with `git diff --exit-code`:

```
green baseline   full suite (-m 'not integration'): 3150 collected, 0 failed, exit 0

1 README launch-line port 8765 -> 8766
                 full suite (-m 'not integration'): 3150 collected, 1 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_the_quoted_launch_line_carries_the_shipped_host_and_default_port

2 README drops the "another companion is already starting up" message
                 full suite (-m 'not integration'): 3150 collected, 2 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_every_line_the_runner_prints_is_quoted_verbatim
  RED    test_companion_docs.py::…::test_both_already_running_messages_are_documented_and_kept_apart

3 README recovery reworded, dropping "Stop the companion first"
                 full suite (-m 'not integration'): 3150 collected, 1 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_the_failed_import_recovery_says_stop_the_app_first

4 README panel headline "Card database not set up yet." -> "Card database is not set up yet."
                 full suite (-m 'not integration'): 3150 collected, 1 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_the_fresh_install_narrative_quotes_the_shipped_panel

5 README leftovers say "its lock file" instead of `companion.lock`
                 full suite (-m 'not integration'): 3150 collected, 1 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_the_discovery_and_lock_filenames_are_the_shipped_constants

6 README documents exit `1` instead of `2`
                 full suite (-m 'not integration'): 3150 collected, 1 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_the_documented_exit_statuses_are_the_only_ones_the_dispatcher_returns

7 README section renamed to "## The companion application" (non-vacuity anchor)
                 full suite (-m 'not integration'): 3150 collected, 15 failed, 0 errored, exit 1
  RED    all 15 tests in test_companion_docs.py — the guard cannot pass over a missing section

8 SOURCE-side: src/companion/app/server.py `DEFAULT_PORT = 8765` -> `8766`
                 full suite (-m 'not integration'): 3150 collected, 5 failed, 0 errored, exit 1
  RED    test_companion_docs.py::…::test_the_quoted_launch_line_carries_the_shipped_host_and_default_port
  RED    test_companion_docs.py::…::test_both_already_running_messages_are_documented_and_kept_apart
  RED    test_companion_docs.py::…::test_the_default_port_and_both_overrides_are_the_shipped_ones
  RED    test_server.py::TestPortResolution::test_defaults_when_nothing_is_configured
  RED    test_server.py::TestNothingElseHardcodesThePort::test_only_the_runner_names_the_default_port
```

Proof 8 is the one that matters most: the README was untouched and the guard still went red, which
is what "keyed on the shipped symbol" means. Every revert was verified clean
(`git diff --exit-code <file>` → exit 0) and `git status --porcelain` showed no plant residue.

**Review round 1 — patch set applied 2026-08-19, with eight further firing proofs.** The review
proved nine guard holes by planting and reverting; each is now closed and red. Two of the new
assertions were themselves wrong on the first cut, and their own firing proofs are what said so —
both are recorded here rather than quietly fixed:

* **Proof 12 failed the first time.** The attribution check searched each file *whole*, so reverting
  `NOTICE`'s Scryfall sentence still passed: the word survived in a section heading elsewhere in the
  file. A credit is a sentence, not a file. Rescoped to every blank-line paragraph carrying the
  Scryfall href, and re-proved.
* **Proof 14 failed the first time.** Reading `ShowSuggestionsResult` alongside `SetActiveDeckResult`
  closed the *model* half, but the claim that **both** tools report the token is made in the
  capability table at `README.md:28` — outside the guarded section, so the plant changed nothing the
  guard could see. The assertion now reads `## What it does` too, and re-proved red.

```
9  README fallback example: port 8765 -> 9999   (slot was a wildcard; 15 tests stayed green)
                 3155 collected, 1 failed, exit 1
  RED    …::test_the_quoted_fallback_line_names_the_shipped_default_port

10 README capability row: ](#the-companion-app) -> a slug naming no heading
                 3155 collected, 1 failed, exit 1
  RED    …::test_every_in_page_link_resolves_and_this_section_is_linked_to

11 README ## Requirements: "Node is not required" -> "Node 22 or newer is required"
                 3155 collected, 1 failed, exit 1
  RED    …::test_the_section_says_node_is_never_required_and_pyproject_agrees

12 NOTICE attribution reverted to card data only  (re-run after rescoping)
                 3155 collected, 1 failed, exit 1
  RED    …TestTheAttributionNamesWhatTheAppActuallyUses::test_the_docs_claim_every_subject_the_footer_claims

13 README attribution reverted to card data only
                 3155 collected, 1 failed, exit 1
  RED    …TestTheAttributionNamesWhatTheAppActuallyUses::test_the_docs_claim_every_subject_the_footer_claims

14 README capability row drops `app_not_running`  (re-run after widening the assertion)
                 3155 collected, 1 failed, exit 1
  RED    …::test_the_section_says_the_companion_is_optional

15 README: an unclosed `~~~` fence opened inside the section
                 3155 collected, 17 failed, exit 1
  RED    every test that reads the section — the extraction fails loudly instead of silently
         widening to the whole file

16 SOURCE-side: src/mcp_server/__main__.py gains a `sys.exit(3)` call
                 3155 collected, 1 failed, exit 1
  RED    …::test_the_documented_exit_statuses_are_the_only_ones_the_dispatcher_returns
```

**Two new assertions carry no firing proof, deliberately.** The panel-copy backslash rejection fires
only on an escape sequence appearing in `ui/src/components/StatePanel/copy.ts`, and the
precedence-probe range guard fires only if `DEFAULT_PORT` moved within two of `_MAX_PORT`. Planting
either means editing a file this story is barred from touching for a proof of a defensive branch;
both are stated here as unproven rather than counted as proven.

**Attribution guard placement.** The subject check went into the Python guard, not
`ui/tests/attribution.test.ts`. `ui/tests/**` sits under the spec's *Ask First* list, and the Python
side needs no permission, touches no `ui/` file, and cannot perturb the committed bundle or
Prettier's scope. It reads `ui/src/components/Footer/copy.ts` read-only, which is how it stays keyed
to what the app claims rather than to what the test remembers. `git status --porcelain` confirms no
`ui/` file changed and the bundle is byte-identical.

**Invented-number correction.** The ephemeral-fallback example printed `http://127.0.0.1:54321`,
an invented illustrative port that the Boundaries section forbids. It is **removed rather than
sourced**: an ephemeral port is by definition whatever the kernel had free, so no literal can be
correct. The fenced block now shows only the fallback line, and the prose says the usual launch line
follows it naming the port actually handed out — and says why no example prints one.

**Final gate results:** `uv run pytest -q` → **3208 passed, 2 skipped** — story baseline 3188/2,
+15 for the first guard cut and +5 for the review's new assertions, no regression at any step.
`cd ui && npm test` → 80 files / 2305 tests, unmoved through both passes. `ruff check .` and
`ruff format --check` clean, `mypy src/` clean on 94 files. `uv run python -m scripts.build_plugin`
then `git status --porcelain -- plugin/` → empty. `git diff --stat` carries no `src/` or `ui/` file.

## Suggested Review Order

**The section itself — read this first**

- The entry point: what the companion is, and that nothing depends on it.
  [`README.md:201`](../../README.md#L201)

- The one documented command, and why its printed line is the only one.
  [`README.md:212`](../../README.md#L212)

- Port precedence, the ephemeral fallback, and the full `--port` contract.
  [`README.md:242`](../../README.md#L242)

- Both "already running" messages — the pair, not one message.
  [`README.md:284`](../../README.md#L284)

- The fresh-install narrative and the F4 recovery this story documents but does not fix.
  [`README.md:341`](../../README.md#L341)

**Claims that live outside the section, and can contradict it**

- Discovery, the token, and the loopback-only envelope a listening socket earns.
  [`README.md:307`](../../README.md#L307)

- The capability row that was a dead end; now a link.
  [`README.md:28`](../../README.md#L28)

- Prerequisites: Node absent by design, plus the measured cache footprint.
  [`README.md:52`](../../README.md#L52)

**Release record**

- What shipped, with dependency floors sourced from `pyproject.toml`.
  [`CHANGELOG.md:10`](../../CHANGELOG.md#L10)

- The TypeScript cap carrying both halves — the refusal and the back-solve to 6.0.3.
  [`CHANGELOG.md:55`](../../CHANGELOG.md#L55)

- A listening socket added to a stdio-only tool warrants its own entry.
  [`CHANGELOG.md:91`](../../CHANGELOG.md#L91)

- Upgrade notes, this file's own convention, carrying the F4 limitation.
  [`CHANGELOG.md:102`](../../CHANGELOG.md#L102)

**Attribution**

- Imagery named where only card data was claimed; both URLs byte-exact.
  [`NOTICE:7`](../../NOTICE#L7)

- The README half of the same correction.
  [`README.md:572`](../../README.md#L572)

**The guard — supporting, but it is what holds all of the above**

- The section constant, and why renaming it is more than one edit.
  [`test_companion_docs.py:101`](../tests/unit/companion/test_companion_docs.py#L101)

- Fence-aware extraction that fails loudly rather than widening to EOF.
  [`test_companion_docs.py:268`](../tests/unit/companion/test_companion_docs.py#L268)

- Prose claims compared through a normaliser, not pinned to markdown formatting.
  [`test_companion_docs.py:170`](../tests/unit/companion/test_companion_docs.py#L170)

- Every assertion keyed on a shipped symbol; zero hand-typed README strings.
  [`test_companion_docs.py:483`](../tests/unit/companion/test_companion_docs.py#L483)

- The attribution coupling, added at review after its first version proved vacuous.
  [`test_companion_docs.py:1029`](../tests/unit/companion/test_companion_docs.py#L1029)

**Peripherals**

- Node floor corrected to the measured `>=20.19.0`.
  [`ARCHITECTURE-SPINE.md:396`](../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L396)

- The same correction in the epic's stack table.
  [`epics-companion-app.md:333`](../planning-artifacts/epics-companion-app.md#L333)
