"""Per-format frozen scoring constants: the ``FormatProfile`` data bags (AD-3, FR4).

One passive, typed, frozen, versioned constants bag per supported format — no scattered magic
numbers, no per-format strategy classes. The scorer (Stories 5.3-5.9) *reads and branches on*
a profile; a profile never scores anything and holds no behavior.

**The AD-3 contract:**

- Values are in-repo Python constants (never an external JSON/YAML data file) and every
  container field is immutable. The module performs no I/O, no clock, no network, and no DB
  access — importable by the pure deterministic core (AD-2).
- **Bump rule:** ANY value change in a profile requires bumping that profile's
  ``format_profile_version`` in the same edit. The version flows into ``data_vintage`` (AD-7)
  and is part of the byte-identical diff surface (AD-8) — a silent value change with an
  unchanged version invalidates every cached diff. Versions are monotonic per format
  (``commander-v1`` → ``commander-v2`` → …).
- Profiles carry **no data versions** — no Game-Changer-list version, no combo-snapshot
  version. That vintage belongs to the imported snapshots (AD-7); carrying it here would let
  the profile lie about what data was actually used.

**Provisional values — Story 5.9 owns tuning.** The initial weights and win-turn bands below
are hand-picked, documented starting points (deck-assess research / addendum §C). Story 5.9
hand-tunes them against the calibration benchmark (NFR8): edit the value, bump the profile's
version, re-run the benchmark. Tests verify shape and invariants only, never exact numbers.
"""

from dataclasses import dataclass
from typing import Final, Literal

#: The AD-7 closed 7-dimension key set, in the AC/spine listing order (the one canonical home —
#: Story 5.7's vector and 5.8's aggregate import it from here so the key set can never fork).
DIMENSIONS: Final[tuple[str, ...]] = (
    "speed",
    "consistency",
    "resilience",
    "interaction",
    "mana_efficiency",
    "card_advantage",
    "combo_potential",
)


@dataclass(frozen=True, slots=True)
class DimensionWeights:
    """Aggregate weights over the closed dimension set (AD-7). Sum to 1.0.

    Exactly one ``float`` field per entry in :data:`DIMENSIONS` — mypy makes a missing or
    extra dimension a type error rather than a runtime surprise in Story 5.8's aggregate.

    Attributes:
        speed: Weight of the expected-win-turn dimension.
        consistency: Weight of the draw/redundancy consistency dimension.
        resilience: Weight of the protection/recursion resilience dimension.
        interaction: Weight of the removal/counter interaction dimension.
        mana_efficiency: Weight of the mana-base/curve efficiency dimension.
        card_advantage: Weight of the card-advantage engine dimension.
        combo_potential: Weight of the combo-line potential dimension.
    """

    speed: float
    consistency: float
    resilience: float
    interaction: float
    mana_efficiency: float
    card_advantage: float
    combo_potential: float


@dataclass(frozen=True, slots=True)
class FormatProfile:
    """One format's frozen scoring constants — a passive data bag, no behavior (AD-3).

    Per-dimension mapping parameters (the signal→0-100 curve slots, NFR8) currently comprise
    ``win_turn_band`` (the ``speed`` curve's anchor) and ``weights`` — the only parameters yet
    defensible from research. Stories 5.3-5.8 extend this shape *additively* as real curves
    land (an additive field on a frozen dataclass is cheap by design); every such edit bumps
    ``format_profile_version``.

    Attributes:
        format_profile_version: Monotonic per-format version string (FR4). Bumped on ANY
            value change in this profile; emitted in ``data_vintage`` (AD-7).
        rubric: Scoring-rubric selector (FR18/FR20 fork): ``"brackets"`` scores against the
            Commander Brackets rubric; ``"heuristic_only"`` rides the heuristic-only fork.
        win_turn_band: Inclusive expected-win-turn band ``(lo, hi)``, ``lo <= hi`` — the
            ``speed`` dimension's mapping anchor (Story 5.7).
        weights: Aggregate weights over the closed 7-dimension set; sum to 1.0 (Story 5.8).
        combos_enabled: Whether combo provisioning runs for this format (Epic 7 branches on
            this; Story 4.2 context).
        multiplayer_variance_caveat: Whether the edge emits the fixed multiplayer-variance
            ``summary`` caveat (AD-6). Never a confidence reason.
    """

    format_profile_version: str
    rubric: Literal["brackets", "heuristic_only"]
    win_turn_band: tuple[int, int]
    weights: DimensionWeights
    combos_enabled: bool
    multiplayer_variance_caveat: bool


#: Commander (multiplayer, Bracket-rubric) profile. Provisional values — 5.9 owns tuning.
COMMANDER_PROFILE: Final[FormatProfile] = FormatProfile(
    format_profile_version="commander-v1",
    rubric="brackets",  # Commander scores against the Brackets rubric (FR18).
    # Casual-Commander games are typically decided around turns 7-10 (deck-assess §1 format
    # research); cEDH candidacy (much faster wins) is flagged separately in 5.7.
    win_turn_band=(7, 10),
    # Provisional spread: multiplayer Commander rewards staying power — consistency,
    # resilience, card advantage, and combo potential over raw speed (deck-assess §7.2
    # hand-tuned starting point). Sum = 1.0; Story 5.9 owns tuning (edit → bump → re-benchmark).
    weights=DimensionWeights(
        speed=0.10,
        consistency=0.20,
        resilience=0.15,
        interaction=0.15,
        mana_efficiency=0.10,
        card_advantage=0.15,
        combo_potential=0.15,
    ),
    combos_enabled=True,  # Spellbook combo data is Commander-centric; core combo format.
    multiplayer_variance_caveat=True,  # Multiplayer politics/variance caveat in summary (AD-6).
)

#: Standard (1v1, heuristic-only) profile. Provisional values — 5.9 owns tuning.
STANDARD_PROFILE: Final[FormatProfile] = FormatProfile(
    format_profile_version="standard-v1",
    rubric="heuristic_only",  # Standard has no Brackets; heuristic-only fork (FR20).
    # 1v1 Standard games are typically decided around turns 5-8 (deck-assess §1 format
    # research) — faster than multiplayer Commander.
    win_turn_band=(5, 8),
    # Provisional spread: FR20 emphasizes curve/interaction/Karsten-60 for Standard — speed,
    # interaction, and mana efficiency lead; combo potential is a minor signal in modern
    # Standard. Sum = 1.0; Story 5.9 owns tuning (edit → bump → re-benchmark).
    weights=DimensionWeights(
        speed=0.20,
        consistency=0.15,
        resilience=0.10,
        interaction=0.20,
        mana_efficiency=0.20,
        card_advantage=0.10,
        combo_potential=0.05,
    ),
    # FR20's heuristic inputs literally include combos; the Commander-centric Spellbook
    # snapshot will match few/no Standard combos, which is fine and unpenalized. If Epic 7
    # finds Standard combo provisioning pathological, flipping this is a data edit + version
    # bump — exactly the AD-3 workflow.
    combos_enabled=True,
    multiplayer_variance_caveat=False,  # 1v1 format — no multiplayer-variance caveat.
)
