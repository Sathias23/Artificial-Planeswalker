# Contributing to Artificial Planeswalker

Thanks for your interest in improving Artificial Planeswalker — a local,
stateless [MCP](https://modelcontextprotocol.io) server that gives an LLM expert
Magic: The Gathering deckbuilding tools over a Scryfall card database.

## Getting set up

You need **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)** (the package
manager and runner — please don't use bare `pip`).

```bash
git clone https://github.com/Sathias23/Artificial-Planeswalker.git
cd Artificial-Planeswalker
python3 setup.py    # checks Python/uv, syncs deps, imports the card DB, installs pre-commit hooks
```

`setup.py` downloads public Scryfall bulk data (~30k cards, no API key) into a
central OS data directory — see the README for where it lives and how to override
it. The semantic-search index is separate and optional; build it when you need
`semantic_search_cards` / `find_similar_cards`:

```bash
uv run python scripts/build_card_embeddings.py   # idempotent + incremental
```

## Quality gates

Every commit is gated by pre-commit (ruff + `mypy --strict` over `src/`). Run the
full set before opening a PR:

```bash
uv run ruff check . --fix     # lint (auto-fix)
uv run ruff format .          # format (line length 100)
uv run mypy src/              # strict type-check
uv run pytest                 # tests (add -m "not integration" to skip DB/network)
```

Don't bypass the hooks — fix the underlying issue. If you add a runtime
dependency that mypy needs to resolve types, add it to `.pre-commit-config.yaml`'s
mypy `additional_dependencies` too.

## Generated artifacts

Three things in this repo are **committed build outputs, not sources**. None of them is
ever hand-edited — an edit is overwritten by the next build, and CI fails on the drift
in the meantime:

| Artifact | Regenerate with | Change it by editing |
|----------|-----------------|----------------------|
| `src/companion/app/static/` — the companion's built SPA bundle | `cd ui && npm run build` | `ui/` |
| `plugin/` — the assembled plugin tree, including its mirror of that bundle | `uv run python -m scripts.build_plugin` | `src/`, the four MTG skills, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, `NOTICE`, or `scripts/build_plugin.py` itself |
| `ui/src/api/types.d.ts` + `ui/src/api/openapi.json` — the TypeScript types generated from the backend's own schema | `cd ui && npm run gen:api` (needs uv; `npm run gen:types` alone regenerates the types half) | the FastAPI routes and Pydantic models in `src/companion/` |

The bundle is committed because the project also ships as a *cloned* plugin tree:
compiling the SPA at install time would leave plugin users with no UI. So the bundle
exists twice — under `src/` and mirrored into `plugin/` — and both copies are generated.
If you change the UI, rebuild the bundle **and** rebuild `plugin/`, and commit what the
tools emit.

Run the relevant build before opening a PR if you touched `ui/`, `src/`, the skills, or
any of the files above; CI rebuilds each artifact and fails if the committed result
differs. A pre-commit hook rebuilds `plugin/` for you — but only if you installed the
hooks (`setup.py` does), so if in doubt run the build and check `git status` yourself.

## Code conventions

- **Typing:** full type hints (`mypy --strict`); modern 3.12 syntax (`X | None`,
  `list[str]`, built-in generics — not `Optional`/`List`/`Dict`).
- **Docstrings:** Google style (`Args:` / `Returns:` / `Raises:`). For MCP tools
  the docstring doubles as the LLM-facing tool description, so keep it accurate.
- **Async boundaries:** `src/data` and `src/logic` are async (SQLAlchemy
  `AsyncSession`), and most MCP tools are `async def` that await them directly.
  The semantic-search tools (`semantic_search_cards`, `find_similar_cards`) are
  sync `def` — FastMCP runs them in a threadpool with their own per-thread SQLite
  connection, since the `sqlite-vec` query path is synchronous.
- **Logging, not prints**, in library code.

## Architecture in brief

Strict import direction; lower layers never import upward:

```
data → logic → mcp_server
```

`src/data` and `src/logic` are the reusable, framework-free domain core.
Repositories return Pydantic schemas, never ORM models. See
[`docs/architecture.md`](docs/architecture.md) for the design of record.

## Tests

`tests/` mirrors `src/`: `tests/unit/<layer>/` (fast, no I/O) and
`tests/integration/<layer>/` (DB, network). Mark network or DB tests with the
`integration` marker so they can be deselected with `-m "not integration"`.

## Pull requests

1. Branch off `master` (e.g. `feat/...`, `fix/...`, `chore/...`).
2. Use [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `chore:`, `docs:`, …).
3. Make sure tests pass and pre-commit is clean.
4. Open a PR against `master` describing the change and how you verified it.

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
