---
stepsCompleted: [1, 2]
currentStep: step-03-create-stories
status: epic-1-stories-draft-awaiting-review
inputDocuments:
  - _bmad-output/specs/spec-deck-workflow-reliability/SPEC.md
  - _bmad-output/specs/spec-deck-workflow-reliability/acceptance.md
  - docs/architecture.md
scope: Deck workflow reliability
approvedGroupings:
  - Reliable deck workflows
  - Trustworthy assessment
---

# Artificial-Planeswalker - Deck Workflow Reliability Epic Breakdown

## Overview

Decompose the saved spec into the two user-approved groupings: reliable deck workflows (CAP-1 and CAP-2) and trustworthy assessment (CAP-3). The spec and its acceptance companion define scope; the existing MCP architecture and current repository instructions constrain implementation. This is brownfield work with no starter template or new UI design scope.

This separate plan preserves the completed Phase 1 plan at epics.md. Historical Letta-first planning and companion UI redesign requirements are excluded. Current repository rules take precedence over the pivot document's historical transport roadmap: stdio remains the only MCP transport.

## Requirements Inventory

### Functional Requirements

FR1: Resolve an entire deck in one bulk request, accepting names and optional printing qualifiers with existing format/platform filters (CAP-1).
FR2: Preserve input order, original text, indices and duplicate inputs; return one attributable found, ambiguous-with-candidates, missing, failed or explicitly unfinished result per input, plus batch completeness (CAP-1).
FR3: Return actionable outcomes for oversized requests and expired deadlines, cancel unfinished work, release resources and permit successful subsequent requests (CAP-1).
FR4: Use consistent card resolution in bulk lookup and import; resolve unambiguous front-face names to playable identities, exclude art cards from ordinary playable resolution, and explicitly report qualifier mismatch or fallback (CAP-1/CAP-2).
FR5: Import name-only and printing-qualified lists while preserving additive behavior, reporting each rejected line, imported totals and partial success, and documenting retry behavior (CAP-2).
FR6: Export verified Arena-compatible names and printing identifiers where used; substitute only verified printings of the same playable identity and explicitly report unexportable cards without silent omission (CAP-2).
FR7: Preserve playable identities, quantities and supported Commander/Deck/Sideboard/Companion sections across import/export round trips, including split and double-faced cards (CAP-2).
FR8: Report Brawl numerical scoring as unsupported without silently substituting a Commander score or strength label (CAP-3).
FR9: Separate complete combos from missing-card suggestions; incomplete variants contribute no credit as functioning combos (CAP-3).
FR10: Preserve supported Commander/Standard assessment behavior except for the intended incomplete-combo correction (CAP-3).

### NonFunctional Requirements

NFR1: Bound lookup work, concurrency and response size; determine and document batch limits and item/batch deadlines from measurements rather than inventing thresholds.
NFR2: Measure orchestration separately from server/database execution for individual, 3-, 15-, approximately 90-, and representative 100-card workloads; do not attribute stalls without evidence.
NFR3: Verify cancellation, resource cleanup and recovery through injected queued/running stalls and subsequent requests.
NFR4: Keep lookup/export/analysis observational and MCP calls stateless; require explicit deck-management intent for mutations and keep the companion read-only.
NFR5: Verify behavior through real entry points, including mixed lookup outcomes, filters, qualifiers and duplicates; parser-only round trips do not establish Arena compatibility.
NFR6: Do not treat platform availability aggregated across printings as proof that a stored printing is Arena-compatible.

### Additional Requirements

- Preserve data-to-logic-to-MCP import direction and framework-free data/logic layers; reuse existing repositories and Pydantic tool contracts.
- Preserve stdio transport, caller-supplied deck/format/platform context, and existing companion boundaries; no new capability in the frozen viewer.
- Update affected shipped skills and regenerate plugin artifacts for tool changes. Generate API types/bundles only when relevant backend/UI contracts change; never hand-edit generated files.
- Any required schema extension needs a migration and preservation of existing deck/card references; decide the printing-data source before implementing printing interoperability.
- Resolve the strict-rejection versus explicit-fallback qualifier policy before implementation; never silently guess an identity.
- Exercise The Emperor of Palamecia with FIN 219, the complete split-card identity associated with Commit, invalid qualifiers and unavailable printings.
- Verify the zero-complete/18-missing-one-card combo case cannot receive maximum functioning-combo credit.
- Run applicable repository quality gates for implementation; this artifact itself changes no runtime behavior.
- Exclude calibrated Brawl scoring, complete Brawl legality, atomic swaps/replacement, broad synergy expansion and companion launch diagnostics.

### UX Design Requirements

No new visual or interaction design is in scope. Actionable tool outcomes, explicit partial results and honest assessment messaging are covered by the functional requirements.

### FR Coverage Map

| Requirement | Epic | Outcome |
| --- | --- | --- |
| FR1 | 1 | Whole-deck bulk lookup |
| FR2 | 1 | Ordered, attributable outcomes for every input |
| FR3 | 1 | Bounded failure and resource recovery |
| FR4 | 1 | Consistent playable-card and printing resolution |
| FR5 | 1 | Flexible imports with explicit partial success |
| FR6 | 1 | Verified Arena exports and unexportable-card diagnostics |
| FR7 | 1 | Identity, quantity and section preservation |
| FR8 | 2 | Explicit unsupported Brawl scoring |
| FR9 | 2 | Complete combos distinguished from suggestions |
| FR10 | 2 | Supported assessment behavior preserved |

## Epic List

### Epic 1: Reliable deck workflows

Users can resolve a whole deck without database workarounds, understand and recover from incomplete lookups, and move supported decks into Arena without manual name repairs or silent card substitutions.

**FRs covered:** FR1-FR7 (CAP-1 and CAP-2).

**Quality coverage:** NFR1-NFR6. Measure limits and deadline ownership; prove cleanup and retry behavior. Verify actual Arena acceptance alongside identity-preserving round trips.

**Implementation considerations:** Keep lookup and import resolution together because they share card identity and printing semantics. Establish a verified printing-data source and qualifier mismatch policy before dependent implementation. Preserve additive imports and observational lookups/exports; ship affected skill and generated-plugin updates with their tool changes.

**Completion boundary:** The representative 100-card workflow and mixed-failure cases pass; neither successful resolution nor Arena export requires Epic 2. Detailed stories will be ordered so each depends only on existing behavior or earlier stories.

### Epic 2: Trustworthy assessment

Users can distinguish unsupported Brawl scoring from supported assessments and distinguish functioning combos from missing-card suggestions, without misleading strength labels or inflated functioning-combo credit.

**FRs covered:** FR8-FR10 (CAP-3).

**Quality coverage:** NFR4 and NFR5. Assessment remains observational and is verified through real entry points, including the zero-complete/18-incomplete-variant regression case.

**Implementation considerations:** Keep format-support reporting and combo-credit correction within assessment behavior. Preserve Commander/Standard behavior except for the intended combo correction. No calibrated Brawl model is introduced.

**Completion boundary:** Existing saved decks receive honest assessment outcomes without requiring Epic 1.

### Delivery relationship

The epics are independently deliverable; their numbering expresses presentation order, not a hard dependency. Epic 1 concentrates changes to card resolution and import/export; Epic 2 concentrates changes to assessment and combo scoring. Shared tool registration, shipped skills and plugin generation are incidental integration overlap and do not justify merging the two user outcomes.

## Epic 1: Reliable deck workflows

Users can resolve whole decks, recover from incomplete lookups and exchange supported deck lists with Arena. The stories below are review drafts, not yet approved. Each includes relevant shipped-skill updates, generated artifacts and entry-point tests; those are part of delivery, not a later integration story.

### Story 1.1: Resolve playable card names consistently

As a deckbuilder,
I want front-face and full card names to resolve consistently across lookup and import,
So that art cards and ambiguous names do not cause accidental card selection.

**Requirements:** FR4; NFR4, NFR5. **Dependencies:** None.

**Acceptance Criteria:**

**Given** a front-face name with one playable identity and a similarly named art card,
**When** I use card lookup or the existing qualified-list importer,
**Then** both resolve the same playable identity,
**And** ordinary playable-card resolution excludes the art card.

**Given** multiple valid playable matches or no valid match,
**When** resolution runs,
**Then** it returns explicit ambiguity with candidates or a not-found result,
**And** it never silently chooses a candidate.

**Given** format/platform filters and full split or double-faced names,
**When** the lookup entry point resolves them,
**Then** existing filters remain effective and full identities are preserved,
**And** observational calls do not change the deck.

### Story 1.2: Honor supplied printing identifiers

As a deckbuilder,
I want supplied set and collector numbers to participate in resolution,
So that qualified imports identify the intended playable card.

**Requirements:** FR4; NFR5, NFR6. **Dependencies:** Story 1.1.

**Acceptance Criteria:**

**Given** the current canonical-card database does not retain every printing,
**When** printing-qualified resolution is designed,
**Then** its verified printing-data source and strict-rejection or explicit-fallback policy are documented before implementation,
**And** only storage needed by this story is introduced, with any required migration preserving existing card/deck references.

**Given** a valid name, set and collector combination including The Emperor of Palamecia with FIN 219,
**When** a qualified import resolves the line,
**Then** the identifiers participate in selecting the playable identity,
**And** the reusable resolver exposes the same outcome to card lookup consumers.

**Given** mismatched, unknown or unavailable printing identifiers,
**When** resolution runs,
**Then** it follows the recorded policy and reports rejection or fallback explicitly,
**And** it never silently substitutes an identity or treats aggregated Arena availability as printing proof.

### Story 1.3: Resolve a whole deck with bounded bulk lookup

As a deckbuilder,
I want one bulk request that completes predictably and reports every input,
So that I can resolve my deck and retry failures without direct database workarounds.

**Requirements:** FR1-FR3, FR4; NFR1-NFR5. **Dependencies:** Story 1.2.

**Acceptance Criteria:**

**Given** individual, 3-, 15-, approximately 90-, and representative 100-card workloads,
**When** baseline and bulk execution are measured,
**Then** orchestration delays are distinguished from server/database processing,
**And** batch size, concurrency, response limits and item/batch deadline ownership are documented from measurements without claiming an unproven stall cause.

**Given** mixed valid, missing, ambiguous, duplicate and printing-qualified inputs,
**When** the bulk MCP entry point runs with format/platform filters,
**Then** it returns one ordered result preserving each input's index and text, plus batch completeness,
**And** shared resolution rules apply without writing to a deck.

**Given** a request exceeds the documented input limit,
**When** it is submitted,
**Then** it returns an actionable limit outcome without silently truncating inputs,
**And** accepted requests retain explicit per-input outcomes within the response bound.

**Given** an injected stall while items are queued or running,
**When** the owning deadline expires,
**Then** completed results remain available and all unfinished inputs have explicit outcomes,
**And** outstanding work is cancelled and resources released so a subsequent request succeeds without accumulating abandoned workers.

### Story 1.4: Import common Arena deck lists with clear partial results

As a deckbuilder,
I want to import name-only and printing-qualified lists,
So that ordinary deck lists work and rejected lines are easy to correct.

**Requirements:** FR5, FR7; NFR4, NFR5. **Dependencies:** Story 1.2; independent of Story 1.3.

**Acceptance Criteria:**

**Given** a list with name-only and qualified card lines in supported sections,
**When** I import it into an existing saved deck,
**Then** the shared resolver determines identities and the import preserves quantities and supported section placement,
**And** additive behavior remains intact.

**Given** valid lines mixed with malformed, ambiguous or unresolved lines,
**When** the import completes,
**Then** every rejected line has an attributable diagnostic and imported totals are accurate,
**And** partial success is explicit rather than represented as complete success.

**Given** a repeated import or duplicate lines,
**When** I retry,
**Then** the outcome follows documented additive/duplicate semantics,
**And** actual saved quantities and returned totals agree.

### Story 1.5: Export verified Arena-compatible decks

As a deckbuilder,
I want an Arena-compatible export of my saved deck,
So that I can import it into Arena without repairing card names or printing identifiers.

**Requirements:** FR6, FR7; NFR4-NFR6. **Dependencies:** Stories 1.2 and 1.4.

**Acceptance Criteria:**

**Given** a deck whose cards have verified Arena-compatible representations,
**When** I export it,
**Then** names and printing identifiers where used are verified for Arena,
**And** playable identities, quantities and supported Commander/Deck/Sideboard/Companion placement are preserved without mutating the saved deck.

**Given** a stored canonical printing that is not Arena-compatible,
**When** export selects a replacement printing,
**Then** it uses only a verified Arena printing of the same playable identity,
**And** aggregated platform availability alone is insufficient evidence.

**Given** a card has no verified exportable representation,
**When** export runs,
**Then** the card is explicitly reported as unexportable,
**And** it is neither silently omitted nor represented as part of a complete valid export.

**Given** split-card and double-faced-card fixtures, including the full identity associated with Commit and The Emperor of Palamecia,
**When** exports are round-tripped and tested for actual Arena acceptance,
**Then** identities, quantities and sections survive without manual name repairs,
**And** evidence includes Arena acceptance rather than only this project's parser agreeing with its own exporter.

### Epic 1 draft coverage

FR1-FR3: Story 1.3. FR4: Stories 1.1-1.3. FR5: Story 1.4. FR6: Story 1.5. FR7: Stories 1.4-1.5. All six NFRs are assigned above. No story depends on a future story or on Epic 2. Printing-source and fallback decisions remain explicit work in Story 1.2; measured operational limits remain explicit work in Story 1.3.
