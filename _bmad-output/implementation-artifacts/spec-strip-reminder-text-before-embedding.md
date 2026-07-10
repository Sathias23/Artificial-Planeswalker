---
title: 'Strip parenthetical reminder text from oracle text before embedding'
type: 'feature'
created: '2026-07-10'
status: 'done'
baseline_commit: 'f443291ab1d4db49adc4464c1c30f29880f2c0a7'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/project-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Card oracle text includes parenthetical *reminder text* (e.g. Menace's `(This creature can't be blocked except by two or more creatures.)`, Convoke's `(Your creatures can help cast this spell...)`). It is embedded verbatim into `card_vec`, so its vocabulary pollutes semantic queries — menace cards surface for "unblockable", convoke cards for "ramp" — because the reminder text literally contains "blocked"/"help cast", diluting recall for true matches.

**Approach:** Strip parenthetical reminder text from `oracle_text` inside the single canonical `compose_card_text` recipe (the source of both the embedded text and its change-detection hash), so every card is embedded on its real rules text. Because only cards *with* reminder text change hash, a normal incremental `build_card_embeddings.py` re-embeds exactly those and skips the rest — no `--rebuild`.

## Boundaries & Constraints

**Always:** Strip inside `compose_card_text` so it stays the ONE canonical composition (production build + every test helper + the RAG eval comparison go through it). Stripping is a pure, deterministic string transform. Preserve the existing field order/newline recipe and the "never empty" guarantee (`name` is NOT NULL). Follow the project's mypy-strict, ruff, Google-docstring, logging rules.

**Ask First:** Any change to what a *query* is embedded against (queries go through `embedder.encode` raw, NOT `compose_card_text` — leave that path untouched). Any decision to force `--rebuild` semantics or touch the stored `content_hash` recipe beyond what the text change naturally causes.

**Never:** Do not strip braces `{...}` (mana/tap symbols are not reminder text). Do not modify the `cards` table or Scryfall import (the raw `oracle_text` column stays intact — stripping is embedding-time only). Do not rebuild/commit `card_vec` as part of this change (it is never committed; the operator re-runs the builder). Do not change query embedding, the tools, or `hybrid_search`.

## I/O & Edge-Case Matrix

`strip_reminder_text(oracle_text)` behavior:

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Trailing keyword reminder | `"Menace (This creature can't be blocked except by two or more creatures.)"` | `"Menace"` — no "blocked" left | N/A |
| Mid-text reminder | `"Convoke (Your creatures can help cast this spell.)\nFlying"` | `"Convoke\nFlying"` | N/A |
| Multiple parentheticals | `"Trample (…) Haste (…)"` | `"Trample Haste"` (single spaces) | N/A |
| Whole-text reminder (basic land) | `"({T}: Add {G}.)"` | `""` — composite still non-empty via name/type | N/A |
| No parentheses (vanilla / normal) | `"Deal 3 damage to any target."` | unchanged | N/A |
| Empty oracle text | `""` | `""` | N/A |
| Braces present | `"{T}: Add {G}."` | unchanged (braces are not parens) | N/A |

</frozen-after-approval>

## Code Map

- `src/search/index_builder.py` -- `compose_card_text` (line ~118) is the single canonical embedding-text recipe; feeds `content_hash`. Add `strip_reminder_text` here and apply it to `oracle_text` inside `compose_card_text`.
- `src/search/__init__.py` -- re-exports `compose_card_text`; export `strip_reminder_text` alongside it for test/tooling access.
- `tests/unit/search/test_index_builder.py` -- existing `compose_card_text`/`content_hash` unit tests; add `strip_reminder_text` cases + a hash-changes-on-reminder-card case.
- `tests/integration/search/test_rag_eval.py` -- the RAG regression guard (CLAUDE.md testing rule); must still pass. Its corpus/queries are hand-authored, unaffected by the recipe change.
- `_bmad-output/project-context.md` -- documents "Embedded text per card = name + type_line + mana_cost + oracle_text + keywords"; note oracle_text is now reminder-stripped.

## Tasks & Acceptance

**Execution:**
- [x] `src/search/index_builder.py` -- add pure `strip_reminder_text(oracle_text: str) -> str` (regex-remove `(...)` spans, tidy the spaces the removal leaves, drop lines that become empty; preserve internal newlines between surviving abilities) and call it on `oracle_text` at the top of `compose_card_text`; update the `compose_card_text` docstring to state reminder text is stripped and that this changes the hash of reminder-text cards (incremental re-embed, no `--rebuild`).
- [x] `src/search/__init__.py` -- export `strip_reminder_text`.
- [x] `tests/unit/search/test_index_builder.py` -- unit-test every I/O Matrix row for `strip_reminder_text`; add a test that `compose_card_text` output no longer contains a reminder phrase and that `content_hash` differs between a reminder-bearing card and its stripped form (proves incremental re-embed triggers).
- [x] `_bmad-output/project-context.md` -- one-line note that embedded `oracle_text` is reminder-stripped.

**Acceptance Criteria:**
- Given a card whose `oracle_text` is `"Menace (This creature can't be blocked except by two or more creatures.)"`, when `compose_card_text` runs, then the composite contains "Menace" and does NOT contain "blocked".
- Given a card with no parentheses in its oracle text, when `compose_card_text` runs, then its output (and thus `content_hash`) is byte-identical to before this change — so the incremental builder skips it (zero re-embed).
- Given a card whose oracle text is entirely reminder text (e.g. a basic land), when `compose_card_text` runs, then the result is non-empty (name + type_line still present) and the embedder is never handed `""`.
- Given the full test suite, when `uv run pytest` runs, then all tests pass including the RAG sanity eval (`test_rag_eval.py`).

## Spec Change Log

- **2026-07-10 (review, iter 0 — patches, no loopback):** Adversarial review (Blind Hunter + Edge Case Hunter) found the initial non-nested regex `\([^()]*\)` (1) left the outer span on nested reminders (5 silver-border DB cards) and (2) matched `\n`, so an unbalanced `(` could silently swallow later ability lines. Patched to a newline-excluding pattern applied to a fixed point (peels nesting innermost-first; unbalanced `(` is fail-safe — keeps text). Added nested-paren + unbalanced-paren tests. Softened the "always reminder text" docstring premise (Un-set/playtest cards excepted). Rejected as by-design/theoretical: the query/document embedding asymmetry (intended; RAG eval passes), no-space token merge, tabs, None input, golden-hash test. **KEEP:** stripping stays inside `compose_card_text` (single canonical recipe); query embedding path untouched; incremental re-embed (no `--rebuild`).

## Design Notes

Strip regex: `re.compile(r"\([^()\n]*\)")` matches a single-line parenthetical span. The inner class excludes `()` (so nested reminders are peeled innermost-first by substituting to a fixed point) and excludes `\n` (so an unbalanced `(` in malformed data strips nothing across a line break rather than silently deleting the intervening ability — fail-safe). Removal leaves stray double-spaces and possibly blank lines, so tidy per line: collapse runs of spaces, `strip()` each line, drop lines that became empty. Example:

```python
def strip_reminder_text(oracle_text: str) -> str:
    without = oracle_text
    while True:
        stripped = _REMINDER_TEXT_RE.sub("", without)
        if stripped == without:
            break
        without = stripped
    lines = [_MULTISPACE_RE.sub(" ", ln).strip() for ln in without.split("\n")]
    return "\n".join(ln for ln in lines if ln)
```

Why in `compose_card_text` and not at import: keeps the raw Scryfall `oracle_text` column intact (still available to `search_cards`/display) while making the embedding recipe the single place that defines embeddable text — the same recipe the RAG eval embeds against.

## Verification

**Commands:**
- `uv run pytest tests/unit/search/test_index_builder.py` -- expected: all pass, including new `strip_reminder_text` + hash-change cases.
- `uv run pytest tests/integration/search/test_rag_eval.py` -- expected: RAG hit-rate still meets target (regression guard).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.

**Manual checks:**
- To take effect on a live index, the operator re-runs `uv run python scripts/build_card_embeddings.py` (incremental; the summary should report the reminder-text cards as `changed` and the rest as `skipped`). Not part of automated verification — `card_vec` is never committed.

## Suggested Review Order

**The transform (start here)**

- Entry point: the pure reminder-strip helper — regex + fixed-point loop, newline-safe.
  [`index_builder.py:128`](../../src/search/index_builder.py#L128)
- The span pattern; excludes `()` (nesting) and `\n` (fail-safe against unbalanced parens).
  [`index_builder.py:123`](../../src/search/index_builder.py#L123)
- The one wiring point: `oracle_text` is stripped inside the canonical `compose_card_text` recipe.
  [`index_builder.py:208`](../../src/search/index_builder.py#L208)

**Surface & docs**

- Public export so tests/tooling can reach the helper.
  [`__init__.py:24`](../../src/search/__init__.py#L24)
- Recipe note: embedded `oracle_text` is reminder-stripped; raw column untouched.
  [`project-context.md:118`](../project-context.md#L118)

**Tests**

- I/O-matrix table (menace, convoke, nested, basic-land, braces, empty).
  [`test_index_builder.py:160`](../../tests/unit/search/test_index_builder.py#L160)
- Fail-safe: an unbalanced `(` never swallows a following ability line.
  [`test_index_builder.py:165`](../../tests/unit/search/test_index_builder.py#L165)
- Composite drops reminder vocabulary and its hash changes (drives incremental re-embed).
  [`test_index_builder.py:177`](../../tests/unit/search/test_index_builder.py#L177)
