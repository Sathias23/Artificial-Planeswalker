# Open-Source Release Readiness Review

**Date:** 2026-07-02
**Reviewed at:** `61cbc89` (master)
**Scope:** full repo + git history — code security, secrets/PII, docs & licensing, packaging & distribution, GitHub state.

> **Decision (2026-07-02):** the "Brad Sprigg" / "Sathias" names stay in the repo; the author's two
> personal email addresses are to be scrubbed from git history (they are deliberately not quoted in
> this document). See the identity section for what was found and where.

---

## Verdict

**Close to ready.** No credentials or secrets anywhere in the repo or its 78-commit history, no
critical or high-severity security bugs in the code, and core hygiene (LICENSE, NOTICE, SECURITY.md,
CI, templates) is strong. What remains: **one identity decision**, **six release blockers**, and a
set of should-fixes.

---

## The one decision: identity

Commit `2cc2dfd` deliberately moved all project contact info to the pseudonym
**Sathias / sathias@slopstudio.net** — but the git history undoes that:

- Every human commit in history is authored `Brad Sprigg <personal Outlook address>` (~78 commits, all branches).
- Historical file versions (pre-`2cc2dfd`) contain the personal Outlook address (66 hits) and a
  personal Gmail address (6 hits) in SECURITY.md, manifest.json, pyproject.toml, and spec docs —
  visible via `git log -p`.
- History also leaks the local machine username (`/home/brads/...` in since-deleted
  `SPIDER_MAN_INVESTIGATION.md` / `docs/project-scan-report.json`) and the handle `Bradmin`
  (historical `.bmad/bmm/config.yaml`).
- The **working tree** still says `Copyright (c) 2026 Brad Sprigg` in LICENSE and NOTICE, and
  `_bmad-output/` planning docs reference "Brad" by first name throughout.

**Resolution:** names ("Brad Sprigg", "Sathias", first-name references in `_bmad-output/`) are
accepted as public; the two personal email addresses are removed from history via a
`git filter-repo` rewrite (author/committer mailmap + blob and commit-message text replacement),
completed before the repo goes public. Note that a force-push alone does not purge old objects from
GitHub's side (merged-PR refs and caches retain pre-rewrite commits); the repo should be recreated,
or GitHub Support asked to run a gc, before flipping public if full scrubbing is required.

`_bmad-output/` content was read through: professional, technical, nothing embarrassing or about
third parties. Keeping it as the public design record is defensible — but note 50+ internal process
docs will be publicly indexed.

---

## Security review of the code

**No critical or high findings.** The two highest-risk surfaces were checked line-by-line and are clean:

- **SQL:** every query is parameterized (`src/search/query.py`, both repositories, index builder —
  the f-string-looking LIKE patterns are bound values, not SQL fragments; ORDER BY/LIMIT are
  integer-driven).
- **Viewer XSS:** JSON island with `</script>` breakout protection in `render.py`; `esc()` on every
  dynamic insertion in `template.html`; art-URL allowlisting in `view_model.py:197-232` blocks
  style-attribute injection.
- No `eval`/`exec`/`subprocess`/`pickle`/`yaml.load` anywhere in `src/` or `scripts/`; TLS
  verification intact with explicit timeouts; deck-view filenames are slug+UUID (no path traversal);
  `webbrowser.open` only on locally rendered `file://` output.

### Findings to harden before release

| # | Sev | Where | Issue | Fix |
|---|-----|-------|-------|-----|
| M1 | Medium | `src/data/importers/scryfall.py:77-81`, `scryfall_api.py:109` | Bulk download written to fixed, world-shared `/tmp/scryfall_<type>.json` — symlink overwrite / content pre-seed window on shared hosts | Use `tempfile.mkdtemp()` per run |
| M2 | Medium | `src/data/importers/scryfall_api.py:96-129` | No max-bytes cap and no check against the `size` field Scryfall advertises — disk exhaustion on a hostile/buggy source (parsing is streamed via ijson, so memory is fine) | Enforce a byte ceiling; compare to advertised `size` |
| L3 | Low | `src/data/importers/importer.py:71,81` | `download_uri` from API metadata fetched verbatim without scheme/host allowlisting | Assert `https://` + Scryfall host |
| L4 | Low | `src/viewer/present.py:24-36`, `src/mcp_server/__main__.py:36-41`, `initialize_database.py:170-173` | Tool output / stderr diagnostics / raw exception text include absolute host paths (username leak to the LLM client) | Conscious decision; consider sanitizing error strings |
| I5 | Info | `src/mcp_server/tools/find_similar.py:252-258` | `%`/`_` in seed name act as LIKE wildcards (bound param — no injection) | Documented behavior; no action |

---

## Release blockers

1. **README quick-start (`python3 setup.py`) fails on a fresh machine.** `setup.py:100-113` runs
   `uv sync` but then imports `src.data`/`sqlalchemy` in the *invoking* system interpreter →
   ImportError for exactly the new-user audience it targets. Re-exec the DB-init step via `uv run`.
2. **Installed plugin ships MIT code with no LICENSE/NOTICE**, and `plugin/server/README.md` has
   dead relative links (docs/, .env.example, LICENSE, CONTRIBUTING). Add LICENSE + NOTICE to
   `SERVER_FILES` in `scripts/build_plugin.py`; fix or absolutize the README links; rebuild + commit.
3. **`.mcpb` bundle double-ships the entire server.** `.mcpbignore` predates the committed `plugin/`
   tree — a real `mcpb pack` run showed 62 of 128 bundled files are the duplicate under `plugin/`.
   Add `/plugin/`, `/.claude-plugin/`, `scripts/build_plugin.py` to `.mcpbignore`.
4. **README contradicts itself about the semantic index.** Quick-start correctly says it's a
   separate step; the "Semantic search index" section (line ~133) claims `setup.py` builds it (it
   doesn't). Mirrored in `plugin/server/README.md`.
5. **`manifest.json` lists 14 of 16 tools** — `initialize_database` and `build_search_index` are
   missing even though the README tells Claude Desktop users to invoke both by name.
   (`docs/plugin-structure.md:17` also still says "14 tools".)
6. **Release infrastructure pointed at doesn't exist.** GitHub has zero releases and no `v0.1.0`
   tag, but CHANGELOG links to `releases/tag/v0.1.0` and the README sends users to a Releases
   `.mcpb` asset. Cut the tag/release with the packed bundle attached as part of going public.

---

## Should-fix before release

- **Dependencies:** `pydantic-settings` declared but imported nowhere; `pydantic` imported in 8+
  modules but only present transitively. Swap the declaration, `uv lock`, rebuild plugin.
- **pyproject.toml metadata:** no `license = "MIT"`, no `[project.urls]`, no classifiers — the one
  place the license *isn't* declared. Wheel also installs a top-level package literally named
  `src` (fine for git/plugin distribution; collision risk if ever on PyPI — rename or document as
  out of scope).
- **Scryfall non-endorsement line:** attribution + WotC Fan Content Policy wording are exemplary,
  but Scryfall's terms also ask for an explicit "not produced by or endorsed by Scryfall" sentence.
  One line each in NOTICE and README.
- **`docs/hero-image.png` provenance:** nothing states its origin/license (3.5 MB). If
  AI-generated/original, say so in NOTICE; if it uses MTG art, attach Fan Content framing; if
  unclear, replace. Compress either way.
- **CODE_OF_CONDUCT.md missing** — the only standard community file absent. Contributor Covenant
  2.1 with the existing contact email.
- **CHANGELOG behind HEAD** — marketplace distribution (`61cbc89`), plugin build script
  (`d91da3c`), and `initialize_database update=true` (`5787a73`) landed after 0.1.0 with no
  Unreleased section. Consider cutting 0.2.0 as the public release.
- **Small doc inconsistencies:** `setup.py:87` prints the stale "./data/cards.db" default; "~60k
  cards" claims (README, CONTRIBUTING, NOTICE) vs `oracle_cards` actually being ~30k;
  `.mcpbignore` still references removed `report_bug`-era scripts.
- **`manifest.json` uses `manifest_version: "0.4"` + `server.type: "uv"`** — the official CLI
  (v2.1.2) validates it, but it's an undocumented edge of the published spec (documented:
  `0.3` / `node|python|binary`). Add `mcpb validate` to CI to catch tooling drift.

---

## Nice-to-have

- CI/license badges in README.
- Tag-triggered release workflow that packs and attaches the `.mcpb`.
- Rename `setup.py` → `install.py`/`scripts/bootstrap.py` (it's a bootstrap CLI, not setuptools;
  the name will confuse contributors — hatchling is the build backend so nothing invokes it).
- Optional `user_config` entry in `manifest.json` mapping to `PLANESWALKER_DATA_DIR`.
- One-line fastembed (Apache-2.0) / `BAAI/bge-small-en-v1.5` (MIT) acknowledgment in NOTICE
  (nothing bundled, so not required).
- Drop stale `types-requests` from pre-commit's mypy `additional_dependencies`.
- Status header on `docs/architecture.md` (reads as a 2026-06-20 pivot doc but is presented as the
  design of record) and on `docs/plugin-structure.md` (self-describes as "a design note, not a
  build script" though `scripts/build_plugin.py` now exists).

---

## Verified in good shape

- **Secrets/history:** `.env` never committed; every historical key-shaped string is a placeholder;
  no databases, models, or user data ever committed; no real IPs/hostnames; largest blob is the
  intentional hero image.
- **Licensing:** clean MIT LICENSE (2026); NOTICE's WotC Fan Content Policy disclaimer uses the
  exact required wording with correct policy URL; MIT declared consistently in manifest.json,
  plugin.json, both READMEs, NOTICE, CONTRIBUTING; all direct + key transitive dependency licenses
  MIT-compatible (fastembed/onnxruntime heavyweight but core-feature-justified and license-clean).
- **Consistency:** version `0.1.0` and Python `>=3.12` match across pyproject (x2), uv.lock (x2),
  manifest.json, plugin.json, CHANGELOG, SECURITY.md, README, CI matrix. Repo URLs correct
  everywhere; root README relative links all resolve; no TODO/placeholder text; no ghost
  `report_bug` references in shipped docs.
- **Plugin tree:** zero drift — `src/` vs `plugin/server/src/` byte-identical (viewer template +
  view_model present in both), skills byte-identical, pyproject/uv.lock byte-identical.
  `scripts/build_plugin.py` is deterministic, hard-fails on missing files, cross-OS safe; CI
  rebuilds and fails on drift; `tests/integration/test_build_plugin.py` asserts 16 registered tools.
- **CI:** actions pinned to full SHAs, `permissions: contents: read`, no secrets (fork-PR safe),
  3.12/3.13 matrix, `uv sync --locked`, ruff lint + format-check, mypy --strict, pytest.
- **MCP surface:** all 16 tools validate inputs and return structured statuses; no tool accepts a
  caller-supplied filesystem write path; both `.mcp.json` files portable with no machine-specific
  paths; `uv lock --check` passes and the entry point imports cleanly.
- **GitHub state:** no open issues, no open PRs (checked 2026-07-02).

---

## Suggested order of operations

1. **Identity question — decided 2026-07-02:** names stay; scrub the two personal emails from
   history (rewrite + force-push, plus GitHub-side purge before going public).
2. Fix the six blockers (setup.py bootstrap, plugin LICENSE/README, `.mcpbignore`, README index
   claim, manifest tool list, tag + release with `.mcpb` attached).
3. Apply the download-hardening changes (M1 mkdtemp, M2 size cap) before the code gets public scrutiny.
4. Sweep the should-fixes (deps, pyproject metadata, Scryfall line, hero-image note, CoC,
   CHANGELOG/0.2.0).
