---
baseline_commit: dcc8b9a
epic: c1
story: c1-1
work_branch: feat/companion-app
---

# Story C1.1: Companion package skeleton with CI-enforced import boundaries

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer building the companion,
I want the read-only and leaf/app import boundaries enforced by CI before any companion code exists,
so that the single-writer premise is structural rather than aspirational, and no later story can quietly breach it.

**Why this story is first.** EPIC-SPLIT.md calls these two guards *"the highest-leverage stories in
the whole feature"* — they are what make AD-2 and AD-3 real rather than aspirational, and they are
cheapest to write **before** there is any code to retrofit them against. Every one of the remaining
75 companion stories is born under them.

## Acceptance Criteria

1. **Package skeleton, nothing more.** `src/companion/__init__.py` and
   `src/companion/app/__init__.py` exist and contain **only a module docstring** (project rule:
   every `src/` file opens with a one-line module docstring). No `contracts.py`, `discovery.py`,
   `client.py`, `main.py`, or any other companion module is created in this story — the guards must
   pass against an empty package, and the modules they guard arrive in later stories.

2. **The guards run in the default test run, unmarked, with no FastAPI installed.**
   `tests/unit/companion/test_import_boundary.py` (with `tests/unit/companion/__init__.py`, matching
   `tests/unit/data/`) passes under a bare `uv run pytest` **and** under
   `uv run pytest -m "not integration"` — no `integration` marker, no network, no database, no
   fixtures beyond `tmp_path`. The guards are **AST-based only**: they parse source files with
   `ast.parse` and never `import` the module under inspection, so they execute with neither
   `fastapi` nor `uvicorn` installed and they detect violations in modules that are never imported
   at runtime (AD-2, AD-3).

3. **Write guard — the banned surface.** An AST walk over every `*.py` under `src/companion/**`
   fails on any of the following, and the assertion message names the **file path, offending symbol
   and line number**, and states that **`src/mcp_server` is the sole writer** (AD-2):
   - a call to any repository **write** method from the closed set
     `{create_deck, update_deck, delete_deck, add_card_to_deck, remove_card_from_deck,
     update_card_quantity, update_deck_color_identity, merge_decks}` (attribute call, any receiver
     — these names are distinctive enough that an unconditional ban has no plausible false
     positive);
   - a **session mutation**: an attribute call `<recv>.<attr>` where
     `attr ∈ {add, add_all, delete, merge, commit, flush, bulk_save_objects}` **and** the last
     dotted segment of `ast.unparse(<recv>)`, lower-cased, is in
     `{session, sess, db, db_session, database, conn, connection}`. The receiver restriction is
     deliberate: an unrestricted `flush`/`add` ban would fire on `file.flush()` in `discovery.py`'s
     atomic temp+rename write and on ordinary `set.add(...)`;
   - a **DML construct**: importing or referencing `insert`, `update` or `delete` from `sqlalchemy`
     (closes the `session.execute(delete(...))` bypass that the receiver rule alone leaves open);
   - a **schema-creation call**: `init_database`, or any reference to `create_all` — FR-22 says the
     companion *serves a "database not initialized" state*, it never creates the schema;
   - an import of `src.data.importers` (or any submodule) — the bulk write path has no business
     inside a read model.

   Each banned category is a named module-level constant in the test file, in the project's closed
   `frozenset` idiom, with a comment saying which AD it serves.

4. **Guard-the-guard: the repository surface is pinned.** A second test reflects over
   `DeckRepository`, `CardRepository` and `ComboSnapshotRepository` (importing them is fine — the
   *test* is not under `src/companion/`) and asserts that **every public method name is classified**
   in exactly one of two explicit constants: the write set from AC 3 or a read set. An unclassified
   method fails with a message telling the developer to classify it. This is the project's standing
   *construction-site enumeration* discipline applied to a guard: a repository write method added in
   a future story cannot silently fall outside the ban.

5. **Leaf/app guard — three rules (AD-3).** A second AST walk enforces:
   - **`src/mcp_server/**`:** importing `src.companion.contracts`, `src.companion.discovery` or
     `src.companion.client` **passes**; importing `src.companion.app` or any submodule **fails at
     module level**. The single exemption is `src/mcp_server/__main__.py`, where a
     **function-local** (non-module-level) import of `src.companion.app.*` is permitted — see
     Decide-once #1. A module-level import there still fails.
   - **Leaf modules** (`src/companion/contracts.py`, `discovery.py`, `client.py` — named by a
     constant, checked only if the file exists, since this story creates none of them): the only
     permitted imports are the **stdlib** (membership in `sys.stdlib_module_names`), `pydantic`,
     `httpx`, `src.paths`, and the sibling leaf modules
     (`src.companion.contracts | discovery | client`). Anything else fails — in particular
     `fastapi`, `uvicorn`, `sqlalchemy`, `src.data`, `src.logic`, `src.companion.app`. There is
     **no `TYPE_CHECKING` exemption**: a leaf must not even type against FastAPI.
   - **Everything outside `src/companion/app/`:** scanning `src/**/*.py` and `scripts/**/*.py`, any
     module-level import of `src.companion.app*` fails, with the same `__main__.py` exemption.
     `tests/**` is **not** scanned — the integration test in story c5-8 must be free to boot the
     real app.

6. **Relative imports are resolved, not skipped.** `ast.ImportFrom` nodes with `level > 0` are
   resolved to their absolute dotted path from the scanned file's package position before any rule
   is applied. A guard that only understands `import src.companion.app` would miss
   `from .app import main` — the exact form a developer inside `src/companion/` would reach for.

7. **The scan cannot pass vacuously.** Each scan asserts it visited **at least one** file, and the
   `src/mcp_server/**` scan asserts a known-present file (`src/mcp_server/__main__.py`) was among
   them. The repo root is resolved from `Path(__file__).resolve().parents[...]`, never from the
   current working directory. `__pycache__` and non-`.py` files are excluded.

8. **The guards are proven to fail, not just to pass.** Negative coverage uses **synthetic source
   written to `tmp_path`** (never a violating file committed to `src/`): for each banned category in
   AC 3 and each rule in AC 5, a test asserts the guard reports a violation, and asserts the message
   contains the file path, the symbol and the line number. Matching positive cases assert the
   permitted forms produce **no** violation — `file.flush()`, `set.add(...)`, a leaf importing
   `httpx`/`pydantic`/`src.paths`/a sibling leaf, `src/mcp_server` importing a leaf module, and a
   function-local app import inside `src/mcp_server/__main__.py`. To make this possible the guard
   logic is factored as **pure functions over a file path (or source string) returning a list of
   violations**, with the pytest tests as thin callers.

9. **Quality gates green from the first commit (NFR-07).** `uv run ruff check .`,
   `uv run ruff format --check .`, `uv run mypy src/` and `uv run pytest -m "not integration"` all
   pass. The existing full suite (1,313+ tests) shows **no new failures**.

10. **Plugin mirror rebuilt and committed.** `src/companion/` is new source under `src/`, which the
    `build-plugin-sync` pre-commit hook and the CI *"Plugin tree in sync with src/"* step both watch.
    `uv run python -m scripts.build_plugin` is run and the resulting `plugin/` changes are committed
    in the same commit. CI fails otherwise.

11. **Scope boundary — what this story must NOT do.** No `fastapi` / `uvicorn` / `openapi-typescript`
    dependency is added to `pyproject.toml` (story c1-2 owns the ASGI app). No `.github/workflows/ci.yml`
    edit is needed — the guards are ordinary pytest tests already covered by the existing
    `uv run pytest -m "not integration"` step. No `.pre-commit-config.yaml` edit is needed — its mypy
    hook is already scoped `files: ^src/` and this story adds no runtime dependency that mypy must
    resolve. No `ui/` directory, no route, no app object.

## Tasks / Subtasks

- [x] **Task 0 — State verification** (standing team agreement from the epic-5/6 retros: any story
      whose notes assert repository state must open with the cheap check that proves it)
  - [x] Confirm the work branch: create `feat/companion-c1-1-package-skeleton` **off
        `feat/companion-app`** (not off `master`); the story PR targets `feat/companion-app`.
  - [x] Confirm `src/companion/` does **not** exist and `src/paths.py` **does**
        (`data_dir()` is what AD-4 will home the discovery file under).
  - [x] Confirm `tests/unit/companion/` does not exist, and that `tests/unit/data/__init__.py`
        exists (the `__init__.py`-per-test-package convention this story follows).

- [x] **Task 1 — Package skeleton** (AC: 1)
  - [x] `src/companion/__init__.py` — module docstring naming the package as the read model +
        relay peer of `src/mcp_server`, and stating the leaf/app split (AD-1, AD-3).
  - [x] `src/companion/app/__init__.py` — module docstring naming it the FastAPI shell, importable
        by nothing outside itself.
  - [x] Nothing else. Do not create `contracts.py`, `discovery.py`, `client.py` or `main.py`.

- [x] **Task 2 — Write guard** (AC: 2, 3, 6, 7)
  - [x] `tests/unit/companion/__init__.py` + `tests/unit/companion/test_import_boundary.py` with a
        module docstring that states both guards, their ADs, and the two documented limitations
        (see Dev Notes → Known limitations).
  - [x] Closed `frozenset` constants: `_REPO_WRITE_METHODS`, `_SESSION_MUTATORS`,
        `_SESSION_RECEIVERS`, `_DML_CONSTRUCTS`, `_SCHEMA_CREATION`, `_BANNED_MODULES`.
  - [x] A `Violation` record (path, symbol, line, rule) and a pure
        `find_write_violations(path: Path) -> list[Violation]` over `ast.parse` output.
  - [x] Relative-import resolution helper shared with Task 3 (AC 6).
  - [x] The scan over `src/companion/**/*.py` excluding `__pycache__`, with the non-empty assertion
        (AC 7) and repo-root resolution from `__file__`.
  - [x] Assertion message format: `f"{rel_path}:{line} — {symbol} ({rule}); src/mcp_server is the
        sole writer"`.

- [x] **Task 3 — Leaf/app guard** (AC: 2, 5, 6, 7)
  - [x] `find_import_violations(path: Path, *, role: ...) -> list[Violation]`, pure, with the three
        rules of AC 5.
  - [x] Module-level vs function-local classification: an import is *module-level* if it is
        reachable from the module body without passing through a `FunctionDef`/`AsyncFunctionDef`.
        (An import nested only inside `if TYPE_CHECKING:` counts as module-level — that is
        deliberate, see AC 5.)
  - [x] `_LEAF_MODULES`, `_LEAF_ALLOWED_THIRD_PARTY = {"pydantic", "httpx"}`,
        `_LEAF_ALLOWED_SRC`, `_APP_IMPORT_EXEMPT = {"src/mcp_server/__main__.py"}` constants.
  - [x] Stdlib membership via `sys.stdlib_module_names` on the **top-level** name of the import.
  - [x] Scans over `src/mcp_server/**`, the leaf modules (skipped when absent), and
        `src/**` + `scripts/**` for the outside-app rule; `tests/**` excluded.

- [x] **Task 4 — Prove the guards fail** (AC: 8)
  - [x] Synthetic-source negative tests in `tmp_path`, one per banned category and per import rule,
        asserting path + symbol + line appear in the message.
  - [x] Positive tests for every permitted form listed in AC 8 — especially `file.flush()`,
        `set.add(...)`, and the function-local `__main__.py` app import.
  - [x] Vacuity tests: an empty scan directory raises, not passes (AC 7).

- [x] **Task 5 — Guard-the-guard on the repository surface** (AC: 4)
  - [x] Classify every public method of the three repositories into the write set (AC 3) or an
        explicit `_REPO_READ_METHODS`; fail on anything unclassified, with a message that tells the
        developer what to do.

- [x] **Task 6 — Quality gates and plugin mirror** (AC: 9, 10, 11)
  - [x] `uv run ruff check . --fix` · `uv run ruff format .` · `uv run mypy src/` ·
        `uv run pytest -m "not integration"`.
  - [x] `uv run python -m scripts.build_plugin`, then `git add plugin/` — verify
        `plugin/server/src/companion/` appears and `git status --porcelain -- plugin/` is clean
        after the commit (this is what the CI step checks).
  - [x] Confirm no `pyproject.toml`, `ci.yml` or `.pre-commit-config.yaml` change was made.

### Review Findings

- [x] [Review][Patch] (low) **RESOLVED — Brad's ruling: keep strict, document it.** TYPE_CHECKING imports count as module-level in *all* roles, not just the leaf: `if TYPE_CHECKING: from src.companion.app... ` fails everywhere, including `__main__.py`. Document this in the module docstring and home the consequence on story c1-9 (use string annotations or forgo typing against the app) [tests/unit/companion/test_import_boundary.py:21]
- [x] [Review][Patch] (high) No companion-surface enumeration pin: a future non-leaf `src/companion` module (incl. `__init__.py`) or a typo'd `_LEAF_MODULES` filename escapes every guard — add a test asserting every `*.py` under `src/companion/**` is either under `app/`, an `__init__.py`, or a member of `_LEAF_MODULES` (fail on anything unclassified, construction-site-enumeration style), and run the leaf import rule over the companion `__init__.py` files [tests/unit/companion/test_import_boundary.py:101]
- [x] [Review][Patch] (medium) `outside_app` role excuses a *module-level* app import in `__main__.py`, contradicting AC 5's function-local-only exemption (real tree saved only by the overlapping `mcp_server` scan) — drop `and not exempt` in the `outside_app` branch and add a pinning test [tests/unit/companion/test_import_boundary.py:411]
- [x] [Review][Patch] (medium) `import sqlalchemy as alch` defeats the DML rule (`alch.delete(...)` matches neither receiver set nor import rule; `emit` discards `alias.asname`) — track sqlalchemy import aliases per file as DML receivers, with a negative test [tests/unit/companion/test_import_boundary.py:86]
- [x] [Review][Patch] (medium) Repository write method referenced without a call bypasses the write guard (`fn = repo.create_deck; fn(...)`) — the names are already deemed unconditionally bannable, so flag bare `Attribute` references to `_REPO_WRITE_METHODS` too [tests/unit/companion/test_import_boundary.py:313]
- [x] [Review][Patch] (low) Dynamic-form bypasses (`importlib`/`runpy`/`__import__`/`getattr`) are undetectable and unstated — add as a third entry in the module docstring's Known limitations [tests/unit/companion/test_import_boundary.py:21]
- [x] [Review][Patch] (low) Public classmethods are invisible to guard-the-guard (`classmethod` objects are not `callable` on 3.12) — include `classmethod`/`staticmethod` in `_public_methods` [tests/unit/companion/test_import_boundary.py:910]
- [x] [Review][Patch] (low) A UTF-8-BOM source file crashes the scans with SyntaxError instead of a clean report — read with `encoding="utf-8-sig"` [tests/unit/companion/test_import_boundary.py:244]
- [x] [Review][Patch] (low) `resolve_import` with `level` exceeding package depth mis-resolves via a negative slice instead of failing — raise on `level - 1 > len(parts)` [tests/unit/companion/test_import_boundary.py:233]
- [x] [Review][Patch] (low) `session.flush()` — the banned twin of the documented `file.flush()` false-positive pair — has no negative test — add it to `_WRITE_VIOLATION_CASES` [tests/unit/companion/test_import_boundary.py:562]
- [x] [Review][Patch] (low) Dev Agent Record inaccuracies: "~750 lines" (actual 944) and gate outputs captured pre-plugin-build ("248 files already formatted"; at `dee555e` it is 250) — correct the Completion Notes [story record]
- [x] [Review][Patch] (medium) **Greptile P1 (PR #9):** `from sqlalchemy import *` + bare `delete(...)` bypassed the write guard — star imports were recorded as bare `base`, and bare-name DML calls are unattributable. Fixed: star imports are now recorded as `base.*` and a sqlalchemy star import is banned at the import site, with a negative test [tests/unit/companion/test_import_boundary.py:296]

## Dev Notes

### Decide-once rulings (made here so later stories inherit them)

**#1 — The dispatcher exemption (affects story c1-9).** AD-14 puts the subcommand dispatcher in
`src/mcp_server/__main__.py` ("`companion` runs the backend"), while AD-3 forbids `src/mcp_server/**`
from importing `src.companion.app.*`. Taken literally the two make c1-9 unimplementable. The ruling:
**a function-local import of `src.companion.app.*` inside `src/mcp_server/__main__.py` is permitted;
a module-level one is not.** This satisfies AD-3's stated prevention target verbatim — *"a stdio MCP
session transitively importing FastAPI and uvicorn merely to read a port number"* — because a bare
`artificial-planeswalker` invocation never enters the `companion` branch and therefore never imports
FastAPI. The exemption is one named constant, is scoped to that one file, and is not extended to any
other module under `src/mcp_server/**`. Do **not** widen it, and do **not** route around the guard
with `runpy`/`importlib` — a guard satisfied by obfuscation is theatre. *(Flagged for Brad in the
questions below.)*

**#2 — Sibling-leaf imports are allowed.** AD-3 says the leaf imports "`pydantic`, `httpx`,
`src.paths` and nothing else **from `src`**". Read strictly that would ban `client.py` from importing
`contracts.py` — which stories c6-1 and c7-1 require (the client posts contract models, and reads
`discovery.py` for port + token). The three leaf modules are collectively *the leaf*, so
intra-leaf imports are permitted; the rule's real target is `src.data`, `src.logic`,
`src.companion.app`, FastAPI, uvicorn and SQLAlchemy.

**#3 — The write guard bans more than the epic's four items.** The epic names "a repository write
method, `session.add`, `session.commit`, `session.delete`". AD-2's rule is broader — *"`src/companion`
cannot reach a write path"* — so the guard also covers `add_all`/`merge`/`flush`/`bulk_save_objects`,
SQLAlchemy DML constructs, `init_database`/`create_all`, and `src.data.importers`. Each addition
closes a bypass a later story could plausibly reach for; each is a named constant with its rationale
in a comment.

### Architecture rules this story makes structural

- **AD-1** — `src/companion/` is a **sibling** of `src/mcp_server/`, both over the same
  `src/data` + `src/logic`. It defines no second card or deck shape and is **not** an MCP client.
- **AD-2** — the MCP server is the **only** writer. Read-only is enforced by *this CI import
  boundary*, deliberately **not** by `mode=ro`: `mode=ro` on a WAL database drags in the `-shm`
  recipe the PRD addendum flagged as a Windows landmine, and `immutable` would foreclose FR-16.
  (PRD NFR-02 still names `mode=ro`; amending it is story c8-3's deliverable, not this one's.)
- **AD-3** — leaf (`contracts.py` / `discovery.py` / `client.py`) vs app (`app/`). The MCP server
  may import the leaf, never the app; nothing outside `app/` imports `app/`.
- **AD-10 / FR-22** — the reason `init_database` and `create_all` are banned here: a missing database
  is a *served UI state*, never something the companion fixes by writing.

### Source tree — what exists, what this story adds

```text
src/
  paths.py                     # EXISTS — data_dir(), database_path(), honours PLANESWALKER_DATA_DIR
  data/                        # EXISTS — repositories return Pydantic schemas, never ORM models
    repositories/{base,card,deck,combo_snapshot}.py
    importers/                 # banned import target for src/companion (AC 3)
    database.py                # create_engine / create_session_factory / init_database
  logic/                       # EXISTS
  mcp_server/
    __main__.py                # EXISTS — console-script target; becomes the dispatcher in c1-9
    server.py, tools/*.py      # EXISTS — 20 registered tools
  search/, viewer/             # EXISTS
  companion/                   # NEW — this story: __init__.py only
    app/                       # NEW — this story: __init__.py only
tests/
  unit/companion/              # NEW — __init__.py + test_import_boundary.py
```

Everything else named in the spine's structural seed (`contracts.py`, `discovery.py`, `client.py`,
`app/main.py`, `app/deps.py`, `app/state.py`, `app/security.py`, `app/routes/`, `app/ws.py`,
`app/images.py`, `app/static/`, `ui/`) belongs to later stories. Creating a stub for any of them
here would put a file under a guard that no story yet owns.

### Repository surface as of `dcc8b9a` (for AC 3 and AC 4)

| Repository | Write methods (banned) | Read methods |
| --- | --- | --- |
| `DeckRepository` (`src/data/repositories/deck.py`) | `create_deck`, `update_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`, `update_card_quantity`, `update_deck_color_identity`, `merge_decks` | `get_deck`, `list_decks`, `find_deck_by_name`, `get_deck_with_cards` |
| `CardRepository` (`card.py`) | — | `get_by_id`, `find_by_name_exact`, `find_by_name_partial`, `find_by_colors`, `find_by_type`, `search_by_keywords`, `search_advanced` |
| `ComboSnapshotRepository` (`combo_snapshot.py`) | — | `snapshot_is_available`, `get_snapshot_state`, `get_metadata`, `get_variants_for_names` |

`BaseRepository` (`base.py`) holds only `__init__(self, session)` and the `self.session` attribute —
which is exactly why the session-mutation rule keys on a receiver whose last segment is `session`.

### Project conventions the guard file must itself obey

- **Module docstring** at the top of every file; **Google-style docstrings** (`Args:` / `Returns:`)
  on the guard's public helper functions.
- **ruff**: line-length 100, `E,F,I,W,N,UP`; isort-ordered imports (stdlib → third-party →
  first-party `src.*`); modern 3.12 syntax (`X | None`, `list[str]`).
- **mypy `--strict`** runs over `src/` only (`uv run mypy src/`), so the test file is not strictly
  typed by CI — but `tests.*` only relaxes `disallow_untyped_defs`; ruff still lints it. Type the
  helper signatures anyway; the pre-commit mypy hook is `files: ^src/`.
- **pytest**: `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed — irrelevant here, these are
  sync tests), `--strict-markers` (so an undeclared marker is an error — do not invent one),
  files `test_*.py`, classes `Test*`, functions `test_*`.
- **Logging, not prints**, in library code with `%`-style lazy args. Not applicable to a test file,
  but the two `__init__.py` docstrings should not tempt anyone into module-level code.

### Gotchas that have bitten this repo before

1. **The plugin mirror is not automatic in every checkout.** An epic-4 retro action item records that
   `.git/hooks/pre-commit` was once absent locally, so `build-plugin-sync` silently did not run and
   CI failed on drift. The hook is installed as of `88b1e66`, but **run
   `uv run python -m scripts.build_plugin` explicitly and commit `plugin/`** — `scripts/build_plugin.py`
   copies the whole of `src/` verbatim, so `src/companion/` lands in `plugin/server/src/companion/`.
2. **`tests/unit/logic/` has no `__init__.py` while `tests/unit/data/` does.** Follow the
   `__init__.py` majority (`data`, `search`, `viewer`, `fixtures`, and every `tests/integration/*`
   package have one) so the new package imports cleanly.
3. **No AST-walking test exists in this repo yet** — there is no precedent to copy. That is expected;
   this story creates it. Do not go looking for a helper that isn't there.
4. **`ast.walk` flattens nesting.** It will happily hand you an import that lives four levels inside a
   function — which is what AC 5's module-level/function-local distinction needs to tell apart. Build
   the module-level set by recursing from the module body and *not* descending into function bodies,
   then treat `set(all_imports) - set(module_level)` as function-local.
5. **CWD is not the repo root under every runner.** Resolve the root from `__file__`
   (`Path(__file__).resolve().parents[3]` from `tests/unit/companion/test_import_boundary.py`) and
   assert a known marker (`pyproject.toml`) exists there.
6. **A guard with an empty scan list is a dead test.** AC 7 exists because this story's own package
   is nearly empty — the write scan legitimately walks two docstring-only files, and a path typo
   would make it walk zero and pass forever.

### Known limitations to document in the test module docstring (state them, don't hide them)

- **Raw SQL is not detected.** `session.execute(text("DELETE ..."))` would pass, because banning
  `sqlalchemy.text` would also ban legitimate read-side pragmas. Accepted; the receiver + DML-construct
  rules cover every ORM-shaped write path.
- **Aliased receivers are not detected.** `async with factory() as s: s.add(obj)` passes, because the
  receiver `s` is not in `_SESSION_RECEIVERS`. Accepted: adding single letters would fire on ordinary
  set/list code. The convention across `src/data` is `session` / `self.session`, and the *repository*
  write-method ban catches the realistic path anyway.

### Testing standards

- New tests live in `tests/unit/companion/` (unit layer mirrors `src/`; fast, no I/O beyond
  `tmp_path`). No `integration` marker — AD-10 reserves the single marked, real-socket test for
  story c5-8.
- Run: `uv run pytest tests/unit/companion/ -v` while iterating, then the full
  `uv run pytest -m "not integration"` before claiming done.
- **Verification before completion:** paste the actual pass counts for ruff, mypy and pytest into the
  Completion Notes. "Tests pass" without output is not acceptance.

### Previous story intelligence (Epic 7, the last completed code work)

There is no prior story in Epic C1. The most recent completed code story is `7-5-compare-deck-power-tool`
(done 2026-07-18). The transferable learnings, all from the epic-5/6/7 retros:

- **Task 0 state verification** — a standing team agreement since the epic-6 retro. Any story asserting
  environment/repo state opens with the cheap check that proves it. Task 0 above is that check.
- **Construction-site enumeration** — promoted to a standing agreement at the epic-7 retro: when a
  concept threads through multiple sites, enumerate *every* site before claiming end-to-end. AC 4's
  repository-classification pin is that discipline turned into an executable assertion.
- **Gate-output homing (epic-7 action item, still open)** — anything this story produces that another
  story must honour needs a key. The two decide-once rulings above are homed on stories **c1-9**
  (dispatcher exemption) and **c6-1 / c7-1** (sibling-leaf imports) explicitly rather than left as
  prose.

### Git intelligence

`HEAD = dcc8b9a`, branch `feat/companion-app`, working tree clean. The last five commits are all
`docs:` — the companion feature brief, PRD, UX spine, architecture spine and epics. **This is the
first code commit of the companion feature**, so there is no recent implementation pattern to match
in `src/companion/`; the patterns to match are the repo-wide ones in the section above.

Commit style: Conventional Commits. Suggested: `feat(companion): package skeleton with CI-enforced
import boundaries`.

### Latest technical information

- **No new dependency is introduced.** The guards use only the stdlib `ast`, `pathlib` and `sys`
  modules, all of which are stable on the Python `>=3.12` floor this project targets.
- `sys.stdlib_module_names` (3.10+) is the correct stdlib membership test for AC 5 — it is a frozenset
  of top-level module names and needs no import of the module being classified, which is precisely the
  no-import property AC 2 requires.
- FastAPI `>=0.139.2` and uvicorn[standard] `>=0.51.0` are the spine's pinned floors — **they belong
  to story c1-2**, not here. TypeScript's `>=5.9,<6.1` upper bound is load-bearing but belongs to
  story c2-1.

### Project Structure Notes

- `src/companion/` is additive; it neither moves nor modifies any existing module. No conflict with
  the current tree.
- `src/mcp_server/__main__.py` is *read* by the leaf/app guard but **not modified** by this story —
  its dispatcher rewrite is story c1-9.
- The only file outside `src/companion/` and `tests/unit/companion/` that this story changes is the
  generated `plugin/` mirror (AC 10), which is a build artifact, never hand-edited.

### References

- [epics-companion-app.md — Story 1.1](_bmad-output/planning-artifacts/epics-companion-app.md#L887-L922) — the source acceptance criteria
- [epics-companion-app.md — Epic 1 framing](_bmad-output/planning-artifacts/epics-companion-app.md#L879-L886) and [stories 1.2–1.9](_bmad-output/planning-artifacts/epics-companion-app.md#L924-L1166) — cross-story context (what must remain buildable under these guards)
- [epics-companion-app.md — Structure & boundaries / Testing](_bmad-output/planning-artifacts/epics-companion-app.md#L192-L206) — the two boundary tests as required deliverables
- ARCHITECTURE-SPINE.md — [AD-1](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L90-L99) · [AD-2](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L101-L112) · [AD-3](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L114-L125) · [AD-10](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L227-L240) · [AD-14](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L304-L313) · [Structural Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md#L433-L457)
- [EPIC-SPLIT.md — Story-shaping notes](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/EPIC-SPLIT.md#L112-L121) — "the highest-leverage stories in the whole feature"
- [prd.md — NFR-02, NFR-07](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md) (via epics inventory [L144-L168](_bmad-output/planning-artifacts/epics-companion-app.md#L144-L168))
- [project-context.md](_bmad-output/project-context.md) — layer boundaries, repository/schema contract, testing rules, ruff/mypy/docstring conventions
- [pyproject.toml](pyproject.toml#L60-L101) — ruff, mypy strict, pytest config
- [ci.yml](.github/workflows/ci.yml#L44-L67) — the four quality gates + the plugin drift check
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — mypy scoped `^src/`, `build-plugin-sync` on `^src/`
- [src/paths.py](src/paths.py) · [src/data/repositories/deck.py](src/data/repositories/deck.py) · [src/data/repositories/base.py](src/data/repositories/base.py) · [src/mcp_server/__main__.py](src/mcp_server/__main__.py)
- [sprint-status.yaml — companion key scheme + branch workflow](_bmad-output/implementation-artifacts/sprint-status.yaml#L187-L237)

## Open questions for Brad

Neither blocks implementation — both are recorded here because a later story inherits the answer.

1. **Dispatcher exemption (Decide-once #1).** Story c1-9 needs `artificial-planeswalker companion` to
   launch the backend from `src/mcp_server/__main__.py`, which AD-3 forbids from importing
   `src.companion.app`. This story permits a *function-local* import there and nowhere else. The
   alternative is moving the console-script entry point out of `src/mcp_server/` entirely — a bigger
   change to `pyproject.toml`'s `[project.scripts]` that AD-14 does not ask for. Confirm the narrow
   exemption is the one you want.
2. **Sibling-leaf imports (Decide-once #2).** AD-3's literal wording ("nothing else from `src`")
   would stop `client.py` importing `contracts.py`. This story allows intra-leaf imports. Worth a
   one-line amendment to AD-3 when story c8-3 reconciles the docs.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Code, bmad-dev-story workflow)

### Debug Log References

**Live proof that the real-tree scans fire** (not just the pure functions). Each guard was probed
with a temporary violating file, the failure output captured, then the probe deleted — no violating
file was ever committed:

1. `src/companion/_probe.py` with `from sqlalchemy import delete`, `from src.companion.app import
   main`, `session.commit()` →
   - write guard: `src/companion/_probe.py:8 — session.commit (session mutation); src/mcp_server is
     the sole writer` and `src/companion/_probe.py:3 — sqlalchemy.delete (sqlalchemy DML
     construct); …`
   - outside-app guard: `src/companion/_probe.py:4 — src.companion.app.main (nothing outside
     src/companion/app/ may import src.companion.app (AD-3))`
2. `src/mcp_server/_probe.py` with `import src.companion.app` → `src/mcp_server/_probe.py:3 —
   src.companion.app (src/mcp_server must not import src.companion.app (AD-3))`
3. `src/companion/client.py` with `from src.data.repositories import DeckRepository` → leaf guard:
   `src/companion/client.py:3 — src.data.repositories.DeckRepository (a leaf module may import only
   the stdlib, pydantic, httpx, src.paths and its sibling leaf modules (AD-3))`

This closes the gap the AC-8 synthetic tests cannot: those exercise the pure functions, while the
probes prove the four real scans are wired to the right roots and roles.

### Completion Notes List

**What was built.** Two AST-only import boundaries, landed before the code they guard. The
`src/companion` package is two docstring-only `__init__.py` files; all the substance is
`tests/unit/companion/test_import_boundary.py` (49 tests, 1,067 lines after review patches — the
original claim of "~750 lines" was inaccurate; the pre-review file was 944 lines with 40 tests):
pure violation-finding functions (`find_write_violations`, `find_import_violations`) plus thin
pytest callers, five real scans, and synthetic negative/positive coverage per rule.

**Verification output (actual, post-review-patches, at final tree state).** The originally
recorded outputs had been captured *before* the AC-10 plugin build (they reported 248 formatted
files; the committed tree has 250). Re-verified after applying all 11 review patches:

- `uv run ruff check .` → `All checks passed!`
- `uv run ruff format --check .` → `250 files already formatted`
- `uv run mypy src/` → `Success: no issues found in 72 source files`
- `uv run pytest tests/unit/companion/ -q` (bare, no marker filter) → `49 passed in 1.16s`
- `uv run pytest tests/unit/companion/ -m "not integration" -q` → `49 passed` (none deselected —
  confirms AC 2's unmarked requirement)
- `uv run pytest -m "not integration" -q` → **`1359 passed, 45 deselected in 60.39s`** — 1310
  pre-existing + 49 guard tests, **no new failures, no regressions**
- `uv run python -m scripts.build_plugin` → `Plugin assembled … (v0.4.0, 4 skills)`;
  `plugin/server/src/companion/{__init__.py,app/__init__.py}` present and committed (review
  patches touched only `tests/` and story artifacts, so the mirror needed no rebuild)

**Implementation decisions worth carrying forward.**

1. **Receiver-scoped DML rule.** AC 3 bans `insert`/`update`/`delete` "from sqlalchemy". An
   unconditional attribute ban on `update` would fire on ordinary `dict.update(...)` inside a read
   model, so the rule fires on (a) any `from sqlalchemy… import insert|update|delete`, and (b) an
   attribute access whose receiver's last segment is in `_DML_RECEIVERS = {sqlalchemy, sa, sql}`.
   A bare `delete(...)` is caught at its import site, which is the only way it can enter the file.
   `dict.update` has an explicit positive test.
2. **The `__main__.py` exemption is genuinely narrow.** For `role="mcp_server"` the app ban covers
   *both* module-level and function-local imports; only a function-local import in
   `src/mcp_server/__main__.py` is excused. Three tests pin this: a module-level import in
   `__main__.py` still fails, a function-local import in any *other* mcp_server module fails, and
   the dispatcher's function-local import passes. Decide-once #1 is therefore executable, not prose.
3. **`ImportFrom` is expanded to `parent` + `parent.alias`.** Needed so `from src.data import
   importers` resolves to the banned `src.data.importers`, and so the leaf rule accepts
   `from src.companion import contracts` (the specific target is permitted even though the parent
   `src.companion` is not).
4. **Module-level classification is a single guided recursion**, not `ast.walk` + set subtraction:
   the walk carries a `module_level` flag that flips to False only when descending into a
   `FunctionDef`/`AsyncFunctionDef`. An import under `if TYPE_CHECKING:` therefore stays
   module-level — deliberate, and covered by `leaf-has-no-type-checking-exemption`.
5. **Guard-the-guard is three assertions, not one.** Beyond AC 4's "every public method is
   classified", the read/write sets are asserted disjoint and `_REPO_WRITE_METHODS` is asserted to
   name only methods that still exist — so a *renamed* write method surfaces as a stale ban rather
   than a silently dead one.

**Scope boundary held (AC 11).** No `pyproject.toml`, `.github/workflows/ci.yml` or
`.pre-commit-config.yaml` change; no fastapi/uvicorn dependency; no `ui/`, route or app object; no
`contracts.py` / `discovery.py` / `client.py` / `main.py`. `git status` shows only `src/companion/`,
`tests/unit/companion/`, the `plugin/` mirror and the BMAD story artifacts.

**Open questions for Brad are unchanged and still worth an answer** — both decide-once rulings are
now encoded in constants (`_APP_IMPORT_EXEMPT`, `_LEAF_ALLOWED_SRC`), so reversing either is a
one-constant edit, but stories c1-9 / c6-1 / c7-1 inherit them as they stand.

### File List

- `src/companion/__init__.py` (new)
- `src/companion/app/__init__.py` (new)
- `tests/unit/companion/__init__.py` (new)
- `tests/unit/companion/test_import_boundary.py` (new)
- `plugin/server/src/companion/__init__.py` (new — generated mirror)
- `plugin/server/src/companion/app/__init__.py` (new — generated mirror)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — c1-1 → review)
- `_bmad-output/implementation-artifacts/c1-1-companion-package-skeleton-with-ci-enforced-import-boundaries.md` (modified — this story record)

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-25 | Story c1-1 implemented: companion package skeleton (two docstring-only `__init__.py`) plus the AD-2 write guard and AD-3 leaf/app guard as 40 AST-based unit tests; plugin mirror rebuilt. All quality gates green, 1350 tests passing, no regressions. Status → review. |
| 2026-07-25 | Greptile P1 on PR #9 fixed: `from sqlalchemy import *` + bare DML call bypassed the write guard; star imports now recorded as `base.*` and a sqlalchemy star import fails at the import site. 50 tests, 1360 passing. |
| 2026-07-25 | Adversarial code review (3 layers): 1 decision + 11 patches applied, 1 dismissed. Brad's ruling: TYPE_CHECKING imports stay module-level in every role (documented; homed on c1-9). Patches: companion-surface enumeration pin + leaf-constrained `__init__.py` (closes the future-non-leaf-module hole); `outside_app` role now fails module-level app imports in `__main__.py` per AC 5; `import sqlalchemy as X` alias-tracked as DML receiver; bare references to repo write methods banned; classmethods visible to guard-the-guard; BOM-tolerant parsing; over-deep relative imports raise instead of laundering; `session.flush()` negative case; dynamic-form limitation documented; Dev Agent Record corrected. 49 tests, 1359 passing, all gates green. Status → done. |
