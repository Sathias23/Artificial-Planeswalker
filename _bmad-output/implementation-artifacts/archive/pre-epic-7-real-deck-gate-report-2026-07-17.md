# Pre-Epic-7 Real-Deck Gate Report (G-R2)

Real-deck sanity pass over every saved deck in the live central DB through the exact Epic 7 path (`get_deck_with_cards` → `get_variants_for_names` → pure `score()`). Epic-6 retro action item 1; closes epic-5 action item 5. Each divergence from human judgment is a **named Epic 7 calibration input** — a divergence is data, not automatically a bug.

- **Run date:** 2026-07-17
- **Baseline commit:** `92e9307`
- **Decks:** enumerated 20, scored 20, skipped: none

## Snapshot metadata (data vintage)

| Field | Value |
|---|---|
| imported_at | 2026-07-16T09:07:00.910971+00:00 |
| export_timestamp | 2026-07-16T07:28:23.230742+00:00 |
| export_version | 5.6.0 |
| variant_count | 94962 |

Per-deck data vintage: each detail section carries the deck's own `updated_at` timestamp.

## Summary

| Deck | Format | Profile | Commanders | Score | Tier | Bracket | cEDH | Combos matched | Flags |
|---|---|---|---|---|---|---|---|---|---|
| Abzan Dragons (`4f9d6f52`) | standard | STANDARD_PROFILE | — | 59 | Tuned | — | no | 6 | — |
| Astonishing Ant-Man — Simic Counters Tempo (`4d0a55fb`) | standard | STANDARD_PROFILE | — | 48 | Tuned | — | no | 1 | — |
| Baron Zemo — Villain Connive (`dcdfa284`) | standard | STANDARD_PROFILE | — | 59 | Tuned | — | no | 0 | — |
| Bulk Import Tool Test - Naya Dinosaurs - 2026-07-10 (`94494472`) | standard | STANDARD_PROFILE | — | 36 | Focused | — | no | 0 | — |
| Graveyard Gravy (`baafd58b`, 3-card stub) | standard | STANDARD_PROFILE | — | 2 | Unfocused | — | no | 0 | incomplete-stub |
| Graveyard Gravy (`e7870022`, 60-card) | standard | STANDARD_PROFILE | — | 53 | Tuned | — | no | 3 | — |
| Iron Man, Modern Marvel — reminder (`5cd42e7f`) | historic | STANDARD_PROFILE | — | 20 | Unfocused | — | no | 0 | incomplete-stub |
| Kotis Saboteur Tempo - Standard Draft (`a380ca25`) | standard | STANDARD_PROFILE | — | 37 | Focused | — | no | 0 | — |
| Kotis, the Fangkeeper — 100-card Brawl (`f02e1faa`) | brawl | COMMANDER_PROFILE (provisional) | Kotis, the Fangkeeper | 75 | High-Power | 2 | no | 12 | provisional-profile, override-commander |
| Kotis, the Fangkeeper — Standard Brawl (`a839fc0b`) | standardbrawl | COMMANDER_PROFILE (provisional) | Kotis, the Fangkeeper | 61 | High-Power | 2 | no | 3 | provisional-profile, override-commander |
| Mardu Midrange (`8db441c0`) | standard | STANDARD_PROFILE | — | 58 | Tuned | — | no | 0 | — |
| Mardu Midrange v2 (`076ac3ed`) | standard | STANDARD_PROFILE | — | 56 | Tuned | — | no | 0 | — |
| MSH — Assemble! — Hexproof Hero Anthem Swarm (`7e86ad5d`) | standard | STANDARD_PROFILE | — | 60 | Tuned | — | no | 1 | — |
| MSH — Namor's Tide — Izzet Merfolk Spellslinger Tempo (`d1c18722`) | standard | STANDARD_PROFILE | — | 71 | High-Power | — | no | 0 | — |
| MSH — Snakebite Edict — Golgari Deathtouch Villain Aristocrats (`4e6b5959`) | standard | STANDARD_PROFILE | — | 66 | High-Power | — | no | 1 | — |
| MSH — The Mad Titan's Gauntlet — Five-Color Power-Up Snap (`c9f5b355`) | standard | STANDARD_PROFILE | — | 69 | High-Power | — | no | 0 | — |
| MSH — Ultron's Forge — Artifact Copy Combo Engine (`e684ceb1`) | standard | STANDARD_PROFILE | — | 68 | High-Power | — | no | 1 | — |
| Prismatic Dragon (`a6ec5c97`) | standard | STANDARD_PROFILE | — | 46 | Tuned | — | no | 5 | near-complete |
| Sephiroth, Fabled SOLDIER — Standard Brawl (`d2ec429d`) | standardbrawl | COMMANDER_PROFILE (provisional) | Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel | 58 | Tuned | 4 | no | 39 | incomplete-stub, provisional-profile, override-commander, dfc-override |
| Skynet (`99f55404`) | standard | STANDARD_PROFILE | — | 68 | High-Power | — | no | 8 | — |

Flag tokens: `incomplete-stub` = below format minimum, outputs not meaningful; `near-complete` = within 2 cards of the minimum, outputs directionally meaningful; `oversize` = above format maximum; `provisional-profile` = brawl-family → COMMANDER_PROFILE mapping is provisional; `unmapped-format-fallback` = format not in the explicit map, STANDARD_PROFILE assumed; `override-commander` = commander from the harness override map; `dfc-override` = override name resolved to a stored DFC full name via name_keys; `gc-unknown` = game_changer unknown_count > 0; `scoring-error` = score() raised (captured in the detail section).

## Per-deck detail

<details><summary><b>Abzan Dragons</b> (<code>4f9d6f52</code>)</summary>

- **Deck id:** `4f9d6f52-3db6-4281-b1b9-ad3400a54255`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Abzan (W/B/G) Dragonstorm midrange. Ramp/fix via Dragonstorm Globe, Herd Heirloom, Maelstrom of the Spirit Dragon and Temples into efficient TDM dragons (Bloomvine Regent, Scavenger Regent, Armament Dragon). Up the Beanstalk + the dragons' high MV draws cards; Betor, Kin to All and a go-tall toughness theme close games. Assassin's Trophy + Clarion Conqueror as interaction. · lands (mainboard): 24 · deck updated_at: 2026-06-21T07:43:50.515002
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 259

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 42 |
| consistency | 47 |
| resilience | 72 |
| interaction | 75 |
| mana_efficiency | 43 |
| card_advantage | 80 |
| combo_potential | 100 |

- **for_format_score:** 59
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** (none)
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (6):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 1642-6439 | almost_included | SPICY | Betor, Kin to All, Warlock Class |
| 2607-6439 | almost_included | SPICY | Archfiend of Despair, Betor, Kin to All |
| 3263-7000 | almost_included | RUTHLESS | Clarion Conqueror, Mycosynth Lattice |
| 3373-6439 | almost_included | SPICY | Astarion, the Decadent, Betor, Kin to All |
| 4475-6439 | almost_included | SPICY | Betor, Kin to All, Wound Reflection |
| 5342-6439 | almost_included | SPICY | Betor, Kin to All, Bloodletter of Aclazotz |

</details>

<details><summary><b>Astonishing Ant-Man — Simic Counters Tempo</b> (<code>4d0a55fb</code>)</summary>

- **Deck id:** `4d0a55fb-9623-445a-8276-cd670197e641`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Simic (GU) counters-tempo built around The Astonishing Ant-Man: chain cheap card draw to pile +1/+1 counters on Ant-Man, then win with a giant trampler or cash counters into a wide Insect swarm. Draw-payoff engine (Terrasymbiosis, Stocking the Pantry, Dictate of Kruphix). · lands (mainboard): 24 · deck updated_at: 2026-06-29T11:24:29.771905
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 62

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 61 |
| consistency | 45 |
| resilience | 30 |
| interaction | 0 |
| mana_efficiency | 85 |
| card_advantage | 80 |
| combo_potential | 25 |

- **for_format_score:** 48
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** interaction_below_baseline, wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (1):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 648-6743 | almost_included | RUTHLESS | Body of Research, Terrasymbiosis |

</details>

<details><summary><b>Baron Zemo — Villain Connive</b> (<code>dcdfa284</code>)</summary>

- **Deck id:** `dcdfa284-ac20-4b53-8923-9a670a4420f5`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Mono-black Villain midrange built around Baron Helmut Zemo. Cast cheap black removal/Villains from hand -> Zemo connives -> the connive draw is your 2nd card each turn -> triggers Madame Masque, Construct a Cosmic Cube, Roxxon Brutes, Raven Eagle. One action = removal + card + grow + token/drain. Baron Strucker cheapens Villains and adds connive; Crossbones turns Villain ETBs into reach. M.O.D.O.K. (-1/-1 anthem) and Doctor Doom close. Boast is pure-upside late-game reach, not the plan. · lands (mainboard): 24 · deck updated_at: 2026-06-25T07:08:56.718473
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 22

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 49 |
| consistency | 19 |
| resilience | 39 |
| interaction | 100 |
| mana_efficiency | 100 |
| card_advantage | 27 |
| combo_potential | 0 |

- **for_format_score:** 59
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** card_draw_below_baseline, wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>Bulk Import Tool Test - Naya Dinosaurs - 2026-07-10</b> (<code>94494472</code>)</summary>

- **Deck id:** `94494472-5c16-4925-a746-9180864dce4f`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: (none) · lands (mainboard): 24 · deck updated_at: 2026-07-10T02:29:58.821370
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 45

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 57 |
| consistency | 37 |
| resilience | 13 |
| interaction | 51 |
| mana_efficiency | 37 |
| card_advantage | 6 |
| combo_potential | 0 |

- **for_format_score:** 36
- **tier:** Focused
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** card_draw_below_baseline, interaction_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>Graveyard Gravy</b> (<code>baafd58b</code>, 3-card stub)</summary>

- **Deck id:** `baafd58b-fc6b-49b3-998d-dc9f549ade17`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Golgari (B/G) graveyard recursion. Core engine pieces: Forum Necroscribe (repeatable reanimation off creature-targeted spells), Overlord of the Balemurk (repeatable self-mill + recursion via Impending/attack trigger), and Aatchik, Emerald Radian (graveyard-scaling token payoff). Still being tuned card-by-card. · lands (mainboard): 0 · deck updated_at: 2026-07-01T08:41:46.885422
- **Mainboard cards (sum of quantities):** 3
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 5
- **FLAG:** incomplete — 3 mainboard cards vs format minimum 60; outputs not meaningful.

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 12 |
| consistency | 0 |
| resilience | 0 |
| interaction | 0 |
| mana_efficiency | 0 |
| card_advantage | 0 |
| combo_potential | 0 |

- **for_format_score:** 2
- **tier:** Unfocused
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** card_draw_below_baseline, interaction_below_baseline, wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>Graveyard Gravy</b> (<code>e7870022</code>, 60-card)</summary>

- **Deck id:** `e7870022-eaa1-48c1-9cfb-b85cfed8b22f`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Orzhov (W/B) graveyard recursion: fill the yard with surveil/mill creatures, grind value with Smile at Death loops and Sidisi's sacrifice ladder, reanimate Valgavoth or Overlord of the Balemurk as the finisher. · lands (mainboard): 24 · deck updated_at: 2026-07-02T10:18:40.846298
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 212

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 48 |
| consistency | 27 |
| resilience | 66 |
| interaction | 46 |
| mana_efficiency | 79 |
| card_advantage | 40 |
| combo_potential | 75 |

- **for_format_score:** 53
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** card_draw_below_baseline, interaction_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (3):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 444-5796 | almost_included | SPICY | Drogskol Reaver, Starving Revenant |
| 5796-6033 | almost_included | SPICY | Marina Vendrell's Grimoire, Starving Revenant |
| 5796-6574 | almost_included | SPICY | Kefka, Court Mage // Kefka, Ruler of Ruin, Starving Revenant |

</details>

<details><summary><b>Iron Man, Modern Marvel — reminder</b> (<code>5cd42e7f</code>)</summary>

- **Deck id:** `5cd42e7f-ffbb-4b4c-8abf-ceab55d3150d`
- **Format:** historic → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Keepsake. A single Iron Man, Modern Marvel (msc/830, Historic-only) held as a reminder from the day Skynet hit Gold — the card that turned out to be a Commander-set card, not Standard-legal. Not a playable list; a memento. · lands (mainboard): 0 · deck updated_at: 2026-06-29T10:21:52.286986
- **Mainboard cards (sum of quantities):** 1
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 0
- **FLAG:** incomplete — 1 mainboard cards vs format minimum 60; outputs not meaningful.
- **Zero-candidate probe:** verified genuinely combo-inert pool: 0 of 1 distinct mainboard names appear as any snapshot piece key (exact name_keys check), and LIKE near-miss probes on 1 sampled non-basic names (Iron Man, Modern Marvel) return no candidate keys — NOT a normalization failure.

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 36 |
| consistency | 60 |
| resilience | 21 |
| interaction | 0 |
| mana_efficiency | 0 |
| card_advantage | 13 |
| combo_potential | 0 |

- **for_format_score:** 20
- **tier:** Unfocused
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** card_draw_below_baseline, interaction_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>Kotis Saboteur Tempo - Standard Draft</b> (<code>a380ca25</code>)</summary>

- **Deck id:** `a380ca25-44ea-4e38-b135-a2d88eaf9f66`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Sultai saboteur tempo based on Kotis, the Fangkeeper: use evasive creatures, equipment, and combat-damage triggers to steal/cast opposing cards and snowball value. · lands (mainboard): 24 · deck updated_at: 2026-07-06T09:52:31.940135
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 0
- **Zero-candidate probe:** verified genuinely combo-inert pool: 0 of 23 distinct mainboard names appear as any snapshot piece key (exact name_keys check), and LIKE near-miss probes on 5 sampled non-basic names (Black Widow, Super Spy; Buster Sword; Dive Down; Enduring Curiosity; Enter the Enigma) return no candidate keys — NOT a normalization failure.

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 59 |
| consistency | 43 |
| resilience | 43 |
| interaction | 0 |
| mana_efficiency | 33 |
| card_advantage | 80 |
| combo_potential | 0 |

- **for_format_score:** 37
- **tier:** Focused
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** interaction_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>Kotis, the Fangkeeper — 100-card Brawl</b> (<code>f02e1faa</code>)</summary>

- **Deck id:** `f02e1faa-6023-494e-9027-7c19b931288e`
- **Format:** brawl → profile COMMANDER_PROFILE (provisional)
- **Identity:** colors C · strategy: Sultai saboteur/equipment: connect with Kotis and a crew of combat-damage-trigger creatures, steal-cast off opponents' libraries. Historic-pool port of the Standard Brawl build. · lands (mainboard): 40 · deck updated_at: 2026-07-05T06:12:57.910554
- **Mainboard cards (sum of quantities):** 100
- **Commanders:** Kotis, the Fangkeeper (source: override, zone: mainboard)
- **Candidate combo variants fetched (over-fetch scale):** 252

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 63 |
| consistency | 46 |
| resilience | 66 |
| interaction | 100 |
| mana_efficiency | 0 |
| card_advantage | 80 |
| combo_potential | 100 |

- **for_format_score:** 75
- **tier:** High-Power
- **bracket_floor:** 2
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** ramp_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (12):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 1089-2353 | almost_included | SPICY | Curiosity, Niv-Mizzet, Parun |
| 1089-4703 | almost_included | SPICY | Brallin, Skyshark Rider, Curiosity |
| 1089-4869 | almost_included | SPICY | Curiosity, Glint-Horn Buccaneer |
| 1089-4971 | almost_included | SPICY | Curiosity, Niv-Mizzet, the Firemind |
| 1089-6428 | almost_included | SPICY | Curiosity, Magmakin Artillerist |
| 618-7624 | almost_included | RUTHLESS | Kiki-Jiki, Mirror Breaker, Sea-Dasher Octopus |
| 6285-6746 | almost_included | CASUAL | Riverchurn Monument, Singularity Rupture |
| 6562-6648 | almost_included | SPICY | Jaws of Defeat, Overkill |
| 900-2011 | almost_included | SPICY | Najeela, the Blade-Blossom, Sword of Feast and Famine |
| 900-3398 | almost_included | SPICY | Hellkite Charger, Sword of Feast and Famine |
| 900-3750 | almost_included | SPICY | Aggravated Assault, Sword of Feast and Famine |
| 95-6746 | almost_included | SPICY | Bruvac the Grandiloquent, Singularity Rupture |

</details>

<details><summary><b>Kotis, the Fangkeeper — Standard Brawl</b> (<code>a839fc0b</code>)</summary>

- **Deck id:** `a839fc0b-e787-4f01-a640-23a95b79ecbd`
- **Format:** standardbrawl → profile COMMANDER_PROFILE (provisional)
- **Identity:** colors C · strategy: Sultai saboteur/steal: make Kotis unblockable or evasive with equipment (Iron Man Armor, Cryptic Coat), stack double strike for extra triggers, cast the opponent's deck for free. Backed by one-sided wipes (indestructible commander), exile removal, and saboteur redundancy (Black Widow, Tinybones, April). · lands (mainboard): 24 · deck updated_at: 2026-07-04T23:15:21.487625
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** Kotis, the Fangkeeper (source: override, zone: mainboard)
- **Candidate combo variants fetched (over-fetch scale):** 19

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 59 |
| consistency | 41 |
| resilience | 51 |
| interaction | 77 |
| mana_efficiency | 0 |
| card_advantage | 72 |
| combo_potential | 75 |

- **for_format_score:** 61
- **tier:** High-Power
- **bracket_floor:** 2
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** ramp_below_baseline, wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (3):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 6285-6746 | almost_included | CASUAL | Riverchurn Monument, Singularity Rupture |
| 6562-6648 | almost_included | SPICY | Jaws of Defeat, Overkill |
| 95-6746 | almost_included | SPICY | Bruvac the Grandiloquent, Singularity Rupture |

</details>

<details><summary><b>Mardu Midrange</b> (<code>8db441c0</code>)</summary>

- **Deck id:** `8db441c0-9158-468e-974d-6da90813b2fb`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Mardu (W/B/R) midrange built around Sephiroth, Fabled SOLDIER with sacrifice/aristocrats support (Feed the Cycle, Scavenger's Talent, Corrupted Conviction) and aggressive threats (Voice of Victory, Stadium Headliner, Avenger of the Fallen). · lands (mainboard): 24 · deck updated_at: 2026-06-21T07:10:06.425367
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 232

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 61 |
| consistency | 38 |
| resilience | 45 |
| interaction | 55 |
| mana_efficiency | 82 |
| card_advantage | 80 |
| combo_potential | 0 |

- **for_format_score:** 58
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** interaction_below_baseline, wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>Mardu Midrange v2</b> (<code>076ac3ed</code>)</summary>

- **Deck id:** `076ac3ed-b59a-431f-b286-af7ed2c8704e`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Mardu (W/B/R) aristocrats/mobilize v2. Upgrade pass over the v1 Sephiroth build: cut clunky Eaten Alive ×2, the narrow 1-of Vampire Gourmand, and the singleton Hardened Tactician; added Come Back Wrong ×2 (removal that steals+sacs their creature for your death payoffs), Fanatical Offering (instant sac + draw 2 + Map), and Dragon Fodder (cheap token fodder). Core unchanged: Sephiroth, Avenger of the Fallen, Voice of Victory, Bone-Cairn Butcher, Stadium Headliner + death-trigger payoffs (Vengeful Bloodwitch, Syr Vondam, Judge Magister Gabranth, Treacherous Greed). · lands (mainboard): 24 · deck updated_at: 2026-06-24T22:07:15.327738
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 192

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 60 |
| consistency | 37 |
| resilience | 45 |
| interaction | 50 |
| mana_efficiency | 82 |
| card_advantage | 80 |
| combo_potential | 0 |

- **for_format_score:** 56
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** interaction_below_baseline, wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>MSH — Assemble! — Hexproof Hero Anthem Swarm</b> (<code>7e86ad5d</code>)</summary>

- **Deck id:** `7e86ad5d-1ff9-463e-ad24-8ea3887c79c6`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Mono-white go-wide Hero tribal aggro: flood the board with cheap Heroes and Hero tokens, anthem with Origin/Avengers Assemble!, and use Captain America's shield counter to give the whole team hexproof so the buffs can't be removed. · lands (mainboard): 22 · deck updated_at: 2026-06-24T08:26:00.205090
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 1

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 54 |
| consistency | 41 |
| resilience | 73 |
| interaction | 33 |
| mana_efficiency | 100 |
| card_advantage | 80 |
| combo_potential | 25 |

- **for_format_score:** 60
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** interaction_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (1):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 3587-7263 | almost_included | SPICY | Boros Reckoner, Take Up the Shield |

</details>

<details><summary><b>MSH — Namor&#x27;s Tide — Izzet Merfolk Spellslinger Tempo</b> (<code>d1c18722</code>)</summary>

- **Deck id:** `d1c18722-9698-479d-bedf-6554299d4a02`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: UR tempo: chain cheap blue noncreature spells so Namor floods Merfolk tokens and grows into an evasive flyer, backed by Loki card draw and stacked cost reduction (Ironheart/Scarlet Witch) to land Vision Quest and a Multiversal Incursion finisher. · lands (mainboard): 23 · deck updated_at: 2026-06-24T08:26:11.630881
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 59

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 61 |
| consistency | 47 |
| resilience | 68 |
| interaction | 100 |
| mana_efficiency | 87 |
| card_advantage | 80 |
| combo_potential | 0 |

- **for_format_score:** 71
- **tier:** High-Power
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** (none)
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>MSH — Snakebite Edict — Golgari Deathtouch Villain Aristocrats</b> (<code>4e6b5959</code>)</summary>

- **Deck id:** `4e6b5959-13bf-48eb-86fd-7cd9c5659f8c`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: BG deathtouch-edict attrition: cheap deathtouchers + The Serpent Society turn every trade into an opponent-sacrifices edict, while Villain ETBs drain via Doom Reigns Supreme and Thunderbolts Conspiracy recurs the core; close with Doctor Doom or Galactus. · lands (mainboard): 23 · deck updated_at: 2026-06-24T08:25:44.293156
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 102

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 65 |
| consistency | 32 |
| resilience | 47 |
| interaction | 91 |
| mana_efficiency | 97 |
| card_advantage | 53 |
| combo_potential | 8 |

- **for_format_score:** 66
- **tier:** High-Power
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** wincon_missing
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (1):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 6507-7705 | almost_included | SPICY | Constant Mists, Mole Man, Moloid Master |

</details>

<details><summary><b>MSH — The Mad Titan&#x27;s Gauntlet — Five-Color Power-Up Snap</b> (<code>c9f5b355</code>)</summary>

- **Deck id:** `c9f5b355-96d9-4b25-a5b1-85ca0a6b971e`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Five-color WUBRG ramp-control: fix into a rainbow base, stabilize with Thanos's one-sided parity wipe, grind with Nick Fury digs and Captain Marvel, and close with Kang's extra turn or a maxed Super-Adaptoid. · lands (mainboard): 24 · deck updated_at: 2026-06-24T08:26:56.985773
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 38

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 55 |
| consistency | 42 |
| resilience | 67 |
| interaction | 90 |
| mana_efficiency | 97 |
| card_advantage | 80 |
| combo_potential | 0 |

- **for_format_score:** 69
- **tier:** High-Power
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** (none)
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos:** none

</details>

<details><summary><b>MSH — Ultron&#x27;s Forge — Artifact Copy Combo Engine</b> (<code>e684ceb1</code>)</summary>

- **Deck id:** `e684ceb1-110b-41cf-9f39-d84bcea3f70e`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Grixis artifact value-combo: flood cheap ETB artifacts, install Ultron to fork each into a copy/body, double key triggers with Scientist Supreme, and close with Vision Quest finishers, Cosmic Cube free-casts, and Multiversal Incursion board-doubling discounted by Ironheart's improvise. · lands (mainboard): 23 · deck updated_at: 2026-06-24T08:25:35.936902
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 5

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 57 |
| consistency | 43 |
| resilience | 67 |
| interaction | 100 |
| mana_efficiency | 70 |
| card_advantage | 80 |
| combo_potential | 25 |

- **for_format_score:** 68
- **tier:** High-Power
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** (none)
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (1):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 2084-7694 | almost_included | CASUAL | Mirror-Mad Phantasm, Multiversal Incursion |

</details>

<details><summary><b>Prismatic Dragon</b> (<code>a6ec5c97</code>)</summary>

- **Deck id:** `a6ec5c97-cda4-4694-ad88-7f26ac60a13d`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Five-color "Prismatic" Dragons. Temples + Verges + Dragonstorm Globe fix all five colors to cast the Stormbrood dragon cycle and the Regent cycle, with payoffs like Ramos, Dragon Engine; Betor, Kin to All; Armament Dragon; and two Sarkhans. Maelstrom of the Spirit Dragon and Call the Spirit Dragons as top-end. · lands (mainboard): 24 · deck updated_at: 2026-06-21T07:39:03.825286
- **Mainboard cards (sum of quantities):** 59
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 105
- **FLAG:** near-complete (59/60) — outputs directionally meaningful.

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 29 |
| consistency | 46 |
| resilience | 79 |
| interaction | 71 |
| mana_efficiency | 0 |
| card_advantage | 59 |
| combo_potential | 100 |

- **for_format_score:** 46
- **tier:** Tuned
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** (none)
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (5):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 1642-6439 | almost_included | SPICY | Betor, Kin to All, Warlock Class |
| 2607-6439 | almost_included | SPICY | Archfiend of Despair, Betor, Kin to All |
| 3373-6439 | almost_included | SPICY | Astarion, the Decadent, Betor, Kin to All |
| 4475-6439 | almost_included | SPICY | Betor, Kin to All, Wound Reflection |
| 5342-6439 | almost_included | SPICY | Betor, Kin to All, Bloodletter of Aclazotz |

</details>

<details><summary><b>Sephiroth, Fabled SOLDIER — Standard Brawl</b> (<code>d2ec429d</code>)</summary>

- **Deck id:** `d2ec429d-c94d-467a-ad70-804d6b021f55`
- **Format:** standardbrawl → profile COMMANDER_PROFILE (provisional)
- **Identity:** colors C · strategy: Mono-black aristocrats port of the Mardu Midrange deck with Sephiroth, Fabled SOLDIER as commander. Sephiroth's color identity forces black-only, so the plan leans fully into deaths-matter: cheap dies-for-value fodder (Greedy Freebooter, Infestation Sage, Agents of HYDRA), steady token engines (Lord Skitter, Bitterbloom Bearer, Rat King), stacked drain payoffs (Vengeful Bloodwitch, Al Bhed Salvagers, Susurian Voidborn, Venerated Stormsinger), and sac-cost value spells (Worthy Cost, Deadly Precision, Fanatical Offering, Pitiless Carnage). Sephiroth draws a card per sac on entry/attack, drains on every creature death, and transforms at 4 deaths in a turn; Bloodletter of Aclazotz and Bloodthirsty Conqueror double the drains, Exsanguinate and Season of Loss close. · lands (mainboard): 0 · deck updated_at: 2026-07-07T09:33:07.334463
- **Mainboard cards (sum of quantities):** 20
- **Commanders:** Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel (source: override, zone: mainboard)
- **Candidate combo variants fetched (over-fetch scale):** 595
- **FLAG:** incomplete — 20 mainboard cards vs format minimum 60; outputs not meaningful.
- **Note:** override commander 'Sephiroth, Fabled SOLDIER' resolved to stored DFC name 'Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel' via name_keys front-face normalization (Epic 7 calibration input: commander storage/lookup)

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 86 |
| consistency | 45 |
| resilience | 33 |
| interaction | 0 |
| mana_efficiency | 0 |
| card_advantage | 32 |
| combo_potential | 100 |

- **for_format_score:** 58
- **tier:** Tuned
- **bracket_floor:** 4
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** card_draw_below_baseline, interaction_below_baseline, ramp_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (39):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 110-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Marauding Blight-Priest |
| 156-5342 | almost_included | ODDBALL | Bloodletter of Aclazotz, Scourge of the Skyclaves |
| 1561-5342 | almost_included | POWERFUL | Bloodletter of Aclazotz, Peer into the Abyss |
| 1612-5342 | almost_included | POWERFUL | Bloodletter of Aclazotz, Shard of the Nightbringer |
| 2129-5342 | almost_included | SPICY | Bloodletter of Aclazotz, Scytheclaw |
| 2615-5342 | almost_included | SPICY | Bloodletter of Aclazotz, Tree of Perdition |
| 2939-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Defiant Bloodlord |
| 2973-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Dina, Soul Steeper |
| 314-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Vito, Thorn of the Dusk Rose |
| 3966-5867 | almost_included | SPICY | Exquisite Blood, Starscape Cleric |
| 3966-7286 | almost_included | SPICY | Exquisite Blood, South Wind Avatar |
| 4141-5342 | almost_included | RUTHLESS | Blood Tribute, Bloodletter of Aclazotz |
| 4624-5342 | almost_included | RUTHLESS | Bloodletter of Aclazotz, Revival // Revenge |
| 4740-6191 | almost_included | SPICY | Aetherflux Reservoir, Bloodthirsty Conqueror |
| 4789-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Cliffhaven Vampire |
| 4794-5342 | almost_included | SPICY | Bloodletter of Aclazotz, Fraying Omnipotence |
| 4843-5342 | almost_included | SPICY | Bloodletter of Aclazotz, Virtus the Veiled |
| 4912-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Epicure of Blood |
| 5136-5342 | almost_included | SPICY | Bloodletter of Aclazotz, Quietus Spike |
| 5342-5377 | almost_included | SPICY | Bloodletter of Aclazotz, Ebonblade Reaper |
| 5342-5460 | almost_included | RUTHLESS | Bloodletter of Aclazotz, Rush of Dread |
| 5342-5605 | almost_included | POWERFUL | Bloodletter of Aclazotz, Torgaar, Famine Incarnate |
| 5342-5944 | almost_included | SPICY | Bloodletter of Aclazotz, Unstoppable Slasher |
| 5342-6004 | almost_included | SPICY | Bloodletter of Aclazotz, Grievous Wound |
| 5342-6109 | almost_included | SPICY | Aphelia, Viper Whisperer, Bloodletter of Aclazotz |
| 5342-6439 | almost_included | SPICY | Betor, Kin to All, Bloodletter of Aclazotz |
| 5342-6765 | almost_included | RUTHLESS | Alpharael, Stonechosen, Bloodletter of Aclazotz |
| 5342-7276 | almost_included | CASUAL | Bloodletter of Aclazotz, Dark Leo & Shredder |
| 5342-7319 | almost_included | SPICY | Bloodletter of Aclazotz, Shredder, Shadow Master |
| 5342-7450 | almost_included | ODDBALL | Bloodletter of Aclazotz, Pox Plague |
| 5755-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Enduring Tenacity |
| 5867-6191 | included | SPICY | Bloodthirsty Conqueror, Starscape Cleric |
| 6191-7286 | included | SPICY | Bloodthirsty Conqueror, South Wind Avatar |
| 6191-7416 | almost_included | SPICY | Bloodthirsty Conqueror, Professor Dellian Fel |
| 6215-6559 | almost_included | RUTHLESS | Tombstone Stairwell, Venerated Stormsinger |
| 6215-6634 | almost_included | RUTHLESS | Al Bhed Salvagers, Tombstone Stairwell |
| 6215-7286 | almost_included | RUTHLESS | South Wind Avatar, Tombstone Stairwell |
| 690-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Sanguine Bond |
| 92-6191 | almost_included | SPICY | Bloodthirsty Conqueror, Vizkopa Guildmage |

</details>

<details><summary><b>Skynet</b> (<code>99f55404</code>)</summary>

- **Deck id:** `99f55404-6111-4ed5-a9ca-780d58b633f0`
- **Format:** standard → profile STANDARD_PROFILE
- **Identity:** colors C · strategy: Azorius (W/U) Equipment voltron + clone engine. Build one elite equipped threat (Shrike Force, Emissary Escort, Tenth District Hero), then DUPLICATE it rather than going wide — Mirrormind Crown (token-trigger -> copy the equipped creature), Extravagant Replication (free upkeep copy), Impostor Syndrome (combat-damage copy), Assimilation Aegis (exile + become a copy), and Multiversal Incursion (copy the whole board) as the finisher. Quality replicated, not quantity. Chrome Dome + Super-Soldier Serum are the artifact/Equipment seeds; Get Lost and An Offer You Can't Refuse handle interaction. ~24-land W/U base. · lands (mainboard): 24 · deck updated_at: 2026-06-28T08:32:57.495835
- **Mainboard cards (sum of quantities):** 60
- **Commanders:** (none) (source: none, zone: -)
- **Candidate combo variants fetched (over-fetch scale):** 324

**7-dimension vector:**

| Dimension | Value |
|---|---|
| speed | 48 |
| consistency | 46 |
| resilience | 87 |
| interaction | 65 |
| mana_efficiency | 85 |
| card_advantage | 80 |
| combo_potential | 100 |

- **for_format_score:** 68
- **tier:** High-Power
- **bracket_floor:** None (heuristic_only)
- **cedh_candidate:** False
- **game_changers:** known_count=0, unknown_count=0, card_names: (none)
- **structural_gaps:** interaction_below_baseline
- **mass_land_denial:** False
- **extra_turn_chains:** False

**Matched combos (8):**

| spellbook_id | bucket | bracket_tag | cards |
|---|---|---|---|
| 1061-2061 | almost_included | RUTHLESS | Extravagant Replication, Timestream Navigator |
| 1530-2061 | almost_included | RUTHLESS | Extravagant Replication, Second Chance |
| 2061-2120 | almost_included | RUTHLESS | Extravagant Replication, Wanderwine Prophets |
| 2440-7282 | almost_included | PRECON_APPROPRIATE | Chrome Dome, Mana Echoes |
| 3259-6911 | almost_included | SPICY | Breath of Fury, Impostor Syndrome |
| 4295-7282 | almost_included | POWERFUL | Chrome Dome, Powerstone Shard |
| 4364-6911 | almost_included | SPICY | Aurelia, the Warleader, Impostor Syndrome |
| 578-7282 | almost_included | ODDBALL | Chrome Dome, Metalworker |

</details>

## Caveats (standing, carried into review)

- `CEDH_TUTOR_MIN=3` (`src/logic/assessment/dimensions.py`): the cEDH candidacy gate requires at least 3 tutor-classified cards.
- The FR6 tutor definition undercounts battlefield/library-exile tutors — tutor-dependent signals (consistency bonus, cEDH candidacy) are conservative.
- brawl/standardbrawl → `COMMANDER_PROFILE` is **provisional**: Epic 7 owns the real format→profile mapping; this mapping choice is itself a calibration observation.
- `DeckCard.commander` flags are absent in the live DB (all decks predate Story 6.1) — commanders came from the explicit harness override map, resolved against mainboard card names via `name_keys()` (DFC front-face aware), no name-guessing.
- `game_changers.unknown_count` is surfaced per deck; a nonzero value means the AD-4 backfill window is open for those cards.
- Decks below the format minimum are scored but flagged: `incomplete-stub` (outputs not meaningful) or `near-complete` (outputs directionally meaningful, within 2 cards of the minimum).
- A divergence from human judgment is **data** (Epic 7 calibration input), not automatically a bug.

## Cross-deck observations (calibration-input candidates)

Factual patterns across the pool — no retuning here; each is a candidate named Epic 7 calibration input.

- **Candidate calibration input — card_advantage saturation:** `card_advantage` is exactly 80 in 11 of 20 decks (Abzan Dragons (`4f9d6f52`), Astonishing Ant-Man — Simic Counters Tempo (`4d0a55fb`), Kotis Saboteur Tempo - Standard Draft (`a380ca25`), Kotis, the Fangkeeper — 100-card Brawl (`f02e1faa`), Mardu Midrange (`8db441c0`), Mardu Midrange v2 (`076ac3ed`), MSH — Assemble! — Hexproof Hero Anthem Swarm (`7e86ad5d`), MSH — Namor's Tide — Izzet Merfolk Spellslinger Tempo (`d1c18722`), MSH — The Mad Titan's Gauntlet — Five-Color Power-Up Snap (`c9f5b355`), MSH — Ultron's Forge — Artifact Copy Combo Engine (`e684ceb1`), Skynet (`99f55404`)) — a saturation/clamp pattern in the draw-density mapping.
- **Candidate calibration input — interaction pegging:** `interaction` sits at exactly 0 or 100 in 9 of 20 decks (Astonishing Ant-Man — Simic Counters Tempo (`4d0a55fb`)=0, Baron Zemo — Villain Connive (`dcdfa284`)=100, Graveyard Gravy (`baafd58b`, 3-card stub)=0, Iron Man, Modern Marvel — reminder (`5cd42e7f`)=0, Kotis Saboteur Tempo - Standard Draft (`a380ca25`)=0, Kotis, the Fangkeeper — 100-card Brawl (`f02e1faa`)=100, MSH — Namor's Tide — Izzet Merfolk Spellslinger Tempo (`d1c18722`)=100, MSH — Ultron's Forge — Artifact Copy Combo Engine (`e684ceb1`)=100, Sephiroth, Fabled SOLDIER — Standard Brawl (`d2ec429d`)=0) — the dimension rails rather than grading.
- **Observation (not a defect) — game_changers inert on this pool:** known_count=0 and unknown_count=0 across all 20 decks. The Game Changer list is Commander-centric, so the signal is plausibly inert on this Standard/Marvel-heavy pool.
- **Candidate calibration input — Brawl mana_efficiency floor:** `mana_efficiency` is 0 on every Brawl-family deck (Kotis, the Fangkeeper — 100-card Brawl (`f02e1faa`), Kotis, the Fangkeeper — Standard Brawl (`a839fc0b`), Sephiroth, Fabled SOLDIER — Standard Brawl (`d2ec429d`)) — the Commander-profile Karsten/pip mapping bottoms out on all real Brawl lists.
- **Candidate calibration input — almost_included dominance:** 78 of 80 matched combo records across all decks are `almost_included` (only 2 `included`) — combo credit is driven almost entirely by one-piece-missing variants.
- **Candidate calibration input — format-blind almost_included inflation:** Abzan Dragons combo_potential=100, Prismatic Dragon combo_potential=100: these scores are driven by Betor-anchored `almost_included` variants whose missing partners (Archfiend of Despair, Mycosynth Lattice, Wound Reflection) are NOT Standard-legal — the combo can never complete in-format, yet it pushes `combo_potential` toward the ceiling. Already logged as a product-level item in `deferred-work.md`.
- **Verified observation — zero candidate variants for Kotis Saboteur Tempo - Standard Draft (`a380ca25`):** a full 60-card deck fetched 0 candidates from a 94,962-variant snapshot; probe result: verified genuinely combo-inert pool: 0 of 23 distinct mainboard names appear as any snapshot piece key (exact name_keys check), and LIKE near-miss probes on 5 sampled non-basic names (Black Widow, Super Spy; Buster Sword; Dive Down; Enduring Curiosity; Enter the Enigma) return no candidate keys — NOT a normalization failure.
- Stub decks with zero candidates (Iron Man, Modern Marvel — reminder (`5cd42e7f`)) were probed the same way; see their detail sections.

## Review sheet (Sathias)

> **Gate ruling (Sathias, 2026-07-17):** all 20 decks accepted as plausible wholesale — no blocking
> divergences. Calibration is deliberately deferred to Epic 7: the Cross-deck observations section
> above stands as the named calibration-input candidates. **G-R2 is CLOSED; Epic 7 story creation is unblocked.**

Mark each deck plausible or name the divergence. The gate closes when every deck has exactly one box checked; divergences become named Epic 7 calibration inputs.

- Abzan Dragons (`4f9d6f52`)
  - [x] plausible
  - [ ] divergence: ______
- Astonishing Ant-Man — Simic Counters Tempo (`4d0a55fb`)
  - [x] plausible
  - [ ] divergence: ______
- Baron Zemo — Villain Connive (`dcdfa284`)
  - [x] plausible
  - [ ] divergence: ______
- Bulk Import Tool Test - Naya Dinosaurs - 2026-07-10 (`94494472`)
  - [x] plausible
  - [ ] divergence: ______
- Graveyard Gravy (`baafd58b`, 3-card stub)
  - [x] plausible
  - [ ] divergence: ______
- Graveyard Gravy (`e7870022`, 60-card)
  - [x] plausible
  - [ ] divergence: ______
- Iron Man, Modern Marvel — reminder (`5cd42e7f`)
  - [x] plausible
  - [ ] divergence: ______
- Kotis Saboteur Tempo - Standard Draft (`a380ca25`)
  - [x] plausible
  - [ ] divergence: ______
- Kotis, the Fangkeeper — 100-card Brawl (`f02e1faa`)
  - [x] plausible
  - [ ] divergence: ______
- Kotis, the Fangkeeper — Standard Brawl (`a839fc0b`)
  - [x] plausible
  - [ ] divergence: ______
- Mardu Midrange (`8db441c0`)
  - [x] plausible
  - [ ] divergence: ______
- Mardu Midrange v2 (`076ac3ed`)
  - [x] plausible
  - [ ] divergence: ______
- MSH — Assemble! — Hexproof Hero Anthem Swarm (`7e86ad5d`)
  - [x] plausible
  - [ ] divergence: ______
- MSH — Namor's Tide — Izzet Merfolk Spellslinger Tempo (`d1c18722`)
  - [x] plausible
  - [ ] divergence: ______
- MSH — Snakebite Edict — Golgari Deathtouch Villain Aristocrats (`4e6b5959`)
  - [x] plausible
  - [ ] divergence: ______
- MSH — The Mad Titan's Gauntlet — Five-Color Power-Up Snap (`c9f5b355`)
  - [x] plausible
  - [ ] divergence: ______
- MSH — Ultron's Forge — Artifact Copy Combo Engine (`e684ceb1`)
  - [x] plausible
  - [ ] divergence: ______
- Prismatic Dragon (`a6ec5c97`)
  - [x] plausible
  - [ ] divergence: ______
- Sephiroth, Fabled SOLDIER — Standard Brawl (`d2ec429d`)
  - [x] plausible
  - [ ] divergence: ______
- Skynet (`99f55404`)
  - [x] plausible
  - [ ] divergence: ______

### Named-divergence template

```
Divergence name:
Deck (name + id):
Expected (human judgment):
Produced (scorer output):
Suspected signal / dimension:
Disposition: Epic 7 calibration input
```

## Appendix: harness source (reproducibility — 6.3 Task 5 precedent)

The harness is throwaway (scratchpad-only, never committed); its full source is embedded here so the run is reproducible with one file + one command.

```python
"""G-R2 Pre-Epic-7 Real-Deck Gate harness (THROWAWAY — scratchpad only, never committed).

Loads every saved deck from the live central DB through the exact Epic 7 path
(``DeckRepository.get_deck_with_cards`` -> ``ComboSnapshotRepository.get_variants_for_names``
-> pure ``score()``) and writes the committed gate report. Read-only against the DB:
no writes, no network. Mirrors ``tests/integration/logic/test_assessment_benchmark.py``
wiring: commander rows stay INSIDE ``deck_cards`` (mainboard-only, ``sideboard=False``);
``commanders`` is a separate resolved-name sequence.

Commander resolution policy: ``DeckCard.commander`` flag first (mainboard rows), else the
explicit spec-frozen override map, resolved against MAINBOARD card names via the
codebase's own ``name_keys()`` normalization (DFC front-face aware). No guessing beyond
the map.

Run from the repo root:
    uv run python "<scratchpad>/g_r2_real_deck_harness.py"
"""

import asyncio
import html
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

from sqlalchemy import func, select

from src.data.database import create_engine, create_session_factory
from src.data.models.combo import ComboVariantPieceModel
from src.data.repositories.combo_snapshot import ComboSnapshotRepository
from src.data.repositories.deck import DeckRepository
from src.data.schemas.combo import ComboSnapshotMeta, name_keys
from src.data.schemas.deck import Deck
from src.logic.assessment import (
    COMMANDER_PROFILE,
    STANDARD_PROFILE,
    CoreAssessment,
    FormatProfile,
    score,
)

REPO_ROOT: Final = Path(r"C:\Users\brads\Projects\Artificial-Planeswalker")
RUN_DATE: Final = date.today().isoformat()
BASELINE_COMMIT: Final = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
REPORT_PATH: Final = (
    REPO_ROOT
    / "_bmad-output"
    / "implementation-artifacts"
    / f"pre-epic-7-real-deck-gate-report-{RUN_DATE}.md"
)

#: Explicit commander override map (spec-frozen): the live DB has ZERO
#: ``DeckCard.commander`` flags (all decks predate Story 6.1). No name-guessing
#: heuristics beyond this map; names resolve via ``name_keys()`` only.
COMMANDER_OVERRIDES: Final[dict[str, tuple[str, ...]]] = {
    "a839fc0b-e787-4f01-a640-23a95b79ecbd": ("Kotis, the Fangkeeper",),  # Standard Brawl 60
    "f02e1faa-6023-494e-9027-7c19b931288e": ("Kotis, the Fangkeeper",),  # 100-card Brawl
    "d2ec429d-c94d-467a-ad70-804d6b021f55": ("Sephiroth, Fabled SOLDIER",),  # Brawl stub (20)
}

#: Explicit format -> (profile label, profile, mainboard min, mainboard max, provisional)
#: mapping. Epic 7 owns the real format->profile mapping; brawl-family ->
#: COMMANDER_PROFILE is itself a calibration observation (provisional). ``None`` max
#: means the format has no maximum deck size.
PROFILE_MAP: Final[dict[str, tuple[str, FormatProfile, int, int | None, bool]]] = {
    "standard": ("STANDARD_PROFILE", STANDARD_PROFILE, 60, None, False),
    "historic": ("STANDARD_PROFILE", STANDARD_PROFILE, 60, None, False),
    "brawl": ("COMMANDER_PROFILE (provisional)", COMMANDER_PROFILE, 100, 100, True),
    "standardbrawl": ("COMMANDER_PROFILE (provisional)", COMMANDER_PROFILE, 60, 60, True),
}

VECTOR_DIMENSIONS: Final = (
    "speed",
    "consistency",
    "resilience",
    "interaction",
    "mana_efficiency",
    "card_advantage",
    "combo_potential",
)

#: Missing at most this many cards below the format minimum -> "near-complete"
#: (outputs directionally meaningful) instead of "incomplete-stub".
NEAR_COMPLETE_TOLERANCE: Final = 2

_BASIC_LAND_NAMES: Final = frozenset({"plains", "island", "swamp", "mountain", "forest", "wastes"})


@dataclass
class DeckResult:
    """Everything the report needs for one deck, keyed by deck id."""

    deck_id: str
    name: str
    format: str
    profile_label: str
    provisional: bool
    unmapped_format: bool
    mainboard_count: int
    land_count: int
    color_identity: str
    strategy: str | None
    updated_at: str
    commanders: tuple[str, ...]
    commander_source: str  # "flag" | "override" | "none"
    commander_zone: str  # "mainboard" | "-"
    dfc_override: bool
    candidate_variant_count: int
    completeness: str  # "ok" | "near-complete" | "incomplete-stub"
    oversize: bool
    format_minimum: int
    format_maximum: int | None
    notes: list[str] = field(default_factory=list)
    zero_overlap_verdict: str | None = None
    assessment: CoreAssessment | None = None
    error: str | None = None


def ascii_safe(text: str) -> str:
    """Console-safe rendering for a cp1252 Windows stdout (em-dashes in deck names)."""
    return text.encode("ascii", errors="replace").decode("ascii")


def md_cell(text: str) -> str:
    """Escape a value for a markdown table cell (pipes break rows, newlines break cells)."""
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def html_safe(text: str) -> str:
    """Escape a value for embedding inside raw HTML (<details><summary>)."""
    return html.escape(text)


def short_id(deck_id: str) -> str:
    return deck_id.split("-")[0]


def is_land(type_line: str) -> bool:
    """Token-wise 'Land' check (handles 'Basic Land — Island', 'Artifact Land', DFCs)."""
    return "land" in type_line.lower().split()


def resolve_profile(
    deck_format: str | None,
) -> tuple[str, FormatProfile, int, int | None, bool, bool, list[str]]:
    """Map a stored format to (label, profile, min, max, provisional, unmapped, notes)."""
    notes: list[str] = []
    key = (deck_format or "").strip().lower()
    if key in PROFILE_MAP:
        label, profile, minimum, maximum, provisional = PROFILE_MAP[key]
        return label, profile, minimum, maximum, provisional, False, notes
    notes.append(
        f"unmapped format {deck_format!r} -> STANDARD_PROFILE fallback "
        f"(60-card minimum assumed)"
    )
    return "STANDARD_PROFILE (fallback)", STANDARD_PROFILE, 60, None, False, True, notes


async def zero_overlap_probe(session, names: list[str]) -> str:
    """Verify a 0-candidate result: normalization failure vs genuinely combo-inert pool.

    Read-only: for each distinct mainboard name, check its ``name_keys()`` against the
    snapshot piece index (exact); then LIKE-probe a sample of non-basic names for
    near-misses (a normalization failure would surface as near-miss keys that exist but
    never match exactly).
    """
    distinct = sorted(set(names))
    exact_hits = 0
    for name in distinct:
        keys = list(name_keys(name))
        result = await session.execute(
            select(func.count()).where(ComboVariantPieceModel.name_key.in_(keys))
        )
        if result.scalar_one():
            exact_hits += 1
    sample = [n for n in distinct if n.lower() not in _BASIC_LAND_NAMES][:5]
    near_misses: list[str] = []
    for name in sample:
        fragment = name.lower().split(" // ")[0].split(",")[0]
        result = await session.execute(
            select(ComboVariantPieceModel.name_key)
            .where(ComboVariantPieceModel.name_key.like(f"%{fragment}%"))
            .limit(3)
        )
        near_misses.extend(row[0] for row in result.fetchall())
    if exact_hits == 0 and not near_misses:
        return (
            f"verified genuinely combo-inert pool: 0 of {len(distinct)} distinct mainboard "
            f"names appear as any snapshot piece key (exact name_keys check), and LIKE "
            f"near-miss probes on {len(sample)} sampled non-basic names "
            f"({'; '.join(sample)}) return no candidate keys — NOT a normalization failure."
        )
    return (
        f"exact name_keys hits for {exact_hits} of {len(distinct)} distinct names; "
        f"near-miss LIKE probe returned {len(near_misses)} keys "
        f"({', '.join(near_misses[:6])}) — investigate normalization."
    )


async def build_result(session, combo_repo: ComboSnapshotRepository, deck: Deck) -> DeckResult:
    """Load-side data for one deck: commanders, mainboard rows, candidate variants."""
    notes: list[str] = []
    label, profile, minimum, maximum, provisional, unmapped, profile_notes = resolve_profile(
        deck.format
    )
    notes.extend(profile_notes)

    # Mainboard-only into score(), mirroring the benchmark convention: commander rows
    # (where present) live inside deck_cards; commanders is a separate name sequence.
    mainboard = tuple(dc for dc in deck.deck_cards if not dc.sideboard)
    mainboard_count = sum(dc.quantity for dc in mainboard)
    mainboard_names = sorted({dc.card.name for dc in mainboard})
    sideboard_names = {dc.card.name for dc in deck.deck_cards if dc.sideboard}
    land_count = sum(dc.quantity for dc in mainboard if is_land(dc.card.type_line))

    # Commander resolution restricted to MAINBOARD rows: DeckCard.commander flag first,
    # else the explicit override map resolved via name_keys() (DFC front-face aware —
    # the codebase's own canonical normalization, not a guessing heuristic).
    flagged = tuple(dc.card.name for dc in mainboard if dc.commander)
    dfc_override = False
    if flagged:
        commanders = flagged
        commander_source = "flag"
        commander_zone = "mainboard"
    elif deck.id in COMMANDER_OVERRIDES:
        commander_source = "override"
        commander_zone = "-"
        verified: list[str] = []
        for name in COMMANDER_OVERRIDES[deck.id]:
            override_keys = set(name_keys(name))
            matched_stored = [
                stored for stored in mainboard_names if override_keys & set(name_keys(stored))
            ]
            if matched_stored:
                # Pass the STORED card name to score() (benchmark convention:
                # commanders are the deck's own card-name strings).
                verified.append(matched_stored[0])
                commander_zone = "mainboard"
                if matched_stored[0] != name:
                    dfc_override = True
                    notes.append(
                        f"override commander {name!r} resolved to stored DFC name "
                        f"{matched_stored[0]!r} via name_keys front-face normalization "
                        f"(Epic 7 calibration input: commander storage/lookup)"
                    )
                if len(matched_stored) > 1:
                    notes.append(
                        f"override commander {name!r} matched multiple stored names "
                        f"{matched_stored!r}; used the first (bytewise order)"
                    )
            else:
                in_sideboard = any(
                    override_keys & set(name_keys(stored)) for stored in sideboard_names
                )
                where = "found only in sideboard" if in_sideboard else "no name_keys overlap"
                notes.append(
                    f"override commander {name!r} NOT resolved from mainboard ({where}) "
                    f"-- scored without it"
                )
        commanders = tuple(verified)
    else:
        commanders = ()
        commander_source = "none"
        commander_zone = "-"

    variant_query_names = sorted(set(mainboard_names) | set(commanders))
    variants = await combo_repo.get_variants_for_names(variant_query_names)

    if mainboard_count < minimum:
        shortfall = minimum - mainboard_count
        completeness = (
            "near-complete" if shortfall <= NEAR_COMPLETE_TOLERANCE else "incomplete-stub"
        )
    else:
        completeness = "ok"
    oversize = maximum is not None and mainboard_count > maximum
    if oversize:
        notes.append(
            f"mainboard {mainboard_count} exceeds the format maximum {maximum} -- "
            f"flagged oversize"
        )

    zero_overlap_verdict: str | None = None
    if len(variants) == 0 and mainboard_names:
        zero_overlap_verdict = await zero_overlap_probe(session, mainboard_names)

    result = DeckResult(
        deck_id=deck.id,
        name=deck.name,
        format=deck.format or "(none)",
        profile_label=label,
        provisional=provisional,
        unmapped_format=unmapped,
        mainboard_count=mainboard_count,
        land_count=land_count,
        color_identity="".join(deck.color_identity) if deck.color_identity else "C",
        strategy=deck.strategy,
        updated_at=deck.updated_at.isoformat(),
        commanders=commanders,
        commander_source=commander_source,
        commander_zone=commander_zone,
        dfc_override=dfc_override,
        candidate_variant_count=len(variants),
        completeness=completeness,
        oversize=oversize,
        format_minimum=minimum,
        format_maximum=maximum,
        notes=notes,
        zero_overlap_verdict=zero_overlap_verdict,
    )

    # score() is pure/sync. Guard per deck: stubs must never crash the run.
    try:
        result.assessment = score(
            mainboard,
            commanders=commanders,
            variants=variants,
            profile=profile,
        )
    except Exception:  # noqa: BLE001 - gate report captures the failure verbatim
        result.error = traceback.format_exc()
    return result


async def collect(
    session_factory,
) -> tuple[ComboSnapshotMeta, list[DeckResult], int, list[str]]:
    """One read-only DB sweep: metadata, all decks, per-deck variants + probes."""
    results: list[DeckResult] = []
    skipped: list[str] = []
    async with session_factory() as session:
        combo_repo = ComboSnapshotRepository(session)
        if not await combo_repo.snapshot_is_available():
            raise SystemExit(
                "ABORT: combo snapshot is not available in the central DB "
                "(snapshot_is_available() returned False). Run "
                "scripts/import_spellbook_combos.py, then re-run this harness."
            )
        metadata = await combo_repo.get_metadata()
        if metadata is None:
            raise SystemExit("ABORT: snapshot metadata row missing despite available snapshot.")

        deck_repo = DeckRepository(session)
        decks = await deck_repo.list_decks()
        if not decks:
            raise SystemExit("ABORT: zero decks enumerated from the central DB.")
        # Stable, human-friendly order: name then id (duplicate names exist).
        deck_ids = [d.id for d in sorted(decks, key=lambda d: (d.name.lower(), d.id))]

        for deck_id in deck_ids:
            deck = await deck_repo.get_deck_with_cards(deck_id)
            if deck is None:
                skipped.append(deck_id)
                continue
            results.append(await build_result(session, combo_repo, deck))
    return metadata, results, len(deck_ids), skipped


def flags_for(result: DeckResult) -> str:
    """Summary-table flag cell: short tokens only (prose lives in detail notes)."""
    flags: list[str] = []
    if result.completeness == "incomplete-stub":
        flags.append("incomplete-stub")
    elif result.completeness == "near-complete":
        flags.append("near-complete")
    if result.oversize:
        flags.append("oversize")
    if result.provisional:
        flags.append("provisional-profile")
    if result.unmapped_format:
        flags.append("unmapped-format-fallback")
    if result.commander_source == "override" and result.commanders:
        flags.append("override-commander")
    if result.dfc_override:
        flags.append("dfc-override")
    if result.assessment is not None and result.assessment.game_changers.unknown_count > 0:
        flags.append("gc-unknown")
    if result.error is not None:
        flags.append("scoring-error")
    return ", ".join(flags) if flags else "—"


def deck_hints(results: list[DeckResult]) -> dict[str, str]:
    """Disambiguation hints (by deck id) for decks sharing a name."""
    name_counts: dict[str, int] = {}
    for r in results:
        name_counts[r.name] = name_counts.get(r.name, 0) + 1
    hints: dict[str, str] = {}
    for r in results:
        if name_counts[r.name] > 1:
            stub = " stub" if r.completeness == "incomplete-stub" else ""
            hints[r.deck_id] = f"{r.mainboard_count}-card{stub}"
    return hints


def deck_label(result: DeckResult, hints: dict[str, str]) -> str:
    """'Name (`shortid`)' with a human hint for duplicate names."""
    hint = hints.get(result.deck_id)
    suffix = f", {hint}" if hint else ""
    return f"{md_cell(result.name)} (`{short_id(result.deck_id)}`{suffix})"


def completeness_note(result: DeckResult) -> str | None:
    if result.completeness == "incomplete-stub":
        return (
            f"incomplete — {result.mainboard_count} mainboard cards vs format minimum "
            f"{result.format_minimum}; outputs not meaningful."
        )
    if result.completeness == "near-complete":
        return (
            f"near-complete ({result.mainboard_count}/{result.format_minimum}) — outputs "
            f"directionally meaningful."
        )
    return None


def cross_deck_observations(
    results: list[DeckResult], hints: dict[str, str], variant_count: int
) -> list[str]:
    """Factual cross-deck patterns, each a candidate named Epic 7 calibration input."""
    scored = [r for r in results if r.assessment is not None]
    lines: list[str] = []

    ca80 = [r for r in scored if r.assessment.vector.card_advantage == 80]
    lines.append(
        f"- **Candidate calibration input — card_advantage saturation:** "
        f"`card_advantage` is exactly 80 in {len(ca80)} of {len(scored)} decks "
        f"({', '.join(deck_label(r, hints) for r in ca80)}) — a saturation/clamp pattern "
        f"in the draw-density mapping."
    )

    pegged = [r for r in scored if r.assessment.vector.interaction in (0, 100)]
    pegged_cells = ", ".join(
        f"{deck_label(r, hints)}={r.assessment.vector.interaction}" for r in pegged
    )
    lines.append(
        f"- **Candidate calibration input — interaction pegging:** `interaction` sits at "
        f"exactly 0 or 100 in {len(pegged)} of {len(scored)} decks ({pegged_cells}) "
        f"— the dimension rails rather than grading."
    )

    gc_all_zero = all(
        r.assessment.game_changers.known_count == 0
        and r.assessment.game_changers.unknown_count == 0
        for r in scored
    )
    if gc_all_zero:
        lines.append(
            f"- **Observation (not a defect) — game_changers inert on this pool:** "
            f"known_count=0 and unknown_count=0 across all {len(scored)} decks. The Game "
            f"Changer list is Commander-centric, so the signal is plausibly inert on this "
            f"Standard/Marvel-heavy pool."
        )

    brawl = [r for r in scored if r.provisional]
    if brawl and all(r.assessment.vector.mana_efficiency == 0 for r in brawl):
        lines.append(
            f"- **Candidate calibration input — Brawl mana_efficiency floor:** "
            f"`mana_efficiency` is 0 on every Brawl-family deck "
            f"({', '.join(deck_label(r, hints) for r in brawl)}) — the Commander-profile "
            f"Karsten/pip mapping bottoms out on all real Brawl lists."
        )

    all_combos = [combo for r in scored for combo in r.assessment.combos]
    almost = sum(1 for c in all_combos if c.bucket == "almost_included")
    lines.append(
        f"- **Candidate calibration input — almost_included dominance:** "
        f"{almost} of {len(all_combos)} matched combo records across all decks are "
        f"`almost_included` (only {len(all_combos) - almost} `included`) — combo credit "
        f"is driven almost entirely by one-piece-missing variants."
    )

    betor = {
        r.name: r.assessment.vector.combo_potential
        for r in scored
        if r.name in ("Abzan Dragons", "Prismatic Dragon")
    }
    if betor:
        rendered = ", ".join(f"{name} combo_potential={value}" for name, value in betor.items())
        lines.append(
            f"- **Candidate calibration input — format-blind almost_included inflation:** "
            f"{rendered}: these scores are driven by Betor-anchored `almost_included` "
            f"variants whose missing partners (Archfiend of Despair, Mycosynth Lattice, "
            f"Wound Reflection) are NOT Standard-legal — the combo can never complete "
            f"in-format, yet it pushes `combo_potential` toward the ceiling. Already "
            f"logged as a product-level item in `deferred-work.md`."
        )

    for r in results:
        if r.zero_overlap_verdict and r.completeness == "ok":
            lines.append(
                f"- **Verified observation — zero candidate variants for "
                f"{deck_label(r, hints)}:** a full {r.mainboard_count}-card deck fetched 0 "
                f"candidates from a {variant_count:,}-variant snapshot; probe result: "
                f"{r.zero_overlap_verdict}"
            )
    stub_zero = [r for r in results if r.zero_overlap_verdict and r.completeness != "ok"]
    if stub_zero:
        labels = ", ".join(deck_label(r, hints) for r in stub_zero)
        lines.append(
            f"- Stub decks with zero candidates ({labels}) were probed the same way; see "
            f"their detail sections."
        )
    return lines


def render_report(
    metadata: ComboSnapshotMeta,
    results: list[DeckResult],
    enumerated: int,
    skipped: list[str],
) -> str:
    """The full gate-report markdown (UTF-8; deck names contain em-dashes)."""
    hints = deck_hints(results)
    lines: list[str] = []
    add = lines.append

    add("# Pre-Epic-7 Real-Deck Gate Report (G-R2)")
    add("")
    add(
        "Real-deck sanity pass over every saved deck in the live central DB through the "
        "exact Epic 7 path (`get_deck_with_cards` → `get_variants_for_names` → pure "
        "`score()`). Epic-6 retro action item 1; closes epic-5 action item 5. "
        "Each divergence from human judgment is a **named Epic 7 calibration input** — "
        "a divergence is data, not automatically a bug."
    )
    add("")
    add(f"- **Run date:** {RUN_DATE}")
    add(f"- **Baseline commit:** `{BASELINE_COMMIT}`")
    skipped_cell = ", ".join(skipped) if skipped else "none"
    add(f"- **Decks:** enumerated {enumerated}, scored {len(results)}, skipped: {skipped_cell}")
    add("")

    add("## Snapshot metadata (data vintage)")
    add("")
    add("| Field | Value |")
    add("|---|---|")
    add(f"| imported_at | {metadata.imported_at} |")
    add(f"| export_timestamp | {metadata.export_timestamp} |")
    add(f"| export_version | {metadata.export_version} |")
    add(f"| variant_count | {metadata.variant_count} |")
    add("")
    add(
        "Per-deck data vintage: each detail section carries the deck's own `updated_at` "
        "timestamp."
    )
    add("")

    add("## Summary")
    add("")
    add(
        "| Deck | Format | Profile | Commanders | Score | Tier | Bracket | cEDH | "
        "Combos matched | Flags |"
    )
    add("|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        a = r.assessment
        commanders = md_cell(", ".join(r.commanders)) if r.commanders else "—"
        if a is None:
            score_c = tier_c = bracket_c = cedh_c = combos_c = "ERROR"
        else:
            score_c = str(a.for_format_score)
            tier_c = a.tier
            bracket_c = str(a.bracket_floor) if a.bracket_floor is not None else "—"
            cedh_c = "yes" if a.cedh_candidate else "no"
            combos_c = str(len(a.combos))
        add(
            f"| {deck_label(r, hints)} | {md_cell(r.format)} | {r.profile_label} | "
            f"{commanders} | {score_c} | {tier_c} | {bracket_c} | {cedh_c} | "
            f"{combos_c} | {flags_for(r)} |"
        )
    add("")
    add(
        "Flag tokens: `incomplete-stub` = below format minimum, outputs not meaningful; "
        f"`near-complete` = within {NEAR_COMPLETE_TOLERANCE} cards of the minimum, "
        "outputs directionally meaningful; `oversize` = above format maximum; "
        "`provisional-profile` = brawl-family → COMMANDER_PROFILE mapping is provisional; "
        "`unmapped-format-fallback` = format not in the explicit map, STANDARD_PROFILE "
        "assumed; `override-commander` = commander from the harness override map; "
        "`dfc-override` = override name resolved to a stored DFC full name via "
        "name_keys; `gc-unknown` = game_changer unknown_count > 0; `scoring-error` = "
        "score() raised (captured in the detail section)."
    )
    add("")

    add("## Per-deck detail")
    add("")
    for r in results:
        hint = hints.get(r.deck_id)
        suffix = f", {html_safe(hint)}" if hint else ""
        add(
            f"<details><summary><b>{html_safe(r.name)}</b> "
            f"(<code>{short_id(r.deck_id)}</code>{suffix})</summary>"
        )
        add("")
        add(f"- **Deck id:** `{r.deck_id}`")
        add(f"- **Format:** {md_cell(r.format)} → profile {r.profile_label}")
        strategy = md_cell(r.strategy) if r.strategy else "(none)"
        add(
            f"- **Identity:** colors {r.color_identity} · strategy: {strategy} · "
            f"lands (mainboard): {r.land_count} · deck updated_at: {r.updated_at}"
        )
        add(f"- **Mainboard cards (sum of quantities):** {r.mainboard_count}")
        commanders = md_cell(", ".join(r.commanders)) if r.commanders else "(none)"
        add(
            f"- **Commanders:** {commanders} (source: {r.commander_source}, "
            f"zone: {r.commander_zone})"
        )
        add(
            f"- **Candidate combo variants fetched (over-fetch scale):** "
            f"{r.candidate_variant_count}"
        )
        note = completeness_note(r)
        if note:
            add(f"- **FLAG:** {note}")
        if r.zero_overlap_verdict:
            add(f"- **Zero-candidate probe:** {r.zero_overlap_verdict}")
        for extra in r.notes:
            add(f"- **Note:** {md_cell(extra)}")
        add("")
        a = r.assessment
        if a is None:
            add("**Scoring error (captured, run continued):**")
            add("")
            add("```")
            add((r.error or "").rstrip())
            add("```")
        else:
            add("**7-dimension vector:**")
            add("")
            add("| Dimension | Value |")
            add("|---|---|")
            for dim in VECTOR_DIMENSIONS:
                add(f"| {dim} | {getattr(a.vector, dim)} |")
            add("")
            add(f"- **for_format_score:** {a.for_format_score}")
            add(f"- **tier:** {a.tier}")
            bracket = a.bracket_floor if a.bracket_floor is not None else "None (heuristic_only)"
            add(f"- **bracket_floor:** {bracket}")
            add(f"- **cedh_candidate:** {a.cedh_candidate}")
            gc = a.game_changers
            gc_names = md_cell(", ".join(gc.card_names)) if gc.card_names else "(none)"
            add(
                f"- **game_changers:** known_count={gc.known_count}, "
                f"unknown_count={gc.unknown_count}, card_names: {gc_names}"
            )
            gaps = ", ".join(a.structural_gaps) if a.structural_gaps else "(none)"
            add(f"- **structural_gaps:** {gaps}")
            add(f"- **mass_land_denial:** {a.mass_land_denial}")
            add(f"- **extra_turn_chains:** {a.extra_turn_chains}")
            add("")
            if a.combos:
                add(f"**Matched combos ({len(a.combos)}):**")
                add("")
                add("| spellbook_id | bucket | bracket_tag | cards |")
                add("|---|---|---|---|")
                for combo in a.combos:
                    add(
                        f"| {combo.spellbook_id} | {combo.bucket} | {combo.bracket_tag} | "
                        f"{md_cell(', '.join(combo.cards))} |"
                    )
            else:
                add("**Matched combos:** none")
        add("")
        add("</details>")
        add("")

    add("## Caveats (standing, carried into review)")
    add("")
    add(
        "- `CEDH_TUTOR_MIN=3` (`src/logic/assessment/dimensions.py`): the cEDH candidacy "
        "gate requires at least 3 tutor-classified cards."
    )
    add(
        "- The FR6 tutor definition undercounts battlefield/library-exile tutors — tutor-"
        "dependent signals (consistency bonus, cEDH candidacy) are conservative."
    )
    add(
        "- brawl/standardbrawl → `COMMANDER_PROFILE` is **provisional**: Epic 7 owns the "
        "real format→profile mapping; this mapping choice is itself a calibration "
        "observation."
    )
    add(
        "- `DeckCard.commander` flags are absent in the live DB (all decks predate Story "
        "6.1) — commanders came from the explicit harness override map, resolved against "
        "mainboard card names via `name_keys()` (DFC front-face aware), no name-guessing."
    )
    add(
        "- `game_changers.unknown_count` is surfaced per deck; a nonzero value means the "
        "AD-4 backfill window is open for those cards."
    )
    add(
        "- Decks below the format minimum are scored but flagged: `incomplete-stub` "
        "(outputs not meaningful) or `near-complete` (outputs directionally meaningful, "
        f"within {NEAR_COMPLETE_TOLERANCE} cards of the minimum)."
    )
    add(
        "- A divergence from human judgment is **data** (Epic 7 calibration input), not "
        "automatically a bug."
    )
    add("")

    add("## Cross-deck observations (calibration-input candidates)")
    add("")
    add(
        "Factual patterns across the pool — no retuning here; each is a candidate named "
        "Epic 7 calibration input."
    )
    add("")
    for line in cross_deck_observations(results, hints, metadata.variant_count):
        add(line)
    add("")

    add("## Review sheet (Sathias)")
    add("")
    add(
        "Mark each deck plausible or name the divergence. The gate closes when every deck "
        "has exactly one box checked; divergences become named Epic 7 calibration inputs."
    )
    add("")
    for r in results:
        add(f"- {deck_label(r, hints)}")
        add("  - [ ] plausible")
        add("  - [ ] divergence: ______")
    add("")
    add("### Named-divergence template")
    add("")
    add("```")
    add("Divergence name:")
    add("Deck (name + id):")
    add("Expected (human judgment):")
    add("Produced (scorer output):")
    add("Suspected signal / dimension:")
    add("Disposition: Epic 7 calibration input")
    add("```")
    add("")

    add("## Appendix: harness source (reproducibility — 6.3 Task 5 precedent)")
    add("")
    add(
        "The harness is throwaway (scratchpad-only, never committed); its full source is "
        "embedded here so the run is reproducible with one file + one command."
    )
    add("")
    add("```python")
    add(Path(__file__).read_text(encoding="utf-8").rstrip())
    add("```")
    add("")
    return "\n".join(lines)


async def main() -> int:
    # Checked-review-box sentinel, constructed so the literal never appears in this
    # source (the report appendix embeds the harness source, which must not trip the
    # guard on its own).
    checked_box = "- [" + "x]"
    if REPORT_PATH.exists() and checked_box in REPORT_PATH.read_text(encoding="utf-8"):
        print(
            f"ABORT: {REPORT_PATH} already contains checked review boxes ({checked_box!r}) "
            f"-- a review is in progress; refusing to overwrite it."
        )
        return 1

    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        metadata, results, enumerated, skipped = await collect(session_factory)
    finally:
        await engine.dispose()

    if not results:
        print("ABORT: zero decks scored.")
        return 1
    assert len(results) + len(skipped) == enumerated, (
        f"scored ({len(results)}) + skipped ({len(skipped)}) != enumerated ({enumerated})"
    )

    report = render_report(metadata, results, enumerated, skipped)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"Snapshot: v{metadata.export_version}, {metadata.variant_count} variants")
    print(f"Decks: enumerated {enumerated}, scored {len(results)}, skipped {len(skipped)}")
    if skipped:
        print(f"  Skipped ids: {', '.join(skipped)}")
    errors = 0
    for r in results:
        a = r.assessment
        if a is None:
            errors += 1
            print(f"  ERROR  {ascii_safe(r.name)} ({short_id(r.deck_id)})")
        else:
            bracket = a.bracket_floor if a.bracket_floor is not None else "-"
            flags = flags_for(r)
            flag_suffix = f"  [{ascii_safe(flags)}]" if flags != "—" else ""
            print(
                f"  {a.for_format_score:>3}  {ascii_safe(a.tier):<22} bracket={bracket} "
                f"cedh={'Y' if a.cedh_candidate else 'n'} combos={len(a.combos):>2} "
                f"variants={r.candidate_variant_count:>4}  {ascii_safe(r.name)} "
                f"({short_id(r.deck_id)}){flag_suffix}"
            )
    print(f"Report written: {REPORT_PATH}")
    if errors:
        print(f"{errors} deck(s) failed to score -- see report error sections.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```
