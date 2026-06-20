# Deferred Work

## Deferred from: code review of 1-1-repository-restructure-dependency-reshape (2026-06-20)

- **`legacy/tests/conftest.py` module-level chainlit import** — `import chainlit` at the top of `legacy/tests/conftest.py` (line 8) causes `ModuleNotFoundError` if someone runs `pytest legacy/tests/` on a lean env (without `--group legacy`). `testpaths = ["tests"]` protects the default run. Fix: add a note to `legacy/` documentation or add a root-level `conftest.py` `collect_ignore_glob` guard to make the failure message clearer.

- **`mock_user_session` fixture state leak** — `legacy/tests/conftest.py` patches `cl.user_session.get/.set` at fixture setup time with no teardown/restore. If a test using this fixture fails mid-run, subsequent tests in the same session inherit the patched session. Fix: rewrite using pytest's `monkeypatch` fixture or a `yield`-based restore. Applies to the legacy test tree only (excluded from active CI).

- **Legacy tests' `tests.fixtures.card_data` import** — Files like `legacy/tests/integration/agent/test_agent_card_search.py` import `from tests.fixtures.card_data`. This works when pytest sets the project root on `sys.path` (standard `uv run pytest` from root) but may fail in IDEs or when running `pytest legacy/tests/` in isolation. Fix: either copy shared fixtures into `legacy/tests/fixtures/` or add a `conftest.py` `sys.path` adjustment to `legacy/tests/`.

- **`PaginatedResult[T]` missing field validators** — `src/data/schemas/pagination.py` has no validators to enforce `page >= 1`, `page_size >= 1`, or `total_pages` consistency with `total_count`. A caller constructing `PaginatedResult(page=0, ...)` silently passes validation; a caller reading `page=1, total_pages=0` has an impossible state. Fix: add `Field(ge=1)` to `page`, `page_size`, `total_pages` and optionally a `model_validator` for `total_pages` consistency.

- **Task 0 out-of-scope changes** — Story 1.1 also shipped three pre-existing-defect fixes (explicitly approved by user): recreated `src/data/schemas/pagination.py`, fixed `CardModel.printed_name` default, and updated test contract assertions for `PaginatedResult`. These were correctness-restoring fixes needed to unblock AC4 (100 tests were failing at baseline). No follow-up action required; noted here for traceability.

## Deferred from: code review of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **Empty string `CARDS_DATABASE_URL` not guarded** — `_resolve_db_path` returns `""` if the env var is set to an empty string, which `sqlite3.connect("")` will fail on (OperationalError). This is an operator misconfiguration that fails loudly; not worth defensive handling given project rules against unnecessary validation. If it becomes a user-facing pain point, add a guard in `_resolve_db_path` to fall back to the default when the stripped URL is empty.

## Deferred from: code review of 1-3-fastmcp-server-with-card-lookup-bug-report (2026-06-20)

- **`updated_at` onupdate lambda silent in ORM** — `src/data/models/bug_report.py:43-47`. SQLAlchemy `mapped_column(onupdate=callable)` does not fire via the ORM unit-of-work; `updated_at` will always equal `created_at`. Matches the pre-existing `DeckModel` pattern. Only matters when a future story adds an update operation.
- **No CHECK constraint on status column** — `src/data/models/bug_report.py:32-34`. Any raw string can be written to `status` bypassing enum validation; reading it back via `BugReport.model_validate` would raise `ValueError`. Currently only triggered by manual DB manipulation. Address when an update story is implemented.
- **CardLookupResult.matches=[] on found status** — `src/mcp_server/tools/card_lookup.py`. An empty list rather than `None` for `matches` when `status="found"` is ambiguous for callers. Design preference; no functional bug.
- **LIKE wildcard injection in card_name/games** — `src/data/repositories/card.py`. Characters `%` and `_` in the card name or games list are passed un-escaped to SQLite LIKE. Pre-existing issue in `CardRepository`; out of scope for Story 1.3.
- **Non-DatabaseError exceptions skip explicit rollback in BugReportRepository** — `src/data/repositories/bug_report.py:50-69`. Exceptions that aren't `IntegrityError` or `DatabaseError` propagate without explicit `rollback()`. The session context manager handles cleanup on exit; low practical risk in current call paths.
- **migrate_add_bug_reports.py CWD-sensitive** — `scripts/migrate_add_bug_reports.py:20`. Default `DATABASE_URL` uses `./data/cards.db`; if the script is run from a non-root directory it silently targets the wrong file. Convention (run via `uv run` from project root) guards this; a doc comment would help.
- **Transport cast is runtime no-op** — `src/mcp_server/__main__.py:20`. `cast(_Transport, os.getenv(...))` provides no runtime validation. FastMCP raises on an invalid transport string anyway, but an explicit guard would give a clearer error message.

## Deferred from: dev of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **`test_list_decks` flaky ordering (pre-existing)** — `tests/integration/data/test_deck_repository.py::test_list_decks` asserts three rapidly-created decks come back newest-first, but `DeckRepository.list_decks` orders by `created_at.desc()` with **no secondary tie-breaker** ([`src/data/repositories/deck.py:260`](../../src/data/repositories/deck.py#L260)). When the three `create_deck` calls land on identical `created_at` timestamps (common under full-suite timing), SQLite resolves the tie arbitrarily and the assertion fails non-deterministically. Verified: the test passes 5/5 in isolation but fails intermittently in the full run. Unrelated to Story 1.2 (which only adds `src/search`); left untouched per scope discipline. Fix: add a deterministic secondary sort key to `list_decks` (e.g. `.order_by(DeckModel.created_at.desc(), DeckModel.id)`) **and** make the test's creation-order intent explicit (e.g. distinct/controlled `created_at` values), since UUID `id` is not time-ordered.
