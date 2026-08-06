/**
 * The generated wire types, pinned by shape (AC 9).
 *
 * ⚠️ **`npm test` passing proves NOTHING about this file. `npm run typecheck` is the gate.**
 *
 * `expectTypeOf` assertions are erased at runtime — they compile to nothing and vitest executes an
 * empty test body. Measured on this project: mutate the generated `status: "ok"` to
 * `status: string` and `vitest run` still reports every test passing, while `tsc -b` exits 2 with
 * `error TS2344: Type '{ status: "ok"; … }' does not satisfy the constraint
 * '{ status: "Expected: literal string: ok, Actual: string"; … }'`.
 *
 * So do **not** "simplify" these into runtime assertions and do not treat a green vitest run as
 * evidence. Both gates run in CI (`typecheck` before `test`), which is what makes this file real.
 *
 * Why pin at all: without it, a regeneration that emitted an empty `types.d.ts` — a broken schema,
 * a generator flag change, a silently truncated file — would pass every gate this project has.
 * These assertions are the reason the drift checks guard something rather than guarding a file.
 */

import { describe, expectTypeOf, it } from 'vitest'

import type {
  Card,
  CardFace,
  ErrorReason,
  ErrorResponse,
  FormatCheckReport,
  FormatCheckRow,
  HealthResponse,
} from './schema'

describe('generated wire types (AD-12)', () => {
  // `status` must stay the 'ok' literal, not widen to string: it is the closed token the
  // backend's Literal["ok"] declares, and the identity probe's whole value is that a caller can
  // tell this companion from an unrelated server holding the same port (AD-4).
  it('pins HealthResponse to the backend shape', () => {
    expectTypeOf<HealthResponse>().toEqualTypeOf<{ status: 'ok'; instance_id: string }>()
  })

  // The body is the token and nothing else — no message, no detail, no errors[] (AD-16).
  it('pins ErrorResponse to the token and nothing else', () => {
    expectTypeOf<ErrorResponse>().toEqualTypeOf<{ reason: ErrorReason }>()
  })

  // All ten named explicitly. This is the one assertion that cannot be derived from the
  // generated file, and that is the point: it is a second, independent statement of AD-16's closed
  // set, so a token dropped on the Python side reddens here instead of quietly deleting a c2-9
  // state panel.
  //
  // c3-2 edited this line to add `card_not_found`, c3-4 to add `forbidden`, and c3-5 to add BOTH
  // of `no_image_data` and `image_fetch_failed` — the first story to add a pair, because AD-11
  // requires a card with no artwork and a failed CDN fetch to be distinguishable and this codebase
  // derives the status from the token. The rule stands unchanged for an eleventh: adding a token
  // is a deliberate act that edits this line — and `npm test` will NOT tell you that you forgot,
  // because this file's assertions erase to nothing at runtime (see the header). The failure
  // arrives from `npm run typecheck`, here and in `components/StatePanel/states.ts`.
  it('pins the closed ten-token reason set', () => {
    expectTypeOf<ErrorReason>().toEqualTypeOf<
      | 'deck_not_found'
      | 'card_not_found'
      | 'no_image_data'
      | 'image_fetch_failed'
      | 'database_not_initialized'
      | 'database_unavailable'
      | 'invalid_request'
      | 'forbidden'
      | 'payload_too_large'
      | 'internal_error'
    >()
  })

  /**
   * `CardFace`, added by story c4-5 (Q1) — and pinned in the two directions that actually bite
   * the detail panel.
   *
   * The panel narrows every face field before drawing it, and the reason that is REQUIRED rather
   * than careful is here in the type: each one is optional AND nullable, so `face.name` is
   * `string | null | undefined` and the three spellings of "absent" are all reachable from one
   * response. A pin that only asserted the alias exists would not have said that.
   */
  it('pins CardFace as all-optional and all-nullable — the reason the panel narrows', () => {
    expectTypeOf<CardFace['name']>().toEqualTypeOf<string | null | undefined>()
    expectTypeOf<CardFace['type_line']>().toEqualTypeOf<string | null | undefined>()
    expectTypeOf<CardFace['oracle_text']>().toEqualTypeOf<string | null | undefined>()
    expectTypeOf<CardFace['mana_cost']>().toEqualTypeOf<string | null | undefined>()
  })

  it('pins CardFace as the element type of `Card.card_faces` — one shape, not two', () => {
    // THE HALF THAT MAKES THE ALIAS LOAD-BEARING. `wire-contract.test.ts` bans a hand-written
    // face shape outside `src/api/`, so the only way the panel can read a face is through this
    // alias — and the only thing that makes the alias correct is that it IS what the hydrated
    // record carries. A regeneration that renamed or restructured the schema reddens here.
    expectTypeOf<NonNullable<Card['card_faces']>[number]>().toEqualTypeOf<CardFace>()
  })

  /**
   * The format-check pair, added by story c4-10 — and pinned on the two properties the panel is
   * BUILT on rather than on "the alias exists".
   *
   * `CHECK_ORDER` and the three-outcome vocabulary are declared constants on the Python side with
   * tests of their own; what a TypeScript consumer needs is that both arrive as **closed
   * string-literal unions**, because that is what makes the label map and the tone map exhaustible
   * by `tsc`. A regeneration that widened either to `string` would leave every map still
   * compiling, every test still green, and a seventh check silently unlabelled — which is the
   * exact failure `Assert<[Exclude<…>] extends [never]>` in `FormatCheck.tsx` exists to catch and
   * which THIS pin is the upstream half of.
   */
  it('pins the six check names as a closed union — the label map depends on it', () => {
    expectTypeOf<FormatCheckRow['check']>().toEqualTypeOf<
      'legality' | 'size' | 'copy_limit' | 'sideboard' | 'banned' | 'rotation'
    >()
  })

  it('pins the three outcomes as a closed union — the tone map depends on it', () => {
    // Three, and no fourth. `deck_validator.py:475-482` declares that as domain vocabulary and
    // says mapping them onto a visual tone is the shell's job — which is why `TONE_FOR_STATUS`
    // lives in the container and `neutral` is unreachable from it.
    expectTypeOf<FormatCheckRow['status']>().toEqualTypeOf<'pass' | 'advisory' | 'violation'>()
  })

  it('pins FormatCheckRow as the element type of the report — one shape, not two', () => {
    // The half that makes the alias load-bearing, exactly as for `CardFace` above:
    // `wire-contract.test.ts` bans a hand-written row shape outside `src/api/`, so the panel can
    // only read a row through this alias, and the only thing that makes the alias correct is that
    // it IS what the report carries.
    expectTypeOf<FormatCheckReport['rows'][number]>().toEqualTypeOf<FormatCheckRow>()
  })

  it('pins `format` as a non-nullable string — the reason there is no `=== null` branch', () => {
    // `deferred-work.md:1972-1981` warned that a "no format" branch keyed on `format === null`
    // would be dead code. It is stronger than that and this is where it is written down: the
    // generated type is `string`, so that branch would not COMPILE. An absent format is `''`,
    // and the field that answers the question is `format_recognized`.
    expectTypeOf<FormatCheckReport['format']>().toEqualTypeOf<string>()
    expectTypeOf<FormatCheckReport['format_recognized']>().toEqualTypeOf<boolean>()
    // …and every field is REQUIRED — no `?`, no `| null` — which is why the narrower in
    // `client.ts` checks shape rather than presence and no consumer writes `?? ''`.
    expectTypeOf<FormatCheckRow['detail']>().toEqualTypeOf<string>()
    expectTypeOf<FormatCheckReport['mainboard_count']>().toEqualTypeOf<number>()
    expectTypeOf<FormatCheckReport['sideboard_count']>().toEqualTypeOf<number>()
  })
})
