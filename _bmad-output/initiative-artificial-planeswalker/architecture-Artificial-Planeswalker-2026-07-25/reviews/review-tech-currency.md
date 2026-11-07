# Reviewer lens — technology currency & reality check

**Target:** `ARCHITECTURE-SPINE.md` (companion-app, 2026-07-25)
**Verdict:** FAIL on one binding; everything else verified.

Lens: *"Verify every committed decision was web-researched or reality-checked rather than
asserted from training data."*

## Findings

### C-1 — CRITICAL — `TypeScript >=5.9` was asserted, and the truth breaks NFR-07

The draft bound `TypeScript >=5.9` without checking. Verification:

- **TypeScript 7.0 went GA 2026-07-08** (7.0.2 as of 2026-07-24) — the Go-native "Project Corsa"
  compiler, ~10× faster than 6.0.
- **But it breaks eslint, which NFR-07 requires in CI.** `typescript-eslint` closed its TS 7
  support request as *not planned* on day one; `typescript-eslint@8.63.0`'s published peer range
  allows only `TypeScript <6.1.0`, so `npm ci` fails outright, and forcing the install with
  `npm install` makes ESLint crash inside `@typescript-eslint/typescript-estree`.
- Root cause: TS 7 has **no stable programmatic API** until 7.1, "at least several months" out
  per Microsoft. Every tool that embeds the compiler is blocked behind that.

A `>=5.9` open-ended floor would resolve to TS 7 on a fresh install and break the frontend lint
gate on the first CI run.

**Fix applied:** bind `>=5.9,<6.1` — an upper bound matching typescript-eslint's peer range —
and move TS 7 adoption to Deferred, gated on 7.1's stable API.

### C-2 — verified correct

| Claim | Status |
| --- | --- |
| FastAPI >=0.139.2 | ✅ 0.139.2 released 2026-07-16; requires Python >=3.10, project is >=3.12 |
| uvicorn >=0.51.0 | ✅ 0.51.0, released 2026-07-08; requires Python >=3.10 |
| Vite >=8.0 | ✅ 8.0 stable 2026-03-12 (Rolldown), 8.0.9 by 2026-04-20 |
| React >=19.2 | ✅ 19.2.7, June 2026 |
| zustand >=5.0 | ✅ 5.0.14 |
| openapi-typescript >=7 | ✅ 7.13.0 current; reads OpenAPI 3.0/3.1, and FastAPI emits 3.1 |
| Node >=20 | ✅ matches openapi-typescript's stated requirement |
| httpx / pydantic / platformdirs / SQLAlchemy / mcp | ✅ read from the project's own `pyproject.toml`, not asserted |

### C-3 — brownfield reality checks (code, not memory)

| Claim | Verified against |
| --- | --- |
| MCP clients invoke `python -m src.mcp_server`, not the console script — so AD-14's dispatcher is safe | `.mcp.json`, `plugin/.mcp.json` — both confirmed |
| `src/paths.py` centralises data location via platformdirs | read in full; `data_dir()`, `database_path()`, `fastembed_cache_dir()` confirmed |
| WAL is genuinely enabled — AD-2's reasoning about `mode=ro` + `-shm` rests on it | `src/search/connection.py` sets `PRAGMA journal_mode=WAL` per connection; `src/data/database.py` comments confirm |
| `cards.image_uris` stores the Scryfall size map | `src/data/models/card.py:85` — `Mapped[dict[str, str] \| None]` |
| `card_faces` stores per-face data including per-face `image_uris` | `src/data/models/card.py:80`, `src/data/schemas/card.py:60`, `transformers.py` |
| **`cards.layout` does NOT exist** | see the adversarial-seam review, finding S-1 — this one is load-bearing |
| `src/viewer` exists and is served by `view_deck` | `src/viewer/{__init__,present,render,view_model}.py` + `template.html` |
| Epic-1 tools async, Epic-2 search tools sync | `src/mcp_server/server.py` module docstring |

## Verdict

One critical binding corrected. No decision in the spine now rests on an unverified version claim.
