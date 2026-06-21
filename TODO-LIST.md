# TODO List — MCP Server Improvements

Derived from a real usage session (2026-06-21) building four 60-card decks
(Mardu Midrange, Prismatic Dragon, Abzan Dragons) through the
`artificial-planeswalker` MCP tools. Items are ordered by leverage.

Legend: `[P0]` highest leverage · `[P1]` important · `[P2]` polish

---

## P0 — Ingestion (biggest workflow win)

- [ ] **`[P0]` Decklist importer** — Add an `import_decklist(deck_id, text)` tool
  that parses the MTGA export format (`4 Sephiroth, Fabled SOLDIER (FIN) 115`)
  and adds every line in one call.
  - _Why:_ Adding one deck took ~39 separate `add_card_to_deck` calls. This is
    the dominant workflow and the exact format users paste.
  - _Acceptance:_ one call ingests a full 60-card list; returns a per-line
    report (added / ambiguous / not_found) so failures are visible.
- [ ] **`[P0]` Batch add** — At minimum, `add_cards(deck_id, [{name|card_id, qty, sideboard}])`
  if the full importer is bigger than one story.
  - _Why:_ also removes the risk of a single fat-fingered `deck_id` silently
    dropping one card mid-batch (happened this session).

## P1 — Card resolution

- [ ] **`[P1]` Resolve by set + collector number** — Let add/import accept
  `(set_code, collector_number)`.
  - _Why:_ Lists carry `(FIN) 115`, but tools only take name/`card_id`. This
    mismatch caused every disambiguation hiccup and made basics resolve to
    arbitrary printings (every `Mountain` became a *The Hobbit* Mountain).
- [ ] **`[P1]` Deprioritize non-playable printings in name resolution** —
  Art-series (`atdm` / `afin`) `Card // Card` entries return as co-equal matches
  and force a `card_id` round-trip.
  - _Evidence:_ Sephiroth, Scavenger Regent, Twinmaw/Whirlwing/Stormshriek
    Stormbrood, Bloomvine Regent all needed manual rescue.
  - _Acceptance:_ exact-name match prefers the real playable printing; art-series
    only surfaces when nothing else matches.
- [ ] **`[P1]` Include power/toughness in card summaries** — `lookup_card_by_name`
  and `search_cards` omit P/T.
  - _Why:_ couldn't cite creature bodies when recommending cards (a basic need
    for a deckbuilding tool).
- [ ] **`[P2]` Consistent basic-land resolution** — `lookup_card_by_name`
  returns a single `found` for `Mountain` but `ambiguous` for `Sephiroth`;
  make the behavior predictable/documented.

## P1 — Deck editing primitives

- [ ] **`[P1]` `set_card_quantity(deck_id, card, qty)`** — Today changing a count
  means delete-the-whole-entry + re-add.
- [ ] **`[P1]` Quantity param on `remove_card_from_deck`** — It currently removes
  the entire entry; can't trim "4 Swamp → 3".
- [ ] **`[P2]` `update_deck` / rename** — Name/format/strategy/tags are fixed at
  creation; renaming requires delete + recreate.

## P1 — Analysis quality

- [ ] **`[P1]` `detect_synergies`: DFC-aware parsing** — It invented `"//"` and
  `"Sorcery"` *creature tribes* by parsing `Disruptive Stormbrood // Petty Revenge`
  type lines literally. Strip/normalize back-face and non-creature type lines.
- [ ] **`[P1]` `detect_synergies`: mechanic-level recognition** — It rated the
  Mardu deck "moderate / 2 outlets" while missing that **Mobilize is a recurring
  sacrifice engine**. Detect interactions (sacrifice fodder, counters-matter,
  death triggers), not just creature types + keywords.
- [ ] **`[P1]` `analyze_mana_curve`: modal/DFC-aware** — Dragons were counted at
  their 5–6 front-face CMC, ignoring the cheap `// Omen` backs, overstating
  "top-heavy." Account for the flexible cheaper mode for MDFC / Omen / Adventure.

## P2 — Data & reporting

- [ ] **`[P2]` Distinguish data-coverage gaps from legality failures** —
  Temple of Silence reports "not available on arena" because the DB only has a
  non-Arena printing, even though it's a real Arena card. A data gap is
  surfacing as a legality verdict; flag it as such in the report.
- [ ] **`[P2]` Card data coverage audit** — Backfill missing Arena printings
  (e.g. Temple of Silence) so availability checks are trustworthy.

---

## Known recurring gotchas (reference for future sessions)

- **Art-series collisions:** names in sets with art series (`atdm`, `afin`)
  return `ambiguous`; re-call `add_card_to_deck` with the real printing's
  `card_id` (the playable `// Omen` or single-faced card, not `Card // Card`).
- **Temple of Silence** has no Arena-available printing in the DB — `validate`
  with `games:["arena"]` will always flag it; it is not a deckbuilding error.
- **Basics** resolve by name to an arbitrary printing (currently *The Hobbit*);
  fine functionally, but not the listed set.
